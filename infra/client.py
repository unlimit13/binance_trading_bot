import os
from dotenv import load_dotenv
from binance.um_futures import UMFutures

load_dotenv()

API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL   = os.getenv("BASE_URL", "https://testnet.binancefuture.com")

# 모든 모듈이 공유하는 Futures 클라이언트 (싱글톤)
um = UMFutures(key=API_KEY, secret=API_SECRET, base_url=BASE_URL)

# 공용 상수
LONG  = "BUY"
SHORT = "SELL"
SYMBOL = "BTCUSDT"
LEVERAGE = 80
MIN_BUFFER = 1.03
MIN_AMOUNT_PERCENTAGE = 0.05 
TIF="GTC"  # "GTC", "IOC", "FOK"

