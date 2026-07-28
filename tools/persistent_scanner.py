# -*- coding: utf-8 -*-
"""
Scanner mémoire PERSISTANT pour Azahar/Citra.

Se connecte UNE SEULE FOIS au stub GDB et garde la connexion ouverte toute la
session (le stub Citra/Azahar n'aime pas les reconnexions répétées). Les
commandes arrivent par un fichier `cmd.txt`, les résultats sont ajoutés à
`scan.log`. L'émulation tourne entre les commandes ; on l'interrompt juste le
temps de lire, puis on la relance.

Lancé en arrière-plan ; piloté en écrivant cmd.txt et en lisant scan.log.
"""
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, r"c:\Users\dorya\Desktop\yo kai watch 2 archipelago\tools")
from memory_scan import GDBStub

HERE = Path(__file__).parent
SNAPS = HERE / "snaps"; SNAPS.mkdir(exist_ok=True)
CMD = HERE / "cmd.txt"
LOG = HERE / "scan.log"
CAND = SNAPS / "candidates.json"
REGIONS = SNAPS / "regions.json"

HEAP_SPACES = [
    (0x00100000, 0x00A00000),  # code + heap bas (10 Mo)
    (0x08100000, 0x00F00000),  # heap APPLICATION / FCRAM (15 Mo)
]
PAGE = 0x1000


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def load_cand():
    return {int(k): v for k, v in json.loads(CAND.read_text()).items()} \
        if CAND.exists() else {}


def save_cand(c):
    CAND.write_text(json.dumps({str(k): v for k, v in c.items()}))


def load_regions():
    return [tuple(r) for r in json.loads(REGIONS.read_text())] \
        if REGIONS.exists() else HEAP_SPACES


def load_snap(name):
    meta = json.loads((SNAPS / f"{name}.json").read_text())
    return meta["addr"], (SNAPS / f"{name}.bin").read_bytes()


def do_probe(gdb):
    found = []
    for base, span in HEAP_SPACES:
        start = None
        for a in range(base, base + span, PAGE):
            ok = gdb.region_readable(a)
            if ok and start is None:
                start = a
            elif not ok and start is not None:
                found.append((start, a - start)); start = None
        if start is not None:
            found.append((start, base + span - start))
    REGIONS.write_text(json.dumps(found))
    total = sum(s for _, s in found)
    log(f"{len(found)} run(s) mappé(s), {total/1e6:.1f} Mo")
    for a, s in found[:25]:
        log(f"  {a:#010x} .. {a+s:#010x}  ({s/1e6:.2f} Mo)")


def do_search(gdb, argv, again):
    value = int(argv[0], 0)
    fmt = {"u8": "<B", "u16": "<H", "u32": "<I"}[argv[1] if len(argv) > 1 else "u32"]
    needle = struct.pack(fmt, value)
    found = {}
    for addr, size in load_regions():
        data = gdb.read(addr, size)
        pos = data.find(needle)
        while pos != -1:
            found[addr + pos] = value
            pos = data.find(needle, pos + 1)
    if again:
        prev = set(load_cand())
        found = {a: v for a, v in found.items() if a in prev}
    save_cand(found)
    log(f"{len(found)} adresse(s) = {value} ({fmt})")
    for a in sorted(found)[:60]:
        log(f"  {a:#010x}")


def do_snap(gdb, name):
    regions = load_regions()
    blob = bytearray(); index = []
    t0 = time.time()
    for addr, size in regions:
        index.append([addr, len(blob), size])
        blob += gdb.read(addr, size)
    (SNAPS / f"{name}.bin").write_bytes(blob)
    (SNAPS / f"{name}.json").write_text(json.dumps(
        {"addr": regions[0][0], "regions": index}))
    log(f"snap '{name}' : {len(blob)/1e6:.1f} Mo en {time.time()-t0:.0f}s")


def do_diff(gdb, argv):
    (a_addr, a), (b_addr, b) = load_snap(argv[0]), load_snap(argv[1])
    bits = len(argv) > 2 and argv[2] == "bits"
    cand = {}
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y and (not bits or (y & ~x)):
            cand[a_addr + i] = y
    save_cand(cand)
    log(f"{len(cand)} octet(s) modifié(s)" + (" (bits 0->1)" if bits else ""))
    for ad, val in list(cand.items())[:60]:
        log(f"  {ad:#010x} : {a[ad-a_addr]:#04x} -> {val:#04x}")


def do_refine(gdb, argv):
    (a_addr, a), (b_addr, b) = load_snap(argv[0]), load_snap(argv[1])
    cand = load_cand()
    kept = {ad: b[ad-b_addr] for ad in cand
            if 0 <= ad-a_addr < len(a) and a[ad-a_addr] != b[ad-b_addr]}
    save_cand(kept)
    log(f"candidats : {len(cand)} -> {len(kept)}")
    for ad, val in list(kept.items())[:60]:
        log(f"  {ad:#010x} : {val:#04x}")


def do_read(gdb, argv):
    from memory_scan import hexdump
    addr, size = int(argv[0], 0), int(argv[1], 0)
    log(hexdump(gdb.read(addr, size), addr))


def do_write(gdb, argv):
    """write <addr> <hexbytes> : écrit des octets bruts en mémoire (paquet M)."""
    addr = int(argv[0], 0)
    data = bytes.fromhex(argv[1])
    ok = gdb.write(addr, data)
    log(f"write {addr:#010x} <- {len(data)} octet(s) : {'OK' if ok else 'ECHEC'}")


def do_peek(gdb):
    cand = load_cand()
    log(f"{len(cand)} candidat(s)")
    for ad in list(cand)[:60]:
        log(f"  {ad:#010x} : {gdb.read(ad, 4).hex()}")


def do_window(argv):
    """Restreint snap/search à une fenêtre [addr, addr+size] (regions.json)."""
    addr, size = int(argv[0], 0), int(argv[1], 0)
    REGIONS.write_text(json.dumps([[addr, size]]))
    log(f"fenêtre active : {addr:#010x} .. {addr+size:#010x} ({size/1e6:.2f} Mo)")


def do_fullregion():
    """Rétablit les deux régions heap complètes."""
    REGIONS.write_text(json.dumps(HEAP_SPACES))
    log("régions rétablies : heap complet (22 Mo)")


HANDLERS = {
    "probe": lambda g, a: do_probe(g),
    "search": lambda g, a: do_search(g, a, False),
    "searchagain": lambda g, a: do_search(g, a, True),
    "snap": lambda g, a: do_snap(g, a[0]),
    "diff": lambda g, a: do_diff(g, a),
    "refine": lambda g, a: do_refine(g, a),
    "read": lambda g, a: do_read(g, a),
    "write": lambda g, a: do_write(g, a),
    "peek": lambda g, a: do_peek(g),
    "window": lambda g, a: do_window(a),
    "fullregion": lambda g, a: do_fullregion(),
}


def main():
    log("=== scanner persistant : attente du stub GDB ===")
    gdb = None
    deadline = time.time() + 120  # laisse le temps de (r)ouvrir Azahar
    while time.time() < deadline:
        try:
            gdb = GDBStub("127.0.0.1", 24689)
            break
        except OSError:
            time.sleep(1.5)
    if gdb is None:
        log("ÉCHEC : stub GDB introuvable après 120 s.")
        return
    gdb.cont()
    log("CONNECTÉ — émulation relancée, en attente de commandes.")

    while True:
        if not CMD.exists():
            time.sleep(0.3)
            continue
        line = CMD.read_text(encoding="utf-8").strip()
        try:
            CMD.unlink()
        except OSError:
            pass
        if not line:
            continue
        log(f"\n>>> {line}")
        if line == "quit":
            gdb.cont(); gdb.detach()
            log("=== déconnexion propre ===")
            return
        cmd, *argv = line.split()
        handler = HANDLERS.get(cmd)
        if not handler:
            log(f"commande inconnue: {cmd}")
            continue
        try:
            gdb.interrupt()
            handler(gdb, argv)
        except Exception as e:  # noqa: BLE001 - on log tout, on ne meurt pas
            log(f"ERREUR: {type(e).__name__}: {e}")
        finally:
            gdb.cont()
        log("<<< done")


if __name__ == "__main__":
    main()
