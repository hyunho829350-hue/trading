"""
운영 통합 메인 (최종 버전)
- 모든 모듈 통합
- 자동 복구 + 모니터링 + 성과 추적
- paper / live 자동 선택

실행:
    py -3.10-32 app\main_prod.py              # config.py의 MODE 사용
    py -3.10-32 app\main_prod.py --paper      # 강제 paper
    py -3.10-32 app\main_prod.py --live       # 강제 live
"""

import sys
import time
import signal
import argparse
sys.path.insert(0, r"C:\trading\app")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from utils.logger import get_logger

log = get_logger("PROD")

# ── 전역 객체 ────────────────────────────────
qt_app     = None
kiwoom     = None
collector  = None
executor   = None
engine     = None
risk       = None
telegram   = None
scheduler  = None
recorder   = None
guard      = None
ai_client  = None
monitor    = None
recovery   = None
tracker    = None
reporter   = None
_running   = True
_config    = None


def on_exit(sig, frame):
    global _running
    _running = False
    log.info("종료 신호 수신")

signal.signal(signal.SIGINT,  on_exit)
signal.signal(signal.SIGTERM, on_exit)


def init(mode=None):
    global qt_app, kiwoom, collector, executor
    global engine, risk, telegram, scheduler
    global recorder, guard, ai_client
    global monitor, recovery, tracker, reporter
    global _config

    # ── 설정 로드 ────────────────────────────
    if mode == "live":
        from config_live import LiveConfig as Cfg
    elif mode == "paper":
        from config_paper import PaperConfig as Cfg
    else:
        from config import Config as Cfg
    _config = Cfg

    actual_mode = Cfg.MODE

    log.info("=" * 60)
    log.info("🚀 운영 시스템 시작 (Production)")
    log.info("MODE    = " + actual_mode)
    log.info("CAPITAL = " + format(Cfg.INITIAL_CAPITAL, ","))
    log.info("TICKERS = " + str(Cfg.TICKERS))
    log.info("=" * 60)

    # ── 1. PyQt5 ────────────��────────────────
    qt_app = QApplication(sys.argv)

    # ── 2. 키움 ──────────────────────────────
    from kiwoom.kiwoom_api import KiwoomAPI
    kiwoom = KiwoomAPI()
    if not kiwoom.login(timeout_sec=60):
        log.error("키움 로그인 실패!")
        sys.exit(1)

    server_type = kiwoom.get_server_type()
    account_no  = Cfg.ACCOUNT_NO or kiwoom.get_account_list()[0]
    log.info("서버: " + server_type + " / 계좌: " + account_no)

    # ── 3. 텔레그램 ─────────────────────────
    from notify.telegram_bot import TelegramBot
    telegram = TelegramBot(
        token=Cfg.TELEGRAM_TOKEN, chat_id=Cfg.TELEGRAM_CHAT_ID,
        enabled=Cfg.TELEGRAM_ENABLED,
    )

    # ── 4. 시스템 모니터 ─────────────────────
    from utils.system_monitor import SystemMonitor
    monitor = SystemMonitor(alert_callback=lambda msg: telegram.send(msg))
    monitor.start_background(interval=60)

    # ── 5. 자��� 복구 ────────────────────────
    from engine.auto_recovery import AutoRecovery
    recovery = AutoRecovery(kiwoom, telegram, max_retry=3)
    recovery.on_safe_mode = lambda reason: risk.block(reason) if risk else None
    recovery.on_reconnected = _on_reconnected
    recovery.start(interval=60)

    # ── 6. 안전 장치 ────────────────────────
    from engine.safety_guard import SafetyGuard
    guard = SafetyGuard(Cfg)

    # ── 7. 기록기 ────────────────────────────
    from engine.paper_recorder import PaperRecorder
    log_dir = getattr(Cfg, "LIVE_LOG_DIR", None) or \
              getattr(Cfg, "PAPER_LOG_DIR", r"C:\trading\data\paper")
    recorder = PaperRecorder(log_dir=log_dir)

    # ── 8. 성과 추적기 ──────────────────────
    from engine.performance_tracker import PerformanceTracker
    tracker = PerformanceTracker()

    # ── 9. 리포트 생성기 ─────────────────────
    from notify.report_generator import ReportGenerator
    reporter = ReportGenerator(tracker, telegram)

    # ── 10. 리스크 ───────────────────────────
    from risk.risk_manager import RiskManager
    risk = RiskManager(
        total_capital=Cfg.INITIAL_CAPITAL, max_per_stock=Cfg.MAX_PER_STOCK,
        stop_loss=Cfg.STOP_LOSS, take_profit=Cfg.TAKE_PROFIT,
        max_daily_loss=Cfg.MAX_DAILY_LOSS, max_stocks=Cfg.MAX_STOCKS,
        max_consecutive_loss=Cfg.MAX_CONSECUTIVE_LOSS,
        max_daily_trades=Cfg.MAX_DAILY_TRADES,
    )

    # ── 11. 매매 엔진 ───────────────────────
    from engine.trade_engine import TradeEngine
    engine = TradeEngine(
        capital=Cfg.INITIAL_CAPITAL, mode=actual_mode,
        max_position_ratio=Cfg.MAX_PER_STOCK, max_positions=Cfg.MAX_STOCKS,
    )

    from strategy.combined_strategy import CombinedStrategy
    for ticker in Cfg.TICKERS:
        strategy = CombinedStrategy(params=Cfg.COMBINED_PARAMS)
        engine.add_strategy(ticker, strategy)

    # ── 12. 주문 실행기 ─────────────────────
    from kiwoom.order_executor import KiwoomOrderExecutor
    executor = KiwoomOrderExecutor(kiwoom, account_no, mode=actual_mode)

    # ── 13. 실시간 수집기 ────────────────────
    from kiwoom.realtime_collector import RealtimeCollector
    collector = RealtimeCollector(kiwoom, interval=Cfg.BAR_INTERVAL)
    collector.on_bar_complete = on_bar_complete
    collector.on_tick = on_tick_received

    # ── 14. AI ───────────────────────────────
    ai_enabled = getattr(Cfg, "AI_ENABLED", False)
    if ai_enabled:
        try:
            from ai.ai_client import AIClient
            ai_client = AIClient()
            if not ai_client.is_available():
                ai_client = None
        except:
            ai_client = None

    # ── 15. 스케줄러 ────────────────────────
    from scheduler.market_scheduler import MarketScheduler
    scheduler = MarketScheduler()
    scheduler.on_reset(_on_daily_reset)
    scheduler.on_start(_on_market_open)
    scheduler.on_pre_close(_on_pre_close)
    scheduler.on_stop(_on_market_close)
    scheduler.start()

    # ── 16. 웹 대시보드 ─────────────────────
    if Cfg.WEB_ENABLED:
        from web.app import run_server_thread
        run_server_thread(port=Cfg.WEB_PORT)

    # ── 시작 알림 ────────────────────────────
    mode_emoji = "🔴" if actual_mode == "live" else "📝"
    telegram.send(
        mode_emoji + " 운영 시스템 시작\n"
        "━━━━━━━━━━━━━━\n"
        "모드: " + actual_mode.upper() + "\n"
        "서버: " + server_type + "\n"
        "자본: " + format(Cfg.INITIAL_CAPITAL, ",") + "원\n"
        "종목: " + str(Cfg.TICKERS) + "\n"
        "AI: " + ("ON" if ai_client else "OFF") + "\n"
        "모니터: ON / 자동복구: ON"
    )


def _on_reconnected():
    """재연결 후 실시간 재등록"""
    if collector and scheduler:
        sch = scheduler.status()
        if sch.get("market_opened") and not sch.get("market_closed"):
            collector.start(_config.TICKERS)
            log.info("재연결 → 실시간 재등록")


# ══════════════════════════════════════════════
#  매매 로직
# ══════════════════════════════════════════════

def on_tick_received(ticker, price, volume):
    """틱 → 손절/익절"""
    try:
        recovery.heartbeat()

        pos = engine.position_mgr.get(ticker)
        if pos is None or pos.get("qty", 0) <= 0:
            return

        avg_price = pos.get("avg_price", 0)
        if avg_price <= 0:
            return

        pnl_rate = (price - avg_price) / avg_price

        if pnl_rate <= -_config.STOP_LOSS:
            execute_sell(ticker, pos["qty"], price, "손절")
        elif pnl_rate >= _config.TAKE_PROFIT:
            execute_sell(ticker, pos["qty"], price, "익절")
    except Exception as e:
        recovery.record_error("틱 처리: " + str(e))


def on_bar_complete(ticker, bar):
    """봉 → 전략+AI → 매매"""
    try:
        recovery.heartbeat()
        recorder.record_bar(ticker, bar)

        if recovery.is_safe_mode():
            return
        if risk.status().get("blocked", False):
            return
        if guard.status()["emergency"]:
            return

        pos = engine.position_mgr.get(ticker)
        position = pos["qty"] if pos else 0
        avg_price = pos["avg_price"] if pos else 0

        strategy = engine.get_strategy(ticker)
        if strategy is None:
            return

        final_signal = strategy.on_bar(bar, engine.capital, position, avg_price)

        # AI
        if ai_client:
            try:
                features = [0.0] * 24
                features[13] = (bar["close"] - bar["open"]) / bar["close"] if bar["close"] > 0 else 0
                features[11] = 1.0
                ai_result = ai_client.predict(features)
                ai_conf = getattr(_config, "AI_MIN_CONF", 0.5)
                if ai_result.get("confidence", 0) >= ai_conf:
                    from ai.brain import AIBrain
                    brain = AIBrain(use_lstm=False)
                    ai_weight = getattr(_config, "AI_WEIGHT", 0.3)
                    final_signal = brain.combine_with_strategy(
                        final_signal, ai_result, ai_weight=ai_weight
                    )
            except:
                pass

        recorder.record_signal(ticker, final_signal)

        # 매수
        if final_signal == "buy" and position == 0:
            if risk.can_buy(capital=engine.capital, price=bar["close"],
                           position_cnt=engine.position_mgr.count()):
                qty = int(engine.capital * _config.MAX_PER_STOCK / bar["close"])
                if qty > 0:
                    can, reason = guard.check_buy(ticker, bar["close"], qty)
                    if can:
                        execute_buy(ticker, qty, bar["close"])

        # 매도
        elif final_signal == "sell" and position > 0:
            can, reason = guard.check_sell(ticker, bar["close"], position)
            if can:
                execute_sell(ticker, position, bar["close"], "전략매도")

        sync_web()
    except Exception as e:
        recovery.record_error("봉 처리: " + str(e))


def execute_buy(ticker, qty, price):
    success = executor.buy_market(ticker, qty)
    if success:
        engine.buy(ticker, price, qty)
        risk.record_trade("buy")
        guard.record_order(price * qty)
        recorder.record_trade(ticker, "BUY", price, qty,
                             amount=price*qty, fee=price*qty*0.00015)
        telegram.send("🟢 매수: " + ticker + " " + str(qty) +
                      "주 @" + format(price, ","))
        from web.app import add_log
        add_log("🟢 매수: " + ticker)


def execute_sell(ticker, qty, price, reason=""):
    pos = engine.position_mgr.get(ticker)
    avg = pos.get("avg_price", 0) if pos else 0

    success = executor.sell_market(ticker, qty)
    if success:
        pnl = engine.sell(ticker, price, qty)
        risk.record_trade("sell", pnl=pnl)
        guard.record_pnl(pnl)
        pnl_rate = ((price - avg) / avg * 100) if avg > 0 else 0
        recorder.record_trade(ticker, "SELL", price, qty,
                             amount=price*qty, pnl=pnl,
                             pnl_rate=pnl_rate, reason=reason)
        emoji = "🟢" if pnl > 0 else "🔴"
        telegram.send(emoji + " 매도(" + reason + "): " + ticker +
                      " " + format(pnl, ",") + "원")
        from web.app import add_log
        add_log(emoji + " 매도: " + ticker)


# ══════════════════════════════════════════════
#  스케줄러 콜백
# ══════════════════════════════════════════════

def _on_daily_reset(dt):
    risk.reset_daily(engine.capital, str(dt.date()))
    guard.reset_daily()
    recovery.reset_errors()

def _on_market_open(dt):
    collector.start(_config.TICKERS)
    telegram.send("🔔 장 시작 — 매매 시작")

def _on_pre_close(dt):
    risk.block("15:20 매수 중단")

def _on_market_close(dt):
    collector.force_complete_all()
    collector.stop()

    # 전량 청산
    positions = engine.position_mgr.get_all()
    for ticker, pos in positions.items():
        if pos.get("qty", 0) > 0:
            current = collector.get_current_bar(ticker)
            price = current["close"] if current else pos.get("avg_price", 0)
            execute_sell(ticker, pos["qty"], price, "장종료청산")

    recorder.save()

    # 성과 기록
    s = engine.status()
    pnl = s["total_asset"] - _config.INITIAL_CAPITAL
    tracker.record_day(
        date=str(dt.date()),
        capital=s["total_asset"],
        pnl=round(pnl),
        trade_count=recorder.stats["total_trades"],
        win_count=recorder.stats["win_count"],
        lose_count=recorder.stats["lose_count"],
    )

    # 리포트
    reporter.daily_report(
        str(dt.date()), round(pnl), s["total_asset"],
        recorder.stats["total_trades"], recorder.stats["win_count"],
    )

    # 주간 리포트 (금요��)
    if dt.weekday() == 4:
        reporter.weekly_report()

    # 월간 리포트 (월말)
    tomorrow = dt + __import__("datetime").timedelta(days=1)
    if tomorrow.month != dt.month:
        reporter.monthly_report()

    sync_web()


# ══════════════════════════════════════════════
#  웹 동기화
# ══════════════════════════════════════════════

def sync_web():
    try:
        from web.app import update_state
        s = engine.status()
        update_state({
            "mode":           _config.MODE.upper(),
            "capital":        s["capital"],
            "eval_value":     s["eval_value"],
            "total_asset":    s["total_asset"],
            "initial_capital":_config.INITIAL_CAPITAL,
            "pnl":            s["pnl"],
            "pnl_rate":       s["pnl_rate"],
            "buy_count":      s["buy_count"],
            "sell_count":     s["sell_count"],
            "positions":      s["positions"],
            "risk":           risk.status(),
            "safety":         guard.status(),
            "recovery":       recovery.status(),
            "monitor":        monitor.check() if monitor else {},
            "ai_enabled":     ai_client is not None,
        })
    except:
        pass


# ══════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════

def main():
    global _running

    parser = argparse.ArgumentParser()
    parser.add_argument("--paper", action="store_true")
    parser.add_argument("--live",  action="store_true")
    args = parser.parse_args()

    mode = None
    if args.live:
        mode = "live"
        confirm = input("⚠️ 실전 투자입니다. 계속? (yes): ")
        if confirm.strip().lower() != "yes":
            print("취소")
            sys.exit(0)
    elif args.paper:
        mode = "paper"

    init(mode)

    sync_timer = QTimer()
    sync_timer.timeout.connect(sync_web)
    sync_timer.start(10_000)

    save_timer = QTimer()
    save_timer.timeout.connect(lambda: recorder.save() if recorder else None)
    save_timer.start(300_000)

    def check_exit():
        if not _running:
            if collector:
                collector.stop()
            if recorder:
                recorder.save()
            if monitor:
                monitor.stop_background()
            if recovery:
                recovery.stop()

            s = engine.status()
            telegram.send("🏁 시스템 종료\n자산: " +
                         format(s["total_asset"], ",") + "원")
            qt_app.quit()

    exit_timer = QTimer()
    exit_timer.timeout.connect(check_exit)
    exit_timer.start(1_000)

    sys.exit(qt_app.exec_())


if __name__ == "__main__":
    main()