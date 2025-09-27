import argparse
import pandas as pd
import time
from utils import load_config, get_um_client, ensure_dirs, utc_now_ms, to_utc_ts

def fetch_range(client, symbol, interval, start_ms, end_ms, limit=1500) -> pd.DataFrame:
    rows=[]
    cur = start_ms
    while cur < end_ms:
        data = client.klines(symbol=symbol, interval=interval, startTime=cur, endTime=end_ms, limit=limit)
        if not data:
            break
        rows += data
        cur = data[-1][0] + 1
        time.sleep(0.15)
    cols = ["open_time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open","high","low","close","volume","tbbav"]:
        if c in df.columns:
            df[c] = df[c].astype(float)
    # tbbav = taker buy base asset volume
    df.rename(columns={"tbbav":"taker_buy_base"}, inplace=True)
    return df[["time","open","high","low","close","volume","taker_buy_base"]].sort_values("time")

def main(mode: str):
    cfg = load_config()
    ensure_dirs()
    client = get_um_client(cfg.use_testnet)

    path = cfg.data_path
    if mode == "backfill":
        start_ms = to_utc_ts(pd.Timestamp(cfg.start_date))
        end_ms   = utc_now_ms()
        df = fetch_range(client, cfg.symbol, cfg.interval, start_ms, end_ms)
        if df.empty:
            raise SystemExit("No data fetched. Check symbol/start_date/testnet setting.")
        df.to_parquet(path)
        print(f"Saved {len(df)} rows → {path}")

    elif mode == "incremental":
        try:
            old = pd.read_parquet(path)
            last_time = old["time"].max()
            start_ms = int(last_time.timestamp() * 1000) + 1
        except Exception:
            old = pd.DataFrame()
            start_ms = to_utc_ts(pd.Timestamp(cfg.start_date))
        end_ms = utc_now_ms()
        df_new = fetch_range(client, cfg.symbol, cfg.interval, start_ms, end_ms)
        if df_new.empty:
            print("No new rows.")
            return
        combined = pd.concat([old, df_new], ignore_index=True) if not old.empty else df_new
        combined = combined.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
        combined.to_parquet(path)
        print(f"Added {len(df_new)} rows | total {len(combined)} → {path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["backfill","incremental"], required=True)
    args = ap.parse_args()
    main(args.mode)
