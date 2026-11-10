"""Pièges (« traps ») d'Archipelago, côté client (lot 4 des pièges ; `docs/systemes/archipelago_v3_pieges.md` §12,
zone ApPieges : §57 de `docs/systemes/archipelago_boite.md`).

Le jeu (`src/archipelago/pieges.cpp`) reçoit un piège comme un DON de type 4 (`hash` = n° du piège) ; ce module :
1. lit les pièges possibles de la graine dans `slot_data.dons` (entrées `{"type": "piege", "piege": n}`) ; aucune
   entrée : rien n'est jamais lu ni écrit ;
2. lit UNE fois par instance du jeu le début de la zone ApPieges (`compile`, `reprise_vue` : 0x14 octets) et AVERTIT,
   sans refuser, pour chaque piège de la graine absent du patch (le jeu l'écarte à la réception : aucune location n'en
   dépend) ; le message nomme le piège dans la langue des notifications (depuis ap/v3-pieges-roue-oni, le patch
   compile 0..5 et 7 : seul un patch d'avant l'Oni avertit pour le 7 ; le 6, envoûtement abandonné, n'est plus dans
   aucune graine) ;
3. compose les bandeaux de réception (« Piège reçu : <nom> », « Piège ignoré : <nom> » pour un piège absent du patch,
   « Effet au prochain combat » pour les pièges de combat), en français ou en anglais ;
4. tient la MÉMOIRE des pièges reçus et pas finis (variante B), par partie et par sauvegarde liée, dans `liaisons.json`
   (clé « <partie>:<liaison>:pieges »), d'après les évènements PIEGE_RECU / PIEGE_FAIT du journal (lus avec le
   journal : aucun paquet de plus). Le fichier n'a qu'un écrivain (ce client) ; chaque écriture relit le fichier
   entier puis le remplace (comme les autres mémoires de `liaisons.json`) ;
5. au lancement (une fois par instance du jeu et par sauvegarde liée), redonne au jeu les rangs mémorisés <= compteur
   de dons de la sauvegarde par la REPRISE (7 entrées au plus par paquet, `reprise_seq` écrit en dernier) ; s'il en
   faut plusieurs paquets, le suivant attend que `reprise_vue` vaille la séquence du précédent ; `reprise_vue` n'est
   relu QUE pendant cette attente, et seulement quand l'en-tête annonce un changement (journal écrit, nouveau passage
   sur le terrain) ou après un filet de 60 s. Un rang que le jeu connaît déjà (file, derniers finis) est écarté par le
   jeu : jamais deux exécutions dans une même instance ; un rang > compteur reviendra par la file de dons.

Limite (variante B, §3.4 de l'analyse) : un piège fait juste avant la fermeture du jeu, dont le PIEGE_FAIT n'a pas été
lu par le client, est redonné une fois au lancement suivant.
"""
from __future__ import annotations

import json
import struct
import time
from pathlib import Path

try:
    from . import boite_protocole as bp
except ImportError:                                          # module chargé hors paquet (tests, outils)
    import boite_protocole as bp

FICHIER_OBJETS = Path(__file__).resolve().parents[1] / "apworld" / "yokaiwatch2" / "donnees" / "objets.json"
TAILLE_LECTURE = 0x14                    # compile, ident, recus..reprises, reprise_vue
OFF_REPRISE_VUE = 0x10
PERIODE_FILET_REPRISE = 60.0             # s : relecture de `reprise_vue` sans changement de l'en-tête (attente seulement)
NOTIF_MAX_CAR = 32                       # bandeau d'un piège : la largeur (bp.NOTIF_LARGEUR) reste la vraie limite
PERIODE_FILET_PURGE = 60.0               # s : nouvel essai de vider la file du jeu (après la victoire, combat en cours)
TEXTES = {
    "fr": {"recu": "Piège reçu : {nom}", "ignore": "Piège ignoré : {nom}", "combat": "Effet au prochain combat",
           "recus": "{n} pièges reçus", "ignores": "{n} pièges ignorés", "fini": "Partie finie : sans effet",
           "absents": "Piège(s) de la graine absent(s) du jeu installé (patch trop ancien ou compilé sans) : {noms}. "
                      "Le jeu les ignorera s'ils arrivent ; la partie n'est pas refusée."},
    "en": {"recu": "Trap received: {nom}", "ignore": "Trap skipped: {nom}", "combat": "Effect at next battle",
           "recus": "{n} traps received", "ignores": "{n} traps skipped", "fini": "Goal reached: no effect",
           "absents": "Trap(s) of this seed missing from the installed game (patch too old or built without them): "
                      "{noms}. The game will skip them if they arrive; the game is not refused."},
}


def textes(langue: str) -> dict:
    return TEXTES.get(langue, TEXTES["fr"])


def charger_noms(fichier: Path = FICHIER_OBJETS) -> dict[int, dict[str, str]]:
    """{n° du piège : {"fr": nom complet, "en": …, "fr_court": …, "en_court": …}} d'après `objets.json` (famille
    `piege`, noms saisis à la main dans l'APWorld) ; nom court = sans « Piège : » / « Trap » (bandeau)."""
    try:
        objets = json.loads(Path(fichier).read_text(encoding="utf-8"))["objets"]
    except (OSError, ValueError, KeyError):
        objets = []
    out: dict[int, dict[str, str]] = {}
    for o in objets:
        if not isinstance(o, dict) or o.get("famille") != "piege" or not isinstance(o.get("piege"), int):
            continue
        fr, en = str(o.get("nom_fr", "")), str(o.get("nom_en", ""))
        court_fr = fr.split(" : ", 1)[1] if fr.startswith("Piège : ") else fr
        court_en = en[:-len(" Trap")] if en.endswith(" Trap") else en
        out[o["piege"]] = {"fr": fr, "en": en, "fr_court": court_fr, "en_court": court_en}
    for n, nom in bp.NOMS_PIEGES.items():              # (secours : objets.json illisible)
        out.setdefault(n, {"fr": "Piège : " + nom, "en": f"Trap {n}", "fr_court": nom, "en_court": f"trap {n}"})
    return out


NOMS = charger_noms()


def nom_piege(n: int, langue: str, court: bool = False) -> str:
    e = NOMS.get(n)
    if e is None:
        return (f"piège {n}" if langue != "en" else f"trap {n}") if court else \
            (f"Piège {n}" if langue != "en" else f"Trap {n}")
    k = "en" if langue == "en" else "fr"
    return e[k + "_court"] if court else e[k]


def lire_slot_data(sd: dict) -> frozenset[int]:
    """N° des pièges possibles de la graine (entrées « piege » de `dons`) ; vide : graine sans pièges."""
    dons = sd.get("dons") if isinstance(sd, dict) else None
    out = set()
    for o in (dons or {}).values() if isinstance(dons, dict) else ():
        if isinstance(o, dict) and o.get("type") == "piege":
            n = o.get("piege", o.get("hachage"))
            if isinstance(n, int) and not isinstance(n, bool) and 0 <= n < 256:
                out.add(n)
    return frozenset(out)


def zone_disponible(h) -> bool:
    return getattr(h, "taille_zone", 0) >= bp.OFF_PIEGES + bp.TAILLE_PIEGES


class SuiviPieges:
    """État du client pour les pièges (une instance par `Synchro`)."""

    def __init__(self, synchro):
        self.s = synchro
        self.pieges: frozenset[int] = frozenset()
        self.absents: tuple[int, ...] = ()                 # pièges de la graine absents du patch (avertissement)
        self._lu: tuple[int, int | None, int] | None = None   # (instance, compile ou None : non publiée, reprise_vue)
        self._attente: dict[tuple[int, int], dict[int, int]] = {}   # (partie, liaison) -> {rang: n°} (mémoire relue)
        self._reprise_cle: tuple | None = None             # (instance, sauvegarde, liaison) déjà reprise / en cours
        self._paquets: list[list[tuple[int, int]]] = []    # paquets de reprise restant à écrire
        self._seq_attendue = 0                             # séquence écrite dont on attend `reprise_vue`
        self._vue = 0                                      # dernière `reprise_vue` connue
        self._signal: tuple[int, int] | None = None        # (journal_ecrit, terrain_numero) à la dernière relecture
        self._t_relecture = 0.0
        self.relectures = 0                                # relectures de `reprise_vue` (tests de charge)
        self.reprises: list[list[tuple[int, int]]] = []    # paquets écrits (journal des tests)
        # après la victoire (§14)
        self._fin: int | None = None                       # partie dont la victoire est prise en compte
        self._purge_instance: int | None = None            # instance du jeu déjà examinée
        self._purge_demandee = False                       # file du jeu à vider (victoire, PIEGE_RECU ensuite)
        self._purge_signal: tuple[int, int] | None = None
        self._purge_t = 0.0
        self.purges: list[int] = []                        # pièges en file au moment de chaque purge (tests)
        self.essais_purge = 0                              # lectures de l'état de la file pour une purge (tests)

    # ------------------------------------------------------------------ graine
    def appliquer(self, sd: dict) -> None:
        self.pieges = lire_slot_data(sd)
        self.absents = ()
        if self.pieges:
            self.s.log.info("Pièges de la graine : %s", ", ".join(nom_piege(n, "fr") for n in sorted(self.pieges)))

    @property
    def actif(self) -> bool:
        return bool(self.pieges)

    def nouvelle_instance(self) -> None:
        self._lu = None
        self._reprise_cle = None
        self._paquets, self._seq_attendue, self._signal = [], 0, None

    def oublier(self) -> None:
        self._reprise_cle = None
        self._paquets, self._seq_attendue, self._signal = [], 0, None

    # ------------------------------------------------------------------ mémoire (liaisons.json)
    @staticmethod
    def cle_memoire(ident: int, liaison: int) -> str:
        return f"{ident & 0xFFFFFFFF:08x}:{liaison & 0xFFFF:04x}:pieges"

    def attente(self, ident: int, liaison: int) -> dict[int, int]:
        """Rangs reçus et pas finis de cette sauvegarde : {rang: n° du piège}."""
        k = (ident, liaison)
        if k not in self._attente:
            e = self.s.liaisons._tout().get(self.cle_memoire(ident, liaison))
            out: dict[int, int] = {}
            for x in (e.get("attente") if isinstance(e, dict) else None) or []:
                if isinstance(x, list) and len(x) == 2 and all(isinstance(v, int) and not isinstance(v, bool)
                                                               for v in x) \
                        and 0 < x[0] <= 0xFFFFFF and 0 <= x[1] < 256:
                    out[x[0]] = x[1]
            self._attente[k] = out
        return self._attente[k]

    def _enregistrer(self, ident: int, liaison: int) -> None:
        reg = self.s.liaisons
        d = reg._tout()                                    # relu : les autres mémoires du fichier sont gardées
        a = self._attente[(ident, liaison)]
        d[self.cle_memoire(ident, liaison)] = {"attente": [[r, n] for r, n in sorted(a.items())],
                                               "date": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            reg.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp = reg.fichier.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(reg.fichier)
        except OSError as e:
            self.s.log.warning("Pièges : mémoire non enregistrée : %s", e)

    def evenements(self, h, evts) -> None:
        """PIEGE_RECU (rang reçu, à faire) et PIEGE_FAIT (toute issue : fini) de la sauvegarde liée -> mémoire."""
        if not self.pieges or h is None:
            return
        ident, liaison = self.s.ident_partie or 0, getattr(h, "liaison_sauvegarde", 0)
        if not ident or not liaison:
            return
        a = self.attente(ident, liaison)
        change = False
        fini = self.s.partie_finie
        for e in evts:
            if e.type == bp.EVT_PIEGE_RECU and fini:
                # objectif atteint (§14) : piège déposé avant la victoire, entré dans la file du jeu après : retiré
                # par la purge, jamais mémorisé (aucune reprise)
                self._purge_demandee = True
                self.s.log.info("Piège %s (rang %d) entré dans la file du jeu après la victoire : à retirer",
                                nom_piege(e.id & 0xFF, "fr"), e.valeur)
            elif e.type == bp.EVT_PIEGE_RECU and 0 < e.valeur <= 0xFFFFFF and a.get(e.valeur) != (e.id & 0xFF):
                a[e.valeur] = e.id & 0xFF
                change = True
            elif e.type == bp.EVT_PIEGE_FAIT and e.valeur in a:
                del a[e.valeur]
                change = True
                self.s.log.info("Piège %s (rang %d) : %s", nom_piege(e.id & 0xFF, "fr"), e.valeur,
                                bp.PIEGES_ISSUES.get(e.drapeaux, f"issue {e.drapeaux}"))
        if change:
            self._enregistrer(ident, liaison)

    # ------------------------------------------------------------------ bandeaux
    def textes_reception(self, pieges: list[int], langue: str, au_dela: int = 3, fini: bool = False) -> list[str]:
        """Bandeaux des pièges reçus (n° dans l'ordre des dons), une ligne chacun ; au-delà de `au_dela`, un résumé.
        `fini` (objectif atteint, §14) : « Piège ignoré : <nom> » chacun (ou « N pièges ignorés »), puis « Partie
        finie : sans effet »."""
        t = textes(langue)
        if fini and pieges:
            if len(pieges) > au_dela:
                return [t["ignores"].format(n=len(pieges)), t["fini"]]
            return [t["ignore"].format(nom=nom_piege(n, langue, court=True)) for n in pieges] + [t["fini"]]
        if len(pieges) > au_dela:
            return [t["recus"].format(n=len(pieges))]
        compiles = self.compiles()
        out = []
        for n in pieges:
            absent = compiles is not None and not compiles >> n & 1
            out.append(t["ignore" if absent else "recu"].format(nom=nom_piege(n, langue, court=True)))
            if not absent and n in bp.PIEGES_DE_COMBAT:
                out.append(t["combat"])
        return out

    # ------------------------------------------------------------------ jeu
    def compiles(self) -> int | None:
        """Masque des pièges compilés lu pour l'instance en cours (None : pas encore lu ou zone non publiée)."""
        if self._lu is None or self._lu[0] != self.s._instance:
            return None
        return self._lu[1]

    async def _lire(self, h) -> None:
        if self._lu is not None and self._lu[0] == self.s._instance:
            return
        compile_, vue = None, 0
        if zone_disponible(h):
            b = await self.s.pont.lire(bp.ZONE + bp.OFF_PIEGES, TAILLE_LECTURE)
            c = struct.unpack_from("<I", b, 0)[0]
            vue = struct.unpack_from("<I", b, OFF_REPRISE_VUE)[0]
            compile_ = c & 0xFF if c & bp.PIEGES_PUBLIE else None
        self._lu, self._vue = (self.s._instance, compile_, vue), vue
        self.s.log.info("Pièges compilés dans le jeu : %s",
                        "zone non publiée (jeu d'avant les pièges)" if compile_ is None else f"{compile_:#x}")

    async def verifier(self, h) -> None:
        """Avertissement (jamais de refus) pour chaque piège de la graine absent du patch ; la fonction 53, elle, est
        exigée par la graine (refus géré avec les autres fonctions étendues)."""
        if not self.pieges or h is None:
            self.absents = ()
            return
        await self._lire(h)
        c = self.compiles()
        absents = () if c is None else tuple(sorted(n for n in self.pieges if not c >> n & 1))
        if absents != self.absents and absents:
            langue = self.s.catalogue.langue
            self.s.log.warning(textes(langue)["absents"].format(
                noms=", ".join(nom_piege(n, langue) for n in absents)))
        self.absents = absents

    async def suivre(self, h) -> None:
        """Pendant une reprise en plusieurs paquets seulement : relit `reprise_vue` (4 octets) quand l'en-tête annonce
        un changement (journal, passage sur le terrain) ou après le filet ; aucune lecture sinon."""
        if not self._seq_attendue or h is None:
            return
        signal = (h.journal_ecrit, getattr(h, "terrain_numero", 0))
        maintenant = time.monotonic()
        if signal == self._signal and maintenant - self._t_relecture < PERIODE_FILET_REPRISE * self.s.echelle:
            return
        self._signal, self._t_relecture = signal, maintenant
        self.relectures += 1
        self._vue = struct.unpack("<I", await self.s.pont.lire(bp.ZONE + bp.OFF_PIEGES + OFF_REPRISE_VUE, 4))[0]
        if self._vue == self._seq_attendue:
            self._seq_attendue = 0

    async def ecrire(self, h) -> None:
        """Reprise des pièges mémorisés (sauvegarde liée, une fois par instance et par sauvegarde) : un paquet de 7
        entrées au plus, `reprise_seq` en dernier ; le paquet suivant attend `reprise_vue` (`suivre`)."""
        if not self.pieges or h is None or self.compiles() is None or self._seq_attendue or self.s.partie_finie:
            return                                         # (objectif atteint, §14 : plus aucune reprise)
        ident, liaison = self.s.ident_partie or 0, getattr(h, "liaison_sauvegarde", 0)
        if self.s.sauvegarde != "liee" or self.s._liaison is None or not ident or not liaison:
            return
        cle = (self.s._instance, getattr(h, "ident_sauvegarde", 0), liaison)
        if cle != self._reprise_cle:
            self._reprise_cle = cle
            a = sorted((r, n) for r, n in self.attente(ident, liaison).items() if r <= h.compteur)
            self._paquets = [a[i:i + bp.CAP_PIEGES_REPRISE] for i in range(0, len(a), bp.CAP_PIEGES_REPRISE)]
            if a:
                self.s.log.info("Pièges reçus et pas finis à redonner au jeu : %s",
                                ", ".join(f"{nom_piege(n, 'fr')} (rang {r})" for r, n in a))
        if not self._paquets:
            return
        paquet = self._paquets.pop(0)
        seq = (self._vue % 0xFFFFFFFE) + 1                 # ≠ reprise_vue et jamais 0
        async with self.s.pont.transaction():
            for off, octets in bp.ecritures_reprise(paquet, seq):
                await self.s.pont.ecrire(bp.ZONE + off, octets)
        self.reprises.append(paquet)
        self._vue = seq                                    # (le jeu passera reprise_vue à seq : la suivante = seq + 1)
        if self._paquets:                                  # paquet suivant : quand `suivre` aura relu reprise_vue == seq
            self._seq_attendue, self._signal, self._t_relecture = seq, None, 0.0
        self.s.log.info("Pièges : reprise de %d entrée(s) écrite(s) (séquence %d)", len(paquet), seq)

    # ------------------------------------------------------------------ après la victoire (§14)
    async def apres_victoire(self, h) -> None:
        """Objectif atteint (`Synchro.partie_finie`) : victoire retenue pour la partie (`liaisons.json`), mémoire des
        pièges reçus pas finis effacée (plus de reprise), et file des pièges du jeu VIDÉE une fois par instance du jeu
        (puis à chaque PIEGE_RECU arrivé après la victoire) par l'écriture d'ApPieges::ident = 0 : le jeu fait alors
        son vider() habituel. Hors combat seulement (`bp.pieges_purge_motif`) ; l'état est lu jeu en marche, puis
        relu et écrit jeu arrêté (une transaction), seulement s'il y a quelque chose à vider. Les pièges reçus après
        la victoire, eux, sont déposés en « type 0 » (`Synchro._don_a_deposer`) : ils n'entrent jamais dans la file."""
        if not self.pieges or h is None or not self.s.partie_finie:
            return
        ident = self.s.ident_partie or 0
        if not ident:
            return
        if self._fin != ident:
            self._fin = ident
            self._purge_demandee = True
            self._paquets, self._seq_attendue = [], 0       # reprise en cours abandonnée
            self.s.liaisons.ecrire_victoire(ident)
            self.s._victoire_memoire[ident] = True
            self.s.log.info("Objectif atteint : les pièges reçus désormais n'ont plus d'effet (déposés sans effet, "
                            "file du jeu vidée, aucune reprise)")
        liaison = getattr(h, "liaison_sauvegarde", 0)
        if liaison and self.attente(ident, liaison):
            self.s.log.info("Pièges reçus pas finis oubliés (partie finie) : %s", ", ".join(
                f"{nom_piege(n, 'fr')} (rang {r})" for r, n in sorted(self.attente(ident, liaison).items())))
            self.attente(ident, liaison).clear()
            self._enregistrer(ident, liaison)
        if self._purge_instance != self.s._instance:
            self._purge_instance, self._purge_demandee, self._purge_signal = self.s._instance, True, None
        if not self._purge_demandee or self.compiles() is None or getattr(h, "ident_partie", 0) != ident:
            return
        signal = (h.journal_ecrit, getattr(h, "terrain_numero", 0))
        maintenant = time.monotonic()
        if signal == self._purge_signal and maintenant - self._purge_t < PERIODE_FILET_PURGE * self.s.echelle:
            return
        self._purge_signal, self._purge_t = signal, maintenant
        self.essais_purge += 1
        etat = await self.s.pont.lire(bp.ZONE + bp.OFF_PIEGES, bp.TAILLE_PIEGES_ETAT)
        prive = await self.s.pont.lire(bp.ZONE + bp.OFF_PIEGES_PRIVE, 0x10)
        motif = bp.pieges_purge_motif(etat, prive)
        if motif == bp.PURGE_OK:
            async with self.s.pont.transaction():          # relu jeu arrêté : rien n'a changé entre-temps
                etat = await self.s.pont.lire(bp.ZONE + bp.OFF_PIEGES, bp.TAILLE_PIEGES_ETAT)
                prive = await self.s.pont.lire(bp.ZONE + bp.OFF_PIEGES_PRIVE, 0x10)
                motif = bp.pieges_purge_motif(etat, prive)
                if motif == bp.PURGE_OK and struct.unpack_from("<I", etat, 4)[0] == ident:
                    await self.s.pont.ecrire(bp.ZONE + bp.OFF_PIEGES_IDENT, struct.pack("<I", 0))
                    self.purges.append(etat[0x26])
                    self.s.log.info("Piège(s) du jeu retiré(s) (partie finie) : %d en file, montre %d, pluie %d",
                                    etat[0x26], *struct.unpack_from("<HH", etat, 0x14))
        if motif in (bp.PURGE_RIEN, bp.PURGE_OK):
            self._purge_demandee = False
        else:
            self.s.log.info("Pièges : file du jeu à vider après la victoire, %s : nouvel essai plus tard",
                            "combat en cours" if motif == bp.PURGE_COMBAT else "rotation de la roue ou Oni en cours")
