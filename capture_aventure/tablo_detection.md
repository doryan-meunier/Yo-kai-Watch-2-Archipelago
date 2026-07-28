# Détection TABLO-BLABLA (2026-07-14) - via intersection 2 Tablos
- **Bitfield "Tablo resolu" : base ~0x086cfb1c** (u8+). Bit = un Tablo resolu.
- Tablo1 (Noripop) = bit 1 ; Tablo2 = bit 2 (consecutifs).
- Methode : diff avant/apres de 2 Tablos + intersection -> 0x086cfb1c seul commun (le reste = bruit Yo-kai/recompense).
- Phase 2 : client monitore 0x086cfb1c+ ; chaque nouveau bit -> check "Tablo-blabla n°NN". Mapper chaque Tablo -> bit en les resolvant.
- Categorie TABLO du monde a reactiver (checks OPTIONNELS, dixit Doteos).
