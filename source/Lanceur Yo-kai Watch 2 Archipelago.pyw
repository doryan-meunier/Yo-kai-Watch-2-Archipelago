"""Lanceur du mod Archipelago de Yo-kai Watch 2 : double-cliquer (Python 3.11+ de python.org)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "archipelago"))
from lanceur.demarrage import main  # noqa: E402

sys.exit(main())
