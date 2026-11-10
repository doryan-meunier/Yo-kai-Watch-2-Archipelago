# -*- coding: utf-8 -*-
"""Logique de la V1, sans Archipelago (tâche A2) : quelles locations, quels objets, quelles règles.

Ce module ne dépend que de la bibliothèque standard. `__init__.py` traduit le `Plan` en régions, locations et
règles Archipelago ; les tests hors ligne (`archipelago/tests/test_apworld_logique.py`) le vérifient
directement, avec un petit remplissage simulé.

Sources : `archipelago/CONCEPTION.md` §3 à §5, `docs/systemes/archipelago_objets_cles.md` (J1 : voies de don,
verrous, règles anti-blocage R1 à R7) et les JSON de `donnees/` (import A1 de l'ancien mod).

Principe (règle R2 de J1) : **la logique n'exige un objet que si le jeu bloque vraiment sans lui.**
- Objets testés par possession par le jeu (portes à clé, PNJ) : toujours exigés, toujours sûrs.
- Objets dont le verrou est à coder côté jeu (J4) ou à vérifier en jeu (T4) : mélangés et exigés seulement
  si l'option `verrous_actifs` les cite (elle doit décrire le patch réellement installé). Sinon, l'objet
  reste à son emplacement d'origine et la logique ne l'exige pas.
- Herbe ancestrale et Super tournevis, Clé salle du trésor et Poignée étrange : verrous de déclencheur de la V1.1
  (`docs/systemes/archipelago_objets_cles_v11.md` §11 et §13).
- Rangs de montre (V1.1, §14 et §17) : objet PROGRESSIF « Rang de montre » (4 exemplaires : D, C, B, A). Depuis le
  mode « rang réel » (§17, slot_data format 20) l'objet EST le rang de la montre : le jeu monte le vrai rang au nombre
  reçu (1 = D … 4 = A) et les montées de rang de l'histoire et des requêtes ne sont plus que des checks ; tout ce que
  le jeu soumet au rang (portes de montre, requêtes, requêtes clés des chapitres 4, 7 et 9) exige les exemplaires.
  Ancien mode (graines de format <= 19, `rangs_reel=False`) : les verrous de montre exigeaient le rang AP en plus du
  rang réel. 32 coffres dorés (et la Clinique du Crépuscule) deviennent des locations quand ce verrou est actif.
- Vélo (V1.1, §15 et §15 bis) : objet « Vélo » (le bouton vélo et la montée sont refusés tant qu'il n'est pas reçu ;
  mode « vélo réel », format 21 : le recevoir donne vraiment le vélo, la requête qs0009 ne le donne plus) et location
  « Objet-clé : Vélo » (fin de la requête qs0009), ajoutés ensemble quand ce verrou est actif ; aucune location n'exige
  le vélo (même logique dans les deux modes).
"""
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .amis_criminels import (AMIS, AMIS_PAR_DEFAUT, CRIMINELS, CRIMINELS_CHAPITRE_MIN, CRIMINELS_PAR_DEFAUT,
                             AMIS_5_ETOILES, AMIS_5_ETOILES_PAR_MEDAILLE, AMI_BANANAR, INVITES, INVITES_ARMEES,
                             INVITES_PAR_DEFAUT, INVITES_PAR_MEDAILLE, INVITES_TOUS, MODES_AMIS, MODES_CRIMINELS,
                             PLACES_PAR_OBJET)
from .boutiques import (BOUTIQUES_APRES_JEU, BOUTIQUES_ARTICLES, BOUTIQUES_PAR_CODE, BOUTIQUES_PAR_DEFAUT,
                        MODES_BOUTIQUES,
                        PRIX_MAX_PAR_DEFAUT, TABLOS_ARTICLES, articles_du_mode, chapitre_article, ids_retires,
                        exclu as boutique_exclue)
from .donnees import donnees
from . import apres_jeu as AJ
from . import medaillium as MD
from . import boss_generation as BG
from . import pieces as PS
from . import zones as ZN
from . import distributeurs as DI
from . import legendaires as LG
from . import donjon_portails as DP
from . import multiplicateur_xp as MX
from . import options_joueur as OJ

# ---------------------------------------------------------------------------
# Noms des jeux (un par langue, mêmes identifiants numériques)
# ---------------------------------------------------------------------------
NOM_JEU = {"fr": "Yo-kai Watch 2", "en": "Yo-kai Watch 2 (English)"}
FAMILLE_JEU = "Yo-kai Watch 2"

# Objet « vitrine » affiché par un coffre dont l'objet n'est pas livré au joueur par ce coffre (objet d'un
# autre monde, argent) : « Important Item 20 », jamais donné par le jeu (J1 §6.1).
HACHAGE_VITRINE = 0xA0531A08

# Texte d'une vitrine : même limite que le bandeau (55 octets UTF-8 utiles, archipelago_boite.md §6bis).
TEXTE_OCTETS_MAX = 55

# Option `objets_evenement` (archipelago_amis_criminels.md §7.4) : activée par défaut (décision de l'humain, 2026-09-29).
OBJETS_EVENEMENT_PAR_DEFAUT = True
# Yo-kai d'évènement à leur emplacement d'origine (archipelago_evenement_invitation.md §9) : dans toute nouvelle graine
# (pas une option du joueur : les trois invitations suivent `invites`, la Capsule favorite `objets_evenement`).
PLACES_PAR_DEFAUT = True

# ---------------------------------------------------------------------------
# Verrous (J1 §0, §3.2, §10 et §11)
# ---------------------------------------------------------------------------
# Le jeu vérifie déjà la possession (condition IsHaveItem) : ne pas donner l'objet suffit [C].
VERROUS_POSSESSION = frozenset({
    "cle_de_derriere", "cle_magnetique_or", "jolie_petite_cle", "jolie_grande_cle",
    "cle_appartement_c_101", "cle_appartement_c_303", "cle_appartement_b_301", "cle_appartement_b_204",
    "huile_de_tendino", "tenue_de_rocker",
    # porte de t105d12 (A-201) : t105g00_trigger n° 68/69 (rangs 76/77 du fichier), IsHaveItem [C] ; clé seulement dans le coffre 216 (Clinique)
    "cle_appartement_a_201",
    # Objets-clés de quête (branche ap/objets-cles-quetes, archipelago_objets_cles_v11.md §16) :
    # - Clé magnétique rouge : console des égouts, t100d00_trigger n° 41 (IsHaveItem) [C] ; porte rouge (flag 1279)
    #   qui s'ouvre aussi de l'autre côté (n° 31, sans objet) : aucune location ne l'exige ;
    # - huit objets du Musée en détresse (quête 40) : remise au conservateur, TALK_CONFIG de t106d31 (IsHaveItem) [C] ;
    #   la quête ne finit qu'avec les dix objets exposés (QUEST_NECESSARY_CONDITION : dix flags d'exposition) [C].
    "cle_magnetique_rouge", "poster_de_film", "bobine_de_film", "bouteille_de_y_cola", "affiche_de_restaurant",
    "louloutre", "pot_canard", "figurine_de_photortue", "robe_de_star",
})
# Objets du Musée en détresse (quête 40) : les dix objets exposés sont exigés [C, t106d31_npc_talk, quest_config].
# La Silhouette de héros n'est pas mélangée (donnée DEUX fois dans la quête 46, retirée entre les deux : une
# substitution par hachage priverait la quête 46 et le musée) ; la Tenue de rocker est un coffre (t201g00).
OBJETS_MUSEE = ("tenue_de_rocker", "poster_de_film", "bobine_de_film", "bouteille_de_y_cola", "affiche_de_restaurant",
                "louloutre", "pot_canard", "figurine_de_photortue", "robe_de_star")

# Verrous à coder côté jeu (J4) ou à confirmer en jeu (T4). Valeurs de l'option `verrous_actifs`.
# mecanisme : description courte ; flag : index de flag bit global lu par l'action (J1 §2.2) quand il est
# connu [C] ; chapitre : chapitre du plafond de phase (g) ; code_jeu : le verrou est appliqué par le CODE du
# patch (le client refuse une partie qui en exige un que le jeu installé n'a pas compilé, boîte §20) ;
# implemente : False = aucun verrou n'existe dans le patch, l'option est acceptée (anciens YAML) mais IGNORÉE
# (objet laissé à sa place, jamais exigé, absent de slot_data). Détail : archipelago_objets_cles.md §13.
VERROUS_A_ACTIVER: Dict[str, dict] = {
    # masque du flag 28 (points de recherche à la loupe : insectes, pêche, et tout ce qui passe par ces points), dès le
    # début, tutoriel du chapitre 1 compris (ap/filet-tutoriel, objets_cles §12.7) : sans le Filet, l'histoire s'arrête
    # en phase 1-50 ; seule location faisable avant : son emplacement (c01 n° 16), la règle « prologue » exige le Filet
    # partout ailleurs
    "filet_a_insectes": {"mecanisme": "masque_flag", "flag": 28, "code_jeu": True},
    # masque du flag 29 (pêche à la loupe) ; aucune séquence d'histoire ne le lit [C]
    "canne_a_peche": {"mecanisme": "masque_flag", "flag": 29, "code_jeu": True},
    # commande 0x3CEF (flag 21, menus de combat), exemptée jusqu'au combat ev06_btl0040 (R1)
    "modele_zero": {"mecanisme": "commande_0x3CEF", "flag": 21, "code_jeu": True},
    # phase 3-40 lue 3-30 : zones de fermeture de l'école actives, suite de l'histoire du chapitre 3 bloquée
    "cles_de_l_ecole": {"mecanisme": "plafond_phase", "chapitre": 3, "code_jeu": True},
    # V1.1 : déclencheur de phase c03_trigger n° 21 ignoré (FUN_00448988) : on entre et on sort de la maison
    # de Coteau fleuri (t103i21) sans la scène ev03_1400 ; suite du chapitre 3 bloquée (objets_cles_v11 §11)
    "herbe_ancestrale": {"mecanisme": "declencheur", "chapitre": 3, "code_jeu": True},
    # V1.1 : c03_trigger n° 27 (2 zones du Quartier des boutiques, t105g00) ignoré : pas d'Heure funeste
    # scénarisée ; suite du chapitre 3 bloquée, rang D (n° 33) retardé (objets_cles_v11 §11)
    "super_tournevis": {"mecanisme": "declencheur", "chapitre": 3, "code_jeu": True},
    # V1.1 : phase 4-50 lue 4-40 (routes et refoulements du Centre-ville actifs) ET c04_trigger n° 14, 15, 17, 18
    # (arrivée au Centre-ville, sur flags) ignorés, jusqu'à l'arrivée ev60_0400 : le Centre-ville reste fermé comme

    # avant la seconde remise d'objets à Maman ; suite du chapitre 4 bloquée (objets_cles_v11 §3, §12)
    "indications_de_maman": {"mecanisme": "plafond_phase_et_declencheur", "chapitre": 4, "code_jeu": True},
    # V1.1 : déclencheur de QUÊTE t102d31 n° 5 (zone du combat de Volteface, quête qs0051 en phase 5) ignoré : la
    # quête 51 ne peut pas finir, ni donc la quête 52 (Misterre) qui l'exige (objets_cles_v11 §13)
    "cle_salle_du_tresor": {"mecanisme": "declencheur_quete", "quete": 51, "code_jeu": True},
    # V1.1 : déclencheur de QUÊTE t105d41 n° 7 (point de la Poignée, qs0057 en phase 9, la nuit) ignoré : la phase
    # reste 9, la route vers Firmain reste fermée ; ni la quête 57 ni la 58 (Ombraptor) ne finissent (v11 §13)
    "poignee_etrange": {"mecanisme": "declencheur_quete", "quete": 57, "code_jeu": True},
    # V1.1 : rangs de montre. Objet PROGRESSIF sans spot (k = 18 dans la boîte, recu[18] = nombre reçu) + modes
    # « portes D » (k = 19, VERROU_RANGS_D_SLOT) et « rang réel » (k = 20, VERROU_RANG_REEL_SLOT, objets_cles_v11 §17) :
    # le jeu monte le rang RÉEL de la montre à min(nombre reçu, A) et ignore les montées de rang de ses scripts
    # (commande 0x364C) ; les verrous de montre (OP_WATCHLOCK_POINT, commande 0x3700) de rang D, C, B, A restent
    # fermés tant que le nombre reçu est inférieur (1 = D … 4 = A). Option indépendante de `objets_cles_melanges`
    # (objets_cles_v11 §5, §14, §17).
    "rangs": {"mecanisme": "verrou_de_montre", "cle_objet": "rang_de_montre", "k": 18, "progressif": True,
              "exemplaires": 4, "code_jeu": True},
    # V1.1 : flags 39 et 40 (bouton vélo du menu terrain : affiché / utilisable) lus 0 et commande 0x3564 (montée)
    # refusée tant que le Vélo n'est pas reçu ; la descente reste permise. Objet sans emplacement ni don dans le jeu
    # (k = 12 dans la boîte, réserve 570..575). Mode « vélo réel » (k = 21, VERROU_VELO_REEL_SLOT, objets_cles_v11
    # §15 bis) : à la réception, le JEU donne vraiment le vélo (flags 39 et 40, objet vélo) et le joueur roule tout de
    # suite ; la requête qs0009 (boutique de vélos de Coteau fleuri) ne le donne plus : c'est seulement un check (et le
    # choix du modèle). Option indépendante de `objets_cles_melanges` (objets_cles_v11 §6, §15, §15 bis).
    "velo": {"mecanisme": "masque_flag_et_commande_0x3564", "flags": [39, 40], "k": 12, "code_jeu": True},
    # Verrou « possession » SANS code de jeu (2026-10-01, décision de l'humain, archipelago_objets_cles.md §14.9) : en
    # phase 2-60, la Crank-a-kai du tutoriel (t102g00, c02_trigger n° 12) ouvre un menu qui n'accepte QUE la Pile ou
    # passe ; sans elle, le jeu ne permet pas d'avancer (vu en jeu par l'humain) : l'histoire s'arrête en 2-60. La pièce
    # reste mélangée et exigée (mêmes règles qu'avec l'ancien verrou k = 1, retiré du patch) ; `code_jeu` faux : le client
    # n'exige rien du build.
    "pile_ou_passe": {"mecanisme": "verifie_en_jeu", "chapitre": 2, "code_jeu": False},
    # ---- V3 (lot 1, docs/systemes/archipelago_objets_cles_v11.md §20) : verrous ÉTENDUS (k >= 40, zone ApVerrous2 de la
    # boîte ; un client d'avant la V3 les ignorerait : la graine porte les n° 22 et 65 dans `fonctions_exigees`).
    # Objets à emplacement d'évènement (EMPLACEMENTS_V3), mélangés avec `objets_cles_melanges` comme les autres ; leurs
    # locations n'existent que si le verrou est actif (une graine sans eux est identique à une graine de la V2).
    # Yo-kai Watch : sans elle, en combat, ni Cible (flag 54), ni Âmultime (commande 0x3C62), ni Purification (commande
    # 0x3C5E(1024)), ni interface de la Modèle zéro (0x3CEF) ; lecture seule, valeur figée par combat. N'arrête pas
    # l'histoire (aucun combat n'exige ces actions par script ou par règle [C]) : règle PRUDENTE (CHAPITRE_BLOQUE_PAR :
    # chapitre 3, et toute location « Boss »).
    "yokai_watch": {"mecanisme": "lectures_de_combat", "flag": 54, "k": 40, "code_jeu": True},
    # Documents perdus : t104i53_quest_trigger n° 3 (remise à Papa, requête clé qs0009 en phase 8) ignoré : la requête
    # ne finit pas, ni donc la phase 7-20
    "documents_perdus": {"mecanisme": "declencheur_quete", "quete": 9, "k": 41, "code_jeu": True},
    # Cartes d'Ultramax : t131i01_quest_trigger n° 4 et 5 (remise, requête clé qs0014 en phase 4) ignorés : la requête
    # ne finit pas, ni donc la phase 6-40
    "cartes_ultramax": {"mecanisme": "declencheur_quete", "quete": 14, "k": 42, "code_jeu": True},
    # ---- V3, lot 9 (docs/systemes/archipelago_v3_objets_cles_apworld.md) : objets-clés livrés côté jeu par les lots 5
    # et 7 (archipelago_v3_lettre_bille_deathlink.md §E.5, archipelago_v3_objets_cles_2.md §8). Verrous ÉTENDUS : k = 48
    # à 55 dans la zone ApVerrous2, k = 56 à 58 dans la zone ApVerrous3 (n° « client » 68 en plus dans
    # `fonctions_exigees`). Désactivés par défaut jusqu'aux essais en jeu, comme ceux du lot 1.
    # Lettre de Komasan : t202g00_quest_trigger n° 4 (remise, requête clé qs0011 en phase 5) ignoré : la requête ne
    # finit pas (ni la phase 5-110), le Grelot félin n'est pas donné
    "lettre_de_komasan": {"mecanisme": "declencheur_quete", "quete": 11, "k": 48, "code_jeu": True},
    # Bille mystérieuse : t201d11_quest_trigger n° 1 (entrée dans la ferronnerie, requête clé qs0012 en phase 4) ignoré
    "bille_mysterieuse": {"mecanisme": "declencheur_quete", "quete": 12, "k": 49, "code_jeu": True},
    # Capsules de lait : c09_trigger n° 10 (entrée dans t200d00, phase 9-80 : scène et combat de fin du chapitre 9)
    # ignoré : l'histoire s'arrête en 9-80, AVANT le siège du chapitre 10 (et non en 10-90, où l'objet est consommé)
    "capsules_de_lait": {"mecanisme": "declencheur", "chapitre": 9, "k": 50, "code_jeu": True},
    # Grelot félin, Montre de luxe : c05_trigger n° 12 (entrée chez le grand-père, t231i03, phase 5-130 : fin du
    # chapitre 5) ignoré tant que l'un des deux, en vigueur, n'est pas reçu
    "grelot_felin": {"mecanisme": "declencheur", "chapitre": 5, "k": 51, "code_jeu": True},
    "montre_de_luxe": {"mecanisme": "declencheur", "chapitre": 5, "k": 52, "code_jeu": True},
    # Miroirs Miroirfeuille : flag 17 « miroirs en service » lu « natif ET objet reçu » (jamais rendu vrai par le mod) ;
    # aucune étape d'histoire ni requête n'exige un miroir [C] : aucune location ne l'exige
    "miroirs": {"mecanisme": "masque_flag", "flag": 17, "k": 53, "code_jeu": True},
    # Mirapo de poche (décision de l'humain du 2026-10-27, docs/systemes/archipelago_mirapo_poche.md) : active aussi
    # « miroirs » (normaliser_options) ; l'objet « Miroirs » est remplacé par 2 exemplaires de l'objet PROGRESSIF
    # « Miroirs progressifs » : le 1er ouvre les miroirs (k = 53, comme l'objet Miroirs), le 2e donne le Mirapo de poche
    # (k = 61 : SELECT tenu sur le terrain ouvre le menu des miroirs, hors donjons et scènes ; jeu à jour exigé). Aucune
    # location n'exige ni l'un ni l'autre : les deux exemplaires sont « utiles » ; aucune location de plus.
    "mirapo_de_poche": {"mecanisme": "commande_mirapo", "cle_objet": "miroirs_progressifs", "k": 61,
                        "exemplaires": 2, "code_jeu": True},
    # Objets de requêtes facultatives : la REMISE de l'objet (déclencheur de la table de quête de la carte) est ignorée
    "ceinture_de_force": {"mecanisme": "declencheur_quete", "quete": 44, "k": 54, "code_jeu": True},
    "robot_retro_neuf": {"mecanisme": "declencheur_quete", "quete": 48, "k": 55, "code_jeu": True},
    "robot_mecanique_use": {"mecanisme": "declencheur_quete", "quete": 48, "k": 56, "code_jeu": True},
    "serviette_douce": {"mecanisme": "declencheur_quete", "quete": 80, "k": 57, "code_jeu": True},
    "dance_revolution": {"mecanisme": "declencheur_quete", "quete": 98, "k": 58, "code_jeu": True},
    # Valeurs SANS code du jeu (« possession » : le jeu teste déjà l'objet, ou rien n'est fermé) : `code_jeu` faux, le
    # client n'exige rien du patch (comme « pile_ou_passe »). Derrière une valeur NOUVELLE pour qu'aucune graine de la
    # V2 ne change (une graine sans ces valeurs garde exactement son pool).
    # - Carte à tamponner : les tampons des gares (script StampRallyMain) testent la possession ; requête 90, puis 39 ;
    # - Clé appartement C-302 : trou de la V2 (son coffre 328 est une location, la clé n'était plus nulle part) : la clé
    #   entre dans le pool ; rien n'est derrière sa porte (t105d19 : ni coffre doré ni location [C]) : « utile » ;
    # - Clé magnétique bleue : avec le verrou « rangs », son coffre 179 (derrière un verrou de montre A) redevient une
    #   location et la clé entre dans le pool ; sans « rangs », rien ne change (le coffre garde sa clé).
    "carte_a_tamponner": {"mecanisme": "possession", "quete": 90, "code_jeu": False},
    "cle_appartement_c_302": {"mecanisme": "possession", "code_jeu": False},
    "cle_magnetique_bleue": {"mecanisme": "possession", "code_jeu": False},
    # ---- V3, lot 11 (docs/systemes/archipelago_v3_train_temps_apworld.md ; côté jeu : archipelago_v3_train_temps.md).
    # Deux CAPACITÉS de déplacement, sans objet du jeu (don « aucun »), verrous de la zone ApVerrous3 (n° « client » 68) :
    # - Train (« Abonnement de train ») : sans lui, les portillons des gares de Granval (t104i61, t103g00, et t107g00 à
    #   partir de 6-40) ne répondent pas ; ceux d'Ourcival et de San Fantastico jamais (retour toujours possible). Les
    #   billets restent payants. L'histoire s'arrête en 4-60 (premier trajet). PAS d'emplacement d'origine (le billet
    #   s'achète) : l'objet est toujours au pool, avec ou sans `objets_cles_melanges` (comme le Vélo) ;
    # - Voyage dans le temps : sans lui, les quatre passages ALLER (gare d'Ourcival, Hauts de Granval hors du chapitre 10,
    #   Mont Sylvestre et Vieux Granval d'après-jeu) sont refusés, les retours jamais. Emplacement d'origine : la
    #   rencontre du Yo-kai du passage en 5-90 (flag 264), mélangé avec `objets_cles_melanges` comme les autres.
    "train": {"mecanisme": "declencheur_carte", "chapitre": 4, "k": 59, "code_jeu": True},
    "voyage_dans_le_temps": {"mecanisme": "declencheur_carte", "chapitre": 5, "k": 60, "code_jeu": True},
}
# Verrous de la V3 (étendus) : jamais dans une graine de la V2. VERROUS_V3 : lot 1 ; VERROUS_V3_OBJETS : lot 9 ;
# VERROUS_V3_PASSAGES : lot 11.
VERROUS_V3: FrozenSet[str] = frozenset({"yokai_watch", "documents_perdus", "cartes_ultramax"})
VERROUS_V3_OBJETS: FrozenSet[str] = frozenset({
    "lettre_de_komasan", "bille_mysterieuse", "capsules_de_lait", "grelot_felin", "montre_de_luxe", "miroirs",
    "ceinture_de_force", "robot_retro_neuf", "robot_mecanique_use", "serviette_douce", "dance_revolution",
    "carte_a_tamponner", "cle_appartement_c_302", "cle_magnetique_bleue"})
FAMILLE_CLE_V3 = "objet_cle_v3"      # famille de leurs objets (objets.json) : jamais dans le pool sans leur verrou
# V3, lot 3 des pièges : famille des pièges d'objets.json (pieges.py) : remplissage tiré dans `__init__.py`, hors du plan
FAMILLE_PIEGE = "piege"
OBJET_MONTRE = "yokai_watch"
# Lot 9 : objets sans emplacement d'évènement (contenu d'un coffre), au pool quand leur valeur est active (la Clé
# magnétique bleue : seulement avec le verrou « rangs », son coffre 179 n'étant une location qu'avec lui).
OBJETS_V3_SANS_EMPLACEMENT = ("cle_appartement_c_302", "cle_magnetique_bleue")
COFFRE_CLE_BLEUE = 179
# Lot 9, option `parchemins` : trois objets que le jeu ne donne que par code QR (inobtenables sur émulateur), donnés
# réellement par leur objet AP ; ni emplacement ni location, « utiles ». Option à part (et non `objets_evenement`, à
# laquelle ils ressemblent) : `objets_evenement` est une option de la V2, activée par défaut ; y ajouter trois objets
# changerait le pool de toutes ses graines.
PARCHEMINS = ("parchemin_en_nyavant", "parchemin_de_victoire", "parchemin_miahourra")
PARCHEMINS_PAR_DEFAUT = False
# N° « client » de `fonctions_exigees` (jamais publié par le jeu) d'une graine qui a un verrou de la zone ApVerrous3
# (k >= VERROU3_BASE) : un client d'avant le lot 9 ignorerait ce verrou sans rien dire ; il refuse la graine sur ce n°.
VERROU3_BASE = 56
FONCTION_CLIENT_7 = 68
# Lot 11 : capacités de déplacement (train ordinaire k = 59, voyage dans le temps k = 60). Le Train n'a pas
# d'emplacement d'origine : toujours au pool quand son verrou est actif.
OBJET_TRAIN = "train"
OBJET_VOYAGE = "voyage_dans_le_temps"
VERROUS_V3_PASSAGES: FrozenSet[str] = frozenset({OBJET_TRAIN, OBJET_VOYAGE})
# Mirapo de poche (2026-10-27) : valeur de `verrous_actifs` désactivée par défaut, hors des grilles des lots d'avant ;
# n° « client » 77 (jamais publié par le jeu) dans `fonctions_exigees` : un client d'avant écrirait recu[61] dès le
# premier exemplaire, il refuse la graine.
VERROU_MIRAPO = "mirapo_de_poche"
OBJET_MIROIRS = "miroirs"
OBJET_MIROIRS_PROGRESSIFS = "miroirs_progressifs"
VERROUS_V3_MIRAPO: FrozenSet[str] = frozenset({VERROU_MIRAPO})
FONCTION_CLIENT_MIRAPO = 77


def verrous_implementes() -> FrozenSet[str]:
    return frozenset(k for k, v in VERROUS_A_ACTIVER.items() if v.get("implemente", True))


def verrous_v2() -> FrozenSet[str]:
    """Verrous implémentés de la V2 publiée (sans les verrous étendus de la V3) : grilles d'options des tests et des
    outils qui contrôlent les graines d'avant la V3 (les verrous de la V3 ont leurs propres tests)."""
    return verrous_implementes() - VERROUS_V3 - VERROUS_V3_OBJETS - VERROUS_V3_PASSAGES - VERROUS_V3_MIRAPO


def verrous_sans_lot9() -> FrozenSet[str]:
    """Verrous de la V2 et du lot 1 de la V3 (sans les objets-clés du lot 9) : grilles des tests des lots 1, 3 et 6."""
    return verrous_implementes() - VERROUS_V3_OBJETS - VERROUS_V3_PASSAGES - VERROUS_V3_MIRAPO


def verrous_sans_lot11() -> FrozenSet[str]:
    """Tous les verrous d'avant le lot 11 (sans le Train ni le Voyage dans le temps) : grilles des tests et des audits
    des lots 9 et 10 (un verrou d'arrêt de plus changerait leurs plans ; le lot 11 a ses propres contrôles)."""
    return verrous_implementes() - VERROUS_V3_PASSAGES - VERROUS_V3_MIRAPO


def verrous_sans_mirapo() -> FrozenSet[str]:
    """Tous les verrous d'avant le Mirapo de poche : grilles des tests et des audits des lots d'avant (le Mirapo change
    le pool : deux « Miroirs progressifs » à la place des Miroirs)."""
    return verrous_implementes() - VERROUS_V3_MIRAPO


def cle_objet_verrou(verrou: str) -> str:
    """Clé de l'objet qui ouvre ce verrou (la même que celle du verrou, sauf « rangs » : « rang_de_montre »)."""
    return VERROUS_A_ACTIVER[verrou].get("cle_objet", verrou)


# ---------------------------------------------------------------------------
# Rangs de montre (objets_cles_v11 §5 et §14)
# ---------------------------------------------------------------------------
# Rang AP = nombre de « Rang de montre » reçus (0 aucun, 1 D, 2 C, 3 B, 4 A) : un verrou de montre de rang D exige 1
# exemplaire, C 2, B 3, A 4 (objets_cles_v11 §14.8, décision de l'humain : rang D verrouillé aussi). Les verrous S
# (après-jeu) ne sont pas touchés par le mod.
# Mode « rang réel » (décision de l'humain, 2026-10-02, objets_cles_v11 §17 ; LE comportement du verrou « rangs » pour
# toute nouvelle graine) : rang réel de la montre = rang AP (le jeu l'écrit à la réception ; c03 n° 33 et les requêtes
# 25 / 26 / 27 ne le montent plus, ce ne sont que des checks). Tout « rang >= X » du jeu exige EXEMPLAIRES_RANG[X].
# Ancien mode (`rangs_reel=False` : graines de format <= 19, pour le tracker) : le rang réel venait du jeu (D : c03
# n° 33, OBJETS_RANG_D ; C, B, A : requêtes 25, 26, 27) et restait exigé EN PLUS du rang AP (EXEMPLAIRES_RANG_REEL,
# SEUIL_RANG_REEL).
VERROU_RANGS = "rangs"
OBJET_RANG = "rang_de_montre"
EXEMPLAIRES_RANG = {"D": 1, "C": 2, "B": 3, "A": 4}
# Entrée supplémentaire de `slot_data.verrous_actifs` quand le verrou « rangs » est actif (slot_data format 7) : mode
# « portes D » du jeu (k = 19 : rang AP = recu[18], portes D fermées aussi). Un jeu qui ne le compile pas est refusé
# par le client (« Verrous incompatibles ») ; un client antérieur le traite comme un verrou ordinaire (bit 19 posé,
# recu[19] = 0 / 1, ignoré par le jeu) : comportement correct. Sans cette entrée (graine antérieure), le jeu garde
# l'ancien calcul (D + nombre reçu, portes D d'origine), cohérent avec l'ancienne logique à 3 exemplaires.
VERROU_RANGS_D_SLOT = {"cle": "rangs_d", "k": 19, "mecanisme": "verrou_de_montre_mode_portes_d",
                       "cle_objet": "rang_de_montre", "code_jeu": True}
# Troisième entrée (slot_data format 20) : mode « rang réel » du jeu (k = 20 : rang réel de la montre monté à
# min(recu[18], A), montées de rang des scripts ignorées). Un jeu qui ne le compile pas est refusé par le client
# (« Verrous incompatibles ») : la logique de la graine compte sur lui ; un client antérieur le traite comme un verrou
# ordinaire (bit 20 exigé et posé, recu[20] = 0 / 1 ignoré par le jeu) : comportement correct. Sans cette entrée
# (graine antérieure), le jeu garde l'ancien comportement (rang réel donné par l'histoire et les requêtes).
VERROU_RANG_REEL_SLOT = {"cle": "rangs_reel", "k": 20, "mecanisme": "rang_de_montre_reel",
                         "cle_objet": "rang_de_montre", "code_jeu": True}
CLE_RANG_REEL = "rangs_reel"        # présente dans `slot_data.verrous_actifs` : graine en mode « rang réel »
# ap/rang-s-objet (décision de l'humain du 2026-11-06, objets_cles_v11 §23) : le rang S devient le 5e exemplaire de
# « Rang de montre » pour les graines NOUVELLES dont l'objectif est d'après-jeu (`a_objectif_aj`), en mode « rang
# réel » : quatrième entrée de `slot_data.verrous_actifs`, mode k = 80 du jeu (zone ApVerrous3) : le jeu écrit le rang
# S quand 5 exemplaires sont reçus ET l'histoire finie (GetPhase >= 11-10, condition d'apparition de la requête 28),
# ignore le rang S de la requête 28 (simple check) et sa fenêtre. Toute exigence « rang S » de la logique vaut
# EXEMPLAIRES_RANG_S (5) au lieu de 4 (la requête 28 elle-même, rang A, garde 4). Un jeu qui ne compile pas k = 80 est
# refusé par le client (« Verrous incompatibles », zone ApVerrous3 : n° 65 et 68 déjà exigés par toute entrée k >= 56) ;
# un client d'avant refuse la graine par le n° « client » 81 (jamais publié). Sans cette entrée (graine d'avant ou
# objectif de la V2) : rang S par la requête 28, logique d'avant (4 exemplaires), tracker reconstruit à l'identique.
VERROU_RANG_S_SLOT = {"cle": "rangs_s", "k": 80, "mecanisme": "rang_de_montre_s", "cle_objet": "rang_de_montre",
                      "code_jeu": True}
CLE_RANG_S = "rangs_s"              # présente dans `slot_data.verrous_actifs` : graine à rang S par l'objet
EXEMPLAIRES_RANG_S = 5
FONCTION_CLIENT_RANG_S = 81
# Interrupteur d'AUDIT (audit_logique.py --sans-rang-s) : faux = règles d'avant (rang S = 4 exemplaires) dans un plan à
# rang S par l'objet (5 exemplaires au pool) : le modèle doit contredire (I5). Toujours vrai ailleurs.
REGLES_RANG_S = True
# Seconde entrée du verrou « velo » (slot_data format 21) : mode « vélo réel » du jeu (k = 21 : à la réception du Vélo,
# le jeu pose les flags 39 et 40 et donne l'objet vélo ; avant, l'objet vélo de la boutique de la requête est retiré).
# Un jeu qui ne le compile pas est refusé par le client (« Verrous incompatibles ») : le joueur qui reçoit le Vélo doit
# pouvoir rouler sans faire la requête ; un client antérieur le traite comme un verrou ordinaire (bit 21 exigé et posé,
# recu[21] = 0 / 1 ignoré par le jeu) : comportement correct. Sans cette entrée (graine antérieure), le jeu garde
# l'ancien comportement (autorisation seulement : le vélo vient de la requête). La logique est la même dans les deux
# modes (aucune location n'exige le vélo ; la location reste la fin de la requête).
VERROU_VELO_REEL_SLOT = {"cle": "velo_reel", "k": 21, "mecanisme": "velo_reel", "cle_objet": "velo",
                         "code_jeu": True}
CLE_VELO_REEL = "velo_reel"         # présente dans `slot_data.verrous_actifs` : graine en mode « vélo réel »
# Rang RÉEL (requêtes de rang de t103i21, jamais modifié par le mod) : chapitres terminés avant de pouvoir l'avoir
# (valeurs de l'ancien mod mesurées en jeu, prudentes : C au 6e chapitre, B au 7e, A au 9e ; la requête du rang S est
# d'après-jeu), et exemplaires AP qu'il faut pour FAIRE la requête : celle du rang B passe par des lieux fermés par
# les verrous C de San Fantastico (t121d03, t121d11), celle du rang A par la Clinique du Crépuscule (verrou B de
# t105g00) [C, conditions GetQuestPhase(qs0026 / qs0027) de ces cartes].
# La requête du rang C (quête 25) se fait dans le Manoir (t103d31, t103d35 : combats btl_qs0025_01..03), derrière le
# verrou D de t103g00 [C] : le rang réel C exige 1 exemplaire (objets_cles_v11 §14.8). Rang réel D (histoire, c03 n° 33,
# carte t103i21, hors de toute porte) : 0.
SEUIL_RANG_REEL = {"C": 5, "B": 6, "A": 8}
EXEMPLAIRES_RANG_REEL = {"C": 1, "B": 2, "A": 3}
# Coffres dorés derrière un verrou de montre D..A (index TBox -> rang du verrou) [C pour les verrous et les routes :
# OP_WATCHLOCK_POINT, et zone de la route vers la carte fermée 8 à 14 unités derrière le mur du verrou ; S pour
# l'appartenance d'un coffre à la partie fermée d'une carte, recoupée avec les étiquettes de l'ancien mod, mesurées
# en jeu] :
# - C : 24, 25 (t101d02, route derrière le verrou de t101d01) ; 44, 45 (partie de t102g00 atteinte par les égouts,
#   route derrière le verrou de t100d00) ; 110 (t103d11) et 90 (partie haute de t103g00 atteinte par t103d11) ;
#   359 (t121d03) et 362..370 (t121d11, grotte du littoral), routes derrière les deux verrous de t121g00 ;
# - B : 107 (t103d03) ; 211..215, 217..219, 221 (Clinique du Crépuscule : route t105g00 -> t105d41 derrière le verrou
#   B de t105g00 ; 219 et 221 aussi derrière celui de t105d45) ;
# - A : 179 (t104d11, 3e étage de la tour du commerce, du côté opposé à l'ascenseur) ;
# - D : 113..123 (Manoir t103d31 et t103d35 : coffres de la V1 « Manoir » et « Manoir arrière ») : la seule entrée du
#   Manoir (routes t103g00 -> t103d31 / t103d33, portes du jardin arrière) est dans la partie de t103g00 fermée par le
#   verrou D (mur (61.8, 100.3, -577.8), tout ce qui est au-delà de z = -578) [C pour les routes et les positions ; S
#   fort pour l'unicité du passage : l'ancien mod, mesuré en jeu, exigeait « chapitre 3 + rang D » pour le Manoir]
#   (objets_cles_v11 §14.8). Le verrou D du Quartier des boutiques (t105g00) ne ferme qu'une impasse sans location.
# Ajouts de la couverture (archipelago_couverture.md §3.1, R3 ; positions et routes vérifiées sur le RomFS) :
# - A : 29 (t101d05, Allée sinistre : derrière le verrou A (11.6, 72.5), du côté opposé à l'entrée et au coffre 28) ;
# - B : 220 (t105d45, Clinique, côté de l'arrivée) ; 207 (t105d12, appartement A-201 du Quartier des boutiques : porte
#   IsHaveItem(Clé appartement A-201), t105g00_trigger n° 68 ; la clé n'est que dans le coffre 216 de la Clinique) : le
#   chemin passe par le verrou B.
# Ajout des checks oubliés (archipelago_couverture.md §9) : B : 216 (t105d43, Clinique : routes t105d41 / t105d45 ->
#   t105d43 sans verrou, seule entrée de la Clinique derrière le verrou B de t105g00 [C]) ; son contenu d'origine, la Clé
#   appartement A-201, entre dans le pool (OBJETS_COFFRES_DE_RANG) et le coffre 207 l'exige (COFFRES_OBJETS_SUPPLEMENTAIRES).
# Les coffres 180..185 (tour du commerce) ne sont derrière aucun verrou de montre : leur étiquette « rang C » de
# l'ancien mod ne demande que le rang réel (exclusion -> SEUIL_RANG_REEL, EXEMPLAIRES_RANG_REEL).
COFFRES_VERROU_DE_MONTRE: Dict[int, str] = {
    **{i: "C" for i in (24, 25, 44, 45, 90, 110, 359, 362, 363, 364, 365, 366, 367, 368, 369, 370)},
    **{i: "B" for i in (107, 207, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221)},
    29: "A", 179: "A",
    **{i: "D" for i in range(113, 124)},
}
# Coffres de rang qui ne deviennent JAMAIS des locations (contenu d'origine gardé) : objet exigé par le jeu que rien
# d'autre ne donne (archipelago_logique_audit.md G2-4) :
# - 179 : Clé magnétique bleue, testée par la console de la base secrète des égouts (t100d00_trigger n° 42 et 45,
#   IsHaveItem) [C]. En faire une location supprimerait la seule clé bleue du jeu ; la mettre dans le pool exigerait
#   une règle sur tout ce que sa porte ouvre, inconnu [S] (aucune location connue derrière) : garder le coffre.
# (216, Clinique, Clé appartement A-201 : gardé d'origine par la couverture R3, devenu une location avec les checks oubliés,
#  la clé entrant dans le pool quand le verrou « rangs » est actif : OBJETS_COFFRES_DE_RANG.)
COFFRES_RANG_NON_LOCATIONS: Dict[int, str] = {179: "cle_magnetique_bleue"}
# Objets-clés dont la seule source est un coffre de rang (location seulement avec le verrou « rangs ») : dans le pool
# seulement quand ce verrou est actif ; sinon le coffre garde son contenu d'origine (et la porte qu'ouvre l'objet ne
# ferme aucune location : le coffre 207 n'existe qu'avec le même verrou). Objet -> index TBox du coffre [C].
OBJETS_COFFRES_DE_RANG: Dict[str, int] = {"cle_appartement_a_201": 216}
# Régions entières derrière un verrou de montre (connexion) : la Clinique du Crépuscule (verrou B de t105g00).
REGIONS_VERROU_DE_MONTRE: Dict[str, str] = {"clinique_du_crepuscule": "B"}
EXCLUSIONS_RANG = {"rang_C": "C", "rang_B": "B", "rang_A": "A"}
# V3 (décision de l'humain du 2026-10-25, docs/systemes/archipelago_tablos.md §10) : étages de la Tour du commerce du
# Centre-ville. L'ascenseur (t104i51 / t104i53, déclencheurs de type 39) ne propose le 3e étage (t104d11) qu'avec le
# flag 587 et le 12e / 13e (t104d13) qu'avec le flag 586 ; aucune route ni téléportation n'y mène autrement. Leur SEUL
# écrivain est t104g00.xq RunCmd_Map41 (déclencheur de type 11 du PNJ 0x69C2F003), PNJ qui n'apparaît qu'avec le flag
# 2113 = « Yo-kai appelé » du Tablo-blabla n° 11 : il faut POSSÉDER ce Yo-kai (amitié au hasard), ce que la logique
# ne modélise pas [C, cfg_entrees / cfg_conditions / xq_cherche sur seq et .pck, aucun mot de code.bin]. Toute location
# de ces deux cartes est EXCLUE (remplissage seulement) dans les graines générées depuis ce lot (`tour_commerce` de
# `construire_plan`, clé `tour_commerce_exclus` de slot_data) ; une graine d'avant garde son plan.
# - coffres : 179 (3e étage, rang A ; verrou « rangs » + « cle_magnetique_bleue »), 180..182 (3e étage) et 183..185
#   (12e étage) avec le verrou « rangs » ; 186 et 490 (13e étage, après-jeu, région « rang_s ») ;
# - requête 95 (« Ronéan : les origines », après-jeu) : acceptée, combattue et finie dans t104d11
#   (t104d11_quest_trigger n° 1 type 52, n° 3 / 4 type 78) ;
# - (la requête 114, dont le Yo-kai est dans t104d13, est déjà toujours exclue.)
TOUR_COMMERCE_COFFRES: FrozenSet[int] = frozenset((179, 180, 181, 182, 183, 184, 185, 186, 490))
TOUR_COMMERCE_QUETES: FrozenSet[int] = frozenset((95,))
TOUR_COMMERCE_PAR_DEFAUT = True        # toute nouvelle graine ; False : graine générée avant ce lot (tracker)
CLE_SLOT_DATA_TOUR = "tour_commerce_exclus"


# ---------------------------------------------------------------------------
# Vélo (objets_cles_v11 §6 et §15)
# ---------------------------------------------------------------------------
# Location « Objet-clé : Vélo » = requête qs0009 terminée (phase 255, lue par le client comme un boss de quête : 4e champ
# de QUEST_CONFIG = 9) [C] : QuestCompleteEx('qs0009') suit l'achat du vélo, la scène ev70_0950 et RunBicycle
# (t103g00_quest n° 8/10), que le verrou soit actif ou non (la montée refusée n'arrête pas le script). Identifiants et
# noms de l'ancien mod. Apparition : GetPhase >= 7-20 (QUEST_CONFIG) ; chemin : maison, gares (train), bureau du
# Centre-ville (t104i53), boutique de vélos (t103g00) ; la phase 6 exige de posséder le Yo-kai Yvantouse
# (QUEST_PHASE -> QUEST_NECESSARY_CONDITION type 2), représenté par le chapitre comme les autres Yo-kai à posséder [S].
# Règle : celle de « Chapitre 7 terminé » (plus stricte que le jeu, jamais moins), comme un boss de quête. Aucune
# location n'exige le vélo : aucune condition de .cfg.bin ne lit les flags 39/40, IsBicycleOn n'est lu que par la
# musique (map_sound) [C] ; la course de vélo (race_menu) fournit ses propres vélos.
VERROU_VELO = "velo"
QUETE_VELO: dict = {"cle": "velo", "id_ap": 59423001, "nom_fr": "Objet-clé : Vélo", "nom_en": "Key Item: Bicycle",
                    "quete": 9, "chapitre": 7, "region": "coteau_fleuri"}


def exemplaires_pour(rang_reel: Optional[str] = None, verrou: Optional[str] = None, reel: bool = True) -> int:
    """Exemplaires de « Rang de montre » exigés : verrou de montre franchi (D 1, C 2, B 3, A 4) et/ou rang de montre
    exigé par le jeu. Mode « rang réel » (`reel`) : le rang X exige EXEMPLAIRES_RANG[X] (D 1, C 2, B 3, A 4) ; ancien
    mode : la requête qui donnait le rang (C : 1 exemplaire, B : 2, A : 3 ; D : histoire, 0)."""
    return max(EXEMPLAIRES_RANG.get(verrou, 0), (EXEMPLAIRES_RANG if reel else EXEMPLAIRES_RANG_REEL).get(rang_reel, 0))


# Jamais mélangés. Vide depuis la V1.1 : la Clé salle du trésor et la Poignée étrange (J1 §7) ont leur verrou de
# déclencheur de quête (objets_cles_v11 §13) et sont mélangées seulement quand il est actif.
NON_MELANGES_V1: FrozenSet[str] = frozenset()

# Coffres qui exigent en plus un objet quand son verrou est actif (index TBox -> objets ; filtrés comme toute règle :
# sans effet quand l'objet n'est pas mélangé). Plus strict que le jeu, jamais moins (objets_cles_v11 §13.4) :
# - 75 « Tunnel abandonné (salle du trésor) - Coffre 02 » (t102d31, (158, 40.6, -461)) : du même côté que la zone du
#   combat de Volteface par rapport à la porte 0x1A0AA0B8 (60, 40, -387), fermée par le jeu à qui n'a pas la Clé
#   salle du trésor (t102d31_trigger n° 20, IsHaveItem) ; accès réel non prouvé [?] : exigence de prudence.
# - 79 « Tunnel abandonné est - Coffre 07 » (t102d32, (-212, 0.3, 159)) : du côté ouest, desservi par le wagon SANS le
#   levier de l'Huile de Tendino (t102d32_trigger n° 8) [S, couverture] ; jamais ouvert dans les sauvegardes de
#   l'humain : Huile exigée par prudence (elle est dans le coffre 78 de la même carte, sans condition).
# - 454..458 « Centre-ville de Granval (géant fantôme) » (t104d33) : route t104i39 -> t104d33 ouverte à partir de la
#   phase 6 de la quête 58 (Ombraptor), jamais refermée (miroir dès la phase 7, y compris après la quête) [C] ; même
#   règle que le boss Ombraptor : quête 57 finie (Poignée étrange), rang A réel, Clinique (verrou B).
# - 207 « Résidence Sérénité (A-201) » (t105d12) : porte IsHaveItem(Clé appartement A-201), t105g00_trigger n° 68/69 [C]
#   (clé dans le pool avec le verrou « rangs », OBJETS_COFFRES_DE_RANG ; le coffre 207 n'existe qu'avec ce verrou).
# - 273..276 « Égouts - Coffre 13..10 » (t100d00) : les égouts sont découpés en secteurs par des murs et dix grilles à
#   sens unique (t100d00_trigger n° 2 à 21, paires type 23 / 21) [S fort ; recoupé avec EGOUTS_COFFRE_ACCESS de l'ancien
#   mod]. Coffres 10 / 11 (276, 275) : secteur où l'on n'entre que par le Quartier des boutiques (t105d01, ouvert en
#   3-140) : Herbe et Clés, comme sa connexion ; coffres 12 / 13 (274, 273) : par le Coteau fleuri (t103d03, 3-70) :
#   Clés (archipelago_logique_audit.md §3 G1-7). Coffres 08 / 09 (Centre-ville) : déjà justes dans les données.
# - 209 « Résidence Sérénité (bâtiment B) » (t105d15) : AUCUNE clé (revue verif/audit-softlock-corrections, archipelago_
#   logique_audit.md §3 G1-9) : la porte n° 76 / 77 de t105g00 (Clé appartement B-301, zone 0x052EA25C, y = 56) mène à
#   t105d17 ; t105d15 s'ouvre par la zone 0xEB20C370 (y = 33, étage de B-204 et A-201), citée par AUCUN déclencheur.
COFFRES_OBJETS_SUPPLEMENTAIRES: Dict[int, Tuple[str, ...]] = {75: ("cle_salle_du_tresor",), 79: ("huile_de_tendino",),
                                                              207: ("cle_appartement_a_201",),
                                                              **{i: ("poignee_etrange",) for i in range(454, 459)},
                                                              273: ("cles_de_l_ecole",), 274: ("cles_de_l_ecole",),
                                                              275: ("herbe_ancestrale", "cles_de_l_ecole"),
                                                              276: ("herbe_ancestrale", "cles_de_l_ecole")}
# Coffres de la V1 (sans exclusion de rang) sur le chemin d'une quête qui exige un rang réel et franchit un verrou de
# montre : (rang réel, verrou de montre) -> exemplaires de « Rang de montre » avec le verrou « rangs » (exemplaires_pour).
COFFRES_RANGS_CHEMIN: Dict[int, Tuple[str, str]] = {i: ("A", "B") for i in range(454, 459)}

# Connexions qui exigent en plus des objets (filtrés comme partout : sans effet quand l'objet n'est pas mélangé ou que
# son verrou n'est pas actif) ; surcharge de `regions.json` (import A1, non modifié). archipelago_logique_audit.md :
# - Quartier des boutiques (t105g00, t105d01, t105d22) : refoulé à l'entrée tant que phase <= 3-130 (c03_trigger n° 86/87)
#   [C] ; le verrou de l'Herbe arrête l'histoire à 3-120 : l'Herbe est exigée (G1-1). La sortie des égouts vers t105d01
#   est dans un secteur où l'on n'entre que PAR t105d01 (grilles à sens unique, §3 G1-7) : pas d'entrée plus précoce.
#   Clés de l'école : explicites (3-140 > 3-40), au lieu de passer seulement par « Chapitre 2 terminé » (§5).
# - Coteau fleuri (t103g00) : refoulé tant que 30010 <= phase <= 30065 (c03_trigger n° 44/45) [C] ; les Clés arrêtent
#   l'histoire à 3-40 : exigées explicitement (§5).
CONNEXIONS_OBJETS_SUPPLEMENTAIRES: Dict[Tuple[str, str], Tuple[str, ...]] = {
    ("menu", "quartier_des_boutiques"): ("herbe_ancestrale", "cles_de_l_ecole"),
    ("menu", "coteau_fleuri"): ("cles_de_l_ecole",),
    # Mont Sylvestre (« 1 chapitre ») : ouverture dans le chapitre 2 non datée : Pile ou passe exigée par prudence (§14)
    ("les_hauts_de_granval", "mont_sylvestre"): ("pile_ou_passe",),
    # V3, lot 11 (archipelago_v3_train_temps_apworld.md §2) :
    # - Train : Ourcival, San Fantastico (et ce qui en part : Mont de l'Ours, Voie du mystère) ne se rejoignent que par
    #   une gare de Granval [C : aucune route à pied dans map_route] ; la Tour Excellence aussi jusqu'en 6-40 (puis à
    #   pied par La Corniche : le Train reste exigé, il l'est déjà par « Chapitre 4 terminé ») ;
    # - Voyage dans le temps : Vieux Granval et Vieil Ourcival (et ce qui en part : Plaines Plinpot, Repaire) par les
    #   passages seulement ; jusqu'en 10-45 le seul passage est à la gare d'Ourcival : le Train est cité avec lui.
    ("centre_ville_de_granval", "ourcival"): ("train",),
    ("centre_ville_de_granval", "san_fantastico"): ("train",),
    ("centre_ville_de_granval", "tour_excellence"): ("train",),
    ("les_hauts_de_granval", "vieux_granval"): ("train", "voyage_dans_le_temps"),
    ("ourcival", "vieil_ourcival"): ("train", "voyage_dans_le_temps"),
}
# V3, lot 11 : chapitres terminés minimaux de connexions quand le Train est exigible (max avec `regions.json`). San
# Fantastico et la Tour Excellence ne s'ouvrent dans le jeu qu'en 6-40 (sorties des quais t100s12 / t100s17 : type 48
# « phase >= 6-31 », zones refoulées par c04 n° 76 / 77, c05 n° 17 / 18, c06 n° 23 / 24 ; route à pied de La Corniche
# refoulée par c02..c05) [C, archipelago_v3_train_temps.md §1.1] : 5 chapitres terminés (6-40 suit sans arrêt : les
# phases 6-10 à 6-30 se jouent dans le passé, par envoi scénarisé). `regions.json` dit « 3 chapitres » : défaut de la
# logique publiée (V2), corrigé pour TOUTE graine par le correctif de la branche `v2` (reporté ensuite dans main) ;
# ici seulement avec le verrou « train », pour ne changer aucune graine d'avant ; sans objet une fois le report fait.
CONNEXIONS_CHAPITRES_TRAIN: Dict[Tuple[str, str], int] = {
    ("centre_ville_de_granval", "san_fantastico"): 5,
    ("centre_ville_de_granval", "tour_excellence"): 5,
}
# V3, lot 11 : objets exigés en plus par des régions d'après-jeu (hors de `AJ.REGIONS[...]["objets"]`, dont un objet
# absent de la graine FERME la région) ; filtrés comme partout. Trains de nuit et Entrain Express : sur les quais,
# derrière les portillons ; Château de Sawayama : passage du Vieux Granval (aller D), requête acceptée dans une station.
REGIONS_AJ_OBJETS_SUPPLEMENTAIRES: Dict[str, Tuple[str, ...]] = {
    "sortilege_express": ("train",), "entrain_express": ("train",),
    "chateau_de_sawayama": ("train", "voyage_dans_le_temps"),
}
# V3, lot 11 : boutiques des trains (wagons N046 / N047) : sur un quai
BOUTIQUES_OBJETS: Dict[str, Tuple[str, ...]] = {"N046": ("train",), "N047": ("train",)}

# Chapitres terminés minimaux de coffres dont la zone s'ouvre plus tard que ne le disent les données (index TBox ->
# chapitres ; max avec les données). Plus strict que les données, exact d'après le jeu (archipelago_logique_audit.md) :
# - 1-8, 10, 11 « Les Hauts de Granval » : OP_TBOX_POINT de t101g00, condition GetPhase >= 20010 [C] (G3-1) ;
# - 425-429 « Vieux Mont de l'Ours » : seule entrée t231g00 -> t231d03 refoulée par c05..c09 tant que
#   50010 <= phase <= 90040 [C] (G3-2) ; 8 chapitres = phase >= 9-10, sans verrou d'arrêt jusqu'à 9-50.
# - 9 (couverture) : même carte et même condition que 1-8, 10, 11 [C].
# Audit softlock (décisions de l'humain du 2026-10-26, archipelago_logique_audit.md §3 G1-10, G1-11 ; corrections pour
# toute graine : condensats_plans.CORRECTIONS_REGLES) :
# - 26 « Les Hauts de Granval (Passage des matous) » (t101d03) : la carte est refoulée tout le chapitre 1 (c01_trigger
#   n° 55) et de 2-10 à 2-80 (c02_trigger n° 50) [C] : ouverte au plus tôt en 2-85, après l'arrêt de la Pile ou passe
#   (2-60) : 1 chapitre, et la Pile (ajoutée comme à tout coffre « 1 chapitre », filtrée quand elle n'est pas exigible) ;
# - 373 « Vieux Hauts de Granval (retour Ch10) » (t201g00) : zone refusée pendant tout le chapitre 10 (c10_trigger
#   n° 94 / 95, 100010 <= phase <= 100990) [C], accès avant le chapitre 10 non prouvé : 10 chapitres, c.-à-d. après la
#   fin du chapitre 10. Avec l'objectif de la V2 (la fin du chapitre 10 est la victoire), la location est donc d'après
#   la victoire : EXCLUE (COFFRES_APRES_VICTOIRE).
COFFRES_CHAPITRES_MIN: Dict[int, int] = {**{i: 1 for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)},
                                         **{i: 8 for i in (425, 426, 427, 428, 429)}, 26: 1, 373: 10}
# Coffres de la V1 dont la règle est celle de l'objectif de la V2 (10 chapitres) : exclus avec cet objectif (rien
# d'après la victoire, invariant I7 d'audit_logique) ; avec un objectif d'après-jeu, ce sont des coffres comme les autres.
COFFRES_APRES_VICTOIRE: FrozenSet[int] = frozenset({373})
# École de nuit (décision de l'humain du 2026-11-03, retour de la bêta V3 ; archipelago_logique_audit.md §2.2 et §3
# G1-13 ; correction pour TOUTE graine : condensats_plans.CORRECTIONS_REGLES) : coffres 31..43 « École élémentaire de
# Granval (nuit) - Coffre 01..13 » (t101i51, t101i52, t101i53, t101i55). `regions.json` les mettait à « 3 chapitres » ;
# le jeu les ouvre dès la phase 3-190 : OP_TBOX_POINT en double, « GetTimeNow de nuit ET flag 558 != 1 » ou « flag 558
# == 1 » (posé en PhCmd_3_190, effacé en PhCmd_3_230) [C] ; l'école est fermée la nuit avant (t101g00_trigger n° 65,
# 1-10 .. 3-180) et ses étages sont atteints dès 3-190 (parcours des routes d'audit_cartes.py) [C]. Entre 3-10 et 3-190,
# l'histoire ne s'arrête qu'aux verrous des Clés de l'école (3-40), de l'Herbe ancestrale (3-120) et du Super tournevis
# (3-150) (audit_logique.ARRET_PHASE) ; aucun rang (aucune condition de cNN_trigger / phase_set_cNN ne lit le rang,
# objets_cles_v11 §17.2 ; premier arrêt de rang : 4-135, dans les deux modes) ; la Yo-kai Watch n'arrête rien (et le
# boss Grolos, pour lequel la logique l'exige par prudence, vient en 3-220) ; seule l'attente des requêtes clés 3, 4 et
# 6 (3-95, zones.ATTENTES) demande un Yo-kai à zone (requête 4) : avec le mélange par zones, l'accès à sa zone
# s'ajoute (zone du chapitre 3 au plus, ouverte avant 3-95 : zones.candidats).
# Règle : 2 chapitres terminés + ces trois objets (filtrés comme partout) [+ accès à la zone].
COFFRES_ECOLE_NUIT: FrozenSet[int] = frozenset(range(31, 44))
ECOLE_NUIT_CHAPITRES = 2
ECOLE_NUIT_OBJETS: Tuple[str, ...] = ("cles_de_l_ecole", "herbe_ancestrale", "super_tournevis")
PHASE_ECOLE_NUIT = 30190
# Interrupteur d'AUDIT (audit_logique.py --sans-ecole) : False = règle d'avant (« 3 chapitres » des données).
REGLE_ECOLE_NUIT = True
# Audit softlock (décision de l'humain du 2026-10-26, archipelago_logique_audit.md §3 G1-8) : CHANTIER du Centre-ville.
# Les requêtes 45 et 58 exigent le flag 584 (QUEST_CONFIG), posé à l'origine par la réinitialisation quotidienne deux ou
# trois jours RÉELS après l'appel du Yo-kai du Tablo-blabla n° 9 (flag 2111, Sumochi) [C]. Fonction étendue 52 du patch
# (FONCTION_CHANTIER, limites.cpp) : le flag 584 est lu vrai dès l'appel. Dans une graine générée depuis (`chantier` de
# `construire_plan`, reconnue par le tracker à 52 dans `fonctions_exigees`) : les requêtes qui exigent 45 ou 58 finies
# (ou les sont : 45, 46, 40, 58), le boss Ombraptor (58) et les coffres 454..458 (route ouverte par la phase 6 de la 58)
# exigent aussi la zone des Yo-kai du Tablo-blabla n° 9 (Sumochi, `zones.DEMANDES`) ; l'accès au Centre-ville est déjà
# compris dans leur chapitre (5 chapitres et plus : « Chapitre 4 terminé » exige les Indications de Maman). La zone est
# aujourd'hui IMPLIQUÉE par leur chapitre (zones de chapitre <= 7, 45 / 46 / 40 l'avaient par la 44) : ajout explicite
# par prudence, seul le texte des règles change. Une graine d'avant garde ses règles (et profite de la fonction 52 avec
# un patch à jour).
QUETES_CHANTIER: FrozenSet[int] = frozenset({45, 58})
TABLO_CHANTIER = 9
COFFRES_QUETE_CHANTIER: Dict[int, int] = {i: 58 for i in range(454, 459)}
FONCTION_CHANTIER = 52
CHANTIER_PAR_DEFAUT = True          # toute nouvelle graine ; False : graine générée avant (tracker)

# San Fantastico et Tour Excellence (correctif 2.0.1) : `regions.json` les ouvrait à « 3 chapitres terminés » (import
# de l'ancien mod, recoupé à tort avec les MAP_ROUTE_LOCK <= 4-60, qui ne font que GUIDER). Dans le jeu [C données] :
# - San Fantastico (t121*) : seule arrivée par le quai t100s12, dont la sortie est un déclencheur de type 48 : n° 1
#   « phase <= 6-30 » = scène de refus et retour, n° 2 « phase >= 60031 » = entrée ; la zone de sortie est en plus
#   refoulée par c04 n° 76, c05 n° 17, c06 n° 23 (4-10 à 6-30) : ouverte à la phase 6-40 ;
# - Tour Excellence (t107*) : quai t100s17 identique (6-40) ; route à pied de La Corniche refoulée par c02 à c05
#   (2-10 à 5-9990), puis c06 n° 6 (« ev60_1000 non vu », avant le refoulement n° 25) y fait entrer : au plus tôt 6-10.
# Donc jamais avant « Chapitre 5 terminé » : les deux connexions de `regions.json` valent 5 chapitres. Sinon un objet
# qui arrête l'histoire au chapitre 4 (Canne à pêche, premier « Rang de montre » en mode « rang réel » : 4-135) pouvait
# être placé dans un coffre ou une boutique de ces régions, hors d'atteinte : partie bloquée. Tout ce qui est rangé
# dans ces deux régions en hérite par la connexion (coffres, boss, requêtes, boutiques N023 / N033, Tablo-blabla n° 17
# à 19, amis d'évènement des gares de la ligne de San Fantastico [S : prudent]). Ourcival (quai t100s16 : type 48 sans
# condition) reste à 3 chapitres (premier trajet en 4-60). Modèle indépendant : audit_logique.PHASE_REGION.

# Quand un verrou est actif, « Chapitre N terminé » exige l'objet (en plus des objets critiques repris de
# l'ancien mod, `regions.json` : Clés de l'école pour le chapitre 2, retirées par CRITIQUES_RETIRES ; Canne à pêche pour
# le chapitre 4, gardée). Exigences volontairement PLUS STRICTES que le jeu, jamais moins (objets_cles.md §13.7) :
# - Clés de l'école (chapitre 2 dans l'ancien mod) : le jeu bloque en réalité la suite du chapitre 3 (phase 3-40) ;
#   RETIRÉES de « Chapitre 2 terminé » (CRITIQUES_RETIRES) et exigées pour le chapitre 3 (arrêt réel). Une location
#   « 2 chapitres » des données qui ne s'ouvre qu'après 3-40 ne les hérite donc d'AUCUNE règle de chapitre : elle doit
#   les citer explicitement (connexions de Coteau fleuri et du Quartier des boutiques,
#   CONNEXIONS_OBJETS_SUPPLEMENTAIRES ; coffres 10 à 13 des égouts, COFFRES_OBJETS_SUPPLEMENTAIRES ; emplacement de
#   la Clé magnétique rouge) (archipelago_logique_audit.md §5, §3 G1-7) ;
# - Modèle zéro (chapitre 6) : la commande 0x3CEF est exemptée jusqu'au combat ev06_btl0040 ; exigée pour la
#   fin du chapitre 6 et Lady Démona, par prudence (combats scénarisés suivants [?]).
# - Herbe ancestrale et Super tournevis (chapitre 3, V1.1) : exactes. Sans l'Herbe, la phase 3-120 ne finit pas
#   (ev03_1400) ; sans le Tournevis, la phase 3-150 non plus (ev03_1800) : le chapitre 3 ne peut pas se terminer.
#   Le Tournevis retarde aussi le rang D (c03_trigger n° 33, après le n° 27) : les coffres du Manoir (113..123,
#   derrière le verrou de montre D de t103g00, « 2 chapitres » dans les données) exigent OBJETS_RANG_D (correction
#   de objets_cles_v11 §14.8 : ce verrou ferme bien des coffres de la V1) ; tout le reste qui demande le rang D suit le
#   chapitre 3 et exige déjà « Chapitre 3 terminé ».
# - Indications de Maman (chapitre 4, V1.1) : exactes. Sans elles, la phase 4-50 ne finit pas (ev04_0700 suit
#   l'arrivée ev60_0400) et le Centre-ville reste fermé : la connexion vers `centre_ville_de_granval` (et tout ce qui
#   en dépend : Tour Excellence, Ourcival, San Fantastico, Mont de l'Ours) et le Musée de La Corniche les exigent
#   déjà dans les données (`regions.json`, `coffres.json`) ; tout le reste d'après le chapitre 4 exige « Chapitre 4
#   terminé ». Le don (c04 n° 10-13) précède le verrou : son emplacement ne les exige pas (objets_cles_v11 §12.5).
# - Pile ou passe (chapitre 2, objets_cles §14) : exacte pour la fin du chapitre 2 (l'histoire s'arrête en 2-60). Retirée
#   de « Chapitre 1 terminé » (critique de l'ancien mod, CRITIQUES_RETIRES) : sinon son propre emplacement (2-50,
#   « 1 chapitre ») l'exigerait. Les locations « 1 chapitre » qui ne passent pas par la règle du chapitre 2 l'exigent
#   explicitement (COFFRES_AVANT_TUTORIEL_PILE, CONNEXIONS_OBJETS_SUPPLEMENTAIRES : Mont Sylvestre ; La Corniche dans les
#   données), sauf son emplacement.
# - Canne à pêche (chapitre 4, objets_cles_v11 §18.3 et §19) : exacte pour la fin du chapitre 4. La requête 99 « Pas le
#   temps de pêcher ! » est une requête CLÉ : la phase 4-135 attend la phase 4 de la quête de chapitre 174, dont la phase
#   3 exige les requêtes 5, 29 et 99 finies [C : QUEST_NECESSARY_CONDITION type 9, phase_set_c04]. Ordre de la 99 [C] :
#   phase 2 (vaincre 3 Yo-kai à la loupe d'Ourcival) -> don de la Canne (l'emplacement, t131g00_quest n° 78) -> phase 3
#   (posséder 3 poissons, que seule la pêche donne : aucune boutique ni script, un lot de Crank-a-kai au hasard) -> finie.
#   Sans la Canne reçue (flag 29 lu « Canne reçue »), l'histoire s'arrête donc en 4-135, APRÈS l'emplacement de la Canne
#   (qui ne l'exige pas : pas de règle circulaire). L'ancien mod avait raison (critique du chapitre 4, mesuré en jeu) ;
#   l'audit G4, qui l'avait retirée (« aucune séquence d'histoire ne pêche »), était faux. Plus strict que le jeu pour les
#   locations « du chapitre 4 » d'avant 4-135 (même convention que les Indications), jamais moins. Les coffres « 3
#   chapitres » dont la zone ne s'ouvre qu'après 4-135 l'exigent aussi (COFFRES_APRES_ARRET_CANNE).
# - V3 (objets_cles_v11 §20) : Documents perdus (chapitre 7) et Cartes d'Ultramax (chapitre 6) : exactes. Les requêtes 9
#   et 14 sont des requêtes CLÉS (quêtes de chapitre 177 et 176, QUEST_NECESSARY_CONDITION type 9) : sans la remise de
#   l'objet, elles ne finissent pas, ni les phases 7-20 et 6-40. Leurs emplacements (le don, avant la remise) ne les
#   exigent pas. Yo-kai Watch (chapitre 3) : règle PRUDENTE, pas un arrêt du jeu : le verrou ne ferme que trois boutons
#   du combat ; aucun des cinq combats scénarisés des chapitres 1 et 2 (ev01_btl0010, ev02_btl0010 / 0020 / 0030,
#   btl_qs0068_01 : Yo-kai ordinaires, sans script de combat, règles de restriction seulement [C]) n'exige ces actions ;
#   à partir du chapitre 3 viennent les boss à parties (Grolos, ev03_btl0020) : la montre est exigée pour finir le
#   chapitre 3 (donc tout ce qui suit) et par toute location « Boss ».
# - V3, lot 9 (archipelago_v3_objets_cles_apworld.md) : exactes. Lettre de Komasan et Bille mystérieuse (chapitre 5) :
#   les requêtes 11 et 12 sont des requêtes CLÉS (quête de chapitre 175, type 9) : sans la remise de la Lettre ou
#   l'entrée de la ferronnerie, la phase 5-110 ne finit pas. Grelot félin et Montre de luxe (chapitre 5) : la scène de
#   fin du chapitre (entrée de t231i03, 5-130) est refusée tant que l'un des deux manque. Capsules de lait (chapitre
#   9, PAS 10) : l'entrée du combat final du chapitre 9 (t200d00, 9-80) est refusée : l'objet est exigé dès « Chapitre 9
#   terminé » (il n'est consommé qu'en 10-90, mais le chapitre 10 se joue ville bouclée : arrêter là enfermerait le
#   joueur). Leurs emplacements (4 et 5 chapitres terminés, le don précède le verrou) ne reprennent pas ces règles.
# - V3, lot 11 (archipelago_v3_train_temps_apworld.md §2). Train (chapitre 4) : exact : le premier trajet (4-60) passe
#   un portillon de Granval. Plus strict que le jeu pour les locations « du chapitre 4 » d'avant 4-60 (même convention
#   que les Indications et la Canne), jamais moins.
#   Voyage dans le temps (chapitre 5, et NON 6) : le jeu ne l'exige qu'en 6-60 d'un joueur qui reste dans le passé
#   pendant tout le chapitre 5 (il y est envoyé par script) ; mais le RETOUR de la gare du Vieil Ourcival existe dès
#   5-100 et n'est jamais refusé : un joueur revenu dans le présent pour y faire des locations « 4 chapitres » (elles
#   sont en logique) ne peut plus repartir, et les requêtes clés de 5-110 sont dans le passé. Si l'objet n'était exigé
#   qu'au chapitre 6, il pourrait être placé derrière « Chapitre 5 terminé » (San Fantastico, 6-40) : graine bloquée
#   pour ce joueur. Exigé dès « Chapitre 5 terminé » (plus strict que le jeu pour un joueur qui ne revient pas, jamais
#   moins). L'évènement est de toute façon dans la région « vieux_granval », fermée sans l'objet.
CHAPITRE_BLOQUE_PAR = {"indications_de_maman": 4, "herbe_ancestrale": 3, "super_tournevis": 3,
                       "cles_de_l_ecole": 3, "pile_ou_passe": 2, "canne_a_peche": 4,
                       "yokai_watch": 3, "documents_perdus": 7, "cartes_ultramax": 6,
                       "lettre_de_komasan": 5, "bille_mysterieuse": 5, "grelot_felin": 5, "montre_de_luxe": 5,
                       "capsules_de_lait": 9,
                       "train": 4, "voyage_dans_le_temps": 5}
# Modèle zéro (2026-11-05, retour de la bêta V3 ; archipelago_objets_cles_v11.md §22) : RETIRÉE de « Chapitre 6
# terminé » et de toute autre règle (Tablo-blabla n° 20 à 22, accès au repaire de Lady Démona, deux exigences reprises
# de l'ancien mod) : elle n'arrête rien [C]. Le flag 21 n'a qu'un lecteur, la commande 0x3CEF (0x0051C624), appelée 14
# fois par les deux seuls scripts du menu de combat (BattleMenu_003j, BattleMenu_Ex_009f : boutons « changer de
# montre » et « Pique », lentille, icônes) ; aucun des 43 scripts de rencontre (seq/battle/encount), aucune condition
# `.cfg.bin`, aucun déclencheur ni `phase_set_cNN` ne la lit (phase_set_c06 : flags d'évènement seulement). Le verrou
# ne retire que l'interface de la Modèle zéro, c'est-à-dire l'interface des chapitres 1 à 5 (tous joués sans elle :
# flag posé en 6-20). En jeu (bêta V3), l'interface reste disponible sans l'objet de 6-20 à la victoire ev06_btl0040
# (exemption R1, voulue) : ce qui y est joué ne prouve rien ; la preuve est celle des données. Interrupteur d'AUDIT
# seulement (condensats des graines de la V2, `audit_logique.py --avec-modele-zero`) : faux = exigences d'avant.
# Toujours vrai ailleurs.
RETRAIT_MODELE_ZERO = True
OBJETS_SANS_EXIGENCE: Tuple[str, ...] = ("modele_zero",)
CHAPITRE_BLOQUE_PAR_AVANT: Dict[str, int] = {"modele_zero": 6}
# Avant l'arrêt des Cartes d'Ultramax (2026-11-05, même retour ; archipelago_objets_cles_v11.md §22) : la requête 14
# « Trouvons Lulutin ! » est bien une requête CLÉ [C : quête de chapitre 176, phase 4 : QUEST_NECESSARY_CONDITION type 9
# des requêtes 13 à 17 ; phase_set_c06 : 6-40 finit quand la quête 176 vaut 5] : sans la remise des Cartes, l'histoire
# s'arrête en 6-40 (« Chapitre 6 terminé » et ce qui suit les exigent toujours). Mais cet arrêt vient APRÈS tout ce qui
# s'ouvre jusqu'en 6-40 : les quatre autres requêtes clés (QUEST_CONFIG « phase == 6-40 » [C, quetes.py]), leurs boss,
# les requêtes, Tablo-blabla, boutiques et amis « du chapitre 6 » que le modèle d'audit_logique place au plus tard en
# 6-40 (certitude C ou S). Ces locations, qui reprenaient la règle de « Chapitre 6 terminé » (plus stricte que le jeu),
# ne l'exigent plus. Vu en jeu (bêta V3, sauvegarde en 6-40) : requête 17 et boss Faux Kappa faits sans les Cartes.
# Clé = (genre, clé) de la location (`LocationPlan`) ; une location qui exige les Cartes pour elle-même (requête 14) n'y
# est jamais. Contrôle : tests/test_zero_ultramax.py (phase du modèle <= ARRET_PHASE des objets retirés, objets absents
# du modèle). Interrupteur d'AUDIT seulement (`audit_logique.py --sans-avant-arret`, condensats) : faux = règle du
# chapitre entière. Toujours vrai ailleurs. Même excès de prudence pour les autres arrêts : LOCATIONS_AVANT_ARRET_SUITE.
REGLES_AVANT_ARRET = True
_CARTES = ("cartes_ultramax",)
LOCATIONS_AVANT_ARRET: Dict[Tuple[str, str], Tuple[str, ...]] = {
    **{("requete", str(n)): _CARTES for n in (13, 15, 16, 17, 30, 45, 51, 85, 90, 100, 108, 113, 155, 164)},
    **{("boss", b): _CARTES for b in ("barbefrousse", "draconfus", "faux_kappa", "volteface")},
    **{("tablo", str(n)): _CARTES for n in (2, 13, 14, 15, 17, 18, 20, 21, 22, 26)},
    **{("boutique", "N016/%d" % e): _CARTES for e in (3, 8, 9, 14, 15, 20, 21, 26, 27, 28)},
    **{("ami", str(n)): _CARTES for n in (12, 232, 316, 351)},
    ("emplacement", "carte_a_tamponner"): _CARTES,
}
# Suite (2026-11-05, ap/tracker-avant-arret ; archipelago_objets_cles_v11.md §22.5) : même correction pour les autres
# objets qui ARRÊTENT l'histoire (verrou actif, objet mélangé, non reçu : `audit_logique.ARRET_PHASE`) et que la règle
# de « Chapitre N terminé », reprise par les locations « du chapitre N », exigeait trop tôt : Pile ou passe (2-60), Clés
# de l'école (3-40), Herbe ancestrale (3-120), Super tournevis (3-150), Indications de Maman (4-40), Train (4-60), Canne
# à pêche (4-135), Voyage dans le temps (5-100, PIRE cas : retour libre dès 5-100, allers refusés), Lettre de Komasan et
# Bille mystérieuse (5-110), Grelot félin et Montre de luxe (5-130), Documents perdus (7-20), Capsules de lait (9-80).
# Une location est dans la liste de l'objet k quand, dans TOUS les plans d'audit où sa règle cite k (verrous de la V2,
# tous les verrous, boss, rang réel ou non, après-jeu, objectif Médaillium, pièces spéciales, terrains de Blasters),
# le modèle d'audit_logique (`exigence_reelle` : train, voyage dans le temps compris) la place au plus tard à la phase
# d'arrêt de k, sans k dans ses objets, certitude C ou S (plans où la RÉGION de la location exige déjà k par ses
# connexions écartés : k y reste exigé) ; tirée par un balayage de ces plans, contrôlée par
# tests/test_avant_arret.py. Ce qui n'y est jamais : « Chapitre N terminé » et les évènements d'histoire (l'arrêt reste
# entier), les requêtes clés qui exigent l'objet pour elles-mêmes, les locations du passé pour le Voyage dans le temps
# (le modèle les y soumet : garde-fou du pire cas), toute location dont le modèle dépasse l'arrêt dans un seul plan.
# Graines à zones (lots M2b) : une location qui demande un Yo-kai placé dans une zone reprend la règle de cette zone
# (`zones.regle_zone`) ; l'objet k est gardé si la zone le porte et s'ouvre après l'arrêt de k ou l'exige sur son chemin
# (`garde_zone`, prudente : toute zone dont la règle est comprise dans celle de la location). Phases d'arrêt :
# PHASES_ARRET (recopiées du modèle, contrôlées par test). Interrupteur d'AUDIT seulement
# (`audit_logique.py --sans-avant-arret-suite`, condensats) : faux = règle du chapitre entière. Toujours vrai ailleurs.
# Hors liste, voulu : Filet à insectes (objet du prologue, rien avant son arrêt), Yo-kai Watch (n'arrête rien : exigée par
# prudence, comme les boss, décision à part ; §22.5), Modèle zéro (retirée de tout, ci-dessus).
REGLES_AVANT_ARRET_SUITE = True
PHASES_ARRET: Dict[str, int] = {
    "pile_ou_passe": ZN.ph(2, 60), "cles_de_l_ecole": ZN.ph(3, 40), "herbe_ancestrale": ZN.ph(3, 120),
    "super_tournevis": ZN.ph(3, 150), "indications_de_maman": ZN.ph(4, 40), "train": ZN.ph(4, 60),
    "canne_a_peche": ZN.ph(4, 135), "voyage_dans_le_temps": ZN.ph(5, 100), "lettre_de_komasan": ZN.ph(5, 110),
    "bille_mysterieuse": ZN.ph(5, 110), "grelot_felin": ZN.ph(5, 130), "montre_de_luxe": ZN.ph(5, 130),
    "cartes_ultramax": ZN.ph(6, 40), "documents_perdus": ZN.ph(7, 20), "capsules_de_lait": ZN.ph(9, 80)}
# objet d'arrêt -> locations (« genre:clé » ; coffre : index TBox) atteintes avant son arrêt
AVANT_ARRET_SUITE: Dict[str, Tuple[str, ...]] = {
    'pile_ou_passe': (  # 57
        'boutique:N001/1', 'boutique:N001/2', 'boutique:N001/3', 'boutique:N001/4', 'boutique:N001/5',
        'boutique:N001/6', 'boutique:N001/7', 'boutique:N007/1', 'boutique:N007/2', 'boutique:N007/3',
        'boutique:N007/4', 'boutique:N007/5', 'boutique:N007/6', 'boutique:N007/7', 'boutique:N019/1',
        'boutique:N028/1', 'boutique:N028/2', 'boutique:N028/3', 'boutique:N029/1', 'boutique:N035/1',
        'boutique:N035/2', 'boutique:N035/3', 'boutique:N035/4', 'boutique:N035/5', 'boutique:N035/6',
        'boutique:N035/7', 'boutique:N035/8', 'boutique:N035/9', 'boutique:N044/1', 'boutique:N044/10',
        'boutique:N044/11', 'boutique:N044/12', 'boutique:N044/13', 'boutique:N044/14', 'boutique:N044/15',
        'boutique:N044/16', 'boutique:N044/17', 'boutique:N044/18', 'boutique:N044/19', 'boutique:N044/2',
        'boutique:N044/20', 'boutique:N044/21', 'boutique:N044/22', 'boutique:N044/23', 'boutique:N044/24',
        'boutique:N044/25', 'boutique:N044/26', 'boutique:N044/27', 'boutique:N044/28', 'boutique:N044/29',
        'boutique:N044/3', 'boutique:N044/4', 'boutique:N044/5', 'boutique:N044/6', 'boutique:N044/7',
        'boutique:N044/8', 'boutique:N044/9',
    ),
    'cles_de_l_ecole': (  # 11
        'ami:54', 'ami:60', 'ami:96', 'ami:143', 'ami:260', 'ami:286', 'ami:348', 'ami:349', 'ami:350', 'ami:354',
        'requete:53',
    ),
    'herbe_ancestrale': (  # 80
        'ami:54', 'ami:60', 'ami:96', 'ami:143', 'ami:205', 'ami:260', 'ami:286', 'ami:348', 'ami:349', 'ami:350',
        'ami:354', 'ami:371', 'ami:373', 'ami:375', 'ami:377', 'ami:379', 'ami:381', 'ami:383', 'ami:385', 'ami:387',
        'coffre:444', 'coffre:445', 'coffre:446', 'coffre:447', 'coffre:448', 'coffre:449', 'coffre:450',
        'coffre:451', 'coffre:452', 'invite:50', 'invite:53', 'invite:59', 'invite:67', 'invite:68', 'invite:88',
        'invite:89', 'invite:90', 'invite:91', 'invite:95', 'invite:105', 'invite:106', 'invite:134', 'invite:136',
        'invite:137', 'invite:138', 'invite:142', 'invite:207', 'invite:208', 'invite:209', 'invite:210',
        'invite:227', 'invite:228', 'invite:233', 'invite:259', 'invite:285', 'invite:298', 'invite:299',
        'invite:370', 'invite:371', 'invite:372', 'invite:373', 'invite:374', 'invite:375', 'invite:376',
        'invite:377', 'invite:378', 'invite:379', 'invite:380', 'invite:381', 'invite:382', 'invite:383',
        'invite:384', 'invite:385', 'invite:386', 'invite:387', 'requete:3', 'requete:4', 'requete:6', 'requete:53',
        'tablo:8',
    ),
    'super_tournevis': (  # 82
        'ami:54', 'ami:60', 'ami:96', 'ami:143', 'ami:205', 'ami:260', 'ami:286', 'ami:348', 'ami:349', 'ami:350',
        'ami:354', 'ami:371', 'ami:373', 'ami:375', 'ami:377', 'ami:379', 'ami:381', 'ami:383', 'ami:385', 'ami:387',
        'coffre:444', 'coffre:445', 'coffre:446', 'coffre:447', 'coffre:448', 'coffre:449', 'coffre:450',
        'coffre:451', 'coffre:452', 'invite:50', 'invite:53', 'invite:59', 'invite:67', 'invite:68', 'invite:88',
        'invite:89', 'invite:90', 'invite:91', 'invite:95', 'invite:105', 'invite:106', 'invite:134', 'invite:136',
        'invite:137', 'invite:138', 'invite:142', 'invite:207', 'invite:208', 'invite:209', 'invite:210',
        'invite:227', 'invite:228', 'invite:233', 'invite:259', 'invite:285', 'invite:298', 'invite:299',
        'invite:370', 'invite:371', 'invite:372', 'invite:373', 'invite:374', 'invite:375', 'invite:376',
        'invite:377', 'invite:378', 'invite:379', 'invite:380', 'invite:381', 'invite:382', 'invite:383',
        'invite:384', 'invite:385', 'invite:386', 'invite:387', 'requete:3', 'requete:4', 'requete:6', 'requete:53',
        'requete:64', 'requete:152', 'tablo:8',
    ),
    'indications_de_maman': (  # 17
        'ami:54', 'ami:60', 'ami:96', 'ami:143', 'ami:260', 'ami:286', 'ami:433', 'ami:441', 'blasters:11',
        'boutique:N037/1', 'boutique:N037/2', 'boutique:N037/3', 'boutique:N037/4', 'requete:25', 'requete:112',
        'requete:125', 'requete:153',
    ),
    'train': (  # 37
        'ami:54', 'ami:60', 'ami:96', 'ami:143', 'ami:260', 'ami:286', 'ami:433', 'ami:434', 'ami:435', 'ami:441',
        'ami:442', 'blasters:11', 'blasters:12', 'boutique:N037/1', 'boutique:N037/2', 'boutique:N037/3',
        'boutique:N037/4', 'criminel:4', 'criminel:11', 'criminel:15', 'criminel:16', 'criminel:17', 'criminel:18',
        'criminel:25', 'criminel:26', 'criminel:27', 'criminel:32', 'criminel:40', 'requete:25', 'requete:66',
        'requete:112', 'requete:125', 'requete:153', 'requete:162', 'tablo:1', 'tablo:9', 'tablo:10',
    ),
    'canne_a_peche': (  # 68
        'ami:54', 'ami:60', 'ami:66', 'ami:96', 'ami:143', 'ami:260', 'ami:286', 'ami:335', 'ami:336', 'ami:337',
        'ami:338', 'ami:339', 'ami:340', 'ami:341', 'ami:342', 'ami:343', 'ami:345', 'ami:347', 'ami:431', 'ami:432',
        'ami:433', 'ami:434', 'ami:435', 'ami:441', 'ami:442', 'blasters:11', 'blasters:12', 'boutique:N004/10',
        'boutique:N004/8', 'boutique:N004/9', 'boutique:N024/1', 'boutique:N024/2', 'boutique:N024/3',
        'boutique:N024/4', 'boutique:N024/5', 'boutique:N024/6', 'boutique:N037/1', 'boutique:N037/2',
        'boutique:N037/3', 'boutique:N037/4', 'criminel:4', 'criminel:11', 'criminel:15', 'criminel:16',
        'criminel:17', 'criminel:18', 'criminel:25', 'criminel:26', 'criminel:27', 'criminel:32', 'criminel:40',
        'requete:5', 'requete:25', 'requete:29', 'requete:66', 'requete:104', 'requete:105', 'requete:106',
        'requete:112', 'requete:125', 'requete:153', 'requete:162', 'tablo:1', 'tablo:6', 'tablo:9', 'tablo:10',
        'tablo:11', 'tablo:12',
    ),
    'voyage_dans_le_temps': (  # 25
        'boss:didgeai', 'boss:taprice', 'boutique:N013/5', 'boutique:N020/5', 'criminel:7', 'criminel:8',
        'criminel:12', 'criminel:19', 'criminel:20', 'criminel:21', 'criminel:22', 'criminel:23', 'criminel:29',
        'criminel:36', 'criminel:37', 'criminel:41', 'criminel:45', 'criminel:46', 'criminel:47', 'criminel:52',
        'requete:41', 'requete:54', 'requete:62', 'requete:154', 'tablo:7',
    ),
    'lettre_de_komasan': (  # 34
        'boss:didgeai', 'boss:fumella', 'boss:taprice', 'boutique:N013/5', 'boutique:N020/5', 'criminel:7',
        'criminel:8', 'criminel:12', 'criminel:19', 'criminel:20', 'criminel:21', 'criminel:22', 'criminel:23',
        'criminel:29', 'criminel:36', 'criminel:37', 'criminel:41', 'criminel:45', 'criminel:46', 'criminel:47',
        'criminel:52', 'requete:10', 'requete:12', 'requete:41', 'requete:54', 'requete:59', 'requete:62',
        'requete:82', 'requete:86', 'requete:87', 'requete:154', 'requete:163', 'tablo:7', 'tablo:25',
    ),
    'bille_mysterieuse': (  # 33
        'boss:didgeai', 'boss:taprice', 'boutique:N013/5', 'boutique:N020/5', 'criminel:7', 'criminel:8',
        'criminel:12', 'criminel:19', 'criminel:20', 'criminel:21', 'criminel:22', 'criminel:23', 'criminel:29',
        'criminel:36', 'criminel:37', 'criminel:41', 'criminel:45', 'criminel:46', 'criminel:47', 'criminel:52',
        'requete:10', 'requete:11', 'requete:41', 'requete:54', 'requete:59', 'requete:62', 'requete:82',
        'requete:86', 'requete:87', 'requete:154', 'requete:163', 'tablo:7', 'tablo:25',
    ),
    'grelot_felin': (  # 35
        'boss:didgeai', 'boss:fumella', 'boss:taprice', 'boutique:N013/5', 'boutique:N020/5', 'criminel:7',
        'criminel:8', 'criminel:12', 'criminel:19', 'criminel:20', 'criminel:21', 'criminel:22', 'criminel:23',
        'criminel:29', 'criminel:36', 'criminel:37', 'criminel:41', 'criminel:45', 'criminel:46', 'criminel:47',
        'criminel:52', 'requete:10', 'requete:11', 'requete:12', 'requete:41', 'requete:54', 'requete:59',
        'requete:62', 'requete:82', 'requete:86', 'requete:87', 'requete:154', 'requete:163', 'tablo:7', 'tablo:25',
    ),
    'montre_de_luxe': (  # 35
        'boss:didgeai', 'boss:fumella', 'boss:taprice', 'boutique:N013/5', 'boutique:N020/5', 'criminel:7',
        'criminel:8', 'criminel:12', 'criminel:19', 'criminel:20', 'criminel:21', 'criminel:22', 'criminel:23',
        'criminel:29', 'criminel:36', 'criminel:37', 'criminel:41', 'criminel:45', 'criminel:46', 'criminel:47',
        'criminel:52', 'requete:10', 'requete:11', 'requete:12', 'requete:41', 'requete:54', 'requete:59',
        'requete:62', 'requete:82', 'requete:86', 'requete:87', 'requete:154', 'requete:163', 'tablo:7', 'tablo:25',
    ),
    'documents_perdus': (  # 24
        'ami:129', 'boss:crocho', 'criminel:3', 'criminel:6', 'criminel:9', 'criminel:24', 'criminel:28',
        'criminel:30', 'criminel:31', 'criminel:33', 'criminel:34', 'criminel:38', 'criminel:42', 'criminel:44',
        'criminel:49', 'emplacement:serviette_douce', 'requete:18', 'requete:26', 'requete:78', 'requete:80',
        'requete:156', 'requete:165', 'tablo:16', 'tablo:19',
    ),
    'capsules_de_lait': (  # 16
        'boss:demophage', 'boss:ombraptor', 'boss:sabrille', 'invite:287', 'requete:19', 'requete:20', 'requete:21',
        'requete:32', 'requete:35', 'requete:40', 'requete:46', 'requete:49', 'requete:58', 'requete:158',
        'requete:167', 'requete:168',
    ),
}
LOCATIONS_AVANT_ARRET_SUITE: Dict[Tuple[str, str], Tuple[str, ...]] = {}
for _k_aa, _locs_aa in AVANT_ARRET_SUITE.items():
    for _l_aa in _locs_aa:
        _cle_aa = tuple(_l_aa.split(":", 1))
        LOCATIONS_AVANT_ARRET_SUITE[_cle_aa] = LOCATIONS_AVANT_ARRET_SUITE.get(_cle_aa, ()) + (_k_aa,)
del _k_aa, _locs_aa, _l_aa, _cle_aa


def acces_objets_regions(connexions) -> Dict[str, set]:
    """Région -> objets des connexions du premier chemin trouvé depuis l'origine (comme `acces_z`)."""
    acces: Dict[str, set] = {REGION_ORIGINE: set()}
    change = True
    while change:
        change = False
        for s_c, c_c, r_c in connexions:
            if s_c in acces and c_c not in acces:
                acces[c_c] = acces[s_c] | set(r_c.objets)
                change = True
    return acces


def retires_avant_arret(loc, plan) -> set:
    """Objets d'arrêt que LOCATIONS_AVANT_ARRET(_SUITE) peut retirer de la règle de cette location du plan
    (interrupteurs ouverts, objets que sa région n'exige pas ; la garde des zones peut en garder) : pour les tests qui
    comparent une règle à celle d'un chapitre."""
    c = cle_avant_arret(loc)
    suite = set(LOCATIONS_AVANT_ARRET_SUITE.get(c, ())) if REGLES_AVANT_ARRET_SUITE else set()
    return (set(LOCATIONS_AVANT_ARRET.get(c, ())) if REGLES_AVANT_ARRET else set()) \
        | (suite - acces_objets_regions(plan.connexions).get(loc.region, set()))


def cle_avant_arret(loc) -> Tuple[str, str]:
    """Clé d'une location dans LOCATIONS_AVANT_ARRET(_SUITE) : (genre, clé) ; coffre : (\"coffre\", index TBox)."""
    return (loc.genre, str(loc.index_tbox)) if loc.genre == "coffre" else (loc.genre, loc.cle)

# Rangs de montre : exemplaires de « Rang de montre » exigés par « Chapitre N terminé » quand le verrou « rangs » est
# actif (objets_cles_v11 §17.3, audit de la logique). Les REQUÊTES CLÉS de l'histoire dépendent du rang [C :
# QUEST_NECESSARY_CONDITION des quêtes de chapitre 174 / 177 / 179 (type 9 = requête terminée, évaluateur FUN_0041908C) ;
# fins de phase 4-135, 7-20 et 9-60 de phase_set_cNN = phase suivante de la quête de chapitre] :
# - chapitre 7 (7-20) : requête 26 « Obtenons le rang B ! », dont les trois combats sont dans t121d03 et t121d11,
#   derrière les verrous de montre C de San Fantastico : 2 exemplaires ;
# - chapitre 9 (9-60) : requête 21, finie dans t231d05, derrière le verrou de montre A de t231d04 : 4 exemplaires ;
# - chapitre 4 (4-135) : requêtes 29 et 99, visibles seulement au rang réel >= D : rang donné par l'histoire (c03
#   n° 33), aucun exemplaire.
# Comme pour les objets critiques, la règle de « Chapitre N terminé » sert aussi aux locations « du chapitre N »
# (requêtes, boss, Tablo-blabla…) : plus stricte que le jeu pour elles, jamais moins. L'objectif les exige toutes.
# CHAPITRE_RANGS : ancien mode (rang D donné par l'histoire). CHAPITRE_RANGS_REEL : mode « rang réel » (§17.4) : le rang
# D ne vient plus de c03 n° 33 : le chapitre 4 exige 1 exemplaire (requêtes 29 et 99 absentes au rang E).
CHAPITRE_RANGS: Dict[int, int] = {7: 2, 9: 4}
CHAPITRE_RANGS_REEL: Dict[int, int] = {4: 1, 7: 2, 9: 4}
# Mode « rang réel », prudence : au rang E, les Yo-kai errants et de loupe soumis au rang sont absents (SET_PATH_POP
# « rang >= D », WM_PLACEMENT_DATA par rang : seules 7 cartes ont des placements au rang E [S]) ; le jeu d'origine
# garantit le rang D dès 3-190. Un check « Ami » d'une espèce de rang D ou plus (`chapitre` >= AMI_CHAPITRE_RANG_D,
# amis_criminels.py) exige 1 exemplaire (locations exclues : règle du tracker) ; les quêtes à Yo-kai visibles au rang E
# portent `rang="D"` dans QUETES (44, 64, 161). Boutique dont la carte a une porte « rang >= D » (GATE_ENTER_INFO_COND
# de t105i27 [C] ; porte mystère plutôt qu'entrée du bâtiment [S fort, §17.2]) : 1 exemplaire par prudence.
AMI_CHAPITRE_RANG_D = 2
# Mode « rang réel » : coffres « 3 chapitres » dont la zone ne s'ouvre qu'APRÈS l'arrêt 4-135 (requêtes 29 et 99, rang
# D) : 316..322 (Canyon de la cigale, Rochers de face, Mont de l'Ours : route t131g00 -> t131d03 fermée tant que
# phase <= 4-140 [S, archipelago_logique_audit.md]) : rang exigé par l'histoire pour y arriver (index TBox -> rang).
COFFRES_APRES_ARRET_RANG: Dict[int, str] = {i: "D" for i in range(316, 323)}
# Les mêmes coffres (après l'arrêt 4-135, dans les deux modes de rang) exigent la Canne à pêche quand son verrou est
# actif et qu'elle est mélangée : la phase 4-135 ne finit pas sans la requête clé 99, donc sans pêcher (§19).
COFFRES_APRES_ARRET_CANNE = frozenset(range(316, 323))
BOUTIQUES_RANG: Dict[str, str] = {"N013": "D"}

# Objets critiques de l'ancien mod (`regions.json`) retirés de « Chapitre N terminé » (archipelago_logique_audit.md G4) :
# - Canne à pêche (chapitre 4) : N'EST PLUS retirée (ap/canne-reelle, 2026-10-02) : le retrait de l'audit G4 (« aucune
#   séquence d'histoire ne pêche ») était faux, la requête 99 est une requête clé du chapitre 4 (CHAPITRE_BLOQUE_PAR).
# - Modèle zéro (chapitre 6, repaire) : retirée le 2026-11-05 (RETRAIT_MODELE_ZERO, ci-dessus) ; elle restait exigée
#   « par prudence » (un seul combat validé en jeu avec l'ancienne interface), sans aucun lecteur d'histoire.
# - Pile ou passe (chapitre 1) : exigée à partir de 2-70 seulement (CHAPITRE_BLOQUE_PAR : chapitre 2) ; au chapitre 1, elle
#   rendait la règle de son propre emplacement circulaire (objets_cles §14.4).
# - Clés de l'école (chapitre 2) : données au chapitre 3 (c03_trigger Phase3) et exigées seulement à partir de 3-40 ;
#   désormais portées par CHAPITRE_BLOQUE_PAR (chapitre 3) et les connexions de Coteau fleuri et du Quartier des
#   boutiques (archipelago_logique_audit.md §5 : l'exigence du chapitre 2 était trop stricte ; 2026-10-01).
CRITIQUES_RETIRES: Dict[int, Tuple[str, ...]] = {1: ("pile_ou_passe",), 2: ("cles_de_l_ecole",)}

# Pile ou passe (objets_cles §14) : objet exigé par tout ce qui suit la phase 2-60. Les règles « N chapitres » (N >= 2) et
# celles qui reprennent la règle du chapitre 2 (boutiques, requêtes, Tablo-blabla, amis, check « chapitre 2 terminé ») la
# contiennent déjà ; les coffres « 1 chapitre » l'exigent en plus, sauf ceux que le jeu ouvre dès 2-10 (OP_TBOX_POINT de
# t101g00, GetPhase >= 20010 [C], COFFRES_CHAPITRES_MIN) ; son emplacement (2-50) ne l'exige jamais.
OBJET_PILE = "pile_ou_passe"
COFFRES_AVANT_TUTORIEL_PILE = frozenset(range(1, 12))
# V3, lot 20 (pieces.py) : les règles « k exemplaires » des checks des pièces spéciales. Interrupteur d'AUDIT
# seulement (`audit_logique.py --pieces --sans-regles` le ferme pour montrer que son modèle contredit une logique sans
# ces règles) : toujours vrai ailleurs.
REGLES_PIECES = True

# Objets dont dépend le rang D de la montre (donné par c03_trigger n° 33, après les n° 21 et 27) quand leur verrou
# est actif : exigés par toute location derrière un verrou de montre (coffres du Manoir, COFFRES_VERROU_DE_MONTRE ;
# filtrés comme partout). Sans objet en mode « rang réel » (le rang D est le premier « Rang de montre » reçu).
OBJETS_RANG_D = ("herbe_ancestrale", "super_tournevis")

# ---------------------------------------------------------------------------
# Emplacements d'objets-clés (dons d'évènement, CONCEPTION §3.2)
# ---------------------------------------------------------------------------
# bit : bit TBox persistant posé par la substitution (J1 §5, R7) ; chapitres : chapitres terminés avant le
# don (script `cNN_trigger` du chapitre NN : NN − 1) [C] ; dons de quête : chapitre d'apparition de la quête et rang
# de montre exigé (`rang_reel` ; représenté par le chapitre ; avec le verrou « rangs », exemplaires de exemplaires_pour), vérifiés sur le
# RomFS (archipelago_couverture.md R1 : l'ancienne borne « 9 chapitres » ne les mettait en logique qu'au chapitre 10,
# ville bouclée). Aucun ne dépend de son propre objet : la Clé de derrière est donnée à l'entrée de t103d31 (Manoir,
# derrière le verrou D), avant les portes de la Clé et des jolies clés ; la Clé salle du trésor au point de la loupe,
# avant la porte qui la teste ; la Poignée après un combat de t105d45, avant son usage dans t105d41. Ces emplacements ne reçoivent que du
# remplissage quand leur objet est mélangé (`progression_permise`, ancien mod), sauf celui du Filet.
# Bits de check des dons RÉPÉTABLES sans marqueur (cinq PNJ du Musée) : tant que le bit n'est pas posé, le jeu lit l'objet
# d'origine « non possédé » (IsHaveItem), pour que le PNJ donne même si l'objet d'Archipelago est déjà là ; la remise au
# musée attend donc le check du PNJ : la règle de la requête 40 doit dominer celles de ces emplacements (objets_cles_v11
# §19.3, test_capacites_reelles). Mêmes bornes que AP_TBOX_REPETABLE_* (boite.h).
TBOX_REPETABLES = (571, 575)
EMPLACEMENTS: Dict[str, dict] = {
    "filet_a_insectes": {"bit": 558, "chapitres": 0},       # c01_trigger RunCmd_Phase16 [C]
    "pile_ou_passe": {"bit": 559, "chapitres": 1},          # c02_trigger RunCmd_Phase11 [C]
    "cles_de_l_ecole": {"bit": 560, "chapitres": 2},        # c03_trigger RunCmd_Phase3 [C]
    "herbe_ancestrale": {"bit": 561, "chapitres": 2, "apres": ("cles_de_l_ecole",)},   # c03 Phase20 [C]
    # c03 Phase26 [C] : exige ev60_0500 <- ev03_1500 <- ev03_1400 (n° 21, consomme l'Herbe)
    "super_tournevis": {"bit": 562, "chapitres": 2, "apres": ("cles_de_l_ecole", "herbe_ancestrale")},
    # quête 99 (>= 4-135, rang D) à Ourcival (t131g00), atteinte par le train (>= 4-70) : Indications [C] (audit G2-3)
    # (V3, lot 11 : la requête 99 est à Ourcival : le Train, filtré quand son verrou n'est pas actif)
    "canne_a_peche": {"bit": 563, "chapitres": 3, "apres": ("indications_de_maman", "train"), "rang_reel": "D"},
    "modele_zero": {"bit": 564, "chapitres": 5},            # c06_trigger RunCmd_Phase1 [C]
    "indications_de_maman": {"bit": 565, "chapitres": 3},   # c04_trigger RunCmd_Phase10..13 [C]
    # quête 54 (>= 5-10, rang C, quête 53 finie ; comme Didgeai) : don de nuit, phase 3, t103d31_quest_trigger n° 5 [C] ;
    # rangs : verrou D (Manoir) et rang réel C (objets_cles_v11 §14.8)
    "cle_de_derriere": {"bit": 566, "chapitres": 4, "rang_reel": "C", "verrou_montre": "D"},
    # quête 53 (>= 3-10, sans rang) : fin de quête dans les égouts, t100d00_quest_trigger n° 6 [C]
    "cle_magnetique_or": {"bit": 567, "chapitres": 2},
    # quête 51 (>= 6-10, rang C, quête 50 finie) : point de la loupe (Filet), t102d31_quest_trigger n° 4 [C]
    "cle_salle_du_tresor": {"bit": 568, "chapitres": 5, "rang_reel": "C"},
    # quête 57 (>= 8-10, rang A, quête 56 finie ; comme Firmain) : après un combat, t105d45_quest_trigger n° 5 [C] ;
    # Clinique du Crépuscule (verrou B de t105g00)
    "poignee_etrange": {"bit": 569, "chapitres": 7, "rang_reel": "A", "verrou_montre": "B"},
    # -- objets-clés de quête (branche ap/objets-cles-quetes, objets_cles_v11 §16) : dons par 0x3B0D (substitution J3),
    # testés par possession ; emplacements EXCLUS (remplissage seulement), règles prudentes. Détection : bit de la
    # réserve 571..575 pour les dons répétables sans marqueur (PNJ qui redonnent l'objet tant qu'il n'est ni possédé ni
    # exposé), sinon marqueur persistant posé par le même script (`flag` : flag bit global ; `quete` : quête à 255),
    # lu par le client comme un boss (entrée de `boss` de slot_data) ; sans bit, la table des dons de script reçoit
    # l'entrée avec AP_SCRIPT_BIT_AUCUN.
    # t100d00_trigger n° 22 (PNJ des égouts, après les dix vannes) : flag 580 (0xB5438FE3) posé juste avant AddItem [C] ;
    # les dix grilles à sens unique ne s'ouvrent que depuis les secteurs de TOUTES les entrées des égouts, dont le
    # Centre-ville (4-50 : 3 chapitres, Indications), le Quartier des boutiques (Herbe, Clés) et le Coteau fleuri (Clés)
    # [S fort] (archipelago_logique_audit.md §3 G1-7)
    "cle_magnetique_rouge": {"flag": 580, "chapitres": 3, "apres": ("pile_ou_passe", "indications_de_maman",
                                                                    "herbe_ancestrale", "cles_de_l_ecole")},
    # t201g00_quest_trigger n° 107 / 108 / 109 (PNJ de Vieux Granval, AddItemWin, sans condition de quête ; répétables
    # tant que l'objet n'est ni possédé ni exposé) [C] : Vieux Granval (4 chapitres)
    # (V3, lot 11 : PNJ de Vieux Granval : Train et Voyage dans le temps, filtrés quand leur verrou n'est pas actif)
    "poster_de_film": {"bit": 571, "chapitres": 4, "apres": ("train", "voyage_dans_le_temps")},
    "bobine_de_film": {"bit": 572, "chapitres": 4, "apres": ("train", "voyage_dans_le_temps")},
    "bouteille_de_y_cola": {"bit": 573, "chapitres": 4, "apres": ("train", "voyage_dans_le_temps")},
    # t104g00_quest_trigger n° 1 (PNJ du Centre-ville, AddItemWin, répétable) [C] : Centre-ville (Indications)
    "affiche_de_restaurant": {"bit": 574, "chapitres": 3, "apres": ("indications_de_maman",)},
    # t105i35_quest_trigger n° 4 (boutique de nuit du Quartier des boutiques, AddItemWin, répétable) [C]
    "louloutre": {"bit": 575, "chapitres": 2, "apres": ("herbe_ancestrale", "cles_de_l_ecole")},
    # t102d03_quest_trigger n° 1 (quête 50, phase 4, la nuit : AddItem, puis phase 5) ; détection à la fin de la quête 50
    # (aucun flag posé ; la quête finit sans l'objet) [C] ; quête 50 : >= 3-10, rang D (après le Tournevis)
    "pot_canard": {"quete": 50, "chapitres": 3, "rang_reel": "D"},
    # t106i02_quest_trigger n° 12 : AddItem puis QuestComplete('qs0048') dans le même script [C] ; quête 48 (rang B)
    # (V3, lot 9 : ce script est la remise du Robot mécanique usé, après celle du Robot rétro neuf : filtrés sinon)
    "figurine_de_photortue": {"quete": 48, "chapitres": 7, "rang_reel": "B",
                              "apres": ("robot_retro_neuf", "robot_mecanique_use")},
    # t104g00_quest_trigger n° 22 : AddItem puis QuestCompleteEx('qs0065') dans le même script [C] ; quête 65 (rang B)
    "robe_de_star": {"quete": 65, "chapitres": 7, "rang_reel": "B"},
}
# Emplacements détectés sans bit de la réserve (flag ou quête) : pas d'index TBox, bit « aucun » dans la table des
# dons de script (AP_SCRIPT_BIT_AUCUN, boîte §12.1).
BIT_SCRIPT_AUCUN = 0xFFFF

# ---- V3 (lot 1) : emplacements des objets à verrou étendu (objets_cles_v11 §20). Hors de `emplacements_objets_cles.json`
# (dont toutes les entrées sont des locations de toute graine) : ces locations n'existent que si le verrou de l'objet
# est actif. Dons de script par 0x3B0D (substitution J3 par hachage), sans bit de la réserve (558..575 tous pris) :
# - Yo-kai Watch : c01_trigger n° 35 (garçon, iky0001) / 36 (fille, iky0002), phase 1-90, AddItem sans fenêtre, juste
#   après RunEvent('ev01_1700') dans la même fonction : marqueur = flag 123 « ev01_1700 vu » (seul écrivain : RunEvent ;
#   jamais remis à 0) [C]. Deux hachages d'origine (`hachages`) : un seul est donné dans une partie. Avant le premier
#   combat du jeu (1-140) et après le don du Filet (1-30).
#   L'objet AP donne l'objet du jeu (celui du personnage joué, choisi par le jeu) : lu par 0x0040E7AC (inventaire).
# - Documents perdus : t103g00_quest_trigger n° 6 (dialogue, qs0009 en phase 7 : AddItemWin puis phase 8) : marqueur =
#   phase de qs0009 >= 8 (8 puis 255, jamais moins) [C]. Requête clé du chapitre 7 (>= 7-20).
# - Cartes d'Ultramax : t131g00_quest_trigger n° 7 (point de recherche d'Ourcival, qs0014 en phase 3 : AddItem,
#   ev06_0700, phase 4) : marqueur = phase de qs0014 >= 4 [C]. Requête clé du chapitre 6 (== 6-40) ; loupe : Filet.
# L'objet AP de ces deux-là donne le vrai objet du jeu (don « objet ») : le script de remise le retire (DeleteItem).
# Comme les autres emplacements d'objets mélangés (sauf le Filet), ils ne reçoivent que du remplissage (EXCLUS).
# Noms anglais relus sur la ROM européenne (archive `engb`), saisis à la main.
EMPLACEMENTS_V3: Dict[str, dict] = {
    "yokai_watch": {"id_ap": 59422730, "nom_fr": "Objet-clé : Yo-kai Watch", "nom_en": "Key Item: Yo-kai Watch",
                    "flag": 123, "chapitres": 0, "hachages": (0x4F6B8097, 0xD662D12D), "progression_permise": False},
    "documents_perdus": {"id_ap": 59422731, "nom_fr": "Objet-clé : Documents perdus",
                         "nom_en": "Key Item: Critical Lost Item", "quete": 9, "phase_min": 8, "chapitres": 6,
                         "progression_permise": False},
    "cartes_ultramax": {"id_ap": 59422732, "nom_fr": "Objet-clé : Cartes d'Ultramax",
                        "nom_en": "Key Item: Moximous Game", "quete": 14, "phase_min": 4, "chapitres": 5,
                        "apres": ("filet_a_insectes",), "progression_permise": False},
    # ---- V3, lot 9 (docs/systemes/archipelago_v3_objets_cles_apworld.md ; tables des lots 5 et 7). Même forme ; règle :
    # - `chapitres` (+ `apres`) : chapitres terminés avant le don, objets exigés avant lui ;
    # - `regle_quete` : n : règle de la requête n SANS l'objet lui-même ni ceux de `sans` (que la requête n'exige
    #   qu'après ce don), dans la région de la requête ;
    # - `regle_chapitre` : n : règle de « Chapitre n terminé ».
    # Chapitre 5 (requêtes clés 10, 11, 12, toutes en 5-110) : la règle de « Chapitre 5 terminé » exige les quatre
    # objets (CHAPITRE_BLOQUE_PAR) : ces emplacements ne la reprennent donc pas (« 4 chapitres terminés », sans cycle) :
    # - Lettre de Komasan : point de recherche de t201d01 (qs0011 phase 4 -> 5) : marqueur = phase de qs0011 >= 5 ;
    # - Bille mystérieuse : PNJ de t201g00 (qs0012 phase 3 -> 4) : marqueur = phase de qs0012 >= 4 ;
    # - Grelot félin : fin de la requête 11 (t202g00_quest n° 4, avec QuestComplete) : marqueur = qs0011 à 255 ; la
    #   remise de la Lettre le précède : l'emplacement exige la Lettre (pas le Grelot, exigé seulement en 5-130) ;
    # - Montre de luxe : fin de la requête 10 (t201i03_quest n° 2, avec QuestComplete) : marqueur = qs0010 à 255 ; aucun
    #   verrou ne ferme la requête 10 (ni la Bille, qui ferme la 12) : sans objet.
    # (V3, lot 11 : ces cinq emplacements sont dans le passé (t201d01, t201g00, t202g00, t201i03, t231g00) : ils exigent
    # le Voyage dans le temps et le Train quand ces verrous sont actifs ; sans cycle : ni l'un ni l'autre n'exige un de
    # ces objets, et « Passage du temps » (5-90) n'exige pas le Voyage)
    "lettre_de_komasan": {"id_ap": 59422737, "nom_fr": "Objet-clé : Lettre de Komasan",
                          "nom_en": "Key Item: Komasan's Letter", "quete": 11, "phase_min": 5, "chapitres": 4,
                          "apres": ("train", "voyage_dans_le_temps"), "progression_permise": False},
    "bille_mysterieuse": {"id_ap": 59422738, "nom_fr": "Objet-clé : Bille mystérieuse",
                          "nom_en": "Key Item: Mysterious Marble", "quete": 12, "phase_min": 4, "chapitres": 4,
                          "apres": ("train", "voyage_dans_le_temps"), "progression_permise": False},
    # Capsules de lait : point de recherche de t231g00 (c06_trigger n° 4, phase 6-30), AddItem puis ev06_0300 dans la
    # même fonction : marqueur = flag 273 « ev06_0300 vu » (lu par le n° 5, condition de fin de la phase 6-30) [C]
    "capsules_de_lait": {"id_ap": 59422739, "nom_fr": "Objet-clé : Capsules de lait",
                         "nom_en": "Key Item: Milk Bottle Tops", "flag": 273, "chapitres": 5,
                         "apres": ("train", "voyage_dans_le_temps"), "progression_permise": False},
    "grelot_felin": {"id_ap": 59422740, "nom_fr": "Objet-clé : Grelot félin", "nom_en": "Key Item: Swirly Bell",
                     "quete": 11, "chapitres": 4, "apres": ("lettre_de_komasan", "train", "voyage_dans_le_temps"),
                     "progression_permise": False},
    "montre_de_luxe": {"id_ap": 59422741, "nom_fr": "Objet-clé : Montre de luxe",
                       "nom_en": "Key Item: Top-Notch Watch", "quete": 10, "chapitres": 4,
                       "apres": ("train", "voyage_dans_le_temps"), "progression_permise": False},
    # Miroirs : pas de don à substituer (le jeu met les miroirs en service en 4-160, PhCmd_4_160) : marqueur = flag
    # 1777 (miroir de t131i01, posé par PhCmd_4_160 seulement, jamais remis à 0) ; 4-160 suit l'arrêt de 4-135 :
    # règle de « Chapitre 4 terminé » (plus stricte de la fin du chapitre, jamais moins)
    "miroirs": {"id_ap": 59422742, "nom_fr": "Objet-clé : Miroirs", "nom_en": "Key Item: Mirapo",
                "flag": 1777, "regle_chapitre": 4, "progression_permise": False},
    # Objets de requêtes facultatives : le don précède la remise ; marqueur = phase de la requête
    "ceinture_de_force": {"id_ap": 59422743, "nom_fr": "Objet-clé : Ceinture de force",
                          "nom_en": "Key Item: Muscle Belt", "quete": 44, "phase_min": 3, "regle_quete": 44,
                          "progression_permise": False},
    "robot_retro_neuf": {"id_ap": 59422744, "nom_fr": "Objet-clé : Robot rétro neuf",
                         "nom_en": "Key Item: New Retro Robot", "quete": 48, "phase_min": 4, "regle_quete": 48,
                         "sans": ("robot_mecanique_use",), "progression_permise": False},
    # (don en phase 6 -> 7, après la remise du Robot rétro neuf en phase 5 : l'emplacement exige le Robot neuf)
    "robot_mecanique_use": {"id_ap": 59422745, "nom_fr": "Objet-clé : Robot mécanique usé",
                            "nom_en": "Key Item: Old Retro Robot", "quete": 48, "phase_min": 7, "regle_quete": 48,
                            "progression_permise": False},
    "serviette_douce": {"id_ap": 59422746, "nom_fr": "Objet-clé : Serviette douce",
                        "nom_en": "Key Item: Fluffy Towel", "quete": 80, "phase_min": 5, "regle_quete": 80,
                        "progression_permise": False},
    "dance_revolution": {"id_ap": 59422747, "nom_fr": "Objet-clé : Dance Revolution",
                         "nom_en": "Key Item: Dance Revolution", "quete": 98, "phase_min": 10, "regle_quete": 98,
                         "progression_permise": False},
    # Carte à tamponner : donnée à l'ACCEPTATION de la requête 90 (t100s17_quest n° 2 : AddItemWin puis QuestAccept) :
    # marqueur = phase de qs0090 >= 2 [S : valeur posée par l'acceptation, à confirmer en jeu, essai T-L7-8]
    "carte_a_tamponner": {"id_ap": 59422748, "nom_fr": "Objet-clé : Carte à tamponner",
                          "nom_en": "Key Item: Stamp Card", "quete": 90, "phase_min": 2, "regle_quete": 90,
                          "progression_permise": False},
    # ---- V3, lot 11 : Voyage dans le temps. Pas de don à substituer (aucun objet du jeu) : marqueur = flag 264
    # « ev05_1100 vu » (rencontre du Yo-kai du passage, c05_trigger n° 8, phase 5-90 ; un seul écrivain, jamais remis à
    # 0 [C]) : entrée `{location, flag}` de `boss`, comme les Miroirs. Le joueur y est par envoi scénarisé (5-10), sans
    # le passage : règle « 4 chapitres terminés » (+ le Train, exigé par 4-60), SANS le Voyage, hors des régions du passé.
    OBJET_VOYAGE: {"id_ap": 59422749, "nom_fr": "Passage du temps", "nom_en": "Time Passage",
                   "flag": 264, "chapitres": 4, "apres": (OBJET_TRAIN,), "progression_permise": False},
}

# ---------------------------------------------------------------------------
# Boss d'histoire (docs/systemes/archipelago_boss.md §3.1, §4.1, §5)
# ---------------------------------------------------------------------------
# Check = flag bit global du combat, posé par le moteur à la VICTOIRE seulement (FUN_005A65C4 ->
# FUN_00413464), persistant ; le client le lit dans P (bit i % 8 de l'octet P + 4 + i / 8). Identifiants AP et
# noms de l'ancien mod (compatibilité du tracker) ; Laure et Marge : deux locations, un seul combat (flag 277).
# Règle = celle de « Chapitre N terminé » du chapitre du boss (exacte pour les boss qui terminent un chapitre,
# plus stricte pour les autres). Correction de l'ancien mod : Cyrustre, Fielippine, Maudicko, Ronéan au
# chapitre 10 (pas 9). Région : celle de l'ancien mod quand son accès est déjà impliqué par la règle ; Lady
# Perpétua en Vieux Granval (le Repaire exige 10 chapitres dans les données). Lady Démona = la victoire
# (check envoyé en même temps que l'objectif) : règle de l'objectif, location exclue de la progression.
BOSS_HISTOIRE: List[dict] = [
    {"cle": "grolos", "id_ap": 59420100, "nom_fr": "Boss : Grolos", "nom_en": "Boss: Gutsy Bones",
     "flag": 208, "chapitre": 3, "region": "les_hauts_de_granval"},
    {"cle": "meganyan", "id_ap": 59420101, "nom_fr": "Boss : Méganyan", "nom_en": "Boss: Meganyan",
     "flag": 251, "chapitre": 4, "region": "ourcival"},
    {"cle": "laure", "id_ap": 59420103, "nom_fr": "Boss : Laure", "nom_en": "Boss: Kin",
     "flag": 277, "chapitre": 6, "region": "san_fantastico"},
    {"cle": "marge", "id_ap": 59420104, "nom_fr": "Boss : Marge", "nom_en": "Boss: Gin",
     "flag": 277, "chapitre": 6, "region": "san_fantastico"},
    {"cle": "tourboeillon", "id_ap": 59420105, "nom_fr": "Boss : Tourbœillon", "nom_en": "Boss: Eyeclone",
     "flag": 292, "chapitre": 7, "region": "les_hauts_de_granval"},
    {"cle": "injustin", "id_ap": 59423010, "nom_fr": "Boss : Injustin", "nom_en": "Boss: Unfairy",
     "flag": 333, "chapitre": 9, "region": "vieux_granval"},
    {"cle": "cyrustre", "id_ap": 59423012, "nom_fr": "Boss : Cyrustre", "nom_en": "Boss: Untidy",
     "flag": 348, "chapitre": 10, "region": "vieux_granval"},
    {"cle": "fielippine", "id_ap": 59423011, "nom_fr": "Boss : Fielippine", "nom_en": "Boss: Unkaind",
     "flag": 351, "chapitre": 10, "region": "vieux_granval"},
    {"cle": "maudicko", "id_ap": 59423013, "nom_fr": "Boss : Maudicko", "nom_en": "Boss: Unpleasant",
     "flag": 354, "chapitre": 10, "region": "vieux_granval"},
    {"cle": "ronean", "id_ap": 59423014, "nom_fr": "Boss : Ronéan", "nom_en": "Boss: Unkeen",
     "flag": 358, "chapitre": 10, "region": "vieux_granval"},
    {"cle": "lady_perpetua", "id_ap": 59420106, "nom_fr": "Boss : Lady Perpétua", "nom_en": "Boss: Dame Dedtime",
     "flag": 372, "chapitre": 10, "region": "vieux_granval"},
    {"cle": "lady_demona", "id_ap": 59420107, "nom_fr": "Boss : Lady Démona", "nom_en": "Boss: Dame Demona",
     "flag": 377, "chapitre": 10, "region": "repaire_de_lady_demona", "victoire": True},
]

# ---------------------------------------------------------------------------
# Boss de quête (docs/systemes/archipelago_boss.md §3.2, §10)
# ---------------------------------------------------------------------------
# Check = quête terminée : phase 255, octet Q + 4 + n du bloc des quêtes Q = *(*0x00815244 + 0x10) (lu par le
# client, aucun changement du jeu), n = 4e champ de QUEST_CONFIG (nom « qs%04d ») [C] ; 255 n'est posé qu'après la
# victoire contre le boss (déclencheur 78, ou rapport conditionné par une phase que seule la victoire donne) [C,
# §10.2], sauf Firmain [S fort : drapeau temporaire générique entre la victoire et le rapport].
# chapitre = max(chapitre d'apparition de la quête, chapitre où le rang de montre exigé s'obtient : C dès 4-10,
# B dès 7-20, A dès 8-10, quêtes 25/26/27 de t103i21 [C]) ; règle = celle de « Chapitre N terminé » (plus stricte
# que le jeu, jamais moins) + objets testés par possession, ou verrouillés par le patch, sur le chemin de la quête
# et des quêtes qu'elle exige finies (`objets`, filtrés comme partout : un objet non mélangé est donné par la quête
# elle-même et n'est pas exigé ; Clé salle du trésor pour les quêtes 51 et 52, Poignée étrange pour les quêtes 57
# et 58, verrous de déclencheur de quête de la V1.1, objets_cles_v11 §13). Rangs : le chapitre représente le rang
# RÉEL (`rang_reel`) ; avec le verrou « rangs » (V1.1, objets_cles_v11 §14), la règle exige aussi les exemplaires de
# « Rang de montre » du rang réel (requête de rang C : 1, B : 2, A : 3) et des verrous de montre sur le chemin de la quête
# (`verrou_montre` : Clinique du Crépuscule, verrou B de t105g00, pour les quêtes 57 et 58 ; t231d05, derrière le
# verrou A de t231d04, pour la quête 21) [C, conditions GetQuestPhase des cartes fermées]. Identifiants et noms de
# l'ancien mod.
# Tromplœil : donjon des portails (quête 6 finie + progression du donjon, ancien mod : 100 globes de portail) non
# modélisable : location EXCLUE (remplissage seulement), règle prudente du chapitre 4.
BOSS_QUETES: List[dict] = [
    {"cle": "barbefrousse", "id_ap": 59420102, "nom_fr": "Boss : Barbefrousse", "nom_en": "Boss: Cap'n Crash",
     "quete": 16, "chapitre": 6, "region": "san_fantastico"},                   # quête d'histoire, phase == 6-40
    {"cle": "didgeai", "id_ap": 59423002, "nom_fr": "Boss : Didgeai", "nom_en": "Boss: Chirpster",
     "quete": 54, "chapitre": 5, "region": "coteau_fleuri",                     # >= 5-10, rang C, quête 53
     "objets": ("cle_de_derriere", "jolie_petite_cle", "jolie_grande_cle"),      # portes de t103g00 (IsHaveItem)
     "rang_reel": "C"},
    {"cle": "sabroclair", "id_ap": 59423003, "nom_fr": "Boss : Sabroclair", "nom_en": "Boss: Phantasmurai",
     "quete": 7, "chapitre": 8, "region": "la_corniche", "rang_reel": "B"},    # >= 8-10, rang B
    {"cle": "ombraptor", "id_ap": 59423004, "nom_fr": "Boss : Ombraptor", "nom_en": "Boss: Massiface",
     "quete": 58, "chapitre": 9, "region": "centre_ville_de_granval",          # >= 9-10, rang A, quête 57
     "objets": ("poignee_etrange",),                                            # quête 57 finie (QUEST_CONFIG)
     "rang_reel": "A", "verrou_montre": "B"},                                   # quête 57 : Clinique
    {"cle": "inamygal", "id_ap": 59423005, "nom_fr": "Boss : Inamygal", "nom_en": "Boss: Tarantutor",
     "quete": 56, "chapitre": 6, "region": "les_hauts_de_granval",             # >= 6-60, rang C
     "rang_reel": "C"},
    {"cle": "volteface", "id_ap": 59423006, "nom_fr": "Boss : Volteface", "nom_en": "Boss: Duwheel",
     "quete": 51, "chapitre": 6, "region": "mont_sylvestre",                    # >= 6-10, rang C, quête 50
     "objets": ("cle_salle_du_tresor",), "rang_reel": "C"},                     # verrou t102d31 n° 5 (v11 §13)
    {"cle": "misterre", "id_ap": 59423007, "nom_fr": "Boss : Misterre", "nom_en": "Boss: Dromp",
     "quete": 52, "chapitre": 8, "region": "mont_sylvestre",                    # >= 8-10, rang A, quête 51
     "objets": ("huile_de_tendino", "cle_salle_du_tresor"),                     # t102d32 (IsHaveItem) ; quête 51 finie
     "rang_reel": "A"},
    {"cle": "firmain", "id_ap": 59423008, "nom_fr": "Boss : Firmain", "nom_en": "Boss: Hans Full",
     "quete": 57, "chapitre": 8, "region": "quartier_des_boutiques",            # >= 8-10, rang A, quête 56
     "objets": ("poignee_etrange",),                                            # verrou t105d41 n° 7 (v11 §13)
     "rang_reel": "A", "verrou_montre": "B"},                                   # Clinique (t105g00, verrou B)
    {"cle": "demophage", "id_ap": 59423009, "nom_fr": "Boss : Démophage", "nom_en": "Boss: Demuncher",
     "quete": 21, "chapitre": 9, "region": "vieil_ourcival",                    # phase == 9-60 ; acceptée dans t231d04,
     "rang_reel": "A", "verrou_montre": "A"},                                   # finie dans t231d05 (verrou A)
    # quête 80 : QUEST_CONFIG exige aussi GetGlobalBitFlag(2103) == 1 = « Yo-kai appelé » du Tablo-blabla n° 8
    # (TERRITORY_INFO T7 de territory_0.01j, Coteau fleuri) : posséder ET appeler un Yo-kai précis, non modélisable
    # [C] : location EXCLUE (remplissage seulement ; archipelago_tablos.md, archipelago_logique_audit.md)
    {"cle": "crocho", "id_ap": 59423015, "nom_fr": "Boss : Crocho", "nom_en": "Boss: Sproink",
     "quete": 80, "chapitre": 7, "region": "coteau_fleuri", "rang_reel": "B",  # >= 7-10, rang B
     "objets": ("serviette_douce",),    # V3, lot 9 : remise de la Serviette douce (verrou k = 57, filtré sinon)
     "exclue": True},
    {"cle": "tromploeil", "id_ap": 59423016, "nom_fr": "Boss : Tromplœil", "nom_en": "Boss: Eyephoon",
     "quete": 8, "chapitre": 4, "region": "la_corniche", "exclue": True,        # donjon des portails
     "objets": ("canne_a_peche",)},     # règle de l'ancien mod gardée (aussi exigée par le chapitre 4, §19)
]

# ---------------------------------------------------------------------------
# Boss du mélange qui n'étaient pas des checks (docs/systemes/archipelago_boss.md §11 ; demande de l'humain du
# 2026-10-09 : « mets tous les boss qui sont dans le mélange »)
# ---------------------------------------------------------------------------
# Les 23 locations ci-dessus viennent de l'ancien mod ; la table du mélange des boss (client/rando_boss.py) a 6 autres
# boss d'AVANT la fin du jeu (les 23 boss d'après-jeu ou du réseau caché, HORS_PERIMETRE, et les deux requêtes de
# transfert de données, Triptyk q108 / Carpitaine q113, ne sont pas des checks). Mode « tous » de l'option `boss`
# seulement : les modes existants gardent exactement leurs locations. Identifiants nouveaux (59423017.., plage 3000-3099
# « évènements détectés par flag » de l'ancien mod, libre au-delà de 3016) ; noms saisis à la main (règle 6).
# - Fumella (place 0x925152B3, MÉLANGÉE : boss sans script) : combat de la requête CLÉ 12 du chapitre 5 (phase ==
#   5-110, exigée par la quête de chapitre qm0005 : QUEST_NECESSARY_CONDITION type 9) ; flag bit global 1208 du hachage
#   de la rencontre, posé par le moteur seul à la victoire (jamais écrit par un script) [C] ; règle du chapitre 5.
# - Draconfus (0x80F13DB5, figé) et Faux Kappa (0xABDC6E76, figé) : combats des requêtes CLÉS 15 et 17 du chapitre 6
#   (phase == 6-40, type 9 de qm0006), sans flag de combat : check = quête à 255, comme Barbefrousse (requête 16 de la
#   même série). Requête 15 : la victoire (t107i01 n° 5, type 78) donne la phase 5, que seul un dialogue en phase 5
#   mène à 6 puis un autre en phase 6 à 255 ; requête 17 : la victoire (t131g00 n° 24 / 25, type 78) termine la quête
#   [C]. Règle du chapitre 6 (5 chapitres + Modèle zéro).
# - Sabrille (0x5F48F264, figée, étape 9-20, flag 327) et Anguigne (0x1C292F01, figée, étape 10-20, flag 341) : combats
#   d'histoire ; flag écrit par le moteur et par le script de victoire seulement, condition de fin de l'étape
#   (phase_set_c09 / c10), jamais remis à 0 [C] ; règles des chapitres 9 et 10.
# - Taprice (0xBDE7A020, MÉLANGÉ, classe 2) : fin du Tunnel sans fin (t131d33). Aucun flag de ce hachage ; la victoire
#   (t131d33_trigger n° 6, type 78) pose l'octet global de progression du tunnel (catégorie 6, index 73, hachage
#   0x8920FFE7 : P + 0x144 + 73) à 6 ; il vaut 0..5 avant (une arrivée au bout du tunnel par valeur), puis ne fait que
#   croître (7..20, 255) : check = octet >= 6 (entrée {location, octet, seuil} de `boss`, client à jour exigé par les
#   n° 22 et 64 de `fonctions_exigees`) [C]. Entrée du tunnel : point de recherche de t131g00 (GetPhase >= 4-160, une
#   fois par JOUR DU JEU : flag 2528 remis à 0 par le changement de jour, pas par l'horloge réelle) ; il faut cinq
#   traversées complètes avant le combat : LONG, location EXCLUE et marquée (PORTAIL_TUNNEL), règle de 4 chapitres
#   terminés (plus stricte que 4-160).
# Le check suit la PLACE (hachage de la rencontre) quel que soit le boss qui l'occupe : les marqueurs viennent tous du
# moteur ou des déclencheurs 78 de ce hachage (archipelago_rando_boss.md §2.4).
BOSS_MELANGE: List[dict] = [
    {"cle": "fumella", "id_ap": 59423017, "nom_fr": "Boss : Fumella", "nom_en": "Boss: Badsmella",
     "flag": 1208, "chapitre": 5, "region": "vieux_granval"},
    {"cle": "draconfus", "id_ap": 59423018, "nom_fr": "Boss : Draconfus", "nom_en": "Boss: Draaagin",
     "quete": 15, "chapitre": 6, "region": "ourcival"},
    {"cle": "faux_kappa", "id_ap": 59423019, "nom_fr": "Boss : Faux Kappa", "nom_en": "Boss: Faux Kappa",
     "quete": 17, "chapitre": 6, "region": "ourcival"},
    {"cle": "sabrille", "id_ap": 59423020, "nom_fr": "Boss : Sabrille", "nom_en": "Boss: Ray O'Light",
     "flag": 327, "chapitre": 9, "region": "vieux_granval"},
    {"cle": "anguigne", "id_ap": 59423021, "nom_fr": "Boss : Anguigne", "nom_en": "Boss: Loiter",
     "flag": 341, "chapitre": 10, "region": "vieux_granval"},
    {"cle": "taprice", "id_ap": 59423022, "nom_fr": "Boss : Taprice", "nom_en": "Boss: Mallice",
     "octet": 73, "seuil": 6, "chapitre": 5, "region": "ourcival", "exclue": True},
]
TOUS_LES_BOSS: List[dict] = BOSS_HISTOIRE + BOSS_QUETES + BOSS_MELANGE

# Valeurs de l'option `boss` (options.py) : modes qui ajoutent des locations de boss. « tous » = histoire_et_quetes +
# BOSS_MELANGE ; les trois premiers modes n'ont pas changé (plans identiques à ceux d'avant).
MODES_BOSS = ("aucun", "histoire", "histoire_et_quetes", "tous")
BOSS_PAR_DEFAUT = "histoire"

# ---------------------------------------------------------------------------
# Tablo-blabla (docs/systemes/archipelago_tablos.md)
# ---------------------------------------------------------------------------
# Check = flag bit global « Yo-kai appelé » (champ +0 de TERRITORY_INFO, territory_0.01j) : décision de l'humain, le
# check part quand le Yo-kai du panneau est APPELÉ (NazoNazoMenu_AskToCall, qui exige de le POSSÉDER), pas à la seule
# bonne réponse (flag « résolu », +8). Flag persistant, jamais effacé, lu par le client dans P (comme les boss).
# Posséder un Yo-kai précis n'est pas modélisable (amitié aléatoire) : les locations sont EXCLUES (remplissage
# seulement), sauf le n° 3 : la fin de la phase 10-45 exige ce flag (phase_set_c10 DATA_ITEM[10, 45] :
# GetGlobalBitFlag(2089) == 1 ; la condition d'une phase est sa condition de FIN) [C] : quiconque finit le chapitre 10 a
# appelé ce Yo-kai ; règle du chapitre 10 (comme Cyrustre… : check au plus tard à 10-45, avant la fin du chapitre).
# Identifiants de l'ancien mod (59422300 + n − 1, numéros du guide) ; noms SANS la réponse (règle 6 : lieux saisis à la
# main). `chapitre` = chapitre dont on prend la règle « Chapitre N terminé » (N − 1 chapitres finis : accès au lieu du
# panneau, archipelago_tablos.md §5.2, borne la plus tardive) ; `apres_jeu` : panneau jamais créé (TABLOS_NON_CREES) ;
# `objets` : objets testés sur le chemin (filtrés comme partout) ; `verrou_montre` : verrou de montre
# franchi (verrou « rangs », grotte du littoral t121d11 derrière le verrou C de t121g00).
TABLOS: List[dict] = [
    {"n": 1, "flag": 2087, "chapitre": 2, "region": "les_hauts_de_granval",
     "lieu_fr": "Les Hauts de Granval (Tout pour tous)", "lieu_en": "Uptown Springdale (Everymart)"},
    {"n": 2, "flag": 2088, "chapitre": 2, "region": "les_hauts_de_granval",
     "lieu_fr": "Les Hauts de Granval (Troc safari)", "lieu_en": "Uptown Springdale (trading shop)"},
    {"n": 3, "flag": 2089, "chapitre": 10, "region": "les_hauts_de_granval", "progression": True,
     "lieu_fr": "Les Hauts de Granval (Centre associatif)", "lieu_en": "Uptown Springdale (community center)"},
    {"n": 4, "flag": 2095, "chapitre": 8, "region": "tunnel_abandonne", "objets": ("huile_de_tendino",),
     "lieu_fr": "Tunnel abandonné (est)", "lieu_en": "Abandoned Tunnel (east)"},
    {"n": 5, "flag": 2096, "chapitre": 8, "region": "tunnel_abandonne",
     "lieu_fr": "Tunnel abandonné (ouest)", "lieu_en": "Abandoned Tunnel (west)"},
    {"n": 6, "flag": 2097, "chapitre": 6, "region": "mont_sylvestre",
     "lieu_fr": "Mont Sylvestre (sommet)", "lieu_en": "Mt. Wildwood (summit)"},
    {"n": 7, "flag": 2098, "chapitre": 6, "region": "mont_sylvestre",
     "lieu_fr": "Mont Sylvestre (sommet)", "lieu_en": "Mt. Wildwood (summit)"},
    {"n": 8, "flag": 2103, "chapitre": 3, "region": "coteau_fleuri",
     "lieu_fr": "Coteau fleuri (sources chaudes)", "lieu_en": "Blossom Heights (hot springs)"},
    {"n": 9, "flag": 2111, "chapitre": 4, "region": "centre_ville_de_granval",
     "lieu_fr": "Centre-ville de Granval (chantier)", "lieu_en": "Downtown Springdale (construction site)"},
    {"n": 10, "flag": 2112, "chapitre": 4, "region": "centre_ville_de_granval",
     "lieu_fr": "Centre-ville de Granval (intérieur)", "lieu_en": "Downtown Springdale (indoors)"},
    {"n": 11, "flag": 2113, "chapitre": 4, "region": "centre_ville_de_granval",
     "lieu_fr": "Centre-ville de Granval (Tour de commerce)", "lieu_en": "Downtown Springdale (trade tower)"},
    {"n": 12, "flag": 2119, "chapitre": 3, "region": "quartier_des_boutiques",
     "lieu_fr": "Quartier des boutiques", "lieu_en": "Shopper's Row"},
    {"n": 13, "flag": 2127, "chapitre": 6, "region": "la_corniche",
     "lieu_fr": "La Corniche (salle des portails, rez-de-chaussée)", "lieu_en": "Breezy Hills (portal hall, ground)"},
    {"n": 14, "flag": 2128, "chapitre": 6, "region": "la_corniche",
     "lieu_fr": "La Corniche (salle des portails, 1er)", "lieu_en": "Breezy Hills (portal hall, 1st)"},
    {"n": 15, "flag": 2129, "chapitre": 6, "region": "la_corniche",
     "lieu_fr": "La Corniche (salle des portails, 2e)", "lieu_en": "Breezy Hills (portal hall, 2nd)"},
    {"n": 16, "flag": 2130, "chapitre": 2, "region": "la_corniche",
     "lieu_fr": "La Corniche (maison des Roch)", "lieu_en": "Breezy Hills (house)"},
    {"n": 17, "flag": 2138, "chapitre": 6, "region": "tour_excellence",
     "lieu_fr": "Tour Excellence", "lieu_en": "Excellent Tower"},
    {"n": 18, "flag": 2140, "chapitre": 6, "region": "san_fantastico",
     "lieu_fr": "San Fantastico (route de la gare)", "lieu_en": "San Fantastico (station road)"},
    {"n": 19, "flag": 2146, "chapitre": 6, "region": "san_fantastico",
     "lieu_fr": "San Fantastico (grotte saline)", "lieu_en": "San Fantastico (salt cave)"},
    {"n": 20, "flag": 2150, "chapitre": 6, "region": "san_fantastico", "objets": ("modele_zero",),
     "verrou_montre": "C",
     "lieu_fr": "San Fantastico (grotte du littoral, 1er)", "lieu_en": "San Fantastico (shore cave, 1st)"},
    {"n": 21, "flag": 2152, "chapitre": 6, "region": "san_fantastico", "objets": ("modele_zero",),
     "verrou_montre": "C",
     "lieu_fr": "San Fantastico (grotte du littoral, 2e)", "lieu_en": "San Fantastico (shore cave, 2nd)"},
    {"n": 22, "flag": 2154, "chapitre": 6, "region": "san_fantastico", "objets": ("modele_zero",),
     "verrou_montre": "C",
     "lieu_fr": "San Fantastico (grotte du littoral, 3e)", "lieu_en": "San Fantastico (shore cave, 3rd)"},
    # n° 23 : panneau sur t100s21, gare terminus de la ligne 0 (train_config) ; train sans condition depuis la gare
    # t104i61 du Centre-ville, ouvert dès l'arrivée au Centre-ville (après l'arrêt 4-50 des Indications de Maman), et
    # depuis t103g00 dès 4-70 [C] ; règle : 3 chapitres + Indications (celle du Centre-ville) ; fermé au chapitre 10
    # (Hauts de Granval seulement), rouvert après la victoire (archipelago_couverture.md R1)
    # (V3, lot 11 : sur un quai, derrière les portillons : le Train, filtré quand son verrou n'est pas actif)
    {"n": 23, "flag": 2142, "chapitre": 4, "region": "centre_ville_de_granval",
     "objets": ("indications_de_maman", "train"),
     "lieu_fr": "Train (gare à confirmer)", "lieu_en": "Train (station to be confirmed)"},
    # n° 24 : Yo-kai World (t001d42), après-jeu (Clé du Yo-kai World : quête 73, phase >= 11-10) [C] : JAMAIS créé
    # (identifiant réservé, TABLOS_NON_CREES) : même exclu, il recevrait un objet d'un autre monde derrière la victoire
    {"n": 24, "flag": 2144, "chapitre": "apres_jeu", "region": "vieux_granval", "apres_jeu": True,
     "lieu_fr": "Yo-kai World", "lieu_en": "Yo-kai World"},
    {"n": 25, "flag": 2156, "chapitre": 5, "region": "vieux_granval",
     "lieu_fr": "Vieux Granval", "lieu_en": "Old Springdale"},
    {"n": 26, "flag": 2158, "chapitre": 5, "region": "vieux_granval",
     "lieu_fr": "Vieux Granval", "lieu_en": "Old Springdale"},
]
# V3 (retour d'un joueur, décision de l'humain du 2026-10-27, archipelago_tablos.md §11) : le check part à l'APPEL, qui
# exige de POSSÉDER le Yo-kai du panneau ; la règle d'un panneau est désormais celle de « Chapitre N terminé » au plus
# tard des deux moments : apparition du panneau (`apparition`, défaut `chapitre`) et Yo-kai OBTENABLE (`TABLOS_YOKAI`),
# avec les objets d'accès de la région où on l'obtient et le rang de montre que demande la loupe (rang de l'espèce :
# le radar ne garde que les Yo-kai de rang <= rang de la montre [C, objets_cles_v11 §17.2] ; D dès 3-160, C dès 4-10
# par la requête 25, B dès 7-20, A dès 8-10 : chapitres 3 / 4 / 7 / 8, comme QUETES). Sources relevées sur la ROM
# européenne (lieux sauvages normaux d'origine, hors salles de portail et cartes d'après la fin ; carte atteinte par le
# parcours des routes d'`audit_cartes.py`) [C sauf mention]. Mélange des Yo-kai : un Yo-kai de Tablo-blabla est une
# espèce EXIGÉE (`rencontres.Analyse.exigences`, catégorie « tablo », et les sources de son évolution / de sa fusion par
# `fermeture`) : il garde un combattant à chaque emplacement d'origine (archipelago_rando_yokai.md §11) ; avec des zones,
# la zone s'ajoute (`avec_zones`). Champs : `chapitre` (règle de « Chapitre N terminé » du lieu où on l'obtient, rang
# compris), `region` (accès par les connexions), `objets`, `rang` (rang de l'espèce, exemplaires de « Rang de montre »
# du verrou « rangs »), `verrou_montre`, `quete` (règle de la requête qui le donne), `apres` (panneaux dont l'APPEL ouvre
# la salle de celui-ci : leur règle s'ajoute), `apres_jeu` (obtenable seulement après la fin : rang S). Aucun nom de
# Yo-kai ici (règle 6) : n° du Médaillium seulement.
TABLOS_YOKAI: Dict[int, dict] = {
    1: {"chapitre": 4, "region": "centre_ville_de_granval"},            # n° 167, rang E : loupe de t104g00 (4-50)
    2: {"chapitre": 6, "region": "tour_excellence", "rang": "C"},       # n° 24, rang C : loupe de t107g00 seulement (6-40)
    3: {"chapitre": 5, "histoire": True},   # n° 70 : don d'histoire (c05_trigger n° 8, 5-90) ; règle inchangée (appel 10-45)
    4: {"chapitre": 8, "quete": 114, "rang": "B", "apres": (5,)},       # n° 117 : requête à transfert 114 seulement
    5: {"chapitre": 7, "region": "centre_ville_de_granval", "rang": "B"},   # n° 315, rang B : loupe de t104g00
    6: {"chapitre": 4, "region": "ourcival", "rang": "C"},              # n° 188, rang C : loupe de t131g00 (jour, sec)
    7: {"chapitre": 5, "region": "mont_sylvestre", "rang": "C"},        # n° 149, rang C : loupe de t102g00, NUIT et pluie
    #                                                                     seulement : heure figée de 4-40 à 4-270 (time_lock)
    8: {"chapitre": 1, "region": "les_hauts_de_granval"},               # n° 8 : évolution du n° 7 (loupe de t101g00)
    9: {"chapitre": 4, "rang": "D"},                                    # n° 14, rang D : salles de portail, Crank-a-kai [S]
    10: {"chapitre": 4, "region": "les_hauts_de_granval", "objets": ("cles_de_l_ecole",)},
    #     n° 23 : combat du jour sur le toit de l'école (t101i58, refoulé <= 3-180), PNJ posé par t101g00 n° 22 (>= 4-10,
    #     au hasard, une fois par jour réel)
    11: {"chapitre": 4, "region": "ourcival", "rang": "C"},             # n° 72, rang C : loupe de t131g00 (4-110)
    12: {"chapitre": 4, "quete": 106},                                  # n° 66 : don de la requête 106
    13: {"chapitre": 4, "region": "centre_ville_de_granval", "rang": "D"},  # n° 56, rang D : loupe de t104g00
    14: {"chapitre": 1, "region": "les_hauts_de_granval", "apres": (13,)},  # n° 127 : loupe de t101g00 ; salle : n° 13 appelé
    15: {"chapitre": 1, "region": "les_hauts_de_granval", "apres": (13, 14)},  # n° 251 : loupe de t101g00
    16: {"chapitre": 7, "region": "vieil_ourcival", "rang": "D"},       # n° 180 : évolution du n° 179 (rang D, loupe de
    #                                                                     t231g00 / t232g00, GetPhase >= 7-10)
    17: {"chapitre": 2, "region": "la_corniche"},                       # n° 47 : loupe de t106g00 (2-90)
    18: {"chapitre": 6, "region": "san_fantastico", "rang": "C", "verrou_montre": "C"},   # n° 309 : errant de t121d03
    #                                                                     seulement (grotte derrière le verrou C de t121g00)
    19: {"chapitre": 7, "region": "mont_de_l_ours", "rang": "B"},       # n° 193, rang B : loupe de t131d05 (4-160)
    20: {"chapitre": 3, "region": "quartier_des_boutiques"},            # n° 163 : loupe de t105g00 (3-140)
    21: {"chapitre": 3, "region": "quartier_des_boutiques", "apres": (20,)},       # n° 165 : loupe de t105g00
    22: {"chapitre": 3, "region": "quartier_des_boutiques", "rang": "D", "apres": (20, 21)},   # n° 166, rang D
    23: {"apres_jeu": True},                                            # n° 326 : légendaire dont un membre (n° 184) est
    #                                                                     de rang S (loupe de t131d05) : après la fin
    24: {"chapitre": 6},                    # n° 71 : errant du donjon des portails (t106d63) ; panneau d'après-jeu
    #                                         (règle de l'après-jeu inchangée, plus stricte)
    25: {"chapitre": 4, "region": "ourcival", "objets": ("grelot_voyageur",)},     # n° 347 : combat du jour de t131d04,
    #                                                                     PNJ présent avec l'objet d'évènement seulement
    26: {"chapitre": 6, "region": "san_fantastico", "rang": "D"},       # n° 297 : fusion du n° 296 (rang D, loupe de t121g00)
    #                                                                     et d'un objet de la boutique d'échange (sans condition)
}
# Apparition du panneau quand elle diffère de `chapitre` (règle d'avant) : n° 6 et 7, sommet du Mont Sylvestre (t102d02,
# point sans condition, carte atteinte dès 3-10 par le parcours des routes, sans mur ni verrou de montre) [C].
TABLOS_APPARITION: Dict[int, int] = {6: 3, 7: 3}
# Graines générées depuis ce lot (`Plan.tablos_apparition`, clé de slot_data `tablos_apparition`) : panneaux dont le
# Yo-kai n'a AUCUNE voie dans la graine, jamais créés : n° 4 sans l'option `requetes_transfert`, n° 25 sans le check
# « Ami » d'évènement de son Yo-kai (objet d'évènement au pool, `amis` = tous ; l'objet dans sa règle), n° 23 avant la fin (créé
# seulement dans la région « rang_s » de l'après-jeu complet, comme le n° 24). Graine d'avant : créés comme avant
# (le tracker garde ses locations), règle corrigée (n° 23 : après la fin).
TABLOS_APPARITION_PAR_DEFAUT = True
CLE_SLOT_DATA_TABLOS = "tablos_apparition"
TABLOS_SANS_TRANSFERT = frozenset((4,))
TABLOS_EVENEMENT = frozenset((25,))
TABLOS_APRES_JEU = frozenset((23,))
TABLO_23_REGION = "rang_s"
# Interrupteur d'AUDIT seulement (`audit_logique.py --sans-tablos`, condensats des graines de la V2) : faux = règles
# d'avant (lieu du panneau seul). Toujours vrai ailleurs.
REGLES_TABLOS_YOKAI = True
# Articles de boutique vendus après un Tablo-blabla (`boutiques.TABLOS_ARTICLES`, retour d'un joueur du 2026-11-03) :
# leur règle comprend celle du panneau, pour TOUTE graine. Interrupteur d'AUDIT seulement (condensats des graines de la
# V2 : `condensats_plans.CORRECTION_BOUTIQUES_TABLOS`) : faux = règle d'avant (région + chapitre). Toujours vrai ailleurs.
REGLES_BOUTIQUES_TABLOS = True
TABLO_ID_BASE = 59422300
for _t in TABLOS:
    _t["id_ap"] = TABLO_ID_BASE + _t["n"] - 1
    _t["nom_fr"] = "Tablo-blabla n°%02d : %s" % (_t["n"], _t["lieu_fr"])
    _t["nom_en"] = "Baffle Board #%02d: %s" % (_t["n"], _t["lieu_en"])
# Panneaux créés comme locations (tous sauf l'après-jeu) ; identifiants réservés, jamais des locations (comme
# QUETES_NON_CREEES) : n° 24 (Yo-kai World, archipelago_couverture.md R1).
TABLOS_CREES: List[dict] = [_t for _t in TABLOS if not _t.get("apres_jeu")]
TABLOS_NON_CREES: Dict[int, int] = {_t["id_ap"]: _t["n"] for _t in TABLOS if _t.get("apres_jeu")}
TABLOS_PAR_N: Dict[int, dict] = {_t["n"]: _t for _t in TABLOS}

# Valeurs de l'option `tablos` (options.py). « tous » par défaut : 25 locations exclues (remplissage seulement, aucun
# risque de blocage même si le joueur n'appelle jamais leur Yo-kai) et le n° 3, garanti par l'histoire.
MODES_TABLOS = ("aucun", "tous")
TABLOS_PAR_DEFAUT = "tous"

# ---------------------------------------------------------------------------
# Requêtes et services (docs/systemes/archipelago_quetes.md §4, branche ap/quetes)
# ---------------------------------------------------------------------------
# Check = quête terminée : phase 255, octet Q + 4 + n du bloc des quêtes (lu par le client, comme les boss de quête),
# n = 4e champ de QUEST_CONFIG [C]. Décision de l'humain (option b) : la récompense d'objet de la quête est REMPLACÉE
# par l'objet Archipelago dans l'écran de résultat (jeu v5, table « récompenses de quête » de la boîte) ; l'argent et
# l'expérience restent. Identifiants de l'ancien mod (QUEST_OFFSET 200, requêtes de rang RANK_OFFSET 50) et 9 nouveaux
# (59420277..285) ; noms FR / EN de l'ancien mod (saisis à la main, règle 6).
# `chapitre` N = max(chapitre d'apparition, chapitre où le rang de montre réel exigé s'obtient : C dès 4-10, B dès
# 7-20, A dès 8-10 [C, QUEST_CONFIG des requêtes 25..27], N des quêtes exigées finies) ; règle = celle de « Chapitre N
# terminé » + objets testés sur le chemin (filtrés comme partout) ; `rang` = rang de montre réel exigé (représenté par
# le chapitre ; avec le verrou « rangs », exemplaires de « Rang de montre » de exemplaires_pour) ; `montre` = verrou
# de montre franchi sur le chemin (verrou « rangs ») ; `region` : région de l'ancien mod (celle du boss pour une
# quête de boss), « menu » quand elle est inconnue (la règle du chapitre implique déjà les accès de l'histoire).
# Exclues (remplissage seulement) : n° 8 (donjon des portails, = Tromplœil), n° 80 (exige le Yo-kai du Tablo-blabla
# n° 8 appelé, flag 2103 : non modélisable, = Crocho, archipelago_logique_audit.md) et les 10 services (option,
# phase 255 remise à 0 par le tirage des services, archipelago_quetes.md §2.5). Non créées (identifiants réservés) :
# n° 112, 113, 114 (SaveCopyFlag : transfert de données jamais fait, §2.6) et n° 28 (rang S, après-jeu).
QUETES: List[dict] = []


def _q(n, id_ap, fr, en, chapitre, region, rang=None, objets=(), montre=None, exclue=False, service=False,
       prefixe=True):
    QUETES.append({
        "n": n, "id_ap": id_ap, "chapitre": chapitre, "region": region, "rang_reel": rang, "objets": tuple(objets),
        "verrou_montre": montre, "exclue": exclue or service, "service": service,
        "nom_fr": ("Service : " if service else "Requête : ") * prefixe + fr,
        "nom_en": ("Service: " if service else "Request: ") * prefixe + en})


# `rang` "D" [C, QUEST_CONFIG : GetWatchRank >= D] : 0 exemplaire dans l'ancien mode (rang D de l'histoire), 1 en mode
# « rang réel ». Prudence (mode « rang réel ») : les quêtes 44, 64 et le service 161, visibles au rang E dès le chapitre 3,
# exigent un Yo-kai (QUEST_NECESSARY_CONDITION type 2 / 1) dont la présence au rang E n'est pas prouvée : "D" aussi.
_CLES_T103G00 = ("cle_de_derriere", "jolie_petite_cle", "jolie_grande_cle")   # portes de Coteau fleuri (IsHaveItem)
# V3, lot 9 : objets dont la REMISE est refusée par un verrou étendu (filtrés comme partout : sans effet quand le verrou
# n'est pas actif). Chaînes [C, QUEST_CONFIG] : 44 -> 45 -> 46 (qui exige aussi la 49) -> Silhouette de héros -> 40
# (Musée) pour la Ceinture de force ; 48 -> Figurine de Photortue, 48 -> 49 -> 46 -> 40 pour les deux Robots.
_CEINTURE = ("ceinture_de_force",)
_ROBOTS = ("robot_retro_neuf", "robot_mecanique_use")
_q(1, 59420200, "Spécialiste des cigales", "A Cicada Professional", 2, "mont_sylvestre")
_q(2, 59420202, "Ça attire les clients !", "Customer Attraction!", 2, "les_hauts_de_granval")
_q(3, 59420204, "Officiellement officiel !", "Officially Official!", 3, "les_hauts_de_granval")
_q(4, 59420205, "Bam boum ! Fusion !", "Bam-Boom! Fusing!", 3, "coteau_fleuri")
_q(5, 59420214, "Secrets de l'Âmechimie", "Secrets of Soulcery", 4, "ourcival")
_q(6, 59420206, "Les portails mystère", "The Gates of Whimsy", 3, "la_corniche")
_q(7, 59420257, "Une armure sinistre", "Eerie, Roving Armor", 8, "la_corniche", "B")
_q(8, 59420226, "Le portail final", "The Final Gate", 4, "la_corniche", objets=("canne_a_peche",), exclue=True)
_q(9, 59420244, "Sur les traces de Papa", "Retrace Dad's Steps", 7, "les_hauts_de_granval",
   objets=("documents_perdus",))    # V3 : remise des Documents perdus (verrou « documents_perdus », filtré sinon)
_q(10, 59420218, "Pièce Au Phil du temps", "Timers & More's Part", 5, "vieil_ourcival")
_q(11, 59420219, "Pièce sanctuaire", "The Shrine's Part", 5, "vieux_granval",
   objets=("lettre_de_komasan",))   # V3 : remise de la Lettre de Komasan (verrou k = 48, filtré sinon)
_q(12, 59420220, "Pièce ferronnerie", "The Ironworks' Part", 5, "vieux_granval",
   objets=("bille_mysterieuse",))   # V3 : entrée de la ferronnerie (verrou k = 49, filtré sinon)
_q(13, 59420221, "Trouvons Parasolal !", "Find Pallysol!", 6, "ourcival")
_q(14, 59420222, "Trouvons Lulutin !", "Find Gnomey!", 6, "ourcival",
   objets=("cartes_ultramax",))     # V3 : remise des Cartes d'Ultramax (verrou « cartes_ultramax », filtré sinon)
_q(15, 59420223, "Trouvons Métaureaulog !", "Find Predictabull!", 6, "ourcival")
_q(16, 59420224, "Trouvons Sirénée !", "Find Mermaidyn!", 6, "san_fantastico")
_q(17, 59420225, "Trouvons Faux Kappa !", "Find Faux Kappa!", 6, "ourcival")
_q(18, 59420243, "Le secret de Jibanyan", "Jibanyan's Secret", 7, "les_hauts_de_granval")
_q(19, 59420260, "Épreuves de Nyada IV", "Nyada's Trials IV", 9, "vieil_ourcival")
_q(20, 59420261, "Épreuves de Nyada V", "Nyada's Trials V", 9, "vieil_ourcival")
_q(21, 59420262, "Épreuves de Nyada VI", "Nyada's Trials VI", 9, "vieil_ourcival", "A", montre="A")
# requêtes de rang (t103i21) : sans préfixe, comme l'ancien mod ; C passe par le Manoir (verrou D de t103g00), B par les
# verrous C de San Fantastico, A par la Clinique du Crépuscule (verrou B) [C, objets_cles_v11 §14, §14.8]
_q(25, 59420050, "Obtenons le rang C !", "Go for Rank C!", 4, "coteau_fleuri", "D", montre="D", prefixe=False)
_q(26, 59420051, "Obtenons le rang B !", "Go for Rank B!", 7, "coteau_fleuri", "C", montre="C", prefixe=False)
_q(27, 59420052, "Obtenons le rang A !", "Go for Rank A!", 8, "coteau_fleuri", "B", montre="B", prefixe=False)
_q(29, 59420216, "Vrai cache-cache", "True Hide-and-Seek", 4, "ourcival", "D")
_q(30, 59420237, "Super cache-cache", "Super Hide-and-Seek", 6, "san_fantastico", "D")
_q(31, 59420258, "Méga cache-cache", "Ultra Hide-and-Seek", 8, "les_hauts_de_granval", "B")
_q(32, 59420277, "Cache-cache expert", "Expert Hide-and-Seek", 9, "mont_sylvestre", "A")
_q(33, 59420250, "C-1 Grand Prix", "C-1 Grand Prix", 8, "les_hauts_de_granval", "C")
_q(34, 59420256, "C-1 Grand Prix A", "C-1 Grand Prix A", 8, "san_fantastico", "B")
_q(35, 59420278, "C-1 Grand Prix S", "C-1 Grand Prix S", 9, "ourcival", "A")
# quête 40 : les dix objets exposés sont exigés (QUEST_NECESSARY_CONDITION de la phase 2 : dix flags d'exposition, posés
# à la remise de chaque objet, TALK_CONFIG de t106d31 : IsHaveItem) [C] ; la Silhouette de héros ne vient que de la
# quête 46 (>= 9-10, rang A, quêtes 45 et 49 finies), la Robe de star de la quête 65 (rang B), la Figurine de la quête 48
# (rang B) : chapitre 9 et rang A (correction de l'ancienne règle « 5 chapitres », objets_cles_v11 §16.3)
_q(40, 59420203, "Musée en détresse", "Collection Correction", 9, "quartier_des_boutiques", "A",
   objets=OBJETS_MUSEE + _CEINTURE + _ROBOTS)       # V3 : la Silhouette de héros vient de la 46 (44, 45, 48, 49)
_q(41, 59420235, "Voyage de l'envoûtement", "Inspirited Away", 5, "mont_sylvestre", "C")
_q(42, 59420265, "La faim justifie le moyen", "Dinner on Hold", 8, "les_hauts_de_granval", "B")
# quête 44 : exige de POSSÉDER Sumochi (QUEST_NECESSARY_CONDITION type 2). Sauvage seulement en salle de portail, MAIS lot
# de la Pièce rouge du Crank-a-kai du présent (5 %, dès le chapitre 2-3) : NON exclue, non marquée (revue
# archipelago_portails_tardifs.md §8). Les quêtes 45 (qs0044 == 255) et 46 (qs0045 == 255) en héritent, la 40 aussi.
_q(44, 59420207, "Super Balaise : l'origine", "Bear Boy: Origins", 3, "coteau_fleuri", "D",
   objets=_CEINTURE)                # V3 : remise de la Ceinture de force (verrou k = 54, filtré sinon)
_q(45, 59420241, "Super Balaise : le retour", "The Bear Boy Returns", 6, "les_hauts_de_granval", "C", objets=_CEINTURE)
_q(46, 59420279, "Super Méga Balaise", "Ultimate Bear Boy", 9, "les_hauts_de_granval", "A",
   objets=_CEINTURE + _ROBOTS)      # exige les requêtes 45 et 49
_q(47, 59420208, "Soirée chaotique", "Hangout Havoc", 3, "coteau_fleuri")
_q(48, 59420254, "Jouets d'antan", "Time and Toys", 8, "vieux_granval", "B",
   objets=_ROBOTS)                  # V3 : remises des deux Robots (verrous k = 55 et 56, filtrés sinon)
_q(49, 59420264, "Qui est cette fille", "Who's That Girl", 9, "centre_ville_de_granval", "A", objets=_ROBOTS)
_q(50, 59420209, "Chasseurs de trésors 1", "Treasure Hunters Pt. 1", 3, "mont_sylvestre", "D")
_q(51, 59420242, "Chasseurs de trésors 2", "Treasure Hunters Pt. 2", 6, "mont_sylvestre", "C",
   objets=("cle_salle_du_tresor",))
_q(52, 59420259, "Chasseurs de trésors 3", "Treasure Hunters Pt. 3", 8, "mont_sylvestre", "A",
   objets=("cle_salle_du_tresor", "huile_de_tendino"))
_q(53, 59420210, "La base secrète", "The Secret Base", 3, "la_corniche")
_q(54, 59420234, "Chasse nocturne", "Gone Haunting", 5, "coteau_fleuri", "C", objets=_CLES_T103G00)
_q(55, 59420245, "Triangle amoureux", "The Heartthrobs", 8, "quartier_des_boutiques", "C", objets=_CLES_T103G00)
_q(56, 59420239, "Ectoplasmes à l'école", "Ghost Club at School", 6, "les_hauts_de_granval", "C")
_q(57, 59420266, "La clinique hantée", "The Haunted Hospital", 8, "quartier_des_boutiques", "A",
   objets=("poignee_etrange",), montre="B")
_q(58, 59420280, "Le géant fantôme", "The Phantom Giant", 9, "centre_ville_de_granval", "A",
   objets=("poignee_etrange",), montre="B")
_q(59, 59420281, "Devoirs d'été - 1re partie", "Independent Study, Pt. 1", 5, "menu", "D")
_q(60, 59420282, "Devoirs d'été - 2e partie", "Independent Study, Pt. 2", 8, "menu", "B")
_q(62, 59420227, "Prix de Gastronomie", "Gourmet Grand Prix", 5, "les_hauts_de_granval", "D")
_q(64, 59420211, "Nouveau look", "Makeover Takeover", 3, "quartier_des_boutiques", "D")
_q(65, 59420246, "Un look trop sophistiqué", "Too Much Makeover", 8, "tour_excellence", "B")
_q(66, 59420213, "La star de Granval 1", "Springdale Star Pt. 1", 4, "les_hauts_de_granval", "C")
_q(67, 59420263, "La star de Granval 2", "Springdale Star Pt. 2", 8, "tour_excellence", "A")
_q(68, 59420201, "Courage, Max !", "Matt, Don't Give Up!", 2, "les_hauts_de_granval")
_q(69, 59420252, "Coup de bluff", "A Card-Carrying Liar", 8, "quartier_des_boutiques", "C")    # exige la 71 (N 8)
_q(71, 59420251, "Un super fan-club", "Catchy Fandom", 8, "centre_ville_de_granval", "D")
_q(78, 59420247, "La reine des cigales", "King of the Cicadas", 7, "mont_sylvestre", "B")
_q(80, 59420248, "Les sources de l'amitié", "A Steamy Friendship", 7, "coteau_fleuri", "B", exclue=True,
   objets=("serviette_douce",))     # V3 : remise de la Serviette douce (verrou k = 57, filtré sinon)
_q(82, 59420228, "Un amour perdu", "Long Lost Love", 5, "vieux_granval", "D")
_q(83, 59420249, "Je veux grandir", "I Just Wanna Grow Up", 8, "centre_ville_de_granval", "C")
_q(85, 59420236, "Virée en mer !", "Take to the Sea!", 6, "san_fantastico", "D", objets=("canne_a_peche",))
_q(86, 59420217, "Le meilleur scarabée", "Which Beetle's Better", 5, "vieil_ourcival", "D")
_q(87, 59420230, "Blues du déménagement", "Moving Blues", 5, "vieux_granval", "D")
_q(88, 59420253, "Querelles gourmandes", "Foodie Feuds", 8, "vieux_granval", "B")
_q(89, 59420229, "Votre mascotte locale", "Your Local Mascot", 6, "ourcival", "C")
_q(90, 59420238, "Tous à bord", "All Aboard", 6, "tour_excellence", "D",
   objets=("carte_a_tamponner", "train"))   # V3 : les tampons des gares testent la possession de la Carte (filtré
#                                              sinon) ; lot 11 : la requête se joue dans les trains
_q(98, 59420283, "Le tango du trio", "Trying Tangle Tango", 8, "menu", "B",
   objets=("dance_revolution",))    # V3 : remise de Dance Revolution (verrou k = 58, filtré sinon)
_q(99, 59420215, "Pas le temps de pêcher !", "No Time For Fishin'!", 4, "ourcival", "D", objets=("canne_a_peche",))
_q(100, 59420284, "Quel charmeur !", "A Real Charmer", 6, "menu", "C")
_q(104, 59420231, "Oden de l'âme 1", "Oden of the Soul Pt. 1", 4, "ourcival", "D")
_q(105, 59420232, "Oden de l'âme 2", "Oden of the Soul Pt. 2", 4, "ourcival", "D")
_q(106, 59420233, "Oden de l'âme 3", "Oden of the Soul Pt. 3", 4, "ourcival", "D")
_q(125, 59420285, "Le casting rêvé d'Irréal", "Directator's All-Star Cast", 4, "menu", "D")
_q(151, 59420267, "Sous un soleil de plomb", "Stuck in the Heat", 2, "les_hauts_de_granval", service=True)
_q(152, 59420268, "Le ventre vide", "Running on Empty", 3, "quartier_des_boutiques", service=True)
_q(153, 59420270, "Une envie de bonbons", "Sweet Satisfaction", 4, "coteau_fleuri", service=True)
_q(154, 59420272, "Espiègleries", "School Pranks", 5, "quartier_des_boutiques", "D", service=True)
_q(155, 59420274, "À la chasse aux insectes !", "Bug Hunting", 6, "mont_sylvestre", "C", service=True)
_q(161, 59420269, "Que de balivernes", "A Likely Story", 3, "quartier_des_boutiques", "D", service=True)
_q(162, 59420271, "La malade imaginaire", "Overstuffed Head", 4, "centre_ville_de_granval", "D", service=True)
_q(163, 59420273, "Un entraînement de star", "Popular Training", 5, "vieil_ourcival", "D", service=True)
_q(164, 59420275, "Un matou en détresse", "Fat Cat's Favor", 6, "san_fantastico", "C", service=True)
_q(166, 59420276, "Coup de foudre", "Struck with Love", 8, "ourcival", "B", service=True)
# Services d'avant l'après-jeu absents de la liste de l'ancien mod (checks oubliés, archipelago_couverture.md §9) :
# nouveaux identifiants 59420286.. (après les 9 requêtes ajoutées), noms FR / EN repris des données de l'ancien mod
# (quest_hashes.json, i18n_en.json) ; conditions de QUEST_CONFIG [C] ; région inconnue : « menu ».
_q(156, 59420286, "Ne pas jouer le jeu", "Gaming the System", 7, "menu", "C", service=True)       # >= 7-10, rang C
_q(157, 59420287, "Cherche coach invisible", "Leading from Behind", 8, "menu", "B", service=True)  # >= 8-10, rang B
_q(158, 59420288, "Vive la technologie", "Tasteful Technology", 9, "menu", "B", service=True)      # >= 9-10, rang B
_q(165, 59420289, "Une vision d'horreur", "A Frightful Sight", 7, "menu", "C", service=True)       # >= 7-10, rang C
_q(167, 59420290, "Ménage spirituel", "Spiritual Cleansing", 9, "menu", "B", service=True)         # >= 9-10, rang B
_q(168, 59420291, "Parlez-vous le chien ?", "A Ruff Translation", 9, "menu", "A", service=True)    # >= 9-10, rang A
# Identifiants réservés, jamais des locations (archipelago_quetes.md §4.2) : requêtes inaccessibles sans transfert de
# données (112, 113, 114) et rang S (28, après-jeu).
QUETES_NON_CREEES: Dict[int, int] = {59420212: 112, 59420240: 113, 59420255: 114, 59420053: 28}
QUETES_PAR_NUMERO: Dict[int, dict] = {q["n"]: q for q in QUETES}

# Valeurs de l'option `quetes` (options.py). « requetes » par défaut : 74 requêtes pouvant recevoir de la progression
# (+ 2 exclues), détection par la phase 255 (même lecture que les boss de quête, persistante pour les requêtes),
# récompenses d'origine sans effet sur la logique (consommables et équipements). Services : option (exclus).
MODES_QUETES = ("aucune", "requetes", "requetes_et_services", OJ.MODE_REQUETES_CLES)   # (clés : options_joueur.py)
QUETES_PAR_DEFAUT = "requetes"

# ---------------------------------------------------------------------------
# Checks « Chapitre N terminé » (docs/systemes/archipelago_couverture.md §3.7, R4)
# ---------------------------------------------------------------------------
# Check = quête de chapitre terminée : les quêtes 171..180 (genre 1 de QUEST_CONFIG) sont les 10 chapitres, la phase
# 255 marque le chapitre fini [C : sauvegardes de l'humain, chapitre 5 -> 171..174 à 255, histoire finie -> 171..180] ;
# lue par le client comme un boss de quête (octet Q + 4 + n du bloc des quêtes, entrée {location, quete} de `boss`),
# aucun changement du jeu. Chapitres 1 à 9 seulement : la fin du chapitre 10 est la victoire (Lady Démona). Identifiants
# de l'ancien mod (« Chapitre N : … » = 59420000 + N − 1, envoyé quand le compteur de chapitre passe à N + 1 : même
# chapitre N) ; noms saisis à la main (pas les titres des chapitres). Règle = celle de l'évènement « Chapitre N
# terminé » (les évènements restent : ces locations sont EN PLUS, dans la région du chapitre).
CHAPITRE_QUETE_BASE = 170
CHAPITRES_CHECKS: List[dict] = [
    {"n": _n, "id_ap": 59420000 + _n - 1, "quete": CHAPITRE_QUETE_BASE + _n,
     "nom_fr": "Histoire : chapitre %d terminé" % _n, "nom_en": "Story: Chapter %d complete" % _n}
    for _n in range(1, 10)]
CHAPITRES_CHECKS_PAR_DEFAUT = True

# Check « Montée de rang : D » (checks oubliés, archipelago_couverture.md §9 ; identifiant et noms de l'ancien mod) : le
# rang D est donné par c03_trigger n° 33 (RunCmd_Phase33 : RunkUp puis RunEvent ev03_2300) ; le flag « évènement vu »
# de ev03_2300 (flag bit global 201, crc32 0x8F9CADA5 de flag_config) est posé par la scène jouée juste après la montée,
# jamais effacé (lu par c03_trigger n° 34 / 35) [C ; sauvegardes : 0 en 3-150, 1 en 3-190]. Lu par le client comme un
# boss d'histoire (entrée {location, flag} de `boss`), aucun changement du jeu. Avec l'option `chapitres` (checks
# d'histoire). Règle = celle de « Chapitre 3 terminé » (2 chapitres + Clés de l'école, Herbe, Tournevis : le n° 33 suit
# les n° 21 et 27, OBJETS_RANG_D) : exacte pour les objets, plus stricte d'un demi-chapitre, jamais moins. Genre
# « rang » (pas « histoire » : sa clé n'est pas un numéro de chapitre). C, B, A : doublons des requêtes de rang (même
# instant que leur fin), S : après-jeu : non créés.
RANG_D_CHECK: dict = {"cle": "rang_d", "id_ap": 59420054, "nom_fr": "Montée de rang : D", "nom_en": "Rank Up: D",
                      "flag": 201, "chapitre": 3, "region": "coteau_fleuri"}

# Coffres dorés du donjon des portails (La Corniche, t106d46 .. t106d62 ; index TBox 444-453, identifiants de l'ancien
# mod 59421230..239) : entrée refusée tant que la quête 6 n'est pas finie (t106d33_trigger n° 1, GetQuestPhase(qs0006)
# < 255), puis portes internes ouvertes avec des globes de portail (t106d41 n° 1-5) ; aucune condition de phase ni
# d'après-jeu sur les routes, les salles et les coffres [C]. Le coût en globes n'est pas modélisable (comme Tromplœil) :
# locations EXCLUES (remplissage seulement), règle de la requête 6 (checks oubliés, archipelago_couverture.md §9).
EXCLUSION_PORTAILS = "zone_portails"
QUETE_PORTAILS = 6

# Checks « tardifs » des portails mystères (docs/systemes/archipelago_portails_tardifs.md ; demande de l'humain : « longs à
# avoir »). Le mod n'a pas d'autre catégorie « tardif » que la location EXCLUE (remplissage seulement : jamais d'objet
# de progression) : ces checks sont exclus ET marqués (`LocationPlan.portail`) pour le tracker du lanceur.
# - PORTAIL_DONJON : donjon des portails de La Corniche (t106d41..) : portes payées en globes de portail, qui ne
#   viennent que du coffre de fin d'une salle de portail (quelques-uns par salle, `_tbox_gate`) et de la boutique N036 : des
#   dizaines de portails quelconques (10 coffres, Tromplœil, requête 8, Tablo-blabla n° 13 à 15) ;
# - PORTAIL_SALLE : exige UNE salle précise parmi les 45 de GATE_ENTER_INFO, tirée au sort à chaque portail
#   (FUN_0064E7B4) : boutique N036 (vendeur de la version « portail » de t104i23) ;
# - PORTAIL_CRANK : espèce sauvage seulement en salle de portail (Sumochi : gymnase t101i59 ; Alfoncéo : t103i31) mais
#   aussi lot de la Pièce rouge du Crank-a-kai (Sumochi 5 % au présent, Alfoncéo 4 % au passé) : long, pas impossible
#   (Tablo-blabla n° 9, amis Sumochi / Darumastar / Alfoncéo, déjà exclus ; PAS les requêtes 44 à 46 et 40, qui restent
#   comme avant) ;
# Non marquée : la requête 6 (son portail est scénarisé : salle fixée par la commande 0x3699('t101i21'), t106g00 n° 39).
# Règle : au moins celle de « Chapitre CHAPITRE_PORTAILS terminé » : les portails apparaissent (random_event, groupe du
# flag 2484) dès la requête 6 finie (>= 3-95) ou la phase 3-131, sauf de 4-35 à la fin du chapitre 4, pendant la
# tempête (flag 62, 7-40..7-70) et le siège (flag 63, 10-20..10-150) [C]. Boutique N036 : salle à condition
# GetPhase >= 4-50, donc chapitre 5 (boutiques.chapitre_article).
PORTAIL_DONJON = "donjon"
PORTAIL_SALLE = "salle"
PORTAIL_CRANK = "crank"
# PORTAIL_REQUETES : check qui exige TOUTES les requêtes (Pandanoko), dont « Le portail final » (donjon) : long pour cette
# raison, pas parce qu'il exigerait une salle précise.
PORTAIL_REQUETES = "requetes"
# PORTAIL_TUNNEL : même catégorie « tardif » (exclue + marquée pour le tracker), sans portail mystère : boss du bout du
# Tunnel sans fin (Taprice), six traversées (la sixième mène au boss) à raison d'une entrée par jour RÉEL (bit 2528,
# remis à 0 par la réinitialisation de 6 h de l'horloge de la console : FUN_00411DA8, archipelago_boss.md §11.3 ;
# l'option `tunnel_sans_limite` de la V3 lève cette limite, sans changer le statut de la location).
PORTAIL_TUNNEL = "tunnel"
PORTAILS = (PORTAIL_DONJON, PORTAIL_SALLE, PORTAIL_CRANK, PORTAIL_REQUETES, PORTAIL_TUNNEL)
CHAPITRE_PORTAILS = 3
TABLOS_PORTAILS: Dict[int, str] = {9: PORTAIL_CRANK, 13: PORTAIL_DONJON, 14: PORTAIL_DONJON, 15: PORTAIL_DONJON}
QUETES_PORTAILS: Dict[int, str] = {8: PORTAIL_DONJON}
BOSS_PORTAILS: Dict[str, str] = {"tromploeil": PORTAIL_DONJON, "taprice": PORTAIL_TUNNEL}
TAG_BOUTIQUE_PORTAILS = "x_portails"

# Bouclage du chapitre 10 (archipelago_couverture.md §2.3) : de 10-10 à la fin du chapitre 10, la ville est fermée
# (refoulements de c10_trigger) ; une location dont la règle exige au moins CHAPITRES_BOUCLAGE chapitres terminés est
# « du chapitre 10 » (histoire du chapitre 10), toute autre doit être faite avant (ou après la victoire). Aucune location
# hors de l'histoire du chapitre 10 ne doit avoir une telle règle (tests : CHAPITRE_10_JUSTIFIEES).
CHAPITRES_BOUCLAGE = 9
# Locations justifiées à 9 chapitres terminés (identifiants AP) : boss du chapitre 10 (Cyrustre, Fielippine, Maudicko,
# Ronéan, Lady Perpétua ; Lady Démona = la victoire), Tablo-blabla n° 3 (appel imposé à 10-45) et coffre 373 « Vieux
# Hauts de Granval (retour Ch10) » (t201g00 : zone du décor du chapitre 10, blocs de t201g00_mesh selon ev10_1100 /
# ev10_1400 / ev10_1700 ; accès avant le chapitre 10 non prouvé [?] : règle de l'ancien mod, mesurée en jeu, gardée
# jusqu'à l'essai du Gros test V1).
# + « Boss : Anguigne » (59423021, mode « tous » de `boss` : combat de l'étape 10-20).
CHAPITRE_10_JUSTIFIEES: FrozenSet[int] = frozenset({59423012, 59423011, 59423013, 59423014, 59420106, 59420107,
                                                    59422302, 59421192, 59423021})

REGION_ORIGINE = "menu"
# Classification d'un objet d'évènement cité par la règle du check « Ami » de son Yo-kai (location exclue) : progression
# pour qu'Archipelago évalue la règle, sans équilibrage (il n'ouvre rien d'autre). `__init__.CLASSIFICATIONS`.
CLASSE_PROGRESSION_SANS_EQUILIBRAGE = "progression_sans_equilibrage"
DERNIER_CHAPITRE = 10       # la fin du chapitre 10 est la victoire (Lady Démona)

NOMS_EVENEMENT_CHAPITRE = {"fr": "Chapitre {} terminé", "en": "Chapter {} complete"}
NOMS_GROUPES = {
    "fr": {"objet_cle": "Objets-clés", "consommable": "Consommables", "argent": "Argent",
           "coffres": "Coffres dorés", "emplacements": "Objets-clés (emplacements)", "boss": "Boss",
           "boss_quetes": "Boss de quête", "boss_melange": "Boss du mélange (ajoutés)",
           "rang": "Rangs de montre", "capacite": "Capacités",
           "tablos": "Tablo-blabla", "requetes": "Requêtes", "services": "Services", "histoire": "Histoire",
           "amis": "Amis", "criminels": "Yo-criminels", "evenement": "Objets d'évènement",
           "boutiques": "Boutiques", "invitation": "Invitations", "objet_cle_v3": "Objets-clés",
           "objet_cle_aj": "Objets-clés", "apres_jeu": "Après-jeu", "blasters": "Blasters",
           "medaillium": "Objets du Médaillium", "piece": "Pièces spéciales",
           "fusion_regionale": "Objets de fusion régionaux", "distributeurs": "Distributeurs",
           "nourriture": "Nourriture", "equipement": "Équipement", "livre": "Livres", "objet_valeur": "Objets de valeur",
           "piege": "Pièges", "terrain_blasters": "Terrains de Ψ Blasters",
           "multiplicateur_xp": "Multiplicateurs d'XP"},
    "en": {"objet_cle": "Key Items", "consommable": "Consumables", "argent": "Money",
           "coffres": "Golden Chests", "emplacements": "Key Items (locations)", "boss": "Bosses",
           "boss_quetes": "Quest Bosses", "boss_melange": "Shuffle Bosses (added)",
           "rang": "Watch Ranks", "capacite": "Abilities",
           "tablos": "Baffle Boards", "requetes": "Requests", "services": "Services", "histoire": "Story",
           "amis": "Friends", "criminels": "Yo-criminals", "evenement": "Event Items", "boutiques": "Shops",
           "invitation": "Invitations", "objet_cle_v3": "Key Items",
           "objet_cle_aj": "Key Items", "apres_jeu": "Postgame", "blasters": "Blasters",
           "medaillium": "Medallium Items", "piece": "Special Coins",
           "fusion_regionale": "Regional Fusion Items", "distributeurs": "Vending Machines",
           "nourriture": "Food", "equipement": "Equipment", "livre": "Books", "objet_valeur": "Valuables",
           "piege": "Traps", "terrain_blasters": "Psychic Blasters Stages",
           "multiplicateur_xp": "EXP Multipliers"},
}


def nom_evenement_chapitre(n: int, langue: str) -> str:
    return NOMS_EVENEMENT_CHAPITRE[langue].format(n)


# ---------------------------------------------------------------------------
# Tables fixes (indépendantes des options) : noms et identifiants
# ---------------------------------------------------------------------------
def coffres_v1() -> List[dict]:
    return [c for c in donnees().coffres if "exclusion" not in c]


def coffres_rangs() -> List[dict]:
    """Coffres exclus de la V1 pour un rang de montre (rang_C/B/A) : locations quand le verrou « rangs » est actif
    (sauf COFFRES_RANG_NON_LOCATIONS)."""
    return [c for c in donnees().coffres
            if c.get("exclusion") in EXCLUSIONS_RANG and c["index_tbox"] not in COFFRES_RANG_NON_LOCATIONS]


def coffres_portails() -> List[dict]:
    """Coffres du donjon des portails : locations exclues (remplissage seulement), règle de la requête 6."""
    return [c for c in donnees().coffres if c.get("exclusion") == EXCLUSION_PORTAILS]


def coffres_apres_jeu() -> List[dict]:
    """Coffres dorés des zones d'après-jeu (V3, lot 3 : `apres_jeu.py`) : locations seulement avec un objectif
    d'après-jeu et l'option `apres_jeu`, et seulement si leur région est ouverte."""
    return [c for c in donnees().coffres if c.get("exclusion") == AJ.EXCLUSION_COFFRES]


def coffre_cle_bleue() -> dict:
    """Coffre de la Clé magnétique bleue (index 179, derrière un verrou de montre A) : location seulement avec le
    verrou « rangs » ET la valeur « cle_magnetique_bleue » (V3, lot 9) ; sinon il garde sa clé."""
    return next(c for c in donnees().coffres if c["index_tbox"] == COFFRE_CLE_BLEUE)


def coffres_possibles() -> List[dict]:
    """Tous les coffres qui peuvent être des locations (la table des noms ne dépend pas des options)."""
    return coffres_v1() + coffres_rangs() + [coffre_cle_bleue()] + coffres_portails() + coffres_apres_jeu()


def regions_v1(rangs: bool = False) -> List[dict]:
    """Régions de la V1 ; avec le verrou « rangs », aussi celles qui sont derrière un verrou de montre (Clinique)."""
    return [r for r in donnees().regions
            if "exclusion" not in r or (rangs and r["cle"] in REGIONS_VERROU_DE_MONTRE)]


def nom_objet(cle: str, langue: str) -> str:
    return donnees().objets_par_cle[cle]["nom_" + langue]


def table_objets(langue: str) -> Dict[str, int]:
    """nom → identifiant AP, pour tous les objets (le paquet de données ne dépend pas des options)."""
    return {o["nom_" + langue]: o["id_ap"] for o in donnees().objets}


def table_locations(langue: str) -> Dict[str, int]:
    t = {c["nom_" + langue]: c["id_ap"] for c in coffres_possibles()}
    t.update({e["nom_" + langue]: e["id_ap"] for e in donnees().emplacements})
    t.update({e["nom_" + langue]: e["id_ap"] for e in EMPLACEMENTS_V3.values()})
    t.update({b["nom_" + langue]: b["id_ap"] for b in TOUS_LES_BOSS})
    t[QUETE_VELO["nom_" + langue]] = QUETE_VELO["id_ap"]
    t.update({x["nom_" + langue]: x["id_ap"] for x in TABLOS_CREES})
    t.update({q["nom_" + langue]: q["id_ap"] for q in QUETES})
    t.update({c["nom_" + langue]: c["id_ap"] for c in CHAPITRES_CHECKS})
    t[RANG_D_CHECK["nom_" + langue]] = RANG_D_CHECK["id_ap"]
    t.update({a["nom_" + langue]: a["id_ap"] for a in AMIS})
    t.update({a["nom_" + langue]: a["id_ap"] for a in INVITES})
    t.update({a["nom_" + langue]: a["id_ap"] for a in AMIS_5_ETOILES})       # (armées : déjà dans AMIS, même nom)
    t[AMI_BANANAR["nom_" + langue]] = AMI_BANANAR["id_ap"]                   # V3, lot 21
    t.update({c["nom_" + langue]: c["id_ap"] for c in CRIMINELS})
    t.update({a["nom_" + langue]: a["id_ap"] for a in BOUTIQUES_ARTICLES})
    t.update({x["nom_" + langue]: x["id_ap"] for x in DI.LOCATIONS})     # V3, lot C1 : distributeurs
    # V3, lot 3 : locations d'après-jeu déclarées (ouvertes ou non) et Tablo-blabla n° 24 (identifiant réservé en V2)
    t.update(AJ.tous_les_noms(langue))
    t.update({x["nom_" + langue]: x["id_ap"] for x in TABLOS if x.get("apres_jeu")})
    t.update({a["nom_" + langue]: a["id_ap"] for a in MD.AMIS_VOIE})      # V3, lot 18 : 7 amis de la Voie du mystère
    return t


def groupes_objets(langue: str) -> Dict[str, Set[str]]:
    g: Dict[str, Set[str]] = {}
    for o in donnees().objets:
        g.setdefault(NOMS_GROUPES[langue][o["famille"]], set()).add(o["nom_" + langue])
    return g


def region_ami(a: dict) -> Optional[str]:
    """Région d'un check « Ami » lié à un lieu (amis_criminels.py) : ami d'histoire = région de l'évènement « Chapitre N
    terminé », ami de requête = région de la requête, ami d'évènement = région de la carte du combat ; None : sans
    région (espèce sauvage, évolution, fusion : lieux selon le mélange calculé chez le joueur)."""
    if a["origine"] == "histoire":
        return next(ch["region"] for ch in donnees().chapitres if ch["numero"] == a["chapitre"])
    if a["origine"] == "requete":
        return QUETES_PAR_NUMERO[a["quete"]]["region"]
    if a["origine"] in ("evenement", "place") or "base_invite" in a:   # évolution d'un invité : région de l'Auberge
        return a["region"]
    if a["origine"] == "fusion_objet":                                  # région de la source de l'objet de fusion
        return a["region"]
    return None


def groupes_locations(langue: str) -> Dict[str, Set[str]]:
    noms_regions = {r["cle"]: r["nom_" + langue] for r in donnees().regions}
    g: Dict[str, Set[str]] = {NOMS_GROUPES[langue]["coffres"]: set(), NOMS_GROUPES[langue]["emplacements"]: set()}
    for c in coffres_possibles():
        g[NOMS_GROUPES[langue]["coffres"]].add(c["nom_" + langue])
        g.setdefault(noms_regions[c["region"]], set()).add(c["nom_" + langue])
    for e in donnees().emplacements:
        g[NOMS_GROUPES[langue]["emplacements"]].add(e["nom_" + langue])
    for e in EMPLACEMENTS_V3.values():
        g[NOMS_GROUPES[langue]["emplacements"]].add(e["nom_" + langue])
    g[NOMS_GROUPES[langue]["emplacements"]].add(QUETE_VELO["nom_" + langue])
    g.setdefault(noms_regions[QUETE_VELO["region"]], set()).add(QUETE_VELO["nom_" + langue])
    g[NOMS_GROUPES[langue]["boss"]] = {b["nom_" + langue] for b in TOUS_LES_BOSS}
    g[NOMS_GROUPES[langue]["boss_quetes"]] = {b["nom_" + langue] for b in BOSS_QUETES}
    g[NOMS_GROUPES[langue]["boss_melange"]] = {b["nom_" + langue] for b in BOSS_MELANGE}
    for b in TOUS_LES_BOSS:
        g.setdefault(noms_regions[b["region"]], set()).add(b["nom_" + langue])
    g[NOMS_GROUPES[langue]["tablos"]] = {x["nom_" + langue] for x in TABLOS_CREES}
    for x in TABLOS_CREES:
        g.setdefault(noms_regions[x["region"]], set()).add(x["nom_" + langue])
    g[NOMS_GROUPES[langue]["requetes"]] = {q["nom_" + langue] for q in QUETES if not q["service"]}
    g[NOMS_GROUPES[langue]["services"]] = {q["nom_" + langue] for q in QUETES if q["service"]}
    for q in QUETES:
        g.setdefault(noms_regions[q["region"]], set()).add(q["nom_" + langue])
    regions_chapitres = {ch["numero"]: ch["region"] for ch in donnees().chapitres}
    g[NOMS_GROUPES[langue]["histoire"]] = {c["nom_" + langue] for c in CHAPITRES_CHECKS} | {RANG_D_CHECK["nom_" + langue]}
    for c in CHAPITRES_CHECKS:
        g.setdefault(noms_regions[regions_chapitres[c["n"]]], set()).add(c["nom_" + langue])
    g.setdefault(noms_regions[RANG_D_CHECK["region"]], set()).add(RANG_D_CHECK["nom_" + langue])
    g[NOMS_GROUPES[langue]["amis"]] = {a["nom_" + langue] for a in AMIS}     # sans région (lieux selon le mélange),
    for a in AMIS:                                                 # sauf amis d'histoire, de requête et d'évènement
        region = region_ami(a)
        if region is not None:
            g.setdefault(noms_regions[region], set()).add(a["nom_" + langue])
    # invités de l'Auberge : dans leur région seulement ; les 16 de Pièce 5 étoiles (lot 20, option `pieces_speciales`) :
    # dans celle de la machine du Crank-a-kai (les groupes ne dépendent pas des options : les 28 invités de la V2 que
    # cette option sort de l'Auberge restent dans le groupe de l'Auberge)
    for a in INVITES + AMIS_5_ETOILES + [AMI_BANANAR]:
        g.setdefault(noms_regions[a["region"]], set()).add(a["nom_" + langue])
    g[NOMS_GROUPES[langue]["criminels"]] = {c["nom_" + langue] for c in CRIMINELS}
    g[NOMS_GROUPES[langue]["boutiques"]] = {a["nom_" + langue] for a in BOUTIQUES_ARTICLES}
    for a in BOUTIQUES_ARTICLES:
        g.setdefault(noms_regions[BOUTIQUES_PAR_CODE[a["boutique"]]["region"]], set()).add(a["nom_" + langue])
    # V3, lot C1 : distributeurs (groupe « Distributeurs » et groupe de la région de la carte)
    g[NOMS_GROUPES[langue]["distributeurs"]] = {x["nom_" + langue] for x in DI.LOCATIONS}
    for x in DI.LOCATIONS:
        g.setdefault(noms_regions[x["region"]], set()).add(x["nom_" + langue])
    # V3, lot 3 : après-jeu (groupe « Après-jeu » et groupe de la région) et terrains du mode Blasters
    aj = g.setdefault(NOMS_GROUPES[langue]["apres_jeu"], set())
    aj.update(c["nom_" + langue] for c in coffres_apres_jeu())
    # (lot 18 : les 7 amis des machines de la Voie du mystère, comme les autres amis d'après-jeu)
    for x in list(AJ.EMPLACEMENTS.values()) + AJ.QUETES + AJ.BOSS + AJ.BOSS_MEDAILLE + AJ.AMIS + MD.AMIS_VOIE:
        aj.add(x["nom_" + langue])
        g.setdefault(noms_regions[x["region"]], set()).add(x["nom_" + langue])
    # (lot 22 : « Ami : Domniscian », dans la région de son terrain)
    aj.add(AJ.AMI_DOMNISCIAN["nom_" + langue])
    g.setdefault(noms_regions[AJ.BLASTERS_PAR_TERRAIN[13]["region"]], set()).add(AJ.AMI_DOMNISCIAN["nom_" + langue])
    # (lot 22-bis : « Ami : Jiganyan / Komak », dans la région du PNJ de leur invitation, comme leur terrain)
    for a in AJ.AMIS_BLASTERS:
        pnj = next(x for x in AMIS if x.get("objet") == AJ.BLASTERS_PAR_TERRAIN[a["terrain"]]["invitation"])
        g.setdefault(noms_regions[pnj["region"]], set()).add(a["nom_" + langue])
    for x in TABLOS:
        if x.get("apres_jeu"):
            aj.add(x["nom_" + langue])
            g.setdefault(noms_regions[AJ.TABLO_24_REGION], set()).add(x["nom_" + langue])
    g[NOMS_GROUPES[langue]["blasters"]] = {b["nom_" + langue] for b in AJ.BLASTERS}
    # V3, lot 6 : requêtes à transfert d'avant la fin et leurs amis (option `requetes_transfert`) : dans le groupe de
    # leur région seulement (les groupes « Requêtes » et « Amis » restent ceux des tables de la V2)
    for q in AJ.QUETES_TRANSFERT:
        g.setdefault(noms_regions[q["region"]], set()).add(q["nom_" + langue])
    for a in AJ.AMIS_TRANSFERT:
        g.setdefault(noms_regions[AJ.QUETES_TRANSFERT_PAR_NUMERO[a["quete"]]["region"]], set()).add(a["nom_" + langue])
    return g


# ---------------------------------------------------------------------------
# Plan d'une graine (dépend des options)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Regle:
    chapitres: int = 0                          # nombre de chapitres terminés (évènement « Chapitre N terminé »)
    objets: Tuple[str, ...] = ()                # clés d'objets exigés
    rangs: int = 0                              # exemplaires de « Rang de montre » exigés (verrou « rangs » actif)
    # V3, lot 20 : EXEMPLAIRES exigés d'un objet à plusieurs exemplaires ((clé, nombre), …, triés) : « k Pièces 5
    # étoiles », « 3 Pile ou passe »… Vide pour toute règle d'avant (pieces.py ; option `pieces_speciales`).
    nombres: Tuple[Tuple[str, int], ...] = ()


@dataclass
class LocationPlan:
    nom: str
    id_ap: Optional[int]                        # None : évènement (chapitre, objectif)
    region: str                                 # clé de région
    regle: Regle
    genre: str                                  # "coffre", "emplacement", "boss", "quete", "tablo", "requete", "rang",
    #                                             "ami", "criminel", "boutique", "invite" (invité de l'Auberge),
    #                                             "distributeur" (V3, lot C1 : cle = « carte/rang/boisson »),
    #                                             "histoire" (check « chapitre N terminé »), "chapitre" (évènement),
    #                                             "objectif"
    prologue: bool = True                       # exige aussi le Filet quand le Filet est exigé
    exclue: bool = False                        # remplissage seulement (LocationProgressType.EXCLUDED)
    portail: Optional[str] = None               # check « tardif » des portails mystères (PORTAILS) : toujours exclue
    verrou: Optional[str] = None                # objet (clé) placé d'office ici, à son emplacement d'origine
    evenement: Optional[str] = None             # nom de l'objet d'évènement placé ici
    cle: Optional[str] = None                   # emplacement : clé de l'objet d'origine ; chapitre : numéro
    index_tbox: Optional[int] = None            # coffre : index TBox ; emplacement : bit TBox du check
    flag: Optional[int] = None                  # boss d'histoire : index du flag bit global posé à la victoire ;
    #                                             Tablo-blabla : flag « Yo-kai appelé »
    quete: Optional[int] = None                 # boss de quête, « quete », « requete » : numéro de la quête (phase 255
    #                                             = terminée)
    phase_min: Optional[int] = None             # V3, emplacement : check dès que la phase de `quete` atteint cette valeur
    hachages: Tuple[int, ...] = ()              # V3, emplacement : hachages d'origine du don (un par personnage joué)
    octet: Optional[int] = None                 # boss (Taprice) : index d'un octet global de catégorie 6 (P + 0x144 + i) ;
    seuil: Optional[int] = None                 # check quand l'octet atteint ce seuil (valeur qui ne décroît jamais)
    service: bool = False                       # « requete » : service (genre 3 de QUEST_CONFIG, 255 transitoire)
    medaille: Optional[int] = None              # « ami », « invite » : n° du Médaillium (bit « ami » de P+0x44C / P+0x604)
    medailles: Tuple[int, ...] = ()             # « ami » : tous les n° qui valent le check (Ultramax N ou K), sinon vide
    etapes: Optional[int] = None                # « criminel » : nombre d'étapes (arrêté : octet P+0x2D0+n >= etapes)
    boutique: Optional[str] = None              # « boutique » : code N0xx de la boutique (fichier shop_shpN0xx)
    entrees: Tuple[int, ...] = ()               # « boutique » : rang(s) de l'entrée SHOP_CONFIG_INFO de l'article dans
    #                                             son fichier (hachage lu dans la ROM du joueur par le client)
    nb_entrees: Optional[int] = None            # « boutique » : nombre d'entrées du fichier (contrôle de la ROM)
    bit: Optional[int] = None                   # « boutique » : bit persistant « premier achat fait » (boite.h)
    apres_jeu: Optional[str] = None             # V3, lot 3 : location d'après-jeu (clé de sa région) ou terrain « long »
    #                                             du mode Blasters (AJ.MARQUE_BLASTERS_LONG) : mention du lanceur ;
    #                                             lot 6 : AJ.MARQUE_TRANSFERT (requête à transfert d'avant la fin)
    terrain: Optional[int] = None               # « blasters » : n° du terrain de Ψ Blasters (bit du mot P + 0x64C)


@dataclass
class Plan:
    langue: str
    regions: List[Tuple[str, str]]                              # (clé, nom)
    connexions: List[Tuple[str, str, Regle]]
    locations: List[LocationPlan]
    pool_objets_cles: List[str]                                 # objets-clés mélangés (clés)
    exiges: FrozenSet[str]                                      # objets cités par au moins une règle
    melanges: FrozenSet[str]                                    # objets d'emplacements mélangés
    verrous_actifs: Tuple[str, ...]
    boss: str = BOSS_PAR_DEFAUT                                 # mode de l'option `boss`
    rangs: int = 0                                              # exemplaires de « Rang de montre » dans le pool
    rangs_reel: bool = False                                    # verrou « rangs » en mode « rang réel » (§17)
    rang_s_objet: bool = False                                  # ap/rang-s-objet : rang S = 5e exemplaire (§23)
    velo: bool = False                                          # verrou « velo » actif (objet et location ajoutés)
    tablos: str = TABLOS_PAR_DEFAUT                             # mode de l'option `tablos`
    quetes: str = QUETES_PAR_DEFAUT                             # mode de l'option `quetes`
    chapitres: bool = CHAPITRES_CHECKS_PAR_DEFAUT               # option `chapitres` : checks « chapitre N terminé »
    amis: str = AMIS_PAR_DEFAUT                                 # mode de l'option `amis`
    criminels: str = CRIMINELS_PAR_DEFAUT                       # mode de l'option `yo_criminels`
    objets_evenement: bool = False                              # option `objets_evenement` : objets des Yo-kai d'évènement
    invites: bool = False                                       # option `invites` : invitations dans le pool et checks
                                                                # « Ami : <invité> » (archipelago_invites.md §15)
    # V3, lot 14 : `invites_armees` : les 16 des armées à l'Auberge (paramètre interne, aucune option : posé par
    # l'objectif « medaillium_complet »). (L'option `invites_5_etoiles` du même lot est retirée : lot 20.)
    invites_armees: bool = False
    # V3, lot 20 : option `pieces_speciales` (pieces.py) : pièces spéciales du Crank-a-kai au pool, leurs Yo-kai hors
    # de l'Auberge ; `pieces_ordre` : ordre de sortie des 16 de la Pièce 5 étoiles de CETTE graine (n° du Médaillium ;
    # vide sans l'option)
    pieces_speciales: bool = False
    pieces_ordre: Tuple[int, ...] = ()
    # V3, lot 21 : graine à pièces spéciales générée depuis le lot 21 (Bananar et sa Pièce bleu ciel, fusions régionales
    # non exclues ; fonction 47 du patch) ; `photos` : le client pose l'option étendue 33 (photos de Ψ Blasters tenues
    # pour prises : objectif « medaillium_complet » ; lot 22 : aussi `blasters` = tous). Faux tous les deux : le plan
    # d'avant.
    lot21: bool = False
    photos: bool = False
    # V3, lot 22 : graine à pièces spéciales générée depuis le lot 22 (Pièce bleu ciel invendable : fonction 48 du
    # patch exigée ; sans effet sur les locations). Faux : le plan d'avant.
    lot22: bool = False
    armees: bool = False                                        # checks « Ami » des 16 des armées (mélange des Yo-kai
                                                                # par rencontre, archipelago_amis_criminels.md §11)
    boutiques: str = BOUTIQUES_PAR_DEFAUT                       # mode de l'option `boutiques`
    boutiques_prix_max: int = PRIX_MAX_PAR_DEFAUT               # option `boutiques_prix_max` (classe de prix)
    # V3, lot C1 : option `distributeurs` (« aucun » : le plan d'avant ; « tous » : 108 checks, distributeurs.py)
    distributeurs: str = DI.PAR_DEFAUT
    classification: Dict[str, str] = field(default_factory=dict)
    nb_remplissage: int = 0
    objet_prologue: Optional[str] = None                        # le Filet, s'il est exigé en logique
    # V3, lot 3 (apres_jeu.py) : objectif de la graine, étendue des checks d'après-jeu, terrains du mode Blasters
    objectif: str = AJ.OBJECTIF_V2
    apres_jeu: str = AJ.APRES_JEU_PAR_DEFAUT
    blasters: str = AJ.BLASTERS_PAR_DEFAUT
    # V3, lot 6 : option `requetes_transfert` (requêtes 107 à 116, fonction 37 du patch) ; verrous étendus du jeu portés
    # par un objet d'après-jeu de la graine (AJ.VERROUS_JEU : Pass sortilège, 4 clés de la Voie du mystère)
    transfert: bool = False
    verrous_aj: Tuple[str, ...] = ()
    # V3, lot 9 : option `parchemins` (les trois Parchemins sont dans le pool)
    parchemins: bool = False
    # V3, lot 10 : mélange des boss d'après-jeu tiré à la génération (place -> occupant, identités omises, trié) : la
    # place du boss de l'objectif et les checks par espèce en dépendent ; vide : boss d'après-jeu à leur place
    boss_sigma: Tuple[Tuple[str, str], ...] = ()
    # V3, lot 18 : objectif « medaillium_complet » (medaillium.py) : {"seuil", "comptes", "voies": {n°: {classe,
    # etat, region, regle, note}}} ; None pour tout autre objectif
    medaillium: Optional[dict] = None
    # V3, lots M2b (zones.py) : zone de chaque Yo-kai demandé ((n° du Médaillium, zone), triés), tirée à la génération ;
    # vide : graine sans zones (mélange des Yo-kai de la version 6 ou antérieure, règles d'avant)
    yokai_zones: Tuple[Tuple[int, str], ...] = ()
    # V3, lot L1 : légendaires mélangés entre eux (legendaires.py) : ((sceau, légendaire donné), …) triés par sceau,
    # n° du Médaillium (sceau = n° de son légendaire d'origine) ; vide : chaque sceau donne son légendaire d'origine
    legendaires: Tuple[Tuple[int, int], ...] = ()
    # Audit softlock (2026-10-26, QUETES_CHANTIER) : graine générée depuis la fonction 52 du patch (flag 584 du chantier
    # lu vrai dès l'appel du Tablo-blabla n° 9) ; faux : graine d'avant, règles d'avant
    chantier: bool = False
    # V3 (2026-10-25) : graine générée depuis l'exclusion des étages de la Tour du commerce (TOUR_COMMERCE_COFFRES) ;
    # faux : le plan d'avant
    tour_commerce: bool = False
    # V3 (2026-10-27) : graine générée depuis les règles « Yo-kai obtenable » des Tablo-blabla (panneaux sans voie non
    # créés : TABLOS_SANS_TRANSFERT, TABLOS_EVENEMENT, TABLOS_APRES_JEU) ; faux : les panneaux d'avant
    tablos_apparition: bool = False
    # ap/portails-donjon : option `donjon_portails` (cinq clés du donjon des portails au pool, verrous k = 62..66 ;
    # coffres 444 à 452 non exclus) ; faux : plan d'avant (donjon_portails.py)
    donjon_portails: bool = False

    @property
    def objectif_medailles(self) -> Tuple[int, ...]:
        """N° du Médaillium exigés par l'objectif (victoire = partie terminée ET tous ces bits) ; vide : objectif de
        la V2 (partie terminée seulement). Structure générique : un boss = un n°."""
        if self.medaillium is not None:
            return tuple(range(1, MD.TOTAL + 1))
        o = AJ.OBJECTIFS_BOSS.get(self.objectif)
        return tuple(o["medailles"]) if o else ()

    @property
    def objectif_seuil(self) -> Optional[int]:
        """V3, lot 18 : nombre de n° de `objectif_medailles` qui suffit à la victoire (None : tous)."""
        return self.medaillium["seuil"] if self.medaillium is not None else None

    @property
    def nom_objectif(self) -> str:
        """Nom de l'évènement de victoire de CE plan."""
        return next(loc.nom for loc in self.locations if loc.genre == "objectif")

    @property
    def filet_en_sphere_0(self) -> bool:
        """Vrai si le Filet est mélangé et exigé : il doit être atteignable avant tout le reste (§5.1)."""
        return self.objet_prologue is not None and self.objet_prologue in self.melanges

    @property
    def pile_en_sphere_2(self) -> bool:
        """Vrai si la Pile ou passe est mélangée et son verrou actif : elle doit être atteignable avec les Filets
        et les évènements du chapitre 1 (sphère 3 au plus du parcours, objets_cles §14.8), comme le Filet l'est sans
        rien (§12.7)."""
        return OBJET_PILE in self.melanges and OBJET_PILE in self.verrous_actifs

    def location(self, nom: str) -> LocationPlan:
        for loc in self.locations:
            if loc.nom == nom:
                return loc
        raise KeyError(nom)


def normaliser_boss(boss) -> str:
    """Option `boss` : nom du mode, ou booléen (True = histoire)."""
    if boss is True:
        return "histoire"
    if boss is False or boss is None:
        return "aucun"
    if boss not in MODES_BOSS:
        raise ValueError(f"mode de boss inconnu : {boss!r}")
    return boss


def normaliser_tablos(tablos) -> str:
    """Option `tablos` : nom du mode, ou booléen (True = tous)."""
    if tablos is True:
        return "tous"
    if tablos is False or tablos is None:
        return "aucun"
    if tablos not in MODES_TABLOS:
        raise ValueError(f"mode de Tablo-blabla inconnu : {tablos!r}")
    return tablos


def normaliser_quetes(quetes) -> str:
    """Option `quetes` : nom du mode, ou booléen (True = requetes)."""
    if quetes is True:
        return "requetes"
    if quetes is False or quetes is None:
        return "aucune"
    if quetes not in MODES_QUETES:
        raise ValueError(f"mode de quêtes inconnu : {quetes!r}")
    return quetes


def normaliser_amis(amis) -> str:
    """Option `amis` : nom du mode, ou booléen (True = tous)."""
    if amis is True:
        return "tous"
    if amis is False or amis is None:
        return "aucun"
    if amis not in MODES_AMIS:
        raise ValueError(f"mode d'amis inconnu : {amis!r}")
    return amis


def normaliser_criminels(criminels) -> str:
    """Option `yo_criminels` : nom du mode, ou booléen (True = tous)."""
    if criminels is True:
        return "tous"
    if criminels is False or criminels is None:
        return "aucun"
    if criminels not in MODES_CRIMINELS:
        raise ValueError(f"mode de Yo-criminels inconnu : {criminels!r}")
    return criminels


def normaliser_boutiques(boutiques) -> str:
    """Option `boutiques` : nom du mode, ou booléen (True = principales)."""
    if boutiques is True:
        return "principales"
    if boutiques is False or boutiques is None:
        return "aucune"
    if boutiques not in MODES_BOUTIQUES:
        raise ValueError(f"mode de boutiques inconnu : {boutiques!r}")
    return boutiques


def normaliser_objectif(objectif=AJ.OBJECTIF_V2, apres_jeu=AJ.APRES_JEU_PAR_DEFAUT) -> Tuple[str, str]:
    """Options `objectif` et `apres_jeu` (V3, lot 3). L'objectif de la V2 force `apres_jeu` à « aucun » : rien
    d'après-jeu n'entre alors dans la graine (décision de l'humain)."""
    objectif = AJ.OBJECTIF_V2 if objectif is None else objectif
    apres_jeu = AJ.APRES_JEU_PAR_DEFAUT if apres_jeu in (None, False) else ("complet" if apres_jeu is True else apres_jeu)
    if objectif not in AJ.OBJECTIFS:
        raise ValueError(f"objectif inconnu : {objectif!r}")
    if apres_jeu not in AJ.MODES_APRES_JEU:
        raise ValueError(f"mode d'après-jeu inconnu : {apres_jeu!r}")
    if objectif == MD.OBJECTIF:
        return objectif, "complet"         # lot 18 : tout l'après-jeu est dans la partie
    return objectif, (AJ.APRES_JEU_PAR_DEFAUT if objectif == AJ.OBJECTIF_V2 else apres_jeu)


def voie_dans_la_graine(objectif=AJ.OBJECTIF_V2, apres_jeu=AJ.APRES_JEU_PAR_DEFAUT) -> bool:
    """La Voie du mystère (ses 4 clés au pool, ses 4 régions) est-elle dans la graine ? Objectif d'après-jeu et checks
    d'après-jeu « complet » (forcé par « medaillium_complet ») : ap/boss-voie-mystere, version 3 du mélange des boss."""
    o, aj = normaliser_objectif(objectif, apres_jeu)
    return o != AJ.OBJECTIF_V2 and aj == "complet" and AJ.VERROUS_DISPONIBLES["voie_du_mystere"]


def normaliser_blasters(blasters) -> str:
    """Option `blasters` : nom du mode, ou booléen (True = tous)."""
    if blasters is True:
        return "tous"
    if blasters is False or blasters is None:
        return "aucun"
    if blasters not in AJ.MODES_BLASTERS:
        raise ValueError(f"mode de Blasters inconnu : {blasters!r}")
    return blasters


def normaliser_options(objets_cles_melanges=True, verrous_actifs=()) -> Tuple[bool, FrozenSet[str]]:
    v = frozenset(verrous_actifs)
    inconnus = v - set(VERROUS_A_ACTIVER)
    if inconnus:
        raise ValueError(f"verrous inconnus : {sorted(inconnus)}")
    # Mirapo de poche : le 1er exemplaire de son objet progressif EST l'objet des Miroirs (verrou k = 53 actif aussi)
    if VERROU_MIRAPO in v:
        v = v | {OBJET_MIROIRS}
    # verrou sans implémentation dans le patch : ignoré (règle R2 : la logique n'exige que les verrous réels)
    return bool(objets_cles_melanges), v & verrous_implementes()


# V3, lots M2b : règles de zone appliquées (False : le modèle de l'audit doit contredire, `audit_logique --zones
# --sans-regles`)
REGLES_ZONES = True


def _union_regles(*regles: Regle) -> Regle:
    """Conjonction de règles : chapitres et rangs au maximum, objets réunis."""
    nombres: Dict[str, int] = {}
    for r in regles:
        for k, n in r.nombres:
            nombres[k] = max(nombres.get(k, 0), n)
    return Regle(max([r.chapitres for r in regles] or [0]),
                 tuple(sorted(set().union(*[set(r.objets) for r in regles]))),
                 max([r.rangs for r in regles] or [0]), tuple(sorted(nombres.items())))


def _voies_medaillium(locations, connexions, regle_objectif, sigma_aj, regions_ok, objets_presents, seuil,
                      regle_quete, regle_quete_aj, rang_s, voies_ps=None, lot21=True, exigibles=frozenset(),
                      membres_leg=None):
    """V3, lot 18 (objectif « medaillium_complet ») : (description de `Plan.medaillium`, règle de victoire).

    Chaque n° du Médaillium (1 à 448) reçoit UNE voie : celle d'une location du plan qui porte son n° (ami, invité,
    place de boss), sinon celle de la table `medaillium.VOIES`. Un n° sans voie lève ValueError : la table doit couvrir
    les 448. Règle d'une voie : la sienne quand elle est certaine (don de l'histoire ou d'une requête, invité de
    l'Auberge), sinon la sienne ET « le monde d'avant la fin entièrement ouvert » (`r_monde` : fin de l'histoire et
    toutes les connexions de régions), parce que le lieu d'une espèce sauvage dépend du mélange fait chez le joueur.
    Règle de victoire = conjonction de TOUTES les voies comptées et de toutes les connexions (quel que soit le seuil).
    """
    par_cible = {c: r for _s, c, r in connexions}

    def acces(region) -> Regle:
        """Règle d'accès d'une région d'après-jeu (chaîne de ses sources) ; région d'avant la fin : `r_monde`."""
        rs = []
        while region in AJ.REGIONS and region in par_cible:
            rs.append(par_cible[region])
            region = AJ.REGIONS[region]["source"]
        return _union_regles(*rs)
    r_monde = _union_regles(regle_objectif, *[r for _s, c, r in connexions if c not in AJ.REGIONS])
    amis = {n: a for a in AMIS for n in a.get("medailles", (a["medaille"],))}
    amis_aj = {a["medaille"]: a for a in AJ.AMIS}
    amis_voie = {a["medaille"] for a in MD.AMIS_VOIE}
    transfert = {a["medaille"] for a in AJ.AMIS_TRANSFERT}
    voies: Dict[int, dict] = {}
    terrain_ami = {a["medaille"]: t for t, a in AJ.AMIS_PAR_TERRAIN.items()}     # (ap/blasters-terrains-apworld)

    def poser(n, classe, etat, region, regle, note="", strict=False):
        if n in voies:
            if strict:
                raise ValueError(f"Médaillium : le n° {n} a déjà une voie ({voies[n]['classe']})")
            return
        voies[n] = {"classe": classe, "etat": etat, "region": region, "regle": regle, "note": note}

    r_boss = [r_monde]
    for loc in locations:
        if loc.id_ap is None:
            continue
        if loc.genre == "boss" and not loc.apres_jeu and loc.cle in MD.BOSS_AVANT:
            r_boss.append(loc.regle)
    r_boss = _union_regles(*r_boss)
    for loc in locations:
        if loc.id_ap is None:
            continue
        large = _union_regles(r_monde, acces(loc.region), loc.regle)
        if loc.genre == "invite":
            for n in loc.medailles or (loc.medaille,):
                poser(n, "invite", MD.HASARD, loc.region, loc.regle)
        elif loc.genre == "ami":
            for n in loc.medailles or (loc.medaille,):
                if voies_ps and n in voies_ps:
                    # lot 20 : Yo-kai d'une pièce spéciale du pool : voie certaine (sa règle), sauf les fusions
                    # régionales (comme les autres fusions à objet du pool : « hasard »)
                    classe, etat, note = voies_ps[n]
                    poser(n, classe, etat, loc.region, loc.regle if etat == MD.GARANTIE else large, note)
                elif AJ.OBJET_TERRAIN.get(terrain_ami.get(n)) in loc.regle.objets:
                    # ap/blasters-terrains-apworld : « Ami » d'un terrain de Ψ Blasters ouvert par son objet (bit posé
                    # par la première victoire sur le terrain) : la règle de la location, objet compris
                    poser(n, "blasters", MD.HASARD, loc.region, large, "terrain de Ψ Blasters ouvert par son objet")
                elif n in amis_voie:
                    poser(n, "machine_voie", MD.FRAGILE, loc.region, large,
                          "pièce du boss de la ligne, tirage dirigé (rien de cette chaîne n'a été essayé en jeu)")
                elif loc.apres_jeu == AJ.MARQUE_TRANSFERT or n in transfert:
                    poser(n, "transfert", MD.HASARD, loc.region, large, "don à 7,5 % par revanche gagnée")
                elif loc.apres_jeu and n in amis_aj:
                    a = amis_aj[n]
                    if a["origine"] == "sauvage":
                        poser(n, "sauvage_apres_jeu", MD.HASARD, loc.region, large)
                    elif a["origine"] == "don":
                        poser(n, "don", MD.HASARD if a["objets"] else MD.GARANTIE, loc.region, large)
                    elif a["origine"] == "legendaire":
                        poser(n, "legendaire", MD.HASARD, loc.region, large, "sceau : ses huit membres amis")
                    else:
                        poser(n, "transfert", MD.HASARD, loc.region, large, "don à 7,5 % par revanche gagnée")
                elif n in amis:
                    a = amis[n]
                    o = a["origine"]
                    if o in ("histoire", "requete"):
                        poser(n, o, MD.GARANTIE, loc.region, loc.regle)
                    else:
                        note = "sans mélange des Yo-kai : salle de portail mystère ou Crank-a-kai seulement" \
                            if a.get("portail") else ""
                        poser(n, o, MD.HASARD, loc.region, large, note)
        elif loc.genre == "boss" and loc.apres_jeu and (loc.medaille is not None or loc.cle in AJ.BOSS_PAR_CLE):
            place = AJ.BOSS_PAR_CLE[loc.cle]["place"] if loc.cle in AJ.BOSS_PAR_CLE else loc.cle
            occ = AJ.occupant(place, sigma_aj)
            ns = [loc.medaille if loc.medaille is not None else AJ.MEDAILLE_BOSS[occ]]
            ns += [MD.BOSS_SECOND[occ]] if occ in MD.BOSS_SECOND else []
            for n in ns:
                if occ in AJ.BOSS_BIT_NON_PROUVE:
                    poser(n, "vaincre", MD.FRAGILE, loc.region, large, MD.NOTE_INFINIRIS)
                elif occ == "mckraken":
                    poser(n, "vaincre", MD.FRAGILE, loc.region, large,
                          "exige le Yo-kai du Tablo-blabla n° 24 ; victoire non relue")
                else:
                    poser(n, "vaincre", MD.GARANTIE, loc.region, large)
    for ns in MD.BOSS_AVANT.values():
        for n in ns:
            poser(n, "vaincre", MD.GARANTIE, None, r_boss, "boss d'avant la fin (sa place suit le mélange des boss)")
    # (lot 21 : une graine d'avant garde ses deux n° non comptés, Domniscian et Bananar)
    for n, v in ({**MD.VOIES, **({} if lot21 else MD.VOIES_AVANT_LOT21)}).items():
        if n in voies and voies[n]["classe"] == "blasters":
            continue                # (ap/blasters-terrains-apworld : voie de la location « Ami » du terrain, ci-dessus)
        if n in voies and n in MD.MEDAILLES_BOSS_VOIE and voies[n]["classe"] == "vaincre":
            continue                # (ap/boss-voie-mystere : voie de la location « Boss : » de la place qui le contient)
        rs, region = [r_monde], v["region"]
        if v["quete"] is not None:
            q = QUETES_PAR_NUMERO.get(v["quete"]) or AJ.QUETES_TRANSFERT_PAR_NUMERO[v["quete"]]
            rs.append(regle_quete(q))
        if v["quete_aj"] is not None:
            q = AJ.QUETES_PAR_NUMERO[v["quete_aj"]]
            rs.append(regle_quete_aj(q))
            region = region or q["region"]
        if region is not None:
            if region not in regions_ok:
                raise ValueError(f"Médaillium : n° {n} dans une région fermée ({region})")
            rs.append(acces(region))
        for autre in v.get("regions", ()):               # lot 21 : régions d'après-jeu exigées en plus
            if autre not in regions_ok:
                raise ValueError(f"Médaillium : n° {n} dans une région fermée ({autre})")
            rs.append(acces(autre))
        manquants = [k for k in v["objets"] if k not in objets_presents]
        if manquants:
            raise ValueError(f"Médaillium : n° {n} exige un objet absent de la graine ({manquants})")
        # (objets à verrou : seulement ceux que la logique peut exiger ; un objet laissé à son emplacement d'origine
        # est donné par l'histoire : l'exiger créerait des boucles)
        objets_voie = tuple(v["objets"]) + tuple(k for k in v.get("objets_si_presents", ()) if k in exigibles)
        rs.append(Regle(0, tuple(sorted(objets_voie)), rang_s if v["rang_s"] else 0))
        poser(n, v["classe"], v["etat"], region, _union_regles(*rs), v["note"], strict=True)
    for n in MD.PIECE_5_ETOILES:
        # (lot 20 : avec l'option `pieces_speciales`, que cet objectif force, les 16 ont une location et donc déjà
        # leur voie « piece » garantie ; ceci ne sert que si l'indicateur `MD.PIECES_SPECIALES_DISPONIBLE` est fermé)
        poser(n, "piece", MD.ATTENTE, None, r_monde, MD.NOTE_5_ETOILES)
    absents = [n for n in range(1, MD.TOTAL + 1) if n not in voies]
    if absents or len(voies) != MD.TOTAL:
        raise ValueError(f"Médaillium : n° sans voie déclarée : {absents}")
    # un légendaire dont un membre du sceau n'est pas compté (sans voie, ou en attente) ne l'est pas non plus (V3, lot
    # L1 : le sceau qui DONNE ce légendaire dans la graine)
    for n, membres in (membres_leg or MD.SCEAUX).items():
        pires = [voies[m]["etat"] for m in membres if voies[m]["etat"] not in MD.ETATS_COMPTES]
        if pires and voies[n]["classe"] == "legendaire":
            voies[n]["etat"] = MD.SANS_VOIE if MD.SANS_VOIE in pires else MD.ATTENTE
            voies[n]["note"] = "sceau : %d membre(s) sans voie comptée" % len(pires)
    comptes = sorted(n for n, v in voies.items() if v["etat"] in MD.ETATS_COMPTES)
    r_tout = _union_regles(r_monde, *[r for _s, _c, r in connexions], *[voies[n]["regle"] for n in comptes])
    for n in comptes:
        if voies[n]["classe"] == "legendaire":
            voies[n]["regle"] = r_tout
    return {"seuil": seuil, "comptes": len(comptes), "voies": voies}, r_tout


def construire_plan(langue: str = "fr", objets_cles_melanges: bool = True, verrous_actifs=(),
                    boss=BOSS_PAR_DEFAUT, tablos=TABLOS_PAR_DEFAUT, quetes=QUETES_PAR_DEFAUT,
                    chapitres=CHAPITRES_CHECKS_PAR_DEFAUT, amis=AMIS_PAR_DEFAUT,
                    yo_criminels=CRIMINELS_PAR_DEFAUT, objets_evenement=OBJETS_EVENEMENT_PAR_DEFAUT,
                    boutiques=BOUTIQUES_PAR_DEFAUT, boutiques_prix_max=PRIX_MAX_PAR_DEFAUT,
                    rangs_reel: bool = True, invites: bool = INVITES_PAR_DEFAUT,
                    boutiques_retirees: bool = True, places: bool = PLACES_PAR_DEFAUT,
                    armees: bool = False, objectif=AJ.OBJECTIF_V2, apres_jeu=AJ.APRES_JEU_PAR_DEFAUT,
                    blasters=AJ.BLASTERS_PAR_DEFAUT, transfert: bool = False,
                    parchemins: bool = PARCHEMINS_PAR_DEFAUT, boss_sigma=None,
                    boss_especes: bool = True, pieces_speciales: bool = PS.OPTION_PAR_DEFAUT,
                    invites_armees: bool = False, medaillium_seuil: Optional[int] = None,
                    pieces_ordre=None, lot21: bool = True, lot22: bool = True, lot22bis: bool = True,
                    distributeurs=DI.PAR_DEFAUT, legendaires=None, yokai_zones=None,
                    chantier: bool = CHANTIER_PAR_DEFAUT,
                    tour_commerce: bool = TOUR_COMMERCE_PAR_DEFAUT,
                    tablos_apparition: bool = TABLOS_APPARITION_PAR_DEFAUT,
                    donjon_portails: bool = DP.OPTION_DONJON_PAR_DEFAUT,
                    blasters_terrains: bool = AJ.BLASTERS_TERRAINS_PAR_DEFAUT,
                    rang_s_objet: bool = True, boss_voie: bool = True) -> Plan:
    """Construit le plan d'une graine pour ces options (pur, déterministe). `boss_voie` (ap/boss-voie-mystere) : les
    4 places de boss de la Voie du mystère ont une location « Boss : … » (bit du Médaillium de leur occupant) quand la
    Voie est dans la graine : True pour toute nouvelle graine ; False = graine générée avant (le tracker le lit dans
    slot_data : aucune de ces locations dans sa liste `amis`). `rangs_reel` : sémantique du verrou
    « rangs » (sans effet s'il est inactif) : True = mode « rang réel » (toute nouvelle graine), False = ancien mode
    (graine de format <= 19 : le tracker du lanceur le lit dans `slot_data.verrous_actifs`). `places` : Yo-kai
    d'évènement à leur emplacement d'origine (3 invitations et « Capsule favorite » dans le pool, leurs locations) :
    True pour toute nouvelle graine ; False = graine générée avant (le tracker le lit dans slot_data : pas de liste
    `evenement_places`), dont le pool n'a pas ces objets. `armees` : la graine garantit un lieu normal aux 16 Yo-kai
    des armées (`amis_criminels.armees_garanties` : mélange des Yo-kai par rencontre, version >= 4) : leurs checks
    « Ami » existent alors, avec l'option `amis` = tous (False par défaut : ni l'APWorld sans ce mélange, ni une graine
    générée avant). `objectif`, `apres_jeu`, `blasters` (V3, lot 3, `apres_jeu.py`) : objectif de la graine, étendue
    des checks d'après-jeu (forcée à « aucun » avec l'objectif de la V2), terrains du mode Blasters ; à leurs valeurs
    par défaut, le plan est exactement celui d'avant. `transfert` (V3, lot 6, option `requetes_transfert`) : les
    requêtes à transfert de sauvegarde 107 à 116 sont dans la graine (fonction 37 du patch) : six d'avant la fin (avec
    l'option `quetes`), quatre d'après-jeu (avec `apres_jeu` = complet), et leurs checks « Ami » (option `amis`).
    `parchemins` (V3, lot 9) : les trois Parchemins (objets du jeu donnés par code QR seulement) sont dans le pool.
    `boss_sigma` (V3, lot 10) : mélange des boss tiré à la génération (`boss_generation.tirer` : place -> occupant) ;
    seule sa partie d'après-jeu compte, et seulement avec un objectif d'après-jeu : l'évènement de victoire est dans
    la région de la place qui contient le boss de l'objectif, avec la règle de cette place. `boss_especes` (lot 10) :
    les places de boss d'après-jeu sans marqueur persistant ont une location (check = bit du Médaillium de leur
    occupant) : True pour toute nouvelle graine ; False = graine à objectif d'après-jeu générée avant le lot 10 (le
    tracker le lit dans slot_data : aucune de ces locations dans sa liste `amis`). `invites_armees` (V3, lot 14 ;
    interne, aucune option : posé par l'objectif « medaillium_complet ») : les 16 des armées sont des invités de
    l'Auberge ; leur location « Ami » (la même que celle du mélange par rencontre) est alors de genre « invite »,
    règle = leur invitation. `pieces_speciales` (V3, lot 20, option du même nom ; `pieces.py`) : pièces spéciales du
    Crank-a-kai au pool (16 Pièces 5 étoiles, 4 Pièces frisson, 9 pièces régionales, 3 Pile ou passe, 3 Super pile ou
    passe, 9 objets de fusion régionaux) ; 28 invités à invitation de la V2 quittent l'Auberge (leur location « Ami »
    garde son identifiant, de genre « ami », règle = leurs pièces et la machine du Crank-a-kai) et les 16 de Pièce 5
    étoiles reçoivent leur location ; `pieces_ordre` : ordre de sortie de ces 16 dans CETTE graine (n° du Médaillium,
    tiré à la génération ; None : l'ordre en dur du jeu). Faux tous les deux : le plan d'avant.
    `objectif` = « medaillium_complet » (V3, lot 18, `medaillium.py`) : victoire = `medaillium_seuil` n° du
    Médaillium (448 par défaut) ; FORCE `apres_jeu` = complet, `boss` = tous, `amis` = tous, `quetes` (au moins
    « requetes » : Pandanoko), `invites`,
    `invites_armees`, `objets_evenement`, `places` et `transfert` ; ajoute au pool le Grelot gris et les 9 objets de
    fusion tirés au sort, et 7 locations « Ami » (machines de la Voie du mystère) ; FORCE aussi `pieces_speciales`
    (lot 20 : voie des 16 de Pièce 5 étoiles et des deux légendaires dont ils sont le sceau).
    `lot21` (V3, lot 21 ; sans effet sans `pieces_speciales`) : True pour toute nouvelle graine : une « Pièce bleu
    ciel » de plus au pool et la location « Ami : Bananar » ; les 9 fusions régionales NON exclues, dans la région du
    Coteau fleuri, avec la règle de la requête 4 (fusion chez M. Zen) ; avec l'objectif « medaillium_complet » : les
    448 n° comptés (Domniscian : photos de Ψ Blasters tenues pour prises par le jeu, `Plan.photos`). False = graine à
    pièces générée avant le lot 21 (le tracker le lit dans slot_data : pas de fonction 47 dans `fonctions_exigees`).
    `lot22` (V3, lot 22) : True pour toute nouvelle graine : avec `blasters` = tous, les photos de Ψ Blasters tenues
    pour prises (`Plan.photos`) et les terrains de Triptyk (3, long) et de Domniscian (13, d'après-jeu) EXCLUS, et
    « Ami : Domniscian » avec `amis` = tous ; avec `apres_jeu` = complet et des boutiques, la boutique N045 (village
    du Château de Sawayama, 3 articles, hors du chemin de l'objectif : exclus). False = graine générée avant le lot 22
    (le tracker le lit dans slot_data : ni terrain 3 dans `blasters`, ni article de N045 dans `boutiques`).
    `lot22bis` (V3, lot 22-bis) : True pour toute nouvelle graine : avec `apres_jeu` = complet, la région de l'Entrain
    Express ouverte et des boutiques, les 13 articles fixes de la boutique N047 entrent aussi dans les modes
    `principales` / `une_par_boutique` (le mode `toutes` les avait déjà ; exclus) ; avec `amis` = tous, « Ami :
    Jiganyan » et « Ami : Komak » à côté de leurs terrains 11 / 12 (exclus). False = graine générée avant (le tracker
    le lit dans slot_data : ni ces deux amis dans `amis`, ni article de N047 dans `boutiques` hors du mode `toutes`).
    `legendaires` (V3, lot L1, option `legendaires_melanges` ; `legendaires.py`) : permutation des huit légendaires
    tirée à la génération (((sceau, légendaire donné), …), n° du Médaillium) : le check « Ami : L » prend la règle, la
    région et l'existence de l'entrée du SCEAU qui donne L ; la voie de L (objectif Médaillium) est ce sceau. None ou
    vide : le plan d'avant (chaque sceau donne son légendaire d'origine).
    `yokai_zones` (V3, lots M2b, `zones.py`) : {n° du Médaillium : zone} des Yo-kai demandés, tirés à la génération
    (`zones.tirer`) pour une graine à mélange des Yo-kai par rencontre de version 7 : toute location qui demande l'un
    d'eux (requête ou service, et celles qui l'exigent finie ; Tablo-blabla ; check « Ami » de ce Yo-kai ; don ou boss
    d'une de ces requêtes) exige aussi l'accès à sa zone (`zones.regle_zone`), ainsi que l'évènement « Chapitre N
    terminé » quand l'histoire attend (`zones.ATTENTES`) une requête qui le demande. None : plan d'avant.
    `chantier` (audit softlock, décision de l'humain du 2026-10-26) : True pour toute nouvelle graine : la fonction 52 du
    patch est exigée (flag 584 du chantier lu vrai dès l'appel du Tablo-blabla n° 9) et, avec des zones, les requêtes
    45 / 58 et ce qui en dépend exigent la zone de Sumochi (QUETES_CHANTIER). False = graine générée avant (le tracker le
    lit dans slot_data : 52 absent de `fonctions_exigees`) : les règles d'avant.
    `tour_commerce` (V3, décision de l'humain du 2026-10-25) : True pour toute nouvelle graine : les locations des étages
    de la Tour du commerce (TOUR_COMMERCE_COFFRES, TOUR_COMMERCE_QUETES : étages ouverts par le Tablo-blabla n° 11
    APPELÉ) sont EXCLUES. False = graine générée avant (le tracker le lit dans slot_data : pas de clé
    `tour_commerce_exclus`) : le plan d'avant.
    `tablos_apparition` (V3, décision de l'humain du 2026-10-27) : True pour toute nouvelle graine : les Tablo-blabla
    dont le Yo-kai n'a aucune voie dans la graine ne sont pas créés (TABLOS_SANS_TRANSFERT, TABLOS_EVENEMENT,
    TABLOS_APRES_JEU). False = graine générée avant (pas de clé `tablos_apparition` dans slot_data) : les panneaux
    d'avant. Dans les deux cas, la règle d'un panneau exige son Yo-kai obtenable (TABLOS_YOKAI).
    `donjon_portails` (ap/portails-donjon, décision de l'humain du 2026-10-27, option désactivée par défaut) : les cinq
    clés du donjon des portails au pool ; les règles des locations du donjon exigent leurs clés (donjon_portails.py) et
    les coffres 444 à 452 ne sont plus exclus ; aucune location du donjon ne garde la marque « portail ».
    `blasters_terrains` (ap/blasters-terrains-apworld, décision de l'humain du 2026-11-05, option désactivée par défaut,
    sans effet avec `blasters` = aucun) : un objet « Terrain : <boss> » par terrain 2..13 au pool (verrous k = 68..79,
    `apres_jeu.VERROUS_TERRAINS`) ; les 13 terrains sont des checks NORMAUX (« Chapitre 3 terminé » + l'objet du
    terrain ; Gargaros : le chapitre seul), comme « Ami : Domniscian / Jiganyan / Komak » (même règle que le terrain).
    False : le plan d'avant (le tracker le lit dans slot_data : clé `blasters_terrains`).
    `rang_s_objet` (ap/rang-s-objet) : rang S = 5e « Rang de montre » (graine nouvelle à objectif d'après-jeu, mode « rang
    réel », seulement si une location exige le rang S) ; False : graine d'avant (entrée « rangs_s » absente)."""
    _arguments = dict(locals())             # (ap/rang-s-objet : plan refait sans le 5e exemplaire s'il n'ouvre rien)
    if langue not in NOM_JEU:
        raise ValueError(langue)
    zones_y = ZN.valider_zones(yokai_zones) if yokai_zones else {}
    transfert = bool(transfert) and AJ.VERROUS_DISPONIBLES["transfert"]
    # V3, lot L1 : permutation des légendaires (forme seulement : les classes de faisabilité sont celles du tirage,
    # `legendaires.tirer` ; le tracker ne connaît pas toujours les options qui les fixent)
    perm_leg = ()
    if legendaires:
        perm_leg = LG.depuis_slot_data([list(x) for x in legendaires])
        if perm_leg is None:
            raise ValueError(f"légendaires : permutation invalide {legendaires!r}")
        if all(s == l for s, l in perm_leg):
            perm_leg = ()
    sceau_de_leg = LG.sceau_de(perm_leg)
    d = donnees()
    melanges_opt, actifs = normaliser_options(objets_cles_melanges, verrous_actifs)
    mode_objectif, mode_aj = normaliser_objectif(objectif, apres_jeu)
    mode_blasters = normaliser_blasters(blasters)
    # ap/blasters-terrains-apworld : un objet par terrain (sans effet sans terrain de Blasters dans la graine)
    terrains_bl = bool(blasters_terrains) and mode_blasters != "aucun"
    a_objectif_aj = mode_objectif != AJ.OBJECTIF_V2
    est_md = mode_objectif == MD.OBJECTIF
    if est_md:
        # lot 18 : tout ce qui porte une voie d'un n° du Médaillium est dans la partie, quelles que soient les options
        boss, amis, invites, invites_armees, objets_evenement, places = "tous", "tous", True, True, True, True
        if normaliser_quetes(quetes) in ("aucune", OJ.MODE_REQUETES_CLES):
            quetes = "requetes"         # Pandanoko (n° 287) ne vient que lorsque toutes les requêtes-checks sont faites
        transfert = AJ.VERROUS_DISPONIBLES["transfert"]
        seuil_md = MD.seuil_valide(medaillium_seuil)
        pieces_speciales = bool(pieces_speciales) or MD.PIECES_SPECIALES_DISPONIBLE     # lot 20
    # V3, lot 20 : pièces spéciales du Crank-a-kai (pieces.py)
    ps = bool(pieces_speciales)
    l21 = ps and bool(lot21)                    # lot 21 : Bananar, fusions régionales non exclues, 448 n° comptés
    ordre_ps = PS.ordre_valide(pieces_ordre) if ps else ()
    exigences_ps = PS.exigences(ordre_ps, l21) if ps else {}
    # mélange des boss d'après-jeu de la graine (permutation de `BG.APRES_JEU`, identités omises)
    sigma_aj = BG.apres_jeu(boss_sigma) if a_objectif_aj else {}
    if sorted(sigma_aj) != sorted(sigma_aj.values()) or any(x == y for x, y in sigma_aj.items()):
        raise ValueError("mélange des boss d'après-jeu : pas une permutation")
    # ap/boss-voie-mystere : boss de la Voie du mystère déplacés (version 3) seulement si la Voie est dans la graine
    if BG.version_de(sigma_aj) == BG.VERSION_VOIE and not voie_dans_la_graine(objectif, apres_jeu):
        raise ValueError("mélange des boss de la Voie du mystère sans la Voie du mystère dans la graine")
    mode_boss = normaliser_boss(boss)
    mode_tablos = normaliser_tablos(tablos)
    mode_quetes = normaliser_quetes(quetes)
    mode_amis = normaliser_amis(amis)
    mode_criminels = normaliser_criminels(yo_criminels)
    mode_boutiques = normaliser_boutiques(boutiques)
    prix_max = int(boutiques_prix_max)
    mode_distributeurs = DI.normaliser(distributeurs)        # V3, lot C1
    # Rangs de montre (V1.1) : objet progressif, indépendant de `objets_cles_melanges` (ce n'est pas un don d'évènement)
    rangs = VERROU_RANGS in actifs
    exemplaires = VERROUS_A_ACTIVER[VERROU_RANGS]["exemplaires"] if rangs else 0
    reel = rangs and bool(rangs_reel)           # mode « rang réel » : rang de la montre = exemplaires reçus
    # ap/rang-s-objet : rang S = 5e exemplaire, seulement avec un objectif d'après-jeu (sinon rien d'après-jeu n'entre
    # dans la graine : un 5e exemplaire n'ouvrirait rien) ; `rang_s_objet` faux = graine d'avant (tracker)
    rang_s_obj = reel and bool(rang_s_objet) and a_objectif_aj
    if rang_s_obj:
        exemplaires += 1
    chapitre_rangs = (CHAPITRE_RANGS_REEL if reel else CHAPITRE_RANGS) if rangs else {}
    # rang D donné par l'histoire (c03 n° 33, après l'Herbe et le Tournevis) : sauf en mode « rang réel »
    objets_rang_d = () if reel else OBJETS_RANG_D
    # Vélo (V1.1) : objet sans emplacement d'évènement, indépendant de `objets_cles_melanges` (comme les rangs)
    velo = VERROU_VELO in actifs

    def rangs_exiges(rang_reel=None, verrou=None) -> int:
        return exemplaires_pour(rang_reel, verrou, reel) if rangs else 0

    # exemplaires du rang S : 5 avec le rang S par l'objet ; sinon (graine d'avant) le rang A de la requête 28
    rang_s_val = EXEMPLAIRES_RANG_S if rang_s_obj and REGLES_RANG_S else rangs_exiges("A")

    objets_emplacements = {e["objet"] for e in d.emplacements}
    objets_cles = [o["cle"] for o in d.objets if o["famille"] == "objet_cle"]
    # toujours mélangés (coffres), sauf un objet dont le seul coffre n'est une location qu'avec le verrou « rangs »
    dans_coffres = [k for k in objets_cles if k not in objets_emplacements
                    and (k not in OBJETS_COFFRES_DE_RANG or rangs)]

    # Objets d'emplacement mélangés
    melanges = set()
    if melanges_opt:
        for k in objets_emplacements:
            if k in NON_MELANGES_V1:
                continue
            if k in VERROUS_POSSESSION or k in actifs:
                melanges.add(k)
        # V3 : objets à verrou étendu, mélangés seulement si leur verrou est actif (objets_cles_v11 §20)
        melanges.update(k for k in EMPLACEMENTS_V3 if k in actifs)
    # V3, lot 11 : le Train n'a pas d'emplacement d'origine : toujours au pool (et exigé) quand son verrou est actif,
    # indépendamment de `objets_cles_melanges` (comme le Vélo et les rangs)
    if OBJET_TRAIN in actifs:
        melanges.add(OBJET_TRAIN)

    # Objets que la logique peut exiger : verrou garanti (possession), ou verrou actif ET objet mélangé.
    # Un objet laissé à son emplacement d'origine est donné par l'histoire au moment où elle en a besoin :
    # l'exiger n'apporterait rien et créerait des boucles (Clés de l'école données au chapitre 3 mais
    # « critiques » pour le chapitre 2 dans l'ancien mod).
    exigibles = set(VERROUS_POSSESSION) | {k for k in melanges if k in actifs}

    # V3, lot 3 : objets d'accès de l'après-jeu (testés par possession par le jeu, apres_jeu.py). Dans la partie : ceux
    # de l'objectif (dès le mode « aucun »), tous ceux des régions ouvertes en mode « complet ». Un objet à emplacement
    # d'origine (don de script substitué) est mélangé avec `objets_cles_melanges`, sinon placé d'office à son
    # emplacement ; les autres (contenu d'un coffre devenu location, objet sans don dans le jeu) vont toujours au pool.
    # Lot 6 : Pass sortilège (objectif Extrabuki dès « aucun », sinon « complet ») et 4 clés de la Voie du mystère
    # (« complet ») : objets à verrou ÉTENDU du jeu (AJ.VERROUS_JEU, k = 43..47), sans objet du jeu ; leur verrou est
    # dans la graine si, et seulement si, l'objet y est (`verrous_aj`).
    objets_aj: List[str] = []
    if a_objectif_aj:
        objets_aj += [k for k in AJ.objets_objectif(mode_objectif, sigma_aj)
                      if AJ.VERROUS_DISPONIBLES.get(k, True)]
        if mode_aj == "complet":
            disponibles = [k for k in AJ.OBJETS_A_EMPLACEMENT + AJ.OBJETS_SANS_EMPLACEMENT + tuple(AJ.OBJETS_COFFRES)
                           if AJ.VERROUS_DISPONIBLES.get("voie_du_mystere" if k in AJ.CLES_VOIE else k, True)
                           and (k != "pass_entrain_exp" or AJ.VERROUS_DISPONIBLES["pass_sortilege"])]
            objets_aj += [k for k in disponibles if k not in objets_aj]
    emplacements_aj = [k for k in objets_aj if k in AJ.EMPLACEMENTS and AJ.region_ouverte(AJ.EMPLACEMENTS[k]["region"])
                       and AJ.VERROUS_DISPONIBLES.get(AJ.EMPLACEMENTS[k].get("verrou"), True)]
    melanges_aj = {k for k in emplacements_aj if melanges_opt}
    pool_aj = sorted(k for k in objets_aj if k not in emplacements_aj or k in melanges_aj)
    verrous_aj = tuple(k for k in AJ.VERROUS_JEU if k in objets_aj)
    melanges |= melanges_aj
    exigibles |= set(objets_aj)

    def filtre(objets) -> Tuple[str, ...]:
        return tuple(sorted(k for k in objets if k in exigibles))

    prologue = d.objet_prologue if d.objet_prologue in exigibles else None
    # 2026-11-05 : objets qui n'arrêtent rien (Modèle zéro), retirés de toute règle reprise des données ou des tables
    sans_exigence = set(OBJETS_SANS_EXIGENCE) if RETRAIT_MODELE_ZERO else set()

    def filtre_r(objets) -> Tuple[str, ...]:
        return tuple(k for k in filtre(objets) if k not in sans_exigence)


    def avec_montre(r: Regle) -> Regle:
        """Règle d'une location « Boss » : la Yo-kai Watch en plus quand elle est exigible (règle prudente, V3)."""
        if OBJET_MONTRE not in exigibles or OBJET_MONTRE in r.objets:
            return r
        return Regle(r.chapitres, tuple(sorted(set(r.objets) | {OBJET_MONTRE})), r.rangs)

    # -- régions et connexions ----------------------------------------------------------------------------
    regions_ok = {r["cle"] for r in regions_v1(rangs)}
    regions = [(r["cle"], r["nom_" + langue]) for r in regions_v1(rangs)]
    connexions = []
    for c in d.connexions:
        if c["source"] in regions_ok and c["cible"] in regions_ok:
            objets = tuple(c["regle"]["objets"]) + CONNEXIONS_OBJETS_SUPPLEMENTAIRES.get((c["source"], c["cible"]), ())
            ch_c = c["regle"]["chapitres_termines"]
            if OBJET_TRAIN in exigibles:
                ch_c = max(ch_c, CONNEXIONS_CHAPITRES_TRAIN.get((c["source"], c["cible"]), 0))
            connexions.append((c["source"], c["cible"],
                               Regle(ch_c, filtre_r(objets),
                                     rangs_exiges(verrou=REGIONS_VERROU_DE_MONTRE.get(c["cible"])))))

    locations: List[LocationPlan] = []

    # -- règles des chapitres (évènements créés plus bas, à leur place) -----------------------------------------
    critiques: Dict[int, Set[str]] = {}
    for ch in d.chapitres:
        critiques.setdefault(ch["numero"], set()).update(ch["objets_critiques"])
    for n, retires in CRITIQUES_RETIRES.items():
        critiques.get(n, set()).difference_update(retires)
    for k, n in {**CHAPITRE_BLOQUE_PAR, **({} if RETRAIT_MODELE_ZERO else CHAPITRE_BLOQUE_PAR_AVANT)}.items():
        critiques.setdefault(n, set()).add(k)
    regle_chapitre: Dict[int, Regle] = {}
    for ch in d.chapitres:
        n = ch["numero"]
        if n <= DERNIER_CHAPITRE:
            regle_chapitre[n] = Regle(ch["chapitres_termines"], filtre(critiques.get(n, ())), chapitre_rangs.get(n, 0))

    # -- V3, lots M2b : zones des Yo-kai demandés (zones.py) : règle d'accès d'une zone = celle de « Chapitre n
    # terminé » de son chapitre (`ZONES[r]["chapitre"]`, règle de base) et les connexions d'un chemin depuis l'origine
    # (objets du train, du voyage dans le temps…) ; une location qui demande un de ces Yo-kai l'exige en plus
    regle_zone: Dict[str, Regle] = {}
    acces_z: Dict[str, Regle] = {}
    if zones_y:
        acces_z = {REGION_ORIGINE: Regle(0, (), 0)}
        change = True
        while change:
            change = False
            for s_c, c_c, r_c in connexions:
                if s_c in acces_z and c_c not in acces_z:
                    acces_z[c_c] = _union_regles(acces_z[s_c], r_c)
                    change = True
        for r_z in sorted(set(zones_y.values())):
            if r_z not in acces_z:
                raise ValueError(f"zone {r_z} hors des régions de la graine")
            regle_zone[r_z] = _union_regles(regle_chapitre[ZN.ZONES[r_z]["chapitre"]], acces_z[r_z])

    def avec_zones(r: Regle, medailles) -> Regle:
        """Règle `r` et l'accès à la zone de chacun de ces Yo-kai demandés (ceux qui ont une zone dans la graine)."""
        zs = sorted({zones_y[m] for m in medailles if m in zones_y}) if REGLES_ZONES else []
        return _union_regles(r, *[regle_zone[z] for z in zs]) if zs else r

    def especes_chantier(n: int) -> Tuple[int, ...]:
        """Audit softlock (G1-8, graine générée depuis : `chantier`) : Yo-kai demandés par le Tablo-blabla n° 9 quand la
        requête n (ou l'une de ses préalables) exige le flag 584 du chantier, lu vrai dès son appel (fonction 52)."""
        if not chantier or not ZN.quetes_closes((n,)) & QUETES_CHANTIER:
            return ()
        return ZN.especes_de_tablo(TABLO_CHANTIER)
    # l'histoire attend des requêtes clés qui demandent un Yo-kai à zone : « Chapitre N terminé » l'exige aussi
    if zones_y:
        for n, (_phase, reqs) in ZN.ATTENTES.items():
            regle_chapitre[n] = avec_zones(regle_chapitre[n], {m for q in reqs for m in ZN.especes_de_quete(q)})

    def regle_ecole_nuit() -> Regle:
        """École de nuit (COFFRES_ECOLE_NUIT) : 2 chapitres terminés + Clés, Herbe, Tournevis (filtrés) et, avec le
        mélange par zones, l'accès à la zone des Yo-kai des requêtes clés attendues entre la fin du chapitre 2 et 3-190
        (requête 4 en 3-95) : connexions jusqu'à la zone et chapitres terminés de sa phase d'ouverture (zone ouverte
        avant 3-190 ; sinon, prudence, la règle complète de la zone)."""
        r = Regle(ECOLE_NUIT_CHAPITRES, filtre(ECOLE_NUIT_OBJETS))
        if not zones_y or not REGLES_ZONES:
            return r
        medailles = {m for n, (p, reqs) in ZN.ATTENTES.items() if n > ECOLE_NUIT_CHAPITRES and p < PHASE_ECOLE_NUIT
                     for q in reqs for m in ZN.especes_de_quete(q)}
        for z in sorted({zones_y[m] for m in medailles if m in zones_y}):
            if ZN.ZONES[z]["phase"] <= PHASE_ECOLE_NUIT:
                r = _union_regles(r, acces_z[z], Regle(ZN.ZONES[z]["phase"] // 10000 - 1))
            else:
                r = _union_regles(r, regle_zone[z])
        return r

    # -- coffres dorés --------------------------------------------------------------------------------------
    # Coffres derrière un verrou de montre (Manoir : verrou D) : rang réel D (OBJETS_RANG_D, avec ou sans le verrou
    # « rangs » ; sans objet en mode « rang réel ») et, avec le verrou « rangs », les exemplaires du verrou.
    for c in coffres_v1():
        montre = COFFRES_VERROU_DE_MONTRE.get(c["index_tbox"])
        ch = max(c["regle"]["chapitres_termines"], COFFRES_CHAPITRES_MIN.get(c["index_tbox"], 0))
        locations.append(LocationPlan(
            nom=c["nom_" + langue], id_ap=c["id_ap"], region=c["region"],
            regle=avec_zones(Regle(ch,
                        filtre(tuple(c["regle"]["objets"]) + COFFRES_OBJETS_SUPPLEMENTAIRES.get(c["index_tbox"], ())
                               + (objets_rang_d if montre else ())
                               + (("canne_a_peche",) if c["index_tbox"] in COFFRES_APRES_ARRET_CANNE else ())
                               + ((OBJET_PILE,) if ch == 1 and c["index_tbox"] not in COFFRES_AVANT_TUTORIEL_PILE
                                  else ())),
                        max(rangs_exiges(verrou=montre),
                            rangs_exiges(*COFFRES_RANGS_CHEMIN.get(c["index_tbox"], (None, None))),
                            rangs_exiges(COFFRES_APRES_ARRET_RANG.get(c["index_tbox"])) if reel else 0)),
                             especes_chantier(COFFRES_QUETE_CHANTIER.get(c["index_tbox"], 0)))
            if not (REGLE_ECOLE_NUIT and c["index_tbox"] in COFFRES_ECOLE_NUIT) else regle_ecole_nuit(),
            genre="coffre", index_tbox=c["index_tbox"],
            exclue=c["index_tbox"] in COFFRES_APRES_VICTOIRE and not a_objectif_aj))

    # -- coffres derrière un verrou de montre ou un rang réel (V1.1, verrou « rangs » actif) ------------------------
    # Chapitres : ceux de l'ancien mod (mesurés avec un rang réel ramené au rang AP, comme le mode « rang réel ») ;
    # ancien mode : au moins le seuil du rang réel ; exemplaires : verrou de montre du coffre et/ou rang exigé
    # (exemplaires_pour).
    # V3, lot 9 : avec la valeur « cle_magnetique_bleue », le coffre 179 (rang A, verrou de montre A) en fait partie
    # et sa clé va au pool ; sans le verrou « rangs », rien (le coffre n'est pas une location et garde sa clé)
    cle_bleue = rangs and "cle_magnetique_bleue" in actifs
    if rangs:
        for c in coffres_rangs() + ([coffre_cle_bleue()] if cle_bleue else []):
            rang_reel = EXCLUSIONS_RANG[c["exclusion"]]
            locations.append(LocationPlan(
                nom=c["nom_" + langue], id_ap=c["id_ap"], region=c["region"],
                regle=Regle(max(c["regle"]["chapitres_termines"], 0 if reel else SEUIL_RANG_REEL[rang_reel]),
                            filtre(tuple(c["regle"]["objets"])
                                   + COFFRES_OBJETS_SUPPLEMENTAIRES.get(c["index_tbox"], ())),
                            rangs_exiges(rang_reel, COFFRES_VERROU_DE_MONTRE.get(c["index_tbox"]))),
                genre="coffre", index_tbox=c["index_tbox"],
                exclue=bool(tour_commerce) and c["index_tbox"] in TOUR_COMMERCE_COFFRES))

    # -- emplacements d'objets-clés -------------------------------------------------------------------------
    for e in d.emplacements:
        k = e["objet"]
        info = EMPLACEMENTS[k]
        est_melange = k in melanges
        locations.append(LocationPlan(
            nom=e["nom_" + langue], id_ap=e["id_ap"], region=REGION_ORIGINE,
            regle=avec_zones(Regle(info["chapitres"], filtre(info.get("apres", ())),
                                   rangs_exiges(info.get("rang_reel"), info.get("verrou_montre"))),
                             ZN.especes_de_quete(info.get("quete") or ZN.DONS_DE_REQUETE.get(k, 0))),
            genre="emplacement", prologue=(k != d.objet_prologue),
            exclue=est_melange and not e["progression_permise"],
            verrou=None if est_melange else k, cle=k, index_tbox=info.get("bit"),
            flag=info.get("flag"), quete=info.get("quete")))
    # V3 : emplacements des objets à verrou étendu, seulement si le verrou est actif (sinon ni location ni objet)
    # (ceux du lot 9, dont la règle reprend celle d'un chapitre ou d'une requête : plus bas, après `regle_quete`)
    for k, info in EMPLACEMENTS_V3.items():
        if k not in actifs or k in VERROUS_V3_OBJETS:
            continue
        est_melange = k in melanges
        locations.append(LocationPlan(
            nom=info["nom_" + langue], id_ap=info["id_ap"], region=REGION_ORIGINE,
            regle=avec_zones(Regle(info["chapitres"], filtre(info.get("apres", ()))),
                             ZN.especes_de_quete(info["quete"]) if info.get("quete") else ()),
            genre="emplacement", exclue=est_melange and not info["progression_permise"],
            verrou=None if est_melange else k, cle=k, flag=info.get("flag"), quete=info.get("quete"),
            phase_min=info.get("phase_min"), hachages=tuple(info.get("hachages", ()))))

    # -- chapitres (évènements) -----------------------------------------------------------------------------
    # (règles calculées plus haut : `regle_chapitre`)
    for ch in d.chapitres:
        n = ch["numero"]
        if n > DERNIER_CHAPITRE:
            continue    # « chapitre 11 » = après la victoire
        if ch["region"] not in regions_ok:
            raise ValueError(f"chapitre {n} dans une région exclue")
        nom = nom_evenement_chapitre(n, langue)
        locations.append(LocationPlan(
            nom=nom, id_ap=None, region=ch["region"], regle=regle_chapitre[n],
            genre="chapitre", evenement=nom, cle=str(n)))

    # -- objectif -------------------------------------------------------------------------------------------
    obj = d.objectif
    regle_objectif = Regle(obj["regle"]["chapitres_termines"], filtre(obj["regle"]["objets"]),
                           max(chapitre_rangs.values(), default=0))
    if not a_objectif_aj:
        locations.append(LocationPlan(
            nom=obj["nom_" + langue], id_ap=None, region=obj["region"], regle=regle_objectif,
            genre="objectif", evenement=obj["nom_" + langue], cle=obj["cle"]))
    # (objectif d'après-jeu : son évènement est créé avec les régions d'après-jeu, plus bas)

    # -- requêtes : règle du chapitre N + objets du chemin (définie ici : les régions d'après-jeu s'en servent) ------
    def regle_quete(q: dict) -> Regle:
        r = regle_chapitre[q["chapitre"]]
        return avec_zones(Regle(r.chapitres, tuple(sorted(set(r.objets) | set(filtre(q["objets"])))),
                                max(r.rangs, rangs_exiges(q["rang_reel"], q["verrou_montre"]))),
                          ZN.especes_de_quete(q["n"]) + especes_chantier(q["n"]))

    # -- V3, lot 9 : emplacements des objets-clés livrés par les lots 5 et 7, seulement si leur verrou est actif -------
    # (règles : voir EMPLACEMENTS_V3 ; jamais l'objet lui-même ; exclus quand l'objet est mélangé, comme les autres)
    for k, info in EMPLACEMENTS_V3.items():
        if k not in actifs or k not in VERROUS_V3_OBJETS:
            continue
        region = REGION_ORIGINE
        if "regle_quete" in info:
            q = QUETES_PAR_NUMERO[info["regle_quete"]]
            r, region = regle_quete(q), q["region"]
            regle = Regle(r.chapitres, tuple(sorted(set(r.objets) - {k} - set(info.get("sans", ())))), r.rangs)
        elif "regle_chapitre" in info:
            r = regle_chapitre[info["regle_chapitre"]]
            regle = Regle(r.chapitres, tuple(sorted(set(r.objets) - {k})), r.rangs)
        else:
            regle = Regle(info["chapitres"], filtre(info.get("apres", ())))
        if region not in regions_ok:
            raise ValueError(f"emplacement de {k} dans une région exclue")
        est_melange = k in melanges
        locations.append(LocationPlan(
            nom=info["nom_" + langue], id_ap=info["id_ap"], region=region, regle=regle,
            genre="emplacement", exclue=est_melange and not info["progression_permise"],
            verrou=None if est_melange else k, cle=k, flag=info.get("flag"), quete=info.get("quete"),
            phase_min=info.get("phase_min")))

    # -- V3, lot 3 : régions d'après-jeu OUVERTES (apres_jeu.py) : seulement avec un objectif d'après-jeu -------------
    # La ville d'après la fin (« apres_jeu ») s'atteint par la règle de l'objectif de la V2 (10 chapitres terminés).
    # Lot 6 : une région dont un objet d'accès n'est pas dans la graine n'est pas créée (verrou inactif : le jeu garde
    # son comportement d'origine, aucune location n'y existe) ; `requetes` : requêtes d'avant la fin exigées finies.
    if a_objectif_aj:
        for k, info in AJ.REGIONS.items():
            if not AJ.region_ouverte(k) or info["source"] not in regions_ok \
                    or any(o not in exigibles for o in info.get("objets", ())):
                continue
            regions.append((k, d.regions_par_cle[k]["nom_" + langue]))
            regions_ok.add(k)
            if info.get("objectif_v2"):
                r = regle_objectif
            else:
                # Entrain Express : par les gares (Centre-ville), sans attendre la fin ; les autres : après la fin
                objets, r_max = set(filtre(tuple(info.get("objets", ()))
                                           + REGIONS_AJ_OBJETS_SUPPLEMENTAIRES.get(k, ()))), \
                    (rang_s_val if info.get("rang") else 0) if rang_s_obj else rangs_exiges(info.get("rang"))
                for n in info.get("requetes", ()):
                    rq = regle_quete(QUETES_PAR_NUMERO[n])
                    objets |= set(rq.objets)
                    r_max = max(r_max, rq.rangs)
                r = Regle(0, tuple(sorted(objets)), r_max)
            connexions.append((info["source"], k, r))

    # -- boss d'histoire (règle du chapitre du boss ; Lady Démona : objectif, exclue) ----------------------------
    if mode_boss != "aucun":
        for b in BOSS_HISTOIRE:
            if b["region"] not in regions_ok:
                raise ValueError(f"boss {b['cle']} dans une région exclue")
            victoire = bool(b.get("victoire")) and not a_objectif_aj   # objectif d'après-jeu : un boss comme un autre
            locations.append(LocationPlan(
                nom=b["nom_" + langue], id_ap=b["id_ap"], region=b["region"],
                regle=avec_montre(regle_objectif if b.get("victoire") else regle_chapitre[b["chapitre"]]),
                genre="boss", exclue=victoire, cle=b["cle"], flag=b["flag"]))

    # -- boss de quête (règle du chapitre + objets du chemin de la quête ; Tromplœil : exclu) --------------------
    if mode_boss in ("histoire_et_quetes", "tous"):
        for b in BOSS_QUETES:
            if b["region"] not in regions_ok:
                raise ValueError(f"boss {b['cle']} dans une région exclue")
            r = regle_chapitre[b["chapitre"]]
            regle = avec_zones(Regle(r.chapitres, tuple(sorted(set(r.objets) | set(filtre(b.get("objets", ()))))),
                                     max(r.rangs, rangs_exiges(b.get("rang_reel"), b.get("verrou_montre")))),
                               ZN.especes_de_quete(b["quete"]) + especes_chantier(b["quete"]))
            locations.append(LocationPlan(
                nom=b["nom_" + langue], id_ap=b["id_ap"], region=b["region"], regle=avec_montre(regle),
                genre="boss", exclue=bool(b.get("exclue")), portail=BOSS_PORTAILS.get(b["cle"]), cle=b["cle"],
                quete=b["quete"]))

    # -- boss du mélange ajoutés (mode « tous » : règle du chapitre du combat ; Taprice : exclu, marqué « tunnel ») --
    if mode_boss == "tous":
        for b in BOSS_MELANGE:
            if b["region"] not in regions_ok:
                raise ValueError(f"boss {b['cle']} dans une région exclue")
            locations.append(LocationPlan(
                nom=b["nom_" + langue], id_ap=b["id_ap"], region=b["region"],
                regle=avec_montre(regle_chapitre[b["chapitre"]]),
                genre="boss", exclue=bool(b.get("exclue")), portail=BOSS_PORTAILS.get(b["cle"]), cle=b["cle"],
                flag=b.get("flag"), quete=b.get("quete"), octet=b.get("octet"), seuil=b.get("seuil")))

    # -- Vélo (V1.1) : fin de la requête qs0009 (règle du chapitre 7, comme un boss de quête) ------------------------
    if velo:
        if QUETE_VELO["region"] not in regions_ok:
            raise ValueError("location du Vélo dans une région exclue")
        locations.append(LocationPlan(
            nom=QUETE_VELO["nom_" + langue], id_ap=QUETE_VELO["id_ap"], region=QUETE_VELO["region"],
            regle=regle_chapitre[QUETE_VELO["chapitre"]], genre="quete", cle=QUETE_VELO["cle"],
            quete=QUETE_VELO["quete"]))

    # -- Tablo-blabla : flag « Yo-kai appelé » ; exclus sauf le n° 3 (imposé par la phase 10-45) -----------------------
    # (V3, 2026-10-27, TABLOS_YOKAI : règle = apparition du panneau ET Yo-kai obtenable ; accès d'une région = celui des
    # connexions, comme les zones)
    acces_t = {REGION_ORIGINE: Regle(0, (), 0)}
    for _ in range(len(connexions)):
        for s_c, c_c, r_c in connexions:
            if s_c in acces_t and c_c not in acces_t:
                acces_t[c_c] = _union_regles(acces_t[s_c], r_c)

    def regle_tablo(x: dict) -> Tuple[Regle, Set[int]]:
        """(règle sans les zones, n° du Médaillium des Yo-kai demandés) d'un Tablo-blabla (et des panneaux `apres`)."""
        y = TABLOS_YOKAI.get(x["n"]) if REGLES_TABLOS_YOKAI else None
        r = regle_chapitre[TABLOS_APPARITION.get(x["n"], x["chapitre"]) if y else x["chapitre"]]
        regle = Regle(r.chapitres, tuple(sorted(set(r.objets) | set(filtre_r(x.get("objets", ()))))),
                      max(r.rangs, rangs_exiges(verrou=x.get("verrou_montre"))))
        medailles = set(ZN.especes_de_tablo(x["n"]))
        if not y or y.get("histoire"):          # (n° 3 : Yo-kai donné par l'histoire bien avant l'appel imposé)
            return regle, medailles
        parts = [regle, Regle(0, filtre(y.get("objets", ())), rangs_exiges(y.get("rang"), y.get("verrou_montre")))]
        if y.get("apres_jeu"):
            parts.append(Regle(DERNIER_CHAPITRE, (), rang_s_val))       # rang S (graine d'avant : requête 28, rang A)
        else:
            parts.append(regle_chapitre[y["chapitre"]])
        if y.get("region"):
            parts.append(acces_t[y["region"]])
        if y.get("quete") is not None:
            parts.append(regle_quete(QUETES_PAR_NUMERO.get(y["quete"]) or AJ.QUETES_TRANSFERT_PAR_NUMERO[y["quete"]]))
        for n in y.get("apres", ()):
            r_n, m_n = regle_tablo(TABLOS_PAR_N[n])
            parts.append(r_n)
            medailles |= m_n
        return _union_regles(*parts), medailles

    def tablo_cree(x: dict) -> bool:
        """Graine générée depuis le 2026-10-27 : panneau dont le Yo-kai a une voie dans la graine (TABLOS_YOKAI)."""
        if not tablos_apparition:
            return True
        if x["n"] in TABLOS_SANS_TRANSFERT:
            return bool(transfert)
        return x["n"] not in TABLOS_APRES_JEU and x["n"] not in TABLOS_EVENEMENT     # (n° 25 : plus bas)

    if mode_tablos == "tous":
        for x in TABLOS_CREES:
            if x["region"] not in regions_ok:
                raise ValueError(f"Tablo-blabla n° {x['n']} dans une région exclue")
            if not tablo_cree(x):
                continue
            regle = avec_zones(*regle_tablo(x))
            locations.append(LocationPlan(
                nom=x["nom_" + langue], id_ap=x["id_ap"], region=x["region"], regle=regle, genre="tablo",
                exclue=not x.get("progression"), portail=TABLOS_PORTAILS.get(x["n"]), cle=str(x["n"]),
                flag=x["flag"]))

    # -- requêtes et services : quête terminée (phase 255) ; règle du chapitre N + objets du chemin (regle_quete) ---
    if mode_quetes != "aucune":
        for q in QUETES:
            if q["service"] and mode_quetes != "requetes_et_services":
                continue
            if mode_quetes == OJ.MODE_REQUETES_CLES and q["n"] not in OJ.REQUETES_CLES:
                continue
            if q["region"] not in regions_ok:
                raise ValueError(f"quête n° {q['n']} dans une région exclue")
            locations.append(LocationPlan(
                nom=q["nom_" + langue], id_ap=q["id_ap"], region=q["region"], regle=regle_quete(q), genre="requete",
                exclue=q["exclue"], portail=QUETES_PORTAILS.get(q["n"]), cle=str(q["n"]), quete=q["n"],
                service=q["service"]))
        # V3, lot 6 : requêtes à transfert d'AVANT la fin (option `requetes_transfert`, fonction 37 du patch) : même
        # forme ; seule la 108 peut recevoir de la progression (apres_jeu.QUETES_TRANSFERT)
        if transfert and mode_quetes != OJ.MODE_REQUETES_CLES:
            for q in AJ.QUETES_TRANSFERT:
                locations.append(LocationPlan(
                    nom=q["nom_" + langue], id_ap=q["id_ap"], region=q["region"], regle=regle_quete(q),
                    genre="requete", exclue=q["exclue"], cle=str(q["n"]), quete=q["n"],
                    apres_jeu=AJ.MARQUE_TRANSFERT))

    # -- checks « Chapitre N terminé » (1 à 9) : quête de chapitre 170 + N terminée ; règle de l'évènement ---------------
    regions_chapitres = {ch["numero"]: ch["region"] for ch in d.chapitres}
    if chapitres:
        for c in CHAPITRES_CHECKS:
            locations.append(LocationPlan(
                nom=c["nom_" + langue], id_ap=c["id_ap"], region=regions_chapitres[c["n"]],
                regle=regle_chapitre[c["n"]], genre="histoire", cle=str(c["n"]), quete=c["quete"]))
        # « Montée de rang : D » : flag « évènement vu » de ev03_2300 (lu comme un boss d'histoire)
        r = RANG_D_CHECK
        if r["region"] not in regions_ok:
            raise ValueError("Montée de rang : D dans une région exclue")
        locations.append(LocationPlan(
            nom=r["nom_" + langue], id_ap=r["id_ap"], region=r["region"], regle=regle_chapitre[r["chapitre"]],
            genre="rang", cle=r["cle"], flag=r["flag"]))

    # -- coffres du donjon des portails : exclus (coût en globes non modélisable), règle de la requête 6 --------------
    q6 = QUETES_PAR_NUMERO[QUETE_PORTAILS]
    r6 = regle_chapitre[q6["chapitre"]]
    for c in coffres_portails():
        if c["region"] not in regions_ok:
            raise ValueError(f"coffre {c['index_tbox']} dans une région exclue")
        locations.append(LocationPlan(
            nom=c["nom_" + langue], id_ap=c["id_ap"], region=c["region"],
            regle=r6,
            genre="coffre", exclue=True, portail=PORTAIL_DONJON, index_tbox=c["index_tbox"]))

    # -- amis : bit « ami » du Médaillium (amis_criminels.py) ------------------------------------------------------
    # - espèce sauvage, évolution, fusion : exclus (lieux selon le mélange calculé chez le joueur, amitié aléatoire) ;
    # - fusion avec objet (FUSIONS_OBJET, archipelago_amis_criminels.md §10) : exclue, règle du chapitre (au moins un
    #   après la base, et celui de la source de l'objet), dans la région de la source de l'objet ;
    # - les 16 des armées (origine « armee », §11) : exclus, seulement si `armees` (mélange des Yo-kai par rencontre) ;
    # - ami d'histoire (don automatique d'un déclencheur de phase) : NON exclu, règle et région de l'évènement
    #   « Chapitre N terminé » du chapitre du don ;
    # - ami de requête (don du script de la requête) : règle, région et exclusion de la requête ;
    # - ami d'évènement : plus bas (après le pool : seulement si son objet y est).
    if mode_amis == "tous":
        for a in AMIS:
            if a["origine"] in ("evenement", "place") or "base_invite" in a:   # plus bas (selon le pool et `invites`)
                continue
            if a["origine"] == "armee" and not armees:      # seulement si le mélange de la graine les place (§11)
                continue
            if a["origine"] == "armee" and invites and invites_armees:
                continue                                    # à l'Auberge : location de genre « invite », plus bas
            region, exclue = region_ami(a) or REGION_ORIGINE, True
            if a["origine"] == "histoire":
                r, exclue = regle_chapitre[a["chapitre"]], False
            elif a["origine"] == "requete":
                q = QUETES_PAR_NUMERO[a["quete"]]
                r, exclue = regle_quete(q), q["exclue"]
            else:
                r = regle_chapitre[a["chapitre"]]
                if reel and a["chapitre"] >= AMI_CHAPITRE_RANG_D:
                    r = Regle(r.chapitres, r.objets, max(r.rangs, EXEMPLAIRES_RANG["D"]))
                if a.get("quete") is not None:      # fusion avec objet donné par le script d'une requête (Tendino)
                    rq = regle_quete(QUETES_PAR_NUMERO[a["quete"]])
                    r = Regle(max(r.chapitres, rq.chapitres), tuple(sorted(set(r.objets) | set(rq.objets))),
                              max(r.rangs, rq.rangs))
                r = avec_zones(r, (a["medaille"],))     # V3, M2b : Yo-kai demandé placé dans sa zone
            if region not in regions_ok:
                raise ValueError(f"ami n° {a['medaille']} dans une région exclue")
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=region, regle=r,
                genre="ami", exclue=exclue, portail=a.get("portail") if exclue else None, cle=str(a["medaille"]),
                medaille=a["medaille"]))

    # -- invités de l'Auberge des voyageurs (amis_criminels.py INVITES, archipelago_invites.md §14) : genre « invite »,
    # hors de l'option `amis`. Déclencheur « requetes » = toutes les locations de genre « requete » de la graine
    # cochées ; sans requêtes : ni invité ni location. EXCLUS ; règle = conjonction des règles de ces requêtes
    # (chapitres et rangs : maximum ; objets : union), dans la région de l'Auberge (son accès s'ajoute par la
    # connexion).
    # (V3, lot 6 : les requêtes à transfert de sauvegarde n'en font pas partie : Pandanoko garde le déclencheur de la V2)
    requetes = [loc for loc in locations if loc.genre == "requete" and loc.quete not in AJ.QUETES_TRANSFERT_PAR_NUMERO]
    for a in INVITES:
        if a["declencheur"] != "requetes" or not requetes:
            continue
        if a["region"] not in regions_ok:
            raise ValueError(f"invité n° {a['medaille']} dans une région exclue")
        r0 = regle_chapitre[a["chapitre"]]
        r = Regle(max([r0.chapitres] + [x.regle.chapitres for x in requetes]),
                  tuple(sorted(set(r0.objets).union(*(x.regle.objets for x in requetes)))),
                  max([r0.rangs] + [x.regle.rangs for x in requetes]))
        locations.append(LocationPlan(
            nom=a["nom_" + langue], id_ap=a["id_ap"], region=a["region"], regle=r,
            genre="invite", exclue=True, cle=str(a["medaille"]), medaille=a["medaille"],
            # toutes les requêtes, donc aussi celles des portails mystères (la plus longue : le donjon, requête 8)
            portail=PORTAIL_REQUETES if any(x.portail for x in requetes) else None))

    # -- Yo-criminels : octet `wantedNN` (étapes gagnées) ; LIBRES avec le patch (fonction 24, limites.cpp) : le jeu
    # propose toujours le premier non arrêté de ORDRE_CRIMINELS (par chapitre puis numéro) : NON exclus ; règle du
    # chapitre du criminel, au moins CRIMINELS_CHAPITRE_MIN (les 5 cartes du tirage de l'emplacement) ; tous ceux qui
    # le précèdent dans l'ordre ont une règle inférieure ou égale (archipelago_amis_criminels.md §6.4) --------------
    if mode_criminels == "tous":
        for c in CRIMINELS:
            if c["region"] not in regions_ok:
                raise ValueError(f"Yo-criminel n° {c['n']} dans une région exclue")
            locations.append(LocationPlan(
                nom=c["nom_" + langue], id_ap=c["id_ap"], region=c["region"],
                regle=regle_chapitre[max(c["chapitre"], CRIMINELS_CHAPITRE_MIN)],
                genre="criminel", exclue=False, cle=str(c["n"]), etapes=c["etapes"]))

    # -- boutiques : premier achat d'un article (bit persistant, jeu v9) ; règle de la région de la carte + chapitre de
    # l'article (au moins un chapitre terminé ; 6-10, quête 62, portes de carte : boutiques.py) ; exclues : hors du
    # périmètre principal (mode « toutes ») ou plus chères que `boutiques_prix_max` (attente d'argent)
    # V3, lot 22 : boutique N045 (village du Château de Sawayama) avec `apres_jeu` = complet, la région ouverte et des
    # boutiques : règle d'une location d'après-jeu de la région (10 chapitres terminés ; accès par la connexion) ;
    # exclue hors du chemin de l'objectif, comme les coffres de la région
    n045 = bool(lot22) and a_objectif_aj and mode_aj == "complet" \
           and all(BOUTIQUES_PAR_CODE[c]["region"] in regions_ok for c in BOUTIQUES_APRES_JEU)
    # V3, lot 22-bis : articles FIXES de N047 (Entrain Express) dans tous les modes, dans la région du train d'or (règle
    # et exclusion de la boucle ci-dessous, comme en mode « toutes » : jamais de progression, accès tiré au sort)
    n047 = bool(lot22bis) and a_objectif_aj and mode_aj == "complet" and "entrain_express" in regions_ok
    for a in articles_du_mode(mode_boutiques, boutiques_retirees, apres_jeu=n045, entrain=n047):
        b = a["boutique"]
        region = BOUTIQUES_PAR_CODE[b]["region"]
        if region not in regions_ok:
            raise ValueError(f"boutique {b} dans une région exclue")
        if b in BOUTIQUES_APRES_JEU:
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=region, regle=Regle(DERNIER_CHAPITRE, (), 0),
                genre="boutique",
                exclue=not AJ.sur_le_chemin(mode_objectif, region=region, sigma=sigma_aj) or boutique_exclue(a, prix_max),
                cle="%s/%d" % (b, a["n"]), boutique=b, entrees=a["entrees"],
                nb_entrees=BOUTIQUES_PAR_CODE[b]["nb_entrees"], bit=a["bit"], apres_jeu=region))
            continue
        r = regle_chapitre[chapitre_article(a)]
        if filtre(BOUTIQUES_OBJETS.get(b, ())):         # V3, lot 11 : wagons-boutiques des trains
            r = Regle(r.chapitres, tuple(sorted(set(r.objets) | set(filtre(BOUTIQUES_OBJETS[b])))), r.rangs)
        if reel and b in BOUTIQUES_RANG:
            r = Regle(r.chapitres, r.objets, max(r.rangs, EXEMPLAIRES_RANG[BOUTIQUES_RANG[b]]))
        if rang_s_obj and a["tag"] == "x_rang_s":
            # ap/rang-s-objet : article vendu au rang S (SHOP_VALID_CONDITION GetWatchRank >= S) : 5e exemplaire (location
            # exclue ; la fin de l'histoire n'est pas ajoutée : I7 / I8 de l'audit réservent « 10 chapitres » à l'après-jeu)
            r = Regle(r.chapitres, r.objets, max(r.rangs, rang_s_val))
        if REGLES_BOUTIQUES_TABLOS and a["tag"] in TABLOS_ARTICLES:
            # article vendu seulement après l'appel d'un Tablo-blabla : règle du panneau (Yo-kai obtenable, zones) en plus
            r = _union_regles(r, avec_zones(*regle_tablo(TABLOS_PAR_N[TABLOS_ARTICLES[a["tag"]]])))
        marque = None
        if b == AJ.BOUTIQUE_ENTRAIN and mode_aj == "complet" and "entrain_express" in regions_ok:
            # V3, lot 3 : la boutique de l'Entrain Express (déjà exclue en V2 : « x_train ») est dans sa région, derrière
            # le Pass Entrain Exp. (le train reste tiré au sort : 10 % par entrée en gare)
            region, marque = "entrain_express", "entrain_express"
        locations.append(LocationPlan(
            nom=a["nom_" + langue], id_ap=a["id_ap"], region=region, regle=r,
            genre="boutique", exclue=boutique_exclue(a, prix_max),
            portail=PORTAIL_SALLE if a["tag"] == TAG_BOUTIQUE_PORTAILS else None, cle="%s/%d" % (b, a["n"]), boutique=b,
            entrees=a["entrees"], nb_entrees=BOUTIQUES_PAR_CODE[b]["nb_entrees"], bit=a["bit"], apres_jeu=marque))

    # -- V3, lot C1 : distributeurs de soda (distributeurs.py) : premier achat de chaque boisson de chaque machine,
    # sans bit de sauvegarde (état tenu par le serveur) ; règle de la région de la carte + « Chapitre 2 terminé » au
    # moins (comme les boutiques) ; machines EXCLUES (remplissage) : `DI.EXCLUES` (machine qui peut disparaître pour
    # toujours, carte dont l'accès n'est pas prouvé). `cle` = « carte/rang/boisson », `nb_entrees` = nombre de points
    # du fichier de la carte (contrôle de la ROM du joueur).
    for x in DI.locations_du_mode(mode_distributeurs):
        if x["region"] not in regions_ok:
            raise ValueError(f"distributeur {x['cle']} dans une région exclue")
        locations.append(LocationPlan(
            nom=x["nom_" + langue], id_ap=x["id_ap"], region=x["region"], regle=regle_chapitre[DI.CHAPITRE_MIN],
            genre="distributeur", exclue=DI.exclue(x), cle=x["cle"], nb_entrees=x["nb_points"]))

    # -- V3, lot 3 : locations d'après-jeu (apres_jeu.py) ----------------------------------------------------------
    # Toutes portent « 10 chapitres terminés » dans leur règle (jamais dans la liste « à faire avant le chapitre 10 »).
    # `cree(sur_chemin)` : None = la location n'existe pas dans ce mode ; True = EXCLUE (hors du chemin de l'objectif,
    # mode « complet ») ; False = progression possible (sur le chemin de l'objectif).
    if a_objectif_aj:
        ob = AJ.objectif_effectif(mode_objectif, sigma_aj)   # lot 10 : région, chemin, objets de la PLACE du boss
        # rang S : 5e exemplaire (ap/rang-s-objet) ; graine d'avant : requête 28 faite, qui exige le rang A
        rang_s = rang_s_val

        def cree(sur_chemin: bool) -> Optional[bool]:
            if mode_aj == "complet":
                return not sur_chemin
            return False if mode_aj == "necessaire" and sur_chemin else None

        def regle_quete_aj(q: dict) -> Regle:
            # (rang A ou S : rang S de la logique ; aucun rang : requête 121, proposée sans condition avec le Pass)
            # (rang S par l'objet : une requête de rang A, la 28 comprise, garde le rang A)
            objets, r_max = set(filtre(q["objets"])), (
                rang_s if q["rang_reel"] == "S" or not rang_s_obj else rangs_exiges("A")) if q["rang_reel"] else 0
            for n in q["requetes"]:                 # requêtes d'AVANT la fin exigées finies : leur règle s'ajoute
                rq = regle_quete(QUETES_PAR_NUMERO[n])
                objets |= set(rq.objets)
                r_max = max(r_max, rq.rangs)
            # (V3, lots M2b : services d'après-jeu qui demandent un Yo-kai à zone : 169, 170)
            return avec_zones(Regle(DERNIER_CHAPITRE, tuple(sorted(objets)), r_max), ZN.especes_de_quete(q["n"]))

        # évènement de victoire : dans la région de la PLACE qui contient le boss (lot 10 : celle où le mélange de la
        # graine l'a mis), avec la règle de cette place : requête de la place (rang, requêtes d'avant la fin, objets)
        # et objets d'accès (place d'Extrabuki : train, donc Pass sortilège + fin de l'histoire par la région, et rang
        # S pour les requêtes 122 et 123)
        region_obj = ob["region"]
        if region_obj not in regions_ok:
            raise ValueError(f"objectif {mode_objectif} dans une région fermée")
        # (lot 18, objectif « medaillium_complet » : pas de place de boss ; évènement créé à la fin, avec les voies)
        place_obj = AJ.PLACES_BOSS[ob["place"]] if not est_md else {}
        r_place = regle_quete_aj(AJ.QUETES_PAR_NUMERO[place_obj["quete"]]) if "quete" in place_obj \
            else Regle(DERNIER_CHAPITRE, (), 0)
        if not est_md:
            locations.append(LocationPlan(
                nom=ob["nom_" + langue], id_ap=None, region=region_obj,
                regle=Regle(DERNIER_CHAPITRE, tuple(sorted(set(r_place.objets) | set(filtre(ob["objets"])))),
                            r_place.rangs),
                genre="objectif", evenement=ob["nom_" + langue], cle=mode_objectif, apres_jeu=region_obj))
        # emplacements d'origine des objets d'accès (dès le mode « aucun » : le don doit être substitué)
        for k in emplacements_aj:
            e = AJ.EMPLACEMENTS[k]
            est_melange = k in melanges_aj
            locations.append(LocationPlan(
                nom=e["nom_" + langue], id_ap=e["id_ap"], region=e["region"],
                regle=Regle(DERNIER_CHAPITRE, (), rang_s if e["region"] == "rang_s" else 0),
                genre="emplacement", exclue=est_melange, verrou=None if est_melange else k, cle=k,
                flag=e.get("flag"), quete=e.get("quete"), phase_min=e.get("phase_min"),
                hachages=tuple(e.get("hachages", ())), apres_jeu=e["region"]))
        # coffres dorés
        for c in coffres_apres_jeu():
            if c["region"] not in regions_ok:
                continue
            x = cree(AJ.sur_le_chemin(mode_objectif, region=c["region"], sigma=sigma_aj))
            if x is None:
                continue
            locations.append(LocationPlan(
                nom=c["nom_" + langue], id_ap=c["id_ap"], region=c["region"],
                regle=Regle(DERNIER_CHAPITRE, filtre(c["regle"]["objets"]),
                            rang_s if c["region"] == "rang_s" or c["index_tbox"] in AJ.COFFRES_STATIONS_RANG_S else 0),
                genre="coffre", exclue=x or (bool(tour_commerce) and c["index_tbox"] in TOUR_COMMERCE_COFFRES),
                index_tbox=c["index_tbox"], apres_jeu=c["region"]))
        # requêtes et services (aucune n'est une requête clé de l'histoire)
        if mode_quetes not in ("aucune", OJ.MODE_REQUETES_CLES):
            for q in AJ.QUETES:
                if not AJ.quete_ouverte(q, transfert) or q["region"] not in regions_ok:
                    continue
                if q["service"] and mode_quetes != "requetes_et_services":
                    continue
                x = cree(AJ.sur_le_chemin(mode_objectif, quete=q["n"], sigma=sigma_aj))
                if x is None:
                    continue
                locations.append(LocationPlan(
                    nom=q["nom_" + langue], id_ap=q["id_ap"], region=q["region"], regle=regle_quete_aj(q),
                    genre="requete", exclue=x or q["service"] or q["hasard"]
                    or (bool(tour_commerce) and q["n"] in TOUR_COMMERCE_QUETES), cle=str(q["n"]), quete=q["n"],
                    service=q["service"], apres_jeu=q["region"]))
        # boss à marqueur persistant de PLACE (le check suit la place, comme en V2) ; la place qui CONTIENT le boss de
        # l'objectif (lot 10 : après mélange) : exclue (elle coïncide avec la victoire) ; la place d'origine du boss de
        # l'objectif, si elle a reçu un autre boss, est une place comme une autre
        for b in AJ.BOSS:
            if b["region"] not in regions_ok or mode_boss == "aucun" or (b["mode"] == "quetes" and mode_boss == "histoire"):
                continue
            est_objectif = b["place"] == ob.get("place")
            x = cree(est_objectif or AJ.sur_le_chemin(mode_objectif, boss=b["place"], sigma=sigma_aj))
            if x is None:
                continue
            r = regle_quete_aj(AJ.QUETES_PAR_NUMERO[b["quete"]]) if b.get("quete") is not None \
                else Regle(DERNIER_CHAPITRE, filtre(b.get("objets", ())), 0)
            locations.append(LocationPlan(
                nom=b["nom_" + langue], id_ap=b["id_ap"], region=b["region"], regle=avec_montre(r), genre="boss",
                exclue=x or est_objectif, cle=b["cle"], flag=b.get("flag"), quete=b.get("quete"), octet=b.get("octet"),
                seuil=b.get("seuil"), apres_jeu=b["region"]))
        # lot 10 : places SANS marqueur persistant (dix des Limbes, McKraken) : check = bit du Médaillium de
        # l'OCCUPANT (le boss que le mélange de la graine y met), posé à la victoire seulement. Exclues : hors du
        # chemin, place du boss de l'objectif, occupant dont le bit n'est pas prouvé (Infiniris), McKraken (Tablo n° 24).
        # ap/boss-voie-mystere : + les 4 places de la Voie du mystère (graines générées depuis : `boss_voie`), quand
        # leur région est dans la graine (sa clé au pool : `apres_jeu` = complet)
        for b in AJ.BOSS_MEDAILLE if boss_especes else ():
            if b["region"] not in regions_ok or mode_boss == "aucun" or (b["voie"] and not boss_voie):
                continue
            est_objectif = b["place"] == ob.get("place")
            x = cree(False) if b["fige"] else \
                cree(est_objectif or AJ.sur_le_chemin(mode_objectif, boss=b["place"], sigma=sigma_aj))
            if x is None:
                continue
            occ = AJ.occupant(b["place"], sigma_aj)
            locations.append(LocationPlan(
                nom=b["nom_" + langue], id_ap=b["id_ap"], region=b["region"],
                regle=avec_montre(Regle(DERNIER_CHAPITRE, filtre(b["objets"]), 0)), genre="boss",
                exclue=x or est_objectif or b["fige"] or occ in AJ.BOSS_BIT_NON_PROUVE, cle=b["cle"],
                medaille=AJ.MEDAILLE_BOSS[occ], apres_jeu=b["region"]))
        if mode_aj == "complet":
            # Tablo-blabla n° 24 (Yo-kai World) : exclu comme les autres panneaux
            if mode_tablos == "tous" and AJ.TABLO_24_REGION in regions_ok:
                for x in TABLOS:
                    if x.get("apres_jeu"):
                        locations.append(LocationPlan(
                            nom=x["nom_" + langue], id_ap=x["id_ap"], region=AJ.TABLO_24_REGION,
                            # (lots M2b : réponse à zone, Nuiroir)
                            regle=avec_zones(Regle(DERNIER_CHAPITRE, (), 0), ZN.especes_de_tablo(x["n"])),
                            genre="tablo", exclue=True, cle=str(x["n"]),
                            flag=x["flag"], apres_jeu=AJ.TABLO_24_REGION))
            # Tablo-blabla n° 23 (graine générée depuis le 2026-10-27) : son Yo-kai (légendaire) exige le rang S
            if mode_tablos == "tous" and tablos_apparition and TABLO_23_REGION in regions_ok:
                for x in TABLOS_CREES:
                    if x["n"] in TABLOS_APRES_JEU:
                        locations.append(LocationPlan(
                            nom=x["nom_" + langue], id_ap=x["id_ap"], region=TABLO_23_REGION,
                            regle=avec_zones(*regle_tablo(x)), genre="tablo", exclue=True, cle=str(x["n"]),
                            flag=x["flag"], apres_jeu=TABLO_23_REGION))
            # amis d'après-jeu : tous exclus (amitié au hasard, sceau à briser dans le menu)
            if mode_amis == "tous":
                amis_aj_par_n = {x["medaille"]: x for x in AJ.AMIS}
                for a0 in AJ.AMIS:
                    # V3, lot L1 : « Ami : L » d'un légendaire : règle, région et existence de l'entrée du sceau qui
                    # donne L dans cette graine (nom, identifiant et n° restent ceux de L)
                    a = a0 if a0["origine"] != "legendaire" else \
                        {**amis_aj_par_n[sceau_de_leg[a0["medaille"]]],
                         **{k: a0[k] for k in ("medaille", "id_ap", "nom_fr", "nom_en", "yokai_fr", "yokai_en")}}
                    if a["region"] not in regions_ok \
                            or (a["verrou"] is not None and not AJ.VERROUS_DISPONIBLES[a["verrou"]]) \
                            or (a["verrou"] == "transfert" and not transfert):
                        continue
                    r = regle_quete_aj(AJ.QUETES_PAR_NUMERO[a["quete"]]) if a["quete"] is not None \
                        else Regle(DERNIER_CHAPITRE, (), rang_s if a["region"] == "rang_s" else 0)
                    r = Regle(r.chapitres, tuple(sorted(set(r.objets) | set(filtre(a["objets"])))), r.rangs)
                    locations.append(LocationPlan(
                        nom=a["nom_" + langue], id_ap=a["id_ap"], region=a["region"], regle=r, genre="ami",
                        exclue=True, cle=str(a["medaille"]), medaille=a["medaille"], apres_jeu=a["region"]))

    # -- V3, lot 18 : amis des machines de la Voie du mystère (objectif « medaillium_complet ») : une pièce par boss de
    # ligne vaincu (fonction 41 : boss à chaque parcours), tirage dirigé vers le Yo-kai manquant (fonction 42).
    # EXCLUS (après-jeu) ; règle : la fin de l'histoire, la ligne du boss (sa région), la montre (boss à vaincre)
    # ap/boss-voie-mystere : la pièce d'une machine est le butin de l'ESPÈCE du boss de la ligne (100 %) : avec le
    # mélange de version 3 (Voie entre eux avec cet objectif), elle se gagne là où ce boss a été mis : clés de sa ligne
    if est_md:
        for a in MD.AMIS_VOIE:
            if a["region"] not in regions_ok:
                raise ValueError(f"ami n° {a['medaille']} dans une région fermée")
            place_piece = AJ.place_du_boss(MD.BOSS_DE_LIGNE[a["region"]], sigma_aj)
            objets_piece = filtre(AJ.PLACES_BOSS[place_piece]["objets"]) \
                if place_piece != MD.BOSS_DE_LIGNE[a["region"]] else ()
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=a["region"],
                regle=avec_montre(Regle(DERNIER_CHAPITRE, objets_piece, 0)), genre="ami", exclue=True,
                cle=str(a["medaille"]), medaille=a["medaille"], apres_jeu=a["region"]))

    # -- V3, lot 6 : amis des requêtes à transfert d'avant la fin (Triptyk, Carpitaine : 7,5 % par revanche gagnée) :
    # EXCLUS, règle de leur requête ; avec les options `requetes_transfert` et `amis` = tous
    if transfert and mode_amis == "tous":
        for a in AJ.AMIS_TRANSFERT:
            q = AJ.QUETES_TRANSFERT_PAR_NUMERO[a["quete"]]
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=q["region"], regle=regle_quete(q), genre="ami",
                exclue=True, cle=str(a["medaille"]), medaille=a["medaille"], apres_jeu=AJ.MARQUE_TRANSFERT))

    # -- ap/portails-donjon : clés du donjon des portails (donjon_portails.py) : règles des locations du donjon (clés de
    # leurs portes en plus), coffres 444 à 452 non exclus, plus de marque « portail » ; les cinq clés au pool
    if donjon_portails:
        # (invité à déclencheur « requetes » : sa règle est l'union de celles des requêtes de la graine, donc aussi les
        # clés de la requête 8 quand elle en est)
        cles_q8 = next((DP.QUETES[8] for x in locations if x.genre == "requete" and x.cle == "8"), ())
        invites_requetes = {str(x["medaille"]) for x in INVITES if x["declencheur"] == "requetes"}
        for i, loc in enumerate(locations):
            d_p = DP.cles_location(loc.genre, loc.index_tbox, loc.cle)
            if d_p is None and loc.genre == "invite" and loc.cle in invites_requetes and cles_q8:
                d_p = (cles_q8, True)
            if d_p is None:
                continue
            cles_p, exclue_p = d_p
            r = loc.regle
            locations[i] = LocationPlan(**{**loc.__dict__, "regle": Regle(
                r.chapitres, tuple(sorted(set(r.objets) | set(cles_p))), r.rangs, r.nombres),
                "exclue": loc.exclue if exclue_p else False,
                "portail": loc.portail if loc.genre == "invite" else None})
        exigibles |= set(DP.CLES)

    # -- objets ---------------------------------------------------------------------------------------------
    pool = sorted(dans_coffres) + sorted(melanges) + [OBJET_RANG] * exemplaires + ([VERROU_VELO] if velo else [])
    pool += [k for k in pool_aj if k not in melanges_aj]        # V3, lot 3 : objets d'après-jeu sans emplacement mélangé
    # V3, lot 9 : objets sans emplacement d'évènement (contenu d'un coffre) dont la valeur est active ; Parchemins
    pool += [k for k in OBJETS_V3_SANS_EMPLACEMENT if k in actifs and (k != "cle_magnetique_bleue" or cle_bleue)]
    pool += list(PARCHEMINS) if parchemins else []
    pool += list(MD.OBJETS) if est_md else []       # V3, lot 18 : Grelot gris, 9 objets de fusion tirés au sort
    # Mirapo de poche : l'objet « Miroirs » devient l'objet PROGRESSIF « Miroirs progressifs » (2 exemplaires) : à
    # l'emplacement des Miroirs (placé d'office sans `objets_cles_melanges`, sinon au pool) et au pool pour le reste
    if VERROU_MIRAPO in actifs:
        if OBJET_MIROIRS not in actifs:
            raise ValueError("Mirapo de poche sans le verrou des Miroirs")
        au_pool = pool.count(OBJET_MIROIRS)
        pool = [k for k in pool if k != OBJET_MIROIRS]
        places_mp = 0
        for loc in locations:
            if loc.verrou == OBJET_MIROIRS:
                loc.verrou = OBJET_MIROIRS_PROGRESSIFS
                places_mp += 1
        if au_pool + places_mp != 1:
            raise ValueError("Mirapo de poche : objet Miroirs introuvable")
        pool += [OBJET_MIROIRS_PROGRESSIFS] * (VERROUS_A_ACTIVER[VERROU_MIRAPO]["exemplaires"] - places_mp)
    pool += list(DP.CLES) if donjon_portails else []   # ap/portails-donjon : une clé par porte à globes
    cites = set()
    for _, _, r in connexions:
        cites.update(r.objets)
    for loc in locations:
        cites.update(loc.regle.objets)
    if prologue:
        cites.add(prologue)

    classification = {}
    for o in d.objets:
        k = o["cle"]
        if o["famille"] in (FAMILLE_PIEGE, AJ.FAMILLE_TERRAINS, MX.FAMILLE):
            # (ap/multiplicateur-xp : « Multiplicateur d'XP », hors du plan comme les pièges : `__init__.create_items`)
            # pièges (V3, lot 3 des pièges) : jamais dans le plan (ni pool, ni règle) ; leur classe vient d'objets.json
            # (`__init__.create_item`) : le plan d'une graine reste celui d'avant, à pièges ou non
            # (ap/blasters-terrains-apworld : terrains de Ψ Blasters : classés plus bas, seulement avec l'option)
            continue
        if o["famille"] in ("objet_cle", FAMILLE_CLE_V3, AJ.FAMILLE):
            classification[k] = "progression" if k in cites else "utile"
        else:
            classification[k] = o["classification"]

    # V3, lot 9 : un objet-clé du lot cité SEULEMENT par des règles de locations exclues (Serviette douce : requête 80,
    # Crocho, Pandanoko) est « progression sans équilibrage » (il n'ouvre rien qui puisse porter de la progression)
    cites_utiles = set()
    for _, _, r in connexions:
        cites_utiles.update(r.objets)
    for loc in locations:
        if not loc.exclue:
            cites_utiles.update(loc.regle.objets)
    for k in VERROUS_V3_OBJETS | (frozenset(DP.CLES) if donjon_portails else frozenset()):
        if k in cites and k not in cites_utiles:
            classification[k] = CLASSE_PROGRESSION_SANS_EQUILIBRAGE

    nb_verrouilles = sum(1 for loc in locations if loc.verrou)
    nb_locations = sum(1 for loc in locations if loc.id_ap is not None)
    # Objets des Yo-kai d'évènement (option `objets_evenement`, archipelago_amis_criminels.md §7.4) : un exemplaire de
    # chacun, à la place du remplissage (dans la limite des places libres). « Utiles » (jamais de progression) tant
    # qu'aucune règle ne les cite ; seule la règle du check « Ami » de LEUR Yo-kai peut en citer un (ci-dessous).
    evenement = [o["cle"] for o in d.objets if o["famille"] == "evenement"
                 and (places or o["cle"] not in PLACES_PAR_OBJET)] if objets_evenement else []
    evenement = evenement[:max(0, nb_locations - nb_verrouilles - len(pool))]
    if cites & set(evenement):
        raise ValueError("objet d'évènement exigé par une règle")
    pool += evenement

    # -- amis d'évènement (archipelago_amis_criminels.md §8.3) : EXCLUS (amitié au hasard) ; créés seulement si l'objet
    # du Yo-kai est dans le pool ; règle = l'objet + la règle de « Chapitre N terminé », dans la région de la carte du
    # combat. Pour qu'Archipelago puisse évaluer cette règle, l'objet cité devient « progression sans équilibrage »
    # (un objet « utile » n'entre jamais dans l'état d'Archipelago : la location serait inatteignable et la
    # génération refusée) ; une location exclue ne reçoit jamais de progression : l'objet d'un Yo-kai n'est donc jamais
    # placé sur un check « Ami » d'évènement (ni le sien, ni un autre). Chaque location ajoute une place de remplissage.
    if mode_amis == "tous":
        for a in AMIS:
            if a["origine"] != "evenement" or a["objet"] not in evenement:
                continue
            if a["region"] not in regions_ok:
                raise ValueError(f"ami n° {a['medaille']} dans une région exclue")
            r = regle_chapitre[a["chapitre"]]
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=a["region"],
                regle=Regle(r.chapitres, tuple(sorted(set(r.objets) | {a["objet"]})), r.rangs),
                genre="ami", exclue=True, cle=str(a["medaille"]), medaille=a["medaille"],
                medailles=tuple(a.get("medailles", ()))))
            classification[a["objet"]] = CLASSE_PROGRESSION_SANS_EQUILIBRAGE
            cites.add(a["objet"])
            nb_locations += 1
    # -- Tablo-blabla n° 25 (graine générée depuis le 2026-10-27, TABLOS_EVENEMENT) : son Yo-kai n'est obtenable qu'avec
    # son objet d'évènement : créé seulement avec le check « Ami » d'évènement de ce Yo-kai (ci-dessus : option `amis` =
    # tous, objet au pool, déjà « progression sans équilibrage »), l'objet dans sa règle
    if mode_tablos == "tous" and tablos_apparition and mode_amis == "tous":
        for x in TABLOS_CREES:
            objets_ev = TABLOS_YOKAI[x["n"]].get("objets", ())
            if x["n"] not in TABLOS_EVENEMENT or not set(objets_ev) <= set(evenement):
                continue
            r, ms = regle_tablo(x)
            locations.append(LocationPlan(
                nom=x["nom_" + langue], id_ap=x["id_ap"], region=x["region"],
                regle=avec_zones(Regle(r.chapitres, tuple(sorted(set(r.objets) | set(objets_ev))), r.rangs), ms),
                genre="tablo", exclue=True, portail=TABLOS_PORTAILS.get(x["n"]), cle=str(x["n"]), flag=x["flag"]))
            nb_locations += 1
    # -- invités de l'Auberge à INVITATION (option `invites`, archipelago_invites.md §15) : un objet « Invitation :
    # <nom> » et une location « Ami : <nom> » par invité (+30 objets, +30 locations : pool équilibré). Location EXCLUE
    # (amitié au taux du jeu) ; règle = l'invitation + la règle de « Chapitre N terminé » dans la région de l'Auberge
    # (son accès s'ajoute par la connexion). Même raison que les objets d'évènement : l'objet cité par une règle doit
    # être de progression pour qu'Archipelago l'évalue ; « sans équilibrage » puisqu'il n'ouvre qu'une location exclue.
    # V3, lot 14 : avec `invites_armees` (interne), les 16 des armées (même location que leur check du mélange par
    # rencontre, qui n'est alors pas créé plus haut).
    # V3, lot 20 : avec `pieces_speciales`, 28 de ces 30 invités QUITTENT l'Auberge (PS.QUITTENT_AUBERGE : ni
    # invitation ni location de genre « invite » ; leur location « Ami » est créée plus bas, avec ses pièces).
    invitations = []
    invitations_armees = []
    if invites:
        for a in INVITES_TOUS:
            if a["declencheur"] != "objet":
                continue
            groupe = a.get("groupe")
            if groupe == "armees" and not invites_armees:
                continue
            if ps and a["medaille"] in PS.QUITTENT_AUBERGE:
                continue
            if a["region"] not in regions_ok:
                raise ValueError(f"invité n° {a['medaille']} dans une région exclue")
            r = regle_chapitre[a["chapitre"]]
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=a["region"],
                regle=Regle(r.chapitres, tuple(sorted(set(r.objets) | {a["objet"]})), r.rangs),
                genre="invite", exclue=True, cle=str(a["medaille"]), medaille=a["medaille"]))
            classification[a["objet"]] = CLASSE_PROGRESSION_SANS_EQUILIBRAGE
            cites.add(a["objet"])
            (invitations_armees if groupe == "armees" else invitations).append(a["objet"])
            nb_locations += 1
        # Yo-kai d'évènement à leur emplacement d'origine (amis_criminels.py, origine « place » ;
        # archipelago_evenement_invitation.md §9) : même schéma (objet « Invitation : <nom> », location « Ami : <nom> »
        # EXCLUE, règle = l'invitation + « Chapitre N terminé » dans la région de la carte du PNJ), mais location de
        # genre « ami » (liste `amis` de slot_data : le Yo-kai n'est pas un invité de l'Auberge).
        for a in AMIS:
            if a["origine"] != "place" or not places:
                continue
            if a["region"] not in regions_ok:
                raise ValueError(f"ami n° {a['medaille']} dans une région exclue")
            r = regle_chapitre[a["chapitre"]]
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=a["region"],
                regle=Regle(r.chapitres, tuple(sorted(set(r.objets) | {a["objet"]})), r.rangs),
                genre="ami", exclue=True, cle=str(a["medaille"]), medaille=a["medaille"]))
            classification[a["objet"]] = CLASSE_PROGRESSION_SANS_EQUILIBRAGE
            cites.add(a["objet"])
            invitations.append(a["objet"])
            nb_locations += 1
        pool += invitations + invitations_armees
        # Évolutions par niveau des invités de l'Auberge (amis_criminels.EVOLUTIONS_INVITES, archipelago_amis_criminels.md
        # §9) : check « Ami » EXCLU de l'espèce évoluée, avec l'option `amis` = tous ; règle = l'invitation de la BASE +
        # « Chapitre N terminé » (un chapitre après la base), dans la région de l'Auberge ; aucun objet de plus (une
        # place de remplissage chacun).
        if mode_amis == "tous":
            for a in AMIS:
                base = INVITES_PAR_MEDAILLE.get(a.get("base_invite"))
                if base is None or base["objet"] not in invitations:
                    continue
                r = regle_chapitre[a["chapitre"]]
                locations.append(LocationPlan(
                    nom=a["nom_" + langue], id_ap=a["id_ap"], region=a["region"],
                    regle=Regle(r.chapitres, tuple(sorted(set(r.objets) | {base["objet"]})), r.rangs),
                    genre="ami", exclue=True, cle=str(a["medaille"]), medaille=a["medaille"]))
                nb_locations += 1
    # -- V3, lot 20 : pièces spéciales du Crank-a-kai (pieces.py ; option `pieces_speciales`, indépendante de
    # `invites` et de `amis`). Une location « Ami » de genre « ami » (liste `amis` de slot_data : bit du Médaillium)
    # par Yo-kai visé : les 16 de Pièce 5 étoiles (nouvelles) et les 28 qui ont quitté l'Auberge (mêmes identifiants
    # qu'en V2). Région : la machine du Crank-a-kai du présent (mont Sylvestre) ; règle : celle de « Chapitre 2
    # terminé » (tutoriel fait, flag 44 posé) + les EXEMPLAIRES de leur pièce (`Regle.nombres`). NON exclues (la
    # pièce donne le Yo-kai à coup sûr : tirage dirigé et pièce rendue du jeu), sauf les 9 fusions régionales (base +
    # objet de fusion, un chapitre de plus). Évolutions par niveau des six (avec `amis` = tous) : règle de la base,
    # un chapitre de plus, exclues. Objets : au pool, de progression.
    voies_ps: Dict[int, Tuple[str, str, str]] = {}
    if ps:
        if PS.REGION_MACHINE not in regions_ok:
            raise ValueError("pièces spéciales : région de la machine du Crank-a-kai fermée")
        fiches = dict(AMIS_5_ETOILES_PAR_MEDAILLE)
        fiches.update({n: INVITES_PAR_MEDAILLE[n] for n in PS.QUITTENT_AUBERGE})
        fiches[PS.BANANAR] = AMI_BANANAR            # (lot 21 ; sans `l21`, `exigences_ps` n'a pas ce n°)

        def regle_ps(n: int, chapitre_plus: int = 0) -> Regle:
            nombres, chapitre, _exclue = exigences_ps[n]
            r = regle_chapitre[chapitre + chapitre_plus]
            return Regle(r.chapitres, r.objets, r.rangs, nombres if REGLES_PIECES else ())

        # Lot 21 : fusion d'un Yo-kai régional avec son objet : chez M. Zen (`t103i31`, Coteau fleuri), qui ne la
        # propose qu'une fois la requête 4 finie (flag 64 [C]) : région du Coteau fleuri, règle de la requête 4 (et
        # de « Chapitre 3 terminé », dont elle est une requête clé), plus l'accès à la machine du mont Sylvestre (la
        # base sort de la machine) : conjonction des connexions d'un chemin depuis l'origine.
        if l21:
            if PS.REGION_FUSION not in regions_ok:
                raise ValueError("pièces spéciales : région de la fusion fermée")
            acces_av = {REGION_ORIGINE: Regle(0, (), 0)}
            change = True
            while change:
                change = False
                for s_c, c_c, r_c in connexions:
                    if s_c in acces_av and c_c not in acces_av:
                        acces_av[c_c] = _union_regles(acces_av[s_c], r_c)
                        change = True
            r_fusion = _union_regles(regle_quete(QUETES_PAR_NUMERO[PS.REQUETE_FUSION]), acces_av[PS.REGION_MACHINE])

        for n in sorted(exigences_ps):
            a = fiches[n]
            exclue = exigences_ps[n][2]
            region_ps, r_ps = PS.REGION_MACHINE, regle_ps(n)
            if l21 and n in PS.MEDAILLES_FUSIONS:
                region_ps, r_ps = PS.REGION_FUSION, _union_regles(r_ps, r_fusion)
            locations.append(LocationPlan(
                nom=a["nom_" + langue], id_ap=a["id_ap"], region=region_ps, regle=r_ps, genre="ami",
                exclue=exclue, cle=str(n), medaille=n))
            nb_locations += 1
            if n in PS.MEDAILLES_FUSIONS:
                voies_ps[n] = ("fusion_objet", MD.GARANTIE, PS.NOTE_FUSION_LOT21) if l21 \
                    else ("fusion_objet", MD.HASARD, PS.NOTE_FUSION)
            elif n == PS.BANANAR:
                voies_ps[n] = ("piece", MD.GARANTIE, PS.NOTE_BLEU)
            else:
                voies_ps[n] = ("piece", MD.GARANTIE, PS.NOTE_PIECE)
        if mode_amis == "tous":
            for a in AMIS:
                base = a.get("base_invite")
                if base not in exigences_ps:
                    continue
                locations.append(LocationPlan(
                    nom=a["nom_" + langue], id_ap=a["id_ap"], region=PS.REGION_MACHINE, regle=regle_ps(base, 1),
                    genre="ami", exclue=True, cle=str(a["medaille"]), medaille=a["medaille"]))
                nb_locations += 1
        # la Pile ou passe de l'histoire est toujours dans la partie (au pool si elle est mélangée, sinon placée
        # d'office à son emplacement) : deux de plus
        pool += PS.pool(True, l21)
        for loc in locations:
            for k, _n in loc.regle.nombres:
                cites.add(k)
        for k in PS.exemplaires(l21):
            utile = any(k == x for loc in locations if not loc.exclue for x, _n in loc.regle.nombres)
            if k in cites:
                classification[k] = "progression" if utile else CLASSE_PROGRESSION_SANS_EQUILIBRAGE
            elif not str(classification.get(k)).startswith("progression"):
                classification[k] = "progression"       # (REGLES_PIECES fermé : objets du pool sans règle)
    # -- V3, lot 3 : terrains de Ψ Blasters (apres_jeu.py) : bit « terrain fini » du mot P + 0x64C. « court » :
    # progression possible ; « long » : exclu et marqué ; terrains d'après-jeu : avec `apres_jeu` = complet, exclus ;
    # Jiganyan / Komak : seulement si l'invitation de Jibanyan S / Komasan S est dans le pool (elle seule permet la
    # rencontre qui débloque le terrain). Aucun objet de plus : une place de remplissage chacun.
    # Lot 22 : avec `blasters` = tous, les photos du terrain 3 sont tenues pour prises par le jeu (option étendue 33,
    # `Plan.photos`) : terrains de Triptyk (3) et de Domniscian (13) ; « Ami : Domniscian » avec `amis` = tous.
    blasters_l22 = bool(lot22) and mode_blasters == "tous"
    # ap/blasters-terrains-apworld (`terrains_bl`) : un objet par terrain 2..13 ; les 13 terrains (quel que soit le mode)
    # sont des checks NORMAUX à la règle « Chapitre 3 terminé » + l'objet (le verrou REMPLACE la condition du jeu :
    # orbes, photos, créatures, requête 96, Limbes, terrains finis, rencontre de Jibanyan S / Komasan S, après-jeu) ;
    # « Ami » des terrains 11 à 13 (`amis` = tous) : même règle, non exclus.
    if terrains_bl:
        for b in AJ.BLASTERS:
            n = b["terrain"]
            objets_t = (AJ.OBJET_TERRAIN[n],) if n in AJ.OBJET_TERRAIN else ()
            regle_t = Regle(AJ.BLASTERS_CHAPITRE - 1, objets_t, 0)
            locations.append(LocationPlan(
                nom=b["nom_" + langue], id_ap=b["id_ap"], region=AJ.BLASTERS_REGION, regle=regle_t, genre="blasters",
                exclue=False, cle=str(n), terrain=n))
            nb_locations += 1
            a = AJ.AMIS_PAR_TERRAIN.get(n)
            if a is not None and mode_amis == "tous":
                locations.append(LocationPlan(
                    nom=a["nom_" + langue], id_ap=a["id_ap"], region=AJ.BLASTERS_REGION, regle=regle_t, genre="ami",
                    exclue=False, cle=str(a["medaille"]), medaille=a["medaille"]))
                nb_locations += 1
        pool += [AJ.OBJET_TERRAIN[n] for n in AJ.TERRAINS_A_OBJET]
        for n in AJ.TERRAINS_A_OBJET:
            cites.add(AJ.OBJET_TERRAIN[n])
            classification[AJ.OBJET_TERRAIN[n]] = "progression"
    if mode_blasters != "aucun" and not terrains_bl:
        for b in AJ.BLASTERS:
            classe = b["classe"]
            if classe != "court" and mode_blasters != "tous":
                continue
            if b.get("lot22") and not blasters_l22:
                continue
            # (`ch_terrain` : ne pas réutiliser le nom du paramètre `chapitres`, lu plus bas pour `Plan.chapitres`)
            ch_terrain, region, marque = AJ.BLASTERS_CHAPITRE - 1, AJ.BLASTERS_REGION, None
            objets = set(filtre(b.get("objets", ())))
            if classe == "apres_jeu":
                if mode_aj != "complet" or b["region"] not in regions_ok \
                        or any(r not in regions_ok for r in b.get("regions_aussi", ())):
                    continue
                ch_terrain, region, marque = DERNIER_CHAPITRE, b["region"], b["region"]
                # (lot 22, Domniscian : les autres régions de ses terrains 1 à 10, au-delà de celle de son check :
                # objets d'accès de leur chaîne ; Limbes éternelles = Clé de cabane, déjà exigée par le Château)
                for r in b.get("regions_aussi", ()):
                    while r in AJ.REGIONS:
                        objets |= set(filtre(AJ.REGIONS[r].get("objets", ())))
                        r = AJ.REGIONS[r]["source"]
            elif classe != "court":
                marque = AJ.MARQUE_BLASTERS_LONG
            if "invitation" in b:
                if b["invitation"] not in invitations:
                    continue
                # région et chapitre du check « Ami » du Yo-kai à rencontrer (son PNJ à son emplacement d'origine)
                pnj = next(a for a in AMIS if a.get("objet") == b["invitation"])
                rp = regle_chapitre[pnj["chapitre"]]
                ch_terrain, region = max(ch_terrain, rp.chapitres), pnj["region"]
                objets |= set(rp.objets) | {b["invitation"]}
            locations.append(LocationPlan(
                nom=b["nom_" + langue], id_ap=b["id_ap"], region=region,
                regle=Regle(ch_terrain, tuple(sorted(objets)), 0), genre="blasters", exclue=classe != "court",
                cle=str(b["terrain"]), terrain=b["terrain"], apres_jeu=marque))
            nb_locations += 1
            ami_terrain = AJ.AMIS_PAR_TERRAIN.get(b["terrain"])
            if ami_terrain is not None and mode_amis == "tous" \
                    and (ami_terrain is AJ.AMI_DOMNISCIAN or bool(lot22bis)):
                # lot 22 : la première victoire sur le terrain 13 pose le bit « ami » du n° 443 (FUN_0040AD40) : même
                # règle, même région, exclu ; lot 22-bis : idem pour les terrains 11 et 12 (n° 441 Jiganyan, 442 Komak)
                a = ami_terrain
                locations.append(LocationPlan(
                    nom=a["nom_" + langue], id_ap=a["id_ap"], region=region,
                    regle=Regle(ch_terrain, tuple(sorted(objets)), 0), genre="ami", exclue=True,
                    cle=str(a["medaille"]), medaille=a["medaille"], apres_jeu=marque))
                nb_locations += 1
    # -- V3, lot 18 : objectif « medaillium_complet » : voie de chacun des 448 n° et évènement de victoire -----------
    medaillium = None
    if est_md:
        medaillium, r_tout = _voies_medaillium(
            locations, connexions, regle_objectif, sigma_aj, regions_ok, set(pool) | {l.verrou for l in locations},
            seuil_md, regle_quete, regle_quete_aj, rang_s, voies_ps, l21, frozenset(exigibles),
            LG.membres_de(perm_leg) if perm_leg else None)
        locations.append(LocationPlan(
            nom=ob["nom_" + langue], id_ap=None, region=REGION_ORIGINE, regle=r_tout, genre="objectif",
            evenement=ob["nom_" + langue], cle=mode_objectif, apres_jeu="apres_jeu"))
        # un objet cité par la règle de victoire doit être de progression pour qu'Archipelago l'évalue
        for k in r_tout.objets + tuple(x for x, _n in r_tout.nombres):
            cites.add(k)
            if not str(classification.get(k)).startswith("progression"):
                classification[k] = "progression" if k in exigibles else CLASSE_PROGRESSION_SANS_EQUILIBRAGE
    # 2026-11-05 : locations atteintes AVANT l'arrêt de l'histoire que la règle de leur chapitre suppose franchi
    # (LOCATIONS_AVANT_ARRET) : sans les objets de cet arrêt (ceux que la location exige pour elle-même ne sont jamais
    # dans la table ; les objets restent cités : classification et `exiges` inchangés)
    # Suite (ap/tracker-avant-arret) : LOCATIONS_AVANT_ARRET_SUITE, sauf ce qu'une zone de la graine exige vraiment
    def garde_zone(loc, k: str) -> bool:
        """Vrai si une zone de la graine, dont la règle est comprise dans celle de la location (prudence : la location
        la demande peut-être), porte k et s'ouvre après l'arrêt de k ou l'exige sur son chemin (connexions)."""
        if not REGLES_ZONES:
            return False                # (règles des zones fermées : aucune zone n'a été ajoutée)
        objets = set(loc.regle.objets)
        for z, r_z in regle_zone.items():
            if k in r_z.objets and set(r_z.objets) <= objets and r_z.chapitres <= loc.regle.chapitres \
                    and (ZN.ZONES[z]["phase"] > PHASES_ARRET.get(k, 0) or k in acces_z[z].objets):
                return True
        return False

    if REGLES_AVANT_ARRET or REGLES_AVANT_ARRET_SUITE:
        # objets des connexions du chemin vers chaque région (premier chemin trouvé, comme `acces_z`) : un objet que la
        # région exige déjà reste dans la règle de la location (la région la fermerait de toute façon : la règle doit
        # garantir sa région)
        acces_aa = acces_objets_regions(connexions)
        for loc in locations:
            cle_aa = cle_avant_arret(loc)
            retires = set(LOCATIONS_AVANT_ARRET.get(cle_aa, ())) if REGLES_AVANT_ARRET else set()
            if REGLES_AVANT_ARRET_SUITE:
                retires |= set(LOCATIONS_AVANT_ARRET_SUITE.get(cle_aa, ())) - acces_aa.get(loc.region, set())
            retires = {k for k in retires & set(loc.regle.objets) if not garde_zone(loc, k)}
            if retires:
                loc.regle = Regle(loc.regle.chapitres, tuple(k for k in loc.regle.objets if k not in retires),
                                  loc.regle.rangs, loc.regle.nombres)
    nb_remplissage = nb_locations - nb_verrouilles - len(pool)
    if nb_remplissage < 0:
        raise ValueError("plus d'objets que de locations")

    if rang_s_obj and REGLES_RANG_S and not any(loc.regle.rangs >= EXEMPLAIRES_RANG_S for loc in locations):
        # ap/rang-s-objet : aucune location n'exige le rang S (objectif d'après-jeu sans check de rang S) : pas de 5e
        # exemplaire, ni de mode k = 80 (rang S par la requête 28, comme une graine d'avant)
        return construire_plan(**{**_arguments, "rang_s_objet": False})
    return Plan(langue=langue, regions=regions, connexions=connexions, locations=locations,
                pool_objets_cles=pool, exiges=frozenset(cites), melanges=frozenset(melanges),
                verrous_actifs=tuple(sorted(actifs)), boss=mode_boss, rangs=exemplaires, rangs_reel=reel, velo=velo,
                rang_s_objet=rang_s_obj,
                tablos=mode_tablos, quetes=mode_quetes, chapitres=bool(chapitres), amis=mode_amis, criminels=mode_criminels,
                objets_evenement=bool(evenement), invites=bool(invitations),
                invites_armees=bool(invitations_armees), pieces_speciales=ps, pieces_ordre=tuple(ordre_ps),
                lot21=l21, photos=(l21 and est_md) or blasters_l22, lot22=ps and bool(lot22),
                armees=bool(armees) and mode_amis == "tous" and not invitations_armees, boutiques=mode_boutiques,
                boutiques_prix_max=prix_max, distributeurs=mode_distributeurs,
                classification=classification, nb_remplissage=nb_remplissage, objet_prologue=prologue,
                objectif=mode_objectif, apres_jeu=mode_aj, blasters=mode_blasters, transfert=transfert,
                verrous_aj=verrous_aj, parchemins=bool(parchemins), boss_sigma=tuple(sorted(sigma_aj.items())),
                medaillium=medaillium, legendaires=perm_leg, yokai_zones=tuple(sorted(zones_y.items())),
                chantier=bool(chantier),
                tour_commerce=bool(tour_commerce), donjon_portails=bool(donjon_portails),
                tablos_apparition=bool(tablos_apparition) and mode_tablos == "tous")


def plan_atteignable(plan: Plan) -> bool:
    """Toutes les locations et l'objectif atteignables avec tous les objets du pool (objets placés d'office ramassés
    à leur location, évènements de chapitre et de victoire ramassés dès que leur règle est remplie) : contrôle « sans
    cycle » du tirage des zones (lots M2b)."""
    etat: Dict[str, int] = {}
    for k in plan.pool_objets_cles:
        etat[k] = etat.get(k, 0) + 1

    def ok(r: Regle, prologue: bool) -> bool:
        if r.chapitres > 0 and not etat.get("#ch%d" % r.chapitres):
            return False
        if any(not etat.get(k) for k in r.objets) or etat.get(OBJET_RANG, 0) < r.rangs:
            return False
        if any(etat.get(k, 0) < n for k, n in r.nombres):
            return False
        return not (prologue and plan.objet_prologue and not etat.get(plan.objet_prologue))
    faites: Set[str] = set()
    while True:
        regions = {REGION_ORIGINE}
        change = True
        while change:
            change = False
            for s, c, r in plan.connexions:
                if s in regions and c not in regions and ok(r, False):
                    regions.add(c)
                    change = True
        nouveau = False
        for loc in plan.locations:
            if loc.nom in faites or loc.region not in regions or not ok(loc.regle, loc.prologue):
                continue
            faites.add(loc.nom)
            nouveau = True
            gain = "#ch" + loc.cle if loc.genre == "chapitre" else "#but" if loc.genre == "objectif" else loc.verrou
            if gain:
                etat[gain] = etat.get(gain, 0) + 1
        if not nouveau:
            return len(faites) == len(plan.locations)


def tirer_zones(rng, options: dict, essais: int = 50) -> Tuple[Dict[int, str], Plan]:
    """Zones des Yo-kai demandés d'une graine (`zones.tirer` avec `rng` = `self.random`) et le plan construit avec
    elles (`options` : arguments de `construire_plan`) ; nouveau tirage, au plus `essais` fois, si une location devient
    inatteignable (cycle). Les règles des zones n'ont pas de cycle par construction (chapitre de la zone <= celui de
    l'attente de requêtes qui la demande) : le contrôle est une défense en profondeur."""
    for _ in range(essais):
        z = ZN.tirer(rng)
        plan = construire_plan(**dict(options, yokai_zones=z))
        if plan_atteignable(plan):
            return z, plan
    raise ValueError("zones des Yo-kai demandés : aucun tirage sans location inatteignable")


def remplissage_possible() -> Tuple[List[str], List[str]]:
    """(consommables, argent) : clés des objets de remplissage."""
    d = donnees()
    conso = [o["cle"] for o in d.objets if o["famille"] == "consommable"]
    argent = [o["cle"] for o in d.objets if o["famille"] == "argent"]
    return conso, argent
