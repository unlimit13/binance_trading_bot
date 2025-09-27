from binance.error import ClientError
from infra.client import um

def ensure_leverage(symbol: str, leverage: int = 50):
    """심볼 레버리지를 지정 배수로 맞춤(예: 50x) + ISOLATED 기본 설정"""
    try:
        um.change_margin_type(symbol=symbol, marginType="ISOLATED")
    except Exception:
        pass  # 이미 ISOLATED면 무시
    um.change_leverage(symbol=symbol, leverage=leverage)

def get_available_balance(asset: str = "USDT") -> float:
    """선물 계좌에서 특정 자산의 availableBalance 반환"""
    try:
        balances = um.balance()
        for b in balances:
            if b["asset"] == asset:
                return float(b["availableBalance"])
        return 0.0
    except ClientError as e:
        print("Error fetching balance:", e)
        return 0.0

def get_current_price(symbol: str = "BTCUSDT") -> float:
    """특정 심볼의 현재 가격(마지막 체결 가격)"""
    try:
        ticker = um.ticker_price(symbol=symbol)
        return float(ticker["price"])
    except ClientError as e:
        print("Error fetching price:", e)
        return 0.0
