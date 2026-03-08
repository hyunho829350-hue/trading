"""
킬 스위치
자동매매 긴급 정지 시스템
승률/손익비/연속손절/지수급락 시 즉시 전체 정지
"""
import datetime
from typing import Callable


class KillSwitch:
    """
    긴급 정지 트리거
    발동 시: 신규 매수 차단 → 미체결 취소 → 보유 청산 (선택)
    """

    TRIGGERS = {
        'win_rate_min':      0.15,   # 승률 15% 미만
        'profit_factor_min': 1.0,    # 손익비 1.0 미만
        'daily_loss_max':   -0.05,   # 일손실 -5%
        'consecutive_loss':  5,      # 5연패
        'index_crash':      -0.03,   # 코스피 -3%
    }

    COOLDOWN_MINUTES = 30   # 발동 후 30분 자동 재개

    def __init__(self, telegram_fn: Callable = None, sell_all_fn: Callable = None):
        self.is_killed = False
        self.kill_reason = ''
        self.killed_at = None
        self._telegram = telegram_fn
        self._sell_all = sell_all_fn

    def check(self, win_rate: float = 1.0, profit_factor: float = 2.0,
              daily_loss_rate: float = 0.0, consecutive_losses: int = 0,
              index_change: float = 0.0) -> bool:
        """
        모든 트리거 체크
        Returns: True if kill switch activated
        """
        if self.is_killed:
            return True

        reason = None

        if win_rate < self.TRIGGERS['win_rate_min']:
            reason = f'승률 {win_rate*100:.0f}% — 기준치 미달'
        elif profit_factor < self.TRIGGERS['profit_factor_min']:
            reason = f'손익비 {profit_factor:.2f} — 기준치 미달'
        elif daily_loss_rate <= self.TRIGGERS['daily_loss_max']:
            reason = f'일손실 {daily_loss_rate*100:.1f}% 초과'
        elif consecutive_losses >= self.TRIGGERS['consecutive_loss']:
            reason = f'{consecutive_losses}연속 손절'
        elif index_change <= self.TRIGGERS['index_crash']:
            reason = f'지수 급락 {index_change*100:.1f}%'

        if reason:
            self.kill(reason)
            return True
        return False

    def kill(self, reason: str):
        """전체 매매 즉시 정지"""
        self.is_killed = True
        self.kill_reason = reason
        self.killed_at = datetime.datetime.now()

        # 텔레그램 긴급 알림
        msg = f'🚨 긴급! 킬스위치 작동\n이유: {reason}\n모든 매매 중단\n{self.COOLDOWN_MINUTES}분 후 자동 재개'
        if self._telegram:
            try:
                self._telegram(msg)
            except Exception:
                pass

        # 보유 종목 전량 청산 (선택)
        if self._sell_all:
            try:
                self._sell_all()
            except Exception:
                pass

    def auto_resume_check(self) -> bool:
        """30분 후 자동 재개 체크"""
        if not self.is_killed or not self.killed_at:
            return False
        elapsed = (datetime.datetime.now() - self.killed_at).total_seconds() / 60
        if elapsed >= self.COOLDOWN_MINUTES:
            self.manual_resume()
            return True
        return False

    def manual_resume(self):
        """수동 킬스위치 해제 (UI 버튼 또는 텔레그램 명령어)"""
        self.is_killed = False
        self.kill_reason = ''
        self.killed_at = None
        if self._telegram:
            try:
                self._telegram('✅ 킬스위치 해제 — 매매 재개')
            except Exception:
                pass

    @property
    def status(self) -> dict:
        return {
            'is_killed': self.is_killed,
            'reason': self.kill_reason,
            'killed_at': str(self.killed_at) if self.killed_at else None,
        }
