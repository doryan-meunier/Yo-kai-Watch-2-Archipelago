"""Configuration locale du client (dossier utilisateur, jamais dans git) : serveur, slot, mot de passe
(chiffré par DPAPI sous Windows, ou non stocké), chemins de la ROM et d'Azahar, identifiant du client.

Emplacement : `%APPDATA%\\ykw2-ap\\` sous Windows, `$XDG_CONFIG_HOME/ykw2-ap` (ou `~/.config/ykw2-ap`) ailleurs ;
la variable d'environnement `YKW2AP_DOSSIER` le remplace (tests, installation portable).
    config.json            configuration (écrite atomiquement, sous le verrou `config.verrou`)
    journaux/client.log    journal du client invisible (tournant, 3 × 1 Mio)
    cache/                 cache du DataPackage d'Archipelago
Bibliothèque standard seulement (ctypes pour DPAPI).

Connexion (serveur, slot, mot de passe) : saisie dans le LANCEUR seulement (carte « Connexion Archipelago » ;
décision de l'humain du 2026-09-28 : le bouton « Archipelago » de l'écran titre n'affiche plus que l'état). Chaque
saisie qui change quelque chose est écrite dans config.json par `enregistrer_connexion`, sous le verrou, avec
`revision_connexion` = révision du disque + 1 (et `source_connexion` « lanceur » ; « jeu » dans un fichier d'une
version antérieure, lu tel quel). Le client surveille config.json (date, taille) et applique toute révision plus
grande que la sienne (reconnexion). `mdp_revision` = révision où le mot de passe a été choisi : une saisie qui ne le touche pas
(« inchangé ») garde celui que le client a déjà. Mot de passe non mémorisé mais saisi dans le lanceur : transmis
au client par `mot_de_passe_transmis` (chiffré DPAPI, lié à la révision), que le client efface dès qu'il l'a lu
(`consommer_transmis`) ; jamais en clair sur le disque, jamais dans les journaux.
"""
from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import sys
import time
import uuid as uuid_mod
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger("ykw2ap.config")
FORMAT = 1
ENTROPIE = b"ykw2-ap mot de passe Archipelago"
SOURCES = ("lanceur",)                  # « jeu » : saisie dans le jeu, jusqu'au 2026-09-28 (fichiers anciens)
TRANSMIS = "mot_de_passe_transmis"


def dossier_utilisateur() -> Path:
    env = os.environ.get("YKW2AP_DOSSIER")
    if env:
        return Path(env)
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "ykw2-ap"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ykw2-ap"


# ------------------------------------------------------------------------------------------------ DPAPI
def chiffrement_disponible() -> bool:
    return sys.platform == "win32"


if sys.platform == "win32":                     # pragma: no cover - dépend du système
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(b: bytes) -> tuple[_Blob, ctypes.Array]:
        tampon = ctypes.create_string_buffer(b, len(b))
        return _Blob(len(b), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char))), tampon

    def _dpapi(fonction_nom: str, donnees: bytes) -> bytes:
        crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
        entree, _t1 = _blob(donnees)
        entropie, _t2 = _blob(ENTROPIE)
        sortie = _Blob()
        fonction = getattr(crypt32, fonction_nom)
        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if not fonction(ctypes.byref(entree), None, ctypes.byref(entropie), None, None, 0x1, ctypes.byref(sortie)):
            raise OSError(f"{fonction_nom} a échoué (erreur {ctypes.GetLastError()})")
        try:
            return ctypes.string_at(sortie.pbData, sortie.cbData)
        finally:
            kernel32.LocalFree(sortie.pbData)

    def chiffrer(texte: str) -> str:
        return base64.b64encode(_dpapi("CryptProtectData", texte.encode("utf-8"))).decode("ascii")

    def dechiffrer(jeton: str) -> str:
        return _dpapi("CryptUnprotectData", base64.b64decode(jeton)).decode("utf-8")
else:
    def chiffrer(texte: str) -> str:
        raise OSError("chiffrement local indisponible sur ce système : mot de passe non stocké")

    def dechiffrer(jeton: str) -> str:
        raise OSError("chiffrement local indisponible sur ce système")


# ------------------------------------------------------------------------------------------------ configuration
@dataclass
class ConfigLocale:
    serveur: str = ""
    slot: str = ""
    mot_de_passe: str = field(default="", repr=False)   # en mémoire seulement ; sur disque : chiffré ou absent
    memoriser_mot_de_passe: bool = True                  # effectif seulement si le chiffrement est disponible
    uuid: str = ""
    rom: str = ""
    azahar: str = ""
    emulateur: str = ""                                  # "zakuro" (intégré) / "azahar" ; "" : Zakuro s'il est fourni
    hote_gdb: str = "127.0.0.1"
    port_gdb: int = 24689
    langue_notifications: str = "fr"
    langue_lanceur: str = ""                             # "fr" / "en" (vide : langue du système)
    lecture: str = "economique"                          # lectures du jeu : "economique" (défaut) ou "normale"
    carte_suivre: bool = True                            # lanceur : sous-onglet « Carte », case « Suivre le jeu »
    yokai_epingle: str = ""                              # lanceur : Yo-kai épinglé sur la carte (clé du tracker, "" : aucun)
    amitie_fenetre: bool = False                         # lanceur : fenêtre d'amitié en combat (lanceur/fenetre_amitie.py)
    amitie_fenetre_pos: str = ""                         # lanceur : position "x,y" de cette fenêtre ("" : coin haut gauche)
    loupe_fenetre: bool = False                          # lanceur : fenêtre de la loupe (lanceur/fenetre_loupe.py)
    loupe_fenetre_pos: str = ""                          # lanceur : position "x,y" de cette fenêtre ("" : coin haut gauche)
    objets_fenetre: bool = False                         # lanceur : fenêtre des derniers objets (lanceur/fenetre_derniers_objets.py)
    objets_fenetre_pos: str = ""                         # lanceur : position "x,y" de cette fenêtre ("" : coin haut droit)
    objets_fenetre_delai: int = 20                       # lanceur : secondes avant qu'une ligne de cette fenêtre s'efface
    premier_plan: bool = False                           # lanceur : fenêtre « toujours au-dessus » (lanceur/premier_plan.py)
    maj_verifier: bool = True                            # lanceur : chercher une mise à jour au lancement (lanceur/maj.py)
    # lanceur : apparence du personnage principal (onglet « Réglages » → « Apparence », installation/apparence.py) :
    # {"nathan" | "katie": {"tenue": "origine" | "c00…" | "teinte", "teinte": 0..359}}, appliquée au prochain « Jouer »
    apparence: dict = field(default_factory=dict)
    # lanceur : mod d'apparence importé (<données>/apparence/import/, installation/apparence_import.py) utilisé
    apparence_import: bool = False
    musique_aleatoire: bool = False                      # lanceur : musiques du jeu mélangées (lanceur/musique_option.py)
    musique_graine: int = 0                              # lanceur : graine de ce mélange (tirée en cochant la case)
    # connexion : la saisie la plus récente gagne (docstring du module)
    revision_connexion: int = 0
    source_connexion: str = ""                           # "lanceur" ("jeu" : version antérieure ; "" : plus ancienne)
    horodatage_connexion: float = 0.0                    # time.time() de la saisie
    mdp_revision: int = 0                                # révision où le mot de passe a été choisi

    @property
    def configuree(self) -> bool:
        return bool(self.serveur and self.slot)

    @property
    def connu(self) -> int:
        return (1 if self.serveur else 0) | (2 if self.slot else 0) | (4 if self.mot_de_passe else 0)


class VerrouConfig:
    """Verrou inter-processus de config.json (lanceur et client) : lecture-modification-écriture sans perte.
    Attente bornée : au-delà, on écrit quand même (l'écriture reste atomique)."""

    def __init__(self, fichier: Path, attente: float = 2.0):
        self.fichier, self.attente = fichier, attente
        self._f = None

    def __enter__(self):
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        fin = time.monotonic() + self.attente
        while True:
            f = open(self.fichier, "a+b")                 # noqa: SIM115 (gardé ouvert jusqu'à __exit__)
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._f = f
                return self
            except OSError:
                f.close()
                if time.monotonic() >= fin:
                    log.warning("Verrou de la configuration non obtenu : écriture sans verrou")
                    return self
                time.sleep(0.02)

    def __exit__(self, *exc):
        if self._f is not None:
            with contextlib.suppress(OSError):
                if os.name == "nt":
                    import msvcrt
                    self._f.seek(0)
                    msvcrt.locking(self._f.fileno(), msvcrt.LK_UNLCK, 1)
                self._f.close()
            self._f = None
        return False


class StockageConfig:
    def __init__(self, dossier: Path | None = None):
        self.dossier = Path(dossier) if dossier else dossier_utilisateur()
        self.fichier = self.dossier / "config.json"
        self.fichier_verrou = self.dossier / "config.verrou"

    @property
    def dossier_journaux(self) -> Path:
        return self.dossier / "journaux"

    @property
    def dossier_cache(self) -> Path:
        return self.dossier / "cache"

    def lire_brut(self) -> dict:
        try:
            brut = json.loads(self.fichier.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            log.warning("Configuration illisible (%s) : valeurs par défaut", e)
            return {}
        return brut if isinstance(brut, dict) else {}

    def signature(self) -> tuple | None:
        """(date, taille) de config.json : un changement signale une écriture (lanceur ou client)."""
        try:
            st = self.fichier.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def revision_disque(self) -> int:
        v = self.lire_brut().get("revision_connexion", 0)
        return v if isinstance(v, int) else 0

    @staticmethod
    def _transmis_valide(brut: dict, c: ConfigLocale) -> str | None:
        """Jeton du mot de passe transmis, s'il appartient à la révision courante (sinon périmé : ignoré)."""
        t = brut.get(TRANSMIS)
        if not isinstance(t, dict) or t.get("revision") != c.revision_connexion or c.mdp_revision != c.revision_connexion:
            return None
        return t.get("jeton") if isinstance(t.get("jeton"), str) else None

    def charger(self) -> ConfigLocale:
        c = ConfigLocale()
        brut = self.lire_brut()
        noms = {f.name for f in fields(ConfigLocale)} - {"mot_de_passe"}
        for k, v in brut.items():
            if k in noms and isinstance(v, type(getattr(c, k))):
                setattr(c, k, v)
        jeton = brut.get("mot_de_passe_chiffre") if c.memoriser_mot_de_passe else None
        jeton = jeton or self._transmis_valide(brut, c)
        if jeton:
            try:
                c.mot_de_passe = dechiffrer(jeton)
            except (OSError, ValueError) as e:
                log.warning("Mot de passe mémorisé illisible (%s) : ignoré", e)
        if not c.uuid:
            c.uuid = uuid_mod.uuid4().hex
        return c

    def _ecrire(self, c: ConfigLocale, transmis: dict | None = None) -> None:
        d = asdict(c)
        mdp = d.pop("mot_de_passe")
        d["format"] = FORMAT
        if mdp and c.memoriser_mot_de_passe and chiffrement_disponible():
            try:
                d["mot_de_passe_chiffre"] = chiffrer(mdp)
            except OSError as e:
                log.warning("Mot de passe non mémorisé : %s", e)
        if transmis is not None:
            d[TRANSMIS] = transmis
        self.dossier.mkdir(parents=True, exist_ok=True)
        tmp = self.fichier.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.fichier)

    def _transmis_a_garder(self, brut: dict, c: ConfigLocale) -> dict | None:
        if c.memoriser_mot_de_passe or self._transmis_valide(brut, c) is None:
            return None
        return brut.get(TRANSMIS)

    def enregistrer(self, c: ConfigLocale) -> None:
        """Écrit toute la configuration `c` (sous le verrou). Un mot de passe transmis encore attendu par le client
        (même révision) est gardé. Pour changer un réglage sans toucher au reste : `modifier`."""
        with VerrouConfig(self.fichier_verrou):
            self._ecrire(c, self._transmis_a_garder(self.lire_brut(), c))

    def modifier(self, **champs) -> ConfigLocale:
        """Relit la configuration, change `champs` (réglages hors connexion), réécrit, sous le verrou : rien de ce
        qu'un autre processus a écrit entre-temps n'est perdu. Renvoie la configuration écrite."""
        with VerrouConfig(self.fichier_verrou):
            brut = self.lire_brut()
            c = self.charger()
            for k, v in champs.items():
                setattr(c, k, v)
            self._ecrire(c, self._transmis_a_garder(brut, c))
            return c

    def enregistrer_connexion(self, serveur: str, slot: str, mot_de_passe: str | None, *,
                              memoriser: bool | None = None, source: str = "lanceur") -> ConfigLocale:
        """Nouvelle saisie de connexion (la plus récente gagne) : révision du disque + 1. `mot_de_passe` None =
        inchangé (le client garde le sien). `memoriser` None = réglage actuel. Mot de passe non mémorisé saisi dans le
        lanceur : transmis chiffré au client (`mot_de_passe_transmis`), jamais en clair. Renvoie la configuration
        écrite (avec le mot de passe en mémoire s'il est connu)."""
        if source not in SOURCES:
            raise ValueError(source)
        with VerrouConfig(self.fichier_verrou):
            c = self.charger()
            c.serveur, c.slot = serveur.strip(), slot.strip()
            if memoriser is not None:
                c.memoriser_mot_de_passe = bool(memoriser)
            c.revision_connexion += 1
            c.source_connexion = source
            c.horodatage_connexion = time.time()
            transmis = None
            if mot_de_passe is not None:
                c.mot_de_passe = mot_de_passe
                c.mdp_revision = c.revision_connexion
                if mot_de_passe and not c.memoriser_mot_de_passe and source == "lanceur":
                    if chiffrement_disponible():
                        try:
                            transmis = {"revision": c.revision_connexion, "jeton": chiffrer(mot_de_passe)}
                        except OSError as e:
                            log.warning("Mot de passe non transmis au client : %s", e)
                    else:
                        log.warning("Chiffrement indisponible : mot de passe non transmis au client")
            self._ecrire(c, transmis)
            return c

    def consommer_transmis(self) -> bool:
        """Client : efface `mot_de_passe_transmis` du disque (après l'avoir lu par `charger`)."""
        with VerrouConfig(self.fichier_verrou):
            brut = self.lire_brut()
            if TRANSMIS not in brut:
                return False
            del brut[TRANSMIS]
            tmp = self.fichier.with_suffix(".tmp")
            tmp.write_text(json.dumps(brut, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.fichier)
            return True
