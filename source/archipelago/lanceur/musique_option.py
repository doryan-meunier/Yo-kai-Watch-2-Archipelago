"""Option « Musique aléatoire » du lanceur (décochée par défaut ; `docs/systemes/archipelago_musique.md`).

Case : onglet « Réglages » → « Paramètres du jeu ». Cochée, les musiques du jeu sont mélangées entre elles
(`installation/musique.py`) ; mémorisée dans `config.json` (`musique_aleatoire`, `musique_graine`, relire-modifier-
écrire sous le verrou). Cocher tire une NOUVELLE graine (nouveau mélange) ; décocher la garde mais n'installe rien.

Application au prochain « Jouer » (ou à l'installation / la réparation du mod) : si l'état installé (clé `musique`
de l'estampille `ykw2ap.json` : version de l'algorithme, graine, mode) n'est pas celui voulu, les fichiers de la
musique sont refaits et l'estampille réécrite (`restampiller`) sans rien changer aux autres fichiers du mod : code,
patchs de `romfs_ext/` des archives `.fa` et estampille identiques à une installation sans l'option une fois la case
décochée (les fichiers de la musique sont retirés, la clé `musique` aussi).
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

from . import logique as _logique  # noqa: F401  (met installation/ sur sys.path)
from installation import installer as inst  # noqa: E402
from installation import musique as mus  # noqa: E402

TEXTES = {
    "fr": {"option": "Musique aléatoire",
           "aide": "Les musiques du jeu sont mélangées entre elles (terrain, combats, scènes), sans musique "
                   "extérieure. Appliqué au prochain « Jouer » ; recocher la case tire un nouveau mélange.",
           "etape": "Préparation de la musique aléatoire…"},
    "en": {"option": "Random music",
           "aide": "The game's music tracks are shuffled among themselves (field, battles, scenes), with no outside "
                   "music. Applied on the next “Play”; checking the box again draws a new shuffle.",
           "etape": "Preparing the random music…"},
}


def texte(langue: str, cle: str) -> str:
    return (TEXTES.get(langue) or TEXTES["fr"])[cle]


def est_fichier_musique(nom: str) -> bool:
    """Fichier du mod qui appartient à la musique aléatoire (chemin relatif au dossier du titre)."""
    return nom.startswith(f"romfs/{mus.DOSSIER}/") or nom.startswith(f"romfs_ext/{mus.DOSSIER}/")


def reglage(config) -> tuple[bool, int]:
    return bool(getattr(config, "musique_aleatoire", False)), int(getattr(config, "musique_graine", 0) or 0)


def fichiers(rom: str | Path, mods: str | Path, actif: bool, graine: int, emulateur: str,
             nos_fichiers=()) -> tuple[dict[str, bytes], list[str], dict | None]:
    """Fichiers de la musique pour une installation : ({chemin: octets}, avertissements, valeur de la clé `musique`
    de l'estampille, None si l'option est désactivée). Un échec n'empêche jamais l'installation (avertissement ;
    la clé porte alors l'erreur, et le prochain « Jouer » réessaie)."""
    v = mus.voulu(actif, graine, emulateur)
    if v is None:
        return {}, [], None
    try:
        r = mus.preparer(rom, graine, emulateur, inst.dossier_titre(mods), nos_fichiers)
    except (mus.ErreurMusique, OSError) as e:
        return {}, [f"Musique aléatoire non installée : {e}"], dict(v, erreur=str(e))
    return r.fichiers, r.avertissements, v


def restampiller(mods: str | Path, rom: str | Path, actif: bool, graine: int, emulateur: str) -> inst.Rapport:
    """Refait les seuls fichiers de la musique d'une installation existante (les autres fichiers du mod sont relus
    tels quels sur le disque, SHA-1 vérifiés par `installer_fichiers`)."""
    est = inst.lire_estampille(mods)
    if est is None:
        raise inst.ErreurInstallation("mod non installé")
    titre = inst.dossier_titre(mods)
    garder = {n: (titre / n).read_bytes() for n in est["fichiers"] if not est_fichier_musique(n)}
    code, exh = garder.pop("code.bin"), garder.pop("exheader.bin")
    infos = {k: v for k, v in est.get("infos", {}).items() if k != "musique"}
    supp, avert, v = fichiers(rom, mods, actif, graine, emulateur, est["fichiers"])
    garder.update(supp)
    if v is not None:
        infos["musique"] = v
    return inst.installer_fichiers(code, exh, mods, est["version"], infos, garder, avert)


def a_refaire(lanceur) -> bool:
    mods = lanceur.dossier_mods()
    if mods is None:
        return False
    try:
        est = inst.lire_estampille(mods)
    except inst.ErreurInstallation:
        return False
    actif, graine = reglage(lanceur.config)
    return mus.a_refaire(est, actif, graine, lanceur.emulateur())


def mettre_a_jour(lanceur, rappel: Callable | None = None, msg=None) -> inst.Rapport | None:
    """« Jouer » : applique le réglage s'il a changé depuis l'installation (sinon rien)."""
    if not a_refaire(lanceur):
        return None
    if rappel is not None and msg is not None:
        rappel(msg)
    actif, graine = reglage(lanceur.config)
    return restampiller(lanceur.dossier_mods(), lanceur.config.rom, actif, graine, lanceur.emulateur())


class OptionMusique:
    """Case « Musique aléatoire » de la fenêtre `racine` du lanceur `lanceur`."""

    def __init__(self, racine: tk.Misc, lanceur, memoriser: Callable[..., None] | None = None):
        self.l = lanceur
        if memoriser is None:
            from . import fenetre_amitie as FA
            memoriser = lambda **c: FA.memoriser(lanceur, **c)    # noqa: E731
        self.memoriser = memoriser
        self.var = tk.BooleanVar(racine, value=reglage(lanceur.config)[0])

    def basculer(self) -> None:
        actif = bool(self.var.get())
        if actif:
            self.memoriser(musique_aleatoire=True, musique_graine=mus.nouvelle_graine())
        else:
            self.memoriser(musique_aleatoire=False)

    def case_option(self, parent: tk.Misc, theme, langue: str, ligne: int, scene=None) -> tk.Misc:
        """Case et explication dans la carte « Paramètres du jeu » (lignes `ligne` et `ligne` + 1)."""
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
