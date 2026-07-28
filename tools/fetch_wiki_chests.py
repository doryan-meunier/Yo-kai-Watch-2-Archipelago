# -*- coding: utf-8 -*-
"""
Récupère les cartes interactives du wiki Yo-kai Watch FR (coffres, etc.).

Les cartes Fandom sont des pages du namespace "Carte:" (ns 2900) dont le
contenu est un JSON de marqueurs (catégories + positions + popups). Source
la plus fiable pour compter/localiser les coffres YW2 par zone.

    python fetch_wiki_chests.py          # liste + résume toutes les cartes

NOTE : seule « Granval - emplacements » couvre complètement les coffres YW2
(35 violets + 33 jaunes). Les autres zones sont partielles côté coffres.
"""
import json
import urllib.parse
import urllib.request
from collections import Counter

WIKI = "https://yokaiwatch.fandom.com/fr/api.php"
UA = {"User-Agent": "Mozilla/5.0 Chrome/126.0 Safari/537.36"}


def _api(**params):
    params.setdefault("format", "json")
    url = WIKI + "?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30).read())


def list_maps():
    d = _api(action="query", list="allpages", apnamespace=2900, aplimit=200)
    return [p["title"] for p in d["query"]["allpages"]]


def load_map(title):
    d = _api(action="query", titles=title, prop="revisions",
             rvprop="content", rvslots="main")
    content = list(d["query"]["pages"].values())[0]["revisions"][0]["slots"]["main"]["*"]
    return json.loads(content)


def summarize(title):
    m = load_map(title)
    catname = {str(c["id"]): c["name"] for c in m.get("categories", [])}
    markers = m.get("markers", [])
    counts = Counter(catname.get(str(x["categoryId"]), "?") for x in markers)
    return markers, counts


if __name__ == "__main__":
    for title in list_maps():
        _, counts = summarize(title)
        print(f"=== {title.replace('Carte:', '')} ===")
        for cat, n in counts.most_common():
            print(f"   {n:3}  {cat}")
