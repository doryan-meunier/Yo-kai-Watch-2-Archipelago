"""Libellé « Archipelago » sur le bouton détourné de l'écran titre (bibliothèque standard seulement).

    python archipelago/installation/libelle.py --romfs <RomFS extrait | ROM déchiffrée> --sortie <dossier>
           [--langues fr,engb] [--texte Archipelago] [--bouton btn_04] [--apercu build/libelle_apercu]

Le libellé des boutons du menu titre est une IMAGE de l'archive de menu localisée
`data/menu/title_d00_c_<LG>.xa` (XPCK) de `yw2_lg_<LG>.fa` (ARC0) : texture `000.xi` (IMGC RGBA8 512×256),
quadrilatères des maillages `NNN.pbi`/`000.pvb`, noms des maillages dans `RES.bin` (`btn_04_off`…).
Pour chaque langue, ce module, À L'INSTALLATION et à partir du RomFS du joueur :

1. relit l'archive de menu, trouve les quadrilatères du libellé du bouton (`<bouton>_off/_on/_push`) ;
2. efface le libellé d'origine dans la texture et y dessine le texte avec la police du jeu
   (`fnt/ft_nrm.xf` de `yw2_a.fa`), épaissie d'un pixel, gris foncé avec contour blanc translucide
   (style relevé sur les libellés d'origine) ;
3. ré-encode la texture, reconstruit l'archive de menu (même taille ou plus petite, complétée par des
   zéros jusqu'à la taille d'origine) ;
4. produit un patch BPS de `yw2_lg_<LG>.fa` qui ne remplace que ces octets, à déposer dans
   `<mods>/00040000001B2900/romfs_ext/yw2_lg_<LG>.fa.bps` : LayeredFS d'Azahar l'applique au fichier du
   RomFS de base au lancement (aucune copie de l'archive de 134 Mo, aucun fichier dans `romfs/`).

Aucun pixel ni octet du jeu n'est versionné : tout vient de la ROM / du RomFS du joueur. Détails et
statut (certain / supposé) : `docs/formats/level5.md` §8-§10, `docs/outils.md` (« Libellé du bouton »).
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import bps as _bps, level5 as L
except ImportError:                     # lancé comme script
    import bps as _bps  # type: ignore[no-redef]
    import level5 as L  # type: ignore[no-redef]

LANGUES = ("fr", "engb", "de", "es", "it", "nl", "ru")
TEXTE_DEFAUT = "Archipelago"
BOUTON_DEFAUT = "btn_04"                # « Transfert de données EF/FB » (btn_03 = « Liaison YO-KAI WATCH 2 »)
POLICE = "fnt/ft_nrm.xf"
ETATS = ("_off", "_on", "_push")

# Style relevé sur les libellés d'origine (btn_03 / btn_04, FR et EN) [C : couleurs dominantes mesurées]
COULEUR_TEXTE = (44, 44, 44)
COULEUR_CONTOUR = (255, 255, 255)
ALPHA_CONTOUR = 153 / 255
RAYON_CONTOUR = 2.0
EPAISSISSEMENT = 1                      # pixels ajoutés à droite de chaque trait (faux gras)


def chemin_xa(langue: str) -> str:
    return f"data/menu/title_d00_c_{langue}.xa"


def nom_fa(langue: str) -> str:
    return f"yw2_lg_{langue}.fa"


# ------------------------------------------------------------------------------------------------
# Rendu du texte (couverture en flottants, puis composition texte sur contour)
# ------------------------------------------------------------------------------------------------
def rendre_texte(police: L.Police, texte: str):
    """-> (largeur, hauteur, pixels RGBA, décalage vertical de l'encre) sur fond transparent."""
    manquants = [c for c in texte if ord(c) not in police.glyphes]
    if manquants:
        raise L.ErreurFormat("caractères absents de la police du jeu : %r" % "".join(manquants))
    marge = int(RAYON_CONTOUR + 1.5)
    x = marge
    glyphes = []
    for c in texte:
        av, ox, oy, gw, gh, cov = police.couverture(ord(c))
        glyphes.append((x + ox, oy, gw, gh, cov))
        x += av + EPAISSISSEMENT
    W = x + marge
    H = police.hauteur + 2 * marge
    g = [0.0] * (W * H)
    for gx, oy, gw, gh, cov in glyphes:
        for yy in range(gh):
            for xx in range(gw):
                v = cov[yy * gw + xx]
                if v <= 0:
                    continue
                for e in range(EPAISSISSEMENT + 1):
                    k = (marge + oy + yy) * W + gx + xx + e
                    if v > g[k]:
                        g[k] = v
    r = RAYON_CONTOUR
    ri = int(r + 1)
    noyau = [(dx, dy, max(0.0, min(1.0, r + 0.5 - (dx * dx + dy * dy) ** 0.5)))
             for dy in range(-ri, ri + 1) for dx in range(-ri, ri + 1)]
    noyau = [n for n in noyau if n[2] > 0]
    pix = []
    for y in range(H):
        for x in range(W):
            gv = g[y * W + x]
            o = 0.0
            for dx, dy, p in noyau:
                X, Y = x + dx, y + dy
                if 0 <= X < W and 0 <= Y < H:
                    v = g[Y * W + X] * p
                    if v > o:
                        o = v
            ac = ALPHA_CONTOUR * o * (1 - gv)
            a = gv + ac
            if a <= 0:
                pix.append((0, 0, 0, 0))
                continue
            col = tuple(int(round((f * gv + w * ac) / a)) for f, w in zip(COULEUR_TEXTE, COULEUR_CONTOUR))
            pix.append(col + (int(round(a * 255)),))
    lignes = [y for y in range(H) if any(pix[y * W + x][3] for x in range(W))]
    colonnes = [x for x in range(W) if any(pix[y * W + x][3] for y in range(H))]
    y0, y1, x0, x1 = lignes[0], lignes[-1] + 1, colonnes[0], colonnes[-1] + 1
    rog = [pix[y * W + x] for y in range(y0, y1) for x in range(x0, x1)]
    return x1 - x0, y1 - y0, rog


# ------------------------------------------------------------------------------------------------
# Quadrilatères du libellé
# ------------------------------------------------------------------------------------------------
@dataclass
class Quad:
    u0: int
    v0: int
    u1: int
    v1: int
    x0: float                            # position écran du texel (u0, v0) (coin), axes u -> X, v -> Y
    y0: float
    kx: float                            # pixels écran par texel
    ky: float

    def ecran(self, u: float, v: float) -> tuple[float, float]:
        return self.x0 + (u - self.u0) * self.kx, self.y0 + (v - self.v0) * self.ky

    def rect_ecran(self):
        (a, b), (c, d) = self.ecran(self.u0, self.v0), self.ecran(self.u1, self.v1)
        return min(a, c), min(b, d), max(a, c), max(b, d)


def quads_libelle(pk: L.Xpck, bouton: str, largeur_tex: int, hauteur_tex: int) -> dict[str, list[Quad]]:
    """{état: [Quad…]} pour `<bouton>_off/_on/_push` : quadrilatères isolés (hors cadre en 9 parties)."""
    noms = L.noms_maillages(pk.lire("RES.bin"))
    sommets = L.sommets_xpvb(pk.lire("000.pvb"))
    res = {}
    for etat in ETATS:
        nom = bouton + etat
        if nom not in noms:
            raise L.ErreurFormat(f"maillage {nom} absent de l'archive de menu")
        pbi = "%03d.pbi" % noms.index(nom)
        quads = []
        for a in L.quads_isoles(L.index_xpvi(pk.lire(pbi))):
            q = sommets[a:a + 4]
            us, vs = [s[3] for s in q], [s[4] for s in q]
            u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
            if u1 - u0 < 8 or v1 - v0 < 8 or u0 < 0 or v0 < 0 or u1 > largeur_tex + 1 or v1 > hauteur_tex:
                continue
            ref = min(q, key=lambda s: (s[3], s[4]))
            opp = max(q, key=lambda s: (s[3], s[4]))
            kx = (opp[0] - ref[0]) / (u1 - u0)
            ky = (opp[1] - ref[1]) / (v1 - v0)
            quads.append(Quad(int(round(u0)), int(round(v0)), int(round(u1)), int(round(v1)),
                              ref[0], ref[1], kx, ky))
        if not quads:
            raise L.ErreurFormat(f"aucun quadrilatère de libellé dans {pbi} ({nom})")
        res[etat] = quads
    return res


def _poser(pixels, W, H, quads: list[Quad], rendu, occupes: dict) -> float:
    """Dessine `rendu` centré dans l'union des quads ; renvoie la part d'encre perdue (0..1)."""
    tw, th, tp = rendu
    sy = 1 if quads[0].ky >= 0 else -1          # Y écran croissant avec v (texture à l'endroit)
    rects = [q.rect_ecran() for q in quads]
    X0, X1 = min(r[0] for r in rects), max(r[2] for r in rects)
    Y0, Y1 = min(r[1] for r in rects), max(r[3] for r in rects)
    ox = (X0 + X1 - tw) / 2
    oy_centre = (Y0 + Y1 - th) / 2 if sy > 0 else (-(Y0 + Y1) - th) / 2
    centres = [((r[0] + r[2]) / 2) for r in rects]
    total = sum(p[3] for p in tp) or 1
    meilleur = None
    for dy in (0, -1, 1, -2, 2):
        ecrit = {}
        pris = 0
        for qi, q in enumerate(quads):
            for v in range(q.v0, q.v1):
                for u in range(q.u0, q.u1):
                    X, Y = q.ecran(u + 0.5, v + 0.5)
                    if min(range(len(quads)), key=lambda j: abs(centres[j] - X)) != qi and \
                            any(r[0] <= X < r[2] for j, r in enumerate(rects) if j != qi):
                        px = (0, 0, 0, 0)            # colonne écran prise par un autre quad
                    else:
                        cx = int(X - ox) if X >= ox else -1
                        cy = int((Y if sy > 0 else -Y) - oy_centre - dy)
                        px = tp[cy * tw + cx] if 0 <= cx < tw and 0 <= cy < th else (0, 0, 0, 0)
                    k = v * W + u
                    if k in ecrit and ecrit[k] != px:
                        ecrit[k] = (0, 0, 0, 0)      # texel partagé par deux quads : transparent
                    elif k not in ecrit:
                        ecrit[k] = px
        pris = sum(p[3] for p in ecrit.values())
        perte = max(0.0, 1 - pris / total)
        if meilleur is None or perte < meilleur[0] - 1e-9:
            meilleur = (perte, ecrit)
        if perte == 0:
            break
    for k, px in meilleur[1].items():
        if k in occupes and occupes[k] != px:
            raise L.ErreurFormat("états du bouton incohérents (même texel, contenus différents)")
        occupes[k] = px
        pixels[k] = px
    return meilleur[0]


@dataclass
class Resultat:
    langue: str
    xa_origine: int
    xa_nouveau: int
    quads: list = field(default_factory=list)
    perte_encre: float = 0.0
    texture: object = None               # L.Imgc modifiée (aperçu)
    quads_off: list = field(default_factory=list)   # quadrilatères de l'état « _off » (aperçu écran)


def modifier_xa(xa: bytes, police: L.Police, texte: str = TEXTE_DEFAUT, bouton: str = BOUTON_DEFAUT,
                langue: str = "?") -> tuple[bytes, Resultat]:
    pk = L.Xpck(xa)
    tex = L.Imgc(pk.lire("000.xi"))
    W, H = tex.largeur, tex.hauteur
    par_etat = quads_libelle(pk, bouton, W, H)
    pixels = list(tex.pixels)
    uv = {(q.u0, q.v0, q.u1, q.v1) for qs in par_etat.values() for q in qs}
    if not any(pixels[v * W + u][3] for (u0, v0, u1, v1) in uv for v in range(v0, v1) for u in range(u0, u1)):
        raise L.ErreurFormat("la zone du libellé est vide dans la texture : archive inattendue")
    for (u0, v0, u1, v1) in uv:
        for v in range(v0, min(v1, H)):
            for u in range(u0, min(u1, W)):
                pixels[v * W + u] = (0, 0, 0, 0)
    rendu = rendre_texte(police, texte)
    occupes: dict = {}
    perte = 0.0
    for etat in ETATS:
        perte = max(perte, _poser(pixels, W, H, par_etat[etat], rendu, occupes))
    tex.pixels = pixels
    nouveau = pk.reconstruire({"000.xi": tex.encoder(pixels)})
    return nouveau, Resultat(langue, len(xa), len(nouveau), sorted(uv), perte, tex, par_etat["_off"])


# ------------------------------------------------------------------------------------------------
# Patch BPS « sur place » de l'archive de langue
# ------------------------------------------------------------------------------------------------
def bps_sur_place(f, base: int, taille: int, position: int, nouveau: bytes) -> bytes:
    """Patch BPS : le fichier (f, base, taille) avec `nouveau` écrit à `position` (même taille totale).
    Voir `bps.bps_sur_place` (plusieurs zones, utilisé pour fusionner libellé et icône d'une même archive)."""
    try:
        return _bps.bps_sur_place(f, base, taille, [(position, nouveau)])
    except _bps.ErreurBps as e:
        raise L.ErreurFormat(str(e)) from e


@dataclass
class Modification:
    """Octets à remplacer dans un fichier de la racine du RomFS (même taille) : fusionnés par l'installateur
    avec ceux d'autres modules (icône) en un seul patch BPS par fichier."""
    fichier: str                         # ex. yw2_lg_fr.fa
    position: int
    octets: bytes
    langue: str = ""
    resultat: object = None


@dataclass
class Patch:
    langue: str
    chemin: str                          # relatif au dossier du titre : romfs_ext/yw2_lg_<LG>.fa.bps
    contenu: bytes
    resultat: Resultat


def modifications(source: L.SourceRomfs, langues=None, texte: str = TEXTE_DEFAUT,
                  bouton: str = BOUTON_DEFAUT) -> tuple[list[Modification], list[str]]:
    """Remplacements (archive de menu redessinée) des archives de langue présentes ; (modifications, avert.)."""
    police = L.Police(_lire_dans_fa(source, "yw2_a.fa", POLICE))
    mods, avert = [], []
    for lg in (langues or LANGUES):
        try:
            f, base, taille = source.ouvrir(nom_fa(lg))
        except L.ErreurFormat as e:
            avert.append(f"{lg} : {e}")
            continue
        with f:
            arc = L.Arc0(f, base)
            nom = chemin_xa(lg)
            if nom not in arc.entrees:
                avert.append(f"{lg} : {nom} absent de {nom_fa(lg)}")
                continue
            off, t_orig = arc.entrees[nom]
            nouveau, res = modifier_xa(arc.lire(nom), police, texte, bouton, lg)
            if len(nouveau) > t_orig:
                avert.append(f"{lg} : archive de menu modifiée plus grande que l'originale "
                             f"({len(nouveau)} > {t_orig}) : langue ignorée")
                continue
            if res.perte_encre > 0.02:
                avert.append(f"{lg} : texte rogné ({res.perte_encre:.0%} de l'encre perdue)")
            nouveau += b"\0" * (t_orig - len(nouveau))
        mods.append(Modification(nom_fa(lg), off, nouveau, lg, res))
    return mods, avert


def generer(source: L.SourceRomfs, langues=None, texte: str = TEXTE_DEFAUT,
            bouton: str = BOUTON_DEFAUT) -> tuple[list[Patch], list[str]]:
    """Patchs BPS des archives de langue présentes (libellé seul) ; renvoie (patchs, avertissements)."""
    mods, avert = modifications(source, langues, texte, bouton)
    patchs = []
    for m in mods:
        f, base, taille = source.ouvrir(m.fichier)
        with f:
            p = bps_sur_place(f, base, taille, m.position, m.octets)
        patchs.append(Patch(m.langue, f"romfs_ext/{m.fichier}.bps", p, m.resultat))
    return patchs, avert


def _lire_dans_fa(source: L.SourceRomfs, fa: str, nom: str) -> bytes:
    f, base, _t = source.ouvrir(fa)
    with f:
        return L.Arc0(f, base).lire(nom)


def conflits(dossier_titre: Path, patchs: list[Patch], nos_fichiers=()) -> tuple[list[Patch], list[str]]:
    """Écarte les langues dont l'archive est déjà modifiée par un autre mod (remplacement dans `romfs/`,
    ou patch/stub dans `romfs_ext/` qui n'est pas le nôtre) : on ne les touche pas."""
    garde, avert = [], []
    for p in patchs:
        fa = nom_fa(p.langue)
        autres = [dossier_titre / "romfs" / fa] + [dossier_titre / "romfs_ext" / (fa + e)
                                                   for e in (".ips", ".bps", ".stub")]
        pris = [a for a in autres if a.exists() and a.relative_to(dossier_titre).as_posix() not in nos_fichiers]
        if pris:
            avert.append(f"{p.langue} : {', '.join(str(a) for a in pris)} existe (autre mod) : libellé non installé "
                         "pour cette langue")
            continue
        garde.append(p)
    return garde, avert


# ------------------------------------------------------------------------------------------------
# Aperçu
# ------------------------------------------------------------------------------------------------
def apercu(res: Resultat, chemin_png: Path, echelle: int = 3) -> None:
    """PNG de la zone des libellés (texture modifiée), agrandie, sur fond bleu (≈ fond du bouton)."""
    tex = res.texture
    W = tex.largeur
    u0 = max(0, min(q[0] for q in res.quads) - 8)
    v0 = max(0, min(q[1] for q in res.quads) - 30)
    u1 = min(W, max(q[2] for q in res.quads) + 8)
    v1 = min(tex.hauteur, max(q[3] for q in res.quads) + 4)
    fond = (40, 150, 230)
    out = []
    for y in range((v1 - v0) * echelle):
        for x in range((u1 - u0) * echelle):
            r, g, b, a = tex.pixels[(v0 + y // echelle) * W + u0 + x // echelle]
            out.append(tuple((c * a + f * (255 - a)) // 255 for c, f in zip((r, g, b), fond)) + (255,))
    L.ecrire_png(chemin_png, (u1 - u0) * echelle, (v1 - v0) * echelle, out)


def apercu_ecran(res: Resultat, chemin_png: Path, echelle: int = 4) -> None:
    """PNG du libellé tel qu'affiché (quads de l'état « _off » posés à leur position écran, au plus proche)."""
    tex = res.texture
    W = tex.largeur
    rects = [q.rect_ecran() for q in res.quads_off]
    X0, Y0 = int(min(r[0] for r in rects)) - 4, int(min(r[1] for r in rects)) - 4
    X1, Y1 = int(max(r[2] for r in rects)) + 4, int(max(r[3] for r in rects)) + 4
    w, h = X1 - X0, Y1 - Y0
    fond = (40, 150, 230)
    toile = [fond + (255,)] * (w * h)
    for q in res.quads_off:
        for v in range(q.v0, q.v1):
            for u in range(q.u0, q.u1):
                X, Y = q.ecran(u + 0.5, v + 0.5)
                x, y = int(X) - X0, int(Y) - Y0
                r, g, b, a = tex.pixels[v * W + u]
                base = toile[y * w + x]
                toile[y * w + x] = tuple((c * a + f * (255 - a)) // 255 for c, f in zip((r, g, b), base)) + (255,)
    grand = [toile[(y // echelle) * w + x // echelle] for y in range(h * echelle) for x in range(w * echelle)]
    L.ecrire_png(chemin_png, w * echelle, h * echelle, grand)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="dossier du RomFS extrait, ou ROM déchiffrée (.3ds/.cci/.cxi)")
    ap.add_argument("--sortie", required=True, type=Path,
                    help="dossier où écrire romfs_ext/*.bps (ex. build/tests_azahar/…/00040000001B2900)")
    ap.add_argument("--langues", help="liste séparée par des virgules (défaut : toutes)")
    ap.add_argument("--texte", default=TEXTE_DEFAUT)
    ap.add_argument("--bouton", default=BOUTON_DEFAUT, help="btn_04 (Transfert EF/FB, défaut) ou btn_03 (Liaison)")
    ap.add_argument("--apercu", type=Path, help="dossier des PNG d'aperçu (hors git, ex. build/libelle_apercu)")
    ap.add_argument("--fa-complet", action="store_true",
                    help="(essai) écrit aussi romfs/yw2_lg_<LG>.fa modifié en entier (~134 Mo), variante de "
                         "chargement par remplacement de fichier, sans romfs_ext")
    a = ap.parse_args(argv)
    try:
        src = L.SourceRomfs(a.romfs)
        patchs, avert = generer(src, a.langues.split(",") if a.langues else None, a.texte, a.bouton)
    except (L.ErreurFormat, OSError) as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    for p in patchs:
        dest = a.sortie / p.chemin
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.contenu)
        r = p.resultat
        print(f"{p.langue} : {dest} ({len(p.contenu)} o) ; archive de menu {r.xa_origine} -> {r.xa_nouveau} o ; "
              f"zones {r.quads}")
        if a.fa_complet:
            try:
                from . import bps
            except ImportError:
                import bps  # type: ignore[no-redef]
            f, base, taille = src.ouvrir(nom_fa(p.langue))
            with f:
                f.seek(base)
                fa = bps.bps_appliquer(f.read(taille), p.contenu)
            complet = a.sortie / "romfs" / nom_fa(p.langue)
            complet.parent.mkdir(parents=True, exist_ok=True)
            complet.write_bytes(fa)
            print(f"{p.langue} : {complet} (archive entière)")
        if a.apercu:
            a.apercu.mkdir(parents=True, exist_ok=True)
            apercu(r, a.apercu / f"texture_{p.langue}.png")
            apercu_ecran(r, a.apercu / f"ecran_{p.langue}.png")
    for w in avert:
        print(f"attention : {w}")
    return 0 if patchs else 1


if __name__ == "__main__":
    sys.exit(main())
