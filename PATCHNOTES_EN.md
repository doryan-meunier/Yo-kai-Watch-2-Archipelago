# Patch notes: V3 (version 3.0.0, compared with V2)

V3 adds the **postgame**, new goals, many new key items and locks, new kinds of checks and new shuffles. Everything new
is **set in the YAML**; the default settings stay close to V2. This document lists what is new, by theme.

Two YAML templates are provided per language: the **default settings** (with every real lock) and an **"everything
on"** template (over 1,400 locations). Lists are written as arrays (`[a, b]`), and every option is explained in the
file.

## Compatibility

- **A game generated with V2 can still be played with the V3 launcher**: the launcher recognises it and adds nothing
  to it (same checks, same Yo-kai and boss shuffle, same guests; no V3 feature turns on). Save **in the game** before
  updating the launcher (no Azahar save state from another build). If you were playing on Azahar, keep Azahar for that
  game (see "PC version" below: Zakuro's save files are kept separately).
- **A game generated with the V3 APWorld needs the V3 launcher.** An older launcher cleanly refuses a game that needs
  a feature it lacks ("the installed game lacks some locks of this seed"): nothing is linked or sent. Every Yo-kai Watch 2 player of the
  multiworld therefore needs to move to V3.
- The French and English worlds still play in the same multiworld.
- The English world's YAML is entirely in English (option names, values, lock keys); a YAML using the French names
  still works (a simple warning gives the English name of each option).

## 1. New goals (option `goal`)

- **`defeat_wobblewok`**: finish the story, then defeat Wobblewok at the bottom of the Infinite Inferno (needs the
  Shack Key, shuffled into the game).
- **`defeat_kat_kraydel`**: finish the story, then defeat Kat Kraydel at the end of the Divine Paradise.
- **`defeat_kabuking`**: finish the story, then defeat Kabuking at the Kaibuki Theater (Hexpress Pass for the Gera
  Gera train, Rank S, then the three resort requests).
- **`complete_medallium`**: finish the story, then fill the Medallium up to the chosen number (`medallium_target`,
  448 = all). All 448 entries have a way the logic accounts for; it is a very long game (around a hundred hours). This
  goal turns on by itself everything it needs (full postgame, friends, bosses, guests, special coins...).
- Victory is sent once the boss is **defeated, wherever it is** (with the boss randomizer it may have moved) and the
  story is finished. `finish_chapter_10` (default) stays the V2 game, without the postgame.

## 2. Postgame (option `postgame`)

- `required`: the checks **on the way to the goal** (golden chests of the Infinite Inferno and the Divine Paradise,
  bosses on the way; for Kabuking, the Rank S request, the Gera Gera train's chests and requests).
- `full`: plus **the whole postgame** of the enabled types: 99 golden chests (Yo-kai World, Hexpress resorts, Sawayama
  Castle, Mystery Way, Rank S corners...), 31 requests and 4 services, 8 bosses, Baffle Board #24, 18 friends (the
  legendaries among them). Anything off the way to the goal only holds filler.
- Shuffled **access items**: Shack Key, Yo-kai World Key, **Hexpress Pass** (the Gera Gera train opens as soon as it
  is received, and the request "Getting to Gera Gera" is offered right away), Happy-Go-Lucky Pass, Boo Bundle, Key to
  Apt. A-203 / B-102, and the **four Mystery Way keys** (the door in San Fantastico and its three branches).
- Sawayama Castle and its requests join the game.

## 3. YO-KAI WATCH Blasters mode (option `blasters_mode`)

- One check per cleared **Psychic Blasters stage** (you play alone by hosting a group).
- `early`: Gargaros and Sproink; `all`: also the long stages (filler), those of Rubeus J and Hardy Hound (with their
  "Friend" checks) and the postgame ones.
- Slimamander's stage asks for 30 Yo-kai photos taken with the console camera (impossible on an emulator): the modded
  game counts them as taken, without writing anything to the save. Hinozall's stage and its "Friend" check become
  possible.
- Rubeus J's and Hardy Hound's stages come from the other editions of the game: alone, this edition never shows them.
  The modded game makes them playable alone when the game has their checks.
- **One item per stage** (option `blasters_stage_unlocks`, off by default): twelve "Stage: <boss>" items; a stage opens
  as soon as its item is received, and only then (no more Oni Orbs, photos or other conditions). Gargaros and the
  Triple Boss Rush stay open. All 13 stages (and the "Friend" checks of Hinozall, Rubeus J and Hardy Hound) become
  regular checks from chapter 4, which may hold required items.

## 4. New key items and locks (option `active_locks`)

As in V2, a lock is **real**: the game truly refuses the action until the item is received, and an item received
"late" never blocks the game. The YAML templates turn them all on (31).

| Item | Without the item |
|---|---|
| **Yo-kai Watch** | in battle, the Pin, Soultimate and Purify buttons are closed (required from chapter 3 and by every boss) |
| Critical Lost Item | Dad does not take it back (chapter 7 request) |
| Moximous Game | Gnomey does not come (chapter 6 request) |
| Komasan's Letter, Mysterious Marble | the two mandatory chapter 5 requests cannot be completed |
| Swirly Bell, Top-Notch Watch | the scene that ends chapter 5 waits for both |
| Milk Bottle Tops | required from the end of chapter 9 (chapter 10 is played in a sealed-off town) |
| **Mirapo** | no warp mirror appears |
| Muscle Belt, New Retro Robot, Old Retro Robot, Fluffy Towel, Dance Revolution | the optional request that asks for it cannot be completed |
| Stamp Card | no station stamps |
| **Train Pass** | station ticket gates shut: no Harrisville, no San Fantastico, the story stops in chapter 4 |
| **Time Travel** | every way into the past is shut (the ways back, never); required from the end of chapter 5 |
| Key to Apt. C-302 | (fixes a V2 oversight: the key exists in the game again) |
| Blue Card Key | (with the watch ranks: its chest becomes a check, the key joins the pool) |

Each V3 key item also has its "Key Item: ..." check at its vanilla spot ("Time Passage" for time travel). A separate
option, **`scrolls`**, adds the game's three Scrolls (normally given through QR codes) to the pool. The "Key Item:
Yo-kai Watch" check is sent in the chapter 1 shop, when the item window shows the location's item instead of the
Strange Watch.

**Watch rank S** (`watch_ranks` lock, with a postgame goal that has rank S checks): a **5th "Watch Rank"** joins the
pool and gives **rank S** once the story is over (received earlier: the watch reaches rank S at the end of the story).
The "Go for Rank S!" request is then only a check. The launcher tracker shows "S" at the 5th copy.

**Pocket Mirapo** (value `pocket_mirapo`, **off by default**, not in the default template: add it to the list; on in
the "everything on" template): the Mirapo item becomes two "Progressive Mirapo" items. The 1st opens the mirrors
(like the Mirapo item); the 2nd gives the **Pocket Mirapo**: **hold SELECT ~0.5 s** in the field to open the mirror
menu anywhere, with every mirror you have registered. It is refused in dungeons, stations, the past and the Yo-kai
World, during a scene or a dialogue, when the story itself shuts the mirrors, and in the area where the story keeps
you (Harrisville, for example): the game then says "The Pocket Mirapo doesn't respond here" and gives the reason. A
banner reminds you of the button when you receive it. With the Pocket Mirapo, SELECT no longer pauses the game in
the field (the console usually treats it as START): START still pauses. Nothing requires it.

**Items in the bag** (with the game-item install, on by default): the Train Pass, Time Travel and Mirapo show up in the
Key Items tab when you receive them. With the 2nd Progressive Mirapo, the "Mirapo" item is replaced by "Pocket
Mirapo" (compact-mirror icon, also in the launcher tracker). With the Gate Dungeon Keys, a single "Gate Dungeon
Keyring (n/5)" item follows the keys you received: it is swapped at each key, and its description lists the open
doors. These items are for display only (the locks work from the Archipelago items received). They have hand-drawn
icons.

## 5. Save-transfer requests (option `save_transfer_requests`)

The **ten requests** that normally only exist after importing a Bony Spirits or Fleshy Souls save are offered **all
ten in the same game**, without any transfer (six before the ending, four after), with the "Friend" checks of the
Yo-kai they give.

## 6. Guests, special coins and the Medallium

- **Wayfarer Manor guests** now arrive in the **order you receive their invitations**. With the Medallium goal, the
  16 army Yo-kai become guests too.
- **Special Crank-a-kai coins** (option `special_coins`): the coins the game only gives through QR codes, passwords or
  online play join the game (16 Five-Star Coins, Flower Excitement Coins, the 9 Traveler's Coins, Select-A-Coin,
  Select-A-Coin +, fusion items of the regional Yo-kai). Each coin **always gives a Yo-kai you are missing** (never an
  item, never a duplicate); the Five-Star Coin order is drawn for the seed and shown by the launcher. A wasted coin
  (full team) is given back. One more Light-Blue Coin gives Bananose, and it can no longer be sold.
- **Shuffled legendaries** (option `shuffled_legendaries`): each Medallium seal gives **another** legendary Yo-kai;
  the eight Yo-kai each seal asks for do not change, and nothing obtainable becomes impossible.

## 7. Yo-kai shuffle

- The shuffle now also covers **trapped chests**, **trains**, **gym missions**, **story places** and Yo-kai
  **spots**; with a postgame goal, the postgame wild Yo-kai too. Far more different Yo-kai from the start of the game.
- The **lens** shows the shuffled Yo-kai as soon as the shuffle is applied, without changing maps.
- **Requested Yo-kai zones** (option `requested_yokai_zones`): every Yo-kai a request, a Baffle Board or a service
  asks for is placed in a **zone drawn for the seed** (at least two spots of that zone); the logic accounts for it and
  the launcher shows "guaranteed at <zone>".
- The launcher explains the state of the shuffle ("Archipelago connection" card) and why a place kept its original Yo-kai
  ("Yo-kai" tab). When the game's logic depends on a shuffle (requested Yo-kai zones, postgame bosses) and it is not
  ready yet (ROM to pick in the launcher, for instance), the game waits: nothing is linked or sent, then it resumes by
  itself.
- **Shuffled Crank-a-kai** (option `shuffled_crank_a_kai`): the Yo-kai given by the ordinary Crank-a-kai coins are
  shuffled among themselves; each one stays obtainable at the same machine with the same kind of coin. The launcher
  says what each coin can give.

## 8. Bosses

- With a postgame goal, the **postgame bosses are shuffled among themselves** (never with the story ones); the shuffle
  is drawn at generation, and the goal boss may move.
- **Mystery Way bosses** (Goldy Bones, Retinado, Hans Galore, Glitzy Bones): when the Mystery Way is part of the game
  (`postgame: full`, or the "complete the Medallium" goal), they are shuffled like the other postgame bosses: among
  themselves with `boss_randomizer: same_class`, with the Infinite Inferno and postgame request bosses with
  `boss_randomizer: full` (among themselves with the Medallium goal, so that the coin of each Mystery Way machine,
  dropped by the boss of its line, can be earned again on every run). A "defeat X" goal boss is never put on the
  Mystery Way. Their four places have a check "Boss: Goldy Bones", "Boss: Retinado", "Boss: Hans Galore", "Boss:
  Glitzy Bones", sent when you defeat the boss found there.
- **Adapted strength** (option `shuffled_boss_strength: adapted`): a moved boss takes the strength of the original boss
  of its place (a late boss placed early is no longer unbeatable, a weak boss placed late is made stronger). The goal
  boss always keeps its own strength.
- Checks for the postgame bosses, including the places with no marker in the save (the check is sent with the
  occupant's Medallium entry).

## 9. New checks

- **Vending machines** (option `vending_machines`): 108 checks, the first drink of each button of each of the 54
  machines.
- **Postgame shops** (with `shops` and the full postgame): the Sawayama Castle village shop and the fixed items of the
  Happy-Go-Lucky Express shop (the golden train).
- **Key requests only** (option `quests: key_requests`): only the 23 requests the story requires (chapters 2 to 7
  and 9) are checks; the other requests are not.

- **Gate Dungeon Keys** (option `gate_dungeon_keys`, off by default): five items, one per orb door of the Gates of
  Whimsy dungeon in Breezy Hills; the dungeon's chests 01 to 03 become regular checks (chests 04 to 10, Eyephoon and "The
  Final Gate" stay out of progression: the way there requires calling Baffle Board Yo-kai, or the logic cannot
  guarantee access).

## 10. Comfort

- **More varied filler** (option `filler`): besides the 12 consumables of V2 (default), all the game's food (74
  items), the 74 equipment items and the 16 books, as you choose (list of families).
- **Adjustable money**: amounts of money items (option `money_amounts`, from 10 to 5,000 euros; default 100 and 500)
  and form (option `money_form`): euros (default), dolls to sell in a shop (iron, bronze, silver, gold, platinum: 3 to
  600 euros), or both.

- **Infinite Tunnel without the daily limit** (on by default).
- **Rematches without the daily limit**, and Mystery Way bosses on every run (option `rematches_no_daily_limit`).
- **Mystery Way directed draws**: its machines always give the Yo-kai you are missing (option
  `mystery_way_directed_draws`).
- **More frequent golden train** (option `golden_train_frequency`: 2, 3 or 4 times in 10 instead of 1).
- **Befriending chance** (option `befriending_chance`): normal, x2, x4 or guaranteed. It does not change who can be
  befriended, and there is still one new friend per battle at most. With "guaranteed", if you fed one of the
  defeated Yo-kai, that one becomes your friend; then a Yo-kai that is not your friend yet (Medallium) is preferred;
  then the rarest, as in the original game. The Mystery Way Oni (Gargaros, Ogralus, Orcanos) are not recruited through
  end-of-battle befriending but through a random gift after the win (5% or 3%): with "guaranteed", that gift is
  guaranteed at the first win (Oni not yet a friend, room in the team). Terror Time Oni and the trap's Oni never
  become friends, as in the original game.
- **DeathLink**: a lost game of Terror Time or Blasters also counts as a death (one per game), only for games
  generated with V3.

- **Random Gate Rewards** (option `random_gate_rewards`, off by default): the chest at the end of a Gate of
  Whimsy gives a game item picked for the seed (food, healing, Exporbs, books, equipment), besides the usual orbs.

- **Traps** (option `traps`, off by default, on in the "everything on" template; share set by `trap_share`, 10% by
  default): part of the filler items become traps, sent to your world like any other item: surprise battle, loss of 10% of your money, watch static
  (radar off for 5 minutes), rain (5 minutes), half HP at the next battle, wheel shuffle (the wheel spins by itself,
  then stays locked for 30 seconds), battle against an Oni matched to the team's strength (no escape; winning gives
  the experience and money of an ordinary Yo-kai). Each trap has its own weight (`..._trap_weight` options, relative: a sum
  of 100 gives percentages). A trap only acts at a safe moment (free field, or the next wild battle), is announced by
  the banner, and never costs a check. A game with traps needs the launcher that can receive them. A trap received
  but not yet triggered when you close the game comes back at the next launch. Once the seed's goal is reached, traps
  have no effect any more: those that arrive afterwards (when the other players release or collect) are announced
  "Trap skipped", and those still waiting for their moment are removed (rain and watch static in progress stop, back
  on the field). Other items are given as before. The goal is remembered from one launch to the next.

- **EXP Multiplier** (option `exp_multiplier`, off by default, on in the "everything on" template): three
  "Progressive EXP Multiplier" items (useful) replace three filler items. All the EXP your Yo-kai earn (won
  battles, request rewards, EXP items) is multiplied by 2 with the first one received, by 3 with the second, by 4
  with the third; the screens show the multiplied value. Money and items do not change. No logic rule depends on
  them. The current tier shows in the bag ("Key Items"): "EXP Multiplier x2", then x3 and x4, which replaces the
  previous one with each copy received.

- **Starting items** (option `starting_items`, empty list by default): the game starts with the chosen items, for
  example `starting_items: ["Bicycle", "Train Pass", "Watch Rank"]` (APWorld names, in English or in French, in
  double quotes). Each name removes one copy of the item from the world (a filler item takes its place) and gives it
  from the start, like a received item; logic counts it as already owned. One mention = one copy ("Watch Rank"
  twice: ranks D and C). An extra mention, an item the game does not put in the world (a key item without its lock,
  an option that is off) and traps are ignored, with a warning at generation; an unknown name stops the generation.

## 11. Spoiler file

Archipelago's spoiler file has a Yo-kai Watch 2 section: boss shuffle (and where the goal boss is), legendaries (seal
→ legendary), Five-Star Coin order, requested Yo-kai zones, traps (effective percentage of each trap). The wild Yo-kai shuffle, the Crank-a-kai shuffle and the
adapted boss strength are computed on the player's side from their ROM: the launcher shows them ("Yo-kai" tab).

## 12. PC version (built-in Zakuro)

- The launcher can ship **Zakuro**, a 3DS emulator that runs the game as **PC code**: the game is prepared once on
  your computer, from your ROM. The first preparation takes a few minutes (about 4 minutes on a recent PC, longer on a
  more modest computer) and may download a compiler of about 100 MB. After that, the prepared game is kept: later
  launches have nothing to redo, and after a mod update only what changed is redone (usually under a minute).
  Nothing from the game is distributed.
- When Zakuro is shipped, it is the default emulator ("2. Emulator" card of the launcher). **Azahar is still
  available**: "Browse..." `azahar.exe` in that card (and `zakuro\zakuro.exe` from the launcher folder to go back to
  Zakuro).
- Zakuro's save files are **separate** from Azahar's (in `%APPDATA%\ykw2-ap\zakuro`, kept when you update the
  launcher): a game started on Azahar continues on Azahar.
- **"Settings"** tab in the launcher, **"Zakuro"** sub-tab: game language, resolution, frame interpolation, window
  size, screens, filter, sound of Zakuro. Applied the next time Zakuro starts.
- **Screens' place**: in Zakuro's window, full screen included, the game's screens can sit against the left or right
  edge instead of in the middle, to put the launcher in the free room (Settings → Zakuro, or Esc → Settings →
  "Screens' place"). Clicking the bottom screen with the mouse follows the screens.
- **Blasters**: Blasters can be played alone on the PC version, with no room and no connection (Yo-kai Pad →
  Blasters → create a group, then start with no guest). Before, the app said that wireless communication was off, or
  disconnected the game at the start.
- **Controllers**: Zakuro reads PlayStation, Xbox and Switch controllers, over USB or Bluetooth, even when its window
  is not in front. `zakuro\tester_manette.cmd` (in the launcher folder) shows what Zakuro sees of a controller.

## 13. Launcher and tracker

- **Autocomplete in the console** ("Chat" tab): typing `!` lists the commands; after `!hint ` or
  `!hint_location `, it lists item or location names from your game, as the Archipelago client does. Arrows to
  choose, Tab or Enter to complete, Esc to close.
- **Friendship window in battle** (checkbox in the **"Settings" → "Game settings"** tab, off by default, with Azahar
  as well as with Zakuro): a small transparent window, on
  top of the game, tells for each enemy Yo-kai whether it is already your friend; hidden outside battles, movable.
- Item column: a single **"Gate Dungeon Keyring (n/5)"** box for the 5 Gate Dungeon Keys (the tooltip tells which
  doors are open), and a single box for the **Progressive Mirapo**: "Mirapo", then "Pocket Mirapo" with the
  second copy.
- **Magnifier window** ("Settings" → "Game settings", off by default): when the watch radar targets a spot, a
  small transparent window names the Yo-kai you will fight there and tells whether it is already your friend.
- **Recent items window** (same place): the last items received and sent, cleared after an adjustable delay.
- **Keep the launcher on top** (same place), without taking the input away from the game.
- **Random music** (same place, unchecked by default): the game's music tracks are shuffled among themselves
  (field, battles, scenes), with no outside music; applied on the next "Play", a new shuffle every time the box is
  checked again. Jingles, rhythm games and language-specific songs keep their music. Purely cosmetic: no effect on
  the Archipelago game.
- **Hero appearance** ("Settings" → "Appearance"): official outfits, sepia tones or a free colour for Nate and Katie,
  with a preview; a few hidden outfits of the game (marked "experimental"); import of an appearance mod you already
  have (zip or folder). Applied on the next "Play", purely cosmetic.
- Map: **"What to do now?"** button: accessible checks, starting with the map you are on.
- Map: the "Map:" list filters as you type (case and accents ignored).
- Map: the door of a building whose shopkeeper is not there yet is no longer "accessible"; night-only shopkeepers
  are shown absent while the story does not let you go out at night yet.
- **Special coins** (icons, count, next Yo-kai) and **Legendaries** sections on the tracker map; "Crank-a-kai" places
  and "guaranteed at <zone>" in the "Yo-kai" tab; "Bosses" view with the applied strength. Yo-kai that the game gives
  without an encounter (guests, special coin Yo-kai, regional fusions) have their row there too, with their location.
- Clear messages when a game is waiting or blocked (shuffle being prepared, ROM to pick, mod to update); exact names
  of what is missing when a launcher or an installed game is too old.

- **Launcher updates**: at startup, the launcher checks whether a newer version exists (a plain request to the public
  repository, no data sent; checkbox in "Settings" → "Game settings"). With the exe, the "Update" button downloads
  and checks the package, replaces the files and restarts the launcher; if that fails, the old version stays in
  place. Refused while the game, Azahar or Zakuro are open. `.pyw` package: an alert with a link. The V2 launcher does
  not have this system: moving from V2 to V3 is done by hand.

## 14. Fixes compared with V2

- **Key to Apt. C-302**: in V2 this key had vanished from the game (its chest had become a check); with the
  `key_to_apt_c_302` lock it is back in the pool.
- **Underground Waterway**: chests 10 and 11 require the Ancient Herb and the School Keys (only reachable from
  Shopper's Row), chests 12 and 13 the School Keys (entered from Blossom Heights), and the "Red Card Key" key item
  (behind the ten gates) 3 chapters, Select-A-Coin, Mom's Directions, the Herb and the Keys.
- **Springdale Business Tower floors** (3rd, 12th and 13th): the elevator only opens them once the Yo-kai of Baffle
  Board #11 has been summoned, which the logic cannot guarantee; their chests and the "Unkeen: Origins" request now
  only hold filler (new games; a V2 game keeps its placement).
- **Harrisville village bus** (chapter 4): while the Fishing Rod or the first Watch Rank ("real rank" mode) is
  missing, the village bus to the station is no longer refused from 4-110 to 4-135: you can fetch the item elsewhere
  and come back with the station bus (original fare). Without the lock, or once the item is received, nothing changes.
  The bus is also given back while request 99 (defeat 3 Pachycoul) is accepted and not finished: with the Yo-kai zone
  shuffle, Pachycoul may only be found in Springdale.
- **Downtown construction site**: the requests "The Bear Boy Returns" and "The Phantom Giant" (and so "Ultimate Bear
  Boy", "Collection Correction", the Massiface boss and the phantom giant chests) no longer wait two or three real
  days after calling the Yo-kai of Baffle Board #9: the site is finished as soon as it is called.
- Logic: the **Catwalk** chest requires chapter 1 completed and the Select-A-Coin; the **Old Uptown "Ch.10 return"**
  chest is only expected after chapter 10 (filler only when the goal is finishing chapter 10).
- **Baffle Boards**: the check is sent when the board's Yo-kai is SUMMONED, which requires owning it. The logic now
  waits for both the board and that Yo-kai (where it is found, the items to get there, the watch rank the lens
  needs): for example board #2 is no longer announced before the Excellent Tower (chapter 6). New games: board #4
  only exists with the `save_transfer_requests` option (its Yo-kai only comes from a save-transfer request), board #25
  only with its event item and the "Friend" checks (the item is required by its rule), and board #23 only in the
  complete postgame (its Yo-kai, a legendary, needs a rank S member).
- Logic: the last three items of the **Shopper's Row** convenience store (N004, `all` mode) are only sold after the
  **Baffle Board #12** Yo-kai; their rule now waits for that board.
- Logic: the 13 chests of **Springdale Elementary School (night)** open as soon as the story night of chapter 3 (step
  3-190); their rule no longer waits for the end of chapter 3, but for chapter 2 finished plus the **School Keys**, the
  **Ancient Herb** and the **Pro Screwdriver** (with the Yo-kai shuffle by zones: also the zone of the Yo-kai of the
  chapter 3 request).
- Logic: a key item that stops the story (Critical Lost Item, Komasan's Letter, Mysterious Marble, Milk Bottle Tops,
  Moximous Game, Fishing Rod…) is no longer required by the checks you can do BEFORE the point where the story stops
  without it (about 280 checks, mostly requests and chests). The end of the chapter and the request that asks for the
  item still require it. The Yo-kai Watch Model Zero does not stop the story: the logic no longer requires it.
- For a game generated with V2, the launcher tracker also shows these corrected logic rules (except the Business
  Tower one).
- "Item obtained" windows: items of your own world that have a picture (invitations, Train Pass, Time Travel, Mirapo,
  Gate Dungeon keys, Hexpress Pass, Mystery Way keys) now show it instead of the Archipelago logo, with the same name.
  Without the mod's items installed: the logo, as before.
