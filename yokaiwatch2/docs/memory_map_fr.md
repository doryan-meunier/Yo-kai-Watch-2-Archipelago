# Trouver la carte mémoire de Yo-kai Watch 2 (Azahar/Citra)

Objectif : remplir `yokaiwatch2/memory_map.py` (adresses RAM des coffres,
requêtes, Médallium, argent) pour que le client envoie les checks
automatiquement. Jeu ciblé : **Spectres Psychiques EU** (title ID
`00040000001B2900`, produit CTR-P-BYSP).

## Journal de rétro-ingénierie (avancement)

Session du 2026-07-06 (Azahar, save FR) — **adresses confirmées STABLES**
entre redémarrages de l'émulateur :

| Donnée | Adresse | Détails |
|---|---|---|
| Argent | `0x086CBBE0` | u32, en **centimes** (6164,19 € = 616419) |
| Coffres | `0x086CFE00` (bitfield ~0x200) | 1 bit fixe par coffre (indexé par ID) |

Méthode coffres validée : 3 coffres ouverts → bits 5, 4, 7 de `0x086CFE75`
(ordre non séquentiel ⇒ bit fixe par ID de coffre, pas par ordre
d'ouverture). Le heap lisible se limite à deux runs : `0x00100000-0x0091D000`
et `0x08100000-0x08E1D000` (la sauvegarde vit dans le second, autour de
`0x086C-0x086E`).

✅ **Deux types de coffres, tous deux UNIQUES** (violets et jaunes) : vérifié
qu'ils partagent le **même bitfield** `0x086CFE00`. Violets → bits 5,4,7 de
`0x086CFE75` ; jaune → bit 2 de `0x086CFE74` (octet adjacent). Donc un seul
`chest_flags` couvre les deux, indexés ensemble par ID global de coffre.

### Régularité des bits (testée en jouant)
- Le bit d'un coffre est un **ID fixe** (reproductible entre sessions), pas
  l'ordre d'ouverture.
- Les coffres d'une **même zone sont groupés** dans des octets contigus.
- **Les Hauts de Granval** = 17 coffres (7 violets + 10 jaunes), bits
  **929-948** (octets `0x086CFE74-76`). Mappés dans
  `memory_map.CHEST_BIT_TO_LOCATION`.

### ✅ Prototype end-to-end validé (2026-07-08)
Test réussi : état réel du jeu (17 coffres ouverts) → lecture du bitfield →
mapping → **serveur Archipelago : 17/17 checks enregistrés**. Le pont
mémoire→AP fonctionne. Piège rencontré : un client avec le tag `TextOnly`
est spectateur, le serveur **ignore ses `LocationChecks`** — le vrai client
ne doit pas porter ce tag.

Reste pour les autres zones : Doteos ne peut pas y accéder pour l'instant ;
le mapping se fera zone par zone (ouvrir les coffres, lire les bits) au fil
de sa progression, avec la même méthode.

### ✅ Écriture mémoire + inventaire (2026-07-08)
- **Écriture validée** : modifier `money` (0x086CBBE0) change l'argent en
  jeu ; modifier une quantité d'inventaire l'applique aussi. Le pont GDB
  écrit bien dans le jeu (commandes `write`/`writeu32` du scanner).
- **Inventaire décodé** (`INVENTORY_*` dans memory_map.py) : tableau
  d'entrées de 16 octets à partir de `0x086CC640`. Chaque objet =
  `[slot u16][type u16][hash CRC32 u32][quantité u32][ptr u32]`. Le hash
  est le CRC32 du nom interne de l'objet (même algo que les archives ARC0).
- **Livraison prouvée** : écrire à `entrée+0x08` ajoute des objets (testé :
  Mini EXPorbe hash `0x8D447F63` remise à 4).

**Reste pour délivrer les items AP** :
1. Mapper chaque item AP → hash CRC32 de l'objet du jeu (via
   `item_config_0.04b.cfg.bin` data-miné, ou empiriquement).
2. Gérer la création d'entrée pour un objet non encore possédé (slot suivant,
   type, hash, quantité, ptr `0x007FD398`).
3. Gérer les items AP « abstraits » (Vélo, rangs, clés, passes) autrement que
   par l'inventaire (flags / valeurs dédiées, à RE).
4. Câbler le client : `ReceivedItems` -> écriture inventaire/valeur.

**Reste à faire** :
- `quest_flags` (terminer une requête → snap/diff) ;
- `medallium_flags` (lier un Yo-kai → snap/diff) ;
- mapping `bit → location` de chaque coffre (remplir `CHEST_BIT_TO_LOCATION`
  dans `memory_map.py`) : soit en ouvrant les coffres un par un, soit en
  extrayant la table des coffres du RomFS (piste automatisable).

Outillage : `tools/memory_scan.py` (REPL interactif). Un scanner
**persistant** piloté par fichier (une seule connexion, robuste aux
reconnexions fragiles du stub Citra) a été utilisé pour cette session.

### Leçons apprises (stub GDB Citra/Azahar)
- Le stub **déteste les reconnexions** : rester sur UNE connexion toute la
  session. Une déconnexion mal gérée bloque le stub jusqu'au redémarrage
  complet d'Azahar (pas un simple Restart).
- Lire par **petits blocs** (≤ 0x400 o) : le buffer de paquet est limité.
- **Cartographier finement** (pages de 4 Ko) avant de lire en continu : une
  lecture qui franchit une page non mappée **fige** le stub.
- Après un timeout, le flux se **désynchronise** (un paquet stop `T05`
  traîne) : il faut le vider (resync) avant la lecture suivante.

## 1. Préparer Azahar

1. Lancez Azahar **sans jeu**.
2. `Émulation > Configurer... > Debug` : cochez **Enable GDB stub**,
   port **24689**. (Dans le fichier `%AppData%\Azahar\config\qt-config.ini`
   cela correspond à `use_gdbstub=true`.)
3. Lancez Yo-kai Watch 2. L'émulation démarre **en pause**, en attente du
   débogueur : c'est normal.

## 2. Lancer le scanner

```bash
cd "chemin/vers/yo kai watch 2 archipelago"
python tools/memory_scan.py
```

À la connexion, le scanner relance l'émulation automatiquement. Jouez
normalement ; chaque commande interrompt l'émulation une fraction de seconde
puis la relance.

## 3. Trouver l'argent (échauffement, 5 minutes)

L'argent est un entier 32 bits affiché à l'écran — recherche exacte :

```
scan> search 64850          # votre montant exact d'argent
```

- Plusieurs occurrences ? Dépensez un peu en boutique, puis relancez
  `search <nouveau montant>` : l'adresse commune aux deux recherches est la
  bonne.
- Vérifiez avec `read <adresse> 4` puis notez-la dans `MEMORY_REGIONS["money"]`.
- L'adresse sert de **point de repère** : les drapeaux de sauvegarde sont
  généralement dans le même bloc (la structure de sauvegarde en RAM).

## 4. Trouver les drapeaux de coffres (la vraie cible)

Méthode « instantané avant/après » :

```
scan> snap avant                       # ~2-4 min (64 Mo)
# ... dans le jeu : ouvrez UN coffre, sans rien faire d'autre ...
scan> snap apres
scan> diff avant apres 1               # bits passés de 0 à 1 uniquement
```

Il restera du bruit (timers, RNG). Pour l'éliminer :

```
scan> snap avant2
# ... ouvrez UN AUTRE coffre ...
scan> snap apres2
scan> refine avant2 apres2             # ne garde que les candidats rechangés
```

Après 2-3 coffres, il ne reste normalement qu'une poignée d'adresses
voisines : c'est le **bitfield des coffres**. Astuce de confirmation :
`watch <adresse> 16` puis ouvrez un coffre — vous verrez le bit se lever en
direct. Notez l'adresse de départ et une taille généreuse (ex. `0x40`) dans
`MEMORY_REGIONS["chest_flags"]`.

> Repère utile : les adresses proches de celle de l'argent sont
> prioritaires — coffres, requêtes et Médallium vivent dans la même
> structure de sauvegarde.

## 5. Requêtes et Médallium (même méthode)

- **Requêtes** : instantané → terminez une requête → instantané → `diff … 1`.
- **Médallium** : instantané → devenez ami avec un Yo-kai → instantané.

## 6. Associer les bits aux locations

Chaque bit trouvé doit être associé à sa location Archipelago dans
`memory_map.py` :

```python
CHEST_BIT_TO_LOCATION[0x12] = "Les Hauts de Granval - Coffre 03"
```

Protocole : ouvrez les coffres un par un, notez pour chacun le bit qui se
lève (`watch`), la zone et l'ordre. Le client journalise aussi les bits
inconnus (`Bit inconnu chest_flags[18]`) pendant que vous jouez : on peut
donc compléter la table progressivement en jouant.

## 7. Tester

1. Renseignez au moins `chest_flags` et quelques bits dans la table.
2. Lancez le **Yo-kai Watch 2 Client** depuis le Launcher Archipelago,
   connectez-vous au serveur, tapez `/citra`.
3. `/memstatus` affiche l'état du pont ; ouvrez un coffre mappé : le check
   part tout seul.

## Notes

- Un instantané complet couvre `0x08000000-0x0C000000` (FCRAM APPLICATION).
  Si le diff ne donne rien, la donnée est peut-être au-delà : réessayez avec
  `snap nom 0x0C000000 0x4000000`.
- Sur 3DS réelle : Luma3DS > Rosalina (L+Bas+Select) > Debugger > Enable,
  puis `python tools/memory_scan.py --host <IP de la 3DS> --port 4003`.
- `write <addr> <hex>` permet de tester l'écriture (réception d'objets,
  pièges, DeathLink) — sauvegardez avant.

## 8. Livraison des objets reçus (Archipelago → jeu)

Quand le joueur reçoit un objet d'un autre monde, le client l'écrit en
mémoire. Trois cas, selon la nature de l'objet.

### 8a. Consommables / objets d'inventaire (Riz, Thé, EXPorbe…)

Inventaire = tableau d'entrées de 16 octets dès `0x086CC640` :
`[slot u16][type u16][hash u32][quantité u32][ptr u32]`. Recette (voir
`client._deliver_to_inventory`) : si l'objet est présent → +quantité (`+0x08`) ;
sinon créer l'entrée + chaîner le ptr (`0x007FD398`) + incrémenter les compteurs
`0x086CC580`/`+4` + **poser le bit du slot** dans le bitfield `0x086CE154`.
Sans ce bit → crash à l'ouverture du sac.

### 8b. Outils et vraies clés (Filet, Canne, Clé de cabane…)

Liste d'objets-clés séparée, entrées de 12 octets dès `0x086CE918` :
`[ptr=0x007FD860][data][hash]` où `data = ((max_haut+1)<<16) | 0x2000 | index`
(le mot haut est un **ordre d'acquisition**, pas une catégorie). Recette (voir
`client._deliver_to_key_items`) : écrire l'entrée + incrémenter `0x086CC5D8` et
`0x086CC5DC` + **poser le bit du slot** dans le bitfield dédié `0x086CF1B0`.
Validé en jeu : la Clé de cabane livrée ainsi est **fonctionnelle** (utilisable).

### 8c. Items abstraits (rang, vélo, déblocage de régions, chapitres, médailles)

Ceux-là ne s'écrivent PAS comme un objet : leur effet dépend de flags d'état
qu'on ne pilote pas fiablement (ex. le flag de rang `0x086D5922` corrèle mais
ne change pas le rang effectif ; « rouler » = flag d'histoire, pas la
possession du vélo). **Choix de design** : le jeu fournit l'unlock réel
naturellement au bon moment de l'histoire, et Archipelago se superpose —
atteindre ce point = un *check* (détection via chapitre/quête/flag), l'item
reste dans le pool pour la logique. Pas de force-write ; on **détecte**, le jeu
délivre.
