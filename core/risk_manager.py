"""
리스크 관리자
80만원 소자본 특화 — 손실 한도, 연속 손절, 일일 매매 제한
"""
from datetime import datetime, date


class RiskManager:
    """소자본 특화 리스크 관리"""

    MAX_POSITIONS    = 2        # 동시 보유 최대 2종목
    MAX_SINGLE_RATIO = 0.50    # 1종목당 최대 50%
    DAILY_LOSS_LIMIT = -0.05   # 일일 -5% 도달 시 매매 중단
    CONSECUTIVE_LOSS = 3       # 연속 3연패 후 30분 휴식
    PAUSE_MINUTES    = 30      # 연속 손절 후 쉬는 시간
    MAX_DAILY_TRADES = 10      # 일일 최대 매매 10회

    def __init__(self, initial_capital: float = 800_000):
        self.initial_capital = initial_capital
        self._today = date.today()
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._pause_until = None   # datetime

    def _reset_if_new_day(self):
        today = date.today()
        if today != self._today:
            self._today = today
            self._daily_trades = 0
            self._daily_pnl = 0.0
            self._consecutive_losses = 0
            self._pause_until = None

    def record_trade(self, profit: float):
        """매매 결과 기록"""
        self._reset_if_new_day()
        self._daily_trades += 1
        self._daily_pnl += profit
        if profit < 0:
            self._consecutive_losses += 1
            if self._consecutive_losses >= self.CONSECUTIVE_LOSS:
                import datetime as dt
                self._pause_until = dt.datetime.now() + dt.timedelta(minutes=self.PAUSE_MINUTES)
        else:
            self._consecutive_losses = 0

    def can_buy(self, current_capital: float, current_positions: int) -> tuple:
        """
        매수 가능 여부 종합 체크
        Returns: (can_buy: bool, reason: str)
        """
        self._reset_if_new_day()

        if current_positions >= self.MAX_POSITIONS:
            return False, f'최대 보유 종목 수 초과 ({self.MAX_POSITIONS}개)'

        if self._daily_trades >= self.MAX_DAILY_TRADES:
            return False, f'일일 최대 매매 횟수 초과 ({self.MAX_DAILY_TRADES}회)'

        daily_loss_rate = self._daily_pnl / self.initial_capital
        if daily_loss_rate <= self.DAILY_LOSS_LIMIT:
            return False, f'일일 손실 한도 초과 ({daily_loss_rate*100:.1f}%)'

        if self._pause_until:
            import datetime as dt
            if dt.datetime.now() < self._pause_until:
                remaining = (self._pause_until - dt.datetime.now()).seconds // 60
                return False, f'연속 {self.CONSECUTIVE_LOSS}연패 — {remaining}분 후 재개'
            else:
                self._pause_until = None
                self._consecutive_losses = 0

        return True, 'OK'

    def calc_position_size(self, capital: float, buy_price: float,
                           risk_per_trade: float = 0.02, stop_loss_rate: float = 0.02) -> int:
        """켈리 기반 주문 수량"""
        import math
        if buy_price <= 0 or stop_loss_rate <= 0:
            return 0
        risk_amount = capital * risk_per_trade
        per_share_risk = buy_price * stop_loss_rate
        qty = math.floor(risk_amount / per_share_risk)
        max_qty = math.floor(capital * self.MAX_SINGLE_RATIO / buy_price)
        return min(qty, max_qty)

    def emergency_check(self, market_change_rate: float) -> tuple:
        """
        긴급 킬스위치 체크
        Returns: (block_buy: bool, reason: str)
        """
        if market_change_rate <= -0.05:
            return True, f'코스닥 -5% 급락 ({market_change_rate*100:.1f}%)'
        if market_change_rate <= -0.03:
            return True, f'코스피 -3% 급락 ({market_change_rate*100:.1f}%)'
        return False, 'normal'

    @property
    def daily_stats(self) -> dict:
        return {
            'daily_trades': self._daily_trades,
            'daily_pnl': self._daily_pnl,
            'consecutive_losses': self._consecutive_losses,
            'is_paused': bool(self._pause_until),
        }
