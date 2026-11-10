"""Onglet « Checks » du lanceur (tracker des locations de la partie) : vue tkinter seulement. Données, états et
filtres : `checks.py` (lui-même sur `client/checks_local.py` et la logique de l'APWorld) ; textes : `textes_checks.py`.

L'onglet relit `checks.json` (client) et `progression.json` quand leur taille ou leur date change (toutes les 1,5 s)
et garde les zones dépliées, la sélection et le défilement. **Aucun spoiler** : seul ce que le client a écrit est
affiché (contenu des checks faits ou indiqués) ; le spoiler log complet est un `.txt` séparé, écrit par le client sur
demande (bouton « Spoiler log (.txt) », après confirmation) puis ouvert avec l'application par défaut.

Clavier : Tab / Maj+Tab entre les champs, Ctrl+F (recherche, `vue.py`), Échap (vide la recherche), Flèche bas (vers
la liste), Entrée ou Espace sur une zone (déplier / replier), Ctrl+Tab (onglet suivant, `vue.py`).
"""
from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from . import carte_checks as CC
from . import checks as CK
from . import theme as th
from .textes import t
from .vue_cartes import VueCarte
from .vue_yokai import Placeholder

INTERVALLE = 1500                         # ms entre deux contrôles des fichiers
ATTENTE_SPOILER = 10.0                    # s : réponse du client à une demande de spoiler log
PAS_SPOILER = 200                         # ms entre deux lectures de la réponse
# explication d'un check « tardif » des portails mystères (`Check.portail`, archipelago_portails_tardifs.md)
TEXTE_PORTAIL = {"donjon": "ck_portail_donjon", "salle": "ck_portail_salle",
                 "crank": "ck_portail_crank",
                 "requetes": "ck_portail_requetes", "tunnel": "ck_portail_tunnel",
                 "apres_jeu": "ck_apres_jeu", "blasters": "ck_blasters_long", "transfert": "ck_transfert",
                 "blasters_edition": "ck_blasters_edition"}
# mention courte de la ligne (un check tardif sans texte propre porte « portail mystère — long »)
ETAT_PORTAIL = {"crank": "ck_e_portail_crank", "tunnel": "ck_e_portail_tunnel",
                "apres_jeu": "ck_e_apres_jeu", "blasters": "ck_e_blasters_long", "transfert": "ck_e_transfert",
                "blasters_edition": "ck_e_blasters_edition"}


class OngletChecks:
    """Contenu de l'onglet (cadre blanc posé dans une carte pleine de la `Scene`)."""

    def __init__(self, scene: th.Scene, theme: th.Theme, langue: str, dossier: Path,
                 ouvrir: Callable[[Path], object] | None = None,
                 confirmer: Callable[[str, str], bool] | None = None,
                 informer: Callable[[str, str], object] | None = None,
                 rom: Callable[[], str | None] = lambda: None,
                 choisir_rom: Callable[[], object] | None = None,
                 generer_cartes: Callable[..., object] | None = None, paresseux: bool = False,
                 suivre: bool = True, memoriser_suivi: Callable[[bool], object] | None = None,
                 epingle=None):
        """`paresseux` (fenêtre du lanceur) : les fichiers de données ne sont pas lus à la construction (onglet
        caché au démarrage) mais à la première ouverture de l'onglet, ou au premier contrôle périodique.
        `suivre` / `memoriser_suivi` : case « Suivre le jeu » du sous-onglet « Carte » (état mémorisé par le
        lanceur, `config.json`)."""
        # onglet « Yo-kai » (`vue_yokai.OngletYokai`, None : aucun) : il porte le Yo-kai épinglé, dont le sous-onglet
        # « Carte » montre les points d'apparition
        self.tracker = epingle
        self.suivre_initial = bool(suivre)
        self.memoriser_suivi = memoriser_suivi or (lambda _actif: None)
        self.sc, self.th, self.langue, self.dossier = scene, theme, langue, Path(dossier)
        self.ouvrir = ouvrir or (lambda _p: None)
        self.confirmer = confirmer or (lambda titre, texte: messagebox.askyesno(titre, texte, parent=self.sc.r))
        self.informer = informer or (lambda titre, texte: messagebox.showinfo(titre, texte, parent=self.sc.r))
        self.rom = rom
        self._choisir_rom = choisir_rom
        self.generation = CC.Generation(generer_cartes)
        self._cartes_verifiees = False
        self.selection: int | None = None     # check choisi, partagé entre la liste et la carte
        self.modele = CK.ModeleChecks(langue=langue)
        self.signature = None
        self.visible = False
        self.a_refaire = True
        self.vue = "zones"                    # zones (liste) | carte | recus
        self.ouverts: set[str] = set()        # zones dépliées par le joueur
        self._filtre_actif = False
        self._demande: tuple[str, float] | None = None       # (nonce, échéance) de la demande de spoiler log
        self.message = ""
        self.v_pas_faits = tk.BooleanVar(scene.r, value=False)
        self.v_acces = tk.BooleanVar(scene.r, value=False)
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
        tete = tk.Frame(f, bg=th.BLANC)
        tete.grid(row=0, column=0, sticky="ew")
        th.Badge(tete, T, None).pack(side="left")
        tk.Label(tete, text=self.tr("ck_titre"), font=T["carte"], bg=th.BLANC, fg=th.NOIR).pack(
            side="left", padx=(px(8), 0))
        self.b_spoiler = th.Pilule(tete, T, self.tr("ck_spoiler"), self.demander_spoiler, police="bouton_petit",
                                   padx=12, pady=3, genre="or")
        self.b_spoiler.pack(side="right", padx=(px(10), 0))
        self.b_vues = {}
        for cle, texte in (("recus", self.tr("ck_recus")), ("carte", self.tr("ck_carte")),
                           ("zones", self.tr("ck_par_zone"))):
            b = th.Pilule(tete, T, texte, lambda k=cle: self.changer_vue(k), police="bouton_petit",
                          padx=12, pady=3, genre="onglet" if cle == self.vue else "normal")
            b.pack(side="right", padx=(px(2), 0))
            self.b_vues[cle] = b
        # filtres
        fl = self.cadre_filtres = tk.Frame(f, bg=th.BLANC)
        fl.grid(row=1, column=0, sticky="ew", pady=(px(8), 0))
        fl.columnconfigure(0, weight=1)
        self.v_texte = tk.StringVar(self.sc.r)
        self.e_texte = Placeholder(fl, T, self.tr("ck_recherche"), self.v_texte)
        self.e_texte.grid(row=0, column=0, sticky="ew", ipady=px(3), padx=(0, px(8)))
        self.e_texte.bind("<KeyRelease>", lambda _e: self.planifier())
        self.e_texte.bind("<Escape>", lambda _e: (self.e_texte.delete(0, "end"), self.planifier()))
        self.e_texte.bind("<Down>", lambda _e: self._vers_liste())
        self.listes: dict[str, ttk.Combobox] = {}
        for i, (cle, largeur) in enumerate((("type", 22), ("zone", 24))):
            cb = ttk.Combobox(fl, state="readonly", style="Yokai.TCombobox", font=T["texte"], width=largeur)
            cb.grid(row=0, column=1 + i, sticky="e", padx=(0 if i == 0 else px(6), 0))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.planifier())
            self.listes[cle] = cb
        op = self.cadre_options = tk.Frame(f, bg=th.BLANC)
        op.grid(row=2, column=0, sticky="ew", pady=(px(6), px(6)))
        self.b_pas_faits = th.Bascule(op, T, self.tr("ck_pas_faits"), self.v_pas_faits, self.planifier)
        self.b_pas_faits.pack(side="left")
        self.b_acces = th.Bascule(op, T, self.tr("ck_accessibles"), self.v_acces, self.planifier)
        self.b_acces.pack(side="left", padx=(px(14), 0))
        self.l_compte = tk.Label(op, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX, anchor="e")
        self.l_compte.pack(side="right")
        # listes : par zone, objets reçus
        cadre_liste = self.cadre_liste = tk.Frame(f, bg=th.NOIR, padx=px(2), pady=px(2))
        cadre_liste.grid(row=3, column=0, sticky="nsew")
        cadre_liste.columnconfigure(0, weight=1)
        cadre_liste.rowconfigure(0, weight=1)
        self.arbre = a = ttk.Treeview(cadre_liste, columns=("etat", "type", "contenu"), style="Yokai.Treeview",
                                      height=3, selectmode="browse")
        a.column("#0", width=px(260), minwidth=px(160), stretch=False)
        a.column("etat", width=px(335), minwidth=px(90), stretch=False)   # (+ mentions des checks « Ami »)
        a.column("type", width=px(80), minwidth=px(60), stretch=False)
        a.column("contenu", width=px(300), minwidth=px(140), stretch=True)
        a.heading("#0", text=self.tr("ck_col_location"), anchor="w")
        for cle, texte in (("etat", "ck_col_etat"), ("type", "ck_col_type"), ("contenu", "ck_col_contenu")):
            a.heading(cle, text=self.tr(texte), anchor="w")
        a.tag_configure("zone", font=T["bouton"], background=th.OR_CLAIR)
        a.tag_configure("pair", background="#FFFAF3")
        a.tag_configure("fait", foreground="#1D7A3C")
        a.tag_configure("accessible", background=th.CYAN_PALE, foreground=th.CYAN_TEXTE)
        a.tag_configure("plus_tard", foreground="#A35A00")
        a.tag_configure("bloque", foreground=th.TEXTE_DOUX)
        a.tag_configure("inconnu", foreground=th.INACTIF_TEXTE)
        a.tag_configure("vide", foreground=th.TEXTE_DOUX)
        self.recu = r = ttk.Treeview(cadre_liste, columns=("objet", "de", "lieu"), style="Yokai.Treeview", height=3,
                                     selectmode="browse")
        r.column("#0", width=px(60), minwidth=px(44), stretch=False, anchor="e")
        r.column("objet", width=px(260), minwidth=px(120), stretch=False)
        r.column("de", width=px(180), minwidth=px(90), stretch=False)
        r.column("lieu", width=px(330), minwidth=px(140), stretch=True)
        r.heading("#0", text=self.tr("ck_col_n"), anchor="e")
        for cle, texte in (("objet", "ck_col_objet"), ("de", "ck_col_de"), ("lieu", "ck_col_lieu")):
            r.heading(cle, text=self.tr(texte), anchor="w")
        r.tag_configure("pair", background="#FFFAF3")
        r.tag_configure("soi", foreground=th.TEXTE_DOUX)
        r.tag_configure("vide", foreground=th.TEXTE_DOUX)
        # pas encore de checks de la partie : message au centre de la liste (au lieu d'une liste vide)
        self.l_vide = tk.Label(cadre_liste, text=th.insecables(self.tr("ck_non_connecte_vide")), font=T["texte"],
                               bg=th.BLANC, fg=th.TEXTE, justify="center", wraplength=px(420))
        self.defil = ttk.Scrollbar(cadre_liste, orient="vertical", style="Yokai.Vertical.TScrollbar")
        self.defil.grid(row=0, column=1, sticky="ns")
        for w in (a, r):
            w.bind("<Configure>", self._colonnes, add="+")
        a.bind("<Return>", self._entree)
        a.bind("<KP_Enter>", self._entree)
        a.bind("<space>", self._entree)
        a.bind("<<TreeviewSelect>>", lambda _e: self._selection_liste())
        a.bind("<<TreeviewOpen>>", lambda _e: self._noter_ouverture(a.focus(), True))
        a.bind("<<TreeviewClose>>", lambda _e: self._noter_ouverture(a.focus(), False))
        # détail de la ligne choisie (texte complet, même si une colonne est trop étroite)
        self.l_detail = tk.Label(f, text="", font=T["texte"], bg=th.CYAN_PALE, fg=th.CYAN_TEXTE, anchor="w",
                                 justify="left", padx=px(8), pady=px(3))
        # sous-onglet « Carte » (vue_cartes.py) : même modèle, mêmes filtres, même sélection
        self.vcarte = VueCarte(f, self)
        self._montrer_liste()
        # état
        self.cadre_etat = tk.Frame(f, bg=th.BLANC)
        self.cadre_etat.grid(row=5, column=0, sticky="ew", pady=(px(8), 0))
        self.cadre_etat.columnconfigure(1, weight=1)
        self.l_aide = tk.Label(f, text=self.tr("ck_aide_clavier"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                               anchor="w", justify="left")
        self.l_aide.grid(row=6, column=0, sticky="ew", pady=(px(4), 0))
        self.lignes_etat: list[tuple[th.Pastille, tk.Label]] = []
        f.bind("<Configure>", self._largeur, add="+")

    def _montrer_liste(self) -> None:
        if self.vue == "carte":
            self.cadre_liste.grid_remove()
            self.vcarte.cadre.grid(row=3, column=0, sticky="nsew")
        else:
            self.vcarte.cadre.grid_remove()
            self.vcarte.info.cacher()
            self.cadre_liste.grid(row=3, column=0, sticky="nsew")
            actif, cache = (self.arbre, self.recu) if self.vue == "zones" else (self.recu, self.arbre)
            cache.grid_remove()
            actif.grid(row=0, column=0, sticky="nsew")
            actif.configure(yscrollcommand=self.defil.set)
            self.defil.configure(command=actif.yview)
        for w in (self.cadre_filtres, self.cadre_options):
            w.grid() if self.vue != "recus" else w.grid_remove()
        for w in (getattr(self, "cadre_etat", None), getattr(self, "l_aide", None)):    # place pour la carte
            if w is not None:
                w.grid() if self.vue != "carte" else w.grid_remove()
        self._maj_detail()

    def _colonnes(self, _e=None) -> None:
        """Dernière colonne : toute la largeur restante."""
        for arbre, derniere in ((self.arbre, "contenu"), (self.recu, "lieu")):
            try:
                w = arbre.winfo_width()
                if w <= 1:
                    continue
                fixes = sum(int(arbre.column(c, "width")) for c in ("#0",) + tuple(arbre["columns"]) if c != derniere)
                arbre.column(derniere, width=max(self.th.px(140), w - fixes - self.th.px(2)))
            except tk.TclError:
                pass

    def _largeur(self, _e=None) -> None:
        lg = max(self.th.px(200), self.cadre.winfo_width() - self.th.px(30))
        for _p, lab in self.lignes_etat:
            lab.configure(wraplength=lg)
        self.l_aide.configure(wraplength=lg)
        self.l_detail.configure(wraplength=lg)

    # ------------------------------------------------------------------ données
    def activer(self, visible: bool) -> None:
        self.visible = visible
        if not visible:
            self.vcarte.info.cacher()
            self.vcarte.abandonner_recherche()
        else:
            self.recharger()                  # pas encore lues (onglet paresseux), ou changées depuis le dernier contrôle
        if visible and self.vue == "carte":
            self._verifier_cartes()
        if visible and self.a_refaire:
            self.remplir()
        if visible and self.vue == "carte":
            self.vcarte.demarrer_suivi()      # suivi du jeu : seulement tant que le sous-onglet est affiché

    def _surveiller(self) -> None:
        try:
            if not self.cadre.winfo_exists():
                return
        except tk.TclError:
            return
        self.recharger()
        self._suivre_generation()
        self.vcarte.surveiller()
        self.cadre.after(INTERVALLE if not self.generation.en_cours else 400, self._surveiller)

    # ------------------------------------------------------------------ cartes (génération en tâche de fond)
    def rom_valide(self) -> bool:
        r = self.rom()
        return bool(r) and Path(r).is_file()

    def epingle_change(self) -> None:
        """Le Yo-kai épinglé a changé (onglet « Yo-kai ») : la carte est redessinée, tout de suite si elle est
        affichée, sinon à sa prochaine ouverture."""
        if self.visible and self.vue == "carte":
            self.remplir()
        elif self.vue == "carte":
            self.a_refaire = True

    def choisir_rom(self) -> None:
        if self._choisir_rom is not None:
            self._choisir_rom()

    def generer_cartes(self, force: bool = False) -> bool:
        """Lance la génération des cartes (tâche de fond) SEULEMENT si elles sont absentes ou périmées
        (`cartes.raison_generation` : fichiers manquants, format, références de l'APWorld), ou si `force` (« Réparer »
        le mod, bouton « Générer » du sous-onglet). False : à jour, déjà en cours, pas de ROM, ou pas de générateur."""
        raison = "demandee" if force else CC.CA.raison_generation(self.dossier, CK.ck.logique_apworld())
        if raison is None:
            return False
        self.derniere_raison = raison                   # tests, journal
        if not self.rom_valide() or not self.generation.lancer():
            return False
        self._gen_etat = None
        self._maj_etat()
        return True

    def _verifier_cartes(self) -> None:
        """Première ouverture de la carte : cartes absentes ou d'une autre version (APWorld, références) ->
        régénérées en tâche de fond si la ROM est connue."""
        if self._cartes_verifiees or self.generation.en_cours:
            return
        self._cartes_verifiees = True
        if self.rom_valide():
            self.generer_cartes(force=False)

    def _suivre_generation(self) -> None:
        g = self.generation
        etat = (g.en_cours, int(g.fraction * 20), g.erreur)
        if etat != getattr(self, "_gen_etat", None):
            self._gen_etat = etat
            self._maj_etat()

    def recharger(self, force: bool = False) -> None:
        sig = CK.signature(self.dossier)
        if not force and sig == self.signature:
            return
        self.signature = sig
        self.modele = CK.charger(self.dossier, self.langue)
        self._maj_listes()
        self._maj_etat()
        self.a_refaire = True
        if self.visible or force:
            self.remplir()

    def _maj_listes(self) -> None:
        m, tr = self.modele, self.tr
        actuels = {cle: (self._valeur(cle) if cb.get() else None) for cle, cb in self.listes.items()}
        self.choix = {
            "type": [(None, tr("ck_tous_types"))] + [(x, tr(f"ck_type_{x}")) for x in CK.types_presents(m)],
            "zone": [(None, tr("ck_toutes_zones"))] + [(cle, nom) for cle, nom in m.zones
                                                       if any(c.zone == cle for c in m.checks)],
        }
        for cle, cb in self.listes.items():            # choix gardé d'un rechargement à l'autre
            actuel = actuels[cle]
            cb.configure(values=[txt for _v, txt in self.choix[cle]])
            cles = [v for v, _txt in self.choix[cle]]
            cb.current(cles.index(actuel) if actuel in cles else 0)
        ok = m.plan_ok and m.present
        self.b_acces.state(["!disabled"] if ok else ["disabled"])
        if not ok and self.v_acces.get():
            self.v_acces.set(False)

    def _valeur(self, cle: str):
        cb = self.listes[cle]
        i = cb.current()
        choix = getattr(self, "choix", {}).get(cle, [])
        return choix[i][0] if 0 <= i < len(choix) else None

    def filtre(self) -> CK.Filtre:
        return CK.Filtre(texte=self.e_texte.valeur().strip(), type=self._valeur("type"), zone=self._valeur("zone"),
                         pas_faits=bool(self.v_pas_faits.get()), accessibles=bool(self.v_acces.get()))

    def changer_vue(self, vue: str) -> None:
        if vue == self.vue:
            return
        self.vcarte.abandonner_recherche()
        self.vue = vue
        for cle, b in self.b_vues.items():
            b.changer_genre("onglet" if cle == vue else "normal")
        self._montrer_liste()
        if vue == "carte":
            self._verifier_cartes()
            self.vcarte.recharger()
            self.remplir()
            # le suivi du jeu d'abord (carte du jeu), puis la sélection venue de la liste (choix à la main : elle
            # l'emporte et met le suivi en pause si elle est sur une autre carte)
            self.cadre.after_idle(self.vcarte.demarrer_suivi)
            self.cadre.after_idle(self.vcarte.montrer_selection)
        else:
            self.remplir()

    def planifier(self) -> None:
        if not getattr(self, "_prevu", False):
            self._prevu = True
            self.cadre.after(120, self._remplir_prevu)

    def _remplir_prevu(self) -> None:
        self._prevu = False
        self.remplir()

    def focus_recherche(self) -> None:
        if self.vue == "recus":
            self.changer_vue("zones")
        self.e_texte.focus_set()
        self.e_texte.select_range(0, "end")

    def _vers_liste(self) -> str:
        a = self.arbre if self.vue == "zones" else self.recu
        enfants = a.get_children()
        if enfants:
            a.focus_set()
            a.focus(enfants[0])
            a.selection_set(enfants[0])
        return "break"

    # ------------------------------------------------------------------ état
    def lignes(self) -> list[tuple[str, str]]:
        """(texte, niveau) des lignes d'état sous la liste."""
        m, out = self.modele, []
        if m.sans_donnees:
            out = [(self.tr("ck_non_connecte_vide"), "attention"), (self.tr("ck_sans_spoiler"), "neutre")]
            g = self.generation
            if g.en_cours:
                out.append((self.tr("ck_cartes_generation", pc=int(g.fraction * 100)), "attention"))
            elif g.erreur:
                out.append((self.tr("ck_cartes_erreur", detail=g.erreur), "erreur"))
            return out
        date = time.strftime("%d/%m %H:%M", time.localtime(m.horodatage)) if m.horodatage else "?"
        out.append((self.tr("ck_connecte" if m.connecte else "ck_deconnecte", joueur=m.joueur or "?",
                            graine=m.graine or "?", date=date), "ok" if m.connecte else "attention"))
        if not m.plan_ok:
            out.append((self.tr("ck_logique_absente"), "erreur"))
        elif m.chapitres_reels is not None:
            out.append((self.tr("ck_mode_reel", n=m.chapitres_reels), "ok"))
        else:
            out.append((self.tr("ck_mode_logique"), "attention"))
        out.append((self.tr("ck_sans_spoiler"), "neutre"))
        if self.message:
            out.append((self.message, "neutre"))
        g = self.generation
        if g.en_cours:
            out.append((self.tr("ck_cartes_generation", pc=int(g.fraction * 100)), "attention"))
        elif g.erreur:
            out.append((self.tr("ck_cartes_erreur", detail=g.erreur), "erreur"))
        return out

    def _maj_etat(self) -> None:
        for p, lab in self.lignes_etat:
            p.destroy()
            lab.destroy()
        self.lignes_etat = []
        px = self.th.px
        for i, (texte, niveau) in enumerate(self.lignes()):
            p = th.Pastille(self.cadre_etat, self.th)
            p.niveau(niveau)
            haut = px(3) + max(0, (self.th["texte"].metrics("linespace") - p.d) // 2)
            p.grid(row=i, column=0, sticky="nw", pady=(haut, 0), padx=(0, px(8)))
            lab = tk.Label(self.cadre_etat, text=th.insecables(texte), font=self.th["texte"], bg=th.BLANC,
                           fg=th.TEXTE, justify="left", anchor="w")
            lab.grid(row=i, column=1, sticky="w", pady=(px(2), px(1)))
            self.lignes_etat.append((p, lab))
        self._largeur()

    # ------------------------------------------------------------------ textes d'une ligne
    def texte_etat(self, c: CK.Check) -> str:
        """État d'une ligne (liste et carte) ; un check « tardif » des portails mystères pas encore fait porte la
        mention « portail mystère — long » (archipelago_portails_tardifs.md)."""
        s = self._texte_etat(c)
        if c.portail and c.etat != "fait":
            s += self.tr(ETAT_PORTAIL.get(c.portail, "ck_e_portail"))
        if c.apparition and c.etat != "fait":                    # Yo-kai d'évènement qui attend que sa place soit libre
            s += self.tr(f"ck_e_app_{c.apparition}")
        if c.etat != "fait":                                     # pièce spéciale / sceau qui donne ce Yo-kai
            s += self.mention_ami(c)
        return s

    def mention_ami(self, c: CK.Check) -> str:
        """Mention courte d'un check « Ami » d'un Yo-kai de pièce spéciale (pièce, rang dans l'ordre, « → prochain »)
        ou d'un légendaire mélangé (sceau qui le donne) ; "" sinon. Ce que la colonne d'objets listait à part."""
        out = ""
        if c.piece is not None:
            f, y = c.piece
            if not y.ami:
                if f.genre == "regions":
                    out += self.tr("ck_e_pc_region", piece=y.piece)       # (reçue : dit par l'état)
                elif f.genre == "ordre" and y.rang:
                    out += self.tr("ck_e_pc_suivant" if y.suivant else "ck_e_pc_rang", piece=f.nom, k=y.rang)
                elif f.genre == "choix":
                    out += self.tr("ck_e_pc_choix", piece=f.nom)
                else:
                    out += self.tr("ck_e_pc_unique", piece=f.nom)
        if c.legendaire is not None:
            out += self.tr("ck_e_sceau", sceau=c.legendaire.sceau)
        return out

    def aide_ami(self, c: CK.Check) -> list[str]:
        """Phrases du détail d'un check « Ami » de pièce spéciale ou de légendaire mélangé (mêmes textes que les
        infobulles des anciennes listes de la colonne d'objets)."""
        aide = []
        if c.piece is not None:
            f, y = c.piece
            tr = self.tr
            if y.ami:
                aide.append(tr("cc_pc_yk_ami", yokai=y.nom))
            elif f.genre == "regions":
                aide.append(tr("cc_pc_yk_region", yokai=y.nom, piece=y.piece,
                               etat=tr("cc_pc_region_recue" if y.piece_recue else "cc_pc_region_pas_recue")))
            elif f.genre == "choix":
                aide += [tr("cc_pc_yk_choix", yokai=y.nom, piece=f.nom), tr("cc_pc_choix").replace("\n", " ")]
            elif f.genre == "unique":
                aide.append(tr("cc_pc_yk_unique", yokai=y.nom, piece=f.nom).replace("\n", " "))
            else:
                aide.append(tr("cc_pc_yk_suivant", yokai=y.nom, piece=f.nom) if y.suivant
                            else tr("cc_pc_yk_rang", yokai=y.nom, piece=f.nom, k=y.rang))
                aide.append(tr("cc_pc_recues", piece=f.nom, n=f.recues, total=f.total))
                aide.append(tr("cc_pc_ordre_graine" if f.cle == "piece_5_etoiles" else "cc_pc_ordre_jeu"))
        if c.legendaire is not None and not c.sceau:             # sceau d'origine (un sceau déplacé : `ck_sceau`)
            aide.append(self.tr("ck_sceau_origine"))
        return aide

    def _texte_etat(self, c: CK.Check) -> str:
        if c.etat == "plus_tard":
            return self.tr("ck_e_plus_tard", n=c.chapitres)
        if c.etat == "bloque":
            parts = list(c.manque) + ([self.tr("ck_e_rangs", n=c.rangs)] if c.rangs else [])
            if not parts:
                return self.tr("ck_e_plus_tard", n=c.chapitres)
            objets = ", ".join(parts)
            if c.chapitres and (self.modele.chapitres_reels or 0) < c.chapitres:
                return self.tr("ck_e_bloque_chap", objets=objets, n=c.chapitres)
            return self.tr("ck_e_bloque", objets=objets)
        return self.tr(f"ck_e_{c.etat}")

    def texte_contenu(self, c: CK.Check) -> str:
        """Contenu affiché : seulement s'il est fait ou indiqué (le modèle n'a rien d'autre)."""
        if c.contenu is None:
            return ""
        if c.indice and c.etat != "fait":
            return self.tr("ck_indice", contenu=c.contenu)
        return c.contenu + (f"  ({self.tr('ck_indice_court')})" if c.indice else "")

    # ------------------------------------------------------------------ liste
    def remplir(self) -> None:
        self.a_refaire = False
        if self.vue == "zones" and self.modele.sans_donnees:
            self.l_vide.place(relx=0.5, rely=0.4, anchor="center")
        else:
            self.l_vide.place_forget()
        if self.vue == "recus":
            self._remplir_recus()
        elif self.vue == "carte":
            self._remplir_carte()
        else:
            self._remplir_zones()

    def _remplir_carte(self) -> None:
        m = self.modele
        f = self.filtre()
        self.vcarte.remplir()
        cpt = m.compter()
        texte = self.tr("ck_compte", faits=cpt.get("fait", 0), total=cpt["total"], acces=cpt.get("accessible", 0),
                        tard=cpt.get("plus_tard", 0), bloque=cpt.get("bloque", 0))
        if f.texte or f.type or f.zone or f.pas_faits or f.accessibles:
            n = sum(1 for c in m.checks if f.garde(c, m))
            texte = self.tr("ck_compte_filtre", n=n) + "   |   " + texte
        self._afficher_compte(texte)
        self._maj_detail()

    def _afficher_compte(self, texte: str) -> None:
        """Compteurs de la liste et de la carte : grisés (tous à 0) tant qu'il n'y a pas de checks de la partie."""
        vide = self.modele.sans_donnees
        self.l_compte.configure(text=self.tr("ck_compte", faits=0, total=0, acces=0, tard=0, bloque=0) if vide
                                else texte, fg=th.INACTIF_TEXTE if vide else th.TEXTE_DOUX)

    def _remplir_zones(self) -> None:
        a, m = self.arbre, self.modele
        f = self.filtre()
        actif = bool(f.texte or f.type or f.zone or f.pas_faits or f.accessibles)
        sel = a.selection()
        haut = a.yview()[0]
        a.delete(*a.get_children())
        zones = CK.par_zone(m, f)
        n = 0
        for cle, nom, checks, cpt in zones:
            iid = "z|" + cle
            acces = cpt.get("accessible", 0)
            a.insert("", "end", iid=iid, text="  " + nom, open=actif or cle in self.ouverts,
                     values=(self.tr("ck_zone_compte", faits=cpt.get("fait", 0), total=cpt["total"]), "",
                             self.tr("ck_zone_acces", n=acces) if acces else self.tr("ck_zone_acces_0")),
                     tags=("zone",))
            for k, c in enumerate(checks):
                tags = (c.etat,) + (("pair",) if k % 2 and c.etat not in ("accessible",) else ())
                a.insert(iid, "end", iid=f"c|{c.id}", text=c.nom,
                         values=(self.texte_etat(c), self.tr(f"ck_t_{c.type}"), self.texte_contenu(c)), tags=tags)
                n += 1
        if not zones and not m.sans_donnees:                  # sans données : message centré (`l_vide`)
            a.insert("", "end", iid="vide", text="  " + self.tr("ck_aucun_resultat"), values=("", "", ""),
                     tags=("vide",))
        self._filtre_actif = actif
        cpt = m.compter()
        texte = self.tr("ck_compte", faits=cpt.get("fait", 0), total=cpt["total"], acces=cpt.get("accessible", 0),
                        tard=cpt.get("plus_tard", 0), bloque=cpt.get("bloque", 0))
        if actif:
            texte = self.tr("ck_compte_filtre", n=n) + "   |   " + texte
        self._afficher_compte(texte)
        if self.selection is not None and a.exists(f"c|{self.selection}"):
            sel = (f"c|{self.selection}",)
        for i in sel:
            if a.exists(i):
                a.selection_set(i)
                a.focus(i)
        if self.visible:                                  # défilement gardé (onglet affiché seulement)
            a.update_idletasks()
            a.yview_moveto(haut)
        self._maj_detail()

    def _remplir_recus(self) -> None:
        r, m = self.recu, self.modele
        haut = r.yview()[0]
        r.delete(*r.get_children())
        for k, x in enumerate(reversed(m.recus)):          # le plus récent en haut
            de = self.tr("ck_moi") if x.soi else x.expediteur
            r.insert("", "end", iid=f"r|{x.n}", text=str(x.n),
                     values=(x.objet, de, x.lieu or self.tr("ck_depart")),
                     tags=(("pair",) if k % 2 else ()) + (("soi",) if x.soi else ()))
        if not m.recus:
            r.insert("", "end", iid="vide", text="", values=(self.tr("ck_aucun_recu"), "", ""), tags=("vide",))
        self.l_compte.configure(text=self.tr("ck_recus_compte", n=len(m.recus)), fg=th.TEXTE_DOUX)
        if self.visible:
            r.update_idletasks()
            r.yview_moveto(haut)

    def detail(self) -> str:
        """Texte complet du check choisi (liste ou carte) : location, zone, état, type, contenu fait ou indiqué."""
        if self.vue == "recus" or self.selection is None:
            return ""
        c = next((x for x in self.modele.checks if x.id == self.selection), None)
        if c is None:
            return ""
        parts = [c.nom, self.modele.nom_zone(c.zone), self.texte_etat(c), self.tr(f"ck_t_{c.type}")]
        contenu = self.texte_contenu(c)
        ou = CK.ou_chercher(self.modele, c)                      # Yo-criminel : pas de lieu fixe, dire où chercher
        aide = [self.tr("ck_ou_criminel", cartes=", ".join(ou))] if ou else []
        if c.portail and c.etat != "fait":                       # check tardif des portails mystères : dire pourquoi
            aide.append(self.tr(TEXTE_PORTAIL.get(c.portail, "ck_portail_salle")))
        if c.revanche and c.etat != "fait":                      # lot 17 : revanche sans limite de jour (option)
            aide.append(self.tr("ck_revanche_libre"))
        if getattr(c, "sceau", None):                            # lot L1 : légendaire donné par un autre sceau
            aide.append(self.tr("ck_sceau", sceau=c.sceau))
        aide += self.aide_ami(c)
        return "  ·  ".join(parts + ([contenu] if contenu else []) + aide)

    def _maj_detail(self) -> None:
        texte = self.detail()
        self.l_detail.configure(text=texte)
        if texte:
            self.l_detail.grid(row=4, column=0, sticky="ew", pady=(self.th.px(4), 0))
        else:
            self.l_detail.grid_remove()

    # ------------------------------------------------------------------ sélection partagée
    def _selection_liste(self) -> None:
        sel = self.arbre.selection()
        if sel and sel[0].startswith("c|"):
            self.selection = int(sel[0][2:])
        elif sel:
            self.selection = None
        self._maj_detail()

    def choisir(self, ident: int | None) -> None:
        """Choisit un check (clic sur la carte, liste « sans position ») : même sélection pour la liste (sa zone y
        sera dépliée) et la carte."""
        self.selection = ident
        c = next((x for x in self.modele.checks if x.id == ident), None)
        if c is not None:
            self.ouverts.add(c.zone)
        if self.vue == "carte":
            self.vcarte.redessiner_selection()
        self._maj_detail()

    def choisir_zone(self, cle) -> None:
        """Filtre « Zone » (= région de la carte) : le même réglage pour la liste et la carte."""
        cles = [v for v, _t in getattr(self, "choix", {}).get("zone", [])]
        if cle in cles:
            self.listes["zone"].current(cles.index(cle))
        self.remplir()

    # ------------------------------------------------------------------ événements
    def _noter_ouverture(self, iid: str, ouvert: bool) -> None:
        if iid and iid.startswith("z|") and not self._filtre_actif:
            (self.ouverts.add if ouvert else self.ouverts.discard)(iid[2:])

    def _entree(self, _e=None) -> str:
        a = self.arbre
        iid = a.focus()
        if iid and a.get_children(iid):
            ouvrir = not a.item(iid, "open")
            a.item(iid, open=ouvrir)
            self._noter_ouverture(iid, ouvrir)
        return "break"

    # ------------------------------------------------------------------ spoiler log
    def demander_spoiler(self) -> bool:
        """Bouton « Spoiler log (.txt) » : explique s'il n'est pas disponible, sinon demande confirmation, puis
        demande au client d'écrire le fichier et l'ouvre quand il est prêt. True si une demande a été déposée."""
        self.recharger()
        m = self.modele
        titre = self.tr("ck_spoiler_titre")
        if not m.present or not m.spoiler:
            self.informer(titre, self.tr("ck_spoiler_pas_de_donnees"))
            return False
        if not self.confirmer(titre, self.tr("ck_spoiler_confirmer")):
            return False
        nonce = CK.ck.demander_spoiler(self.dossier, self.langue)
        self._demande = (nonce, time.monotonic() + ATTENTE_SPOILER)
        self._message(self.tr("ck_spoiler_en_cours"))
        self.b_spoiler.state(["disabled"])
        self.cadre.after(PAS_SPOILER, self._attendre_spoiler)
        return True

    def _attendre_spoiler(self) -> None:
        if self._demande is None:
            return
        nonce, echeance = self._demande
        r = CK.ck.lire_reponse(self.dossier, nonce)
        if r is None and time.monotonic() < echeance:
            self.cadre.after(PAS_SPOILER, self._attendre_spoiler)
            return
        self._demande = None
        self.b_spoiler.state(["!disabled"])
        titre = self.tr("ck_spoiler_titre")
        if r is None:
            try:                                          # demande jamais lue : retirée (pas de fichier plus tard)
                (self.dossier / CK.ck.NOM_DEMANDE).unlink()
            except OSError:
                pass
            self._message("")
            self.informer(titre, self.tr("ck_spoiler_attente"))
        elif not r.get("ok") or not r.get("fichier"):
            self._message("")
            self.informer(titre, self.tr("ck_spoiler_refus"))
        else:
            f = Path(r["fichier"])
            self._message(self.tr("ck_spoiler_ecrit", fichier=str(f)))
            self.ouvrir(f)

    def _message(self, texte: str) -> None:
        self.message = texte
        self._maj_etat()
