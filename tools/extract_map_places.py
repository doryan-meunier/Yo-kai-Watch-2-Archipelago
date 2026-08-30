#!/usr/bin/env python3
"""
Génère yokaiwatch2/data/map_places.json : carte -> lieu, et noms connus.

`map_config.cfg.bin` regroupe les 283 cartes du jeu en ~69 LIEUX (champ 4).
C'est le découpage interne des développeurs, celui que reflète le Médallium.
En revanche les NOMS de ces lieux n'existent nulle part en texte : ils sont
dessinés dans les images localisées (le même fichier `worldmap_*` existe en
fr/en/de/es). On amorce donc la table de noms avec ce que les coffres
permettent de déduire SANS ambiguïté, et on la complètera à la main.

Sortie :
  {"maps":    {"t101g00": 55, ...},          carte -> identifiant de lieu
   "places":  {"55": "École élémentaire", ...}, noms connus (partiels)
   "regions": {"t101": "Les Hauts de Granval", ...}}  repli par préfixe

    python tools/extract_map_places.py [romfs]
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc0 import Arc0, crc32          # noqa: E402
from cfgbin import CfgBin             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROMFS_DEFAUT = r"C:\Users\dorya\Downloads\3dstool\romfs"
CLE_CARTE = 0x5F53258A
CHAMP_LIEU = 4
# ⚠️ AUCUN nom automatique (décision 2026-08-30). L'appariement coffre -> carte
# est lui-même approximatif : il attribuait « École élémentaire de Granval » à
# une carte du Centre-ville. Un nom FAUX est pire qu'un nom absent — le joueur
# chercherait au mauvais endroit. On ne garde donc que la structure (carte ->
# lieu) et les régions validées ; les 69 lieux se nomment à la main, en jeu,
# où la bannière du jeu donne la réponse sans ambiguïté.
SEUIL = 101         # jamais atteint : la table de noms reste vide au départ

# Régions par préfixe, déduites des coffres puis validées à la main.
REGIONS = {
    "t001": "Mont Sylvestre", "t002": "Mont Sylvestre",
    "t100": "Granval", "t101": "Les Hauts de Granval",
    "t102": "Mont Sylvestre", "t103": "Coteau fleuri",
    "t104": "Centre-ville de Granval", "t105": "Quartier des boutiques",
    "t106": "La Corniche", "t107": "Tour Excellence",
    "t121": "San Fantastico", "t131": "Ourcival",
    "t132": "Ourcival", "t200": "Plaines Plinpot",
    "t201": "Vieux Granval", "t202": "Vieux Granval",
    "t206": "Vieux Granval", "t231": "Vieil Ourcival",
    "t232": "Vieil Ourcival", "t301": "Limbes éternelles",
    "t302": "Limbes éternelles", "t303": "Limbes éternelles",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    romfs = Path(sys.argv[1] if len(sys.argv) > 1 else ROMFS_DEFAUT)
    arc = Arc0(str(romfs / "yw2_a.fa"))
    cfg = CfgBin(arc.read_file("map_config.cfg.bin"))

    cartes = sorted({n.rsplit("/", 1)[-1][:-4] for n in arc.names()
                     if n.endswith(".pck")
                     and re.match(r"^t\d{3}[a-z]\d{2}$",
                                  n.rsplit("/", 1)[-1][:-4])})
    par_hash = {crc32(m.encode()): m for m in cartes}
    lieux = {}
    for e in (x for x in cfg.entries if x.key == CLE_CARTE):
        carte = par_hash.get(e.values[0])
        if carte and len(e.values) > CHAMP_LIEU:
            lieux[carte] = e.values[CHAMP_LIEU]

    # amorçage des noms par les coffres, uniquement quand c'est net
    registre = json.loads(
        (ROOT / "yokaiwatch2/data/tbox_offsets.json").read_text("utf-8"))
    votes = collections.defaultdict(collections.Counter)
    for loc, spec in registre.get("chests", {}).items():
        carte = spec["file"].replace(".pck", "")
        if carte in lieux:
            votes[lieux[carte]][loc.rsplit(" - Coffre", 1)[0]] += 1
    noms = {}
    for lieu, cnt in votes.items():
        total = sum(cnt.values())
        zone, n = cnt.most_common(1)[0]
        if 100 * n // total >= SEUIL:
            noms[str(lieu)] = zone

    out = ROOT / "yokaiwatch2" / "data" / "map_places.json"
    out.write_text(json.dumps({"maps": lieux, "places": noms,
                               "regions": REGIONS},
                              ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(lieux)} cartes -> {len(set(lieux.values()))} lieux")
    print(f"{len(noms)} lieux nommés automatiquement "
          f"(sur {len(votes)} documentés par les coffres)")
    print(f"écrit : {out}")


if __name__ == "__main__":
    main()
