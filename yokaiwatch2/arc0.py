# -*- coding: utf-8 -*-
"""
Parseur d'archives Level-5 ARC0 (.fa) — Yo-kai Watch 2.

Porté en Python depuis 3ds-xfsatool (mhvuze). Décompression Level-5 :
en-tête u32 = (tailleDécomp << 3) | type ; type 0=none 1=LZ10 2=Huff4
3=Huff8 4=RLE. Les données compressées suivent l'u32.
"""
import struct
import zlib


def decompress(data: bytes) -> bytes:
    header = struct.unpack_from("<I", data, 0)[0]
    size = header >> 3
    ctype = header & 7
    src = memoryview(data)[4:]
    if ctype == 0:
        return bytes(src[:size])
    if ctype == 1:
        return _lz10(src, size)
    if ctype in (2, 3):
        return _huffman(src, size, 4 if ctype == 2 else 8)
    if ctype == 4:
        return _rle(src, size)
    raise ValueError(f"type de compression inconnu: {ctype}")


def _lz10(src, size: int) -> bytes:
    out = bytearray()
    pos = 0
    while len(out) < size:
        flags = src[pos]; pos += 1
        for i in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> i):
                b0 = src[pos]; b1 = src[pos + 1]; pos += 2
                length = (b0 >> 4) + 3
                disp = (((b0 & 0xF) << 8) | b1) + 1
                start = len(out) - disp
                for k in range(length):
                    out.append(out[start + k])
            else:
                out.append(src[pos]); pos += 1
    return bytes(out[:size])


def _rle(src, size: int) -> bytes:
    out = bytearray()
    pos = 0
    while len(out) < size:
        flag = src[pos]; pos += 1
        if flag & 0x80:
            length = (flag & 0x7F) + 3
            val = src[pos]; pos += 1
            out += bytes([val]) * length
        else:
            length = (flag & 0x7F) + 1
            out += bytes(src[pos:pos + length]); pos += length
    return bytes(out[:size])


def _huffman(src, size: int, bits: int) -> bytes:
    tree_len = (src[0] + 1) * 2
    out = bytearray()
    pos = tree_len
    node_off = 1                    # offset (octets) du noeud courant dans l'arbre
    root_off = 1
    pending = None                  # pour le mode 4 bits
    while len(out) < size:
        if pos + 4 > len(src):
            break
        bits32 = struct.unpack_from("<I", src, pos)[0]
        pos += 4
        for i in range(31, -1, -1):
            bit = (bits32 >> i) & 1
            node = src[node_off]
            offset = node & 0x3F
            next_off = (node_off & ~1) + offset * 2 + 2 + bit
            # bit 0 -> flag de feuille = 0x80 ; bit 1 -> 0x40
            is_leaf = node & (0x80 >> bit)
            node_off = next_off
            if is_leaf:
                val = src[node_off]
                if bits == 8:
                    out.append(val)
                else:
                    if pending is None:
                        pending = val
                    else:
                        out.append((val << 4) | pending)
                        pending = None
                node_off = root_off
            if len(out) >= size:
                break
    return bytes(out[:size])


def crc32(name: bytes) -> int:
    return zlib.crc32(name) & 0xFFFFFFFF


class Arc0:
    def __init__(self, path: str):
        self.path = path
        self.f = open(path, "rb")
        magic = self.f.read(4)
        assert magic == b"ARC0", f"pas une archive ARC0: {magic!r}"
        (self.t1, self.t2, self.t3, self.name_off,
         self.data_off) = struct.unpack("<5I", self.f.read(20))
        self._names = None
        self._entries = None

    def names(self):
        """Liste des chemins (fichiers et dossiers, '/' final = dossier)."""
        if self._names is None:
            self.f.seek(self.name_off)
            blob = self.f.read(self.data_off - self.name_off)
            raw = decompress(blob)
            self._names = [s.decode("latin1") for s in raw.split(b"\x00") if s]
        return self._names

    def entries(self):
        """{crc32: (offset, size)} depuis la table de fichiers (Huffman)."""
        if self._entries is None:
            self.f.seek(self.t3)
            blob = self.f.read(self.name_off - self.t3)
            raw = decompress(blob)
            self._entries = {}
            for i in range(0, len(raw) - 15, 16):
                crc, _unk, off, sz = struct.unpack_from("<4I", raw, i)
                self._entries[crc] = (off, sz)
        return self._entries

    def read_file(self, name: str) -> bytes:
        # Les fichiers sont indexés par crc32 de leur NOM RELATIF (basename).
        basename = name.rsplit("/", 1)[-1]
        off, sz = self.entries()[crc32(basename.encode("latin1"))]
        self.f.seek(self.data_off + off)
        return self.f.read(sz)


if __name__ == "__main__":
    import sys
    arc = Arc0(sys.argv[1])
    names = arc.names()
    print(f"{len(names)} entrées de noms")
    for n in names[:80]:
        print(" ", n)
