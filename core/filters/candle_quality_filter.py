"""
캔들 품질 필터
캔들 모양으로 진짜 매수세 확인
몸통 비율, 윗꼬리, 거래량+캔들 조합, 연속 캔들 패턴
"""


class CandleQualityFilter:
    """캔들 품질 종합 점수 (0~100), 70 이상 통과"""

    def check_body_ratio(self, open_p: float, high_p: float, low_p: float, close_p: float) -> tuple:
        """
        몸통 비율 검사
        Returns: (passed, ratio, reason)
        """
        total = high_p - low_p
        if total <= 0:
            return False, 0.0, 'doji - zero range'

        body = abs(close_p - open_p)
        ratio = body / total

        if ratio >= 0.5:
            return True, ratio, f'강한 방향성 ({ratio:.1%})'
        elif ratio < 0.3:
            return False, ratio, f'방향성 없음 ({ratio:.1%})'
        return True, ratio, f'보통 방향성 ({ratio:.1%})'

    def check_upper_tail_ratio(self, open_p: float, high_p: float, close_p: float) -> tuple:
        """
        윗꼬리 비율 검사 (양봉 전용)
        Returns: (passed, ratio, reason)
        """
        body = abs(close_p - open_p)
        if body <= 0:
            return False, 0.0, 'zero body'

        upper_tail = high_p - max(open_p, close_p)
        ratio = upper_tail / body

        if ratio <= 0.3:
            return True, ratio, f'윗꼬리 정상 ({ratio:.1%})'
        return False, ratio, f'윗꼬리 과다 ({ratio:.1%}) - 위에서 팔린 흔적'

    def check_volume_candle(self, volume: int, avg_volume: float, is_bullish: bool) -> tuple:
        """
        거래량 + 캔들 조합 검사
        Returns: (passed, description)
        """
        high_vol = volume >= avg_volume

        if is_bullish and high_vol:
            return True, 'bullish+volume - Good'
        elif not is_bullish and not high_vol:
            return True, 'bearish+low_vol - 눌림목 OK'
        elif is_bullish and not high_vol:
            return False, 'bullish+low_vol - 거래량 없는 가짜 반등'
        else:
            return False, 'bearish+high_vol - 매도 압력'

    def check_consecutive_candles(self, candle_history: list) -> tuple:
        """
        연속 캔들 패턴 (최근 3개)
        candle_history: [{'open','high','low','close'}, ...]
        Returns: (passed, score, pattern)
        """
        if len(candle_history) < 3:
            return True, 50, 'insufficient_data'

        last3 = candle_history[-3:]
        bullish = [c['close'] > c['open'] for c in last3]
        total = [c['high'] - c['low'] for c in last3]
        bodies = [abs(c['close'] - c['open']) for c in last3]
        doji = [b / t < 0.05 if t > 0 else True for b, t in zip(bodies, total)]

        if all(bullish):
            return True, 100, '3연속 양봉 - 강한 상승 신호'
        elif sum(bullish[-2:]) == 2:
            return True, 70, '2연속 양봉 - 상승 신호'
        elif sum(doji[-2:]) >= 2:
            return False, 30, '연속 도지 - 방향성 없음'
        elif not bullish[-2] and bullish[-1] and bodies[-1] < bodies[-2] * 0.5:
            return False, 30, '긴 음봉 후 짧은 양봉 - 약한 반등'
        return True, 50, 'neutral'

    def score(self, candle_data: dict) -> tuple:
        """
        종합 점수 반환 (0~100)
        Returns: (passed, score, details)
        """
        open_p  = candle_data.get('open', 0)
        high_p  = candle_data.get('high', 0)
        low_p   = candle_data.get('low', 0)
        close_p = candle_data.get('close', 0)
        volume  = candle_data.get('volume', 0)
        avg_vol = candle_data.get('avg_volume', 1)
        history = candle_data.get('candle_history', [])
        is_bullish = close_p > open_p

        total_score = 0
        details = {}

        # 몸통 비율 (30점)
        br_passed, br_ratio, br_reason = self.check_body_ratio(open_p, high_p, low_p, close_p)
        if br_passed and br_ratio >= 0.5:
            total_score += 30
        elif br_passed:
            total_score += 15
        details['body_ratio'] = br_reason

        # 윗꼬리 (20점)
        if is_bullish:
            ut_passed, ut_ratio, ut_reason = self.check_upper_tail_ratio(open_p, high_p, close_p)
            if ut_passed:
                total_score += 20
            details['upper_tail'] = ut_reason
        else:
            total_score += 10
            details['upper_tail'] = 'skip (음봉)'

        # 거래량 (30점)
        vol_passed, vol_reason = self.check_volume_candle(volume, avg_vol, is_bullish)
        if vol_passed:
            if 'Good' in vol_reason:
                total_score += 30
            else:
                total_score += 10
        details['volume_candle'] = vol_reason

        # 연속 캔들 (20점)
        cc_passed, cc_score, cc_pattern = self.check_consecutive_candles(history)
        if cc_passed:
            if cc_score >= 100:
                total_score += 20
            elif cc_score >= 70:
                total_score += 10
        details['consecutive'] = cc_pattern

        passed = total_score >= 70
        return passed, total_score, details
