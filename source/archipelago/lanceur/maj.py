"""Mise à jour du lanceur, SANS affichage (README du lanceur, « Mise à jour du lanceur ») : manifeste public,
téléchargement vérifié, préparation de `.maj/`. Le remplacement lui-même est fait par `maj_outil.py`.

Source : `SOURCE_MAJ`, seule adresse contactée, une requête GET sans identifiant ni jeton, au lancement, si la case
« Vérifier les mises à jour au lancement » est cochée. Aucune donnée du joueur n'est envoyée. Fichier absent (404),
réseau coupé, manifeste invalide : silence.

Manifeste (`outils/fabriquer_manifeste_maj.py`, déposé dans `lanceur/maj.json` du dépôt public) :

    {"format": 1, "version": "3.0.0", "build": 202611021530,
     "zip": {"url": "https://raw.githubusercontent.com/…/ykw2ap-exe-3.0.0.zip", "taille": 24528978, "sha256": "…"},
     "page": "https://github.com/…", "notes": {"fr": "…", "en": "…"}, "build_minimal": 0}

`build` : date UTC AAAAMMJJHHMM du commit du paquet (`version.json`, posé par `fabriquer_paquet.py`). La version seule
ne monte pas (toutes les bêtas s'appellent 3.0.0-beta).

Règle de proposition (`proposee`) : build STRICTEMENT plus grand ET version au moins égale ; une bêta de la V3 ne
descend donc jamais vers une V2, même publiée plus tard (build plus grand). Canal : déduit de la version, sans champ
ni second fichier : une version finale n'accepte jamais une pré-version, une pré-version accepte tout ce qui n'est
pas plus ancien. Un seul manifeste, donc une seule version annoncée à la fois.

`build_minimal` : un lanceur plus ancien que ce build ne se met pas à jour seul (changement de ce mécanisme) : il
montre seulement le lien vers `page`, comme le paquet `.pyw`.

Sécurité : `https` seulement, certificat vérifié, hôtes limités (redirections comprises), taille et SHA-256 du zip
contrôlés, zip examiné avant toute écriture. Le SHA-256 vient du même dépôt que le zip : il prouve que le fichier est
complet et intact, pas son auteur (aucune signature ; qui peut pousser sur le dépôt public peut distribuer du code).

Bibliothèque standard seulement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .maj_outil import (DOSSIER_MAJ, ENTREES, FICHIER_JOURNAL, FICHIER_MARQUE, INTERNE, NOM_EXE, lancer_detache,
                        pid_vivant)

# LA source publique. "" : le lanceur ne contacte rien et n'affiche rien.
DEPOT_PUBLIC = "doryan-meunier/Yo-kai-Watch-2-Archipelago"
BASE_PUBLICATION = f"https://raw.githubusercontent.com/{DEPOT_PUBLIC}/main/lanceur"
SOURCE_MAJ = f"{BASE_PUBLICATION}/maj.json"
PAGE_PUBLIQUE = f"https://github.com/{DEPOT_PUBLIC}"
PREFIXE_DEPOT = f"/{DEPOT_PUBLIC}/"               # raw.githubusercontent.com sert TOUS les dépôts : zip de celui-ci
HOTES_ZIP: tuple[str, ...] = ()                  # hôtes admis en plus de celui du manifeste, pour le zip
HOTES_PAGE: tuple[str, ...] = ("github.com",)    # hôtes admis en plus, pour le lien (ouvert dans le navigateur)
FORMAT_MANIFESTE = 1
AGENT = "YKW2AP-Lanceur"                         # fixe : ni version, ni identifiant

DELAI_MANIFESTE = 5.0                            # s
DELAI_TELECHARGEMENT = 30.0                      # s, par lecture
DUREE_MAX_TELECHARGEMENT = 3600.0                # s, en tout (serveur au goutte-à-goutte)
MARGE_DISQUE = 32 << 20                          # octets, en plus de ce qui est calculé
MAX_MANIFESTE = 64 * 1024
MAX_NOTES = 1500                                 # caractères par langue
MAX_ZIP = 512 << 20
MAX_DECOMPRESSE = 1 << 30
MAX_FICHIERS = 8000
RESERVES_WINDOWS = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                    *(f"lpt{i}" for i in range(1, 10))}
_RE_VERSION = re.compile(r"^(\d{1,6})\.(\d{1,6})\.(\d{1,6})(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
_RE_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ErreurMaj(Exception):
    """`cle` : clé de texte de `textes.py` ; `params` : ses paramètres."""

    def __init__(self, cle: str, **params):
        super().__init__(f"{cle} {params}" if params else cle)
        self.cle, self.params = cle, params


@dataclass(frozen=True)
class Source:
    url: str
    hotes_zip: tuple[str, ...] = ()
    hotes_page: tuple[str, ...] = ()
    prefixe_zip: str = ""                        # chemin imposé à l'adresse du zip
    local_admis: bool = False                    # TESTS seulement : http://127.0.0.1 ; jamais posé par le lanceur


def source_publique() -> Source | None:
    """La source du lanceur, ou None (constante vide ou qui n'est pas en https)."""
    s = Source(SOURCE_MAJ, HOTES_ZIP, HOTES_PAGE, PREFIXE_DEPOT)
    return s if SOURCE_MAJ and url_admise(SOURCE_MAJ, s, ()) else None


@dataclass(frozen=True)
class Identite:
    version: str
    build: int
    forme: str                                   # exe | pyw | depot (dépôt : aucune mise à jour)


@dataclass(frozen=True)
class Annonce:
    version: str
    build: int
    url: str
    taille: int
    sha256: str
    page: str
    notes: dict[str, str] = field(default_factory=dict)
    build_minimal: int = 0
    mode: str = "lien"                           # auto (bouton « Mettre à jour ») | lien (page de téléchargement)

    def texte_notes(self, langue: str) -> str:
        return self.notes.get(langue) or self.notes.get("fr") or self.notes.get("en") or ""


# ------------------------------------------------------------------------------------------------ versions
def lire_identite(application: Path, gele: bool) -> Identite:
    """Version du paquet qui s'exécute (`version.json`, à la racine du paquet) ; aucun : dépôt de développement."""
    try:
        d = json.loads((Path(application) / "version.json").read_text(encoding="utf-8"))
        version = str(d["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return Identite("", 0, "exe" if gele else "depot")
    b = d.get("build")
    return Identite(version, b if isinstance(b, int) and not isinstance(b, bool) else 0, "exe" if gele else "pyw")


def cle_version(version: str) -> tuple[int, int, int, int] | None:
    """(majeur, mineur, correctif, 0 pré-version | 1 finale) ; None si ce n'est pas une version."""
    m = _RE_VERSION.match(version or "")
    if m is None:
        return None
    return int(m[1]), int(m[2]), int(m[3]), 0 if m[4] else 1


def proposee(locale: Identite, version: str, build: int) -> bool:
    """Cette version peut-elle être proposée à ce lanceur ? Docstring du module (build, version, canal)."""
    l, d = cle_version(locale.version), cle_version(version)
    if l is None or d is None or build <= locale.build:
        return False
    if l[3] == 1 and d[3] == 0:                  # canal : une version finale n'accepte pas de pré-version
        return False
    return d >= l


# ------------------------------------------------------------------------------------------------ adresses
def url_admise(url: str, source: Source, hotes: tuple[str, ...]) -> bool:
    """`https` (port normal, sans identifiant), hôte du manifeste ou de `hotes`. En test : aussi http://127.0.0.1."""
    try:
        u = urllib.parse.urlsplit(url)
        port = u.port
    except ValueError:
        return False
    hote = (u.hostname or "").lower()
    if u.username or u.password or not hote or any(c in url for c in " \\\r\n\t"):
        return False
    if source.local_admis and u.scheme == "http" and hote == "127.0.0.1":
        return True
    base = (urllib.parse.urlsplit(source.url).hostname or "").lower()
    return u.scheme == "https" and port in (None, 443) and hote in {base, *(h.lower() for h in hotes)}


def zip_admis(url: str, source: Source) -> bool:
    if not url_admise(url, source, source.hotes_zip):
        return False
    chemin = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    return chemin.startswith(source.prefixe_zip) and ".." not in chemin


class _Redirections(urllib.request.HTTPRedirectHandler):
    """Chaque saut d'une redirection repasse le contrôle de l'adresse."""

    def __init__(self, source: Source, hotes: tuple[str, ...]):
        self.source, self.hotes = source, hotes

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not url_admise(newurl, self.source, self.hotes):
            raise ErreurMaj("maj_hote", url=newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def ouvrir_url(url: str, source: Source, hotes: tuple[str, ...], delai: float):
    """GET sans identifiant ; rend une réponse (gestionnaire de contexte). Injectable dans `verifier` et `telecharger`."""
    if not url_admise(url, source, hotes):
        raise ErreurMaj("maj_hote", url=url)
    gestion: list = [_Redirections(source, hotes)]
    if source.local_admis:
        gestion.append(urllib.request.ProxyHandler({}))
    r = urllib.request.Request(url, headers={"User-Agent": AGENT})
    return urllib.request.build_opener(*gestion).open(r, timeout=delai)


# ------------------------------------------------------------------------------------------------ manifeste
def _notes(n: Any) -> dict[str, str]:
    if not isinstance(n, dict) or not isinstance(n.get("fr"), str) or not isinstance(n.get("en"), str):
        raise ErreurMaj("maj_manifeste", detail="notes")
    return {k: "".join(c for c in n[k] if c == "\n" or c.isprintable()).strip()[:MAX_NOTES] for k in ("fr", "en")}


def lire_manifeste(brut: bytes, source: Source) -> Annonce:
    """Manifeste -> Annonce (`mode` « lien », fixé ensuite par `evaluer`) ; ErreurMaj s'il ne convient pas."""
    def refus(detail: str):
        return ErreurMaj("maj_manifeste", detail=detail)
    try:
        d = json.loads(brut.decode("utf-8"))
    except ValueError as e:
        raise refus("JSON") from e
    if not isinstance(d, dict) or d.get("format") != FORMAT_MANIFESTE:
        raise refus("format")
    version, build, z, page = d.get("version"), d.get("build"), d.get("zip"), d.get("page")
    minimal = d.get("build_minimal", 0)
    if not isinstance(version, str) or cle_version(version) is None:
        raise refus("version")
    for nom, v in (("build", build), ("build_minimal", minimal)):
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise refus(nom)
    if not build or not isinstance(z, dict):
        raise refus("build ou zip")
    url, taille, empreinte = z.get("url"), z.get("taille"), z.get("sha256")
    if not isinstance(url, str) or not zip_admis(url, source):
        raise refus("zip.url")
    if not isinstance(taille, int) or isinstance(taille, bool) or not 0 < taille <= MAX_ZIP:
        raise refus("zip.taille")
    if not isinstance(empreinte, str) or _RE_SHA256.match(empreinte) is None:
        raise refus("zip.sha256")
    if not isinstance(page, str) or not url_admise(page, source, source.hotes_page):
        raise refus("page")
    return Annonce(version, build, url, taille, empreinte, page, _notes(d.get("notes")), minimal)


def evaluer(annonce: Annonce, locale: Identite) -> Annonce | None:
    """Annonce à montrer à ce lanceur (avec son `mode`), ou None."""
    if locale.forme == "depot" or not proposee(locale, annonce.version, annonce.build):
        return None
    auto = locale.forme == "exe" and locale.build >= annonce.build_minimal
    return Annonce(**{**annonce.__dict__, "mode": "auto" if auto else "lien"})


def verifier(source: Source | None, locale: Identite, ouvrir: Callable = ouvrir_url) -> Annonce | None:
    """Y a-t-il mieux ? Toujours silencieux : pas de source, dépôt, pas de réseau, manifeste absent ou invalide -> None."""
    if source is None or locale.forme == "depot":
        return None
    try:
        with ouvrir(source.url, source, (), DELAI_MANIFESTE) as r:
            brut = r.read(MAX_MANIFESTE + 1)
        if len(brut) > MAX_MANIFESTE:
            return None
        return evaluer(lire_manifeste(brut, source), locale)
    except Exception:                            # noqa: BLE001 - 404, réseau, ssl, contenu : ne jamais gêner le lanceur
        return None


# ------------------------------------------------------------------------------------------------ téléchargement
def telecharger(annonce: Annonce, cible: Path, source: Source, progression: Callable[[int], None] | None = None,
                ouvrir: Callable = ouvrir_url, duree_max: float = DUREE_MAX_TELECHARGEMENT,
                horloge: Callable[[], float] = time.monotonic) -> None:
    """Zip -> `cible`, taille et SHA-256 contrôlés ; ErreurMaj sinon. `progression` : pourcentage, quand il change."""
    h = hashlib.sha256()
    n = vu = 0
    fin = horloge() + duree_max
    try:
        with ouvrir(annonce.url, source, source.hotes_zip, DELAI_TELECHARGEMENT) as r, open(cible, "wb") as f:
            lire = getattr(r, "read1", r.read)         # read() attendrait 64 Kio d'un serveur très lent
            while True:
                bloc = lire(1 << 16)
                if not bloc:
                    break
                if horloge() > fin:
                    raise ErreurMaj("maj_lent")
                n += len(bloc)
                if n > annonce.taille:
                    raise ErreurMaj("maj_incomplet")
                h.update(bloc)
                f.write(bloc)
                pc = n * 100 // annonce.taille
                if progression is not None and pc != vu:
                    vu = pc
                    progression(pc)
    except ErreurMaj:
        raise
    except Exception as e:                       # noqa: BLE001 - réseau (OSError, http.client) : même message
        raise ErreurMaj("maj_reseau", detail=str(e)) from e
    if n != annonce.taille:
        raise ErreurMaj("maj_incomplet")
    if h.hexdigest() != annonce.sha256:
        raise ErreurMaj("maj_empreinte")


# ------------------------------------------------------------------------------------------------ zip
def chemin_sur(nom: str) -> bool:
    """Nom de membre d'un zip qui reste sous le dossier d'extraction, sous Windows comme ailleurs."""
    if not nom or nom[0] == "/" or "\\" in nom or ":" in nom or any(ord(c) < 32 for c in nom):
        return False
    for p in nom.split("/"):
        base = p.split(".")[0].lower()
        if p in ("", ".", "..") or p[-1] in ". " or base in RESERVES_WINDOWS or any(c in p for c in '<>"|?*'):
            return False
    return True


def controler_zip(z: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    """Membres à extraire [(info, chemin relatif au paquet)] ; ErreurMaj au moindre doute, AVANT toute écriture.
    Un dossier racine unique (`YKW2-Archipelago-exe-<version>/`) est retiré."""
    infos = [i for i in z.infolist() if not i.is_dir()]
    if not infos or len(z.infolist()) > MAX_FICHIERS:
        raise ErreurMaj("maj_zip", detail="nombre de fichiers")
    tetes = {i.filename.split("/")[0] for i in infos}
    racine = next(iter(tetes)) if len(tetes) == 1 and next(iter(tetes)) not in ENTREES else None
    out, vus, total = [], set(), 0
    for i in z.infolist():
        if not chemin_sur(i.filename.rstrip("/")):
            raise ErreurMaj("maj_zip", detail=i.filename)
        if i.is_dir():
            continue
        if i.flag_bits & 1 or stat.S_ISLNK(i.external_attr >> 16):
            raise ErreurMaj("maj_zip", detail=i.filename)
        rel = i.filename[len(racine) + 1:] if racine else i.filename
        if rel.split("/")[0] not in ENTREES or rel.lower() in vus:
            raise ErreurMaj("maj_zip", detail=i.filename)
        vus.add(rel.lower())
        total += i.file_size
        if total > MAX_DECOMPRESSE:
            raise ErreurMaj("maj_zip", detail="taille")
        out.append((i, rel))
    return out


def extraire(chemin: Path, neuf: Path) -> None:
    """Zip contrôlé -> `neuf`. CRC de chaque membre vérifié par zipfile en lisant."""
    try:
        with zipfile.ZipFile(chemin) as z:
            membres = controler_zip(z)
            neuf.mkdir(parents=True, exist_ok=True)
            for info, rel in membres:
                cible = neuf.joinpath(*rel.split("/"))
                cible.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(cible, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
    except (zipfile.BadZipFile, EOFError, ValueError, NotImplementedError) as e:
        raise ErreurMaj("maj_zip", detail=str(e)) from e


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def verifier_paquet(neuf: Path, annonce: Annonce, application: Path) -> None:
    """Le dossier extrait est-il bien ce qui est annoncé, complet ? (`version.json`, exécutable, code, `exe.json` :
    taille et SHA-256 de chaque fichier de l'interpréteur.) ErreurMaj sinon."""
    def refus(detail: str):
        return ErreurMaj("maj_paquet", detail=detail)
    exe = neuf / NOM_EXE
    try:
        if exe.read_bytes()[:2] != b"MZ":
            raise refus(NOM_EXE)
        v = json.loads((neuf / "version.json").read_text(encoding="utf-8"))
        e = json.loads((neuf / "exe.json").read_text(encoding="utf-8"))
        liste = e["interpreteur"]["liste"]
        if v.get("version") != annonce.version or v.get("build") != annonce.build:
            raise refus("version.json")
        if not liste or e.get("executable") != NOM_EXE:
            raise refus("exe.json")
        for f in liste:
            rel = str(f["chemin"])
            p = neuf.joinpath(*rel.split("/"))
            if not chemin_sur(rel) or not p.is_file() or p.stat().st_size != f["taille"] or _sha256(p) != f["sha256"]:
                raise refus(rel)
    except (OSError, ValueError, KeyError, TypeError) as x:
        raise refus(repr(x)) from x
    if not (neuf / INTERNE / "archipelago" / "lanceur" / "demarrage.py").is_file():
        raise refus("code du lanceur")
    for nom in ("patch/manifeste.json", "patch/code.bps", "patch/exheader.bps"):
        if not neuf.joinpath(*nom.split("/")).is_file():
            raise refus(nom)
    if (application / "zakuro" / "zakuro.exe").is_file() and not (neuf / "zakuro" / "zakuro.exe").is_file():
        raise refus("zakuro")                    # le joueur perdrait son émulateur


def reprendre_zakuro(application: Path, neuf: Path) -> None:
    """`zakuro/` est remplacé en bloc : ce que le paquet ne connaît pas y est reporté, et un `zakuro.exe` identique
    garde sa date (`installation/zakuro.empreinte` : taille + date ; une autre date imposerait une recompilation)."""
    ancien = application / "zakuro"
    if not ancien.is_dir():
        return
    for p in sorted(ancien.rglob("*")):
        rel = p.relative_to(ancien)
        c = neuf / "zakuro" / rel
        if p.is_file() and not c.exists():
            c.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, c)
    a, n = ancien / "zakuro.exe", neuf / "zakuro" / "zakuro.exe"
    if a.is_file() and n.is_file() and _sha256(a) == _sha256(n):
        st = a.stat()
        os.utime(n, ns=(st.st_atime_ns, st.st_mtime_ns))


def copier_outil(exe: Path, cible: Path) -> Path:
    """Copie de l'exécutable en cours et de son `_internal/`, d'où s'exécutera `--role maj` : l'original doit pouvoir
    être déplacé. Rend le chemin de l'exécutable copié."""
    cible.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, cible / exe.name)
    shutil.copytree(exe.parent / INTERNE, cible / INTERNE, ignore=shutil.ignore_patterns("__pycache__"))
    return cible / exe.name


# ------------------------------------------------------------------------------------------------ déroulement
def besoin_extraction(chemin: Path) -> int:
    """Octets une fois extrait (contrôle complet du zip fait ensuite par `extraire`)."""
    try:
        with zipfile.ZipFile(chemin) as z:
            return sum(i.file_size for i, _r in controler_zip(z))
    except (zipfile.BadZipFile, EOFError, ValueError, NotImplementedError) as e:
        raise ErreurMaj("maj_zip", detail=str(e)) from e


def taille_outil(exe: Path) -> int:
    """Copie `.maj/outil` : exécutable + `_internal/`."""
    return exe.stat().st_size + sum(p.stat().st_size for p in (exe.parent / INTERNE).rglob("*") if p.is_file())


def verifier_place(application: Path, besoin: int) -> None:
    if shutil.disk_usage(application).free < besoin + MARGE_DISQUE:
        raise ErreurMaj("maj_disque")


def nettoyer_restes(application: Path) -> None:
    """Retire `.maj/` laissé par la mise à jour précédente (`.maj/outil`, qui ne pouvait pas s'effacer lui-même), sauf
    si une préparation est en cours (autre fenêtre) ou s'il reste un journal d'échange (`maj_outil.reprendre` : dans
    `.maj/ancien` peut se trouver ce qui manque au dossier)."""
    d = Path(application) / DOSSIER_MAJ
    if not d.is_dir() or (d / FICHIER_JOURNAL).exists():
        return
    try:
        if pid_vivant(int((d / FICHIER_MARQUE).read_text(encoding="ascii").strip())):
            return
    except (OSError, ValueError):
        pass
    shutil.rmtree(d, ignore_errors=True)


def preparer(annonce: Annonce, source: Source, application: Path, exe: Path, donnees: Path,
             avant_lancement: Callable[[], None], *, rappel: Callable[[str, dict], None] | None = None,
             ouvrir: Callable = ouvrir_url, lancer: Callable = lancer_detache) -> list[str]:
    """Télécharge, contrôle, prépare `.maj/` et lance l'outil ; rend sa commande. Tout échec avant le lancement :
    `.maj/` retiré, rien d'autre n'a changé. `avant_lancement` : dernier contrôle (refus) et arrêt du client de suivi."""
    dire = rappel or (lambda c, p: None)
    d = application / DOSSIER_MAJ
    nettoyer_restes(application)
    if d.exists():
        raise ErreurMaj("maj_deja")
    try:
        d.mkdir()
        (d / FICHIER_MARQUE).write_text(str(os.getpid()), encoding="ascii")
    except OSError as e:
        raise ErreurMaj("maj_dossier", detail=str(e)) from e
    try:
        verifier_place(application, annonce.taille)
        z = d / "paquet.zip"
        dire("maj_etape_telechargement", {"pc": 0})
        telecharger(annonce, z, source, lambda pc: dire("maj_etape_telechargement", {"pc": pc}), ouvrir)
        dire("maj_etape_controle", {})
        neuf = d / "neuf"
        verifier_place(application, besoin_extraction(z) + taille_outil(exe))
        extraire(z, neuf)
        z.unlink()
        verifier_paquet(neuf, annonce, application)
        reprendre_zakuro(application, neuf)
        outil = copier_outil(exe, d / "outil")
        avant_lancement()
        cmd = [str(outil), "--role", "maj", "--application", str(application), "--pid", str(os.getpid()),
               "--donnees", str(donnees)]
        lancer(cmd)
        return cmd
    except OSError as e:
        shutil.rmtree(d, ignore_errors=True)
        raise ErreurMaj("maj_dossier", detail=str(e)) from e
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
