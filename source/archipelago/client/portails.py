"""Récompense des coffres de fin de portail, côté client (ap/portails-donjon ;
`docs/systemes/archipelago_portails_donjon.md`, zone ApPortails : §55 de `docs/systemes/archipelago_boite.md`).

La liste est tirée à la GÉNÉRATION (`slot_data.portails_recompenses` = [[hachage, quantité], …], 28 entrées). Ce
module :
1. la lit dans slot_data (clé absente : rien n'est jamais lu ni écrit) ;
2. lit une fois par instance du jeu si la zone est publiée et compilée (4 octets) ; sinon AVERTISSEMENT seulement
   (aucune location n'en dépend : le jeu garde ses globes) ;
3. écrit `ident`, `nombre`, `base`, `liaison` et la liste, puis `sequence` EN DERNIER (une transaction), pour la
   sauvegarde LIÉE seulement, et `sequence` = 0 quand elle ne l'est plus ; rien n'est écrit si rien ne change ;
4. tient la mémoire `base` (entrées déjà tirées dans CETTE sauvegarde, par partie et clé de liaison P+0x3B6) dans
   `liaisons.json` (clé « <partie>:<liaison>:portails ») d'après les évènements COFFRE à drapeau
   EVT_COFFRE_PORTAIL (étiquette = rang absolu suivant), lus avec le journal : aucun paquet de plus. Le jeu tire
   max(curseur du lancement, base) : un jeu relancé reprend la liste là où la sauvegarde l'avait laissée (un
   évènement perdu, jeu fermé avant la lecture du journal, fait au pire redonner une entrée).
"""
from __future__ import annotations

import json
import time

try:
    from . import boite_protocole as bp
except ImportError:                                          # module chargé hors paquet (tests, outils)
    import boite_protocole as bp

CLE_SLOT_DATA = "portails_recompenses"


def lire_slot_data(sd: dict) -> tuple[tuple[tuple[int, int], ...] | None, str]:
    """(liste [(objet, quantité)], ou None sans l'option ; erreur de forme, "" si aucune)."""
    v = sd.get(CLE_SLOT_DATA) if isinstance(sd, dict) else None
    if v is None:
        return None, ""
    if not isinstance(v, (list, tuple)) or not 1 <= len(v) <= bp.CAP_PORTAILS:
        return None, "liste des récompenses des portails : 1 à %d entrées" % bp.CAP_PORTAILS
    out = []
    for e in v:
        if not isinstance(e, (list, tuple)) or len(e) != 2 or any(isinstance(x, bool) or not isinstance(x, int)
                                                                  for x in e) \
                or not 0 < e[0] < 1 << 32 or not 1 <= e[1] <= 99:
            return None, "entrée de récompense invalide : %r" % (e,)
        out.append((e[0], e[1]))
    return tuple(out), ""


def portails_disponibles(h) -> bool:
    """Zone d'un jeu qui publie les dons de script ailleurs qu'à 0x4300 (zone v10 : 0x4300 n'est plus à eux)."""
    off = getattr(h, "scripts_off", 0) or 0
    return getattr(h, "taille_zone", 0) >= bp.OFF_PORTAILS + bp.TAILLE_PORTAILS and off not in (0, bp.OFF_PORTAILS)


class SuiviPortails:
    """État du client pour la récompense des portails (une instance par `Synchro`)."""

    def __init__(self, synchro):
        self.s = synchro
        self.liste: tuple[tuple[int, int], ...] | None = None
        self.erreur = ""
        self.absente = False                 # graine à récompenses, jeu sans la zone : avertissement
        self._compile: tuple[int, bool] | None = None   # (instance, ApPortails publiée et compilée)
        self._ecrite: tuple | None = None    # (instance, sauvegarde, liaison) de la dernière liste écrite
        self._valide_instance: int | None = None
        self._sequence = 0
        self._base: dict[tuple[int, int], int] = {}     # (partie, liaison) -> base connue (mémoire relue)

    # ------------------------------------------------------------------ graine
    def appliquer(self, sd: dict) -> None:
        self.liste, self.erreur = lire_slot_data(sd)
        if self.erreur:
            self.s.log.warning("Récompense des portails : %s ; les coffres des portails gardent leurs globes",
                               self.erreur)
        elif self.liste is not None:
            self.s.log.info("Récompense des portails : liste de %d objets", len(self.liste))
        self._ecrite = None

    def nouvelle_instance(self) -> None:
        self._compile = None
        self._ecrite = None
        self._valide_instance = None

    def oublier(self) -> None:
        self._ecrite = None

    # ------------------------------------------------------------------ mémoire (liaisons.json)
    @staticmethod
    def cle_memoire(ident: int, liaison: int) -> str:
        return f"{ident & 0xFFFFFFFF:08x}:{liaison & 0xFFFF:04x}:portails"

    def base(self, ident: int, liaison: int) -> int:
        k = (ident, liaison)
        if k not in self._base:
            e = self.s.liaisons._tout().get(self.cle_memoire(ident, liaison))
            n = e.get("tirees") if isinstance(e, dict) else 0
            self._base[k] = n if isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 0xFFFF else 0
        return self._base[k]

    def noter(self, ident: int, liaison: int, rang: int) -> bool:
        """Rang absolu suivant publié par le jeu : mémoire = max(mémoire, rang). True si elle a changé."""
        if not ident or not liaison or not 0 < rang <= 0xFFFF or rang <= self.base(ident, liaison):
            return False
        self._base[(ident, liaison)] = rang
        reg = self.s.liaisons
        d = reg._tout()
        d[self.cle_memoire(ident, liaison)] = {"tirees": rang, "date": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            reg.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp = reg.fichier.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(reg.fichier)
        except OSError as e:
            self.s.log.warning("Récompense des portails : mémoire non enregistrée : %s", e)
        return True

    def evenements(self, h, evts) -> None:
        """Évènements COFFRE à drapeau EVT_COFFRE_PORTAIL : mémoire `base` de la sauvegarde liée."""
        if self.liste is None or h is None:
            return
        for e in evts:
            if e.type == bp.EVT_COFFRE and e.drapeaux & bp.EVT_COFFRE_PORTAIL:
                self.noter(self.s.ident_partie or 0, getattr(h, "liaison_sauvegarde", 0), e.etiquette)

    # ------------------------------------------------------------------ jeu
    async def compilee(self, h) -> bool:
        if self._compile is None or self._compile[0] != self.s._instance:
            lu = False
            if portails_disponibles(h):
                lu = bp.portails_compile(await self.s.pont.lire(bp.ZONE + bp.OFF_PORTAILS, 4))
            self._compile = (self.s._instance, lu)
            self.s.log.info("Récompense des portails compilée dans le jeu : %s", "oui" if lu else "non")
        return self._compile[1]

    async def verifier(self, h) -> None:
        """Avertissement (jamais de refus : aucune location n'en dépend) si le jeu ne sait pas tirer la liste."""
        if self.liste is None:
            self.absente = False
            return
        absente = not await self.compilee(h)
        if absente and not self.absente:
            self.s.log.warning("Récompense des portails : jeu sans la fonction (patch d'avant ap/portails-donjon) : "
                               "les coffres des portails gardent leurs globes. Installer le patch du mod à jour.")
        self.absente = absente

    async def ecrire(self, h) -> None:
        """Liste + mémoire pour la sauvegarde liée (une transaction, `sequence` en dernier) ; `sequence` = 0 si elle
        ne l'est plus. Aucune écriture si rien ne change."""
        if self.liste is None or self.absente:
            return
        if self._compile is None or self._compile[0] != self.s._instance or not self._compile[1]:
            return
        ident = self.s.ident_partie or 0
        liaison = getattr(h, "liaison_sauvegarde", 0)
        if self.s.sauvegarde == "liee" and ident and liaison:
            # (une fois par instance et par sauvegarde : ensuite le curseur du jeu suit les tirages lui-même)
            cle = (self.s._instance, getattr(h, "ident_sauvegarde", 0), liaison)
            if cle == self._ecrite:
                return
            base = self.base(ident, liaison)
            self._sequence = (self._sequence % 0xFFFFFFFE) + 1
            ecritures = bp.ecritures_portails(self.liste, ident, liaison, base, self._sequence)
            self._ecrite, self._valide_instance = cle, self.s._instance
            texte = "écrite (sauvegarde liée, %d déjà tirées)" % base
        else:
            self._ecrite = None
            if self._valide_instance != self.s._instance:
                return
            ecritures, texte = bp.ecritures_portails_retrait(), "retirée (sauvegarde non liée)"
            self._valide_instance = None
        async with self.s.pont.transaction():
            for off, octets in ecritures:
                await self.s.pont.ecrire(bp.ZONE + off, octets)
        self.s.log.info("Récompense des portails : liste %s", texte)
