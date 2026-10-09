# Notes de version : V2 (par rapport à la V1)

La V2 est une **refonte complète**. Ce document liste ce qui a été fait, par thème.

## 1. Une nouvelle base technique

- **Le jeu lui-même est modifié**, au lieu d'un client qui écrivait dans sa mémoire. Un patch du programme du jeu
  fait donner les objets reçus, remplacer le contenu des coffres et signaler les checks. Le
  client dialogue avec le jeu par une zone d'échange en mémoire.
- **Rien du jeu n'est distribué.** Le patch est appliqué chez vous, à partir de votre ROM, par le lanceur. La distribution ne contient
  aucun octet du jeu (un contrôle automatique le vérifie à la fabrication du paquet).
- L'état de la partie est **dans la sauvegarde** du jeu (plus de fichier « déjà livré » à côté).
- Le client ne laisse plus de décalage entre ce que le jeu affiche et ce qui se passe : ce que montre un coffre ou une
  boutique est ce qui est vraiment envoyé.

## 2. Le lanceur

- Une fenêtre, un bouton **Jouer**. Choix de la ROM (vérifiée), détection d'Azahar, installation / réparation / désinstallation du
  mod en un clic (la désinstallation remet le dossier d'Azahar comme avant).
- Fourni en **`.exe`** (aucun Python à installer) ; une variante `.pyw` existe pour ceux qui ont Python 3.11+.
- Active la « liaison avec le jeu » d'Azahar (stub GDB) **avec votre accord**, après une copie de sauvegarde de sa configuration.
- **Connexion Archipelago** saisie dans le lanceur (serveur, slot, mot de passe, mot de passe mémorisable et chiffré pour votre
  compte Windows), modifiable en pleine partie : le client se reconnecte tout seul.
- État en direct : client, jeu, serveur, sauvegarde (liée / non liée / autre partie / mod à mettre à jour).
- Interface française et anglaise. Journaux accessibles (bouton « Journaux »).
- Un **enregistreur de plantage** : si le jeu panique, le client garde l'adresse fautive et la pile dans `plantage.json`
  pour le diagnostic.

## 3. Liaison des sauvegardes

- Une partie Archipelago se joue sur une **nouvelle partie du jeu** : la sauvegarde est liée automatiquement.
- Une sauvegarde déjà commencée n'est **jamais adoptée**, et une sauvegarde liée à une autre graine est **refusée** : rien n'y est
  reçu ni envoyé, et le lanceur l'indique.
- Garde-fous des deux côtés (le client et le jeu revérifient).

## 4. Verrous réels (option `verrous_actifs`)

Avec un verrou activé, le jeu **refuse vraiment** l'action tant que l'objet n'est pas arrivé :

| Verrou | Effet |
|---|---|
| Filet à insectes | points de recherche à la loupe inutilisables, tutoriel du chapitre 1 compris |
| Canne à pêche | pêche fermée ; utilisable dès réception ; exigée au chapitre 4 (la requête des trois poissons) |
| Modèle zéro | interface de combat du Modèle zéro disponible dès réception (début du chapitre 2) |
| Clés de l'école | école fermée, chapitre 3 bloqué |
| Herbe ancestrale, Super tournevis | scènes du chapitre 3 non déclenchées |
| Indications de Maman | Centre-ville fermé jusqu'à la remise d'objets de Maman (chapitre 4) |
| Clé salle du trésor | combat de Volteface non déclenché |
| Poignée étrange | utilisation de nuit à la Clinique du Crépuscule sans effet |
| Pile ou passe | la Crank-a-kai du tutoriel du chapitre 2 n'accepte que cette pièce (blocage du jeu lui-même) |
| **Rangs de montre réels** | 4 objets progressifs D, C, B, A : chaque exemplaire fait vraiment monter la montre ; les portes de montre, requêtes et passages de l'histoire exigent le rang ; ajoute 36 coffres |
| **Vélo réel** | recevoir le Vélo donne vraiment le vélo (on roule tout de suite) ; sa requête devient un check |
| Capacités anticipées | Canne et Modèle zéro utilisables dès réception, sans attendre l'étape du jeu qui les donne d'ordinaire |

Les verrous respectent les scènes déjà jouées (activation tardive sans danger).

## 5. Les checks

**Coffres et objets-clés**
- Coffres dorés (environ 253 avec les rangs) : le contenu est remplacé par l'objet Archipelago, avec une icône dédiée, et le
  check part à l'ouverture.
- Emplacements d'origine des objets-clés (environ 22) : checks. Fenêtre « objet obtenu » du jeu pour les checks sans affichage.

**Boss**
- Option `boss` : `histoire` (12), `histoire_et_quetes` (23), et le nouveau mode **`tous`** (29 : en plus Fumella, Draconfus,
  Faux Kappa, Sabrille, Anguigne, et Taprice au bout du Tunnel sans fin).
- Le check part à la victoire ; avec le mélange des boss, il reste attaché au lieu du combat.

**Tablo-blabla** : 25 panneaux ; le check part quand le Yo-kai du panneau est appelé.

**Requêtes et services** : environ 76 requêtes et 16 services ; la récompense d'objet de la quête est remplacée par
l'objet Archipelago dans l'écran de résultat.

**Chapitres** : chapitres 1 à 9 terminés et « Montée de rang : D ».

**Amis** (option `amis`, environ 290 checks) : Yo-kai sauvages, évolutions et fusions Yo-kai + Yo-kai ; Yo-kai donnés par
l'histoire ou une requête ; Yo-kai d'évènement (chacun exige son objet) ; évolutions des invités de l'Auberge ;
5 fusions avec un objet garanti ; 16 Yo-kai des armées (avec le mélange des Yo-kai par rencontre).

**Yo-criminels** : un check par criminel arrêté (52). La limite d'un criminel par semaine réelle est levée : le prochain
criminel non arrêté est proposé à volonté, visible sur les 5 cartes de la ville, dès le chapitre 3.

**Boutiques** (option, désactivée par défaut) : le premier achat de chaque article retenu est un check (jusqu'à environ
285) ; réglage du prix maximal pour la progression.

**Portails mystères « longs »** : les checks qui exigent beaucoup de portails ou le Crank-a-kai sont signalés dans le lanceur et ne
reçoivent jamais de progression.

## 6. Mélange des Yo-kai et des boss

**Mélange des Yo-kai** (calculé chez vous depuis votre ROM, identique pour tous les joueurs de la graine) :
- Modes `par_rang`, `total` (échange d'espèces) et **`par_rencontre_rang`** (défaut) / `par_rencontre_total` (chaque Yo-kai de chaque
  rencontre reçoit sa propre espèce).
- **Garanties** : un Yo-kai exigé par le jeu reste trouvable à chacun de ses lieux d'origine ; chaque Yo-kai du mélange a un
  « lieu normal » (hors portail mystère) avant la fin ; plus de point de loupe vide ; 16 espèces normalement
  inobtenables sont ajoutées au réservoir.
- Le mélange est **versionné** par la graine : une partie en cours n'est jamais modifiée par une amélioration ultérieure.
- Les Yo-kai d'évènement, les boss, les Yo-criminels et le Crank-a-kai ne changent pas.

**Mélange des boss** (option `rando_boss`, désactivé par défaut) : un boss d'histoire ou de quête est remplacé par un autre, avec
son script, sa musique et ses statistiques ; le lieu, les scènes et le check restent ceux du boss d'origine.

## 7. Auberge des voyageurs, Yo-kai d'évènement, Ultramax

- **30 invités** : chacun a un objet « Invitation : <nom> » ; une fois reçu, le Yo-kai arrive à l'Auberge des voyageurs (Coteau
  fleuri), une fenêtre l'annonce, et on le combat autant qu'il faut pour qu'il devienne ami (taux d'amitié du jeu).
- **Pandanoko** occupe la **Suite réservée** quand toutes les requêtes-checks sont faites ; les autres invités sont logés dans les
  chambres 101 à 109 et **gardent leur chambre** jusqu'à ce qu'ils soient amis.
- Les **invitations sont de vrais objets du sac** (installés par le lanceur, icône avec le logo du mod).
- **Jibanyan S, Komasan S, Komajiro S** (invitations) et **Hovernyan** (Capsule favorite) apparaissent à leur place d'origine avant
  la fin du jeu. Jibanyan S attend que Jibanyan soit votre ami et que la scène du carrefour soit finie (un blocage de
  l'histoire vu en jeu a été corrigé).
- **Ultramax N et K** dans la même partie, avec deux checks.
- Objets des Yo-kai d'évènement (Rouages, Graines, Grelots, Marque d'Ultramax) dans le pool.

## 8. Bingo-kai et combats du jour

- **Bingo-kai infini** (option) : la machine ne ferme jamais (ni quota quotidien, ni fermeture de nuit).
- Les combats limités à un par jour sont **rejouables** (19 de plus que précédemment).

## 9. DeathLink (option `death_link`)

Une défaite dans le jeu envoie un DeathLink ; une mort reçue déclenche une vraie défaite (en combat, par la voie normale ;
sur le terrain, une fenêtre puis retour au point de reprise), à un moment sûr. Les combats d'évènement sans pénalité de défaite sont gérés.

## 10. Notifications

- Bandeau « Reçu : ... / De : ... » sans interrompre le jeu.
- Fenêtres « objet obtenu » du jeu pour les checks sans affichage (y compris les Yo-criminels).
- Un coffre ou une boutique montre « objet (pour joueur) ».
- Langue des textes réglable (`langue_notifications`).

## 11. Le suivi intégré (remplace le pack PopTracker)

- **Checks** : liste par zone (faits, accessibles, à faire plus tard, bloqués par tel objet), filtres, objets reçus (et qui les a
  envoyés), « Spoiler log » facultatif, aucun spoiler par défaut.
- **Carte** façon PopTracker : régions, marqueurs, compteurs, objectif « Chapitres N/10 », **position du joueur dans le jeu** (case
  « Suivre le jeu »), boutiques (vendeur, porte du bâtiment, articles un par un, conditions d'apparition), rubrique **Invitations**.
- **Yo-kai** : où trouver chaque Yo-kai sauvage sous le mélange réellement appliqué, **épinglage** sur la carte, moments (jour /
  nuit, temps sec / pluie), portails mystères signalés, nourriture préférée, facilité d'amitié, anti-divulgâchage.
- **Discussion** : client texte d'Archipelago (messages en couleurs, discussion, commandes `!hint`, `!remaining`..., indices).
- Le suivi marche même **sans le jeu** (connexion au serveur seule).

## 12. Robustesse et sécurité de la partie

- **Anti-softlock** : un audit rejoue la logique du jeu sur **200 graines** (dans les deux modes de rangs) pour éviter qu'une
  graine bloque ; les verrous sont posés pour ne jamais enfermer un joueur dans un état de jeu.
- **Budget mémoire** : le code ajouté est dimensionné pour ne pas priver le jeu de mémoire (un plantage « mémoire » vu au début a
  été corrigé) ; le build refuse une configuration hors budget.
- **Charge réduite** sur l'émulateur : le client ne lit que ce dont il a besoin, aucun gel de l'émulation.
- Connexions : le client ne ferme jamais la liaison sur une erreur de protocole et se reconnecte seul.
- Les graines de V1 ne sont pas compatibles : il faut générer une nouvelle partie.

## 13. Ce qui disparaît par rapport à la V1

- L'ancien client qui écrivait dans la mémoire du jeu.
- Le pack **PopTracker** (remplacé par le suivi du lanceur).
- Les options `quest_shuffle`, `chest_shuffle`, `tablo_shuffle`, `criminel_shuffle`, `encounter_shuffle`... : remplacées par les
  options de la V2 (voir le YAML, tout y est commenté).
