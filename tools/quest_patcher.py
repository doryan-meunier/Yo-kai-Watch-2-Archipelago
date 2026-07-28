# -*- coding: utf-8 -*-
"""Patche les récompenses de quêtes de Yo-kai Watch 2 dans le mod yw2_lg_fr.fa.

À la génération d'un seed, chaque check-quête reçoit un item Archipelago. Ce
module réécrit EN PLACE (même taille) dans `quest_config_0.06b.cfg.bin` le hash
de récompense de chaque quête :
  * item YKW2 RÉEL  -> son hash (l'objet s'affiche normalement en jeu) ;
  * item ÉTRANGER   -> un slot placeholder, RENOMMÉ (item_text_fr) au nom de
    l'objet étranger (« nom seul », décision de design).

Les fichiers d'une archive ARC0 (.fa) sont NON compressés : une édition de même
taille (hash u32, ou chaîne <= longueur d'origine) s'écrit directement dans le
.fa, sans repack.

Structure quest_config (RE 2026-07-11) :
  - table de commandes cfg.bin : [crc u32][pinfo u16][term u16][params u32...]
  - QUEST_CONFIG (crc de "QUEST_CONFIG") : param[1]=hash quête,
    param[11]=index de départ dans la table QUEST_RSLT_ITEM.
  - QUEST_RSLT_ITEM (crc de "QUEST_RSLT_ITEM") : [hash item u32][quantité u32].
  - En ORDRE FICHIER, récompenses de la quête k = rslt[param11[k] : param11[k+1]].
"""
import struct
import zlib

QUEST_CONFIG_FILE = "quest_config_0.06b.cfg.bin"
ITEM_TEXT_FILE = "item_text_fr.cfg.bin"
CRC_QUEST_CONFIG = zlib.crc32(b"QUEST_CONFIG") & 0xFFFFFFFF
CRC_RSLT = zlib.crc32(b"QUEST_RSLT_ITEM") & 0xFFFFFFFF
P_QUEST_HASH = 1
P_REWARD_START = 11


def build_reward_map(qc: bytes):
    """{hash_quête: [offsets fichier des hash de récompense]} en ordre fichier.

    Les quêtes sans récompense de table (histoire) donnent une liste vide."""
    _, strtab_off, _ = struct.unpack_from("<3I", qc, 0)

    # Offsets des hash de récompense (param[0] de chaque QUEST_RSLT_ITEM), dans
    # l'ordre du fichier = l'ordre de la table.
    needle = struct.pack("<I", CRC_RSLT)
    rslt_hash_offsets = []
    i = qc.find(needle, 0x10)
    while 0 <= i < strtab_off:
        rslt_hash_offsets.append(i + 8)  # +8 = 1er param = hash item
        i = qc.find(needle, i + 1)

    # Quêtes en ordre fichier : (param[11], hash_quête).
    needle = struct.pack("<I", CRC_QUEST_CONFIG)
    quests = []
    i = qc.find(needle, 0x10)
    while 0 <= i < strtab_off:
        pc = struct.unpack_from("<H", qc, i + 4)[0] & 0xFF
        params = struct.unpack_from("<%dI" % pc, qc, i + 8)
        quests.append((params[P_REWARD_START], params[P_QUEST_HASH]))
        i = qc.find(needle, i + 1)

    mapping = {}
    for k, (start, qhash) in enumerate(quests):
        end = quests[k + 1][0] if k + 1 < len(quests) else len(rslt_hash_offsets)
        if end < start:  # param[11] doit être non-décroissant en ordre fichier
            raise ValueError("param[11] décroissant à la quête %d (%#x): %d<%d"
                             % (k, qhash, end, start))
        mapping[qhash] = rslt_hash_offsets[start:end]
    return mapping


def build_item_name_offsets(it: bytes, names):
    """Pour chaque nom d'objet, {nom: (offset, longueur_max)} dans la table de
    chaînes de item_text_fr. On cherche l'entrée COMPLÈTE (`\\0nom\\0`) pour
    viser le NOM et pas une sous-chaîne d'une description. On renomme EN PLACE :
    longueur_max = taille du nom d'origine (le \\0 final reste en place)."""
    out = {}
    for name in names:
        enc = name.encode("utf-8")
        p = it.find(b"\x00" + enc + b"\x00")
        if p < 0:
            continue
        out[name] = (p + 1, len(enc))
    return out


class ModPatcher:
    """Applique les placements AP au mod yw2_lg_fr.fa (édition en place)."""

    def __init__(self, arc):
        """arc : instance qui expose read_file(name) et .data_off + entries()
        (cf. tools/arc0.Arc0)."""
        self.arc = arc
        self.qc = arc.read_file(QUEST_CONFIG_FILE)
        self.it = arc.read_file(ITEM_TEXT_FILE)
        self.qc_base = arc.data_off + self._file_off(QUEST_CONFIG_FILE)
        self.it_base = arc.data_off + self._file_off(ITEM_TEXT_FILE)
        self.reward_map = build_reward_map(self.qc)

    def _file_off(self, name):
        return self.arc.entries()[zlib.crc32(
            name.encode("latin1")) & 0xFFFFFFFF][0]

    def plan(self, placements, placeholder_pool):
        """Construit la liste d'écritures (offset_abs, bytes) SANS écrire.

        placements : {hash_quête: item} où item = ('real', hash) pour un objet
                     YKW2, ('foreign', nom_affiché) pour un objet d'un autre jeu.
        placeholder_pool : [(nom_YKW2, hash_YKW2)] d'objets à repurposer pour les
                     étrangers : leur hash sert de récompense et on renomme leur
                     texte au nom de l'objet étranger. 1 placeholder par objet
                     étranger DISTINCT (même nom étranger -> même placeholder).
        Retourne (writes, warnings). writes = [(offset_absolu, octets)]."""
        writes = []
        warnings = []
        name_offs = build_item_name_offsets(self.it, [n for n, _ in placeholder_pool])
        assigned = {}   # nom_étranger -> hash_placeholder
        next_ph = 0
        for qhash, item in placements.items():
            offs = self.reward_map.get(qhash)
            if not offs:
                warnings.append("quête %#010x sans slot de récompense" % qhash)
                continue
            if item[0] == "real":
                reward_hash = item[1]
            else:  # ('foreign', nom)
                fname = item[1]
                if fname not in assigned:
                    if next_ph >= len(placeholder_pool):
                        warnings.append("pool de placeholders épuisé pour « %s »"
                                        % fname)
                        continue
                    ph_name, ph_hash = placeholder_pool[next_ph]
                    next_ph += 1
                    assigned[fname] = ph_hash
                    if ph_name not in name_offs:
                        warnings.append("placeholder « %s » absent de item_text"
                                        % ph_name)
                    else:
                        off, maxlen = name_offs[ph_name]
                        writes.append((self.it_base + off,
                                       _fit_utf8(fname, maxlen)))
                reward_hash = assigned[fname]
            for o in offs:
                writes.append((self.qc_base + o, struct.pack("<I", reward_hash)))
        return writes, warnings


def _fit_utf8(text: str, maxlen: int) -> bytes:
    """Encode `text` en UTF-8 tronqué à `maxlen` octets SANS couper un
    caractère multi-octets, puis complété de \\x00 jusqu'à `maxlen` (écriture
    même-taille dans la table de chaînes)."""
    enc = text.encode("utf-8")
    if len(enc) > maxlen:
        enc = enc[:maxlen]
        while enc and (enc[-1] & 0xC0) == 0x80:   # octet de continuation
            enc = enc[:-1]
        if enc and (enc[-1] & 0x80) and not (enc[-1] & 0x40):
            enc = enc[:-1]
    return enc + b"\x00" * (maxlen - len(enc))


def apply_writes(mod_path: str, writes) -> None:
    """Applique les écritures (offset_absolu, octets) au fichier .fa, en place."""
    with open(mod_path, "r+b") as f:
        for off, data in writes:
            f.seek(off)
            f.write(data)
