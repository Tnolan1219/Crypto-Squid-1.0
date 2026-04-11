"""Runtime state writer for the localhost monitoring dashboard."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class RuntimeStore:
    def __init__(self, root: Path):
        self._path = root / "data" / "trades" / "runtime_state.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _tmp_path(self) -> Path:
        suffix = f"{os.getpid()}.{threading.get_ident()}.tmp"
        return self._path.with_name(f"{self._path.stem}.{suffix}")

    def write(self, payload: dict) -> bool:
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        content = json.dumps(payload, indent=2)

        for attempt in range(6):
            tmp_path = self._tmp_path()
            try:
                tmp_path.write_text(content, encoding="utf-8")
                tmp_path.replace(self._path)
                return True
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
            except OSError:
                time.sleep(0.05 * (attempt + 1))
            finally:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except OSError:
                    pass

        for attempt in range(3):
            try:
                self._path.write_text(content, encoding="utf-8")
                return True
            except OSError:
                time.sleep(0.05 * (attempt + 1))

        return False

    @property
    def path(self) -> Path:
        return self._path
