import pandas as pd
import plotly.graph_objects as go

def plot_candles(candles):
    df = pd.DataFrame(candles, columns=[
        "time","open","high","low","close","volume","c1","c2","c3","c4","c5","c6"
    ])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)

    fig = go.Figure(data=[go.Candlestick(
        x=df["time"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"]
    )])
    fig.update_layout(title="Candlestick Chart", xaxis_rangeslider_visible=False)
    return fig
