"""Import d'un mod d'apparence de la communauté (bouton « Importer un mod d'apparence » de l'onglet « Apparence »).

    python archipelago/installation/apparence_import.py --romfs <ROM | RomFS> <mod.zip | dossier | yw2_a.fa>

Demande de l'humain du 2026-10-27. Les mods d'apparence (GameBanana…) ne sont PAS redistribuables (licences du type
CC BY-NC-ND) : rien n'en est distribué avec le mod Archipelago ; c'est le joueur qui importe le fichier qu'il a
téléchargé, et les fichiers retenus sont copiés dans SON dossier de données (`apparence/import/`), jamais dans git.

Entrées acceptées (formats rencontrés) :
- zip (« YWML » : `YWML.json` et fichiers libres `include/data/character/…`, ou `romfs/yw2_a.fa` complet), lu par
  `zipfile` SANS extraction sur disque ;
- dossier (mêmes dispositions, fichiers libres ou `yw2_a.fa`) ;
- `yw2_a.fa` complet (archive reconstruite par un moddeur : lecteur TOLÉRANT, `TeteArc0`, la dernière chaîne de la
  table des noms peut manquer de zéro final), comparé à celui du joueur fichier par fichier ;
- `.rar` / `.7z` : refusés avec un message (à extraire d'abord : aucun outil externe n'est lancé).

Tri : ne sont retenus que les REMPLACEMENTS de fichiers qui existent déjà dans le `yw2_a.fa` du joueur, de contenu
différent, dans la liste blanche `data/character/c00*`, `data/character/y*`, `data/menu/bustup/*`. Tout le reste
est ignoré et listé (fichiers ajoutés, identiques, hors liste blanche, chemins suspects…).

Sûreté : aucun chemin du mod n'est utilisé pour écrire (fichiers stockés sous leur SHA-1, chemin du jeu dans le
manifeste, seulement s'il existe dans la ROM) ; chemins absolus, lecteurs, `..` refusés ; tailles bornées (fichier
retenu, total, nombre d'entrées, tables d'archive) ; rien n'est exécuté.

Avertissements (le fichier est retenu sauf mention) :
- `os` : un modèle perd des os nommés du modèle d'origine (animations, surtout de cinématique) ;
- `texture` : une texture plus grande que celle du jeu (mémoire du jeu serrée : docs/systemes/memoire.md) ;
- `p10` : une partie d'animation `_pNN` (NN ≠ 00) remplacée par un MODÈLE (erreur d'un mod pyjama sur Katie) :
  fichier NON retenu.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import apparence as A, level5 as L
except ImportError:                     # lancé comme script
    import apparence as A  # type: ignore[no-redef]
    import level5 as L  # type: ignore[no-redef]

VERSION = 1
ARCHIVE = A.ARCHIVE
LISTE_BLANCHE = ("data/" + "character/c00", "data/" + "character/y", "data/menu/bustup/")
DOSSIER = "import"                          # sous <données>/apparence/
MANIFESTE = "manifeste.json"
TAILLE_FICHIER_MAX = 32 << 20               # fichier retenu
TAILLE_TOTALE_MAX = 256 << 20               # total retenu
ENTREES_MAX = 200_000                       # fichiers d'un zip, d'un dossier ou d'une archive
TETE_MAX = 64 << 20                         # tables d'un yw2_a.fa
LU_MAX = 3 << 30                            # octets lus (décompressés) au total : un yw2_a.fa complet fait ~0,9 Go
EXEMPLES_MAX = 200                          # chemins ignorés gardés par raison dans le manifeste
EXTENSIONS_A_EXTRAIRE = (".rar", ".7z")
RAISONS = ("ajoute", "hors_liste", "identique", "p10", "illisible", "suspect", "trop_gros", "autre_archive",
           "hors_romfs")
PARTIE_ANIMATION = re.compile(r"_p(?!00)\d\d\.xc$")


class ErreurImport(ValueError):
    """Import impossible : `cle` = clé de texte du lanceur (textes_apparence.py), `params` ses paramètres."""

    def __init__(self, cle: str, **params):
        super().__init__(f"{cle} {params}" if params else cle)
        self.cle, self.params = cle, params


# ------------------------------------------------------------------------------------------------ chemins
def chemin_sur(brut: str) -> str | None:
    """Nom d'une entrée de zip / d'un fichier de dossier en chemin POSIX relatif ; None si suspect (absolu,
    lecteur, `..`, caractère de contrôle)."""
    n = brut.replace("\\", "/")
    if not n or n.startswith("/") or re.match(r"^[A-Za-z]:", n) or any(ord(c) < 32 for c in n):
        return None
    parts = [p for p in n.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def chemin_jeu(rel: str, entrees) -> str | None:
    """Chemin du jeu d'un fichier du mod : à partir d'un segment `data` (`include/data/…`, `romfs/data/…`) ; le
    premier qui existe dans l'archive du joueur, sinon le premier (fichier ajouté) ; None sans segment `data`."""
    parts = rel.split("/")
    cands = ["/".join(parts[i:]) for i, p in enumerate(parts) if p.lower() == "data" and i < len(parts) - 1]
    for c in cands:
        if c in entrees:
            return c
        if c.lower() in entrees:
            return c.lower()
    return cands[0] if cands else None


def dans_liste_blanche(ch: str) -> bool:
    return ch.startswith(LISTE_BLANCHE)


# ------------------------------------------------------------------------------------------------ ARC0 tolérant
class TeteArc0:
    """Tables d'une archive ARC0 lues depuis sa tête (octets 0..début des données) ; tolérant : la dernière chaîne
    de la table des noms peut manquer de zéro final (archives reconstruites par des moddeurs)."""

    def __init__(self, tete: bytes):
        if tete[:4] != b"ARC0" or len(tete) < 0x48:
            raise ErreurImport("app_imp_fa_invalide")
        off_d, _h, off_f, off_n, self.off_donnees = struct.unpack_from("<5I", tete, 4)
        nb_d = struct.unpack_from("<H", tete, 0x18)[0]
        try:
            d, fi, noms = (L.decompresser(tete, o) for o in (off_d, off_f, off_n))
        except (L.ErreurFormat, IndexError, ValueError, struct.error) as e:
            raise ErreurImport("app_imp_fa_invalide") from e

        def chaine(o):
            e = noms.find(b"\0", o)
            return noms[o:e if e >= 0 else len(noms)].decode("ascii", "replace")
        self.entrees: dict[str, tuple[int, int]] = {}      # chemin -> (offset absolu dans l'archive, taille)
        vus = 0                                            # itérations (des doublons ne font pas grandir `entrees`)
        try:
            for i in range(nb_d):
                _c, _a, _b, f0, fn, off_nf, off_nd = struct.unpack_from("<IhhhhII", d, i * 20)
                nd = chaine(off_nd)
                for j in range(f0 & 0xFFFF, (f0 & 0xFFFF) + (fn & 0xFFFF)):
                    vus += 1
                    if vus > ENTREES_MAX:
                        raise ErreurImport("app_imp_trop_d_entrees")
                    _fc, on, of, ta = struct.unpack_from("<4I", fi, j * 16)
                    self.entrees[nd + chaine(off_nf + on)] = (self.off_donnees + of, ta)
                    if len(self.entrees) > ENTREES_MAX:
                        raise ErreurImport("app_imp_trop_d_entrees")
        except struct.error as e:
            raise ErreurImport("app_imp_fa_invalide") from e

    @staticmethod
    def lire_tete(f) -> bytes:
        """Tête d'une archive lue depuis le DÉBUT d'un flux (fichier ou membre de zip, lecture en avant)."""
        h = f.read(0x48)
        if len(h) < 0x48 or h[:4] != b"ARC0":
            raise ErreurImport("app_imp_fa_invalide")
        off = struct.unpack_from("<I", h, 0x14)[0]
        if not 0x48 <= off <= TETE_MAX:
            raise ErreurImport("app_imp_fa_invalide")
        return h + f.read(off - 0x48)


# ------------------------------------------------------------------------------------------------ analyse
@dataclass
class Analyse:
    """Résultat d'un import (avant stockage)."""
    nom: str
    retenus: dict = field(default_factory=dict)          # chemin du jeu -> contenu
    ignores: dict = field(default_factory=dict)          # raison -> [chemins] (EXEMPLES_MAX au plus)
    nombres: dict = field(default_factory=dict)          # raison -> nombre
    avertissements: list = field(default_factory=list)   # {"cle", "chemin", "params"}
    archive_complete: bool = False

    def ignorer(self, raison: str, chemin: str) -> None:
        self.nombres[raison] = self.nombres.get(raison, 0) + 1
        lst = self.ignores.setdefault(raison, [])
        if len(lst) < EXEMPLES_MAX:
            lst.append(chemin)

    def avertir(self, cle: str, chemin: str, **params) -> None:
        self.avertissements.append({"cle": cle, "chemin": chemin, "params": params})


def _textures(x: L.Xpck) -> dict[str, tuple[int, int]]:
    out = {}
    for n in x.par_nom:
        if n.endswith(".xi"):
            d = x.lire(n)
            if len(d) >= 0x14 and d[:4] == b"IMGC":
                out[n] = struct.unpack_from("<HH", d, 0x10)
    return out


def examiner(an: Analyse, ch: str, mod: bytes, rom: bytes) -> bool:
    """Contrôles d'un remplacement (avertissements) ; False : fichier non retenu (raison notée)."""
    try:
        xr = L.Xpck(rom)
    except L.ErreurFormat:
        return True                                    # fichier du jeu non XPCK : rien à comparer
    try:
        xm = L.Xpck(mod)
    except (L.ErreurFormat, IndexError, ValueError, struct.error):
        an.ignorer("illisible", ch)
        return False
    modele_m = any(n.endswith((".prm", ".mbn")) for n in xm.par_nom)
    modele_r = any(n.endswith((".prm", ".mbn")) for n in xr.par_nom)
    if PARTIE_ANIMATION.search(ch) and modele_m and not modele_r:
        an.avertir("p10", ch)
        an.ignorer("p10", ch)
        return False
    try:
        so, sm = A.squelette(xr), A.squelette(xm)
    except (L.ErreurFormat, IndexError, ValueError, struct.error):
        so, sm = {}, {}
    perdus = A.os_perdus(so, sm) if so and sm else []
    if perdus:
        an.avertir("os", ch, n=len(perdus), total=len(so), noms=", ".join(perdus[:8]) + (" …" if len(perdus) > 8
                                                                                          else ""))
    try:
        tm, tr = _textures(xm), _textures(xr)
    except (L.ErreurFormat, IndexError, ValueError, struct.error):
        tm, tr = {}, {}
    if tr:
        ref_max = max(w * h for w, h in tr.values())
        for n, (w, h) in sorted(tm.items()):
            w0, h0 = tr.get(n, (0, 0))
            ref = w0 * h0 or ref_max
            if w * h > ref:
                an.avertir("texture", ch, nom=n, l=w, h=h, l0=w0 or None, h0=h0 or None)
                break
    return True


def analyser(source: L.SourceRomfs, chemin: str | Path, progres=None) -> Analyse:
    """Lit le mod `chemin` (zip, dossier ou `yw2_a.fa`) et le compare au `yw2_a.fa` du joueur. ErreurImport si le
    mod ne peut pas être lu. `progres(n)` : appelé de temps en temps (nombre de fichiers vus)."""
    chemin = Path(chemin)
    if chemin.suffix.lower() in EXTENSIONS_A_EXTRAIRE:
        raise ErreurImport("app_imp_extraire", ext=chemin.suffix.lower())
    if not chemin.exists():
        raise ErreurImport("app_imp_introuvable")
    an = Analyse(chemin.name)
    f, base, _t = source.ouvrir(ARCHIVE)
    with f:
        rom = L.Arc0(f, base)
        ctx = _Contexte(an, rom, progres)
        if chemin.is_dir():
            _dossier(ctx, chemin)
        elif zipfile.is_zipfile(chemin):
            _zip(ctx, chemin)
        else:
            with open(chemin, "rb") as g:
                if g.read(4) != b"ARC0":
                    raise ErreurImport("app_imp_format")
                g.seek(0)
                _archive(ctx, ctx.borne(g))
    if not an.retenus and not an.archive_complete and not any(n for n in an.nombres.values()):
        raise ErreurImport("app_imp_vide")
    return an


class _Borne:
    """Flux en lecture seule dont les octets lus s'ajoutent au compteur du contexte (zip bombe, fichier géant)."""

    def __init__(self, ctx, f):
        self._ctx, self._f = ctx, f

    def read(self, n: int = -1) -> bytes:
        d = self._f.read(n)
        self._ctx.lu += len(d)
        if self._ctx.lu > LU_MAX:
            raise ErreurImport("app_imp_trop_gros")
        return d


class _Contexte:
    def __init__(self, an: Analyse, rom: L.Arc0, progres):
        self.an, self.rom, self.progres = an, rom, progres
        self.total = 0
        self.vus = 0
        self.lu = 0                                    # octets lus au total (flux bornés par `borne`)

    def borne(self, f):
        """`f` enveloppé : la lecture cumulée de tout l'import est bornée (`LU_MAX`), quoi que disent les en-têtes."""
        return _Borne(self, f)

    def compter(self) -> None:
        self.vus += 1
        if self.vus > ENTREES_MAX:
            raise ErreurImport("app_imp_trop_d_entrees")
        if self.progres and self.vus % 500 == 0:
            self.progres(self.vus)

    def proposer(self, ch: str, taille: int, lire, lister_identique: bool = True) -> None:
        """Fichier `ch` (chemin du jeu) de `taille` octets, lu par `lire()` seulement s'il peut être retenu
        (`lister_identique` faux : un fichier identique à la ROM n'est pas listé, cas d'une archive complète)."""
        an = self.an
        if ch not in self.rom.entrees:
            an.ignorer("ajoute", ch)
            return
        if not dans_liste_blanche(ch):
            an.ignorer("hors_liste", ch)
            return
        if taille > TAILLE_FICHIER_MAX:
            an.ignorer("trop_gros", ch)
            return
        mod = lire()
        if len(mod) > TAILLE_FICHIER_MAX:
            an.ignorer("trop_gros", ch)
            return
        orig = self.rom.lire(ch)
        if mod == orig:
            if lister_identique:
                an.ignorer("identique", ch)
            return
        if not examiner(an, ch, mod, orig):
            return
        if ch in an.retenus:
            an.avertir("double", ch)
        self.total += len(mod) - len(an.retenus.get(ch, b""))
        if self.total > TAILLE_TOTALE_MAX:
            raise ErreurImport("app_imp_trop_gros")
        an.retenus[ch] = mod

    def fichier_libre(self, rel_brut: str, taille: int, lire, ouvrir_archive) -> None:
        self.compter()
        rel = chemin_sur(rel_brut)
        if rel is None:
            self.an.ignorer("suspect", rel_brut[:200])
            return
        nom = rel.rsplit("/", 1)[-1].lower()
        if nom.endswith(".fa"):
            if nom == ARCHIVE:
                ouvrir_archive()
            else:
                self.an.ignorer("autre_archive", rel)
            return
        ch = chemin_jeu(rel, self.rom.entrees)
        if ch is None:
            self.an.ignorer("hors_romfs", rel)
            return
        self.proposer(ch, taille, lire)


def _lire_borne(f, limite: int = TAILLE_FICHIER_MAX) -> bytes:
    """Au plus `limite` + 1 octets (un en-tête de zip peut mentir sur la taille : le reste n'est jamais lu)."""
    return f.read(limite + 1)


def _est_lien(p: Path) -> bool:
    """Lien symbolique, ou point d'analyse Windows (jonction : `is_symlink` ne la voit pas)."""
    try:
        st = os.lstat(p)
    except OSError:
        return True
    return p.is_symlink() or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def _dossier(ctx: _Contexte, racine: Path) -> None:
    for dp, dns, fns in os.walk(racine, followlinks=False):
        dns[:] = sorted(d for d in dns if not _est_lien(Path(dp) / d))
        for n in sorted(fns):
            p = Path(dp) / n
            if _est_lien(p) or not p.is_file():
                continue
            rel = p.relative_to(racine).as_posix()

            def lire(p=p):
                with open(p, "rb") as g:
                    return _lire_borne(ctx.borne(g))

            def archive(p=p):
                with open(p, "rb") as g:
                    _archive(ctx, ctx.borne(g))
            ctx.fichier_libre(rel, p.stat().st_size, lire, archive)


def _zip(ctx: _Contexte, chemin: Path) -> None:
    try:
        z = zipfile.ZipFile(chemin)
    except (zipfile.BadZipFile, OSError) as e:
        raise ErreurImport("app_imp_zip_invalide") from e
    with z:
        for info in z.infolist():
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise ErreurImport("app_imp_zip_chiffre")

            def lire(info=info):
                with z.open(info) as g:
                    return _lire_borne(ctx.borne(g))

            def archive(info=info):
                with z.open(info) as g:
                    _archive(ctx, ctx.borne(g))
            try:
                ctx.fichier_libre(info.filename, info.file_size, lire, archive)
            except (zipfile.BadZipFile, NotImplementedError, EOFError, OSError) as e:
                raise ErreurImport("app_imp_zip_invalide") from e


def _archive(ctx: _Contexte, f) -> None:
    """`yw2_a.fa` complet lu en AVANT seulement (fichier ou membre de zip) : tête, puis contenus dans l'ordre des
    offsets ; seuls les fichiers communs avec la ROM sont lus (comparaison complète) ; un contenu hors liste blanche
    différent est listé « hors liste », un identique n'est pas listé."""
    an = ctx.an
    an.archive_complete = True
    tete = TeteArc0.lire_tete(f)
    t = TeteArc0(tete)
    pos = len(tete)
    rom = ctx.rom
    for ch, (off, taille) in sorted(t.entrees.items(), key=lambda e: e[1][0]):
        ctx.compter()
        if chemin_sur(ch) is None:
            an.ignorer("suspect", ch[:200])
            continue
        if ch not in rom.entrees:
            an.ignorer("ajoute", ch)
            continue
        if off < pos:
            continue                                     # fichiers qui se recouvrent : ignorés
        if not dans_liste_blanche(ch) and taille != rom.entrees[ch][1]:
            an.ignorer("hors_liste", ch)                 # taille différente : modifié, sans le lire
            continue
        if taille > TAILLE_FICHIER_MAX:
            an.ignorer("trop_gros", ch)
            continue
        _sauter(f, off - pos)
        d = f.read(taille)
        pos = off + len(d)
        if len(d) != taille:
            raise ErreurImport("app_imp_fa_invalide")
        if dans_liste_blanche(ch):
            ctx.proposer(ch, taille, lambda d=d: d, lister_identique=False)
        elif d != rom.lire(ch):
            an.ignorer("hors_liste", ch)


def _sauter(f, n: int) -> None:
    while n > 0:
        b = f.read(min(n, 1 << 20))
        if not b:
            raise ErreurImport("app_imp_fa_invalide")
        n -= len(b)


# ------------------------------------------------------------------------------------------------ stockage
def dossier_import(donnees: str | Path) -> Path:
    return Path(donnees) / "apparence" / DOSSIER


def empreinte_fichiers(fichiers: dict) -> str:
    """Empreinte du contenu importé : {chemin: sha1} triés."""
    return hashlib.sha1(json.dumps({"v": VERSION, "f": fichiers}, sort_keys=True).encode()).hexdigest()[:16]


def enregistrer(an: Analyse, donnees: str | Path) -> dict:
    """Copie les fichiers retenus dans `<données>/apparence/import/` (un fichier par contenu, nommé par son SHA-1)
    avec le manifeste, à la place d'un import précédent (remplacement en fin d'écriture). Renvoie le manifeste."""
    if not an.retenus:
        raise ErreurImport("app_imp_rien")
    cible = dossier_import(donnees)
    tmp = cible.with_name(DOSSIER + ".nouveau")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    fichiers = {}
    for ch, contenu in sorted(an.retenus.items()):
        h = hashlib.sha1(contenu).hexdigest()
        (tmp / f"{h}.bin").write_bytes(contenu)
        fichiers[ch] = {"sha1": h, "taille": len(contenu)}
    m = {"version": VERSION, "nom": an.nom, "date": time.strftime("%Y-%m-%d %H:%M"),
         "empreinte": empreinte_fichiers({c: v["sha1"] for c, v in fichiers.items()}),
         "fichiers": fichiers, "ignores": an.ignores, "nombres": an.nombres, "avertissements": an.avertissements,
         "archive_complete": an.archive_complete}
    (tmp / MANIFESTE).write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    ancien = cible.with_name(DOSSIER + ".ancien")
    if ancien.exists():
        shutil.rmtree(ancien)
    if cible.exists():
        cible.rename(ancien)
    tmp.rename(cible)
    if ancien.exists():
        shutil.rmtree(ancien, ignore_errors=True)
    return m


def lire_manifeste(donnees: str | Path) -> dict | None:
    """Manifeste de l'import présent (None : aucun, ou illisible)."""
    p = dossier_import(donnees) / MANIFESTE
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(m, dict) or not isinstance(m.get("fichiers"), dict) or not m.get("empreinte"):
        return None
    return m


def retirer(donnees: str | Path) -> None:
    """Supprime l'import (copie locale des fichiers retenus, dans le dossier de données du lanceur seulement)."""
    d = dossier_import(donnees)
    if d.exists():
        shutil.rmtree(d)


def reglage(donnees: str | Path) -> dict | None:
    """Clé `import` du réglage effectif d'apparence (apparence.normaliser) ; None sans import valide."""
    m = lire_manifeste(donnees)
    if m is None:
        return None
    return {"dossier": str(dossier_import(donnees)), "empreinte": m["empreinte"]}


def charger(dossier: Path, empreinte: str | None = None) -> dict[str, bytes]:
    """{chemin du jeu: contenu} d'un import ; A.ErreurApparence si le manifeste manque, si son empreinte n'est pas
    celle attendue ou si un fichier a changé (SHA-1)."""
    try:
        m = json.loads((Path(dossier) / MANIFESTE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise A.ErreurApparence(f"mod importé illisible ({e})") from e
    if empreinte is not None and m.get("empreinte") != empreinte:
        raise A.ErreurApparence("mod importé changé depuis le réglage")
    out = {}
    for ch, v in sorted(m.get("fichiers", {}).items()):
        if chemin_sur(ch) != ch or not dans_liste_blanche(ch) or not re.fullmatch(r"[0-9a-f]{40}", v.get("sha1", "")):
            raise A.ErreurApparence(f"mod importé : entrée invalide ({ch})")
        try:
            d = (Path(dossier) / f"{v['sha1']}.bin").read_bytes()
        except OSError as e:
            raise A.ErreurApparence(f"mod importé : {ch} illisible ({e})") from e
        if hashlib.sha1(d).hexdigest() != v["sha1"]:
            raise A.ErreurApparence(f"mod importé : {ch} modifié")
        out[ch] = d
    return out


def chemins_tenue(personnage: str, reglage_perso) -> set[str]:
    """Chemins que la tenue d'un personnage peut changer (conflits montrés à l'import, sans lire la ROM)."""
    n = A.normaliser({personnage: reglage_perso}).get(personnage)
    if n is None:
        return set()
    out = {A.chemin_xc(A.HEROS[personnage])}
    if n["tenue"] in A.CACHEES:
        if A.CACHEES[n["tenue"]]:
            out |= {A.chemin_xc(A.CINEMATIQUE[personnage], p) for p in A.PARTIES_CINEMATIQUE}
        return out
    return out | {A.chemin_xc(m) for m in A.AUTRES_MODELES[personnage]}


def conflits(manifeste: dict | None, reglage_brut) -> list[str]:
    """Chemins du mod importé qui remplacent ceux de la tenue choisie (triés)."""
    if not manifeste:
        return []
    r = reglage_brut if isinstance(reglage_brut, dict) else {}
    tenue = set()
    for p in A.PERSONNAGES:
        tenue |= chemins_tenue(p, r.get(p))
    return sorted(tenue & set(manifeste.get("fichiers", {})))


# ------------------------------------------------------------------------------------------------ outil
def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="dossier du RomFS extrait, ou ROM déchiffrée")
    ap.add_argument("mod", type=Path)
    a = ap.parse_args(argv)
    try:
        an = analyser(L.SourceRomfs(a.romfs), a.mod)
    except ErreurImport as e:
        print(f"refusé : {e.cle} {e.params}")
        return 1
    for ch, d in sorted(an.retenus.items()):
        print(f"retenu   {ch} ({len(d)} o)")
    for r, n in sorted(an.nombres.items()):
        print(f"ignorés  {r} : {n}" + (f" (ex. {', '.join(an.ignores.get(r, [])[:3])})" if an.ignores.get(r) else ""))
    for av in an.avertissements:
        print(f"attention {av['cle']} {av['chemin']} {av['params']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
