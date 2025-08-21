import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="أداة سوق العملات الرقمية", layout="wide")

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
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color='green', decreasing_line_color='red'
    )])
    fig.update_layout(
        title=title, 
        xaxis_rangeslider_visible=False, 
        height=520,
        title_font_size=24,
        margin=dict(l=0, r=0, t=50, b=0)
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

# ===================== OI Analysis =====================
def analyze_oi(oi, df, threshold=5_000_000):
    if not oi or df.empty or len(df) < 5:
        return ("❌ لا توجد بيانات كافية للتحليل.", "error")

    try:
        oi_val = float(oi["oiUsd"])
    except (ValueError, KeyError):
        return ("⚠️ لم أتمكن من قراءة OI بشكل صحيح.", "warning")

    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-5]
    price_change = ((last_close - prev_close) / prev_close) * 100

    if price_change > 1:
        if oi_val > threshold:
            return ("📈 ارتفاع السعر مع OI كبير يؤكد قوة الاتجاه الصعودي.", "success")
        else:
            return ("⚠️ ارتفاع السعر مع OI منخفض. قد يكون حركة مؤقتة.", "warning")
    elif price_change < -1:
        if oi_val > threshold:
            return ("📉 انخفاض السعر مع OI كبير يؤكد قوة الاتجاه الهبوطي.", "error")
        else:
            return ("⚠️ انخفاض السعر مع OI منخفض. قد يكون مجرد تصفية صفقات.", "warning")
    elif abs(price_change) < 0.5:
        if oi_val > threshold:
             return ("⚖️ السعر شبه ثابت مع OI كبير. احتمال تجميع/تصريف.", "warning")
        else:
            return ("✅ حركة عادية بلا إشارات قوية.", "info")
    else:
        return ("✅ حركة عادية بلا إشارات قوية.", "info")

# ===================== UI =====================
st.title("📊 أداة سوق العملات الرقمية — الشموع + Open Interest")

with st.sidebar:
    st.header("⚙️ خيارات التحليل")
    symbol_in = st.text_input("أدخل رمز العملة:", "xrp")
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
    threshold = st.number_input("حد OI (USD)", min_value=1_000_000, value=5_000_000, step=500_000)
    use_perp_okx = st.checkbox("OKX Perpetual (SWAP)", value=True)
    analyze_button = st.button("جلب وتحليل 🔍")

if analyze_button:
    with st.spinner('جارٍ جلب البيانات...'):
        try:
            instId = okx_inst_id(symbol_in, use_perp=use_perp_okx)
            df = okx_get_candles(instId, bar=tf, limit=limit)
            
            if df.empty:
                st.error("❌ لم يتم العثور على بيانات شموع لهذه العملة.")
            else:
                # عرض الرسم البياني
                st.plotly_chart(plot_candles(df, f"OKX {instId} — {tf}"), use_container_width=True)

                # عرض النتائج في أقسام
                st.subheader("📊 ملخص البيانات")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("آخر سعر", f"{df['close'].iloc[-1]:,.4f}")
                col2.metric("أعلى سعر", f"{df['high'].max():,.4f}")
                col3.metric("أدنى سعر", f"{df['low'].min():,.4f}")
                price_change = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
                col4.metric("تغير آخر 5 شموع", f"{price_change:.2f}%")

                # قسم تحليل Open Interest
                st.subheader("📦 Open Interest (OKX)")
                oi = okx_get_open_interest(instId)
                if oi:
                    col_oi_val, col_oi_msg = st.columns([1, 2])
                    col_oi_val.metric("قيمة OI بالدولار", f"{float(oi['oiUsd']):,.0f}")
                    
                    msg, level = analyze_oi(oi, df, threshold)
                    if level == "success":
                        col_oi_msg.success(msg)
                    elif level == "warning":
                        col_oi_msg.warning(msg)
                    elif level == "error":
                        col_oi_msg.error(msg)
                    else:
                        col_oi_msg.info(msg)

                    st.caption(f"آخر تحديث: {pd.to_datetime(oi['ts'], unit='ms')}")
                else:
                    st.warning("لا توجد بيانات OI متاحة لهذه الأداة.")

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ خطأ في الاتصال بواجهة API: {e}. يرجى التحقق من الرمز.")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")
