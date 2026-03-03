import sys
sys.path.insert(0, r"C:\trading\app")

from utils.env_loader import load_env

env = load_env()


class Config:
    """
    전체 시스템 설정
    모든 파라미터를 한 곳에서 관리
    """

    # ── 기본 설정 ────────────────────────────
    MODE            = "paper"          # "paper" or "live"
    INITIAL_CAPITAL = 10_000_000       # 초기 자본금

    # ── KIS API ──────────────────────────────
    APP_KEY         = env.get("APP_KEY",    "")
    APP_SECRET      = env.get("APP_SECRET", "")
    ACCOUNT_NO      = env.get("ACCOUNT_NO", "")

    # ── 텔레그램 ─────────────────────────────
    TELEGRAM_TOKEN   = env.get("TELEGRAM_TOKEN",   "")
    TELEGRAM_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")
    TELEGRAM_ENABLED = True

    # ── 웹 대시보드 ──────────────────────────
    WEB_ENABLED = True
    WEB_PORT    = 5000

    # ── 리스크 설정 ──────────────────────────
    MAX_PER_STOCK        = 0.3     # 종목당 최대 투자 비율 30%
    STOP_LOSS            = 0.02   # 손절 2%
    TAKE_PROFIT          = 0.05   # 익절 5%
    MAX_DAILY_LOSS       = 0.02   # 일일 최대 손실 2%
    MAX_STOCKS           = 5      # 최대 보유 종목 수
    MAX_CONSECUTIVE_LOSS = 3      # 연속 손실 최대 횟수
    MAX_DAILY_TRADES     = 10     # 일일 최대 거래 횟수

    # ── 매매 종목 리스트 ─────────────────────
    TICKERS = [
        "005930",   # 삼성전자
        "000660",   # SK하이닉스
        "035420",   # NAVER
        "005380",   # 현대차
        "051910",   # LG화학
    ]

    # ── 전략 설정 ────────────────────────────
    STRATEGY = "combined"   # "combined" or 개별 전략명

    COMBINED_PARAMS = {
        "buy_threshold":  3,
        "sell_threshold": 2,
        "strategies": [
            {"name": "pullback",    "weight": 1, "params": {"ma_period": 20, "vol_ma": 20}},
            {"name": "volume",      "weight": 1, "params": {"vol_ma": 20, "vol_surge": 2.0}},
            {"name": "ma_breakout", "weight": 1, "params": {"ma_short": 5, "ma_long": 20}},
            {"name": "gap",         "weight": 1, "params": {"gap_min": 1.0}},
            {"name": "rsi",         "weight": 1, "params": {"rsi_period": 14}},
            {"name": "scalping",    "weight": 1, "params": {"bb_period": 20}},
            {"name": "daytrading",  "weight": 1, "params": {"ma_fast": 5, "ma_mid": 10, "ma_slow": 20}},
            {"name": "trend",       "weight": 2, "params": {"ma_fast": 5, "ma_mid": 20, "ma_slow": 60}},
            {"name": "supply",      "weight": 2, "params": {"vol_surge": 2.0}},
            {"name": "resistance",  "weight": 1, "params": {"lookback": 20}},
            {"name": "box",         "weight": 1, "params": {"box_period": 20}},
            {"name": "fallen",      "weight": 1, "params": {"fall_period": 5, "fall_min": 10.0}},
            {"name": "swing",       "weight": 2, "params": {"ma_fast": 5, "ma_mid": 20, "ma_slow": 60}},
            {"name": "daily",       "weight": 1, "params": {"ma_period": 5}},
        ],
    }

    # ── 봉 주기 ──────────────────────────────
    BAR_INTERVAL = 60   # 초 단위 (60 = 1분봉)