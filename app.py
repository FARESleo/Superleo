import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# ===================== API Functions =====================

# Binance: Candlestick data
def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# Binance: Long/Short ratio
def get_long_short_ratio(symbol="BTCUSDT", period="15m", limit=50):
    url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
    params = {"symbol": symbol.upper(), "period": period, "limit": limit}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# Bybit (v5): Open Interest
def get_open_interest(symbol="BTCUSDT", period="15min", limit=50):
    url = "https://api.bybit.com/v5/market/open-interest"
    params = {
        "category": "linear",
        "symbol": symbol.upper(),
        "intervalTime": period,  # v5 uses "intervalTime"
        "limit": limit
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        st.warning(f"⚠️ Bybit API error: {data.get('retMsg')}")
        return []
    return data.get("result", {}).get("list", [])

# ===================== Analyzer =====================
def analyze(candles, oi_list, ratio_data):
    try:
        last_oi = float(oi_list[-1]["openInterest"])
        avg_oi = np.mean([float(x["openInterest"]) for x in oi_list])
        long_ratio = float(ratio_data[-1]["longShortRatio"])
    except Exception:
        return {"status": "error", "message": "البيانات غير كافية للتحليل"}

    if last_oi > avg_oi * 1.2 and long_ratio > 1.5:
        return {"signal": "⚠️ احتمال فخ صانع سوق", "oi": last_oi, "ratio": long_ratio}
    else:
        return {"signal": "✅ حركة طبيعية", "oi": last_oi, "ratio": long_ratio}

# ===================== Visualization =====================
def plot_candles(candles):
    df = pd.DataFrame(candles, columns=[
        "time","open","high","low","close","volume","c1","c2","c3","c4","c5","c6"
    ])
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
    fig.update_layout(title="Candlestick Chart", xaxis_rangeslider_visible=False)
    return fig

# ===================== Streamlit App =====================
st.set_page_config(page_title="Crypto Market Tool", layout="wide")
st.title("📊 Crypto Market Tool")

symbol = st.text_input("أدخل رمز العملة (مثال: BTCUSDT)", "BTCUSDT")

if st.button("تحليل"):
    with st.spinner("⏳ جاري جلب البيانات..."):
        try:
            candles = get_candles(symbol)
            ratios = get_long_short_ratio(symbol)
            oi_list = get_open_interest(symbol)

            if not oi_list or not ratios:
                st.error("⚠️ لم يتم جلب بيانات كافية (جرّب رمز آخر أو فترة مختلفة).")
            else:
                signal = analyze(candles, oi_list, ratios)

                st.subheader("🔍 نتيجة التحليل")
                st.json(signal)

                st.subheader("📈 الرسم البياني")
                st.plotly_chart(plot_candles(candles), use_container_width=True)
        except Exception as e:
            st.error(f"حدث خطأ: {e}")
