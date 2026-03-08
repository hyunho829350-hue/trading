"""
포지션 관리자
보유 종목 포지션 추적 — 최대 2개, 손익분기점, 트레일링 스탑
"""
from datetime import datetime


class PositionManager:
    """
    소자본(80만) 특화: 최대 2종목 동시 보유
    """

    MAX_POSITIONS = 2
    BUY_FEE  = 0.00015
    SELL_FEE = 0.00015
    TAX      = 0.0023
    BREAKEVEN_COST = BUY_FEE + SELL_FEE + TAX  # ~0.261%

    def __init__(self):
        # {stock_code: position_dict}
        self._positions: dict = {}

    # ── 포지션 오픈 ──────────────────────────────────────────────────────
    def open_position(self, stock_code: str, buy_price: float, quantity: int,
                      strategy_name: str = '', capital: float = 0) -> bool:
        """
        포지션 오픈
        Returns: True if successful
        """
        if len(self._positions) >= self.MAX_POSITIONS:
            return False
        if stock_code in self._positions:
            return False

        # 비중 체크 (최대 50%)
        if capital > 0:
            position_value = buy_price * quantity
            if position_value > capital * 0.5:
                return False

        self._positions[stock_code] = {
            'stock_code': stock_code,
            'buy_price': buy_price,
            'quantity': quantity,
            'strategy': strategy_name,
            'open_time': datetime.now(),
            'highest_price': buy_price,
            'current_price': buy_price,
            'breakeven': self.get_breakeven_price(buy_price),
        }
        return True

    def close_position(self, stock_code: str) -> dict | None:
        return self._positions.pop(stock_code, None)

    # ── 가격 갱신 ────────────────────────────────────────────────────────
    def update_price(self, stock_code: str, current_price: float):
        if stock_code not in self._positions:
            return
        pos = self._positions[stock_code]
        pos['current_price'] = current_price
        if current_price > pos['highest_price']:
            pos['highest_price'] = current_price

    # ── 손익 계산 ────────────────────────────────────────────────────────
    def get_unrealized_pnl(self, stock_code: str) -> dict:
        pos = self._positions.get(stock_code, {})
        if not pos:
            return {}
        buy = pos['buy_price']
        cur = pos['current_price']
        qty = pos['quantity']
        gross = (cur - buy) * qty
        cost  = (buy * qty * self.BUY_FEE + cur * qty * (self.SELL_FEE + self.TAX))
        net   = gross - cost
        rate  = net / (buy * qty) * 100 if buy * qty > 0 else 0
        return {'gross': gross, 'net': net, 'rate': rate, 'cost': cost}

    def get_breakeven_price(self, buy_price: float) -> float:
        """손익분기 매도가 (수수료+세금 포함)"""
        return buy_price * (1 + self.BUY_FEE) / (1 - self.SELL_FEE - self.TAX)

    # ── 트레일링 스탑 ────────────────────────────────────────────────────
    def get_trailing_stop_price(self, stock_code: str, trailing_pct: float = 0.015) -> float | None:
        pos = self._positions.get(stock_code)
        if not pos:
            return None
        # 최고가에서 1.5% 하락 시 매도
        return pos['highest_price'] * (1 - trailing_pct)

    # ── 손절 판단 ────────────────────────────────────────────────────────
    def should_cut_loss(self, stock_code: str, stop_loss_rate: float = -0.02) -> bool:
        """손절 조건 확인"""
        pos = self._positions.get(stock_code)
        if not pos:
            return False
        rate = (pos['current_price'] - pos['buy_price']) / pos['buy_price']
        return rate <= stop_loss_rate

    # ── 조회 ─────────────────────────────────────────────────────────────
    def get_position(self, stock_code: str) -> dict | None:
        return self._positions.get(stock_code)

    def get_all_positions(self) -> dict:
        return dict(self._positions)

    def count(self) -> int:
        return len(self._positions)

    def has_position(self, stock_code: str) -> bool:
        return stock_code in self._positions

    def get_hold_minutes(self, stock_code: str) -> float:
        pos = self._positions.get(stock_code)
        if not pos:
            return 0
        delta = datetime.now() - pos['open_time']
        return delta.total_seconds() / 60
