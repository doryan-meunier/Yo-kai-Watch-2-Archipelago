"""Fenêtre d'amitié en combat (option du lanceur, désactivée par défaut ; docs/systemes/archipelago_fenetre_amitie.md).

Case : onglet « Réglages » → « Paramètres du jeu » du lanceur (avec Azahar comme avec Zakuro).
Pendant un combat, une petite fenêtre sans bord, toujours au-dessus, semi-transparente et déplaçable, montre pour
chaque Yo-kai ennemi son nom et « Ami » / « Pas encore ami » (bit « ami » du Médaillium de la sauvegarde chargée).
Elle est cachée hors combat, quand l'option est décochée, sans jeu, ou si le client ne donne plus de nouvelles.

Données : `amis_combat.json`, écrit par le client (`client/amis_combat.py`) d'après ce que le jeu publie
(`docs/systemes/archipelago_boite.md` §53). Noms : base locale `yokai_local.json` générée chez le joueur depuis SA ROM
(`especes[<hachage CHARA_PARAM>].noms`), jamais de texte du jeu dans le code ni dans git (règle 6) ; sans base : le n°
du Médaillium.

La fenêtre ne doit JAMAIS prendre le focus au jeu (manette de Zakuro, clavier d'Azahar) : sans bordure
(`overrideredirect`, jamais activée par Windows à l'affichage), styles étendus WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
(un clic pour la déplacer ne l'active pas, pas de bouton dans la barre des tâches), affichée et cachée par
`ShowWindow(SW_SHOWNOACTIVATE / SW_HIDE)` sous Windows, aucun `focus_set`. La position est mémorisée dans
`config.json` (`amitie_fenetre_pos`, "x,y") au relâchement du déplacement.

Logique sans affichage (testable) : `lire_affichage`, `NomsLocaux` ; vue : `FenetreAmitie` ; contrôleur : `Suivi`.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ARCHIPELAGO = Path(__file__).resolve().parents[1]
for _p in (ARCHIPELAGO, ARCHIPELAGO / "client"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import amis_combat as AMC  # noqa: E402  (client/ : fichier écrit par le client)

NOM_BASE = "yokai_local.json"
PERIODE_MS = 400              # relecture de amis_combat.json (stat seulement si rien n'a changé)
ALPHA = 0.86                  # opacité de la fenêtre
POSITION_DEFAUT = (24, 24)    # coin haut gauche de l'écran

TEXTES = {
    "fr": {"option": "Fenêtre d'amitié en combat", "titre": "Amitié", "ami": "Ami", "pas_ami": "Pas encore ami",
           "inconnu": "?", "numero": "Yo-kai n° {n}", "inconnue": "Yo-kai inconnu",
           "aide": "Pendant un combat, une petite fenêtre transparente indique pour chaque Yo-kai ennemi s'il est déjà "
                   "votre ami (Médaillium). Glissez-la pour la déplacer."},
    "en": {"option": "Friendship window in battle", "titre": "Friendship", "ami": "Friend", "pas_ami": "Not a friend yet",
           "inconnu": "?", "numero": "Yo-kai No. {n}", "inconnue": "Unknown Yo-kai",
           "aide": "During a battle, a small transparent window shows for each enemy Yo-kai whether it is already your "
                   "friend (Medallium). Drag it to move it."},
}


def texte(langue: str, cle: str, **p) -> str:
    t = TEXTES.get(langue) or TEXTES["fr"]
    return t[cle].format(**p) if p else t[cle]


# ------------------------------------------------------------------------------------------------ logique
class NomsLocaux:
    """Noms des espèces depuis `yokai_local.json` (base du joueur, chargée une fois par version du fichier, dans un
    fil de fond : le fichier pèse plusieurs Mo). `nom(param, langue)` : None tant que la base n'est pas prête."""

    def __init__(self, dossier: str | Path, synchrone: bool = False):
        self.fichier = Path(dossier) / NOM_BASE
        self.synchrone = synchrone
        self._sig = None
        self._noms: dict[int, dict[str, str]] = {}
        self._fil: threading.Thread | None = None

    def _signature(self):
        try:
            st = self.fichier.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _charger(self, sig) -> None:
        noms: dict[int, dict[str, str]] = {}
        try:
            base = json.loads(self.fichier.read_text(encoding="utf-8"))
            for p, info in (base.get("especes") or {}).items():
                n = info.get("noms") if isinstance(info, dict) else None
                if str(p).isdigit() and isinstance(n, dict):
                    noms[int(p)] = {lg: v for lg, v in n.items() if isinstance(v, str) and v}
        except (OSError, ValueError, AttributeError):
            noms = {}
        self._noms, self._sig = noms, sig

    def preparer(self) -> None:
        sig = self._signature()
        if sig is None or sig == self._sig or (self._fil is not None and self._fil.is_alive()):
            return
        if self.synchrone:
            self._charger(sig)
            return
        self._fil = threading.Thread(target=self._charger, args=(sig,), daemon=True, name="noms-amitie")
        self._fil.start()

    def nom(self, param: int, langue: str) -> str | None:
        n = self._noms.get(int(param))
        if not n:
            return None
        lg = "engb" if langue == "en" else "fr"
        return n.get(lg) or next(iter(n.values()), None)


@dataclass(frozen=True)
class Ligne:
    nom: str
    statut: str            # "ami" / "pas_ami" / "inconnu"


def lire_affichage(d: dict | None, langue: str, noms: NomsLocaux | None = None,
                   maintenant: float | None = None) -> list[Ligne] | None:
    """Lignes à montrer d'après le contenu de `amis_combat.json` ; None = fenêtre cachée (pas de combat, pas de jeu,
    patch sans la liste, fichier trop ancien ou vide)."""
    if not d or not d.get("publie") or not d.get("combat"):
        return None
    h = d.get("horodatage")
    if not isinstance(h, (int, float)) or abs((time.time() if maintenant is None else maintenant) - h) > AMC.AGE_MAX:
        return None
    lignes = []
    for e in d.get("ennemis") or ():
        if not isinstance(e, dict) or not isinstance(e.get("param"), int):
            continue
        nom = noms.nom(e["param"], langue) if noms is not None else None
        if not nom:
            m = e.get("medaille")
            nom = texte(langue, "numero", n=m) if isinstance(m, int) and m > 0 else texte(langue, "inconnue")
        a = e.get("ami")
        lignes.append(Ligne(nom, "ami" if a is True else "pas_ami" if a is False else "inconnu"))
    return lignes or None


def position(texte_pos: str, ecran: tuple[int, int], taille: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """Position mémorisée ("x,y") ramenée dans l'écran ; défaut : coin haut gauche."""
    try:
        x, y = (int(v) for v in str(texte_pos).split(","))
    except ValueError:
        x, y = POSITION_DEFAUT
    lw, lh = ecran
    x = max(0, min(x, max(0, lw - max(taille[0], 40))))
    y = max(0, min(y, max(0, lh - max(taille[1], 20))))
    return x, y


# ------------------------------------------------------------------------------------------------ vue
FOND, CONTOUR, TEXTE, VERT, ORANGE, GRIS = "#1B1416", "#FFC21A", "#FFFFFF", "#7CE38B", "#FFB04A", "#BDB3AA"

if os.name == "nt":
    import ctypes
    from ctypes import c_int, c_long, c_uint, c_void_p
    _user32 = ctypes.WinDLL("user32")                       # instance à nous : types d'arguments sans effet ailleurs
    _user32.GetParent.argtypes, _user32.GetParent.restype = [c_void_p], c_void_p
    _user32.GetWindowLongW.argtypes, _user32.GetWindowLongW.restype = [c_void_p, c_int], c_long
    _user32.SetWindowLongW.argtypes, _user32.SetWindowLongW.restype = [c_void_p, c_int, c_long], c_long
    _user32.ShowWindow.argtypes, _user32.ShowWindow.restype = [c_void_p, c_int], c_int
    _user32.SetWindowPos.argtypes = [c_void_p, c_void_p, c_int, c_int, c_int, c_int, c_uint]
    _user32.GetForegroundWindow.argtypes, _user32.GetForegroundWindow.restype = [], c_void_p
    _user32.GetWindow.argtypes, _user32.GetWindow.restype = [c_void_p, c_uint], c_void_p
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_APPWINDOW, WS_EX_NOACTIVATE = 0x80, 0x8, 0x40000, 0x08000000
    SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
    HWND_TOPMOST = -1
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
    GW_HWNDPREV = 3
else:                                                        # pragma: no cover - Windows seulement
    _user32 = None


def devant(haut: int, bas: int, limite: int = 4096) -> bool:
    """La fenêtre `haut` est-elle devant `bas` dans l'ordre Z de Windows ? (remonte depuis `bas` ; False hors
    Windows). Sert à ne relever une fenêtre transparente que si le lanceur « au premier plan » est passé devant."""
    if _user32 is None or not haut or not bas:
        return False
    h = bas
    for _ in range(limite):
        h = _user32.GetWindow(h, GW_HWNDPREV) or 0
        if not h:
            return False
        if h == haut:
            return True
    return False


class FenetreAmitie:
    """La petite fenêtre (Toplevel). `discret` : essais pendant que quelqu'un joue (alpha 0, jamais affichée :
    `montrer` ne fait que préparer le cadre Windows caché). `memoriser(x, y)` : appelé au relâchement d'un
    déplacement."""

    def __init__(self, racine: tk.Misc, langue: str, pos: str = "", memoriser: Callable[[int, int], None] | None = None,
                 discret: bool = False):
        self.racine, self.langue, self.memoriser, self.discret = racine, langue, memoriser, discret
        self.top = top = tk.Toplevel(racine)
        top.withdraw()
        top.overrideredirect(True)                           # sans bordure : jamais activée à l'affichage
        top.configure(bg=CONTOUR)
        try:
            top.attributes("-topmost", not discret)
            top.attributes("-alpha", 0.0 if discret else ALPHA)
        except tk.TclError:
            pass
        self.cadre = tk.Frame(top, bg=FOND, padx=8, pady=5)
        self.cadre.pack(padx=1, pady=1)
        self.titre = tk.Label(self.cadre, text=texte(langue, "titre"), bg=FOND, fg=CONTOUR,
                              font=("Segoe UI", 9, "bold"), anchor="w")
        self.titre.grid(row=0, column=0, columnspan=2, sticky="w")
        self.lignes: list[tuple[tk.Label, tk.Label]] = []
        self.visible = False
        self.contenu: list[Ligne] | None = None
        self._hwnd = 0
        self._glisse: tuple[int, int] | None = None
        x, y = position(pos, (top.winfo_screenwidth(), top.winfo_screenheight()))
        top.geometry(f"+{x}+{y}")
        for w in (top, self.cadre, self.titre):
            self._lier(w)

    # -- glisser-déplacer (aucune activation : WS_EX_NOACTIVATE)
    def _lier(self, w: tk.Misc) -> None:
        w.bind("<ButtonPress-1>", self._debut)
        w.bind("<B1-Motion>", self._bouge)
        w.bind("<ButtonRelease-1>", self._fin)

    def _debut(self, e) -> None:
        self._glisse = (e.x_root - self.top.winfo_x(), e.y_root - self.top.winfo_y())

    def _bouge(self, e) -> None:
        if self._glisse is not None:
            self.top.geometry(f"+{e.x_root - self._glisse[0]}+{e.y_root - self._glisse[1]}")

    def _fin(self, _e) -> None:
        if self._glisse is None:
            return
        self._glisse = None
        if self.memoriser is not None:
            self.memoriser(self.top.winfo_x(), self.top.winfo_y())

    # -- Windows : styles étendus et affichage sans activation
    def _preparer_hwnd(self) -> int:
        if self._hwnd or _user32 is None:
            return self._hwnd
        self.top.update_idletasks()
        h = _user32.GetParent(self.top.winfo_id()) or self.top.winfo_id()
        style = _user32.GetWindowLongW(h, GWL_EXSTYLE)
        style = (style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | (0 if self.discret else WS_EX_TOPMOST)) & ~WS_EX_APPWINDOW
        _user32.SetWindowLongW(h, GWL_EXSTYLE, style)
        self._hwnd = h
        return h

    def styles(self) -> int:
        """Styles étendus de la fenêtre (tests) ; 0 hors Windows."""
        return _user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE) if self._hwnd and _user32 is not None else 0

    def montrer(self) -> None:
        if self.visible:
            return
        if self.discret:                                    # essais (quelqu'un joue) : JAMAIS affichée, même invisible :
            self._preparer_hwnd()                           # cadre Windows créé, caché ; « montrée » pour la logique
            self.visible = True                             # (fix/test-premier-plan : lower() de Tk active la fenêtre)
            return
        if not self._hwnd:
            self.top.deiconify()                            # 1re fois : Tk crée la fenêtre (sans bordure : non activée)
            h = self._preparer_hwnd()
        else:
            h = self._hwnd
        if h and _user32 is not None:
            _user32.ShowWindow(h, SW_SHOWNOACTIVATE)
            if not self.discret:
                _user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        elif not h:
            self.top.deiconify()
        self.visible = True

    def relever(self, lanceur: int) -> bool:
        """Lanceur « au premier plan » (HWND `lanceur`, premier_plan.py) passé devant cette fenêtre (case cochée,
        clic dans le lanceur) : la remettre devant lui, SANS activation. Rien si elle est cachée, discrète, ou déjà
        devant. Renvoie True si elle a été relevée."""
        if not self.visible or self.discret or not self._hwnd or _user32 is None or not devant(lanceur, self._hwnd):
            return False
        _user32.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        return True

    def cacher(self) -> None:
        if not self.visible:
            return
        if self._hwnd and _user32 is not None:
            _user32.ShowWindow(self._hwnd, SW_HIDE)
        else:
            self.top.withdraw()
        self.visible = False

    def remplir(self, lignes: list[Ligne]) -> None:
        if lignes == self.contenu:
            return
        self.contenu = list(lignes)
        while len(self.lignes) < len(lignes):
            r = len(self.lignes) + 1
            a = tk.Label(self.cadre, bg=FOND, fg=TEXTE, font=("Segoe UI", 10), anchor="w")
            b = tk.Label(self.cadre, bg=FOND, font=("Segoe UI", 10, "bold"), anchor="e")
            a.grid(row=r, column=0, sticky="w", padx=(0, 12))
            b.grid(row=r, column=1, sticky="e")
            for w in (a, b):
                self._lier(w)
            self.lignes.append((a, b))
        couleurs = {"ami": VERT, "pas_ami": ORANGE, "inconnu": GRIS}
        cles = {"ami": "ami", "pas_ami": "pas_ami", "inconnu": "inconnu"}
        for i, (a, b) in enumerate(self.lignes):
            if i < len(lignes):
                a.configure(text=lignes[i].nom)
                b.configure(text=texte(self.langue, cles[lignes[i].statut]), fg=couleurs[lignes[i].statut])
                a.grid()
                b.grid()
            else:
                a.grid_remove()
                b.grid_remove()

    def changer_langue(self, langue: str) -> None:
        self.langue = langue
        self.titre.configure(text=texte(langue, "titre"))
        self.contenu = None                                  # textes refaits au prochain remplissage

    def existe(self) -> bool:
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    def detruire(self) -> None:
        try:
            self.top.destroy()
        except tk.TclError:
            pass


# ------------------------------------------------------------------------------------------------ lanceur
def memoriser(lanceur, **champs) -> None:
    """Réglage de la fenêtre mémorisé dans config.json (relire-modifier-écrire sous le verrou : rien de ce que le
    client ou une autre fenêtre y a écrit n'est perdu), puis reporté dans la configuration en mémoire du lanceur."""
    try:
        c = lanceur.stockage.modifier(**champs)
    except OSError:
        return
    for k in champs:
        setattr(lanceur.config, k, getattr(c, k))


def case_option(parent: tk.Misc, theme, langue: str, variable: tk.BooleanVar, commande, ligne: int,
                scene=None) -> tk.Misc:
    """Case de l'option et son explication dans la carte « Paramètres du jeu » de l'onglet « Réglages » du lanceur
    (lignes `ligne` et `ligne` + 1 de la grille de la carte) : la vue n'a rien d'autre à construire. `scene`
    (`theme.Scene`) : explication repliée à la largeur de la carte."""
    from . import theme as th
    px = theme.px
    b = th.Bascule(parent, theme, texte(langue, "option"), variable, commande=commande)
    b.grid(row=ligne, column=0, columnspan=3, sticky="w", pady=(px(3), 0))
    aide = tk.Label(parent, text=texte(langue, "aide"), font=theme["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                    justify="left", anchor="w")
    aide.grid(row=ligne + 1, column=0, columnspan=3, sticky="w", padx=(px(28), 0), pady=(0, px(2)))
    if scene is not None:
        scene.texte_extensible(aide, px(32))
    return b


# ------------------------------------------------------------------------------------------------ contrôleur
class Suivi:
    """Relit `amis_combat.json` toutes les PERIODE_MS (stat seulement si rien n'a changé) et montre / cache la
    fenêtre. Rien n'est créé tant que l'option est décochée."""

    def __init__(self, racine: tk.Misc, dossier: str | Path, langue: str, actif: bool = False, pos: str = "",
                 memoriser_pos: Callable[[int, int], None] | None = None, discret: bool = False, auto: bool = True):
        self.racine, self.dossier, self.langue = racine, Path(dossier), langue
        self.actif, self.pos, self.memoriser_pos, self.discret = bool(actif), pos, memoriser_pos, discret
        self.noms = NomsLocaux(dossier)
        self.fenetre: FenetreAmitie | None = None
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
            st = (self.dossier / AMC.NOM_FICHIER).stat()
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

    def _fenetre_vivante(self) -> FenetreAmitie | None:
        # la vue du lanceur détruit tous les enfants de la racine quand elle se reconstruit (changement de langue) :
        # la fenêtre est alors refaite au prochain affichage
        if self.fenetre is not None and not self.fenetre.existe():
            self.fenetre = None
        return self.fenetre

    def changer_langue(self, langue: str) -> None:
        self.langue = langue
        if self._fenetre_vivante() is not None:
            self.fenetre.changer_langue(langue)

    def tour(self) -> list[Ligne] | None:
        """Un passage (appelé par `after`, ou directement par les tests) ; rend les lignes montrées (None : cachée)."""
        lignes = None
        try:
            if self.actif:
                sig = self._signature()
                if sig != self._sig:
                    self._sig, self._donnees = sig, AMC.lire(self.dossier)
                lignes = lire_affichage(self._donnees, self.langue, self.noms)
                if lignes is not None:
                    self.noms.preparer()
                    lignes = lire_affichage(self._donnees, self.langue, self.noms)
            self._fenetre_vivante()
            if lignes is None:
                if self.fenetre is not None:
                    self.fenetre.cacher()
            else:
                if self.fenetre is None:
                    self.fenetre = FenetreAmitie(self.racine, self.langue, self.pos, self._memoriser, self.discret)
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
