
import os
import time
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from urllib.parse import quote_plus

# ---------- Configuration ----------
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT; Win64; x64)"}
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")  # ضع المفتاح في متغير بيئة إذا كان لديك
st.set_page_config(page_title="Crypto Market Tool", layout="wide")
st.title("📊 Crypto Market Tool — OKX + CoinGlass OI")

# ---------- Helper functions ----------
def normalize_symbol(text: str) -> str:
    """
    Normalize user input to a compact uppercase form like BTCUSDT.
    Accepts: btc-usdt, btc/usdt, btc_usdt, BTCUSDT, btcusd etc.
    """
    if not text or not isinstance(text, str):
        return ""
    s = text.strip().upper()
    for ch in ["-", "/", "_", " "]:
        s = s.replace(ch, "")
    # If user typed BTCUSD (no T) try to convert to USDT by default
    if s.endswith("USD") and not s.endswith("USDT"):
        # avoid converting if token actually uses USD pair; user can change
        s = s + "T"  # BTCUSD -> BTCUSDT
    return s

def okx_inst_id_from_symbol(symbol_compact: str, perp=True) -> str:
    """Map BTCUSDT -> BTC-USDT-SWAP (perp) or BTC-USDT (spot)"""
    s = symbol_compact
    # common: endswith USDT, USDC, USD, BTC etc.
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}-USDT-SWAP" if perp else f"{base}-USDT"
    if s.endswith("USDC"):
        base = s[:-4]
        return f"{base}-USDC-SWAP" if perp else f"{base}-USDC"
    if s.endswith("USD"):
        base = s[:-3]
        return f"{base}-USD-SWAP" if perp else f"{base}-USD"
    # fallback: try to insert hyphen before suffix
    # if can't, return original (hoping OKX accepts)
    return s

def to_df_okx(candles):
    """
    OKX returns candles where each item is:
    [ts, open, high, low, close, volume, ...]
    ts usually milliseconds
    """
    if not candles or len(candles) == 0:
        return pd.DataFrame()
    # build df from list of lists
    # columns may vary, take first 6 values
    df = pd.DataFrame(candles)
    # keep first 6 columns
    df = df.iloc[:, :6]
    df.columns = ["ts", "open", "high", "low", "close", "volume"]
    # types
    try:
        df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="ms")
    except Exception:
        # fallback if already datetime-like
        df["ts"] = pd.to_datetime(df["ts"])
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.sort_values("ts").reset_index(drop=True)

# ---------- OKX API functions ----------
def okx_get_candles(instId: str, bar: str = "15m", limit: int = 200):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": instId, "bar": bar, "limit": limit}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        j = r.json()
        if j.get("code") != "0":
            # empty data or error
            return pd.DataFrame()
        data = j.get("data", [])
        return to_df_okx(data)
    except requests.HTTPError as e:
        # bubble up message
        raise RuntimeError(f"OKX HTTP error: {e}")
    except Exception as e:
        raise RuntimeError(f"OKX error: {e}")

def okx_get_open_interest_snapshot(instId: str):
    """
    OKX offers a public open-interest snapshot endpoint (current snapshot).
    This returns a single object (not a timeseries).
    """
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

# ---------- CoinGlass integration ----------
def coinglass_get_open_interest_series(symbol_compact: str, limit: int = 200):
    """
    Best-effort attempt to fetch OI timeseries from CoinGlass open API.
    CoinGlass APIs differ by plan; the user should supply COINGLASS_API_KEY in env var if required.
    This function tries a couple of likely endpoints and parses common response shapes.
    """
    if not symbol_compact:
        return []
    endpoints = [
        f"https://open-api.coinglass.com/api/pro/v1/futures/openInterest?symbol={quote_plus(symbol_compact)}&limit={limit}",
        f"https://open-api.coinglass.com/api/pro/v1/future/openInterest?symbol={quote_plus(symbol_compact)}&limit={limit}",
        f"https://open-api.coinglass.com/api/v1/futures/openInterest?symbol={quote_plus(symbol_compact)}&limit={limit}",
        f"https://open-api.coinglass.com/api/public/v1/openInterest?symbol={quote_plus(symbol_compact)}&limit={limit}",
    ]
    headers = {}
    if COINGLASS_API_KEY:
        # try common header names
        headers["coinglass-api-key"] = COINGLASS_API_KEY
        headers["x-api-key"] = COINGLASS_API_KEY

    for url in endpoints:
        try:
            r = requests.get(url, headers=headers or HEADERS, timeout=12)
            if r.status_code == 403:
                # forbidden, try next
                continue
            r.raise_for_status()
            j = r.json()
            # Try to find list of points in common keys
            candidates = []
            if isinstance(j, dict):
                for key in ("data", "result", "list", "items", "series"):
                    if key in j and isinstance(j[key], (list, dict)):
                        candidates = j[key] if isinstance(j[key], list) else (j[key].get("list") or [])
                        break
            if not candidates and isinstance(j, list):
                candidates = j
            # parse candidates into a list of dicts with timestamp & oi
            parsed = []
            for it in candidates:
                # several shapes possible: {timestamp:..., openInterest:...} or [ts, oi]
                if isinstance(it, dict):
                    ts = it.get("timestamp") or it.get("ts") or it.get("time") or it.get("date")
                    oi_val = it.get("openInterest") or it.get("oi") or it.get("open_interest") or it.get("value")
                    if ts is None or oi_val is None:
                        # try nested structures
                        continue
                    try:
                        ts_int = int(ts)
                    except:
                        try:
                            ts_int = int(float(ts))
                        except:
                            continue
                    parsed.append({"timestamp": ts_int, "openInterest": float(oi_val)})
                elif isinstance(it, (list, tuple)) and len(it) >= 2:
                    # assume [ts, oi, ...]
                    try:
                        ts_int = int(it[0])
                        parsed.append({"timestamp": ts_int, "openInterest": float(it[1])})
                    except:
                        continue
            if parsed:
                # sort by timestamp ascending
                parsed = sorted(parsed, key=lambda x: x["timestamp"])
                return parsed
        except Exception:
            continue
    # nothing found
    return []

# ---------- Simple candle-based quick signals ----------
def quick_candle_signal_df(df: pd.DataFrame) -> str:
    """Return a short human-friendly signal derived from last candle and volume context."""
    try:
        if df.empty or len(df) < 10:
            return "بيانات الشموع قليلة للتقييم."
        last = df.iloc[-1]
        rng = last["high"] - last["low"]
        if rng <= 0:
            return "نطاق الشمعة صفري."
        body = abs(last["close"] - last["open"])
        up_w = last["high"] - max(last["open"], last["close"])
        lo_w = min(last["open"], last["close"]) - last["low"]
        vol_ma = df["volume"].rolling(20).mean().iloc[-1] if len(df) >= 20 else df["volume"].mean()
        vol_spike = last["volume"] > (vol_ma * 1.5 if pd.notna(vol_ma) else last["volume"])
        if up_w / rng > 0.6 and last["close"] < last["open"] and vol_spike:
            return "📉 رفض سعري بظل علوي طويل مع فوليوم مرتفع → احتمال هبوط قصير."
        if lo_w / rng > 0.6 and last["close"] > last["open"] and vol_spike:
            return "📈 امتصاص بيع بظل سفلي طويل مع فوليوم مرتفع → احتمال ارتداد صعودي."
        if body / rng < 0.25 and vol_spike:
            return "⚠️ دوجي/تذبذب مع فوليوم عالي → ترقّب انطلاقة أو كسر قريب."
        return "✅ لا إشارة قوية من الشمعة الأخيرة."
    except Exception as e:
        return f"تحليل الشموع: خطأ داخلي ({e})"

# ---------- UI & Flow ----------
st.markdown("أدخل رمز العملة (مثال: `BTCUSDT` أو `btc-usdt`) ثم اختَر المزود واطلب التحليل.")

col1, col2 = st.columns([2, 1])
with col1:
    user_input = st.text_input("رمز العملة:", "BTCUSDT")
with col2:
    use_perp_okx = st.checkbox("OKX Perp (SWAP)", value=True)
provider = st.selectbox("مزود البيانات (افتراضي OKX):", ["OKX (موصى به)", "CoinGlass OI (إن وُجد مفتاح)", "OKX + CoinGlass OI"], index=2)
bar = st.selectbox("الإطار الزمني للشموع:", ["5m", "15m", "30m", "1h", "4h", "1d"], index=1)
limit = st.slider("عدد الشموع:", 50, 500, 200, 10)

if st.button("جلب البيانات وعرض التحليل"):
    sym = normalize_symbol(user_input)
    if not sym:
        st.error("رمز غير صالح. جرّب مثالًا مثل BTCUSDT أو ETHUSDT.")
    else:
        st.info(f"تمت معالجة الرمز → `{sym}`. يرجى الانتظار قليلاً...")
        # build OKX instId and attempt to fetch candles
        inst_okx = okx_inst_id_from_symbol(sym, perp=use_perp_okx)
        df = None
        okx_failed = False
        try:
            df = okx_get_candles(inst_okx, bar=bar, limit=limit)
            if df.empty:
                # try fallback forms (spot, no SWAP)
                alt1 = inst_okx.replace("-SWAP", "")
                df = okx_get_candles(alt1, bar=bar, limit=limit)
            if df.empty:
                okx_failed = True
        except Exception as e:
            okx_failed = True
            st.warning(f"مشكلة عند جلب الشموع من OKX: {e}")

        # CoinGlass OI
        coinglass_series = []
        cg_failed = False
        if provider.startswith("CoinGlass") or provider.endswith("CoinGlass OI") or provider.startswith("OKX + CoinGlass OI"):
            # CoinGlass expects symbol in many cases as base+quote (BTCUSDT)
            try:
                coinglass_series = coinglass_get_open_interest_series(sym, limit=limit)
                if not coinglass_series:
                    cg_failed = True
            except Exception as e:
                cg_failed = True

        # OKX OI snapshot (fallback)
        okx_oi_snapshot = None
        if okx_failed is False:
            try:
                okx_oi_snapshot = okx_get_open_interest_snapshot(inst_okx)
            except Exception:
                okx_oi_snapshot = None

        # Display results:
        if df is None or df.empty:
            st.error("لم نتمكن من جلب شموع صالحة من OKX لأي من صيغ الرمز المحاولَة.")
            st.caption("حاول تغيير شكل الرمز (مثال: BTCUSDT, BTC-USDT) أو شغّل التطبيق من سيرفر/VPN إذا كانت هناك قيود جغرافية.")
        else:
            st.subheader("📈 الشموع (OKX)")
            st.plotly_chart(plot_candles(df, f"OKX / {inst_okx} — {bar}"), use_container_width=True)
            st.subheader("🔍 إشارة سريعة من الشموع")
            st.info(quick_candle_signal_df(df))

            # show CoinGlass OI if available
            if coinglass_series:
                st.subheader("📦 Open Interest (CoinGlass timeseries)")
                # build df
                try:
                    oi_df = pd.DataFrame(coinglass_series)
                    oi_df["ts"] = pd.to_datetime(oi_df["timestamp"].astype(int), unit="s")
                    oi_df["openInterest"] = oi_df["openInterest"].astype(float)
                    fig_oi = go.Figure()
                    fig_oi.add_trace(go.Scatter(x=oi_df["ts"], y=oi_df["openInterest"], mode="lines+markers", name="OI"))
                    fig_oi.update_layout(title="CoinGlass Open Interest (timeseries)", template="plotly_dark", height=300)
                    st.plotly_chart(fig_oi, use_container_width=True)
                    # quick OI signal
                    last_oi = oi_df["openInterest"].iloc[-1]
                    avg_oi = oi_df["openInterest"].mean()
                    if last_oi > avg_oi * 1.2:
                        st.warning(f"⚠️ مستوى OI مرتفع مقارنة بالمعدل ({last_oi:.0f} vs avg {avg_oi:.0f}) → قد يكون دخول سيولة كبير أو فخ.")
                    else:
                        st.success(f"✅ OI طبيعي نسبياً ({last_oi:.0f} vs avg {avg_oi:.0f})")
                except Exception as e:
                    st.error(f"خطأ في عرض بيانات CoinGlass OI: {e}")
            else:
                st.info("لا توجد بيانات CoinGlass OI متاحة تلقائياً.")
                if COINGLASS_API_KEY:
                    st.caption("لقد ضَعْت مفتاح CoinGlass، لكن API لم يُرجع بيانات صالحة. تأكد من صحة الرمز أو صلاحية المفتاح.")
                else:
                    st.caption("للحصول على OI تاريخي استخدم مفتاح CoinGlass: ضع COINGLASS_API_KEY كمُتغيّر بيئة.")

            # OKX snapshot OI (if present)
            st.subheader("📦 Open Interest (OKX snapshot)")
            if okx_oi_snapshot:
                st.json(okx_oi_snapshot)
                # try present a quick metric if possible
                try:
                    oi_val = float(okx_oi_snapshot.get("oi") or okx_oi_snapshot.get("openInterest") or okx_oi_snapshot.get("open_interest") or 0)
                    st.metric("آخر OI (OKX snapshot)", f"{oi_val:,.0f}")
                except Exception:
                    pass
            else:
                st.write("لا توجد لقطة OI من OKX حالياً (أو لا يدعم هذا الزوج).")

        # extra tips
        st.markdown("---")
        st.markdown("**نصائح:** إذا كانت نتائج الشموع أو OI غير متاحة:\n- جرّب تغيير شكل الرمز (مثال: استخدم `ETHUSDT` أو `ETH-USDT`).\n- إذا كنت داخل بلد عليه حظر، شغّل التطبيق على سيرفر خارجي أو استخدم Streamlit Cloud.\n- لإضافة OI تاريخي استخدم CoinGlass API: ضع مفتاحك في متغيّر البيئة `COINGLASS_API_KEY`.")
