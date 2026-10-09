# Yo-kai Watch 2 : Archipelago, version 2

Version 3DS européenne (EUR), sur l'émulateur **Azahar**, dans un multiworld [Archipelago](https://archipelago.gg).
**Le jeu n'est pas fourni** : il faut posséder sa propre copie et en tirer sa propre ROM déchiffrée. Le mod ne contient
aucune donnée du jeu : il se construit chez vous, à partir de votre ROM.

[Français](#français) | [English](#english)

---

## Français

La V2 **remplace** la V1. Ce n'est pas une mise à jour de l'ancien client : le mod a été entièrement refait. Le jeu
lui-même est maintenant modifié (un patch de son programme, appliqué chez vous par le lanceur), et ce
sont les fonctions du jeu qui donnent les objets, remplacent le contenu des coffres et signalent les checks. Le client ne fait que
relayer. Plus de fichier « déjà livré », plus de différences d'inventaire devinées de l'extérieur : l'état est dans la
sauvegarde du jeu.

**Guides d'installation** : [français](docs/INSTALLATION_FR.md) · [English](docs/INSTALLATION_EN.md)
**Notes de version** : [français](PATCHNOTES_FR.md) · [English](PATCHNOTES_EN.md)

### Ce qu'il faut

- Windows 10 ou 11 (64 bits) pour le lanceur.
- **Azahar** (émulateur 3DS), version **2124.3** (seule version validée).
- **Archipelago 0.6.7 ou plus**, pour générer la partie.
- **Votre propre ROM** déchiffrée de Yo-kai Watch 2 européen (`.3ds`, `.cci` ou `.cxi`), faite avec GodMode9 depuis votre
  cartouche. Version européenne d'origine, sans mise à jour intégrée ni modification.
- Les fichiers de ce dépôt : un APWorld (`yokaiwatch2.apworld` en français, `yokaiwatch2en.apworld` en anglais), un
  YAML modèle, et le lanceur du mod (dossier `lanceur/`).

### Ce qu'on peut faire

Vous jouez l'histoire normalement, mais ce que vous trouvez peut appartenir à un autre joueur, et vos objets sont
éparpillés dans les autres mondes. Avec **tous les types de checks activés**, une partie compte **environ 1 060
locations** (chiffres approximatifs, tirés d'une génération « tout activé » ; les défauts en donnent bien moins, voir
le YAML) :

| Catégorie | Environ | Détail |
|---|---:|---|
| Coffres dorés | 253 | présent et passé ; dont 36 ajoutés par le verrou des rangs de montre (dont la Clinique du Crépuscule) |
| Amis | 290 | un check par Yo-kai devenu ami : sauvages, évolutions, fusions, Yo-kai d'histoire, d'évènement, des armées, invités de l'Auberge |
| Boutiques | 285 | le premier achat de chaque article retenu (boutiques payées en euros) |
| Requêtes | 73 | les requêtes de l'histoire et facultatives (hors rang de montre : 3 de plus) |
| Services | 16 | les services tirés au hasard par le jeu |
| Yo-criminels | 52 | un check par criminel arrêté |
| Tablo-blabla | 25 | le check part quand le Yo-kai du panneau est appelé |
| Boss | 29 | en mode « tous » (12 d'histoire, 11 de quête, 6 de plus) |
| Objets-clés | 22 | leur emplacement d'origine devient un check |
| Chapitres | 9 | chaque chapitre 1 à 9 terminé (le chapitre 10 est la victoire) |

### Ce qu'on reçoit

Les objets-clés de l'aventure (Filet à insectes, Canne à pêche, Clés de l'école, Modèle zéro, Indications de Maman,
Herbe ancestrale, Super tournevis, Pile ou passe...), les **rangs de montre** (D, C, B, A, en objets progressifs), le
**Vélo**, les objets des Yo-kai d'évènement (Rouages, Graines, Grelots, Marque d'Ultramax, Capsule favorite), des
**invitations** (voir plus bas), et des objets de remplissage (nourriture, argent...).

### Les verrous sont réels

Ce n'est pas qu'une affaire de logique : avec le verrou activé, **le jeu refuse vraiment l'action** tant que l'objet n'est pas
arrivé. Sans le Filet, les points de recherche à la loupe sont inutilisables. Sans les Clés de l'école, l'école reste fermée.
Sans le Vélo, pas de vélo. Sans la Canne, pas de pêche. Sans le rang de montre, les portes de montre restent closes et
l'histoire attend. Les verrous sont posés avec prudence (ils respectent les scènes déjà jouées) et la génération est
vérifiée par un audit qui joue la logique du jeu sur 200 graines pour éviter les parties bloquées. Liste complète des verrous
et de leurs effets : commentaires du YAML (`verrous_actifs`).

### Le lanceur

Une fenêtre, un bouton « Jouer ». Le lanceur (fourni en `.exe` : **aucun Python à installer**) :

- vérifie votre ROM, installe le mod dans le dossier de mods d'Azahar (un patch produit chez vous, jamais le jeu), active
  avec votre accord la « liaison avec le jeu » d'Azahar, lance le client puis le jeu ;
- se connecte au serveur Archipelago (adresse, nom du slot, mot de passe saisis dans le lanceur) ;
- contient le **suivi intégré** (qui remplace l'ancien pack PopTracker) : onglet **Checks** (liste par zone, **carte** avec
  votre position dans le jeu, objets reçus, rubrique Invitations), onglet **Yo-kai** (où trouver chaque Yo-kai, épinglage sur
  la carte, jour / nuit / météo, nourriture préférée, facilité d'amitié, boutiques), onglet **Discussion** (client texte
  d'Archipelago : discussion, commandes `!hint`, indices) ;
- est disponible en français et en anglais.

### Et aussi

- **Liaison des sauvegardes** : une partie Archipelago se joue sur une **nouvelle** partie, liée automatiquement. Une
  sauvegarde déjà commencée, ou liée à une autre graine, est refusée (rien n'y est reçu ni envoyé).
- **Mélange des Yo-kai** : les Yo-kai sauvages de chaque rencontre changent, avec des garanties pour ne jamais vous
  bloquer ; le lanceur dit où trouver chacun. **Mélange des boss** (en option).
- **Invités de l'Auberge** : 30 Yo-kai d'avant la fin que le jeu ne garantit pas arrivent à l'Auberge des voyageurs quand
  vous recevez leur « Invitation » ; Jibanyan S, Komasan S et Komajiro S, Hovernyan, Ultramax N et K apparaissent à leur place d'origine.
- **Bingo-kai infini**, Yo-criminels trouvables à volonté, combats « du jour » rejouables.
- **DeathLink** (option), fenêtres « objet obtenu » et bandeaux « Reçu : ... » sans interrompre le jeu.

### À savoir

- Les **boutiques** et le **mélange des boss** sont désactivés dans les réglages par défaut : activez-les dans le YAML.
- Le lanceur n'est **pas signé** : Windows (SmartScreen) peut afficher un avertissement au premier lancement.
- N'utilisez pas de sauvegardes rapides (« save states ») d'Azahar avec ce mod : elles sont liées à la version exacte du mod installé.
- Windows seulement pour le lanceur. Seul Azahar 2124.3 est validé.

Si vous trouvez un problème, joignez le fichier `client.log` du dossier des journaux (bouton « Journaux » du lanceur).

### Contenu du dépôt

| Chemin | Quoi |
|---|---|
| `yokaiwatch2.apworld` | l'APWorld **français** (jeu « Yo-kai Watch 2 ») |
| `yokaiwatch2en.apworld` | l'APWorld **anglais** (jeu « Yo-kai Watch 2 (English) ») |
| `Yo-kai Watch 2 - FR.yaml` | YAML modèle, noms français, commentaires détaillés FR + EN |
| `Yo-kai Watch 2 (English) - EN.yaml` | YAML modèle, noms anglais, commentaires détaillés FR + EN |
| `docs/` | guides d'installation FR et EN |
| `PATCHNOTES_FR.md`, `PATCHNOTES_EN.md` | tout ce qui change par rapport à la V1 |
| `lanceur/` | le lanceur : `ykw2ap-exe-2.0.0.zip` (sans Python, recommandé) et `ykw2ap-2.0.0.zip` (nécessite Python 3.11+) |

Les deux mondes (français et anglais) peuvent jouer dans la **même** multiworld.

### Remerciements

Logo du mod (six cercles d'Archipelago) : MDarkmooN. Projet développé par **Doteos**.

---

## English

V2 **replaces** V1. It is not an update of the old client: the mod was rebuilt from scratch. The game itself is now patched
(a patch of its executable, applied on your machine by the launcher), and the game's own functions give the items, replace
chest contents and report the checks. The client only relays. No more "already delivered" file, no more inventory
differences guessed from outside: the state lives in the game's save.

**Setup guides**: [English](docs/INSTALLATION_EN.md) · [Français](docs/INSTALLATION_FR.md)
**Patch notes**: [English](PATCHNOTES_EN.md) · [Français](PATCHNOTES_FR.md)

*The game is not provided*: you need your own copy and your own decrypted ROM. The mod contains no game data: it is built on
your machine from your ROM.

### What you need

- Windows 10 or 11 (64-bit) for the launcher.
- **Azahar** (3DS emulator), version **2124.3** (the only validated version).
- **Archipelago 0.6.7 or later**, to generate the game.
- **Your own** decrypted ROM of the European Yo-kai Watch 2 (`.3ds`, `.cci` or `.cxi`), dumped with GodMode9 from your
  cartridge. Original European version, no merged update, no modification.
- The files of this repository: an APWorld (`yokaiwatch2.apworld` for French names, `yokaiwatch2en.apworld` for English
  names), a template YAML, and the mod launcher (`lanceur/` folder).

### What you can do

You play the story normally, but what you find may belong to another player, and your own items are scattered across the other
worlds. With **every check type enabled**, a game has **about 1,060 locations** (approximate figures from an "everything
on" generation; the defaults give far fewer, see the YAML):

| Category | About | Details |
|---|---:|---|
| Golden chests | 253 | present and past; including 36 added by the watch-rank lock (Nocturne Hospital among them) |
| Friends | 290 | one check per Yo-kai befriended: wild, evolutions, fusions, story, event and army Yo-kai, Wayfarer Manor guests |
| Shops | 285 | the first purchase of each selected item (shops paid in money) |
| Requests | 73 | story and optional requests (3 more for the watch-rank ones) |
| Services | 16 | the services the game draws at random |
| Yo-criminals | 52 | one check per criminal arrested |
| Baffle Boards | 25 | sent when the board's Yo-kai is called |
| Bosses | 29 | in "all" mode (12 story, 11 quest, 6 more) |
| Key items | 22 | their original spot becomes a check |
| Chapters | 9 | each of chapters 1 to 9 completed (chapter 10 is the goal) |

### What you receive

The adventure's key items (Bug Net, Fishing Rod, School Keys, Model Zero, Mom's Directions, Ancient Herb, Pro Screwdriver,
Select-A-Coin...), **watch ranks** (D, C, B, A, as progressive items), the **Bicycle**, the event Yo-kai items (Cogs, Seeds, Bells,
Moxie Mark, Favorite Capsule), **invitations** (see below), and filler (food, money...).

### Locks are real

It is not only a logic matter: with a lock enabled, **the game really refuses the action** until the item arrives. Without the Bug
Net, lens search points are unusable. Without the School Keys, the school stays closed. Without the Bicycle, no bicycle. Without
the Rod, no fishing. Without the watch rank, watch doors stay shut and the story waits. Locks are laid with care (they respect
scenes already played) and generation is checked by an audit that plays the game's logic over 200 seeds to avoid unwinnable
games. Full list of locks and effects: the YAML comments (`verrous_actifs`).

### The launcher

One window, one "Play" button. The launcher (shipped as an `.exe`: **no Python to install**):

- checks your ROM, installs the mod into Azahar's mods folder (a patch produced on your machine, never the game), enables
  Azahar's "link with the game" with your consent, starts the client, then the game;
- connects to the Archipelago server (address, slot name and password typed in the launcher);
- includes the **built-in tracker** (replacing the old PopTracker pack): **Checks** tab (list by area, **map** with your position
  in the game, received items, Invitations section), **Yo-kai** tab (where to find each Yo-kai, pin on the map, day / night /
  weather, favorite food, befriending odds, shops), **Chat** tab (Archipelago's text client: chat, `!hint` commands, hints);
- is available in French and English.

### And also

- **Save linking**: an Archipelago game is played on a **new** game, linked automatically. A save that was already started, or
  linked to another seed, is refused (nothing is received or sent).
- **Yo-kai randomizer**: wild Yo-kai of every encounter change, with guarantees that never block you; the launcher tells where
  to find each one. **Boss randomizer** (optional).
- **Wayfarer Manor guests**: 30 pre-ending Yo-kai the game does not guarantee arrive at the Manor when you receive their
  "Invitation"; Jibanyan S, Komasan S and Komajiro S, Hovernyan, Ultramax N and K appear at their original places.
- **Endless Crank-a-kai**, Yo-criminals findable at will, "of the day" battles replayable.
- **DeathLink** (option), "item obtained" windows and "Received: ..." banners without interrupting the game.

### Good to know

- **Shops** and the **boss randomizer** are off in the default settings: turn them on in the YAML.
- The launcher is **not signed**: Windows (SmartScreen) may show a warning on first launch.
- Do not use Azahar save states with this mod: they are tied to the exact installed mod version.
- Windows only for the launcher. Only Azahar 2124.3 is validated.

If you find a problem, attach the `client.log` file from the logs folder (the launcher's "Logs" button).

### Repository contents

| Path | What |
|---|---|
| `yokaiwatch2.apworld` | the **French** APWorld (game "Yo-kai Watch 2") |
| `yokaiwatch2en.apworld` | the **English** APWorld (game "Yo-kai Watch 2 (English)") |
| `Yo-kai Watch 2 - FR.yaml` | template YAML, French names, detailed FR + EN comments |
| `Yo-kai Watch 2 (English) - EN.yaml` | template YAML, English names, detailed FR + EN comments |
| `docs/` | setup guides, FR and EN |
| `PATCHNOTES_FR.md`, `PATCHNOTES_EN.md` | everything that changes from V1 |
| `lanceur/` | the launcher: `ykw2ap-exe-2.0.0.zip` (no Python, recommended) and `ykw2ap-2.0.0.zip` (needs Python 3.11+) |

Both worlds (French and English) can play in the **same** multiworld.

### Credits

Mod logo (six-circle Archipelago logo): MDarkmooN. Project developed by **Doteos**.
