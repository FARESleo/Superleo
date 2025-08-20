import numpy as np

def analyze(candles, oi_data, ratio_data):
    """تحليل بسيط: إذا OI مرتفع جدًا + Long% عالي = فخ"""
    try:
        if not oi_data or not ratio_data:
            return {"status": "error", "message": "No data found for the selected symbol."}

        last_oi = float(oi_data[-1]["openInterest"])
        avg_oi = np.mean([float(x["openInterest"]) for x in oi_data])
        long_ratio = float(ratio_data[-1]["longShortRatio"])
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if last_oi > avg_oi * 1.2 and long_ratio > 1.5:
        return {"signal": "⚠️ احتمال فخ صانع سوق", "oi": last_oi, "ratio": long_ratio}
    else:
        return {"signal": "✅ حركة طبيعية", "oi": last_oi, "ratio": long_ratio}

