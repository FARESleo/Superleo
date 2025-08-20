import requests
from requests.exceptions import RequestException

BASE_URL = "https://api.bybit.com"

def get_open_interest(symbol="BTCUSDT", interval="15", limit=50):
    """جلب بيانات Open Interest من Bybit."""
    try:
        # تحقق من الرمز وتحويله إذا لزم الأمر
        if not symbol.isupper() or "USDT" not in symbol:
            return {"error": f"Invalid symbol format. Use uppercase, e.g., BTCUSDT, not {symbol}"}
        symbol = symbol.replace("USDT", "")  # Bybit قد يستخدم الرمز بدون USDT

        url = f"{BASE_URL}/derivatives/v3/public/open-interest?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        if not data or isinstance(data, dict) and "retCode" in data and data["retCode"] != 0:
            return {"error": f"Bybit API error: {data.get('retMsg', 'Unknown error')}"}
        return data
    except RequestException as e:
        return {
            "error": f"Failed to fetch open interest: {str(e)} - URL: {url}. Using test data.",
            "test_data": [{"openInterest": 1000, "timestamp": 1690000000000}]
        }
