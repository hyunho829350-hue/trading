"""
워크포워드 분석
과적합 방지: In-Sample 학습 → Out-of-Sample 검증
"""
import numpy as np
from backtest.backtest_engine import BacktestEngine


class WalkForward:
    """슬라이딩 윈도우 워크포워드 검증"""

    def __init__(self, train_months: int = 4, test_months: int = 2,
                 bars_per_day: int = 78):
        self.train_months = train_months
        self.test_months = test_months
        self.bars_per_month = bars_per_day * 22  # 월 22거래일
        self.results = []

    def run(self, data: list, strategy_factory, total_months: int = 12) -> dict:
        """워크포워드 실행"""
        monthly = self._split_by_months(data)
        window_results = []

        for start in range(0, max(1, len(monthly) - self.train_months - self.test_months + 1)):
            train_end = start + self.train_months
            test_end = train_end + self.test_months

            if test_end > len(monthly):
                break

            train_data = [bar for chunk in monthly[start:train_end] for bar in chunk]
            test_data  = [bar for chunk in monthly[train_end:test_end] for bar in chunk]

            if len(train_data) < 100 or len(test_data) < 20:
                continue

            best_params = self.optimize_params(train_data, strategy_factory)
            test_result = self.validate(test_data, strategy_factory, best_params)

            window_results.append({
                'window': start,
                'best_params': best_params,
                'test_result': test_result,
                'profitable': test_result.get('total_profit', 0) > 0,
            })

        self.results = window_results
        stability = self.calc_stability_score(window_results)
        avg_wr = float(np.mean([r['test_result'].get('win_rate', 0) for r in window_results])) if window_results else 0
        avg_pr = float(np.mean([r['test_result'].get('total_profit_rate', 0) for r in window_results])) if window_results else 0

        return {
            'windows': window_results,
            'stability_score': stability,
            'avg_win_rate': avg_wr,
            'avg_profit_rate': avg_pr,
        }

    def _split_by_months(self, data: list) -> list:
        chunks = []
        i = 0
        while i < len(data):
            chunks.append(data[i:i + self.bars_per_month])
            i += self.bars_per_month
        return [c for c in chunks if c]

    def optimize_params(self, train_data: list, factory) -> dict:
        """학습 구간에서 파라미터 최적화 (그리드 서치)"""
        best_sharpe = -float('inf')
        best_params = {'stop_loss': -0.02, 'take_profit': 0.03, 'trailing_pct': 0.015}

        for sl in [-0.010, -0.015, -0.020, -0.025]:
            for tp in [0.020, 0.030, 0.040]:
                if abs(sl) >= tp:
                    continue
                params = {'stop_loss': sl, 'take_profit': tp, 'trailing_pct': 0.015}
                try:
                    engine = BacktestEngine()
                    fn = factory(params)
                    result = engine.run(train_data, fn,
                                        stop_loss=sl, take_profit=tp,
                                        trailing_pct=0.015)
                    if result['total_trades'] < 5:
                        continue
                    sharpe = self._calc_sharpe(result)
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = params
                except Exception:
                    continue

        return best_params

    def _calc_sharpe(self, result: dict) -> float:
        curve = result.get('equity_curve', [])
        if len(curve) < 2:
            return -float('inf')
        rets = np.diff(curve) / np.array(curve[:-1])
        if np.std(rets) == 0:
            return 0.0
        return float(np.mean(rets) / np.std(rets) * np.sqrt(252 * 78))

    def validate(self, test_data: list, factory, params: dict) -> dict:
        engine = BacktestEngine()
        fn = factory(params)
        return engine.run(test_data, fn,
                          stop_loss=params.get('stop_loss', -0.02),
                          take_profit=params.get('take_profit', 0.03),
                          trailing_pct=params.get('trailing_pct', 0.015))

    def calc_stability_score(self, results: list) -> float:
        if not results:
            return 0.0
        profitable = sum(1 for r in results if r.get('profitable', False))
        return profitable / len(results) * 100
