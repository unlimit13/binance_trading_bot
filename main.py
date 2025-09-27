from trading.account import get_available_balance, get_current_price, ensure_leverage
from status.positions import get_position
from status.open_orders import get_open_orders
from trading.orders import (
    open_position, close_position_market,
    cancel_protective_orders, cancel_limit_resting_orders,
    wait_protective_or_timeout, force_close_on_timeout,get_limit_price_from_orderbook
)
from trading.precision import get_min_notional
import time
from infra.client import SYMBOL,TIF, LEVERAGE, LONG, SHORT, MIN_AMOUNT_PERCENTAGE, MIN_BUFFER, um
from status.history import get_order_trades_summary, calc_pnl_roi_from_order
from datetime import datetime

profit = 0.0
total_profit = 0.0
total_transactions = 0
filled_by_sl = 0
filled_by_tp = 0
clear_by_idle = 0
fee = 0


def log_transaction(tx_num: int, lines: list[str]):
    """transaction.txt 파일에 트랜잭션 단위 로그 기록"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_filename = f"{today_str}-transaction.txt"
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(f"\nTRANSACTION #{tx_num} -------------------\n")
        for line in lines:
            f.write(line + "\n")


def main():
    global fee, profit, total_profit, total_transactions, filled_by_sl, filled_by_tp, clear_by_idle
    ensure_leverage(SYMBOL, leverage=LEVERAGE)
    selected_side=LONG

    while True:
        if selected_side==LONG:
            selected_side=SHORT
        else:
            selected_side=LONG

        tx_lines = []
        bal = get_available_balance("USDT")
        tx_lines.append(f"[BALANCE] availableBalance={bal:.2f} USDT")
        order_price = get_limit_price_from_orderbook(SYMBOL, side="BUY", maker_mode=True, price_offset_ticks=1)
        min_notional = get_min_notional(SYMBOL)

        min_margin_needed = (min_notional / LEVERAGE) * MIN_BUFFER

        if bal < min_margin_needed:
            print("[EXIT] 가용 잔고가 최소 주문 기준에 미달합니다. 루프 종료.")
            break

        margin_usdt = max(bal * MIN_AMOUNT_PERCENTAGE, min_margin_needed)
        print("----------------TRANSACTION #",total_transactions + 1)
        qty, resp_sl, resp_tp = open_position(
            SYMBOL, side=selected_side, margin_usdt=margin_usdt, leverage=LEVERAGE,
            price=order_price , loss_pct=0.3, gain_pct=0.08, tif=TIF
        )

        pos = get_position(SYMBOL)
        if not pos:
            print("[ERROR] 포지션 오픈 실패 또는 즉시 체결 안 됨")
            res = cancel_limit_resting_orders(SYMBOL, include_partially_filled=True)
            time.sleep(5)
            continue

        entry_ref = pos["entryPrice"]
        iso_ref = pos["isolatedWallet"]
        side_ref = pos["side"]

        
        tx_lines.append(f"[POS] {pos['side']} amount={pos['isolatedWallet']:.2f}USDT "
                        f"@ entry={pos['entryPrice']} (BEP={pos['breakEvenPrice']}, "
                        f"liq={pos['liquidationPrice']}, lev={pos['leverage']}x)")

        tp_id = (resp_tp.get("orderId") if resp_tp else None)
        sl_id = (resp_sl.get("orderId") if resp_sl else None)

        w = wait_protective_or_timeout(SYMBOL, tp_order_id=tp_id, sl_order_id=sl_id,
                                       timeout_sec=900, poll_sec=0.5)

        reason = w["reason"]
        close_order_id = None

        if reason in ("TP", "SL"):
            filled_id = w["filled_order_id"]
            stats = calc_pnl_roi_from_order(SYMBOL, filled_id, entry_ref, iso_ref)
            profit = stats["net"] if stats["net"] is not None else 0.0
            roi_pct = f"{(stats['roi']*100):.2f}%" if stats["roi"] is not None else "N/A"

            if reason == "TP":
                filled_by_tp += 1
            else:
                filled_by_sl += 1

            tx_lines.append(
                f"[CLOSE] 이유={reason}, orderId={filled_id if reason!='IDLE' else close_order_id}, "
                f"avg={stats['avg']}, qty={stats['qty']}, "
                f"fee={stats['fee']:.4f} {stats['fee_asset'] or 'USDT'}, "
                f"realized(ex fee)={stats['realized']:.4f} USDT, "
                f"net={profit:.4f} USDT"
            )
            tx_lines.append(f"[RESULT] Net PnL={profit:.4f} USDT, ROI(margin)={roi_pct}")


        else:
            clear_by_idle += 1
            fc = force_close_on_timeout(SYMBOL)
            close_order_id = fc["close_order_id"]

            if close_order_id:
                stats = calc_pnl_roi_from_order(SYMBOL, close_order_id, entry_ref, iso_ref)
                profit = stats["net"] if stats["net"] is not None else 0.0
                roi_pct = f"{(stats['roi']*100):.2f}%" if stats["roi"] is not None else "N/A"

                tx_lines.append(
                    f"[CLOSE] 이유={reason}, orderId={filled_id if reason!='IDLE' else close_order_id}, "
                    f"avg={stats['avg']}, qty={stats['qty']}, "
                    f"fee={stats['fee']:.4f} {stats['fee_asset'] or 'USDT'}, "
                    f"realized(ex fee)={stats['realized']:.4f} USDT, "
                    f"net={profit:.4f} USDT"
                )
                tx_lines.append(f"[RESULT] Net PnL={profit:.4f} USDT, ROI(margin)={roi_pct}")

            else:
                profit = 0.0
                print("[ERROR] IDLE 청산 주문 없음(이미 청산되었을 수 있음)")

        total_transactions += 1
        total_profit += profit

        tx_lines.append(f"[STATS] tx={total_transactions}, TP={filled_by_tp}, SL={filled_by_sl}, IDLE={clear_by_idle}")
        tx_lines.append(f"[STATS] last PnL={profit:.4f} USDT, total_profit={total_profit:.4f} USDT")

        log_transaction(total_transactions, tx_lines)

        time.sleep(5)


if __name__ == "__main__":
    main()
