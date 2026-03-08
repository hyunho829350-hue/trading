"""
조건검색식 LV6: 골든크로스
5일선이 20일선을 상향 돌파하는 순간 포착
중기 추세 전환 신호
"""


class ConditionLv6골든크로스:
    """
    골든크로스 조건 (MA5 오늘 MA20 상향 돌파)
    check(stock_data) -> (bool, int score 0~100)
    """

    MIN_VOLUME_RATIO = 1.5
    MIN_RSI = 45
    MAX_RSI = 70
    MAX_GAP_RATE = 2.0          # 갭상승 2% 초과 시 포기

    def check(self, stock_data: dict) -> tuple:
        """
        골든크로스 조건 체크
        stock_data: {
            price,
            ma5_today, ma5_yesterday,
            ma20_today, ma20_yesterday,
            ma60,
            rsi_14,
            volume_ratio,
            gap_rate,
            change_rate
        }
        Returns: (passed: bool, score: int)
        """
        try:
            price = stock_data.get('price', 0)
            ma5_today = stock_data.get('ma5_today', 0)
            ma5_yesterday = stock_data.get('ma5_yesterday', 0)
            ma20_today = stock_data.get('ma20_today', 0)
            ma20_yesterday = stock_data.get('ma20_yesterday', 0)
            ma60 = stock_data.get('ma60', 0)
            rsi = stock_data.get('rsi_14', 50)
            volume_ratio = stock_data.get('volume_ratio', 0)
            gap_rate = stock_data.get('gap_rate', 0)

            # ── 하드 필터 ──
            # 오늘 골든크로스 발생 (5일선이 오늘 20일선 돌파)
            if ma5_today <= ma20_today:
                return False, 0
            if ma5_yesterday > ma20_yesterday:
                return False, 0  # 어제 이미 골든크로스였으면 신규 신호 아님

            # 60일선 위 (대세 상승)
            if ma60 > 0 and price <= ma60:
                return False, 0

            if volume_ratio < self.MIN_VOLUME_RATIO:
                return False, 0

            if not (self.MIN_RSI <= rsi <= self.MAX_RSI):
                return False, 0

            # 갭상승 2% 초과 시 추격 위험
            if gap_rate > self.MAX_GAP_RATE:
                return False, 0

            # ── 점수 계산 ──
            score = 0

            if volume_ratio >= 2.0:
                score += 30
            elif volume_ratio >= 1.5:
                score += 20

            # 60일선 이격도
            if ma60 > 0:
                dist_60 = (price - ma60) / ma60 * 100
                if dist_60 > 2.0:
                    score += 20

            # RSI 최적 구간
            if 50 <= rsi <= 65:
                score += 20

            # MA5와 MA20의 이격
            if ma20_today > 0:
                ma_gap = (ma5_today - ma20_today) / ma20_today
                if ma_gap >= 0.01:
                    score += 20

            # 갭 없음 보너스 (더 안정적)
            if gap_rate <= 0:
                score += 10

            self.last_score = score
            return score >= 60, score

        except Exception:
            return False, 0
