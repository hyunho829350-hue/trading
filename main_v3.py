"""
main_v3.py — 키움 API 연동 버전
- 키움 로그인 → 실시간 시세 수신 → 전략 판단 → 주문 실행
- paper / live 모드 지원
"""

import sys
import time
import signal
print("0. 시작 (v3 - 키움 연동)")
sys.path.insert(0, r"C:\trading\app")

from PyQt5.QtWidgets import QApplication

from config                      import Config
from utils.logger                import get_logger
from notify.telegram_bot         import TelegramBot
from risk.risk_manager           import RiskManager
from engine.trade_engine         import TradeEngine
from strategy.combined_strategy  import CombinedStrategy
from scheduler.market_scheduler  import MarketScheduler
from web.app                     import run_server_thread, update_state, add_log
from kiwoom.kiwoom_api           import KiwoomAPI
from kiwoom.realtime_collector   import RealtimeCollector
from kiwoom.order_executor       import KiwoomOrderExecutor

log = get_logger("MAIN")

# ── 전역 객체 ────────────────────────────────
qt_app    = None
kiwoom    = None
collector = None
executor  = None
engine    = None
risk      = None
telegram  = None
scheduler = None
_running  = True


def on_exit(sig, frame):
    global _running
    _running = False
    if collector:
        collector.stop()
    if scheduler:
        scheduler.stop()
    log.info("종료 신호 수신")

signal.signal(signal.SIGINT,  on_exit)
signal.signal(signal.SIGTERM, on_exit)


# ══════════════════════════════════════════════
#  초기화
# ══════════════════════════════════════════════
def init():
    global qt_app, kiwoom, collector, executor
    global engine, risk, telegram, scheduler

    log.info("=" * 60)
    log.info("매매 시스템 초기화 시작 (v3 - 키움 연동)")
    log.info("MODE    = " + Config.MODE)
    log.info("CAPITAL = " + format(Config.INITIAL_CAPITAL, ","))
    log.info("TICKERS = " + str(Config.TICKERS))
    log.info("=" * 60)

    # ── 1. PyQt5 앱 (키움 API 필수) ──────────
    qt_app = QApplication(sys.argv)

    # ── 2. 키움 로그인 ───────────────────────
    kiwoom = KiwoomAPI()
    if not kiwoom.login(timeout_sec=60):
        log.error("키움 로그인 실패! 시스템 종료")
        telegram_quick_send("❌ 키움 로그인 실패! 시스템 종료")
        sys.exit(1)

    server_type = kiwoom.get_server_type()
    accounts    = kiwoom.get_account_list()
    user_name   = kiwoom.get_user_name()
    log.info("서버: " + server_type)
    log.info("계좌: " + str(accounts))
    log.info("사용자: " + user_name)

    # 계좌번호 설정
    account_no = Config.ACCOUNT_NO
    if not account_no and accounts:
        account_no = accounts[0]
        log.info("계좌번호 자동 설정: " + account_no)

    # ── 3. 텔레그램 ──────────────────────────
    telegram = TelegramBot(
        token   = Config.TELEGRAM_TOKEN,
        chat_id = Config.TELEGRAM_CHAT_ID,
        enabled = Config.TELEGRAM_ENABLED,
    )

    # ── 4. 리스크 관리자 ─────────────────────
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

    # ── 5. 매매 엔진 ────────────────────────
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
        log.info("전략 등록: " + ticker)

    # ── 6. 키움 주문 실행기 ──────────────────
    executor = KiwoomOrderExecutor(
        kiwoom_api = kiwoom,
        account_no = account_no,
        mode       = Config.MODE,
    )

    # ── 7. 실시간 수집기 ─────────────────────
    collector = RealtimeCollector(
        kiwoom_api = kiwoom,
        interval   = Config.BAR_INTERVAL,
    )
    collector.on_bar_complete = on_bar_complete
    collector.on_tick         = on_tick_received

    # ── 8. 스케줄러 ──────────────────────────
    scheduler = MarketScheduler()
    scheduler.on_reset(_on_daily_reset)
    scheduler.on_start(_on_market_open)
    scheduler.on_pre_close(_on_pre_close)
    scheduler.on_stop(_on_market_close)
    scheduler.start()

    # ── 9. 웹 대시보드 ──────────────────────
    if Config.WEB_ENABLED:
        run_server_thread(port=Config.WEB_PORT)
        log.info("웹 대시보드: http://localhost:" + str(Config.WEB_PORT))

    # ── 시작 알림 ────────────────────────────
    telegram.send_start(
        capital    = Config.INITIAL_CAPITAL,
        strategies = [s["name"] for s in Config.COMBINED_PARAMS["strategies"]],
    )
    telegram.send(
        "🔌 키움 연결 완료\n"
        "📡 서버: " + server_type + "\n"
        "👤 사용자: " + user_name + "\n"
        "💼 계좌: " + account_no
    )
    add_log("🚀 매매 시스템 시작 (키움 연동)")


def telegram_quick_send(msg):
    """초기화 전 긴급 텔레그램 발송"""
    try:
        bot = TelegramBot(
            token   = Config.TELEGRAM_TOKEN,
            chat_id = Config.TELEGRAM_CHAT_ID,
            enabled = Config.TELEGRAM_ENABLED,
        )
        bot.send(msg)
    except:
        pass


# ══════════════════════════════════════════════
#  실시간 매매 핵심 로직
# ══════════════════════════════════════════════
def on_tick_received(ticker, price, volume):
    """
    틱 수신 시 호출
    - 손절/익절 실시간 체크
    """
    pos = engine.position_mgr.get(ticker)
    if pos is None or pos.get("qty", 0) <= 0:
        return

    avg_price = pos.get("avg_price", 0)
    if avg_price <= 0:
        return

    pnl_rate = (price - avg_price) / avg_price

    # 손절 체크
    if pnl_rate <= -Config.STOP_LOSS:
        log.warning(
            "🔴 손절 발동! " + ticker +
            " pnl=" + str(round(pnl_rate * 100, 2)) + "%"
        )
        execute_sell(ticker, pos["qty"], price, reason="손절")

    # 익절 체크
    elif pnl_rate >= Config.TAKE_PROFIT:
        log.info(
            "🟢 익절 발동! " + ticker +
            " pnl=" + str(round(pnl_rate * 100, 2)) + "%"
        )
        execute_sell(ticker, pos["qty"], price, reason="익절")


def on_bar_complete(ticker, bar):
    """
    봉 완성 시 호출 — 전략 판단 + 주문 실행
    """
    log.info("━" * 40)
    log.info("봉 수신: " + ticker + " " + bar["datetime"])

    # 리스크 체크
    r_status = risk.status()
    if r_status.get("blocked", False):
        log.warning("리스크 차단 중: " + r_status.get("block_reason", ""))
        return

    # 현재 포지션 정보
    pos       = engine.position_mgr.get(ticker)
    position  = pos["qty"]       if pos else 0
    avg_price = pos["avg_price"] if pos else 0

    # 전략 판단
    strategy = engine.get_strategy(ticker)
    if strategy is None:
        log.warning("전략 없음: " + ticker)
        return

    signal = strategy.on_bar(bar, engine.capital, position, avg_price)

    # ── 매수 ─────────────────────────────────
    if signal == "buy":
        # 리스크 매수 가능 여부 확인
        can_buy = risk.can_buy(
            capital     = engine.capital,
            price       = bar["close"],
            position_cnt= engine.position_mgr.count(),
        )
        if not can_buy:
            log.warning("리스크 매수 차단: " + ticker)
            return

        qty = calc_buy_qty(bar["close"])
        if qty > 0:
            execute_buy(ticker, qty, bar["close"])

    # ── 매도 ─────────────────────────────────
    elif signal == "sell" and position > 0:
        execute_sell(ticker, position, bar["close"], reason="전략매도")

    sync_web()


def calc_buy_qty(price):
    """매수 수량 계산 (리스크 반영)"""
    if price <= 0:
        return 0
    max_amount = engine.capital * Config.MAX_PER_STOCK
    qty = int(max_amount / price)
    return qty


def execute_buy(ticker, qty, price):
    """매수 실행"""
    log.info("🟢 매수 실행: " + ticker + " " + str(qty) + "주 @" + str(price))

    # 키움 주문 (paper면 스킵, live면 실제 주문)
    success = executor.buy_market(ticker, qty)

    if success:
        # 엔진에 포지션 반영
        engine.buy(ticker, price, qty)
        risk.record_trade("buy")

        msg = ("🟢 매수 체결\n"
               "종목: " + ticker + "\n"
               "수량: " + str(qty) + "주\n"
               "가격: " + format(price, ",") + "원\n"
               "금액: " + format(price * qty, ",") + "원")
        telegram.send(msg)
        add_log("🟢 매수: " + ticker + " " + str(qty) + "주")
    else:
        log.error("매수 실패: " + ticker)
        telegram.send("❌ 매수 실패: " + ticker)


def execute_sell(ticker, qty, price, reason=""):
    """매도 실행"""
    log.info(
        "🔴 매도 실행: " + ticker +
        " " + str(qty) + "주 @" + str(price) +
        " (" + reason + ")"
    )

    success = executor.sell_market(ticker, qty)

    if success:
        # 엔진에 포지션 반영
        pnl = engine.sell(ticker, price, qty)
        risk.record_trade("sell", pnl=pnl)

        msg = ("🔴 매도 체결 (" + reason + ")\n"
               "종목: " + ticker + "\n"
               "수량: " + str(qty) + "주\n"
               "가격: " + format(price, ",") + "원\n"
               "손익: " + format(pnl, ",") + "원")
        telegram.send(msg)
        add_log("🔴 매도: " + ticker + " (" + reason + ")")
    else:
        log.error("매도 실패: " + ticker)
        telegram.send("❌ 매도 실패: " + ticker + " (" + reason + ")")


# ══════════════════════════════════════════════
#  스케줄러 콜백
# ══════════════════════════════════════════════
def _on_daily_reset(dt):
    """08:50 일일 리셋"""
    log.info("일일 리셋 실행")
    risk.reset_daily(engine.capital, str(dt.date()))
    add_log("🔄 일일 리셋 완료")
    sync_web()

def _on_market_open(dt):
    """09:00 장 시작 → 실시간 수집 시작"""
    log.info("장 시작 → 실시간 수집 시작")
    collector.start(Config.TICKERS)
    telegram.send("🔔 장 시작 (09:00) — 실시간 매매 시작")
    add_log("🔔 장 시작 → 실시간 수집 ON")

def _on_pre_close(dt):
    """15:20 신규 매수 중단"""
    log.info("신규 매수 중단 (15:20)")
    risk.block("15:20 매수 중단")
    telegram.send("⏰ 15:20 — 신규 매수를 중단합니다.")
    add_log("⏰ 신규 매수 중단 (15:20)")

def _on_market_close(dt):
    """15:30 장 종료 → 실시간 중지 + 전량 청산"""
    log.info("장 종료 → 전량 청산 시작")

    # 실시간 수집 중지
    collector.force_complete_all()
    collector.stop()

    # 전량 청산
    positions = engine.position_mgr.get_all()
    for ticker, pos in positions.items():
        if pos.get("qty", 0) > 0:
            current_bar = collector.get_current_bar(ticker)
            price = current_bar["close"] if current_bar else pos.get("avg_price", 0)
            execute_sell(ticker, pos["qty"], price, reason="장종료청산")

    # 일일 리포트
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
    add_log("🏁 장 종료 → 전량 청산 완료")
    sync_web()


# ══════════════════════════════════════════════
#  웹 상태 동기화
# ══════════════════════════════════════════════
def sync_web():
    s   = engine.status()
    r   = risk.status()
    sch = scheduler.status()
    col = collector.get_status() if collector else {}
    exe = executor.get_status()  if executor  else {}

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
        "collector": {
            "running":  col.get("running",  False),
            "tickers":  col.get("tickers",  []),
            "interval": col.get("interval", 0),
        },
        "executor": {
            "mode":        exe.get("mode",        ""),
            "order_count": exe.get("order_count", 0),
            "connected":   exe.get("connected",   False),
        },
    })


# ══════════════════════════════════════════════
#  메인 루프
# ══════════════════════════════════════════════
def main():
    global _running

    init()

    log.info("메인 루프 시작 (PyQt5 이벤트 루프)")
    log.info("Ctrl+C 로 종료")

    # PyQt5 타이머로 주기적 작업 실행
    from PyQt5.QtCore import QTimer

    # 10초마다 웹 동기화
    sync_timer = QTimer()
    sync_timer.timeout.connect(sync_web)
    sync_timer.start(10_000)

    # 1초마다 종료 체크
    def check_exit():
        if not _running:
            log.info("시스템 종료 중...")
            if collector:
                collector.stop()

            s = engine.status()
            telegram.send_stop(
                total_asset = s["total_asset"],
                pnl         = s["pnl"],
                pnl_rate    = s["pnl_rate"],
            )
            add_log("🏁 시스템 종료")
            sync_web()
            log.info("시스템 종료 완료 ✅")
            qt_app.quit()

    exit_timer = QTimer()
    exit_timer.timeout.connect(check_exit)
    exit_timer.start(1_000)

    # PyQt5 이벤트 루프 실행 (키움 API 이벤트 처리)
    sys.exit(qt_app.exec_())


if __name__ == "__main__":
    main()