import requests
from requests.exceptions import RequestException

BASE_URL = "https://fapi.binance.com"

def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    """جلب بيانات الشموع من Binance."""
    try:
        url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()  # يثير استثناء إذا كان الطلب غير ناجح
        return res.json()
    except RequestException as e:
        return {"error": f"Failed to fetch candles: {str(e)}"}

def get_long_short_ratio(symbol="BTCUSDT", period="15m", limit=50):
    """جلب نسبة Long/Short من Binance."""
    try:
        url = f"{BASE_URL}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period={period}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except RequestException as e:
        return {"error": f"Failed to fetch long/short ratio: {str(e)}"}
