import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timezone
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="📊 أداة سوق العملات الرقمية", layout="wide")

# إضافة تحديث تلقائي كل 15 ثانية
st_autorefresh(interval=15 * 1000, key="datarefresh")

# باقي الكود الخاص بـ CSS و Helpers كما هو...

@st.cache_data(ttl=60)  # تخزين مؤقت لمدة 60 ثانية
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

# باقي الكود كما هو مع إزالة زر "جلب وتحليل البيانات" وجعل العملية تلقائية
if st.session_state.symbol:
    instId = okx_inst_id(st.session_state.symbol, use_perp=st.session_state.use_perp)
    with st.spinner('⏳ جارٍ جلب البيانات...'):
        try:
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
