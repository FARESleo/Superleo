import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Crypto Market Tool", layout="wide")
st.title("📊 Crypto Market Tool — Candles + Open Interest")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ===================== Helpers =====================
def err_msg(resp_json):
    return f"OKX error: code={resp_json.get('code')} msg={resp_json.get('msg')}"

def to_df_okx(candles):
    cols = ["ts","open","high","low","close","volume","volCcy","volQuote","confirm"]
    df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
    df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    return df.sort_values("ts").reset_index(drop=True)

def plot_candles(df, title):
    fig = go.Figure(data=[go.Candlestick(
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]
    )])
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, height=520)
    return fig

# ===================== OKX API =====================
def okx_inst_id(symbol_text, use_perp=True):
    s = symbol_text.upper().replace("-", "")
    if not s.endswith("USDT"):
        s = f"{s}USDT"
    base = s[:-4]
    return f"{base}-USDT-SWAP" if use_perp else f"{base}-USDT"

def okx_get_candles(instId, bar="15m", limit=200):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": instId, "bar": bar, "limit": limit}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(err_msg(j))
    return to_df_okx(j.get("data", []))

def okx_get_open_interest(instId):
    url = "https://www.okx.com/api/v5/public/open-interest"
    params = {"instId": instId}
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        return None
    return j.get("data", [])[0] if j.get("data") else None

# ===================== OI Analysis =====================
def analyze_oi(oi, df):
    if not oi or df.empty:
        return "❌ لا توجد بيانات كافية."

    try:
        oi_val = float(oi["oiUsd"])
    except:
        return "⚠️ لم أتمكن من قراءة OI."

    # مقارنة السعر الحالي بالمتوسط
    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-5] if len(df) > 5 else df["close"].iloc[0]
    price_change = (last_close - prev_close) / prev_close * 100

    # قاعدة مبسطة للتفسير
    if price_change > 1 and oi_val > 0:
        return f"📈 السعر ↑ {price_change:.2f}% مع OI كبير → دخول Long (انتبه لفخ شراء)."
    elif price_change < -1 and oi_val > 0:
        return f"📉 السعر ↓ {price_change:.2f}% مع OI كبير → دخول Short (انتبه لفخ بيع)."
    elif abs(price_change) < 0.5:
        return "⚖️ السعر شبه ثابت مع OI مستمر → احتمال تجميع/تصريف."
    else:
        return "✅ حركة طبيعية بلا إشارات قوية."

# ===================== UI =====================
symbol_in = st.text_input("أدخل رمز العملة:", "xrp")
tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
limit = st.slider("عدد الشموع", 50, 500, 200, 10)
use_perp_okx = st.checkbox("OKX Perp (SWAP)", value=True)

if st.button("جلب وتحليل"):
    try:
        instId = okx_inst_id(symbol_in, use_perp=use_perp_okx)
        df = okx_get_candles(instId, bar=tf, limit=limit)

        if df.empty:
            st.error("❌ لم تصل بيانات شموع.")
        else:
            st.plotly_chart(plot_candles(df, f"OKX {instId} — {tf}"), use_container_width=True)

            # تحليل OI
            oi = okx_get_open_interest(instId)
            st.subheader("📦 Open Interest (OKX)")
            if oi:
                st.metric("OI بالدولار", f"{float(oi['oiUsd']):,.0f}")
                st.caption(f"آخر تحديث: {oi['ts']}")
                st.info(analyze_oi(oi, df))
            else:
                st.write("لا توجد بيانات OI متاحة.")

    except Exception as e:
        st.error(f"حدث خطأ: {e}")
