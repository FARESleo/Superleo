import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Crypto Market Tool", layout="wide")
st.title("📊 Crypto Market Tool — Candles + OI")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ===================== Helpers =====================
def err_msg(resp_json, exch):
    if exch == "OKX":
        return f"OKX error: code={resp_json.get('code')} msg={resp_json.get('msg')}"
    else:
        return f"Bybit error: retCode={resp_json.get('retCode')} retMsg={resp_json.get('retMsg')}"

def to_df_okx(candles):
    # OKX returns newest-first rows: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    cols = ["ts","open","high","low","close","volume","volCcy","volQuote","confirm"]
    df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
    df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    return df.sort_values("ts").reset_index(drop=True)

def to_df_bybit(candles):
    # Bybit v5 kline list item: [start, open, high, low, close, volume, turnover]
    cols = ["ts","open","high","low","close","volume","turnover"]
    df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
    # Bybit returns seconds
    df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="s")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    return df.sort_values("ts").reset_index(drop=True)

def plot_candles(df, title):
    fig = go.Figure(data=[go.Candlestick(
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]
    )])
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, height=520)
    return fig

def quick_candle_signal(df):
    if df.empty or len(df) < 30:
        return "البيانات قليلة لتقييم نمط واضح."
    last = df.iloc[-1]
    rng  = last["high"] - last["low"]
    if rng <= 0:
        return "نطاق الشمعة صفري."
    body = abs(last["close"] - last["open"])
    up_w = last["high"] - max(last["open"], last["close"])
    lo_w = min(last["open"], last["close"]) - last["low"]
    vol_ma = df["volume"].rolling(20).mean().iloc[-1]
    vol_spike = last["volume"] > (vol_ma * 1.5 if pd.notna(vol_ma) else last["volume"])
    # إشارات مبسطة
    if up_w/rng > 0.6 and last["close"] < last["open"] and vol_spike:
        return "📉 رفض سعري بظل علوي طويل مع فوليوم عالي → ميل هبوطي قصير المدى."
    if lo_w/rng > 0.6 and last["close"] > last["open"] and vol_spike:
        return "📈 امتصاص بيع بظل سفلي طويل مع فوليوم عالي → ميل صعودي قصير المدى."
    if body/rng < 0.25 and vol_spike:
        return "⚠️ تذبذب/توازن (دوجي/سبينينغ) مع فوليوم عالي → ترقّب كسر."
    return "✅ حركة طبيعية بلا إشارة قوية."

# ===================== OKX =====================
def okx_inst_id(symbol_text, use_perp=True):
    # يحول BTCUSDT -> BTC-USDT أو BTC-USDT-SWAP
    s = symbol_text.upper().replace("-", "")
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}-USDT-SWAP" if use_perp else f"{base}-USDT"
    # fallback
    return symbol_text

def okx_get_candles(instId, bar="15m", limit=200):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": instId, "bar": bar, "limit": limit}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(err_msg(j, "OKX"))
    data = j.get("data", [])
    if not data:
        return pd.DataFrame()
    return to_df_okx(data)

def okx_get_open_interest(instId):
    url = "https://www.okx.com/api/v5/public/open-interest"
    params = {"instId": instId}
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        return None
    data = j.get("data", [])
    return data[0] if data else None  # OKX يُرجّع لقطة حالية فقط

# ===================== Bybit (اختياري) =====================
def bybit_get_candles(symbol="BTCUSDT", interval="15", limit=200):
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": symbol.upper(), "interval": str(interval), "limit": limit}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("retCode") != 0:
        raise RuntimeError(err_msg(j, "BYBIT"))
    data = j.get("result", {}).get("list", [])
    if not data:
        return pd.DataFrame()
    return to_df_bybit(data)

def bybit_get_open_interest(symbol="BTCUSDT", period="15min", limit=50):
    url = "https://api.bybit.com/v5/market/open-interest"
    params = {"category":"linear","symbol":symbol.upper(),"intervalTime":period,"limit":limit}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("retCode") != 0:
        return []
    return j.get("result", {}).get("list", [])

# ===================== UI =====================
provider = st.radio("المزوّد", ["OKX (موصى به)","Bybit"], horizontal=True)
symbol_in = st.text_input("أدخل الرمز:", "BTCUSDT")

colA, colB, colC = st.columns(3)
with colA:
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
with colB:
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
with colC:
    use_perp_okx = st.checkbox("OKX Perp (SWAP)", value=True, help="لـ OKX: استخدام عقد دائم -USDT-SWAP")

if st.button("جلب وتحليل"):
    try:
        if provider.startswith("OKX"):
            instId = okx_inst_id(symbol_in, use_perp=use_perp_okx)
            df = okx_get_candles(instId, bar=tf, limit=limit)
            if df.empty:
                st.error("لم تصل شموع من OKX.")
            else:
                st.plotly_chart(plot_candles(df, f"OKX {instId} — {tf}"), use_container_width=True)
                st.subheader("🔍 إشارة سريعة من الشموع/الفوليوم")
                st.info(quick_candle_signal(df))
                oi = okx_get_open_interest(instId)
                st.subheader("📦 Open Interest (OKX)")
                if oi:
                    st.json(oi)
                    st.caption("ملاحظة: OKX يُرجع لقطة حالية لـ OI (وليس سلسلة زمنية).")
                else:
                    st.write("لا توجد بيانات OI متاحة حاليًا لهذا الرمز/المنطقة.")
        else:
            # Bybit
            df = bybit_get_candles(symbol_in, interval=tf.replace("m","").replace("h","0").replace("d","D") if tf.endswith("d") else tf.replace("m","").replace("h","60"), limit=limit)
            if df.empty:
                st.error("لم تصل شموع من Bybit.")
            else:
                st.plotly_chart(plot_candles(df, f"Bybit {symbol_in} — {tf}"), use_container_width=True)
                st.subheader("🔍 إشارة سريعة من الشموع/الفوليوم")
                st.info(quick_candle_signal(df))
                oi_list = bybit_get_open_interest(symbol_in, period=("15min" if tf.endswith("m") else "1h"))
                st.subheader("📦 Open Interest (Bybit)")
                if oi_list:
                    st.write(f"عدد نقاط OI: {len(oi_list)}")
                    # عرض آخر قيمة وأبسط مقارنة إذا توفّرت سلسلة
                    last_oi = float(oi_list[-1]["openInterest"])
                    avg_oi = np.mean([float(x["openInterest"]) for x in oi_list])
                    st.metric("آخر OI", f"{last_oi:,.0f}", delta=f"{(last_oi-avg_oi)/avg_oi*100:.2f}% vs avg")
                else:
                    st.write("لا توجد بيانات OI متاحة (قد يكون حجب من Bybit).")
    except requests.HTTPError as e:
        st.error(f"HTTPError: {e}")
        st.caption("إذا كنت ببلد عليه قيود، جرّب OKX أو شغّل الأداة على خادم/Streamlit Cloud.")
    except Exception as e:
        st.error(f"حدث خطأ: {e}")
