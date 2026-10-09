# Setup guide: Yo-kai Watch 2 on Archipelago (V2)

This guide explains, step by step and with no technical knowledge needed, how to play **Yo-kai Watch 2** (European version, 3DS) in
an [Archipelago](https://archipelago.gg) multiworld, alone or with friends.

> The game is **not provided**. You need your own copy and must make your own decrypted ROM from it. The mod contains no game data: it
> is built on your computer from your ROM.

Version française : [INSTALLATION_FR.md](INSTALLATION_FR.md)

---

## 1. What you need

| Item | Where to get it |
|---|---|
| Windows 10 or 11 (64-bit) | for the mod launcher |
| **Archipelago 0.6.7 or later** | <https://github.com/ArchipelagoMW/Archipelago/releases> (only the person generating the game needs it, but every player can have it) |
| **Azahar 2124.3** (3DS emulator) | <https://github.com/azahar-emu/azahar/releases/tag/2124.3> (the only validated version) |
| **Your decrypted ROM** of the European Yo-kai Watch 2 (`.3ds`, `.cci` or `.cxi`) | made with GodMode9 from your own cartridge. Original version, no merged update, no modification. An "encrypted" ROM is refused |
| **The APWorld** | `yokaiwatch2.apworld` (French names) or `yokaiwatch2en.apworld` (English names), at the root of this repository |
| **A YAML** | `Yo-kai Watch 2 - FR.yaml` or `Yo-kai Watch 2 (English) - EN.yaml`, at the root of this repository |
| **The mod launcher** | the [`lanceur/`](https://github.com/doryan-meunier/Yo-kai-Watch-2-Archipelago/tree/main/lanceur) folder of this repository: the `ykw2ap-exe-2.0.0.zip` file (recommended, no Python to install). Alternative: `ykw2ap-2.0.0.zip`, which needs Python 3.11 or later |

The French and English APWorlds can play in the **same** multiworld. The launcher and the game patch are the same in both cases.

---

## 2. Install the APWorld in Archipelago

*(This step is for the person generating the game; any player can also do it for their own tests.)*

1. Close Archipelago if it is open.
2. Copy `yokaiwatch2.apworld` (and/or `yokaiwatch2en.apworld`) into Archipelago's `custom_worlds` folder. With the standard Windows
   install: `C:\ProgramData\Archipelago\custom_worlds\`. You can also double-click the `.apworld` file if Archipelago is installed
   normally.
3. At the next Archipelago start, the games "Yo-kai Watch 2" (French) and "Yo-kai Watch 2 (English)" are recognised.

---

## 3. Prepare the YAML and generate the game

1. Open the YAML of your choice with a text editor (Notepad is enough). Every option is explained in French **and** English: what each value
   does, what checks or items it adds, and its dependencies.
2. The provided settings are the **default settings**. For the "everything on" profile (about 1,060 locations), follow the "Everything on" line
   of each option. Change the `name:` line if you want a specific player name.
3. Do not translate option or value names: they stay in French in both versions.
4. Put the YAML in Archipelago's `Players` folder (with the other players' files, if any).
5. Run the generation (Archipelago Launcher > "Generate", or `ArchipelagoGenerate.exe`). A `.zip` archive appears in the `output` folder.
6. Host the game in one of these ways:
   - **Online**: upload the `.zip` to <https://archipelago.gg/uploads>; the site gives an address and port to share (easiest with several
     players);
   - **Locally**: run `ArchipelagoServer` with the `.zip`; for friends to connect you need to open port 38281 (default) on your router.

> If the client refuses a game, it requires a lock your mod package lacks: use the latest launcher from the `lanceur/` folder of this repository (see §9).

---

## 4. Install and start the launcher

1. Download the launcher `.zip` from the `lanceur/` folder of this repository (`ykw2ap-exe-2.0.0.zip`) and **extract it** anywhere (for example in Documents).
2. Double-click **`Lanceur Yo-kai Watch 2 Archipelago.exe`** (the window can be switched to English). Keep the `_internal` folder **next to**
   the exe (do not move the exe alone; for a shortcut: right-click the exe, "Create shortcut").
3. **Windows warning**: the first time, Windows may show "Windows protected your PC" (unknown publisher). This is expected: the launcher
   is not signed (a code-signing certificate costs money). Click **"More info"**, then **"Run anyway"**. If your antivirus blocks the launcher,
   use the `.pyw` variant below.

**Python variant (`.pyw`)**: install Python 3.11 or later (with Tcl/Tk, included by default), extract `ykw2ap-2.0.0.zip`, then double-click
`Lanceur Yo-kai Watch 2 Archipelago.pyw`. It works the same way.

---

## 5. Set up the launcher

The steps are numbered in the window:

1. **Game ROM**: click **"Browse..."** and pick your ROM. The launcher checks that it is the right version. Possible messages: "encrypted"
   (make the decrypted ROM again with GodMode9), "unsupported version" (the European version is required, without a merged update or modification).
2. **Azahar**: usually found automatically; otherwise **"Browse..."** and pick `azahar.exe`. Azahar must have been **started at least once**
   before. Look at the line "Link with the game (GDB stub)":
   - if it says "enabled", you are fine;
   - if it says "disabled", click **"Enable..."**. The launcher asks for your consent before changing Azahar's configuration: it makes a **backup
     copy** next to it and only changes the GDB stub settings. **Azahar must be closed** at that moment. You can also do it yourself in Azahar:
     Emulation > Configure > Debug, tick "Enable GDB Stub".
3. **Mod**: its state is shown (not installed / up to date / other version). Installation happens by itself on the first "Play" (up to one minute).
   The "Install", "Repair" and "Uninstall" buttons are there if needed; they are refused while Azahar is open.

---

## 6. Connect to the Archipelago game

In the launcher's **"Archipelago connection"** card:

- **Server**: the address and port, for example `archipelago.gg:38281`;
- **Slot name**: your player name in the game (the YAML's name);
- **Password**: only if the game has one ("Remember password" keeps it, encrypted for your Windows account).

Click **"Save"**. You can change these fields mid-game: the client reconnects by itself. The launcher shows the connection state. As soon as
the connection is saved, the tracker (Checks, Chat and Yo-kai tabs) works **even without starting the game**.

---

## 7. Play

1. Click **"Play"**. The launcher checks everything, installs the mod if needed, starts the invisible client, then Azahar with the game.
   **Always use "Play"**, never Azahar directly.
2. **Start a NEW game** (an empty save slot). It is **linked automatically** to the Archipelago game.
3. A save that was already started is **never used**: the launcher shows "This save is not linked to the Archipelago game: start a new game." and
   nothing is received or sent. A save linked to **another** seed is refused the same way. There is no manual linking of an old save.
4. In the launcher's "State" frame: client, game, server, and save ("linked to this Archipelago game" when all is well).
5. While you play, received items show up in a banner and checks are sent by themselves.

**Azahar save states: not recommended.** They are tied to the exact installed mod version; loading one from another build can bring back the old
code. Use **in-game** saves. If you update the mod, save in game first.

---

## 8. Where to find the tracker

The tracker is **inside the launcher** (no more PopTracker):

- **Checks** tab: your locations by area (done, available, later, blocked), received items, and a **map** with markers and, if you tick "Follow
  the game", your position;
- **Yo-kai** tab: where to find each wild Yo-kai, under the shuffle actually applied; pinning on the map; filters;
- **Chat** tab: Archipelago's text client (coloured messages, chat with other players, `!hint`, `!remaining`...), with a "Hints" sub-tab.

No spoilers by default: a check's content only appears once it is done or hinted.

---

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| The game stays on a **black screen** | the client did not start. Close Azahar and start again from the launcher ("Play"). |
| "Link with the game (GDB stub): disabled" | click "Enable..." (Azahar closed), or enable it in Azahar. |
| "This save is not linked..." / "...belongs to another Archipelago game" | start a new game in an empty slot. |
| "the game must be updated (mod too old)" or "the installed game lacks some locks of this seed" | get the latest launcher from the `lanceur/` folder of this repository; click "Play" (updates the mod) or "Repair". |
| A window mentions **insufficient memory** | your computer is probably saturated: close other programs (browser, games...) and start again. *(Presumed cause, not verified in every case.)* |
| The game crashes (panic) | `plantage.json` in the client's data folder (`%APPDATA%\ykw2-ap`) keeps the cause; attach it to your help request. |
| You need help | **"Logs"** button in the launcher: opens the logs folder; attach `client.log`. |
| The mod looks damaged | **"Repair"** button (uninstalls then reinstalls). |
| ROM refused | see §5, step 1. |

Server messages: "server unreachable" (wrong address or port, server stopped), "unknown slot" (slot name), "password refused", "wrong game" (the
YAML is not for this game).

---

## 10. Uninstall

1. Close Azahar.
2. In the launcher, click **"Uninstall"**: Azahar's mods folder is back exactly as it was (another mod that was there is restored; a translation or
   another mod in `romfs` is never modified).
3. Delete the launcher folder. Your settings and logs are in `%APPDATA%\ykw2-ap`, delete them if you wish.
4. The backup copy of Azahar's configuration made by the launcher stays next to Azahar's configuration file; you can restore it if you want the GDB
   stub off, or turn it off in Azahar.
