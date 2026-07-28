# -*- coding: utf-8 -*-
"""
Génère la table hash CRC32 -> nom de quête FR pour Yo-kai Watch 2.

Sert au client : quand une quête est validée, le jeu écrit le hash de la
dernière quête terminée à `memory_map.LAST_QUEST_DONE_HASH_ADDR`. Cette table
traduit ce hash en nom FR -> on peut envoyer le check « Requête : <nom> ».

Chaîne de résolution (découverte par RE en jouant + data-mining) :
  RAM 0x086CBE74        hash1 = CRC32 du nom interne de la quête terminée
  quest_config.cfg.bin  commande QUEST_CONFIG : param[1] = hash1 (la quête),
                        param[6] = hash du titre affiché
  quest_title_text_fr   le hash du titre est suivi (+8) de l'offset -> nom FR

Le format d'une commande cfg.bin est : [crc u32][param_info u16][term u16]
[params u32...]. On repère les 147 entrées QUEST_CONFIG par le crc32 de leur
nom, et on lit param[1] et param[6] de chaque entrée.

Sortie : yokaiwatch2/data/quest_hashes.json  ({"0x........": "Nom FR"}).

Usage : python tools/extract_quest_hashes.py [<chemin romfs>]
"""
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arc0 import Arc0

QUEST_CONFIG = "quest_config_0.06b.cfg.bin"      # dans yw2_a.fa
QUEST_TITLE_FR = "quest_title_text_fr.cfg.bin"   # dans yw2_lg_fr.fa

# Position (en u32) des champs utiles dans les params de QUEST_CONFIG.
P_QUEST_HASH = 1     # hash interne de la quête (= valeur écrite en RAM)
P_TITLE_HASH = 6     # hash du titre affiché (clé dans quest_title_text)


def build(romfs: Path) -> dict:
    qcfg = Arc0(romfs / "yw2_a.fa").read_file(QUEST_CONFIG)
    qtxt = Arc0(romfs / "yw2_lg_fr.fa").read_file(QUEST_TITLE_FR)
    _, code_end, _ = struct.unpack_from("<3I", qcfg, 0)   # début de la strtab
    _, strtab_off, strtab_size = struct.unpack_from("<3I", qtxt, 0)
    strtab = qtxt[strtab_off:strtab_off + strtab_size]

    def title_of(title_hash: int):
        """Nom FR référencé par un hash de titre dans quest_title_text."""
        pos = qtxt.find(struct.pack("<I", title_hash))
        if pos < 0 or pos + 12 > len(qtxt):
            return None
        off = struct.unpack_from("<I", qtxt, pos + 8)[0]   # offset = champ +8
        if not (0 <= off < strtab_size):
            return None
        end = strtab.find(b"\x00", off)
        try:
            return strtab[off:end].decode("utf-8")
        except UnicodeDecodeError:
            return None

    crc_quest = zlib.crc32(b"QUEST_CONFIG") & 0xFFFFFFFF
    needle = struct.pack("<I", crc_quest)
    mapping: dict = {}
    pos = qcfg.find(needle, 0x10)
    while 0 <= pos < code_end:
        count = struct.unpack_from("<H", qcfg, pos + 4)[0] & 0xFF
        if count > P_TITLE_HASH:
            params = struct.unpack_from("<%dI" % count, qcfg, pos + 8)
            quest_hash = params[P_QUEST_HASH]
            name = title_of(params[P_TITLE_HASH])
            if name and quest_hash >= 0x1000:
                mapping[quest_hash] = name
        pos = qcfg.find(needle, pos + 1)
    return mapping


if __name__ == "__main__":
    romfs = Path(sys.argv[1] if len(sys.argv) > 1
                 else r"C:\Users\dorya\Downloads\3dstool\romfs")
    table = build(romfs)
    out = Path(__file__).parent.parent / "yokaiwatch2" / "data" / "quest_hashes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({f"0x{h:08x}": n for h, n in sorted(table.items())},
                              ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(table)} quêtes écrites dans {out}")
