# AI/hourly_update.py
import subprocess, sys
from pathlib import Path

def run_mod(mod: str, *args: str):
    # 프로젝트 루트를 CWD로 고정
    project_root = Path(__file__).resolve().parent.parent  # binance/
    cmd = [sys.executable, "-m", mod, *args]
    print(">", " ".join(cmd), f"(cwd={project_root})")
    subprocess.run(cmd, check=True, cwd=str(project_root))

def main():
    # 1) 새 데이터 수집(증분)
    run_mod("AI.fetch_klines", "--mode", "incremental")

    # 2) 피처/라벨 갱신
    run_mod("AI.build_dataset")

    # 3) 재학습
    run_mod("AI.train")

    # 4) 최신 신호 출력(로그/모니터링용)
    run_mod("AI.decide")

if __name__ == "__main__":
    main()
