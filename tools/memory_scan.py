# -*- coding: utf-8 -*-
"""
Scanner mémoire pour Yo-kai Watch 2 sous Azahar/Citra (stub GDB).

Outil de rétro-ingénierie « cheat search » : prendre des instantanés de la
mémoire du jeu, les comparer (quels octets/bits ont changé après avoir ouvert
un coffre ?), chercher des valeurs exactes (argent), surveiller une adresse.
Fonctionne sur le stub GDB de l'émulateur (Émulation > Configurer > Debug >
« Enable GDB stub », port 24689) et, en théorie, sur le débogueur Rosalina
d'une 3DS moddée.

Usage :
    python tools/memory_scan.py [--host localhost] [--port 24689]

Commandes du REPL (aide : « help ») :
    snap <nom> [addr] [taille]   instantané (défaut : 0x08000000, 64 Mo)
    diff <a> <b> [0|1]           octets modifiés entre deux instantanés
                                 (1 : seulement les bits passés de 0 à 1)
    refine <a> <b>               garde les adresses déjà candidates qui ont
                                 encore changé entre a et b
    search <valeur> [u8|u16|u32] cherche une valeur exacte en mémoire (argent)
    read <addr> <taille>         hexdump
    write <addr> <hex>           écrit des octets (prudence !)
    watch <addr> <taille>        affiche la valeur à chaque changement
    quit

Notes 3DS :
    La mémoire principale du jeu (région APPLICATION de la FCRAM) est mappée
    autour de 0x08000000. Un instantané complet de 64 Mo prend quelques
    minutes via GDB ; après le premier « diff », on ne travaille plus que sur
    les adresses candidates (rapide). Le protocole interrompt l'émulation le
    temps de chaque lecture puis la relance automatiquement.
"""

import argparse
import socket
import struct
import sys
import time

DEFAULT_REGION = (0x08000000, 0x04000000)  # FCRAM APPLICATION : 64 Mo
# Le stub GDB de Citra/Azahar a un buffer de paquet limité : une lecture de
# N octets renvoie 2N caractères hex. On lit par blocs de 0x400 (réponse de
# 2 Ko) pour rester largement sous la limite et éviter les timeouts.
CHUNK = 0x400


class GDBStub:
    """Client GDB Remote Serial Protocol minimal et synchrone."""

    def __init__(self, host: str, port: int) -> None:
        self.sock = socket.create_connection((host, port), timeout=10)
        self.sock.settimeout(10)
        self.running = False
        # À la connexion, le stub halte le CPU et peut envoyer un paquet stop.
        self._drain()

    # --- framing -----------------------------------------------------------
    @staticmethod
    def _checksum(payload: bytes) -> bytes:
        return b"%02x" % (sum(payload) % 256)

    def _send(self, payload: str) -> None:
        raw = payload.encode()
        self.sock.sendall(b"$" + raw + b"#" + self._checksum(raw))

    def _recv_packet(self) -> str:
        buf = b""
        while True:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("stub GDB déconnecté")
            buf += chunk
            start = buf.find(b"$")
            end = buf.find(b"#", start)
            if start != -1 and end != -1 and len(buf) >= end + 3:
                self.sock.sendall(b"+")
                return buf[start + 1:end].decode()

    def _drain(self) -> None:
        self.sock.settimeout(0.3)
        try:
            while self.sock.recv(4096):
                pass
        except (socket.timeout, BlockingIOError):
            pass
        self.sock.settimeout(10)

    def _exchange(self, payload: str) -> str:
        self._send(payload)
        return self._recv_packet()

    # --- exécution -----------------------------------------------------------
    def cont(self) -> None:
        """Relance l'émulation ('c' n'a pas de réponse tant que ça tourne)."""
        if not self.running:
            self._send("c")
            self.running = True

    def interrupt(self) -> None:
        """Interrompt l'émulation pour pouvoir lire/écrire la mémoire."""
        if self.running:
            self.sock.sendall(b"\x03")
            try:
                self._recv_packet()  # paquet stop (T05...)
            except socket.timeout:
                pass
            self.running = False
        self._drain()  # jette tout paquet stop/notification résiduel

    # --- mémoire ---------------------------------------------------------------
    _HEX = set("0123456789abcdefABCDEF")

    def _read_mem(self, address: int, size: int) -> bytes:
        """Lit un bloc, en resynchronisant si un paquet parasite (stop reply
        T05, notification 'O'...) s'est glissé dans le flux."""
        for _ in range(4):
            reply = self._exchange(f"m{address:x},{size:x}")
            if reply.startswith("E") and len(reply) <= 3:
                return b"\x00" * size            # page non mappée
            if reply and all(c in self._HEX for c in reply):
                return bytes.fromhex(reply)       # réponse hex valide
            self._drain()                         # parasite : on resynchronise
        raise ConnectionError(
            f"lecture désynchronisée @ {address:#x}: {reply!r:.40}")

    def read(self, address: int, length: int) -> bytes:
        # FIABILITÉ (2026-07-20) : lire pendant que le jeu TOURNE désynchronise le
        # stub au-delà de ~256 o (timeout -> stub figé). On HALTE le jeu le temps de
        # la lecture (mémoire stable, stub non sollicité par l'exécution) puis on
        # REPREND. Rend les snaps de plusieurs Ko fiables.
        was_running = self.running
        if was_running:
            self.interrupt()
        try:
            out = bytearray()
            for offset in range(0, length, CHUNK):
                out += self._read_mem(address + offset, min(CHUNK, length - offset))
            return bytes(out)
        finally:
            if was_running:
                self.cont()

    def region_readable(self, address: int) -> bool:
        """Teste si une adresse est mappée (petite lecture atomique).
        Après un timeout éventuel, resynchronise la socket."""
        try:
            reply = self._exchange(f"m{address:x},4")
        except socket.timeout:
            self._drain()  # vide une réponse tardive pour rester synchro
            return False
        return not (reply.startswith("E") and len(reply) <= 3)

    def write(self, address: int, data: bytes) -> bool:
        reply = self._exchange(f"M{address:x},{len(data):x}:{data.hex()}")
        return reply == "OK"

    def detach(self) -> None:
        """Détache le débogueur pour que le stub Citra/Azahar reste
        réarmable. Increvable : n'attend AUCUNE réponse (la socket peut
        être désynchronisée après un timeout)."""
        try:
            self._drain()             # jette ce qui traîne
            self._send("c")           # au cas où le CPU est halté : relance
            self._send("D")           # detach : le stub reprend et réaccepte
            time.sleep(0.2)
        except OSError:
            pass
        finally:
            try:
                self.sock.close()
            except OSError:
                pass


def hexdump(data: bytes, base: int) -> str:
    lines = []
    for i in range(0, len(data), 16):
        row = data[i:i + 16]
        hx = " ".join(f"{b:02x}" for b in row)
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(f"{base + i:08x}  {hx:<47}  {ascii_}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=24689)
    args = parser.parse_args()

    print(f"Connexion au stub GDB {args.host}:{args.port}...")
    try:
        gdb = GDBStub(args.host, args.port)
    except OSError as error:
        sys.exit(f"Échec : {error}\nDans Azahar : Émulation > Configurer > "
                 "Debug > cocher « Enable GDB stub » (port 24689), puis "
                 "relancer le jeu.")
    print("Connecté. L'émulation reprend ; tapez « help » pour les commandes.")
    gdb.cont()

    snapshots = {}   # nom -> (addr, bytes)
    candidates = {}  # adresse -> dernière valeur (résultats de diff/search)

    def paused(fn):
        gdb.interrupt()
        try:
            return fn()
        finally:
            gdb.cont()

    while True:
        try:
            line = input("scan> ").strip()
        except (EOFError, KeyboardInterrupt):
            line = "quit"
        if not line:
            continue
        cmd, *argv = line.split()
        try:
            if cmd in ("quit", "q", "exit"):
                print("Au revoir.")
                return

            elif cmd == "help":
                print(__doc__.split("Commandes du REPL", 1)[1])

            elif cmd == "snap":
                name = argv[0]
                addr = int(argv[1], 0) if len(argv) > 1 else DEFAULT_REGION[0]
                size = int(argv[2], 0) if len(argv) > 2 else DEFAULT_REGION[1]
                print(f"Lecture de {size:#x} octets @ {addr:#010x} "
                      f"(~{size // CHUNK} requêtes, patience)...")
                t0 = time.time()
                data = paused(lambda: gdb.read(addr, size))
                snapshots[name] = (addr, data)
                print(f"Instantané « {name} » : {len(data):#x} octets "
                      f"en {time.time() - t0:.0f}s.")

            elif cmd == "diff":
                (a_addr, a), (b_addr, b) = snapshots[argv[0]], snapshots[argv[1]]
                bits_only = len(argv) > 2 and argv[2] == "1"
                assert a_addr == b_addr and len(a) == len(b), "plages différentes"
                candidates.clear()
                for i, (x, y) in enumerate(zip(a, b)):
                    if x != y and (not bits_only or (y & ~x)):
                        candidates[a_addr + i] = y
                print(f"{len(candidates)} octet(s) modifié(s)"
                      + (" (bits 0->1)" if bits_only else ""))
                for addr, val in list(candidates.items())[:40]:
                    print(f"  {addr:#010x} : {a[addr - a_addr]:#04x} -> {val:#04x}")
                if len(candidates) > 40:
                    print(f"  ... et {len(candidates) - 40} autres")

            elif cmd == "refine":
                (a_addr, a), (b_addr, b) = snapshots[argv[0]], snapshots[argv[1]]
                before = len(candidates)
                for addr in list(candidates):
                    if a[addr - a_addr] == b[addr - b_addr]:
                        del candidates[addr]
                    else:
                        candidates[addr] = b[addr - b_addr]
                print(f"Candidats : {before} -> {len(candidates)}")
                for addr, val in list(candidates.items())[:40]:
                    print(f"  {addr:#010x} : {val:#04x}")

            elif cmd == "search":
                value = int(argv[0], 0)
                fmt = {"u8": "<B", "u16": "<H", "u32": "<I"}[
                    argv[1] if len(argv) > 1 else "u32"]
                needle = struct.pack(fmt, value)
                addr, size = DEFAULT_REGION
                print(f"Recherche de {value} ({fmt}) dans {size:#x} octets...")
                data = paused(lambda: gdb.read(addr, size))
                candidates.clear()
                pos = data.find(needle)
                while pos != -1:
                    candidates[addr + pos] = data[pos]
                    pos = data.find(needle, pos + 1)
                print(f"{len(candidates)} occurrence(s)")
                for a in list(candidates)[:40]:
                    print(f"  {a:#010x}")

            elif cmd == "read":
                addr, size = int(argv[0], 0), int(argv[1], 0)
                print(hexdump(paused(lambda: gdb.read(addr, size)), addr))

            elif cmd == "write":
                addr, data = int(argv[0], 0), bytes.fromhex(argv[1])
                ok = paused(lambda: gdb.write(addr, data))
                print("OK" if ok else "échec d'écriture")

            elif cmd == "watch":
                addr = int(argv[0], 0)
                size = int(argv[1], 0) if len(argv) > 1 else 4
                print("Surveillance ; Ctrl+C pour arrêter.")
                last = None
                try:
                    while True:
                        val = paused(lambda: gdb.read(addr, size))
                        if val != last:
                            print(f"{time.strftime('%H:%M:%S')}  "
                                  f"{addr:#010x} = {val.hex()}")
                            last = val
                        time.sleep(0.5)
                except KeyboardInterrupt:
                    print()

            else:
                print(f"Commande inconnue : {cmd} (essayez « help »)")
        except (KeyError, IndexError, ValueError, AssertionError) as error:
            print(f"Erreur : {error}")
        except (ConnectionError, socket.timeout) as error:
            sys.exit(f"Connexion perdue : {error}")


if __name__ == "__main__":
    main()
