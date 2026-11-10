"""Musique aléatoire (option cosmétique du lanceur ; bibliothèque standard seulement).

    python archipelago/installation/musique.py --romfs <ROM déchiffrée | RomFS extrait> [--graine N] [--liste]

Les musiques du jeu sont mélangées ENTRE ELLES (terrain, combat, scènes) ; aucune musique extérieure n'est ajoutée.
Détails et preuves : `docs/systemes/archipelago_musique.md`.

Format [C, lu sur la ROM de l'humain] : les sons sont décrits par les archives sonores `snd/product/yw_sound.bcsar`
et `yw_sound_<lg>.bcsar` (de, es, fr, it, nl, ru ; le jeu charge celle de la langue, chaînes en 0x105D7C..0x105E48
de code.bin). Bloc INFO d'un CSAR : table des sons (0x2100) et table des fichiers (0x2106). Un son « flux » (détail
0x2201) désigne par son index de fichier (`u32` en +0 de l'enregistrement du son) un fichier EXTERNE (0x220D :
chemin `stream/<nom>.dspadpcm.bcstm`, lu à la demande dans le RomFS). La musique de fond est faite de ces flux.

Voie retenue (M1) : pour chaque musique « place » P, l'index de fichier de P et son volume (`u8` en +8) prennent
ceux de la musique tirée σ(P). Deux octets par son, aucune taille ni aucun décalage ne change (tables, chaînes et
bloc FILE intacts) ; le nom du son, son lecteur, sa priorité, ses options et son détail restent ceux de la place
(le jeu appelle toujours le même son par son nom) ; le volume suit la musique (son mixage d'origine).

Règles de compatibilité (une permutation ne mélange que des musiques de la même CLASSE) :
- son flux à boucle (fichier BCSTM : drapeau de boucle à 1) dont le nom est celui d'une musique de fond
  (`MOTIF_MUSIQUE`) : les flux sans boucle (jingles, fanfares, mini-jeux de rythme, scènes calées sur la durée) sont
  exclus, et une scène qui attend la fin d'un morceau n'attend donc jamais une boucle ;
- exclus en plus (`EXCLUS`) : silence (M00), variante silencieuse du temps d'Oni, course de vélo (pistes jouées
  ENSEMBLE ou en alternance), musiques des jeux de rythme (N30..N33 et M67, citées par les partitions
  `data/res/chart/*.chartbin` de `seq/musicgame`), générique chanté (S99) ;
- fichier propre au son (aucun autre son ne cite le même fichier : variantes « basses » d'une même musique) ;
- même fichier dans les 7 archives (une musique chantée ou parlée par langue a des fichiers différents : exclue) ;
- même CLÉ dans les 7 archives : lecteur, octets du détail du flux (pistes allouées, canaux, hauteur, envois,
  volume et panoramique de piste), codec, boucle, nombre de canaux et taille de bloc du BCSTM ;
- groupes « tout / intro / boucle » (`X`, `X_in` ou `X_intro`, `X_main`) gardés ENSEMBLE : un groupe ne s'échange
  qu'avec un groupe (rôle pour rôle) ; un groupe incomplet est exclu.

Le tirage (`random.Random(graine)`, algorithme de Sattolo par classe : toute musique d'une classe d'au moins deux
change) ne dépend que de la graine et de la ROM. La graine vient du lanceur (case cochée), pas de la graine
Archipelago : cosmétique, choisie par le joueur, sans effet sur la logique, les autres joueurs ou le client.

Fichiers produits (générés chez le joueur depuis SA ROM, jamais distribués) :
- Zakuro : `romfs_ext/snd/product/<archive>.bps`, patch BPS « sur place » (LayeredFS de Zakuro parcourt les
  sous-dossiers de `romfs_ext/`, `zakuro-fs/src/layered.rs`, `Tree::patch`) ;
- Azahar : `romfs/snd/product/<archive>` (archive entière, ~21 Mo chacune) : `LayeredFS::LoadExtRelocations`
  d'Azahar ne lit que les fichiers à la RACINE de `romfs_ext/` (boucle sur `result.children` sans descendre dans
  les dossiers, `src/core/file_sys/layered_fs.cpp`), alors que `LoadRelocations` (`romfs/`) est récursif.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import bps as _bps
except ImportError:                     # lancé comme script
    import bps as _bps  # type: ignore[no-redef]

VERSION = 1                              # version de l'algorithme (empreinte de l'estampille)
MEDIA = 0x200
DOSSIER = "snd/product"
LANGUES = ("", "_de", "_es", "_fr", "_it", "_nl", "_ru")
ARCHIVES = tuple(f"yw_sound{lg}.bcsar" for lg in LANGUES)
ARCHIVE_BASE = ARCHIVES[0]

# noms des musiques de fond (règle de nommage du jeu : A00_…, M00_…, N00_…, S00_…, bgm_ev…), saisis à la main
MOTIF_MUSIQUE = re.compile(r"^(A\d\d|M\d\d|N\d\d|S0\d|bgm_ev)")
EXCLUS = re.compile(r"^(M00$|M12_ONI_TIME_SILENT$|M67_KAKURENBO$|N1[0-3]_bike|N3[0-3]_GAME|S99$)")
ROLE = re.compile(r"^(.+?)(_in|_intro|_main)$")
ROLES_GROUPE = ("tout", "intro", "boucle")

T_SONS, T_FICHIERS = 0, 6                # rangs des références de tables dans le bloc INFO
DETAIL_FLUX, FICHIER_EXTERNE = 0x2201, 0x220D
TAILLE_DETAIL = 0x48                     # octets du détail de flux comparés (pistes, canaux, hauteur, envois, piste)


class ErreurMusique(ValueError):
    """RomFS ou archive sonore inattendue : l'option n'est pas installée (avertissement)."""


# ------------------------------------------------------------------------------------------------
# RomFS : fichiers des sous-dossiers (level5.SourceRomfs ne lit que la racine)
# ------------------------------------------------------------------------------------------------
class Romfs:
    """Fichiers du RomFS d'une ROM déchiffrée (NCSD ou NCCH), ou d'un RomFS extrait (dossier) ; chemins en « / »."""

    def __init__(self, chemin: str | Path):
        self.chemin = Path(chemin)
        self.fichiers: dict[str, tuple[int, int]] = {}
        self.dossier = self.chemin.is_dir()
        if not self.dossier:
            self._lire_rom()

    def _lire_rom(self) -> None:
        try:
            f = open(self.chemin, "rb")
        except OSError as e:
            raise ErreurMusique(f"{self.chemin} : {e}") from e
        with f:
            h = f.read(0x200)
            base = 0
            if h[0x100:0x104] == b"NCSD":
                base = struct.unpack_from("<I", h, 0x120)[0] * MEDIA
                f.seek(base)
                h = f.read(0x200)
            if h[0x100:0x104] != b"NCCH":
                raise ErreurMusique(f"{self.chemin} : ni NCSD ni NCCH (ROM déchiffrée attendue)")
            if not h[0x18F] & 0x04:
                raise ErreurMusique(f"{self.chemin} : ROM chiffrée")
            romfs_off, romfs_taille = struct.unpack_from("<II", h, 0x1B0)
            if not romfs_taille:
                raise ErreurMusique(f"{self.chemin} : pas de RomFS")
            ivfc = base + romfs_off * MEDIA
            f.seek(ivfc)
            iv = f.read(0x60)
            if iv[:4] != b"IVFC":
                raise ErreurMusique(f"{self.chemin} : en-tête IVFC introuvable")
            maitre = struct.unpack_from("<I", iv, 0x08)[0]
            bloc3 = 1 << struct.unpack_from("<I", iv, 0x4C)[0]
            n3 = ivfc + ((0x60 + maitre + bloc3 - 1) // bloc3) * bloc3
            f.seek(n3)
            e = struct.unpack("<10I", f.read(0x28))
            f.seek(n3 + e[3])
            dmeta = f.read(e[4])
            f.seek(n3 + e[7])
            fmeta = f.read(e[8])
        donnees = n3 + e[9]
        pile = [(0, "")]
        vus = set()
        while pile:
            d, chemin = pile.pop()
            if d in vus or d + 0x18 > len(dmeta):
                continue
            vus.add(d)
            _par, _frere, enfant, fichier, _suiv, lg = struct.unpack_from("<6I", dmeta, d)
            nom = dmeta[d + 0x18:d + 0x18 + lg].decode("utf-16-le")
            p = f"{chemin}{nom}/" if (chemin or nom) else ""
            while fichier != 0xFFFFFFFF:
                _pf, suivant, off, taille, _h, lgf = struct.unpack_from("<IIQQII", fmeta, fichier)
                self.fichiers[p + fmeta[fichier + 0x20:fichier + 0x20 + lgf].decode("utf-16-le")] = \
                    (donnees + off, taille)
                fichier = suivant
            while enfant != 0xFFFFFFFF:
                pile.append((enfant, p))
                enfant = struct.unpack_from("<I", dmeta, enfant + 4)[0]

    def existe(self, nom: str) -> bool:
        if self.dossier:
            return (self.chemin / nom).is_file()
        return nom in self.fichiers

    def ouvrir(self, nom: str):
        """(fichier binaire ouvert, position, taille)."""
        if self.dossier:
            p = self.chemin / nom
            if not p.is_file():
                raise ErreurMusique(f"{p} introuvable")
            return open(p, "rb"), 0, p.stat().st_size
        if nom not in self.fichiers:
            raise ErreurMusique(f"{nom} absent du RomFS de {self.chemin}")
        off, taille = self.fichiers[nom]
        return open(self.chemin, "rb"), off, taille

    def lire(self, nom: str, debut: int = 0, n: int | None = None) -> bytes:
        f, off, taille = self.ouvrir(nom)
        with f:
            n = taille - debut if n is None else min(n, taille - debut)
            f.seek(off + debut)
            return f.read(n)


# ------------------------------------------------------------------------------------------------
# CSAR / CSTM
# ------------------------------------------------------------------------------------------------
@dataclass
class Son:
    nom: str
    pos: int                     # position de l'enregistrement du son dans l'archive
    fichier: int                 # index de fichier (u32 en +0)
    volume: int                  # u8 en +8
    lecteur: int                 # u32 en +4
    detail: bytes                # TAILLE_DETAIL octets du détail de flux


@dataclass
class Archive:
    nom: str
    taille: int
    sons: dict[str, Son]                         # sons FLUX nommés
    chemins: dict[int, str]                      # index -> chemin externe
    citations: dict[int, int]                    # index de fichier -> nombre de sons (tous types) qui le citent


def lire_tete(tete: bytes) -> tuple[int, int]:
    """(position, taille) du bloc INFO d'après l'en-tête CSAR."""
    if len(tete) < 0x40 or tete[:4] != b"CSAR" or tete[4:6] != b"\xff\xfe":
        raise ErreurMusique("archive sonore inattendue (CSAR petit-boutiste attendu)")
    nb = struct.unpack_from("<H", tete, 0x10)[0]
    blocs = {}
    for i in range(nb):
        idt, _p, o, t = struct.unpack_from("<HHII", tete, 0x14 + i * 12)
        blocs[idt] = (o, t)
    if 0x2000 not in blocs or 0x2001 not in blocs:
        raise ErreurMusique("archive sonore sans bloc STRG ou INFO")
    return blocs[0x2001]


def analyser(nom: str, d: bytes, taille: int) -> Archive:
    """Archive CSAR `d` (au moins jusqu'à la fin du bloc INFO)."""
    try:
        return _analyser(nom, d, taille)
    except (struct.error, IndexError, UnicodeDecodeError, ValueError) as e:
        if isinstance(e, ErreurMusique):
            raise
        raise ErreurMusique(f"{nom} : structure inattendue ({e})") from e


def _analyser(nom: str, d: bytes, taille: int) -> Archive:
    U = lambda o: struct.unpack_from("<I", d, o)[0]          # noqa: E731
    H = lambda o: struct.unpack_from("<H", d, o)[0]          # noqa: E731
    nb = H(0x10)
    blocs = {}
    for i in range(nb):
        idt, _p, o, t = struct.unpack_from("<HHII", d, 0x14 + i * 12)
        blocs[idt] = (o, t)
    strg, info = blocs[0x2000][0] + 8, blocs[0x2001][0] + 8
    if d[strg - 8:strg - 4] != b"STRG" or d[info - 8:info - 4] != b"INFO":
        raise ErreurMusique(f"{nom} : blocs STRG / INFO introuvables")
    t, _p, o = struct.unpack_from("<HHI", d, strg)
    if t != 0x2400:
        raise ErreurMusique(f"{nom} : table de chaînes inattendue")
    st = strg + o
    noms = []
    for i in range(U(st)):
        _ty, _p, oo, sz = struct.unpack_from("<HHII", d, st + 4 + i * 12)
        noms.append(d[st + oo:st + oo + sz - 1].decode("ascii", "replace"))

    def table(k: int, attendu: int) -> list[tuple[int, int]]:
        ty, _p, o = struct.unpack_from("<HHi", d, info + k * 8)
        if ty != attendu:
            raise ErreurMusique(f"{nom} : table {k} du bloc INFO de type {ty:#x}")
        base = info + o
        return [(H(base + 4 + i * 8), base + struct.unpack_from("<i", d, base + 8 + i * 8)[0])
                for i in range(U(base))]

    chemins = {}
    for i, (_t, p) in enumerate(table(T_FICHIERS, 0x2106)):
        if H(p) == FICHIER_EXTERNE:
            q = p + U(p + 4)
            chemins[i] = d[q:d.index(b"\0", q)].decode("ascii")
    sons, citations = {}, {}
    for _t, p in table(T_SONS, 0x2100):
        fid = U(p)
        citations[fid] = citations.get(fid, 0) + 1
        if H(p + 12) != DETAIL_FLUX or not U(p + 0x14) & 1:
            continue
        q = p + U(p + 0x10)
        nm = noms[U(p + 0x18)]
        sons[nm] = Son(nm, p, fid, d[p + 8], U(p + 4), bytes(d[q:q + TAILLE_DETAIL]))
    return Archive(nom, taille, sons, chemins, citations)


@dataclass(frozen=True)
class Flux:
    codec: int
    boucle: int
    canaux: int
    taille_bloc: int
    frequence: int
    echantillons: int


def lire_flux(entete: bytes) -> Flux:
    """Informations d'un BCSTM (en-tête et bloc INFO)."""
    if entete[:4] != b"CSTM":
        raise ErreurMusique("flux BCSTM inattendu")
    nb = struct.unpack_from("<H", entete, 0x10)[0]
    blocs = {}
    for i in range(nb):
        idt, _p, o, t = struct.unpack_from("<HHII", entete, 0x14 + i * 12)
        blocs[idt] = o
    i = blocs[0x4000]
    _t, _p, o = struct.unpack_from("<HHI", entete, i + 8)
    s = i + 8 + o
    codec, boucle, canaux = entete[s], entete[s + 1], entete[s + 2]
    freq, _deb, fin, _nb, bloc = struct.unpack_from("<5I", entete, s + 4)
    return Flux(codec, boucle, canaux, bloc, freq, fin)


# ------------------------------------------------------------------------------------------------
# Choix des musiques et tirage
# ------------------------------------------------------------------------------------------------
@dataclass
class Unite:
    """Une musique, ou un groupe « tout / intro / boucle » : sons par rôle."""
    nom: str
    sons: dict[str, str]                 # rôle -> nom du son
    classe: tuple = ()


@dataclass
class Catalogue:
    archives: dict[str, Archive]
    unites: list[Unite]
    exclus: dict[str, str] = field(default_factory=dict)     # son -> raison


def role_de(nom: str) -> tuple[str, str]:
    m = ROLE.match(nom)
    if not m:
        return nom, "tout"
    return m.group(1), ("boucle" if m.group(2) == "_main" else "intro")


def catalogue(romfs: Romfs, archives: list[str] | None = None) -> Catalogue:
    """Lit les archives sonores présentes (au moins la commune) et classe les musiques mélangeables."""
    noms = [a for a in (archives or ARCHIVES) if romfs.existe(f"{DOSSIER}/{a}")]
    if ARCHIVE_BASE not in noms:
        raise ErreurMusique(f"{DOSSIER}/{ARCHIVE_BASE} absent du RomFS")
    arch = {}
    for a in noms:
        chemin = f"{DOSSIER}/{a}"
        f, off, taille = romfs.ouvrir(chemin)
        with f:
            f.seek(off)
            tete = f.read(0x40)
            pos, t = lire_tete(tete)
            if pos + t > taille:
                raise ErreurMusique(f"{a} : bloc INFO hors du fichier")
            f.seek(off)
            arch[a] = analyser(a, f.read(pos + t), taille)
    base = arch[ARCHIVE_BASE]
    exclus: dict[str, str] = {}
    flux_cache: dict[str, Flux] = {}

    def flux(chemin: str) -> Flux:
        if chemin not in flux_cache:
            flux_cache[chemin] = lire_flux(romfs.lire(f"{DOSSIER}/{chemin}", 0, 0x400))
        return flux_cache[chemin]

    cles: dict[str, tuple] = {}
    for nm, s in sorted(base.sons.items()):
        if not MOTIF_MUSIQUE.match(nm):
            continue
        if EXCLUS.match(nm):
            exclus[nm] = "exclu (liste)"
            continue
        raison, cle = None, None
        for a, ar in arch.items():
            x = ar.sons.get(nm)
            if x is None:
                raison = f"absent de {a}"
                break
            chemin = ar.chemins.get(x.fichier)
            if chemin is None:
                raison = f"fichier interne dans {a}"
                break
            if chemin != base.chemins.get(s.fichier):
                raison = f"fichier propre à la langue ({a})"
                break
            if ar.citations.get(x.fichier, 0) != 1:
                raison = f"fichier partagé avec un autre son ({a})"
                break
            try:
                fl = flux(chemin)
            except (ErreurMusique, struct.error, KeyError) as e:
                raison = f"flux illisible : {e}"
                break
            c = (x.lecteur, x.detail, fl.codec, fl.boucle, fl.canaux, fl.taille_bloc)
            if cle is None:
                cle = c
            elif c != cle:
                raison = f"description différente dans {a}"
                break
        if raison is None and not flux(base.chemins[s.fichier]).boucle:
            raison = "sans boucle"
        if raison is not None:
            exclus[nm] = raison
            continue
        cles[nm] = cle
    # groupes « tout / intro / boucle »
    groupes: dict[str, dict[str, str]] = {}
    for nm in cles:
        b, r = role_de(nm)
        groupes.setdefault(b, {})[r] = nm
    # un son « X_main » sans X n'est pas un groupe ; un nom qui ressemble à un rôle sans groupe complet est exclu
    unites = []
    for b, roles in sorted(groupes.items()):
        if set(roles) == {"tout"}:
            unites.append(Unite(b, roles))
        elif set(roles) == set(ROLES_GROUPE):
            unites.append(Unite(b, roles))
        else:
            for nm in roles.values():
                exclus[nm] = "groupe intro / boucle incomplet"
    for u in unites:
        u.classe = tuple(sorted((r, cles[nm]) for r, nm in u.sons.items()))
    return Catalogue(arch, unites, exclus)


def tirage(cat: Catalogue, graine: int) -> dict[str, str]:
    """Permutation des unités, classe par classe (Sattolo : un seul cycle, aucune unité fixe dans une classe d'au
    moins deux) : {unité place : unité jouée}."""
    rng = random.Random(int(graine))
    classes: dict[tuple, list[str]] = {}
    for u in cat.unites:
        classes.setdefault(u.classe, []).append(u.nom)
    sigma = {}
    for cl in sorted(classes, key=lambda c: min(classes[c])):
        noms = sorted(classes[cl])
        perm = list(noms)
        for i in range(len(perm) - 1, 0, -1):
            j = rng.randrange(i)
            perm[i], perm[j] = perm[j], perm[i]
        sigma.update(zip(noms, perm))
    return sigma


def remplacements(cat: Catalogue, sigma: dict[str, str]) -> dict[str, list[tuple[int, bytes]]]:
    """Par archive : [(position, octets)] (index de fichier en +0 et volume en +8 de chaque son place)."""
    unites = {u.nom: u for u in cat.unites}
    out: dict[str, list[tuple[int, bytes]]] = {}
    for a, ar in cat.archives.items():
        r = []
        for place, jouee in sigma.items():
            if place == jouee:
                continue
            for role, nm in unites[place].sons.items():
                p, src = ar.sons[nm], ar.sons[unites[jouee].sons[role]]
                r.append((p.pos, struct.pack("<I", src.fichier)))
                r.append((p.pos + 8, bytes([src.volume])))
        out[a] = sorted(r)
    return out


# ------------------------------------------------------------------------------------------------
# Fichiers du mod
# ------------------------------------------------------------------------------------------------
@dataclass
class Resultat:
    fichiers: dict[str, bytes]
    avertissements: list[str]
    sigma: dict[str, str]
    archives: list[str]


def chemin_mod(archive: str, emulateur: str) -> str:
    if emulateur == "zakuro":
        return f"romfs_ext/{DOSSIER}/{archive}.bps"
    return f"romfs/{DOSSIER}/{archive}"


def conflit(titre: Path | None, archive: str, nos_fichiers=()) -> Path | None:
    """Fichier d'un AUTRE mod pour cette archive (remplacement ou patch), ou None."""
    if titre is None:
        return None
    autres = [titre / "romfs" / DOSSIER / archive] + \
        [titre / "romfs_ext" / DOSSIER / (archive + e) for e in (".ips", ".bps", ".stub")]
    for a in autres:
        if a.exists() and a.relative_to(titre).as_posix() not in nos_fichiers:
            return a
    return None


def preparer(source: str | Path, graine: int, emulateur: str = "azahar", titre: Path | None = None,
             nos_fichiers=()) -> Resultat:
    """Fichiers du mod pour la graine `graine` (`emulateur` : "zakuro" -> patchs BPS de `romfs_ext/`, sinon
    archives entières dans `romfs/`). `titre` : dossier du titre (archives prises par un autre mod laissées
    intactes). Lève ErreurMusique si l'archive commune est inutilisable."""
    romfs = Romfs(source)
    cat = catalogue(romfs)
    sigma = tirage(cat, graine)
    rempl = remplacements(cat, sigma)
    fichiers, avert, faites = {}, [], []
    for a in sorted(cat.archives):
        autre = conflit(titre, a, nos_fichiers)
        if autre is not None:
            avert.append(f"Musique aléatoire : {autre} existe (autre mod) : {a} laissée intacte")
            continue
        f, off, taille = romfs.ouvrir(f"{DOSSIER}/{a}")
        with f:
            if emulateur == "zakuro":
                donnees = _bps.bps_sur_place(f, off, taille, rempl[a])
            else:
                f.seek(off)
                b = bytearray(f.read(taille))
                if len(b) != taille:
                    raise ErreurMusique(f"{a} : lecture incomplète")
                for pos, octets in rempl[a]:
                    b[pos:pos + len(octets)] = octets
                donnees = bytes(b)
        fichiers[chemin_mod(a, emulateur)] = donnees
        faites.append(a)
    return Resultat(fichiers, avert, sigma, faites)


def voulu(actif: bool, graine: int, emulateur: str) -> dict | None:
    """Empreinte de l'état voulu (clé `musique` de l'estampille), None si l'option est désactivée."""
    if not actif:
        return None
    return {"version": VERSION, "graine": int(graine), "mode": "bps" if emulateur == "zakuro" else "copie"}


def a_refaire(estampille: dict | None, actif: bool, graine: int, emulateur: str) -> bool:
    """L'installation ne correspond pas au choix du joueur (case, graine, émulateur ou version de l'algorithme)."""
    if estampille is None:
        return False                     # rien d'installé : l'installation complète s'en chargera
    infos = estampille.get("infos", {})
    return infos.get("musique") != voulu(actif, graine, emulateur)


def nouvelle_graine() -> int:
    return random.SystemRandom().randrange(1, 2 ** 31)


def empreinte_sigma(sigma: dict[str, str]) -> str:
    return hashlib.sha1(repr(sorted(sigma.items())).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="ROM déchiffrée (.3ds / .cxi) ou RomFS extrait")
    ap.add_argument("--graine", type=int, default=1)
    ap.add_argument("--liste", action="store_true", help="musiques mélangées, classes et exclusions")
    a = ap.parse_args(argv)
    cat = catalogue(Romfs(a.romfs))
    sigma = tirage(cat, a.graine)
    print(f"{len(cat.archives)} archives, {len(cat.unites)} musiques mélangeables, "
          f"{len({u.classe for u in cat.unites})} classes, {len(cat.exclus)} exclues")
    if a.liste:
        for u in cat.unites:
            print(f"  {u.nom:28} -> {sigma[u.nom]:28} {'+'.join(sorted(u.sons))}")
        for nm, r in sorted(cat.exclus.items()):
            print(f"  exclue : {nm:28} {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
