#!/usr/bin/env python3
"""
Remet les tables de RENCONTRES d'une ROM .3ds à leur état d'origine, en les
comparant à un romfs vierge extrait — sans toucher au reste.

Pourquoi : les fichiers d'annulation peuvent devenir incomplets (application
interrompue, deux mélanges superposés, annulation partielle). Un reliquat
suffit à laisser un boss remplacé alors que le joueur a désactivé le mélange
(cas vécu 2026-08-29 : 238 octets divergents dans common_enc).

On ne restaure QUE les sous-fichiers de rencontres (`common_enc*`, `*_enc_0.*`)
pour préserver le patch des coffres, qui vit dans `*_tbox.cfg.bin`.

    python tools/restore_encounters.py <rom.3ds> <romfs_vierge> [--apply]
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc0 import Arc0, crc32          # noqa: E402
import rom3ds                         # noqa: E402
import xpck                           # noqa: E402

ENC_COMMON = "common_enc_0.03a.cfg.bin"


class _Arc0At(Arc0):
    """Arc0 dont l'archive commence à `base` dans le .3ds."""

    def __init__(self, path: str, base: int):
        self.base = base
        self.path = path
        self.f = open(path, "rb")
        self.f.seek(base)
        assert self.f.read(4) == b"ARC0", "yw2_a.fa : magie ARC0 absente"
        (self.t1, self.t2, self.t3, self.name_off,
         self.data_off) = struct.unpack("<5I", self.f.read(20))
        self.t3 += base
        self.name_off += base
        self.data_off += base
        self._names = None
        self._entries = None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rom")
    ap.add_argument("romfs", help="dossier romfs VIERGE extrait")
    ap.add_argument("--apply", action="store_true", help="écrit dans la ROM")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with open(args.rom, "rb") as f:
        lvl3 = rom3ds.level3_offset(f, rom3ds.romfs_offset(f))
        fa = rom3ds.list_files(f, lvl3)["yw2_a.fa"]
    rom = _Arc0At(args.rom, fa.offset)
    pur = Arc0(str(Path(args.romfs) / "yw2_a.fa"))
    ent = rom.entries()

    corrections = []          # (offset absolu dans le .3ds, octets d'origine)
    examines = 0
    for full in pur.names():
        base = full.rsplit("/", 1)[-1]
        if not (base == ENC_COMMON or base.endswith(".pck")):
            continue
        try:
            off, size = ent[crc32(base.encode("latin1"))]
        except KeyError:
            continue
        rom.f.seek(rom.data_off + off)
        actuel = rom.f.read(size)
        try:
            origine = pur.read_file(base)
        except Exception:                                  # noqa: BLE001
            continue
        if len(origine) != len(actuel):
            continue
        examines += 1
        if base == ENC_COMMON:
            zones = [(0, size)]
        else:
            if actuel[:4] != b"XPCK":
                continue
            try:
                subs = xpck.parse(origine)
            except Exception:                              # noqa: BLE001
                continue
            zones = [(s.offset, s.size) for n, s in subs.items()
                     if "_enc_0." in n]
        for zoff, zsize in zones:
            a = actuel[zoff:zoff + zsize]
            o = origine[zoff:zoff + zsize]
            if a != o:
                corrections.append(
                    (rom.data_off + off + zoff, o,
                     f"{base} ({sum(1 for x, y in zip(a, o) if x != y)} octets)"))
    rom.f.close()

    print(f"{examines} conteneurs comparés")
    if not corrections:
        print("Aucune divergence : les rencontres sont déjà d'origine.")
        return
    total = sum(len(c[1]) for c in corrections)
    print(f"{len(corrections)} zone(s) à restaurer, {total} octets :")
    for _o, _b, quoi in corrections[:15]:
        print("   " + quoi)
    if len(corrections) > 15:
        print(f"   … et {len(corrections) - 15} autres")
    if not args.apply:
        print("\nEssai à blanc. Relancez avec --apply pour écrire.")
        return
    with open(args.rom, "r+b") as f:
        for offset, octets, _quoi in corrections:
            f.seek(offset)
            f.write(octets)
    print(f"\nRestauré : {total} octets remis à leur état d'origine.")


if __name__ == "__main__":
    main()
