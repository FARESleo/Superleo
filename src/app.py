import streamlit as st
from api_binance import get_candles, get_long_short_ratio
from api_bybit import get_open_interest
from analyzer import analyze
from visualizer import plot_candles
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Crypto Market Tool", layout="wide")

# وظيفة تحويل interval إلى تنسيق Bybit
def to_bybit_interval(interval):
    """تحويل interval إلى تنسيق Bybit (رقم دقائق فقط)."""
    try:
        if interval.endswith('m'):
            return interval.rstrip('m')  # مثال: "15m" -> "15"
        elif interval.endswith('h'):
            num = int(interval.rstrip('h'))
            return str(num * 60)  # مثال: "1h" -> "60"، "4h" -> "240"
        elif interval.endswith('d'):
            num = int(interval.rstrip('d'))
            return str(num * 1440)  # مثال: "1d" -> "1440"
        else:
            return interval
    except ValueError:
        return "15"  # قيمة افتراضية

# وظائف باستخدام التخزين المؤقت
@st.cache_data(ttl=300)  # تخزين لمدة 5 دقائق
def fetch_candles(symbol, interval):
    return get_candles(symbol, interval)

@st.cache_data(ttl=300)
def fetch_ratios(symbol, interval):
    return get_long_short_ratio(symbol, interval)

@st.cache_data(ttl=300)
def fetch_oi(symbol, interval):
    return get_open_interest(symbol, interval)

st.title("📊 Crypto Market Tool")

# إدخال المستخدم
col1, col2 = st.columns(2)
with col1:
    symbol = st.text_input("أدخل رمز العملة (مثال: BTCUSDT)", "BTCUSDT")
with col2:
    interval = st.selectbox("اختر الفاصل الزمني", ["5m", "15m", "30m", "1h", "4h"], index=1)

if st.button("تحليل"):
    with st.spinner("جاري جلب البيانات..."):
        # جلب البيانات
        candles = fetch_candles(symbol, interval)
        ratios = fetch_ratios(symbol, interval)
        bybit_interval = to_bybit_interval(interval)  # تحويل لـ Bybit
        oi = fetch_oi(symbol, bybit_interval)

        # التحقق من وجود أخطاء
        if isinstance(candles, dict) and "error" in candles:
            st.error(candles["error"])
        elif isinstance(ratios, dict) and "error" in ratios:
            st.error(ratios["error"])
        elif isinstance(oi, dict) and "error" in oi:
            st.error(oi["error"])
        else:
            # إجراء التحليل
            signal = analyze(candles, oi["result"]["list"], ratios)

            # التحقق من أخطاء التحليل
            if "status" in signal and signal["status"] == "error":
                st.error(signal["message"])
            else:
                # عرض النتائج
                st.subheader("🔍 نتيجة التحليل")
                st.write(f"**الإشارة**: {signal['signal']}")
                st.write(f"**Open Interest**: {signal['oi']:.2f}")
                st.write(f"**متوسط OI**: {signal['avg_oi']:.2f}")
                st.write(f"**Long/Short Ratio**: {signal['ratio']:.2f}")
                st.write(f"**تغير السعر**: {signal['price_change']:.2f}%")

                # عرض الرسم البياني للشموع
                st.subheader("📈 الرسم البياني")
                candle_fig = plot_candles(candles)
                if isinstance(candle_fig, dict) and "error" in candle_fig:
                    st.error(candle_fig["error"])
                else:
                    st.plotly_chart(candle_fig, use_container_width=True)

                # رسم بياني لـ Open Interest
                st.subheader("📊 Open Interest")
                df_oi = pd.DataFrame(oi["result"]["list"])
                df_oi["timestamp"] = pd.to_datetime(df_oi["timestamp"], unit="ms")
                fig_oi = go.Figure(data=[go.Scatter(
                    x=df_oi["timestamp"],
                    y=df_oi["openInterest"].astype(float),
                    mode="lines",
                    name="Open Interest"
                )])
                fig_oi.update_layout(title="Open Interest Over Time")
                st.plotly_chart(fig_oi, use_container_width=True)
