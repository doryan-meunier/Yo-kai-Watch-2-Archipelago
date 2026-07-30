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
| **Azahar** (3DS emulator) | https://azahar-emu.org |
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

1. In **Azahar**: *Emulation → Configure → Debug*, tick **"Enable GDB stub"**
   and leave the port on **24689**.
2. **Restart the game** for the setting to take effect.
3. Start the game and **load your save** (important: the client needs a loaded
   save, not the title screen).

---

## 7. Run the client and play

1. Open **ArchipelagoLauncher** → **Yo-kai Watch 2 (English) Client**.
2. Connect to the server (address and port), using your **slot name** = the
   `name:` from your YAML.
3. In the client, type **`/citra`** and press Enter.
   - Expected message: *"Attached to the GDB stub (port 24689). Emulation resumes."*
4. Just play! Your checks are sent automatically and received items show up
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

---

## 8. The tracker (optional but recommended)

1. Install **PopTracker**: https://github.com/black-sliver/PopTracker/releases
2. Copy the **`tracker/ykw2en-poptracker`** folder into PopTracker's `packs/`
   folder. (`tracker/ykw2-poptracker` is the French pack — take the `en` one.)
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
