import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# ===================== API Functions =====================

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Get Candlestick data from Bybit
def get_candles(symbol="BTCUSDT", interval="15", limit=100):
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": symbol.upper(), "interval": interval, "limit": limit}
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        st.error(f"⚠️ Bybit API error: {data.get('retMsg')}")
        return []
    return data.get("result", {}).get("list", [])

# Get Open Interest from Bybit
def get_open_interest(symbol="BTCUSDT", period="15min", limit=50):
    url = "https://api.bybit.com/v5/market/open-interest"
    params = {"category": "linear", "symbol": symbol.upper(), "intervalTime": period, "limit": limit}
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        st.warning(f"⚠️ Bybit API error: {data.get('retMsg')}")
        return []
    return data.get("result", {}).get("list", [])

# ===================== Analyzer =====================
def analyze(candles, oi_list):
    try:
        last_oi = float(oi_list[-1]["openInterest"])
        avg_oi = np.mean([float(x["openInterest"]) for x in oi_list])
        last_close = float(candles[-1][4])
    except Exception:
        return {"status": "error", "message": "البيانات غير كافية للتحليل"}

    if last_oi > avg_oi * 1.2:
        return {"signal": "⚠️ احتمال دخول أموال كبيرة (قد يكون فخ أو صعود قوي)", "oi": last_oi, "avg_oi": avg_oi, "price": last_close}
    elif last_oi < avg_oi * 0.8:
        return {"signal": "📉 خروج سيولة (احتمال هبوط)", "oi": last_oi, "avg_oi": avg_oi, "price": last_close}
    else:
        return {"signal": "✅ حركة طبيعية", "oi": last_oi, "avg_oi": avg_oi, "price": last_close}

# ===================== Visualization =====================
def plot_candles(candles):
    df = pd.DataFrame(candles, columns=["time","open","high","low","close","volume","turnover"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
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
    fig.update_layout(title="Bybit Candlestick Chart", xaxis_rangeslider_visible=False)
    return fig

# ===================== Streamlit App =====================
st.set_page_config(page_title="Crypto Market Tool (Bybit)", layout="wide")
st.title("📊 Crypto Market Tool (Bybit)")

symbol = st.text_input("أدخل رمز العملة (مثال: BTCUSDT)", "BTCUSDT")

if st.button("تحليل"):
    with st.spinner("⏳ جاري جلب البيانات من Bybit..."):
        try:
            candles = get_candles(symbol)
            oi_list = get_open_interest(symbol)

            if not candles or not oi_list:
                st.error("⚠️ لم يتم جلب بيانات كافية (جرّب رمز آخر أو فترة مختلفة).")
            else:
                signal = analyze(candles, oi_list)

                st.subheader("🔍 نتيجة التحليل")
                st.json(signal)

                st.subheader("📈 الرسم البياني")
                st.plotly_chart(plot_candles(candles), use_container_width=True)
        except Exception as e:
            st.error(f"حدث خطأ: {e}")
