import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timezone

st.set_page_config(page_title="📊 أداة سوق العملات الرقمية", layout="wide")

# ===================== CSS (خلفية + تنسيق) =====================
st.markdown("""
    <style>
    body {
        background: url('https://images.unsplash.com/photo-1621504805083-d1b52d2c8a4d?auto=format&fit=crop&w=1600&q=80') no-repeat center center fixed;
        background-size: cover;
        color: #EEE;
    }
    .main {
        background: rgba(0,0,0,0.75);
        padding: 20px;
        border-radius: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# ===================== Helpers =====================
def err_msg(resp_json):
    return f"OKX error: code={resp_json.get('code')} msg={resp_json.get('msg')}"

def to_df_okx(candles):
    cols = ["ts","open","high","low","close","volume","volCcy","volQuote","confirm"]
    df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
    df["ts"] = pd.to_datetime(df["ts"].astype(str).astype("int64"), unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    return df.sort_values("ts").reset_index(drop=True)

def plot_line_chart(df, title):
    fig = go.Figure()
    
    # إضافة الرسم البياني الخطي
    fig.add_trace(go.Scatter(x=df["ts"], y=df["close"], mode='lines', name='السعر', line=dict(color='cyan', width=2)))
    
    # حساب وإضافة المتوسط المتحرك (50 شمعة)
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    fig.add_trace(go.Scatter(x=df["ts"], y=df['SMA_50'], mode='lines', name='SMA 50', line=dict(color='yellow', dash='dot')))

    # حساب وإضافة المتوسط المتحرك (200 شمعة)
    df['SMA_200'] = df['close'].rolling(window=200).mean()
    fig.add_trace(go.Scatter(x=df["ts"], y=df['SMA_200'], mode='lines', name='SMA 200', line=dict(color='orange', dash='dot')))

    fig.update_layout(
        title=title, 
        xaxis_rangeslider_visible=False, 
        height=520,
        title_font_size=24,
        margin=dict(l=0, r=0, t=50, b=0),
        plot_bgcolor="black",
        paper_bgcolor="rgba(0,0,0,0.6)",
        font=dict(color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# ===================== OKX API =====================
def okx_inst_id(symbol_text, use_perp=True):
    s = symbol_text.upper().replace("-", "")
    if not s.endswith("USDT"):
        s = f"{s}USDT"
    base = s[:-4]
    return f"{base}-USDT-SWAP" if use_perp else f"{base}-USDT"

@st.cache_data(ttl=60)
def okx_get_candles(instId, bar="15m", limit=200):
    url = "https://www.okx.com/api/v5/market/candles"
    if bar in ["1h", "2h", "4h", "6h", "12h", "1d"]:
        bar = bar + "utc"
    current_time_ms = int(pd.Timestamp.now(tz=timezone.utc).timestamp() * 1000)
    params = {"instId": instId, "bar": bar, "limit": limit, "after": current_time_ms}
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(err_msg(j))
    df = to_df_okx(j.get("data", []))
    if not df.empty:
        last_candle_time = df["ts"].iloc[-1]
        current_time = pd.Timestamp.now(tz=timezone.utc)
        time_diff = (current_time - last_candle_time).total_seconds() / 60
        if time_diff > 15:
            st.warning(f"⚠️ البيانات متأخرة بحوالي {int(time_diff)} دقيقة!")
    return df

def okx_get_open_interest(instId):
    url = "https://www.okx.com/api/v5/public/open-interest"
    params = {"instId": instId}
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        return None
    return j.get("data", [])[0] if j.get("data") else None

# ===================== OI Analysis =====================
def analyze_oi(df, oi, threshold=5_000_000):
    if df.empty or not oi:
        return {"msg": "❌ لا توجد بيانات كافية", "risk": "Unknown", "icon": "❌"}

    oi_usd = float(oi.get("oiUsd", 0))
    if len(df) < 5:
        return {"msg": "❌ بيانات غير كافية للتحليل", "risk": "Unknown", "icon": "❌"}

    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-5]
    
    chg = ((last_close - prev_close) / prev_close) * 100
    
    if chg > 1 and oi_usd > threshold:
        return {"msg": "صعود قوي + OI مرتفع → صاعد بقوة", "risk": "Bullish", "icon": "🚀"}
    
    if chg < -1 and oi_usd > threshold:
        return {"msg": "هبوط قوي + OI مرتفع → هابط بقوة", "risk": "Bearish", "icon": "🔻"}
    
    if abs(chg) <= 1 and oi_usd > threshold:
        return {"msg": "سعر شبه ثابت + OI يرتفع بسرعة → تحرك وشيك", "risk": "High Risk", "icon": "⚖️"}
    
    return {"msg": "حركة طبيعية وهادئة", "risk": "Neutral", "icon": "✅"}

# ===================== UI =====================
st.title("📊 أداة سوق العملات الرقمية — تحليل Open Interest")

with st.sidebar:
    st.header("⚙️ خيارات التحليل")
    symbol_in = st.text_input("أدخل رمز العملة:", "BTC")
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
    use_perp_okx = st.checkbox("OKX Perpetual (SWAP)", value=True)
    analyze_button = st.button("🚀 جلب وتحليل البيانات")
    
# تخزين البيانات في حالة الجلسة لتجنب إعادة التحميل
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
    st.session_state.symbol = ""
    st.session_state.use_perp = True

# عند النقر على "جلب وتحليل البيانات"
if analyze_button:
    st.session_state.symbol = symbol_in
    st.session_state.use_perp = use_perp_okx
    with st.spinner('⏳ جارٍ جلب البيانات...'):
        try:
            instId = okx_inst_id(st.session_state.symbol, use_perp=st.session_state.use_perp)
            df = okx_get_candles(instId, bar=tf, limit=limit)
            
            if df.empty:
                st.error("❌ لم يتم العثور على بيانات شموع لهذه العملة.")
            else:
                st.plotly_chart(plot_line_chart(df, f"OKX {instId} — {tf}"), use_container_width=True)

                st.subheader("📊 ملخص البيانات")
                col1, col2, col3 = st.columns(3)
                col1.metric("📈 آخر سعر", f"{df['close'].iloc[-1]:,.4f}")
                col2.metric("🔼 أعلى سعر", f"{df['high'].max():,.4f}")
                col3.metric("🔽 أدنى سعر", f"{df['low'].min():,.4f}")
                
                st.subheader("📦 تحليل Open Interest (OKX)")
                oi = okx_get_open_interest(instId)
                
                if oi:
                    res_instant = analyze_oi(df, oi)
                    
                    if res_instant['risk'] == "Bullish":
                        st.success(f"**{res_instant['icon']} {res_instant['msg']}** - مستوى الخطورة: **{res_instant['risk']}**")
                    elif res_instant['risk'] == "Bearish":
                        st.error(f"**{res_instant['icon']} {res_instant['msg']}** - مستوى الخطورة: **{res_instant['risk']}**")
                    elif res_instant['risk'] == "High Risk":
                        st.warning(f"**{res_instant['icon']} {res_instant['msg']}** - مستوى الخطورة: **{res_instant['risk']}**")
                    else:
                        st.info(f"**{res_instant['icon']} {res_instant['msg']}** - مستوى الخطورة: **{res_instant['risk']}**")
                    
                    st.caption(f"🕒 آخر تحديث: {pd.to_datetime(oi['ts'], unit='ms')}")
                else:
                    st.warning("⚠️ لا توجد بيانات OI متاحة لهذه الأداة.")

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ خطأ في الاتصال بواجهة API: {e}. يرجى التحقق من الرمز.")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")
