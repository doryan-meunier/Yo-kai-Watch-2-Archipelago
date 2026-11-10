"""Textes de l'onglet « Réglages » (sous-onglets « Paramètres du jeu » et « Zakuro », FR / EN), ajoutés aux
tables de `textes.py` (module séparé : l'onglet évolue sans toucher aux textes des autres écrans)."""
from __future__ import annotations

FR = {
    "onglet_reglages": "Réglages",
    # sous-onglets
    "rz_sous_jeu": "Paramètres du jeu",
    "rz_sous_zakuro": "Zakuro",
    "rz_jeu_titre": "Paramètres du jeu",
    "rz_jeu_note": "Ces paramètres servent avec Azahar comme avec Zakuro et s'appliquent tout de suite.",
    "rz_titre": "Réglages de Zakuro (version PC)",
    "rz_aide_titre": "Comment ils s'appliquent",
    # réglages
    "rz_language": "Langue du jeu",
    "rz_resolution": "Résolution de la 3D",
    "rz_scale": "Taille de la fenêtre",
    "rz_layout": "Écrans",
    "rz_filter": "Filtre de l'image",
    "rz_screen_alignment": "Place des écrans",
    "rz_volume": "Volume",
    "rz_frame_interpolation": "Interpolation d'images (30 → 60 images par seconde)",
    "rz_integer_scale": "Agrandir par nombres entiers seulement (bordure autour des écrans)",
    "rz_mute": "Couper le son",
    "rz_show_fps": "Afficher le nombre d'images par seconde",
    "rz_defaut": "{valeur}, par défaut",
    "rz_fois": "{n}×",
    "rz_resolution_1": "1× (celle de la console)",
    "rz_lang_english": "English (anglais)", "rz_lang_french": "Français", "rz_lang_german": "Deutsch (allemand)",
    "rz_lang_italian": "Italiano (italien)", "rz_lang_spanish": "Español (espagnol)",
    "rz_lang_dutch": "Nederlands (néerlandais)", "rz_lang_russian": "Русский (russe)",
    "rz_lang_japanese": "Japonais (absent du jeu européen)", "rz_lang_chinese_simplified": "Chinois simplifié (absent du jeu)",
    "rz_lang_korean": "Coréen (absent du jeu)", "rz_lang_portuguese": "Portugais (absent du jeu)",
    "rz_lang_chinese_traditional": "Chinois traditionnel (absent du jeu)",
    "rz_layout_stacked": "Haut au-dessus du bas", "rz_layout_side_by_side": "Côte à côte",
    "rz_layout_large_top": "Grand écran du haut, petit écran du bas", "rz_layout_top_only": "Écran du haut seul",
    "rz_layout_bottom_only": "Écran du bas seul",
    "rz_filter_smooth": "Lisse", "rz_filter_sharp": "Net (bords adoucis)", "rz_filter_pixels": "Pixels carrés",
    "rz_screen_alignment_center": "Au centre", "rz_screen_alignment_left": "Collés à gauche (place libre à droite)",
    "rz_screen_alignment_right": "Collés à droite (place libre à gauche)",
    "rz_indice_alignement": "Dans une fenêtre plus large que les écrans, plein écran compris : la place libre peut "
                            "accueillir le lanceur. Le toucher de l'écran du bas suit les écrans. Demande le Zakuro "
                            "fourni avec cette version du mod (un plus ancien ignore ce réglage).",
    "rz_indice_resolution": "Au-delà de ce que montre la fenêtre, les pixels en plus lissent les bords ; le coût "
                            "pour la carte graphique monte vite.",
    "rz_indice_interpolation": "Le jeu tourne à 30 images par seconde : une image intermédiaire est dessinée entre "
                               "deux, il s'affiche à 60, avec 1/60 s de retard.",
    "rz_sans_gpu": "Le rendu 3D par la carte graphique est désactivé dans Zakuro : la résolution et l'interpolation "
                   "n'ont pas d'effet.",
    "rz_sans_vulkan": "Zakuro est réglé sur OpenGL : l'interpolation d'images demande Vulkan (réglage de Zakuro).",
    # boutons
    "rz_enregistrer": "Enregistrer",
    "rz_annuler": "Annuler",
    "rz_defauts": "Valeurs par défaut",
    # états
    "rz_fichier": "Fichier : {chemin}",
    "rz_etat_lu": "Réglages lus dans le fichier de Zakuro.",
    "rz_etat_absent": "Pas encore de fichier : valeurs par défaut de Zakuro (le fichier sera créé à l'enregistrement).",
    "rz_etat_modifie": "Modifications non enregistrées.",
    "rz_etat_enregistre": "Enregistré : appliqué au prochain lancement de Zakuro.",
    "rz_etat_rien": "Rien à enregistrer : le fichier a déjà ces valeurs.",
    "rz_etat_ouvert": "Enregistré. Zakuro est ouvert : le changement s'appliquera à son prochain lancement. D'ici là, "
                      "ne changez pas ses réglages dans sa fenêtre (ni F9 / F10) : il réécrirait le fichier avec ses "
                      "anciennes valeurs.",
    "rz_etat_change": "Le fichier a été modifié par Zakuro pendant que vous changiez le formulaire : seuls les "
                      "réglages que vous avez changés seront écrits.",
    "rz_hors_bornes": "Certains réglages du fichier sont hors de ce que propose le lanceur ({cles}) : ils restent tels "
                      "quels tant que vous n'y touchez pas.",
    "rz_rejete": "Zakuro ne peut pas lire une valeur de ce fichier : il utilisera ses valeurs par défaut (fichier "
                 "mis de côté en settings.toml.bad).",
    "rz_err_chemin": "Dossier des réglages introuvable (variable APPDATA absente).",
    "rz_err_lecture": "Le fichier des réglages de Zakuro ne peut pas être lu.",
    "rz_err_illisible": "Le fichier des réglages de Zakuro est illisible : le lanceur n'y écrit pas. Réglez Zakuro "
                        "dans sa fenêtre (Échap → Settings) ou supprimez le fichier.",
    "rz_err_valeur": "Valeur refusée.",
    "rz_err_controle": "Écriture annulée : le fichier relu ne correspondait pas à l'attendu (rien n'a été changé).",
    "rz_err_ecriture": "Le fichier des réglages de Zakuro ne peut pas être écrit.",
    # aide (carte de droite)
    "rz_aide_lancement": "Zakuro lit ses réglages à son lancement : un changement enregistré ici s'applique à la "
                         "prochaine partie lancée par « Jouer ».",
    "rz_aide_fenetre": "Les mêmes réglages restent modifiables dans Zakuro : Échap → Settings.",
    "rz_aide_touches": "Pendant le jeu : Échap ouvre le menu de Zakuro, F1 met en pause, F9 passe à la disposition "
                       "d'écrans suivante, F10 entre l'écran du haut et celui du bas seuls, F11 bascule le plein "
                       "écran.",
    "rz_aide_controles": "Touches du clavier et boutons de la manette : à régler dans Zakuro (Échap → Settings → "
                         "Controls).",
    "rz_aide_azahar": "Ces réglages ne servent qu'à Zakuro (le lanceur utilise Azahar en ce moment).",
    "rz_aide_sans_zakuro": "Zakuro n'est pas fourni avec ce lanceur : ces réglages ne servent qu'à un Zakuro installé "
                           "à part.",
}

EN = {
    "onglet_reglages": "Settings",
    # sub-tabs
    "rz_sous_jeu": "Game settings",
    "rz_sous_zakuro": "Zakuro",
    "rz_jeu_titre": "Game settings",
    "rz_jeu_note": "These settings work with Azahar as well as with Zakuro and apply right away.",
    "rz_titre": "Zakuro settings (PC version)",
    "rz_aide_titre": "How they apply",
    "rz_language": "Game language",
    "rz_resolution": "3D resolution",
    "rz_scale": "Window size",
    "rz_layout": "Screens",
    "rz_filter": "Picture filter",
    "rz_screen_alignment": "Screens' place",
    "rz_volume": "Volume",
    "rz_frame_interpolation": "Frame interpolation (30 → 60 frames per second)",
    "rz_integer_scale": "Scale by whole numbers only (border around the screens)",
    "rz_mute": "Mute",
    "rz_show_fps": "Show the frame rate",
    "rz_defaut": "{valeur}, default",
    "rz_fois": "{n}×",
    "rz_resolution_1": "1× (the console's)",
    "rz_lang_english": "English", "rz_lang_french": "Français (French)", "rz_lang_german": "Deutsch (German)",
    "rz_lang_italian": "Italiano (Italian)", "rz_lang_spanish": "Español (Spanish)",
    "rz_lang_dutch": "Nederlands (Dutch)", "rz_lang_russian": "Русский (Russian)",
    "rz_lang_japanese": "Japanese (not in the European game)",
    "rz_lang_chinese_simplified": "Simplified Chinese (not in the game)",
    "rz_lang_korean": "Korean (not in the game)", "rz_lang_portuguese": "Portuguese (not in the game)",
    "rz_lang_chinese_traditional": "Traditional Chinese (not in the game)",
    "rz_layout_stacked": "Top over bottom", "rz_layout_side_by_side": "Side by side",
    "rz_layout_large_top": "Big top screen, small bottom one", "rz_layout_top_only": "Top screen only",
    "rz_layout_bottom_only": "Bottom screen only",
    "rz_filter_smooth": "Smooth", "rz_filter_sharp": "Sharp (soft edges)", "rz_filter_pixels": "Square pixels",
    "rz_screen_alignment_center": "Centered", "rz_screen_alignment_left": "Against the left edge (room on the right)",
    "rz_screen_alignment_right": "Against the right edge (room on the left)",
    "rz_indice_alignement": "In a window wider than the screens, full screen included: the free room can hold the "
                            "launcher. Touching the bottom screen follows the screens. Needs the Zakuro that comes "
                            "with this version of the mod (an older one ignores this setting).",
    "rz_indice_resolution": "Past what the window shows, the extra pixels smooth the edges; the cost to the graphics "
                            "card grows fast.",
    "rz_indice_interpolation": "The game runs at 30 frames per second: a frame is drawn in between each two, so it "
                               "shows at 60, a 60th of a second late.",
    "rz_sans_gpu": "Drawing the 3D on the graphics card is off in Zakuro: resolution and interpolation have no effect.",
    "rz_sans_vulkan": "Zakuro is set to OpenGL: frame interpolation needs Vulkan (a Zakuro setting).",
    "rz_enregistrer": "Save",
    "rz_annuler": "Cancel",
    "rz_defauts": "Default values",
    "rz_fichier": "File: {chemin}",
    "rz_etat_lu": "Settings read from Zakuro's file.",
    "rz_etat_absent": "No file yet: Zakuro's default values (the file will be created when you save).",
    "rz_etat_modifie": "Unsaved changes.",
    "rz_etat_enregistre": "Saved: applied the next time Zakuro starts.",
    "rz_etat_rien": "Nothing to save: the file already has these values.",
    "rz_etat_ouvert": "Saved. Zakuro is open: the change will apply the next time it starts. Until then, do not change "
                      "its settings in its window (nor F9 / F10): it would write the file again with its old values.",
    "rz_etat_change": "Zakuro changed the file while you were editing the form: only the settings you changed will "
                      "be written.",
    "rz_hors_bornes": "Some settings in the file are outside what the launcher offers ({cles}): they stay as they are "
                      "unless you change them.",
    "rz_rejete": "Zakuro cannot read a value in this file: it will use its default values (file kept aside as "
                 "settings.toml.bad).",
    "rz_err_chemin": "Settings folder not found (no APPDATA variable).",
    "rz_err_lecture": "Zakuro's settings file cannot be read.",
    "rz_err_illisible": "Zakuro's settings file is unreadable: the launcher does not write to it. Set Zakuro up in its "
                        "window (Esc → Settings) or delete the file.",
    "rz_err_valeur": "Value refused.",
    "rz_err_controle": "Writing cancelled: the file read back was not what was expected (nothing was changed).",
    "rz_err_ecriture": "Zakuro's settings file cannot be written.",
    "rz_aide_lancement": "Zakuro reads its settings when it starts: a change saved here applies to the next game "
                         "started with \"Play\".",
    "rz_aide_fenetre": "The same settings can still be changed in Zakuro: Esc → Settings.",
    "rz_aide_touches": "While playing: Esc opens Zakuro's menu, F1 pauses, F9 switches to the next screen layout, F10 "
                       "between the top and the bottom screen alone, F11 toggles full screen.",
    "rz_aide_controles": "Keyboard keys and controller buttons: set them in Zakuro (Esc → Settings → Controls).",
    "rz_aide_azahar": "These settings are only for Zakuro (the launcher is using Azahar right now).",
    "rz_aide_sans_zakuro": "Zakuro does not come with this launcher: these settings are only for a Zakuro installed "
                           "separately.",
}
