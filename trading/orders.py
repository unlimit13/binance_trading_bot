import time
from binance.error import ClientError
from infra.client import um
from trading.precision import get_rounders, _get_precisions, _fmt
from status.positions import get_position
from trading.account import get_current_price
from infra.client import SYMBOL

def prepare_order_params(symbol: str, raw_price: float, raw_qty: float):
    """라운딩 + 최소조건 검사 → (price, qty) or None"""
    ROUND_QTY, ROUND_PRICE, CHECK = get_rounders(symbol)
    try:
        price, qty = CHECK(raw_price, raw_qty)
        return price, qty
    except ValueError as e:
        print(f"[ERROR] {symbol} 주문 불가: {e}")
        return None

def prepare_order_params_from_margin(symbol: str, margin_usdt: float, leverage: int, price: float | None = None):
    """증거금/레버리지로 notional→qty 산출 후 라운딩/검사"""
    if price is None:
        price = get_current_price(symbol)
    notional = margin_usdt * leverage
    raw_qty = notional / price
    return prepare_order_params(symbol, price, raw_qty)

def order(symbol: str, side: str, type: str, price: float, qty: float, tif: str = "GTC"):
    """
    Futures 주문 전송 (LIMIT/MARKET 등) + precision 방어
    """
    price_dec, qty_dec = _get_precisions(symbol)
    ROUND_QTY, ROUND_PRICE, _ = get_rounders(symbol)

    price_r = ROUND_PRICE(price)
    qty_r   = ROUND_QTY(qty)

    price_s = _fmt(price_r, price_dec)
    qty_s   = _fmt(qty_r, qty_dec)

    if type.upper() == "MARKET":
        return um.new_order(
            symbol=symbol, side=side, type="MARKET",
            quantity=qty_s, timeInForce=tif
        )
    else:
        return um.new_order(
            symbol=symbol, side=side, type=type,
            price=price_s, quantity=qty_s,
            timeInForce=tif
        )

def place_take_profit_by_roi_pct(symbol: str, side_open: str, entry_price: float,
                                 leverage: int, roi_gain_pct: float = 0.05,
                                 working_type: str = "MARK_PRICE"):
    """ROI +X%에서 전량 TAKE_PROFIT_MARKET"""
    roi = float(roi_gain_pct)
    side_open = side_open.upper()

    if side_open == "BUY":
        raw_tp = entry_price * (1.0 + roi / leverage)
        close_side = "SELL"
    elif side_open == "SELL":
        raw_tp = entry_price * (1.0 - roi / leverage)
        close_side = "BUY"
    else:
        raise ValueError("side_open must be 'BUY' or 'SELL'")

    _, ROUND_PRICE, _ = get_rounders(symbol)
    tp_price = ROUND_PRICE(raw_tp)
    price_dec, _ = _get_precisions(symbol)
    tp_price_s = _fmt(tp_price, price_dec)

    return um.new_order(
        symbol=symbol,
        side=close_side,
        type="TAKE_PROFIT_MARKET",
        stopPrice=tp_price_s,
        closePosition=True,
        workingType=working_type
    )

def place_stop_loss_by_roi_pct(symbol: str, side_open: str, entry_price: float,
                               leverage: int, roi_loss_pct: float = 0.70,
                               working_type: str = "MARK_PRICE"):
    """ROI -X%에서 전량 STOP_MARKET"""
    roi = float(roi_loss_pct)
    side_open = side_open.upper()

    if side_open == "BUY":
        raw_stop = entry_price * (1.0 - roi / leverage)
        close_side = "SELL"
    elif side_open == "SELL":
        raw_stop = entry_price * (1.0 + roi / leverage)
        close_side = "BUY"
    else:
        raise ValueError("side_open must be 'BUY' or 'SELL'")

    _, ROUND_PRICE, _ = get_rounders(symbol)
    stop_price = ROUND_PRICE(raw_stop)
    price_dec, _ = _get_precisions(symbol)
    stop_price_s = _fmt(stop_price, price_dec)

    return um.new_order(
        symbol=symbol,
        side=close_side,
        type="STOP_MARKET",
        stopPrice=stop_price_s,
        closePosition=True,
        workingType=working_type
    )

def open_position(symbol: str, side: str, margin_usdt: float, leverage: int, price: float,
                  loss_pct: float = 0.70, gain_pct: float = 0.07, tif: str = "GTC"):
    """
    포지션 오픈(LIMIT) + entry 확인 후 SL/TP 등록(MARKET형)
    반환: (opened_qty, sl_response, tp_response)
    """
    params = prepare_order_params_from_margin(symbol, margin_usdt, leverage, price)
    if not params:
        print("[INFO] 주문 준비 실패(최소 수량/최소 명목가 미달 등)")
        return None, None, None

    __price, qty = params

    try:
        resp_open = order(symbol, side=side, type="LIMIT", price=__price, qty=qty, tif=tif)
        #print("[ORDER] 주문 전송:", resp_open)
        #print("[ORDER] 주문 전송")
    except ClientError as e:
        print("[ORDER ERROR]", e)
        return None, None, None

    # 체결 진입가가 잡힐 때까지 대기
    entry_px = None
    retry=0
    while entry_px is None:
        pos = get_position(symbol)
        if pos and pos["entryPrice"] > 0:
            entry_px = pos["entryPrice"]
        else:
            print("[WAIT] 포지션 진입 대기 중...")
            retry += 1
            if retry >= 20:
                print("[TIMEOUT] 포지션 진입 실패. 주문 확인 필요.")
                return None, None, None
            time.sleep(1)

    # SL 등록
    try:
        resp_sl = place_stop_loss_by_roi_pct(
            symbol=symbol, side_open=side, entry_price=entry_px,
            leverage=leverage, roi_loss_pct=loss_pct, working_type="MARK_PRICE"
        )
        #print("[SL] 등록:", resp_sl)
        print("[SL] 등록:",resp_sl["stopPrice"])
    except ClientError as e:
        print("[SL ERROR]", e)
        resp_sl = None

    # TP 등록
    try:
        resp_tp = place_take_profit_by_roi_pct(
            symbol=symbol, side_open=side, entry_price=entry_px,
            leverage=leverage, roi_gain_pct=gain_pct, working_type="MARK_PRICE"
        )
        #print("[TP] 등록:", resp_tp)
        print("[TP] 등록:",resp_tp["stopPrice"])
    except ClientError as e:
        print("[TP ERROR]", e)
        res = close_position_market(SYMBOL)
        res = cancel_limit_resting_orders(SYMBOL, include_partially_filled=True)
        res = cancel_protective_orders(SYMBOL)
        resp_tp = None

    return qty, resp_sl, resp_tp

def cancel_limit_resting_orders(symbol: str, include_partially_filled: bool = False):
    """
    TP/SL/트레일링 등 보호주문은 유지하고,
    '일반 LIMIT 대기 주문'만 취소한다.

    - include_partially_filled=True 이면 PARTIALLY_FILLED 상태도 취소 시도
    반환: {"cancelled":[orderId...], "skipped":[orderId...], "errors":[(orderId, str(e))...] }
    """
    from infra.client import um
    from status.open_orders import get_open_orders

    CANCELABLE_STATUSES = {"NEW", "PENDING_NEW"}
    if include_partially_filled:
        CANCELABLE_STATUSES |= {"PARTIALLY_FILLED"}

    cancelled, skipped, errors = [], [], []

    orders = get_open_orders(symbol)  # 모든 미체결(보호+일반)
    for od in orders:
        # 보호주문(Stop/TP/Trailing or reduceOnly/closePosition)은 건너뜀
        protective = (
            od["kind"] in {"stop_loss", "take_profit", "trailing"}
            or od.get("reduceOnly") or od.get("closePosition")
        )
        if protective:
            skipped.append(od["orderId"])
            continue

        # LIMIT 주문만 대상으로, 취소 가능한 상태만
        if od["kind"] == "limit" and (od["status"] in CANCELABLE_STATUSES):
            try:
                um.cancel_order(symbol=symbol, orderId=od["orderId"])
                cancelled.append(od["orderId"])
            except Exception as e:
                errors.append((od["orderId"], str(e)))
        else:
            skipped.append(od["orderId"])

    return {"cancelled": cancelled, "skipped": skipped, "errors": errors}

def cancel_protective_orders(symbol: str):
    """
    TP/SL/트레일링 등 '보호성' 주문만 모두 취소.
    반환: {"cancelled": [orderId...]}
    """
    from infra.client import um
    from status.open_orders import get_open_orders

    cancelled = []
    orders = get_open_orders(symbol)  # 모든 미체결
    for od in orders:
        otype = (od["type"] or "").upper()
        is_protective = (
            otype in {"STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET"}
            or od.get("reduceOnly") or od.get("closePosition")
        )
        if is_protective:
            try:
                um.cancel_order(symbol=symbol, orderId=od["orderId"])
                cancelled.append(od["orderId"])
            except Exception as e:
                print(f"[CANCEL ERR] orderId={od['orderId']} {e}")
    return {"cancelled": cancelled}

def close_position_market(symbol: str):
    """
    현재 열린 포지션이 있으면 전량 MARKET로 청산(reduceOnly=True)
    반환: {"close_resp": resp or None, "closed_qty": float}
    """
    from infra.client import um
    from status.positions import get_position
    from trading.precision import get_rounders, _get_precisions, _fmt

    pos = get_position(symbol)
    if not pos:
        return {"close_resp": None, "closed_qty": 0.0}

    side_close = "SELL" if pos["side"] == "LONG" else "BUY"
    qty_raw = abs(float(pos["positionAmt"]))
    ROUND_QTY, _, _ = get_rounders(symbol)
    qty = ROUND_QTY(qty_raw)

    if qty <= 0:
        print("[WARN] 청산 수량이 0 입니다. 주문 스킵.")
        return {"close_resp": None, "closed_qty": 0.0}

    # 정밀 포맷
    _, qty_dec = _get_precisions(symbol)
    qty_s = _fmt(qty, qty_dec)

    try:
        resp = um.new_order(
            symbol=symbol,
            side=side_close,
            type="MARKET",
            quantity=qty_s,
            reduceOnly=True
        )
    except Exception as e:
        print("[CLOSE ERR]", e)
        resp = None

    return {"close_resp": resp, "closed_qty": qty}

def wait_protective_or_timeout(symbol: str, tp_order_id: int | None, sl_order_id: int | None,
                               timeout_sec: int = 30, poll_sec: float = 0.5):
    """
    TP/SL 주문이 FILLED 되는지 30초(기본) 동안 폴링.
    - TP/SL 중 하나가 FILLED 되면: {"reason":"TP"|"SL", "filled_order_id": int, "filled_order": dict, "timeout": False}
    - 타임아웃이면:               {"reason":"IDLE", "filled_order_id": None, "filled_order": None, "timeout": True}
    """


    watch = []
    if tp_order_id: watch.append(("TP", tp_order_id))
    if sl_order_id: watch.append(("SL", sl_order_id))

    end_t = time.time() + timeout_sec
    last = {}
    while time.time() < end_t:
        for tag, oid in watch:
            try:
                od = um.get_order(symbol=symbol, orderId=oid)
                last[(tag, oid)] = od
                if od.get("status") == "FILLED":
                    return {"reason": tag, "filled_order_id": oid, "filled_order": od, "timeout": False}
            except Exception:
                pass
        time.sleep(poll_sec)

    return {"reason": "IDLE", "filled_order_id": None, "filled_order": None, "timeout": True}

def force_close_on_timeout(symbol: str):
    """
    타임아웃 시: 보호주문 전부 취소 → 포지션 전량 시장가 청산.
    반환: {"close_order_id": int|None, "close_resp": dict|None}
    """
    _ = cancel_protective_orders(symbol)
    res = close_position_market(symbol)
    close_resp = res.get("close_resp")
    return {
        "close_order_id": (close_resp.get("orderId") if close_resp else None),
        "close_resp": close_resp
    }
    
def get_limit_price_from_orderbook(symbol: str, side: str, depth_limit: int = 5,
                                   maker_mode: bool = False, price_offset_ticks: int = 1):
    """
    호가창에서 LIMIT 주문가 선택:
      - 기본(테이커): BUY→최저 ask, SELL→최고 bid
      - maker_mode=True:
          BUY → 최고 bid - (price_offset_ticks * tickSize)
          SELL → 최저 ask + (price_offset_ticks * tickSize)
        ※ TIF는 GTX(Post Only)를 권장(즉시 체결 방지)
    반환: 라운딩된 price(float)
    """
    from infra.client import um
    from trading.precision import get_rounders

    side_u = side.upper()
    ob = um.depth(symbol=symbol, limit=depth_limit)  # {"bids":[[price,qty],...], "asks":[[price,qty],...]}

    # tickSize 추출
    ex = um.exchange_info()
    s = next(x for x in ex["symbols"] if x["symbol"] == symbol)
    pricef = next(f for f in s["filters"] if f["filterType"] == "PRICE_FILTER")
    tick_size = float(pricef["tickSize"])

    if side_u == "BUY":
        if maker_mode:
            if not ob.get("bids"):
                raise RuntimeError("orderbook bids empty")
            base = float(ob["bids"][0][0])  # 최고 매수호가
            raw_price = base - price_offset_ticks * tick_size
        else:
            if not ob.get("asks"):
                raise RuntimeError("orderbook asks empty")
            raw_price = float(ob["asks"][0][0])  # 최저 매도호가(테이커)
    elif side_u == "SELL":
        if maker_mode:
            if not ob.get("asks"):
                raise RuntimeError("orderbook asks empty")
            base = float(ob["asks"][0][0])  # 최저 매도호가
            raw_price = base + price_offset_ticks * tick_size
        else:
            if not ob.get("bids"):
                raise RuntimeError("orderbook bids empty")
            raw_price = float(ob["bids"][0][0])  # 최고 매수호가(테이커)
    else:
        raise ValueError("side must be 'BUY' or 'SELL'")

    # 음수 방지 + tick 라운딩
    raw_price = max(raw_price, tick_size)
    _, round_price, _ = get_rounders(symbol)
    return round_price(raw_price)

