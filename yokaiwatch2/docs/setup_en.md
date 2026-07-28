# Yo-kai Watch 2 Setup Guide

## Required software

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.5.0
  or newer,
- the `yokaiwatch2.apworld` file,
- a legally dumped copy of *Yo-kai Watch 2: Psychic Specters* (3DS),
- **Emulator route:** Citra or its successor Azahar,
- **Console route:** a 3DS with Luma3DS custom firmware.

## Installing the APWorld

1. Open the Archipelago Launcher.
2. Click **Install APWorld** and select `yokaiwatch2.apworld`
   (or double-click the file, or copy it into `Archipelago/custom_worlds/`).
3. Restart the Launcher: "Yo-kai Watch 2" now appears in the game list.

## Creating your YAML

1. In the Launcher, open **Generate Template Options**; a template
   `Yo-kai Watch 2.yaml` is created in `Archipelago/Players/Templates/`.
2. Copy it to `Archipelago/Players/`, set your `name` and adjust the options
   (goal, shuffles, logic difficulty...). A commented example ships with the
   project (`Yo-kai Watch 2 - Example.yaml`).

## Generating and hosting

1. Put every player's YAML in `Archipelago/Players/`.
2. Run **Generate** from the Launcher (or `ArchipelagoGenerate`).
3. Host the resulting zip on [archipelago.gg](https://archipelago.gg/uploads)
   or locally with **Host** (`ArchipelagoServer`).

## Connecting

1. From the Launcher, open the **Yo-kai Watch 2 Client**.
2. Enter the server address (e.g. `archipelago.gg:38281`) and your slot name.

### With Citra / Azahar

1. Launch the game in the emulator.
2. Enable the GDB stub: *Emulation > Configure > Debug > Enable GDB stub*
   (default port 24689), then restart the emulation.
3. In the client, type `/citra` (or `/citra <port>`).

### On a hacked 3DS (Luma3DS)

1. Enable Rosalina's debugger (L+Down+Select > Debugger options).
2. Point the client at the console's IP and debugger port with
   `/citra <port>` after editing the host in your client settings.

> **Note:** the memory bridge is community work in progress. Until the
> memory map is filled in (see `client.py`), checks can be sent manually
> from the text client while the game-side integration matures.
