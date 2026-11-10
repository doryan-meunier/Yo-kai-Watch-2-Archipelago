"""Apparence du personnage principal (Nathan, Katie) : tenue officielle, sépia ou teinte libre (bibliothèque standard).

    python archipelago/installation/apparence.py --romfs <RomFS extrait | ROM déchiffrée> --personnage nathan
           --tenue c001610 [--teinte 270] [--apercu <PNG hors git>] [--controle]

Demande de l'humain du 2026-10-27 (onglet « Apparence » du lanceur, sous-onglet de « Réglages »). Rien du jeu n'est
distribué : la texture choisie est lue dans le RomFS du JOUEUR à l'installation et écrite dans le patch
`romfs_ext/yw2_a.fa.bps` (chaîné avec les autres modules de cette archive : `installer.preparer_romfs`).

Ce que montrent les données [C, relevé sur la ROM européenne, docs/formats/level5.md §12] :
- le héros sur le terrain est le modèle `data/character/c001000/c001000_p00.xc` (Nathan) ou `c002000` (Katie), une
  archive XPCK dont la seule texture est `000.xi` (IMGC ETC1 256×256) ;
- les variantes officielles `c001610` / `c001620` / `c001630` (Nathan : t-shirt bleu, jaune, vert), `c002600` /
  `c002610` / `c002630` (Katie : rouge, bleu, vert) ont la MÊME géométrie (seuls des noms internes et leurs hachages
  diffèrent) et une texture de même disposition ; les sépia `c00x700` à `c00x730` ont une texture de même disposition
  (version désaturée de chaque couleur) mais un `000.prm` différent ;
- les modèles de cinématiques `c001001`, `c001004`, `c001006` (et `c002001`, `c002004`, `c002006`) ont une `000.xi`
  de même disposition SAUF le visage (dessiné à part dans un atlas d'expressions), et `c001500` / `c002500` une
  `000.xi` identique au pixel près à celle du héros.

Ce que fait le module (le héros garde son maillage, ses noms et tout le reste de son archive : seule `000.xi` change,
ce qui évite les noms internes `c001610_output…` d'une autre archive) :
- tenue officielle ou sépia : la `000.xi` de la variante (octets du joueur) remplace celle du héros ;
- teinte libre : masque = pixels où le héros diffère de sa variante BLEUE (le vêtement que les variantes
  recolorent) ; la variante bleue y est tournée dans le cercle des teintes jusqu'à la teinte choisie (saturation et
  luminosité gardées), le reste est le héros ; seules les tuiles 8×8 qui changent sont réencodées en ETC1 (les
  autres gardent leurs octets d'origine) ;
- modèles de cinématiques et `c00x500` : le même changement (cible − héros) n'est appliqué qu'aux pixels du masque
  où leur texture égale celle du héros ; un modèle n'est modifié que si 90 % au moins des pixels du masque y sont
  identiques à ceux du héros (disposition vérifiée chez le joueur), sinon il est laissé tel quel (avertissement).
  Une texture identique au pixel près reçoit la même `000.xi` que le héros. Sépia : seuls le héros et les
  textures identiques changent (les cinématiques ont un visage à part que la variante sépia ne fournit pas : un
  corps sépia sous un visage en couleur serait incohérent).

Le jeu garde le sexe de la partie : le joueur peut habiller les deux personnages, chacun selon son réglage.

Tenues cachées (branche ap/apparence-import, EXPÉRIMENTALES) : modèles du jeu qui ne servent qu'à des scènes (pyjama
`c001030` / `c002030`, maillot `c001080` / `c002080`, yukata `c002040`, veste `c001020` / `c002020`), au MAILLAGE
différent du héros (23 à 27 os au lieu de 24 / 26). L'archive entière est recopiée sur celle du héros, comme le fait
un mod de la communauté (pyjama) ; la cinématique `c00x001` reçoit la version de cinématique de la tenue (`c00x031`)
partie par partie (`_p00` <- `_p00`, `_p10` <- `_p10`, `_p90` <- `_p90` : jamais une animation remplacée par un
modèle). Squelette contrôlé sur la ROM du joueur (`squelette`) : tous les os NOMMÉS du modèle d'origine doivent
exister dans la tenue avec le même parent (les animations du héros visent les os par le CRC-32 de leur nom) ; sinon
le modèle est laissé tel quel. `c00x004` / `c00x006` (scènes de la montre : 6 à 9 os de la montre et des mains
absents des tenues) et `c00x500` restent d'origine.

Mod d'apparence importé (`apparence_import.py`) : le réglage effectif porte alors {"import": {"dossier", "empreinte"}}
(posé par le lanceur, jamais écrit tel quel dans `config.json`) ; ses fichiers sont ajoutés aux remplacements et
l'emportent, chemin par chemin, sur ceux de la tenue (conflit noté).
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import bps as _bps, icone as ico, level5 as L
except ImportError:                     # lancé comme script
    import bps as _bps  # type: ignore[no-redef]
    import icone as ico  # type: ignore[no-redef]
    import level5 as L  # type: ignore[no-redef]

VERSION = 1                              # change l'empreinte : à augmenter si le calcul des textures change
ARCHIVE = "yw2_a.fa"
TEXTURE = "000.xi"
PERSONNAGES = ("nathan", "katie")
HEROS = {"nathan": "c001000", "katie": "c002000"}
# tenues proposées, dans l'ordre de l'interface (clé = modèle d'origine de la texture) ; « origine » et « teinte »
# ne sont pas des modèles
TENUES = {
    "nathan": ("origine", "c001610", "c001620", "c001630", "c001700", "c001710", "c001720", "c001730",
               "c001030", "c001080", "c001020", "teinte"),
    "katie": ("origine", "c002600", "c002610", "c002630", "c002700", "c002710", "c002720", "c002730",
              "c002030", "c002080", "c002040", "c002020", "teinte"),
}
SEPIA = frozenset({"c001700", "c001710", "c001720", "c001730", "c002700", "c002710", "c002720", "c002730"})
# tenues cachées (expérimentales) : modèle de la tenue -> modèle de cinématique de la même tenue (None : aucun dont le
# squelette convienne ; c001021 / c002021, veste de cinématique, n'ont ni `c_c3` ni les os des cheveux de c00x001)
CACHEES = {"c001030": "c001031", "c001080": None, "c001020": None,
           "c002030": "c002031", "c002080": None, "c002040": None, "c002020": None}
CINEMATIQUE = {"nathan": "c001001", "katie": "c002001"}     # seule cinématique qui reçoit la tenue cachée
PARTIES_CINEMATIQUE = ("p00", "p10", "p90")                  # même partie <- même partie
REFERENCE_BLEUE = {"nathan": "c001610", "katie": "c002610"}
# autres modèles du personnage qui partagent la disposition de la texture (cinématiques ; c00x500 : texture identique)
AUTRES_MODELES = {"nathan": ("c001001", "c001004", "c001006", "c001500"),
                  "katie": ("c002001", "c002004", "c002006", "c002500")}
TEINTE_DEFAUT = 270                      # violet : proposé quand on choisit « couleur personnalisée »
SEUIL_MASQUE = 30                        # somme |ΔR|+|ΔG|+|ΔB| au-delà de laquelle un pixel appartient au vêtement
SEUIL_EGAL = 24                          # en deçà, deux pixels décodés (bruit de l'ETC1) sont tenus pour égaux
ECART_TEINTE = 50 / 360                  # écart de teinte (sur le cercle) à la teinte moyenne du vêtement
PART_DISPOSITION = 0.90                 # part du masque identique au héros exigée pour modifier un autre modèle


class ErreurApparence(L.ErreurFormat):
    """Le réglage ne peut pas être appliqué à ce RomFS (fichier absent, format inattendu)."""


def chemin_xc(modele: str, partie: str = "p00") -> str:
    return "data/" + "character/" + f"{modele}/{modele}_{partie}.xc"


def squelette(xc: L.Xpck | bytes) -> dict[str, str]:
    """Os NOMMÉS d'un modèle XPCK : {nom: parent} (racine `<modèle>_output` notée "<racine>"). Un `.mbn` commence par
    le CRC-32 du nom de l'os puis celui de son parent ; les noms sont dans la table de chaînes de `RES.bin`
    (compressé). Les nœuds sans nom connu sous la racine (un par maillage `.prm`) sont écartés ; un os sans nom
    connu ailleurs est noté par son hachage ("#xxxxxxxx"). Modèle sans os : {}."""
    import re
    import zlib
    x = xc if isinstance(xc, L.Xpck) else L.Xpck(xc)
    mbn = [n for n in x.par_nom if n.endswith(".mbn")]
    if not mbn:
        return {}
    noms: dict[int, str] = {}
    if "RES.bin" in x.par_nom:
        try:
            r = L.decompresser(x.lire("RES.bin"), 0)
        except (L.ErreurFormat, IndexError, ValueError):
            r = b""
        for c in set(re.findall(rb"[\x21-\x7e]{2,64}", r)):
            noms[zlib.crc32(c)] = c.decode("ascii")
    out = {}
    for n in sorted(mbn):
        d = x.lire(n)
        if len(d) < 8:
            continue
        h, p = struct.unpack_from("<II", d, 0)
        nom = noms.get(h)
        if p == 0 or (nom or "").endswith("_output"):
            continue                                       # racine
        parent = noms.get(p)
        if nom is None and (parent or "").endswith("_output"):
            continue                                       # nœud d'un maillage
        out[nom or "#%08x" % h] = "<racine>" if (parent or "").endswith("_output") else (parent or "#%08x" % p)
    return out


def os_perdus(origine: dict[str, str], nouveau: dict[str, str]) -> list[str]:
    """Os nommés du modèle d'origine absents du nouveau ou rattachés à un autre parent (triés)."""
    return sorted(k for k, v in origine.items() if nouveau.get(k) != v)


# ------------------------------------------------------------------------------------------------ réglage
def normaliser(brut) -> dict:
    """Réglage lu dans `config.json` (champ `apparence`) -> {personnage: {"tenue": clé, "teinte": 0..359}}, sans
    les personnages laissés d'origine ; toute valeur inconnue est ignorée (personnage d'origine)."""
    out = {}
    if not isinstance(brut, dict):
        return out
    for p in PERSONNAGES:
        r = brut.get(p)
        if not isinstance(r, dict):
            continue
        tenue = r.get("tenue")
        if tenue not in TENUES[p] or tenue == "origine":
            continue
        if tenue == "teinte":
            t = r.get("teinte", TEINTE_DEFAUT)
            if isinstance(t, bool) or not isinstance(t, (int, float)):
                continue
            out[p] = {"tenue": "teinte", "teinte": int(round(t)) % 360}
        else:
            out[p] = {"tenue": tenue}
    imp = brut.get("import")                # mod importé (posé par le lanceur : `apparence_import.reglage`)
    if isinstance(imp, dict) and isinstance(imp.get("empreinte"), str) and imp["empreinte"] \
            and isinstance(imp.get("dossier"), str) and imp["dossier"]:
        out["import"] = {"empreinte": imp["empreinte"], "dossier": imp["dossier"]}
    return out


def empreinte(brut) -> str:
    """Empreinte du réglage effectif : "" sans changement (installation identique à celle d'avant le module). Le
    mod importé y entre par son empreinte (contenu), pas par son dossier ; sans lui, empreinte d'avant l'import."""
    n = normaliser(brut)
    if not n:
        return ""
    if "import" in n:
        n = dict(n, **{"import": n["import"]["empreinte"]})
    return hashlib.sha1(json.dumps({"v": VERSION, "r": n}, sort_keys=True).encode()).hexdigest()[:16]


def empreinte_personnage(personnage: str, reglage) -> str:
    """Empreinte d'un seul personnage (nom de l'aperçu en cache)."""
    n = normaliser({personnage: reglage}).get(personnage, {"tenue": "origine"})
    return hashlib.sha1(json.dumps({"v": VERSION, "p": personnage, "r": n}, sort_keys=True).encode()).hexdigest()[:16]


# ------------------------------------------------------------------------------------------------ pixels
def ecart(p, q) -> int:
    return abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2])


def masque(heros: list, reference: list, seuil: int = SEUIL_MASQUE) -> list[bool]:
    """Pixels du vêtement : ceux où le héros et sa variante officielle diffèrent."""
    return [ecart(p, q) > seuil for p, q in zip(heros, reference)]


def teinte_moyenne(pixels: list, m: list[bool]) -> float:
    """Teinte (0..1) du vêtement : moyenne sur le cercle des pixels saturés du masque (pondérée par la saturation),
    refaite une fois sur les seuls pixels à moins de ECART_TEINTE de la première (les bords d'une autre couleur ne
    la tirent pas)."""
    import math
    teintes = []
    for p, dans in zip(pixels, m):
        if not dans:
            continue
        h, s, _v = colorsys.rgb_to_hsv(p[0] / 255, p[1] / 255, p[2] / 255)
        if s >= 0.25:
            teintes.append((h, s))

    def moyenne(liste):
        x = sum(s * math.cos(2 * math.pi * h) for h, s in liste)
        y = sum(s * math.sin(2 * math.pi * h) for h, s in liste)
        return None if x == 0 and y == 0 else (math.atan2(y, x) / (2 * math.pi)) % 1.0
    m1 = moyenne(teintes)
    if m1 is None:
        return 0.0

    def ecart_cercle(h):
        d = abs(h - m1) % 1.0
        return min(d, 1.0 - d)
    m2 = moyenne([(h, s) for h, s in teintes if ecart_cercle(h) <= ECART_TEINTE])
    return m1 if m2 is None else m2


def teinter(heros: list, reference: list, m: list[bool], teinte_deg: int) -> list:
    """Texture du héros dont le vêtement (masque) est la variante `reference` tournée jusqu'à `teinte_deg`.

    Dans le masque : pixel de la variante proche de la teinte du vêtement (± ECART_TEINTE, saturation >= 0,15) =
    tourné ; pixel peu saturé de la variante (blancs, gris) = gardé tel quel ; autre pixel saturé de la variante
    (bords rouges ou violets laissés par l'ETC1, détails d'une autre couleur) = pixel du héros (le tourner le ferait
    passer à la teinte du vêtement : liseré visible au bord des manches)."""
    moyenne = teinte_moyenne(reference, m)
    dh = teinte_deg / 360.0 - moyenne
    out = []
    for h, r, dans in zip(heros, reference, m):
        if not dans:
            out.append(h)
            continue
        hh, s, v = colorsys.rgb_to_hsv(r[0] / 255, r[1] / 255, r[2] / 255)
        if s < 0.15:
            out.append(r)
            continue
        d = abs(hh - moyenne) % 1.0
        if min(d, 1.0 - d) > ECART_TEINTE:
            out.append(h)
            continue
        r2, g2, b2 = colorsys.hsv_to_rgb((hh + dh) % 1.0, s, v)
        out.append((round(r2 * 255), round(g2 * 255), round(b2 * 255), r[3]))
    return out


def _borne(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def reporter(autre: list, heros: list, cible: list, m: list[bool], seuil: int = SEUIL_EGAL) -> tuple[list, float]:
    """Change (cible − héros) reporté sur une autre texture de même disposition, aux seuls pixels du masque où elle
    égale le héros. Renvoie (pixels, part du masque où elle égale le héros)."""
    out, egaux, n = [], 0, 0
    for a, h, c, dans in zip(autre, heros, cible, m):
        if not dans:
            out.append(a)
            continue
        n += 1
        if ecart(a, h) > seuil:
            out.append(a)
            continue
        egaux += 1
        out.append((_borne(a[0] + c[0] - h[0]), _borne(a[1] + c[1] - h[1]), _borne(a[2] + c[2] - h[2]), a[3]))
    return out, (egaux / n if n else 0.0)


def encoder_partiel(xi: bytes, pixels: list) -> bytes:
    """Réencode une IMGC dont seules certaines tuiles 8×8 changent : une tuile dont les pixels sont ceux que donne le
    décodage d'origine garde ses octets d'origine (ETC1 : le réencodage les changerait sans raison et coûte ~12 ms
    par tuile) ; les autres sont encodées comme `Imgc.encoder` (tuiles identiques fusionnées, table et tuiles LZ10)."""
    im = L.Imgc(xi)
    w, h, ot = im.largeur, im.hauteur, im.octets_tuile
    tuiles0 = L.decompresser(xi, 0x48 + im.t_table_pad)
    tl, th = (w + 7) // 8, (h + 7) // 8
    etc = im.format in L.FORMATS_ETC

    def px_tuile(pix, n):
        x0, y0 = (n % tl) * 8, (n // tl) * 8
        if etc:
            return [pix[(y0 + i // 8) * w + x0 + i % 8] if x0 + i % 8 < w and y0 + i // 8 < h else (0, 0, 0, 0)
                    for i in range(64)]
        return [pix[(y0 + dy) * w + x0 + dx] if x0 + dx < w and y0 + dy < h else (0, 0, 0, 0)
                for dx, dy in L.MORTON]
    uniques: dict[bytes, int] = {}
    donnees = bytearray()
    table = []
    for n in range(tl * th):
        px = px_tuile(pixels, n)
        if all(p == (0, 0, 0, 0) for p in px):
            table.append(0xFFFF)
            continue
        idx = im.table[n]
        if idx != 0xFFFF and px == px_tuile(im.pixels, n):
            b = tuiles0[idx * ot:(idx + 1) * ot]
        else:
            b = L.encoder_tuile_etc(im.format, px) if etc else L._encoder_tuile(im.format, px)
        if b not in uniques:
            uniques[b] = len(uniques)
            donnees += b
        table.append(uniques[b])
    if len(uniques) >= 0xFFFF:
        raise ErreurApparence("IMGC : trop de tuiles distinctes")
    ctable = L.compresser_lz10(struct.pack("<%dH" % len(table), *table))
    cdonnees = L.compresser_lz10(bytes(donnees))
    e = bytearray(im.entete)
    struct.pack_into("<3I", e, 0x34, len(ctable), len(ctable), len(cdonnees))
    return bytes(e) + ctable + cdonnees


# ------------------------------------------------------------------------------------------------ textures
@dataclass
class Resultat:
    """Ce que le module change pour un personnage."""
    personnage: str
    tenue: str
    teinte: int | None = None
    fichiers: dict = field(default_factory=dict)      # chemin du .xc -> nouveau contenu
    pixels_heros: list | None = field(default_factory=list)  # texture du héros telle que le jeu la décodera
                                                      # (None : modèle du héros remplacé par le mod importé)
    modeles: list = field(default_factory=list)       # autres modèles modifiés
    ignores: list = field(default_factory=list)       # (modèle, raison) laissés tels quels
    messages: list = field(default_factory=list)      # avertissements de l'installation (conflits, fichiers absents)


class Lecteur:
    """Accès aux .xc d'une archive ARC0 du RomFS (ouverte une fois)."""

    def __init__(self, source: L.SourceRomfs):
        self.source = source
        self.f, self.base, self.taille = source.ouvrir(ARCHIVE)
        self.arc = L.Arc0(self.f, self.base)
        self._xc: dict[str, L.Xpck] = {}

    def fermer(self) -> None:
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *_e):
        self.fermer()

    def existe(self, modele: str, partie: str = "p00") -> bool:
        return chemin_xc(modele, partie) in self.arc.entrees

    def brut(self, modele: str, partie: str = "p00") -> bytes:
        ch = chemin_xc(modele, partie)
        if ch not in self.arc.entrees:
            raise ErreurApparence(f"{ch} absent de {ARCHIVE}")
        return self.arc.lire(ch)

    def xc(self, modele: str) -> L.Xpck:
        if modele not in self._xc:
            ch = chemin_xc(modele)
            if ch not in self.arc.entrees:
                raise ErreurApparence(f"{ch} absent de {ARCHIVE}")
            x = L.Xpck(self.arc.lire(ch))
            if TEXTURE not in x.par_nom:
                raise ErreurApparence(f"{ch} : pas de {TEXTURE}")
            self._xc[modele] = x
        return self._xc[modele]

    def texture(self, modele: str) -> tuple[bytes, L.Imgc]:
        d = self.xc(modele).lire(TEXTURE)
        return d, L.Imgc(d)


def _cible(lec: Lecteur, personnage: str, reglage: dict) -> tuple[bytes | None, list, list, list]:
    """(nouvelle 000.xi du héros ou None s'il faut l'encoder, pixels cibles, pixels du héros, masque)."""
    xi_h, im_h = lec.texture(HEROS[personnage])
    tenue = reglage["tenue"]
    ref = tenue if tenue != "teinte" else REFERENCE_BLEUE[personnage]
    xi_r, im_r = lec.texture(ref)
    if (im_r.largeur, im_r.hauteur, im_r.format) != (im_h.largeur, im_h.hauteur, im_h.format):
        raise ErreurApparence(f"{ref} : texture de dimensions ou de format différents de {HEROS[personnage]}")
    if tenue == "teinte":
        m = masque(im_h.pixels, im_r.pixels)
        return None, teinter(im_h.pixels, im_r.pixels, m, reglage["teinte"]), im_h.pixels, m
    return xi_r, im_r.pixels, im_h.pixels, masque(im_h.pixels, im_r.pixels)


def pixels_apercu(lec: Lecteur, personnage: str, reglage) -> tuple[int, int, list]:
    """Aperçu (colonne gauche de la texture : visage au-dessus du vêtement) sans réencodage : (largeur, hauteur,
    pixels RGBA). Réglage d'origine : texture du héros."""
    n = normaliser({personnage: reglage}).get(personnage)
    if n is None or n["tenue"] in CACHEES:
        _x, im = lec.texture(HEROS[personnage] if n is None else n["tenue"])
        pix, w = im.pixels, im.largeur
    else:
        _x, pix, heros, _m = _cible(lec, personnage, n)
        w = lec.texture(HEROS[personnage])[1].largeur
    h = len(pix) // w
    x1 = w // 2                              # moitié gauche (256×256 : 128×256, visage au-dessus du vêtement)
    out = []
    for y in range(h):
        out += [(p[0], p[1], p[2], 255) for p in pix[y * w:y * w + x1]]
    return x1, h, out


def tenue_cachee(lec: Lecteur, personnage: str, tenue: str) -> Resultat:
    """Tenue cachée : archives entières de la tenue recopiées sur le héros et sur sa cinématique `c00x001` (partie
    par partie), après contrôle du squelette (`os_perdus` vide) et des textures (pas plus grandes que celles du
    modèle remplacé). Héros refusé : ErreurApparence ; cinématique refusée : laissée telle quelle (`ignores`)."""
    heros = HEROS[personnage]
    res = Resultat(personnage, tenue)
    x_h, x_t = lec.xc(heros), lec.xc(tenue)
    perdus = os_perdus(squelette(x_h), squelette(x_t))
    if perdus:
        raise ErreurApparence(f"{tenue} : os du héros absents ou rattachés autrement ({', '.join(perdus)})")
    im_h, im_t = L.Imgc(x_h.lire(TEXTURE)), L.Imgc(x_t.lire(TEXTURE))
    if im_t.largeur * im_t.hauteur > im_h.largeur * im_h.hauteur:
        raise ErreurApparence(f"{tenue} : texture plus grande que celle du héros")
    res.fichiers[chemin_xc(heros)] = lec.brut(tenue)
    res.pixels_heros = im_t.pixels
    cine, source = CINEMATIQUE[personnage], CACHEES[tenue]
    for autre in AUTRES_MODELES[personnage]:
        if autre != cine or source is None:
            res.ignores.append((autre, "tenue cachée : modèle gardé d'origine"))
            continue
        if not (lec.existe(cine) and lec.existe(source)):
            res.ignores.append((autre, "absent"))
            continue
        perdus = os_perdus(squelette(lec.xc(cine)), squelette(lec.xc(source)))
        if perdus:
            res.ignores.append((autre, "os absents dans %s (%s)" % (source, ", ".join(perdus))))
            continue
        for partie in PARTIES_CINEMATIQUE:
            if lec.existe(cine, partie) and lec.existe(source, partie):
                res.fichiers[chemin_xc(cine, partie)] = lec.brut(source, partie)
        res.modeles.append(cine)
    return res


def textures(lec: Lecteur, personnage: str, reglage: dict) -> Resultat:
    """Nouveaux .xc d'un personnage pour un réglage NORMALISÉ (`normaliser`)."""
    heros = HEROS[personnage]
    if reglage["tenue"] in CACHEES:
        return tenue_cachee(lec, personnage, reglage["tenue"])
    res = Resultat(personnage, reglage["tenue"], reglage.get("teinte"))
    xi_h, im_h = lec.texture(heros)
    xi_n, cible, pix_h, m = _cible(lec, personnage, reglage)
    if xi_n is None:
        xi_n = encoder_partiel(xi_h, cible)
    res.pixels_heros = L.Imgc(xi_n).pixels
    res.fichiers[chemin_xc(heros)] = lec.xc(heros).reconstruire({TEXTURE: xi_n})
    for autre in AUTRES_MODELES[personnage]:
        if not lec.existe(autre):
            res.ignores.append((autre, "absent"))
            continue
        x = lec.xc(autre)
        xi_a, im_a = lec.texture(autre)
        if (im_a.largeur, im_a.hauteur, im_a.format) != (im_h.largeur, im_h.hauteur, im_h.format):
            res.ignores.append((autre, "texture de dimensions différentes"))
            continue
        if im_a.pixels == pix_h:                       # même texture : même résultat que le héros
            res.fichiers[chemin_xc(autre)] = x.reconstruire({TEXTURE: xi_n})
            res.modeles.append(autre)
            continue
        if reglage["tenue"] in SEPIA:
            res.ignores.append((autre, "sépia : visage de cinématique à part"))
            continue
        nouv, part = reporter(im_a.pixels, pix_h, cible, m)
        if part < PART_DISPOSITION:
            res.ignores.append((autre, "disposition différente (%d %% du vêtement identique)" % round(100 * part)))
            continue
        res.fichiers[chemin_xc(autre)] = x.reconstruire({TEXTURE: encoder_partiel(xi_a, nouv)})
        res.modeles.append(autre)
    return res


def fichiers_a(source: L.SourceRomfs, brut) -> tuple[dict[str, bytes], list[Resultat]]:
    """{chemin: nouveau .xc} à remplacer dans `yw2_a.fa` pour le réglage `brut` (`config.json`), et le détail.
    ErreurApparence / ErreurFormat si le RomFS ne s'y prête pas."""
    n = normaliser(brut)
    rempl: dict[str, bytes] = {}
    resultats = []
    if not n:
        return rempl, resultats
    with Lecteur(source) as lec:
        for p in PERSONNAGES:
            if p in n:
                r = textures(lec, p, n[p])
                rempl.update(r.fichiers)
                resultats.append(r)
        if "import" in n:
            resultats.append(importer(lec, n["import"], rempl, resultats))
    return rempl, resultats


def importer(lec: Lecteur, imp: dict, rempl: dict[str, bytes], resultats: list[Resultat]) -> Resultat:
    """Ajoute à `rempl` les fichiers du mod importé (`apparence_import.charger` : contenu contrôlé par SHA-1). Un
    chemin absent de l'archive du joueur est laissé de côté ; un chemin déjà changé par la tenue est pris au mod
    importé (conflit : la tenue perd ce fichier, noté dans `messages`)."""
    try:
        from . import apparence_import as AI
    except ImportError:                     # lancé comme script
        import apparence_import as AI  # type: ignore[no-redef]
    res = Resultat("import", "import")
    for ch, contenu in AI.charger(Path(imp["dossier"]), imp["empreinte"]).items():
        if ch not in lec.arc.entrees:
            res.messages.append(f"mod importé : {ch} absent de votre {ARCHIVE}, laissé de côté")
            continue
        if ch in rempl:
            for r in resultats:
                if ch in r.fichiers:
                    del r.fichiers[ch]
                    r.ignores.append((ch.rsplit("/", 1)[-1], "remplacé par le mod importé"))
                    if ch == chemin_xc(HEROS.get(r.personnage, "")):
                        r.pixels_heros = None
                    res.messages.append(f"apparence : {ch} vient du mod importé (la tenue « {r.tenue} » de "
                                        f"{r.personnage} n'y est pas appliquée)")
        rempl[ch] = contenu
        res.fichiers[ch] = contenu
        res.modeles.append(ch)
    return res


def messages(resultats: list[Resultat]) -> list[str]:
    """Avertissements de l'installation portés par les résultats (conflits avec le mod importé…)."""
    return [m for r in resultats for m in r.messages]


# ------------------------------------------------------------------------------------------------ chaînage
def separer(mods: list, taille: int, longueur_tete: int):
    """Modifications d'une archive (positions absolues) -> (dans la tête [(pos, octets)], dans les données
    existantes [(pos, octets)], octets ajoutés à la fin). ErreurFormat si une modification est à cheval sur la fin
    de la tête ou si les ajouts de fin ne se suivent pas."""
    tete, dedans, fin = [], [], []
    for m in mods:
        p, o = m.position, m.octets
        if p >= taille:
            fin.append((p, o))
        elif p + len(o) <= longueur_tete:
            tete.append((p, o))
        elif p >= longueur_tete:
            dedans.append((p, o))
        else:
            raise ErreurApparence("modification à cheval sur la fin de la tête de l'archive")
    ajout, pos = b"", taille
    for p, o in sorted(fin):
        if p != pos:
            raise ErreurApparence("ajouts de fin d'archive non contigus")
        ajout += o
        pos += len(o)
    return tete, dedans, ajout


def chainer(source: L.SourceRomfs, precedentes: list, remplacements: dict[str, bytes], grande_icone: bool,
            sha1_tete: str | None = ico.SHA1_TETE_A) -> tuple[list, list[str], bool, bool]:
    """Chaîne les remplacements de l'apparence APRÈS les modules précédents de `yw2_a.fa` (`precedentes` : leurs
    modifications, calculées sans la grande image de la vitrine) puis, si `grande_icone`, la grande image (qui passe
    par `arc0_ajouter_fichier` et doit donc venir en dernier : elle abaisse le début des données).

    Tête de départ = tête d'origine + modifications précédentes de la tête ; les ajouts de fin précédents sont gardés
    devant les nôtres (`arc0_modifier` reçoit la taille de l'archive déjà agrandie). Renvoie (TOUTES les
    modifications de l'archive : écarts tête d'origine -> tête finale, modifications précédentes hors tête, un seul
    ajout de fin ; avertissements ; apparence posée ; grande image posée). Si l'apparence échoue, le reste est rendu
    comme sans elle (avertissement)."""
    f, base, taille = source.ouvrir(ARCHIVE)
    with f:
        arc = L.Arc0(f, base)
        f.seek(base)
        tete0 = f.read(arc.off_donnees)
    avert: list[str] = []
    tp, dedans, ajout = separer(precedentes, taille, len(tete0))
    tete = bytearray(tete0)
    for p, o in tp:
        tete[p:p + len(o)] = o
    tete = bytes(tete)
    if struct.unpack_from("<I", tete, 0x14)[0] != len(tete):
        raise ErreurApparence("tête déjà réorganisée par un ajout de fichier : l'apparence doit passer avant")
    pose = False
    suffixe = b""
    nouvelle = tete
    if remplacements:
        try:
            nouvelle, suffixe = L.arc0_modifier(tete, taille + len(ajout), remplacements, {})
            pose = True
        except L.ErreurFormat as e:
            avert.append(f"apparence : {ARCHIVE} : {e} ; apparence non installée")
    grande = False
    mods = []
    if grande_icone:
        m, a = ico.modifications_grande(source, sha1_tete=sha1_tete, tete_depart=nouvelle)
        if m:
            mods += m                             # écarts entre la tête d'origine et la tête finale
            grande = True
        else:
            avert += a
    if not grande:
        mods += [ico.Modification(ARCHIVE, p, o, ARCHIVE, None) for p, o in ico.spans_differents(tete0, nouvelle)]
    mods += [ico.Modification(ARCHIVE, p, o, ARCHIVE, None) for p, o in dedans]
    if ajout or suffixe:
        mods.append(ico.Modification(ARCHIVE, taille, ajout + suffixe, ARCHIVE, None))
    return mods, avert, pose, grande


# ------------------------------------------------------------------------------------------------ contrôle
class ArchivePatchee:
    """Lecture d'une archive patchée par `bps_sur_place` SANS l'écrire en entier : les octets modifiés viennent du
    patch (TargetRead), le reste de l'archive d'origine."""

    def __init__(self, source: L.SourceRomfs, patch: bytes, fa: str = ARCHIVE):
        self.f, self.base, self.taille = source.ouvrir(fa)
        self.litt = _bps.bps_litteraux(patch)
        fin = max([self.taille] + [p + len(o) for p, o in self.litt])
        self.longueur = fin
        self.tete = self.lire(0, 0x48)
        off = struct.unpack_from("<I", self.tete, 0x14)[0]
        dos, fic = struct.unpack_from("<I", self.tete, 4)[0], struct.unpack_from("<I", self.tete, 0x0C)[0]
        tete = self.lire(0, max(off, struct.unpack_from("<I", self.tete, 0x10)[0]))
        self.tables = (L.decompresser(tete, dos), L.decompresser(tete, fic), off,
                       struct.unpack_from("<H", self.tete, 0x18)[0])

    def fermer(self):
        self.f.close()

    def lire(self, pos: int, n: int) -> bytes:
        out = bytearray()
        if pos < self.taille:
            self.f.seek(self.base + pos)
            out += self.f.read(min(n, self.taille - pos))
        out += b"\0" * (n - len(out))
        for p, o in self.litt:
            a, b = max(p, pos), min(p + len(o), pos + n)
            if a < b:
                out[a - pos:b - pos] = o[a - p:b - p]
        return bytes(out)

    def fichier(self, chemin: str) -> bytes:
        r = L.arc0_recherche_jeu(self.tables, chemin)
        if r is None:
            raise ErreurApparence(f"contrôle : {chemin} introuvable dans l'archive patchée")
        return self.lire(*r)


def verifier(source: L.SourceRomfs, patch: bytes, resultats: list[Resultat]) -> list[str]:
    """Relit le patch de `yw2_a.fa` comme le jeu (recherche par crc) : chaque .xc changé a le contenu attendu et la
    texture du héros se décode comme prévu. Renvoie les lignes du contrôle ; ErreurApparence au premier écart."""
    a = ArchivePatchee(source, patch)
    lignes = []
    try:
        for r in resultats:
            for ch, contenu in r.fichiers.items():
                if a.fichier(ch) != contenu:
                    raise ErreurApparence(f"contrôle : {ch} différent de l'attendu")
            if r.personnage in HEROS and r.pixels_heros is not None:
                pix = L.Imgc(L.Xpck(a.fichier(chemin_xc(HEROS[r.personnage]))).lire(TEXTURE)).pixels
                if pix != r.pixels_heros:
                    raise ErreurApparence(f"contrôle : texture de {HEROS[r.personnage]}")
            lignes.append(f"{r.personnage} : {r.tenue}" + (f" ({r.teinte}°)" if r.teinte is not None else "") +
                          f", {len(r.fichiers)} modèle(s) relus" +
                          (f", laissés : {', '.join(m for m, _r in r.ignores)}" if r.ignores else ""))
    finally:
        a.fermer()
    return lignes


# ------------------------------------------------------------------------------------------------ outil
def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="dossier du RomFS extrait, ou ROM déchiffrée (.3ds/.cci/.cxi)")
    ap.add_argument("--personnage", choices=PERSONNAGES, default="nathan")
    ap.add_argument("--tenue", default="teinte", help="origine, teinte ou modèle (c001610…)")
    ap.add_argument("--teinte", type=int, default=TEINTE_DEFAUT)
    ap.add_argument("--apercu", type=Path, help="PNG de l'aperçu (hors git)")
    ap.add_argument("--controle", action="store_true", help="calcule les textures et relit le patch (sans écrire)")
    a = ap.parse_args(argv)
    src = L.SourceRomfs(a.romfs)
    reglage = {"tenue": a.tenue, "teinte": a.teinte}
    if a.apercu:
        with Lecteur(src) as lec:
            w, h, pix = pixels_apercu(lec, a.personnage, reglage)
        L.ecrire_png(a.apercu, w, h, pix)
        print(f"aperçu : {a.apercu}")
    if a.controle:
        brut = {a.personnage: reglage}
        rempl, res = fichiers_a(src, brut)
        mods, avert, _pose, _g = chainer(src, [], rempl, grande_icone=False, sha1_tete=None)
        f, base, taille = src.ouvrir(ARCHIVE)
        with f:
            tete, dedans, ajout = separer(mods, taille, L.Arc0(f, base).off_donnees)
            p = _bps.bps_sur_place(f, base, taille, tete + dedans, ajout)
        for ligne in avert + verifier(src, p, res):
            print(ligne)
        print(f"patch : {len(p)} octets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
