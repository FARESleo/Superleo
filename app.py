import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="📊 أداة تحليل سوق العملات الرقمية", layout="wide")

# ===================== Helpers =====================
def err_msg(resp_json):
    return f"OKX error: code={resp_json.get('code')} msg={resp_json.get('msg')}"

def to_df_okx(candles):
    # robust conversion from OKX candle rows to DataFrame
    if not candles:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume"])
    # take first 6 columns (ts, o, h, l, c, vol)
    df = pd.DataFrame(candles)
    df = df.iloc[:, :6]
    df.columns = ["ts","open","high","low","close","volume"]
    # convert types robustly
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce").fillna(0).astype("int64")
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", errors="coerce")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.sort_values("ts").reset_index(drop=True)

def plot_candles(df, title):
    fig = go.Figure()

    # Candles
    fig.add_trace(go.Candlestick(
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color='green', decreasing_line_color='red', name="Candles"
    ))

    # Volume as bar on secondary axis
    fig.add_trace(go.Bar(
        x=df["ts"], y=df["volume"], name="Volume", marker_color="lightblue", opacity=0.5, yaxis="y2"
    ))

    # SMA/EMA (if enough data)
    if len(df) >= 20:
        df["SMA20"] = df["close"].rolling(20).mean()
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df["ts"], y=df["SMA20"], mode="lines", name="SMA20", line=dict(color="blue")))
        fig.add_trace(go.Scatter(x=df["ts"], y=df["EMA50"], mode="lines", name="EMA50", line=dict(color="orange")))

    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        height=640,
        margin=dict(l=20, r=20, t=60, b=20),
        yaxis=dict(title="السعر"),
        yaxis2=dict(title="الحجم", overlaying="y", side="right", showgrid=False)
    )
    # improve pan/zoom behavior
    fig.update_xaxes(rangeslider_visible=False, autorange=True)
    fig.update_yaxes(autorange=True)
    return fig

# ===================== OKX API =====================
def okx_inst_id(symbol_text, use_perp=True):
    s = (symbol_text or "").strip().upper().replace("-", "").replace(" ", "")
    if not s:
        return ""
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
    data = j.get("data", [])
    return data[0] if data else None

# ===================== OI Analysis =====================
def analyze_oi(oi, df, threshold=5_000_000):
    if not oi or df.empty or len(df) < 5:
        return ("❌ لا توجد بيانات كافية للتحليل.", "gray")

    # try read several possible keys safely
    oi_usd = None
    for key in ("oiUsd", "oi_usd", "openInterestUsd", "oiValue", "oi"):
        if key in oi:
            try:
                oi_usd = float(oi[key])
                break
            except:
                continue
    if oi_usd is None:
        # try nested numeric values
        try:
            oi_usd = float(next((v for v in oi.values() if isinstance(v, (int,float))), 0))
        except:
            oi_usd = 0.0

    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-5]
    price_change = ((last_close - prev_close) / prev_close) * 100

    # rules (clearer text)
    if price_change > 1:
        if oi_usd > threshold:
            return (f"🟢 صعود قوي ({price_change:.2f}%) مدعوم بزيادة OI (${oi_usd:,.0f}) → اتجاه صعودي حقيقي.", "green")
        else:
            return (f"🟡 صعود ({price_change:.2f}%) مع OI منخفض (${oi_usd:,.0f}) → احذر فخ شراء محتمل.", "orange")
    elif price_change < -1:
        if oi_usd > threshold:
            return (f"🔴 هبوط قوي ({price_change:.2f}%) مدعوم بزيادة OI (${oi_usd:,.0f}) → ضغط بيع حقيقي.", "red")
        else:
            return (f"🟡 هبوط ({price_change:.2f}%) مع OI منخفض (${oi_usd:,.0f}) → قد تكون تصفية مراكز.", "orange")
    else:
        if oi_usd > threshold:
            return (f"⚖️ السعر ثابت نسبياً ({price_change:.2f}%) وOI مرتفع (${oi_usd:,.0f}) → احتمال تجميع أو تصريف من كبار اللاعبين.", "blue")
        else:
            return (f"✅ حركة هادئة ({price_change:.2f}%) وOI منخفض → لا توجد إشارات قوية.", "gray")

# ===================== UI =====================
st.title("📊 أداة تحليل سوق العملات الرقمية — شموع + Open Interest (OKX)")

with st.sidebar:
    st.header("⚙️ الإعدادات")
    symbol_in = st.text_input("أدخل رمز العملة (مثال: xrp أو BTCUSDT):", "xrp")
    tf = st.selectbox("الإطار الزمني", ["5m","15m","30m","1h","4h","1d"], index=1)
    limit = st.slider("عدد الشموع:", 50, 500, 200, 10)
    use_perp_okx = st.checkbox("عرض عقود دائمة (SWAP) إن وُجد", value=True)
    threshold = st.number_input("الحدّ لتمييز OI بالدولار (threshold):", min_value=100_000, value=5_000_000, step=100_000)
    analyze_button = st.button("جلب وتحليل 🔍")

if analyze_button:
    instId = okx_inst_id(symbol_in, use_perp=use_perp_okx)
    if not instId:
        st.error("رمز غير صالح، حاول مثلًا: xrp أو BTCUSDT")
    else:
        with st.spinner("🔄 جلب البيانات من OKX..."):
            try:
                df = okx_get_candles(instId, bar=tf, limit=limit)
            except Exception as e:
                st.error(f"فشل في جلب الشموع: {e}")
                df = pd.DataFrame()

            oi_snapshot = None
            try:
                oi_snapshot = okx_get_open_interest(instId)
            except Exception:
                oi_snapshot = None

        if df.empty:
            st.error("❌ لم نتمكن من جلب شموع صالحة. جرّب تغيير شكل الرمز (مثلاً: XRPUSDT أو XRP-USDT) أو تعطيل SWAP.")
        else:
            # plot
            st.plotly_chart(plot_candles(df, f"OKX {instId} — {tf}"), use_container_width=True)

            # summary metrics
            st.subheader("📊 الملخص السريع")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("آخر سعر", f"{df['close'].iloc[-1]:,.6f}")
            col2.metric("أعلى سعر (خلال الفترة)", f"{df['high'].max():,.6f}")
            col3.metric("أدنى سعر (خلال الفترة)", f"{df['low'].min():,.6f}")
            price_change_5 = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
            col4.metric("تغير آخر 5 شموع", f"{price_change_5:.2f}%")

            # OI analysis and display
            st.subheader("📦 Open Interest (OKX snapshot)")
            if oi_snapshot:
                msg, color = analyze_oi(oi_snapshot, df, threshold=threshold)
                # display colored header
                st.markdown(f"<h3 style='color:{color};'>{msg}</h3>", unsafe_allow_html=True)
                st.caption(f"بيانات الأخيرة (ts): {pd.to_datetime(oi_snapshot.get('ts',0), unit='ms', errors='coerce')}")
                # show numeric fields in neat columns if present
                try:
                    oi_usd = float(oi_snapshot.get("oiUsd") or oi_snapshot.get("oi_usd") or 0)
                    oi_val = float(oi_snapshot.get("oi") or oi_snapshot.get("oiValue") or 0)
                    col1, col2 = st.columns(2)
                    col1.metric("آخر OI (USD)", f"${oi_usd:,.0f}")
                    col2.metric("آخر OI (units)", f"{oi_val:,.0f}")
                except Exception:
                    pass
            else:
                st.warning("لا توجد لقطة OI من OKX متاحة لهذا الزوج.")

            # download CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ تنزيل شموع (CSV)", csv, file_name=f"{symbol_in}_{tf}.csv", mime="text/csv")

            # helpful tips
            st.markdown("---")
            st.markdown("**نصائح:** إذا لم تظهر بيانات شموع أو OI، جرّب كتابة الرمز بشكل كامل مثل `XRPUSDT` أو `XRP-USDT`، أو تعطيل SWAP. إن كانت هناك قيود جغرافية فاشغّل التطبيق على سيرفر خارجي أو Streamlit Cloud.")
