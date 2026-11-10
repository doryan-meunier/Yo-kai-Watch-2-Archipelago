"""Mise en texte des états du lanceur (sans tkinter, testable) : ce que la vue affiche."""
from __future__ import annotations

import dataclasses
import time

from . import tracker as TK
from .logique import EtatAzahar, EtatMod, EtatSession, Msg, az
from .textes import FR as TEXTES_CAUSES, t


def texte_msg(langue: str, m: Msg) -> str:
    return t(langue, m.cle, **m.params)


def texte_mod(langue: str, e: EtatMod) -> str:
    if e.statut == "non_installe" and e.mis_de_cote:
        return t(langue, "mod_non_installe_autre", fichiers=", ".join(e.mis_de_cote))
    s = t(langue, "mod_" + e.statut, version=e.version_installee or "?", installee=e.version_installee or "?",
          paquet=e.version_paquet or "?", detail=e.detail)
    if e.statut == "a_jour" and not e.libelle:
        s += t(langue, "mod_libelle_absent")
    return s


def texte_version_azahar(langue: str, e: EtatAzahar) -> str:
    if e.emulateur == "zakuro":
        return t(langue, "zakuro_version")
    if not e.version:
        return t(langue, "azahar_version_inconnue")
    if e.validee:
        return t(langue, "azahar_version_ok", version=e.version)
    return t(langue, "azahar_version_autre", version=e.version, reference=az.VERSION_REFERENCE)


def texte_gdb(langue: str, e: EtatAzahar) -> str:
    return t(langue, "gdb_" + e.gdb.statut, port=e.gdb.port, fichier=str(e.gdb.fichier or ""))


def lignes_session(langue: str, s: EtatSession, lancee: bool) -> list[str]:
    """Trois lignes : client, jeu, serveur. `lancee` : une partie a été lancée depuis ce lanceur."""
    client = t(langue, "client_suivi" if s.suivi_seul else ("client_pret" if s.client_actif else "client_arrete"))
    if s.jeu_actif:
        jeu = t(langue, "jeu_lance") if s.phase == "jeu" or not s.client_actif else t(langue, "jeu_attente")
    else:
        jeu = t(langue, "jeu_ferme" if lancee else "jeu_non_lance")
    serveur = t(langue, f"serveur_{s.etat}") if s.client_actif else t(langue, "serveur_0")
    if s.client_actif and s.etat == 4 and s.erreur in range(1, 7):
        serveur += f" ({t(langue, f'serveur_err_{s.erreur}')})"      # slot inconnu, mot de passe refusé... (traduit)
    elif s.client_actif and s.etat in (3, 4) and s.message:
        serveur += f" ({s.message})"
    if s.client_actif and s.etat == 3 and s.slot:
        serveur += f" - {s.slot}"
    return [t(langue, "etat_client", valeur=client), t(langue, "etat_jeu", valeur=jeu),
            t(langue, "etat_serveur", valeur=serveur)]


# ---------------------------------------------------------------------- sauvegarde chargée, liaison manuelle
NIVEAUX_SAUVEGARDE = {"attente": "neutre", "liee": "ok", "liaison": "attention", "non_liee": "attention",
                      "autre": "erreur", "jeu_ancien": "erreur", "verrous_incompatibles": "erreur",
                      # mélange des boss de la graine (version 2) non appliqué : rien n'est lié ni envoyé
                      "boss_attente": "attention", "boss_rom": "erreur", "boss_refuse": "erreur", "boss_jeu": "erreur",
                      # V3, lots M2b : mélange des Yo-kai de version 7 (zones des Yo-kai demandés) non appliqué
                      "yokai_attente": "attention", "yokai_rom": "erreur", "yokai_refuse": "erreur",
                      "yokai_jeu": "erreur"}


NIVEAUX_MELANGE = {"absent": "neutre", "aucun": "neutre", "refuse": "erreur", "calcul": "attention",
                   "sans_support": "erreur", "applique": "ok", "pas_applique": "attention"}


def ligne_melange(langue: str, d: dict | None, client_actif: bool = True, maintenant: float | None = None
                  ) -> tuple[str, str]:
    """(texte, niveau) de la ligne « Yo-kai mélangés » de la carte « Connexion » (V3, lot M1) depuis
    `rando_yokai.json` du client (`d`, déjà lu ; None : absent) : mode, version, Yo-kai changés (calcul du client),
    réécritures du jeu (compteur publié dans l'en-tête de la boîte, déjà lu par le client), ou la cause en clair d'un
    refus / d'un mélange pas encore appliqué. `client_actif` faux : on précise la date de cet état."""
    e = TK.etat_melange(d)
    jeu = e.jeu or {}
    cause = str(jeu.get("cause") or "")
    if e.statut == "pas_applique" and cause in ("", "ecrit") and jeu.get("support") is not None:
        cause = "pret"
    texte_cause = t(langue, "cxc_" + cause) if ("cxc_" + cause) in TEXTES_CAUSES else (e.message or "?")
    if e.statut == "refuse" and cause in ("refuse", "") and e.message:
        texte_cause = e.message
    stats = e.stats or {}
    total = int(stats.get("combattants") or 0)
    changes = int(stats.get("changes") or 0) if total else len(e.sigma)
    params = dict(mode=t(langue, "mode_" + e.mode) if e.mode else "?", version=e.version,
                  perimetre=t(langue, "cx_melange_perimetre") if e.perimetre == "apres_jeu" else "",
                  changes=changes, total=total or "?", pct=(100 * changes // total) if total else "?",
                  modifies=int(jeu.get("modifies") or 0), cause=texte_cause)
    cle = "cx_melange_" + e.statut
    if not total and e.statut in ("applique", "pas_applique"):          # modes par espèce : espèces déplacées
        cle += "_especes"
    texte = t(langue, cle, **params)
    horodatage = (d or {}).get("horodatage") if isinstance(d, dict) else None
    if not client_actif and isinstance(horodatage, (int, float)) and e.statut != "absent":
        texte = texte[:-1] if texte.endswith(".") else texte
        texte += t(langue, "cx_melange_vieux", quand=texte_quand(langue, horodatage, maintenant)) + "."
    return texte, NIVEAUX_MELANGE.get(e.statut, "neutre")


def ligne_sauvegarde(langue: str, s: EtatSession) -> tuple[str, str | None]:
    """(texte, niveau) de la ligne « Sauvegarde » de la carte d'état ; texte vide (ligne masquée) sans partie chargée
    ou sans client. Sauvegarde non liée : une partie Archipelago se joue sur une NOUVELLE partie (décision de l'humain
    du 2026-09-28 : plus de liaison manuelle)."""
    if not s.client_actif or s.sauvegarde not in NIVEAUX_SAUVEGARDE:
        return "", None
    return t(langue, "sv_" + s.sauvegarde), NIVEAUX_SAUVEGARDE[s.sauvegarde]


# ---------------------------------------------------------------------- connexion Archipelago (carte 4)
def texte_quand(langue: str, horodatage: float, maintenant: float | None = None) -> str:
    """« le 28/09 à 14:03 » / « on 2026-09-28 at 14:03 » (heure locale)."""
    if horodatage <= 0:
        return ""
    lt = time.localtime(horodatage)
    jour = time.strftime("%d/%m" if langue == "fr" else "%Y-%m-%d", lt)
    return t(langue, "cx_quand", jour=jour, heure=time.strftime("%H:%M", lt))


def etat_connexion(langue: str, config, *, modifie: bool = False, plus_recente=None) -> tuple[str, str]:
    """(texte, niveau) de la ligne d'état de la carte « Connexion Archipelago ». `config` : configuration affichée
    (ConfigLocale) ; `modifie` : formulaire non enregistré ; `plus_recente` : configuration du disque plus récente que
    le formulaire modifié (autre fenêtre du lanceur ; la connexion ne se saisit plus dans le jeu)."""
    if plus_recente is not None:
        return t(langue, "cx_plus_recente", serveur=plus_recente.serveur or "-",
                 slot=plus_recente.slot or "-"), "attention"
    if modifie:
        return t(langue, "cx_modifie"), "attention"
    if not (config.serveur and config.slot):
        return t(langue, "cx_aucune"), "neutre"
    if config.source_connexion in ("lanceur", "jeu"):
        return t(langue, "cx_source_" + config.source_connexion,
                 quand=texte_quand(langue, config.horodatage_connexion)).replace(" .", "."), "ok"
    return t(langue, "cx_source_inconnue"), "ok"


def ligne_suivi(langue: str, s: EtatSession, configuree: bool, demarrage: bool = False) -> tuple[str, str, str, bool]:
    """Ligne « Suivi » de la carte « Connexion Archipelago » (client connecté au serveur, avec ou sans le jeu) :
    (texte, niveau, clé du bouton « cx_connecter » / « cx_deconnecter », bouton actif)."""
    if demarrage:
        return t(langue, "suivi_demarrage"), "attention", "cx_deconnecter", False
    if not s.client_actif:
        if not configuree:
            return t(langue, "suivi_off_sans_cx"), "neutre", "cx_connecter", False
        return t(langue, "suivi_off"), "neutre", "cx_connecter", True
    if s.etat == 3:
        texte, niv = t(langue, "suivi_connecte", slot=s.slot or "?", serveur=s.serveur or "?"), "ok"
    elif s.etat == 4:
        detail = t(langue, f"serveur_err_{s.erreur}") if s.erreur in range(1, 7) else (s.message or "?")
        texte, niv = t(langue, "suivi_erreur", detail=detail), "erreur"
    elif s.etat == 5:
        texte, niv = t(langue, "suivi_reconnexion"), "attention"
    elif s.etat == 1:
        texte, niv = t(langue, "suivi_non_configure"), "attention"
    else:
        texte, niv = t(langue, "suivi_connexion"), "attention"
    if not s.suivi_seul:                                   # jeu attaché (ou client d'une version antérieure)
        return t(langue, "suivi_avec_jeu", ligne=texte), niv, "cx_deconnecter", False
    return texte, niv, "cx_deconnecter", True


# ---------------------------------------------------------------------- niveaux (pastilles de couleur de la vue)
# "ok" (vert), "attention" (orange), "erreur" (rouge), "neutre" (gris) ; None : pas de pastille.

def niveau_rom(ok: bool | None) -> str:
    """ROM : None = vérification en cours ou pas encore faite."""
    return "neutre" if ok is None else ("ok" if ok else "erreur")


def niveau_version_azahar(e: EtatAzahar) -> str | None:
    if not e.executable:
        return None
    return "ok" if e.version and e.validee else "attention"


def niveau_gdb(e: EtatAzahar) -> str | None:
    if not e.executable:
        return None
    return {"actif": "ok", "inactif": "attention"}.get(e.gdb.statut, "erreur")


def niveau_mod(e: EtatMod) -> str:
    if e.statut == "a_jour":
        return "ok" if e.libelle else "attention"
    if e.statut in ("non_installe", "autre_version"):
        return "attention" if e.statut == "autre_version" else "neutre"
    return "erreur"


def niveaux_session(s: EtatSession, lancee: bool) -> list[str]:
    """Niveaux des trois lignes de `lignes_session` (client, jeu, serveur)."""
    client = "ok" if s.client_actif else "neutre"
    if s.jeu_actif:
        jeu = "ok" if s.phase == "jeu" or not s.client_actif else "attention"
    else:
        jeu = "neutre"
    if not s.client_actif:
        serveur = "neutre"
    else:
        serveur = {3: "ok", 4: "erreur", 1: "attention", 2: "attention", 5: "attention"}.get(s.etat, "neutre")
    return [client, jeu, serveur]


# ---------------------------------------------------------------------- tracker de Yo-kai (onglet « Yo-kai »)
SEP = " — "                         # tiret cadratin : « lieu — niveau — à la place de X »


def texte_tribu(langue: str, m: TK.Modele, tribu) -> str:
    """Nom de la tribu lu dans la ROM (noms_local.json) ; sinon « Tribu n » ; 0 / 9 / inconnue : « - »."""
    if not isinstance(tribu, int) or tribu not in TK.TRIBUS_NOMMEES:
        return "-"
    return m.nom_tribu(tribu, langue) or t(langue, "yk_tribu_n", n=tribu)


def texte_niveaux(langue: str, l: TK.Lieu) -> str:
    if l.niv_min == l.niv_max:
        return t(langue, "yk_niveau", n=l.niv_min)
    return t(langue, "yk_niveaux", a=l.niv_min, b=l.niv_max)


def texte_carte(langue: str, m: TK.Modele, carte: str) -> str:
    """Nom de la carte lu dans la ROM du joueur ; sinon région saisie à la main + identifiant."""
    return m.nom_carte(carte, langue) or t(langue, "yk_carte_region", region=TK.nom_region(TK.region_de(carte), langue),
                                           carte=carte)


def textes_moment(langue: str, masque: int) -> list[str]:
    """Restrictions de moment d'un lieu ou d'un point (base au format 13, §19) : « jour seulement », « nuit
    seulement », « pluie seulement », « temps sec seulement » ; rien si tous les moments conviennent ; 0 : « absent de
    cette version du jeu »."""
    if masque == 0:
        return [t(langue, "moment_jamais")]
    out = []
    quand = TK.nom_moment(masque)
    if quand:
        out.append(t(langue, "moment_" + quand))
    if masque & TK.PLUIE and not masque & TK.SEC:
        out.append(t(langue, "moment_pluie"))
    elif masque & TK.SEC and not masque & TK.PLUIE:
        out.append(t(langue, "moment_sec"))
    return out


def texte_lieu(langue: str, m: TK.Modele, l: TK.Lieu, masquer: bool = False, avec_carte: bool = False) -> str:
    """« loupe — niv. 12-14 — à la place de X — nuit seulement — rang de montre requis » (`avec_carte` : nom de la
    carte devant ; `masquer` : Yo-kai d'origine caché, anti-divulgâchage)."""
    morceaux = [texte_carte(langue, m, l.carte)] if avec_carte else []
    methode = t(langue, ("lieu_portail" if l.salle_connue else "lieu_portail_nc") if l.portail
                else "methode_" + l.methode)
    if l.decors:                                     # « loupe (arbre, buisson) » : natures connues des décors
        methode += " (" + ", ".join(t(langue, "decor_" + d) for d in l.decors) + ")"
    if l.methode == TK.CRANK:                        # V3, lot B1 : lot d'une pièce du Bingo-kai aléatoire
        noms = l.piece_noms or {}
        piece = noms.get("en" if langue == "en" else "fr") or noms.get("fr") or ""
        morceaux.append(methode)
        if piece and l.taux is not None:
            morceaux.append(t(langue, "yk_crank_piece", piece=piece, taux=texte_pourcent(langue, l.taux)))
        elif piece and l.exige:                      # pièce spéciale de la graine : tirage dirigé
            morceaux.append(t(langue, "yk_crank_dirige_n" if l.exige > 1 else "yk_crank_dirige", piece=piece,
                              n=l.exige))
        elif piece:
            morceaux.append(piece)
        if l.exige and l.acces is False:
            morceaux.append(t(langue, "yk_pieces_pas_recues", n=l.exige) if l.exige > 1
                            else t(langue, "yk_piece_pas_recue"))
        return SEP.join(morceaux)
    if l.methode == TK.FUSION:                       # fusion régionale : Yo-kai régional + objet de fusion
        noms = l.piece_noms or {}
        objet = noms.get("en" if langue == "en" else "fr") or noms.get("fr") or ""
        morceaux += [methode] + ([t(langue, "yk_fusion_objet", objet=objet)] if objet else [])
        if l.acces is False:
            morceaux.append(t(langue, "yk_fusion_pas_recue"))
        return SEP.join(morceaux)
    if l.methode == TK.INVITE:                       # invité de l'Auberge : niveau du plus haut Yo-kai de l'équipe
        morceaux += [methode, t(langue, "yk_niveau_equipe")]
        if l.conditions == ("invite_attente",) and l.restantes:
            return SEP.join(morceaux + [t(langue, "cond_invite_attente_n", n=l.restantes)])
        if l.conditions == ("invite_file",) and l.rang_file:
            return SEP.join(morceaux + [t(langue, "cond_invite_file_n", n=l.rang_file)])
        if l.conditions == ("invite_present",) and l.piece is not None:
            piece = t(langue, "invite_piece_suite") if l.piece == 0 else t(langue, "invite_piece_chambre", n=100 + l.piece)
            return SEP.join(morceaux + [t(langue, "cond_invite_present_piece", piece=piece)])
        return SEP.join(morceaux + [t(langue, "cond_" + c) for c in l.conditions])
    morceaux += [methode, texte_niveaux(langue, l)]
    if l.a_la_place_de is not None:
        y = m.yokai.get(l.a_la_place_de)
        if masquer:
            morceaux.append(t(langue, "yk_a_la_place_masque"))
        elif y is not None:
            morceaux.append(t(langue, "yk_a_la_place", nom=y.nom(langue)))
    elif l.inchange and m.melange.affectation:      # V3, lot M1 : pourquoi ce lieu garde son Yo-kai d'origine
        morceaux.append(t(langue, "yk_inchange", raison=t(langue, "inch_" + l.inchange)))
    morceaux += textes_moment(langue, l.moment)
    for c in l.conditions:
        if c == "rang" and l.rang_exige is not None:
            morceaux.append(t(langue, "cond_rang_n", rang=TK.RANGS[l.rang_exige]))
        elif not (c == "heure" and l.heure_dite):    # « nuit seulement » le dit déjà
            morceaux.append(t(langue, "cond_" + c))
    if l.jamais:
        pass                                         # « absent de cette version du jeu » : rien à attendre
    elif m.acces_connu and l.acces is False:
        morceaux.append(t(langue, "yk_acces_non"))
    elif m.acces_connu and l.acces is None:
        morceaux.append(t(langue, "yk_acces_portail" if l.portail else "yk_acces_inconnu"))
    return SEP.join(morceaux)


def texte_point(langue: str, m: TK.Modele, l: TK.Lieu, decor: str | None = None, moment: int | None = None) -> str:
    """Infobulle d'un point du Yo-kai épinglé (sous-onglet « Carte ») : « loupe (arbre) — niv. 12-14 — nuit seulement
    — rang de montre C requis — pas encore accessible ». Le décor et le moment sont ceux DU POINT ; le Yo-kai d'origine
    de l'emplacement n'est jamais cité (anti-divulgâchage : la carte ne dit que ce que la ligne dévoilée de l'onglet
    « Yo-kai » dit déjà)."""
    return texte_lieu(langue, m, dataclasses.replace(l, a_la_place_de=None, decors=(decor,) if decor else (),
                                                     moment=l.moment if moment is None else moment))


def resume_yokai(langue: str, m: TK.Modele, y: TK.Yokai, lieux: list[TK.Lieu]) -> str:
    """Colonne « Où, comment » d'un Yo-kai : nombre de lieux (et méthodes) ; ou « pas à l'état sauvage : … »."""
    if not lieux:
        if y.categories:
            return t(langue, "yk_hors_sauvage", categories=", ".join(t(langue, "cat_" + c) for c in y.categories))
        return t(langue, "yk_hors_sauvage_seul")
    n = len({(l.carte, l.methode) for l in lieux})
    s = t(langue, "yk_lieu_1") if n == 1 else t(langue, "yk_lieux", n=n)
    methodes = [t(langue, "methode_" + me) for me in TK.METHODES + (TK.INVITE, TK.CRANK, TK.FUSION)
                if any(l.methode == me for l in lieux)]
    s += " (" + ", ".join(methodes) + ")"
    if y.zone and m.melange.melange:
        # V3, lots M2b : Yo-kai demandé placé par la graine dans sa zone (au moins deux endroits)
        s += SEP + t(langue, "yk_zone", zone=TK.nom_zone(y.zone, langue))
    elif y.fixe and m.melange.melange:
        s += SEP + t(langue, "yk_garde" if m.melange.affectation else "yk_fixe")
    return s


def texte_pourcent(langue: str, x: float) -> str:
    """Pourcentage lisible d'une probabilité 0..1 : entier à partir de 10 %, une décimale en dessous (« 9,1 »,
    « 18 » ; point décimal en anglais)."""
    v = 100.0 * x
    if v >= 9.95:
        return str(int(v + 0.5))
    s = "%.1f" % v
    return s if langue == "en" else s.replace(".", ",")


def titre_amitie(langue: str, a: TK.Amitie, ami: bool | None = None) -> str:
    """Première colonne de la ligne d'amitié : « Amitié : 1 chance sur 32 par combat » (« Amitié » seul si le Yo-kai
    ne peut pas devenir ami). Le taux est toujours celui d'un PREMIER exemplaire (le lanceur ne connaît pas le nombre
    possédé) : si le Yo-kai est déjà ami (`ami`) et que le taux change quand on en possède un, la ligne le dit
    (« 1re amitié : 1 chance sur 32 par combat »)."""
    if not a.possible:
        return t(langue, "yk_amitie_titre")
    return t(langue, "yk_amitie_premiere" if ami and a.baisse else "yk_amitie", n=a.cle)


def texte_amitie(langue: str, a: TK.Amitie) -> str:
    """Colonne « Où, comment » de la ligne d'amitié : « Riz : ≈ 9,1 à 18 % (préférée) » (aliment de la
    catégorie préférée, de la plus faible à la plus forte valeur ; base au format 11 : nom de la catégorie, saisi à la
    main ; catégorie inconnue ou base plus ancienne : « ≈ 9,1 à 18 % avec sa nourriture préférée » ; bonus inconnu :
    la catégorie seule ou rien), ou « Ne peut pas devenir ami en combat » (jamais d'aliment)."""
    if not a.possible:
        return t(langue, "yk_amitie_jamais")
    pref = a.chance_preferee
    aliment = t(langue, "aliment_%d" % a.aliment) if a.aliment in TK.ALIMENTS else ""
    if pref is None:
        return t(langue, "yk_aliment", aliment=aliment) if aliment else ""
    bas, haut = (texte_pourcent(langue, x) for x in pref)
    if aliment:                                      # l'aliment d'abord : jamais coupé par la largeur de la colonne
        return (t(langue, "yk_amitie_aliment_1", a=bas, aliment=aliment) if bas == haut
                else t(langue, "yk_amitie_aliment", a=bas, b=haut, aliment=aliment))
    return t(langue, "yk_amitie_pref_1", a=bas) if bas == haut else t(langue, "yk_amitie_pref", a=bas, b=haut)


def note_amitie(langue: str, a: TK.Amitie) -> str:
    """Seconde ligne (rare) : une autre espèce de la même base (autre combat) ne devient jamais amie ; vide sinon."""
    return t(langue, "yk_amitie_variante") if a.variante_jamais else ""


def texte_etat_melange(langue: str, e: TK.EtatMelange) -> str:
    mode = t(langue, "mode_" + e.mode) if e.mode else "?"
    return t(langue, "melange_" + e.statut, mode=mode, graine=e.graine if e.graine is not None else "?",
             n=len(e.sigma) or e.nb_d, message=e.message or "?")


def lignes_etat_tracker(langue: str, m: TK.Modele) -> list[tuple[str, str]]:
    """Bandeau d'état de l'onglet : [(texte, niveau de pastille)] : mélange, base locale, noms, Médaillium."""
    if not m.base_ok:
        return [(t(langue, "yk_base_absente"), "erreur")]
    out = [(texte_etat_melange(langue, m.melange), m.melange.niveau)]
    date = m.genere.replace("T", " ")[:16] if m.genere else "?"
    out.append((t(langue, "yk_base", n=len(m.yokai), date=date), "ok"))
    if not m.noms_lieux:
        out.append((t(langue, "yk_noms_absents"), "attention"))
    if not m.medaillium:
        out.append((t(langue, "yk_medaillium_absent"), "neutre"))
    elif not m.amis:
        out.append((t(langue, "yk_amis_absent"), "neutre"))
    if not m.conditions_decodees:
        out.append((t(langue, "yk_base_ancienne"), "attention"))
    elif m.progression is None:
        out.append((t(langue, "yk_progression_absente"), "neutre"))
    else:
        p = m.progression
        date = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.horodatage)) if p.horodatage else "?"
        fin = "?" if p.apres_jeu is None else t(langue, "yk_fin_oui" if p.apres_jeu else "yk_fin_non")
        out.append((t(langue, "yk_progression", chapitre=p.chapitre if p.chapitre is not None else "?",
                      rang=TK.RANGS[p.rang] if p.rang is not None else "?", fin=fin, date=date), "ok"))
    return out
