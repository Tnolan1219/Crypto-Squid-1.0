from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.engine import Engine

_DATA_DIRS = [
    "logs",
    "data/trades",
    "data/events",
    "data/control",
    "journal/raw-trades",
    "reports/daily",
    "reports/weekly",
    "memory",
]


def _ensure_dirs() -> None:
    for rel in _DATA_DIRS:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)


def main() -> None:
    _ensure_dirs()
    engine = Engine()
    engine.run()


if __name__ == "__main__":
    main()
