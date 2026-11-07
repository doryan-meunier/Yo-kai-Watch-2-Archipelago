# Guide d'installation : Yo-kai Watch 2 sur Archipelago (V3)

Ce guide explique, pas à pas et sans connaissance technique, comment jouer à **Yo-kai Watch 2** (version européenne, 3DS)
dans un multiworld [Archipelago](https://archipelago.gg), seul ou avec des amis.

> Le jeu n'est **pas fourni**. Il faut posséder sa propre copie et en faire soi-même une ROM déchiffrée. Le mod ne
> contient aucune donnée du jeu : il se construit sur votre ordinateur à partir de votre ROM.

English version: [INSTALLATION_EN.md](INSTALLATION_EN.md)

---

## 1. Ce qu'il vous faut

| Élément | Où l'obtenir |
|---|---|
| Windows 10 ou 11 (64 bits) | pour le lanceur du mod |
| **Archipelago 0.6.7 ou plus** | <https://github.com/ArchipelagoMW/Archipelago/releases> (une seule personne de la partie en a besoin pour générer, mais tous les joueurs peuvent l'avoir) |
| **Un émulateur** | **Zakuro**, fourni avec le lanceur (rien à installer ; il dessine par Vulkan, ou OpenGL si Vulkan ne démarre pas) ; ou **Azahar 2124.3** : <https://github.com/azahar-emu/azahar/releases/tag/2124.3> |
| **Votre ROM** déchiffrée de Yo-kai Watch 2 européen (`.3ds`, `.cci` ou `.cxi`) | à faire avec GodMode9 depuis votre propre cartouche. Version d'origine, sans mise à jour intégrée ni modification. Une ROM « chiffrée » est refusée |
| **L'APWorld de la V3** | [yokaiwatch2.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2.apworld) (noms français) ou [yokaiwatch2en.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2en.apworld) (noms anglais) |
| **Un YAML** | [Yo-kai Watch 2 - FR.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR.yaml) (réglages par défaut) ou [Yo-kai Watch 2 - FR (tout activé).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR%20%28tout%20activ%C3%A9%29.yaml) ; en anglais : [Yo-kai Watch 2 (English) - EN.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN.yaml) ou [Yo-kai Watch 2 (English) - EN (everything on).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN%20%28everything%20on%29.yaml) (clic droit, « Enregistrer le lien sous... ») |
| **Le lanceur du mod** | [ykw2ap-exe-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-exe-3.0.0.zip) (recommandé, aucun Python à installer, Zakuro compris : un clic télécharge le fichier). Variante : [ykw2ap-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-3.0.0.zip), qui demande Python 3.11 ou plus |

Les deux versions de l'APWorld (français et anglais) peuvent jouer dans la **même** partie multiworld. Le lanceur et
le jeu modifié sont les mêmes dans les deux cas.

> **Tous les joueurs Yo-kai Watch 2 d'une partie générée avec l'APWorld de la V3 doivent avoir le lanceur de la V3.**
> Une partie déjà générée avec la V2 se joue aussi avec le lanceur de la V3 (rien n'y change).

---

## 2. Installer l'APWorld dans Archipelago

*(Cette étape concerne la personne qui génère la partie ; chaque joueur peut aussi le faire pour ses propres essais.)*

1. Fermez Archipelago s'il est ouvert.
2. Copiez `yokaiwatch2.apworld` (et/ou `yokaiwatch2en.apworld`) dans le dossier `custom_worlds` d'Archipelago, **à la
   place** de l'APWorld de la V2 s'il y est. Avec l'installation classique sous Windows :
   `C:\ProgramData\Archipelago\custom_worlds\`. Vous pouvez aussi double-cliquer sur le fichier `.apworld` si
   Archipelago est installé normalement.
3. Au prochain lancement d'Archipelago, les jeux « Yo-kai Watch 2 » (français) et « Yo-kai Watch 2 (English) » sont
   reconnus.

---

## 3. Préparer le YAML et générer la partie

1. Choisissez un modèle : **réglages par défaut** (environ 510 locations, tous les verrous réels) ou **« tout
   activé »** (plus de 1 400 locations, avec l'après-jeu jusqu'à Extrabuki). Ouvrez-le avec un éditeur de texte (le
   Bloc-notes suffit). Chaque option y est expliquée : ce que fait chaque valeur, ce qu'elle ajoute comme checks ou
   objets, et ses dépendances.
2. **L'objectif** (option `objectif`) est le premier choix à faire : `finir_chapitre_10` pour une partie de la taille
   de la V2 ; `battre_potofeu`, `battre_filomene` ou `battre_extrabuki` pour ajouter l'après-jeu (réglez alors aussi
   `apres_jeu`) ; `medaillium_complet` pour tout le jeu (une centaine d'heures). Pour composer votre propre profil,
   suivez la ligne « Tout activé » de chaque option. Changez la ligne `name:` si vous voulez un nom de joueur précis.
3. Ne traduisez pas les noms d'options ni de valeurs : chaque monde a les siens. Le YAML français (« Yo-kai Watch 2 »)
   est en français ; le YAML anglais (« Yo-kai Watch 2 (English) ») est entièrement en anglais (`goal`, `bosses`,
   `active_locks`...).
4. Placez le YAML dans le dossier `Players` d'Archipelago (avec ceux des autres joueurs, s'il y en a).
5. Lancez la génération (Archipelago Launcher > « Generate », ou `ArchipelagoGenerate.exe`). Une archive `.zip`
   apparaît dans le dossier `output`.
6. Hébergez la partie, de l'une de ces façons :
   - **En ligne** : envoyez le `.zip` sur <https://archipelago.gg/uploads>, le site donne une adresse et un port à
     partager (le plus simple à plusieurs) ;
   - **En local** : lancez `ArchipelagoServer` avec le `.zip` ; pour que vos amis s'y connectent, il faut ouvrir le
     port 38281 (par défaut) sur votre box.

> Le fichier spoiler de la génération (`..._Spoiler.txt`, si demandé) contient une section Yo-kai Watch 2 : mélange des
> boss, légendaires, ordre des Pièces 5 étoiles, zones des Yo-kai demandés.

---

## 4. Installer et lancer le lanceur

1. Décompressez `ykw2ap-exe-3.0.0.zip` où vous voulez (par exemple dans Documents). Vous pouvez remplacer le
   dossier de la V2 : vos réglages, journaux et sauvegardes de Zakuro sont ailleurs (`%APPDATA%\ykw2-ap`).
2. Double-cliquez sur **`Lanceur Yo-kai Watch 2 Archipelago.exe`**. Gardez le dossier `_internal` (et le dossier
   `zakuro`) **à côté** de l'exe (ne déplacez pas l'exe seul ; pour un raccourci : clic droit sur l'exe, « Créer un
   raccourci »).
3. **Avertissement Windows** : la première fois, Windows peut afficher « Windows a protégé votre ordinateur » (éditeur
   inconnu). C'est normal : le lanceur n'est pas signé (une signature de code est payante). Cliquez sur
   **« Informations complémentaires »**, puis sur **« Exécuter quand même »**. Si votre antivirus bloque le lanceur,
   utilisez la variante `.pyw` ci-dessous.

**Variante Python (`.pyw`)** : installez Python 3.11 ou plus (avec Tcl/Tk, inclus par défaut), décompressez
`ykw2ap-3.0.0.zip`, puis double-cliquez sur `Lanceur Yo-kai Watch 2 Archipelago.pyw`. Le fonctionnement est
identique, sauf pour les mises à jour (voir plus bas).

### Mettre à jour le lanceur

- **Mise à jour automatique (exe)** : au lancement, le lanceur regarde sur le dépôt public du mod si une version plus
  récente existe (une simple demande, aucune donnée envoyée ; case « Vérifier les mises à jour au lancement » dans
  l'onglet « Réglages » → « Paramètres du jeu », cochée par défaut). S'il y en a une, la carte « Mod » de l'onglet
  « Jeu » affiche « Mise à jour disponible » et ses notes. Sauvegardez **en jeu**, fermez le jeu, puis cliquez sur
  **« Mettre à jour »** : le lanceur télécharge le paquet, le vérifie, remplace ses fichiers et redémarre. En cas
  d'échec, l'ancienne version reste en place. Vos réglages, votre connexion et vos sauvegardes sont gardés. Au
  « Jouer » suivant, le mod est réinstallé tout seul (avec Zakuro, seule la partie du jeu qui a changé est préparée
  de nouveau).
- **Variante `.pyw`** : le lanceur signale la nouvelle version avec un bouton « Ouvrir la page » ; téléchargez le
  nouveau zip et décompressez-le à la place de l'ancien.
- **Vous aviez la V2** : son lanceur ne se met pas à jour tout seul. Téléchargez le zip de la V3 ci-dessus et
  décompressez-le (vous pouvez remplacer le dossier de la V2). Une partie générée avec la V2 se continue avec le
  lanceur de la V3 ; si vous la jouiez sur Azahar, gardez Azahar pour elle.

---

## 5. Configurer le lanceur

Dans la fenêtre, les étapes sont numérotées :

1. **ROM du jeu** : cliquez sur **« Choisir... »** et sélectionnez votre ROM. Le lanceur vérifie qu'il s'agit de la
   bonne version. Messages possibles : « chiffrée » (refaites la ROM déchiffrée avec GodMode9), « version non prise en
   charge » (il faut la version européenne, sans mise à jour intégrée ni modification). La ROM sert aussi à calculer,
   chez vous, les mélanges des Yo-kai, des boss et du Bingo-kai : choisissez-la avant de jouer.
2. **Émulateur** :
   - **Zakuro intégré** (par défaut quand il est fourni) : la ligne « Zakuro intégré : le jeu tourne en code PC » s'affiche ; il n'y a
     rien à régler (la liaison avec le jeu est intégrée).
   - **Azahar** : cliquez sur **« Choisir... »** et sélectionnez `azahar.exe`. Azahar doit avoir été **lancé au moins
     une fois** avant. Regardez la ligne « Liaison avec le jeu (stub GDB) » : si elle dit « désactivée », cliquez sur
     **« Activer... »** (Azahar fermé). Le lanceur vous demande votre accord avant de modifier la configuration
     d'Azahar, en fait une **copie de sauvegarde** à côté et ne change que les réglages du stub GDB. Vous pouvez aussi
     le faire vous-même dans Azahar : Émulation > Configurer > Débogage, cocher « Enable GDB Stub ».
   - Pour revenir à Zakuro : « Choisir... » le fichier `zakuro\zakuro.exe` du dossier du lanceur.
3. **Mod** : l'état s'affiche (non installé / à jour / autre version). L'installation se fait toute seule au premier
   « Jouer ». Les boutons « Installer », « Réparer » et « Désinstaller » sont là au besoin ; ils sont refusés si
   l'émulateur est ouvert.

---

## 6. Se connecter à la partie Archipelago

Dans la carte **« Connexion Archipelago »** du lanceur :

- **Serveur** : l'adresse et le port, par exemple `archipelago.gg:38281` ;
- **Nom de slot** : le nom de votre joueur dans la partie (celui du YAML) ;
- **Mot de passe** : seulement si la partie en a un (la case « Mémoriser le mot de passe » le garde, chiffré pour
  votre compte Windows).

Cliquez sur **« Enregistrer »**. Vous pouvez changer ces champs en pleine partie : le client se reconnecte tout seul.
Le lanceur affiche l'état de la connexion, et l'état des mélanges de la partie (Yo-kai, boss). Dès que la connexion
est enregistrée, le suivi (onglets Checks, Discussion, Yo-kai) marche **même sans lancer le jeu**.

---

## 7. Jouer

1. Cliquez sur **« Jouer »**. Le lanceur contrôle tout, installe le mod si besoin, démarre le client invisible, puis
   l'émulateur avec le jeu. Utilisez **toujours « Jouer »**, jamais l'émulateur directement.
2. **Avec Zakuro, la première fois** : « Préparation du jeu pour le PC (recompilation, une seule fois par version du
   mod) : N % ». Le jeu est traduit en code PC sur votre ordinateur : cela prend **quelques minutes** (environ
   4 minutes sur un PC récent, davantage sur un ordinateur plus modeste). La toute première fois, le lanceur peut
   aussi télécharger un compilateur (environ 100 Mo) si l'ordinateur n'en a pas. Le jeu préparé est gardé : les
   lancements suivants démarrent directement, et après une mise à jour du mod, seul ce qui a changé est refait (en
   général moins d'une minute).
3. **Commencez une NOUVELLE partie** du jeu (un emplacement de sauvegarde vide). Elle est **liée automatiquement** à
   la partie Archipelago.
4. Une sauvegarde déjà commencée n'est **jamais utilisée** : le lanceur affiche « Cette sauvegarde n'est pas liée à la
   partie Archipelago : commencez une nouvelle partie. » et rien n'y est reçu ni envoyé. Une sauvegarde liée à une
   **autre** graine est refusée de la même façon.
5. Dans le cadre « État » du lanceur : client, jeu, serveur, et sauvegarde (« liée à cette partie Archipelago » quand
   tout va bien). Si la partie est **en attente** (mélange en préparation, ROM à choisir), suivez le message : elle
   reprend seule.
6. Pendant le jeu, les objets reçus s'affichent par un bandeau, et les checks partent tout seuls.

**Sauvegardes** : Zakuro et Azahar ont chacun leurs sauvegardes (celles de Zakuro sont dans
`%APPDATA%\ykw2-ap\zakuro`). Une partie commencée avec l'un se continue avec le même.

**Réglages de Zakuro** : onglet **« Réglages »** du lanceur, sous-onglet **« Zakuro »** (langue du jeu, résolution de la 3D, interpolation d'images, taille de la fenêtre, disposition des écrans, filtre, volume…), puis « Enregistrer ». Zakuro les lit à son lancement : ils s'appliquent à la prochaine partie lancée par « Jouer ». Ils restent aussi modifiables dans Zakuro (Échap → Settings), avec les touches du clavier et les boutons de la manette (Controls). Zakuro les garde dans `%APPDATA%\zakuro\settings.toml`.

**Sauvegardes rapides (save states) : déconseillées.** Elles sont liées à la version exacte du mod installé ; en
charger une d'un autre build peut faire revenir l'ancien code. Utilisez les sauvegardes **en jeu**. Avant de mettre le
mod à jour, sauvegardez en jeu.

---

## 8. Où trouver le suivi

Le suivi est **dans le lanceur** :

- onglet **Checks** : la liste de vos locations par zone (faites, accessibles, plus tard, bloquées), les objets reçus,
  et une **carte** avec des marqueurs et, si vous cochez « Suivre le jeu », votre position ; rubriques Invitations,
  Pièces spéciales et Légendaires selon les options de la partie ;
- onglet **Yo-kai** : où trouver chaque Yo-kai sauvage, avec le mélange réellement appliqué (lieux « Bingo-kai »,
  « garanti à <zone> ») ; vue « Boss » ; épinglage sur la carte ; filtres ;
- onglet **Discussion** : le client texte d'Archipelago (discussion avec les autres joueurs, `!hint`, `!remaining`...),
  avec un sous-onglet « Indices ».

Aucun spoiler par défaut : le contenu d'un check n'apparaît qu'une fois fait ou s'il a fait l'objet d'un indice.

---

## 9. En cas de problème

| Symptôme | Que faire |
|---|---|
| Le jeu reste sur un **écran noir** | le client n'a pas démarré. Fermez l'émulateur, relancez depuis le lanceur (« Jouer »). |
| « La recompilation du jeu a échoué » (Zakuro) | relancez « Jouer » ; si cela recommence, passez à Azahar (§5) et joignez `client.log` à votre signalement. |
| « Liaison avec le jeu (stub GDB) : désactivée » (Azahar) | cliquez sur « Activer... » (Azahar fermé), ou activez-le dans Azahar. |
| « Cette sauvegarde n'est pas liée... » / « ...appartient à une autre partie Archipelago » | commencez une nouvelle partie sur un emplacement vide. |
| « le jeu installé n'a pas tous les verrous de cette graine » ou « mod trop ancien » | mettez le lanceur à jour (§4) ; cliquez sur « Jouer » (met à jour le mod) ou « Réparer ». |
| « Partie en attente » / « Partie bloquée » (mélange) | suivez le message : souvent, choisir la ROM dans le lanceur puis « Réparer ». |
| Le jeu plante (panique) | le fichier `plantage.json` du dossier des données du client (`%APPDATA%\ykw2-ap`) garde la cause ; joignez-le à votre demande d'aide. |
| Besoin d'aide | bouton **« Journaux »** du lanceur : ouvre le dossier des journaux ; joignez `client.log`. |
| Le mod semble abîmé | bouton **« Réparer »** (désinstalle puis réinstalle). |
| ROM refusée | voir §5, étape 1. |
| La **manette** (PS5 surtout) n'est pas reconnue ou **aucun bouton** ne marche (Zakuro) | double-cliquez sur `zakuro\tester_manette.cmd` (dans le dossier du lanceur) : il montre ce que Zakuro voit de la manette. Si elle y apparaît et que chaque bouton écrit une ligne, Zakuro la lit ; si le jeu ne la suit pas, ou si elle disparaît avec Steam ouvert, quittez **Steam** complètement et réessayez. Sinon : éteignez puis rallumez la manette (ou branchez-la en USB) et relancez le test. Pour quitter Steam : clic droit sur son icône près de l'horloge, « Quitter ». |
| Le jeu n'est **pas en français** (Zakuro) | dans le lanceur, onglet **« Réglages »**, sous-onglet **« Zakuro »** : « Langue du jeu » = Français, « Enregistrer », puis relancez le jeu (ou, dans Zakuro : Échap → Settings → Emulation → Language : French, puis relancez le jeu). |

Message du serveur : « serveur injoignable » (adresse ou port faux, serveur arrêté), « slot inconnu » (nom de slot),
« mot de passe refusé », « mauvais jeu » (le YAML n'est pas pour ce jeu).

---

## 10. Désinstaller

1. Fermez l'émulateur.
2. Dans le lanceur, bouton **« Désinstaller »** : le dossier des mods de l'émulateur redevient comme avant (avec
   Azahar, un autre mod qui s'y trouvait est remis en place ; une traduction ou un autre mod dans `romfs` n'est jamais
   modifié).
3. Supprimez le dossier du lanceur.
4. Vos réglages, journaux et **sauvegardes de Zakuro** sont dans `%APPDATA%\ykw2-ap` : ne supprimez ce dossier que si
   vous ne voulez plus de ces sauvegardes. Zakuro garde aussi le jeu préparé pour le PC dans `%APPDATA%\3dsrecomp` et
   son compilateur dans `%LOCALAPPDATA%\zakuro`, et ses réglages dans `%APPDATA%\zakuro` : vous pouvez les supprimer.
5. Avec Azahar : la copie de sauvegarde de sa configuration faite par le lanceur reste à côté du fichier de
   configuration d'Azahar ; vous pouvez la restaurer, ou désactiver le stub GDB dans Azahar.
