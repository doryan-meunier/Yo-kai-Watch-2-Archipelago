"""Lecture ET écriture des fichiers de configuration Level-5 `.cfg.bin` (« T2B »), bibliothèque standard seulement.

Format (docs/formats/level5.md §5 et §5bis) :

    en-tête 0x10 : nb d'entrées, offset de la table de chaînes, taille de la table, nb de chaînes (u32 LE)
    entrées à 0x10 : crc32(nom de clé) u32, nb de paramètres u8, types (2 bits par paramètre, poids faible
        d'abord : 0 chaîne, 1 entier, 2 flottant), bourrage 0xFF jusqu'au multiple de 4, puis un mot par paramètre
    bourrage 0xFF jusqu'au multiple de 16
    table de chaînes (UTF-8 ou Shift-JIS, terminées par 0 ; valeur de type chaîne = offset, -1 = aucune)
    bourrage 0xFF jusqu'au multiple de 16
    table des clés : taille totale (bourrage compris), nb, offset des noms, taille des noms, nb × (crc32, offset
        du nom), bourrage 0xFF jusqu'au multiple de 16, noms ASCII terminés par 0, bourrage 0xFF jusqu'au
        multiple de 16
    pied de 16 octets : 01 't' '2' 'b' FE, 01 xx 00 01 00, puis 0xFF (xx = 0, ou 1 dans 3 fichiers : gardé tel quel)

Fidélité : `Cfg(data).ecrire() == data` pour un fichier non modifié (les valeurs sont gardées en mots bruts, la
table de chaînes et la table des clés sont gardées telles quelles ; une chaîne nouvelle est ajoutée à la fin de la
table, une clé nouvelle à la fin de la table des clés, reconstruite alors selon la disposition ci-dessus).
`Cfg.reconstruit()` refait TOUT le fichier à partir des seules entrées (chaînes dans l'ordre de première
apparition, sans doublon ; clés dans l'ordre de première apparition) : sert à contrôler que la disposition est
comprise (`tools/romfs/cfg_ecrire_verif.py`), et à créer un fichier de rien.
"""
from __future__ import annotations

import struct
import zlib

PIED = b"\x01t2b\xfe\x01\x00\x00\x01\x00" + b"\xff" * 6
CHAINE, ENTIER, FLOTTANT = 0, 1, 2
AUCUNE = 0xFFFFFFFF


class ErreurCfg(ValueError):
    """Fichier `.cfg.bin` invalide, ou modification impossible."""


def crc32(nom: str) -> int:
    return zlib.crc32(nom.encode("ascii")) & 0xFFFFFFFF


def _bourrer(b: bytearray, multiple: int = 16) -> None:
    b += b"\xff" * (-len(b) % multiple)


class Entree:
    """Une entrée : `cle` (crc32 du nom), `types` (0 / 1 / 2 par paramètre), `mots` (u32 bruts)."""
    __slots__ = ("cle", "types", "mots")

    def __init__(self, cle: int, types, mots):
        if len(types) != len(mots) or len(types) > 255:
            raise ErreurCfg("entrée : types et valeurs de longueurs différentes")
        self.cle, self.types, self.mots = cle, list(types), [m & 0xFFFFFFFF for m in mots]

    def copie(self) -> "Entree":
        return Entree(self.cle, self.types, self.mots)

    def octets(self) -> bytes:
        n = len(self.types)
        b = bytearray(struct.pack("<IB", self.cle, n))
        for i in range(0, n, 4):
            o = 0
            for k, t in enumerate(self.types[i:i + 4]):
                o |= (t & 3) << (2 * k)
            b.append(o)
        _bourrer(b, 4)
        b += struct.pack("<%dI" % n, *self.mots)
        return bytes(b)


def mot_flottant(v: float) -> int:
    return struct.unpack("<I", struct.pack("<f", v))[0]


class Cfg:
    def __init__(self, data: bytes | None = None):
        self.entrees: list[Entree] = []
        self.chaines = bytearray()           # table de chaînes brute
        self.nb_chaines = 0
        self.cles: list[tuple[int, bytes]] = []  # (crc32, nom en octets) dans l'ordre de la table
        self._bloc_cles: bytes | None = None     # table des clés d'origine (gardée telle quelle si rien n'y change)
        self.pied = PIED
        self._suite = b""                        # octets après le pied (aucun dans les fichiers du jeu)
        if data is not None:
            self._lire(bytes(data))

    # ------------------------------------------------------------------------------------------ lecture
    def _lire(self, d: bytes) -> None:
        if len(d) < 0x10:
            raise ErreurCfg("fichier trop court")
        nb, off_ch, taille_ch, nb_ch = struct.unpack_from("<4I", d, 0)
        if off_ch + taille_ch > len(d) or off_ch < 0x10:
            raise ErreurCfg("table de chaînes hors du fichier")
        p = 0x10
        for _ in range(nb):
            if p + 8 > off_ch:
                raise ErreurCfg("entrées qui débordent sur la table de chaînes")
            cle, n = struct.unpack_from("<IB", d, p)
            nt = (n + 3) // 4
            ot = d[p + 5:p + 5 + nt]
            q = (p + 5 + nt + 3) & ~3
            if q + 4 * n > off_ch:
                raise ErreurCfg("entrées qui débordent sur la table de chaînes")
            types = [(ot[i // 4] >> (2 * (i % 4))) & 3 for i in range(n)]
            self.entrees.append(Entree(cle, types, struct.unpack_from("<%dI" % n, d, q)))
            p = q + 4 * n
        self.chaines = bytearray(d[off_ch:off_ch + taille_ch])
        self.nb_chaines = nb_ch
        k = (off_ch + taille_ch + 15) & ~15
        if k + 16 > len(d):
            raise ErreurCfg("table des clés absente")
        taille_k, nk, off_n, taille_n = struct.unpack_from("<4I", d, k)
        if k + taille_k + len(PIED) > len(d) or off_n + taille_n > taille_k or 16 + 8 * nk > off_n:
            raise ErreurCfg("table des clés incohérente")
        noms = d[k + off_n:k + off_n + taille_n]
        for i in range(nk):
            c, o = struct.unpack_from("<2I", d, k + 16 + 8 * i)
            fin = noms.find(b"\0", o)
            if o >= len(noms) or fin < 0:
                raise ErreurCfg("nom de clé hors de la table")
            self.cles.append((c, bytes(noms[o:fin])))
        self._bloc_cles = d[k:k + taille_k]
        self.pied = d[k + taille_k:k + taille_k + len(PIED)]
        if self.pied[:5] != PIED[:5]:
            raise ErreurCfg("pied du fichier inattendu")
        self._suite = d[k + taille_k + len(PIED):]

    # ------------------------------------------------------------------------------------------ accès
    def nom(self, e: Entree) -> str:
        for c, n in self.cles:
            if c == e.cle:
                return n.decode("ascii", "replace")
        return "%08X" % e.cle

    def par_nom(self, nom: str) -> list[Entree]:
        c = crc32(nom)
        return [e for e in self.entrees if e.cle == c]

    def chaine(self, offset: int, encodage: str = "utf-8") -> str | None:
        if offset == AUCUNE:
            return None
        if offset >= len(self.chaines):
            raise ErreurCfg("offset de chaîne hors de la table")
        fin = self.chaines.find(b"\0", offset)
        return bytes(self.chaines[offset:fin if fin >= 0 else len(self.chaines)]).decode(encodage, "replace")

    def valeurs(self, e: Entree, encodage: str = "utf-8") -> list:
        """Valeurs décodées : chaîne (ou None), entier non signé, flottant."""
        out = []
        for t, m in zip(e.types, e.mots):
            if t == CHAINE:
                out.append(self.chaine(m, encodage))
            elif t == FLOTTANT:
                out.append(struct.unpack("<f", struct.pack("<I", m))[0])
            else:
                out.append(m)
        return out

    def _debuts_chaines(self) -> dict[bytes, int]:
        debuts, p = {}, 0
        while p < len(self.chaines):
            fin = self.chaines.find(b"\0", p)
            if fin < 0:
                fin = len(self.chaines)
            debuts.setdefault(bytes(self.chaines[p:fin]), p)
            p = fin + 1
        return debuts

    # ------------------------------------------------------------------------------------------ modification
    def offset_chaine(self, texte: str | bytes | None) -> int:
        """Offset de la chaîne dans la table ; ajoutée à la fin si elle n'y est pas (une chaîne déjà présente
        est réutilisée, comme dans les fichiers du jeu)."""
        if texte is None:
            return AUCUNE
        b = texte.encode("utf-8") if isinstance(texte, str) else bytes(texte)
        if b"\0" in b:
            raise ErreurCfg("chaîne avec un octet nul")
        deja = self._debuts_chaines().get(b)
        if deja is not None:
            return deja
        o = len(self.chaines)
        self.chaines += b + b"\0"
        self.nb_chaines += 1
        return o

    def entree(self, nom: str, valeurs) -> Entree:
        """Construit une entrée : str / None -> chaîne, float -> flottant, int -> entier. La clé est ajoutée à la
        table des clés si elle est nouvelle. (L'entrée n'est pas insérée : `self.entrees.insert(...)`.)"""
        types, mots = [], []
        for v in valeurs:
            if v is None or isinstance(v, (str, bytes)):
                types.append(CHAINE)
                mots.append(self.offset_chaine(v))
            elif isinstance(v, float):
                types.append(FLOTTANT)
                mots.append(mot_flottant(v))
            else:
                types.append(ENTIER)
                mots.append(int(v) & 0xFFFFFFFF)
        c = crc32(nom)
        if all(k != c for k, _n in self.cles):
            self.cles.append((c, nom.encode("ascii")))
            self._bloc_cles = None
        return Entree(c, types, mots)

    # ------------------------------------------------------------------------------------------ écriture
    @staticmethod
    def _table_cles(cles: list[tuple[int, bytes]]) -> bytes:
        noms = bytearray()
        index = bytearray()
        for c, n in cles:
            index += struct.pack("<2I", c, len(noms))
            noms += n + b"\0"
        b = bytearray(16) + index
        _bourrer(b)
        off_n = len(b)
        b += noms
        _bourrer(b)
        struct.pack_into("<4I", b, 0, len(b), len(cles), off_n, len(noms))
        return bytes(b)

    def _assembler(self, chaines: bytes, nb_chaines: int, bloc_cles: bytes, entrees) -> bytes:
        b = bytearray(16)
        for e in entrees:
            b += e.octets()
        _bourrer(b)
        struct.pack_into("<4I", b, 0, len(entrees), len(b), len(chaines), nb_chaines)
        b += chaines
        _bourrer(b)
        b += bloc_cles + self.pied + self._suite
        return bytes(b)

    def ecrire(self) -> bytes:
        for e in self.entrees:
            for t, m in zip(e.types, e.mots):
                if t == CHAINE and m != AUCUNE and m >= len(self.chaines):
                    raise ErreurCfg("offset de chaîne hors de la table")
        bloc = self._bloc_cles if self._bloc_cles is not None else self._table_cles(self.cles)
        return self._assembler(bytes(self.chaines), self.nb_chaines, bloc, self.entrees)

    def reconstruit(self) -> bytes:
        """Fichier refait à partir des entrées seules (voir le texte du module)."""
        chaines = bytearray()
        offsets: dict[bytes, int] = {}
        entrees = []
        for e in self.entrees:
            mots = []
            for t, m in zip(e.types, e.mots):
                if t == CHAINE and m != AUCUNE:
                    fin = self.chaines.find(b"\0", m)
                    s = bytes(self.chaines[m:fin if fin >= 0 else len(self.chaines)])
                    if s not in offsets:
                        offsets[s] = len(chaines)
                        chaines += s + b"\0"
                    m = offsets[s]
                mots.append(m)
            entrees.append(Entree(e.cle, e.types, mots))
        noms = dict(self.cles)
        cles, vues = [], set()
        for e in self.entrees:
            if e.cle not in vues:
                vues.add(e.cle)
                if e.cle not in noms:
                    raise ErreurCfg("clé sans nom : %08X" % e.cle)
                cles.append((e.cle, noms[e.cle]))
        return self._assembler(bytes(chaines), len(offsets), self._table_cles(cles), entrees)
