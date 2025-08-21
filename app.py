import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ============ إعداد الصفحة ============
st.set_page_config(page_title="📊 أداة تحليل سوق العملات الرقمية", layout="wide")

# ============ CSS لتنسيق عصري ============
st.markdown("""
    <style>
    body {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: #EEE;
        font-family: 'Cairo', sans-serif;
    }
    .main {
        background: transparent;
    }
    h1, h2, h3 {
        color: #00e6e6 !important;
        font-weight: 700 !important;
    }
    .stMetric {
        background: rgba(0,0,0,0.3);
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        color: #fff;
        box-shadow: 0px 0px 10px rgba(0,255,255,0.2);
    }
    .css-1d391kg {
        background: transparent !important;
    }
    </style>
""", unsafe_allow_html=True)

# ============ الدوال المساعدة ============
def to_df_okx(candles):
    if not candles:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume"])
    df = pd.DataFrame(candles).iloc[:, :6]
    df.columns = ["ts","open","high","low","close","volume"]
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce").fillna(0).astype("int64")
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", errors="coerce")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.sort_values("ts").reset_index(drop=True)

def plot_candles(df, title):
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color='#00ff99', decreasing_line_color='#ff0066',
        name="Candles"
    ))

    fig.add_trace(go.Bar(
        x=df["ts"], y=df["volume"], name="Volume", marker_color="#3399ff",
        opacity=0.4, yaxis="y2"
    ))

    if len(df) >= 20:
        df["SMA20"] = df["close"].rolling(20).mean()
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df["ts"], y=df["SMA20"], mode="lines",
                                 name="SMA20", line=dict(color="#ffff00", width=1.5)))
        fig.add_trace(go.Scatter(x=df["ts"], y=df["EMA50"], mode="lines",
                                 name="EMA50", line=dict(color="#ff9900", width=1.5)))

    fig.update_layout(
        template="plotly_dark",
        title=title,
        xaxis_rangeslider_visible=False,
        height=600,
        margin=dict(l=10, r=10, t=50, b=10),
        yaxis=dict(title="السعر"),
        yaxis2=dict(title="الحجم", overlaying="y", side="right", showgrid=False)
    )
    return fig

def okx_inst_id(symbol, use_perp=True):
    s = (symbol or "").strip().upper().replace("-", "").replace(" ", "")
    if not s: return ""
    if not s.endswith("USDT"): s += "USDT"
    base = s[:-4]
    return f"{base}-USDT-SWAP" if use_perp else f"{base}-USDT"

def okx_get_candles(instId, bar="15m", limit=200):
    url = "https://www.okx.com/api/v5/market/candles"
    r = requests.get(url, params={"instId": instId, "bar": bar, "limit": limit}, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    j = r.json()
    return to_df_okx(j.get("data", [])) if j.get("code")=="0" else pd.DataFrame()

def okx_get_open_interest(instId):
    url = "https://www.okx.com/api/v5/public/open-interest"
    r = requests.get(url, params={"instId": instId}, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    j = r.json()
    return j.get("data", [])[0] if j.get("code")=="0" and j.get("data") else None

def analyze_oi(oi, df, threshold=5_000_000):
    if not oi or df.empty: return ("❌ لا توجد بيانات كافية", "gray")
    oi_usd = float(oi.get("oiUsd", 0))
    last, prev = df["close"].iloc[-1], df["close"].iloc[-5]
    chg = ((last-prev)/prev)*100
    if chg>1 and oi_usd>threshold: return ("🟢 صعود قوي مدعوم بزيادة OI", "green")
    if chg>1: return ("🟡 صعود ضعيف مع OI منخفض", "orange")
    if chg<-1 and oi_usd>threshold: return ("🔴 هبوط قوي مدعوم بزيادة OI", "red")
    if chg<-1: return ("🟡 هبوط مع OI ضعيف", "orange")
    if oi_usd>threshold: return ("⚖️ سعر ثابت وOI مرتفع → احتمال تجميع/تصريف", "blue")
    return ("✅ حركة طبيعية وهادئة", "gray")

# ============ واجهة المستخدم ============
st.markdown("<h1 style='text-align:center;'>🚀 لوحة تحليل السوق اللحظي</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ الإعدادات")
    sym = st.text_input("العملة:", "XRP")
    tf = st.selectbox("الإطار الزمني", ["5m","15m","1h","4h","1d"], index=1)
    limit = st.slider("عدد الشموع:", 50, 500, 200, 50)
    use_perp = st.checkbox("عقود دائمة (SWAP)", True)
    threshold = st.number_input("عتبة OI بالدولار", 100000, 20000000, 5000000, 500000)
    go_btn = st.button("تحليل الآن 🔍")

if go_btn:
    inst = okx_inst_id(sym, use_perp)
    df = okx_get_candles(inst, tf, limit)
    oi = okx_get_open_interest(inst)

    if df.empty:
        st.error("⚠️ لا توجد بيانات للرمز.")
    else:
        st.plotly_chart(plot_candles(df, f"{inst} — {tf}"), use_container_width=True)

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("آخر سعر", f"{df['close'].iloc[-1]:,.4f}")
        c2.metric("أعلى", f"{df['high'].max():,.4f}")
        c3.metric("أدنى", f"{df['low'].min():,.4f}")
        c4.metric("تغير 5 شموع", f"{((df['close'].iloc[-1]-df['close'].iloc[-5])/df['close'].iloc[-5])*100:.2f}%")

        st.subheader("📦 تحليل Open Interest")
        if oi:
            msg,color = analyze_oi(oi, df, threshold)
            st.markdown(f"<h3 style='color:{color};'>{msg}</h3>", unsafe_allow_html=True)
        else:
            st.warning("لا بيانات OI.")
