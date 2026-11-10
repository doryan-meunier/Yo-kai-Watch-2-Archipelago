"""Objets Archipelago de CE monde montrés avec leur image plutôt qu'avec le logo (branche ap/cles-icone-coffre,
docs/systemes/archipelago_invites.md §21).

Un objet AP sans objet du jeu à donner passe par la vitrine (logo Archipelago + son nom). S'il a une image à lui, le
client écrit dans les tables le hachage d'une DÉFINITION qui la porte. Cette écriture n'est qu'un affichage : tous les
chemins de la boîte (coffres, dons de script, requêtes, boutiques, distributeurs, file ApAnim) traitent déjà ainsi les
objets de ce monde, montrés sans être donnés. La table est fixe et ne dépend d'aucune clé de `slot_data` : la location
est reconnue par le nom d'objet que la graine (ou LocationScouts) fournit déjà pour la vitrine ; une graine en cours en
profite sans être régénérée.

Trois sortes de définitions :
- celles du jeu d'origine (`DU_JEU`), toujours présentes ;
- celles du mod données au joueur par le mod et de même nom que l'objet AP (invitations, Abonnement de train, Voyage
  dans le temps, Miroirs), présentes seulement avec le RomFS du mod ;
- celles d'affichage (`crc32("ap_affiche_" + clé)`), jamais données, pour un objet qui a une image mais pas de définition
  à son nom (autres invitations, Miroirs progressifs, clés du donjon).

Repli : les deux dernières sortes exigent que le jeu publie `ETAT_DEFINITIONS` (patch à jour et RomFS du mod installé) ;
sinon, vitrine et logo, comme avant. Un objet d'un autre monde garde toujours le logo (appelant : `Contenu.propre`).
"""
from __future__ import annotations

import json
import zlib
from pathlib import Path

OBJETS = Path(__file__).resolve().parents[1] / "apworld" / "yokaiwatch2" / "donnees" / "objets.json"

# Objets AP dont le jeu d'origine a la définition, sous le même nom (hachages saisis à la main)
DU_JEU = {"pass_sortilege": 0x0B6C2930, "cle_terrifiante": 0x04815AB1, "cle_sanglier": 0x77CA9EEB,
          "cle_cerf": 0xE775837A, "cle_papillon": 0x73866A27}
# Objets AP du mod dont la définition donnée au joueur porte le nom de l'objet AP
DONNES_MEME_NOM = ("train", "voyage_dans_le_temps", "miroirs")
# Objets AP à définition d'affichage, en plus des invitations sans objet du jeu
AFFICHAGE = ("miroirs_progressifs",) + tuple("cle_donjon_portails_%d" % i for i in range(1, 6))


def _crc(nom: str) -> int:
    return zlib.crc32(nom.encode("ascii")) & 0xFFFFFFFF


def table_par_cle(chemin: str | Path | None = None) -> dict[str, tuple[int, bool]]:
    """{clé de l'objet AP : (hachage de la définition montrée, définition du mod ?)} (`objets.json`)."""
    out: dict[str, tuple[int, bool]] = {}
    for o in json.loads(Path(chemin or OBJETS).read_text(encoding="utf-8"))["objets"]:
        cle = o["cle"]
        if cle in DU_JEU:
            out[cle] = (DU_JEU[cle], False)
        elif cle in DONNES_MEME_NOM:
            out[cle] = (_crc("ap_" + cle), True)
        elif cle in AFFICHAGE:
            out[cle] = (_crc("ap_affiche_" + cle), True)
        elif o.get("famille") == "invitation":
            # (`inventaire` absent : invitation donnée au joueur, sinon sans objet du jeu : définition d'affichage)
            donnee = o.get("inventaire", True) is True
            out[cle] = (_crc(("ap_" if donnee else "ap_affiche_") + cle), True)
    return out


_PAR_NOM: dict[str, tuple[int, bool]] | None = None


def _par_nom() -> dict[str, tuple[int, bool]]:
    """{nom AP, français ou anglais : (hachage, définition du mod ?)} ; vide sans `objets.json` (logo partout)."""
    global _PAR_NOM
    if _PAR_NOM is None:
        try:
            table = table_par_cle()
            objets = json.loads(OBJETS.read_text(encoding="utf-8"))["objets"]
        except (OSError, ValueError, KeyError):
            table, objets = {}, []
        _PAR_NOM = {}
        for o in objets:
            if o["cle"] in table:
                _PAR_NOM[o["nom_fr"]] = _PAR_NOM[o["nom_en"]] = table[o["cle"]]
    return _PAR_NOM


def hachage(nom: str, definitions_du_mod: bool) -> int | None:
    """Définition à montrer pour l'objet AP de CE monde de ce nom, ou None (vitrine et logo)."""
    x = _par_nom().get(nom)
    if x is None or (x[1] and not definitions_du_mod):
        return None
    return x[0]
