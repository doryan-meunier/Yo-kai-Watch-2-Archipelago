"""Sous-onglet « Apparence » de l'onglet « Réglages » : tenue du personnage principal (Nathan / Katie).

Le calcul des textures est dans `installation/apparence.py` (sans affichage) ; ici : le formulaire, l'aperçu, l'état.
- Choix : personnage (le modèle à habiller ; le jeu garde le personnage de la partie, chacun a son réglage), tenue
  (d'origine, tenues officielles, sépia, couleur personnalisée), teinte (curseur, couleur personnalisée seulement).
- Chaque changement est mémorisé tout de suite dans `config.json` (`memoriser` : relire - modifier - écrire sous le
  verrou) ; il est appliqué au prochain « Jouer » (patch `romfs_ext/yw2_a.fa.bps` refait si l'empreinte du réglage
  a changé : `Lanceur.apparence_a_appliquer`).
- Aperçu : calculé dans un fil de fond depuis la ROM du joueur (jamais distribué), mis en cache dans le dossier de
  données (`apparence/apercu_<personnage>_<empreinte>.png`), seulement quand le sous-onglet est affiché.
- Mod d'apparence importé (carte à part, branche ap/apparence-import) : « Importer un fichier… » / « … un dossier… »
  (zip, dossier, `yw2_a.fa` ; analyse dans un fil de fond, `installation/apparence_import.py`), case « Utiliser le
  mod importé », « Retirer » ; résumé (fichiers retenus, ignorés, avertissements, conflits avec la tenue choisie).
  Boîtes de choix injectables (`choisir`, `confirmer`) : aucune boîte native dans les tests.
"""
from __future__ import annotations

import colorsys
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Callable

from . import theme as th
from .textes import t

from .logique import app_mod as A          # installation/apparence.py (logique.py met archipelago/ sur sys.path)
from .logique import app_imp as AI         # installation/apparence_import.py

DOSSIER_CACHE = "apparence"
DELAI_TEINTE = 350                         # ms après le dernier mouvement du curseur : mémorisation et aperçu
NIVEAUX = {"app_etat_origine": "neutre", "app_etat_applique": "ok", "app_etat_attente": "attention",
           "app_etat_sans_mod": "attention", "app_etat_echec": "erreur", "app_etat_inconnu": "erreur"}


def chemin_apercu(dossier: Path, personnage: str, reglage) -> Path:
    return Path(dossier) / DOSSIER_CACHE / f"apercu_{personnage}_{A.empreinte_personnage(personnage, reglage)}.png"


def calculer_apercu(rom: str, dossier: Path, personnage: str, reglage) -> Path:
    """Aperçu en cache (PNG) d'un personnage pour un réglage, calculé depuis la ROM s'il manque."""
    p = chemin_apercu(dossier, personnage, reglage)
    if p.is_file():
        return p
    src = A.L.SourceRomfs(rom)
    with A.Lecteur(src) as lec:
        w, h, pix = A.pixels_apercu(lec, personnage, reglage)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    A.L.ecrire_png(tmp, w, h, pix)
    tmp.replace(p)
    return p


@dataclass
class SourceImport:
    """Accès au mod d'apparence importé (méthodes du `Lanceur` ; injectables pour les tests)."""
    manifeste: Callable[[], dict | None]
    actif: Callable[[], bool]
    changer_actif: Callable[[bool], None]
    importer: Callable[[str], dict]
    retirer: Callable[[], None]


LIGNES_MAX = 6                             # fichiers et avertissements montrés dans le résumé de l'import


def _court(chemin: str) -> str:
    return chemin.rsplit("/", 1)[-1]


def texte_import(langue: str, m: dict | None, conflits: list[str]) -> str:
    """Résumé d'un import (manifeste) dans la langue du lanceur."""
    if not m:
        return t(langue, "app_imp_aucun")
    lignes = []
    fichiers = sorted(m.get("fichiers", {}))
    noms = ", ".join(_court(c) for c in fichiers[:LIGNES_MAX])
    if len(fichiers) > LIGNES_MAX:
        noms += t(langue, "app_imp_et_autres", n=len(fichiers) - LIGNES_MAX)
    lignes.append(t(langue, "app_imp_retenus", n=len(fichiers), noms=noms))
    nombres = {k: v for k, v in (m.get("nombres") or {}).items() if v and k in AI.RAISONS}
    if nombres:
        lignes.append(t(langue, "app_imp_ignores", detail=", ".join(
            t(langue, f"app_imp_r_{k}", n=v)
            for k, v in sorted(nombres.items(), key=lambda kv: AI.RAISONS.index(kv[0])))))
    av = [a for a in m.get("avertissements") or [] if isinstance(a, dict)]
    for a in av[:LIGNES_MAX]:
        p = dict(a.get("params") or {})
        cle = "app_imp_av_texture_sans" if a.get("cle") == "texture" and not p.get("l0") \
            else f"app_imp_av_{a.get('cle')}"
        try:
            lignes.append(t(langue, cle, fichier=_court(str(a.get("chemin", ""))), **p))
        except (KeyError, IndexError, ValueError):
            continue
    if len(av) > LIGNES_MAX:
        lignes.append(t(langue, "app_imp_av_autres", n=len(av) - LIGNES_MAX))
    if conflits:
        lignes.append(t(langue, "app_imp_conflit", noms=", ".join(_court(c) for c in conflits)))
    return "\n".join(lignes)


def couleur_teinte(deg: int) -> str:
    r, g, b = colorsys.hsv_to_rgb((deg % 360) / 360, 0.75, 0.85)
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


class OngletApparence:
    """Deux cartes de la page « reglages/apparence » : le formulaire (colonne gauche, avec l'état) et l'aperçu
    (colonne droite, avec l'aide).

    reglage() : réglage courant (`config.json`) ; memoriser(reglage) ; etat() : `Msg` de `Lanceur.etat_apparence` ;
    rom() : chemin de la ROM ("" : aucune) ; dossier : dossier de données (cache des aperçus) ; apercu(rom, dossier,
    personnage, reglage) -> PNG (injectable pour les tests)."""

    def __init__(self, sc: th.Scene, T: th.Theme, langue: str, *, dossier: Path,
                 reglage: Callable[[], dict], memoriser: Callable[[dict], None],
                 etat: Callable[[], object] | None = None, rom: Callable[[], str] = lambda: "",
                 apercu: Callable[..., Path] = calculer_apercu, personnage: str = "nathan",
                 importeur: SourceImport | None = None, choisir: Callable[[str], str] | None = None,
                 confirmer: Callable[[str], bool] | None = None):
        self.sc, self.T, self.langue = sc, T, langue
        self.dossier, self.lire_reglage, self.memoriser, self.lire_etat, self.rom = (Path(dossier), reglage, memoriser,
                                                                                     etat, rom)
        self.fonction_apercu = apercu
        self.importeur = importeur
        self.choisir = choisir or self._choisir_defaut
        self.confirmer = confirmer or self._confirmer_defaut
        self._file_imp: queue.Queue = queue.Queue()
        self.import_en_cours = False
        self.manifeste_import: dict | None = None
        self.racine = sc.r
        self.actif = False
        self.personnage = personnage if personnage in A.PERSONNAGES else "nathan"
        self.reglage: dict = {}
        self._remplissage = False
        self._apres_teinte = None
        self._file: queue.Queue = queue.Queue()
        self._calcul: tuple | None = None          # (personnage, empreinte) en cours de calcul
        self._voulu: tuple | None = None           # (personnage, empreinte) à montrer
        self.image: tk.PhotoImage | None = None
        self.apercu_png: Path | None = None
        self.etat_cle, self.etat_params = "", {}
        self.v_tenue = tk.StringVar(self.racine)
        self.v_teinte = tk.IntVar(self.racine, value=A.TEINTE_DEFAUT)
        self.v_teinte_txt = tk.StringVar(self.racine)
        self.v_etat = tk.StringVar(self.racine)
        self.v_apercu = tk.StringVar(self.racine)
        self.v_imp = tk.StringVar(self.racine)
        self.v_imp_resultat = tk.StringVar(self.racine)
        self.v_imp_actif = tk.BooleanVar(self.racine, value=False)
        self.construire()
        self.relire()

    def tr(self, cle: str, **p) -> str:
        return t(self.langue, cle, **p)

    # ------------------------------------------------------------------ construction
    def construire(self) -> None:
        T, px, sc = self.T, self.T.px, self.sc
        th.styler_ttk(self.racine, T)
        c = self.corps = sc.carte(self.tr("app_titre"))
        form = tk.Frame(c, bg=th.BLANC)
        form.grid(row=0, column=0, columnspan=3, sticky="ew")
        form.columnconfigure(1, weight=1)
        # personnage : deux pilules, celle du personnage montré est rouge
        tk.Label(form, text=self.tr("app_personnage"), font=T["texte"], bg=th.BLANC, fg=th.TEXTE, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, px(10)), pady=px(3))
        rang = tk.Frame(form, bg=th.BLANC)
        rang.grid(row=0, column=1, sticky="w", pady=px(3))
        self.b_perso = {}
        for p in A.PERSONNAGES:
            b = th.Pilule(rang, T, self.tr(f"app_{p}"), lambda p=p: self.choisir_personnage(p), police="bouton_petit",
                          padx=14, pady=3)
            b.pack(side="left", padx=(0, px(4)))
            self.b_perso[p] = b
        self._indice(form, 1, "app_indice_personnage")
        # tenue
        tk.Label(form, text=self.tr("app_tenue"), font=T["texte"], bg=th.BLANC, fg=th.TEXTE, anchor="w").grid(
            row=2, column=0, sticky="w", padx=(0, px(10)), pady=px(3))
        largeur = max(len(self.tr(k)) for k in self.tr_tenues_toutes()) + 2
        self.liste = ttk.Combobox(form, state="readonly", style="Yokai.TCombobox", font=T["texte"],
                                  textvariable=self.v_tenue, width=largeur)
        self.liste.grid(row=2, column=1, sticky="w", pady=px(3))
        self.liste.bind("<<ComboboxSelected>>", lambda _e: self.saisie_tenue())
        # teinte (couleur personnalisée seulement)
        self.cadre_teinte = tk.Frame(form, bg=th.BLANC)
        self.cadre_teinte.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(2), 0))
        self.cadre_teinte.columnconfigure(1, weight=1)
        tk.Label(self.cadre_teinte, text=self.tr("app_teinte"), font=T["texte"], bg=th.BLANC, fg=th.TEXTE,
                 anchor="w").grid(row=0, column=0, sticky="w", padx=(0, px(10)))
        self.curseur = tk.Scale(self.cadre_teinte, from_=0, to=359, orient="horizontal", showvalue=False,
                                variable=self.v_teinte, command=lambda _v: self.saisie_teinte(), bg=th.BLANC,
                                troughcolor=th.INACTIF_FOND, highlightthickness=0, bd=0, length=px(220),
                                sliderlength=px(18), width=px(12))
        self.curseur.grid(row=0, column=1, sticky="ew")
        self.temoin = tk.Canvas(self.cadre_teinte, width=px(22), height=px(16), bg=th.BLANC, highlightthickness=0)
        self.temoin.grid(row=0, column=2, padx=(px(8), px(4)))
        tk.Label(self.cadre_teinte, textvariable=self.v_teinte_txt, font=T["texte"], bg=th.BLANC, fg=th.TEXTE,
                 width=5, anchor="w").grid(row=0, column=3, sticky="w")
        lab = tk.Label(self.cadre_teinte, text=self.tr("app_indice_teinte"), font=T["petit"], bg=th.BLANC,
                       fg=th.TEXTE_DOUX, justify="left", anchor="w")
        lab.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, px(2)))
        sc.texte_extensible(lab, px(32))
        # tenue cachée (expérimentale) : indication sous la liste
        self.lab_cachee = tk.Label(form, text=self.tr("app_indice_cachee"), font=T["petit"], bg=th.BLANC,
                                   fg=th.TEXTE_DOUX, justify="left", anchor="w")
        self.lab_cachee.grid(row=4, column=0, columnspan=2, sticky="w", padx=(px(28), 0), pady=(0, px(2)))
        sc.texte_extensible(self.lab_cachee, px(32))
        # boutons
        bas = tk.Frame(c, bg=th.BLANC)
        bas.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(px(8), px(2)))
        self.b_origine = th.Pilule(bas, T, self.tr("app_origine"), self.remettre_origine, genre="clair",
                                   police="bouton_petit", padx=10, pady=3)
        self.b_origine.pack(side="left")
        # état
        self.pastille = th.Pastille(c, T)
        haut = px(4) + max(0, (T["texte"].metrics("linespace") - self.pastille.d) // 2)
        self.pastille.grid(row=2, column=0, sticky="nw", pady=(haut, 0), padx=(0, px(8)))
        lab = tk.Label(c, textvariable=self.v_etat, font=T["texte"], bg=th.BLANC, fg=th.TEXTE, justify="left",
                       anchor="w")
        lab.grid(row=2, column=1, columnspan=2, sticky="w", pady=(px(3), px(2)))
        sc.texte_extensible(lab, self.pastille.d + px(12))
        self.v_etat.trace_add("write", lambda *_a: self.replanifier())
        # aperçu et aide (colonne droite)
        a = self.carte_apercu = sc.carte(self.tr("app_apercu_titre"), colonne="d")
        self.lab_image = tk.Label(a, bg=th.BLANC, bd=0)
        self.lab_image.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, px(4)))
        lab = tk.Label(a, textvariable=self.v_apercu, font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX, justify="left",
                       anchor="w")
        lab.grid(row=1, column=0, columnspan=3, sticky="w")
        sc.texte_extensible(lab, px(4))
        self.v_apercu.trace_add("write", lambda *_a: self.replanifier())
        n = 2
        for cle in ("app_aide_rom", "app_aide_jouer", "app_aide_cinematiques", "app_aide_duree"):
            lab = tk.Label(a, text=self.tr(cle), font=T["texte"], bg=th.BLANC, fg=th.TEXTE, justify="left",
                           anchor="w")
            lab.grid(row=n, column=0, columnspan=3, sticky="w", pady=px(3))
            sc.texte_extensible(lab, px(4))
            n += 1
        if self.importeur is not None:
            self.construire_import()

    def construire_import(self) -> None:
        """Carte « Mod d'apparence importé » (colonne gauche, sous le formulaire)."""
        T, px, sc = self.T, self.T.px, self.sc
        c = self.carte_import = sc.carte(self.tr("app_imp_titre"))
        lab = tk.Label(c, textvariable=self.v_imp, font=T["texte"], bg=th.BLANC, fg=th.TEXTE, justify="left",
                       anchor="w")
        lab.grid(row=0, column=0, columnspan=3, sticky="w", pady=(px(2), px(2)))
        sc.texte_extensible(lab, px(4))
        self.b_imp_actif = th.Bascule(c, T, self.tr("app_imp_actif"), self.v_imp_actif, commande=self.basculer_import)
        self.b_imp_actif.grid(row=1, column=0, columnspan=3, sticky="w", pady=px(2))
        rang = tk.Frame(c, bg=th.BLANC)
        rang.grid(row=2, column=0, columnspan=3, sticky="w", pady=(px(6), px(2)))
        self.b_imp_fichier = th.Pilule(rang, T, self.tr("app_imp_fichier"), lambda: self.lancer_import("fichier"),
                                       police="bouton_petit", padx=10, pady=3)
        self.b_imp_fichier.pack(side="left", padx=(0, px(4)))
        self.b_imp_dossier = th.Pilule(rang, T, self.tr("app_imp_dossier"), lambda: self.lancer_import("dossier"),
                                       genre="clair", police="bouton_petit", padx=10, pady=3)
        self.b_imp_dossier.pack(side="left", padx=(0, px(4)))
        self.b_imp_retirer = th.Pilule(rang, T, self.tr("app_imp_retirer"), self.retirer_import, genre="clair",
                                       police="bouton_petit", padx=10, pady=3)
        self.b_imp_retirer.pack(side="left")
        lab = tk.Label(c, textvariable=self.v_imp_resultat, font=T["petit"], bg=th.BLANC, fg=th.TEXTE,
                       justify="left", anchor="w")
        lab.grid(row=3, column=0, columnspan=3, sticky="w", pady=(px(4), px(2)))
        sc.texte_extensible(lab, px(4))
        lab = tk.Label(c, text=self.tr("app_imp_aide"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                       justify="left", anchor="w")
        lab.grid(row=4, column=0, columnspan=3, sticky="w", pady=(px(4), px(2)))
        sc.texte_extensible(lab, px(4))
        for v in (self.v_imp, self.v_imp_resultat):
            v.trace_add("write", lambda *_a: self.replanifier())

    def tr_tenues_toutes(self) -> list[str]:
        return [self._cle_tenue(p, x) for p in A.PERSONNAGES for x in A.TENUES[p]]

    @staticmethod
    def _cle_tenue(personnage: str, tenue: str) -> str:
        return f"app_t_origine_{personnage}" if tenue == "origine" else f"app_t_{tenue}"

    def _indice(self, parent, r, cle) -> tk.Label:
        lab = tk.Label(parent, text=self.tr(cle), font=self.T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                       justify="left", anchor="w")
        lab.grid(row=r, column=0, columnspan=2, sticky="w", padx=(self.T.px(28), 0), pady=(0, self.T.px(2)))
        self.sc.texte_extensible(lab, self.T.px(32))
        return lab

    def replanifier(self) -> None:
        try:
            self.racine.after(30, self.sc.planifier)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ valeurs
    def relire(self) -> None:
        """Réglage de `config.json` montré dans le formulaire (personnage affiché inchangé)."""
        brut = self.lire_reglage() or {}
        self.reglage = {p: dict(r) for p, r in brut.items() if isinstance(r, dict) and p in A.PERSONNAGES}
        self.poser()

    def reglage_perso(self, personnage: str | None = None) -> dict:
        p = personnage or self.personnage
        n = A.normaliser(self.reglage).get(p)
        return n or {"tenue": "origine"}

    def poser(self) -> None:
        """Formulaire = réglage du personnage affiché."""
        self._remplissage = True
        try:
            for p, b in self.b_perso.items():
                b.changer_genre("onglet" if p == self.personnage else "normal")
            r = self.reglage_perso()
            self.options = [(self.tr(self._cle_tenue(self.personnage, x)), x) for x in A.TENUES[self.personnage]]
            self.liste.configure(values=[lib for lib, _x in self.options])
            self.v_tenue.set(next(lib for lib, x in self.options if x == r["tenue"]))
            if r["tenue"] == "teinte":
                self.v_teinte.set(r["teinte"])
            elif "teinte" in self.reglage.get(self.personnage, {}):
                v = self.reglage[self.personnage]["teinte"]
                self.v_teinte.set(int(v) % 360 if isinstance(v, (int, float)) and not isinstance(v, bool)
                                  else A.TEINTE_DEFAUT)
            self.montrer_teinte(r["tenue"] == "teinte")
            self.montrer_cachee(r["tenue"] in A.CACHEES)
            self.maj_temoin()
        finally:
            self._remplissage = False
        self.maj_import()
        self.maj_etat()
        if self.actif:
            self.demander_apercu()

    def montrer_teinte(self, oui: bool) -> None:
        try:
            self.cadre_teinte.grid() if oui else self.cadre_teinte.grid_remove()
        except tk.TclError:
            return
        self.replanifier()

    def montrer_cachee(self, oui: bool) -> None:
        try:
            self.lab_cachee.grid() if oui else self.lab_cachee.grid_remove()
        except tk.TclError:
            return
        self.replanifier()

    def maj_temoin(self) -> None:
        d = int(self.v_teinte.get()) % 360
        self.v_teinte_txt.set(self.tr("app_teinte_valeur", deg=d))
        self.temoin.delete("all")
        px = self.T.px
        self.temoin.create_rectangle(1, 1, px(21), px(15), fill=couleur_teinte(d), outline=th.NOIR)

    def tenue_choisie(self) -> str:
        lib = self.v_tenue.get()
        return next((x for l2, x in self.options if l2 == lib), "origine")

    # ------------------------------------------------------------------ saisie
    def choisir_personnage(self, personnage: str) -> None:
        if personnage == self.personnage:
            return
        self.annuler_attente()
        self.personnage = personnage
        self.poser()

    def _ecrire(self, tenue: str) -> None:
        r = {"tenue": tenue}
        if tenue == "teinte" or "teinte" in self.reglage.get(self.personnage, {}):
            r["teinte"] = int(self.v_teinte.get()) % 360          # la teinte est gardée même hors « personnalisée »
        self.reglage[self.personnage] = r
        self.memoriser({p: dict(v) for p, v in self.reglage.items()})
        self.maj_etat()
        if self.actif:
            self.demander_apercu()

    def saisie_tenue(self) -> None:
        if self._remplissage:
            return
        self.annuler_attente()
        tenue = self.tenue_choisie()
        self.montrer_teinte(tenue == "teinte")
        self.montrer_cachee(tenue in A.CACHEES)
        self._ecrire(tenue)
        self.maj_import()

    def saisie_teinte(self) -> None:
        if self._remplissage:
            return
        self.maj_temoin()
        self.annuler_attente(ecrire=False)
        self._apres_teinte = self.racine.after(DELAI_TEINTE, self.valider_teinte)

    def valider_teinte(self) -> None:
        self._apres_teinte = None
        if self.tenue_choisie() == "teinte":
            self._ecrire("teinte")

    def annuler_attente(self, ecrire: bool = True) -> None:
        """Arrête l'attente du curseur ; `ecrire` : la teinte en attente est mémorisée tout de suite (changement de
        personnage, de tenue : un mouvement de curseur n'est jamais perdu)."""
        if self._apres_teinte is not None:
            try:
                self.racine.after_cancel(self._apres_teinte)
            except tk.TclError:
                pass
            self._apres_teinte = None
            if ecrire and self.tenue_choisie() == "teinte":
                self._ecrire("teinte")

    def remettre_origine(self) -> None:
        self.annuler_attente()
        self.reglage.pop(self.personnage, None)
        self.memoriser({p: dict(v) for p, v in self.reglage.items()})
        self.poser()

    # ------------------------------------------------------------------ mod importé
    def maj_import(self) -> None:
        """État de la carte d'import d'après le manifeste et `config.json` (relus)."""
        if self.importeur is None:
            return
        try:
            m = self.importeur.manifeste()
            actif = bool(self.importeur.actif())
        except Exception as e:  # noqa: BLE001 - affichage seulement
            m, actif = None, False
            self.v_imp_resultat.set(self.tr("app_imp_erreur", detail=str(e)))
        self.manifeste_import = m
        if self.import_en_cours:
            self.v_imp.set(self.tr("app_imp_en_cours"))
        elif m:
            self.v_imp.set(self.tr("app_imp_present", nom=m.get("nom", "?"), date=m.get("date", "")))
        else:
            self.v_imp.set(self.tr("app_imp_aucun"))
        self.v_imp_actif.set(bool(m) and actif)
        libre = not self.import_en_cours
        self.b_imp_actif.state(["!disabled" if m and libre else "disabled"])
        self.b_imp_retirer.state(["!disabled" if m and libre else "disabled"])
        for b in (self.b_imp_fichier, self.b_imp_dossier):
            b.state(["!disabled" if libre else "disabled"])
        if not self.import_en_cours:
            conflits = AI.conflits(m, self.reglage) if m and actif else []
            self.v_imp_resultat.set(texte_import(self.langue, m, conflits) if m else "")

    def basculer_import(self) -> None:
        if self.importeur is None:
            return
        self.importeur.changer_actif(bool(self.v_imp_actif.get()))
        self.maj_import()
        self.maj_etat()

    def _choisir_defaut(self, genre: str) -> str:
        from tkinter import filedialog
        if genre == "dossier":
            return filedialog.askdirectory(parent=self.racine, title=self.tr("app_imp_choisir_dossier"),
                                           mustexist=True) or ""
        return filedialog.askopenfilename(parent=self.racine, title=self.tr("app_imp_choisir_fichier"), filetypes=[
            (self.tr("app_imp_types"), "*.zip *.fa *.rar *.7z"), (self.tr("app_imp_tous"), "*.*")]) or ""

    def _confirmer_defaut(self, texte: str) -> bool:
        from tkinter import messagebox
        return bool(messagebox.askyesno(self.tr("app_imp_titre"), texte, parent=self.racine))

    def lancer_import(self, genre: str) -> None:
        """Choix du fichier / dossier puis analyse dans un fil de fond (la ROM et une archive complète peuvent
        prendre plusieurs secondes)."""
        if self.importeur is None or self.import_en_cours:
            return
        chemin = self.choisir(genre)
        if not chemin:
            return
        self.import_en_cours = True
        self.v_imp_resultat.set("")
        self.maj_import()

        def travail():
            try:
                self._file_imp.put((self.importeur.importer(chemin), None))
            except Exception as e:  # noqa: BLE001 - montré dans la carte
                self._file_imp.put((None, e))
        threading.Thread(target=travail, daemon=True).start()
        self.racine.after(100, self._attendre_import)

    def _attendre_import(self) -> None:
        try:
            _m, err = self._file_imp.get_nowait()
        except queue.Empty:
            try:
                self.racine.after(100, self._attendre_import)
            except tk.TclError:
                pass
            return
        self.import_en_cours = False
        self.maj_import()
        if err is not None:
            cle = getattr(err, "cle", None)
            try:
                texte = self.tr(cle, **getattr(err, "params", {})) if cle else None
            except (KeyError, IndexError, ValueError):
                texte = None
            self.v_imp_resultat.set(texte or self.tr("app_imp_erreur", detail=str(err) or type(err).__name__))
        self.maj_etat()

    def retirer_import(self) -> None:
        if self.importeur is None or self.import_en_cours or not self.manifeste_import:
            return
        if not self.confirmer(self.tr("app_imp_confirmer_retrait")):
            return
        try:
            self.importeur.retirer()
        except OSError as e:
            self.v_imp_resultat.set(self.tr("app_imp_erreur", detail=str(e)))
            return
        self.maj_import()
        self.maj_etat()

    # ------------------------------------------------------------------ état
    def maj_etat(self) -> None:
        if self.lire_etat is None:
            return
        try:
            m = self.lire_etat()
        except Exception as e:  # noqa: BLE001 - état seulement
            self.etat_cle, self.etat_params = "app_etat_inconnu", {"detail": str(e)}
        else:
            self.etat_cle, self.etat_params = m.cle, dict(m.params)
        self.v_etat.set(self.tr(self.etat_cle, **self.etat_params))
        self.pastille.niveau(NIVEAUX.get(self.etat_cle, "neutre"))

    # ------------------------------------------------------------------ aperçu
    def activer(self, actif: bool) -> None:
        """Sous-onglet affiché ou non : l'aperçu n'est calculé que lorsqu'il est affiché."""
        self.actif = actif
        if actif:
            self.relire()

    def demander_apercu(self) -> None:
        r = self.reglage_perso()
        cle = (self.personnage, A.empreinte_personnage(self.personnage, r))
        self._voulu = cle
        rom = self.rom() or ""
        p = chemin_apercu(self.dossier, self.personnage, r)
        if p.is_file():
            self.montrer_apercu(p)
            return
        if not rom or not Path(rom).is_file():
            self.image, self.apercu_png = None, None
            self.lab_image.configure(image="")
            self.v_apercu.set(self.tr("app_apercu_sans_rom"))
            return
        self.v_apercu.set(self.tr("app_apercu_calcul"))
        if self._calcul is not None:                       # un calcul tourne : il relancera le suivant à sa fin
            return
        self._lancer(cle, rom, r)

    def _lancer(self, cle, rom, reglage) -> None:
        self._calcul = cle
        personnage = cle[0]

        def travail():
            try:
                self._file.put((cle, self.fonction_apercu(rom, self.dossier, personnage, reglage), None))
            except Exception as e:  # noqa: BLE001 - montré dans l'onglet
                self._file.put((cle, None, e))
        threading.Thread(target=travail, daemon=True).start()
        self.racine.after(80, self._attendre)

    def _attendre(self) -> None:
        try:
            cle, png, err = self._file.get_nowait()
        except queue.Empty:
            try:
                self.racine.after(80, self._attendre)
            except tk.TclError:
                pass
            return
        self._calcul = None
        if cle != self._voulu:                             # réglage changé pendant le calcul : le suivant
            if self.actif:
                self.demander_apercu()
            return
        if err is not None:
            self.v_apercu.set(self.tr("app_apercu_erreur", detail=str(err)))
            return
        self.montrer_apercu(png)

    def montrer_apercu(self, png: Path) -> None:
        try:
            img = tk.PhotoImage(master=self.racine, file=str(png))
        except tk.TclError as e:
            self.v_apercu.set(self.tr("app_apercu_erreur", detail=str(e)))
            return
        self.image, self.apercu_png = img, Path(png)
        self.lab_image.configure(image=img)
        self.v_apercu.set(self.tr("app_apercu_note"))
        self.replanifier()
