"""
모의투자 통합 메인
- 키움 모의서버 연결
- 실시간 시세 → 전략 판단 → Paper 매매
- AI 신호 결합 (선택)
- 전 과정 기록

실행: py -3.10-32 app/main_paper.py
"""

import sys
import time
import signal
print("0. 모의투자 시작")
sys.path.insert(0, r"C:\trading\app")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from config_paper                import PaperConfig as Config
from utils.logger                import get_logger
from notify.telegram_bot         import TelegramBot
from risk.risk_manager           import RiskManager
from engine.trade_engine         import TradeEngine
from engine.paper_recorder       import PaperRecorder
from strategy.combined_strategy  import CombinedStrategy
from scheduler.market_scheduler  import MarketScheduler
from web.app                     import run_server_thread, update_state, add_log
from kiwoom.kiwoom_api           import KiwoomAPI
from kiwoom.realtime_collector   import RealtimeCollector
from kiwoom.order_executor       import KiwoomOrderExecutor

log = get_logger("PAPER")

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
    global recorder, ai_client

    log.info("=" * 60)
    log.info("모의투자 시스템 초기화")
    log.info("MODE    = " + Config.MODE)
    log.info("CAPITAL = " + format(Config.INITIAL_CAPITAL, ","))
    log.info("TICKERS = " + str(Config.TICKERS))
    log.info("=" * 60)

    # ── 1. PyQt5 ─────────────────────────────
    qt_app = QApplication(sys.argv)

    # ── 2. 키움 로그인 ───────────────────────
    kiwoom = KiwoomAPI()
    if not kiwoom.login(timeout_sec=60):
        log.error("키움 로그인 실패!")
        sys.exit(1)

    server_type = kiwoom.get_server_type()
    account_no  = Config.ACCOUNT_NO or kiwoom.get_account_list()[0]
    log.info("서버: " + server_type + " / 계좌: " + account_no)

    # ── 3. 기록기 ────────────────────────────
    recorder = PaperRecorder(log_dir=Config.PAPER_LOG_DIR)

    # ── 4. 텔레그램 ─────────────────────────
    telegram = TelegramBot(
        token   = Config.TELEGRAM_TOKEN,
        chat_id = Config.TELEGRAM_CHAT_ID,
        enabled = Config.TELEGRAM_ENABLED,
    )

    # ── 5. 리스크 ────────────────────────────
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

    # ── 6. 매매 엔진 ────────────────────────
    engine = TradeEngine(
        capital            = Config.INITIAL_CAPITAL,
        mode               = "paper",
        max_position_ratio = Config.MAX_PER_STOCK,
        max_positions      = Config.MAX_STOCKS,
    )

    for ticker in Config.TICKERS:
        strategy = CombinedStrategy(params=Config.COMBINED_PARAMS)
        engine.add_strategy(ticker, strategy)

    # ── 7. 주문 실행기 (paper 고정) ──────────
    executor = KiwoomOrderExecutor(
        kiwoom_api = kiwoom,
        account_no = account_no,
        mode       = "paper",
    )

    # ── 8. 실시간 수집기 ─────────────────────
    collector = RealtimeCollector(
        kiwoom_api = kiwoom,
        interval   = Config.BAR_INTERVAL,
    )
    collector.on_bar_complete = on_bar_complete
    collector.on_tick         = on_tick_received

    # ── 9. AI 클라이언트 (선택) ──────────────
    if Config.AI_ENABLED:
        try:
            from ai.ai_client import AIClient
            ai_client = AIClient()
            if ai_client.is_available():
                log.info("AI 모듈 활성화")
            else:
                log.info("AI 모델 미학습 → AI 비활성")
                ai_client = None
        except Exception as e:
            log.warning("AI 모듈 로드 실패: " + str(e))
            ai_client = None

    # ── 10. 스케줄러 ─────────────────────────
    scheduler = MarketScheduler()
    scheduler.on_reset(_on_daily_reset)
    scheduler.on_start(_on_market_open)
    scheduler.on_pre_close(_on_pre_close)
    scheduler.on_stop(_on_market_close)
    scheduler.start()

    # ── 11. 웹 대시보드 ─────────────────────
    if Config.WEB_ENABLED:
        run_server_thread(port=Config.WEB_PORT)

    # ── 알림 ─────────────────────────────────
    telegram.send(
        "📝 모의투자 시작\n"
        "서버: " + server_type + "\n"
        "자본: " + format(Config.INITIAL_CAPITAL, ",") + "원\n"
        "종목: " + str(Config.TICKERS) + "\n"
        "AI: " + ("ON" if ai_client else "OFF")
    )
    add_log("📝 모의투자 시작")


# ══════════════════════════════════════════════
#  실시간 매매 로직
# ══════════════════════════════════════════════

def on_tick_received(ticker, price, volume):
    """틱 수신 → 손절/익절 체크"""
    pos = engine.position_mgr.get(ticker)
    if pos is None or pos.get("qty", 0) <= 0:
        return

    avg_price = pos.get("avg_price", 0)
    if avg_price <= 0:
        return

    pnl_rate = (price - avg_price) / avg_price

    if pnl_rate <= -Config.STOP_LOSS:
        log.warning("🔴 손절: " + ticker + " " +
                    str(round(pnl_rate * 100, 2)) + "%")
        execute_sell(ticker, pos["qty"], price, reason="손절")

    elif pnl_rate >= Config.TAKE_PROFIT:
        log.info("🟢 익절: " + ticker + " " +
                 str(round(pnl_rate * 100, 2)) + "%")
        execute_sell(ticker, pos["qty"], price, reason="익절")


def on_bar_complete(ticker, bar):
    """봉 완성 → 전략 + AI → 매매"""

    # 봉 기록
    if Config.PAPER_LOG_EVERY_BAR:
        recorder.record_bar(ticker, bar)

    # 리스크 체크
    r_status = risk.status()
    if r_status.get("blocked", False):
        return

    # 포지션 정보
    pos       = engine.position_mgr.get(ticker)
    position  = pos["qty"]       if pos else 0
    avg_price = pos["avg_price"] if pos else 0

    # ── 전략 판단 ────────────────────────────
    strategy = engine.get_strategy(ticker)
    if strategy is None:
        return

    strategy_signal = strategy.on_bar(bar, engine.capital, position, avg_price)

    # ── AI 판단 (선택) ───────────────────────
    final_signal = strategy_signal

    if ai_client and Config.AI_ENABLED:
        try:
            from ai.feature_builder import FeatureBuilder
            builder = FeatureBuilder()
            # 간이 특징 생성 (현재 bar 기준)
            features = _build_live_features(bar)
            if features:
                ai_result = ai_client.predict(features)
                recorder.record_ai_signal(ticker, ai_result, strategy_signal)

                # AI 신뢰도 충분하면 결합
                if ai_result.get("confidence", 0) >= Config.AI_MIN_CONF:
                    from ai.brain import AIBrain
                    brain = AIBrain(use_lstm=False)
                    final_signal = brain.combine_with_strategy(
                        strategy_signal, ai_result,
                        ai_weight=Config.AI_WEIGHT
                    )
        except Exception as e:
            log.debug("AI 판단 오류: " + str(e))

    # ── 신호 기록 ────────────────────────────
    if Config.PAPER_LOG_SIGNALS:
        recorder.record_signal(ticker, final_signal, {
            "strategy": strategy_signal,
            "bar_close": bar["close"],
        })

    # ── 매수 ─────────────────────────────────
    if final_signal == "buy" and position == 0:
        can_buy = risk.can_buy(
            capital      = engine.capital,
            price        = bar["close"],
            position_cnt = engine.position_mgr.count(),
        )
        if can_buy:
            qty = int(engine.capital * Config.MAX_PER_STOCK / bar["close"])
            if qty > 0:
                execute_buy(ticker, qty, bar["close"])

    # ── 매도 ─────────────────────────────────
    elif final_signal == "sell" and position > 0:
        execute_sell(ticker, position, bar["close"], reason="전략매도")

    sync_web()


def _build_live_features(bar):
    """실시간 bar에서 간이 특징 생성"""
    try:
        c = bar["close"]
        o = bar["open"]
        h = bar["high"]
        l = bar["low"]
        v = bar["volume"]

        if c <= 0:
            return None

        # 간이 특징 24개 (0으로 채움 → 실시간에선 부분적)
        features = [0.0] * 24

        # body ratio
        features[13] = (c - o) / c if c > 0 else 0

        # volume (기본값 대비)
        features[11] = 1.0

        return features
    except:
        return None


def execute_buy(ticker, qty, price):
    """매수 실행 + 기록"""
    success = executor.buy_market(ticker, qty)
    if success:
        engine.buy(ticker, price, qty)
        risk.record_trade("buy")

        amount = price * qty
        fee = amount * 0.00015

        recorder.record_trade(
            ticker, "BUY", price, qty,
            amount=amount, fee=fee,
            reason="전략매수"
        )

        telegram.send(
            "📝 [모의] 매수\n" + ticker +
            " " + str(qty) + "주 @" + format(price, ",")
        )
        add_log("📝 매수: " + ticker)


def execute_sell(ticker, qty, price, reason=""):
    """매도 실행 + 기록"""
    pos = engine.position_mgr.get(ticker)
    avg_price = pos.get("avg_price", 0) if pos else 0

    success = executor.sell_market(ticker, qty)
    if success:
        pnl = engine.sell(ticker, price, qty)
        risk.record_trade("sell", pnl=pnl)

        amount = price * qty
        fee = amount * 0.00015
        tax = amount * 0.0018
        pnl_rate = ((price - avg_price) / avg_price * 100) if avg_price > 0 else 0

        recorder.record_trade(
            ticker, "SELL", price, qty,
            amount=amount, fee=fee, tax=tax,
            pnl=pnl, pnl_rate=pnl_rate,
            reason=reason,
        )

        telegram.send(
            "📝 [모의] 매도 (" + reason + ")\n" + ticker +
            " " + str(qty) + "주 @" + format(price, ",") +
            "\n손익: " + format(pnl, ",") + "원"
        )
        add_log("📝 매도: " + ticker + " (" + reason + ")")


# ══════════════════════════════════════════════
#  스케줄러 콜백
# ══════════════════════════════════════════════

def _on_daily_reset(dt):
    log.info("일일 리셋")
    risk.reset_daily(engine.capital, str(dt.date()))

def _on_market_open(dt):
    log.info("장 시작 → 실시간 수집")
    collector.start(Config.TICKERS)
    telegram.send("📝 [모의] 장 시작 — 매매 시작")

def _on_pre_close(dt):
    log.info("매수 중단")
    risk.block("15:20 매수 중단")

def _on_market_close(dt):
    log.info("장 종료 → 전량 청산")

    collector.force_complete_all()
    collector.stop()

    # 전량 청산
    positions = engine.position_mgr.get_all()
    for ticker, pos in positions.items():
        if pos.get("qty", 0) > 0:
            current = collector.get_current_bar(ticker)
            price = current["close"] if current else pos.get("avg_price", 0)
            execute_sell(ticker, pos["qty"], price, reason="장종료청산")

    # 기록 저장
    recorder.save()

    # 자산 기록
    s = engine.status()
    recorder.record_equity(
        s["capital"], s["eval_value"], s["total_asset"],
        s["positions"],
    )

    # 일별 요약
    summary = recorder.generate_daily_summary(
        Config.INITIAL_CAPITAL, s["total_asset"]
    )
    recorder.print_summary()

    # 텔레그램 리포트
    telegram.send(
        "📝 [모의] 일일 리포트\n"
        "자산: " + format(s["total_asset"], ",") + "원\n"
        "손익: " + format(s["pnl"], ",") + "원\n"
        "매매: " + str(recorder.stats["total_trades"]) + "회\n"
        "승률: " + str(summary.get("win_rate", 0)) + "%"
    )


# ══════════════════════════════════════════════
#  웹 동기화
# ══════════════════════════════════════════════

def sync_web():
    try:
        s   = engine.status()
        r   = risk.status()
        sch = scheduler.status()
        rec = recorder.get_stats()

        update_state({
            "mode":            "PAPER",
            "capital":         s["capital"],
            "eval_value":      s["eval_value"],
            "total_asset":     s["total_asset"],
            "initial_capital": Config.INITIAL_CAPITAL,
            "pnl":             s["pnl"],
            "pnl_rate":        s["pnl_rate"],
            "buy_count":       s["buy_count"],
            "sell_count":      s["sell_count"],
            "positions":       s["positions"],
            "scheduler":       sch,
            "risk": {
                "blocked":      r.get("blocked", False),
                "block_reason": r.get("block_reason", ""),
            },
            "paper_stats":     rec,
            "ai_enabled":      ai_client is not None,
        })
    except:
        pass


# ══════════════════════════════════════════════
#  메인 루프
# ══════════════════════════════════════════════

def main():
    global _running

    init()

    log.info("모의투자 메인 루프 시작")

    # 주기적 저장
    save_timer = QTimer()
    save_timer.timeout.connect(lambda: recorder.save())
    save_timer.start(Config.PAPER_SAVE_INTERVAL * 1000)

    # 웹 동기화
    sync_timer = QTimer()
    sync_timer.timeout.connect(sync_web)
    sync_timer.start(10_000)

    # 종료 체크
    def check_exit():
        if not _running:
            if collector:
                collector.stop()
            recorder.save()
            recorder.print_summary()

            s = engine.status()
            telegram.send(
                "📝 [모의] 시스템 종료\n"
                "자산: " + format(s["total_asset"], ",") + "원"
            )
            qt_app.quit()

    exit_timer = QTimer()
    exit_timer.timeout.connect(check_exit)
    exit_timer.start(1_000)

    sys.exit(qt_app.exec_())


if __name__ == "__main__":
    main()