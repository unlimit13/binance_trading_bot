# status/history.py
from infra.client import um

def get_order_trades_summary(symbol: str, order_id: int):
    """
    특정 주문(order_id)의 체결 히스토리를 불러와
    체결수량 가중 평균체결가, 총 수수료, 총 실현손익을 계산.
    반환: {"avg_price": float|None, "filled_qty": float, "commission": float, "realized_pnl": float}
    """
    trades = um.get_account_trades(symbol=symbol, orderId=order_id) or []
    if not trades:
        return {"avg_price": None, "filled_qty": 0.0, "commission": 0.0, "realized_pnl": 0.0}

    total_qty = 0.0
    total_px_qty = 0.0
    total_fee = 0.0
    total_realized = 0.0

    for t in trades:
        qty = float(t.get("qty", 0) or 0)
        price = float(t.get("price", 0) or 0)
        fee = float(t.get("commission", 0) or 0)
        realized = float(t.get("realizedPnl", 0) or 0)
        total_qty += qty
        total_px_qty += price * qty
        total_fee += fee
        total_realized += realized

    avg_price = (total_px_qty / total_qty) if total_qty > 0 else None
    return {"avg_price": avg_price, "filled_qty": total_qty, "commission": total_fee, "realized_pnl": total_realized}

def calc_pnl_roi_from_order(symbol: str, order_id: int,
                            entry_price_ref: float, iso_wallet_ref: float | None):
    """
    get_account_trades 기반으로 avg_price/realized/commission 합산하여
    Net PnL(= realized - commission)과 ROI(= net / iso_wallet_ref) 계산.
    반환: {"avg": float|None, "qty": float, "realized": float, "fee": float, "net": float, "roi": float|None}
    """
    
    s = get_order_trades_summary(symbol, order_id)
    avg = s["avg_price"]
    qty = s["filled_qty"]
    realized = s["realized_pnl"]
    fee = s["commission"]
    net = realized - fee
    roi = (net / iso_wallet_ref) if iso_wallet_ref and iso_wallet_ref > 0 else None
    return {"avg": avg, "qty": qty, "realized": realized, "fee": fee, "net": net, "roi": roi}
