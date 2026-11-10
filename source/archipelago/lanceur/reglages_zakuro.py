"""Réglages de Zakuro (la version PC du jeu) lus et écrits par le lanceur, **sans affichage**.

Zakuro garde ses réglages dans `%APPDATA%\\zakuro\\settings.toml` (Windows ; `~/Library/Application Support/zakuro`
sous macOS, `$XDG_CONFIG_HOME/zakuro` ailleurs), quel que soit son `--data` [C, `crates/zakuro/src/settings.rs`,
fonction `path`]. Il ne lit ce fichier qu'à son lancement (`Settings::load` dans `lib.rs`) et le réécrit EN ENTIER
depuis ce qu'il a en mémoire à chaque changement fait dans sa fenêtre (menu Settings, F9 / F10, choix du dossier de
jeux, améliorations), pas en quittant. Conséquences :
- un réglage écrit ici s'applique au prochain lancement de Zakuro ;
- si Zakuro est ouvert, un changement fait ensuite dans SA fenêtre remet ses anciennes valeurs (la vue le dit).

Lecture de Zakuro (serde) : champ absent = valeur par défaut ; valeur d'énumération inconnue = valeur par défaut de
ce champ seulement (`or_default`) ; mauvais TYPE ailleurs (ex. `resolution = "x"`) = fichier entier rejeté, mis de côté
en `settings.toml.bad`, toutes les valeurs par défaut. Champs inconnus : ignorés (et perdus à sa prochaine écriture).

Écriture ici (`ecrire`) : relire - modifier - écrire, sous un verrou du lanceur, en ne touchant QUE les lignes des
réglages changés de la table racine (tout le reste du fichier, tables `[keys]` / `[pad]` / `[enhancements]`, champs
inconnus, est recopié octet pour octet) ; le résultat est relu par `tomllib` et comparé à l'attendu avant d'être posé
(écriture atomique : fichier temporaire du même dossier puis `os.replace`). Rien n'est écrit si aucune valeur ne
change ; sans fichier, il n'est créé qu'à l'enregistrement, avec les seuls réglages changés (Zakuro complète le reste
par ses valeurs par défaut). Bibliothèque standard seulement (`tomllib` en lecture).
"""
from __future__ import annotations

import contextlib
import math
import os
import re
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

VARIABLE_CHEMIN = "YKW2AP_ZAKURO_REGLAGES"      # chemin du fichier (essais : jamais le vrai %APPDATA%)


@dataclass(frozen=True)
class Reglage:
    """Un réglage simple de la table racine de `settings.toml`.

    genre : "choix" (chaîne d'une énumération de Zakuro, `snake_case`), "entier" (u32 borné par le menu de Zakuro),
    "booleen", "reel" (f32 entre `mini` et `maxi`). `proposes` : valeurs offertes par le lanceur (sous-ensemble de
    `valeurs`, que Zakuro accepte toutes)."""
    cle: str
    genre: str
    defaut: Any
    valeurs: tuple = ()
    proposes: tuple = ()
    mini: float = 0
    maxi: float = 0


# Langues que le jeu (version européenne) a dans son RomFS : yw2_lg_<engb|fr|de|es|it|nl|ru>.fa
# (docs/formats/level5.md) ; Zakuro en connaît 12 (énumération `Language`), toutes acceptées à la lecture.
LANGUES_ZAKURO = ("japanese", "english", "french", "german", "italian", "spanish", "chinese_simplified", "korean",
                  "dutch", "portuguese", "russian", "chinese_traditional")
LANGUES_JEU = ("english", "french", "german", "italian", "spanish", "dutch", "russian")
DISPOSITIONS = ("stacked", "side_by_side", "large_top", "top_only", "bottom_only")     # ordre du menu de Zakuro
FILTRES = ("smooth", "sharp", "pixels")
# place des écrans dans une fenêtre plus large qu'eux (patch 0004 de Zakuro, `docs/systemes/version_pc.md` §8) ; un
# Zakuro sans ce patch ignore la clé (champ inconnu) et la perd à sa prochaine réécriture du fichier
ALIGNEMENTS = ("center", "left", "right")

REGLAGES: tuple[Reglage, ...] = (
    Reglage("language", "choix", "english", LANGUES_ZAKURO, LANGUES_JEU),
    Reglage("resolution", "entier", 3, mini=1, maxi=8),
    Reglage("frame_interpolation", "booleen", False),
    Reglage("scale", "entier", 2, mini=1, maxi=6),
    Reglage("layout", "choix", "stacked", DISPOSITIONS, DISPOSITIONS),
    Reglage("filter", "choix", "smooth", FILTRES, FILTRES),
    Reglage("integer_scale", "booleen", False),
    Reglage("screen_alignment", "choix", "center", ALIGNEMENTS, ALIGNEMENTS),
    Reglage("volume", "reel", 1.0, mini=0.0, maxi=1.0),
    Reglage("mute", "booleen", False),
    Reglage("show_fps", "booleen", False),
)
PAR_CLE = {r.cle: r for r in REGLAGES}

# lus seulement (réglages de développeur, pas proposés) : sans rendu 3D par le GPU, la résolution et l'interpolation
# n'ont pas d'effet ; l'interpolation demande aussi le présentateur Vulkan (menu de Zakuro, `menus.rs`)
LUS_SEULEMENT = {"hardware_rasterizer": ("booleen", True), "renderer": ("choix", "vulkan")}


class ErreurReglages(Exception):
    """Fichier illisible, valeur refusée ou écriture impossible ; `cle` : clé du texte à montrer."""

    def __init__(self, cle: str, detail: str = ""):
        super().__init__(detail or cle)
        self.cle, self.detail = cle, detail


# ------------------------------------------------------------------------------------------------ chemin
def chemin_reglages(environ: dict | None = None, plateforme: str | None = None) -> Path | None:
    """Où Zakuro lit ses réglages (même règle que `settings.rs`), ou le chemin de `YKW2AP_ZAKURO_REGLAGES`."""
    env = os.environ if environ is None else environ
    plateforme = sys.platform if plateforme is None else plateforme
    if env.get(VARIABLE_CHEMIN):
        return Path(env[VARIABLE_CHEMIN])

    def var(nom):
        v = env.get(nom)
        return Path(v) if v else None
    if plateforme.startswith("win"):
        d = var("APPDATA")
    elif plateforme == "darwin":
        d = var("HOME") / "Library/Application Support" if var("HOME") else None
    else:
        d = var("XDG_CONFIG_HOME") or (var("HOME") / ".config" if var("HOME") else None)
    return d / "zakuro" / "settings.toml" if d else None


# ------------------------------------------------------------------------------------------------ valeurs
def valide(cle: str, valeur: Any) -> bool:
    """La valeur est-elle acceptable pour ce réglage (type exact de Zakuro, bornes de son menu) ?"""
    r = PAR_CLE.get(cle)
    if r is None:
        return False
    if r.genre == "booleen":
        return isinstance(valeur, bool)
    if r.genre == "entier":
        return isinstance(valeur, int) and not isinstance(valeur, bool) and r.mini <= valeur <= r.maxi
    if r.genre == "reel":
        return (isinstance(valeur, (int, float)) and not isinstance(valeur, bool) and math.isfinite(valeur)
                and r.mini <= valeur <= r.maxi)
    return isinstance(valeur, str) and valeur in r.valeurs


def valeurs_par_defaut() -> dict[str, Any]:
    return {r.cle: r.defaut for r in REGLAGES}


@dataclass
class Lecture:
    """Ce que Zakuro verrait au lancement, pour les réglages du lanceur.

    existe : le fichier existe ; erreur : clé du texte si illisible (valeurs = défauts, écriture refusée) ;
    rejete : Zakuro rejetterait le fichier entier (mauvais type d'un champ qu'il lit sans repli) ;
    hors_bornes : réglages présents mais hors de ce que le lanceur propose (affichés à leur valeur par défaut, ou
    bornés), laissés tels quels tant qu'on n'y touche pas ; signature : (taille, date) pour voir un changement."""
    chemin: Path | None
    existe: bool = False
    valeurs: dict = field(default_factory=valeurs_par_defaut)
    erreur: str | None = None
    rejete: bool = False
    hors_bornes: set = field(default_factory=set)
    gpu_3d: bool = True
    vulkan: bool = True
    signature: tuple | None = None


def signature(chemin: Path | None) -> tuple | None:
    if chemin is None:
        return None
    try:
        s = chemin.stat()
    except OSError:
        return None
    return (s.st_size, s.st_mtime_ns)


def _decoder(octets: bytes) -> tuple[str, bool]:
    bom = octets.startswith(b"\xef\xbb\xbf")
    return octets[3:].decode("utf-8") if bom else octets.decode("utf-8"), bom


def lire(chemin: Path | None) -> Lecture:
    """Lit `settings.toml` ; sans fichier : valeurs par défaut de Zakuro (rien n'est créé)."""
    lec = Lecture(chemin)
    if chemin is None:
        lec.erreur = "rz_err_chemin"
        return lec
    lec.signature = signature(chemin)
    try:
        octets = chemin.read_bytes()
    except FileNotFoundError:
        return lec
    except OSError:
        lec.existe, lec.erreur = chemin.exists(), "rz_err_lecture"
        return lec
    lec.existe = True
    try:
        donnees = tomllib.loads(_decoder(octets)[0])
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        lec.erreur = "rz_err_illisible"
        return lec
    for r in REGLAGES:
        if r.cle not in donnees:
            continue
        v = donnees[r.cle]
        if valide(r.cle, v):
            lec.valeurs[r.cle] = float(v) if r.genre == "reel" else v
            continue
        lec.hors_bornes.add(r.cle)
        if r.genre == "choix":
            pass                           # `or_default` : valeur inconnue (ou d'un autre type) = valeur par défaut
        elif r.genre == "entier" and isinstance(v, int) and not isinstance(v, bool):
            lec.valeurs[r.cle] = min(max(v, int(r.mini)), int(r.maxi))     # u32 accepté par Zakuro, hors menu
            lec.rejete |= not 0 <= v <= 0xFFFFFFFF                         # pas un u32 : fichier rejeté
        elif r.genre == "reel" and isinstance(v, (int, float)) and not isinstance(v, bool):
            lec.valeurs[r.cle] = min(max(float(v), r.mini), r.maxi) if math.isfinite(v) else r.defaut
        else:
            lec.rejete = True              # mauvais type d'un champ sans repli : Zakuro rejette tout le fichier
    hw, ren = donnees.get("hardware_rasterizer", True), donnees.get("renderer", "vulkan")
    lec.gpu_3d = hw if isinstance(hw, bool) else True
    lec.vulkan = ren != "opengl"
    return lec


# ------------------------------------------------------------------------------------------------ écriture
def _toml(valeur: Any) -> str:
    """Valeur TOML d'un réglage (types de `REGLAGES` seulement)."""
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    if isinstance(valeur, int):
        return str(valeur)
    if isinstance(valeur, float):
        if not math.isfinite(valeur):
            raise ErreurReglages("rz_err_valeur", repr(valeur))
        texte = repr(valeur)
        return texte if any(c in texte for c in ".en") else texte + ".0"
    if isinstance(valeur, str):
        echappe = []
        for c in valeur:
            if c in '"\\':
                echappe.append("\\" + c)
            elif ord(c) < 0x20 or ord(c) == 0x7F:
                echappe.append(f"\\u{ord(c):04x}")
            else:
                echappe.append(c)
        return '"' + "".join(echappe) + '"'
    raise ErreurReglages("rz_err_valeur", repr(valeur))


_RE_TABLE = re.compile(r"^\s*\[")
_RE_VALEUR = re.compile(r"""\s*(?:"(?:[^"\\]|\\.)*"|'[^']*'|[^#\s]+)(\s*#.*)?$""")


def _motif_cle(cle: str) -> re.Pattern:
    return re.compile(r"^\s*(?:%s|\"%s\"|'%s')\s*=" % ((re.escape(cle),) * 3))


def appliquer_texte(texte: str, changements: dict[str, Any]) -> str:
    """Texte TOML avec les lignes `cle = valeur` des réglages changés remplacées (ou ajoutées à la fin de la table
    racine, avant le premier en-tête de table) ; le reste du texte est inchangé."""
    nl = "\r\n" if "\r\n" in texte else "\n"
    lignes = texte.splitlines(keepends=True)
    fin_racine = next((i for i, ligne in enumerate(lignes) if _RE_TABLE.match(ligne)), len(lignes))
    a_ajouter = []
    for cle, valeur in changements.items():
        nouvelle = f"{cle} = {_toml(valeur)}"
        motif = _motif_cle(cle)
        trouvees = [i for i in range(fin_racine) if motif.match(lignes[i])]
        if trouvees:
            i = trouvees[0]
            fin = lignes[i][len(lignes[i].rstrip("\r\n")):] or nl
            corps = lignes[i].rstrip("\r\n")
            reste = _RE_VALEUR.match(corps, motif.match(corps).end())
            commentaire = reste.group(1) if reste and reste.group(1) else ""      # commentaire de fin de ligne gardé
            lignes[i] = nouvelle + commentaire + fin
        else:
            a_ajouter.append(nouvelle + nl)
    if a_ajouter:
        i = fin_racine
        while i > 0 and not lignes[i - 1].strip():          # après la dernière ligne non vide de la racine
            i -= 1
        if i > 0 and not lignes[i - 1].endswith(("\n", "\r")):
            lignes[i - 1] += nl
        if i == fin_racine < len(lignes):                    # collé à un en-tête de table : une ligne vide entre
            a_ajouter.append(nl)
        lignes[i:i] = a_ajouter
    return "".join(lignes)


def _normal(v: Any) -> Any:
    """Valeur TOML comparable (NaN égal à lui-même, tables et listes en profondeur)."""
    if isinstance(v, float) and math.isnan(v):
        return ("nan",)
    if isinstance(v, dict):
        return {k: _normal(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_normal(x) for x in v]
    return v


def _egal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, abs_tol=1e-6)
    return a == b


@contextlib.contextmanager
def _sans_verrou():
    yield


def ecrire(chemin: Path | None, changements: dict[str, Any], *,
           verrou: Callable[[], contextlib.AbstractContextManager] | None = None,
           essais: int = 5) -> dict[str, Any]:
    """Écrit les réglages `changements` dans `settings.toml` en gardant tout le reste ; renvoie les réglages
    réellement changés dans le fichier (vide : rien n'a été écrit). Lève `ErreurReglages`."""
    if chemin is None:
        raise ErreurReglages("rz_err_chemin")
    for cle, valeur in changements.items():
        if not valide(cle, valeur):
            raise ErreurReglages("rz_err_valeur", f"{cle} = {valeur!r}")
    changements = {k: float(v) if PAR_CLE[k].genre == "reel" else v for k, v in changements.items()}
    with (verrou or _sans_verrou)():
        try:
            octets = chemin.read_bytes()
        except FileNotFoundError:
            octets = b""
        except OSError as e:
            raise ErreurReglages("rz_err_lecture", str(e)) from e
        try:
            texte, bom = _decoder(octets)
            avant = tomllib.loads(texte)
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
            raise ErreurReglages("rz_err_illisible", str(e)) from e
        utiles = {}
        for cle, valeur in changements.items():
            actuel = avant.get(cle, PAR_CLE[cle].defaut)
            if cle in avant and _egal(actuel, valeur):
                continue
            if cle not in avant and _egal(PAR_CLE[cle].defaut, valeur):
                continue                                     # déjà la valeur par défaut de Zakuro
            utiles[cle] = valeur
        if not utiles:
            return {}
        nouveau = appliquer_texte(texte, utiles)
        # contrôle avant de poser : tout le reste identique, les changements présents
        try:
            apres = tomllib.loads(nouveau)
        except tomllib.TOMLDecodeError as e:
            raise ErreurReglages("rz_err_controle", str(e)) from e
        attendu = dict(avant)
        attendu.update(utiles)
        if _normal(apres) != _normal(attendu) or any(type(apres[k]) is not type(v) for k, v in utiles.items()):
            raise ErreurReglages("rz_err_controle", "contenu relu différent de l'attendu")
        donnees = (b"\xef\xbb\xbf" if bom else b"") + nouveau.encode("utf-8")
        _poser(chemin, donnees, essais)
    return utiles


def _poser(chemin: Path, donnees: bytes, essais: int) -> None:
    """Écriture atomique : temporaire du même dossier, puis remplacement (réessayé si le fichier est pris)."""
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ErreurReglages("rz_err_ecriture", str(e)) from e
    tmp = chemin.with_name(f"{chemin.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(donnees)
            f.flush()
            os.fsync(f.fileno())
        for n in range(essais):
            try:
                os.replace(tmp, chemin)
                return
            except PermissionError:
                if n == essais - 1:
                    raise
                time.sleep(0.05 * (n + 1))
    except OSError as e:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise ErreurReglages("rz_err_ecriture", str(e)) from e
