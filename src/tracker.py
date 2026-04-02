"""Rolling price window tracker with drop% and z-score."""

import time
import statistics


class MarketTracker:
    def __init__(self):
        self.prices = []
        self.timestamps = []

    def update(self, price: float) -> None:
        now = time.time()
        self.prices.append(price)
        self.timestamps.append(now)

        # Prune entries older than 3 minutes
        while self.timestamps and now - self.timestamps[0] > 180:
            self.timestamps.pop(0)
            self.prices.pop(0)

    def get_drop_pct(self) -> float:
        """Return % drop from oldest to newest price in the window. Negative = drop."""
        if len(self.prices) < 2:
            return 0.0
        return (self.prices[-1] - self.prices[0]) / self.prices[0] * 100

    def get_zscore(self) -> float:
        """Return z-score of current price vs rolling window. Negative = below mean."""
        if len(self.prices) < 20:
            return 0.0
        mean = statistics.mean(self.prices)
        std = statistics.stdev(self.prices)
        if std == 0:
            return 0.0
        return (self.prices[-1] - mean) / std
