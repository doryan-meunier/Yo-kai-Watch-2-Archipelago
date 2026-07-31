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
| **Azahar** (émulateur 3DS) — **version 2124.3 recommandée** | https://github.com/azahar-emu/azahar/releases/tag/2124.3 |
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
| `encounter_shuffle` | au choix | **randomizer** : mélange les Yo-kai sauvages (voir §8) |
| `boss_encounter_shuffle` | au choix | mélange les boss entre eux (voir §8) |

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

> ⚠️ **Version d'Azahar : la 2124.3 est recommandée.** Les versions 2125.x se
> sont montrées instables avec le client (le stub GDB ne répond plus pendant
> que le jeu tourne : micro-freezes puis déconnexions en boucle) ; la 2126
> réécrit entièrement le stub et n'est pas encore testée. En cas de
> déconnexions répétées, installer la 2124.3 règle le problème.

1. Dans **Azahar** : *Émulation → Configurer → Debug*, cochez
   **« Enable GDB stub »** et laissez le port sur **24689**.
2. **Relancez le jeu** pour que le réglage prenne effet.
3. Le jeu **se fige au démarrage** : c'est normal — avec le stub activé, il
   attend le débogueur. C'est la commande `/citra` du client (étape suivante)
   qui le libère.
4. Une fois le jeu débloqué, **chargez votre sauvegarde** : le client ne livre
   aucun objet tant qu'une partie n'est pas chargée.

---

## 6. Lancer le client et jouer

1. Ouvrez **ArchipelagoLauncher** → **Yo-kai Watch 2 Client**.
2. Connectez-vous au serveur (adresse et port), avec le **nom de slot** = le
   `name:` de votre YAML.
3. Dans le client, tapez **`/citra`** puis Entrée — c'est ce qui **débloque le
   jeu** figé au démarrage.
   - Message attendu : *« Attaché au stub GDB (port 24689) »*.
4. Chargez votre sauvegarde et jouez normalement ! Vos checks partent tout seuls, et les objets reçus
   apparaissent en jeu.

### En cas de souci

| Symptôme | Solution |
|---|---|
| *« Connexion au stub GDB impossible »* | Le stub n'est pas activé, ou le jeu n'a pas été relancé après l'avoir coché. Vérifiez aussi qu'aucun autre programme n'utilise le port 24689. |
| *« Connexion émulateur perdue »* | Retapez `/citra`. Si c'est refusé, faites une sauvegarde d'état, redémarrez le jeu dans Azahar, rechargez l'état, puis `/citra`. |
| Rien ne se passe / aucun check | Vérifiez qu'une sauvegarde est bien **chargée** (pas l'écran-titre) et que `/citra` a été fait. |
| Ralentissements en jeu | Vérifiez le message au `/citra` : *« Lectures sans pause ACTIVES »* signifie que tout va bien. |
| *« ROM introuvable »* | Indiquez votre `.3ds` au client : `/rom <chemin complet>`. |
| *« ROM non modifiable »* | Déplacez la ROM hors de `Program Files` (Windows y interdit l'écriture), puis rouvrez-la dans Azahar. |
| Un coffre affiche encore l'objet d'origine | Le jeu tournait pendant le patch : relancez-le (la ROM est lue au démarrage). |

---

## 7. Ce que vous verrez en jeu (affichage des objets AP)

Le client modifie le jeu à la **connexion au serveur** pour que ce que vous
trouvez corresponde à ce qui est réellement placé dans le multiworld :

- **Coffres** : le coffre affiche **et donne** l'objet du multiworld. Votre
  propre objet apparaît tel quel ; l'objet d'un autre joueur apparaît comme
  « **Item AP** » (il disparaît ensuite tout seul, le vrai objet part à son
  destinataire).
- **Objets-clés** : la plupart des obtentions affichent aussi « Item AP ».
  Cinq dons d'histoire (Filet, Herbe ancestrale, Modèle zéro, Clé de derrière,
  Indications de Maman) gardent leur visuel d'origine — le check et la
  livraison restent corrects, seul le popup ment une seconde.

Pour cela, le client écrit directement dans votre ROM `.3ds` (voir les
prérequis du §8 : ROM déchiffrée, dossier accessible en écriture). D'où
l'ordre conseillé : **connectez le client d'abord, lancez le jeu ensuite** —
la ROM est lue au démarrage du jeu.

---

## 8. Randomizer de Yo-kai (optionnel)

Trois options du YAML mélangent les Yo-kai du jeu, avec la seed de la partie
(tous les joueurs d'une même seed voient le même mélange) :

```yaml
encounter_shuffle: true          # mélange les Yo-kai sauvages de chaque zone
boss_encounter_shuffle: true     # mélange les combats de BOSS entre eux (mécaniques préservées)
encounter_levels: keep_location  # keep_location = le niveau reste sur place (conseillé)
                                 # follow_yokai  = le niveau suit le Yo-kai (chaotique)
```

**Prérequis** : une ROM `.3ds` **déchiffrée**, dans un dossier accessible en
écriture (**pas** `C:\Program Files`). Le client la trouve tout seul via les
fichiers récents d'Azahar ; sinon indiquez-la avec `/rom <chemin du .3ds>`.

Le patch s'applique à la **connexion au serveur** : le client vous demande
alors de **relancer le jeu**. Les reconnexions suivantes ne réécrivent rien.

Bon à savoir :

- des petits fichiers `*.ykw2*.json` apparaissent à côté de la ROM — ce sont
  les données d'**annulation**, ne les supprimez pas ;
- `/unrandomize` restaure la ROM d'origine à tout moment ;
- changer de seed restaure d'abord la ROM, puis applique le nouveau mélange —
  rien ne s'empile.

---

## 9. Le tracker (optionnel mais conseillé)

1. Installez **PopTracker** : https://github.com/black-sliver/PopTracker/releases
2. Copiez le dossier `tracker/ykw2-poptracker` dans le dossier `packs/` de
   PopTracker.
3. Ouvrez PopTracker, choisissez le pack, puis connectez-le au serveur
   Archipelago (bouton **AP**) avec le même nom de slot.

Vous aurez les cartes de chaque zone avec tous les checks positionnés, vos
objets-clés, votre rang de montre, et les compteurs mis à jour en direct.
Les checks dont l'objet a été « hint » par un autre joueur sont surlignés.

---

## 10. Bon à savoir

- **Sauvegardez régulièrement en jeu** : les checks sont détectés en mémoire
  vive, mais votre progression, elle, dépend de la sauvegarde du jeu.
- **Ne lancez pas d'autre outil de débogage** (scanner mémoire, autre client…)
  pendant que le client tourne : le débogueur d'Azahar n'accepte **qu'une seule
  connexion** à la fois.
- Si vous jouez **hors ligne** un moment, reconnectez simplement le client
  ensuite : il rattrape les checks manqués au chargement de la partie.
