"""
모의투자 전용 설정
- 기본 Config를 상속받아 모의투자용 파라미터 오버라이드
- 안전한 설정 (소액, 적은 종목, 강화된 리스크)

사용:
    from config_paper import PaperConfig
    config = PaperConfig
"""

import sys
sys.path.insert(0, r"C:\trading\app")

from config import Config


class PaperConfig(Config):
    """
    모의투자 전용 설정

    변경 사항:
        - MODE = "paper" 고정
        - 소액 자본금
        - 적은 종목 수
        - 강화된 리스크
        - 상세 로깅
    """

    # ── 모드 고정 ────────────────────────────
    MODE = "paper"

    # ── 자본금 (소액) ────────────────────────
    INITIAL_CAPITAL = 10_000_000    # 1000만원

    # ── 종목 (소수 정예) ─────────────────────
    TICKERS = [
        "005930",   # 삼성전자
        "000660",   # SK하이닉스
        "035420",   # NAVER
    ]

    # ── 리스크 (보수적) ──────────────────────
    MAX_PER_STOCK        = 0.2     # 종목당 20% (기본 30%→20%)
    STOP_LOSS            = 0.015   # 손절 1.5% (기본 2%→1.5%)
    TAKE_PROFIT          = 0.03    # 익절 3% (기본 5%→3%)
    MAX_DAILY_LOSS       = 0.015   # 일일 최대 손실 1.5%
    MAX_STOCKS           = 3       # 최대 3종목
    MAX_CONSECUTIVE_LOSS = 2       # 연속 2회 손실 시 중단
    MAX_DAILY_TRADES     = 6       # 일일 최대 6회

    # ── 전략 (threshold 높임 = 신중) ─────────
    COMBINED_PARAMS = {
        "buy_threshold":  4,       # 기본 3→4 (더 신중)
        "sell_threshold": 2,
        "strategies": Config.COMBINED_PARAMS["strategies"],
    }

    # ── 봉 주기 ──────────────────────────────
    BAR_INTERVAL = 60              # 1분봉

    # ── 모의투자 전용 설정 ────────────────────
    PAPER_LOG_DIR        = r"C:\trading\data\paper"
    PAPER_LOG_EVERY_TICK = False   # 모든 틱 기록 (True면 용량 큼)
    PAPER_LOG_EVERY_BAR  = True    # 모든 봉 기록
    PAPER_LOG_SIGNALS    = True    # 전략 신호 기록
    PAPER_SAVE_INTERVAL  = 300     # 5분마다 중간 저장 (초)

    # ── AI 설정 ──────────────────────────────
    AI_ENABLED   = True            # AI 신호 사용
    AI_WEIGHT    = 0.3             # AI 가중치 (전략 0.7 + AI 0.3)
    AI_MIN_CONF  = 0.5             # AI 최소 신뢰도