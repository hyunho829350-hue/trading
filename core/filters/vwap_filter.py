"""
VWAP 필터
기관 평균 단가 기준 수급 방향 확인
"""
import numpy as np


class VWAPFilter:
    """VWAP 기반 수급 방향 확인"""

    def calc_vwap(self, ohlcv_list: list) -> float:
        """
        당일 VWAP 계산
        ohlcv_list: [{'open','high','low','close','volume'}, ...]
        VWAP = Σ(typical_price × volume) / Σvolume
        """
        total_pv = 0.0
        total_v = 0.0
        for bar in ohlcv_list:
            typical = (bar['high'] + bar['low'] + bar['close']) / 3
            vol = bar.get('volume', 0)
            total_pv += typical * vol
            total_v += vol
        return total_pv / total_v if total_v > 0 else 0.0

    def check_above_vwap(self, current_price: float, vwap: float) -> tuple:
        """
        현재가 > VWAP 확인
        Returns: (passed, distance_pct, reason)
        """
        if vwap <= 0:
            return False, 0.0, 'vwap_unavailable'
        dist = (current_price - vwap) / vwap * 100
        if current_price > vwap:
            return True, dist, f'VWAP 상단 (+{dist:.2f}%)'
        return False, dist, f'VWAP 하단 ({dist:.2f}%)'

    def check_vwap_slope(self, vwap_history: list, window: int = 10) -> tuple:
        """
        VWAP 기울기 (선형 회귀)
        Returns: (direction: 'up'/'down'/'flat', slope_pct)
        """
        if len(vwap_history) < 3:
            return 'flat', 0.0

        recent = np.array(vwap_history[-window:], dtype=float)
        n = len(recent)
        if n < 2 or recent[0] <= 0:
            return 'flat', 0.0

        x = np.arange(n)
        # 선형 회귀 기울기
        slope = float(np.polyfit(x, recent, 1)[0])
        slope_pct = slope / recent[0] * 100 if recent[0] > 0 else 0

        if slope_pct > 0.01:
            return 'up', slope_pct
        elif slope_pct < -0.01:
            return 'down', slope_pct
        return 'flat', slope_pct

    def get_vwap_distance(self, current_price: float, vwap: float) -> dict:
        """
        VWAP 이격도
        Returns: {distance_pct, zone, tradeable}
        """
        if vwap <= 0:
            return {'distance_pct': 0, 'zone': 'unknown', 'tradeable': False}

        dist = (current_price - vwap) / vwap * 100
        if dist > 5.0:
            zone, tradeable = 'overbought', False
        elif dist >= 0:
            zone, tradeable = 'entry', True
        else:
            zone, tradeable = 'below_vwap', False

        return {'distance_pct': dist, 'zone': zone, 'tradeable': tradeable}

    def check(self, current_price: float, ohlcv_list: list, vwap_history: list = None) -> tuple:
        """
        통합 VWAP 체크
        Returns: (passed, score, details)
        """
        vwap = self.calc_vwap(ohlcv_list) if ohlcv_list else 0

        score = 0
        details = {}

        # VWAP 상단 여부 (40점)
        above_passed, dist, reason = self.check_above_vwap(current_price, vwap)
        if above_passed:
            score += 40
        details['above_vwap'] = reason
        details['vwap'] = round(vwap, 2)

        # VWAP 기울기 (30점)
        if vwap_history:
            direction, slope = self.check_vwap_slope(vwap_history)
            if direction == 'up':
                score += 30
            elif direction == 'flat':
                score += 10
            details['slope'] = f'{direction} ({slope:.3f}%/bar)'
        else:
            score += 15  # 데이터 없으면 중립

        # 이격도 최적 구간 (30점)
        dist_info = self.get_vwap_distance(current_price, vwap)
        if dist_info['zone'] == 'entry':
            score += 30
        details['distance'] = dist_info

        passed = score >= 60 and above_passed
        return passed, score, details
