"""
가짜 신호 필터 (8가지)
가짜 상승 패턴 차단 → 진짜 급등만 통과
"""


class FakeSignalFilter:
    """8가지 가짜 상승 패턴 필터"""

    def check_volume_fake(self, volume: int, avg_volume: float, price_change_rate: float) -> tuple:
        """① 거래량 없는 상승 차단"""
        if avg_volume <= 0:
            return True, None
        if volume < avg_volume * 0.5 and price_change_rate > 0:
            return False, '거래량없는상승'
        return True, None

    def check_upper_tail(self, open_p: float, high_p: float, close_p: float, low_p: float) -> tuple:
        """② 윗꼬리 긴 양봉 차단"""
        body = abs(close_p - open_p)
        upper_tail = high_p - max(open_p, close_p)
        total = high_p - low_p

        if body > 0 and upper_tail / body > 2.0:
            return False, '윗꼬리양봉'
        if total > 0 and upper_tail / total > 0.6:
            return False, '윗꼬리과다'
        return True, None

    def check_gap_fill(self, prev_close: float, open_p: float, current_price: float) -> tuple:
        """③ 갭상승 후 갭채우기 진행 중 차단"""
        if prev_close <= 0:
            return True, None
        gap = (open_p - prev_close) / prev_close
        if gap > 0.02 and current_price < open_p * 0.99:
            return False, '갭채우기진행중'
        return True, None

    def check_overheated(self, change_rate: float, volume_ratio: float) -> tuple:
        """④ 과열 급등 차단"""
        if change_rate >= 20.0:
            return False, '과열급등(+20%초과)'
        if change_rate >= 15.0 and volume_ratio >= 10.0:
            return False, '과열급등(거래량10배+15%)'
        return True, None

    def check_manipulation(self, market_cap: int, trade_amount: int) -> tuple:
        """⑤ 소형주 작전 의심 차단"""
        if market_cap and market_cap < 30_000_000_000:  # 300억 미만
            if market_cap > 0 and trade_amount / market_cap > 0.3:
                return False, '소형주작전의심'
        return True, None

    def check_weak_execution(self, execution_strength: float) -> tuple:
        """⑥ 체결강도 약한 종목 차단 (100 미만 = 매도 우위)"""
        if execution_strength < 100:
            return False, '체결강도약함'
        return True, None

    def check_high_reversal_risk(self, high_52week: float, current_price: float) -> tuple:
        """⑦ 52주 고점 근처 반전 위험 차단"""
        if high_52week > 0 and current_price >= high_52week * 0.95:
            return False, '52주고점근접'
        return True, None

    def check_gap_down_after_surge(self, prev_high: float, open_p: float) -> tuple:
        """⑧ 급등 후 갭하락 패턴 차단"""
        if prev_high > 0 and (prev_high - open_p) / prev_high >= 0.03:
            return False, '급등후갭하락'
        return True, None

    def check_all(self, stock_data: dict) -> tuple:
        """
        8개 필터 모두 실행 → 하나라도 걸리면 False
        Returns: (passed: bool, failed_filter: str or None)
        """
        volume = stock_data.get('volume', 0)
        avg_volume = stock_data.get('avg_volume', 1)
        change_rate = stock_data.get('change_rate', 0)
        open_p = stock_data.get('open_price', 0)
        high_p = stock_data.get('high_price', 0)
        low_p = stock_data.get('low_price', 0)
        close_p = stock_data.get('close_price', stock_data.get('price', 0))
        prev_close = stock_data.get('prev_close', 0)
        current_price = close_p
        market_cap = stock_data.get('market_cap', 0)
        trade_amount = stock_data.get('trade_amount', 0)
        exec_strength = stock_data.get('execution_strength', 100)
        high_52w = stock_data.get('high_52week', 0)
        prev_high = stock_data.get('prev_high', 0)
        volume_ratio = volume / avg_volume if avg_volume > 0 else 0

        checks = [
            self.check_volume_fake(volume, avg_volume, change_rate),
            self.check_upper_tail(open_p, high_p, close_p, low_p),
            self.check_gap_fill(prev_close, open_p, current_price),
            self.check_overheated(change_rate, volume_ratio),
            self.check_manipulation(market_cap, trade_amount),
            self.check_weak_execution(exec_strength),
            self.check_high_reversal_risk(high_52w, current_price),
            self.check_gap_down_after_surge(prev_high, open_p),
        ]

        for passed, reason in checks:
            if not passed:
                return False, reason

        return True, None
