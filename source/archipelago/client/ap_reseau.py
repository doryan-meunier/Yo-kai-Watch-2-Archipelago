"""Client du protocole réseau Archipelago, en bibliothèque standard seulement (asyncio, ssl, zlib).

Deux couches :
1. `WebSocket` : websocket RFC 6455 écrit à la main (poignée de main HTTP « Upgrade », trames texte et
   binaires, fragmentation, masquage des trames du client, ping/pong, fermeture), ws:// et wss:// (ssl),
   compression « permessage-deflate » (RFC 7692, zlib) : la doc d'Archipelago annonce que les connexions
   non compressées sont dépréciées.
2. `ClientAP` : protocole Archipelago (docs/network protocol.md du dépôt ArchipelagoMW/Archipelago) :
   RoomInfo, GetDataPackage/DataPackage (avec cache disque facultatif), Connect/Connected/ConnectionRefused,
   ReceivedItems (index, resynchronisation par Sync), LocationChecks, LocationScouts/LocationInfo,
   StatusUpdate (CLIENT_GOAL), PrintJSON (texte lisible), RoomUpdate, Say, Bounce/Bounced et DeathLink,
    indices (hints) du slot : Get + SetNotify sur la clé `_read_hints_{team}_{slot}` du data storage, Retrieved / SetReply,
   UpdateHint (priorité d'un indice), ConnectUpdate, InvalidPacket ; reconnexion automatique avec délai croissant.

Le client ne dépend ni du jeu ni du pont GDB : la synchronisation boîte ↔ serveur (C3) s'y branche par les
rappels `sur_*` (fonctions ordinaires ou coroutines) et par les méthodes d'envoi.

Exemple :
    client = ClientAP("archipelago.gg:38281", "Joueur1", mot_de_passe="", dossier_cache=Path("cache"))
    client.sur_objets = lambda objets, debut: print(objets[debut:])
    tache = asyncio.create_task(client.executer())
    await client.attendre_connexion()
    await client.verifier_locations([59421001])
    await client.signaler_victoire()
    await client.arreter()
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import inspect
import json
import logging
import os
import re
import ssl
import struct
import time
import uuid as uuid_mod
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

JEU = "Yo-kai Watch 2"
# Les deux mondes du mod (apworld français / anglais) : même jeu, mêmes identifiants, seul le nom diffère. Le serveur
# refuse (InvalidGame) un Connect dont le nom de jeu n'est pas celui du slot : le client essaie donc l'autre nom avant
# de tenir le refus pour définitif (défaut de la 2.0.0 : un slot du monde anglais ne pouvait pas se connecter).
JEUX = (JEU, "Yo-kai Watch 2 (English)")
PORT_DEFAUT = 38281
VERSION_AP = (0, 6, 7)                  # version du protocole annoncée (Archipelago 0.6.7 installé chez l'humain)
# items_handling : 0b001 objets des autres mondes, 0b010 de son propre monde, 0b100 inventaire de départ
OBJETS_AUTRES, OBJETS_PROPRES, OBJETS_DEPART = 0b001, 0b010, 0b100
# ClientStatus
CLIENT_UNKNOWN, CLIENT_CONNECTED, CLIENT_READY, CLIENT_PLAYING, CLIENT_GOAL = 0, 5, 10, 20, 30
# NetworkItem.flags
PROGRESSION, UTILE, PIEGE = 0b001, 0b010, 0b100
# erreurs de ConnectionRefused après lesquelles réessayer ne sert à rien
REFUS_DEFINITIFS = {"InvalidSlot", "InvalidGame", "IncompatibleVersion", "InvalidPassword", "InvalidItemsHandling"}

GUID_WS = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_SUITE, OP_TEXTE, OP_BINAIRE, OP_FERMER, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
QUEUE_DEFLATE = b"\x00\x00\xff\xff"


# ================================================================================================ websocket
class ErreurWebSocket(Exception):
    """Erreur de connexion ou de protocole websocket."""


class FermetureWebSocket(ErreurWebSocket):
    """La connexion websocket est fermée (par le pair, ou par nous)."""

    def __init__(self, code: int = 1006, raison: str = ""):
        super().__init__(f"websocket fermé ({code}{' ' + raison if raison else ''})")
        self.code, self.raison = code, raison


def cle_acceptation(cle: str) -> str:
    """Sec-WebSocket-Accept attendu pour une Sec-WebSocket-Key."""
    return base64.b64encode(hashlib.sha1((cle + GUID_WS).encode()).digest()).decode()


def appliquer_masque(donnees: bytes, masque: bytes) -> bytes:
    if not donnees:
        return b""
    n = len(donnees)
    m = int.from_bytes((masque * (n // 4 + 1))[:n], "little")
    return (int.from_bytes(donnees, "little") ^ m).to_bytes(n, "little")


def encoder_trame(opcode: int, charge: bytes, *, masque: bytes | None = None, fin: bool = True,
                  rsv1: bool = False) -> bytes:
    """Trame websocket. `masque` (4 octets) : obligatoire pour les trames du client, absent côté serveur."""
    b0 = (0x80 if fin else 0) | (0x40 if rsv1 else 0) | opcode
    n = len(charge)
    bit = 0x80 if masque is not None else 0
    if n < 126:
        tete = struct.pack("!BB", b0, bit | n)
    elif n < 1 << 16:
        tete = struct.pack("!BBH", b0, bit | 126, n)
    else:
        tete = struct.pack("!BBQ", b0, bit | 127, n)
    if masque is None:
        return tete + charge
    return tete + masque + appliquer_masque(charge, masque)


@dataclass
class Trame:
    fin: bool
    rsv1: bool
    opcode: int
    charge: bytes


async def lire_trame(lecteur: asyncio.StreamReader, *, masquee_attendue: bool, taille_max: int) -> Trame:
    """Lit une trame. `masquee_attendue` : vrai côté serveur (le client doit masquer), faux côté client."""
    try:
        b0, b1 = await lecteur.readexactly(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack("!H", await lecteur.readexactly(2))[0]
        elif n == 127:
            n = struct.unpack("!Q", await lecteur.readexactly(8))[0]
        if n > taille_max:
            raise ErreurWebSocket(f"trame trop grande ({n} octets)")
        masquee = bool(b1 & 0x80)
        if masquee != masquee_attendue:
            raise ErreurWebSocket("masquage de trame incorrect")
        masque = await lecteur.readexactly(4) if masquee else None
        charge = await lecteur.readexactly(n) if n else b""
    except asyncio.IncompleteReadError as e:
        raise FermetureWebSocket(1006, "connexion interrompue") from e
    if masque:
        charge = appliquer_masque(charge, masque)
    if b0 & 0x30:
        raise ErreurWebSocket("bits RSV2/RSV3 inattendus")
    return Trame(bool(b0 & 0x80), bool(b0 & 0x40), b0 & 0x0F, charge)


def analyser_extensions(valeur: str) -> dict[str, dict[str, str | None]]:
    """« permessage-deflate; a; b=10, x » -> {"permessage-deflate": {"a": None, "b": "10"}, "x": {}}."""
    res: dict[str, dict[str, str | None]] = {}
    for ext in (v.strip() for v in valeur.split(",") if v.strip()):
        morceaux = [m.strip() for m in ext.split(";")]
        params: dict[str, str | None] = {}
        for p in morceaux[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.strip().lower()] = v.strip().strip('"')
            elif p:
                params[p.lower()] = None
        res[morceaux[0].lower()] = params
    return res


class Deflate:
    """État « permessage-deflate » d'une extrémité (RFC 7692)."""

    def __init__(self, bits_envoi: int = 15, bits_reception: int = 15, reinit_envoi: bool = False,
                 reinit_reception: bool = False, seuil: int = 32):
        # zlib ne sait pas produire une fenêtre de 8 bits en deflate brut : on n'envoie alors pas compressé
        self.compresser_actif = bits_envoi >= 9
        self.bits_envoi, self.bits_reception = max(bits_envoi, 9), bits_reception
        self.reinit_envoi, self.reinit_reception = reinit_envoi, reinit_reception
        self.seuil = seuil
        self._comp = zlib.compressobj(6, zlib.DEFLATED, -self.bits_envoi)
        self._decomp = zlib.decompressobj(-self.bits_reception)

    @classmethod
    def depuis_reponse(cls, params: dict[str, str | None], cote_client: bool = True) -> "Deflate":
        """Paramètres négociés (réponse du serveur) -> état de ce côté."""
        def bits(nom):
            v = params.get(nom)
            return int(v) if v else 15
        if cote_client:
            return cls(bits("client_max_window_bits"), bits("server_max_window_bits"),
                       "client_no_context_takeover" in params, "server_no_context_takeover" in params)
        return cls(bits("server_max_window_bits"), bits("client_max_window_bits"),
                   "server_no_context_takeover" in params, "client_no_context_takeover" in params)

    def compresser(self, donnees: bytes) -> bytes | None:
        """Message compressé (sans la queue 00 00 ff ff), ou None s'il faut l'envoyer tel quel."""
        if not self.compresser_actif or len(donnees) < self.seuil:
            return None
        if self.reinit_envoi:
            self._comp = zlib.compressobj(6, zlib.DEFLATED, -self.bits_envoi)
        c = self._comp.compress(donnees) + self._comp.flush(zlib.Z_SYNC_FLUSH)
        return c[:-4] if c.endswith(QUEUE_DEFLATE) else c

    def decompresser(self, donnees: bytes, taille_max: int) -> bytes:
        if self.reinit_reception:
            self._decomp = zlib.decompressobj(-self.bits_reception)
        try:
            out = self._decomp.decompress(donnees + QUEUE_DEFLATE, taille_max + 1)
        except zlib.error as e:
            raise ErreurWebSocket(f"message compressé invalide ({e})") from e
        if len(out) > taille_max or self._decomp.unconsumed_tail:
            raise ErreurWebSocket("message décompressé trop grand")
        return out


class WebSocket:
    """Connexion websocket établie (côté client par défaut). Un seul lecteur à la fois (`recevoir`) ;
    les envois sont sérialisés par un verrou."""

    def __init__(self, lecteur: asyncio.StreamReader, ecrivain: asyncio.StreamWriter, *, client: bool = True,
                 deflate: Deflate | None = None, taille_max: int = 64 << 20):
        self.lecteur, self.ecrivain = lecteur, ecrivain
        self.client = client
        self.deflate = deflate
        self.taille_max = taille_max
        self.fermee = False
        self.derniere_reception = time.monotonic()
        self._verrou = asyncio.Lock()

    # ---------------------------------------------------------------- ouverture
    @classmethod
    async def connecter(cls, url: str, *, delai: float = 10.0, ssl_ctx: ssl.SSLContext | None = None,
                        compression: bool = True, taille_max: int = 64 << 20) -> "WebSocket":
        """Ouvre ws://hote:port/chemin ou wss://… et fait la poignée de main HTTP « Upgrade »."""
        u = urlsplit(url)
        if u.scheme not in ("ws", "wss") or not u.hostname:
            raise ErreurWebSocket(f"adresse websocket invalide : {url!r}")
        securise = u.scheme == "wss"
        port = u.port or (443 if securise else 80)
        if securise and ssl_ctx is None:
            ssl_ctx = ssl.create_default_context()
        try:
            lecteur, ecrivain = await asyncio.wait_for(
                asyncio.open_connection(u.hostname, port, ssl=ssl_ctx if securise else None,
                                        server_hostname=u.hostname if securise else None,
                                        limit=1 << 20),
                timeout=delai)
        except (OSError, asyncio.TimeoutError, ssl.SSLError) as e:
            raise ErreurWebSocket(f"connexion à {url} impossible : {e or type(e).__name__}") from e
        try:
            ws = await asyncio.wait_for(cls._poignee_de_main(lecteur, ecrivain, u, port, compression, taille_max),
                                        timeout=delai)
        except BaseException as e:
            ecrivain.close()
            if isinstance(e, asyncio.TimeoutError):
                raise ErreurWebSocket(f"poignée de main websocket sans réponse ({url})") from e
            if isinstance(e, (OSError, asyncio.IncompleteReadError, ssl.SSLError)):
                raise ErreurWebSocket(f"poignée de main websocket interrompue ({url}) : {e}") from e
            raise
        return ws

    @classmethod
    async def _poignee_de_main(cls, lecteur, ecrivain, u, port, compression, taille_max) -> "WebSocket":
        cle = base64.b64encode(os.urandom(16)).decode()
        hote = u.hostname if port in (80, 443) else f"{u.hostname}:{port}"
        if ":" in (u.hostname or "") and not hote.startswith("["):     # IPv6
            hote = f"[{u.hostname}]" + (f":{port}" if port not in (80, 443) else "")
        chemin = (u.path or "/") + (f"?{u.query}" if u.query else "")
        lignes = [f"GET {chemin} HTTP/1.1", f"Host: {hote}", "Upgrade: websocket", "Connection: Upgrade",
                  f"Sec-WebSocket-Key: {cle}", "Sec-WebSocket-Version: 13", "User-Agent: ykw2ap"]
        if compression:
            lignes.append("Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits")
        ecrivain.write(("\r\n".join(lignes) + "\r\n\r\n").encode())
        await ecrivain.drain()
        brut = await lecteur.readuntil(b"\r\n\r\n")
        tete = brut.decode("latin-1").split("\r\n")
        m = re.match(r"HTTP/1\.[01] (\d{3})", tete[0])
        if not m or m.group(1) != "101":
            raise ErreurWebSocket(f"le serveur refuse le websocket : {tete[0]!r}")
        entetes = {}
        for ligne in tete[1:]:
            if ":" in ligne:
                k, v = ligne.split(":", 1)
                k = k.strip().lower()
                entetes[k] = f"{entetes[k]}, {v.strip()}" if k in entetes else v.strip()
        if entetes.get("upgrade", "").lower() != "websocket" or \
                "upgrade" not in entetes.get("connection", "").lower():
            raise ErreurWebSocket("réponse « Upgrade » invalide")
        if entetes.get("sec-websocket-accept") != cle_acceptation(cle):
            raise ErreurWebSocket("Sec-WebSocket-Accept invalide")
        deflate = None
        exts = analyser_extensions(entetes.get("sec-websocket-extensions", ""))
        if exts:
            if set(exts) != {"permessage-deflate"} or not compression:
                raise ErreurWebSocket(f"extensions non demandées : {list(exts)}")
            deflate = Deflate.depuis_reponse(exts["permessage-deflate"])
        return cls(lecteur, ecrivain, client=True, deflate=deflate, taille_max=taille_max)

    # ---------------------------------------------------------------- envoi
    async def _envoyer_trame(self, opcode: int, charge: bytes, rsv1: bool = False) -> None:
        if self.fermee and opcode != OP_FERMER:
            raise FermetureWebSocket(1006, "déjà fermée")
        trame = encoder_trame(opcode, charge, masque=os.urandom(4) if self.client else None, rsv1=rsv1)
        async with self._verrou:
            try:
                self.ecrivain.write(trame)
                await self.ecrivain.drain()
            except (OSError, ConnectionError) as e:
                self.fermee = True
                raise FermetureWebSocket(1006, str(e)) from e

    async def envoyer_texte(self, texte: str) -> None:
        await self.envoyer(texte.encode("utf-8"), OP_TEXTE)

    async def envoyer(self, donnees: bytes, opcode: int = OP_BINAIRE) -> None:
        c = self.deflate.compresser(donnees) if self.deflate else None
        if c is None:
            await self._envoyer_trame(opcode, donnees)
        else:
            await self._envoyer_trame(opcode, c, rsv1=True)

    async def ping(self, donnees: bytes = b"") -> None:
        await self._envoyer_trame(OP_PING, donnees[:125])

    # ---------------------------------------------------------------- réception
    async def recevoir(self) -> str | bytes:
        """Message suivant (str pour une trame texte). Répond seul aux pings ; lève FermetureWebSocket
        à la fermeture (après avoir renvoyé la trame de fermeture)."""
        morceaux: list[bytes] = []
        opcode_msg = None
        compresse = False
        total = 0
        while True:
            if self.fermee:
                raise FermetureWebSocket(1006, "connexion fermée")
            t = await lire_trame(self.lecteur, masquee_attendue=not self.client, taille_max=self.taille_max)
            self.derniere_reception = time.monotonic()
            if t.opcode >= 0x8:                                   # trames de contrôle
                if not t.fin or len(t.charge) > 125:
                    raise ErreurWebSocket("trame de contrôle invalide")
                if t.opcode == OP_PING:
                    await self._envoyer_trame(OP_PONG, t.charge)
                elif t.opcode == OP_FERMER:
                    code = struct.unpack("!H", t.charge[:2])[0] if len(t.charge) >= 2 else 1005
                    raison = t.charge[2:].decode("utf-8", "replace")
                    with contextlib.suppress(ErreurWebSocket):
                        await self._envoyer_trame(OP_FERMER, t.charge[:2])
                    self._clore()
                    raise FermetureWebSocket(code, raison)
                continue
            if t.opcode in (OP_TEXTE, OP_BINAIRE):
                if opcode_msg is not None:
                    raise ErreurWebSocket("nouveau message avant la fin du précédent")
                opcode_msg, compresse = t.opcode, t.rsv1
                if t.rsv1 and not self.deflate:
                    raise ErreurWebSocket("message compressé sans extension négociée")
            elif t.opcode == OP_SUITE:
                if opcode_msg is None:
                    raise ErreurWebSocket("trame de suite sans message")
            else:
                raise ErreurWebSocket(f"opcode inconnu {t.opcode}")
            morceaux.append(t.charge)
            total += len(t.charge)
            if total > self.taille_max:
                raise ErreurWebSocket("message trop grand")
            if t.fin:
                donnees = b"".join(morceaux)
                if compresse:
                    donnees = self.deflate.decompresser(donnees, self.taille_max)
                if opcode_msg == OP_TEXTE:
                    try:
                        return donnees.decode("utf-8")
                    except UnicodeDecodeError as e:
                        raise ErreurWebSocket("texte UTF-8 invalide") from e
                return donnees

    def _clore(self) -> None:
        self.fermee = True
        self.ecrivain.close()

    async def fermer(self, code: int = 1000, raison: str = "") -> None:
        if self.fermee:
            return
        with contextlib.suppress(ErreurWebSocket, OSError):
            await self._envoyer_trame(OP_FERMER, struct.pack("!H", code) + raison.encode()[:120])
        self._clore()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.ecrivain.wait_closed(), 1.0)


def contexte_sans_verification() -> ssl.SSLContext:
    """Contexte TLS chiffré mais sans vérification du certificat (repli de `ClientAP._ouvrir` seulement)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def urls_candidates(adresse: str) -> list[str]:
    """« hote:port » -> [wss://…, ws://…] (comme le client officiel : wss d'abord) ; une adresse avec
    schéma est gardée telle quelle. Port par défaut : 38281."""
    adresse = adresse.strip()
    if "://" in adresse:
        u = urlsplit(adresse)
        if u.port is None and u.hostname:
            hote = f"[{u.hostname}]" if ":" in u.hostname else u.hostname
            adresse = f"{u.scheme}://{hote}:{PORT_DEFAUT}{u.path}"
        return [adresse]
    if adresse.startswith("/"):
        adresse = adresse.lstrip("/")
    u = urlsplit("//" + adresse)
    hote = f"[{u.hostname}]" if u.hostname and ":" in u.hostname else u.hostname
    port = u.port or PORT_DEFAUT
    return [f"wss://{hote}:{port}", f"ws://{hote}:{port}"]


# ================================================================================================ Archipelago
@dataclass(frozen=True)
class ObjetReseau:
    """NetworkItem : objet (item), location, joueur (player : qui l'a trouvé pour ReceivedItems, qui le
    reçoit pour LocationInfo), drapeaux (flags)."""
    item: int
    location: int
    player: int
    flags: int = 0

    @classmethod
    def depuis(cls, d: dict) -> "ObjetReseau":
        return cls(int(d["item"]), int(d["location"]), int(d["player"]), int(d.get("flags", 0)))


@dataclass(frozen=True)
class Joueur:
    team: int
    slot: int
    alias: str
    name: str


class RefusConnexion(Exception):
    """ConnectionRefused définitif (mauvais slot, mot de passe, jeu, version…)."""

    def __init__(self, erreurs: list[str]):
        super().__init__(", ".join(erreurs) or "connexion refusée")
        self.erreurs = erreurs


MESSAGES_REFUS = {
    "InvalidSlot": "nom de slot inconnu sur ce serveur",
    "InvalidGame": "ce slot n'est pas une partie de « Yo-kai Watch 2 »",
    "IncompatibleVersion": "version du client incompatible avec le serveur",
    "InvalidPassword": "mot de passe incorrect",
    "InvalidItemsHandling": "réglage items_handling refusé",
}


def version_reseau(v: tuple[int, int, int]) -> dict:
    return {"class": "Version", "major": v[0], "minor": v[1], "build": v[2]}


@dataclass
class DonneesJeu:
    """Noms d'un jeu (DataPackage) : identifiant -> nom."""
    objets: dict[int, str] = field(default_factory=dict)
    locations: dict[int, str] = field(default_factory=dict)
    checksum: str = ""

    @classmethod
    def depuis(cls, d: dict) -> "DonneesJeu":
        return cls({int(v): k for k, v in d.get("item_name_to_id", {}).items()},
                   {int(v): k for k, v in d.get("location_name_to_id", {}).items()}, d.get("checksum", ""))


class ClientAP:
    """Client Archipelago avec reconnexion automatique. États : « deconnecte », « connexion »,
    « connecte », « refuse », « arrete ».

    Rappels (attributs, fonctions ou coroutines, facultatifs) :
      sur_connecte(paquet Connected)          -> après chaque connexion (réussie) au slot
      sur_refus(erreurs: list[str])           -> ConnectionRefused (définitif : le client s'arrête)
      sur_objets(objets: list[ObjetReseau], debut: int)
                                              -> liste COMPLÈTE des objets reçus, et index du premier nouveau
      sur_message(texte: str, paquet: dict)   -> PrintJSON rendu en texte
      sur_deathlink(donnees: dict)            -> DeathLink reçu d'un autre joueur
      sur_deconnexion(raison: str)            -> connexion perdue (une reconnexion suit)
      sur_paquet(paquet: dict)                -> tout paquet reçu (après traitement)
      sur_indices(indices: list[dict])        -> liste COMPLÈTE des indices du slot (hints : receiving_player,
                                                 finding_player, location, item, found, item_flags, status)
    """

    def __init__(self, adresse: str, nom: str, mot_de_passe: str = "", *, jeu: str = JEU,
                 items_handling: int = OBJETS_AUTRES | OBJETS_PROPRES | OBJETS_DEPART,
                 version: tuple[int, int, int] = VERSION_AP, uuid: str | None = None, tags: Iterable[str] = (),
                 deathlink: bool = False, dossier_cache: Path | None = None, ssl_ctx: ssl.SSLContext | None = None,
                 delais_reconnexion: tuple[float, ...] = (1, 2, 5, 10, 20, 30), delai: float = 10.0,
                 intervalle_ping: float = 20.0, silence_max: float = 60.0, journal: logging.Logger | None = None):
        self.adresse, self.nom, self.mot_de_passe = adresse, nom, mot_de_passe
        self.jeu, self.items_handling, self.version = jeu, items_handling, version
        self._jeux_a_essayer = [j for j in JEUX if j != jeu] if jeu in JEUX else []
        self.uuid = uuid or uuid_mod.uuid4().hex
        self.tags = set(tags) | ({"DeathLink"} if deathlink else set())
        self.dossier_cache = Path(dossier_cache) if dossier_cache else None
        self.ssl_ctx = ssl_ctx
        self.tls_non_verifie = False        # vrai : wss:// ouvert sans vérification du certificat (voir `_ouvrir`)
        self.delais_reconnexion = delais_reconnexion
        self.delai = delai
        self.intervalle_ping, self.silence_max = intervalle_ping, silence_max
        self.log = journal or logging.getLogger("ykw2ap.reseau")
        # rappels
        self.sur_connecte: Callable | None = None
        self.sur_refus: Callable | None = None
        self.sur_objets: Callable | None = None
        self.sur_message: Callable | None = None
        self.sur_deathlink: Callable | None = None
        self.sur_deconnexion: Callable | None = None
        self.sur_paquet: Callable | None = None
        self.sur_indices: Callable | None = None
        # état
        self.etat = "deconnecte"
        self.url: str | None = None                 # URL qui a fonctionné (réutilisée pour se reconnecter)
        self.ws: WebSocket | None = None
        self.room_info: dict = {}
        self.slot: int | None = None
        self.team: int | None = None
        self.slot_data: dict = {}
        self.slot_info: dict[int, dict] = {}
        self.joueurs: dict[tuple[int, int], Joueur] = {}
        self.objets_recus: list[ObjetReseau] = []
        self.locations_verifiees: set[int] = set()
        self.locations_manquantes: set[int] = set()
        self.locations_en_attente: set[int] = set()   # envoyées ou à envoyer, pas encore confirmées
        self.victoire = False
        # statut du slot tenu par le serveur (data storage `_read_client_status_{team}_{slot}`, lecture seule), lu
        # une fois à chaque connexion ; None : pas encore de réponse (ou serveur qui ne le connaît pas)
        self.statut_slot: int | None = None
        self.indices: list[dict] = []                 # hints du slot (data storage `_read_hints_{team}_{slot}`)
        self.donnees: dict[str, DonneesJeu] = {}
        self.erreurs_refus: list[str] = []
        self.derniere_erreur = ""
        self._connecte = asyncio.Event()
        self._arret = asyncio.Event()
        self._scouts: list[tuple[set[int], asyncio.Future]] = []
        self._datapackage: asyncio.Future | None = None

    # ------------------------------------------------------------------------------ boucle principale
    async def executer(self) -> None:
        """Se connecte et reste connecté (reconnexion automatique) jusqu'à `arreter()` ou un refus
        définitif (RefusConnexion est alors levée)."""
        essai = 0
        while not self._arret.is_set():
            try:
                await self._session()
                essai = 0                                   # session terminée proprement : on se reconnecte
            except RefusConnexion:
                self.etat = "refuse"
                raise
            except (ErreurWebSocket, OSError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as e:
                self.derniere_erreur = str(e) or type(e).__name__
                if self._arret.is_set():
                    break
                self.log.warning("Serveur Archipelago : %s", self.derniere_erreur)
            finally:
                if self._connecte.is_set() or self.ws is not None:
                    self._connecte.clear()
                    ws, self.ws = self.ws, None
                    if ws is not None:
                        await ws.fermer()
                    self._annuler_attentes()
                    if self.etat != "refuse" and not self._arret.is_set():
                        await self._rappel(self.sur_deconnexion, self.derniere_erreur or "connexion perdue")
                if self.etat != "refuse":
                    self.etat = "deconnecte"
            if self._arret.is_set():
                break
            d = self.delais_reconnexion[min(essai, len(self.delais_reconnexion) - 1)]
            essai += 1
            self.log.info("Reconnexion au serveur Archipelago dans %s s", d)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._arret.wait(), d)
        self.etat = "arrete"

    async def arreter(self) -> None:
        self._arret.set()
        ws = self.ws
        if ws is not None:
            await ws.fermer(1000, "fin du client")

    async def attendre_connexion(self, delai: float | None = None) -> None:
        await asyncio.wait_for(self._connecte.wait(), delai)

    @property
    def connecte(self) -> bool:
        return self._connecte.is_set()

    async def _ouvrir(self) -> WebSocket:
        urls = [self.url] if self.url else urls_candidates(self.adresse)
        echecs: list[ErreurWebSocket] = []
        for url in urls:
            try:
                ws = await WebSocket.connecter(url, delai=self.delai, ssl_ctx=self.ssl_ctx)
            except ErreurWebSocket as e:
                # Certificat du serveur non vérifiable sur CETTE machine (autorité absente du magasin de Windows :
                # Python ne la télécharge pas, contrairement au navigateur) : sans ce repli, le client retombait sur
                # ws://, que les serveurs en TLS seulement (archipelago.gg) ferment aussitôt -> « Serveur
                # injoignable » (2.0.2). La liaison reste chiffrée ; elle n'est pas moins sûre que le repli en clair
                # qui suivait déjà. Jamais avec un contexte fourni par l'appelant.
                if self.ssl_ctx is None and url.startswith("wss://") \
                        and isinstance(e.__cause__, ssl.SSLCertVerificationError):
                    try:
                        ws = await WebSocket.connecter(url, delai=self.delai, ssl_ctx=contexte_sans_verification())
                    except ErreurWebSocket as e2:
                        echecs.append(e)
                        e = e2
                    else:
                        if not self.tls_non_verifie:
                            self.log.warning("Certificat de %s non vérifiable sur cet ordinateur (%s) : connexion "
                                             "chiffrée gardée, sans vérification du certificat", url, e.__cause__)
                        self.tls_non_verifie = True
                        self.url = url
                        return ws
                echecs.append(e)
                self.log.debug("Échec %s : %s", url, e)
                continue
            self.tls_non_verifie = False
            self.url = url
            return ws
        if len(echecs) > 1:      # toutes les causes, pas seulement la dernière (le journal ne montrait que ws://)
            raise ErreurWebSocket(" ; ".join(dict.fromkeys(str(e) for e in echecs))) from echecs[-1]
        raise echecs[0] if echecs else ErreurWebSocket("aucune adresse")

    async def _session(self) -> None:
        self.etat = "connexion"
        self.ws = ws = await self._ouvrir()
        self.log.info("Connecté à %s", self.url)
        garde = asyncio.create_task(self._garder_en_vie(ws))
        try:
            while True:
                msg = await ws.recevoir()
                if isinstance(msg, bytes):
                    continue
                try:
                    paquets = json.loads(msg)
                except json.JSONDecodeError:
                    self.log.warning("Paquet illisible du serveur")
                    continue
                for p in paquets if isinstance(paquets, list) else [paquets]:
                    if isinstance(p, dict):
                        await self._traiter(p)
        except FermetureWebSocket as e:
            if self._arret.is_set():
                return
            raise ErreurWebSocket(f"connexion fermée par le serveur ({e.code}{' ' + e.raison if e.raison else ''})")
        finally:
            garde.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await garde

    async def _garder_en_vie(self, ws: WebSocket) -> None:
        """Ping régulier ; connexion considérée morte après `silence_max` s sans rien recevoir."""
        while not ws.fermee:
            await asyncio.sleep(min(self.intervalle_ping, self.silence_max / 2))
            if time.monotonic() - ws.derniere_reception > self.silence_max:
                self.log.warning("Serveur silencieux depuis %s s : reconnexion", self.silence_max)
                ws._clore()
                return
            with contextlib.suppress(ErreurWebSocket):
                await ws.ping(b"ykw2ap")

    # ------------------------------------------------------------------------------ envoi
    async def envoyer(self, *paquets: dict) -> None:
        ws = self.ws
        if ws is None or ws.fermee:
            raise ErreurWebSocket("pas connecté au serveur Archipelago")
        await ws.envoyer_texte(json.dumps(list(paquets), ensure_ascii=False, separators=(",", ":")))

    async def _envoyer_si_connecte(self, *paquets: dict) -> bool:
        if not self.connecte:
            return False
        try:
            await self.envoyer(*paquets)
            return True
        except ErreurWebSocket:
            return False

    async def verifier_locations(self, locations: Iterable[int]) -> None:
        """Signale des checks (LocationChecks). Mémorisés jusqu'à confirmation du serveur (RoomUpdate) et
        renvoyés à chaque reconnexion : on peut appeler ceci même déconnecté."""
        nouvelles = {int(x) for x in locations} - self.locations_verifiees
        if not nouvelles:
            return
        self.locations_en_attente |= nouvelles
        await self._envoyer_si_connecte({"cmd": "LocationChecks", "locations": sorted(nouvelles)})

    async def scouter(self, locations: Iterable[int], create_as_hint: int = 0,
                      delai: float = 15.0) -> list[ObjetReseau]:
        """LocationScouts -> contenu des locations (LocationInfo). Lève ErreurWebSocket si déconnecté."""
        demande = sorted({int(x) for x in locations})
        if not demande:
            return []
        fut = asyncio.get_running_loop().create_future()
        self._scouts.append((set(demande), fut))
        try:
            await self.envoyer({"cmd": "LocationScouts", "locations": demande, "create_as_hint": create_as_hint})
            return await asyncio.wait_for(fut, delai)
        finally:
            self._scouts = [(s, f) for s, f in self._scouts if f is not fut]

    async def signaler_victoire(self) -> None:
        """StatusUpdate CLIENT_GOAL ; renvoyé à chaque reconnexion (le serveur ignore un doublon)."""
        self.victoire = True
        await self._envoyer_si_connecte({"cmd": "StatusUpdate", "status": CLIENT_GOAL})

    async def envoyer_statut(self, statut: int) -> None:
        await self._envoyer_si_connecte({"cmd": "StatusUpdate", "status": statut})

    async def dire(self, texte: str) -> None:
        """Say : message de discussion (ou commande serveur « !… »)."""
        await self.envoyer({"cmd": "Say", "text": texte})

    async def changer_statut_indice(self, joueur: int, location: int, statut: int) -> None:
        """UpdateHint (serveur 0.6) : priorité d'un indice dont ce slot est le destinataire (`joueur` = slot dans le monde
        duquel est la location). Le serveur répond par un SetReply de la clé des indices (ou ignore / InvalidPacket)."""
        await self.envoyer({"cmd": "UpdateHint", "player": int(joueur), "location": int(location), "status": int(statut)})

    async def synchroniser(self) -> None:
        """Sync : le serveur renvoie tous les objets reçus (ReceivedItems index 0)."""
        await self.envoyer({"cmd": "Sync"})

    async def activer_deathlink(self, actif: bool) -> None:
        if actif:
            self.tags.add("DeathLink")
        else:
            self.tags.discard("DeathLink")
        await self._envoyer_si_connecte({"cmd": "ConnectUpdate", "tags": sorted(self.tags)})

    async def envoyer_deathlink(self, cause: str = "") -> None:
        donnees = {"time": time.time(), "source": self.nom}
        if cause:
            donnees["cause"] = cause
        await self.envoyer({"cmd": "Bounce", "tags": ["DeathLink"], "data": donnees})

    # ------------------------------------------------------------------------------ noms
    def jeu_du_slot(self, slot: int) -> str | None:
        info = self.slot_info.get(int(slot))
        return info.get("game") if info else (self.jeu if slot == self.slot else None)

    def nom_joueur(self, slot: int, team: int | None = None) -> str:
        if int(slot) == 0:
            return "Serveur"
        j = self.joueurs.get((self.team if team is None else team, int(slot)))
        if j:
            return j.alias or j.name
        info = self.slot_info.get(int(slot))
        return info.get("name", f"Joueur {slot}") if info else f"Joueur {slot}"

    def nom_objet(self, item: int, slot: int | None = None) -> str:
        """Nom d'un objet ; `slot` = joueur qui le REÇOIT (c'est son jeu qui le définit)."""
        jeu = self.jeu_du_slot(slot) if slot is not None else self.jeu
        d = self.donnees.get(jeu or "")
        if d and item in d.objets:
            return d.objets[item]
        for d in self.donnees.values():
            if item in d.objets:
                return d.objets[item]
        return f"Objet {item}"

    def nom_location(self, location: int, slot: int | None = None) -> str:
        """Nom d'une location ; `slot` = joueur dans le monde duquel elle se trouve."""
        jeu = self.jeu_du_slot(slot) if slot is not None else self.jeu
        d = self.donnees.get(jeu or "")
        if d and location in d.locations:
            return d.locations[location]
        for d in self.donnees.values():
            if location in d.locations:
                return d.locations[location]
        return f"Lieu {location}"

    def texte_printjson(self, paquet: dict) -> str:
        """Texte lisible d'un PrintJSON (parties text, player_id, item_id, location_id…)."""
        out = []
        for part in paquet.get("data", []):
            t = part.get("type", "text")
            txt = str(part.get("text", ""))
            try:
                if t == "player_id":
                    txt = self.nom_joueur(int(txt))
                elif t == "item_id":
                    txt = self.nom_objet(int(txt), part.get("player"))
                elif t == "location_id":
                    txt = self.nom_location(int(txt), part.get("player"))
            except ValueError:
                pass
            out.append(txt)
        return "".join(out)

    # ------------------------------------------------------------------------------ cache du DataPackage
    def _fichier_cache(self, jeu: str, checksum: str) -> Path | None:
        if not self.dossier_cache or not checksum:
            return None
        sur = re.sub(r"[^A-Za-z0-9_.-]+", "_", jeu)[:60]
        return self.dossier_cache / f"{sur}_{re.sub(r'[^0-9a-fA-F]', '', checksum)[:64]}.json"

    def _lire_cache(self, jeu: str, checksum: str) -> DonneesJeu | None:
        f = self._fichier_cache(jeu, checksum)
        if f is None or not f.is_file():
            return None
        try:
            d = DonneesJeu.depuis(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError, AttributeError):
            return None
        return d if d.checksum == checksum else None

    def _ecrire_cache(self, jeu: str, brut: dict) -> None:
        f = self._fichier_cache(jeu, brut.get("checksum", ""))
        if f is None:
            return
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(brut, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, f)
        except OSError as e:
            self.log.debug("Cache du DataPackage non écrit : %s", e)

    # ------------------------------------------------------------------------------ réception
    async def _rappel(self, fonction: Callable | None, *args: Any) -> None:
        if fonction is None:
            return
        try:
            r = fonction(*args)
            if inspect.isawaitable(r):
                await r
        except Exception:                                  # un rappel fautif ne coupe pas la connexion
            self.log.exception("Erreur dans un rappel du client Archipelago")

    def _annuler_attentes(self) -> None:
        for _, f in self._scouts:
            if not f.done():
                f.set_exception(ErreurWebSocket("connexion perdue"))
        self._scouts.clear()

    async def _traiter(self, p: dict) -> None:
        cmd = p.get("cmd")
        traitant = getattr(self, f"_p_{cmd}", None)
        if traitant is not None:
            await traitant(p)
        await self._rappel(self.sur_paquet, p)

    async def _p_RoomInfo(self, p: dict) -> None:
        self.room_info = p
        a_demander = []
        for jeu, checksum in (p.get("datapackage_checksums") or {}).items():
            d = self.donnees.get(jeu)
            if d and d.checksum == checksum:
                continue
            d = self._lire_cache(jeu, checksum)
            if d:
                self.donnees[jeu] = d
            else:
                a_demander.append(jeu)
        paquets = []
        if a_demander:
            paquets.append({"cmd": "GetDataPackage", "games": a_demander})
        paquets.append(self._paquet_connect())
        await self.envoyer(*paquets)

    async def _p_DataPackage(self, p: dict) -> None:
        for jeu, brut in (p.get("data", {}).get("games") or {}).items():
            self.donnees[jeu] = DonneesJeu.depuis(brut)
            self._ecrire_cache(jeu, brut)

    def _paquet_connect(self) -> dict:
        return {"cmd": "Connect", "password": self.mot_de_passe, "game": self.jeu, "name": self.nom,
                "uuid": self.uuid, "version": version_reseau(self.version),
                "items_handling": self.items_handling, "tags": sorted(self.tags), "slot_data": True}

    async def _p_ConnectionRefused(self, p: dict) -> None:
        erreurs = [str(e) for e in p.get("errors", [])]
        if erreurs == ["InvalidGame"] and self._jeux_a_essayer:
            # slot de l'autre monde du mod (français / anglais) : même connexion, autre nom de jeu ; le nom qui
            # réussit est gardé pour les reconnexions
            self.jeu = self._jeux_a_essayer.pop(0)
            self.log.info("Slot refusé sous ce nom de jeu : nouvel essai avec « %s »", self.jeu)
            await self.envoyer(self._paquet_connect())
            return
        self.erreurs_refus = erreurs
        await self._rappel(self.sur_refus, erreurs)
        # toutes les erreurs documentées sont définitives (REFUS_DEFINITIFS) ; une erreur inconnue aussi :
        # se reconnecter en boucle avec les mêmes paramètres n'y changerait rien
        raise RefusConnexion(erreurs)

    async def _p_Connected(self, p: dict) -> None:
        self.team, self.slot = int(p["team"]), int(p["slot"])
        self.slot_data = p.get("slot_data") or {}
        self.slot_info = {int(k): v for k, v in (p.get("slot_info") or {}).items()}
        self.joueurs = {(int(j["team"]), int(j["slot"])): Joueur(int(j["team"]), int(j["slot"]),
                                                               j.get("alias", ""), j.get("name", ""))
                        for j in p.get("players", [])}
        self.locations_verifiees = {int(x) for x in p.get("checked_locations", [])}
        self.locations_manquantes = {int(x) for x in p.get("missing_locations", [])}
        self.locations_en_attente -= self.locations_verifiees
        self.etat = "connecte"
        self._connecte.set()
        self.log.info("Connecté au slot %s (%d)", self.nom, self.slot)
        # ce qui a été fait pendant la coupure
        paquets = []
        if self.locations_en_attente:
            paquets.append({"cmd": "LocationChecks", "locations": sorted(self.locations_en_attente)})
        if self.victoire:
            paquets.append({"cmd": "StatusUpdate", "status": CLIENT_GOAL})
        # indices (hints) du slot : lus une fois, puis suivis (SetReply à chaque nouvel indice ou changement d'état)
        cle = self.cle_indices
        self.statut_slot = None
        paquets += [{"cmd": "Get", "keys": [cle, self.cle_statut]}, {"cmd": "SetNotify", "keys": [cle]}]
        await self.envoyer(*paquets)
        await self._rappel(self.sur_connecte, p)

    async def _p_ReceivedItems(self, p: dict) -> None:
        index = int(p.get("index", 0))
        objets = [ObjetReseau.depuis(x) for x in p.get("items", [])]
        avant = len(self.objets_recus)
        if index == 0:
            debut = avant if self.objets_recus == objets[:avant] else 0
            self.objets_recus = objets
        elif index <= avant and self.objets_recus[index:] == objets[:avant - index]:
            self.objets_recus += objets[avant - index:]
            debut = avant
        else:                                                   # trou dans la séquence : tout redemander
            self.log.info("ReceivedItems hors séquence (index %d, %d connus) : Sync", index, avant)
            await self.synchroniser()
            return
        if len(self.objets_recus) > debut or index == 0:
            await self._rappel(self.sur_objets, list(self.objets_recus), debut)

    async def _p_RoomUpdate(self, p: dict) -> None:
        self.room_info.update({k: v for k, v in p.items() if k != "cmd"})
        if "checked_locations" in p:
            v = {int(x) for x in p["checked_locations"]}
            self.locations_verifiees |= v
            self.locations_manquantes -= v
            self.locations_en_attente -= v
        if "players" in p:
            for j in p["players"]:
                self.joueurs[(int(j["team"]), int(j["slot"]))] = Joueur(int(j["team"]), int(j["slot"]),
                                                                        j.get("alias", ""), j.get("name", ""))

    async def _p_LocationInfo(self, p: dict) -> None:
        objets = [ObjetReseau.depuis(x) for x in p.get("locations", [])]
        recues = {o.location for o in objets}
        # réponse exacte d'abord : un petit LocationScouts (indices de boutique) ne doit pas résoudre la demande de toutes
        # les locations en attente (le serveur répond par les locations demandées, dans l'ordre des demandes)
        for exacte in (True, False):
            for demande, fut in self._scouts:
                if not fut.done() and (recues == demande if exacte else recues <= demande):
                    fut.set_result(objets)
                    return

    @property
    def cle_indices(self) -> str:
        """Clé du data storage où le serveur (0.6.x) garde les indices de ce slot (lecture seule)."""
        return f"_read_hints_{self.team or 0}_{self.slot or 0}"

    async def _indices_recus(self, valeur: Any) -> None:
        if not isinstance(valeur, list):
            return
        self.indices = [h for h in valeur if isinstance(h, dict)]
        await self._rappel(self.sur_indices, list(self.indices))

    @property
    def cle_statut(self) -> str:
        """Clé du data storage où le serveur (0.6.x) garde le statut de ce slot (ClientStatus, 30 = but atteint)."""
        return f"_read_client_status_{self.team or 0}_{self.slot or 0}"

    @property
    def but_atteint(self) -> bool:
        """Objectif atteint pour le serveur : envoyé par ce client (`victoire`) ou statut du slot lu à la connexion
        (victoire envoyée par un client d'avant, un autre ordinateur, ou avant une relance)."""
        return self.victoire or self.statut_slot == CLIENT_GOAL

    async def _p_Retrieved(self, p: dict) -> None:
        cles = p.get("keys") or {}
        if isinstance(cles, dict) and isinstance(cles.get(self.cle_statut), int) \
                and not isinstance(cles.get(self.cle_statut), bool):
            self.statut_slot = cles[self.cle_statut]
        if isinstance(cles, dict) and self.cle_indices in cles:
            await self._indices_recus(cles[self.cle_indices])

    async def _p_SetReply(self, p: dict) -> None:
        if p.get("key") == self.cle_indices:
            await self._indices_recus(p.get("value"))

    async def _p_PrintJSON(self, p: dict) -> None:
        await self._rappel(self.sur_message, self.texte_printjson(p), p)

    async def _p_Bounced(self, p: dict) -> None:
        if "DeathLink" in p.get("tags", []) and "DeathLink" in self.tags:
            d = p.get("data") or {}
            if d.get("source") != self.nom:
                await self._rappel(self.sur_deathlink, d)

    async def _p_InvalidPacket(self, p: dict) -> None:
        self.log.warning("Paquet refusé par le serveur (%s, %s) : %s", p.get("type"), p.get("original_cmd"),
                         p.get("text"))


def texte_refus(erreurs: list[str]) -> str:
    """Message lisible (français) pour un ConnectionRefused."""
    return " ; ".join(MESSAGES_REFUS.get(e, e) for e in erreurs) or "connexion refusée"
