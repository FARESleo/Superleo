import requests

BASE_URL = "https://api.bybit.com"

def get_open_interest(symbol="BTCUSDT", interval="15min", limit=50):
    url = f"{BASE_URL}/derivatives/v3/public/open-interest?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
    res = requests.get(url)
    
    # تحقق من حالة الرد قبل فك الترميز
    if res.status_code == 200:
        return res.json()
    else:
        # إذا كان الرد غير ناجح، أعد قاموسًا فارغًا أو رسالة خطأ
        # هذا يمنع التطبيق من الانهيار
        print(f"Error fetching data from Bybit API: Status Code {res.status_code}, Response: {res.text}")
        return {"result": {"list": []}}
