# Design : distinguer checks HISTOIRE vs POST-GAME (2026-07-14, demande Doteos)

## Le fait
- Battre le boss final **Lady Demona (N395)** fait passer le compteur chapitre
  `0x086cfa24` de **10 -> 11**. => **Histoire principale = Ch1..10 ; Post-game = Ch11+**.
- Le post-game contient : Tunnel sans fin, Limbes eternelles (boss **Potofeu**),
  Paradis divin (boss **Filomene**), + legendaires/fusions/evolutions tardives, etc.

## Le probleme (Doteos)
> "faudra differencier les checks histoire de ceux post-game, notamment si on
> choisit comme goal Lady Perpetua/Demona le post-game ne sert a rien."

Si le GOAL = battre le boss final (Lady Demona, defaut), alors **tout le post-game
est APRES le goal** :
- Aucune location post-game ne doit porter d'objet de **progression** (sinon item
  requis places au-dela du goal = injouable / soft-lock logique).
- Idealement les checks post-game sont **exclus du seed** quand le goal est
  l'histoire (sinon = checks "morts" que le joueur doit faire APRES avoir gagne,
  sans interet).

A l'inverse, si le GOAL exige le post-game (ex. **Potofeu**, **Filomene**,
**all_legendaries**), alors les checks post-game **doivent** etre inclus et
atteignables (progression OK jusqu'au boss-goal correspondant).

## A implementer (phase 2)
1. **Taguer chaque location** avec un flag `post_game` (bool) ou un `min_chapter`.
   Seuil : `min_chapter >= 11` => post-game. (Story = 1..10.)
   - Boss : Potofeu, Filomene = post-game. Grolos..Lady Demona (388-395) = histoire.
   - Zones : Tunnel sans fin, Limbes eternelles, Paradis divin, Gera Gera Land(?),
     Repaire de Lady Demona = post-game/fin. A confirmer par zone.
   - Coffres/quetes/rang S : ceux debloques Ch11+.
2. **Selon l'option Goal** :
   - Goal = boss final / histoire (Lady Demona, chapitre>=11 comme detecteur) :
     -> EXCLURE les locations post-game du pool (ou au minimum les forcer EXCLUDED
        = filler only, jamais de progression).
   - Goal = Potofeu / Filomene / all_legendaries :
     -> INCLURE le post-game ; la logique gate ces locations derriere chapitre>=11
        + les prerequis (Cle Paradis divin, rang, etc. cf. regions.py BOSS_EVENTS).
3. **Detecteur de goal** deja resolu : boss final = `chapitre>=11`. Les goals
   post-game (Potofeu/Filomene) auront leur propre detecteur (bit registered ou
   flag, a capturer en post-game).

## Lien code
- `regions.py` : REGION_NAMES a deja "Tunnel sans fin", "Limbes eternelles",
  "Paradis divin", "Repaire de Lady Demona" ; BOSS_EVENTS a Lady Demona/Potofeu/
  Filomene avec AccessReq(10,...). -> Passer ces AccessReq a min_chapter=11 pour le
  post-game, et conditionner l'ACTIVATION des locations post-game a l'option goal.
- `options.py` : Goal (option_all_legendaries existe deja). Ajouter/valider les
  goals boss (Lady Demona=defaut, Potofeu, Filomene) + la logique d'inclusion
  post-game.
