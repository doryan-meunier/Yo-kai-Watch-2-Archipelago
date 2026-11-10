"""Sous-onglet « Carte » de l'onglet « Checks » (tracker sur cartes, façon PopTracker), SANS affichage : lecture de
`cartes/cartes_local.json` (généré chez le joueur par `installation/cartes.py`), cartes d'une région, marqueurs
(regroupement, couleur), compteurs, colonne des objets de progression, génération en tâche de fond. La vue tkinter
est dans `vue_cartes.py` ; les checks, leurs états et les filtres viennent de `checks.py` (même modèle, mêmes
filtres, même sélection que la liste).

**Aucun spoiler** : les marqueurs et infobulles n'utilisent que `checks.Check` (contenu connu seulement si fait ou
indiqué). Les images et positions sont des données du jeu, lues dans le dossier de données du joueur, jamais
versionnées ni distribuées. Bibliothèque standard seulement.
"""
from __future__ import annotations

import sys
import threading
import time
import unicodedata
import zlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

ARCHIPELAGO = Path(__file__).resolve().parents[1]
if str(ARCHIPELAGO) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO))

from installation import cartes as CA  # noqa: E402

from . import checks as CK  # noqa: E402
from . import textes as TX  # noqa: E402
from . import tracker as TK  # noqa: E402

import lieu_local as LL  # noqa: E402  (client/, sur sys.path depuis `checks` : lieu du joueur écrit par le client)

CHAPITRES_OBJECTIF = 10                   # objectif « finir le chapitre 10 » (APWorld)
RANGS_MONTRE = "EDCBAS"                   # exemplaires de « Rang de montre » reçus : 0 = E .. 4 = A, 5 = S (logique.py ;
                                          # 5e exemplaire : graines à rang S par l'objet, ap/rang-s-objet)
ORDRE_GENRES = {"exterieur": 0, "donjon": 1, "interieur": 2, "autre": 3}
MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "l", "d", "a", "à", "of", "the"}


# ------------------------------------------------------------------------------------------------ données locales
@dataclass
class InfoCarte:
    id: str
    png: Path
    largeur: int
    hauteur: int
    genre: str
    monde: tuple[float, ...] | None = None    # (x0, z0, x1, z1, Vw, Vh) : monde -> pixel (format 3 ; None : inconnu)


@dataclass
class Position:
    carte: str
    x: float | None                          # pixel de l'image (None : carte seulement)
    y: float | None
    precision: str                           # point | approx | carte
    boutique: str | None = None              # code N0xx : article d'une boutique PLACÉE (marqueur de boutique)

    @property
    def placee(self) -> bool:
        return self.x is not None and self.y is not None


@dataclass
class LieuBoutique:
    """Un lieu d'une boutique (format 5) : son vendeur sur une carte, ou une porte qui y mène (`vers` = carte où l'on
    entre : le bâtiment, ou la galerie qui y conduit)."""
    carte: str
    x: float
    y: float
    genre: str                               # vendeur | entree
    vers: str | None = None
    app: list[dict] | None = None            # vendeur (format 6) : variantes d'apparition ; None : inconnues (ancien)


@dataclass
class DonneesCartes:
    boutiques: dict[str, list[LieuBoutique]] = field(default_factory=dict)   # code -> lieux (format 5)
    cartes: dict[str, InfoCarte] = field(default_factory=dict)
    positions: dict[int, Position] = field(default_factory=dict)
    icones: dict[str, Path] = field(default_factory=dict)     # clé d'objet -> PNG couleur (gris : `CA.GRIS`)
    parents: dict[str, str] = field(default_factory=dict)     # carte sans image -> carte à image à montrer (format 3)
    par_hachage: dict[int, str] = field(default_factory=dict)  # CRC-32 du nom -> carte (toutes les cartes connues)


def dossier_cartes(dossier: str | Path) -> Path:
    return Path(dossier) / CA.DOSSIER


def signature(dossier: str | Path):
    try:
        st = (dossier_cartes(dossier) / CA.NOM_FICHIER).stat()
        return st.st_size, st.st_mtime_ns
    except OSError:
        return None


def charger(dossier: str | Path) -> DonneesCartes | None:
    d = CA.charger(dossier)
    if d is None:
        return None
    base = dossier_cartes(dossier)
    out = DonneesCartes()
    for cid, c in d["cartes"].items():
        try:
            w, h = (int(v) for v in c["taille"])
            png = base / str(c["png"])
        except (KeyError, TypeError, ValueError):
            continue
        if png.is_file():
            out.cartes[cid] = InfoCarte(cid, png, w, h, str(c.get("genre") or "autre"), _monde(c.get("monde")))
    for cid, parent in (d.get("parents") or {}).items() if isinstance(d.get("parents"), dict) else ():
        if isinstance(cid, str) and isinstance(parent, str):
            out.parents[cid] = parent
    out.par_hachage = {zlib.crc32(str(c).encode()) & 0xFFFFFFFF: str(c) for c in list(d["cartes"]) + list(out.parents)}
    bout = d.get("boutiques")
    for code, lieux in bout.items() if isinstance(bout, dict) else ():
        gardes = []
        for l in lieux if isinstance(lieux, list) else ():
            try:
                app = l.get("app")
                lb = LieuBoutique(str(l["carte"]), float(l["px"]), float(l["py"]), str(l.get("genre") or "vendeur"),
                                  str(l["vers"]) if l.get("vers") else None,
                                  [a for a in app if isinstance(a, dict)] if isinstance(app, list) else None)
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            if lb.carte in out.cartes and (lb.genre == "vendeur" or (lb.genre == "entree" and lb.vers in out.cartes)):
                gardes.append(lb)
        if any(l.genre == "vendeur" for l in gardes):
            out.boutiques[str(code)] = gardes
    for i, p in d["locations"].items():
        try:
            if p.get("carte") not in out.cartes:
                continue
            x, y = p.get("px"), p.get("py")
            prec = str(p.get("precision") or "carte")
            if prec == "carte" or x is None or y is None:
                out.positions[int(i)] = Position(p["carte"], None, None, "carte")
            else:
                code = p.get("boutique")
                out.positions[int(i)] = Position(p["carte"], float(x), float(y), prec,
                                                 str(code) if code and str(code) in out.boutiques else None)
        except (TypeError, ValueError, AttributeError):
            continue
    for cle, rel in (d.get("icones") or {}).items():
        f = base / str(rel)
        if f.is_file():
            out.icones[str(cle)] = f
    return out


def _monde(v) -> tuple[float, ...] | None:
    try:
        m = tuple(float(x) for x in v)
    except (TypeError, ValueError):
        return None
    return m if len(m) == 6 and m[2] != m[0] and m[3] != m[1] and m[4] > 0 and m[5] > 0 else None


# ------------------------------------------------------------------------------------------------ suivi du jeu
# Le jeu publie la carte où se trouve le joueur (CRC-32 de son nom) et sa position ; le client les recopie dans
# `lieu.json` (client/lieu_local.py). Ici : résolution du nom, carte à montrer, pixel du joueur, et la petite machine
# à états de la case « Suivre le jeu » (sans affichage : testée sans tkinter).
@dataclass
class Lieu:
    hachage: int                             # CRC-32 du nom de la carte du jeu (0 : aucune : titre, chargement)
    carte: str | None                        # son nom (None : aucune carte, ou carte inconnue des données locales)
    x: float | None                          # position monde du joueur (None : inconnue)
    z: float | None
    changement: int                          # +1 à chaque changement de carte en jeu (lieu.json)


def signature_lieu(dossier: str | Path):
    try:
        st = (Path(dossier) / LL.NOM_LIEU).stat()
        return st.st_size, st.st_mtime_ns
    except OSError:
        return None


def lire_lieu(dossier: str | Path) -> dict | None:
    return LL.lire(dossier)


def lieu_jeu(brut: dict | None, don: DonneesCartes | None, maintenant: float | None = None) -> Lieu | None:
    """Lieu du joueur d'après `lieu.json` ; None : PAS DE JEU (jeu pas attaché, patch qui ne publie pas le lieu, ou
    fichier trop ancien : client arrêté sans le dire, `LL.AGE_MAX`). Jeu en marche sans carte (titre, chargement) :
    un `Lieu` de hachage 0, sans nom ni position."""
    if not isinstance(brut, dict) or not brut.get("publie"):
        return None
    h = brut.get("carte")
    if not isinstance(h, int) or isinstance(h, bool):
        return None
    t = brut.get("horodatage")
    age = (time.time() if maintenant is None else maintenant) - t if isinstance(t, (int, float)) else None
    if age is None or age > LL.AGE_MAX:
        return None
    x, z = brut.get("x"), brut.get("z")
    if not h or not (isinstance(x, (int, float)) and isinstance(z, (int, float))):
        x = z = None
    c = brut.get("changement")
    return Lieu(h & 0xFFFFFFFF, (don.par_hachage.get(h & 0xFFFFFFFF) if don else None), x, z,
                c if isinstance(c, int) else 0)


def ligne_position(lieu: Lieu | None, nom: str | None = None) -> str | None:
    """Ligne « carte:x,z  # nom de la carte » du lieu du joueur, à coller dans la table des lieux libres
    (`installation/lieux_libres.txt`) ; None sans jeu, sans carte connue ou sans position (rien à copier)."""
    if lieu is None or not lieu.carte or lieu.x is None or lieu.z is None:
        return None
    ligne = "%s:%g,%g" % (lieu.carte, round(lieu.x, 1), round(lieu.z, 1))
    return ligne + ("  # " + nom if nom and nom != lieu.carte else "")


def carte_a_montrer(don: DonneesCartes | None, carte: str | None) -> str | None:
    """Carte À IMAGE à afficher quand le joueur est sur `carte` : elle-même si elle a une image ; sinon sa carte
    parente (table locale `parents`, format 3 : groupe de la carte, sinon extérieur de sa zone). None : aucune (garder
    la carte affichée) ; c'est aussi le cas d'une carte sans image avec des données d'un format antérieur (son nom
    n'y est pas : seul son hachage est connu)."""
    if don is None or not carte:
        return None
    if carte in don.cartes:
        return carte
    parent = don.parents.get(carte)
    if parent and parent in don.cartes:
        return parent
    return None


def pixel_joueur(don: DonneesCartes | None, carte_affichee: str | None, lieu: Lieu | None) -> tuple[float, float] | None:
    """Pixel d'image du joueur sur la carte AFFICHÉE (même transformation que les checks, `CA.monde_vers_pixel`) ;
    None si le joueur est sur une autre carte, si sa position ou le rectangle monde de la carte sont inconnus, ou si
    le point tombe hors de l'image."""
    if don is None or lieu is None or lieu.carte is None or lieu.carte != carte_affichee or lieu.x is None \
            or lieu.z is None:
        return None
    info = don.cartes.get(carte_affichee)
    if info is None or info.monde is None:
        return None
    px, py = CA.monde_vers_pixel(info.monde, lieu.x, lieu.z)
    if not (0 <= px < info.largeur and 0 <= py < info.hauteur):
        return None
    return px, py


class Suivi:
    """Case « Suivre le jeu » : quelle carte afficher d'après le lieu du joueur.

    Cochée (`actif`) : la carte affichée devient celle du jeu à chaque changement de carte en jeu. Si le joueur choisit
    à la main une AUTRE carte (liste, région, check choisi dans la liste), le suivi se met en `pause` jusqu'au
    prochain changement de carte en jeu ; rechoisir la carte du jeu, ou décocher puis recocher, le reprend tout de
    suite. Sans jeu (lieu None) ou carte du jeu sans image ni carte parente : rien ne change.

    « Changement de carte en jeu » = la carte À MONTRER change (`carte_a_montrer`) : un passage par une carte que le
    lanceur ne montre pas (arène d'un combat, intérieur sans image dont la carte parente est déjà affichée, écran de
    chargement) puis le retour sur la même carte n'en est pas un : il ne reprend pas un suivi en pause."""

    def __init__(self, actif: bool = True):
        self.actif = bool(actif)
        self.pause = False
        self.cible_jeu: str | None = None        # carte à montrer d'après le jeu, tant qu'il tourne (dernière connue)

    def cocher(self, actif: bool) -> None:
        self.actif, self.pause = bool(actif), False

    def cible(self, lieu: Lieu | None, don: DonneesCartes | None) -> str | None:
        """Carte à afficher maintenant (None : ne rien changer)."""
        if lieu is None:                         # pas de jeu : rien à suivre, plus de pause
            self.cible_jeu, self.pause = None, False
            return None
        c = carte_a_montrer(don, lieu.carte)
        if c is None:                            # carte du jeu que le lanceur ne montre pas : rien ne change
            return None
        if c != self.cible_jeu:                  # changement de carte en jeu : le suivi reprend
            self.cible_jeu, self.pause = c, False
        if not self.actif or self.pause:
            return None
        return c

    def choix_manuel(self, carte: str | None) -> None:
        """Le joueur a choisi `carte` à la main : pause si ce n'est pas la carte du jeu (sinon le suivi continue)."""
        if self.actif and self.cible_jeu is not None:
            self.pause = carte != self.cible_jeu

    @property
    def en_pause(self) -> bool:
        return self.actif and self.pause


# ------------------------------------------------------------------------------------------------ cartes et marqueurs
def filtre_region(f: CK.Filtre) -> CK.Filtre:
    """Même filtre que la liste, sans la recherche ni les bascules : compteurs d'une région."""
    return CK.Filtre(type=f.type, zone=f.zone)


def cartes_du_check(don: DonneesCartes, p: Position) -> list[str]:
    """Cartes où un check est compté : la sienne ; pour l'article d'une boutique placée, chaque carte qui porte un
    marqueur de son VENDEUR (un étal présent sur plusieurs cartes compte sur chacune : le compteur d'une carte = les
    checks qu'on y voit). Les portes d'un bâtiment sont des repères : elles ne comptent pas."""
    if not p.boutique:
        return [p.carte]
    cartes = [p.carte]
    for l in don.boutiques.get(p.boutique, ()):
        if l.genre == "vendeur" and l.carte not in cartes:
            cartes.append(l.carte)
    return cartes


def cartes_de_zone(m: CK.ModeleChecks, don: DonneesCartes, f: CK.Filtre) -> list[tuple[str, int, int]]:
    """[(carte, checks gardés par le filtre, checks de la région sur cette carte)] : grande carte d'abord, puis donjons
    et intérieurs par nombre de checks. Cartes sans check gardé omises (sauf si la région en a : liste stable)."""
    region = filtre_region(f)
    total: dict[str, int] = {}
    gardes: dict[str, int] = {}
    for c in m.checks:
        p = don.positions.get(c.id)
        if p is None or not region.garde(c, m):
            continue
        garde = f.garde(c, m)
        for k in cartes_du_check(don, p):
            total[k] = total.get(k, 0) + 1
            if garde:
                gardes[k] = gardes.get(k, 0) + 1
    cles = sorted(total, key=lambda k: (ORDRE_GENRES.get(don.cartes[k].genre, 9) if k in don.cartes else 9,
                                        -total[k], k))
    return [(k, gardes.get(k, 0), total[k]) for k in cles]


def etat_marqueur(checks: list[CK.Check]) -> str:
    """fait (tous faits) | accessible (tous les restants) | partiel (une partie des restants) | non (aucun)."""
    return _etat_des([c.etat for c in checks])


def _etat_des(etats: list[str]) -> str:
    restants = [e for e in etats if e != "fait"]
    if not restants:
        return "fait"
    acces = sum(1 for e in restants if e == "accessible")
    if acces == len(restants):
        return "accessible"
    return "partiel" if acces else "non"


@dataclass
class Marqueur:
    x: float                                 # centre, en pixels d'image
    y: float
    checks: list[CK.Check]
    etat: str
    indice: bool                             # un check restant indiqué par un hint
    approx: bool                             # au moins une position supposée (à vérifier en jeu)
    genre: str = "check"                     # check | boutique (vendeur : ses articles) | entree (porte du bâtiment)
    codes: tuple[str, ...] = ()              # boutiques du marqueur (N0xx)
    vers: str | None = None                  # entree : carte où l'on entre
    presences: dict = field(default_factory=dict)    # boutique : code -> `Presence` du vendeur À CE MARQUEUR

    @property
    def present(self) -> bool | None:
        """Vendeur là maintenant : True (ou rien de connu contre), False (aucune de ses boutiques), None (« ? »)."""
        v = [p.present for p in self.presences.values()]
        if not v or any(x is True for x in v):
            return True
        return None if any(x is None for x in v) else False

    @property
    def quand(self) -> str | None:
        """« jour » / « nuit » si le vendeur n'est à ce marqueur qu'à ce moment-là (toutes ses boutiques)."""
        m = 0
        for p in self.presences.values():
            m |= p.moment
        return TK.nom_moment(m) if self.presences else None

    @property
    def ids(self) -> list[int]:
        return [c.id for c in self.checks]

    @property
    def faits(self) -> int:
        return sum(1 for c in self.checks if c.etat == "fait")


def marqueurs(m: CK.ModeleChecks, don: DonneesCartes, f: CK.Filtre, carte: str, echelle: float = 1.0,
              rayon: float = 7.0, progression: TK.Progression | None = None) -> list[Marqueur]:
    """Marqueurs des checks gardés placés sur `carte` ; deux checks à moins de `rayon` pixels AFFICHÉS (échelle
    comprise) sont regroupés (centre = moyenne)."""
    pts = []
    for c in m.checks:
        p = don.positions.get(c.id)
        if p is not None and p.carte == carte and p.placee and not p.boutique and f.garde(c, m):
            pts.append((p.x, p.y, c, p.precision == "approx"))
    pts.sort(key=lambda t: (t[1], t[0], t[2].id))
    groupes: list[list] = []
    lim = (rayon / max(echelle, 1e-6)) ** 2
    for x, y, c, ap in pts:
        for g in groupes:
            if (g[0] - x) ** 2 + (g[1] - y) ** 2 <= lim:
                g[2].append((x, y, c, ap))
                n = len(g[2])
                g[0] += (x - g[0]) / n
                g[1] += (y - g[1]) / n
                break
        else:
            groupes.append([x, y, [(x, y, c, ap)]])
    out = []
    for gx, gy, membres in groupes:
        cs = [t[2] for t in membres]
        out.append(Marqueur(gx, gy, cs, etat_marqueur(cs), any(c.indice and c.etat != "fait" for c in cs),
                            any(t[3] for t in membres)))
    return out + marqueurs_boutiques(m, don, f, carte, echelle, rayon, progression)


SEPARATEUR_ARTICLE = " — "                 # « Boutique : <région> (N0xx) — article i » (noms de l'APWorld)


def nom_boutique(checks: list[CK.Check]) -> str:
    """Nom de la boutique d'après le nom de ses articles (partie avant « — article i »)."""
    return checks[0].nom.rsplit(SEPARATEUR_ARTICLE, 1)[0] if checks else ""


def nom_article(c: CK.Check) -> str:
    """« article i » (partie propre à l'article du nom du check) ; nom entier s'il n'a pas cette forme."""
    return c.nom.rsplit(SEPARATEUR_ARTICLE, 1)[-1]


def boutiques_du_marqueur(mq: "Marqueur", don: DonneesCartes) -> list[tuple[str, list[CK.Check]]]:
    """[(code, articles du marqueur de cette boutique)] dans l'ordre des codes du marqueur."""
    out = []
    for code in mq.codes:
        cs = [c for c in mq.checks if (don.positions.get(c.id) and don.positions[c.id].boutique == code)]
        if cs:
            out.append((code, cs))
    return out


def articles_boutiques(m: CK.ModeleChecks, don: DonneesCartes, f: CK.Filtre | None = None) -> dict[str, list[CK.Check]]:
    """Code de boutique placée -> ses articles-checks de la graine (gardés par `f` s'il est donné), dans l'ordre des
    articles. Seuls les checks du modèle : contenu connu seulement si fait ou indiqué (aucun spoiler)."""
    out: dict[str, list[CK.Check]] = {}
    for c in m.checks:
        p = don.positions.get(c.id)
        if p is not None and p.boutique and (f is None or f.garde(c, m)):
            out.setdefault(p.boutique, []).append(c)
    for cs in out.values():
        cs.sort(key=lambda c: c.id)
    return out


# Présence d'un vendeur (format 6, archipelago_tracker_cartes.md §12). Champs 1 et 2 d'un `NPC_APPEAR` [C : lecteur
# `FUN_003D3E24`, comparés à `FUN_0040E594(3)` et à `GetWeatherNow`] : négatif = ignoré ; champ 1 : 0 = le jour
# (6-18 h), 3 = la nuit (18-6 h) ; champ 2 : 0 = temps sec, 1 = pluie ou tempête. Une variante est vraie si son moment,
# sa météo, sa condition et (étal ambulant) son tirage le sont ; le vendeur est là si l'une de ses variantes l'est.
# L'heure et la météo du jeu ne sont pas suivies : elles sont SIGNALÉES (petit rond jour / nuit, texte), jamais niées,
# SAUF quand la progression prouve que la nuit n'est pas libre (`etat_nuit`).
MOMENTS_PNJ = {0: TK.JOUR, 3: TK.NUIT}
METEOS_PNJ = {0: "sec", 1: "pluie"}
PHASE_SANS_FIN = 110000                  # borne haute au-delà du chapitre 10 : pas une limite pour le joueur
FONCTIONS_SUIVIES = ("GetPhase", "GetChapter", "GetWatchRank", "GameClear", "GetTimeNow")

# Sortir la nuit (archipelago_tracker_cartes.md §12.8) [C] : l'horloge du jeu n'avance pas tant que le bit global
# `time_lock` (0x2A329223) vaut 1 (`FUN_00411C5C`, seul lecteur natif), et le lit de la chambre (point 0xA9974D68 de
# t101i02 / t101i04) est alors refusé (déclencheur n° 6, `time_lock == 1`, avant ceux du lit). Ce bit est posé et retiré
# par les commandes d'ENTRÉE de phase (`phase_set_cNN`, `PhCmd_N_M` : 0x36B0) : 1 à 1-10, 0 à 3-20, 1 à 3-60, 0 à 3-70,
# 1 à 3-140, 0 à 3-180, puis 4-40..4-270, 5-10..5-30, 7-40..7-70, 10-40..10-150. Avant 3-20, l'heure est donc figée
# (au jour hors scènes) et le lit refusé : aucune sortie de nuit libre. Plus tard, une fenêtre figée laisse l'heure là
# où l'histoire l'a mise (inconnue du lanceur). Des requêtes posent aussi `time_lock` le temps de leurs scènes [S : non
# suivi, cas courts].
PHASE_NUIT_LIBRE = 30020
FENETRES_HEURE_FIGEE = ((10010, 30020), (30060, 30070), (30140, 30180), (40040, 40270), (50010, 50030),
                        (70040, 70070), (100040, 100150))     # [début, fin) en phases (chapitre × 10000 + pas)


def etat_nuit(prog: TK.Progression | None) -> str | None:
    """« libre » (l'horloge tourne, le lit marche) | « fermee » (avant 3-20 : jamais encore de nuit libre) | « figee »
    (heure figée par l'histoire à cette phase : nuit possible ou non) | None (progression inconnue : rien d'affirmé)."""
    if prog is None:
        return None
    if prog.apres_jeu:
        return "libre"
    if prog.phase is None:
        return None
    if prog.phase < PHASE_NUIT_LIBRE:
        return "fermee"
    if any(lo <= prog.phase < hi for lo, hi in FENETRES_HEURE_FIGEE):
        return "figee"
    return "libre"


@dataclass
class Presence:
    """Ce que le lanceur sait de la présence d'un vendeur à un emplacement."""
    present: bool | None = True              # True : là (rien de connu contre) ; False : absent à coup sûr ; None : « ? »
    moment: int = TK.TOUJOURS                # masque des moments où il peut être là (jour / nuit)
    tirage: dict | None = None               # étal ambulant : {"n" emplacements, "cartes", "taux", "bloque"}
    phase: tuple = (None, None)              # bornes de phase d'histoire (chapitre × 10000 + pas), None : sans borne
    apres_jeu: bool | None = None            # True : après la fin seulement ; False : avant seulement
    meteo: str | None = None                 # « sec » / « pluie » : seulement par ce temps-là
    autres: bool = False                     # dépend aussi d'un flag, d'une requête… que le lanceur ne suit pas
    sauf: bool = False                       # là, sauf pendant des passages de l'histoire (« flag != 1 » non suivis)
    variantes: int = 1                       # nombre de variantes d'apparition du vendeur à ce point
    connue: bool = True                      # faux : fichier d'avant le format 6 (rien de connu)
    nuit: str | None = None                  # vendeur de nuit seulement : « fermee » / « figee » (`etat_nuit`)

    @property
    def quand(self) -> str | None:
        return TK.nom_moment(self.moment)


def _fonctions(rpn) -> set[str]:
    return {j[1] for j in rpn or () if isinstance(j, list) and len(j) > 1 and j[0] == "f"}


def _sans_exclusions(rpn: list) -> list | None:
    """Condition où chaque « fonction non suivie != constante » est supposée VRAIE (les vendeurs fixes sont retirés
    pendant de courts passages de l'histoire par des tests « flag != 1 », « phase de requête != n ») ; None s'il n'y
    en a aucune."""
    out, change, i = [], False, 0
    while i < len(rpn):
        a = rpn[i]
        if i + 2 < len(rpn) and isinstance(a, list) and a[:1] == ["f"] and a[1] not in FONCTIONS_SUIVIES \
                and rpn[i + 1][:1] == ["i"] and rpn[i + 2] == ["o", "!="]:
            out += [["i", 1], ["i", 1], ["o", "=="]]
            change = True
            i += 3
        else:
            out.append(a)
            i += 1
    return out if change else None


def _presence_variante(a: dict, prog: TK.Progression | None) -> Presence:
    p = Presence()
    rpn = a.get("e") if isinstance(a.get("e"), list) else []
    r = a.get("r") if isinstance(a.get("r"), dict) else {}
    masque = MOMENTS_PNJ.get(a.get("h"), TK.TOUJOURS)
    if rpn:
        masque &= TK.moment_condition(rpn)[0]
    p.moment = masque
    p.meteo = METEOS_PNJ.get(a.get("m"))
    val = TK.evaluer(rpn, prog)[0] if rpn else True
    if val is None:                          # seules des exclusions « != » inconnues : présent, sauf exception signalée
        souple = _sans_exclusions(rpn)
        if souple is not None and TK.evaluer(souple, prog)[0] is True:
            val, p.sauf = True, True
    ph = r.get("phase")
    if isinstance(ph, list) and len(ph) == 2:
        p.phase = (ph[0], ph[1])
    if isinstance(r.get("apres_jeu"), bool):
        p.apres_jeu = r["apres_jeu"]
    t = a.get("tirage")
    autres = set() if p.sauf else _fonctions(rpn) - set(FONCTIONS_SUIVIES)
    if isinstance(t, dict):
        try:
            n = int(t["max"]) - int(t["min"]) + 1
        except (KeyError, TypeError, ValueError):
            n = 0
        rt = t.get("e") if isinstance(t.get("e"), list) else []
        debloque = TK.evaluer(rt, prog)[0] if rt else True
        # "fige" [C : `FUN_004142B8`, 2e champ du CONFIG] : le tirage réussi verrouille son groupe (même étal au même
        # point jusqu'au prochain saut de temps vers le matin) ; sinon il est refait à chaque arrivée sur une carte
        p.tirage = {"n": n, "taux": t.get("taux"), "bloque": debloque is False, "cartes": t.get("cartes"),
                    "fige": t.get("mode") == 1, "partage": isinstance(t.get("groupe"), int) and t["groupe"] > 1}
        # exclusions « != » (passages de l'histoire) : pas une exigence ; l'octet tiré : dit par le tirage lui-même
        cites = _fonctions(_sans_exclusions(rpn) or rpn) | _fonctions(_sans_exclusions(rt) or rt)
        autres = cites - set(FONCTIONS_SUIVIES) - {CA.OCTET_GLOBAL}
        rr = _phase_minimale(rt)
        if rr is not None and p.phase == (None, None):
            p.phase = rr
        if debloque is False:
            val = False
        elif val is not False:
            val = None                       # jamais affirmé : le tirage du jour n'est pas connu du lanceur
    p.autres = bool(autres)
    if not masque:
        val = False
    elif not masque & TK.JOUR:               # de nuit seulement : la nuit est-elle libre à ce stade de la partie ?
        nuit = etat_nuit(prog)
        if nuit == "fermee":
            val, p.nuit = False, nuit
        elif nuit == "figee" and val is not False:
            val, p.nuit = None, nuit
    p.present = val
    return p


def _phase_minimale(rpn) -> tuple | None:
    """Borne basse de phase d'une condition de la forme « GetPhase >= N et … » (taux d'un étal) ; None sinon."""
    for i in range(len(rpn or ()) - 2):
        a, b, c = rpn[i:i + 3]
        if a[:2] == ["f", "GetPhase"] and b[:1] == ["i"] and c == ["o", ">="]:
            return (b[1], None)
    return None


def presence(lieu: LieuBoutique, prog: TK.Progression | None = None) -> Presence:
    """Présence du vendeur à `lieu` d'après ses variantes d'apparition et la progression de la sauvegarde liée :
    la variante la plus favorable (vraie, sinon inconnue, sinon fausse) ; moments = union des variantes possibles."""
    if lieu.app is None:
        return Presence(connue=False)
    if not lieu.app:
        return Presence()
    vs = [_presence_variante(a, prog) for a in lieu.app]
    rang = {True: 0, None: 1, False: 2}
    meilleur = min(vs, key=lambda v: rang[v.present])
    possibles = [v for v in vs if v.present is not False] or vs
    m = 0
    for v in possibles:
        m |= v.moment
    meilleur.moment = m
    meilleur.variantes = len(vs)
    return meilleur


def presence_combinee(ps: list[Presence]) -> Presence:
    """Présence d'une boutique à plusieurs emplacements (porte d'un bâtiment) : la plus favorable (là, sinon « ? »,
    sinon absent) ; moments = union des emplacements possibles. Aucune : rien de connu."""
    if not ps:
        return Presence(connue=False)
    rang = {True: 0, None: 1, False: 2}
    meilleur = min(ps, key=lambda v: (not v.connue, rang[v.present]))
    if not meilleur.connue:
        return meilleur
    m = 0
    for v in [v for v in ps if v.connue and v.present is not False] or [v for v in ps if v.connue]:
        m |= v.moment
    return replace(meilleur, moment=m)


def presence_porte(don: DonneesCartes, code: str, vers: str | None, prog: TK.Progression | None = None) -> Presence:
    """Présence du vendeur de `code` derrière une porte qui mène à `vers` : ses emplacements sur cette carte ; aucun
    (la porte mène à une galerie qui conduit au bâtiment) : tous ses emplacements."""
    lieux = [l for l in don.boutiques.get(code, ()) if l.genre == "vendeur"]
    ici = [l for l in lieux if l.carte == vers]
    return presence_combinee([presence(l, prog) for l in (ici or lieux)])


def vendeur_absent(pr: Presence | None) -> bool:
    """Vrai si le vendeur est absent À COUP SÛR (condition connue fausse) à ce stade de la partie."""
    return pr is not None and pr.connue and pr.present is False


def report_article(mq: "Marqueur", code: str, c: CK.Check) -> str | None:
    """Clé de texte de l'état à montrer à la place de « Accessible » pour un article dont le vendeur est absent à coup
    sûr (« plus tard » : la logique de l'APWorld dit accessible, le jeu ne le vend pas maintenant) ; None sinon."""
    pr = mq.presences.get(code)
    if c.etat != "accessible" or not vendeur_absent(pr):
        return None
    return "cc_bt_art_nuit" if pr.nuit == "fermee" else "cc_bt_art_absent"


def etat_presences(mq_codes: tuple, articles: dict, presences: dict) -> str:
    """État (couleur) d'un groupe de boutiques où un article accessible pour la logique mais dont le vendeur est absent
    à coup sûr compte comme non accessible maintenant."""
    etats = []
    for code in mq_codes:
        absent = vendeur_absent(presences.get(code))
        etats += [("non" if absent and c.etat == "accessible" else c.etat) for c in articles.get(code, ())]
    return _etat_des(etats)


def signature_progression(dossier: str | Path):
    try:
        st = (Path(dossier) / TK.NOM_PROGRESSION).stat()
        return st.st_size, st.st_mtime_ns
    except OSError:
        return None


def lire_progression(dossier: str | Path) -> TK.Progression | None:
    """Progression de la sauvegarde liée (`progression.json` du client) ; None : inconnue."""
    import json
    try:
        d = json.loads((Path(dossier) / TK.NOM_PROGRESSION).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return TK.lire_progression(d if isinstance(d, dict) else None, None)


def phase_lisible(phase: int) -> str:
    """« 10-1 » pour 100010 (chapitre × 10000 + pas) : la notation des phases du jeu."""
    return "%d-%d" % (phase // 10000, phase % 10000)


def lignes_presence(pr: Presence) -> list[tuple[str, dict]]:
    """Ce qu'on sait de la présence d'un vendeur, en clés de texte (`textes_checks`) : état, puis ses conditions."""
    if not pr.connue:
        return []
    out: list[tuple[str, dict]] = []
    t = pr.tirage
    if t and t.get("bloque"):
        out.append(("cc_bt_pr_etal_bloque", {}))
    elif pr.present is False:
        out.append(("cc_bt_pr_absent", {}))
    elif pr.present is None:
        out.append(("cc_bt_pr_inconnu", {}))
    if pr.nuit == "fermee":
        out.append(("cc_bt_pr_nuit_fermee", {"a": phase_lisible(PHASE_NUIT_LIBRE)}))
    elif pr.nuit == "figee":
        out.append(("cc_bt_pr_nuit_figee", {}))
    if t:
        out.append(("cc_bt_pr_etal_fige" if t.get("fige") else "cc_bt_pr_etal_libre",
                    {"n": t.get("n") or "?", "c": t.get("cartes") or "?",
                     "taux": t.get("taux") if t.get("taux") is not None else "?"}))
        if t.get("partage"):
            out.append(("cc_bt_pr_etal_partage", {}))
    if pr.quand:
        out.append(("cc_bt_pr_" + pr.quand, {}))
    if pr.meteo:
        out.append(("cc_bt_pr_" + pr.meteo, {}))
    lo, hi = pr.phase
    if pr.present is True:                   # là maintenant : seule une FIN proche vaut d'être dite (vendeur à durée
        lo = None                            # limitée) ; plusieurs variantes : les bornes de l'une ne disent rien
        if pr.variantes > 1 or (hi is not None and hi >= PHASE_SANS_FIN):
            hi = None
    if t and not t.get("bloque"):            # étal en service : la phase de mise en service est passée
        lo = None
    if pr.present is False and pr.variantes > 1 and not (t and t.get("bloque")) and not pr.nuit:
        lo = hi = None                       # absent entre deux de ses périodes (ex. pendant le chapitre 10)
        out.append(("cc_bt_pr_retour", {}))
    if lo is not None and hi is not None:
        out.append(("cc_bt_pr_phase_entre", {"a": phase_lisible(lo), "b": phase_lisible(hi)}))
    elif lo is not None:
        out.append(("cc_bt_pr_phase_min", {"a": phase_lisible(lo), "n": lo // 10000}))
    elif hi is not None:
        out.append(("cc_bt_pr_phase_max", {"b": phase_lisible(hi)}))
    if pr.apres_jeu is not None:
        out.append(("cc_bt_pr_apres_jeu" if pr.apres_jeu else "cc_bt_pr_avant_fin", {}))
    if pr.autres:
        out.append(("cc_bt_pr_autres", {}))
    if pr.sauf:
        out.append(("cc_bt_pr_sauf", {}))
    return out


def marqueurs_boutiques(m: CK.ModeleChecks, don: DonneesCartes, f: CK.Filtre, carte: str, echelle: float = 1.0,
                        rayon: float = 7.0, progression: TK.Progression | None = None) -> list[Marqueur]:
    """Marqueurs de boutique de `carte` : un par vendeur (genre « boutique » : les articles gardés de la boutique ;
    deux vendeurs à moins de `rayon` pixels affichés partagent un marqueur), puis un par porte de bâtiment (genre
    « entree » : articles des boutiques où elle mène ; portes proches vers la même carte regroupées). Une boutique sans
    article gardé par le filtre n'a pas de marqueur ; l'état (couleur) suit celui de ses articles."""
    if not don.boutiques:
        return []
    articles = articles_boutiques(m, don, f)
    lim = (rayon / max(echelle, 1e-6)) ** 2
    groupes: list[list] = []                 # [x, y, genre, vers, [codes], n, {code: présence du vendeur}]
    for code in sorted(don.boutiques):
        if not articles.get(code):
            continue
        for l in don.boutiques[code]:
            if l.carte != carte:
                continue
            genre = "boutique" if l.genre == "vendeur" else "entree"
            for g in groupes:
                if g[2] == genre and g[3] == l.vers and (g[0] - l.x) ** 2 + (g[1] - l.y) ** 2 <= lim:
                    if code not in g[4]:
                        g[4].append(code)
                    if code not in g[6]:
                        g[6][code] = presence(l, progression) if genre == "boutique" \
                            else presence_porte(don, code, l.vers, progression)
                    g[5] += 1
                    g[0] += (l.x - g[0]) / g[5]
                    g[1] += (l.y - g[1]) / g[5]
                    break
            else:
                groupes.append([l.x, l.y, genre, l.vers, [code], 1,
                                {code: presence(l, progression) if genre == "boutique"
                                 else presence_porte(don, code, l.vers, progression)}])
    groupes.sort(key=lambda g: (g[2] != "entree", g[1], g[0]))      # portes d'abord : les vendeurs sont dessinés dessus
    out = []
    for x, y, genre, vers, codes, _n, pres in groupes:
        cs = [c for code in codes for c in articles[code]]
        # porte : présence des vendeurs des boutiques qu'elle dessert (sur la carte où elle mène) ; sa couleur ne dit
        # pas « accessible » pour une boutique au vendeur absent à coup sûr (le vendeur, lui, est dessiné en gris)
        etat = etat_presences(tuple(codes), articles, pres) if genre == "entree" else etat_marqueur(cs)
        out.append(Marqueur(x, y, cs, etat, any(c.indice and c.etat != "fait" for c in cs), False,
                            genre, tuple(codes), vers, pres))
    return out


def sans_position(m: CK.ModeleChecks, don: DonneesCartes, f: CK.Filtre,
                  carte: str | None) -> tuple[list[CK.Check], list[CK.Check]]:
    """(checks gardés sur `carte` sans position précise, checks gardés sans aucune carte) ; les chapitres (sans lieu
    par nature) sont dans l'encart d'objectif, pas ici."""
    sur_carte, sans = [], []
    for c in m.checks:
        if not f.garde(c, m) or c.type == "chapitre":
            continue
        p = don.positions.get(c.id)
        if p is None:
            sans.append(c)
        elif p.carte == carte and not p.placee:
            sur_carte.append(c)
    ordre = {e: i for i, e in enumerate(("accessible", "plus_tard", "bloque", "inconnu", "fait"))}
    cle = (lambda c: (ordre.get(c.etat, 9), c.nom))
    return sorted(sur_carte, key=cle), sorted(sans, key=cle)


def compteurs(m: CK.ModeleChecks, f: CK.Filtre) -> dict[str, int]:
    """Faits / accessibles / restants des checks de la région (et du type) choisis."""
    region = filtre_region(f)
    cs = [c for c in m.checks if region.garde(c, m)]
    faits = sum(1 for c in cs if c.etat == "fait")
    return {"faits": faits, "accessibles": sum(1 for c in cs if c.etat == "accessible"),
            "restants": len(cs) - faits, "total": len(cs)}


def chapitres(m: CK.ModeleChecks) -> tuple[int, list[CK.Check]]:
    """(chapitres terminés, checks « chapitre N terminé » dans l'ordre)."""
    cs = sorted((c for c in m.checks if c.type == "chapitre"), key=lambda c: c.id)
    n = m.chapitres_reels if m.chapitres_reels is not None else sum(1 for c in cs if c.etat == "fait")
    return max(0, min(CHAPITRES_OBJECTIF, int(n))), cs


MEDAILLIUM_LIGNES_MAX = 14                # lignes de la bulle « ce qui manque sans check » de l'encart d'objectif


def texte_medaillium(md: dict, tr) -> str:
    """V3, lot 18 : bulle de l'encart d'objectif « compléter le Médaillium » : compte, entrées que la logique ne
    garantit pas, et entrées MANQUANTES sans check dans la graine (n°, voie, note de l'APWorld)."""
    lignes = [tr("cc_medaillium_bulle").format(acquis="?" if md["acquis"] is None else md["acquis"],
                                              seuil=md["seuil"], total=md["total"])]
    if md["comptes"] < md["seuil"]:
        lignes.append(tr("cc_medaillium_non_garanti").format(n=md["comptes"]))
    # d'abord ce que la logique ne garantit pas (sans voie, en attente, fragile), puis le reste, par n°
    ordre = {"sans_voie": 0, "attente": 1, "fragile": 2}
    manque = sorted(md["sans_check"], key=lambda x: (ordre.get(x[2], 3), x[0]))
    if manque:
        lignes.append(tr("cc_medaillium_sans_check").format(n=len(manque)))
        for n, classe, etat, note in manque[:MEDAILLIUM_LIGNES_MAX]:
            lignes.append("n° %d : %s%s" % (n, note or classe, "" if etat in ("garantie", "hasard") else " [%s]" % etat))
        if len(manque) > MEDAILLIUM_LIGNES_MAX:
            lignes.append("… (+%d)" % (len(manque) - MEDAILLIUM_LIGNES_MAX))
    return "\n".join(lignes)


# ------------------------------------------------------------------------------------------------ Yo-kai épinglé
# Un Yo-kai épinglé dans l'onglet « Yo-kai » (un seul à la fois) : ses points d'apparition EXACTS sur les cartes, sous
# le mélange de la graine (lieux du tracker, `tracker.Lieu.points` : positions monde de la base locale au format 12,
# `archipelago_rando_yokai.md` §18), placés par la même transformation que les checks et le joueur.
@dataclass
class PointYokai:
    x: float                                 # pixels de l'image de la carte
    y: float
    methode: str                             # loupe | errant
    lieux: list[tuple[TK.Lieu, str | None]]  # lieux du Yo-kai qui passent par ce point, nature du décor de loupe
    acces: bool | None                       # False : aucun de ses lieux n'est accessible maintenant ; None : inconnu
    moments: list[int] = field(default_factory=list)    # masque de moments de chaque élément de `lieux`, À CE POINT

    @property
    def moment(self) -> int:
        """Moments où ce point donne le Yo-kai (union de ses lieux ; `tracker.JOUR_SEC`…)."""
        m = 0
        for x in self.moments:
            m |= x
        return m

    @property
    def quand(self) -> str | None:
        """« jour » / « nuit » si le point ne donne le Yo-kai qu'à ce moment-là (petit rond sur le marqueur)."""
        return TK.nom_moment(self.moment)


@dataclass
class Epingle:
    yokai: TK.Yokai
    cartes: dict[str, list[PointYokai]] = field(default_factory=dict)   # carte à image -> points à dessiner
    portails: list[TK.Lieu] = field(default_factory=list)    # salles de portail mystère : listées, jamais dessinées
    sans_position: list[TK.Lieu] = field(default_factory=list)   # position inconnue (base ancienne, chemin sans
    #                                                              position, point hors de l'image)
    sans_image: list[TK.Lieu] = field(default_factory=list)  # carte sans image dans les données locales
    absents: list[TK.Lieu] = field(default_factory=list)     # jamais donnés dans cette version du jeu (base 13, §19)

    @property
    def nombre(self) -> int:
        return sum(len(v) for v in self.cartes.values())


def epingle(y: TK.Yokai | None, don: DonneesCartes | None) -> Epingle | None:
    """Points du Yo-kai épinglé par carte. Deux lieux au même point (conditions différentes) partagent un marqueur ;
    un point qui tombe hors de l'image (points de réserve du jeu, rangés loin de la carte) est ignoré, comme un
    point où ce lieu ne donne jamais le Yo-kai (moments du point et de la condition incompatibles)."""
    if y is None:
        return None
    ep = Epingle(y)
    par_point: dict[tuple, PointYokai] = {}
    for l in y.lieux:
        if l.jamais:
            ep.absents.append(l)
            continue
        if l.portail:
            ep.portails.append(l)
            continue
        info = don.cartes.get(l.carte) if don is not None else None
        if info is None or info.monde is None:
            (ep.sans_image if l.points else ep.sans_position).append(l)
            continue
        place = False
        for x, z, typ in l.points:
            moment = l.moment_point((x, z, typ))
            if not moment:
                continue
            px, py = CA.monde_vers_pixel(info.monde, x, z)
            if not (0 <= px < info.largeur and 0 <= py < info.hauteur):
                continue
            place = True
            cle = (l.carte, l.methode, round(px, 1), round(py, 1))
            p = par_point.get(cle)
            if p is None:
                p = par_point[cle] = PointYokai(px, py, l.methode, [], False)
                ep.cartes.setdefault(l.carte, []).append(p)
            p.lieux.append((l, TK.DECORS_LOUPE.get(typ) if typ is not None else None))
            p.moments.append(moment)
            if l.acces is not False and p.acces is not True:      # un lieu accessible suffit ; sinon inconnu
                p.acces = True if l.acces else None
        if not place:
            ep.sans_position.append(l)
    for pts in ep.cartes.values():
        pts.sort(key=lambda p: (p.y, p.x, p.methode))
    return ep


def cartes_epingle(ep: Epingle | None, don: DonneesCartes | None) -> list[str]:
    """Cartes qui portent un point du Yo-kai épinglé : extérieurs d'abord, puis par nombre de points."""
    if ep is None or don is None:
        return []
    return sorted(ep.cartes, key=lambda k: (ORDRE_GENRES.get(don.cartes[k].genre, 9) if k in don.cartes else 9,
                                            -len(ep.cartes[k]), k))


# ------------------------------------------------------------------------------------------------ objets
@dataclass
class Objet:
    cle: str
    nom: str
    recus: int
    icone: Path | None
    abreviation: str
    badge: str = ""                          # compteur affiché (exemplaires, lettre de rang)
    bulle: str = ""                          # infobulle complète (vide : « nom — reçu (×n) » / « pas encore reçu »)


def abreviation(nom: str) -> str:
    """Initiales des mots significatifs (« Clé de derrière » -> « CD », « Vélo » -> « V »), 3 lettres au plus ; un
    nom qui porte un numéro le garde (« Clé appartement C-101 » -> « C101 »)."""
    for w in nom.split():
        if any(c.isdigit() for c in w):
            return "".join(c for c in w if c.isalnum())[:4].upper()
    mots = [w for w in "".join(c if c.isalnum() else " " for c in nom).split() if w.casefold() not in MOTS_VIDES]
    ini = "".join(w[0] for w in mots)[:3].upper()
    return ini or nom[:2].upper()


def objets_progression(m: CK.ModeleChecks, don: DonneesCartes | None, logique=None) -> list[Objet]:
    """Objets de progression de l'APWorld (objets-clés, rang de montre, capacités), dans l'ordre de l'APWorld :
    progression d'abord, puis utiles ; exemplaires reçus d'après `checks.json`."""
    L = logique or CK.ck.logique_apworld()
    if L is None:
        return []
    try:
        objets = L.donnees().objets
    except Exception:                                  # noqa: BLE001 - logique d'une autre version
        return []
    # V3 : les objets à verrou étendu (Yo-kai Watch…) seulement s'ils sont dans la graine (`objets_v3`)
    v3 = set(getattr(m, "objets_v3", ()) or ())
    choisis = [o for o in objets if o.get("famille") in CA.FAMILLES_ICONES
               or (o.get("famille") in (CA.FAMILLE_CLE_V3, CA.FAMILLE_CLE_AJ, CK.FAMILLE_TERRAINS)
                   and o.get("cle") in v3)]
    choisis.sort(key=lambda o: (0 if o.get("classification") == "progression" else 1))
    out = []
    for o in choisis:
        nom = o["nom_en"] if m.langue == "en" else o["nom_fr"]
        n = int(m.objets_recus.get(o["cle"], 0))
        badge = ""
        if o.get("famille") == "rang":
            badge = RANGS_MONTRE[min(n, len(RANGS_MONTRE) - 1)]
        elif n > 1:
            badge = f"×{n}"
        out.append(Objet(o["cle"], nom, n, (don.icones.get(o["cle"]) if don else None), abreviation(nom), badge))
    return _cases_progressives(out, m, don)


def _cases_progressives(out: list[Objet], m: CK.ModeleChecks, don: DonneesCartes | None) -> list[Objet]:
    """Affichage seulement (ap/lanceur-trousseau), comme le Rang de montre : une case dont l'image suit le nombre reçu.
    - Les 5 « Clé du donjon des portails » (une par porte, dans n'importe quel ordre) -> UNE case « Trousseau du
      donjon (n/5) » à la place de la première, image du trousseau à n clés (grise à 0), infobulle = portes ouvertes.
    - « Miroirs progressifs » (2 exemplaires, option mirapo_de_poche) : image et nom « Miroirs » (grise à 0, puis 1),
      puis « Mirapo de poche » au 2e. Sans l'option, la graine a l'objet « Miroirs » (case inchangée)."""
    def tr(cle, **p):
        return TX.t(m.langue, cle, **p)
    cles = CA.OV.CLES_AP_DONJON
    res: list[Objet] = []
    for o in out:
        if o.cle in cles:
            if any(x.cle == CA.CLE_CASE_TROUSSEAU for x in res):
                continue
            recues = {x.cle for x in out if x.cle in cles and x.recus > 0}
            n, total = len(recues), len(cles)
            portes = [CA.OV.PORTES_GLOBES[i] for i, k in enumerate(cles) if k in recues]
            nom = tr("cc_trousseau", n=n, total=total)
            if portes:
                liste = ", ".join(map(str, portes[:-1])) + (" %s " % tr("cc_trousseau_et") if n > 1 else "") \
                    + str(portes[-1])
                detail = tr("cc_trousseau_portes" if n > 1 else "cc_trousseau_porte", portes=liste)
            else:
                detail = tr("cc_pas_recu")
            icone = don.icones.get(CA.cle_icone_trousseau(n)) if don else None
            res.append(Objet(CA.CLE_CASE_TROUSSEAU, nom, n, icone, abreviation(nom), f"{n}/{total}",
                             f"{nom} — {detail}"))
        elif o.cle == CA.OV.CLE_AP_MIRAPO:
            total = 2
            if o.recus >= total:
                nom = CA.OV.MIRAPO[2] if m.langue == "en" else CA.OV.MIRAPO[1]
                icone = don.icones.get(o.cle) if don else None            # dessin du Mirapo de poche
            else:
                nom = tr("cc_miroirs")
                icone = don.icones.get("miroirs") if don else None        # dessin des Miroirs (gris à 0)
            detail = tr("cc_recu", n=o.recus) if o.recus else tr("cc_pas_recu")
            res.append(replace(o, nom=nom, icone=icone, abreviation=abreviation(nom),
                               badge=f"{min(o.recus, total)}/{total}", bulle=f"{nom} — {detail}"))
        elif o.cle.startswith(CK.FAMILLE_TERRAINS + "_"):
            # ap/blasters-terrains-apworld : les 12 « Terrain : <boss> » -> UNE case « Terrains de Ψ Blasters (n/12) »
            # à la place du premier, sans icône (case dessinée), infobulle = terrains reçus
            if any(x.cle == CK.FAMILLE_TERRAINS for x in res):
                continue
            tous = [x for x in out if x.cle.startswith(CK.FAMILLE_TERRAINS + "_")]
            recus = [x.nom.split(":", 1)[-1].strip() for x in tous if x.recus > 0]
            nom = "Psychic Blasters stages" if m.langue == "en" else "Terrains de Ψ Blasters"
            detail = ", ".join(recus) if recus else tr("cc_pas_recu")
            res.append(Objet(CK.FAMILLE_TERRAINS, nom, len(recus), None, "ΨB", f"{len(recus)}/{len(tous)}",
                             f"{nom} — {detail}"))
        else:
            res.append(o)
    return res


def objets_evenement(m: CK.ModeleChecks, don: DonneesCartes | None, logique=None) -> list[Objet]:
    """Objets des Yo-kai d'évènement de la graine (`ModeleChecks.objets_evenement`, vide : option inactive, section
    cachée), dans l'ordre de l'APWorld ; exemplaires reçus d'après `checks.json` (seulement reçu / pas reçu : aucun
    lieu ni contenu)."""
    if not m.objets_evenement:
        return []
    L = logique or CK.ck.logique_apworld()
    if L is None:
        return []
    try:
        par_cle = {o["cle"]: o for o in L.donnees().objets}
    except Exception:                                  # noqa: BLE001 - logique d'une autre version
        return []
    out = []
    for cle in m.objets_evenement:
        o = par_cle.get(cle)
        if o is None:
            continue
        nom = o["nom_en"] if m.langue == "en" else o["nom_fr"]
        n = int(m.objets_recus.get(cle, 0))
        out.append(Objet(cle, nom, n, (don.icones.get(cle) if don else None), abreviation(nom),
                         f"×{n}" if n > 1 else ""))
    return out


def icone_chapitres(don: DonneesCartes | None) -> Path | None:
    """Icône de la case des chapitres (image du jeu extraite chez le joueur), None : case dessinée."""
    return don.icones.get(CA.CLE_CHAPITRES) if don else None


def replier(texte: str) -> str:
    d = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in d if not unicodedata.combining(c)).casefold()


_LIGATURES = str.maketrans({"œ": "oe", "æ": "ae", "’": "'", "‘": "'"})


def replier_recherche(texte: str) -> str:
    """Forme de comparaison d'une recherche tapée : sans casse ni accents (`replier`), ligatures écrites en deux
    lettres (« coeur » trouve « Cœur »), apostrophe typographique = apostrophe droite, espaces de bord retirés."""
    return replier(texte).translate(_LIGATURES).strip()


def filtrer_noms(noms: list[str], texte: str) -> list[int]:
    """Rangs (ordre gardé) des `noms` qui CONTIENNENT `texte`, sans tenir compte des majuscules ni des accents ;
    texte vide (ou blanc) : tous. Liste des cartes du sous-onglet « Carte » (on écrit pour chercher une carte)."""
    t = replier_recherche(texte)
    if not t:
        return list(range(len(noms)))
    return [i for i, n in enumerate(noms) if t in replier_recherche(n)]


# ------------------------------------------------------------------------------------------------ génération
class Generation:
    """Génération des cartes en tâche de fond (un seul fil à la fois) ; lue par la vue (`after`)."""

    def __init__(self, travail: Callable[..., object] | None = None):
        self.travail = travail
        self.fil: threading.Thread | None = None
        self.arret = threading.Event()
        self.fraction = 0.0
        self.etape = ""
        self.erreur: str | None = None
        self.termine = False                     # la dernière génération a abouti
        self.numero = 0                          # +1 à chaque fin (la vue recharge)

    @property
    def en_cours(self) -> bool:
        return self.fil is not None and self.fil.is_alive()

    def lancer(self) -> bool:
        if self.travail is None or self.en_cours:
            return False
        self.arret.clear()
        self.fraction, self.etape, self.erreur, self.termine = 0.0, "lecture", None, False

        def progression(f, etape):
            self.fraction, self.etape = float(f), str(etape)

        def corps():
            try:
                self.travail(progression=progression, arret=self.arret)
                self.termine = True
            except CA.Interrompu:
                self.erreur = None
            except Exception as e:                   # noqa: BLE001 - montré dans le sous-onglet
                self.erreur = str(e) or repr(e)
            finally:
                self.numero += 1
        self.fil = threading.Thread(target=corps, daemon=True)
        self.fil.start()
        return True

    def arreter(self) -> None:
        self.arret.set()


def moment_carte(points: list[PointYokai]) -> str | None:
    """« jour » / « nuit » si TOUS les points de l'épinglé sur une carte ne le donnent qu'à ce moment-là."""
    m = 0
    for p in points:
        m |= p.moment
    return TK.nom_moment(m)
