"""Onglet « Yo-kai » du lanceur (tracker de Yo-kai, R5) : vue tkinter seulement. Données et filtres : `tracker.py` ;
textes : `presentation.py` / `textes.py` ; dessin : `theme.py`.

Le tracker relit les fichiers locaux (`yokai_local.json`, `rando_yokai.json`, `medaillium.json`, `noms_local.json`,
`progression.json`) quand leur taille ou leur date change (toutes les 1,5 s) et garde les lignes dépliées, la sélection et le défilement.
Les noms des cartes et des tribus sont lus dans la ROM du joueur (`noms_locaux.py`) en tâche de fond s'ils manquent,
comme la base locale (`installation/rencontres.py`) si la ROM est configurée (absente, ou d'un format antérieur).

Clavier : Tab / Maj+Tab entre les champs, Ctrl+F (recherche), Échap (vide la recherche), Flèche bas (vers la liste),
Entrée ou Espace sur une ligne (déplier / replier, dévoiler une ligne masquée), Ctrl+Tab (onglet suivant, `vue.py`).
"""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from . import presentation as P
from . import theme as th
from . import tracker as TK
from .textes import t

INTERVALLE = 1500                         # ms entre deux contrôles des fichiers


def cle_lieu(y: TK.Yokai, l: TK.Lieu) -> str:
    """Identifiant stable d'un emplacement (dévoilement anti-divulgâchage), le même dans les deux vues."""
    return f"{y.cle}|{l.carte}|{l.methode}|{l.a_la_place_de}|{'.'.join(l.conditions)}"


class Placeholder(tk.Entry):
    """Champ de saisie avec texte d'invite gris quand il est vide et sans focus. `valeur()` ignore l'invite."""

    def __init__(self, parent, theme: th.Theme, invite: str, variable: tk.StringVar, **kw):
        px = theme.px
        super().__init__(parent, font=theme["texte"], bg=th.BLANC, fg=th.TEXTE, relief="flat", bd=0,
                         highlightthickness=px(2), highlightbackground=th.NOIR, highlightcolor=th.FOCUS,
                         insertbackground=th.NOIR, **kw)
        self.invite, self.var, self._invite_visible = invite, variable, False
        self.bind("<FocusIn>", lambda _e: self._cacher())
        self.bind("<FocusOut>", lambda _e: self._montrer())
        self._montrer()

    def valeur(self) -> str:
        return "" if self._invite_visible else self.get()

    def changer_invite(self, invite: str) -> None:
        cache = self._invite_visible
        self.invite = invite
        if cache:
            self.delete(0, "end")
            self.insert(0, invite)

    def vider(self) -> None:
        self.delete(0, "end")
        if self.focus_get() is not self:
            self._montrer()

    def _montrer(self):
        if not self.get():
            self._invite_visible = True
            self.configure(fg=th.INACTIF_TEXTE)
            self.insert(0, self.invite)

    def _cacher(self):
        if self._invite_visible:
            self._invite_visible = False
            self.delete(0, "end")
            self.configure(fg=th.TEXTE)


class OngletYokai:
    """Contenu de l'onglet (cadre blanc posé dans une carte pleine de la `Scene`)."""

    def __init__(self, scene: th.Scene, theme: th.Theme, langue: str, dossier: Path,
                 rom: Callable[[], str | None] = lambda: None, paresseux: bool = False,
                 epingle: str = "", memoriser_epingle: Callable[[str], object] | None = None):
        """`paresseux` (fenêtre du lanceur) : les fichiers de données ne sont pas lus à la construction (onglet
        caché au démarrage) mais à la première ouverture de l'onglet, ou au premier contrôle périodique.
        `epingle` / `memoriser_epingle` : Yo-kai épinglé (clé du tracker, "" : aucun), mémorisé par le lanceur
        (`config.json`) ; ses points d'apparition sont montrés par le sous-onglet « Carte » de l'onglet « Checks »."""
        self.sc, self.th, self.langue, self.dossier, self.rom = scene, theme, langue, Path(dossier), rom
        self.epingle = str(epingle or "")
        self.memoriser_epingle = memoriser_epingle or (lambda _cle: None)
        self.yokai_de: dict[str, str] = {}    # ligne de la vue « Par lieu » -> clé du Yo-kai
        self.modele: TK.Modele = TK.Modele(False, TK.etat_melange(None), {}, False)
        self.signature = None
        self.visible = False
        self.a_refaire = True
        self.vue = "yokai"                    # yokai | lieu | boss
        self.devoiles: set[str] = set()
        self.enfants: dict[str, Callable[[], None]] = {}     # iid -> remplissage paresseux des enfants
        self.masques: dict[str, Callable[[], None]] = {}     # iid -> dévoilement
        self._generation_lancee = False
        self._fil: threading.Thread | None = None
        self.v_texte = tk.StringVar(scene.r)
        self.v_non_vus = tk.BooleanVar(scene.r, value=False)
        self.v_non_amis = tk.BooleanVar(scene.r, value=False)
        self.v_acces = tk.BooleanVar(scene.r, value=False)
        self.v_anti = tk.BooleanVar(scene.r, value=False)
        th.styler_ttk(scene.r, theme)
        self.construire()
        if paresseux:                         # état « sans données » cohérent en attendant la lecture
            self._maj_listes()
            self._maj_etat()
            self.remplir()
        else:
            self.recharger(force=True)
        self.cadre.after(INTERVALLE, self._surveiller)

    def tr(self, cle: str, **p) -> str:
        return t(self.langue, cle, **p)

    # ------------------------------------------------------------------ construction
    def construire(self) -> None:
        T, px = self.th, self.th.px
        f = self.cadre = tk.Frame(self.sc.c, bg=th.BLANC)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(3, weight=1)
        # en-tête : titre et choix de la vue
        tete = tk.Frame(f, bg=th.BLANC)
        tete.grid(row=0, column=0, sticky="ew")
        th.Badge(tete, T, None).pack(side="left")
        tk.Label(tete, text=self.tr("yk_titre"), font=T["carte"], bg=th.BLANC, fg=th.NOIR).pack(
            side="left", padx=(px(8), 0))
        self.b_vues = {}
        for cle, texte in (("boss", self.tr("yk_par_boss")), ("lieu", self.tr("yk_par_lieu")),
                           ("yokai", self.tr("yk_par_yokai"))):
            b = th.Pilule(tete, T, texte, lambda k=cle: self.changer_vue(k), police="bouton_petit",
                          padx=12, pady=3, genre="onglet" if cle == self.vue else "normal")
            b.pack(side="right", padx=(px(2), 0))
            self.b_vues[cle] = b
        # filtres
        fl = tk.Frame(f, bg=th.BLANC)
        fl.grid(row=1, column=0, sticky="ew", pady=(px(8), 0))
        fl.columnconfigure(0, weight=1)
        self.e_texte = Placeholder(fl, T, self.tr("yk_recherche"), self.v_texte)
        self.e_texte.grid(row=0, column=0, sticky="ew", ipady=px(3), padx=(0, px(8)))
        self.e_texte.bind("<KeyRelease>", lambda _e: self.planifier())
        self.e_texte.bind("<Escape>", lambda _e: (self.e_texte.delete(0, "end"), self.planifier()))
        self.e_texte.bind("<Down>", lambda _e: self._vers_liste())
        self.listes: dict[str, ttk.Combobox] = {}
        for i, (cle, largeur) in enumerate((("rang", 13), ("tribu", 15), ("methode", 18), ("region", 22))):
            cb = ttk.Combobox(fl, state="readonly", style="Yokai.TCombobox", font=T["texte"], width=largeur)
            cb.grid(row=0, column=1 + i, sticky="e", padx=(0 if i == 0 else px(6), 0))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.planifier())
            self.listes[cle] = cb
        # options
        op = tk.Frame(f, bg=th.BLANC)
        op.grid(row=2, column=0, sticky="ew", pady=(px(6), px(6)))
        self.b_non_vus = th.Bascule(op, T, self.tr("yk_non_vus"), self.v_non_vus, self.planifier)
        self.b_non_vus.pack(side="left")
        self.b_non_amis = th.Bascule(op, T, self.tr("yk_non_amis"), self.v_non_amis, self.planifier)
        self.b_non_amis.pack(side="left", padx=(px(14), 0))
        self.b_acces = th.Bascule(op, T, self.tr("yk_accessibles"), self.v_acces, self.planifier)
        self.b_acces.pack(side="left", padx=(px(14), 0))
        self.b_anti = th.Bascule(op, T, self.tr("yk_anti"), self.v_anti, self.planifier)
        self.b_anti.pack(side="left", padx=(px(14), 0))
        self.l_compte = tk.Label(op, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX)
        self.l_compte.pack(side="right")
        # liste
        cadre_liste = tk.Frame(f, bg=th.NOIR, padx=px(2), pady=px(2))
        cadre_liste.grid(row=3, column=0, sticky="nsew")
        cadre_liste.columnconfigure(0, weight=1)
        cadre_liste.rowconfigure(0, weight=1)
        cols = ("rang", "tribu", "info", "vu", "ami")
        self.arbre = a = ttk.Treeview(cadre_liste, columns=cols, style="Yokai.Treeview", height=6,
                                      selectmode="browse")
        a.grid(row=0, column=0, sticky="nsew")
        defil = ttk.Scrollbar(cadre_liste, orient="vertical", command=a.yview, style="Yokai.Vertical.TScrollbar")
        defil.grid(row=0, column=1, sticky="ns")
        a.configure(yscrollcommand=defil.set)
        a.column("#0", width=px(290), minwidth=px(140), stretch=False)
        a.column("rang", width=px(60), minwidth=px(44), anchor="center", stretch=False)
        a.column("tribu", width=px(104), minwidth=px(60), stretch=False)
        a.column("info", width=px(360), minwidth=px(160), stretch=True)
        a.column("vu", width=px(52), minwidth=px(40), anchor="center", stretch=False)
        a.column("ami", width=px(52), minwidth=px(40), anchor="center", stretch=False)
        for cle, texte in (("rang", "yk_col_rang"), ("tribu", "yk_col_tribu"), ("info", "yk_col_info"),
                           ("vu", "yk_col_vu"), ("ami", "yk_col_ami")):
            a.heading(cle, text=self.tr(texte), anchor="center" if cle in ("rang", "vu", "ami") else "w")
        a.tag_configure("yokai", font=T["bouton"])
        a.tag_configure("region", font=T["bouton"], background=th.OR_CLAIR)
        a.tag_configure("carte", font=T["bouton_petit"], background=th.CYAN_PALE)
        a.tag_configure("pair", background="#FFFAF3")
        a.tag_configure("masque", foreground=th.INACTIF_TEXTE)
        a.tag_configure("vide", foreground=th.TEXTE_DOUX)
        a.tag_configure("amitie", foreground=th.TEXTE_DOUX)
        a.bind("<Configure>", self._colonnes, add="+")
        a.bind("<<TreeviewOpen>>", lambda _e: self._ouvrir(a.focus()))
        a.bind("<ButtonRelease-1>", self._clic)
        a.bind("<<TreeviewSelect>>", lambda _e: self._maj_epingle(), add="+")
        a.bind("<Return>", self._entree)
        a.bind("<KP_Enter>", self._entree)
        a.bind("<space>", self._entree)
        # état
        self.cadre_etat = tk.Frame(f, bg=th.BLANC)
        self.cadre_etat.grid(row=4, column=0, sticky="ew", pady=(px(8), 0))
        self.cadre_etat.columnconfigure(1, weight=1)
        bas = tk.Frame(f, bg=th.BLANC)
        bas.grid(row=5, column=0, sticky="ew", pady=(px(4), 0))
        bas.columnconfigure(0, weight=1)
        self.l_aide = tk.Label(bas, text=self.tr("yk_aide_clavier"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                               anchor="w")
        self.l_aide.grid(row=0, column=0, sticky="ew")
        # Yo-kai épinglé sur la carte (un seul) : nom de l'épinglé, bouton qui agit sur la ligne choisie
        self.l_epingle = tk.Label(bas, text="", font=T["petit"], bg=th.BLANC, fg=th.CYAN_TEXTE)
        self.l_epingle.grid(row=0, column=1, sticky="e", padx=(px(8), px(8)))
        largeur = max(T["bouton_petit"].measure(self.tr(k)) for k in ("yk_epingler", "yk_desepingler")) + 2 * px(10)
        self.b_epingler = th.Pilule(bas, T, self.tr("yk_epingler"), self.basculer_epingle, police="bouton_petit",
                                    padx=10, pady=1, largeur_min=largeur)
        self.b_epingler.grid(row=0, column=2, sticky="e")
        self.lignes_etat: list[tuple[th.Pastille, tk.Label]] = []
        f.bind("<Configure>", self._largeur, add="+")

    def _colonnes(self, _e=None) -> None:
        """Colonne « Où, comment » : toute la largeur restante (aucune colonne coupée à droite)."""
        a, px = self.arbre, self.th.px
        try:
            w = a.winfo_width()
            if w <= 1:
                return
            fixes = sum(int(a.column(c, "width")) for c in ("#0",) + tuple(a["displaycolumns"]) if c != "info")
            a.column("info", width=max(px(160), w - fixes - px(2)))
        except tk.TclError:
            pass

    def _largeur(self, e=None) -> None:
        lg = max(self.th.px(200), self.cadre.winfo_width() - self.th.px(30))
        for _p, lab in self.lignes_etat:
            lab.configure(wraplength=lg)

    # ------------------------------------------------------------------ données
    def activer(self, visible: bool) -> None:
        self.visible = visible
        if visible:
            self.recharger()                  # pas encore lues (onglet paresseux), ou changées depuis le dernier contrôle
            self._generer_si_besoin()
            if self.a_refaire:
                self.remplir()

    def _surveiller(self) -> None:
        try:
            if not self.cadre.winfo_exists():
                return
        except tk.TclError:
            return
        self.recharger()
        self.cadre.after(INTERVALLE, self._surveiller)

    def recharger(self, force: bool = False) -> None:
        sig = TK.signature(self.dossier)
        if not force and sig == self.signature:
            return
        self.signature = sig
        self.modele = TK.charger(self.dossier)
        self._maj_listes()
        self._maj_etat()
        self.a_refaire = True
        if self.visible or force:
            self.remplir()
        else:
            self._maj_epingle()

    # ------------------------------------------------------------------ Yo-kai épinglé
    def yokai_epingle(self) -> TK.Yokai | None:
        """Yo-kai épinglé dans le modèle courant (None : aucun, ou inconnu de la base chargée)."""
        return self.modele.yokai.get(self.epingle) if self.epingle else None

    def yokai_choisi(self) -> TK.Yokai | None:
        """Yo-kai de la ligne choisie (vue « Par Yo-kai » : sa ligne ou l'un de ses lieux ; « Par lieu » : sa ligne)."""
        sel = self.arbre.selection()
        if not sel:
            return None
        iid = sel[0]
        cle = iid.split("|")[1] if iid.startswith("y|") else self.yokai_de.get(iid)
        return self.modele.yokai.get(cle) if cle else None

    def peut_epingler(self, y: TK.Yokai | None) -> bool:
        """Anti-divulgâchage : seul un Yo-kai dont le nom est dévoilé dans l'onglet peut être épinglé."""
        return y is not None and not self.masque_nom(y, self.filtre())

    def epingler(self, cle: str | None) -> None:
        """Épingle le Yo-kai `cle` (un seul : il remplace le précédent) ; None ou "" : désépingle. Mémorisé."""
        cle = str(cle or "")
        if cle == self.epingle:
            return
        self.epingle = cle
        self.memoriser_epingle(cle)
        self.remplir()

    def basculer_epingle(self) -> None:
        y = self.yokai_choisi()
        if y is None or y.cle == self.epingle:
            self.epingler(None)
        elif self.peut_epingler(y):
            self.epingler(y.cle)

    def _maj_epingle(self) -> None:
        """Bouton « Épingler » / « Désépingler » selon la ligne choisie, et nom du Yo-kai épinglé."""
        y, ep = self.yokai_choisi(), self.yokai_epingle()
        desepingler = bool(self.epingle) and (y is None or y.cle == self.epingle)
        texte = self.tr("yk_desepingler" if desepingler else "yk_epingler")
        if self.b_epingler.texte != texte:
            self.b_epingler.changer_texte(texte)
        actif = desepingler or self.peut_epingler(y)
        if self.b_epingler.instate(["disabled"]) == actif:
            self.b_epingler.state(["!disabled"] if actif else ["disabled"])
        nom = ""
        if ep is not None:
            nom = self.tr("yk_epingle", nom=self.tr("yk_masque") if self.masque_nom(ep, self.filtre())
                          else ep.nom(self.langue))
        if self.l_epingle.cget("text") != nom:
            self.l_epingle.configure(text=nom)

    def _generer_si_besoin(self) -> None:
        """Base locale ou noms absents et ROM configurée : générés en tâche de fond (une fois par ouverture)."""
        if self._generation_lancee:
            return
        rom = self.rom()
        manque_base = not (self.dossier / TK.NOM_BASE).is_file() or (
            self.modele.base_ok and self.modele.format_base < max(TK.FORMATS_BASE))
        manque_noms = not (self.dossier / TK.NOM_NOMS).is_file()
        if not rom or not Path(rom).is_file() or not (manque_base or manque_noms):
            return
        self._generation_lancee = True

        def travail():
            try:
                if manque_noms:
                    from . import noms_locaux
                    noms_locaux.generer_fichier(rom, self.dossier)
                if manque_base:
                    from installation import rencontres
                    rencontres.generer_fichier(rom, self.dossier)
            except Exception:                           # noqa: BLE001 - le tracker reste utilisable sans
                pass
        self._fil = threading.Thread(target=travail, daemon=True)
        self._fil.start()

    # ------------------------------------------------------------------ filtres
    def _maj_listes(self) -> None:
        m, tr = self.modele, self.tr
        self.choix = {
            "rang": [(None, tr("yk_tous_rangs"))] + [(i, tr("yk_rang_n", rang=r)) for i, r in enumerate(TK.RANGS)],
            "tribu": [(None, tr("yk_toutes_tribus"))] + [(n, P.texte_tribu(self.langue, m, n))
                                                         for n in TK.tribus_presentes(m) if n in TK.TRIBUS_NOMMEES],
            "methode": [(None, tr("yk_toutes_methodes")), ("loupe", tr("yk_methode_loupe")),
                        ("errant", tr("yk_methode_errant")), ("portail", tr("yk_methode_portail")),
                        ("aucune", tr("yk_methode_aucune"))],
            "region": [(None, tr("yk_toutes_regions"))] + [(r, TK.nom_region(r, self.langue))
                                                          for r in TK.regions_presentes(m)],
        }
        for cle, cb in self.listes.items():
            actuel = self._valeur(cle) if cb.get() else None
            vals = [txt for _v, txt in self.choix[cle]]
            cb.configure(values=vals)
            cles = [v for v, _txt in self.choix[cle]]
            cb.current(cles.index(actuel) if actuel in cles else 0)
        for b, v, ok in ((self.b_non_vus, self.v_non_vus, m.medaillium), (self.b_non_amis, self.v_non_amis, m.amis),
                         (self.b_acces, self.v_acces, m.acces_connu)):
            b.state(["!disabled"] if ok else ["disabled"])
            if not ok and v.get():
                v.set(False)

    def _valeur(self, cle: str):
        cb = self.listes[cle]
        i = cb.current()
        choix = getattr(self, "choix", {}).get(cle, [])
        return choix[i][0] if 0 <= i < len(choix) else None

    def filtre(self) -> TK.Filtre:
        texte = self.e_texte.valeur().strip()
        return TK.Filtre(texte=texte if self.vue in ("yokai", "boss") else "", lieu=texte if self.vue == "lieu" else "",
                         rang=self._valeur("rang"), tribu=self._valeur("tribu"), methode=self._valeur("methode"),
                         region=self._valeur("region"), non_vus=bool(self.v_non_vus.get()),
                         non_amis=bool(self.v_non_amis.get()), accessibles=bool(self.v_acces.get()))

    def changer_vue(self, vue: str) -> None:
        if vue == self.vue:
            return
        self.vue = vue
        for cle, b in self.b_vues.items():
            b.changer_genre("onglet" if cle == vue else "normal")
        self.e_texte.changer_invite(self.tr({"yokai": "yk_recherche", "lieu": "yk_recherche_lieu"}.get(
            vue, "yk_recherche_boss")))
        self.remplir(garder=False)

    def planifier(self) -> None:
        if not getattr(self, "_prevu", False):
            self._prevu = True
            self.cadre.after(120, self._remplir_prevu)

    def _remplir_prevu(self) -> None:
        self._prevu = False
        self.remplir()

    def focus_recherche(self) -> None:
        self.e_texte.focus_set()
        self.e_texte.select_range(0, "end")

    def _vers_liste(self) -> str:
        enfants = self.arbre.get_children()
        if enfants:
            self.arbre.focus_set()
            self.arbre.focus(enfants[0])
            self.arbre.selection_set(enfants[0])
        return "break"

    # ------------------------------------------------------------------ état
    def _maj_etat(self) -> None:
        for p, lab in self.lignes_etat:
            p.destroy()
            lab.destroy()
        self.lignes_etat = []
        px = self.th.px
        for i, (texte, niveau) in enumerate(P.lignes_etat_tracker(self.langue, self.modele)):
            p = th.Pastille(self.cadre_etat, self.th)
            p.niveau(niveau)
            haut = px(3) + max(0, (self.th["texte"].metrics("linespace") - p.d) // 2)
            p.grid(row=i, column=0, sticky="nw", pady=(haut, 0), padx=(0, px(8)))
            lab = tk.Label(self.cadre_etat, text=th.insecables(texte), font=self.th["texte"], bg=th.BLANC,
                           fg=th.TEXTE, justify="left", anchor="w")
            lab.grid(row=i, column=1, sticky="w", pady=(px(2), px(1)))
            self.lignes_etat.append((p, lab))
        self._largeur()

    # ------------------------------------------------------------------ liste
    def masque_nom(self, y: TK.Yokai, f: TK.Filtre) -> bool:
        """Anti-divulgâchage : nom d'un Yo-kai jamais rencontré caché, sauf dévoilé ou cherché par son nom."""
        return bool(self.v_anti.get() and y.vu is not True and y.ami is not True and "n:" + y.cle not in self.devoiles
                    and not (f.texte and TK.replier(f.texte) in TK.replier(y.nom(self.langue))))

    def masque_corr(self, cle: str) -> bool:
        return bool(self.v_anti.get() and "c:" + cle not in self.devoiles)

    def remplir(self, garder: bool = True) -> None:
        a, m, lg = self.arbre, self.modele, self.langue
        self.a_refaire = False
        ouverts = {i for i in self._tous() if a.item(i, "open")} if garder else set()
        sel = a.selection()
        haut = a.yview()[0] if garder else 0.0
        a.delete(*a.get_children())
        self.enfants.clear()
        self.masques.clear()
        self.yokai_de.clear()
        a.heading("#0", text=self.tr({"yokai": "yk_col_nom", "lieu": "yk_col_lieu"}.get(self.vue, "yk_col_boss")),
                  anchor="w")
        a.configure(displaycolumns=("rang", "tribu", "info") + (("vu",) if m.medaillium else ())
                    + (("ami",) if m.amis else ()))
        self._colonnes()
        f = self.filtre()
        n = {"yokai": self._remplir_yokai, "lieu": self._remplir_lieux}.get(self.vue, self._remplir_boss)(f)
        if n == 0 and not a.get_children():
            a.insert("", "end", iid="vide", text="", values=("", "", self.tr("yk_aucun_resultat"), "", ""),
                     tags=("vide",))
        self.l_compte.configure(text=self.tr("yk_boss_compte" if self.vue == "boss" else "yk_compte", n=n))
        for i in sorted(ouverts, key=lambda x: x.count("|")):
            if a.exists(i):
                self._ouvrir(i)
                a.item(i, open=True)
        for i in sel:
            if a.exists(i):
                a.selection_set(i)
                a.focus(i)
        if garder:
            a.update_idletasks()
            a.yview_moveto(haut)
        self._maj_epingle()

    def _tous(self):
        pile = list(self.arbre.get_children())
        while pile:
            i = pile.pop()
            yield i
            pile.extend(self.arbre.get_children(i))

    def _ligne(self, parent: str, iid: str, texte: str, valeurs, tags, rang: int):
        tags = tuple(tags) + (("pair",) if rang % 2 else ())
        self.arbre.insert(parent, "end", iid=iid, text=texte, values=valeurs, tags=tags)

    def _textes_yokai(self, y: TK.Yokai, f: TK.Filtre, lieux) -> tuple[str, tuple, bool]:
        m, lg = self.modele, self.langue
        cache = self.masque_nom(y, f)
        nom = self.tr("yk_masque") if cache else y.nom(lg)
        vu = self.tr("yk_vu") if y.vu else ""
        ami = self.tr("yk_ami") if y.ami else ""
        if y.cle == self.epingle:                      # Yo-kai épinglé sur la carte : marque devant le nom
            nom = self.tr("yk_marque_epingle") + nom
        return "  " + nom, (y.lettre_rang, P.texte_tribu(lg, m, y.tribu), P.resume_yokai(lg, m, y, lieux), vu,
                            ami), cache

    def _remplir_yokai(self, f: TK.Filtre) -> int:
        a, m, lg = self.arbre, self.modele, self.langue
        ys = TK.filtrer(m, f, lg)
        for k, y in enumerate(ys):
            lieux = f.lieux(y)
            iid = "y|" + y.cle
            texte, valeurs, cache = self._textes_yokai(y, f, lieux)
            self._ligne("", iid, texte, valeurs, ("yokai",) + (("masque",) if cache else ()), k)
            if cache:
                self.masques[iid] = lambda y=y, iid=iid, lieux=lieux: self._devoiler_nom(y, iid, lieux)
            if lieux or (y.amitie is not None and not cache):
                a.insert(iid, "end", iid=iid + "|~", text="")
                self.enfants[iid] = lambda y=y, iid=iid, lieux=lieux: self._lieux_yokai(y, iid, lieux)
        return len(ys)

    def _ligne_amitie(self, y: TK.Yokai, iid: str) -> None:
        """Première ligne dépliée d'un Yo-kai : sa facilité d'amitié (base au format 10 ; rien sinon). Jamais tant que
        le nom est masqué (anti-divulgâchage : le taux aiderait à l'identifier). Un appel Tcl (deux pour les rares
        Yo-kai dont une variante ne devient jamais amie)."""
        ai, lg = iid + "|a", self.langue
        if y.amitie is None or self.arbre.exists(ai) or self.masque_nom(y, self.filtre()):
            return
        self.arbre.insert(iid, 0, iid=ai, text=P.titre_amitie(lg, y.amitie, y.ami),
                          values=("", "", P.texte_amitie(lg, y.amitie), "", ""), tags=("amitie",))
        note = P.note_amitie(lg, y.amitie)
        if note:
            self.arbre.insert(iid, 1, iid=iid + "|b", text="", values=("", "", note, "", ""), tags=("amitie",))

    def _lieux_yokai(self, y: TK.Yokai, iid: str, lieux: list[TK.Lieu]) -> None:
        m, lg = self.modele, self.langue
        self._ligne_amitie(y, iid)
        for k, l in enumerate(lieux):
            cle = cle_lieu(y, l)
            cache = l.a_la_place_de is not None and self.masque_corr(cle)
            li = iid + "|" + str(k)
            self._ligne(iid, li, P.texte_carte(lg, m, l.carte), ("", "", P.texte_lieu(lg, m, l, cache), "", ""),
                        ("lieu",) + (("masque",) if cache else ()), k)
            if cache:
                self.masques[li] = lambda li=li, l=l, cle=cle: self._devoiler_corr(li, l, cle)

    def _remplir_lieux(self, f: TK.Filtre) -> int:
        a, m, lg = self.arbre, self.modele, self.langue
        arbre = TK.par_lieu(m, f, lg)
        total = set()
        for k, (region, cartes) in enumerate(arbre):
            ys = {y.cle for _c, el in cartes for y, _l in el}
            total |= ys
            iid = "r|" + region
            self._ligne("", iid, "  " + TK.nom_region(region, lg), ("", "", self.tr("yk_compte", n=len(ys)), "", ""),
                        ("region",), 0)
            a.insert(iid, "end", iid=iid + "|~", text="")
            self.enfants[iid] = lambda iid=iid, cartes=cartes: self._cartes(iid, cartes)
        return len(total)

    def _cartes(self, iid: str, cartes) -> None:
        a, m, lg = self.arbre, self.modele, self.langue
        for k, (carte, elements) in enumerate(cartes):
            ci = iid + "|" + carte
            nom = m.nom_carte(carte, lg)
            texte = f"{nom} ({carte})" if nom else carte
            self._ligne(iid, ci, texte, ("", "", self.tr("yk_compte", n=len({y.cle for y, _l in elements})), "", ""),
                        ("carte",), 0)
            a.insert(ci, "end", iid=ci + "|~", text="")
            self.enfants[ci] = lambda ci=ci, elements=elements: self._yokai_carte(ci, elements)

    def _yokai_carte(self, ci: str, elements) -> None:
        m, lg = self.modele, self.langue
        f = self.filtre()
        for k, (y, l) in enumerate(elements):
            li = ci + "|" + str(k)
            self.yokai_de[li] = y.cle
            cache_nom = self.masque_nom(y, f)
            cle = cle_lieu(y, l)
            cache_corr = l.a_la_place_de is not None and self.masque_corr(cle)
            nom = self.tr("yk_masque") if cache_nom else y.nom(lg)
            self._ligne(ci, li, nom, (y.lettre_rang, P.texte_tribu(lg, m, y.tribu),
                                      P.texte_lieu(lg, m, l, cache_corr), self.tr("yk_vu") if y.vu else "",
                                      self.tr("yk_ami") if y.ami else ""),
                        ("lieu",) + (("masque",) if (cache_nom or cache_corr) else ()), k)
            if cache_nom or cache_corr:
                def devoiler(li=li, y=y, l=l, cle=cle):
                    self.devoiles.update({"n:" + y.cle, "c:" + cle})
                    self.arbre.item(li, text=y.nom(lg), values=(
                        y.lettre_rang, P.texte_tribu(lg, m, y.tribu), P.texte_lieu(lg, m, l, False),
                        self.tr("yk_vu") if y.vu else "", self.tr("yk_ami") if y.ami else ""), tags=("lieu",))
                    self._maj_epingle()
                self.masques[li] = devoiler

    # ------------------------------------------------------------------ boss (rando_boss.json)
    def masque_boss(self, b: TK.BossLigne) -> bool:
        """Anti-divulgâchage : remplaçant caché tant que le Médaillium ne l'a pas vu (rencontre), sauf dévoilé."""
        return bool(self.v_anti.get() and b.remplace_par is not None and b.vu is not True
                    and "b:" + b.cle not in self.devoiles)

    def _texte_boss(self, b: TK.BossLigne, cache: bool) -> str:
        if b.remplace_par is None:
            return self.tr("yk_boss_inchange")
        if cache:
            return self.tr("yk_boss_remplace_masque")
        texte = self.tr("yk_boss_remplace", nom=b.remplacant_affiche(self.langue))
        if b.force:                                     # force adaptée à la place (multiplicateurs en %)
            texte += self.tr("yk_boss_force", pv=b.force[0], stats=b.force[1])
        elif b.force_exclue:                            # boss de l'objectif : jamais adapté
            texte += self.tr("yk_boss_force_objectif")
        return texte

    def _remplir_boss(self, f: TK.Filtre) -> int:
        """Vue « Boss » : « Boss : X — remplacé par Y » par classe (dévoilé à la rencontre ou au clic)."""
        m, lg = self.modele, self.langue
        if m.boss_etat != "actif" or not m.boss:
            cle = {"aucun": "yk_boss_aucun", "refuse": "yk_boss_refuse", "attente": "yk_boss_attente"}.get(
                m.boss_etat, "yk_boss_absent")
            self._ligne("", "b|etat", "", ("", "", self.tr(cle, message=m.boss_message), "", ""), ("vide",), 0)
            return 0
        cherche = TK.replier(f.texte) if f.texte else ""
        n = 0
        for classe in (1, 2, 3, 0):
            ls = [b for b in m.boss if b.classe == classe and (
                not cherche or cherche in TK.replier(b.nom_affiche(lg)) or cherche in TK.replier(b.nom))]
            if not ls:
                continue
            gi = f"b|c{classe}"
            self._ligne("", gi, "  " + self.tr(f"yk_boss_classe_{classe}"),
                        ("", "", self.tr("yk_boss_compte", n=len(ls)), "", ""), ("region",), 0)
            self.arbre.item(gi, open=True)
            for k, b in enumerate(ls):
                bi = f"b|{b.cle}"
                cache = self.masque_boss(b)
                self._ligne(gi, bi, "  " + self.tr("yk_boss_ligne", nom=b.nom_affiche(lg)),
                            ("", "", self._texte_boss(b, cache), self.tr("yk_vu") if b.vu else "", ""),
                            ("yokai",) + (("masque",) if cache else ()), k)
                if cache:
                    self.masques[bi] = lambda bi=bi, b=b: self._devoiler_boss(bi, b)
                n += 1
        return n

    def _devoiler_boss(self, bi: str, b: TK.BossLigne) -> None:
        self.devoiles.add("b:" + b.cle)
        vals = list(self.arbre.item(bi, "values"))
        vals[2] = self._texte_boss(b, False)
        self.arbre.item(bi, values=vals, tags=("yokai",))

    # ------------------------------------------------------------------ événements
    def _ouvrir(self, iid: str) -> None:
        remplir = self.enfants.pop(iid, None)
        if remplir is None:
            return
        faux = iid + "|~"
        if self.arbre.exists(faux):
            self.arbre.delete(faux)
        remplir()

    def _devoiler_nom(self, y: TK.Yokai, iid: str, lieux) -> None:
        self.devoiles.add("n:" + y.cle)
        texte, valeurs, _c = self._textes_yokai(y, self.filtre(), lieux)
        self.arbre.item(iid, text=texte, values=valeurs, tags=("yokai",))
        self._maj_epingle()                            # nom dévoilé : le Yo-kai peut maintenant être épinglé
        if iid not in self.enfants:                    # déjà déplié (ou sans lieu) : la ligne d'amitié arrive maintenant
            self._ligne_amitie(y, iid)

    def _devoiler_corr(self, li: str, l: TK.Lieu, cle: str) -> None:
        self.devoiles.add("c:" + cle)
        vals = list(self.arbre.item(li, "values"))
        vals[2] = P.texte_lieu(self.langue, self.modele, l, False)
        self.arbre.item(li, values=vals, tags=("lieu",))

    def devoiler(self, iid: str) -> bool:
        """Dévoile la ligne masquée `iid` (clic, Entrée) ; False si elle ne l'était pas."""
        f = self.masques.pop(iid, None)
        if f is None:
            return False
        f()
        return True

    def _clic(self, e) -> None:
        a = self.arbre
        if a.identify_region(e.x, e.y) not in ("tree", "cell"):
            return
        if a.identify_element(e.x, e.y).endswith("indicator"):
            return
        iid = a.identify_row(e.y)
        if iid:
            self.devoiler(iid)

    def _entree(self, _e=None) -> str:
        a = self.arbre
        iid = a.focus()
        if not iid:
            return "break"
        if not self.devoiler(iid) and a.get_children(iid):
            ouvrir = not a.item(iid, "open")
            if ouvrir:
                self._ouvrir(iid)
            a.item(iid, open=ouvrir)
        return "break"
