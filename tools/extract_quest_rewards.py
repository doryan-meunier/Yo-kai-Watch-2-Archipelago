# -*- coding: utf-8 -*-
"""
Génère la table des récompenses de quêtes -> objets du jeu (avec hash).

Croise game_data.QUEST_DETAILS (récompenses texte du guide Supersoluce) avec
yokaiwatch2/data/item_hashes.json (hash CRC32 -> nom FR des 889 objets). Sert
à construire un pool d'items Archipelago FIDÈLE : chaque quête contribue au
pool le(s) objet(s) qu'elle donnait réellement.

Sortie : yokaiwatch2/data/quest_rewards.json
  { "Requête : <nom>": [ {"nom","hash","qte"}, ... ], ... }

Usage : python tools/extract_quest_rewards.py
"""
import difflib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent / "yokaiwatch2"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_reward(lines):
    """Extrait [(nom_objet, quantité)] d'une récompense texte (ignore xp/€)."""
    objs = []
    for line in lines:
        line = line.strip().rstrip(".")
        if re.match(r"^\d+\s*(xp|€)", line.lower()):
            continue
        for part in re.split(r"\s+ou\s+|\s+et\s+|,", line):
            part = part.strip()
            qty = 1
            m = re.match(r"^(\d+)x\s+(.+)$", part)       # préfixe "3x Objet"
            if m:
                qty, part = int(m.group(1)), m.group(2).strip()
            m = re.match(r"(.+?)\s*x\s*(\d+)$", part)     # suffixe "Objet x2"
            if m:
                part, qty = m.group(1).strip(), int(m.group(2))
            if part and not re.match(r"^\d+\s*(xp|€)", part.lower()):
                objs.append((part, qty))
    return objs


def main():
    gd = _load("gd", ROOT / "game_data.py")
    items = json.loads((ROOT / "data" / "item_hashes.json").read_text(encoding="utf-8"))
    name2hash = {n: h for h, n in items.items()}
    allnames = list(name2hash)
    normmap = {}
    for n in allnames:
        normmap.setdefault(norm(n), n)

    def match(obj):
        if obj in name2hash:
            return obj
        n = norm(obj)
        if n in normmap:
            return normmap[n]
        cand = [normmap[k] for k in normmap
                if k.startswith(n[:8]) or n.startswith(k[:8])]
        if cand:
            return cand[0]
        cl = difflib.get_close_matches(obj, allnames, n=1, cutoff=0.72)
        return cl[0] if cl else None

    rank_quests = {"Obtenons le rang C !", "Obtenons le rang B !",
                   "Obtenons le rang A !", "Obtenons le rang S !"}
    services = {name for name, _, _ in gd.SERVICES}

    out = {}
    for name, details in gd.QUEST_DETAILS.items():
        rewards = []
        for obj, qty in parse_reward(details.get("recompenses", [])):
            game_name = match(obj)
            if game_name:
                rewards.append({"nom": game_name, "hash": name2hash[game_name],
                                "qte": qty})
        if not rewards:
            continue
        if name in rank_quests:
            key = name
        elif name in services:
            key = f"Service : {name}"
        else:
            key = f"Requête : {name}"
        out[key] = rewards

    dest = ROOT / "data" / "quest_rewards.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in out.values())
    print(f"{len(out)} quêtes/services avec {total} objets de récompense "
          f"-> {dest}")


if __name__ == "__main__":
    main()
