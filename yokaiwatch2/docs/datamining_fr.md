# Data-mining de la ROM (RomFS) — Yo-kai Watch 2

Objectif : extraire du jeu la table des coffres (et autres données) pour
auto-générer le mapping `bit de sauvegarde → location Archipelago`, au lieu
de l'établir à la main coffre par coffre.

## Outils (dans `tools/`)

- **`arc0.py`** — parseur des archives Level-5 **ARC0** (`.fa`). Décompression
  LZ10 + Huffman + RLE portée en Python pur. Extrait n'importe quel fichier
  par son nom.
  ```python
  from arc0 import Arc0
  arc = Arc0(r"...\romfs\yw2_a.fa")
  arc.names()               # 33 089 chemins de fichiers
  data = arc.read_file("t101g00_npc_set_0.01b.cfg.bin")
  ```
  Les fichiers sont indexés par **crc32 du nom relatif** (basename).

- **`cfg_bin.py`** — décompilateur des scripts **cfg.bin** Level-5 (config,
  placements, flags). Retourne une liste de `(commande, [paramètres])`.
  ```python
  from cfg_bin import parse_cfg_bin
  for name, params in parse_cfg_bin(data):
      ...
  ```

## Où sont les données (archive `romfs/yw2_a.fa`, 967 Mo)

| Chemin | Contenu |
|---|---|
| `data/res/map/<code>/` | une map par code (`t101g00`, `t106d64`…) : 342 maps |
| `…/<code>_npc_set_*.cfg.bin` | **placement des entités** de la map (coffres inclus) |
| `…/ev_redbox_*.npcbin` | modèle des **coffres** (« redbox ») |
| `data/res/sys/flag_config.cfg.bin` | 1012 flags de scénario (`FLAG_INFO [index, hash]`) |
| `data/res/item/item_config_*.cfg.bin` | table des objets |

## Ce qu'on a compris sur les coffres

- Les coffres sont placés par la commande `NPC_APPEAR ['ev_redbox_00X_YY',
  …, 'ev_cNNN_…', …]` dans le `npc_set.cfg.bin` de leur map. Chaque coffre
  référence un **event** (`ev_cNNN_…`) qui, à l'ouverture, donne l'objet et
  **pose le flag** correspondant.
- **30 coffres `ev_redbox`** recensés dans 7 maps extérieures (t101g00: 8,
  t103/104/106/121g00: 4, t107/131g00: 3). Ce sont les coffres **violets**.
- Les coffres **jaunes** (et ceux des donjons/intérieurs) ne portent pas de
  modèle `*box*` distinct — piste : les `ev_y*` (219 modèles) ou un
  paramètre de couleur sur le même event. **À identifier.**
- Côté sauvegarde (RAM), tous les coffres partagent le bitfield `0x086CFE00`
  (voir `memory_map.py`), 1 bit fixe par coffre.

## Source complémentaire : wiki Fandom (cartes interactives)

Le wiki FR expose des **cartes interactives** (namespace `Carte:`) dont le
contenu JSON liste les coffres par zone avec position et contenu. Récupérable
sans navigateur via l'API MediaWiki (voir `tools/fetch_wiki_chests.py`).

- **Granval** (`Carte:Granval - emplacements`) : **35 coffres violets** +
  **33 coffres jaunes** YW2 (couverture complète). Confirme le comptage de
  Doteos. Violets = « contenu aléatoire », jaunes = « ??? ».
- **Mont Sylvestre** : 14 coffres jaunes documentés (partiel).
- Autres zones (Ourcival, San Fantastico, Pistachburg, Granval-sur-Mer) :
  cartes surtout de navigation, coffres YW2 non détaillés.
- Autres marqueurs utiles comme checks : Yo-criminels, Portails mystères,
  Scientifiborg Y, Verrous de rangs, Boss, Yo-kai exclusifs.

⚠️ **Incohérence à résoudre** : le wiki donne 35 violets sur Granval, mais le
data-mining ne recense que 30 `ev_redbox` modèles au total. Cause probable :
je comptais les *modèles* `.npcbin` uniques, pas les *placements*
(`NPC_APPEAR`) ; et certains coffres (jaunes, donjons) n'utilisent pas le
modèle `ev_redbox`. À réconcilier en comptant les `NPC_APPEAR` de coffres
dans tous les `npc_set` + en identifiant le modèle des coffres jaunes.

## Ce qui reste pour le mapping bit → coffre

1. Identifier **tous** les types/emplacements de coffres (violets, jaunes,
   donjons).
2. Pour chaque coffre : suivre `placement → event → flag posé → index de
   bit`. L'event (`ev_cNNN`) est un script `cfg.bin` de `data/event/` ;
   c'est là qu'est l'ID de flag.
3. Associer chaque index de bit à une location AP (zone + numéro) et remplir
   `CHEST_BIT_TO_LOCATION` dans `memory_map.py`.

C'est un chantier de plusieurs sessions ; les deux outils ci-dessus en sont
la fondation (tout le RomFS est désormais lisible et décompilable).

## ✅ Table des objets : hash → nom FR (pour délivrer les items)

Découverte de la chaîne de résolution complète (2026-07-08) :

```
inventaire (RAM)     hash1 = CRC32 du nom interne (clé écrite dans le sac)
item_config.cfg.bin  hash1 suivi (+4) de hash2 (clé du nom affiché)
item_text_fr.cfg.bin hash2 → offset → nom FR (chaîne courte, sans \n)
```

`tools/extract_item_hashes.py` génère `yokaiwatch2/data/item_hashes.json` :
**889 objets** `{hash1: nom FR}`. Le `hash1` est exactement la valeur du champ
hash d'une entrée d'inventaire (`memory_map.INVENTORY_HASH_OFFSET`), donc pour
délivrer un objet AP il suffit de : trouver son hash par son nom → écrire/
créer l'entrée d'inventaire correspondante (incrémenter la quantité).

Exemples vérifiés : Mini EXPorbe `0x8D447F63`, Riz à la prune `0x6B85C07A`,
Thé de l'âme `0xF585391C`, Hamburger `0x6D4E0291`, Y-Cola `0x6C8C68A6`.

## ✅ Récompenses de quêtes → pool d'items fidèle

`tools/extract_quest_rewards.py` croise `game_data.QUEST_DETAILS` (récompenses
texte du guide) avec la table des objets → `yokaiwatch2/data/quest_rewards.json`
(**87 quêtes/services, 124 objets** avec hash, ~98 % de correspondance).

Objectif (conception « pool fidèle », idée de Doteos) : à la **génération**
(`create_items`), le pool d'items Archipelago devrait être constitué des
**vrais items** que les checks donnaient à l'origine, au lieu de filler
inventé. On a déjà les quêtes ; restent à data-miner le contenu des coffres
(jaunes = fixe probablement ; **violets = aléatoire**, pas d'item unique →
filler/loot représentatif). Beaucoup de récompenses sont « A ou B » : à la
génération on choisira un objet par check.

Rappel : le nombre d'items du pool doit égaler le nombre de locations
activées (options `*_shuffle` du YAML) — la progression reste toujours dans
le pool, le filler s'ajuste.

## ✅ Table des quêtes : hash → nom FR (pour les checks de requêtes)

Quand une quête est validée, le jeu écrit le hash de la dernière quête
terminée à `memory_map.LAST_QUEST_DONE_HASH_ADDR` (0x086CBE74, transitoire).
Chaîne de résolution (RE en jouant + data-mining, 2026-07-09) :

```
RAM 0x086CBE74        hash1 = CRC32 du nom interne de la quête terminée
quest_config.cfg.bin  QUEST_CONFIG : param[1] = hash1, param[6] = hash du titre
quest_title_text_fr   hash du titre suivi (+8) de l'offset -> nom FR
```

`tools/extract_quest_hashes.py` génère `yokaiwatch2/data/quest_hashes.json` :
**147 quêtes** `{hash1: nom FR}`, 0 corrompue, 0 doublon. Croisement avec le
guide : 88/97 quêtes retrouvées (le reste = accents ou libellés internes du
guide). VÉRIFIÉ sur les hash captés en jeu : Courage `0xBA90D102` →
« Courage, Max ! », Spécialiste des cigales `0x9516CE20`.

Format d'une commande cfg.bin : `[crc u32][param_info u16][term u16][params
u32...]` ; les 147 entrées QUEST_CONFIG se repèrent par crc32("QUEST_CONFIG")
= 0x77EF3D06. La commande `QUEST_RSLT_ITEM` (même fichier) donne aussi les
objets de récompense — piste pour fiabiliser `quest_rewards.json` sans le guide.
