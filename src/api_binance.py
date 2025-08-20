import requests
from requests.exceptions import RequestException

BASE_URL = "https://fapi.binance.com"

def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    """جلب بيانات الشموع من Binance."""
    try:
        # تحقق من أن الرمز يحتوي على أحرف كبيرة فقط ويحتوي على "USDT"
        if not symbol.isupper() or "USDT" not in symbol:
            return {"error": f"Invalid symbol format. Use uppercase, e.g., BTCUSDT, not {symbol}"}
        
        url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()  # يثير استثناء إذا كان الطلب غير ناجح
        data = res.json()
        if not data or isinstance(data, dict) and "code" in data:
            return {"error": f"API returned no data or error: {data.get('msg', 'Unknown error')}"}
        return data
    except RequestException as e:
        return {"error": f"Failed to fetch candles: {str(e)} - URL: {url}"}

def get_long_short_ratio(symbol="BTCUSDT", period="15m", limit=50):
    """جلب نسبة Long/Short من Binance."""
    try:
        if not symbol.isupper() or "USDT" not in symbol:
            return {"error": f"Invalid symbol format. Use uppercase, e.g., BTCUSDT, not {symbol}"}
        
        url = f"{BASE_URL}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period={period}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        if not data or isinstance(data, dict) and "code" in data:
            return {"error": f"API returned no data or error: {data.get('msg', 'Unknown error')}"}
        return data
    except RequestException as e:
        return {"error": f"Failed to fetch long/short ratio: {str(e)} - URL: {url}"}
