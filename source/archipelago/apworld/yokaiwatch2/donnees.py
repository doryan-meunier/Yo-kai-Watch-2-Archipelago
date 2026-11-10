# -*- coding: utf-8 -*-
"""Lecture des données versionnées de l'APWorld (`donnees/*.json`, produites par la tâche A1).

Bibliothèque standard seulement, sans Archipelago : ce module est aussi importé par les tests hors ligne.
Le paquet peut être un dossier ou une archive `.apworld` (zip) : on lit d'abord par `pkgutil.get_data`, puis
par le chemin du fichier.
"""
import json
import os
import pkgutil

ICI = os.path.dirname(os.path.abspath(__file__))


def lire_json(nom: str) -> dict:
    """Lit `donnees/<nom>` (ou un fichier à la racine du paquet si `nom` ne contient pas de dossier)."""
    brut = None
    if __package__:
        try:
            brut = pkgutil.get_data(__package__, nom)
        except (OSError, ImportError, ValueError, AttributeError):
            brut = None
    if brut is None:
        with open(os.path.join(ICI, *nom.split("/")), "rb") as f:
            brut = f.read()
    return json.loads(brut.decode("utf-8"))


def lire_json_facultatif(nom: str):
    """Comme `lire_json`, mais renvoie None si le fichier n'existe pas (estampille absente des sources)."""
    try:
        return lire_json(nom)
    except (OSError, ValueError):
        return None


class Donnees:
    """Les quatre JSON de la V1, chargés une fois."""

    def __init__(self):
        self.coffres = lire_json("donnees/coffres.json")["coffres"]
        self.objets = lire_json("donnees/objets.json")["objets"]
        self.emplacements = lire_json("donnees/emplacements_objets_cles.json")["emplacements"]
        regions = lire_json("donnees/regions.json")
        self.regions = regions["regions"]
        self.connexions = regions["connexions"]
        self.chapitres = regions["chapitres"]
        self.objectif = regions["objectif"]
        self.objet_prologue = regions["objet_prologue"]
        self.objets_par_cle = {o["cle"]: o for o in self.objets}
        self.regions_par_cle = {r["cle"]: r for r in self.regions}


_CACHE = None


def donnees() -> Donnees:
    global _CACHE
    if _CACHE is None:
        _CACHE = Donnees()
    return _CACHE
