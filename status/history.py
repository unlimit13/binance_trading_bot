# status/history.py
from infra.client import um

def get_order_trades_summary(symbol: str, order_id: int):
    """
    체결 히스토리 합산:
      - avg_price: 체결가중평균
      - filled_qty: 총 체결 수량
      - commission: 총 수수료
      - commission_asset: 수수료 자산(보통 USDT; 혼재 시 첫 값 반환)
      - realized_pnl: 실현손익(수수료 제외)
    """
    trades = um.get_account_trades(symbol=symbol, orderId=order_id) or []
    if not trades:
        return {"avg_price": None, "filled_qty": 0.0, "commission": 0.0,
                "commission_asset": None, "realized_pnl": 0.0}

    total_qty, total_px_qty = 0.0, 0.0
    total_fee, total_realized = 0.0, 0.0
    fee_asset = None

    for t in trades:
        qty   = float(t.get("qty", 0) or 0)
        price = float(t.get("price", 0) or 0)
        fee   = float(t.get("commission", 0) or 0)
        rpnl  = float(t.get("realizedPnl", 0) or 0)
        total_qty += qty
        total_px_qty += price * qty
        total_fee += fee
        total_realized += rpnl
        if fee_asset is None:
            fee_asset = t.get("commissionAsset")

    avg_price = (total_px_qty / total_qty) if total_qty > 0 else None
    return {
        "avg_price": avg_price,
        "filled_qty": total_qty,
        "commission": total_fee,
        "commission_asset": fee_asset,
        "realized_pnl": total_realized,
    }

def calc_pnl_roi_from_order(symbol: str, order_id: int,
                            entry_price_ref: float, iso_wallet_ref: float | None):
    """
    get_order_trades_summary 기반으로 Net PnL/ROI 계산
    - realized: 실현손익(수수료 제외)
    - net: realized - commission
    """
    s = get_order_trades_summary(symbol, order_id)
    avg = s["avg_price"]
    qty = s["filled_qty"]
    realized = s["realized_pnl"]            # 수수료 제외 실현손익
    fee = s["commission"]
    fee_asset = s["commission_asset"]
    net = realized - fee
    roi = (net / iso_wallet_ref) if iso_wallet_ref and iso_wallet_ref > 0 else None
    return {"avg": avg, "qty": qty, "realized": realized, "fee": fee,
            "fee_asset": fee_asset, "net": net, "roi": roi}
