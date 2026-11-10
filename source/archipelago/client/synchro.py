"""Cœur de synchronisation serveur Archipelago <-> boîte aux lettres du jeu (tâche C3, CONCEPTION §8.1, option B).

Le client est invisible : la configuration se saisit dans le LANCEUR seulement (config.json ; décision de
l'humain du 2026-09-28 : l'écran « Archipelago » de l'écran titre est en lecture seule) ; le jeu affiche l'état
(§5.2 : écran Archipelago et bandeau). Ce module :
1. surveille config.json (saisie du lanceur, sans GDB : révision de connexion, reconnexion si elle change quelque
   chose) et publie la configuration courante dans la zone « état » (serveur, slot, `connu` : jamais le mot de
   passe) ; la configuration qu'un jeu d'une version antérieure écrirait encore (zone J, claviers) est ignorée ;
2. se connecte au serveur (`ap_reseau.ClientAP`) et publie l'état : non configuré / connexion / connecté /
   erreur (+ message court en français) / déconnecté ;
3. dons : liste `ReceivedItems` -> file de dons (numéro = index AP + 1 ; « déjà livré » = compteur de la
   sauvegarde) ; notifications courtes (≤ 28 caractères, bandeau mono-ligne) ;
4. checks : journal (coffres ouverts, dons d'objets-clés substitués) et relecture des bits persistants
   (P+0x3C4 : coffres, spots 558..569 ; flags bit globaux de P+4 : boss d'histoire vaincus, posés par le jeu à
   la victoire seulement ; phases de quête de Q = *(*0x815244 + 0x10) : boss de quête, quête terminée (255)
   seulement après la victoire, docs/systemes/archipelago_boss.md ; flags « Yo-kai appelé » des Tablo-blabla,
   docs/systemes/archipelago_tablos.md ; octets `wantedNN` des Yo-criminels arrêtés, dans le même paquet ; bits « ami »
   du Médaillium, lus avec le suivi du tracker (5ter), docs/systemes/archipelago_amis_criminels.md) -> LocationChecks ;
5. tables (slot_data de l'APWorld, format 1 ; LocationScouts en repli) : coffres par index (objet de ce
   monde = vrai objet ; sinon vitrine), noms de vitrine par étiquette « <objet> (pour <joueur>) » (J5), dons
   de script des spots d'objets-clés (J3), verrous actifs et objets reçus (J4), récompenses de quête (boîte v5 :
   l'écran de résultat d'une requête montre l'objet AP à la place des objets de la quête, archipelago_quetes.md §8) ;
5bis. randomizer de Yo-kai (boîte v6, docs/systemes/archipelago_rando_yokai.md) : mélange σ calculé depuis la graine
   de `slot_data["rando_yokai"]` et la base locale `yokai_local.json` (générée depuis la ROM du joueur, jamais
   distribuée ; empreinte différente de la référence : mélange refusé), écrit dans la boîte seulement pour la
   sauvegarde liée (sinon `valide` = 0 : le jeu retire le mélange), `rando_yokai.json` pour le tracker du lanceur ;
5quater. randomizer des boss (boîte v7, docs/systemes/archipelago_rando_boss.md §9) : tables B / N calculées depuis la
   graine de `slot_data["rando_boss"]` et la base locale (format 4), écrites pour la sauvegarde liée seulement (même
   protocole que 5bis), `rando_boss.json` pour le tracker du lanceur ;
5ter. suivi pour le tracker du lanceur (sauvegarde liée seulement, avec ou sans randomizer) : `medaillium.json` (« vu »
   et « ami » du Médaillium, une lecture groupée P+0x40C..0x643) et `progression.json` (chapitre, pas, phase, rang de
   montre réel, après-jeu), toutes les PERIODE_MEDAILLIUM secondes ou dès que la progression publiée change ; en-tête
   relu après les données (écartées si la partie a changé) ; base locale d'un format antérieur régénérée depuis la
   ROM (une fois par session) ;
6. victoire (en-tête `progression` : flag « partie terminée », ou chapitre ≥ 11) -> CLIENT_GOAL, une fois, et
   seulement si elle survient APRÈS la liaison de la sauvegarde ; verrous (J4) : le jeu publie la liste des
   verrous COMPILÉS dans son build (boîte v4, zone des verrous +4) ; une partie dont `slot_data.verrous_actifs`
   exige un verrou absent est refusée (état « Verrous incompatibles » : rien n'est lié, livré ni envoyé, car la
   logique de la graine compterait sur un blocage que le jeu ne fait pas) ;
7. LIAISON de la sauvegarde (boîte v4, docs/systemes/archipelago_boite.md §11.2-§11.3) : le client n'adopte
   JAMAIS une sauvegarde qu'il n'a pas liée à cette partie AP. Seule une sauvegarde dont l'identifiant
   (P+0x3BC) vaut `ident_partie` est « liée » : elle seule reçoit des dons, envoie des checks et la victoire, et
   voit les tables (coffres, dons de script, verrous). Liaison automatique d'une partie NEUVE seulement
   (`raison_non_neuve`) : une partie Archipelago = une sauvegarde NEUVE (décision de l'humain du 2026-09-28,
   option (b) : la liaison manuelle d'une sauvegarde existante n'existe plus ; le client n'écrit jamais de clé
   manuelle). Une sauvegarde liée À LA MAIN par une version antérieure (clé bit 15) reste liée, règle G1-2 (décision de l'humain) : les checks DÉJÀ
   faits dans cette sauvegarde (coffres, spots, boss, quêtes, Tablo-blabla) sont envoyés, une fois ; la VICTOIRE
   jamais par cet effet : l'instantané (`RegistreLiaisons`, fichier `liaisons.json` du dossier du client) garde les
   bits de victoire déjà présents, et seule une victoire apparue APRÈS la liaison compte (une sauvegarde déjà finie
   ne fait jamais gagner la partie). Instantané d'exclusion restant : sauvegarde liée par un client v3 (clé 0) ;
8. resynchronisation complète après un relancement du jeu (nouvelle instance de la boîte) ou du client ;
9. suivi des checks pour l'onglet « Checks » du lanceur (`checks_local.py`) : `checks.json` (locations de la graine,
   faites, contenu des FAITES seulement, indices du serveur, objets reçus et expéditeurs, options du plan), réécrit
   seulement quand il change, sur évènement réseau (aucune lecture GDB) ; spoiler log `.txt` écrit seulement sur
   demande du lanceur (`spoiler_demande.json`, surveillé avec config.json), depuis les LocationScouts de TOUTES les
   locations du slot ;
10. discussion du serveur pour l'onglet « Discussion » du lanceur (`chat_local.py`) : chaque PrintJSON (couleurs résolues)
   et les évènements de connexion sont ajoutés à `messages.jsonl` (borné, rotation) ; les messages et commandes « !… »
   saisis dans le lanceur (`chat_commandes.json`, surveillé toutes les PERIODE_CHAT s) sont envoyés par Say, une fois,
   seulement par le client de la session visée et s'il est connecté. Fichiers locaux seulement : aucun paquet GDB.
   Sous-onglet « Indices » (`indices_local.py`) : indices du slot (clé `_read_hints_{team}_{slot}`, Get + SetNotify)
   écrits dans `indices.json` à chaque changement ; une commande du lanceur peut porter une action UpdateHint
   (priorité d'un indice), validée puis envoyée.
11. fenêtre « objet obtenu » des checks sans affichage dans le jeu (`anim_objet.py`, archipelago_boite.md §27) : chaque
   check envoyé d'une location « sans affichage » (boss, fins de chapitre, Montée de rang, Vélo, Tablo-blabla ; toujours
   actif, sans option) est mis dans la file ApAnim du jeu (sauvegarde liée, fonction 29 compilée), 8 places au plus ;
   le jeu les montre une par une au moment sûr du terrain. En-tête de la file lu seulement pendant qu'il y a du travail.

Le transport est abstrait : `PontGdb` (réel ou faux stub) et `ClientAP` (réel ou faux serveur) ; tout est
testable hors ligne (archipelago/tests/test_synchro.py).
"""
from __future__ import annotations

import asyncio
import collections
import contextlib
import copy
import json
import logging
import secrets
import struct
import sys
import time
import zlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from . import affichage as affichage
    from . import boite_protocole as bp
    from . import chat_local as ch
    from . import deathlink as dl
    from . import anim_objet as ao
    from . import checks_local as ck
    from . import indices_local as il
    from . import lieu_local as ll
    from . import amis_combat as amc
    from . import loupe_amis as lpa
    from . import derniers_objets as dobj
    from . import boite_v3 as v3
    from . import rando_yokai as rando
    from . import rando_boss as rboss
    from . import distributeurs as distrib
    from . import legendaires as leg
    from . import portails as portails
    from . import bingo as bingo
    from . import pieges_suivi as pgs
    from .ap_reseau import ClientAP, ObjetReseau, RefusConnexion
    from .boite import Boite, BoiteAbsente, EntreeCoffre, Entete, FilePleine, ObjetADonner
    from .config_locale import ConfigLocale, StockageConfig
    from .gdb import AccesRefuse, ArretNonConfirme, Deconnecte, DelaiDepasse, ErreurGdb, PontGdb
except ImportError:                                          # pragma: no cover - selon le mode d'import
    import affichage as affichage                           # type: ignore[no-redef]
    import boite_protocole as bp                            # type: ignore[no-redef]
    import chat_local as ch                                 # type: ignore[no-redef]
    import deathlink as dl                                  # type: ignore[no-redef]
    import anim_objet as ao                                 # type: ignore[no-redef]
    import checks_local as ck                               # type: ignore[no-redef]
    import indices_local as il                              # type: ignore[no-redef]
    import lieu_local as ll                                 # type: ignore[no-redef]
    import amis_combat as amc                               # type: ignore[no-redef]
    import loupe_amis as lpa                                # type: ignore[no-redef]
    import derniers_objets as dobj                          # type: ignore[no-redef]
    import boite_v3 as v3                                   # type: ignore[no-redef]
    import rando_yokai as rando                             # type: ignore[no-redef]
    import rando_boss as rboss                              # type: ignore[no-redef]
    import distributeurs as distrib                         # type: ignore[no-redef]
    import legendaires as leg                               # type: ignore[no-redef]
    import portails as portails                             # type: ignore[no-redef]
    import bingo as bingo                                   # type: ignore[no-redef]
    import pieges_suivi as pgs                              # type: ignore[no-redef]
    from ap_reseau import ClientAP, ObjetReseau, RefusConnexion  # type: ignore[no-redef]
    from boite import (Boite, BoiteAbsente, EntreeCoffre, Entete,  # type: ignore[no-redef]
                       FilePleine, ObjetADonner)
    from config_locale import ConfigLocale, StockageConfig  # type: ignore[no-redef]
    from gdb import (AccesRefuse, ArretNonConfirme, Deconnecte,  # type: ignore[no-redef]
                     DelaiDepasse, ErreurGdb, PontGdb)

DOSSIER_DONNEES = Path(__file__).resolve().parents[1] / "apworld" / "yokaiwatch2" / "donnees"
FORMAT_SLOT_DATA = 23           # format de slot_data de l'APWorld compris par ce client (2 : boss, 3 : quêtes, 4 : rangs,
#                                 5 : Tablo-blabla, 6 : requêtes et services, 7 : rang D verrouillé, mode k = 19,
#                                 8 : chapitres terminés, liste `avant_chapitre_10`, 9 : `rando_yokai`, 10 : `rando_boss`,
#                                 11 : `amis` et `criminels`,
#                                 12 : `death_link`,
#                                 13 : objets-clés de quête, emplacements sans bit (SCRIPT_BIT_AUCUN) détectés par `boss`,
#                                 14 : `fonctions_exigees`, 15 : `boutiques`, 16 : `bingo_kai_infini`,
#                                 17 : boutiques sans hachages, lus dans la ROM du joueur,
#                                 18 : `objets_evenement`, pour le tracker seulement,
#                                 19 : modes « par rencontre » de `rando_yokai`, 20 : rang de montre réel, mode k = 20,
#                                 21 : vélo réel, mode k = 21, 22 : réservé à ap/boss-adaptes (sauté),
#                                 23 : version du mélange des Yo-kai, `rando_yokai.mode` = « <mode>#2 » ; puis
#                                      « <mode>#3 » (lieu normal garanti, §21) et « <mode>#4 » (espèces
#                                      invitées, §22), sans changement de format)
# Fréquence de lecture (archipelago_boite.md §23) : chaque paquet GDB est traité par l'émulateur entre deux tranches
# d'exécution et chaque arrêt fige le jeu. Tour de base : UN paquet (l'en-tête de la boîte, 0x100 octets) ; tout le reste
# est lu sur évènement publié dans l'en-tête (journal, spots, passage sur le terrain, chapitre / pas, progression,
# sauvegarde, dons reçus du serveur), plus un filet de sécurité rare ; aucun arrêt sauf
# pour écrire, écritures d'un tour groupées dans un seul arrêt. Option `lecture` de config.json.
REGIMES_LECTURE = {
    "economique": {"periode": 1.0, "filet": 60.0},      # défaut
    "normale": {"periode": 0.5, "filet": 15.0},
}
LECTURE_DEFAUT = "economique"
# V3 : n° « client » de `fonctions_exigees` que CE client sait honorer sans rien demander au jeu (66 : victoire par les
# bits du Médaillium et terrains de Ψ Blasters, lot 3 ; 67 : option étendue 25, lot 6 ; 68 : zone ApVerrous3, lot 9) et
# n° de refus d'une option étendue manquante (125). Définis dans `boite_protocole` depuis le lot 9 ; les noms ci-dessous
# restent ceux que ce module utilise (et que ses tests remplacent pour jouer un client plus ancien).
FONCTION_CLIENT_5, FONCTION_CLIENT_6, FONCTION_CLIENT_7 = bp.FONCTION_CLIENT_5, bp.FONCTION_CLIENT_6, bp.FONCTION_CLIENT_7
# V3, lot 10 : n° « client » 69 (jamais publié par le jeu ; défini dans boite_protocole) : mélange des boss de VERSION 2,
# dont la permutation est portée par la graine (`rando_boss.sigma`) ; un client d'avant, qui tient un mode inconnu pour
# « pas de mélange » sans avertir, refuse la partie.
FONCTION_CLIENT_8 = bp.FONCTION_CLIENT_8
# V3, lot 14 : n° « client » 70 (jamais publié par le jeu ; `bp.FONCTION_CLIENT_9`) : ce client sait écrire la liste
# d'invités étendue (ApInvites2 : rangs 32..63, ligne de taux par invité, `_ecrire_invites`). Déclaré dans le protocole
# (`bp.FONCTIONS_CLIENT_V3`) depuis que ce client écrit la zone.
FONCTIONS_CLIENT_LOT3 = bp.FONCTIONS_CLIENT_V3
# Ordre d'arrivée des invités à l'Auberge (`slot_data.invites_ordre`, lot 14) : « liste » = ordre de `slot_data.invites`
# (toute graine de la V2 : clé absente) ; « reception » = ordre de réception des invitations (graines de la V3).
ORDRE_INVITES_LISTE, ORDRE_INVITES_RECEPTION = "liste", "reception"
OPTION2_MANQUANTE_BASE = bp.OPTION2_MANQUANTE_BASE
# Mot des terrains finis de Ψ Blasters : P + 0x64C (u32, bit n = terrain n), à la suite de la lecture groupée du
# Médaillium (P+0x40C..0x643) : la lecture est allongée jusqu'à P+0x64F quand la graine a des terrains (même paquet).
P_BLASTERS = 0x64C
PERIODE_MEDAILLIUM = 60.0       # s : filet de relecture du Médaillium (tracker) ; sinon sur changement de terrain / progression
TOURS_TRACKER_MIN = 10          # tours : relecture du Médaillium au plus une fois par 10 tours sur simple changement de terrain
TOURS_ATTENTE = 2               # tours : relecture de l'en-tête du mélange pendant le retrait d'un ancien mélange
TOURS_ACQUITTEMENT = 30         # tours : `journal_lu` écrit au plus tard (sinon avec la prochaine écriture)
FACTEUR_LECTURES_ARRETEES = 3   # stub qui ne sert pas les lectures jeu en marche (chaque lecture arrête le jeu) : tours ×3
PERIODE_BILAN = 300.0           # s : bilan de la charge GDB dans le journal du client
PERIODE_CHAT = 0.25            # s : surveillance de chat_commandes.json (messages saisis dans le lanceur ; fichier local)
PERIODE_CONFIG = 1.0            # s : surveillance de config.json (saisie du lanceur ; fichier local, aucun paquet GDB)
ESSAIS_RELECTURE = 3            # relecture des bits écartée (partie ou Q changés pendant la lecture) : réessais immédiats
PERIODE_REESSAI_BOSS = 1.0      # s : mélange des boss de version 2 non appliqué : fichiers locaux (ROM, base) revus
ATTENTE_RETRAIT_RANDO = 120.0   # s : attente maximale du retrait d'un ancien mélange avant d'écrire le nouveau
NOTIF_MAX_CAR = 28              # bandeau mono-ligne (~29 caractères larges visibles, E9C)
JOUEUR_MAX_CAR = 10
RESUME_AU_DELA = 3              # plus de dons que ça dans un même relevé : un résumé au lieu du détail
TYPES_DON = {"objet": bp.DON_OBJET, "argent": bp.DON_ARGENT, "yokai": bp.DON_YOKAI,
             "aucun": 0,   # objet AP sans objet du jeu (Rang de montre) : déposé en type 0, ignoré par le jeu
             # lot 4 des pièges : don de type 4, `hash` = n° du piège (archipelago_boite.md §57, pieges_suivi.py)
             "piege": bp.TYPE_DON_PIEGE}

MESSAGES = {                       # message court de l'état (≤ 20 caractères : écran Archipelago, lecture seule)
    "non_configure": "Non configuré",
    "connexion": "Connexion...",
    "connecte": "Connecté",
    "deconnecte": "Reconnexion...",
    "injoignable": "Serveur injoignable",
    "non_liee": "Sauvegarde non liée",
    "autre": "Autre partie AP",
    "jeu_ancien": "Jeu à mettre à jour",
    "liaison": "Liaison...",
    "verrous_incompatibles": "Verrous manquants",
    # mélange des boss de VERSION 2 (tiré à la génération : la logique de la graine le suppose) non appliqué
    "boss_attente": "Boss : préparation",
    "boss_rom": "Boss : ROM absente",
    "boss_refuse": "Mélange boss refusé",
    "boss_jeu": "Jeu à mettre à jour",
    # V3, lots M2b : mélange des Yo-kai de VERSION 7 (zones des Yo-kai demandés : la logique le suppose) non appliqué
    "yokai_attente": "Yo-kai : préparation",
    "yokai_rom": "Yo-kai : ROM absente",
    "yokai_refuse": "Mélange Yo-kai refusé",
    "yokai_jeu": "Jeu à mettre à jour",
}
MESSAGES_EN = {                    # mêmes messages en anglais (option `langue_notifications`, ≤ 20 caractères)
    "non_configure": "Not configured",
    "connexion": "Connecting...",
    "connecte": "Connected",
    "deconnecte": "Reconnecting...",
    "injoignable": "Server unreachable",
    "non_liee": "Save not linked",
    "autre": "Other AP game",
    "jeu_ancien": "Game needs update",
    "liaison": "Linking...",
    "verrous_incompatibles": "Missing locks",
    "boss_attente": "Bosses: preparing",
    "boss_rom": "Bosses: ROM missing",
    "boss_refuse": "Boss shuffle refused",
    "boss_jeu": "Game needs update",
    "yokai_attente": "Yo-kai: preparing",
    "yokai_rom": "Yo-kai: ROM missing",
    "yokai_refuse": "Yo-kai mix refused",
    "yokai_jeu": "Game needs update",
}
MESSAGES_PAR_LANGUE = {"fr": MESSAGES, "en": MESSAGES_EN}
# statuts « mélange des boss de la graine non appliqué » (version 2 seulement) : partie traitée comme incompatible
STATUTS_BOSS_MANQUANT = ("boss_attente", "boss_rom", "boss_refuse", "boss_jeu")
STATUTS_YOKAI_MANQUANT = ("yokai_attente", "yokai_rom", "yokai_refuse", "yokai_jeu")
NOTIF_SAUVEGARDE = {               # notification(s) du bandeau, une fois par sauvegarde chargée (≤ 28 caractères)
    # une partie Archipelago = une sauvegarde neuve (2026-09-28, option (b)) : le dire au joueur
    "non_liee": ("Sauvegarde non liée à AP", "Lancez une nouvelle partie"),
    "autre": "Autre partie AP : bloquée",
    "jeu_ancien": "Jeu à mettre à jour (AP)",
    "verrous_incompatibles": "Verrous incompatibles (AP)",
    # (« boss_attente » : préparation en cours, pas de bandeau ; l'écran Archipelago et le lanceur le disent)
    "boss_rom": ("Boss mélangés : ROM absente", "À régler dans le lanceur"),
    "boss_refuse": ("Mélange des boss refusé", "Voir le lanceur (ROM, mod)"),
    "boss_jeu": ("Boss mélangés : jeu ancien", "Mettez le mod à jour"),
    "yokai_rom": ("Yo-kai mélangés : ROM absente", "À régler dans le lanceur"),
    "yokai_refuse": ("Mélange des Yo-kai refusé", "Voir le lanceur (ROM, mod)"),
    "yokai_jeu": ("Yo-kai mélangés : jeu ancien", "Mettez le mod à jour"),
}
NOTIF_SAUVEGARDE_EN = {            # mêmes notifications en anglais (≤ 28 caractères)
    "non_liee": ("Save not linked to AP", "Start a new game"),
    "autre": "Other AP game: blocked",
    "jeu_ancien": "Game needs updating (AP)",
    "verrous_incompatibles": "Incompatible locks (AP)",
    "boss_rom": ("Shuffled bosses: no ROM", "Set it up in the launcher"),
    "boss_refuse": ("Boss shuffle refused", "See launcher (ROM, mod)"),
    "boss_jeu": ("Shuffled bosses: old game", "Please update the mod"),
    "yokai_rom": ("Shuffled Yo-kai: no ROM", "Set it up in the launcher"),
    "yokai_refuse": ("Yo-kai shuffle refused", "See launcher (ROM, mod)"),
    "yokai_jeu": ("Shuffled Yo-kai: old game", "Please update the mod"),
}
NOTIF_SAUVEGARDE_PAR_LANGUE = {"fr": NOTIF_SAUVEGARDE, "en": NOTIF_SAUVEGARDE_EN}
# Autres textes du bandeau, par langue des notifications (slot_data `langue_notifications`, `Catalogue.langue`) :
# le client les fabrique lui-même (le jeu n'affiche que la chaîne déposée). Retour d'un testeur de la bêta V3
# (2026-10-23) : ils restaient en français dans le monde anglais.
TEXTES_BANDEAU = {
    "fr": {"recu": "Reçu : {objet}", "envoye": "Envoyé : {objet}", "pour": "{objet} (pour {joueur})",
           "recus": "{n} objets reçus", "envoyes": "{n} objets envoyés", "objectif": "Objectif atteint !",
           "plein": "Inventaire plein !", "refus": "Connexion refusée"},
    "en": {"recu": "Received: {objet}", "envoye": "Sent: {objet}", "pour": "{objet} (for {joueur})",
           "recus": "{n} items received", "envoyes": "{n} items sent", "objectif": "Goal complete!",
           "plein": "Inventory full!", "refus": "Connection refused"},
}
VICTOIRE = bp.PROGRESSION_VICTOIRE | bp.PROGRESSION_APRES_JEU
# Bouclage du chapitre 10 (docs/systemes/archipelago_couverture.md §2.3) : de 10-10 à la fin du chapitre 10, la ville
# est fermée. Dernière phase de promenade libre avant : 9-80 (90080, jusqu'à l'entrée dans les Plaines Plinpot t200d00 ;
# ensuite boss, scènes et passage automatique à 10-10 [C, phase_set_c09 / c09_trigger n° 11-13]). Dès 9-80 (et donc à
# l'entrée du chapitre 10 pour une sauvegarde liée plus tard), s'il reste des checks hors du chapitre 10 (slot_data
# `avant_chapitre_10`), bandeau d'avertissement, une fois par sauvegarde liée (drapeau `alerte_ch10` de l'instantané
# de liaison). Textes saisis par nous (pas du jeu), une ligne de bandeau chacun (≤ NOTIF_MAX_CAR) ; {n} = nombre de
# checks restants.
# Mirapo de poche (docs/systemes/archipelago_mirapo_poche.md) : rappel de la commande à la réception de l'exemplaire
# qui la donne ; trois bandeaux d'une ligne (≤ NOTIF_MAX_CAR), textes saisis par nous. Sur le terrain, SELECT ne met
# plus le jeu en pause (ap/mirapo-touche) : le 3e bandeau le dit.
RAPPEL_MIRAPO = {
    "fr": ("Mirapo de poche reçu !", "Tenir SELECT : miroirs", "Pause : START"),
    "en": ("Pocket Mirapo received!", "Hold SELECT: mirror menu", "Pause: START"),
}
SEUIL_ALERTE_CH10 = (9, 80)      # (chapitre, pas de scénario) : phase 9-80
ALERTE_CHAPITRE_10 = {
    "fr": ("Ville bouclée au chap. 10", "{n} checks à faire avant", "ou après la victoire"),
    "en": ("Town locks down in ch. 10", "{n} checks to do before", "or after the victory"),
}
FICHIER_LIAISONS = "liaisons.json"
FICHIER_INVITES = "invites.json"    # invités de l'Auberge des voyageurs : état pour le tracker de Yo-kai du lanceur
FORMAT_INVITES = 1
ERREURS_REFUS = [  # (erreur Archipelago, code §5.2, message court)
    ("InvalidSlot", v3.ERR_SLOT, "Slot inconnu"),
    ("InvalidPassword", v3.ERR_MDP, "Mot de passe refusé"),
    ("IncompatibleVersion", v3.ERR_VERSION, "Version incompatible"),
    ("InvalidGame", v3.ERR_JEU, "Mauvais jeu"),
]
ERREURS_REFUS_EN = {"InvalidSlot": "Unknown slot", "InvalidPassword": "Wrong password",
                    "IncompatibleVersion": "Incompatible version", "InvalidGame": "Wrong game"}


def textes_bandeau(langue: str) -> dict:
    """Textes du bandeau dans la langue des notifications (français si inconnue)."""
    return TEXTES_BANDEAU.get(langue, TEXTES_BANDEAU["fr"])


# ================================================================================================ textes
def _car(texte: str, n: int) -> str:
    return texte if len(texte) <= n else texte[:max(0, n - 3)].rstrip() + "..."


def texte_court(principal: str, suffixe: str = "", max_car: int = NOTIF_MAX_CAR,
                max_largeur: int = bp.NOTIF_LARGEUR) -> str:
    """« principal + suffixe » en une ligne : au plus `max_car` caractères et `max_largeur` demi-unités (règle
    du bandeau, boite_protocole.largeur) ; c'est `principal` qui est raccourci (« ... »), le suffixe reste."""
    principal = " ".join(principal.split())
    suffixe = " ".join(suffixe.split()) if suffixe.strip() else ""
    if suffixe:
        suffixe = " " + suffixe
    n = len(principal)
    while n > 0:
        t = (principal if n == len(principal) else principal[:max(0, n - 3)].rstrip() + "...") + suffixe
        if len(t) <= max_car and bp.largeur(t) <= max_largeur:
            return t
        n -= 1
    return _car(suffixe.strip(), max_car)


def texte_recu(objet: str, joueur: str | None, quantite: int = 1, langue: str = "fr") -> str:
    q = f" x{quantite}" if quantite > 1 else ""
    principal = textes_bandeau(langue)["recu"].format(objet=f"{objet}{q}")
    if joueur:
        return texte_court(principal, f"({_car(joueur, JOUEUR_MAX_CAR)})")
    return texte_court(principal)


def texte_envoye(objet: str, joueur: str, langue: str = "fr") -> str:
    return texte_court(textes_bandeau(langue)["envoye"].format(objet=objet), f"({_car(joueur, JOUEUR_MAX_CAR)})")


def nom_vitrine(objet: str, joueur: str | None, langue: str = "fr") -> str:
    """Nom affiché par un coffre qui contient l'objet d'un autre monde (décision 3 de l'humain) ; même gabarit que
    l'APWorld (`slot_data.POUR`)."""
    return textes_bandeau(langue)["pour"].format(objet=objet, joueur=joueur) if joueur else objet


def ident_partie_par_defaut(graine: str, team: int, slot: int) -> int:
    """Identifiant de partie si slot_data n'en a pas : même formule que l'APWorld (`slot_data.ident_partie` :
    CRC-32 de « graine:slot », non nul). L'équipe n'y entre pas (comme dans l'APWorld)."""
    return zlib.crc32(f"{graine}:{slot}".encode("utf-8")) & 0xFFFFFFFF or 1


def _entier(v: Any) -> int:
    return int(v, 0) if isinstance(v, str) else int(v)


# ================================================================================================ catalogue
# Verrous dont le code a été RETIRÉ du jeu : jamais exigés du build ni écrits dans `actifs`, même si une graine plus
# ancienne les déclare `code_jeu: True`. Pile ou passe (k = 1) : verrou de déclencheur des graines du 2026-09-30 au
# 2026-10-01, retiré (décision de l'humain : la Crank-a-kai du tutoriel n'accepte que la pièce, le jeu bloque de
# lui-même ; archipelago_objets_cles.md §14.9).
VERROUS_SANS_CODE = frozenset({"pile_ou_passe"})


def verrou_code_jeu(v: dict) -> bool:
    """Vrai si ce verrou de `slot_data.verrous_actifs` doit être appliqué par le CODE du jeu (masque de flag,
    commande 0x3CEF, plafond de phase, déclencheur) : objet mélangé (sinon il reste à sa place et le jeu le donne
    lui-même), verrou dont le code existe encore (VERROUS_SANS_CODE : Pile ou passe) et mécanisme autre que « vérifié
    en jeu ». Champ explicite `code_jeu` de l'APWorld s'il est présent."""
    if not v.get("melange", True) or v.get("cle") in VERROUS_SANS_CODE:
        return False
    return bool(v.get("code_jeu", v.get("mecanisme") != "verifie_en_jeu"))


@dataclass
class Contenu:
    """Ce qu'une location montre dans le jeu (slot_data format 1 : {propre, hachage, texte})."""
    propre: bool
    hachage: int
    texte: str | None = None


@dataclass
class Emplacement:
    """Emplacement d'objet-clé (spot) : don de script substitué (J3)."""
    location: int
    bit: int
    hachage_origine: int = 0
    objet_origine: int = 0
    substituer: bool = True
    hachages: tuple[int, ...] = ()      # V3 : tous les hachages d'origine du don (Yo-kai Watch : garçon, fille) ; vide :
    #                                     `hachage_origine` seul


@dataclass
class Recompense:
    """Requête ou service de la graine (slot_data format 6) : location, n° de quête (phase 255 = terminée), service
    (255 transitoire : remis à 0 par le tirage des services, archipelago_quetes.md §2.5)."""
    location: int
    quete: int
    service: bool = False


def _installation_boutiques():
    """Module `archipelago/installation/boutiques.py` (distribué avec le client, comme `installation/rencontres.py`)."""
    racine = Path(__file__).resolve().parents[1]          # archipelago/
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    from installation import boutiques as ib               # noqa: E402
    return ib


@dataclass
class Boutique:
    """Article de boutique de la graine : location, hachage(s) de l'article (clé du jeu), bit persistant « premier achat
    fait » (octets de flags globaux, boite.h AP_BOUTIQUE_OCTETS). Format 17 : `slot_data` ne donne que le code de la
    boutique et le rang de ses entrées ; `articles` est lu dans la ROM du joueur (`installation/boutiques.py`,
    `boutiques_local.json`), vide tant que ce n'est pas fait. Format 15/16 : `articles` venait de `slot_data`."""
    location: int
    articles: tuple[int, ...]
    bit: int
    boutique: str | None = None
    entrees: tuple[int, ...] = ()
    nb_entrees: int | None = None


@dataclass(frozen=True)
class Invite:
    """Invité de l'Auberge des voyageurs (slot_data `invites`, docs/systemes/archipelago_invites.md §14 et §15) : Yo-kai
    que le jeu fait apparaître à l'Auberge quand le client le DÉCLARE. `declencheur` « requetes » (Pandanoko) : toutes
    les `locations` (les requêtes-checks de la graine) sont cochées côté serveur ; « objet » (les 30 invités à
    invitation) : l'objet Archipelago `objet` (« Invitation : <nom> ») a été reçu. Check « Ami » = `location`, envoyé
    quand le bit « ami » du n° `medaille` est posé (`_verifier_amis`, lecture groupée du Médaillium)."""
    location: int
    medaille: int                     # n° du Médaillium (bit « ami »)
    param: int                        # hachage CHARA_PARAM de l'espèce
    declencheur: str
    locations: frozenset[int]
    objet: int = 0                    # déclencheur « objet » : identifiant AP de l'invitation
    # (V3, lot 20 : la ligne de taux relevé du lot 14, clé `taux` de slot_data, est abandonnée : le client ne l'écrit
    # plus, tout invité est au taux du jeu)


@dataclass
class Catalogue:
    """Ce que le client doit savoir de ses objets et locations : objet AP -> don ; location de coffre -> index
    TBox ; spots ; verrous. Chargé depuis les données versionnées de l'APWorld, puis remplacé par `slot_data`
    (format 1 de l'APWorld, `archipelago/apworld/README.md` ; les anciennes clés proposées par C3 restent lues)."""
    objets: dict[int, ObjetADonner] = field(default_factory=dict)
    noms: dict[int, str] = field(default_factory=dict)
    cles: dict[str, int] = field(default_factory=dict)             # clé de l'objet -> identifiant AP
    # objet AP « sans objet du jeu » (don « aucun ») qui a pourtant un objet du jeu FACULTATIF, ajouté au RomFS du
    # joueur par l'installation (invitations, archipelago_invites.md §16) : identifiant AP -> hachage. Décidé ici, par
    # le client, pour toute graine (ancienne ou non : `slot_data` dit « aucun ») ; un jeu sans ces objets ignore le don
    objets_du_jeu: dict[int, int] = field(default_factory=dict)
    coffres: dict[int, int] = field(default_factory=dict)          # location -> index TBox
    hachages_tbox: dict[int, int] = field(default_factory=dict)    # location -> hachage (v2, facultatif)
    spots: dict[int, int] = field(default_factory=dict)            # bit TBox (558..) -> location
    contenus: dict[int, Contenu] = field(default_factory=dict)     # location -> contenu (slot_data)
    emplacements: dict[int, Emplacement] = field(default_factory=dict)   # location -> spot (slot_data)
    verrous: dict[int, int] = field(default_factory=dict)          # k (bit - 558) -> objet AP qui l'ouvre
    boss: dict[int, int] = field(default_factory=dict)             # location -> flag bit global (slot_data)
    quetes: dict[int, int] = field(default_factory=dict)           # location -> n° de quête (boss de quête)
    tablos: dict[int, int] = field(default_factory=dict)           # location -> flag « Yo-kai appelé » (Tablo-blabla)
    amis: dict[int, int] = field(default_factory=dict)             # location -> n° du Médaillium (bit « ami »)
    amis_paires: list[tuple[int, int]] = field(default_factory=list)   # (location, n°) : tous les n° d'une location
    criminels: dict[int, tuple[int, int]] = field(default_factory=dict)  # location -> (n° du criminel, étapes)
    # fonctions du patch exigées par la graine (format 14 : bits 24.. de ApVerrous::compiles, ex. Yo-criminels libres)
    fonctions: set[int] = field(default_factory=set)
    # invités de l'Auberge des voyageurs (slot_data `invites`, format 23 et plus) : vide pour une graine sans invité
    invites: list[Invite] = field(default_factory=list)
    # V3, lot 14 : ordre d'arrivée des invités (« liste » : ordre de `invites`, toute graine de la V2 ; « reception » :
    # ordre de réception des invitations)
    invites_ordre: str = ORDRE_INVITES_LISTE
    fonctions_etendues: set[int] = field(default_factory=set)   # n° >= 32 de `fonctions_exigees`
    verrous2: dict[int, int] = field(default_factory=dict)      # V3 : verrou étendu k (40..55) -> objet AP
    tunnel_sans_limite: bool = False                            # V3 : option `tunnel_sans_limite` de la graine
    amitie: int = 0                                             # V3, lot 16 : option `amitie` (0 normal, 1 x2, 2 x4, 3 assurée)
    # V3, lot 17 : options de confort de l'après-jeu (clés du même nom, absentes = désactivées) : options étendues
    # 29 (revanches et boss de la Voie du mystère sans limite de jour) et 30 (tirage dirigé des machines de la Voie)
    revanches_sans_limite: bool = False
    tirage_dirige_voie: bool = False
    # V3, lot 6 : la graine a les requêtes à transfert de sauvegarde (`fonctions_exigees` contient 37) : le client pose
    # l'option étendue 25 ; des locations en dépendent (refus si le jeu ne la compile pas)
    requetes_transfert: bool = False
    # V3, lot 9 : verrous de la deuxième zone étendue (k = 56..87, ApVerrous3) -> objet AP ; `deathlink_orge` : la
    # graine demande que les parties perdues de la Terr'heure / de Blasters comptent pour le DeathLink (clé de
    # slot_data absente d'une graine de la V2) : option étendue 26, posée seulement si le DeathLink est activé
    verrous3: dict[int, int] = field(default_factory=dict)
    # Mirapo de poche : k -> exemplaires de son objet qu'il faut avoir reçus pour écrire recu[k] = 1 (champ
    # `exemplaires` de l'entrée de `verrous_actifs` ; absent : 1)
    exemplaires3: dict[int, int] = field(default_factory=dict)
    deathlink_orge: bool = False
    # V3, lot 3 : victoire = partie terminée ET tous ces bits du Médaillium (vide : partie terminée seulement) ;
    # terrains de Ψ Blasters : location -> n° du terrain (bit du mot P + 0x64C)
    objectif_medailles: tuple = ()
    # V3, lot 18 (objectif « medaillium_complet ») : nombre de ces n° qui suffit à la victoire (None : tous)
    objectif_seuil: int | None = None
    # V3, lot 20 : pièces spéciales du Crank-a-kai (clé `pieces_speciales` de slot_data) : le client pose l'option
    # étendue 32 du jeu (ApPieces), écrit l'ordre de sortie des 16 de la Pièce 5 étoiles (`pieces_ordre` : n° du
    # Médaillium ; vide : absent ou invalide) et tient les compteurs de pièces reçues
    pieces_speciales: bool = False
    pieces_ordre: tuple = ()
    # V3, lot 21 : photos de Ψ Blasters tenues pour prises (clé `photos_blasters` de slot_data : objectif
    # « medaillium_complet ») : le client pose l'option étendue 33 du jeu (bit 1 du mot d'options de ApPieces).
    photos_blasters: bool = False
    # V3, lot 22 : fréquence du train doré (clé `train_dore` de slot_data, k sur 10 ; absente : 1, jeu d'origine) : le
    # client écrit k dans ApPieces::train_reglage et pose l'option étendue 34 (bit 2 du mot d'options)
    train_dore: int = 1
    # ap/blasters-terrains-apworld : terrains de Ψ Blasters d'autres éditions jouables seul (clé
    # `blasters_autres_editions` de slot_data) : le client pose l'option étendue 35 du jeu (bit 3 du mot d'options de
    # ApPieces) ; absente du jeu : refus (des locations en dépendent)
    blasters_editions: bool = False
    blasters: dict[int, int] = field(default_factory=dict)
    # Yo-kai d'évènement à leur emplacement d'origine (slot_data `evenement_places`) : bit de ApPnj::ev_declares ->
    # identifiant AP de l'objet qui fait apparaître le Yo-kai ; vide pour une graine antérieure (rien n'est écrit)
    evenement_places: dict[int, int] = field(default_factory=dict)
    recompenses: dict[int, Recompense] = field(default_factory=dict)  # location -> requête / service (format 6)
    boutiques: dict[int, Boutique] = field(default_factory=dict)   # location -> article de boutique (format 15)
    # V3, lot C1 : distributeurs de soda (clé `distributeurs` de slot_data ; absente : aucun) : location -> {carte,
    # rang, nb_points, boisson, contenu} (distributeurs.lire_slot_data) ; suivi par `Synchro.distrib`
    distributeurs: dict[int, dict] = field(default_factory=dict)
    quetes_boss: set[int] = field(default_factory=set)             # n° de quête des entrées `quete` de `boss`
    # locations hors du chapitre 10 (slot_data format 8) : bandeau d'avertissement à l'entrée du chapitre 10
    avant_chapitre_10: set[int] = field(default_factory=set)
    # randomizer de Yo-kai (slot_data format 9 ; modes par rencontre : format 19) : {"mode": "par_rang" | "total" |
    # "par_rencontre_rang" | "par_rencontre_total", "graine": 31 bits}, None sinon
    rando_yokai: dict | None = None
    rando_yokai_inconnu: str | None = None  # mode de slot_data que ce client ne sait pas lire (APWorld plus récent)
    # V3, lots M2b : entrée `yokai_zones` de slot_data (zones des Yo-kai demandés, mélange de version 7), telle quelle
    yokai_zones: dict | None = None
    # randomizer des boss (slot_data format 10) : {"mode": "meme_classe" | "total", "graine": 31 bits}, None sinon
    rando_boss: dict | None = None
    rando_boss_inconnu: str | None = None       # mode de mélange des boss que ce client ne connaît pas (boss d'origine)
    # V3, force des boss adaptée à leur place (clé `rando_boss_force` de slot_data, absente = force d'origine ;
    # archipelago_rando_boss.md §15) : {"mode": "adaptee", "exclus": (clés des boss jamais adaptés : boss de l'objectif)}
    # ou None ; `rando_boss_force_inconnu` : valeur que ce client ne sait pas lire (force d'origine, avertissement)
    rando_boss_force: dict | None = None
    rando_boss_force_inconnu: str | None = None
    death_link: bool = False           # option DeathLink du slot (format 12)
    bingo_kai_infini: bool = False     # option « Bingo-kai infini » (format 16) : bit 27 de `actifs` (boîte, §20)
    # (seulement les verrous que le JEU doit appliquer : objet mélangé, mécanisme codé dans le jeu)
    vitrine: int = v3.VITRINE
    politique_reessai: bool = True
    langue: str = "fr"
    ident_partie: int | None = None
    format_slot_data: int = 0

    @classmethod
    def charger(cls, dossier: Path | None = None) -> "Catalogue":
        d = Path(dossier) if dossier else DOSSIER_DONNEES
        c = cls()
        try:
            objets = json.loads((d / "objets.json").read_text(encoding="utf-8"))["objets"]
            coffres = json.loads((d / "coffres.json").read_text(encoding="utf-8"))["coffres"]
            spots = json.loads((d / "emplacements_objets_cles.json").read_text(encoding="utf-8"))["emplacements"]
        except (OSError, ValueError, KeyError) as e:
            logging.getLogger("ykw2ap.synchro").warning("Données de l'APWorld illisibles (%s) : catalogue vide", e)
            return c
        for o in objets:
            t = TYPES_DON.get(o.get("don", "objet"), bp.DON_OBJET)
            q = int(o.get("montant", 1)) if t == bp.DON_ARGENT else int(o.get("quantite", 1))
            h = o.get("piege", 0) if t == bp.TYPE_DON_PIEGE else o.get("hachage", 0)   # (piège : n° du piège)
            c.objets[int(o["id_ap"])] = ObjetADonner(t, _entier(h) & 0xFFFFFFFF, q)
            c.noms[int(o["id_ap"])] = o.get("nom_fr", "")
            c.cles[o.get("cle")] = int(o["id_ap"])
            # (`inventaire` faux : invitation sans objet du jeu, ex. Yo-kai d'évènement à leur emplacement d'origine)
            if o.get("famille") == "invitation" and t == 0 and str(o.get("cle", "")).isascii() \
                    and o.get("inventaire", True):
                c.objets_du_jeu[int(o["id_ap"])] = bp.hachage_invitation(o["cle"])
        for x in coffres:
            c.coffres[int(x["id_ap"])] = int(x["index_tbox"])
        for s in spots:
            bit = v3.SPOTS_PAR_DEFAUT.get(s.get("objet"))
            if bit is not None:
                c.spots[bit] = int(s["id_ap"])
        return c

    @staticmethod
    def _don(o: dict) -> ObjetADonner:
        t = TYPES_DON.get(o.get("type", o.get("don", "objet")), bp.DON_OBJET)
        q = _entier(o.get("montant", o.get("quantite", 1)))
        return ObjetADonner(t, _entier(o.get("hachage", 0)) & 0xFFFFFFFF, q)

    def appliquer_slot_data(self, sd: dict) -> None:
        """slot_data format 1 (APWorld) : ident_partie, langue_notifications, politique_reessai
        ("reessayer"/"ignorer"), verrous_actifs [{objet, cle, hachage, ...}], hachage_vitrine,
        coffres [{index_tbox, location, propre, hachage, texte}], emplacements [{location, objet_origine,
        hachage_origine, bit_tbox, substituer, propre, hachage, texte}], dons {id: {type, hachage, quantite |
        montant}}. Lus aussi (proposition C3) : coffres en identifiants seuls, spots_objets_cles, objets,
        quantites, vitrine, politique_reessai booléen."""
        if not isinstance(sd, dict):
            return
        self.format_slot_data = int(sd.get("format", 0) or 0)
        if sd.get("ident_partie"):
            self.ident_partie = _entier(sd["ident_partie"]) & 0xFFFFFFFF or None
        if isinstance(sd.get("coffres"), list):
            gardes: dict[int, int] = {}
            for x in sd["coffres"]:
                if isinstance(x, dict):
                    loc = _entier(x["location"])
                    idx = _entier(x.get("index_tbox", self.coffres.get(loc, -1)))
                    if x.get("hachage_tbox"):
                        self.hachages_tbox[loc] = _entier(x["hachage_tbox"]) & 0xFFFFFFFF
                    if "hachage" in x:
                        self.contenus[loc] = Contenu(bool(x.get("propre")), _entier(x["hachage"]) & 0xFFFFFFFF,
                                                     x.get("texte"))
                else:
                    loc = _entier(x)
                    idx = self.coffres.get(loc, -1)
                if 0 <= idx < bp.TBOX_NOMBRE and idx not in v3.BITS_RESERVES:
                    gardes[loc] = idx
            self.coffres = gardes
        if isinstance(sd.get("emplacements"), list):
            self.spots, self.emplacements = {}, {}
            for x in sd["emplacements"]:
                loc, bit = _entier(x["location"]), _entier(x["bit_tbox"])
                if bit in v3.BITS_RESERVES:
                    self.spots[bit] = loc
                elif bit != bp.SCRIPT_BIT_AUCUN:
                    continue
                # format 13 : objet-clé de quête sans bit (SCRIPT_BIT_AUCUN) : substitution du don seulement, le check
                # est détecté par son entrée de `boss` (flag bit global ou quête à 255)
                self.emplacements[loc] = Emplacement(loc, bit, _entier(x.get("hachage_origine", 0)) & 0xFFFFFFFF,
                                                     _entier(x.get("objet_origine", 0)), bool(x.get("substituer", True)),
                                                     tuple(_entier(h) & 0xFFFFFFFF for h in x["hachages_origine"])
                                                     if isinstance(x.get("hachages_origine"), list) else ())
                if "hachage" in x:
                    self.contenus[loc] = Contenu(bool(x.get("propre")), _entier(x["hachage"]) & 0xFFFFFFFF,
                                                 x.get("texte"))
        if isinstance(sd.get("boss"), list):
            # boss d'histoire (format 2) : check = flag bit global posé à la victoire ; boss de quête (format 3) :
            # check = phase de la quête à 255 (terminée) ; seulement ceux de la graine
            self.boss, self.quetes, self.quetes_boss = {}, {}, set()
            for x in sd["boss"]:
                if not isinstance(x, dict) or "location" not in x:
                    continue
                if "flag" in x:
                    f = _entier(x["flag"])
                    if 0 <= f <= bp.FLAG_GLOBAL_MAX:
                        self.boss[_entier(x["location"])] = f
                elif "quete" in x and "phase_min" in x:
                    # V3 : don détecté par la PHASE de sa quête (Documents perdus, Cartes d'Ultramax) : pseudo-numéro
                    # rangé avec les quêtes, même lecture groupée des phases
                    n, p = _entier(x["quete"]), _entier(x["phase_min"])
                    if bp.quete_phase_valide(n, p):
                        self.quetes[_entier(x["location"])] = bp.quete_phase_pseudo(n, p)
                        self.quetes_boss.add(bp.quete_phase_pseudo(n, p))
                elif "quete" in x:
                    n = _entier(x["quete"])
                    if 0 <= n < bp.NB_QUETES:
                        self.quetes[_entier(x["location"])] = n
                        self.quetes_boss.add(n)
                elif "octet" in x and "seuil" in x:
                    # boss détecté par un octet global qui ne décroît jamais (Taprice : progression du Tunnel sans
                    # fin >= 6, archipelago_boss.md §11) : pseudo-flag rangé avec les flags de boss
                    o, s = _entier(x["octet"]), _entier(x["seuil"])
                    if bp.boss_octet_valide(o, s):
                        self.boss[_entier(x["location"])] = bp.boss_octet_pseudo(o, s)
        if isinstance(sd.get("tablos"), list):
            # Tablo-blabla (format 5) : check = flag bit global « Yo-kai appelé » (archipelago_tablos.md §9)
            self.tablos = {}
            for x in sd["tablos"]:
                if isinstance(x, dict) and "location" in x and "flag" in x:
                    f = _entier(x["flag"])
                    if 0 <= f <= bp.FLAG_GLOBAL_MAX:
                        self.tablos[_entier(x["location"])] = f
        if isinstance(sd.get("amis"), list):
            # amis (format 11) : check = bit « ami » du Médaillium (P+0x44C | P+0x604), n° du Médaillium 1..511
            # une location peut avoir plusieurs n° (Ultramax N / K : l'un OU l'autre) : `amis` garde le premier,
            # `amis_paires` les a tous ; seules les locations de CETTE liste sont envoyées (graine plus ancienne : ses
            # 196 amis seulement)
            self.amis, self.amis_paires = {}, []
            for x in sd["amis"]:
                if isinstance(x, dict) and "location" in x and "medaille" in x:
                    n = _entier(x["medaille"])
                    if 0 < n < rando.TAILLE_MEDAILLIUM * 8:
                        self.amis.setdefault(_entier(x["location"]), n)
                        self.amis_paires.append((_entier(x["location"]), n))
        if isinstance(sd.get("criminels"), list):
            # Yo-criminels (format 11) : check = octet `wantedNN` (P + 0x2D0 + n) >= nombre d'étapes
            self.criminels = {}
            for x in sd["criminels"]:
                if isinstance(x, dict) and "location" in x and "numero" in x:
                    n, e = _entier(x["numero"]), _entier(x.get("etapes", 1))
                    if 1 <= n <= bp.NB_CRIMINELS and e >= 1:
                        self.criminels[_entier(x["location"])] = (n, e)
        if isinstance(sd.get("fonctions_exigees"), list):
            # fonctions du patch (format 14) : bits de `compiles` que le jeu doit publier (inconnu : exigé quand même,
            # la partie sera refusée par un jeu qui ne le publie pas)
            self.fonctions = {_entier(x) for x in sd["fonctions_exigees"] if 0 <= _entier(x) < 31}
            # fonctions ÉTENDUES (n° >= 32 : bits de ApPnj::fonctions, boite_protocole) ; le n° 22 qui les accompagne
            # (jamais publié : refus d'un client plus ancien) reste dans `fonctions` et est retiré à la vérification
            self.fonctions_etendues = {_entier(x) for x in sd["fonctions_exigees"]
                                       if _entier(x) >= bp.FONCTION_ETENDUE_BASE}
            self.requetes_transfert = bp.FONCTION_TRANSFERT in self.fonctions_etendues
        if isinstance(sd.get("objectif_medailles"), list):
            # V3, lot 3 : n° du Médaillium exigés par l'objectif (un boss = un n° ; graine antérieure : aucun)
            self.objectif_medailles = tuple(sorted({_entier(n) for n in sd["objectif_medailles"]
                                                    if 0 < _entier(n) < rando.TAILLE_MEDAILLIUM * 8}))
            # V3, lot 18 : seuil (objectif « medaillium_complet ») ; absent ou invalide : tous les n° (comme avant)
            s = sd.get("objectif_seuil")
            if isinstance(s, int) and not isinstance(s, bool) and 1 <= s <= len(self.objectif_medailles):
                self.objectif_seuil = s
        if isinstance(sd.get("blasters"), list):
            self.blasters = {}
            for x in sd["blasters"]:
                if isinstance(x, dict) and "location" in x and 0 < _entier(x.get("terrain", 0)) < 32:
                    self.blasters[_entier(x["location"])] = _entier(x["terrain"])
        if isinstance(sd.get("evenement_places"), list):
            self.evenement_places = {}
            for x in sd["evenement_places"]:
                if isinstance(x, dict) and "bit" in x and "objet" in x and 0 <= _entier(x["bit"]) < bp.EV_NOMBRE \
                        and _entier(x["objet"]) > 0:
                    self.evenement_places[_entier(x["bit"])] = _entier(x["objet"])
        if isinstance(sd.get("invites"), list):
            # invités de l'Auberge des voyageurs : le jeu ne montre que ceux que le client déclare ; une graine sans
            # ce champ (toute graine antérieure) n'en a aucun : rien n'est jamais écrit dans la zone des invités
            # (une graine de la V2 a 31 entrées au plus : la limite à 64 de la V3 ne change rien pour elle)
            self.invites = []
            for x in sd["invites"][:bp.CAP_INVITES_V3]:
                if isinstance(x, dict) and all(k in x for k in ("location", "medaille", "param")) \
                        and isinstance(x.get("locations"), list):
                    n = _entier(x["medaille"])
                    if 0 < n < rando.TAILLE_MEDAILLIUM * 8:
                        # (la clé `taux` d'une entrée est ignorée : lot 20, plus de taux relevé à l'Auberge)
                        self.invites.append(Invite(_entier(x["location"]), n, _entier(x["param"]) & 0xFFFFFFFF,
                                                   str(x.get("declencheur", "")),
                                                   frozenset(_entier(l) for l in x["locations"]),
                                                   _entier(x.get("objet", 0))))
            # ordre d'arrivée : « reception » seulement si la graine le dit (clé absente d'une graine de la V2)
            self.invites_ordre = ORDRE_INVITES_RECEPTION if sd.get("invites_ordre") == ORDRE_INVITES_RECEPTION \
                else ORDRE_INVITES_LISTE
        if isinstance(sd.get("quetes"), list):
            # requêtes et services (format 6) : check = phase 255 (même lecture que les boss de quête) ; contenu =
            # ce que l'écran de résultat montre à la place de la récompense (table des récompenses, boîte v5)
            for loc in list(self.recompenses):
                self.quetes.pop(loc, None)
            self.recompenses = {}
            for x in sd["quetes"]:
                if not isinstance(x, dict) or "location" not in x or "quete" not in x:
                    continue
                n, loc = _entier(x["quete"]), _entier(x["location"])
                if not 0 <= n < bp.NB_QUETES:
                    continue
                self.quetes[loc] = n
                self.recompenses[loc] = Recompense(loc, n, bool(x.get("service")))
                if "hachage" in x:
                    self.contenus[loc] = Contenu(bool(x.get("propre")), _entier(x["hachage"]) & 0xFFFFFFFF,
                                                 x.get("texte"))
        if isinstance(sd.get("boutiques"), list):
            # boutiques (format 15) : check = bit persistant « premier achat fait » (ou évènement ACHAT) ; contenu =
            # ce que la boutique montre à la place de l'article jusqu'au premier achat (table des boutiques, jeu v9)
            self.boutiques = {}
            for x in sd["boutiques"]:
                if not isinstance(x, dict) or "location" not in x or "bit" not in x:
                    continue
                loc, bit = _entier(x["location"]), _entier(x["bit"])
                if not 0 <= bit < bp.BOUTIQUE_BITS:
                    continue
                # format 17 : code de la boutique + rangs des entrées (hachage lu dans la ROM du joueur) ; format 15/16
                # (graine plus ancienne) : hachages donnés par slot_data, encore acceptés
                code, ents = x.get("boutique"), x.get("entrees")
                if isinstance(code, str) and isinstance(ents, list) and ents:
                    nb = x.get("nb_entrees")
                    self.boutiques[loc] = Boutique(loc, (), bit, code, tuple(_entier(e) for e in ents),
                                                   _entier(nb) if nb is not None else None)
                else:
                    arts = tuple(_entier(a) & 0xFFFFFFFF for a in (x.get("articles") or []) if _entier(a))
                    if not arts:
                        continue
                    self.boutiques[loc] = Boutique(loc, arts, bit)
                if "hachage" in x:
                    self.contenus[loc] = Contenu(bool(x.get("propre")), _entier(x["hachage"]) & 0xFFFFFFFF,
                                                 x.get("texte"))
        if isinstance(sd.get("distributeurs"), list):
            # V3, lot C1 : distributeurs (check = évènement DISTRIBUTEUR ; contenu montré à la place de la boisson)
            self.distributeurs = distrib.lire_slot_data(sd)[0]
            for loc, x in self.distributeurs.items():
                if x["contenu"] is not None:
                    self.contenus[loc] = Contenu(*x["contenu"])
        sp = sd.get("spots_objets_cles")
        if isinstance(sp, dict):
            self.spots = {_entier(k): _entier(v) for k, v in sp.items()}
        elif isinstance(sp, list):
            self.spots = {_entier(x["bit"]): _entier(x["location"]) for x in sp if isinstance(x, dict)}
        for cle_dons in ("dons", "objets"):
            for k, o in (sd.get(cle_dons) or {}).items():
                if isinstance(o, dict):
                    self.objets[_entier(k)] = self._don(o)
        for k, q in (sd.get("quantites") or {}).items():
            k = _entier(k)
            if k in self.objets:
                o = self.objets[k]
                self.objets[k] = ObjetADonner(o.type, o.hash, _entier(q))
        if "tunnel_sans_limite" in sd:
            self.tunnel_sans_limite = bool(sd["tunnel_sans_limite"])
        if "pieces_speciales" in sd:             # lot 20 : seul `true` active (clé absente = non)
            self.pieces_speciales = sd["pieces_speciales"] is True
            ordre = sd.get("pieces_ordre")
            try:
                bp.ordre_pieces(ordre if isinstance(ordre, list) else [])
                self.pieces_ordre = tuple(int(n) for n in ordre)
            except (ValueError, TypeError):
                self.pieces_ordre = ()               # graine sans ordre lisible : refusée (`_verifier_verrous`)
        if "photos_blasters" in sd:              # lot 21 : seul `true` active (clé absente = non)
            self.photos_blasters = sd["photos_blasters"] is True
        if "blasters_autres_editions" in sd:     # ap/blasters-terrains-apworld : seul `true` active
            self.blasters_editions = sd["blasters_autres_editions"] is True
        if "train_dore" in sd:                   # lot 22 : 2, 3 ou 4 ; toute autre valeur : 1 (jeu d'origine)
            self.train_dore = sd["train_dore"] if sd["train_dore"] in (2, 3, 4) and \
                not isinstance(sd["train_dore"], bool) else 1
        if "amitie" in sd:                       # lot 16 : absente (graine d'avant, ou réglage normal) = taux du jeu
            self.amitie = bp.reglage_amitie(sd["amitie"])
        for cle_o in ("revanches_sans_limite", "tirage_dirige_voie"):   # lot 17 : seul `true` active (clé absente = non)
            if cle_o in sd:
                setattr(self, cle_o, sd[cle_o] is True)
        if "deathlink_orge" in sd:
            self.deathlink_orge = bool(_entier(sd["deathlink_orge"]))
        if isinstance(sd.get("verrous_actifs"), list):
            self.verrous, self.verrous2, self.verrous3 = {}, {}, {}
            self.exemplaires3 = {}
            for v in sd["verrous_actifs"]:
                if not isinstance(v, dict) or not verrou_code_jeu(v):
                    continue
                objet = _entier(v.get("objet", self.cles.get(v.get("cle"), 0)))
                if isinstance(v.get("k"), int) and bp.VERROU3_BASE <= v["k"] < bp.VERROU3_BASE + bp.CAP_VERROUS3:
                    if objet:
                        self.verrous3[v["k"]] = objet    # V3, lot 9 : deuxième zone étendue (ApVerrous3)
                        n = v.get("exemplaires")
                        if isinstance(n, int) and not isinstance(n, bool) and n > 1:
                            self.exemplaires3[v["k"]] = n   # Mirapo de poche : 2e exemplaire de son objet
                    continue
                if isinstance(v.get("k"), int) and bp.VERROU2_BASE <= v["k"] < bp.VERROU2_BASE + bp.CAP_VERROUS2:
                    if objet:
                        self.verrous2[v["k"]] = objet    # V3 : verrou étendu (zone ApVerrous2)
                    continue
                if isinstance(v.get("k"), int) and 0 <= v["k"] < bp.CAP_VERROUS:
                    k = v["k"]                           # verrou sans spot (rangs de montre : k = 18, progressif)
                else:
                    bit = v3.SPOTS_PAR_DEFAUT.get(v.get("cle"))
                    k = None if bit is None else bit - bp.TBOX_SPOT_PREMIER
                if k is not None and objet:
                    self.verrous[k] = objet
        for cle_v in ("hachage_vitrine", "vitrine"):
            if sd.get(cle_v):
                self.vitrine = _entier(sd[cle_v]) & 0xFFFFFFFF
        if "politique_reessai" in sd:
            p = sd["politique_reessai"]
            self.politique_reessai = p != "ignorer" if isinstance(p, str) else bool(p)
        if sd.get("langue_notifications") in ("fr", "en"):
            self.langue = sd["langue_notifications"]
        if isinstance(sd.get("avant_chapitre_10"), list):
            self.avant_chapitre_10 = {_entier(x) for x in sd["avant_chapitre_10"]}
        if "yokai_zones" in sd:
            self.yokai_zones = sd["yokai_zones"] if isinstance(sd["yokai_zones"], dict) else None
        ry = sd.get("rando_yokai")
        # la VERSION du mélange vient de la graine (« <mode>#<n> », sans suffixe = 1 : graines d'avant le format 23,
        # même calcul qu'avant, archipelago_rando_yokai.md §20) ; version inconnue : gardée telle quelle, refusée au
        # calcul (jamais un autre algorithme à la place)
        mv = rando.mode_et_version(ry.get("mode")) if isinstance(ry, dict) else None
        if isinstance(ry, dict):
            self.rando_yokai_inconnu = None
        if mv is not None and mv[0] != "aucun":
            self.rando_yokai = {"mode": mv[0], "graine": _entier(ry.get("graine", 0)) & 0x7FFFFFFF, "melange": mv[1]}
            if mv[1] >= 5 and ry.get("apres_jeu") is True:
                # version 5 (« partout ») : périmètre avec les rencontres sauvages d'après-jeu (graine à l'après-jeu
                # activé) ; ignoré avant la version 5
                self.rando_yokai["apres_jeu"] = True
        elif isinstance(ry, dict):
            self.rando_yokai = None
            if ry.get("mode") != "aucun":
                self.rando_yokai_inconnu = str(ry.get("mode"))
        rb = sd.get("rando_boss")
        # version 1 (V2 publiée) : mode et graine, mélange calculé ici ; version 2 (V3, lot 10 : mode « <mode>#2 ») :
        # la permutation est portée par la graine (`sigma`, `sigma_n`), contrôlée sur la ROM puis appliquée ; mode ou
        # version inconnus : aucun mélange, jamais un autre calcul (et la graine porte le n° client 69 : refus avant)
        mvb = rboss.mode_et_version(rb.get("mode")) if isinstance(rb, dict) else None
        if isinstance(rb, dict):
            self.rando_boss_inconnu = None
        if mvb is not None and mvb[0] != "aucun":
            self.rando_boss = {"mode": mvb[0], "graine": _entier(rb.get("graine", 0)) & 0x7FFFFFFF}
            if mvb[1] >= rboss.VERSION_GRAINE:
                self.rando_boss.update(version=mvb[1], sigma=rb.get("sigma"), sigma_n=rb.get("sigma_n"))
        elif isinstance(rb, dict):
            self.rando_boss = None
            if rb.get("mode") != "aucun":
                self.rando_boss_inconnu = str(rb.get("mode"))
        if isinstance(rb, dict):
            # V3 : force des boss adaptée (clé présente seulement si l'option est activée) ; le boss d'un objectif
            # « battre X » n'est jamais adapté, même si la graine ne le liste pas (`rboss.exclus_force`)
            rf = sd.get("rando_boss_force")
            self.rando_boss_force, self.rando_boss_force_inconnu = None, None
            if isinstance(rf, dict) and rf.get("mode") in rboss.FORCES \
                    and _entier(rf.get("version", rboss.VERSION_FORCE)) == rboss.VERSION_FORCE:
                if rf["mode"] != "d_origine":
                    ex = rf.get("exclus")
                    self.rando_boss_force = {"mode": rf["mode"], "exclus": rboss.exclus_force(
                        sd.get("objectif"), ex if isinstance(ex, list) else ())}
            elif rf is not None:
                self.rando_boss_force_inconnu = str(rf)[:80]
        if "death_link" in sd:
            self.death_link = bool(_entier(sd["death_link"]))
        if "bingo_kai_infini" in sd:
            self.bingo_kai_infini = bool(_entier(sd["bingo_kai_infini"]))

    def locations_anim(self) -> set[int]:
        """Locations dont le check n'a AUCUN affichage dans le jeu (fenêtre « objet obtenu », toujours active, sans option :
        décision de l'humain du 2026-09-30) : boss d'histoire et de quête, fins de chapitre, Montée de rang, Vélo (entrées
        de `boss`), Tablo-blabla, et (décision de l'humain, 2026-10-01 puis précisée le 2026-10-02) les SERVICES
        (`recompenses` à `service` vrai), les amis et (décision de l'humain du 2026-10-07) les Yo-criminels (la scène
        d'arrestation ne montre pas l'objet AP). Pas les requêtes (écran de résultat). Jamais un coffre, un spot d'objet-clé (don de script substitué : fenêtre du jeu) ni un article de
        boutique (montré dans la boutique), SAUF un don de script substitué que le jeu d'origine fait sans fenêtre
        (`bp.DONS_SANS_FENETRE` : Yo-kai Watch, `AddItem(…, 0)`, gros test V3 du 2026-10-22) : sans cela le joueur ne
        voyait pas ce qu'il avait obtenu. Non substitué (objet d'origine donné, verrou seul) : rien, comme le jeu."""
        requetes = {loc for loc, r in self.recompenses.items() if not r.service}     # aussi dans `quetes` (phase 255)
        s = set(self.boss) | set(self.quetes) | set(self.tablos) | set(self.amis)   # `quetes` contient les services
        s |= {inv.location for inv in self.invites}                                 # invités de l'Auberge : amis
        s |= set(self.criminels)                                                    # Yo-criminels arrêtés
        exclus = set(self.coffres) | set(self.emplacements) | set(self.boutiques) | requetes
        exclus |= set(self.spots.values())
        return (s - exclus) | self.dons_sans_fenetre()

    def dons_sans_fenetre(self) -> set[int]:
        """Emplacements dont le don de script est SUBSTITUÉ et fait sans fenêtre dans le jeu d'origine (un de leurs
        hachages d'origine dans `bp.DONS_SANS_FENETRE`) : leur check reçoit la fenêtre « objet obtenu » de la file ApAnim.
        Ne dépend que de champs d'`emplacements` déjà publiés (graines générées avant ce correctif comprises)."""
        return {loc for loc, e in self.emplacements.items()
                if e.substituer and not bp.DONS_SANS_FENETRE.isdisjoint(e.hachages or (e.hachage_origine,))}

    def don(self, item: int) -> ObjetADonner:
        """Don correspondant à un objet AP ; objet inconnu : type 0 (le jeu l'ignore et avance son compteur,
        code TYPE_INCONNU), pour ne pas bloquer la file."""
        return self.objets.get(item, ObjetADonner(0, 0, 0))

    @property
    def services(self) -> set[int]:
        """N° de quête des services de la graine (phase 255 transitoire)."""
        return {r.quete for r in self.recompenses.values() if r.service}

    @property
    def index_vers_location(self) -> dict[int, int]:
        return {i: loc for loc, i in self.coffres.items()}


# ================================================================================================ liaison (v4)
def raison_non_neuve(h, ouverts: set[int], indices_ap: Iterable[int],
                     boss_vaincus: Iterable[int] = (), quetes_finies: Iterable[int] = (),
                     tablos_appeles: Iterable[int] = ()) -> str | None:
    """None si la sauvegarde chargée est une PARTIE NEUVE (liaison automatique permise), sinon la raison.

    Critères (tous exigés ; justification dans archipelago_boite.md §11.3) :
    - aucun identifiant (P+0x3BC == 0) : jamais liée à une partie AP ;
    - compteur de dons (P+0x3B8) à 0 : n'a jamais reçu d'objet d'Archipelago ;
    - chapitre connu (structure de scénario présente) et chapitre 0, ou chapitre 1 avec un pas de scénario
      < 100 (phase d'index 16 de `phase_set_c01` : don du Filet, premier objet-clé mélangé) ;
    - ni « partie terminée » ni après-jeu ;
    - aucun bit de spot d'objet-clé (TBox 558..575) ;
    - aucun coffre d'Archipelago (index TBox de la graine) déjà ouvert ;
    - aucun boss de la graine déjà vaincu (redondant avec le chapitre : le premier boss est au chapitre 3), ni
      aucune quête (boss de quête, requête, service) de la graine déjà terminée (redondant : la première apparaît au
      chapitre 2), ni aucun Tablo-blabla de la graine déjà appelé (redondant : aucun panneau avant le chapitre 2).
    Le jeu v4 revérifie identifiant, compteur, chapitre et spots avant une clé automatique (apLiaison)."""
    if h.ident_sauvegarde:
        return "identifiant déjà présent"
    if h.compteur:
        return f"{h.compteur} don(s) déjà reçu(s)"
    if not h.progression & bp.PROGRESSION_CHAPITRE:
        return "chapitre inconnu"
    if h.progression & VICTOIRE:
        return "partie terminée"
    if h.chapitre > 1 or (h.chapitre == 1 and h.pas_scenario >= bp.PAS_NEUVE):
        return f"chapitre {h.chapitre}, pas {h.pas_scenario}"
    if h.spots:
        return "objet-clé déjà obtenu"
    deja = ouverts & set(indices_ap)
    if deja:
        return f"{len(deja)} coffre(s) AP déjà ouvert(s)"
    boss = set(boss_vaincus)
    if boss:
        return f"{len(boss)} boss déjà vaincu(s)"
    quetes = set(quetes_finies)
    if quetes:
        return f"{len(quetes)} quête(s) déjà terminée(s)"
    tablos = set(tablos_appeles)
    if tablos:
        return f"{len(tablos)} Tablo-blabla déjà appelé(s)"
    return None


@dataclass
class Liaison:
    """Instantané pris à la liaison d'une sauvegarde : bits de victoire déjà présents (la victoire ne compte que si
    elle apparaît après), et ensembles EXCLUS (jamais envoyés comme checks) : toujours vides depuis G1-2 (liaison
    automatique : partie neuve, rien de fait ; liaison MANUELLE : les checks déjà faits sont envoyés), sauf pour une
    sauvegarde liée par un client v3 (clé 0, « premiere_vue ») ; un instantané manuel antérieur qui excluait des
    checks est vidé à son chargement (`Synchro._liaison_manuelle`).
    Historique des champs : `boss` (`quetes`) None : instantané pris par un client sans boss (sans boss de
    quête), complété à la première vue (`Synchro._charger_liaison`). `secours` : bits de spot dont le don avait
    déjà été fait SANS table à la liaison (détection de secours, `bp.SPOTS_SECOURS`), exclus comme `exclus` ; None :
    instantané d'un client sans détection de secours, complété de la même façon. `tablos` : flags « Yo-kai appelé »
    des Tablo-blabla déjà posés à la liaison ; None : instantané d'un client sans Tablo-blabla, complété de même."""
    exclus: set[int] = field(default_factory=set)
    progression: int = 0
    manuelle: bool = False
    origine: str = "auto"          # auto (partie neuve), manuelle (écran, X), premiere_vue (liaison sans instantané)
    boss: set[int] | None = None   # flags bit globaux de boss déjà posés à la liaison
    quetes: set[int] | None = None  # quêtes de boss déjà terminées (phase 255) à la liaison
    secours: set[int] | None = None  # bits de spot vus par la seule détection de secours à la liaison
    tablos: set[int] | None = None   # flags « Yo-kai appelé » des Tablo-blabla déjà posés à la liaison
    # n° de quête lus pour l'instantané `quetes` (None : instantané d'un client sans requêtes, qui ne lisait que les
    # quêtes de boss) ; une quête hors de cet ensemble est complétée à la première vue (`Synchro._couvrir_quetes`)
    quetes_couvertes: set[int] | None = None
    # bandeau du chapitre 10 déjà montré (ou devenu sans objet : victoire, aucun check restant) pour cette sauvegarde
    alerte_ch10: bool = False
    # n° du Médaillium déjà amis / n° des Yo-criminels déjà arrêtés à la liaison (exclus) ; None : instantané d'un client
    # sans amis / Yo-criminels, complété à la première lecture (`Synchro._completer_instantane`) : vide pour une liaison
    # automatique (partie neuve) ou manuelle (G1-2), ce qui est déjà fait à la première vue sinon
    amis: set[int] | None = None
    criminels: set[int] | None = None
    # bits de boutique (premier achat fait) déjà posés à la liaison (exclus) ; None : instantané d'un client sans
    # boutiques, complété à la première lecture comme `amis` / `criminels`
    boutiques: set[int] | None = None
    # n° du Médaillium des invités de l'Auberge dont l'annonce a déjà été montrée pour cette sauvegarde (évènement
    # INVITE du journal) : jamais remontrée, même après un relancement du jeu
    invites_annonces: set[int] = field(default_factory=set)
    # chambre de l'Auberge (1..9 = 101..109) que le JEU a attribuée à chaque invité (n° du Médaillium) dans cette
    # sauvegarde (évènement INVITE_CHAMBRE du journal) : réécrite dans la liste, l'invité la garde jusqu'à l'amitié,
    # d'un lancement à l'autre (archipelago_invites.md §18)
    invites_chambres: dict[int, int] = field(default_factory=dict)
    # terrains de Ψ Blasters déjà finis à la liaison (exclus) ; None : instantané d'un client sans ces checks, complété
    # à la première lecture comme `amis`
    blasters: set[int] | None = None

    def exclus_tous(self) -> set[int]:
        return self.exclus | (self.secours or set())


class RegistreLiaisons:
    """Instantanés des liaisons, par (identifiant de partie, clé de liaison P+0x3B6), dans `liaisons.json` du
    dossier du client (la sauvegarde n'a pas de place pour 576 bits : seuls 2 octets libres, P+0x3B6, gardent la
    clé, bit 15 = liaison manuelle)."""

    def __init__(self, dossier: Path, journal: logging.Logger | None = None):
        self.fichier = Path(dossier) / FICHIER_LIAISONS
        self.log = journal or logging.getLogger("ykw2ap.synchro")

    @staticmethod
    def cle(ident: int, cle_liaison: int) -> str:
        return f"{ident & 0xFFFFFFFF:08x}:{cle_liaison & 0xFFFF:04x}"

    def _tout(self) -> dict:
        try:
            d = json.loads(self.fichier.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            self.log.warning("Liaisons illisibles (%s) : ignorées", e)
            return {}

    def lire(self, ident: int, cle_liaison: int) -> Liaison | None:
        e = self._tout().get(self.cle(ident, cle_liaison))
        if not isinstance(e, dict):
            return None
        boss, quetes, secours, tablos = e.get("boss"), e.get("quetes"), e.get("secours"), e.get("tablos")
        couvertes = e.get("quetes_couvertes")
        amis, criminels, boutiques = e.get("amis"), e.get("criminels"), e.get("boutiques")
        return Liaison({int(x) for x in e.get("exclus", [])}, int(e.get("progression", 0)),
                       bool(e.get("manuelle")), str(e.get("origine", "auto")),
                       None if boss is None else {int(x) for x in boss},
                       None if quetes is None else {int(x) for x in quetes},
                       None if secours is None else {int(x) for x in secours},
                       None if tablos is None else {int(x) for x in tablos},
                       None if couvertes is None else {int(x) for x in couvertes},
                       bool(e.get("alerte_ch10")),
                       None if amis is None else {int(x) for x in amis},
                       None if criminels is None else {int(x) for x in criminels},
                       None if boutiques is None else {int(x) for x in boutiques},
                       {int(x) for x in e.get("invites_annonces", [])},
                       {int(k): int(v) for k, v in (e.get("invites_chambres") or {}).items()
                        if str(k).isdigit() and isinstance(v, int) and 0 < v < bp.INVITES_PIECES},
                       None if e.get("blasters") is None else {int(x) for x in e["blasters"]})

    # Ordre d'ARRIVÉE des invités de l'Auberge (lot 14), par PARTIE et non par sauvegarde : la liste des objets reçus
    # est celle du slot, et les rangs de la liste du jeu doivent être les mêmes pour toutes les sauvegardes liées à
    # la partie (mémoire `garde` du jeu, par rang et par identifiant de partie). Clé « <ident>:invites », qui ne peut
    # pas être celle d'une liaison (« <ident>:<4 chiffres hexadécimaux> ») ; un client d'avant la garde sans la lire.
    @staticmethod
    def cle_invites(ident: int) -> str:
        return f"{ident & 0xFFFFFFFF:08x}:invites"

    def lire_ordre_invites(self, ident: int) -> list[int]:
        e = self._tout().get(self.cle_invites(ident))
        ordre = e.get("ordre") if isinstance(e, dict) else None
        out: list[int] = []
        for x in ordre if isinstance(ordre, list) else []:
            if isinstance(x, int) and not isinstance(x, bool) and 0 < x < 512 and x not in out:
                out.append(x)
        return out

    def ecrire_ordre_invites(self, ident: int, ordre: list[int]) -> None:
        d = self._tout()
        d[self.cle_invites(ident)] = {"ordre": list(ordre), "date": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            self.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.fichier.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.fichier)
        except OSError as e:
            self.log.warning("Ordre d'arrivée des invités non enregistré : %s", e)

    # Objectif atteint, par PARTIE (pièges §14) : clé « <ident>:victoire », jamais remise à faux (une victoire envoyée
    # au serveur ne se retire pas) ; un client d'avant ne la lit pas.
    @staticmethod
    def cle_victoire(ident: int) -> str:
        return f"{ident & 0xFFFFFFFF:08x}:victoire"

    def lire_victoire(self, ident: int) -> bool:
        e = self._tout().get(self.cle_victoire(ident))
        return isinstance(e, dict) and e.get("victoire") is True

    def ecrire_victoire(self, ident: int) -> None:
        d = self._tout()
        if isinstance(d.get(self.cle_victoire(ident)), dict) and d[self.cle_victoire(ident)].get("victoire") is True:
            return
        d[self.cle_victoire(ident)] = {"victoire": True, "date": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            self.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.fichier.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.fichier)
        except OSError as e:
            self.log.warning("Victoire de la partie non enregistrée : %s", e)

    def ecrire(self, ident: int, cle_liaison: int, l: Liaison) -> None:
        d = self._tout()
        e = {"exclus": sorted(l.exclus), "progression": l.progression, "manuelle": l.manuelle,
             "origine": l.origine, "date": time.strftime("%Y-%m-%d %H:%M:%S")}
        if l.boss is not None:
            e["boss"] = sorted(l.boss)
        if l.quetes is not None:
            e["quetes"] = sorted(l.quetes)
        if l.secours is not None:
            e["secours"] = sorted(l.secours)
        if l.tablos is not None:
            e["tablos"] = sorted(l.tablos)
        if l.quetes_couvertes is not None:
            e["quetes_couvertes"] = sorted(l.quetes_couvertes)
        if l.alerte_ch10:
            e["alerte_ch10"] = True
        if l.amis is not None:
            e["amis"] = sorted(l.amis)
        if l.criminels is not None:
            e["criminels"] = sorted(l.criminels)
        if l.boutiques is not None:
            e["boutiques"] = sorted(l.boutiques)
        if l.invites_annonces:
            e["invites_annonces"] = sorted(l.invites_annonces)
        if l.invites_chambres:
            e["invites_chambres"] = {str(k): v for k, v in sorted(l.invites_chambres.items())}
        if l.blasters is not None:
            e["blasters"] = sorted(l.blasters)
        d[self.cle(ident, cle_liaison)] = e
        try:
            self.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.fichier.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.fichier)
        except OSError as e:
            self.log.warning("Liaison non enregistrée : %s", e)


# ================================================================================================ synchro
@dataclass
class Statistiques:
    cycles: int = 0
    instances: int = 0
    depots: int = 0
    checks_envoyes: int = 0
    notifications: int = 0
    tables_ecrites: int = 0
    publications: int = 0
    erreurs_gdb: int = 0
    liaisons: int = 0
    cycles_suivi: int = 0                  # tours sans le jeu (suivi seul : aucun paquet GDB)


class Synchro:
    """Boucle du client invisible. `executer()` ne rend la main qu'à l'arrêt (`arreter()`)."""

    def __init__(self, pont: PontGdb, stockage: StockageConfig, config: ConfigLocale | None = None, *,
                 catalogue: Catalogue | None = None, disposition: v3.DispositionV3 | None = None,
                 periode: float | None = None, periode_filet: float | None = None,
                 periode_resync: float | None = None, echelle: float = 1.0,
                 options_reseau: dict | None = None,
                 fabrique_client: Callable[..., ClientAP] | None = None, journal: logging.Logger | None = None,
                 attacher_jeu: bool = True):
        self.pont = pont
        # suivi seul (lanceur, sans Azahar) : réseau seulement, AUCUN paquet GDB (ni connexion au stub) tant que
        # `attacher_jeu()` n'a pas été appelé ; `detacher_jeu()` y revient (Azahar fermé)
        self.jeu_attache = attacher_jeu
        self.boite = Boite(pont)
        self.zone = v3.ZoneConnexion(self.boite, disposition)
        self.stockage = stockage
        self.config = config or stockage.charger()
        self.catalogue_base = catalogue or Catalogue.charger()
        self.catalogue = self._copie_catalogue()
        # fréquence de lecture : régime de config.json (`lecture`), paramètres explicites prioritaires ; `echelle`
        # multiplie toutes les durées (tests et mesures en temps accéléré, archipelago/tests/charge_gdb.py)
        self.lecture = self.config.lecture if self.config.lecture in REGIMES_LECTURE else LECTURE_DEFAUT
        regime = REGIMES_LECTURE[self.lecture]
        self.echelle = echelle
        self.periode = periode if periode is not None else regime["periode"] * echelle
        filet = periode_filet if periode_filet is not None else periode_resync
        self.periode_filet = filet if filet is not None else regime["filet"] * echelle
        self.options_reseau = dict(options_reseau or {})
        self.fabrique_client = fabrique_client or ClientAP
        self.log = journal or logging.getLogger("ykw2ap.synchro")
        self.liaisons = RegistreLiaisons(stockage.dossier, self.log)
        # lieu du joueur (carte courante, position) recopié de l'en-tête dans lieu.json pour le sous-onglet « Carte »
        # du lanceur : aucun paquet GDB, écritures bornées (lieu_local.py)
        self.lieu = ll.SuiviLieu(stockage.dossier)
        # ennemis du combat en cours et « déjà ami » (fenêtre d'amitié du lanceur) : zone lue seulement quand le
        # numéro publié dans l'en-tête change pendant un combat (amis_combat.py)
        self.amis_combat = amc.SuiviAmisCombat(stockage.dossier)
        # point visé par le radar de la loupe et « déjà ami » (fenêtre de la loupe du lanceur) : zone lue seulement
        # quand le numéro publié dans l'en-tête change et que le radar vise un point (loupe_amis.py)
        self.loupe_amis = lpa.SuiviLoupe(stockage.dossier)
        # connexion : saisie du lanceur (config_locale) ; révision de config.json appliquée
        self._rev_locale = self.config.revision_connexion
        self._signature_config = stockage.signature()
        self.periode_config = PERIODE_CONFIG * echelle
        self.raison_non_liee = ""              # sauvegarde non liée : pourquoi ce n'est pas une partie neuve (etat.json)
        self.stats = Statistiques()
        self._noms_perdus = None               # (instance, noms voulus, places) déjà signalé (table des noms trop petite)
        self._arret = asyncio.Event()
        # réseau
        self.reseau: ClientAP | None = None
        self._tache_reseau: asyncio.Task | None = None
        self._taches: set[asyncio.Task] = set()
        self._deja_connecte = False            # avec la configuration courante
        self._refus: list[str] = []
        self._connexion_prete = False          # slot_data appliqué, identifiant connu
        self.ident_partie: int | None = None
        self.objets: list[ObjetReseau] = []
        self._scout: dict[int, ObjetReseau] = {}
        self._scout_fait = False
        self._definitions_vues = None          # instance du jeu qui publie les définitions d'affichage (§21)
        self._victoire_envoyee = False
        self._victoire_memoire: dict[int, bool] = {}   # partie -> victoire retenue (liaisons.json, pièges §14)
        self._checks_empreinte: str | None = None   # dernier checks.json écrit (aucune écriture s'il n'a pas changé)
        self._indices_empreinte: str | None = None  # dernier indices.json écrit (idem)
        # discussion (onglet « Discussion » du lanceur) : journal des messages et commandes du lanceur
        self.session_chat = secrets.token_hex(8)
        self.journal_chat = ch.JournalMessages(stockage.dossier, self.session_chat)
        self.commandes_chat = ch.SuiviCommandes(stockage.dossier, self.session_chat)
        # fenêtre des derniers objets du lanceur : objets reçus / envoyés par ce slot, tirés des mêmes PrintJSON
        self.derniers_objets = dobj.JournalDerniersObjets(stockage.dossier, self.session_chat,
                                                         planifier=self._planifier_ecriture)
        self.periode_chat = PERIODE_CHAT * echelle
        self._noms_cle: tuple | None = None     # dernier chat_noms.json écrit (autocomplétion de la console)
        self._noms_essais = 0
        # jeu
        self._instance = 0
        self._instance_preparee = -1
        self._publie: v3.EtatConnexion | None = None
        self._message_bandeau = False
        self._table_ecrite: tuple | None = None
        self._config_ecrite: tuple | None = None
        self._depot_cle: tuple | None = None
        self._depot_t = 0.0
        self._resync_t = 0.0
        self._resync_demandee = True
        self._victoire_t = 0.0
        self._spots_vus = -1
        self._progression_vue: tuple | None = None   # (chapitre, pas, terrain) : un changement relit les boss
        self._verrous_ecrits: tuple | None = None
        self._verrous_compiles: tuple[int, int | None] | None = None   # (instance, masque publié par le jeu)
        # invités de l'Auberge des voyageurs : bits compilés lus une fois par instance (seulement si la graine a des
        # invités), dernière liste écrite, séquence de la zone, dernier état écrit dans invites.json
        self._invites_compiles: tuple[int, int | None] | None = None
        self._etendues_compilees: tuple[int, int | None] | None = None   # (instance, bits de ApPnj::fonctions)
        self._invites_ecrits: tuple | None = None
        self._invites_seq = 0
        self._invites_fichier: tuple | None = None
        # lot 14 : bits de ApInvites2 (liste à 64, taux par invité) lus une fois par instance, seulement si la graine
        # en a besoin ; ordre d'arrivée des invités de la partie (identifiant de partie, n° du Médaillium dans
        # l'ordre) : mémoire de liaisons.json, complétée en fin de liste seulement
        self._invites2_compiles: tuple[int, int | None] | None = None
        self._invites_arrivees: tuple[int, list[int]] | None = None
        self._evenement_ecrit: tuple | None = None       # (instance, masque, ident) de ApPnj::ev_declares écrit
        self._panique_vue: tuple[int, int] | None = None   # (instance, compte) de la dernière panique du jeu lue (§28)
        self.paniques: list[dict] = []        # paniques du jeu lues depuis le lancement du client (plantage.json)
        self.options_absentes: list[int] = []   # options du joueur choisies mais non compilées (avertissement)
        self._recompenses_etat: tuple[int, str] | None = None   # (instance, état de la substitution des récompenses)
        self._recompenses_montrees: set[int] = set()   # locations dont l'écran de résultat a montré l'objet (évènement)
        self._fenetres_en_amont: set[int] = set()      # dons substitués en amont (magasin, 1-86) : fenêtre du jeu vue
        self.verrous_manquants: list[int] = []  # verrous exigés par slot_data et absents du jeu (état refusé)
        # lot 17 : les mêmes, avec leur SORTE (« verrou », « fonction », « option » : les trois numérotations se
        # recouvrent, bp.nom_manquant) ; `verrous_manquants` reste la liste des n° seuls
        self.manquants_detail: list[tuple[str, int]] = []
        self._verrous2_compiles: tuple[int, int | None] | None = None   # V3 : (instance, ApVerrous2::compiles)
        self._verrous2_ecrits: tuple | None = None                      # V3 : dernière écriture de ApVerrous2
        self._verrous3_compiles: tuple[int, int | None] | None = None   # lot 9 : (instance, ApVerrous3::compiles)
        self._verrous3_ecrits: tuple | None = None                      # lot 9 : dernière écriture de ApVerrous3
        self._amitie_compilee: tuple[int, bool] | None = None           # lot 16 : (instance, ApAmitie publiée et compilée)
        # lot 20 : (instance, (bits PIECES_* compilés, options étendues 32.. compilées) ou None) ; dernière écriture de
        # ApPieces : (clé, {décalage: octets écrits})
        self._pieces_compile: tuple[int, tuple[int, int] | None] | None = None
        self._pieces_ecrites: tuple | None = None
        self._amitie_ecrite: tuple | None = None                        # lot 16 : dernière écriture de ApAmitie
        # v9 : la graine a des checks de boutique mais le jeu ne les a pas (jeu v8 ou antérieur, ou build --define
        # YKW2_AP_SANS_BOUTIQUES) : ces locations seraient impossibles -> même refus que des verrous manquants
        self.boutiques_manquantes = False
        self._boutiques_etat: tuple[int, str] | None = None     # (instance, « actives » / « non_compilees » / « jeu_ancien »)
        # locations de boutique déjà cochées sur le serveur quand la sauvegarde liée a été vue (instantané par sauvegarde :
        # la table n'est pas réécrite à chaque achat ; le jeu pose lui-même le bit et remet l'article d'origine)
        self._boutiques_faites: frozenset[int] | None = None
        self._boutiques_perdues = None          # (instance, articles voulus) déjà signalé (table des boutiques trop petite)
        self._boutiques_bits: set[int] = set()      # bits de boutique posés, lus par le dernier _lire_bits
        self._boutiques_ecrites: tuple | None = None   # (instance, entrées) de la dernière table des boutiques écrite
        # hachages des articles lus dans la ROM du joueur (format 17, `boutiques_local.json`) : état de la résolution
        # (« pretes », « calcul », « absente », « refusee ») et tâche de génération de la table locale
        self._boutiques_resolution = "pretes"
        self._boutiques_tache: asyncio.Task | None = None
        # indices automatiques des boutiques (évènement BOUTIQUE, archipelago_boutiques.md §10) : (graine, slot, location)
        # dont l'indice a été demandé au serveur (une seule fois par article ; retiré si la demande échoue)
        self._indices_boutiques: set[tuple[str, int, int]] = set()
        # V3, lot C1 : distributeurs de soda (client/distributeurs.py) : table de la boîte, évènements, refus
        self.distrib = distrib.SuiviDistributeurs(self)
        # V3, lot L1 : légendaires mélangés entre eux (client/legendaires.py) : zone ApLegendes, refus
        self.leg = leg.SuiviLegendaires(self)
        # ap/portails-donjon : récompense des coffres de fin de portail (client/portails.py) : zone ApPortails
        self.portails = portails.SuiviPortails(self)
        # V3, lot B1 : Bingo-kai aléatoire (client/bingo.py) : mélange calculé depuis la ROM, zone ApBingo
        self.bingo = bingo.SuiviBingo(self)
        # V3, lot 4 des pièges (client/pieges_suivi.py) : avertissement des pièges absents du patch, bandeaux,
        # mémoire des pièges reçus pas finis (liaisons.json) et reprise au lancement (zone ApPieges)
        self.pieges = pgs.SuiviPieges(self)
        # randomizer de Yo-kai (R3)
        self.rando_melange: rando.Melange | None = None
        self.rando_statut = "aucun"            # aucun | calcul | pret | refuse | base_absente
        self._rando_sans_p: int | None = None  # instance du jeu déjà signalée sans le mélange par rencontre (v10)
        self.rando_message = ""
        # V3, lot M1 : cause de l'état, en clair pour le lanceur (carte « Connexion ») : aucun, mode_inconnu,
        # version_inconnue, base_absente, base_calcul, base_erreur, refuse, pret ; puis, côté jeu (_suivre_rando) :
        # jeu_sans_rando, jeu_ancien, jeu_sans_extension, non_liee, retrait, ecrit
        self.rando_cause = "aucun"
        self._rando_cause_jeu = ""
        self._rando_cle: tuple | None = None   # (ident_partie, mode, graine) du mélange calculé
        self._rando_tache: asyncio.Task | None = None
        self._rando_jeu: tuple[int, int | None] | None = None   # (instance, masque publié : None = jeu sans v6)
        self._rando_fichier: tuple | None = None
        self._rando_attente_t = 0.0
        # randomizer des boss (v7)
        self.boss_melange: rboss.MelangeBoss | None = None
        self.boss_statut = "aucun"             # aucun | calcul | pret | refuse | base_absente
        self.boss_message = ""
        self._boss_cle: tuple | None = None    # (ident_partie, mode, graine) du mélange calculé
        self._boss_jeu: tuple[int, int | None] | None = None    # (instance, masque publié : None = jeu sans v7)
        self._boss_force_jeu = False           # le jeu de cette instance applique la table M (bit BOSS_FORCE)
        self._boss_force_averti: tuple | None = None   # (instance, génération) déjà signalée « force absente du jeu »
        self._boss_fichier: tuple | None = None
        self._boss_attente_t = 0.0
        self._boss_lu_cle: tuple | None = None
        self._boss_lu_t = 0.0
        self._boss_attente = False
        self._boss_valide_lu = 0               # `valide` lu en dernier (0 : rien à retirer dans le jeu)
        # version 2 (mélange tiré à la génération) : motif pour lequel le mélange de la graine n'est PAS appliqué
        # (un des STATUTS_BOSS_MANQUANT), None sinon ; tant qu'il est posé, rien n'est lié, livré ni envoyé
        self.boss_manquant: str | None = None
        # V3, lots M2b : mélange des Yo-kai de version 7 (zones) non appliqué : motif (STATUTS_YOKAI_MANQUANT) ou None
        self.yokai_manquant: str | None = None
        self._yokai_reessai_sig = None
        self._yokai_reessai_t = 0.0
        self._boss_reessai_t = 0.0
        self._boss_reessai_sig: tuple | None = None
        self._medaillium_t = 0.0
        self._medaillium: tuple | None = None
        self._progression_suivi: tuple | None = None   # (ident_sauvegarde, progression publiée) de la dernière lecture
        self._progression_fichier: tuple | None = None
        self._base_rafraichie = False                   # base locale d'un format antérieur : régénérée une fois
        # DeathLink (boîte v8, docs/systemes/archipelago_deathlink.md)
        self.deathlink = dl.EtatDeathLink()
        self._tag_deathlink = False            # tag « DeathLink » annoncé au serveur
        # fenêtre « objet obtenu » des checks sans affichage (§27)
        self.anims = ao.EtatAnims()
        self._battement = 0                    # client_images : +1 à chaque publication (aucune écriture pour lui seul)
        self._reveil = asyncio.Event()         # tour immédiat (dons reçus, connexion, arrêt)
        # lectures sur évènement (§23)
        self._journal_lu = 0                   # index de lecture du client (acquittement différé)
        self._acquitter_t = 0.0                # 0 : rien à acquitter ; sinon date de la première lecture non acquittée
        self._rando_lu_cle: tuple | None = None
        self._rando_lu_t = 0.0
        self._rando_attente = False            # écriture du mélange en cours : en-tête relu tous les TOURS_ATTENTE tours
        self._terrain_suivi: int | None = None
        self._adresse_q: int | None = None     # Q et O validés par la dernière relecture (chaînage relu après seulement)
        self._adresse_rang: int | None = None
        self._resync_echecs = 0
        self._bilan_t = 0.0
        self._bilan_stats: dict | None = None
        self._arrets_signales = False
        self._partie_cle: tuple | None = None
        self.sauvegarde = "aucune"             # aucune | attente | liee | liaison | non_liee | autre | jeu_ancien
        self._liaison: Liaison | None = None   # instantané de la sauvegarde liée chargée
        self._secours_seuls: set[int] = set()  # bits de spot du dernier _lire_bits vus par la seule détection de secours
        self._criminels_arretes: set[int] = set()   # n° des Yo-criminels arrêtés, lus par le dernier _lire_bits
        self._demande: tuple | None = None     # (terrain_numero, clé, numéro de demande) en attente
        self._eval_cle: tuple | None = None    # dernier état évalué d'une sauvegarde sans identifiant
        self._notif_sauvegarde: tuple | None = None
        self._echecs_notifies: set[int] = set()
        self.notifications: collections.deque[str] = collections.deque(maxlen=64)
        self.etat_publie: v3.EtatConnexion | None = None
        self.entete: Any = None

    # ------------------------------------------------------------------------------ cycle de vie
    async def executer(self) -> None:
        self.stockage.consommer_transmis()                 # mot de passe transmis par le lanceur : lu, effacé du disque
        if self.config.configuree:
            self._demarrer_reseau()
        self._lancer(self._surveiller_config())
        self._lancer(self._surveiller_chat())
        try:
            while not self._arret.is_set():
                if not self.jeu_attache:
                    self._suivi_sans_jeu()
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self._reveil.wait(), self.periode)
                    self._reveil.clear()
                    continue
                if not self.pont.connecte:
                    try:
                        await self.pont.connecter(arreter=lambda: self._arret.is_set() or not self.jeu_attache)
                    except Deconnecte:
                        if self._arret.is_set():
                            break
                        continue
                try:
                    await self.cycle()
                except Deconnecte as e:
                    self.log.info("Jeu déconnecté (%s) : attente d'un nouveau lancement", e)
                    self.stats.erreurs_gdb += 1
                    self.lieu.oublier()                    # plus de jeu : plus de lieu pour le lanceur
                    self.amis_combat.oublier()
                    self.loupe_amis.oublier()
                except (ArretNonConfirme, DelaiDepasse, AccesRefuse, BoiteAbsente) as e:
                    self.log.debug("Cycle interrompu : %s", e)
                    self.stats.erreurs_gdb += 1
                except ErreurGdb as e:
                    self.log.warning("Erreur GDB : %s", e)
                    self.stats.erreurs_gdb += 1
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._reveil.wait(), self.periode_effective())
                self._reveil.clear()
        finally:
            self.lieu.oublier()
            self.amis_combat.oublier()
            self.loupe_amis.oublier()
            if self.pont.connecte and self._acquitter_t:
                with contextlib.suppress(Exception):             # dernier acquittement du journal (au mieux)
                    await self.boite.acquitter_journal(self._journal_lu)
            self.derniers_objets.vider()                         # évènements regroupés pas encore écrits
            await self._arreter_reseau()
            for t in list(self._taches):
                t.cancel()

    @staticmethod
    def _planifier_ecriture(delai: float, fonction) -> object:
        return asyncio.get_running_loop().call_later(delai, fonction)

    def arreter(self) -> None:
        self._arret.set()
        self._reveil.set()

    # ------------------------------------------------------------------------------ suivi seul / jeu attaché
    def attacher_jeu(self) -> None:
        """« JOUER » dans le lanceur : le client de suivi attend maintenant le stub GDB d'Azahar (même connexion au
        serveur, même état : rien n'est refait)."""
        if self.jeu_attache:
            return
        self.jeu_attache = True
        self.log.info("Jeu attaché : attente du stub GDB sur %s:%d", self.pont.hote, self.pont.port)
        self.reveiller()

    async def detacher_jeu(self) -> None:
        """Azahar fermé : retour au suivi seul (connexion GDB fermée, état de la partie oublié ; le réseau continue)."""
        if not self.jeu_attache:
            return
        self.jeu_attache = False
        self.reveiller()
        with contextlib.suppress(Exception):
            await self.pont.fermer()
        self._nouvelle_instance()
        self.entete = None
        self.lieu.oublier()
        self.amis_combat.oublier()
        self.loupe_amis.oublier()
        self.log.info("Jeu détaché : suivi seul (connexion au serveur gardée)")

    def _suivi_sans_jeu(self) -> None:
        """Un tour sans le jeu : seulement ce qui se calcule sans lui (mélanges de la graine pour le tracker). Aucun
        accès GDB, aucun check envoyé (les checks ne viennent que du jeu)."""
        self.stats.cycles_suivi += 1
        if self._connexion_prete and self.reseau is not None:
            self._preparer_rando()
            self._preparer_boss()

    def reveiller(self) -> None:
        """Tour suivant sans attendre la période (dons reçus, connexion au serveur)."""
        self._reveil.set()

    @property
    def periode_resync(self) -> float:
        """Ancien nom de `periode_filet` (relecture complète périodique)."""
        return self.periode_filet

    @periode_resync.setter
    def periode_resync(self, v: float) -> None:
        self.periode_filet = v

    def periode_effective(self) -> float:
        """Période du tour ; ×FACTEUR_LECTURES_ARRETEES si le stub ne sert pas les lectures jeu en marche (chaque lecture
        arrête alors le jeu)."""
        if self.pont.lectures_en_marche is False:
            if not self._arrets_signales:
                self._arrets_signales = True
                self.log.warning("Le stub GDB ne sert pas les lectures jeu en marche : chaque lecture arrête le jeu "
                                 "(tour ralenti à %.1f s)", self.periode * FACTEUR_LECTURES_ARRETEES)
            return self.periode * FACTEUR_LECTURES_ARRETEES
        return self.periode

    def _bilan(self) -> None:
        """Charge GDB dans le journal du client toutes les PERIODE_BILAN s (paquets, octets, arrêts du jeu par minute)."""
        maintenant = time.monotonic()
        st = dict(self.pont.stats)
        if self._bilan_stats is None:
            self._bilan_t, self._bilan_stats = maintenant, st
            return
        duree = maintenant - self._bilan_t
        if duree < PERIODE_BILAN * self.echelle:
            return
        d = {k: st.get(k, 0) - self._bilan_stats.get(k, 0) for k in st}
        m = 60.0 / duree
        self.log.info("Charge GDB (%d s, lecture %s) : %.0f paquets/min, %.0f octets/min, %.1f arrêts/min (gel cumulé "
                      "%.0f ms/min), %d lecture(s) jeu arrêté", duree, self.lecture, d["paquets"] * m, d["octets"] * m,
                      d["arrets"] * m, d["duree_arret"] * m * 1000, d["lectures_arretees"])
        self._bilan_t, self._bilan_stats = maintenant, st

    # ------------------------------------------------------------------------------ réseau
    def _copie_catalogue(self) -> Catalogue:
        return copy.deepcopy(self.catalogue_base)

    def _demarrer_reseau(self) -> None:
        c = self.config
        self._deja_connecte = False
        self._refus = []
        self._connexion_prete = False
        self._scout, self._scout_fait = {}, False
        self._victoire_envoyee = False
        self.objets = []
        self.catalogue = self._copie_catalogue()
        self._table_ecrite = self._config_ecrite = self._depot_cle = None
        self._boutiques_ecrites = None
        opts = {"uuid": c.uuid, "dossier_cache": self.stockage.dossier_cache, **self.options_reseau}
        r = self.fabrique_client(c.serveur, c.slot, c.mot_de_passe, **opts)
        r.sur_connecte = self._sur_connecte
        r.sur_refus = self._sur_refus
        r.sur_objets = self._sur_objets
        r.sur_deconnexion = self._sur_deconnexion
        r.sur_indices = self._sur_indices
        r.sur_paquet = self._sur_paquet
        r.sur_message = self._sur_message
        r.sur_deathlink = self._sur_deathlink
        self.deathlink.option, self._tag_deathlink = False, False
        self.reseau = r
        self._tache_reseau = asyncio.create_task(self._executer_reseau(r))
        self.log.info("Connexion à %s (slot %s)", c.serveur, c.slot)

    async def _executer_reseau(self, r: ClientAP) -> None:
        try:
            await r.executer()
        except RefusConnexion as e:
            self.log.warning("Connexion refusée : %s", e)
        except asyncio.CancelledError:
            raise
        except Exception:                                   # pragma: no cover - filet de sécurité
            self.log.exception("Client Archipelago arrêté sur une erreur")

    async def _arreter_reseau(self) -> None:
        r, t = self.reseau, self._tache_reseau
        self.reseau = self._tache_reseau = None
        if r is not None:
            with contextlib.suppress(Exception):
                await r.arreter()
        if t is not None:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t

    async def _sur_connecte(self, paquet: dict) -> None:
        r = self.reseau
        if r is None:
            return
        self._deja_connecte = True
        self._refus = []
        self.catalogue = self._copie_catalogue()
        self.catalogue.appliquer_slot_data(r.slot_data)
        self.distrib.appliquer(r.slot_data if isinstance(r.slot_data, dict) else {})
        self.leg.appliquer(r.slot_data if isinstance(r.slot_data, dict) else {})
        self.portails.appliquer(r.slot_data if isinstance(r.slot_data, dict) else {})
        self.pieges.appliquer(r.slot_data if isinstance(r.slot_data, dict) else {})
        if self.catalogue.format_slot_data > FORMAT_SLOT_DATA:
            self.log.warning("slot_data au format %d (client : %d) : APWorld plus récent que le client",
                             self.catalogue.format_slot_data, FORMAT_SLOT_DATA)
        graine = str(r.room_info.get("seed_name", ""))
        ancien = self.ident_partie
        self.ident_partie = self.catalogue.ident_partie or ident_partie_par_defaut(graine, r.team or 0, r.slot or 0)
        self.bingo.appliquer(r.slot_data if isinstance(r.slot_data, dict) else {})   # V3, lot B1
        if ancien is not None and ancien != self.ident_partie:
            self.anims.attente.clear()               # fenêtres d'une autre partie AP : jamais écrites
        self._connexion_prete = True
        self._config_ecrite = self._table_ecrite = None
        self._resync_demandee = True
        self._rando_lu_cle = None
        self._boss_lu_cle = None
        self.reveiller()
        # la configuration est déjà dans config.json (écrite par le lanceur) ; l'identifiant du client
        # y est gardé s'il manquait (réécrire toute la configuration écraserait une saisie plus récente du lanceur)
        if not self.stockage.lire_brut().get("uuid"):
            try:
                self.stockage.modifier(uuid=self.config.uuid)
            except OSError as e:
                self.log.warning("Configuration non enregistrée : %s", e)
        self.log.info("Connecté : slot %s, identifiant de partie %#010x, %d coffres, %d spots", r.slot,
                      self.ident_partie, len(self.catalogue.coffres), len(self.catalogue.spots))
        self._maj_checks()
        self._maj_indices()
        self._noms_essais = 0
        self._maj_noms_chat()
        self.journal_chat.systeme("connecte", serveur=self.config.serveur, slot=r.nom_joueur(r.slot))
        # DeathLink : tag posé seulement quand le jeu attaché le compile (`_suivre_deathlink`)
        self.deathlink.option, self._tag_deathlink = self.catalogue.death_link, False
        self._maj_tag_deathlink()
        if not self._scout_fait:
            self._lancer(self._scouter(r))

    def _sur_refus(self, erreurs: list[str]) -> None:
        self._refus = list(erreurs) or ["?"]
        self.journal_chat.systeme("refuse", erreurs=list(self._refus))

    def _sur_objets(self, objets: list[ObjetReseau], debut: int) -> None:
        self.objets = list(objets)
        self.invites_arrivees()                              # ordre d'arrivée noté dès la réception (jeu fermé compris)
        self.reveiller()                                     # don reçu : déposé au tour suivant, sans attendre
        self._maj_checks()

    def _sur_indices(self, _indices: list[dict]) -> None:
        self._maj_checks()
        self._maj_indices()

    def _sur_paquet(self, p: dict) -> None:
        if p.get("cmd") == "RoomUpdate" and "checked_locations" in p:
            self._maj_checks()

    def _sur_deconnexion(self, raison: str) -> None:
        self.log.info("Serveur Archipelago perdu : %s", raison)
        self._maj_checks(connecte=False)
        self._maj_indices(connecte=False)
        self.journal_chat.systeme("deconnecte", raison=str(raison)[:200])

    # ------------------------------------------------------------------------------ discussion (onglet du lanceur)
    def _maj_noms_chat(self) -> None:
        """`chat_noms.json` (noms du jeu du slot, pour l'autocomplétion de la console) : écrit une fois par connexion, et
        seulement si le jeu a changé (une reconnexion n'écrit rien). Aucun paquet. Simple aide de la console : aucune
        erreur ici ne doit interrompre la connexion."""
        r = self.reseau
        if r is None:
            return
        try:
            donnees = r.donnees.get(r.jeu)
            cle = (r.jeu, donnees.checksum if donnees else "")
            if cle == self._noms_cle:
                return
            ch.ecrire_noms(self.stockage.dossier, ch.construire_noms(r.jeu, donnees))
            self._noms_cle = cle
        except OSError as e:                 # fichier ouvert par le lanceur à cet instant : deux nouveaux essais
            self.log.debug("chat_noms.json non écrit : %s", e)
            self._noms_essais += 1
            if self._noms_essais < 3:
                self._planifier_ecriture(1.0, self._maj_noms_chat)
        except Exception as e:               # noqa: BLE001 - données inattendues : pas de propositions, c'est tout
            self.log.warning("chat_noms.json non écrit : %r", e)

    def _sur_message(self, _texte: str, p: dict) -> None:
        """PrintJSON du serveur -> `messages.jsonl` (parties colorées, noms résolus ; rien d'autre que ce que le serveur
        envoie)."""
        r = self.reseau
        if r is None:
            return
        parties = ch.parties_printjson(p, slot_soi=r.slot, nom_soi=r.nom_joueur(r.slot) if r.slot else "",
                                       nom_joueur=r.nom_joueur, nom_objet=r.nom_objet, nom_location=r.nom_location)
        self.journal_chat.ajouter(str(p.get("type") or ""), parties)
        ev = dobj.evenement_printjson(p, r.slot, nom_joueur=r.nom_joueur, nom_objet=r.nom_objet,
                                      nom_location=r.nom_location)
        if ev is not None:                       # objet reçu / envoyé par CE slot : derniers_objets.json
            self.derniers_objets.ajouter(ev, jeu=bool(self.jeu_attache and self.pont.connecte))

    async def _surveiller_chat(self) -> None:
        """`chat_commandes.json` (lanceur) surveillé : chaque commande nouvelle de cette session est envoyée une fois."""
        while not self._arret.is_set():
            try:
                await self.suivre_commandes_chat()
            except Exception as e:                            # noqa: BLE001 - la surveillance ne doit pas s'arrêter
                self.log.warning("Commande du lanceur non traitée : %s", e)
            await asyncio.sleep(self.periode_chat)

    async def suivre_commandes_chat(self) -> int:
        """Envoie (Say) les commandes nouvelles du lanceur ; chacune est notée dans le journal (envoyée ou non). Renvoie
        le nombre de commandes envoyées."""
        n = 0
        for c in self.commandes_chat.nouvelles():
            r = self.reseau
            if r is None or not r.connecte:
                self.journal_chat.systeme("non_envoye", commande=c["id"], texte=c["texte"], raison="non_connecte")
                continue
            if "action" in c:
                if await self._action_lanceur(r, c):
                    n += 1
                continue
            try:
                await r.dire(c["texte"])
            except Exception as e:                            # noqa: BLE001 - connexion perdue pendant l'envoi
                self.journal_chat.systeme("non_envoye", commande=c["id"], texte=c["texte"], raison=str(e)[:200])
                continue
            n += 1
            self.journal_chat.systeme("envoye", commande=c["id"], texte=c["texte"])
            self.log.info("Message du lanceur envoyé au serveur (%d caractères)", len(c["texte"]))
        return n

    async def _action_lanceur(self, r: ClientAP, c: dict) -> bool:
        """Action du lanceur (sous-onglet « Indices ») : seul UpdateHint est permis (`indices_local.valider_action`)."""
        paquet = il.valider_action(c.get("action"))
        if paquet is None:
            self.journal_chat.systeme("non_envoye", commande=c["id"], texte=c["texte"], raison="action_invalide")
            return False
        try:
            await r.changer_statut_indice(paquet["player"], paquet["location"], paquet["status"])
        except Exception as e:                                # noqa: BLE001 - connexion perdue pendant l'envoi
            self.journal_chat.systeme("non_envoye", commande=c["id"], texte=c["texte"], raison=str(e)[:200])
            return False
        h = next((h for h in r.indices if il._entier(h.get("finding_player")) == paquet["player"]
                  and il._entier(h.get("location")) == paquet["location"]), None)
        objet = r.nom_objet(int(h["item"]), il._entier(h.get("receiving_player"))) if h and "item" in h else ""
        lieu = r.nom_location(paquet["location"], paquet["player"])
        self.journal_chat.systeme("statut_indice", commande=c["id"], objet=objet, lieu=lieu, statut=paquet["status"])
        self.log.info("Priorité d'un indice demandée au serveur (location %d, état %d)", paquet["location"],
                      paquet["status"])
        return True

    def _maj_indices(self, connecte: bool | None = None) -> None:
        """`indices.json` pour le lanceur (sous-onglet « Indices ») : réécrit seulement s'il a changé."""
        r = self.reseau
        if r is None or r.slot is None:
            return
        try:
            d = il.construire_indices(r.indices, slot=r.slot, team=r.team, graine=str(r.room_info.get("seed_name", "")),
                                      joueur=r.nom_joueur(r.slot), connecte=r.connecte if connecte is None else connecte,
                                      nom_joueur=r.nom_joueur, nom_objet=r.nom_objet, nom_location=r.nom_location)
            self._indices_empreinte = il.ecrire_indices(self.stockage.dossier, d, self._indices_empreinte)
        except OSError as e:
            self.log.warning("indices.json non écrit : %s", e)

    def _lancer(self, coro) -> None:
        t = asyncio.create_task(coro)
        self._taches.add(t)
        t.add_done_callback(self._taches.discard)

    async def _scouter(self, r: ClientAP) -> None:
        """Contenu de TOUTES les locations du slot (LocationScouts, sans indice) pour la table, les notifications
        (« Envoyé : … » d'un boss vaincu), le contenu des checks faits (`checks.json`) et le spoiler log sur demande."""
        locs = r.locations_manquantes | r.locations_verifiees
        try:
            res = await r.scouter(sorted(locs)) if locs else []
        except Exception as e:                               # déconnexion : refait à la prochaine connexion
            self.log.info("LocationScouts non abouti : %s", e)
            return
        if r is not self.reseau:
            return
        self._scout = {o.location: o for o in res}
        self._scout_fait = True
        self._table_ecrite = None
        self.reveiller()
        self.log.info("Contenu de %d locations reçu", len(self._scout))
        self._maj_checks()

    # ------------------------------------------------------------------------------ état publié (§5.2)
    def _message(self, cle: str) -> str:
        """Message court de l'écran Archipelago dans la langue des notifications de la graine (connue après
        slot_data ; français avant)."""
        return MESSAGES_PAR_LANGUE.get(self.catalogue.langue, MESSAGES)[cle]

    def etat_voulu(self) -> v3.EtatConnexion:
        """État publié dans la zone C (écran Archipelago en lecture seule, bandeau, etat.json). Depuis le 2026-09-28,
        jamais de demande de saisie ni d'effacement de mot de passe (drapeaux 0x01 / 0x04 : la configuration se fait
        dans le lanceur) ; `revision_lue` reste à 0."""
        c, r = self.config, self.reseau
        drapeaux = 0
        commun = dict(connu=c.connu, serveur=c.serveur, slot=c.slot)
        if not c.configuree:
            return v3.EtatConnexion(v3.NON_CONFIGURE, drapeaux=drapeaux, message=self._message("non_configure"),
                                    **commun)
        if self._refus:
            en = self.catalogue.langue == "en"
            code, msg = v3.ERR_AUTRE, textes_bandeau(self.catalogue.langue)["refus"]
            for nom, k, m in ERREURS_REFUS:
                if nom in self._refus:
                    code, msg = k, ERREURS_REFUS_EN[nom] if en else m
                    break
            return v3.EtatConnexion(v3.ERREUR, erreur=code, drapeaux=drapeaux | v3.CX_AFFICHER_MESSAGE,
                                    message=msg, **commun)
        if r is not None and r.connecte:
            if self.verrous_manquants or self.boutiques_manquantes or self.distrib.manquants or self.leg.manquants:
                return v3.EtatConnexion(v3.CONNECTE, drapeaux=drapeaux, message=self._message("verrous_incompatibles"),
                                        **commun)
            if self.boss_manquant:                       # mélange des boss de la graine (version 2) non appliqué
                return v3.EtatConnexion(v3.CONNECTE, drapeaux=drapeaux, message=self._message(self.boss_manquant),
                                        **commun)
            if self.yokai_manquant:                      # mélange des Yo-kai de version 7 (zones) non appliqué
                return v3.EtatConnexion(v3.CONNECTE, drapeaux=drapeaux, message=self._message(self.yokai_manquant),
                                        **commun)
            if self.sauvegarde in MESSAGES:
                # sauvegarde non liée / autre partie / jeu ancien / liaison : message dans l'écran seulement (le
                # bandeau reçoit une notification dédiée, une fois par sauvegarde : `_suivre_partie`)
                return v3.EtatConnexion(v3.CONNECTE, drapeaux=drapeaux, message=self._message(self.sauvegarde), **commun)
            return v3.EtatConnexion(v3.CONNECTE, drapeaux=drapeaux | v3.CX_AFFICHER_MESSAGE,
                                    message=self._message("connecte"), **commun)
        if self._deja_connecte:
            return v3.EtatConnexion(v3.DECONNECTE, drapeaux=drapeaux | v3.CX_AFFICHER_MESSAGE,
                                    message=self._message("deconnecte"), **commun)
        if r is not None and r.derniere_erreur:
            return v3.EtatConnexion(v3.ERREUR, erreur=v3.ERR_INJOIGNABLE, drapeaux=drapeaux | v3.CX_AFFICHER_MESSAGE,
                                    message=self._message("injoignable"), **commun)
        return v3.EtatConnexion(v3.CONNEXION, drapeaux=drapeaux, message=self._message("connexion"), **commun)

    async def _publier(self, force: bool = False) -> None:
        voulu = self.etat_voulu()
        if not force and self._publie == voulu.sans_images():
            return
        # AFFICHER_MESSAGE : seulement quand l'état ou le message change (pas pour un simple acquittement)
        if self._publie is not None and not force and (self._publie.etat, self._publie.message) == (voulu.etat, voulu.message):
            voulu = replace(voulu, drapeaux=voulu.drapeaux & ~v3.CX_AFFICHER_MESSAGE)
        self._battement += 1
        a_publier = replace(voulu, client_images=self._battement)
        await self.zone.publier(a_publier)
        self._publie = voulu.sans_images()
        self.etat_publie = a_publier
        self.stats.publications += 1
        self.log.info("État publié : %s — %s", v3.NOMS_ETAT.get(voulu.etat, voulu.etat), voulu.message)

    # ------------------------------------------------------------------------------ configuration du lanceur
    async def _surveiller_config(self) -> None:
        """config.json surveillé (date, taille) : une saisie du lanceur (révision de connexion plus grande que la
        nôtre) est appliquée et reconnecte. Fichier local seulement : aucune lecture ni écriture GDB."""
        while not self._arret.is_set():
            try:
                await self.suivre_fichier_config()
            except Exception as e:                            # noqa: BLE001 - la surveillance ne doit pas s'arrêter
                self.log.warning("Configuration locale illisible : %s", e)
            try:
                self.suivre_demande_spoiler()
            except Exception as e:                            # noqa: BLE001
                self.log.warning("Spoiler log non écrit : %s", e)
            await asyncio.sleep(self.periode_config)

    async def suivre_fichier_config(self) -> bool:
        """Applique config.json s'il a changé ; True si une nouvelle saisie de connexion a été appliquée."""
        sig = self.stockage.signature()
        if sig is None or sig == self._signature_config:
            return False
        self._signature_config = sig
        disque = self.stockage.charger()
        c = self.config
        c.rom = disque.rom                                    # réglage du lanceur (base du randomizer)
        # révision seulement : une configuration écrite par une version antérieure (source « jeu ») compte pareil
        if disque.revision_connexion <= self._rev_locale:
            return False
        if disque.mdp_revision == disque.revision_connexion:  # mot de passe choisi dans cette saisie
            mdp = disque.mot_de_passe
            self.stockage.consommer_transmis()
        else:                                                  # « inchangé » : celui que le client a déjà
            mdp = c.mot_de_passe
        change = (disque.serveur, disque.slot, mdp) != (c.serveur, c.slot, c.mot_de_passe)
        self.log.info("Configuration du lanceur (révision de connexion %d) : serveur %s, slot %s, mot de passe %s%s",
                      disque.revision_connexion,
                      disque.serveur or "-", disque.slot or "-", "défini" if mdp else "aucun",
                      "" if change else " (inchangée)")
        c.serveur, c.slot, c.mot_de_passe = disque.serveur, disque.slot, mdp
        c.memoriser_mot_de_passe = disque.memoriser_mot_de_passe
        c.revision_connexion, c.mdp_revision = disque.revision_connexion, disque.mdp_revision
        c.source_connexion, c.horodatage_connexion = disque.source_connexion, disque.horodatage_connexion
        self._rev_locale = disque.revision_connexion
        if change or self._refus or not (self.reseau and self.reseau.connecte):
            await self._arreter_reseau()
            if c.configuree:
                self._demarrer_reseau()
        self.reveiller()                                       # état republié dans le jeu au prochain tour
        return True

    # ------------------------------------------------------------------------------ un tour
    async def cycle(self) -> None:
        self.stats.cycles += 1
        brut = await self.zone.lire_entete_brut()
        hd = bp.lire_entete(brut)
        if hd["magic"] != bp.MAGIC:
            return                                           # jeu pas encore à sa première image
        h = Entete(**hd)
        self.entete = h
        self.lieu.suivre(h.lieu)                             # en-tête de ce tour seulement : aucun paquet de plus
        await self.amis_combat.suivre(h.etat, h.amis_numero, self.boite.gdb.lire)   # un paquet par changement en combat
        await self.loupe_amis.suivre(h.etat, h.loupe_numero, self.boite.gdb.lire)   # un paquet par changement de point visé
        if self.boite.nouvelle_instance(h):
            self._nouvelle_instance()
        if h.etat & bp.ETAT_DEFINITIONS:
            self._definitions_vues = self._instance  # (bit posé par image, partie chargée : retenu pour cette instance)
        if h.etat & bp.ETAT_PANIQUE:
            await self._suivre_panique()                 # le jeu a paniqué : enregistrement lu, journalisé, acquitté
        a_v3 = self.zone.disponible(h)
        if a_v3:
            self.zone.ajuster(brut)
        # jeu d'une version antérieure (écran Archipelago avec claviers) : jeu suspendu par un clavier, aucune écriture ;
        # sa configuration (zone J) n'est jamais lue (la saisie se fait dans le lanceur)
        if a_v3 and self.zone.saisie_etat(brut) == v3.SAISIE_CLAVIER_OUVERT:
            return
        if self._connexion_prete and self.reseau is not None:
            await self._verifier_verrous(a_v3)
            await self._verifier_boutiques(h)
            await self.distrib.verifier(h)               # V3, lot C1 : distributeurs (refus si le jeu ou la ROM manque)
            await self.leg.verifier(h)                   # V3, lot L1 : légendaires mélangés (refus si le jeu manque)
            await self.portails.verifier(h)              # récompense des portails (avertissement si le jeu manque)
            await self.pieges.verifier(h if a_v3 else None)   # pièges absents du patch (avertissement)
            await self._verifier_boss(h)
            self._verifier_yokai_zones(h)
            await self._configurer_boite(h, a_v3)            # avant la liaison (identifiant de partie, politique)
            await self._suivre_partie(h, brut)
            await self._suivre_rando(h)
            await self._suivre_rando_boss(h)
            await self._suivre_tracker(h)
            await self._suivre_deathlink(h)
            await self._suivre_anims(h)
            await self.pieges.suivre(h)                  # reprise en plusieurs paquets : `reprise_vue` (attente seulement)
            await self.pieges.apres_victoire(h if a_v3 else None)   # objectif atteint : file des pièges du jeu vidée
        async with self.pont.lot():                          # écritures de fin de tour : un seul arrêt
            if a_v3:
                await self._publier(force=self._publie is None)   # l'état d'abord (puis ce qu'il annonce)
            if self._connexion_prete and self.reseau is not None:
                # tables APRÈS le statut de la sauvegarde de CE tour (sauvegarde liée rechargée : table des coffres
                # présente dès ce tour-ci) et AVANT les dons, dans le même arrêt
                await self._ecrire_table(h, a_v3)
                if a_v3:
                    await self._ecrire_verrous()
                    await self._ecrire_verrous2()
                    await self._ecrire_verrous3()
                    await self._ecrire_amitie()
                    await self._ecrire_pieces()
                    await self._ecrire_invites(h)
                    await self._ecrire_evenement()
                    await self.distrib.ecrire(h)         # V3, lot C1 : table des distributeurs (sauvegarde liée)
                    await self.leg.ecrire(h)             # V3, lot L1 : permutation des légendaires (sauvegarde liée)
                    await self.portails.ecrire(h)        # récompense des portails : liste (sauvegarde liée)
                    await self.bingo.ecrire(h)           # V3, lot B1 : mélange du Bingo-kai (sauvegarde liée)
                    await self.pieges.ecrire(h)          # pièges reçus pas finis : reprise (sauvegarde liée)
            await self._deposer_dons(h)
            if self._connexion_prete and self.reseau is not None:
                await self._ecrire_mort(h)               # mort reçue : demande au jeu (et son bandeau, ci-dessous)
                await self._deposer_anims(h)             # fenêtres « objet obtenu » des checks sans affichage
            await self._deposer_notifications(h)
            await self._acquitter_journal(h)                 # avec l'arrêt déjà pris, ou au plus tard après un délai
        self._bilan()

    async def _suivre_panique(self) -> None:
        """Panique du jeu (svc Break « PANIC », §28) : le jeu a recopié dans ApPanique l'adresse de retour et la pile de la
        fonction fautive puis attend (au plus 20 s) que `lu` = `compte`. Lu une fois par panique (un seul paquet), écrit
        dans le journal (ERREUR) et dans `plantage.json` du dossier du client, puis acquitté : le jeu continue sa panique
        (svc Break, fenêtre d'erreur d'Azahar). Aucune autre lecture ni écriture."""
        b = await self.pont.lire(bp.ZONE + bp.OFF_PANIQUE, bp.TAILLE_PANIQUE)
        d = bp.dec_panique(b)
        cle = (self._instance, d["compte"])
        if d["compte"] == 0 or cle == self._panique_vue:
            return
        self._panique_vue = cle
        self.log.error("Le jeu a planté (%s). Garder ce journal et plantage.json pour le diagnostic "
                       "(archipelago/PLAN.md, « Si le jeu plante »).", bp.texte_panique(d))
        e = {"horodatage": time.time(), "instance": self._instance, "ident_partie": self.ident_partie,
             **{k: d[k] for k in ("compte", "raison", "images", "etat", "chapitre", "pas", "terrain_numero")},
             "appelant": f"{d['appelant']:#010x}", "pile": f"{d['pile']:#010x}",
             "regs_r4_r11": [f"{x:#x}" for x in d["regs"]],
             "retours": [[o, f"{v:#010x}"] for o, v in bp.retours_panique(d)],
             "mots": [f"{x:#010x}" for x in d["mots"]]}
        self.paniques.append(e)
        try:
            f = Path(self.stockage.dossier) / "plantage.json"
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps({"format": 1, "paniques": self.paniques[-10:]}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(f)
        except OSError as err:
            self.log.warning("plantage.json non écrit : %s", err)
        async with self.pont.transaction():          # écriture jeu arrêté, comme toutes les autres
            await self.pont.ecrire(bp.ZONE + bp.OFF_PANIQUE + bp.PANIQUE_OFF_LU, struct.pack("<I", d["compte"]))

    def _nouvelle_instance(self) -> None:
        self._instance += 1
        self.stats.instances += 1
        self._publie = None
        self._table_ecrite = self._config_ecrite = self._depot_cle = None
        self._boutiques_ecrites = None
        self._partie_cle = None
        self.distrib.nouvelle_instance()
        self.leg.nouvelle_instance()
        self.portails.nouvelle_instance()
        self.bingo.nouvelle_instance()
        self.pieges.nouvelle_instance()
        self._oublier_sauvegarde()
        self._resync_demandee = True
        self._victoire_t = 0.0
        self._spots_vus = -1
        self._progression_vue = None
        self._verrous_ecrits = None
        self._verrous_compiles = None
        self._invites_compiles = self._invites_ecrits = None
        self._invites2_compiles = None
        self._pieces_compile = self._pieces_ecrites = None
        self._etendues_compilees = None
        self._evenement_ecrit = None
        self._invites_seq = 0
        self._recompenses_etat = None
        self._boutiques_etat = None
        self._rando_jeu = None
        self._medaillium = None
        self._progression_suivi = None
        self._journal_lu, self._acquitter_t = 0, 0.0
        self._rando_lu_cle, self._rando_attente = None, False
        self._boss_jeu, self._boss_force_jeu = None, False
        self._boss_lu_cle, self._boss_attente, self._boss_valide_lu = None, False, 0
        self._terrain_suivi = None
        self._adresse_q = self._adresse_rang = None
        self.deathlink.nouvelle_instance()
        self.anims.nouvelle_instance()
        self._maj_tag_deathlink()
        self.log.info("Nouvelle instance du jeu (session GDB %d) : resynchronisation complète", self.pont.sessions)

    async def _configurer_boite(self, h, a_v3: bool) -> None:
        politique = bp.POLITIQUE_REESSAYER if self.catalogue.politique_reessai else 0
        if h.version >= bp.VERSION_LIAISON:
            # v4 : le jeu ne marque une sauvegarde QUE sur une demande de liaison explicite (liaison_demande,
            # `_evaluer_sauvegarde`) ; un jeu v3 marquerait toute sauvegarde chargée : jamais de MARQUER pour lui
            politique |= bp.POLITIQUE_MARQUER
        langue = 1 if self.catalogue.langue == "en" else 0
        voulu = (self._instance, self.ident_partie, politique, langue, self.catalogue.vitrine)
        if self._config_ecrite == voulu and h.ident_partie == self.ident_partie:
            return
        async with self.pont.transaction():
            await self.boite.configurer(ident_partie=self.ident_partie, politique=politique, notif_langue=langue,
                                        pause=False)
            if a_v3:
                await self.pont.ecrire(*bp.champ("vitrine", self.catalogue.vitrine))
        self._config_ecrite = voulu

    # ------------------------------------------------------------------------------ tables (coffres, J3, J5)
    def _contenu(self, loc: int) -> Contenu | None:
        """Contenu d'une location tel que le jeu le montre : celui de slot_data ou des LocationScouts, avec l'image de
        l'objet quand il en a une (§21 des invitations ; toute graine, aucune clé de slot_data)."""
        c = self._contenu_slot(loc)
        if c is None or not c.propre or c.hachage != self.catalogue.vitrine or not c.texte:
            return c                                 # objet du jeu, ou d'un autre monde : inchangé
        h = affichage.hachage(c.texte, self._definitions_vues == self._instance)
        return c if h is None else Contenu(True, h, None)

    def _contenu_slot(self, loc: int) -> Contenu | None:
        """Contenu d'une location : celui de slot_data (APWorld), sinon déduit du LocationScouts."""
        c = self.catalogue.contenus.get(loc)
        if c is not None:
            return c
        r, o = self.reseau, self._scout.get(loc)
        if o is None or r is None:
            return None
        nom_objet = r.nom_objet(o.item, o.player)
        if o.player == r.slot:
            don = self.catalogue.don(o.item)
            if don.type == bp.DON_OBJET and don.hash:
                return Contenu(True, don.hash, None)
            return Contenu(True, self.catalogue.vitrine, nom_objet)
        return Contenu(False, self.catalogue.vitrine, nom_vitrine(nom_objet, r.nom_joueur(o.player),
                                                                  self.catalogue.langue))

    def table_voulue(self, a_v3: bool) -> tuple[list[EntreeCoffre], dict[int, str]]:
        """Entrées de la table des coffres (par index en v3, par hachage TBox sinon) et noms de vitrine
        {étiquette = location : texte}."""
        entrees, noms = [], {}
        for loc, idx in sorted(self.catalogue.coffres.items(), key=lambda x: x[1]):
            c = self._contenu(loc)
            if c is None:
                continue
            drapeaux = bp.COFFRE_AFFICHAGE_SEUL
            if a_v3:
                tbox, drapeaux = idx, drapeaux | bp.COFFRE_PAR_INDEX
            elif loc in self.catalogue.hachages_tbox:
                tbox = self.catalogue.hachages_tbox[loc]
            else:
                continue
            entrees.append(EntreeCoffre(tbox, c.hachage, 1, drapeaux, loc & 0xFFFFFFFF))
            if c.hachage == self.catalogue.vitrine and c.texte:
                noms[loc] = c.texte
        return entrees, noms

    def scripts_voulus(self) -> tuple[list[v3.EntreeScript], dict[int, str]]:
        """Dons de script substitués (§12) : un par spot connu de slot_data. Spot mélangé : l'objet d'origine
        n'est pas donné, la fenêtre montre le contenu AP (vitrine nommée ou objet de ce monde, qui arrive par la
        file) ; spot NON mélangé : DONNER l'objet d'origine (le jeu le donne lui-même, le bit de check est posé)."""
        entrees, noms = [], {}
        for loc, e in sorted(self.catalogue.emplacements.items(), key=lambda x: x[1].bit):
            c = self._contenu(loc)
            if not e.hachage_origine or c is None:
                continue
            # (V3 : un don à plusieurs hachages d'origine, un par personnage joué, a une entrée par hachage)
            for origine in (e.hachages or (e.hachage_origine,)):
                if e.substituer:
                    entrees.append(v3.EntreeScript(origine, c.hachage, e.bit, 0, loc))
                    if origine in bp.DONS_EN_AMONT:
                        # Montre étrange du magasin : le moment du check (fenêtre du jeu, objet de la location) ; le don
                        # de 1-90 ne donne rien, comme toute entrée sans DONNER (objets_cles_v11 §21)
                        entrees.append(v3.EntreeScript(bp.DONS_EN_AMONT[origine], c.hachage, e.bit, 0, loc))
                else:
                    entrees.append(v3.EntreeScript(origine, origine, e.bit, bp.SCRIPT_DONNER, loc))
            if c.hachage == self.catalogue.vitrine and c.texte:
                noms[loc] = c.texte
        return entrees, noms

    def noms_par_priorite(self, coffres: dict[int, str], scripts: dict[int, str],
                          distributeurs: dict[int, str]) -> list[tuple[int, str]]:
        """Noms de vitrine (étiquette = location) dans l'ordre où ils prennent les places de la table (§13, §13bis) :
        dons de script, distributeurs, coffres, d'abord les locations pas encore faites sur le serveur, puis celles
        déjà faites (un coffre déjà ouvert ne se rouvre que dans une sauvegarde d'avant). Avec un jeu qui n'a que 256
        places (patch antérieur à la suite de la table), le nom d'un don de script n'est plus jamais perdu : avant, les
        coffres prenaient toutes les places et le don du Filet montrait « Objet Archipelago » (gros test V3)."""
        faites = self.reseau.locations_verifiees if self.reseau is not None else set()
        vus: set[int] = set()
        ordre: list[tuple[int, str]] = []
        for deja in (False, True):
            for groupe in (scripts, distributeurs, coffres):
                for loc, texte in groupe.items():
                    if loc in vus or (loc in faites) != deja:
                        continue
                    vus.add(loc)
                    ordre.append((loc, texte))
        return ordre

    def recompenses_voulues(self) -> dict[int, bytes]:
        """Table des récompenses de quête (boîte v5, §21) : n° de quête -> entrée. Objet de ce monde : le vrai objet
        (montré, puis livré par la file de dons quand le check est confirmé) ; autre monde, argent, objet sans objet du
        jeu : la vitrine et son nom. Service déjà envoyé : pas d'entrée (il est rejouable ; il redonne sa récompense
        d'origine, sans objet)."""
        r, verifiees = {}, (self.reseau.locations_verifiees if self.reseau is not None else set())
        for loc, q in sorted(self.catalogue.recompenses.items()):
            c = self._contenu(loc)
            if c is None or (q.service and loc in verifiees):
                continue
            texte = bp.nom_vitrine(c.texte) if c.hachage == self.catalogue.vitrine and c.texte else b""
            r[q.quete] = bp.enc_quete(c.hachage, loc, bp.QUETE_VALIDE, texte)
        return r

    async def _etat_recompenses(self, h) -> str:
        """« actives », « non_compilees » (build --define YKW2_AP_SANS_RECOMPENSES) ou « jeu_ancien » (boîte v4 : aucune
        table ; la récompense d'origine est donnée, le check part quand même par la phase 255). Lu une fois par
        instance du jeu."""
        if self._recompenses_etat is None or self._recompenses_etat[0] != self._instance:
            if not self.zone.recompenses_disponibles(h):
                etat = "jeu_ancien"
            else:
                c = bp.recompenses_compilees(await self.zone.lire_quetes_entete())
                etat = "actives" if c else "non_compilees"
            self._recompenses_etat = (self._instance, etat)
            if self.catalogue.recompenses and etat != "actives":
                self.log.warning("Récompenses de quête d'origine (%s) : les checks de quête partent quand même",
                                 "jeu v%d sans table" % h.version if etat == "jeu_ancien"
                                 else "build compilé sans la substitution")
        return self._recompenses_etat[1]

    def boutiques_voulues(self) -> list[bytes]:
        """Table des boutiques (boîte v9, §26) : une entrée par hachage d'article des locations de boutique pas encore
        faites. Objet de ce monde : le vrai objet (montré, puis livré par la file de dons quand le check est confirmé) ;
        autre monde, argent, objet sans objet du jeu : la vitrine et son nom. Articles omis : déjà cochés sur le serveur
        quand la sauvegarde liée a été vue (instantané `_boutiques_faites` : l'article reste d'origine même si le joueur
        recharge une sauvegarde d'avant l'achat) ; le jeu omet de lui-même ceux dont le bit est posé."""
        if self._boutiques_faites is None:
            verifiees = self.reseau.locations_verifiees if self.reseau is not None else set()
            self._boutiques_faites = frozenset(loc for loc in self.catalogue.boutiques if loc in verifiees)
        r = []
        for loc, b in sorted(self.catalogue.boutiques.items(), key=lambda x: x[1].bit):
            c = self._contenu(loc)
            if c is None or loc in self._boutiques_faites:
                continue
            texte = bp.nom_vitrine(c.texte) if c.hachage == self.catalogue.vitrine and c.texte else b""
            affiche = 0 if c.hachage == self.catalogue.vitrine else c.hachage
            for a in b.articles:
                r.append(bp.enc_boutique(a, affiche, loc, b.bit, bp.BOUTIQUE_VALIDE, texte))
        if len(r) > bp.CAP_BOUTIQUES:
            # jamais atteint par les données connues (290 articles au plus pour 320 places, test_logo_grande_partie) ;
            # sinon les derniers articles (bits les plus hauts) resteraient d'origine : le dire, jamais en silence
            signal = (getattr(self, "_instance", 0), len(r))
            if getattr(self, "_boutiques_perdues", None) != signal:
                self._boutiques_perdues = signal
                self.log.warning("Table des boutiques : %d articles pour %d places : les %d derniers restent d'origine "
                                 "(sans logo Archipelago ni check)", len(r), bp.CAP_BOUTIQUES,
                                 len(r) - bp.CAP_BOUTIQUES)
        return r[:bp.CAP_BOUTIQUES]

    async def _etat_boutiques(self, h) -> str:
        """« actives », « non_compilees » (build --define YKW2_AP_SANS_BOUTIQUES) ou « jeu_ancien » (boîte v8 ou
        antérieure : aucune table). Lu une fois par instance du jeu."""
        if self._boutiques_etat is None or self._boutiques_etat[0] != self._instance:
            if not self.zone.boutiques_disponibles(h):
                etat = "jeu_ancien"
            else:
                c = bp.boutiques_compilees(await self.zone.lire_boutiques_entete())
                etat = "actives" if c else "non_compilees"
            self._boutiques_etat = (self._instance, etat)
        return self._boutiques_etat[1]

    def _preparer_boutiques(self) -> str:
        """Hachages des articles (format 17) lus dans `boutiques_local.json`, généré depuis la ROM configurée s'il manque
        (tâche de fond, < 1 s) ; renvoie l'état : « pretes » (tous les articles ont leur hachage), « calcul »,
        « absente » (ni table locale ni ROM : « Réparer le mod »), « refusee » (ROM qui ne correspond pas)."""
        a_resoudre = {loc: b for loc, b in self.catalogue.boutiques.items() if not b.articles}
        if not a_resoudre:
            self._boutiques_resolution = "pretes"
            return "pretes"
        if self._boutiques_tache is not None and not self._boutiques_tache.done():
            return "calcul"
        try:
            ib = _installation_boutiques()
        except Exception as e:  # noqa: BLE001 - module distribué avec le client ; absent : refus clair
            return self._boutiques_refus("absente", f"module installation/boutiques.py introuvable ({e})")
        try:
            attendue = ib.apworld_boutiques().EMPREINTE_ARTICLES
        except Exception:  # noqa: BLE001 - APWorld embarqué illisible : la table locale reste contrôlée article par article
            attendue = None
        table = ib.charger(self.stockage.dossier, attendue)
        if table is None:
            if self._boutiques_resolution == "refusee":
                return "refusee"            # ROM déjà refusée : pas de nouvelle lecture à chaque tour
            rom = self.config.rom
            if not rom or not Path(rom).is_file():
                return self._boutiques_refus("absente", "table locale des boutiques absente et ROM non configurée "
                                             "(« Réparer le mod » dans le lanceur)")
            self.log.info("Articles de boutique : table locale générée depuis la ROM…")
            self._boutiques_resolution = "calcul"
            self._boutiques_tache = asyncio.create_task(asyncio.to_thread(ib.generer_fichier, rom,
                                                                          self.stockage.dossier))
            self._boutiques_tache.add_done_callback(self._boutiques_generee)
            return "calcul"
        try:
            resolus = {loc: ib.cles_article(table, b.boutique, b.entrees, b.nb_entrees) for loc, b in a_resoudre.items()}
        except ib.ErreurBoutiques as e:
            return self._boutiques_refus("refusee", f"article de la graine introuvable dans la ROM ({e})")
        for loc, arts in resolus.items():
            self.catalogue.boutiques[loc].articles = arts
        self._boutiques_resolution = "pretes"
        self.log.info("Articles de boutique lus dans la ROM du joueur : %d location(s)", len(resolus))
        return "pretes"

    def _boutiques_refus(self, etat: str, message: str) -> str:
        if self._boutiques_resolution != etat:
            self.log.error("Boutiques : %s ; les checks de boutique sont impossibles (rien ne sera lié, livré ni "
                           "envoyé)", message)
        self._boutiques_resolution = etat
        return etat

    def _boutiques_generee(self, t: asyncio.Task) -> None:
        if t.cancelled():
            return
        e = t.exception()
        if e is not None:
            self._boutiques_refus("refusee", f"ROM refusée : {e}")
        else:
            self.log.info("Table locale des boutiques écrite : %s", t.result())
            self._boutiques_resolution = "absente"      # relue tout de suite (« pretes » si elle convient)
            self._preparer_boutiques()

    async def _verifier_boutiques(self, h) -> None:
        """Une graine avec des checks de boutique exige un jeu v9 compilé avec les boutiques et les hachages de ses
        articles lus dans la ROM du joueur (format 17) : sinon ces locations sont impossibles (l'achat donnerait l'objet
        d'origine, aucun bit) -> état « Verrous incompatibles » (rien n'est lié, livré ni envoyé), comme un verrou
        manquant (§20)."""
        resolution = self._preparer_boutiques() if self.catalogue.boutiques else "pretes"
        manquantes = bool(self.catalogue.boutiques) and (await self._etat_boutiques(h) != "actives"
                                                         or resolution != "pretes")
        if manquantes != self.boutiques_manquantes:
            self.boutiques_manquantes = manquantes
            if manquantes and resolution != "pretes":
                self.log.warning("Boutiques : hachages des articles pas encore lus dans la ROM du joueur (%s) : "
                                 "partie en attente", resolution)
            elif manquantes:
                pourquoi = ("jeu v%d" % h.version if self._boutiques_etat[1] == "jeu_ancien"
                            else "build compilé sans les boutiques")
                self.log.error("Boutiques absentes du jeu installé (%s) : la partie a %d checks de boutique ; rien ne "
                               "sera lié, livré ni envoyé. Installer le patch du mod à jour, ou générer une graine avec "
                               "l'option boutiques: aucune.", pourquoi, len(self.catalogue.boutiques))

    async def _ecrire_table(self, h, a_v3: bool) -> None:
        if not self._scout_fait and not self.catalogue.contenus:
            return
        entrees, noms_coffres = self.table_voulue(a_v3)
        scripts, noms_scripts = self.scripts_voulus() if a_v3 else ([], {})
        noms_voulus = self.noms_par_priorite(noms_coffres, noms_scripts, self.distrib.noms() if a_v3 else {})
        places = await self.zone.capacite_noms(h, self._instance) if a_v3 else 0
        noms = dict(noms_voulus[:places])
        signal = (self._instance, len(noms_voulus), places)
        if len(noms_voulus) > places and self.sauvegarde == "liee" and self._noms_perdus != signal:
            self._noms_perdus = signal
            self.log.warning("Noms de vitrine : %d pour %d places dans ce jeu (patch à mettre à jour) : %d nom(s) "
                             "laissés de côté (locations déjà faites d'abord, puis les derniers coffres de la liste), "
                             "qui montreront « Objet Archipelago »",
                             len(noms_voulus), places, len(noms_voulus) - places)
        recompenses = None
        if a_v3 and self.catalogue.recompenses and await self._etat_recompenses(h) == "actives":
            recompenses = self.recompenses_voulues()
        boutiques = None
        if a_v3 and self.catalogue.boutiques and await self._etat_boutiques(h) == "actives":
            boutiques = self.boutiques_voulues() if self.sauvegarde == "liee" else []
        if self.sauvegarde != "liee":
            # sauvegarde non liée (ou aucune) : aucune table qui change le jeu (le jeu v4 les ignore aussi)
            entrees, scripts, noms = [], [], {}
            recompenses = {} if recompenses is not None else None
        if boutiques is not None:
            # table des boutiques (jusqu'à 25 Ko) : écrite à part, seulement si ELLE change (pas à chaque changement des
            # autres tables) ; une table vide ne coûte qu'un mot (`valide` = 0), et seulement pour en retirer une
            cle_b = (self._instance, tuple(boutiques))
            if cle_b != self._boutiques_ecrites and (boutiques or self._boutiques_ecrites is not None):
                await self.zone.ecrire_boutiques(boutiques)
                self.log.info("Table des boutiques écrite : %d article(s)", len(boutiques))
            self._boutiques_ecrites = cle_b if (boutiques or self._boutiques_ecrites is not None) else None
        cle = (self._instance, tuple(entrees), tuple(scripts), tuple(sorted(noms.items())),
               None if recompenses is None else tuple(sorted(recompenses.items())))
        if self._table_ecrite == cle:
            return
        if not entrees and self.catalogue.coffres and self.sauvegarde == "liee":
            self.log.warning("Table des coffres non écrite : boîte v%d sans entrées par index ni hachages TBox",
                             h.version)
        await self.boite.ecrire_table_coffres(entrees)
        if a_v3:
            await self.zone.ecrire_noms(noms)
            if len(scripts) > self.zone.capacites["scripts"]:
                # jeu antérieur aux objets-clés de quête (16 entrées) : les dernières (bit 575, puis sans bit) sont
                # ignorées, leurs objets sont donnés d'origine (archipelago_objets_cles_v11.md §16.4)
                self.log.warning("Table des dons de script : %d entrées pour %d places dans ce jeu (patch à mettre à "
                                 "jour) : les dernières sont ignorées", len(scripts), self.zone.capacites["scripts"])
            await self.zone.ecrire_scripts(scripts[:self.zone.capacites["scripts"]])
        if recompenses is not None:
            await self.zone.ecrire_recompenses(recompenses)
        self._table_ecrite = cle
        self.stats.tables_ecrites += 1
        self.log.info("Tables écrites : %d coffres, %d dons de script, %d noms de vitrine, %s récompenses de quête",
                      len(entrees), len(scripts), len(noms), "-" if recompenses is None else len(recompenses))

    async def _verifier_verrous(self, a_v3: bool) -> None:
        """Verrous compilés dans le jeu (§20, lus une fois par instance) comparés aux verrous que slot_data exige :
        un verrou exigé mais absent fausserait la logique de la graine (elle compte sur un objet qui bloque vraiment)
        -> état « Verrous incompatibles »."""
        if self._verrous_compiles is None or self._verrous_compiles[0] != self._instance:
            compiles = bp.verrous_compiles(await self.zone.lire_verrous()) if a_v3 else None
            self._verrous_compiles = (self._instance, compiles)
            self.log.info("Verrous compilés dans le jeu : %s", "aucune liste publiée (jeu sans verrous)"
                          if compiles is None else f"{compiles:#x}")
        compiles = self._verrous_compiles[1] or 0
        # invités de l'Auberge : le n° FONCTION_INVITES n'est jamais publié dans `compiles` (un client d'avant les
        # invités refuse donc la graine) ; ici il se lit dans la zone des invités, une fois par instance
        fonctions = set(self.catalogue.fonctions) - {bp.FONCTION_INVITES, bp.FONCTION_ETENDUES}
        manquants = sorted(k for k in set(self.catalogue.verrous) | fonctions if not compiles >> k & 1)
        # lot 17 : n° de `manquants` qui sont des VERROUS (pour le nom seulement : `manquants` garde les n°)
        m_verrous = [k for k in self.catalogue.verrous if not compiles >> k & 1]
        if self.catalogue.invites or bp.FONCTION_INVITES in self.catalogue.fonctions:
            if self._invites_compiles is None or self._invites_compiles[0] != self._instance:
                h = self.entete
                bits = await self.zone.lire_invites_compile() \
                    if a_v3 and h is not None and self.zone.invites_disponibles(h) else None
                self._invites_compiles = (self._instance, bits)
                self.log.info("Invités de l'Auberge compilés dans le jeu : %s",
                              "non (jeu antérieur ou compilé sans)" if bits is None else f"{bits:#x}")
            if not (self._invites_compiles[1] or 0) & bp.INVITES_COMPILE:
                manquants = sorted(manquants + [bp.FONCTION_INVITES])
        # lot 14 : liste de plus de 32 invités, ou invité à ligne de taux : bits de ApInvites2 lus une fois par
        # instance, seulement pour une telle graine ; patch sans la liste à 64 ou sans le taux par invité (d'avant le
        # lot 12 de la V3, ou zone non publiée) : refus, même si la graine n'avait pas listé la fonction 38
        besoin2 = self._invites2_voulus()
        if besoin2:
            if self._invites2_compiles is None or self._invites2_compiles[0] != self._instance:
                h = self.entete
                lu = await self.zone.lire_invites2_compile() \
                    if a_v3 and h is not None and self.zone.invites2_disponibles(h) else None
                self._invites2_compiles = (self._instance, lu)
                self.log.info("Invités de l'Auberge de la V3 (liste à 64, taux par invité) compilés dans le jeu : %s",
                              "non (jeu d'avant le lot 12 de la V3)" if lu is None else f"{lu:#x}")
            if (self._invites2_compiles[1] or 0) & besoin2 != besoin2 and bp.FONCTION_INVITES_V3 not in manquants:
                manquants = sorted(manquants + [bp.FONCTION_INVITES_V3])
        # fonctions étendues (n° >= 32) : lues dans ApPnj::fonctions, une fois par instance, seulement si la graine en
        # exige ; le n° 22 seul (graine d'un APWorld plus récent que ce client ?) ne demande rien de plus
        connues = bp.FONCTIONS_CLIENT_CONNUES | FONCTIONS_CLIENT_LOT3
        if self.catalogue.fonctions_etendues - connues:
            if self._etendues_compilees is None or self._etendues_compilees[0] != self._instance:
                h = self.entete
                await self._lire_etendues(a_v3)
            # (les n° « client » connus de ce client, jamais publiés par le jeu, ne demandent rien au jeu)
            manquants = sorted(set(manquants) | {n for n in self.catalogue.fonctions_etendues - connues
                                                 if not bp.fonction_etendue_compilee(self._etendues_compilees[1], n)})
        # V3 : verrous et options ÉTENDUS (k >= 40, ApVerrous2) : `compiles` lu une fois par instance, seulement si
        # la graine en a ; verrou exigé absent du jeu (patch d'avant la V3 ou compilé sans) : même refus
        c2 = None
        if self._zone2_voulue():
            if self._verrous2_compiles is None or self._verrous2_compiles[0] != self._instance:
                h = self.entete
                lu = await self.zone.lire_verrous2_compiles() \
                    if a_v3 and h is not None and self.zone.verrous2_disponibles(h) else None
                self._verrous2_compiles = (self._instance, lu)
                self.log.info("Verrous étendus compilés dans le jeu : %s",
                              "aucune liste publiée (jeu d'avant la V3)" if lu is None else f"{lu:#x}")
            c2 = self._verrous2_compiles[1]
            m2 = [k for k in self.catalogue.verrous2 if not bp.verrou2_compile(c2, k)]
            m_verrous += m2
            manquants = sorted(manquants + m2)
            # lot 6 : option étendue 25 (requêtes à transfert) : des locations en dépendent ; bit absent de `compiles`
            # (patch sans la fonction, ou d'avant) : refus, comme un verrou manquant
            if self.catalogue.requetes_transfert and not (c2 or 0) >> bp.OPTION2_TRANSFERT & 1:
                manquants = sorted(manquants + [OPTION2_MANQUANTE_BASE + bp.OPTION2_TRANSFERT])
        # lot 9 : verrous de la DEUXIÈME zone étendue (k >= 56, ApVerrous3) : 16 octets lus une fois par instance,
        # seulement si la graine en a ; zone non publiée (patch d'avant le lot 5) ou verrou non compilé : même refus
        if self.catalogue.verrous3:
            if self._verrous3_compiles is None or self._verrous3_compiles[0] != self._instance:
                h = self.entete
                lu = await self.zone.lire_verrous3_compiles() \
                    if a_v3 and h is not None and self.zone.verrous3_disponibles(h) else None
                self._verrous3_compiles = (self._instance, lu)
                self.log.info("Verrous de la deuxième zone étendue compilés dans le jeu : %s",
                              "zone non publiée (jeu d'avant le lot 5 de la V3)" if lu is None else f"{lu:#x}")
            c3 = self._verrous3_compiles[1]
            m3 = [k for k in self.catalogue.verrous3 if not bp.verrou3_compile(c3, k)]
            m_verrous += m3
            manquants = sorted(manquants + m3)
        # lot 20 : pièces spéciales du Crank-a-kai (option étendue 32, zone ApPieces) : des locations en dépendent.
        # 16 octets lus une fois par instance, seulement pour une telle graine ; zone non publiée (patch d'avant le
        # lot 19), option non compilée ou une des quatre parties absente : refus (code 132) ; patch qui ne lit pas
        # l'ordre de sortie de la graine (lot 19 seul), ou graine sans ordre lisible : refus (code 196)
        # lot 21 : la même lecture sert aux photos de Ψ Blasters (option étendue 33, `photos_blasters`) : option non
        # compilée : refus (code 133) ; graine à pièces générée depuis le lot 21 (fonction 47 exigée : Bananar à la
        # Pièce bleu ciel) devant un patch sans la ligne de tirage : refus (code 197)
        train_absent = False                     # lot 22 : fréquence du train doré absente du jeu (avertissement)
        if self.catalogue.pieces_speciales or self.catalogue.photos_blasters or self.catalogue.train_dore > 1 \
                or self.catalogue.blasters_editions:
            if self._pieces_compile is None or self._pieces_compile[0] != self._instance:
                h = self.entete
                lu = await self.zone.lire_pieces_compile() \
                    if a_v3 and h is not None and self.zone.pieces_disponibles(h) else None
                self._pieces_compile = (self._instance, lu)
                self.log.info("Pièces spéciales du Crank-a-kai compilées dans le jeu : %s",
                              "non (jeu d'avant le lot 19 de la V3)" if lu is None else f"{lu[0]:#x}, options {lu[1]:#x}")
            lu = self._pieces_compile[1]
            if self.catalogue.pieces_speciales:
                if lu is None or lu[0] & bp.PIECES_TOUT != bp.PIECES_TOUT or not lu[1] & bp.PIECES_OPTION:
                    manquants = sorted(manquants + [bp.PIECES_OPTION_MANQUANTE])
                elif not lu[0] & bp.PIECES_ORDRE or not self.catalogue.pieces_ordre:
                    manquants = sorted(manquants + [bp.PIECES_ORDRE_MANQUANT])
                elif bp.FONCTION_LOT21 in self.catalogue.fonctions_etendues and not lu[0] & bp.PIECES_BLEU:
                    manquants = sorted(manquants + [bp.PIECES_BLEU_MANQUANT])
            if self.catalogue.photos_blasters and (
                    lu is None or not lu[0] & bp.PIECES_PHOTOS or not lu[1] & bp.PIECES_OPTION_PHOTOS):
                manquants = sorted(manquants + [bp.PHOTOS_OPTION_MANQUANTE])
            # ap/blasters-terrains-apworld : option étendue 35 (Jiganyan / Komak jouables seul) non compilée : refus
            if self.catalogue.blasters_editions and (lu is None or not lu[1] & bp.PIECES_OPTION_EDITIONS):
                manquants = sorted(manquants + [bp.EDITIONS_OPTION_MANQUANTE])
            train_absent = self.catalogue.train_dore > 1 and (
                lu is None or not lu[0] & bp.PIECES_TRAIN_REGLAGE or not lu[1] & bp.PIECES_OPTION_TRAIN)
        options = bp.options_actives(self.catalogue.bingo_kai_infini or self.catalogue.pieces_speciales)
        options_absentes = sorted(k for k in range(32) if options >> k & 1 and not compiles >> k & 1)
        # (option 26, DeathLink de la Terr'heure / de Blasters : absente du jeu, on avertit sans refuser ; les morts
        # du mode ne partent simplement pas)
        options2 = self._options2_confort()
        options_absentes += [100 + k for k in range(24, 31) if options2 >> k & 1 and not (c2 or 0) >> k & 1]
        # lot 17 : options étendues 29 (revanches et boss de la Voie sans limite de jour) et 30 (tirage dirigé) : une
        # option compilée peut avoir perdu une de ses FONCTIONS (29 : 41, 43, 44 ; 30 : 42 ; patch d'entre deux lots, ou
        # compilé sans) : ApPnj::fonctions lu une fois par instance (la même lecture que pour une graine qui exige
        # des fonctions étendues), puis avertissement par fonction absente ; jamais de refus (confort)
        portees = bp.fonctions_options2(options2 & (c2 or 0))
        if portees:
            if self._etendues_compilees is None or self._etendues_compilees[0] != self._instance:
                await self._lire_etendues(a_v3)
            options_absentes += [bp.OPTION_FONCTION_MANQUANTE_BASE + n for n in portees
                                 if not bp.fonction_etendue_compilee(self._etendues_compilees[1], n)]
        # lot 16 : chance d'amitié réglable (option `amitie` de la graine, zone ApAmitie) : 8 octets lus une fois par
        # instance, seulement si la graine la règle ; absente du jeu (patch d'avant, ou compilé sans) : on avertit sans
        # refuser, le jeu garde son taux (aucune location n'en dépend)
        if self.catalogue.amitie:
            if self._amitie_compilee is None or self._amitie_compilee[0] != self._instance:
                h = self.entete
                lu = await self.zone.lire_amitie_compilee() \
                    if a_v3 and h is not None and self.zone.amitie_disponible(h) else False
                self._amitie_compilee = (self._instance, lu)
                self.log.info("Chance d'amitié réglable compilée dans le jeu : %s", "oui" if lu else
                              "non (jeu d'avant le lot 16 de la V3, ou compilé sans)")
            if not self._amitie_compilee[1]:
                options_absentes.append(bp.OPTION_AMITIE_MANQUANTE)
        # lot 22 : fréquence du train doré (option de confort) absente du jeu : on avertit sans refuser
        if train_absent:
            options_absentes.append(bp.OPTION_TRAIN_MANQUANTE)
        # lot B1 : Bingo-kai aléatoire (option de confort) : zone ApBingo absente ou non compilée (8 octets lus une fois
        # par instance, seulement pour une graine qui a l'option) : on avertit sans refuser (300 + 51)
        if self.bingo.actif and not await self.bingo.compilee(self.entete if a_v3 else None):
            options_absentes.append(bp.OPTION_FONCTION_MANQUANTE_BASE + bp.FONCTION_BINGO_MELANGE)
        if options_absentes != self.options_absentes:
            self.options_absentes = options_absentes
            if options_absentes:                     # confort seulement : aucune location n'en dépend, rien de refusé
                self.log.warning("Option(s) %s choisie(s) dans la graine mais absente(s) du jeu installé (patch trop "
                                 "ancien ou compilé sans) : le jeu garde son comportement d'origine.",
                                 ", ".join(self._nom_option(k) for k in options_absentes))
        # lot 17 : noms par sorte. Un n° de `manquants` est un verrou s'il vient d'une des trois listes de verrous de
        # la graine, une option s'il vaut 100 + bit, une fonction sinon (n° de `fonctions_exigees`, 23 et 38 compris) ;
        # un même n° peut être à la fois un verrou étendu et une fonction étendue manquants (41 à 45) : les deux noms
        reste = list(manquants)
        for k in m_verrous:
            reste.remove(k)
        detail = [(bp.SORTE_VERROU, k) for k in sorted(m_verrous)] \
            + [(bp.SORTE_OPTION if k >= OPTION2_MANQUANTE_BASE else bp.SORTE_FONCTION, k) for k in reste]
        if manquants != self.verrous_manquants or detail != self.manquants_detail:
            self.verrous_manquants = manquants
            self.manquants_detail = detail
            if manquants:
                self.log.error("Verrous incompatibles : la partie exige %s, absent(s) du jeu installé (patch trop ancien "
                               "ou compilé sans) ; rien ne sera lié, livré ni envoyé. Installer le patch du mod à jour, "
                               "ou générer une graine sans ce(s) verrou(s) (option verrous_actifs).",
                               ", ".join(bp.nom_manquant(sorte, k) for sorte, k in detail))

    async def _ecrire_verrous(self) -> None:
        """Verrous (§16) : actifs = verrous de slot_data ; recu[k] = l'objet est dans ReceivedItems. Verrou progressif
        (rangs de montre, k = 18) : recu[k] = NOMBRE d'exemplaires dans ReceivedItems. Graine de format 7 : entrée
        « rangs_d » (k = 19, même objet) = mode « portes D » du jeu (rang AP = ce nombre, portes D fermées) ; recu[19]
        vaut 0 / 1 et n'est pas lu par le jeu. Graine antérieure (sans k = 19) : rang AP = D + ce nombre. Graine de
        format 20 : entrée « rangs_reel » (k = 20, même objet) = mode « rang réel » : le JEU monte le vrai rang de la
        montre à min(recu[18], A) sur le terrain de la sauvegarde liée (idempotent : une sauvegarde antérieure
        rechargée est remontée par le jeu, sans rien de plus à écrire ici) ; recu[20] vaut 0 / 1, non lu par le jeu.
        Graine de format 21 : entrée « velo_reel » (k = 21, objet Vélo) = mode « vélo réel » : le JEU donne vraiment le
        vélo quand recu[12] passe à 1 (flags 39 / 40, objet vélo ; une sauvegarde antérieure rechargée est remise en
        état par le jeu) ; recu[21] vaut 0 / 1, non lu par le jeu."""
        recus = collections.Counter(o.item for o in self.objets)
        actifs = 0
        recu: dict[int, bool | int] = {}
        for k, objet in self.catalogue.verrous.items():
            if 0 <= k < self.zone.capacites["verrous"]:
                actifs |= 1 << k
                recu[k] = min(recus[objet], 255) if k in bp.VERROUS_PROGRESSIFS else objet in recus
        # options du joueur appliquées par le jeu (bits 24.., sans objet : recu[] non concerné) ; un jeu qui ne les
        # compile pas ignore le bit (jeu d'origine), aucune location n'en dépend
        # (lot 20 : les pièces spéciales forcent le Bingo-kai infini, même pour un slot_data qui l'aurait oublié)
        actifs |= bp.options_actives(self.catalogue.bingo_kai_infini or self.catalogue.pieces_speciales)
        if self.sauvegarde != "liee" or self.verrous_manquants:
            actifs = 0                                   # sauvegarde non liée : aucun verrou (jeu normal)
        cle = (self._instance, actifs, tuple(sorted(recu.items())))
        if cle == self._verrous_ecrits:
            return
        await self.zone.ecrire_verrous(actifs, recu)
        self._verrous_ecrits = cle
        self.log.info("Verrous : actifs %#x, reçus %s", actifs, sorted(k for k, v in recu.items() if v))

    async def _ecrire_verrous2(self) -> None:
        """Verrous et options ÉTENDUS de la V3 (§34) : actifs = verrous étendus de slot_data (bit k - 40) et options
        étendues (bit 24 : Tunnel sans fin sans limite) ; recu[k - 40] = l'objet est dans ReceivedItems ; `ident` =
        identifiant de la partie. Seulement si la graine en a ET si le jeu publie la liste (lue une fois par instance
        par `_verifier_verrous`) ; écrit quand quelque chose change : aucun paquet périodique. Une graine d'avant la
        V3 n'écrit jamais ici (un état laissé par une autre graine est ignoré par le jeu : `ident` différent).
        Lot 9 : option étendue 26 (DeathLink de la Terr'heure / de Blasters), écrite avec les autres pour une graine
        de la V3 dont le DeathLink est activé (`_mort_orge_voulue`), masquée par `compiles` : aucun paquet de plus."""
        if not self._zone2_voulue() \
                or self._verrous2_compiles is None \
                or self._verrous2_compiles[0] != self._instance or self._verrous2_compiles[1] is None:
            return
        compiles = self._verrous2_compiles[1]
        recus = {o.item for o in self.objets}
        actifs = 0
        recu: dict[int, bool] = {}
        for k, objet in self.catalogue.verrous2.items():
            actifs |= 1 << (k - bp.VERROU2_BASE)
            recu[k] = objet in recus
        actifs |= bp.options2_actives(self.catalogue.tunnel_sans_limite) & compiles
        # lot 6 : option étendue 25 (requêtes à transfert), écrite avec les autres : aucun paquet de plus
        actifs |= bp.options2_transfert(self.catalogue.requetes_transfert) & compiles
        actifs |= bp.options2_mort_orge(self._mort_orge_voulue()) & compiles
        # lot 17 : options étendues 29 et 30 (confort de l'après-jeu), écrites avec les autres : aucun paquet de plus
        actifs |= bp.options2_confort_aj(self.catalogue.revanches_sans_limite,
                                         self.catalogue.tirage_dirige_voie) & compiles
        # fix/amitie-oni : « amitié assurée » pose aussi l'option étendue 28 (don assuré des Oni de la Voie du
        # mystère : leur amitié est un don de script au hasard, pas le tirage de fin de combat) ; aucun paquet de plus
        actifs |= bp.options2_amitie_oni(self.catalogue.amitie) & compiles
        if self.sauvegarde != "liee" or self.verrous_manquants:
            actifs = 0                                   # sauvegarde non liée : aucun verrou (jeu normal)
        cle = (self._instance, actifs, tuple(sorted(recu.items())), self.ident_partie or 0)
        if cle == self._verrous2_ecrits:
            return
        await self.zone.ecrire_verrous2(actifs, recu, self.ident_partie or 0)
        self._verrous2_ecrits = cle
        self.log.info("Verrous étendus : actifs %#x, reçus %s", actifs, sorted(k for k, v in recu.items() if v))

    def _nom_option(self, k: int) -> str:
        """Nom d'une option de `options_absentes` : k < 100 : ApVerrous ; 100 + bit : ApVerrous2 ; 200 : amitié."""
        if k == bp.OPTION_AMITIE_MANQUANTE:
            return f"Chance d'amitié ({bp.AMITIE_NOMS.get(self.catalogue.amitie, '?')})"
        if k == bp.OPTION_TRAIN_MANQUANTE:
            return f"Fréquence du train doré ({bp.TRAIN_NOMS.get(self.catalogue.train_dore, '?')})"
        nom = bp.nom_option_absente(k)                   # 100 + bit : ApVerrous2 ; 300 + n : fonction d'une option
        return nom if nom is not None else bp.NOMS_OPTIONS.get(k, f"k={k}")

    def _options2_confort(self) -> int:
        """Bits des options étendues de CONFORT que la graine demande (absentes du jeu : avertissement seulement) :
        24 Tunnel sans fin, 26 DeathLink du mode, 29 revanches et boss de la Voie, 30 tirage dirigé (lot 17),
        28 don assuré des Oni de la Voie du mystère (posé par « amitié assurée », fix/amitie-oni)."""
        c = self.catalogue
        return bp.options2_actives(c.tunnel_sans_limite) | bp.options2_mort_orge(self._mort_orge_voulue()) \
            | bp.options2_confort_aj(c.revanches_sans_limite, c.tirage_dirige_voie) | bp.options2_amitie_oni(c.amitie)

    async def _lire_etendues(self, a_v3: bool) -> None:
        """ApPnj::fonctions (fonctions étendues, n° >= 32), lu UNE fois par instance du jeu : pour une graine qui en
        exige, ou (lot 17) qui demande une option étendue portée par des fonctions (29, 30)."""
        h = self.entete
        bits = await self.zone.lire_fonctions_etendues() \
            if a_v3 and h is not None and self.zone.pnj_disponibles(h) else None
        self._etendues_compilees = (self._instance, bits)
        self.log.info("Fonctions étendues compilées dans le jeu : %s",
                      "aucune liste publiée (jeu antérieur)" if bits is None else f"{bits:#x}")

    async def _ecrire_amitie(self) -> None:
        """Chance d'amitié (lot 16, §43) : `reglage` = option `amitie` de la graine, `ident` = identifiant de la
        partie. Seulement si la graine la règle ET si le jeu publie la zone (lue une fois par instance par
        `_verifier_verrous`) ; un paquet de 8 octets, écrit quand quelque chose change : aucun paquet périodique.
        Sauvegarde non liée ou verrou manquant : réglage 0 (taux du jeu), comme les verrous. Une graine sans réglage
        n'écrit jamais ici (un état laissé par une autre graine est ignoré par le jeu : `ident` différent)."""
        if not self.catalogue.amitie or self._amitie_compilee is None \
                or self._amitie_compilee[0] != self._instance or not self._amitie_compilee[1]:
            return
        reglage = self.catalogue.amitie
        if self.sauvegarde != "liee" or self.verrous_manquants:
            reglage = bp.AMITIE_NORMAL
        cle = (self._instance, reglage, self.ident_partie or 0)
        if cle == self._amitie_ecrite:
            return
        await self.zone.ecrire_amitie(reglage, self.ident_partie or 0)
        self._amitie_ecrite = cle
        self.log.info("Chance d'amitié : %s", bp.AMITIE_NOMS[reglage])

    def pieces_recues(self) -> list[int]:
        """Nombre d'objets AP de chaque famille de pièces spéciales (`bp.FAMILLES_PIECES`) dans les objets reçus du
        serveur, quel que soit leur don (une Pile ou passe trouvée à son emplacement d'origine non substitué compte :
        le jeu l'a donnée lui-même). Reconnus par le hachage de leur objet du jeu (`dons` de slot_data)."""
        famille = {f[1]: i for i, f in enumerate(bp.FAMILLES_PIECES)}
        recues = [0] * bp.NB_PIECES_FAMILLES
        for o in self.objets:
            don = self.catalogue.objets.get(o.item)
            if don is not None and don.type == bp.DON_OBJET and don.hash in famille:
                recues[famille[don.hash]] += 1
        return recues

    async def _ecrire_pieces(self) -> None:
        """Pièces spéciales du Crank-a-kai (lot 20, §45) : `dons_valides` (numéro du dernier don compté) PUIS
        `recues` (compteurs par famille), l'ordre de sortie des 16 de la Pièce 5 étoiles, `ident`, et le mot
        d'options EN DERNIER. Seulement si la graine a l'option ET si le jeu publie tout ce qu'elle exige (lu une
        fois par instance par `_verifier_verrous`) ; seuls les champs qui ont changé sont réécrits, quand ils
        changent : aucun paquet périodique. `dons_valides` n'avance qu'avec les compteurs (le jeu attend d'avoir
        traité ce don avant de rendre une pièce : une borne plus ancienne est toujours sûre). Sauvegarde non liée ou
        verrou manquant : option 0 (jeu d'origine), comme les verrous. Une graine sans l'option n'écrit jamais ici
        (un état laissé par une autre graine est ignoré par le jeu : `ident` différent)."""
        if not (self.catalogue.pieces_speciales or self.catalogue.photos_blasters or self.catalogue.train_dore > 1
                or self.catalogue.blasters_editions) \
                or self._pieces_compile is None \
                or self._pieces_compile[0] != self._instance or self._pieces_compile[1] is None:
            return
        en_vigueur = self.sauvegarde == "liee" and not self.verrous_manquants
        option = en_vigueur and self.catalogue.pieces_speciales
        # lot 21 : option étendue 33 (photos de Ψ Blasters), bit 1 du même mot, écrit avec lui (aucun paquet de plus)
        photos = en_vigueur and self.catalogue.photos_blasters
        # ap/blasters-terrains-apworld : option étendue 35, bit 3 du même mot
        editions = en_vigueur and self.catalogue.blasters_editions
        # lot 22 : fréquence du train doré (réglage k écrit avant le mot d'options ; bit 2 hors vigueur : nul) ; une
        # option absente du jeu (avertie par `_verifier_verrous`) n'est pas écrite
        lu = self._pieces_compile[1]
        train = self.catalogue.train_dore if en_vigueur and lu[0] & bp.PIECES_TRAIN_REGLAGE \
            and lu[1] & bp.PIECES_OPTION_TRAIN else 1
        recues = self.pieces_recues() if self.catalogue.pieces_speciales else [0] * bp.NB_PIECES_FAMILLES
        ident = self.ident_partie or 0
        ordre = self.catalogue.pieces_ordre or None
        cle = (self._instance, option, tuple(recues), ident, ordre, photos, train, editions)
        if self._pieces_ecrites is not None and cle == self._pieces_ecrites[0]:
            return
        avant = self._pieces_ecrites[1] if self._pieces_ecrites is not None \
            and self._pieces_ecrites[0][0] == self._instance else {}
        dons_valides = len(self.objets)
        toutes = bp.ecritures_pieces(option, recues, dons_valides, ident, ordre, photos, train, editions)
        # la borne des dons ne se réécrit qu'avec les compteurs (ou la première fois)
        compteurs_changes = avant.get(bp.OFF_PIECES + bp.PIECES_OFF_RECUES) != toutes[1][1]
        ecritures = [(off, octets) for off, octets in toutes
                     if avant.get(off) != octets
                     and (off != bp.OFF_PIECES + bp.PIECES_OFF_DONS_VALIDES or compteurs_changes or not avant)]
        if ecritures:
            await self.zone.ecrire_pieces(ecritures)
        nouveau = dict(avant)
        nouveau.update(dict(ecritures))
        self._pieces_ecrites = (cle, nouveau)
        self.log.info("Pièces spéciales : option %s%s, reçues %s (dons comptés jusqu'au n° %d)",
                      "posée" if option else "retirée",
                      "" if not self.catalogue.photos_blasters else
                      (" ; photos de Ψ Blasters tenues pour prises" if photos else " ; photos de Ψ Blasters : non"),
                      ", ".join(f"{bp.FAMILLES_PIECES[f][0]} {n}" for f, n in enumerate(recues) if n) or "aucune",
                      dons_valides)
        if self.catalogue.blasters_editions:         # ap/blasters-terrains-apworld
            self.log.info("Ψ Blasters : terrains d'autres éditions (Jiganyan, Komak) %s",
                          "jouables seul" if editions else "pas en vigueur (sauvegarde non liée ou verrou manquant)")
        if self.catalogue.train_dore > 1:            # lot 22
            self.log.info("Train doré : %d fois sur 10%s", train, "" if train > 1 else " (réglage pas en vigueur)")

    def _mort_orge_voulue(self) -> bool:
        """Lot 9 : la graine est une graine de la V3 qui demande le DeathLink du mode Terr'heure / Blasters
        (`deathlink_orge` de slot_data, absent d'une graine de la V2) ET son option DeathLink est activée."""
        return bool(self.catalogue.deathlink_orge and self.catalogue.death_link)

    def _zone2_voulue(self) -> bool:
        """La graine a un verrou ou une option étendus de la zone ApVerrous2 (lue et écrite seulement alors)."""
        c = self.catalogue
        return bool(c.verrous2 or c.tunnel_sans_limite or c.requetes_transfert or self._mort_orge_voulue()
                    or c.revanches_sans_limite or c.tirage_dirige_voie        # lot 17 : options étendues 29, 30
                    or bp.options2_amitie_oni(c.amitie))                      # fix/amitie-oni : option 28

    async def _ecrire_verrous3(self) -> None:
        """Verrous de la DEUXIÈME zone étendue (lot 9, §38) : actifs = verrous k >= 56 de slot_data (bit k - 56) ;
        recu[k - 56] = l'objet est dans ReceivedItems ; `ident` = identifiant de la partie. Seulement si la graine en
        a ET si le jeu publie la zone (lue une fois par instance par `_verifier_verrous`) ; `ident` et recu[] d'abord,
        `actifs` EN DERNIER (boite_v3) ; écrit quand quelque chose change : aucun paquet périodique. `actifs` = 0 si
        la sauvegarde n'est pas liée ou s'il manque un verrou."""
        if not self.catalogue.verrous3 or self._verrous3_compiles is None \
                or self._verrous3_compiles[0] != self._instance or self._verrous3_compiles[1] is None:
            return
        recus = collections.Counter(o.item for o in self.objets)
        actifs = 0
        recu: dict[int, bool] = {}
        for k, objet in self.catalogue.verrous3.items():
            actifs |= 1 << (k - bp.VERROU3_BASE)
            recu[k] = bp.recu_verrou3(k, recus[objet], self.catalogue.exemplaires3)   # Mirapo de poche : 2 exemplaires
        if self.sauvegarde != "liee" or self.verrous_manquants:
            actifs = 0
        cle = (self._instance, actifs, tuple(sorted(recu.items())), self.ident_partie or 0)
        if cle == self._verrous3_ecrits:
            return
        await self.zone.ecrire_verrous3(actifs, recu, self.ident_partie or 0)
        self._verrous3_ecrits = cle
        self.log.info("Verrous de la deuxième zone étendue : actifs %#x, reçus %s", actifs,
                      sorted(k for k, v in recu.items() if v))

    # ------------------------------------------------------------------------------ invités de l'Auberge des voyageurs
    def invite_declare(self, inv: Invite) -> bool:
        """Déclencheur de l'invité rempli. « requetes » : la graine a des requêtes-checks et le serveur les tient
        TOUTES pour cochées (critère (i) de l'analyse : couvre les services, survit aux rechargements). « objet » :
        son invitation est dans les objets reçus du serveur (ReceivedItems : survit aux rechargements et aux
        relancements, vaut pour toute sauvegarde liée à la partie). Déclencheur inconnu de ce client (APWorld plus
        récent) : jamais."""
        r = self.reseau
        if r is None:
            return False
        if inv.declencheur == "objet":
            return inv.objet != 0 and any(o.item == inv.objet for o in self.objets)
        if inv.declencheur != "requetes" or not inv.locations:
            return False
        return inv.locations <= r.locations_verifiees

    # ------------------------------------------------------- Yo-kai d'évènement à leur emplacement d'origine (§33)
    def evenement_masque(self) -> int:
        """Bits de ApPnj::ev_declares : Yo-kai dont l'objet AP (slot_data `evenement_places`) est dans les objets
        reçus du serveur (ReceivedItems : vaut pour toute sauvegarde liée, survit aux relancements)."""
        recus = {o.item for o in self.objets}
        return sum(1 << k for k, objet in self.catalogue.evenement_places.items() if objet in recus)

    async def _ecrire_evenement(self) -> None:
        """Objets reçus -> ApPnj::ev_declares + ev_ident, seulement si la graine en a, si le jeu publie la fonction
        étendue 34 et si rien ne manque. Écrit quand le masque change (objet reçu, nouvelle instance) : aucun paquet
        périodique. Écrit même hors sauvegarde liée : le masque vise l'identifiant de partie (`ev_ident`) et le jeu
        l'ignore pour toute autre sauvegarde ; ainsi un PNJ est là dès le chargement de la sauvegarde, sans attendre
        la liaison de ce tour."""
        if not self.catalogue.evenement_places or self.verrous_manquants or not self.ident_partie \
                or self._etendues_compilees is None or self._etendues_compilees[0] != self._instance \
                or not bp.fonction_etendue_compilee(self._etendues_compilees[1], bp.FONCTION_EVENEMENT_PLACE):
            return
        cle = (self._instance, self.evenement_masque(), self.ident_partie)
        if cle == self._evenement_ecrit:
            return
        await self.zone.ecrire_evenement(cle[1], self.ident_partie)
        self._evenement_ecrit = cle
        self.log.info("Yo-kai d'évènement à leur place : %s",
                      ", ".join(bp.EV_NOMS[k] for k in range(bp.EV_NOMBRE) if cle[1] >> k & 1) or "aucun objet reçu")

    def _invites2_voulus(self) -> int:
        """Bits INVITES2_* de ApInvites2 dont la graine a besoin : liste à 64 (plus de 32 invités dans la graine),
        taux par invité (un invité à ligne de taux). 0 : toute graine de la V2, rien n'est lu ni écrit là."""
        invs = self.catalogue.invites
        # (lot 20 : le taux par invité, INVITES2_TAUX, n'est plus demandé par aucune graine)
        return bp.INVITES2_CAP64 if len(invs) > bp.CAP_INVITES else 0

    def invites_arrivees(self) -> list[int]:
        """Graine à ordre de RÉCEPTION (lot 14) : n° du Médaillium des invités à invitation dans l'ordre où leurs
        invitations sont arrivées, pour CETTE partie. Mémoire de `liaisons.json` (clé de la partie), complétée EN FIN
        DE LISTE seulement, d'après la liste des objets reçus du serveur (ordre du serveur : le même à chaque
        connexion, « ajout seulement ») : un invité déjà noté ne change JAMAIS de place, même si le serveur rejouait
        ses objets dans un autre ordre (sauvegarde du serveur perdue, objets renvoyés par `/send`). Graine de la V2
        (ordre de la liste) ou partie inconnue : liste vide, rien n'est lu ni écrit."""
        ident = self.ident_partie
        if self.catalogue.invites_ordre != ORDRE_INVITES_RECEPTION or not ident:
            return []
        if self._invites_arrivees is None or self._invites_arrivees[0] != ident:
            self._invites_arrivees = (ident, self.liaisons.lire_ordre_invites(ident))
        ordre = self._invites_arrivees[1]
        par_objet = {inv.objet: inv.medaille for inv in self.catalogue.invites
                     if inv.declencheur == "objet" and inv.objet}
        connus, nouveaux = set(ordre), []
        for o in self.objets:                                # ordre du serveur
            m = par_objet.get(o.item)
            if m is not None and m not in connus:
                connus.add(m)
                nouveaux.append(m)
        if nouveaux:
            ordre += nouveaux
            self.liaisons.ecrire_ordre_invites(ident, ordre)
            self.log.info("Invités de l'Auberge : ordre d'arrivée complété (%s) ; %d arrivé(s)",
                          ", ".join(f"n° {m}" for m in nouveaux), len(ordre))
        return ordre

    def invites_ordonnes(self) -> list[Invite]:
        """Invités dans l'ordre de la liste du JEU. Graine de la V2 (ordre de la liste) : ceux de la graine, dans
        l'ordre de `slot_data.invites`, déclarés ou non : exactement la liste de la V2. Graine à ordre de réception :
        d'abord l'invité à déclencheur « requetes » s'il existe (Pandanoko : il loge dans la Suite, ne compte pas dans
        les neuf chambres et n'attend jamais ; rang 0 fixe, déclaré ou non), puis les invités à invitation ARRIVÉS,
        dans l'ordre d'arrivée (`invites_arrivees`). Un invité pas encore arrivé n'est pas dans la liste : il y entre
        à la FIN quand son invitation est reçue, donc aucun rang déjà attribué ne bouge (mémoire des chambres du jeu,
        par rang ; annonces et chambres du client, par n° du Médaillium)."""
        invs = self.catalogue.invites
        if self.catalogue.invites_ordre != ORDRE_INVITES_RECEPTION:
            return list(invs)
        par_medaille = {inv.medaille: inv for inv in invs if inv.declencheur == "objet"}
        fixes = [inv for inv in invs if inv.declencheur != "objet"]
        return (fixes + [par_medaille[m] for m in self.invites_arrivees() if m in par_medaille])[:bp.CAP_INVITES_V3]

    def invites_voulus(self) -> list[tuple[int, int, int, int]]:
        """Liste à écrire dans le jeu : (CHARA_PARAM, n° du Médaillium, drapeaux, chambre) dans l'ordre du jeu
        (`invites_ordonnes` : ordre de la graine pour une graine de la V2, ordre de réception sinon).
        `chambre` : celle que le jeu a attribuée à l'invité dans la sauvegarde liée (mémoire de liaison ; 0 : aucune,
        et toujours 0 pour Pandanoko, qui loge dans la Suite) ; un patch antérieur ignore cet octet. Drapeaux : bits
        4..7 = ligne de taux de l'invité (0 pour toute graine de la V2 : les drapeaux de la V2)."""
        l = self._liaison
        annonces = l.invites_annonces if l is not None else set()
        chambres = l.invites_chambres if l is not None else {}
        return [(inv.param, inv.medaille,
                 bp.drapeaux_invite((bp.INVITE_DECLARE if self.invite_declare(inv) else 0)
                                    | (bp.INVITE_ANNONCE if inv.medaille in annonces else 0), 0),
                 0 if inv.param == bp.INVITES_PARAM_PNJ else chambres.get(inv.medaille, 0))
                for inv in self.invites_ordonnes()]

    async def _ecrire_invites(self, h) -> None:
        """Liste des invités -> ApInvites, pour la sauvegarde LIÉE seulement et seulement si le jeu publie la fonction
        (un jeu antérieur n'a rien là). Écrite quand elle change (déclencheur rempli, annonce faite, autre sauvegarde
        liée, nouvelle instance) : aucun paquet périodique. Le jeu revérifie tout (sauvegarde visée et liée, pas
        encore ami) ; hors sauvegarde liée, rien n'est écrit : la liste déjà là vise une autre sauvegarde."""
        if not self.catalogue.invites or self._invites_compiles is None \
                or self._invites_compiles[0] != self._instance \
                or not (self._invites_compiles[1] or 0) & bp.INVITES_COMPILE:
            return
        if self.sauvegarde != "liee" or self._liaison is None or self.verrous_manquants or not h.partie \
                or not self.ident_partie:
            return
        voulus = self.invites_voulus()
        self._maj_invites_fichier(h, voulus)
        cle = (self._instance, self.ident_partie, tuple(voulus))
        if cle == self._invites_ecrits:
            return
        # lot 14 : plus de 32 entrées = suite dans ApInvites2 (jamais sans le bit de la liste à 64 : la graine est
        # refusée avant, `_verifier_verrous`) ; 32 au plus : exactement les écritures de la V2
        compile2 = self._invites2_compiles[1] if self._invites2_compiles is not None \
            and self._invites2_compiles[0] == self._instance else None
        if len(voulus) > bp.CAP_INVITES and not (compile2 or 0) & bp.INVITES2_CAP64:
            return
        self._invites_seq += 1
        await self.zone.ecrire_invites(voulus, self.ident_partie, self._invites_seq, compile2)
        self._invites_ecrits = cle
        declares = [f"n° {m}{' (déjà annoncé)' if d & bp.INVITE_ANNONCE else ''}{f' (chambre {100 + c})' if c else ''}"
                    for _, m, d, c in voulus if d & bp.INVITE_DECLARE]
        self.log.info("Invités de l'Auberge : %d sur %d déclaré(s)%s", len(declares), len(voulus),
                      " : " + ", ".join(declares) if declares else "")

    def _maj_invites_fichier(self, h, voulus) -> None:
        """`invites.json` (tracker de Yo-kai du lanceur) : état de chaque invité pour la sauvegarde liée : « attente »
        (déclencheur pas rempli : `restantes` locations à cocher, ou invitation pas reçue), « present » (`piece` : 0 la
        Suite, réservée à Pandanoko ; 1..9 les chambres 101..109), « file » (déclaré, attend qu'une des neuf chambres
        se libère : `rang` dans la file),
        « ami » (bit du Médaillium de la dernière lecture groupée). Patch courant (Suite réservée, chambres gardées) :
        rien n'est calculé, la chambre est celle que le jeu a signalée (mémoire de liaison) ; patch antérieur : même
        calcul que ce patch-là (`bp.etats_invites`), sans les errants StreetPass du joueur, que le client ne lit pas.
        Écrit seulement quand il change."""
        r = self.reseau
        amis = set()
        if self._medaillium is not None and self._medaillium[0] == h.ident_sauvegarde:
            z = rando.zones_medaillium(self._medaillium[1]).get("ami") or b""
            if len(z) >= rando.TAILLE_MEDAILLIUM:
                amis = {inv.medaille for inv in self.catalogue.invites if z[inv.medaille >> 3] >> (inv.medaille & 7) & 1}
        etats = []
        # la règle d'affectation est celle que le patch publie (Suite réservée à Pandanoko, ou patch antérieur)
        pieces, reservee = bp.regle_invites(self._invites_compiles[1])
        calcul = bp.etats_invites([(p, m, bool(d & bp.INVITE_DECLARE), c) for p, m, d, c in voulus], amis, pieces,
                                  reservee)
        # (ordre du fichier : celui de la graine ; `voulus` est dans l'ordre du jeu, le même pour une graine de la V2)
        reception = self.catalogue.invites_ordre == ORDRE_INVITES_RECEPTION
        par_medaille = {v[1]: e for v, e in zip(voulus, calcul)}
        arrivee = {m: k + 1 for k, m in enumerate(self.invites_arrivees())} if reception else {}
        for inv in self.catalogue.invites:
            e = par_medaille.get(inv.medaille) or {"etat": "ami" if inv.medaille in amis else "attente"}
            restantes = len(inv.locations - r.locations_verifiees) if r is not None else len(inv.locations)
            x = {"medaille": inv.medaille, "location": inv.location, "declencheur": inv.declencheur,
                 "etat": e["etat"], "restantes": restantes, "total": len(inv.locations)}
            if "piece" in e:
                x["piece"] = e["piece"]
            if "rang" in e:
                x["rang"] = e["rang"]
            if inv.medaille in arrivee:
                x["arrivee"] = arrivee[inv.medaille]         # lot 14 : rang d'arrivée (1 = la première invitation reçue)
            etats.append(x)
        cle = (self.ident_partie, h.ident_sauvegarde, json.dumps(etats, sort_keys=True))
        if cle == self._invites_fichier:
            return
        try:
            p = Path(self.stockage.dossier) / FICHIER_INVITES
            tmp = p.with_suffix(".tmp")
            contenu = {"format": FORMAT_INVITES, "horodatage": time.time(),
                       "ident_partie": self.ident_partie, "ident_sauvegarde": h.ident_sauvegarde, "invites": etats}
            if reception:
                contenu["ordre"] = ORDRE_INVITES_RECEPTION   # (clé absente pour une graine de la V2 : fichier d'avant)
            tmp.write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(p)
            self._invites_fichier = cle
        except OSError as ex:
            self.log.warning("invites.json non écrit : %s", ex)

    # ------------------------------------------------------------------------------ randomizer de Yo-kai (R3)
    def _rando_publier(self, statut: str, message: str, niveau: int = logging.INFO, cause: str | None = None) -> None:
        self.rando_cause = cause or statut
        if (statut, message) != (self.rando_statut, self.rando_message):
            self.rando_statut, self.rando_message = statut, message
            self.log.log(niveau, "Randomizer de Yo-kai : %s", message)
        self._rando_fichier_local()

    def _rando_fichier_local(self, jeu: dict | None = None) -> None:
        """`rando_yokai.json` (tracker du lanceur) : réécrit quand le mélange, l'état ou ce que le jeu publie change."""
        etat = {"pret": "actif", "aucun": "aucun", "refuse": "refuse", "base_absente": "refuse"}.get(
            self.rando_statut, "attente")
        # V3, lot M1 : cause en clair (client puis jeu) et état de la sauvegarde, pour la carte « Connexion »
        diag = {"cause": self._rando_cause_jeu or self.rando_cause, "sauvegarde": self.sauvegarde}
        cle = (self.ident_partie, self.rando_statut, self.rando_message,
               None if self.rando_melange is None else self.rando_melange.generation,
               None if jeu is None else tuple(sorted(jeu.items())), tuple(sorted(diag.items())))
        if cle == self._rando_fichier:
            return
        self._rando_fichier = cle
        try:
            rando.ecrire_fichier_local(self.stockage.dossier, self.rando_melange, self.ident_partie, etat,
                                       dict(jeu or {}, message=self.rando_message, **diag))
        except OSError as e:
            self.log.warning("rando_yokai.json non écrit : %s", e)

    def _preparer_rando(self) -> None:
        """Mélange de la graine, une fois par (partie, mode, graine). Base locale absente : générée en tâche de fond
        depuis la ROM configurée (sinon : « Réparer le mod » dans le lanceur)."""
        ry = self.catalogue.rando_yokai
        version = 1 if ry is None else int(ry.get("melange", 1))
        apres_jeu = bool(ry and ry.get("apres_jeu"))
        cle = (self.ident_partie, None if ry is None else ry["mode"], None if ry is None else ry["graine"], version,
               apres_jeu, json.dumps(self.catalogue.yokai_zones, sort_keys=True))
        if cle == self._rando_cle or (self._rando_tache is not None and not self._rando_tache.done()):
            return
        if ry is None:
            self._rando_cle, self.rando_melange = cle, None
            if self.catalogue.rando_yokai_inconnu:
                self._rando_publier("refuse", f"mode de mélange {self.catalogue.rando_yokai_inconnu!r} inconnu de ce "
                                    "client (APWorld plus récent : mettre à jour le mod) : Yo-kai d'origine",
                                    logging.WARNING, cause="mode_inconnu")
                return
            self._rando_publier("aucun", "pas de mélange sur cette partie")
            return
        if version not in rando.VERSIONS_MELANGE:
            self._rando_cle, self.rando_melange = cle, None
            self._rando_publier("refuse", f"mélange de version {version} inconnu de ce client (APWorld plus récent : "
                                "mettre à jour le mod) : Yo-kai d'origine", logging.WARNING, cause="version_inconnue")
            return
        base = rando.charger_base(self.stockage.dossier)
        rom = self.config.rom
        besoin = rando.format_requis(ry["mode"], version)
        if base is not None and base.get("format", 0) < besoin and rom and Path(rom).is_file():
            base = None         # format antérieur (sans les espèces exigées fixées / les emplacements) : régénérée
        if base is None:
            if not rom or not Path(rom).is_file():
                self._rando_cle, self.rando_melange = cle, None
                self._rando_publier("base_absente", "base locale des rencontres absente : « Réparer le mod » dans le "
                                    "lanceur (ROM non configurée)", logging.WARNING)
                return
            self._rando_publier("calcul", "base locale des rencontres générée depuis la ROM…", cause="base_calcul")
            self._rando_tache = asyncio.create_task(asyncio.to_thread(rando.generer_base, rom, self.stockage.dossier))
            self._rando_tache.add_done_callback(self._rando_generee)
            return
        self._rando_cle = cle
        try:
            zones = None
            if version >= rando.VERSION_ZONES:
                # V3, lots M2b : zones des Yo-kai demandés, tirées par la génération ; table de l'APWorld du paquet
                # (même empreinte exigée : sinon une autre version de la table, refus)
                zmod, zg = ck.zones_apworld(), ck.zones_de_slot_data({"yokai_zones": self.catalogue.yokai_zones})
                if zmod is None or zg is None:
                    raise rando.RandoImpossible("zones des Yo-kai demandés absentes ou d'une autre version de la "
                                                "table (mettre le mod à jour)")
                zones = rando.zones_client(zg, zmod.cartes_par_zone(), zmod.K)
            self.rando_melange = rando.calculer(base, ry["graine"], ry["mode"], version=version, apres_jeu=apres_jeu,
                                                zones=zones)
        except rando.RandoImpossible as e:
            self.rando_melange = None
            self._rando_publier("refuse", f"mélange refusé : {e}", logging.ERROR)
            return
        m = self.rando_melange
        if m.par_rencontre:
            perimetre = (f", périmètre {'avec' if m.perimetre == 'apres_jeu' else 'sans'} l'après-jeu"
                         if m.version >= 5 else "")
            self._rando_publier("pret", f"mélange {m.mode} (version {m.version}{perimetre}) de la graine {m.graine} : "
                                f"{m.stats['changes']} combattants "
                                f"changés sur {m.stats['combattants']} ({m.stats['rencontres_changees']} rencontres sur "
                                f"{len(m.w)}), empreinte {m.empreinte[:12]}" + self._rando_sans_normal(m)
                                + self._rando_categories(m))
            return
        self._rando_publier("pret", f"mélange {m.mode} (version {m.version}) de la graine {m.graine} : "
                            f"{len(m.sigma)} espèces déplacées, "
                            f"{len(m.w)} rencontres, empreinte {m.empreinte[:12]}" + self._rando_sans_normal(m))

    @staticmethod
    def _rando_sans_normal(m) -> str:
        """Version 3 du mélange (§21) : repli annoncé dans le journal (jamais silencieux)."""
        if m.version < 3:
            return ""
        invitees = ""
        if m.version >= 4:                                # §22 : espèces invitées (repli annoncé, jamais silencieux)
            invitees = (f" ; {len(m.invitees) - len(m.invitees_absentes)} Yo-kai invités placés sur "
                        f"{len(m.invitees)}" + (f" ({len(m.invitees_absentes)} sans aucune place : "
                                                + ", ".join(f"0x{p:08X}" for p in m.invitees_absentes[:8]) + ")"
                                                if m.invitees_absentes else ""))
        if not m.sans_normal:
            return invitees + " ; chaque Yo-kai du mélange a un lieu hors portail mystère"
        return (invitees + f" ; {len(m.sans_normal)} Yo-kai sans lieu hors portail mystère (contrainte infaisable "
                "pour eux : " + ", ".join(f"0x{p:08X}" for p in m.sans_normal[:8]) + ")")

    @staticmethod
    def _rando_categories(m) -> str:
        """Version 5 : combattants changés par catégorie de rencontre et raisons des combattants gardés (journal)."""
        if m.version < 5:
            return ""
        cats = ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in m.stats.get("categories", {}).items())
        gardes = ", ".join(f"{k} {v}" for k, v in m.stats.get("gardes_raisons", {}).items())
        return f" ; par catégorie : {cats} ; gardés : {gardes}"

    def _rando_generee(self, t: asyncio.Task) -> None:
        if t.cancelled():
            return
        e = t.exception()
        if e is not None:
            self._rando_cle = (self.ident_partie, None, None, None)
            self._rando_publier("base_absente", f"base locale des rencontres non générée ({e}) : « Réparer le mod »",
                                logging.ERROR, cause="base_erreur")
        else:
            self.log.info("Base locale des rencontres générée : %s", t.result())

    async def _suivre_rando(self, h) -> None:
        """Écrit le mélange dans la boîte v6 pour la sauvegarde liée ; sinon `valide` = 0 (le jeu retire le mélange).
        Changement de mélange : `valide` = 0, attente que le jeu publie les tables d'origine (générations 0), puis
        écriture des tables et de `valide` (§22). Jeu sans v6 ou sans le randomizer compilé : rien n'est écrit."""
        self._preparer_rando()
        if not self.zone.rando_disponible(h):
            if self.rando_melange is not None and self._rando_jeu != (self._instance, None):
                self._rando_jeu = (self._instance, None)
                self.log.warning("Randomizer de Yo-kai : jeu v%d sans table de mélange (patch du mod à mettre à jour) : "
                                 "Yo-kai d'origine", h.version)
            if self.rando_melange is not None:
                self._rando_cause_jeu = "jeu_sans_rando"
            self._rando_fichier_local({"support": False})
            return
        # en-tête du mélange relu sur évènement seulement (§23) : instance, partie ou statut de la sauvegarde, mélange
        # voulu, passage sur le terrain ou terrain stable (le jeu publie gen_carte / gen_commune sur le terrain stable) ;
        # tous les TOURS_ATTENTE tours pendant l'écriture d'un mélange ; filet de sécurité sinon
        m = self.rando_melange
        voulu = m.generation if (m is not None and self.sauvegarde == "liee") else 0
        maintenant = time.monotonic()
        cle_lue = (self._instance, h.partie, h.ident_sauvegarde, self.sauvegarde, voulu, h.terrain_numero, h.stable)
        delai = TOURS_ATTENTE * self.periode if self._rando_attente else self.periode_filet
        if cle_lue == self._rando_lu_cle and maintenant - self._rando_lu_t < delai:
            return
        self._rando_lu_cle, self._rando_lu_t = cle_lue, maintenant
        brut = await self.zone.lire_rando_entete()
        e = bp.dec_rando_entete(brut)
        self._rando_attente = False
        self._rando_cause_jeu = ""
        if self._rando_jeu is None or self._rando_jeu[0] != self._instance:
            self._rando_jeu = (self._instance, bp.rando_compile(brut))
            if self.rando_melange is not None and not self._rando_jeu[1]:
                self.log.warning("Randomizer de Yo-kai absent du jeu installé (compilé sans) : Yo-kai d'origine")
        compile_ = self._rando_jeu[1]
        if compile_ and self.rando_melange is not None and self.rando_melange.par_rencontre and not (
                self.zone.rando_rencontre_disponible(h) and compile_ & bp.RANDO_PAR_RENCONTRE):
            # mélange par rencontre demandé, jeu v6-v9 : rien n'est écrit (jamais au-delà de sa zone), mélange retiré
            if self._rando_sans_p != self._instance:
                self._rando_sans_p = self._instance
                self.log.warning("Randomizer de Yo-kai : le jeu installé (v%d) ne connaît pas le mélange par "
                                 "rencontre (patch du mod à mettre à jour) : Yo-kai d'origine", h.version)
            compile_ = 0
            self._rando_cause_jeu = "jeu_ancien"
        if compile_ and self.rando_melange is not None and self.rando_melange.par_rencontre and \
                len(self.rando_melange.entrees) > bp.CAP_RANDO_P and not compile_ & bp.RANDO_P_ETENDU:
            # V3 (version 5 avec l'après-jeu) : plus de 2048 places ; un patch sans l'extension des entrées P ne peut
            # pas les recevoir : rien n'est écrit (jamais un mélange tronqué), Yo-kai d'origine
            if self._rando_sans_p != self._instance:
                self._rando_sans_p = self._instance
                self.log.warning("Randomizer de Yo-kai : %d places pour ce mélange, le jeu installé n'en reçoit que %d "
                                 "(patch du mod à mettre à jour) : Yo-kai d'origine", len(self.rando_melange.entrees),
                                 bp.CAP_RANDO_P)
            compile_ = 0
            self._rando_cause_jeu = "jeu_sans_extension"
        if compile_ and self.rando_melange is not None and self.rando_melange.par_rencontre and (
                len(self.rando_melange.especes) > bp.CAP_RANDO_ESPECES and not compile_ & bp.RANDO_ESPECES_ETENDU):
            # V3, lot M2a-bis (version 6 : spots) : plus de 256 espèces ; un patch sans la table d'espèces étendue ne
            # peut pas les recevoir : rien n'est écrit (jamais un mélange tronqué), Yo-kai d'origine
            if self._rando_sans_p != self._instance:
                self._rando_sans_p = self._instance
                self.log.warning("Randomizer de Yo-kai : %d espèces pour ce mélange, le jeu installé n'en reçoit que %d "
                                 "(patch du mod à mettre à jour) : Yo-kai d'origine", len(self.rando_melange.especes),
                                 bp.CAP_RANDO_ESPECES)
            compile_ = 0
            self._rando_cause_jeu = "jeu_sans_extension"
        # (V3, lot M1 : compteurs du jeu en plus, déjà dans l'en-tête lu : aucune lecture GDB de plus)
        jeu = {"support": bool(compile_), "valide": e["valide"], "table_gen": e["table_gen"],
               "gen_carte": e["gen_carte"], "gen_commune": e["gen_commune"], "modifies": e["modifies"],
               "derniere": e["derniere"], "loupes": e["loupes"], "erreurs": e["erreurs"],
               "tardives": e["tardives"], "analyses": e["analyses"]}
        m = self.rando_melange
        voulu = m.generation if (m is not None and self.sauvegarde == "liee") else 0
        if not compile_ and m is not None and not self._rando_cause_jeu:
            self._rando_cause_jeu = "jeu_sans_rando"
        if compile_ and m is not None and not self._rando_cause_jeu:
            self._rando_cause_jeu = ("ecrit" if e["valide"] == m.generation and e["table_gen"] == m.generation
                                     else "non_liee" if voulu == 0 else "retrait")
        self._rando_fichier_local(jeu)
        if not compile_:
            return
        if voulu == 0:
            if e["valide"] != 0:
                await self.zone.ecrire_rando_valide(0)
                self._rando_attente = True
                self.log.info("Randomizer de Yo-kai : mélange retiré (sauvegarde %s)", self.sauvegarde)
            return
        if e["table_gen"] == voulu:
            if e["valide"] != voulu:
                await self.zone.ecrire_rando_valide(voulu)
                self._rando_attente = True
                self.log.info("Randomizer de Yo-kai : mélange %#010x réactivé", voulu)
            return
        # autres tables dans la boîte : d'abord les retirer du jeu
        maintenant = time.monotonic()
        self._rando_attente = True                          # retrait puis écriture : en-tête relu souvent
        if e["valide"] != 0:
            await self.zone.ecrire_rando_valide(0)
            self._rando_attente_t = maintenant
            return
        encore = {e["gen_carte"], e["gen_commune"]} - {0, bp.RANDO_GEN_AUCUNE, bp.RANDO_GEN_IGNOREE}
        if encore and e["table_gen"] != 0:
            if not self._rando_attente_t:
                self._rando_attente_t = maintenant
            if maintenant - self._rando_attente_t < ATTENTE_RETRAIT_RANDO * self.echelle:
                return
            self.log.warning("Randomizer de Yo-kai : l'ancien mélange (%s) n'a pas été retiré en %d s ; nouveau mélange "
                             "écrit quand même (une table déjà mélangée le garde jusqu'à son prochain chargement)",
                             ", ".join(f"{g:#x}" for g in sorted(encore)), ATTENTE_RETRAIT_RANDO)
        self._rando_attente_t = 0.0
        if m.par_rencontre:
            await self.zone.ecrire_rando_rencontre(m.entrees, m.especes, m.w, voulu, m.empreinte32)
            self.log.info("Randomizer de Yo-kai : mélange par rencontre %#010x écrit (%d places, %d espèces, %d "
                          "rencontres)", voulu, len(m.entrees), len(m.especes), len(m.w))
            return
        await self.zone.ecrire_rando(m.sigma, m.beta, m.w, voulu, m.empreinte32)
        self.log.info("Randomizer de Yo-kai : mélange %#010x écrit (%d espèces, %d bases, %d rencontres)", voulu,
                      len(m.sigma), len(m.beta), len(m.w))

    # ------------------------------------------------------------------------------ randomizer des boss (v7)
    def _boss_publier(self, statut: str, message: str, niveau: int = logging.INFO) -> None:
        if (statut, message) != (self.boss_statut, self.boss_message):
            self.boss_statut, self.boss_message = statut, message
            self.log.log(niveau, "Randomizer des boss : %s", message)
        self._boss_fichier_local()

    def _boss_fichier_local(self, jeu: dict | None = None) -> None:
        """`rando_boss.json` (tracker du lanceur) : réécrit quand le mélange, l'état ou ce que le jeu publie change."""
        etat = {"pret": "actif", "aucun": "aucun", "refuse": "refuse", "base_absente": "refuse"}.get(
            self.boss_statut, "attente")
        cle = (self.ident_partie, self.boss_statut, self.boss_message,
               None if self.boss_melange is None else self.boss_melange.generation,
               None if jeu is None else tuple(sorted(jeu.items())))
        if cle == self._boss_fichier:
            return
        self._boss_fichier = cle
        try:
            rboss.ecrire_fichier_local(self.stockage.dossier, self.boss_melange, self.ident_partie, etat,
                                       dict(jeu or {}, message=self.boss_message))
        except OSError as e:
            self.log.warning("rando_boss.json non écrit : %s", e)

    def _boss_cle_voulue(self) -> tuple:
        rb = self.catalogue.rando_boss
        return (self.ident_partie, None if rb is None else rb["mode"], None if rb is None else rb["graine"],
                None if rb is None else rb.get("version", 1),
                None if rb is None or not isinstance(rb.get("sigma"), dict) else tuple(sorted(rb["sigma"].items())),
                self._boss_force_voulue())

    def _boss_force_voulue(self) -> tuple[str, tuple[str, ...]]:
        """(force, boss exclus) de la graine : (« d_origine », ()) sans l'option `rando_boss_force`."""
        rf = self.catalogue.rando_boss_force
        return ("d_origine", ()) if not rf else (rf["mode"], tuple(rf.get("exclus") or ()))

    def _noter_boss_jeu(self, brut: bytes) -> None:
        """Ce que le jeu de cette instance publie dans l'en-tête des boss : randomizer compilé, force adaptée."""
        self._boss_jeu = (self._instance, bp.boss_compile(brut))
        self._boss_force_jeu = bp.boss_force(brut)

    def _verifier_yokai_zones(self, h) -> None:
        """VERSION 7 du mélange des Yo-kai (zones des Yo-kai demandés tirées à la génération, lots M2b) : la LOGIQUE de
        la graine suppose chaque Yo-kai demandé placé dans sa zone ; sans ce mélange chez le joueur, une requête que la
        logique dit faisable peut ne pas l'être. Tant que le mélange n'est pas prêt (base absente, ROM ou zones
        refusées, calcul en cours) ou que le jeu ne peut pas le recevoir (patch sans le randomizer ou sans les tables
        étendues), la partie est bloquée comme pour les boss de version 2 (`_verifier_boss`) : rien n'est lié, livré ni
        envoyé ; levé tout seul quand le mélange est prêt. Versions 1 à 6 : rien ici (Yo-kai d'origine + avertissement,
        la partie continue). Aucune lecture GDB (état du calcul et de ce que le jeu a publié, déjà connus)."""
        ry = self.catalogue.rando_yokai
        # (version inconnue de ce client, ex. 8 : refusée par le mélange, Yo-kai d'origine + avertissement, comme avant)
        v = int(ry.get("melange", 1)) if ry is not None else 1
        if v < rando.VERSION_ZONES or v not in rando.VERSIONS_MELANGE:
            self.yokai_manquant = None
            self._yokai_reessai_sig = None
            return
        self._preparer_rando()
        pret = self.rando_statut == "pret" and self.rando_melange is not None
        if pret:
            self._yokai_reessai_sig = None
        elif self.rando_statut in ("base_absente", "refuse") \
                and (self._rando_tache is None or self._rando_tache.done()):
            # ROM configurée ou base (re)générée entre-temps (« Réparer le mod ») : nouvel essai, sans relancer le client
            maintenant = time.monotonic()
            if self._yokai_reessai_sig is None:
                self._yokai_reessai_sig, self._yokai_reessai_t = self._boss_signature_locale(), maintenant
            elif maintenant - self._yokai_reessai_t >= max(self.periode, PERIODE_REESSAI_BOSS * self.echelle):
                self._yokai_reessai_t = maintenant
                if self._boss_signature_locale() != self._yokai_reessai_sig:
                    self._yokai_reessai_sig = None
                    self._rando_cle = None
                    self._preparer_rando()
                    pret = self.rando_statut == "pret" and self.rando_melange is not None
        if not pret:
            motif = {"base_absente": "yokai_rom", "refuse": "yokai_refuse"}.get(self.rando_statut, "yokai_attente")
        elif not self.zone.rando_disponible(h) or self._rando_cause_jeu in ("jeu_sans_rando", "jeu_ancien",
                                                                          "jeu_sans_extension"):
            motif = "yokai_jeu"
        else:
            motif = None
        if motif != self.yokai_manquant:
            self.yokai_manquant = motif
            if motif is None:
                self.log.info("Mélange des Yo-kai de la graine (zones) prêt : la partie reprend")
            else:
                self.log.log(logging.INFO if motif == "yokai_attente" else logging.ERROR,
                             "Mélange des Yo-kai de la graine NON appliqué (%s) : la logique de cette graine suppose "
                             "chaque Yo-kai demandé dans sa zone ; rien ne sera lié, livré ni envoyé tant qu'il manque. "
                             "%s", self.rando_message or motif,
                             {"yokai_attente": "Préparation en cours : patienter.",
                              "yokai_rom": "Configurer la ROM du jeu dans le lanceur (puis « Réparer le mod »).",
                              "yokai_refuse": "La ROM configurée n'est pas celle de la graine, ou le mod est à mettre "
                                              "à jour (« Réparer le mod » dans le lanceur).",
                              "yokai_jeu": "Installer le patch du mod à jour (« Réparer le mod ») et relancer le jeu."
                              }[motif])

    def _boss_signature_locale(self) -> tuple:
        """Ce dont dépend un mélange non préparé : ROM configurée (réglage du lanceur, suivi par `suivre_fichier_config`)
        et base locale des rencontres. Fichiers locaux seulement : aucun paquet GDB."""
        rom = self.config.rom
        try:
            st = (Path(self.stockage.dossier) / rando.NOM_BASE).stat()
            base = (st.st_mtime_ns, st.st_size)
        except OSError:
            base = None
        return rom, bool(rom) and Path(rom).is_file(), base

    async def _verifier_boss(self, h) -> None:
        """VERSION 2 du mélange des boss (tiré à la génération, `<mode>#2`) : la LOGIQUE de la graine a été calculée avec
        les boss déplacés (le boss de l'objectif et les occupants des places « sans marqueur ») ; sans le mélange chez
        le joueur, la victoire peut être inaccessible. Tant que le mélange n'est pas prêt (base absente, ROM ou
        permutation refusée, base en cours de génération) ou que le jeu n'a pas la table des boss, la partie est
        traitée comme des verrous manquants (`boutiques_manquantes`, §20) : rien n'est lié, livré ni envoyé. Levé tout
        seul dès que le mélange est prêt et que le jeu peut le recevoir (ROM configurée dans le lanceur, base générée,
        jeu mis à jour et relancé). VERSION 1 (mélange calculé chez le joueur, la logique n'en dépend pas) : rien ici,
        comportement inchangé (boss d'origine + avertissement, la partie continue).
        Charge GDB (§23) : une lecture de l'en-tête des boss par instance du jeu, pour les graines de version 2
        seulement (le jeu a-t-il le mélange compilé ?) ; le reste se lit dans l'en-tête du tour et des fichiers locaux."""
        rb = self.catalogue.rando_boss
        if rb is None or rb.get("version", 1) < rboss.VERSION_GRAINE:
            self.boss_manquant = None
            self._boss_reessai_sig = None
            return
        self._preparer_boss()
        pret = self.boss_statut == "pret" and self.boss_melange is not None \
            and self._boss_cle == self._boss_cle_voulue()
        if pret:
            self._boss_reessai_sig = None
        elif self.boss_statut in ("base_absente", "refuse") \
                and (self._rando_tache is None or self._rando_tache.done()):
            # ROM configurée ou base (re)générée entre-temps (« Réparer le mod ») : nouvel essai, sans relancer le client
            maintenant = time.monotonic()
            if self._boss_reessai_sig is None:
                self._boss_reessai_sig, self._boss_reessai_t = self._boss_signature_locale(), maintenant
            elif maintenant - self._boss_reessai_t >= max(self.periode, PERIODE_REESSAI_BOSS * self.echelle):
                self._boss_reessai_t = maintenant
                if self._boss_signature_locale() != self._boss_reessai_sig:
                    self._boss_reessai_sig = None
                    self._boss_cle = None
                    self._preparer_boss()
                    pret = self.boss_statut == "pret" and self.boss_melange is not None
        if not pret:
            motif = {"base_absente": "boss_rom", "refuse": "boss_refuse"}.get(self.boss_statut, "boss_attente")
        elif not self.zone.boss_disponible(h):
            motif = "boss_jeu"
        else:
            if self._boss_jeu is None or self._boss_jeu[0] != self._instance:
                self._noter_boss_jeu(await self.zone.lire_boss_entete())
            motif = None if self._boss_jeu[1] else "boss_jeu"
        if motif != self.boss_manquant:
            self.boss_manquant = motif
            if motif is None:
                self.log.info("Mélange des boss de la graine prêt : la partie reprend")
            else:
                self.log.log(logging.INFO if motif == "boss_attente" else logging.ERROR,
                             "Mélange des boss de la graine NON appliqué (%s) : la logique de cette graine le suppose ; "
                             "rien ne sera lié, livré ni envoyé tant qu'il manque. %s", self.boss_message or motif,
                             {"boss_attente": "Préparation en cours : patienter.",
                              "boss_rom": "Configurer la ROM du jeu dans le lanceur (puis « Réparer le mod »).",
                              "boss_refuse": "La ROM configurée n'est pas celle de la graine, ou le mod est à mettre "
                                             "à jour (« Réparer le mod » dans le lanceur).",
                              "boss_jeu": "Installer le patch du mod à jour (« Réparer le mod ») et relancer le jeu."
                              }[motif])

    def _preparer_boss(self) -> None:
        """Mélange des boss de la graine, une fois par (partie, mode, graine). Base locale absente ou d'un format sans
        les scripts de combat (< 4) : générée en tâche de fond depuis la ROM configurée (même base que les Yo-kai)."""
        rb = self.catalogue.rando_boss
        cle = self._boss_cle_voulue()
        if cle == self._boss_cle or (self._rando_tache is not None and not self._rando_tache.done()):
            return
        if rb is None:
            self._boss_cle, self.boss_melange = cle, None
            if self.catalogue.rando_boss_inconnu:
                self._boss_publier("refuse", "mode de mélange des boss inconnu de ce client ("
                                   f"{self.catalogue.rando_boss_inconnu}) : boss d'origine ; mettre le mod à jour",
                                   logging.ERROR)
            else:
                self._boss_publier("aucun", "pas de mélange des boss sur cette partie")
            return
        base = rando.charger_base(self.stockage.dossier)
        rom = self.config.rom
        force, exclus = self._boss_force_voulue()
        # force adaptée : la base doit porter les stats et les multiplicateurs (format 18) ; sinon régénérée depuis la
        # ROM si elle est configurée (sans ROM : mélange appliqué à la force d'origine, avertissement)
        minimum = rboss.FORMAT_BASE_FORCE if force == "adaptee" else rboss.FORMAT_BASE_BOSS
        if base is not None and base.get("format", 0) < minimum and rom and Path(rom).is_file():
            base = None         # format antérieur (sans les scripts de combat / les stats) : régénérée depuis la ROM
        if base is None:
            if not rom or not Path(rom).is_file():
                self._boss_cle, self.boss_melange = cle, None
                self._boss_publier("base_absente", "base locale des rencontres absente : « Réparer le mod » dans le "
                                   "lanceur (ROM non configurée)", logging.WARNING)
                return
            self._boss_publier("calcul", "base locale des rencontres générée depuis la ROM…")
            self._rando_tache = asyncio.create_task(asyncio.to_thread(rando.generer_base, rom, self.stockage.dossier))
            self._rando_tache.add_done_callback(self._boss_generee)
            return
        self._boss_cle = cle
        try:
            if rb.get("version", 1) >= rboss.VERSION_GRAINE:
                # permutation portée par la graine (tirée à la génération) : contrôlée sur la ROM, jamais recalculée
                # (version 3, ap/boss-voie-mystere : boss de la Voie du mystère mélangés aussi)
                self.boss_melange = rboss.appliquer_graine(base, rb["mode"], rb["graine"], rb.get("sigma"),
                                                           rb.get("sigma_n"), force=force, exclus=exclus,
                                                           version=rb.get("version", rboss.VERSION_GRAINE))
            else:
                self.boss_melange = rboss.calculer(base, rb["graine"], rb["mode"], force=force, exclus=exclus)
        except rboss.RandoBossImpossible as e:
            self.boss_melange = None
            plus = " ; ATTENTION : la logique de cette graine suppose ce mélange (le boss de l'objectif est resté à " \
                "sa place d'origine)" if rb.get("version", 1) >= rboss.VERSION_GRAINE else ""
            self._boss_publier("refuse", f"mélange refusé : {e}{plus}", logging.ERROR)
            return
        m = self.boss_melange
        if self.catalogue.rando_boss_force_inconnu:
            self.log.warning("Randomizer des boss : force des boss de la graine inconnue de ce client (%s) : force "
                             "d'origine ; mettre le mod à jour", self.catalogue.rando_boss_force_inconnu)
        texte_force = ""
        if m.force == "adaptee":
            texte_force = f", force adaptée à {len(m.m)} places"
            if m.force_exclues:
                texte_force += f" (boss de l'objectif à sa force d'origine : {', '.join(m.exclus)})"
            if m.force_ignorees:
                texte_force += f" ({len(m.force_ignorees)} sans données : force d'origine)"
                self.log.warning("Randomizer des boss : force adaptée impossible pour %d places (base locale sans les "
                                 "stats : configurer la ROM, « Réparer le mod ») : force d'origine",
                                 len(m.force_ignorees))
        self._boss_publier("pret", f"mélange {m.mode} de la graine {m.graine}{texte_force} : {len(m.sigma)} boss à script déplacés "
                           f"({len(m.b)} places), {len(m.n)} boss sans script, empreinte {m.empreinte[:12]}")

    def _boss_generee(self, t: asyncio.Task) -> None:
        if t.cancelled():
            return
        e = t.exception()
        if e is not None:
            self._boss_cle = (self.ident_partie, None, None)
            self._boss_publier("base_absente", f"base locale des rencontres non générée ({e}) : « Réparer le mod »",
                               logging.ERROR)
        else:
            self.log.info("Base locale des rencontres générée : %s", t.result())

    async def _suivre_rando_boss(self, h) -> None:
        """Écrit le mélange des boss dans la boîte v7 pour la sauvegarde liée ; sinon `valide` = 0 (le jeu remet les
        places d'origine). Même protocole que le randomizer de Yo-kai (§22 / §24) : changement de mélange = retrait,
        attente des générations 0, puis tables et `valide`. Jeu sans v7 ou sans le randomizer des boss : rien.
        Charge GDB (§23) : en-tête relu sur les mêmes évènements que celui des Yo-kai ; sans mélange sur la partie et
        `valide` déjà lu à 0 pour cette instance du jeu : plus aucune lecture (sauf filet de sécurité)."""
        self._preparer_boss()
        if not self.zone.boss_disponible(h):
            if self.boss_melange is not None and self._boss_jeu != (self._instance, None):
                self._boss_jeu = (self._instance, None)
                self.log.warning("Randomizer des boss : jeu v%d sans table des boss (patch du mod à mettre à jour) : "
                                 "boss d'origine", h.version)
            self._boss_fichier_local({"support": False})
            return
        connu = self._boss_jeu is not None and self._boss_jeu[0] == self._instance
        # force adaptée : écrite seulement si le jeu de CETTE instance l'applique ; sinon le même mélange sans M (même
        # génération qu'un mélange sans l'option : rien à retirer)
        m = self.boss_melange
        if m is not None and m.m and connu and not self._boss_force_jeu:
            m = rboss.sans_force(m)
        voulu = m.generation if (m is not None and self.sauvegarde == "liee") else 0
        maintenant = time.monotonic()
        if m is None and connu and self._boss_valide_lu == 0 and not self._boss_attente \
                and maintenant - self._boss_lu_t < self.periode_filet:
            return
        cle_lue = (self._instance, h.partie, h.ident_sauvegarde, self.sauvegarde, voulu, h.terrain_numero, h.stable)
        delai = TOURS_ATTENTE * self.periode if self._boss_attente else self.periode_filet
        if cle_lue == self._boss_lu_cle and maintenant - self._boss_lu_t < delai:
            return
        self._boss_lu_cle, self._boss_lu_t = cle_lue, maintenant
        brut = await self.zone.lire_boss_entete()
        e = bp.dec_boss_entete(brut)
        self._boss_attente = False
        self._boss_valide_lu = e["valide"]
        if not connu:
            self._noter_boss_jeu(brut)
            if self.boss_melange is not None and not self._boss_jeu[1]:
                self.log.warning("Randomizer des boss absent du jeu installé (compilé sans) : boss d'origine")
        compile_ = self._boss_jeu[1]
        if m is not None and m.m and not self._boss_force_jeu:
            # graine « adaptee » + patch sans la table M (antérieur ou --define YKW2_AP_SANS_BOSS_FORCE) : la partie
            # continue, boss mélangés à leur force d'origine (aucune location n'en dépend) ; un avertissement
            if compile_ and self._boss_force_averti != (self._instance, m.generation):
                self._boss_force_averti = (self._instance, m.generation)
                self.log.warning("Randomizer des boss : force adaptée absente du jeu installé (patch du mod à mettre "
                                 "à jour) : boss mélangés à leur force d'origine")
            m = rboss.sans_force(m)
            voulu = m.generation if self.sauvegarde == "liee" else 0
        jeu = {"support": bool(compile_), "valide": e["valide"], "table_gen": e["table_gen"],
               "gen_carte": e["gen_carte"], "gen_commune": e["gen_commune"], "places": e["places"],
               "especes": e["especes"], "erreurs": e["erreurs"], "manquants": e["manquants"],
               "force": bool(compile_ and self._boss_force_jeu and m is not None and m.m),
               "forces": e["forces"]}
        self._boss_fichier_local(jeu)
        if not compile_:
            return
        if voulu == 0:
            if e["valide"] != 0:
                await self.zone.ecrire_boss_valide(0)
                self._boss_attente = True
                self._boss_valide_lu = 0
                self.log.info("Randomizer des boss : mélange retiré (sauvegarde %s)", self.sauvegarde)
            return
        if e["table_gen"] == voulu:
            if e["valide"] != voulu:
                await self.zone.ecrire_boss_valide(voulu)
                self._boss_attente = True
                self.log.info("Randomizer des boss : mélange %#010x réactivé", voulu)
            return
        # autres tables dans la boîte : d'abord les retirer du jeu
        self._boss_attente = True
        if e["valide"] != 0:
            await self.zone.ecrire_boss_valide(0)
            self._boss_attente_t = maintenant
            return
        encore = {e["gen_carte"], e["gen_commune"]} - {0, bp.RANDO_GEN_AUCUNE, bp.RANDO_GEN_IGNOREE}
        if encore and e["table_gen"] != 0:
            if not self._boss_attente_t:
                self._boss_attente_t = maintenant
            if maintenant - self._boss_attente_t < ATTENTE_RETRAIT_RANDO * self.echelle:
                return
            self.log.warning("Randomizer des boss : l'ancien mélange (%s) n'a pas été retiré en %d s ; nouveau mélange "
                             "écrit quand même (une table déjà modifiée le garde jusqu'à son prochain chargement)",
                             ", ".join(f"{g:#x}" for g in sorted(encore)), ATTENTE_RETRAIT_RANDO)
        self._boss_attente_t = 0.0
        # table M : seulement si le jeu l'applique, et (nombre 0 compris) si cette graine en a une ou si une autre en
        # a laissé une dans la boîte (aucune écriture de plus sans l'option)
        await self.zone.ecrire_boss(m.b, m.n, voulu, m.empreinte32,
                                    m.m if self._boss_force_jeu and (m.m or e["m_nombre"]) else None)
        self._boss_valide_lu = voulu
        self.log.info("Randomizer des boss : mélange %#010x écrit (%d places à script, %d boss sans script, force "
                      "adaptée à %d places)", voulu, len(m.b), len(m.n), len(m.m))

    # ------------------------------------------------------------------------------ suivi pour le tracker
    async def _suivre_tracker(self, h) -> None:
        """Fichiers du tracker de Yo-kai du lanceur, pour la SAUVEGARDE LIÉE seulement (docs/systemes/
        archipelago_rando_yokai.md §10.6) : `medaillium.json` (bits « vu » et « ami », une lecture groupée
        P+0x40C..0x643) et `progression.json` (chapitre, pas et progression de l'en-tête, rang de montre réel lu dans
        O = *(*0x0081521C + 0x10)). Relus sur évènement (§23) : tout de suite si la progression publiée change, sur un
        passage sur le terrain (fin de combat, de scène, de menu : au plus une fois par TOURS_TRACKER_MIN tours), et
        toutes les PERIODE_MEDAILLIUM secondes en filet ; en-tête et objet du rang relus APRÈS les données : tout est
        écarté si la partie a changé."""
        self._rafraichir_base()
        if self.sauvegarde != "liee" or not h.partie or not h.adresse_p:
            return
        maintenant = time.monotonic()
        publiee = (h.ident_sauvegarde, h.chapitre, h.pas_scenario, h.progression)
        ecoule = maintenant - self._medaillium_t
        if publiee == self._progression_suivi and ecoule < PERIODE_MEDAILLIUM * self.echelle \
                and (h.terrain_numero == self._terrain_suivi or ecoule < TOURS_TRACKER_MIN * self.periode):
            return
        self._medaillium_t = maintenant
        debut, taille = rando.LECTURE_MEDAILLIUM
        # V3, lot 3 : + le mot des terrains de Ψ Blasters (P + 0x64C), dans le même paquet, seulement pour une graine
        # qui a ces checks (toute autre graine : exactement la lecture d'avant)
        taille_lue = max(taille, P_BLASTERS + 4 - debut) if self.catalogue.blasters else taille
        b_lu = await self.pont.lire(h.adresse_p + debut, taille_lue)
        b = b_lu[:taille]
        o, rang = await self.boite.rang_montre(self._adresse_rang)
        if not await self._meme_partie(h):
            return
        if o is not None or self._adresse_rang is not None:
            apres = await self.boite.adresse_rang()
            if apres != o:
                self._adresse_rang = None                       # O déplacé (ou nul) : relu en entier au prochain tour
                return
        self._adresse_rang = o
        self._progression_suivi, self._terrain_suivi = publiee, h.terrain_numero
        await self._verifier_amis(h, b)
        self._noter_medailles_objectif(b)
        await self._verifier_blasters(h, b_lu, debut)
        cle = (h.ident_sauvegarde, b)
        if cle != self._medaillium:
            try:
                rando.ecrire_medaillium(self.stockage.dossier, self.ident_partie, b, h.ident_sauvegarde)
                self._medaillium = cle
            except OSError as ex:
                self.log.warning("medaillium.json non écrit : %s", ex)
        connu = bool(h.progression & bp.PROGRESSION_CHAPITRE)
        prog = {"ident_sauvegarde": h.ident_sauvegarde,
                "chapitre": h.chapitre if connu else None, "pas_scenario": h.pas_scenario if connu else None,
                "phase": h.chapitre * 10000 + h.pas_scenario if connu else None,
                "rang_montre": rang, "apres_jeu": bool(h.progression & bp.PROGRESSION_VICTOIRE)}
        cle = tuple(sorted(prog.items()))
        if cle != self._progression_fichier:
            try:
                rando.ecrire_progression(self.stockage.dossier, self.ident_partie, prog)
                self._progression_fichier = cle
            except OSError as ex:
                self.log.warning("progression.json non écrit : %s", ex)

    def _rafraichir_base(self) -> None:
        """Base locale d'un format antérieur (n° du Médaillium faux, lieux sans condition décodée) : régénérée en tâche
        de fond depuis la ROM configurée, une fois par session (le mélange, calculé sur W, D, F, reste identique)."""
        if self._base_rafraichie or (self._rando_tache is not None and not self._rando_tache.done()):
            return
        self._base_rafraichie = True
        rom = self.config.rom
        if not rom or not Path(rom).is_file() or not rando.base_a_refaire(self.stockage.dossier):
            return
        self.log.info("Base locale des rencontres d'un format antérieur : régénération depuis la ROM")
        self._rando_tache = asyncio.create_task(asyncio.to_thread(rando.generer_base, rom, self.stockage.dossier))
        self._rando_tache.add_done_callback(self._base_regeneree)

    def _base_regeneree(self, t: asyncio.Task) -> None:
        if t.cancelled():
            return
        e = t.exception()
        if e is not None:
            self.log.warning("Base locale des rencontres non régénérée (%s) : l'ancienne reste utilisée", e)
        else:
            self.log.info("Base locale des rencontres régénérée : %s", t.result())

    # ------------------------------------------------------------------------------ partie chargée
    async def _meme_partie(self, h) -> bool:
        """Relit l'en-tête APRÈS une lecture de données (journal, bits, progression) : si la partie a changé
        entre-temps (autre sauvegarde chargée, retour au titre), les données lues sont écartées."""
        h2 = await self.boite.detecter()
        return (h2 is not None and h2.partie == h.partie and h2.adresse_p == h.adresse_p
                and h2.ident_sauvegarde == h.ident_sauvegarde)

    def _oublier_sauvegarde(self) -> None:
        self._medailles_objectif = set()
        self.sauvegarde = "aucune"
        self._boutiques_faites = None
        self.distrib.oublier()
        self.leg.oublier()
        self.portails.oublier()
        self.bingo.oublier()
        self.pieges.oublier()
        self._liaison = None
        self._demande = None
        self._eval_cle = None
        self.raison_non_liee = ""

    def _indices_ap(self) -> set[int]:
        return set(self.catalogue.coffres.values()) | set(self.catalogue.spots)

    async def _lire_bits(self, h) -> tuple[set[int], set[int], set[int] | None, set[int]] | None:
        """Bits persistants de la partie chargée : (index TBox posés, flags de boss de la graine posés, quêtes de
        boss de la graine terminées, flags « Yo-kai appelé » des Tablo-blabla de la graine posés), lus puis validés
        par une relecture de l'adresse de Q (boss de quête) et de l'en-tête (`_meme_partie`) ; None sans partie ou si
        la partie a changé. Flags (boss, secours, Tablo-blabla : P+4+14 .. P+4+269 au plus, un paquet) et phases de
        quête : une lecture groupée chacun, aucune si la graine n'en a pas ; flags et TBox dans le même paquet quand ils y
        tiennent (`Boite.bits_partie`, §23). Q validé par la relecture précédente : chaînage relu après seulement. Q
        illisible (maillon nul ou hors du tas) : quêtes None (« inconnues »), sans bloquer les coffres ni les boss."""
        boss: set[int] | None = set()
        tablos: set[int] = set()
        secours = self._secours()
        seuls: set[int] = set()
        # une seule lecture groupée : flags TBox, flags des boss, flags « évènement vu » de la détection de secours et
        # flags « Yo-kai appelé » des Tablo-blabla
        flags = set(self.catalogue.boss.values()) | set(secours.values()) | set(self.catalogue.tablos.values())
        # boss détectés par un octet global (pseudo-flags) : les 8 flags bit de l'octet, dans la même lecture
        pseudos = {f for f in self.catalogue.boss.values() if bp.boss_octet_decode(f) is not None}
        for f in pseudos:
            flags |= set(bp.boss_octet_flags(bp.boss_octet_decode(f)[0]))
        flags -= pseudos
        if self.catalogue.criminels or self.catalogue.boutiques:
            # + octets des Yo-criminels et des bits de boutique, dans le même regroupement (un paquet, §23)
            lu_p = await self.boite.partie_groupee(h, flags, bool(self.catalogue.criminels),
                                                   bool(self.catalogue.boutiques))
            octets_boutiques = self.boite.octets_boutiques
        else:
            octets_boutiques = b""
            lu = await self.boite.bits_partie(h, flags)
            lu_p = None if lu is None else (*lu, b"")
        if lu_p is None:
            return None
        ouverts, poses, octets_criminels = lu_p
        # Yo-criminels : arrêté quand l'octet `wantedNN` atteint le nombre d'étapes (dans le même paquet)
        arretes = {n for n, e in self.catalogue.criminels.values()
                   if len(octets_criminels) >= n and octets_criminels[n - 1] >= e}
        if self.catalogue.boss or secours or self.catalogue.tablos:
            boss = (poses & set(self.catalogue.boss.values())) | bp.boss_octets_atteints(pseudos, poses)
            tablos = poses & set(self.catalogue.tablos.values())
            # don d'un spot fait sans table (bit jamais posé) : l'évènement joué juste après le don fait foi
            seuls = {bit for bit, f in secours.items() if f in poses and bit not in ouverts}
            ouverts = ouverts | seuls
        quetes: set[int] | None = set()
        if self.catalogue.quetes:
            lu = await self.boite.quetes_terminees(h, self.catalogue.quetes.values(), self._adresse_q)
            if lu is None:
                self.log.debug("Bloc des quêtes illisible (Q nul ou hors du tas) : quêtes relues plus tard")
                quetes = None
            else:
                adresse_q, quetes = lu
                apres = await self.boite.adresse_quetes()
                if apres != adresse_q:
                    self._adresse_q = None                   # Q déplacé : données écartées, chaînage relu en entier
                    return None
                self._adresse_q = adresse_q
        if not await self._meme_partie(h):
            return None
        self._secours_seuls = seuls
        self._criminels_arretes = arretes
        self._boutiques_bits = bp.bits_boutiques(octets_boutiques) if octets_boutiques else set()
        return ouverts, boss, quetes, tablos

    def _secours(self) -> dict[int, int]:
        """Détection de secours (`bp.SPOTS_SECOURS`) des spots de la graine : bit de spot -> flag « évènement vu »."""
        return {bit: f for bit, f in bp.SPOTS_SECOURS.items() if bit in self.catalogue.spots}

    async def _evaluer_sauvegarde(self, h) -> str:
        """Statut de la sauvegarde chargée (règle v4) : `liee` seulement si P+0x3BC == ident_partie. Une
        sauvegarde SANS identifiant n'est liée que si c'est une PARTIE NEUVE (liaison automatique) ; la liaison manuelle
        n'existe plus (décision de l'humain du 2026-09-28, option (b)) : une sauvegarde existante reste « non liée »,
        le joueur commence une nouvelle partie."""
        ident = self.ident_partie
        if h.ident_sauvegarde == ident:
            return "liee"
        if h.ident_sauvegarde:
            return "autre"
        if h.version < bp.VERSION_LIAISON:
            return "jeu_ancien"                          # un jeu v3 ne sait pas lier sans risque
        d = self._demande
        if d is not None and h.liaison_demande == d[2] and h.terrain_numero == d[0]:
            return "liaison"                             # le jeu la traitera au terrain stable
        if not h.stable:
            # décision seulement sur le terrain stable (une nouvelle partie n'est pas encore « non liée »)
            return "non_liee" if self.sauvegarde == "non_liee" else "attente"
        cle_eval = (h.terrain_numero, h.compteur, h.chapitre, h.pas_scenario, h.progression, h.spots)
        if cle_eval == self._eval_cle:
            return "non_liee"
        bits = await self._lire_bits(h)
        if bits is None:
            return "non_liee"
        ouverts, boss, quetes, tablos = bits
        seuls = set(self._secours_seuls)
        self._eval_cle = cle_eval
        indices = self._indices_ap()
        # critères de partie neuve sur les bits RÉELS : un Filet donné sans table dans une partie neuve (chapitre 1,
        # client coupé) n'empêche pas la liaison automatique, et son check est envoyé après elle (G1-3)
        raison = raison_non_neuve(h, ouverts - seuls, indices, boss, quetes or (), tablos)
        if raison is None:
            cle = secrets.randbelow(0x7FFF) + 1           # partie neuve : aucune quête finie avant la liaison
            l = Liaison((ouverts - seuls) & indices, h.progression & VICTOIRE, False, "auto", set(boss),
                        set(quetes or ()), set(), set(tablos), self._numeros_quetes())
            self.log.info("Nouvelle partie détectée : liaison automatique à la partie AP %#010x", ident)
        else:
            self.raison_non_liee = raison
            self.log.info("Sauvegarde non liée à la partie AP (%s) : rien n'est livré ni envoyé ; une partie "
                          "Archipelago se joue sur une nouvelle partie", raison)
            return "non_liee"
        self.liaisons.ecrire(ident, cle, l)              # instantané enregistré AVANT la demande
        n = await self.boite.demander_liaison(h.terrain_numero, cle)
        self._demande = (h.terrain_numero, cle, n)
        self.stats.liaisons += 1
        return "liaison"

    async def _charger_liaison(self, h) -> Liaison | None:
        """Instantané de la sauvegarde liée chargée ; sans instantané enregistré (autre ordinateur, sauvegarde
        marquée par un ancien client, clé manuelle d'une version antérieure : la liaison manuelle n'existe plus depuis
        le 2026-09-28 mais ces sauvegardes restent liées, règle G1-2), celui de la première vue : ce qui est déjà ouvert ou
        gagné maintenant ne compte pas (seule une clé automatique v4, partie neuve, en est dispensée)."""
        ident, cle = self.ident_partie, h.liaison_sauvegarde
        l = self.liaisons.lire(ident, cle)
        if l is not None and (l.manuelle or cle & bp.LIAISON_MANUELLE):
            return self._liaison_manuelle(l, cle)
        if l is None and cle & bp.LIAISON_MANUELLE:
            # liaison manuelle sans instantané (autre ordinateur, fichier perdu) : même règle qu'à la liaison (G1-2) ;
            # la victoire déjà présente à cette première vue ne compte pas (on ne sait pas si elle suit la liaison)
            l = self._liaison_manuelle_vide(h)
            self.log.warning("Sauvegarde liée manuellement sans instantané (clé %#06x) : checks déjà faits envoyés%s",
                             cle, " ; victoire déjà acquise ignorée" if l.progression else "")
            self.liaisons.ecrire(ident, cle, l)
            return l
        if l is not None and l.boss is not None and l.quetes is not None and l.secours is not None \
                and l.tablos is not None:
            return await self._couvrir_quetes(h, l, cle)
        if l is not None:
            # instantané pris par un client sans boss (ou sans boss de quête) : même règle qu'un instantané absent
            # (§11.3), pour la partie manquante seulement. Liaison automatique = partie neuve (chapitre 1) : aucun
            # boss vaincu ni aucune quête finie avant elle ; sinon, première vue.
            if l.origine == "auto" and not l.manuelle:
                l.boss = set() if l.boss is None else l.boss
                l.quetes = set() if l.quetes is None else l.quetes
                l.secours = set() if l.secours is None else l.secours
                l.tablos = set() if l.tablos is None else l.tablos
            else:
                bits = await self._lire_bits(h)
                if bits is None:
                    return None
                if l.boss is None:
                    l.boss = set(bits[1])
                    self.log.warning("Instantané sans boss (clé %#06x) : %d boss déjà vaincu(s) à la première vue ne "
                                     "compteront pas", cle, len(l.boss))
                if l.quetes is None and bits[2] is not None:  # Q illisible : complété par _resynchroniser
                    l.quetes = set(bits[2])
                    self.log.warning("Instantané sans boss de quête (clé %#06x) : %d quête(s) déjà terminée(s) à la "
                                     "première vue ne compteront pas", cle, len(l.quetes))
                if l.tablos is None:
                    l.tablos = set(bits[3])
                    if l.tablos:
                        self.log.warning("Instantané sans Tablo-blabla (clé %#06x) : %d Yo-kai déjà appelé(s) à la "
                                         "première vue ne compteront pas", cle, len(l.tablos))
                if l.secours is None:
                    l.secours = self._secours_seuls & self._indices_ap()
                    if l.secours:
                        self.log.warning("Instantané sans détection de secours (clé %#06x) : %d don(s) de spot faits "
                                         "sans table à la première vue ne compteront pas", cle, len(l.secours))
        elif cle and not cle & bp.LIAISON_MANUELLE:
            l = Liaison(set(), 0, False, "auto", set(), set(), set(), set(), self._numeros_quetes())
        else:
            bits = await self._lire_bits(h)
            if bits is None:
                return None
            ouverts, boss, quetes, tablos = bits
            l = Liaison(ouverts & self._indices_ap(), h.progression & VICTOIRE, bool(cle), "premiere_vue", set(boss),
                        None if quetes is None else set(quetes), self._secours_seuls & self._indices_ap(), set(tablos),
                        None if quetes is None else self._numeros_quetes())
            self.log.warning("Sauvegarde liée sans instantané (clé %#06x) : %d coffre(s)/spot(s) déjà ouverts, %d "
                             "boss déjà vaincu(s), %d Tablo-blabla déjà appelé(s) et la victoire déjà acquise ne "
                             "compteront pas", cle, len(l.exclus), len(boss) + len(quetes or ()), len(tablos))
        self.liaisons.ecrire(ident, cle, l)
        return await self._couvrir_quetes(h, l, cle)

    def _liaison_manuelle_vide(self, h) -> Liaison:
        """Instantané d'une liaison MANUELLE (G1-2) : rien d'exclu, bits de victoire présents gardés."""
        return Liaison(set(), h.progression & VICTOIRE, True, "manuelle", set(), set(), set(), set(),
                       self._numeros_quetes())

    def _liaison_manuelle(self, l: Liaison, cle: int) -> Liaison:
        """Instantané d'une liaison manuelle relu : un instantané écrit par un client d'avant G1-2 excluait les
        checks déjà faits à la liaison ; ils sont remis en jeu (envoyés à la resynchronisation qui suit), la
        victoire déjà acquise reste ignorée (`progression` inchangée)."""
        exclus = (len(l.exclus_tous()), len(l.boss or ()), len(l.quetes or ()), len(l.tablos or ()))
        if any(exclus) or None in (l.boss, l.quetes, l.secours, l.tablos) or not l.manuelle \
                or l.quetes_couvertes != self._numeros_quetes():
            if any(exclus):
                self.log.warning("Liaison manuelle antérieure (clé %#06x) : %d coffre(s)/spot(s), %d boss, %d quête(s) "
                                 "et %d Tablo-blabla exclus jusqu'ici seront envoyés (G1-2)", cle, *exclus)
            l = Liaison(set(), l.progression, True, "manuelle", set(), set(), set(), set(), self._numeros_quetes())
            self.liaisons.ecrire(self.ident_partie, cle, l)
        return l

    def _numeros_quetes(self) -> set[int]:
        """N° des quêtes lues par ce client (boss de quête, requêtes, services de la graine)."""
        return set(self.catalogue.quetes.values())

    async def _couvrir_quetes(self, h, l: Liaison, cle: int) -> Liaison | None:
        """Instantané pris par un client qui ne lisait pas toutes les quêtes de la graine (avant les requêtes : seules
        les quêtes de boss) : les quêtes NON couvertes sont complétées comme un instantané absent (§11.3) — liaison
        automatique (partie neuve) : aucune quête finie avant elle ; sinon, première vue : celles déjà terminées
        maintenant ne compteront pas. Q illisible : complété plus tard (`_resynchroniser`)."""
        if l.quetes is None:
            return l
        couvertes = l.quetes_couvertes if l.quetes_couvertes is not None else set(self.catalogue.quetes_boss)
        manquantes = self._numeros_quetes() - couvertes
        if not manquantes and l.quetes_couvertes is not None:
            return l
        if manquantes and not (l.origine == "auto" and not l.manuelle):
            bits = await self._lire_bits(h)
            if bits is None:
                return None
            if bits[2] is None:
                return l                                     # Q illisible : relu plus tard
            deja = bits[2] & manquantes
            l.quetes = set(l.quetes) | deja
            if deja:
                self.log.warning("Instantané sans requêtes (clé %#06x) : %d quête(s) déjà terminée(s) à la première vue "
                                 "ne compteront pas", cle, len(deja))
        l.quetes_couvertes = couvertes | self._numeros_quetes()
        self.liaisons.ecrire(self.ident_partie, cle, l)
        return l

    async def _suivre_partie(self, h, brut: bytes) -> None:
        r = self.reseau
        if not h.partie:
            self._partie_cle = None
            self._oublier_sauvegarde()
            self._notif_sauvegarde = None
            await self._lire_journal(h, ignorer=True)
            return
        cle = (h.adresse_p, h.ident_sauvegarde, h.liaison_sauvegarde)
        if cle != self._partie_cle:
            self._partie_cle = cle
            self._oublier_sauvegarde()
            self._resync_demandee = True
            self._adresse_q = self._adresse_rang = None
            self._victoire_t = 0.0
            self._echecs_notifies.clear()
        # verrous exigés absents du jeu : aucune liaison, aucun don, aucun check (la partie n'est pas jouable)
        # (mélange des boss de la graine non appliqué, version 2 : même refus, sous son propre statut)
        statut = "verrous_incompatibles" if self.verrous_manquants or self.boutiques_manquantes \
            or self.distrib.manquants or self.leg.manquants \
            else self.boss_manquant or self.yokai_manquant or await self._evaluer_sauvegarde(h)
        if statut != self.sauvegarde:
            self.log.info("Sauvegarde chargée : %s (identifiant %#010x, attendu %#010x)", statut,
                          h.ident_sauvegarde, self.ident_partie)
            self.sauvegarde = statut
        if statut != "liee":
            if statut in NOTIF_SAUVEGARDE and self._notif_sauvegarde != (cle, statut):
                self._notif_sauvegarde = (cle, statut)
                textes = NOTIF_SAUVEGARDE_PAR_LANGUE.get(self.catalogue.langue, NOTIF_SAUVEGARDE)[statut]
                for texte in (textes,) if isinstance(textes, str) else textes:
                    self._notifier(texte)
            await self._lire_journal(h, ignorer=True)    # rien n'est envoyé depuis cette sauvegarde
            return
        if self._liaison is None:
            self._liaison = await self._charger_liaison(h)
            if self._liaison is None:
                return
        maintenant = time.monotonic()
        # (dons : déposés en fin de tour, `_deposer_dons`, avec les autres écritures dans un seul arrêt)
        # journal ; spots publiés dans l'en-tête (bits 558..) : un changement déclenche la relecture
        if h.spots != self._spots_vus:
            self._spots_vus = h.spots
            self._resync_demandee = True
        # boss : la victoire pose le flag du combat, puis l'histoire avance (phase suivante) ; un changement de
        # chapitre ou de pas de scénario relit les flags sans attendre la resynchronisation périodique. Boss de
        # quête : la quête se termine par une scène ou un rapport suivi d'un retour sur le terrain
        # (`terrain_numero`) : ce changement relit aussi. Tablo-blabla : l'appel du Yo-kai (menu, puis scène du
        # territoire) se termine par un retour sur le terrain : même relecture. Tout passage sur le terrain relit
        # (évènement rare : fin de combat, de scène, de menu, changement de carte ; §23), la relecture périodique
        # n'est plus qu'un filet de sécurité (`periode_filet`)
        progression = (h.chapitre, h.pas_scenario, h.terrain_numero)
        if progression != self._progression_vue:
            self._progression_vue = progression
            self._resync_demandee = True
        await self._lire_journal(h)
        # resynchronisation par les bits persistants
        if self._resync_demandee or maintenant - self._resync_t > self.periode_filet:
            await self._resynchroniser(h)
        self._alerter_chapitre_10(h)
        # victoire : seulement si elle est apparue APRÈS la liaison (instantané)
        nouvelle_victoire = h.progression & VICTOIRE & ~self._liaison.progression
        # V3, lot 3 : objectif d'après-jeu : partie terminée ET bits du Médaillium de l'objectif (lus par le suivi du
        # tracker, sur le retour au terrain qui suit le combat ; au plus tard au filet de PERIODE_MEDAILLIUM)
        if not self._victoire_envoyee and nouvelle_victoire and self._objectif_atteint():
            self._victoire_envoyee = True
            if self.catalogue.objectif_seuil is not None:
                detail = ", Médaillium %d / %d" % (len(self._medailles_objectif), self.catalogue.objectif_seuil)
            else:
                detail = ", Médaillium %s" % list(self.catalogue.objectif_medailles) \
                    if self.catalogue.objectif_medailles else ""
            self.log.info("Victoire (progression %#x, chapitre %d%s) : CLIENT_GOAL", h.progression, h.chapitre,
                          detail)
            await r.signaler_victoire()
            self._notifier(textes_bandeau(self.catalogue.langue)["objectif"])

    def _alerter_chapitre_10(self, h) -> None:
        """Bandeau « ville bouclée au chapitre 10, N checks à faire avant » dès la phase 9-80 (dernière promenade libre
        avant le chapitre 10), ou à la liaison d'une sauvegarde déjà au chapitre 10, une fois par sauvegarde liée, s'il reste des locations de `avant_chapitre_10` non vérifiées (serveur : manquantes, ni
        vérifiées ni en attente). Sauvegarde déjà victorieuse ou après-jeu (la ville est rouverte) : marqué sans bandeau.
        Appelé seulement pour une sauvegarde liée (mêmes garde-fous que les checks)."""
        l, r = self._liaison, self.reseau
        if l is None or r is None or l.alerte_ch10 or not self.catalogue.avant_chapitre_10:
            return
        if not h.progression & bp.PROGRESSION_CHAPITRE or (h.chapitre, h.pas_scenario) < SEUIL_ALERTE_CH10:
            return
        restants = set()
        if h.chapitre <= 10 and not h.progression & VICTOIRE:
            restants = ((self.catalogue.avant_chapitre_10 & r.locations_manquantes)
                        - r.locations_verifiees - r.locations_en_attente)
        l.alerte_ch10 = True
        self.liaisons.ecrire(self.ident_partie, h.liaison_sauvegarde, l)
        if not restants:
            return
        self.log.info("Chapitre %d-%d : %d check(s) hors chapitre 10 restent (ville bouclée de 10-10 à la fin)",
                      h.chapitre, h.pas_scenario, len(restants))
        textes = ALERTE_CHAPITRE_10.get(self.catalogue.langue, ALERTE_CHAPITRE_10["fr"])
        for t in textes:
            self._notifier(t.format(n=len(restants)))

    def _don_a_deposer(self, o: ObjetReseau, fini: bool = False) -> ObjetADonner:
        """Objet de ce monde trouvé à un spot NON substitué : le jeu l'a donné lui-même (DONNER), le rang est
        déposé comme « type 0 » (ignoré par le jeu, compteur avancé) pour ne pas le donner deux fois."""
        e = self.catalogue.emplacements.get(o.location)
        if e is not None and not e.substituer and self.reseau is not None and o.player == self.reseau.slot:
            return ObjetADonner(0, 0, 0)
        don = self.catalogue.don(o.item)
        if don.type == 0 and o.item in self.catalogue.objets_du_jeu:
            # invitation : son objet du jeu, s'il existe chez ce joueur (RomFS patché à l'installation) ; sinon le jeu
            # l'ignore (OBJET_INCONNU, compteur avancé) comme le « type 0 » d'avant. L'invité ne dépend pas de ce don.
            return ObjetADonner(bp.DON_OBJET, self.catalogue.objets_du_jeu[o.item], 1)
        if don.type == bp.TYPE_DON_PIEGE and fini:
            # objectif atteint (§14 des pièges) : piège sans effet, déposé en « type 0 » (compteur avancé, file libre)
            return ObjetADonner(0, 0, 0)
        return don

    @property
    def partie_finie(self) -> bool:
        """Objectif de la graine atteint : victoire envoyée par ce client, statut du slot lu sur le serveur (but), ou
        mémoire de la partie dans `liaisons.json` (clé « <partie>:victoire », écrite par le suivi des pièges)."""
        r = self.reseau
        if self._victoire_envoyee or (r is not None and r.but_atteint):
            return True
        ident = self.ident_partie
        if not ident:
            return False
        if ident not in self._victoire_memoire:
            self._victoire_memoire[ident] = self.liaisons.lire_victoire(ident)
        return self._victoire_memoire[ident]

    async def _lire_journal(self, h, ignorer: bool = False) -> None:
        """Évènements non lus (index de lecture du CLIENT : `journal_lu` du jeu n'est écrit qu'avec une autre écriture,
        ou au plus tard après TOURS_ACQUITTEMENT tours, `_acquitter_journal` ; le jeu ne s'en sert que pour compter les
        évènements écrasés)."""
        lu = max(h.journal_lu, self._journal_lu)
        if h.journal_ecrit <= lu:
            return
        j = await self.boite.lire_journal(h, lu)
        if not ignorer and not await self._meme_partie(h):
            return                                       # relu au prochain tour, avec le bon en-tête
        if j.perdus:
            self.log.info("%d évènements du journal perdus : resynchronisation", j.perdus)
            self._resync_demandee = True
        if not ignorer:
            await self._traiter_evenements(h, j.evenements)
        self._journal_lu = j.ecrit
        if not self._acquitter_t:
            self._acquitter_t = time.monotonic()

    async def _acquitter_journal(self, h) -> None:
        """`journal_lu` = index de lecture du client : dans l'arrêt déjà pris par une autre écriture de ce tour, sinon
        au plus tard TOURS_ACQUITTEMENT tours après la lecture (ou quand le retard approche la capacité du journal)."""
        if not self._acquitter_t or self._journal_lu <= h.journal_lu:
            self._acquitter_t = 0.0
            return
        if self.pont.en_marche and time.monotonic() - self._acquitter_t < TOURS_ACQUITTEMENT * self.periode \
                and self._journal_lu - h.journal_lu < bp.CAP_JOURNAL // 2:
            return
        await self.boite.acquitter_journal(self._journal_lu)
        self._acquitter_t = 0.0

    async def _deposer_dons(self, h) -> None:
        """Dons reçus d'AP -> file de dons, pour la sauvegarde liée seulement (liaison chargée). Pré-vérification sans
        arrêt (`Boite.deposer_dons` avec l'en-tête du tour) : le jeu n'est arrêté que s'il y a vraiment à écrire."""
        if not (self._connexion_prete and self.reseau is not None and h.partie and self.sauvegarde == "liee"
                and self._liaison is not None):
            return
        maintenant = time.monotonic()
        a_livrer = len(self.objets) > h.compteur
        cle_depot = (self._instance, h.compteur, len(self.objets), h.ident_sauvegarde)
        if not a_livrer or (cle_depot == self._depot_cle and maintenant - self._depot_t <= self.periode_filet):
            return
        fini = self.pieges.actif and self.partie_finie
        dons = [self._don_a_deposer(o, fini) for o in self.objets]
        res = await self.boite.deposer_dons(dons, h)
        self._depot_cle, self._depot_t = cle_depot, maintenant
        if res.ecrits:
            self.stats.depots += len(res.ecrits)
            self.log.info("Dons déposés : %d (compteur %d, %d reçus)", len(res.ecrits), res.compteur, len(self.objets))
        if res.conflits:
            self.log.warning("Dons en attente au contenu différent (non touchés) : %s", res.conflits)

    async def _traiter_evenements(self, h, evts) -> None:
        self.portails.evenements(h, evts)                # récompense des portails : mémoire des entrées tirées
        self.pieges.evenements(h, evts)                  # pièges reçus / finis : mémoire de la sauvegarde liée
        index_loc = self.catalogue.index_vers_location
        exclus = self._liaison.exclus if self._liaison is not None else set()
        checks, dons = [], []
        bits_vus: set[int] = set()                       # bits d'articles de boutique montrés (évènements BOUTIQUE)
        for e in evts:
            if e.type == bp.EVT_COFFRE:
                idx = e.index_tbox
                loc = index_loc.get(idx) if idx is not None else None
                if loc is None and e.etiquette in self.catalogue.coffres:
                    loc = e.etiquette                    # étiquette de la table = identifiant de location
                # check immédiat seulement si le flag TBox vient d'être posé (0x01) ; un coffre doré est d'abord
                # « regardé » sans être ouvert (0x35EB(0), ev98_0070) puis marqué par 0x35F1 : son check vient
                # du bit persistant (resynchronisation), jamais d'un coffre resté fermé (excédent, combat)
                if loc is not None and e.drapeaux & bp.EVT_COFFRE_MARQUE_OUVERT \
                        and self.catalogue.coffres[loc] not in exclus:
                    checks.append(loc)
                self._resync_demandee = True
            elif e.type == bp.EVT_OBJET_JEU:
                self._resync_demandee = True             # don d'objet-clé substitué (J3) : bit à relire
                if e.drapeaux & bp.EVT_OBJET_SUBSTITUE and e.id in bp.DONS_EN_AMONT.values() \
                        and e.etiquette in self.catalogue.emplacements:
                    # magasin (1-86) : le jeu ouvre la fenêtre de l'objet de la location : check à ce moment, sans
                    # fenêtre ApAnim ; sauvegarde déjà passée par 1-90 à la liaison : ne compte pas (`boss` de l'instantané)
                    self._fenetres_en_amont.add(e.etiquette)
                    l = self._liaison
                    if l is None or self.catalogue.boss.get(e.etiquette) not in (l.boss or ()):
                        checks.append(e.etiquette)
            elif e.type == bp.EVT_RECOMPENSE:
                # récompense de quête remplacée (v5) : l'écran de résultat montre l'objet ; la quête vient de passer à
                # 255 (relecture) et l'objet de ce monde, livré ensuite par la file, n'a pas à être réannoncé
                if e.etiquette in self.catalogue.recompenses:
                    self._recompenses_montrees.add(e.etiquette)
                self._resync_demandee = True
            elif e.type == bp.EVT_ACHAT:
                # premier achat d'un article de boutique (v9) : check immédiat (le bit est posé, relu ensuite) ; l'objet
                # de ce monde montré, livré ensuite par la file, n'a pas à être réannoncé
                b = self.catalogue.boutiques.get(e.etiquette)
                if b is not None:
                    self._recompenses_montrees.add(e.etiquette)
                    l = self._liaison
                    if l is None or l.boutiques is None or b.bit not in l.boutiques:
                        checks.append(e.etiquette)
                self._resync_demandee = True
            elif e.type == bp.EVT_INVITE:
                # annonce d'un invité de l'Auberge fermée par le joueur : notée pour la sauvegarde (jamais remontrée)
                l = self._liaison
                if l is not None and e.valeur not in l.invites_annonces \
                        and any(inv.medaille == e.valeur for inv in self.catalogue.invites):
                    l.invites_annonces.add(e.valeur)
                    self.liaisons.ecrire(self.ident_partie, h.liaison_sauvegarde, l)
                    self.log.info("Invité de l'Auberge annoncé en jeu : n° %d du Médaillium", e.valeur)
            elif e.type == bp.EVT_INVITE_CHAMBRE:
                # le jeu a attribué une chambre à un invité : notée pour la sauvegarde (il la garde jusqu'à l'amitié,
                # d'un lancement à l'autre) ; la liste est réécrite avec elle au même tour
                l = self._liaison
                if l is not None and 0 < e.quantite < bp.INVITES_PIECES \
                        and l.invites_chambres.get(e.valeur) != e.quantite \
                        and any(inv.medaille == e.valeur and inv.param != bp.INVITES_PARAM_PNJ
                                for inv in self.catalogue.invites):
                    for m in [m for m, c in l.invites_chambres.items() if c == e.quantite]:
                        del l.invites_chambres[m]            # l'ancien occupant (devenu ami) a libéré la chambre
                    l.invites_chambres[e.valeur] = e.quantite
                    self.liaisons.ecrire(self.ident_partie, h.liaison_sauvegarde, l)
                    self.log.info("Invité de l'Auberge n° %d du Médaillium : chambre %d", e.valeur, 100 + e.quantite)
            elif e.type == bp.EVT_BOUTIQUE:
                bits_vus.update(bp.bits_evt_boutique(vars(e)))   # articles visibles d'une boutique ouverte (§10)
            elif e.type in (bp.EVT_DISTRIBUTEUR, bp.EVT_DISTRIBUTEUR_VU):
                # V3, lot C1 : boisson Archipelago achetée (check), distributeur ouvert (indices)
                self.distrib.evenement(e, checks, self._recompenses_montrees)
            elif e.type == bp.EVT_DON and (e.drapeaux == bp.CODE_OK or (
                    e.drapeaux in (bp.CODE_TYPE_INCONNU, bp.CODE_OBJET_INCONNU) and self._don_sans_objet(e.valeur))):
                dons.append(e.valeur)
            elif e.type == bp.EVT_DON_ECHEC and e.valeur not in self._echecs_notifies:
                self._echecs_notifies.add(e.valeur)
                self._notifier(textes_bandeau(self.catalogue.langue)["plein"])
        if checks:
            await self._envoyer_checks(checks)
        if bits_vus:
            self._indiquer_boutique(bits_vus)
        self.distrib.indiquer_vues()                     # V3, lot C1 : indices des boissons AP montrées
        self._notifier_dons(dons)

    def _indiquer_boutique(self, bits: set[int]) -> None:
        """Évènements BOUTIQUE (v9, boutique ouverte, `archipelago_boutiques.md` §10) : indices « annoncés »
        (LocationScouts `create_as_hint` 2, le serveur n'annonce que les nouveaux) des articles que le jeu a réellement
        MONTRÉS à cette ouverture (bits publiés : ligne AP posée et condition d'affichage vraie ; jamais un article
        conditionnel encore caché), présents dans la graine et pas encore cochés (ni en attente, ni déjà indiqués, ni
        faits avant la liaison), une seule fois par article. Sauvegarde liée seulement (le journal d'une autre sauvegarde
        est ignoré ; revérifié ici)."""
        r, l = self.reseau, self._liaison
        if r is None or l is None or r.slot is None or not self._connexion_prete or self.sauvegarde != "liee":
            return
        locs = {loc for loc, x in self.catalogue.boutiques.items() if x.bit in bits}
        codes = sorted({self.catalogue.boutiques[loc].boutique or "?" for loc in locs})
        cle = (str(r.room_info.get("seed_name", "")), int(r.slot))
        deja = set()
        for h in r.indices:
            with contextlib.suppress(KeyError, TypeError, ValueError):
                if int(h.get("finding_player", -1)) == r.slot:
                    deja.add(int(h["location"]))
        faits = self._boutiques_bits | (l.boutiques or set())
        a_indiquer = sorted(loc for loc in locs
                            if loc in r.locations_manquantes and loc not in r.locations_verifiees
                            and loc not in r.locations_en_attente and loc not in deja
                            and (*cle, loc) not in self._indices_boutiques
                            and self.catalogue.boutiques[loc].bit not in faits)
        if not a_indiquer:
            return
        self._indices_boutiques |= {(*cle, loc) for loc in a_indiquer}
        self._lancer(self._envoyer_indices_boutique(r, cle, a_indiquer, "/".join(codes)))

    async def _envoyer_indices_boutique(self, r: ClientAP, cle: tuple[str, int], locs: list[int],
                                        code: str) -> None:
        try:
            await r.scouter(locs, create_as_hint=2)
        except Exception as e:                               # déconnexion : redemandés à la prochaine ouverture
            self._indices_boutiques -= {(*cle, loc) for loc in locs}
            self.log.info("Indices de la boutique %s non créés : %s", code, e)
            return
        self.log.info("Indices de la boutique %s : %d article(s) %s", code, len(locs), locs)

    def _don_sans_objet(self, numero: int) -> bool:
        """Don n° `numero` (1 = premier de ReceivedItems) d'un objet AP connu SANS objet du jeu (don « aucun » : Rang
        de montre, verrou progressif) : le jeu l'ignore (TYPE_INCONNU) mais il est bien reçu, donc annoncé. Une
        invitation (don « aucun », objet du jeu facultatif) dont l'objet n'existe pas chez ce joueur est ignorée de
        même (OBJET_INCONNU) et annoncée de même."""
        if not 1 <= numero <= len(self.objets):
            return False
        o = self.catalogue.objets.get(self.objets[numero - 1].item)
        # (piège déposé en « type 0 » après la victoire, §14 des pièges : annoncé « ignoré »)
        return o is not None and (o.type == 0 or (o.type == bp.TYPE_DON_PIEGE and self.partie_finie))

    def _notifier_dons(self, numeros: list[int]) -> None:
        r = self.reseau
        spots = set(self.catalogue.spots.values()) | set(self.catalogue.emplacements)   # dons substitués (bit ou non)
        a_dire, pieges = [], []
        for n in numeros:
            if not 1 <= n <= len(self.objets):
                continue
            o = self.objets[n - 1]
            don = self.catalogue.don(o.item)
            if don.type == bp.TYPE_DON_PIEGE:
                pieges.append(don.hash)                  # piège : toujours annoncé (son bandeau, pas « Reçu : »)
                continue
            if o.player == r.slot and (o.location in self.catalogue.coffres or o.location in spots
                                       or o.location in self._recompenses_montrees):
                continue                                 # le coffre (don substitué, écran de résultat) l'a montré
            a_dire.append(o)
        rappel = self._rappel_mirapo(numeros)
        if len(a_dire) > RESUME_AU_DELA:
            self._notifier(textes_bandeau(self.catalogue.langue)["recus"].format(n=len(a_dire)))
        else:
            for o in a_dire:
                don = self.catalogue.don(o.item)
                joueur = r.nom_joueur(o.player) if o.player not in (0, r.slot) else None
                q = don.quantite if don.type == bp.DON_OBJET else 1
                self._notifier(texte_recu(r.nom_objet(o.item, r.slot), joueur, q, self.catalogue.langue))
        for texte in rappel:
            self._notifier(texte)
        # lot 4 des pièges : « Piège reçu : <nom> » (ou « Piège ignoré » s'il est absent du patch), FR / EN ; après la
        # victoire (§14) : « Piège ignoré : <nom> » puis « Partie finie : sans effet »
        for texte in self.pieges.textes_reception(pieges, self.catalogue.langue, RESUME_AU_DELA,
                                                  fini=bool(pieges) and self.partie_finie):
            self._notifier(texte, pgs.NOTIF_MAX_CAR)

    def _rappel_mirapo(self, numeros: list[int]) -> list[str]:
        """Mirapo de poche : bandeau qui rappelle la commande (SELECT tenu sur le terrain) quand un de ces objets reçus
        est l'exemplaire qui la donne (le 2e « Miroirs progressifs »), une seule fois."""
        k = bp.VERROU_MIRAPO
        objet, seuil = self.catalogue.verrous3.get(k), self.catalogue.exemplaires3.get(k, 1)
        if not objet:
            return []
        for n in numeros:
            if 1 <= n <= len(self.objets) and self.objets[n - 1].item == objet and \
                    sum(1 for o in self.objets[:n] if o.item == objet) == seuil:
                return [texte_court(t) for t in RAPPEL_MIRAPO.get(self.catalogue.langue, RAPPEL_MIRAPO["fr"])]
        return []

    async def _resynchroniser(self, h) -> None:
        self._resync_demandee = False
        self._resync_t = time.monotonic()
        bits = await self._lire_bits(h)
        if bits is None:
            # lecture écartée (partie ou Q changés pendant la lecture) : réessayée au tour suivant, quelques fois
            self._resync_echecs += 1
            self._resync_demandee = self._resync_echecs <= ESSAIS_RELECTURE
            return
        self._resync_echecs = 0
        ouverts, boss, quetes, tablos = bits
        l = self._liaison
        if quetes is not None and l is not None and l.quetes is None:
            # instantané sans quêtes (Q illisible à la liaison) : complété à la première lecture réussie de Q, rien
            # n'est envoyé pour les quêtes déjà finies à ce moment (règle de la première vue)
            l.quetes = set(quetes)
            l.quetes_couvertes = self._numeros_quetes()
            self.liaisons.ecrire(self.ident_partie, h.liaison_sauvegarde, l)
            self.log.warning("Instantané des quêtes complété : %d quête(s) déjà terminée(s) ne compteront pas",
                             len(l.quetes))
        if quetes is not None and l is not None and l.quetes:
            # service déjà terminé à la liaison : son 255 est TRANSITOIRE (remis à 0 par le tirage des services,
            # archipelago_quetes.md §2.5) et le service revient ; vu à une autre phase, il sort de l'instantané (le
            # refaire comptera)
            leves = {n for n in l.quetes & self.catalogue.services if n not in quetes}
            if leves:
                l.quetes = set(l.quetes) - leves
                self.liaisons.ecrire(self.ident_partie, h.liaison_sauvegarde, l)
                self.log.info("Service(s) %s de l'instantané remis en jeu par le jeu : ils compteront", sorted(leves))
        exclus = l.exclus_tous() if l is not None else set()
        boss_exclus = (l.boss if l is not None else None) or set()
        quetes_exclues = (l.quetes if l is not None else None) or set()
        tablos_exclus = (l.tablos if l is not None else None) or set()
        checks = [loc for loc, idx in self.catalogue.coffres.items() if idx in ouverts and idx not in exclus]
        checks += [loc for bit, loc in self.catalogue.spots.items() if bit in ouverts and bit not in exclus]
        checks += [loc for loc, f in self.catalogue.boss.items() if f in boss and f not in boss_exclus]
        if quetes is not None:
            checks += [loc for loc, n in self.catalogue.quetes.items() if n in quetes and n not in quetes_exclues]
        checks += [loc for loc, f in self.catalogue.tablos.items() if f in tablos and f not in tablos_exclus]
        if self.catalogue.criminels and l is not None:
            criminels_exclus = self._completer_instantane(h, l, "criminels", self._criminels_arretes)
            checks += [loc for loc, (n, _e) in self.catalogue.criminels.items()
                       if n in self._criminels_arretes and n not in criminels_exclus]
        if self.catalogue.boutiques and l is not None:
            # boutiques : bit « premier achat fait » (octets de flags globaux, même paquet que la TBox)
            boutiques_exclues = self._completer_instantane(h, l, "boutiques", self._boutiques_bits)
            checks += [loc for loc, b in self.catalogue.boutiques.items()
                       if b.bit in self._boutiques_bits and b.bit not in boutiques_exclues]
        await self._envoyer_checks(checks)

    def _completer_instantane(self, h, l: Liaison, champ: str, deja: set[int]) -> set[int]:
        """Instantané `amis` / `criminels` de la liaison (exclus) ; absent (liaison prise par un client sans ces checks) :
        complété maintenant, vide pour une liaison automatique (partie neuve : rien de fait avant) ou manuelle (G1-2 : ce
        qui est déjà fait est envoyé), sinon (première vue) ce qui est déjà fait maintenant, qui ne comptera pas."""
        v = getattr(l, champ)
        if v is None:
            v = set(deja) if l.origine == "premiere_vue" and not l.manuelle else set()
            setattr(l, champ, v)
            self.liaisons.ecrire(self.ident_partie, h.liaison_sauvegarde, l)
            if v:
                self.log.warning("Instantané sans %s (clé %#06x) : %d déjà fait(s) à la première vue ne compteront pas",
                                 champ, h.liaison_sauvegarde, len(v))
        return v

    async def _verifier_amis(self, h, octets: bytes) -> None:
        """Checks « Ami : <Yo-kai> » : bits « ami » (P+0x44C | P+0x604) de la lecture groupée du Médaillium que le suivi du
        tracker vient de faire et de valider (sauvegarde liée, partie inchangée : `_suivre_tracker`) ; aucun paquet GDB."""
        l = self._liaison
        if not (self.catalogue.amis or self.catalogue.invites) or l is None or self.reseau is None:
            return
        ami = rando.zones_medaillium(octets).get("ami") or b""
        if len(ami) < rando.TAILLE_MEDAILLIUM:
            return
        paires = self.catalogue.amis_paires or list(self.catalogue.amis.items())
        # invités de l'Auberge des voyageurs : même bit « ami », même instantané de liaison
        paires = paires + [(inv.location, inv.medaille) for inv in self.catalogue.invites]
        poses = {n for n in {n for _loc, n in paires} if ami[n >> 3] >> (n & 7) & 1}
        exclus = self._completer_instantane(h, l, "amis", poses)
        await self._envoyer_checks(sorted({loc for loc, n in paires if n in poses and n not in exclus}))

    def _noter_medailles_objectif(self, octets: bytes) -> None:
        """V3, lot 3 : n° du Médaillium de l'objectif dont le bit est posé dans la lecture groupée qui vient d'être
        validée (sauvegarde liée) ; la victoire (`_suivre_partie`) les exige tous, en plus de la partie terminée."""
        if not self.catalogue.objectif_medailles:
            return
        ami = rando.zones_medaillium(octets).get("ami") or b""
        if len(ami) < rando.TAILLE_MEDAILLIUM:
            return
        avant = len(getattr(self, "_medailles_objectif", ()))
        self._medailles_objectif = {n for n in self.catalogue.objectif_medailles if ami[n >> 3] >> (n & 7) & 1}
        if self.catalogue.objectif_seuil is not None and len(self._medailles_objectif) != avant:
            # lot 18 : journal seulement (aucune lecture ni écriture de plus : mêmes octets que le suivi du tracker)
            self.log.info("Objectif Médaillium : %d / %d", len(self._medailles_objectif),
                          self.catalogue.objectif_seuil)

    def _objectif_atteint(self) -> bool:
        """Bits du Médaillium exigés par l'objectif tous posés (toujours vrai pour l'objectif de la V2) ; objectif
        à seuil (lot 18, « medaillium_complet ») : au moins `objectif_seuil` de ces bits."""
        poses = getattr(self, "_medailles_objectif", set())
        if self.catalogue.objectif_seuil is not None:
            return len(poses) >= self.catalogue.objectif_seuil
        return set(self.catalogue.objectif_medailles) <= poses

    async def _verifier_blasters(self, h, octets: bytes, debut: int) -> None:
        """V3, lot 3 : checks « Ψ Blasters : <boss> » : bit n (n° du terrain) du mot P + 0x64C, lu à la suite de la
        lecture groupée du Médaillium (aucun paquet GDB de plus) ; instantané de liaison `blasters`."""
        l = self._liaison
        if not self.catalogue.blasters or l is None or self.reseau is None:
            return
        mot = octets[P_BLASTERS - debut:P_BLASTERS - debut + 4]
        if len(mot) < 4:
            return
        v = int.from_bytes(mot, "little")
        poses = {n for n in set(self.catalogue.blasters.values()) if v >> n & 1}
        exclus = self._completer_instantane(h, l, "blasters", poses)
        await self._envoyer_checks(sorted(loc for loc, n in self.catalogue.blasters.items()
                                          if n in poses and n not in exclus))

    async def _envoyer_checks(self, locations: Iterable[int]) -> None:
        """LocationChecks des nouvelles locations ; notification « Envoyé : <objet> (<joueur>) » pour celles qui
        contiennent l'objet d'un autre monde (résumé au-delà de quelques-unes)."""
        r = self.reseau
        nouvelles = {int(x) for x in locations} - r.locations_verifiees - r.locations_en_attente
        if not nouvelles:
            return
        self.stats.checks_envoyes += len(nouvelles)
        self.log.info("Checks : %s", sorted(nouvelles))
        await r.verifier_locations(nouvelles)
        self._maj_checks()
        eligibles = self.catalogue.locations_anim() - self._fenetres_en_amont
        lot = sorted(loc for loc in nouvelles if loc in eligibles)
        if len(lot) > ao.LOT_MAX:
            # rattrapage (liaison d'une sauvegarde déjà avancée, client absent longtemps) : pas une file de fenêtres
            # à fermer une à une, le bandeau « Envoyé : … » suffit
            self.log.info("Fenêtres « objet obtenu » non montrées : %d checks concernés d'un coup (rattrapage)", len(lot))
            lot = []
        ajoutees = self.anims.ajouter(lot)
        if ajoutees:
            self.log.info("Fenêtre « objet obtenu » à montrer dans le jeu : %s", ajoutees)
        envois = [self._scout[loc] for loc in sorted(nouvelles)
                  if loc in self._scout and self._scout[loc].player != r.slot]
        if len(envois) > RESUME_AU_DELA:
            self._notifier(textes_bandeau(self.catalogue.langue)["envoyes"].format(n=len(envois)))
            return
        for o in envois:
            self._notifier(texte_envoye(r.nom_objet(o.item, o.player), r.nom_joueur(o.player), self.catalogue.langue))

    # ------------------------------------------------------------------------------ onglet « Checks » du lanceur
    def _contenu_scout(self, o: ObjetReseau) -> dict:
        r = self.reseau
        return {"objet": r.nom_objet(o.item, o.player), "joueur": r.nom_joueur(o.player), "soi": o.player == r.slot,
                "flags": o.flags}

    def _indices_du_monde(self) -> dict[int, dict]:
        """Indices (hints) du serveur qui portent sur une location de CE monde : location -> contenu indiqué."""
        r = self.reseau
        out: dict[int, dict] = {}
        for h in r.indices:
            try:
                if int(h.get("finding_player", -1)) != r.slot:
                    continue
                dest = int(h["receiving_player"])
                out[int(h["location"])] = {"objet": r.nom_objet(int(h["item"]), dest), "joueur": r.nom_joueur(dest),
                                           "soi": dest == r.slot, "trouve": bool(h.get("found")),
                                           "flags": int(h.get("item_flags", 0) or 0)}
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def _donnees_checks(self, connecte: bool | None = None) -> dict | None:
        r = self.reseau
        if r is None or not self._connexion_prete or r.slot is None:
            return None
        toutes = r.locations_manquantes | r.locations_verifiees
        faites = r.locations_verifiees | (r.locations_en_attente & toutes)
        recus = [{"n": i + 1, "id": o.item, "objet": r.nom_objet(o.item, r.slot), "expediteur": r.nom_joueur(o.player),
                  "soi": o.player == r.slot,
                  "location": r.nom_location(o.location, o.player) if o.location >= 0 else "", "flags": o.flags}
                 for i, o in enumerate(self.objets)]
        return ck.construire_checks(
            ident_partie=self.ident_partie, graine=str(r.room_info.get("seed_name", "")), slot=r.slot, team=r.team,
            joueur=r.nom_joueur(r.slot), options=ck.options_de_slot_data(r.slot_data), locations=toutes, faites=faites,
            contenus={l: self._contenu_scout(o) for l, o in self._scout.items()}, indices=self._indices_du_monde(),
            recus=recus, connecte=r.connecte if connecte is None else connecte,
            contenus_complets=self._scout_fait and toutes <= set(self._scout))

    def _maj_checks(self, connecte: bool | None = None) -> None:
        """`checks.json` pour le lanceur : réécrit seulement s'il a changé (fichier local, aucun paquet GDB)."""
        try:
            d = self._donnees_checks(connecte)
            if d is not None:
                self._checks_empreinte = ck.ecrire_checks(self.stockage.dossier, d, self._checks_empreinte)
        except OSError as e:
            self.log.warning("checks.json non écrit : %s", e)

    def suivre_demande_spoiler(self) -> bool:
        """Demande du lanceur (`spoiler_demande.json`) : spoiler log `.txt` de toutes les locations du slot (contenu
        des LocationScouts), puis réponse (`spoiler_reponse.json`). True si une demande a été traitée."""
        dossier = self.stockage.dossier
        if not (dossier / ck.NOM_DEMANDE).is_file():
            return False
        d = ck.lire_json(dossier / ck.NOM_DEMANDE) or {}
        nonce = str(d.get("nonce", ""))[:64]
        r = self.reseau
        toutes = (r.locations_manquantes | r.locations_verifiees) if r is not None else set()
        if r is None or not self._connexion_prete or not self._scout_fait or not toutes <= set(self._scout):
            ck.repondre(dossier, nonce, False, erreur="pas_de_donnees")
            self.log.info("Spoiler log demandé : contenu des locations pas encore reçu du serveur")
            return True
        langue = d.get("langue") if d.get("langue") in ("fr", "en") else "fr"
        texte = ck.texte_spoiler(
            langue=langue, graine=str(r.room_info.get("seed_name", "")), joueur=r.nom_joueur(r.slot), slot=r.slot,
            options=ck.options_de_slot_data(r.slot_data), locations=toutes,
            faites=r.locations_verifiees | (r.locations_en_attente & toutes),
            contenus={l: self._contenu_scout(o) for l, o in self._scout.items()},
            noms_serveur={l: r.nom_location(l, r.slot) for l in toutes})
        f = ck.ecrire_spoiler(dossier, texte)
        ck.repondre(dossier, nonce, True, f)
        self.log.info("Spoiler log écrit à la demande du lanceur (%d locations)", len(toutes))
        return True

    # ------------------------------------------------------------------------------ DeathLink (§25)
    def _maj_tag_deathlink(self) -> None:
        """Tag « DeathLink » = option du slot ET jeu attaché qui compile le DeathLink (sans jeu : on ne peut ni mourir
        ni envoyer sa mort)."""
        r, voulu = self.reseau, self.deathlink.tag
        if r is None or not self._deja_connecte or voulu == self._tag_deathlink:
            return
        self._tag_deathlink = voulu
        self.log.info("DeathLink %s", "activé (tag posé)" if voulu else "désactivé (tag retiré)")
        self._lancer(r.activer_deathlink(voulu))

    def _sur_deathlink(self, donnees: dict) -> None:
        r = self.reseau
        if r is None:
            return
        m = self.deathlink.recue(donnees, r.nom)
        if m is None:
            self.log.info("DeathLink de %s ignoré", donnees.get("source") or "?")
            return
        self.log.info("DeathLink reçu de %s (%s)", m.source, m.cause or "sans cause")
        self.reveiller()

    async def _suivre_deathlink(self, h) -> None:
        """DeathLink compilé dans le jeu (lu UNE fois par instance, seulement si l'option est active : aucune lecture de
        plus sinon) ; défaite réelle publiée dans l'en-tête (`defaites`) -> Bounce DeathLink."""
        d, r = self.deathlink, self.reseau
        if h.version < bp.VERSION_MORT or h.taille_zone < bp.OFF_MORT + bp.TAILLE_MORT:
            if d.jeu is None and d.option:
                self.log.warning("DeathLink : jeu v%d sans DeathLink (patch à mettre à jour) : option ignorée",
                                 h.version)
            d.jeu = False
        elif d.jeu is None and d.option:
            b = await self.pont.lire(bp.ZONE + bp.OFF_MORT, 0x10)
            c = bp.mort_compile(b)
            d.jeu, d.demande = bool(c), bp.lire_mort(b)["demande"]
            d.fenetre = bool(c) and bp.mort_fenetre(b)
            if not d.jeu:
                self.log.warning("DeathLink : absent de ce build du jeu (YKW2_AP_SANS_DEATHLINK) : option ignorée")
        self._maj_tag_deathlink()
        if h.version < bp.VERSION_MORT or not h.partie:
            return
        if d.defaites_vues(h.defaites, (h.adresse_p, h.ident_sauvegarde), self.sauvegarde == "liee") and r:
            cause = dl.texte_cause(r.nom, self.catalogue.langue)
            self.log.info("Défaite dans le jeu (%d depuis le lancement) : DeathLink envoyé (%s)", h.defaites, cause)
            self._lancer(r.envoyer_deathlink(cause))

    async def _ecrire_mort(self, h) -> None:
        """Mort reçue -> ApMort (identifiant de partie, puis numéro de demande EN DERNIER), sauvegarde liée seulement ;
        le jeu l'exécute au prochain moment sûr (combat : défaite forcée ; terrain : fenêtre « Vous êtes tombé...
        (DeathLink de <joueur>) » puis retour au point de reprise). Le nom du joueur à l'origine est écrit d'abord
        (ApMortFenetre.source), seulement pour un jeu qui compile la fenêtre (ces octets avaient un autre rôle avant)."""
        d = self.deathlink
        m = d.a_transmettre(bool(h.partie) and self.sauvegarde == "liee" and bool(self.ident_partie))
        if m is None:
            return
        n = d.prochaine_demande()
        async with self.pont.transaction():
            if d.fenetre and h.taille_zone >= bp.OFF_MORT_FENETRE + bp.TAILLE_MORT_FENETRE:
                await self.pont.ecrire(bp.ZONE + bp.OFF_MORT_FENETRE, bp.enc_mort_source(m.source))
            await self.pont.ecrire(bp.ZONE + bp.OFF_MORT + 8, struct.pack("<I", self.ident_partie & 0xFFFFFFFF))
            await self.pont.ecrire(bp.ZONE + bp.OFF_MORT + 4, struct.pack("<I", n))
        d.transmise()
        self.log.info("Mort liée demandée au jeu (demande %d) : %s", n, m.source)
        self._notifier(dl.texte_bandeau(m.source, self.catalogue.langue))

    # ------------------------------------------------------------------------------ fenêtres « objet obtenu » (§27)
    def _anim_compilee(self, h) -> bool:
        """Fonction 29 publiée par le jeu de cette instance (liste des verrous compilés, lue une fois par instance)."""
        if h.version < bp.VERSION_BOUTIQUES or h.taille_zone < bp.OFF_ANIM_TABLE + bp.CAP_ANIM * bp.TAILLE_ANIM:
            return False
        v = self._verrous_compiles
        return v is not None and v[0] == self._instance and bool((v[1] or 0) >> bp.FONCTION_ANIM & 1)

    def _anim_possible(self, h) -> bool:
        return (self.sauvegarde == "liee" and bool(h.partie) and bool(self.ident_partie) and self.anims.travail
                and self._anim_compilee(h))

    def _anim_entree(self, loc: int) -> tuple[int, bytes, int] | None:
        """(objet montré, 0 = la vitrine ; nom de la vitrine ; quantité) de la location, ou None si son contenu n'est
        pas encore connu (LocationScouts en cours)."""
        c = self._contenu(loc)
        if c is None:
            return None
        if c.hachage == self.catalogue.vitrine or not c.hachage:
            return 0, bp.nom_vitrine(c.texte) if c.texte else b"", 1
        return c.hachage, b"", 1

    async def _suivre_anims(self, h) -> None:
        """En-tête de la file des fenêtres (0x40 octets, un paquet) : seulement pendant qu'il y a du travail (voir
        `EtatAnims.besoin_lecture`)."""
        a = self.anims
        if not self._anim_possible(h):
            return
        a.tour()
        if not a.besoin_lecture():
            return
        entete = bp.dec_anim_entete(await self.pont.lire(bp.ZONE + bp.OFF_ANIM, 0x40))
        faites = a.lue(entete)
        if faites:
            self.log.info("Fenêtre(s) « objet obtenu » traitée(s) par le jeu : %s (montrées %d, écartées %d)", faites,
                          a.montrees, a.ecartees)

    async def _deposer_anims(self, h) -> None:
        """Entrées de la file des fenêtres (dans l'arrêt de fin de tour), puis `ecrites` EN DERNIER."""
        a = self.anims
        if not self._anim_possible(h) or not a.attente:
            return
        liste = a.a_ecrire(self._anim_entree, self.ident_partie)
        if not liste:
            return
        async with self.pont.transaction():
            for n, _loc, octets in liste:
                await self.pont.ecrire(bp.adr_anim(n), octets)
            await self.pont.ecrire(bp.ZONE + bp.OFF_ANIM, struct.pack("<I", liste[-1][0] & 0xFFFFFFFF))
        a.ecrites_faites(liste)
        self.log.info("Fenêtre(s) « objet obtenu » écrite(s) dans le jeu : %s", [loc for _n, loc, _o in liste])

    # ------------------------------------------------------------------------------ notifications
    def _notifier(self, texte: str, max_car: int = NOTIF_MAX_CAR) -> None:
        self.notifications.append(texte_court(texte, max_car=max_car))

    async def _deposer_notifications(self, h) -> None:
        """Notifications en attente -> file du jeu, toutes celles qui y tiennent, dans un seul arrêt (aucun si la file du
        jeu est pleine : places comptées jeu en marche)."""
        if not h.notifications:
            self.notifications.clear()
            return
        if not self.notifications:
            return
        n = await self.boite.deposer_notifications(list(self.notifications)[:bp.CAP_NOTIFS], h)
        for _ in range(n):
            self.notifications.popleft()
            self.stats.notifications += 1
