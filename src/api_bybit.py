import requests
from requests.exceptions import RequestException

BASE_URL = "https://api.bybit.com"

def get_open_interest(symbol="BTCUSDT", interval="15", limit=50):
    """جلب بيانات Open Interest من Bybit."""
    try:
        url = f"{BASE_URL}/derivatives/v3/public/open-interest?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except RequestException as e:
        return {"error": f"Failed to fetch open interest: {str(e)}"}
