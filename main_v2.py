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
from scheduler.market_scheduler  import MarketScheduler
from web.app                     import run_server_thread, update_state, add_log

log = get_logger("MAIN")

# ── 전역 객체 ────────────────────────────────
engine    = None
risk      = None
telegram  = None
scheduler = None
_running  = True

def on_exit(sig, frame):
    global _running
    _running = False
    if scheduler:
        scheduler.stop()
    log.info("종료 신호 수신")

signal.signal(signal.SIGINT,  on_exit)
signal.signal(signal.SIGTERM, on_exit)


# ── 초기화 ───────────────────────────────────
def init():
    global engine, risk, telegram, scheduler

    log.info("=" * 50)
    log.info("매매 시스템 초기화 시작")
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

    # 전략 등록
    for ticker in Config.TICKERS:
        strategy = CombinedStrategy(params=Config.COMBINED_PARAMS)
        engine.add_strategy(ticker, strategy)
        log.info("전략 등록 완료: " + ticker)

    # 스케줄러
    scheduler = MarketScheduler()
    scheduler.on_reset(_on_daily_reset)
    scheduler.on_start(_on_market_open)
    scheduler.on_pre_close(_on_pre_close)
    scheduler.on_stop(_on_market_close)
    scheduler.start()

    # 웹 대시보드
    if Config.WEB_ENABLED:
        run_server_thread(port=Config.WEB_PORT)
        log.info("웹 대시보드: http://localhost:" + str(Config.WEB_PORT))

    # 시작 알림
    telegram.send_start(
        capital    = Config.INITIAL_CAPITAL,
        strategies = [s["name"] for s in Config.COMBINED_PARAMS["strategies"]],
    )
    add_log("🚀 매매 시스템 시작")


# ── 스케줄러 콜백 ────────────────────────────
def _on_daily_reset(dt):
    """08:50 일일 리셋"""
    log.info("일일 리셋 실행")
    risk.reset_daily(engine.capital, str(dt.date()))
    add_log("🔄 일일 리셋 완료")
    sync_web()

def _on_market_open(dt):
    """09:00 장 시작"""
    log.info("장 시작 → 매매 시작")
    telegram.send("🔔 장 시작 (09:00) — 매매를 시작합니다.")
    add_log("🔔 장 시작 (09:00)")

def _on_pre_close(dt):
    """15:20 신규 매수 중단"""
    log.info("신규 매수 중단 (15:20)")
    telegram.send("⏰ 15:20 — 신규 매수를 중단합니다.")
    add_log("⏰ 신규 매수 중단 (15:20)")

def _on_market_close(dt):
    """15:30 장 종료 → 전량 청산 + 일일 리포트"""
    log.info("장 종료 → 전량 청산 시작")
    add_log("🏁 장 종료 → 전량 청산")

    # 전량 청산
    positions = engine.position_mgr.get_all()
    for ticker, pos in positions.items():
        engine.force_sell(ticker)
        add_log("🔴 강제청산: " + ticker)

    # 일일 리포트 전송
    s = engine.status()
    telegram.send_daily_report(
        date        = str(dt.date()),
        total_asset = s["total_asset"],
        pnl         = s["pnl"],
        pnl_rate    = s["pnl_rate"],
        buy_count   = s["buy_count"],
        sell_count  = s["sell_count"],
        win_count   = max(0, s["sell_count"] - 1),
        lose_count  = 1,
    )
    sync_web()
    log.info("일일 리포트 전송 완료")


# ── 웹 상태 동기화 ───────────────────────────
def sync_web():
    s = engine.status()
    r = risk.status()
    sch = scheduler.status()
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
        "scheduler": {
            "is_trading_day": sch["is_trading_day"],
            "market_opened":  sch["market_opened"],
            "pre_closed":     sch["pre_closed"],
            "market_closed":  sch["market_closed"],
        },
        "risk": {
            "blocked":          r.get("blocked",          False),
            "block_reason":     r.get("block_reason",     ""),
            "daily_pnl":        r.get("daily_pnl",        0),
            "daily_pnl_rate":   r.get("daily_pnl_rate",   0.0),
            "daily_trades":     r.get("daily_trades",     0),
            "consecutive_loss": r.get("consecutive_loss", 0),
        },
    })


# ── 메인 루프 ────────────────────────────────
def main():
    global _running

    init()

    log.info("메인 루프 대기 중... (장 시작 대기)")
    log.info("Ctrl+C 로 종료")

    sync_count = 0
    while _running:
        time.sleep(1)
        sync_count += 1
        # 10초마다 웹 상태 동기화
        if sync_count % 10 == 0:
            sync_web()

    # ── 종료 처리 ────────────────────────────
    log.info("시스템 종료 중...")
    s = engine.status()
    telegram.send_stop(
        total_asset = s["total_asset"],
        pnl         = s["pnl"],
        pnl_rate    = s["pnl_rate"],
    )
    add_log("🏁 시스템 종료")
    sync_web()
    log.info("시스템 종료 완료 ✅")


if __name__ == "__main__":
    main()