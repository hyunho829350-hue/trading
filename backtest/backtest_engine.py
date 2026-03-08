"""
백테스트 엔진
실전과 동일한 환경: 수수료 0.015% + 세금 0.23% + 슬리피지 시뮬레이션
초기자본 80만원 특화
"""
import numpy as np
from typing import Callable, Dict, List


class BacktestEngine:
    """핵심 백테스트 실행 엔진"""

    BUY_FEE = 0.00015
    SELL_FEE = 0.00015
    TAX = 0.0023
    INITIAL_CAPITAL = 800_000   # 80만원
    MAX_POSITIONS = 2           # 최대 동시 보유 2종목
    POSITION_RATIO = 0.45       # 1종목당 45%

    # 거래대금별 슬리피지 테이블
    SLIPPAGE_TABLE = [
        (5_000_000_000, 0.0005),
        (2_000_000_000, 0.0010),
        (1_000_000_000, 0.0020),
        (0,             0.0040),
    ]

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.capital = self.INITIAL_CAPITAL
        self.trades: List[dict] = []
        self.equity_curve: List[float] = []
        self.positions: Dict[str, dict] = {}
        self.total_fee_tax = 0.0
        self.total_slippage_cost = 0.0

    def _get_slippage(self, trade_amount: float) -> float:
        for threshold, slip in self.SLIPPAGE_TABLE:
            if trade_amount >= threshold:
                return slip
        return 0.0040

    def simulate_fill(self, order_price: float, candle: dict, direction: str,
                      trade_amount: float) -> float:
        """실전 체결 시뮬레이션 (슬리피지 포함)"""
        slippage = self._get_slippage(trade_amount)
        if direction == 'BUY':
            if candle.get('close', order_price) < candle.get('open', order_price):
                slippage += 0.001   # 음봉 구간 추가 슬리피지
            fill = order_price * (1 + slippage)
            fill = min(fill, candle.get('high', fill))
        else:
            fill = order_price * (1 - slippage)
            fill = max(fill, candle.get('low', fill))

        self.total_slippage_cost += abs(fill - order_price) * (trade_amount / max(order_price, 1))
        return fill

    def apply_cost(self, buy_price: float, sell_price: float, quantity: int) -> dict:
        """수수료 + 세금 계산"""
        buy_total  = buy_price  * quantity * (1 + self.BUY_FEE)
        sell_total = sell_price * quantity * (1 - self.SELL_FEE - self.TAX)
        net = sell_total - buy_total
        fee_tax = (buy_price * quantity * self.BUY_FEE +
                   sell_price * quantity * (self.SELL_FEE + self.TAX))
        self.total_fee_tax += fee_tax
        return {'net_profit': net, 'buy_total': buy_total, 'sell_total': sell_total, 'fee_tax': fee_tax}

    def run(self, data: list, strategy_check_fn: Callable,
            stop_loss: float = -0.02, take_profit: float = 0.03,
            trailing_stop: bool = True, trailing_pct: float = 0.015,
            max_hold_bars: int = 24) -> dict:
        """
        백테스트 실행
        data: list of {open, high, low, close, volume} dicts
        strategy_check_fn(data_slice) -> (buy: bool, score: int)
        """
        self.capital = self.INITIAL_CAPITAL
        self.trades = []
        self.equity_curve = []
        self.positions = {}
        self.total_fee_tax = 0.0
        self.total_slippage_cost = 0.0

        for i in range(20, len(data)):
            current = data[i]
            data_slice = data[:i + 1]

            # ── 보유 포지션 청산 체크 ──
            to_close = []
            for pid, pos in self.positions.items():
                cur_price = current['close']
                pnl_rate = (cur_price - pos['buy_price']) / pos['buy_price']

                # 트레일링 스탑
                if trailing_stop:
                    if cur_price > pos.get('highest', pos['buy_price']):
                        pos['highest'] = cur_price
                    trail_price = pos['highest'] * (1 - trailing_pct)
                    if cur_price <= trail_price and pos['highest'] > pos['buy_price'] * 1.005:
                        to_close.append((pid, cur_price, 'trailing_stop'))
                        continue

                if pnl_rate <= stop_loss:
                    to_close.append((pid, cur_price, 'stop_loss'))
                elif pnl_rate >= take_profit:
                    to_close.append((pid, cur_price, 'take_profit'))
                elif (i - pos['entry_bar']) >= max_hold_bars:
                    to_close.append((pid, cur_price, 'time_stop'))

            for pid, sell_price, reason in to_close:
                pos = self.positions.pop(pid)
                amount = sell_price * pos['quantity']
                actual_sell = self.simulate_fill(sell_price, current, 'SELL', amount)
                cost = self.apply_cost(pos['buy_price'], actual_sell, pos['quantity'])
                self.capital += pos['buy_price'] * pos['quantity'] + cost['net_profit']
                self.trades.append({
                    'entry_bar': pos['entry_bar'], 'exit_bar': i,
                    'buy_price': pos['buy_price'], 'sell_price': actual_sell,
                    'quantity': pos['quantity'],
                    'net_profit': cost['net_profit'],
                    'net_profit_rate': cost['net_profit'] / (pos['buy_price'] * pos['quantity']),
                    'exit_reason': reason, 'fee_tax': cost['fee_tax'],
                })

            # ── 신규 진입 체크 ──
            if len(self.positions) < self.MAX_POSITIONS:
                try:
                    buy_signal, score = strategy_check_fn(data_slice)
                except Exception:
                    buy_signal, score = False, 0

                if buy_signal:
                    invest = self.capital * self.POSITION_RATIO
                    order_price = current['close']
                    actual_buy = self.simulate_fill(order_price, current, 'BUY', invest)
                    quantity = int(invest / actual_buy) if actual_buy > 0 else 0
                    if quantity > 0:
                        buy_total = actual_buy * quantity * (1 + self.BUY_FEE)
                        if buy_total <= self.capital:
                            self.capital -= buy_total
                            pid = f"{i}"
                            self.positions[pid] = {
                                'buy_price': actual_buy, 'quantity': quantity,
                                'entry_bar': i, 'highest': actual_buy, 'score': score,
                            }

            # 자산 곡선 기록
            pos_value = sum(p['quantity'] * current['close'] for p in self.positions.values())
            self.equity_curve.append(self.capital + pos_value)

        return self.calc_result()

    def calc_result(self) -> dict:
        """백테스트 결과 집계"""
        if not self.trades:
            return {
                'total_trades': 0, 'win_trades': 0, 'lose_trades': 0,
                'win_rate': 0.0, 'total_profit': 0.0, 'total_profit_rate': 0.0,
                'max_drawdown': 0.0, 'profit_factor': 0.0,
                'avg_win': 0.0, 'avg_loss': 0.0, 'avg_hold_bars': 0.0,
                'total_fee_tax': self.total_fee_tax,
                'total_slippage': self.total_slippage_cost,
                'final_capital': self.capital,
                'equity_curve': self.equity_curve, 'trades': [],
                'exit_reasons': {},
            }

        wins   = [t for t in self.trades if t['net_profit'] > 0]
        losses = [t for t in self.trades if t['net_profit'] <= 0]
        total_win  = sum(t['net_profit'] for t in wins)
        total_loss = abs(sum(t['net_profit'] for t in losses))

        # MDD 계산
        peak = self.INITIAL_CAPITAL
        mdd = 0.0
        for val in self.equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            if dd > mdd:
                mdd = dd

        exit_reasons: dict = {}
        for t in self.trades:
            r = t['exit_reason']
            exit_reasons[r] = exit_reasons.get(r, 0) + 1

        return {
            'total_trades': len(self.trades),
            'win_trades': len(wins),
            'lose_trades': len(losses),
            'win_rate': len(wins) / len(self.trades) * 100,
            'total_profit': sum(t['net_profit'] for t in self.trades),
            'total_profit_rate': (self.capital - self.INITIAL_CAPITAL) / self.INITIAL_CAPITAL * 100,
            'max_drawdown': mdd * 100,
            'profit_factor': total_win / total_loss if total_loss > 0 else float('inf'),
            'avg_win': total_win / len(wins) if wins else 0,
            'avg_loss': total_loss / len(losses) if losses else 0,
            'avg_hold_bars': float(np.mean([t['exit_bar'] - t['entry_bar'] for t in self.trades])),
            'total_fee_tax': self.total_fee_tax,
            'total_slippage': self.total_slippage_cost,
            'final_capital': self.capital,
            'equity_curve': self.equity_curve,
            'trades': self.trades,
            'exit_reasons': exit_reasons,
        }
