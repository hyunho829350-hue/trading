"""
비용 계산기
수수료 0.015% + 세금 0.23% = 정확한 실질 순수익 계산
"""


class CostCalculator:
    """
    매매 비용 정확 계산
    - 매수 수수료: 0.015%
    - 매도 수수료: 0.015%
    - 증권거래세(코스닥): 0.23%
    """

    BUY_FEE_RATE  = 0.00015   # 0.015%
    SELL_FEE_RATE = 0.00015   # 0.015%
    TAX_RATE      = 0.0023    # 0.23% (코스닥)
    MIN_NET_PROFIT_RATE = 0.005  # 최소 0.5% 순수익 필요

    def calc_buy_cost(self, price: float, quantity: int) -> dict:
        """매수 총 비용"""
        amount = price * quantity
        fee = amount * self.BUY_FEE_RATE
        return {
            'total': amount + fee,
            'fee': fee,
            'net_amount': amount,
        }

    def calc_sell_revenue(self, price: float, quantity: int) -> dict:
        """매도 실수령액"""
        amount = price * quantity
        fee = amount * self.SELL_FEE_RATE
        tax = amount * self.TAX_RATE
        return {
            'total': amount - fee - tax,
            'fee': fee,
            'tax': tax,
            'net_amount': amount,
        }

    def calc_net_profit(self, buy_price: float, sell_price: float, quantity: int) -> dict:
        """실제 순수익 계산 (수수료+세금 제외)"""
        buy_cost = self.calc_buy_cost(buy_price, quantity)
        sell_rev = self.calc_sell_revenue(sell_price, quantity)

        profit = sell_rev['total'] - buy_cost['total']
        profit_rate = profit / buy_cost['total'] * 100

        return {
            'profit': profit,
            'profit_rate': profit_rate,
            'fee_total': buy_cost['fee'] + sell_rev['fee'],
            'tax_total': sell_rev['tax'],
        }

    def calc_breakeven_price(self, buy_price: float) -> float:
        """
        손익분기 매도가 (이 가격에 팔면 ±0)
        = buy_price × (1 + BUY_FEE) / (1 - SELL_FEE - TAX)
        """
        return buy_price * (1 + self.BUY_FEE_RATE) / (1 - self.SELL_FEE_RATE - self.TAX_RATE)

    def calc_min_target_price(self, buy_price: float, target_profit_rate: float = 0.01) -> float:
        """
        목표 순수익률 달성을 위한 최소 매도가
        기본: 1% 순수익 목표
        """
        breakeven = self.calc_breakeven_price(buy_price)
        return breakeven * (1 + target_profit_rate)

    def is_worth_trading(self, buy_price: float, expected_sell_price: float,
                         slippage_rate: float = 0.002) -> bool:
        """
        이 매매가 할 만한가?
        수수료+세금+슬리피지 감안 최소 +0.5% 이상 이익 예상 시 True
        """
        if buy_price <= 0 or expected_sell_price <= 0:
            return False

        # 예상 순수익률 계산
        gross_return = (expected_sell_price - buy_price) / buy_price
        total_cost = self.BUY_FEE_RATE + self.SELL_FEE_RATE + self.TAX_RATE + slippage_rate
        net_return = gross_return - total_cost

        return net_return >= self.MIN_NET_PROFIT_RATE

    def calc_total_cost_rate(self, slippage_rate: float = 0.002) -> float:
        """왕복 총 비용률"""
        return self.BUY_FEE_RATE + self.SELL_FEE_RATE + self.TAX_RATE + slippage_rate
