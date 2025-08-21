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
    table {
      width: 100%;
      max-width: 1000px;
      margin: auto;
      border-collapse: separate;
      border-spacing: 0 10px;
    }
    th, td {
      padding: 15px;
      background-color: #161b22;
      border: 1px solid #30363d;
      text-align: right;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    th:first-child, td:first-child { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
    th:last-child, td:last-child { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
    th {
      background-color: #21262d;
      font-weight: 700;
      color: #8b949e;
      border-color: #30363d;
    }
    tr:hover td {
      background-color: #1b2129;
    }
    .up { color: #2ea043; font-weight: bold; }
    .down { color: #f85149; font-weight: bold; }
    .extreme { color: #d29922; font-weight: bold; }
    .coin-name-cell {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .coin-icon {
      width: 24px;
      height: 24px;
      border-radius: 50%;
    }
    .coin-symbol {
        color: #8b949e;
        font-size: 12px;
    }
    .status-text {
        font-size: 14px;
        color: #8b949e;
        margin-top: 15px;
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
    params = {"instId": instId, "bar": bar, "limit": limit}
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

@st.cache_data(ttl=600)
def okx_get_tickers(instType="SWAP"):
    url = "https://www.okx.com/api/v5/market/tickers"
    params = {"instType": instType}
    try:
        r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        j = r.json()
        if j.get("code") != "0":
            st.error(f"خطأ في جلب بيانات tickers: {err_msg(j)}")
            return []
        return j.get("data", [])
    except requests.exceptions.RequestException as e:
        st.error(f"❌ خطأ في الاتصال بواجهة API: {e}. يرجى التحقق من الرمز.")
        return []

def okx_get_open_interest(instId):
    url = "https://www.okx.com/api/v5/public/open-interest"
    params = {"instId": instId}
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        return None
    return j.get("data", [])[0] if j.get("data") else None

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
        max_lever = float(data.get("lever", 1))
        return max_lever
    return None

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
    avg_volume = df["volume"].mean()
    if chg > 1 and oi_usd > threshold and avg_volume > df["volume"].mean() * 1.2:
        return {"msg": "صعود قوي + OI مرتفع + حجم مرتفع → صاعد بقوة", "risk": "Bullish", "icon": "🚀"}
    if chg < -1 and oi_usd > threshold and avg_volume > df["volume"].mean() * 1.2:
        return {"msg": "هبوط قوي + OI مرتفع + حجم مرتفع → هابط بقوة", "risk": "Bearish", "icon": "🔻"}
    if abs(chg) <= 1 and oi_usd > threshold:
        return {"msg": "سعر شبه ثابت + OI يرتفع بسرعة → تحرك وشيك", "risk": "High Risk", "icon": "⚖️"}
    return {"msg": "حركة طبيعية وهادئة", "risk": "Neutral", "icon": "✅"}

# ===================== Trading Calculator (with Fees) =====================
def trading_calculator(df, instId):
    if df.empty:
        st.error("❌ لا توجد بيانات لعرض الحاسبة. يرجى جلب البيانات أولاً.")
        return

    try:
        max_lever = okx_get_max_leverage(instId) or 125.0
    except Exception as e:
        st.warning(f"⚠️ فشل في جلب أقصى رافعة مالية. سيتم استخدام القيمة الافتراضية 125x. (الخطأ: {e})")
        max_lever = 125.0

    imr_default = 100 / max_lever if max_lever > 0 else 1
    mmr_default = imr_default / 2 if imr_default > 0 else 0.5

    st.subheader("📈 حاسبة التداول المتقدمة")
    with st.expander("افتح الحاسبة", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            imr = st.number_input("الهامش المبدئي (IMR %)", min_value=0.1, max_value=100.0, value=imr_default, step=0.1, key="imr")
            mmr = st.number_input("هامش الحفاظ (MMR %)", min_value=0.1, max_value=100.0, value=mmr_default, step=0.1, key="mmr")
            capital = st.number_input("المبلغ (USDT)", min_value=1.0, value=10.0, step=1.0, key="capital")

        with col2:
            current_price = st.number_input("السعر الحالي", min_value=0.01, value=float(df["close"].iloc[-1]), step=0.01, key="current_price")
            target_price = st.number_input("سعر الهدف", min_value=0.01, value=float(df["close"].iloc[-1]) * 1.05, step=0.01, key="target_price")
            direction = st.selectbox("الاتجاه", ["📈 شراء (Long)", "📉 بيع (Short)"], key="direction")

        with col3:
            trading_fees_percent = st.number_input("رسوم التداول (%)", min_value=0.0, max_value=10.0, value=0.05, step=0.01, key="fees")
            available_margin = st.number_input("الهامش المتاح في المحفظة", min_value=0.0, value=1000.0, step=100.0, key="available_margin")
            leverage = st.slider("الرافعة المالية", min_value=1, max_value=int(max_lever), value=int(max_lever/2), key="leverage")

        margin_diff = imr - mmr
        
        if margin_diff <= 0 or any(v is None for v in [imr, mmr, capital, current_price, target_price, trading_fees_percent, available_margin, leverage]):
            st.error("⚠️ يرجى إدخال قيم صالحة لجميع الحقول.")
            return

        price_change = ((target_price - current_price) / current_price) * 100
        actual_price_change = -price_change if direction == "📉 بيع (Short)" else price_change
        roi_percent = actual_price_change * leverage
        
        gross_pnl_value = (capital * roi_percent) / 100
        fees_value = capital * (trading_fees_percent / 100) * 2
        net_pnl_value = gross_pnl_value - fees_value
        
        if direction == "📈 شراء (Long)":
            liquidation_price = current_price * (1 - (margin_diff / 100))
        else:
            liquidation_price = current_price * (1 + (margin_diff / 100))

        col1_res, col2_res, col3_res = st.columns(3)
        with col1_res:
            st.metric("فرق الهامش", f"{margin_diff:.2f}%")
            st.metric("التغير %", f"{actual_price_change:.2f}%")
        with col2_res:
            st.metric("الربح الإجمالي (PnL)", f"{gross_pnl_value:.2f} USDT", delta_color="inverse" if gross_pnl_value < 0 else "normal")
            st.metric("الرسوم", f"{fees_value:.2f} USDT")
        with col3_res:
            st.metric("الربح الصافي (Net PnL)", f"{net_pnl_value:.2f} USDT", delta_color="inverse" if net_pnl_value < 0 else "normal")
            st.metric("سعر التصفية", f"{liquidation_price:.4f}")

        oi = okx_get_open_interest(instId)
        analysis = analyze_oi(st.session_state.df, oi) if oi else {"risk": "Unknown"}
        st.subheader("📊 اقتراح الصفقة")
        st.write(f"**الاقتراح:** {analysis['msg']} - **الخطورة:** {analysis['risk']} {analysis['icon']}")

# ===================== UI =====================
st.title("📊 أداة سوق العملات الرقمية — تحليل Open Interest")

if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "BTC"
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'inst_id' not in st.session_state:
    st.session_state.inst_id = okx_inst_id(st.session_state.selected_symbol)
    
st.markdown("---")
st.header("⚡ متتبع السوق اللحظي (OKX)")

col_sel, col_type, col_btn = st.columns([1, 0.5, 0.2])
with col_sel:
    threshold = st.selectbox("اختر عتبة التغيير (24 ساعة)", [1, 5, 10, 20, 50], index=2, key='threshold_select')
with col_type:
    change_type = st.radio("نوع التغيير", ["صعود (Gainers)", "هبوط (Losers)"], key='change_type')
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 تحديث العملات", key='update_coins_btn'):
        st.cache_data.clear()
        st.rerun()

tickers = okx_get_tickers(instType="SWAP")
filtered_tickers = []
if tickers:
    for t in tickers:
        try:
            change_percent = float(t['sodUtc']) * 100
            if change_type == "صعود (Gainers)" and change_percent >= threshold:
                filtered_tickers.append(t)
            elif change_type == "هبوط (Losers)" and change_percent <= -threshold:
                filtered_tickers.append(t)
        except (ValueError, KeyError):
            continue

    if change_type == "صعود (Gainers)":
        filtered_tickers.sort(key=lambda x: float(x['sodUtc']), reverse=True)
    else:
        filtered_tickers.sort(key=lambda x: float(x['sodUtc']), reverse=False)

    st.info("⚠️ اضغط على زر 'جلب وتحليل البيانات' بعد اختيار العملة.")
    
    coin_names = [f"**{c['instId']}** ({float(c['sodUtc']) * 100:.2f}%) - السعر: ${float(c['last']):.4f}" for c in filtered_tickers]
    
    selected_coin_name = st.selectbox("اختر عملة من القائمة", coin_names, key='coin_select')
    
    if selected_coin_name:
        selected_symbol = selected_coin_name.split('**')[1].split('**')[0].replace("-USDT-SWAP", "")
        if st.session_state.selected_symbol != selected_symbol:
            st.session_state.selected_symbol = selected_symbol
            st.session_state.symbol_changed = True
    else:
        st.session_state.symbol_changed = False
    
    st.markdown("---")
else:
    st.warning("⚠️ لا توجد بيانات متاحة في الوقت الحالي. حاول تغيير عتبة التغيير.")
    st.session_state.symbol_changed = False


# Main Analysis Section
st.header("🔍 تحليل العملة المختارة")
col_sym, col_tf, col_lim, col_perp = st.columns(4)
with col_sym:
    st.session_state.selected_symbol = st.text_input("أدخل رمز العملة:", st.session_state.selected_symbol, key="manual_symbol")
with col_tf:
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0, key='timeframe')
with col_lim:
    limit = st.slider("عدد الشموع", 50, 500, 200, 10, key='limit')
with col_perp:
    st.markdown("<br>", unsafe_allow_html=True)
    use_perp_okx = st.checkbox("OKX Perpetual (SWAP)", value=True, key='use_perp')

analyze_button = st.button("🚀 جلب وتحليل البيانات", key='analyze_btn')

if analyze_button or st.session_state.get('symbol_changed'):
    with st.spinner('⏳ جارٍ جلب البيانات...'):
        try:
            instId = okx_inst_id(st.session_state.selected_symbol, use_perp=use_perp_okx)
            df = okx_get_candles(instId, bar=tf, limit=limit)
            st.session_state.df = df
            st.session_state.inst_id = instId
            
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
        except RuntimeError as e:
            st.error(f"❌ حدث خطأ: {e}")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")
            st.exception(e)

# Display calculator only once
if 'df' in st.session_state and not st.session_state.df.empty:
    trading_calculator(st.session_state.df, st.session_state.inst_id)
    
# Clean up symbol_changed after use
if 'symbol_changed' in st.session_state:
    del st.session_state.symbol_changed

