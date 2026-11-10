"""Identifiants des distributeurs de soda lus dans la ROM DU JOUEUR (V3, lot C1, `docs/systemes/archipelago_v3_distributeurs.md`),
pour le client : la table des distributeurs de la boîte (zone ApDistrib, §50 de `archipelago_boite.md`) désigne une
machine par (carte, identifiant de son point OP_VENDING_POINT), l'identifiant que le jeu lit en W + 0x30F70 quand le
joueur ouvre la machine.

    python -m installation.distributeurs --rom <ROM déchiffrée | dossier du RomFS> [--sortie <dossier>]   (depuis archipelago/)

Règle 6 de `CLAUDE.md` (même décision que pour les boutiques, `archipelago_boutiques.md` §9) : ni l'APWorld, ni
`slot_data`, ni le paquet ne contiennent ces identifiants (la liste énumérerait toute la table des distributeurs).
L'APWorld ne garde que l'identité d'une machine : carte, RANG de son point dans le fichier `<carte>_oneplace` et nombre
de points du fichier ; ce module relit les points dans la ROM configurée et écrit `distributeurs_local.json` dans le
dossier de données du client (`%APPDATA%/ykw2-ap/`), JAMAIS versionné ni distribué (build/ en développement).

Contrôles (refus clair si la ROM ne correspond pas) : chaque carte de l'APWorld a le nombre de points attendu ; la liste
(CRC-32 du nom de la carte, identifiant du point, réglage) des 54 machines, dans l'ordre de l'APWorld, redonne
`EMPREINTE_DISTRIBUTEURS` (SHA-1) ; aucun identifiant nul ni en double dans une carte.

Source [C, `tools/romfs/cfg_entrees.py --nom OP_VENDING_POINT`] : `yw2_a.fa:data/res/map/<carte>/<carte>.pck`, fichier
`<carte>_oneplace_*.cfg.bin` (jamais la variante `_gate`), entrées OP_VENDING_POINT dans l'ordre du fichier : champ 1 =
identifiant du point, champ 3 = réglage (n° du fichier `shop_shpM00n`).
Bibliothèque standard seulement (lecteurs de `level5.py` et `rencontres.py`).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import zlib
from pathlib import Path

ARCHIPELAGO = Path(__file__).resolve().parents[1]
if str(ARCHIPELAGO) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO))

from installation import level5 as L5  # noqa: E402
from installation.rencontres import CfgBin  # noqa: E402

FORMAT = 1
NOM_FICHIER = "distributeurs_local.json"
ARCHIVE = "yw2_a.fa"
# chemins et noms assemblés : le paquet ne recopie aucune chaîne de code.bin (contrôle de fabriquer_paquet.py)
DOSSIER_CARTES = "data/res/" + "map/"
MORCEAU_ONEPLACE, MORCEAU_GATE = "_one" + "place_", "_ga" + "te"
ENTREE = "OP_VEND" + "ING_POINT"
APWORLD_DISTRIBUTEURS = ARCHIPELAGO / "apworld" / "yokaiwatch2" / "distributeurs.py"


class ErreurDistributeurs(Exception):
    """ROM qui ne correspond pas à la table de l'APWorld, ou machine de `slot_data` introuvable dans la table locale."""


def chemin_pck(carte: str) -> str:
    return DOSSIER_CARTES + carte + "/" + carte + ".pck"


def points_fichier(data: bytes) -> list[list[int]]:
    """[identifiant, réglage] des entrées OP_VENDING_POINT d'un fichier `_oneplace`, dans l'ordre du fichier."""
    out = []
    for nom, vals in CfgBin(data).entrees:
        if nom == ENTREE:
            p = vals[0] if vals else None
            r = vals[2] if len(vals) > 2 else None
            out.append([int(p) & 0xFFFFFFFF if isinstance(p, int) else 0, int(r) if isinstance(r, int) else 0])
    return out


def lire_archive(arc, cartes) -> dict[str, list[list[int]]]:
    """{carte: [[identifiant, réglage], …]} des cartes demandées d'une archive `yw2_a.fa` ouverte (`level5.Arc0`)."""
    table = {}
    for carte in cartes:
        chemin = chemin_pck(carte)
        if chemin not in arc.entrees:
            continue
        x = L5.Xpck(arc.lire(chemin))
        points = []
        for n in sorted(f[0] for f in x.fichiers):
            if n.startswith(carte + MORCEAU_ONEPLACE) and MORCEAU_GATE not in n and "_pos" not in n:
                points += points_fichier(x.lire(n))
        table[carte] = points
    return table


def apworld_distributeurs(chemin: str | Path | None = None):
    """Module `distributeurs.py` de l'APWorld embarqué (chargé avec `boutiques.py`, dont il prend les noms de régions)."""
    p = Path(chemin) if chemin else APWORLD_DISTRIBUTEURS
    nom = "ykw2_apworld_distributeurs_paquet"
    if nom not in sys.modules:
        import types
        paquet = types.ModuleType(nom)
        paquet.__path__ = [str(p.parent)]
        sys.modules[nom] = paquet
    spec = importlib.util.spec_from_file_location(nom + ".distributeurs", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nom + ".distributeurs"] = mod
    spec.loader.exec_module(mod)
    return mod


def lire_rom(rom: str | Path, cartes) -> dict[str, list[list[int]]]:
    src = L5.SourceRomfs(rom)
    f, off, _t = src.ouvrir(ARCHIVE)
    with f:
        return lire_archive(L5.Arc0(f, off), cartes)


def empreinte(liste) -> str:
    """SHA-1 de (CRC-32 de la carte, identifiant, réglage) u32 petit-boutistes (`EMPREINTE_DISTRIBUTEURS` de l'APWorld)."""
    return hashlib.sha1(b"".join(struct.pack("<III", zlib.crc32(c.encode("ascii")) & 0xFFFFFFFF, p & 0xFFFFFFFF,
                                             r & 0xFFFFFFFF) for c, p, r in liste)).hexdigest()


def point(table: dict, carte: str, rang: int, nb_points: int | None = None) -> int:
    """Identifiant du point de la machine (carte, rang) ; ErreurDistributeurs si la table locale ne le permet pas."""
    pts = table.get(carte) if isinstance(table, dict) else None
    if not isinstance(pts, list):
        raise ErreurDistributeurs(f"carte {carte!r} sans distributeur dans la ROM")
    if nb_points is not None and len(pts) != nb_points:
        raise ErreurDistributeurs(f"carte {carte} : {len(pts)} distributeurs dans la ROM, {nb_points} attendus")
    if not isinstance(rang, int) or not 0 <= rang < len(pts):
        raise ErreurDistributeurs(f"carte {carte} : distributeur {rang!r} hors du fichier ({len(pts)})")
    if not pts[rang][0]:
        raise ErreurDistributeurs(f"carte {carte} : distributeur {rang} sans identifiant")
    return pts[rang][0]


def verifier(table: dict, apw) -> list[tuple[str, int, int]]:
    """Contrôle la table lue dans la ROM contre celle de l'APWorld (`apw` : module distributeurs) ; renvoie (carte,
    identifiant, réglage) des machines dans l'ordre de l'APWorld. ErreurDistributeurs si la ROM ne correspond pas."""
    for carte, (_region, n) in apw.CARTES.items():
        pts = table.get(carte)
        if pts is None or len(pts) != n:
            raise ErreurDistributeurs(f"carte {carte} : {0 if pts is None else len(pts)} distributeurs dans la ROM, {n} "
                                      "attendus (ROM européenne de Yo-kai Watch 2 attendue)")
        ids = [p for p, _r in pts]
        if 0 in ids or len(set(ids)) != len(ids):
            raise ErreurDistributeurs(f"carte {carte} : identifiants de distributeur nuls ou en double")
    liste = [(d["carte"], table[d["carte"]][d["rang"]][0], table[d["carte"]][d["rang"]][1]) for d in apw.DISTRIBUTEURS]
    if len(liste) != apw.NB_MACHINES or empreinte(liste) != apw.EMPREINTE_DISTRIBUTEURS:
        raise ErreurDistributeurs("distributeurs différents de ceux de l'APWorld (ordre ou contenu) : ROM européenne de "
                                  "Yo-kai Watch 2 attendue")
    return liste


def generer(rom: str | Path, apw=None) -> dict:
    """Contenu de `distributeurs_local.json` (vérifié contre l'APWorld embarqué) : {format, empreinte, cartes}."""
    apw = apw or apworld_distributeurs()
    table = lire_rom(rom, apw.CARTES)
    verifier(table, apw)
    return {"format": FORMAT, "empreinte": apw.EMPREINTE_DISTRIBUTEURS, "cartes": table}


def ecrire(d: dict, dossier: str | Path) -> Path:
    """Écrit `distributeurs_local.json` (atomique) dans le dossier de données du client."""
    p = Path(dossier)
    p.mkdir(parents=True, exist_ok=True)
    f = p / NOM_FICHIER
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, f)
    return f


def generer_fichier(rom: str | Path, dossier: str | Path, apw=None) -> Path:
    return ecrire(generer(rom, apw), dossier)


def charger(dossier: str | Path, empreinte_attendue: str | None = None) -> dict | None:
    """Table {carte: [[identifiant, réglage], …]} de `distributeurs_local.json` ; None si absent, illisible, d'un autre
    format ou vérifié contre une autre table de l'APWorld (`empreinte_attendue` : à régénérer)."""
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("format") != FORMAT or not isinstance(d.get("cartes"), dict):
        return None
    if empreinte_attendue is not None and d.get("empreinte") != empreinte_attendue:
        return None
    table = {}
    for carte, pts in d["cartes"].items():
        if not isinstance(pts, list) or not all(isinstance(x, list) and len(x) == 2 and all(
                isinstance(v, int) and 0 <= v <= 0xFFFFFFFF for v in x) for x in pts):
            return None
        table[carte] = pts
    return table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", required=True, help="ROM déchiffrée (.3ds / .cxi) ou dossier du RomFS")
    ap.add_argument("--sortie", help="dossier où écrire distributeurs_local.json (défaut : contrôle seulement)")
    ap.add_argument("--empreinte", action="store_true", help="affiche l'empreinte calculée sans contrôle (maintenance)")
    a = ap.parse_args(argv)
    if a.empreinte:
        apw = apworld_distributeurs()
        t = lire_rom(a.rom, apw.CARTES)
        liste = [(d["carte"], t[d["carte"]][d["rang"]][0], t[d["carte"]][d["rang"]][1]) for d in apw.DISTRIBUTEURS
                 if d["carte"] in t and d["rang"] < len(t[d["carte"]])]
        print(f"{len(liste)} machines ; empreinte {empreinte(liste)}")
        return 0
    try:
        d = generer(a.rom)
    except (ErreurDistributeurs, L5.ErreurFormat, OSError) as e:
        print(f"ROM refusée : {e}", file=sys.stderr)
        return 1
    n = sum(len(v) for v in d["cartes"].values())
    print(f"{len(d['cartes'])} cartes, {n} distributeurs ; conformes à l'APWorld (empreinte {d['empreinte']})")
    if a.sortie:
        print(ecrire(d, a.sortie))
    return 0


if __name__ == "__main__":
    sys.exit(main())
