"""Onglet « Réglages » du lanceur : réglages de Zakuro (version PC du jeu), au lieu d'Échap → Settings dans sa fenêtre.

Toute la lecture et l'écriture de `settings.toml` est dans `reglages_zakuro.py` (sans affichage) ; ici : le formulaire,
ce qui a changé, l'état. Le fichier n'est lu qu'à la première ouverture de l'onglet, puis relu (taille et date) toutes
les 1,5 s tant que l'onglet est affiché et que le formulaire n'est pas modifié. « Enregistrer » n'écrit que les
réglages changés dans le formulaire (et rien s'ils ont déjà ces valeurs dans le fichier).
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from . import reglages_zakuro as RZ
from . import theme as th
from .textes import t

INTERVALLE = 1500                         # ms entre deux contrôles du fichier (onglet affiché seulement)
VOLUMES = tuple(range(0, 101, 10))        # pourcentages proposés


class OngletReglagesZakuro:
    """Deux cartes de la page « reglages » de la scène : le formulaire (colonne gauche) et l'aide (colonne droite).

    zakuro_fourni() : Zakuro est-il fourni avec ce lanceur ; emulateur() : "zakuro" ou "azahar" ;
    zakuro_ouvert() : un Zakuro tourne-t-il (None : inconnu) ; verrou() : verrou du lanceur pour l'écriture."""

    def __init__(self, sc: th.Scene, T: th.Theme, langue: str, *, chemin: Path | None = None,
                 zakuro_fourni: Callable[[], bool] = lambda: True,
                 emulateur: Callable[[], str] = lambda: "zakuro",
                 zakuro_ouvert: Callable[[], bool | None] = lambda: None,
                 verrou: Callable[[], object] | None = None):
        self.sc, self.T, self.langue = sc, T, langue
        self.chemin = RZ.chemin_reglages() if chemin is None else chemin
        self.zakuro_fourni, self.emulateur, self.zakuro_ouvert, self.verrou = (zakuro_fourni, emulateur,
                                                                               zakuro_ouvert, verrou)
        self.racine = sc.r
        self.lecture: RZ.Lecture | None = None
        self.base: dict = {}                         # valeurs montrées après la dernière lecture
        self.actif = False
        self._apres = None
        self._remplissage = False
        self.change_dehors = False                   # fichier changé pendant une modification du formulaire
        self.etat_cle, self.etat_niveau, self.etat_params = "", None, {}
        self.vars: dict[str, tk.Variable] = {}
        self.choix: dict[str, list[tuple[str, object]]] = {}     # libellé ↔ valeur, par réglage à liste
        self.listes: dict[str, ttk.Combobox] = {}
        self.v_etat = tk.StringVar(self.racine)
        self.v_chemin = tk.StringVar(self.racine)
        self.v_note = tk.StringVar(self.racine)
        self.v_emu = tk.StringVar(self.racine)
        self.construire()

    def tr(self, cle: str, **p) -> str:
        return t(self.langue, cle, **p)

    # ------------------------------------------------------------------ construction
    def construire(self) -> None:
        T, px, sc = self.T, self.T.px, self.sc
        th.styler_ttk(self.racine, T)
        c = self.corps = sc.carte(self.tr("rz_titre"))
        form = tk.Frame(c, bg=th.BLANC)
        form.grid(row=0, column=0, columnspan=3, sticky="ew")
        form.columnconfigure(1, weight=1)
        r = 0

        def liste(cle: str, options: list[tuple[str, object]], indice: str | None = None):
            nonlocal r
            tk.Label(form, text=self.tr(f"rz_{cle}"), font=T["texte"], bg=th.BLANC, fg=th.TEXTE, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, px(10)), pady=px(3))
            var = self.vars[cle] = tk.StringVar(self.racine)
            cb = ttk.Combobox(form, state="readonly", style="Yokai.TCombobox", font=T["texte"], textvariable=var,
                              width=max(len(lib) for lib, _v in options) + 2)
            cb.grid(row=r, column=1, sticky="w", pady=px(3))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.saisie())
            self.choix[cle], self.listes[cle] = options, cb
            cb.configure(values=[lib for lib, _v in options])
            r += 1
            if indice:
                self._indice(form, r, indice)
                r += 1

        def bascule(cle: str, indice: str | None = None):
            nonlocal r
            var = self.vars[cle] = tk.BooleanVar(self.racine)
            b = th.Bascule(form, T, self.tr(f"rz_{cle}"), var, commande=self.saisie)
            b.grid(row=r, column=0, columnspan=2, sticky="w", pady=(px(3), 0))
            r += 1
            if indice:
                self._indice(form, r, indice)
                r += 1

        def defaut(cle, lib, valeur):
            return self.tr("rz_defaut", valeur=lib) if RZ.PAR_CLE[cle].defaut == valeur else lib

        liste("language", [(defaut("language", self.tr(f"rz_lang_{v}"), v), v) for v in RZ.LANGUES_JEU])
        liste("resolution", [(defaut("resolution", self.tr("rz_resolution_1") if n == 1 else self.tr("rz_fois", n=n),
                                     n), n) for n in range(1, 9)], "rz_indice_resolution")
        bascule("frame_interpolation", "rz_indice_interpolation")
        self.lab_gpu = self._indice(form, r, "", couleur=th.ROUGE_SOMBRE, variable=self.v_note)
        r += 1

        def montrer_note(*_a):
            try:
                self.lab_gpu.grid() if self.v_note.get() else self.lab_gpu.grid_remove()
                self.replanifier()
            except tk.TclError:
                pass
        self.v_note.trace_add("write", montrer_note)
        montrer_note()
        liste("scale", [(defaut("scale", self.tr("rz_fois", n=n), n), n) for n in range(1, 7)])
        liste("layout", [(defaut("layout", self.tr(f"rz_layout_{v}"), v), v) for v in RZ.DISPOSITIONS])
        liste("filter", [(defaut("filter", self.tr(f"rz_filter_{v}"), v), v) for v in RZ.FILTRES])
        bascule("integer_scale")
        liste("screen_alignment", [(defaut("screen_alignment", self.tr(f"rz_screen_alignment_{v}"), v), v)
                                   for v in RZ.ALIGNEMENTS], "rz_indice_alignement")
        liste("volume", [(defaut("volume", f"{p} %", p / 100), p / 100) for p in VOLUMES])
        bascule("mute")
        bascule("show_fps")
        largeur = max(max(len(lib) for lib, _v in o) for o in self.choix.values()) + 2
        for cb in self.listes.values():                 # listes de même largeur
            cb.configure(width=largeur)
        # boutons
        bas = tk.Frame(c, bg=th.BLANC)
        bas.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(px(8), px(2)))
        self.b_enregistrer = th.Pilule(bas, T, self.tr("rz_enregistrer"), self.enregistrer, genre="or")
        self.b_enregistrer.pack(side="right")
        self.b_annuler = th.Pilule(bas, T, self.tr("rz_annuler"), self.annuler)
        self.b_annuler.pack(side="right", padx=(0, px(4)))
        self.b_defauts = th.Pilule(bas, T, self.tr("rz_defauts"), self.defauts, genre="clair",
                                   police="bouton_petit", padx=10, pady=3)
        self.b_defauts.pack(side="left")
        self.boutons = [self.b_enregistrer, self.b_annuler, self.b_defauts]
        # état
        self.pastille = th.Pastille(c, T)
        haut = px(4) + max(0, (T["texte"].metrics("linespace") - self.pastille.d) // 2)
        self.pastille.grid(row=2, column=0, sticky="nw", pady=(haut, 0), padx=(0, px(8)))
        lab = tk.Label(c, textvariable=self.v_etat, font=T["texte"], bg=th.BLANC, fg=th.TEXTE, justify="left",
                       anchor="w")
        lab.grid(row=2, column=1, columnspan=2, sticky="w", pady=(px(3), px(2)))
        sc.texte_extensible(lab, self.pastille.d + px(12))
        self.v_etat.trace_add("write", lambda *_a: self.replanifier())
        # aide (colonne droite)
        a = sc.carte(self.tr("rz_aide_titre"), colonne="d")
        lc = th.LabelChemin(a, self.v_chemin, T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX)
        lc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, px(4)))
        sc.texte_extensible(lc, px(4))
        n = 1
        lab_emu = tk.Label(a, textvariable=self.v_emu, font=T["texte"], bg=th.BLANC, fg=th.ROUGE_SOMBRE,
                           justify="left", anchor="w")
        lab_emu.grid(row=n, column=0, columnspan=3, sticky="w", pady=px(3))
        sc.texte_extensible(lab_emu, px(4))
        self.v_emu.trace_add("write", lambda *_a: self.replanifier())
        for cle in ("rz_aide_lancement", "rz_aide_fenetre", "rz_aide_touches", "rz_aide_controles"):
            n += 1
            lab = tk.Label(a, text=self.tr(cle), font=T["texte"], bg=th.BLANC, fg=th.TEXTE, justify="left",
                           anchor="w")
            lab.grid(row=n, column=0, columnspan=3, sticky="w", pady=px(3))
            sc.texte_extensible(lab, px(4))
        self.v_chemin.set(self.tr("rz_fichier", chemin=str(self.chemin) if self.chemin else "?"))
        self.maj_boutons()

    def replanifier(self) -> None:
        """Un texte a changé de hauteur : mise en page refaite après le calcul des hauteurs par Tk (le cadre d'une
        carte a une hauteur fixée par la scène, son <Configure> ne suffit pas ; même règle que `vue.replanifier`)."""
        try:
            self.racine.after(30, self.sc.planifier)
        except tk.TclError:
            pass

    def _indice(self, parent, r, cle, couleur=th.TEXTE_DOUX, variable: tk.StringVar | None = None) -> tk.Label:
        lab = tk.Label(parent, text=self.tr(cle) if cle else "", font=self.T["petit"], bg=th.BLANC, fg=couleur,
                       justify="left", anchor="w")
        if variable is not None:
            lab.configure(textvariable=variable)
        lab.grid(row=r, column=0, columnspan=2, sticky="w", padx=(self.T.px(28), 0), pady=(0, self.T.px(2)))
        self.sc.texte_extensible(lab, self.T.px(32))
        return lab

    # ------------------------------------------------------------------ valeurs du formulaire
    def _poser(self, valeurs: dict) -> None:
        self._remplissage = True
        try:
            for r in RZ.REGLAGES:
                v = valeurs[r.cle]
                if r.genre == "booleen":
                    self.vars[r.cle].set(bool(v))
                    continue
                options = self.choix[r.cle]
                lib = next((lib for lib, x in options if self._meme(r.cle, x, v)), None)
                if lib is None:                       # valeur du fichier hors des propositions : montrée telle quelle
                    lib = self._libelle_hors(r.cle, v)
                    options.append((lib, v))
                    self.listes[r.cle].configure(values=[x for x, _v in options])
                self.vars[r.cle].set(lib)
        finally:
            self._remplissage = False

    def _libelle_hors(self, cle: str, v) -> str:
        if cle == "language":
            return self.tr(f"rz_lang_{v}") if isinstance(v, str) else str(v)
        if cle == "volume":
            return f"{round(v * 100)} %"
        return self.tr("rz_fois", n=v) if cle in ("resolution", "scale") else str(v)

    @staticmethod
    def _meme(cle: str, a, b) -> bool:
        if cle == "volume":
            return abs(float(a) - float(b)) < 0.005
        return a == b

    def valeurs(self) -> dict:
        """Valeurs du formulaire, dans les types de `reglages_zakuro`."""
        d = {}
        for r in RZ.REGLAGES:
            var = self.vars[r.cle]
            if r.genre == "booleen":
                d[r.cle] = bool(var.get())
            else:
                lib = var.get()
                d[r.cle] = next((x for l2, x in self.choix[r.cle] if l2 == lib), self.base.get(r.cle, r.defaut))
        return d

    def modifies(self) -> dict:
        """Réglages changés dans le formulaire depuis la dernière lecture du fichier."""
        return {k: v for k, v in self.valeurs().items() if not self._meme(k, v, self.base.get(k))}

    # ------------------------------------------------------------------ lecture
    def activer(self, oui: bool) -> None:
        self.actif = oui
        if oui:
            if self.lecture is None:
                self.relire()
            self.v_emu.set("" if self.zakuro_fourni() and self.emulateur() == "zakuro" else
                           self.tr("rz_aide_azahar" if self.zakuro_fourni() else "rz_aide_sans_zakuro"))
            self._programmer()
        elif self._apres is not None:
            try:
                self.racine.after_cancel(self._apres)
            except tk.TclError:
                pass
            self._apres = None

    def _programmer(self) -> None:
        if self._apres is None and self.actif:
            self._apres = self.racine.after(INTERVALLE, self._controler)

    def _controler(self) -> None:
        self._apres = None
        try:
            if self.lecture is not None and RZ.signature(self.chemin) != self.lecture.signature:
                if self.modifies():
                    self.change_dehors = True
                    self.etat("rz_etat_change", "attention")
                else:
                    self.relire(garder_etat=True)
        except tk.TclError:
            return
        self._programmer()

    def relire(self, garder_etat: bool = False) -> None:
        """Relit le fichier et remet le formulaire à ses valeurs."""
        lec = self.lecture = RZ.lire(self.chemin)
        self.base = dict(lec.valeurs)
        self.change_dehors = False
        self._poser(lec.valeurs)
        notes = []
        if not lec.gpu_3d:
            notes.append(self.tr("rz_sans_gpu"))
        elif not lec.vulkan:
            notes.append(self.tr("rz_sans_vulkan"))
        self.v_note.set("\n".join(notes))
        if not garder_etat or lec.erreur:
            self.etat_lecture()
        self.maj_boutons()

    def etat_lecture(self) -> None:
        lec = self.lecture
        if lec is None:
            return
        if lec.erreur:
            self.etat(lec.erreur, "erreur")
        elif lec.rejete:
            self.etat("rz_rejete", "attention")
        elif lec.hors_bornes:
            self.etat("rz_hors_bornes", "attention", cles=", ".join(sorted(lec.hors_bornes)))
        elif lec.existe:
            self.etat("rz_etat_lu", "ok")
        else:
            self.etat("rz_etat_absent", "neutre")

    def etat(self, cle: str, niveau: str | None, **params) -> None:
        self.etat_cle, self.etat_niveau, self.etat_params = cle, niveau, params
        self.v_etat.set(self.tr(cle, **params))
        self.pastille.niveau(niveau)

    def maj_boutons(self) -> None:
        illisible = self.lecture is not None and self.lecture.erreur is not None
        modifie = bool(self.modifies()) if self.vars and self.lecture is not None else False
        self.b_enregistrer.state(["!disabled" if modifie and not illisible else "disabled"])
        self.b_annuler.state(["!disabled" if modifie else "disabled"])
        self.b_defauts.state(["disabled" if illisible else "!disabled"])
        for cb in self.listes.values():
            cb.configure(state="disabled" if illisible else "readonly")

    # ------------------------------------------------------------------ actions
    def saisie(self) -> None:
        if self._remplissage:
            return
        if self.modifies():
            if not self.change_dehors:
                self.etat("rz_etat_modifie", "attention")
        else:
            self.change_dehors = False
            self.etat_lecture()
        self.maj_boutons()

    def annuler(self) -> None:
        self.relire()

    def defauts(self) -> None:
        self._poser(RZ.valeurs_par_defaut())
        self.saisie()

    def enregistrer(self) -> bool:
        """Écrit les réglages changés ; renvoie True si le fichier a été écrit."""
        changes = self.modifies()
        if not changes:
            return False
        try:
            ecrits = RZ.ecrire(self.chemin, changes, verrou=self.verrou)
        except RZ.ErreurReglages as e:
            self.etat(e.cle, "erreur")
            self.maj_boutons()
            return False
        self.relire()
        if not ecrits:
            self.etat("rz_etat_rien", "neutre")
            return False
        ouvert = False
        try:
            ouvert = bool(self.zakuro_ouvert())
        except Exception:                                            # noqa: BLE001 - simple avertissement
            pass
        self.etat("rz_etat_ouvert" if ouvert else "rz_etat_enregistre", "attention" if ouvert else "ok")
        return True
