"""
주문 최적화기
슬리피지를 최소화하는 최적 주문 실행
- 전략별 최적 매수 타점
- 분할 매수 계획
- 동적 손익분기 계산
"""
import math


class OrderOptimizer:
    """
    슬리피지 최소화 최적 주문 실행
    전략별 매수 타점, 분할 매수, 동적 TP/SL
    """

    # 전략별 호가 오프셋 (틱 단위)
    STRATEGY_OFFSET = {
        'scalping':   0,   # bid1 + 0틱 (빠른 진입)
        'daytrading': 1,   # bid1 + 1틱
        'pullback':   2,   # bid1 + 2틱 (여유 있게)
        'vi_breakout': 2,  # bid1 + 2틱 (못 잡으면 포기)
        'default':    1,
    }

    BUY_FEE  = 0.00015
    SELL_FEE = 0.00015
    TAX      = 0.0023

    def get_tick_size(self, price: int) -> int:
        """KRX 호가 단위"""
        if price < 1_000:     return 1
        elif price < 5_000:   return 5
        elif price < 10_000:  return 10
        elif price < 50_000:  return 50
        elif price < 100_000: return 100
        elif price < 500_000: return 500
        else:                 return 1_000

    def get_buy_price(self, ask1: int, bid1: int, current_price: int,
                      strategy_type: str = 'default') -> int:
        """
        전략별 최적 지정가 매수가
        Returns: int (틱 반올림된 주문가)
        """
        offset_ticks = self.STRATEGY_OFFSET.get(strategy_type, 1)
        tick = self.get_tick_size(bid1)
        price = bid1 + offset_ticks * tick

        # ask1 초과 방지
        return min(price, ask1)

    def split_order(self, total_amount: float, stock_price: int,
                    strategy: str = 'default') -> list:
        """
        분할 매수 계획: 50% → 30% → 20%
        Returns: [{ratio, amount, quantity, reason}, ...]
        """
        splits = [
            (0.50, '1차 확인 진입'),
            (0.30, '2차 추가 확인'),
            (0.20, '3차 최종 확신'),
        ]
        result = []
        for ratio, reason in splits:
            amount = total_amount * ratio
            qty = math.floor(amount / stock_price) if stock_price > 0 else 0
            result.append({
                'ratio': ratio,
                'amount': amount,
                'quantity': qty,
                'reason': reason,
            })
        return result

    def get_sell_price(self, buy_price: int, current_price: int,
                       hold_minutes: int, trailing_high: int = None) -> dict:
        """
        보유 시간에 따른 동적 손익분기 계산
        Returns: {take_profit, stop_loss, trailing_stop, breakeven}
        """
        # 손익분기점 (수수료+세금 포함)
        breakeven = buy_price * (1 + self.BUY_FEE) / (1 - self.SELL_FEE - self.TAX)

        # 보유 시간에 따른 TP/SL
        if hold_minutes < 5:
            tp_rate, sl_rate = 0.010, -0.005
        elif hold_minutes < 30:
            tp_rate, sl_rate = 0.020, -0.010
        else:
            tp_rate, sl_rate = 0.030, -0.020

        tick = self.get_tick_size(buy_price)

        def round_price(p):
            return int(round(p / tick) * tick)

        trailing_stop = None
        if trailing_high:
            trailing_stop = round_price(trailing_high * 0.985)

        return {
            'take_profit': round_price(buy_price * (1 + tp_rate)),
            'stop_loss': round_price(buy_price * (1 + sl_rate)),
            'trailing_stop': trailing_stop,
            'breakeven': round_price(breakeven),
        }

    def calc_position_size(self, capital: float, risk_per_trade: float = 0.02,
                           stop_loss_rate: float = 0.02, buy_price: int = None) -> int:
        """
        켈리 기반 주문 수량 계산
        quantity = (자본 × 리스크 비율) / (매수가 × 손절 비율)
        """
        if not buy_price or buy_price <= 0:
            return 0
        if stop_loss_rate <= 0:
            stop_loss_rate = 0.02

        # 1회 리스크 금액
        risk_amount = capital * risk_per_trade
        # 1주당 리스크 (손절 금액)
        per_share_risk = buy_price * stop_loss_rate

        qty = math.floor(risk_amount / per_share_risk)

        # 최대 50% 제한
        max_qty = math.floor(capital * 0.5 / buy_price)
        return min(qty, max_qty)
