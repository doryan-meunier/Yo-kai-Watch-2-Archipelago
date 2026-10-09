# Guide d'installation : Yo-kai Watch 2 sur Archipelago (V2)

Ce guide explique, pas à pas et sans connaissance technique, comment jouer à **Yo-kai Watch 2** (version européenne, 3DS) dans un
multiworld [Archipelago](https://archipelago.gg), seul ou avec des amis.

> Le jeu n'est **pas fourni**. Il faut posséder sa propre copie et en faire soi-même une ROM déchiffrée. Le mod ne contient aucune
> donnée du jeu : il se construit sur votre ordinateur à partir de votre ROM.

English version: [INSTALLATION_EN.md](INSTALLATION_EN.md)

---

## 1. Ce qu'il vous faut

| Élément | Où l'obtenir |
|---|---|
| Windows 10 ou 11 (64 bits) | pour le lanceur du mod |
| **Archipelago 0.6.7 ou plus** | <https://github.com/ArchipelagoMW/Archipelago/releases> (une seule personne de la partie en a besoin pour générer, mais tous les joueurs peuvent l'avoir) |
| **Azahar 2124.3** (émulateur 3DS) | <https://github.com/azahar-emu/azahar/releases/tag/2124.3> (seule version validée) |
| **Votre ROM** déchiffrée de Yo-kai Watch 2 européen (`.3ds`, `.cci` ou `.cxi`) | à faire avec GodMode9 depuis votre propre cartouche. Version d'origine, sans mise à jour intégrée ni modification. Une ROM « chiffrée » est refusée |
| **L'APWorld** | `yokaiwatch2.apworld` (noms français) ou `yokaiwatch2en.apworld` (noms anglais), à la racine de ce dépôt |
| **Un YAML** | `Yo-kai Watch 2 - FR.yaml` ou `Yo-kai Watch 2 (English) - EN.yaml`, à la racine de ce dépôt |
| **Le lanceur du mod** | dossier [`lanceur/`](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/tree/main/lanceur) de ce dépôt : le fichier `ykw2ap-exe-2.0.0.zip` (recommandé, aucun Python à installer). Variante : `ykw2ap-2.0.0.zip`, qui demande Python 3.11 ou plus |

Les deux versions de l'APWorld (français et anglais) peuvent jouer dans la **même** partie multiworld. Le lanceur et le patch du jeu sont les
mêmes dans les deux cas.

---

## 2. Installer l'APWorld dans Archipelago

*(Cette étape concerne la personne qui génère la partie ; chaque joueur peut aussi le faire pour ses propres tests.)*

1. Fermez Archipelago s'il est ouvert.
2. Copiez `yokaiwatch2.apworld` (et/ou `yokaiwatch2en.apworld`) dans le dossier `custom_worlds` d'Archipelago. Avec l'installation
   classique sous Windows : `C:\ProgramData\Archipelago\custom_worlds\`. Vous pouvez aussi double-cliquer sur le fichier `.apworld` si
   Archipelago est installé normalement.
3. Au prochain lancement d'Archipelago, les jeux « Yo-kai Watch 2 » (français) et « Yo-kai Watch 2 (English) » sont reconnus.

---

## 3. Préparer le YAML et générer la partie

1. Ouvrez le YAML de votre choix avec un éditeur de texte (le Bloc-notes suffit). Chaque option y est expliquée en français **et** en
   anglais : ce que fait chaque valeur, ce qu'elle ajoute comme checks ou objets, et ses dépendances.
2. Les réglages fournis sont les **réglages par défaut**. Pour le profil « tout activé » (environ 1 060 locations), suivez la ligne « Tout
   activé » de chaque option. Changez la ligne `name:` si vous voulez un nom de joueur précis.
3. Ne traduisez pas les noms d'options ni de valeurs : ils restent en français dans les deux versions.
4. Placez le YAML dans le dossier `Players` d'Archipelago (avec ceux des autres joueurs, s'il y en a).
5. Lancez la génération (Archipelago Launcher > « Generate », ou `ArchipelagoGenerate.exe`). Une archive `.zip` apparaît dans le dossier
   `output`.
6. Hébergez la partie, de l'une de ces façons :
   - **En ligne** : envoyez le `.zip` sur <https://archipelago.gg/uploads>, le site donne une adresse et un port à partager (le plus
     simple à plusieurs) ;
   - **En local** : lancez `ArchipelagoServer` avec le `.zip` ; pour que vos amis s'y connectent, il faut ouvrir le port 38281 (par défaut) sur
     votre box.

> Si le client refuse une partie, c'est qu'elle exige un verrou absent de votre paquet du mod : prenez le lanceur le plus récent de la
> dossier `lanceur/` de ce dépôt (voir §9).

---

## 4. Installer et lancer le lanceur

1. Téléchargez le `.zip` du lanceur dans le dossier `lanceur/` de ce dépôt (`ykw2ap-exe-2.0.0.zip`) et **décompressez-le** où vous voulez (par exemple dans
   Documents).
2. Double-cliquez sur **`Lanceur Yo-kai Watch 2 Archipelago.exe`**. Gardez le dossier `_internal` **à côté** de l'exe (ne déplacez pas
   l'exe seul ; pour un raccourci : clic droit sur l'exe, « Créer un raccourci »).
3. **Avertissement Windows** : la première fois, Windows peut afficher « Windows a protégé votre ordinateur » (éditeur inconnu). C'est
   normal : le lanceur n'est pas signé (une signature de code est payante). Cliquez sur **« Informations complémentaires »**, puis sur
   **« Exécuter quand même »**. Si votre antivirus bloque le lanceur, utilisez la variante `.pyw` ci-dessous.

**Variante Python (`.pyw`)** : installez Python 3.11 ou plus (avec Tcl/Tk, inclus par défaut), décompressez `ykw2ap-2.0.0.zip`, puis
double-cliquez sur `Lanceur Yo-kai Watch 2 Archipelago.pyw`. Le fonctionnement est identique.

---

## 5. Configurer le lanceur

Dans la fenêtre, les étapes sont numérotées :

1. **ROM du jeu** : cliquez sur **« Choisir... »** et sélectionnez votre ROM. Le lanceur vérifie qu'il s'agit de la bonne version. Messages
   possibles : « chiffrée » (refaites la ROM déchiffrée avec GodMode9), « version non prise en charge » (il faut la version européenne,
   sans mise à jour intégrée ni modification).
2. **Azahar** : il est en général trouvé tout seul ; sinon, **« Choisir... »** et sélectionnez `azahar.exe`. Azahar doit avoir été **lancé au
   moins une fois** avant. Regardez la ligne « Liaison avec le jeu (stub GDB) » :
   - si elle dit « activée », c'est bon ;
   - si elle dit « désactivée », cliquez sur **« Activer... »**. Le lanceur vous demande votre accord avant de modifier la configuration
     d'Azahar : il en fait une **copie de sauvegarde** à côté, et ne change que les réglages du stub GDB. **Azahar doit être fermé** à ce
     moment. Vous pouvez aussi le faire vous-même dans Azahar : Émulation > Configurer > Débogage, cocher « Enable GDB Stub ».
3. **Mod** : l'état s'affiche (non installé / à jour / autre version). L'installation se fait toute seule au premier « Jouer » (jusqu'à une
   minute). Les boutons « Installer », « Réparer » et « Désinstaller » sont là au besoin ; ils sont refusés si Azahar est ouvert.

---

## 6. Se connecter à la partie Archipelago

Dans la carte **« Connexion Archipelago »** du lanceur :

- **Serveur** : l'adresse et le port, par exemple `archipelago.gg:38281` ;
- **Nom de slot** : le nom de votre joueur dans la partie (celui du YAML) ;
- **Mot de passe** : seulement si la partie en a un (la case « Mémoriser le mot de passe » le garde, chiffré pour votre compte Windows).

Cliquez sur **« Enregistrer »**. Vous pouvez changer ces champs en pleine partie : le client se reconnecte tout seul. Le lanceur affiche
l'état de la connexion. Dès que la connexion est enregistrée, le suivi (onglets Checks, Discussion, Yo-kai) marche **même sans lancer le
jeu**.

---

## 7. Jouer

1. Cliquez sur **« Jouer »**. Le lanceur contrôle tout, installe le mod si besoin, démarre le client invisible, puis Azahar avec le jeu.
   Utilisez **toujours « Jouer »**, jamais Azahar directement.
2. **Commencez une NOUVELLE partie** du jeu (un emplacement de sauvegarde vide). Elle est **liée automatiquement** à la partie Archipelago.
3. Une sauvegarde déjà commencée n'est **jamais utilisée** : le lanceur affiche « Cette sauvegarde n'est pas liée à la partie Archipelago :
   commencez une nouvelle partie. » et rien n'y est reçu ni envoyé. Une sauvegarde liée à une **autre** graine est refusée de la même
   façon. Il n'y a pas de liaison manuelle d'une ancienne sauvegarde.
4. Dans le cadre « État » du lanceur : client, jeu, serveur, et sauvegarde (« liée à cette partie Archipelago » quand tout va bien).
5. Pendant le jeu, les objets reçus s'affichent par un bandeau, et les checks partent tout seuls.

**Sauvegardes rapides (save states) d'Azahar : déconseillées.** Elles sont liées à la version exacte du mod installé ; en charger une
d'un autre build peut faire revenir l'ancien code. Utilisez les sauvegardes **en jeu**. Si vous mettez le mod à jour, sauvegardez en jeu
avant.

---

## 8. Où trouver le suivi

Le suivi est **dans le lanceur** (plus de PopTracker) :

- onglet **Checks** : la liste de vos locations par zone (faites, accessibles, plus tard, bloquées), les objets reçus, et une **carte** avec
  des marqueurs et, si vous cochez « Suivre le jeu », votre position ;
- onglet **Yo-kai** : où trouver chaque Yo-kai sauvage, avec le mélange réellement appliqué ; épinglage sur la carte ; filtres ;
- onglet **Discussion** : le client texte d'Archipelago (messages en couleurs, discussion avec les autres joueurs, `!hint`,
  `!remaining`...), avec un sous-onglet « Indices ».

Aucun spoiler par défaut : le contenu d'un check n'apparaît qu'une fois fait ou s'il a fait l'objet d'un indice.

---

## 9. En cas de problème

| Symptôme | Que faire |
|---|---|
| Le jeu reste sur un **écran noir** | le client n'a pas démarré. Fermez Azahar, relancez depuis le lanceur (« Jouer »). |
| « Liaison avec le jeu (stub GDB) : désactivée » | cliquez sur « Activer... » (Azahar fermé), ou activez-le dans Azahar. |
| « Cette sauvegarde n'est pas liée... » / « ...appartient à une autre partie Archipelago » | commencez une nouvelle partie sur un emplacement vide. |
| « jeu à mettre à jour (mod trop ancien) » ou « le jeu installé n'a pas tous les verrous de cette graine » | récupérez le lanceur le plus récent dans le dossier `lanceur/` de ce dépôt ; cliquez sur « Jouer » (met à jour le mod) ou « Réparer ». |
| Une fenêtre parle de **mémoire insuffisante** | votre ordinateur est probablement saturé : fermez les autres programmes (navigateur, jeux...) et relancez. *(Cause supposée, non vérifiée pour tous les cas.)* |
| Le jeu plante (panique) | le fichier `plantage.json` du dossier des données du client (`%APPDATA%\ykw2-ap`) garde la cause ; joignez-le à votre demande d'aide. |
| Besoin d'aide | bouton **« Journaux »** du lanceur : ouvre le dossier des journaux ; joignez `client.log`. |
| Le mod semble abîmé | bouton **« Réparer »** (désinstalle puis réinstalle). |
| ROM refusée | voir §5, étape 1. |

Message du serveur : « serveur injoignable » (adresse ou port faux, serveur arrêté), « slot inconnu » (nom de slot), « mot de passe refusé »,
« mauvais jeu » (le YAML n'est pas pour ce jeu).

---

## 10. Désinstaller

1. Fermez Azahar.
2. Dans le lanceur, bouton **« Désinstaller »** : le dossier des mods d'Azahar redevient exactement comme avant (un autre mod qui s'y trouvait
   est remis en place ; une traduction ou un autre mod dans `romfs` n'est jamais modifié).
3. Supprimez le dossier du lanceur. Vos réglages et journaux sont dans `%APPDATA%\ykw2-ap`, à supprimer si vous le souhaitez.
4. La copie de sauvegarde de la configuration d'Azahar faite par le lanceur reste à côté du fichier de configuration d'Azahar ; vous
   pouvez la restaurer si vous voulez désactiver le stub GDB, ou le désactiver dans Azahar.
