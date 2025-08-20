import requests

BASE_URL = "https://api.bybit.com"

def get_open_interest(symbol="BTCUSDT", interval="15min", limit=50):
    url = f"{BASE_URL}/derivatives/v3/public/open-interest?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
    res = requests.get(url).json()
    return res
