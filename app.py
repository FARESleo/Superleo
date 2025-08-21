import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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

def plot_candles(df, title):
    fig = go.Figure(data=[go.Candlestick(
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color='lime', decreasing_line_color='red'
    )])
    fig.update_layout(
        title=title, 
        xaxis_rangeslider_visible=False, 
        height=520,
        title_font_size=24,
        margin=dict(l=0, r=0, t=50, b=0),
        plot_bgcolor="black",
        paper_bgcolor="rgba(0,0,0,0.6)",
        font=dict(color="white")
    )
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
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(err_msg(j))
    return to_df_okx(j.get("data", []))

def okx_get_open_interest(instId):
    url = "https://www.okx.com/api/v5/public/open-interest"
    params = {"instId": instId}
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        return None
    return j.get("data", [])[0] if j.get("data") else None

# ===================== OI Analysis (محسنة) =====================
def analyze_oi(oi, df, threshold=5_000_000):
    if not oi or df.empty:
        return {"msg":"❌ لا توجد بيانات كافية","color":"gray","icon":"❌","risk":"Unknown"}
    
    oi_usd = float(oi.get("oiUsd",0))
    last, prev = df["close"].iloc[-1], df["close"].iloc[-5]
    chg = ((last-prev)/prev)*100
    
    oi_change = (oi_usd - threshold) / threshold * 100
    
    if chg > 1 and oi_usd > threshold:
        return {"msg":"🚀 صعود قوي + OI مرتفع → احتمال استمرار الاتجاه الصاعد","color":"lime","icon":"🚀","risk":"Bullish"}
    
    if chg > 1 and oi_usd <= threshold:
        return {"msg":"📈 صعود ضعيف مع OI منخفض → الاتجاه غير مدعوم بقوة","color":"yellow","icon":"📈","risk":"Weak Bullish"}
    
    if chg < -1 and oi_usd > threshold:
        return {"msg":"🔻 هبوط قوي + OI مرتفع → احتمال ضغط بيعي أو تصريف","color":"red","icon":"🔻","risk":"Bearish"}
    
    if chg < -1 and oi_usd <= threshold:
        return {"msg":"⚠️ هبوط ضعيف مع OI منخفض → لا يوجد ضغط كبير","color":"orange","icon":"⚠️","risk":"Weak Bearish"}
    
    if abs(chg) <= 1 and oi_usd > threshold:
        if oi_change > 20:
            return {"msg":"🔴 سعر شبه ثابت + OI يرتفع بسرعة → احتمال فخ (تجميع/تصريف)","color":"cyan","icon":"⚖️","risk":"High Risk"}
        else:
            return {"msg":"🟡 سعر شبه ثابت + OI مرتفع → مراقبة لاحتمال تحرك كبير","color":"cyan","icon":"⚖️","risk":"Medium Risk"}
    
    return {"msg":"✅ حركة طبيعية وهادئة","color":"white","icon":"✅","risk":"Neutral"}

# ===================== UI =====================
st.title("📊 أداة سوق العملات الرقمية — الشموع + Open Interest")

with st.sidebar:
    st.header("⚙️ خيارات التحليل")
    symbol_in = st.text_input("أدخل رمز العملة:", "BTC")
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
    use_perp_okx = st.checkbox("OKX Perpetual (SWAP)", value=True)
    analyze_button = st.button("🚀 جلب وتحليل البيانات")

if analyze_button:
    with st.spinner('⏳ جارٍ جلب البيانات...'):
        try:
            instId = okx_inst_id(symbol_in, use_perp=use_perp_okx)
            df = okx_get_candles(instId, bar=tf, limit=limit)
            
            if df.empty:
                st.error("❌ لم يتم العثور على بيانات شموع لهذه العملة.")
            else:
                st.plotly_chart(plot_candles(df, f"OKX {instId} — {tf}"), use_container_width=True)

                st.subheader("📊 ملخص البيانات")
                col1, col2, col3 = st.columns(3)
                col1.metric("📈 آخر سعر", f"{df['close'].iloc[-1]:,.4f}")
                col2.metric("🔼 أعلى سعر", f"{df['high'].max():,.4f}")
                col3.metric("🔽 أدنى سعر", f"{df['low'].min():,.4f}")
                
                st.subheader("📦 Open Interest (OKX)")
                oi = okx_get_open_interest(instId)
                if oi:
                    res = analyze_oi(oi, df)
                    st.markdown(f"""
                    <div style="
                        background: rgba(20,20,20,0.8);
                        border-left: 8px solid {res['color']};
                        padding: 20px;
                        border-radius: 10px;
                        margin: 15px 0;
                        font-size: 1.2em;
                        color: {res['color']};
                    ">
                        <b style="font-size:1.5em;">{res['icon']} {res['msg']}</b><br>
                        🧭 مستوى الخطورة: <b style="color:{res['color']}">{res['risk']}</b>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"🕒 آخر تحديث: {pd.to_datetime(oi['ts'], unit='ms')}")
                else:
                    st.warning("⚠️ لا توجد بيانات OI متاحة لهذه الأداة.")

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ خطأ في الاتصال بواجهة API: {e}. يرجى التحقق من الرمز.")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")
