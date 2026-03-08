"""
슬리피지 추적기
매매마다 예상 vs 실제 체결가 차이를 측정하고 다음 주문에 반영
"""
import os
import sqlite3
from datetime import datetime


class SlippageTracker:
    """
    매매마다 슬리피지를 측정하고 다음 주문에 반영
    - SQLite slip_record 테이블에 저장
    - 종목별 최근 10회 평균 슬리피지 계산
    """

    DB_PATH = r"C:\trading\db\trading.db"

    # 시총 등급별 기본 슬리피지
    DEFAULT_SLIPPAGE = {
        'large':  0.0005,   # 0.05% 대형주
        'mid':    0.0015,   # 0.15% 중형주
        'small':  0.0030,   # 0.30% 소형주
    }

    def __init__(self, db_path: str = None):
        self.db_path = db_path or self.DB_PATH
        # 메모리 캐시: {stock_code: [slip_rate, ...]} (최근 10개)
        self._cache: dict = {}
        self._init_db()

    def _init_db(self):
        """DB 초기화 (로컬 폴백)"""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS slip_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    order_price REAL NOT NULL,
                    filled_price REAL NOT NULL,
                    slip_rate REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass  # DB 없어도 메모리 캐시로 동작

    # ── KRX 틱 사이즈 ────────────────────────────────────────────────────
    def get_tick_size(self, price: int) -> int:
        """KRX 호가 단위"""
        if price < 1_000:     return 1
        elif price < 5_000:   return 5
        elif price < 10_000:  return 10
        elif price < 50_000:  return 50
        elif price < 100_000: return 100
        elif price < 500_000: return 500
        else:                 return 1_000

    def _round_to_tick(self, price: float) -> int:
        tick = self.get_tick_size(int(price))
        return int(round(price / tick) * tick)

    # ── 슬리피지 기록 ────────────────────────────────────────────────────
    def record(self, stock_code: str, order_price: float, filled_price: float,
               direction: str, market_cap: int = None):
        """
        체결 후 호출 — 슬리피지 기록
        direction: 'BUY' or 'SELL'
        """
        if direction == 'BUY':
            slip_rate = (filled_price - order_price) / order_price if order_price > 0 else 0
        else:
            slip_rate = (order_price - filled_price) / order_price if order_price > 0 else 0

        # 메모리 캐시
        if stock_code not in self._cache:
            self._cache[stock_code] = []
        self._cache[stock_code].append(slip_rate)
        if len(self._cache[stock_code]) > 10:
            self._cache[stock_code] = self._cache[stock_code][-10:]

        # DB 저장
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO slip_record
                (stock_code, direction, order_price, filled_price, slip_rate, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (stock_code, direction, order_price, filled_price,
                  slip_rate, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── 평균 슬리피지 조회 ───────────────────────────────────────────────
    def get_avg_slippage(self, stock_code: str, market_cap: int = None) -> float:
        """종목별 최근 10회 평균 슬리피지"""
        if stock_code in self._cache and self._cache[stock_code]:
            return sum(self._cache[stock_code]) / len(self._cache[stock_code])

        # DB 조회 시도
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute("""
                SELECT slip_rate FROM slip_record
                WHERE stock_code = ?
                ORDER BY id DESC LIMIT 10
            """, (stock_code,)).fetchall()
            conn.close()
            if rows:
                rates = [r[0] for r in rows]
                return sum(rates) / len(rates)
        except Exception:
            pass

        # 기본값: 시총 등급별
        if market_cap:
            if market_cap >= 500_000_000_000:  # 5000억 이상 대형주
                return self.DEFAULT_SLIPPAGE['large']
            elif market_cap >= 100_000_000_000:  # 1000억 이상 중형주
                return self.DEFAULT_SLIPPAGE['mid']
        return self.DEFAULT_SLIPPAGE['small']

    # ── 안전 매수가 계산 ─────────────────────────────────────────────────
    def get_safe_buy_price(self, stock_code: str, base_price: int, market_cap: int = None) -> int:
        """
        슬리피지 감안 안전 매수 지정가
        이 가격에 안 채워지면 포기 (추격 금지)
        """
        avg_slip = self.get_avg_slippage(stock_code, market_cap)
        safe_price = base_price * (1 + avg_slip)
        return self._round_to_tick(safe_price)

    # ── 안전 매도 목표가 계산 ────────────────────────────────────────────
    def get_safe_sell_price(self, stock_code: str, buy_price: int,
                            target_rate: float, market_cap: int = None) -> int:
        """
        수수료+세금+슬리피지 포함 실제 목표 매도가
        target_rate: 원하는 순수익률 (0.03 = 3%)
        """
        avg_slip = self.get_avg_slippage(stock_code, market_cap)
        # 매수 수수료 0.015%, 매도 수수료 0.015% + 세금 0.23% + 슬리피지
        total_cost = 0.00015 + 0.00015 + 0.0023 + avg_slip
        sell_price = buy_price * (1 + target_rate + total_cost)
        return self._round_to_tick(sell_price)

    # ── 진입 포기 판단 ───────────────────────────────────────────────────
    def should_skip(self, stock_code: str, current_spread_rate: float) -> bool:
        """호가 스프레드가 너무 넓으면 진입 포기"""
        if current_spread_rate > 0.005:   # 0.5% 초과: 무조건 포기
            return True
        if current_spread_rate > 0.003:   # 0.3% 초과: 포기
            return True
        return False
