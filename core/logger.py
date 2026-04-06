from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(root: Path) -> logging.Logger:
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("cryptosquid")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = logging.FileHandler(logs_dir / "engine.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    trades_handler = logging.FileHandler(logs_dir / "trades.log", encoding="utf-8")
    trades_handler.setFormatter(formatter)
    trades_handler.setLevel(logging.INFO)
    logger.addHandler(trades_handler)

    signals_handler = logging.FileHandler(logs_dir / "signals.log", encoding="utf-8")
    signals_handler.setFormatter(formatter)
    signals_handler.setLevel(logging.INFO)
    logger.addHandler(signals_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger
