"""Thème visuel du lanceur : couleurs, polices (avec repli), widgets dessinés sur Canvas, mise en page.

Direction artistique inspirée de l'interface de Yo-kai Watch (rouge montre, blanc, contours noirs épais, coins
arrondis, accents or et cyan), sans aucun asset du jeu : l'emblème de l'en-tête est le logo Archipelago de
MDarkmooN (`ressources/embleme_<N>.png`, fait par `outils/preparer_icone.py`), repli sur un cadran de montre en
formes géométriques si l'image ne se charge pas ; les motifs sont dessinés ici. Bibliothèque standard seulement (tkinter). Aucune logique du lanceur : la vue (`vue.py`) assemble
ces éléments.

    Theme(racine)            polices choisies parmi celles du système, facteur d'échelle (100 %, 150 %...)
    Scene(racine, theme)     grand Canvas : fond à points, bandeau rouge à rayons, emblème, cartes, pied
    Pilule(...)              bouton « pilule » (ombre portée, survol, appui, focus clavier, état désactivé)
    Pastille(...)            voyant d'état (ok / attention / erreur / neutre)
"""
from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont, ttk
from typing import Callable, Iterable

# ---------------------------------------------------------------------------------------------------- couleurs
ROUGE = "#E4002B"
ROUGE_SURVOL = "#FF2A4F"
ROUGE_RAYON = "#CC0026"
ROUGE_SOMBRE = "#8A0019"
BLANC = "#FFFFFF"
NOIR = "#1B1416"
OR = "#FFC21A"
OR_SURVOL = "#FFD65C"
OR_CLAIR = "#FFE9A6"
CYAN = "#3CC8EC"
CYAN_CLAIR = "#A6EBFA"
CYAN_PALE = "#E5F8FD"
CYAN_TEXTE = "#0A4D61"
FOND = "#FFF7EE"
POINT = "#F4DFCB"
OMBRE_CARTE = "#EBCFB8"
TEXTE = "#231B1C"
TEXTE_DOUX = "#6B5F59"
BLANC_SURVOL = "#FFF4CC"
INACTIF_FOND = "#F1ECE7"
INACTIF_TEXTE = "#A69C94"
INACTIF_CONTOUR = "#BDB3AA"
FOCUS = "#0096C7"

RESSOURCES = Path(__file__).resolve().parent / "ressources"
TAILLES_EMBLEME = (60, 75, 90, 105, 120)        # diamètres disponibles (2 × rayon de l'emblème, 100 % .. 200 %)
TAILLES_ICONE = (16, 24, 32, 48, 64, 128, 256)

NIVEAUX = {"ok": "#23A94F", "attention": "#F28C00", "erreur": ROUGE, "neutre": "#BDB5AE"}

# Préférences de polices (Windows d'abord, puis repli courant) ; aucune police n'est embarquée.
POLICES_NOIRES = ("Segoe UI Black", "Arial Black")
POLICES_DEMI = ("Segoe UI Semibold", "Segoe UI Variable Display Semib")
POLICES_TEXTE = ("Segoe UI", "Helvetica", "Arial", "DejaVu Sans", "Liberation Sans")


def choisir_famille(preferences: Iterable[str], disponibles: Iterable[str]) -> str | None:
    """Première famille de `preferences` présente dans `disponibles` (casse ignorée), ou None."""
    dispo = {f.lower(): f for f in disponibles}
    for p in preferences:
        if p.lower() in dispo:
            return dispo[p.lower()]
    return None


def specs_polices(disponibles: Iterable[str]) -> dict[str, tuple[str, int, str]]:
    """(famille, taille en points, graisse) de chaque rôle, avec repli : une famille « Black » ou « Semibold »
    absente est remplacée par la famille de texte en gras ; sans aucune famille connue, « TkDefaultFont »."""
    dispo = list(disponibles)
    texte = choisir_famille(POLICES_TEXTE, dispo) or "TkDefaultFont"
    noire = choisir_famille(POLICES_NOIRES, dispo)
    demi = choisir_famille(POLICES_DEMI, dispo)

    def n(taille):
        return (noire, taille, "normal") if noire else (texte, taille, "bold")

    def d(taille):
        return (demi, taille, "normal") if demi else (texte, taille, "bold")

    return {
        "titre": n(20), "titre_etroit": n(15), "jouer": n(16), "carte": n(12), "badge": n(10),
        "sous_titre": d(10), "bouton": d(10), "bouton_petit": d(9),
        "texte": (texte, 10, "normal"), "petit": (texte, 9, "normal"),
    }


class Theme:
    """Polices et facteur d'échelle d'une fenêtre. `px(n)` : n pixels à 100 % (96 ppp), mis à l'échelle."""

    def __init__(self, racine: tk.Misc, familles: Iterable[str] | None = None):
        self.echelle = max(1.0, racine.winfo_fpixels("1i") / 96.0)
        dispo = tkfont.families(racine) if familles is None else familles
        self.specs = specs_polices(dispo)
        self.polices = {role: tkfont.Font(racine, family=f, size=s, weight=g)
                        for role, (f, s, g) in self.specs.items()}

    def px(self, n: float) -> int:
        return max(1, round(n * self.echelle))

    def __getitem__(self, role: str) -> tkfont.Font:
        return self.polices[role]


# ---------------------------------------------------------------------------------------------------- dessin
def points_rond_rect(x1: float, y1: float, x2: float, y2: float, r: float, pas: int = 8) -> list[float]:
    """Polygone d'un rectangle aux coins arrondis (arcs calculés : plus net qu'un polygone lissé)."""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts: list[float] = []
    for cx, cy, a0 in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0), (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
        for i in range(pas + 1):
            a = math.radians(a0 + 90 * i / pas)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def rond_rect(c: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    return c.create_polygon(points_rond_rect(x1, y1, x2, y2, r), **kw)


def etoile(cx: float, cy: float, r: float, branches: int = 5, creux: float = 0.45) -> list[float]:
    pts: list[float] = []
    for i in range(branches * 2):
        a = math.radians(-90 + 180 * i / branches)
        rr = r if i % 2 == 0 else r * creux
        pts += [cx + rr * math.cos(a), cy + rr * math.sin(a)]
    return pts


def charger_image(racine: tk.Misc, nom: str) -> tk.PhotoImage | None:
    """PNG de `ressources/` (Tk 8.6 lit le PNG) ; None s'il manque ou ne se lit pas."""
    try:
        return tk.PhotoImage(master=racine, file=str(RESSOURCES / nom))
    except (tk.TclError, OSError):
        return None


def nom_embleme(diametre: float) -> str:
    return "embleme_%d.png" % min(TAILLES_EMBLEME, key=lambda t: abs(t - diametre))


MASQUE_POINT_2 = ((1, 2), (0, 3), (0, 4), (0, 4), (1, 3))     # rayon 2 : (1re, dernière) colonne de chaque ligne


def masque_point(r: int) -> list[tuple[int, int]]:
    """Pixels (dx, dy) d'un point du fond de rayon `r`, autour de son centre : la forme que Tk donne à un ovale plein
    sans contour de boîte [-r, r] sous Windows (relevée sur des captures à 100 % et 150 %)."""
    if r == 2:
        return [(x - 2, y - 2) for y, (a, b) in enumerate(MASQUE_POINT_2) for x in range(a, b + 1)]
    return [(dx, dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r + 1]


def image_points(maitre: tk.Misc, largeur: int, rangs: int, pas: int, rayon: int, marge: int) -> tk.PhotoImage:
    """Fond à points en réseau hexagonal, en UNE image (`largeur` px, `rangs` rangées espacées de `pas`, la 1re
    rangée centrée à y = `rayon`) : rangées paires à x = marge + k * pas, impaires décalées de pas / 2 ; seuls les
    points dont le centre est dans la largeur sont dessinés. Remplace ~2 000 ovales du canevas (voir `Scene._entete`) :
    le motif est posé une fois sur une tuile, que Tk répète lui-même (`copy -to`)."""
    hauteur = (rangs - 1) * pas + 2 * rayon + 1
    tuile = tk.PhotoImage(master=maitre, width=pas, height=2 * pas)
    lignes = [[FOND] * pas for _ in range(2 * pas)]
    motif = masque_point(rayon)
    departs = (marge, pas / 2 + marge)
    for rang, x in enumerate(departs):
        cx = math.floor(x + 0.5)
        for dx, dy in motif:
            if 0 <= cx + dx < pas:
                lignes[rang * pas + rayon + dy][cx + dx] = POINT
    tuile.put(" ".join("{" + " ".join(ligne) + "}" for ligne in lignes))
    image = tk.PhotoImage(master=maitre, width=largeur, height=hauteur)
    maitre.tk.call(image, "copy", tuile, "-to", 0, 0, largeur, hauteur)
    for x in departs:                                   # point coupé par le bord droit : centre hors de la largeur
        k = max(0, math.ceil((largeur - x) / pas))
        gauche = math.floor(x + k * pas + 0.5) - rayon
        if gauche < largeur:
            image.put(FOND, to=(max(0, gauche), 0, largeur, hauteur))
    return image


def dessiner_embleme(c: tk.Canvas, cx: float, cy: float, R: float, px: Callable[[float], int], tag: str) -> None:
    """Cadran de montre / médaille en formes géométriques (pas le logo officiel) : charnière, boîtier noir,
    lunette or graduée, verre cyan avec reflet, médaille rouge à étoile blanche."""
    kw = {"tags": tag}
    o = px(3)
    c.create_oval(cx - R + o, cy - R + o, cx + R + o, cy + R + o, fill=ROUGE_SOMBRE, outline="", **kw)
    # charnière du couvercle (en haut) et boutons latéraux
    rond_rect(c, cx - 0.32 * R, cy - 1.16 * R, cx + 0.32 * R, cy - 0.7 * R, 0.12 * R, fill=NOIR, outline="", **kw)
    rond_rect(c, cx - 0.2 * R, cy - 1.08 * R, cx + 0.2 * R, cy - 0.9 * R, 0.06 * R, fill=OR, outline="", **kw)
    for s in (-1, 1):
        rond_rect(c, cx + s * 0.9 * R - 0.14 * R, cy - 0.16 * R, cx + s * 0.9 * R + 0.14 * R, cy + 0.16 * R,
                  0.06 * R, fill=NOIR, outline="", **kw)
        rond_rect(c, cx + s * 1.02 * R - 0.08 * R, cy - 0.12 * R, cx + s * 1.02 * R + 0.08 * R, cy + 0.12 * R,
                  0.04 * R, fill=BLANC, outline=NOIR, width=max(1, px(1)), **kw)
    c.create_oval(cx - R, cy - R, cx + R, cy + R, fill=NOIR, outline="", **kw)
    r1 = 0.88 * R
    c.create_oval(cx - r1, cy - r1, cx + r1, cy + r1, fill=OR, outline="", **kw)
    for i in range(12):                                          # graduations
        a = math.radians(i * 30)
        ra, rb = 0.84 * R, (0.7 if i % 3 == 0 else 0.75) * R
        c.create_line(cx + ra * math.sin(a), cy - ra * math.cos(a), cx + rb * math.sin(a), cy - rb * math.cos(a),
                      fill=NOIR, width=px(2.4 if i % 3 == 0 else 1.4), capstyle="round", **kw)
    r2 = 0.66 * R
    c.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, fill=NOIR, outline="", **kw)
    r3 = 0.58 * R
    c.create_oval(cx - r3, cy - r3, cx + r3, cy + r3, fill=CYAN_CLAIR, outline="", **kw)
    c.create_arc(cx - 0.48 * R, cy - 0.48 * R, cx + 0.48 * R, cy + 0.48 * R, start=100, extent=70, style="arc",
                 outline=BLANC, width=px(2.5), **kw)
    r4 = 0.34 * R
    c.create_oval(cx - r4, cy - r4, cx + r4, cy + r4, fill=ROUGE, outline=NOIR, width=px(2), **kw)
    c.create_polygon(etoile(cx, cy + 0.02 * R, 0.24 * R), fill=BLANC, outline="", **kw)


# ---------------------------------------------------------------------------------------------------- widgets
class Pilule(tk.Canvas):
    """Bouton en forme de pilule. Interface compatible avec `ttk.Button` pour ce que la vue utilise :
    `state([...])`, `instate([...])`, `invoke()`. Clavier : Tab pour le focus, Entrée ou Espace pour cliquer."""

    GENRES = {  # fond, survol, texte, épaisseur du contour, décalage de l'ombre
        "normal": (BLANC, BLANC_SURVOL, TEXTE, 2, 3),
        "or": (OR, OR_SURVOL, NOIR, 2, 3),
        "primaire": (ROUGE, ROUGE_SURVOL, BLANC, 3, 5),
        "clair": (BLANC, BLANC_SURVOL, TEXTE, 2, 3),
        "onglet": (ROUGE, ROUGE_SURVOL, BLANC, 2, 3),          # onglet choisi (même taille que « normal »)
    }

    def __init__(self, parent: tk.Misc, theme: Theme, texte: str, commande: Callable[[], object] | None, *,
                 genre: str = "normal", fond: str = BLANC, police: str = "bouton", padx: int = 16, pady: int = 5,
                 icone: str | None = None, largeur_min: int = 0):
        self.th, self.texte, self.commande, self.genre = theme, texte, commande, genre
        self.fond_g, self.survol_g, self.texte_g, ep, omb = self.GENRES[genre]
        px = theme.px
        self.ep, self.omb, self.marge = px(ep), px(omb), px(3)
        self.police = theme[police]
        self.icone = icone
        self.l_icone = round(self.police.metrics("linespace") * 0.55) if icone else 0
        tw = self.police.measure(texte) + (self.l_icone + px(10) if icone else 0)
        self.w = max(tw + 2 * px(padx), largeur_min)
        self.h = self.police.metrics("linespace") + 2 * px(pady)
        super().__init__(parent, width=self.w + self.omb + 2 * self.marge, height=self.h + self.omb + 2 * self.marge,
                         bg=fond, highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self._actif, self._survol, self._appui, self._focus = True, False, False, False
        for ev, f in (("<Enter>", self._entrer), ("<Leave>", self._sortir), ("<ButtonPress-1>", self._presser),
                      ("<ButtonRelease-1>", self._relacher), ("<FocusIn>", self._focus_in),
                      ("<FocusOut>", self._focus_out), ("<KeyPress-space>", self._touche),
                      ("<KeyPress-Return>", self._touche), ("<KeyPress-KP_Enter>", self._touche)):
            self.bind(ev, f)
        self.dessiner()

    # -- compatibilité ttk
    def state(self, specs: Iterable[str] | None = None):
        for s in specs or ():
            if s == "disabled":
                self._actif = False
            elif s == "!disabled":
                self._actif = True
        self.configure(takefocus=1 if self._actif else 0, cursor="hand2" if self._actif else "arrow")
        if not self._actif:
            self._appui = False
        self.dessiner()
        return () if self._actif else ("disabled",)

    def instate(self, specs: Iterable[str]) -> bool:
        return all((not self._actif) if s == "disabled" else self._actif for s in specs
                   if s in ("disabled", "!disabled"))

    def invoke(self):
        if self._actif and self.commande is not None:
            return self.commande()
        return None

    def changer_texte(self, texte: str) -> None:
        """Autre libellé (ex. « Afficher » / « Masquer ») ; la taille ne change pas (prévoir `largeur_min`)."""
        self.texte = texte
        self.dessiner()

    def changer_genre(self, genre: str) -> None:
        """Couleurs d'un autre genre (onglet choisi / non choisi) ; la taille ne change pas."""
        self.fond_g, self.survol_g, self.texte_g, ep, _omb = self.GENRES[genre]
        self.ep = self.th.px(ep)
        self.genre = genre
        self.dessiner()

    # -- dessin
    def dessiner(self) -> None:
        self.delete("all")
        m, w, h = self.marge, self.w, self.h
        d = self.omb if self._appui else 0
        r = h / 2
        if self._actif:
            fond = self.survol_g if (self._survol or self._focus) else self.fond_g
            texte, contour = self.texte_g, NOIR
            if not self._appui:
                rond_rect(self, m + self.omb, m + self.omb, m + w + self.omb, m + h + self.omb, r, fill=NOIR,
                          outline="")
        else:
            fond, texte, contour = INACTIF_FOND, INACTIF_TEXTE, INACTIF_CONTOUR
        x, y = m + d, m + d
        rond_rect(self, x, y, x + w, y + h, r, fill=fond, outline=contour, width=self.ep)
        if self._focus and self._actif:
            e = self.th.px(4)
            rond_rect(self, x + e, y + e, x + w - e, y + h - e, r - e, fill="", outline=FOCUS,
                      width=self.th.px(1.5), dash=(3, 2))
        cx, cy = x + w / 2, y + h / 2
        if self.icone == "jouer":
            tw = self.police.measure(self.texte)
            li = self.l_icone
            total = li + self.th.px(10) + tw
            ix = cx - total / 2
            self.create_polygon(ix, cy - li / 2 * 1.1, ix + li * 0.95, cy, ix, cy + li / 2 * 1.1, fill=texte,
                                outline=NOIR if self._actif else "", width=self.th.px(1.5), joinstyle="round")
            self.create_text(ix + li + self.th.px(10), cy, text=self.texte, font=self.police, fill=texte, anchor="w")
        else:
            self.create_text(cx, cy, text=self.texte, font=self.police, fill=texte)

    # -- événements
    def _entrer(self, _e=None):
        self._survol = True
        self.dessiner()

    def _sortir(self, _e=None):
        self._survol = self._appui = False
        self.dessiner()

    def _presser(self, _e=None):
        if self._actif:
            self._appui = True
            self.focus_set()
            self.dessiner()

    def _relacher(self, e=None):
        dedans = e is None or (0 <= e.x < int(self["width"]) and 0 <= e.y < int(self["height"]))
        faire = self._appui and dedans
        self._appui = False
        self.dessiner()
        if faire:
            self.invoke()

    def _focus_in(self, _e=None):
        self._focus = True
        self.dessiner()

    def _focus_out(self, _e=None):
        self._focus = False
        self.dessiner()

    def _touche(self, _e=None):
        if not self._actif:
            return "break"
        self._appui = True
        self.dessiner()
        self.after(90, self._fin_touche)
        return "break"

    def _fin_touche(self):
        self._appui = False
        try:
            self.dessiner()
        except tk.TclError:
            return
        self.invoke()


class Pastille(tk.Canvas):
    """Voyant rond coloré ; `niveau(None)` le cache (la place reste réservée, pour l'alignement)."""

    def __init__(self, parent: tk.Misc, theme: Theme, fond: str = BLANC):
        self.d = theme.px(14)
        super().__init__(parent, width=self.d + 2, height=self.d + 2, bg=fond, highlightthickness=0, bd=0,
                         takefocus=0)
        self.px = theme.px
        self.valeur: str | None = None
        self.niveau(None)

    def niveau(self, niveau: str | None) -> None:
        self.valeur = niveau
        self.delete("all")
        if niveau is None:
            return
        d = self.d
        self.create_oval(1, 1, d, d, fill=NIVEAUX.get(niveau, NIVEAUX["neutre"]), outline=NOIR,
                         width=max(1, self.px(1.5)))
        e = d * 0.28
        self.create_oval(d * 0.3, d * 0.26, d * 0.3 + e, d * 0.26 + e * 0.8, fill=BLANC, outline="")


class Badge(tk.Canvas):
    """Médaillon d'en-tête de carte : numéro sur disque or, ou étoile sur disque cyan (numéro absent)."""

    def __init__(self, parent: tk.Misc, theme: Theme, numero: str | None, fond: str = BLANC):
        d = theme.px(26)
        super().__init__(parent, width=d + theme.px(2) + 2, height=d + theme.px(2) + 2, bg=fond,
                         highlightthickness=0, bd=0, takefocus=0)
        o = theme.px(2)
        self.create_oval(1 + o, 1 + o, d + o, d + o, fill=NOIR, outline="")
        self.create_oval(1, 1, d, d, fill=OR if numero else CYAN, outline=NOIR, width=theme.px(2))
        c = (d + 1) / 2
        if numero:
            self.create_text(c, c, text=numero, font=theme["badge"], fill=NOIR)
        else:
            self.create_polygon(etoile(c, c + theme.px(0.5), d * 0.3), fill=BLANC, outline=NOIR,
                                width=max(1, theme.px(1)))


class Bascule(tk.Canvas):
    """Case à cocher dessinée (case arrondie à contour noir, coche blanche sur rouge) suivie de son texte, à
    l'échelle du thème. Clavier : Tab pour le focus, Espace ou Entrée pour basculer. `variable` : tk.BooleanVar."""

    def __init__(self, parent: tk.Misc, theme: Theme, texte: str, variable: tk.BooleanVar,
                 commande: Callable[[], object] | None = None, fond: str = BLANC):
        self.th, self.texte, self.var, self.commande = theme, texte, variable, commande
        self.police = theme["texte"]
        self.c = theme.px(16)
        self.marge = theme.px(3)
        h = max(self.c, self.police.metrics("linespace")) + 2 * self.marge
        w = self.c + theme.px(8) + self.police.measure(texte) + 2 * self.marge
        super().__init__(parent, width=w, height=h, bg=fond, highlightthickness=0, bd=0, takefocus=1,
                         cursor="hand2")
        self.h, self.w = h, w
        self._actif, self._focus, self._survol = True, False, False
        for ev, f in (("<ButtonRelease-1>", lambda _e: self.basculer()), ("<KeyPress-space>", self._touche),
                      ("<KeyPress-Return>", self._touche), ("<FocusIn>", lambda _e: self._etat(focus=True)),
                      ("<FocusOut>", lambda _e: self._etat(focus=False)), ("<Enter>", lambda _e: self._etat(survol=True)),
                      ("<Leave>", lambda _e: self._etat(survol=False))):
            self.bind(ev, f)
        variable.trace_add("write", lambda *_: self.dessiner())
        self.dessiner()

    def _etat(self, focus=None, survol=None):
        if focus is not None:
            self._focus = focus
        if survol is not None:
            self._survol = survol
        self.dessiner()

    def _touche(self, _e=None):
        self.basculer()
        return "break"

    def state(self, specs: Iterable[str] | None = None):
        for s in specs or ():
            if s in ("disabled", "!disabled"):
                self._actif = s == "!disabled"
        self.configure(takefocus=1 if self._actif else 0, cursor="hand2" if self._actif else "arrow")
        self.dessiner()

    def instate(self, specs: Iterable[str]) -> bool:
        return all((not self._actif) if s == "disabled" else self._actif for s in specs
                   if s in ("disabled", "!disabled"))

    def basculer(self) -> None:
        if not self._actif:
            return
        self.var.set(not self.var.get())
        if self.commande is not None:
            self.commande()

    def dessiner(self) -> None:
        try:
            self.delete("all")
        except tk.TclError:
            return
        px, m, c = self.th.px, self.marge, self.c
        y = (self.h - c) / 2
        coche = bool(self.var.get())
        if not self._actif:
            fond, contour, texte = INACTIF_FOND, INACTIF_CONTOUR, INACTIF_TEXTE
        else:
            fond = ROUGE if coche else (BLANC_SURVOL if self._survol or self._focus else BLANC)
            contour, texte = NOIR, TEXTE
        rond_rect(self, m, y, m + c, y + c, px(4), fill=fond, outline=contour, width=px(2))
        if coche:
            self.create_line(m + c * 0.25, y + c * 0.52, m + c * 0.44, y + c * 0.72, m + c * 0.77, y + c * 0.3,
                             fill=BLANC if self._actif else INACTIF_TEXTE, width=px(2.4), capstyle="round",
                             joinstyle="round")
        tx = m + c + px(8)
        self.create_text(tx, self.h / 2, text=self.texte, font=self.police, fill=texte, anchor="w")
        if self._focus and self._actif:
            self.create_line(tx, self.h - px(2), tx + self.police.measure(self.texte), self.h - px(2), fill=FOCUS,
                             width=px(1.5), dash=(3, 2))


class Champ(tk.Canvas):
    """Champ de saisie du thème : cadre arrondi à contour noir (bleu de focus quand il a le clavier, rouge si
    `signaler(True)`), fond blanc, texte à l'échelle. S'étire en largeur (grille `sticky="ew"`). `masque` : caractères
    remplacés par des points (mot de passe), réglable par `masquer()`."""

    PUCE = "•"

    def __init__(self, parent: tk.Misc, theme: Theme, variable: tk.StringVar, *, masque: bool = False,
                 largeur: int = 140, fond: str = BLANC):
        self.th = theme
        px = theme.px
        police = theme["texte"]
        self.pad = px(9)
        self.h = police.metrics("linespace") + 2 * px(6)
        super().__init__(parent, width=px(largeur), height=self.h, bg=fond, highlightthickness=0, bd=0, takefocus=0,
                         cursor="xterm")
        self.entree = tk.Entry(self, textvariable=variable, font=police, bd=0, relief="flat", highlightthickness=0,
                               bg=BLANC, fg=TEXTE, insertbackground=NOIR, selectbackground=CYAN_CLAIR,
                               selectforeground=NOIR, show=self.PUCE if masque else "", width=1)
        self._fen = self.create_window(self.pad, self.h / 2, window=self.entree, anchor="w")
        self._focus = self._erreur = False
        self.entree.bind("<FocusIn>", lambda _e: self._etat(focus=True), add="+")
        self.entree.bind("<FocusOut>", lambda _e: self._etat(focus=False), add="+")
        self.bind("<Configure>", lambda _e: self.dessiner())
        self.bind("<ButtonPress-1>", lambda _e: self.entree.focus_set())
        self.dessiner()

    def _etat(self, focus: bool | None = None) -> None:
        if focus is not None:
            self._focus = focus
        self.dessiner()

    def masquer(self, oui: bool) -> None:
        self.entree.configure(show=self.PUCE if oui else "")

    @property
    def masque(self) -> bool:
        return bool(self.entree.cget("show"))

    def signaler(self, erreur: bool) -> None:
        if erreur != self._erreur:
            self._erreur = erreur
            self.dessiner()

    def dessiner(self) -> None:
        try:
            self.delete("cadre")
            w = max(self.winfo_width(), 1) if self.winfo_width() > 1 else int(self.cget("width"))
        except tk.TclError:
            return
        px = self.th.px
        contour = ROUGE if self._erreur else (FOCUS if self._focus else NOIR)
        e = px(2)
        rond_rect(self, e / 2, e / 2, w - e / 2 - 1, self.h - e / 2 - 1, px(9), fill=BLANC, outline=contour, width=e,
                  tags="cadre")
        self.tag_lower("cadre")
        self.itemconfigure(self._fen, width=max(10, w - 2 * self.pad))


def styler_ttk(racine: tk.Misc, theme: Theme) -> ttk.Style:
    """Styles ttk du thème (thème « clam », seul à accepter les couleurs partout) : liste « Yokai.Treeview »,
    listes déroulantes « Yokai.TCombobox », barre de défilement. Tailles à l'échelle (100 % .. 200 %)."""
    px = theme.px
    s = ttk.Style(racine)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    ligne = theme["texte"].metrics("linespace")
    s.configure("Yokai.Treeview", background=BLANC, fieldbackground=BLANC, foreground=TEXTE, font=theme["texte"],
                rowheight=ligne + px(9), bordercolor=NOIR, borderwidth=0, relief="flat", indent=px(18))
    s.map("Yokai.Treeview", background=[("selected", CYAN_CLAIR)], foreground=[("selected", NOIR)])
    s.configure("Yokai.Treeview.Heading", background=OR, foreground=NOIR, font=theme["bouton_petit"],
                relief="flat", bordercolor=NOIR, borderwidth=1, padding=(px(6), px(4)))
    s.map("Yokai.Treeview.Heading", background=[("active", OR_SURVOL)])
    s.layout("Yokai.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    s.configure("Yokai.TCombobox", fieldbackground=BLANC, background=BLANC, foreground=TEXTE, arrowcolor=NOIR,
                bordercolor=NOIR, lightcolor=BLANC, darkcolor=BLANC, padding=(px(6), px(3)), arrowsize=px(13))
    s.map("Yokai.TCombobox", fieldbackground=[("readonly", BLANC)], background=[("active", BLANC_SURVOL)],
          bordercolor=[("focus", FOCUS)], selectbackground=[("readonly", BLANC)],
          selectforeground=[("readonly", TEXTE)])
    s.configure("Yokai.Vertical.TScrollbar", background=OR_CLAIR, troughcolor=FOND, bordercolor=NOIR,
                arrowcolor=NOIR, lightcolor=OR_CLAIR, darkcolor=OR_CLAIR, arrowsize=px(14))
    racine.option_add("*TCombobox*Listbox.font", theme["texte"])
    racine.option_add("*TCombobox*Listbox.selectBackground", CYAN_CLAIR)
    racine.option_add("*TCombobox*Listbox.selectForeground", NOIR)
    return s


def separer_numero(titre: str) -> tuple[str | None, str]:
    """« 1. ROM du jeu » -> ("1", "ROM du jeu") ; sans numéro : (None, titre)."""
    tete, sep, reste = titre.partition(". ")
    if sep and tete.isdigit():
        return tete, reste
    return None, titre


def insecables(texte: str) -> str:
    """Espaces insécables autour des guillemets français et avant « : » (pas de « orphelin en fin de ligne)."""
    nb = "\u00a0"
    return (texte.replace("« ", "«" + nb).replace(" »", nb + "»").replace(" :", nb + ":")
            .replace(" ;", nb + ";"))


def raccourcir_chemin(texte: str, police: tkfont.Font, largeur: int) -> str:
    """Coupe le milieu d'un chemin trop long pour `largeur` pixels (« C:\\Users\\…\\jeu.3ds »)."""
    if largeur <= 0 or police.measure(texte) <= largeur:
        return texte
    g, d = len(texte) // 2, len(texte) // 2
    while g > 3 and police.measure(texte[:g] + "…" + texte[-d:]) > largeur:
        if g >= d:
            g -= 1
        else:
            d -= 1
    return texte[:g] + "…" + texte[-d:]


class LabelChemin(tk.Label):
    """Label d'un chemin de fichier : texte de la variable, coupé au milieu s'il ne tient pas en largeur."""

    def __init__(self, parent, variable: tk.StringVar, police: tkfont.Font, **kw):
        super().__init__(parent, font=police, anchor="w", justify="left", **kw)
        self.var, self.police, self.largeur = variable, police, 0
        variable.trace_add("write", lambda *_: self.maj())
        self.maj()

    def fixer_largeur(self, largeur: int) -> None:
        if largeur != self.largeur:
            self.largeur = largeur
            self.maj()

    def maj(self) -> None:
        try:
            self.configure(text=raccourcir_chemin(self.var.get(), self.police, self.largeur))
        except tk.TclError:
            pass




# ---------------------------------------------------------------------------------------------------- scène
class Scene:
    """Toute la fenêtre est un Canvas : fond crème à points, bandeau rouge à rayons avec l'emblème, puis des
    blocs (cartes blanches arrondies à contour noir, bouton centré, pied de page).

    Mise en page adaptative : fenêtre large (>= `LARGEUR_DEUX_COLONNES` à 100 %), colonne gauche (blocs « g »)
    et colonne droite (cartes « d » en haut, la dernière étirée, boutons « d » en bas, alignés sur la gauche) ;
    fenêtre étroite, une seule colonne dans l'ordre de création. Barre de défilement seulement si le contenu
    dépasse (petit écran à 150 %). Mise en page refaite au plus une fois par tour de boucle."""

    LARGEUR_DEUX_COLONNES = 800
    LARGEUR_DEFAUT = 900

    def __init__(self, racine: tk.Tk, theme: Theme):
        self.r, self.th = racine, theme
        px = theme.px
        largeur = px(self.LARGEUR_DEFAUT)
        try:
            if racine.winfo_screenwidth() < largeur + px(40):
                largeur = px(620)
        except tk.TclError:
            pass
        self.c = tk.Canvas(racine, bg=FOND, highlightthickness=0, bd=0, width=largeur, height=px(560),
                           takefocus=0)
        self.c.grid(row=0, column=0, sticky="nsew")
        self.defil = ttk.Scrollbar(racine, orient="vertical", command=self.c.yview)
        self.c.configure(yscrollcommand=self.defil.set)
        racine.rowconfigure(0, weight=1)
        racine.columnconfigure(0, weight=1)
        self.blocs: list[tuple[str, str, object]] = []          # (genre, colonne, objet)
        self.textes: list[tuple[tk.Widget, int, tk.Widget]] = []
        self.fenetres: dict[str, int] = {}
        self.titre = self.sous_titre = ""
        self.b_langue: Pilule | None = None
        self.pied_var: tk.StringVar | None = None
        self._carte: tk.Widget | None = None
        self._prevu = False
        self._demandees = {1, px(560)}                     # hauteurs de fenêtre posées par la mise en page
        self.embleme = charger_image(racine, nom_embleme(2 * px(30)))   # logo Archipelago (sinon dessin)
        self.hauteur = 0
        self._points: tk.PhotoImage | None = None          # fond à points (une image, voir `_entete`)
        self._points_cle: tuple | None = None
        self.deux_colonnes = False
        # pages (onglets) : chaque bloc appartient à la page en construction (« » : toutes les pages, ex. le pied)
        self.pages: list[str] = []                         # page de chaque bloc (parallèle à self.blocs)
        self.page_construction = "jeu"
        self.page = "jeu"
        self.b_onglets: dict[str, Pilule] = {}
        # sous-onglets d'une page (onglet « Réglages ») : blocs de la page « <page>/<sous-page> », visibles quand la
        # page est affichée et que cette sous-page y est choisie ; rangée de pilules sous la barre d'onglets
        self.b_sous: dict[str, dict[str, Pilule]] = {}
        self.sous_page: dict[str, str] = {}
        self.c.bind("<Configure>", lambda _e: self.planifier())
        racine.bind("<MouseWheel>", self._molette, add="+")

    # -- construction
    def entete(self, titre: str, sous_titre: str, texte_langue: str, commande) -> Pilule:
        self.titre, self.sous_titre = titre, insecables(sous_titre)
        self.b_langue = Pilule(self.c, self.th, texte_langue, commande, genre="clair", fond=ROUGE,
                               police="bouton_petit", padx=12, pady=3)
        return self.b_langue

    def carte(self, titre: str, colonne: str = "g") -> tk.Frame:
        """Nouvelle carte ; renvoie le cadre du contenu (grille : 0 pastille, 1 texte extensible, 2 bouton)."""
        numero, nom = separer_numero(titre)
        f = tk.Frame(self.c, bg=BLANC)
        tete = tk.Frame(f, bg=BLANC)
        tete.pack(fill="x")
        Badge(tete, self.th, numero).pack(side="left")
        tk.Label(tete, text=nom, font=self.th["carte"], bg=BLANC, fg=NOIR).pack(side="left", padx=(self.th.px(8), 0))
        corps = tk.Frame(f, bg=BLANC)
        corps.pack(fill="x", pady=(self.th.px(4), 0))
        corps.columnconfigure(1, weight=1)
        self._carte = f
        self._ajouter("carte", colonne, f)
        return corps

    def centre(self, widget: tk.Widget, colonne: str = "d") -> None:
        self._ajouter("centre", colonne, widget)

    def pied(self, boutons: list[tk.Widget], variable: tk.StringVar) -> None:
        self.pied_var = variable
        variable.trace_add("write", lambda *_: self.planifier())
        page, self.page_construction = self.page_construction, ""
        self._ajouter("pied", "", boutons)
        self.page_construction = page

    def onglets(self, onglets: list[tuple[str, str]], commande: Callable[[str], object]) -> dict[str, Pilule]:
        """Barre d'onglets sous le bandeau : une pilule par (clé, texte) ; l'onglet choisi est rouge. `commande(clé)`
        est appelée au clic (ou Entrée / Espace). Les blocs créés ensuite vont dans la page `page_construction`."""
        for cle, texte in onglets:
            self.b_onglets[cle] = Pilule(self.c, self.th, texte, lambda k=cle: commande(k), fond=FOND,
                                         padx=20, pady=4)
        self._maj_onglets()
        return self.b_onglets

    def sous_onglets(self, page: str, onglets: list[tuple[str, str]], commande: Callable[[str], object],
                     choisi: str | None = None) -> dict[str, Pilule]:
        """Sous-onglets de la page `page` : une pilule par (clé, texte), sur une rangée sous la barre d'onglets, montrée
        seulement quand `page` est affichée ; `commande(clé)` au clic. Les blocs construits avec `page_construction` =
        « <page>/<clé> » ne sont visibles que dans ce sous-onglet ; `choisi` : sous-onglet de départ (défaut : le
        premier)."""
        b = self.b_sous[page] = {}
        for cle, texte in onglets:
            b[cle] = Pilule(self.c, self.th, texte, lambda k=cle: commande(k), fond=FOND, police="bouton_petit",
                            padx=14, pady=3)
        cles = [cle for cle, _t in onglets]
        self.sous_page[page] = choisi if choisi in cles else cles[0]
        self._maj_onglets()
        return b

    def montrer_sous(self, page: str, sous: str) -> None:
        """Choisit le sous-onglet `sous` de la page `page` (blocs des autres sous-onglets masqués, pas détruits)."""
        self.sous_page[page] = sous
        self._maj_onglets()
        self.planifier()

    def plein(self, widget: tk.Widget) -> None:
        """Carte pleine largeur étirée jusqu'au pied (onglet « Yo-kai ») ; `widget` : cadre blanc du contenu."""
        self._ajouter("plein", "", widget)

    def montrer(self, page: str) -> None:
        """Affiche la page `page` (les blocs des autres pages sont masqués, pas détruits)."""
        self.page = page
        self._maj_onglets()
        self.planifier()

    def _maj_onglets(self) -> None:
        for cle, b in self.b_onglets.items():
            genre = "onglet" if cle == self.page else "normal"
            if b.genre != genre:
                b.changer_genre(genre)
        for page, boutons in self.b_sous.items():
            for cle, b in boutons.items():
                genre = "onglet" if cle == self.sous_page.get(page) else "normal"
                if b.genre != genre:
                    b.changer_genre(genre)

    def _visible(self, i: int) -> bool:
        p = self.pages[i]
        return p in ("", self.page) or (self.page in self.sous_page and p == f"{self.page}/{self.sous_page[self.page]}")

    def texte_extensible(self, widget: tk.Widget, reserve: int) -> None:
        """`widget` (Label ou LabelChemin) de la dernière carte créée : largeur de la carte moins `reserve`."""
        self.textes.append((widget, reserve, self._carte))

    def _ajouter(self, genre: str, colonne: str, objet) -> None:
        self.blocs.append((genre, colonne, objet))
        self.pages.append(self.page_construction)
        for w in (objet if isinstance(objet, list) else [objet]):
            w.bind("<Configure>", lambda _e: self.planifier(), add="+")

    # -- mise en page
    def planifier(self) -> None:
        if not self._prevu:
            self._prevu = True
            self.c.after_idle(self.disposer)

    def _fenetre(self, cle: str, widget: tk.Widget, x, y, **kw) -> None:
        if cle in self.fenetres:
            self.c.coords(self.fenetres[cle], x, y)
            self.c.itemconfigure(self.fenetres[cle], state="normal", **kw)
        else:
            self.fenetres[cle] = self.c.create_window(x, y, window=widget, **kw)

    def _masquer(self, i: int) -> None:
        """Masque les fenêtres du bloc `i` (page non affichée)."""
        for cle, ident in self.fenetres.items():
            if cle == f"b{i}" or cle.startswith(f"b{i}_"):
                self.c.itemconfigure(ident, state="hidden")

    def _entete(self, W: int) -> int:
        """Bandeau rouge (rayons, emblème, titre détouré, sous-titre), fond à points ; renvoie le y du contenu."""
        c, th, px = self.c, self.th, self.th.px
        marge = px(20)
        R = px(30)
        cx = marge + R + px(2)
        tx = cx + R + px(20)
        lw = self.b_langue.winfo_reqwidth() if self.b_langue else 0
        largeur_titre = max(px(160), W - tx - lw - marge - px(8))
        police = th["titre"] if th["titre"].measure(self.titre) <= largeur_titre else th["titre_etroit"]
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2), (3, 3)):
            c.create_text(tx + px(dx), px(dy), text=self.titre, font=police, fill=NOIR, anchor="nw",
                          width=largeur_titre, tags=("decor", "titre"))
        t = c.create_text(tx, 0, text=self.titre, font=police, fill=BLANC, anchor="nw", width=largeur_titre,
                          tags=("decor", "titre"))
        tb = c.bbox(t)
        s = c.create_text(tx, tb[3] + px(3), text=self.sous_titre, font=th["sous_titre"], fill=BLANC, anchor="nw",
                          width=max(px(160), W - tx - marge), tags=("decor", "titre"))
        sb = c.bbox(s)
        haut_textes = sb[3] - tb[1]
        bande = max(2 * R + 2 * px(14), haut_textes + 2 * px(13))
        c.move("titre", 0, (bande - haut_textes) / 2 - tb[1] + px(1))
        cy = bande / 2
        if self.b_langue:
            self._fenetre("langue", self.b_langue, W - marge + px(6), px(10), anchor="ne")

        c.create_rectangle(0, 0, W, bande, fill=ROUGE, outline="", tags="decor")
        L, n = W * 2, 20
        for i in range(0, n * 2, 2):
            a0, a1 = math.radians(i * 180 / n), math.radians((i + 1) * 180 / n)
            c.create_polygon(cx, cy, cx + L * math.cos(a0), cy + L * math.sin(a0), cx + L * math.cos(a1),
                             cy + L * math.sin(a1), fill=ROUGE_RAYON, outline="", tags="decor")
        bas = max(c.winfo_height(), self.hauteur, px(400)) + px(40)
        c.create_rectangle(0, bande, W, bas + px(400), fill=FOND, outline="", tags="decor")
        # points en réseau hexagonal : UNE image (refaite seulement quand la taille change), et non ~2 000 ovales
        # recréés à chaque mise en page (33 des 39 ms d'une mise en page, et autant d'appels Tcl : voir
        # `vue.priorite_interface`)
        p, rp = px(18), px(1.7)
        rangs = -(-len(range(bande + px(10), bas, p)) // 16) * 16     # par 16 rangées (le surplus est hors de vue)
        if rangs > 0 and W > 0:
            cle = (W, rangs, p, rp, px(6))
            if self._points_cle != cle:
                try:
                    self._points, self._points_cle = image_points(c, W, rangs, p, rp, px(6)), cle
                except tk.TclError:
                    self._points = self._points_cle = None
            if self._points is not None:
                c.create_image(0, bande + px(10) - rp, image=self._points, anchor="nw", tags="decor")
        e = px(6)                                                     # liseré or sous le bandeau
        c.create_rectangle(0, bande, W, bande + e, fill=OR, outline="", tags="decor")
        c.create_line(0, bande, W, bande, fill=NOIR, width=px(3), tags="decor")
        c.create_line(0, bande + e, W, bande + e, fill=NOIR, width=px(2), tags="decor")
        if self.embleme is not None:
            o = px(3)
            r = self.embleme.width() / 2
            c.create_oval(cx - r + o, cy - r + o, cx + r + o, cy + r + o, fill=ROUGE_SOMBRE, outline="",
                          tags="decor")
            c.create_image(cx, cy, image=self.embleme, tags="decor")
        else:
            dessiner_embleme(c, cx, cy, R, px, "decor")
        c.tag_raise("titre")
        return bande + e + px(16)

    def _carte_dessin(self, cle: str, f: tk.Widget, x1: int, x2: int, y: int, h: int) -> int:
        """Carte (ombre, fond blanc, contour noir) autour du cadre `f` de hauteur `h` ; renvoie le bas."""
        c, px = self.c, self.th.px
        pad = px(12)
        y2 = y + h + 2 * pad
        o = px(5)
        rond_rect(c, x1 + o, y + o, x2 + o, y2 + o, px(18), fill=OMBRE_CARTE, outline="", tags="decor")
        rond_rect(c, x1, y, x2, y2, px(18), fill=BLANC, outline=NOIR, width=px(3), tags="decor")
        self._fenetre(cle, f, x1 + pad, y + pad, anchor="nw", width=x2 - x1 - 2 * pad, height=h)
        return y2

    def disposer(self) -> None:
        self._prevu = False
        c, th, px = self.c, self.th, self.th.px
        try:
            W = c.winfo_width()
        except tk.TclError:
            return
        if W <= 1:
            W = int(c["width"])
        c.delete("decor")
        marge, pad, gap = px(20), px(12), px(12)
        deux = self.deux_colonnes = W >= px(self.LARGEUR_DEUX_COLONNES)
        y0 = self._entete(W)
        if self.b_onglets:                                            # barre d'onglets
            x, h = marge - px(3), 0
            for cle, b in self.b_onglets.items():
                self._fenetre("onglet_" + cle, b, x, y0 - px(6), anchor="nw")
                x += b.winfo_reqwidth() + px(2)
                h = max(h, b.winfo_reqheight())
            y0 += h + px(4)
        for page, boutons in self.b_sous.items():                     # sous-onglets de la page affichée
            if page != self.page:
                for cle in boutons:
                    if f"sous_{page}_{cle}" in self.fenetres:
                        c.itemconfigure(self.fenetres[f"sous_{page}_{cle}"], state="hidden")
                continue
            x, h = marge + px(4), 0
            for cle, b in boutons.items():
                self._fenetre(f"sous_{page}_{cle}", b, x, y0, anchor="nw")
                x += b.winfo_reqwidth() + px(2)
                h = max(h, b.winfo_reqheight())
            y0 += h + px(12)
        for i in range(len(self.blocs)):
            if not self._visible(i):
                self._masquer(i)
        visibles = [i for i in range(len(self.blocs)) if self._visible(i)]
        plein = [i for i in visibles if self.blocs[i][0] == "plein"]

        # colonnes : bornes x de chaque colonne
        if deux:
            milieu = marge + round((W - 2 * marge - gap) * 0.56)
            cols = {"g": (marge, milieu), "d": (milieu + gap, W - marge)}
        else:
            cols = {"g": (marge, W - marge), "d": (marge, W - marge)}
        for w, reserve, carte in self.textes:                         # largeur des textes avant les hauteurs
            col = next((k for g, k, o in self.blocs if o is carte), "g")
            x1, x2 = cols.get(col, (marge, W - marge))
            lg = max(px(120), x2 - x1 - 2 * pad - reserve)
            try:
                if isinstance(w, LabelChemin):
                    w.fixer_largeur(lg)
                else:
                    w.configure(wraplength=lg)
            except tk.TclError:
                pass

        def hauteur(o):
            return o.winfo_reqheight()

        y = y0
        pied = [(i, o) for i, (g, k, o) in enumerate(self.blocs) if g == "pied" and self._visible(i)]
        h_pied = max((b.winfo_reqheight() for _i, o in pied for b in o), default=0)
        if plein:
            # carte pleine largeur étirée jusqu'au pied (au moins sa hauteur demandée : défilement sinon)
            try:
                h_vis = c.winfo_height() if c.winfo_height() > 1 else int(c["height"])
            except tk.TclError:
                h_vis = 0
            for i in plein:
                o = self.blocs[i][2]
                h = max(hauteur(o), h_vis - y - 2 * pad - gap - h_pied - px(8))
                y = self._carte_dessin(f"b{i}", o, marge, W - marge, y, h) + gap
        elif not deux:
            for i, (genre, col, obj) in enumerate(self.blocs):
                if not self._visible(i):
                    continue
                if genre == "carte":
                    y = self._carte_dessin(f"b{i}", obj, marge, W - marge, y, hauteur(obj)) + gap
                elif genre == "centre":
                    self._fenetre(f"b{i}", obj, W / 2, y, anchor="n")
                    y += hauteur(obj) + gap
        else:
            gauche = [(i, o) for i, (g, k, o) in enumerate(self.blocs) if k == "g" and g == "carte" and i in visibles]
            cartes_d = [(i, o) for i, (g, k, o) in enumerate(self.blocs) if k == "d" and g == "carte" and i in visibles]
            boutons_d = [(i, o) for i, (g, k, o) in enumerate(self.blocs) if k == "d" and g == "centre"
                         and i in visibles]
            yg = y0
            for i, o in gauche:
                yg = self._carte_dessin(f"b{i}", o, *cols["g"], yg, hauteur(o)) + gap
            bas_g = yg - gap
            h_boutons = sum(hauteur(o) + gap for _i, o in boutons_d)
            yd = y0
            for n, (i, o) in enumerate(cartes_d):
                h = hauteur(o)
                if n == len(cartes_d) - 1:                            # dernière carte étirée jusqu'aux boutons
                    h = max(h, bas_g - h_boutons - yd - 2 * pad - px(4))
                yd = self._carte_dessin(f"b{i}", o, *cols["d"], yd, h) + gap
            yd = max(yd, bas_g - h_boutons + gap + px(4))
            x1, x2 = cols["d"]
            for i, o in boutons_d:
                self._fenetre(f"b{i}", o, (x1 + x2) / 2, yd - px(2), anchor="n")
                yd += hauteur(o) + gap
            y = max(yg, yd)
        for i, obj in pied:
            x, h = marge - px(3), 0
            for k, b in enumerate(obj):
                self._fenetre(f"b{i}_{k}", b, x, y - px(4), anchor="nw")
                x += b.winfo_reqwidth() + px(4)
                h = max(h, b.winfo_reqheight())
            if self.pied_var is not None:
                t = c.create_text(W - marge, y - px(4) + h / 2, text=self.pied_var.get(), font=th["petit"],
                                  fill=TEXTE_DOUX, anchor="e", tags="decor")
                b = c.bbox(t)
                if b:
                    fond = c.create_rectangle(b[0] - px(6), b[1] - px(2), b[2] + px(6), b[3] + px(2), fill=FOND,
                                              outline="", tags="decor")
                    c.tag_lower(fond, t)
            y += h
        self.hauteur = y + px(6)
        c.configure(scrollregion=(0, 0, W, max(self.hauteur, c.winfo_height())))
        self._ajuster_hauteur(grandir_seulement=bool(plein))

    def _ajuster_hauteur(self, grandir_seulement: bool = False) -> None:
        """Tant que le joueur n'a pas changé la hauteur de la fenêtre, elle suit celle du contenu (bornée par
        l'écran) ; barre de défilement si le contenu dépasse. Page à carte pleine (`grandir_seulement`) : la
        fenêtre ne rétrécit pas (pas de saut de taille en changeant d'onglet)."""
        r = self.r
        try:
            h_actuelle = r.winfo_height()
            voulue = max(min(self.hauteur, r.winfo_screenheight() - self.th.px(90)), r.minsize()[1])
            if grandir_seulement and h_actuelle > 1:
                voulue = max(voulue, h_actuelle)
            # hauteur visible = celle de la FENÊTRE (le canevas en occupe toute la hauteur, mais ne la prend qu'un
            # tour de boucle après elle)
            h_visible = h_actuelle if h_actuelle > 1 else voulue
            if h_actuelle in self._demandees and voulue != h_actuelle:
                largeur = r.winfo_width() if r.winfo_width() > 1 else int(self.c["width"])
                r.geometry(f"{largeur}x{voulue}")
                self._demandees.add(voulue)
                # la barre se décide sur la hauteur DEMANDÉE (le canevas occupe toute la fenêtre), pas sur l'ancienne :
                # sinon elle apparaissait un tour (contenu > ancienne hauteur), rétrécissait le canevas, changeait les
                # retours à la ligne donc la hauteur, puis disparaissait au tour suivant... (17 mises en page et
                # ~0,5 s de fenêtre qui se cherche à l'ouverture, 6 à chaque changement d'onglet)
                h_visible = voulue
            if self.hauteur > h_visible + 2:
                self.defil.grid(row=0, column=1, sticky="ns")
            else:
                self.defil.grid_remove()
                self.c.yview_moveto(0)
        except tk.TclError:
            pass

    def _molette(self, e) -> None:
        try:
            if self.hauteur > self.c.winfo_height():
                self.c.yview_scroll(int(-e.delta / 120), "units")
        except tk.TclError:
            pass
