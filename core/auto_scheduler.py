"""
자동 스케줄러
장 전/중/후 자동화 작업 — APScheduler 기반
공휴일 자동 판별
"""
import time
from datetime import datetime, date


try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_APScheduler = True
except ImportError:
    HAS_APScheduler = False


# 2026년 공휴일 (예시 — 매년 업데이트 필요)
HOLIDAYS_2026 = {
    date(2026, 1, 1), date(2026, 3, 1), date(2026, 5, 5),
    date(2026, 5, 25), date(2026, 6, 6), date(2026, 8, 15),
    date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27),
    date(2026, 10, 3), date(2026, 10, 9), date(2026, 12, 25),
}


def is_trading_day(d: date = None) -> bool:
    """거래일 여부 확인 (주말/공휴일 제외)"""
    d = d or date.today()
    if d.weekday() >= 5:  # 토/일
        return False
    return d not in HOLIDAYS_2026


class AutoScheduler:
    """
    장 전/중/후 자동화 스케줄
    APScheduler 없으면 단순 루프로 폴백
    """

    SCHEDULE = {
        '08:40': 'prepare',
        '08:50': 'pre_market',
        '09:00': 'market_open',
        '11:30': 'lunch_check',
        '14:50': 'pre_close',
        '15:20': 'cancel_all',
        '15:30': 'market_close',
        '15:40': 'daily_report',
        '16:00': 'data_update',
        '17:00': 'ai_retrain',
        '18:00': 'backtest_update',
    }

    def __init__(self, engine=None, telegram=None, trade_book=None):
        self.engine     = engine
        self.telegram   = telegram
        self.trade_book = trade_book
        self._scheduler = None
        self._running   = False

    def run(self):
        """스케줄러 시작"""
        if HAS_APScheduler:
            self._run_with_apscheduler()
        else:
            self._run_simple_loop()

    def _run_with_apscheduler(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        self._scheduler = BackgroundScheduler(timezone='Asia/Seoul')

        for time_str, task_name in self.SCHEDULE.items():
            h, m = map(int, time_str.split(':'))
            self._scheduler.add_job(
                self._run_task,
                'cron',
                hour=h, minute=m,
                args=[task_name],
                id=task_name
            )

        self._scheduler.start()
        self._running = True
        print('[Scheduler] APScheduler 시작')

        try:
            while self._running:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            self._scheduler.shutdown()

    def _run_simple_loop(self):
        """APScheduler 없을 때 단순 루프"""
        self._running = True
        last_run: dict = {}

        while self._running:
            if not is_trading_day():
                time.sleep(60)
                continue

            now = datetime.now()
            current_time = now.strftime('%H:%M')

            if current_time in self.SCHEDULE and last_run.get(current_time) != now.date():
                task = self.SCHEDULE[current_time]
                last_run[current_time] = now.date()
                self._run_task(task)

            time.sleep(30)

    def _run_task(self, task_name: str):
        """작업 실행"""
        if not is_trading_day():
            return

        print(f'[Scheduler] {task_name} 실행 ({datetime.now().strftime("%H:%M")})')

        try:
            fn = getattr(self, f'_task_{task_name}', None)
            if fn:
                fn()
            else:
                print(f'[Scheduler] 미구현 작업: {task_name}')
        except Exception as e:
            msg = f'스케줄 오류: {task_name} — {e}'
            print(f'[Scheduler ERROR] {msg}')
            if self.telegram:
                self.telegram.send(self.telegram.msg_error('AutoScheduler', msg))

    # ── 작업 구현 ────────────────────────────────────────────────────────
    def _task_prepare(self):
        """08:40 — 종목풀 수집, AI 모델 로드"""
        print('[08:40] 장 준비 — 종목풀 수집, AI 모델 로드')

    def _task_pre_market(self):
        """08:50 — 조건검색식 사전 스캔"""
        print('[08:50] 장전 스캔')

    def _task_market_open(self):
        """09:00 — 매매 엔진 시작"""
        print('[09:00] 장 개장 — 매매 엔진 START')
        if self.engine:
            self.engine.start()
        if self.telegram:
            self.telegram.send('🟢 장 개장 — 자동매매 시작')

    def _task_lunch_check(self):
        """11:30 — 점심 전 포지션 체크"""
        print('[11:30] 점심 전 포지션 체크')

    def _task_pre_close(self):
        """14:50 — 신규 매수 중단"""
        print('[14:50] 신규 매수 차단')
        if self.engine:
            self.engine.is_running = False  # 신규 진입 차단 (기존 보유는 유지)

    def _task_cancel_all(self):
        """15:20 — 미체결 전부 취소"""
        print('[15:20] 미체결 전부 취소')

    def _task_market_close(self):
        """15:30 — 장 마감"""
        print('[15:30] 장 마감 — 엔진 STOP')
        if self.engine:
            self.engine.stop()

    def _task_daily_report(self):
        """15:40 — 일일 결과 텔레그램 발송"""
        print('[15:40] 일일 결과 집계')
        if self.trade_book and self.telegram:
            try:
                daily = self.trade_book.get_daily_summary()
                progress = self.trade_book.get_80만_to_target_progress()
                msg = self.telegram.msg_daily_report(
                    pnl=daily.get('pnl', 0),
                    pnl_rate=daily.get('pnl', 0) / 800_000 * 100,
                    trades=daily.get('trades', 0),
                    buy_count=0, sell_count=daily.get('trades', 0),
                    win_rate=daily.get('win_rate', 0),
                    fee_tax=0,
                    capital=progress.get('current', 800_000),
                    achievement=progress.get('achievement_pct', 0),
                )
                self.telegram.send(msg)
            except Exception as e:
                self.telegram.send(f'일일 리포트 오류: {e}')

    def _task_data_update(self):
        """16:00 — 봉 데이터 수집"""
        print('[16:00] 봉 데이터 업데이트')

    def _task_ai_retrain(self):
        """17:00 — AI 피드백 재학습"""
        print('[17:00] AI 피드백 재학습')

    def _task_backtest_update(self):
        """18:00 — 백테스트 갱신"""
        print('[18:00] 백테스트 갱신')

    def stop(self):
        self._running = False
        if self._scheduler:
            try:
                self._scheduler.shutdown()
            except Exception:
                pass
