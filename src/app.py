import streamlit as st
from api_binance import get_candles, get_long_short_ratio
from api_bybit import get_open_interest
from analyzer import analyze
from visualizer import plot_candles

st.set_page_config(page_title="Crypto Market Tool", layout="wide")

st.title("📊 Crypto Market Tool")
symbol = st.text_input("أدخل رمز العملة (مثال: BTCUSDT)", "BTCUSDT")

if st.button("تحليل"):
    with st.spinner("جاري جلب البيانات..."):
        candles = get_candles(symbol)
        ratios = get_long_short_ratio(symbol)
        oi = get_open_interest(symbol)

        signal = analyze(candles, oi["result"]["list"], ratios)

        st.subheader("🔍 نتيجة التحليل")
        st.write(signal)

        st.subheader("📈 الرسم البياني")
        st.plotly_chart(plot_candles(candles), use_container_width=True)
