"""Fenêtre de la loupe (option du lanceur, désactivée par défaut ; docs/systemes/archipelago_loupe_amis.md).

Case : onglet « Réglages » → « Paramètres du jeu » du lanceur (avec Azahar comme avec Zakuro), à part de la fenêtre
d'amitié en combat (on peut vouloir l'une sans l'autre ; elles ne sont jamais montrées en même temps : terrain / combat).
Sur le terrain, quand le radar de la montre vise un point de loupe, une petite fenêtre sans bord, toujours au-dessus,
semi-transparente et déplaçable, montre le ou les Yo-kai que ce point peut faire combattre À CET INSTANT (après le
mélange) et pour chacun « Ami » / « Pas encore ami » (bit « ami » du Médaillium de la sauvegarde chargée). Si le point
peut lancer plusieurs rencontres de 1ers combattants différents (tirage pondéré au moment de la loupe), chaque espèce a
sa ligne avec sa chance sur 100. Cachée quand le radar ne vise rien, en combat, option décochée, sans jeu, ou si le
client ne donne plus de nouvelles.

Données : `loupe.json`, écrit par le client (`client/loupe_amis.py`) d'après ce que le jeu publie
(`docs/systemes/archipelago_boite.md` §54). Noms : base locale `yokai_local.json` générée chez le joueur depuis SA ROM
(`especes[<hachage CHARA_PARAM>].noms`, et `.base` pour un point à base fixe), jamais de texte du jeu dans le code ni
dans git (règle 6) ; sans base : le n° du Médaillium.

La fenêtre est celle de la fenêtre d'amitié (`fenetre_amitie.FenetreAmitie` : jamais de focus, WS_EX_NOACTIVATE,
glisser-déplacer, position mémorisée), avec son propre titre et sa propre position (`loupe_fenetre_pos`).

Logique sans affichage (testable) : `lire_affichage`, `NomsLoupe` ; vue : `FenetreLoupe` ; contrôleur : `SuiviLoupe`.
"""
from __future__ import annotations

import json
import sys
import time
import tkinter as tk
from pathlib import Path
from typing import Callable

ARCHIPELAGO = Path(__file__).resolve().parents[1]
for _p in (ARCHIPELAGO, ARCHIPELAGO / "client"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import loupe_amis as LPA  # noqa: E402  (client/ : fichier écrit par le client)

from . import fenetre_amitie as FA  # noqa: E402

PERIODE_MS = 400              # relecture de loupe.json (stat seulement si rien n'a changé)
GENRE_FIXE = 1                # ApLoupe::genre : point à base fixe (aucune rencontre connue)

TEXTES = {
    "fr": {"option": "Fenêtre de la loupe", "titre": "Radar de la loupe", "chance": "{nom} ({p} %)",
           "autres": "+ {n} autre(s)", "particulier": "{nom} (point particulier)",
           "aide": "Sur le terrain, quand le radar de la montre vise un point, une petite fenêtre transparente indique "
                   "le Yo-kai qu'on y trouvera (après le mélange) et s'il est déjà votre ami (Médaillium). Glissez-la "
                   "pour la déplacer."},
    "en": {"option": "Magnifier window", "titre": "Magnifier radar", "chance": "{nom} ({p}%)",
           "autres": "+ {n} more", "particulier": "{nom} (special spot)",
           "aide": "In the field, when the watch's radar points at a spot, a small transparent window shows the Yo-kai "
                   "you will find there (after shuffling) and whether it is already your friend (Medallium). Drag it "
                   "to move it."},
}


def texte(langue: str, cle: str, **p) -> str:
    t = TEXTES.get(langue) or TEXTES["fr"]
    return t[cle].format(**p) if p else t[cle]


# ------------------------------------------------------------------------------------------------ logique
class NomsLoupe(FA.NomsLocaux):
    """Noms des espèces (comme la fenêtre d'amitié) et, pour un point à base fixe, nom d'une espèce de cette base."""

    def __init__(self, dossier: str | Path, synchrone: bool = False):
        super().__init__(dossier, synchrone)
        self._bases: dict[int, int] = {}                     # base CHARA_BASE -> une espèce CHARA_PARAM

    def _charger(self, sig) -> None:
        super()._charger(sig)
        bases: dict[int, int] = {}
        try:
            base = json.loads(self.fichier.read_text(encoding="utf-8"))
            for p, info in sorted((base.get("especes") or {}).items()):
                b = info.get("base") if isinstance(info, dict) else None
                if str(p).isdigit() and isinstance(b, int) and b not in bases:
                    bases[b] = int(p)
        except (OSError, ValueError, AttributeError):
            bases = {}
        self._bases = bases

    def nom_base(self, base: int, langue: str) -> str | None:
        p = self._bases.get(int(base))
        return self.nom(p, langue) if p is not None else None


def lire_affichage(d: dict | None, langue: str, noms: NomsLoupe | None = None,
                   maintenant: float | None = None) -> list[FA.Ligne] | None:
    """Lignes à montrer d'après le contenu de `loupe.json` ; None = fenêtre cachée (radar sans cible, pas de jeu, patch
    sans la loupe, fichier trop ancien ou vide)."""
    if not d or not d.get("publie") or not d.get("cible"):
        return None
    h = d.get("horodatage")
    if not isinstance(h, (int, float)) or abs((time.time() if maintenant is None else maintenant) - h) > LPA.AGE_MAX:
        return None
    lignes: list[FA.Ligne] = []
    if d.get("genre") == GENRE_FIXE:
        b = d.get("base")
        nom = noms.nom_base(b, langue) if noms is not None and isinstance(b, int) else None
        lignes.append(FA.Ligne(texte(langue, "particulier", nom=nom or FA.texte(langue, "inconnue")), "inconnu"))
        return lignes
    especes = [e for e in d.get("especes") or () if isinstance(e, dict) and isinstance(e.get("param"), int)]
    plusieurs = len(especes) > 1 or (isinstance(d.get("autres"), int) and d["autres"] > 0)
    for e in especes:
        nom = noms.nom(e["param"], langue) if noms is not None and e["param"] else None
        if not nom:
            m = e.get("medaille")
            nom = FA.texte(langue, "numero", n=m) if isinstance(m, int) and m > 0 else FA.texte(langue, "inconnue")
        p = e.get("poids")
        if plusieurs and isinstance(p, int):
            nom = texte(langue, "chance", nom=nom, p=p)
        a = e.get("ami")
        lignes.append(FA.Ligne(nom, "ami" if a is True else "pas_ami" if a is False else "inconnu"))
    if isinstance(d.get("autres"), int) and d["autres"] > 0:
        lignes.append(FA.Ligne(texte(langue, "autres", n=d["autres"]), "inconnu"))
    return lignes or None


# ------------------------------------------------------------------------------------------------ vue
class FenetreLoupe(FA.FenetreAmitie):
    """La fenêtre d'amitié, avec le titre de la loupe."""

    def __init__(self, racine: tk.Misc, langue: str, pos: str = "", memoriser: Callable[[int, int], None] | None = None,
                 discret: bool = False):
        super().__init__(racine, langue, pos, memoriser, discret)
        self.titre.configure(text=texte(langue, "titre"))

    def changer_langue(self, langue: str) -> None:
        super().changer_langue(langue)
        self.titre.configure(text=texte(langue, "titre"))


# ------------------------------------------------------------------------------------------------ lanceur
def case_option(parent: tk.Misc, theme, langue: str, variable: tk.BooleanVar, commande, ligne: int,
                scene=None) -> tk.Misc:
    """Case de l'option et son explication dans la carte « Paramètres du jeu » (lignes `ligne` et `ligne` + 1)."""
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
class SuiviLoupe(FA.Suivi):
    """Relit `loupe.json` toutes les PERIODE_MS (stat seulement si rien n'a changé) et montre / cache la fenêtre. Rien
    n'est créé tant que l'option est décochée."""

    def __init__(self, racine: tk.Misc, dossier: str | Path, langue: str, actif: bool = False, pos: str = "",
                 memoriser_pos: Callable[[int, int], None] | None = None, discret: bool = False, auto: bool = True):
        super().__init__(racine, dossier, langue, actif, pos, memoriser_pos, discret, auto=False)
        self.noms = NomsLoupe(dossier)
        if auto:
            self._planifier()

    def _signature(self):
        try:
            st = (self.dossier / LPA.NOM_FICHIER).stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def tour(self) -> list[FA.Ligne] | None:
        """Un passage (appelé par `after`, ou directement par les tests) ; rend les lignes montrées (None : cachée)."""
        lignes = None
        try:
            if self.actif:
                sig = self._signature()
                if sig != self._sig:
                    self._sig, self._donnees = sig, LPA.lire(self.dossier)
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
                    self.fenetre = FenetreLoupe(self.racine, self.langue, self.pos, self._memoriser, self.discret)
                self.fenetre.remplir(lignes)
                self.fenetre.montrer()
                if self.au_dessus is not None:
                    self.fenetre.relever(self.au_dessus())
        finally:
            if self._apres is not None:
                self._planifier()
        return lignes
