#!/usr/bin/env python3
"""
Génère yokaiwatch2/data/yokai_names.json : identifiant d'unité -> nom FR.

Le jeu ne manipule que des identifiants numériques dans ses tables de
rencontres. Pour dire à un joueur QUEL Yo-kai il croisera après un mélange, il
faut cette correspondance — et elle n'existe nulle part ailleurs que dans la
ROM : chara_param -> chara_base -> chara_text (archive de langue).

    python tools/extract_yokai_names.py [romfs]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import randomize_encounters as R          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROMFS_DEFAUT = r"C:\Users\dorya\Downloads\3dstool\romfs"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    romfs = Path(sys.argv[1] if len(sys.argv) > 1 else ROMFS_DEFAUT)
    noms = R.unit_names(romfs)
    noms = {str(k): v for k, v in sorted(noms.items()) if v}
    out = ROOT / "yokaiwatch2" / "data" / "yokai_names.json"
    out.write_text(json.dumps(noms, ensure_ascii=False, indent=0),
                   encoding="utf-8")
    print(f"{len(noms)} Yo-kai nommés -> {out}")
    print("exemples :", ", ".join(list(noms.values())[:6]))


if __name__ == "__main__":
    main()
