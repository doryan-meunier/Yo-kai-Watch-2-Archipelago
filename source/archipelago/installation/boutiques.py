"""Hachages des articles de boutique lus dans la ROM DU JOUEUR (checks de boutique, `docs/systemes/archipelago_boutiques.md`
§9), pour le client : la table des boutiques de la boîte (v9, §26) est indexée par ce hachage (clé +0 de l'entrée
SHOP_CONFIG_INFO, celle du flag octet de stock).

    python -m installation.boutiques --rom <ROM déchiffrée | dossier du RomFS> [--sortie <dossier>]   (depuis archipelago/)

Règle 6 de `CLAUDE.md` (décision de l'humain du 2026-09-29) : ni l'APWorld, ni `slot_data`, ni le paquet ne contiennent
ces hachages (la liste énumérait toute la table des boutiques). L'APWorld ne garde que l'identité d'un article : code de
la boutique (N0xx), RANG de son entrée dans le fichier et nombre d'entrées du fichier ; ce module relit les clés dans la
ROM configurée et écrit `boutiques_local.json` dans le dossier de données du client (`%APPDATA%/ykw2-ap/`), JAMAIS
versionné ni distribué (build/ en développement).

Contrôles (refus clair si la ROM ne correspond pas) : chaque boutique de l'APWorld existe et a le nombre d'entrées
attendu ; les clés des 297 articles, dans l'ordre des identifiants AP, redonnent `EMPREINTE_ARTICLES` (SHA-1) (V3, lot
22 : celles de la boutique d'après-jeu N045, à part : `EMPREINTE_ARTICLES_APRES_JEU`) ; aucune clé nulle ni en double. À la résolution d'un article de `slot_data` (`cles_article`) : boutique connue, nombre
d'entrées du fichier égal à celui de la graine, rangs dans le fichier.

Source [C, `tools/romfs/boutiques.py`] : `yw2_a.fa:data/res/shop/shop_shpN0xx_0.01n.cfg.bin` (le seul gabarit chargé
par le jeu), entrées `SHOP_CONFIG_INFO` dans l'ordre du fichier, valeur 0.
Bibliothèque standard seulement (lecteurs de `level5.py` et `rencontres.py`).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import struct
import sys
from pathlib import Path

ARCHIPELAGO = Path(__file__).resolve().parents[1]
if str(ARCHIPELAGO) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO))

from installation import level5 as L5  # noqa: E402
from installation.rencontres import CfgBin  # noqa: E402

FORMAT = 1
NOM_FICHIER = "boutiques_local.json"
ARCHIVE = "yw2_a.fa"
# chemins assemblés : le paquet ne recopie aucune chaîne de code.bin (contrôle de fabriquer_paquet.py)
DOSSIER_SHOP = "data/res/" + "shop/"
PREFIXE, SUFFIXE = "shop_" + "shp", "_0.01n" + ".cfg.bin"
ENTREE = "SHOP_CONFIG_INFO"
RE_CODE = re.compile(r"N\d{3}$")          # boutiques normales (type 0) seulement : les seules de l'APWorld
APWORLD_BOUTIQUES = ARCHIPELAGO / "apworld" / "yokaiwatch2" / "boutiques.py"


class ErreurBoutiques(Exception):
    """ROM qui ne correspond pas à la table de l'APWorld, ou article de `slot_data` introuvable dans la table locale."""


def nom_fichier(code: str) -> str:
    return DOSSIER_SHOP + PREFIXE + code + SUFFIXE


def cles_fichier(data: bytes) -> list[int]:
    """Clés +0 des entrées SHOP_CONFIG_INFO d'un fichier de boutique, dans l'ordre du fichier."""
    out = []
    for nom, vals in CfgBin(data).entrees:
        if nom == ENTREE:
            v = vals[0] if vals else None
            out.append(int(v) & 0xFFFFFFFF if isinstance(v, int) else 0)
    return out


def lire_archive(arc) -> dict[str, list[int]]:
    """{code N0xx: clés} de toutes les boutiques normales d'une archive `yw2_a.fa` ouverte (`level5.Arc0` ou objet qui a
    `entrees` (chemins) et `lire(chemin)`)."""
    table = {}
    for chemin in sorted(arc.entrees):
        if not (chemin.startswith(DOSSIER_SHOP + PREFIXE) and chemin.endswith(SUFFIXE)):
            continue
        code = chemin[len(DOSSIER_SHOP + PREFIXE):-len(SUFFIXE)]
        if RE_CODE.match(code):
            table[code] = cles_fichier(arc.lire(chemin))
    return table


def lire_rom(rom: str | Path) -> dict[str, list[int]]:
    """{code: clés} depuis la ROM déchiffrée (ou le dossier du RomFS) du joueur."""
    src = L5.SourceRomfs(rom)
    f, off, _t = src.ouvrir(ARCHIVE)
    with f:
        return lire_archive(L5.Arc0(f, off))


def apworld_boutiques(chemin: str | Path | None = None):
    """Module `boutiques.py` de l'APWorld embarqué (pur : ni Archipelago, ni autre module du monde)."""
    p = Path(chemin) if chemin else APWORLD_BOUTIQUES
    spec = importlib.util.spec_from_file_location("ykw2_apworld_boutiques_table", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def empreinte(cles) -> str:
    """SHA-1 (hexadécimal) d'une liste de clés u32, petit-boutiste (`EMPREINTE_ARTICLES` de l'APWorld)."""
    return hashlib.sha1(b"".join(struct.pack("<I", k & 0xFFFFFFFF) for k in cles)).hexdigest()


def cles_article(table: dict, code: str, entrees, nb_entrees: int | None = None) -> tuple[int, ...]:
    """Clé(s) d'un article (code de boutique, rangs de ses entrées) ; ErreurBoutiques si la table locale ne le permet
    pas (boutique absente, autre nombre d'entrées, rang hors du fichier, clé nulle)."""
    cles = table.get(code) if isinstance(table, dict) else None
    if not isinstance(cles, list):
        raise ErreurBoutiques(f"boutique {code!r} absente de la ROM")
    if nb_entrees is not None and len(cles) != nb_entrees:
        raise ErreurBoutiques(f"boutique {code} : {len(cles)} entrées dans la ROM, {nb_entrees} attendues")
    entrees = tuple(entrees)
    if not entrees:
        raise ErreurBoutiques(f"boutique {code} : article sans entrée")
    out = []
    for e in entrees:
        if not isinstance(e, int) or not 0 <= e < len(cles):
            raise ErreurBoutiques(f"boutique {code} : entrée {e!r} hors du fichier ({len(cles)} entrées)")
        if not cles[e]:
            raise ErreurBoutiques(f"boutique {code} : entrée {e} sans clé")
        out.append(cles[e])
    return tuple(out)


def verifier(table: dict, apw) -> list[int]:
    """Contrôle la table lue dans la ROM contre celle de l'APWorld (`apw` : module boutiques) ; renvoie les clés des
    articles dans l'ordre des identifiants AP. ErreurBoutiques (message pour le joueur) si la ROM ne correspond pas."""
    for b in apw.BOUTIQUES:
        cles = table.get(b["code"])
        if cles is None:
            raise ErreurBoutiques(f"boutique {b['code']} absente de la ROM (ROM européenne de Yo-kai Watch 2 attendue)")
        if len(cles) != b["nb_entrees"]:
            raise ErreurBoutiques(f"boutique {b['code']} : {len(cles)} articles dans la ROM, {b['nb_entrees']} attendus "
                                  "(ROM européenne de Yo-kai Watch 2 attendue)")
    # (V3, lot 22 : les boutiques d'après-jeu, ajoutées à la fin de la table, ont leur propre empreinte ; celle des 297
    # articles d'avant ne change pas : un fichier local déjà écrit reste valable)
    aj = getattr(apw, "BOUTIQUES_APRES_JEU", frozenset())
    liste, liste_aj = [], []
    for a in apw.BOUTIQUES_ARTICLES:
        (liste_aj if a["boutique"] in aj else liste).extend(cles_article(table, a["boutique"], a["entrees"]))
    if len(set(liste + liste_aj)) != len(liste + liste_aj):
        raise ErreurBoutiques("articles de boutique en double dans la ROM")
    if len(liste) != apw.NB_CLES or empreinte(liste) != apw.EMPREINTE_ARTICLES \
            or (aj and (len(liste_aj) != apw.NB_CLES_APRES_JEU
                        or empreinte(liste_aj) != apw.EMPREINTE_ARTICLES_APRES_JEU)):
        raise ErreurBoutiques("articles de boutique différents de ceux de l'APWorld (ordre ou contenu) : ROM européenne "
                              "de Yo-kai Watch 2 attendue")
    return liste + liste_aj


def generer(rom: str | Path, apw=None) -> dict:
    """Contenu de `boutiques_local.json` (vérifié contre l'APWorld embarqué) : {format, empreinte, boutiques}."""
    apw = apw or apworld_boutiques()
    table = lire_rom(rom)
    verifier(table, apw)
    return {"format": FORMAT, "empreinte": apw.EMPREINTE_ARTICLES, "boutiques": table}


def ecrire(d: dict, dossier: str | Path) -> Path:
    """Écrit `boutiques_local.json` (atomique) dans le dossier de données du client."""
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
    """Table {code: clés} de `boutiques_local.json` ; None si absent, illisible, d'un autre format ou vérifié contre une
    autre table de l'APWorld (`empreinte_attendue` : à régénérer)."""
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("format") != FORMAT or not isinstance(d.get("boutiques"), dict):
        return None
    if empreinte_attendue is not None and d.get("empreinte") != empreinte_attendue:
        return None
    table = {}
    for code, cles in d["boutiques"].items():
        if not isinstance(cles, list) or not all(isinstance(k, int) and 0 <= k <= 0xFFFFFFFF for k in cles):
            return None
        table[code] = cles
    return table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", required=True, help="ROM déchiffrée (.3ds / .cxi) ou dossier du RomFS")
    ap.add_argument("--sortie", help="dossier où écrire boutiques_local.json (défaut : contrôle seulement)")
    a = ap.parse_args(argv)
    try:
        d = generer(a.rom)
    except (ErreurBoutiques, L5.ErreurFormat, OSError) as e:
        print(f"ROM refusée : {e}", file=sys.stderr)
        return 1
    n = sum(len(v) for v in d["boutiques"].values())
    print(f"{len(d['boutiques'])} boutiques, {n} entrées ; articles de l'APWorld conformes (empreinte {d['empreinte']})")
    if a.sortie:
        print(ecrire(d, a.sortie))
    return 0


if __name__ == "__main__":
    sys.exit(main())
