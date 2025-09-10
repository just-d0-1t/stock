
import pandas as pd

# 假设 df['close'] 是收盘价
ema_short = df['close'].ewm(span=12, adjust=False).mean()
ema_long  = df['close'].ewm(span=26, adjust=False).mean()
dif = ema_short - ema_long
dea = dif.ewm(span=9, adjust=False).mean()
macd = 2 * (dif - dea)

