# Corrections a appliquer en phase 2 (issues de la capture live, 2026-07-14)

## CADRAGE SCOPE (Doteos, 2026-07-14) — TRES IMPORTANT
1. **Objets-cles checks** = SEULEMENT ceux captures dans l'aventure cette session
   (scratchpad/keyitem_capture.json, 25 entrees) + les objets DONNES PAR LES QUETES.
   NE PAS generer les ~123 checks natifs speculatifs (KEY_ITEM_GAME_ORDER). Reduire
   NATIVE_KEY / KEY_ITEM_GAME_ORDER a cette liste verifiee.
2. **Quetes** = pour l'instant SEULEMENT celles de chapitre <= 10 (avant le post-game
   Ch11 'Danger au vieux Granval'). Filtrer REQUETES/SERVICES sur chap <= 10.
   (Coherent avec le tag story/post-game : post-game exclu si goal = histoire.)
3. **Items donnes par les combats de BOSS et les FINS DE CHAPITRE** = DIFFERE
   ('on verra ca apres'). Ne pas placer d'items sur ces recompenses pour l'instant.


## Items/locations a RETIRER (fantomes / inventes)
- **Yo-kai Cam** : RETIRER du pool + locations. Placement vanilla FAUX
  (VANILLA_KEY_PLACEMENTS['Yo-kai Cam']='Requete: Vrai cache-cache' est faux).
  Doteos: "je sais pas ce que c'est, enleve-le".
- **Cle de la clinique** : RETIRER (item invente). La Clinique du Crepuscule
  n'exige QUE le rang B, aucune cle. regions.py: remplacer
  AccessReq(8,0,('Cle de la clinique',)) par AccessReq(min_chapter=9, combat_rank=3).

## Items a marquer NON-required / exclure du hard-gating
(cf. keyitem_capture.json 'required:false') : Montre etrange, Medallium des Yo-kai,
Cahier de vacances, Indications de Maman, Montre de luxe, Modele zero,
Capsule de lait. -> flags d'histoire, retirer de CRITICAL_KEY_ITEMS.

## Velo
- PAS de check velo separe : 1 velo gratuit (quete 'Sur les traces de Papa',
  deja un check) + autres achetables (boutique, pas des checks). Pas besoin des
  hashes velo. Velo non-required.

## Zones / chapitres corriges (cf. zone_unlocks.json)
- Plaines Plinpot: Ch8 (regions.py avait AccessReq(7,3)).
- Clinique du Crepuscule: Ch9 + rang B, PAS de cle.
- La Corniche=2, Coteau fleuri=3, Quartier boutiques=3, Centre-ville=4,
  Ourcival=4, Mont de l'Ours=4, Ecole nuit=3(Cles), San Fantastico=4,
  Tour Excellence=4, Manoir=rang D, Grotte du littoral=rang C.
- Coteau fleuri: coffres gate rang C (1018,1038) + libre (1037).

## Rangs (chaine progressive, cf. rank_detection.md)
- Detecteur: 0x086d023a (E=0..S=5). D=Ch3, C=Ch6, B=Ch7, A=Ch9. Reste S (post-game).
- Gates quetes: 'Pas le temps de pecher'=rang D, 'Trouvons Sirenee'=rang C,
  Nyada VI=rang A, 'Obtenons le rang X' chaine.

## Detections (phase 2 client)
- BOSS: bitfield Medallium 'enregistre', base 0x086cfebc, bit=N (LINEAIRE).
  Fire a la RENCONTRE. Boss histoire N388-395 (cf. boss_table.json).
- RANG: 0x086d023a.
- GOAL boss final (Lady Demona): compteur chapitre 0x086cfa24 >= 11.
- TABLO: 0x086cfb1c (bits 1-3 = Grotte littoral SEULEMENT ; structure incomplete,
  OPTIONNEL/OFF). Triptic-tac (Tablo#3) hors fenetre -> bit TBD.

## Quetes : reconciliation game_data.py (Supersoluce) vs capture live
- game_data.py REQUETES/SERVICES = (nom, region, chapitres completes requis).
  Certains chapitres Supersoluce != capture live (ex. 'Obtenons le rang C':
  Supersoluce 3 vs live Ch6). REGLE: capture live prioritaire quand dispo,
  Supersoluce sinon. Supersoluce = "quand la quete apparait" (borne basse),
  la completion peut exiger + (rang/items) -> gater sur le max sur pour eviter
  soft-lock.
- CHAPITRES nommes (game_data.py): 1 La montre disparue ... 10 Retour a la normale,
  11 Danger au vieux Granval (post-game).
