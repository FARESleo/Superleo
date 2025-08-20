import requests

BASE_URL = "https://fapi.binance.com"

def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    res = requests.get(url).json()
    return res

def get_long_short_ratio(symbol="BTCUSDT", period="15m", limit=50):
    url = f"{BASE_URL}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period={period}&limit={limit}"
    res = requests.get(url).json()
    return res
