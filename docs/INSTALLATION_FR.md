# Guide d'installation — Yo-kai Watch 2 sur Archipelago

Ce guide explique comment jouer à **Yo-kai Watch 2 : Spectres Psychiques**
dans un multiworld [Archipelago](https://archipelago.gg), seul ou avec des amis.

> **Version du jeu supportée : 3DS européenne (FR)**, jouée sur l'émulateur
> **Azahar**. Le jeu n'est pas fourni : il faut posséder sa propre copie.

---

## 1. Ce qu'il vous faut

| Élément | Où l'obtenir |
|---|---|
| **Archipelago** 0.5.0 ou plus | https://github.com/ArchipelagoMW/Archipelago/releases |
| **Azahar** (émulateur 3DS) | https://azahar-emu.org |
| Votre copie de **Yo-kai Watch 2 : Spectres Psychiques** (EU/FR) | — |
| **`yokaiwatch2.apworld`** | ce dépôt (à la racine) |
| Un fichier **YAML** de configuration | ce dépôt (voir §3) |
| *(optionnel)* le pack **PopTracker** | ce dépôt, dossier `tracker/` |

---

## 2. Installer l'APWorld

1. Fermez Archipelago s'il est ouvert.
2. Copiez **`yokaiwatch2.apworld`** dans le dossier `custom_worlds/` de votre
   installation Archipelago.
   - Windows (installation classique) : `C:\ProgramData\Archipelago\custom_worlds\`
3. C'est tout — au prochain lancement, le jeu « Yo-kai Watch 2 » sera reconnu.

---

## 3. Préparer sa configuration (YAML)

Prenez l'un des fichiers fournis à la racine du dépôt :

- **`Yo-kai Watch 2 - Histoire FR.yaml`** — recommandé pour commencer
  (toute l'histoire jusqu'à Lady Démona, commentaires en français) ;
- **`Yo-kai Watch 2 - Story EN.yaml`** — même chose, commentaires en anglais
  (le jeu reste **« Yo-kai Watch 2 »**, donc les noms de checks sont en français).

> Pour jouer avec les noms de checks et d'objets **en anglais**, c'est un autre
> apworld : voir [INSTALLATION_EN.md](INSTALLATION_EN.md). Les deux versions
> peuvent participer au **même multiworld**.

Ouvrez-le dans un éditeur de texte et changez au minimum la ligne `name:` par
votre pseudo. Les options sont commentées directement dans le fichier.

### Réglages conseillés

| Option | Valeur conseillée | Pourquoi |
|---|---|---|
| `quest_shuffle` | `true` | les requêtes et services deviennent des checks |
| `chest_shuffle` | `true` | chaque coffre devient un check |
| `tablo_shuffle` | `true` | 19 Tablo-blabla jouables (les autres sont exclus d'office) |
| `criminel_shuffle` | **`false`** | ⛔ détection pas assez fiable, peut bloquer la partie |
| `death_link` | au choix | si un joueur tombe, tout le monde tombe |

> ⚠️ **Ne désactivez jamais `quest_shuffle` ET `chest_shuffle` en même temps** :
> il ne resterait pas assez de checks et la génération échouerait.

Placez ensuite votre YAML dans le dossier `Players/` d'Archipelago.

---

## 4. Générer et héberger la partie

1. Lancez **ArchipelagoGenerate** (ou `ArchipelagoLauncher` → *Generate*).
2. Une archive `.zip` apparaît dans `output/`.
3. Deux façons de jouer :
   - **En ligne** : envoyez le `.zip` sur https://archipelago.gg/uploads —
     le site vous donne une adresse et un port à partager (le plus simple à
     plusieurs) ;
   - **En local** : lancez `ArchipelagoServer` avec le `.zip`. Pour que vos amis
     s'y connectent, il faudra ouvrir le port (38281 par défaut) sur votre box.

---

## 5. Activer le lien avec l'émulateur

Le client lit la mémoire du jeu via le débogueur intégré d'Azahar.

1. Dans **Azahar** : *Émulation → Configurer → Debug*, cochez
   **« Enable GDB stub »** et laissez le port sur **24689**.
2. **Relancez le jeu** pour que le réglage prenne effet.
3. Lancez le jeu et **chargez votre sauvegarde** (important : le client a besoin
   d'une partie chargée, pas de l'écran-titre).

---

## 6. Lancer le client et jouer

1. Ouvrez **ArchipelagoLauncher** → **Yo-kai Watch 2 Client**.
2. Connectez-vous au serveur (adresse et port), avec le **nom de slot** = le
   `name:` de votre YAML.
3. Dans le client, tapez **`/citra`** puis Entrée.
   - Message attendu : *« Attaché au stub GDB (port 24689) »*.
4. Jouez normalement ! Vos checks partent tout seuls, et les objets reçus
   apparaissent en jeu.

### En cas de souci

| Symptôme | Solution |
|---|---|
| *« Connexion au stub GDB impossible »* | Le stub n'est pas activé, ou le jeu n'a pas été relancé après l'avoir coché. Vérifiez aussi qu'aucun autre programme n'utilise le port 24689. |
| *« Connexion émulateur perdue »* | Retapez `/citra`. Si c'est refusé, faites une sauvegarde d'état, redémarrez le jeu dans Azahar, rechargez l'état, puis `/citra`. |
| Rien ne se passe / aucun check | Vérifiez qu'une sauvegarde est bien **chargée** (pas l'écran-titre) et que `/citra` a été fait. |
| Ralentissements en jeu | Vérifiez le message au `/citra` : *« Lectures sans pause ACTIVES »* signifie que tout va bien. |

---

## 7. Le tracker (optionnel mais conseillé)

1. Installez **PopTracker** : https://github.com/black-sliver/PopTracker/releases
2. Copiez le dossier `tracker/ykw2-poptracker` dans le dossier `packs/` de
   PopTracker.
3. Ouvrez PopTracker, choisissez le pack, puis connectez-le au serveur
   Archipelago (bouton **AP**) avec le même nom de slot.

Vous aurez les cartes de chaque zone avec tous les checks positionnés, vos
objets-clés, votre rang de montre, et les compteurs mis à jour en direct.
Les checks dont l'objet a été « hint » par un autre joueur sont surlignés.

---

## 8. Bon à savoir

- **Sauvegardez régulièrement en jeu** : les checks sont détectés en mémoire
  vive, mais votre progression, elle, dépend de la sauvegarde du jeu.
- **Ne lancez pas d'autre outil de débogage** (scanner mémoire, autre client…)
  pendant que le client tourne : le débogueur d'Azahar n'accepte **qu'une seule
  connexion** à la fois.
- Si vous jouez **hors ligne** un moment, reconnectez simplement le client
  ensuite : il rattrape les checks manqués au chargement de la partie.
