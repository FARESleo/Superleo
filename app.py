import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="📊 أداة تحليل سوق العملات الرقمية", layout="wide")

# ===================== Helpers =====================
def err_msg(resp_json):
    return f"OKX error: code={resp_json.get('code')} msg={resp_json.get('msg')}"

def to_df_okx(candles):
    cols = ["ts","open","high","low","close","volume","volCcy","volQuote","confirm"]
    df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
    df["ts"] = pd.to_datetime(df["ts"].astype(str).astype(np.int64), unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    return df.sort_values("ts").reset_index(drop=True)

def plot_candles(df, title):
    fig = go.Figure()

    # شموع
    fig.add_trace(go.Candlestick(
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color='green', decreasing_line_color='red',
        name="Candles"
    ))

    # حجم التداول
    fig.add_trace(go.Bar(
        x=df["ts"], y=df["volume"],
        name="Volume", marker_color="lightblue", opacity=0.5, yaxis="y2"
    ))

    # متوسطات متحركة
    df["SMA20"] = df["close"].rolling(20).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    fig.add_trace(go.Scatter(
        x=df["ts"], y=df["SMA20"], mode="lines", name="SMA 20", line=dict(color="blue")
    ))
    fig.add_trace(go.Scatter(
        x=df["ts"], y=df["EMA50"], mode="lines", name="EMA 50", line=dict(color="orange")
    ))

    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        height=600,
        margin=dict(l=20, r=20, t=50, b=20),
        yaxis=dict(title="السعر"),
        yaxis2=dict(title="الحجم", overlaying="y", side="right", showgrid=False)
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
def analyze_oi(oi, df):
    if not oi or df.empty or len(df) < 5:
        return "❌ لا توجد بيانات كافية للتحليل.", "gray"

    try:
        oi_val = float(oi["oiUsd"])
    except (ValueError, KeyError):
        return "⚠️ لم أتمكن من قراءة OI بشكل صحيح.", "gray"

    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-5]
    price_change = ((last_close - prev_close) / prev_close) * 100

    if price_change > 1:
        if oi_val > 5_000_000:
            return "🟢 صعود قوي مدعوم بزيادة OI (مراكز شراء جديدة).", "green"
        else:
            return "🟡 صعود ضعيف بدون دعم قوي (احتمال فخ).", "orange"
    elif price_change < -1:
        if oi_val > 5_000_000:
            return "🔴 هبوط قوي مدعوم بزيادة OI (مراكز بيع).", "red"
        else:
            return "🟡 هبوط ضعيف (تصفية مراكز فقط).", "orange"
    else:
        if oi_val > 5_000_000:
            return "⚖️ السعر شبه ثابت مع OI كبير → تجميع/تصريف محتمل.", "blue"
        else:
            return "✅ حركة طبيعية بدون إشارات قوية.", "gray"

# ===================== UI =====================
st.title("📊 أداة احترافية لتحليل سوق العملات الرقمية")

with st.sidebar:
    st.header("⚙️ الإعدادات")
    symbol_in = st.text_input("أدخل رمز العملة:", "BTC")
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
    use_perp_okx = st.checkbox("OKX Perpetual (SWAP)", value=True)
    analyze_button = st.button("جلب وتحليل 🔍")

if analyze_button:
    with st.spinner('🔄 جارٍ جلب البيانات...'):
        try:
            instId = okx_inst_id(symbol_in, use_perp=use_perp_okx)
            df = okx_get_candles(instId, bar=tf, limit=limit)
            
            if df.empty:
                st.error("❌ لم يتم العثور على بيانات شموع لهذه العملة.")
            else:
                # --- رسم ---
                st.plotly_chart(plot_candles(df, f"OKX {instId} — {tf}"), use_container_width=True)

                # --- ملخص ---
                st.subheader("📊 ملخص البيانات")
                col1, col2, col3 = st.columns(3)
                col1.metric("آخر سعر", f"{df['close'].iloc[-1]:,.4f}")
                col2.metric("أعلى سعر", f"{df['high'].max():,.4f}")
                col3.metric("أدنى سعر", f"{df['low'].min():,.4f}")

                # --- Open Interest ---
                st.subheader("📦 تحليل Open Interest")
                oi = okx_get_open_interest(instId)
                if oi:
                    signal, color = analyze_oi(oi, df)
                    st.markdown(f"<h3 style='color:{color}'>{signal}</h3>", unsafe_allow_html=True)
                    st.caption(f"آخر تحديث: {pd.to_datetime(oi['ts'], unit='ms')}")
                else:
                    st.warning("لا توجد بيانات OI متاحة لهذه الأداة.")

                # --- زر تحميل البيانات ---
                st.download_button(
                    "⬇️ تحميل البيانات (CSV)",
                    df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{symbol_in}_{tf}.csv",
                    mime="text/csv"
                )

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ خطأ في الاتصال بواجهة API: {e}.")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")
