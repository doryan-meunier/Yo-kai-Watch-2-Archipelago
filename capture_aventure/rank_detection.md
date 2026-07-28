# Détection du RANG de montre (2026-07-14)
Via before/after de l'upgrade rang D -> C :
- **Adresse du rang : 0x086d023a** (u8). Valeur = rang : E=0, D=1, C=2, B=3, A=4, S=5.
- Confirmé : passe de 0x01 (D) a 0x02 (C) a l'upgrade. **Confirme aussi C=2 -> B=3 (Ch7) et B=3 -> A=4 (Ch9) en direct.** Chaine E->D->C->B->A validee empiriquement (reste S a capturer).
- Le vieux 0x086D5922 (memory-map, "correle mais ne pilote pas") n'est PAS le bon.
- Changements secondaires a 0x086d0262-0x086d026c (structure liee, ignorer).
## Usage phase 2
- Client : lire 0x086d023a ; a chaque increment -> check "Obtenons le rang X" (D->C->B->A->S).
- Rangs captures par chapitre : D=Ch3, C=Ch6, B=Ch7, A=Ch9.
