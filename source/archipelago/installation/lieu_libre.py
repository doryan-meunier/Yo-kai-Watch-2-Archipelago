"""ESSAI « invités à des lieux libres » : des Yo-kai posés à des endroits choisis (un par carte), à qui on parle
pour les combattre (bibliothèque standard seulement). Désactivé par défaut : rien de ceci n'entre dans
l'installation normale (`installer.py installer … --essai-lieu-libre` l'ajoute, la même commande sans l'option le
retire). Les lieux viennent de la TABLE `lieux_libres.txt` (lieux.py : format, hauteur déduite) ou de `--lieu`.

    python archipelago/installation/lieu_libre.py --romfs <ROM déchiffrée | RomFS extrait> --sortie <dossier>
           [--table <fichier> | --lieu t101g00:496,72 [--espece 0x6BB26576] [--reste]]
           [--condition toujours | bit:0x<hachage>] [--icone] [--verifier]

Tout est fabriqué CHEZ LE JOUEUR à partir de son RomFS (aucun octet du jeu dans le dépôt ni dans le paquet), pour
CHAQUE lieu de la table :

1. `data/res/map/<carte>/<carte>_npc_set_0.01b.cfg.bin` : + `NPC_BASE`, `NPC_PRESET`, `NPC_APPEAR` (compteurs des
   `*_BEGIN` + 1). Les entrées sont COPIÉES de celles du PNJ de la Suite de l'Auberge des voyageurs
   (`t103i69`, identifiant `crc32("npc_sasurai")`), avec la base de l'espèce voulue, le nom du fichier de position
   et la condition d'apparition.
2. `…/<carte>_npc_talk_0.03d.cfg.bin` : + `TALK_INFO`, `TALK_CONFIG` (copies de ceux de la Suite).
3. `…/<nom>.npcbin` (nouveau fichier) et le même dans `…/npc.pck` (le jeu lit l'un ou l'autre selon le moment,
   `FUN_004C6F60`) : copie de `sasurai.npcbin` de la Suite, `POINT` = (x, y, z, angle).
4. lieu marqué `reste` : `…/<carte>.pck|<carte>_trigger.cfg.bin` reçoit EN TÊTE un déclencheur
   `(77, 0x713FE778, 0, 0, 0, 0, 0)` : « fin du combat de la Suite » pris par la table de la CARTE (interrogée avant
   la table commune, `FUN_004484D8`) et sans script (n° 0 : rien n'est lancé). La scène d'adieu `ev98_0110`, qui
   efface le PNJ, n'est donc pas jouée sur cette carte : le Yo-kai reste, on lui reparle tout de suite.
Une fois pour toute la table :
5. `common_enc` (dossier `data/res/battle/`) : espèce du combattant de la rencontre `0x713FE778` (4 octets sur
   place) = celle du PREMIER lieu. EFFET DE BORD DE L'ESSAI : le combat de la Suite, et celui de tous les lieux,
   devient celui de cette espèce (le combattant « selon la carte » est à brancher côté natif).

En gardant l'identifiant du PNJ de la Suite, aucun script ni déclencheur n'est ajouté : « parler à ce PNJ »
(`common_trigger` n° 14 -> `ev98_0100`) et « fin du combat » (n° 125 -> `ev98_0110`) sont dans la table COMMUNE à
toutes les cartes (docs/systemes/archipelago_invites.md §2 et §9bis).

Archive touchée : `yw2_a.fa` (967 Mo). Les fichiers agrandis et les fichiers ajoutés vont À LA FIN de l'archive,
qui grandit de la taille des `npc.pck` / `npc_set` / `npc_talk` (+ `.pck` avec `reste`) de chaque carte
(`level5.arc0_modifier`) ; seules les tables de tête changent, aucun autre fichier ne
bouge. Un seul patch `romfs_ext/yw2_a.fa.bps` : avec l'icône de la vitrine, les deux modules sont fusionnés (la
grande image est ajoutée à la tête déjà modifiée, `icone.modifications_grande(tete_depart=…)`).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import struct
import sys
import tempfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import bps as _bps, t2b, icone as ico, level5 as L, lieux as LX
    from .lieux import Lieu
except ImportError:                     # lancé comme script
    import bps as _bps  # type: ignore[no-redef]
    import t2b  # type: ignore[no-redef]
    import icone as ico  # type: ignore[no-redef]
    import level5 as L  # type: ignore[no-redef]
    import lieux as LX  # type: ignore[no-redef]
    from lieux import Lieu  # type: ignore[no-redef]

ARCHIVE = "yw2_a.fa"
DOSSIER_CARTES = "data/res/map/"
SUFFIXE_SET = "_npc_set_0.01b.cfg.bin"          # (chemins assemblés : aucune chaîne de code.bin recopiée)
SUFFIXE_TALK = "_npc_talk_0.03d.cfg.bin"
NOM_PCK = "npc.pck"
EXT_POSITION = ".npcbin"
CARTE_MODELE = "t103i69"                         # Suite de l'Auberge des voyageurs
PNJ_MODELE = zlib.crc32(b"npc_sasurai") & 0xFFFFFFFF      # 0x95C2369D
POSITION_MODELE = "sasurai"
CHARA_PARAM = "data/res/" + "character/" + "chara_param" + "_0.03a" + ".cfg.bin"
COMMON_ENC = "data/res/" + "battle/" + "common_enc" + "_0.03a" + ".cfg.bin"
RENCONTRE = 0x713FE778                           # combat lancé par ev98_0100 (modèle du PNJ ≠ y007000)
COMBATTANT_ORIGINE = 0xDB1CC069                  # Pandanoko

BUCHINYAN = LX.BUCHINYAN
NOM_POSITION = LX.PREFIXE_NOM + "00"
TYPE_FIN_COMBAT = 77                             # déclencheur « fin du combat <rencontre> » (FUN_005A65C4)
# Condition compilée « GetGlobalBitFlag(h) == 1 » (forme de toutes les conditions de ce type des `npc_set`) :
# longueur, nombre de jetons, appel (crc32 du nom de la fonction, 1 argument « hachage »), entier 1, « == ».
_COND_BIT = (bytes.fromhex("0000000018 05 35") + struct.pack(">I", zlib.crc32(b"GetGlobalBitFlag")) +
             bytes.fromhex("000a 01 28 0006 02 34"), bytes.fromhex("32 00000001 78"))


ESSAI = Lieu()


def lire_lieu(texte: str, lieu: Lieu | None = None) -> Lieu:
    """« carte:x,z » (hauteur à déduire), « carte:x,y,z » ou « carte:x,y,z,angle » -> Lieu (les autres champs
    viennent de `lieu`, sinon de l'essai par défaut)."""
    lieu = lieu or Lieu()
    carte, x, y, z, angle = LX.lire_position(texte)
    return Lieu(carte, x, y, z, angle or 0.0, lieu.espece, lieu.condition, lieu.nom, lieu.combat, lieu.reste,
                lieu.note)


def liste_lieux(lieux) -> list[Lieu]:
    """None (essai par défaut), un `Lieu` ou une liste -> liste contrôlée (un invité par carte, noms distincts)."""
    if lieux is None:
        lieux = [ESSAI]
    elif isinstance(lieux, Lieu):
        lieux = [lieux]
    lieux = list(lieux)
    if not lieux:
        raise L.ErreurFormat("table des lieux vide")
    LX.verifier_table(lieux)
    return lieux


def condition_compilee(condition: str) -> str | None:
    """Chaîne de condition d'un `NPC_APPEAR` : None = sans condition, sinon base64 du code compilé."""
    if condition == "toujours":
        return None
    if condition.startswith("bit:"):
        try:
            h = int(condition[4:], 0)
        except ValueError:
            h = -1
        if 0 <= h <= 0xFFFFFFFF:
            return base64.b64encode(_COND_BIT[0] + struct.pack(">I", h) + _COND_BIT[1]).decode("ascii")
    raise L.ErreurFormat(f"condition « {condition} » : attendu « toujours » ou « bit:0x<hachage> »")


# ------------------------------------------------------------------------------------------------
# Fichiers de la carte
# ------------------------------------------------------------------------------------------------
def _une(c: t2b.Cfg, nom: str, quoi: str) -> t2b.Entree:
    es = c.par_nom(nom)
    if len(es) != 1:
        raise L.ErreurFormat(f"{quoi} : {len(es)} entrée(s) {nom}, une seule attendue")
    return es[0]


def _inserer(c: t2b.Cfg, nom: str, e: t2b.Entree, quoi: str) -> int:
    """Ajoute `e` à la fin du bloc `nom` (juste avant `nom_END`), compteur de `nom_BEGIN` + 1 ; renvoie son rang
    dans le bloc. Le compteur doit être égal au nombre d'entrées du bloc (sinon : fichier non compris, refus)."""
    debut, fin = _une(c, nom + "_BEGIN", quoi), _une(c, nom + "_END", quoi)
    i0, i1 = c.entrees.index(debut), c.entrees.index(fin)
    bloc = c.entrees[i0 + 1:i1]
    if i1 < i0 or len(debut.mots) != 1 or debut.mots[0] != len(bloc) or any(x.cle != e.cle for x in bloc):
        raise L.ErreurFormat(f"{quoi} : bloc {nom} inattendu")
    if bloc and len(bloc[0].mots) != len(e.mots):
        raise L.ErreurFormat(f"{quoi} : {nom} a {len(bloc[0].mots)} champs, {len(e.mots)} dans le modèle")
    c.entrees.insert(i1, e)
    debut.mots[0] += 1
    return len(bloc)


def ajouter_pnj(npc_set: bytes, npc_talk: bytes, modele_set: bytes, modele_talk: bytes, base: int, nom: str,
                condition: str | None, ident: int = PNJ_MODELE) -> tuple[bytes, bytes, dict]:
    """Ajoute au `npc_set` et au `npc_talk` d'une carte le PNJ `ident`, copié de celui des fichiers modèles (la
    Suite), avec la base `base`, le fichier de position `nom` et la condition donnée. Renvoie (npc_set, npc_talk,
    {rangs des entrées ajoutées}). ErreurFormat si la carte a déjà ce PNJ ou si un fichier n'a pas la forme
    attendue."""
    cs, ct = t2b.Cfg(npc_set), t2b.Cfg(npc_talk)
    ms, mt = t2b.Cfg(modele_set), t2b.Cfg(modele_talk)
    for c, noms in ((cs, ("NPC_BASE", "NPC_PRESET")), (ct, ("TALK_INFO",))):
        for n in noms:
            if any(e.mots and e.mots[0] == ident for e in c.par_nom(n)):
                raise L.ErreurFormat(f"la carte a déjà un PNJ 0x{ident:08X} ({n})")

    def modele(c, n):
        es = [e for e in c.par_nom(n) if e.mots and e.mots[0] == ident]
        if len(es) != 1:
            raise L.ErreurFormat(f"modèle : {n} du PNJ 0x{ident:08X} introuvable")
        return es[0].copie()
    # NPC_BASE : (identifiant, 0, base, 0, type, …)
    b = modele(ms, "NPC_BASE")
    if len(b.mots) < 5 or any(t != t2b.ENTIER for t in b.types):
        raise L.ErreurFormat("modèle : NPC_BASE inattendu")
    b.mots[2] = base
    rang_base = _inserer(cs, "NPC_BASE", b, "npc_set")
    # NPC_APPEAR : (fichier de position, -1, -1, condition, -1, 0[, -1])
    ma = ms.par_nom("NPC_APPEAR")
    mp = modele(ms, "NPC_PRESET")
    if len(mp.mots) != 3 or mp.mots[2] != 1 or mp.mots[1] >= len(ma) or len(ma[mp.mots[1]].mots) != 6:
        raise L.ErreurFormat("modèle : NPC_PRESET / NPC_APPEAR inattendus")
    a = ma[mp.mots[1]]
    existants = cs.par_nom("NPC_APPEAR")
    champs = len(existants[0].mots) if existants else 6
    if champs not in (6, 7):
        raise L.ErreurFormat(f"npc_set : NPC_APPEAR à {champs} champs")
    valeurs: list = [nom, a.mots[1], a.mots[2], condition if condition is not None else 0, a.mots[4], a.mots[5]]
    if champs == 7:
        valeurs.append(0xFFFFFFFF)       # 7e champ : -1 pour 456 des 457 entrées de t101g00
    rang_appear = _inserer(cs, "NPC_APPEAR", cs.entree("NPC_APPEAR", valeurs), "npc_set")
    mp.mots[1] = rang_appear
    _inserer(cs, "NPC_PRESET", mp, "npc_set")
    # TALK_INFO (identifiant, premier TALK_CONFIG, nombre) ; TALK_CONFIG copié
    ti = modele(mt, "TALK_INFO")
    mc = mt.par_nom("TALK_CONFIG")
    if len(ti.mots) != 3 or ti.mots[2] != 1 or ti.mots[1] >= len(mc):
        raise L.ErreurFormat("modèle : TALK_INFO inattendu")
    tc = mc[ti.mots[1]].copie()
    if any(t != t2b.ENTIER for t in tc.types):
        raise L.ErreurFormat("modèle : TALK_CONFIG avec des chaînes")
    rang_config = _inserer(ct, "TALK_CONFIG", tc, "npc_talk")
    ti.mots[1] = rang_config
    _inserer(ct, "TALK_INFO", ti, "npc_talk")
    return cs.ecrire(), ct.ecrire(), {"npc_base": rang_base, "npc_appear": rang_appear, "talk_config": rang_config}


def fichier_position(modele: bytes, x: float, y: float, z: float, angle: float) -> bytes:
    """`.npcbin` copié du modèle, avec son unique `POINT` (x, y, z, angle) remplacé."""
    c = t2b.Cfg(modele)
    p = _une(c, "POINT", "fichier de position modèle")
    pm = _une(c, "POINT_MAX", "fichier de position modèle")
    if len(p.mots) != 4 or pm.mots != [1]:
        raise L.ErreurFormat("fichier de position modèle : POINT inattendu")
    p.types = [t2b.FLOTTANT] * 4
    p.mots = [t2b.mot_flottant(v) for v in (x, y, z, angle)]
    return c.ecrire()


def declencheur_reste(trigger: bytes, rencontre: int = RENCONTRE) -> bytes:
    """Table de déclencheurs de la carte (`<carte>_trigger.cfg.bin`) avec, EN TÊTE, une entrée « fin du combat
    `rencontre` » sans script (n° de `RunCmd_Map%d` et de `RunCmdRpd_Map%d` nuls : `FUN_004484D8` ne lance rien et
    rend « traité »). Comme la table de la carte est interrogée avant la table commune, le déclencheur commun
    n° 125 (-> `ev98_0110`, adieu et effacement du PNJ) n'est pas joué sur cette carte. Sans effet si l'entrée y
    est déjà. ErreurFormat si la table n'a pas la forme attendue (`DATA_COUNT`, `DATA_ITEM` à 7 entiers ou plus)."""
    c = t2b.Cfg(trigger)
    compte = _une(c, "DATA_COUNT", "déclencheurs de la carte")
    items = c.par_nom("DATA_ITEM")
    if len(compte.mots) != 1 or compte.mots[0] != len(items) or c.entrees[0] is not compte:
        raise L.ErreurFormat("déclencheurs de la carte : DATA_COUNT inattendu")
    champs = len(items[0].mots) if items else 7
    if champs < 7 or any(len(e.mots) != champs for e in items):
        raise L.ErreurFormat("déclencheurs de la carte : DATA_ITEM inattendu")
    if any(e.mots[0] == TYPE_FIN_COMBAT and e.mots[1] == rencontre for e in items):
        if items[0].mots[:2] == [TYPE_FIN_COMBAT, rencontre] and not any(items[0].mots[2:]):
            return trigger
        raise L.ErreurFormat("déclencheurs de la carte : la carte a déjà un déclencheur de fin de ce combat")
    e = c.entree("DATA_ITEM", [TYPE_FIN_COMBAT, rencontre] + [0] * (champs - 2))
    c.entrees.insert(1, e)
    compte.mots[0] += 1
    return c.ecrire()


def nom_declencheurs(pck: "L.Xpck", carte: str) -> str:
    """Nom, dans le `.pck` de la carte, de sa table de déclencheurs de visite normale (`<carte>_trigger.cfg.bin`,
    pas `_quest_trigger` ni `_trigger_gate`)."""
    noms = [n for n, _o, _t in pck.fichiers if n == carte + "_trigger.cfg.bin"]
    if len(noms) != 1:
        raise L.ErreurFormat(f"{carte}.pck : pas de table de déclencheurs de carte ({carte}_trigger.cfg.bin) : "
                             "« reste » impossible sur cette carte")
    return noms[0]


def base_de(chara_param: bytes, espece: int) -> int:
    for e in t2b.Cfg(chara_param).par_nom("CHARA_PARAM_INFO"):
        if len(e.mots) > 1 and e.mots[0] == espece:
            return e.mots[1]
    raise L.ErreurFormat(f"espèce 0x{espece:08X} absente de chara_param")


def combattant(common_enc: bytes, espece: int, rencontre: int = RENCONTRE,
               origine: int | None = COMBATTANT_ORIGINE) -> bytes:
    """`common_enc` avec l'espèce du combattant unique de `rencontre` remplacée (fichier de même taille). Refus
    si la rencontre n'a pas exactement un combattant, s'il est partagé avec une autre rencontre, ou s'il n'est
    pas celui attendu (`origine`)."""
    c = t2b.Cfg(common_enc)
    tables = c.par_nom("ENCOUNT_TABLE")
    t = [e for e in tables if e.mots and e.mots[0] == rencontre]
    if len(t) != 1 or len(t[0].mots) < 7:
        raise L.ErreurFormat("common_enc : rencontre 0x%08X introuvable" % rencontre)
    cites = [m for m in t[0].mots[1:7] if m != 0xFFFFFFFF]
    persos = c.par_nom("ENCOUNT_CHARA")
    if len(cites) != 1 or cites[0] >= len(persos):
        raise L.ErreurFormat("common_enc : la rencontre n'a pas un combattant unique")
    k = cites[0]
    if sum(1 for e in tables for m in e.mots[1:7] if m == k) != 1:
        raise L.ErreurFormat("common_enc : combattant partagé avec une autre rencontre")
    if origine is not None and persos[k].mots[0] not in (origine, espece):
        raise L.ErreurFormat("common_enc : combattant inattendu (0x%08X)" % persos[k].mots[0])
    persos[k].mots[0] = espece
    out = c.ecrire()
    if len(out) != len(common_enc):
        raise L.ErreurFormat("common_enc : taille modifiée")
    return out


# ------------------------------------------------------------------------------------------------
# Archive
# ------------------------------------------------------------------------------------------------
@dataclass
class Resume:
    lieux: list = field(default_factory=list)
    bases: dict = field(default_factory=dict)       # nom du lieu -> base du PNJ
    taille_archive: int = 0
    ajout: int = 0                               # octets ajoutés à la fin de l'archive
    remplaces: dict = field(default_factory=dict)   # chemin -> (ancienne taille, nouvelle taille)
    ajoutes: dict = field(default_factory=dict)     # chemin -> taille
    rangs: dict = field(default_factory=dict)       # nom du lieu -> rangs des entrées ajoutées
    hauteurs: dict = field(default_factory=dict)    # nom du lieu -> lieux.Hauteur (y déduit seulement)
    icone: bool = False
    marge_tete: int = 0                          # octets encore libres dans les tables de tête (avant l'icône)
    combattant: int | None = None                # espèce écrite dans la rencontre commune
    contenus: dict = field(default_factory=dict)    # chemin -> octets (pour le contrôle, jamais écrits)
    sur_place: dict = field(default_factory=dict)   # chemin -> octets du fichier modifié sur place

    @property
    def lieu(self) -> Lieu:
        return self.lieux[0]

    @lieu.setter
    def lieu(self, v: Lieu) -> None:
        self.lieux[0] = v

    @property
    def base(self) -> int:
        return self.bases[self.lieux[0].nom]

    def lignes(self) -> list[str]:
        out = []
        for lieu in self.lieux:
            out.append("lieu %s : %s ; base du PNJ 0x%08X" % (lieu.nom, lieu.decrire(), self.bases[lieu.nom]))
            h = self.hauteurs.get(lieu.nom)
            if h is not None:
                out.append("  hauteur déduite : y = %g (%d point(s) voisin(s), le plus proche à %.0f unités, écart %g)"
                           % (h.y, len(h.voisins), h.voisins[0][0], h.ecart))
        out.append("archive %s : %d octets -> %d (+%d)" % (ARCHIVE, self.taille_archive,
                                                          self.taille_archive + self.ajout, self.ajout))
        out += ["remplacé : %s (%d -> %d octets)" % (n, a, b) for n, (a, b) in sorted(self.remplaces.items())]
        out += ["ajouté : %s (%d octets)" % (n, t) for n, t in sorted(self.ajoutes.items())]
        out += ["modifié sur place : %s" % n for n in sorted(self.sur_place)]
        out.append("tables de tête : %d octets encore libres" % self.marge_tete)
        if self.icone:
            out.append("fusionné avec la grande image de la vitrine (icône)")
        return out


def marge_tete(tete: bytes) -> int:
    """Octets nuls à la fin des tables de tête (place encore libre avant le début des données)."""
    return len(tete) - len(tete.rstrip(b"\0"))


def modifications(source: L.SourceRomfs, lieux=None, grande_icone: bool = False,
                  verifier_sha1: bool = True, supplement=None) -> tuple[list, list[str], Resume]:
    """Remplacements à faire dans `yw2_a.fa` pour l'essai : `ico.Modification` (position, octets) ; celui dont la
    position est la taille de l'archive est à AJOUTER à la fin. `lieux` : un `Lieu`, une liste (table), ou None
    (essai par défaut). `grande_icone` : la grande image de la vitrine (icone.py) est ajoutée à la même tête (ne pas
    la demander en plus à `icone.modifications`).
    `supplement` : (remplacements, ajouts) d'un AUTRE module pour la même archive (`invitations.fichiers_a`), faits
    dans le même calcul de la tête (un seul patch par archive).
    ErreurFormat si l'archive n'est pas celle d'origine, si un fichier n'a pas la forme attendue ou si la table est
    invalide (deux invités sur une carte, hauteur indéductible) : rien n'est alors à installer pour l'essai."""
    try:
        return _modifications(source, liste_lieux(lieux), grande_icone, verifier_sha1, supplement)
    except (t2b.ErreurCfg, struct.error, IndexError) as e:
        raise L.ErreurFormat(f"fichier de configuration inattendu : {e}") from e


def _modifications(source, lieux, grande_icone, verifier_sha1, supplement=None):
    modele = DOSSIER_CARTES + CARTE_MODELE + "/"
    for lieu in lieux:
        condition_compilee(lieu.condition)
    f, base_f, taille = source.ouvrir(ARCHIVE)
    avert: list[str] = []
    with f:
        arc = L.Arc0(f, base_f)
        f.seek(base_f)
        tete = f.read(arc.off_donnees)
        if verifier_sha1 and hashlib.sha1(tete).hexdigest() != ico.SHA1_TETE_A:
            raise L.ErreurFormat("tête de l'archive différente de l'original attendu (autre version du jeu ou "
                                 "autre mod)")
        res = Resume(list(lieux), taille_archive=taille)
        chara_param = arc.lire(CHARA_PARAM)
        modele_set, modele_talk = arc.lire(modele + CARTE_MODELE + SUFFIXE_SET), \
            arc.lire(modele + CARTE_MODELE + SUFFIXE_TALK)
        modele_pos = arc.lire(modele + POSITION_MODELE + EXT_POSITION)
        remplacements: dict[str, bytes] = {}
        ajouts: dict[str, bytes] = {}
        points: dict = {}
        for lieu in lieux:
            dossier = DOSSIER_CARTES + lieu.carte + "/"
            ch_set, ch_talk = dossier + lieu.carte + SUFFIXE_SET, dossier + lieu.carte + SUFFIXE_TALK
            ch_pck, ch_pos = dossier + NOM_PCK, dossier + lieu.nom + EXT_POSITION
            if ch_set not in arc.entrees:
                raise L.ErreurFormat(f"carte {lieu.carte} inconnue ({ch_set} absent de l'archive)")
            if ch_pos in arc.entrees:
                raise L.ErreurFormat(f"{ch_pos} existe déjà")
            h = LX.resoudre_hauteur(arc, lieu, points)
            if h is not None:
                res.hauteurs[lieu.nom] = h
                if h.avertissement:
                    avert.append("%s (%g, %g) : %s" % (lieu.carte, lieu.x, lieu.z, h.avertissement))
            res.bases[lieu.nom] = base_de(chara_param, lieu.espece)
            npc_set, npc_talk, res.rangs[lieu.nom] = ajouter_pnj(
                arc.lire(ch_set), arc.lire(ch_talk), modele_set, modele_talk, res.bases[lieu.nom], lieu.nom,
                condition_compilee(lieu.condition))
            position = fichier_position(modele_pos, lieu.x, lieu.y, lieu.z, lieu.angle)
            remplacements[ch_set], remplacements[ch_talk] = npc_set, npc_talk
            remplacements[ch_pck] = L.Xpck(arc.lire(ch_pck)).reconstruire({}, {lieu.nom + EXT_POSITION: position})
            ajouts[ch_pos] = position
            if lieu.reste:
                ch_carte = dossier + lieu.carte + ".pck"
                pck = L.Xpck(arc.lire(ch_carte))
                nom_t = nom_declencheurs(pck, lieu.carte)
                remplacements[ch_carte] = pck.reconstruire({nom_t: declencheur_reste(pck.lire(nom_t))})
        mods = []
        avec_combat = [lieu for lieu in lieux if lieu.combat]
        if avec_combat:
            res.combattant = avec_combat[0].espece
            off, _t = arc.entrees[COMMON_ENC]
            ancien = arc.lire(COMMON_ENC)
            nouveau = combattant(ancien, res.combattant)
            res.sur_place[COMMON_ENC] = nouveau
            mods += [ico.Modification(ARCHIVE, off + p, o, ARCHIVE, res)
                     for p, o in ico.spans_differents(ancien, nouveau, ecart=0)]
            autres = sorted({lieu.espece for lieu in avec_combat} - {res.combattant})
            if autres:
                avert.append("le combat de tous les lieux est celui de l'espèce 0x%08X (premier lieu) : le combattant "
                             "selon la carte est à brancher côté natif" % res.combattant)
        for n, d in remplacements.items():
            res.remplaces[n] = (arc.entrees[n][1], len(d))
        if supplement is not None:
            for a_faire, d in ((remplacements, supplement[0]), (ajouts, supplement[1])):
                if set(a_faire) & set(d):
                    raise L.ErreurFormat("un même fichier est modifié par deux modules")
                a_faire.update(d)
        nouvelle, suffixe = L.arc0_modifier(tete, taille, remplacements, ajouts)
    res.ajoutes = {n: len(d) for n, d in ajouts.items()}
    res.contenus = {**remplacements, **ajouts}
    res.ajout = len(suffixe)
    res.marge_tete = marge_tete(nouvelle)
    if grande_icone:
        m, a = ico.modifications_grande(source, sha1_tete=ico.SHA1_TETE_A if verifier_sha1 else None,
                                        tete_depart=nouvelle)
        if m:
            mods += m                    # écarts entre la tête d'origine et la tête finale (les deux modules)
            res.icone = True
        else:
            avert += a
    if not res.icone:
        mods += [ico.Modification(ARCHIVE, p, o, ARCHIVE, res) for p, o in ico.spans_differents(tete, nouvelle)]
    mods.append(ico.Modification(ARCHIVE, taille, suffixe, ARCHIVE, res))
    return mods, avert, res


def separer_ajout(mods: list, taille: int) -> tuple[list[tuple[int, bytes]], bytes]:
    """[(position, octets)] sur place et octets à ajouter à la fin (positions >= taille, qui doivent se suivre)."""
    sur_place = [(m.position, m.octets) for m in mods if m.position < taille]
    ajout, fin = b"", taille
    for m in sorted((m for m in mods if m.position >= taille), key=lambda m: m.position):
        if m.position != fin:
            raise L.ErreurFormat("ajouts de fin d'archive non contigus")
        ajout += m.octets
        fin += len(m.octets)
    return sur_place, ajout


def patch(source: L.SourceRomfs, mods: list) -> bytes:
    f, base, taille = source.ouvrir(ARCHIVE)
    with f:
        sur_place, ajout = separer_ajout(mods, taille)
        return _bps.bps_sur_place(f, base, taille, sur_place, ajout)


def _relire_lieu(avant: "L.Arc0", apres: "L.Arc0", lieu: Lieu, base: int) -> str:
    """Relecture « métier » d'un lieu dans l'archive patchée ; renvoie la ligne du compte rendu."""
    dossier = DOSSIER_CARTES + lieu.carte + "/"
    cs = t2b.Cfg(apres.lire(dossier + lieu.carte + SUFFIXE_SET))
    ct = t2b.Cfg(apres.lire(dossier + lieu.carte + SUFFIXE_TALK))
    for c, blocs in ((cs, ("NPC_BASE", "NPC_PRESET", "NPC_APPEAR")),
                     (ct, ("TALK_INFO", "TALK_CONFIG", "TALK_SELECT", "TALK_PAGE"))):
        for b in blocs:
            if _une(c, b + "_BEGIN", "relecture").mots[0] != len(c.par_nom(b)):
                raise L.ErreurFormat(f"relecture : compteur de {b} faux ({lieu.carte})")
    pre = [e for e in cs.par_nom("NPC_PRESET") if e.mots[0] == PNJ_MODELE]
    bas = [e for e in cs.par_nom("NPC_BASE") if e.mots[0] == PNJ_MODELE]
    inf = [e for e in ct.par_nom("TALK_INFO") if e.mots[0] == PNJ_MODELE]
    if len(pre) != 1 or len(bas) != 1 or len(inf) != 1 or bas[0].mots[2] != base:
        raise L.ErreurFormat(f"relecture : PNJ ajouté introuvable ({lieu.carte})")
    ap = cs.par_nom("NPC_APPEAR")[pre[0].mots[1]]
    va = cs.valeurs(ap)
    if pre[0].mots[2] != 1 or va[0] != lieu.nom or \
            (va[3] if ap.types[3] == t2b.CHAINE else None) != condition_compilee(lieu.condition):
        raise L.ErreurFormat(f"relecture : NPC_APPEAR ajouté inattendu ({lieu.carte})")
    if inf[0].mots[1] >= len(ct.par_nom("TALK_CONFIG")):
        raise L.ErreurFormat(f"relecture : TALK_INFO hors de TALK_CONFIG ({lieu.carte})")
    libre = apres.lire(dossier + lieu.nom + EXT_POSITION)
    pck_avant, pck = L.Xpck(avant.lire(dossier + NOM_PCK)), L.Xpck(apres.lire(dossier + NOM_PCK))
    if pck.lire(lieu.nom + EXT_POSITION) != libre or pck.nb != pck_avant.nb + 1:
        raise L.ErreurFormat(f"relecture : fichier de position absent de npc.pck ({lieu.carte})")
    for n, _o, _t in pck_avant.fichiers:
        if pck.lire(n) != pck_avant.lire(n):
            raise L.ErreurFormat(f"relecture : npc.pck|{n} modifié ({lieu.carte})")
    crcs = [struct.unpack_from("<I", pck.data, pck.off_info + 12 * i)[0] for i in range(pck.nb)]
    if crcs != sorted(crcs):
        raise L.ErreurFormat(f"relecture : entrées de npc.pck non triées ({lieu.carte})")
    point = t2b.Cfg(libre)
    vp = point.valeurs(_une(point, "POINT", "relecture"))
    if [round(v, 3) for v in vp] != [round(v, 3) for v in (lieu.x, lieu.y, lieu.z, lieu.angle)]:
        raise L.ErreurFormat(f"relecture : POINT inattendu ({lieu.carte})")
    reste = ""
    ch_carte = dossier + lieu.carte + ".pck"
    if lieu.reste:
        ca, cp = L.Xpck(avant.lire(ch_carte)), L.Xpck(apres.lire(ch_carte))
        nom_t = nom_declencheurs(ca, lieu.carte)
        ta, tp = t2b.Cfg(ca.lire(nom_t)), t2b.Cfg(cp.lire(nom_t))
        ia, ip = ta.par_nom("DATA_ITEM"), tp.par_nom("DATA_ITEM")
        if len(ip) != len(ia) + 1 or tp.par_nom("DATA_COUNT")[0].mots != [len(ip)] or \
                ip[0].mots[:2] != [TYPE_FIN_COMBAT, RENCONTRE] or any(ip[0].mots[2:]) or \
                [e.mots for e in ip[1:]] != [e.mots for e in ia] or [e.types for e in ip[1:]] != [e.types for e in ia]:
            raise L.ErreurFormat(f"relecture : déclencheur « reste » inattendu ({lieu.carte})")
        for n, _o, _t in ca.fichiers:
            if n != nom_t and cp.lire(n) != ca.lire(n):
                raise L.ErreurFormat(f"relecture : {lieu.carte}.pck|{n} modifié")
        reste = " ; reste après le combat (%d déclencheurs de carte, le nôtre en tête)" % len(ip)
    elif apres.entrees.get(ch_carte) != avant.entrees.get(ch_carte):
        raise L.ErreurFormat(f"relecture : {lieu.carte}.pck modifié sans « reste »")
    return ("%s : %d NPC_BASE, %d NPC_APPEAR, %d TALK_CONFIG ; npc.pck %d fichiers (les %d d'origine identiques) ; "
            "position (%g, %g, %g, %g)%s"
            % ((lieu.carte, len(cs.par_nom("NPC_BASE")), len(cs.par_nom("NPC_APPEAR")),
                len(ct.par_nom("TALK_CONFIG")), pck.nb, pck_avant.nb) + tuple(vp) + (reste,)))


def verifier(source: L.SourceRomfs, p: bytes, res: Resume, dossier_tmp: str | Path | None = None) -> list[str]:
    """Applique le patch à l'archive du joueur (dans un fichier temporaire, supprimé ensuite) et contrôle le
    résultat : taille, relecture de CHAQUE fichier d'origine au même endroit (recherche faite comme le jeu), contenu
    des fichiers remplacés, ajoutés et modifiés sur place, relecture des tables et du fichier de position de chaque
    lieu. Renvoie les lignes du compte rendu ; ErreurFormat au premier écart."""
    f, base, taille = source.ouvrir(ARCHIVE)
    out = []
    with f, tempfile.TemporaryFile(dir=dossier_tmp) as cible:
        avant = L.Arc0(f, base)
        nt = _bps.bps_appliquer_flux(f, base, taille, p, cible)
        if nt != taille + res.ajout:
            raise L.ErreurFormat("taille de l'archive patchée inattendue")
        out.append("patch appliqué : %d -> %d octets (CRC source et cible justes)" % (taille, nt))
        apres = L.Arc0(cible, 0)
        cible.seek(0)
        tete = cible.read(apres.off_donnees)
        tables = L.arc0_tables(tete)
        attendus = len(avant.entrees) + len(res.ajoutes) + (1 if res.icone else 0)
        if len(apres.entrees) != attendus:
            raise L.ErreurFormat("nombre de fichiers inattendu (%d, %d attendus)" % (len(apres.entrees), attendus))
        memes = 0
        for nom, (off, t) in avant.entrees.items():
            # (les fichiers de la racine, sans dossier, ne sont pas cherchés ainsi : tables relues seulement)
            trouve = L.arc0_recherche_jeu(tables, nom) if "/" in nom else apres.entrees.get(nom)
            if trouve is None or apres.entrees.get(nom) != trouve:
                raise L.ErreurFormat(f"{nom} : introuvable par la recherche du jeu, ou tables incohérentes")
            if nom in res.remplaces:
                continue
            if trouve != (off, t):
                raise L.ErreurFormat(f"{nom} : déplacé")
            memes += 1
        out.append("%d fichiers d'origine retrouvés au même endroit par la recherche du jeu" % memes)
        for nom, contenu in res.contenus.items():
            trouve = L.arc0_recherche_jeu(tables, nom)
            if trouve is None or trouve[1] != len(contenu) or trouve[0] < taille or apres.lire(nom) != contenu:
                raise L.ErreurFormat(f"{nom} : contenu ou position inattendus après le patch")
        out.append("%d fichiers remplacés ou ajoutés relus à la fin de l'archive, contenu attendu"
                   % len(res.contenus))
        for nom, contenu in res.sur_place.items():
            if apres.lire(nom) != contenu:
                raise L.ErreurFormat(f"{nom} : contenu inattendu après le patch")
        for lieu in res.lieux:
            out.append(_relire_lieu(avant, apres, lieu, res.bases[lieu.nom]))
        if res.combattant is not None:
            ce = t2b.Cfg(apres.lire(COMMON_ENC))
            t = [e for e in ce.par_nom("ENCOUNT_TABLE") if e.mots[0] == RENCONTRE][0]
            if ce.par_nom("ENCOUNT_CHARA")[t.mots[1]].mots[0] != res.combattant:
                raise L.ErreurFormat("relecture : combattant inattendu")
            out.append("common_enc : combattant de 0x%08X = 0x%08X" % (RENCONTRE, res.combattant))
        if res.icone:
            nom = ico.DOSSIER_ATLAS + ico.NOM_GRANDE
            if L.arc0_recherche_jeu(tables, nom) is None or L.Imgc(apres.lire(nom)).largeur != ico.TAILLE_GRANDE:
                raise L.ErreurFormat("relecture : grande image de la vitrine absente")
            out.append("grande image de la vitrine présente (%s)" % nom)
        libre = marge_tete(tete)
        if res.icone:                    # la grande image est logée entre les tables et l'ancien début des données
            off, t = apres.entrees[ico.DOSSIER_ATLAS + ico.NOM_GRANDE]
            libre = avant.off_donnees - (off + t)
        out.append("tables de tête de l'archive patchée : %d octets encore libres" % libre)
    return out


def lieux_demandes(table: str | Path | None = None, lieu: str | None = None, espece: str | None = None,
                   condition: str | None = None, reste: bool = False, combat: bool = True) -> list[Lieu]:
    """Lieux d'une commande : `lieu` (« carte:x,z » ou « carte:x,y,z[,angle] », un seul lieu, avec `espece` et
    `reste`) ou, sinon, la table (`table`, défaut : `lieux_libres.txt`). `condition` : donnée à tous les lieux qui
    n'en ont pas dans la table (« toujours »). ErreurFormat si quelque chose est mal formé."""
    if lieu:
        modele = Lieu(reste=reste)
        if espece:
            try:
                modele.espece = int(espece, 0)
            except ValueError:
                raise L.ErreurFormat(f"espèce « {espece} » : hachage attendu") from None
        lieux = [lire_lieu(lieu, modele)]
    else:
        if espece or reste:
            raise L.ErreurFormat("espèce et « reste » se donnent dans la table (ou avec un lieu unique)")
        lieux = LX.charger_table(table)
    for x in lieux:
        if condition and x.condition == "toujours":
            x.condition = condition
        condition_compilee(x.condition)
        x.combat = combat
    return liste_lieux(lieux)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", type=Path, required=True, help="ROM déchiffrée ou RomFS extrait")
    ap.add_argument("--sortie", type=Path, required=True, help="dossier de sortie (hors du dépôt)")
    ap.add_argument("--table", type=Path, help="table des lieux (défaut : %s)" % LX.FICHIER_TABLE.name)
    ap.add_argument("--lieu", help="un seul lieu au lieu de la table : carte:x,z (hauteur déduite) ou "
                                   "carte:x,y,z[,angle]")
    ap.add_argument("--espece", help="avec --lieu : CHARA_PARAM de l'espèce (défaut : Buchinyan)")
    ap.add_argument("--reste", action="store_true", help="avec --lieu : le Yo-kai reste après le combat")
    ap.add_argument("--condition", help="toujours | bit:0x<hachage d'un flag global> (lieux sans condition)")
    ap.add_argument("--sans-combat", action="store_true", help="ne pas toucher au combattant de la rencontre")
    ap.add_argument("--icone", action="store_true", help="fusionner avec la grande image de la vitrine")
    ap.add_argument("--verifier", action="store_true", help="appliquer le patch et contrôler l'archive obtenue")
    a = ap.parse_args(argv)
    try:
        lieux = lieux_demandes(a.table, a.lieu, a.espece, a.condition, a.reste, not a.sans_combat)
        src = L.SourceRomfs(a.romfs)
        mods, avert, res = modifications(src, lieux, grande_icone=a.icone)
        p = patch(src, mods)
        for ligne in res.lignes():
            print(ligne)
        for w in avert:
            print("attention :", w)
        if a.verifier:
            for ligne in verifier(src, p, res):
                print("contrôle :", ligne)
    except (L.ErreurFormat, t2b.ErreurCfg, _bps.ErreurBps, OSError) as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    d = a.sortie / "romfs_ext"
    d.mkdir(parents=True, exist_ok=True)
    (d / (ARCHIVE + ".bps")).write_bytes(p)
    print("écrit : %s (%d octets)" % (d / (ARCHIVE + ".bps"), len(p)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
