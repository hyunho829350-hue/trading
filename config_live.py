"""
실전 투자 전용 설정
- 모의투자 검증 통과 후에만 사용
- 최대 안전 장치 적용

⚠️ 실제 돈이 투입됩니다! 신중하게 설정하세요.
"""

import sys
sys.path.insert(0, r"C:\trading\app")

from config import Config


class LiveConfig(Config):
    """
    실전 투자 설정

    모의투자 대비 변경:
        - MODE = "live"
        - 실전 계좌
        - 강화된 안전 장치
    """

    # ── 모드 ─────────────────────────────────
    MODE = "live"

    # ── 자본금 ───────────────────────────────
    INITIAL_CAPITAL = 10_000_000    # 시작은 소액으로

    # ── 종목 ─────────────────────────────────
    TICKERS = [
        "005930",   # 삼성전자
        "000660",   # SK하이닉스
        "035420",   # NAVER
    ]

    # ── 리스크 (최대 보수적) ─────────────────
    MAX_PER_STOCK        = 0.15    # 종목당 15%
    STOP_LOSS            = 0.015   # 손절 1.5%
    TAKE_PROFIT          = 0.03    # 익절 3%
    MAX_DAILY_LOSS       = 0.01    # 일일 최대 손실 1%
    MAX_STOCKS           = 3       # 최대 3종목
    MAX_CONSECUTIVE_LOSS = 2       # 연속 2회 → 중단
    MAX_DAILY_TRADES     = 5       # 일일 최대 5회

    # ── 전략 ─────────────────────────────────
    COMBINED_PARAMS = {
        "buy_threshold":  5,       # 매우 신중
        "sell_threshold": 2,
        "strategies": Config.COMBINED_PARAMS["strategies"],
    }

    # ── AI ────────────────────────────────────
    AI_ENABLED   = True
    AI_WEIGHT    = 0.3
    AI_MIN_CONF  = 0.6             # 높은 신뢰도만

    # ── 안전 장치 ────────────────────────────
    SAFETY_ENABLED           = True
    SAFETY_MAX_ORDER_AMOUNT  = 3_000_000   # 1회 주문 최대 300만
    SAFETY_MAX_TOTAL_INVEST  = 8_000_000   # 총 투자 최대 800만
    SAFETY_REQUIRE_CONFIRM   = False       # 주문 전 확인 (True면 텔레그램 확인)
    SAFETY_COOL_DOWN         = 30          # 주문 후 30초 대기
    SAFETY_MARKET_HOURS_ONLY = True        # 장 시간에만 주문
    SAFETY_EMERGENCY_STOP    = 0.03        # 3% 손실 시 전체 중단

    # ── 기록 ─────────────────────────────────
    LIVE_LOG_DIR = r"C:\trading\data\live"