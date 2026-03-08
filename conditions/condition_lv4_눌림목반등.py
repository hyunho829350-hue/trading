"""
조건검색식 LV4: 눌림목 반등
급등 후 5일선까지 눌린 뒤 반등하는 안전한 진입 패턴
리스크 낮고 손익비 좋음
"""


class ConditionLv4눌림목반등:
    """
    눌림목 반등 조건
    check(stock_data) -> (bool, int score 0~100)
    """

    # 눌림목 범위: MA5 아래 -0.5% ~ -3%
    MIN_DIST_FROM_MA5 = -0.030   # -3%
    MAX_DIST_FROM_MA5 = -0.005   # -0.5%

    MIN_BODY_RATIO = 0.60        # 양봉 몸통 60% 이상
    MIN_VOLUME_RATIO = 1.5       # 거래량 1.5배 이상
    MIN_RSI = 35
    MAX_RSI = 55
    MIN_TRADE_AMOUNT = 2_000_000_000  # 20억
    MAX_SPREAD_RATE = 0.002      # 0.2%
    MAX_CHANGE_TODAY = 5.0       # 오늘 이미 5% 이상 오른 종목 제외

    def check(self, stock_data: dict) -> tuple:
        """
        눌림목 반등 조건 체크
        stock_data: {
            price (=close_price), open_price, high_price, low_price,
            change_rate, volume, prev_avg_volume,
            ma5, ma20, rsi_14,
            trade_amount, ask1, bid1
        }
        Returns: (passed: bool, score: int)
        """
        try:
            price = stock_data.get('price', 0)
            open_p = stock_data.get('open_price', price)
            high_p = stock_data.get('high_price', price)
            low_p = stock_data.get('low_price', price)
            change_rate = stock_data.get('change_rate', 0)
            volume = stock_data.get('volume', 0)
            prev_avg_vol = stock_data.get('prev_avg_volume', 1)
            ma5 = stock_data.get('ma5', 0)
            ma20 = stock_data.get('ma20', 0)
            rsi = stock_data.get('rsi_14', 50)
            trade_amount = stock_data.get('trade_amount', 0)
            ask1 = stock_data.get('ask1', price)
            bid1 = stock_data.get('bid1', price)

            # ── 하드 필터 ──
            if ma5 <= 0:
                return False, 0

            dist_from_ma5 = (price - ma5) / ma5
            if not (self.MIN_DIST_FROM_MA5 <= dist_from_ma5 <= self.MAX_DIST_FROM_MA5):
                return False, 0

            # 현재 캔들 양봉
            if price <= open_p:
                return False, 0

            candle_range = high_p - low_p
            body = price - open_p
            body_ratio = body / candle_range if candle_range > 0 else 0
            if body_ratio < self.MIN_BODY_RATIO:
                return False, 0

            volume_ratio = volume / prev_avg_vol if prev_avg_vol > 0 else 0
            if volume_ratio < self.MIN_VOLUME_RATIO:
                return False, 0

            if ma5 <= 0 or ma20 <= 0 or ma5 <= ma20:
                return False, 0

            if not (self.MIN_RSI <= rsi <= self.MAX_RSI):
                return False, 0

            if trade_amount < self.MIN_TRADE_AMOUNT:
                return False, 0

            spread_rate = (ask1 - bid1) / price if price > 0 else 1
            if spread_rate > self.MAX_SPREAD_RATE:
                return False, 0

            if change_rate > self.MAX_CHANGE_TODAY:
                return False, 0

            # ── 점수 계산 ──
            score = 0

            # 몸통 비율
            if body_ratio >= 0.8:
                score += 30
            elif body_ratio >= 0.6:
                score += 20

            # RSI 최적 구간 (40~50)
            if 40 <= rsi <= 50:
                score += 20

            # 거래량 비율
            if volume_ratio >= 2.0:
                score += 20
            elif volume_ratio >= 1.5:
                score += 10

            # 눌림목 최적 구간 (-1% ~ -2%)
            if -0.02 <= dist_from_ma5 <= -0.01:
                score += 20
            else:
                score += 10

            self.last_score = score
            return score >= 60, score

        except Exception:
            return False, 0
