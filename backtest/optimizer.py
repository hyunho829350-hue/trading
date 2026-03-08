"""
파라미터 최적화기 (그리드 서치)
손절/익절/보유시간 최적 조합 탐색
샤프지수 최대화
"""
import itertools
import numpy as np
from backtest.backtest_engine import BacktestEngine


class Optimizer:
    """백테스트 파라미터 그리드 서치"""

    SEARCH_SPACE = {
        'stop_loss':   [-0.005, -0.010, -0.015, -0.020, -0.025, -0.030],
        'take_profit': [0.010,  0.015,  0.020,  0.030,  0.040,  0.050],
    }
    MIN_TRADES = 30  # 유효 결과 최소 매매 횟수

    def grid_search(self, data: list, strategy_factory,
                    search_space: dict = None) -> list:
        """
        그리드 서치
        strategy_factory(params) -> strategy_check_fn
        Returns: sorted list of result dicts (best first)
        """
        sp = search_space or self.SEARCH_SPACE
        keys = list(sp.keys())
        all_results = []

        for combo in itertools.product(*sp.values()):
            params = dict(zip(keys, combo))

            # 손절 >= 익절 조합 스킵
            sl = params.get('stop_loss', -0.02)
            tp = params.get('take_profit', 0.03)
            if abs(sl) >= tp:
                continue

            try:
                engine = BacktestEngine()
                fn = strategy_factory(params)
                result = engine.run(data, fn,
                                    stop_loss=sl, take_profit=tp)
                if result['total_trades'] < self.MIN_TRADES:
                    continue

                result['params'] = params
                result['sharpe'] = self._calc_sharpe(result)
                all_results.append(result)
            except Exception:
                continue

        all_results.sort(key=lambda x: x.get('sharpe', -float('inf')), reverse=True)
        return all_results

    def _calc_sharpe(self, result: dict) -> float:
        curve = result.get('equity_curve', [])
        if len(curve) < 2:
            return -float('inf')
        rets = np.diff(curve) / np.array(curve[:-1])
        std = float(np.std(rets))
        if std == 0:
            return 0.0
        return float(np.mean(rets) / std * np.sqrt(252 * 78))

    def get_best_params(self, opt_results: list) -> dict:
        """
        최적 파라미터 반환
        상위 10개 중 매매 횟수가 가장 많은 것 (과최적화 방지)
        """
        if not opt_results:
            return {'stop_loss': -0.02, 'take_profit': 0.03}
        top10 = opt_results[:10]
        best = max(top10, key=lambda x: x.get('total_trades', 0))
        return best.get('params', {'stop_loss': -0.02, 'take_profit': 0.03})

    def generate_heatmap_data(self, opt_results: list) -> dict:
        """히트맵 데이터 생성 (stop_loss × take_profit)"""
        sls = sorted(set(r['params']['stop_loss'] for r in opt_results if 'params' in r))
        tps = sorted(set(r['params']['take_profit'] for r in opt_results if 'params' in r))
        heatmap = {}
        for r in opt_results:
            p = r.get('params', {})
            if 'stop_loss' in p and 'take_profit' in p:
                heatmap[(p['stop_loss'], p['take_profit'])] = r.get('win_rate', 0)
        return {'stop_losses': sls, 'take_profits': tps, 'heatmap': heatmap}
