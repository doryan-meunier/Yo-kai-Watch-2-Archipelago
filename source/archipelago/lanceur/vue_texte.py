"""Onglet « Discussion » du lanceur, à la manière du TextClient d'Archipelago : journal des messages du serveur
(PrintJSON) aux couleurs habituelles d'Archipelago, champ de saisie pour la discussion (Say) et les commandes du serveur
(`!hint`, `!remaining`…), commandes locales (`/help`, `/clear`, `/received`, `/missing`), historique, recherche.

Le lanceur n'a pas de connexion au serveur : il lit `messages.jsonl` écrit par le client et lui passe les messages à
envoyer par `chat_commandes.json` (`client/chat_local.py`, fichiers locaux seulement, aucune lecture GDB). L'état du
client (connecté, session visée) vient de `etat.json`. Anti-divulgâchage : rien d'autre que ce que le serveur envoie
lui-même ; `/missing` ne donne que les noms des locations (jamais leur contenu).

Clavier : Entrée (envoyer), Flèches haut / bas (historique), Échap (vider le champ), Ctrl+F (recherche, `vue.py`),
Tab / Maj+Tab. Autocomplétion (`autocompletion.py`) : à partir de « ! », liste au-dessus du champ, dans l'onglet ; tant
qu'elle est ouverte, flèches (se déplacer), Tab ou Entrée (compléter), Échap (fermer), clic ; le focus reste au champ.

Deux sous-onglets : « Discussion » (le journal, premier) et « Indices » (`vue_indices.py` : indices du slot lus dans
`indices.json`, priorité modifiable). La ligne d'état du client est commune aux deux.
"""
from __future__ import annotations

import json
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont, messagebox, ttk
from typing import Callable

from . import autocompletion as AC
from . import theme as th
from .textes import t
from .tracker import replier
from .vue_yokai import Placeholder

_CLIENT = Path(__file__).resolve().parents[1] / "client"
if str(_CLIENT) not in sys.path:
    sys.path.insert(0, str(_CLIENT))
import chat_local as ch  # noqa: E402  (client/, distribué avec le lanceur)

INTERVALLE = 300                          # ms entre deux lectures du journal
TOURS_ETAT = 3                            # etat.json relu tous les 3 tours (≈ 1 s)
ETAT_PERIME = 15.0                        # s : même règle que logique.ETAT_PERIME
ATTENTE_CLIENT = 5.0                      # s : une commande non reprise par le client est signalée
AFFICHAGE_MAX = 2000                      # messages gardés à l'écran
HISTORIQUE_MAX = 100
RACCOURCIS = ("!hint ", "!hint_location ", "!remaining", "!missing", "!checked", "!status", "!players", "/help")

# Couleurs du journal (fond sombre comme le TextClient ; teintes par défaut de kvui d'Archipelago)
FOND_JOURNAL = "#1E1718"
TEXTE_JOURNAL = "#EFE8E3"
COULEURS = {
    "texte": TEXTE_JOURNAL, "moi": "#EE00EE", "joueur": "#F5DD5A",
    "objet_progression": "#AF99EF", "objet_utile": "#6D8BE8", "objet_piege": "#FA8072", "objet": "#00EEEE",
    "lieu": "#00FF7F", "entree": "#6495ED",
    "indice_trouve": "#00FF7F", "indice_non_trouve": "#FF6B6B", "indice_prioritaire": "#AF99EF",
    "indice_eviter": "#FA8072", "indice_sans_priorite": "#6D8BE8",
    "rouge": "#FF5555", "vert": "#00FF7F", "jaune": "#FAFAD2", "bleu": "#6495ED", "magenta": "#EE00EE",
    "cyan": "#00EEEE", "blanc": "#FFFFFF", "noir": "#9A8F89", "violet": "#AF99EF", "orange": "#FF7700",
    "gras": TEXTE_JOURNAL,
    # lignes du client et du lanceur
    "heure": "#8C817B", "systeme": "#B8ADA6", "systeme_ok": "#7FD88F", "attention": "#F2A04A", "erreur": "#FF8080",
    "envoi": "#D8D0CA", "local": "#9FD8E8", "evenement": th.OR, "discret": "#A69C94",
}
GRAS = {"moi", "gras", "evenement"}
ITALIQUE = {"systeme", "systeme_ok", "attention", "local", "discret"}
# couleur du texte ordinaire selon le type de PrintJSON
TYPES_LIGNE = {"Goal": "evenement", "Release": "evenement", "Collect": "evenement", "Countdown": "evenement",
               "Join": "discret", "Part": "discret", "TagsChanged": "discret", "Tutorial": "discret"}


# ------------------------------------------------------------------------------------------------ sans affichage
def lire_etat(dossier: Path) -> dict | None:
    try:
        d = json.loads((Path(dossier) / "etat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def etat_client(dossier: Path, maintenant: float | None = None) -> tuple[str, str, dict, str | None]:
    """(niveau de la pastille, clé du texte, paramètres, session du client connecté ou None)."""
    d = lire_etat(dossier)
    maintenant = time.time() if maintenant is None else maintenant
    try:
        frais = d is not None and maintenant - float(d.get("horodatage", 0)) < ETAT_PERIME
    except (TypeError, ValueError):
        frais = False
    if not frais or d.get("phase") == "arrete":
        return "neutre", "tx_arrete", {}, None
    p = {"serveur": d.get("serveur") or "?", "slot": d.get("slot") or "?", "message": d.get("message") or "?"}
    etat = d.get("etat")
    if etat == 3:
        session = d.get("session_chat") if isinstance(d.get("session_chat"), str) and d.get("session_chat") else None
        return ("ok" if session else "attention"), "tx_connecte", p, session
    if etat in (2, 5):
        return "attention", "tx_connexion", p, None
    return "erreur" if etat == 4 else "attention", "tx_erreur", p, None


def rendu(entree: dict, langue: str) -> list[tuple[str, str]]:
    """Morceaux (texte, genre) d'une entrée de `messages.jsonl` (ou locale du lanceur)."""
    if entree.get("type") == "systeme":
        cle, p = str(entree.get("cle", "")), dict(entree.get("params") or {})
        if cle == "refuse":
            p["erreurs"] = ", ".join(str(e) for e in p.get("erreurs") or []) or "?"
        if cle == "non_envoye" and p.get("raison") in ("non_connecte", "action_invalide"):
            p["raison"] = t(langue, f"tx_s_{p['raison']}")
        if cle == "statut_indice":
            from .vue_indices import nom_statut
            p["etat"] = nom_statut(langue, p.get("statut") if isinstance(p.get("statut"), int) else 0)
            p.setdefault("objet", "?")
            p.setdefault("lieu", "?")
        genre = {"connecte": "systeme_ok", "deconnecte": "attention", "refuse": "erreur", "envoye": "envoi",
                 "non_envoye": "erreur", "statut_indice": "envoi"}.get(cle, "systeme")
        connues = ("connecte", "deconnecte", "refuse", "envoye", "non_envoye", "statut_indice")
        texte = t(langue, f"tx_s_{cle}", **p) if cle in connues else t(langue, "tx_s_inconnu", nom=cle)
        return [(texte, genre)]
    if "local" in entree:
        return [(str(x), str(g)) for x, g in entree["local"]]
    base = TYPES_LIGNE.get(str(entree.get("type", "")), "texte")
    out = []
    for p in entree.get("parties") or []:
        if not isinstance(p, dict):
            continue
        g = str(p.get("g", "texte"))
        out.append((str(p.get("x", "")), base if g == "texte" else (g if g in COULEURS else "texte")))
    return out


# ------------------------------------------------------------------------------------------------ onglet
class OngletTexte:
    """Contenu de l'onglet (cadre blanc posé dans une carte pleine de la `Scene`)."""

    def __init__(self, scene: th.Scene, theme: th.Theme, langue: str, dossier: Path,
                 confirmer: Callable[[str, str], bool] | None = None, surveiller: bool = True):
        self.sc, self.th, self.langue, self.dossier = scene, theme, langue, Path(dossier)
        self.confirmer = confirmer or (lambda titre, texte: messagebox.askyesno(titre, texte, parent=self.sc.r))
        self.lecteur = ch.LecteurMessages(self.dossier, garder=AFFICHAGE_MAX)
        self.entrees: list[dict] = []
        self.historique: list[str] = []
        self.pos_historique: int | None = None
        self.brouillon = ""
        self.attente: dict[str, tuple[str, float]] = {}       # commande déposée -> (texte, échéance)
        self.visible = False
        self.etat = ("neutre", "tx_arrete", {}, None)
        self._tour = 0
        self._filtre = ""
        self.v_auto = tk.BooleanVar(scene.r, value=True)
        self.vue = "discussion"                                 # sous-onglet : discussion | indices
        # autocomplétion de la console (`autocompletion.py`)
        self.ac: AC.Liste | None = None
        self.ac_ouverte = False
        self.ac_choix: int | None = None
        self._ac_texte: str | None = ""                         # texte pour lequel la liste est à jour
        self._ac_touche = False                                 # choix déplacé à la main depuis la dernière frappe
        self._ac_texte_note = ""
        self._ac_catalogue = AC.Catalogue()
        th.styler_ttk(scene.r, theme)
        self.construire()
        self.maj_etat()
        self.lire()
        if surveiller:
            self.cadre.after(INTERVALLE, self._surveiller)

    def tr(self, cle: str, **p) -> str:
        return t(self.langue, cle, **p)

    # ------------------------------------------------------------------ construction
    def construire(self) -> None:
        T, px = self.th, self.th.px
        f = self.cadre = tk.Frame(self.sc.c, bg=th.BLANC)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)
        tete = tk.Frame(f, bg=th.BLANC)
        tete.grid(row=0, column=0, sticky="ew")
        th.Badge(tete, T, None).pack(side="left")
        self.l_titre = tk.Label(tete, text=self.tr("tx_titre"), font=T["carte"], bg=th.BLANC, fg=th.NOIR)
        self.l_titre.pack(side="left", padx=(px(8), 0))
        # outils du journal (cachés dans le sous-onglet « Indices »)
        self.cadre_outils = outils = tk.Frame(tete, bg=th.BLANC)
        outils.pack(side="right")
        self.b_effacer = th.Pilule(outils, T, self.tr("tx_effacer"), self.effacer, police="bouton_petit", padx=12,
                                   pady=3)
        self.b_effacer.pack(side="right", padx=(px(10), 0))
        self.b_auto = th.Bascule(outils, T, self.tr("tx_auto"), self.v_auto, self._auto_change)
        self.b_auto.pack(side="right")
        # sous-onglets (Discussion d'abord)
        self.cadre_vues = vues = tk.Frame(tete, bg=th.BLANC)
        vues.pack(side="right", padx=(0, px(14)))
        self.b_vues = {}
        for cle, texte in (("discussion", self.tr("tx_vue_discussion")), ("indices", self.tr("tx_vue_indices"))):
            b = th.Pilule(vues, T, texte, lambda k=cle: self.changer_vue(k), police="bouton_petit", padx=12, pady=3,
                          genre="onglet" if cle == self.vue else "normal")
            b.pack(side="left", padx=(px(2), 0))
            self.b_vues[cle] = b
        # recherche
        rch = tk.Frame(f, bg=th.BLANC)
        rch.grid(row=1, column=0, sticky="ew", pady=(px(8), px(6)))
        rch.columnconfigure(0, weight=1)
        self.v_recherche = tk.StringVar(self.sc.r)
        self.e_recherche = Placeholder(rch, T, self.tr("tx_recherche"), self.v_recherche)
        self.e_recherche.grid(row=0, column=0, sticky="ew", ipady=px(3), padx=(0, px(8)))
        self.e_recherche.bind("<KeyRelease>", lambda _e: self.planifier())
        self.e_recherche.bind("<Escape>", lambda _e: (self.e_recherche.delete(0, "end"), self.planifier()))
        self.e_recherche.bind("<Return>", lambda _e: (self.e_saisie.focus_set(), "break")[1])
        self.l_compte = tk.Label(rch, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX, anchor="e")
        self.l_compte.grid(row=0, column=1, sticky="e")
        # journal
        cadre = tk.Frame(f, bg=th.NOIR, padx=px(2), pady=px(2))
        cadre.grid(row=2, column=0, sticky="nsew")
        cadre.columnconfigure(0, weight=1)
        cadre.rowconfigure(0, weight=1)
        base = T["texte"]
        self.police = base
        self.police_gras = tkfont.Font(root=self.sc.r, font=base)
        self.police_gras.configure(weight="bold")
        self.police_ital = tkfont.Font(root=self.sc.r, font=base)
        self.police_ital.configure(slant="italic")
        self.police_petite = T["petit"]
        self.texte = x = tk.Text(cadre, height=12, width=60, wrap="word", bg=FOND_JOURNAL, fg=TEXTE_JOURNAL,
                                 font=base, relief="flat", bd=0, highlightthickness=0, padx=px(10), pady=px(8),
                                 spacing1=px(2), spacing3=px(2), insertbackground=TEXTE_JOURNAL, cursor="arrow",
                                 selectbackground="#5B4A55", selectforeground="#FFFFFF", takefocus=1,
                                 inactiveselectbackground="#4A3D45")
        for g, c in COULEURS.items():
            x.tag_configure(g, foreground=c, font=self.police_gras if g in GRAS else
                            self.police_ital if g in ITALIQUE else base)
        x.tag_configure("heure", font=self.police_petite)
        x.tag_configure("trouve", background="#6B5400")
        x.tag_raise("trouve")
        x.configure(state="disabled")
        x.bind("<Key>", self._touche_journal)
        self.defil = ttk.Scrollbar(cadre, orient="vertical", style="Yokai.Vertical.TScrollbar", command=x.yview)
        self.defil.grid(row=0, column=1, sticky="ns")
        x.configure(yscrollcommand=self.defil.set)
        x.grid(row=0, column=0, sticky="nsew")
        # saisie
        sai = tk.Frame(f, bg=th.BLANC)
        sai.grid(row=3, column=0, sticky="ew", pady=(px(8), 0))
        sai.columnconfigure(0, weight=1)
        self.v_saisie = tk.StringVar(self.sc.r)
        self.e_saisie = Placeholder(sai, T, self.tr("tx_invite"), self.v_saisie)
        self.e_saisie.grid(row=0, column=0, sticky="ew", ipady=px(5), padx=(0, px(8)))
        for ev in ("<Return>", "<KP_Enter>"):
            self.e_saisie.bind(ev, lambda _e: self.touche_entree())
        self.e_saisie.bind("<Up>", lambda _e: self.touche_fleche(-1))
        self.e_saisie.bind("<Down>", lambda _e: self.touche_fleche(1))
        self.e_saisie.bind("<Escape>", lambda _e: self.touche_echap())
        self.b_envoyer = th.Pilule(sai, T, self.tr("tx_envoyer"), self.envoyer, genre="or", police="bouton_petit",
                                   padx=16, pady=4)
        self.b_envoyer.grid(row=0, column=1, sticky="e")
        # raccourcis : insèrent la commande dans le champ (rien n'est envoyé sans Entrée)
        rac = self.cadre_raccourcis = tk.Frame(f, bg=th.BLANC)
        rac.grid(row=4, column=0, sticky="ew", pady=(px(6), 0))
        tk.Label(rac, text=self.tr("tx_raccourcis"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX).pack(
            side="left", padx=(0, px(4)))
        self.b_raccourcis = []
        for cmd in RACCOURCIS:
            b = th.Pilule(rac, T, cmd.strip(), lambda c=cmd: self.inserer(c), police="bouton_petit", padx=8,
                          pady=2)
            b.pack(side="left", padx=(0, px(1)))
            self.b_raccourcis.append(b)
        # état du client
        et = tk.Frame(f, bg=th.BLANC)
        et.grid(row=5, column=0, sticky="ew", pady=(px(8), 0))
        et.columnconfigure(1, weight=1)
        self.p_etat = th.Pastille(et, T)
        haut = px(3) + max(0, (T["texte"].metrics("linespace") - self.p_etat.d) // 2)
        self.p_etat.grid(row=0, column=0, sticky="nw", pady=(haut, 0), padx=(0, px(8)))
        self.l_etat = tk.Label(et, text="", font=T["texte"], bg=th.BLANC, fg=th.TEXTE, justify="left", anchor="w")
        self.l_etat.grid(row=0, column=1, sticky="w", pady=(px(2), px(1)))
        self.l_aide = tk.Label(f, text=self.tr("tx_aide_clavier"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                               anchor="w", justify="left")
        self.l_aide.grid(row=6, column=0, sticky="ew", pady=(px(4), 0))
        f.bind("<Configure>", self._largeur, add="+")
        # sous-onglet « Indices » (même place que le journal ; la ligne d'état reste visible)
        from .vue_indices import VueIndices
        self.indices = VueIndices(f, self)
        self._widgets_discussion = [rch, cadre, sai, rac, self.l_aide]
        self._construire_propositions()

    def _construire_propositions(self) -> None:
        """Liste de l'autocomplétion : un cadre DANS l'onglet, posé au-dessus du champ de saisie (créé en dernier, donc
        devant le journal) ; aucune fenêtre, et ni le cadre ni la liste ne prennent le focus. Fermée, elle n'existe pas
        pour le gestionnaire de placement. Le clic passe avant la classe Listbox (qui prendrait le focus)."""
        T, px = self.th, self.th.px
        self.ac_cadre = tk.Frame(self.cadre, bg=th.OR, padx=px(2), pady=px(2), takefocus=0)
        self.ac_liste = lb = tk.Listbox(self.ac_cadre, font=T["texte"], bg=FOND_JOURNAL, fg=TEXTE_JOURNAL, height=1,
                                        relief="flat", bd=0, highlightthickness=0, activestyle="none", takefocus=0,
                                        exportselection=False, selectbackground="#5B4A55", selectforeground="#FFFFFF",
                                        selectmode="browse")
        lb.pack(fill="x")
        self.ac_note = tk.Label(self.ac_cadre, font=T["petit"], bg=FOND_JOURNAL, fg=COULEURS["discret"], anchor="w",
                                justify="left", padx=px(4))
        self.ac_note.pack(fill="x")
        lb.bind("<Button-1>", self._ac_clic)
        lb.bind("<Motion>", self._ac_survol)
        e = self.e_saisie
        e.bind("<KeyRelease>", lambda _e: self.ac_maj(), add="+")
        e.bind("<Tab>", lambda _e: "break" if self.ac_completer() else None)
        e.bind("<FocusOut>", lambda _e: self.ac_fermer(), add="+")

    def changer_vue(self, vue: str) -> None:
        """Sous-onglet « Discussion » (journal) ou « Indices »."""
        if vue not in self.b_vues:
            return
        self.vue = vue
        self.ac_fermer()
        for cle, b in self.b_vues.items():
            b.changer_genre("onglet" if cle == vue else "normal")
        self.l_titre.configure(text=self.tr("tx_titre" if vue == "discussion" else "hi_titre"))
        if vue == "indices":
            for w in self._widgets_discussion:
                w.grid_remove()
            self.cadre_outils.pack_forget()
            self.indices.cadre.grid(row=1, column=0, rowspan=4, sticky="nsew")
        else:
            self.indices.cadre.grid_remove()
            for w in self._widgets_discussion:
                w.grid()
            self.cadre_outils.pack(side="right", before=self.cadre_vues)
        self.indices.activer(self.visible and vue == "indices")
        if vue == "discussion" and self.visible:
            self.lire()
            if self.v_auto.get():
                self.texte.see("end")

    def _largeur(self, _e=None) -> None:
        lg = max(self.th.px(200), self.cadre.winfo_width() - self.th.px(30))
        self.l_etat.configure(wraplength=lg)
        self.l_aide.configure(wraplength=lg)

    def _touche_journal(self, e) -> str | None:
        """Journal en lecture seule mais sélectionnable : copie (Ctrl+C), défilement et Tab permis ; une lettre tapée
        va dans le champ de saisie."""
        if e.state & 0x4 or e.keysym in ("Up", "Down", "Prior", "Next", "Home", "End", "Tab", "ISO_Left_Tab"):
            return None
        if e.char and e.char.isprintable():
            self.e_saisie.focus_set()
            self.e_saisie.insert("end", e.char)
            return "break"
        return None

    # ------------------------------------------------------------------ données
    def activer(self, visible: bool) -> None:
        self.visible = visible
        if not visible:
            self.ac_fermer()
        self.indices.activer(visible and self.vue == "indices")
        if visible:
            self.lire()
            if self.v_auto.get():
                self.texte.see("end")

    def _surveiller(self) -> None:
        try:
            if not self.cadre.winfo_exists():
                return
        except tk.TclError:
            return
        self._tour += 1
        if self._tour % TOURS_ETAT == 0:
            self.maj_etat()
        self.lire()
        self._verifier_attente()
        self.indices.surveiller()
        self.cadre.after(INTERVALLE, self._surveiller)

    def lire(self) -> int:
        """Nouveaux messages du journal du client -> affichage. Renvoie leur nombre."""
        nouveaux, remis = self.lecteur.lire()
        if remis:
            self.entrees = []
            self.redessiner()
        for d in nouveaux:
            if d.get("commande") in self.attente:
                self.attente.pop(d["commande"], None)
        if nouveaux:
            self.ajouter(nouveaux)
        return len(nouveaux)

    def maj_etat(self) -> None:
        niveau, cle, p, session = self.etat = etat_client(self.dossier)
        self.p_etat.niveau(niveau)
        self.l_etat.configure(text=th.insecables(self.tr(cle, **p)))
        self.e_saisie.changer_invite(self.tr("tx_invite" if session else "tx_invite_hors"))
        self.b_envoyer.state(["!disabled"])

    @property
    def session(self) -> str | None:
        return self.etat[3]

    # ------------------------------------------------------------------ affichage
    def _correspond(self, d: dict) -> bool:
        return not self._filtre or self._filtre in replier("".join(x for x, _g in rendu(d, self.langue)))

    def _ecrire(self, d: dict) -> None:
        x = self.texte
        if x.index("end-1c") != "1.0":
            x.insert("end", "\n")
        tt = d.get("t")
        if isinstance(tt, (int, float)):
            x.insert("end", time.strftime("%H:%M:%S ", time.localtime(tt)), ("heure",))
        debut = x.index("end-1c")
        for texte, genre in rendu(d, self.langue):
            x.insert("end", texte, (genre,))
        if self._filtre:
            self._surligner(debut)

    def _surligner(self, debut: str) -> None:
        """Surligne le texte cherché (comparaison sans accents ni casse, sur la ligne qui vient d'être écrite)."""
        x = self.texte
        ligne = x.get(debut, "end-1c")
        plie = "".join(replier(c) or " " for c in ligne).lower()
        cible = self._filtre
        i = plie.find(cible)
        while i >= 0 and cible:
            x.tag_add("trouve", f"{debut}+{i}c", f"{debut}+{i + len(cible)}c")
            i = plie.find(cible, i + len(cible))

    def ajouter(self, entrees: list[dict]) -> None:
        self.entrees.extend(entrees)
        if len(self.entrees) > AFFICHAGE_MAX + 200:
            self.entrees = self.entrees[-AFFICHAGE_MAX:]
            self.redessiner()
            return
        x = self.texte
        bas = x.yview()[1] >= 0.999
        x.configure(state="normal")
        for d in entrees:
            if self._correspond(d):
                self._ecrire(d)
        x.configure(state="disabled")
        if self.v_auto.get() and bas:
            x.see("end")
        self._maj_compte()

    def redessiner(self) -> None:
        x = self.texte
        x.configure(state="normal")
        x.delete("1.0", "end")
        for d in self.entrees:
            if self._correspond(d):
                self._ecrire(d)
        x.configure(state="disabled")
        if self.v_auto.get() or self._filtre:
            x.see("end")
        self._maj_compte()

    def _maj_compte(self) -> None:
        total = len(self.entrees)
        if self._filtre:
            n = sum(1 for d in self.entrees if self._correspond(d))
            self.l_compte.configure(text=self.tr("tx_compte_filtre", n=n, total=total))
        else:
            self.l_compte.configure(text=self.tr("tx_compte", n=total))

    def texte_affiche(self) -> str:
        return self.texte.get("1.0", "end-1c")

    def planifier(self) -> None:
        if not getattr(self, "_prevu", False):
            self._prevu = True
            self.cadre.after(150, self._filtrer)

    def _filtrer(self) -> None:
        self._prevu = False
        self._filtre = replier(self.e_recherche.valeur())
        self.redessiner()

    def _auto_change(self) -> None:
        if self.v_auto.get():
            self.texte.see("end")

    def local(self, *lignes) -> None:
        """Ligne(s) du lanceur (aide, résultats locaux, erreurs), affichées seulement ici. Une ligne = (texte, genre) ou
        liste de morceaux (texte, genre)."""
        morceaux: list[tuple[str, str]] = []
        for i, ligne in enumerate(lignes):
            parts = [ligne] if isinstance(ligne, tuple) else list(ligne)
            for k, (texte, genre) in enumerate(parts):
                morceaux.append((("\n" if i and not k else "") + texte, genre))
        self.ajouter([{"t": time.time(), "type": "local", "local": morceaux}])
        self.texte.see("end")

    def effacer(self) -> None:
        """Bouton « Effacer » / `/clear` : vide l'affichage seulement (le journal du client n'est pas touché)."""
        self.entrees = []
        self.redessiner()

    def focus_recherche(self) -> None:
        if self.vue == "indices":
            self.indices.focus_recherche()
            return
        self.e_recherche.focus_set()
        self.e_recherche.select_range(0, "end")

    def focus_saisie(self) -> None:
        self.e_saisie.focus_set()

    # ------------------------------------------------------------------ saisie
    def inserer(self, commande: str) -> None:
        self.e_saisie._cacher()
        self.e_saisie.delete(0, "end")
        self.e_saisie.insert(0, commande)
        self.e_saisie.focus_set()
        self.e_saisie.icursor("end")
        self.ac_maj()

    def ac_maj(self) -> None:
        """Après une frappe : recalcule la liste si le texte a changé. Touches sans effet sur le texte, texte remis par
        l'historique ou liste fermée par Échap : `_ac_texte` est déjà à jour, rien à faire."""
        texte = self.e_saisie.valeur()
        if texte == self._ac_texte:
            return
        self._ac_texte = texte
        if not texte.startswith("!"):                     # message ordinaire : un seul appel Tcl (`get`) par frappe
            self.ac_fermer()
            return
        if " " in texte:                                  # seules les commandes à noms lisent le fichier du client
            self._ac_catalogue = self._ac_catalogue.actualiser(self.dossier)
        liste = AC.proposer(texte, self._ac_catalogue)
        if liste is None:
            self.ac_fermer()
        else:
            self._ac_montrer(liste)

    def _ac_montrer(self, liste: AC.Liste) -> None:
        """Peu d'appels Tcl : une insertion groupée, et un `place` seulement à l'ouverture."""
        lb, self.ac = self.ac_liste, liste
        self._ac_touche = False
        lb.delete(0, "end")
        lb.insert("end", *[p.nom for p in liste.entrees])
        lb.configure(height=len(liste.entrees))
        self._ac_choisir(liste.choix)
        if not self.ac_ouverte:
            self.ac_ouverte = True
            self.ac_cadre.place(in_=self.e_saisie, x=0, y=-self.th.px(4), relwidth=1.0, anchor="sw")

    def _ac_choisir(self, i: int | None) -> None:
        self.ac_choix = i
        self.ac_liste.selection_clear(0, "end")
        if i is not None:
            self.ac_liste.selection_set(i)
            self.ac_liste.see(i)
        self._ac_note()

    def _ac_note(self) -> None:
        """Pied de la liste : les touches et le nombre de noms cachés."""
        l = self.ac
        note = self.tr("tx_ac_touches")
        if l.total > len(l.entrees):
            note = self.tr("tx_ac_plus", n=l.total - len(l.entrees)) + " · " + note
        if note != self._ac_texte_note:
            self._ac_texte_note = note
            self.ac_note.configure(text=note, wraplength=max(self.th.px(200), self.e_saisie.winfo_width()))

    def ac_fermer(self) -> None:
        """Ferme la liste ; elle ne revient que si le texte change."""
        self._ac_texte = self.e_saisie.valeur()
        if self.ac_ouverte:
            self.ac_ouverte = False
            self.ac_cadre.place_forget()

    def _ac_remplacer(self, texte: str) -> None:
        self.e_saisie._cacher()
        self.e_saisie.delete(0, "end")
        self.e_saisie.insert(0, texte)
        self.e_saisie.icursor("end")
        self.e_saisie.xview_moveto(1.0)

    def ac_completer(self, i: int | None = None) -> bool:
        """Tab, Entrée, clic : le nom complet dans le champ. Faux si la liste est fermée (Tab change de champ)."""
        if not self.ac_ouverte:
            return False
        i = i if i is not None else (self.ac_choix if self.ac_choix is not None else 0)
        self.pos_historique = None
        self._ac_remplacer(self.ac.entrees[i].complet)
        self.ac_fermer()
        self._ac_texte = None                              # après « !hint » : les noms s'ouvrent aussitôt
        if self.ac.entrees[i].complet.endswith(" "):
            self.ac_maj()
        else:
            self._ac_texte = self.e_saisie.valeur()
        return True

    def touche_entree(self) -> str:
        """Entrée : complète le nom choisi s'il n'est pas déjà tapé (nom exact sans déplacement : envoi), sinon envoie
        comme avant."""
        if self.ac_ouverte and self.ac_choix is not None:
            p = self.ac.entrees[self.ac_choix]
            if self._ac_touche or not p.exact:
                self.ac_completer()
                return "break"
        self.envoyer()
        return "break"

    def touche_fleche(self, sens: int) -> str:
        """Haut / bas : dans la liste si elle est ouverte (en boucle), sinon l'historique."""
        if not self.ac_ouverte:
            self.historique_pas(sens)
            self._ac_texte = self.e_saisie.valeur()        # un texte rappelé n'ouvre pas la liste
            return "break"
        n = len(self.ac.entrees)
        i = self.ac_choix
        self._ac_touche = True
        self._ac_choisir((0 if sens > 0 else n - 1) if i is None else (i + sens) % n)
        return "break"

    def touche_echap(self) -> str:
        """Échap : ferme la liste si elle est ouverte, sinon vide le champ."""
        if self.ac_ouverte:
            self.ac_fermer()
        else:
            self.e_saisie.delete(0, "end")
            self.ac_fermer()
        return "break"

    def _ac_clic(self, e) -> str:
        i = self.ac_liste.nearest(e.y)
        if self.ac_ouverte and 0 <= i < len(self.ac.entrees):
            self.ac_completer(i)
        return "break"                                     # jamais la classe Listbox : le focus reste dans le champ

    def _ac_survol(self, e) -> None:
        i = self.ac_liste.nearest(e.y)
        if self.ac_ouverte and i != self.ac_choix and 0 <= i < len(self.ac.entrees):
            self._ac_touche = True
            self._ac_choisir(i)

    def historique_pas(self, sens: int) -> str:
        h = self.historique
        if not h:
            return "break"
        if self.pos_historique is None:
            if sens > 0:
                return "break"
            self.brouillon = self.e_saisie.valeur()
            self.pos_historique = len(h)
        pos = self.pos_historique + sens
        if pos < 0:
            pos = 0
        self.e_saisie._cacher()
        self.e_saisie.delete(0, "end")
        if pos >= len(h):
            self.pos_historique = None
            self.e_saisie.insert(0, self.brouillon)
        else:
            self.pos_historique = pos
            self.e_saisie.insert(0, h[pos])
        self.e_saisie.icursor("end")
        return "break"

    def envoyer(self) -> bool:
        """Entrée / « Envoyer » : commande locale « /… », sinon message ou commande « !… » transmis au client connecté.
        True si quelque chose a été fait (champ vidé)."""
        self.ac_fermer()
        texte = self.e_saisie.valeur().strip()
        if not texte:
            return False
        texte = texte[:ch.TEXTE_MAX]
        if not self.historique or self.historique[-1] != texte:
            self.historique = (self.historique + [texte])[-HISTORIQUE_MAX:]
        self.pos_historique = None
        if texte.startswith("/"):
            self.e_saisie.delete(0, "end")
            self.commande_locale(texte)
            return True
        self.maj_etat()
        session = self.session
        if not session:
            self.local((self.tr("tx_l_hors_ligne"), "erreur"))
            return False                                   # texte gardé dans le champ
        if texte.split()[0].lower() == "!release" and not self.confirmer(self.tr("tx_l_release_titre"),
                                                                          self.tr("tx_l_release")):
            self.local((self.tr("tx_l_release_annule"), "local"))
            return False
        try:
            c = ch.deposer_commande(self.dossier, texte, session)
        except (OSError, ValueError) as e:
            self.local((self.tr("tx_l_erreur_ecriture", erreur=e), "erreur"))
            return False
        self.attente[c["id"]] = (texte, time.monotonic() + ATTENTE_CLIENT)
        self.e_saisie.delete(0, "end")
        return True

    def _verifier_attente(self) -> None:
        maintenant = time.monotonic()
        for ident, (texte, echeance) in list(self.attente.items()):
            if maintenant > echeance:
                self.attente.pop(ident, None)
                self.local((self.tr("tx_l_sans_reponse", texte=texte), "erreur"))

    def commande_locale(self, texte: str) -> None:
        cmd = texte.split()[0].lower()
        if cmd in ("/help", "/aide", "/?"):
            self.local(*[(ligne, "local") for ligne in self.tr("tx_l_aide").split("\n")])
        elif cmd in ("/clear", "/effacer", "/cls"):
            self.effacer()
            self.local((self.tr("tx_l_efface"), "local"))
        elif cmd in ("/received", "/recus", "/reçus"):
            self.local(*self._recus())
        elif cmd in ("/missing", "/manquants"):
            self.local(*self._manquants())
        else:
            self.local((self.tr("tx_l_inconnue", cmd=cmd), "erreur"))

    def _recus(self) -> list[tuple[str, str]]:
        """Objets reçus d'après `checks.json` (écrit par le client) ; couleurs selon les drapeaux."""
        d = self._checks()
        recus = [r for r in (d or {}).get("recus", []) if isinstance(r, dict)]
        if not recus:
            return [(self.tr("tx_l_recus_aucun"), "local")]
        out: list = [(self.tr("tx_l_recus_titre", n=len(recus)), "local")]
        for r in recus:
            de = self.tr("tx_l_recus_moi") if r.get("soi") else str(r.get("expediteur", "?"))
            lieu = self.tr("tx_l_recus_lieu", lieu=r["location"]) if r.get("location") else ""
            out.append([(f"  {r.get('n', '?')}. ", "texte"),
                        (str(r.get("objet", "?")), ch.genre_objet(r.get("flags", 0))),
                        (self.tr("tx_l_recus_de"), "texte"), (de, "moi" if r.get("soi") else "joueur"),
                        (lieu, "lieu")])
        return out

    def _manquants(self) -> list[tuple[str, str]]:
        """Locations pas encore faites (noms seulement, d'après `checks.json`) ; jamais leur contenu."""
        d = self._checks()
        if not d:
            return [(self.tr("tx_l_manquants_aucun"), "local")]
        try:
            from . import checks as CK
            m = CK.charger(self.dossier, self.langue)
            noms = [c.nom for c in m.checks if c.etat != "fait"]
        except Exception:                                  # noqa: BLE001 - logique absente : noms bruts
            noms = []
        if not noms:
            return [(self.tr("tx_l_manquants_aucun"), "local")]
        return [(self.tr("tx_l_manquants_titre", n=len(noms)), "local")] + [("  " + n, "lieu") for n in noms]

    def _checks(self) -> dict | None:
        try:
            d = json.loads((self.dossier / "checks.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return d if isinstance(d, dict) else None
