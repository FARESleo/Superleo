import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def plot_candles(candles):
    """إنشاء رسم بياني للشموع مع الحجم."""
    try:
        df = pd.DataFrame(candles, columns=[
            "time", "open", "high", "low", "close", "volume", "c1", "c2", "c3", "c4", "c5", "c6"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)

        # إنشاء رسم بياني مع شموع وحجم
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.1, subplot_titles=("Candlestick", "Volume"),
                            row_heights=[0.7, 0.3])

        # الشموع
        fig.add_trace(go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Candlesticks"
        ), row=1, col=1)

        # الحجم
        fig.add_trace(go.Bar(
            x=df["time"],
            y=df["volume"],
            name="Volume",
            marker_color="blue"
        ), row=2, col=1)

        fig.update_layout(
            title="Candlestick Chart with Volume",
            xaxis_rangeslider_visible=False,
            showlegend=True,
            height=600
        )
        return fig
    except Exception as e:
        return {"error": f"Failed to plot candles: {str(e)}"}
