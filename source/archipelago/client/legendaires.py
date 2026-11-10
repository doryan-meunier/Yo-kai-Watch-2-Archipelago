"""Légendaires mélangés entre eux, côté client (V3, lot L1, `docs/systemes/archipelago_v3_legendaires.md` ; zone
ApLegendes, §51 de `docs/systemes/archipelago_boite.md`).

La permutation est tirée à la GÉNÉRATION (`slot_data.legendaires` = [[sceau, légendaire donné], …], n° du Médaillium,
sceau = n° de son légendaire d'origine). Ce module :
1. la lit dans slot_data (clé absente : aucun mélange, rien n'est jamais écrit) ;
2. lit une fois par instance du jeu si la zone est publiée et compilée (8 octets) ; sinon refus de la partie
   (« Verrous incompatibles », comme une fonction étendue absente : la fonction 50 l'est aussi pour `_verifier_verrous`) ;
3. écrit `ident`, `donne` et `valide` en UN paquet de 16 octets pour la sauvegarde LIÉE seulement, et `valide` = 0
   quand elle ne l'est plus ; rien n'est écrit si rien ne change (aucune lecture ni écriture périodique).
Le jeu réécrit le légendaire de chaque sceau à la lecture de la table et à chaque commande 0x3CDD (page des légendes).
"""
from __future__ import annotations

try:
    from . import boite_protocole as bp
except ImportError:                                          # module chargé hors paquet (tests, outils)
    import boite_protocole as bp


def lire_slot_data(sd: dict) -> tuple[tuple[int, ...] | None, str]:
    """(`donne` : sceau k -> légendaire donne[k], ou None sans mélange ; erreur de forme, "" si aucune)."""
    v = sd.get("legendaires") if isinstance(sd, dict) else None
    if v is None:
        return None, ""
    try:
        d = bp.donne_depuis_paires(v)
    except (TypeError, ValueError, IndexError) as e:
        return None, str(e)
    return (None if d == tuple(range(bp.NB_SCEAUX)) else d), ""


class SuiviLegendaires:
    """État du client pour les légendaires mélangés (une instance par `Synchro`)."""

    def __init__(self, synchro):
        self.s = synchro
        self.donne: tuple[int, ...] | None = None
        self.erreur = ""                     # slot_data illisible (refus)
        self.manquants = False               # graine à légendaires mélangés, jeu qui ne les a pas : refus
        self._compile: tuple[int, bool] | None = None   # (instance, ApLegendes publiée et compilée)
        self._ecrite: tuple | None = None    # (instance, sauvegarde, donne) de la dernière permutation écrite
        self._valide_instance: int | None = None   # instance du jeu qui a reçu `valide` (pas encore retiré)

    # ------------------------------------------------------------------ graine
    def appliquer(self, sd: dict) -> None:
        self.donne, self.erreur = lire_slot_data(sd)
        if self.erreur:
            self.s.log.error("Légendaires mélangés : %s ; la partie est refusée", self.erreur)
        elif self.donne is not None:
            self.s.log.info("Légendaires mélangés : %s", ", ".join(
                f"{bp.MEDAILLE_LEGENDAIRE0 + k}->{bp.MEDAILLE_LEGENDAIRE0 + l}" for k, l in enumerate(self.donne)))
        self._ecrite = None

    @property
    def actifs(self) -> bool:
        return self.donne is not None or bool(self.erreur)

    def nouvelle_instance(self) -> None:
        self._compile = None
        self._ecrite = None
        self._valide_instance = None

    def oublier(self) -> None:
        """Sauvegarde changée : la permutation est réécrite pour la suivante (ou retirée si elle n'est pas liée)."""
        self._ecrite = None

    # ------------------------------------------------------------------ jeu
    async def compilee(self, h) -> bool:
        if self._compile is None or self._compile[0] != self.s._instance:
            lu = False
            if bp.legendes_disponibles(h):
                lu = bp.legendes_compilees(await self.s.pont.lire(bp.ZONE + bp.OFF_LEGENDES, 8))
            self._compile = (self.s._instance, lu)
            self.s.log.info("Légendaires mélangés compilés dans le jeu : %s",
                            "oui" if lu else "non (patch d'avant le lot L1)")
        return self._compile[1]

    async def verifier(self, h) -> None:
        """Refus (« Verrous incompatibles ») si la graine mélange les légendaires et que le jeu ne le sait pas faire."""
        if not self.actifs:
            self.manquants = False
            return
        manquants = bool(self.erreur) or not await self.compilee(h)
        if manquants != self.manquants:
            self.manquants = manquants
            if manquants:
                self.s.log.error("Légendaires mélangés : %s ; rien ne sera lié, livré ni envoyé. Installer le patch du "
                                 "mod à jour, ou générer une graine sans l'option legendaires_melanges.",
                                 self.erreur or "jeu sans la fonction (patch d'avant le lot L1)")

    async def ecrire(self, h) -> None:
        """`ident` + `donne` + `valide` (un paquet) pour la sauvegarde liée ; `valide` = 0 si elle ne l'est plus.
        Aucune écriture si rien ne change."""
        if self.donne is None or self.manquants:
            return
        if self._compile is None or self._compile[0] != self.s._instance or not self._compile[1]:
            return
        if self.s.sauvegarde == "liee":
            cle = (self.s._instance, h.ident_sauvegarde, self.donne)
            if cle == self._ecrite:
                return
            ecritures, texte = bp.ecritures_legendes(self.donne, self.s.ident_partie or 0), "écrite (sauvegarde liée)"
            self._ecrite, self._valide_instance = cle, self.s._instance
        else:
            # sauvegarde non liée : `valide` = 0 seulement si CETTE instance du jeu a reçu la permutation (le jeu ne
            # l'appliquerait de toute façon pas à une sauvegarde non liée ; rien à retirer sinon : aucun paquet)
            self._ecrite = None
            if self._valide_instance != self.s._instance:
                return
            ecritures, texte = bp.ecritures_legendes_retrait(), "retirée (sauvegarde non liée)"
            self._valide_instance = None
        async with self.s.pont.transaction():
            for off, octets in ecritures:
                await self.s.pont.ecrire(bp.ZONE + off, octets)
        self.s.log.info("Légendaires mélangés : permutation %s", texte)
