# -*- coding: utf-8 -*-
"""
Décompilateur de scripts cfg.bin Level-5 (Yo-kai Watch 2).

Porté en Python 3 depuis youkai_bin_decomp.py (mhvuze / 3ds-xfsatool).
Un cfg.bin est une liste de commandes : chaque commande a un nom (résolu par
hash CRC32 via une table de clés) et des paramètres typés (int/float/string).
"""
import struct


def parse_cfg_bin(data: bytes):
    """Retourne la liste des commandes : (nom, [params]) où params sont des
    int / float / str selon leur type."""
    lines, strtab_off, strtab_size = struct.unpack_from("<3I", data, 0)

    # --- table des chaînes (paramètres string) ---
    strings_blob = data[strtab_off:strtab_off + strtab_size]
    string_table = {}
    start = 0
    for i, b in enumerate(strings_blob):
        if b == 0:
            string_table[start] = strings_blob[start:i].decode("latin1")
            start = i + 1

    # --- table des clés (hash CRC32 -> nom de commande) ---
    kt = strtab_off + strtab_size
    if kt % 16:
        kt += 16 - (kt % 16)
    _kt_size, key_count, key_offset, key_str_len = struct.unpack_from("<4I", data, kt)
    key_strings = data[kt + key_offset:kt + key_offset + key_str_len]
    key_table = {}
    for i in range(key_count):
        crc, off = struct.unpack_from("<2I", data, kt + 0x10 + i * 8)
        end = key_strings.index(b"\x00", off)
        key_table[crc] = key_strings[off:end].decode("latin1")

    # --- code (commandes) ---
    commands = []
    pos = 0x10
    code_end = strtab_off
    for _ in range(lines):
        if pos + 8 > code_end:
            break
        crc, param_info, _term = struct.unpack_from("<IHH", data, pos)
        param_type = param_info >> 8
        param_count = param_info & 0xFF
        pos += 8
        name = key_table.get(crc, "cmd_%08x" % crc)
        params = []
        for x in range(param_count):
            raw = struct.unpack_from("<I", data, pos)[0]
            typ = (param_type >> (2 * x)) & 3
            if typ == 1:       # entier
                params.append(raw)
            elif typ == 2:     # flottant
                params.append(struct.unpack_from("<f", data, pos)[0])
            else:              # chaîne (offset dans string_table)
                params.append(string_table.get(raw, "[%08x]" % raw))
            pos += 4
        commands.append((name, params))
    return commands


if __name__ == "__main__":
    import sys
    from arc0 import Arc0
    arc = Arc0(sys.argv[1])
    cmds = parse_cfg_bin(arc.read_file(sys.argv[2]))
    print(f"{len(cmds)} commandes")
    from collections import Counter
    freq = Counter(c[0] for c in cmds)
    print("=== commandes les plus fréquentes ===")
    for name, n in freq.most_common(20):
        print(f"  {n:5}  {name}")
    print("=== 30 premières commandes ===")
    for name, params in cmds[:30]:
        print(f"  {name} {params}")
