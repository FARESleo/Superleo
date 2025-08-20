import requests
from requests.exceptions import RequestException
import time

BASE_URL = "https://api.coingecko.com/api/v3"

# خريطة لتحويل الرموز إلى معرفات CoinGecko
COIN_ID_MAP = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "XRPUSDT": "ripple",
    "BNBUSDT": "binancecoin"
}

def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    """جلب بيانات الشموع من CoinGecko."""
    try:
        # تحقق من الرمز وتحويله إلى معرف CoinGecko
        if not symbol.isupper() or "USDT" not in symbol:
            return {"error": f"Invalid symbol format. Use uppercase, e.g., BTCUSDT, not {symbol}"}
        coin_id = COIN_ID_MAP.get(symbol, symbol.replace("USDT", "").lower())
        if coin_id not in COIN_ID_MAP.values():
            return {"error": f"Unsupported symbol {symbol}. Supported: {list(COIN_ID_MAP.keys())}"}

        # تحويل interval إلى أيام (تقريبي)
        days = {
            "5m": 1/288,   # 5 دقائق × 288 = يوم
            "15m": 1/96,   # 15 دقيقة × 96 = يوم
            "30m": 1/48,   # 30 دقيقة × 48 = يوم
            "1h": 1,       # ساعة واحدة
            "4h": 4        # 4 ساعات
        }.get(interval, 1)

        url = f"{BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        # استخراج بيانات OHLCV وتحويلها
        ohlcv = data.get("prices", [])
        if not ohlcv:
            return {"error": f"No OHLCV data available for {coin_id} from CoinGecko."}

        # تحديد الحد (limit) من آخر القيم
        candles = [[int(p[0]), p[1], p[1], p[1], p[1], 0] for p in ohlcv[-limit:]]  # افتراضي (تحسين لاحق)
        return candles
    except RequestException as e:
        return {
            "error": f"Failed to fetch candles from CoinGecko: {str(e)} - URL: {url}. Using test data.",
            "test_data": [
                [1690000000000, 30000, 30500, 29500, 30050, 1000],
                [1690000060000, 30050, 31000, 29800, 30900, 1200],
                [1690000120000, 30900, 31200, 30700, 31000, 800]
            ]
        }

def get_long_short_ratio(symbol="BTCUSDT", period="15m", limit=50):
    """جلب نسبة Long/Short (غير مدعوم مباشرة في CoinGecko، إرجاع بيانات اختبار)."""
    try:
        return {"error": "Long/Short ratio not supported by CoinGecko. Using test data.", "test_data": [{"longShortRatio": 1.2, "timestamp": 1690000000000}]}
    except RequestException as e:
        return {"error": f"Failed to fetch long/short ratio: {str(e)}. Using test data.", "test_data": [{"longShortRatio": 1.2, "timestamp": 1690000000000}]}
