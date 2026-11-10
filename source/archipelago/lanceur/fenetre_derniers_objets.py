"""Fenêtre des derniers objets reçus et envoyés (option du lanceur, désactivée par défaut ;
docs/systemes/archipelago_fenetre_derniers_objets.md).

Case : onglet « Réglages » → « Paramètres du jeu » du lanceur (avec Azahar comme avec Zakuro), avec le délai
d'effacement. Une petite fenêtre sans bord, toujours au-dessus, semi-transparente et déplaçable, montre les derniers
objets de CE joueur : reçus (flèche verte, « de <joueur> »), envoyés (flèche bleue, « pour <joueur> ») et trouvés
dans son propre monde (point vert). Les objets de progression ressortent (étoile, gras, couleur « plum »
d'Archipelago) ; utiles et pièges ont la couleur d'Archipelago.

Disparition : CHAQUE LIGNE s'efface `delai` secondes après l'arrivée de l'objet (10 à 120 s, 20 par défaut), en
pâlissant pendant ses `PALIT` dernières secondes ; la fenêtre se cache dès qu'il n'y a plus de ligne. Choix : une
fenêtre qui se cache entière après le DERNIER objet resterait affichée indéfiniment pendant une série d'envois (une
fin de partie, un `!release`), et les plus vieux objets y resteraient aussi longtemps que les nouveaux ; ligne par
ligne, chaque objet a la même durée de vie, et la fenêtre ne coûte rien à l'écran quand rien n'arrive. Au plus
`NB_LIGNES` lignes, les plus récentes en haut, puis « + N autres » si d'autres objets récents ne tiennent pas.

Données : `derniers_objets.json`, écrit par le client (`client/derniers_objets.py`) d'après les PrintJSON ItemSend du
serveur, déjà filtrés sur ce joueur (les échanges entre deux autres joueurs n'y sont jamais) ; noms venus du serveur.
Seuls les objets arrivés pendant que le jeu était attaché au client sont montrés (la fenêtre est faite pour être
au-dessus du jeu : en suivi seul, rien ne s'affiche sur le bureau).

Mécanique de la fenêtre (jamais de focus : manette de Zakuro, clavier d'Azahar ; déplacement, mode discret des
essais) : celle de la fenêtre d'amitié (`fenetre_amitie.FenetreAmitie`), dont `FenetreObjets` hérite. Position
mémorisée dans `config.json` (`objets_fenetre_pos`, "x,y" ; défaut : coin haut DROIT, la fenêtre d'amitié étant au coin
haut gauche), délai dans `objets_fenetre_delai`.

Logique sans affichage (testable) : `lire_affichage` ; vue : `FenetreObjets` ; contrôleur : `Suivi`.
"""
from __future__ import annotations

import sys
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Callable

ARCHIPELAGO = Path(__file__).resolve().parents[1]
for _p in (ARCHIPELAGO, ARCHIPELAGO / "client"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import derniers_objets as DO  # noqa: E402  (client/ : fichier écrit par le client)

from . import fenetre_amitie as FA  # noqa: E402

PERIODE_MS = 400              # relecture de derniers_objets.json (stat seulement si rien n'a changé) et effacements
NB_LIGNES = 5                 # lignes d'objets montrées au plus
DELAIS = (10, 20, 30, 60, 120)
DELAI_DEFAUT = 20
PALIT = 3.0                   # s : la ligne pâlit pendant ses dernières secondes
AVANCE_MAX = 5.0              # s : un évènement daté du futur (horloge changée) au-delà est ignoré
NOM_MAX, JOUEUR_MAX = 34, 18  # caractères (largeur de la fenêtre bornée)
LARGEUR_DEFAUT = 330          # px : largeur supposée pour la position par défaut (coin haut droit)

TEXTES = {
    "fr": {"option": "Fenêtre des derniers objets", "titre": "Derniers objets", "de": "de {j}", "pour": "pour {j}",
           "trouve": "trouvé", "serveur": "du serveur", "autres": "+ {n} autre", "autres_n": "+ {n} autres",
           "delai": "Effacer chaque ligne après", "secondes": "{n} s",
           "aide": "Au-dessus du jeu, une petite fenêtre transparente montre les derniers objets reçus et envoyés, "
                   "pour ne pas rater un bandeau. Glissez-la pour la déplacer."},
    "en": {"option": "Recent items window", "titre": "Recent items", "de": "from {j}", "pour": "to {j}",
           "trouve": "found", "serveur": "from the server", "autres": "+ {n} more", "autres_n": "+ {n} more",
           "delai": "Clear each line after", "secondes": "{n} s",
           "aide": "Above the game, a small transparent window shows the latest items received and sent, so you do "
                   "not miss a banner. Drag it to move it."},
}


def texte(langue: str, cle: str, **p) -> str:
    t = TEXTES.get(langue) or TEXTES["fr"]
    return t[cle].format(**p) if p else t[cle]


def delai_valide(v) -> int:
    """Délai d'effacement ramené à une valeur proposée (défaut : `DELAI_DEFAUT`)."""
    try:
        v = int(v)
    except (TypeError, ValueError):
        return DELAI_DEFAUT
    return v if v in DELAIS else min(DELAIS, key=lambda d: (abs(d - v), d))


def _court(s: str, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def genre_flags(flags: int) -> str:
    """Genre d'un objet d'après NetworkItem.flags, comme le TextClient : progression d'abord."""
    flags = int(flags or 0)
    return "progression" if flags & 1 else "utile" if flags & 2 else "piege" if flags & 4 else "objet"


# ------------------------------------------------------------------------------------------------ logique
@dataclass(frozen=True)
class LigneObjet:
    sens: str              # "recu" / "envoye" / "trouve" ; "autres" : ligne de résumé
    objet: str             # nom de l'objet (ou « + N autres »)
    detail: str            # « de Bob » / « pour Alice » / « trouvé » ; "" pour le résumé
    genre: str             # "progression" / "utile" / "piege" / "objet"
    palit: bool = False    # dernières secondes de la ligne


def evenements_recents(d: dict | None, delai: float, maintenant: float | None = None) -> list[dict]:
    """Évènements encore à montrer (jeu attaché, moins de `delai` s), du plus récent au plus ancien."""
    if not d or not isinstance(d.get("evenements"), list):
        return []
    now = time.time() if maintenant is None else maintenant
    out = []
    for e in d["evenements"]:
        if not isinstance(e, dict) or e.get("sens") not in DO.SENS or not e.get("jeu"):
            continue
        t, n = e.get("t"), e.get("n")
        if not isinstance(t, (int, float)) or not isinstance(n, int) or not -AVANCE_MAX <= now - t < delai:
            continue
        out.append(e)
    out.sort(key=lambda e: e["n"], reverse=True)
    return out


def lire_affichage(d: dict | None, langue: str, delai: float = DELAI_DEFAUT,
                   maintenant: float | None = None) -> list[LigneObjet] | None:
    """Lignes à montrer d'après le contenu de `derniers_objets.json` ; None = fenêtre cachée (rien de récent)."""
    now = time.time() if maintenant is None else maintenant
    recents = evenements_recents(d, delai, now)
    if not recents:
        return None
    lignes = []
    for e in recents[:NB_LIGNES]:
        sens = e["sens"]
        if sens == "trouve":
            detail = texte(langue, "trouve")
        elif e.get("serveur"):
            detail = texte(langue, "serveur")
        else:
            detail = texte(langue, "de" if sens == "recu" else "pour", j=_court(e.get("joueur") or "?", JOUEUR_MAX))
        lignes.append(LigneObjet(sens, _court(e.get("objet") or "?", NOM_MAX), detail,
                                 genre_flags(e.get("flags") if isinstance(e.get("flags"), int) else 0),
                                 palit=delai - (now - e["t"]) <= PALIT))
    reste = len(recents) - NB_LIGNES
    if reste > 0:
        lignes.append(LigneObjet("autres", texte(langue, "autres" if reste == 1 else "autres_n", n=reste), "", "objet"))
    return lignes


def position_defaut(ecran: tuple[int, int]) -> str:
    """Coin haut droit de l'écran ("x,y"), la fenêtre d'amitié occupant le coin haut gauche."""
    return f"{max(0, ecran[0] - LARGEUR_DEFAUT - 24)},24"


# ------------------------------------------------------------------------------------------------ vue
VERT, BLEU, GRIS, PALE = FA.VERT, "#6FD3FF", FA.GRIS, "#8C837C"
COULEURS_GENRE = {"progression": "#DDA0DD", "utile": "#9DB0FF", "piege": "#FA8072", "objet": FA.TEXTE}
SIGNES = {"recu": ("↓", VERT), "envoye": ("↑", BLEU), "trouve": ("•", VERT), "autres": ("", GRIS)}


class FenetreObjets(FA.FenetreAmitie):
    """La petite fenêtre : mécanique de `FenetreAmitie` (sans bord, sans focus, déplaçable, discrète), trois colonnes
    (signe du sens, objet, joueur)."""

    def __init__(self, racine: tk.Misc, langue: str, pos: str = "",
                 memoriser: Callable[[int, int], None] | None = None, discret: bool = False):
        if not pos:
            pos = position_defaut((racine.winfo_screenwidth(), racine.winfo_screenheight()))
        super().__init__(racine, langue, pos, memoriser, discret)
        self.titre.configure(text=texte(langue, "titre"))
        self.titre.grid_configure(columnspan=3)
        self.objets: list[tuple[tk.Label, tk.Label, tk.Label]] = []

    def remplir(self, lignes: list[LigneObjet]) -> None:
        if lignes == self.contenu:
            return
        self.contenu = list(lignes)
        while len(self.objets) < len(lignes):
            r = len(self.objets) + 1
            s = tk.Label(self.cadre, bg=FA.FOND, font=("Segoe UI", 10, "bold"), anchor="w", width=2)
            a = tk.Label(self.cadre, bg=FA.FOND, anchor="w")
            b = tk.Label(self.cadre, bg=FA.FOND, fg=GRIS, font=("Segoe UI", 9), anchor="w")
            s.grid(row=r, column=0, sticky="w")
            a.grid(row=r, column=1, sticky="w", padx=(0, 10))
            b.grid(row=r, column=2, sticky="w")
            for w in (s, a, b):
                self._lier(w)
            self.objets.append((s, a, b))
        for i, (s, a, b) in enumerate(self.objets):
            if i >= len(lignes):
                for w in (s, a, b):
                    w.grid_remove()
                continue
            l = lignes[i]
            signe, couleur = SIGNES[l.sens]
            prog = l.genre == "progression" and l.sens != "autres"
            nom = ("★ " + l.objet) if prog else l.objet
            s.configure(text=signe, fg=PALE if l.palit else couleur)
            a.configure(text=nom, fg=PALE if l.palit else (GRIS if l.sens == "autres" else COULEURS_GENRE[l.genre]),
                        font=("Segoe UI", 10, "bold" if prog else "normal"))
            b.configure(text=l.detail, fg=PALE if l.palit else GRIS)
            for w in (s, a, b):
                w.grid()

    def changer_langue(self, langue: str) -> None:
        self.langue = langue
        self.titre.configure(text=texte(langue, "titre"))
        self.contenu = None


# ------------------------------------------------------------------------------------------------ lanceur
def case_option(parent: tk.Misc, theme, langue: str, variable: tk.BooleanVar, commande, delai: int,
                changer_delai: Callable[[int], None], ligne: int, scene=None) -> tk.Misc:
    """Case de l'option, son explication et le choix du délai dans la carte « Paramètres du jeu » de l'onglet
    « Réglages » (lignes `ligne` à `ligne` + 2 de la grille de la carte) : la vue n'a rien d'autre à construire."""
    from . import theme as th
    px = theme.px
    b = th.Bascule(parent, theme, texte(langue, "option"), variable, commande=commande)
    b.grid(row=ligne, column=0, columnspan=3, sticky="w", pady=(px(8), 0))
    aide = tk.Label(parent, text=texte(langue, "aide"), font=theme["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                    justify="left", anchor="w")
    aide.grid(row=ligne + 1, column=0, columnspan=3, sticky="w", padx=(px(28), 0), pady=(0, px(2)))
    if scene is not None:
        scene.texte_extensible(aide, px(32))
    rang = tk.Frame(parent, bg=th.BLANC)
    rang.grid(row=ligne + 2, column=0, columnspan=3, sticky="w", padx=(px(28), 0), pady=(px(2), px(2)))
    tk.Label(rang, text=texte(langue, "delai"), font=theme["petit"], bg=th.BLANC, fg=th.TEXTE,
             anchor="w").pack(side="left", padx=(0, px(8)))
    th.styler_ttk(parent.winfo_toplevel(), theme)
    libelles = [texte(langue, "secondes", n=d) for d in DELAIS]
    var = tk.StringVar(parent, value=texte(langue, "secondes", n=delai_valide(delai)))
    cb = ttk.Combobox(rang, state="readonly", style="Yokai.TCombobox", font=theme["petit"], textvariable=var,
                      values=libelles, width=max(len(x) for x in libelles) + 2)
    cb.pack(side="left")
    cb.bind("<<ComboboxSelected>>", lambda _e: changer_delai(DELAIS[libelles.index(var.get())]))
    b.liste_delai = cb                                      # tests
    return b


# ------------------------------------------------------------------------------------------------ contrôleur
class Suivi:
    """Relit `derniers_objets.json` toutes les PERIODE_MS (stat seulement si rien n'a changé), efface les lignes
    trop anciennes et montre / cache la fenêtre. Rien n'est créé tant que l'option est décochée."""

    def __init__(self, racine: tk.Misc, dossier: str | Path, langue: str, actif: bool = False, pos: str = "",
                 delai: int = DELAI_DEFAUT, memoriser_pos: Callable[[int, int], None] | None = None,
                 discret: bool = False, auto: bool = True, horloge: Callable[[], float] = time.time):
        self.racine, self.dossier, self.langue = racine, Path(dossier), langue
        self.actif, self.pos, self.memoriser_pos, self.discret = bool(actif), pos, memoriser_pos, discret
        self.delai = delai_valide(delai)
        self.horloge = horloge
        self.fenetre: FenetreObjets | None = None
        self.au_dessus: Callable[[], int] | None = None    # HWND du lanceur « au premier plan » (premier_plan.py)
        self._sig = None
        self._donnees: dict | None = None
        self._apres = None
        if auto:                                             # tests : `tour()` appelé à la main
            self._planifier()

    def _planifier(self) -> None:
        try:
            self._apres = self.racine.after(PERIODE_MS, self.tour)
        except tk.TclError:
            self._apres = None

    def _signature(self):
        try:
            st = (self.dossier / DO.NOM_FICHIER).stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _memoriser(self, x: int, y: int) -> None:
        self.pos = f"{x},{y}"
        if self.memoriser_pos is not None:
            self.memoriser_pos(x, y)

    def activer(self, actif: bool) -> None:
        self.actif = bool(actif)
        if not self.actif and self._fenetre_vivante() is not None:
            self.fenetre.cacher()

    def changer_delai(self, delai: int) -> None:
        self.delai = delai_valide(delai)

    def _fenetre_vivante(self) -> FenetreObjets | None:
        # la vue du lanceur détruit tous les enfants de la racine quand elle se reconstruit (changement de langue) :
        # la fenêtre est alors refaite au prochain affichage
        if self.fenetre is not None and not self.fenetre.existe():
            self.fenetre = None
        return self.fenetre

    def changer_langue(self, langue: str) -> None:
        self.langue = langue
        if self._fenetre_vivante() is not None:
            self.fenetre.changer_langue(langue)

    def tour(self) -> list[LigneObjet] | None:
        """Un passage (appelé par `after`, ou directement par les tests) ; rend les lignes montrées (None : cachée)."""
        lignes = None
        try:
            if self.actif:
                sig = self._signature()
                if sig != self._sig:
                    self._sig, self._donnees = sig, DO.lire(self.dossier)
                lignes = lire_affichage(self._donnees, self.langue, self.delai, self.horloge())
            self._fenetre_vivante()
            if lignes is None:
                if self.fenetre is not None:
                    self.fenetre.cacher()
            else:
                if self.fenetre is None:
                    self.fenetre = FenetreObjets(self.racine, self.langue, self.pos, self._memoriser, self.discret)
                self.fenetre.remplir(lignes)
                self.fenetre.montrer()
                if self.au_dessus is not None:
                    self.fenetre.relever(self.au_dessus())
        finally:
            if self._apres is not None:
                self._planifier()
        return lignes

    def arreter(self) -> None:
        if self._apres is not None:
            try:
                self.racine.after_cancel(self._apres)
            except tk.TclError:
                pass
            self._apres = None
        if self.fenetre is not None:
            self.fenetre.detruire()
            self.fenetre = None
