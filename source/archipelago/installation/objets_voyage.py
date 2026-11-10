"""Objets du jeu des trois objets Archipelago de voyage de la V3, du Mirapo de poche et du Trousseau du donjon
(§16.11 : `MIRAPO`, `trousseaux()`, plus bas) (bibliothèque standard seulement).

« Abonnement de train » (verrou `train`, k = 59), « Voyage dans le temps » (`voyage_dans_le_temps`, k = 60) et
« Miroirs » (`miroirs`, k = 53) sont des objets Archipelago SANS objet du jeu (don « aucun » dans `objets.json`) :
la mécanique est portée par le verrou (`recu` de la zone d'échange), jamais par l'inventaire. Ce module en fait
AUSSI de vrais objets importants du jeu, visibles dans l'onglet « Objets clés » (demande de l'humain du 2026-10-19,
`docs/systemes/archipelago_invites.md` §16.10) :

- définitions, index et textes : ajoutés par le module des invitations (`invitations.py`, même patch « tout ou rien »,
  même capacité du sous-inventaire), APRÈS les 33 invitations (rangs et hachages des invitations inchangés) ;
- hachages à nous, figés (une sauvegarde les contient) : objet `crc32("ap_" + clé)`, nom `crc32("ap_" + clé +
  "_nom")`, description `crc32("ap_" + clé + "_description")` (clés de `objets.json`) ;
- icônes (aucune image du jeu) : images dessinées par l'humain (`ressources/objet_*.png`, réduites par `reduire` ;
  toutes depuis ap/icones-voyage-miroirs ; les primitives de dessin ci-dessous ne servent plus) : 32×32 dans
  l'atlas (cases sans objet 111, 112, 152, réaffectées à 16 tuiles libres chacune : `icone.modifier_atlas`), 64×64
  pour les écrans « en grand » (`item_112`, `item_113`, `item_153`, ajoutées à `yw2_a.fa`), et les mêmes dessins pour la colonne d'objets du lanceur
  (`cartes.ICONES_DESSINEES`) ;
- don : par le JEU, pas par la file de dons (`src/archipelago/verrous.cpp`, `apObjetsVoyageImage`) : une fois par
  passage sur le terrain et à chaque réception, objet reçu (verrou en vigueur, sauvegarde liée), défini (RomFS patché)
  et absent de l'inventaire -> GiveItem. Un objet reçu AVANT la mise à jour est donc donné aussi, et un jeu sans le
  patch RomFS ne donne rien (définition absente).

    python archipelago/installation/objets_voyage.py --apercu <dossier hors git>
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

try:
    from . import level5 as L
except ImportError:                     # lancé comme script
    import level5 as L  # type: ignore[no-redef]

Pixel = tuple[int, int, int, int]

# Contour sombre commun (style des icônes d'objets du jeu : trait foncé épais, aplats, un reflet)
CONTOUR = (44, 30, 40)
EPAISSEUR = 0.058                       # fraction du côté (≈ 1,9 px à 32×32)


# ------------------------------------------------------------------------------------------------ primitives
# Chaque forme est une fonction (x, y) -> distance signée approchée (négative à l'intérieur), coordonnées en
# fractions du côté (0..1, y vers le bas).
def disque(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def ellipse(cx, cy, rx, ry):
    def f(x, y):
        k = math.hypot((x - cx) / rx, (y - cy) / ry)
        return (k - 1.0) * min(rx, ry)
    return f


def boite(cx, cy, dx, dy, r=0.0):
    """Rectangle de demi-côtés (dx, dy), coins arrondis de rayon r."""
    def f(x, y):
        qx, qy = abs(x - cx) - dx + r, abs(y - cy) - dy + r
        return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r
    return f


def segment(ax, ay, bx, by, r):
    def f(x, y):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - ax - t * dx, y - ay - t * dy) - r
    return f


def anneau(cx, cy, r, demi, a0, a1):
    """Arc de cercle épais (rayon r, demi-épaisseur demi) de l'angle a0 à a1 (degrés, sens horaire, 0 = droite)."""
    def f(x, y):
        a = math.degrees(math.atan2(y - cy, x - cx)) % 360.0
        lo, hi = a0 % 360.0, (a1 - a0) % 360.0
        if (a - lo) % 360.0 <= hi:
            return abs(math.hypot(x - cx, y - cy) - r) - demi
        d = []
        for ang in (a0, a1):
            px, py = cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))
            d.append(math.hypot(x - px, y - py) - demi)
        return min(d)
    return f


def polygone(points):
    def f(x, y):
        dedans = False
        dmin = 1e9
        n = len(points)
        for i in range(n):
            ax, ay = points[i]
            bx, by = points[(i + 1) % n]
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                dedans = not dedans
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            dmin = min(dmin, math.hypot(x - ax - t * dx, y - ay - t * dy))
        return -dmin if dedans else dmin
    return f


def union(*formes):
    return lambda x, y: min(g(x, y) for g in formes)


def inter(a, b):
    return lambda x, y: max(a(x, y), b(x, y))


def rendre(couches, cote: int, sur: int = 4) -> list[Pixel]:
    """Couches [(forme, couleur)] peintes dans l'ordre (la dernière qui couvre un échantillon gagne), suréchantillonnage
    `sur` × `sur` ; pixels RGBA `cote` × `cote`."""
    n = cote * sur
    out = []
    for y in range(cote):
        for x in range(cote):
            r = g = b = a = 0
            for sy in range(sur):
                for sx in range(sur):
                    px, py = (x * sur + sx + 0.5) / n, (y * sur + sy + 0.5) / n
                    c = None
                    for forme, couleur in couches:
                        if forme(px, py) <= 0.0:
                            c = couleur
                    if c is not None:
                        r, g, b, a = r + c[0], g + c[1], b + c[2], a + 1
            out.append((r // a, g // a, b // a, 255 * a // (sur * sur)) if a else (0, 0, 0, 0))
    return out


def contour(forme, e=EPAISSEUR):
    """La forme grossie de l'épaisseur du contour (à peindre en CONTOUR avant la forme elle-même)."""
    return lambda x, y: forme(x, y) - e


def cerne(forme, couleur, e=EPAISSEUR):
    return [(contour(forme, e), CONTOUR), (forme, couleur)]


# ------------------------------------------------------------------------------------------------ images de l'humain
# ap/icones-images (2026-10-28) : l'Abonnement de train et les 5 trousseaux ne sont plus dessinés en code mais
# repris des images dessinées par l'humain (PNG RGBA 100×100, fond transparent, aucune donnée du jeu), dans
# `installation/ressources/` (copiées dans le paquet et l'exe comme les autres ressources). Lues en Python pur
# (`level5.lire_png`, pas de Pillow chez le joueur) et réduites à la taille voulue (32 atlas / lanceur, 64 grande image).
RESSOURCES = Path(__file__).resolve().parent / "ressources"
IMAGE_TRAIN = "objet_abonnement_train.png"
IMAGES_TROUSSEAU = {n: "objet_trousseau_%d.png" % n for n in range(1, 6)}
# ap/icones-voyage-miroirs (2026-11-04) : Voyage dans le temps (montre de poche, 120×120), Miroirs (miroir sombre
# fissuré, 64×64) et Mirapo de poche (miroir rond à ruban violet, 64×64, converti une fois du WebP de l'humain en PNG
# RGBA) : mêmes règles ; à 64 les deux miroirs sont repris tels quels.
IMAGE_TEMPS = "objet_voyage_temps.png"
IMAGE_MIROIRS = "objet_miroirs.png"
IMAGE_MIRAPO = "objet_mirapo_poche.png"
_IMAGES: dict = {}
RAIDEUR_ALPHA = 1.5


def reduire(w: int, h: int, pix, cote: int) -> list[Pixel]:
    """Image w × h RGBA réduite à cote × cote par moyenne de zone EXACTE (poids fractionnaires des pixels source
    coupés par les bords de la zone), alpha prémultiplié (pas de halo sombre au bord des formes)."""
    def poids(n_src: int, n_dst: int):
        # pour chaque pixel cible : [(pixel source, part de recouvrement)]
        e = n_src / n_dst
        out = []
        for i in range(n_dst):
            a, b = i * e, (i + 1) * e
            k, lst = int(a), []
            while k < b and k < n_src:
                part = min(b, k + 1) - max(a, k)
                if part > 1e-9:
                    lst.append((k, part))
                k += 1
            out.append(lst)
        return out
    px, py = poids(w, cote), poids(h, cote)
    res = []
    for ly in py:
        for lx in px:
            r = g = b = a = tot = 0.0
            for sy, wy in ly:
                ligne = sy * w
                for sx, wx in lx:
                    pr, pg, pb, pa = pix[ligne + sx]
                    k = wx * wy
                    tot += k
                    if pa:
                        m = k * pa
                        r, g, b, a = r + pr * m, g + pg * m, b + pb * m, a + m
            if a <= 0.0:
                res.append((0, 0, 0, 0))
                continue
            # bord net : la moyenne étale le contour sur une frange à demi transparente ; on raidit l'alpha autour
            # de 1/2 (pente 1,5) : la frange pâle disparaît, le trait sombre du contour reste plein
            al = int(max(0.0, min(255.0, (a / tot - 127.5) * RAIDEUR_ALPHA + 127.5)) + 0.5)
            if al == 0:
                res.append((0, 0, 0, 0))
                continue
            res.append((min(255, int(r / a + 0.5)), min(255, int(g / a + 0.5)), min(255, int(b / a + 0.5)),
                        min(255, al)))
    return res


def image(nom: str, cote: int = 32) -> list[Pixel]:
    """L'image `ressources/<nom>` à cote × cote (mémorisée par (nom, cote))."""
    cle = (nom, cote)
    if cle not in _IMAGES:
        if nom not in _IMAGES:
            w, h, pix = L.lire_png(RESSOURCES / nom)
            _IMAGES[nom] = (w, h, [tuple(p) for p in pix])
        w, h, pix = _IMAGES[nom]
        _IMAGES[cle] = pix if (w, h) == (cote, cote) else reduire(w, h, pix, cote)
    return list(_IMAGES[cle])


# ------------------------------------------------------------------------------------------------ dessins
def dessin_train(cote: int = 32) -> list[Pixel]:
    """Abonnement de train : carte d'abonnement dessinée par l'humain (`ressources/objet_abonnement_train.png`)."""
    return image(IMAGE_TRAIN, cote)


def dessin_temps(cote: int = 32) -> list[Pixel]:
    """Voyage dans le temps : montre de poche dessinée par l'humain (`ressources/objet_voyage_temps.png`)."""
    return image(IMAGE_TEMPS, cote)


def dessin_miroirs(cote: int = 32) -> list[Pixel]:
    """Miroirs : miroir sombre fissuré dessiné par l'humain (`ressources/objet_miroirs.png`)."""
    return image(IMAGE_MIROIRS, cote)


def dessin_mirapo_poche(cote: int = 32) -> list[Pixel]:
    """Mirapo de poche (ap/objets-mirapo-trousseau) : miroir rond à ruban violet dessiné par l'humain
    (`ressources/objet_mirapo_poche.png`)."""
    return image(IMAGE_MIRAPO, cote)



def dessin_trousseau(nombre: int, cote: int = 32) -> list[Pixel]:
    """Trousseau du donjon à `nombre` clés (1..5) : image dessinée par l'humain
    (`ressources/objet_trousseau_<nombre>.png`)."""
    if not 1 <= nombre <= 5:
        raise ValueError(nombre)
    return image(IMAGES_TROUSSEAU[nombre], cote)


# ------------------------------------------------------------------------------------------------ objets
# (clé de objets.json, colonne, ligne de la case de l'atlas, dessin, descriptions FR / EN) ; cases : cercles numérotés
# sans objet (aucune entrée d'item_config ne les cite), grandes images `item_<n>` absentes du jeu [C : relevé sur la
# ROM européenne, test_objets_voyage]. Descriptions saisies à la main (deux lignes, `\\n` = retour à la ligne du moteur
# de texte, comme les invitations ; 38 caractères au plus par ligne : les lignes des descriptions du jeu font 41
# caractères au plus en français, 38 en anglais [M, item_text_fr / engb]).
LIGNE_MAX = 38
OBJETS = (
    ("train", 15, 6, dessin_train, {
        "fr": "Un abonnement de train Archipelago.\\nLes portillons des gares s'ouvrent !",
        "en": "An Archipelago train pass.\\nStation gates will let you through!"}),
    ("voyage_dans_le_temps", 0, 7, dessin_temps, {
        "fr": "Le droit de voyager dans le temps.\\nLe passé t'ouvre ses portes !",
        "en": "Permission to travel through time.\\nThe past is now open to you!"}),
    ("miroirs", 8, 9, dessin_miroirs, {
        "fr": "Les Miroirfeuille te font voyager\\nd'une ville à l'autre en un instant !",
        "en": "Mirapo mirrors are at your service.\\nHop from town to town in a flash!"}),
)
DESSINS = {cle: dessin for cle, _c, _l, dessin, _d in OBJETS}

# ap/objets-mirapo-trousseau (`archipelago_invites.md` §16.11) : objets du jeu SANS objet Archipelago propre (noms
# saisis à la main), donnés par le jeu d'après les verrous reçus (`apObjetsVoyageImage`), jamais deux du même GROUPE
# dans le sac (le jeu retire l'ancien juste avant de donner le nouveau) : un groupe ne prend qu'un emplacement.
# - « Mirapo de poche » : 2e exemplaire des « Miroirs progressifs » (verrou k = 61) ; remplace « Miroirs » (même
#   groupe). Case 155 (11, 9), grande image item_156.
# - « Trousseau du donjon (n/5) » : une définition par ENSEMBLE m (1..31) de clés du donjon des portails reçues (bit i
#   = porte à 5, 10, 20, 30, 40 globes), pour que la description liste les portes ouvertes ; icône selon le NOMBRE n de
#   clés (cases 194..198 = (2..6, 12), grandes images item_195..item_199). Hachages crc32("ap_trousseau_donjon_<m>").
GROUPES = {"miroirs": "miroirs", "mirapo_de_poche": "miroirs"}
GROUPE_TROUSSEAU = "trousseau_donjon"
MIRAPO = ("mirapo_de_poche", "Mirapo de poche", "Pocket Mirapo", 11, 9, dessin_mirapo_poche, {
    "fr": "Un Mirapo qui tient dans la poche !\\nTiens SELECT : voyage par les miroirs",
    "en": "A Mirapo that fits in your pocket!\\nHold SELECT to travel by mirror."})
CLE_AP_MIRAPO = "miroirs_progressifs"               # objet AP (objets.json) dont le 2e exemplaire est le Mirapo
CLES_AP_DONJON = tuple("cle_donjon_portails_%d" % i for i in range(1, 6))
PORTES_GLOBES = (5, 10, 20, 30, 40)                 # besoin des portes, dans l'ordre des clés (k = 62..66)
CASES_TROUSSEAU = {n: (1 + n, 12) for n in range(1, 6)}   # n clés -> (colonne, ligne)
PREFIXE_TROUSSEAU = "trousseau_donjon_"


def _dessin_trousseau_n(n: int):
    """Le dessin à n clés, une seule fonction par n (les définitions de même n partagent la même case de l'atlas)."""
    f = _DESSINS_TROUSSEAU.get(n)
    if f is None:
        f = _DESSINS_TROUSSEAU[n] = lambda cote=32, n=n: dessin_trousseau(n, cote)
    return f


_DESSINS_TROUSSEAU: dict = {}


def _liste(nombres: list[int], et: str) -> str:
    return ", ".join(map(str, nombres[:-1])) + (" %s " % et if len(nombres) > 1 else "") + str(nombres[-1])


def trousseau(masque: int) -> tuple:
    """(clé, nom FR, nom EN, colonne, ligne, dessin, descriptions) de la version du trousseau du masque `masque`."""
    if not 1 <= masque <= 31:
        raise ValueError(masque)
    portes = [PORTES_GLOBES[i] for i in range(5) if masque >> i & 1]
    n = len(portes)
    col, lig = CASES_TROUSSEAU[n]
    fr = ("Portes : %s globes" if n > 1 else "Porte : %s globes") % _liste(portes, "et")
    en = ("Doors: %s orbs" if n > 1 else "Door: %s orbs") % _liste(portes, "and")
    return (PREFIXE_TROUSSEAU + str(masque), "Trousseau du donjon (%d/5)" % n, "Gate Dungeon Keyring (%d/5)" % n,
            col, lig, _dessin_trousseau_n(n), {
                "fr": "Clés des portes du donjon des portails\\n" + fr,
                "en": "Keys to the Gate Dungeon's orb doors.\\n" + en})


def trousseaux() -> list[tuple]:
    return [trousseau(m) for m in range(1, 32)]


# ap/multiplicateur-xp-objet (`archipelago_invites.md` §16.13) : « Multiplicateur d'XP x2 / x3 / x4 », objet du jeu de
# l'objet AP progressif « Multiplicateur d'XP » (`multiplicateur_xp` d'objets.json, 3 exemplaires, verrous k = 81..83,
# `archipelago_multiplicateur_xp.md`) : une définition par PALIER (n exemplaires reçus -> facteur n + 1), un seul
# groupe (le jeu retire le palier tenu puis donne le suivant : un emplacement du sac). Hachages
# crc32("ap_multiplicateur_xp_<facteur>") ; cases sans objet 263..265 = (7..9, 16), grandes images item_264..item_266.
# Icônes dessinées en code (aucune image du jeu) : médaille ronde (vert, bleu, or selon le palier) marquée « x2 »,
# « x3 », « x4 ». Noms et descriptions saisis à la main (38 caractères au plus par ligne).
CLE_AP_XP = "multiplicateur_xp"
GROUPE_XP = "multiplicateur_xp"
PREFIXE_XP = "multiplicateur_xp_"
FACTEURS_XP = (2, 3, 4)
CASES_XP = {2: (7, 16), 3: (8, 16), 4: (9, 16)}
_COULEURS_XP = {2: ((70, 190, 90), (40, 140, 60), (170, 240, 170)),        # (aplat, anneau sombre, reflet)
                3: ((70, 150, 235), (40, 95, 185), (175, 215, 255)),
                4: ((250, 195, 45), (205, 135, 20), (255, 240, 165))}
_MOTS_XP = {2: ("doublée", "doubled"), 3: ("triplée", "tripled"), 4: ("quadruplée", "quadrupled")}


def _glyphe_chiffre(n: int, r: float):
    """Le chiffre n (2, 3, 4) en trait épais de demi-épaisseur r, dans la moitié droite de l'icône."""
    if n == 2:
        a = 25.0
        ex, ey = 0.62 + 0.15 * math.cos(math.radians(a)), 0.37 + 0.15 * math.sin(math.radians(a))
        return union(anneau(0.62, 0.37, 0.15, r, 185.0, 360.0 + a), segment(ex, ey, 0.47, 0.76, r),
                     segment(0.47, 0.76, 0.80, 0.76, r))
    if n == 3:
        return union(anneau(0.62, 0.36, 0.125, r, 195.0, 450.0), anneau(0.62, 0.625, 0.14, r, 270.0, 525.0))
    if n == 4:
        return union(segment(0.70, 0.23, 0.70, 0.79, r), segment(0.70, 0.23, 0.46, 0.60, r),
                     segment(0.46, 0.60, 0.81, 0.60, r))
    raise ValueError(n)


def dessin_xp(facteur: int, cote: int = 32) -> list[Pixel]:
    """Multiplicateur d'XP : médaille ronde à la couleur du palier, « x<facteur> » en blanc cerné de sombre."""
    plat, sombre, reflet = _COULEURS_XP[facteur]
    fond = disque(0.5, 0.5, 0.43)
    interieur = disque(0.5, 0.5, 0.36)
    brillance = ellipse(0.36, 0.27, 0.12, 0.06)
    signe = union(segment(0.20, 0.47, 0.35, 0.66, 0.042), segment(0.35, 0.47, 0.20, 0.66, 0.042))
    texte = union(signe, _glyphe_chiffre(facteur, 0.05))
    return rendre(cerne(fond, sombre) + [(interieur, plat), (brillance, reflet),
                                         (contour(texte, 0.038), CONTOUR), (texte, (255, 255, 255))], cote)


def _dessin_xp_f(facteur: int):
    """Le dessin du palier, une seule fonction par facteur (une case d'atlas par dessin)."""
    f = _DESSINS_XP.get(facteur)
    if f is None:
        f = _DESSINS_XP[facteur] = lambda cote=32, facteur=facteur: dessin_xp(facteur, cote)
    return f


_DESSINS_XP: dict = {}


def multiplicateur_xp(facteur: int) -> tuple:
    """(clé, nom FR, nom EN, colonne, ligne, dessin, descriptions) du palier « x<facteur> » (2, 3, 4)."""
    if facteur not in FACTEURS_XP:
        raise ValueError(facteur)
    col, lig = CASES_XP[facteur]
    fr, en = _MOTS_XP[facteur]
    return (PREFIXE_XP + str(facteur), "Multiplicateur d'XP x%d" % facteur, "EXP Multiplier x%d" % facteur,
            col, lig, _dessin_xp_f(facteur), {
                "fr": "L'expérience gagnée est %s !\\nCombats, requêtes, objets d'XP" % fr,
                "en": "All EXP you earn is %s!\\nBattles, requests and EXP items." % en})


def multiplicateurs_xp() -> list[tuple]:
    return [multiplicateur_xp(f) for f in FACTEURS_XP]


# ap/cles-icone-coffre (`archipelago_invites.md` §21) : définitions d'AFFICHAGE, jamais données : elles portent le nom de
# l'objet AP et l'image d'un objet du mod dans la fenêtre « objet obtenu ». Clé de l'objet AP -> (colonne, ligne, dessin,
# descriptions). Clés du donjon : image du trousseau à une clé ; Miroirs progressifs : image des Miroirs (premier stade,
# quel que soit l'exemplaire : les tables sont fixes, et le nom reste celui de l'objet AP).
def affichage_cle(i: int) -> tuple:
    """(colonne, ligne, dessin, descriptions) de l'affichage de la clé n° i (0..4) du donjon des portails."""
    n = PORTES_GLOBES[i]
    col, lig = CASES_TROUSSEAU[1]
    return col, lig, _dessin_trousseau_n(1), {
        "fr": "Clé d'une porte du donjon des portails\\nPorte : %d globes" % n,
        "en": "Key to a Gate Dungeon orb door.\\nDoor: %d orbs" % n}


def affichage_miroirs() -> tuple:
    """(colonne, ligne, dessin, descriptions) de l'affichage des Miroirs progressifs."""
    _c, col, lig, dessin, desc = OBJETS[2]
    return col, lig, dessin, desc


# Icônes dessinées de la colonne d'objets du lanceur pour des objets AP sans objet du jeu d'origine : clé AP ->
# (clé de l'objet ajouté au jeu, dont le hachage entre dans la signature des références, dessin).
ICONES_LANCEUR = {cle: (cle, dessin) for cle, dessin in DESSINS.items()}
ICONES_LANCEUR[CLE_AP_MIRAPO] = (MIRAPO[0], dessin_mirapo_poche)


def etendre_couleurs(pix: list[Pixel], cote: int) -> list[Pixel]:
    """Couleur des pixels transparents étendue depuis les voisins (pas de liseré au filtrage ; l'ETC1 n'a pas à coder
    une couleur arbitraire sous l'alpha nul), comme `icone.charger_icone`."""
    rgb = {i: p[:3] for i, p in enumerate(pix) if p[3]}
    if not rgb:
        return list(pix)
    while len(rgb) < cote * cote:
        ajout = {}
        for i in range(cote * cote):
            if i in rgb:
                continue
            x = i % cote
            v = [rgb[j] for j in (i - 1 if x else -1, i + 1 if x < cote - 1 else -1, i - cote, i + cote)
                 if 0 <= j < cote * cote and j in rgb]
            if v:
                ajout[i] = tuple(sum(k[n] for k in v) // len(v) for n in range(3))
        rgb.update(ajout)
    return [rgb[i] + (pix[i][3],) for i in range(cote * cote)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apercu", type=Path, required=True, help="dossier des PNG d'aperçu (hors git)")
    a = ap.parse_args(argv)
    a.apercu.mkdir(parents=True, exist_ok=True)
    fonds = ((128, 128, 128), (250, 240, 215), (60, 70, 130))
    a_voir = [(cle, dessin) for cle, _c, _l, dessin, _d in OBJETS] + [(MIRAPO[0], MIRAPO[5])]
    a_voir += [("trousseau_%d" % n, _dessin_trousseau_n(n)) for n in range(1, 6)]
    a_voir += [(t[0], t[5]) for t in multiplicateurs_xp()]
    for cle, dessin in a_voir:
        for cote, echelle in ((32, 8), (64, 4)):
            pix = dessin(cote)
            out = []
            for y in range(cote * echelle):
                for x in range(cote * len(fonds) * echelle):
                    fx = x // echelle
                    r, g, b, al = pix[(y // echelle) * cote + fx % cote]
                    f = fonds[fx // cote]
                    out.append(tuple((c * al + v * (255 - al)) // 255 for c, v in zip((r, g, b), f)) + (255,))
            p = a.apercu / f"{cle}_{cote}.png"
            L.ecrire_png(p, cote * len(fonds) * echelle, cote * echelle, out)
            print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
