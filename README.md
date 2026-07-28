# Yo-kai Watch 2 : Spectres Psychiques — Archipelago

> **Version 1 — jouable de bout en bout.**
> Toute l'aventure, de la montre disparue jusqu'à Lady Démona, mélangée dans un
> multiworld [Archipelago](https://archipelago.gg).

Version 3DS européenne (FR), sur l'émulateur **Azahar**.
*Le jeu n'est pas fourni : il faut posséder sa propre copie.*

📖 **[Guide d'installation (français)](docs/INSTALLATION_FR.md)** ·
**[Setup guide (English)](docs/INSTALLATION_EN.md)**

---

## Ce qu'on peut faire

Vous jouez l'histoire normalement, mais tout ce que vous trouvez peut appartenir
à un autre joueur — et vos objets à vous sont éparpillés dans les autres mondes.

**Plus de 400 checks**, en français, détectés automatiquement pendant que vous
jouez :

| Catégorie | Nombre | Détail |
|---|---:|---|
| 🎁 **Coffres** | 164 | présent et passé, toutes zones, y compris les égouts, le manoir, les appartements fermés à clé |
| 📜 **Requêtes et services** | 77 | les vraies requêtes du jeu |
| 👹 **Boss** | 23 | histoire **et** boss optionnels de quêtes |
| 🖼️ **Tablo-blabla** | 19 | le check part quand vous écrivez la bonne réponse |
| 📖 **Chapitres** | 11 | chaque chapitre terminé |
| ⌚ **Rangs de montre** | 9 | les requêtes de rang **et** chaque montée de rang |
| 🔑 **Objets-clés** | 20+ | leur emplacement d'origine devient un check |

## Ce qu'on peut recevoir

- Les **objets-clés** de l'aventure (Filet à insectes, Canne à pêche, Clés de
  l'école, Modèle zéro, Indications de Maman, clés d'appartements…) ;
- Les **améliorations de la Yo-kai Watch** (rangs E → S) ;
- Le **Vélo** ;
- Des **objets de combat**, médailles et pièces Crank-a-kai ;
- Des **consommables** en remplissage (nourriture, EXPorbes, soins…).

## Ce qui est vraiment bloqué

Ce n'est pas qu'une affaire de logique : le jeu est **réellement verrouillé**
tant que vous n'avez pas reçu l'objet. Sans les Clés de l'école, l'école reste
fermée. Sans les Indications de Maman, le Centre-ville et le train sont
inaccessibles. Sans le Filet, la Canne à pêche, l'Herbe ancestrale ou le Super
tournevis, l'action correspondante est indisponible.

Le verrouillage est **prudent** : il n'intervient qu'une fois l'événement du jeu
déclenché. Le tutoriel et les scènes d'histoire se déroulent donc normalement,
et rien ne casse que vous receviez l'objet avant ou après.

## Options principales

| Option | Effet |
|---|---|
| `goal` | condition de victoire (par défaut : battre **Lady Démona**) |
| `quest_shuffle` · `chest_shuffle` · `tablo_shuffle` | activer ou non ces catégories de checks |
| `key_item_shuffle` | les objets-clés passent dans le pool multiworld |
| `progressive_watch_rank` | les rangs de montre en objets progressifs |
| `death_link` | quand un joueur tombe au combat, tout le monde tombe |

Tout est commenté directement dans les fichiers YAML fournis.

---

## Tracker inclus

Un pack **PopTracker** complet est fourni dans `tracker/` :

- une **carte détaillée par zone**, avec chaque check placé à son vrai
  emplacement ;
- vos **objets-clés** et votre **rang de montre** en colonne ;
- les compteurs **faits / accessibles / restants** en direct ;
- synchronisation automatique avec le serveur Archipelago ;
- les checks dont l'objet a été **hint** par un autre joueur sont surlignés.

---

## État du projet

**La V1 est complète et testée en jeu** : l'aventure entière est jouable du
début à la fin, les checks partent au bon moment, les objets reçus arrivent
réellement dans l'inventaire, et la victoire est détectée.

Limites connues, sans conséquence sur une partie normale :

- **Yo-criminels** : détection pas assez fiable → laissez `criminel_shuffle` sur
  `false` (c'est la valeur par défaut).
- **Tablo-blabla** : 19 des 26 sont utilisables ; les 7 autres sont exclus
  automatiquement, vous n'avez rien à faire.
- **Post-game** (Tunnel sans fin, Limbes éternelles, Paradis divin) : les zones
  existent mais ne sont pas incluses dans l'objectif « histoire » par défaut.

---

## Contenu du dépôt

| Chemin | Quoi |
|---|---|
| `yokaiwatch2.apworld` | **l'APWorld à installer** dans `custom_worlds/` |
| `Yo-kai Watch 2 - *.yaml` | configurations prêtes à l'emploi (FR, EN, exemple complet) |
| `docs/` | guides d'installation FR et EN |
| `tracker/` | le pack PopTracker |
| `yokaiwatch2/` | le code source de l'APWorld |
| `tools/` | utilitaires de développement (génération du tracker, extraction de données) |

---

## Remerciements

Projet développé par **Doteos**.
Données de jeu issues du guide **Supersoluce** (version française).
