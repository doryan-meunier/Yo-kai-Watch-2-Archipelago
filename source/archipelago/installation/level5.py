"""Formats Level-5 du RomFS de Yo-kai Watch 2 nécessaires au libellé du bouton (bibliothèque standard seulement).

Module autonome de l'installateur (distribué au joueur, comme `bps.py`) ; `tools/romfs/image.py` et
`tools/romfs/police.py` l'importent pour les usages de développement. Formats détaillés (certain/supposé) :
`docs/formats/level5.md` §2 à §4 et §8 à §10.

- RomFS : dossier déjà extrait (`yw2_a.fa`…) ou lu directement dans la ROM déchiffrée (NCSD/NCCH → IVFC
  niveau 3), sans rien extraire sur le disque.
- Compression Level-5 (lecture 0 à 5, écriture LZ10), archives ARC0 (`.fa`, lecture) et XPCK (lecture et
  reconstruction), images IMGC (`.xi`, lecture et écriture), maillages XPVB/XPVI et noms de l'ANMC
  (`RES.bin`) d'une archive de menu, police XF (`.xf` : FNT.bin + image), PNG (écriture, lecture simple).

Aucune donnée du jeu n'est contenue ici : tout est relu dans la ROM / le RomFS du joueur.
"""
from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

MEDIA = 0x200


class ErreurFormat(ValueError):
    """Fichier du jeu illisible ou différent de ce qu'attend le module (message destiné au joueur)."""


# ------------------------------------------------------------------------------------------------
# Compression Level-5 : u32 LE = méthode (bits 0-2) | taille décompressée << 3
# ------------------------------------------------------------------------------------------------
def entete_compression(data: bytes, off: int = 0) -> tuple[int, int]:
    v = struct.unpack_from("<I", data, off)[0]
    return v & 7, v >> 3


def _lz10(src, pos, taille):
    out = bytearray()
    n = len(src)
    while len(out) < taille and pos < n:
        flags = src[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= taille:
                break
            if flags & (0x80 >> bit):
                b0, b1 = src[pos], src[pos + 1]
                pos += 2
                longueur = (b0 >> 4) + 3
                debut = len(out) - ((((b0 & 0xF) << 8) | b1) + 1)
                if debut < 0:
                    raise ErreurFormat("LZ10 : référence avant le début des données")
                for i in range(longueur):
                    out.append(out[debut + i])
            else:
                out.append(src[pos])
                pos += 1
    return bytes(out[:taille])


def _huffman(src, pos, taille, bits):
    tree_size = src[pos]
    tree = bytes(src[pos:pos + (tree_size + 1) * 2])
    p = pos + (tree_size + 1) * 2
    out = bytearray()
    demi = -1
    node_pos = 1
    while len(out) < taille and p + 4 <= len(src):
        word = struct.unpack_from("<I", src, p)[0]
        p += 4
        for i in range(31, -1, -1):
            b = (word >> i) & 1
            node = tree[node_pos]
            child = (node_pos & ~1) + (node & 0x3F) * 2 + 2 + b
            if node & (0x80 >> b):
                val = tree[child]
                if bits == 8:
                    out.append(val)
                elif demi < 0:
                    demi = val & 0xF
                else:
                    out.append(demi | ((val & 0xF) << 4))
                    demi = -1
                node_pos = 1
                if len(out) >= taille:
                    break
            else:
                node_pos = child
    return bytes(out[:taille])


def _rle(src, pos, taille):
    out = bytearray()
    while len(out) < taille:
        f = src[pos]
        pos += 1
        if f & 0x80:
            out += bytes([src[pos]]) * ((f & 0x7F) + 3)
            pos += 1
        else:
            out += src[pos:pos + (f & 0x7F) + 1]
            pos += (f & 0x7F) + 1
    return bytes(out[:taille])


def decompresser(data: bytes, off: int = 0) -> bytes:
    methode, taille = entete_compression(data, off)
    pos = off + 4
    if methode == 0:
        return bytes(data[pos:pos + taille])
    if methode == 1:
        return _lz10(data, pos, taille)
    if methode in (2, 3):
        return _huffman(data, pos, taille, 4 if methode == 2 else 8)
    if methode == 4:
        return _rle(data, pos, taille)
    if methode == 5:
        # sortie bornée à `taille` AVANT de décompresser (un flux zlib malveillant peut multiplier sa taille par 1000)
        return zlib.decompressobj().decompress(bytes(data[pos:]), taille)
    raise ErreurFormat("méthode de compression Level-5 inconnue : %d" % methode)


def compresser_lz10(data: bytes, essais_max: int = 256) -> bytes:
    """Bloc Level-5 méthode 1 (LZ10), complété à 4 octets.

    Pour chaque position : plus longue correspondance (chaînes de hachage sur 3 octets, fenêtre 4 096,
    longueurs 3..18) ; puis découpage optimal par programmation dynamique (littéral 9 bits, référence
    17 bits). Un peu plus compact que la compression d'origine sur les images du menu titre.
    """
    data = bytes(data)
    n = len(data)
    tetes: dict[bytes, int] = {}
    prec = [-1] * n
    long_ = [0] * n
    dist = [0] * n
    for pos in range(n):
        if pos + 3 > n:
            break
        cle = data[pos:pos + 3]
        c = tetes.get(cle, -1)
        prec[pos] = c
        tetes[cle] = pos
        meil_l = meil_d = 0
        maxl = min(18, n - pos)
        essais = 0
        while c >= 0 and pos - c <= 4096 and essais < essais_max:
            if data[c + meil_l if meil_l < maxl else c] == data[pos + meil_l if meil_l < maxl else pos]:
                l = 3
                while l < maxl and data[c + l] == data[pos + l]:
                    l += 1
                if l > meil_l:
                    meil_l, meil_d = l, pos - c
                    if l == maxl:
                        break
            c = prec[c]
            essais += 1
        if meil_l >= 3:
            long_[pos], dist[pos] = meil_l, meil_d
    cout = [0] * (n + 1)
    choix = [0] * n
    for pos in range(n - 1, -1, -1):
        best, bl = 9 + cout[pos + 1], 1
        for l in range(3, long_[pos] + 1):
            c = 17 + cout[pos + l]
            if c < best:
                best, bl = c, l
        cout[pos], choix[pos] = best, bl
    out = bytearray(struct.pack("<I", (n << 3) | 1))
    pos = 0
    while pos < n:
        drap_pos = len(out)
        out.append(0)
        drap = 0
        for bit in range(8):
            if pos >= n:
                break
            l = choix[pos]
            if l >= 3:
                drap |= 0x80 >> bit
                d = dist[pos] - 1
                out += bytes((((l - 3) << 4) | (d >> 8), d & 0xFF))
                pos += l
            else:
                out.append(data[pos])
                pos += 1
        out[drap_pos] = drap
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def _longueurs_huffman(freq: dict[int, int]) -> dict[int, int]:
    """Longueurs de code de Huffman (au moins 2 symboles)."""
    import heapq
    tas = [(f, i, (s,)) for i, (s, f) in enumerate(sorted(freq.items()))]
    heapq.heapify(tas)
    lg = {s: 0 for s in freq}
    n = len(tas)
    while len(tas) > 1:
        f1, _i1, a = heapq.heappop(tas)
        f2, _i2, b = heapq.heappop(tas)
        for s in a + b:
            lg[s] += 1
        heapq.heappush(tas, (f1 + f2, n, a + b))
        n += 1
    return lg


def compresser_huffman8(data: bytes) -> bytes:
    """Bloc Level-5 méthode 3 (Huffman 8 bits Nintendo, relu par `_huffman`) : [taille de l'arbre][arbre][flux en
    mots u32 LE, bit de poids fort d'abord], complété à 4 octets.

    Arbre : nœud à l'index i = décalage (6 bits) de la paire de ses enfants, bit 7 / bit 6 = enfant 0 / 1 est une
    feuille ; paire des enfants à (i & ~1) + 2 + 2 × décalage, donc au plus 64 paires après celle du nœud. Placement
    des paires : dernier nœud créé d'abord (profondeur), sauf si cela rendrait une échéance intenable (la plus proche
    échéance est alors servie) ; ErreurFormat si l'arbre ne se place pas. Le résultat est relu et comparé."""
    data = bytes(data)
    freq: dict[int, int] = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    if not freq:
        freq = {0: 0}
    if len(freq) == 1:
        freq[(next(iter(freq)) + 1) & 0xFF] = 0             # arbre à deux feuilles au moins
    lg = _longueurs_huffman(freq)
    # codes canoniques, puis arbre explicite (nœud = [enfant0, enfant1], feuille = int)
    symboles = sorted(lg, key=lambda s: (lg[s], s))
    codes: dict[int, tuple[int, int]] = {}
    code, prec = 0, lg[symboles[0]]
    for s in symboles:
        code <<= lg[s] - prec
        prec = lg[s]
        codes[s] = (code, lg[s])
        code += 1
    racine: list = [None, None]
    for s, (c, n) in codes.items():
        noeud = racine
        for k in range(n - 1, 0, -1):
            b = (c >> k) & 1
            if noeud[b] is None:
                noeud[b] = [None, None]
            noeud = noeud[b]
        noeud[c & 1] = s
    # placement : paire 0 = (taille, racine) ; chaque nœud interne en attente a une échéance (dernière paire permise)
    table = bytearray(2)
    attente: list[tuple[int, list]] = [(1, racine)]      # (index du nœud dans la table, nœud)

    def echeance(i: int) -> int:
        return (i >> 1) + 64

    def tenable(liste: list, c: int) -> bool:
        return all(d >= c + j for j, d in enumerate(sorted(echeance(i) for i, _n in liste)))

    c = 1
    while attente:
        choix = len(attente) - 1                         # profondeur d'abord
        reste = attente[:choix] + [(2 * c + b, x) for b, x in enumerate(attente[choix][1]) if isinstance(x, list)]
        if not tenable(reste, c + 1):
            choix = min(range(len(attente)), key=lambda k: echeance(attente[k][0]))
        i, noeud = attente.pop(choix)
        if echeance(i) < c:
            raise ErreurFormat("Huffman : arbre impossible à placer")
        table += b"\0\0"
        v = c - (i >> 1) - 1
        for b in (0, 1):
            x = noeud[b]
            if isinstance(x, list):
                attente.append((2 * c + b, x))
            else:
                v |= 0x80 >> b
                table[2 * c + b] = x
        table[i] |= v
        c += 1
    while len(table) % 4:
        table += b"\0"
    if len(table) > 512:
        raise ErreurFormat("Huffman : arbre trop grand")
    table[0] = len(table) // 2 - 1
    out = bytearray(struct.pack("<I", (len(data) << 3) | 3)) + table
    mot, nb = 0, 0
    for byte in data:
        cd, n = codes[byte]
        for k in range(n - 1, -1, -1):
            mot = (mot << 1) | ((cd >> k) & 1)
            nb += 1
            if nb == 32:
                out += struct.pack("<I", mot)
                mot, nb = 0, 0
    if nb:
        out += struct.pack("<I", mot << (32 - nb))
    if _huffman(bytes(out), 4, len(data), 8) != data:
        raise ErreurFormat("Huffman : contrôle de l'encodage en échec")
    return bytes(out)


# ------------------------------------------------------------------------------------------------
# Sources du RomFS : dossier extrait, ou ROM déchiffrée (.3ds/.cci/.cxi) lue sur place
# ------------------------------------------------------------------------------------------------
class SourceRomfs:
    """Accès aux fichiers de la racine du RomFS : `ouvrir(nom)` -> (fichier binaire, offset, taille)."""

    def __init__(self, chemin: str | Path):
        self.chemin = Path(chemin)
        self.fichiers: dict[str, tuple[int, int]] = {}
        if self.chemin.is_dir():
            self.rom = None
        else:
            self.rom = self.chemin
            self._lire_rom()

    def _lire_rom(self):
        with open(self.rom, "rb") as f:
            h = f.read(0x200)
            base = 0
            if h[0x100:0x104] == b"NCSD":
                base = struct.unpack_from("<I", h, 0x120)[0] * MEDIA
                f.seek(base)
                h = f.read(0x200)
            if h[0x100:0x104] != b"NCCH":
                raise ErreurFormat(f"{self.rom} : ni NCSD ni NCCH (ROM déchiffrée attendue)")
            if not h[0x18F] & 0x04:
                raise ErreurFormat(f"{self.rom} : ROM chiffrée (drapeau NoCrypto absent)")
            romfs_off, romfs_taille = struct.unpack_from("<II", h, 0x1B0)
            if not romfs_taille:
                raise ErreurFormat(f"{self.rom} : pas de RomFS")
            ivfc = base + romfs_off * MEDIA
            f.seek(ivfc)
            iv = f.read(0x60)
            if iv[:4] != b"IVFC":
                raise ErreurFormat(f"{self.rom} : en-tête IVFC du RomFS introuvable")
            maitre = struct.unpack_from("<I", iv, 0x08)[0]
            bloc3 = 1 << struct.unpack_from("<I", iv, 0x4C)[0]
            n3 = ivfc + ((0x60 + maitre + bloc3 - 1) // bloc3) * bloc3
            f.seek(n3)
            e = struct.unpack("<10I", f.read(0x28))
            dmeta_off, dmeta_t, fmeta_off, fmeta_t, donnees = e[3], e[4], e[7], e[8], e[9]
            f.seek(n3 + dmeta_off)
            dmeta = f.read(dmeta_t)
            f.seek(n3 + fmeta_off)
            fmeta = f.read(fmeta_t)
        fichier = struct.unpack_from("<I", dmeta, 12)[0]       # premier fichier de la racine
        while fichier != 0xFFFFFFFF:
            _par, suivant, off, taille, _h, lg = struct.unpack_from("<IIQQII", fmeta, fichier)
            nom = fmeta[fichier + 0x20:fichier + 0x20 + lg].decode("utf-16-le")
            self.fichiers[nom] = (n3 + donnees + off, taille)
            fichier = suivant

    def ouvrir(self, nom: str):
        if self.rom is None:
            p = self.chemin / nom
            if not p.is_file():
                raise ErreurFormat(f"{p} introuvable dans le RomFS")
            return open(p, "rb"), 0, p.stat().st_size
        if nom not in self.fichiers:
            raise ErreurFormat(f"{nom} absent du RomFS de {self.rom}")
        off, taille = self.fichiers[nom]
        return open(self.rom, "rb"), off, taille

    def lire_tout(self, nom: str) -> bytes:
        f, off, taille = self.ouvrir(nom)
        with f:
            f.seek(off)
            return f.read(taille)


# ------------------------------------------------------------------------------------------------
# ARC0 (.fa) : lecture des tables (voir tools/romfs/arc0.py)
# ------------------------------------------------------------------------------------------------
class Arc0:
    """Archive ARC0 à `base` dans le fichier `f` (laissé ouvert par l'appelant)."""

    def __init__(self, f, base: int = 0):
        self.f, self.base = f, base
        f.seek(base)
        h = f.read(0x48)
        if h[:4] != b"ARC0":
            raise ErreurFormat("archive .fa invalide (magie %r)" % h[:4])
        off_d, _off_h, off_f, off_n, self.off_donnees = struct.unpack_from("<5I", h, 4)
        nb_d = struct.unpack_from("<H", h, 0x18)[0]
        f.seek(base)
        tables = f.read(self.off_donnees)
        dossiers, fichiers, noms = (decompresser(tables, o) for o in (off_d, off_f, off_n))

        def chaine(o):
            return noms[o:noms.index(b"\0", o)].decode("ascii", "replace")
        self.entrees: dict[str, tuple[int, int]] = {}     # chemin -> (offset relatif à base, taille)
        for i in range(nb_d):
            _c, _a, _b, f0, fn, off_nf, off_nd = struct.unpack_from("<IhhhhII", dossiers, i * 20)
            nd = chaine(off_nd)
            for j in range(f0, f0 + fn):
                _fc, off_nom, off_fi, taille = struct.unpack_from("<4I", fichiers, j * 16)
                self.entrees[nd + chaine(off_nf + off_nom)] = (self.off_donnees + off_fi, taille)

    def lire(self, nom: str) -> bytes:
        if nom not in self.entrees:
            raise ErreurFormat(f"{nom} absent de l'archive")
        off, taille = self.entrees[nom]
        self.f.seek(self.base + off)
        return self.f.read(taille)


def _compresser_comme(methode: int, data: bytes) -> bytes:
    if methode == 3:
        return compresser_huffman8(data)
    if methode == 1:
        return compresser_lz10(data)
    if methode == 0:
        b = struct.pack("<I", len(data) << 3) + bytes(data)
        return b + b"\0" * (-len(b) % 4)
    raise ErreurFormat("ARC0 : méthode de compression de table non prise en charge (%d)" % methode)


def arc0_ajouter_fichier(tete: bytes, dossier: str, nom: str, contenu: bytes, alignement: int = 16) -> bytes:
    """Ajoute le fichier `dossier` + `nom` (dossier existant, avec `/` final) à une archive ARC0 SANS changer sa
    taille ni déplacer aucun fichier : `tete` = les `off_donnees` premiers octets de l'archive (en-tête et tables) ;
    renvoie la nouvelle tête, de même longueur, à écrire à sa place.

    Lecteur du jeu (`docs/formats/level5.md` §3) : tables des dossiers, des hachages et des fichiers lues à la suite
    depuis 0x48 (tailles = différences des offsets +4/+8/+0xC/+0x10), double dichotomie NON SIGNÉE sur les crc
    (dossier avec `/` final, puis nom du fichier dans la tranche u16 premier / nombre du dossier), position =
    +0x14 + offset (32 bits) ; ni noms, ni hachages de dossiers, ni +0x1C / +0x24..+0x47 lus.

    - table des fichiers : entrée {crc32(nom), nom, 0, taille} insérée à sa place (triée par crc dans le dossier),
      nombre de fichiers (+0x1C, et +0x3C s'il le répète) + 1 ; recompressée avec la méthode d'origine (Huffman
      8 bits pour les archives du jeu) ;
    - table des dossiers : « premier fichier » + 1 pour TOUS les autres dossiers dont le premier fichier est au rang
      d'insertion ou après (la table est triée par crc, pas par rang), nombre de fichiers du dossier + 1 ;
      recompressée de même ; table des hachages : octets d'origine ;
    - table des noms : nom ajouté à la fin (le jeu ne la lit pas ; outils seulement), recompressée de même ;
    - zone de données : son début (+0x14) est ABAISSÉ juste après les tables, le contenu y est logé (alignement
      `alignement` depuis le début de l'archive), et tous les offsets de fichiers augmentent d'autant : chaque
      fichier existant garde sa position absolue ;
    - +0x20 (taille du tas des tables = Σ align4(taille décompressée + 8) des quatre tables) : recalculé.
    ErreurFormat si la tête n'est pas celle attendue, si le fichier existe déjà, ou si tables + contenu ne tiennent
    pas dans la place de l'ancienne tête."""
    tete = bytes(tete)
    if tete[:4] != b"ARC0" or len(tete) < 0x48:
        raise ErreurFormat("archive .fa invalide")
    off_d, off_h, off_f, off_n, off_donnees = struct.unpack_from("<5I", tete, 4)
    nb_d = struct.unpack_from("<H", tete, 0x18)[0]
    nb_f = struct.unpack_from("<I", tete, 0x1C)[0]
    if len(tete) != off_donnees or not 0x48 == off_d <= off_h <= off_f <= off_n <= off_donnees:
        raise ErreurFormat("ARC0 : tête inattendue")
    m_f, m_n = entete_compression(tete, off_f)[0], entete_compression(tete, off_n)[0]
    dossiers = bytearray(decompresser(tete, off_d))
    fichiers = bytearray(decompresser(tete, off_f))
    noms = bytearray(decompresser(tete, off_n))
    if len(dossiers) < nb_d * 20 or len(fichiers) != nb_f * 16:
        raise ErreurFormat("ARC0 : tables incohérentes avec l'en-tête")

    def chaine(o):
        return bytes(noms[o:noms.index(b"\0", o)])
    cible = None
    for i in range(nb_d):
        if chaine(struct.unpack_from("<I", dossiers, i * 20 + 16)[0]) == dossier.encode("ascii"):
            cible = i
    if cible is None:
        raise ErreurFormat(f"ARC0 : dossier {dossier} absent")
    _c, _a, _b, f0, fn, off_nf, _o = struct.unpack_from("<IhhHHII", dossiers, cible * 20)
    crc = zlib.crc32(nom.encode("ascii")) & 0xFFFFFFFF
    crcs = [struct.unpack_from("<I", fichiers, j * 16)[0] for j in range(f0, f0 + fn)]
    if crc in crcs:
        raise ErreurFormat(f"ARC0 : {dossier}{nom} existe déjà")
    if crcs != sorted(crcs):
        raise ErreurFormat("ARC0 : fichiers du dossier non triés par crc")
    if nb_f + 1 > 0xFFFF:
        raise ErreurFormat("ARC0 : trop de fichiers")
    rang = f0 + sum(1 for c in crcs if c < crc)
    # décalage des offsets : calculé après la mise en page, appliqué ensuite (les tailles compressées en dépendent
    # peu : on itère jusqu'à stabilité)
    ajout_nom = nom.encode("ascii") + b"\0"
    noms2 = bytes(noms) + ajout_nom
    for i in range(nb_d):
        if i != cible:
            d0 = struct.unpack_from("<H", dossiers, i * 20 + 8)[0]
            if d0 >= rang:
                struct.pack_into("<H", dossiers, i * 20 + 8, d0 + 1)
    struct.pack_into("<H", dossiers, cible * 20 + 10, fn + 1)
    if bytes(dossiers) != decompresser(tete, off_d):
        # le « premier fichier » d'autres dossiers change : la table des dossiers est recompressée aussi
        m_d = entete_compression(tete, off_d)[0]
        cdossiers = _compresser_comme(m_d, bytes(dossiers))
    else:
        cdossiers = tete[off_d:off_h]
    chach = tete[off_h:off_f]
    cnoms = _compresser_comme(m_n, noms2)
    decalage = 0
    debut_min = 0
    for essai in range(36):
        f2 = bytearray()
        for j in range(nb_f):
            c, o_nom, o_fi, t = struct.unpack_from("<4I", fichiers, j * 16)
            if j == rang:
                f2 += struct.pack("<4I", crc, len(noms) - off_nf, 0, len(contenu))
            if o_fi + decalage > 0xFFFFFFFF:
                raise ErreurFormat("ARC0 : offset de fichier hors limites")
            f2 += struct.pack("<4I", c, o_nom, o_fi + decalage, t)
        if rang == nb_f:
            f2 += struct.pack("<4I", crc, len(noms) - off_nf, 0, len(contenu))
        cfichiers = _compresser_comme(m_f, bytes(f2))
        fin_tables = off_d + len(cdossiers) + len(chach) + len(cfichiers) + len(cnoms)
        # Le début des données dépend de la taille compressée de la table des fichiers, qui dépend des offsets,
        # donc du début des données : 4 tours « au plus juste » (comportement d'origine, inchangé quand il
        # converge), puis, s'il oscille, début des données seulement repoussé (suite monotone : elle s'arrête).
        nouveau_debut = max(fin_tables + (-fin_tables % alignement), debut_min)
        if nouveau_debut + len(contenu) > off_donnees:
            raise ErreurFormat("ARC0 : pas de place pour le fichier ajouté (%d octets, %d libres)"
                               % (len(contenu), off_donnees - nouveau_debut))
        if off_donnees - nouveau_debut == decalage:
            break
        decalage = off_donnees - nouveau_debut
        if essai >= 3:
            debut_min = nouveau_debut
    else:
        raise ErreurFormat("ARC0 : mise en page instable")
    h = bytearray(tete[:0x48])
    n_h = off_d + len(cdossiers)
    n_f = n_h + len(chach)
    n_n = n_f + len(cfichiers)
    struct.pack_into("<5I", h, 4, off_d, n_h, n_f, n_n, nouveau_debut)
    struct.pack_into("<I", h, 0x1C, nb_f + 1)
    if struct.unpack_from("<I", h, 0x3C)[0] == nb_f:
        struct.pack_into("<I", h, 0x3C, nb_f + 1)
    def a4(n):
        return (n + 8 + 3) & ~3
    croissance = a4(len(f2)) - a4(len(fichiers)) + a4(len(noms2)) - a4(len(noms))
    struct.pack_into("<I", h, 0x20, struct.unpack_from("<I", h, 0x20)[0] + croissance)
    out = bytes(h) + tete[0x48:off_d] + cdossiers + chach + cfichiers + cnoms
    out += b"\0" * (nouveau_debut - len(out)) + bytes(contenu)
    out += b"\0" * (off_donnees - len(out))
    assert len(out) == off_donnees
    return out


def arc0_tables(tete: bytes) -> tuple[bytes, bytes, int, int]:
    """(table des dossiers, table des fichiers, début des données, nombre de dossiers) d'une tête ARC0."""
    off_d, _off_h, off_f, _off_n, off_donnees = struct.unpack_from("<5I", tete, 4)
    return decompresser(tete, off_d), decompresser(tete, off_f), off_donnees, struct.unpack_from("<H", tete, 0x18)[0]


def arc0_recherche_jeu(tete, chemin: str) -> tuple[int, int] | None:
    """Recherche d'un fichier COMME LE FAIT LE JEU (`FUN_001EF684`, docs/formats/level5.md §3bis) : dossier par
    dichotomie non signée sur crc32(dossier avec « / »), fichier par dichotomie sur crc32(nom) dans la tranche
    (premier, nombre) du dossier ; les noms ne sont pas lus. Renvoie (position absolue dans l'archive, taille) ou
    None. Sert à contrôler une tête modifiée. `tete` : la tête, ou le résultat de `arc0_tables(tete)` (pour
    beaucoup de recherches)."""
    dossiers, fichiers, off_donnees, nb_d = tete if isinstance(tete, tuple) else arc0_tables(tete)
    coupe = chemin.rfind("/") + 1
    cd = zlib.crc32(chemin[:coupe].encode("ascii")) & 0xFFFFFFFF
    cf = zlib.crc32(chemin[coupe:].encode("ascii")) & 0xFFFFFFFF

    def dicho(table, pas, debut, nombre, crc):
        a, b = 0, nombre
        while a < b:
            m = (a + b) // 2
            c = struct.unpack_from("<I", table, (debut + m) * pas)[0]
            if c == crc:
                return debut + m
            if c < crc:
                a = m + 1
            else:
                b = m
        return None
    i = dicho(dossiers, 20, 0, nb_d, cd)
    if i is None:
        return None
    f0, fn = struct.unpack_from("<HH", dossiers, i * 20 + 8)
    j = dicho(fichiers, 16, f0, fn, cf)
    if j is None:
        return None
    _c, _n, off, taille = struct.unpack_from("<4I", fichiers, j * 16)
    return (off_donnees + off) & 0xFFFFFFFF, taille


def arc0_modifier(tete: bytes, taille_archive: int, remplacements: dict[str, bytes] | None = None,
                  ajouts: dict[str, bytes] | None = None) -> tuple[bytes, bytes]:
    """Remplace des fichiers (de TAILLE QUELCONQUE) et en ajoute dans une archive ARC0, sans déplacer aucun autre
    fichier : les nouveaux contenus sont mis À LA FIN de l'archive, qui grandit.

    `tete` = les `off_donnees` premiers octets (en-tête et tables) ; `taille_archive` = taille actuelle ;
    `remplacements` / `ajouts` = {chemin complet: contenu} (le dossier d'un ajout doit exister). Renvoie
    (nouvelle tête, de même longueur ; octets à ajouter à la fin de l'archive).

    - chaque contenu est écrit à la suite, suivi d'au moins un octet nul puis complété au multiple de 4 (disposition
      des archives du jeu) ; l'entrée du fichier reçoit son nouvel offset (relatif au début des données, +0x14,
      inchangé) et sa nouvelle taille ; l'ancienne place d'un fichier remplacé reste inutilisée ;
    - ajout : même traitement des tables que `arc0_ajouter_fichier` (entrée insérée à sa place triée par crc dans
      la tranche du dossier, « premier fichier » + 1 pour les autres dossiers à partir du rang d'insertion, nombre
      de fichiers du dossier et de l'archive + 1, nom ajouté à la fin de la table des noms) ;
    - tables des dossiers, des fichiers et des noms recompressées avec leur méthode d'origine (une table inchangée
      garde ses octets) ; elles doivent tenir avant le début des données (le reste est mis à zéro) ; +0x20 recalculé.
    La tête rendue est une tête valide : on peut lui appliquer ensuite `arc0_ajouter_fichier` (icône de la
    vitrine), qui abaisse le début des données et décale tous les offsets, les nouveaux compris.
    ErreurFormat : tête inattendue, fichier à remplacer absent, fichier à ajouter déjà présent, dossier absent,
    offset hors de 32 bits, tables trop grandes."""
    remplacements = dict(remplacements or {})
    ajouts = dict(ajouts or {})
    tete = bytes(tete)
    if tete[:4] != b"ARC0" or len(tete) < 0x48:
        raise ErreurFormat("archive .fa invalide")
    off_d, off_h, off_f, off_n, off_donnees = struct.unpack_from("<5I", tete, 4)
    nb_d = struct.unpack_from("<H", tete, 0x18)[0]
    nb_f = struct.unpack_from("<I", tete, 0x1C)[0]
    if len(tete) != off_donnees or not 0x48 == off_d <= off_h <= off_f <= off_n <= off_donnees or \
            taille_archive < off_donnees:
        raise ErreurFormat("ARC0 : tête inattendue")
    m_d, m_f, m_n = (entete_compression(tete, o)[0] for o in (off_d, off_f, off_n))
    dossiers0 = decompresser(tete, off_d)
    fichiers0 = decompresser(tete, off_f)
    noms0 = decompresser(tete, off_n)
    dossiers, fichiers, noms = bytearray(dossiers0), bytearray(fichiers0), bytearray(noms0)
    if len(dossiers) < nb_d * 20 or len(fichiers) != nb_f * 16:
        raise ErreurFormat("ARC0 : tables incohérentes avec l'en-tête")

    def chaine(o):
        return bytes(noms[o:noms.index(b"\0", o)]).decode("ascii", "replace")

    def dossier_de(nom_dossier):
        for i in range(nb_d):
            if chaine(struct.unpack_from("<I", dossiers, i * 20 + 16)[0]) == nom_dossier:
                return i
        return None
    suffixe = bytearray(b"\0" * (-taille_archive % 4))

    def loger(contenu: bytes) -> int:
        off = taille_archive + len(suffixe) - off_donnees
        if off > 0xFFFFFFFF or len(contenu) > 0xFFFFFFFF:
            raise ErreurFormat("ARC0 : offset de fichier hors limites")
        suffixe.extend(bytes(contenu) + b"\0")
        suffixe.extend(b"\0" * (-len(suffixe) % 4))
        return off
    # --- remplacements : l'entrée garde son rang, son crc et son nom
    for chemin in sorted(remplacements):
        coupe = chemin.rfind("/") + 1
        i = dossier_de(chemin[:coupe])
        trouve = None
        if i is not None:
            f0, fn, off_nf = struct.unpack_from("<HHI", dossiers, i * 20 + 8)
            for j in range(f0, f0 + fn):
                if chaine(off_nf + struct.unpack_from("<I", fichiers, j * 16 + 4)[0]) == chemin[coupe:]:
                    trouve = j
        if trouve is None:
            raise ErreurFormat(f"ARC0 : {chemin} absent (remplacement impossible)")
        struct.pack_into("<II", fichiers, trouve * 16 + 8, loger(remplacements[chemin]), len(remplacements[chemin]))
    # --- ajouts
    for chemin in sorted(ajouts):
        coupe = chemin.rfind("/") + 1
        nom = chemin[coupe:]
        cible = dossier_de(chemin[:coupe])
        if cible is None or not nom:
            raise ErreurFormat(f"ARC0 : dossier de {chemin} absent")
        f0, fn, off_nf = struct.unpack_from("<HHI", dossiers, cible * 20 + 8)
        crc = zlib.crc32(nom.encode("ascii")) & 0xFFFFFFFF
        crcs = [struct.unpack_from("<I", fichiers, j * 16)[0] for j in range(f0, f0 + fn)]
        if crc in crcs:
            raise ErreurFormat(f"ARC0 : {chemin} existe déjà")
        if crcs != sorted(crcs):
            raise ErreurFormat("ARC0 : fichiers du dossier non triés par crc")
        if len(fichiers) // 16 + 1 > 0xFFFF or fn + 1 > 0xFFFF:
            raise ErreurFormat("ARC0 : trop de fichiers")
        if len(noms) < off_nf:
            raise ErreurFormat("ARC0 : table des noms incohérente")
        rang = f0 + sum(1 for c in crcs if c < crc)
        contenu = ajouts[chemin]
        fichiers[rang * 16:rang * 16] = struct.pack("<4I", crc, len(noms) - off_nf, loger(contenu), len(contenu))
        noms += nom.encode("ascii") + b"\0"
        for i in range(nb_d):
            if i != cible:
                d0 = struct.unpack_from("<H", dossiers, i * 20 + 8)[0]
                if d0 >= rang:
                    struct.pack_into("<H", dossiers, i * 20 + 8, d0 + 1)
        struct.pack_into("<H", dossiers, cible * 20 + 10, fn + 1)
    # --- mise en page
    cdossiers = tete[off_d:off_h] if bytes(dossiers) == dossiers0 else _compresser_comme(m_d, bytes(dossiers))
    cfichiers = tete[off_f:off_n] if bytes(fichiers) == fichiers0 else _compresser_comme(m_f, bytes(fichiers))
    cnoms = _compresser_comme(m_n, bytes(noms))
    chach = tete[off_h:off_f]
    n_h = off_d + len(cdossiers)
    n_f = n_h + len(chach)
    n_n = n_f + len(cfichiers)
    if n_n + len(cnoms) > off_donnees:
        raise ErreurFormat("ARC0 : tables modifiées trop grandes (%d octets de trop)"
                           % (n_n + len(cnoms) - off_donnees))
    h = bytearray(tete[:0x48])
    struct.pack_into("<5I", h, 4, off_d, n_h, n_f, n_n, off_donnees)
    nb_f2 = len(fichiers) // 16
    if struct.unpack_from("<I", h, 0x3C)[0] == nb_f:
        struct.pack_into("<I", h, 0x3C, nb_f2)
    struct.pack_into("<I", h, 0x1C, nb_f2)

    def a4(n):
        return (n + 8 + 3) & ~3
    croissance = a4(len(fichiers)) - a4(len(fichiers0)) + a4(len(noms)) - a4(len(noms0))
    struct.pack_into("<I", h, 0x20, struct.unpack_from("<I", h, 0x20)[0] + croissance)
    out = bytes(h) + tete[0x48:off_d] + cdossiers + chach + cfichiers + cnoms
    out += b"\0" * (off_donnees - len(out))
    return out, bytes(suffixe)


# ------------------------------------------------------------------------------------------------
# XPCK : lecture et reconstruction avec des fichiers remplacés
# ------------------------------------------------------------------------------------------------
class Xpck:
    def __init__(self, data: bytes):
        if data[:4] != b"XPCK":
            raise ErreurFormat("archive XPCK invalide (magie %r)" % data[:4])
        self.data = bytes(data)
        self.nb = struct.unpack_from("<H", data, 4)[0] & 0xFFF
        self.off_info, off_noms, self.off_donnees = [x * 4 for x in struct.unpack_from("<3H", data, 6)]
        noms = decompresser(data, off_noms)
        self.fichiers = []      # [nom, offset relatif aux données, taille]
        for i in range(self.nb):
            _c, on, olo, tlo, ohi, thi = struct.unpack_from("<IHHHBB", data, self.off_info + 12 * i)
            nom = noms[on:noms.index(b"\0", on)].decode("ascii", "replace")
            self.fichiers.append([nom, ((ohi << 16) | olo) << 2, (thi << 16) | tlo])
        self.par_nom = {f[0]: f for f in self.fichiers}

    def lire(self, nom: str) -> bytes:
        _n, off, t = self.par_nom[nom]
        return self.data[self.off_donnees + off:self.off_donnees + off + t]

    def reconstruire(self, remplacements: dict[str, bytes], ajouts: dict[str, bytes] | None = None) -> bytes:
        """Même en-tête, mêmes entrées et table de noms ; données réécrites dans l'ordre d'origine,
        chaque fichier suivi d'au moins un octet nul puis aligné sur 4 (disposition des archives du
        jeu : la reconstruction sans remplacement redonne l'archive d'origine octet pour octet).
        `ajouts` = {nom: contenu} de fichiers NOUVEAUX : voir `_avec_ajouts`."""
        if ajouts:
            return Xpck(self._avec_ajouts(ajouts)).reconstruire(remplacements)
        ordre = sorted(range(self.nb), key=lambda i: self.fichiers[i][1])
        donnees = bytearray()
        nouv = {}
        for i in ordre:
            nom = self.fichiers[i][0]
            contenu = remplacements.get(nom, None)
            if contenu is None:
                contenu = self.lire(nom)
            nouv[i] = (len(donnees), len(contenu))
            donnees += contenu + b"\0"          # toujours au moins un zéro, puis alignement sur 4 [C]
            while len(donnees) % 4:
                donnees.append(0)
        tete = bytearray(self.data[:self.off_donnees])
        for i, (off, t) in nouv.items():
            e = self.off_info + 12 * i
            o4 = off >> 2
            if o4 >= 1 << 24 or t >= 1 << 24:
                raise ErreurFormat("XPCK : fichier trop grand")
            struct.pack_into("<HHBB", tete, e + 6, o4 & 0xFFFF, t & 0xFFFF, o4 >> 16, t >> 16)
        struct.pack_into("<I", tete, 0x10, len(donnees) >> 2)
        return bytes(tete) + bytes(donnees)

    def _avec_ajouts(self, ajouts: dict[str, bytes]) -> bytes:
        """Archive avec des fichiers en plus : entrées gardées TRIÉES par crc32 du nom (ordre des archives du jeu),
        nom ajouté à la fin de la table des noms (recompressée avec sa méthode d'origine, LZ10 ou aucune), données
        ajoutées à la fin ; les 4 bits hauts du mot de comptage (+4) sont gardés. Les offsets des fichiers
        existants (relatifs au début des données) ne changent pas."""
        d = self.data
        mot = struct.unpack_from("<H", d, 4)[0]
        off_noms = struct.unpack_from("<H", d, 8)[0] * 4
        if self.off_info + 12 * self.nb != off_noms:
            raise ErreurFormat("XPCK : disposition inattendue (entrées)")
        methode = entete_compression(d, off_noms)[0]
        noms = bytearray(decompresser(d, off_noms))
        entrees = [bytearray(d[self.off_info + 12 * i:self.off_info + 12 * i + 12]) for i in range(self.nb)]
        crcs = [struct.unpack_from("<I", e, 0)[0] for e in entrees]
        if crcs != sorted(crcs):
            raise ErreurFormat("XPCK : entrées non triées par crc")
        donnees = bytearray(d[self.off_donnees:])
        if len(donnees) % 4:
            raise ErreurFormat("XPCK : données non alignées")
        for nom in sorted(ajouts):
            contenu = ajouts[nom]
            crc = zlib.crc32(nom.encode("ascii")) & 0xFFFFFFFF
            if nom in self.par_nom or crc in crcs:
                raise ErreurFormat(f"XPCK : {nom} existe déjà")
            o4 = len(donnees) >> 2
            if o4 >= 1 << 24 or len(contenu) >= 1 << 24 or len(noms) > 0xFFFF or len(entrees) + 1 > 0xFFF:
                raise ErreurFormat("XPCK : archive trop grande")
            e = bytearray(struct.pack("<IHHHBB", crc, len(noms), o4 & 0xFFFF, len(contenu) & 0xFFFF,
                                      o4 >> 16, len(contenu) >> 16))
            rang = sum(1 for c in crcs if c < crc)
            entrees.insert(rang, e)
            crcs.insert(rang, crc)
            noms += nom.encode("ascii") + b"\0"
            donnees += bytes(contenu) + b"\0"
            donnees += b"\0" * (-len(donnees) % 4)
        cnoms = _compresser_comme(methode, bytes(noms))
        cnoms += b"\0" * (-len(cnoms) % 4)
        tete = bytearray(d[:self.off_info]) + b"".join(entrees)
        n_noms = len(tete)
        tete += cnoms
        n_donnees = len(tete)
        if n_noms // 4 > 0xFFFF or n_donnees // 4 > 0xFFFF:
            raise ErreurFormat("XPCK : tables trop grandes")
        struct.pack_into("<H", tete, 4, (mot & 0xF000) | len(entrees))
        struct.pack_into("<3H", tete, 6, self.off_info // 4, n_noms // 4, n_donnees // 4)
        struct.pack_into("<2H", tete, 0x0C, len(entrees) * 12 // 4, len(cnoms) // 4)
        struct.pack_into("<I", tete, 0x10, len(donnees) >> 2)
        return bytes(tete) + bytes(donnees)


# ------------------------------------------------------------------------------------------------
# IMGC (.xi)
# ------------------------------------------------------------------------------------------------
FORMATS_PIXELS = {0: ("RGBA8", 32), 1: ("RGBA4444", 16), 2: ("RGBA5551", 16), 3: ("RGB8", 24),
                  4: ("RGB565", 16), 0xB: ("LA8", 16), 0xC: ("LA4", 8), 0xD: ("L8", 8), 0xF: ("A8", 8),
                  0x11: ("L4", 4), 0x12: ("A4", 4), 0x1B: ("ETC1", 4), 0x1C: ("ETC1A4", 8)}
FORMATS_ETC = (0x1B, 0x1C)

# Ordre dans une tuile 8×8 : bits de l'index, du poids faible au fort = y0 x0 y1 x1 y2 x2 [C]
MORTON = []
for _i in range(64):
    MORTON.append((((_i >> 1) & 1) | ((_i >> 2) & 2) | ((_i >> 3) & 4),
                   (_i & 1) | ((_i >> 1) & 2) | ((_i >> 2) & 4)))


def _ext(v, bits):
    return (v * 255 + ((1 << bits) - 1) // 2) // ((1 << bits) - 1)


def _q(v, bits):
    return (v * ((1 << bits) - 1) + 127) // 255


def _decoder_pixel(fmt, b, i):
    if fmt == 0:
        a, bl, g, r = b[4 * i:4 * i + 4]
        return r, g, bl, a
    if fmt == 3:
        bl, g, r = b[3 * i:3 * i + 3]
        return r, g, bl, 255
    if fmt in (1, 2, 4, 0xB):
        v = b[2 * i] | (b[2 * i + 1] << 8)
        if fmt == 1:
            return _ext(v >> 12, 4), _ext((v >> 8) & 15, 4), _ext((v >> 4) & 15, 4), _ext(v & 15, 4)
        if fmt == 2:
            return _ext(v >> 11, 5), _ext((v >> 6) & 31, 5), _ext((v >> 1) & 31, 5), 255 if v & 1 else 0
        if fmt == 4:
            return _ext(v >> 11, 5), _ext((v >> 5) & 63, 6), _ext(v & 31, 5), 255
        return v >> 8, v >> 8, v >> 8, v & 255
    if fmt in (0xC, 0xD, 0xF):
        v = b[i]
        if fmt == 0xC:
            return _ext(v >> 4, 4), _ext(v >> 4, 4), _ext(v >> 4, 4), _ext(v & 15, 4)
        return (v, v, v, 255) if fmt == 0xD else (255, 255, 255, v)
    v = (b[i >> 1] >> (4 * (i & 1))) & 15
    return (_ext(v, 4),) * 3 + (255,) if fmt == 0x11 else (255, 255, 255, _ext(v, 4))


# ETC1 / ETC1A4 [C : atlas d'icônes d'objets (item_icon.xi, docs/formats/level5.md §11), lisible ainsi]
# Tuile 8×8 = 4 blocs 4×4 dans l'ordre (0,0), (0,4), (4,0), (4,4) (x, y) ; un bloc = [8 octets d'alpha 4 bits
# (ETC1A4 seulement)] + mot ETC1 de 64 bits en petit-boutiste. Le pixel (X, Y) du bloc a l'index i = Y*4 + X
# (transposé par rapport à l'ETC1 usuel, comme l'ordre Morton y0 x0 des autres formats) ; alpha au quartet i.
ETC_BLOCS = ((0, 0), (0, 4), (4, 0), (4, 4))
ETC_TABLES = ((2, 8), (5, 17), (9, 29), (13, 42), (18, 60), (24, 80), (33, 106), (47, 183))


def _borner(v):
    return 0 if v < 0 else 255 if v > 255 else v


def _etc_ext5(v):
    return (v << 3) | (v >> 2)


def _etc_bases(w):
    if (w >> 33) & 1:
        c1 = [(w >> s) & 31 for s in (59, 51, 43)]
        d = [(w >> s) & 7 for s in (56, 48, 40)]
        c2 = [(c + (x - 8 if x & 4 else x)) & 31 for c, x in zip(c1, d)]
        return tuple(_etc_ext5(v) for v in c1), tuple(_etc_ext5(v) for v in c2)
    return (tuple(((w >> s) & 15) * 17 for s in (60, 52, 44)), tuple(((w >> s) & 15) * 17 for s in (56, 48, 40)))


def _etc_sous_bloc(flip, X, Y):
    """0 ou 1 : sous-bloc du pixel (X, Y) d'un bloc (disposition transposée, voir ETC_BLOCS)."""
    return int(X >= 2) if flip else int(Y >= 2)


def decoder_bloc_etc1(w: int) -> list[tuple[int, int, int]]:
    """Mot ETC1 -> 16 couleurs, index i = Y*4 + X."""
    flip = (w >> 32) & 1
    bases = _etc_bases(w)
    tabs = ((w >> 37) & 7, (w >> 34) & 7)
    out = []
    for i in range(16):
        sb = _etc_sous_bloc(flip, i & 3, i >> 2)
        m = ETC_TABLES[tabs[sb]][(w >> i) & 1]
        if (w >> (16 + i)) & 1:
            m = -m
        out.append(tuple(_borner(c + m) for c in bases[sb]))
    return out


def decoder_tuile_etc(fmt: int, b: bytes) -> list[tuple[int, int, int, int]]:
    """Tuile ETC1 (32 octets) ou ETC1A4 (64 octets) -> 64 pixels (r, g, b, a), index y*8 + x."""
    pix = [(0, 0, 0, 0)] * 64
    t = 16 if fmt == 0x1C else 8
    for k, (bx, by) in enumerate(ETC_BLOCS):
        bl = b[t * k:t * (k + 1)]
        alpha = struct.unpack_from("<Q", bl, 0)[0] if fmt == 0x1C else None
        couleurs = decoder_bloc_etc1(struct.unpack_from("<Q", bl, t - 8)[0])
        for i, c in enumerate(couleurs):
            a = ((alpha >> (4 * i)) & 15) * 17 if alpha is not None else 255
            pix[(by + (i >> 2)) * 8 + bx + (i & 3)] = c + (a,)
    return pix


def _etc_erreur(px, poids, base, table):
    """Meilleurs modificateurs d'un sous-bloc : (erreur pondérée, [(msb, lsb)…])."""
    err, choix = 0, []
    for (r, g, b), p in zip(px, poids):
        meilleur = None
        for lsb in (0, 1):
            for msb in (0, 1):
                m = -table[lsb] if msb else table[lsb]
                e = ((_borner(base[0] + m) - r) ** 2 + (_borner(base[1] + m) - g) ** 2 +
                     (_borner(base[2] + m) - b) ** 2)
                if meilleur is None or e < meilleur[0]:
                    meilleur = (e, msb, lsb)
        err += meilleur[0] * p
        choix.append(meilleur[1:])
    return err, choix


def _etc_chercher(px, poids, moyenne, diff, ref=None):
    """Meilleure (erreur, table, base quantifiée, modificateurs) d'un sous-bloc. Pour chaque table : base =
    moyenne quantifiée, puis raffinée aux moindres carrés d'après les modificateurs choisis (3 tours) ; enfin
    ±1 par canal autour du meilleur. `ref` : base du 1er sous-bloc en mode différentiel (écart -4..3)."""
    n = 31 if diff else 15

    def quant(v):
        q = [min(n, max(0, round(c * n / 255))) for c in v]
        return [min(a + 3, max(a - 4, c)) for a, c in zip(ref, q)] if ref is not None else q

    def essai(q, table):
        base = tuple(_etc_ext5(v) for v in q) if diff else tuple(v * 17 for v in q)
        return _etc_erreur(px, poids, base, table)
    s = sum(poids) or 1
    best = None
    for ti, table in enumerate(ETC_TABLES):
        q, vus = quant(moyenne), set()
        for _tour in range(3):
            if tuple(q) in vus:
                break
            vus.add(tuple(q))
            e, choix = essai(q, table)
            if best is None or e < best[0]:
                best = (e, ti, q, choix)
            ms = [(-table[l] if m else table[l]) for m, l in choix]
            q = quant([sum((p[c] - m) * w for p, m, w in zip(px, ms, poids)) / s for c in range(3)])
    e0, ti, q0, _c = best
    for dr in (-1, 0, 1):
        for dg in (-1, 0, 1):
            for db in (-1, 0, 1):
                q = [min(n, max(0, v + d)) for v, d in zip(q0, (dr, dg, db))]
                if ref is not None:
                    q = [min(a + 3, max(a - 4, c)) for a, c in zip(ref, q)]
                e, choix = essai(q, ETC_TABLES[ti])
                if e < best[0]:
                    best = (e, ti, q, choix)
    return best


def encoder_bloc_etc1(px: list, poids: list) -> int:
    """16 couleurs (index i = Y*4 + X) pondérées (un pixel transparent ne compte pas) -> mot ETC1.
    Recherche : 2 découpes × 2 modes (individuel 4 bits, différentiel 5+3 bits) × 8 tables, base raffinée
    (`_etc_chercher`). Suffisant pour une icône (64 blocs en quelques secondes)."""
    if not any(poids):
        poids = [1] * 16
    meilleur = None
    for flip in (0, 1):
        groupes = ([], [])
        for i in range(16):
            groupes[_etc_sous_bloc(flip, i & 3, i >> 2)].append(i)
        moyennes = []
        for g in groupes:
            s = sum(poids[i] for i in g)
            moyennes.append([sum(px[i][c] * poids[i] for i in g) / s if s else 0 for c in range(3)])
        for diff in (1, 0):
            r0 = _etc_chercher([px[i] for i in groupes[0]], [poids[i] for i in groupes[0]], moyennes[0], diff)
            r1 = _etc_chercher([px[i] for i in groupes[1]], [poids[i] for i in groupes[1]], moyennes[1], diff,
                               r0[2] if diff else None)
            total = r0[0] + r1[0]
            if meilleur is None or total < meilleur[0]:
                meilleur = (total, flip, diff, [r0, r1], groupes)
    _t, flip, diff, res, groupes = meilleur
    (_e1, t1, c1, ch1), (_e2, t2, c2, ch2) = res
    w = (flip << 32) | (diff << 33) | (t1 << 37) | (t2 << 34)
    if diff:
        for k, s in enumerate((59, 51, 43)):
            w |= (c1[k] << s) | (((c2[k] - c1[k]) & 7) << (s - 3))
    else:
        for k, s in enumerate((60, 52, 44)):
            w |= (c1[k] << s) | (c2[k] << (s - 4))
    for g, ch in zip(groupes, (ch1, ch2)):
        for i, (msb, lsb) in zip(g, ch):
            w |= (msb << (16 + i)) | (lsb << i)
    return w


def encoder_tuile_etc(fmt: int, pix: list) -> bytes:
    """64 pixels (r, g, b, a), index y*8 + x -> tuile ETC1 (32 octets) ou ETC1A4 (64 octets)."""
    out = bytearray()
    for bx, by in ETC_BLOCS:
        bloc = [pix[(by + (i >> 2)) * 8 + bx + (i & 3)] for i in range(16)]
        if fmt == 0x1C:
            alpha = 0
            for i, p in enumerate(bloc):
                alpha |= ((p[3] * 15 + 127) // 255) << (4 * i)
            out += struct.pack("<Q", alpha)
            poids = [p[3] for p in bloc]
        else:
            poids = [1] * 16
        out += struct.pack("<Q", encoder_bloc_etc1([p[:3] for p in bloc], poids))
    return bytes(out)


def _encoder_tuile(fmt, px):
    out = bytearray()
    if fmt in (0x11, 0x12):
        vals = [_q(p[0] if fmt == 0x11 else p[3], 4) for p in px]
        return bytes(vals[i] | (vals[i + 1] << 4) for i in range(0, 64, 2))
    for r, g, bl, a in px:
        if fmt == 0:
            out += bytes((a, bl, g, r))
        elif fmt == 3:
            out += bytes((bl, g, r))
        elif fmt == 1:
            out += struct.pack("<H", (_q(r, 4) << 12) | (_q(g, 4) << 8) | (_q(bl, 4) << 4) | _q(a, 4))
        elif fmt == 2:
            out += struct.pack("<H", (_q(r, 5) << 11) | (_q(g, 5) << 6) | (_q(bl, 5) << 1) | (a >= 128))
        elif fmt == 4:
            out += struct.pack("<H", (_q(r, 5) << 11) | (_q(g, 6) << 5) | _q(bl, 5))
        elif fmt == 0xB:
            out += bytes((a, r))
        elif fmt == 0xC:
            out.append((_q(r, 4) << 4) | _q(a, 4))
        else:
            out.append(r if fmt == 0xD else a)
    return bytes(out)


class Imgc:
    """Image IMGC décodée : `pixels` = liste de (r, g, b, a) en lignes, `largeur` × `hauteur`."""

    def __init__(self, data: bytes):
        if data[:4] != b"IMGC":
            raise ErreurFormat("image IMGC invalide (magie %r)" % data[:4])
        self.entete = bytes(data[:0x48])
        self.format, self.bpp = data[0xA], data[0xD]
        self.octets_tuile = struct.unpack_from("<H", data, 0xE)[0]
        self.largeur, self.hauteur = struct.unpack_from("<HH", data, 0x10)
        _t, self.t_table_pad, _d = struct.unpack_from("<3I", data, 0x34)
        if self.format not in FORMATS_PIXELS:
            raise ErreurFormat("format de pixels IMGC non pris en charge : 0x%X" % self.format)
        if self.octets_tuile != 64 * self.bpp // 8:
            raise ErreurFormat("IMGC : taille de tuile inattendue")
        self.methodes = (entete_compression(data, 0x48)[0], entete_compression(data, 0x48 + self.t_table_pad)[0])
        table = decompresser(data, 0x48)
        tuiles = decompresser(data, 0x48 + self.t_table_pad)
        self.table = struct.unpack("<%dH" % (len(table) // 2), table)
        self.nb_tuiles = len(tuiles) // self.octets_tuile
        tl, th = (self.largeur + 7) // 8, (self.hauteur + 7) // 8
        if len(self.table) < tl * th:
            raise ErreurFormat("IMGC : table de tuiles trop courte")
        w, h, ot = self.largeur, self.hauteur, self.octets_tuile
        pix = [(0, 0, 0, 0)] * (w * h)
        for n in range(tl * th):
            idx = self.table[n]
            if idx == 0xFFFF:
                continue
            b = tuiles[idx * ot:(idx + 1) * ot]
            if len(b) < ot:
                raise ErreurFormat("IMGC : index de tuile hors des données")
            x0, y0 = (n % tl) * 8, (n // tl) * 8
            if self.format in FORMATS_ETC:
                for i, p in enumerate(decoder_tuile_etc(self.format, b)):
                    x, y = x0 + (i & 7), y0 + (i >> 3)
                    if x < w and y < h:
                        pix[y * w + x] = p
                continue
            for i, (dx, dy) in enumerate(MORTON):
                x, y = x0 + dx, y0 + dy
                if x < w and y < h:
                    pix[y * w + x] = _decoder_pixel(self.format, b, i)
        self.pixels = pix

    def encoder(self, pixels=None) -> bytes:
        """Mêmes format et dimensions ; tuiles identiques fusionnées, tuiles entièrement (0, 0, 0, 0) ->
        0xFFFF (comme l'original) ; table et tuiles compressées en LZ10."""
        pixels = self.pixels if pixels is None else pixels
        w, h = self.largeur, self.hauteur
        tl, th = (w + 7) // 8, (h + 7) // 8
        uniques: dict[bytes, int] = {}
        donnees = bytearray()
        table = []
        for n in range(tl * th):
            x0, y0 = (n % tl) * 8, (n // tl) * 8
            if self.format in FORMATS_ETC:
                px = [pixels[(y0 + i // 8) * w + x0 + i % 8] if x0 + i % 8 < w and y0 + i // 8 < h
                      else (0, 0, 0, 0) for i in range(64)]
            else:
                px = [pixels[(y0 + dy) * w + x0 + dx] if x0 + dx < w and y0 + dy < h else (0, 0, 0, 0)
                      for dx, dy in MORTON]
            if all(p == (0, 0, 0, 0) for p in px):
                table.append(0xFFFF)
                continue
            b = encoder_tuile_etc(self.format, px) if self.format in FORMATS_ETC else _encoder_tuile(self.format, px)
            if b not in uniques:
                uniques[b] = len(uniques)
                donnees += b
            table.append(uniques[b])
        if len(uniques) >= 0xFFFF:
            raise ErreurFormat("IMGC : trop de tuiles distinctes")
        ctable = compresser_lz10(struct.pack("<%dH" % len(table), *table))
        cdonnees = compresser_lz10(bytes(donnees))
        e = bytearray(self.entete)
        struct.pack_into("<3I", e, 0x34, len(ctable), len(ctable), len(cdonnees))
        return bytes(e) + ctable + cdonnees


# ------------------------------------------------------------------------------------------------
# Maillages d'une archive de menu : XPVB (sommets), XPVI (index), ANMC (noms des maillages)
# ------------------------------------------------------------------------------------------------
def sommets_xpvb(data: bytes) -> list[tuple[float, float, float, float, float]]:
    """Sommets (x, y, z, u, v) ; u, v en pixels de la texture [C pour 20 octets / sommet]."""
    if data[:4] != b"XPVB":
        raise ErreurFormat("XPVB invalide")
    off, pas, nb = struct.unpack_from("<3H", data, 8)
    if pas != 20:
        raise ErreurFormat("XPVB : %d octets par sommet (20 attendus)" % pas)
    brut = decompresser(data, off)
    return [struct.unpack_from("<5f", brut, 20 * i) for i in range(min(nb, len(brut) // 20))]


def index_xpvi(data: bytes) -> list[int]:
    if data[:4] != b"XPVI":
        raise ErreurFormat("XPVI invalide")
    nb = struct.unpack_from("<I", data, 8)[0]
    brut = decompresser(data, 0x0C)
    return list(struct.unpack_from("<%dH" % nb, brut, 0))


def quads_isoles(index: list[int]) -> list[int]:
    """Premiers sommets a des quadrilatères isolés (triangles a, a+2, a+1 puis a+1, a+3, a+2)."""
    res = []
    for i in range(0, len(index) - 5, 6):
        a = index[i]
        if index[i:i + 6] == [a, a + 2, a + 1, a + 3, a + 1, a + 2] and a not in res:
            res.append(a)
    return res


def noms_maillages(res_bin: bytes) -> list[str]:
    """Noms des parties de l'ANMC (`RES.bin`) dans l'ordre de la table de chaînes, après les entrées
    « #nom n » : même ordre que les maillages `000.pbi`, `001.pbi`… [S fort : vérifié visuellement
    pour btn_01…btn_04 et btn_update du menu titre, FR et EN]."""
    x = decompresser(res_bin, 0)
    if x[:4] != b"ANMC":
        raise ErreurFormat("RES.bin : ANMC attendu")
    chaines = [m.group().decode() for m in re.finditer(rb"[\x21-\x7e][\x20-\x7e]*(?=\x00)", x)]
    dernier_diese = max((i for i, c in enumerate(chaines) if c.startswith("#")), default=-1)
    return [c for c in chaines[dernier_diese + 1:] if " " not in c]


# ------------------------------------------------------------------------------------------------
# Police XF (`fnt/ft_nrm.xf` de yw2_a.fa) : XPCK { 000.xi, FNT.bin }
# ------------------------------------------------------------------------------------------------
class Police:
    """Glyphes : code -> (largeur d'avance, décalage x, décalage y, l, h, canal, x, y dans l'image)."""

    def __init__(self, xf: bytes):
        pk = Xpck(xf)
        fnt = pk.lire("FNT.bin")
        if fnt[:6] != b"FNTC01":
            raise ErreurFormat("FNT.bin : FNTC01 attendu")
        self.hauteur = struct.unpack_from("<H", fnt, 0x0C)[0]
        so, _sc, lo, lc = struct.unpack_from("<4H", fnt, 0x1C)
        tailles = decompresser(fnt, so * 4)
        grands = decompresser(fnt, lo * 4)
        self.image = Imgc(pk.lire("000.xi"))
        self.glyphes = {}
        for i in range(min(lc, len(grands) // 8)):
            code, info_c, info_i = struct.unpack_from("<HHI", grands, 8 * i)
            ox, oy, gw, gh = struct.unpack_from("<bbBB", tailles, 4 * (info_c & 0x3FF))
            self.glyphes[code] = (info_c >> 10, ox, oy, gw, gh, info_i & 0xF,
                                  (info_i >> 4) & 0x3FFF, info_i >> 18)

    def couverture(self, code: int):
        """(avance, ox, oy, l, h, liste de couvertures 0..1 en lignes)."""
        av, ox, oy, gw, gh, canal, gx, gy = self.glyphes[code]
        W = self.image.largeur
        cov = [self.image.pixels[(gy + y) * W + gx + x][canal] / 255.0 for y in range(gh) for x in range(gw)]
        return av, ox, oy, gw, gh, cov


# ------------------------------------------------------------------------------------------------
# PNG
# ------------------------------------------------------------------------------------------------
def ecrire_png(chemin, largeur: int, hauteur: int, pixels) -> None:
    brut = bytearray()
    for y in range(hauteur):
        brut.append(0)
        for p in pixels[y * largeur:(y + 1) * largeur]:
            brut += bytes(p)

    def morceau(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    Path(chemin).write_bytes(b"\x89PNG\r\n\x1a\n" +
                             morceau(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 6, 0, 0, 0)) +
                             morceau(b"IDAT", zlib.compress(bytes(brut), 9)) + morceau(b"IEND", b""))


def lire_png(chemin):
    """PNG 8 bits (gris, gris+alpha, RGB, RGBA), non entrelacé -> (largeur, hauteur, pixels RGBA)."""
    d = Path(chemin).read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ErreurFormat("pas un PNG")
    p, idat = 8, b""
    w = h = prof = typ = entrel = None
    while p < len(d):
        n = struct.unpack_from(">I", d, p)[0]
        t, c = d[p + 4:p + 8], d[p + 8:p + 8 + n]
        if t == b"IHDR":
            w, h, prof, typ, _c, _f, entrel = struct.unpack(">IIBBBBB", c)
        elif t == b"IDAT":
            idat += c
        p += 12 + n
    if prof != 8 or entrel or typ not in (0, 2, 4, 6):
        raise ErreurFormat("PNG non pris en charge (8 bits, non entrelacé, sans palette)")
    nc = {0: 1, 2: 3, 4: 2, 6: 4}[typ]
    brut = zlib.decompress(idat)
    ligne = w * nc
    prec = bytearray(ligne)
    pix, pos = [], 0
    for _y in range(h):
        filtre = brut[pos]
        cur = bytearray(brut[pos + 1:pos + 1 + ligne])
        pos += 1 + ligne
        for i in range(ligne):
            a = cur[i - nc] if i >= nc else 0
            b = prec[i]
            c = prec[i - nc] if i >= nc else 0
            if filtre == 1:
                cur[i] = (cur[i] + a) & 255
            elif filtre == 2:
                cur[i] = (cur[i] + b) & 255
            elif filtre == 3:
                cur[i] = (cur[i] + ((a + b) >> 1)) & 255
            elif filtre == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        for x in range(w):
            v = cur[x * nc:(x + 1) * nc]
            pix.append((v[0], v[0], v[0], 255) if nc == 1 else (v[0], v[0], v[0], v[1]) if nc == 2
                       else (v[0], v[1], v[2], 255) if nc == 3 else tuple(v))
        prec = cur
    return w, h, pix
