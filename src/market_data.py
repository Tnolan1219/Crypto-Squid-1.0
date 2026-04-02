"""Coinbase Advanced Trade price fetcher."""

from coinbase.rest import RESTClient
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).parent.parent / ".env")

client = RESTClient(
    api_key=os.getenv("COINBASE_API_KEY_NAME"),
    api_secret=os.getenv("COINBASE_PRIVATE_KEY"),
)


def get_price(symbol: str) -> float:
    product = client.get_product(product_id=symbol)
    return float(product["price"])
