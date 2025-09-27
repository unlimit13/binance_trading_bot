import pandas as pd
from utils import load_config, ensure_dirs
import subprocess, sys, pathlib

def run(cmd: list[str]):
    print(">", " ".join(cmd))
    res = subprocess.run(cmd, check=True)
    return res.returncode

def main():
    cfg = load_config()
    ensure_dirs()

    # 1) 새 데이터 수집(증분)
    run([sys.executable, "fetch_klines.py", "--mode", "incremental"])

    # 2) 피처/라벨 갱신
    run([sys.executable, "build_dataset.py"])

    # 3) 재학습
    run([sys.executable, "train.py"])

    # 4) 최신 신호 출력(로그/모니터링용)
    run([sys.executable, "decide.py"])

if __name__ == "__main__":
    main()
