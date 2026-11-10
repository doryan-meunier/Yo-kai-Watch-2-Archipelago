"""Distributeurs de soda en checks, côté client (V3, lot C1, `docs/systemes/archipelago_v3_distributeurs.md` ; zone
ApDistrib, §50 de `docs/systemes/archipelago_boite.md`).

Un check par boisson et par machine, SANS bit de sauvegarde : le serveur tient l'état. Ce module :
1. lit `slot_data.distributeurs` (machines de la graine : carte, rang du point dans le fichier `<carte>_oneplace`,
   nombre de points du fichier, boisson ; contenu montré) ;
2. résout l'identifiant du point de chaque machine dans la ROM DU JOUEUR (`installation/distributeurs.py`, fichier
   local `distributeurs_local.json`, généré en tâche de fond s'il manque ; règle 6 : jamais dans l'APWorld) ;
3. écrit la table de la boîte pour la sauvegarde LIÉE seulement : toutes les machines de la graine dans l'ordre (index =
   rang de la machine), leurs boissons « à acheter » = locations ni cochées ni en attente sur le serveur, ni achetées
   pendant cette instance du jeu ; table complète une fois (jeu arrêté, `valide` en dernier), puis seulement l'octet
   `a_acheter` d'une machine qui change (dans le lot du tour) ;
4. lit les évènements DISTRIBUTEUR (achat : location envoyée) et DISTRIBUTEUR_VU (machine ouverte : indices des
   boissons Archipelago montrées) ;
5. noms de vitrine des boissons (« <objet> (pour <joueur>) ») ajoutés À LA FIN de la table des noms (§13), après ceux
   des coffres et des dons de script : seulement s'il reste de la place.
Aucune lecture périodique : `compile` de la zone est lu une fois par instance du jeu, seulement pour une graine qui a
des distributeurs ; le reste ne lit que l'en-tête et le journal, déjà lus à chaque tour.
"""
from __future__ import annotations

import asyncio
import contextlib
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from . import boite_protocole as bp
except ImportError:                                          # module chargé hors paquet (tests, outils)
    import boite_protocole as bp


@dataclass
class Machine:
    """Machine de la graine : (carte, rang du point dans le fichier), index dans la table du jeu ; `point` lu dans la
    ROM du joueur (0 tant que ce n'est pas fait) ; locations de ses boissons (None : boisson sans location)."""
    index: int
    carte: str
    rang: int
    nb_points: int | None
    locations: list
    point: int = 0


def lire_slot_data(sd: dict) -> tuple[dict[int, dict], list[str]]:
    """{location: {carte, rang, nb_points, boisson, contenu}} de `slot_data.distributeurs` (clé absente : aucun) et les
    erreurs de forme rencontrées (entrées écartées)."""
    out, erreurs = {}, []
    for x in sd.get("distributeurs") or [] if isinstance(sd.get("distributeurs"), list) else []:
        try:
            loc, carte, rang, boisson = int(x["location"]), str(x["carte"]), int(x["rang"]), int(x["boisson"])
            nb = x.get("nb_points")
            nb = int(nb) if nb is not None else None
        except (KeyError, TypeError, ValueError):
            erreurs.append(repr(x)[:80])
            continue
        if not (carte.isascii() and carte.isalnum() and len(carte) == 7) or not 0 <= boisson < bp.DISTRIB_LIGNES \
                or rang < 0:
            erreurs.append(repr(x)[:80])
            continue
        c = None
        if "hachage" in x:
            c = (bool(x.get("propre")), int(x["hachage"]) & 0xFFFFFFFF, x.get("texte"))
        out[loc] = {"carte": carte, "rang": rang, "nb_points": nb, "boisson": boisson, "contenu": c}
    return out, erreurs


def machines_de(locs: dict[int, dict]) -> tuple[list[Machine], int]:
    """Machines dans l'ordre des locations et `etiquette_base` (location de la boisson 0 de la machine 0) ; ValueError
    si les locations ne suivent pas la convention du jeu (boisson i de la machine m = base + 2 m + i)."""
    if not locs:
        return [], 0
    premiere = min(locs)
    base = premiere - locs[premiere]["boisson"]
    machines: dict[tuple[str, int], Machine] = {}
    for loc in sorted(locs):
        x = locs[loc]
        m = (loc - base) // bp.DISTRIB_LIGNES
        if loc - base != bp.DISTRIB_LIGNES * m + x["boisson"]:
            raise ValueError(f"location {loc} hors de la convention des distributeurs")
        cle = (x["carte"], x["rang"])
        if cle not in machines:
            if m != len(machines):
                raise ValueError(f"machine {cle} au rang {m} (attendu {len(machines)})")
            machines[cle] = Machine(m, x["carte"], x["rang"], x["nb_points"], [None] * bp.DISTRIB_LIGNES)
        mach = machines[cle]
        if mach.index != m or mach.locations[x["boisson"]] is not None:
            raise ValueError(f"location {loc} : machine {cle} incohérente")
        mach.locations[x["boisson"]] = loc
    if len(machines) > bp.CAP_DISTRIB:
        raise ValueError(f"{len(machines)} machines pour {bp.CAP_DISTRIB} places dans le jeu")
    return list(machines.values()), base


def entrees_table(machines: list[Machine], fait, affiche) -> list[bytes]:
    """Entrées de la table (une par machine, dans l'ordre) : boisson « à acheter » = location présente et non faite
    (`fait(loc)`) ; objet montré = `affiche(loc)` (0 : vitrine)."""
    out = []
    for m in machines:
        a = sum(1 << i for i, loc in enumerate(m.locations) if loc is not None and not fait(loc))
        out.append(bp.enc_distrib(bp.crc_carte(m.carte), m.point,
                                  tuple(affiche(loc) if loc is not None else 0 for loc in m.locations), a,
                                  bp.DISTRIB_VALIDE))
    return out


def _installation():
    racine = Path(__file__).resolve().parents[1]          # archipelago/
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    from installation import distributeurs as idi           # noqa: E402
    return idi


class SuiviDistributeurs:
    """État du client pour les distributeurs (une instance par `Synchro`)."""

    def __init__(self, synchro):
        self.s = synchro
        self.locs: dict[int, dict] = {}
        self.machines: list[Machine] = []
        self.base = 0
        self.erreur_table = ""              # graine dont la liste ne suit pas la convention (refus)
        self.resolution = "pretes"          # pretes | calcul | absente | refusee (points lus dans la ROM du joueur)
        self._tache: asyncio.Task | None = None
        self.manquants = False              # graine à distributeurs, jeu ou ROM qui ne les permettent pas : refus
        self._etat: tuple[int, int | None] | None = None   # (instance, bits DISTRIB_* publiés ou None)
        self._ecrite: tuple | None = None   # (instance, sauvegarde, entrées écrites) de la dernière table
        self.achetes: set[int] = set()      # locations dont l'achat a été lu dans le journal (cette instance)
        self._indices: set[tuple[str, int, int]] = set()
        self._vues: list[int] = []          # boissons AP montrées (DISTRIBUTEUR_VU) lues dans ce tour, à indiquer
        self.statut = "aucun"

    # ------------------------------------------------------------------ graine
    def appliquer(self, sd: dict) -> None:
        self.locs, erreurs = lire_slot_data(sd)
        if erreurs:
            self.s.log.warning("Distributeurs : %d entrée(s) de slot_data illisible(s) : %s", len(erreurs), erreurs[:3])
        try:
            self.machines, self.base = machines_de(self.locs)
            self.erreur_table = ""
        except ValueError as e:
            self.machines, self.base, self.erreur_table = [], 0, str(e)
        self.resolution = "pretes" if not self.machines else "absente"
        self._ecrite = None

    @property
    def actifs(self) -> bool:
        return bool(self.locs)

    def nouvelle_instance(self) -> None:
        self._etat = None
        self._ecrite = None
        self.achetes.clear()

    def oublier(self) -> None:
        """Sauvegarde changée : la table est réécrite pour la suivante (ou retirée si elle n'est pas liée)."""
        self._ecrite = None

    # ------------------------------------------------------------------ points lus dans la ROM du joueur
    def preparer(self) -> str:
        if not self.machines or all(m.point for m in self.machines):
            self.resolution = "pretes" if not self.erreur_table else "refusee"
            return self.resolution
        if self._tache is not None and not self._tache.done():
            return "calcul"
        try:
            idi = _installation()
        except Exception as e:  # noqa: BLE001 - module distribué avec le client ; absent : refus clair
            return self._refus("absente", f"module installation/distributeurs.py introuvable ({e})")
        try:
            attendue = idi.apworld_distributeurs().EMPREINTE_DISTRIBUTEURS
        except Exception:  # noqa: BLE001 - APWorld embarqué illisible : contrôle machine par machine
            attendue = None
        table = idi.charger(self.s.stockage.dossier, attendue)
        if table is None:
            if self.resolution == "refusee":
                return "refusee"
            rom = self.s.config.rom
            if not rom or not Path(rom).is_file():
                return self._refus("absente", "table locale des distributeurs absente et ROM non configurée "
                                   "(« Réparer le mod » dans le lanceur)")
            self.s.log.info("Distributeurs : table locale générée depuis la ROM…")
            self.resolution = "calcul"
            self._tache = asyncio.create_task(asyncio.to_thread(idi.generer_fichier, rom, self.s.stockage.dossier))
            self._tache.add_done_callback(self._generee)
            return "calcul"
        try:
            points = [idi.point(table, m.carte, m.rang, m.nb_points) for m in self.machines]
        except idi.ErreurDistributeurs as e:
            return self._refus("refusee", f"distributeur de la graine introuvable dans la ROM ({e})")
        for m, p in zip(self.machines, points):
            m.point = p
        self.resolution = "pretes"
        self.s.log.info("Distributeurs lus dans la ROM du joueur : %d machine(s)", len(self.machines))
        return "pretes"

    def _generee(self, t: asyncio.Task) -> None:
        if t.cancelled():
            return
        e = t.exception()
        if e is not None:
            self._refus("refusee", f"ROM refusée : {e}")
        else:
            self.s.log.info("Table locale des distributeurs écrite : %s", t.result())
            self.resolution = "absente"
            self.preparer()

    def _refus(self, etat: str, message: str) -> str:
        if self.resolution != etat:
            self.s.log.error("Distributeurs : %s ; les checks de distributeur sont impossibles (rien ne sera lié, livré "
                             "ni envoyé)", message)
        self.resolution = etat
        return etat

    # ------------------------------------------------------------------ jeu
    async def compile(self, h) -> int | None:
        """Bits DISTRIB_* publiés par le jeu (lus une fois par instance), None : zone absente ou non publiée."""
        if self._etat is None or self._etat[0] != self.s._instance:
            lu = None
            if bp.distrib_disponibles(h):
                lu = bp.distrib_compiles(await self.s.pont.lire(bp.ZONE + bp.OFF_DISTRIB, 8))
            self._etat = (self.s._instance, lu)
            self.s.log.info("Distributeurs compilés dans le jeu : %s",
                            "non (patch d'avant le lot C1)" if lu is None else f"{lu:#x}")
            if lu is not None and lu & bp.DISTRIB_COMPILE and not lu & bp.DISTRIB_BONUS:
                self.s.log.warning("Distributeurs : ce patch n'empêche pas la boisson bonus (1 achat sur 20) de "
                                   "remplacer l'achat d'une boisson Archipelago : il faudra alors la racheter")
        return self._etat[1]

    async def verifier(self, h) -> None:
        """Refus de la partie (« Verrous incompatibles ») si la graine a des distributeurs et que la ROM ne permet pas
        de les reconnaître ou que le jeu ne les a pas (la fonction 49 absente est aussi refusée comme toute fonction
        étendue, `_verifier_verrous`)."""
        if not self.actifs:
            if self.manquants:
                self.manquants = False
            return
        if self.erreur_table:
            manquants = True
        else:
            c = await self.compile(h)
            manquants = self.preparer() != "pretes" or c is None or not c & bp.DISTRIB_COMPILE
        if manquants != self.manquants:
            self.manquants = manquants
            if manquants:
                self.s.log.error("Distributeurs : %s ; la partie a %d checks de distributeur : rien ne sera lié, livré "
                                 "ni envoyé. Installer le patch du mod à jour, ou générer une graine avec l'option "
                                 "distributeurs: aucun.",
                                 self.erreur_table or ("points pas encore lus dans la ROM (%s)" % self.resolution
                                                       if self.resolution != "pretes" else "jeu sans les distributeurs"),
                                 len(self.locs))

    def _fait(self, loc: int) -> bool:
        r = self.s.reseau
        return loc in self.achetes or (r is not None and (loc in r.locations_verifiees or loc in r.locations_en_attente))

    def _affiche(self, loc: int) -> int:
        c = self.s._contenu(loc) if hasattr(self.s, "_contenu") else None
        if c is None:
            x = self.locs.get(loc, {}).get("contenu")
            return 0 if x is None or x[1] == self.s.catalogue.vitrine else x[1]
        return 0 if c.hachage == self.s.catalogue.vitrine else c.hachage

    def noms(self) -> dict[int, bytes]:
        """Noms de vitrine des boissons Archipelago (étiquette = location) : « <objet> (pour <joueur>) »."""
        out = {}
        for loc in sorted(self.locs):
            c = self.s._contenu(loc) if hasattr(self.s, "_contenu") else None
            texte = c.texte if c is not None else (self.locs[loc]["contenu"] or (0, 0, None))[2]
            hachage = c.hachage if c is not None else (self.locs[loc]["contenu"] or (0, self.s.catalogue.vitrine))[1]
            if texte and hachage == self.s.catalogue.vitrine:
                out[loc] = texte
        return out

    async def ecrire(self, h) -> None:
        """Table des distributeurs (sauvegarde liée, jeu qui la publie, points résolus) : complète au premier tour ou
        quand les machines changent, sinon les seuls octets `a_acheter` qui changent ; table retirée (`valide` = 0) si
        la sauvegarde n'est plus liée. Aucune écriture si rien ne change."""
        if not self.actifs or self.manquants or self.resolution != "pretes":
            return
        c = self._etat[1] if self._etat and self._etat[0] == self.s._instance else None
        if c is None or not c & bp.DISTRIB_COMPILE:
            return
        liee = self.s.sauvegarde == "liee"
        if not liee:
            if self._ecrite is not None and self._ecrite[2]:
                async with self.s.pont.transaction():
                    await self.s.pont.ecrire(bp.ZONE + bp.OFF_DISTRIB, struct.pack("<I", 0))
                self.s.log.info("Table des distributeurs retirée (sauvegarde non liée)")
            self._ecrite = (self.s._instance, None, ())
            return
        entrees = entrees_table(self.machines, self._fait, self._affiche)
        cle = (self.s._instance, h.ident_sauvegarde)
        ancienne = self._ecrite
        if ancienne is not None and ancienne[:2] == cle and ancienne[2] == tuple(entrees):
            return
        if ancienne is not None and ancienne[:2] == cle and len(ancienne[2]) == len(entrees) \
                and all(a[:16] == b[:16] for a, b in zip(ancienne[2], entrees)):
            changes = {i: b[16] for i, (a, b) in enumerate(zip(ancienne[2], entrees)) if a[16] != b[16]}
            async with self.s.pont.transaction():
                for off, octets in bp.ecritures_distrib_a_acheter(changes):
                    await self.s.pont.ecrire(bp.ZONE + off, octets)
            self.s.log.info("Distributeurs : boissons à acheter mises à jour (%d machine(s))", len(changes))
        else:
            async with self.s.pont.transaction():
                await self.s.boite.entete_arret()
                for off, octets in bp.ecritures_distributeurs(entrees, self.base):
                    await self.s.pont.ecrire(bp.ZONE + off, octets)
            n = sum(bin(e[16]).count("1") for e in entrees)
            self.s.log.info("Table des distributeurs écrite : %d machine(s), %d boisson(s) à acheter", len(entrees), n)
        self._ecrite = (*cle, tuple(entrees))

    # ------------------------------------------------------------------ journal
    def evenement(self, e, checks: list[int], montrees: set[int]) -> None:
        """Évènements DISTRIBUTEUR (achat : location ajoutée à `checks`, contenu montré par la fenêtre du jeu) et
        DISTRIBUTEUR_VU (indices). La location est vérifiée contre la machine et la boisson de l'évènement."""
        if e.type == bp.EVT_DISTRIBUTEUR:
            loc = e.etiquette
            x = self.locs.get(loc)
            m = self._machine(loc)
            if x is None or m is None or (bp.crc_carte(m.carte), m.point, x["boisson"]) != (e.id, e.valeur, e.index):
                self.s.log.warning("Distributeurs : achat d'une machine inconnue (carte %#x, point %#x, boisson %d, "
                                   "location %d) : ignoré", e.id, e.valeur, e.index, loc)
                return
            self.achetes.add(loc)
            montrees.add(loc)
            checks.append(loc)
        elif e.type == bp.EVT_DISTRIBUTEUR_VU:
            m = next((m for m in self.machines if (bp.crc_carte(m.carte), m.point) == (e.id, e.valeur)), None)
            if m is not None:
                self._vues += [loc for i, loc in enumerate(m.locations) if loc is not None and e.index >> i & 1]

    def indiquer_vues(self) -> None:
        """Après les checks du tour (un achat lu dans la même lecture du journal part en check, pas en indice)."""
        vues, self._vues = self._vues, []
        if vues:
            self._indiquer(vues)

    def _machine(self, loc: int) -> Machine | None:
        x = self.locs.get(loc)
        if x is None:
            return None
        return next((m for m in self.machines if (m.carte, m.rang) == (x["carte"], x["rang"])), None)

    def _indiquer(self, locs: list[int]) -> None:
        """Indices « annoncés » (LocationScouts `create_as_hint` 2) des boissons Archipelago montrées, une fois par
        location (comme les boutiques, `archipelago_boutiques.md` §10)."""
        s, r = self.s, self.s.reseau
        if r is None or r.slot is None or not s._connexion_prete or s.sauvegarde != "liee":
            return
        cle = (str(r.room_info.get("seed_name", "")), int(r.slot))
        deja = set()
        for h in r.indices:
            with contextlib.suppress(KeyError, TypeError, ValueError):
                if int(h.get("finding_player", -1)) == r.slot:
                    deja.add(int(h["location"]))
        a_indiquer = sorted(loc for loc in locs if loc in r.locations_manquantes and not self._fait(loc)
                            and loc not in deja and (*cle, loc) not in self._indices)
        if not a_indiquer:
            return
        self._indices |= {(*cle, loc) for loc in a_indiquer}
        s._lancer(self._envoyer_indices(r, cle, a_indiquer))

    async def _envoyer_indices(self, r, cle, locs) -> None:
        try:
            await r.scouter(locs, create_as_hint=2)
        except Exception as e:                               # déconnexion : redemandés à la prochaine ouverture
            self._indices -= {(*cle, loc) for loc in locs}
            self.s.log.info("Indices du distributeur non créés : %s", e)
            return
        self.s.log.info("Indices du distributeur : %s", locs)
