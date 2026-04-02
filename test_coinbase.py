from coinbase.rest import RESTClient
from dotenv import load_dotenv
import os

load_dotenv()

client = RESTClient(
    api_key=os.getenv("COINBASE_API_KEY_NAME"),
    api_secret=os.getenv("COINBASE_PRIVATE_KEY")
)

accounts = client.get_accounts()

print("CONNECTED SUCCESSFULLY")
print(accounts)

products = client.get_product(product_id="BTC-USD")

print("BTC DATA:")
print(products)