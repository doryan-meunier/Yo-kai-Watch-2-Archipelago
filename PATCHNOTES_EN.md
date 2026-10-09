# Patch notes: V2 (compared with V1)

V2 is a **complete rebuild**. This document lists what was done, by theme.

## 1. A new technical base

- **The game itself is patched**, instead of a client writing into its memory. A patch of the game's executable
  makes the game give received items, replace chest contents and report checks. The client talks to the game
  through an exchange area in memory.
- **Nothing from the game is distributed.** The patch is applied on your machine, from your ROM, by the launcher. The release
  contains no game byte (an automatic check verifies this when the package is built).
- The game state is **in the save file** (no more "already delivered" file kept on the side).
- No more gap between what the game shows and what happens: what a chest or a shop displays is what is really sent.

## 2. The launcher

- One window, one **Play** button. ROM selection (verified), Azahar detection, one-click install / repair / uninstall of the mod
  (uninstalling puts Azahar's folder back as it was).
- Shipped as an **`.exe`** (no Python to install); a `.pyw` variant exists for people who have Python 3.11+.
- Enables Azahar's "link with the game" (GDB stub) **with your consent**, after a backup copy of its configuration.
- **Archipelago connection** typed in the launcher (server, slot, password; the password can be remembered, encrypted for your
  Windows account), editable mid-game: the client reconnects by itself.
- Live status: client, game, server, save (linked / not linked / other game / mod needs updating).
- French and English interface. Logs reachable (the "Logs" button).
- A **crash recorder**: if the game panics, the client keeps the faulting address and the stack in `plantage.json` for diagnosis.

## 3. Save linking

- An Archipelago game is played on a **new game**: the save is linked automatically.
- A save that was already started is **never adopted**, and a save linked to another seed is **refused**: nothing is received or
  sent, and the launcher says so.
- Safeguards on both sides (the client and the game both re-check).

## 4. Real locks (option `verrous_actifs`)

With a lock enabled, the game **really refuses** the action until the item arrives:

| Lock | Effect |
|---|---|
| Bug Net | lens search points unusable, chapter 1 tutorial included |
| Fishing Rod | fishing closed; usable on receipt; required in chapter 4 (the three-fish request) |
| Model Zero | Model Zero battle interface available on receipt (start of chapter 2) |
| School Keys | school closed, chapter 3 blocked |
| Ancient Herb, Pro Screwdriver | chapter 3 scenes not triggered |
| Mom's Directions | Downtown closed until Mom's hand-over (chapter 4) |
| Treasure Room Key | Duwheel fight not triggered |
| Strange Handle | night use at the Nocturne Hospital has no effect |
| Select-A-Coin | the chapter 2 tutorial Crank-a-kai only accepts this coin (the game itself blocks) |
| **Real watch ranks** | 4 progressive items D, C, B, A: each copy really upgrades the watch; watch doors, requests and story passages require the rank; adds 36 chests |
| **Real Bicycle** | receiving the Bicycle really gives the bicycle (you ride at once); its request becomes a check |
| Anticipated abilities | Rod and Model Zero usable on receipt, without waiting for the game step that normally gives them |

Locks respect scenes already played (late activation is safe).

## 5. Checks

**Chests and key items**
- Golden chests (about 253 with ranks): the content is replaced by the Archipelago item, with a dedicated icon, and the check is
  sent on opening.
- Original spots of key items (about 22): checks. The game's "item obtained" window for checks that have no display of their own.

**Bosses**
- Option `boss`: `histoire` (12), `histoire_et_quetes` (23), and the new **`tous`** mode (29: also Badsmella, Draaagin, Faux Kappa,
  Ray O'Light, Loiter, and Mallice at the end of the Infinite Tunnel).
- The check is sent on victory; with the boss randomizer it stays attached to the place of the fight.

**Baffle Boards**: 25 boards; the check is sent when the board's Yo-kai is called.

**Requests and services**: about 76 requests and 16 services; the quest's item reward is replaced by the Archipelago item in
the result screen.

**Chapters**: chapters 1 to 9 completed and "Rank Up: D".

**Friends** (option `amis`, about 290 checks): wild Yo-kai, evolutions and Yo-kai + Yo-kai fusions; Yo-kai given by the story or
a request; event Yo-kai (each requires its item); evolutions of the Manor guests; 5 fusions with a guaranteed item; 16 army
Yo-kai (with the per-encounter Yo-kai randomizer).

**Yo-criminals**: one check per criminal arrested (52). The one-per-real-week limit is lifted: the next criminal not yet
arrested is offered at will, visible on the 5 town maps, from chapter 3.

**Shops** (option, off by default): the first purchase of each selected item is a check (up to about 285); a maximum price setting
for progression.

**"Long" mystery portals**: checks that need many portals or the Crank-a-kai are flagged in the launcher and never hold
progression.

## 6. Yo-kai and boss randomizers

**Yo-kai randomizer** (computed on your machine from your ROM, identical for every player of the seed):
- Modes `par_rang` and `total` (species swap) and **`par_rencontre_rang`** (default) / `par_rencontre_total` (every Yo-kai of every
  encounter gets its own species).
- **Guarantees**: a Yo-kai required by the game stays findable at each of its original places; every shuffled Yo-kai has a
  "normal place" (not a mystery portal) before the end; no more empty lens points; 16 species that are normally unobtainable are
  added to the pool.
- The shuffle is **versioned** by the seed: a game in progress is never altered by a later improvement.
- Event Yo-kai, bosses, Yo-criminals and the Crank-a-kai do not change.

**Boss randomizer** (option `rando_boss`, off by default): a story or quest boss is replaced by another one, with its script,
music and stats; the place, scenes and check stay those of the original boss.

## 7. Wayfarer Manor, event Yo-kai, Ultramax

- **30 guests**: each has an "Invitation: <name>" item; once received, the Yo-kai arrives at Wayfarer Manor (Blossom Heights), a
  window announces it, and you battle it as often as needed to befriend it (the game's befriend odds).
- **Pandanoko** takes the **reserved Suite** once all request checks are done; the other guests are housed in rooms 101 to 109
  and **keep their room** until they are friends.
- **Invitations are real bag items** (installed by the launcher, icon with the mod logo).
- **Jibanyan S, Komasan S, Komajiro S** (invitations) and **Hovernyan** (Favorite Capsule) appear at their original place before
  the end of the game. Jibanyan S waits until Jibanyan is your friend and the crossroads scene is over (a story-blocking bug
  seen in game was fixed).
- **Ultramax N and K** in the same game, with two checks.
- Event Yo-kai items (Cogs, Seeds, Bells, Moxie Mark) in the pool.

## 8. Crank-a-kai and "of the day" battles

- **Endless Crank-a-kai** (option): the machine never closes (no daily quota, no night closing).
- Battles limited to one per day are **replayable** (19 more than before).

## 9. DeathLink (option `death_link`)

A defeat in the game sends a DeathLink; a received death triggers a real defeat (in battle, through the normal path; on the field, a
window then a return to the respawn point), at a safe moment. Event battles without a defeat penalty are handled.

## 10. Notifications

- "Received: ... / From: ..." banner without interrupting the game.
- The game's "item obtained" windows for checks without a display (Yo-criminals included).
- A chest or a shop shows "item (for player)".
- Text language can be set (`langue_notifications`).

## 11. Built-in tracker (replaces the PopTracker pack)

- **Checks**: list by area (done, available, later, blocked by a given item), filters, received items (and who sent them), optional
  "Spoiler log", no spoilers by default.
- **Map** PopTracker-style: regions, markers, counters, "Chapters N/10" goal, **your position in the game** ("Follow the game"
  checkbox), shops (vendor, building door, items one by one, appearance conditions), **Invitations** section.
- **Yo-kai**: where to find each wild Yo-kai under the shuffle actually applied, **pinning** on the map, moments (day / night, dry /
  rain), mystery portals flagged, favorite food, befriending odds, spoiler hiding.
- **Chat**: Archipelago's text client (coloured messages, chat, `!hint`, `!remaining`... commands, hints).
- The tracker works even **without the game** (server connection only).

## 12. Robustness and game safety

- **Anti-softlock**: an audit replays the game's logic over **200 seeds** (in both rank modes) so that no seed is unwinnable;
  locks are laid so that a player is never trapped in a game state.
- **Memory budget**: the added code is sized not to starve the game of memory (a "memory" crash seen early on was fixed); the build
  refuses a configuration over budget.
- **Low load** on the emulator: the client only reads what it needs, no emulation freezes.
- Connections: the client never closes the link on a protocol error and reconnects by itself.
- V1 seeds are not compatible: generate a new game.

## 13. What disappears from V1

- The old client that wrote into the game's memory.
- The **PopTracker** pack (replaced by the launcher's tracker).
- The options `quest_shuffle`, `chest_shuffle`, `tablo_shuffle`, `criminel_shuffle`, `encounter_shuffle`...: replaced by the V2
  options (see the YAML, everything is commented there).
