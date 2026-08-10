"""
stock_features.py
==================
Единая функция построения признаков для LightGBM-модели акций.
Используется и в приложении (app_local.py, инференс на живых котировках),
и в обучающем скрипте (scripts/train_lgbm.py).

Почему это отдельный модуль, а не копия в каждом файле:
раньше build_features() была продублирована в app_local.py и в
scripts/train_lgbm.py, и эти копии успели разойтись — обучающий скрипт в
репозитории строил только 20 признаков без макро-данных (VIX/TNX/DXY), а
реально задеплоенная модель (data/artifacts/lgbm/) обучена на 39 признаках
с макро. Из-за этого расхождения scripts/train_lgbm.py было невозможно
использовать, чтобы честно воспроизвести или переобучить актуальную
модель — он тренировал другую, более слабую модель на другом наборе фич.

Вынос в общий модуль устраняет train/serve skew: инференс и обучение
гарантированно считают одни и те же признаки одним и тем же кодом.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Порядок и состав признаков — как в data/artifacts/lgbm/train_summary.json
FEATURE_COLS = [
    "ret1", "ret2", "ret3", "ret5", "ret10", "ret20", "log_ret1",
    "rsi14", "macd_h", "macd_sign", "atr14", "bb_pos", "bb_width",
    "vol5", "vol10", "vol20", "vol_ratio",
    "ma10_ratio", "ma20_ratio", "ma50_ratio", "ma200_ratio",
    "dist_hi52", "dist_lo52", "hl52_range",
    "vol_rel", "vol_spike",
    "mom10", "mom20", "mom_cross", "ma_cross_20_50", "mom_5_20",
    "day_of_week", "month", "week_of_year",
    "vix_z", "vix_ret", "tnx_z", "tnx_ret", "dxy_z", "dxy_ret",
]

MACRO_TICKERS = {"vix": "^VIX", "tnx": "^TNX", "dxy": "DX-Y.NYB"}


def build_features(df: pd.DataFrame, macro: pd.DataFrame | None = None) -> pd.DataFrame:
    """Строим 39 признаков для LightGBM (без leakage, всё строго backward-looking)."""
    d = df.copy()
    c = d["Close"]
    macro = macro if macro is not None and not macro.empty else pd.DataFrame()

    # Доходности
    for n in [1, 2, 3, 5, 10, 20]:
        d[f"ret{n}"] = c.pct_change(n)
    d["log_ret1"] = np.log(c / c.shift(1))

    # RSI-14
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - 100 / (1 + gain / (loss + 1e-9))

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    d["macd_h"]    = macd - macd.ewm(span=9, adjust=False).mean()
    d["macd_sign"] = (macd > 0).astype(float)

    # ATR
    hl = d["High"] - d["Low"]
    hc = (d["High"] - c.shift()).abs()
    lc = (d["Low"]  - c.shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean() / (c + 1e-9)

    # Bollinger Bands
    ma20  = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    d["bb_pos"]   = (c - ma20) / (2 * std20 + 1e-9)
    d["bb_width"] = (4 * std20) / (ma20 + 1e-9)

    # Волатильность
    d["vol5"]      = c.pct_change().rolling(5).std()
    d["vol10"]     = c.pct_change().rolling(10).std()
    d["vol20"]     = c.pct_change().rolling(20).std()
    d["vol_ratio"] = d["vol5"] / (d["vol20"] + 1e-9)

    # Скользящие средние
    for m in [10, 20, 50, 200]:
        d[f"ma{m}_ratio"] = c / (c.rolling(m, min_periods=m // 2).mean() + 1e-9)

    # 52-week hi/lo
    r52h = c.rolling(252, min_periods=60).max()
    r52l = c.rolling(252, min_periods=60).min()
    d["dist_hi52"]  = (r52h - c) / (r52h + 1e-9)
    d["dist_lo52"]  = (c - r52l) / (r52l + 1e-9)
    d["hl52_range"] = (r52h - r52l) / (r52l + 1e-9)

    # Объём
    v_ma = d["Volume"].rolling(20).mean() if "Volume" in d.columns else pd.Series(1, index=d.index)
    d["vol_rel"]   = (d["Volume"] if "Volume" in d.columns else 1) / (v_ma + 1e-9)
    d["vol_spike"] = (d["vol_rel"] > 2.0).astype(float)
    # vol_ratio = vol10/vol20 (перекрывает более раннее определение выше — так же, как в обучении)
    d["vol_ratio"] = d["vol10"] / (d["vol20"] + 1e-9)

    # Momentum
    d["mom10"]      = c / (c.shift(10) + 1e-9) - 1
    d["mom20"]      = c / (c.shift(20) + 1e-9) - 1
    d["mom_cross"]  = (d["mom10"] > d["mom20"]).astype(float)
    d["ma_cross_20_50"] = (c.rolling(20).mean() > c.rolling(50).mean()).astype(float)
    d["mom_5_20"]   = d["ret5"] / (d["ret20"].abs() + 1e-9)

    # Сезонность
    d["dow"]          = d.index.dayofweek.astype(float)
    d["day_of_week"]  = d["dow"]
    d["month"]        = d.index.month.astype(float)
    d["week_of_year"] = d.index.isocalendar().week.astype(float)

    # Макро (VIX/TNX/DXY) — z-score и 5-дневное изменение, сырые уровни не используем
    if not macro.empty:
        d = d.join(macro.reindex(d.index).ffill(), how="left")
        for col in macro.columns:
            if col in d.columns:
                roll_mean = d[col].rolling(60, min_periods=20).mean()
                roll_std  = d[col].rolling(60, min_periods=20).std()
                d[f"{col}_z"]   = (d[col] - roll_mean) / (roll_std + 1e-9)
                d[f"{col}_ret"] = d[col].pct_change(5)
                d.drop(columns=[col], inplace=True)

    return d.dropna()


def fetch_macro_range(start: str, end: str) -> pd.DataFrame:
    """
    Макро-данные (VIX/TNX/DXY) за явный диапазон дат — вариант для обучения
    (в приложении используется @st.cache_data-обёртка fetch_macro() с
    period="3y", т.к. там нужны только последние данные для инференса).
    """
    import yfinance as yf

    frames = {}
    for name, sym in MACRO_TICKERS.items():
        try:
            df = yf.download(sym, start=start, end=end, auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            frames[name] = df["Close"].rename(name)
        except Exception:
            pass
    return pd.concat(frames.values(), axis=1).ffill() if frames else pd.DataFrame()
