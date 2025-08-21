import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="أداة سوق العملات الرقمية", layout="wide")

# ===================== Helpers =====================
# ... (الدوال المساعدة: err_msg, to_df_okx, plot_candles)
# ...

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
# ... (الدوال الخاصة بواجهة OKX API)
# ...

# ===================== OI Analysis =====================
def analyze_oi(oi, df):
    if not oi or df.empty or len(df) < 5:
        return "❌ لا توجد بيانات كافية للتحليل."

    try:
        oi_val = float(oi["oiUsd"])
    except (ValueError, KeyError):
        return "⚠️ لم أتمكن من قراءة OI بشكل صحيح."

    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-5]
    price_change = ((last_close - prev_close) / prev_close) * 100

    if price_change > 1:
        if oi_val > 5000000:
            return "📈 ارتفاع السعر مع OI كبير يؤكد قوة الاتجاه الصعودي."
        else:
            return "⚠️ ارتفاع السعر مع OI منخفض. قد يكون حركة مؤقتة."
    elif price_change < -1:
        if oi_val > 5000000:
            return "📉 انخفاض السعر مع OI كبير يؤكد قوة الاتجاه الهبوطي."
        else:
            return "⚠️ انخفاض السعر مع OI منخفض. قد يكون تصفية صفقات لا أكثر."
    elif abs(price_change) < 0.5:
        if oi_val > 5000000:
             return "⚖️ السعر شبه ثابت مع OI كبير. يرجى مراقبة احتمال تجميع/تصريف."
        else:
            return "✅ حركة عادية بلا إشارات قوية."
    else:
        return "✅ حركة عادية بلا إشارات قوية."

# ===================== UI =====================
st.title("📊 أداة سوق العملات الرقمية — الشموع + Open Interest")

with st.sidebar:
    st.header("خيارات التحليل")
    symbol_in = st.text_input("أدخل رمز العملة:", "xrp")
    tf = st.selectbox("الإطار الزمني", ["15m","5m","30m","1h","4h","1d"], index=0)
    limit = st.slider("عدد الشموع", 50, 500, 200, 10)
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
                col1, col2, col3 = st.columns(3)
                col1.metric("آخر سعر", f"{df['close'].iloc[-1]:,.4f}")
                col2.metric("أعلى سعر (أيام)", f"{df['high'].max():,.4f}")
                col3.metric("أدنى سعر (أيام)", f"{df['low'].min():,.4f}")
                
                # قسم تحليل Open Interest
                st.subheader("📦 Open Interest (OKX)")
                oi = okx_get_open_interest(instId)
                if oi:
                    col_oi_val, col_oi_msg = st.columns([1, 2])
                    col_oi_val.metric("قيمة OI بالدولار", f"{float(oi['oiUsd']):,.0f}")
                    col_oi_msg.info(analyze_oi(oi, df))
                    st.caption(f"آخر تحديث: {pd.to_datetime(oi['ts'], unit='ms')}")
                else:
                    st.warning("لا توجد بيانات OI متاحة لهذه الأداة.")

        except requests.exceptions.HTTPError as e:
            st.error(f"❌ خطأ في الاتصال بواجهة API: {e}. يرجى التحقق من الرمز.")
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")

