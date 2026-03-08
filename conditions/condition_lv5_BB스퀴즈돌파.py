"""
조건검색식 LV5: 볼린저밴드 스퀴즈 돌파
BB가 수축(스퀴즈) 후 폭발하는 순간 포착
횡보 → 돌파 직전의 에너지 응축 상태
"""
import numpy as np


class ConditionLv5BB스퀴즈돌파:
    """
    BB 스퀴즈 돌파 조건
    check(stock_data) -> (bool, int score 0~100)
    """

    BB_PERIOD = 20
    BB_STD = 2.0
    MIN_SQUEEZE_BARS = 5         # 최소 5봉 수축 유지
    MIN_VOLUME_SURGE = 2.0       # 거래량 20봉 평균 2배
    MIN_TRADE_AMOUNT = 2_500_000_000  # 25억
    MAX_SPREAD_RATE = 0.0025     # 0.25%

    def check(self, stock_data: dict) -> tuple:
        """
        BB 스퀴즈 돌파 조건 체크
        stock_data: {
            prices_5min: list (최근 25개 이상),
            volumes_5min: list,
            macd: float,
            macd_signal: float,
            trade_amount: float,
            ask1, bid1, price,
            ma20: float
        }
        Returns: (passed: bool, score: int)
        """
        try:
            prices = stock_data.get('prices_5min', [])
            volumes = stock_data.get('volumes_5min', [])
            macd = stock_data.get('macd', 0)
            macd_signal = stock_data.get('macd_signal', 0)
            trade_amount = stock_data.get('trade_amount', 0)
            ask1 = stock_data.get('ask1', 0)
            bid1 = stock_data.get('bid1', 0)
            price = stock_data.get('price', prices[-1] if prices else 0)
            ma20 = stock_data.get('ma20', 0)

            if len(prices) < self.BB_PERIOD + self.MIN_SQUEEZE_BARS:
                return False, 0

            prices_arr = np.array(prices, dtype=float)
            vols_arr = np.array(volumes, dtype=float) if volumes else np.ones(len(prices))

            # BB 계산 (마지막 20봉)
            def calc_bb(p_arr):
                mid = np.mean(p_arr[-self.BB_PERIOD:])
                std = np.std(p_arr[-self.BB_PERIOD:])
                upper = mid + self.BB_STD * std
                lower = mid - self.BB_STD * std
                width = (upper - lower) / mid if mid > 0 else 0
                return upper, mid, lower, width

            upper, mid, lower, bb_width = calc_bb(prices_arr)

            # 이전 20봉의 BB 폭 계산 (스퀴즈 감지)
            bb_widths = []
            for i in range(self.BB_PERIOD, len(prices_arr) - self.MIN_SQUEEZE_BARS + 1):
                _, _, _, w = calc_bb(prices_arr[:i])
                bb_widths.append(w)

            if not bb_widths:
                return False, 0

            min_bb_width = min(bb_widths)

            # 스퀴즈: 현재 BB 폭이 최소값의 1.1배 이내
            squeeze_detected = bb_width <= min_bb_width * 1.1

            # 스퀴즈 지속 시간 확인
            squeeze_count = 0
            for i in range(len(bb_widths) - 1, -1, -1):
                if bb_widths[i] <= min_bb_width * 1.2:
                    squeeze_count += 1
                else:
                    break

            # ── 하드 필터 ──
            if not squeeze_detected:
                return False, 0
            if squeeze_count < self.MIN_SQUEEZE_BARS:
                return False, 0

            # 현재가가 상단밴드 돌파
            if price <= upper:
                return False, 0

            # 거래량 급증
            if len(vols_arr) >= self.BB_PERIOD:
                vol_avg = np.mean(vols_arr[-self.BB_PERIOD:])
                current_vol = vols_arr[-1]
                vol_surge_ratio = current_vol / vol_avg if vol_avg > 0 else 0
            else:
                vol_surge_ratio = 0

            if vol_surge_ratio < self.MIN_VOLUME_SURGE:
                return False, 0

            if macd <= macd_signal:
                return False, 0

            if ma20 > 0 and price <= ma20:
                return False, 0

            if trade_amount < self.MIN_TRADE_AMOUNT:
                return False, 0

            spread_rate = (ask1 - bid1) / price if price > 0 else 1
            if spread_rate > self.MAX_SPREAD_RATE:
                return False, 0

            # ── 점수 계산 ──
            score = 0

            if squeeze_count >= 10:
                score += 30
            elif squeeze_count >= 5:
                score += 20

            if vol_surge_ratio >= 3.0:
                score += 30
            elif vol_surge_ratio >= 2.0:
                score += 20

            if macd > macd_signal:
                score += 20

            if spread_rate <= 0.001:
                score += 10

            breakout_pct = (price - upper) / upper if upper > 0 else 0
            if breakout_pct > 0.005:
                score += 10

            self.last_score = score
            return score >= 65, score

        except Exception:
            return False, 0
