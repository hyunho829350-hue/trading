import sys
import time
import signal
print("0. 시작")
sys.path.insert(0, r"C:\trading\app")

from config                      import Config
from utils.logger                import get_logger
from notify.telegram_bot         import TelegramBot
from risk.risk_manager           import RiskManager
from engine.trade_engine         import TradeEngine
from strategy.combined_strategy  import CombinedStrategy
from web.app                     import run_server_thread, update_state, add_log

log = get_logger("MAIN")

# ── 종료 플래그 ──────────────────────────────
_running = True

def on_exit(sig, frame):
    global _running
    _running = False
    log.info("종료 신호 수신")

signal.signal(signal.SIGINT,  on_exit)
signal.signal(signal.SIGTERM, on_exit)


# ── 초기화 ───────────────────────────────────
def init():
    log.info("=" * 50)
    log.info("매매 시스템 초기��� 시작")
    log.info("MODE    = " + Config.MODE)
    log.info("CAPITAL = " + format(Config.INITIAL_CAPITAL, ","))
    log.info("TICKERS = " + str(Config.TICKERS))
    log.info("=" * 50)

    # 텔레그램
    telegram = TelegramBot(
        token   = Config.TELEGRAM_TOKEN,
        chat_id = Config.TELEGRAM_CHAT_ID,
        enabled = Config.TELEGRAM_ENABLED,
    )

    # 리스크 관리자
    risk = RiskManager(
        total_capital        = Config.INITIAL_CAPITAL,
        max_per_stock        = Config.MAX_PER_STOCK,
        stop_loss            = Config.STOP_LOSS,
        take_profit          = Config.TAKE_PROFIT,
        max_daily_loss       = Config.MAX_DAILY_LOSS,
        max_stocks           = Config.MAX_STOCKS,
        max_consecutive_loss = Config.MAX_CONSECUTIVE_LOSS,
        max_daily_trades     = Config.MAX_DAILY_TRADES,
    )

    # 매매 엔진
    engine = TradeEngine(
        capital            = Config.INITIAL_CAPITAL,
        mode               = Config.MODE,
        max_position_ratio = Config.MAX_PER_STOCK,
        max_positions      = Config.MAX_STOCKS,
    )

    # 전략 등록 (전 종목 동일 복합전략)
    for ticker in Config.TICKERS:
        strategy = CombinedStrategy(params=Config.COMBINED_PARAMS)
        engine.add_strategy(ticker, strategy)
        log.info("전략 등록 완료: " + ticker)

    # 웹 대시보드
    if Config.WEB_ENABLED:
        run_server_thread(port=Config.WEB_PORT)
        log.info("웹 대시보드: http://localhost:" + str(Config.WEB_PORT))

    # 시스템 시작 알림
    telegram.send_start(
        capital    = Config.INITIAL_CAPITAL,
        strategies = [s["name"] for s in Config.COMBINED_PARAMS["strategies"]],
    )
    add_log("🚀 매매 시스템 시작")

    return engine, risk, telegram


# ── 웹 상태 동기화 ───────────────────────────
def sync_web(engine, risk):
    s = engine.status()
    r = risk.status() if hasattr(risk, "status") else {}
    update_state({
        "capital":         s["capital"],
        "eval_value":      s["eval_value"],
        "total_asset":     s["total_asset"],
        "initial_capital": Config.INITIAL_CAPITAL,
        "pnl":             s["pnl"],
        "pnl_rate":        s["pnl_rate"],
        "buy_count":       s["buy_count"],
        "sell_count":      s["sell_count"],
        "positions":       s["positions"],
        "risk": {
            "blocked":          r.get("blocked",          False),
            "block_reason":     r.get("block_reason",     ""),
            "daily_pnl":        r.get("daily_pnl",        0),
            "daily_pnl_rate":   r.get("daily_pnl_rate",   0.0),
            "daily_trades":     r.get("daily_trades",     0),
            "consecutive_loss": r.get("consecutive_loss", 0),
        },
    })


# ── 더미 봉 생성 (실전 연동 전 테스트용) ───────
def make_dummy_bars(tickers, count=80):
    import random
    bars = {}
    for ticker in tickers:
        base  = 50000
        price = base
        data  = []
        vol_base = 500000
        for i in range(count):
            change = random.randint(-300, 400)
            price  = max(price + change, 10000)
            vol    = int(vol_base * random.uniform(0.5, 3.0))
            data.append({
                "datetime": "2026" + str(i).zfill(4),
                "open":     price - random.randint(0, 200),
                "high":     price + random.randint(0, 500),
                "low":      price - random.randint(0, 400),
                "close":    price,
                "volume":   vol,
            })
        bars[ticker] = data
    return bars


# ── 메인 루프 ────────────────────────────────
def main():
    global _running

    engine, risk, telegram = init()

    # 더미 봉 데이터 준비 (실전 연동 전)
    log.info("더미 봉 데이터 생성 중...")
    bars = make_dummy_bars(Config.TICKERS, count=100)

    log.info("매매 루프 시작")
    bar_idx = 0
    max_idx = max(len(v) for v in bars.values())

    while _running and bar_idx < max_idx:
        for ticker in Config.TICKERS:
            ticker_bars = bars[ticker]
            if bar_idx >= len(ticker_bars):
                continue

            bar = ticker_bars[bar_idx]

            # 리스크 체크 후 엔진에 봉 전달
            can, reason = risk.can_buy(
                ticker,
                bar["close"],
                risk.calc_qty(ticker, bar["close"], engine.capital),
                engine.capital,
            )
            if not can and "차단" in reason:
                telegram.send_risk_block(reason)
                add_log("⛔ " + reason)

            # 엔진 봉 수신
            prev_buy  = engine.order_mgr.total_buy_count()
            prev_sell = engine.order_mgr.total_sell_count()
            engine.on_bar(ticker, bar)
            new_buy  = engine.order_mgr.total_buy_count()
            new_sell = engine.order_mgr.total_sell_count()

            # 매수 발생
            if new_buy > prev_buy:
                pos = engine.position_mgr.get(ticker)
                telegram.send_buy(
                    ticker   = ticker,
                    name     = ticker,
                    price    = bar["close"],
                    qty      = pos["qty"],
                    strategy = "CombinedStrategy",
                )
                add_log("🟢 " + ticker + " 매수 " +
                        format(bar["close"], ",") + "원")
                risk.on_buy(ticker, bar["close"],
                            engine.position_mgr.get_qty(ticker))

            # 매도 발생
            if new_sell > prev_sell:
                pnl      = engine.capital - Config.INITIAL_CAPITAL
                pnl_rate = pnl / Config.INITIAL_CAPITAL * 100
                telegram.send_sell(
                    ticker   = ticker,
                    name     = ticker,
                    price    = bar["close"],
                    qty      = 0,
                    pnl      = pnl,
                    pnl_rate = pnl_rate,
                    reason   = "전략신호",
                )
                add_log("🔵 " + ticker + " 매도 " +
                        format(bar["close"], ",") + "원")
                risk.on_sell(ticker, bar["close"], 0)

        # 웹 상태 동기화
        sync_web(engine, risk)
        bar_idx += 1
        time.sleep(0.05)   # 실전에서는 BAR_INTERVAL 초로 변경

    # ── 종료 처리 ────────────────────────────
    log.info("매매 루프 종료")
    s = engine.status()
    telegram.send_stop(
        total_asset = s["total_asset"],
        pnl         = s["pnl"],
        pnl_rate    = s["pnl_rate"],
    )
    telegram.send_daily_report(
        date        = "2026-02-22",
        total_asset = s["total_asset"],
        pnl         = s["pnl"],
        pnl_rate    = s["pnl_rate"],
        buy_count   = s["buy_count"],
        sell_count  = s["sell_count"],
        win_count   = max(0, s["sell_count"] - 1),
        lose_count  = 1,
    )
    add_log("🏁 매매 시스템 종료")
    sync_web(engine, risk)

    print()
    engine.print_status()
    print()
    log.info("시스템 종료 완료 ✅")


if __name__ == "__main__":
    main()