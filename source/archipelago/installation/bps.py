"""Décodeur de patchs BPS (format « beat »), bibliothèque standard seulement.

Module partagé entre l'installateur du mod (`installer.py`, chez le joueur) et `tools/ap_patch.py`
(création des patchs, dans le dépôt), qui l'importe : une seule implémentation de l'application.

Format : « BPS1 », varint taille source, varint taille cible, varint taille des métadonnées, métadonnées,
actions (SourceRead 0, TargetRead 1, SourceCopy 2, TargetCopy 3 ; longueur - 1 dans les bits hauts),
puis CRC-32 source, CRC-32 cible et CRC-32 du patch (petit-boutiste).
"""
from __future__ import annotations

import struct
import zlib


class ErreurBps(ValueError):
    """Patch BPS invalide, ou appliqué au mauvais fichier source."""


def lire_varint(p: bytes, i: int) -> tuple[int, int]:
    """Lit un entier BPS à la position i ; renvoie (valeur, position suivante)."""
    v, s = 0, 1
    while True:
        if i >= len(p):
            raise ErreurBps("BPS : patch tronqué")
        x = p[i]
        i += 1
        v += (x & 0x7F) * s
        if x & 0x80:
            return v, i
        s <<= 7
        v += s


def entete(p: bytes) -> tuple[int, int, int, int]:
    """(taille source, taille cible, CRC-32 source, CRC-32 cible) annoncés par le patch."""
    if p[:4] != b"BPS1" or len(p) < 4 + 3 + 12:
        raise ErreurBps("pas un patch BPS")
    i = 4
    ns, i = lire_varint(p, i)
    nt, i = lire_varint(p, i)
    crc_s, crc_t = struct.unpack_from("<II", p, len(p) - 12)
    return ns, nt, crc_s, crc_t


def bps_appliquer(src: bytes, p: bytes) -> bytes:
    """Applique le patch p à src ; vérifie le CRC du patch, la source (taille, CRC) et la cible."""
    if p[:4] != b"BPS1" or len(p) < 4 + 3 + 12:
        raise ErreurBps("pas un patch BPS")
    if zlib.crc32(p[:-4]) != struct.unpack_from("<I", p, len(p) - 4)[0]:
        raise ErreurBps("BPS : CRC du patch invalide")
    i = 4
    ns, i = lire_varint(p, i)
    nt, i = lire_varint(p, i)
    nm, i = lire_varint(p, i)
    i += nm
    crc_s, crc_t = struct.unpack_from("<II", p, len(p) - 12)
    if len(src) != ns or zlib.crc32(src) != crc_s:
        raise ErreurBps("BPS : fichier source différent de celui attendu (CRC/ taille)")
    out = bytearray()
    so = to = 0
    fin = len(p) - 12
    while i < fin:
        d, i = lire_varint(p, i)
        cmd, n = d & 3, (d >> 2) + 1
        if cmd == 0:
            out += src[len(out):len(out) + n]
        elif cmd == 1:
            out += p[i:i + n]
            i += n
        else:
            o, i = lire_varint(p, i)
            o = -(o >> 1) if o & 1 else o >> 1
            if cmd == 2:
                so += o
                out += src[so:so + n]
                so += n
            else:
                to += o
                if to + n <= len(out):          # sans chevauchement : copie directe
                    out += out[to:to + n]
                    to += n
                else:
                    for _ in range(n):
                        out.append(out[to])
                        to += 1
        if len(out) > nt:
            raise ErreurBps("BPS : cible plus longue qu'annoncé")
    if len(out) != nt or zlib.crc32(out) != crc_t:
        raise ErreurBps("BPS : résultat incorrect (CRC cible)")
    return bytes(out)


def bps_litteraux(p: bytes) -> list[tuple[int, bytes]]:
    """(position dans la cible, octets) de chaque TargetRead du patch."""
    i = 4
    _, i = lire_varint(p, i)
    _, i = lire_varint(p, i)
    nm, i = lire_varint(p, i)
    i += nm
    pos, fin, out = 0, len(p) - 12, []
    while i < fin:
        d, i = lire_varint(p, i)
        cmd, n = d & 3, (d >> 2) + 1
        if cmd == 1:
            out.append((pos, p[i:i + n]))
            i += n
        elif cmd in (2, 3):
            _, i = lire_varint(p, i)
        pos += n
    return out


# ------------------------------------------------------------------------------------------------ écriture
def ecrire_varint(v: int) -> bytes:
    out = bytearray()
    while True:
        x = v & 0x7F
        v >>= 7
        if v == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        v -= 1


def _crc_flux(f, debut: int, taille: int, crc: int = 0) -> int:
    f.seek(debut)
    reste = taille
    while reste:
        b = f.read(min(reste, 1 << 22))
        if not b:
            raise ErreurBps("fichier source tronqué")
        crc = zlib.crc32(b, crc)
        reste -= len(b)
    return crc


def bps_sur_place(f, base: int, taille: int, remplacements: list[tuple[int, bytes]],
                  ajout: bytes = b"") -> bytes:
    """Patch BPS d'un fichier (ouvert `f`, à `base`, de `taille` octets) dont seuls des morceaux changent, à
    taille égale : `remplacements` = [(position, nouveaux octets)…] disjoints. Actions : SourceRead entre les
    morceaux, TargetRead pour chacun. Le fichier n'est lu qu'en flux (CRC), jamais en entier en mémoire (les
    archives du jeu font jusqu'à ~1 Go).
    `ajout` : octets mis APRÈS la fin du fichier (la cible fait `taille + len(ajout)` octets ; Azahar donne au
    fichier patché la taille de la cible, `layered_fs.cpp` : `file.relocation.size = buffer.size()`)."""
    rs = sorted(remplacements)
    fin_prec = 0
    for pos, d in rs:
        if pos < fin_prec or pos + len(d) > taille:
            raise ErreurBps("remplacements qui se chevauchent ou sortent du fichier")
        fin_prec = pos + len(d)
    crc_s = _crc_flux(f, base, taille)
    p = bytearray(b"BPS1" + ecrire_varint(taille) + ecrire_varint(taille + len(ajout)) + ecrire_varint(0))
    crc_t, cur = 0, 0
    for pos, d in rs:
        if pos > cur:
            p += ecrire_varint(((pos - cur - 1) << 2) | 0)
            crc_t = _crc_flux(f, base + cur, pos - cur, crc_t)
        if d:
            p += ecrire_varint(((len(d) - 1) << 2) | 1) + d
            crc_t = zlib.crc32(d, crc_t)
        cur = pos + len(d)
    if taille > cur:
        p += ecrire_varint(((taille - cur - 1) << 2) | 0)
        crc_t = _crc_flux(f, base + cur, taille - cur, crc_t)
    if ajout:
        p += ecrire_varint(((len(ajout) - 1) << 2) | 1) + ajout
        crc_t = zlib.crc32(ajout, crc_t)
    p += struct.pack("<II", crc_s, crc_t)
    p += struct.pack("<I", zlib.crc32(bytes(p)))
    return bytes(p)


def bps_appliquer_flux(f, base: int, taille: int, p: bytes, sortie) -> int:
    """Applique à un GROS fichier (ouvert `f`, à `base`, de `taille` octets) un patch fait par `bps_sur_place`
    (actions SourceRead et TargetRead seulement), en flux : la cible est écrite dans `sortie` (fichier binaire
    ouvert en écriture). Vérifie le CRC du patch, de la source et de la cible ; renvoie la taille de la cible."""
    if p[:4] != b"BPS1" or len(p) < 4 + 3 + 12:
        raise ErreurBps("pas un patch BPS")
    if zlib.crc32(p[:-4]) != struct.unpack_from("<I", p, len(p) - 4)[0]:
        raise ErreurBps("BPS : CRC du patch invalide")
    i = 4
    ns, i = lire_varint(p, i)
    nt, i = lire_varint(p, i)
    nm, i = lire_varint(p, i)
    i += nm
    crc_s, crc_t = struct.unpack_from("<II", p, len(p) - 12)
    if ns != taille or _crc_flux(f, base, taille) != crc_s:
        raise ErreurBps("BPS : fichier source différent de celui attendu (CRC / taille)")
    pos, crc, fin = 0, 0, len(p) - 12
    while i < fin:
        d, i = lire_varint(p, i)
        cmd, n = d & 3, (d >> 2) + 1
        if cmd == 0:
            if pos + n > taille:
                raise ErreurBps("BPS : lecture de la source hors du fichier")
            f.seek(base + pos)
            reste = n
            while reste:
                b = f.read(min(reste, 1 << 22))
                if not b:
                    raise ErreurBps("fichier source tronqué")
                sortie.write(b)
                crc = zlib.crc32(b, crc)
                reste -= len(b)
        elif cmd == 1:
            b = p[i:i + n]
            i += n
            sortie.write(b)
            crc = zlib.crc32(b, crc)
        else:
            raise ErreurBps("BPS : action de copie non prise en charge en flux")
        pos += n
    if pos != nt or crc != crc_t:
        raise ErreurBps("BPS : résultat incorrect (CRC cible)")
    return nt
