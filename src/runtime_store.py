"""Runtime state writer for the localhost monitoring dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class RuntimeStore:
    def __init__(self, root: Path):
        self._path = root / "data" / "trades" / "runtime_state.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, payload: dict) -> None:
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(self._path)

    @property
    def path(self) -> Path:
        return self._path
