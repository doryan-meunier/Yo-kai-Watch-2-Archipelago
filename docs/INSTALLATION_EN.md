# Setup Guide — Yo-kai Watch 2 on Archipelago

This guide explains how to play **Yo-kai Watch 2: Psychic Specters** in an
[Archipelago](https://archipelago.gg) multiworld, alone or with friends.

> **Supported version: European (FR) 3DS release**, played on the **Azahar**
> emulator. The game itself is not provided — you must own your own copy.

---

## 1. What you need

| Item | Where to get it |
|---|---|
| **Archipelago** 0.5.0 or newer | https://github.com/ArchipelagoMW/Archipelago/releases |
| **Azahar** (3DS emulator) | https://azahar-emu.org |
| Your copy of **Yo-kai Watch 2: Psychic Specters** (EU/FR) | — |
| **`yokaiwatch2.apworld`** | this repository (root folder) |
| A **YAML** configuration file | this repository (see §3) |
| *(optional)* the **PopTracker** pack | this repository, `tracker/` folder |

---

## 2. Install the APWorld

1. Close Archipelago if it is running.
2. Copy **`yokaiwatch2.apworld`** into the `custom_worlds/` folder of your
   Archipelago installation.
   - Windows (standard install): `C:\ProgramData\Archipelago\custom_worlds\`
3. That's it — "Yo-kai Watch 2" will be recognised on the next launch.

---

## 3. Prepare your configuration (YAML)

Pick one of the files in the repository root:

- **`Yo-kai Watch 2 - Story EN.yaml`** — recommended to start with
  (the full story up to Lady Démona, English comments);
- **`Yo-kai Watch 2 - Histoire FR.yaml`** — same thing, French comments;
- **`Yo-kai Watch 2 - Example.yaml`** — every available option, worth exploring
  once you are comfortable.

Open it in a text editor and change at least the `name:` line to your nickname.
Every option is documented inline in the file.

### Recommended settings

| Option | Recommended | Why |
|---|---|---|
| `quest_shuffle` | `true` | requests and services become checks |
| `chest_shuffle` | `true` | every chest becomes a check |
| `tablo_shuffle` | `true` | 19 playable Tablo-blabla (the rest are excluded automatically) |
| `criminel_shuffle` | **`false`** | ⛔ detection is not reliable enough, it can block the run |
| `death_link` | your call | when one player dies, everyone dies |

> ⚠️ **Never disable `quest_shuffle` AND `chest_shuffle` at the same time**:
> too few checks would remain and generation would fail.

Then drop your YAML into Archipelago's `Players/` folder.

---

## 4. Generate and host the game

1. Run **ArchipelagoGenerate** (or `ArchipelagoLauncher` → *Generate*).
2. A `.zip` archive appears in `output/`.
3. Two ways to play:
   - **Online**: upload the `.zip` to https://archipelago.gg/uploads — the site
     gives you an address and port to share (easiest for a group);
   - **Locally**: run `ArchipelagoServer` with the `.zip`. For friends to
     connect you will need to forward the port (38281 by default) on your router.

---

## 5. Enable the emulator link

The client reads the game's memory through Azahar's built-in debugger.

1. In **Azahar**: *Emulation → Configure → Debug*, tick **"Enable GDB stub"**
   and leave the port on **24689**.
2. **Restart the game** for the setting to take effect.
3. Start the game and **load your save** (important: the client needs a loaded
   save, not the title screen).

---

## 6. Run the client and play

1. Open **ArchipelagoLauncher** → **Yo-kai Watch 2 Client**.
2. Connect to the server (address and port), using your **slot name** = the
   `name:` from your YAML.
3. In the client, type **`/citra`** and press Enter.
   - Expected message: *"Attaché au stub GDB (port 24689)"*.
4. Just play! Your checks are sent automatically and received items show up
   in-game.

### Troubleshooting

| Symptom | Fix |
|---|---|
| *"Connexion au stub GDB impossible"* | The stub is not enabled, or the game was not restarted after ticking it. Also make sure no other program is using port 24689. |
| *"Connexion émulateur perdue"* | Type `/citra` again. If it is refused, make a save state, restart the game in Azahar, load the state, then `/citra`. |
| Nothing happens / no checks | Make sure a save is actually **loaded** (not the title screen) and that you ran `/citra`. |
| In-game slowdowns | Check the message after `/citra`: *"Lectures sans pause ACTIVES"* means everything is fine. |

---

## 7. Showing item names in-game (optional)

By default, when a request gives you a reward, the game displays the **original**
item — not the Archipelago item you actually receive.

You can show the **real** name: the client knows how to patch the game's language
archive, provided it is installed as a **LayeredFS mod**.

> ℹ️ **Purely cosmetic.** Without this mod everything works: checks are sent and
> items are delivered normally. Only the reward display changes.
> **Your ROM is never modified** — the client only writes to the copy placed in
> the mods folder.

### Setup

1. Extract `yw2_lg_fr.fa` from the romfs of **your own copy** of the game
   (using a tool such as *3dstool* / *ctrtool*). That file cannot be
   distributed here: it is part of the game.
2. Place it here (create the folders if needed):
   ```
   %APPDATA%\Azahar\load\mods\00040000001B2900\romfs\yw2_lg_fr.fa
   ```
3. In Azahar, make sure mods (LayeredFS) are enabled for the game.
4. Connect the client: it patches the file automatically on connection.

Then, in-game:
- a reward that is a **real game item** → its true name is displayed;
- a reward belonging to **another player** → "**Item AP**" is displayed
  (the exact name stays visible in the client and the tracker).

---

## 8. The tracker (optional but recommended)

1. Install **PopTracker**: https://github.com/black-sliver/PopTracker/releases
2. Copy the `tracker/ykw2-poptracker` folder into PopTracker's `packs/` folder.
3. Open PopTracker, pick the pack, then connect it to the Archipelago server
   (the **AP** button) using the same slot name.

You get a map per area with every check placed, your key items, your watch rank
and live counters. Checks whose item was hinted by another player are
highlighted.

---

## 9. Good to know

- **Save often in-game**: checks are detected in RAM, but your progress itself
  depends on the game's own save.
- **Do not run another debugging tool** (memory scanner, second client…) while
  the client is running: Azahar's debugger accepts **only one connection** at a
  time.
- If you play **offline** for a while, just reconnect the client afterwards: it
  catches up on missed checks once your save is loaded.
