# -*- coding: utf-8 -*-
"""
Carte mémoire de Yo-kai Watch 2 : Spectres Psychiques (EU, 00040000001B2900).

C'EST ICI que la rétro-ingénierie s'enregistre. Tant que les adresses valent
0, le client fonctionne en mode « texte » (checks manuels) ; dès qu'une
région est renseignée, le client lit la mémoire via le stub GDB
d'Azahar/Citra et envoie les checks automatiquement.

Comment trouver les adresses : voir docs/memory_map_fr.md (méthode complète
avec tools/memory_scan.py). Résumé : instantané -> action en jeu (ouvrir un
coffre) -> instantané -> `diff a b 1` -> recouper avec un 2e coffre.

Les adresses sont des adresses VIRTUELLES du processus 3DS (la FCRAM
APPLICATION est mappée autour de 0x08000000).
"""

import json
import pkgutil
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Régions mémoire à surveiller : nom -> (adresse, taille en octets).
# Une adresse à 0 signifie « pas encore trouvée ».
#
# Adresses trouvées par rétro-ingénierie (Azahar/Citra, EU 00040000001B2900,
# heap APPLICATION). Confirmées STABLES entre deux redémarrages de
# l'émulateur. Voir docs/memory_map_fr.md et tools/memory_scan.py.
#   money       0x086CBBE0  u32, argent en centimes (6164,19 € = 616419)
#   chest_flags 0x086CFE00  bitfield ; chaque coffre = 1 bit fixe (par ID).
#               Les DEUX types de coffres (violets ET jaunes) partagent ce
#               même bitfield ; ils sont donc indexés ensemble par ID global.
#               Vérifié : violets -> bits 5,4,7 de 0x086CFE75 ;
#                         jaune   -> bit 2 de 0x086CFE74 (octet adjacent).
# ---------------------------------------------------------------------------
MEMORY_REGIONS: Dict[str, Tuple[int, int]] = {
    "chest_flags": (0x086CFE00, 0x200),   # coffres violets + jaunes (vérifié)
    "quest_flags": (0x0, 0x40),           # requêtes/services terminés (à RE)
    # Médallium « enregistré » (bit = N° du Yo-kai). VÉRIFIÉ cette session :
    # base 0x086CFEBC, boss d'histoire N388-395 (cf. MEDALLIUM_BIT_TO_LOCATION).
    # Le bit se met à la RENCONTRE du boss (biographie) ; OK pour des boss
    # d'histoire obligatoires. Seuls les bits mappés (boss) déclenchent un check ;
    # les milliers d'autres Yo-kai amis restent sans location (no-op).
    "medallium_flags": (0x086CFEBC, 0x80),
    "tablo_flags": (0x086CFB1C, 0x100),   # Tablo-blabla résolus (bits mappés seulement)
    "money": (0x086CBBE0, 0x4),           # argent du joueur (u32, centimes)
    "inventory": (0x086CC640, 0x400),     # sac d'objets (voir INVENTORY_* ci-dessous)
}

# ---------------------------------------------------------------------------
# Inventaire (sac d'objets) — VÉRIFIÉ par RE (lecture + écriture testées).
# ATTENTION : l'entrée à l'OFFSET 0 est un EN-TÊTE RÉSERVÉ (slot=0, type=0x0102,
# champ « hash » = un pointeur RAM ~0x086ce12c, qté=0, ptr=0x007FD398) — ce n'est
# JAMAIS un objet. Les vrais objets commencent à l'offset 0x10 (slots 0..N). D'où
# le `off != 0` dans le scan client. count = nb d'objets HORS en-tête ; count2
# (+4) = count+1 ; slotbits = 1 bit/objet (5 objets -> 0x1f). Confirmé au scanner
# 2026-07-15. Livraison sur inventaire VIDE = créer la 1re entrée à 0x10 (slot 0)
# en chaînant depuis l'en-tête (offset 0) ; recette validée en jeu (objet-test).
# Tableau d'entrées de 16 octets à partir de INVENTORY_BASE :
#   0x00 u16  slot (index)
#   0x02 u16  type / ordre d'affichage
#   0x04 u32  hash CRC32 du nom interne de l'objet (= clé de l'objet)
#   0x08 u32  quantité
#   0x0C u32  pointeur (constant 0x007FD398 = struct de définition en RAM)
# Écrire à +0x08 change la quantité en jeu (testé : Mini EXPorbe 0x8D447F63).
#
# RECETTE COMPLÈTE DE LIVRAISON (VÉRIFIÉE en jeu, 2026-07-10) :
#  * Objet DÉJÀ possédé -> incrémenter sa quantité (+0x08). Simple et sûr.
#  * Objet ABSENT -> créer une entrée, en 4 étapes (sinon CRASH à l'ouverture
#    du menu si une étape manque, notamment le bitfield des slots) :
#      1. chaîner l'ancienne DERNIÈRE entrée : son ptr (+0x0C) 0 -> 0x007FD398 ;
#      2. écrire la nouvelle entrée à la fin :
#         [slot=N u16][type u16][hash1 u32][qté u32][ptr=0 u32] ;
#      3. incrémenter les compteurs INVENTORY_COUNT (0x086CC580) ET son voisin
#         0x086CC584 (= count+1) ;
#      4. poser le bit N dans INVENTORY_SLOT_BITS (0x086CE154), 1 bit par slot
#         occupé (6 objets = 0x3F ; le 7e slot -> bit 6 -> 0x7F).
#    ⚠️ CORRECTION (RE 2026-07-27, dump des 69 entrées d'une vraie save) : le
#    champ à l'offset 0x02 n'est PAS la catégorie d'onglet mais un INDEX
#    D'AFFICHAGE unique. Preuve : il ne corrèle pas avec la catégorie
#    item_config — les objets de catégorie 20 ont les valeurs 5, 9, 11, 12, 13,
#    15, 21, 22... ; ses valeurs vont de 2 à 69 pour 69 entrées (≈ une
#    permutation d'index). L'ancienne lecture « nourriture=7, EXPorbe=5 » venait
#    de coïncidences sur les premières entrées.
#    -> Pour créer une entrée à la main : mettre max(index existants)+1.
#    VALIDÉ EN JEU (Doteos 2026-07-27) : Globe de portail x99 écrit avec
#    index 70 (69 entrées) -> visible et utilisable en jeu.
#    NB : items.ITEM_GAME_TYPE (5/7/10) écrit donc une valeur qui n'a pas le sens
#    supposé. Les livraisons fonctionnent quand même, mais c'est une piste
#    sérieuse pour le bug historique des « pièces invisibles » (jamais reconfirmé).
# ---------------------------------------------------------------------------
INVENTORY_BASE = 0x086CC640
INVENTORY_ENTRY_SIZE = 0x10
INVENTORY_QTY_OFFSET = 0x08
INVENTORY_HASH_OFFSET = 0x04
INVENTORY_PTR_OFFSET = 0x0C
INVENTORY_PTR_VALUE = 0x007FD398        # ptr « entrée suivante existe »
INVENTORY_COUNT_ADDR = 0x086CC580       # nombre d'entrées (u32) ; voisin +4 = count+1
INVENTORY_SLOT_BITS = 0x086CE154        # bitfield : 1 bit par slot occupé
INVENTORY_ENTRY_PTR = 0x007FD398

# ---------------------------------------------------------------------------
# Objets-clés / outils (montre, filet, vélo, clés...) — VÉRIFIÉ (RE + livraison
# testée en jeu, 2026-07-11). Liste séparée de l'inventaire, entrées de
# 12 octets à partir de KEY_ITEM_BASE :
#   0x00 u32  pointeur (constant 0x007FD860 = struct de définition ; marqueur
#             « entrée occupée », identique pour toutes les entrées)
#   0x04 u32  data = (ordre_acquisition << 16) | 0x2000 | index_de_position
#             mot BAS = 0x2000 + index (position dans la liste) ; mot HAUT =
#             ordre d'acquisition (compteur global d'objets-clés jamais obtenus,
#             PAS une catégorie : le Médallium vaut 5 sur une save et 3 sur une
#             autre — prouvé sur 2 saves 2026-07-11). Livraison = max(haut)+1.
#   0x08 u32  hash CRC32 du nom interne de l'objet
# Un objet-clé possédé = son hash présent ici. Hash connus : Filet à insectes
# 0x4806448E, Yo-kai Watch 0x4F6B8097, Médallium 0xA165E1BB, Canne à pêche
# 0xD10F1534, Clé de cabane 0xE454B3AF.
#
# RECETTE COMPLÈTE DE LIVRAISON (VÉRIFIÉE en jeu, 2026-07-11 : Canne à pêche +
# Clé de cabane ajoutées sans crash ; la Clé de cabane est FONCTIONNELLE, Doteos
# a pu l'utiliser => pour une clé, l'avoir dans la liste suffit). Comme
# l'inventaire mais avec SON PROPRE bitfield, à une adresse séparée (pointée en
# double par le descripteur 0x086CC5D4/0x086CC5E4) :
#      1. écrire la nouvelle entrée à KEY_ITEM_BASE + index*0x0C :
#         [ptr=0x007FD860][data=((max_haut+1)<<16)|0x2000|index][hash] ;
#      2. incrémenter le compteur KEY_ITEM_COUNT (0x086CC5D8) ;
#      3. incrémenter son voisin KEY_ITEM_COUNT2 (0x086CC5DC = count+1) ;
#      4. poser le bit `index` dans le bitfield KEY_ITEM_SLOT_BITS (0x086CF1B0)
#         — 3 objets = 0x07, le 4e -> bit 3 -> 0x0F. SANS ce bit : CRASH à
#         l'ouverture du menu objets-clés (comme l'inventaire).
# Descripteur du conteneur à 0x086CC5D0 : [ptr entrées 0x086CE918][ptr bitfield
# 0x086CF1B0][count][count+1][taille<<16|capacité = 0x000C00B4]...
# ---------------------------------------------------------------------------
KEY_ITEM_LIST = (0x086CE900, 0x100)     # zone à scanner (début approx.)
KEY_ITEM_BASE = 0x086CE918              # 1re entrée (index 0)
KEY_ITEM_ENTRY_SIZE = 0x0C
KEY_ITEM_DATA_OFFSET = 0x04
KEY_ITEM_HASH_OFFSET = 0x08
KEY_ITEM_PTR_VALUE = 0x007FD860         # ptr constant « entrée occupée »
KEY_ITEM_COUNT_ADDR = 0x086CC5D8        # vrai compteur d'objets-clés (u32)
KEY_ITEM_COUNT2_ADDR = 0x086CC5DC       # voisin = count+1
KEY_ITEM_SLOT_BITS = 0x086CF1B0         # bitfield : 1 bit par slot occupé
KEY_ITEM_DATA_MARK = 0x2000             # base du mot bas de `data`

# ---------------------------------------------------------------------------
# Progression de l'histoire — VÉRIFIÉ (RE en jouant : 1->2->3 aux transitions
# de chapitre). u16 = numéro du chapitre en cours. Le chapitre N est terminé
# quand cette valeur atteint N+1 => check « Chapitre N » quand STORY_CHAPTER
# passe à N+1. Un seul mot à lire pour tous les checks d'histoire.
# ---------------------------------------------------------------------------
STORY_CHAPTER_ADDR = 0x086CFA24     # u16, numéro de chapitre courant

# HARD-GATES DE ZONE (progression scénario) — relevé au scanner (2026-07-20).
# Certaines zones sont gatées par un "pas de scénario" (u16) juste après le
# chapitre. Tant que l'objet-clé AP correspondant n'est pas REÇU, le client
# maintient le pas à `locked` (le jeu le repasse à `unlocked` quand le joueur fait
# l'événement en jeu -> on revert => la zone reste verrouillée). À la réception ->
# on laisse le jeu débloquer. On ne touche QUE la valeur `unlocked` exacte (jamais
# une autre valeur de scénario) pour ne pas casser d'autres beats.
#   École (Collège de Granval) : 0x086CFA26 + miroir 0x086CFA2A ; 0x1E=verrouillé
#   (objectif « récupérer les clés » réaffiché), 0x28=débloqué. Objet = Clés de l'école.
# Deux TYPES de gate (RE au scanner 2026-07-20) :
#  * kind="u16"  : un PAS DE SCÉNARIO (u16). Tant que l'objet AP n'est pas reçu, on
#    remet `locked` dès que la valeur vaut EXACTEMENT `unlocked` (le jeu l'y met quand
#    le joueur fait l'événement) -> la zone reste verrouillée.
#  * kind="bits" : un ou plusieurs BITS de CAPACITÉ/EVENT (région 0x086CFAB6-0x086CFAEA).
#    Tant que l'objet AP n'est pas reçu, on EFFACE ces bits (&~masque) ; à la réception
#    on les POSE (|masque). Bits relevés en jeu, blocage vérifié pour chacun.
#    ⚠️ Toujours lire-modifier-écrire (préserver les autres bits de l'octet).
STORY_GATES: Tuple[dict, ...] = (
    # --- gate par PAS DE SCÉNARIO -------------------------------------------------
    {"item": "Clés de l'école", "kind": "u16",
     "addrs": (0x086CFA26, 0x086CFA2A),
     "trigger": (0x086CFFF9, 0x20),           # b5 : event école fait
     "locked": 0x001E, "unlocked": 0x0028},
    # --- gates par BIT(S) ---------------------------------------------------------
    # 0x086CFAB7 = registre des CAPACITÉS D'OUTIL
    # FILET : gate CONDITIONNEL (Doteos 2026-07-25). C'est le 1er objet du tuto ; le
    # jeu pose lui-même la capacité 0x086CFAB7 b4 quand on « parle au perso après le
    # filet ». Un hard-gate classique cassait le tuto (bit posé/effacé trop tôt).
    # Règle exacte de Doteos : tant que le MARQUEUR « parlé au perso » (0x086CFFCA b1)
    # est OFF, on ne touche à RIEN (le tuto se fait nativement). Dès qu'il passe ON,
    # ALORS on gate : item AP reçu -> on laisse (le jeu a posé le bit) ; pas reçu ->
    # on reverrouille (efface b4). Item reçu APRÈS avoir parlé -> marqueur déjà ON +
    # reçu -> on repose b4 (déverrouille). "trigger" = déclencheur du latch.
    {"item": "Filet à insectes", "kind": "bits",
     "trigger": (0x086CFFCA, 0x02),           # b1 : marqueur « parlé au perso »
     "bits": ((0x086CFAB7, 0x10),)},          # b4 : capacité filet à insectes
    # ⚠️ Tous ces gates à bit portent un "trigger" = marqueur de l'EVENT NATIF fait
    # (Doteos 2026-07-25). Tant que le marqueur est OFF, le client NE TOUCHE À RIEN
    # (le tuto/scénario se déroule nativement, le jeu pose lui-même la capacité). Dès
    # que le marqueur passe ON, on gate : reçu -> on pose/laisse le bit ; pas reçu ->
    # on efface (reverrouille). Un item reçu AVANT l'event ne pose donc plus le bit
    # prématurément ; il se posera quand le joueur fera l'event.
    {"item": "Canne à pêche", "kind": "bits",
     "trigger": (0x086CFFF8, 0x01),           # b0 : event canne fait
     "bits": ((0x086CFAB7, 0x20),)},          # b5 : pêcher
    {"item": "Herbe ancestrale", "kind": "bits",
     "trigger": (0x086CFFF9, 0x01),           # b0 : event herbe fait
     "bits": ((0x086CFACB, 0x40),)},          # b6 : cinématique du magasin
    {"item": "Super tournevis", "kind": "bits",
     "trigger": (0x086CFFF9, 0x02),           # b1 : event tournevis fait
     "bits": ((0x086CFACC, 0x02),)},          # b1 : cinématique du magasin
    {"item": "Indications de Maman", "kind": "bits",
     "trigger": (0x086CFFF9, 0x10),           # b4 : event indications fait (marqueur)
     # ⚠️ L'event pose TROIS bits dans 0x086CFACF : b2+b3+b5 (0x2c) — RE au scanner
     # avant/après (Doteos 2026-07-26 : 0x01 -> 0x2d). L'accès gare/Centre-ville exige
     # les TROIS (vérifié : effacer les 3 + recharger la zone = bloqué ; en reposer
     # qu'un = insuffisant). Le jeu ré-évalue à l'entrée de zone. -> masque 0x2c.
     "bits": ((0x086CFACF, 0x2C),)},          # b2+b3+b5 : débloque Centre-ville + train
    # MODÈLE ZÉRO — gate réduit au SEUL bit utile (RE bit-à-bit Doteos 2026-07-27).
    # Comme le Vélo : bloque la CAPACITÉ (fonctions de combat de la montre) sans
    # gater aucune zone ni la progression de l'histoire.
    # L'event natif pose 4 zones de bits ; isolation en jeu (chaque bit effacé seul,
    # en boucle au scanner, pendant que Doteos jouait) :
    #   0x086CFAEA b6 (= WATCH_UPGRADE_FLAG « amélioration montre ») -> bloque RIEN
    #   0x086CFAD5 b6   -> bloque RIEN
    #   0x086CFABD b1+b2 -> bloque RIEN
    #   0x086CFAB6 b5   -> ⭐ SEUL bit qui bloque réellement la Modèle zéro
    # ⚠️ Effacer les 4 CASSAIT le scénario Ch6 (PNJ absent, marqueur de quête
    # pointant un endroit vide) — c'étaient les 3 bits INUTILES les coupables.
    # Effacer b5 SEUL : montre bloquée, histoire intacte (vérifié en rejouant
    # l'event). NB : pas de trigger latché (Modèle zéro n'a aucun marqueur d'event
    # propre, détection par compteur 0x086CFA26==0x14) mais b5 seul est inoffensif.
    {"item": "Modèle zéro", "kind": "bits",
     "bits": ((0x086CFAB6, 0x20),)},          # b5 : fonctions de combat de la montre
    # Vélo : capacité de rouler (comme la Modèle zéro, ne débloque aucune zone).
    # 2 noms possibles selon l'option progressive_bicycle -> "items" (liste).
    # PAS de "trigger" (décision Doteos 2026-07-29, comme la Modèle zéro) : le
    # vélo est une CAPACITÉ, elle doit être utilisable DÈS la réception de l'item
    # AP, sans attendre « Sur les traces de Papa ». Sans l'item, les bits restent
    # effacés en continu -> le vélo reste inutilisable même obtenu nativement.
    {"items": ("Vélo", "Vélo (progressif)"), "kind": "bits",
     # ⚠️ L'obtention native pose DEUX bits (RE Doteos 2026-07-29, diff
     # avant/après) : 0x086CFAB8 b7 ET 0x086CFAB9 b0. On ne gérait que le b0 ->
     # au déverrouillage il manquait le b7, ce qui explique très probablement le
     # vélo inutilisable signalé par Doteos (même bug que les Indications de
     # Maman). NB : le vélo est aussi un VRAI objet-clé écrit dans la liste
     # (livraison + neutralisation gérées côté client, cf. items.BICYCLE_HASHES).
     "bits": ((0x086CFAB8, 0x80), (0x086CFAB9, 0x01))},
)

# Checks détectés par un FLAG d'event (et non par l'objet). Indispensable pour les
# objets à EXEMPLAIRE UNIQUE : si le joueur reçoit l'objet AP avant d'atteindre le
# spot natif, le jeu ne peut pas en rajouter un 2e -> la détection par objet ne voit
# jamais de « natif non légitime » -> le check ne part JAMAIS (bug Pile ou passe /
# Clés de l'école signalé par Doteos). La détection par FLAG part dès que le joueur
# FAIT l'événement, indépendamment de l'objet. Deux formes :
#   * "mask" : octet & masque != 0 (bit posé)
#   * "u16"  : mot 16 bits == valeur exacte (pas de scénario)
# ⚠️ Ces flags sont LUS TÔT dans poll_game (avant que _enforce_story_gates ne
# reverrouille) -> on capte bien la valeur « débloqué » que le jeu vient de poser.
EVENT_CHECK_FLAGS: Tuple[dict, ...] = (
    # Objets-clés hard-gatés : le check part sur le flag de l'event, pas l'objet.
    # École : marqueur d'event 0x086CFFF9 b5 (RE 2026-07-23) au lieu du compteur
    # u16 0x086CFA26==0x28 (qui REPASSAIT par 0x28 à d'autres events = faux positif).
    {"location": "Objet-clé : Clés de l'école", "addr": 0x086CFFF9, "mask": 0x20},
    # Herbe : marqueur d'event 0x086CFFF9 b0 (RE 2026-07-24) au lieu du bit capacité
    # 0x086CFACB b6 (posé par le client à la livraison -> check partait trop tôt).
    {"location": "Objet-clé : Herbe ancestrale", "addr": 0x086CFFF9, "mask": 0x01},
    # Tournevis : marqueur d'event 0x086CFFF9 b1 (RE 2026-07-24) au lieu du bit
    # capacité 0x086CFACC b1 (posé par le client à la livraison -> trop tôt).
    {"location": "Objet-clé : Super tournevis", "addr": 0x086CFFF9, "mask": 0x02},
    # Indications de Maman : marqueur d'event 0x086CFFF9 b4 (RE 2026-07-24) au lieu
    # du bit capacité 0x086CFACF (posé par le client -> trop tôt ; en plus l'event
    # pose b3, pas b4 = l'ancien masque était douteux).
    {"location": "Objet-clé : Indications de Maman", "addr": 0x086CFFF9, "mask": 0x10},
    # Canne : marqueur d'event 0x086CFFF8 b0 (RE 2026-07-24) au lieu du bit capacité
    # 0x086CFAB7 b5 (posé par le client à la livraison -> trop tôt).
    {"location": "Objet-clé : Canne à pêche", "addr": 0x086CFFF8, "mask": 0x01},
    # Modèle zéro : PAS de marqueur propre (RE 2026-07-24 : l'event ne pose que ses
    # bits de GATE 0x086cfab6/abd/ad5/aea, que le client pose à la livraison, + le
    # compteur). On détecte donc par le compteur scénario 0x086CFA26 == 0x14 (le
    # client n'y touche pas). Check EXCLUDED = filler -> un éventuel faux positif du
    # compteur ne libère qu'un filler tôt (aucun soft-lock). À surveiller en test.
    # min_chapter=6 : le compteur de PAS 0x086CFA26 repasse par 0x14 à des chapitres
    # antérieurs (faux positif au chap 3 signalé par Doteos 2026-07-25). Modèle zéro
    # s'obtient au chapitre 6 -> on n'accepte le signal qu'à partir du compteur de
    # CHAPITRE (0x086CFA24) >= 6.
    {"location": "Objet-clé : Modèle zéro", "addr": 0x086CFA26, "u16": 0x0014,
     "min_chapter": 6},
    # Pile ou passe (item-gaté, mais son check souffrait de la même faille exemplaire-
    # unique). Flag = son bit MARQUEUR « obtenue » (0x086CFFFA b1) -> le check part à
    # l'obtention, indépendamment de l'objet AP. RE Doteos 2026-07-22.
    {"location": "Objet-clé : Pile ou passe", "addr": 0x086CFFFA, "mask": 0x02},
    # Vélo : marqueur d'event 0x086CFFF8 b5 (RE 2026-07-24, event « Sur les traces de
    # Papa » ; miroir 0x086D0048 b5 confirme) au lieu du bit capacité 0x086CFAB9 b0
    # (posé par le client à la livraison -> le check partait trop tôt).
    # ⚠️ CORRECTION (RE Doteos 2026-07-29, DEUX acquisitions comparées) : le
    # marqueur dépend du MODÈLE de vélo choisi par le joueur — « Vélo du vent »
    # pose 0x086CFFF8 b5, « Vélo du couchant » pose 0x086CFFFE b7. L'ancienne
    # détection sur 0x086CFFF8 b5 ne partait donc QUE si le joueur prenait ce
    # modèle-là (bug constaté : check jamais envoyé). Les SEULS bits communs aux
    # deux acquisitions sont 0x086D0128 b0 et 0x086D0129 b2 -> on détecte sur le
    # premier, indépendant du modèle.
    {"location": "Objet-clé : Vélo", "addr": 0x086D0128, "mask": 0x01},
    # Clé magnétique or : marqueur d'event 0x086D0006 b2 (RE 2026-07-24, diff ISOLÉ en
    # s'arrêtant AVANT la fin de « La base secrète » ; miroir 0x086D0056 b2 confirme).
    # Robuste (part à l'obtention, pas de faille exemplaire-unique).
    {"location": "Objet-clé : Clé magnétique or", "addr": 0x086D0006, "mask": 0x04},
    # Clé de derrière : marqueur d'event 0x086CFFF9 b6 (RE 2026-07-24, manoir « Chasse
    # nocturne » ; miroir 0x086D0049 b6 confirme). Robuste (pas de faille exemplaire-unique).
    {"location": "Objet-clé : Clé de derrière", "addr": 0x086CFFF9, "mask": 0x40},
    # Clé salle du trésor (au sol, tunnel abandonné) : marqueur 0x086D0007 b4 (RE
    # Doteos 2026-07-24, miroir 0x086D0057 b4 confirme). Hash 0x07AF7386.
    {"location": "Objet-clé : Clé salle du trésor", "addr": 0x086D0007, "mask": 0x10},
    # Poignée étrange (quête « La clinique hantée ») : marqueur d'event 0x086D0007 b6
    # (RE Doteos 2026-07-24, miroir 0x086D0057 b6). Hash 0xE0175E81.
    {"location": "Objet-clé : Poignée étrange", "addr": 0x086D0007, "mask": 0x40},
    # Boss Didgeai : bit MÉDALLIUM N°413 (base 0x086CFEBC + 413//8 = 0x086CFEEF,
    # bit 413%8 = b5) -> « Didgeai enregistré » = boss battu. Signal canonique et
    # unique (confirmé par la capture Doteos 2026-07-24 : N413 « NOUV.! » à la défaite ;
    # RE diff : 0x086cfeef 0x00->0x20). Boss non détectable autrement.
    # Boss Sabroclair : bit MÉDALLIUM N°404 (0x086CFEBC + 404//8 = 0x086CFEEE, bit
    # 404%8 = b4). Fin quête « Une armure sinistre » (Ch7). Doteos 2026-07-24.
    # Boss Ombraptor : bit MÉDALLIUM N°402 (0x086CFEBC + 402//8 = 0x086CFEEE, bit
    # 402%8 = b2). Fin quête « Le géant fantôme » (Ch10). Doteos 2026-07-24.
    # Boss Inamygal : bit MÉDALLIUM N°406 (0x086CFEBC + 406//8 = 0x086CFEEE, bit
    # 406%8 = b6). Fin quête « Ectoplasmes à l'école » (Ch6). Doteos 2026-07-24.
    # Boss Volteface : bit MÉDALLIUM N°412 (0x086CFEBC + 412//8 = 0x086CFEEF, bit
    # 412%8 = b4). Fin quête « Chasseurs de trésors 2 », exige Clé salle du trésor.
    # Misterre (Yo-kai amicable, fin « Chasseurs de trésors 3 ») : bit MÉDALLIUM N°119
    # (0x086CFEBC + 119//8 = 0x086CFECA, bit 119%8 = b7). Doteos 2026-07-24.
    # Boss Firmain : bit MÉDALLIUM N°415 (0x086CFEBC + 415//8 = 0x086CFEEF, bit 415%8
    # = b7). Fin quête « La clinique hantée » (Ch8). Doteos 2026-07-24.
    # Démophage : bit MÉDALLIUM N°38 (0x086CFEBC + 38//8 = 0x086CFEC0, bit 38%8 = b6 ;
    # RE Doteos 2026-07-25). Quête « Épreuves de Nyada VI » (Vieil Ourcival).
    # Injustin : bit MÉDALLIUM N°355 (0x086CFEBC + 355//8 = 0x086CFEE8, bit 355%8 = b3 ;
    # RE Doteos 2026-07-25). Ch9, Vieux Granval.
    # Fielippine : bit MÉDALLIUM N°356 (0x086CFEBC + 356//8 = 0x086CFEE8, bit 356%8 =
    # b4 ; RE Doteos 2026-07-25). Ch9, Vieux Granval.
    # Cyrustre : bit MÉDALLIUM N°357 (0x086CFEBC + 357//8 = 0x086CFEE8, bit 357%8 = b5 ;
    # RE Doteos 2026-07-25). Ch9, Vieux Granval.
    # Maudicko : MÉDALLIUM N°358 (0x086CFEE8 b6). Ch9, Vieux Granval. RE Doteos 2026-07-25.
    # Ronéan : MÉDALLIUM N°359 (0x086CFEE8 b7). Ch9, Vieux Granval. RE Doteos 2026-07-25.
    # Crocho : MÉDALLIUM N°398 (0x086CFEBC + 398//8 = 0x086CFEED, bit 398%8 = b6). Ch7,
    # quête « Les sources de l'amitié » (Coteau fleuri). Doteos 2026-07-25.
    # ⭐ Barbefrousse : MARQUEUR D'EVENT « vaincu » (RE Doteos 2026-07-28, diff
    # rencontre -> victoire) = 0x086CFFF1 b2, miroir 0x086D0041 b2 (même famille
    # que les marqueurs d'objets-clés 0x086CFFF7-FA / +0x50). Remplace le bit
    # MÉDALLIUM N°390 qui se posait dès la RENCONTRE (check envoyé en plein
    # combat, même en cas de DÉFAITE). Robuste : ne part qu'à la victoire.
    {"location": "Boss : Barbefrousse", "addr": 0x086CFFF1, "mask": 0x04},
    # ⭐ Laure + Marge : MÊME marqueur « vaincu » 0x086CFFF0 b0 (miroir 0x086D0040)
    # — RE Doteos 2026-07-28, diff avant/après le combat. Elles s'affrontent dans
    # le MÊME combat, d'où un flag unique et 2 checks simultanés. Le diff montrait
    # aussi 0x086CFFC9 b1, ÉCARTÉ car absent du diff Barbefrousse (= progression de
    # chapitre, pas un flag de boss). Le bloc 0x086CFFF0-F1 = flags de boss.
    {"location": "Boss : Laure", "addr": 0x086CFFF0, "mask": 0x01},
    {"location": "Boss : Marge", "addr": 0x086CFFF0, "mask": 0x01},
    # Tromplœil : MÉDALLIUM N°416 (0x086CFEBC + 416//8 = 0x086CFEF0, bit 416%8 = b0).
    # Boss de la Zone des portails (100 globes de portail). Doteos 2026-07-27.
    # Filet : check sur le bit MARQUEUR d'event 0x086CFFF7 b7 (RE 2026-07-23, diff
    # acquisition). PAS le bit de capacité 0x086CFAB7 b4 (celui-là est POSÉ par le
    # client à la livraison -> le check partait trop tôt). Le marqueur n'est posé que
    # quand on FAIT l'event -> le check part au bon moment, même si l'AP reçu avant.
    {"location": "Objet-clé : Filet à insectes", "addr": 0x086CFFF7, "mask": 0x80},
)

# ---------------------------------------------------------------------------
# Quêtes — MÉCANISME PRINCIPAL (détection en direct) : hash CRC32 de la
# dernière quête TERMINÉE, écrit à 0x086CBE74 (transitoire : écrasé à la quête
# suivante ; le client poll assez vite pour le capter). Le hash identifie la
# quête ; mapping hash -> nom FR complet dans data/quest_hashes.json (147
# quêtes, VÉRIFIÉ : Courage 0xBA90D102, Spécialiste des cigales 0x9516CE20,
# générés par tools/extract_quest_hashes.py). Récompense = objet(s) dans
# l'inventaire (voir data/quest_rewards.json).
#
# Le client, tant qu'il tourne pendant le jeu, envoie le check « Requête : <nom> »
# à chaque changement de cette valeur. C'est le cas d'usage standard AP.
# ---------------------------------------------------------------------------
LAST_QUEST_DONE_HASH_ADDR = 0x086CBE74
QUEST_DONE_COUNT_ADDR = 0x086CC5B0     # (candidat, non confirmé)

# Bitfield PERSISTANT des quêtes terminées — LOCALISÉ mais mapping incomplet.
# Des bits isolés (1/quête) vivent vers 0x086CFB60, mêlés à d'autres données
# de save. Bit VÉRIFIÉ : Spécialiste des cigales -> 0x086CFB66 bit5 (nouvelle
# partie, bit isolé, absent avant / présent après). Le mapping bit -> quête
# n'est PAS une formule simple (ni ID param[4], ni ordre de fichier, ni rang
# trié) ; à résoudre par data-mining (chantier, comme le bit->coffre). Utile
# seulement pour resynchroniser les quêtes faites client fermé.
QUEST_FLAGS_REGION = (0x086CFB60, 0x40)   # zone approx., mapping bit->quête TODO

# ---------------------------------------------------------------------------
# Boss / événements de scénario — bitfield d'ÉVÉNEMENTS confirmé à ~0x086D0100
# (dans le bloc de flags de save 0x086CF800-0x086D0800). Très creux : chaque
# événement majeur y allume un ou deux bits. Observé :
#   - Meganyan (combat spécial)          -> 0x086D0107 bit4, 0x086D010D bit1
#   - Fin chapitre 4 / boss Hovernyan     -> 0x086D010E bit2/bit4
# Le mapping bit -> événement précis reste à établir (data-mining flag_config
# + captures isolées). NOTE : les boss de FIN DE CHAPITRE (Hovernyan, etc.)
# sont déjà détectables via STORY_CHAPTER_ADDR (chapitre 4->5 reconfirmé) ; ce
# bitfield sert surtout aux boss/événements qui ne changent PAS le chapitre.
# Yo-criminels : 52 entrées dans wanted_config_EU (flag dédié à capturer sur un
# combat ISOLÉ ; c'est le meilleur test pour un flag de boss propre).
# ---------------------------------------------------------------------------
EVENT_FLAGS_REGION = (0x086D0100, 0x10)   # bitfield événements scénario (mapping TODO)

# Yo-criminels (Wanted) — bitfield dédié « Yo-criminel vaincu », VÉRIFIÉ :
# battre « Bushidouble » (combat isolé) a posé 0x086CFD9C bit0 (seul bit dans une
# région vierge ; absent des saves où aucun criminel n'a été battu). 52 cibles
# recensées dans wanted_config_EU. Le mapping bit -> Yo-criminel reste à établir
# (indexation par wanted_config ? à confirmer avec un 2e criminel ; noms via la
# table des Yo-kai). C'est le flag de boss « propre » qu'on cherchait.
WANTED_FLAGS_REGION = (0x086CFD90, 0x10)  # bitfield Yo-criminels (mapping TODO)
WANTED_BUSHIDOUBLE_FLAG = (0x086CFD9C, 0)  # (octet, bit) VÉRIFIÉ

# ---------------------------------------------------------------------------
# Rang de la Yo-kai Watch — flag « rang D atteint » à 0x086D5922 (dans un
# tableau de déblocages à 0x086D5918, 1 octet par flag). VÉRIFIÉ cohérent sur
# 3 saves : 0 quand rang E, 1 quand rang >= D. ATTENTION : l'AFFICHAGE du rang
# vient d'une copie runtime (pas de cet octet), donc écrire ici ne change pas
# le rang affiché à chaud (test fait) ; mais le flag de save reste fiable pour
# un check « rang D atteint ». Les paliers suivants (C, B, A, S) ont sans doute
# leur propre flag dans le même tableau, à capturer aux examens correspondants.
# ---------------------------------------------------------------------------
WATCH_RANK_D_FLAG_ADDR = 0x086D5922       # flag « rang D atteint » (u8, 0/1) — save (legacy)
WATCH_RANK_FLAGS_REGION = (0x086D5918, 0x20)  # tableau de flags de déblocage

# RANG DE MONTRE COURANT — VÉRIFIÉ cette session (aventure de zéro, 2026-07-14) :
# octet unique valant directement le rang (E=0, D=1, C=2, B=3, A=4, S=5).
# Confirmé EN DIRECT sur toute la chaîne D->C->B->A (upgrades observés). C'est la
# copie RUNTIME (celle qui pilote l'affichage), bien plus fiable que le flag save
# 0x086D5922 ci-dessus. Détection : lire cet octet ; chaque incrément -> check
# « Obtenons le rang X ! » (WATCH_RANK). Rangs par chapitre : D=Ch3, C=Ch6, B=Ch7,
# A=Ch9, S=post-game.
WATCH_RANK_VALUE_ADDR = 0x086D023A        # u8, rang courant (0=E .. 5=S)

# Fonctionnalités / améliorations de la Yo-kai Watch — cluster de flags de
# déblocage dans 0x086CFAE8-0x086CFAFA (bits individuels). VÉRIFIÉ : obtenir
# l'« amélioration de la montre » pose 0x086CFAEA bit6 (0->1, seul changement
# propre du cœur de save ; PAS un objet-clé : le compteur 0x086CC5DC reste
# identique et rien n'apparaît dans KEY_ITEM_LIST). Les changements observés au
# passage du rang D touchaient aussi cette zone (0x086CFAE9, 0x086CFAF9).
WATCH_UPGRADE_FLAG = (0x086CFAEA, 6)      # (octet, index de bit) amélioration montre
WATCH_FEATURE_FLAGS_REGION = (0x086CFAE8, 0x14)  # flags de fonctions de la montre

# ---------------------------------------------------------------------------
# DeathLink : état de combat + PV de l'équipe — VÉRIFIÉ par RE (2026-07-15,
# session live : 2 défaites, 1 combat normal, exploration).
#  * BATTLE_STATE_ADDR (u32) : 0 = exploration ; 6 = EN COMBAT, du lancement
#    jusqu'à l'écran « Perdu... » INCLUS (l'écran persiste jusqu'à l'appui ->
#    un poll à 2 s l'attrape toujours). Trouvé par triangulation de snapshots
#    (2 écrans Perdu = 6, respawn = 0).
#  * Roue d'équipe : 6 entrées de 0xE0 octets ; PV ACTUELS (u16) du slot i à
#    PARTY_HP_FIRST_ADDR + i*0xE0 ; PV max à +0x28 de chaque PV actuel.
#    Écrire les PV pilote le jeu (5 PV affichés au menu après write).
#  * DÉFAITE = état de combat == 6 ET somme des PV de la roue == 0. Vérifié
#    sans faux positif : combat normal = 6 avec PV > 0 ; exploration avec
#    équipe K.O. = état 0 ; après respawn les PV RESTENT à 0 (pas de soin
#    auto) mais l'état repasse à 0.
#  * KILL (mort DeathLink reçue) = écrire 0 aux 6 PV. Le jeu traite 0 comme
#    « 1 PV » (pas de K.O. immédiat : le check de mort ne s'évalue que sur un
#    coup reçu) -> en combat, le moindre coup achève chaque Yo-kai ; hors
#    combat, l'équipe reste agonisante jusqu'au prochain combat.
# ---------------------------------------------------------------------------
BATTLE_STATE_ADDR = 0x086B3B64      # u32 : 0 = exploration, 6 = en combat
BATTLE_STATE_FIGHTING = 6           # valeur « en combat » (écran Perdu inclus)
PARTY_HP_FIRST_ADDR = 0x086B3BEC    # u16 : PV actuels du 1er slot de la roue
PARTY_ENTRY_STRIDE = 0xE0           # taille d'une entrée Yo-kai (224 octets)
PARTY_SLOT_COUNT = 6                # slots de la roue d'équipe
PARTY_HP_MAX_OFFSET = 0x28          # PV max = adresse des PV actuels + 0x28
# DÉCOUVERTE CLÉ (tests live 2026-07-15/16) : PENDANT un combat, le jeu
# travaille sur une COPIE live des PV (struct de combat) — le tableau
# d'équipe ci-dessus est FIGÉ sur les valeurs d'avant-combat, puis réécrit
# DÉJÀ SOIGNÉ à la défaite (vérifié : 439 plein pendant l'écran Perdu).
# => Le tableau d'équipe est INUTILISABLE pour détecter une défaite, et un
# kill en plein combat doit écrire la COPIE LIVE (le tableau ne sert qu'au
# kill hors combat : au combat suivant, la roue démarre à 0 PV).
#
# STRUCT DE COMBAT LIVE — VÉRIFIÉE et STABLE (2 combats + défaite, save
# rang A niv 99 ET adresses du tableau confirmées sur 2 saves) :
#   * allocation déterministe : TOUJOURS à la même adresse ;
#   * 1 entrée de 0x4E8 octets par combattant ; les 6 PREMIERS = la roue du
#     joueur (ordre de la roue), les ennemis suivent (NE PAS y toucher) ;
#   * chaque entrée : PV MAX (u16) puis PV COURANTS (u16) adjacents ;
#   * HORS combat : struct entièrement VIDÉE (max = 0 -> garde-fou
#     d'existence naturel) ; en combat : repeuplée aux vraies valeurs ;
#   * DÉFAITE (écran « Perdu... ») : état de combat != 0 (3 sur l'écran,
#     6 pendant le combat) + les 6 cur = 0 avec max > 0 ;
#   * écrire 0 aux cur live = « comme 1 PV » (le K.O. ne s'évalue que sur
#     un coup reçu) -> le moindre coup achève chaque Yo-kai.
BATTLE_HP_FIRST_ADDR = 0x087B568E   # u16 : PV MAX du 1er slot ; cur = +2
BATTLE_HP_CUR_OFFSET = 2            # PV courants = entrée + 2
BATTLE_HP_ENTRY_STRIDE = 0x4E8      # taille d'une entrée combattant
# Compteur 0x086CA259 (u8) : ÉCARTÉ comme signal de mort — test live : il
# saute à l'OUVERTURE de chaque combat (compteur de combats, matérialisé au
# lancement ; lisait 0 après chargement de save puis 11 au 1er combat).
DEFEAT_COUNTER_CANDIDATE_ADDR = 0x086CA259  # u8, compteur de COMBATS (écarté)

# ---------------------------------------------------------------------------
# Bit -> location Archipelago. L'index de bit compte à partir du début de la
# région chest_flags (0x086CFE00) : bit_global = (octet - 0x086CFE00) * 8 + bit.
#
# Mapping établi par RE en jouant (ouverture des coffres + lecture du bitfield,
# voir docs/memory_map_fr.md). Les Hauts de Granval : 17 coffres (7 violets +
# 10 jaunes), bits 929-948. Numérotés par index de bit croissant. Chaque zone
# occupe une plage de bits contiguë (bit = ID fixe du coffre). Attention :
# ouvrir un coffre peut aussi poser un flag secondaire (contenu de l'objet,
# ex. bit 3634 vu au 1er coffre du canyon de la cigale) ; le bit du COFFRE est
# celui de la plage contiguë de la zone, confirmé en recoupant 2 coffres voisins.
# Ourcival : sous-zones à plages de bits contiguës (RE en jouant) —
#   Rochers de face     : bits 1244-1246 (3 coffres ; le 3e, déjà ouvert, déduit
#                         par contiguïté après RE des 2 premiers)
#   Canyon de la cigale : bits 1247-1248 (2 coffres)
# Centre-ville de Granval : 15 coffres, bits 1082-1099 (trous 1094/97/98),
#   RE « une passe + filtrage » (3 coffres isolés + 12 d'un coup, parasites de
#   contenu ~3600-3700 écartés). (Corrigé : ce n'était pas le quartier des
#   affaires mais le centre-ville — cf. Doteos.)
# ---------------------------------------------------------------------------
# ⚠️ JAUNES UNIQUEMENT (RE 2026-07-12, Doteos) : après reset des bits de coffres
# puis réouverture des SEULS coffres jaunes zone par zone, chaque liste ne
# contient plus que les coffres JAUNES (contenu fixe, checks AP). Les VIOLETS
# (contenu aléatoire, repop) ont été retirés — ils ne sont plus des locations.
# 70 coffres jaunes au total sur 18 zones.
_HAUTS_BITS = [929, 930, 931, 932, 933, 934, 935, 936, 938, 939]  # 7 violets retirés
_HAUTS_MATOUS_BITS = [954]             # Passage des matous : 1 jaune (955 violet)
_OURCIVAL_ROCHER_BITS = [1244, 1245, 1246]
_OURCIVAL_CIGALE_BITS = [1247, 1248, 1249]   # +1249 (RE 2026-07-12)
# Ourcival (zone principale) : COMPLÉTÉ par la capture aventure (2026-07-14) —
# ajout de 1218, 1223, 1225 qui manquaient (zone = 1218-1227 + 1241/1242, 12 jaunes).
_OURCIVAL_PRINCIPAL_BITS = [1218, 1219, 1220, 1221, 1222, 1223, 1224, 1225, 1226, 1227, 1241, 1242]
_CENTRE_VILLE_BITS = [1082, 1083, 1084, 1085, 1086, 1087, 1088,
                      1105]  # 8 violets retirés ; 1105 = coffre oublié
                             # (capture 2026-07-16, Bracelet en toc natif)
# Corniche (Domaine de la Corniche) : 1150,1151,1153 + 1154 (jaune confirmé en
# jeu 2026-07-18, Poupée bronze — était classé violet à tort).
_CORNICHE_BITS = [1150, 1151, 1153, 1154, 1155, 1152]  # 1152 ajouté en fin
                                       # (Coffre 06, Docteur Tit'ange) pour ne pas
                                       # renuméroter 03/04/05 (2026-07-19)
_EGOUTS_BITS = [1197, 1198, 1194, 1196, 1195, 1199, 1200, 1206, 1205, 1204, 1203, 1202, 1201]  # jaunes ;
                                       # 1194=entrée B ; 1196/1195=accès Ruelle
                                       # obscure ; 1199/1200=accès Corniche ;
                                       # 1206/1205=accès Centre-ville ;
                                       # 1204/1203=accès Quartier des boutiques ;
                                       # 1202/1201=accès Coteau fleuri (2026-07-19)
_ALLEE_SINISTRE_BITS = [956]           # Allée sinistre : 1 jaune (958 violet)
_RUELLE_OBSCURE_BITS = [950]           # Ruelle obscure : 1 jaune (capture 2026-07-18)
_CANAL_ISOLE_BITS = [952, 953]         # Canal isolé (sous-zone Ruelle obscure) : 2 jaunes, rang C
# Corniche > Maison des Roch (intérieur) : 1 coffre, bit 1421 (plage propre).
_MAISON_ROCH_BITS = [1421]
# Corniche > Méga toboggan : 2 jaunes (993, 994) ; 995 violet.
_MEGA_TOBOGGAN_BITS = [993, 994, 1080]  # 1080 = Coffre 03 (EXPorbe moyen, 2026-07-19)
# Corniche > Musée (nuit) : 8 coffres, byte 0x086CFE92 PLEIN (bits 1168-1175). Accès
# via Télémire (débloqué Ch4 Ourcival -> exige Indications de Maman). RE Doteos 2026-
# 07-24 (ordre = ordre d'ouverture des coffres 01-08).
_CORNICHE_MUSEE_BITS = [1168, 1170, 1171, 1169, 1173, 1172, 1175, 1174]
# Mont Sylvestre > Tunnel abandonné (salle du trésor) : 5 coffres (RE Doteos 2026-
# 07-24). Accès via la quête « Chasseurs de trésors 2 » (Ch6). Coffres 3/4/5 au MÊME
# marqueur en jeu. Ordre = ordre d'ouverture (01-05).
_TUNNEL_TRESOR_BITS = [998, 1003, 1005, 1002, 1001, 999, 1000, 1004]  # 999/1000/1004
                                       # = Coffres 06/07/08 (oubliés, ajoutés 2026-07-24)
# Tunnel abandonné EST (accès après le Tablo Draconfus, quête « Chasseurs de trésors
# 3 », Ch8) : 6 coffres (RE Doteos 2026-07-24). C02 contient Clé appartement B-204,
# C06 contient Huile de Tendino (objets-clés). Ordre = ordre d'ouverture (01-06).
_TUNNEL_EST_BITS = [1008, 1010, 1009, 1011, 1012, 1006]
# Sommet du Mont Sylvestre (accès via le méga toboggan) : 1 coffre, bit 991.
_SOMMET_SYLVESTRE_BITS = [991]
# Sentier de randonnée (Mont Sylvestre) : 1 coffre, bit 987.
_SENTIER_RANDO_BITS = [987]
# Mont Sylvestre (zone) : coffre 975 CONFIRMÉ en direct. (Le cluster 960-967 que
# je croyais Mont Sylvestre est en fait l'ÉCOLE, cf. _ECOLE_NUIT_BITS.) Reste 2
# coffres manquants non encore atteints, plage inconnue.
_MONT_SYLVESTRE_BITS = [975]
# Mont Sylvestre accessible via les ÉGOUTS (côté Corniche), rang C requis :
# 2 coffres (bit 972 = Grand EXPorbe, capture 2026-07-19).
_SYLVESTRE_EGOUT_BITS = [972, 973]
# École élémentaire de Granval (nuit) : 13 jaunes, bits 959-971 CONTIGUS (aucun
# violet ; +962 découvert au reset RE 2026-07-12).
_ECOLE_NUIT_BITS = [959, 960, 961, 962, 963, 964, 965, 966, 967, 968, 969, 970, 971]
# Côté fleuri (Mont Sylvestre) : 11 coffres au total (info Doteos), 8 CONFIRMÉS
# ici (bits 1014-1031, espacés ; 1019 était déjà ouvert). Manquent 3 : 1 coffre
# inaccessible pour l'instant + 2 « fantômes » ouverts avant la 1re référence,
# hors de cette plage (plage éloignée probable, cf. Maison des Roch @1421) ->
# à capturer en direct plus tard ou via data-mining.
_COTE_FLEURI_BITS = [1013, 1014, 1015, 1016, 1017, 1019, 1033]  # +1033 Coffre 07
                                       # (Poupée bronze, 2026-07-19)
# Granval (Quartier des boutiques) : 5 jaunes (1115-1119) ; 1121-1132 violets.
_GRANVAL_BOUTIQUES_BITS = [1115, 1116, 1117, 1118, 1119, 1133]  # 1133 = Coffre 06
                                       # (Contre-allées, Vivez Karaté, 2026-07-19)
# Centre-ville de Granval, sous-zone sans nom : 1 jaune (1103 ; 1102 violet).
_CENTRE_VILLE_SOUSZONE_BITS = [1103]
# ⚠️ DÉCISION FINALE (Doteos, RE 2026-07-12) : on NE GARDE QUE LES COFFRES JAUNES
# comme checks (contenu fixe, permettant l'affichage de texte). Les VIOLETS
# (contenu aléatoire, repop, bit 1->0) sont EXCLUS des locations. La
# classification a été faite par : reset des bits de coffres à 0, puis
# réouverture des SEULS coffres jaunes zone par zone (bit=1 => jaune, fiable).
# Les listes _*_BITS ci-dessus ne contiennent donc plus que des jaunes.
CHEST_BIT_TO_LOCATION: Dict[int, str] = {}
CHEST_BIT_TO_LOCATION.update({
    bit: f"Les Hauts de Granval - Coffre {i:02d}"
    for i, bit in enumerate(_HAUTS_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Les Hauts de Granval (Passage des matous) - Coffre {i:02d}"
    for i, bit in enumerate(_HAUTS_MATOUS_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Ourcival (Rochers de face) - Coffre {i:02d}"
    for i, bit in enumerate(_OURCIVAL_ROCHER_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Ourcival (Canyon de la cigale) - Coffre {i:02d}"
    for i, bit in enumerate(_OURCIVAL_CIGALE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Ourcival - Coffre {i:02d}"
    for i, bit in enumerate(_OURCIVAL_PRINCIPAL_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Centre-ville de Granval - Coffre {i:02d}"
    for i, bit in enumerate(_CENTRE_VILLE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Corniche - Coffre {i:02d}"
    for i, bit in enumerate(_CORNICHE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Égouts - Coffre {i:02d}"
    for i, bit in enumerate(_EGOUTS_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Allée sinistre - Coffre {i:02d}"
    for i, bit in enumerate(_ALLEE_SINISTRE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Ruelle obscure - Coffre {i:02d}"
    for i, bit in enumerate(_RUELLE_OBSCURE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Canal isolé - Coffre {i:02d}"
    for i, bit in enumerate(_CANAL_ISOLE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Corniche (Maison des Roch) - Coffre {i:02d}"
    for i, bit in enumerate(_MAISON_ROCH_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Corniche (Méga toboggan) - Coffre {i:02d}"
    for i, bit in enumerate(_MEGA_TOBOGGAN_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Corniche (Musée) - Coffre {i:02d}"
    for i, bit in enumerate(_CORNICHE_MUSEE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Tunnel abandonné (salle du trésor) - Coffre {i:02d}"
    for i, bit in enumerate(_TUNNEL_TRESOR_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Tunnel abandonné est - Coffre {i:02d}"
    for i, bit in enumerate(_TUNNEL_EST_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Sommet du Mont Sylvestre - Coffre {i:02d}"
    for i, bit in enumerate(_SOMMET_SYLVESTRE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Sentier de randonnée - Coffre {i:02d}"
    for i, bit in enumerate(_SENTIER_RANDO_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Mont Sylvestre - Coffre {i:02d}"
    for i, bit in enumerate(_MONT_SYLVESTRE_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Mont Sylvestre (accès égouts) - Coffre {i:02d}"
    for i, bit in enumerate(_SYLVESTRE_EGOUT_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"École élémentaire de Granval (nuit) - Coffre {i:02d}"
    for i, bit in enumerate(_ECOLE_NUIT_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Côté fleuri - Coffre {i:02d}"
    for i, bit in enumerate(_COTE_FLEURI_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Granval (Quartier des boutiques) - Coffre {i:02d}"
    for i, bit in enumerate(_GRANVAL_BOUTIQUES_BITS, start=1)
})
CHEST_BIT_TO_LOCATION.update({
    bit: f"Centre-ville de Granval (sous-zone) - Coffre {i:02d}"
    for i, bit in enumerate(_CENTRE_VILLE_SOUSZONE_BITS, start=1)
})

# ---------------------------------------------------------------------------
# COFFRES DE L'AVENTURE (capture live 2026-07-14, TOUS jaunes dixit Doteos).
# Zones NOUVELLES non re-mappées lors des sessions précédentes (Doteos n'a pas
# ré-ouvert les zones déjà mappées en refaisant l'aventure). bit = ID fixe du
# coffre (diff avant/après vérifié). Cf. capture_aventure/chest_mapping.json.
# ---------------------------------------------------------------------------
_ADVENTURE_CHESTS: Dict[str, List[int]] = {
    "Manoir (Coteau fleuri)":              [1042, 1045, 1046, 1049, 1050, 1051],
    # Partie arrière du manoir (derrière la porte « Clé de derrière ») : nouveaux
    # coffres gatés par l'objet-clé AP Clé de derrière (capture 2026-07-19).
    "Manoir arrière (Coteau fleuri)":      [1041, 1047, 1048, 1043, 1044],
    "Tour Excellence":                     [1207, 1208, 1209, 1210, 1211, 1419],  # 1419 = Clé C-101
    # Parvis de la gare d'Ourcival (sous-zone) : 3 coffres (capture 2026-07-19)
    "Parvis de la gare d'Ourcival":        [1258, 1257, 1256, 1251, 1252],
    "Mont de l'Ours (présent)":            [1250],
    # 1285 = coffre oublié, capturé le 2026-07-16 (diff propre, 1 seul bit) ;
    # AJOUTÉ EN FIN de liste pour ne pas renuméroter les coffres 01-12.
    "San Fantastico":                      [1259, 1260, 1261, 1262, 1263, 1264,
                                            1265, 1266, 1267, 1268, 1269, 1271,
                                            1285, 1270, 1272, 1420],  # 1270=C14,
                                            # 1272=C15, 1420=C16 (Clé C-303, 2026-07-19)
    "San Fantastico (rang C)":             [1287],
    # Tour du commerce (sous-zone du Centre-ville) — capture 2026-07-16,
    # diffs propres 1 bit/coffre. Accès : chapitre 4 (min_chapter=3) + rang C ;
    # le coffre 1107 exige le rang A (contenait la Clé magnétique bleue,
    # NATIVE : débloque un Yo-kai, pas de check -> le coffre reste un check
    # normal, la clé va en liste d'objets-clés donc la neutralisation
    # d'inventaire ne la touche pas).
    "Tour du commerce (3e étage)":         [1108, 1109, 1110],
    "Tour du commerce (3e étage, rang A)": [1107],
    "Tour du commerce (12e étage)":        [1111, 1112, 1113],
    # Appartement C-303 (Quartier des boutiques) : coffre derrière la porte
    # ouverte par l'objet-clé AP « Clé appartement C-303 » (capture
    # 2026-07-16, Sabre déchaîné natif). Le check exige la clé en logique.
    "Quartier des boutiques (appartement C-303)": [1138],
    "Grotte du littoral":                  [1290, 1291, 1292, 1293, 1294, 1295,
                                            1296, 1297, 1298],
    "Coteau fleuri (présent)":             [1037],
    "Coteau fleuri (rang C)":              [1018, 1038],  # Anneau illusion / Pièce verte
    "Clinique du Crépuscule":              [1139, 1140, 1141, 1142, 1143, 1145,
                                            1146, 1147, 1149],
    "Vieux Hauts de Granval":              [1299, 1302, 1303, 1304, 1300],  # +1300 Coffre 05
    "Vieux Hauts de Granval (retour Ch10)": [1301],
    "Vieux Coteau Fleuri":                 [1305, 1306, 1307, 1308],
    "Chemin du Sanctuaire du Renard":      [1319],
    "Chemin du Puits":                     [1321],
    "Vieille Ferronnerie de Granval":      [1324, 1325],
    "Vieux Mont Sylvestre":                [1326],
    "Lac des Coloquintes (passé)":         [1329],
    # 1332/1335-1339 : coffres oubliés (capture 2026-07-16, sous-zones Bosquet
    # des lucioles / Sentier aux plantes fusionnées ici — choix Doteos).
    # Ajoutés EN FIN (ordre de capture) pour préserver la numérotation 01-02.
    # NB : le coffre bit 1351 (Clé appartement B-301, Vieil Ourcival) n'est PAS
    # mappé : objet-clé -> son check est « Objet-clé : Clé appartement B-301 ».
    "Vieil Ourcival":                      [1333, 1334, 1332, 1336, 1337, 1338,
                                            1339, 1335, 1340, 1351],  # 1340=Coffre 09
                                            # (Temple des songes) ; 1351=Coffre 10
                                            # (Clé appartement B-301, 2026-07-19)
    # Vieux Mont de l'Ours (passé, accès via Vieil Ourcival) — capture 2026-07-16.
    "Vieux Mont de l'Ours":                [1354, 1355, 1357, 1353, 1356],  # 1353=Coffre 04
                                            # (Pièce mauve) ; 1356=Coffre 05 (Remède
                                            # puiss., capture 2026-07-19)
    # Coteau fleuri, coffre isolé exigeant le rang B (capture 2026-07-16).
    "Coteau fleuri (rang B)":              [1035],
    "Plaines Plinpot":                     [1361, 1362, 1363, 1364, 1365, 1366,
                                            1367, 1368, 1369, 1370, 1371],
    # Zone des portails (Doteos 2026-07-27) : donjons des « portails mystère »,
    # accès depuis La Corniche après la quête du même nom. Chaque coffre coûte un
    # nombre de GLOBES DE PORTAIL (consommable, hash 0x46452D56) :
    #   Coffre 01 = 10 globes · 02-03 = 20 · 04-09 = 30 · 10 = 40 (Salle des
    #   portails, même palier que les tablos n°13/14/15).
    # ⚠️ La logique AP ne sait pas exprimer « posséder N consommables » ->
    # coût NON modélisé en V1 (prévu pour la V2 : globes dans le pool).
    "Zone des portails":                   [1372, 1373, 1374, 1375, 1376, 1377,
                                            1378, 1379, 1380, 1381],
}
for _zone, _bits in _ADVENTURE_CHESTS.items():
    CHEST_BIT_TO_LOCATION.update({
        _b: f"{_zone} - Coffre {_i:02d}" for _i, _b in enumerate(_bits, start=1)
    })

# ---------------------------------------------------------------------------
# Rattachement de chaque ZONE de coffre (préfixe avant " - Coffre") à une
# RÉGION Archipelago (regions.REGION_NAMES). Les sous-zones/intérieurs héritent
# de la région de leur quartier parent. ⚠️ 3 rattachements PROVISOIRES à
# confirmer par Doteos (marqués TODO).
# ---------------------------------------------------------------------------
CHEST_ZONE_TO_REGION: Dict[str, str] = {
    "Les Hauts de Granval":                       "Les Hauts de Granval",
    "Les Hauts de Granval (Passage des matous)":  "Les Hauts de Granval",
    "Allée sinistre":                             "Les Hauts de Granval",   # confirmé Doteos
    "Ruelle obscure":                             "Les Hauts de Granval",   # confirmé Doteos
    "Canal isolé":                                "Les Hauts de Granval",   # confirmé Doteos (rang C)
    "École élémentaire de Granval (nuit)":        "Les Hauts de Granval",   # confirmé Doteos
    "Égouts":                                     "Les Hauts de Granval",   # confirmé Doteos
    "Centre-ville de Granval":                    "Centre-ville de Granval",
    "Tour du commerce (3e étage)":                "Centre-ville de Granval",
    "Tour du commerce (3e étage, rang A)":        "Centre-ville de Granval",
    "Tour du commerce (12e étage)":               "Centre-ville de Granval",
    "Quartier des boutiques (appartement C-303)": "Quartier des boutiques",
    "Centre-ville de Granval (sous-zone)":        "Centre-ville de Granval",
    "Granval (Quartier des boutiques)":           "Quartier des boutiques",
    "Corniche":                                   "La Corniche",
    "Corniche (Maison des Roch)":                 "La Corniche",
    "Corniche (Méga toboggan)":                   "La Corniche",
    "Corniche (Musée)":                           "La Corniche",
    "Tunnel abandonné (salle du trésor)":         "Mont Sylvestre",
    "Tunnel abandonné est":                       "Mont Sylvestre",
    "Côté fleuri":                                "Coteau fleuri",
    "Ourcival":                                   "Ourcival",
    "Parvis de la gare d'Ourcival":               "Ourcival",
    # Géographie corrigée (Doteos 2026-07-16) : ces deux zones sont AU
    # Mont de l'Ours (les noms de locations restent inchangés — compat seeds).
    "Ourcival (Rochers de face)":                 "Mont de l'Ours",
    "Ourcival (Canyon de la cigale)":             "Mont de l'Ours",
    "Mont Sylvestre":                             "Mont Sylvestre",
    "Sommet du Mont Sylvestre":                   "Mont Sylvestre",
    "Sentier de randonnée":                       "Mont Sylvestre",
    "Mont Sylvestre (accès égouts)":              "Mont Sylvestre",
    # --- Zones de l'aventure (2026-07-14) ---
    "Manoir (Coteau fleuri)":                     "Coteau fleuri",
    "Manoir arrière (Coteau fleuri)":             "Coteau fleuri",
    "Coteau fleuri (présent)":                    "Coteau fleuri",
    "Coteau fleuri (rang C)":                     "Coteau fleuri",
    "Tour Excellence":                            "Tour Excellence",
    "Mont de l'Ours (présent)":                   "Mont de l'Ours",
    "San Fantastico":                             "San Fantastico",
    "San Fantastico (rang C)":                    "San Fantastico",
    "Grotte du littoral":                         "San Fantastico",
    "Clinique du Crépuscule":                     "Clinique du Crépuscule",
    "Vieux Hauts de Granval":                     "Vieux Granval",
    "Vieux Hauts de Granval (retour Ch10)":       "Vieux Granval",
    "Vieux Coteau Fleuri":                        "Vieux Granval",
    "Chemin du Sanctuaire du Renard":             "Vieux Granval",
    "Chemin du Puits":                            "Vieux Granval",
    "Vieille Ferronnerie de Granval":             "Vieux Granval",
    "Vieux Mont Sylvestre":                       "Vieux Granval",
    "Lac des Coloquintes (passé)":                "Vieux Granval",
    "Vieil Ourcival":                             "Vieil Ourcival",
    "Vieux Mont de l'Ours":                       "Vieil Ourcival",
    "Coteau fleuri (rang B)":                     "Coteau fleuri",
    "Plaines Plinpot":                            "Plaines Plinpot",
    # Portails : donjons atteints depuis La Corniche -> rattachés à cette région
    # (pas de région propre ; les marqueurs tracker vont sur la carte Corniche).
    "Zone des portails":                          "La Corniche",
}


def chest_zone_of(location_name: str) -> str:
    """'Corniche (Méga toboggan) - Coffre 02' -> 'Corniche (Méga toboggan)'."""
    return location_name.rsplit(" - Coffre", 1)[0]


def chest_region_of(location_name: str) -> str:
    """Région Archipelago d'une location de coffre (via CHEST_ZONE_TO_REGION)."""
    return CHEST_ZONE_TO_REGION[chest_zone_of(location_name)]


QUEST_BIT_TO_LOCATION: Dict[int, str] = {}

# Bit (= N° Médallium, base 0x086CFEBC) -> location boss. Boss d'histoire
# VÉRIFIÉS en jeu (2026-07-14). Les N° suivent l'ordre du Médallium (pas l'ordre
# des chapitres). Post-game (Potofeu/Filomène) : N° à capturer plus tard.
MEDALLIUM_BIT_TO_LOCATION: Dict[int, str] = {
    388: "Boss : Grolos",
    389: "Boss : Méganyan",
    # 390 Barbefrousse RETIRÉ du Médallium (Doteos 2026-07-28) : le bit Médallium
    # se pose à la RENCONTRE -> le check partait en plein combat, avant même la
    # victoire (Doteos a perdu le combat, le check était déjà envoyé). Détecté
    # désormais par son MARQUEUR D'EVENT « vaincu » (EVENT_CHECK_FLAGS,
    # 0x086CFFF1 b2), capturé par diff rencontre -> victoire.
    391: "Boss : Tourbœillon",
    # 392 Laure / 393 Marge RETIRÉS du Médallium (Doteos 2026-07-28) : bit posé à
    # la RENCONTRE. Détectés par leur marqueur d'event « vaincu » 0x086CFFF0 b0
    # (voir EVENT_CHECK_FLAGS) — un SEUL flag pour les deux, elles se battent dans
    # le MÊME combat, donc les 2 checks partent ensemble (comportement correct).
    394: "Boss : Lady Perpétua",
    395: "Boss : Lady Démona",
    # --- Boss OPTIONNELS (déplacés depuis EVENT_CHECK_FLAGS 2026-07-28) ---
    38: "Boss : Démophage",
    119: "Boss : Misterre",
    355: "Boss : Injustin",
    356: "Boss : Fielippine",
    357: "Boss : Cyrustre",
    358: "Boss : Maudicko",
    359: "Boss : Ronéan",
    398: "Boss : Crocho",
    402: "Boss : Ombraptor",
    404: "Boss : Sabroclair",
    406: "Boss : Inamygal",
    412: "Boss : Volteface",
    413: "Boss : Didgeai",
    415: "Boss : Firmain",
    416: "Boss : Tromplœil",
}

# (nom de région mémoire, table bit -> location) exploitées par le client.
# Tablo-blabla : bitfield à 0x086CFB1C, bit = « n° du tablo RÉSOLU » (relatif à la
# base). RE Doteos 2026-07-24/25 (voir capture_aventure/tablo_captures.json). Seuls
# les tablos capturés sont mappés (détectables) ; les autres restent inactifs. Note :
# le packing des 2 bits (complété/résolu) varie (parfois +4, parfois adjacents) ; on
# mappe le bit RÉSOLU. Les autres bits du byte (compteurs/révélés) = no-op.
TABLO_BASE = 0x086CFB1C
TABLO_BIT_TO_LOCATION: Dict[int, str] = {
    1259: "Tablo-blabla n°01 : Granpapéti",
    1260: "Tablo-blabla n°02 : Feulion",
    1261: "Tablo-blabla n°03 : Triptic-tac",
    1267: "Tablo-blabla n°04 : Robonyan",
    1268: "Tablo-blabla n°05 : Draconfus",
    1275: "Tablo-blabla n°08 : Ronimpec",
    1283: "Tablo-blabla n°09 : Sumochi",
    1285: "Tablo-blabla n°11 : Hiblusion",
    1291: "Tablo-blabla n°12 : Maître Oden",
    1302: "Tablo-blabla n°16 : Grégrigry",
    1307: "Tablo-blabla n°17 : Chaipô",
    1309: "Tablo-blabla n°18 : Croquin",
    1315: "Tablo-blabla n°19 : Supernoël",
    # n°20 Noripop (San Fantastico / Grotte du littoral) : paire CONSÉCUTIVE
    # 1318/1319 (0x086cfbc0 b6/b7) + bit 1 de la grappe Grotte (0x086CFB1C).
    # RÉSOLU = le bit HAUT : vérifié en direct (Doteos 2026-07-27 a écrit la
    # réponse -> SEUL 1319 posé, 1318 encore à 0 ; 1318 se pose à la complétion
    # totale). Cohérent avec la règle « on mappe le bit résolu ».
    1319: "Tablo-blabla n°20 : Noripop",
    # n°21 Wakapoeira (même grotte) : paire 1320/1321 (0x086cfbc1 b0/b1) + bit 2
    # de la grappe. Diff LIVE 2026-07-27 : écrire la réponse pose 0x086cfb1c
    # 0x02->0x06 (bit 2) et 0x086cfbc1 0x00->0x02 = SEUL 1321. Règle « bit haut
    # = résolu » confirmée une 2e fois.
    1321: "Tablo-blabla n°21 : Wakapoeira",
    # n°22 Salsalga (même grotte) : paire 1322/1323 (0x086cfbc1 b2/b3) + bit 3 de
    # la grappe. Bits relevés le 2026-07-20 ; RÉSOLU = 1323 par la règle « bit
    # haut » désormais confirmée 2 fois en direct (Noripop 1319, Wakapoeira 1321).
    1323: "Tablo-blabla n°22 : Salsalga",
    # n°13 Cupistol (La Corniche, Salle des portails, quiz rez-de-chaussée ;
    # accès = 40 globes de portail). Diff LIVE 2026-07-27 : écrire la réponse pose
    # 0x086cfbbd b7 = 1295 ET 0x086cfbbe b3 = 1299 -> motif « complété +4 = résolu »
    # (comme Granpapéti 1255/1259, Hiblusion 1281/1285) -> on mappe le HAUT.
    1299: "Tablo-blabla n°13 : Cupistol",
    # n°14 Cigalopin (Salle des portails, quiz 1er étage). Diff LIVE : SEUL
    # 0x086cfbbe b4 = 1300 posé (le « complété » 1296 reste à 0) -> confirme que
    # le bit HAUT du couple est bien le résolu. Les résolus se suivent : 1299,
    # 1300 (et 1301 attendu pour le n°15).
    1300: "Tablo-blabla n°14 : Cigalopin",
    # n°15 Chiperpiou (Salle des portails, quiz 2e étage). PRÉDICTION VALIDÉE
    # 2026-07-27 : 0x086cfbbe 0x5d -> 0x7d = bit 5 = 1301, la suite attendue des
    # résolus (1299, 1300, 1301). Salle des portails COMPLÈTE.
    1301: "Tablo-blabla n°15 : Chiperpiou",
}

FLAG_TABLES: List[Tuple[str, Dict[int, str]]] = [
    ("chest_flags", CHEST_BIT_TO_LOCATION),
    ("quest_flags", QUEST_BIT_TO_LOCATION),
    # ⚠️ medallium_flags RETIRÉ de FLAG_TABLES (Doteos 2026-07-28) : un bit
    # Médallium se pose à la RENCONTRE du boss, pas à sa victoire -> il ne doit
    # plus envoyer de check directement. MEDALLIUM_BIT_TO_LOCATION sert désormais
    # à ARMER une victoire en attente (client : _boss_pending), confirmée par la
    # fin du combat sans défaite. Cf. la section « boss » de client.poll_game.
    ("tablo_flags", TABLO_BIT_TO_LOCATION),
]


def memory_map_ready() -> bool:
    """Vrai dès qu'au moins une région surveillée est renseignée."""
    return any(addr != 0 for name, (addr, _size) in MEMORY_REGIONS.items()
               if name != "money")


def new_set_bits(before: bytes, after: bytes) -> List[int]:
    """Index des bits passés de 0 à 1 entre deux lectures d'une région."""
    bits: List[int] = []
    for i, (old, new) in enumerate(zip(before, after)):
        gained = new & ~old
        if gained:
            bits += [i * 8 + b for b in range(8) if gained & (1 << b)]
    return bits


# ---------------------------------------------------------------------------
# Aides de détection non-bitfield (exploitées par client.py à l'étape 2).
# ---------------------------------------------------------------------------
_QUEST_HASH_NAMES: Dict[int, str] = {}


def load_quest_hash_names() -> Dict[int, str]:
    """{hash CRC32 (int) -> nom FR de la quête} depuis data/quest_hashes.json.

    Le jeu écrit le hash de la dernière quête terminée à
    LAST_QUEST_DONE_HASH_ADDR ; cette table le traduit en nom (mis en cache).
    """
    global _QUEST_HASH_NAMES
    if not _QUEST_HASH_NAMES:
        # pkgutil.get_data lit la ressource depuis le package, qu'il soit un
        # dossier (dev) OU un zip (.apworld chargé par Archipelago).
        raw = json.loads(
            pkgutil.get_data(__package__, "data/quest_hashes.json").decode("utf-8"))
        _QUEST_HASH_NAMES = {int(k, 16): v for k, v in raw.items()}
    return _QUEST_HASH_NAMES


def chapters_completed(chapter_counter: int) -> List[int]:
    """Chapitres TERMINÉS déduits du compteur STORY_CHAPTER_ADDR.

    Le compteur vaut le numéro du chapitre EN COURS ; les chapitres 1..(K-1)
    sont donc terminés quand il vaut K (vérifié en jouant, 1->2->3->4->5).
    """
    return list(range(1, max(1, chapter_counter)))
