#!/usr/bin/env python3
"""
Build script: packages the yokaiwatch2/ folder into yokaiwatch2.apworld.

An .apworld is simply a zip archive whose root contains the world package
folder. Usage:

    python build_apworld.py            # writes ./yokaiwatch2.apworld
    python build_apworld.py --out dir  # writes dir/yokaiwatch2.apworld
"""

import argparse
import zipfile
from pathlib import Path

WORLD_NAME = "yokaiwatch2"
EXCLUDED_DIRS = {"__pycache__", ".mypy_cache", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def build(output_dir: Path) -> Path:
    source = Path(__file__).parent / WORLD_NAME
    if not source.is_dir():
        raise SystemExit(f"world folder not found: {source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{WORLD_NAME}.apworld"

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            archive.write(path, Path(WORLD_NAME) / path.relative_to(source))

    print(f"OK: {target} ({target.stat().st_size / 1024:.1f} KiB)")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent,
                        help="output directory (default: project root)")
    build(parser.parse_args().out)
