import requests
from requests.exceptions import RequestException

BASE_URL = "https://fapi.binance.com"

def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    """جلب بيانات الشموع من Binance أو إرجاع بيانات اختبار إذا فشل."""
    try:
        # تحقق من أن الرمز يحتوي على أحرف كبيرة فقط ويحتوي على "USDT"
        if not symbol.isupper() or "USDT" not in symbol:
            return {"error": f"Invalid symbol format. Use uppercase, e.g., BTCUSDT, not {symbol}"}
        
        url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        if not data or isinstance(data, dict) and "code" in data:
            return {"error": f"API returned no data or error: {data.get('msg', 'Unknown error')}"}
        return data
    except RequestException as e:
        # إرجاع بيانات اختبار إذا فشل الطلب
        return {
            "error": f"Failed to fetch candles: {str(e)} - URL: {url}. Using test data.",
            "test_data": [
                [1690000000000, 30000, 30500, 29500, 30050, 1000, 0, 0, 0, 0, 0, 0],
                [1690000060000, 30050, 31000, 29800, 30900, 1200, 0, 0, 0, 0, 0, 0],
                [1690000120000, 30900, 31200, 30700, 31000, 800, 0, 0, 0, 0, 0, 0]
            ]
        }

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
        # إرجاع بيانات اختبار إذا فشل الطلب
        return {
            "error": f"Failed to fetch long/short ratio: {str(e)} - URL: {url}. Using test data.",
            "test_data": [{"longShortRatio": 1.2, "timestamp": 1690000000000}]
        }
