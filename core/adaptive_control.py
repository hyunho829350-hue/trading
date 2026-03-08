"""
적응형 제어 (켈리 공식)
최근 성과 기반으로 투자 비중 자동 조절
승률 하락 시 비중 축소, 상승 시 확대
"""


class AdaptiveControl:
    """
    켈리 공식 기반 동적 비중 조절
    Half-Kelly 적용으로 안전 마진 확보
    """

    KELLY_SAFETY = 0.5      # 하프켈리
    MIN_RATIO = 0.10        # 최소 비중 10%
    MAX_RATIO = 0.50        # 최대 비중 50%
    LOOKBACK = 20           # 최근 N회 기준

    def __init__(self):
        self._trade_results: list = []  # [(profit, loss)] 리스트

    def record_trade(self, profit: float):
        """매매 결과 기록 (최근 20회 유지)"""
        self._trade_results.append(profit)
        if len(self._trade_results) > self.LOOKBACK * 3:
            self._trade_results = self._trade_results[-self.LOOKBACK * 3:]

    def get_current_performance(self) -> dict:
        """최근 N회 성과 지표"""
        recent = self._trade_results[-self.LOOKBACK:] if len(self._trade_results) >= 5 else self._trade_results
        if not recent:
            return {'win_rate': 0.5, 'avg_win': 0, 'avg_loss': 0, 'profit_factor': 1.0, 'n': 0}

        wins   = [p for p in recent if p > 0]
        losses = [p for p in recent if p <= 0]
        win_rate = len(wins) / len(recent)
        avg_win  = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 1
        pf = (avg_win * win_rate) / (avg_loss * (1 - win_rate)) if avg_loss > 0 and (1 - win_rate) > 0 else 1.0

        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': pf,
            'n': len(recent),
        }

    def get_kelly_ratio(self) -> float:
        """
        켈리 비중 계산 (하프켈리)
        f = (b×p - q) / b  where b=손익비, p=승률, q=1-p
        """
        perf = self.get_current_performance()
        p = perf['win_rate']
        q = 1 - p
        avg_win  = perf['avg_win']
        avg_loss = perf['avg_loss']

        if avg_loss <= 0 or perf['n'] < 5:
            return 0.20  # 데이터 부족 시 기본값 20%

        b = avg_win / avg_loss  # 손익비
        if b <= 0:
            return self.MIN_RATIO

        kelly = (b * p - q) / b
        half_kelly = kelly * self.KELLY_SAFETY

        return max(self.MIN_RATIO, min(self.MAX_RATIO, half_kelly))

    def adjust_aggressiveness(self) -> str:
        """성과에 따라 공격성 자동 조절"""
        perf = self.get_current_performance()
        wr = perf['win_rate']

        if wr >= 0.60:
            return 'aggressive'   # 조건 완화
        elif wr >= 0.40:
            return 'normal'
        elif wr >= 0.30:
            return 'conservative'  # 조건 강화
        else:
            return 'defensive'     # 24시간 보수 모드
