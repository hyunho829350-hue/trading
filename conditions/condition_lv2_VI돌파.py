"""
조건검색식 LV2: VI(변동성완화장치) 돌파
VI 해제 직후 120초 이내 포착 → 폭발적 상승 노림
"""
import time


class ConditionLv2VI돌파:
    """
    VI 해제 후 2분 이내 포착 조건
    check(stock_data) -> (bool, int score 0~100)
    """

    VI_TIMEOUT_SEC = 120        # VI 해제 후 유효 시간
    MIN_CHANGE = 10.0           # 최소 +10% 상승 중
    MIN_VOLUME_RATIO = 5.0
    MIN_TRADE_AMOUNT = 3_000_000_000  # 30억
    MAX_SPREAD_RATE = 0.005     # 0.5% (VI 직후 스프레드 넓어짐)

    def check(self, stock_data: dict) -> tuple:
        """
        VI 돌파 조건 체크
        stock_data: {
            vi_released: bool,
            vi_release_time: float (timestamp),
            vi_trigger_price: int,
            current_time: float (timestamp),
            price, change_rate, volume, avg_volume,
            trade_amount, ask1, bid1
        }
        Returns: (passed: bool, score: int)
        """
        try:
            vi_released = stock_data.get('vi_released', False)
            vi_release_time = stock_data.get('vi_release_time', 0)
            vi_trigger_price = stock_data.get('vi_trigger_price', 0)
            current_time = stock_data.get('current_time', time.time())
            price = stock_data.get('price', 0)
            change_rate = stock_data.get('change_rate', 0)
            volume = stock_data.get('volume', 0)
            avg_volume = stock_data.get('avg_volume', 1)
            trade_amount = stock_data.get('trade_amount', 0)
            ask1 = stock_data.get('ask1', price)
            bid1 = stock_data.get('bid1', price)

            # ── 하드 필터 ──
            if not vi_released:
                return False, 0

            elapsed = current_time - vi_release_time
            if elapsed > self.VI_TIMEOUT_SEC:
                return False, 0

            if vi_trigger_price > 0 and price < vi_trigger_price:
                return False, 0

            if change_rate < self.MIN_CHANGE:
                return False, 0

            volume_ratio = volume / avg_volume if avg_volume > 0 else 0
            if volume_ratio < self.MIN_VOLUME_RATIO:
                return False, 0

            if trade_amount < self.MIN_TRADE_AMOUNT:
                return False, 0

            spread_rate = (ask1 - bid1) / price if price > 0 else 1
            if spread_rate > self.MAX_SPREAD_RATE:
                return False, 0

            # ── 점수 계산 ──
            score = 0

            # VI 해제 후 경과 시간 (빠를수록 고점수)
            if elapsed < 30:
                score += 40
            elif elapsed < 60:
                score += 30
            elif elapsed < 120:
                score += 20

            # 등락률
            if change_rate >= 15:
                score += 30
            elif change_rate >= 10:
                score += 20

            # 거래량
            if volume_ratio >= 10:
                score += 20

            # 스프레드 타이트 보너스
            if spread_rate <= 0.002:
                score += 10

            self.last_score = score
            return score >= 60, score

        except Exception:
            return False, 0
