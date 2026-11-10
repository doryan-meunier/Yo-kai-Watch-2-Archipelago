"""Sous-onglet « Indices » de l'onglet « Discussion » (à la manière de l'onglet « Hints » du TextClient d'Archipelago) :
tous les indices qui concernent le joueur, qu'il en soit le TROUVEUR (un objet de quelqu'un est dans son monde) ou le
DESTINATAIRE (un de ses objets est chez quelqu'un), y compris ceux créés automatiquement (boutiques).

Colonnes : destinataire, objet (couleur selon progression / utile / piège comme Archipelago), trouveur, lieu, entrée
(affichée seulement si un indice en a une), état (trouvé, ou priorité : prioritaire, non précisé, sans priorité, à
éviter). Tri : non trouvés d'abord puis priorité (clic sur un en-tête : tri par cette colonne, second clic : ordre
inverse). Filtre : texte (sans accents ni casse), « tous / mes objets / dans mon monde », « masquer les trouvés ».

Source : `indices.json`, écrit par le client à chaque Retrieved / SetReply de la clé `_read_hints_{team}_{slot}`
(`client/indices_local.py`) ; relu quand sa date ou sa taille change (aucune connexion du lanceur au serveur, aucune
lecture GDB). Priorité : clic sur l'état (ou Entrée / Espace sur la ligne choisie) d'un indice dont le joueur est le
destinataire et pas encore trouvé -> menu ; le choix est passé au client par `chat_commandes.json` (action UpdateHint),
le serveur répond par la liste mise à jour. Anti-divulgâchage : rien d'autre que les indices donnés par le serveur.

Table dessinée dans un `tk.Text` (et non un `ttk.Treeview`, qui ne colore que des lignes entières) : une ligne par
indice, colonnes par taquets de tabulation, textes trop longs coupés par « … » (le texte complet est dans le détail).
"""
from __future__ import annotations

import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont, ttk

from . import theme as th
from .textes import t
from .tracker import replier
from .vue_yokai import Placeholder

_CLIENT = Path(__file__).resolve().parents[1] / "client"
if str(_CLIENT) not in sys.path:
    sys.path.insert(0, str(_CLIENT))
import chat_local as ch  # noqa: E402  (client/, distribué avec le lanceur)
import indices_local as il  # noqa: E402

TOURS_LECTURE = 3                         # indices.json contrôlé tous les 3 tours de l'onglet (≈ 1 s)
ATTENTE_SERVEUR = 6.0                     # s : priorité demandée non confirmée par le serveur -> signalée
COLONNES = ("destinataire", "objet", "trouveur", "lieu", "entree", "statut")
POIDS = {"destinataire": 14, "objet": 22, "trouveur": 14, "lieu": 26, "entree": 13, "statut": 13}
MIN = {"destinataire": 70, "objet": 90, "trouveur": 70, "lieu": 100, "entree": 60, "statut": 95}
VUES = ("tous", "recus", "monde")         # tous / mes objets (je suis le destinataire) / dans mon monde (trouveur)

FOND = "#1E1718"                          # comme le journal de la Discussion (TextClient)
FOND_PAIR = "#271F21"
FOND_CHOISI = "#4A3D45"
TEXTE = "#EFE8E3"
COULEURS = {
    "moi": "#EE00EE", "joueur": "#F5DD5A", "objet_progression": "#AF99EF", "objet_utile": "#6D8BE8",
    "objet_piege": "#FA8072", "objet": "#00EEEE", "lieu": "#00FF7F", "entree": "#6495ED", "vide": "#8C817B",
    # états (couleurs de l'onglet « Hints » de kvui, Archipelago 0.6)
    "st_40": "#00FF7F", "st_0": "#FFFFFF", "st_10": "#00EEEE", "st_20": "#FA8072", "st_30": "#AF99EF",
    "attente": "#B8ADA6",
}


# ------------------------------------------------------------------------------------------------ sans affichage
def nom_statut(langue: str, statut: int) -> str:
    return t(langue, f"hi_st_{statut if statut in il.STATUTS else 0}")


def filtrer(indices: list[dict], slot: int | None, *, vue: str = "tous", masquer_trouves: bool = False,
            texte: str = "", langue: str = "fr") -> list[dict]:
    cible = replier(texte)
    out = []
    for h in indices:
        if vue == "recus" and h.get("destinataire_slot") != slot:
            continue
        if vue == "monde" and h.get("trouveur_slot") != slot:
            continue
        if masquer_trouves and h.get("trouve"):
            continue
        if cible:
            tout = " ".join(str(h.get(k, "")) for k in ("destinataire", "objet", "trouveur", "lieu", "entree"))
            if cible not in replier(tout + " " + nom_statut(langue, int(h.get("statut", 0) or 0))):
                continue
        out.append(h)
    return out


def _cle_defaut(h: dict) -> tuple:
    st = int(h.get("statut", 0) or 0)
    return (bool(h.get("trouve")), il.RANG_STATUT.get(st, 1), replier(str(h.get("destinataire", ""))),
            replier(str(h.get("objet", ""))), replier(str(h.get("lieu", ""))))


def trier(indices: list[dict], colonne: str | None = None, inverse: bool = False) -> list[dict]:
    """Ordre par défaut (`colonne` None ou « statut ») : non trouvés d'abord, puis prioritaire, non précisé, sans
    priorité, à éviter ; sinon par la colonne (texte replié), l'ordre par défaut départageant."""
    if colonne in (None, "statut"):
        return sorted(indices, key=_cle_defaut, reverse=inverse)
    return sorted(indices, key=lambda h: (replier(str(h.get(colonne, ""))), _cle_defaut(h)), reverse=inverse)


def couper(police: tkfont.Font, texte: str, largeur: int) -> str:
    """`texte` tronqué par « … » pour tenir dans `largeur` pixels."""
    if largeur <= 0:
        return ""
    if police.measure(texte) <= largeur:
        return texte
    bas, haut = 0, len(texte)
    while bas < haut:                              # plus long préfixe qui tient avec « … »
        m = (bas + haut + 1) // 2
        if police.measure(texte[:m].rstrip() + "…") <= largeur:
            bas = m
        else:
            haut = m - 1
    return (texte[:bas].rstrip() + "…") if bas else ""


# ------------------------------------------------------------------------------------------------ vue
class VueIndices:
    """Cadre du sous-onglet, posé par `OngletTexte` dans sa propre grille (`onglet.cadre`)."""

    def __init__(self, parent: tk.Misc, onglet):
        self.o = onglet
        self.th, self.langue, self.dossier = onglet.th, onglet.langue, onglet.dossier
        self.donnees: dict | None = None
        self.signature = None
        self.lignes: list[dict] = []              # indices affichés (filtrés, triés), dans l'ordre des lignes
        self.choix: tuple[int, int] | None = None    # (trouveur, location) de la ligne choisie
        self.tri: tuple[str | None, bool] = (None, False)
        self.attente: dict[tuple[int, int], tuple[int, float]] = {}   # demandé : (trouveur, location) -> (état, échéance)
        self.message = ""
        self.visible = False
        self.a_refaire = True
        self._tour = 0
        self._x: list[int] = []                   # début de chaque colonne affichée (pixels)
        self._cols: list[str] = []
        self.v_trouves = tk.BooleanVar(onglet.sc.r, value=False)
        self.construire(parent)
        self.recharger(force=True)

    def tr(self, cle: str, **p) -> str:
        return t(self.langue, cle, **p)

    # ------------------------------------------------------------------ construction
    def construire(self, parent: tk.Misc) -> None:
        T, px = self.th, self.th.px
        f = self.cadre = tk.Frame(parent, bg=th.BLANC)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)
        # filtres
        fl = tk.Frame(f, bg=th.BLANC)
        fl.grid(row=0, column=0, sticky="ew", pady=(px(8), px(6)))
        fl.columnconfigure(0, weight=1)
        self.v_recherche = tk.StringVar(self.o.sc.r)
        self.e_recherche = Placeholder(fl, T, self.tr("hi_recherche"), self.v_recherche)
        self.e_recherche.grid(row=0, column=0, sticky="ew", ipady=px(3), padx=(0, px(8)))
        self.e_recherche.bind("<KeyRelease>", lambda _e: self.planifier())
        self.e_recherche.bind("<Escape>", lambda _e: (self.e_recherche.delete(0, "end"), self.planifier()))
        self.e_recherche.bind("<Down>", lambda _e: (self.corps.focus_set(), self.deplacer(0), "break")[2])
        self.l_vue = ttk.Combobox(fl, state="readonly", style="Yokai.TCombobox", font=T["texte"], width=24,
                                  values=[self.tr(f"hi_vue_{v}") for v in VUES])
        self.l_vue.current(0)
        self.l_vue.grid(row=0, column=1, sticky="e")
        self.l_vue.bind("<<ComboboxSelected>>", lambda _e: self.planifier())
        op = tk.Frame(f, bg=th.BLANC)
        op.grid(row=1, column=0, sticky="ew", pady=(0, px(6)))
        self.b_trouves = th.Bascule(op, T, self.tr("hi_masquer_trouves"), self.v_trouves, self.planifier)
        self.b_trouves.pack(side="left")
        self.l_compte = tk.Label(op, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX, anchor="e")
        self.l_compte.pack(side="right")
        # table : en-têtes (cliquables : tri) + corps
        cadre = tk.Frame(f, bg=th.NOIR, padx=px(2), pady=px(2))
        cadre.grid(row=2, column=0, sticky="nsew")
        cadre.columnconfigure(0, weight=1)
        cadre.rowconfigure(1, weight=1)
        self.police = T["texte"]
        self.police_tete = T["bouton_petit"]
        self.police_gras = tkfont.Font(root=self.o.sc.r, font=self.police)
        self.police_gras.configure(weight="bold")
        self.padx = px(10)
        self.tete = tk.Text(cadre, height=1, wrap="none", bg=th.OR, fg=th.NOIR, font=self.police_tete, relief="flat",
                            bd=0, highlightthickness=0, padx=self.padx, pady=px(4), cursor="hand2", takefocus=0)
        self.tete.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.corps = x = tk.Text(cadre, height=10, width=60, wrap="none", bg=FOND, fg=TEXTE, font=self.police,
                                 relief="flat", bd=0, highlightthickness=0, padx=self.padx, pady=px(4),
                                 spacing1=px(3), spacing3=px(3), cursor="arrow", takefocus=1,
                                 selectbackground=FOND_CHOISI, inactiveselectbackground=FOND_CHOISI,
                                 insertbackground=FOND, exportselection=False)
        for g, c in COULEURS.items():
            x.tag_configure(g, foreground=c)
        x.tag_configure("moi", font=self.police_gras)
        x.tag_configure("pair", background=FOND_PAIR)
        x.tag_configure("choisi", background=FOND_CHOISI)
        x.tag_configure("modifiable", underline=True)
        x.tag_configure("message", foreground="#D8D0CA", justify="center", spacing1=px(24), wrap="word")
        x.tag_raise("choisi")
        x.tag_raise("sel")
        x.tag_bind("modifiable", "<Enter>", lambda _e: x.configure(cursor="hand2"))
        x.tag_bind("modifiable", "<Leave>", lambda _e: x.configure(cursor="arrow"))
        x.configure(state="disabled")
        x.bind("<Button-1>", self._clic)
        x.bind("<Up>", lambda _e: self.deplacer(-1))
        x.bind("<Down>", lambda _e: self.deplacer(1))
        x.bind("<Prior>", lambda _e: self.deplacer(-10))
        x.bind("<Next>", lambda _e: self.deplacer(10))
        for ev in ("<Return>", "<KP_Enter>", "<space>"):
            x.bind(ev, lambda _e: (self.menu_statut(), "break")[1])
        self.defil = ttk.Scrollbar(cadre, orient="vertical", style="Yokai.Vertical.TScrollbar", command=x.yview)
        self.defil.grid(row=1, column=1, sticky="ns")
        x.configure(yscrollcommand=self.defil.set)
        x.grid(row=1, column=0, sticky="nsew")
        x.bind("<Configure>", lambda _e: self.dessiner(), add="+")
        self.tete.bind("<Button-1>", self._clic_tete)
        self.tete.configure(state="disabled")
        # détail de la ligne choisie (texte complet) et messages
        self.l_detail = tk.Label(f, text="", font=T["texte"], bg=th.CYAN_PALE, fg=th.CYAN_TEXTE, anchor="w",
                                 justify="left", padx=px(8), pady=px(3))
        self.l_detail.grid(row=3, column=0, sticky="ew", pady=(px(6), 0))
        self.l_aide = tk.Label(f, text=self.tr("hi_aide_clavier"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                               anchor="w", justify="left")
        self.l_aide.grid(row=4, column=0, sticky="ew", pady=(px(4), 0))
        self.menu = tk.Menu(f, tearoff=0, font=T["texte"])
        f.bind("<Configure>", self._largeur, add="+")

    def _largeur(self, _e=None) -> None:
        lg = max(self.th.px(200), self.cadre.winfo_width() - self.th.px(30))
        self.l_detail.configure(wraplength=lg)
        self.l_aide.configure(wraplength=lg)

    # ------------------------------------------------------------------ données
    @property
    def slot(self) -> int | None:
        return (self.donnees or {}).get("slot")

    def activer(self, visible: bool) -> None:
        self.visible = visible
        if visible:
            self.recharger()
            if self.a_refaire:
                self.remplir()

    def surveiller(self) -> None:
        """Appelé à chaque tour de l'onglet « Discussion » : relit `indices.json` s'il a changé, échéances."""
        self._tour += 1
        if self._tour % TOURS_LECTURE == 0:
            self.recharger()
        self._verifier_attente()

    def recharger(self, force: bool = False) -> bool:
        p = self.dossier / il.NOM_INDICES
        try:
            st = p.stat()
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if sig == self.signature and not force:
            return False
        self.signature = sig
        self.donnees = il.lire_indices(self.dossier) if sig is not None else None
        for h in (self.donnees or {}).get("indices", []):             # demandes confirmées par le serveur
            k = (h.get("trouveur_slot"), h.get("location"))
            if k in self.attente and (h.get("statut") == self.attente[k][0] or h.get("trouve")):
                self.attente.pop(k, None)
        self.a_refaire = True
        if self.visible:
            self.remplir()
        return True

    def _vue(self) -> str:
        i = self.l_vue.current()
        return VUES[i] if 0 <= i < len(VUES) else "tous"

    def planifier(self) -> None:
        if not getattr(self, "_prevu", False):
            self._prevu = True
            self.cadre.after(120, self._remplir_prevu)

    def _remplir_prevu(self) -> None:
        self._prevu = False
        self.remplir()

    def remplir(self) -> None:
        tous = (self.donnees or {}).get("indices", [])
        self.lignes = trier(filtrer(tous, self.slot, vue=self._vue(), masquer_trouves=self.v_trouves.get(),
                                    texte=self.e_recherche.valeur(), langue=self.langue), *self.tri)
        self.a_refaire = False
        non_trouves = sum(1 for h in tous if not h.get("trouve"))
        if len(self.lignes) == len(tous):
            self.l_compte.configure(text=self.tr("hi_compte", n=len(tous), nt=non_trouves))
        else:
            self.l_compte.configure(text=self.tr("hi_compte_filtre", n=len(self.lignes), total=len(tous)))
        self.dessiner()

    # ------------------------------------------------------------------ dessin
    def _colonnes_visibles(self) -> list[str]:
        entrees = any(h.get("entree") for h in (self.donnees or {}).get("indices", []))
        return [c for c in COLONNES if c != "entree" or entrees]

    def _positions(self) -> None:
        """Début de chaque colonne (pixels, depuis le bord du texte) selon la largeur disponible."""
        px = self.th.px
        cols = self._colonnes_visibles()
        dispo = max(px(300), self.corps.winfo_width() - 2 * self.padx - px(4))
        mins = {c: px(MIN[c]) for c in cols}
        total = sum(POIDS[c] for c in cols)
        larg = {c: max(mins[c], dispo * POIDS[c] // total) for c in cols}
        exces = sum(larg.values()) - dispo
        if exces > 0:                                # rendre la place prise par les minimums aux colonnes larges
            for c in sorted(cols, key=lambda c: -(larg[c] - mins[c])):
                prise = min(exces, larg[c] - mins[c])
                larg[c] -= prise
                exces -= prise
        x, self._x = 0, []
        for c in cols:
            self._x.append(x)
            x += larg[c]
        self._x.append(x)
        self._cols = cols

    def _cellules(self, h: dict) -> list[tuple[str, str, str]]:
        """(colonne, texte, genre) d'une ligne."""
        slot = self.slot
        st = int(h.get("statut", 0) or 0)
        k = (h.get("trouveur_slot"), h.get("location"))
        if k in self.attente:
            etat, genre_st = self.tr("hi_attente", etat=nom_statut(self.langue, self.attente[k][0])), "attente"
        else:
            etat, genre_st = nom_statut(self.langue, st), f"st_{st if st in il.STATUTS else 0}"
            if il.modifiable(h, slot):
                etat += " ▾"
        return [("destinataire", str(h.get("destinataire", "?")), "moi" if h.get("destinataire_slot") == slot
                 else "joueur"),
                ("objet", str(h.get("objet", "?")), ch.genre_objet(int(h.get("flags", 0) or 0))),
                ("trouveur", str(h.get("trouveur", "?")), "moi" if h.get("trouveur_slot") == slot else "joueur"),
                ("lieu", str(h.get("lieu", "?")), "lieu"),
                ("entree", str(h.get("entree") or ""), "entree"),
                ("statut", etat, genre_st)]

    def dessiner(self) -> None:
        if self.corps.winfo_width() <= 1:
            return
        self._positions()
        gap = self.th.px(10)
        tabs = " ".join(f"{x} left" for x in self._x[1:-1])
        # en-têtes
        tt = self.tete
        tt.configure(state="normal", tabs=tabs or "")
        tt.delete("1.0", "end")
        col, inv = self.tri
        for i, c in enumerate(self._cols):
            lib = self.tr(f"hi_col_{c}")
            if c == (col or "statut") and (col is not None or inv):
                lib += " ▼" if inv else " ▲"
            w = self._x[i + 1] - self._x[i] - gap
            tt.insert("end", ("\t" if i else "") + couper(self.police_tete, lib, w))
        tt.configure(state="disabled")
        # corps
        x = self.corps
        haut = x.yview()[0]
        x.configure(state="normal", tabs=tabs or "")
        x.delete("1.0", "end")
        if not self.lignes:
            cle = "hi_vide_filtre" if (self.donnees or {}).get("indices") else \
                "hi_vide" if self.donnees is not None else "hi_jamais"
            x.insert("end", self.tr(cle), ("message",))
        for n, h in enumerate(self.lignes):
            debut = x.index("end-1c")
            cells = {c: (txt, g) for c, txt, g in self._cellules(h)}
            for i, c in enumerate(self._cols):
                txt, g = cells[c]
                w = self._x[i + 1] - self._x[i] - gap
                tags = (g, "modifiable") if c == "statut" and il.modifiable(h, self.slot) and \
                    (h.get("trouveur_slot"), h.get("location")) not in self.attente else (g,)
                if i:
                    x.insert("end", "\t")
                x.insert("end", couper(self.police_gras if g == "moi" else self.police, txt, w) or " ", tags)
            x.insert("end", "\n")
            if n % 2:
                x.tag_add("pair", debut, f"{debut} lineend+1c")
        if self.lignes:
            x.delete("end-2c", "end-1c")                              # pas de ligne vide à la fin
        self._marquer_choix()
        x.configure(state="disabled")
        x.yview_moveto(haut)
        self._maj_detail()

    def _index_choix(self) -> int | None:
        if self.choix is None:
            return None
        return next((i for i, h in enumerate(self.lignes)
                     if (h.get("trouveur_slot"), h.get("location")) == self.choix), None)

    def _marquer_choix(self) -> None:
        x = self.corps
        x.tag_remove("choisi", "1.0", "end")
        i = self._index_choix()
        if i is not None:
            x.tag_add("choisi", f"{i + 1}.0", f"{i + 1}.0 lineend+1c")

    def texte_affiche(self) -> str:
        return self.corps.get("1.0", "end-1c")

    def entetes(self) -> str:
        return self.tete.get("1.0", "end-1c")

    # ------------------------------------------------------------------ sélection, tri
    def choisir(self, i: int | None) -> None:
        if i is None or not self.lignes:
            self.choix = None
        else:
            i = max(0, min(len(self.lignes) - 1, i))
            h = self.lignes[i]
            self.choix = (h.get("trouveur_slot"), h.get("location"))
            self.corps.see(f"{i + 1}.0")
        self._marquer_choix()
        self._maj_detail()

    def deplacer(self, pas: int) -> str:
        i = self._index_choix()
        self.choisir(0 if i is None else i + pas)
        return "break"

    def _colonne_en(self, xpix: int) -> str | None:
        xpix -= self.padx
        for i, c in enumerate(self._cols):
            if self._x[i] <= xpix < self._x[i + 1]:
                return c
        return self._cols[-1] if self._cols and xpix >= self._x[-1] else None

    def _clic(self, e) -> str:
        self.corps.focus_set()
        if not self.lignes:
            return "break"
        ligne = int(self.corps.index(f"@{e.x},{e.y}").split(".")[0]) - 1
        if not 0 <= ligne < len(self.lignes):
            return "break"
        self.choisir(ligne)
        if self._colonne_en(e.x) == "statut":
            self.menu_statut(e.x_root, e.y_root)
        return "break"

    def _clic_tete(self, e) -> str:
        c = self._colonne_en(e.x)
        if c:
            self.trier_par(c)
        return "break"

    def trier_par(self, colonne: str) -> None:
        col, inv = self.tri
        actuelle = col or "statut"
        self.tri = (None if colonne == "statut" else colonne, not inv if colonne == actuelle else False)
        self.remplir()

    # ------------------------------------------------------------------ détail
    def _maj_detail(self) -> None:
        i = self._index_choix()
        morceaux = []
        if i is not None:
            h = self.lignes[i]
            morceaux.append(self.tr("hi_detail", objet=h.get("objet", "?"), dest=h.get("destinataire", "?"),
                                    lieu=h.get("lieu", "?"), trouveur=h.get("trouveur", "?"),
                                    etat=nom_statut(self.langue, int(h.get("statut", 0) or 0))))
            if h.get("entree"):
                morceaux.append(self.tr("hi_detail_entree", entree=h["entree"]))
            if il.modifiable(h, self.slot):
                morceaux.append(self.tr("hi_detail_modifiable"))
        if self.donnees is not None and not self.donnees.get("connecte", True):
            morceaux.append(self.tr("hi_hors_ligne"))
        if self.message:
            morceaux.append(self.message)
        texte = " ".join(morceaux)
        self.l_detail.configure(text=th.insecables(texte) if texte else "")
        if texte:
            self.l_detail.grid()
        else:
            self.l_detail.grid_remove()

    def informer(self, texte: str) -> None:
        self.message = texte
        self._maj_detail()

    # ------------------------------------------------------------------ priorité (UpdateHint)
    def menu_statut(self, x_root: int | None = None, y_root: int | None = None) -> bool:
        """Menu des priorités de la ligne choisie ; False (et un message) si elle n'est pas modifiable."""
        i = self._index_choix()
        if i is None:
            return False
        h = self.lignes[i]
        if not il.modifiable(h, self.slot):
            self.informer(self.tr("hi_non_modifiable_trouve" if h.get("trouve") else "hi_non_modifiable"))
            return False
        m = self.menu
        m.delete(0, "end")
        actuel = int(h.get("statut", 0) or 0)
        for st in il.STATUTS_CHOISIS:
            m.add_command(label=("✓ " if st == actuel else "    ") + nom_statut(self.langue, st),
                          command=lambda s=st, h=h: self.changer_statut(h, s))
        if x_root is None:
            bb = self.corps.bbox(f"{i + 1}.0") or (0, 0, 0, 0)
            x_root = self.corps.winfo_rootx() + (self._x[-2] if len(self._x) > 1 else 0) + self.padx
            y_root = self.corps.winfo_rooty() + bb[1] + bb[3]
        try:
            m.tk_popup(x_root, y_root)
        finally:
            m.grab_release()
        return True

    def changer_statut(self, h: dict, statut: int) -> bool:
        """Dépose l'action UpdateHint pour le client connecté. True si déposée."""
        if not il.modifiable(h, self.slot) or statut not in il.STATUTS_CHOISIS:
            return False
        if statut == int(h.get("statut", 0) or 0):
            return False
        self.o.maj_etat()
        session = self.o.session
        if not session:
            self.informer(self.tr("hi_hors_ligne_action"))
            return False
        action = il.action_statut(int(h["trouveur_slot"]), int(h["location"]), statut)
        texte = self.tr("hi_action", objet=h.get("objet", "?"), etat=nom_statut(self.langue, statut))
        try:
            ch.deposer_commande(self.dossier, texte, session, action=action)
        except (OSError, ValueError) as e:
            self.informer(self.tr("tx_l_erreur_ecriture", erreur=e))
            return False
        self.attente[(int(h["trouveur_slot"]), int(h["location"]))] = (statut, time.monotonic() + ATTENTE_SERVEUR)
        self.message = ""
        self.remplir()
        return True

    def _verifier_attente(self) -> None:
        maintenant = time.monotonic()
        perimees = [k for k, (_s, ech) in self.attente.items() if maintenant > ech]
        for k in perimees:
            self.attente.pop(k, None)
        if perimees:
            self.informer(self.tr("hi_sans_reponse"))
            self.remplir()

    def focus_recherche(self) -> None:
        self.e_recherche.focus_set()
        self.e_recherche.select_range(0, "end")
