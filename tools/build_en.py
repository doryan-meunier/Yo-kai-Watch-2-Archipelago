#!/usr/bin/env python3
"""
Génère la version ANGLAISE de l'apworld depuis la source française.

Principe : la source reste unique (dossier `yokaiwatch2/`, jeu « Yo-kai Watch 2 »).
Ce script en produit une copie `yokaiwatch2en/` où chaque LITTÉRAL de chaîne qui
est un nom de location / d'item / de zone est remplacé par sa traduction
(tools/i18n_translate.py), plus les gabarits de f-strings et le nom du jeu.
La logique n'est pas touchée : mêmes IDs, mêmes règles, même client.

    python tools/build_en.py            # écrit ./yokaiwatch2en/ + rapport
    python tools/build_en.py --report   # n'écrit rien, liste les remplacements

⚠️ Ne JAMAIS renommer le jeu français : les YAML et les seeds existantes
   s'appuient sur « Yo-kai Watch 2 ».
"""

import argparse
import io
import json
import re
import shutil
import sys
import tokenize
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n_translate import translate_name, _piece  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "yokaiwatch2"
DST = ROOT / "yokaiwatch2en"

GAME_FR = "Yo-kai Watch 2"
GAME_EN = "Yo-kai Watch 2 (English)"

# Gabarits de f-strings et fragments de libellés : remplacés tels quels.
# (Le contenu interpolé, lui, vient des tables déjà traduites.)
TEMPLATES = {
    'f"Chapitre {n} : {CHAPITRES[n]}"': 'f"Chapter {n}: {CHAPITRES[n]}"',
    'f"Chapitre {chapter} terminé"': 'f"Chapter {chapter} complete"',
    'f"Événement : Chapitre {chapter}"': 'f"Event: Chapter {chapter}"',
    'f"Boss : {name}"': 'f"Boss: {name}"',
    'f"Requête : {_name}"': 'f"Request: {_name}"',
    'f"Service : {_name}"': 'f"Service: {_name}"',
    'f"Requête : {quest_name}"': 'f"Request: {quest_name}"',
    'f"Service : {quest_name}"': 'f"Service: {quest_name}"',
    'f"Montée de rang : {WATCH_RANKS[rank]}"': 'f"Rank Up: {WATCH_RANKS[rank]}"',
    '"Montée de rang : "': '"Rank Up: "',
    'f"Tablo-blabla n°{num:02d} : {reponse}"':
        'f"Baffle Board #{num:02d}: {reponse}"',
    'f"Médaille légendaire : {yokai}"': 'f"Legendary Medal: {yokai}"',
    'f"Sceau légendaire : {yokai}"': 'f"Legendary Seal: {yokai}"',
    'f"Passe de quartier : {district}"': 'f"District Pass: {district}"',
    'f"Amitié : {_name}"': 'f"Friendship: {_name}"',
    'f"Évolution : {name}"': 'f"Evolution: {name}"',
    'f"Objet de fusion : {_nom}"': 'f"Fusion Item: {_nom}"',
    'f"Planque : {_nom}"': 'f"Hideout: {_nom}"',
    'f"Komasan : rencontre {num}"': 'f"Komasan: encounter {num}"',
    'f"Yo-criminels : {n} capture"': 'f"Yo-criminals: {n} capture"',
    'f"{prefix} : {name}"': 'f"{prefix}: {name}"',
    'f"{prefix} : {name} ({region})"': 'f"{prefix}: {name} ({region})"',
    'f"{connection.name} (retour)"': 'f"{connection.name} (return)"',
    'f"{_zone} - Coffre {_i:02d}"': 'f"{_zone} - Chest {_i:02d}"',
    'f"{region} - {label} {i:02d}"': 'f"{region} - {label} {i:02d}"',
    # découpage de noms composés (doit suivre les libellés traduits)
    '"Coffre", 1)': '"Chest", 1)',
    '" - Coffre", 1)': '" - Chest", 1)',
    'r"Chapitre (\\d+) "': 'r"Chapter (\\d+) "',
    '"Objet-clé : "': '"Key Item: "',
    # identité du monde
    f'"{GAME_FR} Client"': f'"{GAME_EN} Client"',
    f'GAME_NAME = "{GAME_FR}"': f'GAME_NAME = "{GAME_EN}"',
}

# Générateur du pack PopTracker : mêmes règles + ses propres libellés d'UI.
TRACKER_SRC = ROOT / "tools" / "generate_tracker_pack.py"
TRACKER_DST = ROOT / "tools" / "generate_tracker_pack_en.py"
TRACKER_TEMPLATES = {
    'PKG = ROOT / "yokaiwatch2"': 'PKG = ROOT / "yokaiwatch2en"',
    'OUT = ROOT / "tracker" / "ykw2-poptracker"':
        'OUT = ROOT / "tracker" / "ykw2en-poptracker"',
    'zip_path = ROOT / "tracker" / "ykw2-poptracker"':
        'zip_path = ROOT / "tracker" / "ykw2en-poptracker"',
    '"name": "Yo-kai Watch 2 (Archipelago)"':
        '"name": "Yo-kai Watch 2 (Archipelago, English)"',
    f'"game_name": "{GAME_FR}"': f'"game_name": "{GAME_EN}"',
    '"package_uid": "ykw2_ap_doteos"': '"package_uid": "ykw2_ap_doteos_en"',
    '"Rang (logique)"': '"Rank (logic)"',
    '"Rang de Yo-kai Watch"': '"Yo-kai Watch Rank"',
    'f"Rang {letter.upper()}"': 'f"Rank {letter.upper()}"',
    '"Chapitre d\'histoire"': '"Story Chapter"',
    '"Chapitres faits"': '"Chapters done"',
    '"Yo-criminels faits"': '"Yo-criminals done"',
    'r"Chapitre (\\d+)"': 'r"Chapter (\\d+)"',
    '"Égouts - Coffre"': '"Underground Waterway - Chest"',
    '"Égouts - "': '"Underground Waterway - "',
    'tools/generate_tracker_pack.py': 'tools/generate_tracker_pack_en.py',
    # Chemins de sections utilisés par autotracking.lua pour les compteurs des
    # groupes du bas. Le Lua est dans une chaîne triple-quotée, donc invisible
    # pour le tokenizer : il FAUT le traiter ici (sinon compteur « 0/0 »).
    '["@Chapitres/"]': '["@Chapters/"]',
    '["@Yo-criminels/"]': '["@Yo-criminals/"]',
}


def _slug(name: str) -> str:
    """Identique à slug() du générateur de tracker (ids de cartes/items)."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    r = "".join(c if c.isalnum() else "_" for c in s)
    while "__" in r:
        r = r.replace("__", "_")
    return r.strip("_")


def tracker_map_ids(text: str) -> dict:
    """Les ids de cartes « det_<slug de région> » sont écrits EN DUR dans
    MULTI_MAP_COORDS. Le slug vient du nom de région, donc il change avec la
    traduction : on réécrit chaque id sur la région anglaise, sinon les
    marqueurs atterrissent sur une carte fantôme (bug vécu : les coffres des
    Égouts sur « det_egouts » alors que l'onglet est « det_underground_waterway »)."""
    ids = {}
    for fr_region in set(re.findall(r'"([^"\\\n]+)":\s*"[^"\\\n]+\.(?:png|jpg|jpeg|webp)"',
                                    text)):
        en_region = _piece(fr_region)
        if en_region is None:
            continue
        old, new = f'"det_{_slug(fr_region)}"', f'"det_{_slug(en_region)}"'
        if old != new and old in text:
            ids[old] = new
    return ids

# Messages du client (phrases libres, pas des noms) : table dédiée.
CLIENT_MESSAGES = {
    k: v for k, v in json.loads(
        (ROOT / "tools" / "i18n_client_en.json").read_text(encoding="utf-8")
    ).items() if not k.startswith("_")
}

# Fichiers de données non embarqués dans l'apworld.
SKIP_FILES = {"i18n_en.json", "i18n_manual_en.json",
              "important_key_items_FULL_124.json.bak"}

# Littéraux simples, non préfixés (pas de f"", r"", b""). Une apostrophe est
# autorisée dans un littéral entre guillemets doubles, et inversement.
_QUOTED = re.compile(r'(?<![A-Za-z0-9_])(?:"([^"\\\n]*)"|\'([^\'\\\n]*)\')')
# jeton minuscule = code interne (PopTracker, slugs) ; extension = fichier
_CODE = re.compile(r'^[a-z0-9_:.-]+$')
_FILE = re.compile(r'\.(png|jpg|jpeg|webp|json|lua|md|txt|apworld)$', re.I)


def _translate_literal(text: str) -> str:
    """Traduit un littéral simple (nom complet ou morceau de nom)."""
    return translate_name(text) or _piece(text)


# f-strings de coffres : f"<Zone> - Coffre {i:02d}"
_FCHEST = re.compile(r'f"([^"{}]+) - (Coffre|Objet au sol) \{([^}]+)\}"')
_CHEST_LABEL = {"Coffre": "Chest", "Objet au sol": "Ground Item"}


def transform_py(text: str, stats: dict) -> str:
    def fchest(m):
        zone = _piece(m.group(1))
        if zone is None:
            return m.group(0)
        en = f'f"{zone} - {_CHEST_LABEL[m.group(2)]} {{{m.group(3)}}}"'
        stats[m.group(0)] = en
        return en

    text = _FCHEST.sub(fchest, text)

    for fr, en in sorted(TEMPLATES.items(), key=lambda kv: -len(kv[0])):
        if fr in text:
            stats[fr] = en
            text = text.replace(fr, en)

    # Littéraux simples : repérés par le VRAI tokenizer Python. Une regex se
    # décale sur les f-strings (le guillemet fermant se réapparie avec le
    # littéral suivant) et rate des valeurs de dictionnaire.
    lines = text.splitlines(keepends=True)
    edits = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type != tokenize.STRING or tok.start[0] != tok.end[0]:
            continue
        raw = tok.string
        if raw[0] not in "\"'":        # préfixe f/r/b : laissé aux gabarits
            continue
        if raw[:3] in ('"""', "'''"):
            continue
        body = raw[1:-1]
        if not body or "\\" in body:
            continue
        # codes internes, chemins et noms de fichiers : jamais traduits
        # (« rang », « chapitre », « égout.jpg », « images/x.png »…).
        if _CODE.match(body) or _FILE.search(body) or "/" in body:
            continue
        en = _translate_literal(body)
        if en is None or en == body:
            continue
        stats[body] = en
        # la traduction peut contenir une apostrophe ("Shopper's Row") :
        # on choisit un guillemet qui ne s'y trouve pas.
        q = raw[0] if raw[0] not in en else ('"' if '"' not in en else "'")
        edits.append((tok.start[0], tok.start[1], tok.end[1],
                      f"{q}{en.replace(q, chr(92) + q)}{q}"))

    for row, col0, col1, new in sorted(edits, reverse=True):
        line = lines[row - 1]
        lines[row - 1] = line[:col0] + new + line[col1:]
    return "".join(lines)


def transform_json(obj, stats: dict):
    if isinstance(obj, str):
        en = _translate_literal(obj)
        if en is not None and en != obj:
            stats[obj] = en
            return en
        return obj
    if isinstance(obj, list):
        return [transform_json(v, stats) for v in obj]
    if isinstance(obj, dict):
        return {transform_json(k, stats): transform_json(v, stats)
                for k, v in obj.items()}
    return obj


def build(report_only: bool) -> None:
    if not report_only:
        if DST.exists():
            shutil.rmtree(DST)
        DST.mkdir(parents=True)

    per_file = {}
    for path in sorted(SRC.rglob("*")):
        rel = path.relative_to(SRC)
        if path.is_dir() or "__pycache__" in rel.parts:
            continue
        if path.name in SKIP_FILES or path.suffix in {".pyc", ".pyo"}:
            continue
        stats = {}
        if path.suffix == ".py":
            text = path.read_text(encoding="utf-8")
            # ⚠️ mod_patcher.py AUSSI (correctif 2026-08-31) : il porte les
            # NOMS DE FICHIERS de langue (`yw2_lg_fr.fa`, `item_text_fr…`).
            # Sans traduction, la version anglaise allait chercher la
            # traduction FRANÇAISE — que personne d'anglophone n'a installée.
            if path.name in ("client.py", "mod_patcher.py"):
                for fr, en in CLIENT_MESSAGES.items():
                    if fr in text:
                        stats[fr] = en
                        text = text.replace(fr, en)
            out = transform_py(text, stats)
        elif path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if path.name == "archipelago.json":
                # Manifeste : c'est lui qui déclare le jeu à Archipelago.
                data["game"] = GAME_EN
                stats[GAME_FR] = GAME_EN
                out = json.dumps(data, ensure_ascii=False)
            else:
                out = json.dumps(transform_json(data, stats),
                                 ensure_ascii=False, indent=1)
        else:
            out = None
        if stats:
            per_file[str(rel)] = stats
        if not report_only:
            target = DST / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if out is None:
                shutil.copy2(path, target)
            else:
                target.write_text(out, encoding="utf-8")

    # générateur du pack PopTracker anglais
    stats = {}
    text = TRACKER_SRC.read_text(encoding="utf-8")
    tmpl = {**TRACKER_TEMPLATES, **tracker_map_ids(text)}
    for fr, en in sorted(tmpl.items(), key=lambda kv: -len(kv[0])):
        if fr in text:
            stats[fr] = en
            text = text.replace(fr, en)
    text = transform_py(text, stats)
    if stats:
        per_file[str(TRACKER_DST.relative_to(ROOT))] = stats
    if not report_only:
        TRACKER_DST.write_text(text, encoding="utf-8")

    total = sum(len(v) for v in per_file.values())
    for name, stats in per_file.items():
        print(f"{name:32} {len(stats):5} remplacements")
    print(f"TOTAL {total} remplacements")
    if not report_only:
        print(f"OK: {DST}")
    return per_file


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true",
                    help="n'écrit rien, affiche seulement le rapport")
    ap.add_argument("--dump", type=Path,
                    help="écrit le détail des remplacements en JSON")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    per_file = build(args.report)
    if args.dump:
        args.dump.write_text(json.dumps(per_file, ensure_ascii=False, indent=1),
                             encoding="utf-8")
