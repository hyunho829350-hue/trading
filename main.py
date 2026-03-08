"""
메인 진입점 — paper 모드 자동매매 시스템 실행
키움 32bit Python + 전체 모듈 통합
"""
import sys
import os

# 프로젝트 루트를 Python path에 추가
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.trading_engine import TradingEngine
from core.auto_scheduler import AutoScheduler
from storage.trade_book import TradeBook
from notify.telegram_bot import TelegramBot

# ── 설정 로드 ──────────────────────────────────────────────────────────
try:
    import yaml
    config_path = r'C:\trading\config\paths.yaml'
    if not os.path.exists(config_path):
        config_path = os.path.join(BASE_DIR, 'config', 'paths.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            CONFIG = yaml.safe_load(f) or {}
    else:
        CONFIG = {}
except Exception:
    CONFIG = {}

# 기본 설정
CONFIG.setdefault('mode', 'paper')
CONFIG.setdefault('initial_capital', 800_000)
CONFIG.setdefault('stop_loss', -0.02)
CONFIG.setdefault('take_profit', 0.03)
CONFIG.setdefault('trailing_pct', 0.015)
CONFIG.setdefault('telegram_token', '')
CONFIG.setdefault('telegram_chat_id', '')


def main():
    print('=' * 60)
    print(f'  AI 자동매매 시스템 — {CONFIG["mode"].upper()} 모드')
    print(f'  초기 자본: {CONFIG["initial_capital"]:,}원')
    print(f'  손절: {CONFIG["stop_loss"]*100:.1f}%  익절: {CONFIG["take_profit"]*100:.1f}%')
    print('=' * 60)

    # 텔레그램 봇 초기화
    telegram = TelegramBot(
        token=CONFIG.get('telegram_token', ''),
        chat_id=CONFIG.get('telegram_chat_id', '')
    )

    # 매매 장부 초기화
    trade_book = TradeBook()

    # 매매 엔진 초기화
    engine = TradingEngine(
        config=CONFIG,
        telegram_fn=telegram.send
    )

    # 스케줄러 초기화
    scheduler = AutoScheduler(engine=engine, telegram=telegram, trade_book=trade_book)

    # PyQt5 UI 실행 여부 확인
    ui_mode = '--ui' in sys.argv or '--gui' in sys.argv

    if ui_mode:
        try:
            from PyQt5.QtWidgets import QApplication
            from ui.main_dashboard import launch
            app, window = launch(engine=engine, trade_book=trade_book, telegram=telegram)
            # 스케줄러는 백그라운드 스레드로
            import threading
            sched_thread = threading.Thread(target=scheduler.run, daemon=True)
            sched_thread.start()
            sys.exit(app.exec_())
        except ImportError:
            print('[경고] PyQt5 없음 — CLI 모드로 실행')
            _run_cli(engine, scheduler, telegram, trade_book)
    else:
        _run_cli(engine, scheduler, telegram, trade_book)


def _run_cli(engine, scheduler, telegram, trade_book):
    """CLI 모드 실행 (스케줄러만)"""
    print('[CLI 모드] 스케줄러 실행 — Ctrl+C로 종료')
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print('\n[종료] 사용자 중단')
        engine.stop()


if __name__ == '__main__':
    main()
