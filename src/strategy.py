"""Entry signal checker — CRYPTO SQUID core rules (Layer 1, immutable)."""


def check_entry(symbol: str, drop: float, zscore: float) -> bool:
    """
    Returns True when all entry conditions are met.
    drop: % change over rolling 3-min window (negative = price fell)
    zscore: current price z-score (negative = below rolling mean)
    """
    if symbol == "BTC-USD":
        return drop <= -0.75 and zscore <= -2.0
    elif symbol == "ETH-USD":
        return drop <= -1.0 and zscore <= -2.0
    return False
