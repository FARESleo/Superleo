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
    .calculator-section {
        background: rgba(22, 27, 34, 0.9);
        padding: 20px;
        border-radius: 15px;
        margin-top: 20px;
    }
    .stButton button {
        width: 100%;
        padding: 10px;
        background: #58a6ff;
        border: none;
        border-radius: 8px;
        color: #0d1117;
        font-weight: bold;
    }
    .stButton button:hover {
        background: #478bff;
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
    fig.add_trace(go.Scatter(x=df["ts"], y=df["close"], mode='lines', name='السعر', line=dict(color='cyan', width=2)))
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    fig.add_trace(go.Scatter(x=df["ts"], y=df['SMA_50'], mode='lines', name='SMA 50', line=dict(color='yellow', dash='dot')))
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
        last_candle_time = last_candle_time.tz_localize(timezone.utc)
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

# دالة جديدة لجلب maxLever من OKX API (حقيقي)
def okx_get_max_leverage(instId, instType="SWAP"):
    url = "https://www.okx.com/api/v5/public/instruments"
    params = {"instType": instType, "instId": instId}
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        st.error(f"خطأ في جلب maxLever: {err_msg(j)}")
        return None
    data = j.get("data", [])[0] if j.get("data") else None
    if data:
        max_lever = float(data.get("lever", 1))  # maxLever من الـ API
        return max_lever
    return None

# ===================== OI Analysis ===================== (محسن لدقة أكبر)
def analyze_oi(df, oi, threshold=5_000_000):
    if df.empty or not oi:
        return {"msg": "❌ لا توجد بيانات كافية", "risk": "Unknown", "icon": "❌"}
    oi_usd = float(oi.get("oiUsd", 0))
    if len(df) < 5:
        return {"msg": "❌ بيانات غير كافية للتحليل", "risk": "Unknown", "icon": "❌"}
    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-5]
    chg = ((last_close - prev_close) / prev_close) * 100
    avg_volume = df["volume"].mean()  # إضافة فحص لحجم التداول لدقة
    if chg > 1 and oi_usd > threshold and avg_volume > df["volume"].mean() * 1.2:
        return {"msg": "صعود قوي + OI مرتفع + حجم مرتفع → صاعد بقوة", "risk": "Bullish", "icon": "🚀"}
    if chg < -1 and oi_usd > threshold and avg_volume > df["volume"].mean() * 1.2:
        return {"msg": "هبوط قوي + OI مرتفع + حجم مرتفع → هابط بقوة", "risk": "Bearish", "icon": "🔻"}
    if abs(chg) <= 1 and oi_usd > threshold:
        return {"msg": "سعر شبه ثابت + OI يرتفع بسرعة → تحرك وشيك", "risk": "High Risk", "icon": "⚖️"}
    return {"msg": "حركة طبيعية وهادئة", "risk": "Neutral", "icon": "✅"}

# ===================== Trading Calculator ===================== (مع قيم حقيقية)
def trading_calculator(df, instId):
    if df.empty:
        st.error("❌ لا توجد بيانات لعرض الحاسبة. يرجى جلب البيانات أولاً.")
        return

    max_lever = okx_get_max_leverage(instId) or 125.0  # افتراضي إذا فشل الجلب (مثل BTC-SWAP)
    imr_default = 100 / max_lever  # IMR حقيقي من maxLever
    mmr_default = imr_default / 2  # MMR تقريبي (نصف IMR، كما في بعض البورصات)

    st.subheader("📈 حاسبة التداول المتقدمة")
    with st.expander("افتح الحاسبة", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            imr = st.number_input("الهامش المبدئي (IMR %)", min_value=0.1, max_value=100.0, value=imr_default, step=0.1)
            mmr = st.number_input("هامش الحفاظ (MMR %)", min_value=0.1, max_value=100.0, value=mmr_default, step=0.1)
            capital = st.number_input("المبلغ (USDT)", min_value=1.0, value=10.0, step=1.0)

        with col2:
            current_price = st.number_input("السعر الحالي", min_value=0.01, value=float(df["close"].iloc[-1]), step=0.01)
            target_price = st.number_input("سعر الهدف", min_value=0.01, value=float(df["close"].iloc[-1]) * 1.05, step=0.01)
            direction = st.selectbox("الاتجاه", ["📈 شراء (Long)", "📉 بيع (Short)"])

        # حساب الرافعة المالية
        margin_diff = imr - mmr
        max_leverage = 100 / margin_diff if margin_diff > 0 else 1
        leverage_options = [5, 10, 20, 30, 50, 100]
        leverage_labels = [f"{x}x ({'منخفضة' if x <= 10 else 'متوسطة' if x <= 50 else 'عالية جداً'})" for x in leverage_options if x <= max_leverage]
        leverage_labels.append(f"{max_leverage:.2f}x (القصوى)")
        leverage = st.selectbox("اختر الرافعة المالية", leverage_labels, index=0)
        leverage = float(leverage.split("x")[0])

        # الحسابات
        if margin_diff <= 0 or any(v is None for v in [imr, mmr, capital, current_price, target_price]):
            st.error("⚠️ يرجى إدخال قيم صالحة لجميع الحقول.")
            return

        price_change = ((target_price - current_price) / current_price) * 100
        actual_price_change = -price_change if direction == "📉 بيع (Short)" else price_change
        roi_percent = actual_price_change * leverage
        pnl_value = (capital * roi_percent) / 100

        if direction == "📈 شراء (Long)":
            liquidation_price = current_price * (1 - (margin_diff / 100))
        else:
            liquidation_price = current_price * (1 + (margin_diff / 100))

        # عرض النتائج
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("فرق الهامش", f"{margin_diff:.2f}%")
            st.metric("التغير %", f"{actual_price_change:.2f}%")
        with col2:
            st.metric("ROI %", f"{roi_percent:.2f}%", delta_color="inverse")
            st.metric("PnL (USDT)", f"{pnl_value:.2f} USDT", delta_color="inverse" if pnl_value < 0 else "normal")
        with col3:
            st.metric("سعر التصفية", f"{liquidation_price:.4f}")

        # اقتراح الصفقة بناءً على التحليل
        oi = okx_get_open_interest(instId)
        analysis = analyze_oi(df, oi) if oi else {"risk": "Unknown"}
        st.subheader("📊 اقتراح الصفقة")
        if analysis["risk"] == "Bullish":
            suggestion = "📈 شراء (Long)" if direction == "📈 شراء (Long)" else "📉 بيع (Short) قد لا يكون مناسبًا"
            entry_price = current_price
            exit_price = target_price
            return_percent = roi_percent if direction == "📈 شراء (Long)" else -roi_percent
        elif analysis["risk"] == "Bearish":
            suggestion = "📉 بيع (Short)" if direction == "📉 بيع (Short)" else "📈 شراء (Long) قد لا يكون مناسبًا"
            entry_price = current_price
            exit_price = target_price
            return_percent = -roi_percent if direction == "📉 بيع (Short)" else roi_percent
        else:
            suggestion = "⚖️ الوضع محايد، يرجى تقييم إضافي"
            entry_price = current_price
            exit_price = target_price
            return_percent = roi_percent

        st.write(f"**الاقتراح:** {suggestion}")
        st.write(f"**سعر الدخول:** {entry_price:.4f}")
        st.write(f"**سعر الخروج:** {exit_price:.4f}")
        st.write(f"**نسبة العائد:** {return_percent:.2f}%")

# ===================== UI =====================
st.title("📊 أداة سوق العملات الرقمية — تحليل Open Interest")

with st.sidebar:
    st.header("⚙️ خيارات التحليل")
    symbol_in = st.text_input("أدخل رمز العملة:", "BTC")
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
    use_perp_okx = st.checkbox("OKX Perpetual (SWAP)", value=True)
    analyze_button = st.button("🚀 جلب وتحليل البيانات")
    
# تخزين البيانات في حالة الجلسة
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
    st.session_state.symbol = ""
    st.session_state.use_perp = True
    st.session_state.show_calculator = False

# عند النقر على "جلب وتحليل البيانات"
if analyze_button:
    st.session_state.symbol = symbol_in
    st.session_state.use_perp = use_perp_okx
    with st.spinner('⏳ جارٍ جلب البيانات...'):
        try:
            instId = okx_inst_id(st.session_state.symbol, use_perp=st.session_state.use_perp)
            df = okx_get_candles(instId, bar=tf, limit=limit)
            st.session_state.df = df
            
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

                # إضافة خيار الحاسبة
                if st.button("📊 افتح حاسبة التداول"):
                    st.session_state.show_calculator = True
                    st.experimental_rerun()  # إعادة تشغيل لضمان التحديث

except requests.exceptions.HTTPError as e:
            st.error(f"❌ خطأ في الاتصال بواجهة API: {e}. يرجى التحقق من الرمز.")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")

# عرض الحاسبة إذا تم تفعيلها
if st.session_state.show_calculator and not st.session_state.df.empty:
    trading_calculator(st.session_state.df, okx_inst_id(st.session_state.symbol, use_perp=st.session_state.use_perp))
