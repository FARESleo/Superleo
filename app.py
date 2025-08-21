
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="📊 أداة سوق العملات الرقمية", layout="wide")

# ---------------- CSS شامل مع صورة خلفية تقنية ----------------
IMG = "https://images.unsplash.com/photo-1621504805083-d1b52d2c8a4d?auto=format&fit=crop&w=1600&q=80"

st.markdown(f"""
<style>
/* apply background on multiple possible Streamlit containers to be robust */
[data-testid="stAppViewContainer"], .stApp, .main, .block-container, section[data-testid="stAppViewContainer"] {{
  background-image: linear-gradient(rgba(5,10,15,0.65), rgba(5,10,15,0.65)), url('{IMG}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}

/* dark translucent main panel */
.block-container {{
  background: rgba(10, 15, 20, 0.65) !important;
  border-radius: 12px;
  padding: 18px;
}}

/* sidebar styling */
[data-testid="stSidebar"] {{
  background: rgba(0,0,0,0.6);
  color: #fff;
  border-radius: 10px;
}}

/* card-like alert style */
.alert-card {{
  background: rgba(20,20,20,0.7);
  border-radius: 10px;
  padding: 14px;
  margin: 12px 0;
  color: #fff;
  box-shadow: 0 6px 18px rgba(0,0,0,0.45);
}}

/* small responsive tweaks */
@media (max-width: 768px) {{
  .block-container {{ padding: 12px; }}
}}
</style>
""", unsafe_allow_html=True)

# ---------------- Helpers ----------------
def to_df_okx(candles):
    """Robust conversion of OKX candles list to dataframe without numpy."""
    if not candles:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume"])
    df = pd.DataFrame(candles).iloc[:, :6]      # take first 6 columns
    df.columns = ["ts","open","high","low","close","volume"]
    # safe numeric conversion
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce").fillna(0).astype('int64')
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", errors="coerce")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.sort_values("ts").reset_index(drop=True)

def plot_candles(df, title):
    fig = go.Figure()
    # candles
    fig.add_trace(go.Candlestick(
        x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color='rgba(0,255,170,0.95)', decreasing_line_color='rgba(255,60,90,0.95)',
        name="Candles"
    ))
    # volume as bar on secondary y-axis
    fig.add_trace(go.Bar(
        x=df["ts"], y=df["volume"], name="Volume", marker_color="rgba(100,150,255,0.5)", opacity=0.5, yaxis="y2"
    ))
    # SMA/EMA if available
    if len(df) >= 20:
        df["SMA20"] = df["close"].rolling(20).mean()
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df["ts"], y=df["SMA20"], mode="lines", name="SMA20",
                                 line=dict(color="rgba(255,220,0,0.9)", width=1.5)))
        fig.add_trace(go.Scatter(x=df["ts"], y=df["EMA50"], mode="lines", name="EMA50",
                                 line=dict(color="rgba(255,140,0,0.9)", width=1.2)))
    # layout (dark)
    fig.update_layout(
        template="plotly_dark",
        title=title,
        xaxis_rangeslider_visible=False,
        height=620,
        margin=dict(l=12, r=12, t=56, b=12),
        yaxis=dict(title="السعر"),
        yaxis2=dict(title="الحجم", overlaying="y", side="right", showgrid=False),
        plot_bgcolor="rgba(0,0,0,0.5)",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    # ensure smooth pan/zoom
    fig.update_xaxes(autorange=True)
    fig.update_yaxes(autorange=True)
    return fig

# ---------------- OKX API ----------------
def okx_inst_id(symbol_text, use_perp=True):
    s = (symbol_text or "").strip().upper().replace("-", "").replace(" ", "")
    if not s:
        return ""
    if not s.endswith("USDT"):
        s += "USDT"
    base = s[:-4]
    return f"{base}-USDT-SWAP" if use_perp else f"{base}-USDT"

def okx_get_candles(instId, bar="15m", limit=200):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": instId, "bar": bar, "limit": limit}
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        # return empty df to handle gracefully
        return pd.DataFrame()
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

# ---------------- OI analysis (card result) ----------------
def analyze_oi(oi, df, threshold=5_000_000):
    if (not oi) or df.empty or len(df) < 6:
        return {"msg":"❌ بيانات غير كافية", "color":"#888", "icon":"❌", "level":"neutral"}
    # try several keys safely
    oi_usd = 0.0
    for k in ("oiUsd","oi_usd","openInterestUsd","oiValue","oi"):
        if k in oi:
            try:
                oi_usd = float(oi[k])
                break
            except:
                continue
    # fallback: try numbers in values
    if oi_usd == 0.0:
        try:
            for v in oi.values():
                if isinstance(v,(int,float)):
                    oi_usd = float(v); break
        except:
            oi_usd = 0.0

    last = df["close"].iloc[-1]
    prev = df["close"].iloc[-5]
    chg = ((last - prev) / prev) * 100

    # decision rules with icons + hex colors
    if chg > 1 and oi_usd > threshold:
        return {"msg":f"🚀 صعود قوي ({chg:.2f}%) مدعوم بزيادة OI (${oi_usd:,.0f})", "color":"#1eff7a", "icon":"🚀", "level":"bull"}
    if chg > 1:
        return {"msg":f"🟡 صعود ضعيف ({chg:.2f}%) بدون دعم OI كبير (${oi_usd:,.0f}) — انتبه لفخ", "color":"#ffd24d", "icon":"🟡", "level":"caution"}
    if chg < -1 and oi_usd > threshold:
        return {"msg":f"🔻 هبوط قوي ({chg:.2f}%) مدعوم بزيادة OI (${oi_usd:,.0f}) — ضغط بيع", "color":"#ff5c6e", "icon":"🔻", "level":"bear"}
    if chg < -1:
        return {"msg":f"⚠️ هبوط ({chg:.2f}%) مع OI منخفض (${oi_usd:,.0f}) — قد تكون تصفية", "color":"#ff9f43", "icon":"⚠️", "level":"caution"}
    if oi_usd > threshold:
        return {"msg":f"⚖️ سعر ثابت نسبياً ({chg:.2f}%) وOI مرتفع (${oi_usd:,.0f}) → احتمال تجميع/تصريف", "color":"#5bc0de", "icon":"⚖️", "level":"alert"}
    return {"msg":f"✅ حركة طبيعية ({chg:.2f}%) وOI منخفض", "color":"#cfcfcf", "icon":"✅", "level":"neutral"}

# ---------------- UI ----------------
st.title("📊 تحليل السوق — شموع + Open Interest (OKX)")

with st.sidebar:
    st.header("⚙️ إعدادات")
    symbol_in = st.text_input("رمز العملة (مثال: xrp أو BTCUSDT):", "xrp")
    tf = st.selectbox("الإطار الزمني:", ["5m","15m","30m","1h","4h","1d"], index=1)
    limit = st.slider("عدد الشموع:", 50, 500, 200, 10)
    use_perp = st.checkbox("عرض عقود دائمة (SWAP) إن وُجد", value=True)
    threshold = st.number_input("عتبة OI بالدولار:", min_value=100_000, value=5_000_000, step=100_000)
    go = st.button("🔍 جلب وتحليل")

if go:
    inst = okx_inst_id(symbol_in, use_perp=use_perp)
    if not inst:
        st.error("رمز غير صالح. جرّب xrp أو btcusdt.")
    else:
        with st.spinner("جاري جلب الشموع..."):
            df = okx_get_candles(inst, bar=tf, limit=limit)
            oi_snapshot = okx_get_open_interest(inst)
        if df.empty:
            st.error("❌ لم نتمكن من جلب بيانات الشموع. جرّب صيغة أخرى (XRPUSDT أو XRP-USDT) أو تعطيل SWAP.")
        else:
            # chart
            st.plotly_chart(plot_candles(df, f"{inst} — {tf}"), use_container_width=True)

            # metrics row
            st.subheader("📈 ملخص")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("آخر سعر", f"{df['close'].iloc[-1]:,.6f}")
            c2.metric("أعلى خلال الفترة", f"{df['high'].max():,.6f}")
            c3.metric("أدنى خلال الفترة", f"{df['low'].min():,.6f}")
            change5 = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
            c4.metric("تغير آخر 5 شموع", f"{change5:.2f}%")

            # OI analysis card
            st.subheader("📦 Open Interest")
            if oi_snapshot:
                res = analyze_oi(oi_snapshot, df, threshold=threshold)
                # styled card
                st.markdown(f"""
                <div class="alert-card" style="border-left:6px solid {res['color']};">
                  <div style="font-size:1.1rem; margin-bottom:6px;">
                    <b style="font-size:1.3rem;">{res['icon']} &nbsp; {res['msg']}</b>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                # show numeric OI if present
                try:
                    oi_usd = float(oi_snapshot.get("oiUsd") or oi_snapshot.get("oi_usd") or 0)
                    oi_units = float(oi_snapshot.get("oi") or oi_snapshot.get("oiValue") or 0)
                    r1,r2 = st.columns(2)
                    r1.metric("آخر OI (USD)", f"${oi_usd:,.0f}")
                    r2.metric("آخر OI (وحدات)", f"{oi_units:,.0f}")
                except:
                    pass
            else:
                st.warning("لا توجد بيانات OI من OKX لهذا الزوج.")

            # download button
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ تنزيل شموع (CSV)", csv, file_name=f"{symbol_in}_{tf}.csv", mime="text/csv")

            st.markdown("---")
            st.markdown("نصيحة: إن لم تظهر الصورة كخلفية جرب تفريغ الكاش (Ctrl+F5) أو افتح الصفحة في نافذة جديدة. بعض المتصفحات تحتفظ بـ CSS السابق.")
