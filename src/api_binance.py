import requests
from requests.exceptions import RequestException
import time

BASE_URL = "https://api.coingecko.com/api/v3"

def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    """جلب بيانات الشموع من CoinGecko."""
    try:
        # تحويل الرمز إلى صيغة CoinGecko (BTC بدلاً من BTCUSDT)
        coin_id = "bitcoin" if symbol == "BTCUSDT" else symbol.replace("USDT", "").lower()
        # تحويل interval إلى أيام (CoinGecko يستخدم أيام بدلاً من دقائق)
        days = {
            "5m": 1/288,  # تقريبي (5 دقائق × 288 = يوم)
            "15m": 1/96,  # تقريبي (15 دقيقة × 96 = يوم)
            "30m": 1/48,  # تقريبي (30 دقيقة × 48 = يوم)
            "1h": 1,      # ساعة واحدة
            "4h": 4       # 4 ساعات
        }.get(interval, 1)

        url = f"{BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        # استخراج بيانات OHLCV وتحويلها إلى تنسيق مشابه لـ Binance
        ohlcv = data.get("prices", [])
        if not ohlcv:
            return {"error": "No OHLCV data available from CoinGecko."}

        # تحديد الحد (limit) من آخر القيم
        candles = [[int(p[0]), p[1], p[1], p[1], p[1], 0] for p in ohlcv[-limit:]]
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
