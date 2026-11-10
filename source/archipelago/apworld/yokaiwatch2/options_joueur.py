# -*- coding: utf-8 -*-
"""Options demandées par les joueurs de la V2 (lot options-joueur-v2) : requêtes clés seulement, remplissage par
familles, argent réglable. Module pur (aucun import d'Archipelago) : `logique.py` y lit la table des requêtes clés,
`__init__.py` y tire chaque objet de remplissage. Conception : `docs/systemes/archipelago_options_joueur_v2.md`.

Graines d'avant : rien ne change. Ces options ne touchent ni le jeu ni le client publié (les objets nouveaux sont
donnés par la voie `DON_OBJET` / `DON_ARGENT` existante, d'après `dons` de slot_data) ; leurs valeurs par défaut
reproduisent EXACTEMENT le tirage d'avant (mêmes listes, mêmes appels à `random`).
"""
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

# ------------------------------------------------------------------------------------------------- requêtes clés
# Requêtes CLÉS de l'histoire : celles qu'une quête de chapitre (171 à 180) exige finies (condition de type 9 de
# QUEST_NECESSARY_CONDITION d'une de ses phases), et leurs prérequis (aucun). Table saisie à la main (numéros de
# requête seulement) ; relue sur la ROM du joueur par `archipelago/outils/requetes_cles.py` (comparaison exacte) et
# recoupée avec `zones.ATTENTES` par les tests. Chapitre -> requêtes.
REQUETES_CLES_PAR_CHAPITRE: Dict[int, Tuple[int, ...]] = {
    2: (1, 2, 68), 3: (3, 4, 6), 4: (5, 29, 99), 5: (10, 11, 12), 6: (13, 14, 15, 16, 17), 7: (9, 18, 26),
    9: (19, 20, 21),
}
REQUETES_CLES: FrozenSet[int] = frozenset(q for qs in REQUETES_CLES_PAR_CHAPITRE.values() for q in qs)
# Valeur de l'option `quetes` (logique.MODES_QUETES) : seules les requêtes clés sont des checks
MODE_REQUETES_CLES = "requetes_cles"

# ------------------------------------------------------------------------------------------------- remplissage
# Familles de remplissage (option `remplissage`, clés françaises) -> familles d'objets.json qui les composent.
# « consommables » : les 12 objets de la V2 (défaut : tirage d'avant à l'identique). « nourriture » : les 74 aliments du
# jeu (6 d'entre eux sont aussi des consommables de la V2 : mêmes objets AP). « equipement » : 74 équipements ;
# « livres » : 16 livres (bonus de stats / techniques des Yo-kai). Noms repris des données de l'ancien mod de l'humain,
# hachages = identifiants des objets donnés (règle 6).
FAMILLES_REMPLISSAGE = ("consommables", "nourriture", "equipement", "livres")
REMPLISSAGE_PAR_DEFAUT = frozenset({"consommables"})
FAMILLE_OBJETS = {"consommables": "consommable", "nourriture": "nourriture", "equipement": "equipement",
                  "livres": "livre"}
# consommables de la V2 qui sont des aliments (famille « nourriture » aussi)
ALIMENTS_V2 = ("barre_de_chocolat", "riz_a_la_prune", "riz_a_la_crevette", "y_cola", "the_de_l_ame", "hamburger")

# Argent : montants proposés (option `argent_montants`, clé -> centimes) ; défaut = ceux de la V2 (100 € et 500 €)
MONTANTS: Dict[str, int] = {"euros_10": 1000, "euros_20": 2000, "euros_50": 5000, "euros_100": 10000,
                            "euros_200": 20000, "euros_500": 50000, "euros_1000": 100000, "euros_2000": 200000,
                            "euros_5000": 500000}
MONTANTS_PAR_DEFAUT = frozenset({"euros_100", "euros_500"})
# Forme du don d'argent (option `argent_forme`)
FORMES_ARGENT = ("euros", "objets_a_revendre", "les_deux")
FORME_PAR_DEFAUT = "euros"
# Objets à revendre : les cinq poupées du jeu (famille « objet_valeur ») et leur prix de vente en centimes (11e valeur
# d'ITEM_CONSUME, toutes « vendables » : bit 30 de la définition) [C : tools/romfs, item_config ; identifiants seuls]
POUPEES: Dict[str, int] = {"poupee_de_fer": 300, "poupee_bronze": 1000, "poupee_d_argent": 5000,
                           "poupee_d_or": 20000, "poupee_de_platine": 60000}


def normaliser_familles(familles: Optional[Iterable[str]]) -> Tuple[str, ...]:
    """Familles choisies, dans l'ordre de FAMILLES_REMPLISSAGE ; vide ou inconnues seulement : le défaut."""
    choisies = tuple(f for f in FAMILLES_REMPLISSAGE if f in set(familles or ()))
    return choisies or tuple(sorted(REMPLISSAGE_PAR_DEFAUT))


def normaliser_montants(montants: Optional[Iterable[str]]) -> Tuple[int, ...]:
    """Montants choisis en centimes, croissants ; vide : le défaut."""
    choisis = sorted(MONTANTS[m] for m in set(montants or ()) if m in MONTANTS)
    return tuple(choisis) or tuple(sorted(MONTANTS[m] for m in MONTANTS_PAR_DEFAUT))


def objets_famille(objets: Sequence[dict], famille: str) -> List[str]:
    """Clés des objets d'une famille de remplissage, dans l'ordre d'objets.json."""
    f = FAMILLE_OBJETS[famille]
    return [o["cle"] for o in objets
            if o["famille"] == f or (famille == "nourriture" and o["cle"] in ALIMENTS_V2)]


def objets_argent(objets: Sequence[dict], montants: Sequence[int]) -> List[str]:
    """Objets « argent » des montants choisis (ordre d'objets.json : 100 € et 500 € d'abord, comme dans la V2)."""
    return [o["cle"] for o in objets if o["famille"] == "argent" and o["montant"] in set(montants)]


def poupees(montants: Sequence[int]) -> List[str]:
    """Poupées dont le prix de vente est compris entre le plus petit et le plus grand montant ; aucune : la plus proche
    de cet intervalle (rapport des prix)."""
    bas, haut = min(montants), max(montants)
    dedans = [k for k, v in POUPEES.items() if bas <= v <= haut]
    if dedans:
        return dedans

    def ecart(v: int) -> float:
        return bas / v if v < bas else v / haut
    return [min(POUPEES, key=lambda k: ecart(POUPEES[k]))]


class Tirage:
    """Tirage d'un objet de remplissage (`__init__._remplissage`). Avec les options par défaut, mêmes listes et mêmes
    appels à `random` que la V2 : `randrange(100) < part` -> `choice(argent)`, sinon `choice(consommables)`."""

    def __init__(self, objets: Sequence[dict], familles=None, part_argent: int = 15, montants=None,
                 forme: str = FORME_PAR_DEFAUT):
        self.familles = normaliser_familles(familles)
        self.par_famille = {f: objets_famille(objets, f) for f in self.familles}
        m = normaliser_montants(montants)
        if forme not in FORMES_ARGENT:
            raise ValueError(f"forme d'argent inconnue : {forme!r}")
        self.forme = forme
        self.euros = objets_argent(objets, m)
        self.poupees = poupees(m)
        self.part_argent = part_argent

    def tirer(self, random) -> str:
        # (`randrange` appelé à chaque tirage, même à 0 % : flux de `random` de la V2)
        if random.randrange(100) < self.part_argent:
            if self.forme == "euros":
                return random.choice(self.euros)
            if self.forme == "objets_a_revendre":
                return random.choice(self.poupees)
            return random.choice(random.choice((self.euros, self.poupees)))
        if len(self.familles) == 1:
            return random.choice(self.par_famille[self.familles[0]])
        return random.choice(self.par_famille[random.choice(self.familles)])

    def cles(self) -> List[str]:
        """Tous les objets que ce tirage peut donner (sans doublon, ordre stable)."""
        vus = []
        for f in self.familles:
            vus += self.par_famille[f]
        if self.part_argent > 0:
            vus += self.euros if self.forme != "objets_a_revendre" else []
            vus += self.poupees if self.forme != "euros" else []
        return list(dict.fromkeys(vus))
