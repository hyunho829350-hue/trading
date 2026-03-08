"""
매매 엔진 (핵심)
Start 버튼 누르면 실행 — 9단계 매매 파이프라인
실시간 126종목 스캔 → 조건 → 필터 → AI → 주문
"""
import time
import threading
from typing import Callable, List

from conditions.condition_manager import ConditionManager
from core.filters.fake_signal_filter import FakeSignalFilter
from core.spread_monitor import SpreadMonitor
from core.risk_manager import RiskManager
from core.adaptive_control import AdaptiveControl
from core.kill_switch import KillSwitch
from core.position_manager import PositionManager
from core.order_optimizer import OrderOptimizer
from core.cost_calculator import CostCalculator
from core.slippage_tracker import SlippageTracker


class TradingEngine:
    """
    전체 자동매매 시스템 몸통
    9단계 매매 파이프라인
    """

    MONITOR_INTERVAL = 180  # 3분 주기 포지션 모니터링
    MAX_HOLD_MINUTES = 120  # 최대 보유 2시간

    def __init__(self, config: dict = None,
                 order_fn: Callable = None,
                 cancel_fn: Callable = None,
                 telegram_fn: Callable = None):
        self.config = config or {}
        self.order_fn   = order_fn    # 실제 주문 함수 (키움 API)
        self.cancel_fn  = cancel_fn   # 주문 취소 함수
        self.telegram   = telegram_fn # 텔레그램 발송

        self.is_running = False
        self.capital = self.config.get('initial_capital', 800_000)

        # 모듈 초기화
        self.condition_mgr  = ConditionManager()
        self.fake_filter    = FakeSignalFilter()
        self.spread_monitor = SpreadMonitor()
        self.risk_manager   = RiskManager(self.capital)
        self.adaptive       = AdaptiveControl()
        self.kill_switch    = KillSwitch(telegram_fn=telegram_fn)
        self.position_mgr   = PositionManager()
        self.order_opt      = OrderOptimizer()
        self.cost_calc      = CostCalculator()
        self.slippage       = SlippageTracker()

        # AI 클라이언트 (선택적 — 없으면 조건점수만 사용)
        self.ai_client = None
        self._monitor_thread = None

    def start(self):
        """매매 엔진 시작"""
        self.is_running = True
        self._log('매매 엔진 시작')
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        """매매 엔진 정지"""
        self.is_running = False
        self._log('매매 엔진 정지')

    # ── 실시간 시세 수신 콜백 ────────────────────────────────────────────
    def on_realtime_data(self, stock_data: dict):
        """
        키움 실시간 시세 수신 시 호출
        9단계 파이프라인 실행
        """
        if not self.is_running:
            return

        stock_code = stock_data.get('stock_code', '')
        if not stock_code:
            return

        # 킬스위치 확인
        if self.kill_switch.is_killed:
            self.kill_switch.auto_resume_check()
            return

        # 이미 보유 중인 종목은 모니터링으로 처리
        if self.position_mgr.has_position(stock_code):
            self._update_position_price(stock_code, stock_data)
            return

        # 매수 가능 여부 체크
        can_buy, reason = self.risk_manager.can_buy(
            self.capital, self.position_mgr.count()
        )
        if not can_buy:
            return

        # ── 1단계: 조건검색식 체크 ──
        results = self.condition_mgr.check_all(stock_data)
        best_condition = next((r for r in results if r['passed']), None)
        if not best_condition:
            return

        # ── 2단계: 가짜 신호 필터 ──
        fake_ok, fake_reason = self.fake_filter.check_all(stock_data)
        if not fake_ok:
            return

        # ── 4단계: 스프레드 체크 ──
        ask1 = stock_data.get('ask1', 0)
        bid1 = stock_data.get('bid1', 0)
        price = stock_data.get('price', 0)
        if price > 0 and ask1 > 0 and bid1 > 0:
            spread = self.spread_monitor.get_spread(ask1, bid1, price)
            if self.slippage.should_skip(stock_code, spread):
                return

        # ── 수익성 체크 (수수료+슬리피지 감안) ──
        expected_gain = price * (1 + 0.01)  # 1% 목표
        if not self.cost_calc.is_worth_trading(price, expected_gain):
            return

        # ── 5단계: AI 판단 (선택적) ──
        ai_signal = 'BUY'
        if self.ai_client:
            try:
                ai_result = self.ai_client.predict(stock_data)
                ai_signal = 'BUY' if ai_result.get('BUY', 0) > 0.65 else 'HOLD'
            except Exception:
                pass

        if ai_signal != 'BUY':
            return

        # ── 6단계: 리스크 체크 ──
        can_buy, reason = self.risk_manager.can_buy(
            self.capital, self.position_mgr.count()
        )
        if not can_buy:
            return

        # ── 7단계: 켈리 비중 결정 ──
        kelly = self.adaptive.get_kelly_ratio()
        invest_amount = self.capital * kelly

        # ── 8단계: 최적 타점 계산 ──
        strategy_type = best_condition['name']
        buy_price = self.order_opt.get_buy_price(ask1, bid1, price, strategy_type)

        stop_loss_rate = abs(self.config.get('stop_loss', 0.02))
        quantity = self.order_opt.calc_position_size(
            invest_amount, stop_loss_rate, stop_loss_rate, buy_price
        )

        if quantity <= 0:
            return

        # ── 9단계: 주문 실행 ──
        self._execute_buy(stock_code, buy_price, quantity,
                          strategy_name=strategy_type,
                          condition_score=best_condition['score'])

    # ── 주문 실행 ────────────────────────────────────────────────────────
    def _execute_buy(self, stock_code: str, buy_price: int, quantity: int,
                     strategy_name: str = '', condition_score: int = 0):
        """매수 주문 실행"""
        try:
            if self.order_fn:
                self.order_fn(stock_code, buy_price, quantity, '매수')
            else:
                self._log(f'[PAPER] 매수 {stock_code} {quantity}주 @{buy_price:,}')

            # 포지션 오픈
            self.position_mgr.open_position(
                stock_code, buy_price, quantity, strategy_name, self.capital
            )
            cost = buy_price * quantity * 1.00015
            self.capital -= cost

            # 기록 및 알림
            self._log(f'✅ 매수 {stock_code} {quantity}주 @{buy_price:,} [{strategy_name}/{condition_score}점]', 'buy')
            if self.telegram:
                self.telegram(
                    f'✅ 매수 체결\n종목: {stock_code}\n'
                    f'가격: {buy_price:,}원 × {quantity}주\n'
                    f'조건: {strategy_name} (score: {condition_score})'
                )
        except Exception as e:
            self._log(f'매수 오류 {stock_code}: {e}', 'error')

    def _execute_sell(self, stock_code: str, sell_price: int, reason: str = ''):
        """매도 주문 실행"""
        pos = self.position_mgr.get_position(stock_code)
        if not pos:
            return
        try:
            if self.order_fn:
                self.order_fn(stock_code, sell_price, pos['quantity'], '매도')
            else:
                self._log(f'[PAPER] 매도 {stock_code} {pos["quantity"]}주 @{sell_price:,} [{reason}]')

            pnl = self.cost_calc.calc_net_profit(pos['buy_price'], sell_price, pos['quantity'])
            self.capital += sell_price * pos['quantity'] * (1 - 0.00015 - 0.0023)
            self.position_mgr.close_position(stock_code)
            self.risk_manager.record_trade(pnl['profit'])
            self.adaptive.record_trade(pnl['profit'])
            self.slippage.record(stock_code, pos['buy_price'], sell_price, 'SELL')

            self._log(f'💰 매도 {stock_code} {pnl["profit_rate"]:+.2f}% [{reason}]',
                      'sell' if pnl['profit'] >= 0 else 'loss')
            if self.telegram:
                self.telegram(
                    f'{"💰" if pnl["profit"] >= 0 else "🔴"} 매도 완료\n'
                    f'종목: {stock_code}\n'
                    f'순수익: {pnl["profit"]:+,.0f}원 ({pnl["profit_rate"]:+.2f}%)\n'
                    f'청산이유: {reason}'
                )

            # 킬스위치 체크
            stats = self.risk_manager.daily_stats
            perf = self.adaptive.get_current_performance()
            self.kill_switch.check(
                win_rate=perf['win_rate'],
                profit_factor=perf['profit_factor'],
                daily_loss_rate=stats['daily_pnl'] / max(self.capital, 1),
                consecutive_losses=stats['consecutive_losses'],
            )

        except Exception as e:
            self._log(f'매도 오류 {stock_code}: {e}', 'error')

    # ── 포지션 모니터링 ──────────────────────────────────────────────────
    def _update_position_price(self, stock_code: str, stock_data: dict):
        price = stock_data.get('price', 0)
        if price:
            self.position_mgr.update_price(stock_code, price)

    def _monitor_loop(self):
        """3분 주기 포지션 모니터링"""
        while self.is_running:
            time.sleep(self.MONITOR_INTERVAL)
            if not self.is_running:
                break
            self._check_all_positions()

    def _check_all_positions(self):
        """모든 보유 종목 손절/익절/시간청산 확인"""
        stop_loss = self.config.get('stop_loss', -0.02)
        take_profit = self.config.get('take_profit', 0.03)
        trailing_pct = self.config.get('trailing_pct', 0.015)

        for code, pos in list(self.position_mgr.get_all_positions().items()):
            cur_price = pos.get('current_price', pos['buy_price'])
            pnl_rate = (cur_price - pos['buy_price']) / pos['buy_price']
            hold_min = self.position_mgr.get_hold_minutes(code)

            # 트레일링 스탑
            trail_price = self.position_mgr.get_trailing_stop_price(code, trailing_pct)
            if trail_price and cur_price <= trail_price and pnl_rate > 0.005:
                self._execute_sell(code, cur_price, '트레일링스탑')
                continue

            # 손절
            if pnl_rate <= stop_loss:
                self._execute_sell(code, cur_price, '손절')
                continue

            # 익절
            if pnl_rate >= take_profit:
                self._execute_sell(code, cur_price, '익절')
                continue

            # 시간 손절 (2시간)
            if hold_min >= self.MAX_HOLD_MINUTES:
                self._execute_sell(code, cur_price, '시간청산')

    def sell_all(self):
        """전체 포지션 즉시 청산"""
        for code, pos in list(self.position_mgr.get_all_positions().items()):
            self._execute_sell(code, pos.get('current_price', pos['buy_price']), '전체매도')

    def _log(self, msg: str, log_type: str = 'info'):
        ts = time.strftime('%H:%M:%S')
        print(f'[{ts}] [{log_type.upper()}] {msg}')
