"""Noms des cartes et des tribus lus dans la ROM DU JOUEUR, pour le tracker de Yo-kai (onglet « Yo-kai »).

    python -m lanceur.noms_locaux --rom <ROM déchiffrée | dossier du RomFS> --sortie <dossier>   (depuis archipelago/)

Écrit `noms_local.json` dans le dossier de données du client (`%APPDATA%/ykw2-ap/`), à côté de `yokai_local.json`. Ce
fichier contient des textes du jeu dans la langue du joueur : il n'est JAMAIS versionné ni distribué (règle 6 de
`CLAUDE.md`) ; le lanceur le refait depuis la ROM configurée (installation, réparation, ou à l'ouverture de l'onglet
s'il manque).

Source [C, `docs/systemes/archipelago_rando_yokai.md` §4.1] : `yw2_lg_<lg>.fa:data/res/text/system_text_<lg>.cfg.bin`,
entrées `TEXT_INFO(clé, variante, texte, 0)` :
- nom d'une carte = clé `crc32(identifiant de carte)` (identifiants = dossiers `data/res/map/<id>/` de `yw2_a.fa`) ;
- nom d'une tribu = clé `crc32("sys_tribe_%02d" % (tribu - 1))` pour les tribus 1..8 (`FUN_0049f618`, `sub r2, r2, #1`) ;
  0 et 9 n'ont pas de nom ;
- n° du Médaillium de chaque espèce (`CHARA_PARAM_INFO` v[49], fichiers `data/res/character/*.cfg.bin` de `yw2_a.fa`),
  pour lire les bits « vu » de `medaillium.json` (le champ `medaille` de `yokai_local.json`, v[2] de la base, n'est
  PAS ce numéro).
Bibliothèque standard seulement (lecteurs de `installation/level5.py` et `installation/rencontres.py`).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import zlib
from pathlib import Path

ARCHIPELAGO = Path(__file__).resolve().parents[1]
if str(ARCHIPELAGO) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO))

from installation import level5 as L5  # noqa: E402
from installation.rencontres import CfgBin  # noqa: E402

FORMAT = 1
NOM_FICHIER = "noms_local.json"
LANGUES = ("fr", "engb")
TRIBUS = range(1, 9)


def _crc(s: str) -> int:
    return zlib.crc32(s.encode("ascii")) & 0xFFFFFFFF


def identifiants_et_medailles(src: L5.SourceRomfs) -> tuple[list[str], dict[int, int]]:
    """(identifiants de carte, {espèce CHARA_PARAM: n° du Médaillium}) depuis yw2_a.fa. N° = `CHARA_PARAM_INFO` v[49]
    (champ u16 +100 de l'enregistrement natif, `FUN_004D6B0C` ; 0 = hors Médaillium), celui des bits du Médaillium
    de la sauvegarde (P+0x40C « vu », `FUN_0041550C`) [C, archipelago_rando_yokai.md « Tracker »]."""
    f, off, _t = src.ouvrir("yw2_a.fa")
    with f:
        arc = L5.Arc0(f, off)
        ids = sorted({c.split("/")[3] for c in arc.entrees if c.startswith("data/res/map/") and c.count("/") >= 4})
        medailles: dict[int, int] = {}
        for c in sorted(arc.entrees):
            if not (c.startswith("data/res/character/") and c.endswith(".cfg.bin")):
                continue
            try:
                entrees = CfgBin(arc.lire(c)).entrees
            except (L5.ErreurFormat, ValueError, IndexError, KeyError, OSError):
                continue
            for nom, v in entrees:
                if nom == "CHARA_PARAM_INFO" and len(v) > 49 and isinstance(v[0], int) and isinstance(v[49], int)                         and 0 < v[49] < 512:
                    medailles[v[0]] = v[49]
        return ids, medailles


def textes_systeme(src: L5.SourceRomfs, langue: str) -> dict[int, str]:
    """TEXT_INFO de system_text_<lg> : clé -> texte (variante 0)."""
    f, off, _t = src.ouvrir(f"yw2_lg_{langue}.fa")
    with f:
        arc = L5.Arc0(f, off)
        cible = [c for c in arc.entrees if c.endswith(f"/system_text_{langue}.cfg.bin")]
        if not cible:
            return {}
        out: dict[int, str] = {}
        for nom, v in CfgBin(arc.lire(cible[0])).entrees:
            if nom == "TEXT_INFO" and len(v) > 2 and isinstance(v[0], int) and isinstance(v[2], str) and v[2] \
                    and v[1] in (0, None):
                out.setdefault(v[0], v[2])
        return out


def generer(rom: str | Path, langues=LANGUES) -> dict:
    src = L5.SourceRomfs(rom)
    ids, medailles = identifiants_et_medailles(src)
    out = {"format": FORMAT, "genere": datetime.datetime.now().isoformat(timespec="seconds"), "langues": {},
           "medailles": {str(p): n for p, n in sorted(medailles.items())}}
    for lg in langues:
        try:
            txt = textes_systeme(src, lg)
        except (L5.ErreurFormat, OSError, KeyError):
            txt = {}
        cartes = {i: txt[_crc(i)] for i in ids if _crc(i) in txt}
        tribus = {str(t): txt[_crc("sys_tribe_%02d" % (t - 1))] for t in TRIBUS if _crc("sys_tribe_%02d" % (t - 1)) in txt}
        out["langues"][lg] = {"cartes": cartes, "tribus": tribus}
    return out


def ecrire(noms: dict, dossier: str | Path) -> Path:
    d = Path(dossier)
    d.mkdir(parents=True, exist_ok=True)
    p = d / NOM_FICHIER
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(noms, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, p)
    return p


def generer_fichier(rom: str | Path, dossier: str | Path) -> Path:
    return ecrire(generer(rom), dossier)


def charger(dossier: str | Path) -> dict | None:
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("format") == FORMAT else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--sortie", required=True)
    a = ap.parse_args(argv)
    p = generer_fichier(a.rom, a.sortie)
    d = charger(a.sortie) or {}
    print("écrit :", p, {lg: (len(v["cartes"]), len(v["tribus"])) for lg, v in d.get("langues", {}).items()},
          len(d.get("medailles", {})), "numéros de médaille")
    return 0


if __name__ == "__main__":
    sys.exit(main())
