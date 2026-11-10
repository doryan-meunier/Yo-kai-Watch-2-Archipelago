"""Boîte aux lettres v3 vue par le client : état de connexion publié par le client (écran Archipelago en lecture
seule, bandeau), progression (victoire), dons de script substitués (J3), noms de vitrine (J5) et verrous (J4). La
configuration saisie dans le jeu (`ConfigJeu`, `lire_config`) n'existe plus que dans un jeu antérieur au 2026-09-28 :
le client ne la lit plus (décodeur gardé pour les tests et les outils).

Aligné sur la spécification FINALE du côté jeu (branche ap/boite-v3, docs/systemes/archipelago_boite.md §10 à
§17) : les constantes et encodages viennent de `boite_protocole.py` (v3), vérifié contre `src/archipelago/boite.h`
par `tools/ap_boite_test.py --selftest`. Les offsets des zones sont en plus RELUS dans l'en-tête (le jeu les
publie : 0x78, 0x7A, 0xA4, 0xA8, 0xBC) ; `DispositionV3` ne garde que les valeurs par défaut.

Règles (§7, §10.5) : le client n'écrit que les champs C ; mot de validation (`sequence`, `scripts_nombre`,
`noms_nombre`, `actifs`) écrit en DERNIER, dans un paquet séparé, jeu arrêté ; le mot de passe n'est jamais
republié (seulement `connu & 0x04`).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, replace

try:
    from . import boite_protocole as bp
    from .boite import Boite, Entete
except ImportError:                          # pragma: no cover - selon le mode d'import
    import boite_protocole as bp            # type: ignore[no-redef]
    from boite import Boite, Entete         # type: ignore[no-redef]

VERSION_V3 = 3
TAILLE_ZONE_V3 = bp.TAILLE_ZONE             # 0xA000

# --- configuration écrite par le JEU (§10.2) ---
CFG_REVISION, CFG_DRAPEAUX, CFG_REV_EFFACEE, CFG_CODE_CLAVIER = 0x00, 0x04, 0x08, 0x0C
CFG_SERVEUR, CFG_SLOT, CFG_MDP = (0x10, 128), (0x90, 64), (0xD0, 48)
TAILLE_CONFIG = bp.TAILLE_CONFIG
CFG_SERVEUR_PRESENT, CFG_SLOT_PRESENT, CFG_MDP_PRESENT, CFG_MDP_INCHANGE = (bp.CFG_SERVEUR, bp.CFG_SLOT, bp.CFG_MDP,
                                                                          bp.CFG_MDP_INCHANGE)

# --- état de connexion écrit par le CLIENT (§10.3) ---
CX_SEQUENCE, CX_ETAT, CX_REV_LUE, CX_ERREUR, CX_DRAPEAUX, CX_IMAGES, CX_CONNU = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18
TAILLE_CONNEXION = bp.TAILLE_CONNEXION
ABSENT, NON_CONFIGURE, CONNEXION, CONNECTE, ERREUR, DECONNECTE = 0, 1, 2, 3, 4, 5
NOMS_ETAT = bp.ETATS_CONNEXION
ERR_AUCUNE, ERR_INJOIGNABLE, ERR_SLOT, ERR_MDP, ERR_VERSION, ERR_JEU, ERR_AUTRE = 0, 1, 2, 3, 4, 5, 6
CX_DEMANDER_SAISIE, CX_AFFICHER_MESSAGE, CX_EFFACER_MDP = bp.CNX_DEMANDE_SAISIE, bp.CNX_MESSAGE, bp.CNX_EFFACER_MDP
CONNU_SERVEUR, CONNU_SLOT, CONNU_MDP = 0x01, 0x02, 0x04
SAISIE_RIEN, SAISIE_CLAVIER_OUVERT, SAISIE_VALIDEE, SAISIE_ANNULEE, SAISIE_ERREUR = (0, bp.SAISIE_OUVERTE,
                                                                                    bp.SAISIE_VALIDEE,
                                                                                    bp.SAISIE_ANNULEE, bp.SAISIE_ERREUR)

# --- spots d'objets-clés et verrous (§12.4, §16) : k = bit - 558 ---
SPOTS_PAR_DEFAUT = {
    "filet_a_insectes": 558, "pile_ou_passe": 559, "cles_de_l_ecole": 560, "herbe_ancestrale": 561,
    "super_tournevis": 562, "canne_a_peche": 563, "modele_zero": 564, "indications_de_maman": 565,
    "cle_de_derriere": 566, "cle_magnetique_or": 567, "cle_salle_du_tresor": 568, "poignee_etrange": 569,
    # 570 : k = 12 du Vélo (verrou sans spot, bit jamais posé) ; 571..575 : objets du Musée en détresse donnés par des
    # PNJ qui les redonnent (sans marqueur persistant), archipelago_objets_cles_v11.md §16 ; les autres objets-clés de
    # quête n'ont pas de bit (SCRIPT_BIT_AUCUN, détection par flag ou quête, slot_data format 13)
    "poster_de_film": 571, "bobine_de_film": 572, "bouteille_de_y_cola": 573, "affiche_de_restaurant": 574,
    "louloutre": 575,
}
BITS_RESERVES = range(bp.TBOX_SPOT_PREMIER, bp.TBOX_NOMBRE)   # jamais des coffres
VITRINE = bp.VITRINE_DEFAUT


@dataclass(frozen=True)
class DispositionV3:
    """Valeurs par défaut (spécification finale) ; les offsets publiés par le jeu dans l'en-tête priment."""
    config_off: int = bp.OFF_CONFIG
    connexion_off: int = bp.OFF_CONNEXION
    scripts_off: int = bp.OFF_SCRIPTS
    noms_off: int = bp.OFF_NOMS
    verrous_off: int = bp.OFF_VERROUS
    version_min: int = VERSION_V3


def _cstr(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("utf-8", "replace")


@dataclass(frozen=True)
class ConfigJeu:
    """Configuration saisie dans un jeu antérieur au 2026-09-28 (§10.2) ; plus lue par le client."""
    revision: int = 0
    drapeaux: int = 0
    revision_effacee: int = 0
    code_clavier: int = 0
    serveur: str = ""
    slot: str = ""
    mot_de_passe: str = ""

    @property
    def mdp_inchange(self) -> bool:
        return bool(self.drapeaux & CFG_MDP_INCHANGE)

    @classmethod
    def decoder(cls, b: bytes) -> "ConfigJeu":
        d = bp.dec_config(b)
        return cls(d["revision"], d["drapeaux"], d["revision_effacee"], d["erreur"], d["serveur"].strip(),
                   d["slot"].strip(), d["mdp"])

    def encoder(self) -> bytes:
        """Pour les tests (modèle du jeu) : ce que le jeu écrit."""
        return bp.enc_config(self.revision, self.drapeaux, self.serveur, self.slot, self.mot_de_passe,
                             self.revision_effacee, self.code_clavier)


@dataclass(frozen=True)
class EtatConnexion:
    """État publié par le client (§10.3), sans `sequence` (gérée par `ZoneConnexion.publier`)."""
    etat: int = NON_CONFIGURE
    revision_lue: int = 0
    erreur: int = ERR_AUCUNE
    drapeaux: int = 0
    client_images: int = 0
    connu: int = 0
    message: str = ""
    serveur: str = ""
    slot: str = ""

    def corps(self) -> bytes:
        """Octets +4 .. +0x200 (tout sauf sequence)."""
        return bp.enc_connexion(0, self.etat, self.revision_lue, self.erreur, self.drapeaux, self.client_images,
                                self.connu, self.message, self.serveur, self.slot)[4:]

    def sans_images(self) -> "EtatConnexion":
        return replace(self, client_images=0)

    @classmethod
    def decoder(cls, b: bytes) -> tuple[int, "EtatConnexion"]:
        d = bp.dec_connexion(b)
        return d["sequence"], cls(d["etat"], d["revision_lue"], d["erreur"], d["drapeaux"], d["client_images"],
                                  d["connu"], d["message"], d["serveur"], d["slot"])


@dataclass(frozen=True)
class EntreeScript:
    """Don de script substitué (§12.1)."""
    origine: int
    affiche: int = 0                     # 0 = la vitrine
    bit: int = bp.SCRIPT_BIT_AUCUN
    drapeaux: int = 0                    # SCRIPT_DONNER
    etiquette: int = 0

    def encoder(self) -> bytes:
        return bp.enc_script(self.origine, self.affiche, self.bit, self.drapeaux, self.etiquette)


def champ_entete(brut: bytes, nom: str) -> int:
    o, f = bp.CHAMP[nom]
    return struct.unpack_from("<" + f, brut, o)[0]


class ZoneConnexion:
    """Accès aux zones v3 au-dessus de `boite.Boite`."""

    def __init__(self, boite: Boite, disposition: DispositionV3 | None = None):
        self.boite = boite
        self.d = disposition or DispositionV3()
        self._off = {"config": self.d.config_off, "connexion": self.d.connexion_off, "scripts": self.d.scripts_off,
                     "noms": self.d.noms_off, "verrous": self.d.verrous_off}
        self.capacites = {"scripts": bp.CAP_SCRIPTS, "noms": bp.CAP_NOMS, "verrous": bp.CAP_VERROUS}
        self._noms2: tuple | None = None     # (instance, places de la suite de la table des noms publiées, §13bis)

    @property
    def gdb(self):
        return self.boite.gdb

    def disponible(self, h: Entete) -> bool:
        return h.version >= self.d.version_min

    def ajuster(self, brut: bytes) -> None:
        """Prend les offsets et capacités publiés par le jeu dans l'en-tête (s'ils sont non nuls)."""
        taille = champ_entete(brut, "taille_zone") or TAILLE_ZONE_V3
        for zone, champ, t in (("config", "config_off", TAILLE_CONFIG), ("connexion", "connexion_off", TAILLE_CONNEXION),
                               ("noms", "noms_off", bp.TAILLE_NOM), ("verrous", "verrous_off", bp.TAILLE_VERROUS)):
            v = champ_entete(brut, champ)
            if v and v + t <= taille:
                self._off[zone] = v
        for zone, champ in (("noms", "noms_capacite"), ("verrous", "verrous_capacite")):
            v = champ_entete(brut, champ)
            if v:
                self.capacites[zone] = v
        # dons de script : offset ET capacité publiés ensemble (0xDC40 / 48 depuis les objets-clés de quête, 0x4300 / 16
        # avant) ; une paire qui ne tient pas dans la zone publiée est écartée pour l'emplacement v3 d'origine, présent
        # dans toute zone v3 et plus (jamais d'écriture hors de la zone d'un jeu ancien)
        off, cap = champ_entete(brut, "scripts_off"), champ_entete(brut, "scripts_capacite")
        if off and cap and off + cap * bp.TAILLE_SCRIPT <= taille:
            self._off["scripts"], self.capacites["scripts"] = off, cap
        elif self._off["scripts"] + self.capacites["scripts"] * bp.TAILLE_SCRIPT > taille:
            self._off["scripts"], self.capacites["scripts"] = bp.OFF_SCRIPTS_V3, bp.CAP_SCRIPTS_V3

    def adresse(self, zone: str) -> int:
        return bp.ZONE + self._off[zone]

    @property
    def adresse_config(self) -> int:
        return self.adresse("config")

    @property
    def adresse_connexion(self) -> int:
        return self.adresse("connexion")

    async def lire_entete_brut(self) -> bytes:
        return await self.gdb.lire(bp.ZONE, bp.TAILLE_ENTETE)

    @staticmethod
    def saisie_etat(brut: bytes) -> int:
        return champ_entete(brut, "saisie_etat")

    @staticmethod
    def ecran_ouvert(brut: bytes) -> bool:
        return bool(champ_entete(brut, "ecran_ouvert"))

    # ------------------------------------------------------------------ configuration / état
    async def lire_config(self) -> ConfigJeu:
        return ConfigJeu.decoder(await self.gdb.lire(self.adresse_config, TAILLE_CONFIG))

    async def lire_revision(self) -> int:
        return struct.unpack("<I", await self.gdb.lire(self.adresse_config, 4))[0]

    async def lire_etat(self) -> tuple[int, EtatConnexion]:
        return EtatConnexion.decoder(await self.gdb.lire(self.adresse_connexion, TAILLE_CONNEXION))

    async def publier(self, etat: EtatConnexion) -> int:
        """Écrit l'état (jeu arrêté) : corps, puis `sequence` + 1 en dernier. Renvoie la nouvelle séquence
        (relue dans la mémoire du jeu : elle repart de 0 après un relancement)."""
        async with self.gdb.transaction():
            seq = struct.unpack("<I", await self.gdb.lire(self.adresse_connexion, 4))[0]
            await self.gdb.ecrire(self.adresse_connexion + 4, etat.corps())
            seq = (seq + 1) & 0xFFFFFFFF or 1
            await self.gdb.ecrire(self.adresse_connexion, struct.pack("<I", seq))
            return seq

    async def battement(self, images: int) -> None:
        """client_images seul (pas de changement de séquence)."""
        async with self.gdb.transaction():
            await self.gdb.ecrire(self.adresse_connexion + CX_IMAGES, struct.pack("<I", images & 0xFFFFFFFF))

    # ------------------------------------------------------------------ tables (J3, J5, J4)
    async def _ecrire_table(self, zone: str, entrees: list[bytes], champ_nombre: str) -> None:
        if len(entrees) > self.capacites[zone]:
            raise ValueError(f"{len(entrees)} entrées pour la table {zone} (capacité {self.capacites[zone]})")
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            if entrees:
                await self.gdb.ecrire(self.adresse(zone), b"".join(entrees))
            adr, v = bp.champ(champ_nombre, len(entrees))
            await self.gdb.ecrire(adr, v)                           # nombre en dernier

    async def ecrire_scripts(self, entrees: list[EntreeScript]) -> None:
        """Table des dons de script (§12) : entrées puis `scripts_nombre`."""
        await self._ecrire_table("scripts", [e.encoder() for e in entrees], "scripts_nombre")

    async def capacite_noms(self, h: Entete, instance=None) -> int:
        """Places de noms de vitrine : table du §13 (`noms_capacite`) + sa suite (§13bis) si le jeu la publie (mot
        `publie` lu une fois par instance du jeu ; jeu antérieur : rien n'est lu à 0x27FC0, hors de sa zone)."""
        if self._noms2 is None or self._noms2[0] != instance:
            cap2 = 0
            if bp.noms2_disponible(h):
                cap2 = bp.noms2_publie(await self.gdb.lire(bp.ZONE + bp.OFF_NOMS2_ENTETE, 16))
            self._noms2 = (instance, cap2)
        return self.capacites["noms"] + self._noms2[1]

    async def ecrire_noms(self, noms: dict[int, str]) -> None:
        """Noms de vitrine par ÉTIQUETTE (identifiant de location AP) (§13) : entrées puis `noms_nombre` ; au-delà
        de `noms_capacite`, dans la suite (§13bis) si le jeu la publie (`capacite_noms` appelé avant), entrées puis
        son `nombre`. Plus de noms que de places : ValueError (l'appelant choisit lesquels garder)."""
        entrees = [bp.enc_nom(et, bp.nom_vitrine(texte)) for et, texte in sorted(noms.items()) if et]
        cap1 = self.capacites["noms"]
        cap2 = self._noms2[1] if self._noms2 is not None else 0
        if len(entrees) > cap1 + cap2:
            raise ValueError(f"{len(entrees)} noms de vitrine pour {cap1 + cap2} places")
        await self._ecrire_table("noms", entrees[:cap1], "noms_nombre")
        if cap2:
            suite = entrees[cap1:]
            async with self.gdb.transaction():
                await self.boite.entete_arret()
                if suite:
                    await self.gdb.ecrire(bp.ZONE + bp.OFF_NOMS2, b"".join(suite))
                await self.gdb.ecrire(bp.ZONE + bp.OFF_NOMS2_ENTETE + bp.NOMS2_OFF_NOMBRE,
                                      struct.pack("<I", len(suite)))      # nombre en dernier

    # ------------------------------------------------------------------ v5 : récompenses de quête (§21)
    @staticmethod
    def recompenses_disponibles(h: Entete) -> bool:
        """Jeu v5 : zone assez grande pour la table des récompenses de quête (un jeu v4 n'a rien à 0xA000 : ne
        JAMAIS y écrire, ce serait hors de la zone réservée)."""
        return h.version >= bp.VERSION_RECOMPENSES and h.taille_zone >= bp.TAILLE_ZONE_V5

    async def lire_quetes_entete(self) -> bytes:
        return await self.gdb.lire(bp.ZONE + bp.OFF_QUETES, 0x40)

    async def ecrire_recompenses(self, entrees: dict[int, bytes]) -> None:
        """Table des récompenses de quête (§21) : une entrée de 80 octets par n° de quête (les autres à 0 : récompense
        d'origine), puis `valide` en DERNIER (1 s'il y a au moins une entrée, sinon 0 : table ignorée)."""
        table = bytearray(bp.CAP_QUETES * bp.TAILLE_QUETE)
        for n, e in entrees.items():
            if not 0 <= n < bp.CAP_QUETES or len(e) != bp.TAILLE_QUETE:
                raise ValueError(f"entrée de récompense invalide : quête {n}")
            table[n * bp.TAILLE_QUETE:(n + 1) * bp.TAILLE_QUETE] = e
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_QUETES_TABLE, bytes(table))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_QUETES, struct.pack("<I", 1 if entrees else 0))

    # ------------------------------------------------------------------ v6 : randomizer de Yo-kai (§22)
    @staticmethod
    def rando_disponible(h: Entete) -> bool:
        """Jeu v6 : zone assez grande pour les tables du mélange (un jeu v5 n'a rien à 0xE000 : ne JAMAIS y écrire)."""
        return h.version >= bp.VERSION_RANDO and h.taille_zone >= bp.TAILLE_ZONE_V6

    @staticmethod
    def rando_rencontre_disponible(h: Entete) -> bool:
        """Jeu v10 : zone assez grande pour les tables du mélange par rencontre (un jeu v9 n'a rien à 0x20000)."""
        return h.version >= bp.VERSION_RANDO_RENCONTRE and h.taille_zone >= bp.TAILLE_ZONE_V10

    async def lire_rando_entete(self) -> bytes:
        return await self.gdb.lire(bp.ZONE + bp.OFF_RANDO, 0x40)

    async def ecrire_rando_valide(self, generation: int) -> None:
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO, struct.pack("<I", generation & 0xFFFFFFFF))

    async def ecrire_rando(self, sigma: dict[int, int], beta: dict[int, int], w, generation: int,
                           empreinte: int) -> None:
        """Tables du mélange (§22), jeu arrêté, dans cet ordre : table_gen = 0, σ, β, W, nombres et empreinte,
        table_gen = génération, puis valide = génération EN DERNIER. À n'appeler que si aucune table n'a de mélange
        appliqué d'une autre génération (gen_carte / gen_commune publiés à 0) : le jeu ne pourrait plus le retirer."""
        sig = {a: b for a, b in sigma.items() if a != b}
        bet = {a: b for a, b in beta.items() if a != b}
        lw = sorted(set(w))
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 8, struct.pack("<I", 0))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_SIGMA, bp.enc_paires(sig, bp.CAP_RANDO_SIGMA))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_BETA, bp.enc_paires(bet, bp.CAP_RANDO_BETA))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_W, bp.enc_w(lw))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 0x0C,
                                  struct.pack("<HHII", len(sig), len(bet), len(lw), empreinte & 0xFFFFFFFF))
            # v10 : p_nombre = 0 (mélange σ) ; champ réservé d'un jeu v6-v9 (dans l'en-tête : sans effet)
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 0x3C, struct.pack("<HH", 0, 0))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 8, struct.pack("<I", generation))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO, struct.pack("<I", generation))

    async def ecrire_rando_rencontre(self, entrees, especes, w, generation: int, empreinte: int) -> None:
        """v10 : tables du mélange par rencontre (§22.4), jeu arrêté : table_gen = 0, espèces, entrées P, W, nombres
        (σ = β = 0, p_nombre, especes_nombre) et empreinte, table_gen, puis valide EN DERNIER. Mêmes conditions que
        `ecrire_rando` ; seulement si `rando_rencontre_disponible` et le bit RANDO_PAR_RENCONTRE est publié."""
        lw = sorted(set(w))
        # V3 : au-delà de CAP_RANDO_P entrées, la suite va dans la zone σ / β (bit RANDO_P_ETENDU, vérifié par l'appelant)
        # V3 (M2a-bis) : au-delà de CAP_RANDO_ESPECES espèces, la suite dans la 2e table (bit RANDO_ESPECES_ETENDU,
        # vérifié par l'appelant)
        (esp, esp2), (p, p2) = bp.enc_especes_etendu(especes), bp.enc_p_etendu(entrees)
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 8, struct.pack("<I", 0))
            if esp:
                await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_ESPECES, esp)
            if esp2:
                await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_ESPECES2, esp2)
            if p:
                await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_P, p)
            if p2:
                await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_P2, p2)
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO_W, bp.enc_w(lw))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 0x0C,
                                  struct.pack("<HHII", 0, 0, len(lw), empreinte & 0xFFFFFFFF))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 0x3C, struct.pack("<HH", len(entrees), len(especes)))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO + 8, struct.pack("<I", generation))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_RANDO, struct.pack("<I", generation))

    # ------------------------------------------------------------------ v7 : randomizer des boss (§24)
    @staticmethod
    def boss_disponible(h: Entete) -> bool:
        """Jeu v7 : zone assez grande pour les tables des boss (un jeu v6 n'a rien à 0x12000 : ne JAMAIS y écrire)."""
        return h.version >= bp.VERSION_BOSS and h.taille_zone >= bp.TAILLE_ZONE_V7

    async def lire_boss_entete(self) -> bytes:
        return await self.gdb.lire(bp.ZONE + bp.OFF_BOSS, 0x40)

    async def ecrire_boss_valide(self, generation: int) -> None:
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS, struct.pack("<I", generation & 0xFFFFFFFF))

    async def ecrire_boss(self, b: dict[int, int], n: dict[int, tuple[int, int]], generation: int,
                          empreinte: int, m: dict[int, tuple[int, ...]] | None = None) -> None:
        """Tables des boss (§24), jeu arrêté, dans cet ordre : table_gen = 0, B, N, (M et son nombre), nombres et
        empreinte, table_gen = génération, puis valide = génération EN DERNIER. Même condition que `ecrire_rando` (ancien
        mélange retiré). `m` : table M de la force adaptée (§49), écrite (vide comprise : nombre 0) SEULEMENT si le jeu
        publie BOSS_FORCE ; None : rien n'est écrit à 0x22800 ni en +0x3C (jeu sans la force adaptée)."""
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS + 8, struct.pack("<I", 0))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS_B, bp.enc_boss_b(b))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS_N, bp.enc_boss_n(n))
            if m is not None:
                if m:
                    await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS_M, bp.enc_boss_m(m)[:16 * len(m)])
                await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS + 0x3C, struct.pack("<H", len(m)))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS + 0x0C,
                                  struct.pack("<HHI", len(b), len(n), empreinte & 0xFFFFFFFF))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS + 8, struct.pack("<I", generation))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOSS, struct.pack("<I", generation))

    # ------------------------------------------------------------------ v9 : boutiques (§26)
    @staticmethod
    def boutiques_disponibles(h: Entete) -> bool:
        """Jeu v9 : zone assez grande pour la table des boutiques (un jeu v8 n'a rien à 0x16000 : ne JAMAIS y écrire)."""
        return h.version >= bp.VERSION_BOUTIQUES and h.taille_zone >= bp.TAILLE_ZONE_V9

    async def lire_boutiques_entete(self) -> bytes:
        return await self.gdb.lire(bp.ZONE + bp.OFF_BOUTIQUES, 0x40)

    async def ecrire_boutiques(self, entrees: list[bytes]) -> None:
        """Table des boutiques (§26), jeu arrêté : `valide` = 0, entrées triées par article (celles-là seulement : le jeu ne
        lit pas au-delà de `nombre`), `nombre`, puis `valide` = 1 EN DERNIER ; sans entrée : `valide` = 0 seulement
        (table ignorée, boutiques d'origine)."""
        table = bp.enc_table_boutiques(entrees)[:len(entrees) * bp.TAILLE_BOUTIQUE]
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOUTIQUES, struct.pack("<I", 0))
            if not entrees:
                return                                      # table ignorée par le jeu : rien d'autre à écrire
            # seulement les entrées utiles (le jeu ne lit pas au-delà de `nombre`)
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOUTIQUES_TABLE, table)
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOUTIQUES + 8, struct.pack("<I", len(entrees)))
            await self.gdb.ecrire(bp.ZONE + bp.OFF_BOUTIQUES, struct.pack("<I", 1))

    # ------------------------------------------------------------------ invités de l'Auberge des voyageurs (§31)
    @staticmethod
    def invites_disponibles(h: Entete) -> bool:
        """Zone assez grande pour ApInvites (trou de la zone v10 : un jeu antérieur n'a rien là, ne JAMAIS y écrire)."""
        return h.taille_zone >= bp.OFF_INVITES + bp.TAILLE_INVITES

    async def lire_invites_compile(self) -> int | None:
        """Bits INVITES_* compilés dans le jeu, None si le champ n'est pas publié."""
        return bp.invites_compiles(await self.gdb.lire(bp.ZONE + bp.OFF_INVITES, 4))

    async def ecrire_invites(self, invites: list[tuple], ident: int, sequence: int,
                             compile2: int | None = None) -> None:
        """Liste des invités (§31), jeu arrêté : liste, ident et nombre, puis `sequence` EN DERNIER. Ne touche ni
        `compile` (jeu) ni `forcer` (outil de test). 32 entrées au plus : les écritures de la V2, à l'octet près ;
        au-delà (V3, lot 14) : d'abord la suite dans ApInvites2 (`bp.ecritures_invites_v3`, `compile2` = bits lus
        dans le jeu : refus sans la liste à 64)."""
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            for adresse, octets in bp.ecritures_invites_v3(invites, ident, sequence, compile2):
                await self.gdb.ecrire(adresse, octets)

    @staticmethod
    def invites2_disponibles(h: Entete) -> bool:
        """Zone assez grande pour ApInvites2 (un jeu antérieur n'a rien là, ne JAMAIS y écrire)."""
        return h.taille_zone >= bp.OFF_INVITES2 + bp.TAILLE_INVITES2

    async def lire_invites2_compile(self) -> int | None:
        """Bits INVITES2_* compilés dans le jeu (liste à 64, taux par invité), None si la zone n'est pas publiée."""
        return bp.invites2_compiles(await self.gdb.lire(bp.ZONE + bp.OFF_INVITES2, 8))

    # ------------------------------------------------------------------ fonctions étendues du patch (§32)
    @staticmethod
    def pnj_disponibles(h: Entete) -> bool:
        """Zone assez grande pour ApPnj (un jeu antérieur n'a rien là)."""
        return h.taille_zone >= bp.OFF_PNJ + bp.TAILLE_PNJ

    async def lire_fonctions_etendues(self) -> int | None:
        """Bits des fonctions étendues (n° 32 + b) compilées dans le jeu, None si le champ n'est pas publié."""
        return bp.fonctions_etendues(await self.gdb.lire(bp.ZONE + bp.OFF_PNJ, 4))

    async def ecrire_evenement(self, masque: int, ident: int) -> None:
        """Yo-kai d'évènement à leur emplacement d'origine (§33) : `ev_declares` et `ev_ident`, une écriture de 8
        octets, jeu arrêté. À n'appeler que si le jeu publie la fonction étendue 34."""
        adresse, octets = bp.ecriture_evenement(masque, ident)
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(adresse, octets)

    # ------------------------------------------------------------------ verrous étendus de la V3 (§34)
    @staticmethod
    def verrous2_disponibles(h: Entete) -> bool:
        """Zone assez grande pour ApVerrous2 (un jeu antérieur à la V3 n'y publie rien)."""
        return h.taille_zone >= bp.OFF_VERROUS2 + bp.TAILLE_VERROUS2

    async def lire_verrous2_compiles(self) -> int | None:
        """Verrous et options étendus compilés dans le jeu, None si la liste n'est pas publiée (jeu d'avant la V3)."""
        return bp.verrous2_compiles(await self.gdb.lire(bp.ZONE + bp.OFF_VERROUS2, 8))

    async def lire_verrous2(self) -> bytes:
        return await self.gdb.lire(bp.ZONE + bp.OFF_VERROUS2, bp.TAILLE_VERROUS2)

    async def ecrire_verrous2(self, actifs: int, recu: dict[int, bool], ident: int) -> None:
        """Verrous étendus (§34), jeu arrêté : recu[] et `ident` (+8, 20 octets) puis `actifs` (+0) EN DERNIER. À
        n'appeler que si le jeu publie la liste (`compiles`, jamais écrit ici)."""
        b = bp.enc_verrous2(actifs, recu, ident)
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_VERROUS2 + 8, b[8:])
            await self.gdb.ecrire(bp.ZONE + bp.OFF_VERROUS2, b[:4])

    # ------------------------------------------------------------------ deuxième zone de verrous étendus (§38)
    @staticmethod
    def verrous3_disponibles(h: Entete) -> bool:
        """Zone assez grande pour ApVerrous3 (un jeu d'avant le lot 5 de la V3 n'y publie rien)."""
        return h.taille_zone >= bp.OFF_VERROUS3 + bp.TAILLE_VERROUS3

    async def lire_verrous3_compiles(self) -> int | None:
        """Verrous k = 56..87 compilés dans le jeu (bit k - 56), None si la zone n'est pas publiée : les 16 premiers
        octets (`actifs`, `compiles`, `publie`, `ident`), une lecture."""
        return bp.verrous3_compiles(await self.gdb.lire(bp.ZONE + bp.OFF_VERROUS3, 0x10))

    async def ecrire_verrous3(self, actifs: int, recu: dict[int, bool], ident: int) -> None:
        """Verrous de la deuxième zone (§38), jeu arrêté : `ident` et recu[32] (+0x0C, 0x24 octets) puis `actifs`
        (+0) EN DERNIER. `compiles` et `publie` (+4, +8) sont au jeu : jamais écrits. À n'appeler que si le jeu
        publie la zone."""
        b = bp.enc_verrous3(actifs, recu, ident)
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(bp.ZONE + bp.OFF_VERROUS3 + 0x0C, b[0x0C:])
            await self.gdb.ecrire(bp.ZONE + bp.OFF_VERROUS3, b[:4])

    # ------------------------------------------------------------------ chance d'amitié (lot 16, §43)
    @staticmethod
    def amitie_disponible(h: Entete) -> bool:
        """Zone assez grande pour ApAmitie (un jeu d'avant le lot 16 de la V3 n'y publie rien)."""
        return h.taille_zone >= bp.OFF_AMITIE + bp.TAILLE_AMITIE

    async def lire_amitie_compilee(self) -> bool:
        """Le jeu publie ApAmitie et la chance d'amitié réglable y est compilée (8 octets, une lecture)."""
        return bp.amitie_compilee(await self.gdb.lire(bp.ZONE + bp.OFF_AMITIE, 8))

    async def ecrire_amitie(self, reglage: int, ident: int) -> None:
        """Réglage de la chance d'amitié (§43), jeu arrêté : `ident` et `reglage` en un paquet de 8 octets. À
        n'appeler que si le jeu publie la zone (`publie` / `compile`, jamais écrits ici)."""
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            for off, octets in bp.ecritures_amitie(reglage, ident):
                await self.gdb.ecrire(bp.ZONE + off, octets)

    # ------------------------------------------------------------------ pièces spéciales du Crank-a-kai (§45)
    @staticmethod
    def pieces_disponibles(h: Entete) -> bool:
        """Zone assez grande pour ApPieces (un jeu d'avant le lot 19 de la V3 n'y publie rien)."""
        return h.taille_zone >= bp.OFF_PIECES + bp.TAILLE_PIECES

    async def lire_pieces_compile(self) -> tuple[int, int] | None:
        """(bits PIECES_* compilés, options étendues 32.. compilées) du jeu, None si ApPieces n'est pas publiée
        (16 octets, une lecture)."""
        b = await self.gdb.lire(bp.ZONE + bp.OFF_PIECES, 16)
        c = bp.pieces_compilees(b)
        return None if c is None else (c, bp.dec_pieces(b)["options_compilees"])

    async def ecrire_pieces(self, ecritures: list[tuple[int, bytes]]) -> None:
        """Écritures de ApPieces (`bp.ecritures_pieces`, ou seulement celles qui ont changé, dans le même ORDRE :
        borne des dons, compteurs, ordre de sortie, identifiant, option en dernier), jeu arrêté. À n'appeler que si
        le jeu publie la zone (`publie`, `compile`, `options_compilees` ne sont jamais écrits ici)."""
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            for off, octets in ecritures:
                await self.gdb.ecrire(bp.ZONE + off, octets)

    async def lire_verrous(self) -> bytes:
        """Zone des verrous (§16, §20) : `compiles` (+4) et le diagnostic sont écrits par le jeu."""
        return await self.gdb.lire(self.adresse("verrous"), bp.TAILLE_VERROUS)

    async def ecrire_verrous(self, actifs: int, recu: dict[int, bool]) -> None:
        """Verrous (§16) : `recu[]` (+8) puis `actifs` (+0) en dernier."""
        b = bp.enc_verrous(actifs, recu)
        async with self.gdb.transaction():
            await self.boite.entete_arret()
            await self.gdb.ecrire(self.adresse("verrous") + 8, b[8:8 + bp.CAP_VERROUS])
            await self.gdb.ecrire(self.adresse("verrous"), b[:4])
