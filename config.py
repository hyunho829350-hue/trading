# config.py – Global configuration for the scalping trading system

# ── API Settings ─────────────────────────────────────────────────────────────
API_MOCK_MODE = True          # True = simulation mode (no real Kiwoom connection)
KIWOOM_ACCOUNT = "1234567890" # Demo account number

# ── Throttle / Rate-limit ─────────────────────────────────────────────────────
MAX_ORDERS_PER_SECOND  = 5    # Kiwoom API order limit
MAX_QUERIES_PER_SECOND = 5    # Kiwoom API query limit
THROTTLE_DELAY_SEC     = 0.2  # Delay injected when approaching rate limit

# ── Trading Parameters ────────────────────────────────────────────────────────
SLIPPAGE_TICKS         = 2    # Max ticks away from current price for limit orders
ORDER_TIMEOUT_SEC      = 3    # Cancel & resubmit if unfilled after this many seconds
POSITION_TIMEOUT_MIN   = 10   # Force-liquidate position after this many minutes

# ── Risk Management ───────────────────────────────────────────────────────────
MAX_POSITION_COUNT     = 5    # Maximum simultaneous positions
MAX_LOSS_PER_TRADE_PCT = 0.5  # Stop-loss (% of entry price)
TAKE_PROFIT_PCT        = 1.0  # Take-profit (% above entry price)
DAILY_LOSS_LIMIT_KRW   = 500_000  # Kill-switch triggers if daily loss exceeds this

# ── Auto-Journal / SQLite ─────────────────────────────────────────────────────
JOURNAL_DB_PATH = "trades.db"

# ── UI Refresh ────────────────────────────────────────────────────────────────
UI_TICK_INTERVAL_MS = 500   # Watchlist / positions refresh interval (ms)
LOG_MAX_LINES       = 500   # Maximum lines kept in the system log
