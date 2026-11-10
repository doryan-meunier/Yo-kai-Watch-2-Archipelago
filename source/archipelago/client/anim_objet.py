"""Fenêtre « objet obtenu » des checks qui n'ont pas d'affichage dans le jeu (boss, Tablo-blabla, fin de chapitre…) :
logique pure du client, sans GDB ni réseau (testée seule) ; `synchro.Synchro` fait les lectures et les écritures.
Protocole : docs/systemes/archipelago_boite.md §27 ; analyse : docs/systemes/archipelago_anim_objet.md.

- Quand le client envoie un check d'une location « sans affichage » (boss d'histoire et de quête, fins de chapitre,
  Montée de rang : D, Vélo, Tablo-blabla, don de script substitué que le jeu d'origine fait sans fenêtre : Yo-kai
  Watch, `Catalogue.dons_sans_fenetre` : `Catalogue.locations_anim` ; comportement fixe, décision de l'humain du
  2026-09-30 : aucune option dans le YAML), il la met dans sa file d'attente (`ajouter`), dans l'ordre des checks.
- Il écrit les entrées dans la file du jeu (8 places, ApAnim) seulement pour la sauvegarde liée, si le jeu compile la
  fonction 29, et jamais au-delà de `traitees + 8` (places connues par la dernière lecture de l'en-tête de la file).
- Le jeu montre les entrées une par une au moment sûr du terrain et avance `traitees` à la fermeture de chaque fenêtre.
  L'en-tête de la file (0x40 octets, un paquet) n'est lu que tant que des entrées attendent ou sont dans le jeu, au plus
  une fois tous les TOURS_RELECTURE tours (aucune lecture de plus sinon, archipelago_boite.md §23).
- Nouvelle instance du jeu (jeu relancé) : les entrées écrites mais pas encore confirmées traitées sont réécrites (la
  file du jeu est repartie à zéro). Une entrée qui visait la sauvegarde liée alors qu'une autre était chargée est
  écartée par le jeu (jamais montrée à une autre partie).
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Callable

try:
    from . import boite_protocole as bp
except ImportError:                                          # pragma: no cover - selon le mode d'import
    import boite_protocole as bp                            # type: ignore[no-redef]

TOURS_RELECTURE = 5                  # en-tête de la file relu au plus une fois par 5 tours pendant qu'il y a du travail
LOT_MAX = bp.CAP_ANIM               # plus de checks concernés au même tour (rattrapage) : aucune fenêtre pour ce lot
ATTENTE_MAX = 64                     # locations gardées au plus en attente (au-delà : les plus anciennes sont oubliées)


@dataclass
class EtatAnims:
    """File du client pour une connexion et une instance du jeu."""
    attente: collections.deque[int] = field(default_factory=collections.deque)   # locations à écrire, dans l'ordre
    en_vol: dict[int, int] = field(default_factory=dict)     # numéro écrit -> location (pas encore traitée par le jeu)
    ecrites: int | None = None       # `ecrites` du jeu (None : en-tête pas encore lu dans cette instance)
    traitees: int = 0                # `traitees` lu en dernier
    montrees: int = 0                # `montrees` lu en dernier (journal du client)
    ecartees: int = 0
    tours: int = 0                   # tours depuis la dernière lecture de l'en-tête
    ecrites_total: int = 0           # entrées écrites depuis le lancement du client (statistiques, tests)
    oubliees: int = 0                # locations oubliées (file du client pleine)

    def ajouter(self, locations) -> list[int]:
        """Locations dont le check vient d'être envoyé (déjà filtrées : « sans affichage » et option). Renvoie celles
        qui ont été ajoutées (une location déjà en attente ou dans le jeu ne l'est pas deux fois)."""
        deja = set(self.attente) | set(self.en_vol.values())
        ajoutees = []
        for loc in locations:
            if loc in deja:
                continue
            if len(self.attente) >= ATTENTE_MAX:
                self.attente.popleft()
                self.oubliees += 1
            self.attente.append(loc)
            deja.add(loc)
            ajoutees.append(loc)
        return ajoutees

    @property
    def travail(self) -> bool:
        return bool(self.attente or self.en_vol)

    def tour(self) -> None:
        self.tours += 1

    def besoin_lecture(self) -> bool:
        """L'en-tête de la file doit-il être lu à ce tour ? Jamais sans travail ; tout de suite si l'état du jeu est
        inconnu ; sinon au plus une fois par TOURS_RELECTURE tours tant que des entrées sont dans le jeu (places libérées,
        confirmation)."""
        if not self.travail:
            return False
        if self.ecrites is None:
            return True
        return bool(self.en_vol) and self.tours >= TOURS_RELECTURE

    def lue(self, entete: dict) -> list[int]:
        """En-tête de la file lu (dec_anim_entete). Renvoie les locations dont l'entrée est traitée par le jeu."""
        self.tours = 0
        ecrites, traitees = entete["ecrites"], entete["traitees"]
        if self.ecrites is not None and ecrites < self.ecrites:
            self.nouvelle_instance()                  # file du jeu repartie à zéro sans que le client l'ait vu
        self.ecrites, self.traitees = ecrites, traitees
        self.montrees, self.ecartees = entete["montrees"], entete["ecartees"]
        faites = [n for n in self.en_vol if n <= traitees]
        return [self.en_vol.pop(n) for n in sorted(faites)]

    @property
    def places(self) -> int:
        if self.ecrites is None:
            return 0
        return max(0, bp.CAP_ANIM - (self.ecrites - self.traitees))

    def a_ecrire(self, entree: Callable[[int], tuple[int, bytes, int] | None], ident: int) -> list[tuple[int, int, bytes]]:
        """Entrées à écrire à ce tour, dans l'ordre : [(numéro, location, octets)] ; `entree(loc)` donne (objet montré,
        0 = vitrine ; texte du nom de vitrine ; quantité), ou None si le contenu de la location n'est pas encore connu
        (on s'arrête là : l'ordre est gardé)."""
        out = []
        n = self.ecrites
        if n is None:
            return out
        for loc in list(self.attente)[:self.places]:
            e = entree(loc)
            if e is None:
                break
            affiche, texte, quantite = e
            n += 1
            out.append((n, loc, bp.enc_anim(n, loc, affiche, ident, quantite, texte)))
        return out

    def ecrites_faites(self, liste: list[tuple[int, int, bytes]]) -> None:
        """Les entrées de `a_ecrire` sont écrites (puis `ecrites` en dernier)."""
        for n, loc, _ in liste:
            self.attente.remove(loc)
            self.en_vol[n] = loc
            self.ecrites = n
            self.ecrites_total += 1
        self.tours = 0

    def nouvelle_instance(self) -> None:
        """Jeu relancé : la file du jeu est vide ; ce qui y était sans être confirmé traité est réécrit, en premier."""
        self.attente = collections.deque([self.en_vol[n] for n in sorted(self.en_vol)] + list(self.attente))
        self.en_vol.clear()
        self.ecrites = None
        self.traitees = 0
        self.tours = 0
