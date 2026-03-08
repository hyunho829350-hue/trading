"""
조건검색식 LV1: 급등초기 포착
목표: 이제 막 오르기 시작하는 종목 포착
수수료+세금+슬리피지 합산 손익분기: +0.5% 이상
"""


class ConditionLv1급등초기:
    """
    급등 초기 포착 조건
    check(stock_data) -> (bool, int score 0~100)
    """

    # 가격 조건
    MIN_PRICE = 2_000       # 2천원 이상 (동전주 제외)
    MAX_PRICE = 30_000      # 3만원 이하 (고가주 제외)
    MIN_CHANGE = 7.0        # 등락률 최소 +7%
    MAX_CHANGE = 20.0       # 등락률 최대 +20% (추격 금지)

    # 거래량/거래대금 조건
    MIN_VOLUME_RATIO = 5.0              # 전일 평균 대비 5배 이상
    MIN_TRADE_AMOUNT = 3_000_000_000    # 30억 이상

    # 시가총액 조건 (중소형주)
    MIN_CAP = 30_000_000_000            # 300억 이상
    MAX_CAP = 300_000_000_000           # 3000억 이하

    # 호가 조건
    MIN_BID_ASK_RATIO = 1.5             # 매수잔량/매도잔량 >= 1.5
    MAX_SPREAD_RATE = 0.003             # 호가 스프레드 <= 0.3%

    def check(self, stock_data: dict) -> tuple:
        """
        급등초기 조건 체크
        stock_data: {
            price, change_rate, volume, avg_volume,
            trade_amount, market_cap,
            bid_qty, ask_qty, ask1, bid1,
            ma5, ma20
        }
        Returns: (passed: bool, score: int)
        """
        try:
            price = stock_data.get('price', 0)
            change_rate = stock_data.get('change_rate', 0)
            volume = stock_data.get('volume', 0)
            avg_volume = stock_data.get('avg_volume', 1)
            trade_amount = stock_data.get('trade_amount', 0)
            market_cap = stock_data.get('market_cap', 0)
            bid_qty = stock_data.get('bid_qty', 0)
            ask_qty = stock_data.get('ask_qty', 1)
            ask1 = stock_data.get('ask1', price)
            bid1 = stock_data.get('bid1', price)
            ma5 = stock_data.get('ma5', 0)
            ma20 = stock_data.get('ma20', 0)

            # ── 하드 필터 (하나라도 실패하면 즉시 False) ──
            if not (self.MIN_PRICE <= price <= self.MAX_PRICE):
                return False, 0
            if not (self.MIN_CHANGE <= change_rate <= self.MAX_CHANGE):
                return False, 0

            volume_ratio = volume / avg_volume if avg_volume > 0 else 0
            if volume_ratio < self.MIN_VOLUME_RATIO:
                return False, 0
            if trade_amount < self.MIN_TRADE_AMOUNT:
                return False, 0
            if market_cap and not (self.MIN_CAP <= market_cap <= self.MAX_CAP):
                return False, 0

            spread_rate = (ask1 - bid1) / price if price > 0 else 1
            if spread_rate > self.MAX_SPREAD_RATE:
                return False, 0

            # ── 점수 계산 ──
            score = 0

            # 거래량 비율 점수
            if volume_ratio >= 10:
                score += 50
            elif volume_ratio >= 5:
                score += 30

            # 호가비율 점수
            bid_ask_ratio = bid_qty / ask_qty if ask_qty > 0 else 0
            if bid_ask_ratio >= 2.0:
                score += 30
            elif bid_ask_ratio >= 1.5:
                score += 20

            # 정배열 (MA5 > MA20, 현재가 > MA5)
            if ma5 > 0 and ma20 > 0 and ma5 > ma20 and price > ma5:
                score += 20

            self.last_score = score
            return score >= 70, score

        except Exception:
            return False, 0
