import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np
import yaml
from dotenv import load_dotenv
from binance.um_futures import UMFutures

load_dotenv()

@dataclass
class Config:
    symbol: str
    interval: str
    start_date: str
    horizon: int
    theta: float
    model_path: str
    data_path: str
    train_path: str
    train_window_bars: int
    min_conf: float
    taker_fee_each: float
    slippage: float
    use_testnet: bool

def load_config(path: str = "config.yaml") -> Config:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    use_testnet = os.getenv("USE_TESTNET", "true").lower() == "true"
    return Config(
        symbol=cfg["symbol"],
        interval=cfg["interval"],
        start_date=cfg["start_date"],
        horizon=int(cfg["horizon"]),
        theta=float(cfg["theta"]),
        model_path=cfg["model_path"],
        data_path=cfg["data_path"],
        train_path=cfg["train_path"],
        train_window_bars=int(cfg["train_window_bars"]),
        min_conf=float(cfg["min_conf"]),
        taker_fee_each=float(cfg["taker_fee_each"]),
        slippage=float(cfg["slippage"]),
        use_testnet=use_testnet
    )

def get_um_client(use_testnet: bool) -> UMFutures:
    base_url = "https://testnet.binancefuture.com" if use_testnet else "https://fapi.binance.com"
    key = os.getenv("BINANCE_API_KEY", "")
    sec = os.getenv("BINANCE_API_SECRET", "")
    return UMFutures(key=key, secret=sec, base_url=base_url)

def utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def to_utc_ts(dt) -> int:
    """pandas.Timestamp or datetime -> ms since epoch (UTC)"""
    if isinstance(dt, pd.Timestamp):
        if dt.tzinfo is None:
            dt = dt.tz_localize("UTC")
        else:
            dt = dt.tz_convert("UTC")
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def ensure_dirs():
    os.makedirs("data", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("exp", exist_ok=True)

# ---------- Feature helpers ----------
def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: df with columns: time, open, high, low, close, volume, taker_buy_base
    Output: adds feature columns
    """
    df = df.sort_values("time").copy()
    df.set_index("time", inplace=True)

    # 가격 기반
    log_close = np.log(df["close"])
    df["ret_1"]  = log_close.diff(1)
    df["ret_3"]  = log_close.diff(3)
    df["ret_5"]  = log_close.diff(5)
    df["vol_10"] = df["ret_1"].rolling(10).std()
    df["vol_30"] = df["ret_1"].rolling(30).std()

    # 모멘텀/오실레이터
    import ta
    df["rsi_7"]  = ta.momentum.RSIIndicator(df["close"], window=7).rsi()
    st = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"], window=7, smooth_window=3)
    df["stoch"]  = st.stoch()
    df["cci_10"] = ta.trend.CCIIndicator(df["high"], df["low"], df["close"], window=10).cci()

    # 거래량 기반
    df["log_vol"] = np.log(df["volume"] + 1.0)
    df["vol_ratio_1_10"] = df["volume"] / (df["volume"].rolling(10).mean() + 1e-12)
    df["vol_zscore_10"] = (df["volume"] - df["volume"].rolling(10).mean()) / (df["volume"].rolling(10).std() + 1e-12)

    # 전체 거래 중 BUY/SELL 비율 (taker buy base volume 활용)
    # Binance kline: "taker buy base asset volume" 제공 → buy_ratio = tbbav / volume
    if "taker_buy_base" in df.columns:
        buy_ratio = (df["taker_buy_base"] / (df["volume"] + 1e-12)).clip(0, 1)
        df["buy_ratio"] = buy_ratio
        df["sell_ratio"] = 1.0 - buy_ratio
        # 비율의 최근 이상치
        df["buy_ratio_z10"] = (buy_ratio - buy_ratio.rolling(10).mean()) / (buy_ratio.rolling(10).std() + 1e-12)
    else:
        # 없으면 0.5로 중립 채움
        df["buy_ratio"] = 0.5
        df["sell_ratio"] = 0.5
        df["buy_ratio_z10"] = 0.0

    df.reset_index(inplace=True)
    return df

def make_labels(df: pd.DataFrame, horizon: int, theta: float) -> pd.DataFrame:
    df = df.sort_values("time").copy()
    df.set_index("time", inplace=True)
    future_ret = np.log(df["close"]).shift(-horizon) - np.log(df["close"])
    label = np.zeros(len(df), dtype=int)
    label[future_ret >  theta] =  1
    label[future_ret < -theta] = -1
    df["label"] = label
    df.reset_index(inplace=True)
    return df

FEATURES = [
    # 가격/변동성
    "ret_1","ret_3","ret_5","vol_10","vol_30",
    # 모멘텀
    "rsi_7","stoch","cci_10",
    # 거래량
    "log_vol","vol_ratio_1_10","vol_zscore_10",
    # 매수/매도 비율
    "buy_ratio","sell_ratio","buy_ratio_z10"
]
