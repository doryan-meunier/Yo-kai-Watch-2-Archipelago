"""Garder le lanceur au premier plan (option du lanceur, décochée par défaut ; README du lanceur, « Garder le lanceur au
premier plan »).

Case : onglet « Réglages » → « Paramètres du jeu ». Cochée, la fenêtre principale du lanceur est « toujours au-dessus »
(`wm attributes -topmost` de Tk) : elle reste visible au-dessus du jeu en fenêtre (Azahar, Zakuro). Effet immédiat,
mémorisé dans `config.json` (`premier_plan`, relire-modifier-écrire sous le verrou, comme `amitie_fenetre`) et
réappliqué au démarrage. Le changement de langue reconstruit le contenu de la fenêtre, pas la racine : l'attribut et
la variable de la case restent.

Focus : cocher ou décocher ne prend jamais le focus au jeu. Seul `-topmost` est posé (aucun `focus_force`, `lift`,
`deiconify`) ; vérifié sous Windows avec Tk 8.6.15 : l'attribut ne recrée pas le cadre Windows de la fenêtre, ne
l'active pas (ni au premier plan, ni comme fenêtre active de son fil) et ne montre pas une fenêtre retirée.

Fenêtres transparentes (amitié en combat, derniers objets) : elles sont « toujours au-dessus » elles aussi ; Windows
range au sommet de la bande « au-dessus » la dernière fenêtre posée ou activée, donc le lanceur passerait devant elles
quand on coche la case ou qu'on clique dans le lanceur. Leurs contrôleurs (`Suivi`) les relèvent donc sans activation
(`FenetreAmitie.relever` : SetWindowPos(HWND_TOPMOST, SWP_NOACTIVATE), seulement si le lanceur est au-dessus d'elles)
à chaque passage (400 ms), et tout de suite quand la case est cochée.

Boîtes de dialogue : toutes celles du lanceur (messagebox, choix de fichier) ont la racine pour parent ; Windows les
crée alors POSSÉDÉES par la fenêtre du lanceur, et une fenêtre possédée reste toujours au-dessus de sa propriétaire
(et devient « au-dessus » avec elle) : elles ne se cachent pas derrière. Les listes déroulantes ttk (fenêtre transitoire
et `-topmost`) et les infobulles de la carte (`-topmost`, créées après) aussi. Un test vérifie que chaque appel de
messagebox / filedialog du lanceur passe `parent=`.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable

from . import fenetre_amitie as FA

TEXTES = {
    "fr": {"option": "Garder le lanceur au premier plan",
           "aide": "La fenêtre du lanceur reste au-dessus des autres fenêtres, y compris du jeu en fenêtre. Le jeu "
                   "garde la main : cocher ou décocher ne lui prend ni le clavier ni la manette."},
    "en": {"option": "Keep the launcher on top",
           "aide": "The launcher window stays above other windows, including the game when it runs in a window. The "
                   "game keeps control: checking or unchecking does not take the keyboard or the controller away "
                   "from it."},
}


def texte(langue: str, cle: str) -> str:
    return (TEXTES.get(langue) or TEXTES["fr"])[cle]


def est_au_dessus(racine: tk.Misc) -> bool:
    """Attribut `-topmost` actuel de la fenêtre (False si Tk refuse)."""
    try:
        return bool(int(racine.attributes("-topmost")))
    except (tk.TclError, ValueError):
        return False


def appliquer(racine: tk.Misc, actif: bool) -> bool:
    """Pose `-topmost` sur la fenêtre si sa valeur change ; rien d'autre (pas de lift, focus ni deiconify : le jeu
    garde le focus). Renvoie True si l'attribut a été changé."""
    actif = bool(actif)
    if est_au_dessus(racine) == actif:
        return False
    try:
        racine.attributes("-topmost", actif)
    except tk.TclError:
        return False
    return True


def cadre(racine: tk.Misc) -> int:
    """HWND du cadre Windows de la fenêtre (0 hors Windows ou si Tk ne le donne pas)."""
    if FA._user32 is None:
        return 0
    try:
        return int(racine.wm_frame(), 16)
    except (tk.TclError, ValueError):
        return 0


class PremierPlan:
    """Réglage « Garder le lanceur au premier plan » de la fenêtre `racine` du lanceur `lanceur` : variable de la
    case, application immédiate, mémorisation et relève des fenêtres transparentes (`suivis` : contrôleurs `Suivi` de
    fenetre_amitie / fenetre_derniers_objets, qui reçoivent `au_dessus`)."""

    def __init__(self, racine: tk.Misc, lanceur, suivis: Iterable = (),
                 memoriser: Callable[..., None] | None = None):
        self.racine, self.l = racine, lanceur
        self.suivis = list(suivis)
        self.memoriser = memoriser or (lambda **c: FA.memoriser(lanceur, **c))
        self.var = tk.BooleanVar(racine, value=bool(getattr(lanceur.config, "premier_plan", False)))
        self._hwnd = 0
        for s in self.suivis:
            s.au_dessus = self.au_dessus
        appliquer(racine, self.var.get())                   # démarrage : réglage mémorisé réappliqué

    def au_dessus(self) -> int:
        """HWND du lanceur quand il est « toujours au-dessus » (les fenêtres transparentes doivent rester devant
        lui), 0 sinon."""
        if not self.var.get():
            return 0
        if not self._hwnd:
            self._hwnd = cadre(self.racine)
        return self._hwnd

    def basculer(self) -> None:
        """Case cochée ou décochée : mémorisée, appliquée tout de suite, fenêtres transparentes relevées."""
        actif = bool(self.var.get())
        self.memoriser(premier_plan=actif)
        appliquer(self.racine, actif)
        self.relever()

    def relever(self) -> None:
        h = self.au_dessus()
        if not h:
            return
        for s in self.suivis:
            f = s._fenetre_vivante()
            if f is not None:
                f.relever(h)

    def case_option(self, parent: tk.Misc, theme, langue: str, ligne: int, scene=None) -> tk.Misc:
        """Case et explication dans la carte « Paramètres du jeu » (lignes `ligne` et `ligne` + 1 de la grille)."""
        from . import theme as th
        px = theme.px
        b = th.Bascule(parent, theme, texte(langue, "option"), self.var, commande=self.basculer)
        b.grid(row=ligne, column=0, columnspan=3, sticky="w", pady=(px(8), 0))
        aide = tk.Label(parent, text=texte(langue, "aide"), font=theme["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                        justify="left", anchor="w")
        aide.grid(row=ligne + 1, column=0, columnspan=3, sticky="w", padx=(px(28), 0), pady=(0, px(2)))
        if scene is not None:
            scene.texte_extensible(aide, px(32))
        return b
