"""
조건검색식 LV3: 상한가 근접
상한가(30%) 근처 25~29.9% 구간 포착
상한가 매수잔량 100만주 이상 시 추가 상승 가능성
"""


class ConditionLv3상한가근접:
    """
    상한가 근접 조건 (25~29.9%)
    check(stock_data) -> (bool, int score 0~100)
    """

    MIN_CHANGE = 25.0
    MAX_CHANGE = 29.9
    MIN_UPPER_BID = 1_000_000       # 상한가 매수잔량 100만주
    MIN_TRADE_AMOUNT = 5_000_000_000  # 50억
    MIN_CAP = 10_000_000_000         # 100억
    MAX_CAP = 200_000_000_000        # 2000억
    MAX_TRADE_RANK = 50
    MIN_GAP_FROM_OPEN = 0.05         # 시가 대비 +5%

    def check(self, stock_data: dict) -> tuple:
        """
        상한가 근접 조건 체크
        stock_data: {
            price, change_rate, volume, avg_volume,
            trade_amount, market_cap,
            upper_limit_bid, trade_rank, open_price
        }
        Returns: (passed: bool, score: int)
        """
        try:
            price = stock_data.get('price', 0)
            change_rate = stock_data.get('change_rate', 0)
            trade_amount = stock_data.get('trade_amount', 0)
            market_cap = stock_data.get('market_cap', 0)
            upper_limit_bid = stock_data.get('upper_limit_bid', 0)
            trade_rank = stock_data.get('trade_rank', 999)
            open_price = stock_data.get('open_price', price)
            volume = stock_data.get('volume', 0)
            avg_volume = stock_data.get('avg_volume', 1)

            # ── 하드 필터 ──
            if not (self.MIN_CHANGE <= change_rate <= self.MAX_CHANGE):
                return False, 0
            if upper_limit_bid < self.MIN_UPPER_BID:
                return False, 0
            if trade_amount < self.MIN_TRADE_AMOUNT:
                return False, 0
            if market_cap and not (self.MIN_CAP <= market_cap <= self.MAX_CAP):
                return False, 0
            if trade_rank > self.MAX_TRADE_RANK:
                return False, 0

            gap_from_open = (price - open_price) / open_price if open_price > 0 else 0
            if gap_from_open < self.MIN_GAP_FROM_OPEN:
                return False, 0

            # ── 점수 계산 ──
            score = 0

            # 상한가 매수잔량
            if upper_limit_bid >= 2_000_000:
                score += 40
            elif upper_limit_bid >= 1_000_000:
                score += 25

            # 거래대금 순위
            if trade_rank <= 10:
                score += 30
            elif trade_rank <= 30:
                score += 20
            elif trade_rank <= 50:
                score += 10

            # 등락률 구간
            if change_rate >= 28:
                score += 20
            elif change_rate >= 25:
                score += 10

            # 거래량 비율
            volume_ratio = volume / avg_volume if avg_volume > 0 else 0
            if volume_ratio >= 10:
                score += 10

            self.last_score = score
            return score >= 65, score

        except Exception:
            return False, 0
