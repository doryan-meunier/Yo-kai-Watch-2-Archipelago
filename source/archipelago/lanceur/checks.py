"""Tracker des checks (onglet « Checks » du lanceur), SANS affichage : lecture de `checks.json` (écrit par le client,
`client/checks_local.py`) et de `progression.json`, plan de la graine d'après la logique de l'APWorld, état de chaque
location (faite / accessible maintenant / plus tard dans l'histoire / objets manquants), filtres, compteurs, objets
reçus. La vue tkinter est dans `vue_checks.py`. Bibliothèque standard seulement.

**Aucun spoiler** : le contenu d'une location n'est connu ici que si elle est faite ou indiquée par un hint (c'est
tout ce que le client écrit dans `checks.json`) ; le spoiler log complet est un fichier `.txt` séparé, écrit par le
client sur demande explicite (`demander_spoiler`).
"""
from __future__ import annotations

import collections
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

_CLIENT = Path(__file__).resolve().parents[1] / "client"
if str(_CLIENT) not in sys.path:
    sys.path.insert(0, str(_CLIENT))

import checks_local as ck  # noqa: E402  (client/, distribué avec le lanceur)

from . import tracker as TK  # noqa: E402

NOM_CHECKS = ck.NOM_CHECKS
FICHIERS = (ck.NOM_CHECKS, TK.NOM_PROGRESSION, TK.NOM_INVITES, TK.NOM_MEDAILLIUM)
TYPES = ck.TYPES
ETATS = ("fait", "accessible", "plus_tard", "bloque", "inconnu")
# `logique.PORTAILS` de l'APWorld : checks tardifs des portails mystères ; « tunnel » : boss du bout du Tunnel sans fin
PORTAILS = ("donjon", "salle", "crank", "requetes", "tunnel")
# V3, lot 3 : mêmes mentions pour les locations d'après-jeu (`LocationPlan.apres_jeu`) et les terrains longs de Blasters
MENTION_APRES_JEU, MENTION_BLASTERS = "apres_jeu", "blasters"
MENTION_TRANSFERT = "transfert"             # V3, lot 6 : requête à transfert de sauvegarde d'avant la fin, et son ami
# ap/blasters-terrains-apworld : terrains de Jiganyan (11) / Komak (12) et leurs « Ami » (n° 441 / 442) dans une graine
# qui ne fait pas poser l'option étendue 35 (clé `blasters_autres_editions` absente : graine d'avant) : terrains d'autres
# éditions, jamais listés seul dans cette édition du jeu : infaisables, montrés « bloqués » avec cette mention
MENTION_BLASTERS_EDITION = "blasters_edition"
TERRAINS_AUTRES_EDITIONS, MEDAILLES_AUTRES_EDITIONS = (11, 12), (441, 442)
MANQUE_EDITION = {"fr": "terrain d'une autre édition (graine d'avant)", "en": "other-edition stage (older seed)"}
FAMILLE_TERRAINS = "terrain_blasters"       # objets « Terrain : <boss> » (option `blasters_terrains` de l'APWorld)
FAMILLE_CLE_AJ = "objet_cle_aj"             # V3, lot 3 : objets d'accès de l'après-jeu (seulement s'ils sont dans la graine)


def mention(loc) -> str | None:
    """Mention de la ligne d'un check : check tardif des portails (`portail`), sinon terrain long de Blasters, sinon
    location d'après-jeu."""
    if loc is None:
        return None
    if getattr(loc, "portail", None):
        return loc.portail
    aj = getattr(loc, "apres_jeu", None)
    if aj == "blasters_long":
        return MENTION_BLASTERS
    if aj == "transfert":
        return MENTION_TRANSFERT
    return MENTION_APRES_JEU if aj else None
AUTRES = "__autres__"
FAMILLE_EVENEMENT = "evenement"             # objets des Yo-kai d'évènement (option `objets_evenement` de l'APWorld)
FAMILLE_CLE_V3 = "objet_cle_v3"             # V3 : objets à verrou étendu (seulement dans une graine qui a leur verrou)
FAMILLE_INVITATION = "invitation"           # objets « Invitation : <Yo-kai> » (option `invites` de l'APWorld)
NOM_ORIGINE = {"fr": "Histoire et objets-clés", "en": "Story and key items"}


# Checks « Ami » dont le Yo-kai, posé à sa place du jeu d'origine par son objet AP, attend que cette place soit libre
# (n° du Médaillium -> texte `ck_e_app_<clé>` ; docs/systemes/archipelago_evenement_invitation.md §10) : Jibanyan S
# (433) quand Jibanyan est ami, Hovernyan (351) une fois le chapitre 6 terminé. Vrai pour toute graine, ancienne ou
# nouvelle, jouée avec un patch à jour.
APPARITION = {433: "jibanyan", 351: "hovernyan"}
# V3, lot 17 : checks « Ami » dont le Yo-kai ne vient que par la REVANCHE d'une requête finie (n° du Médaillium :
# Triptyk, Carpitaine, Octorgone, Kyubi ; 7,5 % par victoire) : avec l'option `revanches_sans_limite` de la graine,
# la revanche se refait sans attendre le lendemain (docs/systemes/archipelago_v3_branchement_voie_revanches.md)
REVANCHES_LIBRES = frozenset({232, 316, 320, 80})


@dataclass
class Check:
    id: int
    nom: str
    zone: str                                  # clé de région de l'APWorld (AUTRES : absente du plan local)
    type: str                                  # coffre | objet_cle | boss | requete | tablo | chapitre | velo
    etat: str                                  # fait | accessible | plus_tard | bloque | inconnu
    contenu: str | None = None                 # « objet » ou « objet (pour joueur) » : fait ou indiqué SEULEMENT
    indice: bool = False                       # contenu connu par un indice (hint)
    exclue: bool = False                       # remplissage seulement (APWorld)
    # check « tardif » des portails mystères (APWorld, `logique.PORTAILS`) : donjon | salle | crank | requetes | tunnel ; None sinon
    portail: str | None = None
    # Yo-kai d'évènement à sa place d'origine qui n'apparaît pas dès l'objet reçu (APPARITION) : jibanyan | hovernyan
    apparition: str | None = None
    # check « Ami » d'une revanche de requête finie, dans une graine à revanches sans limite de jour (REVANCHES_LIBRES)
    revanche: bool = False
    # V3, lot L1 : check « Ami » d'un légendaire dans une graine à légendaires mélangés : nom du légendaire D'ORIGINE du
    # sceau qui le donne (« sceau de Shogunyan ») ; None : sceau d'origine, ou pas un légendaire
    sceau: str | None = None
    chapitres: int = 0                         # chapitres terminés exigés par la règle (et les connexions)
    manque: tuple[str, ...] = ()               # noms des objets manquants (bloque)
    rangs: int = 0                             # exemplaires de « Rang de montre » manquants (bloque)
    # retour du gros test V3 (2026-10-19) : ce que la colonne d'objets montrait dans ses listes, porté par la ligne
    # « Ami : <nom> » elle-même. Pièces spéciales : (famille, Yo-kai) de `ModeleChecks.pieces` (rang dans l'ordre,
    # « prochain », pièce qui le donne) ; légendaires mélangés : ligne de `ModeleChecks.legendaires` du sceau qui le
    # donne (sceau d'origine compris). None : pas un tel check, ou graine sans l'option.
    piece: "tuple[FamillePieces, YokaiPiece] | None" = None
    legendaire: "LigneLegendaire | None" = None


@dataclass
class Recu:
    n: int
    objet: str
    expediteur: str
    lieu: str
    soi: bool


@dataclass
class Invitation:
    """Un objet « Invitation : <Yo-kai> » de la graine (rubrique « Invitations » du sous-onglet « Carte »)."""
    cle: str                                   # clé de l'objet de l'APWorld
    nom: str                                   # nom de l'objet (« Invitation : Noko »)
    yokai: str                                 # nom du Yo-kai invité
    recus: int = 0                             # exemplaires reçus (checks.json)
    medaille: int | None = None                # n° du Médaillium de l'invité (None : inconnu de la logique locale)
    # état de l'invité d'une invitation REÇUE, si le lanceur le connaît déjà (`invites.json` du client, ou check
    # « Ami : <nom> » fait) : attente | file | present | ami ; None : inconnu (ou invitation pas reçue)
    etat: str | None = None
    piece: int | None = None                   # présent : 0 la Suite, 1..9 les chambres 101..109
    rang: int | None = None                    # dans la file : rang (1..)
    # V3, lot 14 : rang d'ARRIVÉE (graine à ordre de réception : 1 = la première invitation reçue ; None : pas reçue,
    # ou graine à ordre de la liste). (Le taux d'amitié relevé à l'Auberge du même lot est abandonné : lot 20.)
    arrivee: int | None = None


@dataclass
class YokaiPiece:
    """Un Yo-kai qu'une pièce spéciale du Crank-a-kai fait sortir (rubrique « Pièces spéciales »)."""
    medaille: int
    nom: str
    ami: bool = False                          # déjà ami (check « Ami » fait, ou bit du Médaillium de la partie)
    rang: int | None = None                    # famille à ordre de sortie : rang (1..) ; None : au choix / régional
    suivant: bool = False                      # famille à ordre de sortie : c'est lui que la prochaine pièce donnera
    piece: str = ""                            # pièce régionale : nom de SA pièce
    piece_recue: bool = False                  # pièce régionale : sa pièce est reçue
    piece_cle: str = ""                        # pièce régionale : clé d'objet de sa pièce (icône ; lot 21)


@dataclass
class FamillePieces:
    """Une famille de pièces spéciales de la graine (V3, lot 20) et les Yo-kai qu'elle donne. `genre` : « ordre »
    (Pièce 5 étoiles : ordre de sortie de la graine ; Pièce frisson : ordre du jeu), « choix » (Pile ou passe, Super
    pile ou passe : le joueur choisit parmi ceux qui manquent), « regions » (les 9 pièces régionales, un Yo-kai
    chacune), « unique » (lot 21 : Pièce bleu ciel, un seul Yo-kai, Bananar)."""
    cle: str
    nom: str
    genre: str
    recues: int = 0                            # exemplaires reçus (checks.json)
    total: int = 0                             # exemplaires dans la graine
    yokai: list[YokaiPiece] = field(default_factory=list)

    @property
    def suivant(self) -> YokaiPiece | None:
        return next((y for y in self.yokai if y.suivant), None)


@dataclass
class LigneLegendaire:
    """Un sceau de la page des légendes du Médaillium (V3, lot L1 : graine à légendaires mélangés)."""
    rang: int                                  # 1..8 : place du sceau dans la page des légendes
    sceau: str                                 # nom du légendaire d'ORIGINE du sceau (ses huit membres d'origine)
    donne: str                                 # nom du légendaire que le sceau donne dans cette graine
    medaille: int                              # n° du Médaillium du légendaire donné
    ami: bool = False                          # déjà ami (check fait, ou bit du Médaillium de la partie)


@dataclass
class ModeleChecks:
    present: bool = False                      # checks.json lisible
    connecte: bool = False
    spoiler: bool = False                      # le client a le contenu de toutes les locations (spoiler log possible)
    joueur: str = ""
    graine: str = ""
    checks: list[Check] = field(default_factory=list)
    zones: list[tuple[str, str]] = field(default_factory=list)     # (clé, nom) dans l'ordre de l'APWorld
    recus: list[Recu] = field(default_factory=list)
    chapitres_reels: int | None = None         # chapitres vraiment terminés (None : inconnus -> sens « en logique »)
    plan_ok: bool = False                      # logique de l'APWorld disponible et plan reconstruit
    objets_recus: dict[str, int] = field(default_factory=dict)     # clé d'objet de l'APWorld -> exemplaires reçus
    # objets des Yo-kai d'évènement de la graine (famille « evenement » dans le pool, ordre de l'APWorld) : section à
    # part de la colonne d'objets du sous-onglet « Carte » ; vide : option inactive (section cachée)
    objets_evenement: list[str] = field(default_factory=list)
    # V3 : objets à verrou étendu de la graine (famille « objet_cle_v3 » : Yo-kai Watch, Documents perdus, Cartes
    # d'Ultramax), dans l'ordre de l'APWorld ; vide pour une graine sans ces verrous (rien de plus dans la colonne)
    objets_v3: list[str] = field(default_factory=list)
    # invitations de la graine (famille « invitation » dans le pool, ordre de l'APWorld = ordre de la file en jeu) :
    # rubrique « Invitations » de la même colonne ; vide : graine sans l'option `invites` (rubrique absente)
    invitations: list[Invitation] = field(default_factory=list)
    # V3, lot 14 : la graine loge ses invités dans l'ordre de RÉCEPTION des invitations (`invites_ordre` de slot_data) :
    # la rubrique montre alors les invitations reçues d'abord, dans cet ordre (celui de la file), puis les autres
    invitations_reception: bool = False
    # V3, lot 18 : objectif « medaillium_complet » : {"acquis": entrées remplies (None : Médaillium de la partie
    # inconnu), "seuil", "total", "comptes": entrées que la logique garantit, "sans_check": [(n°, voie, état,
    # note)] des entrées MANQUANTES qui n'ont pas de check dans la graine (toutes, si le Médaillium est inconnu)} ;
    # None : autre objectif
    medaillium: dict | None = None
    # V3, lot 20 : pièces spéciales du Crank-a-kai de la graine (option `pieces_speciales`) : rubrique « Pièces
    # spéciales » de la colonne d'objets (pièces reçues, Yo-kai qui sortiront, dans l'ordre) ; vide : graine sans
    # l'option (rubrique absente)
    pieces: list[FamillePieces] = field(default_factory=list)
    # V3, lot L1 : légendaires mélangés (option `legendaires_melanges`) : rubrique « Légendaires » de la colonne
    # d'objets (quel sceau donne quel légendaire) ; vide : graine sans l'option (rubrique absente)
    legendaires: list[LigneLegendaire] = field(default_factory=list)
    horodatage: float = 0.0
    langue: str = "fr"

    @property
    def sans_donnees(self) -> bool:
        """Pas encore de checks de la partie (pas de `checks.json` valide, ou client jamais connecté à la graine :
        aucune location) : l'onglet l'explique au lieu d'une liste et d'une carte vides."""
        return not self.present or not self.checks

    def compter(self, checks: list[Check] | None = None) -> dict[str, int]:
        c = collections.Counter(x.etat for x in (self.checks if checks is None else checks))
        c["total"] = len(self.checks if checks is None else checks)
        return c

    def nom_zone(self, cle: str) -> str:
        return dict(self.zones).get(cle, cle)


# Yo-criminels (docs/systemes/archipelago_criminels_combats_jour.md) : le criminel du moment est un personnage posé
# dans la rue, sur les 5 cartes de la ville (6 points possibles par carte) ; clés de région de l'APWorld de ces cartes
# (t101g00, t103g00, t104g00, t105g00, t106g00), dans l'ordre du jeu.
ZONES_CRIMINELS = ("les_hauts_de_granval", "coteau_fleuri", "centre_ville_de_granval", "quartier_des_boutiques",
                   "la_corniche")


def ou_chercher(m: ModeleChecks, c: Check) -> list[str]:
    """Noms des zones où chercher un check qui n'a pas de lieu fixe : les 5 cartes de la ville pour un Yo-criminel
    (sa « zone » dans l'APWorld n'est que la région de sa règle de logique) ; [] pour les autres checks."""
    if c.type != "criminel":
        return []
    return [m.nom_zone(z) for z in ZONES_CRIMINELS]


def signature(dossier: Path) -> tuple:
    out = []
    for n in FICHIERS:
        try:
            st = (Path(dossier) / n).stat()
            out.append((st.st_size, st.st_mtime_ns))
        except OSError:
            out.append(None)
    return tuple(out)


def _texte_contenu(c: dict, langue: str) -> str:
    return ck.contenu_texte(str(c.get("objet") or "?"), c.get("joueur"), bool(c.get("soi")), langue)


def progression_medaillium(plan, octets: bytes | None) -> dict | None:
    """V3, lot 18 : avancement de l'objectif « medaillium_complet » d'un plan ; `octets` : bits « ami » du Médaillium
    de la partie (`tracker.bits_medaillium(…, "ami")`), None : inconnus."""
    md = getattr(plan, "medaillium", None) if plan is not None else None
    if not md:
        return None
    voies = md["voies"]
    pose = (lambda n: bool(octets[n >> 3] >> (n & 7) & 1)) if octets else (lambda n: False)
    avec_check = set()
    for loc in plan.locations:
        if loc.id_ap is not None:
            avec_check.update(getattr(loc, "medailles", ()) or ((loc.medaille,) if getattr(loc, "medaille", None) else ()))
    return {"acquis": sum(1 for n in voies if pose(n)) if octets else None, "seuil": md["seuil"],
            "total": len(voies), "comptes": md["comptes"],
            "sans_check": [(n, v["classe"], v["etat"], v["note"]) for n, v in sorted(voies.items())
                           if n not in avec_check and not pose(n)]}


def construire(d: dict | None, progression: dict | None, langue: str = "fr", logique=None,
               invites: dict | None = None, medaillium: dict | None = None) -> ModeleChecks:
    """Modèle de l'onglet à partir de `checks.json` (`d`) et de `progression.json` (même partie seulement) ;
    `invites` : `invites.json` du client (état des invités de l'Auberge, même partie seulement), None : inconnu."""
    m = ModeleChecks(langue=langue)
    if not d or d.get("format") != ck.FORMAT_CHECKS or not isinstance(d.get("locations"), list):
        return m
    m.present = True
    m.connecte, m.spoiler = bool(d.get("connecte")), bool(d.get("spoiler_disponible"))
    m.joueur, m.graine = str(d.get("joueur") or ""), str(d.get("graine") or "")
    m.horodatage = float(d.get("horodatage") or 0.0)
    L = logique or ck.logique_apworld()
    ids_objets = {}
    cles_evenement: list[str] = []
    cles_v3: list[str] = []
    cles_aj: list[str] = []
    cles_tb: list[str] = []
    objets_invitation: list[dict] = []
    if L is not None:
        try:
            from importlib import import_module
            don = import_module(ck.PAQUET_PUR + ".donnees").donnees()
            ids_objets = {int(o["id_ap"]): o["cle"] for o in don.objets}
            cles_evenement = [o["cle"] for o in don.objets if o.get("famille") == FAMILLE_EVENEMENT]
            cles_v3 = [o["cle"] for o in don.objets if o.get("famille") == FAMILLE_CLE_V3]
            cles_aj = [o["cle"] for o in don.objets if o.get("famille") == FAMILLE_CLE_AJ]
            cles_tb = [o["cle"] for o in don.objets if o.get("famille") == FAMILLE_TERRAINS]
            objets_invitation = [o for o in don.objets if o.get("famille") == FAMILLE_INVITATION]
        except Exception:                                  # noqa: BLE001
            ids_objets, cles_evenement, objets_invitation = {}, [], []
    toutes = [int(x) for x in d["locations"]]
    faites = {int(x) for x in d.get("faites") or []}
    contenus = {int(k): v for k, v in (d.get("contenus_faits") or {}).items() if isinstance(v, dict)}
    indices = {int(k): v for k, v in (d.get("indices") or {}).items() if isinstance(v, dict)}
    recus_brut = [r for r in d.get("recus") or [] if isinstance(r, dict)]
    m.recus = [Recu(int(r.get("n", i + 1)), str(r.get("objet") or "?"), str(r.get("expediteur") or "?"),
                    str(r.get("location") or ""), bool(r.get("soi"))) for i, r in enumerate(recus_brut)]
    m.objets_recus = dict(collections.Counter(ids_objets[int(r["id"])] for r in recus_brut
                                              if isinstance(r.get("id"), int) and int(r["id"]) in ids_objets))
    plan = ck.construire_plan(d.get("options"), langue, L)
    m.objets_evenement = objets_evenement_graine(d.get("options"), plan, cles_evenement, m.objets_recus)
    m.objets_v3 = objets_v3_graine(d.get("options"), cles_v3, m.objets_recus, plan)
    # objets d'accès de l'après-jeu : ceux du pool de CETTE graine (ou déjà reçus), à la suite, dans la même colonne
    pool = set(plan.pool_objets_cles) if plan is not None else set()
    m.objets_v3 += [k for k in cles_aj if k in pool or m.objets_recus.get(k, 0)]
    # ap/blasters-terrains-apworld : objets « Terrain : <boss> » de CETTE graine (ou déjà reçus), dans la même colonne
    m.objets_v3 += [k for k in cles_tb if k in pool or m.objets_recus.get(k, 0)]
    # progression réelle : sauvegarde liée de CETTE partie, et checks « Histoire : chapitre N terminé » faits
    prog = progression if isinstance(progression, dict) and progression.get("format") == TK.FORMAT_PROGRESSION \
        and progression.get("ident_partie") in (None, d.get("ident_partie")) else None
    acces: dict[int, ck.Acces] = {}
    places: dict[int, object] = {}
    if plan is not None:
        m.plan_ok = True
        # région d'origine de l'APWorld (« Menu ») : dons d'objets-clés et checks d'histoire, sans lieu précis
        m.zones = [(cle, NOM_ORIGINE.get(langue, NOM_ORIGINE["fr"]) if cle == "menu" else nom) for cle, nom in plan.regions]
        places = {loc.id_ap: loc for loc in plan.locations if loc.id_ap is not None}
        chap_faits = [int(loc.cle) for i, loc in places.items() if i in faites and loc.genre == "histoire"]
        m.chapitres_reels = ck.chapitres_termines(prog, chap_faits)
        objets = [ids_objets[int(r["id"])] for r in recus_brut
                  if isinstance(r.get("id"), int) and int(r["id"]) in ids_objets]
        acces = ck.evaluer(plan, objets, m.chapitres_reels)
    revanches = isinstance(d.get("options"), dict) and d["options"].get("revanches_sans_limite") is True
    editions = isinstance(d.get("options"), dict) and d["options"].get("blasters_editions") is True
    sceaux = sceaux_graine(plan, L, langue)                 # V3, lot L1 : légendaire -> nom du sceau qui le donne
    for i in toutes:
        loc = places.get(i)
        if i in faites:
            etat = "fait"
        elif loc is None or i not in acces:
            etat = "inconnu"
        else:
            etat = acces[i].etat
        a = acces.get(i)
        contenu, indice = None, False
        if i in faites and i in contenus:
            contenu = _texte_contenu(contenus[i], langue)
        if i in indices:
            indice = True
            if contenu is None:
                contenu = _texte_contenu(indices[i], langue)
        manque = tuple(L.nom_objet(k, langue) if L is not None else k for k in (a.objets if a else ()))
        portail = mention(loc)
        if not editions and loc is not None and (
                (loc.genre == "blasters" and getattr(loc, "terrain", None) in TERRAINS_AUTRES_EDITIONS)
                or (loc.genre == "ami" and getattr(loc, "medaille", None) in MEDAILLES_AUTRES_EDITIONS)):
            portail = MENTION_BLASTERS_EDITION
            if etat != "fait":
                etat, manque = "bloque", (MANQUE_EDITION.get(langue, MANQUE_EDITION["fr"]),)
        m.checks.append(Check(
            id=i, nom=loc.nom if loc is not None else f"#{i}", zone=loc.region if loc is not None else AUTRES,
            type=ck.type_de(loc) if loc is not None else "coffre", etat=etat, contenu=contenu, indice=indice,
            exclue=bool(loc.exclue) if loc is not None else False,
            portail=portail,
            apparition=APPARITION.get(getattr(loc, "medaille", None))
            if loc is not None and loc.genre == "ami" and not getattr(loc, "medailles", ()) else None,
            revanche=bool(revanches and loc is not None and loc.genre == "ami"
                          and getattr(loc, "medaille", None) in REVANCHES_LIBRES),
            sceau=sceaux.get(getattr(loc, "medaille", None)) if loc is not None and loc.genre == "ami" else None,
            chapitres=a.chapitres if a else 0,
            manque=manque if etat == "bloque" else (), rangs=a.rangs if a and etat == "bloque" else 0))
    m.invitations = invitations_graine(plan, objets_invitation, m.objets_recus, L, langue)
    etats = TK.lire_invites(invites, d.get("ident_partie"))
    etats_invitations(m.invitations, etats,
                      {loc.medaille for i, loc in places.items()
                       if i in faites and loc.genre in ("invite", "ami") and getattr(loc, "medaille", None)})
    options = d.get("options") if isinstance(d.get("options"), dict) else {}
    if options.get("invites_ordre") == "reception":
        m.invitations_reception = True
        m.invitations = ordre_reception(m.invitations, [ids_objets.get(r.get("id")) for r in recus_brut], etats)
    if any(c.zone == AUTRES for c in m.checks):
        m.zones.append((AUTRES, "Autres locations" if langue != "en" else "Other locations"))
    # V3, lot 18 : compteur de l'objectif « medaillium_complet » (`medaillium.json` de la même partie seulement)
    bits_amis = TK.bits_medaillium(medaillium, d.get("ident_partie"), "ami")
    m.medaillium = progression_medaillium(plan, bits_amis)
    # V3, lot 20 : rubrique « Pièces spéciales » (amis : checks « Ami » faits, et bits du Médaillium de la partie)
    amis_faits = {loc.medaille for i, loc in places.items()
                  if i in faites and loc.genre in ("invite", "ami") and getattr(loc, "medaille", None)}
    if bits_amis:
        amis_faits |= {n for n in range(1, min(len(bits_amis) * 8, 1024)) if bits_amis[n >> 3] >> (n & 7) & 1}
    m.pieces = pieces_graine(plan, m.objets_recus, amis_faits, L, langue)
    m.legendaires = legendaires_graine(plan, amis_faits, L, langue)
    annoter_amis(m, places)
    return m


def annoter_amis(m: ModeleChecks, places: dict) -> None:
    """Rattache à chaque check « Ami : <nom> » sa ligne de pièce spéciale (famille, Yo-kai) et sa ligne de légendaire
    (sceau qui le donne), d'après le n° du Médaillium de sa location. Rien de plus que ce que la graine publie déjà
    pour être montré (mêmes données que les anciennes listes de la colonne d'objets)."""
    if not m.pieces and not m.legendaires:
        return
    par_piece = {}
    for f in m.pieces:
        for y in f.yokai:
            par_piece.setdefault(y.medaille, (f, y))
    par_leg = {lg.medaille: lg for lg in m.legendaires}
    for c in m.checks:
        loc = places.get(c.id)
        if loc is None or loc.genre != "ami" or getattr(loc, "medailles", ()):
            continue
        n = getattr(loc, "medaille", None)
        c.piece = par_piece.get(n)
        c.legendaire = par_leg.get(n)


def _noms_legendaires(logique, langue: str) -> dict[int, str]:
    AJ = getattr(logique, "AJ", None)
    cle = "yokai_en" if langue == "en" else "yokai_fr"
    return {a["medaille"]: a[cle] for a in getattr(AJ, "AMIS", ()) if a.get("origine") == "legendaire"}


def sceaux_graine(plan, logique, langue: str) -> dict[int, str]:
    """V3, lot L1 : légendaire (n°) -> nom du légendaire d'origine du sceau qui le donne, pour les seuls légendaires
    déplacés ; {} : graine sans l'option, plan absent, ou logique locale d'une autre version."""
    perm = getattr(plan, "legendaires", ()) if plan is not None else ()
    if not perm or logique is None:
        return {}
    noms = _noms_legendaires(logique, langue)
    return {l: noms.get(s, f"n° {s}") for s, l in perm if s != l}


def legendaires_graine(plan, amis: set, logique, langue: str) -> list[LigneLegendaire]:
    """V3, lot L1 : les huit sceaux de la page des légendes et le légendaire que chacun donne dans CETTE graine
    (`Plan.legendaires`, publié par la graine pour être montré) ; [] : graine sans l'option."""
    perm = getattr(plan, "legendaires", ()) if plan is not None else ()
    if not perm or logique is None:
        return []
    noms = _noms_legendaires(logique, langue)
    return [LigneLegendaire(k, noms.get(s, f"n° {s}"), noms.get(l, f"n° {l}"), l, l in amis)
            for k, (s, l) in enumerate(sorted(perm), 1)]


def pieces_graine(plan, recus: dict[str, int], amis: set, logique, langue: str) -> list[FamillePieces]:
    """Familles de pièces spéciales de la graine (V3, lot 20 ; `Plan.pieces_speciales`), dans l'ordre : Pièce 5
    étoiles (ordre de sortie de CETTE graine, `Plan.pieces_ordre`), Pièce frisson (fleur), pièces régionales, Pile ou
    passe, Super pile ou passe. [] : graine sans l'option, plan absent, ou logique locale d'une autre version. Rien
    qui ne soit déjà connu du joueur : ses objets reçus, ses amis, et l'ordre de sortie (publié par la graine pour
    être montré : « la prochaine pièce donnera X »)."""
    PS = getattr(logique, "PS", None) if logique is not None else None
    if plan is None or PS is None or not getattr(plan, "pieces_speciales", False):
        return []
    try:
        par_cle = logique.donnees().objets_par_cle
        fiches = dict(getattr(logique, "AMIS_5_ETOILES_PAR_MEDAILLE", {}))
        fiches.update(getattr(logique, "INVITES_PAR_MEDAILLE", {}))
        bananar = getattr(logique, "AMI_BANANAR", None)             # lot 21
        if bananar:
            fiches[bananar["medaille"]] = bananar
        totaux = PS.exemplaires(True) if hasattr(PS, "exemplaires") else PS.EXEMPLAIRES
        cle_nom, cle_yk = ("nom_en", "yokai_en") if langue == "en" else ("nom_fr", "yokai_fr")

        def nom_yokai(n: int) -> str:
            return str(fiches.get(n, {}).get(cle_yk) or f"n° {n}")

        def famille(cle: str, genre: str, medailles, ordonnee: bool) -> FamillePieces:
            f = FamillePieces(cle, par_cle[cle][cle_nom], genre, int(recus.get(cle, 0)), totaux[cle])
            for k, n in enumerate(medailles, 1):
                f.yokai.append(YokaiPiece(n, nom_yokai(n), n in amis, k if ordonnee else None))
            if ordonnee:
                premier = next((y for y in f.yokai if not y.ami), None)
                if premier is not None:
                    premier.suivant = True
            return f

        out = [famille(PS.OBJET_5_ETOILES, "ordre", plan.pieces_ordre or PS.ORDRE_JEU, True),
               famille(PS.OBJET_FRISSON, "ordre", PS.ORDRE_FRISSON, True)]
        regions = FamillePieces("regions", "", "regions", 0, len(PS.REGIONALES))
        for piece, n, _fusion, _objet in PS.REGIONALES:
            recue = int(recus.get(piece, 0)) > 0
            regions.recues += 1 if recue else 0
            regions.yokai.append(YokaiPiece(n, nom_yokai(n), n in amis, None, False, par_cle[piece][cle_nom], recue,
                                            piece))
        out.append(regions)
        for cle in (PS.OBJET_PILE, PS.OBJET_SUPER):
            out.append(famille(cle, "choix", PS.CHOIX[cle], False))
        if getattr(plan, "lot21", False) and bananar:       # lot 21 : Pièce bleu ciel (graine d'avant : absente)
            out.append(famille(PS.OBJET_BLEU, "unique", (PS.BANANAR,), False))
        return out
    except (AttributeError, KeyError, TypeError, ValueError):
        return []


def objets_v3_graine(options, cles: list[str], recus: dict[str, int], plan=None) -> list[str]:
    """Objets-clés de la V3 présents dans la graine (`cles` : ceux de l'APWorld, dans son ordre), ou déjà reçus. Une
    graine de la V2 n'en a aucun. Avec le plan reconstruit (lot 9) : ceux de SON pool ou placés d'office à leur
    emplacement (les Parchemins de l'option `parchemins` y sont ; la Clé magnétique bleue n'y est qu'avec le verrou
    des rangs) ; sans plan : ceux dont le verrou (même clé) est dans `verrous_actifs` de slot_data."""
    if plan is not None:
        presents = set(getattr(plan, "pool_objets_cles", ()) or ())             | {loc.verrou for loc in getattr(plan, "locations", ()) if getattr(loc, "verrou", None)}
        return [k for k in cles if k in presents or recus.get(k, 0)]
    verrous = options.get("verrous_actifs") if isinstance(options, dict) else None
    verrous = set(verrous) if isinstance(verrous, (list, tuple, set)) else set()
    return [k for k in cles if k in verrous or recus.get(k, 0)]


def objets_evenement_graine(options, plan, cles: list[str], recus: dict[str, int]) -> list[str]:
    """Objets d'évènement de la graine (`cles` : ceux de l'APWorld, dans son ordre). Option publiée (slot_data 18) :
    ceux du pool du plan (tous s'il n'y a pas de plan), aucun si elle est inactive ; graine plus ancienne (option
    inconnue) : tous, mais seulement si l'un d'eux a été reçu (sinon section cachée). Seulement des objets DE CE MONDE
    que le joueur peut recevoir : aucun spoiler (ni lieu ni contenu)."""
    opt = options.get("objets_evenement") if isinstance(options, dict) else None
    if opt is None:
        return list(cles) if any(recus.get(k, 0) for k in cles) else []
    if not opt:
        return []
    if plan is None:
        return list(cles)
    pool = set(getattr(plan, "pool_objets_cles", ()) or ())
    return [k for k in cles if k in pool]


def invitations_graine(plan, objets: list[dict], recus: dict[str, int], logique, langue: str) -> list[Invitation]:
    """Invitations de la graine (`objets` : ceux de la famille « invitation » de l'APWorld, dans son ordre). Leur
    présence vient de la GRAINE : objets du pool du plan reconstruit d'après ses options (`invites_mode` et
    `evenement_places` de slot_data), plus tout objet d'invitation déjà reçu (plan absent, logique locale d'une autre
    version) ; une graine sans l'option, ou d'avant, n'en a aucune. Seulement des objets DE CE MONDE que le joueur
    peut recevoir, reçus ou non : aucun spoiler (ni lieu ni contenu)."""
    pool = set(getattr(plan, "pool_objets_cles", ()) or ()) if plan is not None else set()
    # Yo-kai invité de chaque objet : tables de l'APWorld (invités de l'Auberge, Yo-kai d'évènement à leur place)
    par_objet: dict[str, dict] = {}
    # (`INVITES_TOUS`, V3, lot 14 : + les 16 de Pièce 5 étoiles et les 16 des armées ; avant les amis : même objet)
    for table in (getattr(logique, "INVITES_TOUS", None) or getattr(logique, "INVITES", ()), getattr(logique, "AMIS", ())):
        for a in table or ():
            if isinstance(a, dict) and a.get("objet") and "base_invite" not in a:
                par_objet.setdefault(a["objet"], a)
    out = []
    for o in objets:
        cle = o["cle"]
        n = int(recus.get(cle, 0))
        if cle not in pool and not n:
            continue
        nom = o["nom_en"] if langue == "en" else o["nom_fr"]
        a = par_objet.get(cle) or {}
        yokai = a.get("yokai_en" if langue == "en" else "yokai_fr") or nom.split(":", 1)[-1].strip()
        med = a.get("medaille")
        out.append(Invitation(cle, nom, str(yokai), n, med if isinstance(med, int) else None))
    return out


def ordre_reception(invitations: list[Invitation], recus: list, invites: list[dict]) -> list[Invitation]:
    """Rubrique d'une graine à ordre de réception : les invitations REÇUES d'abord, dans l'ordre de réception (`recus` :
    clés des objets reçus, dans l'ordre du serveur : `checks.json`), puis les autres dans l'ordre de l'APWorld. Pour
    les invités de l'Auberge dont le client a publié le rang d'arrivée (`invites` : `tracker.lire_invites`), c'est CE
    rang qui fait foi entre eux (mémoire du client : ordre de la liste écrite au jeu), aux mêmes places de la liste.
    Pose `arrivee` de chaque invitation reçue (rang publié par le client, sinon rang parmi les invitations reçues)."""
    premier: dict[str, int] = {}
    for k, cle in enumerate(recus):
        if isinstance(cle, str):
            premier.setdefault(cle, k)
    recues = sorted((i for i in invitations if i.recus > 0), key=lambda i: premier.get(i.cle, len(recus)))
    publie = {x["medaille"]: x["arrivee"] for x in invites if x.get("arrivee")}
    places = [k for k, i in enumerate(recues) if i.medaille in publie]
    for k, i in zip(places, sorted((recues[k] for k in places), key=lambda i: publie[i.medaille])):
        recues[k] = i
    for k, i in enumerate(recues):
        i.arrivee = publie.get(i.medaille, k + 1)
    return recues + [i for i in invitations if i.recus <= 0]


def etats_invitations(invitations: list[Invitation], invites: list[dict], amis: set) -> None:
    """État de l'invité de chaque invitation REÇUE, d'après ce que le lanceur a déjà (`invites` : `tracker.lire_invites`
    de `invites.json` ; `amis` : n° du Médaillium des checks « Ami » faits) ; rien pour une invitation pas reçue."""
    par_medaille = {x["medaille"]: x for x in invites}
    for inv in invitations:
        if not inv.recus or inv.medaille is None:
            continue
        x = par_medaille.get(inv.medaille)
        if x is not None:
            inv.etat, inv.piece, inv.rang = x["etat"], x.get("piece"), x.get("rang")
        if inv.medaille in amis:
            inv.etat, inv.piece, inv.rang = "ami", None, None


_PLAN_VOIES: tuple[str, object] | None = None       # (options en JSON, plan) : dernier plan reconstruit pour les voies


def _plan_options(options: dict, logique):
    """Plan de la graine pour `options` (français : seuls les n° et clés servent), gardé tant qu'elles ne changent pas
    (checks.json change à chaque objet reçu ; la reconstruction prend ~0,1 s)."""
    global _PLAN_VOIES
    cle = json.dumps(options, sort_keys=True, default=str)
    if logique is None and _PLAN_VOIES is not None and _PLAN_VOIES[0] == cle:
        return _PLAN_VOIES[1]
    plan = ck.construire_plan(options, "fr", logique)
    if logique is None:
        _PLAN_VOIES = (cle, plan)
    return plan


def voies_graine(d: dict | None, logique=None) -> list[TK.VoieGraine]:
    """Voies de Yo-kai que la GRAINE donne sans rencontre (onglet Yo-kai, `tracker.construire(voies=…)`), d'après le
    plan reconstruit depuis les options de `checks.json` : invités de l'Auberge (locations de genre « invite » du plan,
    reçus ou non : le tracker les montre « pas encore invité » tant que `invites.json` ne les a pas), pièces spéciales
    (`Plan.pieces_speciales` : Pièce 5 étoiles dans l'ordre de sortie de la graine, Pièce frisson, pièces régionales,
    Pile ou passe et Super pile ou passe, Pièce bleu ciel du lot 21) et fusions régionales. Noms des Yo-kai, des pièces
    et des objets : ceux saisis à la main dans l'APWorld (règle 6). Accès = objets exigés reçus (`recus` de
    checks.json) ; rien d'autre (ni lieu ni contenu d'une location). [] sans plan."""
    if not isinstance(d, dict) or d.get("format") != ck.FORMAT_CHECKS or not isinstance(d.get("options"), dict):
        return []
    L = logique or ck.logique_apworld()
    if L is None:
        return []
    plan = _plan_options(d["options"], logique)
    if plan is None:
        return []
    don = L.donnees()
    par_cle = don.objets_par_cle
    ids = {int(o["id_ap"]): o["cle"] for o in don.objets}
    recus = collections.Counter(ids[int(r["id"])] for r in d.get("recus") or []
                                if isinstance(r, dict) and isinstance(r.get("id"), int) and int(r["id"]) in ids)
    fiches: dict[int, dict] = {}
    for table in (getattr(L, "INVITES_TOUS", None) or getattr(L, "INVITES", ()), getattr(L, "AMIS_5_ETOILES", ()),
                  (getattr(L, "AMI_BANANAR", None),)):
        for a in table or ():
            if isinstance(a, dict) and isinstance(a.get("medaille"), int):
                fiches.setdefault(a["medaille"], a)

    def noms(n: int) -> dict:
        a = fiches.get(n) or {}
        return {lg: str(a[k]) for lg, k in (("fr", "yokai_fr"), ("engb", "yokai_en")) if a.get(k)}

    def objet(cle: str) -> dict:
        o = par_cle.get(cle) or {}
        return {lg: str(o[k]) for lg, k in (("fr", "nom_fr"), ("en", "nom_en")) if o.get(k)}

    out: list[TK.VoieGraine] = []
    for loc in plan.locations:
        if loc.genre == "invite" and isinstance(loc.medaille, int):
            a = fiches.get(loc.medaille) or {}
            out.append(TK.VoieGraine(loc.medaille, noms(loc.medaille), "invite", str(a.get("declencheur") or "")))
    PS = getattr(L, "PS", None)
    if PS is not None and getattr(plan, "pieces_speciales", False):
        def piece(cle: str, n: int, k: int, machine: str = "present") -> None:
            out.append(TK.VoieGraine(n, noms(n), "piece", objet_noms=objet(cle), exige=k, machine=machine,
                                     acces=recus[cle] >= k))
        for k, n in enumerate(plan.pieces_ordre or PS.ORDRE_JEU, 1):
            piece(PS.OBJET_5_ETOILES, n, k)        # avec k pièces, les k premiers manquants de l'ordre sortent
        for k, n in enumerate(PS.ORDRE_FRISSON, 1):
            piece(PS.OBJET_FRISSON, n, k)
        for cle, n, _f, _o in PS.REGIONALES:
            piece(cle, n, 1)
        for cle in (PS.OBJET_PILE, PS.OBJET_SUPER):
            for n in PS.CHOIX[cle]:
                piece(cle, n, 1)                   # au choix dans le menu : une pièce suffit pour celui-là
        if getattr(plan, "lot21", False):
            piece(PS.OBJET_BLEU, PS.BANANAR, 1)
            piece(PS.OBJET_BLEU, PS.BANANAR, 1, "passe")   # (origine du jeu) : dirigée sur les DEUX machines (lot 21)
        for cle, n, f, o in PS.REGIONALES:
            out.append(TK.VoieGraine(f, noms(f), "fusion", objet_noms=objet(o),
                                     acces=recus[cle] >= 1 and recus[o] >= 1))
    return out


def charger(dossier: str | Path, langue: str = "fr") -> ModeleChecks:
    d = Path(dossier)
    return construire(ck.lire_json(d / ck.NOM_CHECKS), TK.lire_json(d / TK.NOM_PROGRESSION), langue,
                      invites=TK.lire_json(d / TK.NOM_INVITES), medaillium=TK.lire_json(d / TK.NOM_MEDAILLIUM))


# ------------------------------------------------------------------------------------------------ filtres
@dataclass
class Filtre:
    texte: str = ""
    type: str | None = None                    # un de TYPES, ou None (tous)
    zone: str | None = None
    pas_faits: bool = False
    accessibles: bool = False

    def garde(self, c: Check, m: ModeleChecks) -> bool:
        if self.type and c.type != self.type:
            return False
        if self.zone and c.zone != self.zone:
            return False
        if self.pas_faits and c.etat == "fait":
            return False
        if self.accessibles and c.etat != "accessible":
            return False
        if self.texte:
            t = TK.replier(self.texte)
            cible = " ".join((c.nom, m.nom_zone(c.zone), c.contenu or ""))
            if c.piece is not None:                      # « Pièce 5 étoiles », « Pièce du sud »… trouvent leurs Yo-kai
                cible += " " + (c.piece[1].piece or c.piece[0].nom)
            if c.legendaire is not None:                 # le nom du sceau trouve le légendaire qu'il donne
                cible += " " + c.legendaire.sceau
            if t not in TK.replier(cible):
                return False
        return True


def par_zone(m: ModeleChecks, f: Filtre) -> list[tuple[str, str, list[Check], dict[str, int]]]:
    """[(clé de zone, nom, checks gardés, compteurs de TOUTE la zone)] dans l'ordre des régions de l'APWorld ; zones
    sans check gardé omises. Dans une zone : non faits d'abord (accessibles, plus tard, bloqués), puis faits."""
    ordre = {e: i for i, e in enumerate(("accessible", "plus_tard", "bloque", "inconnu", "fait"))}
    out = []
    for cle, nom in m.zones:
        tous = [c for c in m.checks if c.zone == cle]
        gardes = sorted((c for c in tous if f.garde(c, m)), key=lambda c: (ordre.get(c.etat, 9), c.nom))
        if gardes:
            out.append((cle, nom, gardes, m.compter(tous)))
    return out


def types_presents(m: ModeleChecks) -> list[str]:
    presents = {c.type for c in m.checks}
    return [t for t in TYPES if t in presents]
