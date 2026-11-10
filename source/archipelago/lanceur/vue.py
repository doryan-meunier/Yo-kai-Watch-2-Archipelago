"""Fenêtre tkinter du lanceur (vue seulement : toute la logique est dans `logique.py`).

Les opérations longues (vérification de la ROM, installation, démarrage) tournent dans un fil séparé ; leur
résultat revient à la fenêtre par une file lue toutes les 100 ms (tkinter n'est pas sûr entre fils).
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from . import fenetre_amitie as FA
from . import fenetre_loupe as FL
from . import fenetre_derniers_objets as FDO
from . import premier_plan as PP
from . import musique_option as MO
from . import logique as L
from . import theme as th
from . import tracker as TK
from .presentation import (etat_connexion, ligne_melange, ligne_sauvegarde, ligne_suivi, lignes_session, niveau_gdb,
                           niveau_mod,
                           niveau_rom,
                           niveau_version_azahar, niveaux_session, texte_gdb, texte_mod, texte_msg,
                           texte_version_azahar)
from .textes import langue_systeme, t
from .vue_checks import OngletChecks
from .vue_apparence import OngletApparence, SourceImport
from .vue_reglages_zakuro import OngletReglagesZakuro
from .vue_texte import OngletTexte
from .vue_yokai import OngletYokai


def ouvrir(chemin: Path) -> None:
    if os.name == "nt":
        os.startfile(str(chemin))                        # noqa: S606 - dossier ou fichier local
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(chemin)])
    else:
        subprocess.Popen(["xdg-open", str(chemin)])


class Fenetre:
    def __init__(self, racine: tk.Tk, lanceur: L.Lanceur):
        self.racine, self.l = racine, lanceur
        self.langue = lanceur.langue() or langue_systeme()
        self.file: queue.Queue = queue.Queue()
        self.occupe = False
        self.session: L.Session | None = None
        self.lancee = False
        self.suivi_demarrage = False                     # démarrage du client de suivi en cours (fil de fond)
        self.etat_az: L.EtatAzahar | None = None
        self.etat_mod: L.EtatMod | None = None
        self.rom_ok = False
        self.page = "jeu"
        self.sous_reglages = "jeu"                       # sous-onglet de « Réglages » : « jeu », « apparence » ou « zakuro »
        self.app_personnage = "nathan"                   # personnage montré dans « Apparence » (gardé au changement de langue)
        racine.bind("<Control-Tab>", self.onglet_suivant)
        racine.bind("<Control-f>", self.rechercher)
        racine.bind("<Control-F>", self.rechercher)
        self.v = {k: tk.StringVar(racine) for k in (
            "rom", "rom_etat", "azahar", "azahar_version", "gdb", "mod", "message", "s1", "s2", "s3", "s4", "versions",
            "cx_etat", "cx_suivi", "cx_melange", "maj", "maj_notes", "maj_raison")}
        self.maj_annonce = None                          # mise à jour annoncée (maj.py)
        self.maj_refus: L.Msg | None = None
        self.maj_var = tk.BooleanVar(racine, value=bool(lanceur.config.maj_verifier))
        self._melange_sig = None                         # (taille, date) de rando_yokai.json déjà affiché
        self._melange_lu: dict | None = None
        # connexion Archipelago (carte 4) : formulaire gardé d'une construction à l'autre (changement de langue)
        self.cx = {k: tk.StringVar(racine) for k in ("serveur", "slot", "mdp")}
        self.cx_memoriser = tk.BooleanVar(racine, value=True)
        self.cx_modifie = self.cx_mdp_touche = self.cx_mdp_connu = self.cx_mdp_visible = False
        self.cx_plus_recente = None                      # configuration du disque plus récente que le formulaire modifié
        self._cx_remplissage = False
        for k, var in self.cx.items():
            var.trace_add("write", lambda *_a, k=k: self.cx_saisie(k))
        self.v["cx_etat"].trace_add("write", lambda *_a: self.replanifier())   # hauteur de la carte 4
        self.remplir_connexion(lanceur.config)
        # fenêtre d'amitié en combat (option, fenetre_amitie.py) : créée avant la carte « Paramètres du jeu » (onglet
        # « Réglages ») qui porte sa case
        self.amitie_var = tk.BooleanVar(racine, value=bool(lanceur.config.amitie_fenetre))
        self.amitie = FA.Suivi(racine, lanceur.stockage.dossier, self.langue, actif=self.amitie_var.get(),
                               pos=lanceur.config.amitie_fenetre_pos,
                               memoriser_pos=lambda x, y: FA.memoriser(lanceur, amitie_fenetre_pos=f"{x},{y}"))
        # fenêtre de la loupe (option, fenetre_loupe.py) : point visé par le radar de la montre, sur le terrain
        self.loupe_var = tk.BooleanVar(racine, value=bool(lanceur.config.loupe_fenetre))
        self.loupe = FL.SuiviLoupe(racine, lanceur.stockage.dossier, self.langue, actif=self.loupe_var.get(),
                                   pos=lanceur.config.loupe_fenetre_pos,
                                   memoriser_pos=lambda x, y: FA.memoriser(lanceur, loupe_fenetre_pos=f"{x},{y}"))
        # fenêtre des derniers objets reçus / envoyés (option, fenetre_derniers_objets.py), même carte
        self.objets_var = tk.BooleanVar(racine, value=bool(lanceur.config.objets_fenetre))
        self.objets = FDO.Suivi(racine, lanceur.stockage.dossier, self.langue, actif=self.objets_var.get(),
                                pos=lanceur.config.objets_fenetre_pos, delai=lanceur.config.objets_fenetre_delai,
                                memoriser_pos=lambda x, y: FA.memoriser(lanceur, objets_fenetre_pos=f"{x},{y}"))
        # « Garder le lanceur au premier plan » (option, premier_plan.py) : réappliquée ici, case dans la même carte
        self.premier_plan = PP.PremierPlan(racine, lanceur, (self.amitie, self.loupe, self.objets))
        self.musique = MO.OptionMusique(racine, lanceur)   # « Musique aléatoire » (musique_option.py), même carte
        self.construire()
        self.rafraichir(verifier_rom=True)
        # suivi seul : le lanceur ouvert, le client suit la partie sur le serveur (sans le jeu) si la connexion est
        # enregistrée ; il s'arrête à la fermeture du lanceur (lanceur.pid), sauf jeu en cours
        lanceur.enregistrer_presence()
        if lanceur.config.configuree:
            self.demarrer_suivi()
        racine.protocol("WM_DELETE_WINDOW", self.fermer)
        racine.after(100, self.lire_file)
        racine.after(1000, self.suivre)
        fin_maj = lanceur.resultat_maj()                 # mise à jour faite avant cette ouverture
        if fin_maj is not None:
            self.message(texte_msg(self.langue, fin_maj))
        racine.after(DELAI_NETTOYAGE_MAJ, lambda: threading.Thread(target=lanceur.nettoyer_maj, daemon=True).start())
        if lanceur.maj_verifier_actif():
            racine.after(DELAI_VERIFICATION_MAJ, self.chercher_maj)

    # ------------------------------------------------------------------ construction
    def tr(self, cle: str, **p) -> str:
        return t(self.langue, cle, **p)

    def construire(self) -> None:
        """Fenêtre dessinée par `theme.Scene` : bandeau, trois cartes (ROM, Azahar, mod), « Jouer », carte d'état,
        pied. Mêmes variables, boutons et commandes que la logique attend ; aucun comportement ici."""
        for w in self.racine.winfo_children():
            w.destroy()
        self.racine.title(self.tr("titre"))
        self.racine.configure(bg=th.FOND)
        self.theme = T = th.Theme(self.racine)
        px = T.px
        self.racine.minsize(px(560), px(360))
        sc = self.scene = th.Scene(self.racine, T)
        self.boutons: list[th.Pilule] = []
        self.pastilles: dict[str, th.Pastille] = {}
        sc.entete(self.tr("titre"), self.tr("sous_titre"), self.tr("langue"), self.changer_langue)
        self.onglets = sc.onglets([("jeu", self.tr("onglet_jeu")), ("yokai", self.tr("onglet_yokai")),
                                   ("checks", self.tr("onglet_checks")), ("texte", self.tr("onglet_texte")),
                                   ("reglages", self.tr("onglet_reglages"))],
                                  self.changer_onglet)
        sc.page_construction = "jeu"

        def bouton(parent, cle, commande, genre="normal"):
            b = th.Pilule(parent, T, self.tr(cle), commande, genre=genre)
            self.boutons.append(b)
            return b

        def ligne(corps, r, cle, commande=None, chemin=False, bouton_cle="choisir"):
            """Une ligne de carte : pastille, texte (variable `cle`), bouton facultatif à droite."""
            p = th.Pastille(corps, T)
            haut = px(4) + max(0, (T["texte"].metrics("linespace") - p.d) // 2)
            p.grid(row=r, column=0, sticky="nw", pady=(haut, 0), padx=(0, px(8)))
            self.pastilles[cle] = p
            if chemin:
                lab = th.LabelChemin(corps, self.v[cle], T["texte"], bg=th.BLANC, fg=th.TEXTE_DOUX)
            else:
                lab = tk.Label(corps, textvariable=self.v[cle], font=T["texte"], bg=th.BLANC, fg=th.TEXTE,
                               justify="left", anchor="w")
            b = None
            reserve = p.d + px(12)
            if commande is not None:
                lab.grid(row=r, column=1, sticky="w", pady=(px(3), px(2)))
                b = bouton(corps, bouton_cle, commande)
                b.grid(row=r, column=2, sticky="e", padx=(px(10), 0))
                reserve += b.winfo_reqwidth() + px(10)
            else:
                lab.grid(row=r, column=1, columnspan=2, sticky="w", pady=(px(3), px(2)))
            sc.texte_extensible(lab, reserve)
            if not chemin:                                  # ligne vide (Azahar absent) : masquée
                widgets = [w for w in (p, lab, b) if w is not None]

                def montrer(*_):
                    try:
                        for w in widgets:
                            w.grid() if self.v[cle].get() else w.grid_remove()
                    except tk.TclError:
                        pass
                self.v[cle].trace_add("write", montrer)
                montrer()
            return b

        # 1. ROM
        c = sc.carte(self.tr("rom"))
        ligne(c, 0, "rom", self.choisir_rom, chemin=True)
        ligne(c, 1, "rom_etat")
        # 2. Azahar
        c = sc.carte(self.tr("emulateur"))
        ligne(c, 0, "azahar", self.choisir_azahar, chemin=True)
        ligne(c, 1, "azahar_version")
        self.b_gdb = ligne(c, 2, "gdb", self.activer_gdb, bouton_cle="activer")
        # 3. Mod
        c = sc.carte(self.tr("mod"))
        ligne(c, 0, "mod")
        bm = tk.Frame(c, bg=th.BLANC)
        bm.grid(row=1, column=1, columnspan=2, sticky="w", pady=(px(6), 0))
        for i, (cle, cmd, genre) in enumerate((("installer", self.installer, "or"),
                                               ("reparer", self.reparer, "normal"),
                                               ("desinstaller", self.desinstaller, "normal"))):
            bouton(bm, cle, cmd, genre).grid(row=0, column=i, padx=(0 if i == 0 else px(2), 0))
        self.b_installer, self.b_reparer, self.b_desinstaller = self.boutons[-3:]
        # mise à jour du lanceur (maj.py) : lignes vides, donc masquées, tant que rien n'est annoncé
        self.b_maj = ligne(c, 2, "maj", self.cliquer_maj, bouton_cle="maj_bouton_lien")   # libellé le plus long
        ligne(c, 3, "maj_notes")
        ligne(c, 4, "maj_raison")
        # 4. Connexion Archipelago (colonne de droite, au-dessus de « Jouer »)
        c = sc.carte(self.tr("connexion"), colonne="d")
        form = tk.Frame(c, bg=th.BLANC)
        form.grid(row=0, column=0, columnspan=3, sticky="ew")
        form.columnconfigure(1, weight=1)
        libelles = (("serveur", "cx_serveur"), ("slot", "cx_slot"), ("mdp", "cx_mdp"))
        col_libelle = max(T["texte"].measure(self.tr(cle)) for _k, cle in libelles) + px(10)
        self.cx_champs: dict[str, th.Champ] = {}
        for r, (k, cle) in enumerate(libelles):
            tk.Label(form, text=self.tr(cle), font=T["texte"], bg=th.BLANC, fg=th.TEXTE, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, px(10)), pady=px(3))
            ch = th.Champ(form, T, self.cx[k], masque=k == "mdp" and not self.cx_mdp_visible)
            ch.grid(row=r, column=1, columnspan=1 if k == "mdp" else 2, sticky="ew", pady=px(3))
            ch.entree.bind("<Return>", lambda _e: self.enregistrer_connexion())
            ch.entree.bind("<KP_Enter>", lambda _e: self.enregistrer_connexion())
            ch.entree.bind("<Escape>", lambda _e: self.annuler_connexion())
            self.cx_champs[k] = ch
        l_voir = max(T["bouton_petit"].measure(self.tr(k)) for k in ("cx_afficher", "cx_masquer")) + 2 * px(10)
        self.b_cx_voir = th.Pilule(form, T, self.tr("cx_masquer" if self.cx_mdp_visible else "cx_afficher"),
                                   self.basculer_mdp, genre="clair", police="bouton_petit", padx=10, pady=3,
                                   largeur_min=l_voir)
        self.b_cx_voir.grid(row=2, column=2, sticky="e", padx=(px(6), 0))
        self.boutons.append(self.b_cx_voir)
        self.cx_indice = tk.Label(form, text=self.tr("cx_mdp_indice"), font=T["petit"], bg=th.BLANC,
                                  fg=th.TEXTE_DOUX, justify="left", anchor="w")
        self.cx_indice.grid(row=3, column=1, columnspan=2, sticky="w", pady=(0, px(2)))
        sc.texte_extensible(self.cx_indice, col_libelle + px(4))
        bas = tk.Frame(form, bg=th.BLANC)
        bas.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(px(4), px(2)))
        self.b_cx_memo = th.Bascule(bas, T, self.tr("cx_memoriser"), self.cx_memoriser, commande=self.cx_bascule)
        self.b_cx_memo.pack(side="left")
        self.boutons.append(self.b_cx_memo)
        self.b_cx_enregistrer = bouton(bas, "cx_enregistrer", self.enregistrer_connexion, "or")
        self.b_cx_enregistrer.pack(side="right")
        ligne(c, 1, "cx_etat")
        # suivi seul : client connecté au serveur sans le jeu (Checks, Discussion, Yo-kai)
        self.b_cx_suivi = ligne(c, 2, "cx_suivi", self.basculer_suivi, bouton_cle="cx_deconnecter")
        # V3, lot M1 : le mélange des Yo-kai est-il appliqué ? (rando_yokai.json du client ; aucune lecture du jeu)
        ligne(c, 3, "cx_melange")
        self._melange_sig = None
        self.maj_indice()
        # Jouer
        self.b_jouer = th.Pilule(sc.c, T, self.tr("jouer").upper(), self.jouer, genre="primaire", fond=th.FOND,
                                 police="jouer", padx=34, pady=7, icone="jouer", largeur_min=px(250))
        self.boutons.append(self.b_jouer)
        sc.centre(self.b_jouer)
        # État
        c = sc.carte(self.tr("etat"), colonne="d")
        for i, k in enumerate(("s1", "s2", "s3")):
            ligne(c, i, k)
        ligne(c, 3, "s4")                                # sauvegarde chargée (liée / non liée : nouvelle partie)
        self.cadre_message = msg = tk.Frame(c.master, bg=th.CYAN)     # en bas de la carte
        lab = tk.Label(msg, textvariable=self.v["message"], font=T["texte"], bg=th.CYAN_PALE, fg=th.CYAN_TEXTE,
                       justify="left", anchor="w", padx=px(10), pady=px(6))
        lab.pack(fill="x", padx=(px(4), 0))
        sc.texte_extensible(lab, px(24))
        # onglet « Yo-kai » (tracker, vue_yokai.py)
        sc.page_construction = "yokai"
        # données des onglets cachés : lues à leur ouverture (ou au premier contrôle des fichiers), pas au démarrage
        self.tracker = OngletYokai(sc, T, self.langue, self.l.stockage.dossier, rom=lambda: self.l.config.rom,
                                   paresseux=True, epingle=self.l.config.yokai_epingle,
                                   memoriser_epingle=self._changer_epingle)
        sc.plein(self.tracker.cadre)
        # onglet « Checks » (tracker des locations, vue_checks.py)
        sc.page_construction = "checks"
        self.checks = OngletChecks(sc, T, self.langue, self.l.stockage.dossier, ouvrir=ouvrir,
                                   rom=lambda: self.l.config.rom, choisir_rom=self.choisir_rom,
                                   generer_cartes=self.l.generer_cartes, paresseux=True,
                                   suivre=self.l.config.carte_suivre, memoriser_suivi=self.l.changer_suivi_carte,
                                   epingle=self.tracker)
        sc.plein(self.checks.cadre)
        # onglet « Discussion » (serveur Archipelago, à la TextClient, vue_texte.py)
        sc.page_construction = "texte"
        self.texte = OngletTexte(sc, T, self.langue, self.l.stockage.dossier)
        sc.plein(self.texte.cadre)
        # onglet « Réglages » : sous-onglet « Paramètres du jeu » (options du lanceur valables pour tous les
        # émulateurs), « Apparence » (vue_apparence.py : tenue du personnage principal, aperçu calculé à l'ouverture
        # du sous-onglet), puis « Zakuro » (vue_reglages_zakuro.py : settings.toml lu à la première ouverture du
        # sous-onglet)
        sc.sous_onglets("reglages", [("jeu", self.tr("rz_sous_jeu")), ("apparence", self.tr("app_sous")),
                                     ("zakuro", self.tr("rz_sous_zakuro"))],
                        self.changer_sous_reglages, choisi=self.sous_reglages)
        sc.page_construction = "reglages/jeu"
        c = sc.carte(self.tr("rz_jeu_titre"))
        self.b_amitie = FA.case_option(c, T, self.langue, self.amitie_var, self.basculer_amitie, ligne=0, scene=sc)
        self.amitie.changer_langue(self.langue)
        self.b_loupe = FL.case_option(c, T, self.langue, self.loupe_var, self.basculer_loupe, ligne=2, scene=sc)
        self.loupe.changer_langue(self.langue)
        self.b_objets = FDO.case_option(c, T, self.langue, self.objets_var, self.basculer_objets,
                                        self.l.config.objets_fenetre_delai, self.changer_delai_objets, ligne=4,
                                        scene=sc)
        self.objets.changer_langue(self.langue)
        note = tk.Label(c, text=self.tr("rz_jeu_note"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                        justify="left", anchor="w")
        self.b_premier_plan = self.premier_plan.case_option(c, T, self.langue, ligne=7, scene=sc)
        self.b_musique = self.musique.case_option(c, T, self.langue, ligne=9, scene=sc)
        self.b_maj_case = None
        if self.l.maj_possible():                        # sans source (ou depuis le dépôt) : rien n'est affiché
            self.b_maj_case = th.Bascule(c, T, self.tr("maj_case"), self.maj_var, commande=self.basculer_maj)
            self.b_maj_case.grid(row=11, column=0, columnspan=3, sticky="w", pady=(px(8), 0))
            aide = tk.Label(c, text=self.tr("maj_case_aide"), font=T["petit"], bg=th.BLANC, fg=th.TEXTE_DOUX,
                            justify="left", anchor="w")
            aide.grid(row=12, column=0, columnspan=3, sticky="w", padx=(px(28), 0), pady=(0, px(2)))
            sc.texte_extensible(aide, px(32))
            self.boutons.append(self.b_maj_case)
        note.grid(row=20, column=0, columnspan=3, sticky="w", pady=(px(8), 0))
        sc.texte_extensible(note, px(4))
        sc.page_construction = "reglages/apparence"
        if getattr(self, "apparence", None) is not None:
            self.app_personnage = self.apparence.personnage
        self.apparence = OngletApparence(sc, T, self.langue, dossier=self.l.stockage.dossier,
                                         reglage=self.l.reglage_apparence, memoriser=self.l.changer_apparence,
                                         etat=self.l.etat_apparence, rom=lambda: self.l.config.rom or "",
                                         personnage=self.app_personnage, importeur=SourceImport(
                                             manifeste=self.l.import_apparence, actif=self.l.import_apparence_actif,
                                             changer_actif=self.l.changer_import_apparence,
                                             importer=self.l.importer_apparence,
                                             retirer=self.l.retirer_import_apparence))
        sc.page_construction = "reglages/zakuro"
        self.reglages = OngletReglagesZakuro(
            sc, T, self.langue, zakuro_fourni=lambda: self.l.zakuro() is not None, emulateur=self.l.emulateur,
            zakuro_ouvert=self.l.zakuro_en_cours,
            verrou=lambda: L.config_locale.VerrouConfig(self.l.stockage.dossier / "zakuro_reglages.verrou"))
        sc.page_construction = "jeu"
        # pied
        pied = [th.Pilule(sc.c, T, self.tr(cle), cmd, genre="clair", fond=th.FOND, police="bouton_petit", padx=12,
                          pady=3) for cle, cmd in (("journaux", self.ouvrir_journaux), ("aide", self.ouvrir_aide))]
        sc.pied(pied, self.v["versions"])
        self.maj_cadre_message()
        self.maj_etat_connexion()
        self.maj_montrer()
        self.changer_onglet(self.page)

    def changer_onglet(self, page: str) -> None:
        """Onglet « Jeu » (lanceur), « Yo-kai » (tracker) ou « Checks » (locations) ; Ctrl+Tab passe au suivant, Ctrl+F
        cherche un Yo-kai (ou une location dans l'onglet « Checks »)."""
        self.page = page
        self.scene.montrer(page)
        self.tracker.activer(page == "yokai")
        self.checks.activer(page == "checks")
        self.texte.activer(page == "texte")
        self.reglages.activer(page == "reglages" and self.sous_reglages == "zakuro")
        self.apparence.activer(page == "reglages" and self.sous_reglages == "apparence")

    def changer_sous_reglages(self, sous: str) -> None:
        """Sous-onglet de « Réglages » : « jeu » (Paramètres du jeu), « apparence » (tenue du personnage, aperçu
        calculé à l'ouverture) ou « zakuro » (settings.toml, lu à la première ouverture de ce sous-onglet seulement)."""
        self.sous_reglages = sous
        self.scene.montrer_sous("reglages", sous)
        self.reglages.activer(self.page == "reglages" and sous == "zakuro")
        self.apparence.activer(self.page == "reglages" and sous == "apparence")

    def onglet_suivant(self, _e=None) -> str:
        ordre = list(self.onglets)
        self.changer_onglet(ordre[(ordre.index(self.page) + 1) % len(ordre)])
        self.onglets[self.page].focus_set()
        return "break"

    def rechercher(self, _e=None) -> str:
        if self.page == "checks":
            self.checks.focus_recherche()
            return "break"
        if self.page == "texte":
            self.texte.focus_recherche()
            return "break"
        if self.page != "yokai":
            self.changer_onglet("yokai")
        self.tracker.focus_recherche()
        return "break"

    def maj_cadre_message(self) -> None:
        """Bandeau de message de la carte d'état : visible seulement s'il y a un message."""
        try:
            if self.v["message"].get():
                self.cadre_message.pack(side="bottom", fill="x", pady=(self.theme.px(10), 0))
            else:
                self.cadre_message.pack_forget()
        except tk.TclError:
            pass

    def niveau(self, cle: str, niveau: str | None) -> None:
        p = self.pastilles.get(cle)
        if p is not None:
            p.niveau(niveau)

    # ------------------------------------------------------------------ état
    def rafraichir(self, verifier_rom: bool = False) -> None:
        c = self.l.config
        self.v["rom"].set(c.rom or self.tr("aucun_fichier"))
        if verifier_rom:                                 # après le premier affichage (voir DELAI_VERIFICATION_ROM)
            self.en_fond(lambda: ("rom", self.l.verifier_rom()), self.tr("rom_verification"), bloquer=False,
                         delai=DELAI_VERIFICATION_ROM)
        self.etat_az = e = self.l.etat_azahar(rafraichir=True)
        self.v["azahar"].set(str(e.executable) if e.executable else self.tr("azahar_absent"))
        self.v["azahar_version"].set(texte_version_azahar(self.langue, e) if e.executable else "")
        self.v["gdb"].set(texte_gdb(self.langue, e) if e.executable else "")
        self.niveau("azahar", None if e.executable else "erreur")
        self.niveau("azahar_version", niveau_version_azahar(e))
        self.niveau("gdb", niveau_gdb(e))
        self.etat_mod = m = self.l.etat_mod()
        self.v["mod"].set(texte_mod(self.langue, m))
        self.niveau("mod", niveau_mod(m))
        self.apparence.maj_etat()                        # appliquée / au prochain « Jouer »
        self.v["versions"].set(self.tr("versions", lanceur=L.VERSION_LANCEUR, mod=m.version_paquet or "?",
                                       azahar=e.version or "?"))
        self.maj_session()
        self.maj_boutons()

    def maj_boutons(self) -> None:
        en_jeu = self.session is not None and self.session.azahar.poll() is None
        libre = not self.occupe and not en_jeu
        m = self.etat_mod.statut if self.etat_mod else ""
        e = self.etat_az
        etats = {
            self.b_gdb: libre and e is not None and e.gdb.statut == "inactif",
            self.b_installer: libre and self.rom_ok and m in ("non_installe", "autre_version"),
            self.b_reparer: libre and self.rom_ok and m in ("a_jour", "autre_version", "modifie"),
            self.b_desinstaller: libre and m in ("a_jour", "autre_version", "modifie"),
            self.b_jouer: libre,
            # connexion : modifiable aussi pendant la partie (le client se reconnecte)
            self.b_cx_enregistrer: not self.occupe,
            self.b_cx_memo: not self.occupe,
            self.b_cx_voir: True,
            self.b_cx_suivi: not self.occupe and self._suivi_bouton_actif,
            self.b_maj: self.maj_bouton_actif(libre),
            self.b_maj_case: True,
        }
        for b in self.boutons:
            b.state(["!disabled"] if etats.get(b, libre) else ["disabled"])

    def maj_session(self) -> None:
        s = self.l.etat_session(self.session)
        self._etat_session = s
        self.maj_suivi(s)
        for k, ligne, niv in zip(("s1", "s2", "s3"), lignes_session(self.langue, s, self.lancee),
                                 niveaux_session(s, self.lancee)):
            self.v[k].set(ligne)
            self.niveau(k, niv)
        texte, niv = ligne_sauvegarde(self.langue, s)
        if self.v["s4"].get() != texte:
            self.v["s4"].set(texte)
            self.replanifier()
        self.niveau("s4", niv)

    def suivre(self) -> None:
        self.suivre_connexion()
        if self.session is not None:
            self.maj_session()
            if self.session.azahar.poll() is not None:   # le client revient au suivi seul (ou s'arrête)
                self.session = None
                self.message(self.tr("partie_finie"))
                self.rafraichir()
        elif not self.occupe:
            self.maj_session()
        self.maj_melange()
        self.maj_suivre()
        self.maj_boutons()
        self.racine.after(1000, self.suivre)

    def maj_melange(self) -> None:
        """Ligne « Yo-kai mélangés » de la carte « Connexion » : rando_yokai.json relu seulement quand il change (taille
        ou date : un `stat` par seconde, rien de plus) ; client arrêté : l'état affiché est daté."""
        p = Path(self.l.stockage.dossier) / TK.NOM_MELANGE
        try:
            st = p.stat()
            sig = (st.st_size, st.st_mtime_ns)
        except OSError:
            sig = None
        s = getattr(self, "_etat_session", None)          # celui de maj_session (fichier d'état déjà lu)
        actif = bool(s and s.client_actif)
        if sig != self._melange_sig:
            self._melange_sig = sig
            self._melange_lu = TK.lire_json(p) if sig is not None else None
        texte, niv = ligne_melange(self.langue, self._melange_lu, actif)
        if self.v["cx_melange"].get() != texte:
            self.v["cx_melange"].set(texte)
            self.replanifier()
        self.niveau("cx_melange", niv)

    def message(self, texte: str) -> None:
        change = self.v["message"].get() != texte
        self.v["message"].set(texte)
        self.maj_cadre_message()
        if change:                                       # bandeau apparu, disparu ou d'une autre hauteur : la carte
            self.replanifier()                           # d'état (hauteur fixée par la scène) et la fenêtre suivent

    # ------------------------------------------------------------------ connexion Archipelago
    def remplir_connexion(self, c) -> None:
        """Formulaire = configuration `c` (config.json). Mot de passe : affiché (masqué) s'il est connu du lanceur
        (mémorisé) ; sinon champ vide, qui veut dire « inchangé » tant qu'on n'y touche pas."""
        self._cx_remplissage = True
        try:
            self.cx["serveur"].set(c.serveur)
            self.cx["slot"].set(c.slot)
            self.cx["mdp"].set(c.mot_de_passe)
            self.cx_memoriser.set(c.memoriser_mot_de_passe)
        finally:
            self._cx_remplissage = False
        self.cx_mdp_connu = bool(c.mot_de_passe)
        self.cx_modifie = self.cx_mdp_touche = False
        self.cx_plus_recente = None
        for ch in getattr(self, "cx_champs", {}).values():
            ch.signaler(False)
        if hasattr(self, "cx_indice"):
            self.maj_indice()
            self.maj_etat_connexion()

    def cx_saisie(self, champ: str) -> None:
        if self._cx_remplissage:
            return
        if champ == "mdp":
            self.cx_mdp_touche = True
        self.cx_modifie = True
        if champ in getattr(self, "cx_champs", {}):
            self.cx_champs[champ].signaler(False)
        self.maj_etat_connexion()

    def cx_bascule(self) -> None:
        self.cx_modifie = True
        self.maj_indice()
        self.maj_etat_connexion()

    def maj_indice(self) -> None:
        try:
            self.cx_indice.grid_remove() if self.cx_memoriser.get() else self.cx_indice.grid()
        except tk.TclError:
            pass
        self.replanifier()

    def replanifier(self) -> None:
        """Un texte de la carte a changé de hauteur : mise en page refaite (le cadre d'une carte a une hauteur fixée
        par la scène, son <Configure> ne suffit pas)."""
        sc = getattr(self, "scene", None)
        if sc is not None:                               # après le calcul des hauteurs demandées par Tk (au repos)
            self.racine.after(30, sc.planifier)

    def basculer_mdp(self) -> None:
        self.cx_mdp_visible = not self.cx_mdp_visible
        self.cx_champs["mdp"].masquer(not self.cx_mdp_visible)
        self.b_cx_voir.changer_texte(self.tr("cx_masquer" if self.cx_mdp_visible else "cx_afficher"))

    def valeurs_connexion(self) -> tuple[str, str, str | None, bool]:
        """(serveur, slot, mot de passe ou None = inchangé, mémoriser)."""
        mdp = self.cx["mdp"].get() if self.cx_mdp_touche or self.cx_mdp_connu else None
        return self.cx["serveur"].get(), self.cx["slot"].get(), mdp, bool(self.cx_memoriser.get())

    def annuler_connexion(self) -> str:
        """Échap : le formulaire reprend config.json (abandon des modifications, ou saisie arrivée du jeu)."""
        self.remplir_connexion(self.l.config)
        return "break"

    def maj_etat_connexion(self, erreur: L.Msg | list[L.Msg] | None = None) -> None:
        if erreur is not None:
            texte = " ".join(texte_msg(self.langue, m) for m in (erreur if isinstance(erreur, list) else [erreur]))
            niv = "erreur"
        else:
            texte, niv = etat_connexion(self.langue, self.l.config, modifie=self.cx_modifie,
                                        plus_recente=self.cx_plus_recente)
        self.v["cx_etat"].set(texte)
        self.niveau("cx_etat", niv)

    def signaler_connexion(self, serveur: str, slot: str, msg: L.Msg) -> None:
        """Saisie refusée : champs en rouge, raison dans la ligne d'état de la carte, focus sur le premier champ."""
        erreurs = L.valider_connexion(serveur, slot)
        for k in ("serveur", "slot"):
            self.cx_champs[k].signaler(k in erreurs)
        if erreurs:
            self.cx_champs[next(iter(erreurs))].entree.focus_set()
        self.maj_etat_connexion(list(erreurs.values()) or msg)

    def enregistrer_connexion(self) -> bool:
        if self.occupe:
            return False
        serveur, slot, mdp, memo = self.valeurs_connexion()
        try:
            m = self.l.enregistrer_connexion(serveur, slot, mdp, memo)
        except L.ErreurLanceur as e:
            self.signaler_connexion(serveur, slot, e.msg)
            return False
        self.remplir_connexion(self.l.config)
        self.message(texte_msg(self.langue, m))
        if not self.l.client_en_cours(self.session):    # connexion enregistrée : le suivi démarre (sans le jeu)
            self.demarrer_suivi()
        return True

    def suivre_connexion(self) -> None:
        """Saisie plus récente dans config.json (autre fenêtre du lanceur) : affichée, sauf si le formulaire a des
        modifications non enregistrées (signalées alors, sans les écraser)."""
        try:
            d = self.l.relire_connexion()
        except OSError:
            return
        if d is None:
            return
        if self.cx_modifie:
            self.cx_plus_recente = d
            self.maj_etat_connexion()
        else:
            self.remplir_connexion(d)

    # ------------------------------------------------------------------ suivi seul (client sans le jeu)
    _suivi_bouton_actif = False

    def maj_suivi(self, s: L.EtatSession) -> None:
        texte, niv, cle, actif = ligne_suivi(self.langue, s, self.l.config.configuree, self.suivi_demarrage)
        if self.v["cx_suivi"].get() != texte:
            self.v["cx_suivi"].set(texte)
            self.replanifier()
        self.niveau("cx_suivi", niv)
        self._suivi_bouton_actif = actif
        b = getattr(self, "b_cx_suivi", None)
        if b is not None and b.texte != self.tr(cle):
            b.changer_texte(self.tr(cle))

    def demarrer_suivi(self, montrer: bool = False) -> None:
        """Client de suivi (fil de fond, sans bloquer la fenêtre) ; `montrer` : résultat dans la zone de message."""
        if self.suivi_demarrage:
            return
        self.suivi_demarrage = True
        self.maj_session()

        def corps():
            try:
                m = self.l.demarrer_suivi()
                self.file.put(("ok", ("suivi", m if montrer or m.cle != "suivi_deja" else None)))
            except L.ErreurLanceur as e:
                self.file.put(("ok", ("suivi", e.msg)))
            except Exception as e:                          # noqa: BLE001 - montré au joueur, sans fenêtre modale
                self.file.put(("ok", ("suivi", L.Msg("client_echec", {"detail": repr(e)}))))
        threading.Thread(target=corps, daemon=True).start()

    def basculer_suivi(self) -> None:
        """Bouton « Déconnecter » / « Connecter » de la ligne « Suivi »."""
        s = self.l.etat_session(self.session)
        if not s.client_actif:
            self.demarrer_suivi(montrer=True)
            return

        def travail():
            return ("suivi_arret", self.l.deconnecter_suivi())
        self.en_fond(travail, self.tr("cx_deconnecter") + "…")

    # ------------------------------------------------------------------ mise à jour du lanceur (maj.py)
    def chercher_maj(self) -> None:
        """Fil de fond, une fois par ouverture : jamais bloquant, silencieux si rien n'arrive."""
        def corps():
            a = self.l.verifier_maj()
            if a is not None:
                self.file.put(("ok", ("maj", a)))
        threading.Thread(target=corps, daemon=True).start()

    def maj_bouton_actif(self, libre: bool) -> bool:
        a = self.maj_annonce
        return a is not None and (a.mode == "lien" or (libre and self.maj_refus is None))

    def maj_montrer(self) -> None:
        """Lignes de la carte « Mod » ; vides (donc masquées) sans annonce. Refaites au changement de langue."""
        a = self.maj_annonce
        raison = self.maj_refus if a is not None and a.mode == "auto" else None
        textes = {"maj": self.tr("maj_disponible", version=a.version) if a else "",
                  "maj_notes": a.texte_notes(self.langue) if a else "",
                  "maj_raison": (texte_msg(self.langue, raison) if raison else
                                 self.tr("maj_manuelle") if a and a.mode == "lien" else "")}
        change = False
        for k, v in textes.items():
            if self.v[k].get() != v:
                self.v[k].set(v)
                change = True
        self.niveau("maj", "attention" if a else None)
        self.niveau("maj_raison", "attention" if raison else None)
        cle = "maj_bouton_lien" if a is not None and a.mode == "lien" else "maj_bouton"
        if self.b_maj.texte != self.tr(cle):
            self.b_maj.changer_texte(self.tr(cle))
        if change:
            self.replanifier()

    def maj_suivre(self) -> None:
        """Une fois par seconde, seulement quand une mise à jour automatique est annoncée."""
        a = self.maj_annonce
        if a is not None and a.mode == "auto":
            self.maj_refus = self.l.refus_maj(self.session)
            self.maj_montrer()

    def basculer_maj(self) -> None:
        self.l.changer_maj_verifier(bool(self.maj_var.get()))

    def cliquer_maj(self) -> None:
        a = self.maj_annonce
        if a is None:
            return
        if a.mode == "lien":
            import webbrowser
            webbrowser.open(a.page)                      # https et hôte contrôlés (maj.lire_manifeste)
            return
        self.maj_refus = self.l.refus_maj(self.session)
        if self.maj_refus is not None:
            self.maj_montrer()
            self.maj_boutons()
            return
        if not messagebox.askyesno(self.tr("maj_titre"), self.tr("maj_accord", version=a.version),
                                   parent=self.racine):
            return

        def travail():
            self.l.installer_maj(a, self.session, rappel=lambda m: self.file.put(("etape", m)))
            return ("maj_prete", None)
        self.en_fond(travail, self.tr("maj_en_cours"))

    def basculer_amitie(self) -> None:
        """Case « Fenêtre d'amitié en combat » (onglet « Réglages » → « Paramètres du jeu ») : mémorisée, appliquée
        tout de suite."""
        actif = bool(self.amitie_var.get())
        FA.memoriser(self.l, amitie_fenetre=actif)
        self.amitie.activer(actif)

    def basculer_loupe(self) -> None:
        """Case « Fenêtre de la loupe » (onglet « Réglages » → « Paramètres du jeu ») : mémorisée, appliquée tout de
        suite."""
        actif = bool(self.loupe_var.get())
        FA.memoriser(self.l, loupe_fenetre=actif)
        self.loupe.activer(actif)

    def basculer_objets(self) -> None:
        """Case « Fenêtre des derniers objets » (même carte) : mémorisée, appliquée tout de suite."""
        actif = bool(self.objets_var.get())
        FA.memoriser(self.l, objets_fenetre=actif)
        self.objets.activer(actif)

    def changer_delai_objets(self, delai: int) -> None:
        """Délai d'effacement des lignes de cette fenêtre : mémorisé, appliqué tout de suite."""
        FA.memoriser(self.l, objets_fenetre_delai=int(delai))
        self.objets.changer_delai(delai)

    def fermer(self) -> None:
        self.amitie.arreter()
        self.loupe.arreter()
        self.objets.arreter()
        self.l.fermer()                                  # lanceur.pid effacé : le client de suivi s'arrête (hors jeu)
        self.racine.destroy()

    # ------------------------------------------------------------------ fil de fond
    def en_fond(self, travail, texte: str, bloquer: bool = True, delai: int = 0) -> None:
        """`travail` dans un fil de fond (résultat par la file) ; `delai` (ms) : fil démarré un peu plus tard par la
        boucle Tk (le message, lui, est affiché tout de suite)."""
        if bloquer:
            self.occupe = True
            self.maj_boutons()
        self.message(texte)

        def corps():
            try:
                self.file.put(("ok", travail()))
            except L.ErreurLanceur as e:
                self.file.put(("erreur", e.msg))
            except Exception as e:                          # noqa: BLE001 - montré au joueur
                self.file.put(("erreur", L.Msg("installation_echec", {"detail": repr(e)})))
            finally:
                if bloquer:
                    self.file.put(("libre", None))
        fil = threading.Thread(target=corps, daemon=True)
        if delai > 0:
            self.racine.after(delai, fil.start)
        else:
            fil.start()

    def lire_file(self) -> None:
        try:
            while True:
                genre, val = self.file.get_nowait()
                if genre == "libre":
                    self.occupe = False
                    self.rafraichir()
                elif genre == "etape":
                    self.message(texte_msg(self.langue, val))
                elif genre == "erreur":
                    self.message(texte_msg(self.langue, val))
                    messagebox.showerror(self.tr("erreur"), texte_msg(self.langue, val), parent=self.racine)
                else:
                    self.resultat(*val)
        except queue.Empty:
            pass
        self.racine.after(100, self.lire_file)

    def resultat(self, quoi: str, r) -> None:
        if quoi == "rom":
            self.rom_ok = r.ok
            self.v["rom_etat"].set(texte_msg(self.langue, r.msg))
            self.niveau("rom_etat", niveau_rom(r.ok))
            if not self.occupe:
                self.message(self.tr("pret") if r.ok and not self.l.problemes(self.etat_az) else "")
            self.maj_boutons()
        elif quoi == "installation":
            if r.action == "deja_installe":
                txt = self.tr("installation_deja")
            elif r.action == "desinstalle":
                txt = self.tr("desinstallation_ok")
            else:
                txt = self.tr("installation_ok", version=r.version, dossier=str(r.dossier))
            for a in r.avertissements:
                txt += "\n" + self.tr("installation_avert", detail=a)
            self.message(txt)
            if r.action != "desinstalle":            # cartes du tracker : absentes ou périmées seulement (voir
                self.checks.generer_cartes(force=False)  # cartes.raison_generation) ; « Réparer » : refaites
        elif quoi == "reparation":
            self.resultat("installation", r)
            self.checks.generer_cartes(force=True)
        elif quoi == "jouer":
            self.session = r
            self.lancee = True
            self.message("")
        elif quoi == "suivi":
            self.suivi_demarrage = False
            if r is not None:
                self.message(texte_msg(self.langue, r))
            self.maj_session()
        elif quoi == "suivi_arret":
            self.message(texte_msg(self.langue, r))
            self.maj_session()
        elif quoi == "maj":
            self.maj_annonce = r
            self.maj_suivre()
            self.maj_montrer()
            self.maj_boutons()
        elif quoi == "maj_prete":                    # l'outil attend la fin de ce processus
            self.racine.after(200, self.fermer)

    # ------------------------------------------------------------------ actions
    def changer_langue(self) -> None:
        self.langue = "en" if self.langue == "fr" else "fr"
        self.l.changer_langue(self.langue)
        self.construire()
        self.rafraichir(verifier_rom=True)

    def _changer_epingle(self, cle: str) -> None:
        """Yo-kai épinglé (onglet « Yo-kai ») : mémorisé, puis montré par le sous-onglet « Carte » des checks."""
        self.l.changer_epingle(cle)
        self.checks.epingle_change()

    def choisir_rom(self) -> None:
        f = filedialog.askopenfilename(parent=self.racine, title=self.tr("choisir_rom_titre"), filetypes=[
            (self.tr("filtre_rom"), "*.3ds *.cci *.cxi"), (self.tr("filtre_tout"), "*.*")])
        if not f:
            return
        self.v["rom"].set(f)
        self.en_fond(lambda: ("rom", self.l.choisir_rom(f)), self.tr("rom_verification"))

    def choisir_azahar(self) -> None:
        types = [(self.tr("filtre_exe"), "*.exe")] if os.name == "nt" else []
        f = filedialog.askopenfilename(parent=self.racine, title=self.tr("choisir_azahar_titre"),
                                       filetypes=types + [(self.tr("filtre_tout"), "*.*")])
        if f and self.l.choisir_azahar(f):
            self.rafraichir()

    def activer_gdb(self) -> None:
        g = self.l.etat_gdb(self.l.info_azahar(True))
        if self.l._en_cours():
            messagebox.showerror(self.tr("erreur"), self.tr("azahar_ouvert_config"), parent=self.racine)
            return
        accord = messagebox.askyesno(self.tr("gdb_accord_titre"),
                                     self.tr("gdb_accord", fichier=str(g.fichier), port=g.port), parent=self.racine)
        if not accord:
            self.message(self.tr("gdb_refuse"))
            return
        try:
            s = self.l.activer_gdb(accord=True)
        except L.ErreurLanceur as e:
            messagebox.showerror(self.tr("erreur"), texte_msg(self.langue, e.msg), parent=self.racine)
            return
        self.message(self.tr("gdb_active", sauvegarde=str(s)) if s else self.tr("gdb_deja"))
        self.rafraichir()

    def installer(self) -> None:
        self.en_fond(lambda: ("installation", self.l.installer(rappel=lambda m: self.file.put(("etape", m)))),
                     self.tr("installation_en_cours"))

    def reparer(self) -> None:
        self.en_fond(lambda: ("reparation", self.l.reparer(rappel=lambda m: self.file.put(("etape", m)))),
                     self.tr("installation_en_cours"))

    def desinstaller(self) -> None:
        if messagebox.askyesno(self.tr("confirmation"), self.tr("desinstallation_accord"), parent=self.racine):
            self.en_fond(lambda: ("installation", self.l.desinstaller()), self.tr("desinstaller"))

    def jouer(self) -> None:
        serveur, slot, mdp, memo = self.valeurs_connexion()
        try:                                             # « Jouer » enregistre aussi la connexion modifiée
            m = self.l.preparer_connexion(serveur, slot, mdp, memo)
        except L.ErreurLanceur as e:
            self.signaler_connexion(serveur, slot, e.msg)
            self.message(texte_msg(self.langue, e.msg))
            return
        if m is not None:
            self.remplir_connexion(self.l.config)

        def travail():
            s = self.l.jouer(rappel=lambda m: self.file.put(("etape", m)))
            return ("jouer", s)
        self.en_fond(travail, self.tr("etape_client"))

    def ouvrir_journaux(self) -> None:
        d = self.l.dossier_journaux
        d.mkdir(parents=True, exist_ok=True)
        ouvrir(d)

    def ouvrir_aide(self) -> None:
        a = L.fichier_aide()
        if a is None:
            messagebox.showinfo(self.tr("information"), self.tr("aide_absente"), parent=self.racine)
        else:
            ouvrir(a)


def dpi_systeme() -> None:
    """Windows : fenêtre nette à 125 %/150 % (sinon Windows l'agrandit en bitmap, flou). Tk lit alors la vraie
    résolution et le thème met polices et dessins à l'échelle (`Theme.px`)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


INTERVALLE_GIL = 0.0005                # s ; voir `priorite_interface`
# ms : la vérification de la ROM (décompression du code en Python pur, ~0,5 s de calcul) démarre après le premier
# affichage de la fenêtre, au lieu de lui disputer le processeur (premier affichage mesuré : 520 ms avec, 350 sans)
DELAI_VERIFICATION_ROM = 400
DELAI_VERIFICATION_MAJ = 1500           # ms : après le premier affichage et la vérification de la ROM
DELAI_NETTOYAGE_MAJ = 10000             # ms : l'outil de remplacement qui nous a relancés est alors terminé


def priorite_interface() -> None:
    """La fenêtre passe avant les tâches de fond. Les opérations longues (vérification de la ROM, installation,
    génération des cartes et de la base des Yo-kai) tournent dans des fils en Python pur, qui gardent le GIL ; avec
    l'intervalle de commutation par défaut (5 ms, arrondi à ~15 ms par l'horloge de Windows), CHAQUE appel Tcl du fil
    de la fenêtre attendait ce délai pour reprendre le GIL : une mise en page (des centaines d'appels) gelait la
    fenêtre plusieurs secondes « quand il charge des trucs » (mesuré : 39 ms -> 28 s). Sous la milliseconde, le fil
    de fond rend le GIL dès qu'on le lui demande ; il n'est pas ralenti quand la fenêtre ne fait rien."""
    sys.setswitchinterval(INTERVALLE_GIL)


ID_APPLICATION = "YKW2.Archipelago.Lanceur"


def identite_windows() -> None:
    """Windows : identifiant d'application propre, pour que la barre des tâches montre l'icône du lanceur (et non
    celle de pythonw) et ne le regroupe pas avec d'autres scripts Python."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APPLICATION)
    except (AttributeError, OSError):
        pass


def appliquer_icone(racine: tk.Tk) -> list:
    """Icône de la fenêtre et de la barre des tâches, aussi pour les fenêtres filles (boîtes de dialogue) : sous
    Windows le `.ico` multi-tailles (`iconbitmap(default=…)`) SEUL (appelé après `iconphoto`, il remet une icône
    générique, vu sous Windows 11) ; ailleurs, ou s'il échoue, les PNG multi-tailles (`iconphoto`, Tk 8.6).
    Sans effet si les ressources manquent."""
    images: list = []
    ico = th.RESSOURCES / "icone.ico"
    if os.name == "nt" and ico.is_file():
        try:
            racine.iconbitmap(default=str(ico))
            return images
        except tk.TclError:
            pass
    images = [i for i in (th.charger_image(racine, f"icone_{n}.png") for n in th.TAILLES_ICONE) if i is not None]
    try:
        if images:
            racine.iconphoto(True, *images)
    except tk.TclError:
        pass
    racine._icones_ykw2 = images                      # garder les images en vie
    return images


def main(argv: list[str] | None = None) -> int:
    priorite_interface()
    dpi_systeme()
    identite_windows()
    racine = tk.Tk()
    appliquer_icone(racine)
    Fenetre(racine, L.Lanceur())
    racine.mainloop()
    return 0
