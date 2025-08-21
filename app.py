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
def analyze_oi(close_price, prev_close_price, oi_usd, threshold=5_000_000):
    chg = ((close_price - prev_close_price) / prev_close_price) * 100
    
    if chg > 1 and oi_usd > threshold:
        return "Bullish"
    
    if chg > 1 and oi_usd <= threshold:
        return "Weak Bullish"
    
    if chg < -1 and oi_usd > threshold:
        return "Bearish"
    
    if chg < -1 and oi_usd <= threshold:
        return "Weak Bearish"
    
    if abs(chg) <= 1 and oi_usd > threshold:
        return "High Risk"
    
    return "Neutral"

# ===================== Backtesting Logic =====================
def run_backtest(df):
    if df.empty:
        return {"total_pnl": 0, "wins": 0, "losses": 0, "win_rate": 0, "avg_pnl": 0}
    
    trades = []
    position = None # 'long' or None
    buy_price = 0
    
    # محاكاة التداول
    for i in range(5, len(df)):
        current_row = df.iloc[i]
        prev_close_price = df.iloc[i-5]["close"]
        
        # تحليل الإشارة
        oi_data = okx_get_open_interest(okx_inst_id(st.session_state.symbol, st.session_state.use_perp))
        if not oi_data:
            continue
            
        oi_usd = float(oi_data.get("oiUsd", 0))
        signal = analyze_oi(current_row["close"], prev_close_price, oi_usd)
        
        if signal == "Bullish" and position is None:
            buy_price = current_row["close"]
            position = "long"
        
        elif signal == "Bearish" and position == "long":
            sell_price = current_row["close"]
            pnl = sell_price - buy_price
            trades.append(pnl)
            position = None
            buy_price = 0
            
    # حساب النتائج
    if not trades:
        return {"total_pnl": 0, "wins": 0, "losses": 0, "win_rate": 0, "avg_pnl": 0}

    total_pnl = sum(trades)
    wins = sum(1 for t in trades if t > 0)
    losses = sum(1 for t in trades if t <= 0)
    win_rate = (wins / len(trades)) * 100 if trades else 0
    avg_pnl = total_pnl / len(trades)
    
    return {
        "total_pnl": total_pnl,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_pnl": avg_pnl
    }

# ===================== UI =====================
st.title("📊 أداة سوق العملات الرقمية — تحليل Open Interest")

with st.sidebar:
    st.header("⚙️ خيارات التحليل")
    symbol_in = st.text_input("أدخل رمز العملة:", "BTC")
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
    use_perp_okx = st.checkbox("OKX Perpetual (SWAP)", value=True)
    analyze_button = st.button("🚀 جلب وتحليل البيانات")
    
    st.markdown("---")
    st.subheader("🕵️‍♂️ تقييم الاستراتيجية")
    backtest_button = st.button("📈 تشغيل التحليل التاريخي (Backtest)")
    
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
                    res_instant = analyze_oi(df['close'].iloc[-1], df['close'].iloc[-5], float(oi.get("oiUsd", 0)))
                    
                    if res_instant == "Bullish":
                        st.success(f"**🚀 صعود قوي + OI مرتفع → صاعد بقوة** - مستوى الخطورة: **Bullish**")
                    elif res_instant == "Bearish":
                        st.error(f"**🔻 هبوط قوي + OI مرتفع → هابط بقوة** - مستوى الخطورة: **Bearish**")
                    elif "Weak" in res_instant or res_instant == "High Risk":
                        st.warning(f"**⚖️ تحرك وشيك: مراقبة حذرة. قد يكون صعوداً أو هبوطاً قوياً.** - مستوى الخطورة: **High Risk**")
                    else:
                        st.info(f"**✅ حركة طبيعية وهادئة** - مستوى الخطورة: **Neutral**")
                    
                    st.caption(f"🕒 آخر تحديث: {pd.to_datetime(oi['ts'], unit='ms')}")
                else:
                    st.warning("⚠️ لا توجد بيانات OI متاحة لهذه الأداة.")

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ خطأ في الاتصال بواجهة API: {e}. يرجى التحقق من الرمز.")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")

# عند النقر على "تشغيل التحليل التاريخي"
if backtest_button:
    if not st.session_state.df.empty:
        with st.spinner('⏳ جارٍ تشغيل التحليل التاريخي...'):
            results = run_backtest(st.session_state.df)
            
            st.subheader("📊 نتائج التحليل التاريخي (Backtest)")
            
            if results["total_pnl"] > 0:
                st.success(f"✅ **أداء ممتاز!** صافي الربح كان: {results['total_pnl']:.4f}")
            elif results["total_pnl"] < 0:
                st.error(f"❌ **أداء ضعيف!** صافي الخسارة كان: {abs(results['total_pnl']):.4f}")
            else:
                st.info("ℹ️ **أداء محايد!** لم تسجل صفقات أو كان صافي الربح 0.")
            
            st.markdown("---")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("عدد الصفقات الرابحة", f"{results['wins']}")
            col2.metric("عدد الصفقات الخاسرة", f"{results['losses']}")
            col3.metric("نسبة النجاح (Win Rate)", f"{results['win_rate']:.2f}%")
            
            st.markdown(f"**ملاحظة**: التحليل يعتمد على استراتيجية بسيطة (شراء عند Bullish وبيع عند Bearish).")
    else:
        st.warning("⚠️ يرجى جلب البيانات أولاً قبل تشغيل التحليل التاريخي.")

