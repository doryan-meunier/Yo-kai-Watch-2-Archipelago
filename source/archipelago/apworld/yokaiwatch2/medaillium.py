# -*- coding: utf-8 -*-
"""Objectif « compléter le Médaillium » (V3, lot 18 : docs/systemes/archipelago_v3_objectif_medaillium.md), sans
Archipelago.

Données saisies à la main (règle 6 de CLAUDE.md : n° du Médaillium, n° de requêtes, identifiants AP, clés de régions et
d'objets, noms FR / EN relus dans la ROM européenne). Le plan est construit par `logique.construire_plan`
(`objectif` = « medaillium_complet ») ; l'inventaire des 448 se rejoue sur la ROM du joueur par
`archipelago/outils/medaillium_voies.py`, qui compare cette table aux données du jeu.

VICTOIRE : flag « partie terminée » ET au moins `seuil` bits « acquis » (P+0x44C | P+0x604) parmi les n° 1 à 448
(slot_data `objectif_medailles` = les 448 n°, `objectif_seuil` = le seuil ; lus par le client dans la lecture groupée
du Médaillium qu'il fait déjà : aucun paquet de plus).

LOGIQUE : l'évènement de victoire exige l'accès à TOUT ce qui donne un n° compté (toutes les régions, tous les objets
qui ouvrent une espèce), quel que soit le seuil : un seuil plus bas raccourcit la partie, il n'allège pas la logique
(plus stricte que nécessaire, jamais moins).

Chaque n° a une VOIE (classe) et un ÉTAT :
- « garantie » : la voie donne le n° à coup sûr (don de script, boss à vaincre) ;
- « hasard » : voie répétable sans limite, issue au hasard (amitié au taux du jeu, errants, don tiré au sort) ;
- « fragile » : voie connue, mais un point n'a jamais été vu en jeu (voir la note) ;
- « attente » : voie en attente d'une décision de l'humain : le n° n'est PAS compté par la logique ;
- « sans_voie » : aucune voie garantie sur émulateur : le n° n'est PAS compté par la logique.
Depuis le lot 21 (docs/systemes/archipelago_v3_medaillium_448.md) plus aucun n° n'est « attente » ni « sans_voie » :
les 448 sont comptés (Domniscian : photos de Ψ Blasters tenues pour prises par le jeu modifié ; Bananar : Pièce bleu
ciel du pool, tirage dirigé). Une graine d'avant garde ses deux n° non comptés (`VOIES_AVANT_LOT21`).
"""
from typing import Dict, FrozenSet, List, Tuple

OBJECTIF = "medaillium_complet"
TOTAL = 448                                 # n° du Médaillium (FUN_0041A944 : 448 n° distincts)
SEUIL_PAR_DEFAUT = TOTAL                    # strict (décision de l'humain, 2026-10-12)
NOM_FR, NOM_EN = "Objectif : compléter le Médaillium", "Goal: complete the Medallium"
# N° « client » de `fonctions_exigees`, jamais publié par le jeu : un client d'avant ce lot (qui ne connaît ni le
# seuil ni les options forcées) refuse la graine. Fonctions étendues du patch dont l'objectif dépend : boss de la Voie
# du mystère à chaque parcours (41), tirage dirigé des machines de la Voie (42), revanches sans limite de jour (43, 44).
FONCTION_CLIENT_10 = 71
FONCTIONS_JEU: Tuple[int, ...] = (41, 42, 43, 44)
# Lot 21 : clé de slot_data posée avec cet objectif : le client pose l'option étendue 33 du jeu (photos de Ψ Blasters
# tenues pour prises ; fonction étendue 47 et n° « client » 73 : `pieces.FONCTION_LOT21`, `FONCTION_CLIENT_12`).
CLE_PHOTOS = "photos_blasters"

GARANTIE, HASARD, FRAGILE, ATTENTE, SANS_VOIE = "garantie", "hasard", "fragile", "attente", "sans_voie"
ETATS = (GARANTIE, HASARD, FRAGILE, ATTENTE, SANS_VOIE)
ETATS_COMPTES: FrozenSet[str] = frozenset((GARANTIE, HASARD, FRAGILE))

# Modes du mélange des Yo-kai permis avec cet objectif : sans mélange, ou par rencontre (version >= 4 : chaque espèce
# du réservoir garde un lieu normal d'avant la fin pour TOUTE graine). Les modes par espèce (« par_rang », « total »)
# laissent des espèces sans lieu normal (9 ou 10 sur la ROM européenne) : remplacés par le mode par rencontre de même
# portée (`mode_rando_permis`).
MODES_RANDO_PERMIS = ("aucun", "par_rencontre_rang", "par_rencontre_total")
MODES_RANDO_REMPLACES = {"par_rang": "par_rencontre_rang", "total": "par_rencontre_total"}


def mode_rando_permis(mode: str) -> str:
    return MODES_RANDO_REMPLACES.get(mode, mode)


# ---------------------------------------------------------------------------
# Objets ajoutés au pool par l'objectif (famille « medaillium » d'objets.json ; objets du jeu donnés réellement)
# ---------------------------------------------------------------------------
FAMILLE = "medaillium"
# Grelot gris (donné seulement par code QR dans le jeu d'origine) : fait apparaître Darknyan après la requête 124.
OBJET_GRELOT_GRIS = "grelot_gris"
# Les 9 objets de fusion que le jeu ne donne que par tirage (loterie, Crank-a-kai, tickets à gratter) : clé -> n° du
# Médaillium du résultat de la fusion (base : `FUSIONS_TIREES`).
OBJETS_FUSION: Dict[str, int] = {
    "epee_legendaire": 28, "epee_maudite": 29, "epee_sacree": 30, "orbe_ghz": 64, "cape_de_blizzard": 131,
    "costume_sable": 173, "eclat_demoniaque": 237, "revue_maudite": 273, "poudre_jouvence": 278,
}
OBJETS: Tuple[str, ...] = (OBJET_GRELOT_GRIS,) + tuple(OBJETS_FUSION)

# ---------------------------------------------------------------------------
# Checks « Ami » des 7 Yo-kai des machines de la Voie du mystère (décision de l'humain, 2026-10-12)
# ---------------------------------------------------------------------------
# Une pièce par victoire sur le boss de la ligne (boss à chaque parcours : fonction 41), tirage dirigé vers le Yo-kai
# manquant (fonction 42). EXCLUS (après-jeu ; rien de cette chaîne n'a été essayé en jeu). Région = la ligne du boss.
# Identifiants : à la suite des invités de Pièce 5 étoiles (59420941..59420947).
AMIS_VOIE: List[dict] = []
for _n, _id, _fr, _en, _region in (
        (79, 59420941, "Tengurou", "Flengu", "voie_du_mystere"),
        (281, 59420942, "Morféa", "Sandi", "voie_du_mystere"),
        (332, 59420943, "Rubinyan", "Rubinyan", "route_des_farceurs"),
        (333, 59420944, "Topanyan", "Topanyan", "route_des_bouffis"),
        (331, 59420945, "Émeranyan", "Emenyan", "grand_route_doree"),
        (330, 59420946, "Saphinyan", "Sapphinyan", "grand_route_doree"),
        (334, 59420947, "Diamanyan", "Dianyan", "grand_route_doree")):
    AMIS_VOIE.append({"medaille": _n, "id_ap": _id, "region": _region, "yokai_fr": _fr, "yokai_en": _en,
                      "nom_fr": "Ami : " + _fr, "nom_en": "Friend: " + _en})
# Boss de la ligne d'une machine (clé du mélange des boss) : la pièce de la machine est son butin (100 %, `CHARA_PARAM_INFO`
# de l'espèce, aucune autre source dans les données ni les scripts) [C] (ap/boss-voie-mystere)
BOSS_DE_LIGNE: Dict[str, str] = {"voie_du_mystere": "blingos", "route_des_farceurs": "cycloptique",
                                 "route_des_bouffis": "maximain", "grand_route_doree": "bogos"}
# N° « vaincre » des 4 boss de la Voie : voie de la table VOIES pour une graine d'avant, celle de la location « Boss : »
# de leur place pour une graine qui l'a (`logique.construire_plan(boss_voie=True)`)
MEDAILLES_BOSS_VOIE: FrozenSet[int] = frozenset((423, 424, 425, 426))

# ---------------------------------------------------------------------------
# N° du Médaillium des boss d'AVANT la fin (clés de `logique.TOUS_LES_BOSS`) : bit posé par le moteur à la victoire
# pour chaque ennemi présent de l'espèce (FUN_005579A8). Les boss dont l'espèce est RECRUTABLE (Injustin à Ronéan,
# Misterre, Démophage, Draconfus, Faux Kappa, Sabrille, Anguigne) n'ont pas de n° « à vaincre » : absents.
# Fumella (n° 362, maléfique) : aussi errante de la Voie du mystère.
# ---------------------------------------------------------------------------
BOSS_AVANT: Dict[str, Tuple[int, ...]] = {
    "grolos": (388,), "meganyan": (389,), "barbefrousse": (390,), "tourboeillon": (391,), "laure": (392,),
    "marge": (393,), "lady_perpetua": (394,), "lady_demona": (395,), "crocho": (398,), "ombraptor": (402,),
    "sabroclair": (404,), "inamygal": (406,), "volteface": (412,), "didgeai": (413,), "firmain": (415,),
    "tromploeil": (416,), "taprice": (417,),
}
# Second n° d'une place de boss d'après-jeu à deux espèces (`apres_jeu.MEDAILLE_BOSS` n'en porte qu'un)
BOSS_SECOND: Dict[str, int] = {"mariotte_et_maribass": 420}
# Occupant dont le bit n'est pas prouvé posé par son combat (`apres_jeu.BOSS_BIT_NON_PROUVE`) : état « fragile »
NOTE_INFINIRIS = "les six combattants de la rencontre n'ont pas de n° : bit du n° 446 non prouvé [S]"

# ---------------------------------------------------------------------------
# Voies des n° qui n'ont PAS de location « Ami » / « Boss » par n° dans le plan
# ---------------------------------------------------------------------------
# Champs : `classe` ; `etat` ; `region` : région d'après-jeu (clé d'`apres_jeu.REGIONS`) ou None = le monde d'avant la
# fin, entièrement ouvert ; `objets` : objets exigés en plus ; `quete` : requête d'avant la fin dont la règle
# s'ajoute (`logique.QUETES` ou `apres_jeu.QUETES_TRANSFERT`) ; `quete_aj` : requête d'après-jeu (`apres_jeu.QUETES`) ;
# `rang_s` ; `bases` : n° des Yo-kai sources (fusion) ; `note`.
VOIES: Dict[int, dict] = {}


def _v(n, classe, etat, region=None, objets=(), quete=None, quete_aj=None, rang_s=False, bases=(), note="",
       regions=(), objets_si_presents=(), table=None):
    """`regions` (lot 21) : régions d'après-jeu exigées EN PLUS de `region` ; `objets_si_presents` : objets exigés
    seulement quand la logique de la graine peut les exiger (objets à verrou actif et mélangés : sinon le jeu les donne
    lui-même au moment où l'histoire en a besoin)."""
    table = VOIES if table is None else table
    if n in table:
        raise ValueError(f"n° {n} en double")
    table[n] = {"classe": classe, "etat": etat, "region": region, "objets": tuple(objets), "quete": quete,
                "quete_aj": quete_aj, "rang_s": bool(rang_s), "bases": tuple(bases), "note": note,
                "regions": tuple(regions), "objets_si_presents": tuple(objets_si_presents)}


# -- combats répétables d'avant la fin (amitié au taux du jeu) ---------------------------------------------------
_v(13, "combat", HASARD, note="Fouétar : combats de la Terr'heure ; clé d'amitié 1024 (la plus basse du jeu)")
_v(23, "combat", FRAGILE, note="Coach Antonic : toit de l'école, combat du jour (octet du jour 601 : limite d'un par "
                               "jour réel non relue)")
_v(55, "spot", HASARD, note="Mémétal : spot à combat (un combat par jour par spot [S])")
_v(97, "spot", HASARD, note="Frérosse : spot à combat ; aussi au Crank-a-kai")
_v(169, "spot", HASARD, note="Grainpère : spot à combat ; aussi au Crank-a-kai et dans un train")
_v(272, "spot", HASARD, note="Ornella : spot à combat, errante de carte ; aussi au Crank-a-kai")
_v(187, "combat", HASARD, quete=41, note="Donchan : revanche après la requête 41 (limite du jour levée : fonction 44)")
_v(235, "combat", HASARD, note="Hennimi : PNJ sans condition (limite du jour levée par le patch)")
_v(242, "combat", HASARD, note="Maltesse : égouts (limite du jour levée par le patch)")
_v(261, "combat", HASARD, note="Cerbébert : six rencontres communes, sans limite")
_v(430, "combat", HASARD, note="Narinos : déclencheurs communs, avant la fin [S]")
# -- Tunnel sans fin (taux du jeu : décision de l'humain) --------------------------------------------------------
_v(65, "tunnel", HASARD, note="Dynamo : évènement du Tunnel sans fin (0,43 % par bloc au-delà de 101), clé 256 ; "
                              "aussi au Bingo-kai gagnant de l'Entrain Express (tirage dirigé, après Cho-cho ; "
                              "train au hasard : 1 passage sur 5)")
_v(116, "tunnel", HASARD, note="Corniaque : évènement du Tunnel sans fin (0,28 % par bloc au-delà de 201), clé 512")
_v(132, "tunnel", HASARD, note="Cho-cho : évènement du Tunnel sans fin (0,28 % par bloc au-delà de 201), clé 512 ; "
                               "aussi au Bingo-kai gagnant de l'Entrain Express (tirage dirigé, le premier ; train "
                               "au hasard : 1 passage sur 5)")
# -- dons de script --------------------------------------------------------------------------------------------
_v(274, "don", HASARD, quete=80, note="Crocho : don de la requête 80 (qui exige le Yo-kai du Tablo-blabla n° 8)")
_v(168, "fusion_objet", FRAGILE, quete=100, bases=(167,),
   note="Puissanfon : objet au CHOIX de la requête 100 (un parmi trois) ; sinon récompense du jeu musical (tirage)")
_v(117, "don", GARANTIE, quete=114, objets=("invitation_parantonn",),
   note="Robonyan : don de la requête à transfert 114 (exige Parantonn, invité de l'Auberge)")
# -- fusions à objet du pool (les 9 objets de fusion tirés au sort) ------------------------------------------------
_v(28, "fusion_objet", HASARD, objets=("epee_legendaire",), bases=(27,))
_v(29, "fusion_objet", HASARD, objets=("epee_maudite",), bases=(27,))
_v(30, "fusion_objet", HASARD, objets=("epee_sacree",), bases=(27,))
_v(64, "fusion_objet", HASARD, objets=("orbe_ghz",), bases=(63,))
_v(131, "fusion_objet", HASARD, objets=("cape_de_blizzard",), bases=(130,))
_v(173, "fusion_objet", HASARD, objets=("costume_sable",), bases=(172,))
_v(278, "fusion_objet", HASARD, objets=("poudre_jouvence",), bases=(277,))
_v(237, "fusion_objet", HASARD, region="yokai_world", objets=("eclat_demoniaque",), bases=(236,))
_v(273, "fusion_objet", HASARD, objets=("revue_maudite",), bases=(272,))
# -- fusions à objet de boutique « rang >= S » (boutique d'échange à points, N016, N035) ---------------------------
for _n, _base in ((36, 35), (113, 112), (115, 114), (156, 155), (304, 303), (186, 185), (301, 300)):
    _v(_n, "fusion_objet", HASARD, region="rang_s", rang_s=True, bases=(_base,),
       note="objet vendu sous la condition « rang >= S » (boutique d'échange à points, ou boutique en euros)")
# -- combats de requêtes d'après-jeu (rejouables : limites du jour levées, fonctions 43 / 44 et patch de la V2) ----
_v(21, "combat", HASARD, quete_aj=73, note="Âmiral : revanche après la requête 73")
_v(38, "combat", HASARD, quete_aj=23, note="Démophage : combat de la requête 23, rejoué jusqu'à l'amitié")
_v(160, "combat", HASARD, quete_aj=24, note="Maître Nyada : combat de la requête 24, rejoué jusqu'à l'amitié")
_v(120, "combat", HASARD, quete_aj=84, note="Ressak : revanche après la requête 84 (heure du jeu [S])")
_v(353, "combat", HASARD, quete_aj=120, note="Jibakoma : revanche après la requête 120 (Paquet spirituel)")
for _n, _q in ((355, 91), (356, 92), (357, 93), (358, 94), (359, 95)):
    _v(_n, "combat", HASARD, quete_aj=_q, note="combat de la requête des origines, rejoué jusqu'à l'amitié")
_v(352, "combat", HASARD, quete_aj=124, objets=(OBJET_GRELOT_GRIS,),
   note="Darknyan : revanche du PNJ après la requête 124, avec le Grelot gris")
_v(121, "don", HASARD, quete_aj=115, note="Crapop : don de la requête à transfert 115 (objet = butin au hasard)")
_v(282, "don", HASARD, quete_aj=110, note="Arachnus : don de la requête à transfert 110 (objet = butin au hasard)")
_v(436, "combat", HASARD, region="limbes_eternelles", quete_aj=119, note="Obskyurbi : PNJ après la requête 119")
_v(437, "combat", HASARD, region="entrain_express",
   note="Luminoct : PNJ de l'Entrain Express (train tiré au sort : 10 % par entrée en gare)")
# -- Voie du mystère -----------------------------------------------------------------------------------------------
_v(438, "don", HASARD, region="route_des_farceurs", note="Gargaros ami : don à 5 % par victoire sur l'Oni du lieu")
_v(439, "don", HASARD, region="route_des_bouffis", note="Ogralos ami : don à 5 % par victoire sur l'Oni du lieu")
_v(440, "don", HASARD, region="grand_route_doree", note="Orqanos ami : don à 3 % par victoire sur l'Oni du lieu")
for _n in range(360, 370):
    _v(_n, "vaincre", FRAGILE, region="voie_du_mystere",
       note="Yo-kai maléfique errant de la ligne principale de la Voie (à Vieux Granval : chapitre 10 seulement) ; "
            "bit posé à la victoire [S fort : jamais vu en jeu]")
_v(423, "vaincre", GARANTIE, region="voie_du_mystere", note="Blingos : boss de la ligne principale")
_v(426, "vaincre", GARANTIE, region="route_des_farceurs", note="Cycloptique : boss de la Route des farceurs")
_v(425, "vaincre", GARANTIE, region="route_des_bouffis", note="Maximain : boss de la Route des bouffis")
_v(424, "vaincre", GARANTIE, region="grand_route_doree", note="Bogos : boss de la Grand-route dorée")
# -- autres boss sans location par n° ------------------------------------------------------------------------------
_v(396, "vaincre", GARANTIE, quete=108, note="Triptyk : premier combat de la requête à transfert 108 (ou gymnase)")
_v(400, "vaincre", FRAGILE, quete=113,
   note="Carpitaine : premier combat de la requête à transfert 113 (appât : source non relue), ou gymnase")
_v(410, "vaincre", FRAGILE, region="yokai_world",
   note="McKraken (seconde forme) : seulement au gymnase du Centre-ville, après le Tablo-blabla n° 24 [gymnase "
        "jamais essayé en jeu]")
for _n in (427, 428, 429):
    _v(_n, "vaincre", FRAGILE, region="apres_jeu",
       note="Oni : Terr'heure (défaite attendue), ou gymnase après la fin [gymnase jamais essayé en jeu]")
# -- mode Blasters (les bits sont posés à la première victoire, sans donner le Yo-kai) -----------------------------
_v(441, "blasters", HASARD, objets=("invitation_jibanyan_s",),
   note="Jiganyan : terrain 11 de Ψ Blasters (6 000 orbes au total, rencontre de Jibanyan S) ; solo non essayé")
_v(442, "blasters", HASARD, objets=("invitation_komasan_s",),
   note="Komak : terrain 12 de Ψ Blasters (6 000 orbes au total, rencontre de Komasan S) ; solo non essayé")
# Domniscian (lot 21, décision de l'humain du 2026-10-13) : son terrain exige les terrains 1 à 10 ; le 3 demande 30
# Yo-kai pris en photo avec l'appareil de la console (infaisable sur émulateur) : le jeu modifié tient ces photos pour
# prises (option étendue 33, posée par le client pour cet objectif : `slot_data.photos_blasters`). Restent les
# conditions des autres terrains : 4 000 orbes au total, 30 créatures différentes (terrain 4 : Canne à pêche et
# Filet), 30 Gargaros vaincus (terrain 7), la requête 96 finie (terrain 9 : Château de Sawayama) et Potofeu vaincu
# (terrain 10 : Limbes éternelles). Très long : « hasard ».
_v(443, "blasters", HASARD, regions=("chateau_de_sawayama", "limbes_eternelles"),
   objets_si_presents=("canne_a_peche", "filet_a_insectes"),
   note="Domniscian : terrain 13 de Ψ Blasters (terrains 1 à 10 finis : 4 000 orbes au total, 30 créatures, 30 "
        "Gargaros, requête du Château de Sawayama, Potofeu) ; les 30 photos du terrain 3 sont tenues pour prises par "
        "le jeu modifié ; très long, solo non essayé")
# -- graine d'AVANT le lot 21 (tracker du lanceur : pas de fonction 47 dans ses `fonctions_exigees`) : les deux voies
# que ce lot a décidées gardent leur état d'alors (n° non comptés par la logique)
VOIES_AVANT_LOT21: Dict[int, dict] = {}
_v(443, "blasters", SANS_VOIE, table=VOIES_AVANT_LOT21,
   note="Domniscian : terrain 13 de Ψ Blasters, qui exige les terrains 1 à 10, dont le 3 (30 Yo-kai pris en photo "
        "avec l'appareil de la console)")
# Bananar (314) : depuis le lot 21, location « Ami : Bananar » de l'option `pieces_speciales` (une Pièce bleu ciel au
# pool, tirage dirigé : voie « piece », garantie) : plus dans cette table.
_v(314, "piece", ATTENTE, table=VOIES_AVANT_LOT21,
   note="Bananar : Pièce bleu ciel du Crank-a-kai du passé seulement (3 % ; aucune voie décidée)")
# Les 16 de Pièce 5 étoiles : avec l'option `pieces_speciales` (forcée par cet objectif : lot 20), 16 Pièces 5 étoiles
# au pool et une location « Ami » chacun (voie « piece », garantie) ; sans elle (indicateur fermé), pièce seulement
# (13 aussi au Tunnel sans fin) : « attente ».
PIECE_5_ETOILES: Tuple[int, ...] = (37, 39, 81, 83, 118, 122, 157, 159, 199, 201, 238, 240, 279, 283, 305, 321)
NOTE_5_ETOILES = "Pièce 5 étoiles du Crank-a-kai (4 % par tirage) : sans voie garantie hors de l'option « pieces_speciales »"

# ---------------------------------------------------------------------------
# Lot « pièces spéciales » (côté jeu : lot 19 ; APWorld, client, lanceur : lot 20, `pieces.py` ; décisions de l'humain
# du 2026-10-12 / 13, `docs/systemes/archipelago_v3_pieces_speciales.md` §13). OUVERT : cet objectif FORCE l'option
# `pieces_speciales` (qui force `bingo_kai_infini`). Voies :
# - les 16 de Pièce 5 étoiles : 16 Pièces 5 étoiles au pool, n'importe quelle machine ordinaire donne le premier
#   manquant de l'ordre de sortie de la graine ; jamais des invités de l'Auberge (`invites_5_etoiles` est retirée) ;
#   Gorgouille (324) et Slurpent (329), dont ils sont le sceau, sont comptés avec eux ;
# - les 4 « frisson » (59, 68, 233, 228) : 4 Pièces frisson (fleur) ; les 9 régionaux (370, 372, …, 386) : leur pièce ;
#   les 9 fusions régionales (371, 373, …, 387) : leur objet de fusion ; ces 22 quittent l'Auberge ;
# - Pile ou passe / Super pile ou passe (95, 259, 53 ; 142, 285, 138) : 3 + 3 pièces ; ils quittent l'Auberge ;
# - Cho-cho (132) et Dynamo (65) : machine du train d'or (Entrain Express) dirigée par le jeu, mais train au hasard :
#   ils gardent la voie « tunnel » (hasard, « longs ») ; Corniaque (116) reste au Tunnel ;
# - le taux d'amitié relevé de l'Auberge est abandonné.
# L'indicateur reste (fermé : l'objectif ne force pas l'option, les 16 restent « en attente ») pour les tests.
# ---------------------------------------------------------------------------
PIECES_SPECIALES_DISPONIBLE = True
NOTE_PIECES_SPECIALES = "garantie par l'option « pieces_speciales » : pièce du pool, tirage dirigé, pièce rendue"
# (nom du lot 18, gardé : les familles, par clé)
PIECES_SPECIALES_A_VENIR: Dict[str, Tuple[int, ...]] = {
    "piece_5_etoiles": PIECE_5_ETOILES,
    "piece_frisson": (59, 68, 228, 233),
    "piece_regionale": (370, 372, 374, 376, 378, 380, 382, 384, 386),
    "fusion_regionale": (371, 373, 375, 377, 379, 381, 383, 385, 387),
    "pile_ou_passe": (53, 95, 259),
    "super_pile_ou_passe": (138, 142, 285),
    "train_d_or": (65, 132),
}

# Classes des voies (toutes sources : table ci-dessus et locations du plan)
CLASSES = ("sauvage", "sauvage_apres_jeu", "evolution", "fusion", "fusion_objet", "histoire", "requete", "don",
           "evenement", "place", "invite", "legendaire", "transfert", "machine_voie", "combat", "spot", "tunnel",
           "vaincre", "blasters", "piece")
# Sceaux des légendaires (n° du légendaire -> n° des huit membres) : pour l'outil d'inventaire (comparé à la ROM)
SCEAUX: Dict[int, Tuple[int, ...]] = {
    322: (69, 300, 265, 135, 146, 256, 127, 280),
    323: (12, 16, 24, 106, 109, 132, 295, 299),
    324: (37, 81, 118, 157, 199, 279, 238, 321),
    325: (160, 303, 158, 174, 185, 70, 62, 38),
    326: (171, 180, 187, 268, 184, 65, 166, 119),
    327: (13, 102, 307, 80, 169, 270, 320, 165),
    328: (260, 10, 96, 151, 54, 57, 258, 188),
    329: (39, 83, 122, 159, 201, 240, 283, 305),
}


def seuil_valide(seuil) -> int:
    s = SEUIL_PAR_DEFAUT if seuil is None else int(seuil)
    if not 1 <= s <= TOTAL:
        raise ValueError(f"seuil du Médaillium hors de 1..{TOTAL} : {seuil!r}")
    return s
