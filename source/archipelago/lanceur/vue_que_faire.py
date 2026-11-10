"""Panneau « Que faire maintenant ? » du sous-onglet « Carte » (onglet « Checks ») : vue tkinter seulement. Calcul :
`que_faire.py` ; textes : `textes_que_faire.py`.

Un bouton or « Que faire maintenant ? » sous « Copier ma position » (colonne de gauche) ouvre le panneau À LA PLACE de
la colonne de droite (compteurs, légende, checks sans position), qui revient à la fermeture. Le panneau liste, par
carte, les checks accessibles à faire maintenant, en commençant par la carte où se trouve le joueur (sinon la carte
affichée), puis les cartes proches. Les articles d'une même boutique sont rangés sous une ligne de la boutique (repliée).
Clic (ou Entrée) sur un check : sa carte est ouverte, le check choisi (sélection partagée avec la liste) et la vue
centrée sur son marqueur ; sur une boutique : sa carte et le panneau de ses articles ; sur un titre de carte : la carte.
Comme tout choix à la main, cela met le suivi du jeu en pause s'il s'agit d'une autre carte que celle du jeu. Survol
d'une ligne : nom complet, zone et mention (une seule liaison pour toute la liste).

Recalcul (rien à chaque image) : à l'ouverture, puis seulement quand une entrée change (`que_faire.signature`),
contrôlée toutes les `PERIODE` ms tant que le panneau est ouvert (rien n'est lu ni calculé quand le sous-onglet est
caché : le tour ne fait que se replanifier). Sans jeu suivi, le départ est la carte affichée À L'OUVERTURE du panneau
(figée : un clic dans la liste change la carte affichée, la liste ne doit pas se réordonner sous le curseur).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from . import que_faire as QF
from . import theme as th
from .textes_que_faire import t

if TYPE_CHECKING:                                   # pragma: no cover
    from .vue_cartes import VueCarte

PERIODE = 1000                                      # ms entre deux contrôles de la signature (panneau ouvert)
GROUPES_OUVERTS = 3                                 # groupes dépliés à l'ouverture (les plus proches)
COULEUR_INDICE = "#8A6100"
COULEUR_INCERTAIN = "#A35A00"
# clés de texte complètes (pas de concaténation : `test_lanceur.TestTextes` relève les clés passées à `self.tr`)
TEXTES_PROXIMITE = {"ici": "qf_p_ici", "a_cote": "qf_p_a_cote", "region": "qf_p_region", "voisine": "qf_p_voisine",
                    "loin": "qf_p_loin", "inconnue": "qf_p_inconnue", "sans_position": "qf_p_sans_position"}
TEXTES_REPORT = {"absent": "qf_s_absent", "nuit": "qf_s_nuit"}
TEXTES_MASQUES = {"exclus": "qf_masque_exclus", "absent": "qf_masque_absent", "nuit": "qf_masque_nuit"}


class QueFaire:
    """Bouton et panneau (posés par `VueCarte.construire`)."""

    def __init__(self, vue: "VueCarte", gauche: tk.Misc, droite: tk.Misc, cadre: tk.Misc):
        self.v, self.o, self.th = vue, vue.o, vue.th
        self.droite = droite
        self.ouvert = False
        self.resultat: QF.Resultat | None = None
        self._sig = None
        self._tache = None
        self._elements: dict[str, object] = {}       # iid -> Ligne ou Groupe
        self._ouverts: set[str] | None = None        # groupes dépliés (clé de groupe) gardés d'un recalcul à l'autre
        self._ouverts_b: set[str] = set()            # boutiques dépliées
        self.depart_affiche: str | None = None       # carte affichée à l'ouverture (départ quand le jeu n'est pas suivi)
        self.calculs = 0                             # nombre de recalculs (tests : rien sans changement)
        T, px = self.th, self.th.px
        self.v_tout = tk.BooleanVar(cadre, value=False)
        self.bouton = th.Pilule(gauche, T, self.tr("qf_bouton"), self.basculer, genre="or", police="bouton_petit",
                                padx=10, pady=2)
        self.bouton.grid(row=4, column=0, sticky="w", pady=(px(6), 0))
        self.bouton.bind("<Enter>", lambda e: vue.info.montrer(self.tr("qf_bouton_aide"), e.x_root, e.y_root),
                         add="+")
        self.bouton.bind("<Leave>", lambda _e: vue.info.cacher(), add="+")
        p = self.panneau = tk.Frame(cadre, bg=th.BLANC)
        p.columnconfigure(0, weight=1)
        p.rowconfigure(5, weight=1)
        tete = tk.Frame(p, bg=th.BLANC)
        tete.grid(row=0, column=0, sticky="ew")
        tete.columnconfigure(0, weight=1)
        tk.Label(tete, text=self.tr("qf_titre"), font=T["bouton"], bg=th.BLANC, fg=th.NOIR, anchor="w").grid(
            row=0, column=0, sticky="w")
        self.b_fermer = th.Pilule(tete, T, self.tr("qf_fermer"), self.fermer, police="bouton_petit", padx=8, pady=1)
        self.b_fermer.grid(row=0, column=1, sticky="e")
        lg = px(320)
        self.l_depuis = tk.Label(p, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE, anchor="w", justify="left",
                                 wraplength=lg)
        self.l_depuis.grid(row=1, column=0, sticky="ew", pady=(px(2), 0))
        self.l_compte = tk.Label(p, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX, anchor="w",
                                 justify="left", wraplength=lg)
        self.l_compte.grid(row=2, column=0, sticky="ew")
        self.b_tout = th.Bascule(p, T, self.tr("qf_montrer_tout"), self.v_tout, self.maj)
        self.b_tout.grid(row=3, column=0, sticky="w", pady=(px(2), 0))
        self.l_masques = tk.Label(p, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX, anchor="w",
                                  justify="left", wraplength=lg)
        self.l_masques.grid(row=4, column=0, sticky="ew")
        cadre_arbre = tk.Frame(p, bg=th.NOIR, padx=px(1), pady=px(1))
        cadre_arbre.grid(row=5, column=0, sticky="nsew", pady=(px(3), 0))
        cadre_arbre.rowconfigure(0, weight=1)
        cadre_arbre.columnconfigure(0, weight=1)
        a = self.arbre = ttk.Treeview(cadre_arbre, columns=("zone",), show="tree", style="Yokai.Treeview", height=6,
                                      selectmode="browse")
        a.column("#0", width=px(228), minwidth=px(150), stretch=True)
        a.column("zone", width=px(84), minwidth=px(60), stretch=False)
        a.grid(row=0, column=0, sticky="nsew")
        defil = ttk.Scrollbar(cadre_arbre, orient="vertical", command=a.yview, style="Yokai.Vertical.TScrollbar")
        defil.grid(row=0, column=1, sticky="ns")
        a.configure(yscrollcommand=defil.set)
        a.tag_configure("groupe", font=T["bouton_petit"], background=th.OR_CLAIR)
        a.tag_configure("ici", font=T["bouton_petit"], background=th.CYAN_PALE)
        a.tag_configure("normal", foreground=th.CYAN_TEXTE)
        a.tag_configure("indice", foreground=COULEUR_INDICE)
        a.tag_configure("incertain", foreground=COULEUR_INCERTAIN)
        a.tag_configure("masque", foreground=th.TEXTE_DOUX)
        a.tag_configure("vide", foreground=th.TEXTE_DOUX)
        a.bind("<ButtonRelease-1>", self._clic, add="+")
        a.bind("<Motion>", self._survol, add="+")
        a.bind("<Leave>", lambda _e: self._cacher_bulle(), add="+")
        self._survole: str | None = None
        a.bind("<Return>", lambda _e: self.activer(a.focus()), add="+")
        a.bind("<KP_Enter>", lambda _e: self.activer(a.focus()), add="+")
        a.bind("<<TreeviewOpen>>", lambda _e: self._noter_ouverts(), add="+")
        a.bind("<<TreeviewClose>>", lambda _e: self.arbre.after_idle(self._noter_ouverts), add="+")
        self.l_aide = tk.Label(p, text=self.tr("qf_aide"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                               anchor="w", justify="left", wraplength=lg)
        self.l_aide.grid(row=6, column=0, sticky="ew", pady=(px(3), 0))

    def tr(self, cle: str, **p) -> str:
        return t(self.o.langue, cle, **p)

    # ------------------------------------------------------------------ ouverture
    def basculer(self) -> None:
        self.fermer() if self.ouvert else self.ouvrir()

    def ouvrir(self) -> None:
        if not self.ouvert:
            self.ouvert = True
            self.depart_affiche = self.v.carte
            self._ouverts, self._ouverts_b = None, set()
            self.v.info.cacher()
            self.droite.grid_remove()
            self.panneau.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=(self.th.px(8), 0))
            self.bouton.changer_genre("onglet")
        self.maj(force=True)
        self._lancer()

    def fermer(self) -> None:
        if not self.ouvert:
            return
        self.ouvert = False
        self.panneau.grid_remove()
        self.droite.grid()
        self.bouton.changer_genre("or")
        if self._tache is not None:
            try:
                self.panneau.after_cancel(self._tache)
            except tk.TclError:
                pass
            self._tache = None

    def _lancer(self) -> None:
        if self._tache is None:
            self._tache = self.panneau.after(PERIODE, self._tour)

    def _tour(self) -> None:
        """Contrôle périodique tant que le panneau est ouvert ; sous-onglet caché : rien n'est lu ni calculé."""
        self._tache = None
        try:
            if not self.ouvert or not self.panneau.winfo_exists():
                return
            if self.o.visible and self.o.vue == "carte":
                self.maj()
            self._tache = self.panneau.after(PERIODE, self._tour)
        except tk.TclError:
            self._tache = None

    # ------------------------------------------------------------------ calcul
    def entrees(self) -> dict:
        v = self.v
        f = self.o.filtre()
        return {"m": self.o.modele, "don": v.don, "f": f, "prog": v.progression(), "lieu": v.lieu,
                "carte_affichee": self.depart_affiche, "montrer_tout": bool(self.v_tout.get())}

    def maj(self, force: bool = False) -> bool:
        """Recalcule et remplit si une entrée a changé (ou `force`) ; True si la liste a été refaite."""
        if not self.ouvert:
            return False
        e = self.entrees()
        sig = QF.signature(**e)
        if not force and sig == self._sig:
            return False
        self._sig = sig
        if not hasattr(self, "_connexions"):
            self._connexions = QF.connexions_apworld()
        self.resultat = QF.construire(connexions=self._connexions, **e)
        self.calculs += 1
        self.remplir()
        self._lancer()
        return True

    # ------------------------------------------------------------------ affichage
    def _noms_cartes(self) -> dict[str, str]:
        from . import noms_locaux
        d = noms_locaux.charger(self.o.dossier) or {}
        lg = "engb" if self.o.langue == "en" else "fr"
        return ((d.get("langues") or {}).get(lg) or {}).get("cartes") or {}

    @staticmethod
    def cle_groupe(gr: QF.Groupe) -> str:
        return ("c|" + gr.carte) if gr.carte else ("z|" + str(gr.zone))

    def texte_ligne(self, l: QF.Ligne, court: bool = False) -> str:
        """Nom du check (« article i » seul sous la ligne de sa boutique : `court`), ★ s'il est indiqué, mention."""
        s = ("★ " if l.check.indice else "") + (QF.CC.nom_article(l.check) if court else l.check.nom)
        if l.report:
            s += self.tr(TEXTES_REPORT[l.report])
        elif l.check.exclue:
            s += self.tr("qf_s_exclu")
        elif l.incertain:
            s += self.tr("qf_s_incertain")
        if l.carte is not None and l.position is None:
            s += self.tr("qf_s_inconnue")
        return s

    def texte_proximite(self, gr: QF.Groupe) -> str:
        if gr.proximite == "ici" and self.resultat is not None and self.resultat.mode == "affichee":
            return self.tr("qf_p_ici_affichee")
        return self.tr(TEXTES_PROXIMITE[gr.proximite])

    def _filtres(self) -> str:
        f = self.o.filtre()
        parts = []
        if f.type:
            parts.append(self.o.tr(f"ck_type_{f.type}"))
        if f.texte:
            parts.append("« %s »" % f.texte if self.o.langue != "en" else '"%s"' % f.texte)
        return ", ".join(parts)

    def remplir(self) -> None:
        a, r, m = self.arbre, self.resultat, self.o.modele
        noms = self._noms_cartes()
        nom = (lambda k: noms.get(k, k))
        if r is None:
            return
        if r.mode == "joueur":
            depuis = self.tr("qf_depuis_joueur", carte=nom(r.depuis))
        elif r.mode == "affichee":
            depuis = self.tr("qf_depuis_affichee", carte=nom(r.depuis))
        else:
            depuis = self.tr("qf_depuis_aucune")
        self.l_depuis.configure(text=depuis)
        compte = self.tr("qf_compte", n=r.total)
        filtres = self._filtres()
        if filtres:
            compte += "\n" + self.tr("qf_filtres", filtres=filtres)
        self.l_compte.configure(text=compte)
        detail = [self.tr(cle, n=r.masques[k]) for k, cle in TEXTES_MASQUES.items() if r.masques.get(k)]
        self.l_masques.configure(text=self.tr("qf_masques", detail=", ".join(detail)) if detail else "")
        haut = a.yview()[0]
        choix = a.selection()
        a.delete(*a.get_children())
        self._elements = {}
        if m.sans_donnees:
            a.insert("", "end", iid="vide", text=self.tr("qf_sans_donnees"), values=("",), tags=("vide",))
            return
        if not r.groupes:
            a.insert("", "end", iid="vide", text=self.tr("qf_rien"), values=("",), tags=("vide",))
            return
        premiers = {self.cle_groupe(gr) for gr in r.groupes[:GROUPES_OUVERTS]}
        ouverts = premiers if self._ouverts is None else self._ouverts
        for gr in r.groupes:
            gi = self.cle_groupe(gr)
            if gr.carte:
                texte = self.tr("qf_groupe", carte=nom(gr.carte), n=len(gr.lignes))
            else:
                texte = self.tr("qf_groupe_zone", zone=m.nom_zone(gr.zone), n=len(gr.lignes))
            a.insert("", "end", iid=gi, text=texte, values=(self.texte_proximite(gr),), open=gi in ouverts,
                     tags=("ici" if gr.proximite == "ici" else "groupe",))
            self._elements[gi] = gr
            boutiques: dict[str, list[QF.Ligne]] = {}
            for l in gr.lignes:
                if l.boutique:
                    boutiques.setdefault(l.boutique, []).append(l)
            vues: set[str] = set()
            for l in gr.lignes:
                parent = gi
                if l.boutique and len(boutiques[l.boutique]) > 1:   # articles d'une boutique : sous sa ligne
                    parent = f"{gi}|b|{l.boutique}"
                    if l.boutique not in vues:
                        vues.add(l.boutique)
                        arts = boutiques[l.boutique]
                        a.insert(gi, "end", iid=parent, open=parent in self._ouverts_b,
                                 text=self.tr("qf_boutique", code=l.boutique, n=len(arts)),
                                 values=(m.nom_zone(l.check.zone),), tags=(self.tag_ligne(arts[0]),))
                        self._elements[parent] = arts
                li = f"l|{l.check.id}"
                texte = self.texte_ligne(l, court=parent != gi)
                a.insert(parent, "end", iid=li, text=texte, values=(m.nom_zone(l.check.zone),),
                         tags=(self.tag_ligne(l),))
                self._elements[li] = l
        for i in choix:
            if a.exists(i):
                a.selection_set(i)
                a.focus(i)
        try:
            a.update_idletasks()
            a.yview_moveto(haut)
        except tk.TclError:
            pass

    @staticmethod
    def tag_ligne(l: QF.Ligne) -> str:
        return ("masque" if l.rang == QF.RANG_MASQUE else "indice" if l.rang == QF.RANG_INDICE
                else "incertain" if l.rang == QF.RANG_INCERTAIN else "normal")

    def _noter_ouverts(self) -> None:
        a = self.arbre
        self._ouverts = {i for i in a.get_children() if a.item(i, "open")}
        self._ouverts_b = {b for i in a.get_children() for b in a.get_children(i) if a.item(b, "open")}

    # ------------------------------------------------------------------ infobulle
    def texte_bulle(self, iid: str) -> str:
        x, m = self._elements.get(iid), self.o.modele
        if isinstance(x, QF.Ligne):
            lignes = [x.check.nom, m.nom_zone(x.check.zone) + "  ·  " + self.o.texte_etat(x.check)]
            if x.check.contenu:
                lignes.append(self.o.texte_contenu(x.check))
            return "\n".join(lignes)
        if isinstance(x, list) and x:
            return "%s\n%s" % (QF.CC.nom_boutique([l.check for l in x]), m.nom_zone(x[0].check.zone))
        return ""

    def _survol(self, e) -> None:
        iid = self.arbre.identify_row(e.y)
        if iid == self._survole:
            return
        self._survole = iid
        texte = self.texte_bulle(iid) if iid else ""
        if texte:
            self.v.info.montrer(texte, e.x_root, e.y_root)
        else:
            self.v.info.cacher()

    def _cacher_bulle(self) -> None:
        self._survole = None
        self.v.info.cacher()

    # ------------------------------------------------------------------ choix
    def _clic(self, e) -> None:
        iid = self.arbre.identify_row(e.y)
        if iid and self.arbre.identify_element(e.x, e.y) not in ("Treeitem.indicator",):
            self.activer(iid)

    def activer(self, iid: str) -> None:
        """Check : ouvre sa carte, le choisit et centre la vue sur son marqueur ; groupe de carte : ouvre la carte."""
        x = self._elements.get(iid)
        self._cacher_bulle()
        if isinstance(x, QF.Groupe):
            if x.carte:
                self.aller_carte(x.carte)
        elif isinstance(x, QF.Ligne):
            self.aller(x)
        elif isinstance(x, list) and x:                        # boutique : son 1er article (panneau de la boutique)
            self.aller(x[0])

    def _montrer_carte(self, carte: str) -> bool:
        v, o = self.v, self.o
        if v.don is None or carte not in v.don.cartes:
            return False
        f = o.filtre()
        if f.zone is not None and carte not in [k for k, _g, _t in QF.CC.cartes_de_zone(o.modele, v.don, f)]:
            o.choisir_zone(None)                               # sinon la carte serait hors de la liste des cartes
        return True

    def aller_carte(self, carte: str) -> None:
        if self._montrer_carte(carte):
            self.v.ajuster = True
            self.v.ouvrir_carte(carte)

    def aller(self, l: QF.Ligne) -> None:
        v, o = self.v, self.o
        cid = l.check.id
        if l.carte is not None and self._montrer_carte(l.carte):
            v.info.cacher()
            v.ouvrir_carte(l.carte, l.position)
            v._sel_montree = cid                               # déjà montrée : le retour sur le sous-onglet n'y revient pas
            o.choisir(cid)
            p = v.don.positions.get(cid)
            if p is not None and p.boutique:                   # article : le panneau de sa boutique, sur la carte
                mq = next((x for x in v.marqueurs if x.genre == "boutique" and cid in x.ids), None)
                if mq is not None:
                    v.panneau = (v.carte, mq.codes)
                    v._dessiner_panneau()
            if l.position is not None:
                v.centrer(*l.position)
        else:
            o.choisir(cid)                                     # sans carte : détail sous la carte seulement
