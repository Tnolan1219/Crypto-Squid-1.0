from __future__ import annotations

from abc import ABC, abstractmethod


class Strategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def fetch_data(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate_signals(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, actions: list[dict]) -> None:
        raise NotImplementedError

    @abstractmethod
    def manage_risk(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def cancel_orders(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def current_pnl(self) -> float:
        raise NotImplementedError
