"""Bouton « Que faire maintenant ? » du sous-onglet « Carte » (onglet « Checks ») : SANS affichage. Choisit, parmi les
checks que le tracker juge déjà accessibles (`checks.Check.etat`, logique de l'APWorld + progression réelle), ceux à
faire maintenant, les regroupe par carte et range les groupes du plus proche au plus loin de la carte du joueur. La
vue tkinter est dans `vue_que_faire.py` ; textes dans `textes_que_faire.py`. Demande de l'humain du 2026-10-24,
`docs/systemes/archipelago_tracker_cartes.md` §16.

**Ce qui est proposé** : checks non faits à l'état « accessible », gardés par les filtres « type » et « recherche » de
l'onglet. Jamais : « plus tard » (histoire pas assez avancée), objets manquants, inconnus. Masqués sauf demande
explicite du joueur (`montrer_tout`) : les checks EXCLUS (remplissage seulement : jamais d'objet de progression ;
les checks « tardifs » des portails mystères, d'après-jeu… le sont tous) et les articles dont le vendeur est absent à
coup sûr à ce stade (« vendeur absent », « pas encore de sortie la nuit » : `carte_checks.presence`, §12).
Le filtre « Zone » (= barre des régions de la carte) n'est PAS appliqué : il sert à parcourir les cartes, et le but est
justement de partir du joueur ; « Pas faits » et « Accessibles » vont de soi.

**Distance** (choix, §16.2) : `cartes_local.json` ne contient pas les routes entre cartes extérieures (`map_route` ne
sert à la génération que pour les portes des boutiques) ; le lanceur connaît : (1) l'identifiant des cartes
(`t<zone><genre><n>`) et la règle des cartes parentes (§9.1 : une carte se rattache à l'extérieur de sa zone,
`t<zone>g00`) ; (2) les PORTES des bâtiments à boutique (extérieur -> intérieur, §11.3) ; (3) la région de chaque
carte (préfixe saisi à la main, `tracker.REGIONS`, sinon la région de l'APWorld de la majorité de ses checks) ;
(4) le graphe des régions de l'APWorld (`regions.json` : connexions, en étoile autour de la région d'origine « menu »,
qui tient lieu de ville). Graphe : carte — extérieur de sa zone (1 pas), porte (1 pas), extérieur ou carte sans
extérieur — nœud de sa région (1 pas), région — région (connexion de l'APWorld : 2 « sauts de région », 1 pour une
connexion à « menu », de sorte que deux quartiers de la ville sont voisins). Coût = (sauts de région, pas), comparé
dans cet ordre : une carte de la même région passe toujours avant une carte d'une autre région. Sans graphe des
régions (logique absente) : ordre des régions de l'APWorld.

**Priorité dans une carte** : checks à indice (hint) d'abord, puis les autres non exclus (ils peuvent contenir un objet
de progression), puis ceux dont la présence est incertaine (étal ambulant « ? »), puis (si demandés) exclus et
reportés. Groupes : carte du joueur, puis par distance, puis plus de checks prioritaires d'abord. Les checks sans
position sur les cartes (amis, chapitres…) viennent à la fin, groupés par zone de l'APWorld.

Tout est calculé à l'ouverture du panneau et quand une entrée change (modèle relu, carte du joueur, progression,
filtres) : quelques millisecondes pour un plan de 1 400 checks, rien à chaque image. Aucun spoiler : rien d'autre que
`checks.Check` (contenu connu seulement s'il est fait ou indiqué). Bibliothèque standard seulement.
"""
from __future__ import annotations

import heapq
from collections import Counter
from dataclasses import dataclass, field

from . import carte_checks as CC
from . import checks as CK
from . import tracker as TK

HUB = "menu"                              # région d'origine de l'APWorld : dons et histoire (tient lieu de ville)
SAUT_REGION, SAUT_HUB = 2, 1              # coût d'une connexion de régions ; d'une connexion à HUB
REGION_DE_PREFIXE = {p: cle for cle, prefixes, _fr, _en in TK.REGIONS for p in prefixes}
INCONNUE = (10 ** 6, 10 ** 6)             # distance d'une carte hors du graphe

# rangs de priorité d'une ligne (plus petit = d'abord)
RANG_INDICE, RANG_NORMAL, RANG_INCERTAIN, RANG_MASQUE = 0, 1, 2, 3
# proximité affichée d'un groupe
PROXIMITES = ("ici", "a_cote", "region", "voisine", "loin", "inconnue", "sans_position")


@dataclass
class Ligne:
    check: CK.Check
    carte: str | None                     # carte où le faire (la plus proche pour un étal sur plusieurs cartes)
    rang: int                             # RANG_*
    incertain: bool = False               # présence du vendeur inconnue (étal ambulant, condition non suivie)
    report: str | None = None             # « absent » / « nuit » : vendeur absent à coup sûr (montré sur demande)
    position: tuple[float, float] | None = None    # pixel de la carte (marqueur), None : position inconnue
    boutique: str | None = None           # code N0xx : article d'une boutique placée (regroupé par la vue)


@dataclass
class Groupe:
    carte: str | None                     # None : checks sans position (groupés par zone de l'APWorld)
    zone: str | None                      # zone de l'APWorld (groupe sans position)
    distance: tuple[int, int]             # (sauts de région, pas)
    proximite: str                        # un de PROXIMITES
    lignes: list[Ligne] = field(default_factory=list)

    @property
    def prioritaires(self) -> int:
        return sum(1 for l in self.lignes if l.rang <= RANG_NORMAL)


@dataclass
class Resultat:
    depuis: str | None = None             # carte de départ (None : aucune)
    mode: str | None = None               # « joueur » (carte du jeu) | « affichee » (carte affichée) | None
    groupes: list[Groupe] = field(default_factory=list)
    masques: Counter = field(default_factory=Counter)    # exclus, absent, nuit : non montrés (montrer_tout faux)
    total: int = 0                        # lignes montrées

    @property
    def lignes(self) -> list[Ligne]:
        return [l for g in self.groupes for l in g.lignes]


# ------------------------------------------------------------------------------------------------ régions et graphe
def exterieur(carte: str) -> str:
    """Extérieur de la zone d'une carte (`t101i35` -> `t101g00`), la règle des cartes parentes (§9.1)."""
    return carte[:4] + "g00"


def regions_des_cartes(m: CK.ModeleChecks, don: CC.DonneesCartes | None,
                       valides: set[str] | None = None) -> dict[str, str]:
    """Région de l'APWorld de chaque carte à image : préfixe saisi à la main (`tracker.REGIONS`), sinon la zone la plus
    fréquente parmi les checks placés sur cette carte (hors « autres » ; la région d'origine HUB, celle des dons
    d'histoire, seulement s'il n'y en a pas d'autre : la carte est alors rattachée au nœud de la ville).
    `valides` : régions connues de l'APWorld ; un préfixe saisi à la main qui n'en fait pas partie (Granval `t100`,
    Limbes `t301`… : régions du suivi seulement) est ignoré, sinon la carte serait un nœud isolé du graphe (distance
    « inconnue » de toutes les autres) : elle est alors rattachée par le vote de ses checks."""
    if don is None:
        return {}
    votes: dict[str, Counter] = {}
    for c in m.checks:
        p = don.positions.get(c.id)
        if p is not None and c.zone != CK.AUTRES:
            votes.setdefault(p.carte, Counter())[c.zone] += 1
    out = {}
    for k in don.cartes:
        r = REGION_DE_PREFIXE.get(k[:4])
        if valides is not None and r not in valides:
            r = None
        if r is None and votes.get(k):
            r = sorted(votes[k].items(), key=lambda kv: (kv[0] == HUB, -kv[1], kv[0]))[0][0]
        if r is not None:
            out[k] = r
    return out


def connexions_apworld(logique=None) -> list[tuple[str, str]] | None:
    """(source, cible) des connexions de régions de l'APWorld (`regions.json`) ; None : logique absente."""
    L = logique or CK.ck.logique_apworld()
    if L is None:
        return None
    try:
        from importlib import import_module
        don = import_module(CK.ck.PAQUET_PUR + ".donnees").donnees()
        return [(str(c["source"]), str(c["cible"])) for c in don.connexions]
    except Exception:                                      # noqa: BLE001 - logique d'une autre version
        return None


def graphe(don: CC.DonneesCartes | None, regions: dict[str, str], connexions: list[tuple[str, str]] | None,
           ordre_regions: list[str]) -> dict[tuple, list[tuple[tuple, tuple[int, int]]]]:
    """Graphe non orienté : nœuds ("c", carte) et ("r", région) ; arêtes (voisin, (sauts de région, pas))."""
    g: dict[tuple, list] = {}

    def lier(a, b, cout):
        if a != b:
            g.setdefault(a, []).append((b, cout))
            g.setdefault(b, []).append((a, cout))

    cartes = set(don.cartes) if don is not None else set()
    for k in sorted(cartes):
        g.setdefault(("c", k), [])
        ext = exterieur(k)
        if ext in cartes and ext != k:
            lier(("c", k), ("c", ext), (0, 1))            # carte de la zone -> son extérieur
        elif k in regions:
            lier(("c", k), ("r", regions[k]), (0, 1))     # extérieur (ou carte sans extérieur) -> sa région
    if don is not None:
        for lieux in don.boutiques.values():               # portes des bâtiments à boutique
            for l in lieux:
                if l.genre == "entree" and l.vers in cartes:
                    lier(("c", l.carte), ("c", l.vers), (0, 1))
    if connexions:
        for s, c in connexions:
            lier(("r", s), ("r", c), (SAUT_HUB if HUB in (s, c) else SAUT_REGION, 0))
    else:                                                  # sans graphe : régions voisines dans l'ordre de l'APWorld
        for a, b in zip(ordre_regions, ordre_regions[1:]):
            lier(("r", a), ("r", b), (SAUT_REGION, 0))
    return g


def distances(g: dict, depart: tuple | None) -> dict[tuple, tuple[int, int]]:
    """Plus courts chemins depuis `depart` (Dijkstra, coûts comparés comme des couples)."""
    if depart is None:
        return {}
    d = {depart: (0, 0)}
    tas = [((0, 0), depart)]
    while tas:
        cout, n = heapq.heappop(tas)
        if cout > d.get(n, INCONNUE):
            continue
        for v, (dr, dp) in g.get(n, ()):
            nc = (cout[0] + dr, cout[1] + dp)
            if nc < d.get(v, INCONNUE):
                d[v] = nc
                heapq.heappush(tas, (nc, v))
    return d


def origine(don: CC.DonneesCartes | None, lieu: CC.Lieu | None, carte_affichee: str | None,
            regions: dict[str, str], valides: set[str] | None = None) -> tuple[tuple | None, str | None, str | None]:
    """(nœud de départ, carte de départ, mode) : la carte du jeu (`carte_a_montrer` : elle-même ou sa carte parente),
    sinon la région de son préfixe, sinon la carte affichée (jeu non suivi), sinon rien."""
    if lieu is not None and lieu.carte:
        c = CC.carte_a_montrer(don, lieu.carte)
        if c is not None:
            return ("c", c), c, "joueur"
        r = REGION_DE_PREFIXE.get(lieu.carte[:4])
        if r is not None and (valides is None or r in valides):
            return ("r", r), lieu.carte, "joueur"
    if don is not None and carte_affichee in don.cartes:
        return ("c", carte_affichee), carte_affichee, "affichee"
    return None, None, None


def proximite(dist: tuple[int, int], est_depart: bool) -> str:
    if est_depart:
        return "ici"
    if dist >= INCONNUE:
        return "inconnue"
    if dist[0] == 0:
        return "a_cote" if dist[1] <= 2 else "region"
    return "voisine" if dist[0] <= SAUT_REGION else "loin"


# ------------------------------------------------------------------------------------------------ candidats
def _presences_vendeur(don: CC.DonneesCartes, code: str, prog) -> dict[str, CC.Presence]:
    """Présence du vendeur de `code` sur chaque carte où il a un emplacement (la plus favorable de la carte)."""
    par_carte: dict[str, list] = {}
    for l in don.boutiques.get(code, ()):
        if l.genre == "vendeur":
            par_carte.setdefault(l.carte, []).append(CC.presence(l, prog))
    return {k: CC.presence_combinee(ps) for k, ps in par_carte.items()}


def _point_vendeur(don: CC.DonneesCartes, code: str, carte: str) -> tuple[float, float] | None:
    l = next((l for l in don.boutiques.get(code, ()) if l.genre == "vendeur" and l.carte == carte), None)
    return (l.x, l.y) if l is not None else None


def construire(m: CK.ModeleChecks, don: CC.DonneesCartes | None, f: CK.Filtre | None = None,
               prog: TK.Progression | None = None, lieu: CC.Lieu | None = None, carte_affichee: str | None = None,
               connexions: list[tuple[str, str]] | None = None, montrer_tout: bool = False) -> Resultat:
    """Liste « Que faire maintenant ? » (voir la docstring du module)."""
    f = f or CK.Filtre()
    garde = CK.Filtre(texte=f.texte, type=f.type)          # type et recherche seulement (zone : voir plus haut)
    ordre_regions = [k for k, _n in m.zones]
    valides = (set(ordre_regions) | {x for c in (connexions or ()) for x in c}) if (connexions or ordre_regions) else None
    regions = regions_des_cartes(m, don, valides)
    g = graphe(don, regions, connexions, ordre_regions)
    depart, carte_depart, mode = origine(don, lieu, carte_affichee, regions, valides)
    dist = distances(g, depart)
    res = Resultat(depuis=carte_depart, mode=mode)

    def d_carte(k: str) -> tuple[int, int]:
        return dist.get(("c", k), INCONNUE)

    lignes: list[Ligne] = []
    for c in m.checks:
        if c.etat != "accessible" or not garde.garde(c, m):
            continue
        p = don.positions.get(c.id) if don is not None else None
        cartes = [p.carte] if p is not None else []
        incertain, report = False, None
        if p is not None and p.boutique and don is not None:
            pres = _presences_vendeur(don, p.boutique, prog)
            ok = [k for k in CC.cartes_du_check(don, p) if k in pres and pres[k].present is not False]
            if pres and not ok:                            # absent à coup sûr partout : « plus tard » pour le jeu
                report = "nuit" if any(x.nuit == "fermee" for x in pres.values()) else "absent"
            elif ok:
                cartes = ok
                incertain = all(pres[k].present is None for k in ok)
        if c.exclue or report:
            if not montrer_tout:
                res.masques["exclus" if c.exclue else report] += 1
                continue
            rang = RANG_MASQUE
        else:
            rang = RANG_INDICE if c.indice else (RANG_INCERTAIN if incertain else RANG_NORMAL)
        carte = min(cartes, key=lambda k: (d_carte(k), cartes.index(k))) if cartes else None
        pos = None
        if carte is not None and p is not None:
            if p.boutique and don is not None:
                pos = _point_vendeur(don, p.boutique, carte)
            elif p.placee and p.carte == carte:
                pos = (p.x, p.y)
        lignes.append(Ligne(c, carte, rang, incertain, report, pos, p.boutique if p is not None else None))

    par_cle: dict[tuple, Groupe] = {}
    for l in lignes:
        if l.carte is not None:
            cle = ("c", l.carte)
            if cle not in par_cle:
                d = d_carte(l.carte)
                par_cle[cle] = Groupe(l.carte, None, d, proximite(d, l.carte == carte_depart and mode is not None))
        else:
            cle = ("z", l.check.zone)
            if cle not in par_cle:
                d = dist.get(("r", l.check.zone), INCONNUE)
                par_cle[cle] = Groupe(None, l.check.zone, d, "sans_position")
        par_cle[cle].lignes.append(l)
    for gr in par_cle.values():
        gr.lignes.sort(key=lambda l: (l.rang, l.check.nom.casefold(), l.check.id))

    def ordre_genre(k: str | None) -> int:
        info = don.cartes.get(k) if (don is not None and k) else None
        return CC.ORDRE_GENRES.get(info.genre, 9) if info is not None else 9

    zones = {k: i for i, (k, _n) in enumerate(m.zones)}
    res.groupes = sorted(par_cle.values(), key=lambda gr: (
        gr.carte is None,                                  # checks sans position : à la fin
        gr.proximite != "ici", gr.distance,
        -gr.prioritaires, ordre_genre(gr.carte), zones.get(gr.zone, 999), gr.carte or "", gr.zone or ""))
    res.total = len(lignes)
    return res


def signature(m: CK.ModeleChecks, don: CC.DonneesCartes | None, f: CK.Filtre | None, prog: TK.Progression | None,
              lieu: CC.Lieu | None, carte_affichee: str | None, montrer_tout: bool) -> tuple:
    """Ce dont dépend le résultat : la vue ne recalcule que quand elle change (modèle et cartes relus = nouveaux
    objets ; carte du joueur, ou carte affichée quand le jeu n'est pas suivi ; progression ; type et recherche)."""
    carte_jeu = CC.carte_a_montrer(don, lieu.carte) if lieu is not None and lieu.carte else None
    jeu = (lieu.carte, carte_jeu) if lieu is not None and lieu.carte else None
    return (id(m), id(don), None if f is None else (f.texte, f.type), jeu,
            None if carte_jeu else carte_affichee,
            None if prog is None else (prog.phase, prog.rang, prog.apres_jeu), bool(montrer_tout))
