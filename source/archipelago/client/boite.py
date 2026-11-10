"""Accès typé à la boîte aux lettres Archipelago (protocole v2, docs/systemes/archipelago_boite.md), par le
pont GDB persistant (`gdb.PontGdb`). Bibliothèque standard seulement.

Règles du protocole respectées ici (§7) :
- le client n'écrit que les champs « C » ;
- toute écriture se fait jeu arrêté (`PontGdb.transaction()`, arrêt confirmé), et le mot de validation
  (`numero` d'un don ou d'une notification, `coffres_nombre`, `journal_lu`) est écrit EN DERNIER, dans un
  paquet séparé ;
- une entrée de don de numéro > compteur n'est jamais réécrite avec un AUTRE contenu (elle peut être en
  cours de traitement) ; une notification de numéro > notifs_affichees n'est jamais réécrite ;
- la boîte est reconnue par son magic « YKAP » ; rien n'est écrit sans lui.

Les versions ≥ 3 de la boîte (J2) sont des extensions compatibles : elles sont acceptées, les champs
inconnus sont ignorés.
"""
from __future__ import annotations

import dataclasses
import struct
from dataclasses import dataclass, field
from typing import Iterable, Sequence

try:                                        # paquet (archipelago.client) ou dossier sur sys.path
    from . import boite_protocole as bp
    from .gdb import TAILLE_BLOC, AccesRefuse, PontGdb
except ImportError:                          # pragma: no cover - selon le mode d'import
    import boite_protocole as bp            # type: ignore[no-redef]
    from gdb import TAILLE_BLOC, AccesRefuse, PontGdb    # type: ignore[no-redef]

VERSION_MIN = 1


class BoiteAbsente(Exception):
    """Magic absent à 0x0091C000 : build sans le mod (--define YKW2_AP), ou jeu pas encore à sa 1re image."""


class FilePleine(Exception):
    """File de notifications pleine (8 en attente) : réessayer plus tard."""


# ---------------------------------------------------------------------------------------------- types
Entete = dataclasses.make_dataclass("Entete", [(n, int) for n, _, _ in bp.ENTETE], frozen=True)
Entete.__doc__ = "En-tête de la boîte (champs de boite_protocole.ENTETE, §3 de la doc)."
Entete.partie = property(lambda s: bool(s.etat & bp.ETAT_PARTIE))
Entete.terrain = property(lambda s: bool(s.etat & bp.ETAT_TERRAIN))
Entete.stable = property(lambda s: bool(s.etat & bp.ETAT_STABLE))
Entete.bloque = property(lambda s: bool(s.etat & bp.ETAT_BLOQUE))
Entete.attente = property(lambda s: bool(s.etat & bp.ETAT_ATTENTE))
Entete.en_pause = property(lambda s: bool(s.etat & bp.ETAT_PAUSE))
Entete.notifications = property(lambda s: s.version >= 2)
# lieu du joueur (§29) : None (jeu qui ne le publie pas), sinon (hachage de la carte, (x, z) ou None)
Entete.lieu = property(lambda s: bp.lieu_publie(s.etat, s.carte, s.pos_x, s.pos_z))


@dataclass(frozen=True)
class Don:
    numero: int
    type: int
    hash: int
    quantite: int

    def encoder(self) -> bytes:
        return bp.enc_don(self.numero, self.type, self.hash, self.quantite)


@dataclass(frozen=True)
class ObjetADonner:
    """Contenu d'un don (sans numéro) : type (DON_OBJET / DON_ARGENT / DON_YOKAI), hachage, quantité
    (argent : centimes)."""
    type: int
    hash: int = 0
    quantite: int = 1


@dataclass(frozen=True)
class Evenement:
    numero: int
    type: int
    drapeaux: int
    quantite: int
    id: int
    valeur: int
    valeur2: int
    etiquette: int
    index: int
    image: int

    @property
    def nom_type(self) -> str:
        return bp.EVTS.get(self.type, f"?{self.type}")

    @property
    def index_tbox(self) -> int | None:
        """COFFRE : index du flag TBox (bit de P+0x3C4), None si inconnu."""
        return None if self.type != bp.EVT_COFFRE or self.index == bp.INDEX_INCONNU else self.index

    @property
    def quantite_don(self) -> int:
        """DON / DON_ECHEC : quantité complète (s32, négative possible pour l'argent)."""
        return struct.unpack("<i", struct.pack("<I", self.valeur2 & 0xFFFFFFFF))[0]

    def texte(self) -> str:
        return bp.texte_evt(dataclasses.asdict(self))


@dataclass(frozen=True)
class EntreeCoffre:
    """Entrée de la table de remplacement des coffres (§5)."""
    tbox: int
    objet: int = 0
    quantite: int = 0
    drapeaux: int = 0
    etiquette: int = 0
    utilisations: int = 0          # écrit par le jeu (ignoré à l'écriture)

    def encoder(self) -> bytes:
        return bp.enc_coffre(self.tbox, self.objet, self.quantite, self.drapeaux, self.etiquette, 0)


@dataclass(frozen=True)
class Notification:
    numero: int
    duree: int
    drapeaux: int
    texte: bytes


@dataclass
class LectureJournal:
    evenements: list[Evenement] = field(default_factory=list)
    perdus: int = 0                # évènements écrasés avant lecture (resynchroniser sur l'état)
    ecrit: int = 0                 # valeur de journal_ecrit à acquitter


@dataclass
class DepotDons:
    ecrits: list[int] = field(default_factory=list)       # numéros (ré)écrits
    deja_presents: int = 0                                # entrées déjà identiques
    conflits: list[int] = field(default_factory=list)     # numéros en attente avec un autre contenu (non touchés)
    compteur: int = 0


# ---------------------------------------------------------------------------------------------- boîte
class Boite:
    """Boîte aux lettres vue par le client. Les méthodes d'écriture ouvrent elles-mêmes une transaction
    (jeu arrêté) si l'appelant n'en a pas déjà une ; plusieurs opérations peuvent être groupées dans un
    même arrêt avec `async with boite.gdb.transaction(): ...`."""

    def __init__(self, gdb: PontGdb):
        self.gdb = gdb
        self._session = -1
        self._images = -1
        self._entete_arret: tuple[int, int, Entete] | None = None   # (session, n° d'arrêt, en-tête lu pendant cet arrêt)
        self.octets_boutiques = b""       # v9 : octets des bits de boutique de la dernière `partie_groupee(boutiques=True)`

    async def entete_arret(self) -> Entete:
        """En-tête (magic vérifié) jeu ARRÊTÉ : lu une fois par arrêt, puis resservi tant que le jeu reste arrêté (le jeu
        ne peut rien y changer ; seuls ses champs J sont utilisés par les appelants, jamais un champ C que ce même arrêt
        vient d'écrire). Jeu en marche : lecture normale."""
        g = self.gdb
        cle = (g.sessions, g.numero_arret)
        if not g.en_marche and self._entete_arret is not None and self._entete_arret[:2] == cle:
            return self._entete_arret[2]
        h = await self.entete()
        if not g.en_marche:
            self._entete_arret = (*cle, h)
        return h

    async def lire_plages(self, plages: Iterable[tuple[int, int]]) -> dict[tuple[int, int], bytes]:
        """Lit plusieurs plages `(adresse, taille)` en regroupant deux plages voisines quand la plage fusionnée tient dans
        un paquet (`gdb.TAILLE_BLOC`, 0x400 octets) : moins de paquets, sans paquet plus gros que ceux du stub. Renvoie
        {plage demandée: octets}."""
        voulues = sorted({(int(a), int(n)) for a, n in plages if n > 0})
        groupes: list[list[int]] = []                        # [début, fin]
        for a, n in voulues:
            if groupes and max(groupes[-1][1], a + n) - groupes[-1][0] <= TAILLE_BLOC:
                groupes[-1][1] = max(groupes[-1][1], a + n)
            else:
                groupes.append([a, a + n])
        lus = [(g0, await self.gdb.lire(g0, g1 - g0)) for g0, g1 in groupes]
        out = {}
        for a, n in voulues:
            for g0, b in lus:
                if g0 <= a and a + n <= g0 + len(b):
                    out[(a, n)] = b[a - g0:a - g0 + n]
                    break
        return out

    # -------------------------------------------------------------- lecture de l'en-tête
    async def entete(self) -> Entete:
        b = await self.gdb.lire(bp.ZONE, bp.TAILLE_ENTETE)
        h = bp.lire_entete(b)
        if h["magic"] != bp.MAGIC:
            raise BoiteAbsente(f"magic {h['magic']:#010x} à {bp.ZONE:#x} (build sans YKW2_AP, ou jeu pas encore "
                               "démarré)")
        if h["version"] < VERSION_MIN:
            raise BoiteAbsente(f"version de boîte {h['version']} inconnue")
        return Entete(**h)

    async def detecter(self) -> Entete | None:
        """En-tête, ou None si la boîte n'est pas (encore) là (magic absent, mémoire pas montée)."""
        try:
            return await self.entete()
        except (BoiteAbsente, AccesRefuse):
            return None

    def nouvelle_instance(self, h: Entete) -> bool:
        """Vrai si cet en-tête vient d'une instance du jeu que ce client n'a pas encore préparée : première
        lecture, nouvelle session GDB, ou `images` qui repart en arrière (jeu relancé). Il faut alors
        réécrire la table des coffres, la politique, ident_partie (§5 limite 4, CONCEPTION §8.1 point 2)."""
        nouveau = self.gdb.sessions != self._session or h.images < self._images
        self._session, self._images = self.gdb.sessions, h.images
        return nouveau

    # -------------------------------------------------------------- configuration (champs C)
    async def _ecrire_champ(self, nom: str, valeur: int) -> None:
        adr, donnees = bp.champ(nom, valeur & 0xFFFFFFFF)
        await self.gdb.ecrire(adr, donnees)

    async def configurer(self, *, ident_partie: int | None = None, politique: int | None = None,
                         pause: bool | None = None, notif_duree_auto: int | None = None,
                         notif_langue: int | None = None) -> None:
        """Écrit les champs de configuration donnés (les autres restent tels quels)."""
        valeurs = {"ident_partie": ident_partie, "politique": politique,
                   "pause": None if pause is None else int(bool(pause)),
                   "notif_duree_auto": notif_duree_auto, "notif_langue": notif_langue}
        async with self.gdb.transaction():
            await self.entete_arret()
            for nom, v in valeurs.items():
                if v is not None:
                    await self._ecrire_champ(nom, v)

    async def demander_liaison(self, terrain: int, cle: int) -> int:
        """v4 (§11.2) : demande au jeu de lier la sauvegarde chargée (identifiant `ident_partie` en P+0x3BC, `cle`
        en P+0x3B6) au terrain stable, si elle est encore au passage sur le terrain `terrain` et sans identifiant.
        Écrit le terrain, la clé, puis le numéro de demande EN DERNIER ; renvoie ce numéro."""
        async with self.gdb.transaction():
            h = await self.entete()
            n = (h.liaison_demande + 1) & 0xFFFFFFFF or 1
            await self._ecrire_champ("liaison_terrain", terrain)
            await self._ecrire_champ("liaison_cle", cle & 0xFFFF)
            await self._ecrire_champ("liaison_demande", n)
            return n

    async def battement(self, valeur: int) -> None:
        """client_images : battement de cœur libre du client (ignoré par le jeu)."""
        async with self.gdb.transaction():
            await self._ecrire_champ("client_images", valeur)

    # -------------------------------------------------------------- dons (§4)
    async def lire_dons(self) -> list[Don]:
        b = await self.gdb.lire(bp.ZONE + bp.OFF_DONS, bp.CAP_DONS * bp.TAILLE_DON)
        return [Don(**bp.dec_don(b[i * 16:i * 16 + 16])) for i in range(bp.CAP_DONS)]

    async def lire_dons_rangs(self, debut: int, fin: int) -> dict[int, Don]:
        """Entrées de la file pour les rangs debut..fin (au plus 128, au plus deux lectures : file circulaire)."""
        rangs = list(range(debut, fin + 1))[:bp.CAP_DONS]
        out: dict[int, Don] = {}
        i = 0
        while i < len(rangs):
            k = min(len(rangs) - i, bp.CAP_DONS - rangs[i] % bp.CAP_DONS)
            b = await self.gdb.lire(bp.adr_don(rangs[i]), k * bp.TAILLE_DON)
            for j in range(k):
                out[rangs[i + j]] = Don(**bp.dec_don(b[j * 16:j * 16 + 16]))
            i += k
        return out

    @staticmethod
    def _dons_a_ecrire(objets: Sequence[ObjetADonner], compteur: int, file: dict[int, Don],
                       res: DepotDons) -> list[Don]:
        a_ecrire = []
        for n in range(compteur + 1, min(len(objets), compteur + bp.CAP_DONS) + 1):
            o = objets[n - 1]
            voulu = Don(n, o.type, o.hash & 0xFFFFFFFF, o.quantite)
            actuel = file[n]
            if actuel == voulu:
                res.deja_presents += 1
            elif actuel.numero == n:
                res.conflits.append(n)
            else:
                a_ecrire.append(voulu)
        return a_ecrire

    async def deposer_dons(self, objets: Sequence[ObjetADonner], h: Entete | None = None) -> DepotDons:
        """Dépose les objets reçus d'AP : `objets[k]` est l'objet de rang k+1 (index AP k). Seuls les rangs
        compteur < n ≤ compteur+128 sont écrits (le compteur est relu jeu arrêté) ; une entrée déjà identique
        n'est pas réécrite ; une entrée en attente au contenu différent n'est jamais touchée (conflit).
        Avec `h` (en-tête lu ce tour, jeu en marche) : pré-vérification SANS arrêt des rangs à écrire (seul le client
        écrit ces entrées : ce qui est lu jeu en marche est exact) ; rien à écrire -> aucun arrêt du jeu."""
        res = DepotDons()
        if h is not None and self.gdb.en_marche:
            fin = min(len(objets), h.compteur + bp.CAP_DONS)
            res.compteur = h.compteur
            if fin <= h.compteur:
                return res
            if not self._dons_a_ecrire(objets, h.compteur, await self.lire_dons_rangs(h.compteur + 1, fin), res):
                return res                                   # tout est déjà là (ou en conflit) : aucun arrêt
            res = DepotDons()
        async with self.gdb.transaction():
            h = await self.entete_arret()
            res.compteur = h.compteur
            fin = min(len(objets), h.compteur + bp.CAP_DONS)
            if fin <= h.compteur:
                return res
            file = await self.lire_dons_rangs(h.compteur + 1, fin)
            for voulu in self._dons_a_ecrire(objets, h.compteur, file, res):
                n = voulu.numero
                e = voulu.encoder()
                adr = bp.adr_don(n)
                await self.gdb.ecrire(adr + 4, e[4:])          # contenu d'abord
                await self.gdb.ecrire(adr, e[:4])              # numéro en dernier (validation)
                res.ecrits.append(n)
        return res

    # -------------------------------------------------------------- journal (§6)
    async def lire_journal(self, h: Entete | None = None, lu: int | None = None) -> LectureJournal:
        """Évènements lu+1 .. journal_ecrit (sans les acquitter : voir `acquitter_journal`). `lu` : index de lecture du
        client s'il est en avance sur `journal_lu` (acquittement différé), sinon `journal_lu` de l'en-tête."""
        h = h or await self.entete()
        ecrit, lu = h.journal_ecrit, max(h.journal_lu, lu or 0)
        res = LectureJournal(ecrit=ecrit)
        if ecrit <= lu:
            return res
        if ecrit - lu > bp.CAP_JOURNAL:
            res.perdus = ecrit - lu - bp.CAP_JOURNAL
            lu = ecrit - bp.CAP_JOURNAL
        # lecture groupée : au plus deux plages contiguës (tampon circulaire)
        numeros = list(range(lu + 1, ecrit + 1))
        brut: dict[int, bytes] = {}
        debut = 0
        while debut < len(numeros):
            i0 = (numeros[debut] - 1) % bp.CAP_JOURNAL
            k = min(len(numeros) - debut, bp.CAP_JOURNAL - i0)
            b = await self.gdb.lire(bp.adr_evt(numeros[debut]), k * bp.TAILLE_EVT)
            for j in range(k):
                brut[numeros[debut + j]] = b[j * 32:j * 32 + 32]
            debut += k
        for n in numeros:
            e = Evenement(**bp.dec_evt(brut[n]))
            if e.numero != n:          # écrasé, ou en cours d'écriture
                res.perdus += 1
                continue
            res.evenements.append(e)
        return res

    async def acquitter_journal(self, ecrit: int) -> None:
        async with self.gdb.transaction():
            await self._ecrire_champ("journal_lu", ecrit)

    # -------------------------------------------------------------- table des coffres (§5)
    async def lire_table_coffres(self, h: Entete | None = None) -> list[EntreeCoffre]:
        h = h or await self.entete()
        n = min(h.coffres_nombre, bp.CAP_COFFRES)
        if not n:
            return []
        b = await self.gdb.lire(bp.ZONE + bp.OFF_COFFRES, n * bp.TAILLE_COFFRE)
        return [EntreeCoffre(**bp.dec_coffre(b[i * 16:i * 16 + 16])) for i in range(n)]

    async def ecrire_table_coffres(self, entrees: Sequence[EntreeCoffre]) -> None:
        """Remplace toute la table (jeu arrêté) : entrées, puis coffres_nombre en dernier."""
        if len(entrees) > bp.CAP_COFFRES:
            raise ValueError(f"{len(entrees)} entrées de coffre (capacité {bp.CAP_COFFRES})")
        if len({e.tbox for e in entrees}) != len(entrees) or any(e.tbox == 0 for e in entrees):
            raise ValueError("table des coffres : hachage TBox nul ou en double")
        async with self.gdb.transaction():
            await self.entete_arret()
            if entrees:
                await self.gdb.ecrire(bp.ZONE + bp.OFF_COFFRES, b"".join(e.encoder() for e in entrees))
            await self._ecrire_champ("coffres_nombre", len(entrees))

    # -------------------------------------------------------------- notifications (§6bis)
    async def deposer_notification(self, texte: str | bytes, duree: int = 0, balises: bool = False) -> int:
        """Dépose un texte (UTF-8, une ligne, 55 octets au plus : coupé sans casser de caractère) dans la
        file du client. Renvoie son numéro ; FilePleine si 8 notifications sont déjà en attente. Pour
        préparer un texte au bandeau (largeur, provenance), voir `boite_protocole.formater_notif`."""
        b = bp.texte_utf8(texte) if isinstance(texte, str) else bp.texte_utf8(texte.decode("utf-8", "replace"))
        async with self.gdb.transaction():
            h = await self.entete_arret()
            if not h.notifications:
                raise BoiteAbsente("boîte v1 : pas de notifications")
            base = h.notifs_affichees
            file = await self.lire_notifications()
            en_attente = {x.numero for x in file if x.numero > base}
            numero = base + 1
            while numero in en_attente:
                numero += 1
            if numero - base > bp.CAP_NOTIFS:
                raise FilePleine(f"{bp.CAP_NOTIFS} notifications en attente")
            e = bp.enc_notif(numero, b, duree & 0xFFFF, bp.NOTIF_BALISES if balises else 0)
            adr = bp.adr_notif(numero)
            await self.gdb.ecrire(adr + 4, e[4:])
            await self.gdb.ecrire(adr, e[:4])
            return numero

    async def deposer_notifications(self, textes: Sequence[str], h: Entete | None = None) -> int:
        """Dépose plusieurs textes dans la file du client en UN arrêt ; renvoie le nombre déposé (les premiers de
        `textes`, dans l'ordre ; 0 si la file est pleine). Avec `h` (en-tête lu ce tour, jeu en marche), les places
        libres sont comptées SANS arrêt (seul le client écrit ces entrées, et `notifs_affichees` ne fait qu'augmenter :
        une place vue libre le reste) ; file pleine -> aucun arrêt. `notifs_affichees` est relu jeu arrêté."""
        if not textes:
            return 0
        file = None
        if h is not None and self.gdb.en_marche:
            if not h.notifications:
                raise BoiteAbsente("boîte v1 : pas de notifications")
            file = await self.lire_notifications()
            if len({x.numero for x in file if x.numero > h.notifs_affichees}) >= bp.CAP_NOTIFS:
                return 0
        async with self.gdb.transaction():
            h = await self.entete_arret()
            if not h.notifications:
                raise BoiteAbsente("boîte v1 : pas de notifications")
            if file is None:
                file = await self.lire_notifications()
            base = h.notifs_affichees
            en_attente = {x.numero for x in file if x.numero > base}
            numero, n = base, 0
            for texte in textes:
                numero += 1
                while numero in en_attente:
                    numero += 1
                if numero - base > bp.CAP_NOTIFS:
                    break
                e = bp.enc_notif(numero, bp.texte_utf8(texte), 0, 0)
                adr = bp.adr_notif(numero)
                await self.gdb.ecrire(adr + 4, e[4:])
                await self.gdb.ecrire(adr, e[:4])
                n += 1
            return n

    async def lire_notifications(self) -> list[Notification]:
        b = await self.gdb.lire(bp.ZONE + bp.OFF_NOTIFS, bp.CAP_NOTIFS * bp.TAILLE_NOTIF)
        t = bp.TAILLE_NOTIF
        return [Notification(**bp.dec_notif(b[i * t:(i + 1) * t])) for i in range(bp.CAP_NOTIFS)]

    async def texte_affiche(self) -> str:
        """Tampon du texte affiché (ou dernier affiché) par le jeu."""
        b = await self.gdb.lire(bp.ZONE + bp.OFF_NOTIF_TAMPON, bp.TAILLE_TAMPON)
        return b.split(b"\0")[0].decode("utf-8", "replace")

    # -------------------------------------------------------------- état de la partie (hors boîte)
    async def lire_flags_tbox(self, h: Entete) -> bytes | None:
        """Les 0x48 octets des flags TBox (P+0x3C4) de la partie chargée, ou None sans partie."""
        if not h.partie or not h.adresse_p:
            return None
        return await self.gdb.lire(h.adresse_p + bp.P_FLAGS_TBOX, bp.TAILLE_FLAGS_TBOX)

    async def coffres_ouverts(self, h: Entete) -> set[int] | None:
        """Index TBox dont le flag vaut 1 (resynchronisation des checks, CONCEPTION §3.1), None sans partie."""
        b = await self.lire_flags_tbox(h)
        return None if b is None else bits_poses(b)

    async def flags_globaux_poses(self, h: Entete, flags: Iterable[int]) -> set[int] | None:
        """Parmi `flags` (index de flags bit globaux), ceux qui valent 1 dans la partie chargée ; None sans partie.
        Une seule lecture : les octets P + 4 + min // 8 .. P + 4 + max // 8 (boss d'histoire : 22 octets)."""
        voulus = sorted({int(f) for f in flags if 0 <= int(f) <= bp.FLAG_GLOBAL_MAX})
        if not h.partie or not h.adresse_p:
            return None
        if not voulus:
            return set()
        premier, dernier = voulus[0] // 8, voulus[-1] // 8
        b = await self.gdb.lire(h.adresse_p + bp.P_FLAGS_GLOBAUX + premier, dernier - premier + 1)
        return {f for f in voulus if b[f // 8 - premier] >> (f % 8) & 1}

    async def bits_partie(self, h: Entete, flags: Iterable[int]) -> tuple[set[int], set[int]] | None:
        """(index TBox posés, parmi `flags` les flags bit globaux posés) de la partie chargée, None sans partie : même
        résultat que `coffres_ouverts` + `flags_globaux_poses`, en regroupant les deux plages de P dans un seul paquet
        quand elles y tiennent (`lire_plages`)."""
        lu = await self.partie_groupee(h, flags)
        return None if lu is None else (lu[0], lu[1])

    async def partie_groupee(self, h: Entete, flags: Iterable[int], criminels: bool = False,
                             boutiques: bool = False) -> tuple[set[int], set[int], bytes] | None:
        """Comme `bits_partie`, plus (si `criminels`) les NB_CRIMINELS octets `wantedNN` (P + 0x2D1 ..) dans le même
        regroupement (P + 0x2D1 .. P + 0x40B : un seul paquet avec les flags et la TBox) ; b"" sinon. `boutiques` : les
        octets des bits de boutique (P + 0x14E .. P + 0x3AC, v9) sont lus dans le même regroupement et renvoyés par
        `octets_boutiques` (dernier résultat de cette lecture)."""
        self.octets_boutiques = b""
        if not h.partie or not h.adresse_p:
            return None
        voulus = sorted({int(f) for f in flags if 0 <= int(f) <= bp.FLAG_GLOBAL_MAX})
        tbox = (h.adresse_p + bp.P_FLAGS_TBOX, bp.TAILLE_FLAGS_TBOX)
        plages = [tbox]
        if voulus:
            premier, dernier = voulus[0] // 8, voulus[-1] // 8
            fl = (h.adresse_p + bp.P_FLAGS_GLOBAUX + premier, dernier - premier + 1)
            plages.append(fl)
        cr = (h.adresse_p + bp.P_CRIMINELS + 1, bp.NB_CRIMINELS)
        if criminels:
            plages.append(cr)
        off, n = bp.plage_octets_boutiques()
        bt = (h.adresse_p + off, n)
        if boutiques:
            plages.append(bt)
        lu = await self.lire_plages(plages)
        if boutiques:
            self.octets_boutiques = lu[bt]
        poses = {f for f in voulus if lu[fl][f // 8 - premier] >> (f % 8) & 1} if voulus else set()
        return bits_poses(lu[tbox]), poses, (lu[cr] if criminels else b"")

    async def adresse_quetes(self) -> int | None:
        """Q = *(*0x00815244 + 0x10), bloc des phases de quête (hors boîte, deux lectures) ; None si un maillon
        est nul ou hors du tas (jeu pas encore initialisé)."""
        s = struct.unpack("<I", await self.gdb.lire(bp.ADR_SINGLETON_QUETES, 4))[0]
        if not adresse_tas(s):
            return None
        q = struct.unpack("<I", await self.gdb.lire(s + bp.OFF_OBJET_SINGLETON, 4))[0]
        return q if adresse_tas(q) else None

    async def adresse_rang(self) -> int | None:
        """O = *(*0x0081521C + 0x10), objet qui porte le rang de montre réel (hors boîte, deux lectures) ; None si un
        maillon est nul ou hors du tas."""
        s = struct.unpack("<I", await self.gdb.lire(bp.ADR_SINGLETON_RANG, 4))[0]
        if not adresse_tas(s):
            return None
        o = struct.unpack("<I", await self.gdb.lire(s + bp.OFF_OBJET_SINGLETON, 4))[0]
        return o if adresse_tas(o) else None

    async def rang_montre(self, adresse: int | None = None) -> tuple[int, int] | tuple[None, None]:
        """(O, rang de montre réel 0..5) de la partie chargée, ou (None, None) (objet absent, valeur hors bornes).
        L'appelant relit l'en-tête (et `adresse_rang()`) APRÈS : valeur écartée si la partie a changé. `adresse` : O
        validé par une relecture précédente (le chaînage n'est alors relu qu'après, pour la validation)."""
        o = adresse if adresse is not None else await self.adresse_rang()
        if o is None:
            return None, None
        r = (await self.gdb.lire(o + bp.OFF_RANG_MONTRE, 1))[0]
        return (o, r) if r <= bp.RANG_MONTRE_MAX else (None, None)

    async def quetes_terminees(self, h: Entete, quetes: Iterable[int],
                               adresse: int | None = None) -> tuple[int, set[int]] | None:
        """(Q, parmi `quetes` celles dont la phase vaut 255) dans la partie chargée ; None sans partie ou sans Q.
        Une seule lecture des phases : Q + 4 + min .. Q + 4 + max (boss de quête 7..80 : 74 octets). L'appelant
        relit `adresse_quetes()` APRÈS (même règle que l'en-tête : données écartées si Q a changé). `adresse` : Q
        validé par une relecture précédente (le chaînage n'est alors relu qu'après : deux lectures de moins)."""
        # pseudo-numéros « quête arrivée à la phase N » (bp.quete_phase_pseudo : Documents perdus, Cartes d'Ultramax) :
        # même lecture, la phase de leur quête
        demandees = {int(n) for n in quetes}
        reelles = {n: ((bp.quete_phase_decode(n) or (n, 0))[0]) for n in demandees}
        demandees = {n for n in demandees if 0 <= reelles[n] < bp.NB_QUETES and (n < bp.NB_QUETES or n >= bp.QUETE_PHASE_BASE)}
        voulues = sorted({reelles[n] for n in demandees})
        if not h.partie:
            return None
        if not voulues:
            return 0, set()
        q = adresse if adresse is not None else await self.adresse_quetes()
        if q is None:
            return None
        premier, dernier = voulues[0], voulues[-1]
        b = await self.gdb.lire(q + bp.Q_PHASES + premier, dernier - premier + 1)
        return q, {n for n in demandees if bp.quete_atteinte(n, b[reelles[n] - premier])}


def adresse_tas(a: int) -> bool:
    """Pointeur plausible vers un objet du jeu (tas ou tas linéaire, aligné sur 4)."""
    return bp.ADR_TAS_MIN <= a < bp.ADR_TAS_MAX and not a & 3


def bits_poses(b: bytes) -> set[int]:
    """Index des bits à 1 (bit i de l'octet i // 8, petit-boutiste comme les mots de FUN_00412f08)."""
    return {8 * k + i for k, octet in enumerate(b) for i in range(8) if octet >> i & 1}


def objets_depuis(liste: Iterable[tuple[int, int, int]]) -> list[ObjetADonner]:
    """Petit utilitaire : [(type, hash, quantite), …] -> [ObjetADonner, …]."""
    return [ObjetADonner(t, h, q) for t, h, q in liste]
