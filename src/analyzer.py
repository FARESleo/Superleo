import numpy as np
import pandas as pd

def analyze(candles, oi_data, ratio_data):
    """تحليل بيانات السعر، OI، وLong/Short Ratio لتحديد إشارة السوق."""
    try:
        # تحويل البيانات إلى DataFrame
        df_candles = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume", "c1", "c2", "c3", "c4", "c5", "c6"])
        df_candles["close"] = df_candles["close"].astype(float)
        df_oi = pd.DataFrame(oi_data)
        df_ratio = pd.DataFrame(ratio_data)

        # حساب OI الأخير ومتوسطه
        last_oi = float(df_oi["openInterest"].iloc[-1])
        avg_oi = np.mean(df_oi["openInterest"].astype(float))

        # حساب Long/Short Ratio
        long_ratio = float(df_ratio["longShortRatio"].iloc[-1])

        # تحليل تغير السعر كنسبة مئوية
        price_change = (df_candles["close"].iloc[-1] - df_candles["close"].iloc[-2]) / df_candles["close"].iloc[-2] * 100

        # منطق التحليل
        signal = "✅ حركة طبيعية"
        if last_oi > avg_oi * 1.2 and long_ratio > 1.5 and price_change > 2:
            signal = "⚠️ احتمال فخ صانع سوق (ارتفاع حاد مع OI مرتفع)"
        elif last_oi < avg_oi * 0.8 and long_ratio < 0.8:
            signal = "⚠️ احتمال انخفاض (OI منخفض وShort مرتفع)"

        return {
            "signal": signal,
            "oi": last_oi,
            "avg_oi": avg_oi,
            "ratio": long_ratio,
            "price_change": price_change
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
