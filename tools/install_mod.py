# -*- coding: utf-8 -*-
"""Installe le mod d'affichage des noms d'objets Archipelago (Yo-kai Watch 2).

Le client peut afficher le VRAI nom de l'objet Archipelago sur les récompenses
de requêtes, à condition que l'archive de langue du jeu soit installée comme
mod LayeredFS. Ce script copie ce fichier depuis VOTRE propre copie du jeu vers
le dossier des mods d'Azahar.

Le fichier n'est pas fourni avec le projet : il fait partie du jeu. Il faut donc
avoir extrait le romfs de sa cartouche / son dump au préalable (3dstool,
ctrtool, GodMode9…).

Usage :
    python tools/install_mod.py <chemin du romfs>

Exemple :
    python tools/install_mod.py "D:\\yw2\\romfs"

Rien n'est modifié dans votre ROM : le client n'écrit que dans la COPIE placée
dans le dossier des mods.
"""
import os
import shutil
import sys

TITLE_ID = "00040000001B2900"     # Yo-kai Watch 2 : Spectres Psychiques (EU)
LANG_ARCHIVE = "yw2_lg_fr.fa"


def mods_dir():
    """Dossier romfs du mod LayeredFS, pour Azahar (ou Citra en repli)."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        sys.exit("APPDATA introuvable : lancez ce script sous Windows.")
    for emu in ("Azahar", "azahar", "Citra"):
        base = os.path.join(appdata, emu)
        if os.path.isdir(base):
            return os.path.join(base, "load", "mods", TITLE_ID, "romfs")
    sys.exit("Ni Azahar ni Citra n'ont été trouvés dans %APPDATA%.")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    romfs = sys.argv[1]
    source = os.path.join(romfs, LANG_ARCHIVE)
    if not os.path.isfile(source):
        sys.exit(f"{LANG_ARCHIVE} est introuvable dans {romfs}.\n"
                 "Vérifiez que vous avez bien extrait le romfs du jeu.")

    target_dir = mods_dir()
    target = os.path.join(target_dir, LANG_ARCHIVE)
    os.makedirs(target_dir, exist_ok=True)

    if os.path.isfile(target):
        answer = input(f"{target}\nexiste déjà. L'écraser ? [o/N] ").strip().lower()
        if answer not in ("o", "oui", "y", "yes"):
            sys.exit("Annulé — rien n'a été modifié.")

    size_mb = os.path.getsize(source) / (1024 * 1024)
    print(f"Copie de {LANG_ARCHIVE} ({size_mb:.0f} Mo)…")
    shutil.copy2(source, target)
    print(f"Installé : {target}\n"
          "Activez les mods (LayeredFS) dans Azahar, puis connectez le client :\n"
          "il patchera ce fichier automatiquement.")


if __name__ == "__main__":
    main()
