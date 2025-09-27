from infra.client import um

def get_position(symbol: str):
    """
    열린 포지션 정보 + ROI 계산 반환, 없으면 None.
    ROI:
      - roiByMargin = uPnL / isolatedWallet
      - roiByNotional = uPnL / (abs(positionAmt)*entryPrice)
    """
    data = um.get_position_risk(symbol=symbol)
    rows = data if isinstance(data, list) else [data]
    opened = [r for r in rows if abs(float(r.get("positionAmt", "0"))) > 0]
    if not opened:
        return None

    pos = max(opened, key=lambda r: abs(float(r.get("positionAmt", "0"))))
    amt = float(pos.get("positionAmt", "0"))
    side = "LONG" if amt > 0 else "SHORT"

    entry = float(pos.get("entryPrice", "0") or 0)
    u_pnl = float(pos.get("unRealizedProfit", pos.get("unrealizedProfit", "0")) or 0)
    iso_wallet = float(pos.get("isolatedWallet", "0") or 0)

    notional = abs(amt) * entry if entry > 0 else 0.0
    roi_by_margin = (u_pnl / iso_wallet) if iso_wallet > 0 else None
    roi_by_notional = (u_pnl / notional) if notional > 0 else None

    return {
        "symbol": symbol,
        "side": side,
        "positionAmt": amt,
        "entryPrice": entry,
        "breakEvenPrice": float(pos.get("breakEvenPrice", pos.get("breakEvenPoint", "0")) or 0),
        "markPrice": float(pos.get("markPrice", "0") or 0),
        "unrealizedProfit": u_pnl,
        "leverage": int(float(pos.get("leverage", "0") or 0)),
        "marginType": (pos.get("marginType") or "").lower(),
        "liquidationPrice": float(pos.get("liquidationPrice", "0") or 0),
        "isolatedWallet": iso_wallet,
        "roiByMargin": roi_by_margin,
        "roiByNotional": roi_by_notional,
    }




