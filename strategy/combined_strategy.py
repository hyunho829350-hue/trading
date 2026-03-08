"""
14개 전략 통합 투표
소자본 특화: 스캘핑/거래량 가중치 2배
"""


class CombinedStrategy:
    """
    14개 전략 투표 통합 관리
    합산 점수 60 이상 → BUY 신호
    """

    STRATEGY_NAMES = [
        'pullback', 'volume', 'ma_breakout', 'gap', 'rsi',
        'scalping', 'daytrading', 'trend', 'supply', 'resistance',
        'box', 'fallen', 'swing', 'daily',
    ]

    # 소자본 특화 가중치
    WEIGHTS = {
        'scalping':    2.0,
        'volume':      1.8,
        'ma_breakout': 1.5,
        'pullback':    1.5,
        'resistance':  1.3,
    }
    DEFAULT_WEIGHT = 1.0
    BUY_THRESHOLD = 60.0  # 점수 기준

    def _get_weight(self, name: str) -> float:
        return self.WEIGHTS.get(name, self.DEFAULT_WEIGHT)

    def _check_pullback(self, data: dict) -> float:
        """눌림목 반등: 5일선 터치 후 양봉 회복"""
        price = data.get('price', 0)
        ma5   = data.get('ma5', 0)
        ma20  = data.get('ma20', 0)
        open_p = data.get('open_price', price)
        rsi  = data.get('rsi_14', 50)
        if ma5 > 0 and ma20 > 0 and ma5 > ma20:
            dist = (price - ma5) / ma5
            if -0.03 <= dist <= 0 and price > open_p and 35 <= rsi <= 55:
                return 0.75
        return 0.0

    def _check_volume(self, data: dict) -> float:
        """거래량 폭발: 전일 대비 3배 이상 + 양봉"""
        volume = data.get('volume', 0)
        avg_vol = data.get('avg_volume', 1)
        price = data.get('price', 0)
        open_p = data.get('open_price', price)
        ratio = volume / avg_vol if avg_vol > 0 else 0
        if ratio >= 3 and price > open_p:
            return min(ratio / 10, 1.0)
        return 0.0

    def _check_ma_breakout(self, data: dict) -> float:
        """이평선 돌파: 60일선 상향 돌파"""
        price = data.get('price', 0)
        ma60  = data.get('ma60', 0)
        prev  = data.get('prev_price', price)
        if ma60 > 0 and price > ma60 and prev <= ma60:
            return 0.80
        return 0.0

    def _check_gap(self, data: dict) -> float:
        """갭상승: 전일종가 대비 +2% 이상"""
        change = data.get('gap_rate', 0)
        if change >= 2.0:
            return min(change / 5, 1.0)
        return 0.0

    def _check_rsi(self, data: dict) -> float:
        """RSI 반등: 30 이하 과매도 후 반등"""
        rsi = data.get('rsi_14', 50)
        if rsi <= 30:
            return (30 - rsi) / 30
        return 0.0

    def _check_scalping(self, data: dict) -> float:
        """스캘핑: 1분봉 기준 초단기 변동성"""
        change = data.get('change_rate', 0)
        vol_ratio = data.get('volume_ratio', 1)
        if 1.0 <= change <= 5.0 and vol_ratio >= 3.0:
            return min(change / 5, 1.0)
        return 0.0

    def _check_trend(self, data: dict) -> float:
        """추세 추종: 5/20/60 정배열"""
        ma5  = data.get('ma5', 0)
        ma20 = data.get('ma20', 0)
        ma60 = data.get('ma60', 0)
        price = data.get('price', 0)
        if ma5 > 0 and ma20 > 0 and ma60 > 0 and ma5 > ma20 > ma60 and price > ma5:
            return 0.70
        return 0.0

    def _check_generic(self, data: dict, name: str) -> float:
        """나머지 전략 기본 구현"""
        change = data.get('change_rate', 0)
        vol_ratio = data.get('volume_ratio', 1)
        if change > 0 and vol_ratio > 1.5:
            return 0.50
        return 0.0

    def vote(self, stock_data: dict) -> tuple:
        """
        14개 전략 투표
        Returns: (buy_signal: bool, total_score: float, voted_strategies: list)
        """
        scores = {}
        check_fns = {
            'pullback':    self._check_pullback,
            'volume':      self._check_volume,
            'ma_breakout': self._check_ma_breakout,
            'gap':         self._check_gap,
            'rsi':         self._check_rsi,
            'scalping':    self._check_scalping,
            'trend':       self._check_trend,
        }

        for name in self.STRATEGY_NAMES:
            fn = check_fns.get(name, lambda d, n=name: self._check_generic(d, n))
            try:
                raw_score = fn(stock_data)
            except Exception:
                raw_score = 0.0
            weighted = raw_score * self._get_weight(name) * 100
            scores[name] = weighted

        total = sum(scores.values())
        voted = [n for n, s in scores.items() if s > 30]
        return total >= self.BUY_THRESHOLD, total, voted

    def get_sell_signal(self, position: dict, current_data: dict) -> bool:
        """보유 중 매도 신호 (과반 전략이 매도 의견 시)"""
        price = current_data.get('price', 0)
        buy_price = position.get('buy_price', price)
        if buy_price <= 0:
            return False

        sell_votes = 0
        rsi = current_data.get('rsi_14', 50)
        change = current_data.get('change_rate', 0)

        if rsi >= 75:
            sell_votes += 3
        if change <= -2:
            sell_votes += 4
        pnl_rate = (price - buy_price) / buy_price * 100
        if pnl_rate >= 3:
            sell_votes += 5  # 수익 나면 익절 권장

        return sell_votes >= 5
