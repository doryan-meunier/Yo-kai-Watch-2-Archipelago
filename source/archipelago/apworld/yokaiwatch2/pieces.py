# -*- coding: utf-8 -*-
"""Pièces spéciales du Crank-a-kai (V3, lot 20 : docs/systemes/archipelago_v3_pieces_speciales.md §13), sans Archipelago.

Données saisies à la main (règle 6 de CLAUDE.md : n° du Médaillium, clés d'objets, identifiants AP ; les hachages des
objets du jeu sont dans `donnees/objets.json`, relus sur la ROM européenne). Le côté jeu est le lot 19 (option étendue
32, fonction étendue 46, zone ApPieces : `src/archipelago/pieces.cpp`, `voie.cpp`).

OPTION `pieces_speciales` (désactivée par défaut ; FORCÉE par l'objectif « medaillium_complet » ; elle FORCE
`bingo_kai_infini`). Avec elle :
- au pool, des objets ORDINAIRES du jeu (don « objet » par la file existante, rien à installer dans le RomFS) :
  16 Pièces 5 étoiles, 4 Pièces frisson (fleur), les 9 pièces régionales, 3 Pile ou passe (dont celle de l'histoire :
  2 de plus), 3 Super pile ou passe, les 9 objets de fusion régionaux ; tous de progression ;
- le jeu DIRIGE le tirage : une pièce donne à coup sûr un Yo-kai visé qui manque (jamais un objet, jamais un
  doublon), et redonne une pièce perdue (« pièce rendue », bornée) : ces checks « Ami » sont CERTAINS ;
- les Yo-kai visés QUITTENT l'Auberge des voyageurs : leurs invitations ne sont pas créées, leurs locations « Ami »
  gardent leur identifiant AP, avec la règle ci-dessous, et peuvent contenir de la progression ;
- les 16 de Pièce 5 étoiles ne sont JAMAIS des invités (l'option `invites_5_etoiles` du lot 14 est retirée) : sans
  cette option, leurs 16 locations « Ami » n'existent pas.
Sans l'option : exactement le plan d'avant (les 28 Yo-kai de la V2 concernés restent des invités de l'Auberge).

RÈGLES (toutes : accès à la machine du PRÉSENT, mont Sylvestre, après le tutoriel du Crank-a-kai = phase 2-70,
flag 44 [C, §12.10] : portée par « Chapitre 2 terminé », plus stricte que le jeu, jamais moins ; n'importe quelle
machine ordinaire donne les 16, la machine du passé n'est donc jamais exigée ; Pile ou passe et Super pile ou passe
ne se mettent que dans la machine du présent) :
- « Ami : <5 étoiles> » de rang k dans l'ORDRE DE SORTIE de la graine : k Pièces 5 étoiles. L'ordre est tiré une
  fois à la génération (`slot_data.pieces_ordre`), écrit dans le jeu par le client (ApPieces::ordre) ; avec k pièces,
  les k premiers MANQUANTS de l'ordre sortent : un Yo-kai de rang k est obtenu avec au plus k pièces ;
- « Ami : <frisson> » de rang k dans l'ordre fixe du jeu (ORDRE_FRISSON) : k Pièces frisson (fleur) ;
- « Ami : <régional> » : sa pièce ;
- « Ami : Loubarbare / Corniot / Toutouïe » : 3 Pile ou passe (le joueur choisit ; le menu ne propose que ceux qui
  manquent : un Yo-kai précis n'est certain qu'avec les trois) ; « Ami : Komasan / Noko / Buchinyan » : 3 Super pile
  ou passe ;
- « Ami : <fusion régionale> » (371 … 387) : la pièce de sa base, son objet de fusion, un chapitre de plus
  (convention des dérivés) ; EXCLUE (la fusion elle-même n'a jamais été vue en jeu poser le bit [S fort]) ;
- évolutions par niveau (Babalance, Pardomino, Racaïd, Komaous, Bicorniot, Nénunoko) : la règle de leur base, un
  chapitre de plus ; EXCLUES (niveau à atteindre), avec l'option `amis` = tous, comme avant.
Cho-cho (132) et Dynamo (65) : machine du train d'or dirigée par le jeu, mais le train passe au hasard (1 sur 10 ;
lot 22 : 2 à 4 sur 10 avec l'option `train_dore`, que la logique ne suppose jamais) et
après la fin : aucun check nouveau, ils restent « longs » (voie « tunnel » du Médaillium).

LOT 21 (docs/systemes/archipelago_v3_medaillium_448.md ; décisions de l'humain du 2026-10-13), pour toute graine
générée depuis (`lot21` vrai ; une graine d'avant, reconnue par l'absence de la fonction 47 dans ses
`fonctions_exigees`, garde les règles ci-dessus) :
- BANANAR (n° 314) : une « Pièce bleu ciel » de plus au pool (pièce de COULEUR ordinaire du jeu, vendable et
  trouvable) ; le jeu dirige le tirage de cette pièce vers Bananar, sur les DEUX machines ordinaires, tant qu'il n'est
  pas ami (ensuite : tirage du jeu) ; location « Ami : Bananar » : 1 Pièce bleu ciel + la machine du présent, NON
  exclue ;
- les 9 FUSIONS RÉGIONALES ne sont plus exclues : la pièce de la base + l'objet de fusion + la machine + la fusion
  chez M. Zen du Coteau fleuri (`t103i31`), qui ne la propose qu'une fois la requête 4 « Bam boum ! Fusion ! » finie
  (flag 64, posé par le script de fin de la requête, phase >= 3-95 ; requête CLÉ du chapitre 3) [C]. Règle : celle de
  la requête 4 et de « Chapitre 3 terminé », dans la région du Coteau fleuri, avec l'accès au mont Sylvestre. Aucun
  niveau, rang ni prix n'est exigé par la fusion, et le menu « nouvel ami » qui la suit pose le bit du Médaillium [C].
"""
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

OPTION_PAR_DEFAUT = False
# Fonction étendue du patch (bit 14 de ApPnj::fonctions, les quatre parties du lot 19) et n° « client », JAMAIS
# publié par le jeu : un client d'avant accepterait la graine sans poser l'option étendue 32 ni l'ordre de sortie ni
# les compteurs de pièces reçues ; il la refuse sur ce n° (et sur le 22). Suivant libre : 73.
FONCTION_JEU = 46
FONCTION_CLIENT_11 = 72
# Lot 21 : fonction étendue 47 du patch (Bananar à la Pièce bleu ciel ; photos de Ψ Blasters) et n° « client » 73,
# jamais publié : un client d'avant ne compterait pas la Pièce bleu ciel reçue et ne poserait pas l'option étendue 33.
FONCTION_LOT21 = 47
FONCTION_CLIENT_12 = 73
# Lot 22 : fonction étendue 48 du patch (bit 16 de ApPnj::fonctions) : la Pièce bleu ciel n'est plus dans la liste de
# VENTE des boutiques tant que l'option est en vigueur. Aucun n° « client » (le client n'écrit rien de nouveau) : un
# patch d'avant est refusé par la fonction elle-même. Suivants libres : fonction 49, option étendue 34, n° « client » 74.
FONCTION_LOT22 = 48

FAMILLE = "piece"                           # famille d'objets.json des pièces ajoutées par ce lot
FAMILLE_FUSION = "fusion_regionale"         # ... et des 9 objets de fusion régionaux
OBJET_5_ETOILES = "piece_5_etoiles"
OBJET_FRISSON = "piece_frisson_fleur"
OBJET_PILE = "pile_ou_passe"                # objet-clé de la V2 (famille « objet_cle », verrou du tutoriel du chapitre 2)
OBJET_SUPER = "super_pile_ou_passe"
OBJET_BLEU = "piece_bleu_ciel"              # lot 21 : pièce de couleur ordinaire, un seul visé (Bananar)
BANANAR = 314

# Les 16 de la Pièce 5 étoiles dans l'ordre EN DUR du jeu (n° du Médaillium croissant : lignes SORTE_5E de voie.cpp).
# C'est l'ordre de sortie d'un jeu qui n'a pas reçu d'ordre (et le repli du jeu si l'ordre écrit est invalide).
ORDRE_JEU: Tuple[int, ...] = (37, 39, 81, 83, 118, 122, 157, 159, 199, 201, 238, 240, 279, 283, 305, 321)
# Les 4 de la Pièce frisson (fleur), dans l'ordre fixe du jeu (Trodésolé, Apélicain, Dracunyan, Raltesse)
ORDRE_FRISSON: Tuple[int, ...] = (59, 68, 233, 228)
# Pièces régionales : (clé de la pièce, n° du Yo-kai, n° de sa fusion, clé de l'objet de fusion) [C : COMBINE_INFO]
REGIONALES: Tuple[Tuple[str, int, int, str], ...] = (
    ("piece_du_nord", 370, 371, "sculpture_d_ours"),
    ("piece_du_nordet", 372, 373, "lanterne_carassin"),
    ("piece_du_levant", 374, 375, "lanterne_du_maitre"),
    ("piece_du_centre", 376, 377, "embleme_d_or"),
    ("piece_du_ponant", 378, 379, "moule_a_takoyaki"),
    ("piece_des_montagnes", 380, 381, "sable_des_dunes"),
    ("piece_du_sud", 382, 383, "chapeau_de_paille"),
    ("piece_du_centre_ouest", 384, 385, "statue_de_terre_cuite"),
    ("piece_des_iles", 386, 387, "hibiscus_rouge"),
)
# Pièces au choix : les trois Yo-kai de chaque pièce (ordre des places du menu du jeu)
CHOIX: Dict[str, Tuple[int, ...]] = {OBJET_PILE: (95, 259, 53), OBJET_SUPER: (142, 285, 138)}

# Exemplaires de chaque objet dans la partie (pool ; Pile ou passe : celle de l'histoire comprise, où qu'elle soit)
EXEMPLAIRES: Dict[str, int] = {OBJET_5_ETOILES: len(ORDRE_JEU), OBJET_FRISSON: len(ORDRE_FRISSON),
                               **{p: 1 for p, _n, _f, _o in REGIONALES}, OBJET_PILE: 3, OBJET_SUPER: 3,
                               **{o: 1 for _p, _n, _f, o in REGIONALES}}
# (ordre des familles de pièces du jeu, `ApPieces::recues` : la Pièce bleu ciel du lot 21 est la dernière)
PIECES: Tuple[str, ...] = (OBJET_5_ETOILES, OBJET_FRISSON) + tuple(p for p, _n, _f, _o in REGIONALES) \
    + (OBJET_PILE, OBJET_SUPER, OBJET_BLEU)
EXEMPLAIRES_LOT21: Dict[str, int] = {OBJET_BLEU: 1}
OBJETS_FUSION: Tuple[str, ...] = tuple(o for _p, _n, _f, o in REGIONALES)

# Machine exigée par toutes les règles : celle du présent (mont Sylvestre `t102g00`), après le tutoriel du chapitre 2
REGION_MACHINE = "mont_sylvestre"
CHAPITRE_MACHINE = 2
CHAPITRE_DERIVE = CHAPITRE_MACHINE + 1      # fusions régionales et évolutions par niveau : un chapitre de plus
# Lot 21 : la fusion Yo-kai + objet se fait chez M. Zen (`t103i31`, Coteau fleuri), qui ne la propose qu'après la
# requête 4 (flag 64 [C]) ; le lieu du passé (`t201i01`, sans condition) n'est jamais exigé.
REGION_FUSION = "coteau_fleuri"
REQUETE_FUSION = 4
CHAPITRE_FUSION = 3

# N° du Médaillium qui QUITTENT l'Auberge des voyageurs avec l'option (28 des 30 invités à invitation de la V2 ;
# restent : Épinyan et Bandinyan, et Pandanoko, qui n'a pas d'invitation)
MEDAILLES_REGIONALES: Tuple[int, ...] = tuple(n for _p, n, _f, _o in REGIONALES)
MEDAILLES_FUSIONS: Tuple[int, ...] = tuple(f for _p, _n, f, _o in REGIONALES)
QUITTENT_AUBERGE: FrozenSet[int] = frozenset(ORDRE_FRISSON) | frozenset(MEDAILLES_REGIONALES) \
    | frozenset(MEDAILLES_FUSIONS) | frozenset(CHOIX[OBJET_PILE]) | frozenset(CHOIX[OBJET_SUPER])
# Checks dont la pièce donne le Yo-kai à coup sûr : NON exclus (16 + 4 + 9 + 6)
CERTAINS: FrozenSet[int] = frozenset(ORDRE_JEU) | frozenset(ORDRE_FRISSON) | frozenset(MEDAILLES_REGIONALES) \
    | frozenset(CHOIX[OBJET_PILE]) | frozenset(CHOIX[OBJET_SUPER])
# ... et, depuis le lot 21, Bananar et les 9 fusions régionales (35 + 1 + 9 = 45 non exclus)
CERTAINS_LOT21: FrozenSet[int] = CERTAINS | frozenset((BANANAR,)) | frozenset(MEDAILLES_FUSIONS)

NOTE_PIECE = "pièce spéciale du pool, tirage dirigé et pièce rendue (lots 19 et 20 : rien n'a été essayé en jeu)"
NOTE_FUSION = "fusion de son Yo-kai régional (pièce du pool) avec son objet de fusion (au pool)"
NOTE_FUSION_LOT21 = ("fusion de son Yo-kai régional (pièce du pool) avec son objet de fusion (au pool), chez M. Zen du "
                     "Coteau fleuri après la requête « Bam boum ! Fusion ! »")
NOTE_BLEU = ("Pièce bleu ciel du pool : le tirage est dirigé vers Bananar sur les deux machines tant qu'il n'est pas "
             "ami (lot 21 : rien n'a été essayé en jeu)")
# Yo-kai du Bingo-kai gagnant (gare Brise-boucle) : tirage dirigé par le jeu, train au hasard (1 sur 10, ou le réglage
# `train_dore` : lot 22), après la fin
TRAIN_D_OR: Tuple[int, ...] = (132, 65)
# Bananar (n° 314, Pièce bleu ciel du passé, 3 %) : décidé au lot 21 (une Pièce bleu ciel au pool, tirage dirigé).
# Plus aucun Yo-kai « de pièce » sans voie décidée ; (314,) pour une graine d'avant le lot 21.
SANS_VOIE_DECIDEE: Tuple[int, ...] = ()
SANS_VOIE_AVANT_LOT21: Tuple[int, ...] = (BANANAR,)


def ordre_valide(ordre: Optional[Sequence[int]]) -> Tuple[int, ...]:
    """Ordre de sortie des 16 de la Pièce 5 étoiles (n° du Médaillium) ; None : l'ordre en dur du jeu. ValueError
    si ce n'est pas une permutation des 16."""
    if ordre is None:
        return ORDRE_JEU
    o = tuple(int(n) for n in ordre)
    if sorted(o) != sorted(ORDRE_JEU):
        raise ValueError(f"ordre des Pièces 5 étoiles : pas une permutation des 16 Yo-kai ({ordre!r})")
    return o


def tirer_ordre(alea) -> Tuple[int, ...]:
    """Ordre de sortie d'une graine : permutation des 16, tirée UNE fois à la génération (`alea` : le générateur du
    monde ; appelé seulement pour une graine qui a l'option : le flux aléatoire des autres ne change pas)."""
    o = list(ORDRE_JEU)
    alea.shuffle(o)
    return tuple(o)


def exigences(ordre: Sequence[int], lot21: bool = True) -> Dict[int, Tuple[Tuple[Tuple[str, int], ...], int, bool]]:
    """n° du Médaillium -> (exemplaires exigés ((clé d'objet, nombre), …), chapitres terminés, exclue) pour chaque
    Yo-kai obtenu par une pièce de ce lot (hors évolutions par niveau, qui suivent leur base). `lot21` (toute graine
    générée depuis le lot 21) : Bananar en plus, fusions régionales NON exclues au chapitre de la fusion (la règle de
    la requête 4 et la région du Coteau fleuri s'ajoutent dans `logique.construire_plan`)."""
    e: Dict[int, Tuple[Tuple[Tuple[str, int], ...], int, bool]] = {}
    for k, n in enumerate(ordre_valide(ordre), 1):
        e[n] = (((OBJET_5_ETOILES, k),), CHAPITRE_MACHINE, False)
    for k, n in enumerate(ORDRE_FRISSON, 1):
        e[n] = (((OBJET_FRISSON, k),), CHAPITRE_MACHINE, False)
    for piece, n, fusion, objet in REGIONALES:
        e[n] = (((piece, 1),), CHAPITRE_MACHINE, False)
        e[fusion] = (tuple(sorted(((piece, 1), (objet, 1)))), CHAPITRE_FUSION if lot21 else CHAPITRE_DERIVE, not lot21)
    for piece, ns in CHOIX.items():
        for n in ns:
            e[n] = (((piece, len(ns)),), CHAPITRE_MACHINE, False)
    if lot21:
        e[BANANAR] = (((OBJET_BLEU, 1),), CHAPITRE_MACHINE, False)
    return e


def exemplaires(lot21: bool = True) -> Dict[str, int]:
    """Exemplaires de chaque objet des pièces spéciales dans la partie (lot 21 : + la Pièce bleu ciel)."""
    return {**EXEMPLAIRES, **(EXEMPLAIRES_LOT21 if lot21 else {})}


def pool(pile_deja_dans_la_partie: bool = True, lot21: bool = True) -> List[str]:
    """Objets ajoutés au pool par l'option. La Pile ou passe de l'histoire existe toujours dans la partie (dans le
    pool si elle est mélangée, sinon placée d'office à son emplacement d'origine) : 2 de plus font les 3."""
    p: List[str] = []
    for cle, n in exemplaires(lot21).items():
        p += [cle] * (n - 1 if cle == OBJET_PILE and pile_deja_dans_la_partie else n)
    return p
