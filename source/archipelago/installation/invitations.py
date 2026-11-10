"""Objets du jeu « Invitation : <nom du Yo-kai> » (bibliothèque standard seulement).

    python archipelago/installation/invitations.py --romfs <RomFS extrait | ROM déchiffrée> [--apercu <dossier hors git>]
           [--sortie <dossier du titre>]

Les 33 objets Archipelago « Invitation : <nom> » (les 30 invités de l'Auberge des voyageurs, `docs/systemes/
archipelago_invites.md` §15, et Jibanyan S, Komasan S, Komajiro S, invités à leur emplacement d'origine,
`archipelago_evenement_invitation.md` §9) deviennent de VRAIS objets importants du jeu, visibles dans l'inventaire
(§16 du premier document). Rien du jeu n'est distribué : tout est écrit CHEZ LE JOUEUR, à l'installation, dans des
patchs BPS (`romfs_ext/<archive>.bps`) calculés depuis son propre RomFS.

Ce qui est ajouté :
1. `yw2_a.fa`, configuration des objets : 33 entrées « objet important » (copie de l'entrée de l'objet vitrine
   0xA0531A08, « Important Item 20 », jamais donné par le jeu : type 60, un exemplaire, ni prix ni effet), de
   hachage `crc32("ap_" + clé)` (clé de `objets.json` : identifiant à nous, absent du jeu), et 33 entrées d'index ;
   les compteurs des deux sections sont augmentés. Le jeu alloue ses tableaux d'après ces compteurs [C :
   0x004DEE34, 0x004DEC14] et cherche un objet par son hachage dans l'index [C : 0x00644C08].
2. Archives de langue (`yw2_lg_<LG>.fa`), textes des objets : 33 noms (« Invitation : <nom> » en français,
   « Invitation: <name> » pour les autres langues : repli sur l'anglais) et deux descriptions (celle des invités de
   l'Auberge ; celle des trois invités à leur emplacement d'origine, qui ne sont pas à l'Auberge). Le jeu trie
   lui-même la table des noms au chargement [C : 0x004E6590].
3. Icône commune : une enveloppe DESSINÉE ICI en code (`dessiner`), dans la case libre (14, 31) de l'atlas d'icônes
   (famille de cases factices sans tuile commune avec la vitrine) et sa grande image 64×64 `item_511` (ajoutée).

V3 (`archipelago_invites.md` §16.10) : le module ajoute AUSSI, après les 33 invitations, les trois objets de voyage
« Abonnement de train », « Voyage dans le temps », « Miroirs » (`objets_voyage.py` : case d'atlas réaffectée, icône
et grande image dessinées, description propre ; `objets_installes()`). 36 objets : le sac des objets importants est
alors plein au pire cas (180 / 180). Puis (§16.11) le « Mirapo de poche » et les 31 versions du « Trousseau du
donjon » (une par ensemble de clés : le jeu n'en tient qu'une, et le Mirapo remplace les Miroirs) : 68 objets, 179
emplacements au pire cas une fois comptés deux objets du jeu jamais donnés (`JAMAIS_DONNES`). Puis (§16.13) les 3
paliers du « Multiplicateur d'XP » (x2, x3, x4 : un seul tenu, le jeu échange) : 71 objets, 180 / 180 emplacements
(marge nulle : plus rien ne peut être ajouté à ce sous-inventaire sans en retirer).

TOUT OU RIEN : la configuration n'est modifiée que si les textes de TOUTES les archives de langue présentes le sont
aussi (un objet défini sans nom dans une langue aurait un nom nul). L'installateur (`installer.preparer_romfs`)
retire tout le module si une seule de ses archives ne peut pas être patchée.

(Les 16 invitations des Yo-kai de Pièce 5 étoiles, objets ORDINAIRES du sac du lot 14 de la V3, sont retirées par
le lot 20 : ces Yo-kai viennent par des Pièces 5 étoiles, objets du jeu d'origine ; ce module ne crée plus que
des objets importants.)

Sans ces patchs (ROM non modifiable, autre mod sur une archive, désinstallation), les objets n'existent pas : le jeu
ignore le don (`AP_ERR_OBJET_INCONNU`, compteur avancé) et l'invité vient quand même (déclenché par l'objet AP reçu,
jamais par l'inventaire). Une sauvegarde qui contient ces objets reste chargeable par un jeu qui ne les connaît pas
(entrées gardées telles quelles, jamais listées : §16.3).
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import bps as _bps, icone as ico, level5 as L, objets_voyage as OV, t2b
except ImportError:                     # lancé comme script
    import bps as _bps  # type: ignore[no-redef]
    import icone as ico  # type: ignore[no-redef]
    import level5 as L  # type: ignore[no-redef]
    import objets_voyage as OV  # type: ignore[no-redef]
    import t2b  # type: ignore[no-redef]

ARCHIVE = "yw2_a.fa"
LANGUES = ("fr", "engb", "de", "es", "it", "nl", "ru")
# (chemins assemblés : le paquet ne recopie aucune chaîne de code.bin)
CONFIG = "data/res/" + "item/" + "item_config" + "_0.04b" + ".cfg.bin"
DOSSIER_TEXTE = "data/res/" + "text/"
OBJETS = Path(__file__).resolve().parents[1] / "apworld" / "yokaiwatch2" / "donnees" / "objets.json"

MODELE = ico.VITRINE                     # entrée copiée : « Important Item 20 », jamais donné par le jeu
COLONNE, LIGNE = 14, 31                  # case libre de l'atlas (aucun objet), n° 510
ID_GRANDE = LIGNE * 16 + COLONNE + 1     # 511 : grande image `item_511` (absente du jeu)
NOM_GRANDE = "item_%03d.xi" % ID_GRANDE
# Cases factices (ronds numérotés sans objet, ou objets jamais donnés 504 / 506 / 508 = « Important Item » 21 / 23 /
# 25) qui partagent des tuiles avec la case 510 ; aucune tuile commune avec la vitrine (503) [C, relevé sur les 4
# atlas de la ROM d'origine]
CASES_FACTICES = frozenset({111, 112, 152, 195, 197, 205, 216, 239, 263, 265, 284, 295, 297, 301,
                            504, 506, 508, 510})
PREFIXE_HACHAGE = "ap_"                  # hachage de l'objet = crc32("ap_" + clé)
PREFIXE_AFFICHAGE = "affiche_"           # définition d'affichage (§21) : crc32("ap_affiche_" + clé de l'objet AP)
NUMERO_BASE = 3001                       # champ « numéro » des entrées (affichage / identité, valeurs libres)
DESCRIPTIONS = {
    "fr": "Une invitation pour un Yo-kai.\\nRetrouve-le à l'Auberge des voyageurs",
    "en": "An invitation for a Yo-kai guest.\\nGo and meet them at the inn!",
}
# Invitations des Yo-kai d'évènement à leur EMPLACEMENT D'ORIGINE (clés de `objets.json` : identifiants à nous) : le
# Yo-kai n'est pas à l'Auberge mais à sa place du jeu d'origine (Hauts de Granval, Centre-ville de Granval) : seconde
# description (saisie à la main).
CLES_LIEU_ORIGINE = frozenset({"invitation_jibanyan_s", "invitation_komasan_s", "invitation_komajiro_s"})
DESCRIPTIONS_LIEU = {
    "fr": "Une invitation pour un Yo-kai.\\nIl t'attend quelque part à Granval",
    "en": "An invitation for a Yo-kai guest.\\nLook for them around Springdale!",
}
# Capacité du sous-inventaire des objets importants du jeu (emplacements) [C : archipelago_invites.md §16.2] et objets
# importants du jeu qui ne peuvent JAMAIS être tenus en même temps que les autres [S, compte des définitions] : 6
# objets factices (« Important Item 20 » à 25, dont la vitrine) et 12 doublons garçon / fille (deux montres de
# départ, deux montres de quête, deux vélos de départ et neuf vélos de boutique : un seul des deux jeux par partie).
# 162 - 18 = 144 objets importants au plus dans une sauvegarde ; + 33 invitations = 177 <= 180 (marge de 3).
# ap/objets-mirapo-trousseau (§16.11) : + 2 objets JAMAIS DONNÉS (`JAMAIS_DONNES`, ni par le jeu ni par le mod [C :
# aucun script, seq ET .pck, aucune entrée de .cfg.bin, aucun mot de code.bin, archipelago_v3_inventaire_objets_cles.md
# §5 ; aucune table du mod, test_objets_mirapo_trousseau]) : 162 - 20 = 142 ; + 33 invitations + 4 emplacements
# d'objets de voyage (train, voyage dans le temps, Miroirs OU Mirapo de poche, UNE version du trousseau) = 179 <= 180.
# ap/multiplicateur-xp-objet (§16.13) : + 1 emplacement (UN palier du Multiplicateur d'XP) = 180 <= 180, marge nulle.
CAPACITE_IMPORTANTS = 180
JAMAIS_DONNES = (0xA60825A2, 0x6A9D5B66)    # Ticket de musée (iky0007), Fiole de ramolline (iky0039)
IMPORTANTS_JAMAIS_ENSEMBLE = 18 + len(JAMAIS_DONNES)
# Index des champs d'une entrée d'objet important (18 valeurs entières) [C : gestionnaire 0x004DE9C0 / 0x004DDF80]
V_HACHAGE, V_NOM, V_TYPE, V_NUMERO, V_TRI, V_MAX, V_COLONNE, V_LIGNE, V_DESCRIPTION, V_NOM2 = \
    0, 1, 2, 4, 5, 6, 12, 13, 14, 17
NB_CHAMPS = 18
TYPE_IMPORTANT = 60


class ErreurInvitations(L.ErreurFormat):
    """Fichier du jeu inattendu : rien n'est installé pour les invitations."""


def crc32(nom: str) -> int:
    return zlib.crc32(nom.encode("ascii")) & 0xFFFFFFFF


@dataclass(frozen=True)
class Invitation:
    """Objet important ajouté au jeu : une invitation, ou (V3, `objets_voyage.py`) un objet de voyage, qui a alors sa
    propre case d'icône, sa propre description et son propre dessin."""
    cle: str
    nom_fr: str
    nom_en: str
    lieu: bool = False                   # Yo-kai à son emplacement d'origine (pas à l'Auberge) : seconde description
    colonne: int = COLONNE               # case de l'atlas (v12, v13) ; défaut : l'enveloppe
    ligne: int = LIGNE
    description_fr: str = ""             # description propre (objets de voyage) ; vide : celle des invitations
    description_en: str = ""
    dessin: object = field(default=None, compare=False, repr=False)   # (cote) -> pixels ; None : l'enveloppe
    groupe: str = ""                     # objets jamais ensemble dans le sac (le jeu échange) : un emplacement par groupe
    affichage: bool = False              # définition d'affichage, jamais donnée : aucun emplacement du sac (§21)

    @property
    def emplacement(self) -> str:
        """Clé d'emplacement du sac : le groupe, sinon l'objet lui-même (§16.11)."""
        return self.groupe or self.cle

    @property
    def hachage(self) -> int:
        return crc32(PREFIXE_HACHAGE + self.cle)

    @property
    def hachage_nom(self) -> int:
        return crc32(PREFIXE_HACHAGE + self.cle + "_nom")

    def nom(self, langue: str) -> str:
        return self.nom_fr if langue == "fr" else self.nom_en

    @property
    def propre(self) -> bool:
        """Objet à description, case et dessin propres (objet de voyage), pas une invitation."""
        return bool(self.description_fr)

    @property
    def hachage_description(self) -> int:
        if self.propre:
            return crc32(PREFIXE_HACHAGE + self.cle + "_description")
        return HACHAGE_DESCRIPTION_LIEU if self.lieu else HACHAGE_DESCRIPTION

    def description(self, langue: str) -> str:
        return self.description_fr if langue == "fr" else self.description_en

    @property
    def id_grande(self) -> int:
        """N° de la grande image `item_%03d` (ItemIcon_GetID : colonne + 16 × ligne + 1)."""
        return self.ligne * 16 + self.colonne + 1

    def pixels(self, cote: int) -> list:
        return dessiner(cote) if self.dessin is None else self.dessin(cote)


HACHAGE_DESCRIPTION = crc32(PREFIXE_HACHAGE + "invitation_description")
HACHAGE_DESCRIPTION_LIEU = crc32(PREFIXE_HACHAGE + "invitation_description_lieu")


def descriptions(invs: list["Invitation"], langue: str) -> list[tuple[int, str]]:
    """(hachage, texte) des descriptions dont ces invitations ont besoin, dans un ordre fixe (celle de l'Auberge
    d'abord : avec les 30 invités seuls, exactement l'entrée d'avant)."""
    lg = "fr" if langue == "fr" else "en"
    out = []
    if any(not i.lieu and not i.propre for i in invs):
        out.append((HACHAGE_DESCRIPTION, DESCRIPTIONS[lg]))
    if any(i.lieu and not i.propre for i in invs):
        out.append((HACHAGE_DESCRIPTION_LIEU, DESCRIPTIONS_LIEU[lg]))
    out += [(i.hachage_description, i.description(lg)) for i in invs if i.propre]   # objets de voyage, à la suite
    return out


def invitations(chemin: str | Path | None = None) -> list[Invitation]:
    """Les objets de la famille « invitation » de `objets.json` (noms saisis à la main, dans l'ordre du fichier : les
    30 invités de l'Auberge puis les trois Yo-kai d'évènement à leur emplacement d'origine ; l'ordre fixe le champ
    « numéro » de chaque objet), sauf ceux dont le champ `inventaire` serait faux (invitation sans objet du jeu : plus
    aucune depuis la branche `ap/checks-fusions-armees`, le champ reste lu). Capacité : `archipelago_invites.md`
    §16.9."""
    d = json.loads(Path(chemin or OBJETS).read_text(encoding="utf-8"))["objets"]
    out = [Invitation(o["cle"], o["nom_fr"], o["nom_en"], o["cle"] in CLES_LIEU_ORIGINE) for o in d
           if o.get("famille") == "invitation" and o.get("inventaire", True) is True]
    for i in out:
        if not i.cle.isascii() or any(c in s for s in (i.nom_fr, i.nom_en) for c in "<>[]\\\n\0"):
            raise ErreurInvitations(f"objets.json : invitation {i.cle!r} invalide")
    h = [i.hachage for i in out] + [i.hachage_nom for i in out] + [HACHAGE_DESCRIPTION, HACHAGE_DESCRIPTION_LIEU]
    if len(set(h)) != len(h) or 0 in h:
        raise ErreurInvitations("objets.json : hachages d'invitations en double")
    return out


def objets_voyage(chemin: str | Path | None = None) -> list[Invitation]:
    """Les trois objets de voyage de la V3 (`objets_voyage.OBJETS` : Abonnement de train, Voyage dans le temps, Miroirs),
    noms repris d'`objets.json` (saisis à la main), case, dessin et description de `objets_voyage.py`. Un objet absent
    d'`objets.json` (APWorld plus ancien) est sauté."""
    d = {o["cle"]: o for o in json.loads(Path(chemin or OBJETS).read_text(encoding="utf-8"))["objets"]}
    out = []
    for cle, col, lig, dessin, desc in OV.OBJETS:
        o = d.get(cle)
        if o is None:
            continue
        out.append(Invitation(cle, o["nom_fr"], o["nom_en"], False, col, lig, desc["fr"], desc["en"], dessin,
                              OV.GROUPES.get(cle, "")))
    # §16.11 : Mirapo de poche (si l'APWorld a les Miroirs progressifs), puis les 31 versions du Trousseau du donjon
    # (si l'APWorld a les clés du donjon des portails) ; noms saisis à la main (objets_voyage.py)
    if OV.CLE_AP_MIRAPO in d and "miroirs" in d:
        cle, fr, en, col, lig, dessin, desc = OV.MIRAPO
        out.append(Invitation(cle, fr, en, False, col, lig, desc["fr"], desc["en"], dessin, OV.GROUPES[cle]))
    if all(c in d for c in OV.CLES_AP_DONJON):
        for cle, fr, en, col, lig, dessin, desc in OV.trousseaux():
            out.append(Invitation(cle, fr, en, False, col, lig, desc["fr"], desc["en"], dessin, OV.GROUPE_TROUSSEAU))
    # §16.13 : les 3 paliers du Multiplicateur d'XP (si l'APWorld a l'objet AP), un seul emplacement (même groupe)
    if OV.CLE_AP_XP in d:
        for cle, fr, en, col, lig, dessin, desc in OV.multiplicateurs_xp():
            out.append(Invitation(cle, fr, en, False, col, lig, desc["fr"], desc["en"], dessin, OV.GROUPE_XP))
    for i in out:
        if not i.cle.isascii() or any(c in s for s in (i.nom_fr, i.nom_en, i.description_fr, i.description_en)
                                      for c in "<>[]\n\0"):
            raise ErreurInvitations(f"objet de voyage {i.cle!r} invalide")
    return out


def objets_affichage(chemin: str | Path | None = None) -> list[Invitation]:
    """Définitions d'AFFICHAGE (`archipelago_invites.md` §21), après tous les autres objets : objets AP sans définition
    à eux qui ont pourtant une image (invitations sans objet du jeu, Miroirs progressifs, clés du donjon), montrés à
    la place du logo. Jamais données, ni par le jeu ni par le client : aucun emplacement du sac. La DERNIÈRE est la sonde
    du jeu (`AP_SONDE_DEFINITIONS`) : le module étant « tout ou rien », elle prouve que toutes sont là."""
    d = json.loads(Path(chemin or OBJETS).read_text(encoding="utf-8"))["objets"]
    par_cle = {o["cle"]: o for o in d}
    out = [Invitation(PREFIXE_AFFICHAGE + o["cle"], o["nom_fr"], o["nom_en"], affichage=True) for o in d
           if o.get("famille") == "invitation" and o.get("inventaire", True) is not True]
    o = par_cle.get(OV.CLE_AP_MIRAPO)
    if o is not None and "miroirs" in par_cle:
        col, lig, dessin, desc = OV.affichage_miroirs()
        out.append(Invitation(PREFIXE_AFFICHAGE + o["cle"], o["nom_fr"], o["nom_en"], False, col, lig, desc["fr"],
                              desc["en"], dessin, affichage=True))
    if all(c in par_cle for c in OV.CLES_AP_DONJON):
        for i, cle in enumerate(OV.CLES_AP_DONJON):
            col, lig, dessin, desc = OV.affichage_cle(i)
            o = par_cle[cle]
            out.append(Invitation(PREFIXE_AFFICHAGE + cle, o["nom_fr"], o["nom_en"], False, col, lig, desc["fr"],
                                  desc["en"], dessin, affichage=True))
    return out


def objets_installes(chemin: str | Path | None = None) -> list[Invitation]:
    """Tous les objets importants que le module ajoute : les invitations d'abord (rangs, numéros et hachages
    inchangés), puis les objets de voyage (`archipelago_invites.md` §16.10), puis les définitions d'affichage (§21).
    Hachages tous distincts."""
    out = invitations(chemin) + objets_voyage(chemin) + objets_affichage(chemin)
    h = [i.hachage for i in out] + [i.hachage_nom for i in out] + sorted({i.hachage_description for i in out})
    if len(set(h)) != len(h) or 0 in h:
        raise ErreurInvitations("objets.json : hachages d'objets ajoutés en double")
    # une case d'atlas par dessin : deux objets ne partagent une case que s'ils ont le MÊME dessin (versions du
    # trousseau de même nombre de clés) ; jamais la case de l'enveloppe ni celle de la vitrine
    par_case: dict = {}
    for i in out:
        if i.propre and par_case.setdefault((i.colonne, i.ligne), i.dessin) is not i.dessin:
            raise ErreurInvitations("cases d'icônes des objets de voyage en double")
    if any(c in par_case for c in ((COLONNE, LIGNE), (ico.COLONNE, ico.LIGNE))) or \
            len({id(v) for v in par_case.values()}) != len(par_case):
        raise ErreurInvitations("cases d'icônes des objets de voyage en double")
    return out


def emplacements(invs: list[Invitation]) -> int:
    """Emplacements du sac des objets importants que ces objets peuvent prendre EN MÊME TEMPS (un par groupe)."""
    return len({i.emplacement for i in invs if not i.affichage})


def dessiner(cote: int = 32, sur: int = 4) -> list[tuple[int, int, int, int]]:
    """Enveloppe crème à rabat, contour sombre, scellée par le logo du mod (`logo_cachet`, demande de l'humain du
    2026-10-08 : à la place du cachet rouge) : `cote` × `cote` RGBA (suréchantillonnage `sur`)."""
    n = cote * sur
    contour, papier, ombre, rabat = (58, 40, 30), (250, 240, 214), (222, 204, 170), (240, 226, 192)
    x0, x1, y0, y1 = 0.09, 0.91, 0.24, 0.80                 # corps de l'enveloppe (fractions du côté)
    ep = 0.055                                               # épaisseur du contour
    cx, pointe = 0.5, 0.56                                   # pointe du rabat

    def dist_segment(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5

    def couleur(px, py):
        if not (x0 - ep <= px <= x1 + ep and y0 - ep <= py <= y1 + ep):
            return None
        if not (x0 <= px <= x1 and y0 <= py <= y1):
            return contour
        d_rabat = min(dist_segment(px, py, x0, y0, cx, pointe), dist_segment(px, py, x1, y0, cx, pointe))
        if d_rabat < ep * 0.5:
            return contour
        d_bas = min(dist_segment(px, py, x0, y1, 0.38, 0.52), dist_segment(px, py, x1, y1, 0.62, 0.52))
        if d_bas < ep * 0.3:
            return ombre
        # au-dessus des deux bords du rabat : le rabat
        t = abs(px - cx) / (x1 - cx)
        return rabat if py < pointe - (pointe - y0) * t else papier

    out = []
    for y in range(cote):
        for x in range(cote):
            r = g = b = a = 0
            for sy in range(sur):
                for sx in range(sur):
                    c = couleur((x * sur + sx + 0.5) / n, (y * sur + sy + 0.5) / n)
                    if c is not None:
                        r, g, b, a = r + c[0], g + c[1], b + c[2], a + 1
            if a:
                out.append((r // a, g // a, b // a, 255 * a // (sur * sur)))
            else:
                out.append((0, 0, 0, 0))
    return poser_logo(out, cote)


# Le logo du mod (celui de l'objet vitrine, `ressources/icone_objet_64.png`, logo de MDarkmooN : aucune image du jeu)
# sert de cachet : réduit à la moitié du côté et posé au centre de l'enveloppe.
PART_LOGO, CENTRE_LOGO_Y = 0.5, 0.53


def logo_cachet(cote: int) -> tuple[int, list]:
    """(d, pixels d × d RGBA) : le logo 64×64 réduit par moyenne de blocs (alpha prémultiplié) à d = cote / 2."""
    w, h, pix = L.lire_png(ico.GRANDE)
    d = max(1, int(cote * PART_LOGO))
    out = []
    for y in range(d):
        for x in range(d):
            xa, xb = x * w // d, max(x * w // d + 1, (x + 1) * w // d)
            ya, yb = y * h // d, max(y * h // d + 1, (y + 1) * h // d)
            r = g = b = a = 0
            for yy in range(ya, yb):
                for xx in range(xa, xb):
                    q = pix[yy * w + xx]
                    r, g, b, a = r + q[0] * q[3], g + q[1] * q[3], b + q[2] * q[3], a + q[3]
            n = (xb - xa) * (yb - ya)
            out.append((r // a, g // a, b // a, a // n) if a else (0, 0, 0, 0))
    return d, out


def poser_logo(fond: list, cote: int) -> list:
    """Le logo du mod composé par-dessus l'enveloppe (alpha « au-dessus »)."""
    d, logo = logo_cachet(cote)
    x0, y0 = (cote - d) // 2, int(cote * CENTRE_LOGO_Y) - d // 2
    out = list(fond)
    for y in range(d):
        for x in range(d):
            lr, lg, lb, la = logo[y * d + x]
            if not la:
                continue
            i = (y0 + y) * cote + x0 + x
            fr, fg, fb, fa = out[i]
            a = la + fa * (255 - la) // 255
            out[i] = tuple((c1 * la + c2 * fa * (255 - la) // 255) // a for c1, c2 in ((lr, fr), (lg, fg), (lb, fb)))                 + (a,)
    return out


def icone_32() -> list:
    """L'enveloppe 32×32, couleur des pixels transparents étendue depuis les voisins (comme `icone.charger_icone`)."""
    pix = dessiner(ico.CASE)
    rgb = {i: p[:3] for i, p in enumerate(pix) if p[3]}
    c = ico.CASE
    while len(rgb) < c * c:
        ajout = {}
        for i in range(c * c):
            if i in rgb:
                continue
            x = i % c
            v = [rgb[j] for j in (i - 1 if x else -1, i + 1 if x < c - 1 else -1, i - c, i + c)
                 if 0 <= j < c * c and j in rgb]
            if v:
                ajout[i] = tuple(sum(k[n] for k in v) // len(v) for n in range(3))
        rgb.update(ajout)
    return [rgb[i] + (pix[i][3],) for i in range(c * c)]


def case_atlas() -> tuple:
    """L'entrée `cases_en_plus` de `icone.modifier_atlas` pour l'enveloppe."""
    return (COLONNE, LIGNE, icone_32(), CASES_FACTICES)


# Cases dont les objets de voyage peuvent reprendre les tuiles (réaffectation, `icone.modifier_atlas`) : les deux
# familles de cercles numérotés sans objet (celle de la vitrine et celle de l'enveloppe) ; les tuiles de la vitrine et
# de l'enveloppe, écrites avant, ne sont jamais reprises.
CASES_REAFFECTABLES = frozenset(ico.CASES_FACTICES | CASES_FACTICES)


def cases_atlas(invs: list[Invitation] | None = None) -> tuple:
    """Les entrées `cases_en_plus` de `icone.modifier_atlas` pour ces objets : l'enveloppe (s'il y a une invitation),
    puis une case réaffectée par objet de voyage."""
    invs = objets_installes() if invs is None else invs
    out = [case_atlas()] if any(not i.propre for i in invs) else []
    vues = set()
    for i in invs:
        if i.propre and (i.colonne, i.ligne) not in vues:          # une case par dessin (§16.11 : trousseau)
            vues.add((i.colonne, i.ligne))
            out.append((i.colonne, i.ligne, OV.etendre_couleurs(i.pixels(ico.CASE), ico.CASE), CASES_REAFFECTABLES,
                        True))
    return tuple(out)


# ------------------------------------------------------------------------------------------------
# Fichiers de configuration
# ------------------------------------------------------------------------------------------------
def _section(c: t2b.Cfg, nom: str) -> tuple[t2b.Entree, int, int]:
    """(entrée <nom>_BEGIN, rang de <nom>_END, nombre d'entrées <nom>) d'une section bien formée."""
    debut = c.par_nom(nom + "_BEGIN")
    fin = [i for i, e in enumerate(c.entrees) if e.cle == t2b.crc32(nom + "_END")]
    n = len(c.par_nom(nom))
    if len(debut) != 1 or len(fin) != 1 or len(debut[0].mots) != 1 or debut[0].types != [t2b.ENTIER] \
            or debut[0].mots[0] != n:
        raise ErreurInvitations(f"section {nom} inattendue")
    i0 = c.entrees.index(debut[0])
    if any(e.cle != t2b.crc32(nom) for e in c.entrees[i0 + 1:fin[0]]) or fin[0] - i0 - 1 != n:
        raise ErreurInvitations(f"section {nom} : entrées inattendues")
    return debut[0], fin[0], n


def _ajouter(c: t2b.Cfg, nom: str, nouvelles: list[t2b.Entree]) -> None:
    debut, fin, n = _section(c, nom)
    c.entrees[fin:fin] = nouvelles
    debut.mots[0] = n + len(nouvelles)


def _absents(c: t2b.Cfg, hachages) -> None:
    pris = {e.mots[0] for e in c.entrees if e.mots}
    deja = sorted(h for h in hachages if h in pris)
    if deja:
        raise ErreurInvitations("déjà présent dans le fichier (autre mod, ou fichier déjà modifié) : "
                                + ", ".join("0x%08X" % h for h in deja))


def modifier_config(data: bytes, invs: list[Invitation]) -> bytes:
    """Configuration des objets avec les objets importants des invitations en plus (entrées et index ajoutés en fin
    de section). Refus si les objets importants du jeu et les invitations ne tiennent pas dans les emplacements du
    sous-inventaire (un don refusé faute de place bloquerait la file de dons)."""
    try:
        c = t2b.Cfg(data)
        _d, _f, n_imp = _section(c, "ITEM_IMPORTANT")
        _section(c, "ITEM_INDEX")
        _absents(c, [i.hachage for i in invs])
        modeles = [e for e in c.par_nom("ITEM_IMPORTANT") if e.mots[V_HACHAGE] == MODELE]
        if len(modeles) != 1 or len(modeles[0].mots) != NB_CHAMPS or set(modeles[0].types) != {t2b.ENTIER} \
                or modeles[0].mots[V_TYPE] != TYPE_IMPORTANT or modeles[0].mots[V_MAX] != 1:
            raise ErreurInvitations("entrée modèle (objet vitrine) absente ou inattendue")
        index = c.par_nom("ITEM_INDEX")
        if any(len(e.mots) != 3 for e in index) or \
                [e.mots[2] for e in index if e.mots[1] in (60, 61)] != list(range(n_imp)):
            raise ErreurInvitations("index des objets inattendu")
        if n_imp + len(invs) > 0x7FFF or len(index) + len(invs) > 0x7FFF:
            raise ErreurInvitations("trop d'objets")
        if n_imp - IMPORTANTS_JAMAIS_ENSEMBLE + emplacements(invs) > CAPACITE_IMPORTANTS:
            raise ErreurInvitations(f"{n_imp} objets importants dans le jeu : pas de place pour {emplacements(invs)} "
                                    f"objets Archipelago ({CAPACITE_IMPORTANTS} emplacements)")
        objets, entrees_index = [], []
        for rang, inv in enumerate(invs):
            e = modeles[0].copie()
            e.mots[V_HACHAGE] = inv.hachage
            e.mots[V_NOM] = e.mots[V_NOM2] = inv.hachage_nom
            e.mots[V_NUMERO] = NUMERO_BASE + rang
            # V_TRI : gardé du modèle (valeur déjà connue du jeu ; les invitations se suivent en fin de liste)
            e.mots[V_COLONNE], e.mots[V_LIGNE] = inv.colonne, inv.ligne
            e.mots[V_DESCRIPTION] = inv.hachage_description
            objets.append(e)
            entrees_index.append(t2b.Entree(t2b.crc32("ITEM_INDEX"), [t2b.ENTIER] * 3,
                                            [inv.hachage, TYPE_IMPORTANT, n_imp + rang]))
        _ajouter(c, "ITEM_IMPORTANT", objets)
        _ajouter(c, "ITEM_INDEX", entrees_index)
        return c.ecrire()
    except (t2b.ErreurCfg, struct.error, IndexError) as e:
        raise ErreurInvitations(f"configuration des objets inattendue : {e}") from e


def modifier_textes(data: bytes, invs: list[Invitation], langue: str) -> bytes:
    """Textes des objets d'une langue avec les noms des invitations et leurs descriptions (une ou deux) en plus."""
    try:
        c = t2b.Cfg(data)
        _section(c, "NOUN_INFO")
        _section(c, "TEXT_INFO")
        desc = descriptions(invs, langue)
        _absents(c, [i.hachage_nom for i in invs] + [h for h, _t in desc])
        # modèle : le nom de l'objet vitrine (clé = champ « nom » de son entrée de configuration, relu ici dans la
        # forme attendue : 14 valeurs, le nom dans la 4e chaîne)
        noms = [e for e in c.par_nom("NOUN_INFO")
                if len(e.mots) == 14 and e.types[2:10] == [t2b.CHAINE] * 8 and e.mots[5] != t2b.AUCUNE
                and all(m == t2b.AUCUNE for k, m in enumerate(e.mots[2:10]) if k != 3)
                and all(m == 0 for m in e.mots[1:2] + e.mots[10:])]
        textes = [e for e in c.par_nom("TEXT_INFO")
                  if len(e.mots) == 4 and e.types == [t2b.ENTIER, t2b.ENTIER, t2b.CHAINE, t2b.ENTIER]
                  and e.mots[1] == 0 and e.mots[3] == 0]
        if not noms or not textes:
            raise ErreurInvitations("aucune entrée de nom ou de description de la forme attendue")
        nouveaux = []
        for inv in invs:
            e = noms[0].copie()
            e.mots[0] = inv.hachage_nom
            e.mots[5] = c.offset_chaine(inv.nom(langue))
            nouveaux.append(e)
        ajouts = []
        for h, texte in desc:
            t = textes[0].copie()
            t.mots[0] = h
            t.mots[2] = c.offset_chaine(texte)
            ajouts.append(t)
        _ajouter(c, "NOUN_INFO", nouveaux)
        _ajouter(c, "TEXT_INFO", ajouts)
        return c.ecrire()
    except (t2b.ErreurCfg, struct.error, IndexError) as e:
        raise ErreurInvitations(f"textes des objets ({langue}) inattendus : {e}") from e


def chemin_textes(langue: str) -> str:
    return DOSSIER_TEXTE + "item_text_" + langue + ".cfg.bin"


def nom_fa(langue: str) -> str:
    return "yw2_lg_%s.fa" % langue


# ------------------------------------------------------------------------------------------------
# Modifications des archives
# ------------------------------------------------------------------------------------------------
@dataclass
class Resume:
    invitations: int = 0
    langues: tuple = ()
    config: tuple = (0, 0)               # tailles avant / après
    textes: dict = None                  # langue -> (avant, après)
    contenus: dict = None                # archive -> {chemin: nouveau contenu} (contrôles, jamais écrit dans git)
    grande: list = None                  # pixels de la grande image telle que le jeu la décodera (l'enveloppe)
    grandes: dict = None                 # n° de grande image -> pixels décodés (enveloppe et objets de voyage)

    def lignes(self) -> list[str]:
        noms = ", ".join("item_%03d.xi" % n for n in sorted(self.grandes or {})) or NOM_GRANDE
        out = [f"{self.invitations} objets ajoutés (invitations et objets de voyage) : configuration {self.config[0]} "
               f"-> {self.config[1]} o, grandes images {noms}"]
        out += [f"  textes {lg} : {a} -> {b} o" for lg, (a, b) in sorted((self.textes or {}).items())]
        return out


def grandes_images(invs: list[Invitation]) -> list[tuple[int, object]]:
    """[(n° de grande image, objet qui la dessine)] : l'enveloppe (commune aux invitations) puis une par objet de
    voyage, dans l'ordre."""
    out = [(ID_GRANDE, None)] if any(not i.propre for i in invs) else []
    vus = set()
    for i in invs:
        if i.propre and i.id_grande not in vus:                   # une par case (§16.11 : trousseau)
            vus.add(i.id_grande)
            out.append((i.id_grande, i))
    return out


def fichiers_a(source: L.SourceRomfs, invs: list[Invitation] | None = None) -> tuple[dict, dict, Resume]:
    """(remplacements, ajouts, résumé) à faire dans `yw2_a.fa` : la configuration des objets et les grandes images.
    À passer à `level5.arc0_modifier` (seul, ou avec les fichiers d'un autre module : `lieu_libre.modifications`)."""
    invs = objets_installes() if invs is None else invs
    f, base, _taille = source.ouvrir(ARCHIVE)
    with f:
        arc = L.Arc0(f, base)
        if CONFIG not in arc.entrees:
            raise ErreurInvitations(f"{CONFIG} absent de {ARCHIVE}")
        if ico.DOSSIER_ATLAS + ico.MODELE_GRANDE not in arc.entrees:
            raise ErreurInvitations(f"{ico.DOSSIER_ATLAS}{ico.MODELE_GRANDE} absent")
        modele = arc.lire(ico.DOSSIER_ATLAS + ico.MODELE_GRANDE)
        ajouts, grandes = {}, {}
        for n, obj in grandes_images(invs):
            ch = ico.DOSSIER_ATLAS + "item_%03d.xi" % n
            if ch in arc.entrees or ch in ajouts:
                raise ErreurInvitations(f"{ch} existe déjà")
            pix = dessiner(ico.TAILLE_GRANDE) if obj is None else obj.pixels(ico.TAILLE_GRANDE)
            ajouts[ch], grandes[n] = ico.encoder_grande(modele, pix)
        ancien = arc.lire(CONFIG)
        nouveau = modifier_config(ancien, invs)
    res = Resume(len(invs), config=(len(ancien), len(nouveau)), textes={}, contenus={},
                 grande=grandes.get(ID_GRANDE), grandes=grandes)
    res.contenus[ARCHIVE] = {CONFIG: nouveau, **ajouts}
    return {CONFIG: nouveau}, ajouts, res


def modifications_langues(source: L.SourceRomfs, invs: list[Invitation], res: Resume) -> list:
    """Remplacements des archives de langue PRÉSENTES (tête réécrite, fichier de textes agrandi mis à la fin).
    ErreurFormat si une seule archive présente ne peut pas être modifiée (tout ou rien)."""
    mods, langues = [], []
    for lg in LANGUES:
        try:
            f, base, taille = source.ouvrir(nom_fa(lg))
        except L.ErreurFormat:
            continue                             # langue absente de cette ROM : rien à faire pour elle
        with f:
            arc = L.Arc0(f, base)
            ch = chemin_textes(lg)
            if ch not in arc.entrees:
                raise ErreurInvitations(f"{ch} absent de {nom_fa(lg)}")
            ancien = arc.lire(ch)
            nouveau = modifier_textes(ancien, invs, lg)
            f.seek(base)
            tete = f.read(arc.off_donnees)
            nouvelle, suffixe = L.arc0_modifier(tete, taille, {ch: nouveau}, {})
        mods += [ico.Modification(nom_fa(lg), p, o, lg, res) for p, o in ico.spans_differents(tete, nouvelle)]
        mods.append(ico.Modification(nom_fa(lg), taille, suffixe, lg, res))
        res.textes[lg] = (len(ancien), len(nouveau))
        res.contenus[nom_fa(lg)] = {ch: nouveau}
        langues.append(lg)
    if not langues:
        raise ErreurInvitations("aucune archive de langue dans le RomFS")
    res.langues = tuple(langues)
    return mods


def archives(source: L.SourceRomfs) -> list[str]:
    """Archives que le module modifie pour ce RomFS (toutes nécessaires : tout ou rien)."""
    out = [ARCHIVE]
    for lg in LANGUES:
        try:
            f, _b, _t = source.ouvrir(nom_fa(lg))
        except L.ErreurFormat:
            continue
        f.close()
        out.append(nom_fa(lg))
    return out


def modifications(source: L.SourceRomfs, invs: list[Invitation] | None = None, verifier_sha1: bool = True,
                  grande_vitrine: bool = False, fichiers=None) -> tuple[list, list[str], Resume]:
    """Toutes les modifications du module (hors atlas : `case_atlas()` est à passer à `icone.modifications`).

    `grande_vitrine` : la grande image de l'objet vitrine (icone.py) est ajoutée à la même tête de `yw2_a.fa` (ne pas
    la demander en plus à `icone.modifications` : un seul calcul de la tête par archive).
    `fichiers` : (remplacements, ajouts, résumé) déjà calculés par `fichiers_a` et DÉJÀ pris en charge par un autre
    module pour `yw2_a.fa` (`lieu_libre.modifications(supplement=…)`) : seules les archives de langue sont rendues.
    ErreurFormat : rien n'est à installer pour les invitations."""
    invs = objets_installes() if invs is None else invs
    avert: list[str] = []
    mods: list = []
    if fichiers is None:
        rempl, ajouts, res = fichiers_a(source, invs)
        f, base, taille = source.ouvrir(ARCHIVE)
        with f:
            arc = L.Arc0(f, base)
            f.seek(base)
            tete = f.read(arc.off_donnees)
        import hashlib
        if verifier_sha1 and hashlib.sha1(tete).hexdigest() != ico.SHA1_TETE_A:
            raise ErreurInvitations("tête de l'archive différente de l'original attendu (autre version du jeu ou "
                                    "autre mod)")
        nouvelle, suffixe = L.arc0_modifier(tete, taille, rempl, ajouts)
        finale = None
        if grande_vitrine:
            m, a = ico.modifications_grande(source, sha1_tete=ico.SHA1_TETE_A if verifier_sha1 else None,
                                            tete_depart=nouvelle)
            if m:
                mods += m                # écarts entre la tête d'origine et la tête finale (les deux modules)
                finale = True
            else:
                avert += a
        if finale is None:
            mods += [ico.Modification(ARCHIVE, p, o, ARCHIVE, res) for p, o in ico.spans_differents(tete, nouvelle)]
        mods.append(ico.Modification(ARCHIVE, taille, suffixe, ARCHIVE, res))
    else:
        _r, _a, res = fichiers
    mods += modifications_langues(source, invs, res)
    return mods, avert, res


def verifier(source: L.SourceRomfs, patchs: dict[str, bytes], invs: list[Invitation] | None = None) -> list[str]:
    """Relit les archives PATCHÉES (patchs BPS appliqués en mémoire à la seule tête et à la fin ajoutée) comme le
    fera le jeu : chaque invitation a son entrée, son index, son nom dans chaque langue, la description et la grande
    image. Renvoie les lignes du contrôle ; ErreurFormat au premier écart."""
    import io
    invs = objets_installes() if invs is None else invs
    lignes = []

    def archive_patchee(fa):
        f, base, taille = source.ouvrir(fa)
        with f:
            sortie = io.BytesIO()
            _bps.bps_appliquer_flux(f, base, taille, patchs["romfs_ext/%s.bps" % fa], sortie)
        return sortie

    def controler(fa, lecture):
        s = archive_patchee(fa)
        arc = L.Arc0(s, 0)
        lecture(arc)

    def config(arc):
        c = t2b.Cfg(arc.lire(CONFIG))
        imp = {e.mots[0]: e for e in c.par_nom("ITEM_IMPORTANT")}
        idx = {e.mots[0]: e for e in c.par_nom("ITEM_INDEX")}
        rangs = [e.mots[0] for e in c.par_nom("ITEM_IMPORTANT")]
        cons = {e.mots[0]: e for e in c.par_nom("ITEM_CONSUME")}
        for inv in invs:
            x = idx.get(inv.hachage)
            e = imp.get(inv.hachage)
            if e is None or x is None or x.mots[1] != TYPE_IMPORTANT or rangs[x.mots[2]] != inv.hachage \
                    or e.mots[V_NOM] != inv.hachage_nom \
                    or (e.mots[V_COLONNE], e.mots[V_LIGNE]) != (inv.colonne, inv.ligne) \
                    or e.mots[V_DESCRIPTION] != inv.hachage_description:
                raise ErreurInvitations(f"contrôle : {inv.cle} mal défini dans la configuration patchée")
        if c.par_nom("ITEM_IMPORTANT_BEGIN")[0].mots[0] != len(imp) or \
                c.par_nom("ITEM_INDEX_BEGIN")[0].mots[0] != len(idx) or \
                c.par_nom("ITEM_CONSUME_BEGIN")[0].mots[0] != len(cons):
            raise ErreurInvitations("contrôle : compteurs de la configuration patchée")
        for n, _obj in grandes_images(invs):
            im = L.Imgc(arc.lire(ico.DOSSIER_ATLAS + "item_%03d.xi" % n))
            if (im.largeur, im.hauteur) != (ico.TAILLE_GRANDE, ico.TAILLE_GRANDE):
                raise ErreurInvitations(f"contrôle : grande image item_{n:03d}")
        lignes.append(f"{ARCHIVE} : {len(invs)} objets, index et {len(grandes_images(invs))} grande(s) image(s) relus "
                      f"({len(imp)} objets importants)")

    controler(ARCHIVE, config)
    for lg in LANGUES:
        fa = nom_fa(lg)
        if "romfs_ext/%s.bps" % fa not in patchs:
            continue

        def textes(arc, lg=lg):
            c = t2b.Cfg(arc.lire(chemin_textes(lg)))
            noms = {e.mots[0]: c.valeurs(e)[5] for e in c.par_nom("NOUN_INFO")}
            desc = {e.mots[0]: c.valeurs(e)[2] for e in c.par_nom("TEXT_INFO")}
            for inv in invs:
                if noms.get(inv.hachage_nom) != inv.nom(lg):
                    raise ErreurInvitations(f"contrôle : nom de {inv.cle} ({lg})")
            for h, texte in descriptions(invs, lg):
                if desc.get(h) != texte:
                    raise ErreurInvitations(f"contrôle : description ({lg})")
            lignes.append(f"{fa} : {len(invs)} noms et {len(descriptions(invs, lg))} description(s) relus "
                          f"({len(noms)} noms)")
        controler(fa, textes)
    return lignes


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="dossier du RomFS extrait, ou ROM déchiffrée (.3ds/.cci/.cxi)")
    ap.add_argument("--sortie", type=Path, help="dossier du titre où écrire romfs_ext/*.bps (invitations et icônes)")
    ap.add_argument("--apercu", type=Path, help="dossier des PNG d'aperçu de l'enveloppe (hors git)")
    a = ap.parse_args(argv)
    if a.apercu:
        a.apercu.mkdir(parents=True, exist_ok=True)
        for cote in (ico.CASE, ico.TAILLE_GRANDE):
            r = ico.Resultat("", "", 0, 0)
            r.pixels_case = dessiner(cote)
            ico.apercu(r, a.apercu / f"enveloppe_{cote}.png", echelle=256 // cote, cote=cote)
            print(f"aperçu : {a.apercu / f'enveloppe_{cote}.png'}")
    try:
        src = L.SourceRomfs(a.romfs)
        invs = objets_installes()
        mods, avert, res = modifications(src, invs, grande_vitrine=True)
        m2, a2 = ico.modifications(src, grande=False, cases_en_plus=cases_atlas(invs))
    except (L.ErreurFormat, OSError) as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    for ligne in res.lignes():
        print(ligne)
    for w in avert + a2:
        print(f"attention : {w}")
    par_fichier: dict[str, list] = {}
    for m in mods + m2:
        par_fichier.setdefault(m.fichier, []).append(m)
    patchs = {}
    for fa, ms in sorted(par_fichier.items()):
        f, base, taille = src.ouvrir(fa)
        with f:
            sur_place = [(m.position, m.octets) for m in ms if m.position < taille]
            ajout = b"".join(m.octets for m in sorted(ms, key=lambda m: m.position) if m.position >= taille)
            patchs[f"romfs_ext/{fa}.bps"] = _bps.bps_sur_place(f, base, taille, sur_place, ajout)
        print(f"{fa} : patch de {len(patchs[f'romfs_ext/{fa}.bps'])} o")
    try:
        for ligne in verifier(src, patchs, invs):
            print("contrôle :", ligne)
    except L.ErreurFormat as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    if a.sortie:
        for n, p in patchs.items():
            dest = a.sortie / n
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p)
            print(f"  -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
