import argparse
import pandas as pd
import numpy as np
from joblib import dump
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier
from AI.utils import load_config, ensure_dirs, FEATURES

def train_once(df: pd.DataFrame, model_path: str, window_bars: int):
    if len(df) > window_bars:
        df = df.iloc[-window_bars:].copy()

    X = df[FEATURES].values
    y = (df["label"].values + 1)  # -1,0,1 -> 0,1,2

    tscv = TimeSeriesSplit(n_splits=5)
    params = dict(
        n_estimators=400, max_depth=4, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9,
        objective="multi:softprob", num_class=3, eval_metric="mlogloss", n_jobs=4
    )
    best = None; best_score = -1
    for tr, va in tscv.split(X):
        m = XGBClassifier(**params).fit(X[tr], y[tr])
        score = m.score(X[va], y[va])
        if score > best_score:
            best_score, best = score, m

    dump(best, model_path)
    return best_score

def main():
    cfg = load_config()
    ensure_dirs()
    df = pd.read_parquet(cfg.train_path)
    if df.empty:
        raise SystemExit("Empty training dataset. Run build_dataset.py first.")
    acc = train_once(df, cfg.model_path, cfg.train_window_bars)
    print(f"Saved model → {cfg.model_path} | CV acc≈ {acc:.4f}")

if __name__ == "__main__":
    main()
