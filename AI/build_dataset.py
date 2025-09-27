import argparse
import pandas as pd
from utils import load_config, ensure_dirs, compute_features, make_labels, FEATURES

def main():
    cfg = load_config()
    ensure_dirs()
    df = pd.read_parquet(cfg.data_path)
    if df.empty:
        raise SystemExit("Empty price file. Run fetch_klines.py first.")

    df_feat = compute_features(df)
    df_lbl  = make_labels(df_feat, cfg.horizon, cfg.theta)

    data = df_lbl.dropna(subset=FEATURES + ["label"]).reset_index(drop=True)
    data.to_parquet(cfg.train_path)
    print(f"Dataset saved: {len(data)} rows → {cfg.train_path}")
    print("Feature columns:", FEATURES)

if __name__ == "__main__":
    main()
