# Détection des boss = via le MÉDALLIUM (insight Doteos 2026-07-13)

Battre un boss l'ENREGISTRE dans le Médallium (icône non-grisée). Donc le bit
"enregistré" du Yo-kai du boss = signal de défaite du boss.

- 1er boss d'histoire (Ch3) = **Grolos, N° 388** (squelette du toit de l'école).
- Zone Médallium (données riches) ~ **0x086e5c-0x086e60** (a changé fort au diff boss).
- C'est la `medallium_flags` (FLAG_TABLES, était (0x0,0x80) = TODO, 128 o = 1024 bits).
- Diff boss (avant/après) sauvegardé : boss_candidates.json (131) ; boss-normal = 90.
  Candidats isolés écartés (listes/données/coffres). Le vrai signal = Médallium.

## À faire (phase 2 / session dédiée)
1. RE la `medallium_flags` (bitfield "enregistré", base à trouver ; bit N = Yo-kai N).
   Réf : Grolos = bit 388. Faire 2 boss -> 2 bits -> déduire base + pas.
2. Mapper chaque BOSS d'histoire -> son N° Médallium -> son bit.
3. Client : détecter le bit du boss -> check "Boss : X". Réactiver BOSS dans le YAML.
Bonus : la même RE détecte l'amitié Yo-kai (yokai_shuffle) si un jour voulu.

## RÉSOLU (2026-07-14) — bitfield boss/medal enregistré TROUVÉ
Via 2 boss consécutifs (Grolos N°388, Méganyan N°389) + before/after diff + intersection :
- **0x086cfeec = 0x30** : bit 4 = Grolos(388), bit 5 = Méganyan(389). CONFIRMÉ (2 boss).
- 0x086cff2c = 0x30 aussi (2e bitfield, 0x40 plus loin ; vu/vaincu ?).
- Mapping : boss N° -> octet (base + N//8), bit (N%8). Base ~ 0x086cfebc (si N°=index, octet48=0x086cfeec).
- ATTENTION : dans/près de la région "chest bitfield" 0x086cfe00 -> c'est en fait une GROSSE
  région de flags (coffres + medallium + events), sous-plages distinctes.
- Phase 2 : mapper chaque BOSS d'histoire -> N° Médallium -> bit. Détecter le bit -> check "Boss : X".
  Confirmer la base exacte avec un 3e boss / en lisant le bitfield complet.
