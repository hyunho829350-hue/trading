"""
호가 스프레드 모니터
실시간 스프레드 감시 → 슬리피지 큰 종목 자동 차단
"""


class SpreadMonitor:
    """
    실시간 호가 스프레드 감시
    - 스프레드 계산
    - 시장 충격 계산
    - 최적 주문 방식 결정
    """

    WARN_SPREAD = 0.003    # 0.3% 경고
    BLOCK_SPREAD = 0.005   # 0.5% 차단

    def get_spread(self, ask1: int, bid1: int, current_price: int) -> float:
        """스프레드율 계산"""
        if current_price <= 0:
            return 1.0
        return (ask1 - bid1) / current_price

    def get_market_impact(self, order_qty: int, ask_volumes: list) -> float:
        """
        내 주문이 호가에 미치는 충격 계산
        ask_volumes: [(price, qty), ...] 매도 호가 목록 (낮은 가격 우선)
        Returns: 충격 비율 (0.002 = 0.2%)
        """
        if not ask_volumes or order_qty <= 0:
            return 0.0

        remaining = order_qty
        base_price = ask_volumes[0][0] if ask_volumes else 0
        if base_price <= 0:
            return 0.0

        last_price = base_price
        for price, qty in ask_volumes:
            if remaining <= 0:
                break
            remaining -= qty
            last_price = price

        if base_price > 0:
            return (last_price - base_price) / base_price
        return 0.0

    def get_optimal_order_type(self, spread_rate: float, urgency: bool = False) -> dict:
        """
        스프레드에 따른 최적 주문 방식 결정
        Returns: {type, price_offset_ticks, reason}
        """
        if urgency:
            return {'type': 'limit', 'price_offset_ticks': 2, 'reason': 'VI해제 긴급진입'}

        if spread_rate < 0.001:
            return {'type': 'limit', 'price_offset_ticks': 0, 'reason': '타이트 스프레드 - bid1 진입'}
        elif spread_rate <= 0.003:
            return {'type': 'limit', 'price_offset_ticks': 1, 'reason': '보통 스프레드 - bid1+1틱'}
        else:
            return {'type': 'skip', 'price_offset_ticks': 0, 'reason': f'스프레드 {spread_rate*100:.2f}% 초과 - 진입 포기'}

    def watch(self, stock_code: str, ask1: int, bid1: int, current_price: int,
              has_position: bool = False) -> dict:
        """
        실시간 스프레드 모니터링
        Returns: {alert, action, spread_rate}
        """
        spread_rate = self.get_spread(ask1, bid1, current_price)

        if spread_rate > 0.01 and has_position:
            return {'alert': True, 'action': 'sell_immediately', 'spread_rate': spread_rate}
        elif spread_rate > 0.005 and has_position:
            return {'alert': True, 'action': 'sell_soon', 'spread_rate': spread_rate}
        elif spread_rate > self.BLOCK_SPREAD:
            return {'alert': True, 'action': 'avoid_entry', 'spread_rate': spread_rate}
        elif spread_rate > self.WARN_SPREAD:
            return {'alert': True, 'action': 'caution', 'spread_rate': spread_rate}
        else:
            return {'alert': False, 'action': 'normal', 'spread_rate': spread_rate}

    def calc_effective_buy_price(self, bid1: int, spread_rate: float, urgency: bool = False) -> float:
        """스프레드 감안 실질 예상 체결가"""
        if urgency:
            return bid1 * (1 + spread_rate * 0.8)  # 스프레드의 80% 만큼 불리하게 체결
        return bid1 * (1 + spread_rate * 0.5)
