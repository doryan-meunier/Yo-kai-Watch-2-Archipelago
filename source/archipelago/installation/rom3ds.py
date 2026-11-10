"""Extraction de code.bin et exheader.bin depuis la ROM DÉCHIFFRÉE du joueur (tâche I1).

    python archipelago/installation/rom3ds.py <rom.3ds|.cci|.cxi> [--sortie <dossier>]

Bibliothèque standard seulement. La ROM n'est ouverte qu'en lecture (quelques Mo lus, même pour un fichier
de 4 Go). Formats (3dbrew « NCSD », « NCCH », « NCCH/Extended Header », « ExeFS ») :

- `.3ds`/`.cci` : en-tête NCSD (« NCSD » à 0x100), table des partitions à 0x120 (8 × (offset, taille) en
  unités de 0x200 octets) ; la partition 0 est le NCCH exécutable (CXI) du jeu.
- `.cxi` : le NCCH directement, à l'offset 0.
- NCCH : « NCCH » à 0x100, Program ID à 0x118, code produit à 0x150, SHA-256 de l'exheader à 0x160,
  taille de l'exheader à 0x180 (0x400), drapeaux à 0x188 (octet 7 : bit 0x04 NoCrypto), ExeFS à 0x1A0
  (offset, taille en unités de 0x200). L'exheader (0x400) et l'AccessDesc (0x400) suivent l'en-tête :
  on extrait les 0x800 octets, comme orig/exheader.bin et comme le lisent Azahar et Luma3DS.
- Exheader : drapeaux du SCI à 0x0D (bit 0 : `.code` compressé), Title ID de l'ACI à 0x200.
- ExeFS : 10 entrées (nom 8, offset 4, taille 4) ; SHA-256 de l'entrée i à 0x200 - 0x20 × (i + 1) ;
  les données commencent à 0x200.
- Compression du `.code` : LZ77 « à rebours » (BLZ) : pied de 8 octets (u32 : taille compressée sur 24 bits
  | taille de l'en-tête de fin << 24 ; u32 : octets ajoutés à la décompression), lecture de la fin vers le
  début (même algorithme que ctrtool, Azahar `ncch_container.cpp` et Luma3DS).

Vérifications : ROM non chiffrée (NoCrypto), SHA-256 de l'exheader et du `.code` conformes à ceux du NCCH et
de l'ExeFS (une ROM chiffrée ou abîmée y échoue même si le drapeau est trompeur), Title ID
00040000001B2900 dans le NCCH et l'exheader, SHA-1 du code.bin décompressé = référence de la version
européenne. Chaque refus lève une `ErreurRom` au message explicite, destiné au joueur.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

MEDIA = 0x200
TITLE_ID = 0x00040000001B2900
TITLE_ID_STR = f"{TITLE_ID:016X}"
SHA1_CODE_REF = "66143fcb0d1ea75a054006bd342c4eb456a2a975"    # code.bin décompressé (CLAUDE.md)
TAILLE_CODE_REF = 7_737_344
EXHEADER_TAILLE = 0x800        # exheader 0x400 + AccessDesc 0x400
NCCH_FLAG_NOCRYPTO = 0x04      # drapeaux NCCH, octet 7

AIDE_DECHIFFRER = ("Faites une copie DÉCHIFFRÉE de votre cartouche avec GodMode9 sur votre console "
                   "(« Dump Cart (full) », puis « Decrypt file » si besoin) et choisissez ce fichier.")


class ErreurRom(Exception):
    """Refus de la ROM ; le message est destiné au joueur."""


class RomChiffree(ErreurRom):
    pass


class FormatInconnu(ErreurRom):
    pass


class VersionNonPriseEnCharge(ErreurRom):
    pass


class RomAbimee(ErreurRom):
    pass


@dataclass
class ContenuRom:
    """Résultat de l'extraction."""
    code: bytes                     # code.bin décompressé
    exheader: bytes                 # 0x800 octets, tel quel
    title_id: int
    code_produit: str
    format: str                     # "NCSD" (.3ds/.cci) ou "NCCH" (.cxi)
    offset_ncch: int
    code_etait_compresse: bool
    avertissements: list[str] = field(default_factory=list)

    @property
    def title_id_str(self) -> str:
        return f"{self.title_id:016X}"

    @property
    def sha1_code(self) -> str:
        return hashlib.sha1(self.code).hexdigest()

    @property
    def sha1_exheader(self) -> str:
        return hashlib.sha1(self.exheader).hexdigest()


# ------------------------------------------------------------------------------------------------
# Décompression BLZ (LZ77 à rebours du .code 3DS)
# ------------------------------------------------------------------------------------------------
def decompresser_blz(src: bytes) -> bytes:
    """Décompresse un `.code` 3DS. Lève RomAbimee si les données sont incohérentes."""
    n = len(src)
    if n < 8:
        raise RomAbimee("code compressé trop court")
    haut_bas, ajout = struct.unpack_from("<II", src, n - 8)
    lg_enc = haut_bas & 0xFFFFFF          # octets compressés, comptés depuis la fin (pied compris)
    lg_pied = haut_bas >> 24              # octets de fin à sauter avant le flux (pied + bourrage)
    if lg_enc > n or lg_pied < 8 or lg_pied > lg_enc:
        raise RomAbimee("en-tête de compression du code invalide")
    taille = n + ajout
    out = bytearray(taille)
    out[:n] = src
    i = n - lg_pied            # prochain octet à lire (en décroissant)
    arret = n - lg_enc         # début de la partie compressée (le reste est tel quel)
    o = taille                 # prochain octet à écrire (en décroissant)
    while i > arret:
        i -= 1
        ctrl = src[i]
        for _ in range(8):
            if i <= arret:
                break
            if ctrl & 0x80:
                if i - 2 < arret:
                    raise RomAbimee("flux compressé tronqué")
                i -= 2
                v = src[i] | (src[i + 1] << 8)
                lg = ((v >> 12) & 0xF) + 3
                dist = (v & 0x0FFF) + 2
                if o < lg:
                    raise RomAbimee("copie compressée hors des bornes")
                # l'octet écrit en o-1-k est lu en o-k+dist (déjà écrit : plus haut dans le tampon)
                if o + dist >= taille:
                    raise RomAbimee("référence compressée hors des bornes")
                if dist + 1 >= lg:            # pas de chevauchement : copie d'un bloc
                    out[o - lg:o] = out[o - lg + 1 + dist:o + 1 + dist]
                    o -= lg
                else:
                    for _k in range(lg):
                        out[o - 1] = out[o + dist]
                        o -= 1
            else:
                if o < 1:
                    raise RomAbimee("flux compressé trop long")
                i -= 1
                o -= 1
                out[o] = src[i]
            ctrl = (ctrl << 1) & 0xFF
    if o != arret:
        raise RomAbimee(f"décompression incomplète du code ({o:#x} != {arret:#x})")
    return bytes(out)


# ------------------------------------------------------------------------------------------------
# Lecture des conteneurs
# ------------------------------------------------------------------------------------------------
def _lire(f: BinaryIO, offset: int, taille: int) -> bytes:
    f.seek(offset)
    d = f.read(taille)
    if len(d) != taille:
        raise RomAbimee(f"fichier tronqué (lecture de {taille:#x} octets à {offset:#x})")
    return d


def trouver_ncch(f: BinaryIO) -> tuple[str, int]:
    """(format, offset du NCCH du jeu) : partition 0 d'un NCSD, ou NCCH à l'offset 0."""
    f.seek(0)
    h = f.read(0x200)
    if len(h) < 0x200:
        raise FormatInconnu("Fichier trop petit pour être une ROM 3DS.")
    magie = h[0x100:0x104]
    if magie == b"NCSD":
        off, taille = struct.unpack_from("<II", h, 0x120)
        if off == 0 or taille == 0:
            raise FormatInconnu("ROM .3ds sans partition de jeu (partition 0 vide).")
        return "NCSD", off * MEDIA
    if magie == b"NCCH":
        return "NCCH", 0
    if h[:4] == b"\x20\x20\x00\x00":
        raise FormatInconnu("Fichier .cia non pris en charge : choisissez une copie .3ds, .cci ou .cxi "
                            "de votre cartouche.")
    raise FormatInconnu("Ce fichier n'est pas une ROM 3DS reconnue (.3ds, .cci ou .cxi). Si c'est bien "
                        "votre ROM, elle est peut-être chiffrée. " + AIDE_DECHIFFRER)


def extraire(chemin: str | Path, *, title_id_attendu: int | None = TITLE_ID,
             sha1_attendu: str | None = SHA1_CODE_REF) -> ContenuRom:
    """Extrait et vérifie code.bin (décompressé) et l'exheader.

    `title_id_attendu`/`sha1_attendu` à None désactivent la vérification de version (tests synthétiques)."""
    chemin = Path(chemin)
    if not chemin.is_file():
        raise ErreurRom(f"ROM introuvable : {chemin}")
    with open(chemin, "rb") as f:
        fmt, base = trouver_ncch(f)
        ncch = _lire(f, base, 0x200)
        if ncch[0x100:0x104] != b"NCCH":
            raise FormatInconnu("Partition de jeu illisible (pas d'en-tête NCCH).")
        drapeaux = ncch[0x188:0x190]
        if not drapeaux[7] & NCCH_FLAG_NOCRYPTO:
            raise RomChiffree("Cette ROM est chiffrée : le mod ne peut pas la lire. " + AIDE_DECHIFFRER)
        program_id, = struct.unpack_from("<Q", ncch, 0x118)
        code_produit = ncch[0x150:0x160].split(b"\x00")[0].decode("ascii", "replace")
        taille_exh, = struct.unpack_from("<I", ncch, 0x180)
        if taille_exh != 0x400:
            raise FormatInconnu(f"Partition de jeu sans exheader standard (taille {taille_exh:#x}).")
        exheader = _lire(f, base + 0x200, EXHEADER_TAILLE)
        if hashlib.sha256(exheader[:0x400]).digest() != ncch[0x160:0x180]:
            raise RomChiffree("L'exheader ne correspond pas à son empreinte : la ROM est chiffrée (malgré "
                              "l'indication contraire) ou abîmée. " + AIDE_DECHIFFRER)
        tid_exh, = struct.unpack_from("<Q", exheader, 0x200)
        if title_id_attendu is not None and (program_id != title_id_attendu or tid_exh != title_id_attendu):
            raise VersionNonPriseEnCharge(
                f"Ce n'est pas Yo-kai Watch 2 version européenne (Title ID {program_id:016X}, attendu "
                f"{title_id_attendu:016X}) : version non prise en charge.")
        compresse = bool(exheader[0x0D] & 1)
        exefs_off, exefs_taille = struct.unpack_from("<II", ncch, 0x1A0)
        if exefs_off == 0 or exefs_taille == 0:
            raise FormatInconnu("La partition de jeu n'a pas d'ExeFS.")
        exefs = base + exefs_off * MEDIA
        eh = _lire(f, exefs, 0x200)
        entree = None
        for k in range(10):
            nom, off, taille = struct.unpack_from("<8sII", eh, 0x10 * k)
            if nom.rstrip(b"\x00") == b".code":
                entree = (k, off, taille)
                break
        if entree is None:
            raise RomAbimee("L'ExeFS ne contient pas de fichier .code.")
        k, off, taille = entree
        if off + taille > exefs_taille * MEDIA:
            raise RomAbimee("Entrée .code hors de l'ExeFS.")
        brut = _lire(f, exefs + 0x200 + off, taille)
        if hashlib.sha256(brut).digest() != eh[0x200 - 0x20 * (k + 1):0x200 - 0x20 * k]:
            raise RomChiffree("Le fichier .code ne correspond pas à son empreinte : la ROM est chiffrée ou "
                              "abîmée. " + AIDE_DECHIFFRER)
    code = decompresser_blz(brut) if compresse else brut
    c = ContenuRom(code=code, exheader=exheader, title_id=program_id, code_produit=code_produit, format=fmt,
                   offset_ncch=base, code_etait_compresse=compresse)
    if sha1_attendu is not None and c.sha1_code != sha1_attendu:
        raise VersionNonPriseEnCharge(
            f"Le code du jeu ne correspond pas à la version prise en charge (SHA-1 {c.sha1_code}, attendu "
            f"{sha1_attendu}) : version non prise en charge (mise à jour installée dans la ROM, autre "
            f"révision ou ROM modifiée).")
    return c


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--sortie", type=Path, help="dossier où écrire code.bin et exheader.bin (jamais dans git)")
    a = ap.parse_args(argv)
    try:
        c = extraire(a.rom)
    except ErreurRom as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    print(f"format {c.format} (NCCH à {c.offset_ncch:#x}), {c.code_produit}, Title ID {c.title_id_str}")
    print(f"code.bin : {len(c.code)} octets (compressé dans la ROM : {'oui' if c.code_etait_compresse else 'non'}),"
          f" SHA-1 {c.sha1_code} (référence OK)")
    print(f"exheader.bin : {len(c.exheader):#x} octets, SHA-1 {c.sha1_exheader}")
    if a.sortie:
        a.sortie.mkdir(parents=True, exist_ok=True)
        (a.sortie / "code.bin").write_bytes(c.code)
        (a.sortie / "exheader.bin").write_bytes(c.exheader)
        print(f"écrits dans {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
