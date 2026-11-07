# Setup guide: Yo-kai Watch 2 on Archipelago (V3)

This guide explains, step by step and with no technical knowledge needed, how to play **Yo-kai Watch 2** (European
version, 3DS) in an [Archipelago](https://archipelago.gg) multiworld, alone or with friends.

> The game is **not provided**. You need to own your own copy and make your own decrypted ROM. The mod contains no game
> data: it is built on your computer from your ROM.

Version française : [INSTALLATION_FR.md](INSTALLATION_FR.md)

---

## 1. What you need

| Item | Where to get it |
|---|---|
| Windows 10 or 11 (64-bit) | for the mod launcher |
| **Archipelago 0.6.7 or later** | <https://github.com/ArchipelagoMW/Archipelago/releases> (only the person who generates the game needs it, but every player may have it) |
| **An emulator** | **Zakuro**, shipped with the launcher (nothing to install; it draws through Vulkan, or OpenGL where Vulkan does not start); or **Azahar 2124.3**: <https://github.com/azahar-emu/azahar/releases/tag/2124.3> |
| **Your own** decrypted ROM of the European Yo-kai Watch 2 (`.3ds`, `.cci` or `.cxi`) | made with GodMode9 from your own cartridge. Original version, no merged update, no modification. An "encrypted" ROM is refused |
| **The V3 APWorld** | [yokaiwatch2en.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2en.apworld) (English names) or [yokaiwatch2.apworld](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/yokaiwatch2.apworld) (French names) |
| **A YAML** | [Yo-kai Watch 2 (English) - EN.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN.yaml) (default settings) or [Yo-kai Watch 2 (English) - EN (everything on).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20%28English%29%20-%20EN%20%28everything%20on%29.yaml); in French: [Yo-kai Watch 2 - FR.yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR.yaml) or [Yo-kai Watch 2 - FR (tout activé).yaml](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/Yo-kai%20Watch%202%20-%20FR%20%28tout%20activ%C3%A9%29.yaml) (right-click, "Save link as...") |
| **The mod launcher** | [ykw2ap-exe-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-exe-3.0.0.zip) (recommended, no Python to install, Zakuro included: one click downloads the file). Variant: [ykw2ap-3.0.0.zip](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/raw/main/lanceur/ykw2ap-3.0.0.zip), which needs Python 3.11 or later |

Both APWorlds (English and French) can play in the **same** multiworld. The launcher and the modded game are the same
in both cases.

> **Every Yo-kai Watch 2 player of a game generated with the V3 APWorld needs the V3 launcher.** A game already
> generated with V2 can also be played with the V3 launcher (nothing changes in it).

---

## 2. Install the APWorld in Archipelago

*(This step is for the person who generates the game; every player may also do it for their own tries.)*

1. Close Archipelago if it is open.
2. Copy `yokaiwatch2en.apworld` (and/or `yokaiwatch2.apworld`) into Archipelago's `custom_worlds` folder, **replacing**
   the V2 APWorld if it is there. With the usual Windows install: `C:\ProgramData\Archipelago\custom_worlds\`. You can
   also double-click the `.apworld` file if Archipelago is installed normally.
3. The next time Archipelago starts, the games "Yo-kai Watch 2 (English)" and "Yo-kai Watch 2" (French) are
   recognised.

---

## 3. Prepare the YAML and generate the game

1. Pick a template: **default settings** (about 510 locations, every real lock) or **"everything on"** (over 1,400
   locations, with the postgame up to Kabuking). Open it with a text editor (Notepad is enough). Every option is
   explained: what each value does, which checks or items it adds, and what it depends on.
2. **The goal** (option `goal`) is the first choice to make: `finish_chapter_10` for a game the size of V2;
   `defeat_wobblewok`, `defeat_kat_kraydel` or `defeat_kabuking` to add the postgame (then also set `postgame`);
   `complete_medallium` for the whole game (around a hundred hours). To build your own profile, follow the "Everything
   on" line of each option. Change the `name:` line if you want a specific player name.
3. Do not translate option or value names: each world has its own. The English YAML ("Yo-kai Watch 2 (English)") is
   entirely in English (`goal`, `bosses`, `active_locks`...); the French YAML ("Yo-kai Watch 2") is in French.
4. Put the YAML in Archipelago's `Players` folder (with the other players' YAMLs, if any).
5. Generate (Archipelago Launcher > "Generate", or `ArchipelagoGenerate.exe`). A `.zip` archive appears in the
   `output` folder.
6. Host the game, in one of these ways:
   - **Online**: upload the `.zip` to <https://archipelago.gg/uploads>; the site gives an address and port to share
     (the easiest with several players);
   - **Locally**: run `ArchipelagoServer` with the `.zip`; for your friends to connect, port 38281 (default) must be
     opened on your router.

> The generation's spoiler file (`..._Spoiler.txt`, when requested) has a Yo-kai Watch 2 section: boss shuffle,
> legendaries, Five-Star Coin order, requested Yo-kai zones.

---

## 4. Install and start the launcher

1. Unzip `ykw2ap-exe-3.0.0.zip` wherever you like (for example in Documents). You can replace the V2 folder: your
   settings, logs and Zakuro save files are stored elsewhere (`%APPDATA%\ykw2-ap`).
2. Double-click **`Lanceur Yo-kai Watch 2 Archipelago.exe`**. Keep the `_internal` folder (and the `zakuro` folder)
   **next to** the exe (do not move the exe alone; for a shortcut: right-click the exe, "Create shortcut").
3. **Windows warning**: the first time, Windows may show "Windows protected your PC" (unknown publisher). This is
   normal: the launcher is not signed (code signing costs money). Click **"More info"**, then **"Run anyway"**. If
   your antivirus blocks the launcher, use the `.pyw` variant below.

**Python variant (`.pyw`)**: install Python 3.11 or later (with Tcl/Tk, included by default), unzip
`ykw2ap-3.0.0.zip`, then double-click `Lanceur Yo-kai Watch 2 Archipelago.pyw`. It works the same way, except for
updates (see below).

### Updating the launcher

- **Automatic update (exe)**: at startup, the launcher checks the mod's public repository for a newer version (a
  plain request, no data sent; "Check for updates at startup" box in the "Settings" tab → "Game settings", ticked by
  default). If there is one, the "Mod" card of the "Game" tab shows "Update available" and its notes. Save **in the
  game**, close the game, then click **"Update"**: the launcher downloads the package, checks it, replaces its files
  and restarts. If anything fails, the old version stays in place. Your settings, connection and save files are kept.
  On the next "Play", the mod is reinstalled by itself (with Zakuro, only the part of the game that changed is
  prepared again).
- **`.pyw` variant**: the launcher reports the new version with an "Open the page" button; download the new zip and
  unzip it in place of the old one.
- **Coming from V2**: its launcher does not update itself. Download the V3 zip above and unzip it (you can replace the
  V2 folder). A game generated with V2 continues with the V3 launcher; if you played it on Azahar, keep Azahar for it.

---

## 5. Set up the launcher

The window shows numbered steps:

1. **Game ROM**: click **"Browse..."** and select your ROM. The launcher checks it is the right version. Possible
   messages: "encrypted" (make the ROM again, decrypted, with GodMode9), "unsupported version" (the European version is
   needed, without a merged update or modification). The ROM is also used to compute, on your side, the Yo-kai, boss
   and Crank-a-kai shuffles: pick it before playing.
2. **Emulator**:
   - **Built-in Zakuro** (the default when it is shipped): the line "Built-in Zakuro: the game runs as PC code" is
     shown; there is nothing to set up (the link with the game is built in).
   - **Azahar**: click **"Browse..."** and select `azahar.exe`. Azahar must have been **started at least once**
     before. Look at the "Link with the game (GDB stub)" line: if it says "disabled", click **"Enable..."** (Azahar
     closed). The launcher asks for your consent before changing Azahar's configuration, makes a **backup copy** next
     to it and only changes the GDB stub settings. You can also do it yourself in Azahar: Emulation > Configure >
     Debug, tick "Enable GDB Stub".
   - To go back to Zakuro: "Browse..." the `zakuro\zakuro.exe` file in the launcher folder.
3. **Mod**: its state is shown (not installed / up to date / other version). Installation happens by itself on the
   first "Play". The "Install", "Repair" and "Uninstall" buttons are there if needed; they are refused while the
   emulator is open.

---

## 6. Connect to the Archipelago game

In the launcher's **"4. Archipelago connection"** card:

- **Server**: the address and port, for example `archipelago.gg:38281`;
- **Slot name**: your player name in the game (the one in the YAML);
- **Password**: only if the game has one (the "Remember password" box keeps it, encrypted for your Windows account).

Click **"Save"**. You can change these fields in the middle of a game: the client reconnects by itself. The launcher
shows the connection state, and the state of the game's shuffles (Yo-kai, bosses). As soon as the connection is saved,
the tracker (Checks, Chat, Yo-kai tabs) works **even without starting the game**.

---

## 7. Play

1. Click **"Play"**. The launcher checks everything, installs the mod if needed, starts the hidden client, then the
   emulator with the game. **Always** use "Play", never the emulator directly.
2. **With Zakuro, the first time**: "Preparing the game for PC (recompiling, once per mod version): N%". The game is
   turned into PC code on your computer: it takes **a few minutes** (about 4 minutes on a recent PC, longer on a more
   modest computer). The very first time, the launcher may also download a compiler (about 100 MB) if the computer has
   none. The prepared game is kept: later launches start directly, and after a mod update only what changed is redone
   (usually under a minute).
3. **Start a NEW game** (an empty save slot). It is **linked automatically** to the Archipelago game.
4. A save that was already started is **never used**: the launcher shows "This save is not linked to the Archipelago
   game: start a new game." and nothing is received or sent there. A save linked to **another** seed is refused the
   same way.
5. In the launcher's "Status" frame: client, game, server, and save ("linked to this Archipelago game" when all is
   well). If the game is **on hold** (shuffle being prepared, ROM to pick), follow the message: it resumes by itself.
6. While playing, received items show up in a banner, and checks are sent by themselves.

**Save files**: Zakuro and Azahar each have their own save files (Zakuro's are in `%APPDATA%\ykw2-ap\zakuro`). A game
started with one continues with the same one.

**Zakuro settings**: the launcher's **"Settings"** tab, **"Zakuro"** sub-tab (game language, 3D resolution, frame interpolation, window size, screen layout, filter, volume…), then "Save". Zakuro reads them when it starts: they apply to the next game started with "Play". They can still be changed in Zakuro (Esc → Settings), along with keyboard keys and controller buttons (Controls). Zakuro keeps them in `%APPDATA%\zakuro\settings.toml`.

**Save states: not recommended.** They are tied to the exact installed mod version; loading one from another build can
bring the old code back. Use **in-game** saves. Before updating the mod, save in the game.

---

## 8. Where to find the tracker

The tracker is **in the launcher**:

- **Checks** tab: your locations by area (done, reachable, later, blocked), the items received, and a **map** with
  markers and, if you tick "Follow the game", your position; Invitations, Special coins and Legendaries sections
  depending on the game's options;
- **Yo-kai** tab: where to find each wild Yo-kai, with the shuffle actually applied ("Crank-a-kai" places,
  "guaranteed at <zone>"); "Bosses" view; pin on the map; filters;
- **Chat** tab: Archipelago's text client (chat with the other players, `!hint`, `!remaining`...), with a "Hints"
  sub-tab.

No spoiler by default: a check's content only shows once it is done or if it was hinted.

---

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| The game stays on a **black screen** | the client did not start. Close the emulator, start again from the launcher ("Play"). |
| "Recompiling the game failed" (Zakuro) | click "Play" again; if it happens again, switch to Azahar (§5) and attach `client.log` to your report. |
| "Link with the game (GDB stub): disabled" (Azahar) | click "Enable..." (Azahar closed), or enable it in Azahar. |
| "This save is not linked..." / "This save belongs to another Archipelago game" | start a new game in an empty slot. |
| "the installed game lacks some locks of this seed" or "mod too old" | update the launcher (§4); click "Play" (updates the mod) or "Repair". |
| "Game on hold" / "Game blocked" (shuffle) | follow the message: usually, pick the ROM in the launcher, then "Repair". |
| The game crashes (panic) | the `plantage.json` file in the client's data folder (`%APPDATA%\ykw2-ap`) keeps the cause; attach it to your help request. |
| Need help | the launcher's **"Logs"** button opens the logs folder; attach `client.log`. |
| The mod seems broken | **"Repair"** button (uninstalls, then reinstalls). |
| ROM refused | see §5, step 1. |
| The **controller** (PS5 especially) is not detected or **no button** works (Zakuro) | double-click `zakuro\tester_manette.cmd` (in the launcher's folder): it shows what Zakuro sees of the controller. If it appears there and every button prints a line, Zakuro reads it; if the game does not follow it, or it disappears while Steam is open, quit **Steam** completely and try again. Otherwise turn the controller off and on again (or plug it in with USB) and run the test again. To quit Steam: right-click its icon near the clock, "Exit". |
| The game is **not in English** (Zakuro) | in the launcher, **"Settings"** tab, **"Zakuro"** sub-tab: "Game language" = English, "Save", then start the game again (or, in Zakuro: Esc → Settings → Emulation → Language, then start the game again). |

Server messages: "server unreachable" (wrong address or port, server stopped), "unknown slot" (slot name), "wrong
password", "wrong game" (the YAML is not for this game).

---

## 10. Uninstall

1. Close the emulator.
2. In the launcher, **"Uninstall"** button: the emulator's mods folder goes back to how it was (with Azahar, another
   mod that was there is put back; a translation or another mod in `romfs` is never modified).
3. Delete the launcher folder.
4. Your settings, logs and **Zakuro save files** are in `%APPDATA%\ykw2-ap`: only delete that folder if you no longer
   want those saves. Zakuro also keeps the game prepared for PC in `%APPDATA%\3dsrecomp` and its compiler in
   `%LOCALAPPDATA%\zakuro`, and its settings in `%APPDATA%\zakuro`: you can delete them.
5. With Azahar: the backup copy of its configuration made by the launcher stays next to Azahar's configuration file;
   you can restore it, or disable the GDB stub in Azahar.
