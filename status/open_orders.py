from binance.error import ParameterRequiredError
from infra.client import um

def get_open_orders_safe(symbol: str):
    """
    일부 라이브러리 버전에서 get_open_orders()가 orderId를 요구하는 문제를 우회.
    1) 정상 동작하면 그대로 사용
    2) 에러 시 get_orders()로 최근 히스토리 받아 '열린 상태'만 필터
    """
    try:
        return um.get_open_orders(symbol=symbol) or []
    except ParameterRequiredError:
        hist = um.get_orders(symbol=symbol, limit=500) or []
        OPEN_STATUSES = {"NEW", "PARTIALLY_FILLED", "PENDING_NEW"}
        return [o for o in hist if (o.get("status") in OPEN_STATUSES)]

def get_open_orders(symbol: str):
    """심볼의 모든 미체결 주문(보호주문 + 일반 지정가 등) 리스트 반환. 없으면 []"""
    oo = get_open_orders_safe(symbol)

    def classify_kind(t: str) -> str:
        t = (t or "").upper()
        if t == "LIMIT": return "limit"
        if t.startswith("TAKE_PROFIT"): return "take_profit"
        if t.startswith("STOP") and t != "TRAILING_STOP_MARKET": return "stop_loss"
        if t == "TRAILING_STOP_MARKET": return "trailing"
        return "other"

    out = []
    for o in (oo or []):
        otype = (o.get("type") or "").upper()
        out.append({
            "orderId": int(o.get("orderId")),
            "type": otype,
            "side": o.get("side"),
            "reduceOnly": bool(o.get("reduceOnly", False)),
            "closePosition": bool(o.get("closePosition", False)),
            "workingType": o.get("workingType"),
            "stopPrice": float(o.get("stopPrice")) if o.get("stopPrice") else None,
            "price": float(o.get("price", 0) or 0),
            "origQty": float(o.get("origQty", 0) or 0),
            "executedQty": float(o.get("executedQty", 0) or 0),
            "status": o.get("status"),
            "timeInForce": o.get("timeInForce"),
            "kind": classify_kind(otype),
        })
    return out
