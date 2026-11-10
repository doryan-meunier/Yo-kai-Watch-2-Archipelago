"""Tracker de Yo-kai (onglet « Yo-kai » du lanceur, étape R5 de `docs/systemes/archipelago_rando_yokai.md`), SANS
affichage : lecture des fichiers locaux, « où trouver ce Yo-kai » sous le mélange réellement appliqué, filtres,
recherche inverse par région / carte. La vue tkinter est dans `vue_yokai.py`. Bibliothèque standard seulement.

Données (toutes dans le dossier de données du client, `%APPDATA%/ykw2-ap/`, jamais versionnées ni distribuées) :
- `yokai_local.json` : base des rencontres générée CHEZ LE JOUEUR depuis SA ROM (`installation/rencontres.py`) :
  rencontres (combattants, niveaux, lieux : carte, méthode, condition ; format 2 : condition décodée), espèces (base,
  rang, tribu, n° du Médaillium au format 2, noms dans la langue du joueur) ;
- `rando_yokai.json` : écrit par le client (`client/rando_yokai.py`) : état, mode, graine, σ, ce que le jeu publie ;
- `medaillium.json` : Médaillium de la sauvegarde liée (client) : bits « vu » (P+0x40C) et, au format 2, « ami »
  (P+0x44C | P+0x604), indexés par le n° du Médaillium de l'espèce (`CHARA_PARAM_INFO` v[49]) ;
- `progression.json` : progression de la sauvegarde liée (client) : phase d'histoire, rang de montre réel, après-jeu,
  pour le filtre « Accessibles maintenant » (conditions des lieux évaluées comme le jeu, `evaluer`) ;
- `noms_local.json` : noms des cartes et des tribus, n° du Médaillium (`noms_locaux.py`, depuis la ROM du joueur ;
  utilisé pour une base au format 1, dont le champ `medaille` est faux) ;
- `rando_boss.json` : écrit par le client (`client/rando_boss.py`) : pour chaque boss, le boss qui prend sa place (vue
  « Boss » : « Boss : X — remplacé par Y », masqué jusqu'à la rencontre, c.-à-d. le bit « vu » du Médaillium d'une
  espèce du remplaçant, ou jusqu'au clic) ;
- `invites.json` : écrit par le client (`client/synchro.py`) : invités de l'Auberge des voyageurs de la graine pour la
  sauvegarde liée (`archipelago_invites.md` §14 et §15) : état « attente » (requêtes restantes, ou invitation pas
  reçue), « file » (invité, attend qu'une chambre se libère), « present » (pièce : Suite, réservée à Pandanoko, ou
  chambre 101..109 pour les invités à invitation, neuf à la fois)
  ou « ami » : un lieu « invité » de plus sur la ligne du Yo-kai (carte t103i69) ;
- `bingo.json` : écrit par le client (`client/bingo.py`, V3, lot B1) pour une graine à Bingo-kai aléatoire : ce que
  chaque pièce de chaque machine ordinaire du Bingo-kai peut donner dans CETTE partie : un lieu « Crank-a-kai » de plus
  sur la ligne de chaque Yo-kai (carte de la machine : t102g00 présent, t202g00 passé ; pièce et taux).
Aucun nom de Yo-kai n'est dans le code : ils viennent de la base locale. Les régions sont saisies à la main (préfixe
de l'identifiant de carte, d'après l'ancien mod de l'humain ; noms de `apworld/.../regions.json`) : les noms fins des
lieux ne sont pas des textes du jeu (images, `archipelago_rando_yokai.md` §1.4).
"""
from __future__ import annotations

import json
import zlib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

NOM_BASE = "yokai_local.json"
NOM_MELANGE = "rando_yokai.json"
NOM_MEDAILLIUM = "medaillium.json"
NOM_NOMS = "noms_local.json"                 # noms des cartes et des tribus (lanceur/noms_locaux.py)
NOM_PROGRESSION = "progression.json"         # progression de la sauvegarde liée (client)
NOM_BOSS = "rando_boss.json"                 # mélange des boss (client)
NOM_INVITES = "invites.json"                 # invités de l'Auberge des voyageurs (client, sauvegarde liée)
NOM_BINGO = "bingo.json"                     # V3, lot B1 : Bingo-kai aléatoire (client, ce que donne chaque pièce)
FICHIERS = (NOM_BASE, NOM_MELANGE, NOM_MEDAILLIUM, NOM_NOMS, NOM_PROGRESSION, NOM_BOSS, NOM_INVITES, NOM_BINGO)
# checks.json (client) : options de la graine, d'où le lanceur reconstruit le plan (`checks.voies_graine`) pour les
# Yo-kai que la GRAINE fait venir sans rencontre (invités à invitation pas encore reçus, pièces spéciales) ; relu
# aussi quand il change (objets reçus : accès d'une voie)
NOM_CHECKS = "checks.json"
FICHIERS_SIGNATURE = FICHIERS + (NOM_CHECKS,)
FORMATS_BASE = (1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)  # 1 : `medaille` faux (n° lu dans noms_local.json), lieux sans condition décodée ;
                                       # 3 : espèces non recrutables en combat fixées (mélange du client) ;
                                       # 4 : scripts de combat (mélange des boss)
                                       # 5 : espèces exigées et leurs sources (anti-softlock)
                                       # 6 : périmètre avant l'après-jeu, Yo-kai d'évènement
                                       # 7 : emplacements précis (mélange par rencontre)
                                       # 10 : taux d'amitié (facilité d'amitié de chaque Yo-kai)
                                       # 11 : lieux « portail » (salles des portails mystères, §16)
                                       # 12 : positions monde des lieux (Yo-kai épinglé sur la carte, §18)
                                       # 13 : moments des lieux (jour / nuit, pluie, version du jeu, §19)
                                       # 17 : périmètre « partout » du mélange version 5 (`melange5`)
                                       # 19 : idem pour la version 6, spots compris (`melange6`) ; 18 : branche
                                       #      ap/v3-boss-force (non fusionnée)
FORMAT_BOSS = 1                        # rando_boss.json
FORMAT_MELANGE = 1
FORMATS_MEDAILLIUM = (1, 2)            # 1 : « vu » seulement ; 2 : « vu » et « ami »
FORMAT_PROGRESSION = 1
FORMAT_INVITES = 1
RANGS = "EDCBAS"                       # rang 0..5 (sys_rank_00..05 : E..S, FUN_0049f618)
TRIBUS_NOMMEES = range(1, 9)           # tribus 1..8 (sys_tribe_00..07) ; 0 et 9 : aucun nom dans le jeu
METHODES = ("loupe", "errant", "portail")
# « portail » (base au format 11, archipelago_rando_yokai.md §16) : errant d'un fichier `<carte>_enc_pos_gate`, visible
# seulement quand la carte sert de salle d'un portail mystère (salle tirée au sort) : jamais « accessible maintenant »
# de façon sûre (au mieux incertain « ? »), et listé après les lieux normaux.
PORTAIL = "portail"
# « invite » (invites.json, docs/systemes/archipelago_invites.md §14 et §15) : Yo-kai qui vient à l'Auberge des voyageurs
# (la Suite t103i69 pour Pandanoko seul, les chambres 101 à 109, t103i60..68, pour les autres : neuf à la fois, règle
# calculée par le jeu et refaite par le client) quand son déclencheur est rempli (toutes les requêtes
# pour Pandanoko, l'objet « Invitation : <nom> » pour les 30 autres) ; combattu au niveau du plus haut Yo-kai de
# l'équipe, ami au taux du jeu (autant de combats qu'il faut). Pas une méthode du filtre (METHODES) : un lieu de plus
# sur la ligne du Yo-kai. États : « attente » (pas encore invité), « file » (invité, attend qu'une chambre se libère),
# « present » (dans la pièce `piece` : 0 la Suite, 1..9 les chambres), « ami » (il ne revient plus).
INVITE = "invite"
CARTE_INVITES = "t103i69"
CARTES_INVITES = ("t103i69",) + tuple("t103i6%d" % i for i in range(9))   # carte de chaque pièce (0 : la Suite)
ETATS_INVITE = ("attente", "file", "present", "ami")
# « crank » (bingo.json, V3, lot B1) : lot d'une pièce du Bingo-kai (Crank-a-kai) dans une graine à Bingo-kai aléatoire,
# sur la carte de la machine. Pas une méthode du filtre (METHODES) : un lieu de plus sur la ligne du Yo-kai.
CRANK = "crank"
CARTES_CRANK = {"present": "t102g00", "passe": "t202g00"}
FORMAT_BINGO = 1
# « fusion » (V3, lot 20 / 21, pieces.py) : fusion d'un Yo-kai régional avec son objet de fusion, chez le fusionneur du
# Coteau fleuri (`t103i31`, après la requête 4). Pas une méthode du filtre : un lieu de plus sur la ligne du Yo-kai.
FUSION = "fusion"
CARTE_FUSION = "t103i31"
# Voies de la GRAINE (plan reconstruit depuis checks.json, `checks.voies_graine`) : un Yo-kai qu'aucune rencontre de la
# base ne contient (Avallée, n° 380 : pièce régionale) n'a pas de ligne dans la base ; la voie apporte ses noms (saisis
# à la main dans l'APWorld, amis_criminels.py / pieces.py) et la ligne est créée (clé « m<n° du Médaillium> »).
SORTES_VOIE = ("invite", "piece", "fusion")


@dataclass(frozen=True)
class VoieGraine:
    """Voie d'un Yo-kai donnée par la graine (pas par une rencontre). `sorte` : « invite » (invité de l'Auberge à
    déclencheur `declencheur`, « objet » ou « requetes »), « piece » (pièce spéciale du pool : `objet_noms` = nom de la
    pièce, `exige` exemplaires, machine `machine`), « fusion » (Yo-kai régional + `objet_noms`) ; `acces` : objets
    exigés reçus (None : inconnu)."""
    medaille: int
    noms: dict                          # {langue de la base (fr, engb) : nom du Yo-kai}
    sorte: str
    declencheur: str = ""
    objet_noms: dict | None = None      # {fr, en} : pièce ou objet de fusion
    exige: int | None = None            # pièce : exemplaires qui le donnent à coup sûr
    machine: str = "present"
    acces: bool | None = None
# Catégories d'aliment (base au format 11 : `aliment` des espèces = CHARA_BASE_YOKAI_INFO v[17] = champ 3 des objets
# nourriture d'`item_config`) dont le libellé est saisi à la main dans `textes.py` (« aliment_<n> ») ; toute autre
# valeur : rien n'est affiché.
ALIMENTS = frozenset((1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19))
# Nature des décors de loupe (base au format 11 : types de point d'un lieu de loupe = crc32 du nom du décor
# `data/map/<décor>`), saisie à la main d'après le contenu du décor (t200 / t300 : mêmes décors, version du passé, sauf
# `t300w131`, un autre décor que la voiture de `t100w131` / `t200w131`) ;
# libellés « decor_<nature> » de `textes.py`. Décor absent d'ici (nature non établie) : « loupe » sans type.
_DECORS = {"arbre": ("t100w011", "t200w011", "t300w011"), "buisson": ("t100w021", "t200w021", "t300w021"),
           "bambous": ("t100w031", "t200w031"), "fleurs": ("t100w041",),
           "riviere": ("t100w061", "t200w061", "t300w061"), "plage": ("t100w081",), "poubelles": ("t100w091",),
           "herbes": ("t100w191", "t200w191"), "etang": ("t100w201", "t200w201"),
           "distributeur": ("t100w141",), "voiture": ("t100w131", "t200w131"), "porte": ("t100w171",),
           "poteau": ("t100w121", "t200w121"), "plancher": ("t100w151", "t200w151", "t300w151"),
           # natures SUPPOSÉES d'après les textures seules (demande de l'humain : afficher la supposition), à confirmer
           "cartons": ("t100w101",), "steles": ("t100w161", "t200w161"),
           "ville": ("t102w011", "t107w011", "t131w011"), "canal": ("t100w071",), "charrette": ("t300w131",),
           "nenuphars": ("t100w051",)}
DECORS_LOUPE = {zlib.crc32(d.encode()): nature for nature, ds in _DECORS.items() for d in ds}
ORDRE_DECORS = tuple(_DECORS)

# Région d'une carte = préfixe de 4 caractères de son identifiant (saisi à la main : table de l'ancien mod de l'humain,
# noms des régions de l'APWorld). Ordre = ordre d'affichage.
REGIONS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("les_hauts_de_granval", ("t101",), "Les Hauts de Granval", "Uptown Springdale"),
    ("quartier_des_boutiques", ("t105",), "Quartier des boutiques", "Shopper's Row"),
    ("centre_ville_de_granval", ("t104",), "Centre-ville de Granval", "Downtown Springdale"),
    ("coteau_fleuri", ("t103",), "Coteau fleuri", "Blossom Heights"),
    ("la_corniche", ("t106",), "La Corniche", "Breezy Hills"),
    ("tour_excellence", ("t107",), "Tour Excellence", "Excellent Tower"),
    ("granval", ("t100",), "Granval", "Springdale"),
    ("mont_sylvestre", ("t102", "t001", "t002"), "Mont Sylvestre", "Mt. Wildwood"),
    ("ourcival", ("t131", "t132"), "Ourcival", "Harrisville"),
    ("san_fantastico", ("t121",), "San Fantastico", "San Fantastico"),
    ("plaines_plinpot", ("t200",), "Plaines Plinpot", "Flatpot Plains"),
    ("vieux_granval", ("t201", "t202", "t206"), "Vieux Granval", "Old Springdale"),
    ("vieil_ourcival", ("t231", "t232"), "Vieil Ourcival", "Old Harrisville"),
    ("limbes_eternelles", ("t301", "t302", "t303"), "Limbes éternelles", "Infinite Inferno"),
)
AUTRE_REGION = "autre"
_REGION_DE_PREFIXE = {p: cle for cle, prefixes, _fr, _en in REGIONS for p in prefixes}
_NOMS_REGIONS = {cle: (fr, en) for cle, _p, fr, en in REGIONS}
ORDRE_REGIONS = [cle for cle, *_ in REGIONS] + [AUTRE_REGION]

# Fonctions de condition d'un lieu (texte de la base locale) -> clé de texte de la condition (textes.py « cond_* »).
CONDITIONS = {"GetWatchRank": "rang", "GameClear": "apres_jeu", "GetTimeNow": "heure", "GetPhase": "histoire",
              "GetGlobalByteFlag": "histoire", "GetGlobalBitFlag": "histoire", "GetQuestPhase": "quete",
              "IsHaveItem": "objet"}

# Catégories des rencontres non sauvages (base locale, champ « cat » : noms d'entrées de .cfg.bin joints par « + »)
# -> clé de texte (textes.py « cat_* »). Inconnue : « autre ».
CATEGORIES = {"DATA_ITEM": "histoire", "WANTED_INFO": "criminel", "TRAIN_EVENT_DATA": "train", "YS_YOKAI": "spot",
              "ITABLE_DATA_MORE": "coffre", "GYM_MISSION_BATTLE_ENC_" "INFO_DATA": "gymnase",
              "OP_WATCH_POINT": "point", "script_de_combat": "boss", "script_ou_aucune": "script",
              "BTL_RULE_INFO_RULE_DATA": "histoire", "FLAG_INFO": "histoire"}


def region_de(carte: str) -> str:
    return _REGION_DE_PREFIXE.get((carte or "")[:4], AUTRE_REGION)


def nom_region(cle: str, langue: str) -> str:
    fr, en = _NOMS_REGIONS.get(cle, ("Autres lieux", "Other places"))
    return en if langue == "en" else fr


_REGIONS_APWORLD: dict | None = None


def nom_zone(cle: str, langue: str) -> str:
    """Nom d'une zone des Yo-kai demandés (V3, lots M2b : clé de région de l'APWorld, `donnees/regions.json` du
    paquet) ; la clé elle-même si le fichier manque."""
    global _REGIONS_APWORLD
    if _REGIONS_APWORLD is None:
        p = Path(__file__).resolve().parents[1] / "apworld" / "yokaiwatch2" / "donnees" / "regions.json"
        try:
            _REGIONS_APWORLD = {r["cle"]: r for r in json.loads(p.read_text(encoding="utf-8"))["regions"]}
        except (OSError, ValueError, KeyError, TypeError):
            _REGIONS_APWORLD = {}
    r = _REGIONS_APWORLD.get(cle) or {}
    return r.get("nom_en" if langue == "en" else "nom_fr") or cle


def langue_base(langue: str) -> str:
    """Langue des noms de la base locale (`rencontres.LANGUES_DEFAUT` : fr, engb) pour la langue du lanceur."""
    return "engb" if langue == "en" else "fr"


def replier(texte: str) -> str:
    """Forme de recherche : minuscules, sans accents ni ponctuation superflue (« Élé-ment » -> « ele ment »)."""
    d = unicodedata.normalize("NFKD", texte or "")
    s = "".join(c for c in d if not unicodedata.combining(c)).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def categorie(cat: str) -> str:
    # (le flag « combat gagné » qui porte le nom d'une rencontre, FLAG_INFO, ne décide la catégorie que s'il est seul :
    # une rencontre de spot est « FLAG_INFO+YS_YOKAI »)
    for partie in sorted((cat or "").split("+"), key=lambda x: x == "FLAG_INFO"):
        if partie in CATEGORIES:
            return CATEGORIES[partie]
        if partie.startswith("GYM_"):
            return "revanche"
    return "autre"


# V3, lot M1 : pourquoi un lieu garde son Yo-kai d'origine sous un mélange par rencontre (clé de texte « inch_* »).
# Raisons d'exclusion d'une rencontre (champ `exclusion` de la base, ou `melange5` du périmètre en version 5) :
_INCH_EXCLUSION = {"evenement": "evenement", "sans_amitie": "sans_amitie", "jamais_version": "jamais",
                   "hors_partie": "hors_partie", "apres_jeu": "apres_jeu", "script": "combat_requete",
                   "quete": "combat_requete", "script_de_combat": "combat_requete", "condition": "condition"}


def raison_exigence(categories) -> str:
    """Raison (clé « inch_* ») d'un Yo-kai gardé parce que le jeu l'exige (catégories de `exigees` / `fixees`)."""
    cats = set(categories or ())
    if cats & {"quete_posseder", "quete_vaincre"}:
        return "requete"
    for cle, raison in (("tablo", "tablo"), ("sceau_legendaire", "sceau")):
        if cle in cats:
            return raison
    if cats & {"source_evolution", "source_fusion"}:
        return "source"
    if cats & {"condition:InPartyMember", "condition:GetPartyInNum", "condition:GetGlobalCharaCompFlagAnyOneCRC"}:
        return "histoire"
    if any(c.startswith("condition:YS_") for c in cats):
        return "spot"
    if cats & {"declencheur", "quete_position", "regle_combat"}:
        return "lieu_requete"
    if any(c.startswith("script") for c in cats):
        return "script"
    return "exige"


def raison_inchangee(em: "EtatMelange", base: dict, exigences: dict, e: dict, c: list) -> str | None:
    """Raison pour laquelle le combattant `c` de la rencontre sauvage `e` garde son espèce d'origine sous le mélange
    par rencontre `em` (None : pas de mélange par rencontre, ou combattant changé). `exigences` : espèce -> catégories
    (`exigees` | `fixees` de la base)."""
    if not em.affectation or em.en_jeu(e, c) != int(c[1]):
        return None
    h, r = e.get("h"), (int(e.get("f", -1)), int(c[0]))
    if h in em.hors_w:
        return "jamais"
    if not (e.get("wp") or h in em.ajout_w):
        raisons = e.get("exclusion") or ()
        bloc = base.get("melange6" if em.version >= 6 else "melange5") if em.version >= 5 else None
        per = ((bloc or {}).get("perimetres") or {}).get(em.perimetre)
        if isinstance(per, dict):
            raisons = (per.get("exclusion") or {}).get(str(h), raisons)
        for x in _INCH_EXCLUSION:                    # dans l'ordre de la table : la raison la plus précise d'abord
            if x in raisons:
                return _INCH_EXCLUSION[x]
        return "technique"
    if (c[6] if len(c) > 6 else 1) and r not in em.liberes or r in em.figes:
        return "partage"
    g = em.gardes.get(r)
    if g in ("tout", "emplacement"):
        cats = set(exigences.get(int(c[1])) or ())
        if em.version >= 6:                           # version 6 : les dialogues des spots ne gardent plus rien
            cats = {x for x in cats if not x.startswith("condition:YS_")} or cats
        return raison_exigence(cats)
    if g in ("loupe", "hors_reservoir"):
        return g
    return "hasard"


def conditions(texte: str) -> tuple[str, ...]:
    """Texte de condition de la base (« GetWatchRank GetTimeNow ») -> clés triées, sans doublon ; inconnue : « special »."""
    out = []
    for mot in (texte or "").split():
        k = CONDITIONS.get(mot, "special")
        if k not in out:
            out.append(k)
    return tuple(out)


# ------------------------------------------------------------------------------------------------ lecture
def lire_json(p: Path) -> dict | None:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def signature(dossier: Path) -> tuple:
    """(taille, date) des fichiers locaux : le tracker se recharge quand elle change."""
    out = []
    for n in FICHIERS_SIGNATURE:
        try:
            st = (Path(dossier) / n).stat()
            out.append((st.st_size, st.st_mtime_ns))
        except OSError:
            out.append(None)
    return tuple(out)


def _hachage(x) -> int | None:
    try:
        return int(x, 0) if isinstance(x, str) else int(x)
    except (TypeError, ValueError):
        return None


@dataclass
class EtatMelange:
    """Ce que le tracker affiche : `statut` (clé de texte « melange_* ») et le mélange utilisé (σ vide : origine)."""
    statut: str                        # absent | aucun | refuse | calcul | sans_support | applique | pas_applique
    niveau: str                        # ok | attention | erreur | neutre (pastille)
    sigma: dict[int, int] = field(default_factory=dict)
    mode: str = ""
    graine: int | None = None
    message: str = ""
    ident_partie: int | None = None
    nb_d: int = 0
    # mélange par rencontre (archipelago_rando_yokai.md §11) : (index du fichier, index d'ENCOUNT_CHARA) -> espèce en jeu
    affectation: dict[tuple[int, int], int] = field(default_factory=dict)
    # version 2 du mélange (§20, champs `hors_w` / `figes` de rando_yokai.json ; vides pour la version 1) : rencontres
    # retirées de W / W' (elles ne sortent jamais dans cette version du jeu) et combattants (fichier, index) partagés
    # avec elles : le jeu ne les réécrit pas
    hors_w: frozenset = frozenset()
    figes: frozenset = frozenset()
    # version 5 (« partout », archipelago_v3_melange_partout.md ; vides avant) : rencontres ajoutées au W' (hors des
    # rencontres sauvages d'origine : coffres, trains, gymnase…) -> catégorie ; combattants libérés (drapeau
    # « partagé » brut levé, modifiables en version 5) ; périmètre ; version du mélange
    ajout_w: dict = field(default_factory=dict)
    liberes: frozenset = frozenset()
    perimetre: str = ""
    version: int = 1
    # V3, lot M1 : combattants (fichier, index) gardés par le mélange par rencontre -> raison (tout, emplacement, loupe,
    # hors_reservoir) ; statistiques du client (combattants changés…) ; ce que le jeu publie
    gardes: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    jeu: dict = field(default_factory=dict)
    # V3, lots M2b (version 7) : Yo-kai demandés placés dans leur zone : espèce -> (n° du Médaillium, zone, [cartes de
    # chacune de ses unités])
    zones: dict = field(default_factory=dict)

    @property
    def melange(self) -> bool:
        return bool(self.sigma or self.affectation)

    def en_jeu(self, e: dict, c: list) -> int:
        """Espèce en jeu du combattant `c` de la rencontre sauvage `e` (même règle que le jeu : combattant non partagé
        d'une rencontre de W ; client/rando_yokai.Melange.en_jeu)."""
        orig = int(c[1])
        if (self.hors_w or self.figes) and (e.get("h") in self.hors_w
                                            or (int(e.get("f", -1)), int(c[0])) in self.figes):
            return orig
        if self.affectation:                           # mélange par rencontre : W' (`wp`) et partage relatif à W'
            if not (e.get("wp") or e.get("h") in self.ajout_w) or len(c) < 7:
                return orig
            if c[6] and (int(e.get("f", -1)), int(c[0])) not in self.liberes:
                return orig
            return self.affectation.get((int(e.get("f", -1)), int(c[0])), orig)
        if c[3] or not e.get("w"):
            return orig
        return self.sigma.get(orig, orig)


def etat_melange(d: dict | None) -> EtatMelange:
    """Interprète `rando_yokai.json` (client/rando_yokai.ecrire_fichier_local, synchro._suivre_rando). Le tracker montre
    ce que le jeu utilise : lieux d'origine si le fichier manque, si la partie n'a pas de mélange, si le client l'a
    refusé ou si le jeu installé n'a pas le randomizer ; le mélange s'il est calculé (appliqué, ou pas encore : partie
    non liée, jeu fermé avant l'écriture ; mention « attention »)."""
    if not d or d.get("format") != FORMAT_MELANGE:
        return EtatMelange("absent", "neutre")
    jeu = d.get("jeu") if isinstance(d.get("jeu"), dict) else {}
    ident = d.get("ident_partie")
    msg = str(jeu.get("message") or "")
    etat = d.get("etat")
    if etat == "aucun":
        return EtatMelange("aucun", "neutre", message=msg, ident_partie=ident, jeu=jeu)
    if etat == "refuse":
        return EtatMelange("refuse", "erreur", message=msg, ident_partie=ident, jeu=jeu)
    sigma = {}
    for a, b in (d.get("sigma") or {}).items():
        ha, hb = _hachage(a), _hachage(b)
        if ha is not None and hb is not None:
            sigma[ha] = hb
    affectation = {}
    for x in d.get("affectation") or ():
        if isinstance(x, list) and len(x) == 3 and isinstance(x[0], int) and isinstance(x[1], int):
            hx = _hachage(x[2])
            if hx is not None:
                affectation[(x[0], x[1])] = hx
    if etat != "actif" or not (sigma or affectation):
        return EtatMelange("calcul", "attention", message=msg, ident_partie=ident, jeu=jeu)
    hors_w = frozenset(x for x in d.get("hors_w") or () if isinstance(x, int))
    figes = frozenset((x[0], x[1]) for x in d.get("figes") or ()
                      if isinstance(x, list) and len(x) == 2 and all(isinstance(v, int) for v in x))
    liberes = frozenset((x[0], x[1]) for x in d.get("liberes") or ()
                        if isinstance(x, list) and len(x) == 2 and all(isinstance(v, int) for v in x))
    ajout_w = {x[0]: str(x[1]) for x in d.get("ajout_w") or ()
               if isinstance(x, list) and len(x) == 2 and isinstance(x[0], int)}
    gardes = {(x[0], x[1]): str(x[2]) for x in d.get("gardes") or ()
              if isinstance(x, list) and len(x) == 3 and isinstance(x[0], int) and isinstance(x[1], int)}
    version = d.get("melange") if isinstance(d.get("melange"), int) else 1
    zones = {}
    for x in d.get("zones") or ():
        hx = _hachage(x[0]) if isinstance(x, list) and len(x) == 4 else None
        if hx is not None and isinstance(x[1], int) and isinstance(x[2], str) and isinstance(x[3], list):
            zones[hx] = (x[1], x[2], [list(c) for c in x[3] if isinstance(c, list)])
    commun = dict(mode=str(d.get("mode") or ""), graine=d.get("graine"), message=msg, ident_partie=ident, zones=zones,
                  nb_d=int(d.get("nb_d") or 0), affectation=affectation, hors_w=hors_w, figes=figes,
                  ajout_w=ajout_w, liberes=liberes, perimetre=str(d.get("perimetre") or ""), version=version,
                  gardes=gardes, stats=d.get("stats") if isinstance(d.get("stats"), dict) else {}, jeu=jeu)
    if jeu.get("support") is False:
        return EtatMelange("sans_support", "erreur", **commun)
    if jeu.get("valide") and jeu.get("valide") == d.get("generation"):
        return EtatMelange("applique", "ok", sigma, **commun)
    return EtatMelange("pas_applique", "attention", sigma, **commun)


TAILLE_VU = 0x40                        # P+0x40C..0x44B : 512 bits « vu » (GetGlobalCharaMetFlag, FUN_0041550C)


def _meme_partie(d: dict, ident_partie: int | None) -> bool:
    return ident_partie is None or d.get("ident_partie") in (None, ident_partie)


def lire_bingo(d: dict | None, ident_partie: int | None) -> list[tuple[str, dict, list]]:
    """V3, lot B1 : lignes de `bingo.json` (client) pour la partie du mélange seulement, pièces que le mélange touche :
    [(machine, {langue : nom de la pièce}, [{param, medaille, poids, total, change}])] ; [] si absent, d'un autre
    format ou d'une autre partie, ou si le mélange n'est pas prêt. Les listes « fr » et « en » du fichier vont par
    paires (mêmes lignes, même ordre)."""
    if not d or d.get("format") != FORMAT_BINGO or not _meme_partie(d, ident_partie) or d.get("statut") != "pret":
        return []
    pieces = d.get("pieces") if isinstance(d.get("pieces"), dict) else {}
    fr, en = pieces.get("fr"), pieces.get("en")
    if not isinstance(fr, list):
        return []
    en = en if isinstance(en, list) and len(en) == len(fr) else [None] * len(fr)
    out = []
    for x, xe in zip(fr, en):
        if isinstance(x, dict) and x.get("machine") in CARTES_CRANK and isinstance(x.get("yokai"), list) \
                and not x.get("dirigee"):
            noms = {"fr": str(x.get("nom") or "")}
            if isinstance(xe, dict):
                noms["en"] = str(xe.get("nom") or "")
            out.append((x["machine"], noms, x["yokai"]))
    return out


def bits_medaillium(d: dict | None, ident_partie: int | None, zone: str = "vu") -> bytes | None:
    """Bits du Médaillium de `medaillium.json` : `zone` « vu » (P+0x40C) ou « ami » (P+0x44C | P+0x604, format 2
    seulement), 0x40 octets, bit n = n° du Médaillium n ; None si absent, d'un autre format ou d'une autre partie que
    le mélange."""
    if not d or d.get("format") not in FORMATS_MEDAILLIUM or not _meme_partie(d, ident_partie):
        return None
    if d.get("p_offset", 0x40C) != 0x40C:
        return None
    try:
        if d["format"] >= 2:
            b = bytes.fromhex(str(d.get(zone, "")))
            return b if len(b) == TAILLE_VU else None
        return (bytes.fromhex(str(d.get("octets", "")))[:TAILLE_VU] or None) if zone == "vu" else None
    except ValueError:
        return None


# ------------------------------------------------------------------------------------------------ progression
@dataclass
class Progression:
    """Progression de la sauvegarde liée (`progression.json`, client) : valeurs des fonctions de condition du jeu.
    None : inconnue (fichier absent, autre partie, champ illisible)."""
    phase: int | None = None           # GetPhase : chapitre × 10000 + pas (FUN_00646A68)
    chapitre: int | None = None
    pas: int | None = None
    rang: int | None = None            # GetWatchRank : rang de montre réel, 0 = E … 5 = S
    apres_jeu: bool | None = None      # GameClear : flag « partie terminée »
    horodatage: float = 0.0

    @property
    def connue(self) -> bool:
        return self.phase is not None or self.rang is not None or self.apres_jeu is not None


def lire_invites(d: dict | None, ident_partie: int | None) -> list[dict]:
    """Invités de l'Auberge des voyageurs de `invites.json` (client), pour la partie du mélange seulement :
    [{"medaille", "etat" (ETATS_INVITE), "restantes", "declencheur", "piece" (présent : 0..9), "rang" (file : 1..),
    "arrivee" (graine à ordre de réception : rang d'arrivée de l'invitation, 1 = la première ; None sinon)}] ;
    [] si le fichier manque ou vient d'une autre partie."""
    if not d or d.get("format") != FORMAT_INVITES or not _meme_partie(d, ident_partie) \
            or not isinstance(d.get("invites"), list):
        return []
    out = []
    for x in d["invites"]:
        if isinstance(x, dict) and isinstance(x.get("medaille"), int) and x.get("etat") in ETATS_INVITE:
            r, pc, rg = x.get("restantes"), x.get("piece"), x.get("rang")

            def entier(v, maxi):
                return v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= maxi else None
            out.append({"medaille": x["medaille"], "etat": x["etat"], "restantes": entier(r, 10 ** 6),
                        "declencheur": x.get("declencheur") if isinstance(x.get("declencheur"), str) else "",
                        "piece": entier(pc, len(CARTES_INVITES) - 1) if x["etat"] == "present" else None,
                        "rang": entier(rg, 10 ** 4) if x["etat"] == "file" else None,
                        "arrivee": entier(x.get("arrivee"), 10 ** 4) or None})
    return out


def lire_progression(d: dict | None, ident_partie: int | None) -> Progression | None:
    if not d or d.get("format") != FORMAT_PROGRESSION or not _meme_partie(d, ident_partie):
        return None

    def entier(k, hi=None):
        v = d.get(k)
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 and (hi is None or v <= hi) else None
    ap = d.get("apres_jeu")
    p = Progression(entier("phase"), entier("chapitre"), entier("pas_scenario"), entier("rang_montre", 5),
                    ap if isinstance(ap, bool) else None, float(d.get("horodatage") or 0.0))
    return p if p.connue else None


class _Heure:
    """Valeur de GetTimeNow : l'heure du jeu n'est pas suivie ; une comparaison qui la cite est supposée vraie et le
    lieu est signalé « selon l'heure »."""


# Moments où un lieu donne son Yo-kai (base au format 13, `archipelago_rando_yokai.md` §19) : masque de 4 bits, mêmes
# valeurs que `installation/rencontres.py`. Jour = 6 h à 18 h, nuit = 18 h à 6 h ; pluie = pluie ou tempête.
JOUR_SEC, JOUR_PLUIE, NUIT_SEC, NUIT_PLUIE = 1, 2, 4, 8
JOUR, NUIT = JOUR_SEC | JOUR_PLUIE, NUIT_SEC | NUIT_PLUIE
SEC, PLUIE = JOUR_SEC | NUIT_SEC, JOUR_PLUIE | NUIT_PLUIE
TOUJOURS = JOUR | NUIT
# Valeurs de GetTimeNow [C : `FUN_005E2E24(heure)`] : 0 = 6 h à 8 h, 1 = 8 h à 16 h, 2 = 16 h à 18 h, 3 = 18 h à 6 h
# (les conditions du jeu qui testent 4 ou 5 ne sont jamais vraies par ces valeurs-là).
CRENEAUX_JOUR, CRENEAU_NUIT = (0, 1, 2), 3


def nom_moment(masque: int) -> str | None:
    """Restriction de moment à signaler : « jour » / « nuit » (un seul des deux), None sinon (les deux, ou aucun)."""
    if masque & JOUR and not masque & NUIT:
        return "jour"
    if masque & NUIT and not masque & JOUR:
        return "nuit"
    return None


_HEURE = _Heure()
_COMPARER = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
             ">=": lambda a, b: a >= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def moment_condition(rpn) -> tuple[int, bool]:
    """(masque de moments que la condition d'un lieu PERMET, vrai si ce masque dit tout de sa dépendance à l'heure).
    La condition est évaluée à chaque valeur de GetTimeNow, le reste inconnu : un créneau est exclu seulement si elle
    y est fausse à coup sûr. Sans GetTimeNow : (TOUJOURS, False). Le second élément est faux quand la condition
    distingue des créneaux à l'intérieur de la journée, ou cite l'heure sans rien exclure (« selon l'heure » reste
    affiché)."""
    if not isinstance(rpn, list) or not any(isinstance(j, list) and j[:2] == ["f", "GetTimeNow"] for j in rpn):
        return TOUJOURS, False
    jour = [evaluer(rpn, None, h)[0] is not False for h in CRENEAUX_JOUR]
    nuit = evaluer(rpn, None, CRENEAU_NUIT)[0] is not False
    masque = (JOUR if any(jour) else 0) | (NUIT if nuit else 0)
    if not masque:                      # fausse à tous les créneaux connus : forme non comprise, rien d'affirmé
        return TOUJOURS, False
    return masque, masque != TOUJOURS and (all(jour) or not any(jour))


def evaluer(rpn, p: Progression | None, creneau: int | None = None) -> tuple[bool | None, bool]:
    """Évalue une condition décodée (jetons de `installation/rencontres.decoder_condition`) comme le jeu
    (`FUN_005B8D68`), en logique à trois valeurs : (True / False / None = inconnu, dépend de l'heure). Fonctions
    connues : GetPhase, GetWatchRank, GameClear, GetChapter (progression de la sauvegarde liée) ; GetTimeNow :
    comparaison supposée vraie (heure signalée) ; toute autre fonction (flags d'histoire, phase de requête, objet),
    tout jeton inconnu ou pile incohérente : None. « et » / « ou » : un faux (vrai) connu décide seul. `creneau` :
    valeur de GetTimeNow à supposer (`moment_condition`) au lieu de « favorable »."""
    if not rpn:
        return True, False
    if not isinstance(rpn, list):
        return None, False
    p = p or Progression()
    heure = False
    pile: list = []
    for j in rpn:
        if not isinstance(j, list) or not j:
            return None, heure
        t = j[0]
        if t == "i" and len(j) > 1 and isinstance(j[1], int):
            pile.append(j[1])
        elif t == "f" and len(j) > 1:
            nom = j[1]
            if nom == "GetPhase":
                pile.append(p.phase)
            elif nom == "GetChapter":
                pile.append(p.chapitre)
            elif nom == "GetWatchRank":
                pile.append(p.rang)
            elif nom == "GameClear":
                pile.append(None if p.apres_jeu is None else int(p.apres_jeu))
            elif nom == "GetTimeNow":
                pile.append(_HEURE if creneau is None else creneau)
            else:
                pile.append(None)
        elif t == "n":
            pile.append(None)
        elif t == "o" and len(j) > 1 and len(pile) >= 2:
            b, a = pile.pop(), pile.pop()
            op = j[1]
            if op in _COMPARER:
                if a is _HEURE or b is _HEURE:
                    heure = True
                    pile.append(True)
                elif a is None or b is None:
                    pile.append(None)
                else:
                    pile.append(bool(_COMPARER[op](int(a), int(b))))
            elif op in ("et", "ou"):
                va = None if a is None or a is _HEURE else bool(a)
                vb = None if b is None or b is _HEURE else bool(b)
                decisif = op == "ou"
                if va is decisif or vb is decisif:
                    pile.append(decisif)
                elif va is None or vb is None:
                    pile.append(None)
                else:
                    pile.append(not decisif)
            else:
                return None, heure
        else:
            return None, heure
    if len(pile) != 1 or pile[0] is None or pile[0] is _HEURE:
        return None, heure
    return bool(pile[0]), heure


def medaille_vue(octets: bytes, numero: int) -> bool:
    """Bit « vu » du Médaillium : n° `numero` (1..511, `CHARA_PARAM_INFO` v[49]), bit n de P+0x40C, poids faible
    d'abord [C : `FUN_0041550C`, sauvegardes réelles ; `archipelago_rando_yokai.md`, « Tracker »]."""
    if not isinstance(numero, int) or numero <= 0 or (numero >> 3) >= len(octets):
        return False
    return bool(octets[numero >> 3] >> (numero & 7) & 1)


# ------------------------------------------------------------------------------------------------ modèle
@dataclass
class Lieu:
    carte: str
    region: str
    methode: str                       # loupe | errant | portail (salle d'un portail mystère, §16)
    conditions: tuple[str, ...]
    niv_min: int
    niv_max: int
    a_la_place_de: str | None = None   # clé du Yo-kai d'origine de cet emplacement (None : inchangé)
    rencontres: int = 1
    condition: dict | None = None      # condition décodée (base au format 2) : {"e": jetons, "rang", "phase"…}
    acces: bool | None = None          # accessible maintenant (progression de la sauvegarde liée) ; None : inconnu « ? »
    heure: bool = False                # dépend de l'heure du jeu (non suivie : supposée favorable)
    salle_connue: bool = True          # portail : la carte est une salle de GATE_ENTER_INFO (False : non confirmé)
    decors: tuple[str, ...] = ()       # loupe : natures connues des décors de ses points (ORDRE_DECORS), sans doublon
    # base au format 12 (§18) : positions MONDE (x, z, type de point de loupe ou None) où ce Yo-kai peut sortir à ce
    # lieu : points de loupe, points d'apparition des errants (salle de portail : dans la salle). Vide : inconnues.
    points: tuple[tuple[float, float, int | None], ...] = ()
    # base au format 13 (§19) : QUAND ce lieu donne ce Yo-kai. `moment` = masque (JOUR_SEC | JOUR_PLUIE | NUIT_SEC |
    # NUIT_PLUIE) : modes jour / nuit et taux sec / pluie de ses points de loupe, ou poids de l'errant dans cette version
    # du jeu, ET créneaux que sa condition permet (`moment_cond`) ; 0 : jamais. Base plus ancienne : la condition seule.
    moment: int = TOUJOURS
    moment_cond: int = TOUJOURS
    heure_dite: bool = False           # le moment affiché dit tout de la condition horaire (pas de « selon l'heure »)
    masques: dict = field(default_factory=dict)    # point de loupe (x, z, type) -> masque du POINT (hors condition)
    restantes: int | None = None       # lieu « invité » en attente : locations du déclencheur encore à cocher
    piece: int | None = None           # lieu « invité » présent : sa pièce (0 la Suite, 1..9 les chambres 101..109)
    rang_file: int | None = None       # lieu « invité » dans la file : sa place (1 = le prochain à avoir une pièce)
    piece_noms: dict | None = None     # lieu « crank » (V3, lot B1) : nom de la pièce par langue (ROM du joueur)
    taux: float | None = None          # ... chance par tour (poids du lot / total de la table), 0..1
    # lieu « crank » d'une pièce spéciale de la graine (voie, tirage dirigé) : exemplaires qui le donnent à coup sûr ;
    # lieu « fusion » : `piece_noms` = nom de l'objet de fusion
    exige: int | None = None
    # V3, lot M1 : sous un mélange par rencontre, pourquoi ce lieu garde le Yo-kai d'origine (clé « inch_* » de
    # textes.py : requete, tablo, sceau, condition, apres_jeu, partage, hasard…) ; None : changé, ou pas de mélange
    inchange: str | None = None

    def moment_point(self, point: tuple) -> int:
        """Masque de moments de l'un de ses points : celui du point de loupe (base 13), sinon celui du lieu."""
        m = self.masques.get(point)
        return self.moment if m is None else m & self.moment_cond

    @property
    def jamais(self) -> bool:
        """Jamais donné par ce lieu (errant au poids nul dans cette version du jeu, moments incompatibles)."""
        return self.moment == 0

    @property
    def portail(self) -> bool:
        return self.methode == PORTAIL

    @property
    def rang_exige(self) -> int | None:
        r = (self.condition or {}).get("rang")
        return r if isinstance(r, int) and 0 <= r <= 5 else None


@dataclass(frozen=True)
class Amitie:
    """Facilité d'amitié de fin de combat d'un Yo-kai (base au format 10, `archipelago_rando_yokai.md` §15) pour un
    PREMIER exemplaire (k = 0 Yo-kai de même base possédé) : une chance sur `cle` par combat (`cle` 0 : jamais ami) ;
    `bonus` = bonus de l'aliment de valeur 1 et 4 (dix-millièmes) quand sa catégorie est la préférée, coefficient
    compris (None : inconnu) ; `suivantes` = clés pour k = 1..5 ; `variante_jamais` : une autre espèce de la même base
    (combat d'histoire, boss) ne devient jamais amie."""
    cle: int
    bonus: tuple[float, float] | None = None
    suivantes: tuple[int, ...] = ()
    variante_jamais: bool = False
    aliment: int = 0                   # catégorie d'aliment préférée (ALIMENTS ; 0 : inconnue, rien d'affiché)

    @property
    def possible(self) -> bool:
        return self.cle > 0

    @property
    def chance(self) -> float:
        """Probabilité par combat sans aliment (0..1)."""
        return 1.0 / self.cle if self.cle > 0 else 0.0

    @property
    def chance_preferee(self) -> tuple[float, float] | None:
        """Probabilité par combat avec un aliment de la catégorie préférée : (valeur 1, valeur 4), plafonnée à 1."""
        if self.cle <= 0 or self.bonus is None:
            return None
        return tuple(min(1.0, self.chance + b / 10000.0) for b in self.bonus)

    @property
    def baisse(self) -> bool:
        """Le taux change quand on possède déjà un Yo-kai de cette base (la valeur affichée est celle de k = 0)."""
        return self.cle > 0 and any(c != self.cle for c in self.suivantes)


def lire_table_amitie(base: dict | None) -> tuple[list[list[int]], float | None] | None:
    """(lignes [clé, bonus 1..4], coefficient de l'aliment préféré) du champ `amitie` de la base locale (format 10) ;
    None : champ absent (base plus ancienne) ou mal formé : rien n'est affiché."""
    t = base.get("amitie") if isinstance(base, dict) else None
    lignes = t.get("lignes") if isinstance(t, dict) else None
    if not isinstance(lignes, list) or not lignes:
        return None
    out = []
    for l in lignes:
        if not isinstance(l, list) or not l or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0
                                                       for x in l):
            return None
        out.append(l)
    coef = t.get("prefere")
    return out, (float(coef) if isinstance(coef, (int, float)) and not isinstance(coef, bool) and coef > 0 else None)


def amitie_espece(table, quartets, aliment=None) -> Amitie | None:
    """Amitié d'une espèce : `quartets` = champ `amitie` de l'espèce (n° de ligne pour k = 0..5) ; None s'il manque.
    Un n° hors de la table vise une ligne absente : jamais ami (comme le jeu, `recrutable_en_combat`)."""
    if table is None or not isinstance(quartets, list) or not quartets or not all(
            isinstance(q, int) and not isinstance(q, bool) and q >= 0 for q in quartets):
        return None
    lignes, coef = table

    def ligne(q):
        return lignes[q] if q < len(lignes) else [0]
    l0 = ligne(quartets[0])
    bonus = None
    if l0[0] > 0 and coef is not None and len(l0) >= 5:
        bonus = (l0[1] * coef, l0[4] * coef)
    al = aliment if isinstance(aliment, int) and not isinstance(aliment, bool) and aliment in ALIMENTS else 0
    return Amitie(l0[0], bonus, tuple(ligne(q)[0] for q in quartets[1:]), aliment=al)


def amitie_groupe(candidates: list[Amitie | None]) -> Amitie | None:
    """Amitié affichée pour un Yo-kai (espèces d'une même base) : celle de l'espèce qui peut devenir amie (la plus
    favorable s'il y en a plusieurs), avec `variante_jamais` si une autre ne le peut pas ; None si aucune n'est connue."""
    connues = [a for a in candidates if a is not None]
    if not connues:
        return None
    possibles = sorted((a for a in connues if a.possible), key=lambda a: a.cle)
    if not possibles:
        return connues[0]
    a = possibles[0]
    return Amitie(a.cle, a.bonus, a.suivantes, len(possibles) < len(connues), a.aliment)


@dataclass
class Yokai:
    cle: str                           # « b<base> » (ou « p<param> » sans base) : les variantes d'une base ensemble
    especes: tuple[int, ...]
    noms: dict[str, str]
    rang: int | None
    tribu: int | None
    medaille: int | None               # n° du Médaillium (noms_local.json), None : inconnu ou hors Médaillium
    lieux: list[Lieu] = field(default_factory=list)
    categories: tuple[str, ...] = ()   # rencontres non sauvages où il apparaît (histoire, Yo-criminel…)
    melange: bool = False              # déplacé par le mélange (dans D et σ ≠ identité)
    fixe: bool = False                 # espèce fixée (F : quête, Tablo-blabla…) ; le mélange ne la touche jamais
    zone: str | None = None            # V3, lots M2b : zone garantie (Yo-kai demandé placé par la graine)
    vu: bool | None = None             # déjà rencontré (bit « vu » du Médaillium) ; None : inconnu
    ami: bool | None = None            # déjà ami (bit « ami » du Médaillium, P+0x44C | P+0x604) ; None : inconnu
    amitie: Amitie | None = None       # facilité d'amitié en combat (base au format 10) ; None : inconnue

    def nom(self, langue: str) -> str:
        lg = langue_base(langue)
        return self.noms.get(lg) or next((v for v in self.noms.values() if v), "") or "0x%08X" % self.especes[0]

    @property
    def lettre_rang(self) -> str:
        return RANGS[self.rang] if isinstance(self.rang, int) and 0 <= self.rang < len(RANGS) else "?"


@dataclass
class BossLigne:
    """Un boss de la graine (vue « Boss ») : `nom` saisi à la main (français) ; `noms` : noms du jeu (base locale, langue
    du joueur) de l'espèce principale du boss et de son remplaçant ; `vu` : bit « vu » d'une espèce du remplaçant."""
    cle: str
    nom: str
    classe: int                        # 1 : chapitres 3-7, 2 : chapitres 8-10, 3 : après-jeu, 0 : sans script
    remplace_par: str | None           # clé du remplaçant (None : pas remplacé)
    nom_remplacant: str
    noms: dict[str, str] = field(default_factory=dict)
    noms_remplacant: dict[str, str] = field(default_factory=dict)
    vu: bool | None = None
    # V3, force adaptée à la place (appliquée par le jeu installé) : multiplicateurs (%) PV, For, Esp, Déf, Vit ;
    # `force_exclue` : le remplaçant est le boss de l'objectif, à sa force d'origine (jamais adapté)
    force: list[int] | None = None
    force_exclue: bool = False

    def nom_affiche(self, langue: str) -> str:
        return self.nom if langue == "fr" else (self.noms.get(langue_base(langue)) or self.nom)

    def remplacant_affiche(self, langue: str) -> str:
        return self.nom_remplacant if langue == "fr" else (self.noms_remplacant.get(langue_base(langue))
                                                          or self.nom_remplacant)


def lire_boss(d: dict | None, base: dict | None, medaillium: dict | None) -> tuple[str, str, list[BossLigne]]:
    """(état, message, lignes) de `rando_boss.json` : état « absent » (pas de fichier), « aucun », « refuse »,
    « attente » (calcul, jeu sans le randomizer…), « actif »."""
    if not d or d.get("format") != FORMAT_BOSS:
        return "absent", "", []
    jeu = d.get("jeu") if isinstance(d.get("jeu"), dict) else {}
    msg = str(jeu.get("message") or "")
    etat = d.get("etat") if d.get("etat") in ("aucun", "refuse", "actif") else "attente"
    if etat == "actif" and jeu.get("support") is False:
        etat = "attente"
    esp = (base or {}).get("especes") if isinstance(base, dict) else None
    esp = esp if isinstance(esp, dict) else {}
    octets = bits_medaillium(medaillium, d.get("ident_partie"))

    def noms(liste) -> dict[str, str]:
        for x in liste or ():
            h = _hachage(x)
            n = (esp.get(str(h)) or {}).get("noms") if h is not None else None
            if isinstance(n, dict) and any(n.values()):
                return {k: v for k, v in n.items() if v}
        return {}

    lignes = []
    par_cle = {b.get("cle"): b for b in d.get("boss") or () if isinstance(b, dict)}
    for b in par_cle.values():
        vu = None
        if octets is not None:
            meds = [(esp.get(str(_hachage(x))) or {}).get("medaille") for x in b.get("especes") or ()]
            meds = [m for m in meds if isinstance(m, int) and m > 0]
            vu = any(medaille_vue(octets, m) for m in meds) if meds else None
        # force adaptée : seulement si le jeu installé l'applique (`jeu.force`, publié par le client)
        f = b.get("force")
        force = [int(x) for x in f] if (jeu.get("force") is True and b.get("remplace_par") and isinstance(f, list)
                                        and len(f) == 5 and all(isinstance(x, int) for x in f)) else None
        exclue = bool(jeu.get("force") is True and b.get("remplace_par") and b.get("force_exclue") is True)
        lignes.append(BossLigne(str(b.get("cle")), str(b.get("nom") or b.get("cle")), int(b.get("classe") or 0),
                                b.get("remplace_par"), str(b.get("remplace_par_nom") or ""),
                                noms(b.get("especes_origine")), noms(b.get("especes")), vu, force, exclue))
    ordre = {1: 0, 2: 1, 3: 2, 0: 3}
    lignes.sort(key=lambda x: (ordre.get(x.classe, 9), replier(x.nom)))
    return etat, msg, lignes


@dataclass
class Modele:
    """Tout ce que l'onglet affiche. `base_ok` False : base locale absente ou illisible (message « Réparer »)."""
    base_ok: bool
    melange: EtatMelange
    yokai: dict[str, Yokai]
    medaillium: bool                   # « vu » connu (medaillium.json de la partie + n° du Médaillium)
    genere: str = ""
    nb_rencontres: int = 0
    cartes: dict[str, dict[str, str]] = field(default_factory=dict)   # langue de la base -> {carte: nom}
    tribus: dict[str, dict[int, str]] = field(default_factory=dict)   # langue de la base -> {tribu: nom}
    amis: bool = False                 # « ami » connu (medaillium.json au format 2 de la partie)
    progression: Progression | None = None   # progression de la sauvegarde liée (progression.json de la partie)
    conditions_decodees: bool = False  # base au format 2 : conditions des lieux évaluables
    format_base: int = 0
    boss_etat: str = "absent"          # rando_boss.json : absent | aucun | refuse | attente | actif
    boss_message: str = ""
    boss: list[BossLigne] = field(default_factory=list)

    @property
    def acces_connu(self) -> bool:
        """Filtre « Accessibles maintenant » possible : conditions décodées et progression de la partie connue."""
        return self.conditions_decodees and self.progression is not None

    @property
    def noms_lieux(self) -> bool:
        return any(self.cartes.values())

    def nom_carte(self, carte: str, langue: str) -> str | None:
        return (self.cartes.get(langue_base(langue)) or {}).get(carte)

    def nom_tribu(self, tribu, langue: str) -> str | None:
        return (self.tribus.get(langue_base(langue)) or {}).get(tribu) if isinstance(tribu, int) else None

    def trier(self, langue: str, cles=None) -> list[Yokai]:
        ys = [self.yokai[k] for k in (cles if cles is not None else self.yokai)]
        return sorted(ys, key=lambda y: (replier(y.nom(langue)), y.cle))


def _cle_espece(esp: dict, p: int) -> str:
    b = esp.get(str(p), {}).get("base")
    return f"b{int(b)}" if isinstance(b, int) else f"p{p}"


def construire(base: dict | None, melange: dict | None = None, medaillium: dict | None = None,
               noms: dict | None = None, progression: dict | None = None, boss: dict | None = None,
               invites: dict | None = None, bingo: dict | None = None,
               voies: list[VoieGraine] | None = None) -> Modele:
    """Modèle du tracker depuis les trois fichiers (déjà lus). Pour chaque Yo-kai (regroupé par base) : ses lieux
    sauvages sous le mélange utilisé (voir `etat_melange`), avec le Yo-kai d'origine de chaque emplacement changé ;
    même règle que le jeu (`client/rando_yokai.appliquer`) : seules les rencontres de W sont réécrites, jamais un
    combattant partagé avec une rencontre hors W."""
    em = etat_melange(melange)
    cartes, tribus = lire_noms(noms)
    medailles = {int(k): int(v) for k, v in ((noms or {}).get("medailles") or {}).items()
                 if str(k).isdigit() and isinstance(v, int)} if isinstance(noms, dict) else {}
    be, bm, bl = lire_boss(boss, base, medaillium)
    if not isinstance(base, dict) or base.get("format") not in FORMATS_BASE or not isinstance(base.get("especes"), dict):
        return Modele(False, em, {}, False, cartes=cartes, tribus=tribus, boss_etat=be, boss_message=bm, boss=bl)
    esp = base["especes"]
    fmt = base["format"]
    if fmt >= 2:                                   # n° du Médaillium de la base (v[49] par espèce) : il prime
        for k, v in esp.items():
            if str(k).isdigit() and isinstance(v, dict) and isinstance(v.get("medaille"), int) and v["medaille"] > 0:
                medailles[int(k)] = v["medaille"]
    octets = bits_medaillium(medaillium, em.ident_partie)
    octets_amis = bits_medaillium(medaillium, em.ident_partie, "ami")
    prog = lire_progression(progression, em.ident_partie)
    # V3, lot M1 : catégories d'exigence par espèce (raison d'un Yo-kai gardé par le mélange par rencontre)
    exigences = {int(p): set(r) for p, r in (base.get("exigees") or {}).items() if str(p).isdigit()}
    for p, r in (base.get("fixees") or {}).items():
        if str(p).isdigit():
            exigences.setdefault(int(p), set()).update(r)
    fixees = {int(p) for p in (base.get("fixees") or {}) if str(p).isdigit()}
    sigma = em.sigma
    deplacees = set(sigma) | {int(c[1]) for e in base.get("rencontres") or () if "w" in e
                               for c in e.get("c") or () if em.en_jeu(e, c) != int(c[1])}
    yokai: dict[str, Yokai] = {}

    def groupe(p: int) -> Yokai | None:
        info = esp.get(str(p))
        if not info or not info.get("yokai"):
            return None
        k = _cle_espece(esp, p)
        y = yokai.get(k)
        if y is None:
            noms = {lg: n for lg, n in (info.get("noms") or {}).items() if n}
            if not noms:
                return None                            # espèce sans nom affichable (modèle, variante technique)
            y = yokai[k] = Yokai(k, (p,), noms, info.get("rang"), info.get("tribu"), medailles.get(p))
        elif p not in y.especes:
            y.especes += (p,)
            if y.medaille is None:
                y.medaille = medailles.get(p)
        return y

    for p in sorted(int(k) for k in esp if str(k).isdigit()):
        y = groupe(p)
        if y is not None:
            y.melange |= p in deplacees
            y.fixe |= p in fixees
            if p in em.zones:
                y.zone = em.zones[p][1]
    agreges: dict[tuple, Lieu] = {}
    points: dict[int, set] = {}                        # id(lieu) -> positions (format 12)
    bruts: dict[int, int] = {}                         # id(lieu) -> masque de moments de la base (format 13)
    masques: dict[int, dict] = {}                      # id(lieu) -> {point de loupe : masque} (format 13)
    categories: dict[str, set[str]] = {}
    nb = 0
    for e in base.get("rencontres") or ():
        combattants = e.get("c") or ()
        lieux = e.get("lieux")
        if lieux is None:                              # rencontre non sauvage : catégorie du Yo-kai
            for c in combattants:
                y = groupe(em.en_jeu(e, c))        # version 5 : coffre, train, gymnase mélangés (sinon : d'origine)
                if y is not None:
                    categories.setdefault(y.cle, set()).add(categorie(e.get("cat", "")))
            continue
        nb += 1
        pos = e.get("pos")
        lus = [_points_et_masques(p) for p in pos] if isinstance(pos, list) and len(pos) == len(lieux) else None
        positions = [x[0] for x in lus] if lus is not None else None
        mom = e.get("mom")
        moments = mom if isinstance(mom, list) and len(mom) == len(lieux) and all(
            isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= TOUJOURS for x in mom) else None
        masques_pos = ([x[1] if li[1] == "loupe" else {} for x, li in zip(lus, lieux)]
                       if moments is not None and lus is not None else None)
        for c in combattants:
            orig = int(c[1])
            en_jeu = em.en_jeu(e, c)
            y = groupe(en_jeu)
            if y is None:
                continue
            yo = groupe(orig)
            place = yo.cle if (en_jeu != orig and yo is not None) else None
            inch = raison_inchangee(em, base, exigences, e, c) if place is None else None
            niv = int(c[2])
            for k_lieu, li in enumerate(lieux):
                carte, methode, cond = li[:3]
                dec = li[3] if len(li) > 3 and isinstance(li[3], dict) else None
                cle = (y.cle, carte, methode, cond, place, json.dumps(dec, sort_keys=True) if dec else "", inch)
                l = agreges.get(cle)
                if l is None:
                    agreges[cle] = l = Lieu(carte, region_de(carte), methode, conditions(cond), niv, niv, place, 0,
                                            dec)
                    l.inchange = inch
                    if fmt >= 2:
                        l.acces, l.heure = evaluer(dec["e"] if dec else [], prog) if prog is not None else (
                            None, bool(dec and dec.get("heure")))
                    if dec:
                        l.moment_cond, l.heure_dite = moment_condition(dec.get("e"))
                    if methode == PORTAIL:
                        # salle tirée au sort : condition fausse = sûrement pas ; vraie = incertain (« ? »)
                        l.salle_connue = not (len(li) > 4 and li[4] == 0)
                        if l.acces:
                            l.acces = None
                    y.lieux.append(l)
                if methode == "loupe" and len(li) > 4 and isinstance(li[4], list):
                    natures = {DECORS_LOUPE[d] for d in li[4] if isinstance(d, int) and d in DECORS_LOUPE}
                    if natures - set(l.decors):
                        l.decors = tuple(n for n in ORDRE_DECORS if n in natures or n in l.decors)
                l.niv_min, l.niv_max = min(l.niv_min, niv), max(l.niv_max, niv)
                l.rencontres += 1
                if positions is not None:
                    pts = positions[k_lieu]
                    if pts - points.setdefault(id(l), set()):
                        points[id(l)] |= pts
                if moments is not None:
                    bruts[id(l)] = bruts.get(id(l), 0) | moments[k_lieu]
                    if masques_pos is not None and masques_pos[k_lieu]:
                        mq = masques.setdefault(id(l), {})
                        for pt, mm in masques_pos[k_lieu].items():
                            mq[pt] = mq.get(pt, 0) | mm
    # invités de l'Auberge des voyageurs (invites.json de CETTE partie) : un lieu « invité » sur la ligne du Yo-kai,
    # accessible quand il est présent (dans SA pièce) ; « attente » : déclencheur pas encore rempli ; « file » : invité,
    # attend qu'une pièce se libère ; « ami » : il ne revient plus
    voies = [v for v in voies or () if isinstance(v, VoieGraine) and v.sorte in SORTES_VOIE
             and isinstance(v.medaille, int) and v.medaille > 0]
    noms_voies = {v.medaille: v.noms for v in voies if isinstance(v.noms, dict) and any(v.noms.values())}

    def par_medaille(n: int) -> Yokai | None:
        """Ligne du Yo-kai de ce n° du Médaillium ; créée d'après une voie de la graine si la base n'en a aucune."""
        y = next((y for y in yokai.values() if y.medaille == n or any(medailles.get(p) == n for p in y.especes)), None)
        if y is None and n in noms_voies:
            y = yokai[f"m{n}"] = Yokai(f"m{n}", (), {lg: s for lg, s in noms_voies[n].items() if s}, None, None, n)
        return y

    listes = lire_invites(invites, em.ident_partie)
    for inv in listes:
        y = par_medaille(inv["medaille"])
        if y is None:
            continue
        carte = CARTES_INVITES[inv["piece"] or 0] if inv["etat"] == "present" else CARTE_INVITES
        cond = "invite_" + inv["etat"]
        if inv["etat"] == "attente" and inv["declencheur"] == "objet":
            cond = "invite_attente_objet"                # pas « toutes les requêtes » : son invitation
        l = Lieu(carte, region_de(CARTE_INVITES), INVITE, (cond,), 0, 0, None, 1)
        l.acces = inv["etat"] in ("present", "ami")
        l.restantes = inv["restantes"]
        l.piece = inv["piece"]
        l.rang_file = inv["rang"]
        y.lieux.append(l)
    # invités de la GRAINE absents d'invites.json (graine à ordre de réception : le client n'y met un invité à
    # invitation qu'à la réception de son invitation ; ou client jamais lié) : « pas encore invité », dès le début
    deja = {inv["medaille"] for inv in listes}
    for v in voies:
        if v.sorte != "invite" or v.medaille in deja:
            continue
        deja.add(v.medaille)
        y = par_medaille(v.medaille)
        if y is None:
            continue
        cond = "invite_attente_objet" if v.declencheur == "objet" else "invite_attente"
        l = Lieu(CARTE_INVITES, region_de(CARTE_INVITES), INVITE, (cond,), 0, 0, None, 1)
        l.acces = False
        y.lieux.append(l)
    # pièces spéciales de la graine (tirage dirigé, pieces.py) et fusions régionales : un lieu par voie
    for v in voies:
        if v.sorte == "invite":
            continue
        y = par_medaille(v.medaille)
        if y is None:
            continue
        carte = CARTES_CRANK.get(v.machine, CARTES_CRANK["present"]) if v.sorte == "piece" else CARTE_FUSION
        l = Lieu(carte, region_de(carte), CRANK if v.sorte == "piece" else FUSION, (), 0, 0, None, 1)
        l.piece_noms = dict(v.objet_noms) if isinstance(v.objet_noms, dict) else None
        l.exige = v.exige if isinstance(v.exige, int) and v.exige > 0 else None
        l.acces = v.acces
        y.lieux.append(l)
    # V3, lot B1 : Bingo-kai aléatoire (bingo.json de CETTE partie) : un lieu « Crank-a-kai » par (machine, pièce) qui
    # peut donner le Yo-kai ; noms des pièces lus dans la ROM du joueur (bingo_local.json, recopiés par le client)
    for machine, noms_piece, lots in lire_bingo(bingo, em.ident_partie):
        carte = CARTES_CRANK[machine]
        for x in lots:
            if not isinstance(x, dict) or not isinstance(x.get("param"), int):
                continue
            y = groupe(int(x["param"]))
            if y is None:
                continue
            l = Lieu(carte, region_de(carte), CRANK, (), 0, 0, None, 1)
            l.piece_noms = noms_piece
            total, poids = x.get("total"), x.get("poids")
            l.taux = poids / total if isinstance(total, int) and isinstance(poids, int) and total > 0 else None
            y.lieux.append(l)
    rang_region = {r: i for i, r in enumerate(ORDRE_REGIONS)}
    table = lire_table_amitie(base)
    for y in yokai.values():
        if table is not None:
            y.amitie = amitie_groupe([amitie_espece(table, (esp.get(str(p)) or {}).get("amitie"),
                                                    (esp.get(str(p)) or {}).get("aliment")) for p in y.especes])
        for l in y.lieux:
            if points.get(id(l)):
                l.points = tuple(sorted(points[id(l)], key=lambda p: (p[0], p[1], p[2] or 0)))
            l.masques = masques.get(id(l), {})
            l.moment = bruts.get(id(l), TOUJOURS) & l.moment_cond
            if l.jamais:
                l.acces = False
        y.lieux.sort(key=lambda l: (l.portail, rang_region.get(l.region, 99), l.carte, l.methode, l.conditions,
                                    l.niv_min))
        y.categories = tuple(sorted(categories.get(y.cle, set()) - {""}))
        # (ligne créée d'après une voie de la graine : aucune espèce de la base, son seul n° du Médaillium)
        nums = [medailles[p] for p in y.especes if p in medailles] or ([y.medaille] if not y.especes and y.medaille
                                                                       else [])
        if octets is not None and medailles:
            y.vu = any(medaille_vue(octets, n) for n in nums)
        if octets_amis is not None and medailles:
            y.ami = any(medaille_vue(octets_amis, n) for n in nums)
            if y.ami:
                y.vu = True                            # un ami a forcément été vu (FUN_004AAA98 pose les deux)
    return Modele(True, em, yokai, octets is not None and bool(medailles), str(base.get("genere", "")), nb, cartes,
                  tribus, octets_amis is not None and bool(medailles), prog, fmt >= 2, fmt, be, bm, bl)


def _points_et_masques(brut) -> tuple[set[tuple[float, float, int | None]], dict[tuple, int]]:
    """Positions d'un lieu de la base (format 12) : [[x, z] ou [x, z, type de point]…] -> {(x, z, type ou None)}, et
    masques de moments de ses points de loupe (format 13 : [x, z, type, masque]) -> {(x, z, type) : masque} ; tout
    élément mal formé est ignoré (base abîmée : pas de point, pas de masque, jamais d'erreur). Une seule passe."""
    out, masques = set(), {}
    for p in brut if isinstance(brut, list) else ():
        if isinstance(p, list) and len(p) >= 2 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in p[:2]):
            t = p[2] if len(p) > 2 and isinstance(p[2], int) and not isinstance(p[2], bool) else None
            k = (float(p[0]), float(p[1]), t)
            out.add(k)
            if t is not None and len(p) > 3:
                mm = p[3]
                if isinstance(mm, int) and not isinstance(mm, bool) and 0 <= mm <= TOUJOURS:
                    masques[k] = mm
    return out, masques


def _points(brut) -> set[tuple[float, float, int | None]]:
    return _points_et_masques(brut)[0]


def _masques(brut) -> dict[tuple[float, float, int | None], int]:
    return _points_et_masques(brut)[1]


def charger(dossier: str | Path) -> Modele:
    d = Path(dossier)
    melange = lire_json(d / NOM_MELANGE)
    return construire(lire_json(d / NOM_BASE), melange, lire_json(d / NOM_MEDAILLIUM),
                      lire_json(d / NOM_NOMS), lire_json(d / NOM_PROGRESSION), lire_json(d / NOM_BOSS),
                      lire_json(d / NOM_INVITES), lire_json(d / NOM_BINGO),
                      voies_dossier(d, etat_melange(melange).ident_partie))


def voies_dossier(d: Path, ident_partie: int | None = None) -> list[VoieGraine]:
    """Voies de la graine de `checks.json` (plan reconstruit par la logique de l'APWorld, `checks.voies_graine`), pour
    la partie du mélange seulement ; [] sans fichier, d'une autre partie, sans logique locale ou en cas d'erreur : le
    tracker reste celui de la base seule."""
    c = lire_json(d / NOM_CHECKS)
    if not isinstance(c, dict) or not _meme_partie(c, ident_partie):
        return []
    try:
        from . import checks as CK                    # (import tardif : checks importe ce module)
        return CK.voies_graine(c)
    except Exception:                                  # noqa: BLE001
        return []


def lire_noms(noms: dict | None) -> tuple[dict[str, dict[str, str]], dict[str, dict[int, str]]]:
    """`noms_local.json` -> (noms des cartes, noms des tribus) par langue de la base ; vides s'il manque."""
    cartes: dict[str, dict[str, str]] = {}
    tribus: dict[str, dict[int, str]] = {}
    if not isinstance(noms, dict) or noms.get("format") != 1 or not isinstance(noms.get("langues"), dict):
        return cartes, tribus
    for lg, v in noms["langues"].items():
        if not isinstance(v, dict):
            continue
        cartes[lg] = {str(k): str(n) for k, n in (v.get("cartes") or {}).items() if n}
        tribus[lg] = {int(k): str(n) for k, n in (v.get("tribus") or {}).items() if str(k).isdigit() and n}
    return cartes, tribus


# ------------------------------------------------------------------------------------------------ filtres
@dataclass
class Filtre:
    texte: str = ""
    rang: int | None = None
    tribu: int | None = None
    methode: str | None = None         # loupe | errant | portail | aucune (pas de lieu sauvage) | None (tous)
    region: str | None = None
    carte: str = ""                    # début d'identifiant de carte (« t101 », « t101g00 »)
    lieu: str = ""                     # recherche inverse : texte cherché dans le nom de la carte, de sa région ou
                                       # son identifiant (vue « par lieu »)
    non_vus: bool = False              # Yo-kai jamais rencontrés seulement (Médaillium connu)
    non_amis: bool = False             # Yo-kai pas encore amis seulement (« ami » du Médaillium connu)
    accessibles: bool = False          # lieux accessibles maintenant seulement (conditions décodées + progression) ;
                                       # un lieu à condition inconnue (acces None) est gardé et marqué « ? »

    def lieux(self, y: Yokai) -> list[Lieu]:
        """Lieux d'un Yo-kai qui passent les filtres de lieu (méthode, région, carte, accessibilité)."""
        m = self.methode if self.methode in METHODES else None
        c = self.carte.strip().lower()
        return [l for l in y.lieux if (m is None or l.methode == m) and (self.region is None or l.region == self.region)
                and (not c or l.carte.lower().startswith(c)) and not (self.accessibles and l.acces is False)]

    def garde(self, y: Yokai, langue: str) -> bool:
        if self.texte and replier(self.texte) not in replier(y.nom(langue)):
            return False
        if self.rang is not None and y.rang != self.rang:
            return False
        if self.tribu is not None and y.tribu != self.tribu:
            return False
        if self.non_vus and y.vu is not False:
            return False
        if self.non_amis and y.ami is not False:
            return False
        if self.methode == "aucune":
            return not y.lieux and self.region is None and not self.carte.strip() and not self.accessibles
        if self.methode in METHODES or self.region is not None or self.carte.strip() or self.accessibles:
            return bool(self.lieux(y))
        return True


def filtrer(m: Modele, f: Filtre, langue: str) -> list[Yokai]:
    return [y for y in m.trier(langue) if f.garde(y, langue)]


def lieu_correspond(m: Modele, carte: str, texte: str, langue: str) -> bool:
    """Recherche inverse : `texte` dans l'identifiant de la carte, son nom (ROM du joueur) ou celui de sa région."""
    q = replier(texte)
    if not q:
        return True
    return any(q in replier(x) for x in (carte, m.nom_carte(carte, langue) or "", nom_region(region_de(carte), langue)))


def par_lieu(m: Modele, f: Filtre, langue: str) -> list[tuple[str, list[tuple[str, list[tuple[Yokai, Lieu]]]]]]:
    """Recherche inverse : [(région, [(carte, [(Yo-kai, lieu)…])…])…], régions et cartes dans l'ordre d'affichage,
    Yo-kai par nom ; mêmes filtres que la liste (le texte filtre les Yo-kai, `f.lieu` les cartes)."""
    arbre: dict[str, dict[str, list]] = {}
    cache: dict[str, bool] = {}
    for y in filtrer(m, f, langue):
        for l in f.lieux(y):
            if l.carte not in cache:
                cache[l.carte] = lieu_correspond(m, l.carte, f.lieu, langue)
            if cache[l.carte]:
                arbre.setdefault(l.region, {}).setdefault(l.carte, []).append((y, l))
    out = []
    for r in sorted(arbre, key=lambda r: ORDRE_REGIONS.index(r) if r in ORDRE_REGIONS else 99):
        cartes = [(c, sorted(arbre[r][c], key=lambda yl: (yl[1].portail, replier(yl[0].nom(langue)), yl[1].methode,
                                                            yl[1].niv_min)))
                  for c in sorted(arbre[r])]
        out.append((r, cartes))
    return out


def regions_presentes(m: Modele) -> list[str]:
    vues = {l.region for y in m.yokai.values() for l in y.lieux}
    return [r for r in ORDRE_REGIONS if r in vues]


def tribus_presentes(m: Modele) -> list[int]:
    return sorted({y.tribu for y in m.yokai.values() if isinstance(y.tribu, int)})
