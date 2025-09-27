from infra.client import um

def _get_precisions(symbol: str):
    """심볼의 tickSize/stepSize로 가격/수량 허용 소수점 자리(decimals) 계산"""
    ex = um.exchange_info()
    s = next(x for x in ex["symbols"] if x["symbol"] == symbol)
    pricef = next(f for f in s["filters"] if f["filterType"] == "PRICE_FILTER")
    lot    = next(f for f in s["filters"] if f["filterType"] in ("MARKET_LOT_SIZE", "LOT_SIZE"))

    def _decimals(x: float):
        txt = f"{x:.16f}".rstrip("0").rstrip(".")
        return len(txt.split(".")[1]) if "." in txt else 0

    tick_size = float(pricef["tickSize"])
    step_size = float(lot["stepSize"])
    return _decimals(tick_size), _decimals(step_size)

def _fmt(v: float, decimals: int) -> str:
    """정확히 허용 자리수로 포맷"""
    return f"{v:.{decimals}f}"

def get_rounders(symbol: str):
    """
    지정 심볼의 수량/가격 라운딩 + 최소조건 검사 유틸 반환
    반환: (round_qty, round_price, check_minimums)
    """
    ex = um.exchange_info()
    s = next(x for x in ex["symbols"] if x["symbol"] == symbol)

    lot = next(f for f in s["filters"] if f["filterType"] in ("MARKET_LOT_SIZE", "LOT_SIZE"))
    pricef = next(f for f in s["filters"] if f["filterType"] == "PRICE_FILTER")
    notionalf = next(f for f in s["filters"] if f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL"))

    step_size    = float(lot["stepSize"])
    min_qty      = float(lot["minQty"])
    tick_size    = float(pricef["tickSize"])
    min_notional = float(notionalf.get("notional") or notionalf.get("minNotional") or 0.0)

    import math
    def round_qty(q: float) -> float:
        return math.floor(q / step_size) * step_size if step_size > 0 else q

    def round_price(p: float) -> float:
        return math.floor(p / tick_size) * tick_size if tick_size > 0 else p

    def check_minimums(price: float, qty: float):
        rp = round_price(price)
        rq = round_qty(qty)
        if rq < min_qty:
            raise ValueError(f"qty {rq} < minQty {min_qty}")
        if rp * rq < min_notional:
            raise ValueError(f"notional {rp*rq} < minNotional {min_notional}")
        return rp, rq

    return round_qty, round_price, check_minimums

def get_min_notional(symbol: str) -> float:
    """심볼의 (MIN_)NOTIONAL을 가져온다."""
    ex = um.exchange_info()
    s = next(x for x in ex["symbols"] if x["symbol"] == symbol)
    nf = next(f for f in s["filters"] if f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL"))
    return float(nf.get("notional") or nf.get("minNotional") or 0.0)