import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ================== Binance Candles ==================
def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"⚠️ خطأ في Binance API: {e}")
        return []

# ================== CoinGlass Open Interest ==================
def get_open_interest(symbol="BTC", interval="15m"):
    url = f"https://open-api.coinglass.com/api/futures/openInterest"
    headers = {"coinglassSecret": "demo"}  # مفتاح تجريبي، تحتاج مفتاحك من CoinGlass
    params = {"symbol": symbol.upper(), "interval": interval}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("success") and data.get("data"):
            return data["data"]
        else:
            st.warning("⚠️ لم يتم العثور على بيانات OI من CoinGlass")
            return []
    except Exception as e:
        st.error(f"⚠️ خطأ في CoinGlass API: {e}")
        return []

# ================== Analyzer ==================
def analyze(candles, oi_data):
    try:
        closes = [float(c[4]) for c in candles]
        last_close = closes[-1]

        oi_values = [float(x["sumOpenInterest"]) for x in oi_data]
        last_oi = oi_values[-1]
        avg_oi = sum(oi_values) / len(oi_values)

        if last_oi > avg_oi * 1.2:
            signal = "⚠️ دخول سيولة كبيرة (قد يكون صعود قوي أو فخ)."
        elif last_oi < avg_oi * 0.8:
            signal = "📉 خروج سيولة (احتمال هبوط)."
        else:
            signal = "✅ حركة طبيعية."

        return {"signal": signal, "last_price": last_close, "last_oi": last_oi, "avg_oi": avg_oi}
    except Exception:
        return {"signal": "❌ البيانات غير كافية للتحليل"}

# ================== Visualization ==================
def plot_candles(candles):
    df = pd.DataFrame(candles, columns=["time","open","high","low","close","volume","ct","qav","n","taker_base","taker_quote","ignore"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)

    fig = go.Figure(data=[go.Candlestick(
        x=df["time"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"]
    )])
    fig.update_layout(title="Binance Candlestick", xaxis_rangeslider_visible=False)
    return fig

# ================== Streamlit UI ==================
st.set_page_config(page_title="Crypto Analyzer", layout="wide")
st.title("📊 Crypto Analyzer")

symbol = st.text_input("أدخل العملة (مثال: BTCUSDT)", "BTCUSDT")
if st.button("تحليل"):
    with st.spinner("⏳ جاري جلب البيانات..."):
        candles = get_candles(symbol)
        oi_data = get_open_interest(symbol.replace("USDT",""))  # CoinGlass يحتاج الرمز بدون USDT

        if not candles:
            st.error("❌ لم يتم جلب بيانات الشموع.")
        elif not oi_data:
            st.error("❌ لم يتم جلب بيانات OI.")
        else:
            result = analyze(candles, oi_data)
            st.subheader("🔍 التحليل")
            st.json(result)

            st.subheader("📈 الشموع")
            st.plotly_chart(plot_candles(candles), use_container_width=True)
