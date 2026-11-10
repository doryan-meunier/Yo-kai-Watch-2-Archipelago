"""Icône Archipelago de l'objet vitrine dans le jeu (bibliothèque standard seulement).

    python archipelago/installation/icone.py --romfs <RomFS extrait | ROM déchiffrée> --sortie <dossier du titre>
           [--apercu <dossier hors git>]

L'objet vitrine 0xA0531A08 (`iky2020`, « Important Item 20 », jamais donné par le jeu : objets des autres mondes
dans les coffres, dons de script, récompenses de quête, fenêtre « objet obtenu ») a pour icône la case
(colonne 7, ligne 31) de l'atlas d'icônes d'objets : champs v12/v13 de son entrée `ITEM_IMPORTANT` de
`item_config_0.04b.cfg.bin`. Cette case est un carré factice numéroté « 504 », utilisé par cette seule entrée.

L'atlas (IMGC ETC1A4 512×1024, grille 16×32 de cases 32×32) est chargé une fois pour toutes (ressource
« ItemIcon », 0x003C437C) par le résolveur localisé `FUN_00419AE8` : `data/menu/item_icon/<lg>/item_icon.xi`
s'il existe (de, nl, ru : dans leur archive de langue), sinon l'atlas commun de `yw2_a.fa` (fr, engb, es,
it). Les quatre atlas sont donc modifiés.

À L'INSTALLATION, à partir du RomFS du joueur, pour chaque atlas :
1. vérifie son SHA-1 (atlas d'origine attendu ; sinon il est laissé tel quel, avertissement : repli propre) ;
2. ré-encode en ETC1A4 notre icône (`ressources/icone_objet.png`, logo de MDarkmooN) dans les 16 tuiles 8×8 de
   la case, SANS toucher à la table de tuiles (ses octets compressés restent ceux d'origine). Dix de ces tuiles
   sont partagées avec d'autres carrés factices (cases sans objet, et celles d'`iky2022`/`iky2024`, jamais
   donnés) : vérifié ici, refus sinon ;
3. recompresse le bloc de tuiles (LZ10), qui doit tenir dans la place de l'original ;
4. renvoie les octets à remplacer : l'installateur en fait un patch BPS « sur place » par archive
   (`romfs_ext/<archive>.bps`, fusionné avec celui du libellé pour les archives de langue).

GRANDE IMAGE (64×64) : les écrans qui montrent un objet en grand (fiche d'objet et boutons du choix de l'écran de
résultat d'une requête, fenêtres « objet obtenu » et de don de script, loterie, grattage…) chargent, par script,
`data/menu/item_icon/item_%03d` avec le n° = colonne + 16 × ligne + 1 de la case (`ItemIcon_GetID`, rubrique 1 de
la commande 0x3B22). Pour la vitrine : 504, fichier ABSENT du jeu (carré orange ou bouton vide). Il est AJOUTÉ à
`yw2_a.fa` (`level5.arc0_ajouter_fichier`) : notre image (`ressources/icone_objet_64.png`, IMGC ETC1A4 64×64 dont
l'en-tête vient d'une image voisine du joueur), logée dans la place libérée en tête de l'archive, sans changer sa
taille ni la position d'aucun fichier ; seuls l'en-tête et les tables changent (patch « sur place » fusionné avec
celui de l'atlas). Refus propre (avertissement) si la tête de l'archive n'est pas celle attendue (SHA-1).

Aucun octet du jeu n'est versionné ni distribué. Détails : `docs/formats/level5.md` §3bis et §11.
Note : Azahar charge en mémoire tout fichier patché par `romfs_ext/` ; pour `yw2_a.fa` (967 Mo), c'est ~1 Go de
mémoire en plus pendant la partie.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import bps as _bps, level5 as L
except ImportError:                     # lancé comme script
    import bps as _bps  # type: ignore[no-redef]
    import level5 as L  # type: ignore[no-redef]

VITRINE = 0xA0531A08
COLONNE, LIGNE, CASE = 7, 31, 32         # case de la vitrine dans l'atlas (item_config : v12, v13) [C]
FORMAT = 0x1C                            # ETC1A4
LARGEUR, HAUTEUR = 512, 1024
ESSAIS_LZ_REAFFECTEES = 1024             # profondeur de recherche LZ10 quand des cases sont réaffectées (modifier_atlas)
ICONE = Path(__file__).resolve().parent / "ressources" / "icone_objet.png"
GRANDE = Path(__file__).resolve().parent / "ressources" / "icone_objet_64.png"
TAILLE_GRANDE = 64
ID_GRANDE = LIGNE * 16 + COLONNE + 1     # n° de `item_%03d` de la vitrine (ItemIcon_GetID) [C, scripts]
NOM_GRANDE = "item_%03d.xi" % ID_GRANDE
MODELE_GRANDE = "item_%03d.xi" % (ID_GRANDE - 1)      # image 64×64 voisine : en-tête IMGC seulement
# SHA-1 de la tête (en-tête + tables, jusqu'au début des données) de `yw2_a.fa` d'origine : identifiant de
# vérification, pas une donnée du jeu
SHA1_TETE_A = "2d468782184b12f8bd84811aa1bc768671f9cb72"

DOSSIER_ATLAS = "data/menu/item_icon/"
NOM_ATLAS = "item_icon.xi"               # (chemins assemblés : le paquet ne recopie aucune chaîne de code.bin)
# (archive, chemin de l'atlas, SHA-1 de l'atlas d'origine : identifiant de vérification, pas une donnée du jeu)
ATLAS = (
    ("yw2_a.fa", DOSSIER_ATLAS + NOM_ATLAS, "88277a98dac69f4486e5c3f7f2af6baaa8fafdcc"),
    ("yw2_lg_de.fa", DOSSIER_ATLAS + "de/" + NOM_ATLAS, "ee8a5da4e89c4ba5a4c8d3e09a1bea4fa4b70712"),
    ("yw2_lg_nl.fa", DOSSIER_ATLAS + "nl/" + NOM_ATLAS, "45365ef3bed37c9a4f4f8d98fcd625a171dd2c7b"),
    ("yw2_lg_ru.fa", DOSSIER_ATLAS + "ru/" + NOM_ATLAS, "4319edbb3a3c6ffed10e03a33edd854ce345cdd7"),
)
# Cases qui peuvent partager des tuiles avec celle de la vitrine : carrés factices numérotés, aucun objet
# (item_config) ou objets jamais donnés (505 = iky2022, 507 = iky2024) [C, relevé sur l'original].
CASES_FACTICES = frozenset({108, 110, 155, 194, 196, 198, 202, 211, 215, 241, 245, 262, 264, 296, 298, 300,
                            503, 505, 507, 509})


@dataclass
class Modification:
    fichier: str
    position: int
    octets: bytes
    langue: str = ""
    resultat: object = None


@dataclass
class Resultat:
    fichier: str
    atlas: str
    taille_origine: int
    taille_nouvelle: int
    tuiles: list = field(default_factory=list)       # index des tuiles réécrites
    partagees: dict = field(default_factory=dict)    # index -> cases qui la partagent
    pixels_case: list = field(default_factory=list)  # la case telle que le jeu la décodera (32×32 RGBA)
    cases_en_plus: dict = field(default_factory=dict)  # (colonne, ligne) -> pixels décodés des autres icônes posées
    videes: list = field(default_factory=list)       # tuiles libres vidées (cases réaffectées seulement)


def ErreurFormat_case(colonne: int, ligne: int, quoi: str) -> "L.ErreurFormat":
    return L.ErreurFormat(f"case ({colonne}, {ligne}) : {quoi}")


def charger_icone(chemin: Path = ICONE):
    """32×32 RGBA ; la couleur des pixels transparents est étendue depuis les pixels voisins (pas de liseré au
    filtrage, et l'ETC1 n'a pas à coder une couleur arbitraire sous l'alpha nul)."""
    w, h, pix = L.lire_png(chemin)
    if (w, h) != (CASE, CASE):
        raise L.ErreurFormat(f"{chemin} : {w}×{h}, {CASE}×{CASE} attendu")
    pix = [tuple(p) for p in pix]
    connus = {i for i, p in enumerate(pix) if p[3]}
    if not connus:
        raise L.ErreurFormat(f"{chemin} : image vide")
    rgb = {i: pix[i][:3] for i in connus}
    while len(rgb) < CASE * CASE:
        ajout = {}
        for i in range(CASE * CASE):
            if i in rgb:
                continue
            x, y = i % CASE, i // CASE
            v = [rgb[j] for j in (i - 1 if x else -1, i + 1 if x < CASE - 1 else -1, i - CASE, i + CASE)
                 if 0 <= j < CASE * CASE and j in rgb]
            if v:
                ajout[i] = tuple(sum(c[k] for c in v) // len(v) for k in range(3))
        rgb.update(ajout)
    return [rgb[i] + (pix[i][3],) for i in range(CASE * CASE)]


def _tuiles_case(table, colonne: int = COLONNE, ligne: int = LIGNE):
    """[(position n de la table, x0, y0 dans la case)] des 16 tuiles de la case."""
    tl = LARGEUR // 8
    return [((ligne * 4 + ty) * tl + colonne * 4 + tx, tx * 8, ty * 8) for ty in range(4) for tx in range(4)]


def _case_de(n: int) -> int:
    tl = LARGEUR // 8
    return (n // tl // 4) * 16 + (n % tl) // 4


def modifier_atlas(xi: bytes, icone: list, sha1: str | None, cases_en_plus=()) -> tuple[bytes, Resultat]:
    """Atlas modifié (même taille que `xi`, complété par des zéros) ; lève ErreurFormat si l'atlas n'est pas
    celui attendu ou si le résultat ne tient pas.
    `cases_en_plus` : [(colonne, ligne, pixels 32×32, cases factices permises)] d'autres icônes à poser dans le même
    bloc de tuiles (invitations.py) ; chacune ne doit toucher que des tuiles de ses cases factices permises, et
    aucune tuile de la vitrine ; leurs pixels décodés sont rendus dans `Resultat.cases_en_plus`. Sans elles, le
    résultat est celui d'avant, octet pour octet.
    Un 5e élément vrai (`reaffecter`, objets_voyage.py) : la case reçoit 16 tuiles LIBRES qui lui sont propres (tuiles
    dont toutes les cases utilisatrices sont des cases factices permises, jamais écrites par une autre icône) et la
    table de tuiles est réécrite (recompressée en Huffman 8 bits, comme l'originale) : les 33 cases sans objet sont
    des cercles numérotés qui se partagent leurs tuiles (deux familles, celles de la vitrine et de l'enveloppe), aucune
    n'a de tuiles à elle seule. Les cases factices dont une tuile est reprise montrent un fragment d'icône : aucun
    objet ne les affiche. Sans case réaffectée, la table n'est pas touchée (résultat d'avant, octet pour octet)."""
    if sha1 is not None and hashlib.sha1(xi).hexdigest() != sha1:
        raise L.ErreurFormat("atlas différent de l'original attendu (autre version du jeu ou autre mod)")
    if xi[:4] != b"IMGC" or xi[0xA] != FORMAT or struct.unpack_from("<HH", xi, 0x10) != (LARGEUR, HAUTEUR):
        raise L.ErreurFormat("atlas inattendu (IMGC ETC1A4 512×1024 attendu)")
    t_table, t_pad, t_tuiles = struct.unpack_from("<3I", xi, 0x34)
    debut_tuiles = 0x48 + t_pad
    if L.entete_compression(xi, debut_tuiles)[0] != 1:
        raise L.ErreurFormat("bloc de tuiles de l'atlas : compression LZ10 attendue")
    table = struct.unpack("<%dH" % ((LARGEUR // 8) * (HAUTEUR // 8)), L.decompresser(xi, 0x48))
    tuiles = bytearray(L.decompresser(xi, debut_tuiles))
    res = Resultat("", "", len(xi), 0)
    ecrit: dict[int, bytes] = {}
    for n, x0, y0 in _tuiles_case(table):
        idx = table[n]
        if idx == 0xFFFF or (idx + 1) * 64 > len(tuiles):
            raise L.ErreurFormat("tuile de la case de la vitrine absente de l'atlas")
        partage = sorted({_case_de(m) for m, v in enumerate(table) if v == idx})
        if not set(partage) <= CASES_FACTICES:
            raise L.ErreurFormat(f"tuile {idx} partagée avec des cases d'objets visibles : {partage}")
        px = [icone[(y0 + i // 8) * CASE + x0 + i % 8] for i in range(64)]
        b = L.encoder_tuile_etc(FORMAT, px)
        if idx in ecrit and ecrit[idx] != b:
            raise L.ErreurFormat("une même tuile sert deux fois dans la case avec des contenus différents")
        ecrit[idx] = b
        tuiles[idx * 64:(idx + 1) * 64] = b
        res.tuiles.append(idx)
        if len(partage) > 1:
            res.partagees[idx] = partage
    simples = [tuple(c[:4]) for c in cases_en_plus if len(c) < 5 or not c[4]]
    reaffectees = [tuple(c[:4]) for c in cases_en_plus if len(c) >= 5 and c[4]]
    for colonne, ligne, pixels, permises in simples:
        for n, x0, y0 in _tuiles_case(table, colonne, ligne):
            idx = table[n]
            if idx == 0xFFFF or (idx + 1) * 64 > len(tuiles):
                raise ErreurFormat_case(colonne, ligne, "tuile absente de l'atlas")
            partage = {_case_de(m) for m, v in enumerate(table) if v == idx}
            if not partage <= set(permises) | {ligne * 16 + colonne}:
                raise ErreurFormat_case(colonne, ligne, f"tuile {idx} partagée avec des cases d'objets visibles : "
                                                        f"{sorted(partage)}")
            px = [pixels[(y0 + i // 8) * CASE + x0 + i % 8] for i in range(64)]
            b = L.encoder_tuile_etc(FORMAT, px)
            if idx in ecrit and ecrit[idx] != b:
                raise ErreurFormat_case(colonne, ligne, "tuile déjà écrite avec un autre contenu")
            ecrit[idx] = b
            tuiles[idx * 64:(idx + 1) * 64] = b
    table2 = list(table)
    if reaffectees:
        utilisateurs: dict[int, set] = {}
        for m, v in enumerate(table):
            utilisateurs.setdefault(v, set()).add(_case_de(m))
        cibles = [lig * 16 + col for col, lig, _p, _q in reaffectees]
        prises = {LIGNE * 16 + COLONNE} | {lig * 16 + col for col, lig, _p, _q in simples}
        if len(set(cibles)) != len(cibles) or set(cibles) & prises:
            raise L.ErreurFormat("cases réaffectées en double ou déjà prises par une autre icône")
        for colonne, ligne, pixels, permises in reaffectees:
            libres = [t for t in sorted(utilisateurs) if t != 0xFFFF and t not in ecrit
                      and (t + 1) * 64 <= len(tuiles) and utilisateurs[t] <= set(permises)]
            if len(libres) < 16:
                raise ErreurFormat_case(colonne, ligne, f"{len(libres)} tuiles libres seulement")
            for k, (n, x0, y0) in enumerate(_tuiles_case(table, colonne, ligne)):
                idx = libres[k]
                px = [pixels[(y0 + i // 8) * CASE + x0 + i % 8] for i in range(64)]
                b = L.encoder_tuile_etc(FORMAT, px)
                ecrit[idx] = b
                tuiles[idx * 64:(idx + 1) * 64] = b
                table2[n] = idx
        # place : les tuiles libres restantes (cercles numérotés sans objet, jamais affichés) sont vidées (64 octets
        # nuls : transparentes), sinon l'atlas ne tient plus dans sa taille d'origine (~170 octets de trop sur la ROM
        # européenne avec trois icônes)
        vidables = set().union(*(set(q) for _c, _l, _p, q in reaffectees))
        for t in sorted(utilisateurs):
            if t != 0xFFFF and t not in ecrit and (t + 1) * 64 <= len(tuiles) and utilisateurs[t] <= vidables:
                tuiles[t * 64:(t + 1) * 64] = bytes(64)
                res.videes.append(t)
    # cases réaffectées (objets de voyage, trousseaux) : recherche de correspondances plus profonde (1 024 essais au lieu
    # de 256 : ~1 900 octets de moins sur la ROM européenne, ~5 s de plus par atlas) ; il le faut depuis les images
    # dessinées par l'humain (ap/icones-images : ~90 octets de trop avec 256 essais) ; sans case réaffectée,
    # compression d'avant, octet pour octet
    ctuiles = L.compresser_lz10(bytes(tuiles), ESSAIS_LZ_REAFFECTEES if reaffectees else 256)
    if reaffectees:
        brute = struct.pack("<%dH" % len(table2), *table2)       # même méthode que la table d'origine
        ctable = L.compresser_huffman8(brute) if L.entete_compression(xi, 0x48)[0] == 3 else L.compresser_lz10(brute)
        nouveau = bytearray(xi[:0x48])
        struct.pack_into("<3I", nouveau, 0x34, len(ctable), len(ctable), len(ctuiles))
        nouveau += ctable
        debut_nouveau = len(nouveau)
    else:
        nouveau = bytearray(xi[:debut_tuiles])
        struct.pack_into("<I", nouveau, 0x3C, len(ctuiles))
        debut_nouveau = debut_tuiles
    nouveau += ctuiles
    if len(nouveau) > len(xi):
        raise L.ErreurFormat(f"atlas modifié plus grand que l'original ({len(nouveau)} > {len(xi)} octets)")
    nouveau += b"\0" * (len(xi) - len(nouveau))
    # contrôle : relecture du résultat comme le fera le jeu
    t2 = L.decompresser(bytes(nouveau), debut_nouveau)
    if len(t2) != len(tuiles) or t2 != bytes(tuiles) or bytes(nouveau[:0x34]) != xi[:0x34] or \
            (not reaffectees and bytes(nouveau[0x40:debut_tuiles]) != xi[0x40:debut_tuiles]) or \
            struct.unpack("<%dH" % len(table2), L.decompresser(bytes(nouveau), 0x48)) != tuple(table2):
        raise L.ErreurFormat("contrôle de l'atlas modifié en échec")
    table = tuple(table2)
    case = [(0, 0, 0, 0)] * (CASE * CASE)
    for n, x0, y0 in _tuiles_case(table):
        for i, p in enumerate(L.decoder_tuile_etc(FORMAT, t2[table[n] * 64:(table[n] + 1) * 64])):
            case[(y0 + i // 8) * CASE + x0 + i % 8] = p
    res.pixels_case = case
    for colonne, ligne, _pixels, _permises in simples + reaffectees:
        case = [(0, 0, 0, 0)] * (CASE * CASE)
        for n, x0, y0 in _tuiles_case(table, colonne, ligne):
            for i, p in enumerate(L.decoder_tuile_etc(FORMAT, t2[table[n] * 64:(table[n] + 1) * 64])):
                case[(y0 + i // 8) * CASE + x0 + i % 8] = p
        res.cases_en_plus[(colonne, ligne)] = case
    res.taille_nouvelle = debut_nouveau + len(ctuiles)
    return bytes(nouveau), res


def charger_grande(chemin: Path = GRANDE):
    """64×64 RGBA (grande image de la vitrine)."""
    w, h, pix = L.lire_png(chemin)
    if (w, h) != (TAILLE_GRANDE, TAILLE_GRANDE):
        raise L.ErreurFormat(f"{chemin} : {w}×{h}, {TAILLE_GRANDE}×{TAILLE_GRANDE} attendu")
    return [tuple(p) for p in pix]


def encoder_grande(modele: bytes, pixels: list) -> tuple[bytes, list]:
    """IMGC ETC1A4 64×64 de `pixels`, en-tête repris de `modele` (image 64×64 du même dossier) ; renvoie aussi les
    pixels tels que le jeu les décodera (aperçu)."""
    im = L.Imgc(modele)
    if (im.largeur, im.hauteur, im.format) != (TAILLE_GRANDE, TAILLE_GRANDE, FORMAT):
        raise L.ErreurFormat("image modèle inattendue (IMGC ETC1A4 64×64 attendu)")
    xi = im.encoder(pixels)
    return xi, L.Imgc(xi).pixels


def spans_differents(ancien: bytes, nouveau: bytes, ecart: int = 64) -> list[tuple[int, bytes]]:
    """[(position, octets)] des zones où `nouveau` diffère de `ancien` (même longueur), zones proches fusionnées."""
    if len(ancien) != len(nouveau):
        raise ValueError("longueurs différentes")
    zones: list[list[int]] = []
    i, n = 0, len(ancien)
    while i < n:
        if ancien[i] == nouveau[i]:
            i += 1
            continue
        j = i
        while j < n and ancien[j] != nouveau[j]:
            j += 1
        if zones and i - zones[-1][1] <= ecart:
            zones[-1][1] = j
        else:
            zones.append([i, j])
        i = j
    return [(a, bytes(nouveau[a:b])) for a, b in zones]


def modifications_grande(source: L.SourceRomfs, pixels: list | None = None,
                         sha1_tete: str | None = SHA1_TETE_A,
                         tete_depart: bytes | None = None) -> tuple[list[Modification], list[str]]:
    """Ajout de `item_504.xi` (grande image de la vitrine) à `yw2_a.fa` : remplacements de l'en-tête et des tables
    (taille de l'archive et position des fichiers inchangées). Archive absente, différente de l'original ou sans
    place : aucune modification, avertissement.
    `tete_depart` : tête DÉJÀ modifiée par un autre module de la même archive (`lieu_libre.py`), à laquelle l'image
    est ajoutée ; la tête d'origine reste contrôlée par `sha1_tete`, et les remplacements rendus sont les écarts
    entre la tête d'ORIGINE et la tête finale (un seul patch par archive)."""
    pixels = pixels or charger_grande()
    try:
        f, base, _taille = source.ouvrir("yw2_a.fa")
    except L.ErreurFormat as e:
        return [], [f"grande image : {e}"]
    with f:
        try:
            arc = L.Arc0(f, base)
            f.seek(base)
            tete = f.read(arc.off_donnees)
            if sha1_tete is not None and hashlib.sha1(tete).hexdigest() != sha1_tete:
                raise L.ErreurFormat("tête de l'archive différente de l'original attendu (autre version du jeu ou "
                                     "autre mod)")
            if DOSSIER_ATLAS + MODELE_GRANDE not in arc.entrees:
                raise L.ErreurFormat(f"{DOSSIER_ATLAS}{MODELE_GRANDE} absent")
            xi, decode = encoder_grande(arc.lire(DOSSIER_ATLAS + MODELE_GRANDE), pixels)
            if tete_depart is not None and len(tete_depart) != len(tete):
                raise L.ErreurFormat("tête de départ de longueur inattendue")
            nouvelle = L.arc0_ajouter_fichier(tete if tete_depart is None else tete_depart, DOSSIER_ATLAS,
                                              NOM_GRANDE, xi)
        except L.ErreurFormat as e:
            return [], [f"grande image : yw2_a.fa : {e} ; grande image non installée"]
    res = Resultat("yw2_a.fa", DOSSIER_ATLAS + NOM_GRANDE, len(tete), len(xi))
    res.pixels_case = decode
    mods = [Modification("yw2_a.fa", pos, octets, "yw2_a.fa", res)
            for pos, octets in spans_differents(tete, nouvelle)]
    return mods, []


def modifications(source: L.SourceRomfs, icone: list | None = None, atlas=ATLAS,
                  verifier_sha1: bool = True, grande: bool = True,
                  cases_en_plus=()) -> tuple[list[Modification], list[str]]:
    """Remplacements des atlas présents (un atlas absent ou différent de l'original est ignoré, avertissement), et
    (`grande`) ajout de la grande image de la vitrine à `yw2_a.fa` (`modifications_grande`).
    `cases_en_plus` : autres icônes à poser dans les mêmes atlas (voir `modifier_atlas`) ; si un atlas ne peut pas
    les recevoir, il reçoit l'icône de la vitrine seule (avertissement)."""
    mods, avert = _modifications_atlas(source, icone, atlas, verifier_sha1, cases_en_plus)
    if grande:
        m, a = modifications_grande(source, sha1_tete=SHA1_TETE_A if verifier_sha1 else None)
        mods += m
        avert += a
    return mods, avert


def _modifications_atlas(source: L.SourceRomfs, icone: list | None, atlas,
                         verifier_sha1: bool, cases_en_plus=()) -> tuple[list[Modification], list[str]]:
    icone = icone or charger_icone()
    mods, avert = [], []
    for fa, nom, sha1 in atlas:
        try:
            f, base, _taille = source.ouvrir(fa)
        except L.ErreurFormat as e:
            if fa != "yw2_a.fa":
                continue                     # archive de langue absente : rien à faire
            avert.append(f"icône : {e}")
            continue
        with f:
            try:
                arc = L.Arc0(f, base)
                if nom not in arc.entrees:
                    avert.append(f"icône : {nom} absent de {fa} : non installée pour cette archive")
                    continue
                off, _t = arc.entrees[nom]
                xi = arc.lire(nom)
                try:
                    nouveau, res = modifier_atlas(xi, icone, sha1 if verifier_sha1 else None, cases_en_plus)
                except L.ErreurFormat as e:
                    if not cases_en_plus:
                        raise
                    # repli : les icônes sans réaffectation (enveloppe), puis la vitrine seule
                    simples = tuple(c for c in cases_en_plus if len(c) < 5 or not c[4])
                    try:
                        if not simples or len(simples) == len(cases_en_plus):
                            raise e
                        nouveau, res = modifier_atlas(xi, icone, sha1 if verifier_sha1 else None, simples)
                        avert.append(f"icône : {fa} ({nom}) : {e} ; icônes des objets de voyage non posées dans "
                                     "cet atlas")
                    except L.ErreurFormat:
                        nouveau, res = modifier_atlas(xi, icone, sha1 if verifier_sha1 else None)
                        avert.append(f"icône : {fa} ({nom}) : {e} ; icônes supplémentaires non posées dans cet atlas")
            except L.ErreurFormat as e:
                avert.append(f"icône : {fa} ({nom}) : {e} ; icône non installée pour cette archive")
                continue
        res.fichier, res.atlas = fa, nom
        mods.append(Modification(fa, off, nouveau, fa, res))
    return mods, avert


def apercu(res: Resultat, chemin_png: Path, echelle: int = 8, cote: int = CASE) -> None:
    """La case (ou la grande image) telle que le jeu la décodera, agrandie, sur trois fonds (gris, crème, bleu)."""
    fonds = ((128, 128, 128), (250, 240, 215), (60, 70, 130))
    W = cote * len(fonds)
    out = []
    for y in range(cote * echelle):
        for x in range(W * echelle):
            fx = x // echelle
            r, g, b, a = res.pixels_case[(y // echelle) * cote + fx % cote]
            f = fonds[fx // cote]
            out.append(tuple((c * a + v * (255 - a)) // 255 for c, v in zip((r, g, b), f)) + (255,))
    L.ecrire_png(chemin_png, W * echelle, cote * echelle, out)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="dossier du RomFS extrait, ou ROM déchiffrée (.3ds/.cci/.cxi)")
    ap.add_argument("--sortie", type=Path, help="dossier du titre où écrire romfs_ext/*.bps (icône seule)")
    ap.add_argument("--apercu", type=Path, help="dossier des PNG d'aperçu (hors git)")
    a = ap.parse_args(argv)
    try:
        src = L.SourceRomfs(a.romfs)
        mods, avert = modifications(src)
    except (L.ErreurFormat, OSError) as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    vus = set()
    for m in mods:
        r = m.resultat
        if id(r) in vus:
            continue
        vus.add(id(r))
        if r.atlas.endswith(NOM_GRANDE):
            print(f"{m.fichier} : {r.atlas} ajouté ({r.taille_nouvelle} o, tête de {r.taille_origine} o)")
            if a.apercu:
                a.apercu.mkdir(parents=True, exist_ok=True)
                apercu(r, a.apercu / "grande_image.png", cote=TAILLE_GRANDE, echelle=4)
            continue
        print(f"{m.fichier} : {r.atlas} ; tuiles {r.tuiles} ; atlas {r.taille_origine} -> {r.taille_nouvelle} o "
              f"(tuiles partagées avec des cases factices : {len(r.partagees)})")
        if a.apercu:
            a.apercu.mkdir(parents=True, exist_ok=True)
            apercu(r, a.apercu / f"icone_{m.fichier.replace('.fa', '')}.png")
    if a.sortie:
        par_fichier: dict[str, list] = {}
        for m in mods:
            par_fichier.setdefault(m.fichier, []).append((m.position, m.octets))
        for fa, rempl in par_fichier.items():
            f, base, taille = src.ouvrir(fa)
            with f:
                p = _bps.bps_sur_place(f, base, taille, rempl)
            dest = a.sortie / "romfs_ext" / f"{fa}.bps"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p)
            print(f"  -> {dest} ({len(p)} o)")
    for w in avert:
        print(f"attention : {w}")
    return 0 if mods else 1


if __name__ == "__main__":
    sys.exit(main())
