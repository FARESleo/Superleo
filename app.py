
import os
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from urllib.parse import quote_plus

# ---------- config ----------
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT; Win64; x64)"}
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")  # ضع مفتاح CoinGlass هنا لو لديك
st.set_page_config(page_title="Crypto Market Tool", layout="wide")
st.title("📊 Crypto Market Tool — OKX + CoinGlass OI")

# ---------- helpers ----------
def normalize_input_to_okx_inst(symbol_text: str, perp=True) -> str:
    """
    Normalize user input to OKX instId forms:
    - input 'xrp' => 'XRP-USDT-SWAP' (if perp True) or 'XRP-USDT'
    - input 'BTCUSDT' => 'BTC-USDT-SWAP'
    - input 'eth-usdt' => 'ETH-USDT-SWAP'
    """
    if not symbol_text or not isinstance(symbol_text, str):
        return ""
    s = symbol_text.strip().upper().replace(" ", "").replace("_", "").replace("/", "").replace("--", "-")
    # if user provided like BTCUSDT or BTCUSDT.SOMETHING
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}-USDT-SWAP" if perp else f"{base}-USDT"
    # try USD/USDC patterns
    if s.endswith("USDC"):
        base = s[:-4]
        return f"{base}-USDC-SWAP" if perp else f"{base}-USDC"
    # fallback: assume it's base only
    return f"{s}-USDT-SWAP" if perp else f"{s}-USDT"

def to_df_okx(candles):
    """
    convert OKX candle list to DataFrame with columns: ts, open, high, low, close, volume
    OKX candle row format: [ts, o, h, l, c, vol, ...] ts in milliseconds
    """
    if not candles or len(candles) == 0:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume"])
    df = pd.DataFrame(candles)
    df = df.iloc[:, :6]
    df.columns = ["ts","open","high","low","close","volume"]
    # convert types
    try:
        df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="ms")
    except Exception:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.sort_values("ts").reset_index(drop=True)

def okx_get_candles(instId: str, bar: str = "15m", limit: int = 200):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": instId, "bar": bar, "limit": limit}
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(f"OKX error: {j.get('code')} {j.get('msg')}")
    data = j.get("data", [])
    return to_df_okx(data)

def okx_get_open_interest_snapshot(instId: str):
    url = "https://www.okx.com/api/v5/public/open-interest"
    params = {"instId": instId}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=12)
        r.raise_for_status()
        j = r.json()
        if j.get("code") != "0":
            return None
        data = j.get("data", [])
        return data[0] if data else None
    except Exception:
        return None

# ---------- CoinGlass integration (timeseries OI) ----------
def coinglass_get_oi_series(symbol_compact: str, limit: int = 200):
    """
    Try to fetch OI timeseries from CoinGlass (best-effort).
    Accepts symbol like 'BTCUSDT' or 'XRPUSDT'.
    Returns list of dicts: {'timestamp': <int seconds>, 'openInterest': <float>}
    """
    if not symbol_compact:
        return []
    base_endpoints = [
        "https://open-api.coinglass.com/api/pro/v1/futures/openInterest",
        "https://open-api.coinglass.com/api/v1/futures/openInterest",
        "https://open-api.coinglass.com/api/public/v1/openInterest"
    ]
    headers = {}
    if COINGLASS_API_KEY:
        headers["coinglass-api-key"] = COINGLASS_API_KEY
        headers["x-api-key"] = COINGLASS_API_KEY

    for ep in base_endpoints:
        params = {"symbol": symbol_compact, "limit": limit}
        try:
            r = requests.get(ep, params=params, headers=headers or HEADERS, timeout=12)
            if r.status_code in (403, 401):
                # key required or forbidden
                continue
            r.raise_for_status()
            j = r.json()
            # try common shapes
            candidates = []
            if isinstance(j, dict):
                for key in ("data","result","list","items","series"):
                    if key in j and isinstance(j[key], list):
                        candidates = j[key]
                        break
            if not candidates and isinstance(j, list):
                candidates = j
            parsed = []
            for it in candidates:
                if isinstance(it, dict):
                    ts = it.get("timestamp") or it.get("ts") or it.get("time") or it.get("date")
                    oi = it.get("openInterest") or it.get("oi") or it.get("value") or it.get("open_interest")
                    if ts is None or oi is None:
                        continue
                    try:
                        ts_int = int(float(ts))
                        parsed.append({"timestamp": ts_int, "openInterest": float(oi)})
                    except:
                        continue
                elif isinstance(it, (list, tuple)) and len(it) >= 2:
                    try:
                        ts_int = int(float(it[0]))
                        parsed.append({"timestamp": ts_int, "openInterest": float(it[1])})
                    except:
                        continue
            if parsed:
                parsed = sorted(parsed, key=lambda x: x["timestamp"])
                return parsed
        except Exception:
            continue
    return []

# ---------- plotting ----------
def plot_candles(df, title="Candles"):
    fig = go.Figure(data=[go.Candlestick(x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"])])
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, template="plotly_dark", height=540)
    return fig

def plot_oi_series(oi_list):
    if not oi_list:
        return None
    oi_df = pd.DataFrame(oi_list)
    oi_df["ts"] = pd.to_datetime(oi_df["timestamp"].astype(int), unit="s")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=oi_df["ts"], y=oi_df["openInterest"], mode="lines", name="Open Interest"))
    fig.update_layout(title="Open Interest (CoinGlass)", template="plotly_dark", height=300)
    return fig, oi_df

# ---------- trap detection ----------
def detect_market_maker_trap(df: pd.DataFrame, oi_series=None, oi_snapshot=None):
    """
    Returns human-friendly signals about possible traps/squeezes.
    - df: candles dataframe (must have ts, open, high, low, close, volume)
    - oi_series: list/df of historical OI points (preferred)
    - oi_snapshot: single dict from OKX snapshot (used if no series)
    """
    if df is None or df.empty or len(df) < 3:
        return "❓ البيانات قليلة لتقييم الفخاخ."

    # last two candles
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    # candle geometry
    rng = (last["high"] - last["low"]) if (last["high"] - last["low"]) != 0 else 1e-9
    body = abs(last["close"] - last["open"])
    up_wick = last["high"] - max(last["open"], last["close"])
    low_wick = min(last["open"], last["close"]) - last["low"]

    vol_ma = df["volume"].rolling(20).mean().iloc[-1] if len(df) >= 20 else df["volume"].mean()
    vol_spike = last["volume"] > (vol_ma * 1.5 if pd.notna(vol_ma) else last["volume"])

    signals = []

    # OI context: prefer series
    oi_last = None
    oi_avg = None
    if oi_series:
        try:
            oidf = pd.DataFrame(oi_series)
            oidf["openInterest"] = pd.to_numeric(oidf["openInterest"], errors="coerce").fillna(0.0)
            oi_last = float(oidf["openInterest"].iloc[-1])
            oi_avg = float(oidf["openInterest"].rolling(window=min(len(oidf), 20)).mean().iloc[-1])
        except Exception:
            oi_last = None
            oi_avg = None
    elif oi_snapshot:
        # try to find number in snapshot (oi, openInterest, oiValue)
        for key in ("oi","openInterest","open_interest","openInterestValue","value"):
            if key in oi_snapshot:
                try:
                    oi_last = float(oi_snapshot.get(key) or oi_snapshot.get(key, 0))
                except:
                    oi_last = None
                break

    # 1) Divergence price vs OI
    if oi_last is not None and oi_avg is not None:
        # price up + OI up strong => possible trap (many entering longs)
        if last["close"] > prev["close"] and oi_last > (oi_avg * 1.15):
            signals.append("⚠️ احتمال فخ شراء: السعر صاعد وOpen Interest يرتفع بقوة.")
        # price down + OI up => possible trap بيع (short pressure)
        if last["close"] < prev["close"] and oi_last > (oi_avg * 1.15):
            signals.append("⚠️ احتمال فخ بيع: السعر هابط وOpen Interest يرتفع.")

    # 2) sudden OI drop with price move -> possible squeeze
    if oi_last is not None and oi_avg is not None:
        if oi_last < (oi_avg * 0.8) and last["close"] > prev["close"]:
            signals.append("🔥 احتمال Short Squeeze: OI انخفض مع ارتداد سعري صاعد.")
        if oi_last < (oi_avg * 0.8) and last["close"] < prev["close"]:
            signals.append("🔥 احتمال Long Squeeze: OI انخفض مع هبوط سعري.")

    # 3) wick + volume patterns
    if up_wick / rng > 0.6 and vol_spike:
        signals.append("📉 ذيل علوي طويل + فوليوم مرتفع → تصريف محتمل عند القمة.")
    if low_wick / rng > 0.6 and vol_spike:
        signals.append("📈 ذيل سفلي طويل + فوليوم مرتفع → امتصاص بيع محتمل عند القاع.")
    if body / rng < 0.25 and vol_spike:
        signals.append("⚠️ دوجي/تذبذب مع فوليوم عالي → ترقّب كسر/انطلاقة.")

    return "\n".join(signals) if signals else "✅ لا توجد إشارات واضحة للفخاخ الآن."

# ---------- UI ----------
st.markdown("أدخل رمز العملة (مثال: `xrp` أو `BTCUSDT`). النظام سيحاول اكتشاف الزوج المناسب (USDT) تلقائيًا.")

col1, col2, col3 = st.columns([2,1,1])
with col1:
    user_input = st.text_input("رمز العملة:", "xrp")
with col2:
    bar = st.selectbox("الإطار الزمني:", ["5m","15m","30m","1h","4h","1d"], index=1)
with col3:
    limit = st.slider("عدد الشموع:", 50, 300, 200, 10)

use_perp = st.checkbox("عرض عقود دائمة (SWAP) إن وُجد (OKX Perp)", value=True)

if st.button("جلب وتحليل"):
    symbol_compact = (user_input or "").strip()
    if not symbol_compact:
        st.error("رمز غير صالح. اكتب مثلاً: xrp أو btcusdt")
    else:
        instId = normalize_input_to_okx_inst(symbol_compact, perp=use_perp)
        st.info(f"جاري جلب الشموع للرمز: `{instId}` — إن تعذر حاول تغيير الشكل أو تعطيل SWAP.")
        # get candles
        try:
            df = okx_get_candles(instId, bar=bar, limit=limit)
        except Exception as e:
            st.error(f"خطأ عند جلب الشموع من OKX: {e}")
            df = pd.DataFrame()

        # try coinGlass OI timeseries first
        oi_series = []
        if COINGLASS_API_KEY:
            try:
                oi_series = coinglass_get_oi_series(symbol_compact.upper(), limit=limit)
            except Exception:
                oi_series = []
        else:
            # try without key as well (best-effort)
            try:
                oi_series = coinglass_get_oi_series(symbol_compact.upper(), limit=limit)
            except Exception:
                oi_series = []

        # okx snapshot
        oi_snapshot = None
        try:
            oi_snapshot = okx_get_open_interest_snapshot(instId)
        except Exception:
            oi_snapshot = None

        # display
        if df is None or df.empty:
            st.error("لم نتمكن من جلب شموع من OKX. جرّب تغيّر شكل الرمز أو تعطيل SWAP.")
        else:
            st.subheader("📈 الشموع")
            st.plotly_chart(plot_candles(df, f"{instId} — {bar}"), use_container_width=True)

            st.subheader("🔍 إشارة سريعة من الشموع/الفوليوم")
            st.info(detect_market_maker_trap(df, oi_series=oi_series if oi_series else None, oi_snapshot=oi_snapshot))

            # show OI results
            st.subheader("📦 Open Interest")
            if oi_series:
                fig_pair = plot_oi_series(oi_series)
                if fig_pair:
                    fig_oi, oi_df = fig_pair
                    st.plotly_chart(fig_oi, use_container_width=True)
                    last_oi = oi_df["openInterest"].iloc[-1]
                    avg_oi = oi_df["openInterest"].rolling(window=min(len(oi_df), 20)).mean().iloc[-1]
                    st.metric("آخر OI (CoinGlass)", f"{last_oi:,.0f}", delta=f"{(last_oi-avg_oi)/avg_oi*100:.2f}% vs 20MA")
            else:
                if oi_snapshot:
                    st.json(oi_snapshot)
                    # try to estimate numeric OI if available
                    keys = ["oi","openInterest","open_interest","openInterestValue","value"]
                    found = None
                    for k in keys:
                        if k in oi_snapshot:
                            try:
                                found = float(oi_snapshot.get(k))
                                break
                            except:
                                continue
                    if found is not None:
                        st.metric("آخر OI (OKX snapshot)", f"{found:,.0f}")
                else:
                    st.write("لا توجد بيانات OI متاحة من CoinGlass أو OKX لهذا الرمز.")

        st.markdown("---")
        st.markdown("**نصائح:**\n- إذا لم تظهر بيانات: جرّب كتابة الرمز كاملاً مثل `XRPUSDT` أو `XRP-USDT`.\n- إن كانت قيود جغرافية تمنع الوصول: شغّل التطبيق عبر سيرفر خارجي أو Streamlit Cloud.\n- لإضافة OI تاريخي أفضل سجّل في CoinGlass وخذ API key وضعه في متغير البيئة `COINGLASS_API_KEY`.")
