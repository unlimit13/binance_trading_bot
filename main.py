from trading.account import get_available_balance, get_current_price, ensure_leverage
from status.positions import get_position
from status.open_orders import get_open_orders
from trading.orders import open_position, close_position_market,cancel_protective_orders,cancel_limit_resting_orders
from trading.precision import get_min_notional
import time
from infra.client import SYMBOL, LEVERAGE, LONG, SHORT,MIN_AMOUNT_PERCENTAGE,MIN_BUFFER, um
from status.history import get_order_trades_summary

profit=0
total_profit=0
transactions=0

def main():
    ensure_leverage(SYMBOL, leverage=LEVERAGE)

    while True:
        bal = get_available_balance("USDT")
        order_price = get_current_price(SYMBOL)
        min_notional = get_min_notional(SYMBOL)

        # 이 심볼/레버리지에서 요구되는 '최소 증거금' (버퍼 포함)
        min_margin_needed = (min_notional / LEVERAGE) * MIN_BUFFER

        print(f"\n[LOOP] balance={bal:.4f} USDT, price={order_price}, "
              f"minNotional={min_notional}, minMarginNeeded≈{min_margin_needed:.4f} USDT")

        # 잔고가 최소 주문 증거금보다 낮으면 종료
        if bal < min_margin_needed:
            print("[EXIT] 가용 잔고가 최소 주문 기준에 미달합니다. 루프 종료.")
            break

        # 기본 5% 마진, 미달 시 최소 기준으로 상향
        margin_usdt = max(bal * MIN_AMOUNT_PERCENTAGE, min_margin_needed)

        # 포지션 오픈 (기존 open_position 사용; LIMIT + TP/SL 자동 세팅)
        qty, resp_sl, resp_tp = open_position(
            SYMBOL, side="BUY", margin_usdt=margin_usdt, leverage=LEVERAGE,
            price=order_price + 10, loss_pct=0.70, gain_pct=0.07, tif="GTC"
        )

        # 상태 출력
        p = get_position(SYMBOL)
        if p:
            roi_margin   = f"{p['roiByMargin']*100:.2f}%" if p['roiByMargin'] is not None else "N/A"
            roi_notional = f"{p['roiByNotional']*100:.2f}%" if p['roiByNotional'] is not None else "N/A"
            pnl = f"{p['unrealizedProfit']:.2f} USDT"
            print(f"[POS] {p['side']} {p['positionAmt']} @ entry={p['entryPrice']} "
                  f"(BEP={p['breakEvenPrice']}, liq={p['liquidationPrice']}, lev={p['leverage']}x)")
            print(f"PnL={pnl}, ROI (margin)={roi_margin}, ROI (notional)={roi_notional}")
        else:
            print("[POS] 열린 포지션 없음")
            res = cancel_limit_resting_orders(SYMBOL, include_partially_filled=True)
            print("[CANCEL LIMITS] cancelled:", res["cancelled"])
            print("[CANCEL LIMITS] skipped:", res["skipped"])
            print("[CANCEL LIMITS] errors:", res["errors"])
            continue

        ods = get_open_orders(SYMBOL)
        print(f"[OPEN ORDERS] {len(ods)}개")
        for od in ods:
            print(f"- ({od['kind']}) {od['type']} {od['side']} "
                  f"price={od['price']} stop={od['stopPrice']} "
                  f"qty={od['executedQty']}/{od['origQty']} status={od['status']}")

        # 10초 대기
        print(f"[SLEEP] {10}s 대기 후 포지션 종료")
        time.sleep(10)

        # 보호 주문 전체 취소 + 포지션 전량 청산
        _ = cancel_protective_orders(SYMBOL)
        _ = close_position_market(SYMBOL)

        
        print(f"[SLEEP] {10}s 대기 후 포지션 시작")
        time.sleep(10)
        

if __name__ == "__main__":
    main()
