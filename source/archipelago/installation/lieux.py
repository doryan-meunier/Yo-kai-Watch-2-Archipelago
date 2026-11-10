"""Table des « lieux libres » (invités posés ailleurs qu'à l'Auberge) : lecture de la table, hauteur du sol déduite
des points connus de la carte, relevé de ces points pour le contrôle visuel (bibliothèque standard seulement).

La TABLE (`lieux_libres.txt`, à côté de ce fichier) est une donnée du MOD saisie à la main : espèce (hachage
`CHARA_PARAM`), carte, coordonnées (règle 6 de CLAUDE.md : noms, identifiants numériques et adresses saisis à la
main). Une ligne par lieu, `#` = commentaire :

    <espèce 0x…>  <carte>:<x>,<z>            [y=<hauteur>] [angle=<degrés>] [condition=…] [reste]
    <espèce 0x…>  <carte>:<x>,<y>,<z>[,<angle>]  [condition=…] [reste]

- `carte:x,z` est exactement ce que copie le bouton « Copier ma position » du lanceur (vue Carte, « Suivre le
  jeu ») ; la hauteur y est alors DÉDUITE des points connus les plus proches de la carte (`hauteur`), sauf `y=`.
- `condition=toujours` (défaut) ou `condition=bit:0x<hachage d'un flag global>`.
- `reste` : le Yo-kai reste à sa place après le combat (pas de scène d'adieu, on peut lui reparler tout de suite) :
  voir `lieu_libre.py` (déclencheur de carte qui passe avant celui de la table commune).

Limite de la chaîne utilisée (celle de la Suite de l'Auberge) : UN invité par carte.

Les points connus viennent du RomFS du joueur et ne sont jamais écrits dans le dépôt.
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import level5 as L, t2b
except ImportError:                     # lancé comme script
    import level5 as L  # type: ignore[no-redef]
    import t2b  # type: ignore[no-redef]

FICHIER_TABLE = Path(__file__).with_name("lieux_libres.txt")
DOSSIER_CARTES = "data/res/map/"
NOM_PCK = "npc.pck"
EXT_POSITION = ".npcbin"
PREFIXE_NOM = "ap_lieu_"

BUCHINYAN = 0x6BB26576
RAYON = 120.0                 # unités monde : au-delà, un point connu ne dit rien de la hauteur
VOISINS = 6
ECART_MAX = 1.5               # écart de hauteur entre voisins au-delà duquel on signale une pente / un étage
LOIN = 60.0                   # point le plus proche au-delà : hauteur peu sûre


@dataclass
class Lieu:
    carte: str = "t101g00"
    x: float = 496.0
    y: float | None = 0.0                # None : à déduire des points connus de la carte (`resoudre_hauteur`)
    z: float = 72.0
    angle: float = 0.0
    espece: int = BUCHINYAN              # CHARA_PARAM
    condition: str = "toujours"          # "toujours" ou "bit:0x<hachage du flag global>"
    nom: str = PREFIXE_NOM + "00"        # nom du fichier de position (sans extension)
    combat: bool = True                  # (premier lieu seulement) réécrire le combattant de la rencontre commune
    reste: bool = False                  # pas de scène d'adieu : le PNJ reste après le combat
    note: str = ""                       # commentaire de la table (jamais écrit dans le jeu)

    def decrire(self) -> str:
        return "%s (%g, %s, %g) angle %g, espèce 0x%08X, condition %s%s" % (
            self.carte, self.x, "?" if self.y is None else "%g" % self.y, self.z, self.angle, self.espece,
            self.condition, ", reste" if self.reste else "")


def lire_position(texte: str) -> tuple[str, float, float | None, float, float | None]:
    """« carte:x,z » (copié du lanceur), « carte:x,y,z » ou « carte:x,y,z,angle » -> (carte, x, y | None, z,
    angle | None). ErreurFormat sinon."""
    try:
        carte, coord = texte.strip().split(":")
        v = [float(c) for c in coord.split(",")]
        if len(v) not in (2, 3, 4) or not (carte.isascii() and carte.isalnum()) or not all(map(math.isfinite, v)):
            raise ValueError
    except ValueError:
        raise L.ErreurFormat(f"lieu « {texte} » : attendu carte:x,z ou carte:x,y,z[,angle]") from None
    if len(v) == 2:
        return carte, v[0], None, v[1], None
    return carte, v[0], v[1], v[2], (v[3] if len(v) == 4 else None)


def lire_ligne(ligne: str, rang: int = 0) -> Lieu | None:
    """Une ligne de la table -> Lieu (None : ligne vide ou commentaire). ErreurFormat si elle est mal formée."""
    corps, _sep, note = ligne.partition("#")
    mots = corps.split()
    if not mots:
        return None
    if len(mots) < 2:
        raise L.ErreurFormat(f"ligne « {ligne.strip()} » : attendu <espèce> <carte:x,z> [options]")
    try:
        espece = int(mots[0], 16) if mots[0].lower().startswith("0x") else -1
    except ValueError:
        espece = -1
    if not 0 < espece <= 0xFFFFFFFF:
        raise L.ErreurFormat(f"espèce « {mots[0]} » : hachage CHARA_PARAM attendu (0x…)")
    carte, x, y, z, angle = lire_position(mots[1])
    lieu = Lieu(carte, x, y, z, angle or 0.0, espece, nom=PREFIXE_NOM + "%02d" % rang, note=note.strip())
    for m in mots[2:]:
        cle, sep, val = m.partition("=")
        try:
            if m == "reste":
                lieu.reste = True
            elif cle == "y" and sep:
                lieu.y = float(val)
            elif cle == "angle" and sep:
                lieu.angle = float(val)
            elif cle == "condition" and sep:
                lieu.condition = val
            else:
                raise ValueError
        except ValueError:
            raise L.ErreurFormat(f"option « {m} » inconnue (y=, angle=, condition=, reste)") from None
    return lieu


def lire_table(texte: str) -> list[Lieu]:
    """Texte de la table -> lieux, dans l'ordre (noms de fichier `ap_lieu_NN` par rang). ErreurFormat avec le n° de
    ligne ; deux lieux sur la même carte sont refusés (limite de la chaîne de l'Auberge)."""
    lieux: list[Lieu] = []
    for n, ligne in enumerate(texte.splitlines(), 1):
        try:
            lieu = lire_ligne(ligne, len(lieux))
        except L.ErreurFormat as e:
            raise L.ErreurFormat(f"ligne {n} : {e}") from None
        if lieu is not None:
            lieux.append(lieu)
    verifier_table(lieux)
    return lieux


def verifier_table(lieux: list[Lieu]) -> None:
    vues: dict[str, int] = {}
    noms = set()
    for k, lieu in enumerate(lieux):
        if lieu.carte in vues:
            raise L.ErreurFormat("deux invités sur la carte %s (lieux n° %d et %d) : un seul par carte avec la "
                                 "chaîne de l'Auberge" % (lieu.carte, vues[lieu.carte] + 1, k + 1))
        vues[lieu.carte] = k
        if lieu.nom in noms or not lieu.nom.isascii() or not lieu.nom.replace("_", "").isalnum():
            raise L.ErreurFormat(f"nom de fichier de position invalide ou en double : {lieu.nom}")
        noms.add(lieu.nom)


def charger_table(chemin: str | Path | None = None) -> list[Lieu]:
    chemin = Path(chemin) if chemin else FICHIER_TABLE
    try:
        return lire_table(chemin.read_text(encoding="utf-8"))
    except OSError as e:
        raise L.ErreurFormat(f"table des lieux illisible : {e}") from e


def ligne_table(lieu: Lieu) -> str:
    """Ligne de table d'un lieu (forme complète, y explicite s'il est connu)."""
    mots = ["0x%08X" % lieu.espece, "%s:%g,%g" % (lieu.carte, lieu.x, lieu.z)]
    if lieu.y is not None:
        mots.append("y=%g" % lieu.y)
    if lieu.angle:
        mots.append("angle=%g" % lieu.angle)
    if lieu.condition != "toujours":
        mots.append("condition=" + lieu.condition)
    if lieu.reste:
        mots.append("reste")
    return "  ".join(mots) + ("  # " + lieu.note if lieu.note else "")


# ------------------------------------------------------------------------------------------------
# Points connus d'une carte
# ------------------------------------------------------------------------------------------------
@dataclass
class Point:
    x: float
    y: float
    z: float
    genre: str            # pnj | errant | animal | zone
    nom: str = ""


def _signe(v):
    return struct.unpack("<i", struct.pack("<I", v))[0] if isinstance(v, int) and v >= 0x80000000 else v


def _nombre(v) -> float | None:
    v = _signe(v)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def genre_position(nom: str) -> str:
    """Genre d'un fichier de position d'après son nom (`enc_pth_…`, `enm_…` : errants ; `ani_…` : animaux)."""
    if nom.startswith(("enc_", "enm_")):
        return "errant"
    if nom.startswith("ani_"):
        return "animal"
    return "pnj"


def points_position(data: bytes, nom: str) -> list[Point]:
    """`POINT` (x, y, z, angle) d'un fichier `.npcbin`."""
    out = []
    try:
        c = t2b.Cfg(data)
    except t2b.ErreurCfg:
        return out
    for e in c.par_nom("POINT"):
        v = [_nombre(x) for x in c.valeurs(e)[:3]]
        if len(v) == 3 and None not in v:
            out.append(Point(v[0], v[1], v[2], genre_position(nom), nom))
    return out


def points_zones(data: bytes, nom: str) -> list[Point]:
    """`SHAPE_DATA_ITEM` / `POINT_DATA_ITEM` (identifiant, x, y, z, …) d'un `_oneplace_pos` ou d'un `_layout.bin` :
    zones de déclencheurs, coffres, points à examiner."""
    out = []
    try:
        c = t2b.Cfg(data)
    except (t2b.ErreurCfg, struct.error, IndexError):
        return out
    for e in c.entrees:
        if c.nom(e) not in ("SHAPE_DATA_ITEM", "POINT_DATA_ITEM") or len(e.mots) < 4:
            continue
        v = [_nombre(x) for x in c.valeurs(e)[1:4]]
        if None not in v:
            out.append(Point(v[0], v[1], v[2], "zone", "%s 0x%08X" % (nom, e.mots[0])))
    return out


def points_carte(arc: "L.Arc0", carte: str) -> list[Point]:
    """Points connus de la carte, en visite normale : fichiers de position des PNJ, errants et animaux (dossier de
    la carte et `npc.pck`), zones et points du `.pck` de la carte. Les fichiers des salles de portail mystère
    (`_gate`) sont écartés (autre disposition de la carte). Liste vide si la carte n'existe pas."""
    dossier = DOSSIER_CARTES + carte + "/"
    pts: list[Point] = []
    vus = set()
    try:
        x = L.Xpck(arc.lire(dossier + NOM_PCK))
        for n, _o, _t in x.fichiers:
            if n.endswith(EXT_POSITION) and "_gate" not in n:
                vus.add(n)
                pts += points_position(x.lire(n), n[:-len(EXT_POSITION)])
    except (L.ErreurFormat, KeyError, struct.error, IndexError, ValueError):
        pass
    for k in sorted(arc.entrees):
        if k.startswith(dossier) and k.endswith(EXT_POSITION) and "/" not in k[len(dossier):]:
            n = k[len(dossier):]
            if n not in vus and "_gate" not in n and not n.startswith(PREFIXE_NOM):
                pts += points_position(arc.lire(k), n[:-len(EXT_POSITION)])
    try:
        x = L.Xpck(arc.lire(dossier + carte + ".pck"))
        for n, _o, _t in x.fichiers:
            if "_gate" in n:
                continue
            if n.endswith("_layout.bin") or "_oneplace_pos" in n:
                pts += points_zones(x.lire(n), "zone")
    except (L.ErreurFormat, KeyError, struct.error, IndexError, ValueError):
        pass
    return pts


# ------------------------------------------------------------------------------------------------
# Hauteur
# ------------------------------------------------------------------------------------------------
@dataclass
class Hauteur:
    y: float | None                                  # None : aucun point connu assez proche
    voisins: list[tuple[float, Point]] = field(default_factory=list)    # (distance, point), du plus proche au plus loin
    ecart: float = 0.0                               # max - min des hauteurs des voisins
    avertissement: str = ""

    @property
    def sure(self) -> bool:
        return self.y is not None and not self.avertissement


def hauteur(points: list[Point], x: float, z: float) -> Hauteur:
    """Hauteur du sol en (x, z) = celle du point connu le plus proche (distance horizontale) ; les `VOISINS` plus
    proches dans `RAYON` servent de témoins : s'ils divergent de plus d'`ECART_MAX` (pente, escalier, étage), ou si
    le plus proche est à plus de `LOIN`, un avertissement demande de donner y à la main (`y=` dans la table)."""
    proches = sorted(((math.hypot(p.x - x, p.z - z), p) for p in points), key=lambda t: t[0])
    proches = [t for t in proches if t[0] <= RAYON][:VOISINS]
    if not proches:
        return Hauteur(None, [], 0.0, "aucun point connu à moins de %g unités : donner y à la main (y=…)" % RAYON)
    ys = [p.y for _d, p in proches]
    h = Hauteur(proches[0][1].y, proches, max(ys) - min(ys))
    if h.ecart > ECART_MAX:
        h.avertissement = ("hauteurs voisines de %g à %g (pente ou étage) : y = %g pris au point le plus proche "
                           "(%s, à %.0f unités) ; à vérifier en jeu, ou donner y=…"
                           % (min(ys), max(ys), h.y, proches[0][1].nom or proches[0][1].genre, proches[0][0]))
    elif proches[0][0] > LOIN:
        h.avertissement = ("point connu le plus proche à %.0f unités : y = %g peu sûr, à vérifier en jeu ou donner "
                           "y=…" % (proches[0][0], h.y))
    return h


def resoudre_hauteur(arc: "L.Arc0", lieu: Lieu, cache: dict | None = None) -> Hauteur | None:
    """Donne à `lieu.y` la hauteur déduite s'il n'en a pas (None rendu : y était donné à la main). ErreurFormat si
    aucun point connu ne permet de la déduire."""
    if lieu.y is not None:
        return None
    cache = cache if cache is not None else {}
    if lieu.carte not in cache:
        cache[lieu.carte] = points_carte(arc, lieu.carte)
    h = hauteur(cache[lieu.carte], lieu.x, lieu.z)
    if h.y is None:
        raise L.ErreurFormat(f"{lieu.carte} ({lieu.x:g}, {lieu.z:g}) : {h.avertissement}")
    lieu.y = h.y
    return h


_RE_PRESSE_PAPIERS = re.compile(r"^\s*([A-Za-z0-9]+:-?[0-9.]+,-?[0-9.]+)")


def position_copiee(texte: str) -> str | None:
    """Extrait « carte:x,z » d'une ligne copiée du lanceur (« t101g00:496,72  # Les Hauts de Granval »)."""
    m = _RE_PRESSE_PAPIERS.match(texte or "")
    return m.group(1) if m else None
