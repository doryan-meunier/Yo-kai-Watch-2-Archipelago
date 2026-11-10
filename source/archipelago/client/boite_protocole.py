"""Protocole de la boîte aux lettres Archipelago (v9) : constantes, disposition, encodage des entrées et
règles de texte du bandeau. Module partagé, bibliothèque standard uniquement, sans dépendance :
- par le client du mod (`archipelago/client/boite.py`) ;
- par le client de test `tools/ap_boite_test.py` (qui vérifie dans son `--selftest` que ces constantes
  sont celles de `src/archipelago/boite.h`).
Référence : docs/systemes/archipelago_boite.md. Toute modification du format se fait dans boite.h, dans ce
module et dans la doc en même temps.
"""
from __future__ import annotations

import struct

# --- Protocole (doit correspondre à src/archipelago/boite.h ; vérifié par --selftest) ---
ZONE = 0x0091C000
TAILLE_ZONE = 0x28000         # v10 depuis fix/nom-don-script (0x24000 avant : suite des noms de vitrine) ; 0x20000 en v9, 0x16000 en v7/v8, 0x12000 en v6, 0xE000 en v5, 0xA000 en v3/v4, 0x4000 en v1/v2)
MAGIC = 0x50414B59            # "YKAP"
VERSION = 10                  # v10 : mélange des Yo-kai par rencontre (§22.4) ; v9 : boutiques (§26) ; v8 : DeathLink (§25) ; v7 : randomizer des boss (§24) ; v6 : randomizer de Yo-kai (§22) ; v5 : récompenses de quête (§21) ; v4 : liaison (§11.2)
OFF_DONS, CAP_DONS = 0x0100, 128
OFF_JOURNAL, CAP_JOURNAL = 0x0C00, 128
OFF_COFFRES, CAP_COFFRES = 0x1C00, 576
# Notifications (v2)
OFF_NOTIFS, CAP_NOTIFS, TAILLE_NOTIF, NOTIF_TEXTE = 0x0900, 8, 64, 56
OFF_NOTIFS_AUTO, CAP_NOTIFS_AUTO = 0x0B00, 8
OFF_NOTIF_TAMPON, TAILLE_TAMPON = 0x0B80, 128
POLITIQUE_REESSAYER, POLITIQUE_NOTIF_AUTO = 0x01, 0x02
NOTIF_BALISES = 0x01
NOTIF_ETAT_AFFICHAGE, NOTIF_ETAT_AUTO, NOTIF_ETAT_SUSPENDUE = 0x01, 0x02, 0x04
NOTIF_DUREE_DEFAUT = 120      # images (~4 s)
NOTIF_LARGEUR = 112           # largeur max estimée (demi-unités, bandeau mono-ligne ~121, voir la doc)
NOTIF_AUTO_TEXTE = 4
# v3 (docs/systemes/archipelago_boite.md §10 à §14)
OFF_CONFIG, TAILLE_CONFIG = 0x4000, 0x100            # configuration de connexion (écrite par le jeu)
OFF_CONNEXION, TAILLE_CONNEXION = 0x4100, 0x200      # état de connexion (écrit par le client)
OFF_SCRIPTS, CAP_SCRIPTS, TAILLE_SCRIPT = 0xDC40, 48, 16  # dons de script (J3) ; 0x4300 / 16 entrées jusqu'aux
#   objets-clés de quête (objets_cles_v11 §16) : le jeu publie offset et capacité (scripts_off, scripts_capacite)
OFF_SCRIPTS_V3, CAP_SCRIPTS_V3 = 0x4300, 16                # emplacement d'origine (présent dans toute zone v3 et plus)
OFF_VITRINE, OFF_PRIVE = 0x4400, 0x4500              # jeu seulement
OFF_VERROUS, CAP_VERROUS, TAILLE_VERROUS = 0x4F00, 24, 0x100   # verrous de capacité (J4, client)
# v4 (J4, §20) : verrous compilés dans le build (ApVerrous::compiles, écrit par le JEU en +4) ; bit 31 = liste publiée.
# Numéros k = spots : 0 Filet, 1 Pile ou passe (machine du tutoriel, déclencheurs de phase et de carte), 2 Clés de l'école, 3 Herbe ancestrale, 4 Super tournevis (V1.1), 5 Canne à pêche,
# 6 Modèle zéro, 7 Indications de Maman (V1.1), 10 Clé salle du trésor, 11 Poignée étrange (V1.1, déclencheurs de quête),
# 12 Vélo (V1.1, sans spot : réserve 570..575), 18 Rangs de montre (V1.1, objet PROGRESSIF sans spot : recu[18] = nombre
# d'exemplaires reçus, pas 0/1), 19 portes de montre D (MODE du verrou 18, archipelago_objets_cles_v11.md §14.8 : actif,
# rang AP = recu[18] et portes D fermées aussi ; inactif, rang AP = D + recu[18] ; recu[19] ignoré par le jeu),
# 20 rang de montre RÉEL (MODE du verrou 18, archipelago_objets_cles_v11.md §17 : actif, le jeu monte le vrai rang de
# la montre à min(recu[18], A) et ignore les montées de rang de ses scripts ; recu[20] ignoré par le jeu),
# 21 vélo RÉEL (MODE du verrou 12, archipelago_objets_cles_v11.md §15 bis : actif, le jeu donne vraiment le vélo à la
# réception du Vélo, flags 39 / 40 et objet vélo, et retire l'objet vélo de la boutique tant qu'il n'est pas reçu ;
# recu[21] ignoré par le jeu).
VERROUS_PUBLIES = 0x80000000
NOMS_VERROUS = {0: "Filet à insectes", 1: "Pile ou passe", 2: "Clés de l'école", 3: "Herbe ancestrale", 4: "Super tournevis",
                5: "Canne à pêche", 6: "Modèle zéro", 7: "Indications de Maman", 10: "Clé salle du trésor",
                11: "Poignée étrange", 12: "Vélo", 18: "Rang de montre", 19: "Rang de montre (portes D)",
                20: "Rang de montre (rang réel)", 21: "Vélo (vélo réel)",
                23: "Invités de l'Auberge des voyageurs",
                24: "Yo-criminels libres", 25: "Combats d'évènement libres",
                26: "Grelots d'eShop", 28: "Boutiques", 29: "Fenêtre « objet obtenu » des checks",
                30: "Yo-criminels trouvables", 22: "Fonctions étendues (client trop ancien)",
                32: "Ultramax N et K dans la même partie", 33: "Invités de l'Auberge à leur espèce",
                40: "Yo-kai Watch", 41: "Documents perdus", 42: "Cartes d'Ultramax",
                65: "Verrous étendus (client trop ancien)"}
# Fonctions du patch SANS objet (bits 24.. de `compiles`, jamais dans `actifs` ; src/archipelago/verrous.h) : exigées
# par slot_data `fonctions_exigees` (format 14, archipelago_amis_criminels.md §6) ; absentes -> partie refusée comme un
# verrou manquant.
FONCTION_CRIMINELS_LIBRES = 24
FONCTION_COMBATS_LIBRES = 25
FONCTION_GRELOTS_ESHOP = 26
FONCTION_BOUTIQUES = 28      # articles de boutique Archipelago (boîte v9, §26 ; slot_data format 15)
FONCTIONS_CONNUES = frozenset({FONCTION_CRIMINELS_LIBRES, FONCTION_COMBATS_LIBRES, FONCTION_GRELOTS_ESHOP,
                               FONCTION_BOUTIQUES})
# Options du joueur appliquées par le code du jeu (ni verrou ni objet) : bit k de `compiles` (option compilée, écrit par
# le jeu) ET de `actifs` (option choisie dans la graine, écrit par le client) ; recu[k] n'existe pas (k >= 24). Les bits
# 24..26 et 28 sont les fonctions sans objet ci-dessus (FONCTIONS_CONNUES).
OPTION_BINGO_KAI = 27        # Bingo-kai infini (slot_data format 16, docs/systemes/archipelago_bingo_kai.md)
NOMS_OPTIONS = {OPTION_BINGO_KAI: "Bingo-kai infini"}
FLAG_BINGO_RESTANT = 0xA45A65EC   # octet global n° 16 : tours de Bingo-kai restant aujourd'hui (lu au moins 1 par le jeu)
VERROU_PILE = 1              # k de la Pile ou passe (spot 559) : verrou RETIRÉ du jeu le 2026-10-01 (objets_cles §14.9),
#                              jamais compilé ni exigé (synchro.VERROUS_SANS_CODE) ; gardé pour les noms
VERROU_CANNE = 5             # k de la Canne à pêche (spot 563) : flag 29 lu « Canne reçue » (objets_cles_v11 §19)
VERROU_MODELE_ZERO = 6       # k de la Modèle zéro (spot 564) : commande 0x3CEF (objets_cles_v11 §19.4)
VERROU_VELO = 12             # k du verrou du Vélo (bit TBox 570 de la réserve : jamais posé, aucun spot)
VERROU_RANGS = 18            # k du verrou des rangs de montre (réserve 18..23 : aucun spot)
VERROU_RANGS_D = 19          # mode « portes D » du verrou des rangs (graine récente : 4 exemplaires D, C, B, A)
VERROU_RANG_REEL = 20        # mode « rang réel » du verrou des rangs (slot_data format 20, objets_cles_v11 §17)
VERROU_VELO_REEL = 21        # mode « vélo réel » du verrou du Vélo (slot_data format 21, objets_cles_v11 §15 bis)
VERROUS_PROGRESSIFS = frozenset({VERROU_RANGS})   # recu[k] = compteur (le client y écrit le nombre reçu)
NB_COMPTEURS_VERROUS = 24    # diagnostic du jeu : k < 8 à +0x20 / +0x40, 8..15 à +0x68 / +0x88, 16..23 à +0xA8 / +0xC8
                             # (0 si jeu antérieur)
OFF_PARTAGE, TAILLE_PARTAGE = 0x5000, 0x1000         # page de l'applet clavier (jeu seulement)
OFF_NOMS, CAP_NOMS, TAILLE_NOM, NOM_TEXTE = 0x6000, 256, 64, 56   # noms de vitrine (J5)
# Suite de la table des noms de vitrine (§13bis, fix/nom-don-script) : la table du §13 n'a que 256 places, une graine
# « tout activé » en multimonde a plus de 400 noms (coffres, dons de script, distributeurs). Places 256.. dans une table
# à part (zone agrandie à 0x28000, version inchangée) : en-tête ApNoms2Entete (0x40) à 0x27FC0 {publie « ANM2 » (J),
# capacite (J), offset (J), nombre (C, écrit EN DERNIER)}, entrées ApNom (même format) à 0x24000. La capacité publiée
# dans l'en-tête principal reste 256 (un client antérieur ne déborde jamais) ; jeu antérieur : rien à 0x24000, le
# client garde les 256 noms les plus utiles (dons de script d'abord, locations pas encore faites).
TAILLE_ZONE_NOMS2 = 0x28000
OFF_NOMS2, CAP_NOMS2, OFF_NOMS2_ENTETE = 0x24000, 255, 0x27FC0
NOMS2_PUBLIE = int.from_bytes(b"ANM2", "little")
NOMS2_OFF_NOMBRE = 0x0C


def noms2_disponible(h) -> bool:
    """Zone assez grande pour la suite de la table des noms (un jeu antérieur n'a rien à 0x24000 : ne JAMAIS y
    écrire) ; le mot `publie` doit encore être lu (`noms2_publie`)."""
    return getattr(h, "taille_zone", 0) >= TAILLE_ZONE_NOMS2


def noms2_publie(brut: bytes) -> int:
    """Capacité de la suite publiée par le jeu (0 : absente), d'après les 16 premiers octets de son en-tête."""
    if len(brut) < 16:
        return 0
    publie, capacite, offset, _ = struct.unpack_from("<4I", brut)
    if publie != NOMS2_PUBLIE or offset != OFF_NOMS2:
        return 0
    return min(capacite, CAP_NOMS2)
# v5 (docs/systemes/archipelago_boite.md §21, archipelago_quetes.md §8) : récompenses de quête. En-tête (0x40 octets) :
# valide (C, écrit en dernier), compile (J : bit 31 publié, bit 0 substitution compilée), substitutions (J), derniere
# (J : n° | mode << 8) ; puis une entrée de 80 octets par n° de quête (index de Q + 4) : affiche, etiquette, drapeaux,
# utilisations (J), texte du nom de vitrine (56 octets).
VERSION_RECOMPENSES = 5
TAILLE_ZONE_V5 = 0xE000
OFF_QUETES, OFF_QUETES_TABLE, CAP_QUETES, TAILLE_QUETE, QUETE_TEXTE = 0xA000, 0xA040, 192, 80, 56
QUETE_VALIDE, QUETE_DONNER = 0x01, 0x02
QUETES_COMPILE, QUETES_PUBLIE = 0x01, 0x80000000
RECOMPENSE_FIXE, RECOMPENSE_CHOIX, RECOMPENSE_DONNE = 0x01, 0x02, 0x04
EVT_RECOMPENSE = 5
# v6 (docs/systemes/archipelago_boite.md §22, archipelago_rando_yokai.md) : randomizer de Yo-kai. En-tête (0x40 octets)
# à 0xE000 : valide (C, génération à appliquer, écrite en dernier), compile (J), table_gen (C), sigma_nombre / beta_nombre
# (C, u16), w_nombre (C), empreinte (C), gen_carte / gen_commune (J), compteurs (J) ; σ (paires u32 triées par origine),
# β (idem, bases), W (u32 triés). Écriture (jeu arrêté) : table_gen = 0, tables et nombres, table_gen, puis valide.
VERSION_RANDO = 6
TAILLE_ZONE_V6 = 0x12000
OFF_RANDO, OFF_RANDO_SIGMA, OFF_RANDO_BETA, OFF_RANDO_W = 0xE000, 0xE040, 0xE840, 0xF040
CAP_RANDO_SIGMA, CAP_RANDO_BETA, CAP_RANDO_W = 256, 256, 2048
OFF_RANDO_PRIVE, OFF_RANDO_MARQUES, CAP_RANDO_MARQUES = 0x11040, 0x11100, 0xF00
RANDO_PUBLIE, RANDO_RENCONTRES, RANDO_LOUPE = 0x80000000, 0x01, 0x02
# v10 (§22.4, archipelago_rando_yokai.md §11) : mélange PAR RENCONTRE (zone agrandie à 0x24000). En-tête : p_nombre
# (+0x3C, u16 ; 0 = mélange σ) et especes_nombre (+0x3E, u16). Table des espèces à 0x20000 ({u32 CHARA_PARAM, u32
# CHARA_BASE} par id), entrées P à 0x20800 (u32 triés par clé = index dans W << 3 | place j ; bit 14 = 1er combattant ;
# id d'origine bits 16-23, id en jeu bits 24-31). Bit RANDO_PAR_RENCONTRE de `compile` : le jeu sait les appliquer.
VERSION_RANDO_RENCONTRE = 10
TAILLE_ZONE_V10 = 0x24000
OFF_RANDO_ESPECES, CAP_RANDO_ESPECES, OFF_RANDO_P, CAP_RANDO_P = 0x20000, 256, 0x20800, 2048
RANDO_PAR_RENCONTRE = 0x04
# Garde-fou « loupe jamais vide » (archipelago_rando_yokai.md §14.3) : bit de `compile` ; le jeu ne réécrit la base d'un
# point de loupe que si la loupe peut montrer la nouvelle espèce dans le décor du point. Compteurs (jeu seulement) dans
# ApRandoPrive : bases refusées (+0x4C) et bases non réécrites faute de watchmap_common chargé (+0x50).
RANDO_LOUPE_DECOR = 0x08
# V3, mélange « partout » (version 5, archipelago_v3_melange_partout.md) : bit de `compile` ; les entrées P n° 2048 et
# suivantes (jusqu'à CAP_RANDO_P_TOTAL) sont dans la zone σ / β (inutilisée par le mélange par rencontre). Sans ce bit,
# jamais plus de CAP_RANDO_P entrées.
RANDO_P_ETENDU = 0x10
OFF_RANDO_P2, CAP_RANDO_P2 = OFF_RANDO_SIGMA, 1024
CAP_RANDO_P_TOTAL = CAP_RANDO_P + CAP_RANDO_P2
OFF_RANDO_LOUPES_REFUSEES, OFF_RANDO_LOUPES_SANS_COMMUNE = 0x11040 + 0x4C, 0x11040 + 0x50
# V3, lot M2a-bis (archipelago_v3_melange_partout.md §8) : bit de `compile` ; le jeu relit les bases des points de loupe
# de la carte en cours sur le terrain stable quand le mélange est écrit (ou retiré) après le chargement de la carte (la
# loupe montrait l'espèce d'origine jusqu'au changement de carte). Jeu seulement (ApRandoPrive) : table suivie (+0x54),
# génération appliquée à ses bases (+0x58), relectures faites (+0x5C). Aucune écriture du client.
RANDO_LOUPE_TARDIVE = 0x20
OFF_RANDO_LOUPE_CTX, OFF_RANDO_LOUPE_GEN, OFF_RANDO_LOUPES_TARDIVES = 0x11040 + 0x54, 0x11040 + 0x58, 0x11040 + 0x5C
# V3, lot M2a-bis (mélange version 6 : spots, jusqu'à ~262 espèces) : bit de `compile` ; l'id d'espèce EN JEU d'une
# entrée P a un 9e bit (bit 15, RANDO_P_EN_JEU_HAUT) et les espèces d'id 256 et suivants sont dans une 2e table
# (OFF_RANDO_ESPECES2, CAP_RANDO_ESPECES2 au plus) ; l'id d'ORIGINE reste sur 8 bits (espèces d'origine numérotées en
# premier). Sans ce bit, jamais plus de CAP_RANDO_ESPECES espèces.
RANDO_ESPECES_ETENDU = 0x40
RANDO_P_EN_JEU_HAUT = 0x8000
OFF_RANDO_ESPECES2, CAP_RANDO_ESPECES2 = 0x23800, 32
CAP_RANDO_ESPECES_TOTAL = CAP_RANDO_ESPECES + CAP_RANDO_ESPECES2
RANDO_P_CLE, RANDO_P_PREMIER = 0x3FFF, 0x4000
RANDO_GEN_AUCUNE, RANDO_GEN_IGNOREE = 0xFFFFFFFF, 0xFFFFFFFE
RANDO_SUIVIS = 8
RANDO_ENTETE = ("valide", "compile", "table_gen", "sigma_nombre", "beta_nombre", "w_nombre", "empreinte", "gen_carte",
                "gen_commune", "modifies", "analyses", "loupes", "erreurs", "derniere", "analyses_loupe", "tardives",
                "p_nombre", "especes_nombre")
# v7 (docs/systemes/archipelago_boite.md §24, archipelago_rando_boss.md §9) : randomizer des boss. En-tête (0x40 octets)
# à 0x12000 : valide (C, écrite en dernier), compile (J), table_gen (C), b_nombre / n_nombre (C, u16), empreinte (C),
# gen_carte / gen_commune (J), compteurs (J) ; B = {u32 place, u32 donneur} triées par place (boss à script) ; N =
# {u32 place, u32 origine, u32 cible, u32 0} triées par place (boss sans script). Même protocole d'écriture que §22.
VERSION_BOSS = 7
TAILLE_ZONE_V7 = 0x16000
OFF_BOSS, OFF_BOSS_B, OFF_BOSS_N = 0x12000, 0x12040, 0x12240
CAP_BOSS_B, CAP_BOSS_N = 64, 16
OFF_BOSS_PRIVE, OFF_BOSS_INSTANT, CAP_BOSS_INSTANT, OFF_BOSS_SAUV, CAP_BOSS_SAUV = 0x12400, 0x12480, 48, 0x14000, 96
TAILLE_INSTANT, TAILLE_SAUV = 0x90, 0x4C
BOSS_PUBLIE, BOSS_COMPILE = 0x80000000, 0x01
BOSS_NOM, BOSS_MEMBRES = 16, 6
BOSS_ENTETE = ("valide", "compile", "table_gen", "b_nombre", "n_nombre", "empreinte", "gen_carte", "gen_commune",
               "places", "especes", "restaurees", "instantanes", "erreurs", "derniere", "tardives", "manquants",
               "m_nombre", "forces")
# V3, force des boss adaptée à leur place (branche ap/v3-boss-force, reprise de ap/boss-adaptes ;
# archipelago_rando_boss.md §15-§16, archipelago_boite.md §49) : bit BOSS_FORCE de `compile` (absent : jeu antérieur ou
# --define YKW2_AP_SANS_BOSS_FORCE : le client n'écrit pas M et avertit) ; m_nombre (C, u16 +0x3C, écrit avec B / N),
# forces (J, u16 +0x3E) ; table M = {u32 place, s16 m[5] (PV, For, Esp, Déf, Vit en %), u16 0} triée par place, à
# 0x22800 (espace libre après les entrées P de la v10, réservé depuis le lot des invités ; zone inchangée).
BOSS_FORCE = 0x02
OFF_BOSS_M, CAP_BOSS_M = 0x22800, 80
# v8 (docs/systemes/archipelago_boite.md §25, archipelago_deathlink.md) : DeathLink, dans la zone de la v7 (taille
# inchangée). ApMort (0x40 octets) à 0x15F00 : compile (J), demande (C, écrite EN DERNIER), ident (C, identifiant de
# partie de la sauvegarde visée), faite (J), etat (J), compteurs (J). En-tête +0x90 `defaites` (J) : défaites RÉELLES
# du joueur depuis le lancement (jamais une défaite forcée par une mort reçue).
VERSION_MORT = 8
OFF_MORT, TAILLE_MORT = 0x15F00, 0x40
MORT_PUBLIE, MORT_COMPILE = 0x80000000, 0x01
MORT_ETATS = {0: "aucune", 1: "en attente", 2: "défaite forcée en cours", 3: "fenêtre affichée",
              4: "fenêtre fermée, retour au point de reprise dû"}
MORT_REPORTS = [(0x01, "pas de partie"), (0x02, "ni terrain ni combat"),
                (0x04, "combat jamais forcé (en ligne, règle 3/15) ou issue déjà décidée"),
                (0x08, "début ou fin de combat"), (0x10, "évènement / vélo"), (0x20, "carte"),
                (0x40, "fenêtre de la mort ajoutée ou ouverte")]
MORT_CHAMPS = ("compile", "demande", "ident", "faite", "etat", "executees", "combat", "terrain", "abandonnees",
               "attente", "motif", "ignorees", "fin_vue", "forcee", "images_combat", "images_sur")
MORT_IMAGES_COMBAT, MORT_IMAGES_TERRAIN = 150, 30
MORT_HASH_DEFAITES = 0xEE5E8CA9
# Fenêtre de la mort reçue sur le terrain (archipelago_deathlink.md §4ter) : fenêtre d'information du jeu « Vous êtes
# tombé... (DeathLink de <joueur>) » par la file de fenêtres du terrain, fermée par le joueur, puis retour au point de
# reprise (repli : même retour sans message). Bit MORT_FENETRE de `compile` ; ApMortFenetre (0xC0 octets) à
# OFF_MORT_FENETRE : `source` (C, MORT_SOURCE octets, nom du joueur à l'origine, écrit AVANT `demande` et seulement si le
# jeu publie MORT_FENETRE ; vide : texte sans nom), puis état privé du jeu et `texte` affiché. Taille de zone et version
# inchangées. L'ancien « combat de défaite » (bit 0x02, mêmes octets) est retiré : le client n'écrit rien dans ces octets
# pour un jeu qui ne publie pas MORT_FENETRE.
MORT_ECRAN_ANCIEN, MORT_FENETRE = 0x02, 0x04
MORT_ETAT_FENETRE, MORT_ETAT_RETOUR, MORT_REPORT_FENETRE = 3, 4, 0x40
MORT_TEXTE_HASH = 0x3279D626                        # crc32("ap_deathlink_fenetre") : faux label de texte de la fenêtre
OFF_MORT_FENETRE, TAILLE_MORT_FENETRE = 0x15F40, 0xC0
MORT_SOURCE, MORT_TEXTE = 0x30, 0x60
MORT_NOM_MAX = 16                                   # caractères du nom montré (nom de slot AP : 16 au plus)
MORT_IMAGES_OUVERTURE, MORT_ESSAIS_FENETRE = 90, 3
MORT_FEN_AUCUNE, MORT_FEN_AJOUTEE, MORT_FEN_OUVERTE = 0, 1, 2
MORT_FEN_ETATS = {0: "aucune", 1: "ajoutée (ouverture attendue)", 2: "ouverte (appui attendu)"}
MORT_FENETRE_CHAMPS = ("etat", "images", "fenetres", "vue", "repli", "essais", "montrees", "annulees", "replis",
                       "textes", "demande")         # u32 à partir de +MORT_SOURCE
FENETRE_TEXTE = 0                                   # type d'entrée de la file du jeu : texte d'un label, sans icône
# Diagnostic du forçage en combat (archipelago_deathlink.md §3bis, boîte §25.5) : ApMortDiag (0x40 octets) à
# OFF_MORT_DIAG, juste avant ApMort (octets libres de la zone v7 : taille et version inchangées), tenu par le jeu
# seulement si `compile` porte MORT_DIAG ; lu par `ap_boite_test.py morts`, jamais par le client (aucune charge GDB).
# `refus` : dernier motif pour lequel la défaite n'a pas été forcée dans un combat pendant qu'une mort attendait ;
# `refus_masque` : motifs vus pour la demande `refus_demande` (bit 1 << motif) ; `attendus` : combats finis sans
# défaite forcée pendant qu'une mort attendait (elle s'exécute alors sur le terrain).
MORT_DIAG = 0x08
OFF_MORT_DIAG, TAILLE_MORT_DIAG = 0x15EC0, 0x40
MORT_DIAG_CHAMPS = ("refus", "refus_demande", "refus_masque", "refus_rencontre", "refus_octets", "refus_regles",
                    "refus_images", "attendus", "attendu_motif", "attendu_rencontre", "forcees", "forcee_demande",
                    "forcee_rencontre", "forcee_drapeaux", "forcee_images", "manquees")
(MORT_REFUS_AUCUN, MORT_REFUS_ABSENT, MORT_REFUS_EN_LIGNE, MORT_REFUS_REGLE_2A, MORT_REFUS_RESULTAT,
 MORT_REFUS_DECIDE, MORT_REFUS_INTRO, MORT_REFUS_TERMINE, MORT_REFUS_APPEL) = range(9)
MORT_REFUS = {
    MORT_REFUS_AUCUN: "aucun",
    MORT_REFUS_ABSENT: "combat pas encore créé (chargement)",
    MORT_REFUS_EN_LIGNE: "combat en ligne / entre joueurs (G+0x21, G+0x2F)",
    MORT_REFUS_REGLE_2A: "règle 3/15 (G+0x2A) : combat entre joueurs ou visiteur de ev98_0100",
    MORT_REFUS_RESULTAT: "résultat du combat déjà écrit (combat fini)",
    MORT_REFUS_DECIDE: "issue déjà décidée par les règles (victoire décidée / forcée, défaite déjà forcée)",
    MORT_REFUS_INTRO: "introduction du combat (moins de 150 images)",
    MORT_REFUS_TERMINE: "combat terminé, résultat pas encore écrit",
    MORT_REFUS_APPEL: "FUN_00456E40 a refusé",
}
MORT_REFUS_REPORT = {MORT_REFUS_EN_LIGNE: 0x04, MORT_REFUS_REGLE_2A: 0x04, MORT_REFUS_DECIDE: 0x04}   # sinon 0x08
MORT_DIAG_SANS_PENALITE = 0x01                      # forcee_drapeaux : combat à règle 3/18 (G+0x2B)
# v9 (docs/systemes/archipelago_boite.md §26, archipelago_boutiques.md §8) : boutiques (zone agrandie à 0x20000). En-tête
# ApBoutiquesEntete (0x40 octets) à 0x16000 : valide (C, écrit EN DERNIER), compile (J), nombre (C), compteurs (J) ;
# table de 320 entrées ApBoutique (80 octets) triées par article à 0x16040 : article, affiche (0 = vitrine), etiquette
# (location), bit (u16), drapeaux, utilisations (J), texte (56 octets). Évènement ACHAT (6) : id = article, valeur =
# objet montré, valeur2 = prix payé, etiquette = location, index = bit, drapeaux 0x01 bit posé / 0x02 surplus.
# Évènement BOUTIQUE (7, indices, archipelago_boutiques.md §10) : à l'ouverture (2001), bits des articles AP posés ET
# visibles (condition d'affichage vraie), BOUTIQUE_BITS_EVT par évènement : deux u16 dans chacun de id, valeur,
# valeur2, etiquette, index (bits pairs en bas), BOUTIQUE_BIT_AUCUN = vide ; quantite = nombre de bits ; drapeaux
# 0x01 = dernier évènement de l'ouverture. Jeu sans le bit BOUTIQUES_INDICES dans `compile` : aucun indice
# automatique (rien d'autre ne change).
VERSION_BOUTIQUES = 9
TAILLE_ZONE_V9 = 0x20000
OFF_BOUTIQUES, OFF_BOUTIQUES_TABLE, CAP_BOUTIQUES, TAILLE_BOUTIQUE, BOUTIQUE_TEXTE = 0x16000, 0x16040, 320, 80, 56
OFF_BOUTIQUES_PRIVE, OFF_BOUTIQUES_LIGNES, BOUTIQUES_LIGNES = 0x1C500, 0x1C540, 80
BOUTIQUES_PUBLIE, BOUTIQUES_COMPILE, BOUTIQUE_VALIDE = 0x80000000, 0x01, 0x01
BOUTIQUES_INDICES = 0x02
BOUTIQUE_BITS_EVT, BOUTIQUE_BIT_AUCUN, BOUTIQUE_EVT_DERNIER = 10, 0xFFFF, 0x01
BOUTIQUE_CHAMPS_BITS = ("id", "valeur", "valeur2", "etiquette", "index")
ACHAT_BIT_POSE, ACHAT_SURPLUS = 0x01, 0x02
EVT_ACHAT = 6
EVT_BOUTIQUE = 7
BOUTIQUES_ENTETE = ("valide", "compile", "nombre", "achats", "dernier", "ouvertes", "lignes", "ignorees", "surplus",
                    "types_masques", "annonces")
# Bits persistants « premier achat fait » : flags octets globaux NON définis (P + 0x144 + index) ; bit k -> octet
# BOUTIQUE_OCTETS[k // 8], bit k % 8 (même liste que AP_BOUTIQUE_OCTETS de boite.h, vérifiée par --selftest).
BOUTIQUE_OCTETS = (53, 54, 55, 69, 70, 74, 75, 82, 83, 84, 85, 86, 87, 88, 89, 90, 121, 122, 123, 124, 125, 126, 127,
                   607, 608, 609, 610, 611, 612, 613, 614, 615, 616, 10, 58, 99, 100, 344, 387, 599)
BOUTIQUE_BITS = 8 * len(BOUTIQUE_OCTETS)          # 320 (sans 396 ni 449, voisins des octets wantedNN)
P_FLAGS_OCTETS = 0x144
# Fenêtre « objet obtenu » des checks sans affichage (docs/systemes/archipelago_boite.md §27, archipelago_anim_objet.md) :
# dans la zone v9 (version et taille inchangées), fonction 29 de `compiles` (FONCTION_ANIM : sans elle, rien n'est écrit).
# En-tête ApAnimEntete (0x40 octets) à 0x1FC80 : ecrites (C, écrit EN DERNIER), traitees (J), montrees, ecartees,
# annulees, etat, motif, images, etiquette, fenetres, perdues (J) ; puis 8 entrées ApAnim (80 octets) à 0x1FCC0, entrée n
# (1, 2, …) à la place (n - 1) % 8 : numero, etiquette (location), affiche (0 = vitrine), ident (identifiant de partie),
# quantite (u16), drapeaux, texte (56 octets, nom de la vitrine). Le client n'écrit jamais au-delà de traitees + 8.
FONCTION_ANIM = 29
OFF_ANIM, OFF_ANIM_TABLE, CAP_ANIM, TAILLE_ANIM, ANIM_TEXTE = 0x1FC80, 0x1FCC0, 8, 80, 56
ANIM_ENTETE = ("ecrites", "traitees", "montrees", "ecartees", "annulees", "etat", "motif", "images", "etiquette",
               "fenetres", "perdues")
ANIM_ETATS = {0: "aucune", 1: "attente du moment sûr", 2: "ajoutée à la file du jeu", 3: "fenêtre ouverte"}
ANIM_REPORTS = [(0x01, "pas de partie"), (0x02, "terrain pas au sommet"), (0x04, "évènement / sous-état"),
                (0x08, "carte"), (0x10, "fenêtre du jeu"), (0x20, "mort en attente")]
ANIM_IMAGES_SURES, ANIM_IMAGES_OUVERTURE = 30, 90
NOTIF_AUTO_MESSAGE = 5
POLITIQUE_MARQUER = 0x04
COFFRE_PAR_INDEX = 0x04
EVT_OBJET_SUBSTITUE, EVT_OBJET_BIT_POSE = 0x04, 0x08
PROGRESSION_CHAPITRE, PROGRESSION_VICTOIRE, PROGRESSION_APRES_JEU = 0x01, 0x02, 0x04
HASH_FLAG_FIN = 0x176F56BB
CHAPITRE_APRES_JEU = 11
TBOX_SPOT_PREMIER, TBOX_NOMBRE = 558, 576
# Bits de check des dons de script RÉPÉTABLES (PNJ du Musée : Poster, Bobine, Y-Cola, Affiche, Louloutre) : tant que le
# bit n'est pas posé, le jeu lit l'objet d'origine « non possédé » (IsHaveItem, objets_cles_v11 §19.3)
TBOX_REPETABLE_PREMIER, TBOX_REPETABLE_DERNIER = 571, 575
SCRIPT_DONNER, SCRIPT_BIT_AUCUN = 0x01, 0xFFFF
VITRINE_DEFAUT = 0xA0531A08   # « Important Item 20 » (iky2020), jamais donné
# v4 : liaison de la sauvegarde (docs/systemes/archipelago_boite.md §11.2, §11.3)
VERSION_LIAISON = 4           # premier jeu qui ne marque une sauvegarde QUE sur demande explicite
LIAISON_MANUELLE = 0x8000     # bit 15 de la clé de liaison (P+0x3B6) : sauvegarde existante liée par le joueur
LIAISON_ARMEE = 0x01          # liaison_manuelle (jeu v4 à v6) : « lier la prochaine sauvegarde » armé (écran, X puis X)
#                               depuis le 2026-09-28 : liaison manuelle supprimée (jeu : clé manuelle refusée ; client :
#                               jamais écrite) ; LIAISON_MANUELLE sert encore à reconnaître une sauvegarde liée avant
PAS_NEUVE = 100               # partie neuve : chapitre 0, ou chapitre 1 et pas_scenario < 100
IMAGES_FENETRE = 900
SAISIE_OUVERTE, SAISIE_VALIDEE, SAISIE_ANNULEE, SAISIE_ERREUR = 1, 2, 3, 4
CFG_SERVEUR, CFG_SLOT, CFG_MDP, CFG_MDP_INCHANGE = 0x01, 0x02, 0x04, 0x08
CNX_DEMANDE_SAISIE, CNX_MESSAGE, CNX_EFFACER_MDP = 0x01, 0x02, 0x04
ETATS_CONNEXION = {0: "client absent", 1: "non configuré", 2: "connexion", 3: "connecté", 4: "erreur",
                   5: "déconnecté"}
TYPES_DON = {"objet": 1, "argent": 2, "yokai": 3}
NOMS_DON = {v: k for k, v in TYPES_DON.items()}
CODES = {0: "OK", 1: "TYPE_INCONNU", 2: "OBJET_INCONNU", 3: "ECHEC_DON", 4: "PARTIE", 5: "QUANTITE", 6: "NON_LIEE"}
BITS_ETAT = [(0x01, "partie"), (0x02, "terrain"), (0x04, "stable"), (0x08, "BLOQUE"), (0x10, "attente"),
             (0x20, "pause"), (0x80, "lieu"), (0x100, "position"), (0x200, "amis_combat"), (0x400, "en_combat"),
             (0x800, "loupe"), (0x1000, "loupe_cible")]
EVTS = {1: "COFFRE", 2: "OBJET_JEU", 3: "DON", 4: "DON_ECHEC", 5: "RECOMPENSE", 6: "ACHAT", 7: "BOUTIQUE",
        8: "INVITE", 9: "INVITE_CHAMBRE"}
COFFRE_AFFICHAGE_SEUL, COFFRE_UNE_FOIS = 0x01, 0x02
PORT_AZAHAR = 24689           # CITRA_GDB_PORT du mod (yokaiwatch2/constants.py)

# En-tête : (nom, offset, format struct)
ENTETE = [
    ("magic", 0x00, "I"), ("version", 0x04, "H"), ("taille_entete", 0x06, "H"), ("taille_zone", 0x08, "I"),
    ("dons_off", 0x0C, "H"), ("dons_capacite", 0x0E, "H"), ("journal_off", 0x10, "H"),
    ("journal_capacite", 0x12, "H"), ("coffres_off", 0x14, "H"), ("coffres_capacite", 0x16, "H"),
    ("taille_don", 0x18, "H"), ("taille_evt", 0x1A, "H"), ("taille_coffre", 0x1C, "H"),
    ("liaison_sauvegarde", 0x1E, "H"),
    ("images", 0x20, "I"), ("etat", 0x24, "I"), ("compteur", 0x28, "I"), ("ident_sauvegarde", 0x2C, "I"),
    ("dernier_numero", 0x30, "I"), ("dernier_resultat", 0x34, "I"), ("dernier_code_erreur", 0x38, "I"),
    ("numero_erreur", 0x3C, "I"), ("dons_traites", 0x40, "I"), ("journal_ecrit", 0x44, "I"),
    ("journal_perdus", 0x48, "I"), ("adresse_p", 0x4C, "I"), ("adresse_joueur", 0x50, "I"),
    ("images_terrain", 0x54, "I"),
    ("notifs_off", 0x58, "H"), ("notifs_capacite", 0x5A, "H"), ("taille_notif", 0x5C, "H"),
    ("notif_texte_max", 0x5E, "H"), ("notifs_affichees", 0x60, "I"), ("notif_etat", 0x64, "I"),
    ("notif_restant", 0x68, "I"), ("notifs_auto_ecrites", 0x6C, "I"), ("notifs_auto_perdues", 0x70, "I"),
    ("notifs_montrees", 0x74, "I"),
    ("config_off", 0x78, "H"), ("connexion_off", 0x7A, "H"), ("saisie_etat", 0x7C, "I"),
    # lieu du joueur (branche ap/carte-suivi, §29) : valides SEULEMENT si ETAT_LIEU (ces 12 octets étaient privés dans
    # un jeu antérieur) ; pos_x / pos_z : bits d'un flottant 32 bits (`lieu_publie`)
    ("carte", 0x80, "I"), ("pos_x", 0x84, "I"), ("pos_z", 0x88, "I"),
    ("prive_auto_lu", 0x8C, "I"), ("defaites", 0x90, "I"),
    ("ecran_ouvert", 0x94, "I"), ("chapitre", 0x98, "H"), ("pas_scenario", 0x9A, "H"), ("progression", 0x9C, "I"),
    ("spots", 0xA0, "I"), ("scripts_off", 0xA4, "H"), ("scripts_capacite", 0xA6, "H"), ("noms_off", 0xA8, "H"),
    ("noms_capacite", 0xAA, "H"), ("taille_nom", 0xAC, "H"), ("nom_texte_max", 0xAE, "H"),
    ("vitrine_etiquette", 0xB0, "I"), ("substitutions", 0xB4, "I"), ("vitrine_off", 0xB8, "H"),
    ("prive_off", 0xBA, "H"), ("verrous_off", 0xBC, "H"), ("verrous_capacite", 0xBE, "H"),
    ("journal_lu", 0xC0, "I"), ("coffres_nombre", 0xC4, "I"), ("ident_partie", 0xC8, "I"),
    ("politique", 0xCC, "I"), ("pause", 0xD0, "I"), ("client_images", 0xD4, "I"),
    ("notif_duree_auto", 0xD8, "I"), ("notif_langue", 0xDC, "I"),
    ("scripts_nombre", 0xE0, "I"), ("noms_nombre", 0xE4, "I"), ("vitrine", 0xE8, "I"),
    # v4
    ("liaison_demande", 0xEC, "I"), ("liaison_terrain", 0xF0, "I"), ("liaison_cle", 0xF4, "H"),
    # fenêtre d'amitié en combat (§53) : valide SEULEMENT si ETAT_AMIS_COMBAT (avant : `reserve_f6`, toujours 0)
    ("amis_numero", 0xF6, "H"),
    ("terrain_numero", 0xF8, "I"), ("liaison_manuelle", 0xFC, "I"),
    # loupe plus parlante (§54) : mêmes octets que `liaison_manuelle` (jeu v4 à v6, bit 0 jamais posé depuis), valides
    # SEULEMENT si ETAT_LOUPE ; toujours pair (le bit 0 LIAISON_ARMEE n'y est donc jamais lu à 1)
    ("loupe_numero", 0xFC, "I"),
]
CHAMP = {n: (o, f) for n, o, f in ENTETE}


def lire_mort(b: bytes) -> dict:
    """ApMort (v8) : les 0x40 octets à OFF_MORT (ou un préfixe : champs présents seulement)."""
    return {n: struct.unpack_from("<I", b, 4 * i)[0] for i, n in enumerate(MORT_CHAMPS) if 4 * i + 4 <= len(b)}


def lire_mort_fenetre(b: bytes) -> dict:
    """ApMortFenetre : les 0xC0 octets à OFF_MORT_FENETRE (source, état privé du jeu, texte affiché)."""
    d = {n: struct.unpack_from("<I", b, MORT_SOURCE + 4 * i)[0] for i, n in enumerate(MORT_FENETRE_CHAMPS)}
    d["source"] = b[:MORT_SOURCE].split(b"\0")[0]
    d["texte"] = b[0x60:0x60 + MORT_TEXTE].split(b"\0")[0]
    return d


def mort_diag(b: bytes) -> bool:
    """Diagnostic du forçage en combat tenu par le jeu : bit MORT_DIAG du champ `compile` publié."""
    c = struct.unpack_from("<I", b, 0)[0]
    return bool(c & MORT_PUBLIE) and bool(c & MORT_DIAG)


def lire_mort_diag(b: bytes) -> dict:
    """ApMortDiag : les 0x40 octets à OFF_MORT_DIAG."""
    return {n: struct.unpack_from("<I", b, 4 * i)[0] for i, n in enumerate(MORT_DIAG_CHAMPS)}


def texte_mort_refus(masque: int) -> str:
    """Motifs d'un masque de refus (bit 1 << motif), en clair."""
    return " ; ".join(t for k, t in MORT_REFUS.items() if k and masque >> k & 1) or "-"


def mort_fenetre(b: bytes) -> bool:
    """Fenêtre de la mort sur le terrain compilée : bit MORT_FENETRE du champ `compile` publié."""
    c = struct.unpack_from("<I", b, 0)[0]
    return bool(c & MORT_PUBLIE) and bool(c & MORT_FENETRE)


def enc_mort_source(nom: str | None) -> bytes:
    """Champ `source` d'ApMortFenetre : nom du joueur à l'origine (une ligne, MORT_NOM_MAX caractères au plus, UTF-8
    terminé par 0, jamais coupé au milieu d'un caractère) ; None, vide ou « ? » : champ nul (texte sans nom)."""
    nom = " ".join((nom or "").split())
    if nom == "?":
        nom = ""
    return _champ_texte(nom[:MORT_NOM_MAX], MORT_SOURCE)


def texte_mort_fenetre(source: bytes, langue: int = 0) -> bytes:
    """Texte que le jeu compose pour la fenêtre (composerTexte de deathlink.cpp) : deux lignes, nom neutralisé."""
    nom = copier_texte(bytes(source).split(b"\0")[0][:MORT_SOURCE - 1], True)
    t = b"You fell...\n(DeathLink" if langue == 1 else "Vous êtes tombé...\n(DeathLink".encode("utf-8")
    if nom:
        t += (b" from " if langue == 1 else b" de ") + nom
    return (t + b")")[:MORT_TEXTE - 1]


def mort_compile(b: bytes) -> bool | None:
    """DeathLink compilé dans le jeu : True / False, None si le champ n'est pas publié (jeu v7 ou antérieur)."""
    c = struct.unpack_from("<I", b, 0)[0]
    return None if not c & MORT_PUBLIE else bool(c & MORT_COMPILE)


def lire_entete(b: bytes) -> dict:
    return {n: struct.unpack_from("<" + f, b, o)[0] for n, o, f in ENTETE}


def champ(nom: str, valeur: int) -> tuple[int, bytes]:
    o, f = CHAMP[nom]
    return ZONE + o, struct.pack("<" + f, valeur)


def enc_don(numero: int, type_: int, hash_: int, quantite: int) -> bytes:
    return struct.pack("<IBBHIi", numero, type_, 0, 0, hash_ & 0xFFFFFFFF, quantite)


def dec_don(b: bytes) -> dict:
    n, t, _, _, h, q = struct.unpack("<IBBHIi", b)
    return {"numero": n, "type": t, "hash": h, "quantite": q}


def dec_evt(b: bytes) -> dict:
    n, t, d, q, i, v, v2, et, idx, img = struct.unpack("<IBBHIIIIII", b)
    return {"numero": n, "type": t, "drapeaux": d, "quantite": q, "id": i, "valeur": v, "valeur2": v2,
            "etiquette": et, "index": idx, "image": img}


def enc_evt(e: dict) -> bytes:
    return struct.pack("<IBBHIIIIII", e["numero"], e["type"], e["drapeaux"], e["quantite"], e["id"], e["valeur"],
                       e["valeur2"], e["etiquette"], e["index"], e["image"])


def enc_coffre(tbox: int, objet: int, quantite: int, drapeaux: int, etiquette: int, utilisations: int = 0) -> bytes:
    return struct.pack("<IIHBBI", tbox, objet, quantite, drapeaux, utilisations, etiquette)


def dec_coffre(b: bytes) -> dict:
    t, o, q, d, u, e = struct.unpack("<IIHBBI", b)
    return {"tbox": t, "objet": o, "quantite": q, "drapeaux": d, "utilisations": u, "etiquette": e}


def adr_don(numero: int) -> int:
    return ZONE + OFF_DONS + (numero % CAP_DONS) * 16


def adr_evt(numero: int) -> int:
    return ZONE + OFF_JOURNAL + ((numero - 1) % CAP_JOURNAL) * 32


def adr_notif(numero: int) -> int:
    return ZONE + OFF_NOTIFS + (numero % CAP_NOTIFS) * TAILLE_NOTIF


# --- v3 : configuration, état de connexion, dons de script, noms de vitrine ---
def _chaine(b: bytes) -> str:
    return b.split(b"\0")[0].decode("utf-8", "replace")


def _champ_texte(texte: str | bytes, taille: int) -> bytes:
    """Texte UTF-8 d'un champ de `taille` octets (terminé par 0, sans couper un caractère)."""
    b = texte.encode("utf-8") if isinstance(texte, str) else bytes(texte)
    if len(b) > taille - 1:
        b = b[:taille - 1]
        while b and b[-1] & 0xC0 == 0x80:
            b = b[:-1]
        if b and b[-1] >= 0xC0:
            b = b[:-1]
    return b.ljust(taille, b"\0")


def enc_config(revision: int, drapeaux: int, serveur: str, slot: str, mdp: str = "", revision_effacee: int = 0,
               erreur: int = 0) -> bytes:
    return (struct.pack("<IIII", revision, drapeaux, revision_effacee, erreur) + _champ_texte(serveur, 128)
            + _champ_texte(slot, 64) + _champ_texte(mdp, 48))


def dec_config(b: bytes) -> dict:
    rev, dr, eff, err = struct.unpack_from("<IIII", b)
    return {"revision": rev, "drapeaux": dr, "revision_effacee": eff, "erreur": err,
            "serveur": _chaine(b[0x10:0x90]), "slot": _chaine(b[0x90:0xD0]), "mdp": _chaine(b[0xD0:0x100])}


def enc_connexion(sequence: int, etat: int, revision_lue: int = 0, erreur: int = 0, drapeaux: int = 0,
                  client_images: int = 0, connu: int = 0, message: str = "", serveur: str = "",
                  slot: str = "") -> bytes:
    b = struct.pack("<IIIIIIII", sequence, etat, revision_lue, erreur, drapeaux, client_images, connu, 0)
    b += _champ_texte(message, NOTIF_TEXTE) + b"\0" * 8 + _champ_texte(serveur, 128) + _champ_texte(slot, 64)
    return b.ljust(TAILLE_CONNEXION, b"\0")


def dec_connexion(b: bytes) -> dict:
    seq, etat, rl, err, dr, ci, connu, _ = struct.unpack_from("<IIIIIIII", b)
    return {"sequence": seq, "etat": etat, "revision_lue": rl, "erreur": err, "drapeaux": dr, "client_images": ci,
            "connu": connu, "message": _chaine(b[0x20:0x58]), "serveur": _chaine(b[0x60:0xE0]),
            "slot": _chaine(b[0xE0:0x120])}


def enc_script(origine: int, affiche: int = 0, bit: int = SCRIPT_BIT_AUCUN, drapeaux: int = 0, etiquette: int = 0,
               utilisations: int = 0) -> bytes:
    return struct.pack("<IIHBBI", origine, affiche, bit, drapeaux, utilisations, etiquette)


def dec_script(b: bytes) -> dict:
    o, a, bit, d, u, e = struct.unpack("<IIHBBI", b)
    return {"origine": o, "affiche": a, "bit": bit, "drapeaux": d, "utilisations": u, "etiquette": e}


def enc_nom(etiquette: int, texte: str | bytes) -> bytes:
    return struct.pack("<IHBB", etiquette, 0, 0, 0) + _champ_texte(texte, NOM_TEXTE)


def dec_nom(b: bytes) -> dict:
    e, _, d, _ = struct.unpack_from("<IHBB", b)
    return {"etiquette": e, "drapeaux": d, "texte": b[8:].split(b"\0")[0]}


def enc_verrous(actifs: int, recu: dict[int, bool | int] | list[int]) -> bytes:
    """Zone des verrous (J4) : `actifs` (bit k) puis recu[k] (1 = reçu). Écrire recu (+8) AVANT actifs (+0).
    Verrou progressif (k de VERROUS_PROGRESSIFS, rangs) : recu[k] = nombre d'exemplaires reçus (plafonné à 255) ;
    un booléen y vaut 0 / 1."""
    r = bytearray(CAP_VERROUS)
    for k, v in (recu.items() if isinstance(recu, dict) else enumerate(recu)):
        if k in VERROUS_PROGRESSIFS and not isinstance(v, bool):
            r[k] = max(0, min(255, int(v)))
        else:
            r[k] = 1 if v else 0
    return (struct.pack("<II", actifs, 0) + bytes(r)).ljust(TAILLE_VERROUS, b"\0")


def dec_verrous(b: bytes) -> dict:
    """Zone des verrous : `actifs` (C), `compiles` (J, v4 §20 : bit k compilé, bit 31 liste publiée), recu[] (C),
    diagnostic du jeu (appliqués / exemptés par verrou k < 24, dernière phase plafonnée : brute, rendue ; dernier
    verrou de montre lu : rang exigé, rang AP, valeur rendue au script)."""
    actifs, compiles = struct.unpack_from("<II", b)
    d = {"actifs": actifs, "compiles": compiles, "recu": list(b[8:8 + CAP_VERROUS])}
    if len(b) >= 0xEB:
        d["appliques"] = (list(struct.unpack_from("<8I", b, 0x20)) + list(struct.unpack_from("<8I", b, 0x68))
                          + list(struct.unpack_from("<8I", b, 0xA8)))
        d["exemptes"] = (list(struct.unpack_from("<8I", b, 0x40)) + list(struct.unpack_from("<8I", b, 0x88))
                         + list(struct.unpack_from("<8I", b, 0xC8)))
        d["phase_brute"], d["phase_rendue"] = struct.unpack_from("<II", b, 0x60)
        # rangs (k = 18) : dernier verrou de montre lu (rang exigé, rang AP, valeur rendue au script : 6 = fermé)
        d["rang_exige"], d["rang_ap"], d["rang_rendu"] = b[0xE8], b[0xE9], b[0xEA]
    if len(b) >= 0xF4:
        # Yo-criminels libres (fonction 24) : dernier `wanted_no` rendu au jeu, lectures du bit 2072 rendues fausses ;
        # combats du jour libres (fonction 25) : lectures « déjà combattu aujourd'hui » rendues fausses
        d["criminel_rendu"] = b[0xEB]
        d["criminels_masques"], d["combats_libres"] = struct.unpack_from("<II", b, 0xEC)
    if len(b) >= 0xF8:
        # Bingo-kai infini (option 27) : lectures de la réserve du jour rendues 1 au lieu de 0 (0 : jeu antérieur)
        d["bingo_rendus"] = struct.unpack_from("<I", b, 0xF4)[0]
    if len(b) >= 0xFF:
        # rang réel (mode k = 20, 0 dans un jeu antérieur) : dernier rang écrit par le mod, rang réel de la sauvegarde
        # liée, fenêtre « rang » en attente, écritures, fenêtres de script filtrées, fenêtres mises en file par le mod ;
        # 0x364C neutralisée : appliques[20] ; 0x364C laissée (rang S) : exemptes[20]
        d["rang_reel_ecrit"], d["rang_reel_lu"], d["rang_fenetre"] = b[0xF8], b[0xF9], b[0xFA]
        d["rang_ecritures"], d["rang_filtrees"], d["rang_montrees"] = b[0xFC], b[0xFD], b[0xFE]
    if len(b) >= 0x100:
        # vélo réel (mode k = 21, 0 dans un jeu antérieur) : bits VELO_DIAG_* de ce que le mod a fait depuis le
        # lancement ; dons du vélo (flags posés) : appliques[21] ; objets vélo retirés : exemptes[21]
        d["velo_reel"] = b[0xFF]
    return d


def verrous_compiles(b: bytes) -> int | None:
    """Masque des verrous compilés dans le jeu, ou None si le jeu ne publie pas la liste (build antérieur à la
    v4 « verrous » : aucun verrou)."""
    c = struct.unpack_from("<I", b, 4)[0]
    return c & ~VERROUS_PUBLIES if c & VERROUS_PUBLIES else None


def options_actives(bingo_kai_infini: bool) -> int:
    """Bits d'options du joueur à poser dans `actifs` (le client les écrit avec les verrous, dans le même paquet)."""
    return (1 << OPTION_BINGO_KAI) if bingo_kai_infini else 0


def option_compilee(b: bytes, k: int) -> bool:
    """Option k compilée dans le jeu (liste publiée, bit k de `compiles`)."""
    c = verrous_compiles(b)
    return c is not None and bool(c >> k & 1)


def bingo_restant_vu(b: bytes, brut: int, sauvegarde_liee: bool = True) -> int:
    """Modèle de bingoFiltre (bingo.cpp) : réserve de tours du jour du Bingo-kai (octet 0xA45A65EC) vue par le jeu.
    Lue au moins 1 si l'option est compilée, choisie (bit 27 de `actifs`) et la sauvegarde liée ; sinon la valeur
    stockée."""
    v = dec_verrous(b)
    actif = option_compilee(b, OPTION_BINGO_KAI) and bool(v["actifs"] >> OPTION_BINGO_KAI & 1) and sauvegarde_liee
    return 1 if brut == 0 and actif else brut


def verrou_actif(b: bytes, k: int) -> bool:
    """Modèle de apVerrouActif (boite.cpp) : verrou k compilé dans le jeu, actif et objet non reçu (la condition
    « sauvegarde liée » est vérifiée à part par le jeu). Verrous à interrupteur seulement (« reçu » = octet non nul) :
    ne modélise PAS un verrou progressif (rangs de montre, k = 18 : recu[18] = nombre reçu, comparé au rang exigé,
    voir `rang_exige_vu`)."""
    v = dec_verrous(b)
    return 0 <= k < CAP_VERROUS and bool((v["compiles"] & ~VERROUS_PUBLIES) >> k & 1) \
        and bool(v["actifs"] >> k & 1) and not v["recu"][k]


def velo_vu(b: bytes, flag_brut: bool, a_velo: bool = False) -> bool:
    """Modèle de apVerrouFiltreFlag pour les flags 39 et 40 (bouton vélo du menu terrain, verrous.cpp) : valeur vue par
    le jeu. Masquée (0) si le verrou du Vélo (k = 12) s'applique, sauf si le joueur roule déjà (`a_velo` : il garde son
    bouton pour descendre)."""
    return bool(flag_brut) and (a_velo or not verrou_actif(b, VERROU_VELO))


def montee_velo_refusee(b: bytes, argument: int) -> bool:
    """Modèle de la garde 0x005336D4 (commande 0x3564, verrous.cpp) : une demande de montée (argument non nul) est
    ignorée tant que le Vélo n'est pas reçu ; la descente (0) passe toujours."""
    return argument != 0 and verrou_actif(b, VERROU_VELO)


# Vélo réel (mode k = 21, verrous.cpp apVeloReelImage, objets_cles_v11 §15 bis).
VELO_DIAG = [(0x01, "flags posés"), (0x02, "objet vélo donné"), (0x04, "objet vélo retiré"),
             (0x08, "bouton redessiné"), (0x10, "flag 40 laissé au jeu (phase >= 7-40)"), (0x20, "don de l'objet refusé")]
VELO_DIAG_FLAGS, VELO_DIAG_DONNE, VELO_DIAG_RETIRE, VELO_DIAG_BOUTON, VELO_DIAG_TEMPETE, VELO_DIAG_ECHEC = (
    m for m, _ in VELO_DIAG)
VELO_PHASE_TEMPETE = 70040   # à partir de la phase 7-40, le flag 40 est géré par le jeu (PhCmd_7_40 / PhCmd_7_70)
VELO_COULEUR_GARCON, VELO_COULEUR_FILLE = 10, 11   # couleurs des modèles par défaut (another_shop)


def velo_reel_en_vigueur(b: bytes) -> bool:
    """Mode « vélo réel » (apVeloReelImage, verrous.cpp) : verrou du Vélo (k = 12) et mode 21 compilés et actifs (la
    sauvegarde liée est vérifiée à part par le jeu)."""
    v = dec_verrous(b)
    return _verrou_en_vigueur(v, VERROU_VELO) and _verrou_en_vigueur(v, VERROU_VELO_REEL)


def velo_objet_de_la_couleur(couleur: int, garcon: bool) -> str:
    """Modèle de apVeloObjetDeLaCouleur : nom interne de l'objet vélo de la couleur enregistrée (`bicycle_color_num`)
    pour ce joueur ; couleur 0 (jamais choisie) ou hors table : modèle par défaut du genre."""
    if 1 <= couleur <= 9:
        return "iky%04d" % ((65 if garcon else 74) + couleur)
    return "iky0011" if garcon else "iky0012"


def velo_reel_evaluation(b: bytes, flag39: bool, flag40: bool, velos: int, phase: int) -> dict | None:
    """Modèle d'une évaluation de apVeloReelImage (terrain libre d'une sauvegarde liée) : état après l'évaluation,
    {flag39, flag40, velos (nombre d'objets vélo), donne, retire, ecrit} ; None hors du mode (rien n'est fait).
    Vélo reçu : flag 39 posé s'il ne l'est pas (et flag 40 avant la phase 7-40), un objet vélo donné si l'inventaire
    n'en a aucun ; pas reçu : tout objet vélo de l'inventaire est retiré, les flags ne sont jamais touchés."""
    if not velo_reel_en_vigueur(b):
        return None
    if not dec_verrous(b)["recu"][VERROU_VELO]:
        return {"flag39": flag39, "flag40": flag40, "velos": 0, "donne": False, "retire": velos > 0, "ecrit": False}
    ecrit = not flag39
    if ecrit and phase < VELO_PHASE_TEMPETE:
        flag40 = True
    return {"flag39": True, "flag40": flag40, "velos": max(velos, 1), "donne": velos == 0, "retire": False,
            "ecrit": ecrit}


RANGS_MONTRE = {1: "D", 2: "C", 3: "B", 4: "A", 5: "S"}
RANG_D, RANG_C, RANG_A, RANG_IMPOSSIBLE = 1, 2, 4, 6
RANG_S, PHASE_RANG_S = 5, 110010    # ap/rang-s-objet : rang S, phase 11-10 (fin de l'histoire, requête 28)


def _verrou_en_vigueur(v: dict, k: int) -> bool:
    return bool((v["compiles"] & ~VERROUS_PUBLIES) >> k & 1 and v["actifs"] >> k & 1)


def peche_vue(b: bytes, flag_brut: bool, liee: bool = True, reelle: bool = True) -> bool:
    """Modèle de apVerrouFiltreFlag pour le flag 29 (pêche, verrous.cpp, objets_cles_v11 §19) : valeur vue par le jeu.
    Verrou de la Canne (k = 5) en vigueur (compilé, actif, sauvegarde liée) : « Canne reçue », que le flag natif (posé
    seulement par la requête 99) le soit ou non ; sinon la valeur native. `reelle=False` : build
    YKW2_AP_SANS_CANNE_REELLE (ancien masque : le flag natif reste nécessaire)."""
    v = dec_verrous(b)
    if not (liee and _verrou_en_vigueur(v, VERROU_CANNE)):
        return bool(flag_brut)
    recu = bool(v["recu"][VERROU_CANNE])
    return recu if reelle else (recu and bool(flag_brut))


def modele_zero_vue(b: bytes, flag_natif: bool, tutoriels_finis: bool, combat_gagne: bool, liee: bool = True,
                    reelle: bool = True, garde: bool = True) -> bool:
    """Modèle de la commande 0x3CEF remplacée (0x0051C624, verrous.cpp, objets_cles_v11 §19.4), hors mémoire de combat :
    interface de la Modèle zéro dans les combats. Verrou k = 6 en vigueur : reçue -> active même avant le flag 21 (phase
    6-20), une fois les tutoriels de combat finis (flag de PhCmd_2_70 ; `garde=False` : build
    YKW2_AP_MODELE_ZERO_SANS_GARDE) ; non reçue -> flag natif, masqué après la victoire ev06_btl0040. Hors vigueur :
    flag natif. `reelle=False` : build YKW2_AP_SANS_MODELE_ZERO_REEL (ancien verrou seul)."""
    v = dec_verrous(b)
    if not (liee and _verrou_en_vigueur(v, VERROU_MODELE_ZERO)):
        return bool(flag_natif)
    if v["recu"][VERROU_MODELE_ZERO]:
        if flag_natif or not reelle:
            return bool(flag_natif)
        return bool(tutoriels_finis) or not garde
    return bool(flag_natif) and not combat_gagne


def appli_invocation_vue(b: bytes, flag_brut: bool, liee: bool = True) -> bool:
    """Modèle de apVerrouFiltreFlag pour le flag 73 (entrée 20 du menu principal, appli d'invocation par médailles) :
    vraie dès que la Modèle zéro est reçue (verrou k = 6 en vigueur), jamais masquée."""
    v = dec_verrous(b)
    return bool(flag_brut) or (liee and _verrou_en_vigueur(v, VERROU_MODELE_ZERO) and bool(v["recu"][VERROU_MODELE_ZERO]))


def possession_masquee(scripts, bits_poses, objet: int, liee: bool = True) -> bool:
    """Modèle de apBoitePossessionMasquee (boite.cpp, condition IsHaveItem d'un objet possédé, objets_cles_v11 §19.3) :
    vrai si l'objet est l'origine d'une entrée de la table des dons de script (`scripts` : dictionnaires de dec_script,
    dans l'ordre de la table) dont le bit de check est dans la réserve « répétable » et pas encore posé (`bits_poses` :
    ensemble des index TBox posés). La première entrée de cet objet décide, comme dans la substitution."""
    if not objet or not liee:
        return False
    for e in scripts:
        if e["origine"] != objet:
            continue
        return TBOX_REPETABLE_PREMIER <= e["bit"] <= TBOX_REPETABLE_DERNIER and e["bit"] not in bits_poses
    return False


def combat_memo(memo: int, loop: int) -> int:
    """Modèle de apBoiteCombatMemo : valeur de 0x3CEF figée pour le combat du loop `loop` (0 / 1), ou -1."""
    if not loop or not memo & 2 or memo & ~3 != loop & ~3:
        return -1
    return memo & 1


def combat_memoriser(memo: int, loop: int, valeur: bool) -> int:
    """Modèle de apBoiteCombatMemoriser : nouveau mot ApPrive + 0x38."""
    return (loop & ~3) | 2 | int(bool(valeur)) if loop else memo


def rang_ap(b: bytes) -> tuple[int, bool] | None:
    """Rang AP que le jeu compare aux portes de montre (apVerrouRangMontre), et mode « portes D » ; None si le verrou
    des rangs n'est pas en vigueur (non compilé ou inactif : jeu d'origine). Mode « portes D » (k = 19 compilé et
    actif, graine récente) : rang AP = recu[18] (0 aucun, 1 D … 4 A) ; sinon : D + recu[18]."""
    v = dec_verrous(b)
    if not _verrou_en_vigueur(v, VERROU_RANGS):
        return None
    portes_d = _verrou_en_vigueur(v, VERROU_RANGS_D)
    return (v["recu"][VERROU_RANGS] if portes_d else RANG_D + v["recu"][VERROU_RANGS]), portes_d


def rang_exige_vu(b: bytes, rang_exige: int) -> int:
    """Modèle de apVerrouRangMontre (verrous.cpp) : rang exigé que voit le script d'un verrou de montre (ev98_0060)
    pour ce rang exigé d'origine. Verrou des rangs compilé et actif (la sauvegarde liée est vérifiée à part par le
    jeu) et rang exigé dans les portes concernées (D, C, B, A en mode « portes D », sinon C, B, A) : si le rang AP
    (`rang_ap`) est inférieur, 6 (aucun rang réel, 0..5, ne suffit) ; sinon (et pour S) inchangé : le rang réel
    reste exigé comme d'origine."""
    r = rang_ap(b)
    if r is None:
        return rang_exige
    ap, portes_d = r
    if not (RANG_D if portes_d else RANG_C) <= rang_exige <= RANG_A:
        return rang_exige
    return rang_exige if ap >= rang_exige else RANG_IMPOSSIBLE


def rang_reel_en_vigueur(b: bytes) -> bool:
    """Mode « rang réel » (apRangReel, verrous.cpp) : verrou des rangs (k = 18) et mode 20 compilés et actifs (la
    sauvegarde liée est vérifiée à part par le jeu)."""
    v = dec_verrous(b)
    return _verrou_en_vigueur(v, VERROU_RANGS) and _verrou_en_vigueur(v, VERROU_RANG_REEL)


def rang_reel_cible(b: bytes, rang: int, rang_s: bool = False, phase: int = 0) -> int:
    """Modèle de apRangReelImage : rang réel de la montre (octet O + 0x2E) après une image de terrain d'une sauvegarde
    liée dont le rang vaut `rang`. Mode « rang réel » : max(rang, min(recu[18], plafond)) (jamais de baisse, rang S
    gardé) ; plafond A, ou S avec le mode « rang S par l'objet » (`rang_s` : k = 80 en vigueur, ap/rang-s-objet) à
    partir de la phase 11-10 (`phase` = GetPhase) ; sinon inchangé."""
    if not rang_reel_en_vigueur(b):
        return rang
    plafond = RANG_S if rang_s and phase >= PHASE_RANG_S else RANG_A
    return max(rang, min(dec_verrous(b)["recu"][VERROU_RANGS], plafond))


def rang_ecrit_par_script(b: bytes, rang: int, valeur: int, relatif: bool = False, liee: bool = True,
                          rang_s: bool = False) -> int:
    """Modèle de la garde 0x004CD6F8 (commande 0x364C, RunkUp) : rang réel après `0x364C(valeur [, relatif])` quand
    il valait `rang`. Mode « rang réel » et sauvegarde liée : une valeur finale E..A (0..4) est ignorée (le rang ne
    vient que de l'objet AP), S aussi avec le mode « rang S par l'objet » (`rang_s`, k = 80 en vigueur) ; au-dessus
    (rang S de la requête 28, après-jeu, sans ce mode) et hors du mode : écriture d'origine."""
    finale = (rang + valeur if relatif else valeur) & 0xFF
    if liee and rang_reel_en_vigueur(b) and (finale <= RANG_A or (rang_s and finale == RANG_S)):
        return rang
    return finale


def fenetre_rang_filtree(b: bytes, rang: int, liee: bool = True, rang_s: bool = False) -> bool:
    """Modèle de apRangFenetreFiltree (commande 0x35B8, type 17) : la fenêtre « rang » d'un script n'est pas mise en
    file en mode « rang réel » pour E..A, et S avec le mode « rang S par l'objet » (`rang_s`) (le mod la met en file
    lui-même quand il monte la montre)."""
    return liee and rang <= (RANG_S if rang_s else RANG_A) and rang_reel_en_vigueur(b)


# Bus du village d'Ourcival rendu (apBusOurcivalRendu, verrous.cpp ; archipelago_v3_objets_cles_2.md §12).
BUS_OURCIVAL = (39, 71, 0x887203E3)          # c04_trigger n° 89 : type, n° (RunCmd_Phase71, refus), point de t131g00
PHASE_BUS_DEBUT, PHASE_BUS_FIN = 40110, 40135
# Requête 99 (qs0099) en cours : bus rendu aussi, toutes graines (§12.6) ; phase 1 = proposée, 2 = acceptée (vaincre
# 3 Pachycoul), 3 = posséder 3 poissons, 255 = finie.
QUETE_99, QUETE_99_ACCEPTEE, QUETE_FINIE = 0x4A0FFD5B, 2, 255


def bus_ourcival_rendu(b: bytes, type_: int, n: int, ident: int, table_phase: bool, phase: int, rang: int,
                       liee: bool = True, quete99: int = 0, ident_partie: int = 1) -> bool:
    """Modèle de apBusOurcivalRendu (accroche FUN_00448988) : vrai si l'entrée retenue (type, n°, identifiant) est le
    refus du bus du village d'Ourcival et doit être ignorée (la recherche retombe sur le bus ordinaire de
    t131g00_trigger n° 2). Conditions : table de PHASE, 4-110 <= `phase` <= 4-135, sauvegarde liée, et
    - un verrou qui arrête l'histoire en 4-135 en vigueur sans son objet : Canne (k = 5) non reçue, ou mode « rang
      réel » avec un rang réel (`rang`, octet O + 0x2E) inférieur à D ;
    - ou (toutes graines) un client avec identifiant de partie (`ident_partie` non nul) et la requête 99 acceptée et
      pas finie (`quete99` = sa phase, GetQuestPhase : 2 <= phase < 255)."""
    if (type_, n, ident) != BUS_OURCIVAL or not table_phase or not liee:
        return False
    if not PHASE_BUS_DEBUT <= phase <= PHASE_BUS_FIN:
        return False
    v = dec_verrous(b)
    if _verrou_en_vigueur(v, VERROU_CANNE) and not v["recu"][VERROU_CANNE]:
        return True
    if rang_reel_en_vigueur(b) and rang < RANG_D:
        return True
    return ident_partie != 0 and QUETE_99_ACCEPTEE <= quete99 < QUETE_FINIE


def adr_script(i: int) -> int:
    return ZONE + OFF_SCRIPTS + i * TAILLE_SCRIPT


def adr_nom(i: int) -> int:
    return ZONE + OFF_NOMS + i * TAILLE_NOM


# --- v5 : récompenses de quête ---
def enc_quete(affiche: int = 0, etiquette: int = 0, drapeaux: int = QUETE_VALIDE, texte: str | bytes = b"",
              utilisations: int = 0) -> bytes:
    """Entrée de la table des récompenses de quête (80 octets) ; texte = nom de la vitrine (vide : nom par défaut)."""
    return (struct.pack("<IIBBHI", affiche & 0xFFFFFFFF, etiquette & 0xFFFFFFFF, drapeaux, utilisations, 0, 0)
            + _champ_texte(texte, QUETE_TEXTE) + bytes(8))


def dec_quete(b: bytes) -> dict:
    a, e, d, u, _, _ = struct.unpack_from("<IIBBHI", b)
    return {"affiche": a, "etiquette": e, "drapeaux": d, "utilisations": u, "texte": b[16:16 + QUETE_TEXTE].split(b"\0")[0]}


def dec_quetes_entete(b: bytes) -> dict:
    v, c, n, der = struct.unpack_from("<IIII", b)
    return {"valide": v, "compile": c, "substitutions": n, "derniere": der}


def adr_quete(numero: int) -> int:
    return ZONE + OFF_QUETES_TABLE + numero * TAILLE_QUETE


def recompenses_compilees(entete_quetes: bytes) -> bool | None:
    """Champ `compile` publié par le jeu v5 : True (substitution compilée), False (build sans, --define
    YKW2_AP_SANS_RECOMPENSES), None (non publié : jeu antérieur)."""
    c = struct.unpack_from("<I", entete_quetes, 4)[0]
    if not c & QUETES_PUBLIE:
        return None
    return bool(c & QUETES_COMPILE)


# --- fenêtre « objet obtenu » des checks sans affichage (§27) ---
def enc_anim(numero: int, etiquette: int, affiche: int = 0, ident: int = 0, quantite: int = 1,
             texte: str | bytes = b"") -> bytes:
    """Entrée de la file des fenêtres (80 octets) ; affiche = 0 : la vitrine, nommée par `texte` (vide : nom par
    défaut)."""
    return (struct.pack("<IIIIHBBI", numero & 0xFFFFFFFF, etiquette & 0xFFFFFFFF, affiche & 0xFFFFFFFF,
                        ident & 0xFFFFFFFF, quantite & 0xFFFF, 0, 0, 0) + _champ_texte(texte, ANIM_TEXTE))


def dec_anim(b: bytes) -> dict:
    n, e, a, i, q, d, _r, _r2 = struct.unpack_from("<IIIIHBBI", b)
    return {"numero": n, "etiquette": e, "affiche": a, "ident": i, "quantite": q, "drapeaux": d,
            "texte": b[24:24 + ANIM_TEXTE].split(b"\0")[0]}


def dec_anim_entete(b: bytes) -> dict:
    return dict(zip(ANIM_ENTETE, struct.unpack_from("<11I", b)))


def adr_anim(numero: int) -> int:
    """Adresse de l'entrée n (1, 2, …) de la file des fenêtres."""
    return ZONE + OFF_ANIM_TABLE + ((numero - 1) % CAP_ANIM) * TAILLE_ANIM


def anim_compilee(verrous: bytes) -> bool:
    """Fenêtre « objet obtenu » des checks compilée dans le jeu (bit 29 de `compiles`, liste publiée)."""
    return option_compilee(verrous, FONCTION_ANIM)


# --- Yo-criminels trouvables (docs/systemes/archipelago_criminels_combats_jour.md §8) ---
# Fonction 30 de `compiles` (information : aucune graine ne l'exige, le client n'écrit rien). Quand le bit est publié,
# le jeu tient un diagnostic de 0x20 octets dans sa zone privée (ApCriminels, src/archipelago/boite.h) ; ces octets
# valent 0 dans un jeu antérieur : ne les lire que si le bit est publié.
FONCTION_CRIMINELS_TROUVABLES = 30
OFF_CRIMINELS, TAILLE_CRIMINELS = OFF_PRIVE + 0x80, 0x20
CRIMINELS_MOTIFS = {0: "un criminel est posé (rien à faire)", 1: "sauvegarde non liée",
                    2: "singleton du jeu absent (transition)", 3: "Yo-criminels pas débloqués, ou fenêtre fermée",
                    4: "tous les Yo-criminels sont arrêtés", 5: "aucun emplacement, tirage déjà fait pendant ce passage",
                    6: "tirage fait"}
CRIMINELS_CAUSES = {0: "aucun", 1: "aucun emplacement posé", 2: "criminel proposé changé (arrestation complète)"}
# Octets globaux de catégorie 6 (P + 0x144 + index) et bits globaux (catégorie 0) des Yo-criminels [C]
OCTET_WANTED_NO, OCTET_WANTED_LIEU = 21, 23          # criminel stocké (écrit par le jeu), emplacement (1..30, 0 aucun)
FLAG_WANTED_OUVERT, FLAG_WANTED_FERME_1, FLAG_WANTED_FERME_2 = 69, 62, 63
FLAG_WANTED_SEMAINE, FLAG_WANTED_TOUS = 2072, 2073
# Les 5 cartes de la ville (WANTED_MAP, dans l'ordre de wanted_config) : point p (1..30) = carte (p - 1) // 6, rang
# (p - 1) % 6. Noms internes de cartes (déjà dans le dépôt : cartes du tracker), pas des données du jeu en masse.
CARTES_CRIMINELS = ("t101g00", "t103g00", "t104g00", "t105g00", "t106g00")
POINTS_PAR_CARTE = 6


def carte_du_point(point: int) -> int | None:
    """Index (0..4) de la carte de la ville du point `point` (1..30), None sinon."""
    return (point - 1) // POINTS_PAR_CARTE if 1 <= point <= len(CARTES_CRIMINELS) * POINTS_PAR_CARTE else None


def point_homologue(point: int, carte: int | None) -> int:
    """Modèle d'apCriminelsEmplacementVu (limites.cpp) : valeur de l'emplacement vue par les NPC_APPEAR quand le
    joueur est sur la carte de la ville d'index `carte` (None : hors des 5 cartes) : le point de même rang."""
    if carte is None or carte_du_point(point) is None or not 0 <= carte < len(CARTES_CRIMINELS):
        return point
    return carte * POINTS_PAR_CARTE + (point - 1) % POINTS_PAR_CARTE + 1


def points_homologues(point: int) -> list[int]:
    """Les 5 points (un par carte) où le criminel posé au point `point` est visible ; [] si aucun n'est posé."""
    if carte_du_point(point) is None:
        return []
    return [point_homologue(point, c) for c in range(len(CARTES_CRIMINELS))]


def criminels_trouvables_compiles(verrous: bytes) -> bool:
    """Yo-criminels trouvables compilés dans le jeu (bit 30 de `compiles`, liste publiée)."""
    return option_compilee(verrous, FONCTION_CRIMINELS_TROUVABLES)


def dec_criminels(b: bytes) -> dict:
    """ApCriminels (0x20 octets à OFF_CRIMINELS) : état et diagnostic du jeu."""
    terrain, carte = struct.unpack_from("<II", b, 0)
    miroirs, evaluations = struct.unpack_from("<II", b, 0x14)
    return {"terrain": terrain, "carte": carte, "carte_lieu": b[8], "dernier": b[9], "criminel": b[0xA], "lieu": b[0xB],
            "motif": b[0xC], "tirages": b[0xD], "tire_avant": b[0xE], "tire_apres": b[0xF], "tire_cause": b[0x10],
            "vu_stocke": b[0x11], "vu_rendu": b[0x12], "rafraichis": b[0x13], "miroirs": miroirs,
            "evaluations": evaluations}


# --- Invités de l'Auberge des voyageurs (docs/systemes/archipelago_invites.md §14, archipelago_boite.md §31) ---
# Zone ApInvites (0x200 octets) dans le trou de la zone v10 entre la table M de ap/boss-adaptes (0x22800..0x23000) et l'enregistreur de
# panique (0x23E00) : version et taille inchangées. `compile` (J, +0) ; le client écrit ident (+8), nombre (+0xC) et la
# liste (+0xC0, 8 octets par invité : CHARA_PARAM, n° du Médaillium u16, drapeaux u8), puis `sequence` (+4) EN DERNIER,
# et SEULEMENT si le jeu publie INVITES_COMPILE. `forcer` (+0x10) n'est écrit que par `ap_boite_test.py invites`.
# Le n° FONCTION_INVITES de `fonctions_exigees` (slot_data) désigne les invités : il n'est JAMAIS publié dans
# ApVerrous::compiles (un client d'avant les invités refuse donc la graine : « Verrous incompatibles ») ; ce client-ci
# le vérifie dans ApInvites::compile.
FONCTION_INVITES = 23
OFF_INVITES, TAILLE_INVITES, CAP_INVITES, TAILLE_INVITE = 0x23000, 0x200, 32, 8
OFF_INVITES_LISTE, INVITES_TEXTE = 0xC0, 0x60
INVITES_PUBLIE = 0x80000000
INVITES_COMPILE, INVITES_NIVEAU, INVITES_AMITIE, INVITES_ANNONCE, INVITES_ESPECE = 0x01, 0x02, 0x04, 0x08, 0x10
INVITES_CHAMBRES = 0x20                              # les neuf chambres logent aussi un invité
# Règle d'affectation « Suite réservée, chambres gardées » (archipelago_invites.md §18) : la Suite ne loge que
# Pandanoko (reconnu par son CHARA_PARAM, INVITES_PARAM_PNJ), les autres invités seulement les chambres 101 à 109 (neuf
# à la fois), et un invité logé GARDE sa chambre jusqu'à l'amitié (personne ne se décale ; la chambre libérée va au
# premier de la file). Le JEU décide et signale chaque chambre attribuée (EVT_INVITE_CHAMBRE) ; le client la note pour
# la sauvegarde liée (liaisons.json) et la réécrit dans l'entrée de l'invité (octet +7) : elle vaut d'un lancement à
# l'autre. Le client ne calcule donc RIEN pour ce patch : `invites.json` dit ce que le jeu a confirmé.
# Sans ce bit (patch d'avant le 2026-10-09) : la Suite d'abord puis les chambres, pour tous, et tout le monde avance ;
# le client refait alors ce calcul-là pour le lanceur (`regle_invites`).
INVITES_SUITE_RESERVEE = 0x40
# Pièces d'invité (archipelago_invites.md §15) : 0 = Suite (t103i69), 1..9 = chambres 101..109 (t103i60..68) ; CRC-32
# du nom de carte, hachage et index du bit global de la pièce (`appear_sasurai_npc%02d` pour les chambres)
INVITES_PIECES = 10
INVITES_NOMS_PIECES = ("Suite",) + tuple(f"chambre {101 + i}" for i in range(9))
INVITES_CARTES_NOMS = ("t103i69",) + tuple(f"t103i6{i}" for i in range(9))
INVITES_CARTES = (0x98CDF955, 0xE11141F1, 0x96167167, 0x0F1F20DD, 0x7818104B,
                  0xE67C85E8, 0x917BB57E, 0x0872E4C4, 0x7F75D452, 0xEFCAC9C3)
INVITES_FLAGS = (0x3CDB0D89, 0x278F7E9D, 0x50884E0B, 0xC9811FB1, 0xBE862F27,
                 0x20E2BA84, 0x57E58A12, 0xCEECDBA8, 0xB9EBEB3E, 0x2954F6AF)
INVITES_BITS = (1502, 1505, 1506, 1507, 1508, 1509, 1510, 1511, 1512, 1513)
INVITES_PNJ = 0x95C2369D                             # crc32("npc_sasurai")
INVITES_BASE_SUITE, INVITES_BASE_CHAMBRE = 0xBD17305C, 0xF1CFD67A   # bases d'origine du PNJ (Pandanoko, attente)
# Motif du dernier refus de l'accroche (ApInvites::refus_motif, valeur en cause dans `refus_valeur`). Le mot +8 d'un
# NPC_BASE est le POINTEUR de l'enregistrement CHARA_BASE (FUN_004C32F8 -> FUN_0064DF3C), pas le hachage de la base.
INVITES_REFUS_AUCUN, INVITES_REFUS_POINTEUR, INVITES_REFUS_ORIGINE, INVITES_REFUS_PARAM, INVITES_REFUS_BASE = range(5)
INVITES_REFUS = {
    INVITES_REFUS_AUCUN: "aucun",
    INVITES_REFUS_POINTEUR: "le mot +8 du NPC_BASE n'est pas un pointeur d'enregistrement CHARA_BASE (mot lu : {v:#010x})",
    INVITES_REFUS_ORIGINE: "base d'origine du PNJ inattendue (base lue : {v:#010x})",
    INVITES_REFUS_PARAM: "CHARA_PARAM de l'invité introuvable dans le jeu ({v:#010x})",
    INVITES_REFUS_BASE: "enregistrement CHARA_BASE de la base de l'invité introuvable (base {v:#010x})",
}
# Valeurs RÉELLES lues dans un état d'Azahar pris dans la Suite (2026-10-09, ROM européenne) : CHARA_PARAM -> base
# (FUN_003AE640 -> +4), base -> adresse de l'enregistrement CHARA_BASE (FUN_0064DF3C ; +0 = la base). Servent au modèle
# du jeu des tests ; les adresses ne sont dans aucun code du jeu ni du client.
INVITES_JEU_PARAMS = {0xDB1CC069: 0xBD17305C, 0x33077779: 0x550C874C}            # Pandanoko, Corniot
INVITES_JEU_BASES = {0xBD17305C: 0x084F51E4, 0x550C874C: 0x084F2C3C, 0xF1CFD67A: 0x084F647C}


def pointeur_du_jeu(p: int) -> bool:
    """pointeurDuJeu d'invites.cpp : mot aligné dans le tas ordinaire ou la mémoire linéaire."""
    return p & 3 == 0 and (0x08000000 <= p < 0x10000000 or 0x14000000 <= p < 0x1C000000)


def texte_refus_invite(motif: int, valeur: int) -> str:
    return INVITES_REFUS.get(motif, f"motif {motif} ({{v:#010x}})").format(v=valeur)
INVITE_DECLARE, INVITE_ANNONCE = 0x01, 0x02
INVITES_FEN_AUCUNE, INVITES_FEN_AJOUTEE, INVITES_FEN_OUVERTE = 0, 1, 2
INVITES_FEN_ETATS = {0: "aucune", 1: "ajoutée (ouverture attendue)", 2: "ouverte (appui attendu)"}
(INVITES_MOTIF_AUCUN, INVITES_MOTIF_LISTE, INVITES_MOTIF_PARTIE, INVITES_MOTIF_NON_DECLARE, INVITES_MOTIF_TOUS_AMIS,
 INVITES_MOTIF_ESPECE, INVITES_MOTIF_PIECES) = range(7)
INVITES_MOTIFS = {
    INVITES_MOTIF_AUCUN: "un invité est présent",
    INVITES_MOTIF_LISTE: "pas de liste valide (client absent, ou graine sans invité)",
    INVITES_MOTIF_PARTIE: "pas de partie, ou sauvegarde non liée / autre que celle de la liste",
    INVITES_MOTIF_NON_DECLARE: "aucun invité déclaré (déclencheur pas encore rempli)",
    INVITES_MOTIF_TOUS_AMIS: "tous les invités déclarés sont déjà amis",
    INVITES_MOTIF_ESPECE: "l'invité courant n'est pas l'espèce d'origine du PNJ (patch antérieur)",
    INVITES_MOTIF_PIECES: "des invités attendent mais aucune pièce n'est libre pour eux (errants StreetPass des "
                          "chambres, Suite prise par le jeu)",
}
INVITES_IMAGES_SURES, INVITES_IMAGES_OUVERTURE = 30, 90
INVITES_TEXTE_HASH = 0x8277B40F                      # crc32("ap_invite_fenetre") : faux label de texte de l'annonce
EVT_INVITE = 8                                       # journal : annonce fermée (id = CHARA_PARAM, valeur = n° du
#                                                      Médaillium, index = rang dans la liste, valeur2 = séquence)
INVITES_FLAG_SUITE, INVITES_FLAG_AMITIE = 0x3CDB0D89, 0xABCB4EE6   # bits globaux 1502 et 24 (lus, jamais écrits)
INVITES_RENCONTRE = 0x713FE778                       # rencontre de script du combat de la Suite (ev98_0100)
INVITES_CARTE_SUITE = 0x98CDF955                     # crc32("t103i69")
INVITES_PARAM_PNJ, INVITES_NIVEAU_PNJ = 0xDB1CC069, 10   # combattant d'origine (Pandanoko, niveau 10)
P_AMIS_COMP, P_AMIS_COMPEX = 0x44C, 0x604            # bits « ami » du Médaillium (bit n = octet n >> 3, bit n & 7)
INVITES_CHAMPS = ("compile", "sequence", "ident", "nombre", "forcer", "param_ecrit", "base_ecrite", "fen_masque",
                  "present", "annoncees", "etat", "images", "fenetres", "montrees", "annulees", "textes")   # 16 u32
INVITES_OCTETS = ("en_suite", "combat_vu", "combat_invite", "niveau_ecrit", "niveau_equipe", "fen_invite",
                  "motif", "piece_chargee")                                                 # u8 à partir de +0x40
INVITES_COMPTEURS = ("lectures", "amities", "combats", "niveaux", "restaurations", "especes")   # u32 à partir de +0x48
# fin de la zone (J) : pieces[10] +0x1C0, invite_charge +0x1CA, visite +0x1CB, occupees u16 +0x1CC, retour +0x1CE,
# refus_motif +0x1CF, puis charges, refus, especes_combat, refus_valeur, champ_lu, base_lue (u32 à partir de +0x1D0)
OFF_INVITES_PIECES = 0x1C0
# (privé, J) chambres TENUES : garde[10] +0x1E8 (rang + 1 de l'invité qui tient la chambre p = 1..9), signale u16
# +0x1F2, garde_ident +0x1F4, signale_seq +0x1F8 (anciennes réserves : 0 dans un patch antérieur)
OFF_INVITES_GARDE = 0x1E8
EVT_INVITE_CHAMBRE = 9                               # journal : un invité tient une chambre que la liste du client ne
                                                     # connaît pas (id = CHARA_PARAM, valeur = n° du Médaillium, index =
                                                     # rang, quantité = chambre 1..9) : à mémoriser (liaisons.json)
INVITES_FIN_OCTETS = ((0x1CA, "invite_charge"), (0x1CB, "visite"), (0x1CE, "retour"), (0x1CF, "refus_motif"))
INVITES_FIN_COMPTEURS = ("charges", "refus", "especes_combat", "refus_valeur", "champ_lu", "base_lue")   # u32 à partir de +0x1D0
# Texte de l'annonce (composerTexte d'invites.cpp ; langue des notifications), deux lignes : chacune tient dans la
# largeur des lignes des messages d'information du jeu lui-même (au plus ~116 demi-unités du modèle de largeur_car :
# « disponibles à la Librairie Plume, au », `sys_info_win_*`).
INVITES_ANNONCE_TEXTE = {0: "Un Yo-kai est apparu à l'Auberge\ndes voyageurs, allez le voir.",
                         1: "A Yo-kai has appeared at\nWayfarer Manor, go and see it."}
INVITES_LARGEUR_LIGNE = 116


# --- PNJ des cartes et fonctions ÉTENDUES du patch (src/archipelago/pnj.cpp, boite.h ApPnj ; archipelago_boite.md §32) ---
# Les 32 bits de `compiles` sont pris : une fonction étendue n (>= 32) est publiée dans le bit n - 32 de ApPnj::fonctions
# (0x40 octets juste après ApInvites, même trou de la zone v10 : 0 dans un jeu antérieur). Dans `fonctions_exigees`,
# une graine qui en exige une ajoute FONCTION_ETENDUES (22), JAMAIS publié dans `compiles` : un client d'avant les
# fonctions étendues (qui ignore les n° >= 31) refuse la graine sur le 22 ; ce client-ci retire le 22 et vérifie chaque
# n° >= 32 dans ApPnj::fonctions, lu UNE fois par instance du jeu et seulement si la graine en exige. Le client n'écrit
# dans cette zone que `ev_declares` / `ev_ident` (8 octets en +0x24), et seulement si le jeu publie la fonction 34.
FONCTION_ETENDUES = 22
FONCTION_ETENDUE_BASE = 32
FONCTION_DEUX_ULTRAMAX = 32          # Ultramax N et K dans la même partie (archipelago_ultramax_deux.md)
FONCTION_INVITES_ESPECE = 33         # invités de l'Auberge à leur espèce (archipelago_invites.md §15)
# Yo-kai d'évènement à leur emplacement d'origine (archipelago_evenement_invitation.md §9) : quand l'objet AP du
# Yo-kai k est reçu, le client pose le bit k de ApPnj::ev_declares (avec l'identifiant de partie en `ev_ident`) ; le
# jeu neutralise alors les clauses « jeu fini » / « transfert » de la condition d'apparition de SON PNJ.
FONCTION_EVENEMENT_PLACE = 34
# Même fonction, version corrigée (2026-10-09, archipelago_evenement_invitation.md §10) : le Yo-kai n'apparaît que
# lorsque sa place est LIBRE (Jibanyan S : Jibanyan déjà ami ET flag « évènement vu » ev01_2200 ; Hovernyan : flag de
# fin du chapitre 6). Publiée par le jeu (bit 3 de ApPnj::fonctions) ; exigée par les graines générées depuis : un
# patch d'avant (Jibanyan S par-dessus le Jibanyan de l'histoire au chapitre 1 : histoire bloquée) est refusé. Rien de
# plus à faire pour le client : n° vérifié comme toute fonction étendue.
FONCTION_EVENEMENT_LIBRE = 35
# N° JAMAIS publié par le jeu, ajouté par une graine dont une fonction demande au CLIENT d'écrire quelque chose de
# nouveau (ici `ev_declares`) : un client d'avant tient tout n° >= 63 pour absent et refuse la graine, même avec le
# patch à jour ; ce client-ci le retire.
FONCTION_CLIENT_2 = 63
# Idem pour une LECTURE nouvelle du client (archipelago_boss.md §11) : entrée {location, octet, seuil} de la liste `boss`
# (« Boss : Taprice » : octet global de progression du Tunnel sans fin). Un client d'avant ignorerait l'entrée sans
# rien dire (check jamais envoyé) : il refuse la graine sur ce n°, que ce client-ci retire.
FONCTION_CLIENT_3 = 64
# Idem pour les verrous ÉTENDUS de la V3 (k >= 40, zone ApVerrous2, plus bas) et la détection par PHASE de quête
# (`phase_min` d'une entrée {location, quete} de `boss`) : un client d'avant ignore en silence un verrou de k >= 24 et
# lirait l'entrée comme « quête terminée » ; il refuse la graine sur ce n° (et sur le 22), que ce client-ci retire.
FONCTION_CLIENT_4 = 65
FONCTIONS_CLIENT_CONNUES = frozenset({FONCTION_CLIENT_2, FONCTION_CLIENT_3, FONCTION_CLIENT_4})
# Tunnel sans fin sans limite par jour (fonction du patch, bit 4 de ApPnj::fonctions) : publiée par le jeu ; aucune
# graine ne l'exige aujourd'hui (l'option s'écrit dans ApVerrous2, voir OPTION2_TUNNEL).
FONCTION_TUNNEL_LIBRE = 36
# Boss détecté par un octet global de catégorie 6 (P + P_FLAGS_OCTETS + index) qui ne décroît jamais : pseudo-flag
# rangé avec les flags de boss (catalogue, instantané de liaison `boss`), au-dessus de tout index de flag bit réel
# (FLAG_GLOBAL_MAX < 0x10000). Lu comme les 8 flags bit de son octet, dans la même lecture groupée que les autres.
BOSS_OCTET_BASE = 0x100000


def boss_octet_valide(octet: int, seuil: int) -> bool:
    """Octet global lisible par le client (avant les octets du mod, P + P_LIAISON) et seuil d'un octet non nul."""
    return 0 <= octet < P_LIAISON - P_FLAGS_OCTETS and 1 <= seuil <= 255


def boss_octet_pseudo(octet: int, seuil: int) -> int:
    """Pseudo-flag d'un boss détecté par « octet global `octet` >= `seuil` »."""
    return BOSS_OCTET_BASE | (octet & 0xFFF) << 8 | (seuil & 0xFF)


def boss_octet_decode(pseudo: int) -> tuple[int, int] | None:
    """(octet, seuil) d'un pseudo-flag de `boss_octet_pseudo`, None pour un flag bit ordinaire."""
    if pseudo < BOSS_OCTET_BASE:
        return None
    return (pseudo >> 8) & 0xFFF, pseudo & 0xFF


def boss_octet_flags(octet: int) -> list[int]:
    """Les 8 index de flags bit globaux (bit i % 8 de P + 4 + i // 8) qui recouvrent l'octet global `octet`
    (P + 0x144 + octet), du bit 0 au bit 7."""
    base = (P_FLAGS_OCTETS + octet - P_FLAGS_GLOBAUX) * 8
    return list(range(base, base + 8))


def boss_octets_atteints(pseudos, poses) -> set[int]:
    """Parmi les pseudo-flags `pseudos`, ceux dont l'octet (reconstruit depuis les flags bit `poses`) atteint le seuil."""
    out = set()
    for p in pseudos:
        d = boss_octet_decode(p)
        if d is None:
            continue
        valeur = sum(1 << k for k, f in enumerate(boss_octet_flags(d[0])) if f in poses)
        if valeur >= d[1]:
            out.add(p)
    return out
EV_JIBANYAN_S, EV_KOMASAN_S, EV_KOMAJIRO_S, EV_HOVERNYAN, EV_NOMBRE = 0, 1, 2, 3, 4
EV_NOMS = ("Jibanyan S", "Komasan S", "Komajiro S", "Hovernyan")
EV_MEDAILLES = (433, 434, 435, 351)
EV_CARTES = ("t101g00", "t104i27", "t104g00", "t231i01")
EV_APPARITIONS = ("y1529000_01_01", "y159900_01_01", "y159910_01_01", "y236000_01")   # NPC_APPEAR +4
EV_LONGUEURS = (194, 50, 17, 26)                     # u16 +1 de la condition décodée (longueur - 3)
EV_FLAG_FINI, EV_OCTET_TRANSFERT, EV_GAMECLEAR = 0x176F56BB, 0xB3E9494F, 0x10B14096
EV_JIB_CLAUSE_1, EV_JIB_CLAUSE_2 = 23, 46            # Jibanyan S : jetons « entier 1, == » (le 2e est neutralisé)
EV_FLAG_OFFSET = 19                                  # k = 0, 3 : hachage du flag de la 1re clause, remplacé par :
EV_JIB_FLAG_LIBRE = 0xC3966699                       # crc32("ev01_2200"), bit global n° 128 : place de Jibanyan S libre
EV_HOV_FLAG_LIBRE = 0xD4058588                       # bit global n° 281 : chapitre 6 fini (pièce de Hovernyan libre)
EV_JIB_AMI_MEDAILLE = 135                            # Jibanyan S attend que Jibanyan (n° 135) soit ami
EV_FLAGS_LIBRES = {EV_JIBANYAN_S: EV_JIB_FLAG_LIBRE, EV_HOVERNYAN: EV_HOV_FLAG_LIBRE}
OFF_PNJ_EV_ATTENTE = 0x12                            # u8 ev_attente (J) : bit k = déclaré mais en attente (k = 0)
OFF_PNJ_EV = 0x24                                    # ev_declares (C), ev_ident (C), ev_forcer (T), puis J
PNJ_EV_CHAMPS = ("ev_declares", "ev_ident", "ev_forcer", "ev_poses", "ev_charges", "ev_ecrits", "ev_refus")
OFF_PNJ, TAILLE_PNJ = 0x23200, 0x40
PNJ_PUBLIE = 0x80000000
ULTRAMAX_N, ULTRAMAX_K = 1, 2
ULTRAMAX_NOMS = {0: "celui du personnage joué", ULTRAMAX_N: "Ultramax N", ULTRAMAX_K: "Ultramax K"}
ULTRAMAX_MEDAILLE_N, ULTRAMAX_MEDAILLE_K = 431, 432
ULTRAMAX_CARTE = 0x507C7926          # crc32("t131g00") : Ourcival
ULTRAMAX_OBJET = 0xF2A2F16F          # Marque d'Ultramax
PNJ_CHAMPS = ("fonctions", "accroches", "contexte")                       # u32 à partir de +0
PNJ_OCTETS = ("um_forcer", "um_voulu", "um_quitte", "um_montre", "um_genre", "um_amis")   # u8 à partir de +0x0C
PNJ_COMPTEURS = ("um_charges", "um_echanges", "um_choix", "um_refus")     # u32 à partir de +0x14


def dec_pnj(b: bytes) -> dict:
    """ApPnj (0x40 octets à OFF_PNJ)."""
    d = dict(zip(PNJ_CHAMPS, struct.unpack_from("<3I", b, 0)))
    d.update(zip(PNJ_OCTETS, b[0x0C:0x0C + len(PNJ_OCTETS)]))
    d.update(zip(PNJ_COMPTEURS, struct.unpack_from("<4I", b, 0x14)))
    d.update(zip(PNJ_EV_CHAMPS, struct.unpack_from("<7I", b, OFF_PNJ_EV)))
    d["ev_attente"] = b[OFF_PNJ_EV_ATTENTE]
    return d


def ecriture_evenement(masque: int, ident: int) -> tuple[int, bytes]:
    """(adresse, octets) de `ev_declares` + `ev_ident` (8 octets, une seule écriture, jeu arrêté). Ne touche ni
    `ev_forcer` (outil de test) ni les champs du jeu."""
    return ZONE + OFF_PNJ + OFF_PNJ_EV, struct.pack("<II", masque & ((1 << EV_NOMBRE) - 1), ident & 0xFFFFFFFF)


def evenement_attend(k: int, declare: bool, jibanyan_ami: bool) -> bool:
    """Objet reçu mais apparition en attente (`ev_attente`) : Jibanyan S tant que Jibanyan n'est pas ami."""
    return declare and k == EV_JIBANYAN_S and not jibanyan_ami


def evenement_condition(k: int, cond: bytes | None, declare: bool,
                        jibanyan_ami: bool = True) -> tuple[bytes | None, bool]:
    """Modèle d'`evenementCharges` (pnj.cpp) pour l'apparition du Yo-kai k : (condition après l'accroche — None =
    pointeur nul = sans condition —, refus). Non déclaré, ou en attente (Jibanyan S sans Jibanyan ami) : inchangée.
    Condition inattendue : inchangée, refus. Jibanyan S et Hovernyan gardent une condition : leur 1re clause lit le
    flag « place libre » (EV_FLAGS_LIBRES) au lieu de « jeu fini »."""
    if not declare or evenement_attend(k, declare, jibanyan_ami):
        return cond, False

    def cite(c: bytes, h: int) -> bool:
        fin = 3 + (c[1] | c[2] << 8)
        return fin <= 256 and h.to_bytes(4, "big") in c[3:fin]
    un_egal = b"\x32\x00\x00\x00\x01\x78"
    ok = cond is not None and len(cond) >= 3 and cond[0] == 0 and (cond[1] | cond[2] << 8) == EV_LONGUEURS[k] \
        and len(cond) >= EV_LONGUEURS[k] + 3
    if ok and k == EV_JIBANYAN_S:
        ok = cond[19:23] == EV_FLAG_FINI.to_bytes(4, "big") and cond[23:29] == un_egal \
            and cond[42:46] == EV_OCTET_TRANSFERT.to_bytes(4, "big") and cond[46:52] == un_egal
    elif ok and k == EV_KOMASAN_S:
        ok = cite(cond, EV_FLAG_FINI) and cite(cond, EV_OCTET_TRANSFERT)
    elif ok and k == EV_KOMAJIRO_S:
        ok = cite(cond, EV_GAMECLEAR)
    elif ok:
        ok = cond[19:23] == EV_FLAG_FINI.to_bytes(4, "big") and cond[23:29] == un_egal
    if not ok:
        return cond, True
    if k not in EV_FLAGS_LIBRES:
        return None, False
    c = bytearray(cond)
    c[EV_FLAG_OFFSET:EV_FLAG_OFFSET + 4] = EV_FLAGS_LIBRES[k].to_bytes(4, "big")
    if k == EV_JIBANYAN_S:
        c[EV_JIB_CLAUSE_2 + 1:EV_JIB_CLAUSE_2 + 6] = b"\x7F\xFF\xFF\xFF\x79"
    return bytes(c), False


def fonctions_etendues(b: bytes) -> int | None:
    """Bits des fonctions étendues compilées dans le jeu (bit b = fonction 32 + b), None si le champ n'est pas publié
    (jeu antérieur aux fonctions étendues)."""
    c = struct.unpack_from("<I", b, 0)[0]
    return c & ~PNJ_PUBLIE if c & PNJ_PUBLIE else None


def fonction_etendue_compilee(bits: int | None, n: int) -> bool:
    return (bits is not None and FONCTION_ETENDUE_BASE <= n < FONCTION_ETENDUE_BASE + 31
            and bool(bits >> (n - FONCTION_ETENDUE_BASE) & 1))


def ultramax_choix(voulu: int, quitte: bool, genre: int, ami_n: bool, ami_k: bool) -> int:
    """Modèle d'apUltramaxImage (pnj.cpp), joueur libre sur une autre carte qu'Ourcival : Ultramax voulu au prochain
    chargement d'Ourcival. Celui qui n'est pas encore ami ; si aucun ou les deux le sont : alternance à chaque sortie
    d'Ourcival (`quitte`), en commençant par celui du personnage joué (`genre` : 1 garçon -> N, 2 fille -> K)."""
    if ami_n != ami_k:
        return ULTRAMAX_K if ami_n else ULTRAMAX_N
    if voulu not in (ULTRAMAX_N, ULTRAMAX_K):
        voulu = ULTRAMAX_K if genre == 2 else ULTRAMAX_N
    return ULTRAMAX_N + ULTRAMAX_K - voulu if quitte else voulu


def ultramax_montre(forcer: int, voulu: int, genre: int) -> tuple[int, bool]:
    """Modèle de l'accroche (ultramaxCharges) : (Ultramax montré au chargement d'Ourcival, conditions échangées)."""
    naturel = ULTRAMAX_K if genre == 2 else ULTRAMAX_N
    v = forcer if forcer in (ULTRAMAX_N, ULTRAMAX_K) else voulu
    if v not in (ULTRAMAX_N, ULTRAMAX_K):
        v = naturel
    return v, v != naturel


def texte_annonce_invite(langue: int = 0) -> bytes:
    """Texte que le jeu compose pour l'annonce d'un invité (invites.cpp)."""
    return INVITES_ANNONCE_TEXTE[1 if langue == 1 else 0].encode("utf-8")[:INVITES_TEXTE - 1]


def enc_invite(param: int, medaille: int, drapeaux: int = 0, chambre: int = 0) -> bytes:
    """Entrée ApInvite (8 octets). `chambre` : chambre mémorisée pour cet invité (1..9 = 101..109, 0 : aucune)."""
    return struct.pack("<IHBB", param & 0xFFFFFFFF, medaille & 0xFFFF, drapeaux & 0xFF,
                       chambre if 0 < chambre < INVITES_PIECES else 0)


def dec_invite(b: bytes) -> dict:
    param, medaille, drapeaux, chambre = struct.unpack_from("<IHBB", b)
    return {"param": param, "medaille": medaille, "drapeaux": drapeaux, "chambre": chambre}


def dec_invites(b: bytes) -> dict:
    """ApInvites (0x200 octets à OFF_INVITES)."""
    d = dict(zip(INVITES_CHAMPS, struct.unpack_from("<16I", b, 0)))
    d.update(zip(INVITES_OCTETS, b[0x40:0x40 + len(INVITES_OCTETS)]))
    d.update(zip(INVITES_COMPTEURS, struct.unpack_from("<6I", b, 0x48)))
    d["texte"] = bytes(b[0x60:0x60 + INVITES_TEXTE]).split(b"\0")[0]
    n = min(d["nombre"], CAP_INVITES)
    d["liste"] = [dec_invite(b[OFF_INVITES_LISTE + i * TAILLE_INVITE:]) for i in range(n)]
    d["pieces"] = list(b[OFF_INVITES_PIECES:OFF_INVITES_PIECES + INVITES_PIECES])
    for off, nom in INVITES_FIN_OCTETS:
        d[nom] = b[off]
    d["occupees"] = struct.unpack_from("<H", b, 0x1CC)[0]
    d.update(zip(INVITES_FIN_COMPTEURS, struct.unpack_from("<%dI" % len(INVITES_FIN_COMPTEURS), b, 0x1D0)))
    d["garde"] = list(b[OFF_INVITES_GARDE:OFF_INVITES_GARDE + INVITES_PIECES])
    d["signale"], d["garde_ident"], d["signale_seq"] = struct.unpack_from("<HII", b, OFF_INVITES_GARDE + INVITES_PIECES)
    return d


def invites_compiles(b: bytes) -> int | None:
    """Bits INVITES_* compilés dans le jeu (début de ApInvites), None si le champ n'est pas publié (jeu antérieur aux
    invités, ou compilé sans)."""
    c = struct.unpack_from("<I", b, 0)[0]
    return c & ~INVITES_PUBLIE if c & INVITES_PUBLIE else None


def ecritures_invites(invites: list[tuple], ident: int, sequence: int) -> list[tuple[int, bytes]]:
    """Écritures (adresse, octets) de la liste des invités, dans l'ordre : liste, puis ident et nombre, puis `sequence`
    EN DERNIER. `invites` = [(CHARA_PARAM, n° du Médaillium, drapeaux[, chambre])] dans l'ordre de la graine. Ne touche ni
    `compile` ni `forcer`."""
    if len(invites) > CAP_INVITES:
        raise ValueError("trop d'invités")
    liste = b"".join(enc_invite(*x) for x in invites).ljust(CAP_INVITES * TAILLE_INVITE, b"\0")
    base = ZONE + OFF_INVITES
    return [(base + OFF_INVITES_LISTE, liste),
            (base + 8, struct.pack("<II", ident & 0xFFFFFFFF, len(invites))),
            (base + 4, struct.pack("<I", sequence & 0xFFFFFFFF))]


def regle_invites(compile_bits: int | None) -> tuple[int, bool]:
    """(nombre de pièces d'invité, Suite réservée à Pandanoko) d'après les bits INVITES_* publiés par le jeu : la règle
    d'`affecter` que CE patch applique. Patch d'avant la Suite réservée : 10 pièces pour tous (ou la Suite seule, pour
    un build d'essai sans les chambres)."""
    c = compile_bits or 0
    return (INVITES_PIECES if c & INVITES_CHAMBRES else 1), bool(c & INVITES_SUITE_RESERVEE)


def affectation_gardee(liste: list[tuple], amis: set[int], occupees: int = 0,
                        garde: list[int] | None = None) -> tuple[list[int], int, list[int]]:
    """Modèle d'`affecter` (invites.cpp), règle « Suite réservée, chambres gardées ». `liste` = [(CHARA_PARAM, n° du
    Médaillium, déclaré[, chambre mémorisée par le client : 1..9, 0 aucune])] ; `amis` = n° déjà amis ; `occupees` :
    bit p = pièce p dont le jeu se sert ; `garde` : rang + 1 de l'invité qui tenait chaque chambre à l'image précédente
    (mémoire du jeu, même liste ; None : aucune). Rend ([rang + 1 de l'invité LOGÉ dans chaque pièce], motif, [rang + 1
    de l'invité qui TIENT chaque pièce, logé ou non]).
      0. Pandanoko tient la Suite (pièce 0) ; il ne compte pas dans les chambres et n'en attend jamais une ;
      1. un candidat (déclaré, pas encore ami) tient la chambre mémorisée par le client ;
      2. sinon celle qu'il tenait à l'image précédente ;
      3. les candidats sans chambre prennent, dans l'ordre de la liste, les chambres que personne ne tient et dont le
         jeu ne se sert pas ; les suivants attendent. Personne ne change jamais de chambre."""
    t = [0] * INVITES_PIECES
    candidats, chambres, tient = set(), [], set()
    des_amis = False
    for i, e in enumerate(liste[:CAP_INVITES]):
        param, medaille, declare = e[0], e[1], e[2]
        if not param or not 0 < medaille < 512 or not declare:
            continue
        if medaille in amis:
            des_amis = True
            continue
        candidats.add(i)
        if param == INVITES_PARAM_PNJ:
            if not t[0]:
                t[0] = i + 1
            continue
        chambres.append(i)
        c = e[3] if len(e) > 3 else 0
        if 1 <= c < INVITES_PIECES and not t[c]:
            t[c] = i + 1
            tient.add(i)
    for p in range(1, INVITES_PIECES):
        g = garde[p] if garde else 0
        if not t[p] and g and g - 1 in chambres and g - 1 not in tient:
            t[p] = g
            tient.add(g - 1)
    p = 1
    for i in chambres:
        if i in tient:
            continue
        while p < INVITES_PIECES and (t[p] or occupees >> p & 1):
            p += 1
        if p >= INVITES_PIECES:
            break
        t[p] = i + 1
        tient.add(i)
    loges = [0 if occupees >> q & 1 else g for q, g in enumerate(t)]
    motif = INVITES_MOTIF_AUCUN if any(loges) else INVITES_MOTIF_PIECES if candidats \
        else INVITES_MOTIF_TOUS_AMIS if des_amis else INVITES_MOTIF_NON_DECLARE
    return loges, motif, t


def affectation_invites(liste: list[tuple], amis: set[int], occupees: int = 0, pieces: int = INVITES_PIECES,
                        reservee: bool = True, garde: list[int] | None = None) -> tuple[list[int], int]:
    """Qui loge où, selon la règle du patch (`regle_invites`) : ([rang + 1 de l'invité de chaque pièce, 0 = personne]
    sur 10 pièces, motif INVITES_MOTIF_* quand personne n'est logé). `reservee` : règle courante (`affectation_gardee`).
    Sans `reservee` (patch antérieur) : les invités déclarés pas encore amis prennent, dans l'ordre de la liste, les
    `pieces` premières pièces libres, la Suite d'abord (`pieces` = 1 : build d'essai « Suite seule ») ; tout le monde
    avance quand une pièce se libère."""
    if reservee:
        return affectation_gardee(liste, amis, occupees, garde)[:2]
    loges = [0] * INVITES_PIECES
    motif = INVITES_MOTIF_NON_DECLARE
    p = n = 0
    for i, e in enumerate(liste[:CAP_INVITES]):
        param, medaille, declare = e[0], e[1], e[2]
        if not param or not 0 < medaille < 512 or not declare:
            continue
        if medaille in amis:
            if not n and motif == INVITES_MOTIF_NON_DECLARE:
                motif = INVITES_MOTIF_TOUS_AMIS
            continue
        while p < pieces and occupees >> p & 1:
            p += 1
        if p >= pieces:
            if not n:
                motif = INVITES_MOTIF_PIECES
            break
        loges[p] = i + 1
        p += 1
        n += 1
        motif = INVITES_MOTIF_AUCUN
    return loges, motif


def etats_invites(liste: list[tuple], amis: set[int], pieces: int = INVITES_PIECES,
                  reservee: bool = True) -> list[dict]:
    """État de chaque invité pour le lanceur (même ordre que `liste`) : {"etat": "attente" (pas encore déclaré) |
    "file" (déclaré, attend qu'une chambre se libère ; "rang" : sa place dans la file, 1 = le prochain) | "present"
    ("piece" : 0 Suite, 1..9 chambres 101..109) | "ami"}. `pieces`, `reservee` : la règle du patch (`regle_invites`).
    Règle courante (`reservee`) : RIEN n'est calculé ici ; Pandanoko déclaré est dans la Suite, un invité est dans la
    chambre que le jeu lui a attribuée (4e élément de son entrée, mémoire du client), et « dans la file » tant que le
    jeu ne lui en a signalé aucune. Patch antérieur : même calcul que ce patch-là, sans les errants StreetPass du
    joueur (non lus : un invité annoncé dans une chambre qu'un errant occupe est en réalité dans la suivante)."""
    if reservee:
        piece_de: dict[int, int] = {}
        prises: set[int] = set()
        for i, e in enumerate(liste):
            if not e[2] or e[1] in amis:
                continue
            c = 0 if e[0] == INVITES_PARAM_PNJ else (e[3] if len(e) > 3 else 0)
            if (e[0] == INVITES_PARAM_PNJ or 1 <= c < INVITES_PIECES) and c not in prises:
                piece_de[i] = c
                prises.add(c)
    else:
        loges, _motif = affectation_invites(liste, amis, 0, pieces, False)
        piece_de = {g - 1: p for p, g in enumerate(loges) if g}
    etats, attente = [], 0
    for i, e in enumerate(liste):
        if e[1] in amis:
            etats.append({"etat": "ami"})
        elif i in piece_de:
            etats.append({"etat": "present", "piece": piece_de[i]})
        elif e[2]:
            attente += 1
            etats.append({"etat": "file", "rang": attente})
        else:
            etats.append({"etat": "attente"})
    return etats


def invites_zone(zone: bytes, ident_sauvegarde: int, amis: set[int] | None, liee: bool = True, occupees: int = 0,
                 pieces: int = INVITES_PIECES, reservee: bool = True) -> tuple[list[int], int]:
    """`affecter` sur une zone ApInvites lue : ([rang + 1 par pièce], motif). `amis` = n° du Médaillium déjà amis
    (Comp | CompEx) de la sauvegarde chargée, None sans partie."""
    d = dec_invites(zone)
    if d["sequence"] == 0 or not 0 < d["nombre"] <= CAP_INVITES:
        return [0] * INVITES_PIECES, INVITES_MOTIF_LISTE
    if amis is None or d["ident"] == 0 or d["ident"] != ident_sauvegarde or not liee:
        return [0] * INVITES_PIECES, INVITES_MOTIF_PARTIE
    liste = [(e["param"], e["medaille"], bool(e["drapeaux"] & INVITE_DECLARE or d["forcer"] >> i & 1), e["chambre"])
             for i, e in enumerate(d["liste"])]
    garde = d["garde"] if d["garde_ident"] == d["ident"] else None
    return affectation_invites(liste, amis, occupees, pieces, reservee, garde)


def invite_courant(zone: bytes, ident_sauvegarde: int, amis: set[int] | None, liee: bool = True,
                   pieces: int = INVITES_PIECES, reservee: bool = True) -> tuple[int, int]:
    """(Rang du premier invité logé, la Suite d'abord, ou -1 ; motif INVITES_MOTIF_*) : `present` - 1 de la zone."""
    loges, motif = invites_zone(zone, ident_sauvegarde, amis, liee, 0, pieces, reservee)
    premier = next((g for g in loges if g), 0)
    return premier - 1, motif


# --- v9 : boutiques ---
def enc_boutique(article: int, affiche: int = 0, etiquette: int = 0, bit: int = 0, drapeaux: int = BOUTIQUE_VALIDE,
                 texte: str | bytes = b"", utilisations: int = 0) -> bytes:
    """Entrée de la table des boutiques (80 octets) ; texte = nom de la vitrine (vide : nom par défaut)."""
    return (struct.pack("<IIIHBB", article & 0xFFFFFFFF, affiche & 0xFFFFFFFF, etiquette & 0xFFFFFFFF, bit & 0xFFFF,
                        drapeaux, utilisations) + _champ_texte(texte, BOUTIQUE_TEXTE) + bytes(8))


def dec_boutique(b: bytes) -> dict:
    a, af, e, bit, d, u = struct.unpack_from("<IIIHBB", b)
    return {"article": a, "affiche": af, "etiquette": e, "bit": bit, "drapeaux": d, "utilisations": u,
            "texte": b[16:16 + BOUTIQUE_TEXTE].split(b"\0")[0]}


def dec_boutiques_entete(b: bytes) -> dict:
    return dict(zip(BOUTIQUES_ENTETE, struct.unpack_from("<11I", b)))


def boutiques_compilees(entete_boutiques: bytes) -> bool | None:
    """Champ `compile` publié par le jeu v9 : True (articles AP compilés), False (build --define
    YKW2_AP_SANS_BOUTIQUES), None (non publié : jeu antérieur)."""
    c = struct.unpack_from("<I", entete_boutiques, 4)[0]
    if not c & BOUTIQUES_PUBLIE:
        return None
    return bool(c & BOUTIQUES_COMPILE)


def indices_boutiques_compiles(entete_boutiques: bytes) -> bool | None:
    """Évènement BOUTIQUE (indices automatiques) écrit par le jeu ? None : champ non publié (jeu v8 ou antérieur)."""
    c = struct.unpack_from("<I", entete_boutiques, 4)[0]
    if not c & BOUTIQUES_PUBLIE:
        return None
    return bool(c & BOUTIQUES_INDICES)


def bits_evt_boutique(e: dict) -> list[int]:
    """Bits d'articles d'un évènement BOUTIQUE (dans l'ordre, places vides omises, `quantite` au plus)."""
    bits = []
    for nom in BOUTIQUE_CHAMPS_BITS:
        v = e[nom]
        bits += [v & 0xFFFF, v >> 16 & 0xFFFF]
    return [b for b in bits[:min(e["quantite"], BOUTIQUE_BITS_EVT)] if b != BOUTIQUE_BIT_AUCUN]


def enc_bits_evt_boutique(bits: list[int]) -> dict:
    """Champs id, valeur, valeur2, etiquette, index d'un évènement BOUTIQUE pour au plus BOUTIQUE_BITS_EVT bits."""
    if len(bits) > BOUTIQUE_BITS_EVT:
        raise ValueError("trop de bits pour un évènement BOUTIQUE")
    m = list(bits) + [BOUTIQUE_BIT_AUCUN] * (BOUTIQUE_BITS_EVT - len(bits))
    return {nom: m[2 * i] | m[2 * i + 1] << 16 for i, nom in enumerate(BOUTIQUE_CHAMPS_BITS)}


def enc_table_boutiques(entrees: list[bytes]) -> bytes:
    """Table complète (CAP_BOUTIQUES entrées) : entrées triées par article (recherche dichotomique du jeu), zéros
    ensuite ; une clé en double est une erreur (le jeu n'en verrait qu'une)."""
    tri = sorted(entrees, key=lambda e: struct.unpack_from("<I", e)[0])
    cles = [struct.unpack_from("<I", e)[0] for e in tri]
    if len(tri) > CAP_BOUTIQUES or len(set(cles)) != len(cles) or 0 in cles:
        raise ValueError("table des boutiques invalide (capacité, doublon ou article nul)")
    return b"".join(tri) + bytes(TAILLE_BOUTIQUE * (CAP_BOUTIQUES - len(tri)))


def plage_octets_boutiques() -> tuple[int, int]:
    """(offset dans P, taille) de la plage des octets des bits de boutique (P + 0x14E .. P + 0x3AC)."""
    lo, hi = min(BOUTIQUE_OCTETS), max(BOUTIQUE_OCTETS)
    return P_FLAGS_OCTETS + lo, hi - lo + 1


def bits_boutiques(octets: bytes) -> set[int]:
    """Bits posés, depuis les octets de `plage_octets_boutiques()`."""
    lo = min(BOUTIQUE_OCTETS)
    out = set()
    for k in range(BOUTIQUE_BITS):
        i = BOUTIQUE_OCTETS[k >> 3] - lo
        if 0 <= i < len(octets) and octets[i] >> (k & 7) & 1:
            out.add(k)
    return out


def adr_octet_bit_boutique(adresse_p: int, bit: int) -> tuple[int, int]:
    """(adresse de l'octet, masque) du bit persistant `bit` dans la partie P."""
    return adresse_p + P_FLAGS_OCTETS + BOUTIQUE_OCTETS[bit >> 3], 1 << (bit & 7)


# --- v6 : randomizer de Yo-kai ---
def dec_rando_entete(b: bytes) -> dict:
    v = struct.unpack_from("<IIIHHIIIIIIIIIIIHH", b)
    return dict(zip(RANDO_ENTETE, v))


def rando_compile(entete_rando: bytes) -> int | None:
    """Champ `compile` publié par le jeu v6 : masque RANDO_RENCONTRES | RANDO_LOUPE (| RANDO_PAR_RENCONTRE en v10,
    | RANDO_LOUPE_DECOR avec le garde-fou de la loupe ; 0 : build --define YKW2_AP_SANS_RANDO_YOKAI), None (non publié :
    jeu antérieur)."""
    c = struct.unpack_from("<I", entete_rando, 4)[0]
    if not c & RANDO_PUBLIE:
        return None
    return c & (RANDO_RENCONTRES | RANDO_LOUPE | RANDO_PAR_RENCONTRE | RANDO_LOUPE_DECOR | RANDO_P_ETENDU
                | RANDO_LOUPE_TARDIVE | RANDO_ESPECES_ETENDU)


def enc_paires(paires: dict[int, int], cap: int) -> bytes:
    """Table de paires (origine, cible) triées par origine, identités exclues, complétée par des zéros."""
    lp = sorted((a & 0xFFFFFFFF, b & 0xFFFFFFFF) for a, b in paires.items() if a != b)
    if len(lp) > cap:
        raise ValueError(f"{len(lp)} paires (capacité {cap})")
    return b"".join(struct.pack("<II", a, b) for a, b in lp) + bytes(8 * (cap - len(lp)))


def enc_w(w, cap: int = CAP_RANDO_W) -> bytes:
    lw = sorted({x & 0xFFFFFFFF for x in w})
    if len(lw) > cap:
        raise ValueError(f"{len(lw)} rencontres (capacité {cap})")
    return struct.pack(f"<{len(lw)}I", *lw) + bytes(4 * (cap - len(lw)))


def dec_paires(b: bytes, n: int) -> dict[int, int]:
    return dict(struct.unpack_from("<II", b, 8 * i) for i in range(n))


def dec_w(b: bytes, n: int) -> list[int]:
    return list(struct.unpack_from(f"<{n}I", b))


def enc_especes(especes, cap: int = CAP_RANDO_ESPECES) -> bytes:
    """v10 : table des espèces du mélange par rencontre [(CHARA_PARAM, CHARA_BASE)] (id = rang), sans remplissage."""
    if len(especes) > cap:
        raise ValueError(f"{len(especes)} espèces (capacité {cap})")
    return b"".join(struct.pack("<II", p & 0xFFFFFFFF, b & 0xFFFFFFFF) for p, b in especes)


def enc_especes_etendu(especes) -> tuple[bytes, bytes]:
    """V3 (bit RANDO_ESPECES_ETENDU) : table des espèces (CAP_RANDO_ESPECES_TOTAL au plus) -> (ids 0..255, à
    OFF_RANDO_ESPECES ; ids 256.., à OFF_RANDO_ESPECES2)."""
    b = enc_especes(especes, CAP_RANDO_ESPECES_TOTAL)
    return b[:8 * CAP_RANDO_ESPECES], b[8 * CAP_RANDO_ESPECES:]


def id_en_jeu(v: int) -> int:
    """Id de l'espèce en jeu d'une entrée P (bits 24-31, bit 15 = 9e bit : V3, RANDO_ESPECES_ETENDU)."""
    return (v >> 24) | (0x100 if v & RANDO_P_EN_JEU_HAUT else 0)


def enc_p(entrees, cap: int = CAP_RANDO_P) -> bytes:
    """v10 : entrées P (u32) triées par clé (bits 0-13), clés distinctes, sans remplissage."""
    le = sorted((x & 0xFFFFFFFF for x in entrees), key=lambda x: x & RANDO_P_CLE)
    if len(le) > cap:
        raise ValueError(f"{len(le)} entrées (capacité {cap})")
    cles = [x & RANDO_P_CLE for x in le]
    if cles != sorted(set(cles)):
        raise ValueError("entrées P : clés non distinctes ou non triées")
    return struct.pack(f"<{len(le)}I", *le)


def enc_p_etendu(entrees) -> tuple[bytes, bytes]:
    """V3 (bit RANDO_P_ETENDU) : entrées P triées (CAP_RANDO_P_TOTAL au plus) -> (les CAP_RANDO_P premières, à
    OFF_RANDO_P ; la suite, à OFF_RANDO_P2) : une seule suite triée pour la dichotomie du jeu."""
    b = enc_p(entrees, CAP_RANDO_P_TOTAL)
    return b[:4 * CAP_RANDO_P], b[4 * CAP_RANDO_P:]


# --- v7 : randomizer des boss ---
def dec_boss_entete(b: bytes) -> dict:
    v = struct.unpack_from("<IIIHHIIIIIIIIIIIHH", b)
    return dict(zip(BOSS_ENTETE, v))


def boss_force(entete_boss: bytes) -> bool:
    """Le jeu applique la table M (force adaptée à la place) : bit BOSS_FORCE publié avec le randomizer des boss."""
    c = struct.unpack_from("<I", entete_boss, 4)[0]
    return bool(c & BOSS_PUBLIE and c & BOSS_COMPILE and c & BOSS_FORCE)


def enc_boss_m(m: dict[int, tuple[int, ...]], cap: int = CAP_BOSS_M) -> bytes:
    """Table M : {place: (PV, For, Esp, Déf, Vit) en %} triée par place, complétée par des zéros."""
    lp = sorted((p & 0xFFFFFFFF, tuple(v)) for p, v in m.items())
    if len(lp) > cap:
        raise ValueError(f"{len(lp)} places de force adaptée (capacité {cap})")
    out = b""
    for p, v in lp:
        if len(v) != 5 or not all(1 <= x <= 0x7FFF for x in v):
            raise ValueError(f"multiplicateurs invalides pour 0x{p:08X} : {v}")
        out += struct.pack("<I5hH", p, *v, 0)
    return out + bytes(16 * (cap - len(lp)))


def dec_boss_m(b: bytes, n: int) -> dict[int, tuple[int, ...]]:
    out = {}
    for i in range(n):
        p, *v = struct.unpack_from("<I5h", b, 16 * i)
        out[p] = tuple(v)
    return out


def boss_compile(entete_boss: bytes) -> int | None:
    """Champ `compile` publié par le jeu v7 : BOSS_COMPILE (0 : build --define YKW2_AP_SANS_RANDO_BOSS), None (non
    publié : jeu antérieur)."""
    c = struct.unpack_from("<I", entete_boss, 4)[0]
    if not c & BOSS_PUBLIE:
        return None
    return c & BOSS_COMPILE


def enc_boss_b(b: dict[int, int], cap: int = CAP_BOSS_B) -> bytes:
    """Table B : {place: donneur} triée par place, complétée par des zéros."""
    lp = sorted((p & 0xFFFFFFFF, d & 0xFFFFFFFF) for p, d in b.items())
    if len(lp) > cap:
        raise ValueError(f"{len(lp)} places de boss (capacité {cap})")
    return b"".join(struct.pack("<II", p, d) for p, d in lp) + bytes(8 * (cap - len(lp)))


def enc_boss_n(n: dict[int, tuple[int, int]], cap: int = CAP_BOSS_N) -> bytes:
    """Table N : {place: (espèce d'origine, espèce cible)} triée par place, complétée par des zéros."""
    lp = sorted((p & 0xFFFFFFFF, o & 0xFFFFFFFF, c & 0xFFFFFFFF) for p, (o, c) in n.items())
    if len(lp) > cap:
        raise ValueError(f"{len(lp)} boss sans script (capacité {cap})")
    return b"".join(struct.pack("<IIII", p, o, c, 0) for p, o, c in lp) + bytes(16 * (cap - len(lp)))


def dec_boss_b(b: bytes, n: int) -> dict[int, int]:
    return dict(struct.unpack_from("<II", b, 8 * i) for i in range(n))


def dec_boss_n(b: bytes, n: int) -> dict[int, tuple[int, int]]:
    out = {}
    for i in range(n):
        p, o, c, _r = struct.unpack_from("<IIII", b, 16 * i)
        out[p] = (o, c)
    return out


def nom_vitrine(objet: str, joueur: str | None = None, max_largeur: int | None = None) -> bytes:
    """Nom de vitrine conseillé : « objet (pour joueur) », une ligne, neutralisé, au plus NOM_TEXTE - 1
    octets (même traitement que le jeu). `max_largeur` : coupe à la largeur estimée (modèle du bandeau)."""
    t = f"{objet} (pour {joueur})" if joueur else objet
    b = copier_texte(t.encode("utf-8"), True)
    if max_largeur:
        b = copier_limite(b, max_largeur)
    return _champ_texte(b, NOM_TEXTE).split(b"\0")[0]


def spots_bits(spots: int) -> list[int]:
    """Index TBox (558..575) des bits de spots publiés dans l'en-tête (champ spots)."""
    return [TBOX_SPOT_PREMIER + k for k in range(TBOX_NOMBRE - TBOX_SPOT_PREMIER) if spots >> k & 1]


def victoire(h: dict) -> bool:
    """Critère de victoire (J2) : flag « partie terminée », ou chapitre >= 11 en secours ; partie chargée."""
    return bool(h["etat"] & ETAT_PARTIE) and bool(h.get("progression", 0)
                                                  & (PROGRESSION_VICTOIRE | PROGRESSION_APRES_JEU))


# --- Notifications : encodage et textes (mêmes règles que boite.cpp) ---
def texte_utf8(texte: str) -> bytes:
    """Texte -> octets UTF-8 d'une entrée (au plus NOTIF_TEXTE - 1, sans couper un caractère)."""
    b = texte.encode("utf-8")
    if len(b) > NOTIF_TEXTE - 1:
        b = b[:NOTIF_TEXTE - 1]
        while b and b[-1] & 0xC0 == 0x80:          # octets de continuation d'un caractère coupé
            b = b[:-1]
        if b and b[-1] >= 0xC0:                    # octet de tête sans sa suite
            b = b[:-1]
    return b


def enc_notif(numero: int, texte: bytes, duree: int = 0, drapeaux: int = 0) -> bytes:
    assert len(texte) < NOTIF_TEXTE
    return struct.pack("<IHBB", numero, duree, drapeaux, 0) + texte.ljust(NOTIF_TEXTE, b"\0")


def dec_notif(b: bytes) -> dict:
    n, d, dr, _ = struct.unpack_from("<IHBB", b)
    return {"numero": n, "duree": d, "drapeaux": dr, "texte": b[8:].split(b"\0")[0]}


def _octets_car(c: int) -> int:
    return 4 if c >= 0xF0 else 3 if c >= 0xE0 else 2 if c >= 0xC0 else 1


def largeur_car(b: bytes, i: int = 0) -> int:
    """Modèle de apLargeurCar : largeur estimée (demi-unités) du caractère UTF-8 en b[i]."""
    c = b[i]
    if c < 0x80:
        ch = chr(c)
        if ch in " il!.,:;'|()[]-Ijftr\"":
            return 2
        if ch in "mwMW@%&":
            return 6
        return 5 if "A" <= ch <= "Z" else 4
    if b[i:i + 3] == "€".encode():
        return 6
    if c == 0xC3 and i + 1 < len(b) and b[i + 1] >= 0x9F:
        return 4
    return 5


def largeur(texte: str | bytes) -> int:
    b = texte.encode() if isinstance(texte, str) else texte
    w, i = 0, 0
    while i < len(b) and b[i]:
        w += largeur_car(b, i)
        i += _octets_car(b[i])
    return w


def copier_limite(src: bytes, max_largeur: int = NOTIF_LARGEUR, cap: int = TAILLE_TAMPON) -> bytes:
    """Modèle de apCopierLimite : coupe src à max_largeur (estimée), suivi de "..." si coupé."""
    couper = largeur(src) > max_largeur
    limite = (max_largeur - 6 if max_largeur > 6 else 0) if couper else max_largeur
    reserve = 3 if couper else 0
    out, i, larg = bytearray(), 0, 0
    while i < len(src) and src[i]:
        n = _octets_car(src[i])
        lc = largeur_car(src, i)
        if larg + lc > limite or len(out) + n + reserve + 1 > cap:
            break
        out += src[i:i + n]
        i += n
        larg += lc
    return bytes(out) + (b"..." if couper else b"")


def copier_texte(src: bytes, neutral: bool = True) -> bytes:
    """Modèle de apCopierTexte : mono-ligne (0x0A, 0x0D et « \\n » -> espace), neutralisation."""
    out, i = bytearray(), 0
    while i < len(src) and src[i]:
        c = src[i]
        i += 1
        if c in (10, 13):
            c = 0x20
        elif c == 0x5C and i < len(src) and src[i] == 0x6E:
            c = 0x20
            i += 1
        elif neutral:
            c = {0x3C: 0x28, 0x5B: 0x28, 0x3E: 0x29, 0x5D: 0x29, 0x5C: 0x2F}.get(c, c)
        out.append(c)
    return bytes(out)


def neutraliser(b: bytes) -> bytes:
    return copier_texte(b, True)


def formater_notif(texte: str, de: str | None = None, max_largeur: int = NOTIF_LARGEUR,
                   une_ligne: bool = False) -> list[str]:
    """Texte(s) conseillé(s) pour le bandeau MONO-LIGNE (~121 demi-unités, E9C) : chaque texte tient
    sur une ligne, coupé avec « ... » au-delà de `max_largeur`. Avec `de` : une 2e notification
    « De : X » (ou, avec une_ligne, « texte (X) » sur la même ligne, coupé si besoin)."""
    texte = copier_texte(texte.encode(), False).decode()
    textes = [f"{texte} ({de})"] if de and une_ligne else [texte] + ([f"De : {de}"] if de else [])
    return [copier_limite(t.encode(), max_largeur).decode() for t in textes]


def texte_evt(e: dict) -> str:
    t = EVTS.get(e["type"], f"?{e['type']}")
    d = e["drapeaux"]
    if e["type"] == 1:
        dr = ",".join(n for b, n in ((1, "marqué-ouvert"), (2, "remplacé"), (4, "affichage-seul")) if d & b) or "-"
        return (f"#{e['numero']} COFFRE tbox={e['id']:#010x} index={e['index'] if e['index'] != 0xFFFFFFFF else '?'} "
                f"natif={e['valeur']:#010x}x{e['quantite']} rendu={e['valeur2']:#010x} etiquette={e['etiquette']} [{dr}]")
    if e["type"] == 2:
        dr = ",".join(n for b, n in ((1, "supprimé"), (2, "réussi"), (4, "substitué"), (8, "bit-posé"))
                      if d & b) or "échec"
        if d & EVT_OBJET_SUBSTITUE:
            idx = e["index"] if e["index"] != 0xFFFFFFFF else "-"
            return (f"#{e['numero']} OBJET_JEU objet={e['id']:#010x}x{e['quantite']} affiché={e['valeur2']:#010x} "
                    f"bit={idx} etiquette={e['etiquette']} retour={e['valeur']} [{dr}]")
        return f"#{e['numero']} OBJET_JEU objet={e['id']:#010x}x{e['quantite']} retour={e['valeur']} [{dr}]"
    if e["type"] == EVT_RECOMPENSE:
        dr = ",".join(n for b, n in ((RECOMPENSE_FIXE, "objets-fixes"), (RECOMPENSE_CHOIX, "choix"),
                                     (RECOMPENSE_DONNE, "donné")) if d & b) or "-"
        return (f"#{e['numero']} RECOMPENSE quête={e['id']} affiché={e['valeur']:#010x} etiquette={e['etiquette']} "
                f"[{dr}]")
    if e["type"] == EVT_BOUTIQUE:
        dernier = " [dernier]" if d & BOUTIQUE_EVT_DERNIER else ""
        return f"#{e['numero']} BOUTIQUE bits visibles={bits_evt_boutique(e)}{dernier}"
    if e["type"] in (3, 4):
        q = struct.unpack("<i", struct.pack("<I", e["valeur2"]))[0]
        return (f"#{e['numero']} {t} numero_don={e['valeur']} type={NOMS_DON.get(e['index'], e['index'])} "
                f"hash={e['id']:#010x} quantite={q} code={CODES.get(d, d)}")
    return f"#{e['numero']} {t} {e}"


# --- Compléments pour le client du mod (valeurs de la doc, pas de #define dans boite.h) ---
TAILLE_ENTETE = 0x100
TAILLE_DON, TAILLE_EVT, TAILLE_COFFRE = 16, 32, 16
EVT_COFFRE, EVT_OBJET_JEU, EVT_DON, EVT_DON_ECHEC = 1, 2, 3, 4
DON_OBJET, DON_ARGENT, DON_YOKAI = 1, 2, 3
CODE_OK, CODE_TYPE_INCONNU, CODE_OBJET_INCONNU, CODE_ECHEC_DON, CODE_PARTIE, CODE_QUANTITE = 0, 1, 2, 3, 4, 5
CODE_NON_LIEE = 6


def hachage_invitation(cle: str) -> int:
    """Hachage de l'objet du JEU d'une invitation (clé de `objets.json`, « invitation_<nom> ») : `crc32("ap_" + clé)`,
    la convention de `installation/invitations.py` qui ajoute ces objets au RomFS du joueur (identifiant à nous, absent
    du jeu d'origine ; `docs/systemes/archipelago_invites.md` §16)."""
    import zlib
    return zlib.crc32(("ap_" + cle).encode("ascii")) & 0xFFFFFFFF
ETAT_PARTIE, ETAT_TERRAIN, ETAT_STABLE, ETAT_BLOQUE, ETAT_ATTENTE, ETAT_PAUSE = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20
ETAT_PANIQUE = 0x40          # le jeu a paniqué (svc Break) : enregistrement ApPanique (§28), bit collant
# Lieu du joueur (§29, branche ap/carte-suivi) : carte courante et position publiées dans l'en-tête (aucune lecture en
# plus : le tour de base lit déjà l'en-tête). ETAT_LIEU : ce jeu publie `carte` (0x80, CRC-32 du nom de la carte, 0 =
# aucune) ; ETAT_POSITION : `pos_x` / `pos_z` (0x84 / 0x88) valides à cette image.
ETAT_LIEU, ETAT_POSITION = 0x80, 0x100
POSITION_MAX = 1.0e6         # garde-fou : une coordonnée au-delà (ou non finie) n'est pas une position
# Fenêtre d'amitié en combat (§53, branche ap/fenetre-amitie-combat ; docs/systemes/archipelago_fenetre_amitie.md) :
# ETAT_AMIS_COMBAT = ce jeu publie ApAmisCombat et `amis_numero` (0xF6) ; ETAT_EN_COMBAT = combat en cours à cette image.
# Le client ne lit la zone (0x40 octets, un paquet) que pendant un combat, quand `amis_numero` change.
ETAT_AMIS_COMBAT, ETAT_EN_COMBAT = 0x200, 0x400
OFF_AMIS_COMBAT, TAILLE_AMIS_COMBAT = 0x23780, 0x40
AMIS_COMBAT_PUBLIE = 0x31435041     # « APC1 »
AMIS_COMBAT_COMPILE = 0x01
CAP_AMIS_COMBAT = 6
AMI_NON, AMI_OUI, AMI_INCONNU = 0, 1, 2


def lire_amis_combat(b: bytes) -> dict | None:
    """ApAmisCombat (0x40 octets à OFF_AMIS_COMBAT) : {publie, compile, numero, en_combat, nombre, mises_a_jour,
    ennemis: [{param, medaille, ami, emplacement}]} ; None si le bloc est trop court."""
    if len(b) < TAILLE_AMIS_COMBAT:
        return None
    publie, compile_, numero, en_combat, nombre, maj = struct.unpack_from("<IIIBBH", b, 0)
    ennemis = []
    for k in range(min(nombre, CAP_AMIS_COMBAT)):
        param, medaille, ami, emplacement = struct.unpack_from("<IHBB", b, 0x10 + 8 * k)
        ennemis.append({"param": param, "medaille": medaille, "ami": ami, "emplacement": emplacement})
    return {"publie": publie, "compile": compile_, "numero": numero, "en_combat": en_combat, "nombre": nombre,
            "mises_a_jour": maj, "ennemis": ennemis}


def enc_amis_combat(numero: int, en_combat: bool, ennemis, mises_a_jour: int = 0,
                    publie: int = AMIS_COMBAT_PUBLIE, compile_: int = AMIS_COMBAT_COMPILE) -> bytes:
    """Bloc ApAmisCombat tel que le jeu l'écrit (outils d'essai, modèle du jeu des tests) ; `ennemis` : n-uplets
    (param, medaille, ami, emplacement)."""
    ennemis = list(ennemis)[:CAP_AMIS_COMBAT]
    b = bytearray(TAILLE_AMIS_COMBAT)
    struct.pack_into("<IIIBBH", b, 0, publie, compile_, numero & 0xFFFFFFFF, 1 if en_combat else 0, len(ennemis),
                     mises_a_jour & 0xFFFF)
    for k, (param, medaille, ami, emplacement) in enumerate(ennemis):
        struct.pack_into("<IHBB", b, 0x10 + 8 * k, param & 0xFFFFFFFF, medaille & 0xFFFF, ami & 0xFF, emplacement & 0xFF)
    return bytes(b)


def amis_combat_accepte(d: dict | None, amis_numero: int) -> bool:
    """Bloc lu cohérent avec l'en-tête lu avant lui : zone publiée et compilée, `numero` PAIR (écriture finie) et égal
    (modulo 65536) au numéro publié dans l'en-tête. Sinon : relire au tour suivant."""
    return bool(d and d["publie"] == AMIS_COMBAT_PUBLIE and d["compile"] & AMIS_COMBAT_COMPILE
                and d["numero"] % 2 == 0 and d["numero"] & 0xFFFF == amis_numero & 0xFFFF)


# Loupe plus parlante (§54, branche ap/loupe-pas-eu ; docs/systemes/archipelago_loupe_amis.md) : ETAT_LOUPE = ce jeu
# publie ApLoupe et `loupe_numero` (0xFC, ancien `liaison_manuelle`, toujours pair) ; ETAT_LOUPE_CIBLE = le radar de la
# montre vise un point de loupe à cette image. Le client ne lit la zone (0x40 octets, un paquet) que si le radar vise
# un point et que `loupe_numero` a changé.
ETAT_LOUPE, ETAT_LOUPE_CIBLE = 0x800, 0x1000
# Objets montrés avec leur image (archipelago_invites.md §21) : ETAT_DEFINITIONS = la table des objets du jeu contient
# la définition sonde (patch à jour ET RomFS du mod installé) ; sans ce bit, le client garde la vitrine.
ETAT_DEFINITIONS, SONDE_DEFINITIONS = 0x2000, 0x7BD5B3D5
OFF_LOUPE, TAILLE_LOUPE = 0x237C0, 0x40
LOUPE_PUBLIE = 0x314C5041           # « APL1 »
LOUPE_COMPILE = 0x01
CAP_LOUPE = 4
LOUPE_GENRE_APPEAR, LOUPE_GENRE_FIXE = 0, 1


def lire_loupe(b: bytes) -> dict | None:
    """ApLoupe (0x40 octets à OFF_LOUPE) : {publie, compile, numero, cible, nombre, genre, autres, point, mises_a_jour,
    identifiant, base, appear, especes: [{param, medaille, ami, poids}]} ; None si le bloc est trop court."""
    if len(b) < TAILLE_LOUPE:
        return None
    (publie, compile_, numero, cible, nombre, genre, autres, point, maj, identifiant, base,
     appear) = struct.unpack_from("<IIIBBBBHHIII", b, 0)
    especes = []
    for k in range(min(nombre, CAP_LOUPE)):
        param, medaille, ami, poids = struct.unpack_from("<IHBB", b, 0x20 + 8 * k)
        especes.append({"param": param, "medaille": medaille, "ami": ami, "poids": poids})
    return {"publie": publie, "compile": compile_, "numero": numero, "cible": cible, "nombre": nombre, "genre": genre,
            "autres": autres, "point": point, "mises_a_jour": maj, "identifiant": identifiant, "base": base,
            "appear": appear, "especes": especes}


def enc_loupe(numero: int, cible: bool, especes=(), point: int = 0, identifiant: int = 0, base: int = 0,
              appear: int = 0, genre: int = LOUPE_GENRE_APPEAR, autres: int = 0, mises_a_jour: int = 0,
              publie: int = LOUPE_PUBLIE, compile_: int = LOUPE_COMPILE) -> bytes:
    """Bloc ApLoupe tel que le jeu l'écrit (outils d'essai, modèle du jeu des tests) ; `especes` : n-uplets
    (param, medaille, ami, poids)."""
    especes = list(especes)[:CAP_LOUPE] if cible else []
    b = bytearray(TAILLE_LOUPE)
    struct.pack_into("<IIIBBBBHHIII", b, 0, publie, compile_, numero & 0xFFFFFFFF, 1 if cible else 0, len(especes),
                     genre & 0xFF if cible else 0, autres & 0xFF if cible else 0, point & 0xFFFF if cible else 0,
                     mises_a_jour & 0xFFFF, identifiant & 0xFFFFFFFF if cible else 0, base & 0xFFFFFFFF if cible else 0,
                     appear & 0xFFFFFFFF if cible else 0)
    for k, (param, medaille, ami, poids) in enumerate(especes):
        struct.pack_into("<IHBB", b, 0x20 + 8 * k, param & 0xFFFFFFFF, medaille & 0xFFFF, ami & 0xFF, poids & 0xFF)
    return bytes(b)


def loupe_accepte(d: dict | None, loupe_numero: int) -> bool:
    """Bloc lu cohérent avec l'en-tête lu avant lui : zone publiée et compilée, `numero` PAIR (écriture finie) et égal
    au numéro publié dans l'en-tête. Sinon : relire au tour suivant."""
    return bool(d and d["publie"] == LOUPE_PUBLIE and d["compile"] & LOUPE_COMPILE
                and d["numero"] % 2 == 0 and d["numero"] & 0xFFFFFFFF == loupe_numero & 0xFFFFFFFF)


def lieu_publie(etat: int, carte: int, pos_x: int, pos_z: int) -> tuple[int, tuple[float, float] | None] | None:
    """(hachage de la carte courante, position (x, z) ou None) publiés par le jeu ; None si le jeu ne publie pas le
    lieu (patch antérieur : bit ETAT_LIEU absent, les octets 0x80..0x8B y sont privés). Carte 0 : aucune carte (titre,
    chargement, pas de partie)."""
    if not etat & ETAT_LIEU:
        return None
    if not carte or not etat & ETAT_POSITION:
        return carte, None
    x, z = struct.unpack("<ff", struct.pack("<II", pos_x & 0xFFFFFFFF, pos_z & 0xFFFFFFFF))
    if not (x == x and z == z and abs(x) <= POSITION_MAX and abs(z) <= POSITION_MAX):
        return carte, None
    return carte, (x, z)
# drapeaux des évènements (§6)
EVT_COFFRE_MARQUE_OUVERT, EVT_COFFRE_REMPLACE, EVT_COFFRE_AFFICHAGE_SEUL = 0x01, 0x02, 0x04
EVT_OBJET_SAUTE, EVT_OBJET_REUSSI = 0x01, 0x02
# bloc de progression P (adresse publiée dans l'en-tête, champ adresse_p)
P_COMPTEUR, P_IDENT, P_LIAISON = 0x3B8, 0x3BC, 0x3B6
P_FLAGS_TBOX, TAILLE_FLAGS_TBOX = 0x3C4, 0x48      # 576 bits : bit i = flag TBox d'index i
# flags bit globaux (FUN_00412F08 / FUN_00413464) : flag i = bit i % 8 de l'octet P + 4 + i // 8 (sauvegardés,
# bloc 1) ; le client ne lit que des flags dont l'octet précède P_LIAISON (octets libres du mod ensuite)
P_FLAGS_GLOBAUX = 0x004
FLAG_GLOBAL_MAX = (P_LIAISON - P_FLAGS_GLOBAUX) * 8 - 1
# Yo-criminels (docs/systemes/archipelago_amis_criminels.md §3) : octet `wantedNN` (flag de catégorie 6 n° 396 + N de
# flag_config ; octets de catégorie 6 à P + 0x144 + i) = P + 0x2D0 + N, N = 1..52 : nombre d'étapes gagnées contre le
# criminel N (+1 à chaque victoire, ev76_0400 ; jamais remis à zéro) [C]
P_CRIMINELS, NB_CRIMINELS = 0x2D0, 52
# Détection de secours d'un don de script fait SANS table de substitution (client absent, table perdue au
# relancement : le script donne l'objet d'origine, aucun bit de spot n'est posé, §12.2) : bit de spot -> flag bit
# global « évènement vu » posé à la fin de la scène jouée juste après le don dans le même script, et nulle part
# ailleurs [C]. Filet : c01_trigger RunCmd_Phase16, AddItem 0x4806448E puis RunEvent('ev01_0800') (seul appel de
# cette scène) ; crc32("ev01_0800") = 0x64082BC4 = flag 113 (catégorie 0 de flag_config_0.01), qu'aucun script
# n'écrit. Seul le Filet en a besoin : seul emplacement qui accepte la progression (archipelago_logique_audit.md G1-3).
SPOTS_SECOURS = {558: 113}
INDEX_INCONNU = 0xFFFFFFFF
# bloc des quêtes Q = *(*0x00815244 + 0x10), HORS boîte (le client le suit lui-même, archipelago_boss.md §10) :
# phase de la quête n (4e champ de QUEST_CONFIG, nom « qs%04d ») = octet Q + 4 + n, n < 192 (GetQuestPhase
# 0x004BE680 -> FUN_0041015C -> FUN_00646EB8) ; 255 = terminée. 0x815244 est un pointeur partagé {objet, compteur}
# créé et libéré avec P et les autres blocs de sauvegarde (FUN_005D9438 / FUN_005DE030) ; le chargement d'une
# sauvegarde relit le bloc 0xC EN PLACE (Q+4..Q+0xF3, FUN_003FC408).
ADR_SINGLETON_QUETES = 0x00815244
OFF_OBJET_SINGLETON = 0x10
Q_PHASES, NB_QUETES = 0x004, 192
PHASE_QUETE_TERMINEE = 255
# rang de montre réel (valeur de la condition GetWatchRank, 0 = E … 5 = S) : octet O + 0x2E, O = *(*0x0081521C + 0x10)
# (FUN_0040F420 ; 0x0081521C est un pointeur partagé {objet, compteur} comme 0x00815244 ; l'objet +8 est le bloc 0xF2
# de la sauvegarde, rang à +0x26 du bloc [C, archipelago_objets_cles_v11.md §5.1 ; sauvegardes de l'humain]).
ADR_SINGLETON_RANG = 0x0081521C
OFF_RANG_MONTRE = 0x2E
RANG_MONTRE_MAX = 5
# adresses de tas plausibles pour un objet du jeu (tas 0x08000000.., tas linéaire 0x14000000.. / 0x30000000..)
ADR_TAS_MIN, ADR_TAS_MAX = 0x08000000, 0x40000000

# --- Enregistreur de panique (§28, src/archipelago/panique.cpp ; absent avec --define YKW2_AP_SANS_PANIQUE) ---
# ApPanique (0x200 octets) à 0x23E00, dans la zone v10 (taille et version inchangées). Le jeu y recopie, à la panique
# (FUN_001371D4, svc Break « PANIC »), l'adresse de retour empilée (après le `bl` fautif), r4..r11 et 96 mots de la pile
# de la fonction qui a paniqué, pose ETAT_PANIQUE dans l'en-tête, puis attend (au plus 20 s, l'émulateur tourne) que le
# client écrive `lu` = `compte` avant de rendre la main (svc Break comme d'origine).
OFF_PANIQUE, TAILLE_PANIQUE, PANIQUE_MOTS = 0x23E00, 0x200, 96
PANIQUE_OFF_LU = 0x40
PANIQUE_CHAMPS = ("compte", "appelant", "raison", "pile")
# Plages d'adresses de code (adresses de retour plausibles dans la pile) : .text d'origine, zone d'extension (code du mod
# relogé ou ajouté, après la boîte : 0x0091C000 + 0x28000 depuis fix/nom-don-script).
CODE_TEXTE = (0x00100000, 0x006F4000)
CODE_EXTENSION = (0x00944000, 0x00A00000)


def enc_panique(compte: int, appelant: int, raison: int = 0, pile: int = 0, regs=(), images: int = 0, etat: int = 0,
                chapitre: int = 0, pas: int = 0, terrain: int = 0, lu: int = 0, attendu_ms: int = 0,
                mots=()) -> bytes:
    """Enregistrement tel que le jeu l'écrit (tests, ap_boite_test.py)."""
    r = list(regs)[:8] + [0] * (8 - len(list(regs)[:8]))
    m = list(mots)[:PANIQUE_MOTS] + [0] * (PANIQUE_MOTS - len(list(mots)[:PANIQUE_MOTS]))
    return (struct.pack("<4I8I2I2HI2I", compte, appelant, raison, pile, *r, images, etat, chapitre, pas, terrain, lu,
                        attendu_ms) + bytes(14 * 4) + struct.pack(f"<{PANIQUE_MOTS}I", *m))


def dec_panique(b: bytes) -> dict:
    compte, appelant, raison, pile = struct.unpack_from("<4I", b)
    regs = list(struct.unpack_from("<8I", b, 0x10))
    images, etat, chapitre, pas, terrain, lu, attendu = struct.unpack_from("<2I2HI2I", b, 0x30)
    mots = list(struct.unpack_from(f"<{PANIQUE_MOTS}I", b, 0x80))
    return {"compte": compte, "appelant": appelant, "raison": raison, "pile": pile, "regs": regs, "images": images,
            "etat": etat, "chapitre": chapitre, "pas": pas, "terrain_numero": terrain, "lu": lu, "attendu_ms": attendu,
            "mots": mots}


def est_code(v: int) -> bool:
    return CODE_TEXTE[0] <= v < CODE_TEXTE[1] or CODE_EXTENSION[0] <= v < CODE_EXTENSION[1]


def retours_panique(d: dict) -> list[tuple[int, int]]:
    """Mots de la pile qui ressemblent à des adresses de retour (code d'origine ou du mod) : [(décalage, adresse)].
    Bit 0 (retour Thumb) gardé tel quel. Les adresses se lisent avec la carte du build installé (ykw2.map)."""
    return [(4 * i, v) for i, v in enumerate(d["mots"]) if est_code(v & ~1)]


def texte_panique(d: dict) -> str:
    """Une ligne pour le journal du client."""
    r = ", ".join(f"+{o:#x}:{v:#010x}" for o, v in retours_panique(d)) or "aucune"
    return (f"panique n° {d['compte']} (raison {d['raison']}) : retour {d['appelant']:#010x} (le `bl` fautif est juste "
            f"avant), pile {d['pile']:#010x}, image {d['images']}, état {d['etat']:#x}, chapitre {d['chapitre']}-"
            f"{d['pas']}, terrain n° {d['terrain_numero']} ; r4..r11 "
            + " ".join(f"{x:#x}" for x in d["regs"]) + f" ; adresses de retour dans la pile : {r}")


# --- Verrous ÉTENDUS de la V3 (src/archipelago/boite.h ApVerrous2, verrous.h ; archipelago_boite.md §34) ---
# Les 24 n° de verrou de la zone ApVerrous et ses bits 24..31 sont tous pris. Zone de 0x80 octets juste après ApPnj
# (0 dans un jeu antérieur). Verrou étendu k (40..55) = bit k - 40 de `actifs` (C) / `compiles` (J, bit 31 = liste
# publiée) et octet recu[k - 40] (C) ; bits 24..30 : options étendues du joueur (compilée ET choisie). `ident` (C) =
# identifiant de partie pour lequel la zone vaut (le jeu l'ignore s'il diffère de celui de l'en-tête). Le client lit
# `compiles` une fois par instance du jeu quand la graine a un verrou ou une option étendus, et écrit recu[] + ident
# puis `actifs` en dernier, seulement quand ils changent : aucun paquet périodique.
OFF_VERROUS2, TAILLE_VERROUS2, CAP_VERROUS2 = 0x23240, 0x80, 16
VERROU2_BASE = 40
VERROUS2_PUBLIES = 0x80000000
VERROU_MONTRE = 40           # Yo-kai Watch : Cible, Âmultime, Purification et interface zéro fermés en combat
VERROU_DOCUMENTS = 41        # Documents perdus : remise à Papa refusée (t104i53_quest_trigger n° 3, qs0009)
VERROU_CARTES = 42           # Cartes d'Ultramax : remise refusée (t131i01_quest_trigger n° 4 / 5, qs0014)
OPTION2_TUNNEL = 24          # option étendue : Tunnel sans fin sans limite par jour (bit global 2528 lu faux)
NOMS_OPTIONS2 = {OPTION2_TUNNEL: "Tunnel sans fin sans limite par jour"}
VERROUS2_CHAMPS = {"actifs": 0x00, "compiles": 0x04, "ident": 0x18, "tunnel_rendus": 0x1C, "montre_memo": 0x60}
MONTRE_MEMO_FAIT, MONTRE_MEMO_VERROU = 2, 1
FLAG_CIBLE = 0x3E1E067A      # flag 54 : bouton Cible du combat
FLAG_MODELE_ZERO_NATIF, FLAG_EV06_BTL0040 = 0x63C11B45, 0xFD86C9F0   # exemption de la montre : 6-20 -> ev06_btl0040
FLAG_TUNNEL_JOUR = 0x6F7D22E6           # bit global 2528 : Tunnel sans fin déjà fait aujourd'hui
MASQUE_PURIFICATION = 1024              # argument de la commande 0x3C5E
REGLE_SANS_AMULTIME = 0x00400000        # règle du combat lue par la commande 0x3C62
MONTRE_GARCON, MONTRE_FILLE = 0x4F6B8097, 0xD662D12D   # objet Yo-kai Watch du jeu selon le personnage joué
# Dons de script substitués (J3) que le jeu d'origine fait SANS fenêtre « objet obtenu » : `AddItem(objet, n, 0)` (pas de
# 0x35B8), la substitution remplace l'objet en silence. Recensement de toutes les voies de don des emplacements
# d'objets-clés (`archipelago_anim_objet.md` §6bis, branche fix/fenetre-don-montre) : seule la Yo-kai Watch (c01_trigger
# n° 35 / 36, phase 1-90) ; tous les autres passent par `AddItem(…, 1)` (fenêtre 0x35B8, accrochée) ou `AddItemWin`
# (fenêtre d'`OpenInfoWinEx`). Le client montre la fenêtre de ces dons par la file ApAnim (§27), au moment sûr.
DONS_SANS_FENETRE = frozenset({MONTRE_GARCON, MONTRE_FILLE})
# Don d'origine -> don visible PLUS TÔT de la même histoire, à substituer aussi pour la même location
# (`archipelago_objets_cles_v11.md` §21) : Montre étrange du magasin (1-86, c01_trigger n° 33 / 34, `AddItem(…, 1)` :
# fenêtre 0x35B8), rendue au joueur comme Yo-kai Watch à 1-90. Le check part à la fenêtre du magasin ; le don de 1-90
# reste substitué (ne donne rien) et son flag 123 reste le filet.
MONTRE_ETRANGE_GARCON, MONTRE_ETRANGE_FILLE = 0x36B73833, 0x41B008A5
DONS_EN_AMONT = {MONTRE_GARCON: MONTRE_ETRANGE_GARCON, MONTRE_FILLE: MONTRE_ETRANGE_FILLE}
# déclencheurs de quête refusés : (type, n, identifiant, carte du joueur ou None) -> verrou
DECLENCHEURS2 = {(13, 3, 0x6DF692F0, None): VERROU_DOCUMENTS,
                 (11, 4, 0xF9A7133D, 0x2DE564BA): VERROU_CARTES, (11, 5, 0xF9A7133D, 0x2DE564BA): VERROU_CARTES}


def options2_actives(tunnel_sans_limite: bool) -> int:
    """Bits d'options étendues à poser dans ApVerrous2::actifs."""
    return (1 << OPTION2_TUNNEL) if tunnel_sans_limite else 0


def enc_verrous2(actifs: int, recu, ident: int) -> bytes:
    """Partie CLIENT de ApVerrous2 : actifs (+0), [compiles : jeu], recu[16] (+8), ident (+0x18) : 0x1C octets."""
    r = bytearray(CAP_VERROUS2)
    for k, v in (recu.items() if isinstance(recu, dict) else enumerate(recu)):
        i = k - VERROU2_BASE if k >= VERROU2_BASE else k
        if 0 <= i < CAP_VERROUS2:
            r[i] = 1 if v else 0
    return struct.pack("<II", actifs & 0x7FFFFFFF, 0) + bytes(r) + struct.pack("<I", ident & 0xFFFFFFFF)


def dec_verrous2(b: bytes) -> dict:
    """ApVerrous2 (0x80 octets à OFF_VERROUS2) ; au moins les 8 premiers octets."""
    b = bytes(b).ljust(TAILLE_VERROUS2, b"\0")
    d = {n: struct.unpack_from("<I", b, o)[0] for n, o in VERROUS2_CHAMPS.items()}
    d["recu"] = list(b[8:8 + CAP_VERROUS2])
    d["appliques"] = list(struct.unpack_from("<8I", b, 0x20))
    d["exemptes"] = list(struct.unpack_from("<8I", b, 0x40))
    return d


def verrous2_compiles(b: bytes) -> int | None:
    """Masque des verrous (bits 0..15) et options (24..30) étendus compilés dans le jeu, None si la liste n'est pas
    publiée (jeu antérieur à la V3)."""
    c = struct.unpack_from("<I", b, 4)[0]
    return c & ~VERROUS2_PUBLIES if c & VERROUS2_PUBLIES else None


def verrou2_compile(compiles: int | None, k: int) -> bool:
    return compiles is not None and VERROU2_BASE <= k < VERROU2_BASE + CAP_VERROUS2 \
        and bool(compiles >> (k - VERROU2_BASE) & 1)


def verrous2_valides(b: bytes, ident_client: int) -> bool:
    """Modèle de apVerrous2Valides (boite.cpp) : la zone vaut pour la partie du client connecté."""
    return ident_client == 0 or dec_verrous2(b)["ident"] == ident_client


def verrou2_actif(b: bytes, k: int, ident_client: int = 0) -> bool:
    """Modèle de apVerrou2Actif (boite.cpp) : verrou étendu k compilé, actif, objet non reçu, zone valide (la
    condition « sauvegarde liée » est vérifiée à part par le jeu)."""
    if not VERROU2_BASE <= k < VERROU2_BASE + CAP_VERROUS2:
        return False
    d = dec_verrous2(b)
    i = k - VERROU2_BASE
    return verrou2_compile(verrous2_compiles(b), k) and bool(d["actifs"] >> i & 1) and not d["recu"][i] \
        and verrous2_valides(b, ident_client)


def option2_active(b: bytes, bit: int, ident_client: int = 0) -> bool:
    """Modèle de apOption2Active : option étendue compilée, choisie, zone valide (liaison vérifiée à part)."""
    c = verrous2_compiles(b)
    return 24 <= bit < 31 and c is not None and bool(c >> bit & 1) and bool(dec_verrous2(b)["actifs"] >> bit & 1) \
        and verrous2_valides(b, ident_client)


def montre_decision(b: bytes, liee: bool, flag21: bool, combat_gagne: bool, ident_client: int = 0) -> bool:
    """Modèle de la décision de apMontreVerrouillee (verrous.cpp), prise à la première lecture d'un combat : le verrou
    « montre » s'applique s'il est en vigueur, hors de la fenêtre 6-20 (flag 21 natif) -> victoire ev06_btl0040."""
    return verrou2_actif(b, VERROU_MONTRE, ident_client) and liee and not (flag21 and not combat_gagne)


def montre_lectures(verrou: bool, cible_brut: bool, regles: int, purification_brut: bool, zero_brut: bool) -> dict:
    """Ce que les quatre lecteurs du combat rendent une fois la décision prise (figée) : flag 54, commande 0x3C62
    (vrai = Âmultime interdit), 0x3C5E(1024) (vrai = purification interdite), 0x3CEF (interface de la Modèle zéro)."""
    return {"cible": cible_brut and not verrou,
            "amultime_interdit": bool(regles & REGLE_SANS_AMULTIME) or verrou,
            "purification_interdite": purification_brut or verrou,
            "modele_zero": zero_brut and not verrou}


def tunnel_vu(b: bytes, brut: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de apTunnelFiltreFlag : bit 2528 lu faux quand l'option est en vigueur."""
    return brut and not (option2_active(b, OPTION2_TUNNEL, ident_client) and liee)


def declencheur2_refuse(b: bytes, type_: int, n: int, ident: int, carte: int, table_de_quete: bool, liee: bool,
                        ident_client: int = 0) -> int | None:
    """Modèle des deux branches étendues de apVerrouDeclencheur : verrou k qui fait ignorer cette entrée, ou None."""
    for (t, nn, i, c), k in DECLENCHEURS2.items():
        if (t, nn, i) == (type_, n, ident) and (c is None or c == carte):
            return k if table_de_quete and liee and verrou2_actif(b, k, ident_client) else None
    return None


# --- V3, lot 2 : accès à l'après-jeu (verrous.h ; docs/systemes/archipelago_v3_acces_postgame.md, boîte §35) ---
# Voie du mystère : quatre clés = quatre verrous étendus par LECTURE de flag (en vigueur : flag lu « clé reçue »).
VERROU_CLE_TERRIFIANTE = 43  # flag 536 : porte de San Fantastico (t121g00)
VERROU_CLE_SANGLIER = 44     # flag 538 : Route des farceurs (t121d25 -> t131d03c)
VERROU_CLE_CERF = 45         # flag 539 : Route des bouffis (t121d25 -> t201d01c)
VERROU_CLE_PAPILLON = 46     # flag 537 : Grand-route dorée (t121d25 -> t121d31)
VERROU_PASS_SORTILEGE = 47   # Pass sortilège : trains de nuit de t100s22 fermés ; reçu : requête 121 proposée tout de suite
FLAGS_VOIE = {0xDAD52F7A: VERROU_CLE_TERRIFIANTE, 0xA99EEB20: VERROU_CLE_SANGLIER, 0x3921F6B1: VERROU_CLE_CERF,
              0xADD21FEC: VERROU_CLE_PAPILLON}
TRAINS_NUIT_SORTILEGE = (0x2EE8BA1C, 0x59EF8A8A)   # TRAIN_DATA de t100s22 vers Gera Gera Land
QUETE_SORTILEGE = 121
VERROUS2_TRAIN = {"train_rec": 0x64, "train_cond": 0x68, "train_echanges": 0x6C}   # ApVerrous2, jeu seulement


def verrou2_en_vigueur(b: bytes, k: int, ident_client: int = 0) -> bool:
    """Modèle de apVerrou2Progressif (sans la liaison, vérifiée à part) : verrou étendu compilé, déclaré actif, zone
    valide ; l'objet peut être reçu ou non (dec_verrous2(b)["recu"][k - 40])."""
    if not VERROU2_BASE <= k < VERROU2_BASE + CAP_VERROUS2:
        return False
    return verrou2_compile(verrous2_compiles(b), k) and bool(dec_verrous2(b)["actifs"] >> (k - VERROU2_BASE) & 1) \
        and verrous2_valides(b, ident_client)


def voie_flag_vu(b: bytes, flag: int, brut: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de la branche « Voie du mystère » de apVerrouFiltreFlag : valeur vue par le jeu pour un flag 536..539."""
    k = FLAGS_VOIE.get(flag)
    if k is None or not (liee and verrou2_en_vigueur(b, k, ident_client)):
        return brut
    return bool(dec_verrous2(b)["recu"][k - VERROU2_BASE])


def train_disponible(b: bytes, train: int, natif: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de FUN_00646558 (builds AP) : les deux trains de nuit de t100s22 sont indisponibles tant que le verrou
    « Pass sortilège » s'applique ; tout autre train (dont les 54 lignes entre les stations) : valeur native."""
    if train in TRAINS_NUIT_SORTILEGE and liee and verrou2_actif(b, VERROU_PASS_SORTILEGE, ident_client):
        return False
    return natif


def quete121_anticipee(b: bytes, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de la décision de apTrainImage : la condition d'apparition de la requête 121 est levée (pointeur nul) tant
    que le verrou est en vigueur ET le Pass reçu."""
    return liee and verrou2_en_vigueur(b, VERROU_PASS_SORTILEGE, ident_client) \
        and bool(dec_verrous2(b)["recu"][VERROU_PASS_SORTILEGE - VERROU2_BASE])


# --- V3, lot 4 : requêtes à transfert de sauvegarde 107..116 dans une même partie (transfert.cpp ;
# docs/systemes/archipelago_v3_transfert.md, boîte §36). Option étendue 25 (bit de ApVerrous2::actifs / compiles, sans
# objet) et fonction étendue 37 du patch (bit 5 de ApPnj::fonctions). Le jeu remplace, à la lecture de `quest_config`
# et du `npc_set` de t100d00, le hachage de chaque clause « GetGlobalByteFlag(0xB3E9494F) ==/!= N » par un faux
# hachage selon N ; la condition rend alors l'octet réel (option hors vigueur) ou N (en vigueur).
OPTION2_TRANSFERT = 25
FONCTION_TRANSFERT = 37
FLAG_TRANSFERT = 0xB3E9494F                                # octet global de catégorie 6, n° 7
FAUX_TRANSFERT = {1: 0xAA80CA2D, 2: 0x33899B97}            # crc32("ap_transfert_1"), crc32("ap_transfert_2")
QUETES_TRANSFERT = {1: (107, 108, 109, 110, 111), 2: (112, 113, 114, 115, 116)}   # camp (valeur de l'octet) -> requêtes
TRANSFERT_APPARITIONS = ("ych_204_01", "ych_205_01")       # NPC_APPEAR de t100d00 récrites (deux enregistrements chacune)
VERROUS2_TRANSFERT = {"transfert_quetes": 0x70, "transfert_pnj": 0x74, "transfert_rendus": 0x78,
                      "transfert_refus": 0x7C}             # ApVerrous2, jeu seulement (diagnostic)
NOMS_OPTIONS2[OPTION2_TRANSFERT] = "Requêtes à transfert de sauvegarde (les deux camps)"


def options2_transfert(transfert: bool) -> int:
    """Bit d'option étendue à ajouter à ApVerrous2::actifs (avec options2_actives) pour une graine qui rend les
    requêtes 107..116 faisables."""
    return (1 << OPTION2_TRANSFERT) if transfert else 0


def transfert_recrit(cond: bytes | None) -> tuple[bytes | None, int, int]:
    """Modèle de transfertRecrit (transfert.cpp) sur une condition décodée (octet 0 nul, u16 longueur - 3 en +1) :
    (condition après l'accroche, nombre de clauses qui portent un faux hachage, citations de forme inattendue)."""
    if not cond or cond[0] != 0:
        return cond, 0, 0
    fin = 3 + (cond[1] | cond[2] << 8)
    if fin > 256 or fin > len(cond):
        return cond, 0, 0
    c, n, refus = bytearray(cond), 0, 0
    faux = {h.to_bytes(4, "big") for h in FAUX_TRANSFERT.values()}
    for i in range(4, fin - 9):
        if c[i - 1] != 0x34:
            continue
        h = bytes(c[i:i + 4])
        if h in faux:
            n += 1
        elif h == FLAG_TRANSFERT.to_bytes(4, "big"):
            if c[i + 4] == 0x32 and c[i + 5:i + 8] == bytes(3) and c[i + 8] in (1, 2) and c[i + 9] in (0x78, 0x79):
                c[i:i + 4] = FAUX_TRANSFERT[c[i + 8]].to_bytes(4, "big")
                n += 1
            else:
                refus += 1
    return bytes(c), n, refus


def transfert_lu(b: bytes, cle: int, reel: int, liee: bool, ident_client: int = 0) -> int:
    """Modèle de la condition 0x004BF538 pour l'octet de transfert et ses faux hachages : valeur vue par le jeu.
    `cle` = hachage lu dans la condition (FLAG_TRANSFERT : clause non récrite ; FAUX_TRANSFERT[N] : clause récrite)."""
    if cle not in FAUX_TRANSFERT.values():
        return reel
    if not (liee and option2_active(b, OPTION2_TRANSFERT, ident_client)):
        return reel
    return 1 if cle == FAUX_TRANSFERT[1] else 2


# Détection d'un don par la PHASE de sa quête (Documents perdus : qs0009 >= 8 ; Cartes d'Ultramax : qs0014 >= 4) :
# entrée {location, quete, phase_min} de `boss`. Pseudo-numéro rangé avec les numéros de quête (catalogue, instantané
# de liaison `quetes`), au-dessus de tout numéro réel (NB_QUETES = 192) ; même lecture groupée des phases.
QUETE_PHASE_BASE = 0x10000


def quete_phase_valide(quete: int, phase_min: int) -> bool:
    return 0 <= quete < NB_QUETES and 1 <= phase_min < PHASE_QUETE_TERMINEE


def quete_phase_pseudo(quete: int, phase_min: int) -> int:
    """Pseudo-numéro de « quête `quete` arrivée à la phase `phase_min` (ou terminée) »."""
    return QUETE_PHASE_BASE | (phase_min & 0xFF) << 8 | (quete & 0xFF)


def quete_phase_decode(pseudo: int) -> tuple[int, int] | None:
    """(quête, phase minimale) d'un pseudo-numéro, None pour un numéro de quête ordinaire."""
    if pseudo < QUETE_PHASE_BASE:
        return None
    return pseudo & 0xFF, (pseudo >> 8) & 0xFF


def quete_atteinte(numero: int, phase: int) -> bool:
    """La phase lue vaut-elle le check de ce numéro (ordinaire : 255 ; pseudo : >= phase minimale) ?"""
    d = quete_phase_decode(numero)
    return phase == PHASE_QUETE_TERMINEE if d is None else phase >= d[1]


# --- V3, lot 5 (docs/systemes/archipelago_v3_lettre_bille_deathlink.md §E ; boîte §37 et §38) ---
# Lettre de Komasan (k = 48) et Bille mystérieuse (k = 49) : verrous étendus de la zone ApVerrous2 (bits 8 et 9), par
# refus d'un déclencheur de quête. Le client n'a rien de nouveau à faire : il écrit déjà tout k de 40 à 55.
VERROU_LETTRE = 48           # remise de la Lettre refusée (t202g00_quest_trigger n° 4, type 11, PNJ 0x834C5E70, qs0011)
VERROU_BILLE = 49            # entrée dans t201d11 sans la scène (t201d11_quest_trigger n° 1, type 73, qs0012)
OBJET_LETTRE, OBJET_BILLE = 0x8A48B278, 0x8D257661     # iky0033, iky0037 : l'objet AP donne le vrai objet du jeu
DECLENCHEURS2.update({(11, 4, 0x834C5E70, None): VERROU_LETTRE, (73, 1, 0xFD12CED6, None): VERROU_BILLE})

# Deuxième zone de verrous étendus : ApVerrous3, 0x100 octets à 0x23300 (0 dans un jeu antérieur). Verrou k (56..87) =
# bit k - 56 de `actifs` (C, +0, écrit EN DERNIER) / `compiles` (J, +4) et octet recu[k - 56] (C, +0x10) ; `publie`
# (J, +8) = VERROUS3_PUBLIES quand la liste est publiée ; `ident` (C, +0x0C) = identifiant de partie pour lequel la zone
# vaut. Aucun verrou n'y est encore compilé. Compteurs u16 du jeu : appliques (+0x40) / exemptes (+0x80) pour 56..87,
# appliques2 (+0xC0) / exemptes2 (+0xD0) pour les verrous 48..55 de ApVerrous2.
OFF_VERROUS3, TAILLE_VERROUS3, CAP_VERROUS3 = 0x23300, 0x100, 32
VERROU3_BASE = 56
VERROUS3_PUBLIES = 0x33565041
VERROUS3_COMPILES_DEFAUT = 0
N_CLIENT_VERROUS3 = 68       # n° « client » proposé pour une graine à verrou k >= 56 (63..66 pris, 67 : transfert)


def enc_verrous3(actifs: int, recu, ident: int) -> bytes:
    """Partie CLIENT de ApVerrous3 : actifs (+0), [compiles, publie : jeu], ident (+0x0C), recu[32] (+0x10) : 0x30
    octets. Le client écrit [0x0C:0x30] puis [0:4] en dernier."""
    r = bytearray(CAP_VERROUS3)
    for k, v in (recu.items() if isinstance(recu, dict) else enumerate(recu)):
        i = k - VERROU3_BASE if k >= VERROU3_BASE else k
        if 0 <= i < CAP_VERROUS3:
            r[i] = min(255, int(v))
    return struct.pack("<IIII", actifs & 0xFFFFFFFF, 0, 0, ident & 0xFFFFFFFF) + bytes(r)


def dec_verrous3(b: bytes) -> dict:
    """ApVerrous3 (0x100 octets à OFF_VERROUS3) ; au moins les 0x30 premiers octets."""
    d = dict(zip(("actifs", "compiles", "publie", "ident"), struct.unpack_from("<IIII", b, 0)))
    d["recu"] = list(b[0x10:0x10 + CAP_VERROUS3])
    if len(b) >= TAILLE_VERROUS3:
        d["appliques"] = list(struct.unpack_from("<32H", b, 0x40))
        d["exemptes"] = list(struct.unpack_from("<32H", b, 0x80))
        d["appliques2"] = list(struct.unpack_from("<8H", b, 0xC0))
        d["exemptes2"] = list(struct.unpack_from("<8H", b, 0xD0))
    return d


def verrous3_compiles(b: bytes) -> int | None:
    """Verrous 56..87 compilés (bit k - 56), None si le jeu ne publie pas la zone (patch d'avant le lot 5)."""
    d = dec_verrous3(b)
    return d["compiles"] if d["publie"] == VERROUS3_PUBLIES else None


def verrou3_en_vigueur(b: bytes, k: int, ident_client: int = 0) -> bool:
    """Modèle d'apVerrou3EnVigueur, hors sauvegarde liée : publié, compilé, actif, zone valide."""
    if not VERROU3_BASE <= k < VERROU3_BASE + CAP_VERROUS3:
        return False
    d, c = dec_verrous3(b), verrous3_compiles(b)
    i = k - VERROU3_BASE
    return c is not None and bool(c >> i & 1) and bool(d["actifs"] >> i & 1) \
        and (ident_client == 0 or d["ident"] == ident_client)


def verrou3_actif(b: bytes, k: int, ident_client: int = 0) -> bool:
    """Modèle d'apVerrou2Actif pour k >= 56 (hors sauvegarde liée) : en vigueur et objet non reçu."""
    return verrou3_en_vigueur(b, k, ident_client) and not dec_verrous3(b)["recu"][k - VERROU3_BASE]


# DeathLink : parties PERDUES de la Terr'heure et de Blasters (même loop, gestionnaire M = *0x008151B4). Bit MORT_ORGE
# de ApMort::compile ; ApMortOrge (0x40 octets à OFF_MORT_ORGE), jeu seulement : lu par `ap_boite_test.py morts`,
# jamais par le client (une partie perdue est publiée par `defaites` de l'en-tête, comme une défaite de combat).
MORT_ORGE = 0x10
OFF_MORT_ORGE, TAILLE_MORT_ORGE = 0x232C0, 0x40
MORT_ORGE_CHAMPS = ("etat", "parties", "perdues", "publiees", "satisfaites", "non_liees", "reussies", "sans_verdict",
                    "issue", "verdict", "bilan", "image", "defaites_debut", "deja")
ORGE_EN_COURS, ORGE_VERDICT_PERDU, ORGE_VERDICT_REUSSI = 0x01, 0x02, 0x04
ORGE_TYPE_BLASTERS_PERDU, ORGE_TYPE_REUSSI, ORGE_TYPE_TERREUR_PERDUE = 63, 65, 66
ORGE_ISSUES = {0: "aucune partie finie", 1: "perdue : défaite publiée (DeathLink envoyé par le client)",
               2: "perdue : mort reçue en attente satisfaite (rien d'envoyé)", 3: "perdue : sauvegarde non liée (rien)",
               4: "réussie (rien)", 5: "finie sans verdict vu (rien)",
               6: "perdue : une défaite était déjà publiée pendant la partie (rien de plus)",
               7: "perdue pendant une défaite de combat forcée (rien)"}
ORGE_VERDICTS = {0: "aucun", 63: "63 (Blasters : partie perdue)", 65: "65 (réussite : quelqu'un est sorti)",
                 66: "66 (Terr'heure perdue)"}


def mort_orge(b: bytes) -> bool:
    """Parties perdues du mode publiées par le jeu : bit MORT_ORGE du champ `compile` publié de ApMort."""
    c = struct.unpack_from("<I", b, 0)[0]
    return bool(c & MORT_PUBLIE) and bool(c & MORT_ORGE)


def lire_mort_orge(b: bytes) -> dict:
    """ApMortOrge : les 0x40 octets à OFF_MORT_ORGE."""
    return {n: struct.unpack_from("<I", b, 4 * i)[0] for i, n in enumerate(MORT_ORGE_CHAMPS)}


# --- V3, lot 7 (docs/systemes/archipelago_v3_objets_cles_2.md ; boîte §39) ---
# Objets-clés de plus, verrous étendus de ApVerrous2 (k = 50..55) et de ApVerrous3 (k = 56..58).
VERROU_CAPSULES = 50         # Capsules de lait : c09_trigger n° 10 refusé (entrée dans t200d00, 9-80 : avant le siège)
VERROU_GRELOT = 51           # Grelot félin   } c05_trigger n° 12 refusé (entrée dans t231i03, 5-130 : fin du chapitre 5)
VERROU_MONTRE_LUXE = 52      # Montre de luxe } tant que l'un des deux, en vigueur, n'est pas reçu
VERROU_MIROIRS = 53          # Miroirs Miroirfeuille : flag 17 lu « natif ET objet reçu »
VERROU_CEINTURE = 54         # Ceinture de force : remise refusée (t103i03_quest_trigger n° 2, qs0044)
VERROU_ROBOT_NEUF = 55       # Robot rétro neuf : remise refusée (t231i05_quest_trigger n° 1, qs0048 phase 5)
VERROU_ROBOT_USE = 56        # Robot mécanique usé : remise refusée (t106i02_quest_trigger n° 12, fin de qs0048)
VERROU_SERVIETTE = 57        # Serviette douce : remise refusée (t103i38 / t103i39_quest_trigger n° 3, qs0080)
VERROU_DANCE = 58            # Dance Revolution : remise refusée (t121g00_quest_trigger n° 72, qs0098)
NOMS_VERROUS_LOT7 = {VERROU_CAPSULES: "Capsules de lait", VERROU_GRELOT: "Grelot félin",
                     VERROU_MONTRE_LUXE: "Montre de luxe", VERROU_MIROIRS: "Miroirs", VERROU_CEINTURE: "Ceinture de force",
                     VERROU_ROBOT_NEUF: "Robot rétro neuf", VERROU_ROBOT_USE: "Robot mécanique usé",
                     VERROU_SERVIETTE: "Serviette douce", VERROU_DANCE: "Dance Revolution"}
# hachages des objets du jeu que l'objet AP donne (don « objet ») ; Miroirs : aucun objet du jeu
OBJETS_LOT7 = {VERROU_CAPSULES: 0x5C007505, VERROU_GRELOT: 0x142C27DB, VERROU_MONTRE_LUXE: 0xFA2246F7,
               VERROU_CEINTURE: 0x8E0B5F56, VERROU_ROBOT_NEUF: 0x99CBE625, VERROU_ROBOT_USE: 0xEECCD6B3,
               VERROU_SERVIETTE: 0xC28C4169, VERROU_DANCE: 0x7C6B19A6}
FLAG_MIROIRS = 0xF874059B    # flag 17 « miroirs en service »
# déclencheurs de QUÊTE refusés (table de quête de la carte) : zone 2 (clés à 4 champs, carte None) et zone 3
DECLENCHEURS2.update({(13, 2, 0x5C386C83, None): VERROU_CEINTURE, (39, 1, 0xA8E256A8, None): VERROU_ROBOT_NEUF})
DECLENCHEURS3 = {(13, 12, 0xF2A7EE35): VERROU_ROBOT_USE, (13, 3, 0x07A7F1E2): VERROU_SERVIETTE,
                 (13, 72, 0x44353410): VERROU_DANCE}
# déclencheurs de PHASE refusés (table cNN_trigger du chapitre) : (type, n, identifiant, chapitre) -> verrous
DECLENCHEURS_PHASE7 = {(73, 10, 0x2BB2A864, 9): (VERROU_CAPSULES,),
                       (73, 12, 0x457F7738, 5): (VERROU_GRELOT, VERROU_MONTRE_LUXE)}
VERROUS3_COMPILES_DEFAUT = 0x7       # 56, 57, 58
# DeathLink de la Terr'heure / de Blasters RÉSERVÉ aux graines qui le demandent : option étendue 26 de ApVerrous2,
# écrite par le client (avec les autres options étendues) pour une graine V3 dont le DeathLink est activé. Absente :
# le jeu ne publie rien pour une partie perdue du mode et ne tient pas la mort reçue pour satisfaite.
OPTION2_MORT_ORGE = 26
NOMS_OPTIONS2[OPTION2_MORT_ORGE] = "DeathLink à la Terr'heure et en Blasters"
MORT_ORGE_CHAMPS = MORT_ORGE_CHAMPS + ("sans_option",)      # +0x38 : parties perdues sans l'option
ORGE_ISSUES[8] = "perdue : la graine ne demande pas ces morts (option étendue 26 absente) : rien"

# --- V3, lot 9 (docs/systemes/archipelago_v3_objets_cles_apworld.md) : branchement côté client -------------------
# N° « client » de `fonctions_exigees` que le client de la V3 honore sans rien demander au jeu (jamais publiés par le
# jeu : un client d'avant refuse la graine). HORS de FONCTIONS_CLIENT_CONNUES (ceux de la V2 publiée) :
# 66 = victoire par les bits du Médaillium (`objectif_medailles`) et lecture du mot des terrains de Ψ Blasters (lot 3) ;
# 67 = option étendue 25 (requêtes à transfert de sauvegarde) écrite quand la graine exige la fonction 37 (lot 6 ;
#      défini jusque-là dans synchro.py) ;
# 68 = verrous de la zone ApVerrous3 (k >= 56) lus et écrits (N_CLIENT_VERROUS3, lot 9).
FONCTION_CLIENT_5 = 66
FONCTION_CLIENT_6 = 67
FONCTION_CLIENT_7 = N_CLIENT_VERROUS3
# 69 = mélange des boss de VERSION 2, permutation portée par la graine (lot 10 ; défini jusque-là dans synchro.py)
FONCTION_CLIENT_8 = 69
FONCTIONS_CLIENT_V3 = frozenset({FONCTION_CLIENT_5, FONCTION_CLIENT_6, FONCTION_CLIENT_7, FONCTION_CLIENT_8})
# N° de « verrou manquant » d'une OPTION étendue dont des locations dépendent et que le jeu ne compile pas (100 + bit) :
# 125 = option 25 (requêtes à transfert). L'option 26 (DeathLink du mode) n'en a pas : absente, on avertit seulement.
OPTION2_MANQUANTE_BASE = 100
NOMS_VERROUS.update({
    37: "Requêtes à transfert de sauvegarde (fonction 37)",
    43: "Clé terrifiante", 44: "Clé sanglier", 45: "Clé cerf", 46: "Clé papillon", 47: "Pass sortilège",
    VERROU_LETTRE: "Lettre de Komasan", VERROU_BILLE: "Bille mystérieuse", **NOMS_VERROUS_LOT7,
    FONCTION_CLIENT_5: "Objectif d'après-jeu / Blasters (client trop ancien)",
    FONCTION_CLIENT_6: "Requêtes à transfert de sauvegarde (client trop ancien)",
    FONCTION_CLIENT_7: "Verrous de la deuxième zone étendue (client trop ancien)",
    FONCTION_CLIENT_8: "Mélange des boss tiré à la génération (client trop ancien)",
    OPTION2_MANQUANTE_BASE + OPTION2_TRANSFERT: "Requêtes à transfert de sauvegarde (option 25)"})


def verrou3_compile(compiles: int | None, k: int) -> bool:
    """Le verrou k (56..87) est-il compilé dans le jeu ? (`compiles` : verrous3_compiles, None = zone non publiée)"""
    return compiles is not None and VERROU3_BASE <= k < VERROU3_BASE + CAP_VERROUS3 \
        and bool(compiles >> (k - VERROU3_BASE) & 1)


def options2_mort_orge(deathlink_orge: bool) -> int:
    """Bit d'option étendue à poser dans ApVerrous2::actifs pour une graine V3 à DeathLink (en plus des autres)."""
    return (1 << OPTION2_MORT_ORGE) if deathlink_orge else 0


def mort_orge_choisie(b: bytes, ident_client: int = 0) -> bool:
    """Modèle de apOption2Choisie(26) : compilée, choisie, zone valide (sans la condition « sauvegarde liée »)."""
    return option2_active(b, OPTION2_MORT_ORGE, ident_client)


def miroirs_vus(b: bytes, brut: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de la branche « miroirs » de apVerrouFiltreFlag : flag 17 lu faux tant que le verrou s'applique ; jamais
    rendu vrai (le flag natif reste exigé)."""
    return brut and not (liee and verrou2_actif(b, VERROU_MIROIRS, ident_client))


def declencheur3_refuse(b3: bytes, type_: int, n: int, ident: int, table_de_quete: bool, liee: bool,
                        ident_client: int = 0) -> int | None:
    """Branches de apVerrouDeclencheur pour les verrous de la zone 3 : verrou k qui fait ignorer l'entrée, ou None."""
    k = DECLENCHEURS3.get((type_, n, ident))
    return k if k is not None and table_de_quete and liee and verrou3_actif(b3, k, ident_client) else None


def declencheur_phase7_refuse(b2: bytes, type_: int, n: int, ident: int, chapitre: int, table_de_phase: bool,
                              liee: bool, ident_client: int = 0) -> int | None:
    """Branches « phase » du lot 7 de apVerrouDeclencheur (Capsules de lait ; Grelot félin / Montre de luxe) : premier
    verrou en vigueur et non reçu qui fait ignorer l'entrée, ou None."""
    if not (table_de_phase and liee):
        return None
    for k in DECLENCHEURS_PHASE7.get((type_, n, ident, chapitre), ()):
        if verrou2_actif(b2, k, ident_client):
            return k
    return None

# --- V3, lot 8 (docs/systemes/archipelago_v3_train_temps.md ; boîte §40) ---
# Train ordinaire (k = 59) et voyage dans le temps (k = 60) : deux objets AP sans objet du jeu, zone ApVerrous3.
# Verrous par refus de déclencheurs de la table de CARTE, la carte du joueur dans la clé.
VERROU_TRAIN = 59            # portillons des trois gares de Granval fermés (Ourcival et San Fantastico jamais touchées)
VERROU_TEMPS = 60            # quatre passages ALLER du PNJ du temps refusés (les retours jamais)
NOMS_VERROUS_LOT8 = {VERROU_TRAIN: "Abonnement de train", VERROU_TEMPS: "Voyage dans le temps"}
NOMS_VERROUS.update(NOMS_VERROUS_LOT8)       # note N2 de la revue du lot 9
VERROUS3_COMPILES_DEFAUT = 0x1F      # 56..58 (lot 7), 59, 60
CARTE_T104I61, CARTE_T103G00, CARTE_T107G00 = 0x0BC149DE, 0xBDD5CB7D, 0x32B75C2A     # gares de Granval
CARTE_T121G00, CARTE_T132G00 = 0x6D1C5096, 0x42C9D6C8                               # San Fantastico, gare d'Ourcival
CARTE_T101G00, CARTE_T102G00, CARTE_T201G00 = 0x17DC03F6, 0x0569AC18, 0x91487158
CARTE_T202G00, CARTE_T232G00, CARTE_T301G00 = 0x83FDDEB6, 0xC45DA466, 0x5A14A2FD
# Portillons : carte -> {(type, identifiant) : n° de l'entrée a « gare fermée de 0 h à 6 h », jamais refusée} ; les
# autres entrées du même (type, identifiant) sont b (Pass illimité), c (distributeur) et e (Pass journalier).
PORTILLONS = {
    CARTE_T104I61: {(39, i): 1 + 5 * r for r, i in enumerate((0x2EB8F411, 0xB7B1A5AB, 0xC0B6953D, 0x5ED2009E,
                                                             0x29D53008, 0xB0DC61B2, 0xC7DB5124, 0x57644CB5))},
    CARTE_T103G00: {(23, 0x541B5FEA): 32},
    CARTE_T107G00: {(23, 0xC7A27904): 1},
}
PORTILLONS_SUITES = ((81, 0x48B7B0A2), (50, 0xB1754038))     # après l'achat, choix « prendre le train » : sans n°
# portillons des gares extérieures (mêmes entrées, jamais dans la clé) : pour les tests
PORTILLONS_LIBRES = {CARTE_T121G00: (23, 0x38A99D20), CARTE_T132G00: (23, 0x95CC524C)}
# Passages du temps (type 13) : (carte, n°, identifiant). ALLERS refusés ; RETOURS jamais.
PASSAGES_TEMPS_ALLER = ((CARTE_T132G00, 12, 0x320A59B0), (CARTE_T101G00, 79, 0xE18BFE20),
                        (CARTE_T102G00, 57, 0xF33E51CE), (CARTE_T201G00, 15, 0x2AD72D85),
                        (CARTE_T201G00, 16, 0x2AD72D85))
PASSAGES_TEMPS_RETOUR = ((CARTE_T232G00, 5, 0xB49E2B1E), (CARTE_T201G00, 13, 0x671F8C8E),
                         (CARTE_T202G00, 2, 0x75AA2360), (CARTE_T301G00, 3, 0xE18BFE20))
CHAPITRE_SIEGE = 10          # le passage de t101g00 n'est jamais refusé pendant le chapitre 10 (Granval présent fermé)
PHASE_TOUR_OUVERTE = 60040   # 6-40 : avant, le portillon de t107g00 n'est jamais refusé (aucune sortie à pied)
FLAG_PASSAGE_TEMPS = 264     # « ev05_1100 vu » (0x48F43538) : rencontre du PNJ du passage en 5-90 = emplacement d'origine
# fenêtre « portillon / passage fermé » : ApVerrous3 +0xE0 (états du jeu), faux labels de la commande 0x35C0
VERROUS3_MSG = {"msg_terrain": 0xE0, "msg_attente": 0xE4, "msg_images": 0xE5, "msg_montres": 0xE6, "msg_textes": 0xE7,
                "msg_age": 0xE8}
TRAIN_TEXTE_HASH, TEMPS_TEXTE_HASH = 0xF3EE41E7, 0x0740D857
PASSAGE_IMAGES_MAX = 600
TEXTES_PASSAGE = {
    (VERROU_TRAIN, 0): "Le portillon reste fermé.\nObjet AP requis : Abonnement de train",
    (VERROU_TRAIN, 1): "The ticket gate stays shut.\nArchipelago item needed: Train Pass",
    (VERROU_TEMPS, 0): "Le passage reste fermé.\nObjet AP requis : Voyage dans le temps",
    (VERROU_TEMPS, 1): "The way through time stays shut.\nArchipelago item needed: Time Travel",
}


def passage_cle(type_: int, n: int, ident: int, carte: int) -> int | None:
    """Clé de apVerrouPassage : verrou (59 / 60) dont l'entrée (type, n°, identifiant) de la table de carte de
    `carte` dépend, ou None (entrée jamais refusée)."""
    if type_ == 13:
        return VERROU_TEMPS if (carte, n, ident) in PASSAGES_TEMPS_ALLER else None
    if carte not in PORTILLONS:
        return None
    if (type_, ident) in PORTILLONS_SUITES:
        return VERROU_TRAIN
    a = PORTILLONS[carte].get((type_, ident))
    return VERROU_TRAIN if a is not None and n != a else None


def passage_refuse(b3: bytes, type_: int, n: int, ident: int, carte: int, phase: int, table_de_carte: bool,
                   liee: bool, ident_client: int = 0) -> tuple[int | None, bool]:
    """Modèle de apVerrouPassage : (verrou qui fait ignorer l'entrée ou None, exempté). `phase` = GetPhase
    (chapitre * 10000 + phase). Exempté (verrou en vigueur, objet non reçu, entrée laissée au jeu) : le portillon de
    t107g00 avant 6-40 ; le passage de t101g00 pendant le chapitre 10."""
    k = passage_cle(type_, n, ident, carte)
    if k is None or not (table_de_carte and liee and verrou3_actif(b3, k, ident_client)):
        return None, False
    if k == VERROU_TRAIN and carte == CARTE_T107G00 and phase < PHASE_TOUR_OUVERTE:
        return None, True
    if k == VERROU_TEMPS and carte == CARTE_T101G00 and phase // 10000 == CHAPITRE_SIEGE:
        return None, True
    return k, False


def texte_passage(k: int, langue: int) -> bytes:
    """Texte de la fenêtre (apPassageTexteLabel) : langue des notifications (1 = anglais, sinon français)."""
    return TEXTES_PASSAGE[(k, 1 if langue == 1 else 0)].encode("utf-8")


# --- V3, lot 12 (docs/systemes/archipelago_v3_invites_medaillium.md, archipelago_boite.md §41) : invités de l'Auberge,
# extension V3 (zone ApInvites2, invites.cpp). ApInvites (format de la V2) est inchangée : une liste de 32 entrées au
# plus s'écrit par `ecritures_invites`, exactement comme avant.
#  - fonction étendue 38 : liste à 64 entrées (rangs 32..63 dans ApInvites2) et taux d'amitié relevé par invité (bits
#    4..7 de ApInvite::drapeaux = ligne plafond de CHARA_FRIEND_RATE_INFO) ; exigée avec le n° « client » 70 ;
#  - option étendue 27 + fonction étendue 39 : amitié assurée pendant les combats dont la rencontre de script est dans
#    `uniques` (écrits par le client, valables pour `uniques_ident` = identifiant de partie du client).
OFF_INVITES2, TAILLE_INVITES2, CAP_INVITES_V3 = 0x23400, 0x200, 64
INVITES2_PUBLIE = 0x32495041                               # « API2 »
INVITES2_CAP64, INVITES2_TAUX, INVITES2_UNIQUES = 0x01, 0x02, 0x04
OFF_INVITES2_LISTE, OFF_INVITES2_UNIQUES, CAP_UNIQUES = 0x100, 0x40, 24
INVITE_TAUX_DECALAGE, INVITE_TAUX_MAX = 4, 8
FONCTION_INVITES_V3 = 38
OPTION2_AMITIE_UNIQUES = 27
FONCTION_AMITIE_UNIQUES = 39
FONCTION_CLIENT_9 = 70                                     # client qui sait écrire ApInvites2 (jamais publié par le jeu)
# 70 est dans FONCTIONS_CLIENT_V3 depuis le lot 14 : le client écrit ApInvites2 (`ecritures_invites_v3`, appelée par
# `ZoneConnexion.ecrire_invites`) et refuse la partie si le patch ne publie pas la liste à 64 ou le taux par invité.
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_9}
NOMS_OPTIONS2[OPTION2_AMITIE_UNIQUES] = "Amitié assurée des combats uniques"
NOMS_VERROUS.update({
    FONCTION_INVITES_V3: "Invités de l'Auberge : liste à 64 et taux d'amitié relevé (fonction 38)",
    FONCTION_AMITIE_UNIQUES: "Amitié assurée des combats uniques (fonction 39)",
    FONCTION_CLIENT_9: "Invités de l'Auberge de la V3 (client trop ancien)"})
INVITES2_CHAMPS = ("publie", "compile", "ident", "sequence", "forcer", "annoncees", "fen_masque", "taux_param",
                   "taux_origine", "taux_ecrit", "taux_ecritures", "taux_remises", "uniques_ident", "uniques_nombre",
                   "unique_combat", "uniques_lus")       # u32 à partir de +0x00
# Lignes de CHARA_FRIEND_RATE_INFO [C, ROM européenne : archipelago_rando_yokai.md §15.2] : n° de ligne -> clé (chance
# par combat sans aliment = 1 / clé). Ligne 0 : clé nulle (jamais ami).
CLES_TAUX = {1: 8, 2: 16, 3: 32, 4: 64, 5: 128, 6: 256, 7: 512, 8: 1024}
LIGNE_TAUX_5_ETOILES = 5                                   # proposé pour les 16 invités de Pièce 5 étoiles : clé 128


def options2_amitie_uniques(active: bool) -> int:
    """Bit de l'option étendue 27 à poser dans ApVerrous2::actifs."""
    return (1 << OPTION2_AMITIE_UNIQUES) if active else 0


def drapeaux_invite(drapeaux: int, ligne: int = 0) -> int:
    """Drapeaux d'un invité avec sa ligne de taux plafond (0 : taux d'origine, ce qu'écrit un client de la V2)."""
    if not 0 <= ligne <= INVITE_TAUX_MAX:
        raise ValueError("ligne de taux hors de 0..8")
    return (drapeaux & 0x0F) | ligne << INVITE_TAUX_DECALAGE


def ligne_invite(drapeaux: int) -> int:
    """Ligne plafond lue par le jeu dans les drapeaux d'un invité (hors de 1..8 : aucune)."""
    ligne = drapeaux >> INVITE_TAUX_DECALAGE & 0xF
    return ligne if ligne <= INVITE_TAUX_MAX else 0


def quartets_releves(mot: int, ligne: int) -> int:
    """Modèle de taux() (invites.cpp) : mot des quartets de ligne de taux (CHARA_PARAM +0x20) avec la ligne plafond :
    quartet' = min(quartet, ligne) pour les 6 quartets ; un quartet nul reste nul ; l'octet haut est gardé."""
    if not ligne:
        return mot
    out = mot & 0xFF000000
    for k in range(6):
        out |= min(mot >> 4 * k & 0xF, ligne) << 4 * k
    return out


def dec_invites2(b: bytes) -> dict:
    """ApInvites2 (0x200 octets à OFF_INVITES2)."""
    d = dict(zip(INVITES2_CHAMPS, struct.unpack_from("<16I", b, 0)))
    d["uniques"] = list(struct.unpack_from("<%dI" % CAP_UNIQUES, b, OFF_INVITES2_UNIQUES))[:min(d["uniques_nombre"],
                                                                                              CAP_UNIQUES)]
    d["uniques_combats"], = struct.unpack_from("<I", b, 0xA0)
    d["uniques_refus"], d["uniques_refuse"] = struct.unpack_from("<II", b, 0xB4)   # lot 15 (0 dans un jeu d'avant)
    d["taux_ligne"], d["taux_refus"] = b[0xA4], b[0xA5]
    d["liste"] = [dec_invite(b[OFF_INVITES2_LISTE + i * TAILLE_INVITE:]) for i in range(CAP_INVITES_V3 - CAP_INVITES)]
    return d


def invites2_compiles(b: bytes) -> int | None:
    """Bits INVITES2_* compilés (début de ApInvites2), None si la zone n'est pas publiée (jeu d'avant le lot 12)."""
    publie, compile_ = struct.unpack_from("<II", b, 0)
    return compile_ if publie == INVITES2_PUBLIE else None


def ecritures_invites_v3(invites: list[tuple], ident: int, sequence: int,
                         compile2: int | None = None) -> list[tuple[int, bytes]]:
    """Écritures (adresse, octets) d'une liste d'invités de 64 entrées au plus. 32 entrées au plus : exactement celles
    d'`ecritures_invites` (rien n'est écrit dans ApInvites2). Au-delà : d'abord la suite de la liste dans ApInvites2
    (`liste`, puis `ident` et `sequence`), puis ApInvites comme avant (`sequence` EN DERNIER), `nombre` = total.
    `compile2` (bits INVITES2_* lus dans le jeu) : fourni, une liste de plus de 32 entrées est refusée sans
    INVITES2_CAP64. `invites` = [(CHARA_PARAM, n° du Médaillium, drapeaux[, chambre])], drapeaux par `drapeaux_invite`."""
    if len(invites) <= CAP_INVITES:
        return ecritures_invites(invites, ident, sequence)
    if len(invites) > CAP_INVITES_V3:
        raise ValueError("trop d'invités")
    if compile2 is not None and not compile2 & INVITES2_CAP64:
        raise ValueError("liste de plus de 32 invités : le jeu ne publie pas la liste à 64")
    suite = b"".join(enc_invite(*x) for x in invites[CAP_INVITES:]).ljust(
        (CAP_INVITES_V3 - CAP_INVITES) * TAILLE_INVITE, b"\0")
    liste = b"".join(enc_invite(*x) for x in invites[:CAP_INVITES])
    base, base2 = ZONE + OFF_INVITES, ZONE + OFF_INVITES2
    return [(base2 + OFF_INVITES2_LISTE, suite),
            (base2 + 8, struct.pack("<II", ident & 0xFFFFFFFF, sequence & 0xFFFFFFFF)),
            (base + OFF_INVITES_LISTE, liste),
            (base + 8, struct.pack("<II", ident & 0xFFFFFFFF, len(invites))),
            (base + 4, struct.pack("<I", sequence & 0xFFFFFFFF))]


def liste_invites_v3(zone: bytes, zone2: bytes | None) -> list[dict] | None:
    """Modèle de listeValide (invites.cpp), partie « liste » : entrées de la liste (dictionnaires de `dec_invite` + la
    clé "force"), None si elle n'est pas valide. Plus de 32 entrées : la suite doit être celle de cette liste
    (ApInvites2 publiée avec INVITES2_CAP64, `ident` égal, `sequence` non nulle)."""
    d = dec_invites(zone)
    n = d["nombre"]
    c2 = invites2_compiles(zone2) if zone2 is not None else None
    cap = CAP_INVITES_V3 if c2 is not None and c2 & INVITES2_CAP64 else CAP_INVITES
    if d["sequence"] == 0 or not 0 < n <= cap:
        return None
    liste = [dict(e, force=bool(d["forcer"] >> i & 1)) for i, e in enumerate(d["liste"])]
    if n > CAP_INVITES:
        d2 = dec_invites2(zone2)
        if d2["sequence"] == 0 or d2["ident"] != d["ident"]:
            return None
        liste = [dict(dec_invite(zone[OFF_INVITES_LISTE + i * TAILLE_INVITE:]), force=bool(d["forcer"] >> i & 1))
                 for i in range(CAP_INVITES)]
        liste += [dict(e, force=bool(d2["forcer"] >> i & 1)) for i, e in enumerate(d2["liste"][:n - CAP_INVITES])]
    return liste


def affectation_gardee_v3(liste: list[tuple], amis: set[int], occupees: int = 0,
                           garde: list[int] | None = None) -> tuple[list[int], int, list[int]]:
    """`affectation_gardee` pour une liste de 64 entrées au plus (même règle, même résultat pour 32 entrées au plus :
    vérifié par le selftest)."""
    t = [0] * INVITES_PIECES
    candidats, chambres, tient = set(), [], set()
    des_amis = False
    for i, e in enumerate(liste[:CAP_INVITES_V3]):
        param, medaille, declare = e[0], e[1], e[2]
        if not param or not 0 < medaille < 512 or not declare:
            continue
        if medaille in amis:
            des_amis = True
            continue
        candidats.add(i)
        if param == INVITES_PARAM_PNJ:
            if not t[0]:
                t[0] = i + 1
            continue
        chambres.append(i)
        c = e[3] if len(e) > 3 else 0
        if 1 <= c < INVITES_PIECES and not t[c]:
            t[c] = i + 1
            tient.add(i)
    for p in range(1, INVITES_PIECES):
        g = garde[p] if garde else 0
        if not t[p] and g and g - 1 in chambres and g - 1 not in tient:
            t[p] = g
            tient.add(g - 1)
    p = 1
    for i in chambres:
        if i in tient:
            continue
        while p < INVITES_PIECES and (t[p] or occupees >> p & 1):
            p += 1
        if p >= INVITES_PIECES:
            break
        t[p] = i + 1
        tient.add(i)
    loges = [0 if occupees >> q & 1 else g for q, g in enumerate(t)]
    motif = INVITES_MOTIF_AUCUN if any(loges) else INVITES_MOTIF_PIECES if candidats \
        else INVITES_MOTIF_TOUS_AMIS if des_amis else INVITES_MOTIF_NON_DECLARE
    return loges, motif, t


def invites_zone_v3(zone: bytes, zone2: bytes | None, ident_sauvegarde: int, amis: set[int] | None, liee: bool = True,
                    occupees: int = 0) -> tuple[list[int], int]:
    """`affecter` (règle « Suite réservée, chambres gardées ») sur les zones ApInvites + ApInvites2 lues."""
    d = dec_invites(zone)
    liste = liste_invites_v3(zone, zone2)
    if liste is None:
        return [0] * INVITES_PIECES, INVITES_MOTIF_LISTE
    if amis is None or d["ident"] == 0 or d["ident"] != ident_sauvegarde or not liee:
        return [0] * INVITES_PIECES, INVITES_MOTIF_PARTIE
    entrees = [(e["param"], e["medaille"], bool(e["drapeaux"] & INVITE_DECLARE or e["force"]), e["chambre"])
               for e in liste]
    garde = d["garde"] if d["garde_ident"] == d["ident"] else None
    return affectation_gardee_v3(entrees, amis, occupees, garde)[:2]


def ecritures_uniques(rencontres: list[int], ident_partie: int) -> list[tuple[int, bytes]]:
    """Écritures (adresse, octets) de la liste des rencontres de script à amitié assurée (option étendue 27) : la
    liste, `uniques_ident`, puis `uniques_nombre` EN DERNIER. Liste vide : nombre 0 (rien d'assuré)."""
    if len(rencontres) > CAP_UNIQUES:
        raise ValueError("trop de combats uniques")
    base2 = ZONE + OFF_INVITES2
    table = b"".join(struct.pack("<I", r & 0xFFFFFFFF) for r in rencontres).ljust(CAP_UNIQUES * 4, b"\0")
    return [(base2 + 0x34, struct.pack("<I", 0)),
            (base2 + OFF_INVITES2_UNIQUES, table),
            (base2 + 0x30, struct.pack("<I", ident_partie & 0xFFFFFFFF)),
            (base2 + 0x34, struct.pack("<I", len(rencontres)))]


def unique_reconnu(zone2: bytes, verrous2: bytes, rencontre: int, liee: bool, ident_client: int) -> bool:
    """Modèle de uniqueDebut (invites.cpp) : le combat qui commence avec cette rencontre de script est-il un combat
    unique à amitié assurée ? (option 27 compilée, choisie, zone valide, sauvegarde liée ; liste du client valable pour
    cette partie ; rencontre dans la liste.)"""
    c2 = invites2_compiles(zone2)
    if not rencontre or c2 is None or not c2 & INVITES2_UNIQUES or not liee \
            or not option2_active(verrous2, OPTION2_AMITIE_UNIQUES, ident_client):
        return False
    d = dec_invites2(zone2)
    if not 0 < d["uniques_nombre"] <= CAP_UNIQUES or not d["uniques_ident"] or d["uniques_ident"] != ident_client:
        return False
    if c2 & INVITES2_SANS_REJOUABLES and rencontre in RENCONTRES_REJOUABLES:
        return False                    # lot 15 : jamais d'amitié assurée pour un combat rejouable à volonté
    return rencontre in d["uniques"]


# Don assuré des trois Oni amis de la Voie du mystère (option étendue 28, fonction étendue 40 ; verrous.cpp,
# FUN_00448988) : rencontre de l'Oni « du jour » -> (n° de l'entrée de type 78 « aucun exemplaire possédé » dans la
# table de déclencheurs de la carte, n° du Médaillium de l'Oni donné) [C : t131d03c / t201d01c / t121d31_trigger].
OPTION2_DON_ONI = 28
FONCTION_DON_ONI = 40
ONI_ESSAIS = 1024
ONI_TYPE_VICTOIRE = 78
DONS_ONI = {0xFD6B12B7: (7, 438), 0xEFDEBD59: (6, 439), 0x4E79EB7D: (6, 440)}
INVITES2_ONI = {"oni_reprises": 0xA8, "oni_dons": 0xAC, "oni_dernier": 0xB0}   # ApInvites2, jeu seulement
NOMS_OPTIONS2[OPTION2_DON_ONI] = "Don assuré des Oni de la Voie du mystère"
# (revue du lot 13 : NOMS_VERROUS est indexé par n° de VERROU ; l'écriture NOMS_VERROUS[40] du lot 12 écrasait le nom
# du verrou 40 « Yo-kai Watch » : retirée, le nom de la fonction 40 est dans NOMS_FONCTIONS_LOT12)
NOMS_FONCTIONS_LOT12 = {FONCTION_DON_ONI: "Don assuré des Oni de la Voie du mystère (fonction 40)"}


def options2_don_oni(active: bool) -> int:
    """Bit de l'option étendue 28 à poser dans ApVerrous2::actifs."""
    return (1 << OPTION2_DON_ONI) if active else 0


def don_oni_vise(verrous2: bytes, type_: int, n: int, ident: int, table_de_carte: bool, liee: bool, amis: set[int],
                 ident_client: int = 0) -> bool:
    """Modèle de apOniDonVise (verrous.cpp) : l'entrée (type, n°, identifiant) dont la condition vient d'être fausse
    est-elle réévaluée ? (entrée du don « aucun possédé » d'un Oni, table de la carte, option 28 en vigueur, sauvegarde
    liée, Oni pas encore ami.)"""
    if type_ != ONI_TYPE_VICTOIRE or ident not in DONS_ONI or DONS_ONI[ident][0] != n:
        return False
    return table_de_carte and liee and option2_active(verrous2, OPTION2_DON_ONI, ident_client) \
        and DONS_ONI[ident][1] not in amis


def don_oni_reprise(clauses_fixes: bool, tirages) -> bool:
    """Modèle de apOniReprise : la condition est réévaluée au plus ONI_ESSAIS fois ; `clauses_fixes` = ses clauses sans
    hasard (pas déjà possédé, place libre), `tirages` = itérable des résultats successifs de Random."""
    if not clauses_fixes:
        return False
    for i, t in enumerate(tirages):
        if i >= ONI_ESSAIS:
            break
        if t:
            return True
    return False


# --- V3, lot 13 : Voie du mystère et limites du jour de l'après-jeu (voie.cpp ; docs/systemes/
# archipelago_v3_voie_tirages.md, archipelago_boite.md §42). Le client n'écrit que deux bits de ApVerrous2::actifs :
#  - option étendue 29 « limites d'un par jour réel levées » : boss de la Voie du mystère « un par parcours »
#    (fonction étendue 41) et revanches d'Âmiral, de Ressak et de Jibakoma sans « reviens demain » (fonction 43) ;
#  - option étendue 30 « tirage dirigé des quatre machines de la Voie du mystère » (fonction étendue 42).
# ApTirages (0x40 octets, jeu seulement) : ce que le build contient, état « boss rejouable », compteurs.
OPTION2_LIMITES_JOUR = 29
OPTION2_TIRAGE_DIRIGE = 30
FONCTION_BOSS_VOIE = 41
FONCTION_TIRAGE_DIRIGE = 42
FONCTION_COMBATS_REQUETES = 43
OFF_TIRAGES, TAILLE_TIRAGES = 0x23600, 0x40
TIRAGES_PUBLIE = 0x31545041            # « APT1 »
TIRAGES_BOSS_VOIE, TIRAGES_REQUETES, TIRAGES_DIRIGE = 0x01, 0x02, 0x04
TIRAGES_CHAMPS = {"publie": 0x00, "compile": 0x04, "voie_carte": 0x0C, "voie_entrees": 0x10, "voie_victoires": 0x14,
                  "voie_rendus": 0x18, "voie_annules": 0x1C, "requetes_rendus": 0x20, "tirages": 0x24,
                  "tirages_diriges": 0x28, "tirage_table": 0x2C, "tirage_lot": 0x30, "tirage_refus": 0x34}
TIRAGES_OFF_REJOUABLES = 0x08
TIRAGE_REFUS = {0: "dirigé (ou aucun tirage vu)", 1: "rien ne manque dans cette table", 2: "table ou lot inattendu",
                3: "somme des poids inattendue", 4: "option 30 pas en vigueur"}
# bits « boss vaincu aujourd'hui » 2524..2527 (rang 0..3), flags de ligne, « reviens demain » des trois revanches
FLAGS_BOSS_VOIE = (0x5510BEB5, 0xCC19EF0F, 0xBB1EDF99, 0x257A4A3A)
FLAGS_LIGNE_VOIE = (0x5D97C8B7, 0x92F2439B, 0x5E91324B)
FLAGS_REVANCHES_JOUR = {0x298C46BA: 2515, 0x3070CFD6: 2558, 0xFDA78697: 2540}   # Âmiral, Ressak, Jibakoma
CARTE_T121I10 = 0x7E994CDD
TIRAGE_RETOUR = 0x0040C000
# Yo-kai visés par le tirage dirigé, dans l'ordre de priorité : (table, lot, CHARA_PARAM, n° du Médaillium)
CIBLES_TIRAGE = (
    (0x15B35EA5, 0x780CFE00, 0x727F566E, 79), (0x15B35EA5, 0xFA5C69D1, 0xF02FC1BF, 281),
    (0x62B46E33, 0x0D9AE652, 0x07E94E3C, 332), (0x54294050, 0x42DB7095, 0x48A8D8FB, 333),
    (0x232E70C6, 0x1481D713, 0x1EF27F7D, 331), (0x232E70C6, 0x3FAC84D0, 0x35DF2CBE, 330),
    (0x232E70C6, 0x26B7B591, 0x2CC41DFF, 334),
    (0x15B35EA5, 0x2D192B3E, 0x276A8350, 118), (0x62B46E33, 0xB03A7329, 0xBA49DB47, 283),
    (0x54294050, 0xFE988CAE, 0xF4EB24C0, 122))
TABLES_TIRAGE = (0x15B35EA5, 0x62B46E33, 0x54294050, 0x232E70C6)   # gacha_double_01 .. 04
NOMS_OPTIONS2[OPTION2_LIMITES_JOUR] = "Limites d'un par jour de l'après-jeu levées (boss de la Voie du mystère, revanches)"
NOMS_OPTIONS2[OPTION2_TIRAGE_DIRIGE] = "Tirage dirigé des machines de la Voie du mystère"
# Noms des fonctions étendues de ce lot, à part : NOMS_VERROUS est indexé par n° de VERROU, et 41 à 43 y sont déjà
# les Documents perdus, les Cartes d'Ultramax et la Clé terrifiante (les n° de fonction étendue 32.. et les n° de verrou
# étendu 40.. se recouvrent ; l'entrée 40 a été écrasée par le lot 12 : à régler par le lot APWorld).
NOMS_FONCTIONS_LOT13 = {FONCTION_BOSS_VOIE: "Boss de la Voie du mystère : un par parcours (fonction 41)",
                        FONCTION_TIRAGE_DIRIGE: "Tirage dirigé des machines de la Voie du mystère (fonction 42)",
                        FONCTION_COMBATS_REQUETES: "Revanches d'après-jeu sans « reviens demain » (fonction 43)"}


def options2_limites_jour(active: bool) -> int:
    """Bit de l'option étendue 29 à poser dans ApVerrous2::actifs."""
    return (1 << OPTION2_LIMITES_JOUR) if active else 0


def options2_tirage_dirige(active: bool) -> int:
    """Bit de l'option étendue 30 à poser dans ApVerrous2::actifs."""
    return (1 << OPTION2_TIRAGE_DIRIGE) if active else 0


def tirages_compiles(b: bytes) -> int | None:
    """Bits TIRAGES_* compilés (début de ApTirages), None si la zone n'est pas publiée (jeu d'avant le lot 13)."""
    publie, compile_ = struct.unpack_from("<II", bytes(b).ljust(8, b"\0"), 0)
    return compile_ if publie == TIRAGES_PUBLIE else None


def dec_tirages(b: bytes) -> dict:
    """ApTirages (0x40 octets à OFF_TIRAGES)."""
    b = bytes(b).ljust(TAILLE_TIRAGES, b"\0")
    d = {n: struct.unpack_from("<I", b, o)[0] for n, o in TIRAGES_CHAMPS.items()}
    d["voie_rejouables"] = b[TIRAGES_OFF_REJOUABLES]
    return d


def voie_ecriture(rejouables: int, flag: int, valeur: bool) -> int:
    """Modèle de apVoieEcriture : nouvel état « rejouable » (4 bits) après l'écriture d'un flag global par le jeu."""
    if flag in FLAGS_LIGNE_VOIE:
        return 0x0F
    if flag in FLAGS_BOSS_VOIE and valeur:
        return rejouables & ~(1 << FLAGS_BOSS_VOIE.index(flag))
    return rejouables


def voie_image(rejouables: int, carte_vue: int, partie: bool, carte: int) -> tuple[int, int]:
    """Modèle de apVoieImage : (rejouables, carte_vue) après une image."""
    if not partie:
        return 0, 0
    if not carte or carte == carte_vue:
        return rejouables, carte_vue
    return (0x0F if carte == CARTE_T121I10 else rejouables), carte


def jour_lu(tirages: bytes, verrous2: bytes, flag: int, brut: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de apJourFiltreFlag (derrière FUN_00412F08) : valeur vue par le jeu pour un bit de boss de la Voie ou un
    « reviens demain » de revanche. Rien de compilé, option 29 pas en vigueur, flag hors liste : valeur du jeu."""
    c = tirages_compiles(tirages)
    if not brut or c is None or not liee or not option2_active(verrous2, OPTION2_LIMITES_JOUR, ident_client):
        return brut
    if flag in FLAGS_BOSS_VOIE and c & TIRAGES_BOSS_VOIE:
        return not dec_tirages(tirages)["voie_rejouables"] >> FLAGS_BOSS_VOIE.index(flag) & 1
    if flag in FLAGS_REVANCHES_JOUR and c & TIRAGES_REQUETES:
        return False
    return brut


# --- V3, lot 15 : revanches sans limite de jour (voie.cpp, invites.cpp ; docs/systemes/archipelago_v3_revanches.md,
# archipelago_boite.md §43). Décision de l'humain (2026-10-12) : les combats de requêtes d'après-jeu qu'on peut refaire
# n'ont PAS d'amitié assurée ; ils se refont sans « reviens demain ».
#  - fonction étendue 44, sous la MÊME option étendue 29 : bits « reviens demain » des revanches de Donchan (requête
#    41), Triptyk (108), Carpitaine (113), Octorgone (111) et Kyubi (116) lus faux ; ApTirages::compile bit 0x08 ;
#  - ApInvites2::compile bit 0x08 : une rencontre REJOUABLE à volonté écrite dans `uniques` est ignorée par le jeu.
# Le client n'écrit rien de plus (le bit 29 de ApVerrous2::actifs, déjà celui du lot 13).
FONCTION_REVANCHES_REQUETES = 44
TIRAGES_REVANCHES = 0x08
TIRAGES_CHAMPS["revanches_rendus"] = 0x38
INVITES2_SANS_REJOUABLES = 0x08
# bit « reviens demain » -> (n° du bit, n° de la requête)
FLAGS_REVANCHES_REQUETES = {0xECAF7455: (2530, 41), 0xF0DD63C2: (2531, 108), 0x7E148B0B: (2532, 113),
                            0x901AEA27: (2533, 111), 0x0E7E7F84: (2534, 116)}
# Rencontres de script que le jeu relance tant que le Yo-kai n'est pas ami (requête laissée en phase 2, ou revanche
# d'une requête finie) : jamais d'amitié assurée (même liste, même ordre que k_rejouables d'invites.cpp).
RENCONTRES_REJOUABLES = (
    0x3086B34B, 0x22331CA5, 0x9A8F7BC0, 0x07584379, 0xBFE4241C,   # requêtes 91 à 95
    0xED5F4AD1, 0xEEECE7CB,                                       # requêtes 23 et 24
    0x22D201B8, 0xA3313B73, 0xADBF6720,                           # revanches des requêtes 73, 84, 120
    0x22DDF077, 0xC81677FA,                                       # requêtes 124 et 41
    0x8BC24D15, 0x61A3E3A4, 0xCBAA2B2F, 0x567D1396)               # requêtes 108, 113, 111, 116
NOMS_FONCTIONS_LOT15 = {
    FONCTION_REVANCHES_REQUETES: "Revanches de requêtes finies sans « reviens demain », suite (fonction 44)"}


def revanche_lue(tirages: bytes, verrous2: bytes, flag: int, brut: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de apJourFiltreFlag pour les cinq revanches de la fonction 44 : valeur vue par le jeu pour leur bit
    « reviens demain ». Fonction pas compilée, option 29 pas en vigueur, autre flag : valeur du jeu."""
    c = tirages_compiles(tirages)
    if not brut or c is None or not c & TIRAGES_REVANCHES or flag not in FLAGS_REVANCHES_REQUETES or not liee \
            or not option2_active(verrous2, OPTION2_LIMITES_JOUR, ident_client):
        return brut
    return False


def tirage_dirige_motif(table: int, lots: list[tuple], somme: int, amis: set[int], rang: int, en_vigueur: bool,
                         tire: int) -> tuple[int, int, int]:
    """Modèle de tirageDirige (voie.cpp) pour une des quatre tables : (valeur rendue au jeu par FUN_00674668 pour le
    tirage de lot, motif TIRAGE_REFUS, lot imposé ou 0). `lots` : (lot, poids, plafond, est_objet, contenu, rang_exige)
    dans l'ordre de la table ; `somme` : diviseur calculé par le jeu ; `tire` : valeur du jeu (état[3] % somme). Le jeu
    retient le lot dont l'intervalle ]cumul, cumul + poids] contient valeur + 1."""
    if not en_vigueur:
        return tire, 4, 0
    cumul, choix, valeur, impose, manque = 0, len(CIBLES_TIRAGE), tire, 0, False
    for lot, poids, plafond, est_objet, contenu, rang_exige in lots:
        if rang_exige > rang:
            continue
        for c, (t, l, param, medaille) in enumerate(CIBLES_TIRAGE[:choix]):
            if t != table or l != lot or medaille in amis:
                continue
            manque = True
            if est_objet or contenu != param or poids == 0 or plafond != 0:
                continue
            choix, valeur, impose = c, cumul, lot
        cumul += poids
    if cumul != somme:
        return tire, 3, 0
    if choix == len(CIBLES_TIRAGE):
        return tire, 2 if manque else 1, 0
    return valeur, 0, impose


def tirage_dirige(table: int, lots: list[tuple], somme: int, amis: set[int], rang: int, en_vigueur: bool,
                  tire: int) -> int:
    """Valeur rendue au jeu pour le tirage de lot (toute autre table que les quatre de la Voie : celle du jeu)."""
    if table not in TABLES_TIRAGE:
        return tire
    return tirage_dirige_motif(table, lots, somme, amis, rang, en_vigueur, tire)[0]


def lot_retenu(lots: list[tuple], rang: int, valeur: int) -> int:
    """Modèle de la boucle de choix de FUN_0040B81C (0x0040C028) : lot retenu pour la valeur rendue par FUN_00674668."""
    r, cumul = valeur + 1, 0
    for lot, poids, plafond, est_objet, contenu, rang_exige in lots:
        if rang_exige > rang:
            continue
        avant, cumul = cumul, cumul + poids
        if avant <= r <= cumul and poids:
            return lot
    return 0


# --- V3, lot 16 : chance d'amitié après un combat (amitie.cpp ; docs/systemes/archipelago_v3_option_amitie.md,
# archipelago_boite.md §43). Option GÉNÉRALE du joueur à quatre valeurs (`amitie` de slot_data, absente = normal) :
# aucune location n'en dépend, rien n'est écrit dans la sauvegarde. Zone ApAmitie (0x40 octets) : le jeu publie
# `publie` / `compile` ; le client écrit `ident` puis `reglage` EN DERNIER, quand ils changent (aucun paquet
# périodique). Fonction étendue 45 publiée par le jeu (44 : lot 15), JAMAIS exigée par une graine : un jeu sans la
# fonction garde le taux du jeu et le client avertit sans refuser la partie.
FONCTION_AMITIE = 45
OFF_AMITIE, TAILLE_AMITIE = 0x23700, 0x40
AMITIE_PUBLIE = 0x31415041              # « APA1 »
AMITIE_COMPILE = 0x01
AMITIE_COMPILE_NOURRI = 0x02            # « assurée » : le Yo-kai NOURRI est préféré (FUN_005574F8 récrite, 2026-10-21)
AMITIE_COMPILE_PAS_EU = 0x04            # ... puis un Yo-kai pas encore AMI (Médaillium) est préféré (2026-10-24)
AMITIE_NORMAL, AMITIE_X2, AMITIE_X4, AMITIE_ASSUREE = 0, 1, 2, 3
AMITIE_REGLAGES = {"normal": AMITIE_NORMAL, "x2": AMITIE_X2, "x4": AMITIE_X4, "assuree": AMITIE_ASSUREE}
AMITIE_NOMS = {AMITIE_NORMAL: "taux du jeu", AMITIE_X2: "chance x 2", AMITIE_X4: "chance x 4",
               AMITIE_ASSUREE: "amitié assurée"}
AMITIE_CHAMPS = {"publie": 0x00, "compile": 0x04, "ident": 0x08, "reglage": 0x0C, "tirages": 0x10, "changes": 0x14,
                 "assures": 0x18, "dernier_seuil": 0x1C, "dernier_borne": 0x20, "dernier_tire": 0x24,
                 "dernier_reglage": 0x28, "dernier_param": 0x2C, "choix": 0x30, "choix_nourris": 0x34,
                 "dernier_choix": 0x38, "choix_pas_eus": 0x3C}
OPTION_AMITIE_MANQUANTE = 200           # code de `options_absentes` du client (comme 100 + bit pour ApVerrous2)
NOMS_FONCTIONS_LOT16 = {FONCTION_AMITIE: "Chance d'amitié réglable (fonction 45)"}


def options2_amitie_oni(reglage: int) -> int:
    """fix/amitie-oni (bug vu en jeu 2026-11-06) : bit de l'option étendue 28 (don assuré des Oni de la Voie du
    mystère) que le client pose pour le réglage d'amitié `reglage`. Les trois Oni amis (Gargaros 438, Ogralos 439,
    Orqanos 440) ne passent JAMAIS par le tirage de fin de combat que règle ApAmitie (le combattant des combats « du
    jour » est un CHARA_PARAM de boss, v[31] = 0) : dans le jeu d'origine, ils sont donnés par un déclencheur de
    victoire à `Random(5)` / `Random(3)`. « Amitié assurée » retire donc aussi ce hasard ; les autres réglages
    laissent le taux du jeu (décision du 2026-10-13 : Oni au taux du jeu hors de ce réglage)."""
    return options2_don_oni(reglage == AMITIE_ASSUREE)


def reglage_amitie(valeur) -> int:
    """Réglage (0..3) d'une valeur de slot_data : nom (« x2 »…) ou entier ; toute valeur inconnue = normal (une
    graine d'un APWorld plus récent ne doit jamais donner PLUS que ce que ce client comprend)."""
    if isinstance(valeur, str):
        return AMITIE_REGLAGES.get(valeur, AMITIE_NORMAL)
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return AMITIE_NORMAL
    return valeur if AMITIE_NORMAL <= valeur <= AMITIE_ASSUREE else AMITIE_NORMAL


def amitie_compilee(b: bytes) -> bool:
    """Le jeu publie ApAmitie et la fonction y est compilée (8 premiers octets de la zone)."""
    publie, compile_ = struct.unpack_from("<II", bytes(b).ljust(8, b"\0"), 0)
    return publie == AMITIE_PUBLIE and bool(compile_ & AMITIE_COMPILE)


def ecritures_amitie(reglage: int, ident: int) -> list[tuple[int, bytes]]:
    """Écriture du client (offset dans la zone d'échange) : `ident` et `reglage`, contigus, en UN paquet de 8 octets
    (jeu arrêté ; `reglage` en dernier dans le paquet). `publie`, `compile` et les compteurs sont au jeu."""
    assert AMITIE_NORMAL <= reglage <= AMITIE_ASSUREE
    assert AMITIE_CHAMPS["reglage"] == AMITIE_CHAMPS["ident"] + 4
    return [(OFF_AMITIE + AMITIE_CHAMPS["ident"], struct.pack("<II", ident & 0xFFFFFFFF, reglage))]


def dec_amitie(b: bytes) -> dict:
    """ApAmitie (0x40 octets à OFF_AMITIE)."""
    b = bytes(b).ljust(TAILLE_AMITIE, b"\0")
    return {n: struct.unpack_from("<I", b, o)[0] for n, o in AMITIE_CHAMPS.items()}


def amitie_en_vigueur(b: bytes, ident_client: int, liee: bool, magic: bool = True) -> int:
    """Réglage EN VIGUEUR vu par le jeu (reglageEnVigueur d'amitie.cpp) : 1..3, ou 0 (tirage du jeu d'origine)."""
    d = dec_amitie(b)
    if not magic or not AMITIE_X2 <= d["reglage"] <= AMITIE_ASSUREE:
        return AMITIE_NORMAL
    if d["publie"] != AMITIE_PUBLIE or not d["compile"] & AMITIE_COMPILE:
        return AMITIE_NORMAL
    if ident_client and d["ident"] != ident_client:
        return AMITIE_NORMAL
    return d["reglage"] if liee else AMITIE_NORMAL


def _s32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def amitie_seuil(bonus: int, cle: int, premier: int = 1) -> tuple[int, int]:
    """(seuil, borne) du tirage du jeu (FUN_00659CD4, fin) : seuil = bonus x clé + premier x 10000 (32 bits signés),
    borne = clé x 10000 ; chance du jeu = min(1, seuil / borne) = min(1, bonus / 10000 + premier / clé)."""
    return _s32(bonus * cle + premier * 10000), _s32(cle * 10000)


def amitie_seuil_regle(seuil: int, reglage: int) -> int:
    """Seuil comparé au nombre tiré : x 2 ou x 4, saturé à 0x7FFFFFFF ; négatif ou nul : inchangé (seuilRegle)."""
    if seuil <= 0 or reglage not in (AMITIE_X2, AMITIE_X4):
        return seuil
    return min(seuil * (2 if reglage == AMITIE_X2 else 4), 0x7FFFFFFF)


def amitie_decision(reglage: int, interrupteur: bool, seuil: int, borne: int, tire) -> tuple[bool, bool]:
    """(devient ami, nombre tiré consommé) pour un candidat qui a passé TOUS les refus du jeu. `interrupteur` :
    0xABCB4EE6 lu vrai (Pandanoko, invités, combats uniques, ou le jeu). `tire` : fonction sans argument qui rend le
    nombre du jeu (0 .. borne - 1), appelée au plus une fois, et seulement là où le jeu tire."""
    if interrupteur or reglage == AMITIE_ASSUREE:
        return True, False
    if borne <= 0:
        return False, False
    n = tire()
    return amitie_seuil_regle(seuil, reglage) > n, True


def amitie_choix_detail(retenus, reglage: int, tire) -> tuple:
    """Choix de l'ami de fin de combat (FUN_005574F8 récrite, amitie.cpp ; doc §10 et §11). `retenus` : pour chacun
    des 12 emplacements, None (vide, refusé par FUN_00659CD4 ou écarté par l'interrupteur en combat à règle 0x200) ou
    (poids, nourri[, pas_eu]) : poids = 1 / clé du quartet 0 (0 : clé nulle), nourri = hachage d'aliment non nul,
    pas_eu = pas encore ami dans le Médaillium (absent : « déjà eu », pas de préférence). `reglage` : réglage EN
    VIGUEUR. `tire(n)` = FUN_0055D920(1, n - 1), appelé une fois s'il y a au moins un candidat.
    Rend (emplacement retenu ou None, choix limité aux nourris, choix limité aux pas encore amis). Jeu d'origine : le
    plus petit poids (le plus rare), tirage à égalité. En « assurée » : 1) s'il y a au moins un nourri, les nourris
    seulement ; 2) parmi ce qui reste, s'il y a au moins un pas encore ami, ceux-là seulement ; 3) la règle du jeu."""
    assuree = reglage == AMITIE_ASSUREE
    nourris_seuls = assuree and any(r is not None and r[1] for r in retenus)
    reste = [r is not None and (not nourris_seuls or bool(r[1])) for r in retenus]
    pas_eu = [reste[i] and len(r) > 2 and bool(r[2]) for i, r in enumerate(retenus)]
    pas_eus_seuls = assuree and any(pas_eu)
    minimum, candidats = -1.0, []
    for i, r in enumerate(retenus):
        if not reste[i] or (pas_eus_seuls and not pas_eu[i]):
            continue
        if minimum < 0.0 or r[0] < minimum:
            minimum, candidats = r[0], [i]
        elif r[0] == minimum:
            candidats.append(i)
    if not candidats:
        return None, nourris_seuls, pas_eus_seuls
    return candidats[tire(len(candidats))], nourris_seuls, pas_eus_seuls


def amitie_choix(retenus, reglage: int, tire) -> tuple:
    """amitie_choix_detail sans le 3e élément : (emplacement retenu ou None, choix limité aux nourris)."""
    i, nourris_seuls, _ = amitie_choix_detail(retenus, reglage, tire)
    return i, nourris_seuls


def amitie_chance(reglage: int, seuil: int, borne: int) -> float:
    """Chance exacte (0..1) du même candidat, interrupteur faux : nombre de valeurs tirées gagnantes / borne."""
    if reglage == AMITIE_ASSUREE:
        return 1.0
    if borne <= 0:
        return 0.0
    return max(0, min(amitie_seuil_regle(seuil, reglage), borne)) / borne


# --- V3, lot 17 (docs/systemes/archipelago_v3_branchement_voie_revanches.md) : branchement côté client des options
# étendues 29 et 30 (lots 13 et 15), et noms des « manquants » séparés par SORTE.
#
# Les n° de la liste `verrous_manquants` du client viennent de trois numérotations qui se RECOUVRENT :
#  - « verrou »   : n° k d'un verrou (0..23 : ApVerrous ; 40..55 : ApVerrous2 ; 56..87 : ApVerrous3) ;
#  - « fonction » : n° de `fonctions_exigees` (22..30 : bits de ApVerrous::compiles ou n° sentinelles ; 32..62 : fonctions
#                   étendues de ApPnj::fonctions ; 63.. : n° « client », jamais publiés par le jeu) ;
#  - « option »   : 100 + bit d'une option étendue de ApVerrous2 dont des locations dépendent (125).
# Les fonctions étendues 41 à 45 portaient donc, dans un message « Verrous manquants », le nom des verrous de même n°
# (Documents perdus, Cartes d'Ultramax, Clé terrifiante, Clé sanglier, Clé cerf). NOMS_VERROUS ne garde que les
# verrous ; NOMS_FONCTIONS a toutes les fonctions ; `nom_manquant(sorte, n)` choisit la table.
SORTE_VERROU, SORTE_FONCTION, SORTE_OPTION = "verrou", "fonction", "option"
NOMS_FONCTIONS = {n: NOMS_VERROUS.pop(n) for n in (
    FONCTION_ETENDUES, FONCTION_INVITES, FONCTION_CRIMINELS_LIBRES, FONCTION_COMBATS_LIBRES, FONCTION_GRELOTS_ESHOP,
    FONCTION_BOUTIQUES, FONCTION_ANIM, FONCTION_CRIMINELS_TROUVABLES, FONCTION_DEUX_ULTRAMAX, FONCTION_INVITES_ESPECE,
    FONCTION_TRANSFERT, FONCTION_INVITES_V3, FONCTION_AMITIE_UNIQUES, FONCTION_CLIENT_4, FONCTION_CLIENT_5,
    FONCTION_CLIENT_6, FONCTION_CLIENT_7, FONCTION_CLIENT_8, FONCTION_CLIENT_9)}
NOMS_FONCTIONS.update({
    FONCTION_EVENEMENT_PLACE: "Yo-kai d'évènement à leur emplacement d'origine (fonction 34)",
    FONCTION_EVENEMENT_LIBRE: "Yo-kai d'évènement à leur emplacement d'origine, place libre (fonction 35)",
    FONCTION_TUNNEL_LIBRE: "Tunnel sans fin sans limite par jour (fonction 36)",
    FONCTION_CLIENT_2: "Yo-kai d'évènement à leur emplacement d'origine (client trop ancien)",
    FONCTION_CLIENT_3: "Boss détecté par un octet de progression (client trop ancien)",
    **NOMS_FONCTIONS_LOT12, **NOMS_FONCTIONS_LOT13, **NOMS_FONCTIONS_LOT15, **NOMS_FONCTIONS_LOT16})
NOMS_OPTIONS_MANQUANTES = {OPTION2_MANQUANTE_BASE + OPTION2_TRANSFERT:
                           NOMS_VERROUS.pop(OPTION2_MANQUANTE_BASE + OPTION2_TRANSFERT)}


def nom_manquant(sorte: str, n: int) -> str:
    """Nom affiché d'un élément exigé par la graine et absent du jeu (ou du client), selon sa SORTE."""
    if sorte == SORTE_FONCTION:
        return NOMS_FONCTIONS.get(n, f"fonction {n}")
    if sorte == SORTE_OPTION:
        return NOMS_OPTIONS_MANQUANTES.get(n, f"option étendue {n - OPTION2_MANQUANTE_BASE}")
    return NOMS_VERROUS.get(n, f"verrou k={n}")


# Options étendues de CONFORT de l'après-jeu (clés `revanches_sans_limite` et `tirage_dirige_voie` de slot_data,
# absentes = désactivées) : le client pose le bit 29 / 30 de ApVerrous2::actifs avec les autres options étendues
# (aucun paquet de plus) ; il n'écrit RIEN dans ApTirages (zone du jeu seulement : l'ordre des Yo-kai visés par le
# tirage dirigé est CIBLES_TIRAGE, en dur dans voie.cpp). Aucune location n'en dépend : rien dans `fonctions_exigees`,
# aucun n° « client » ; option ou fonction absente du jeu : avertissement, jamais de refus.
# Fonctions étendues que chaque option porte (un build peut en retirer une : --define YKW2_AP_SANS_…) :
FONCTIONS_OPTION2 = {OPTION2_LIMITES_JOUR: (FONCTION_BOSS_VOIE, FONCTION_COMBATS_REQUETES, FONCTION_REVANCHES_REQUETES),
                     OPTION2_TIRAGE_DIRIGE: (FONCTION_TIRAGE_DIRIGE,)}
# code de `options_absentes` du client : option étendue compilée mais dont une FONCTION manque (300 + n° de fonction)
OPTION_FONCTION_MANQUANTE_BASE = 300


def options2_confort_aj(revanches_sans_limite: bool, tirage_dirige_voie: bool) -> int:
    """Bits des options étendues 29 et 30 à poser dans ApVerrous2::actifs pour ces deux options de la graine."""
    return options2_limites_jour(revanches_sans_limite) | options2_tirage_dirige(tirage_dirige_voie)


def fonctions_options2(options2: int) -> tuple[int, ...]:
    """Fonctions étendues portées par les options étendues 29 / 30 présentes dans `options2` (dans l'ordre des n°)."""
    return tuple(sorted(n for bit, fs in FONCTIONS_OPTION2.items() if options2 >> bit & 1 for n in fs))


def nom_option_absente(k: int) -> str | None:
    """Nom d'un code de `options_absentes` : 100 + bit (option étendue de ApVerrous2), 300 + n (fonction d'une option
    étendue) ; None pour un code d'une autre famille (k < 100 : ApVerrous ; 200 : amitié)."""
    if k >= OPTION_FONCTION_MANQUANTE_BASE:
        return NOMS_FONCTIONS.get(k - OPTION_FONCTION_MANQUANTE_BASE, f"fonction {k - OPTION_FONCTION_MANQUANTE_BASE}")
    if OPTION2_MANQUANTE_BASE <= k < OPTION_AMITIE_MANQUANTE:
        return NOMS_OPTIONS2.get(k - OPTION2_MANQUANTE_BASE, f"option étendue {k - OPTION2_MANQUANTE_BASE}")
    return None


# ------------------------------------------------------------------------------------------------------------------
# V3, lot 18 (docs/systemes/archipelago_v3_objectif_medaillium.md) : objectif « medaillium_complet »
# ------------------------------------------------------------------------------------------------------------------
# N° « client » 71, jamais publié par le jeu : ce client sait lire `slot_data.objectif_seuil` (victoire = partie
# terminée ET au moins ce nombre de bits « acquis » parmi `objectif_medailles`). Un client d'avant, qui exigerait les
# 448 bits quel que soit le seuil, refuse la graine. Les fonctions 41 à 44 du patch, que cet objectif exige, sont des
# fonctions étendues ordinaires (vérifiées dans ApPnj::fonctions) ; les options étendues 29 et 30 arrivent par les
# clés `revanches_sans_limite` / `tirage_dirige_voie` de slot_data, forcées à vrai par l'APWorld.
FONCTION_CLIENT_10 = 71
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_10}
NOMS_FONCTIONS[FONCTION_CLIENT_10] = "Objectif « Médaillium complet » (client trop ancien)"
# --- V3, lot 19 : pièces spéciales du Crank-a-kai (pieces.cpp, voie.cpp ; docs/systemes/
# archipelago_v3_pieces_speciales.md §12, archipelago_boite.md §44). CÔTÉ JEU et protocole seulement : ni l'APWorld ni
# `synchro.py` n'écrivent encore cette zone (lot suivant).
# UNE option du joueur, l'option étendue 32 (bit 0 de ApPieces::options : ApVerrous2 n'a plus de bit d'option libre),
# et UNE fonction étendue, 46, publiée dans ApPnj::fonctions quand les quatre parties sont compilées :
#  - tirage dirigé par TABLE : Pièce 5 étoiles (n'importe laquelle des deux machines ordinaires donne le premier des
#    16 Yo-kai visés qui n'est pas ami, ordre unique), Pièce frisson (fleur), 9 pièces régionales, Bingo-kai gagnant ;
#  - pièce rendue : « reçues d'Archipelago - visés déjà amis > pièces du sac » redonne la différence, dans la limite
#    d'un budget compté dans la sauvegarde ;
#  - Entrain Express : passage 1 fois sur 5 (lot 22 : remplacé par le seul réglage `train_dore`, option étendue 34) ;
#  - Pile ou passe / Super pile ou passe : un Yo-kai déjà ami n'est plus proposé dans le menu de choix.
# Zone ApPieces (0xC0 octets) : le jeu publie `publie`, `compile`, `options_compilees` ; le client écrit
# `dons_valides`, `recues`, `ident`, puis `options` EN DERNIER, seulement quand ils changent (aucun paquet périodique).
OPTION3_PIECES = 32                      # option étendue 32 = bit 0 du SECOND mot d'options étendues (ApPieces::options)
OPTION3_BASE = 32
FONCTION_PIECES = 46
OFF_PIECES, TAILLE_PIECES = 0x23640, 0xC0
PIECES_PUBLIE = 0x31505041               # « APP1 »
PIECES_TIRAGE, PIECES_RENDUE, PIECES_TRAIN, PIECES_CHOIX = 0x01, 0x02, 0x04, 0x08
PIECES_TOUT = PIECES_TIRAGE | PIECES_RENDUE | PIECES_TRAIN | PIECES_CHOIX
# V3, lot 20 : le tirage de la Pièce 5 étoiles suit l'ordre de sortie écrit par le client (ApPieces::ordre, 16 octets
# à +0x94 : ordre[r] = rang, dans la liste EN DUR du jeu, du Yo-kai qui sort en r-ième). Bit de `compile` à part de
# PIECES_TOUT (la fonction 46 est publiée par un patch du lot 19, qui ne lit pas l'ordre) : une graine dont l'ordre
# est tiré à la génération exige ce bit (`PIECES_EXIGES`).
PIECES_ORDRE = 0x10
PIECES_EXIGES = PIECES_TOUT | PIECES_ORDRE
NB_PIECES_5E = 16
PIECES_OFF_ORDRE, PIECES_OFF_ORDRE_ETAT = 0x94, 0xA4
ORDRE_CLIENT, ORDRE_EN_DUR = 1, 2
ORDRE_ETATS = {0: "aucun tirage de Pièce 5 étoiles vu", ORDRE_CLIENT: "ordre de la graine suivi",
               ORDRE_EN_DUR: "ordre de la graine absent ou invalide : ordre en dur du jeu"}
PIECES_OPTION = 0x00000001
PIECES_OPTION_PHOTOS = 0x00000002          # (lot 21) option étendue 33 : photos de Ψ Blasters tenues pour prises
CAP_PIECES_FAMILLES, NB_PIECES_FAMILLES = 16, 14          # (lot 21 : famille 13, Pièce bleu ciel)
PIECES_OFF_OPTIONS, PIECES_OFF_IDENT, PIECES_OFF_DONS_VALIDES, PIECES_OFF_RECUES = 0x08, 0x10, 0x14, 0x18
PIECES_CHAMPS = {"publie": 0x00, "compile": 0x04, "options": 0x08, "options_compilees": 0x0C, "ident": 0x10,
                 "dons_valides": 0x14, "tirages": 0x28, "tirages_diriges": 0x2C, "tirage_table": 0x30,
                 "tirage_lot": 0x34, "tirage_refus": 0x38, "tirages_croises": 0x3C, "rendu_cle": 0x40, "rendues": 0x44,
                 "rendu_famille": 0x48, "rendu_refus": 0x4C, "evaluations": 0x70, "differes": 0x74,
                 "choix_table": 0x78, "choix_plan": 0x7C, "choix_remplaces": 0x80, "train_ecritures": 0x84,
                 "train_releves": 0x88, "train_alea": 0x8C, "ordre_etat": 0xA4,
                 "photos_relevees": 0xA8, "photos_reelles": 0xAC,                    # (lot 21)
                 "train_reglage": 0xB0, "ventes_masquees": 0xB4, "train_k": 0xB8}    # (lot 22)
PIECES_OFF_RENDU_DU, PIECES_OFF_RENDU_SAC, PIECES_OFF_BUDGET_SAC, PIECES_OFF_BUDGET_CHOIX = 0x50, 0x60, 0x90, 0x91
TIRAGE_REFUS_OBJET = 5
TIRAGE_REFUS_PIECES = {**TIRAGE_REFUS, 4: "option « pièces spéciales » pas en vigueur",
                       TIRAGE_REFUS_OBJET: "lot d'une autre table : objet du tirage inattendu"}
RENDU_AUCUN, RENDU_HORS_VIGUEUR, RENDU_DONS_ATTENDUS, RENDU_SINGLETON, RENDU_BUDGET, RENDU_ECHEC, RENDU_INCONNUE = \
    range(7)
RENDU_REFUS = {RENDU_AUCUN: "rien à signaler", RENDU_HORS_VIGUEUR: "option pas en vigueur",
               RENDU_DONS_ATTENDUS: "des dons comptés par le client ne sont pas encore traités",
               RENDU_SINGLETON: "inventaire ou définitions absents", RENDU_BUDGET: "budget de pièces redonnées épuisé",
               RENDU_ECHEC: "le jeu a refusé le don (réessayé au prochain passage sur le terrain)",
               RENDU_INCONNUE: "pièce inconnue de ce jeu"}
PIECES_OCTET_SAC, PIECES_OCTET_CHOIX = 396, 449       # flags octets globaux non définis (catégorie 6) : pièces redonnées
PIECES_BUDGET_SAC, PIECES_BUDGET_CHOIX = 60, 12
TABLE_5E_PRESENT, TABLE_5E_PASSE = 0xB73A21B6, 0x27853C27
TABLE_PILE, TABLE_SUPER_PILE = 0x377BE3C6, 0xAE72B27C
TABLE_TRAIN_OR = 0x2443B4DF
TABLE_BLEU_PRESENT, TABLE_BLEU_PASSE = 0x3E9E0D66, 0xC03D1120    # (lot 21) Pièce bleu ciel : gacha_present / gacha_past
FLAG_TRAIN_OR = 0x33CEE5A0                # flag temporaire n° 142 : l'Entrain Express est en gare
TRAIN_OR_SUR = 9                          # (k - 1) « non » sur 9 deviennent « oui » : 1/10 + 9/10 x (k - 1)/9 = k/10
TRAIN_TRANCHE = 7281                      # tirage 16 bits gardé sous 9 x 7281 = 65529 (uniforme) : 7281 par neuvième
CLASSE_CAPSULE, CAPSULE_LOT = 0x007FADE4, 364
SORTE_VOIE, SORTE_5E, SORTE_PIECE, SORTE_REGION, SORTE_BLEU = range(5)
# Familles de pièces, dans l'ordre des compteurs `recues` : (clé, objet du jeu, n° du Médaillium des Yo-kai visés dans
# l'ordre de sortie, exemplaires que le sac peut tenir, 1 = budget « choix »).
FAMILLES_PIECES = (
    ("piece_5_etoiles", 0xCB567D2C, (37, 39, 81, 83, 118, 122, 157, 159, 199, 201, 238, 240, 279, 283, 305, 321), 99, 0),
    ("piece_frisson_fleur", 0x35F5616A, (59, 68, 233, 228), 99, 0),
    ("piece_du_nord", 0x60694E14, (370,), 99, 0), ("piece_du_nordet", 0x176E7E82, (372,), 99, 0),
    ("piece_du_levant", 0x8E672F38, (374,), 99, 0), ("piece_du_centre", 0xF9601FAE, (376,), 99, 0),
    ("piece_du_ponant", 0x69DF023F, (378,), 99, 0), ("piece_des_montagnes", 0x1ED832A9, (380,), 99, 0),
    ("piece_du_sud", 0x7E1FBB4C, (382,), 99, 0), ("piece_du_centre_ouest", 0x09188BDA, (384,), 99, 0),
    ("piece_des_iles", 0x9011DA60, (386,), 99, 0),
    ("pile_ou_passe", 0x93538339, (95, 259, 53), 1, 1), ("super_pile_ou_passe", 0x21778140, (142, 285, 138), 1, 1),
    # V3, lot 21 : pièce de COULEUR ordinaire du jeu (vendable, trouvable) ; un seul visé, Bananar
    ("piece_bleu_ciel", 0xE35507D8, (314,), 99, 0))
FAMILLE_PIECE = {f[0]: i for i, f in enumerate(FAMILLES_PIECES)}
# Yo-kai visés par le tirage dirigé de ce lot, à la suite de CIBLES_TIRAGE dans voie.cpp, dans l'ordre de priorité :
# (table, lot, CHARA_PARAM, n° du Médaillium, sorte).
CIBLES_PIECES = (
    (TABLE_5E_PRESENT, 0xD8998DFE, 0xD2EA2590, 37, SORTE_5E), (TABLE_5E_PASSE, 0x0B3A4899, 0x0149E0F7, 39, SORTE_5E),
    (TABLE_5E_PRESENT, 0x1AE5B9FB, 0x10961195, 81, SORTE_5E), (TABLE_5E_PASSE, 0x8EE6064C, 0x8495AE22, 83, SORTE_5E),
    (TABLE_5E_PRESENT, 0x2D192B3E, 0x276A8350, 118, SORTE_5E), (TABLE_5E_PASSE, 0xFE988CAE, 0xF4EB24C0, 122, SORTE_5E),
    (TABLE_5E_PRESENT, 0x87328142, 0x8D41292C, 157, SORTE_5E), (TABLE_5E_PASSE, 0x69F16D95, 0x6382C5FB, 159, SORTE_5E),
    (TABLE_5E_PRESENT, 0xE2571FBD, 0xE824B7D3, 199, SORTE_5E), (TABLE_5E_PASSE, 0x59A344A3, 0x53D0ECCD, 201, SORTE_5E),
    (TABLE_5E_PRESENT, 0x29BB6958, 0x23C8C136, 238, SORTE_5E), (TABLE_5E_PASSE, 0x71FA1BF9, 0x7B89B397, 240, SORTE_5E),
    (TABLE_5E_PRESENT, 0xCD8299E3, 0xC7F1318D, 279, SORTE_5E), (TABLE_5E_PASSE, 0xB03A7329, 0xBA49DB47, 283, SORTE_5E),
    (TABLE_5E_PASSE, 0x78F89EAE, 0x728B36C0, 305, SORTE_5E), (TABLE_5E_PRESENT, 0x96CF12D7, 0x9CBCBAB9, 321, SORTE_5E),
    (0xEB1042E3, 0x8FF64161, 0x8585E90F, 59, SORTE_PIECE), (0xEB1042E3, 0xCBC80593, 0xC1BBADFD, 68, SORTE_PIECE),
    (0xEB1042E3, 0x86F4C436, 0x8C876C58, 233, SORTE_PIECE), (0xEB1042E3, 0x737462F6, 0x7907CA98, 228, SORTE_PIECE),
    (0x0CA86FE4, 0xA5D9E145, 0xAFAA492B, 370, SORTE_REGION), (0x7BAF5F72, 0x0FD029CE, 0x05A381A0, 372, SORTE_REGION),
    (0x1B68D697, 0x2ABB7612, 0x20C8DE7C, 374, SORTE_REGION), (0x6C6FE601, 0x80B2BE99, 0x8AC116F7, 376, SORTE_REGION),
    (0xF566B7BB, 0x606DC9AA, 0x6A1E61C4, 378, SORTE_REGION), (0x8261872D, 0x98B9C8F5, 0x92CA609B, 380, SORTE_REGION),
    (0x1C05128E, 0x32B0007E, 0x38C3A810, 382, SORTE_REGION), (0x6B022218, 0x17DB5FA2, 0x1DA8F7CC, 384, SORTE_REGION),
    (0xF20B73A2, 0xBDD29729, 0xB7A13F47, 386, SORTE_REGION),
    (TABLE_TRAIN_OR, 0x40EC2482, 0x45A1A65C, 132, SORTE_PIECE), (TABLE_TRAIN_OR, 0xDAD16226, 0xDF9CE0F8, 65, SORTE_PIECE),
    # V3, lot 21 : Bananar, lot de la table du PASSÉ de la Pièce bleu ciel ; dirigé sur les deux machines (la dernière
    # ligne : `k_bananar` de voie.cpp)
    (TABLE_BLEU_PASSE, 0x14DB40E8, 0x1EA8E886, 314, SORTE_BLEU))
# toutes les lignes de k_cibles (voie.cpp), dans l'ordre : celles du lot 13 (sorte Voie) puis celles de ce lot
CIBLES_TOUTES = tuple(c + (SORTE_VOIE,) for c in CIBLES_TIRAGE) + CIBLES_PIECES
PREMIERE_5E = len(CIBLES_TIRAGE)
# lots des deux tables au choix : (table, lot, n° du Médaillium), dans l'ordre des places du menu
CHOIX_PILE = ((TABLE_PILE, 0x5E7C3C5F, 95), (TABLE_PILE, 0xC7756DE5, 259), (TABLE_PILE, 0xB0725D73, 53),
              (TABLE_SUPER_PILE, 0x2E16C8D0, 142), (TABLE_SUPER_PILE, 0x5911F846, 285),
              (TABLE_SUPER_PILE, 0xC018A9FC, 138))
NOMS_OPTIONS3 = {OPTION3_PIECES: "Pièces spéciales du Crank-a-kai (tirage dirigé, pièce rendue, train d'or, Pile ou passe)"}
NOMS_FONCTIONS_LOT19 = {FONCTION_PIECES: "Pièces spéciales du Crank-a-kai (fonction 46)"}
NOMS_FONCTIONS.update(NOMS_FONCTIONS_LOT19)
# V3, lot 20 : n° « client » 72, jamais publié par le jeu : ce client sait écrire ApPieces (option étendue 32, ordre
# de sortie des 16, compteurs de pièces reçues). Un client d'avant accepterait la graine sans jamais poser l'option :
# il la refuse sur ce n° (et sur le 22). Suivant libre : 73.
FONCTION_CLIENT_11 = 72
N_CLIENT_PIECES_PROPOSE = FONCTION_CLIENT_11         # (nom du lot 19, gardé)
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_11}
NOMS_FONCTIONS[FONCTION_CLIENT_11] = "Pièces spéciales du Crank-a-kai (client trop ancien)"
# Codes de `verrous_manquants` du client pour une graine à pièces spéciales (sorte « option », >= 100) :
# - 100 + 32 : zone ApPieces non publiée, option étendue 32 non compilée, ou une des quatre parties absente ;
# - PIECES_ORDRE_MANQUANT : le patch a tout cela mais ne lit pas l'ordre de sortie de la graine (patch du lot 19) :
#   les règles « k Pièces 5 étoiles » de la graine ne vaudraient pas. (Hors de 100..163, les options étendues.)
PIECES_OPTION_MANQUANTE = OPTION2_MANQUANTE_BASE + OPTION3_PIECES
PIECES_ORDRE_MANQUANT = 196
NOMS_OPTIONS_MANQUANTES[PIECES_OPTION_MANQUANTE] = "Pièces spéciales du Crank-a-kai (option étendue 32)"
NOMS_OPTIONS_MANQUANTES[PIECES_ORDRE_MANQUANT] = \
    "Pièces spéciales : ordre de sortie de la Pièce 5 étoiles porté par la graine (patch trop ancien)"


def pieces_compilees(b: bytes) -> int | None:
    """Bits PIECES_* compilés (début de ApPieces), None si la zone n'est pas publiée (jeu d'avant le lot 19)."""
    publie, compile_ = struct.unpack_from("<II", bytes(b).ljust(8, b"\0"), 0)
    return compile_ if publie == PIECES_PUBLIE else None


def dec_pieces(b: bytes) -> dict:
    """ApPieces (0xC0 octets à OFF_PIECES)."""
    b = bytes(b).ljust(TAILLE_PIECES, b"\0")
    d = {n: struct.unpack_from("<I", b, o)[0] for n, o in PIECES_CHAMPS.items()}
    d["recues"] = list(b[PIECES_OFF_RECUES:PIECES_OFF_RECUES + CAP_PIECES_FAMILLES])
    d["rendu_du"] = list(b[PIECES_OFF_RENDU_DU:PIECES_OFF_RENDU_DU + CAP_PIECES_FAMILLES])
    d["rendu_sac"] = list(b[PIECES_OFF_RENDU_SAC:PIECES_OFF_RENDU_SAC + CAP_PIECES_FAMILLES])
    d["budget_sac"], d["budget_choix"] = b[PIECES_OFF_BUDGET_SAC], b[PIECES_OFF_BUDGET_CHOIX]
    d["ordre"] = list(b[PIECES_OFF_ORDRE:PIECES_OFF_ORDRE + NB_PIECES_5E])
    return d


# Ordre EN DUR du jeu (lignes SORTE_5E de k_cibles, voie.cpp) : n° du Médaillium croissant. ApPieces::ordre[r] est un
# rang dans CETTE liste.
ORDRE_5E_JEU = FAMILLES_PIECES[0][2]


def ordre_pieces(medailles) -> bytes:
    """Les 16 octets de ApPieces::ordre pour un ordre de sortie donné en n° du Médaillium (slot_data
    `pieces_ordre`) : ordre[r] = rang du r-ième Yo-kai dans ORDRE_5E_JEU. ValueError si ce n'est pas une permutation
    des 16."""
    medailles = [int(m) for m in medailles]
    if sorted(medailles) != sorted(ORDRE_5E_JEU):
        raise ValueError("ordre des Pièces 5 étoiles : pas une permutation des 16 Yo-kai")
    return bytes(ORDRE_5E_JEU.index(m) for m in medailles)


def ordre_valide(octets) -> bool:
    """Modèle de ordre5E (voie.cpp) : 16 valeurs < 16, toutes différentes."""
    octets = bytes(octets)[:NB_PIECES_5E]
    return len(octets) == NB_PIECES_5E and sorted(octets) == list(range(NB_PIECES_5E))


def ordre_5e_applique(octets=None) -> tuple:
    """N° du Médaillium des 16, dans l'ordre que le jeu suit pour ces octets de ApPieces::ordre (repli : ordre en
    dur)."""
    if octets is not None and ordre_valide(octets):
        return tuple(ORDRE_5E_JEU[i] for i in bytes(octets)[:NB_PIECES_5E])
    return tuple(ORDRE_5E_JEU)


def recues_pieces(recues) -> bytes:
    """Les 16 compteurs `recues` : `recues` = liste par famille, ou dictionnaire {clé de FAMILLES_PIECES: nombre}."""
    if isinstance(recues, dict):
        inconnues = set(recues) - set(FAMILLE_PIECE)
        if inconnues:
            raise ValueError(f"famille de pièce inconnue : {sorted(inconnues)}")
        recues = [recues.get(f[0], 0) for f in FAMILLES_PIECES]
    recues = list(recues)
    if len(recues) > NB_PIECES_FAMILLES or any(n < 0 for n in recues):
        raise ValueError("compteurs de pièces invalides")
    return bytes(min(n, 255) for n in recues).ljust(CAP_PIECES_FAMILLES, b"\0")


def ecritures_pieces(option: bool, recues, dons_valides: int, ident: int, ordre=None,
                     photos: bool = False, train: int = 1, editions: bool = False) -> list[tuple[int, bytes]]:
    """Écritures du client dans ApPieces, DANS L'ORDRE : numéro du dernier don compté, compteurs, ordre de sortie
    des 16 de la Pièce 5 étoiles (lot 20 : `ordre` = n° du Médaillium dans l'ordre de la graine ; None : rien n'est
    écrit là, le jeu garde son ordre en dur), identifiant de partie, puis le mot d'options en dernier (décalages dans
    la zone). `dons_valides` = numéro du dernier don de la file que `recues` compte : le jeu ne rend aucune pièce tant
    qu'il ne l'a pas traité. Il s'écrit AVANT les compteurs : entre les deux écritures le jeu voit au pire l'ancien
    compte avec la nouvelle borne (il attend), jamais une pièce comptée dont le don n'est pas encore arrivé (elle
    serait prise pour une pièce perdue et donnée deux fois). L'ordre s'écrit AVANT l'option : le jeu ne dirige aucun
    tirage (option pas en vigueur) tant que l'ordre de la graine n'est pas en place. `photos` (lot 21) : bit 1 du
    même mot d'options (option étendue 33, photos de Ψ Blasters tenues pour prises), indépendant de `option`.
    `train` (lot 22) : fréquence du train doré, k sur 10 (2..4 : `train_reglage` écrit AVANT le mot d'options, bit 2
    du mot posé ; 1 : bit 2 nul, `train_reglage` n'est pas écrit). `editions` (ap/blasters-terrains-apworld) : bit 3
    (option étendue 35, terrains de Ψ Blasters d'autres éditions jouables seul)."""
    e = [(OFF_PIECES + PIECES_OFF_DONS_VALIDES, struct.pack("<I", dons_valides & 0xFFFFFFFF)),
         (OFF_PIECES + PIECES_OFF_RECUES, recues_pieces(recues))]
    if ordre is not None:
        e.append((OFF_PIECES + PIECES_OFF_ORDRE, ordre_pieces(ordre)))
    train = int(train) if int(train) in (2, 3, 4) else 1
    if train > 1:
        e.append((OFF_PIECES + 0xB0, struct.pack("<I", train)))
    return e + [(OFF_PIECES + PIECES_OFF_IDENT, struct.pack("<I", ident & 0xFFFFFFFF)),
                (OFF_PIECES + PIECES_OFF_OPTIONS,
                 struct.pack("<I", (PIECES_OPTION if option else 0) | (PIECES_OPTION_PHOTOS if photos else 0)
                             | (0x4 if train > 1 else 0) | (0x8 if editions else 0)))]


def pieces_en_vigueur(b: bytes, partie: int, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de apPiecesEnVigueur : zone publiée, partie (PIECES_*) compilée, option compilée et posée par le client
    pour SA partie (`ident`), sauvegarde liée."""
    c = pieces_compilees(b)
    if c is None or not c & partie or not liee:
        return False
    d = dec_pieces(b)
    if not d["options_compilees"] & PIECES_OPTION or not d["options"] & PIECES_OPTION:
        return False
    return not ident_client or d["ident"] == ident_client


def _passe_table(lots: list[tuple], rang: int, cherche: int) -> dict:
    """Modèle de passeTable (voie.cpp) : `lots` = (lot, poids, plafond, est_objet, contenu, rang_exige)."""
    r = {"total": 0, "plafonds": 0, "avant": 0, "poids": 0, "plafond": 0, "trouve": False}
    for lot, poids, plafond, _est_objet, _contenu, rang_exige in lots:
        if rang_exige > rang:
            continue
        if plafond:
            r["plafonds"] += 1
        if cherche and lot == cherche and not r["trouve"]:
            r.update(trouve=True, avant=r["total"], poids=poids, plafond=plafond)
        r["total"] += poids
    return r


def tirage_pieces_motif(table: int, tables: dict, somme: int, amis: set[int], rang: int, vigueur_voie: bool,
                        vigueur_pieces: bool, tire: int, objet_ok: bool = True,
                        pieces_compile: bool = True, ordre=None, bleu_compile: bool = True) -> tuple[int, int, int, int]:
    """Modèle de tirageDirige (voie.cpp, lots 13, 19 et 20) : (valeur rendue au jeu par FUN_00674668, motif
    TIRAGE_REFUS, lot visé ou 0, lot ÉCRIT dans l'objet du tirage ou 0). `tables` : {table: lots} de toutes les tables
    chargées (lots = (lot, poids, plafond, est_objet, contenu, rang_exige)) ; `table` : celle de la pièce mise dans la
    machine. Une table qui n'est visée par aucune ligne rend (tire, -1, 0, 0) : rien n'est compté. `ordre` (lot 20) :
    les 16 octets de ApPieces::ordre (None ou pas une permutation : ordre en dur des lignes). `bleu_compile` (lot
    21) : la ligne de Bananar est compilée (Pièce bleu ciel, les deux machines)."""
    cibles = CIBLES_TOUTES if pieces_compile else CIBLES_TOUTES[:PREMIERE_5E]
    if not bleu_compile:
        cibles = tuple(c for c in cibles if c[4] != SORTE_BLEU)
    if pieces_compile and ordre is not None and ordre_valide(ordre):
        # Pièce 5 étoiles : les 16 lignes SORTE_5E dans l'ordre écrit par le client (les autres lignes inchangées)
        cibles = cibles[:PREMIERE_5E] + tuple(cibles[PREMIERE_5E + i] for i in bytes(ordre)[:NB_PIECES_5E]) \
            + cibles[PREMIERE_5E + NB_PIECES_5E:]
    premiere = next((i for i, c in enumerate(cibles) if c[0] == table), None)
    if premiere is None and table == TABLE_BLEU_PRESENT:
        # lot 21 : l'AUTRE table de la Pièce bleu ciel (machine du présent), qui n'a pas le lot de Bananar
        premiere = next((i for i, c in enumerate(cibles) if c[4] == SORTE_BLEU), None)
    if premiere is None:
        return tire, -1, 0, 0
    sorte = cibles[premiere][4]
    if sorte == SORTE_5E:
        premiere = PREMIERE_5E
    if not (vigueur_voie if sorte == SORTE_VOIE else vigueur_pieces):
        return tire, 4, 0, 0
    if table not in tables:
        return tire, 2, 0, 0
    courante = _passe_table(tables[table], rang, 0)
    if courante["total"] != somme:
        return tire, 3, 0, 0
    manque = False
    infos = {l[0]: l for lots in tables.values() for l in lots}      # CAPSULE_ITEM_INFO : recherche globale du lot
    for t, lot, param, medaille, s in cibles[premiere:]:
        meme = t == table
        if not meme and not (sorte in (SORTE_5E, SORTE_BLEU) and s == sorte):
            continue
        if medaille in amis:
            continue
        manque = True
        info = infos.get(lot)
        if info is None or info[3] or info[4] != param or t not in tables:
            continue
        p = _passe_table(tables[t], rang, lot)
        if not p["trouve"] or p["poids"] == 0 or (p["plafond"] and s != SORTE_REGION):
            continue
        if not meme:
            if courante["plafonds"] or p["plafond"] or not objet_ok:
                return tire, TIRAGE_REFUS_OBJET, 0, 0
            return tire, 0, lot, lot
        return p["avant"], 0, lot, 0
    return tire, (2 if manque else 1), 0, 0


def lot_final(lots: list[tuple], rang: int, valeur: int, ecrit: int = 0) -> tuple[int, dict]:
    """Modèle de la boucle de choix de FUN_0040B81C (0x0040C028..0x0040C1B0) avec ses plafonds : (lot retenu, octets de
    plafond écrits {lot: valeur}). `ecrit` : lot déjà posé dans l'objet avant la boucle (champ +364 non nul : le jeu
    ne retient plus rien). `lots` : (lot, poids, plafond, est_objet, contenu, rang_exige, compteur du plafond)."""
    r, cumul, retenu, ecrits = valeur + 1, 0, ecrit, {}
    for l in lots:
        lot, poids, plafond, rang_exige = l[0], l[1], l[2], l[5]
        compteur = l[6] if len(l) > 6 else 0
        if retenu == 0:
            if rang_exige > rang:
                continue
            avant, cumul = cumul, cumul + poids
            if avant <= r <= cumul and poids:        # (le jeu : cumul_avant <= r et r <= cumul_après)
                retenu = lot
                if plafond:
                    ecrits[lot] = 0                  # lot tiré : son compteur est remis à 0
                continue
        if plafond:                                  # lot à plafond non tiré : compteur + 1, imposé s'il l'atteint
            n = (compteur + 1) & 0xFF
            if plafond <= n:
                retenu, ecrits[lot] = lot, 0
            else:
                ecrits[lot] = n
    return retenu, ecrits


def piece_rendue(recues, amis: set[int], sac: dict, budgets: tuple[int, int], connues=None,
                 plein: bool = False,
                 bleu_compile: bool = True) -> tuple[list[tuple[int, int, int]], tuple[int, int], int, list[int], list[int]]:
    """Modèle de apPiecesImage (une évaluation EN VIGUEUR, dons traités) : (dons [(famille, objet, nombre)], nouveaux
    budgets (sac, choix), motif RENDU_*, dû par famille, sac par famille). `sac` : {objet: nombre} ; `budgets` : les
    deux octets persistants ; `connues` : objets définis dans ce jeu (défaut : tous) ; `plein` : GiveItem refuse."""
    b = list(budgets)
    dons, refus, dus, sacs = [], RENDU_AUCUN, [], []
    octets = recues_pieces(recues)
    for f, (cle_f, piece, medailles, maximum, choix) in enumerate(FAMILLES_PIECES):
        if cle_f == "piece_bleu_ciel" and not bleu_compile:
            medailles = ()                          # (lot 21) build sans la ligne de Bananar : jamais due
        du = max(0, min(octets[f], len(medailles)) - sum(1 for m in medailles if m in amis))
        dus.append(du)
        if du == 0:
            sacs.append(0)
            continue
        dans = max(0, sac.get(piece, 0))
        sacs.append(min(dans, 255))
        cible = min(du, maximum)
        if dans >= cible:
            continue
        manque, plafond = cible - dans, (PIECES_BUDGET_CHOIX if choix else PIECES_BUDGET_SAC)
        if b[choix] >= plafond:
            refus = RENDU_BUDGET
            continue
        manque = min(manque, plafond - b[choix])
        if connues is not None and piece not in connues:
            refus = RENDU_INCONNUE
            continue
        if plein:
            refus = RENDU_ECHEC
            continue
        b[choix] += manque
        dons.append((f, piece, manque))
    return dons, (b[0], b[1]), refus, dus, sacs


def choix_plan(table: int, lots: list[int], amis: set[int]) -> tuple[int, int, int] | None:
    """Modèle de choixPlace (pieces.cpp), option en vigueur : lot montré à chaque place du menu de Pile ou passe /
    Super pile ou passe, ou None = menu du jeu (autre table, table inattendue, aucun ami, tous amis). `lots` = les
    lots de la table, dans l'ordre."""
    if table not in (TABLE_PILE, TABLE_SUPER_PILE) or len(lots) != 3:
        return None
    connus = {l: m for t, l, m in CHOIX_PILE if t == table}
    if any(l not in connus for l in lots):
        return None
    deja = [connus[l] in amis for l in lots]
    if not any(deja) or all(deja):
        return None
    plan = []
    for i in range(3):
        j = i
        while deja[j]:
            j = 0 if j == 2 else j + 1
        plan.append(j)
    return tuple(plan)


def train_or_tirage(alea: int, images: int, k: int = 2) -> tuple[bool, int]:
    """Modèle du relèvement de l'Entrain Express (FUN_005011CC) pour une écriture « 0 » du flag n° 142, fréquence
    k sur 10 en vigueur (lot 22 : réglage du joueur, k = 2..4) : (le flag est écrit à 1, nouvel état du générateur).
    Tirage 16 bits uniforme sous 9 x 7281 (rejet), « 1 » si < 7281 x (k - 1) : (k - 1) / 9 exactement."""
    x = (alea ^ (images * 0x9E3779B1)) & 0xFFFFFFFF
    while True:
        if x == 0:
            x = 0x2545F491
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        tire = x >> 8 & 0xFFFF
        if tire < TRAIN_OR_SUR * TRAIN_TRANCHE:
            return tire < TRAIN_TRANCHE * (k - 1), x


# --- V3, lot 21 : Médaillium couvert à 448 / 448 (photos.cpp, voie.cpp, pieces.cpp ; docs/systemes/
# archipelago_v3_medaillium_448.md, archipelago_boite.md §47).
# UNE fonction étendue, 47, publiée quand les deux parties sont compilées :
#  - PHOTOS : option étendue 33 (bit 1 de ApPieces::options), posée par le client pour une graine qui le demande
#    (`slot_data.photos_blasters`, objectif « medaillium_complet ») : la condition GetChrPhotoCnt rend au moins 30 (seul
#    usage : déblocage du terrain 3 de Ψ Blasters, que le terrain 13 de Domniscian, n° 443, exige). Lecture seule ;
#  - BANANAR (n° 314) : ligne de plus du tirage dirigé, Pièce bleu ciel, sur les deux machines ordinaires ; famille 13
#    de la pièce rendue. Sous l'option étendue 32 « pièces spéciales ».
# N° « client » 73, jamais publié par le jeu : ce client sait poser l'option 33 et compter la famille 13. Suivant
# libre : 74. Prochaine fonction étendue libre : 48 ; prochaine option étendue libre : 34.
OPTION3_PHOTOS = 33
FONCTION_LOT21 = 47
PIECES_BLEU, PIECES_PHOTOS = 0x20, 0x40
PIECES_LOT21 = PIECES_BLEU | PIECES_PHOTOS
PIECES_PUBLIES = PIECES_EXIGES | PIECES_LOT21          # tout ce qu'un patch de ce dépôt publie dans ApPieces::compile
PIECES_OPTIONS_COMPILEES = PIECES_OPTION | PIECES_OPTION_PHOTOS
PHOTOS_SEUIL = 30
PIECE_BLEU_CIEL = FAMILLES_PIECES[FAMILLE_PIECE["piece_bleu_ciel"]][1]
FAMILLE_BLEU = FAMILLE_PIECE["piece_bleu_ciel"]
NOMS_OPTIONS3[OPTION3_PHOTOS] = "Photos de Ψ Blasters tenues pour prises (terrain 3 débloqué sans appareil photo)"
NOMS_FONCTIONS[FONCTION_LOT21] = "Médaillium 448 : photos de Ψ Blasters, Bananar à la Pièce bleu ciel (fonction 47)"
FONCTION_CLIENT_12 = 73
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_12}
NOMS_FONCTIONS[FONCTION_CLIENT_12] = "Médaillium 448 : photos de Ψ Blasters, Pièce bleu ciel (client trop ancien)"
# Code de `verrous_manquants` (sorte « option ») : graine qui demande les photos, patch sans l'option étendue 33
PHOTOS_OPTION_MANQUANTE = OPTION2_MANQUANTE_BASE + OPTION3_PHOTOS
NOMS_OPTIONS_MANQUANTES[PHOTOS_OPTION_MANQUANTE] = "Photos de Ψ Blasters tenues pour prises (option étendue 33)"
# Code pour une graine à pièces spéciales qui a Bananar, devant un patch sans sa ligne de tirage (bit PIECES_BLEU)
PIECES_BLEU_MANQUANT = 197
NOMS_OPTIONS_MANQUANTES[PIECES_BLEU_MANQUANT] = \
    "Pièces spéciales : Bananar à la Pièce bleu ciel (patch trop ancien)"


def option3_active(b: bytes, option: int, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de apOption3Active : zone publiée, bit `option` (PIECES_OPTION*) compilé et posé par le client pour SA
    partie, sauvegarde liée. Indépendant des parties de `compile`."""
    if pieces_compilees(b) is None or not liee:
        return False
    d = dec_pieces(b)
    if not d["options_compilees"] & option or not d["options"] & option:
        return False
    return not ident_client or d["ident"] == ident_client


def photos_lues(b: bytes, photos: int, liee: bool, ident_client: int = 0) -> tuple[int, bool]:
    """Modèle de apPhotosLues (photos.cpp) : (valeur rendue par la condition GetChrPhotoCnt pour un compteur réel
    `photos`, relevée ?). Le build doit avoir la partie PHOTOS (sinon la condition est celle du jeu)."""
    c = pieces_compilees(b)
    if photos >= PHOTOS_SEUIL or c is None or not c & PIECES_PHOTOS \
            or not option3_active(b, PIECES_OPTION_PHOTOS, liee, ident_client):
        return photos, False
    return PHOTOS_SEUIL, True


def ecritures_photos(options_actuelles: int, photos: bool, ident: int) -> list[tuple[int, bytes]]:
    """Écritures de l'outil d'essai pour poser ou retirer la seule option étendue 33 (le bit 0 du mot est gardé) :
    identifiant de partie, puis le mot d'options en dernier."""
    mot = (options_actuelles & ~PIECES_OPTION_PHOTOS) | (PIECES_OPTION_PHOTOS if photos else 0)
    return [(OFF_PIECES + PIECES_OFF_IDENT, struct.pack("<I", ident & 0xFFFFFFFF)),
            (OFF_PIECES + PIECES_OFF_OPTIONS, struct.pack("<I", mot & 0xFFFFFFFF))]

# --- V3, lot 22 (docs/systemes/archipelago_v3_blasters_photos_bleu_ciel.md ; archipelago_boite.md §48) ---
#  - Pièce bleu ciel INVENDABLE : fonction étendue 48 (bit 16 de ApPnj::fonctions), bit 0x80 de ApPieces::compile ;
#    sous l'option étendue 32 en vigueur, la liste de VENTE des boutiques est construite sans elle (vente.cpp) ;
#    exigée par toute graine à pièces spéciales générée depuis ce lot ; aucun n° « client » (le client n'écrit rien
#    de nouveau pour elle) ; compteur `ventes_masquees` (+0xB4) ;
#  - FRÉQUENCE DU TRAIN DORÉ : option étendue 34 (bit 2 de ApPieces::options), bit 0x100 de `compile`, réglage k
#    sur 10 dans `train_reglage` (+0xB0, écrit avant le mot d'options) ; fréquence appliquée publiée dans `train_k`
#    (+0xB8). Le réglage décide SEUL (décision de l'humain du 2026-10-17 : l'option 32 ne relève plus le train).
#    Option de confort : absente du jeu = avertissement (code 201 de `options_absentes`), jamais un refus.
# Suivants libres : fonction 49, option étendue 35, n° « client » 74.
FONCTION_LOT22 = 48
OPTION3_TRAIN = 34
PIECES_INVENDABLE, PIECES_TRAIN_REGLAGE = 0x80, 0x100
PIECES_LOT22 = PIECES_INVENDABLE | PIECES_TRAIN_REGLAGE
PIECES_PUBLIES = PIECES_EXIGES | PIECES_LOT21 | PIECES_LOT22
PIECES_OPTION_TRAIN = 0x00000004
PIECES_OPTIONS_COMPILEES = PIECES_OPTION | PIECES_OPTION_PHOTOS | PIECES_OPTION_TRAIN
PIECES_OFF_TRAIN_REGLAGE = 0xB0
TRAIN_K = (1, 2, 3, 4)                    # k sur 10 : normal, x2, x3, x4
TRAIN_NOMS = {1: "normal", 2: "x2", 3: "x3", 4: "x4"}
NOMS_OPTIONS3[OPTION3_TRAIN] = "Fréquence du train doré (Entrain Express)"
NOMS_FONCTIONS[FONCTION_LOT22] = "Pièce bleu ciel invendable (fonction 48)"
OPTION_TRAIN_MANQUANTE = 201            # code de `options_absentes` du client : graine qui règle le train, jeu sans
DEF_VENDABLE = 0x40000000               # mot +40 d'une définition d'objet : bit 30 « vendable »
SHOP_VENTE = 0x850                      # ywCLoopMenuShop : `tmp_shop_sell` (1 = onglet vente)


def train_k(b: bytes, liee: bool, ident_client: int = 0) -> int:
    """Modèle de trainK (pieces.cpp) : fréquence du train doré appliquée, k sur 10 (1 = jeu d'origine)."""
    c = pieces_compilees(b)
    if c is None or not c & PIECES_TRAIN_REGLAGE or not option3_active(b, PIECES_OPTION_TRAIN, liee, ident_client):
        return 1
    r = dec_pieces(b)["train_reglage"]
    return r if r in (2, 3, 4) else 1


def piece_vendable(b: bytes, vendable_def: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle de la liste de VENTE (vente.cpp) pour la Pièce bleu ciel : apparaît-elle parmi les objets à vendre ?
    (`vendable_def` : bit 30 de sa définition dans le jeu.)"""
    c = pieces_compilees(b)
    if not vendable_def:
        return False
    return not (c is not None and c & PIECES_INVENDABLE and pieces_en_vigueur(b, PIECES_INVENDABLE, liee,
                                                                             ident_client))

# --- V3, lots M2b (docs/systemes/archipelago_v3_melange_zones.md) : zones des Yo-kai demandés -------------------------
# N° « client » 74, jamais publié par le jeu : ce client sait placer un Yo-kai demandé dans la zone que la graine lui a
# tirée (mélange des Yo-kai de version 7, `slot_data.yokai_zones`, table `apworld/yokaiwatch2/zones.py`). Un client
# d'avant refuse la graine (la logique suppose le placement). Rien de nouveau dans le jeu ni dans la boîte.
# Suivant libre : 77 (75 et 76 : lots C1 et L1).
FONCTION_CLIENT_13 = 74
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_13}
NOMS_FONCTIONS[FONCTION_CLIENT_13] = "Zones des Yo-kai demandés (client trop ancien)"
# --- V3, lot C1 : distributeurs de soda en checks (docs/systemes/archipelago_v3_distributeurs.md ; archipelago_boite.md
# §50 ; src/archipelago/boutiques.cpp, zone ApDistrib de boite.h). Un check par boisson (ligne 0 / 1 du menu) et par
# machine (54 points OP_VENDING_POINT), SANS bit de sauvegarde : le serveur tient l'état.
#  - fonction étendue 49 (bit 17 de ApPnj::fonctions) : le jeu reconnaît une machine et publie l'achat ;
#  - n° « client » 75 (jamais publié, dans FONCTIONS_CLIENT_V3) : un client d'avant, qui n'écrit pas la table et ne lit
#    pas l'évènement DISTRIBUTEUR, refuse la graine (les checks de distributeur ne partiraient jamais) ;
#  - zone (version et taille inchangées) : en-tête ApDistribEntete (0x40) à 0x23900, table de CAP_DISTRIB entrées
#    ApDistrib (20 octets : carte, point, objet montré par ligne, octet `a_acheter`, drapeaux) à 0x23940, privé du jeu
#    (0x60) à 0x23DA0 ; le client écrit TOUTES les machines de la graine dans l'ordre de l'APWorld (index = rang), puis
#    `nombre`, `etiquette_base` et `valide` EN DERNIER ; ensuite il ne réécrit que l'octet `a_acheter` d'une entrée qui
#    change (une location cochée) ;
#  - évènement DISTRIBUTEUR (10) : id = carte (CRC-32 du nom), valeur = point, valeur2 = article (clé SHOP_CONFIG_INFO),
#    etiquette = location (etiquette_base + 2 m + i), index = ligne i ; DISTRIBUTEUR_VU (11, indices) à l'ouverture :
#    id = carte, valeur = point, etiquette = location de la ligne 0, index = masque des lignes AP, quantite = nombre.
# Prochains libres (après ce lot) : fonction étendue 50, n° « client » 76 (74 : ap/v3-melange-logique-b).
FONCTION_DISTRIBUTEURS = 49
FONCTION_CLIENT_C1 = 75
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_C1}
NOMS_FONCTIONS[FONCTION_DISTRIBUTEURS] = "Distributeurs de soda en checks (fonction 49)"
NOMS_FONCTIONS[FONCTION_CLIENT_C1] = "Distributeurs de soda en checks (client trop ancien)"
OFF_DISTRIB, OFF_DISTRIB_TABLE, CAP_DISTRIB, TAILLE_DISTRIB = 0x23900, 0x23940, 56, 20
OFF_DISTRIB_PRIVE, TAILLE_DISTRIB_PRIVE = 0x23DA0, 0x60
DISTRIB_PUBLIE, DISTRIB_COMPILE, DISTRIB_BONUS, DISTRIB_INDICES = 0x80000000, 0x01, 0x02, 0x04
# fix/distributeurs-affichage (information seulement, aucun refus) : bouton redessiné dès l'achat, nom coupé à la
# largeur du bouton (DISTRIB_NOM_LARGEUR, modèle `largeur_distrib`)
DISTRIB_REDESSIN = 0x08
DISTRIB_NOM_LARGEUR = 132
DISTRIB_VALIDE = 0x01
DISTRIB_LIGNES = 2
DISTRIB_MARQUES = 6
EVT_DISTRIBUTEUR, EVT_DISTRIBUTEUR_VU = 10, 11
EVTS[EVT_DISTRIBUTEUR] = "DISTRIBUTEUR"
EVTS[EVT_DISTRIBUTEUR_VU] = "DISTRIBUTEUR_VU"
SHOP_TYPE_DISTRIB, SHOP_ID = 2, 0x854
W_POINT_REGARDE, POINTS_CARTE, POINT_REGLAGE = 0x30F70, 0x00815394, 0x0C
BONUS_DISTRIB, BONUS_RUBRIQUE = 0x1CE69C29, 8
DISTRIB_ENTETE = ("valide", "compile", "nombre", "etiquette_base", "achats", "ouvertures", "lignes", "refus",
                  "bonus_evites", "motif", "carte_vue", "point_vu", "annonces", "redessins", "noms_coupes")
DISTRIB_MOTIF_POSE, DISTRIB_MOTIF_TABLE, DISTRIB_MOTIF_CARTE, DISTRIB_MOTIF_POINT = 0, 1, 2, 3
DISTRIB_MOTIF_REGLAGE, DISTRIB_MOTIF_INCONNUE, DISTRIB_MOTIF_FAIT = 4, 5, 6
DISTRIB_MOTIFS = {DISTRIB_MOTIF_POSE: "lignes Archipelago posées",
                  DISTRIB_MOTIF_TABLE: "table non valide (client absent) ou sauvegarde non liée",
                  DISTRIB_MOTIF_CARTE: "carte courante inconnue",
                  DISTRIB_MOTIF_POINT: "point regardé absent de la table des points de la carte",
                  DISTRIB_MOTIF_REGLAGE: "réglage du point différent de celui du menu",
                  DISTRIB_MOTIF_INCONNUE: "machine absente de la table du client",
                  DISTRIB_MOTIF_FAIT: "aucune ligne à acheter (tout coché ou achat en attente)"}
# Code de `verrous_manquants` du client pour une graine à distributeurs devant un patch sans la boisson bonus évitée :
# jamais un refus (racheter suffit), avertissement seulement
DISTRIB_BONUS_ABSENT = 202


def crc_carte(nom: str) -> int:
    """Identifiant d'une carte tel que le jeu le range (FUN_0013EEEC = CRC-32 du nom, `t101g00`)."""
    import zlib
    return zlib.crc32(nom.encode("ascii")) & 0xFFFFFFFF


def distrib_disponibles(h) -> bool:
    """Zone assez grande pour ApDistrib (trou de la zone v10 : un jeu antérieur n'a rien là, ne JAMAIS y écrire avant
    d'avoir lu `compile`)."""
    return getattr(h, "taille_zone", 0) >= OFF_DISTRIB_PRIVE + TAILLE_DISTRIB_PRIVE


def enc_distrib(carte: int, point: int, affiche=(0, 0), a_acheter: int = 0, drapeaux: int = DISTRIB_VALIDE) -> bytes:
    """Entrée de la table des distributeurs (20 octets)."""
    a = tuple(affiche) + (0,) * (DISTRIB_LIGNES - len(tuple(affiche)))
    return struct.pack("<IIIIBBH", carte & 0xFFFFFFFF, point & 0xFFFFFFFF, a[0] & 0xFFFFFFFF, a[1] & 0xFFFFFFFF,
                       a_acheter & 0xFF, drapeaux & 0xFF, 0)


def dec_distrib(b: bytes) -> dict:
    c, p, a0, a1, aa, d, _r = struct.unpack_from("<IIIIBBH", b)
    return {"carte": c, "point": p, "affiche": (a0, a1), "a_acheter": aa, "drapeaux": d}


def dec_distrib_entete(b: bytes) -> dict:
    return dict(zip(DISTRIB_ENTETE, struct.unpack_from("<%dI" % len(DISTRIB_ENTETE), b)))


# Nom d'un bouton de distributeur (boutiques.cpp, apDistribLargeurCar / apDistribCouper, mêmes règles) : largeur estimée
# en pixels de la police du menu par un modèle à classes qui MAJORE chaque avance de la police normale.
_DISTRIB_CLASSES = ((5, frozenset(b" ',.Iijl|")), (6, frozenset(b'!"()/:;[\\]{}frt')), (8, frozenset(b"-*_`x")),
                    (13, frozenset(b"GOQm@")), (15, frozenset(b"MW%")))


def _octets_car_distrib(b: bytes, i: int) -> int:
    c = b[i]
    n = 4 if c >= 0xF0 else 3 if c >= 0xE0 else 2 if c >= 0xC0 else 1
    k = 1
    while k < n and i + k < len(b) and b[i + k]:
        k += 1
    return k


def largeur_car_distrib(b: bytes, i: int = 0) -> int:
    c = b[i]
    if c < 0x80:
        for largeur, classe in _DISTRIB_CLASSES:
            if c in classe:
                return largeur
        if 0x41 <= c <= 0x5A or c in b"&w":
            return 12
        return 10
    s = b[i + 1] if i + 1 < len(b) else 0
    if c == 0xC3 and 0x9F <= s <= 0xBF and s not in (0xA6, 0xB0, 0xB7):
        return 10
    return 15


def largeur_distrib(texte) -> int:
    b = texte.encode("utf-8") if isinstance(texte, str) else bytes(texte)
    w, i = 0, 0
    while i < len(b) and b[i]:
        w += largeur_car_distrib(b, i)
        i += _octets_car_distrib(b, i)
    return w


def couper_nom_distrib(src: bytes, cap: int = BOUTIQUE_TEXTE) -> bytes:
    """Modèle de apDistribCouper : nom coupé à DISTRIB_NOM_LARGEUR (sans espace final, suivi de "...") ; inchangé s'il
    tient."""
    src = bytes(src).split(b"\0")[0]
    couper = largeur_distrib(src) > DISTRIB_NOM_LARGEUR
    limite = DISTRIB_NOM_LARGEUR - 18 if couper else DISTRIB_NOM_LARGEUR
    out, i, larg = bytearray(), 0, 0
    while i < len(src):
        n, lc = _octets_car_distrib(src, i), largeur_car_distrib(src, i)
        if larg + lc > limite or len(out) + n + 3 + 1 > cap:
            couper = True
            break
        out += src[i:i + n]
        i += n
        larg += lc
    if couper:
        out = out.rstrip(b" ") + b"..."
    return bytes(out)


def distrib_compiles(entete: bytes) -> int | None:
    """Bits DISTRIB_* publiés par le jeu (`compile` de ApDistribEntete), None si le champ n'est pas publié (patch d'avant
    le lot C1 : octets jamais écrits) ; 0 : build sans les distributeurs."""
    c = struct.unpack_from("<I", entete, 4)[0]
    if not c & DISTRIB_PUBLIE:
        return None
    return c & ~DISTRIB_PUBLIE


def ecritures_distributeurs(entrees: list[bytes], etiquette_base: int) -> list[tuple[int, bytes]]:
    """Écritures (décalage dans la zone, octets) de la table complète, dans l'ordre : `valide` = 0, entrées, `nombre`,
    `etiquette_base`, `valide` = 1 EN DERNIER ; sans entrée : `valide` = 0 seulement (machines d'origine)."""
    if len(entrees) > CAP_DISTRIB or any(len(e) != TAILLE_DISTRIB for e in entrees):
        raise ValueError("table des distributeurs invalide")
    out = [(OFF_DISTRIB, struct.pack("<I", 0))]
    if not entrees:
        return out
    out.append((OFF_DISTRIB_TABLE, b"".join(entrees)))
    out.append((OFF_DISTRIB + 8, struct.pack("<II", len(entrees), etiquette_base & 0xFFFFFFFF)))
    out.append((OFF_DISTRIB, struct.pack("<I", 1)))
    return out


def ecritures_distrib_a_acheter(changes: dict[int, int]) -> list[tuple[int, bytes]]:
    """Mise à jour de l'octet `a_acheter` des entrées `index` -> octet (table déjà valide : un octet, écriture atomique)."""
    return [(OFF_DISTRIB_TABLE + TAILLE_DISTRIB * i + 16, bytes([v & 0xFF])) for i, v in sorted(changes.items())
            if 0 <= i < CAP_DISTRIB]


def etiquette_distrib(etiquette_base: int, index: int, ligne: int) -> int:
    """Location de la ligne `ligne` de la machine de rang `index` (convention partagée avec le jeu)."""
    return etiquette_base + DISTRIB_LIGNES * index + ligne


_texte_evt_avant_c1 = texte_evt


def texte_evt(e: dict) -> str:   # noqa: F811 - complète la version d'avant pour les évènements du lot C1
    if e["type"] == EVT_DISTRIBUTEUR:
        return (f"#{e['numero']} DISTRIBUTEUR carte={e['id']:#010x} point={e['valeur']:#010x} ligne={e['index']} "
                f"article={e['valeur2']:#010x} etiquette={e['etiquette']}")
    if e["type"] == EVT_DISTRIBUTEUR_VU:
        return (f"#{e['numero']} DISTRIBUTEUR_VU carte={e['id']:#010x} point={e['valeur']:#010x} "
                f"lignes={e['index']:#x} etiquette0={e['etiquette']}")
    return _texte_evt_avant_c1(e)


# ------------------------------------------------------------------------------------------------------------------
# V3, lot L1 : légendaires mélangés entre eux (docs/systemes/archipelago_v3_legendaires.md, archipelago_boite.md §51 ;
# src/archipelago/legendaires.cpp, zone ApLegendes de boite.h)
# ------------------------------------------------------------------------------------------------------------------
#  - fonction étendue 50 du patch (bit 18 de ApPnj::fonctions) et n° « client » 76 (jamais publié : un client d'avant,
#    qui n'écrit pas ApLegendes, refuse la graine : le tracker dirait « tel sceau donne tel légendaire » sans que le jeu
#    le fasse) : exigés par toute graine qui a l'option `legendaires_melanges` (clé `legendaires` de slot_data) ;
#  - zone (version et taille inchangées) : ApLegendes (0x40) à 0x23740 ; le client écrit `ident` (identifiant de
#    partie), `donne` (8 octets : sceau k -> légendaire donne[k], n° 322 + k -> n° 322 + donne[k]) et `valide` EN
#    DERNIER, en UN paquet de 16 octets, pour la sauvegarde LIÉE seulement ; `valide` = 0 retire la permutation ;
#  - le jeu réécrit le légendaire de chaque sceau (champ +4 de LEGEND_DATA_CONFIG) à chaque lecture de la table et à
#    chaque commande 0x3CDD, avec l'affectation EFFECTIVE (`legendes_effectif`) qui tient compte des sceaux déjà brisés.
FONCTION_LEGENDES = 50
FONCTION_CLIENT_L1 = 76
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_L1}
NOMS_FONCTIONS[FONCTION_LEGENDES] = "Légendaires mélangés entre eux (fonction 50)"
NOMS_FONCTIONS[FONCTION_CLIENT_L1] = "Légendaires mélangés entre eux (client trop ancien)"
OFF_LEGENDES, TAILLE_LEGENDES = 0x23740, 0x40
LEGENDES_PUBLIE = int.from_bytes(b"APL1", "little")
LEGENDES_COMPILE = 0x01
LEGENDES_VALIDE = int.from_bytes(b"LEG1", "little")
NB_SCEAUX = 8
MEDAILLE_LEGENDAIRE0 = 322                    # sceau k (octet +73) : légendaire n° 322 + k dans le jeu d'origine
LEG_ETAT_AUCUN, LEG_ETAT_PERMUTE, LEG_ETAT_ORIGINE, LEG_ETAT_TABLE, LEG_ETAT_DONNE = 0, 1, 2, 3, 4
LEG_ETATS = {LEG_ETAT_AUCUN: "table pas encore lue depuis le lancement",
             LEG_ETAT_PERMUTE: "permutation de la graine appliquée",
             LEG_ETAT_ORIGINE: "légendaires d'origine (hors vigueur : client absent, autre partie, sauvegarde non liée)",
             LEG_ETAT_TABLE: "table des sceaux inattendue : rien n'a été réécrit",
             LEG_ETAT_DONNE: "permutation écrite invalide : légendaires d'origine"}
LEGENDES_CHAMPS = {"publie": 0x00, "compile": 0x04, "ident": 0x08, "valide": 0x14, "etat": 0x18,
                   "applications": 0x24, "reecrits": 0x28, "refus": 0x2C, "masques": 0x30, "lectures": 0x34}
LEGENDES_OFF_DONNE, LEGENDES_OFF_EFFECTIF = 0x0C, 0x1C
# Sceaux de la ROM européenne (hachage du sceau, +0 ; légendaire d'origine, +4 : CHARA_PARAM des n° 322..329) : les
# mêmes constantes que SCEAU_H / LEGENDAIRE_H de legendaires.cpp (ap_boite_test.py --selftest les compare).
SCEAUX_H = (0x8865BE54, 0x116CEFEE, 0x666BDF78, 0xF80F4ADB, 0x8F087A4D, 0x16012BF7, 0x61061B61, 0xF1B906F0)
LEGENDAIRES_H = (0x97122416, 0x2FAE4373, 0x1870B341, 0x8B4F70B2, 0x0AC51CAF, 0xCB271688, 0xB2797BCA, 0x739B71ED)
P_SCEAUX_BRISES = 0x644                       # P + 0x644 : bit k = sceau k brisé (FUN_004155BC / FUN_00415C04)


def legendes_disponibles(h) -> bool:
    """Zone assez grande pour ApLegendes (un jeu d'avant le lot L1 n'y publie rien)."""
    return getattr(h, "taille_zone", 0) >= OFF_LEGENDES + TAILLE_LEGENDES


def legendes_compilees(b: bytes) -> bool:
    """Le jeu publie ApLegendes et la réécriture y est compilée (8 premiers octets de la zone)."""
    publie, compile_ = struct.unpack_from("<II", bytes(b).ljust(8, b"\0"), 0)
    return publie == LEGENDES_PUBLIE and bool(compile_ & LEGENDES_COMPILE)


def permutation_valide(donne) -> bool:
    d = list(donne)
    return len(d) == NB_SCEAUX and sorted(d) == list(range(NB_SCEAUX))


def donne_depuis_paires(paires) -> tuple[int, ...]:
    """`slot_data.legendaires` = [[n° du légendaire d'origine du sceau, n° donné], …] (8 paires) -> donne[k].
    ValueError si ce n'est pas une permutation des n° 322..329."""
    out = [None] * NB_SCEAUX
    for p in paires or ():
        s, l = int(p[0]) - MEDAILLE_LEGENDAIRE0, int(p[1]) - MEDAILLE_LEGENDAIRE0
        if not 0 <= s < NB_SCEAUX or not 0 <= l < NB_SCEAUX or out[s] is not None:
            raise ValueError(f"légendaires : paire invalide {p!r}")
        out[s] = l
    if None in out or not permutation_valide(out):
        raise ValueError(f"légendaires : pas une permutation des huit sceaux ({paires!r})")
    return tuple(out)


def ecritures_legendes(donne, ident: int) -> list[tuple[int, bytes]]:
    """Écriture du client (offset dans la zone d'échange) : `ident`, `donne` et `valide` contigus, en UN paquet de 16
    octets (jeu arrêté ; `valide` en dernier dans le paquet). `publie`, `compile` et les compteurs sont au jeu."""
    if not permutation_valide(donne):
        raise ValueError(f"légendaires : pas une permutation : {donne!r}")
    assert LEGENDES_OFF_DONNE == LEGENDES_CHAMPS["ident"] + 4 and LEGENDES_CHAMPS["valide"] == LEGENDES_OFF_DONNE + 8
    return [(OFF_LEGENDES + LEGENDES_CHAMPS["ident"],
             struct.pack("<I", ident & 0xFFFFFFFF) + bytes(donne) + struct.pack("<I", LEGENDES_VALIDE))]


def ecritures_legendes_retrait() -> list[tuple[int, bytes]]:
    """Retrait de la permutation (sauvegarde non liée) : `valide` = 0 seulement."""
    return [(OFF_LEGENDES + LEGENDES_CHAMPS["valide"], struct.pack("<I", 0))]


def dec_legendes(b: bytes) -> dict:
    """ApLegendes (0x40 octets à OFF_LEGENDES)."""
    b = bytes(b).ljust(TAILLE_LEGENDES, b"\0")
    d = {n: struct.unpack_from("<I", b, o)[0] for n, o in LEGENDES_CHAMPS.items()}
    d["donne"] = tuple(b[LEGENDES_OFF_DONNE:LEGENDES_OFF_DONNE + NB_SCEAUX])
    d["effectif"] = tuple(b[LEGENDES_OFF_EFFECTIF:LEGENDES_OFF_EFFECTIF + NB_SCEAUX])
    return d


def legendes_en_vigueur(b: bytes, ident_client: int, liee: bool, magic: bool = True):
    """Permutation EN VIGUEUR vue par le jeu (enVigueur de legendaires.cpp) : tuple `donne`, ou None (légendaires
    d'origine) ; LEG_ETAT_DONNE si `valide` est posé mais `donne` n'est pas une permutation."""
    d = dec_legendes(b)
    if not magic or d["valide"] != LEGENDES_VALIDE:
        return None
    if d["publie"] != LEGENDES_PUBLIE or not d["compile"] & LEGENDES_COMPILE:
        return None
    if ident_client and d["ident"] != ident_client:
        return None
    if not liee:
        return None
    return d["donne"] if permutation_valide(d["donne"]) else LEG_ETAT_DONNE


def legendes_effectif(donne, brises: int, amis: int) -> tuple[int, ...]:
    """Affectation EFFECTIVE (apLegendesEffectif de legendaires.cpp, même algorithme) : légendaire posé dans chaque
    sceau, d'après la permutation `donne`, les sceaux déjà brisés (bit k) et les légendaires déjà amis (bit l)."""
    donne = list(donne)
    out = [None] * NB_SCEAUX
    vus = 0
    for s in range(NB_SCEAUX):
        if vus >> s & 1:
            continue
        cycle, c = 0, s
        while True:
            cycle |= 1 << c
            c = donne[c]
            if c == s or cycle >> c & 1:
                break
        vus |= cycle
        dans = [k for k in range(NB_SCEAUX) if cycle >> k & 1]
        fait = pris = 0
        for k in dans:                                                    # (1)
            if not brises >> k & 1 and not amis >> donne[k] & 1:
                out[k], fait, pris = donne[k], fait | 1 << k, pris | 1 << donne[k]
        libres = [l for l in dans if not amis >> l & 1 and not pris >> l & 1]
        for k in dans:                                                    # (2)
            if fait >> k & 1 or brises >> k & 1:
                continue
            if not libres:
                break
            l = libres.pop(0)
            out[k], fait, pris = l, fait | 1 << k, pris | 1 << l
        for k in dans:                                                    # (3)
            if not fait >> k & 1 and not pris >> donne[k] & 1:
                out[k], fait, pris = donne[k], fait | 1 << k, pris | 1 << donne[k]
        reste = [l for l in dans if not pris >> l & 1]
        for k in dans:                                                    # (4)
            if not fait >> k & 1:
                l = reste.pop(0)
                out[k], fait, pris = l, fait | 1 << k, pris | 1 << l
    return tuple(out)


def texte_legendes(d: dict, noms=None) -> list[str]:
    """Lignes lisibles de l'état de ApLegendes (outil `ap_boite_test.py legendes`)."""
    nom = (lambda n: noms.get(n, f"n° {n}")) if noms else (lambda n: f"n° {n}")
    out = [f"compilée : {'oui' if d['publie'] == LEGENDES_PUBLIE and d['compile'] & LEGENDES_COMPILE else 'non'} ; "
           f"permutation {'écrite' if d['valide'] == LEGENDES_VALIDE else 'absente'} (partie {d['ident']:#010x})",
           f"dernier état : {LEG_ETATS.get(d['etat'], d['etat'])} ; lectures de la table {d['lectures']}, "
           f"applications {d['applications']}, champs réécrits {d['reecrits']}, refus {d['refus']}",
           f"sceaux brisés {d['masques'] & 0xFF:#04x}, légendaires amis {d['masques'] >> 8 & 0xFF:#04x}"]
    for k in range(NB_SCEAUX):
        e = d["effectif"][k]
        prevu = d["donne"][k] if d["valide"] == LEGENDES_VALIDE else k
        out.append(f"  sceau de {nom(MEDAILLE_LEGENDAIRE0 + k)} : prévu {nom(MEDAILLE_LEGENDAIRE0 + prevu)}, "
                   f"posé {nom(MEDAILLE_LEGENDAIRE0 + e) if e < NB_SCEAUX else '-'}")
    return out

# ------------------------------------------------------------------------------------------------------------------
# V3, lot B1 (docs/systemes/archipelago_v3_bingo_aleatoire.md ; archipelago_boite.md §52 ; voie.cpp, zone ApBingo de
# boite.h) : Bingo-kai (Crank-a-kai) ALÉATOIRE. Les lots Yo-kai des tables que le tirage dirigé ne vise pas sont
# remplacés, au tirage, par leur image dans une permutation σ calculée par le CLIENT depuis la ROM du joueur et la
# graine (`client/bingo.py`) ; le client l'écrit en cycles dans la zone ApBingo (0x240 octets à 0x15C80, trou de la
# zone v7 entre les sauvegardes des boss et ApMortDiag ; version et taille de zone inchangées).
#  - fonction étendue 51 (bit 19 de ApPnj::fonctions) ; option de CONFORT : aucune location n'en dépend, la graine
#    ne l'exige pas (ni `fonctions_exigees`, ni n° « client ») ; absente du jeu : avertissement (code 300 + 51 de
#    `options_absentes`), jamais de refus ;
#  - le client écrit `lots` (cycle après cycle), puis `ident`, `nombre`, `somme`, `fins` et `valide` EN DERNIER (un
#    paquet de 32 octets) ; `valide` = 0 retire le mélange (sauvegarde non liée) ; rien n'est écrit si rien ne change.
# Prochains libres (après ce lot) : fonction étendue 52 (prise par l'audit softlock, ci-dessous), n° « client » 77.
FONCTION_BINGO_MELANGE = 51
NOMS_FONCTIONS[FONCTION_BINGO_MELANGE] = "Bingo-kai aléatoire (fonction 51)"
OFF_BINGO, TAILLE_BINGO = 0x15C80, 0x240
BINGO_PUBLIE = int.from_bytes(b"APB1", "little")
BINGO_COMPILE = 0x01
BINGO_VALIDE = int.from_bytes(b"BIN1", "little")
CAP_BINGO = 128
BINGO_SOMME_PAS, BINGO_SOMME_PAS_FINS = 0x9E3779B9, 0x85EBCA6B
BINGO_OFF_LOTS = 0x40
BINGO_CHAMPS = {"publie": 0x00, "compile": 0x04, "ident": 0x08, "nombre": 0x0C, "somme": 0x10, "valide": 0x24,
                "tirages": 0x28, "melanges": 0x2C, "table": 0x30, "origine": 0x34, "image": 0x38, "refus": 0x3C}
BINGO_OFF_FINS = 0x14
BINGO_REFUS_AUCUN, BINGO_REFUS_GARDE, BINGO_REFUS_OPTION, BINGO_REFUS_TABLE = 0, 1, 2, 3
BINGO_REFUS_SOMME, BINGO_REFUS_OBJET, BINGO_REFUS_IMAGE, BINGO_REFUS_LISTE = 4, 5, 6, 7
BINGO_REFUS = {BINGO_REFUS_AUCUN: "lot remplacé par son image",
               BINGO_REFUS_GARDE: "lot du jeu gardé (objet, ou Yo-kai que le mélange ne déplace pas)",
               BINGO_REFUS_OPTION: "mélange pas en vigueur (client absent, autre partie, sauvegarde non liée)",
               BINGO_REFUS_TABLE: "table absente des données chargées, ou lot à plafond",
               BINGO_REFUS_SOMME: "somme des poids recalculée différente de celle du jeu",
               BINGO_REFUS_OBJET: "objet du tirage inattendu",
               BINGO_REFUS_IMAGE: "image inconnue des données, pas un Yo-kai, ou écartée par le rang de montre",
               BINGO_REFUS_LISTE: "table du client invalide (nombre, fin de cycle, somme de contrôle)"}
TABLE_PIECES_JEU = 0xFFFED2A7                 # crc32("prize1001") : table des pièces de jeu (AP_TABLE_PIECES_JEU)


def bingo_disponible(h) -> bool:
    """Zone assez grande pour ApBingo (toute zone v7+ ; un jeu d'avant le lot B1 n'y publie rien : lire `compile`)."""
    return getattr(h, "taille_zone", 0) >= OFF_BINGO + TAILLE_BINGO


def bingo_compile(b: bytes) -> bool:
    """Le jeu publie ApBingo et le mélange y est compilé (8 premiers octets de la zone)."""
    publie, compile_ = struct.unpack_from("<II", bytes(b).ljust(8, b"\0"), 0)
    return publie == BINGO_PUBLIE and bool(compile_ & BINGO_COMPILE)


def bingo_cycles(sigma: dict) -> tuple[list[int], list[bool]]:
    """Permutation {lot : image} -> (lots, fins) : les lots déplacés cycle après cycle (chaque cycle part de son plus
    petit lot, cycles dans l'ordre de ces plus petits lots), fins[i] vrai pour le dernier lot d'un cycle. Les points
    fixes ne sont pas écrits. ValueError si ce n'est pas une permutation de ses clés."""
    s = {int(k) & 0xFFFFFFFF: int(v) & 0xFFFFFFFF for k, v in dict(sigma).items()}
    if sorted(s.values()) != sorted(s):
        raise ValueError("Bingo-kai : σ n'est pas une permutation de ses lots")
    lots, fins, vus = [], [], set()
    for depart in sorted(s):
        if depart in vus or s[depart] == depart:
            vus.add(depart)
            continue
        x = depart
        while x not in vus:
            vus.add(x)
            lots.append(x)
            fins.append(False)
            x = s[x]
        fins[-1] = True
    if 0 in lots:
        raise ValueError("Bingo-kai : lot nul dans σ")
    return lots, fins


def bingo_sigma(lots, fins) -> dict:
    """Modèle de la lecture du jeu (imageBingo de voie.cpp) : {lot : image} des lots déplacés."""
    out, debut = {}, 0
    for i, x in enumerate(lots):
        if fins[i]:
            out[x] = lots[debut]
            debut = i + 1
        else:
            out[x] = lots[i + 1]
    return out


def bingo_mots_fins(fins) -> list[int]:
    mots = [0] * (CAP_BINGO // 32)
    for i, f in enumerate(fins):
        if f:
            mots[i >> 5] |= 1 << (i & 31)
    return mots


def bingo_somme(lots, mots_fins) -> int:
    """Contrôle de la table (apBingoSomme de voie.cpp) : nombre + somme des (lots[i] ^ (i + 1) * PAS) + somme des
    (fins[j] ^ (j + 1) * PAS_FINS), sur 32 bits."""
    s, k = len(lots), 0
    for x in lots:
        k = (k + BINGO_SOMME_PAS) & 0xFFFFFFFF
        s = (s + ((x & 0xFFFFFFFF) ^ k)) & 0xFFFFFFFF
    k = 0
    for m in mots_fins:
        k = (k + BINGO_SOMME_PAS_FINS) & 0xFFFFFFFF
        s = (s + ((m & 0xFFFFFFFF) ^ k)) & 0xFFFFFFFF
    return s


def ecritures_bingo(sigma: dict, ident: int) -> list[tuple[int, bytes]]:
    """Écritures du client (offset dans la zone d'échange) : `lots`, puis `ident`, `nombre`, `somme`, `fins` et
    `valide` contigus en UN paquet (`valide` en dernier). ValueError : σ vide, trop grand ou pas une permutation."""
    lots, fins = bingo_cycles(sigma)
    if not lots or len(lots) > CAP_BINGO:
        raise ValueError(f"Bingo-kai : {len(lots)} lots déplacés (1 à {CAP_BINGO} attendus)")
    mots = bingo_mots_fins(fins)
    assert BINGO_CHAMPS["nombre"] == BINGO_CHAMPS["ident"] + 4 and BINGO_CHAMPS["somme"] == BINGO_CHAMPS["nombre"] + 4
    assert BINGO_OFF_FINS == BINGO_CHAMPS["somme"] + 4 and BINGO_CHAMPS["valide"] == BINGO_OFF_FINS + 4 * len(mots)
    entete = struct.pack("<III", ident & 0xFFFFFFFF, len(lots), bingo_somme(lots, mots)) \
        + struct.pack("<%dI" % len(mots), *mots) + struct.pack("<I", BINGO_VALIDE)
    return [(OFF_BINGO + BINGO_OFF_LOTS, struct.pack("<%dI" % len(lots), *lots)),
            (OFF_BINGO + BINGO_CHAMPS["ident"], entete)]


def ecritures_bingo_retrait() -> list[tuple[int, bytes]]:
    """Retrait du mélange (sauvegarde non liée) : `valide` = 0 seulement."""
    return [(OFF_BINGO + BINGO_CHAMPS["valide"], struct.pack("<I", 0))]


def dec_bingo(b: bytes) -> dict:
    """ApBingo (0x240 octets à OFF_BINGO)."""
    b = bytes(b).ljust(TAILLE_BINGO, b"\0")
    d = {n: struct.unpack_from("<I", b, o)[0] for n, o in BINGO_CHAMPS.items()}
    d["fins"] = list(struct.unpack_from("<%dI" % (CAP_BINGO // 32), b, BINGO_OFF_FINS))
    d["lots"] = list(struct.unpack_from("<%dI" % CAP_BINGO, b, BINGO_OFF_LOTS))
    return d


def bingo_en_vigueur(b: bytes, ident_client: int, liee: bool, magic: bool = True) -> dict | None:
    """σ EN VIGUEUR vue par le jeu (bingoEnVigueur de voie.cpp) : {lot : image}, ou None (Bingo-kai d'origine) ;
    BINGO_REFUS_LISTE (entier) si `valide` est posé mais la table est mal formée."""
    d = dec_bingo(b)
    if not magic or d["valide"] != BINGO_VALIDE or d["publie"] != BINGO_PUBLIE or not d["compile"] & BINGO_COMPILE:
        return None
    if ident_client and d["ident"] != ident_client:
        return None
    if not liee:
        return None
    n = d["nombre"]
    fin = lambda i: bool(d["fins"][i >> 5] >> (i & 31) & 1)
    if not 1 <= n <= CAP_BINGO or not fin(n - 1) or bingo_somme(d["lots"][:n], d["fins"]) != d["somme"] \
            or 0 in d["lots"][:n]:
        return BINGO_REFUS_LISTE
    return bingo_sigma(d["lots"][:n], [fin(i) for i in range(n)])


def bingo_tirage(lots_table, r: int, rang: int = 0) -> int:
    """Modèle du choix du jeu (FUN_0040B81C, 0x0040BF08 et 0x0040C0B4) refait par melangeBingo : `lots_table` =
    [(lot, poids, rang exigé ou None si le lot est inconnu des données)], r = valeur tirée + 1 ; lot retenu (0 :
    aucun)."""
    total = 0
    for lot, poids, exige in lots_table:
        if exige is None or exige > rang:
            continue
        avant, total = total, total + poids
        if poids and avant <= r <= total:
            return lot
    return 0


def texte_bingo(d: dict, noms=None) -> list[str]:
    """Lignes lisibles de l'état de ApBingo (outil `ap_boite_test.py bingo-melange`) ; `noms` : {lot : texte}."""
    nom = (lambda x: noms.get(x, f"{x:#010x}")) if noms else (lambda x: f"{x:#010x}")
    compile_ = d["publie"] == BINGO_PUBLIE and d["compile"] & BINGO_COMPILE
    out = [f"compilé : {'oui' if compile_ else 'non'} ; mélange "
           f"{'écrit' if d['valide'] == BINGO_VALIDE else 'absent'} (partie {d['ident']:#010x}, {d['nombre']} lots)",
           f"tirages vus sur une table non dirigée {d['tirages']}, lots remplacés {d['melanges']}",
           f"dernier tirage : table {d['table']:#010x}, lot du jeu {nom(d['origine']) if d['origine'] else '-'}, "
           f"posé {nom(d['image']) if d['image'] else '-'} ; {BINGO_REFUS.get(d['refus'], d['refus'])}"]
    return out

# ------------------------------------------------------------------------------------------------------------------
# Audit softlock (décision de l'humain du 2026-10-26, docs/systemes/archipelago_logique_audit.md §3 G1-8 ; limites.cpp) :
# CHANTIER du Centre-ville sans attente de jours réels. Fonction étendue 52 (bit 20 de ApPnj::fonctions) : le flag
# global 584 (requêtes 45 et 58), posé à l'origine par la réinitialisation quotidienne deux ou trois jours RÉELS après
# l'appel du Tablo-blabla n° 9, est lu vrai dès que le flag 2111 (Tablo-blabla n° 9 appelé) est posé, sauvegarde liée.
# Rien à écrire pour le client ; exigée (avec 22) par toute graine générée depuis ce lot : un client d'avant vérifie
# déjà tout n° >= 32 dans ApPnj::fonctions (pas de n° « client »). Prochains libres : fonction étendue 53, n° « client » 77.
FONCTION_CHANTIER = 52
NOMS_FONCTIONS[FONCTION_CHANTIER] = "Chantier du Centre-ville sans attente de jours réels (fonction 52)"

# ------------------------------------------------------------------------------------------------------------------
# Mirapo de poche (décision de l'humain du 2026-10-27, docs/systemes/archipelago_mirapo_poche.md ; mirapo.cpp) : objet
# PROGRESSIF « Miroirs progressifs » (valeur `mirapo_de_poche` de `verrous_actifs`, qui active aussi `miroirs`) : le
# 1er exemplaire ouvre les miroirs (k = 53, zone ApVerrous2 : recu[53] = 0 / 1 comme avant), le 2e le Mirapo de poche
# (k = 61, zone ApVerrous3 : recu[61] = 1 à partir de MIRAPO_EXEMPLAIRES exemplaires reçus : entrée de `verrous_actifs`
# avec `exemplaires`). Commande dans le jeu : SELECT tenu ~0,5 s sur le terrain. N° « client » 77 (jamais publié) :
# un client d'avant écrirait recu[61] = 1 dès le premier exemplaire ; il refuse la graine sur ce n°.
# Prochains libres : fonction étendue 53, n° « client » 79 (78 : portails).
VERROU_MIRAPO = 61
MIRAPO_EXEMPLAIRES = 2
NOMS_VERROUS[VERROU_MIRAPO] = "Mirapo de poche"
FONCTION_CLIENT_MIRAPO = 77
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_MIRAPO}
NOMS_FONCTIONS[FONCTION_CLIENT_MIRAPO] = "Mirapo de poche (client trop ancien)"
MIRAPO_TOUCHE = 0x4                  # SELECT (bit HID 2)
# ap/mirapo-touche : le SDK replie SELECT sur START (pause) tant que cet octet vaut 0 (jeu d'origine, jamais écrit par
# le jeu) ; le mod le pose à 1 sur le terrain quand le Mirapo de poche agit (SELECT à part, pause sur START).
SDK_SELECT_SEPARE = 0x00828768
HID_START = 0x8
MIRAPO_IMAGES_TENUE = 15
MIRAPO_ATTENTE_MAX = 90
MIRAPO_DECLENCHEUR = 0x29F9462D      # RunTrigger des miroirs (common_trigger n° 48, type 13)
MIRAPO_TEXTE_HASH = 0xC3A8CD92       # crc32("ap_mirapo_fenetre")
FLAG_MIROIRS_SERVICE, FLAG_TEMPETE, FLAG_SIEGE, FLAG_PORTAIL_SALLE = 0xF874059B, 0x8BAAE62D, 0x8CA83098, 0x5AF7B8D2
QUETE_18, QUETE_120 = 0xF5D147C5, 0xD1E5F603
# Plages de phases refusées partout (bornes comprises) : tempête (7-40..7-70), tout le chapitre 10 (siège)
MIRAPO_PHASES_REFUSEES = ((70040, 70070), (100000, 109999))
# Zones refusées (ap/mirapo-phases, retour en jeu du 2026-11-06) : (première phase, dernière phase, NN) = cartes
# « t1NN… » refusées pendant la plage : fenêtres d'enfermement de la ROM (I14 de audit_logique.py) ; ailleurs, le
# joueur peut marcher jusqu'à un miroir du jeu (archipelago_mirapo_poche.md §4bis).
MIRAPO_ZONES_REFUSEES = ((20100, 20110, 106), (40110, 40270, 131), (60050, 60070, 131), (60050, 60070, 132))
MIRAPO_ARME_AUCUN, MIRAPO_ARME_ATTENTE, MIRAPO_ARME_EVENEMENT = 0, 1, 2
MIRAPO_MOTIFS = {0: "menu des miroirs demandé", 1: "moment pas sûr (dialogue, menu, scène, mort ou fenêtre en attente)",
                 2: "singleton absent", 3: "déjà armé", 4: "miroirs hors service (flag 17)",
                 5: "tempête ou siège (flags 62 / 63)", 6: "requête 18 (phases 1-2) ou 120 (phases 9-18)",
                 7: "phase refusée", 8: "salle de portail mystère (bit 2484)", 9: "carte refusée (donjon, passé…)",
                 10: "zone retenue par l'histoire (fenêtre d'enfermement)"}
MIRAPO_MOTIF_SERVICE = 4             # motifs >= : refus « de lieu » (fenêtre « ne répond pas ici »)
VERROUS3_MIRAPO = {"mirapo_etat": 0xEC, "mirapo_tenue": 0xED, "mirapo_motif": 0xEE, "mirapo_sauts": 0xEF,
                   "mirapo_age": 0xF0, "mirapo_menus": 0xF4, "mirapo_refus": 0xF6, "mirapo_departs": 0xF8}
# Miroir de départ (fix/mirapo-refus-jeu, bug vu en jeu le 2026-11-07 : message de refus du JEU) : la
# fonction de script WarpMenu demande 0x083E(100, PNJ) puis 0x083E(105) au loop du menu des miroirs ; 105 = « le PNJ
# est la clé d'un WARP_INFO » (loop + 0x864 posé par 100), sinon le label MIRAPO_LABEL_IMPOSSIBLE et sortie. Le Mirapo
# de poche passe un PNJ nul : la garde de 0x083E rend 1 à 105 pendant l'armement (apMirapoMenuDepart).
MIRAPO_VTABLE_MENU_WARP = 0x007FB1D4  # yw::ywCLoopMenuWarp
MIRAPO_SLOT_MENU_WARP = 0x00464C38    # slot +0x4C (sous-commandes 100..106, 200)
MIRAPO_CMD_DEPART = 105
MIRAPO_LABEL_IMPOSSIBLE = 0x460F2A37  # label du texte du jeu montré par WarpMenu quand 105 est faux


def mirapo_menu_depart(*, vtable: int, commande: int, arme: int) -> bool:
    """Modèle d'apMirapoMenuDepart (mirapo.cpp) : vrai = la garde de 0x083E rend 1 sans appeler le loop."""
    return commande == MIRAPO_CMD_DEPART and vtable == MIRAPO_VTABLE_MENU_WARP and arme != MIRAPO_ARME_AUCUN


def mirapo_warpmenu(pnj: int, cles_warp, *, arme: int = MIRAPO_ARME_AUCUN, accroche: bool = True) -> str:
    """Modèle du début de la fonction de script WarpMenu (WarpMenu.xq) : « impossible » (label MIRAPO_LABEL_IMPOSSIBLE,
    sortie) ou « menu ». 105 du jeu = PNJ égal à la clé d'un WARP_INFO (FUN_00465514 -> loop + 0x864) ; avec
    l'accroche, rendu vrai pendant l'armement."""
    depart = pnj in set(cles_warp)
    if accroche and mirapo_menu_depart(vtable=MIRAPO_VTABLE_MENU_WARP, commande=MIRAPO_CMD_DEPART, arme=arme):
        depart = True
    return "menu" if depart else "impossible"
# Largeur d'une ligne de la fenêtre d'information (type 0, messages d'histoire) : la ligne la plus large des messages
# d'histoire que le jeu y montre (sys_info_win_22, FR : 133 demi-unités, modèle `largeur`) ; une ligne de 161 débordait
# du cadre (Mirapo, vu en jeu le 2026-11-06). Borne prudente : jamais mesurée au-delà.
FENETRE_INFO_LARGEUR = 133
# Texte de la fenêtre de refus du Mirapo de poche (apPassageTexteLabel, verrous.cpp) : 2e ligne selon le motif lu dans
# ApVerrous3::mirapo_motif ; clé (motif, langue), motif 0 = repli (motif inattendu).
_MIRAPO_L1 = ("Le Mirapo de poche ne répond pas ici.", "The Pocket Mirapo won't respond here.")
_MIRAPO_L2 = {0: ("Pas pour l'instant.", "Not right now."),
              4: ("Les miroirs sont hors service.", "The mirrors are out of service."),
              5: ("Les miroirs sont fermés pour l'instant.", "The mirrors are closed for now."),
              6: ("Pas pendant cette requête.", "Not during this request."),
              7: ("Pas ici pour l'instant (histoire).", "Not here for now (story)."),
              8: ("Pas dans une salle de portail.", "Not inside a gate room."),
              9: ("Pas dans ce lieu (donjon, passé...).", "Not in this place (dungeon, past...)."),
              10: ("Pas ici pour l'instant (histoire).", "Not here for now (story).")}
TEXTES_MIRAPO = {(m, lg): _MIRAPO_L1[lg] + "\n" + t[lg] for m, t in _MIRAPO_L2.items() for lg in (0, 1)}


def texte_mirapo(motif: int, langue: int) -> bytes:
    """Texte de la fenêtre de refus du Mirapo de poche (apPassageTexteLabel) pour le motif du refus."""
    lg = 1 if langue == 1 else 0
    return TEXTES_MIRAPO.get((motif, lg), TEXTES_MIRAPO[(0, lg)]).encode("utf-8")


def recu_verrou3(k: int, nombre: int, exemplaires: dict) -> bool:
    """recu[k] écrit par le client dans ApVerrous3 : objet reçu au moins `exemplaires.get(k, 1)` fois (Mirapo de poche :
    2e exemplaire des « Miroirs progressifs »)."""
    return nombre >= exemplaires.get(k, 1)


def mirapo_carte_ordinaire(nom: str) -> bool:
    """Carte acceptée (carteOrdinaire) : « t1NN(g|i)NN » ; donjons « d », gares « s », passé « t2 »… refusés."""
    return len(nom) == 7 and nom[:2] == "t1" and nom[4] in "gi" and all(nom[i].isdigit() for i in (2, 3, 5, 6))


# Emplacements de carte du jeu (boite.h : AP_W_POIGNEE_CARTE…) : poignée {u16 index, u8 genre 2} à W + 0x397F8,
# emplacement W + 8 + index * 0x16A0 (4 au plus), +4 = POINTEUR vers le nom (char*, FUN_0066A960), pas le nom en place.
MIRAPO_W_POIGNEE_CARTE, MIRAPO_W_CARTES, MIRAPO_TAILLE_CARTE, MIRAPO_CAP_CARTES = 0x397F8, 8, 0x16A0, 4
MIRAPO_CARTE_NOM = 4


def mirapo_carte_memoire(lire_u32, lire_chaine, w: int):
    """Modèle de carteOrdinaire (mirapo.cpp) au niveau de la mémoire : nom de la carte courante si elle est ordinaire,
    None sinon. `lire_u32(adresse)`, `lire_chaine(adresse)` (chaîne C). Le nom se lit par le pointeur de
    l'emplacement + 4 (fix/mirapo-filtre-cartes : lu en place, toutes les cartes étaient refusées)."""
    poignee = lire_u32(w + MIRAPO_W_POIGNEE_CARTE)
    index = poignee & 0xFFFF
    if poignee == 0 or (poignee >> 16) & 0xFF != 2 or index >= MIRAPO_CAP_CARTES:
        return None
    pointeur = lire_u32(w + MIRAPO_W_CARTES + index * MIRAPO_TAILLE_CARTE + MIRAPO_CARTE_NOM)
    if pointeur == 0:
        return None
    nom = lire_chaine(pointeur)
    return nom if mirapo_carte_ordinaire(nom) else None


def mirapo_phase_refusee(phase: int) -> bool:
    return any(a <= phase <= b for a, b in MIRAPO_PHASES_REFUSEES)


def mirapo_zone_refusee(phase: int, carte: str) -> bool:
    """Carte ordinaire « t1NN… » d'une zone refusée à cette phase (zoneRefusee, mirapo.cpp)."""
    return any(a <= phase <= b and carte[1:4] == str(nn) for a, b, nn in MIRAPO_ZONES_REFUSEES)


def mirapo_motif(*, arme: int = MIRAPO_ARME_AUCUN, moment_sur: bool = True, singletons: bool = True,
                 flag17: bool = True, flag62: bool = False, flag63: bool = False, q18: int = 0, q120: int = 0,
                 phase: int = 50010, portail: bool = False, carte: str = "t101g00") -> int:
    """Modèle de motifRefus (mirapo.cpp), dans le même ordre : 0 = menu des miroirs demandé."""
    if arme != MIRAPO_ARME_AUCUN:
        return 3
    if not moment_sur:
        return 1
    if not singletons:
        return 2
    if not flag17:
        return 4
    if flag62 or flag63:
        return 5
    if q18 in (1, 2) or 9 <= q120 <= 18:
        return 6
    if mirapo_phase_refusee(phase):
        return 7
    if portail:
        return 8
    if not mirapo_carte_ordinaire(carte):
        return 9
    if mirapo_zone_refusee(phase, carte):
        return 10
    return 0


def sdk_touches(brutes: int, select_separe: bool) -> int:
    """Touches rendues par le lecteur du SDK (FUN_0015B0DC -> FUN_001747BC) : sans l'octet SDK_SELECT_SEPARE, SELECT
    est rendu comme START (bit 0x4 effacé, 0x8 posé)."""
    if select_separe or not brutes & MIRAPO_TOUCHE:
        return brutes
    return (brutes & ~MIRAPO_TOUCHE) | HID_START


def mirapo_select_suivant(pose: bool, voulu: bool, touches: int) -> bool:
    """Modèle de suivreSelect (mirapo.cpp) : nouvel état de l'octet SDK_SELECT_SEPARE (posé ou non par le mod).
    `voulu` = Mirapo de poche en vigueur ET terrain ; hors terrain, l'octet n'est rendu qu'une fois SELECT relâché."""
    if voulu:
        return True
    return pose and bool(touches & MIRAPO_TOUCHE)


def mirapo_en_vigueur(b3: bytes, liee: bool, ident_client: int = 0) -> bool:
    """Le Mirapo de poche agit (apVerrou2Progressif(61) et recu[61] non nul) : zone publiée, bit compilé et actif,
    zone de la partie du client, sauvegarde liée, objet reçu (2 exemplaires)."""
    return liee and verrou3_en_vigueur(b3, VERROU_MIRAPO, ident_client) \
        and bool(dec_verrous3(b3)["recu"][VERROU_MIRAPO - VERROU3_BASE])
# Donjon des portails et récompense des portails (ap/portails-donjon, décisions de l'humain du 2026-10-27 ;
# docs/systemes/archipelago_portails_donjon.md, boîte §55). Numéros pris APRÈS ceux réservés pour ap/mirapo-poche
# (verrou k = 61, n° « client » 77, fonction étendue 53).
#  - Clés du donjon : verrous k = 62..66 de ApVerrous3 (le client les écrit déjà génériquement : tout k >= 56 de
#    `slot_data.verrous_actifs`, n° « client » 68 exigé par la graine) : clé reçue -> octet global du compteur de sa
#    porte relevé au besoin par le jeu (donjon.cpp). Aucun code de plus côté client.
#  - Récompense : zone ApPortails (0x100 octets) à 0x4300 (ancienne table des dons de script, libre en zone v10) ;
#    `compile` (J, +0) publié ; le client écrit ident (+4), nombre (+0xC), base (+0xE), liaison (+0x10), la liste
#    (+0x20, 28 entrées {u32 objet, u16 quantité, u16 0}), puis `sequence` (+8) EN DERNIER, pour la sauvegarde liée ;
#    sequence = 0 retire la liste. Évènement COFFRE à drapeau EVT_COFFRE_PORTAIL : étiquette = rang absolu suivant
#    (mémoire `base` du client, par partie et clé de liaison). N° « client » 78 exigé par une graine qui a la liste
#    (`slot_data.portails_recompenses`) : un client d'avant ne l'écrirait pas.
VERROU_DONJON_1, VERROU_DONJON_2, VERROU_DONJON_3, VERROU_DONJON_4, VERROU_DONJON_5 = 62, 63, 64, 65, 66
VERROUS_DONJON = (VERROU_DONJON_1, VERROU_DONJON_2, VERROU_DONJON_3, VERROU_DONJON_4, VERROU_DONJON_5)
# (porte, besoin, octet global du compteur, index de l'octet) [C : GATE_NEED_BALL_INFO, flag_config]
PORTES_DONJON = ((0xBF496FF5, 5, 0xE4CE9C72, 371), (0x740E9813, 10, 0x93C9ACE4, 372), (0x6A786D4B, 20, 0x0AC0FD5E, 373),
                 (0xF41CF8E8, 30, 0x7DC7CDC8, 374), (0x41553E88, 40, 0xE3A3586B, 375))
FONCTION_CLIENT_P1 = 78
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_P1}
NOMS_FONCTIONS[FONCTION_CLIENT_P1] = "Récompense des portails mystères (client trop ancien)"
OFF_PORTAILS, TAILLE_PORTAILS, CAP_PORTAILS = 0x4300, 0x100, 28
PORTAILS_PUBLIE, PORTAILS_COMPILE, PORTAILS_DONJON = 0x80000000, 0x01, 0x02
PORTAILS_TBOX = 0x1632876D
EVT_COFFRE_PORTAIL = 0x08
PORTAILS_REFUS = {0: "remplacé", 1: "liste absente ou incomplète", 2: "autre partie ou sauvegarde non liée",
                  3: "liste d'une autre sauvegarde (clé de liaison)", 4: "entrée vide"}


def portails_compile(b: bytes) -> bool:
    """La zone ApPortails est publiée et la récompense compilée (4 premiers octets au moins)."""
    c = struct.unpack_from("<I", b, 0)[0]
    return bool(c & PORTAILS_PUBLIE) and bool(c & PORTAILS_COMPILE)


def ecritures_portails(entrees, ident: int, liaison: int, base: int, sequence: int) -> list[tuple[int, bytes]]:
    """Écritures (décalage dans la zone, octets) de la liste : [+4, +0x20 + 8 n) d'abord, `sequence` (+8) EN DERNIER.
    `entrees` = [(objet, quantité)] (28 au plus, liste de la graine tronquée)."""
    e = list(entrees)[:CAP_PORTAILS]
    if not e or not sequence:
        raise ValueError("liste vide ou séquence nulle")
    corps = struct.pack("<IIHHH", ident & 0xFFFFFFFF, 0, len(e), min(int(base), 0xFFFF), liaison & 0xFFFF)
    table = b"".join(struct.pack("<IHH", int(o) & 0xFFFFFFFF, max(1, min(99, int(q))), 0) for o, q in e)
    return [(OFF_PORTAILS + 4, corps[:4]), (OFF_PORTAILS + 0xC, corps[8:]),
            (OFF_PORTAILS + 0x20, table), (OFF_PORTAILS + 8, struct.pack("<I", sequence & 0xFFFFFFFF))]


def ecritures_portails_retrait() -> list[tuple[int, bytes]]:
    return [(OFF_PORTAILS + 8, b"\0" * 4)]


def dec_portails(b: bytes) -> dict:
    """ApPortails (0x100 octets à OFF_PORTAILS)."""
    d = dict(zip(("compile", "ident", "sequence", "nombre", "base", "liaison", "curseur", "liaison_j", "tirages",
                  "globes", "refus", "refus_nombre"), struct.unpack_from("<IIIHHHHHHHBB", b, 0)))
    d["entrees"] = [struct.unpack_from("<IH", b, 0x20 + 8 * i) for i in range(CAP_PORTAILS)] if len(b) >= 0x100 else []
    return d


def portails_tirage(d: dict, tbox: int, ident_partie: int, liaison_courante: int, liee: bool = True):
    """Modèle de apPortailsCoffre : (objet, quantité, rang suivant) si le coffre est remplacé, sinon (None, motif).
    Ne modifie pas `d` (le curseur rendu est le rang suivant)."""
    if tbox != PORTAILS_TBOX:
        return None, None
    n = d["nombre"]
    if d["sequence"] == 0 or not 1 <= n <= CAP_PORTAILS:
        return None, 1
    if ident_partie == 0 or d["ident"] != ident_partie or not liee:
        return None, 2
    if d["liaison"] != liaison_courante:
        return None, 3
    curseur = d["curseur"] if d["liaison_j"] == liaison_courante else 0
    rang = max(curseur, d["base"])
    objet, quantite = d["entrees"][rang % n]
    if objet == 0 or quantite == 0:
        return None, 4
    return (objet, quantite, min(rang + 1, 0xFFFF)), 0
VERROUS3_COMPILES_DEFAUT = 0x3F | (0x1F << (VERROU_DONJON_1 - VERROU3_BASE))   # 56..60 (lots 7, 8), 61 (Mirapo), 62..66 (donjon) = 0x7FF
NOMS_VERROUS_DONJON = {k: f"Clé du donjon des portails {i + 1}" for i, k in enumerate(VERROUS_DONJON)}


# Terrains de Ψ Blasters (ap/blasters-terrains-jeu, demande de l'humain du 2026-11-04 ;
# docs/systemes/archipelago_v3_blasters_terrains.md) : un objet AP par terrain À CONDITION de déblocage, verrou
# k = VERROU_BLASTERS_BASE + n de ApVerrous3 (n = 2..10, 13 ; k = 68..76, 79 ; 67 réservé, jamais compilé) ; k = 77,
# 78 (Jiganyan, Komak : terrains d'AUTRES ÉDITIONS, masques de version 1 / 2) compilés avec l'option étendue 35.
# Zone inchangée : le client les écrit déjà génériquement (tout k >= 56 de `slot_data.verrous_actifs`, n° « client »
# 68 exigé par la graine, refus si le bit n'est pas dans `compiles`). Le jeu (blasters.cpp) : en vigueur, terrain
# débloqué si et seulement si l'objet est reçu, au menu ET pour le bit « terrain fini » ; hors vigueur, jeu d'origine.
# Noms saisis à la main (boss du terrain ; FR : orgetime_true_matching_text, EN : archipelago_v3_blasters.md §1.4).
VERROU_BLASTERS_BASE = 66
TERRAINS_BLASTERS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 13)
TERRAINS_AUTRES_EDITIONS = (11, 12)
VERROUS_BLASTERS = tuple(VERROU_BLASTERS_BASE + n for n in sorted(TERRAINS_BLASTERS + TERRAINS_AUTRES_EDITIONS))
BLASTERS_RETOUR_FINI = 0x0040B358     # FUN_0040AD40 : retour de l'appel de la condition (relais de FUN_00415380)
NOMS_TERRAINS_BLASTERS = {             # n : (FR, EN)
    0: ("Ruée de triple boss", "Triple Boss Rush"), 1: ("Gargaros", "Gargaros"), 2: ("Crocho", "Sproink"),
    3: ("Triptyk", "Slimamander"), 4: ("Carpitaine", "SV Snaggerjag"), 5: ("Ogralos", "Ogralus"),
    6: ("McKraken", "McKraken"), 7: ("Démophage", "Demuncher"), 8: ("Orqanos", "Orcanos"),
    9: ("Lady Perpétua", "Dame Dedtime"), 10: ("Potofeu", "Wobblewok"), 11: ("Jiganyan", "Rubeus J"),
    12: ("Komak", "Hardy Hound"), 13: ("Domniscian", "Hinozall")}
NOMS_VERROUS_BLASTERS = {VERROU_BLASTERS_BASE + n: f"Terrain : {NOMS_TERRAINS_BLASTERS[n][0]}" for n in TERRAINS_BLASTERS}
VERROUS3_COMPILES_DEFAUT |= sum(1 << (k - VERROU3_BASE) for k in VERROUS_BLASTERS)   # = 0xFFF7FF
# Option étendue 35 « terrains de Ψ Blasters d'autres éditions » (bit 3 de ApPieces::options / options_compilees) :
# posée par le client pour une graine qui la demande (lot APWorld suivant : n° « client » à prendre, 80) ; en vigueur,
# le menu ajoute le bit de l'édition locale (VERSION_EDITION_LOCALE = 2 : octet 0x00860960 + 0x4C58 lu dans les états
# d'Azahar) au masque des terrains 11 et 12 dans sa copie de la table.
OPTION3_EDITIONS = 35
PIECES_OPTION_EDITIONS = 0x00000008
PIECES_OPTIONS_COMPILEES |= PIECES_OPTION_EDITIONS
VERSION_EDITION_LOCALE = 2
MASQUES_TERRAINS_BLASTERS = (7, 7, 4, 5, 6, 7, 4, 4, 7, 4, 4, 1, 2, 4)   # +7 de ORGE_STAGE [C, orge_time_stage]
# ap/blasters-terrains-apworld (archipelago_v3_blasters_terrains.md §10) : noms des douze verrous dans les messages
# « Verrous manquants » (11 et 12 compris : verrous des terrains d'autres éditions, compilés avec l'option 35) ;
# option étendue 35 posée par ce client pour une graine à `slot_data.blasters_autres_editions` (bit 3 du mot d'options
# de ApPieces, écrit avec les bits 0..2) ; absente du jeu (zone non publiée ou bit non compilé) : REFUS (code 135 de
# `verrous_manquants`, des locations en dépendent). N° « client » 80, jamais publié par le jeu : un client d'avant
# accepterait la graine sans poser le bit ; suivant libre : 81.
NOMS_VERROUS_BLASTERS.update({VERROU_BLASTERS_BASE + n: f"Terrain : {NOMS_TERRAINS_BLASTERS[n][0]}"
                              for n in TERRAINS_AUTRES_EDITIONS})
NOMS_VERROUS.update(NOMS_VERROUS_BLASTERS)
FONCTION_CLIENT_EDITIONS = 80
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_EDITIONS}
NOMS_FONCTIONS[FONCTION_CLIENT_EDITIONS] = "Ψ Blasters : terrains d'autres éditions (client trop ancien)"
NOMS_OPTIONS3[OPTION3_EDITIONS] = "Ψ Blasters : terrains d'autres éditions jouables seul (Jiganyan, Komak)"
EDITIONS_OPTION_MANQUANTE = OPTION2_MANQUANTE_BASE + OPTION3_EDITIONS
NOMS_OPTIONS_MANQUANTES[EDITIONS_OPTION_MANQUANTE] = \
    "Ψ Blasters : terrains d'autres éditions jouables seul (option étendue 35)"


def blasters_terrain_verdict(b3: bytes, n: int, natif: bool, liee: bool, ident_client: int = 0) -> bool:
    """Modèle du verdict de blasters.cpp (verdict()) pour le terrain n : `natif` = condition du jeu. Terrain sans
    objet (0, 1, 11, 12) ou verrou hors vigueur (zone non publiée, bit non compilé ou non actif, autre partie,
    sauvegarde non liée) : `natif` ; en vigueur : objet reçu (recu[k - 56] non nul)."""
    if n not in TERRAINS_BLASTERS + TERRAINS_AUTRES_EDITIONS:
        return natif
    k = VERROU_BLASTERS_BASE + n
    if not (liee and verrou3_en_vigueur(b3, k, ident_client)):
        return natif
    return bool(dec_verrous3(b3)["recu"][k - VERROU3_BASE])


def blasters_terrain_liste(bp_pieces: bytes, n: int, liee: bool, ident_client: int = 0,
                           version: int = VERSION_EDITION_LOCALE) -> tuple[bool, int]:
    """Modèle du test de masque de FUN_00530D98 (blasters.cpp) : (terrain évalué et listé ?, masque laissé dans la
    copie de la table du menu). Terrain d'une autre édition (11, 12) avec l'option étendue 35 en vigueur : masque
    élargi au bit de l'édition locale ; sinon masque d'origine."""
    m = MASQUES_TERRAINS_BLASTERS[n]
    bit = 1 << version
    if m & bit:
        return True, m
    if n in TERRAINS_AUTRES_EDITIONS and option3_active(bp_pieces, PIECES_OPTION_EDITIONS, liee, ident_client):
        return True, m | bit
    return False, m


# ------------------------------------------------------------------------------------------------
# V3 : PIÈGES (« traps ») d'Archipelago (src/archipelago/pieges.cpp ; zone ApPieges de boite.h ;
# docs/systemes/archipelago_boite.md §57, docs/systemes/archipelago_v3_pieges.md). Protocole seulement : le client
# (dépôt type 4, mémoire « reçus pas faits » par partie, reprise au lancement, bandeaux) est `client/pieges_suivi.py`.
#  - un piège est un DON de la file de dons existante : type TYPE_DON_PIEGE, `hash` = n° du piège (PIEGE_*), quantité 1,
#    rang = numéro du don (le compteur de la sauvegarde avance : le rejeu du serveur ne le redonne pas) ;
#  - le jeu journalise EVT_PIEGE_RECU (id = n°, valeur = rang, valeur2 = 0 don / 1 reprise) puis EVT_PIEGE_FAIT
#    (drapeaux = PIEGE_ISSUE_*, id = n°, valeur = rang, valeur2 = détail : argent retiré en centimes, rencontre du
#    combat surprise, 0) ; un rang déjà connu du jeu (file ou derniers finis) n'est ni rejournalisé ni refait ;
#  - VARIANTE B (mémoire du client) : par partie, rangs reçus (PIEGE_RECU, ou don de type 4 validé) moins rangs finis
#    (PIEGE_FAIT, toute issue) ; au lancement (sauvegarde liée), le client redonne ces rangs par la REPRISE :
#    ecritures_reprise(entrées, seq) (7 entrées au plus, `reprise_seq` EN DERNIER), puis attend
#    ApPieges::reprise_vue == seq avant la reprise suivante. Le jeu n'accepte qu'un rang <= compteur de dons de la
#    sauvegarde (au-delà, la file de dons le redonnera) et écarte un rang déjà connu : jamais de double exécution, même si
#    le client renvoie un rang dont il n'a pas encore lu le PIEGE_FAIT ;
#  - fonction étendue 53 (bit 21 de ApPnj::fonctions) = le jeu sait recevoir des pièges ; bit n de ApPieges::compile =
#    piège n compilé (un piège absent est écarté avec PIEGE_ISSUE_ABSENT : le client avertit, ne refuse pas) ;
#  - n° « client » 79 (jamais publié par le jeu) : exigé par toute graine à pièges (refus des clients d'avant).
TYPE_DON_PIEGE = 4
EVT_PIEGE_RECU, EVT_PIEGE_FAIT = 12, 13
FONCTION_PIEGES = 53
FONCTION_CLIENT_PIEGES = 79
NOMS_FONCTIONS[FONCTION_PIEGES] = "Pièges d'Archipelago (fonction 53)"
NOMS_FONCTIONS[FONCTION_CLIENT_PIEGES] = "Pièges d'Archipelago (client trop ancien)"
# (lot 4 des pièges, client : 79 est dans FONCTIONS_CLIENT_V3 depuis que ce client dépose les pièges en type 4, tient
# leur mémoire par partie et les reprend au lancement : `client/pieges_suivi.py`)
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_PIEGES}
NOMS_DON[TYPE_DON_PIEGE] = "piege"
OFF_PIEGES, TAILLE_PIEGES = 0x1FF40, 0xC0
PIEGES_PUBLIE, PIEGES_MELANGE_ROUE = 0x80000000, 0x100
(PIEGE_COMBAT, PIEGE_ARGENT, PIEGE_MONTRE, PIEGE_PLUIE, PIEGE_PV, PIEGE_ROUE, PIEGE_ENVOUTEMENT,
 PIEGE_ONI) = range(8)
NB_PIEGES = 8
NOMS_PIEGES = {PIEGE_COMBAT: "combat surprise", PIEGE_ARGENT: "perte d'argent", PIEGE_MONTRE: "montre brouillée",
               PIEGE_PLUIE: "pluie", PIEGE_PV: "PV à moitié", PIEGE_ROUE: "équipe mélangée",
               PIEGE_ENVOUTEMENT: "envoûtement", PIEGE_ONI: "terreur (Oni)"}
# « au prochain combat » (bandeau du client) ; l'envoûtement (6) est abandonné : plus aucune graine ne le contient
PIEGES_DE_COMBAT = frozenset({PIEGE_PV, PIEGE_ROUE})
# 0..5 et 7 (Oni, ap/v3-pieges-roue-oni) ; envoûtement (6) jamais compilé ; le bit 0x100 (PIEGES_MELANGE_ROUE : le
# piège 5 fait tourner la roue) est hors de `pieges_compiles` (octet bas seulement)
PIEGES_COMPILES_DEFAUT = 0xBF
CAP_PIEGES_FILE, CAP_PIEGES_FAITS, CAP_PIEGES_REPRISE = 16, 11, 7
PIEGE_ATTENTE_COMBAT, PIEGE_REESSAI_COMBAT, PIEGE_COMMENCE = 600, 30, 0xFFFF
PIEGE_RELECTURE_PV, PIEGE_REECRITURES_PV = 60, 8
PIEGE_ISSUE_FAIT, PIEGE_ISSUE_PLEINE, PIEGE_ISSUE_ABSENT = 0, 1, 2
PIEGES_ISSUES = {PIEGE_ISSUE_FAIT: "fait", PIEGE_ISSUE_PLEINE: "perdu (file pleine)",
                 PIEGE_ISSUE_ABSENT: "écarté (absent du jeu)"}
PIEGES_REFUS = {0: "aucun", 1: "mort DeathLink en attente", 2: "terrain pas libre", 3: "répit de 30 s",
                4: "ni point de loupe visé par le radar, ni tirage sur la carte", 5: "combat refusé ou jamais commencé",
                6: "temps imposé par l'histoire", 7: "combat de script (ni errant, ni loupe)",
                8: "personne au-dessus de la moitié des PV, ou PV sans cesse réécrits",
                9: "pas de partie liée", 10: "Oni introuvable, modifié ou équipe vide",
                11: "tutoriels de combat pas finis",
                12: "en ligne, règle 3/15 ou 3/18, ou issue décidée par les règles",
                13: "combat scénarisé (flag temporaire 99)"}
PIEGES_COMBAT_ETATS = {0: "pas encore créé", 1: "rien à faire ou refusé", 2: "fait", 3: "PV écrits, relecture"}
PIEGE_RETOUR_ERRANT = 0x0049851C          # retour de l'appel de FUN_00415058 par FUN_004984E4
PIEGE_DUREE_TERRAIN, PIEGE_DUREE_MAX, PIEGE_DUREE_ROUE, PIEGE_REPIT = 9000, 27000, 900, 900
PIEGE_FLAG_RADAR, PIEGE_RETOUR_RADAR = 0x9B0A23F4, 0x0048EF8C
PIEGE_OCTET_METEO, PIEGE_PLUIE_VALEUR = 0x97580970, 5


def pieges_entree(rang: int, piege: int) -> int:
    """Mot d'une entrée de file / reprise : (rang << 8) | n°."""
    if not 0 < rang <= 0xFFFFFF or not 0 <= piege < 256:
        raise ValueError("rang ou n° de piège hors bornes")
    return (rang << 8) | piege


def dec_pieges(b: bytes) -> dict:
    """ApPieges (0xC0 octets à OFF_PIEGES)."""
    d = dict(zip(("compile", "ident", "recus", "faits", "perdus", "reprises", "reprise_vue", "montre", "pluie",
                  "roue", "repit", "combat", "refus", "refus_piege", "dernier", "rencontre", "attente", "nombre",
                  "faits_n", "refus_rencontre", "images_combat"),
                 struct.unpack_from("<IIHHHHIHHHHBBBBIHBBII", b, 0)))
    d["file"] = [(e >> 8, e & 0xFF) for e in struct.unpack_from("<16I", b, 0x30)][:min(d["nombre"], 16)]
    d["derniers"] = [(e >> 8, e & 0xFF) for e in struct.unpack_from("<11I", b, 0x70) if e]
    d["pv_attente"], d["reessai"] = struct.unpack_from("<HH", b, 0x9C)
    d["reprise_seq"] = struct.unpack_from("<I", b, 0xA0)[0]
    d["reprise"] = [(e >> 8, e & 0xFF) for e in struct.unpack_from("<7I", b, 0xA4) if e]
    return d


# Pièges après la victoire (ap/pieges-apres-victoire, archipelago_v3_pieges.md §14) : CLIENT seul, aucun n° ni bit
# nouveau. Une fois l'objectif atteint, le client dépose les pièges en « type 0 » (le jeu les ignore, compteur avancé)
# et VIDE la file du jeu par la voie de pieges.cpp qui existe depuis le lot 0 : il écrit ApPieges::ident = 0
# (≠ identifiant de partie) ; à l'image suivante, apPiegesImage appelle vider() (file, derniers finis, montre, pluie,
# roue, répit, Oni remis, roue_phase), comme pour une autre partie. Seulement HORS combat et hors séquence en cours
# (`pieges_purge_motif`), jeu arrêté entre la lecture et l'écriture.
OFF_PIEGES_IDENT = OFF_PIEGES + 0x04
TAILLE_PIEGES_ETAT = 0x30                     # compile .. images_combat (avant la file)
OFF_PIEGES_PRIVE, OFF_PRIVE_ROUE_PHASE, OFF_PRIVE_ONI_PHASE = 0x110C0, 0x00, 0x0C   # ApPiegesPrive (boite.h)
PURGE_RIEN, PURGE_OK, PURGE_COMBAT, PURGE_SEQUENCE = 0, 1, 2, 3


def pieges_purge_motif(etat: bytes, prive: bytes) -> int:
    """`etat` = 0x30 premiers octets d'ApPieges, `prive` = au moins 0x10 octets d'ApPiegesPrive : PURGE_RIEN (file
    vide, ni montre, ni pluie, ni roue), PURGE_COMBAT (combat en cours : images_combat, combat surprise demandé ou
    commencé), PURGE_SEQUENCE (rotation de la roue ou combat d'Oni en cours), sinon PURGE_OK."""
    montre, pluie, roue = struct.unpack_from("<HHH", etat, 0x14)
    rencontre, attente, nombre = struct.unpack_from("<IHB", etat, 0x20)
    images_combat = struct.unpack_from("<I", etat, 0x2C)[0]
    if not nombre and not montre and not pluie and not roue:
        return PURGE_RIEN
    if images_combat or rencontre or attente or roue:
        return PURGE_COMBAT
    if prive[OFF_PRIVE_ROUE_PHASE] or prive[OFF_PRIVE_ONI_PHASE]:
        return PURGE_SEQUENCE
    return PURGE_OK


def pieges_compiles(b: bytes) -> int:
    """Masque des pièges compilés (0 si la zone n'est pas publiée)."""
    c = struct.unpack_from("<I", b, 0)[0]
    return c & 0xFF if c & PIEGES_PUBLIE else 0


def ecritures_reprise(entrees, seq: int) -> list[tuple[int, bytes]]:
    """Écritures de la reprise : 7 entrées (rang, n°) au plus, places vides à 0, puis `reprise_seq` EN DERNIER."""
    e = list(entrees)
    if len(e) > CAP_PIEGES_REPRISE or not seq:
        raise ValueError("reprise trop longue ou séquence nulle")
    mots = [pieges_entree(r, p) for r, p in e] + [0] * (CAP_PIEGES_REPRISE - len(e))
    return [(OFF_PIEGES + 0xA4, struct.pack("<7I", *mots)), (OFF_PIEGES + 0xA0, struct.pack("<I", seq & 0xFFFFFFFF))]


def pieges_a_reprendre(evenements) -> list[tuple[int, int]]:
    """Mémoire du client (variante B) : (rang, n°) reçus et pas finis, d'après les évènements du journal
    [(type, rang, n°)], dans l'ordre des rangs."""
    recus, finis = {}, set()
    for t, rang, piege in evenements:
        if t == EVT_PIEGE_RECU:
            recus[rang] = piege
        elif t == EVT_PIEGE_FAIT:
            finis.add(rang)
    return sorted((r, p) for r, p in recus.items() if r not in finis)


class ModelePieges:
    """Modèle de la file des pièges de pieges.cpp (réception, reprise, fin) pour les tests hors ligne."""

    def __init__(self, compile_: int = PIEGES_COMPILES_DEFAUT):
        self.compile = compile_
        self.file: list[tuple[int, int]] = []
        self.derniers: list[tuple[int, int]] = []
        self.journal: list[tuple[int, int, int, int]] = []    # (type, issue, rang, n°)
        self.reprise_vue = 0

    def connu(self, rang: int) -> bool:
        return any(r == rang for r, _p in self.file) or any(r == rang for r, _p in self.derniers)

    def _fini(self, rang: int, piege: int, issue: int) -> None:
        self.derniers = (self.derniers + [(rang, piege)])[-CAP_PIEGES_FAITS:]
        self.journal.append((EVT_PIEGE_FAIT, issue, rang, piege))

    def ajouter(self, piege: int, rang: int, origine: int = 0) -> None:
        if rang == 0 or rang > 0xFFFFFF or self.connu(rang):
            return
        if piege >= NB_PIEGES or not self.compile & (1 << piege):
            self._fini(rang, piege, PIEGE_ISSUE_ABSENT)
        elif len(self.file) >= CAP_PIEGES_FILE:
            self._fini(rang, piege, PIEGE_ISSUE_PLEINE)
        else:
            self.file.append((rang, piege))
            self.journal.append((EVT_PIEGE_RECU, origine, rang, piege))

    def vider(self) -> None:
        """vider() de pieges.cpp (ApPieges::ident différent de l'identifiant de partie) : file et derniers finis
        effacés, sans évènement ; `reprise_vue` gardé."""
        self.file, self.derniers = [], []

    def reprise(self, entrees, seq: int, compteur: int) -> None:
        if seq == 0 or seq == self.reprise_vue:
            return
        for rang, piege in entrees:
            if rang <= compteur:
                self.ajouter(piege, rang, 1)
        self.reprise_vue = seq

    def faire(self, piege: int) -> int | None:
        """Le plus ancien piège n° `piege` est fait ; rend son rang (None s'il n'y en a pas)."""
        for i, (rang, p) in enumerate(self.file):
            if p == piege:
                del self.file[i]
                self._fini(rang, p, PIEGE_ISSUE_FAIT)
                return rang
        return None


def pieges_effet_applicable(ident_zone: int, ident_partie: int, ident_sauvegarde: int | None) -> bool:
    """effetApplicable de pieges.cpp : montre et pluie n'agissent que sur la sauvegarde liée de la partie de la zone.
    `ident_sauvegarde` : P + 0x3BC, None sans P ; ident_partie 0 = client sans identifiant, pas de contrôle
    (apSauvegardeLiee)."""
    return ident_zone == ident_partie and (ident_partie == 0 or ident_sauvegarde == ident_partie)


class ModeleEffetsPieges:
    """Modèle des effets en cours de pieges.cpp : filtres apPiegesRadar / apPiegesMeteo et décompte d'apPiegesImage."""

    def __init__(self, ident: int):
        self.ident_zone = self.ident_partie = self.ident_sauvegarde = ident
        self.montre = self.pluie = 0

    def applicable(self) -> bool:
        return pieges_effet_applicable(self.ident_zone, self.ident_partie, self.ident_sauvegarde)

    def radar(self, brut: bool, retour: int = PIEGE_RETOUR_RADAR) -> bool:
        if brut or retour != PIEGE_RETOUR_RADAR:
            return brut
        return self.montre != 0 and self.applicable()

    def meteo(self, brut: int, imposee: bool = False) -> int:
        if self.pluie == 0 or not self.applicable() or brut != 0 or imposee:
            return brut
        return PIEGE_PLUIE_VALEUR

    def image(self, libre: bool = True) -> None:
        if self.ident_zone != self.ident_partie:            # vider
            self.ident_zone, self.montre, self.pluie = self.ident_partie, 0, 0
        if self.ident_sauvegarde is None or not self.applicable() or not libre:
            return
        self.montre = max(self.montre - 1, 0)
        self.pluie = max(self.pluie - 1, 0)


class ModeleCombatsPieges(ModelePieges):
    """Modèle du suivi des combats de pieges.cpp (apPiegesImage / imageCombat / combatCree / essaiTerrain pour le combat
    surprise), même ordre que le C : fin de combat, puis combat surprise demandé / commencé, puis relecture des PV. Le
    piège de combat se décide une fois, à la création du combat (`cree`, FUN_0045786C), jamais sur une image de combat.
    `attente` ne sert QU'AU combat surprise (marqueur PIEGE_COMMENCE) ; les PV ont leur compteur (`pv_attente`, revue de
    ap/v3-pieges-jeu : réutiliser `attente` bloquait les pièges de terrain ~20 s après un combat surprise)."""

    def __init__(self, compile_: int = PIEGES_COMPILES_DEFAUT):
        super().__init__(compile_)
        self.rencontre = self.attente = self.pv_attente = self.reessai = self.images_combat = 0
        self.combat = 0          # PIEGES_COMBAT_ETATS
        self.refus = 0
        self.errant = 0          # ApPiegesPrive::errant : posé par l'appel de FUN_00415058 venu de FUN_004984E4
        self.roue_armee = False
        self.pv_baisses = self.pv_reecrit = 0
        self.equipe: list[list[int]] = []    # [présent, K.O., PV, PV max] des 6 places du joueur
        self.essais_radar = 0    # recherches d'un point visé (une toutes les PIEGE_REESSAI_COMBAT images au plus)
        self.essais_oni = 0      # essais de lancer le combat d'Oni (même rythme)

    def essai_combat_surprise(self, point_vise: int, accepte: bool = True, repli: int = 0) -> bool:
        """Boucle de terrain réduite à un combat surprise (voir `boucle_terrain`)."""
        return self.boucle_terrain(point_vise, accepte, repli)

    def boucle_terrain(self, point_vise: int, accepte: bool = True, repli: int = 0, oni_accepte: bool = False,
                       tutoriels: bool = True) -> bool:
        """Fin de apPiegesImage : image d'essai décidée une fois (`reessai` nul), file parcourue dans l'ordre, chaque
        sorte de combat essayée une fois, `reessai` posé APRÈS la boucle. `point_vise` = rencontre du point visé par le
        radar (0 : aucun), `repli` = rencontre du tirage sur la carte (0 : aucune). Tutoriels de combat pas finis :
        aucun combat, motif 11 ; argent et montre (toujours faisables) passent, quelle que soit leur place."""
        image_essai = not self.reessai
        tentes = set() if image_essai else {PIEGE_COMBAT, PIEGE_ONI}
        for _rang, p in self.file:
            if p in (PIEGE_ARGENT, PIEGE_MONTRE):
                self.faire(p)
                return True
            if p not in (PIEGE_COMBAT, PIEGE_ONI) or p in tentes:
                continue
            tentes.add(p)
            if not tutoriels:
                self.refus = 11
                continue
            if p == PIEGE_COMBAT:
                self.essais_radar += 1
                r = point_vise or repli
                if not r or not accepte:
                    self.refus = 4 if not r else 5
                    continue
                self.rencontre, self.attente = r, 0
                return True
            self.essais_oni += 1
            if oni_accepte:
                self.rencontre, self.attente = 0x03F01229, 0      # kRencontreOni
                return True
            self.refus = 5
        if image_essai and tentes:
            self.reessai = PIEGE_REESSAI_COMBAT
        return False

    def pose_rencontre(self, hachage: int, retour: int = 0) -> None:
        """FUN_00415058 : `retour` = adresse de retour ; toute écriture hors de FUN_004984E4 retire la marque."""
        self.errant = hachage if retour == PIEGE_RETOUR_ERRANT else 0

    def combat_refuse(self, rencontre: int, loupe=(), octets: bool = False, regles: int = 0, scene: bool = False,
                      tutoriels: bool = True, oni: bool = False) -> int:
        """combatRefuse : 0 = éligible, sinon motif. `rencontre` = J + 0x110, jamais nulle dans un vrai combat."""
        if octets or regles & 0x62000:
            return 12
        if oni:
            return 7
        if scene:
            return 13
        if not tutoriels:
            return 11
        if not rencontre or rencontre not in (self.errant, self.rencontre, *loupe):
            return 7
        return 0

    def pv_moitie(self) -> int:
        """pvMoitie : PV ramenés à (max + 1) / 2 ; rend le nombre de Yo-kai qui étaient au-dessus."""
        n = 0
        for y in self.equipe:
            cible = (y[3] + 1) >> 1
            if y[0] and not y[1] and y[2] and cible and y[2] > cible:
                y[2] = cible
                n += 1
        return n

    def cree(self, equipe=(), motif: int = 0) -> None:
        """combatCree : décision du piège de combat à la création du combat, un seul appel par combat."""
        self.equipe = [list(y) for y in equipe]
        self.combat = 1
        pv = any(p == PIEGE_PV for _r, p in self.file)
        roue = any(p == PIEGE_ROUE for _r, p in self.file)
        if not pv and not roue:
            return
        if motif:
            self.refus = motif
            return
        if pv:
            self.pv_baisses, self.pv_reecrit = self.pv_moitie(), 0
            if self.pv_baisses:
                self.pv_attente, self.combat = 0, 3   # (ne pas écrire `attente` : marqueur du combat surprise)
                return
            self.refus = 8
            if not roue:
                return
        self.roue_armee = True
        self.combat = 2

    def image(self, combat: bool, rencontre_script: int = 0, libre: bool = True) -> None:
        """Une image de apPiegesImage (sauvegarde liée)."""
        if combat:
            self.images_combat += 1
        elif self.images_combat:
            self.images_combat, self.combat = 0, 0
            if self.attente == PIEGE_COMMENCE:
                self.rencontre = self.attente = 0
        if libre and not combat and self.reessai:
            self.reessai -= 1
        if self.rencontre and self.attente != PIEGE_COMMENCE:
            if combat and rencontre_script == self.rencontre and self.faire(PIEGE_COMBAT) is not None:
                self.attente = PIEGE_COMMENCE
            elif not combat:
                self.attente += 1
                if self.attente >= PIEGE_ATTENTE_COMBAT:
                    self.refus, self.rencontre, self.attente = 5, 0, 0
        if not combat or self.combat != 3:
            return
        if not any(p == PIEGE_PV for _r, p in self.file):
            self.combat = 1
        elif self.pv_moitie():
            self.pv_attente = 0
            self.pv_reecrit += 1
            if self.pv_reecrit >= PIEGE_REECRITURES_PV:
                self.refus, self.combat = 8, 1
        else:
            self.pv_attente += 1
            if self.pv_attente >= PIEGE_RELECTURE_PV:
                self.faire(PIEGE_PV)
                self.combat = 2

    def terrain_bloque(self) -> bool:
        """Les pièges de terrain attendent-ils un combat surprise (`z->rencontre != 0`) ?"""
        return self.rencontre != 0


def pieges_perte_argent(m: int) -> int:
    """Argent retiré par le piège P2 (centimes) : m / 10 calculé comme le jeu ((m * 0xCCCCCCCD) >> 35)."""
    return (m * 0xCCCCCCCD) >> 35


# Multiplicateur d'XP (ap/multiplicateur-xp, demande de l'humain du 2026-11-06 ; docs/systemes/
# archipelago_multiplicateur_xp.md ; xp.cpp) : objet AP PROGRESSIF « Multiplicateur d'XP » (3 exemplaires) porté par
# trois entrées de `slot_data.verrous_actifs` de même objet, k = 81, 82, 83 de ApVerrous3 (80 : ap/rang-s-objet), `exemplaires` 1, 2, 3 :
# le client les écrit génériquement (recu[k] = 1 à partir de ce nombre d'exemplaires reçus, `recu_verrou3`), le jeu
# compte les k en vigueur et reçus : facteur 1 + ce nombre (x2, x3, x4) sur TOUTE l'expérience (ap/multiplicateur-xp-tout :
# ApplyReward FUN_004B2A04, seul chemin de l'ajout d'expérience, récrite ; ses trois appelants : combat gagné, requête,
# objet d'expérience ; un patch d'avant ne multipliait que les combats). N° « client » exigé par la graine : 77 (le client qui sait
# lire `exemplaires`, celui du Mirapo de poche) ; un patch sans ces bits est refusé comme un verrou manquant. Aucune
# écriture ni lecture GDB de plus.
VERROUS_XP = (81, 82, 83)
XP_APPLY_REWARD = 0x004B2A04
XP_APPELANTS = {0x00557CE0: "combat gagné", 0x00527DF0: "requête (0x3CBE)", 0x005664E0: "objet d'expérience"}
XP_PLAFOND = 99999
NOMS_VERROUS_XP = {k: f"Multiplicateur d'XP ({i + 1}/3)" for i, k in enumerate(VERROUS_XP)}
NOMS_VERROUS.update(NOMS_VERROUS_XP)
VERROUS3_COMPILES_DEFAUT |= sum(1 << (k - VERROU3_BASE) for k in VERROUS_XP)   # = 0xEFFF7FF (0xFFFF7FF avec le rang S, k = 80)


def xp_facteur(b3: bytes, liee: bool, ident_client: int = 0) -> int:
    """Facteur appliqué par xp.cpp (facteurXp) : 1 + nombre de k = 81..83 en vigueur et reçus."""
    if not liee:
        return 1
    d = dec_verrous3(b3)
    return 1 + sum(1 for k in VERROUS_XP
                   if verrou3_en_vigueur(b3, k, ident_client) and d["recu"][k - VERROU3_BASE])


def xp_multiplier(champs: dict, entrees: list, facteur: int) -> tuple:
    """Modèle de multiplierRecompense (xp.cpp) : `champs` = {12, 16, 20, 28, 32} (décalages de la récompense),
    `entrees` = expérience de chaque Yo-kai inscrit (combat, requête : égale à +12 ; objet d'expérience : +12 = 0,
    entrée multipliée seule). Rend (champs, entrees) après multiplication."""
    if facteur <= 1:
        return dict(champs), list(entrees)

    def m(v: int) -> int:
        return v if v >= XP_PLAFOND else min(v * facteur, XP_PLAFOND)
    c = dict(champs)
    for o in (16, 20, 28, 32):
        c[o] = m(champs[o])
    c[12] = c[28] + c[16] + c[32] + c[20]
    e = [0 if v == 0 else (c[12] if v == champs[12] else m(v)) for v in entrees[:6]] + list(entrees[6:])
    return c, e

# ap/rang-s-objet (archipelago_objets_cles_v11.md §23) : rang S de la montre par le 5e « Rang de montre ». Mode du mode
# « rang réel » (k = 20), k = 80 de la zone ApVerrous3 (AP_VERROU_RANG_S de verrous.h), sans objet propre : entrée
# « rangs_s » de `verrous_actifs` d'une graine nouvelle d'après-jeu ; le client l'écrit comme tout k >= 56 (bit
# d'`actifs`, recu[80] = 0 / 1, non lu par le jeu : le compte est recu[18]). En vigueur : plafond de l'écriture du rang
# réel S (5) à partir de la phase 11-10, 0x364C(5) ignoré et sa fenêtre filtrée (modèles plus haut, paramètre `rang_s`).
# N° « client » 81 (jamais publié par le jeu) : un client d'avant accepterait la graine (le jeu ferait juste) mais son
# tracker compterait 4 exemplaires pour le rang S ; suivant libre : 82.
VERROU_RANG_S = 80
VERROUS3_COMPILES_DEFAUT |= 1 << (VERROU_RANG_S - VERROU3_BASE)      # = 0xFFFF7FF (avec le multiplicateur d'XP, k = 81..83)
NOMS_VERROUS[VERROU_RANG_S] = "Rang de montre S (5e exemplaire)"
FONCTION_CLIENT_RANG_S = 81
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_RANG_S}
NOMS_FONCTIONS[FONCTION_CLIENT_RANG_S] = "Rang de montre S par l'objet (client trop ancien)"

# ---- ap/boss-voie-mystere (2026-11-06) : mélange des boss de VERSION 3 (`slot_data.rando_boss.mode` = « <mode>#3 »,
# boss de la Voie du mystère mélangés aussi : apworld/yokaiwatch2/boss_generation.py). Rien de nouveau dans le jeu
# (tables B / N comme la version 2). N° « client » 82 (jamais publié par le jeu) : un client d'avant range « #3 » dans
# « mode inconnu » et la partie n'aurait pas le mélange que sa logique suppose ; il la refuse (« Verrous manquants »).
# Suivant libre : 83.
FONCTION_CLIENT_BOSS_VOIE = 82
FONCTIONS_CLIENT_V3 = FONCTIONS_CLIENT_V3 | {FONCTION_CLIENT_BOSS_VOIE}
NOMS_FONCTIONS[FONCTION_CLIENT_BOSS_VOIE] = "Mélange des boss de la Voie du mystère (client trop ancien)"
