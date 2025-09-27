# decide.py
import argparse
import pandas as pd
from joblib import load
from utils import load_config, get_um_client, compute_features, FEATURES
from datetime import datetime, timezone
import numpy as np

def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def floor_minute_ms(ms: int) -> int:
    return (ms // 60000) * 60000

def last_closed_kline_end_ms() -> int:
    return floor_minute_ms(now_ms()) - 1

def fetch_last_window_klines(client, symbol: str, interval: str, window: int) -> pd.DataFrame:
    end_ms = last_closed_kline_end_ms()
    data = client.klines(symbol=symbol, interval=interval, endTime=end_ms, limit=window)
    cols = ["open_time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"]
    df = pd.DataFrame(data, columns=cols)
    if df.empty:
        raise RuntimeError("No klines returned.")
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open","high","low","close","volume","tbbav"]:
        if c in df.columns:
            df[c] = df[c].astype(float)
    df.rename(columns={"tbbav": "taker_buy_base"}, inplace=True)
    return df[["time","open","high","low","close","volume","taker_buy_base"]].sort_values("time")

def decide_action(min_conf: float | None = None, window: int | None = None) -> dict:
    """
    호출 시점의 최신 분봉 데이터를 Testnet/Mainnet에서 가져와서
    BUY/SELL/HOLD 신호와 확률을 리턴.
    """
    cfg = load_config()
    client = get_um_client(cfg.use_testnet)
    win = window or int(getattr(cfg, "decision_window", 120))

    raw = fetch_last_window_klines(client, cfg.symbol, cfg.interval, win)
    feat = compute_features(raw).dropna(subset=FEATURES)
    if feat.empty:
        raise RuntimeError("Not enough data after feature engineering.")

    x = feat.iloc[-1:][FEATURES].values
    model = load(cfg.model_path)
    proba = model.predict_proba(x)[0]  # [SELL, HOLD, BUY]
    p_sell, p_hold, p_buy = proba
    use_conf = min_conf if min_conf is not None else cfg.min_conf

    if p_buy >= max(proba) and p_buy >= use_conf:
        action, conf = "BUY", float(p_buy)
    elif p_sell >= max(proba) and p_sell >= use_conf:
        action, conf = "SELL", float(p_sell)
    else:
        action, conf = "HOLD", float(max(proba))

    return {
        "time": str(feat["time"].iloc[-1]),
        "close": float(raw["close"].iloc[-1]),
        "action": action,
        "confidence": round(conf, 4),
        "proba": [round(float(p), 4) for p in proba],
        "window_used": win
    }

# CLI 실행도 가능하게 유지
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-conf", type=float, default=None)
    ap.add_argument("--window", type=int, default=None)
    args = ap.parse_args()
    out = decide_action(min_conf=0.6, window=120)
    print(out)
