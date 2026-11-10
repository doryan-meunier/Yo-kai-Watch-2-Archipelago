"""Sous-onglet « Carte » de l'onglet « Checks » (tracker sur cartes, façon PopTracker) : vue tkinter seulement. Données,
regroupement et couleurs : `carte_checks.py` ; checks, états, filtres et sélection : ceux de l'onglet (`vue_checks.py`,
`checks.py`), partagés avec la liste.

Disposition (spécification de l'humain, d'après son ancien pack PopTracker) :
- en haut, la barre des RÉGIONS (= filtre « Zone » de la liste : changer l'un change l'autre), puis le choix de la
  carte de la région (grande carte d'abord) et le zoom ; on peut ÉCRIRE dans la liste des cartes pour la filtrer
  (nom qui contient le texte, sans casse ni accents, dans la langue du lanceur : `carte_checks.filtrer_noms`) ;
  flèches haut / bas, Entrée ou clic : choisir ; Échap, clic ailleurs ou perte du focus : nom de la carte courante
  rendu ; la carte ne change que sur un choix (aucun redessin pendant la frappe) ;
- à gauche, la grille des OBJETS de progression (icônes lues dans la ROM du joueur, grisées tant qu'ils ne sont pas
  reçus, compteur pour les objets multiples ; Vélo, Rang de montre (lettre du rang) et chapitres (N/10) avec l'icône
  d'un objet du jeu qui les représente, `cartes.ICONES_SANS_HACHAGE` ; case dessinée si l'icône manque), et en
  bas l'encart d'OBJECTIF (chapitres N/10, un carré par check « chapitre N terminé ») ;
- au centre, la minicarte avec des marqueurs CARRÉS : vert accessible, rouge pas accessible, gris foncé fait, orange
  groupe en partie accessible, liseré or = indice (hint), contour pointillé = position approximative ; un carré
  regroupe les checks proches (nombre inscrit) ; survol : infobulle (nom, état, contenu SEULEMENT si fait ou indiqué) ;
  clic : sélection partagée avec la liste et détail sous la vue ; glisser : déplacer, molette : défiler (Ctrl : zoom) ;
- à droite, les COMPTEURS (faites, accessibles, restantes) de la région, la légende, et les checks de la région sans
  position (« position inconnue » sur la carte affichée, « sans lieu »).
BOUTIQUES (`cartes_local.json` au format 5, `archipelago_tracker_cartes.md` §11) : une MAISON par boutique, posée sur
son vendeur, de la couleur de l'état global de ses articles-checks, avec le nombre d'articles restants ; survol : une
ligne par article (état ; contenu seulement s'il est fait ou indiqué) ; clic : panneau de ses articles dessiné sur la
carte (clic sur une ligne : l'article est choisi) ; petite maison blanche : porte du bâtiment sur la carte d'où l'on
entre (clic : ouvre la carte de l'intérieur). Logique : `carte_checks.marqueurs_boutiques`.
YO-KAI ÉPINGLÉ (onglet « Yo-kai », un seul à la fois, mémorisé) : ses points d'apparition exacts sur la carte affichée,
en violet : LOSANGE = point de loupe, TRIANGLE = point d'apparition d'un errant (pâle : pas accessible maintenant) ;
survol : méthode, décor du point, niveaux, conditions ; les cartes qui en portent sont marquées « ◆ » dans la liste des
cartes et listées à droite (clic : ouvrir la carte), avec les lieux non dessinés (portails mystères, position
inconnue). Logique : `carte_checks.epingle`.
INVITATIONS (graine qui en a : `ModeleChecks.invitations`) : rubrique repliable sous les objets, une ligne compacte
par invitation (petite enveloppe au logo du mod, en couleur si elle est reçue, grise sinon ; nom du Yo-kai ; pour une
invitation reçue, l'état court de l'invité que le lanceur connaît déjà : « ch. 103 », « file 2 », « ami ») ; survol :
phrase complète ; clic sur le titre : replier / déplier. Une seule liaison d'évènements pour toute la rubrique.
SUIVI DU JEU (case « Suivre le jeu », cochée par défaut, mémorisée) : la carte affichée devient celle où le joueur se
trouve dans le jeu à chaque changement de carte (lieu publié par le jeu, recopié par le client dans `lieu.json`) ; une
carte choisie à la main met le suivi en pause jusqu'au prochain changement de carte en jeu ; un rond cyan « vous êtes
ici » marque la position du joueur quand la carte affichée est celle du jeu. Logique (sans affichage) :
`carte_checks.Suivi`. Le fichier n'est lu que tant que le sous-onglet est AFFICHÉ (rien pour un onglet caché).
Sans cartes générées : message, choix de la ROM si elle manque, génération en tâche de fond avec progression.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

from . import carte_checks as CC
from . import checks as CK
from . import presentation as P
from . import theme as th
from .vue_que_faire import QueFaire

if TYPE_CHECKING:                                   # pragma: no cover
    from .vue_checks import OngletChecks

COULEURS = {"fait": "#4A4A4A", "accessible": "#1FB24A", "partiel": "#F28C00", "non": th.ROUGE}
COULEUR_INDICE = th.OR
COULEUR_SELECTION = th.CYAN
FOND_CARTE = "#2B2326"
FACTEURS = ((1, 3), (2, 5), (1, 2), (2, 3), (1, 1), (3, 2), (2, 1), (3, 1))   # zoom : (agrandir, réduire) de PhotoImage
COLONNES_OBJETS = 4
LIGNES_LISTE_CARTES = 12                             # lignes visibles de la liste filtrée des cartes
PAS_ICONES = 6                                       # icônes décodées par tour de boucle (`VueCarte.prechauffer`)
DELAI_ICONES = 40                                    # ms entre deux tours
INFOBULLE_MAX = 10                                   # lignes d'une infobulle de groupe
INFOBULLE_BOUTIQUE_MAX = 30                          # articles listés dans l'infobulle d'une boutique
PANNEAU_CONTENU_MAX = 34                             # caractères du contenu d'un article dans le panneau d'une boutique
PERIODE_SUIVI = 500                                  # ms entre deux lectures du lieu du joueur (sous-onglet affiché)
COULEUR_JOUEUR = th.CYAN                             # rond « vous êtes ici »
TAILLES_ENVELOPPE = (16, 20, 24, 32)                 # `ressources/invitation_<N>.png` (outils/preparer_enveloppes.py)
INVITATION_NOM_MAX = 15                              # caractères du nom d'un Yo-kai dans la rubrique « Invitations »
COULEURS_INVITE = {"attente": th.TEXTE_DOUX, "file": "#A35A00", "present": th.CYAN_TEXTE, "ami": "#1D7A3C"}
COULEUR_YOKAI = "#8E3FD1"                            # Yo-kai épinglé : losange (loupe), triangle (errant)
COULEUR_YOKAI_PALE = "#E9D7FA"                       # point pas accessible maintenant
# petit rond sur le marqueur d'un point qui ne donne le Yo-kai qu'à un moment (base 13, §19) : (fond, contour)
COULEUR_ABSENT, COULEUR_ABSENT_BORD = "#E4E4E4", "#6B6B6B"    # vendeur absent maintenant (maison vide)
COULEURS_MOMENT = {"jour": ("#FFC933", "#7A5200"), "nuit": ("#1B2A63", th.BLANC)}
TEXTES_CARTE_MOMENT = {"jour": "cc_yk_carte_jour", "nuit": "cc_yk_carte_nuit"}   # ligne d'une carte de l'épinglé


class Infobulle:
    """Petite fenêtre sans bordure près du pointeur."""

    def __init__(self, parent: tk.Misc, theme: th.Theme):
        self.parent, self.th = parent, theme
        self.fen: tk.Toplevel | None = None
        self.texte = ""

    def montrer(self, texte: str, x: int, y: int) -> None:
        self.cacher()
        self.texte = texte
        if not texte:
            return
        f = self.fen = tk.Toplevel(self.parent)
        f.wm_overrideredirect(True)
        try:
            f.attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(f, text=texte, font=self.th["petit"], bg="#FFFBEA", fg=th.TEXTE, justify="left", anchor="w",
                 padx=self.th.px(6), pady=self.th.px(3), relief="solid", borderwidth=1).pack()
        f.wm_geometry(f"+{x + self.th.px(14)}+{y + self.th.px(12)}")

    def cacher(self) -> None:
        if self.fen is not None:
            try:
                self.fen.destroy()
            except tk.TclError:
                pass
        self.fen = None
        self.texte = ""


class VueCarte:
    """Contenu du sous-onglet (cadre posé par `OngletChecks` à la place de la liste)."""

    def __init__(self, parent: tk.Misc, onglet: "OngletChecks"):
        self.o, self.th = onglet, onglet.th
        self.don: CC.DonneesCartes | None = None
        self._sig = object()
        self.carte: str | None = None                # carte affichée
        self.facteur = FACTEURS.index((1, 1))        # index dans FACTEURS
        self._ox = self._oy = 0.0                    # décalage de l'image (centrée si plus petite que la vue)
        self.ajuster = True                          # zoom automatique tant que le joueur ne zoome pas
        self.marqueurs: list[CC.Marqueur] = []
        self._image_base: tk.PhotoImage | None = None
        self._image: tk.PhotoImage | None = None
        self._image_cle = None
        self._icones: dict[str, tk.PhotoImage] = {}
        self._cycle: dict[int, int] = {}             # marqueur -> rang du check choisi au prochain clic
        self._gen_vu = -1
        self._rom_demandee = False
        self._chauffe = None                         # signature des cartes dont les icônes sont (pré)chargées
        self._a_chauffer: list[tuple[Path, bool]] = []
        # suivi du jeu : case « Suivre le jeu » (mémorisée par l'onglet), lieu du joueur lu dans lieu.json
        self.suivi = CC.Suivi(getattr(onglet, "suivre_initial", True))
        self.v_suivre = tk.BooleanVar(parent, value=self.suivi.actif)
        self.lieu: CC.Lieu | None = None
        self._lieu_brut: dict | None = None
        self._sig_lieu = object()
        self._tache_suivi = None                     # boucle `after` du suivi (None : arrêtée, sous-onglet caché)
        self._sel_montree: int | None = None         # dernière sélection dont la carte a été ouverte
        # Yo-kai épinglé (onglet « Yo-kai ») : points par carte, recalculés quand lui, la base ou les cartes changent
        self._ep: CC.Epingle | None = None
        self._ep_sig = object()
        self._ep_montre = getattr(getattr(onglet, "tracker", None), "epingle", "") or ""
        self.points_yokai: list[CC.PointYokai] = []
        self.panneau: tuple[str, tuple[str, ...]] | None = None    # (carte, codes) de la boutique au panneau ouvert
        self._lignes_panneau: dict[int, int] = {}                  # élément du canevas -> check de la ligne
        self._items_yokai: dict[int, int] = {}
        self.cartes: list[tuple[str, int, int]] = []
        self.info = Infobulle(parent, self.th)
        self.construire(parent)

    def tr(self, cle: str, **p) -> str:
        return self.o.tr(cle, **p)

    # ------------------------------------------------------------------ construction
    def construire(self, parent: tk.Misc) -> None:
        T, px = self.th, self.th.px
        f = self.cadre = tk.Frame(parent, bg=th.BLANC)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(2, weight=1)
        # barre des régions (disposition en lignes, refaite à chaque changement de largeur)
        self.barre = tk.Frame(f, bg=th.BLANC, height=px(26))
        self.barre.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.barre.bind("<Configure>", lambda _e: self._disposer_regions(), add="+")
        self.b_regions: list[tuple[object, th.Pilule]] = []
        # outils : carte de la région, zoom
        outils = tk.Frame(f, bg=th.BLANC)
        outils.grid(row=1, column=1, sticky="ew", pady=(px(4), px(4)))
        outils.columnconfigure(1, weight=1)
        tk.Label(outils, text=self.tr("cc_carte"), font=T["bouton_petit"], bg=th.BLANC, fg=th.TEXTE).grid(
            row=0, column=0, padx=(0, px(6)))
        # liste des cartes : on peut y ÉCRIRE pour filtrer (sans casse ni accents) ; flèches / Entrée / clic : choisir,
        # Échap ou perte du focus : nom de la carte courante. La carte ne change que sur un choix explicite.
        self.cb_carte = ttk.Combobox(outils, style="Yokai.TCombobox", font=T["texte"], width=30)
        self.cb_carte.grid(row=0, column=1, sticky="ew")
        self.cb_carte.bind("<<ComboboxSelected>>", lambda _e: self._choisir_carte_liste())
        self._construire_recherche_carte(f)
        self.b_zoom = []
        for i, (texte, cmd) in enumerate((("−", lambda: self.zoomer(-1)), ("+", lambda: self.zoomer(1)),
                                          (self.tr("cc_ajuster"), self.ajuster_zoom))):
            b = th.Pilule(outils, T, texte, cmd, police="bouton_petit", padx=8 if i < 2 else 10, pady=2)
            b.grid(row=0, column=2 + i, padx=(px(6) if i == 0 else px(3), 0))
            self.b_zoom.append(b)
        # suivi du jeu : case mémorisée, « (en pause) » après un choix à la main
        self.b_suivre = th.Bascule(outils, T, self.tr("cc_suivre"), self.v_suivre, self._bascule_suivi)
        self.b_suivre.grid(row=0, column=5, padx=(px(10), 0))
        self.b_suivre.bind("<Enter>", lambda e: self.info.montrer(self.tr("cc_suivre_aide"), e.x_root, e.y_root),
                           add="+")
        self.b_suivre.bind("<Leave>", lambda _e: self.info.cacher(), add="+")
        self.l_suivi = tk.Label(outils, text="", font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX)
        self.l_suivi.grid(row=0, column=6, padx=(px(2), 0))
        # gauche : objets et objectif
        gauche = tk.Frame(f, bg=th.BLANC)
        gauche.grid(row=1, column=0, rowspan=2, sticky="nsw", padx=(0, px(8)))
        gauche.rowconfigure(1, weight=1)
        tk.Label(gauche, text=self.tr("cc_objets"), font=T["bouton_petit"], bg=th.BLANC, fg=th.TEXTE,
                 anchor="w").grid(row=0, column=0, sticky="ew")
        self.cellule = px(38)
        # colonne défilante (molette, barre montrée seulement si tout ne tient pas) : objets de progression, chapitres,
        # puis section « Objets d'évènement » quand la graine en a
        self.c_objets = tk.Canvas(gauche, bg=th.BLANC, highlightthickness=0, width=self.cellule * COLONNES_OBJETS,
                                  height=self.cellule * 4, yscrollincrement=1)
        self.c_objets.grid(row=1, column=0, sticky="nsw")
        self.defil_objets = ttk.Scrollbar(gauche, orient="vertical", command=self.c_objets.yview,
                                          style="Yokai.Vertical.TScrollbar")
        self.c_objets.configure(yscrollcommand=self._defil_objets)
        self.c_objets.bind("<MouseWheel>", self._molette_objets, add="+")
        self.c_objets.bind("<Configure>", lambda _e: self._defil_objets(*self.c_objets.yview()), add="+")
        self.c_objets.bind("<Leave>", lambda _e: self.info.cacher(), add="+")
        self._hauteur_objets = 0
        # rubrique « Invitations » : UNE liaison pour toutes ses lignes (ligne trouvée d'après l'ordonnée)
        self.invitations_repliees = False
        self._zone_inv: tuple[int, int, int, int] | None = None    # (y du titre, y de la liste, pas, lignes)
        self._inv_survol = None                      # ligne survolée (rang, "titre" ou None)
        self._inv_texte = ""                         # texte de l'infobulle que la rubrique a montrée
        self._enveloppes: dict[bool, tk.PhotoImage | None] = {}
        self.c_objets.bind("<Motion>", self._survol_invitations, add="+")
        self.c_objets.bind("<Leave>", lambda _e: setattr(self, "_inv_survol", None), add="+")
        self.c_objets.bind("<ButtonRelease-1>", self._clic_invitations, add="+")
        # V3, lot 20 : rubrique « Pièces spéciales » : mêmes principes (une liaison pour toute la grille)
        self._zone_pieces: tuple[int, int] | None = None  # (y du titre, y de la grille)
        self._grille_pieces: tuple[int, int] | None = None          # (y de la grille d'icônes, nombre de cases) ; lot 21
        self._cases_pieces: list[tuple] = []
        self._pc_survol = None
        self._pc_texte = ""
        self.c_objets.bind("<Motion>", self._survol_pieces, add="+")
        self.c_objets.bind("<Leave>", lambda _e: setattr(self, "_pc_survol", None), add="+")
        self.c_objectif = tk.Canvas(gauche, bg=th.BLANC, highlightthickness=0, width=self.cellule * COLONNES_OBJETS,
                                    height=px(92))
        self.c_objectif.grid(row=2, column=0, sticky="sw", pady=(px(6), 0))
        # position du joueur copiée dans le presse-papiers (« carte:x,z », pour donner un lieu sans rien calculer) :
        # lue dans lieu.json au clic seulement, réponse dans l'infobulle (aucune tâche périodique en plus) ;
        # sous l'objectif : la barre d'outils n'a plus de place (la liste des cartes y serait écrasée)
        self.b_copier = th.Pilule(gauche, T, self.tr("cc_copier"), self.copier_position, police="bouton_petit",
                                  padx=10, pady=2)
        self.b_copier.grid(row=3, column=0, sticky="w", pady=(px(6), 0))
        self.b_copier.bind("<Enter>", lambda e: self.info.montrer(self.tr("cc_copier_aide"), e.x_root, e.y_root),
                           add="+")
        self.b_copier.bind("<Leave>", lambda _e: self.info.cacher(), add="+")
        self.copie: str | None = None                # dernière ligne copiée (tests, diagnostic)
        # centre : carte
        centre = self.centre = tk.Frame(f, bg=th.NOIR, padx=px(2), pady=px(2))
        centre.grid(row=2, column=1, sticky="nsew")
        centre.columnconfigure(0, weight=1)
        centre.rowconfigure(0, weight=1)
        self.canvas = c = tk.Canvas(centre, bg=FOND_CARTE, highlightthickness=0, width=px(420), height=px(260),
                                    xscrollincrement=1, yscrollincrement=1)
        c.grid(row=0, column=0, sticky="nsew")
        self.defil_v = ttk.Scrollbar(centre, orient="vertical", command=c.yview, style="Yokai.Vertical.TScrollbar")
        self.defil_h = ttk.Scrollbar(centre, orient="horizontal", command=c.xview)
        self.defil_v.grid(row=0, column=1, sticky="ns")
        self.defil_h.grid(row=1, column=0, sticky="ew")
        c.configure(yscrollcommand=self.defil_v.set, xscrollcommand=self.defil_h.set)
        c.bind("<ButtonPress-1>", self._appui, add="+")
        c.bind("<B1-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1), add="+")
        c.bind("<MouseWheel>", self._molette, add="+")
        c.bind("<Configure>", lambda _e: self._redimensionne(), add="+")
        c.bind("<Leave>", lambda _e: self.info.cacher(), add="+")
        c.tag_bind("yokai", "<Enter>", self._survol_yokai)       # un seul lien pour tous les points épinglés
        c.tag_bind("yokai", "<Leave>", lambda _e: self.info.cacher())
        c.tag_bind("ligne", "<Enter>", self._survol_panneau)     # lignes du panneau d'une boutique
        c.tag_bind("ligne", "<Leave>", lambda _e: self.info.cacher())
        c.tag_bind("ligne", "<ButtonRelease-1>", self._clic_panneau)
        # message (sans cartes) posé sur le canevas
        self.cadre_msg = tk.Frame(centre, bg=th.BLANC, padx=px(16), pady=px(12))
        self.l_msg = tk.Label(self.cadre_msg, text="", font=T["texte"], bg=th.BLANC, fg=th.TEXTE, justify="left",
                              wraplength=px(380))
        self.l_msg.pack(anchor="w")
        self.barre_gen = ttk.Progressbar(self.cadre_msg, mode="determinate", maximum=100, length=px(320))
        self.b_msg = th.Pilule(self.cadre_msg, T, "", self._action_msg, police="bouton_petit", padx=12, pady=3,
                               genre="or")
        self._action = None
        # droite : compteurs, légende, checks sans position
        droite = tk.Frame(f, bg=th.BLANC)
        droite.grid(row=1, column=2, rowspan=2, sticky="nse", padx=(px(8), 0))
        droite.rowconfigure(3, weight=1)
        self.l_compteurs = {}
        cpt = tk.Frame(droite, bg=th.BLANC)
        cpt.grid(row=0, column=0, sticky="ew")
        for i, (cle, couleur) in enumerate((("faits", COULEURS["fait"]), ("accessibles", COULEURS["accessible"]),
                                            ("restants", th.ROUGE))):
            n = tk.Label(cpt, text="0", font=T["titre"], bg=th.BLANC, fg=couleur, anchor="e", width=4)
            n.grid(row=i, column=0, sticky="e")
            tk.Label(cpt, text=self.tr(f"cc_{cle}"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE, anchor="w",
                     justify="left").grid(row=i, column=1, sticky="w", padx=(px(4), 0))
            self.l_compteurs[cle] = n
            n.couleur = couleur                              # grisé tant qu'il n'y a pas de checks de la partie
        self.c_legende = tk.Canvas(droite, bg=th.BLANC, highlightthickness=0, width=px(190), height=px(212))
        self.c_legende.grid(row=1, column=0, sticky="w", pady=(px(4), px(4)))
        tk.Label(droite, text=self.tr("cc_sans_position"), font=T["bouton_petit"], bg=th.BLANC, fg=th.TEXTE,
                 anchor="w").grid(row=2, column=0, sticky="ew")
        cadre_liste = tk.Frame(droite, bg=th.NOIR, padx=px(1), pady=px(1))
        cadre_liste.grid(row=3, column=0, sticky="nsew")
        cadre_liste.rowconfigure(0, weight=1)
        cadre_liste.columnconfigure(0, weight=1)
        self.liste = ttk.Treeview(cadre_liste, show="tree", style="Yokai.Treeview", height=3, selectmode="browse")
        self.liste.column("#0", width=px(170), minwidth=px(120), stretch=True)
        self.liste.grid(row=0, column=0, sticky="nsew")
        self.liste.tag_configure("titre", font=T["bouton_petit"], background=th.OR_CLAIR)
        for e, coul in (("fait", "#1D7A3C"), ("accessible", th.CYAN_TEXTE), ("plus_tard", "#A35A00"),
                        ("bloque", th.TEXTE_DOUX), ("inconnu", th.INACTIF_TEXTE)):
            self.liste.tag_configure(e, foreground=coul)
        self.liste.bind("<<TreeviewSelect>>", lambda _e: self._choisir_liste(), add="+")
        self.liste.tag_configure("yokai", font=T["bouton_petit"], background=COULEUR_YOKAI_PALE)
        self.b_desepingler = th.Pilule(droite, T, self.tr("yk_desepingler"), self._desepingler, police="bouton_petit",
                                       padx=10, pady=1)
        self._dessiner_legende()
        # bouton « Que faire maintenant ? » (sous « Copier ma position ») : son panneau prend la place de la colonne
        # de droite tant qu'il est ouvert (vue_que_faire.py, calcul : que_faire.py)
        self.que_faire = QueFaire(self, gauche, droite, f)

    # ------------------------------------------------------------------ données
    def recharger(self, force: bool = False) -> bool:
        sig = CC.signature(self.o.dossier)
        if not force and sig == self._sig:
            return False
        self._sig = sig
        self.don = CC.charger(self.o.dossier) if sig is not None else None
        self._image_base = self._image = None
        self._image_cle = None
        self._icones = {}
        return True

    def surveiller(self) -> None:
        """Appelée par le cycle de l'onglet : fin de génération, fichier changé, ROM choisie entre-temps."""
        g = self.o.generation
        change = False
        if g.numero != self._gen_vu and not g.en_cours:
            self._gen_vu = g.numero
            change = self.recharger(force=True)
        elif self.recharger():
            change = True
        if self.o.visible and self.o.vue == "carte":
            if self.don is None and self._rom_demandee and self.o.rom_valide():
                self._rom_demandee = False
                self.o.generer_cartes()
            if change or g.en_cours or self._signature_epingle() != self._ep_sig or self._progression_changee():
                self.remplir()
        self.prechauffer()

    def progression(self) -> CC.TK.Progression | None:
        """Progression de la sauvegarde liée (présence des vendeurs) ; relue quand `progression.json` change."""
        sig = CC.signature_progression(self.o.dossier)
        if sig != getattr(self, "_prog_sig", ()):
            self._prog_sig = sig
            self._prog = CC.lire_progression(self.o.dossier) if sig is not None else None
        return getattr(self, "_prog", None)

    def _progression_changee(self) -> bool:
        """Vrai si la progression lue a changé depuis le dernier dessin ET qu'un vendeur de la carte en dépend."""
        avant = getattr(self, "_prog", None)
        apres = self.progression()
        cle = lambda p: None if p is None else (p.phase, p.rang, p.apres_jeu)   # noqa: E731
        return cle(avant) != cle(apres) and any(mq.presences for mq in self.marqueurs)

    # ------------------------------------------------------------------ Yo-kai épinglé
    def _signature_epingle(self) -> tuple:
        tr = self.o.tracker
        if tr is None or not tr.epingle:                     # rien d'épinglé : rien à recalculer ni à redessiner
            return (None,)
        return (tr.epingle, tr.signature, tr.modele.format_base, self._sig)

    def epingle(self) -> CC.Epingle | None:
        """Points du Yo-kai épinglé par carte (None : aucun épinglé) ; recalculés seulement quand le Yo-kai épinglé,
        les fichiers du tracker ou les cartes changent."""
        tr = self.o.tracker
        if tr is not None and tr.epingle and tr.signature is None:   # onglet « Yo-kai » jamais ouvert : fichiers lus
            tr.recharger()
        sig = self._signature_epingle()
        if sig != self._ep_sig:
            self._ep_sig = sig
            self._ep = CC.epingle(tr.yokai_epingle(), self.don) if len(sig) > 1 else None
        return self._ep

    def nom_epingle(self) -> str:
        tr, ep = self.o.tracker, self._ep
        if tr is None or ep is None:
            return ""
        return self.tr("yk_masque") if tr.masque_nom(ep.yokai, tr.filtre()) else ep.yokai.nom(self.o.langue)

    def _desepingler(self) -> None:
        if self.o.tracker is not None:
            self.o.tracker.epingler(None)

    def _vers_carte_epingle(self, ep: CC.Epingle | None) -> None:
        """Un NOUVEAU Yo-kai vient d'être épinglé : si la carte affichée n'a aucun de ses points, la carte du jeu si
        elle en a, sinon sa première carte, est ouverte (choix à la main : le suivi du jeu se met en pause)."""
        cle = getattr(self.o.tracker, "epingle", "") or ""
        if cle == self._ep_montre:
            return
        self._ep_montre = cle
        if ep is None or not ep.cartes or self.carte in ep.cartes:
            return
        jeu = self.suivi.cible_jeu
        self.carte = jeu if jeu in ep.cartes else CC.cartes_epingle(ep, self.don)[0]
        self.ajuster = True
        self.suivi.choix_manuel(self.carte)
        self._maj_etat_suivi()

    def _icones_voulues(self) -> list[tuple[Path, bool]]:
        """(fichier, grisée) des icônes que la colonne d'objets affiche pour le modèle courant."""
        m = self.o.modele
        voulues = [(o.icone, o.recus <= 0) for o in CC.objets_progression(m, self.don) + CC.objets_evenement(m, self.don)
                   if o.icone]
        chap = CC.icone_chapitres(self.don)
        if chap:
            voulues.append((chap, CC.chapitres(m)[0] <= 0))
        return voulues

    def prechauffer(self) -> None:
        """Décode les icônes de la colonne d'objets par petits lots (`PAS_ICONES` par tour de boucle), sous-onglet
        encore caché : la première ouverture de « Carte » n'a plus ~60 PNG à décoder d'un coup dans le fil de la
        fenêtre. Sans effet si elles le sont déjà ; une icône demandée avant son tour est décodée à la demande."""
        if self.don is None or self._chauffe == self._sig:
            return
        self._chauffe = self._sig
        en_cours = bool(self._a_chauffer)
        self._a_chauffer = self._icones_voulues()
        if not en_cours:
            self._pas_chauffe()

    def _pas_chauffe(self) -> None:
        faits = 0
        while self._a_chauffer and faits < PAS_ICONES:
            chemin, gris = self._a_chauffer.pop(0)
            avant = len(self._icones)
            self._icone(chemin, gris)
            faits += len(self._icones) > avant
        if self._a_chauffer:
            try:
                self.c_objets.after(DELAI_ICONES, self._pas_chauffe)
            except tk.TclError:
                self._a_chauffer = []

    # ------------------------------------------------------------------ remplissage
    def remplir(self) -> None:
        self.info.cacher()
        self._maj_regions()
        self._dessiner_objets()
        self._dessiner_objectif()
        self._maj_compteurs()
        if self.don is None or not self.don.cartes:
            self._montrer_message()
            self._maj_liste([], [])
            self._vider_liste_cartes()
            return
        m, f = self.o.modele, self.o.filtre()
        ep = self.epingle()
        if m.sans_donnees and not (ep and ep.cartes):        # cartes prêtes, mais pas encore de checks de la partie
            self._montrer_message(self.tr("ck_non_connecte_vide"))
            self._maj_liste([], [])
            self.cartes = []
            self._vider_liste_cartes()
            self.marqueurs = []
            return
        self.cadre_msg.place_forget()
        self.cartes = CC.cartes_de_zone(m, self.don, f) if not m.sans_donnees else []
        cles = [k for k, _g, _t in self.cartes]
        # cartes du Yo-kai épinglé : toujours dans la liste (quels que soient la région et les filtres), marquées
        for k in CC.cartes_epingle(ep, self.don):
            if k not in cles:
                self.cartes.append((k, 0, 0))
                cles.append(k)
        self._vers_carte_epingle(ep)
        # carte SUIVIE (celle du jeu) : gardée dans la liste même si les filtres n'y laissent aucun check
        suivie = self.suivi.cible_jeu if self.suivi.actif and not self.suivi.pause else None
        if suivie and suivie == self.carte and suivie in self.don.cartes and suivie not in cles:
            self.cartes.append((suivie, 0, 0))
            cles.append(suivie)
        noms = self._noms_cartes()
        marque = self.tr("cc_yk_marque")
        self._libelles = [f"{marque if ep and k in ep.cartes else ''}{noms.get(k, k)}  ({g}/{t})"
                          for k, g, t in self.cartes]
        self._noms_recherche = [noms.get(k, k) for k, _g, _t in self.cartes]
        if self.carte not in cles:
            self.carte = cles[0] if cles else None
            self.ajuster = True
        self._maj_liste_cartes()
        self._dessiner_carte()
        sur, sans = CC.sans_position(m, self.don, f, self.carte)
        self._maj_liste(sur, sans)

    def _noms_cartes(self) -> dict[str, str]:
        """Noms des cartes dans la langue du joueur (`noms_local.json`), identifiant ajouté aux noms en double."""
        from . import noms_locaux
        d = noms_locaux.charger(self.o.dossier) or {}
        lg = "engb" if self.o.langue == "en" else "fr"
        noms = ((d.get("langues") or {}).get(lg) or {}).get("cartes") or {}
        vus: dict[str, int] = {}
        for k, _g, _t in getattr(self, "cartes", []):
            vus[noms.get(k, k)] = vus.get(noms.get(k, k), 0) + 1
        return {k: (noms.get(k, k) if vus.get(noms.get(k, k), 0) <= 1 or k not in noms else f"{noms[k]} ({k})")
                for k, _g, _t in getattr(self, "cartes", [])}

    def _montrer_message(self, texte_seul: str | None = None) -> None:
        """Message au centre du canevas : génération des cartes (barre, bouton), ou `texte_seul` (sans action)."""
        g, px = self.o.generation, self.th.px
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, 1, 1))
        self.barre_gen.pack_forget()
        self.b_msg.pack_forget()
        self._action = None
        if texte_seul:
            texte = th.insecables(texte_seul)
        elif g.en_cours:
            texte = self.tr("cc_generation", pc=int(g.fraction * 100), etape=self.tr(f"cc_etape_{g.etape}")
                            if g.etape in ("lecture", "positions", "images", "icones", "ecriture") else g.etape)
            self.barre_gen.configure(value=int(g.fraction * 100))
            self.barre_gen.pack(anchor="w", pady=(px(8), 0))
        elif not self.o.rom_valide():
            texte = self.tr("cc_sans_rom")
            self._action = "rom"
        elif g.erreur:
            texte = self.tr("cc_erreur", detail=g.erreur)
            self._action = "generer"
        else:
            texte = self.tr("cc_absentes")
            self._action = "generer"
        if self._action:
            self._maj_bouton_msg(self.tr("cc_choisir_rom") if self._action == "rom" else self.tr("cc_generer"))
            self.b_msg.pack(anchor="w", pady=(px(10), 0))
        self.l_msg.configure(text=texte)
        self.cadre_msg.place(relx=0.5, rely=0.45, anchor="center")

    def _maj_bouton_msg(self, texte: str) -> None:
        if self.b_msg.texte != texte:
            parent = self.b_msg.master
            self.b_msg.destroy()
            self.b_msg = th.Pilule(parent, self.th, texte, self._action_msg, police="bouton_petit", padx=12, pady=3,
                                   genre="or")

    def _action_msg(self) -> None:
        if self._action == "rom":
            self._rom_demandee = True
            self.o.choisir_rom()
        elif self._action == "generer":            # demandé par le joueur (cartes absentes ou erreur)
            self.o.generer_cartes(force=True)
            self.remplir()

    # ------------------------------------------------------------------ régions
    def _maj_regions(self) -> None:
        regions = [(None, self.tr("cc_toutes_regions"))] + [(k, n) for k, n in self.o.choix.get("zone", [])
                                                             if k is not None]
        actuelle = self.o._valeur("zone")
        if [k for k, _n in regions] != [k for k, _b in self.b_regions]:
            for _k, b in self.b_regions:
                b.destroy()
            self.b_regions = []
            for k, n in regions:
                b = th.Pilule(self.barre, self.th, n, lambda k=k: self.choisir_region(k), police="petit",
                              padx=7, pady=0)
                self.b_regions.append((k, b))
            self._disposer_regions()
        for k, b in self.b_regions:
            b.changer_genre("onglet" if k == actuelle else "normal")

    def _disposer_regions(self) -> None:
        px = self.th.px
        largeur = max(px(200), self.barre.winfo_width())
        x = y = 0
        haut = 0
        for _k, b in self.b_regions:
            w, h = int(b.cget("width")), int(b.cget("height"))    # canevas de la pilule (ombre comprise)
            if x and x + w > largeur:
                x, y = 0, y + haut + px(3)
            b.place(x=x, y=y)
            x += w + px(3)
            haut = max(haut, h)
        self.barre.configure(height=max(px(20), y + haut + px(2)))

    def choisir_region(self, cle) -> None:
        """Région = filtre « Zone » de l'onglet (partagé avec la liste). Choix à la main : le suivi du jeu se met en
        pause, sauf si la carte montrée pour cette région est celle du jeu."""
        self.suivi.choix_manuel(None)
        self.o.choisir_zone(cle)
        self.suivi.choix_manuel(self.carte)
        self._maj_etat_suivi()
        self.carte = None

    # ------------------------------------------------------------------ carte
    def _choisir_carte_liste(self) -> None:
        """Choix dans la liste native de la boîte (flèche) : elle montre la liste FILTRÉE, d'où `_filtre`."""
        i = self.cb_carte.current()
        if 0 <= i < len(self._filtre):
            self._choisir_carte(self._filtre[i])

    def _choisir_carte(self, rang: int) -> None:
        """Choix explicite de la carte de rang `rang` de `self.cartes` (seul endroit où la liste change de carte)."""
        self._fermer_liste_cartes()
        self._saisie = False
        if not 0 <= rang < len(self.cartes):
            self._rendre_nom_carte()
            return
        self.carte = self.cartes[rang][0]
        self.ajuster = True
        self.suivi.choix_manuel(self.carte)                  # autre carte que celle du jeu : suivi en pause
        self.remplir()
        self._maj_etat_suivi()
        if self._focus_dans_boite():
            self.cb_carte.select_range(0, "end")             # la frappe suivante remplace le nom

    # ------------------------------------------------------------------ liste des cartes : écrire pour chercher
    def _construire_recherche_carte(self, f: tk.Frame) -> None:
        """Boîte modifiable + liste filtrée POSÉE sous la boîte (`place`, aucune fenêtre en plus : la boîte garde le
        focus, les captures discrètes la voient). Filtrage : `CC.filtrer_noms` (noms dans la langue du lanceur)."""
        T = self.th
        self._libelles: list[str] = []               # libellés de toutes les lignes de `self.cartes` (même ordre)
        self._noms_recherche: list[str] = []         # nom seul de chaque carte (sans marque ni compteur)
        self._filtre: list[int] = []                 # rangs (dans `self.cartes`) des lignes montrées
        self._saisie = False                         # du texte a été tapé et aucune carte n'est encore choisie
        self._liste_ouverte = False
        self._texte_vu = ""
        self._taille_recherche: tuple[int, int] | None = None   # taille du canevas à l'ouverture de la liste
        cb = self.cb_carte
        cb.bind("<KeyRelease>", self._frappe_carte, add="+")
        cb.bind("<Down>", lambda _e: self._deplacer_liste_cartes(1))
        cb.bind("<Up>", lambda _e: self._deplacer_liste_cartes(-1))
        cb.bind("<Return>", lambda _e: self._valider_liste_cartes())
        cb.bind("<KP_Enter>", lambda _e: self._valider_liste_cartes())
        cb.bind("<Escape>", lambda _e: self._echap_carte())
        cb.bind("<FocusIn>", lambda _e: cb.select_range(0, "end") if not self._saisie else None, add="+")
        cb.bind("<FocusOut>", lambda _e: cb.after_idle(self._focus_quitte_carte), add="+")
        cb.bind("<Enter>", self._aide_carte, add="+")
        cb.bind("<Leave>", lambda _e: self.info.cacher(), add="+")
        self.l_cartes = lb = tk.Listbox(f, font=T["texte"], bg=th.BLANC, fg=th.TEXTE, selectbackground=th.CYAN_CLAIR,
                                        selectforeground=th.NOIR, activestyle="none", relief="solid", borderwidth=1,
                                        highlightthickness=0, exportselection=False, takefocus=0)
        lb.bind("<ButtonPress-1>", self._clic_liste_cartes)
        lb.bind("<Motion>", self._survol_liste_cartes)
        # clic ailleurs dans la fenêtre (carte, objets...) : la recherche est abandonnée (un canevas ne prend pas le
        # focus : pas de <FocusOut>) ; le clic sur la liste s'arrête avant (« break »)
        haut = f.winfo_toplevel()
        id_clic = haut.bind("<ButtonPress-1>", self._clic_ailleurs_carte, add="+")

        def _retirer(e) -> None:                     # la fenêtre survit aux reconstructions (changement de langue) :
            if e.widget is cb:                       # ne pas laisser une liaison par vue détruite
                try:
                    haut.unbind("<ButtonPress-1>", id_clic)
                except tk.TclError:
                    pass
        cb.bind("<Destroy>", _retirer, add="+")

    def _focus_dans_boite(self) -> bool:
        try:
            w = str(self.cb_carte.tk.call("focus"))
        except tk.TclError:
            return False
        nom = str(self.cb_carte)
        return w == nom or w.startswith(nom + ".")        # boîte, ou sa liste native (`<boîte>.popdown`)

    def _aide_carte(self, e) -> None:
        if not self._liste_ouverte:
            self.info.montrer(self.tr("cc_carte_aide"), e.x_root, e.y_root)

    def _ecrire_boite(self) -> None:
        """Liste complète dans la boîte, nom de la carte courante écrit (hors saisie)."""
        self._filtre = list(range(len(self._libelles)))
        self.cb_carte.configure(values=self._libelles)
        cles = [k for k, _g, _t in self.cartes]
        if self.carte in cles and len(self._libelles) == len(cles):
            self.cb_carte.current(cles.index(self.carte))
        else:
            self.cb_carte.set("")
        self._texte_vu = self.cb_carte.get()

    def _maj_liste_cartes(self) -> None:
        """Après `remplir` : hors saisie, liste complète et nom de la carte courante ; pendant une saisie, le texte tapé
        reste et le filtre est refait sur les nouvelles lignes (ligne choisie gardée si elle y est encore)."""
        if not self._saisie:
            self._fermer_liste_cartes()
            self._ecrire_boite()
            return
        sel = self.l_cartes.curselection()
        avant = self._filtre[sel[0]] if sel and sel[0] < len(self._filtre) else None
        avant = self.cartes[avant][0] if avant is not None and avant < len(self.cartes) else None
        self._filtrer_cartes(self.cb_carte.get(), garder=avant)

    def _vider_liste_cartes(self) -> None:
        self._libelles, self._noms_recherche, self._filtre = [], [], []
        self._saisie = False
        self._fermer_liste_cartes()
        self.cb_carte.configure(values=[])
        self.cb_carte.set("")
        self._texte_vu = ""

    def _frappe_carte(self, _e=None) -> None:
        texte = self.cb_carte.get()
        if texte == self._texte_vu:                      # flèches, Maj, Entrée... : rien n'a été écrit
            return
        self._texte_vu = texte
        if not self._libelles:
            return
        self._filtrer_cartes(texte)

    def _filtrer_cartes(self, texte: str, garder: str | None = None) -> None:
        """Filtre la liste (aucune carte redessinée : seule la liste change) et la montre, 1re ligne choisie."""
        self.info.cacher()
        self._saisie = True
        self._filtre = CC.filtrer_noms(self._noms_recherche, texte)
        self.cb_carte.configure(values=[self._libelles[i] for i in self._filtre])
        choix = 0 if self._filtre else None
        if garder is not None:
            choix = next((j for j, i in enumerate(self._filtre) if self.cartes[i][0] == garder), choix)
        self._montrer_liste_cartes(choix)

    def _montrer_liste_cartes(self, choix: int | None) -> None:
        lb = self.l_cartes
        lb.delete(0, "end")
        if self._filtre:
            lb.insert("end", *[self._libelles[i] for i in self._filtre])
        else:                                            # aucun résultat : une ligne grise, rien à choisir
            lb.insert("end", self.tr("cc_carte_aucune"))
            lb.itemconfigure(0, foreground=th.TEXTE_DOUX, selectforeground=th.TEXTE_DOUX, selectbackground=th.BLANC)
        lb.configure(height=max(1, min(LIGNES_LISTE_CARTES, lb.size())))
        lb.place(in_=self.cb_carte, x=0, rely=1.0, y=1, relwidth=1.0)
        lb.lift()
        self._liste_ouverte = True
        self._taille_recherche = None                    # <Configure> en retard traités par ce tour : sans effet
        lb.update_idletasks()                            # hauteur réelle AVANT `see` : sinon (1 ligne) la ligne choisie
        self._taille_recherche = self._taille_canevas()
        self._choisir_ligne(choix)                       # devient la 1re visible et les précédentes sont masquées

    def _choisir_ligne(self, i: int | None) -> None:
        lb = self.l_cartes
        lb.selection_clear(0, "end")
        if i is None or not self._filtre:
            return
        i = max(0, min(len(self._filtre) - 1, i))
        lb.selection_set(i)
        lb.activate(i)
        lb.see(i)

    def _taille_canevas(self) -> tuple[int, int]:
        return self.canvas.winfo_width(), self.canvas.winfo_height()

    def abandonner_recherche(self) -> None:
        """Changement d'onglet, de sous-vue ou de taille : la recherche est abandonnée (nom de la carte courante rendu)."""
        try:
            if (self._saisie or self._liste_ouverte) and self.cb_carte.winfo_exists():
                self._rendre_nom_carte()
        except tk.TclError:
            pass

    def _fermer_liste_cartes(self) -> None:
        if self._liste_ouverte:
            self.l_cartes.place_forget()
        self._liste_ouverte = False

    def ligne_choisie(self) -> int | None:
        """Rang (dans `self.cartes`) de la ligne en surbrillance de la liste ouverte, None sinon (tests)."""
        sel = self.l_cartes.curselection() if self._liste_ouverte else ()
        return self._filtre[sel[0]] if sel and sel[0] < len(self._filtre) else None

    def _deplacer_liste_cartes(self, sens: int) -> str:
        if not self._liste_ouverte:                      # liste fermée : l'ouvrir sur la carte courante
            if not self._saisie:
                self._filtre = list(range(len(self._libelles)))
            if not self._libelles:
                return "break"
            cles = [self.cartes[i][0] for i in self._filtre]
            self._montrer_liste_cartes(cles.index(self.carte) if self.carte in cles else 0)
            return "break"
        sel = self.l_cartes.curselection()
        self._choisir_ligne(sel[0] + sens if sel else 0)
        return "break"

    def _valider_liste_cartes(self) -> str:
        rang = self.ligne_choisie()
        if rang is not None:
            self._choisir_carte(rang)
        return "break"                                   # aucun résultat : rien ne change (Échap pour revenir)

    def _echap_carte(self) -> str:
        self._rendre_nom_carte()
        if self._focus_dans_boite():
            self.cb_carte.select_range(0, "end")
        return "break"

    def _rendre_nom_carte(self) -> None:
        """Abandon de la recherche : liste fermée, nom de la carte courante rendu (jamais de carte inexistante)."""
        self._fermer_liste_cartes()
        self._saisie = False
        self._ecrire_boite()

    def _focus_quitte_carte(self) -> None:
        try:
            if not self.cb_carte.winfo_exists() or self._focus_dans_boite():
                return
        except tk.TclError:
            return
        if self._saisie or self._liste_ouverte:
            self._rendre_nom_carte()

    def _clic_liste_cartes(self, e) -> str:
        if self._filtre:
            i = self.l_cartes.nearest(e.y)
            if 0 <= i < len(self._filtre):
                self._choisir_carte(self._filtre[i])
        return "break"

    def _survol_liste_cartes(self, e) -> None:
        if self._filtre:
            self._choisir_ligne(self.l_cartes.nearest(e.y))

    def _clic_ailleurs_carte(self, e) -> None:
        try:
            if not (self._saisie or self._liste_ouverte) or not self.cb_carte.winfo_exists():
                return
            if str(e.widget) == str(self.cb_carte):
                if "arrow" in str(self.cb_carte.identify(e.x, e.y)):
                    self._fermer_liste_cartes()          # la liste native (filtrée) prend le relais
                return
        except tk.TclError:
            return
        self._rendre_nom_carte()

    def ouvrir_carte(self, carte: str, centrer: tuple[float, float] | None = None) -> None:
        """Carte d'un check choisi dans la liste (choix à la main : pause du suivi si ce n'est pas la carte du jeu)."""
        self.carte = carte
        self.suivi.choix_manuel(carte)
        self.remplir()
        self._maj_etat_suivi()
        if centrer:
            self.centrer(*centrer)

    # ------------------------------------------------------------------ suivi du jeu
    def demarrer_suivi(self) -> None:
        """Sous-onglet affiché : lit le lieu du joueur tout de suite puis toutes les `PERIODE_SUIVI` ms. La boucle
        s'arrête seule dès que le sous-onglet n'est plus affiché (aucune lecture pour un onglet caché)."""
        if self._tache_suivi is None:
            self._tour_suivi()

    def _tour_suivi(self) -> None:
        self._tache_suivi = None
        try:
            if not self.cadre.winfo_exists() or not (self.o.visible and self.o.vue == "carte"):
                return
            self.suivre_jeu()
            self._tache_suivi = self.cadre.after(PERIODE_SUIVI, self._tour_suivi)
        except tk.TclError:
            self._tache_suivi = None

    def lire_lieu(self, maintenant: float | None = None) -> CC.Lieu | None:
        sig = CC.signature_lieu(self.o.dossier)
        if sig != self._sig_lieu:
            self._sig_lieu = sig
            self._lieu_brut = CC.lire_lieu(self.o.dossier) if sig is not None else None
        self.lieu = CC.lieu_jeu(self._lieu_brut, self.don, maintenant)
        return self.lieu

    def suivre_jeu(self, maintenant: float | None = None) -> None:
        """Un tour du suivi : carte du jeu montrée si le suivi est actif et pas en pause, rond du joueur déplacé."""
        avant = self.lieu
        lieu = self.lire_lieu(maintenant)
        if self.don is None or not self.don.cartes or self.o.modele.sans_donnees:
            return
        cible = self.suivi.cible(lieu, self.don)
        if cible is not None and cible != self.carte and cible in self.don.cartes:
            self._montrer_carte_jeu(cible)
        elif lieu != avant:
            self._dessiner_joueur()
        self._maj_etat_suivi()

    def _montrer_carte_jeu(self, carte: str) -> None:
        """Affiche la carte du jeu ; si la région choisie n'a aucun check sur cette carte, la région repasse à
        « Toutes les régions » (sinon ses checks y seraient tous masqués)."""
        m, f = self.o.modele, self.o.filtre()
        self.carte = carte
        self.ajuster = True
        if f.zone is not None and carte not in [k for k, _g, _t in CC.cartes_de_zone(m, self.don, f)]:
            self.o.choisir_zone(None)                        # remplit (carte gardée : entrée de la carte suivie)
        else:
            self.o.remplir()

    def _bascule_suivi(self) -> None:
        self.suivi.cocher(bool(self.v_suivre.get()))
        self.o.memoriser_suivi(self.suivi.actif)
        if self.o.visible and self.o.vue == "carte":
            self.suivre_jeu()
        self._maj_etat_suivi()

    def copier_position(self) -> str | None:
        """Bouton « Copier ma position » : met « carte:x,z  # nom » dans le presse-papiers d'après le suivi du jeu
        (`lieu.json` relu maintenant) ; rien n'est copié sans suivi récent, sans carte connue ou sans position.
        Renvoie la ligne copiée (None : rien)."""
        lieu = self.lire_lieu()
        ligne = CC.ligne_position(lieu, self.nom_carte(lieu.carte) if lieu is not None and lieu.carte else None)
        if ligne is not None:
            self.cadre.clipboard_clear()
            self.cadre.clipboard_append(ligne)
            self.copie = ligne
        try:
            x, y = self.b_copier.winfo_rootx(), self.b_copier.winfo_rooty() + self.b_copier.winfo_height()
            self.info.montrer(self.tr("cc_copie_faite", ligne=ligne) if ligne else self.tr("cc_copie_rien"), x, y)
        except tk.TclError:
            pass
        return ligne

    def _maj_etat_suivi(self) -> None:
        texte = self.tr("cc_suivi_pause") if self.suivi.en_pause else ""
        if self.l_suivi.cget("text") != texte:
            self.l_suivi.configure(text=texte)

    def position_joueur(self) -> tuple[float, float] | None:
        """Pixel d'image du joueur sur la carte affichée (None : pas sur cette carte, ou position inconnue)."""
        return CC.pixel_joueur(self.don, self.carte, self.lieu)

    def _dessiner_joueur(self) -> None:
        """Rond « vous êtes ici » (au-dessus des marqueurs) ; redessiné seul quand le joueur se déplace. Suivi actif
        et carte plus grande que la vue : la vue est recentrée quand le joueur en sort."""
        c, px = self.canvas, self.th.px
        c.delete("joueur")
        p = self.position_joueur()
        if p is None:
            return
        x, y = self.image_vers_canevas(*p)
        r = px(6)
        c.create_oval(x - r - px(3), y - r - px(3), x + r + px(3), y + r + px(3), fill=th.BLANC, outline=th.NOIR,
                      width=1, tags=("joueur",))
        c.create_oval(x - r, y - r, x + r, y + r, fill=COULEUR_JOUEUR, outline=th.NOIR, width=1, tags=("joueur",))
        c.create_oval(x - px(2), y - px(2), x + px(2), y + px(2), fill=th.NOIR, outline="", tags=("joueur",))
        c.tag_bind("joueur", "<Enter>", lambda e: self.info.montrer(self.tr("cc_joueur"), e.x_root, e.y_root))
        c.tag_bind("joueur", "<Leave>", lambda _e: self.info.cacher())
        if self.suivi.actif and not self.suivi.pause:
            x0, y0 = c.canvasx(0), c.canvasy(0)
            if not (x0 <= x <= x0 + c.winfo_width() and y0 <= y <= y0 + c.winfo_height()):
                self.centrer(*p)

    def _facteur(self) -> float:
        a, b = FACTEURS[self.facteur]
        return a / b

    def _choisir_facteur_ajuste(self) -> None:
        info = self.don.cartes.get(self.carte) if self.don and self.carte else None
        if info is None:
            return
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        if w <= 2 or h <= 2:
            w, h = self.th.px(420), self.th.px(260)
        ok = [i for i, (a, b) in enumerate(FACTEURS) if info.largeur * a / b <= w and info.hauteur * a / b <= h]
        self.facteur = max(ok) if ok else 0

    def zoomer(self, sens: int) -> None:
        self.ajuster = False
        n = max(0, min(len(FACTEURS) - 1, self.facteur + sens))
        if n != self.facteur:
            cx, cy = self._centre_vue()
            self.facteur = n
            self._dessiner_carte()
            self.centrer(cx, cy)

    def ajuster_zoom(self) -> None:
        self.ajuster = True
        self._dessiner_carte()

    def _centre_vue(self) -> tuple[float, float]:
        c, k = self.canvas, self._facteur()
        return ((c.canvasx(0) + c.winfo_width() / 2 - self._ox) / k,
                (c.canvasy(0) + c.winfo_height() / 2 - self._oy) / k)

    def centrer(self, x: float, y: float) -> None:
        """Centre la vue sur le pixel d'image (x, y)."""
        info = self.don.cartes.get(self.carte) if self.don and self.carte else None
        if info is None:
            return
        k = self._facteur()
        W, H = info.largeur * k, info.hauteur * k
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if W > w:
            c.xview_moveto(max(0.0, min(1.0, (x * k - w / 2) / W)))
        if H > h:
            c.yview_moveto(max(0.0, min(1.0, (y * k - h / 2) / H)))

    def image_vers_canevas(self, x: float, y: float) -> tuple[float, float]:
        k = self._facteur()
        return self._ox + x * k, self._oy + y * k

    def _redimensionne(self) -> None:
        if ((self._saisie or self._liste_ouverte) and self._taille_recherche is not None
                and self._taille_canevas() != self._taille_recherche):
            self.abandonner_recherche()                  # vraie nouvelle taille (pas un <Configure> en retard)
        if self.don is not None and self.carte and self.o.vue == "carte":
            avant = (self.facteur, self._ox, self._oy)
            if self.ajuster:
                self._choisir_facteur_ajuste()
            if avant != (self.facteur,) + self._decalage():
                self._dessiner_carte()

    def _decalage(self) -> tuple[float, float]:
        info = self.don.cartes.get(self.carte) if self.don and self.carte else None
        if info is None:
            return 0.0, 0.0
        k = self._facteur()
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return max(0.0, (w - info.largeur * k) / 2) // 1, max(0.0, (h - info.hauteur * k) / 2) // 1

    def _image_carte(self, info: CC.InfoCarte) -> tk.PhotoImage | None:
        cle = (info.id, self.facteur)
        if self._image_cle == cle and self._image is not None:
            return self._image
        try:
            if self._image_base is None or self._image_cle is None or self._image_cle[0] != info.id:
                self._image_base = tk.PhotoImage(master=self.canvas, file=str(info.png))
            a, b = FACTEURS[self.facteur]
            im = self._image_base
            if a > 1:
                im = im.zoom(a)
            if b > 1:
                im = im.subsample(b)
        except (tk.TclError, OSError):
            return None
        self._image, self._image_cle = im, cle
        return im

    def _dessiner_carte(self) -> None:
        c = self.canvas
        c.delete("all")
        self.info.cacher()
        info = self.don.cartes.get(self.carte) if self.don and self.carte else None
        if info is None:
            c.configure(scrollregion=(0, 0, 1, 1))
            c.create_text(self.th.px(20), self.th.px(20), text=self.tr("cc_aucune_carte"), anchor="nw",
                          fill=th.BLANC, font=self.th["texte"])
            self.marqueurs = []
            return
        if self.ajuster:
            self._choisir_facteur_ajuste()
        k = self._facteur()
        im = self._image_carte(info)
        W, H = round(info.largeur * k), round(info.hauteur * k)
        self._ox, self._oy = self._decalage()
        if im is not None:
            c.create_image(self._ox, self._oy, image=im, anchor="nw", tags=("fond",))
        c.configure(scrollregion=(0, 0, W + 2 * self._ox, H + 2 * self._oy))
        self.marqueurs = CC.marqueurs(self.o.modele, self.don, self.o.filtre(), self.carte, k,
                                      rayon=self.th.px(8), progression=self.progression())
        sel = self.o.selection
        for i, mq in enumerate(self.marqueurs):
            self._dessiner_marqueur(i, mq, k, sel in mq.ids)
        self._dessiner_epingle()
        self._dessiner_joueur()
        self._dessiner_panneau()

    # ------------------------------------------------------------------ panneau d'une boutique (sur la carte)
    def marqueur_panneau(self) -> CC.Marqueur | None:
        """Marqueur de boutique dont le panneau est ouvert sur la carte affichée (None : fermé)."""
        if self.panneau is None or self.panneau[0] != self.carte:
            return None
        return next((mq for mq in self.marqueurs if mq.genre == "boutique" and mq.codes == self.panneau[1]), None)

    def lignes_panneau(self, mq: CC.Marqueur) -> list[tuple[str, CK.Check | None]]:
        """Lignes du panneau : pour chaque boutique du marqueur, son titre (« nom — n/m faits », check None) puis UN
        article par ligne : « article i », suivi de son contenu s'il est fait ou indiqué (`texte_contenu` : rien
        d'autre n'est connu du lanceur)."""
        lignes: list[tuple[str, CK.Check | None]] = []
        for _code, cs in CC.boutiques_du_marqueur(mq, self.don):
            faits = sum(1 for c in cs if c.etat == "fait")
            acces = 0 if CC.vendeur_absent(mq.presences.get(_code)) else sum(1 for c in cs if c.etat == "accessible")
            lignes.append((self.tr("cc_bt_resume_acces" if acces else "cc_bt_resume", nom=CC.nom_boutique(cs),
                                   n=faits, m=len(cs), k=acces), None))
            for c in cs:
                contenu = self.o.texte_contenu(c)
                if len(contenu) > PANNEAU_CONTENU_MAX:
                    contenu = contenu[:PANNEAU_CONTENU_MAX - 1] + "…"
                lignes.append((f"{CC.nom_article(c)} — {contenu}" if contenu else CC.nom_article(c), c))
        return lignes

    def _dessiner_panneau(self) -> None:
        """Panneau de la boutique choisie, dessiné SUR la carte à côté de son marqueur : chaque article avec un carré
        de la couleur de son état (liseré or : indice), en colonnes si la liste dépasse la hauteur visible ; clic sur
        une ligne : l'article est choisi (ligne de détail, liste de l'onglet) ; clic sur la carte : fermé."""
        c, px = self.canvas, self.th.px
        c.delete("panneau")
        self._lignes_panneau = {}
        mq = self.marqueur_panneau()
        if mq is None:
            return
        lignes = self.lignes_panneau(mq)
        pas, marge, carre = px(15), px(6), px(8)
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 2 or h <= 2:                                 # canevas pas encore affiché : taille de départ
            w, h = px(420), px(260)
        vue_h = max(px(120), h)
        par_colonne = max(4, (vue_h - 2 * marge - px(8)) // pas)
        colonnes = [lignes[i:i + par_colonne] for i in range(0, len(lignes), par_colonne)]
        items, x = [], 0
        haut = pas * max(len(col) for col in colonnes)
        for col in colonnes:
            large = 0
            for j, (texte, chk) in enumerate(col):
                y = j * pas + pas // 2
                if chk is None:
                    t = c.create_text(x, y, text=texte, anchor="w", font=self.th["bouton_petit"], fill=th.NOIR,
                                      tags=("panneau",))
                else:
                    etat = "fait" if chk.etat == "fait" else "accessible" if chk.etat == "accessible" else "non"
                    if etat == "accessible" and CC.report_article(mq, self._code_article(chk), chk):
                        etat = "non"                                 # vendeur absent à coup sûr : pas maintenant
                    indice = chk.indice and chk.etat != "fait"
                    items.append(c.create_rectangle(x, y - carre // 2, x + carre, y + carre // 2, fill=COULEURS[etat],
                                                    outline=COULEUR_INDICE if indice else th.NOIR,
                                                    width=px(2) if indice else 1, tags=("panneau", "ligne")))
                    self._lignes_panneau[items[-1]] = chk.id
                    choisi = chk.id == self.o.selection
                    t = c.create_text(x + carre + px(5), y, text=texte, anchor="w",
                                      font=self.th["bouton_petit" if choisi else "petit"],
                                      fill=th.CYAN_TEXTE if choisi else th.TEXTE, tags=("panneau", "ligne"))
                    self._lignes_panneau[t] = chk.id
                items.append(t)
                large = max(large, c.bbox(t)[2] - x)
            x += large + px(14)
        large_tout = x - px(14)
        # fond, puis placement à côté du marqueur, ramené dans la partie visible de la carte
        fond = c.create_rectangle(-marge, -marge, large_tout + marge, haut + marge, fill="#FFFBEA", outline=th.NOIR,
                                  width=1, tags=("panneau",))
        c.tag_lower(fond, items[0])
        mx, my = self.image_vers_canevas(mq.x, mq.y)
        x0, y0 = c.canvasx(0), c.canvasy(0)
        dx = mx + px(16) + marge
        if dx + large_tout + marge > x0 + w:                     # pas la place à droite : à gauche du marqueur
            dx = mx - px(16) - marge - large_tout
        dx = max(x0 + marge + 1, min(dx, x0 + w - large_tout - marge - 1))
        dy = max(y0 + marge + 1, min(my - haut / 2, y0 + h - haut - marge - 1))
        c.move("panneau", dx, dy)

    def _survol_panneau(self, e) -> None:
        item = self.canvas.find_withtag("current")
        ident = self._lignes_panneau.get(item[0]) if item else None
        chk = next((x for x in self.o.modele.checks if x.id == ident), None) if ident is not None else None
        if chk is not None:
            mq = self.marqueur_panneau()
            etat = (self.texte_etat_article(mq, self._code_article(chk), chk) if mq is not None
                    else self.o.texte_etat(chk))
            s = f"{chk.nom} — {etat}"
            contenu = self.o.texte_contenu(chk)
            self.info.montrer(f"{s} — {contenu}" if contenu else s, e.x_root, e.y_root)

    def _clic_panneau(self, _e) -> None:
        item = self.canvas.find_withtag("current")
        ident = self._lignes_panneau.get(item[0]) if item else None
        if ident is not None:
            self.info.cacher()
            self.o.choisir(ident)

    def fermer_panneau(self) -> None:
        if self.panneau is not None:
            self.panneau = None
            self.canvas.delete("panneau")

    def _dessiner_epingle(self) -> None:
        """Points du Yo-kai épinglé sur la carte affichée : losange (loupe) ou triangle (errant) violet, pâle si aucun
        de ses lieux n'est accessible maintenant ; petit rond jaune (jour seulement) ou bleu nuit (nuit seulement) en
        haut à droite du marqueur. Un appel Tcl par point, un de plus pour un point à moment restreint (infobulle :
        lien posé une fois sur l'étiquette « yokai »)."""
        c, px = self.canvas, self.th.px
        ep = self._ep
        self.points_yokai = list(ep.cartes.get(self.carte) or ()) if ep is not None and self.carte else []
        self._items_yokai = {}
        r = px(7)
        for i, p in enumerate(self.points_yokai):
            x, y = self.image_vers_canevas(p.x, p.y)
            if p.acces is False:
                kw = {"fill": COULEUR_YOKAI_PALE, "outline": COULEUR_YOKAI, "width": px(2)}
            else:
                kw = {"fill": COULEUR_YOKAI, "outline": th.BLANC, "width": px(1)}
            if p.methode == "loupe":
                forme = (x, y - r, x + r, y, x, y + r, x - r, y)
            else:
                forme = (x, y - r, x + r, y + r * 0.8, x - r, y + r * 0.8)
            self._items_yokai[c.create_polygon(*forme, tags=("yokai",), **kw)] = i
            quand = p.quand
            if quand:
                self._items_yokai[self._rond_moment(c, x + r * 0.8, y - r * 0.8, px(4), quand, ("yokai",))] = i

    @staticmethod
    def _rond_moment(c, x: float, y: float, r: float, quand: str, tags=()) -> int:
        fond, contour = COULEURS_MOMENT[quand]
        return c.create_oval(x - r, y - r, x + r, y + r, fill=fond, outline=contour, tags=tags)

    def texte_infobulle_yokai(self, p: CC.PointYokai) -> str:
        """Nom du Yo-kai épinglé, puis une ligne par lieu qui passe par ce point : méthode (décor du point), niveaux,
        conditions (rang de montre, nuit…), accès."""
        tr = self.o.tracker
        lignes = [self.tr("cc_yk_marque") + self.nom_epingle()]
        vus = []
        for (l, decor), moment in zip(p.lieux, p.moments):
            texte = P.texte_point(self.o.langue, tr.modele, l, decor, moment)
            if texte not in vus:
                vus.append(texte)
        lignes += vus[:INFOBULLE_MAX]
        if len(vus) > INFOBULLE_MAX:
            lignes.append(self.tr("cc_et_autres", n=len(vus) - INFOBULLE_MAX))
        return "\n".join(lignes)

    def _survol_yokai(self, e) -> None:
        item = self.canvas.find_withtag("current")
        i = self._items_yokai.get(item[0]) if item else None
        if i is not None and 0 <= i < len(self.points_yokai):
            self.info.montrer(self.texte_infobulle_yokai(self.points_yokai[i]), e.x_root, e.y_root)

    @staticmethod
    def _maison(x: float, y: float, r: float) -> tuple[float, ...]:
        """Forme du marqueur de boutique : une maison (carré surmonté d'un toit pointu)."""
        return (x - r, y + r, x - r, y - r * 0.3, x, y - r * 1.35, x + r, y - r * 0.3, x + r, y + r)

    def _dessiner_boutique(self, i: int, mq: CC.Marqueur, choisi: bool) -> None:
        """Marqueur de boutique : MAISON pleine de la couleur de l'état global de ses articles (tous faits / restants
        accessibles / en partie / aucun accessible), nombre d'articles restants inscrit (« ✓ » : tous faits) ; porte
        d'un bâtiment à boutique (genre « entree ») : petite maison blanche au contour de cette couleur. Trois à cinq
        appels Tcl par marqueur, comme un marqueur de check."""
        c, px = self.canvas, self.th.px
        x, y = self.image_vers_canevas(mq.x, mq.y)
        entree = mq.genre == "entree"
        r = px(6) if entree else px(9)
        tag = f"m{i}"
        tags = ("marqueur", tag)
        if choisi and not entree:
            c.create_rectangle(x - r - px(5), y - r * 1.35 - px(5), x + r + px(5), y + r + px(5),
                               outline=COULEUR_SELECTION, width=px(3), tags=tags)
        if mq.indice:
            c.create_polygon(*self._maison(x, y, r + px(3)), fill="", outline=COULEUR_INDICE, width=px(2), tags=tags)
        if entree:
            # porte : vendeur(s) absent(s) à coup sûr derrière elle : contour gris en pointillés ; présence inconnue :
            # « ? » dans la petite maison (jamais la couleur « accessible » pour une boutique fermée)
            present = mq.present if len(mq.checks) - mq.faits else True
            if present is False:
                c.create_polygon(*self._maison(x, y, r), fill=COULEUR_ABSENT, outline=COULEUR_ABSENT_BORD, width=px(2),
                                 dash=(3, 2), tags=tags)
            else:
                c.create_polygon(*self._maison(x, y, r), fill=th.BLANC, outline=COULEURS[mq.etat], width=px(2),
                                 tags=tags)
            if present is None:
                c.create_text(x, y + r * 0.15, text="?", fill=th.NOIR, font=self.th["badge"], tags=tags)
        else:
            # vendeur absent à coup sûr (condition connue fausse) : maison VIDE grise, jamais la couleur « accessible » ;
            # présence inconnue (étal ambulant, flag ou requête non suivis) : « ? » ; jour / nuit : petit rond
            reste = len(mq.checks) - mq.faits
            present = mq.present if reste else True
            if present is False:
                c.create_polygon(*self._maison(x, y, r), fill=COULEUR_ABSENT, outline=COULEUR_ABSENT_BORD, width=px(2),
                                 dash=(3, 2), tags=tags)
                c.create_text(x, y + r * 0.15, text=str(reste) if reste < 100 else "99+", fill=COULEUR_ABSENT_BORD,
                              font=self.th["badge"], tags=tags)
            else:
                c.create_polygon(*self._maison(x, y, r), fill=COULEURS[mq.etat], outline=th.BLANC, width=1, tags=tags)
                c.create_text(x, y + r * 0.15, text="✓" if not reste else str(reste) if reste < 100 else "99+",
                              fill=th.BLANC, font=self.th["badge"], tags=tags)
            if present is None:
                rr = px(5)
                c.create_oval(x - r - rr * 0.4, y - r * 1.2 - rr, x - r + rr * 1.6, y - r * 1.2 + rr, fill=th.BLANC,
                              outline=th.NOIR, tags=tags)
                c.create_text(x - r + rr * 0.6, y - r * 1.2, text="?", fill=th.NOIR, font=self.th["badge"], tags=tags)
            if reste and mq.quand:
                self._rond_moment(c, x + r * 0.9, y - r * 1.1, px(4), mq.quand, tags)
        c.tag_bind(tag, "<Enter>", lambda e, i=i: self._survol(i, e), add="+")
        c.tag_bind(tag, "<Leave>", lambda _e: self.info.cacher(), add="+")
        c.tag_bind(tag, "<ButtonRelease-1>", lambda _e, i=i: self.clic_marqueur(i), add="+")

    def nom_carte(self, carte: str) -> str:
        """Nom d'une carte dans la langue du joueur (`noms_local.json`), sinon son identifiant."""
        from . import noms_locaux
        d = noms_locaux.charger(self.o.dossier) or {}
        lg = "engb" if self.o.langue == "en" else "fr"
        return (((d.get("langues") or {}).get(lg) or {}).get("cartes") or {}).get(carte, carte)

    def texte_etat_article(self, mq: CC.Marqueur, code: str, c: CK.Check) -> str:
        """État d'un article : celui de la logique, sauf « Accessible » quand son vendeur est absent à coup sûr à ce
        stade de la partie (« plus tard », avec la raison : nuit pas encore libre, ou vendeur absent)."""
        cle = CC.report_article(mq, code, c)
        return self.tr(cle) if cle else self.o.texte_etat(c)

    def _code_article(self, c: CK.Check) -> str | None:
        p = self.don.positions.get(c.id) if self.don is not None else None
        return p.boutique if p is not None else None

    def texte_infobulle_boutique(self, mq: CC.Marqueur) -> str:
        """Boutique : son nom et « n/m faits », puis CHAQUE article gardé par les filtres avec son état et son contenu
        (fait ou indiqué SEULEMENT, comme partout : `texte_contenu` de l'onglet). Porte : la carte où l'on entre et le
        résumé de chaque boutique qu'elle dessert."""
        lignes = []
        entree = mq.genre == "entree"
        if entree:
            lignes.append(self.tr("cc_bt_entree", carte=self.nom_carte(mq.vers or "")))
        reste_lignes = INFOBULLE_BOUTIQUE_MAX
        for _code, cs in CC.boutiques_du_marqueur(mq, self.don):
            faits = sum(1 for c in cs if c.etat == "fait")
            acces = sum(1 for c in cs if c.etat == "accessible")
            pr = mq.presences.get(_code)
            if pr is not None and pr.connue and pr.present is False:
                acces = 0                                    # vendeur absent à coup sûr : pas de « accessible »
            lignes.append(self.tr("cc_bt_resume_acces" if acces else "cc_bt_resume", nom=CC.nom_boutique(cs), n=faits,
                                  m=len(cs), k=acces))
            for cle, params in CC.lignes_presence(pr) if pr is not None else ():
                lignes.append("   " + self.tr(cle, **params))
            if entree:
                continue
            for c in cs[:max(0, reste_lignes)]:
                s = f"   {CC.nom_article(c)} — {self.texte_etat_article(mq, _code, c)}"
                contenu = self.o.texte_contenu(c)
                if contenu:
                    s += f" — {contenu}"
                lignes.append(s)
            if len(cs) > reste_lignes:
                lignes.append("   " + self.tr("cc_bt_autres", n=len(cs) - max(0, reste_lignes)))
            reste_lignes -= len(cs)
        return "\n".join(lignes)

    def _dessiner_marqueur(self, i: int, mq: CC.Marqueur, k: float, choisi: bool) -> None:
        if mq.genre != "check":
            self._dessiner_boutique(i, mq, choisi)
            return
        c, px = self.canvas, self.th.px
        x, y = self.image_vers_canevas(mq.x, mq.y)
        n = len(mq.checks)
        r = px(6) if n == 1 else px(8)
        tag = f"m{i}"
        tags = ("marqueur", tag)
        if choisi:
            c.create_rectangle(x - r - px(5), y - r - px(5), x + r + px(5), y + r + px(5), outline=COULEUR_SELECTION,
                               width=px(3), tags=tags)
        if mq.indice:
            c.create_rectangle(x - r - px(3), y - r - px(3), x + r + px(3), y + r + px(3), outline=COULEUR_INDICE,
                               width=px(2), tags=tags)
        kw = {"dash": (3, 2)} if mq.approx else {}
        c.create_rectangle(x - r, y - r, x + r, y + r, fill=COULEURS[mq.etat], outline=th.BLANC, width=1, tags=tags,
                           **kw)
        if n > 1:
            c.create_text(x, y, text=str(n) if n < 100 else "99+", fill=th.BLANC, font=self.th["badge"], tags=tags)
        c.tag_bind(tag, "<Enter>", lambda e, i=i: self._survol(i, e), add="+")
        c.tag_bind(tag, "<Leave>", lambda _e: self.info.cacher(), add="+")
        c.tag_bind(tag, "<ButtonRelease-1>", lambda _e, i=i: self.clic_marqueur(i), add="+")

    def texte_infobulle(self, mq: CC.Marqueur) -> str:
        """Nom, état et contenu (fait ou indiqué SEULEMENT, via `texte_contenu` de l'onglet) des checks du marqueur."""
        if mq.genre != "check":
            return self.texte_infobulle_boutique(mq)
        lignes = []
        for c in mq.checks[:INFOBULLE_MAX]:
            s = f"{c.nom} — {self.o.texte_etat(c)}"
            contenu = self.o.texte_contenu(c)
            if contenu:
                s += f" — {contenu}"
            lignes.append(s)
        if len(mq.checks) > INFOBULLE_MAX:
            lignes.append(self.tr("cc_et_autres", n=len(mq.checks) - INFOBULLE_MAX))
        if mq.approx:
            lignes.append(self.tr("cc_approx"))
        return "\n".join(lignes)

    def _survol(self, i: int, e) -> None:
        if 0 <= i < len(self.marqueurs):
            self.info.montrer(self.texte_infobulle(self.marqueurs[i]), e.x_root, e.y_root)

    def _appui(self, e) -> None:
        self.canvas.scan_mark(e.x, e.y)
        if self.panneau is not None:                         # clic hors du panneau et des marqueurs : le fermer
            item = self.canvas.find_withtag("current")
            tags = self.canvas.gettags(item[0]) if item else ()
            if "panneau" not in tags and "marqueur" not in tags:
                self.fermer_panneau()

    def _molette(self, e) -> str:
        if e.state & 0x0004:                                 # Ctrl : zoom
            self.zoomer(1 if e.delta > 0 else -1)
        else:
            self.canvas.yview_scroll(-1 * (e.delta // 120 or (1 if e.delta > 0 else -1)) * self.th.px(40), "units")
        return "break"

    def clic_marqueur(self, i: int) -> None:
        """Choisit un check du marqueur (clics successifs : checks suivants du groupe, restants d'abord)."""
        if not 0 <= i < len(self.marqueurs):
            return
        mq = self.marqueurs[i]
        if mq.genre == "entree":                             # porte d'un bâtiment à boutique : ouvrir sa carte
            if mq.vers and self.don is not None and mq.vers in self.don.cartes:
                self.info.cacher()
                self.ajuster = True
                self.ouvrir_carte(mq.vers)
            return
        if not mq.checks:
            return
        if mq.genre == "boutique":
            # boutique : le panneau de ses articles s'ouvre sur la carte (second clic sur le marqueur : il se ferme) ;
            # si aucun de ses articles n'était choisi, le premier qui reste à faire l'est (détail sous la carte)
            self.info.cacher()
            cle = (self.carte, mq.codes)
            if self.panneau == cle:
                self.fermer_panneau()
                return
            self.panneau = cle
            if self.o.selection in mq.ids:
                self._dessiner_panneau()
            else:
                self.o.choisir(min(mq.checks, key=lambda c: (c.etat == "fait", c.id)).id)
            return
        ordre = sorted(mq.checks, key=lambda c: (c.etat == "fait", c.nom))
        rang = self._cycle.get(i, 0) % len(ordre)
        if self.o.selection in mq.ids and len(ordre) > 1:
            rang = (ordre.index(next(c for c in ordre if c.id == self.o.selection)) + 1) % len(ordre)
        self._cycle[i] = rang + 1
        self.o.choisir(ordre[rang].id)

    def montrer_selection(self) -> None:
        """Sélection venue de la liste : ouvre sa carte et la centre (si elle a une position). Pendant le suivi d'un
        jeu en marche, une sélection DÉJÀ montrée ne rouvre pas sa carte (elle détournerait le suivi à chaque retour
        sur le sous-onglet) ; une nouvelle sélection l'ouvre (choix à la main : suivi en pause)."""
        sel = self.o.selection
        p = self.don.positions.get(sel) if self.don and sel is not None else None
        deja, self._sel_montree = sel == self._sel_montree, sel
        if p is None or (deja and self.suivi.actif and self.suivi.cible_jeu is not None):
            self.remplir()
            return
        if p.carte in [k for k, _g, _t in CC.cartes_de_zone(self.o.modele, self.don, self.o.filtre())]:
            self.ouvrir_carte(p.carte, (p.x, p.y) if p.placee else None)
            mq = next((x for x in self.marqueurs if x.genre == "boutique" and sel in x.ids), None)
            if mq is not None:                               # article d'une boutique : son panneau, sur la carte
                self.panneau = (self.carte, mq.codes)
                self._dessiner_panneau()
        else:
            self.remplir()

    def redessiner_selection(self) -> None:
        self._sel_montree = self.o.selection                 # choisie sur la carte : déjà montrée
        if self.don is not None and self.carte:
            vue = (self.canvas.xview()[0], self.canvas.yview()[0])
            self._dessiner_carte()
            self.canvas.xview_moveto(vue[0])
            self.canvas.yview_moveto(vue[1])
            self._marquer_liste()

    # ------------------------------------------------------------------ colonnes
    def _maj_compteurs(self) -> None:
        cpt = CC.compteurs(self.o.modele, self.o.filtre())
        vide = self.o.modele.sans_donnees
        for cle, lab in self.l_compteurs.items():
            lab.configure(text="–" if vide else str(cpt[cle]), fg=th.INACTIF_TEXTE if vide else lab.couleur)

    def _dessiner_legende(self) -> None:
        c, px = self.c_legende, self.th.px
        c.delete("all")
        y = px(8)
        for cle, texte in (("accessible", "cc_l_accessible"), ("partiel", "cc_l_partiel"), ("non", "cc_l_non"),
                           ("fait", "cc_l_fait"), ("indice", "cc_l_indice"), ("approx", "cc_l_approx"),
                           ("boutique", "cc_l_boutique"), ("absent", "cc_l_bt_absent"),
                           ("incertain", "cc_l_bt_incertain"), ("entree", "cc_l_entree"),
                           ("joueur", "cc_l_joueur"), ("yokai", "cc_l_yokai"), ("jour", "cc_l_yk_jour"),
                           ("nuit", "cc_l_yk_nuit")):
            r = px(5)
            x = px(8)
            if cle == "boutique":                             # maison pleine : vendeur (ses articles)
                c.create_polygon(*self._maison(x, y + px(1), r), fill=COULEURS["accessible"], outline=th.NOIR)
            elif cle == "absent":                             # maison vide : vendeur absent maintenant
                c.create_polygon(*self._maison(x, y + px(1), r), fill=COULEUR_ABSENT, outline=COULEUR_ABSENT_BORD)
            elif cle == "incertain":                          # « ? » : présence du vendeur inconnue (étal ambulant)
                c.create_polygon(*self._maison(x, y + px(1), r), fill=COULEURS["accessible"], outline=th.NOIR)
                c.create_text(x, y + px(1), text="?", fill=th.BLANC, font=self.th["badge"])
            elif cle == "entree":                             # petite maison blanche : porte du bâtiment
                c.create_polygon(*self._maison(x, y + px(1), r - px(1)), fill=th.BLANC,
                                 outline=COULEURS["accessible"], width=px(2))
            elif cle in COULEURS_MOMENT:                      # losange épinglé avec son petit rond de moment
                c.create_polygon(x, y - r, x + r, y, x, y + r, x - r, y, fill=COULEUR_YOKAI, outline=th.NOIR)
                self._rond_moment(c, x + r * 0.8, y - r * 0.8, px(3), cle)
            elif cle == "yokai":                                # losange (loupe) et triangle (errant) côte à côte
                c.create_polygon(x, y - r, x + r, y, x, y + r, x - r, y, fill=COULEUR_YOKAI, outline=th.NOIR)
                x += px(13)
                c.create_polygon(x, y - r, x + r, y + r * 0.8, x - r, y + r * 0.8, fill=COULEUR_YOKAI,
                                 outline=th.NOIR)
            elif cle == "joueur":
                c.create_oval(x - r - px(2), y - r - px(2), x + r + px(2), y + r + px(2), fill=th.BLANC,
                              outline=th.NOIR)
                c.create_oval(x - r, y - r, x + r, y + r, fill=COULEUR_JOUEUR, outline=th.NOIR)
            elif cle == "indice":
                c.create_rectangle(x - r - px(2), y - r - px(2), x + r + px(2), y + r + px(2), outline=COULEUR_INDICE,
                                   width=px(2))
                c.create_rectangle(x - r, y - r, x + r, y + r, fill=COULEURS["accessible"], outline=th.NOIR)
            elif cle == "approx":
                c.create_rectangle(x - r, y - r, x + r, y + r, fill=COULEURS["accessible"], outline=th.NOIR,
                                   dash=(3, 2))
            else:
                c.create_rectangle(x - r, y - r, x + r, y + r, fill=COULEURS[cle], outline=th.NOIR)
            c.create_text(x + px(12), y, text=self.tr(texte), anchor="w", font=self.th["petit"], fill=th.TEXTE)
            y += px(14)

    def _maj_liste(self, sur: list[CK.Check], sans: list[CK.Check]) -> None:
        a = self.liste
        a.delete(*a.get_children())
        self._maj_liste_epingle()
        for cle, texte, checks in (("sur", self.tr("cc_inconnue", n=len(sur)), sur),
                                   ("sans", self.tr("cc_sans_lieu", n=len(sans)), sans)):
            if not checks:
                continue
            a.insert("", "end", iid=cle, text=texte, open=True, tags=("titre",))
            for c in checks:
                a.insert(cle, "end", iid=f"{cle}|{c.id}", text=c.nom, tags=(c.etat,))
        self._marquer_liste()

    def _maj_liste_epingle(self) -> None:
        """En tête de la liste de droite : le Yo-kai épinglé, ses cartes (clic : ouvrir), puis ses lieux non dessinés
        (portails mystères, position inconnue, carte sans image) ; bouton « Désépingler » sous la liste."""
        a, ep, tr = self.liste, self._ep, self.o.tracker
        if ep is None:
            self.b_desepingler.grid_remove()
            return
        self.b_desepingler.grid(row=4, column=0, sticky="e", pady=(self.th.px(4), 0))
        lg, m = self.o.langue, tr.modele
        a.insert("", "end", iid="yk", open=True, tags=("yokai",),
                 text=self.tr("cc_yk_titre", nom=self.nom_epingle(), n=ep.nombre))
        for k in CC.cartes_epingle(ep, self.don):
            acces = any(p.acces is not False for p in ep.cartes[k])
            quand = CC.moment_carte(ep.cartes[k])
            a.insert("yk", "end", iid=f"ykc|{k}", tags=("accessible" if acces else "bloque",),
                     text=self.tr(TEXTES_CARTE_MOMENT.get(quand, "cc_yk_carte"), nom=P.texte_carte(lg, m, k),
                                  n=len(ep.cartes[k])))
        for cle, lieux in (("portails", ep.portails), ("sans_position", ep.sans_position),
                           ("sans_image", ep.sans_image), ("absents", ep.absents)):
            cartes = sorted({l.carte for l in lieux})
            if not cartes:
                continue
            a.insert("yk", "end", iid=f"ykx|{cle}", text=self.tr(f"cc_yk_{cle}", n=len(cartes)), open=False,
                     tags=("inconnu",))
            for k in cartes:
                a.insert(f"ykx|{cle}", "end", iid=f"ykl|{cle}|{k}", text=P.texte_carte(lg, m, k), tags=("inconnu",))
        if not a.get_children("yk"):
            a.insert("yk", "end", iid="ykx|aucun", tags=("inconnu",),
                     text=self.tr("cc_yk_a_refaire" if 0 < m.format_base < 12 else "cc_yk_aucun"))  # 12 : positions

    def _marquer_liste(self) -> None:
        sel = self.o.selection
        for p in self.liste.get_children():
            for i in self.liste.get_children(p):
                if sel is not None and i.endswith(f"|{sel}"):
                    if self.liste.selection() != (i,):
                        self._liste_auto = True
                        self.liste.selection_set(i)
                    self.liste.see(i)
                    return
        if self.liste.selection():
            self._liste_auto = True
            self.liste.selection_remove(*self.liste.selection())

    def _choisir_liste(self) -> None:
        if getattr(self, "_liste_auto", False):
            self._liste_auto = False
            return
        s = self.liste.selection()
        if s and s[0].startswith("yk"):                      # Yo-kai épinglé : une de ses cartes -> l'ouvrir
            if s[0].startswith("ykc|"):
                self.ouvrir_carte(s[0].split("|", 1)[1])
            return
        if s and "|" in s[0]:
            self.o.choisir(int(s[0].split("|", 1)[1]))

    def _icone(self, chemin: Path, gris: bool) -> tk.PhotoImage | None:
        f = Path(str(chemin).replace(".png", CC.CA.GRIS)) if gris else chemin
        cle = str(f)
        if cle not in self._icones:
            try:
                im = tk.PhotoImage(master=self.c_objets, file=cle)
                taille = self.cellule - self.th.px(6)
                if im.width() * 2 <= taille:
                    im = im.zoom(2)
                self._icones[cle] = im
            except (tk.TclError, OSError):
                return None
        return self._icones[cle]

    def _defil_objets(self, debut, fin) -> None:
        """Barre de la colonne d'objets : montrée seulement si son contenu dépasse la hauteur visible."""
        self.defil_objets.set(debut, fin)
        if float(debut) <= 0.0 and float(fin) >= 1.0:
            self.defil_objets.grid_remove()
        else:
            self.defil_objets.grid(row=1, column=1, sticky="ns")

    def _molette_objets(self, e) -> str:
        if self._hauteur_objets > self.c_objets.winfo_height():
            self.c_objets.yview_scroll(-1 * (e.delta // 120 or (1 if e.delta > 0 else -1)) * self.th.px(38), "units")
        return "break"

    def texte_objet(self, o: CC.Objet) -> str:
        """Infobulle d'une case de la colonne d'objets : la sienne (cases progressives : Trousseau du donjon,
        Miroirs progressifs), sinon « nom — reçu (×n) » / « nom — pas encore reçu »."""
        if o.bulle:
            return o.bulle
        return f"{o.nom} — " + (self.tr("cc_recu", n=o.recus) if o.recus else self.tr("cc_pas_recu"))

    def _dessiner_objets(self) -> None:
        c, px, s = self.c_objets, self.th.px, self.cellule
        c.delete("all")
        objets = CC.objets_progression(self.o.modele, self.don)
        n_chap, _cs = CC.chapitres(self.o.modele)
        cases = [(f"o{i}", o) for i, o in enumerate(objets)] + [(f"o{len(objets)}", None)]
        lignes = (len(cases) + COLONNES_OBJETS - 1) // COLONNES_OBJETS
        hauteur = max(s, lignes * s)
        # section « Objets d'évènement » (graine qui les contient) : titre et compteur, puis leurs cases
        evenement = CC.objets_evenement(self.o.modele, self.don)
        positions = [((i % COLONNES_OBJETS) * s, (i // COLONNES_OBJETS) * s) for i in range(len(cases))]
        if evenement:
            y_titre = hauteur + px(6)
            recus = sum(1 for o in evenement if o.recus > 0)
            c.create_line(px(2), y_titre, s * COLONNES_OBJETS - px(2), y_titre, fill=th.INACTIF_CONTOUR, width=px(1),
                          tags=("titre_ev",))
            c.create_text(px(2), y_titre + px(4), text=self.tr("cc_evenement"), anchor="nw", font=self.th["petit"],
                          fill=th.TEXTE, tags=("titre_ev",))
            c.create_text(s * COLONNES_OBJETS - px(2), y_titre + px(4), text=f"{recus}/{len(evenement)}", anchor="ne",
                          font=self.th["petit"], fill=th.TEXTE_DOUX, tags=("titre_ev",))
            y_ev = y_titre + px(24)
            for j, o in enumerate(evenement):
                cases.append((f"e{j}", o))
                positions.append(((j % COLONNES_OBJETS) * s, y_ev + (j // COLONNES_OBJETS) * s))
            hauteur = y_ev + ((len(evenement) + COLONNES_OBJETS - 1) // COLONNES_OBJETS) * s
        hauteur = self._dessiner_invitations(hauteur)
        hauteur = self._dessiner_pieces(hauteur)
        self._hauteur_objets = hauteur
        c.configure(scrollregion=(0, 0, s * COLONNES_OBJETS, hauteur))
        for (tag, o), (x0, y0) in zip(cases, positions):
            cx, cy = x0 + s / 2, y0 + s / 2
            if o is None:
                recu, abr, badge, nom = n_chap > 0, "Ch", f"{n_chap}/{CC.CHAPITRES_OBJECTIF}", \
                    self.tr("cc_chapitres", n=n_chap, total=CC.CHAPITRES_OBJECTIF)
                icone = CC.icone_chapitres(self.don)
            else:
                recu, abr, badge = o.recus > 0, o.abreviation, o.badge
                nom = self.texte_objet(o)
                icone = o.icone
            im = self._icone(icone, not recu) if icone else None      # sans icône : case dessinée (repli)
            if im is not None:
                c.create_image(cx, cy, image=im, tags=(tag,))
            else:
                r = s / 2 - px(4)
                th.rond_rect(c, cx - r, cy - r, cx + r, cy + r, px(5), fill=th.OR if recu else th.INACTIF_FOND,
                             outline=th.NOIR if recu else th.INACTIF_CONTOUR, width=px(1.5), tags=(tag,))
                c.create_text(cx, cy - (s * 0.17 if badge else 0), text=abr, font=self.th["bouton_petit"],
                              fill=th.NOIR if recu else th.INACTIF_TEXTE, tags=(tag,))
            if badge:
                bx, by = x0 + s - px(3), y0 + s - px(3)
                t = c.create_text(bx, by, text=badge, anchor="se", font=self.th["badge"], fill=th.BLANC, tags=(tag,))
                x1, y1, x2, y2 = c.bbox(t)
                fond = c.create_rectangle(x1 - px(2), y1, x2 + px(1), y2, fill=th.ROUGE if recu else th.INACTIF_TEXTE,
                                          outline="", tags=(tag,))
                c.tag_raise(t, fond)
            c.create_rectangle(x0, y0, x0 + s, y0 + s, outline="", fill="", tags=(tag,))
            c.tag_bind(tag, "<Enter>", lambda e, t=nom: self.info.montrer(t, e.x_root, e.y_root), add="+")
            c.tag_bind(tag, "<Leave>", lambda _e: self.info.cacher(), add="+")

    # ------------------------------------------------------------------ rubrique « Invitations »
    def _enveloppe(self, grise: bool) -> tk.PhotoImage | None:
        """Petite enveloppe au logo du mod (PNG de `ressources/`, lu une fois) ; None : fichier absent (repli dessiné)."""
        if grise not in self._enveloppes:
            n = max((t for t in TAILLES_ENVELOPPE if t <= self.th.px(16)), default=TAILLES_ENVELOPPE[0])
            nom = "invitation_%d%s.png" % (n, "_gris" if grise else "")
            self._enveloppes[grise] = th.charger_image(self.c_objets, nom)
        return self._enveloppes[grise]

    def etat_invitation(self, inv: CK.Invitation) -> tuple[str, str, str]:
        """(texte court, phrase, couleur) de l'état de l'invité d'une invitation reçue ; ("", "", "") : inconnu."""
        e = inv.etat if inv.recus > 0 else None
        if e not in COULEURS_INVITE:
            return "", "", ""
        tr = self.tr
        if e == "present" and inv.piece is not None:
            if inv.piece == 0:
                court = piece = tr("cc_inv_suite")
            else:
                court, piece = tr("cc_inv_c_chambre", n=100 + inv.piece), tr("cc_inv_chambre", n=100 + inv.piece)
            return court, tr("cc_inv_present_piece", piece=piece), COULEURS_INVITE[e]
        if e == "file" and inv.rang:
            return tr("cc_inv_c_file_n", n=inv.rang), tr("cc_inv_file_n", n=inv.rang), COULEURS_INVITE[e]
        return tr(f"cc_inv_c_{e}"), tr(f"cc_inv_{e}"), COULEURS_INVITE[e]

    def texte_infobulle_invitation(self, inv: CK.Invitation) -> str:
        texte = f"{inv.nom} — " + (self.tr("cc_recu", n=inv.recus) if inv.recus > 0 else self.tr("cc_pas_recu"))
        phrase = self.etat_invitation(inv)[1]
        return f"{texte}\n{phrase}" if phrase else texte

    def _dessiner_invitations(self, y0: int) -> int:
        """Rubrique « Invitations » sous les objets (rien si la graine n'en a pas) ; renvoie la hauteur du contenu.
        Deux à trois éléments de canevas par ligne, aucune liaison par ligne."""
        self._zone_inv, self._inv_survol = None, None
        invs = self.o.modele.invitations
        if not invs:
            return y0
        c, px, T = self.c_objets, self.th.px, self.th
        w = self.cellule * COLONNES_OBJETS
        y = y0 + px(6)
        c.create_line(px(2), y, w - px(2), y, fill=th.INACTIF_CONTOUR, width=px(1), tags=("titre_inv",))
        c.create_text(px(2), y + px(4), text=("▸ " if self.invitations_repliees else "▾ ") + self.tr("cc_invitations"),
                      anchor="nw", font=T["petit"], fill=th.TEXTE, tags=("titre_inv",))
        c.create_text(w - px(2), y + px(4), text=f"{sum(1 for i in invs if i.recus > 0)}/{len(invs)}", anchor="ne",
                      font=T["petit"], fill=th.TEXTE_DOUX, tags=("titre_inv",))
        y_liste, pas = y + px(24), px(17)
        lignes = 0 if self.invitations_repliees else len(invs)
        self._zone_inv = (y, y_liste, pas, lignes)
        cote = px(16)
        for k, inv in enumerate(invs[:lignes]):
            cy = y_liste + k * pas + pas // 2
            recu = inv.recus > 0
            im = self._enveloppe(not recu)
            if im is not None:
                c.create_image(px(2), cy, image=im, anchor="w", tags=("inv",))
            else:                                            # ressource absente : petite enveloppe dessinée
                c.create_rectangle(px(3), cy - cote * 0.3, px(1) + cote, cy + cote * 0.3, tags=("inv",),
                                   fill="#FAF0D6" if recu else th.INACTIF_FOND,
                                   outline=th.NOIR if recu else th.INACTIF_CONTOUR)
            nom = inv.yokai if len(inv.yokai) <= INVITATION_NOM_MAX else inv.yokai[:INVITATION_NOM_MAX - 1] + "…"
            c.create_text(px(6) + cote, cy, text=nom, anchor="w", font=T["petit"],
                          fill=th.TEXTE if recu else th.INACTIF_TEXTE, tags=("inv", f"inv{k}"))
            court, _phrase, couleur = self.etat_invitation(inv)
            if court:
                c.create_text(w - px(2), cy, text=court, anchor="e", font=T["petit"], fill=couleur,
                              tags=("inv", f"inv_etat{k}"))
        return y_liste + lignes * pas + px(2)

    def ligne_invitation(self, y: float):
        """Ligne de la rubrique à l'ordonnée `y` du contenu : rang d'une invitation, "titre", ou None."""
        if self._zone_inv is None:
            return None
        y_titre, y_liste, pas, lignes = self._zone_inv
        if y_titre <= y < y_liste:
            return "titre"
        k = int((y - y_liste) // pas) if y >= y_liste else -1
        return k if 0 <= k < lignes else None

    def _survol_invitations(self, e) -> None:
        k = self.ligne_invitation(self.c_objets.canvasy(e.y))
        if k == self._inv_survol:
            return
        self._inv_survol = k
        if k is None:
            if self._inv_texte and self.info.texte == self._inv_texte:   # pas l'infobulle d'une case d'objet
                self.info.cacher()
            self._inv_texte = ""
            return
        invs = self.o.modele.invitations
        self._inv_texte = self.tr("cc_inv_aide_reception" if self.o.modele.invitations_reception
                                  else "cc_inv_aide") if k == "titre" else \
            (self.texte_infobulle_invitation(invs[k]) if k < len(invs) else "")
        self.info.montrer(self._inv_texte, e.x_root, e.y_root)

    def _clic_invitations(self, e) -> None:
        if self.ligne_invitation(self.c_objets.canvasy(e.y)) == "titre":
            self.basculer_invitations()

    def basculer_invitations(self) -> None:
        """Replie ou déplie la liste (le titre et son compteur restent) ; le défilement suit la nouvelle hauteur."""
        self.invitations_repliees = not self.invitations_repliees
        self.info.cacher()
        self._dessiner_objets()
        self._defil_objets(*self.c_objets.yview())

    # ------------------------------------------------------------------ rubrique « Pièces spéciales » (V3, lot 20)
    def nom_famille_pieces(self, f: CK.FamillePieces) -> str:
        return f.nom or self.tr("cc_pc_regions")

    def texte_infobulle_pieces(self, f: CK.FamillePieces, y) -> str:
        tr = self.tr
        nom = self.nom_famille_pieces(f)
        if y is None:
            if f.genre == "regions":
                return tr("cc_pc_regions_aide", n=f.recues, total=f.total)
            lignes = [tr("cc_pc_recues", piece=nom, n=f.recues, total=f.total)]
            if f.genre == "choix":
                lignes.append(tr("cc_pc_choix") if any(not x.ami for x in f.yokai) else tr("cc_pc_complet"))
            elif f.genre == "unique":
                lignes.append(tr("cc_pc_yk_unique", yokai=f.yokai[0].nom, piece=nom)
                              if any(not x.ami for x in f.yokai) else tr("cc_pc_complet"))
            else:
                s = f.suivant
                lignes.append(tr("cc_pc_prochaine", yokai=s.nom) if s is not None else tr("cc_pc_complet"))
                lignes.append(tr("cc_pc_ordre_graine" if f.cle == "piece_5_etoiles" else "cc_pc_ordre_jeu"))
            return "\n".join(lignes)
        if y.ami:
            return tr("cc_pc_yk_ami", yokai=y.nom)
        if f.genre == "regions":
            return tr("cc_pc_yk_region", yokai=y.nom, piece=y.piece,
                      etat=tr("cc_pc_region_recue" if y.piece_recue else "cc_pc_region_pas_recue"))
        if f.genre == "choix":
            return tr("cc_pc_yk_choix", yokai=y.nom, piece=nom)
        if f.genre == "unique":
            return tr("cc_pc_yk_unique", yokai=y.nom, piece=nom)
        if y.suivant:
            return tr("cc_pc_yk_suivant", yokai=y.nom, piece=nom)
        return tr("cc_pc_yk_rang", yokai=y.nom, piece=nom, k=y.rang)

    def cases_pieces(self) -> list[tuple]:
        """Cases de la grille d'icônes de la rubrique (lot 21), dans l'ordre : (clé de l'objet, nom de la pièce,
        reçues, total, famille, Yo-kai ou None). Une case par pièce : les 9 pièces régionales ont chacune la leur."""
        out = []
        for f in getattr(self.o.modele, "pieces", None) or ():
            if f.genre == "regions":
                out += [(y.piece_cle, y.piece, 1 if y.piece_recue else 0, 1, f, y) for y in f.yokai]
            else:
                out.append((f.cle, f.nom, f.recues, f.total, f, None))
        return out

    def texte_infobulle_case_pieces(self, case: tuple) -> str:
        """Infobulle d'une case de la grille : la pièce et son compte, puis ce que la liste dit de la famille."""
        _cle, nom, recues, total, f, y = case
        if total > 1:
            tete = self.tr("cc_pc_case", piece=nom, n=recues, total=total)
        else:
            tete = self.tr("cc_pc_case_une" if recues else "cc_pc_case_aucune", piece=nom)
        suite = self.texte_infobulle_pieces(f, y).split("\n")
        return "\n".join([tete] + (suite[1:] if y is None else suite))

    def _dessiner_cases_pieces(self, y0: int) -> int:
        """Grille d'icônes des pièces (image du jeu extraite chez le joueur, grise tant que la pièce n'est pas
        reçue ; case dessinée si l'icône manque) avec le nombre reçu ; renvoie l'ordonnée du bas. Aucune liaison par
        case : la case se déduit de la position du pointeur (`case_pieces`)."""
        c, px, s = self.c_objets, self.th.px, self.cellule
        cases = self.cases_pieces()
        self._cases_pieces, self._grille_pieces = cases, (y0, len(cases))
        for i, (cle, nom, recues, total, _f, _y) in enumerate(cases):
            x0, yc = (i % COLONNES_OBJETS) * s, y0 + (i // COLONNES_OBJETS) * s
            cx, cy = x0 + s / 2, yc + s / 2
            recu = recues > 0
            chemin = self.don.icones.get(cle) if self.don is not None else None
            im = self._icone(chemin, not recu) if chemin else None
            if im is not None:
                # (une pièce à compteur : icône remontée d'un cran, le compteur en bas de case la couvre moins)
                c.create_image(cx, cy - (px(6) if total > 1 else 0), image=im, tags=("pcg", f"pcg{i}"))
            else:
                r = s / 2 - px(4)
                th.rond_rect(c, cx - r, cy - r, cx + r, cy + r, px(5), fill=th.OR if recu else th.INACTIF_FOND,
                             outline=th.NOIR if recu else th.INACTIF_CONTOUR, width=px(1.5), tags=("pcg", f"pcg{i}"))
                c.create_text(cx, cy - (s * 0.17 if total > 1 else 0), text=CC.abreviation(nom),
                              font=self.th["bouton_petit"], fill=th.NOIR if recu else th.INACTIF_TEXTE,
                              tags=("pcg", f"pcg{i}"))
            if total > 1:                                        # nombre de pièces reçues, sur le nombre de la graine
                t = c.create_text(x0 + s - px(3), yc + s - px(3), text=f"{recues}/{total}", anchor="se",
                                  font=self.th["badge"], fill=th.BLANC, tags=("pcg", f"pcg_n{i}"))
                x1, y1, x2, y2 = c.bbox(t)
                fond = c.create_rectangle(x1 - px(2), y1, x2 + px(1), y2, outline="", tags=("pcg",),
                                          fill=th.ROUGE if recu else th.INACTIF_TEXTE)
                c.tag_raise(t, fond)
        return y0 + ((len(cases) + COLONNES_OBJETS - 1) // COLONNES_OBJETS) * s

    def case_pieces(self, x: float, y: float):
        """Rang de la case de la grille d'icônes au point (x, y) du contenu, ou None."""
        if self._grille_pieces is None:
            return None
        y0, n = self._grille_pieces
        s = self.cellule
        if y < y0 or x < 0 or x >= s * COLONNES_OBJETS:
            return None
        i = int((y - y0) // s) * COLONNES_OBJETS + int(x // s)
        return i if 0 <= i < n else None

    def _dessiner_pieces(self, y0: int) -> int:
        """Rubrique « Pièces spéciales » sous les invitations (rien si la graine n'a pas l'option) ; renvoie la
        hauteur du contenu. Sous le titre : la grille d'icônes des pièces avec le nombre reçu (lot 21). Les Yo-kai
        qu'elles donnent ne sont plus listés ici (retour du gros test V3) : leurs checks « Ami : <nom> » portent le
        rang dans l'ordre, « → prochain » et la pièce (`VueChecks.mention_ami`). Aucune liaison par case."""
        self._zone_pieces, self._pc_survol = None, None
        self._grille_pieces, self._cases_pieces = None, []
        familles = getattr(self.o.modele, "pieces", None) or ()
        if not familles:
            return y0
        c, px, T = self.c_objets, self.th.px, self.th
        w = self.cellule * COLONNES_OBJETS
        y = y0 + px(6)
        c.create_line(px(2), y, w - px(2), y, fill=th.INACTIF_CONTOUR, width=px(1), tags=("titre_pc",))
        c.create_text(px(2), y + px(4), text=self.tr("cc_pieces"), anchor="nw", font=T["petit"], fill=th.TEXTE,
                      tags=("titre_pc",))
        c.create_text(w - px(2), y + px(4), anchor="ne", font=T["petit"], fill=th.TEXTE_DOUX, tags=("titre_pc",),
                      text=f"{sum(f.recues for f in familles)}/{sum(f.total for f in familles)}")
        y_grille = y + px(24)
        self._zone_pieces = (y, y_grille)
        return self._dessiner_cases_pieces(y_grille) + px(2)

    def ligne_pieces(self, y: float):
        """"titre" si l'ordonnée `y` du contenu est sur le titre de la rubrique, sinon None."""
        if self._zone_pieces is None:
            return None
        y_titre, y_grille = self._zone_pieces
        return "titre" if y_titre <= y < y_grille else None

    def _survol_pieces(self, e) -> None:
        xc, yc = self.c_objets.canvasx(e.x), self.c_objets.canvasy(e.y)
        k = self.ligne_pieces(yc)
        if k is None and self._zone_pieces is not None:
            i = self.case_pieces(xc, yc)                    # grille d'icônes (lot 21)
            k = ("case", i) if i is not None else None
        if k == self._pc_survol:
            return
        self._pc_survol = k
        if k is None:
            if self._pc_texte and self.info.texte == self._pc_texte:    # pas l'infobulle d'une autre rubrique
                self.info.cacher()
            self._pc_texte = ""
            return
        if k == "titre":
            self._pc_texte = self.tr("cc_pc_aide")
        else:
            self._pc_texte = self.texte_infobulle_case_pieces(self._cases_pieces[k[1]])
        self.info.montrer(self._pc_texte, e.x_root, e.y_root)

    def _dessiner_objectif(self) -> None:
        c, px = self.c_objectif, self.th.px
        c.delete("all")
        w = int(c.cget("width"))
        n, cs = CC.chapitres(self.o.modele)
        th.rond_rect(c, px(1), px(1), w - px(1), px(90), px(8), fill=th.FOND, outline=th.OR, width=px(2))
        R = px(15)
        th.dessiner_embleme(c, px(8) + R, px(8) + R + px(4), R, px, "embleme")
        c.create_text(px(14) + 2 * R, px(8), text=self.tr("cc_objectif"), anchor="nw", font=self.th["petit"],
                      fill=th.TEXTE_DOUX)
        md = getattr(self.o.modele, "medaillium", None)
        if md:
            # V3, lot 18 : objectif « compléter le Médaillium » : entrées remplies / seuil (« ? » tant que le
            # Médaillium de la partie n'a pas été lu), chapitres à la suite ; au survol : ce qui manque sans check
            acquis = md["acquis"]
            c.create_text(px(14) + 2 * R, px(24), text=self.tr("cc_medaillium_titre"), anchor="nw",
                          font=self.th["bouton_petit"], fill=th.NOIR, tags=("md",))
            c.create_text(px(14) + 2 * R, px(38), anchor="nw", font=self.th["carte"], tags=("md",),
                          text="%s/%d   %s %d/%d" % ("?" if acquis is None else acquis, md["seuil"],
                                                   self.tr("cc_medaillium_chapitres"), n, CC.CHAPITRES_OBJECTIF),
                          fill=th.INACTIF_TEXTE if acquis is None
                          else th.ROUGE if acquis < md["seuil"] else "#1D7A3C")
            texte = CC.texte_medaillium(md, self.tr)
            c.tag_bind("md", "<Enter>", lambda e, t=texte: self.info.montrer(t, e.x_root, e.y_root), add="+")
            c.tag_bind("md", "<Leave>", lambda _e: self.info.cacher(), add="+")
        else:
            c.create_text(px(14) + 2 * R, px(24), text=self.tr("cc_chapitres_titre"), anchor="nw",
                          font=self.th["bouton_petit"], fill=th.NOIR)
            c.create_text(px(14) + 2 * R, px(38), text=f"{n}/{CC.CHAPITRES_OBJECTIF}", anchor="nw",
                          font=self.th["carte"], fill=th.INACTIF_TEXTE if self.o.modele.sans_donnees
                          else th.ROUGE if n < CC.CHAPITRES_OBJECTIF else "#1D7A3C")
        # un carré par check « chapitre N terminé » (cachés s'ils ne sont pas des locations de la graine)
        taille = min(px(14), (w - px(16)) // max(1, len(cs)) - px(2)) if cs else px(14)
        x = px(8)
        for i, ch in enumerate(cs):
            etat = "fait" if ch.etat == "fait" else ("accessible" if ch.etat == "accessible" else "non")
            tag = f"ch{i}"
            c.create_rectangle(x, px(62), x + taille, px(62) + taille, fill=COULEURS[etat],
                               outline=COULEUR_INDICE if ch.indice and ch.etat != "fait" else th.BLANC,
                               width=px(2) if ch.indice else 1, tags=(tag,))
            texte = f"{ch.nom} — {self.o.texte_etat(ch)}"
            contenu = self.o.texte_contenu(ch)
            if contenu:
                texte += f" — {contenu}"
            c.tag_bind(tag, "<Enter>", lambda e, t=texte: self.info.montrer(t, e.x_root, e.y_root), add="+")
            c.tag_bind(tag, "<Leave>", lambda _e: self.info.cacher(), add="+")
            c.tag_bind(tag, "<ButtonRelease-1>", lambda _e, i=ch.id: self.o.choisir(i), add="+")
            x += taille + px(2)
