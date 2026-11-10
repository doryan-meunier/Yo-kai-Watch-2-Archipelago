# Yo-kai Watch 2 : Archipelago, version 3

Version 3DS européenne (EUR), dans un multiworld [Archipelago](https://archipelago.gg), sur l'émulateur **Zakuro**
(fourni) ou **Azahar**. **Le jeu n'est pas fourni** : il faut posséder sa propre copie et en tirer sa propre ROM
déchiffrée. Le mod ne contient aucune donnée du jeu : il se construit chez vous, à partir de votre ROM.

[Français](#français) | [English](#english)

---

## Français

Version actuelle : **3.0.0**. La V3 remplace la V2.

**Guides d'installation** : [français](docs/INSTALLATION_FR.md) · [English](docs/INSTALLATION_EN.md)
**Notes de version** : [français](PATCHNOTES_FR.md) · [English](PATCHNOTES_EN.md)

**Transparence** : mod écrit avec une IA, code source et licence MIT : voir [plus bas](#transparence--usage-de-lia-contenu-code-source).

### Téléchargements

Un clic sur un lien lance le téléchargement :

| Fichier | Lien |
|---|---|
| Lanceur du mod (recommandé, aucun Python à installer, Zakuro compris) | [ykw2ap-exe-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-exe-3.0.0.zip) |
| Lanceur du mod, variante Python 3.11+ | [ykw2ap-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-3.0.0.zip) |
| APWorld français | [yokaiwatch2.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2.apworld) |
| APWorld anglais | [yokaiwatch2en.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2en.apworld) |
| YAML modèle français, réglages par défaut | [Yo-kai Watch 2 - FR.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR.yaml) |
| YAML modèle français, tout activé | [Yo-kai Watch 2 - FR (tout activé).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR%20%28tout%20activ%C3%A9%29.yaml) |
| YAML modèle anglais, réglages par défaut | [Yo-kai Watch 2 (English) - EN.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN.yaml) |
| YAML modèle anglais, tout activé | [Yo-kai Watch 2 (English) - EN (everything on).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN%20%28everything%20on%29.yaml) |

Pour un YAML, si le navigateur l'affiche au lieu de le télécharger : clic droit sur le lien, « Enregistrer le lien
sous... ».

### Ce qu'est la V3

Vous jouez l'histoire normalement, mais ce que vous trouvez peut appartenir à un autre joueur, et vos objets sont
éparpillés dans les autres mondes. Le jeu lui-même est modifié chez vous par le lanceur : les verrous sont **réels**
(le jeu refuse vraiment l'action tant que l'objet n'est pas reçu). Par rapport à la V2, la V3 ajoute :

- l'**après-jeu** et de nouveaux **objectifs** : battre Potofeu, Filomène ou Extrabuki, ou compléter le Médaillium ;
- le mode **Blasters** (terrains de Ψ Blasters en checks, et un objet par terrain au choix) ;
- de **nouveaux objets-clés et verrous** (Yo-kai Watch, Abonnement de train, Voyage dans le temps, Miroirs et Mirapo
  de poche, objets des requêtes du chapitre 5...), un 5e Rang de montre pour le rang S, les **requêtes à transfert**
  sans transfert ;
- les **pièces spéciales** du Crank-a-kai, les **légendaires mélangés**, le **Bingo-kai aléatoire**, les **zones des
  Yo-kai demandés** ;
- un **mélange des Yo-kai** bien plus large, les **boss d'après-jeu** mélangés (Voie du mystère comprise) et une
  **force des boss adaptée** ;
- les **distributeurs** de soda et de nouvelles **boutiques** en checks ;
- des **pièges** (au choix), un **multiplicateur d'XP**, des **objets de départ** choisis dans le YAML ;
- des options de **confort** (Tunnel sans fin et revanches sans limite de jour, chance d'amitié, train doré,
  remplissage et argent réglables) ;
- une **version PC** : Zakuro, fourni avec le lanceur, fait tourner le jeu en code PC ;
- un lanceur plus complet : carte du suivi, onglet Yo-kai, fenêtres d'amitié et de la loupe, apparence du héros,
  musique aléatoire, **mise à jour automatique**.

Le détail est dans les [notes de version](PATCHNOTES_FR.md) et dans les commentaires des YAML.

### Ce qu'il faut

- Windows 10 ou 11 (64 bits).
- **Archipelago 0.6.7 ou plus**, pour générer la partie.
- **Votre propre ROM** déchiffrée de Yo-kai Watch 2 européen (`.3ds`, `.cci` ou `.cxi`), faite avec GodMode9 depuis
  votre cartouche (version d'origine, sans mise à jour intégrée ni modification).
- Un émulateur : **Zakuro** est fourni avec le lanceur (il dessine par Vulkan, ou OpenGL si Vulkan ne démarre pas) ;
  **Azahar 2124.3** reste possible.

### Installer (résumé)

1. Copiez l'APWorld (`yokaiwatch2.apworld` en français, `yokaiwatch2en.apworld` en anglais) dans le dossier
   `custom_worlds` d'Archipelago, à la place de celui de la V2.
2. Prenez un YAML modèle (réglages par défaut, ou « tout activé »), choisissez l'objectif, générez la partie.
3. Décompressez le lanceur (`ykw2ap-exe-3.0.0.zip`), lancez `Lanceur Yo-kai Watch 2 Archipelago.exe`, choisissez votre
   ROM, saisissez la connexion Archipelago, puis « Jouer ». Avec Zakuro, la première partie commence par une
   préparation du jeu pour le PC (quelques minutes, environ 4 sur un PC récent) ; le jeu préparé est gardé, les
   lancements suivants démarrent directement.
4. Commencez une **nouvelle** partie du jeu : elle se lie toute seule.

Tout est expliqué pas à pas dans le [guide d'installation](docs/INSTALLATION_FR.md).

### Mettre à jour

- Le lanceur (exe) regarde au démarrage si une version plus récente est publiée ici et propose de se mettre à jour
  (onglet « Jeu », carte « Mod », bouton « Mettre à jour »). Sauvegardez en jeu et fermez le jeu avant.
- **Depuis la V2** : le lanceur de la V2 ne se met pas à jour tout seul. Téléchargez le lanceur de la V3 ci-dessus et
  remplacez l'APWorld dans `custom_worlds`.
- Une partie générée avec la V2 reste jouable avec le lanceur de la V3 (rien n'y change). Une partie générée avec
  l'APWorld de la V3 demande le lanceur de la V3 pour tous les joueurs Yo-kai Watch 2 de la partie.
- Sauvegardez **en jeu** ; n'utilisez pas les sauvegardes rapides (« save states ») : elles sont liées à la version
  exacte du mod installé.

### Signaler un bug

**[Ouvrir un ticket](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/issues/new/choose)** (« Issues ») sur ce dépôt : un formulaire vous guide. Préparez :

1. **Ce qui s'est passé** : ce que vous faisiez, ce que vous attendiez, ce qui est arrivé ; le chapitre et l'endroit
   du jeu ; si cela se reproduit.
2. **Le fichier `client.log`** : bouton **« Journaux »** du lanceur (il ouvre le dossier des journaux,
   `%APPDATA%\ykw2-ap`) ; joignez aussi **`plantage.json`** s'il existe (il est écrit quand le jeu plante).
3. **Une capture de l'onglet concerné** du lanceur (onglet « Jeu » pour l'état et la connexion, « Checks » pour un
   check ou un objet, « Yo-kai » pour le mélange, « Discussion » pour un message du serveur) et, si possible, de
   l'écran du jeu.
4. **Les versions** affichées en bas du lanceur (« Lanceur ... - mod ... »), l'émulateur utilisé (Zakuro ou Azahar),
   et le **YAML** de la partie.
5. Si c'est un blocage, une **sauvegarde en jeu** juste avant le problème aide beaucoup.

### Contenu du dépôt

| Chemin | Quoi |
|---|---|
| `yokaiwatch2.apworld` | l'APWorld **français** de la V3 (jeu « Yo-kai Watch 2 ») |
| `yokaiwatch2en.apworld` | l'APWorld **anglais** de la V3 (jeu « Yo-kai Watch 2 (English) ») |
| `Yo-kai Watch 2 - FR.yaml` | YAML modèle du monde français : réglages par défaut, tous les verrous |
| `Yo-kai Watch 2 - FR (tout activé).yaml` | YAML modèle du monde français : tout activé (après-jeu jusqu'à Extrabuki) |
| `Yo-kai Watch 2 (English) - EN.yaml` | YAML modèle du monde anglais (entièrement en anglais) : réglages par défaut |
| `Yo-kai Watch 2 (English) - EN (everything on).yaml` | YAML modèle du monde anglais : tout activé |
| `docs/` | guides d'installation FR et EN |
| `PATCHNOTES_FR.md`, `PATCHNOTES_EN.md` | tout ce qui change par rapport à la V2 |
| `source/` | le code source du lanceur, du client et des APWorlds (voir « Transparence ») |
| `LICENSE` | licence MIT |
| `lanceur/` | le lanceur : `ykw2ap-exe-3.0.0.zip` (sans Python, recommandé, avec Zakuro), `ykw2ap-3.0.0.zip` (nécessite Python 3.11+) et `maj.json` (lu par la mise à jour automatique) |

### Transparence : usage de l'IA, contenu, code source

- **IA** : presque tout le code et la documentation de ce mod (lanceur, client, APWorlds et patch du jeu) ont été
  écrits avec une IA (**Claude**, d'Anthropic), sous ma direction. Je décide de ce que fait le mod, j'essaie chaque
  fonction en jeu, et une bêta avec des testeurs a précédé la sortie. Je ne suis pas développeur professionnel ;
  le support et les corrections se font avec les mêmes outils.
- **Contenu** : un lanceur et un client Archipelago (Python), deux APWorlds (français et anglais), un patch du code du
  jeu **fabriqué chez le joueur** à partir de sa propre ROM, et une version adaptée de l'émulateur Zakuro (licence MIT).
  Aucune donnée du jeu n'est distribuée.
- **Sur votre ordinateur**, le lanceur : installe le patch dans le dossier de mods de l'émulateur (« Désinstaller » le
  remet exactement comme avant), active la liaison GDB de l'émulateur seulement avec votre accord (pour dialoguer
  avec le jeu), se connecte au serveur Archipelago que vous indiquez, et vérifie sur ce dépôt s'il existe une mise à
  jour du lanceur.
- **Code source** : le dossier [`source/`](source/) contient exactement les fichiers du lanceur `ykw2ap-3.0.0.zip`
  (lanceur, client, APWorlds, installation), plus les modifications apportées à Zakuro (`source/zakuro/patches/`).
  Seul le code source du patch du jeu n'est pas publié, parce qu'il est tiré du code du jeu lui-même ; le patch
  est distribué sous forme de différences (`.bps`) contrôlées pour ne contenir aucun octet du jeu.
- **Licence** : MIT (voir [`LICENSE`](LICENSE)), pour le code de ce projet.
### Ancienne version (V2 2.0.3)

Une partie de la V2 déjà générée se joue aussi avec le lanceur de la V3. Les fichiers de la V2 ne sont plus
proposés ici ; ils restent seulement dans l'étiquette [`v2.0.3`](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/tree/v2.0.3).

### Remerciements

Logo du mod (six cercles d'Archipelago) : MDarkmooN. Zakuro (émulateur 3DS, licence MIT) :
<https://github.com/fearkov/zakuro>, fourni ici dans une version adaptée au mod.
Projet développé par **Doteos**.

---

## English

Current version: **3.0.0**. V3 replaces V2.

**Setup guides**: [English](docs/INSTALLATION_EN.md) · [Français](docs/INSTALLATION_FR.md)
**Patch notes**: [English](PATCHNOTES_EN.md) · [Français](PATCHNOTES_FR.md)

**Disclosure**: mod written with AI, source code and MIT licence: see [below](#disclosure-ai-use-contents-source-code).

### Downloads

One click on a link starts the download:

| File | Link |
|---|---|
| Mod launcher (recommended, no Python to install, Zakuro included) | [ykw2ap-exe-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-exe-3.0.0.zip) |
| Mod launcher, Python 3.11+ variant | [ykw2ap-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-3.0.0.zip) |
| English APWorld | [yokaiwatch2en.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2en.apworld) |
| French APWorld | [yokaiwatch2.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2.apworld) |
| English template YAML, default settings | [Yo-kai Watch 2 (English) - EN.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN.yaml) |
| English template YAML, everything on | [Yo-kai Watch 2 (English) - EN (everything on).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN%20%28everything%20on%29.yaml) |
| French template YAML, default settings | [Yo-kai Watch 2 - FR.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR.yaml) |
| French template YAML, everything on | [Yo-kai Watch 2 - FR (tout activé).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR%20%28tout%20activ%C3%A9%29.yaml) |

For a YAML, if the browser shows it instead of downloading it: right-click the link, "Save link as...".

### What V3 is

You play the story normally, but what you find may belong to another player, and your own items are scattered across
the other worlds. The game itself is modified on your machine by the launcher: locks are **real** (the game truly
refuses the action until the item is received). Compared with V2, V3 adds:

- the **postgame** and new **goals**: defeat Wobblewok, Kat Kraydel or Kabuking, or complete the Medallium;
- the **Blasters** mode (Psychic Blasters stages as checks, and one item per stage if you want);
- **new key items and locks** (Yo-kai Watch, Train Pass, Time Travel, Mirapo and the Pocket Mirapo, the chapter 5
  request items...), a 5th Watch Rank for rank S, the **save-transfer requests** without any transfer;
- the **special Crank-a-kai coins**, **shuffled legendaries**, **shuffled Crank-a-kai**, **requested Yo-kai zones**;
- a much wider **Yo-kai shuffle**, shuffled **postgame bosses** (Mystery Way included) and **adapted boss strength**;
- **vending machines** and new **shops** as checks;
- **traps** (optional), an **EXP multiplier**, **starting items** chosen in the YAML;
- **comfort** options (Infinite Tunnel and rematches without the daily limit, befriending chance, golden train,
  adjustable filler and money);
- a **PC version**: Zakuro, shipped with the launcher, runs the game as PC code;
- a richer launcher: tracker map, Yo-kai tab, friendship and magnifier windows, hero appearance, random music,
  **automatic updates**.

Details are in the [patch notes](PATCHNOTES_EN.md) and in the YAML comments.

### What you need

- Windows 10 or 11 (64-bit).
- **Archipelago 0.6.7 or later**, to generate the game.
- **Your own** decrypted ROM of the European Yo-kai Watch 2 (`.3ds`, `.cci` or `.cxi`), dumped with GodMode9 from your
  cartridge (original version, no merged update, no modification).
- An emulator: **Zakuro** is shipped with the launcher (it draws through Vulkan, or OpenGL where Vulkan does not
  start); **Azahar 2124.3** is still possible.

### Install (summary)

1. Copy the APWorld (`yokaiwatch2en.apworld` for English names, `yokaiwatch2.apworld` for French names) into
   Archipelago's `custom_worlds` folder, replacing the V2 one.
2. Take a template YAML (default settings, or "everything on"), pick the goal, generate the game.
3. Unzip the launcher (`ykw2ap-exe-3.0.0.zip`), run `Lanceur Yo-kai Watch 2 Archipelago.exe`, pick your ROM, enter the
   Archipelago connection, then "Play". With Zakuro, the first game starts with preparing the game for PC (a few
   minutes, about 4 on a recent PC); the prepared game is kept, later launches start directly.
4. Start a **new** game: it links by itself.

Everything is explained step by step in the [setup guide](docs/INSTALLATION_EN.md).

### Updating

- At startup, the launcher (exe) checks whether a newer version is published here and offers to update itself
  ("Game" tab, "Mod" card, "Update" button). Save in the game and close it first.
- **Coming from V2**: the V2 launcher does not update itself. Download the V3 launcher above and replace the APWorld in
  `custom_worlds`.
- A game generated with V2 can still be played with the V3 launcher (nothing changes in it). A game generated with the
  V3 APWorld needs the V3 launcher for every Yo-kai Watch 2 player of the multiworld.
- Save **in the game**; do not use save states: they are tied to the exact installed mod version.

### Reporting a bug

**[Open an issue](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/issues/new/choose)** in this repository: a form guides you. Have ready:

1. **What happened**: what you were doing, what you expected, what happened; the chapter and the place in the game;
   whether it happens again.
2. **The `client.log` file**: the launcher's **"Logs"** button (it opens the logs folder, `%APPDATA%\ykw2-ap`); also
   attach **`plantage.json`** if it exists (it is written when the game crashes).
3. **A screenshot of the relevant tab** of the launcher ("Game" for the status and connection, "Checks" for a check or
   an item, "Yo-kai" for the shuffle, "Chat" for a server message) and, if possible, of the game screen.
4. **The versions** shown at the bottom of the launcher ("Launcher ... - mod ..."), the emulator used (Zakuro or
   Azahar), and the game's **YAML**.
5. For a softlock, an **in-game save** made just before the problem helps a lot.

### Repository contents

| Path | What |
|---|---|
| `yokaiwatch2.apworld` | the V3 **French** APWorld (game "Yo-kai Watch 2") |
| `yokaiwatch2en.apworld` | the V3 **English** APWorld (game "Yo-kai Watch 2 (English)") |
| `Yo-kai Watch 2 - FR.yaml` | template YAML of the French world: default settings, every lock |
| `Yo-kai Watch 2 - FR (tout activé).yaml` | template YAML of the French world: everything on (postgame up to Kabuking) |
| `Yo-kai Watch 2 (English) - EN.yaml` | template YAML of the English world (entirely in English): default settings |
| `Yo-kai Watch 2 (English) - EN (everything on).yaml` | template YAML of the English world: everything on |
| `docs/` | setup guides, EN and FR |
| `PATCHNOTES_EN.md`, `PATCHNOTES_FR.md` | everything that changes from V2 |
| `source/` | source code of the launcher, client and APWorlds (see "Disclosure") |
| `LICENSE` | MIT licence |
| `lanceur/` | the launcher: `ykw2ap-exe-3.0.0.zip` (no Python, recommended, with Zakuro), `ykw2ap-3.0.0.zip` (needs Python 3.11+) and `maj.json` (read by the automatic update) |

### Disclosure: AI use, contents, source code

- **AI**: almost all of the code and documentation of this mod (launcher, client, APWorlds and game patch) was written
  with an AI (**Claude**, by Anthropic), under my direction. I decide what the mod does, I test every feature in game,
  and a beta with testers came before the release. I am not a professional developer; support and fixes are done
  with the same tools.
- **Contents**: a launcher and an Archipelago client (Python), two APWorlds (French and English), a patch for the
  game's code that is **built on the player's machine** from their own ROM, and an adapted build of the Zakuro
  emulator (MIT licence). No game data is distributed.
- **On your machine**, the launcher: installs the patch into the emulator's mods folder ("Uninstall" restores it
  exactly), enables the emulator's GDB stub only with your consent (to talk to the game), connects to the Archipelago
  server you enter, and checks this repository for launcher updates.
- **Source code**: the [`source/`](source/) folder holds exactly the files of the `ykw2ap-3.0.0.zip` launcher
  (launcher, client, APWorlds, installation), plus the changes made to Zakuro (`source/zakuro/patches/`). Only the
  source of the game patch is not published, because it is derived from the game's own code; the patch is
  distributed as differences (`.bps`) checked to contain no byte of the game.
- **Licence**: MIT (see [`LICENSE`](LICENSE)), for this project's code.
### Previous version (V2 2.0.3)

An already generated V2 game can also be played with the V3 launcher. The V2 files are no longer offered here; they
only remain in the [`v2.0.3`](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/tree/v2.0.3) tag.

### Credits

Mod logo (six-circle Archipelago logo): MDarkmooN. Zakuro (3DS emulator, MIT licence):
<https://github.com/fearkov/zakuro>, shipped here in a version adapted to the mod.
Project developed by **Doteos**.
