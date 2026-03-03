"""
실전 투자 메인
- 키움 실서버 연결
- 실시간 시세 → 전략+AI → 실제 주문
- 다중 안전 장치 적용
- 전 과정 기록

⚠️ 실제 돈이 투입됩니다!

실행: py -3.10-32 app/main_live.py
"""

import sys
import time
import signal
print("⚠️  실전 투자 시작")
sys.path.insert(0, r"C:\trading\app")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from config_live                 import LiveConfig as Config
from utils.logger                import get_logger
from notify.telegram_bot         import TelegramBot
from risk.risk_manager           import RiskManager
from engine.trade_engine         import TradeEngine
from engine.paper_recorder       import PaperRecorder
from engine.safety_guard         import SafetyGuard
from strategy.combined_strategy  import CombinedStrategy
from scheduler.market_scheduler  import MarketScheduler
from web.app                     import run_server_thread, update_state, add_log
from kiwoom.kiwoom_api           import KiwoomAPI
from kiwoom.realtime_collector   import RealtimeCollector
from kiwoom.order_executor       import KiwoomOrderExecutor

log = get_logger("LIVE")

# ── 전역 객체 ────────────────────────────────
qt_app    = None
kiwoom    = None
collector = None
executor  = None
engine    = None
risk      = None
telegram  = None
scheduler = None
recorder  = None
guard     = None
ai_client = None
_running  = True


def on_exit(sig, frame):
    global _running
    _running = False
    log.info("종료 신호 수신")

signal.signal(signal.SIGINT,  on_exit)
signal.signal(signal.SIGTERM, on_exit)


# ══════════════════════════════════════════════
#  초기화
# ══════════════════════════════════════════════
def init():
    global qt_app, kiwoom, collector, executor
    global engine, risk, telegram, scheduler
    global recorder, guard, ai_client

    log.info("=" * 60)
    log.info("⚠️  실전 투자 시스템 초기화")
    log.info("MODE    = " + Config.MODE)
    log.info("CAPITAL = " + format(Config.INITIAL_CAPITAL, ","))
    log.info("=" * 60)

    # ── 실전 전환 검증 ───────────────────────
    _verify_live_readiness()

    # ── 1. PyQt5 ─────────────────────────────
    qt_app = QApplication(sys.argv)

    # ── 2. 키움 로그인 ───────────────────────
    kiwoom = KiwoomAPI()
    if not kiwoom.login(timeout_sec=60):
        log.error("키움 로그인 실패!")
        sys.exit(1)

    server_type = kiwoom.get_server_type()
    account_no  = Config.ACCOUNT_NO or kiwoom.get_account_list()[0]

    # 실서버 확인
    if "모의" in server_type:
        log.warning("⚠️  모의서버 연결됨! 실서버가 아닙니다.")
    else:
        log.info("✅ 실서버 연결: " + account_no)

    # ── 3. 텔레그램 ─────────────────────────
    telegram = TelegramBot(
        token   = Config.TELEGRAM_TOKEN,
        chat_id = Config.TELEGRAM_CHAT_ID,
        enabled = Config.TELEGRAM_ENABLED,
    )

    # ── 4. 안전 장치 ────────────────────────
    guard = SafetyGuard(Config)

    # ── 5. 기록기 ────────────────────────────
    recorder = PaperRecorder(log_dir=Config.LIVE_LOG_DIR)

    # ── 6. 리스크 ────────────────────────────
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

    # ── 7. 매매 엔진 ────────────────────────
    engine = TradeEngine(
        capital            = Config.INITIAL_CAPITAL,
        mode               = "live",
        max_position_ratio = Config.MAX_PER_STOCK,
        max_positions      = Config.MAX_STOCKS,
    )

    for ticker in Config.TICKERS:
        strategy = CombinedStrategy(params=Config.COMBINED_PARAMS)
        engine.add_strategy(ticker, strategy)

    # ── 8. 주문 실행기 (LIVE) ────────────────
    executor = KiwoomOrderExecutor(
        kiwoom_api = kiwoom,
        account_no = account_no,
        mode       = "live",
    )

    # ── 9. 실시간 수집기 ─────────────────────
    collector = RealtimeCollector(
        kiwoom_api = kiwoom,
        interval   = Config.BAR_INTERVAL,
    )
    collector.on_bar_complete = on_bar_complete
    collector.on_tick         = on_tick_received

    # ── 10. AI ───────────────────────────────
    if Config.AI_ENABLED:
        try:
            from ai.ai_client import AIClient
            ai_client = AIClient()
            if ai_client.is_available():
                log.info("AI 활성화")
            else:
                ai_client = None
        except:
            ai_client = None

    # ── 11. 스케줄러 ──────────���──────────────
    scheduler = MarketScheduler()
    scheduler.on_reset(_on_daily_reset)
    scheduler.on_start(_on_market_open)
    scheduler.on_pre_close(_on_pre_close)
    scheduler.on_stop(_on_market_close)
    scheduler.start()

    # ── 12. 웹 대시보드 ─────────────────────
    if Config.WEB_ENABLED:
        run_server_thread(port=Config.WEB_PORT)

    # ── 시작 알림 ────────────────────────────
    telegram.send(
        "🔴 실전 투자 시작\n"
        "━━━━━━━━━━━━━━\n"
        "서버: " + server_type + "\n"
        "계좌: " + account_no + "\n"
        "자본: " + format(Config.INITIAL_CAPITAL, ",") + "원\n"
        "종목: " + str(Config.TICKERS) + "\n"
        "AI: " + ("ON" if ai_client else "OFF") + "\n"
        "안전장치: ON\n"
        "━━━━━━━━━━━━━━\n"
        "⚠️ 실제 주문이 실행됩니다!"
    )
    add_log("🔴 실전 투자 시작")


def _verify_live_readiness():
    """실전 전환 전 검증"""
    try:
        from engine.paper_validator import PaperValidator
        validator = PaperValidator()
        result = validator.is_ready_for_live()

        if not result["ready"]:
            log.warning("=" * 50)
            log.warning("⚠️  모의투자 검증 미통과!")
            log.warning("실패 항목:")
            for f in result["failed"]:
                log.warning("  ❌ " + f)
            log.warning("=" * 50)
            log.warning("⚠️  검증 미통과 상태로 실전 진행합니다.")
            log.warning("    (강제 실행 중 — 주의하세요!)")
        else:
            log.info("✅ 모의투자 검증 통과!")
    except Exception as e:
        log.warning("모의투자 검증 스킵: " + str(e))


# ══════════════════════════════════════════════
#  실시간 매매
# ══════════════════════════════════════════════

def on_tick_received(ticker, price, volume):
    """틱 → 손절/익절"""
    pos = engine.position_mgr.get(ticker)
    if pos is None or pos.get("qty", 0) <= 0:
        return

    avg_price = pos.get("avg_price", 0)
    if avg_price <= 0:
        return

    pnl_rate = (price - avg_price) / avg_price

    if pnl_rate <= -Config.STOP_LOSS:
        log.warning("🔴 손절: " + ticker)
        execute_sell(ticker, pos["qty"], price, reason="손절")

    elif pnl_rate >= Config.TAKE_PROFIT:
        log.info("🟢 익절: " + ticker)
        execute_sell(ticker, pos["qty"], price, reason="익절")


def on_bar_complete(ticker, bar):
    """봉 완성 → 전략+AI → 주문"""

    recorder.record_bar(ticker, bar)

    # 긴급 중단 체크
    if guard and guard.status()["emergency"]:
        log.warning("긴급 중단 상태 — 매매 스킵")
        return

    # 리스크 체크
    r_status = risk.status()
    if r_status.get("blocked", False):
        return

    # 포지션
    pos       = engine.position_mgr.get(ticker)
    position  = pos["qty"]       if pos else 0
    avg_price = pos["avg_price"] if pos else 0

    # 전략 판단
    strategy = engine.get_strategy(ticker)
    if strategy is None:
        return

    strategy_signal = strategy.on_bar(bar, engine.capital, position, avg_price)

    # AI 결합
    final_signal = strategy_signal
    if ai_client and Config.AI_ENABLED:
        try:
            features = _build_live_features(bar)
            if features:
                ai_result = ai_client.predict(features)
                recorder.record_ai_signal(ticker, ai_result, strategy_signal)

                if ai_result.get("confidence", 0) >= Config.AI_MIN_CONF:
                    from ai.brain import AIBrain
                    brain = AIBrain(use_lstm=False)
                    final_signal = brain.combine_with_strategy(
                        strategy_signal, ai_result,
                        ai_weight=Config.AI_WEIGHT
                    )
        except:
            pass

    recorder.record_signal(ticker, final_signal)

    # ── 매수 ─────────────────────────────────
    if final_signal == "buy" and position == 0:
        can_risk = risk.can_buy(
            capital      = engine.capital,
            price        = bar["close"],
            position_cnt = engine.position_mgr.count(),
        )
        if not can_risk:
            return

        qty = int(engine.capital * Config.MAX_PER_STOCK / bar["close"])
        if qty > 0:
            # 안전 장치 검증
            can_safe, reason = guard.check_buy(ticker, bar["close"], qty)
            if can_safe:
                execute_buy(ticker, qty, bar["close"])
            else:
                log.warning("안전장치 차단: " + reason)
                recorder.record_signal(ticker, "BLOCKED:" + reason)

    # ── 매도 ─────────────────────────────────
    elif final_signal == "sell" and position > 0:
        can_safe, reason = guard.check_sell(ticker, bar["close"], position)
        if can_safe:
            execute_sell(ticker, position, bar["close"], reason="전략매도")

    sync_web()


def _build_live_features(bar):
    """간이 특징 생성"""
    try:
        c = bar["close"]
        if c <= 0:
            return None
        features = [0.0] * 24
        features[13] = (c - bar["open"]) / c if c > 0 else 0
        features[11] = 1.0
        return features
    except:
        return None


def execute_buy(ticker, qty, price):
    """실전 매수"""
    amount = price * qty
    log.info("🔴 실전 매수: " + ticker + " " + str(qty) +
             "주 @" + format(price, ","))

    success = executor.buy_market(ticker, qty)
    if success:
        engine.buy(ticker, price, qty)
        risk.record_trade("buy")
        guard.record_order(amount)

        fee = amount * 0.00015
        recorder.record_trade(
            ticker, "BUY", price, qty,
            amount=amount, fee=fee, reason="전략매수"
        )

        telegram.send(
            "🔴 [실전] 매수 체결\n"
            "종목: " + ticker + "\n"
            "수량: " + str(qty) + "주\n"
            "가격: " + format(price, ",") + "원\n"
            "금액: " + format(amount, ",") + "원"
        )
        add_log("🔴 실전 매수: " + ticker)
    else:
        log.error("매수 실패: " + ticker)
        telegram.send("❌ [실전] 매수 실패: " + ticker)


def execute_sell(ticker, qty, price, reason=""):
    """실전 매도"""
    pos = engine.position_mgr.get(ticker)
    avg_price = pos.get("avg_price", 0) if pos else 0

    log.info("🔴 실전 매도: " + ticker + " (" + reason + ")")

    success = executor.sell_market(ticker, qty)
    if success:
        pnl = engine.sell(ticker, price, qty)
        risk.record_trade("sell", pnl=pnl)
        guard.record_pnl(pnl)

        amount = price * qty
        fee = amount * 0.00015
        tax = amount * 0.0018
        pnl_rate = ((price - avg_price) / avg_price * 100) if avg_price > 0 else 0

        recorder.record_trade(
            ticker, "SELL", price, qty,
            amount=amount, fee=fee, tax=tax,
            pnl=pnl, pnl_rate=pnl_rate, reason=reason,
        )

        emoji = "🟢" if pnl > 0 else "🔴"
        telegram.send(
            emoji + " [실전] 매도 (" + reason + ")\n"
            "종목: " + ticker + "\n"
            "수량: " + str(qty) + "주\n"
            "가격: " + format(price, ",") + "원\n"
            "손익: " + format(pnl, ",") + "원 (" +
            str(round(pnl_rate, 2)) + "%)"
        )
        add_log("🔴 실전 매도: " + ticker + " " + format(pnl, ",") + "원")
    else:
        log.error("매도 실패: " + ticker)
        telegram.send("❌ [실전] 매도 실패: " + ticker)


# ══════════════════════════════════════════════
#  스케줄러 콜백
# ══════════════════════════════════════════════

def _on_daily_reset(dt):
    log.info("일일 리셋")
    risk.reset_daily(engine.capital, str(dt.date()))
    guard.reset_daily()

def _on_market_open(dt):
    log.info("장 시작")
    collector.start(Config.TICKERS)
    telegram.send("🔴 [실전] 장 시작 — 매매 시작")

def _on_pre_close(dt):
    log.info("매수 중단")
    risk.block("15:20 매수 중단")
    telegram.send("🔴 [실전] 15:20 매수 중단")

def _on_market_close(dt):
    log.info("장 종료 → 전량 청산")

    collector.force_complete_all()
    collector.stop()

    positions = engine.position_mgr.get_all()
    for ticker, pos in positions.items():
        if pos.get("qty", 0) > 0:
            current = collector.get_current_bar(ticker)
            price = current["close"] if current else pos.get("avg_price", 0)
            execute_sell(ticker, pos["qty"], price, reason="장종료청산")

    # 기록 저장
    recorder.save()

    s = engine.status()
    recorder.record_equity(
        s["capital"], s["eval_value"], s["total_asset"], s["positions"]
    )

    summary = recorder.generate_daily_summary(
        Config.INITIAL_CAPITAL, s["total_asset"]
    )
    recorder.print_summary()

    pnl = s["total_asset"] - Config.INITIAL_CAPITAL
    pnl_rate = (pnl / Config.INITIAL_CAPITAL * 100)

    telegram.send(
        "🔴 [실전] 일일 리포트\n"
        "━━━━━━━━━━━━━━\n"
        "자산: " + format(s["total_asset"], ",") + "원\n"
        "손익: " + format(round(pnl), ",") + "원 (" +
        str(round(pnl_rate, 2)) + "%)\n"
        "매매: " + str(recorder.stats["total_trades"]) + "회\n"
        "승률: " + str(summary.get("win_rate", 0)) + "%\n"
        "안전장치: " + str(guard.status())
    )


# ══════════════════════════════════════════════
#  웹 동기화
# ══════════════════════════════════════════════

def sync_web():
    try:
        s = engine.status()
        r = risk.status()
        g = guard.status()

        update_state({
            "mode":            "🔴 LIVE",
            "capital":         s["capital"],
            "eval_value":      s["eval_value"],
            "total_asset":     s["total_asset"],
            "initial_capital": Config.INITIAL_CAPITAL,
            "pnl":             s["pnl"],
            "pnl_rate":        s["pnl_rate"],
            "buy_count":       s["buy_count"],
            "sell_count":      s["sell_count"],
            "positions":       s["positions"],
            "risk":            r,
            "safety":          g,
            "ai_enabled":      ai_client is not None,
        })
    except:
        pass


# ══════════════════════════════════════════════
#  메인 루프
# ══════════════════════════════════════════════

def main():
    global _running

    # ── 최종 확인 ────────────────────────────
    print()
    print("⚠️" * 20)
    print("  실전 투자를 시작합니다!")
    print("  실제 돈이 투입됩니다!")
    print("⚠️" * 20)
    print()

    confirm = input("계속 하시겠습니까? (yes 입력): ")
    if confirm.strip().lower() != "yes":
        print("취소됨")
        sys.exit(0)

    init()

    log.info("실전 메인 루프 시작")

    # 주기적 저장
    save_timer = QTimer()
    save_timer.timeout.connect(lambda: recorder.save())
    save_timer.start(300_000)  # 5분

    # 웹 동기화
    sync_timer = QTimer()
    sync_timer.timeout.connect(sync_web)
    sync_timer.start(5_000)  # 5초

    # 긴급 중단 모니터
    def check_safety():
        g = guard.status()
        if g["emergency"] and not _running:
            log.error("긴급 중단 + 종료 신호 → 전량 청산")
            _force_sell_all()

    safety_timer = QTimer()
    safety_timer.timeout.connect(check_safety)
    safety_timer.start(3_000)

    # 종료 체크
    def check_exit():
        if not _running:
            log.info("시스템 종료 중...")
            if collector:
                collector.stop()

            _force_sell_all()
            recorder.save()
            recorder.print_summary()

            s = engine.status()
            telegram.send(
                "🔴 [실전] 시스템 종료\n"
                "자산: " + format(s["total_asset"], ",") + "원"
            )
            qt_app.quit()

    exit_timer = QTimer()
    exit_timer.timeout.connect(check_exit)
    exit_timer.start(1_000)

    sys.exit(qt_app.exec_())


def _force_sell_all():
    """전량 강제 청산"""
    positions = engine.position_mgr.get_all()
    for ticker, pos in positions.items():
        if pos.get("qty", 0) > 0:
            current = collector.get_current_bar(ticker) if collector else None
            price = current["close"] if current else pos.get("avg_price", 0)
            execute_sell(ticker, pos["qty"], price, reason="긴급청산")


if __name__ == "__main__":
    main()