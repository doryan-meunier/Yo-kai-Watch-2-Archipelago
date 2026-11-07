# Notes de version : V3 (version 3.0.0, par rapport à la V2)

La V3 ajoute l'**après-jeu**, de nouveaux objectifs, beaucoup de nouveaux objets-clés et verrous, de nouveaux types de
checks et de nouveaux mélanges. Tout ce qui est nouveau est **réglable dans le YAML** ; les réglages par défaut
restent proches de la V2. Ce document liste les nouveautés par thème.

Deux modèles de YAML par langue sont fournis : les **réglages par défaut** (avec tous les verrous réels) et un modèle
**« tout activé »** (plus de 1 400 locations). Les listes y sont écrites en tableau (`[a, b]`), et chaque option est
expliquée dans le fichier.

## Compatibilité

- **Une partie générée avec la V2 reste jouable avec le lanceur de la V3** : le lanceur la reconnaît et n'y ajoute
  rien (mêmes checks, même mélange des Yo-kai et des boss, mêmes invités ; aucune nouveauté de la V3 ne s'y active).
  Sauvegardez **en jeu** avant de mettre le lanceur à jour (pas de sauvegarde rapide « save state » d'un autre
  build). Si vous jouiez sur Azahar, gardez Azahar pour cette partie (voir « Version PC » plus bas : les sauvegardes
  de Zakuro sont à part).
- **Une partie générée avec l'APWorld de la V3 demande le lanceur de la V3.** Un lanceur plus ancien refuse
  proprement une partie qui demande une fonction qu'il n'a pas (« le jeu installé n'a pas tous les verrous de
  cette graine ») : rien n'est lié ni envoyé. Tous les joueurs Yo-kai Watch 2 de la partie doivent donc passer à la V3.
- Les mondes français et anglais jouent toujours dans la même partie multiworld.
- Le YAML du monde anglais est entièrement en anglais (noms d'options, valeurs, clés des verrous) ; un YAML qui
  utilise les noms français marche toujours (un simple avertissement donne le nom anglais de chaque option).

## 1. Nouveaux objectifs (option `objectif`)

- **`battre_potofeu`** : finir l'histoire, puis vaincre Potofeu au fond des Limbes éternelles (il faut la Clé de
  cabane, mélangée dans la partie).
- **`battre_filomene`** : finir l'histoire, puis vaincre Filomène au bout du Sanctuaire divin.
- **`battre_extrabuki`** : finir l'histoire, puis vaincre Extrabuki au Théâtre Kaibuki (Pass sortilège pour le train
  de Gera Gera, rang S, puis les trois requêtes des stations).
- **`medaillium_complet`** : finir l'histoire, puis remplir le Médaillium jusqu'au nombre choisi
  (`medaillium_seuil`, 448 = tout). Les 448 entrées ont une voie prévue par la logique ; c'est une partie très longue
  (une centaine d'heures). Cet objectif active de lui-même tout ce dont il a besoin (après-jeu complet, amis, boss,
  invités, pièces spéciales...).
- La victoire part quand le boss est **vaincu, où qu'il soit** (avec le mélange des boss, il peut avoir changé de
  place) et que l'histoire est finie. `finir_chapitre_10` (défaut) reste la partie de la V2, sans après-jeu.

## 2. Après-jeu (option `apres_jeu`)

- `necessaire` : les checks du **chemin de l'objectif** (coffres dorés des Limbes éternelles et du Sanctuaire divin,
  boss traversés ; pour Extrabuki, requête du rang S, coffres et requêtes du train de Gera Gera).
- `complet` : en plus **tout l'après-jeu** des types activés : 99 coffres dorés (Yo-kai World, stations du Sortilège
  Express, Château de Sawayama, Voie du mystère, recoins de rang S...), 31 requêtes et 4 services, 8 boss, le
  Tablo-blabla n° 24, 18 amis (dont les légendaires). Ce qui est hors du chemin de l'objectif ne contient que du
  remplissage.
- **Objets d'accès** mélangés : Clé de cabane, Clé du Yo-kai World, **Pass sortilège** (le train de Gera Gera s'ouvre
  dès réception, la requête « Direction Gera Gera ! » est proposée tout de suite), Pass Entrain Exp., Paquet
  spirituel, Clés d'appartement A-203 / B-102, et les **quatre clés de la Voie du mystère** (porte de San Fantastico et
  ses trois embranchements).
- Le Château de Sawayama et ses requêtes entrent dans la partie.

## 3. Mode YO-KAI WATCH Blasters (option `blasters`)

- Un check par **terrain de Ψ Blasters** fini (on y joue seul en créant un groupe).
- `debut` : Gargaros et Crocho ; `tous` : aussi les terrains longs (remplissage), ceux de Jiganyan et Komak (avec
  leurs checks « Ami ») et ceux de l'après-jeu.
- Le terrain de Triptyk demande 30 photos de Yo-kai prises avec l'appareil de la console (impossible sur émulateur) :
  le jeu modifié les tient pour prises, sans rien écrire dans la sauvegarde. Le terrain de Domniscian et son check
  « Ami » deviennent possibles.
- Les terrains de Jiganyan et Komak viennent des autres éditions du jeu : seul, cette édition ne les montre jamais. Le
  jeu modifié les rend jouables seul quand la partie a leurs checks.
- **Un objet par terrain** (option `blasters_terrains`, désactivée par défaut) : douze objets « Terrain : <boss> » ;
  un terrain s'ouvre dès que son objet est reçu, et seulement alors (plus d'orbes onis, de photos ni d'autres
  conditions). Gargaros et la Ruée de triple boss restent ouverts. Les 13 terrains (et les « Ami » de Domniscian,
  Jiganyan et Komak) deviennent des checks ordinaires dès le chapitre 4, qui peuvent contenir des objets nécessaires.

## 4. Nouveaux objets-clés et verrous (option `verrous_actifs`)

Comme en V2, un verrou est **réel** : le jeu refuse vraiment l'action tant que l'objet n'est pas reçu, et un objet
reçu « en retard » ne bloque jamais la partie. Les modèles de YAML les activent tous (31).

| Objet | Effet sans l'objet |
|---|---|
| **Yo-kai Watch** | en combat, boutons Cible, Âmultime et Purifier fermés (exigée dès le chapitre 3 et par tous les boss) |
| Documents perdus | Papa ne les reprend pas (requête du chapitre 7) |
| Cartes d'Ultramax | Lulutin ne vient pas (requête du chapitre 6) |
| Lettre de Komasan, Bille mystérieuse | les deux requêtes obligatoires du chapitre 5 ne finissent pas |
| Grelot félin, Montre de luxe | la scène de fin du chapitre 5 attend les deux |
| Capsules de lait | exigées dès la fin du chapitre 9 (le chapitre 10 se joue en ville bouclée) |
| **Miroirs** | aucun miroir de téléportation n'apparaît |
| Ceinture de force, Robot rétro neuf, Robot mécanique usé, Serviette douce, Dance Revolution | la requête facultative qui les demande ne finit pas |
| Carte à tamponner | pas de tampon dans les gares |
| **Abonnement de train** | portillons des gares fermés : ni Ourcival ni San Fantastico, l'histoire s'arrête au chapitre 4 |
| **Voyage dans le temps** | tous les passages vers le passé fermés (les retours, jamais) ; exigé dès la fin du chapitre 5 |
| Clé appartement C-302 | (correction d'un oubli de la V2 : la clé existe de nouveau dans la partie) |
| Clé magnétique bleue | (avec les rangs : son coffre devient un check, la clé entre dans le pool) |

Chaque objet-clé de la V3 a aussi son check « Objet-clé : ... » à son emplacement d'origine (et « Passage du temps »
pour le voyage dans le temps). Le check « Objet-clé : Yo-kai Watch » part au magasin du chapitre 1, quand la fenêtre
d'objet obtenu montre l'objet de la location à la place de la Montre étrange. Option à part **`parchemins`** : les
trois Parchemins du jeu (donnés d'ordinaire par code QR) entrent dans le pool.

**Rang S de la montre** (verrou `rangs`, avec un objectif d'après-jeu qui a des checks de rang S) : un **5e « Rang de
montre »** entre dans le pool et donne le **rang S**, une fois l'histoire finie (reçu avant, la montre passe au rang S
à la fin de l'histoire). La requête « Obtenons le rang S ! » n'est plus qu'un check. Le suivi du lanceur affiche « S »
au 5e exemplaire.

**Mirapo de poche** (valeur `mirapo_de_poche`, **désactivée par défaut**, absente du modèle par défaut : ajoutez-la à
la liste ; activée dans le modèle « tout activé ») : l'objet Miroirs devient deux objets progressifs « Miroirs
progressifs ». Le 1er ouvre les miroirs (comme l'objet Miroirs) ; le 2e donne le **Mirapo de poche** : **tenir SELECT
~0,5 s** sur le terrain ouvre le menu des miroirs n'importe où, avec tous les miroirs déjà enregistrés. Il est refusé
dans les donjons, les gares, le passé et le monde des Yo-kai, pendant une scène ou un dialogue, quand l'histoire
elle-même ferme les miroirs, et dans la zone où l'histoire retient le joueur (le village d'Ourcival, par exemple) :
le jeu répond alors « Le Mirapo de poche ne répond pas ici » et en donne la raison. Un bandeau rappelle la touche à
la réception. Avec le Mirapo de poche, SELECT ne met plus le jeu en pause sur le terrain (la console le traite
d'habitude comme START) : la pause reste sur START. Rien ne l'exige.

**Objets dans le sac** (avec l'installation des objets du jeu, active par défaut) : l'Abonnement de train, le Voyage
dans le temps et les Miroirs apparaissent dans l'onglet « Objets clés » quand vous les recevez. Au 2e exemplaire des
Miroirs progressifs, l'objet « Miroirs » est remplacé par « Mirapo de poche » (icône de poudrier, aussi dans le suivi
du lanceur). Avec les clés du donjon des portails, un seul objet « Trousseau du donjon (n/5) » suit les clés reçues :
il est échangé à chaque clé, et sa description liste les portes ouvertes. Ce ne sont que des objets d'affichage (les
verrous marchent d'après les objets Archipelago reçus). Ces objets ont des icônes dessinées à la main.

## 5. Requêtes à transfert (option `requetes_transfert`)

Les **dix requêtes** qui n'existent d'ordinaire qu'après le transfert d'une sauvegarde d'Esprits farceurs ou de
Fantômes bouffis sont proposées **toutes les dix dans la même partie**, sans transfert (six avant la fin, quatre
après), avec les checks « Ami » des Yo-kai qu'elles donnent.

## 6. Invités, pièces spéciales et Médaillium

- **Invités de l'Auberge** : ils arrivent dans l'**ordre où vous recevez leurs invitations**. Avec l'objectif
  Médaillium, les 16 Yo-kai des armées deviennent aussi des invités.
- **Pièces spéciales du Crank-a-kai** (option `pieces_speciales`) : les pièces que le jeu ne donne que par code QR,
  mot de passe ou en ligne entrent dans la partie (16 Pièces 5 étoiles, Pièces frisson (fleur), les 9 pièces
  régionales, Pile ou passe, Super pile ou passe, objets de fusion des Yo-kai régionaux). Chaque pièce donne **à coup
  sûr un Yo-kai qui vous manque** (jamais un objet, jamais un doublon) ; l'ordre des Pièces 5 étoiles est tiré pour la
  partie et montré par le lanceur. Une pièce perdue (équipe pleine) est redonnée. Une Pièce bleu ciel de plus donne
  Bananar, et ne se vend plus.
- **Légendaires mélangés** (option `legendaires_melanges`) : chaque sceau du Médaillium donne un **autre** légendaire ;
  les huit Yo-kai demandés par chaque sceau ne changent pas, et rien d'obtenable ne devient impossible.

## 7. Mélange des Yo-kai

- Le mélange touche désormais aussi les **coffres piégés**, les **trains**, les **missions du gymnase**, les **lieux
  d'histoire** et les **spots** de Yo-kai ; avec un objectif d'après-jeu, les Yo-kai sauvages d'après-jeu aussi.
  Nettement plus de Yo-kai différents dès le début du jeu.
- La **loupe** montre le Yo-kai mélangé dès que le mélange est appliqué, sans changer de carte.
- **Zones des Yo-kai demandés** (option `zones_yokai`) : chaque Yo-kai qu'une requête, un Tablo-blabla ou un service
  demande est placé dans une **zone tirée pour la partie** (au moins deux endroits de cette zone) ; la logique en tient
  compte et le lanceur affiche « garanti à <zone> ».
- Le lanceur explique l'état du mélange (carte « Connexion Archipelago ») et pourquoi un lieu est resté d'origine (onglet
  « Yo-kai »). Quand la logique de la partie dépend d'un mélange (zones des Yo-kai demandés, boss d'après-jeu) et
  qu'il n'est pas encore prêt (ROM à choisir dans le lanceur, par exemple), la partie attend : rien n'est lié ni
  envoyé, puis elle reprend seule.
- **Bingo-kai aléatoire** (option `bingo_aleatoire`) : les Yo-kai que donnent les pièces ordinaires du Crank-a-kai
  sont mélangés entre eux ; chacun reste obtenable à la même machine avec la même sorte de pièce. Le lanceur dit ce
  que chaque pièce peut donner.

## 8. Boss

- Avec un objectif d'après-jeu, les **boss d'après-jeu sont mélangés entre eux** (jamais avec ceux de l'histoire) ; le
  mélange est tiré à la génération, et le boss de l'objectif peut changer de place.
- **Boss de la Voie du mystère** (Blingos, Cycloptique, Maximain, Bogos) : quand la Voie du mystère fait partie de la
  partie (`apres_jeu: complet`, ou objectif « compléter le Médaillium »), ils sont mélangés comme les autres boss
  d'après-jeu : entre eux avec `rando_boss: meme_classe`, avec les boss des Limbes et des requêtes d'après-jeu avec
  `rando_boss: total` (entre eux avec l'objectif Médaillium, pour que la pièce de chaque machine de la Voie, laissée
  par le boss de la ligne, se regagne à chaque parcours). Le boss d'un objectif « battre X » n'est jamais mis sur la
  Voie. Leurs quatre places ont un check « Boss : Blingos », « Boss : Cycloptique », « Boss : Maximain », « Boss :
  Bogos », envoyé à la victoire contre le boss qui s'y trouve.
- **Force adaptée** (option `rando_boss_force: adaptee`) : un boss déplacé prend la force du boss d'origine de sa
  place (un boss de fin de jeu placé tôt n'est plus imbattable, un boss faible placé tard est renforcé). Le boss de
  l'objectif garde toujours sa force d'origine.
- Checks des boss d'après-jeu, y compris pour les places sans marqueur dans la sauvegarde (le check part avec la
  fiche du Médaillium de l'occupant).

## 9. Nouveaux checks

- **Distributeurs de soda** (option `distributeurs`) : 108 checks, la première boisson de chaque bouton de chacun des
  54 distributeurs.
- **Boutiques d'après-jeu** (avec `boutiques` et l'après-jeu complet) : boutique du village du Château de Sawayama et
  articles fixes de la boutique de l'Entrain Express (le train doré).
- **Requêtes clés seulement** (option `quetes: requetes_cles`) : seules les 23 requêtes que l'histoire exige
  (chapitres 2 à 7 et 9) sont des checks ; les autres requêtes ne le sont pas.

- **Clés du donjon des portails** (option `donjon_portails`, désactivée par défaut) : cinq objets, un par porte à
  globes du donjon des portails mystères de La Corniche ; les coffres 01 à 03 du donjon deviennent des checks
  ordinaires (les coffres 04 à 10, Tromplœil et « Le portail final » restent hors progression : chemin exigeant d'appeler
  des Yo-kai de Tablo-blabla, ou accès que la logique ne garantit pas).

## 10. Confort

- **Remplissage plus varié** (option `remplissage`) : en plus des 12 consommables de la V2 (défaut), toute la
  nourriture du jeu (74 aliments), les 74 équipements et les 16 livres, au choix (liste de familles).
- **Argent réglable** : montants des dons d'argent au choix (option `argent_montants`, de 10 € à 5 000 € ; défaut
  100 € et 500 €) et forme (option `argent_forme`) : des euros (défaut), des poupées à revendre en boutique (fer, bronze,
  argent, or, platine : de 3 € à 600 €), ou les deux.

- **Tunnel sans fin sans limite par jour** (activé par défaut).
- **Revanches sans limite de jour** et boss de la Voie du mystère à chaque parcours (option
  `revanches_sans_limite`).
- **Tirage dirigé de la Voie du mystère** : ses machines donnent à coup sûr les Yo-kai qui manquent (option
  `tirage_dirige_voie`).
- **Train doré plus fréquent** (option `train_dore` : 2, 3 ou 4 fois sur 10 au lieu de 1).
- **Chance d'amitié** (option `amitie`) : normale, x2, x4 ou assurée. Elle ne change pas qui peut devenir ami, et il
  reste un seul nouvel ami par combat. Avec « assurée », si vous avez nourri un des Yo-kai battus, c'est lui qui
  devient votre ami ; ensuite, un Yo-kai qui n'est pas encore votre ami (Médaillium) est préféré ; enfin le plus
  rare, comme dans le jeu d'origine. Les Oni de la Voie du mystère (Gargaros, Ogralos, Orqanos) ne se recrutent pas
  par l'amitié de fin de combat, mais par un don au hasard après la victoire (5 % ou 3 %) : avec « assurée », ce don
  est assuré à la première victoire (Oni pas encore ami, place dans l'équipe). Les Oni de la Terr'heure et celui du
  piège ne deviennent pas amis, comme dans le jeu d'origine.
- **DeathLink** : une partie perdue de la Terr'heure ou de Blasters compte aussi pour une mort (une par partie),
  seulement pour les parties générées avec la V3.

- **Récompense aléatoire des portails** (option `portails_recompenses`, désactivée par défaut) : le coffre de fin
  d'un portail mystère donne un objet du jeu tiré pour la graine (nourriture, soins, orbes, livres, équipements), en
  plus des globes d'origine.

- **Pièges** (option `pieges`, désactivée par défaut, activée dans le modèle « tout activé » ; part réglable par
  `part_pieges`, 10 % par défaut) : une part des objets de remplissage devient des pièges, envoyés à votre monde comme n'importe quel objet : combat surprise, perte de 10 %
  de l'argent, montre brouillée (radar éteint 5 minutes), pluie (5 minutes), PV à moitié au prochain combat, équipe
  mélangée (la roue tourne toute seule, puis reste bloquée 30 secondes), combat contre un Oni à la force de
  l'équipe (sans fuite ; victoire : l'expérience et l'argent d'un Yo-kai ordinaire). Chaque piège a son poids (options
  `piege_...`, relatifs : une somme de 100 donne des pourcentages). Un piège n'agit qu'à un moment sûr (terrain libre
  ou prochain combat sauvage), il est annoncé par le bandeau et ne fait jamais perdre de check. Une partie avec des
  pièges demande le lanceur qui sait les recevoir. Un piège reçu et pas encore déclenché quand on ferme le jeu revient
  au lancement suivant. Une fois l'objectif de la partie atteint, les pièges n'ont plus d'effet : ceux qui arrivent
  ensuite (quand les autres joueurs font leur release ou leur collect) sont annoncés « Piège ignoré », et ceux qui
  attendaient encore leur moment sont retirés (pluie et montre brouillée en cours arrêtées, au retour sur le terrain).
  Les autres objets sont donnés comme avant. La victoire est retenue d'un lancement à l'autre.

- **Multiplicateur d'XP** (option `multiplicateur_xp`, désactivée par défaut, activée dans le modèle « tout
  activé ») : trois objets « Multiplicateur d'XP » (progressifs, utiles) remplacent trois objets de remplissage.
  Toute l'expérience gagnée par les Yo-kai (fin de combat gagné, récompense de requête, objets d'expérience) est
  multipliée par 2 avec le premier reçu, par 3 avec le deuxième, par 4 avec le troisième ; les écrans montrent la
  valeur multipliée. L'argent et les objets ne changent pas. Aucune règle de logique n'en dépend. Le palier atteint
  est visible dans le sac (« Objets clés ») : « Multiplicateur d'XP x2 », puis x3 et x4, qui remplace le précédent à
  chaque exemplaire reçu.

- **Objets de départ** (option `objets_de_depart`, tableau vide par défaut) : la partie commence avec les objets
  choisis, par exemple `objets_de_depart: ["Vélo", "Abonnement de train", "Rang de montre"]` (noms de l'APWorld,
  en français ou en anglais, entre guillemets doubles). Chaque nom retire un exemplaire de l'objet du monde (un objet
  de remplissage prend sa place) et le donne dès le début, comme un objet reçu ; la logique le compte comme déjà
  possédé. Une mention = un exemplaire (deux fois « Rang de montre » : rangs D et C). Une mention de trop, un objet
  que la partie ne met pas dans le monde (objet-clé sans son verrou, option désactivée) et les pièges sont ignorés,
  avec un avertissement à la génération ; un nom inconnu arrête la génération.

## 11. Fichier spoiler

Le fichier spoiler d'Archipelago contient une section Yo-kai Watch 2 : mélange des boss (et place du boss de
l'objectif), légendaires (sceau → légendaire), ordre des Pièces 5 étoiles, zones des Yo-kai demandés, pièges
(pourcentage effectif de chaque piège). Le mélange des
Yo-kai sauvages, du Bingo-kai et la force adaptée des boss sont calculés chez le joueur depuis sa ROM : le lanceur les
montre (onglet « Yo-kai »).

## 12. Version PC (Zakuro intégré)

- Le lanceur peut fournir **Zakuro**, un émulateur 3DS qui fait tourner le jeu en **code PC** : le jeu est préparé une
  fois sur votre ordinateur, à partir de votre ROM. La première préparation prend quelques minutes (environ 4 minutes
  sur un PC récent, davantage sur un ordinateur plus modeste) et peut télécharger un compilateur d'environ 100 Mo.
  Ensuite, le jeu préparé est gardé : les lancements suivants n'ont rien à refaire, et après une mise à jour du mod,
  seul ce qui a changé est refait (en général moins d'une minute). Rien du jeu n'est distribué.
- Quand Zakuro est fourni, c'est l'émulateur par défaut (carte « 2. Émulateur » du lanceur). **Azahar reste
  utilisable** : « Choisir... » `azahar.exe` dans cette carte (et `zakuro\zakuro.exe` du dossier du lanceur pour
  revenir à Zakuro).
- Les sauvegardes de Zakuro sont **séparées** de celles d'Azahar (dans `%APPDATA%\ykw2-ap\zakuro`, elles restent
  quand vous mettez le lanceur à jour) : une partie commencée sur Azahar se continue sur Azahar.
- Onglet **« Réglages »** du lanceur, sous-onglet **« Zakuro »** : langue du jeu, résolution, interpolation
  d'images, taille de la fenêtre, écrans, filtre, son de Zakuro. Appliqués au prochain lancement de Zakuro.
- **Place des écrans** : dans la fenêtre de Zakuro, plein écran compris, les écrans du jeu peuvent être collés à gauche
  ou à droite au lieu d'être centrés, pour poser le lanceur dans la place libre (Réglages → Zakuro, ou Échap →
  Settings → « Screens' place »). Le toucher de l'écran du bas à la souris suit les écrans.
- **Blasters** : les Blasters se jouent seul sur la version PC, sans salon ni connexion (Yo-kai Pad → Blasters →
  « Créer un groupe », puis lancer sans invité). Avant, l'application affichait « communication sans fil
  désactivée » ou « Déconnecté. ».
- **Manettes** : Zakuro lit les manettes PlayStation, Xbox et Switch, en USB ou en Bluetooth, même quand sa fenêtre
  n'est pas au premier plan. `zakuro\tester_manette.cmd` (dans le dossier du lanceur) montre ce que Zakuro voit d'une
  manette.

## 13. Lanceur et suivi

- **Autocomplétion dans la console** (onglet « Discussion ») : en tapant `!`, une liste propose les commandes ; après
  `!hint ` ou `!hint_location `, les noms d'objets ou de lieux de votre jeu, comme dans le client d'Archipelago.
  Flèches pour choisir, Tab ou Entrée pour compléter, Échap pour fermer.
- **Fenêtre d'amitié en combat** (case dans l'onglet **« Réglages » → « Paramètres du jeu »**, décochée par
  défaut, avec Azahar comme avec Zakuro) : une petite fenêtre
  transparente, au-dessus du jeu, dit pour chaque Yo-kai ennemi s'il est déjà votre ami ; cachée hors combat,
  déplaçable.
- Colonne des objets : une seule case **« Trousseau du donjon (n/5) »** pour les 5 clés du donjon des portails
  (l'infobulle dit quelles portes sont ouvertes), et une seule case pour les **Miroirs progressifs** : « Miroirs »,
  puis « Mirapo de poche » au deuxième exemplaire.
- **Fenêtre de la loupe** (« Réglages » → « Paramètres du jeu », décochée par défaut) : quand le radar de la montre
  vise un point, une petite fenêtre transparente nomme le Yo-kai qu'on y combattra et dit s'il est déjà votre ami.
- **Fenêtre des derniers objets** (même endroit) : les derniers objets reçus et envoyés, effacés après un délai
  réglable.
- **Garder le lanceur au premier plan** (même endroit), sans prendre la main au jeu.
- **Musique aléatoire** (même endroit, décochée par défaut) : les musiques du jeu sont mélangées entre elles
  (terrain, combats, scènes), sans aucune musique extérieure ; appliquée au prochain « Jouer », un nouveau mélange à
  chaque fois qu'on recoche la case. Les jingles, les jeux de rythme et les chansons propres à une langue gardent
  leur musique. Purement cosmétique : sans effet sur la partie Archipelago.
- **Apparence du héros** (« Réglages » → « Apparence ») : tenues officielles, tons sépia ou couleur libre pour Nathan
  et Katie, avec un aperçu ; quelques tenues cachées du jeu (marquées « expérimental ») ; import d'un mod d'apparence
  que vous avez déjà (zip ou dossier). Appliqué au prochain « Jouer », purement cosmétique.
- Carte : bouton **« Que faire maintenant ? »** : les checks accessibles, en commençant par la carte où vous êtes.
- Carte : la liste « Carte : » se filtre en écrivant (sans tenir compte des majuscules ni des accents).
- Carte : la porte d'un bâtiment dont le vendeur n'est pas encore là n'est plus « accessible » ; les vendeurs de nuit
  sont montrés absents tant que la nuit n'est pas libre dans l'histoire.
- Rubriques **Pièces spéciales** (icônes, compte, prochain Yo-kai) et **Légendaires** dans la carte du suivi ; lieux
  « Bingo-kai » et « garanti à <zone> » dans l'onglet « Yo-kai » ; vue « Boss » avec la force appliquée. Les Yo-kai
  que la partie donne sans rencontre (invités, Yo-kai des pièces spéciales, fusions régionales) y ont aussi leur
  ligne, avec leur lieu.
- Messages clairs quand une partie est en attente ou bloquée (mélange en préparation, ROM à choisir, mod à mettre à
  jour) ; noms exacts de ce qui manque quand un lanceur ou un jeu installé est trop ancien.

- **Mise à jour du lanceur** : au lancement, le lanceur regarde si une version plus récente existe (requête simple au
  dépôt public, aucune donnée envoyée ; case dans « Réglages » → « Paramètres du jeu »). Avec l'exe, le bouton
  « Mettre à jour » télécharge et contrôle le paquet, remplace les fichiers et relance le lanceur ; en cas d'échec,
  l'ancienne version reste en place. Refusé tant que le jeu, Azahar ou Zakuro sont ouverts. Paquet `.pyw` : une
  alerte avec un lien. Le lanceur de la V2 n'a pas ce système : le passage de la V2 à la V3 se fait à la main.

## 14. Corrections par rapport à la V2

- **Clé appartement C-302** : en V2, cette clé avait disparu de la partie (son coffre était devenu un check) ; avec le
  verrou `cle_appartement_c_302`, elle revient dans le pool.
- **Égouts** : les coffres 10 et 11 exigent l'Herbe ancestrale et les Clés de l'école (on n'y entre que par le
  Quartier des boutiques), les coffres 12 et 13 les Clés de l'école (entrée par le Coteau fleuri), et l'objet-clé
  « Clé magnétique rouge » (après les dix grilles) 3 chapitres, la Pile ou passe, les Indications de Maman, l'Herbe et
  les Clés.
- **Étages de la Tour du commerce** (3e, 12e et 13e) : l'ascenseur ne les ouvre qu'après l'appel du Yo-kai du
  Tablo-blabla n° 11, ce que la logique ne peut pas garantir ; leurs coffres et la requête « Ronéan : les origines »
  ne contiennent plus que du remplissage (nouvelles parties ; une partie de la V2 garde son placement).
- **Bus du village d'Ourcival** (chapitre 4) : tant que la Canne à pêche ou le 1er Rang de montre (mode « rang
  réel ») manque, le bus du village vers la gare n'est plus refusé de 4-110 à 4-135 : on peut aller chercher l'objet
  ailleurs puis revenir par le bus de la gare (prix d'origine : 2 €). Sans verrou, ou l'objet reçu, rien ne change.
  Le bus est aussi rendu tant que la requête 99 (vaincre 3 Pachycoul) est acceptée et pas finie : avec le mélange par
  zones, Pachycoul peut n'être qu'à Granval.
- **Chantier du Centre-ville** : les requêtes « Super Balaise : le retour » et « Le géant fantôme » (et donc « Super
  Méga Balaise », « Musée en détresse », le boss Ombraptor et les coffres du géant fantôme) n'attendent plus deux ou
  trois jours réels après l'appel du Yo-kai du Tablo-blabla n° 9 : le chantier est fini dès l'appel.
- Logique : le coffre du **Passage des matous** exige le chapitre 1 terminé et la Pile ou passe ; le coffre **« retour
  Ch10 » du Vieux Granval** n'est attendu qu'après le chapitre 10 (remplissage seulement quand l'objectif est la fin du
  chapitre 10).
- **Tablo-blabla** : le check part quand on APPELLE le Yo-kai du panneau, ce qui exige de le posséder. La logique
  attend désormais à la fois le panneau et ce Yo-kai (lieu où on le trouve, objets pour y aller, rang de montre que
  demande la loupe) : par exemple le n° 2 n'est plus annoncé avant la Tour Excellence (chapitre 6). Nouvelles parties :
  le n° 4 n'existe qu'avec l'option `requetes_transfert` (son Yo-kai ne vient que d'une requête à transfert), le n° 25
  qu'avec son objet d'évènement et les checks « Ami » (l'objet est cité par sa règle), et le n° 23 seulement dans
  l'après-jeu complet (son Yo-kai, un légendaire, exige un membre de rang S).
- Logique : les trois derniers articles de la supérette du **Quartier des boutiques** (N004, mode `toutes`) ne sont
  vendus qu'après le Yo-kai du **Tablo-blabla n° 12** ; leur règle attend désormais ce panneau.
- Logique : les 13 coffres de l'**École élémentaire de Granval (nuit)** s'ouvrent dès la nuit d'histoire du chapitre 3
  (phase 3-190) ; leur règle n'attend plus la fin du chapitre 3, mais le chapitre 2 terminé et les **Clés de l'école**,
  l'**Herbe ancestrale** et le **Super tournevis** (avec le mélange des Yo-kai par zones : aussi la zone du Yo-kai de la
  requête du chapitre 3).
- Logique : un objet-clé qui arrête l'histoire (Documents perdus, Lettre de Komasan, Bille mystérieuse, Capsules de
  lait, Cartes d'Ultramax, Canne à pêche…) n'est plus exigé par les checks qu'on peut faire AVANT le moment où
  l'histoire s'arrête sans lui (environ 280 checks, requêtes et coffres surtout). La fin du chapitre et la requête qui
  demande l'objet l'exigent toujours. Le Yo-kai Watch Modèle zéro n'arrête pas l'histoire : la logique ne l'exige plus.
- Pour une partie générée avec la V2, le suivi du lanceur affiche aussi ces règles de logique corrigées (sauf celle
  de la Tour du commerce).
- Fenêtres « objet obtenu » : les objets de votre propre monde qui ont une image (invitations, Abonnement de train,
  Voyage dans le temps, Miroirs, clés du donjon des portails, Pass sortilège, clés de la Voie du mystère) la montrent à
  la place du logo Archipelago, sous le même nom. Sans les objets du mod installés : le logo, comme avant.
