"""Lots du Bingo-kai (Crank-a-kai) lus dans la ROM DU JOUEUR (V3, lot B1, `docs/systemes/archipelago_v3_bingo_aleatoire.md`),
pour le client et le lanceur : le mélange « Bingo-kai aléatoire » (`client/bingo.py`) se calcule chez le joueur depuis ces
lots et la graine de la partie (`slot_data.bingo_aleatoire`).

    python -m installation.bingo_lots --rom <ROM déchiffrée | dossier du RomFS> [--sortie <dossier>]   (depuis archipelago/)

Règle 6 de `CLAUDE.md` : ni l'APWorld, ni `slot_data`, ni le paquet ne contiennent ces tables (ce serait la table des
lots du RomFS) ; ce module les relit dans la ROM configurée et écrit `bingo_local.json` dans le dossier de données du
client (`%APPDATA%/ykw2-ap/`), JAMAIS versionné ni distribué (build/ en développement).

Contenu (format 1) : les lignes des deux machines ordinaires (`gacha_present`, `gacha_past` : pièce, table), les tables
qu'elles citent (lot, poids, plafond), les lots de ces tables (genre : 0 Yo-kai ; `CHARA_PARAM` ; rang de montre exigé),
et, pour l'affichage seulement, le n° du Médaillium et le nom de chaque Yo-kai, le nom de chaque pièce (langues `fr`
et `engb`). Le client contrôle l'empreinte des données qui décident du mélange (`client/bingo.py`) : une autre ROM
donnerait un autre mélange, il refuse alors le mélange (avertissement), sans rien écrire dans le jeu.

Sources [C, `docs/systemes/archipelago_v3_pieces_speciales.md` §2 ; gestionnaire de CAPSULE_ITEM_INFO `FUN_005032E4`] :
`yw2_a.fa:data/res/capsule/` (fichiers `capsule_config_*.cfg.bin`) (CAPSULE_ITEM_INFO : v[0] lot, v[1] genre (+32), v[2] CHARA_PARAM
ou objet (+4), v[5] rang exigé (+34) ; CAPSULE_RATE_INFO(table) suivi de ses CAPSULE_RATE_INFO_DATA(lot, poids, octet,
plafond)), `capsule_machine_config_*.cfg.bin` (CAPSULE_MACHINE_CONFIG_INFO(machine) suivi de ses
lignes `_DATA` de CAPSULE_MACHINE_CONFIG_INFO (pièce, coût en pièces de jeu, table, 0)), `chara_param_*` (v[1] base, v[49] n°),
`chara_base_*` (v[4] nom), `item_config_*` (v[1] nom), textes `chara_text_<lg>` / `item_text_<lg>` des archives de langue.
Bibliothèque standard seulement (lecteurs de `level5.py` et `rencontres.py`).
"""
from __future__ import annotations

import argparse
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
NOM_FICHIER = "bingo_local.json"
ARCHIVE = "yw2_a.fa"
LANGUES = ("fr", "engb")
# noms assemblés : le paquet ne recopie aucune chaîne de code.bin (contrôle de fabriquer_paquet.py)
MACHINES = {"present": "gacha_" + "present", "passe": "gacha_" + "past"}
MORCEAUX = {"capsule": "/cap" + "sule_config_", "machine": "/cap" + "sule_machine_config_",
            "param": "/chara_" + "param_", "base": "/chara_" + "base_", "objets": "/item_" + "config"}
ENTREES = {"lot": "CAPSULE_ITEM_INFO", "table": "CAPSULE_RATE_INFO", "taux": "CAPSULE_RATE_INFO_DATA",
           "machine": "CAPSULE_MACHINE_CONFIG_INFO", "ligne": "CAPSULE_MACHINE_CONFIG_" "INFO_DATA",
           "param": "CHARA_PARAM_INFO", "base": "CHARA_BASE_YOKAI_INFO"}
V_BASE, V_MEDAILLE, V_NOM_BASE = 1, 49, 4


class ErreurBingo(Exception):
    """ROM sans les tables attendues."""


def crc(s: str) -> int:
    return zlib.crc32(s.encode("ascii")) & 0xFFFFFFFF


def _fichier(arc, morceau: str, extension: str = ".cfg.bin") -> bytes:
    cands = sorted(c for c in arc.entrees if morceau in c and c.endswith(extension))
    if not cands:
        raise ErreurBingo(f"fichier « *{morceau}*{extension} » absent de {ARCHIVE}")
    return arc.lire(cands[0])


def _entier(v, i: int, defaut: int = 0) -> int:
    x = v[i] if len(v) > i else defaut
    return int(x) & 0xFFFFFFFF if isinstance(x, int) and not isinstance(x, bool) else defaut


def lire_tables(capsule: bytes, machines: bytes) -> dict:
    """{machines, tables, lots} depuis les deux fichiers de configuration du Bingo-kai (contenu brut, sans choix)."""
    lots, tables, cur = {}, {}, None
    for n, v in CfgBin(capsule).entrees:
        if n == ENTREES["lot"] and v:
            lots[_entier(v, 0)] = [_entier(v, 1), _entier(v, 2), _entier(v, 5)]
        elif n == ENTREES["table"] and v:
            cur = _entier(v, 0)
            tables.setdefault(cur, [])
        elif n == ENTREES["taux"] and cur is not None:
            tables[cur].append([_entier(v, 0), _entier(v, 1), _entier(v, 3)])
    noms = {crc(x): k for k, x in MACHINES.items()}
    lignes, cur = {k: [] for k in MACHINES}, None
    autres = set()
    for n, v in CfgBin(machines).entrees:
        if n == ENTREES["machine"] and v:
            cur = noms.get(_entier(v, 0))
            if cur is None:
                cur = "autre"
        elif n == ENTREES["ligne"] and cur is not None:
            ligne = [_entier(v, 0), _entier(v, 1), _entier(v, 2)]
            if cur == "autre":
                autres.add(ligne[2])
            else:
                lignes[cur].append(ligne)
    if not all(lignes.values()):
        raise ErreurBingo("machines du Bingo-kai du présent / du passé absentes (ROM européenne de Yo-kai Watch 2 "
                          "attendue)")
    citees = {l[2] for ls in lignes.values() for l in ls} | autres
    tables = {t: x for t, x in tables.items() if t in citees}
    gardes = {lot for t in tables.values() for lot, _p, _c in t}
    return {"machines": lignes, "autres_tables": sorted(autres), "tables": tables,
            "lots": {l: x for l, x in lots.items() if l in gardes}}


def _noms(src, fichier_texte: str) -> dict[str, dict[int, str]]:
    out = {}
    for lg in LANGUES:
        try:
            f, off, _t = src.ouvrir(f"yw2_lg_{lg}.fa")
        except (L5.ErreurFormat, OSError, KeyError):
            out[lg] = {}
            continue
        with f:
            arc = L5.Arc0(f, off)
            cible = [c for c in arc.entrees if c.endswith(f"/{fichier_texte}_{lg}.cfg.bin")]
            out[lg] = {v[0]: v[5] for n, v in CfgBin(arc.lire(cible[0])).entrees
                       if n == "NOUN_INFO" and len(v) > 5 and isinstance(v[0], int) and isinstance(v[5], str)} \
                if cible else {}
    return out


def generer(rom: str | Path) -> dict:
    """Contenu de `bingo_local.json`."""
    src = L5.SourceRomfs(rom)
    f, off, _t = src.ouvrir(ARCHIVE)
    with f:
        arc = L5.Arc0(f, off)
        d = lire_tables(_fichier(arc, MORCEAUX["capsule"]), _fichier(arc, MORCEAUX["machine"]))
        params = {v[0]: v for n, v in CfgBin(_fichier(arc, MORCEAUX["param"])).entrees if n == ENTREES["param"]}
        bases = {v[0]: v for n, v in CfgBin(_fichier(arc, MORCEAUX["base"])).entrees if n == ENTREES["base"]}
        noms_objets = {}
        for c in sorted(x for x in arc.entrees if MORCEAUX["objets"] in x and x.endswith(".cfg.bin")):
            for n, v in CfgBin(arc.lire(c)).entrees:
                if n != "ITEM_INDEX" and v and isinstance(v[0], int) and len(v) > 1 and isinstance(v[1], int):
                    noms_objets.setdefault(v[0], v[1])
    textes_yk, textes_ob = _noms(src, "chara_" + "text"), _noms(src, "item_" + "text")
    yokai = {}
    for lot, (genre, param, _r) in d["lots"].items():
        if genre != 0:
            continue
        p = params.get(param)
        b = bases.get(p[V_BASE]) if p and len(p) > V_BASE else None
        nom = b[V_NOM_BASE] if b and len(b) > V_NOM_BASE else None
        yokai[param] = {"medaille": _entier(p, V_MEDAILLE) if p and len(p) > V_MEDAILLE else 0,
                        "noms": {lg: textes_yk[lg].get(nom, "") for lg in LANGUES}}
    pieces = {l[0] for ls in d["machines"].values() for l in ls if l[0]}
    noms_pieces = {pc: {lg: textes_ob[lg].get(noms_objets.get(pc), "") for lg in LANGUES} for pc in pieces}
    return {"format": FORMAT,
            "machines": d["machines"], "autres_tables": d["autres_tables"],
            "tables": {str(t): x for t, x in sorted(d["tables"].items())},
            "lots": {str(l): x for l, x in sorted(d["lots"].items())},
            "yokai": {str(p): x for p, x in sorted(yokai.items())},
            "pieces": {str(p): x for p, x in sorted(noms_pieces.items())}}


def ecrire(d: dict, dossier: str | Path) -> Path:
    """Écrit `bingo_local.json` (atomique) dans le dossier de données du client."""
    p = Path(dossier)
    p.mkdir(parents=True, exist_ok=True)
    f = p / NOM_FICHIER
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)
    return f


def generer_fichier(rom: str | Path, dossier: str | Path) -> Path:
    return ecrire(generer(rom), dossier)


def _valide(d) -> bool:
    if not isinstance(d, dict) or d.get("format") != FORMAT:
        return False
    try:
        for k in MACHINES:
            for l in d["machines"][k]:
                if len(l) != 3 or not all(isinstance(x, int) for x in l):
                    return False
        for t, lots in d["tables"].items():
            int(t)
            if not all(len(x) == 3 and all(isinstance(y, int) for y in x) for x in lots):
                return False
        for l, x in d["lots"].items():
            int(l)
            if len(x) != 3 or not all(isinstance(y, int) for y in x):
                return False
        return isinstance(d.get("autres_tables"), list) and isinstance(d.get("yokai"), dict) \
            and isinstance(d.get("pieces"), dict)
    except (KeyError, TypeError, ValueError):
        return False


def charger(dossier: str | Path) -> dict | None:
    """Contenu de `bingo_local.json` ; None si absent, illisible ou d'un autre format (à régénérer)."""
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if _valide(d) else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", required=True, help="ROM déchiffrée (.3ds / .cxi) ou dossier du RomFS")
    ap.add_argument("--sortie", help="dossier où écrire bingo_local.json (défaut : résumé seulement)")
    a = ap.parse_args(argv)
    try:
        d = generer(a.rom)
    except (ErreurBingo, L5.ErreurFormat, OSError) as e:
        print(f"ROM refusée : {e}", file=sys.stderr)
        return 1
    n = sum(len(v) for v in d["machines"].values())
    print(f"{n} lignes de machine, {len(d['tables'])} tables, {len(d['lots'])} lots, {len(d['yokai'])} Yo-kai")
    if a.sortie:
        print(ecrire(d, a.sortie))
    return 0


if __name__ == "__main__":
    sys.exit(main())
