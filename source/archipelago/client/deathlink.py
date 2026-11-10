"""DeathLink du client (docs/systemes/archipelago_deathlink.md, boîte v8 : archipelago_boite.md §25). Logique pure, sans
GDB ni réseau (testée seule) ; `synchro.Synchro` fait les lectures, les écritures et les envois.

- Défaite RÉELLE du joueur : le jeu compte ses défaites depuis le lancement dans l'en-tête (+0x90 `defaites`), jamais
  celles qu'il a forcées pour une mort reçue ni celle qui satisfait une mort en attente (pas de boucle) ; combats
  d'évènement (règle 3/18) compris, combats en ligne exclus. Le client compare au compteur vu au tour précédent (même
  instance du jeu, même sauvegarde) et envoie UN Bounce DeathLink par hausse, sauvegarde liée seulement, au plus un par
  DELAI_ENVOI secondes.
- Mort reçue d'un autre joueur : ses propres DeathLink sont ignorés (source = son slot, filtré aussi par `ap_reseau`),
  ainsi que les morts reçues moins de DELAI_RECU secondes après la dernière transmise au jeu ou moins de DELAI_ECHO
  secondes après sa propre mort envoyée. La mort est écrite dans la boîte (ApMortFenetre : nom du joueur à l'origine,
  si le jeu compile la fenêtre ; ApMort : ident puis demande + 1, en dernier) seulement si la sauvegarde liée est
  chargée ; le jeu l'exécute au prochain moment sûr (terrain : fenêtre « Vous êtes tombé... (DeathLink de <joueur>) »
  dans la langue des notifications, puis retour au point de reprise ; combat : défaite forcée).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

DELAI_ENVOI = 5.0       # s : deux défaites publiées en moins de 5 s -> un seul DeathLink
DELAI_RECU = 10.0       # s : morts reçues groupées (la suivante n'est transmise qu'après ce délai)
DELAI_ECHO = 3.0        # s : une mort reçue juste après avoir envoyé la sienne est ignorée (même incident)
PERIMEE = 60.0          # s : une mort reçue pendant que la sauvegarde liée n'est pas chargée est oubliée après ce délai


def texte_cause(slot: str, langue: str = "fr") -> str:
    return f"{slot} was defeated" if langue == "en" else f"{slot} a été vaincu(e)"


def texte_bandeau(joueur: str, langue: str = "fr") -> str:
    return f"DeathLink: {joueur}" if langue == "en" else f"Mort liée : {joueur}"


@dataclass
class MortRecue:
    source: str
    cause: str
    recue: float


@dataclass
class EtatDeathLink:
    """État du DeathLink pour une connexion (option du slot) et une instance du jeu (boîte)."""
    horloge: Callable[[], float] = time.monotonic
    option: bool = False                 # option `death_link` du slot (slot_data)
    jeu: bool | None = None              # DeathLink compilé dans le jeu (None : pas encore lu / jeu absent)
    fenetre: bool = False                # fenêtre de la mort compilée dans le jeu (bit MORT_FENETRE) : nom à écrire
    demande: int | None = None           # dernier numéro de demande (ApMort.demande) lu ou écrit dans cette instance
    base_defaites: int | None = None     # compteur `defaites` vu au tour précédent
    cle_partie: tuple | None = None      # sauvegarde de ce compteur (adresse P, identifiant)
    envoi_t: float = -1e9                # dernier DeathLink envoyé
    ecrit_t: float = -1e9                # dernière mort transmise au jeu
    attente: list[MortRecue] = field(default_factory=list)
    envoyees: int = 0
    transmises: int = 0
    ignorees: int = 0

    @property
    def tag(self) -> bool:
        """Tag « DeathLink » voulu : option du slot ET jeu attaché qui le compile."""
        return self.option and self.jeu is True

    def nouvelle_instance(self) -> None:
        self.jeu = None
        self.fenetre = False
        self.demande = None
        self.base_defaites = None
        self.cle_partie = None
        self.attente.clear()

    # ------------------------------------------------------------------ défaites du joueur (jeu -> réseau)
    def defaites_vues(self, n: int, cle_partie: tuple, liee: bool) -> bool:
        """Compteur `defaites` lu dans l'en-tête ce tour-ci. Renvoie True s'il faut envoyer un DeathLink."""
        if self.base_defaites is None or cle_partie != self.cle_partie or n < self.base_defaites:
            self.base_defaites, self.cle_partie = n, cle_partie    # référence (nouvelle instance, autre sauvegarde)
            return False
        if n == self.base_defaites:
            return False
        self.base_defaites = n
        if not (self.tag and liee):
            return False
        maintenant = self.horloge()
        if maintenant - self.envoi_t < DELAI_ENVOI:
            return False
        self.envoi_t = maintenant
        self.envoyees += 1
        return True

    # ------------------------------------------------------------------ morts reçues (réseau -> jeu)
    def recue(self, donnees: dict, soi: str) -> MortRecue | None:
        """DeathLink reçu (Bounced). Renvoie la mort gardée pour le jeu, ou None si elle est ignorée."""
        source = str(donnees.get("source") or "?")
        if not self.tag or source == soi:
            return None
        maintenant = self.horloge()
        if maintenant - self.envoi_t < DELAI_ECHO:
            self.ignorees += 1
            return None
        m = MortRecue(source, str(donnees.get("cause") or ""), maintenant)
        self.attente.append(m)
        return m

    def a_transmettre(self, liee: bool) -> MortRecue | None:
        """Mort à écrire dans la boîte ce tour-ci (la plus ancienne ; les suivantes reçues dans DELAI_RECU sont fondues
        dedans), ou None. Sans sauvegarde liée, les morts reçues vieillissent et sont oubliées après PERIMEE s."""
        maintenant = self.horloge()
        if not self.attente or not self.tag or self.demande is None:
            return None
        if not liee:
            self.attente = [m for m in self.attente if maintenant - m.recue < PERIMEE]
            return None
        if maintenant - self.ecrit_t < DELAI_RECU:
            # dans le délai de la mort précédente : fondue avec elle (le jeu n'en exécute qu'une)
            self.ignorees += len(self.attente)
            self.attente.clear()
            return None
        return self.attente[0]

    def transmise(self) -> int:
        """La mort `a_transmettre()` a été écrite : numéro de demande écrit ; les morts en attente sont fondues."""
        self.demande = (self.demande or 0) + 1
        self.ecrit_t = self.horloge()
        self.transmises += 1
        self.ignorees += max(0, len(self.attente) - 1)
        self.attente.clear()
        return self.demande

    def prochaine_demande(self) -> int:
        return ((self.demande or 0) + 1) & 0xFFFFFFFF
