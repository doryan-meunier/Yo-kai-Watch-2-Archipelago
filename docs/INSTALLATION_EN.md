# Setup Guide — Yo-kai Watch 2 on Archipelago (English)

This guide explains how to play **Yo-kai Watch 2: Psychic Specters** in an
[Archipelago](https://archipelago.gg) multiworld, alone or with friends, with
**every location and item name in English**.

> **Supported version: European 3DS release**, played on the **Azahar**
> emulator. The game itself is not provided — you must own your own copy.

> **Two versions exist.** `yokaiwatch2en.apworld` is the game
> **"Yo-kai Watch 2 (English)"**; `yokaiwatch2.apworld` is the French one,
> **"Yo-kai Watch 2"**. They are the same world — same logic, same checks, same
> IDs — only the displayed names differ, and **both can take part in the same
> multiworld**. This guide covers the English one; for the French version see
> [INSTALLATION_FR.md](INSTALLATION_FR.md).

---

## 1. What you need

| Item | Where to get it |
|---|---|
| **Archipelago** 0.6.0 or newer | https://github.com/ArchipelagoMW/Archipelago/releases |
| **Azahar** (3DS emulator) — **version 2124.3 recommended** | https://github.com/azahar-emu/azahar/releases/tag/2124.3 |
| Your copy of **Yo-kai Watch 2: Psychic Specters** (EU) | — |
| **`yokaiwatch2en.apworld`** | this repository (root folder) |
| **`Yo-kai Watch 2 (English) - Story EN.yaml`** | this repository (root folder) |
| *(optional)* the **PopTracker** pack | this repository, `tracker/ykw2en-poptracker` |

---

## 2. Put the game itself in English

The European cartridge contains **all seven languages** in one build, and the
game follows the **console's system language**. So:

1. In **Azahar**: *Emulation → Configure → System*.
2. Set the language to **English**.
3. Restart the game.

Nothing else changes — the memory addresses are identical in every language, so
the client works the same way.

---

## 3. Install the APWorld

1. Close Archipelago if it is running.
2. Copy **`yokaiwatch2en.apworld`** into the `custom_worlds/` folder of your
   Archipelago installation.
   - Windows (standard install): `C:\ProgramData\Archipelago\custom_worlds\`
3. That's it — **"Yo-kai Watch 2 (English)"** will be recognised on the next
   launch. You can keep `yokaiwatch2.apworld` next to it; the two games coexist.

---

## 4. Prepare your configuration (YAML)

Use **`Yo-kai Watch 2 (English) - Story EN.yaml`** from the repository root. It
plays the whole story up to Dame Demona; the post-game is not part of this
version.

> The file **must** declare `game: Yo-kai Watch 2 (English)`. If you start from
> a French YAML instead, generation will fail with *"No world found to handle
> game …"*.

Open it in a text editor and change at least the `name:` line to your nickname.
Every option is documented inline in the file.

### Recommended settings

| Option | Recommended | Why |
|---|---|---|
| `quest_shuffle` | `true` | requests and services become checks |
| `chest_shuffle` | `true` | every chest becomes a check |
| `tablo_shuffle` | `true` | 19 playable Baffle Boards (the rest are excluded automatically) |
| `criminel_shuffle` | **`false`** | ⛔ detection is not reliable enough, it can block the run |
| `death_link` | your call | when one player dies, everyone dies |
| `encounter_shuffle` | your call | **randomizer**: shuffles wild Yo-kai (see §9) |
| `boss_encounter_shuffle` | your call | shuffles bosses among themselves (see §9) |

> ⚠️ **Never disable `quest_shuffle` AND `chest_shuffle` at the same time**:
> too few checks would remain and generation would fail.

Then drop your YAML into Archipelago's `Players/` folder.

---

## 5. Generate and host the game

1. Run **ArchipelagoGenerate** (or `ArchipelagoLauncher` → *Generate*).
2. A `.zip` archive appears in `output/`.
3. Two ways to play:
   - **Online**: upload the `.zip` to https://archipelago.gg/uploads — the site
     gives you an address and port to share (easiest for a group);
   - **Locally**: run `ArchipelagoServer` with the `.zip`. For friends to
     connect you will need to forward the port (38281 by default) on your router.

---

## 6. Enable the emulator link

The client reads the game's memory through Azahar's built-in debugger.

> ⚠️ **Azahar version: 2124.3 is recommended.** The 2125.x builds proved
> unstable with the client (the GDB stub stops answering while the game runs:
> micro-freezes then disconnection loops); 2126 fully rewrites the stub and is
> untested yet. If you get repeated disconnections, installing 2124.3 fixes it.

1. In **Azahar**: *Emulation → Configure → Debug*, tick **"Enable GDB stub"**
   and leave the port on **24689**.
2. **Restart the game** for the setting to take effect.
3. The game **freezes at boot**: this is normal — with the stub enabled it
   waits for the debugger. The client's `/citra` command (next step) is what
   releases it.
4. Once the game is running, **load your save**: the client delivers nothing
   until a save is loaded.

> ### No save file yet?
> That is fine, and there is **nothing special to do**: just start a **new
> game** after running `/citra`. The client does not require a pre-existing
> save — it only needs you to be **inside the game** rather than on the title
> screen. It waits through the intro, then picks up on its own.
>
> What it cannot do is work on the title screen or in the file-select menu:
> there it reports "waiting for a loaded save" and delivers nothing. That is
> expected, and it clears up as soon as you are playing.

---

## 7. Run the client and play

1. Open **ArchipelagoLauncher** → **Yo-kai Watch 2 (English) Client**.
2. Connect to the server (address and port), using your **slot name** = the
   `name:` from your YAML.
3. In the client, type **`/citra`** and press Enter — this is what **releases
   the game** frozen at boot.
   - Expected message: *"Attached to the GDB stub (port 24689). Emulation resumes."*
4. Load your save and just play! Your checks are sent automatically and received items show up
   in-game.

### Troubleshooting

| Symptom | Fix |
|---|---|
| *"No world found to handle game Yo-kai Watch 2 (English)"* | The apworld is not in `custom_worlds/`, or Archipelago was not restarted after copying it. |
| *"Cannot connect to the GDB stub"* | The stub is not enabled, or the game was not restarted after ticking it. Also make sure no other program is using port 24689. |
| *"Emulator connection lost"* | Type `/citra` again. If it is refused, make a save state, restart the game in Azahar, load the state, then `/citra`. |
| Nothing happens / no checks | Make sure a save is actually **loaded** (not the title screen) and that you ran `/citra`. |
| In-game slowdowns | Check the message after `/citra`: *"Pause-free reads ACTIVE"* means everything is fine. |
| Received items never show up | Close the client, delete `Archipelago/ykw2/delivered_unknown_<your slot number>.txt`, then reconnect with your save loaded. The client will deliver everything again. |
| *"ROM not found"* | Point the client to your `.3ds`: `/rom <full path>`. |
| *"ROM not writable"* | Move the ROM out of `Program Files` (Windows forbids writing there), then reopen it in Azahar. |
| A chest still shows its original item | The game was running during the patch: restart it (the ROM is read at boot). |

---

## 8. What you will see in game (AP item display)

The client modifies the game **when you connect to the server**, so what you
find matches what the multiworld actually placed there:

- **Chests** display **and give** the multiworld item. Your own items appear
  as themselves; another player's item appears as "**Item AP**" (it then
  removes itself, the real item goes to its owner).
- **Key items**: most pickups also display "Item AP". Five story gives
  (Bug Net, Ancient Herb, Model Zero, Back Door Key, Mom's Directions) keep
  their native visual — the check and the delivery stay correct, only the
  popup lies for a second.

This works by writing directly into your `.3ds` ROM (see §9 for the
requirements: decrypted ROM, writable folder). Hence the recommended order:
**connect the client first, launch the game after** — the ROM is read at
game boot.

---

## 9. Yo-kai randomizer (optional)

Three YAML options shuffle the game's Yo-kai, using the multiworld seed
(every player of the same seed gets the same shuffle):

```yaml
encounter_shuffle: true          # shuffles the wild Yo-kai of every area
boss_encounter_shuffle: true     # shuffles BOSS fights among themselves (mechanics preserved)
encounter_levels: keep_location  # keep_location = the level stays put (recommended)
                                 # follow_yokai  = the level travels with the Yo-kai
```

**Requirements**: a **decrypted** `.3ds` ROM, in a writable folder (**not**
`C:\Program Files`). The client finds it by itself through Azahar's recent
files; otherwise point to it with `/rom <path to the .3ds>`.

The patch is applied **when connecting to the server**: the client then asks
you to **restart the game**. Later reconnections rewrite nothing.

Good to know:

- small `*.ykw2*.json` files appear next to the ROM — they are the **undo**
  data, do not delete them;
- `/unrandomize` restores the original ROM at any time;
- changing seeds first restores the ROM, then applies the new shuffle —
  nothing ever stacks.

---

## 10. The tracker (optional but recommended)

1. Install **PopTracker**: https://github.com/black-sliver/PopTracker/releases
2. Copy the **`tracker/ykw2en-poptracker`** folder into PopTracker's `packs/`
   folder. (`tracker/ykw2-poptracker` is the French pack — take the `en` one.)
3. Open PopTracker, pick the pack, then connect it to the Archipelago server
   (the **AP** button) using the same slot name.

You get a map per area with every check placed, your key items, your watch rank
and live counters. Checks whose item was hinted by another player are
highlighted.

---

## 11. Good to know

- **Save often in-game**: checks are detected in RAM, but your progress itself
  depends on the game's own save.
- **Do not run another debugging tool** (memory scanner, second client…) while
  the client is running: Azahar's debugger accepts **only one connection** at a
  time.
- If you play **offline** for a while, just reconnect the client afterwards: it
  catches up on missed checks once your save is loaded.
