# -*- coding: utf-8 -*-
"""
Génère la table hash CRC32 -> nom d'objet FR pour Yo-kai Watch 2.

Chaîne de résolution (découverte par RE) :
  inventaire (RAM)         hash1 = CRC32 du nom interne de l'objet
  item_config.cfg.bin      hash1 est suivi (à +4) de hash2 (clé du nom affiché)
  item_text_fr.cfg.bin     hash2 -> offset -> nom FR (chaîne courte sans \\n)

Sortie : yokaiwatch2/data/item_hashes.json  ({"0x........": "Nom FR"}).
Le hash1 est la clé écrite dans l'inventaire (voir memory_map.INVENTORY_*),
donc cette table permet de délivrer n'importe quel objet AP par son nom.

Usage : python tools/extract_item_hashes.py <chemin romfs>
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arc0 import Arc0

ITEM_CONFIG = "item_config_0.04b.cfg.bin"   # dans yw2_a.fa
ITEM_TEXT_FR = "item_text_fr.cfg.bin"       # dans yw2_lg_fr.fa


def build(romfs: Path) -> dict:
    icfg = Arc0(romfs / "yw2_a.fa").read_file(ITEM_CONFIG)
    itxt = Arc0(romfs / "yw2_lg_fr.fa").read_file(ITEM_TEXT_FR)
    _, strtab_off, strtab_size = struct.unpack_from("<3I", itxt, 0)
    strtab = itxt[strtab_off:strtab_off + strtab_size]

    def name_of(off: int):
        if not (0 <= off < strtab_size):
            return None
        end = strtab.find(b"\x00", off)
        try:
            return strtab[off:end].decode("utf-8")
        except UnicodeDecodeError:
            return None

    mapping: dict = {}
    seen: set = set()
    pos = 0
    while pos + 8 <= len(icfg):
        hash1, hash2 = struct.unpack_from("<II", icfg, pos)
        pos += 4
        if hash1 < 0x1000 or hash2 < 0x1000 or hash1 in seen:
            continue
        tp = itxt.find(struct.pack("<I", hash2))
        if tp < 0 or tp + 32 > len(itxt):
            continue
        for off in struct.unpack_from("<8I", itxt, tp)[1:]:
            s = name_of(off)
            # un NOM est court, sans saut de ligne, commençant par une majuscule
            if s and 0 < len(s) < 40 and "\\n" not in s and s[:1].isupper():
                mapping[hash1] = s
                seen.add(hash1)
                break
    return mapping


if __name__ == "__main__":
    romfs = Path(sys.argv[1] if len(sys.argv) > 1
                 else r"C:\Users\dorya\Downloads\3dstool\romfs")
    table = build(romfs)
    out = Path(__file__).parent.parent / "yokaiwatch2" / "data" / "item_hashes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({f"0x{h:08x}": n for h, n in table.items()},
                              ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(table)} objets écrits dans {out}")
