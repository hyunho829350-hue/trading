"""
조건 매니저: 6개 조건검색식 통합 관리
쿨다운(10분), 통계, 최적 종목 탐색
"""
import time
from conditions.condition_lv1_급등초기 import ConditionLv1급등초기
from conditions.condition_lv2_VI돌파 import ConditionLv2VI돌파
from conditions.condition_lv3_상한가근접 import ConditionLv3상한가근접
from conditions.condition_lv4_눌림목반등 import ConditionLv4눌림목반등
from conditions.condition_lv5_BB스퀴즈돌파 import ConditionLv5BB스퀴즈돌파
from conditions.condition_lv6_골든크로스 import ConditionLv6골든크로스


class ConditionManager:
    """
    6개 조건검색식 통합 관리
    - 쿨다운: 동일 종목 10분 내 재포착 차단
    - 통계: 조건별 승률/수익 추적
    """

    COOLDOWN_MINUTES = 10

    def __init__(self):
        self.conditions = {
            '급등초기':    ConditionLv1급등초기(),
            'VI돌파':      ConditionLv2VI돌파(),
            '상한가근접':  ConditionLv3상한가근접(),
            '눌림목반등':  ConditionLv4눌림목반등(),
            'BB스퀴즈돌파': ConditionLv5BB스퀴즈돌파(),
            '골든크로스':  ConditionLv6골든크로스(),
        }

        # 쿨다운 추적: {stock_code: {condition_name: last_trigger_time}}
        self._cooldowns: dict = {}

        # 통계: {condition_name: {total, passed, win_count, total_pnl}}
        self.stats: dict = {
            name: {'total': 0, 'passed': 0, 'win_count': 0, 'total_pnl': 0.0}
            for name in self.conditions
        }

    # ── 쿨다운 관리 ──────────────────────────────────────────────────────
    def _is_in_cooldown(self, stock_code: str, condition_name: str) -> bool:
        last = self._cooldowns.get(stock_code, {}).get(condition_name, 0)
        return (time.time() - last) < self.COOLDOWN_MINUTES * 60

    def set_cooldown(self, stock_code: str, condition_name: str):
        if stock_code not in self._cooldowns:
            self._cooldowns[stock_code] = {}
        self._cooldowns[stock_code][condition_name] = time.time()

    # ── 조건 체크 ────────────────────────────────────────────────────────
    def check_all(self, stock_data: dict) -> list:
        """
        6개 조건 모두 체크
        Returns: list of {name, passed, score}
        """
        stock_code = stock_data.get('stock_code', '')
        results = []

        for name, cond in self.conditions.items():
            self.stats[name]['total'] += 1

            if stock_code and self._is_in_cooldown(stock_code, name):
                results.append({'name': name, 'passed': False, 'score': 0, 'reason': 'cooldown'})
                continue

            try:
                passed, score = cond.check(stock_data)
            except Exception:
                passed, score = False, 0

            if passed:
                self.stats[name]['passed'] += 1
                if stock_code:
                    self.set_cooldown(stock_code, name)

            results.append({'name': name, 'passed': passed, 'score': score})

        return results

    def get_best(self, stock_list: list) -> dict | None:
        """
        여러 종목 중 가장 높은 점수로 통과한 종목 반환
        stock_list: list of stock_data dicts
        Returns: dict {stock_data, condition_name, score} or None
        """
        best = None
        best_score = 0

        for stock_data in stock_list:
            results = self.check_all(stock_data)
            for r in results:
                if r['passed'] and r['score'] > best_score:
                    best_score = r['score']
                    best = {
                        'stock_data': stock_data,
                        'condition_name': r['name'],
                        'score': r['score'],
                    }

        return best

    def record_result(self, condition_name: str, stock_code: str, was_profitable: bool, pnl: float = 0.0):
        """
        매매 결과 기록 → 조건별 승률 추적
        """
        if condition_name in self.stats:
            if was_profitable:
                self.stats[condition_name]['win_count'] += 1
            self.stats[condition_name]['total_pnl'] += pnl

    def get_stats(self) -> dict:
        """
        조건별 성과 통계 반환
        Returns: {condition_name: {total, passed, pass_rate, win_count, win_rate, total_pnl}}
        """
        result = {}
        for name, s in self.stats.items():
            passed = s['passed']
            win = s['win_count']
            result[name] = {
                'total_checks': s['total'],
                'passed': passed,
                'pass_rate': passed / s['total'] * 100 if s['total'] > 0 else 0,
                'win_count': win,
                'win_rate': win / passed * 100 if passed > 0 else 0,
                'total_pnl': s['total_pnl'],
                'avg_pnl': s['total_pnl'] / passed if passed > 0 else 0,
            }
        return result
