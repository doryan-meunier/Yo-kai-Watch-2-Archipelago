"""Logique du lanceur, SANS affichage (testable hors ligne ; la vue tkinter est dans `vue.py`).

Parcours du joueur (CONCEPTION.md, décision 5 révisée le 2026-09-28 : serveur, slot et mot de passe se saisissent
dans le lanceur SEULEMENT ; le bouton « Archipelago » de l'écran titre du jeu n'affiche plus que l'état ; une partie
Archipelago se joue sur une sauvegarde NEUVE, plus de liaison manuelle) :
1. choisir sa ROM déchiffrée (vérifiée : Yo-kai Watch 2 EUR, SHA-1 du code) et Azahar (détecté) ;
2. installer le mod (patchs BPS livrés + ROM du joueur -> dossier mods d'Azahar, libellé « Archipelago ») ;
3. activer le stub GDB d'Azahar, seulement avec l'accord du joueur (copie de sauvegarde de qt-config.ini) ;
4. connexion Archipelago (obligatoire avant « Jouer ») : serveur, slot, mot de passe -> config.json
   (`enregistrer_connexion`), que le client applique même s'il tourne déjà (il se reconnecte) ; dès qu'elle est
   enregistrée (ou à l'ouverture du lanceur si elle l'est déjà), la vue démarre le client en « suivi seul »
   (`demarrer_suivi` : serveur sans le jeu, pour les onglets Checks / Discussion / Yo-kai) ; « Déconnecter »
   (`deconnecter_suivi`) l'arrête ; le lanceur fermé (`fermer`), il s'arrête seul, sauf jeu en cours ;
5. « Jouer » : le MÊME client (démarré en suivi seul s'il ne tourne pas) reçoit la demande d'attacher le jeu
   (`client_demande.json`, accusée dans etat.json), puis Azahar est lancé sur la ROM (il attend le débogueur pour
   lancer le jeu) et son PID est donné au client (fichier) ; Azahar fermé, le client revient au suivi seul ;
6. pendant la partie, ligne « Sauvegarde » : liée, ou non liée (« commencez une nouvelle partie »).

Toutes les dépendances extérieures (détection d'Azahar, processus lancés, dossiers) sont injectables : les tests
utilisent de faux exécutables et un faux dossier mods. Les messages sont des clés (`Msg`) traduites par
`textes.py`. Bibliothèque standard seulement.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
from urllib.parse import urlsplit
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ARCHIPELAGO = Path(__file__).resolve().parents[1]
for _p in (ARCHIPELAGO, ARCHIPELAGO / "client"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config_locale  # noqa: E402
import execution  # noqa: E402  (client/ : mode normal ou exécutable empaqueté)
from config_locale import ConfigLocale, StockageConfig  # noqa: E402
from installation import apparence as app_mod  # noqa: E402
from installation import apparence_import as app_imp  # noqa: E402
from installation import azahar as az  # noqa: E402
from installation import installer as inst  # noqa: E402
from installation import rom3ds  # noqa: E402
from installation import zakuro as zk  # noqa: E402
from . import maj as maj_mod  # noqa: E402
from . import maj_outil  # noqa: E402

VERSION_LANCEUR = "1.0.0"
PRINCIPAL = ARCHIPELAGO / "client" / "principal.py"
FICHIER_ETAT = "etat.json"            # écrit par le client (principal.py)
FICHIER_PID = "azahar.pid"            # écrit par le lanceur, lu par le client (--quitter-avec-fichier / « jouer »)
FICHIER_DEMANDE = "client_demande.json"   # demandes au client de suivi : {nonce, action (jouer | arreter), …}
FICHIER_LANCEUR = "lanceur.pid"       # PID du lanceur ouvert : le client de suivi s'arrête quand il se ferme
ETAT_PERIME = 15.0                    # s : un etat.json plus vieux vient d'un client arrêté
SERVEUR_MAX_OCTETS = 127              # champs affichés dans le jeu (boîte §10.3) : serveur char[128], slot char[64]
SLOT_MAX_OCTETS = 63


@dataclass
class Msg:
    """Message pour le joueur : clé de `textes.py` + paramètres (et le détail brut, en français)."""
    cle: str
    params: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:                   # utile dans les journaux et les tests
        return self.cle + (f" {self.params}" if self.params else "")


class ErreurLanceur(Exception):
    def __init__(self, msg: Msg):
        super().__init__(str(msg))
        self.msg = msg


# ------------------------------------------------------------------------------------------------ processus
def gele() -> bool:
    """Lanceur empaqueté en un exécutable (PyInstaller) ? Voir `client/execution.py`."""
    return execution.gele()


def interpreteur_sans_fenetre() -> str:
    return execution.interpreteur_sans_fenetre()


def options_detachees(sans_fenetre: bool) -> dict:
    """Le processus survit au lanceur ; `sans_fenetre` : pas de console (client invisible)."""
    if os.name == "nt":
        drapeaux = subprocess.CREATE_NEW_PROCESS_GROUP
        if sans_fenetre:
            drapeaux |= subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        return {"creationflags": drapeaux, "close_fds": True}
    return {"start_new_session": True, "close_fds": True}


def lancer_processus_defaut(cmd: list[str], *, sans_fenetre: bool = False, console: bool = False) -> subprocess.Popen:
    if console:                                   # client dans la console du lanceur en ligne de commande
        return subprocess.Popen(cmd)
    if not sans_fenetre:
        # Programme à fenêtre (Azahar) : lancement ordinaire, sans rediriger ses entrées/sorties ni changer
        # de groupe de processus. Vu en jeu (2026-09-26) : lancé avec stdin/stdout/stderr sur DEVNULL et
        # CREATE_NEW_PROCESS_GROUP, Azahar 2124.3 restait bloqué sans fenêtre (journal vide, stub GDB jamais
        # ouvert) ; le même Azahar lancé normalement (Start-Process) démarre et le client s'y connecte.
        return subprocess.Popen(cmd, close_fds=True)
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            **options_detachees(sans_fenetre))


def ecrire_atomique(p: Path, texte: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + ".tmp")
    t.write_text(texte, encoding="utf-8")
    os.replace(t, p)


# ------------------------------------------------------------------------------------------------ paquet
def candidats_patch() -> list[Path]:
    """Dossier des patchs du mod (code.bps, exheader.bps, manifeste.json) : variable YKW2AP_PATCH, puis
    `patch/` du paquet distribué (à côté de l'exécutable s'il est empaqueté), puis `build/ap_patch` du dépôt."""
    c = []
    if os.environ.get("YKW2AP_PATCH"):
        c.append(Path(os.environ["YKW2AP_PATCH"]))
    if gele():
        c.append(execution.dossier_application() / "patch")
    c += [ARCHIPELAGO.parent / "patch", ARCHIPELAGO.parent / "build" / "ap_patch"]
    return c


def trouver_patch() -> Path | None:
    for d in candidats_patch():
        if (d / "manifeste.json").is_file():
            return d
    return None


def fichier_aide() -> Path | None:
    for p in (execution.dossier_application() / "LISEZMOI.txt", ARCHIPELAGO.parent / "LISEZMOI.txt",
              ARCHIPELAGO / "lanceur" / "LISEZMOI.txt"):
        if p.is_file():
            return p
    return None


# ------------------------------------------------------------------------------------------------ connexion
def valider_serveur(texte: str) -> Msg | None:
    """Validation légère de l'adresse : « hôte », « hôte:port » ou « ws(s)://hôte[:port] » (port 1..65535, défaut
    38281 comme le client), sans espace, 127 octets au plus. None si elle convient."""
    t = texte.strip()
    if not t:
        return Msg("cx_serveur_vide")
    if len(t.encode("utf-8")) > SERVEUR_MAX_OCTETS:
        return Msg("cx_serveur_long")
    reste = t
    if "://" in t:
        schema, _s, reste = t.partition("://")
        if schema.lower() not in ("ws", "wss"):
            return Msg("cx_serveur_format")
    reste = reste.rstrip("/")
    if not reste or any(c.isspace() for c in reste) or "/" in reste or "@" in reste:
        return Msg("cx_serveur_format")
    try:
        u = urlsplit("//" + reste)
        port = u.port
    except ValueError:
        return Msg("cx_serveur_format")
    if not u.hostname or port == 0 or (reste.endswith(":") and port is None):
        return Msg("cx_serveur_format")
    return None


def valider_slot(texte: str) -> Msg | None:
    t = texte.strip()
    if not t:
        return Msg("cx_slot_vide")
    if len(t.encode("utf-8")) > SLOT_MAX_OCTETS:
        return Msg("cx_slot_long")
    return None


def valider_connexion(serveur: str, slot: str) -> dict[str, Msg]:
    """Erreurs par champ (« serveur », « slot ») ; vide si la saisie convient."""
    out = {}
    for cle, m in (("serveur", valider_serveur(serveur)), ("slot", valider_slot(slot))):
        if m is not None:
            out[cle] = m
    return out


# ------------------------------------------------------------------------------------------------ états
@dataclass
class EtatRom:
    ok: bool
    msg: Msg
    chemin: Path | None = None


@dataclass
class EtatMod:
    statut: str      # sans_paquet | sans_dossier | non_installe | a_jour | autre_version | modifie | illisible
    version_paquet: str | None = None
    version_installee: str | None = None
    libelle: bool = False                 # libellé « Archipelago » installé
    mis_de_cote: list[str] = field(default_factory=list)   # fichiers d'un autre mod qui seront sauvegardés
    detail: str = ""
    dossier: Path | None = None


@dataclass
class EtatGdb:
    statut: str      # actif | inactif | config_absente | azahar_absent
    port: int = az.PORT_GDB_DEFAUT
    fichier: Path | None = None


@dataclass
class EtatAzahar:
    executable: Path | None
    version: str | None
    validee: bool
    en_cours: bool | None
    gdb: EtatGdb
    dossier_mods: Path | None
    emulateur: str = "azahar"           # "zakuro" : Zakuro intégré (docs/systemes/version_pc.md)


def processus_vivant(pid: int) -> bool:
    import principal                              # archipelago/client (sur sys.path)
    return principal.processus_vivant(pid)


class ProcessusPid:
    """Processus connu par son seul PID (client de suivi démarré par une autre fenêtre du lanceur) : interface « façon
    Popen » réduite. `terminate` ne fait rien (on ne tue pas un client qu'on n'a pas lancé)."""

    def __init__(self, pid: int):
        self.pid = pid

    def poll(self) -> int | None:
        return None if processus_vivant(self.pid) else 0

    def wait(self, timeout: float | None = None) -> int:
        fin = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            if fin is not None and time.monotonic() >= fin:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(0.5)
        return 0

    def terminate(self) -> None:
        pass


@dataclass
class Session:
    client: Any                          # objets « façon Popen » : .pid, .poll(), .terminate()
    azahar: Any
    fichier_pid: Path
    debut: float


@dataclass
class EtatSession:
    client_actif: bool
    jeu_actif: bool
    phase: str | None                    # suivi | attente_jeu | jeu | arrete (fichier d'état du client)
    etat: int                            # code de connexion au serveur (0 inconnu, 1..5 : boite_protocole)
    message: str
    slot: str = ""
    serveur: str = ""
    erreur: int = 0                      # etat 4 : 1 injoignable, 2 slot inconnu, 3 mot de passe refusé, 4..6
    sauvegarde: str = ""                 # aucune | attente | liee | liaison | non_liee | autre | jeu_ancien | verrous_…
    raison_non_liee: str = ""            # sauvegarde non liée : pourquoi ce n'est pas une partie neuve (journal)

    @property
    def suivi_seul(self) -> bool:
        """Client actif sans le jeu (suivi seul : réseau seulement)."""
        return self.client_actif and self.phase == "suivi"


# ------------------------------------------------------------------------------------------------ lanceur
class Lanceur:
    def __init__(self, stockage: StockageConfig | None = None, *, dossier_patch: Path | None = None,
                 dossier_mods: Path | None = None, dossier_util_azahar: Path | None = None,
                 lancer_processus: Callable[..., Any] | None = None,
                 azahar_en_cours: Callable[[], bool | None] | None = None,
                 detecter_azahar: Callable[..., az.InfoAzahar] | None = None,
                 commande_client: list[str] | None = None, libelle: bool = True,
                 extraire_rom: Callable[..., rom3ds.ContenuRom] | None = None, icone: bool = True,
                 invitations: bool | None = None, candidats_zakuro: list[Path] | None = None,
                 source_maj: Any = "publique", identite_maj: Any = None, application_maj: Path | None = None,
                 exe_maj: Path | None = None, ouvrir_maj: Callable | None = None,
                 lancer_maj: Callable | None = None):
        self.stockage = stockage or StockageConfig()
        self.config: ConfigLocale = self.stockage.charger()
        self._dossier_patch = dossier_patch
        self._dossier_mods = dossier_mods
        self._dossier_util = dossier_util_azahar
        self.lancer_processus = lancer_processus or lancer_processus_defaut
        self._en_cours = azahar_en_cours or az.azahar_en_cours
        self._detecter = detecter_azahar or az.detecter
        self._commande_client = commande_client          # tests : remplace « python principal.py »
        self.libelle = libelle
        self.icone = icone                               # icône de l'objet vitrine en jeu (installation/icone.py)
        # objets du jeu « Invitation : <nom> » (installation/invitations.py) : facultatifs, tout ou rien ; sans eux les
        # invitations restent des objets Archipelago sans objet dans l'inventaire (l'invité vient quand même).
        # ACTIVÉ PAR DÉFAUT depuis l'essai en jeu du 2026-10-09 (décision de l'humain) : objets visibles dans le sac ;
        # une sauvegarde relue par un jeu SANS ces objets se charge sans plantage mais perd les enveloppes (rappel
        # visuel seulement : l'invité ne dépend pas de l'inventaire). YKW2_AP_INVITATIONS=0 les désactive.
        if invitations is None:
            invitations = os.environ.get("YKW2_AP_INVITATIONS", "").strip().lower() not in ("0", "non", "false", "off")
        self.invitations = invitations
        # (V3, lot 20 : les 16 objets ORDINAIRES du sac du lot 14, variable YKW2_AP_INVITATIONS_SAC, sont retirés avec
        # les invitations des Yo-kai de Pièce 5 étoiles : la variable n'est plus lue.)
        self._extraire = extraire_rom or rom3ds.extraire
        # Zakuro intégré (zakuro/zakuro.exe du paquet, ou YKW2AP_ZAKURO) ; tests : liste injectée (vide = absent)
        if candidats_zakuro is None:
            candidats_zakuro = zk.candidats_executable(execution.dossier_application() if gele() else None,
                                                       ARCHIPELAGO.parent)
        self._candidats_zakuro = candidats_zakuro
        # mise à jour du lanceur (maj.py) ; tests : source locale, faux paquet, aucun vrai processus
        self.maj_source = maj_mod.source_publique() if source_maj == "publique" else source_maj
        self._maj_identite, self._maj_application = identite_maj, application_maj
        self._maj_exe, self._maj_ouvrir, self._maj_lancer = exe_maj, ouvrir_maj, lancer_maj
        self._info: az.InfoAzahar | None = None
        self._rom_ok: tuple | None = None                # (chemin, taille, date) de la dernière ROM vérifiée
        self._client: Any = None                         # client lancé par CE lanceur (suivi seul, puis jeu)
        if not self.client_en_cours():                   # mot de passe transmis jamais lu par un client : effacé
            self.purger_transmis()

    # ---------------------------------------------------------------- configuration
    def _memoriser(self, **champs) -> None:
        """Relit la configuration avant d'écrire (sous le verrou) : rien de ce qu'un autre processus y a écrit n'est
        perdu."""
        c = self.stockage.modifier(**champs)
        for k in champs:
            setattr(self.config, k, getattr(c, k))

    def langue(self) -> str:
        return self.config.langue_lanceur

    def changer_langue(self, langue: str) -> None:
        self._memoriser(langue_lanceur=langue)

    def changer_suivi_carte(self, actif: bool) -> None:
        """Case « Suivre le jeu » du sous-onglet « Carte » (onglet « Checks ») : mémorisée."""
        self._memoriser(carte_suivre=bool(actif))

    def changer_epingle(self, cle: str | None) -> None:
        """Yo-kai épinglé depuis l'onglet « Yo-kai » (ses points d'apparition sur le sous-onglet « Carte ») : clé du
        tracker (« b<base> »), mémorisée ; None ou "" : aucun."""
        self._memoriser(yokai_epingle=str(cle or ""))

    @property
    def dossier_journaux(self) -> Path:
        return self.stockage.dossier_journaux

    # ---------------------------------------------------------------- mise à jour du lanceur (maj.py)
    def maj_application(self) -> Path:
        return self._maj_application or execution.dossier_application()

    def maj_identite(self) -> maj_mod.Identite:
        return self._maj_identite or maj_mod.lire_identite(self.maj_application(), gele())

    def maj_possible(self) -> bool:
        """Une source est définie et ce lanceur est un paquet (jamais depuis le dépôt) : la case existe."""
        return self.maj_source is not None and self.maj_identite().forme != "depot"

    def maj_verifier_actif(self) -> bool:
        return self.maj_possible() and self.config.maj_verifier

    def changer_maj_verifier(self, actif: bool) -> None:
        """Case « Vérifier les mises à jour au lancement » (onglet « Réglages ») : mémorisée."""
        self._memoriser(maj_verifier=bool(actif))

    def verifier_maj(self) -> maj_mod.Annonce | None:
        """Toujours silencieux (fil de fond) ; aucune requête si la case est décochée ou sans source."""
        if not self.maj_verifier_actif():
            return None
        return maj_mod.verifier(self.maj_source, self.maj_identite(), self._maj_ouvrir or maj_mod.ouvrir_url)

    def refus_maj(self, session: "Session | None" = None) -> Msg | None:
        """Pourquoi la mise à jour est refusée en ce moment (bouton grisé), ou None. Le client de SUIVI seul ne
        compte pas : il ne touche pas au jeu et `installer_maj` l'arrête, comme le ferait la fermeture du lanceur."""
        exe = self._maj_exe or Path(sys.executable)
        if exe.name != maj_outil.NOM_EXE:
            return Msg("maj_refus_renomme", {"nom": maj_outil.NOM_EXE})
        if self._en_cours() is not False:
            return Msg("maj_refus_azahar")
        if self.zakuro_en_cours() is not False:
            return Msg("maj_refus_zakuro")
        s = self.etat_session(session)
        if s.client_actif and not s.suivi_seul:
            return Msg("maj_refus_client")
        return None

    def installer_maj(self, annonce: maj_mod.Annonce, session: "Session | None" = None,
                      rappel: Callable[[Msg], None] | None = None) -> None:
        """Prépare la mise à jour et lance l'outil de remplacement ; la vue ferme ensuite le lanceur. Lève
        ErreurLanceur si elle n'a pas lieu : la version en place n'a alors pas été touchée."""
        def controle() -> None:                          # dernier contrôle, juste avant de partir
            r = self.refus_maj(session)
            if r is not None:
                raise ErreurLanceur(r)
            self.deconnecter_suivi()
        kw = {}
        if self._maj_ouvrir is not None:
            kw["ouvrir"] = self._maj_ouvrir
        if self._maj_lancer is not None:
            kw["lancer"] = self._maj_lancer
        dire = rappel or (lambda m: None)
        try:
            maj_mod.preparer(annonce, self.maj_source, self.maj_application(), self._maj_exe or Path(sys.executable),
                             self.stockage.dossier, controle, rappel=lambda c, p: dire(Msg(c, p)), **kw)
        except maj_mod.ErreurMaj as e:
            raise ErreurLanceur(Msg(e.cle, e.params)) from e
        except ErreurLanceur:
            raise
        except Exception as e:                            # noqa: BLE001 - montré au joueur, rien n'a changé
            raise ErreurLanceur(Msg("maj_echec", {"detail": repr(e)})) from e

    def nettoyer_maj(self) -> None:
        """Restes de la mise à jour précédente (paquet exécutable seulement : ailleurs, aucun `.maj/`)."""
        if self.maj_identite().forme == "exe":
            maj_mod.nettoyer_restes(self.maj_application())

    def resultat_maj(self) -> Msg | None:
        """Message sur la dernière mise à jour (une seule fois), montré à l'ouverture."""
        r = maj_outil.lire_resultat(self.stockage.dossier)
        if r is None:
            return None
        if r.get("ok"):
            return Msg("maj_reussie", {"version": str(r.get("version", "?"))})
        raison = str(r.get("raison", "inattendue"))
        if raison not in ("lanceur_ouvert", "fichiers_ouverts", "controle", "retour_impossible", "interrompue"):
            raison = "inattendue"
        return Msg("maj_echec_" + raison, {"detail": str(r.get("detail", ""))})

    # ---------------------------------------------------------------- connexion Archipelago
    def relire_connexion(self) -> ConfigLocale | None:
        """Configuration du disque si une saisie plus récente (autre fenêtre du lanceur) y a été écrite depuis la
        dernière lecture ; None sinon. Lecture seule (aucune écriture)."""
        if self.stockage.revision_disque() <= self.config.revision_connexion:
            return None
        self.config = self.stockage.charger()
        return self.config

    def connexion_modifiee(self, serveur: str, slot: str, mot_de_passe: str | None, memoriser: bool) -> bool:
        """La saisie du formulaire diffère-t-elle de config.json ? (`mot_de_passe` None : non modifié.)"""
        d = self.stockage.charger()
        return ((serveur.strip(), slot.strip(), bool(memoriser)) != (d.serveur, d.slot, d.memoriser_mot_de_passe)
                or (mot_de_passe is not None and mot_de_passe != d.mot_de_passe))

    def enregistrer_connexion(self, serveur: str, slot: str, mot_de_passe: str | None, memoriser: bool) -> Msg:
        """Saisie de la carte « Connexion Archipelago » -> config.json (nouvelle révision : la plus récente gagne ;
        un client qui tourne se reconnecte). `mot_de_passe` None = inchangé. Lève ErreurLanceur si la saisie ne
        convient pas (premier problème). Le mot de passe n'est jamais journalisé."""
        erreurs = valider_connexion(serveur, slot)
        if erreurs:
            raise ErreurLanceur(next(iter(erreurs.values())))
        try:
            self.config = self.stockage.enregistrer_connexion(serveur, slot, mot_de_passe, memoriser=memoriser,
                                                              source="lanceur")
        except OSError as e:
            raise ErreurLanceur(Msg("cx_echec", {"detail": str(e)})) from e
        if mot_de_passe and not memoriser and not config_locale.chiffrement_disponible():
            return Msg("cx_mdp_non_transmis")
        return Msg("cx_enregistre_client" if self.client_en_cours() else "cx_enregistre")

    def preparer_connexion(self, serveur: str, slot: str, mot_de_passe: str | None, memoriser: bool) -> Msg | None:
        """« Jouer » : enregistre la saisie si elle a changé. La connexion ne se saisit plus dans le jeu (2026-09-28) :
        rien de configuré -> ErreurLanceur (« cx_requise »), comme une saisie qui ne convient pas."""
        if not self.connexion_modifiee(serveur, slot, mot_de_passe, memoriser):
            if not self.stockage.charger().configuree:
                raise ErreurLanceur(Msg("cx_requise"))
            return None
        if not serveur.strip() and not slot.strip():
            raise ErreurLanceur(Msg("cx_requise"))
        return self.enregistrer_connexion(serveur, slot, mot_de_passe, memoriser)

    def client_en_cours(self, session: "Session | None" = None) -> bool:
        return self.etat_session(session).client_actif

    def purger_transmis(self) -> None:
        """Efface un mot de passe transmis (non mémorisé) qu'aucun client n'a lu : il ne reste pas sur le disque."""
        try:
            if self.stockage.consommer_transmis():
                self.config = self.stockage.charger()
        except OSError:
            pass

    # ---------------------------------------------------------------- ROM
    @staticmethod
    def _cle_fichier(p: Path) -> tuple:
        st = p.stat()
        return (str(p), st.st_size, st.st_mtime_ns)

    def verifier_rom(self, chemin: str | Path | None = None) -> EtatRom:
        if chemin is None:
            chemin = self.config.rom
        if not chemin:
            return EtatRom(False, Msg("rom_aucune"))
        p = Path(chemin)
        if not p.is_file():
            return EtatRom(False, Msg("rom_introuvable", {"chemin": str(p)}), p)
        try:
            if self._rom_ok == self._cle_fichier(p):
                return EtatRom(True, Msg("rom_ok"), p)
            self._extraire(p)
        except rom3ds.RomChiffree as e:
            return EtatRom(False, Msg("rom_chiffree", {"detail": str(e)}), p)
        except rom3ds.VersionNonPriseEnCharge as e:
            return EtatRom(False, Msg("rom_version", {"detail": str(e)}), p)
        except rom3ds.FormatInconnu as e:
            return EtatRom(False, Msg("rom_format", {"detail": str(e)}), p)
        except (rom3ds.ErreurRom, OSError, ValueError) as e:
            return EtatRom(False, Msg("rom_abimee", {"detail": str(e)}), p)
        self._rom_ok = self._cle_fichier(p)
        return EtatRom(True, Msg("rom_ok"), p)

    def choisir_rom(self, chemin: str | Path) -> EtatRom:
        r = self.verifier_rom(chemin)
        if r.ok:
            self._memoriser(rom=str(Path(chemin).resolve()))
        return r

    # ---------------------------------------------------------------- émulateur (Zakuro intégré ou Azahar)
    def zakuro(self) -> Path | None:
        """`zakuro.exe` fourni avec le lanceur, s'il y est."""
        return zk.trouver_executable(self._candidats_zakuro)

    def emulateur(self) -> str:
        """« zakuro » (intégré, par défaut quand il est fourni) ou « azahar »."""
        choix = self.config.emulateur
        if choix == "azahar":
            return "azahar"
        return "zakuro" if self.zakuro() is not None else "azahar"

    def choisir_emulateur(self, nom: str) -> bool:
        if nom not in ("azahar", "zakuro") or (nom == "zakuro" and self.zakuro() is None):
            return False
        self._memoriser(emulateur=nom)
        self._info = None
        return True

    def zakuro_en_cours(self) -> bool | None:
        return zk.en_cours()

    def _emulateur_ouvert(self) -> bool | None:
        return self.zakuro_en_cours() if self.emulateur() == "zakuro" else self._en_cours()

    def choisir_azahar(self, chemin: str | Path) -> bool:
        """Choix d'un exécutable : `zakuro.exe` (celui du paquet) choisit Zakuro intégré, tout autre Azahar."""
        p = Path(chemin)
        if not p.is_file():
            return False
        z = self.zakuro()
        if z is not None and p.resolve() == z.resolve():
            return self.choisir_emulateur("zakuro")
        self._memoriser(azahar=str(p.resolve()), emulateur="azahar")
        self._info = None
        return True

    def info_azahar(self, rafraichir: bool = False) -> az.InfoAzahar:
        if self._info is None or rafraichir:
            exe = Path(self.config.azahar) if self.config.azahar else None
            if exe is not None and not exe.is_file():
                exe = None
            self._info = self._detecter(exe, self._dossier_util)
            if exe is None and self._info.executable is not None:
                self._memoriser(azahar=str(self._info.executable))
        return self._info

    def etat_gdb(self, info: az.InfoAzahar | None = None) -> EtatGdb:
        info = info or self.info_azahar()
        if info.dossier_utilisateur is None:
            return EtatGdb("azahar_absent")
        fichier = az.fichier_config(info.dossier_utilisateur)
        if info.reglages_gdb is None:
            return EtatGdb("config_absente", fichier=fichier)
        g = info.reglages_gdb
        return EtatGdb("actif" if g.actif else "inactif", g.port, g.fichier)

    def etat_azahar(self, rafraichir: bool = False) -> EtatAzahar:
        if self.emulateur() == "zakuro":           # rien à détecter ni à régler : stub GDB par la ligne de commande
            return EtatAzahar(self.zakuro(), "zakuro", True, self.zakuro_en_cours(),
                              EtatGdb("actif", self.config.port_gdb), self.dossier_mods(), "zakuro")
        info = self.info_azahar(rafraichir)
        return EtatAzahar(info.executable, info.version, info.version_validee, self._en_cours(),
                          self.etat_gdb(info), self.dossier_mods(info))

    def activer_gdb(self, accord: bool) -> Path | None:
        """Active le stub GDB dans qt-config.ini. Exige l'accord explicite du joueur et Azahar fermé.
        Renvoie la copie de sauvegarde (None si rien n'a changé)."""
        if not accord:
            raise ErreurLanceur(Msg("gdb_refuse"))
        g = self.etat_gdb(self.info_azahar(True))
        if g.statut == "azahar_absent":
            raise ErreurLanceur(Msg("azahar_absent"))
        if g.statut == "config_absente":
            raise ErreurLanceur(Msg("gdb_config_absente", {"fichier": str(g.fichier)}))
        if self._en_cours():
            raise ErreurLanceur(Msg("azahar_ouvert_config"))
        try:
            sauvegarde = az.activer_stub_gdb(g.fichier, g.port, accord=True)
        except (OSError, UnicodeDecodeError) as e:
            raise ErreurLanceur(Msg("gdb_echec", {"detail": str(e)})) from e
        self._info = None
        return sauvegarde

    # ---------------------------------------------------------------- mod
    def dossier_patch(self) -> Path | None:
        return self._dossier_patch or trouver_patch()

    def patch(self) -> inst.Patch:
        d = self.dossier_patch()
        if d is None or not (d / "manifeste.json").is_file():
            raise ErreurLanceur(Msg("paquet_absent"))
        try:
            return inst.charger_patch(d)
        except inst.ErreurInstallation as e:
            raise ErreurLanceur(Msg("paquet_abime", {"detail": str(e)})) from e

    def dossier_mods(self, info: az.InfoAzahar | None = None) -> Path | None:
        if self._dossier_mods is not None:
            return self._dossier_mods
        if self.emulateur() == "zakuro":
            return zk.dossier_mods(self.stockage.dossier)
        info = info or self.info_azahar()
        return info.dossier_mods

    def etat_mod(self) -> EtatMod:
        try:
            patch = self.patch()
        except ErreurLanceur as e:
            return EtatMod("sans_paquet", detail=e.msg.params.get("detail", ""))
        mods = self.dossier_mods()
        if mods is None:
            return EtatMod("sans_dossier", patch.version)
        titre = inst.dossier_titre(mods)
        try:
            est = inst.lire_estampille(mods)
        except inst.ErreurInstallation as e:
            return EtatMod("illisible", patch.version, detail=str(e), dossier=titre)
        if est is None:
            autres = [n for n in inst.FICHIERS_MOD + inst.FICHIERS_EN_CONFLIT if (titre / n).is_file()]
            return EtatMod("non_installe", patch.version, mis_de_cote=autres, dossier=titre)
        version = est.get("version")
        libelle = bool(est.get("infos", {}).get("libelle"))
        for n, s in est.get("fichiers", {}).items():
            p = titre / n
            if not p.is_file() or inst.sha1_fichier(p) != s:
                return EtatMod("modifie", patch.version, version, libelle, detail=str(p), dossier=titre)
        f = est.get("fichiers", {})
        a_jour = (version == patch.version and f.get("code.bin") == patch.manifeste["code"]["cible_sha1"]
                  and f.get("exheader.bin") == patch.manifeste["exheader"]["cible_sha1"])
        return EtatMod("a_jour" if a_jour else "autre_version", patch.version, version, libelle, dossier=titre)

    def _exiger_azahar_ferme(self) -> None:
        if self._emulateur_ouvert():
            raise ErreurLanceur(Msg("zakuro_ouvert_mod" if self.emulateur() == "zakuro" else "azahar_ouvert_mod"))

    def _preparer_romfs(self, rom: Path, mods: Path) -> tuple[dict[str, bytes], list[str], dict]:
        """Patchs `romfs_ext/` (libellé, icône, objets « Invitation », apparence du personnage) : (fichiers,
        avertissements, champs de l'estampille). Le réglage d'apparence est relu dans `config.json` ; sans réglage,
        ni paramètre ni champ en plus (installation identique à celle d'avant l'onglet « Apparence »)."""
        reglage = self.reglage_apparence_effectif()
        empreinte = app_mod.empreinte(reglage)
        supp, avert, infos = {}, [], {}
        if self.libelle or self.icone or self.invitations or empreinte:
            inf = {"libelle": [], "icone": [], "invitations": []}
            kw = {"apparence": reglage} if empreinte else {}
            try:
                supp, avert, inf = inst.preparer_romfs(rom, mods, libelle=self.libelle, icone=self.icone,
                                                       invitations=self.invitations, **kw)
            except inst.ErreurInstallation as e:
                avert = [f"libellé, icône, objets « Invitation » et apparence non installés : {e}"]
            for cle, actif in (("libelle", self.libelle), ("icone", self.icone),
                               ("invitations", self.invitations)):
                if actif:
                    infos[cle] = sorted(inf.get(cle, []))
            if empreinte:
                infos["apparence"] = sorted(inf.get("apparence", []))
                infos["apparence_empreinte"] = empreinte
                if not infos["apparence"]:
                    infos["apparence_erreur"] = next((a for a in avert if "pparence" in a), "") or \
                        "archive non modifiable"
        return supp, avert, infos

    # ---------------------------------------------------------------- apparence du personnage (onglet « Réglages »)
    def reglage_apparence(self) -> dict:
        """Réglage d'apparence de `config.json` (relu : l'écriture d'une autre fenêtre du lanceur compte)."""
        a = self.stockage.lire_brut().get("apparence")        # brut : sans déchiffrer le mot de passe
        return dict(a) if isinstance(a, dict) else {}

    def changer_apparence(self, reglage: dict) -> None:
        """Mémorise le réglage (relire - modifier - écrire sous le verrou) ; appliqué au prochain « Jouer »."""
        self._memoriser(apparence={p: dict(r) for p, r in (reglage or {}).items() if isinstance(r, dict)})

    def reglage_apparence_effectif(self) -> dict:
        """Réglage appliqué au « Jouer » : celui de l'onglet + le mod d'apparence importé s'il est utilisé (clé
        `import`, jamais écrite dans `config.json` : dossier et empreinte relus à chaque fois)."""
        r = self.reglage_apparence()
        if self.import_apparence_actif():
            imp = app_imp.reglage(self.stockage.dossier)
            if imp is not None:
                r["import"] = imp
        return r

    # mod d'apparence importé (bouton « Importer un mod d'apparence ») ---------------------------------------------
    def import_apparence(self) -> dict | None:
        """Manifeste du mod importé (None : aucun)."""
        return app_imp.lire_manifeste(self.stockage.dossier)

    def import_apparence_actif(self) -> bool:
        return self.stockage.lire_brut().get("apparence_import") is True

    def changer_import_apparence(self, actif: bool) -> None:
        """Case « Utiliser le mod importé » (relire - modifier - écrire) ; appliquée au prochain « Jouer »."""
        self._memoriser(apparence_import=bool(actif))

    def importer_apparence(self, chemin: str | Path, progres=None) -> dict:
        """Analyse le mod `chemin` (zip, dossier, yw2_a.fa) contre la ROM du joueur, copie les fichiers retenus dans
        le dossier de données (à la place d'un import précédent) et l'active. app_imp.ErreurImport si rien n'est
        retenu (l'import précédent est alors gardé). Renvoie le manifeste."""
        rom = self.config.rom or ""
        if not rom or not Path(rom).exists():
            raise app_imp.ErreurImport("app_imp_sans_rom")
        an = app_imp.analyser(app_mod.L.SourceRomfs(rom), chemin, progres)
        m = app_imp.enregistrer(an, self.stockage.dossier)
        self.changer_import_apparence(True)
        return m

    def retirer_import_apparence(self) -> None:
        """Retire le mod importé (copie locale supprimée, case décochée) ; le jeu le perd au prochain « Jouer »."""
        app_imp.retirer(self.stockage.dossier)
        self.changer_import_apparence(False)

    def etat_apparence(self) -> Msg:
        """État du réglage d'apparence par rapport au mod installé (clés `app_etat_*` de textes_apparence.py)."""
        voulu = app_mod.empreinte(self.reglage_apparence_effectif())
        mods = self.dossier_mods()
        try:
            est = inst.lire_estampille(mods) if mods is not None else None
        except inst.ErreurInstallation as e:
            return Msg("app_etat_inconnu", {"detail": str(e)})
        if est is None:
            return Msg("app_etat_sans_mod" if voulu else "app_etat_origine")
        infos = est.get("infos", {})
        if infos.get("apparence_empreinte", "") != voulu:
            return Msg("app_etat_attente")
        if not voulu:
            return Msg("app_etat_origine")
        if not infos.get("apparence"):
            return Msg("app_etat_echec", {"detail": infos.get("apparence_erreur", "")})
        return Msg("app_etat_applique")

    def apparence_a_appliquer(self) -> bool:
        """Le mod est installé et son apparence n'est pas celle du réglage (« Jouer » refait alors le patch)."""
        mods = self.dossier_mods()
        try:
            est = inst.lire_estampille(mods) if mods is not None else None
        except inst.ErreurInstallation:
            return False
        if est is None:
            return False
        return est.get("infos", {}).get("apparence_empreinte", "") !=             app_mod.empreinte(self.reglage_apparence_effectif())

    def appliquer_apparence(self, rom: str | Path | None = None) -> inst.Rapport:
        """Refait les seuls patchs `romfs_ext/` du mod installé avec le réglage d'apparence courant : code.bin et
        exheader.bin restent ceux de l'installation (relus, contrôlés par leur SHA-1), aucune recompilation (Zakuro lit
        le RomFS par LayeredFS). Le jeu doit être fermé."""
        self._exiger_azahar_ferme()
        rom = Path(rom or self.config.rom or "")
        r = self.verifier_rom(rom) if str(rom) not in ("", ".") else EtatRom(False, Msg("rom_aucune"))
        if not r.ok:
            raise ErreurLanceur(r.msg)
        mods = self.dossier_mods()
        if mods is None:
            raise ErreurLanceur(Msg("dossier_mods_absent"))
        try:
            est = inst.lire_estampille(mods)
            if est is None:
                return self.installer(rom)
            titre = inst.dossier_titre(mods)
            code, exh = (titre / "code.bin").read_bytes(), (titre / "exheader.bin").read_bytes()
            supp, avert, maj = self._preparer_romfs(rom, mods)
            # fichiers de la musique aléatoire (romfs/snd/product/…) : gardés tels quels, comme `infos.musique`
            from . import musique_option as MO
            for n in est.get("fichiers", {}):
                if MO.est_fichier_musique(n):
                    supp[n] = (titre / n).read_bytes()
            infos = {k: v for k, v in est.get("infos", {}).items()
                     if k not in ("apparence", "apparence_empreinte", "apparence_erreur")}
            infos.update(maj)
            return inst.installer_fichiers(code, exh, mods, est.get("version"), infos, supp, avert)
        except inst.ErreurInstallation as e:
            raise ErreurLanceur(Msg("installation_echec", {"detail": str(e)})) from e
        except OSError as e:
            raise ErreurLanceur(Msg("installation_echec", {"detail": str(e)})) from e

    def installer(self, rom: str | Path | None = None,
                  rappel: Callable[[Msg], None] | None = None) -> inst.Rapport:
        """Installe (ou met à jour) le mod depuis la ROM du joueur ; libellé « Archipelago », icône de l'objet
        vitrine et objets « Invitation » de l'inventaire si possible (un échec de l'un d'eux n'empêche pas
        l'installation : avertissement)."""
        self._exiger_azahar_ferme()
        patch = self.patch()
        rom = Path(rom or self.config.rom or "")
        r = self.verifier_rom(rom) if str(rom) not in ("", ".") else EtatRom(False, Msg("rom_aucune"))
        if not r.ok:
            raise ErreurLanceur(r.msg)
        mods = self.dossier_mods()
        if mods is None:
            raise ErreurLanceur(Msg("dossier_mods_absent"))
        try:
            contenu = self._extraire(rom)
            code_mod, exh_mod = inst.appliquer_patchs(contenu.code, contenu.exheader, patch)
            infos = {"source_code_sha1": contenu.sha1_code, "source_exheader_sha1": contenu.sha1_exheader,
                     "code_produit": contenu.code_produit, "lanceur": VERSION_LANCEUR}
            supp, avert, maj = self._preparer_romfs(rom, mods)
            infos.update(maj)
            # musique aléatoire (option cosmétique, lanceur/musique_option.py) : rien sans la case cochée
            from . import musique_option as MO
            m_supp, m_avert, m_info = MO.fichiers(rom, mods, *MO.reglage(self.config), self.emulateur(),
                                                  (inst.lire_estampille(mods) or {}).get("fichiers", {}))
            if m_info is not None:
                supp = {**supp, **m_supp}
                avert = list(avert) + m_avert
                infos["musique"] = m_info
            # randomizer de Yo-kai (R2) : base locale des rencontres, générée depuis la ROM du joueur dans son dossier
            # de données (jamais distribuée) ; un échec n'empêche pas l'installation (noté dans l'estampille : le client
            # refusera le mélange avec « Réparer le mod », ou refera la base depuis la ROM configurée)
            try:
                from installation import rencontres as renc
                renc.generer_fichier(rom, self.stockage.dossier)
                infos["rencontres"] = "generee"
            except Exception as e:  # noqa: BLE001 - la base est facultative pour installer
                infos["rencontres"] = f"non generee : {e}"
            # tracker de Yo-kai (R5) : noms des cartes et des tribus, n° du Médaillium, lus dans la ROM du joueur
            # (noms_local.json, jamais distribué) ; facultatif (l'onglet « Yo-kai » affiche alors régions et identifiants)
            try:
                from . import noms_locaux
                noms_locaux.generer_fichier(rom, self.stockage.dossier)
                infos["noms_locaux"] = "generes"
            except Exception as e:  # noqa: BLE001 - facultatif
                infos["noms_locaux"] = f"non generes : {e}"
            # boutiques (archipelago_boutiques.md §9) : hachages des articles lus dans la ROM du joueur
            # (boutiques_local.json, jamais distribué) ; un échec n'empêche pas l'installation (le client refait la
            # table depuis la ROM configurée, ou refuse une graine à boutiques si la ROM ne correspond pas)
            try:
                from installation import boutiques as bq
                bq.generer_fichier(rom, self.stockage.dossier)
                infos["boutiques"] = "generees"
            except Exception as e:  # noqa: BLE001 - facultatif pour installer
                infos["boutiques"] = f"non generees : {e}"
            # V3, lot C1 : distributeurs (identifiants de leurs points lus dans la ROM du joueur, distributeurs_local.json,
            # jamais distribué) ; facultatif comme les boutiques (le client refait la table depuis la ROM configurée)
            try:
                from installation import distributeurs as di
                di.generer_fichier(rom, self.stockage.dossier)
                infos["distributeurs"] = "generes"
            except Exception as e:  # noqa: BLE001 - facultatif pour installer
                infos["distributeurs"] = f"non generes : {e}"
            # V3, lot B1 : lots du Bingo-kai (bingo_local.json, lus dans la ROM du joueur, jamais distribués) ; facultatif
            # (le client refait le fichier depuis la ROM configurée ; sans lui, Bingo-kai d'origine)
            try:
                from installation import bingo_lots as ib
                ib.generer_fichier(rom, self.stockage.dossier)
                infos["bingo"] = "generes"
            except Exception as e:  # noqa: BLE001 - facultatif pour installer
                infos["bingo"] = f"non generes : {e}"
            rapport = inst.installer_fichiers(code_mod, exh_mod, mods, patch.version, infos, supp, avert)
            if self.emulateur() == "zakuro":           # le code PC du jeu moddé, produit chez le joueur
                self.recompiler(rom, rappel)
            return rapport
        except inst.ErreurInstallation as e:
            raise ErreurLanceur(Msg("installation_echec", {"detail": str(e)})) from e
        except rom3ds.ErreurRom as e:
            raise ErreurLanceur(Msg("rom_abimee", {"detail": str(e)})) from e

    def a_recompiler(self) -> bool:
        return self.emulateur() == "zakuro" and zk.a_recompiler(self.stockage.dossier, self.zakuro())

    def recompiler(self, rom: str | Path | None = None, rappel: Callable[[Msg], None] | None = None) -> None:
        """Zakuro : recompile le jeu moddé en code PC (~5 min la première fois, téléchargement de Zig
        compris si besoin ; ensuite incrémentale : seuls les fichiers C changés, souvent moins d'une minute)."""
        exe = self.zakuro()
        if exe is None:
            raise ErreurLanceur(Msg("zakuro_absent"))
        rom = Path(rom or self.config.rom or "")
        dire = rappel or (lambda m: None)
        dire(Msg("etape_recompilation", {"pct": 0}))
        try:
            zk.recompiler(exe, rom, self.stockage.dossier,
                          progression=lambda n, _t: dire(Msg("etape_recompilation", {"pct": n})))
        except zk.ErreurZakuro as e:
            raise ErreurLanceur(Msg("recompilation_echec", {"detail": str(e)})) from e

    def generer_cartes(self, *, progression=None, arret=None) -> Path:
        """Cartes du tracker (sous-onglet « Carte » de « Checks ») : minicartes PNG, positions et icônes générées depuis
        la ROM configurée dans le dossier de données (`cartes/`, jamais distribué) ; ~1 min, appelée en tâche de fond
        par la vue après l'installation ou la réparation, ou à l'ouverture du sous-onglet si elles manquent."""
        rom = Path(self.config.rom or "")
        if str(rom) in ("", ".") or not rom.is_file():
            raise ErreurLanceur(Msg("rom_aucune"))
        import checks_local as ck
        from installation import cartes
        logique = ck.logique_apworld()
        if logique is None:
            raise ErreurLanceur(Msg("installation_echec", {"detail": "logique de l'APWorld introuvable"}))
        return cartes.generer(rom, self.stockage.dossier, logique, progression=progression, arret=arret)

    def desinstaller(self) -> inst.Rapport:
        self._exiger_azahar_ferme()
        mods = self.dossier_mods()
        if mods is None:
            raise ErreurLanceur(Msg("dossier_mods_absent"))
        try:
            return inst.desinstaller(mods)
        except inst.ErreurInstallation as e:
            raise ErreurLanceur(Msg("desinstallation_echec", {"detail": str(e)})) from e

    def reparer(self, rappel: Callable[[Msg], None] | None = None) -> inst.Rapport:
        """Réinstallation complète : désinstallation (retour à l'état d'avant) puis installation."""
        self._exiger_azahar_ferme()
        if self.etat_mod().statut not in ("non_installe",):
            self.desinstaller()
        return self.installer(rappel=rappel)

    # ---------------------------------------------------------------- jouer
    def problemes(self, etat_az: EtatAzahar | None = None, verifier_mod: bool = True) -> list[Msg]:
        """Ce qui empêche de jouer (hors installation du mod, que « Jouer » fait lui-même si besoin)."""
        out = []
        r = self.verifier_rom()
        if not r.ok:
            out.append(r.msg)
        e = etat_az or self.etat_azahar()
        if e.executable is None:
            out.append(Msg("azahar_absent"))
        elif e.gdb.statut != "actif":
            out.append(Msg("gdb_" + e.gdb.statut))
        if e.en_cours:
            out.append(Msg("zakuro_ouvert_jeu" if e.emulateur == "zakuro" else "azahar_ouvert_jeu"))
        m = self.etat_mod() if verifier_mod else EtatMod("a_jour")
        if m.statut in ("sans_paquet", "sans_dossier", "modifie", "illisible"):
            out.append(Msg("mod_" + m.statut, {"detail": m.detail}))
        return out

    def commande_client(self, fichier_pid: Path | None, port: int, console: bool = False) -> list[str]:
        """Ligne de commande du client. `fichier_pid` None : suivi seul (`--suivi`, arrêt avec ce lanceur) ; sinon
        l'ancien mode (attente du jeu, arrêt avec Azahar), gardé pour le débogage."""
        if self._commande_client is not None:
            base = list(self._commande_client)
        else:               # `python[w] client/principal.py`, ou `<exécutable> --role client` (empaqueté)
            base = execution.commande("client", console=console)
        cmd = base + ["--dossier", str(self.stockage.dossier), "--port", str(port)]
        if fichier_pid is None:
            cmd += ["--suivi", "--lanceur-pid", str(os.getpid())]
        else:
            cmd += ["--quitter-avec-fichier", str(fichier_pid)]
        return cmd + (["--console"] if console else [])

    def lire_etat_client(self) -> dict | None:
        try:
            d = json.loads((self.stockage.dossier / FICHIER_ETAT).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return d if isinstance(d, dict) else None

    # ---------------------------------------------------------------- suivi seul (client sans le jeu)
    def enregistrer_presence(self) -> None:
        """Ce lanceur est ouvert (`lanceur.pid`) : le client de suivi vit tant qu'il l'est. Appelée par la vue."""
        try:
            ecrire_atomique(self.stockage.dossier / FICHIER_LANCEUR, str(os.getpid()))
        except OSError:
            pass

    def fermer(self) -> None:
        """Fermeture de la fenêtre : `lanceur.pid` effacé s'il est le nôtre (le client de suivi s'arrête alors seul, sauf
        jeu en cours) ; mot de passe transmis jamais lu effacé."""
        f = self.stockage.dossier / FICHIER_LANCEUR
        try:
            if f.read_text(encoding="ascii").strip() == str(os.getpid()):
                f.unlink()
        except (OSError, ValueError):
            pass
        if not self.client_en_cours():
            self.purger_transmis()

    def etat_client_vivant(self) -> dict | None:
        """etat.json d'un client qui tourne (récent, pas arrêté), sinon None."""
        e = self.lire_etat_client()
        if e is None or e.get("phase") == "arrete":
            return None
        try:
            recent = time.time() - float(e.get("horodatage", 0)) < ETAT_PERIME
        except (TypeError, ValueError):
            recent = False
        c = self._client
        if c is not None and c.pid == e.get("pid") and c.poll() is None:
            return e
        return e if recent else None

    def _demander(self, action: str, **params) -> str:
        nonce = secrets.token_hex(8)
        ecrire_atomique(self.stockage.dossier / FICHIER_DEMANDE,
                        json.dumps(dict(params, nonce=nonce, action=action, horodatage=time.time()), ensure_ascii=False))
        return nonce

    def _attendre_accuse(self, nonce: str, attente: float) -> dict | None:
        """etat.json qui accuse réception de la demande `nonce` (None : pas de réponse dans le délai)."""
        limite = time.monotonic() + attente
        while True:
            e = self.lire_etat_client()
            if e is not None and e.get("demande") == nonce:
                return e
            if time.monotonic() >= limite:
                return None
            time.sleep(0.05)

    def _lancer_client_suivi(self, port: int, attente: float, console: bool = False) -> Any:
        """Démarre le client en suivi seul et attend son premier etat.json (ErreurLanceur sinon)."""
        dossier = self.stockage.dossier
        dossier.mkdir(parents=True, exist_ok=True)
        for f in (dossier / FICHIER_ETAT, dossier / FICHIER_DEMANDE):
            f.unlink(missing_ok=True)
        self.enregistrer_presence()
        try:
            client = self.lancer_processus(self.commande_client(None, port, console), sans_fenetre=not console,
                                           console=console)
        except OSError as e:
            raise ErreurLanceur(Msg("client_echec", {"detail": str(e)})) from e
        limite = time.monotonic() + attente
        while True:
            code = client.poll()
            if code is not None:
                raise ErreurLanceur(Msg("client_deja" if code == 1 else "client_echec", {"detail": f"code {code}"}))
            e = self.lire_etat_client()
            if e is not None and e.get("phase") != "arrete" and (e.get("pid") == client.pid or gele()):
                break
            if time.monotonic() >= limite:
                _terminer(client)
                raise ErreurLanceur(Msg("client_lent"))
            time.sleep(0.1)
        self._client = client
        return client

    def demarrer_suivi(self, attente: float = 15.0) -> Msg:
        """Client en suivi seul (serveur Archipelago sans le jeu : Checks, Discussion, Yo-kai) s'il ne tourne pas déjà.
        Exige une connexion enregistrée (ErreurLanceur « cx_requise »)."""
        if not self.stockage.charger().configuree:
            raise ErreurLanceur(Msg("cx_requise"))
        if self.etat_client_vivant() is not None:
            self.enregistrer_presence()
            return Msg("suivi_deja")
        self._lancer_client_suivi(self.config.port_gdb, attente)
        return Msg("suivi_demarre")

    def deconnecter_suivi(self, attente: float = 5.0) -> Msg:
        """« Déconnecter » : arrête le client de suivi (refusé pendant une partie : ErreurLanceur)."""
        e = self.etat_client_vivant()
        if e is None:
            return Msg("suivi_deja_arrete")
        if e.get("phase") in ("jeu", "attente_jeu") or e.get("mode") == "jeu":
            raise ErreurLanceur(Msg("suivi_jeu_en_cours"))
        if "mode" not in e:                               # client d'une version antérieure : pas de demandes
            raise ErreurLanceur(Msg("client_deja"))
        nonce = self._demander("arreter")
        limite = time.monotonic() + attente
        while time.monotonic() < limite:
            e = self.lire_etat_client()
            if e is None or e.get("phase") == "arrete":
                return Msg("suivi_deconnecte")
            if e.get("demande") == nonce and e.get("refus"):
                raise ErreurLanceur(Msg("suivi_jeu_en_cours"))
            time.sleep(0.05)
        c = self._client
        if c is not None and c.pid == (e or {}).get("pid"):
            _terminer(c)                                  # client lancé par nous, muet : arrêté quand même
            return Msg("suivi_deconnecte")
        raise ErreurLanceur(Msg("client_lent"))

    def jouer(self, *, installer_si_besoin: bool = True, verifier_mod: bool = True, attente_client: float = 15.0,
              console: bool = False, rappel: Callable[[Msg], None] | None = None) -> Session:
        """Attache le jeu au client de suivi (démarré ici s'il ne tourne pas), puis lance Azahar sur la ROM : un seul
        client, une seule connexion au slot, rien de perdu. `verifier_mod` False (lancer.py) : ne regarde pas le mod
        installé (installation de développement)."""
        dire = rappel or (lambda m: None)
        etat_az = self.etat_azahar(rafraichir=True)
        bloquants = self.problemes(etat_az, verifier_mod)
        if bloquants:
            raise ErreurLanceur(bloquants[0])
        if verifier_mod and self.etat_mod().statut != "a_jour":
            if not installer_si_besoin:
                raise ErreurLanceur(Msg("mod_non_installe"))
            dire(Msg("etape_installation"))
            self.installer(rappel=dire)
        if verifier_mod and self.apparence_a_appliquer():   # onglet « Apparence » : réglage changé depuis le patch
            dire(Msg("etape_apparence"))
            try:
                self.appliquer_apparence()
            except (ErreurLanceur, OSError) as e:    # cosmétique : le jeu se lance quand même (nouvel essai au « Jouer » suivant)
                dire(e.msg if isinstance(e, ErreurLanceur) else Msg("installation_echec", {"detail": str(e)}))
        if verifier_mod:                                  # musique aléatoire : réglage changé depuis l'installation
            from . import musique_option as MO
            try:
                MO.mettre_a_jour(self, dire, Msg("etape_installation"))
            except inst.ErreurInstallation as e:
                raise ErreurLanceur(Msg("installation_echec", {"detail": str(e)})) from e
        if verifier_mod and self.a_recompiler():         # Zakuro : code PC absent ou d'une autre version du mod
            self.recompiler(rappel=dire)
        port = etat_az.gdb.port
        if self.config.port_gdb != port:
            self._memoriser(port_gdb=port)
        dossier = self.stockage.dossier
        dossier.mkdir(parents=True, exist_ok=True)
        fichier_pid = dossier / FICHIER_PID
        fichier_pid.unlink(missing_ok=True)
        dire(Msg("etape_client"))
        debut = time.time()
        e = self.etat_client_vivant()
        nouveau = e is None
        if nouveau:                                       # aucun client : démarré en suivi seul, puis attaché
            client = self._lancer_client_suivi(port, attente_client, console)
        elif e.get("phase") == "suivi" and e.get("mode") == "suivi":
            c = self._client                              # le client de suivi qui tourne déjà : le même continue
            client = c if c is not None and c.pid == e.get("pid") and c.poll() is None else ProcessusPid(int(e["pid"]))
        else:                                             # jeu déjà attaché, ou client d'une version antérieure
            raise ErreurLanceur(Msg("client_deja", {"detail": str(e.get("phase"))}))
        nonce = self._demander("jouer", fichier_pid=str(fichier_pid), port=port)
        accuse = self._attendre_accuse(nonce, attente_client)
        if accuse is None or accuse.get("refus"):
            if nouveau:
                _terminer(client)
            raise ErreurLanceur(Msg("client_lent") if accuse is None
                                else Msg("client_deja", {"detail": str(accuse.get("refus"))}))
        dire(Msg("etape_jeu"))
        try:
            if etat_az.emulateur == "zakuro":
                cmd = zk.commande_jeu(etat_az.executable, Path(self.config.rom), self.stockage.dossier, port)
            else:
                cmd = [str(etat_az.executable), str(self.config.rom)]
            azahar = self.lancer_processus(cmd, sans_fenetre=False)
        except OSError as ex:
            if nouveau:
                _terminer(client)
            else:                                         # le client revient au suivi seul (aucun PID : délai)
                ecrire_atomique(fichier_pid, "0")
            raise ErreurLanceur(Msg("azahar_echec", {"detail": str(ex)})) from ex
        ecrire_atomique(fichier_pid, str(azahar.pid))
        return Session(client, azahar, fichier_pid, debut)

    def etat_session(self, session: Session | None) -> EtatSession:
        e = self.lire_etat_client()
        if session is not None:
            client_actif = session.client.poll() is None
            jeu_actif = session.azahar.poll() is None
        else:                       # lanceur rouvert pendant une partie : seul le fichier d'état renseigne
            recent = e is not None and time.time() - float(e.get("horodatage", 0)) < ETAT_PERIME
            client_actif = recent and e.get("phase") != "arrete"
            jeu_actif = bool(client_actif and e.get("phase") == "jeu")
        if e is None or not client_actif:
            return EtatSession(client_actif, jeu_actif, None if e is None else e.get("phase"), 0, "")
        try:
            erreur = int(e.get("erreur", 0) or 0)
        except (TypeError, ValueError):
            erreur = 0
        return EtatSession(client_actif, jeu_actif, e.get("phase"), int(e.get("etat", 0) or 0),
                           str(e.get("message", "")), str(e.get("slot", "")), str(e.get("serveur", "")), erreur,
                           str(e.get("sauvegarde", "") or ""), str(e.get("raison_non_liee", "") or ""))


def _terminer(p) -> None:
    try:
        p.terminate()
    except (OSError, AttributeError):
        pass
