# -*- coding: utf-8 -*-
"""
Archipelago client for Yo-kai Watch 2: Psychic Specters.

Text client + pont mémoire GDB vers Azahar/Citra :
  * `/citra [port]` attache le client au stub GDB de l'émulateur
    (Émulation > Configurer > Debug > « Enable GDB stub », port 24689).
  * Dès que memory_map.py contient des adresses (voir
    docs/memory_map_fr.md et tools/memory_scan.py), le client lit
    périodiquement les drapeaux du jeu et envoie les checks tout seul.
  * Tant que la carte mémoire est vide, le client reste utilisable en mode
    texte (checks manuels).

Sur 3DS moddée, le débogueur Rosalina expose le même protocole GDB : pointez
`/citra <port>` vers l'IP de la console.
"""

import asyncio
import json
import os
import pkgutil
import random
import re
import struct
from typing import Dict, List, Optional

import Utils
from CommonClient import (
    ClientCommandProcessor,
    CommonContext,
    get_base_parser,
    gui_enabled,
    logger,
    server_loop,
)
from NetUtils import ClientStatus

from . import mod_patcher
from .constants import (
    CITRA_GDB_PORT,
    CRIMINEL_MILESTONES,
    GAME_NAME,
    PROGRESSIVE_RANK_ITEM,
    RANK_ITEM_NAMES,
)
from .items import (
    DEFAULT_INVENTORY_TYPE,
    FILLER_WEIGHTS,
    ITEM_GAME_HASH,
    ITEM_GAME_TYPE,
    ITEM_NAME_TO_ID,
    KEY_ITEM_GAME,
    NATIVE_CHEST_ITEM_BY_LOCATION,
)

# Consommables filler (pour livrer une quantité aléatoire 1-3, comme un coffre).
FILLER_ITEM_NAMES = {name for name, _weight in FILLER_WEIGHTS}
from .locations import (LOCATION_NAME_TO_ID, RANK_QUEST_NAMES, STORY_LOCATIONS,
                        native_key_check_name)
from .memory_map import (
    BATTLE_HP_CUR_OFFSET,
    BATTLE_HP_ENTRY_STRIDE,
    BATTLE_HP_FIRST_ADDR,
    BATTLE_STATE_ADDR,
    CHEST_BIT_TO_LOCATION,
    FLAG_TABLES,
    INVENTORY_BASE,
    INVENTORY_COUNT_ADDR,
    INVENTORY_ENTRY_SIZE,
    INVENTORY_PTR_OFFSET,
    INVENTORY_PTR_VALUE,
    INVENTORY_QTY_OFFSET,
    INVENTORY_SLOT_BITS,
    KEY_ITEM_BASE,
    KEY_ITEM_COUNT_ADDR,
    KEY_ITEM_COUNT2_ADDR,
    KEY_ITEM_DATA_MARK,
    KEY_ITEM_DATA_OFFSET,
    KEY_ITEM_ENTRY_SIZE,
    KEY_ITEM_HASH_OFFSET,
    MEDALLIUM_BIT_TO_LOCATION,
    KEY_ITEM_PTR_VALUE,
    KEY_ITEM_SLOT_BITS,
    LAST_QUEST_DONE_HASH_ADDR,
    MEMORY_REGIONS,
    PARTY_ENTRY_STRIDE,
    PARTY_HP_FIRST_ADDR,
    PARTY_SLOT_COUNT,
    EVENT_CHECK_FLAGS,
    STORY_CHAPTER_ADDR,
    STORY_GATES,
    WANTED_FLAGS_REGION,
    WATCH_RANK_VALUE_ADDR,
    chapters_completed,
    load_quest_hash_names,
    memory_map_ready,
    new_set_bits,
)

# Registre-based neutralisation (Doteos 2026-07-19) : bit de coffre -> hash de
# l'item NATIF (déterministe). On sait EXACTEMENT quoi retirer à l'ouverture d'un
# coffre (fini le diff fragile qui devinait). Construit depuis le registre
# native_chest_items.json + CHEST_BIT_TO_LOCATION + ITEM_GAME_HASH.
CHEST_BIT_TO_NATIVE_HASH: Dict[int, int] = {}
for _bit, _loc in CHEST_BIT_TO_LOCATION.items():
    _it = NATIVE_CHEST_ITEM_BY_LOCATION.get(_loc)
    if _it and _it in ITEM_GAME_HASH:
        CHEST_BIT_TO_NATIVE_HASH[_bit] = ITEM_GAME_HASH[_it]

# item_id Archipelago -> nom d'objet (pour la livraison des items reçus).
ITEM_ID_TO_NAME: Dict[int, str] = {code: name for name, code in ITEM_NAME_TO_ID.items()}

POLL_INTERVAL = 2.0  # secondes entre deux lectures mémoire (compromis lag/réactivité)


# ---------------------------------------------------------------------------
# Client GDB Remote Serial Protocol minimal (Azahar / Citra / Rosalina)
# ---------------------------------------------------------------------------
class GDBStubClient:
    def __init__(self) -> None:
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.running = False  # l'émulation tourne (pas de réponse aux paquets)
        # Mode « lectures sans pause » (perf, Doteos 2026-07-26) : le stub de
        # Citra/Azahar traite les paquets GDB DANS la boucle CPU, donc il peut
        # répondre aux lectures pendant que le jeu TOURNE. Détecté par
        # probe_no_halt() à l'attachement ; si supporté, poll_game ne halte plus
        # l'émulation pour LIRE -> disparition du micro-freeze périodique. Les
        # ÉCRITURES read-modify-write restent sous halt (begin_halt) : atomiques.
        self.no_halt = False
        # Buffer de réception PERSISTANT : les octets reçus APRÈS le premier
        # paquet d'un même segment TCP (ex. T05 parasite coalescé avec la vraie
        # réponse) sont conservés pour l'échange suivant au lieu d'être jetés
        # (revue 2026-07-26 : réponse perdue -> stall 10 s pris pour une
        # déconnexion).
        self._rxbuf = b""
        # Sérialise TOUT accès au flux GDB : deux coroutines qui lisent le même
        # StreamReader en même temps -> « read() called while another coroutine is
        # already waiting » (sonde DeathLink vs poll, reconnexion /citra...).
        # Une transaction complète (interrupt->lectures->cont) prend ce verrou.
        self.io_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self.writer is not None and not self.writer.is_closing()

    async def connect(self, host: str = "localhost",
                      port: int = CITRA_GDB_PORT) -> None:
        self.reader, self.writer = await asyncio.open_connection(host, port)
        self._rxbuf = b""
        # À la connexion le stub halte le CPU (et peut émettre un paquet stop).
        try:
            await asyncio.wait_for(self.reader.read(4096), timeout=0.3)
        except asyncio.TimeoutError:
            pass
        self.running = False
        await self.cont()

    async def close(self) -> None:
        if self.writer:
            # Detach propre ('D') : relâche le stub pour éviter de le bloquer
            # (sinon Azahar refuse les reconnexions et doit être redémarré).
            try:
                self.writer.write(b"$D#44")
                await self.writer.drain()
                await asyncio.wait_for(self.reader.read(64), timeout=0.3)
            except (asyncio.TimeoutError, ConnectionError, OSError):
                pass
            self.writer.close()
            self.writer = None
            self.reader = None
            self.running = False
            self.no_halt = False    # re-sondé à la prochaine connexion

    @staticmethod
    def _checksum(payload: bytes) -> bytes:
        return b"%02x" % (sum(payload) % 256)

    async def _read_packet(self) -> str:
        assert self.reader and self.writer
        buffer = self._rxbuf
        while True:
            start = buffer.find(b"$")
            end = buffer.find(b"#", start)
            if start != -1 and end != -1 and len(buffer) >= end + 3:
                self._rxbuf = buffer[end + 3:]   # reste conservé (paquet suivant)
                self.writer.write(b"+")
                await self.writer.drain()
                return buffer[start + 1:end].decode()
            chunk = await asyncio.wait_for(self.reader.read(65536), timeout=10)
            if not chunk:
                raise ConnectionError("stub GDB déconnecté")
            buffer += chunk

    async def _exchange(self, payload: str) -> str:
        assert self.writer
        raw = payload.encode()
        self.writer.write(b"$" + raw + b"#" + self._checksum(raw))
        await self.writer.drain()
        return await self._read_packet()

    _HEX = set("0123456789abcdefABCDEF")

    async def _drain(self) -> None:
        """Jette tout paquet parasite en attente (stop reply, notification 'O')."""
        assert self.reader
        self._rxbuf = b""    # purge aussi le buffer persistant (resynchronisation)
        while True:
            try:
                data = await asyncio.wait_for(self.reader.read(4096), timeout=0.05)
            except asyncio.TimeoutError:
                return
            if not data:
                return

    async def _exchange_valid(self, payload: str, ok: str = "") -> str:
        """Envoie `payload` et relit jusqu'à une réponse pertinente, en
        ignorant les paquets parasites (notifications asynchrones du stub)."""
        raw = payload.encode()
        self.writer.write(b"$" + raw + b"#" + self._checksum(raw))
        await self.writer.drain()
        reply = ""
        for _ in range(8):
            reply = await self._read_packet()
            if reply.startswith("E") and len(reply) <= 3:
                return reply
            if ok and reply == ok:
                return reply
            if not ok and reply and all(c in self._HEX for c in reply):
                return reply
            # parasite ('O...', 'T05...', 'S05'...) -> on resynchronise
        return reply

    async def cont(self) -> None:
        """Relance l'émulation ('c' ne répond pas tant que ça tourne)."""
        if not self.running and self.writer:
            self.writer.write(b"$c#63")
            await self.writer.drain()
            self.running = True

    async def interrupt(self) -> None:
        """Interrompt l'émulation pour lire/écrire la mémoire."""
        if self.running and self.writer:
            self.writer.write(b"\x03")
            await self.writer.drain()
            try:
                await self._read_packet()  # paquet stop (T05...)
            except asyncio.TimeoutError:
                pass
            self.running = False
        await self._drain()  # jette tout paquet parasite résiduel

    async def begin_halt(self) -> bool:
        """Halte l'émulation pour une TRANSACTION D'ÉCRITURE (mode no_halt) ;
        retourne True si c'est CET appel qui a halté (l'appelant doit alors
        cont() en finally). Si déjà halté (mode classique : poll_game a
        interrompu) -> False, rien à faire."""
        if self.running:
            await self.interrupt()
            return True
        return False

    async def probe_no_halt(self) -> bool:
        """Détecte si le stub répond aux lectures PENDANT que le jeu tourne.

        Le stub GDB de Citra/Azahar appelle HandlePacket dans la boucle CPU ->
        les paquets 'm' sont normalement servis même sans halt. On teste avec
        une vraie lecture sous timeout court. Toute réponse (hex ou E..) prouve
        le support. En cas de silence : on resynchronise le flux (interrupt +
        drain avalent la réponse tardive éventuelle) et on garde le mode halt."""
        await self.cont()
        await self._drain()
        try:
            reply = await asyncio.wait_for(
                self._exchange_valid(f"m{0x086CFA24:x},4"), timeout=1.5)
            # SEULE une réponse de DONNÉES prouve le support : exactement 8
            # caractères hex (4 octets lus). Un stub peut répondre 'E..' (accès
            # mémoire refusé en marche, ex. Rosalina) : activer le mode sur cette
            # base transformerait toutes les lectures du poll en zéros silencieux
            # (read_memory zéro-remplit les 'E..') = détection morte sans erreur.
            # ⚠️ 'E01' est AUSSI tout-hex ('E' ∈ _HEX) -> le test de LONGUEUR est
            # indispensable (revue 2026-07-26).
            self.no_halt = (len(reply) == 8
                            and all(c in self._HEX for c in reply))
        except (asyncio.TimeoutError, ConnectionError, OSError):
            self.no_halt = False
            # resynchronisation : la réponse tardive (si elle arrive au halt)
            # est jetée par interrupt()/_drain() ; puis on relance l'émulation.
            try:
                await self.interrupt()
                await self.cont()
            except (asyncio.TimeoutError, ConnectionError, OSError):
                pass
        return self.no_halt

    async def read_memory(self, address: int, length: int) -> bytes:
        out = bytearray()
        chunk = 0x400  # lectures courtes = stub plus stable
        for offset in range(0, length, chunk):
            size = min(chunk, length - offset)
            reply = await self._exchange_valid(f"m{address + offset:x},{size:x}")
            if reply.startswith("E") and len(reply) <= 3:
                out += b"\x00" * size
            else:
                out += bytes.fromhex(reply)
        return bytes(out)

    async def write_memory(self, address: int, data: bytes) -> None:
        reply = await self._exchange_valid(
            f"M{address:x},{len(data):x}:{data.hex()}", ok="OK")
        if reply != "OK":
            raise ConnectionError(f"écriture GDB refusée à {address:#x}: {reply}")


# ---------------------------------------------------------------------------
# Client Archipelago
# ---------------------------------------------------------------------------
class YKW2CommandProcessor(ClientCommandProcessor):
    def _cmd_citra(self, port: str = "") -> None:
        """Attache le client au stub GDB d'Azahar/Citra (port 24689)."""
        if isinstance(self.ctx, YKW2Context):
            asyncio.create_task(
                self.ctx.attach_emulator(int(port) if port else CITRA_GDB_PORT))

    def _cmd_memstatus(self) -> None:
        """Affiche l'état du pont mémoire (régions configurées)."""
        if isinstance(self.ctx, YKW2Context):
            for name, (addr, size) in MEMORY_REGIONS.items():
                state = f"{addr:#010x} ({size:#x} octets)" if addr else "non trouvée"
                logger.info("  %s : %s", name, state)
            logger.info("Pont mémoire %s ; émulateur %s.",
                        "prêt" if memory_map_ready() else "non configuré",
                        "attaché" if self.ctx.gdb.connected else "non attaché")


def _build_chapter_locations() -> Dict[int, str]:
    """{n -> nom de la location 'Chapitre n : <titre>'} depuis STORY_LOCATIONS."""
    mapping: Dict[int, str] = {}
    for name in STORY_LOCATIONS:
        match = re.match(r"Chapitre (\d+) ", name)
        if match:
            mapping[int(match.group(1))] = name
    return mapping


def _build_quest_hash_locations() -> Dict[int, str]:
    """{hash de quête -> nom de location AP} en croisant quest_hashes.json avec
    les locations existantes (Requête / Service / requête de rang au nom direct).
    Les quêtes sans location (quêtes principales d'histoire) sont ignorées."""
    mapping: Dict[int, str] = {}
    for quest_hash, quest_name in load_quest_hash_names().items():
        for candidate in (f"Requête : {quest_name}",
                          f"Service : {quest_name}", quest_name):
            if candidate in LOCATION_NAME_TO_ID:
                mapping[quest_hash] = candidate
                break
    return mapping


class YKW2Context(CommonContext):
    game = GAME_NAME
    items_handling = 0b111  # objets reçus de toutes les sources
    command_processor = YKW2CommandProcessor

    def __init__(self, server_address, password) -> None:
        super().__init__(server_address, password)
        self.gdb = GDBStubClient()
        self.slot_data: Dict[str, object] = {}
        self.flag_cache: Dict[str, bytes] = {}
        # Mappings de détection non-bitfield (statiques), voir poll_game.
        self.chapter_locations = _build_chapter_locations()
        self.quest_hash_locations = _build_quest_hash_locations()
        self.last_quest_hash: Optional[int] = None
        # location AP -> hash de quête (pour patcher les récompenses en jeu).
        self.quest_loc_to_hash: Dict[int, int] = {}
        for _qh, _loc in self.quest_hash_locations.items():
            _lid = LOCATION_NAME_TO_ID.get(_loc)
            if _lid:
                self.quest_loc_to_hash[_lid] = _qh
        # Paliers de Yo-criminels : nb de captures -> nom de location.
        self.criminel_locations = {
            n: f"Yo-criminels : {n} capture" + ("s" if n > 1 else "")
            for n in CRIMINEL_MILESTONES
        }
        # Rang de montre : valeur du rang (2=C..5=S) -> location « Obtenons le rang X ».
        # Le rang D (1) n'est pas une requête (donné par l'histoire) -> pas de location.
        self.rank_quest_locations: Dict[int, str] = dict(RANK_QUEST_NAMES)
        # Victoire (goal) déjà envoyée au serveur ? (évite le renvoi à chaque poll).
        self._goal_sent: bool = False
        # Anti FAUX-checks sur valeur PÉRIMÉE (nouvelle partie juste après une save
        # avancée : la RAM garde un instant l'ancien rang / chapitre). On ne fire
        # QUE sur un franchissement RÉEL observé en jeu.
        #  * _prev_rank_value : rang du poll précédent (fire rang sur incrément).
        #  * _seen_pre_goal : on a vu chapitre < 11 en jeu (garde-fou anti fausse
        #    victoire si le compteur est périmé à >=11 à la connexion).
        self._prev_rank_value: Optional[int] = None
        self._seen_pre_goal: bool = False
        # BOSS — détection GÉNÉRIQUE de la victoire (Doteos 2026-07-28). Le bit
        # Médallium se pose à la RENCONTRE du boss (check envoyé en plein combat,
        # même en cas de défaite). On s'en sert donc seulement pour ARMER une
        # victoire en attente ; le check ne part qu'à la FIN DU COMBAT sans avoir
        # vu l'écran « Perdu ». Évite de RE le flag propre de chacun des 22 boss.
        #  * _boss_pending  : locations de boss rencontrés, victoire attendue
        #  * _boss_won      : victoires confirmées (re-proposées à chaque poll,
        #                     _queue_check déduplique)
        #  * _boss_lost     : écran « Perdu » vu pendant le combat en cours
        self._prev_medallium: Optional[bytes] = None
        self._prev_battle_state: int = 0
        self._boss_pending: set = set()
        self._boss_won: set = set()
        self._boss_lost: bool = False
        # Livraison des items reçus.
        #  * delivered_count = index des CONSOMMABLES déjà écrits ; persisté par
        #    (seed, slot) dans un fichier, rechargé à la connexion (idempotence
        #    des reconnexions). La 1re passe part de l'existant pour ne pas
        #    ré-empiler les consommables d'une partie en cours.
        #  * _keyitem_done = objets-clés confirmés livrés cette session (évite de
        #    re-scanner en jeu) ; leur vraie idempotence vient du presence-check.
        self.delivered_count: Optional[int] = None
        self._keyitem_done: set = set()
        self._gates_logged: set = set()  # hard-gates déjà loggués (anti-spam)
        self._hard_key_shuffle: bool = False   # shuffle DUR des objets-clés
        # Neutralisation de l'item natif des coffres (design unifié) : à
        # l'ouverture d'un coffre, le jeu ajoute un item natif ; on le retire
        # pour ne garder que l'item AP. On compare l'inventaire RÉEL de ce poll à
        # celui du poll PRÉCÉDENT (pas un modèle cumulé qui dérive), en excluant
        # ce que le CLIENT a livré entre les deux -> le reste = ce que le JEU a
        # ajouté (l'item du coffre). Garde-fou : un coffre donne 1 type d'objet ;
        # si trop de types apparaissent d'un coup, on ne retire RIEN (sécurité
        # anti-suppression massive d'objets légitimes).
        #  * _prev_inv = lecture inventaire du poll précédent {hash: qté}.
        #  * _delivered_this_poll / _delivered_last_poll = livraisons client de ce
        #    poll / du poll précédent (appliquées en jeu entre les 2 lectures).
        self._prev_inv: Optional[Dict[int, int]] = None
        self._delivered_this_poll: Dict[int, int] = {}
        self._delivered_last_poll: Dict[int, int] = {}
        self._NEUTRALIZE_MAX_TYPES = 2   # au-delà = suspect -> on ne retire rien
        # DeathLink (option death_link, adresses RE 2026-07-15/16) :
        #  * _deathlink_pending = morts reçues d'autres joueurs, en attente ;
        #    appliquées sous GDB interrompu (pas dans le callback synchrone
        #    on_deathlink) et consommées seulement APRÈS succès (une erreur
        #    GDB -> retry au cycle suivant).
        #  * _can_send_death = armé quand la roue est VUE vivante en combat
        #    (hors verrou) ; désarmé à chaque envoi et à chaque mort reçue.
        #  * _death_to_send = défaite détectée à transmettre ; flushée dès que
        #    le serveur AP est joignable (pas de mort perdue sur coupure).
        # Détection sur les PV de COMBAT LIVE (struct de combat, adresse
        # stable) : le tableau d'équipe est FIGÉ pendant un combat et
        # réécrit DÉJÀ SOIGNÉ à la défaite -> inutilisable (vérifié live).
        #  * _prev_live_alive = « roue vue vivante EN COMBAT » à la lecture
        #    précédente ; la défaite = transition vivant -> tous à 0 avec
        #    la struct existante (max > 0) et l'état combat != 0.
        #  * _dl_kill_lock = verrou anti-boucle : posé à chaque mort reçue
        #    appliquée, levé quand l'équipe est VUE resoignée HORS combat
        #    (le respawn post-défaite resoigne le tableau -> levée auto
        #    après que la mort reçue a fait son œuvre).
        self._deathlink_pending: List[str] = []
        self._can_send_death: bool = False
        self._death_to_send: bool = False
        self._prev_live_alive: bool = False
        self._dl_kill_lock: bool = False

    # ------------------------------------------------------------------
    def _queue_check(self, location_name: Optional[str],
                     new_checks: List[int]) -> None:
        """Ajoute le check si la location existe, manque encore et n'est pas déjà en file."""
        if not location_name:
            return
        location_id = LOCATION_NAME_TO_ID.get(location_name)
        if (location_id and location_id in self.missing_locations
                and location_id not in new_checks):
            new_checks.append(location_id)
            logger.info("Check : %s", location_name)

    # ------------------------------------------------------------------
    # Livraison des items reçus -> écriture inventaire (recette memory_map)
    # ------------------------------------------------------------------
    async def _deliver_to_inventory(self, item_hash: int, inv_type: int,
                                    amount: int = 1) -> bool:
        """Wrapper transactionnel : halte le temps de la modification (mode
        no_halt) — la fonction relit son état PUIS écrit plusieurs paquets
        dépendants -> doit être atomique face au jeu qui tourne."""
        own = await self.gdb.begin_halt()
        try:
            return await self._deliver_to_inventory_raw(item_hash, inv_type,
                                                        amount)
        finally:
            if own:
                await self.gdb.cont()

    async def _deliver_to_inventory_raw(self, item_hash: int, inv_type: int,
                                        amount: int = 1) -> bool:
        """Ajoute `amount` d'un objet (par son hash) dans l'inventaire.

        Si l'objet est présent -> incrémente sa quantité. Sinon -> crée une
        entrée (chaînage ptr + entrée + compteurs + bit de slot). Voir la
        recette complète dans memory_map (section inventaire).
        Retourne True si livré, False si l'inventaire n'est pas exploitable
        (ex. vide sur une nouvelle partie) -> l'appelant RÉESSAIE plus tard."""
        span = 0x800
        inv = await self.gdb.read_memory(INVENTORY_BASE, span)
        # 1) objet déjà présent : incrémenter la quantité ; repérer au passage la
        #    VRAIE dernière entrée (plus haute entrée non nulle, marqueur ptr==0).
        last_off = None
        for off in range(0, span, INVENTORY_ENTRY_SIZE):
            _slot, _typ, h, qty, ptr = struct.unpack_from("<HHIII", inv, off)
            if off != 0 and h == item_hash:
                new_qty = min(99, qty + amount)
                await self.gdb.write_memory(
                    INVENTORY_BASE + off + INVENTORY_QTY_OFFSET,
                    struct.pack("<I", new_qty))
                # ⚠️ ENTRÉE « ÉPUISÉE » (RE + fix Doteos 2026-07-27) : quand un
                # consommable tombe à 0, le jeu GARDE l'entrée mais EFFACE son bit
                # de slot (et décrémente `count`) -> l'objet disparaît de l'affichage.
                # Ré-incrémenter la seule quantité le laisse donc INVISIBLE (cause
                # probable des bugs historiques « reçu mais pas dans l'inventaire »).
                # -> si le bit de slot est éteint, on le repose et on recompte.
                # `count2` (= nb d'entrées PHYSIQUES + 1) ne bouge pas : l'entrée
                # existait déjà.
                if qty == 0:
                    bit_addr = INVENTORY_SLOT_BITS + _slot // 8
                    bits = (await self.gdb.read_memory(bit_addr, 1))[0]
                    if not bits & (1 << (_slot % 8)):
                        await self.gdb.write_memory(
                            bit_addr, bytes([bits | (1 << (_slot % 8))]))
                        cnt = int.from_bytes(await self.gdb.read_memory(
                            INVENTORY_COUNT_ADDR, 4), "little")
                        await self.gdb.write_memory(
                            INVENTORY_COUNT_ADDR, struct.pack("<I", cnt + 1))
                        logger.info("Entrée épuisée réactivée (slot %d) pour "
                                    "%#010x : bit de slot reposé.", _slot,
                                    item_hash)
                return True
            if off != 0 and (h or qty or ptr):
                last_off = off

        # 2) objet absent : créer une entrée.
        #    Structure de l'inventaire VÉRIFIÉE par RE (2026-07-15) :
        #      * offset 0x00 = EN-TÊTE réservé (ptr=0x007FD398, qté=0, "hash" =
        #        un pointeur RAM) -> JAMAIS un objet ; d'où le `off != 0` du scan.
        #      * objets à partir de 0x10, slots 0..N, chaînés par ptr=0x007FD398 ;
        #        la DERNIÈRE entrée a ptr=0. count = nb d'objets (hors en-tête) ;
        #        count2 (+4) = count+1.
        #    Deux cas de création :
        #      * inventaire NON vide -> nouvelle entrée après la vraie dernière ;
        #      * inventaire VIDE (last_off None, ex. neutralisation d'un coffre
        #        qui a retiré le dernier objet) -> 1re entrée à 0x10 (slot 0),
        #        chaînée depuis l'EN-TÊTE (offset 0). Sans ça : livraison bloquée.
        if last_off is None:
            # Garde-fou : en-tête absent (tout à zéro) = état non exploitable
            # (ex. inventaire pas encore initialisé) -> on réessaie, sans écrire.
            _hslot, _htyp, _hh, _hq, _hptr = struct.unpack_from("<HHIII", inv, 0)
            if not (_hh or _hptr or _htyp):
                logger.info("Inventaire vide sans en-tête exploitable : livraison "
                            "de %#010x reportée (réessai au prochain poll).", item_hash)
                return False
            chain_off, new_off, new_slot = 0, INVENTORY_ENTRY_SIZE, 0
        elif last_off + 2 * INVENTORY_ENTRY_SIZE > span:
            logger.info("Inventaire plein : livraison de %#010x reportée "
                        "(réessai au prochain poll).", item_hash)
            return False
        else:
            new_slot = struct.unpack_from("<H", inv, last_off)[0] + 1
            chain_off, new_off = last_off, last_off + INVENTORY_ENTRY_SIZE
        count = int.from_bytes(
            await self.gdb.read_memory(INVENTORY_COUNT_ADDR, 4), "little")
        # a. chaîner l'entrée précédente (vraie dernière entrée, ou en-tête) :
        #    son ptr 0 -> 0x007FD398 (« une entrée suit »).
        await self.gdb.write_memory(INVENTORY_BASE + chain_off + INVENTORY_PTR_OFFSET,
                                    struct.pack("<I", INVENTORY_PTR_VALUE))
        # b. écrire la nouvelle entrée [slot, type, hash, qté, ptr=0 (dernière)]
        await self.gdb.write_memory(INVENTORY_BASE + new_off, struct.pack(
            "<HHIII", new_slot, inv_type, item_hash, min(99, amount), 0))
        # c. incrémenter les deux compteurs (count2 = count+1 préservé)
        await self.gdb.write_memory(INVENTORY_COUNT_ADDR,
                                    struct.pack("<I", count + 1))
        await self.gdb.write_memory(INVENTORY_COUNT_ADDR + 4,
                                    struct.pack("<I", count + 2))
        # d. poser le bit du slot dans le bitfield des slots occupés
        byte_addr = INVENTORY_SLOT_BITS + new_slot // 8
        cur = (await self.gdb.read_memory(byte_addr, 1))[0]
        await self.gdb.write_memory(
            byte_addr, bytes([cur | (1 << (new_slot % 8))]))
        if chain_off == 0:
            logger.info("Livraison %#010x sur inventaire vide : 1re entrée créée "
                        "à 0x10 (slot 0).", item_hash)
        return True

    async def _deliver_to_key_items(self, item_hash: int) -> None:
        """Wrapper transactionnel (cf. _deliver_to_inventory)."""
        own = await self.gdb.begin_halt()
        try:
            return await self._deliver_to_key_items_raw(item_hash)
        finally:
            if own:
                await self.gdb.cont()

    async def _deliver_to_key_items_raw(self, item_hash: int) -> None:
        """Ajoute un objet-clé (outil/clé) dans la liste d'objets-clés.

        Idempotent : ne fait rien si le hash est déjà présent. Sinon crée une
        entrée (entrée + 2 compteurs + bit de slot). Voir la recette complète
        dans memory_map (section objets-clés). SANS le bit de slot -> CRASH.
        Le mot haut de `data` = ordre d'acquisition = max(existants)+1."""
        count = int.from_bytes(
            await self.gdb.read_memory(KEY_ITEM_COUNT_ADDR, 4), "little")
        # scan des `count` entrées : déjà possédé ? + plus grand `haut`.
        span = max(count, 1) * KEY_ITEM_ENTRY_SIZE
        listing = await self.gdb.read_memory(KEY_ITEM_BASE, span)
        max_order = 0
        for i in range(count):
            base = i * KEY_ITEM_ENTRY_SIZE
            if struct.unpack_from(
                    "<I", listing, base + KEY_ITEM_HASH_OFFSET)[0] == item_hash:
                return
            data = struct.unpack_from(
                "<I", listing, base + KEY_ITEM_DATA_OFFSET)[0]
            max_order = max(max_order, data >> 16)
        if count >= 180:  # capacité 0xB4
            logger.warning("Liste d'objets-clés pleine : %#010x ignoré.",
                           item_hash)
            return
        index = count
        entry = KEY_ITEM_BASE + index * KEY_ITEM_ENTRY_SIZE
        # data = (ordre_acquisition << 16) | 0x2000 | index ; validé en jeu :
        # Canne à pêche 0x00022003, Clé de cabane 0x0012200A.
        data_word = ((max_order + 1) << 16) | KEY_ITEM_DATA_MARK | index
        # 1. écrire l'entrée [ptr constant][data][hash]
        await self.gdb.write_memory(entry, struct.pack(
            "<III", KEY_ITEM_PTR_VALUE, data_word, item_hash))
        # 2+3. incrémenter les deux compteurs
        await self.gdb.write_memory(KEY_ITEM_COUNT_ADDR,
                                    struct.pack("<I", count + 1))
        await self.gdb.write_memory(KEY_ITEM_COUNT2_ADDR,
                                    struct.pack("<I", count + 2))
        # 4. poser le bit du slot dans le bitfield dédié (0x086CF1B0)
        byte_addr = KEY_ITEM_SLOT_BITS + index // 8
        cur = (await self.gdb.read_memory(byte_addr, 1))[0]
        await self.gdb.write_memory(
            byte_addr, bytes([cur | (1 << (index % 8))]))
        self._ki_cache = None    # liste modifiée -> cache périmé (perf)

    async def _read_key_item_hashes(self) -> Dict[int, int]:
        """Lit la liste d'objets-clés en jeu -> {hash: index}."""
        count = int.from_bytes(
            await self.gdb.read_memory(KEY_ITEM_COUNT_ADDR, 4), "little")
        count = min(count, 180)
        if count <= 0:
            return {}
        listing = await self.gdb.read_memory(
            KEY_ITEM_BASE, count * KEY_ITEM_ENTRY_SIZE)
        out: Dict[int, int] = {}
        for i in range(count):
            h = struct.unpack_from(
                "<I", listing, i * KEY_ITEM_ENTRY_SIZE + KEY_ITEM_HASH_OFFSET)[0]
            if h:
                out[h] = i
        return out

    async def _key_items_cached(self) -> Dict[int, int]:
        """Liste d'objets-clés avec CACHE sur le compteur (perf, Doteos 2026-07-26).

        Lue 2x par cycle avant (check « Item AP dédié » + neutralisation) = 4+
        allers-retours GDB. Ici : 1 lecture du compteur (4 o) ; le LISTING n'est
        relu que si le compteur change, si le cache a été invalidé (écriture
        client : livraison/retrait) ou périodiquement (1 cycle sur 4 — borne le
        cas compteur-stable à contenu changé, ex. quête qui consomme un objet-clé
        pendant qu'un don natif arrive). Obsolescence bornée à ~8 s, sans effet
        joueur (la neutralisation/le check partent au cycle suivant)."""
        count = int.from_bytes(
            await self.gdb.read_memory(KEY_ITEM_COUNT_ADDR, 4), "little")
        cache = getattr(self, "_ki_cache", None)
        if (cache is not None and count == getattr(self, "_ki_count", -1)
                and getattr(self, "_poll_n", 0) % 4 != 0):
            return cache
        fresh = await self._read_key_item_hashes()
        self._ki_cache, self._ki_count = fresh, count
        return fresh

    async def _remove_from_key_items(self, item_hash: int) -> bool:
        """Wrapper transactionnel (cf. _deliver_to_inventory)."""
        own = await self.gdb.begin_halt()
        try:
            return await self._remove_from_key_items_raw(item_hash)
        finally:
            if own:
                await self.gdb.cont()

    async def _remove_from_key_items_raw(self, item_hash: int) -> bool:
        """Retire un objet-clé de la liste (swap-last) — miroir de la livraison.
        La liste a `count` = nb réel d'entrées (pas le décalage de l'inventaire).
        Retourne True si retiré."""
        count = int.from_bytes(
            await self.gdb.read_memory(KEY_ITEM_COUNT_ADDR, 4), "little")
        if count <= 0:
            return False
        listing = await self.gdb.read_memory(
            KEY_ITEM_BASE, count * KEY_ITEM_ENTRY_SIZE)
        target = None
        for i in range(count):
            if struct.unpack_from(
                    "<I", listing, i * KEY_ITEM_ENTRY_SIZE + KEY_ITEM_HASH_OFFSET
                    )[0] == item_hash:
                target = i
                break
        if target is None:
            return False
        last = count - 1
        if target != last:
            # déplace la dernière entrée dans le trou (corrige son index bas)
            l_ptr, l_data, l_hash = struct.unpack_from(
                "<III", listing, last * KEY_ITEM_ENTRY_SIZE)
            new_data = (l_data & 0xFFFF0000) | KEY_ITEM_DATA_MARK | target
            await self.gdb.write_memory(
                KEY_ITEM_BASE + target * KEY_ITEM_ENTRY_SIZE,
                struct.pack("<III", l_ptr, new_data, l_hash))
        await self.gdb.write_memory(
            KEY_ITEM_BASE + last * KEY_ITEM_ENTRY_SIZE, bytes(KEY_ITEM_ENTRY_SIZE))
        await self.gdb.write_memory(KEY_ITEM_COUNT_ADDR, struct.pack("<I", count - 1))
        await self.gdb.write_memory(KEY_ITEM_COUNT2_ADDR, struct.pack("<I", count))
        byte_addr = KEY_ITEM_SLOT_BITS + last // 8
        b = (await self.gdb.read_memory(byte_addr, 1))[0]
        await self.gdb.write_memory(byte_addr, bytes([b & ~(1 << (last % 8))]))
        self._ki_cache = None    # liste modifiée -> cache périmé (perf)
        return True

    async def _neutralize_native_key_items(self, present=None) -> None:
        """Shuffle DUR des objets-clés : retire de la liste en jeu tout objet-clé
        AP-shufflé que le JOUEUR N'A PAS reçu d'AP (= don natif de l'histoire) ;
        AP le (re)livre là où il est placé. Distinction native/AP : légitime si
        présent dans items_received (source de vérité AP, repeuplée à la connexion)
        OU livré cette session (_keyitem_done). ⚠️ SOFT-LOCK possible si un objet
        requis pour progresser est retiré avant d'être atteignable (logique
        anti-soft-lock à ajouter). Ne tourne que si activé (hard_key_shuffle)."""
        legit = {ITEM_ID_TO_NAME.get(ni.item) for ni in self.items_received}
        legit |= self._keyitem_done
        ap_key_hashes = {ITEM_GAME_HASH[n]: n
                         for n in KEY_ITEM_GAME if n in ITEM_GAME_HASH}
        if present is None:      # lecture partagée par poll_game (perf) sinon
            present = await self._read_key_item_hashes()
        native_checks: List[int] = []
        for h, name in ap_key_hashes.items():
            if h in present and name not in legit:
                # Le spot natif de l'objet devient un check (filler) : on le
                # déclenche AVANT de retirer l'objet natif de la liste.
                # native_key_check_name -> None si l'objet est obtenu via un coffre
                # (doublon) -> _queue_check ignore alors le check.
                self._queue_check(native_key_check_name(name), native_checks)
                if await self._remove_from_key_items(h):
                    logger.info("Objet-clé natif retiré (shuffle dur) : %s", name)
        if native_checks:
            await self.send_msgs([{"cmd": "LocationChecks",
                                   "locations": native_checks}])

    async def _enforce_story_gates(self, peek=None) -> None:
        """Hard-gate de zone (progression scénario). Pour chaque gate : tant que
        l'objet-clé AP n'est PAS reçu, on remet le pas de scénario à `locked` DÈS
        qu'il vaut EXACTEMENT `unlocked` (le jeu l'y met quand le joueur fait
        l'événement) -> la zone reste verrouillée même après l'événement (le check
        natif est quand même envoyé + l'objet natif retiré par le shuffle dur).
        À la réception de l'objet AP : on ne touche plus rien -> le jeu débloque
        naturellement au prochain déclenchement de l'événement. On ne réécrit QUE
        la valeur `unlocked` exacte (jamais une autre) pour ne pas casser d'autres
        moments du scénario."""
        received = {ITEM_ID_TO_NAME.get(ni.item) for ni in self.items_received}

        # Perf (Doteos 2026-07-26) : les LECTURES (trigger + valeur courante) tombent
        # toutes dans le gros bloc déjà lu ce cycle (0x086CFA24..0x086D023B). Si
        # `peek` est fourni, on tranche dedans au lieu de refaire ~20 allers-retours
        # GDB par poll (le jeu est halté tout le cycle, aucun step antérieur n'écrit
        # ces adresses -> valeurs à jour). Les ÉCRITURES restent en GDB (rares).
        async def _rd(addr: int, n: int) -> bytes:
            if peek is not None:
                b = peek(addr, n)
                if b is not None:
                    return b
            return await self.gdb.read_memory(addr, n)

        # Écritures TRANSACTIONNELLES (mode no_halt) : la décision vient d'une
        # lecture potentiellement PRISE EN MARCHE (peek non halté) -> avant
        # d'écrire, on halte, on RELIT la valeur fraîche et on ne modifie que si
        # c'est toujours nécessaire (sinon on écraserait un octet que le jeu
        # vient de changer). En mode halt classique, begin_halt est un no-op
        # (déjà halté par poll_game) et la relecture ne coûte qu'un petit read.
        async def _locked_write_u16_if(addr: int, expect: int,
                                       value: bytes) -> bool:
            own = await self.gdb.begin_halt()
            try:
                fresh = await self.gdb.read_memory(addr, 2)
                if int.from_bytes(fresh, "little") == expect:
                    await self.gdb.write_memory(addr, value)
                    return True
                return False
            finally:
                if own:
                    await self.gdb.cont()

        async def _locked_write_bits(addr: int, mask: int,
                                     set_bits: bool) -> bool:
            own = await self.gdb.begin_halt()
            try:
                fresh = (await self.gdb.read_memory(addr, 1))[0]
                want = (fresh | mask) if set_bits else (fresh & ~mask & 0xFF)
                if want != fresh:
                    await self.gdb.write_memory(addr, bytes([want]))
                    return True
                return False
            finally:
                if own:
                    await self.gdb.cont()

        for gate in STORY_GATES:
            # Un gate peut accepter PLUSIEURS noms d'objet (ex. Vélo / Vélo
            # (progressif) selon l'option) : "items" (liste) OU "item" (unique).
            names = gate.get("items") or (gate["item"],)
            item = names[0]                     # nom pour le log / _gates_logged
            has_item = any(n in received for n in names)
            changed = False

            # Gate CONDITIONNEL (latch) : si "trigger" présent, on ne fait RIEN tant
            # que le marqueur déclencheur (event NATIF fait) est OFF (Doteos 2026-07-25).
            # Le tuto/scénario se déroule alors nativement ; le jeu pose lui-même la
            # capacité. Dès que le marqueur passe ON, on gate normalement (pose si reçu
            # / efface sinon). Un item reçu AVANT l'event ne pose donc plus le bit trop
            # tôt ; il se posera quand le joueur fera l'event (« sa se débloque tout seul »).
            trig = gate.get("trigger")
            if trig is not None:
                tbyte = (await _rd(trig[0], 1))[0]
                if not (tbyte & trig[1]):
                    self._gates_logged.discard(item)
                    continue              # pas encore déclenché -> ne rien toucher

            if gate.get("kind", "u16") == "u16":
                # Pas de scénario : on ne touche QUE la valeur `unlocked` exacte
                # (jamais une autre valeur de scénario -> aucun autre beat cassé).
                if has_item:
                    self._gates_logged.discard(item)
                    continue          # reçu -> laisser le jeu débloquer
                for addr in gate["addrs"]:
                    raw = await _rd(addr, 2)
                    if int.from_bytes(raw, "little") == gate["unlocked"]:
                        if await _locked_write_u16_if(
                                addr, gate["unlocked"],
                                int(gate["locked"]).to_bytes(2, "little")):
                            changed = True
            else:
                # Bits de capacité/event : lire-modifier-écrire (on préserve les
                # autres bits de l'octet, qui portent d'autres events).
                for addr, mask in gate["bits"]:
                    cur = (await _rd(addr, 1))[0]
                    want = (cur | mask) if has_item else (cur & ~mask & 0xFF)
                    if want != cur:
                        if await _locked_write_bits(addr, mask, has_item):
                            changed = True
                if has_item:
                    if changed:
                        logger.info("Capacité débloquée (« %s » reçu)", item)
                    self._gates_logged.discard(item)
                    continue

            # Ne loguer QU'UNE fois par "session de verrouillage" (le jeu peut
            # reposer la valeur -> sinon spam à chaque poll).
            if changed and item not in self._gates_logged:
                self._gates_logged.add(item)
                logger.info("Verrouillé (objet AP « %s » non reçu)", item)


    # --- neutralisation de l'item natif des coffres (design unifié) ---------
    @staticmethod
    def _parse_inventory(raw: bytes) -> Dict[int, int]:
        """{hash: quantité totale} depuis un dump inventaire (entrées 16 o)."""
        inv: Dict[int, int] = {}
        for off in range(0, len(raw), INVENTORY_ENTRY_SIZE):
            _slot, _typ, h, qty, _ptr = struct.unpack_from("<HHIII", raw, off)
            if off != 0 and h:
                inv[h] = inv.get(h, 0) + qty
        return inv

    async def _remove_from_inventory(self, item_hash: int, amount: int) -> None:
        """Wrapper transactionnel (cf. _deliver_to_inventory)."""
        own = await self.gdb.begin_halt()
        try:
            return await self._remove_from_inventory_raw(item_hash, amount)
        finally:
            if own:
                await self.gdb.cont()

    async def _remove_from_inventory_raw(self, item_hash: int,
                                         amount: int) -> None:
        """Retire `amount` d'un objet : décrémente la quantité ; si elle tombe
        à <=0, retire l'entrée (échange avec la VRAIE dernière entrée + décrément
        des compteurs + effacement du bit de slot). Réciproque de la recette
        d'ajout.

        La dernière entrée est trouvée en SCANNANT la plus haute entrée non nulle
        (marqueur ptr==0), et NON via `count` : `count` peut être décalé d'une
        unité par rapport au nombre réel d'entrées (observé en RE 2026-07-12),
        donc (count-1)*taille pointe à côté et corromprait l'inventaire. Si la
        structure est inattendue (dernière entrée sans ptr==0), on n'écrit RIEN —
        le retrait sera retenté au prochain poll."""
        span = 0x800
        inv = await self.gdb.read_memory(INVENTORY_BASE, span)
        target_off = cur_qty = None
        last_off = None
        for off in range(0, span, INVENTORY_ENTRY_SIZE):
            _slot, _typ, h, qty, ptr = struct.unpack_from("<HHIII", inv, off)
            if off != 0 and h == item_hash and target_off is None:
                target_off, cur_qty = off, qty
            if off != 0 and (h or qty or ptr):
                last_off = off          # plus haute entrée non nulle = la dernière
        if target_off is None:
            return
        new_qty = cur_qty - amount
        if new_qty > 0:
            await self.gdb.write_memory(
                INVENTORY_BASE + target_off + INVENTORY_QTY_OFFSET,
                struct.pack("<I", new_qty))
            return
        if last_off is None:
            return
        lslot, ltyp, lhash, lqty, lptr = struct.unpack_from("<HHIII", inv, last_off)
        if lptr != 0:
            return  # structure inattendue -> ne pas corrompre, on réessaiera
        count = int.from_bytes(
            await self.gdb.read_memory(INVENTORY_COUNT_ADDR, 4), "little")
        # déplace la vraie dernière entrée dans le trou (préserve le slot du trou)
        if target_off != last_off:
            await self.gdb.write_memory(INVENTORY_BASE + target_off + 2,
                                        struct.pack("<HII", ltyp, lhash, lqty))
        await self.gdb.write_memory(INVENTORY_BASE + last_off,
                                    bytes(INVENTORY_ENTRY_SIZE))
        await self.gdb.write_memory(INVENTORY_COUNT_ADDR,
                                    struct.pack("<I", count - 1))
        await self.gdb.write_memory(INVENTORY_COUNT_ADDR + 4,
                                    struct.pack("<I", count))
        if last_off - INVENTORY_ENTRY_SIZE > 0:
            await self.gdb.write_memory(
                INVENTORY_BASE + last_off - INVENTORY_ENTRY_SIZE
                + INVENTORY_PTR_OFFSET, struct.pack("<I", 0))
        bit_addr = INVENTORY_SLOT_BITS + lslot // 8
        b = (await self.gdb.read_memory(bit_addr, 1))[0]
        await self.gdb.write_memory(
            bit_addr, bytes([b & ~(1 << (lslot % 8))]))

    async def _neutralize_native_chest(self, current_inv: Dict[int, int],
                                       target_hashes: set) -> Dict[int, int]:
        """Retire l'item natif des coffres qui viennent d'être ouverts.

        REGISTRE-BASED (Doteos 2026-07-19) : `target_hashes` = les hash NATIFS
        EXACTS des coffres mappés ouverts ce poll (via CHEST_BIT_TO_NATIVE_HASH).
        On ne regarde QUE ces hash -> le bruit multiworld (autres items apparus,
        filler livré, gains divers) est IGNORÉ. Fini l'ancien diff fragile qui
        devinait sur tous les items et s'annulait dès >2 types.

        La QUANTITÉ retirée = `current_inv[h] - _prev_inv[h] - _delivered_last_poll[h]`
        (ce que le JEU a ajouté pour CE hash, hors nos livraisons), ce qui gère
        les coffres qui donnent x2/x3 sans quantité codée en dur. Robuste car
        borné aux hash de coffre connus. Retourne {hash: qté retirée}."""
        removed: Dict[int, int] = {}
        if self._prev_inv is None:
            return removed
        for h in target_hashes:
            added = (current_inv.get(h, 0) - self._prev_inv.get(h, 0)
                     - self._delivered_last_poll.get(h, 0))
            if added > 0:
                logger.info("Neutralisation coffre (registre) : %#010x  "
                            "(courant=%d, précédent=%d, livré=%d -> retire %d)",
                            h, current_inv.get(h, 0), self._prev_inv.get(h, 0),
                            self._delivered_last_poll.get(h, 0), added)
                await self._remove_from_inventory(h, added)
                removed[h] = added
        return removed

    # --- persistance de l'index livré (idempotence entre redémarrages) ------
    def _delivery_state_path(self) -> str:
        seed = getattr(self, "seed_name", None) or "unknown"
        slot = getattr(self, "slot", None) or 0
        return Utils.user_path("ykw2", f"delivered_{seed}_{slot}.txt")

    def load_delivered_count(self) -> None:
        """Recharge l'index livré (consommables) depuis le fichier (None si
        absent) et réinitialise le suivi des objets-clés livrés cette session."""
        # Les objets-clés sont ré-évalués par présence à chaque connexion ; on
        # repart d'un set vide (le presence-check en jeu fait foi).
        self._keyitem_done: set = set()
        try:
            with open(self._delivery_state_path(), encoding="ascii") as f:
                self.delivered_count = int(f.read().strip())
        except (OSError, ValueError):
            self.delivered_count = None

    def _save_delivered_count(self) -> None:
        """Écriture ATOMIQUE (temp + rename) pour ne pas corrompre l'état si le
        client meurt en plein écrit."""
        try:
            path = self._delivery_state_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="ascii") as f:
                f.write(str(self.delivered_count))
            os.replace(tmp, path)
        except OSError:
            pass

    def _ap_rank_floor(self) -> int:
        """Rang de montre PLANCHER accordé par les items AP reçus (0=aucun,
        1=D .. 5=S). Progressif : chaque « Rang de Yo-kai Watch (progressif) »
        = +1 rang. Individuels (progressive_watch_rank off) : le plus haut
        rang reçu. Recalculé depuis items_received -> idempotent, robuste aux
        reconnexions (aucun compteur à persister)."""
        progressive = 0
        highest = 0
        rank_levels = {name: level for level, name in RANK_ITEM_NAMES.items()}
        for net_item in self.items_received:
            name = ITEM_ID_TO_NAME.get(net_item.item)
            if name == PROGRESSIVE_RANK_ITEM:
                progressive += 1
            elif name in rank_levels:
                highest = max(highest, rank_levels[name])
        return min(5, max(progressive, highest))

    async def _deliver_watch_rank(self, chapter: int, rank_raw: bytes) -> None:
        """SHUFFLE DUR du rang de montre : le rang en jeu = EXACTEMENT le
        plancher AP (CHANGEMENT DE DESIGN Doteos 2026-07-16 ; avant, item
        abstrait « le jeu délivre via ses quêtes »).

        Deux sens :
          * items AP > rang en jeu -> LIVRAISON (écrit le plancher) ;
          * rang en jeu > items AP -> NEUTRALISATION d'un gain natif (quête
            de rang / amélioration d'histoire) : le rang est ramené au
            plancher ; le CHECK de la quête part quand même (l'incrément est
            lu AVANT le clamp sur ce poll, et le hash de quête couvre les
            complétions sans incrément). Anti-soft-lock : la logique du
            générateur gate chapitres/boss/zones par CHAPTER_COMBAT_RANKS et
            AccessReq(rang) -> les items de rang sont toujours obtenables
            avant d'être requis (même chaîne de garantie que les objets-clés).

        VÉRIFIÉ en jeu : écrire 0x086D023A pilote l'affichage (badge RANG
        WATCH) ET persiste dans la sauvegarde (save/reload OK). Rien tant
        qu'aucune save n'est chargée (chapitre 0 : RAM non initialisée)."""
        if chapter < 1:
            return
        floor = self._ap_rank_floor()
        current = rank_raw[0] if rank_raw else 0

        # CHECKS « Montée de rang » (Doteos 2026-07-26) : le byte de rang n'est
        # écrit QUE par le client (clamp au plancher AP) ou par un ÉVÉNEMENT
        # NATIF de montée (histoire fin Ch2 = D ; requêtes de rang = C..S). Si
        # la valeur lue diffère de ce qu'on a laissé au poll précédent
        # (_rank_expected), c'est une montée native de valeur V=current -> les
        # montées 1..V sont FAITES (chaînage garanti : D est une étape
        # d'histoire obligatoire, chaque requête de rang exige la précédente)
        # -> on envoie leurs checks (dédup par missing_locations). À la 1re
        # lecture (resync, _rank_expected None) : on ne crédite que si
        # current > floor (au-delà du plancher AP = forcément fait nativement ;
        # en dessous, impossible de distinguer notre propre clamp d'une montée
        # native -> on s'abstient, un futur event la re-signalera).
        expected = getattr(self, "_rank_expected", None)
        native_rank = 0
        if expected is None:
            if current > floor:
                native_rank = current
        elif current != expected and 1 <= current <= 5:
            native_rank = current
        if native_rank:
            rank_checks: List[int] = []
            for v in range(1, min(native_rank, 5) + 1):
                self._queue_check("Montée de rang : " + "EDCBAS"[v],
                                  rank_checks)
                # Rang natif V atteint => la REQUÊTE de rang V a été faite
                # (seule source du rang V ; D vient de l'histoire, sans requête).
                # Crédite AUSSI son check (idée Doteos 2026-07-26) : rattrape les
                # quêtes de rang faites HORS LIGNE, que la détection par hash
                # transitoire ne peut pas voir a posteriori. Dédup automatique
                # (_queue_check filtre les locations déjà envoyées).
                if v >= 2:
                    self._queue_check(RANK_QUEST_NAMES[v], rank_checks)
            if rank_checks:
                await self.send_msgs([{"cmd": "LocationChecks",
                                       "locations": rank_checks}])
        # Après ce poll, le byte vaudra `floor` (clamp ci-dessous, ou déjà égal).
        self._rank_expected = floor

        if current == floor:
            return
        await self.gdb.write_memory(WATCH_RANK_VALUE_ADDR, bytes([floor]))
        letters = "EDCBAS"
        if floor > current:
            logger.info("Rang de montre livré : %s (items AP : %d).",
                        letters[floor], floor)
        else:
            logger.info("Rang natif neutralisé (shuffle dur) : %s -> %s "
                        "(le rang vient des items AP ; le check de la "
                        "quête est conservé).",
                        letters[min(current, 5)], letters[floor])

    async def deliver_pending_items(self) -> None:
        """Écrit en jeu les items reçus pas encore livrés.

        Deux régimes selon la nature de l'objet :
          * OBJETS-CLÉS (progression) -> livrés IDEMPOTEMMENT, indépendamment du
            compteur : `_deliver_to_key_items` saute si le hash est déjà présent.
            Donc jamais perdus ni dupliqués, même si le compteur se désync
            (rechargement d'une vieille save, perte du fichier d'état).
          * CONSOMMABLES (filler) -> gardés par `delivered_count` (on ne peut pas
            distinguer une quantité déjà livrée), persisté par (seed, slot).
          * ITEMS ABSTRAITS (rang, vélo, régions) -> no-op en jeu : le jeu les
            délivre naturellement au bon moment de l'histoire (cf. design).
        """
        received = self.items_received

        # 1) Progression (objets-clés) : idempotent, hors compteur.
        for net_item in received:
            name = ITEM_ID_TO_NAME.get(net_item.item)
            if name in KEY_ITEM_GAME and name not in self._keyitem_done:
                item_hash = ITEM_GAME_HASH.get(name)
                if item_hash is not None:
                    await self._deliver_to_key_items(item_hash)
                    self._keyitem_done.add(name)
                    logger.info("Reçu et livré (objet-clé) : %s", name)

        # 2) Consommables : gated par le compteur (anti-duplication).
        if self.delivered_count is None:
            # 1re passe sans état : on part de l'existant pour ne pas re-livrer
            # les consommables déjà en jeu (client rattaché à une partie en cours).
            self.delivered_count = len(received)
            self._save_delivered_count()
            return
        changed = False
        while self.delivered_count < len(received):
            net_item = received[self.delivered_count]
            name = ITEM_ID_TO_NAME.get(net_item.item)
            item_hash = ITEM_GAME_HASH.get(name) if name else None
            if name in KEY_ITEM_GAME:
                pass  # déjà géré idempotemment ci-dessus
            elif self._from_own_quest(net_item):
                # Objet reçu depuis TA PROPRE quête : le JEU l'a déjà donné (patch
                # de récompense) -> ne PAS re-livrer (design unifié, évite le
                # doublon). Les objets-clés (idempotents) sont exclus ci-dessus.
                logger.info("Reçu (donné par la quête en jeu) : %s",
                            name or net_item.item)
            elif item_hash is not None:
                inv_type = ITEM_GAME_TYPE.get(name, DEFAULT_INVENTORY_TYPE)
                # Consommables filler : quantité ALÉATOIRE 1-3 (mime le contenu
                # d'un coffre : « Riz à la prune x2 », etc.). Les autres objets
                # (utiles, outils) restent en x1.
                amount = random.randint(1, 3) if name in FILLER_ITEM_NAMES else 1
                if not await self._deliver_to_inventory(item_hash, inv_type, amount):
                    # Inventaire pas prêt (vide) -> on STOPPE ici SANS avancer
                    # delivered_count : l'item sera re-livré au prochain poll
                    # (pas de perte). Les items suivants attendent aussi.
                    break
                # On enregistre la VRAIE quantité livrée pour que la neutralisation
                # de coffre (diff d'inventaire) n'attribue pas ce surplus au jeu.
                self._delivered_this_poll[item_hash] = \
                    self._delivered_this_poll.get(item_hash, 0) + amount
                logger.info("Reçu et livré : %s x%d", name, amount)
            elif name == PROGRESSIVE_RANK_ITEM or name in RANK_ITEM_NAMES.values():
                # rangs de montre : appliqués DIRECTEMENT en jeu par
                # _deliver_watch_rank (force-write, design 2026-07-16).
                logger.info("Reçu : %s -> rang appliqué en jeu.", name)
            else:
                # items abstraits : le jeu les délivre via l'histoire (no-op ici)
                logger.info("Reçu (délivré par l'histoire) : %s",
                            name or net_item.item)
            self.delivered_count += 1
            changed = True
        if changed:
            self._save_delivered_count()

    def _from_own_quest(self, net_item) -> bool:
        """Vrai si l'item a été trouvé à une de TES quêtes (le jeu l'a donné via
        le patch de récompense) -> ne pas le re-livrer en mémoire."""
        return (getattr(net_item, "player", None) == self.slot
                and getattr(net_item, "location", None) in self.quest_loc_to_hash)

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self.load_delivered_count()  # idempotence : reprend l'index livré
            # Shuffle DUR des objets-clés : si les objets-clés sont shufflés, on
            # retire les dons NATIFS (histoire) -> tu ne les as que via AP.
            self._hard_key_shuffle = bool(self.slot_data.get("key_item_shuffle"))
            # DeathLink : synchronisation INCONDITIONNELLE du tag (False le
            # RETIRE — sans ça, le tag d'une room précédente du même process
            # collerait et on enverrait/recevrait des morts option OFF).
            # État par room remis à zéro : pas de mort héritée, pas
            # d'armement fondé sur une autre session de jeu.
            Utils.async_start(self.update_death_link(
                bool(self.slot_data.get("death_link"))))
            del self._deathlink_pending[:]
            self._can_send_death = False
            self._death_to_send = False
            self._prev_live_alive = False
            self._dl_kill_lock = False
            # Affichage en jeu des récompenses de quêtes : on scoute les
            # locations de quêtes pour savoir quel item AP est placé à chacune,
            # puis on patchera le mod (cf. LocationInfo).
            # IMPORTANT : ne scouter QUE les locations RÉELLEMENT dans la seed
            # (sinon le serveur plante sur une location exclue, ex. post-game
            # 'Obtenons le rang S', et ferme la connexion). Les locations du slot
            # = missing + checked, fournies dans le paquet Connected.
            active_locs = (set(args.get("missing_locations", ()))
                           | set(args.get("checked_locations", ())))
            scout = [loc for loc in self.quest_loc_to_hash if loc in active_locs]
            if scout:
                Utils.async_start(self.send_msgs([{
                    "cmd": "LocationScouts",
                    "locations": scout,
                    "create_as_hint": 0}]))
            if memory_map_ready():
                logger.info("Carte mémoire configurée : tapez /citra pour "
                            "activer l'envoi automatique des checks.")
            else:
                logger.info("Carte mémoire non renseignée (memory_map.py) : "
                            "client en mode texte. Voir "
                            "docs/memory_map_fr.md pour la compléter.")
        elif cmd == "LocationInfo":
            Utils.async_start(
                self._patch_quest_rewards(args.get("locations", [])))

    def _foreign_item_name(self, item_id: int, player: int) -> str:
        """Nom d'un item (éventuellement d'un autre jeu) pour l'affichage."""
        try:
            return self.item_names.lookup_in_slot(item_id, player)
        except Exception:  # noqa: BLE001 - API item_names variable selon version
            return "Item %d" % item_id

    def _player_name(self, player: int) -> str:
        try:
            return self.player_names[player]
        except Exception:  # noqa: BLE001
            return "P%d" % player

    async def _patch_quest_rewards(self, location_infos) -> None:
        """Écrit dans le mod yw2_lg_fr.fa l'item AP placé à chaque quête, pour
        qu'il s'AFFICHE en jeu (objet réel du monde, ou nom de l'objet étranger).
        No-op silencieux si le mod n'est pas présent (le client livre quand
        même les items)."""
        mod_path = mod_patcher.find_mod_archive()
        if not mod_path:
            return
        placements: Dict[int, tuple] = {}
        for info in location_infos:
            loc = info["location"] if isinstance(info, dict) else info.location
            item = info["item"] if isinstance(info, dict) else info.item
            player = info["player"] if isinstance(info, dict) else info.player
            qhash = self.quest_loc_to_hash.get(loc)
            if qhash is None:
                continue
            if player == self.slot:
                # objet à SOI : objet YKW2 réel -> son hash ; sinon (abstrait :
                # rang, vélo...) -> son nom, sans tag de joueur (c'est le tien).
                name = ITEM_ID_TO_NAME.get(item)
                game_hash = ITEM_GAME_HASH.get(name)
                placements[qhash] = (("real", game_hash) if game_hash
                                     else ("foreign", name or "???"))
            else:
                # objet d'un AUTRE joueur : « nom (joueur destinataire) ».
                placements[qhash] = ("foreign", "%s (%s)" % (
                    self._foreign_item_name(item, player),
                    self._player_name(player)))
        if not placements:
            return
        try:
            count, warnings = mod_patcher.patch_mod(mod_path, placements)
            logger.info("Récompenses de quêtes affichées en jeu : %d quêtes "
                        "patchées (%d écritures).", len(placements), count)
            for w in warnings[:3]:
                logger.debug("patch mod : %s", w)
        except Exception as error:  # noqa: BLE001
            logger.error("Patch des récompenses en jeu échoué : %s: %s",
                         type(error).__name__, error)

    def on_deathlink(self, data: dict) -> None:
        # super() met à jour last_death_link (anti-echo de la couche AP).
        super().on_deathlink(data)
        # AUCUNE écriture mémoire ici : callback synchrone, or les écritures
        # exigent le GDB interrompu -> on note la mort, poll_game l'applique
        # au prochain cycle (~2 s). Liste (pas un scalaire) : deux morts
        # reçues avant le même poll = un seul kill mais toutes les sources
        # sont journalisées.
        self._deathlink_pending.append(data.get("source") or "?")
        logger.info("DeathLink reçu de %s — l'équipe sera mise K.O. au "
                    "prochain cycle.", self._deathlink_pending[-1])

    async def _apply_deathlink_kill(self, sources: List[str],
                                    battle_active: bool) -> None:
        """Wrapper transactionnel (cf. _deliver_to_inventory)."""
        own = await self.gdb.begin_halt()
        try:
            return await self._apply_deathlink_kill_raw(sources, battle_active)
        finally:
            if own:
                await self.gdb.cont()

    async def _apply_deathlink_kill_raw(self, sources: List[str],
                                        battle_active: bool) -> None:
        """Applique une mort DeathLink reçue (à appeler sous gdb.interrupt()).

        Met les PV à 1 (pas 0 — même létalité, le K.O. ne s'évalue que sur
        un coup reçu, mais 1 reste un état LÉGAL pour le jeu hors combat,
        idée Doteos) : (1) au TABLEAU d'équipe (toujours — au prochain
        combat, la roue démarre agonisante) ; (2) aux PV de COMBAT LIVE si
        un combat est en cours (le combat actuel devient létal : le moindre
        coup achève chaque Yo-kai). Seuls les slots OCCUPÉS (PV/PV max > 0)
        sont écrits. Idempotent : un retry après erreur GDB est sûr.
        L'anti-boucle est géré par l'appelant (verrou _dl_kill_lock)."""
        # `battle_active` passé par le scan peut être PÉRIMÉ (lecture en marche,
        # mode no_halt) -> on re-lit l'état de combat FRAIS sous le halt de cette
        # transaction (revue 2026-07-26) : un combat qui vient de commencer reçoit
        # bien ses PV live à 1, un combat qui vient de finir n'écrit pas dans une
        # struct nettoyée (les gardes live_max>0 protègent déjà).
        fresh_state = int.from_bytes(
            await self.gdb.read_memory(BATTLE_STATE_ADDR, 4), "little")
        battle_active = fresh_state != 0
        span = (PARTY_SLOT_COUNT - 1) * PARTY_ENTRY_STRIDE + 2
        party = await self.gdb.read_memory(PARTY_HP_FIRST_ADDR, span)
        hit = 0
        for i in range(PARTY_SLOT_COUNT):
            offset = i * PARTY_ENTRY_STRIDE
            if struct.unpack_from("<H", party, offset)[0] > 1:
                await self.gdb.write_memory(
                    PARTY_HP_FIRST_ADDR + offset, b"\x01\x00")
                hit += 1
        if battle_active:
            for i in range(PARTY_SLOT_COUNT):
                base = BATTLE_HP_FIRST_ADDR + i * BATTLE_HP_ENTRY_STRIDE
                pair = await self.gdb.read_memory(base, 4)
                live_max = struct.unpack_from("<H", pair, 0)[0]
                live_cur = struct.unpack_from("<H", pair, 2)[0]
                if live_max > 0 and live_cur > 1:
                    await self.gdb.write_memory(
                        base + BATTLE_HP_CUR_OFFSET, b"\x01\x00")
        logger.info("DeathLink appliqué (mort de %s) : équipe à 1 PV%s.",
                    ", ".join(sources),
                    " (combat en cours : prochaine attaque fatale)"
                    if battle_active else "")

    async def _confirm_wipe_halted(self) -> bool:
        """Re-confirme un wipe (défaite) par une lecture ATOMIQUE sous halt.
        Utilisé en mode no_halt avant d'envoyer une mort DeathLink : élimine
        les faux positifs de scan déchiré (fin de combat gagné nettoyée entre
        deux paquets). state==0 ou un PV courant > 0 -> pas de défaite."""
        own = await self.gdb.begin_halt()
        try:
            state = int.from_bytes(
                await self.gdb.read_memory(BATTLE_STATE_ADDR, 4), "little")
            if state == 0:
                return False
            any_max = any_cur = False
            for i in range(PARTY_SLOT_COUNT):
                pair = await self.gdb.read_memory(
                    BATTLE_HP_FIRST_ADDR + i * BATTLE_HP_ENTRY_STRIDE, 4)
                if struct.unpack_from("<H", pair, 0)[0]:
                    any_max = True
                if struct.unpack_from("<H", pair, 2)[0]:
                    any_cur = True
            return any_max and not any_cur
        finally:
            if own:
                await self.gdb.cont()

    async def _deathlink_scan(self) -> Optional[tuple]:
        """Lectures DeathLink + kill éventuel, sous gdb.interrupt().

        Lit l'état de combat et les 6 paires [max, cur] de la struct de
        combat LIVE ; la lecture PRÉCÈDE le kill pour qu'une VRAIE défaite
        simultanée (le joueur venait de perdre quand la mort est arrivée)
        reste transmissible. Les morts en attente sont consommées APRÈS
        succès (erreur GDB -> retry au cycle suivant, kill idempotent).
        Retourne (state, live_max, live_cur, kill_applied, array_alive)
        ou None si DeathLink inactif."""
        if "DeathLink" not in self.tags and not self._deathlink_pending:
            return None
        state = int.from_bytes(
            await self.gdb.read_memory(BATTLE_STATE_ADDR, 4), "little")
        live_max: List[int] = []
        live_cur: List[int] = []
        kill_applied = False
        if state == 0 and not self._deathlink_pending:
            # Perf (Doteos 2026-07-26) : HORS combat la struct de combat est
            # VIDÉE (max=0) -> lire les 6 paires ne peut donner que des zéros.
            # Listes vides = exactement la même évaluation aval (live_exists/
            # live_alive False, comme une vraie lecture hors combat), mais on
            # économise 6 allers-retours GDB — sur le poll ET la sonde (~1/s).
            pass
        else:
            for i in range(PARTY_SLOT_COUNT):
                pair = await self.gdb.read_memory(
                    BATTLE_HP_FIRST_ADDR + i * BATTLE_HP_ENTRY_STRIDE, 4)
                live_max.append(struct.unpack_from("<H", pair, 0)[0])
                live_cur.append(struct.unpack_from("<H", pair, 2)[0])
            if self._deathlink_pending:
                _sources = list(self._deathlink_pending)
                await self._apply_deathlink_kill(
                    _sources, battle_active=(state != 0 and any(live_max)))
                del self._deathlink_pending[:len(_sources)]
                kill_applied = True
        # Levée du verrou anti-boucle : uniquement HORS combat, en relisant
        # le TABLEAU d'équipe (la vérité hors combat). SEUIL > 1 : le kill
        # laisse l'équipe à 1 PV (état légal, idée Doteos), donc « revécu »
        # = resoigné AU-DESSUS de l'agonie (soin réel ou respawn
        # post-défaite qui soigne à fond) — sinon le verrou sauterait tout
        # seul et la mort reçue serait renvoyée (ping-pong).
        array_alive = None
        if self._dl_kill_lock and state == 0:
            span = (PARTY_SLOT_COUNT - 1) * PARTY_ENTRY_STRIDE + 2
            array = await self.gdb.read_memory(PARTY_HP_FIRST_ADDR, span)
            array_alive = any(
                struct.unpack_from("<H", array, i * PARTY_ENTRY_STRIDE)[0] > 1
                for i in range(PARTY_SLOT_COUNT))
        return state, live_max, live_cur, kill_applied, array_alive

    async def _deathlink_evaluate(self, state: int, live_max: List[int],
                                  live_cur: List[int], kill_applied: bool,
                                  array_alive: Optional[bool]) -> None:
        """Détection de DÉFAITE sur les PV de COMBAT LIVE + anti-boucle.

        DÉFAITE = la struct de combat EXISTE (max > 0), TOUS les PV courants
        à 0, transition depuis « vue vivante », état de combat != 0 (6 en
        combat, 3 sur l'écran « Perdu... », 0 en exploration — vérifié).
        Hors combat la struct est VIDÉE (max = 0) -> aucun faux positif en
        fin de combat gagné ni sur lecture zéro-paddée. L'armement se fait
        quand la roue est VUE vivante EN COMBAT, sauf verrou anti-boucle
        (_dl_kill_lock : mort reçue non « purgée ») -> un soin partiel en
        plein combat condamné ne réarme pas, et une équipe mise à 0 par
        DeathLink qui perd son prochain combat n'envoie rien non plus.
        Le verrou saute quand l'équipe est vue resoignée HORS combat (le
        respawn post-défaite resoigne le tableau -> levée automatique une
        fois la mort reçue consommée). Appelée par poll_game ET la sonde."""
        if "DeathLink" not in self.tags:
            return
        live_exists = any(live_max)
        live_alive = any(live_cur)
        if self._dl_kill_lock and array_alive:
            self._dl_kill_lock = False
            logger.info("DeathLink : équipe revue vivante -> détection "
                        "réarmable.")
        wiped = (live_exists and not live_alive and self._prev_live_alive
                 and state != 0)
        if wiped and self._can_send_death and self.gdb.no_halt:
            # Mode no_halt (revue 2026-07-26) : le scan a été pris EN MARCHE, en
            # 7 paquets séparés -> le nettoyage de fin de combat GAGNÉ peut
            # tomber entre deux paquets (slot K.O. lu avant le memset, survivants
            # lus après = 0/0) et fabriquer un faux wipe. Une mort DeathLink est
            # IRRÉVERSIBLE et diffusée à tous -> on RE-CONFIRME sous halt
            # (lecture atomique) avant d'envoyer.
            wiped = await self._confirm_wipe_halted()
        if wiped and self._can_send_death:
            # Désarmé immédiatement (un seul envoi par défaite) ; l'envoi
            # effectif attend un serveur joignable (_death_to_send).
            self._can_send_death = False
            self._death_to_send = True
            logger.info("Défaite détectée -> DeathLink pour les autres "
                        "joueurs.")
        elif (state != 0 and live_alive and not kill_applied
                and not self._dl_kill_lock):
            self._can_send_death = True  # roue vue VIVANTE en combat
        if self._death_to_send and self.server and self.server.socket:
            self._death_to_send = False
            await self.send_death(
                "Équipe Yo-kai anéantie dans Yo-kai Watch 2 !")
        # Un kill appliqué à CE cycle rend la lecture « vivant » caduque
        # (les PV live viennent d'être mis à 0) -> l'invalider empêche une
        # fausse transition au cycle suivant ; le verrou + désarmement
        # bloquent tout renvoi de cette mort reçue.
        self._prev_live_alive = live_alive and not kill_applied
        if kill_applied:
            self._can_send_death = False
            self._dl_kill_lock = True

    async def _deathlink_probe(self) -> None:
        """Sonde légère (~1 s) entre deux gros polls : mêmes lectures + même
        évaluation que poll_game. Nécessaire car un écran « Perdu... » fermé
        vite peut tenir dans l'intervalle d'un poll de 2 s ; applique aussi
        les morts reçues en attente (latence du kill ~1 s)."""
        if "DeathLink" not in self.tags and not self._deathlink_pending:
            return
        if self.gdb.no_halt:
            # lectures en marche ; un kill éventuel prend son propre halt court
            scan = await self._deathlink_scan()
        else:
            await self.gdb.interrupt()
            try:
                scan = await self._deathlink_scan()
            finally:
                await self.gdb.cont()
        if scan is not None:
            await self._deathlink_evaluate(*scan)

    async def attach_emulator(self, port: int) -> None:
        try:
            # Verrou : ne pas réassigner reader/writer pendant qu'un poll lit.
            async with self.gdb.io_lock:
                await self.gdb.connect(port=port)
                # Perf : teste les lectures SANS pause (fin du micro-freeze
                # périodique si le stub les sert). Sticky-désactivé après 2
                # pertes de connexion en mode no-halt (stub instable).
                if getattr(self, "_no_halt_losses", 0) < 2:
                    await self.gdb.probe_no_halt()
            logger.info("Attaché au stub GDB (port %d). L'émulation reprend.",
                        port)
            if self.gdb.no_halt:
                logger.info("Lectures sans pause ACTIVES : l'émulation n'est "
                            "plus haltée pour lire (fini le micro-freeze). Les "
                            "écritures restent ponctuellement synchronisées.")
            else:
                logger.info("Lectures sans pause non supportées par ce stub : "
                            "mode halt classique conservé.")
        except OSError as error:
            logger.error("Connexion au stub GDB impossible (port %d) : %s. "
                         "Dans Azahar : Émulation > Configurer > Debug > "
                         "« Enable GDB stub », puis relancez le jeu.",
                         port, error)

    # ------------------------------------------------------------------
    # Lecture des drapeaux -> envoi des checks
    # ------------------------------------------------------------------
    async def poll_game(self) -> None:
        # Mode « lectures sans pause » : on ne halte PLUS l'émulation pour le
        # poll (fini le micro-freeze toutes les POLL_INTERVAL s). Les fonctions
        # d'écriture prennent leur propre halt court (begin_halt) — atomicité
        # préservée. En mode classique (stub sans support) : halt global comme
        # avant. Lectures en marche = potentiellement « déchirées » entre deux
        # chunks, sans conséquence : flags monotones, re-poll 2 s plus tard, et
        # toute écriture re-vérifie sa valeur FRAÎCHE sous halt avant d'écrire.
        if not self.gdb.no_halt:
            await self.gdb.interrupt()
        else:
            # Resynchronisation PÉRIODIQUE du flux (revue 2026-07-26) : en mode
            # halt, interrupt() drainait les paquets parasites à chaque cycle ;
            # sans halt il faut le faire explicitement, sinon une réponse
            # abandonnée (timeout/cancel) décale TOUTES les réponses suivantes
            # d'un cran -> données de la mauvaise adresse acceptées comme
            # valides -> faux checks. Coût : ~50 ms sans halt (le jeu tourne).
            await self.gdb._drain()
        try:
            # SNAPSHOT INVENTAIRE pris au DÉBUT du cycle, AVANT le bloc de flags
            # (revue 2026-07-26). Il devient _prev_inv en fin de cycle. Invariant
            # requis par la neutralisation de coffre : pour tout bit détecté au
            # cycle suivant, _prev_inv doit dater d'AVANT l'ouverture. Comme le
            # bit est lu APRÈS ce snapshot, toute ouverture postérieure au bloc
            # de CE cycle (y compris pendant le corps du poll en mode no_halt)
            # est vue au cycle suivant avec un _prev_inv antérieur -> delta juste.
            # (Avant : _prev_inv relu en FIN de poll -> un coffre ouvert pendant
            # le poll entrait dans _prev_inv AVANT que son bit soit vu -> delta
            # nul -> item natif jamais retiré, définitivement.)
            inv_snapshot = self._parse_inventory(
                await self.gdb.read_memory(INVENTORY_BASE, 0x800))
            # --- LECTURE GROUPÉE (perf, Doteos 2026-07-26) --------------------
            # Presque TOUT ce qu'on lit par cycle tient dans UNE plage contiguë de
            # la save (0x086CFA24..0x086D023B) : compteur de chapitre, les ~28 flags
            # d'event, wanted, rang, + les bitfields chest/medallium/tablo. Avant, on
            # faisait ~34 petites lectures GDB séparées, chacune pendant que l'ému est
            # HALTÉE -> mini-freeze en jeu. On lit désormais ce bloc EN UNE FOIS puis
            # on tranche en mémoire (1 aller-retour au lieu de ~34).
            flag_regions = {name for name, _ in FLAG_TABLES}
            _BLK_BASE = 0x086CFA24
            _BLK_SIZE = 0x818                 # jusqu'au rang 0x086D023A inclus
            _blob = await self.gdb.read_memory(_BLK_BASE, _BLK_SIZE)

            def _peek(addr: int, n: int):
                """Tranche depuis le bloc groupé ; None si hors bloc (repli direct)."""
                off = addr - _BLK_BASE
                return _blob[off:off + n] if 0 <= off and off + n <= len(_blob) else None

            readings: Dict[str, bytes] = {}
            for region_name, (address, size) in MEMORY_REGIONS.items():
                if address and region_name in flag_regions:
                    readings[region_name] = (_peek(address, size)
                                             or await self.gdb.read_memory(address, size))
            chapter_raw = _peek(STORY_CHAPTER_ADDR, 2)
            quest_raw = await self.gdb.read_memory(LAST_QUEST_DONE_HASH_ADDR, 4)  # hors bloc
            wanted_raw = _peek(*WANTED_FLAGS_REGION)
            rank_raw = _peek(WATCH_RANK_VALUE_ADDR, 1)
            # Flags d'event servant de CHECK (tranchés du bloc, valeur « débloqué »
            # que le jeu vient de poser). mask = bit ; u16 = valeur exacte.
            event_flags_set = set()
            _chapter_now = int.from_bytes(chapter_raw, "little")
            # Garde anti-ZÉROS (revue 2026-07-26) : en mode no_halt, une lecture
            # qui échoue en marche ('E..' zéro-remplie par read_memory) donnerait
            # un cycle entier « tout à zéro » silencieux (chapitre 0, aucun flag).
            # Si on a DÉJÀ vu une save chargée (chapitre >= 1) et que le chapitre
            # retombe à 0, le cycle est suspect : on l'IGNORE (aucun cache/check
            # touché) ; 3 d'affilée -> le mode no_halt est désactivé.
            if _chapter_now >= 1:
                self._seen_chapter_ge1 = True
                self._nh_zero_strikes = 0
            elif self.gdb.no_halt and getattr(self, "_seen_chapter_ge1", False):
                # Confirmation SOUS HALT (une lecture atomique) : distingue la
                # vraie panne de lecture d'un retour LÉGITIME au menu titre.
                _own = await self.gdb.begin_halt()
                try:
                    _fresh = await self.gdb.read_memory(STORY_CHAPTER_ADDR, 2)
                finally:
                    if _own:
                        await self.gdb.cont()
                if int.from_bytes(_fresh, "little") >= 1:
                    # le halt lit un chapitre valide -> les lectures en marche
                    # étaient bien bogus : cycle ignoré, strike.
                    self._nh_zero_strikes = getattr(self, "_nh_zero_strikes",
                                                    0) + 1
                    if self._nh_zero_strikes >= 3:
                        self.gdb.no_halt = False
                        logger.info("Lectures sans pause : données incohérentes "
                                    "(3 cycles à zéro) -> retour au mode halt.")
                    return
                # chapitre 0 confirmé (menu / pas de save) : cycle normal ; se
                # ré-armera au prochain chargement (chapitre >= 1).
                self._seen_chapter_ge1 = False
            for _ev in EVENT_CHECK_FLAGS:
                # Garde-fou chapitre : certains signaux (ex. Modèle zéro détecté par
                # le compteur de PAS 0x086CFA26==0x14, partagé) repassent par leur
                # valeur à des chapitres antérieurs -> faux positif (check lâché trop
                # tôt, bug Doteos 2026-07-25 : Modèle zéro validé au chap 3). On
                # n'accepte le signal que si le chapitre courant atteint min_chapter.
                if _chapter_now < _ev.get("min_chapter", 0):
                    continue
                if "u16" in _ev:
                    _raw = _peek(_ev["addr"], 2)
                    if _raw is not None and int.from_bytes(_raw, "little") == _ev["u16"]:
                        event_flags_set.add(_ev["location"])
                else:
                    _b = _peek(_ev["addr"], 1)
                    if _b is not None and _b[0] & _ev["mask"]:
                        event_flags_set.add(_ev["location"])
            # --- BOSS : victoire GÉNÉRIQUE (Doteos 2026-07-28) -----------------
            # 1) un bit MÉDALLIUM mappé qui s'allume = boss RENCONTRÉ -> on arme.
            # 2) le check ne part qu'à la FIN du combat, si on n'a pas vu l'écran
            #    « Perdu » (état 3). Une défaite laisse le boss armé pour le
            #    prochain essai. Coût : 1 lecture de l'état de combat, uniquement
            #    quand un boss est en attente.
            _md_now = _peek(0x086CFEBC, 0x80)
            if _md_now is not None:
                if self._prev_medallium is not None:
                    for _i, (_o, _n) in enumerate(zip(self._prev_medallium, _md_now)):
                        _g = _n & ~_o
                        if not _g:
                            continue
                        for _b in range(8):
                            if _g & (1 << _b):
                                _loc = MEDALLIUM_BIT_TO_LOCATION.get(_i * 8 + _b)
                                if _loc and _loc not in self._boss_won:
                                    self._boss_pending.add(_loc)
                                    logger.info("Boss rencontré : %s — le check "
                                                "partira à la victoire.", _loc)
                self._prev_medallium = _md_now
            if self._boss_pending:
                _st = int.from_bytes(
                    await self.gdb.read_memory(BATTLE_STATE_ADDR, 4), "little")
                if _st != 0:
                    # EN COMBAT : défaite = équipe ANÉANTIE (tous les PV de combat
                    # LIVE à 0 alors que la struct existe). ⚠️ Ne PAS se fier à
                    # l'état 3 : il apparaît aussi en VICTOIRE (constaté en jeu
                    # par Doteos 2026-07-29 — « perdu » loggué sur un combat
                    # gagné). Même signal que le DeathLink, validé en jeu.
                    _mx = _cur = False
                    for _s in range(PARTY_SLOT_COUNT):
                        _pair = await self.gdb.read_memory(
                            BATTLE_HP_FIRST_ADDR + _s * BATTLE_HP_ENTRY_STRIDE, 4)
                        if struct.unpack_from("<H", _pair, 0)[0]:
                            _mx = True
                        if struct.unpack_from("<H", _pair, 2)[0]:
                            _cur = True
                    if _mx and not _cur:
                        self._boss_lost = True
                if self._prev_battle_state != 0 and _st == 0:
                    if self._boss_lost:
                        logger.info("Combat de boss PERDU -> aucun check envoyé "
                                    "(%d boss toujours en attente).",
                                    len(self._boss_pending))
                    else:
                        for _loc in sorted(self._boss_pending):
                            logger.info("Boss VAINCU : %s", _loc)
                        self._boss_won |= self._boss_pending
                        self._boss_pending = set()
                    self._boss_lost = False
                self._prev_battle_state = _st
            # victoires confirmées -> checks (dédupliqués par _queue_check)
            event_flags_set |= self._boss_won

            # DeathLink : lectures (état + PV de combat LIVE) + kill éventuel
            # — tout est dans _deathlink_scan (partagé avec la sonde ~1 s).
            # None si DeathLink inactif (aucun coût GDB).
            deathlink_scan = await self._deathlink_scan()
            # Un coffre vient-il d'être ouvert ? On ne déclenche la neutralisation
            # QUE si un bit de COFFRE MAPPÉ (un vrai check, CHEST_BIT_TO_LOCATION)
            # passe à 1. Le bitfield 0x086CFE00 contient AUSSI des flags non-coffres
            # (ramassages normaux, story) : sans ce filtre, ramasser un item normal
            # déclenchait à tort la neutralisation et RETIRAIT l'item (bug Doteos).
            # REGISTRE-BASED (Doteos 2026-07-19) : on collecte le hash natif EXACT
            # de chaque coffre mappé qui vient de s'ouvrir. On ne retire QUE ces
            # hash -> le bruit multiworld (autres items apparus) est ignoré (fini
            # le garde-fou fragile « >2 types = annule »).
            opened_native_hashes: set = set()
            chest_cur = readings.get("chest_flags")
            if chest_cur is not None:
                chest_prev = self.flag_cache.get("chest_flags")
                if chest_prev is not None:
                    for bit in new_set_bits(chest_prev, chest_cur):
                        h = CHEST_BIT_TO_NATIVE_HASH.get(bit)
                        if h is not None:
                            opened_native_hashes.add(h)
            # Coffre ouvert -> relecture FRAÎCHE de l'inventaire SOUS HALT (revue
            # 2026-07-26) : le snapshot de début de cycle peut précéder de peu
            # l'ouverture (item pas encore dedans) et, en mode no_halt, un dump
            # pris en marche peut être déchiré. La lecture haltée est atomique et
            # postérieure à l'ouverture -> `added` = current - _prev_inv(avant
            # ouverture) - livraisons du cycle précédent : exact. PRÉ-livraison
            # (les livraisons de CE cycle arrivent après).
            current_inv: Optional[Dict[int, int]] = None
            if opened_native_hashes:
                own = await self.gdb.begin_halt()
                try:
                    current_inv = self._parse_inventory(
                        await self.gdb.read_memory(INVENTORY_BASE, 0x800))
                finally:
                    if own:
                        await self.gdb.cont()
            # Livraison des items reçus (renseigne _delivered_this_poll).
            self._delivered_this_poll = {}
            await self.deliver_pending_items()
            # Rang de montre : force-write si les items AP dépassent le rang
            # en jeu (rank_raw = lecture PRÉ-livraison -> aucun incrément vu
            # sur ce poll ; les suivants sont couverts par le plancher).
            chapter = int.from_bytes(chapter_raw, "little")
            await self._deliver_watch_rank(chapter, rank_raw)
            # Retrait de l'item natif du coffre (design unifié : ne garder que
            # l'item AP) — compare à la lecture RÉELLE du poll précédent.
            if opened_native_hashes:
                await self._neutralize_native_chest(
                    current_inv, opened_native_hashes)
            # Item AP dédié (« Parchemin En nyavant » -> affiché « Item AP ») :
            # une quête portant un item ÉTRANGER donne cet item en récompense
            # (juste pour l'affichage en jeu). Doteos ne doit PAS le garder :
            # dès qu'il apparaît, on le retire (jamais obtenu légitimement -> aucun
            # risque de fausse suppression). ⚠️ C'est un OBJET-CLÉ (pas l'inventaire
            # normal !) -> on le cherche dans la liste des objets-clés (bug 2026-07-24
            # signalé par Doteos : cherché à tort dans INVENTORY_BASE -> jamais retiré).
            # Liste d'objets-clés lue UNE fois (cache compteur) et PARTAGÉE entre
            # le check « Item AP dédié » et la neutralisation (perf 2026-07-26).
            ki_present = await self._key_items_cached()
            if mod_patcher.DEDICATED_AP_ITEM_HASH in ki_present:
                if await self._remove_from_key_items(
                        mod_patcher.DEDICATED_AP_ITEM_HASH):
                    logger.info("Item AP dédié (récompense de quête étrangère) "
                                "retiré des objets-clés.")
                    ki_present = await self._key_items_cached()  # relu (invalidé)
            # Shuffle DUR des objets-clés : retire les dons natifs (histoire)
            # que le joueur n'a pas reçus d'AP. + Hard-gates de zone : maintient une
            # zone VERROUILLÉE tant que son objet-clé AP n'est pas reçu (progression
            # scénario forcée). Uniquement en shuffle dur (sinon vanilla : la clé
            # n'est jamais « reçue » d'AP -> ne pas verrouiller à vie).
            if getattr(self, "_hard_key_shuffle", False):
                await self._neutralize_native_key_items(present=ki_present)
                await self._enforce_story_gates(peek=_peek)
            # Mémorise l'état de CE poll pour le diff du prochain : _prev_inv =
            # le SNAPSHOT de DÉBUT de cycle (antérieur au bloc de flags -> cf.
            # invariant en tête de poll). Les livraisons de CE cycle (postérieures
            # au snapshot) sont couvertes par _delivered_last_poll (soustrait au
            # calcul `added` du cycle suivant) ; les retraits de coffre de CE
            # cycle donnent un delta négatif au prochain (ignoré par `added > 0`).
            self._poll_n = getattr(self, "_poll_n", 0) + 1
            self._prev_inv = inv_snapshot
            self._delivered_last_poll = dict(self._delivered_this_poll)
        finally:
            await self.gdb.cont()

        new_checks: List[int] = []

        # 1) Bitfields (coffres, etc.) : chaque bit 0->1 -> une location.
        # À la première lecture, on compare à "tout à zéro" pour resynchroniser
        # les checks déjà accomplis avant la connexion (le serveur ignore les
        # doublons). Ensuite on ne réagit qu'aux nouveaux bits.
        for region_name, bit_table in FLAG_TABLES:
            if region_name not in readings:
                continue
            current = readings[region_name]
            previous = self.flag_cache.get(region_name)
            self.flag_cache[region_name] = current
            if previous is None:
                previous = bytes(len(current))
            for bit in new_set_bits(previous, current):
                self._queue_check(bit_table.get(bit), new_checks)

        # 2) Histoire : le compteur de chapitre donne les chapitres terminés.
        chapter = int.from_bytes(chapter_raw, "little")
        if chapter != getattr(self, "_dbg_prev_chapter", None):
            _cl = {n: self.chapter_locations.get(n) for n
                   in chapters_completed(chapter)}
            _miss = {n: (self.chapter_locations.get(n) in LOCATION_NAME_TO_ID
                         and LOCATION_NAME_TO_ID[self.chapter_locations[n]]
                         in self.missing_locations)
                     for n in chapters_completed(chapter)}
            logger.info("[diag] compteur chapitre = %d ; terminés = %s ; "
                        "locations = %s ; encore manquantes = %s",
                        chapter, chapters_completed(chapter), _cl, _miss)
            self._dbg_prev_chapter = chapter
        for chapter_num in chapters_completed(chapter):
            self._queue_check(self.chapter_locations.get(chapter_num), new_checks)

        # 2b) Victoire (goal). Le boss final Lady Démona vaincu = le compteur
        # d'histoire passe à 11 (VÉRIFIÉ en jeu : 10 -> 11 à sa défaite). Pour le
        # goal « final_boss » (et « story_100 »), on envoie CLIENT_GOAL dès
        # chapitre >= 11. Les goals post-game (Potofeu/Filomène, légendaires…)
        # auront leur propre condition quand leur détection sera faite.
        if not self._goal_sent:
            goal = self.slot_data.get("goal", 0)
            if 1 <= chapter < 11:
                # chapitre 0 exclu (revue 2026-07-26) : 0 = pas de save chargée
                # OU lecture transitoirement zéro-remplie ('E..' en marche) ->
                # ne doit PAS armer le garde anti-fausse-victoire.
                self._seen_pre_goal = True   # on a vu l'avant-goal EN JEU
            # Garde-fou anti FAUSSE VICTOIRE : on n'envoie CLIENT_GOAL que si on a
            # VU un chapitre < 11 cette session (sinon un compteur PÉRIMÉ à >=11 à
            # la connexion déclencherait une victoire immédiate). 0=final_boss,
            # 1=story_100.
            if goal in (0, 1) and chapter >= 11 and self._seen_pre_goal:
                self._goal_sent = True
                await self.send_msgs([{"cmd": "StatusUpdate",
                                       "status": ClientStatus.CLIENT_GOAL}])
                self.finished_game = True

        # 3) Quêtes : hash (transitoire) de la dernière quête terminée. On ne
        # réagit qu'aux changements ; les quêtes principales d'histoire (sans
        # location) sont ignorées silencieusement.
        quest_hash = int.from_bytes(quest_raw, "little")
        if quest_hash and quest_hash != self.last_quest_hash:
            self.last_quest_hash = quest_hash
            self._queue_check(self.quest_hash_locations.get(quest_hash), new_checks)

        # 4) Yo-criminels : popcount du bitfield WANTED = nb de captures ->
        # chaque palier atteint devient un check (re-queuer est idempotent).
        caught = sum(bin(byte).count("1") for byte in wanted_raw)
        for milestone, loc_name in self.criminel_locations.items():
            if caught >= milestone:
                self._queue_check(loc_name, new_checks)

        # 5) Rang de montre : l'octet WATCH_RANK_VALUE_ADDR vaut le rang courant
        # (0=E .. 5=S). On fire « Obtenons le rang X » UNIQUEMENT sur un
        # INCRÉMENT réel (franchissement en jeu), PAS sur la valeur absolue :
        # sinon une valeur PÉRIMÉE (nouvelle partie juste après une save rang A ->
        # l'octet garde 4 un moment) déclenche faussement C/B/A. Le baseline est
        # pris au 1er poll (aucun fire).
        rank_value = rank_raw[0] if rank_raw else 0
        # PLAFOND par chapitre : le rang ne peut pas dépasser ce qui est
        # obtenable au chapitre courant (D=Ch3, C=Ch6, B=Ch7, A=Ch9, S=Ch11).
        # Neutralise les valeurs PÉRIMÉES/fluctuantes de 0x086D023A pendant le
        # chargement d'une nouvelle partie (ex. octet à 4 alors qu'on est au Ch1).
        _max_rank = (5 if chapter >= 11 else 4 if chapter >= 9 else
                     3 if chapter >= 7 else 2 if chapter >= 6 else
                     1 if chapter >= 3 else 0)
        rank_value = min(rank_value, _max_rank)
        # GARDE-FOU force-write (design 2026-07-16 : l'item AP DONNE le rang) :
        # un incrément <= plancher AP vient d'une LIVRAISON, pas d'une quête ->
        # aucun check. Les rangs gagnés en quête avec un rang déjà >= via AP ne
        # produisent plus d'incrément : leurs checks passent par le hash de
        # quête (Obtenons le rang C/B/A/S ont tous un hash, détection quêtes).
        _ap_floor = self._ap_rank_floor()
        if self._prev_rank_value is not None and rank_value > self._prev_rank_value:
            for rank_level, loc_name in self.rank_quest_locations.items():
                if (self._prev_rank_value < rank_level <= rank_value
                        and rank_level > _ap_floor):
                    self._queue_check(loc_name, new_checks)
        self._prev_rank_value = rank_value

        # 6) DeathLink : détection sur les PV de COMBAT LIVE (le tableau
        # d'équipe est figé en combat et réécrit soigné à la défaite ->
        # inutilisable, vérifié live). Logique partagée avec la sonde ~1 s.
        if deathlink_scan is not None:
            await self._deathlink_evaluate(*deathlink_scan)

        # 7) Checks déclenchés par un FLAG d'EVENT (et non par un objet) : le check
        # part quand le joueur FAIT l'événement, quel que soit son choix (ex. le
        # choix des beignets du Ch4 -> bit commun aux deux beignets, jamais manquable).
        for _loc in event_flags_set:
            self._queue_check(_loc, new_checks)

        if new_checks:
            await self.send_msgs([{"cmd": "LocationChecks",
                                   "locations": new_checks}])


async def game_watcher(ctx: YKW2Context) -> None:
    """Boucle de surveillance mémoire -> checks Archipelago."""
    while not ctx.exit_event.is_set():
        try:
            if ctx.gdb.connected and ctx.slot_data and memory_map_ready():
                async with ctx.gdb.io_lock:
                    await ctx.poll_game()
        except (ConnectionError, asyncio.TimeoutError, OSError) as error:
            logger.error("Connexion émulateur perdue : %s: %s. Refaites /citra "
                         "(redémarrez Azahar si la reconnexion est refusée).",
                         type(error).__name__, error or "timeout")
            # On ne compte comme « instabilité du no_halt » que les TIMEOUTS (le
            # stub a cessé de répondre) — PAS les ConnectionError (fermeture ou
            # redémarrage NORMAL d'Azahar, revue 2026-07-26 : sinon 2 relances de
            # l'ému suffisaient à désactiver le mode à vie). Au bout de 2, retour
            # sticky au mode halt classique pour la session.
            if ctx.gdb.no_halt and isinstance(error, asyncio.TimeoutError):
                ctx._no_halt_losses = getattr(ctx, "_no_halt_losses", 0) + 1
                if ctx._no_halt_losses >= 2:
                    logger.info("Lectures sans pause désactivées pour la "
                                "session (2 pertes par timeout).")
            # close() sous io_lock (revue 2026-07-26) : sinon course avec un
            # /citra concurrent (attach_emulator tient le verrou pendant
            # connect+probe) -> lecture simultanée du même StreamReader ->
            # RuntimeError qui tuait la boucle game_watcher.
            async with ctx.gdb.io_lock:
                await ctx.gdb.close()
            ctx.flag_cache.clear()
            # Rang : l'attendu vient de l'ANCIENNE session d'émulation (le joueur
            # peut recharger une autre save) -> repartir en mode resync prudent.
            ctx._rank_expected = None
            ctx._ki_cache = None
            # DeathLink : l'armement et les lectures « poll précédent »
            # viennent de l'ANCIENNE session d'émulation (le joueur peut
            # relancer Azahar / charger une autre save) -> on repart de zéro
            # pour ne jamais envoyer une mort sur la foi d'un état périmé.
            # Les morts reçues en attente (_deathlink_pending) sont
            # CONSERVÉES : elles seront appliquées à la reconnexion (choix
            # assumé : les PV à 0 restent soignables, pas de vraie perte).
            ctx._can_send_death = False
            ctx._death_to_send = False
            ctx._prev_live_alive = False
        except Exception:
            # Toute AUTRE erreur (KeyError, struct, etc.) stoppait AVANT
            # silencieusement la boucle -> plus aucune détection. On la loggue
            # (avec traceback) et on CONTINUE (poll résilient).
            logger.exception("Erreur inattendue dans poll_game "
                             "(loggée, le poll continue) :")
        # Entre deux gros polls : sonde DeathLink légère pour ne pas rater un écran
        # « Perdu... » fermé vite. CHAQUE sonde HALTE l'ému -> pour limiter les
        # mini-freeze (Doteos 2026-07-26), on ne sonde qu'UNE fois par cycle (au
        # milieu), pas toutes les secondes. DeathLink reste évalué à chaque gros
        # poll ; la sonde n'ajoute qu'une résolution intermédiaire. No-op si
        # DeathLink inactif (aucun halt). Erreur de sonde = silencieuse.
        _steps = max(1, int(POLL_INTERVAL))
        # (_steps-1)//2 : pour 2 pas -> sonde après le 1er sleep = MILIEU du cycle
        # (revue 2026-07-26 : _steps//2 la plaçait en FIN de cycle, collée au poll
        # suivant -> double halt dos à dos et espacement inutile).
        _probe_at = (_steps - 1) // 2           # une seule sonde, au milieu du cycle
        for _i in range(_steps):
            await asyncio.sleep(1.0)
            if _i != _probe_at:
                continue
            if "DeathLink" not in ctx.tags and not ctx._deathlink_pending:
                continue                        # DeathLink off -> pas de halt inutile
            try:
                if ctx.gdb.connected and ctx.slot_data and memory_map_ready():
                    async with ctx.gdb.io_lock:
                        await ctx._deathlink_probe()
            except Exception:  # noqa: BLE001
                pass


def launch(*launch_args: str) -> None:
    async def main(args) -> None:
        ctx = YKW2Context(args.connect, args.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        watcher = asyncio.create_task(game_watcher(ctx), name="game watcher")
        await ctx.exit_event.wait()
        watcher.cancel()
        await ctx.shutdown()

    parser = get_base_parser(description="Yo-kai Watch 2 Archipelago client.")
    args = parser.parse_args(launch_args)
    Utils.init_logging("YoKaiWatch2Client", exception_logger="Client")
    import colorama
    colorama.just_fix_windows_console()
    asyncio.run(main(args))
    colorama.deinit()


if __name__ == "__main__":
    launch()
