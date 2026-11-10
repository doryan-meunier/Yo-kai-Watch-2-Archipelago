"""`python archipelago/lanceur` (ou `pythonw`) : ouvre le lanceur. Voir `demarrage.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lanceur.demarrage import main  # noqa: E402

sys.exit(main())
