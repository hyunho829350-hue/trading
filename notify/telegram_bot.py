"""
텔레그램 알림 봇
매수/매도/킬스위치/일일리포트/오류 알림
비동기 발송으로 매매 지연 방지
"""
import threading
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class TelegramBot:
    """텔레그램 비동기 알림 발송"""

    def __init__(self, token: str = '', chat_id: str = ''):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f'https://api.telegram.org/bot{token}' if token else ''
        self._queue: list = []
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._send_loop, daemon=True)
        self._worker.start()

    def send(self, message: str):
        """비동기 텍스트 발송"""
        with self._lock:
            self._queue.append(('text', message))

    def send_chart(self, image_path: str):
        """차트 이미지 발송"""
        with self._lock:
            self._queue.append(('photo', image_path))

    def _send_loop(self):
        """백그라운드 발송 루프"""
        while True:
            item = None
            with self._lock:
                if self._queue:
                    item = self._queue.pop(0)
            if item:
                try:
                    if item[0] == 'text':
                        self._do_send_text(item[1])
                    elif item[0] == 'photo':
                        self._do_send_photo(item[1])
                except Exception:
                    pass
            time.sleep(0.1)

    def _do_send_text(self, text: str):
        if not self.token or not self.chat_id:
            print(f'[TELEGRAM] {text}')
            return
        if not HAS_REQUESTS:
            print(f'[TELEGRAM] {text}')
            return
        try:
            requests.post(
                f'{self.base_url}/sendMessage',
                json={'chat_id': self.chat_id, 'text': text, 'parse_mode': 'HTML'},
                timeout=5
            )
        except Exception:
            print(f'[TELEGRAM 실패] {text}')

    def _do_send_photo(self, image_path: str):
        if not self.token or not self.chat_id or not HAS_REQUESTS:
            return
        try:
            with open(image_path, 'rb') as f:
                requests.post(
                    f'{self.base_url}/sendPhoto',
                    data={'chat_id': self.chat_id},
                    files={'photo': f},
                    timeout=10
                )
        except Exception:
            pass

    # ── 메시지 포맷 ──────────────────────────────────────────────────────
    def msg_buy(self, stock_name: str, stock_code: str, price: int, qty: int,
                condition: str, score: int, stop_price: int, target_price: int) -> str:
        return (
            f'✅ 매수 체결\n'
            f'종목: {stock_name} ({stock_code})\n'
            f'가격: {price:,}원 × {qty}주\n'
            f'금액: {price*qty:,}원\n'
            f'조건: {condition} (score: {score})\n'
            f'손절: {stop_price:,}원\n'
            f'목표: {target_price:,}원'
        )

    def msg_sell(self, stock_name: str, sell_price: int, net_profit: float,
                 net_rate: float, hold_minutes: float, reason: str,
                 cumulative_pnl: float, cumulative_rate: float) -> str:
        emoji = '💰' if net_profit >= 0 else '🔴'
        return (
            f'{emoji} 매도 완료\n'
            f'종목: {stock_name}\n'
            f'매도가: {sell_price:,}원\n'
            f'순수익: {net_profit:+,.0f}원 ({net_rate:+.2f}%)\n'
            f'보유시간: {hold_minutes:.0f}분\n'
            f'청산이유: {reason}\n'
            f'누적: {cumulative_pnl:+,.0f}원 ({cumulative_rate:+.1f}%)'
        )

    def msg_kill_switch(self, reason: str) -> str:
        return (
            f'🚨 긴급! 킬스위치 작동\n'
            f'이유: {reason}\n'
            f'모든 매매 중단\n'
            f'30분 후 자동 재개'
        )

    def msg_daily_report(self, pnl: float, pnl_rate: float, trades: int,
                         buy_count: int, sell_count: int, win_rate: float,
                         fee_tax: float, capital: float, achievement: float) -> str:
        return (
            f'📊 오늘의 결과\n'
            f'──────────────\n'
            f'수익금: {pnl:+,.0f}원\n'
            f'수익률: {pnl_rate:+.2f}%\n'
            f'매매횟수: {trades}회 (매수{buy_count}/매도{sell_count})\n'
            f'승률: {win_rate:.1f}%\n'
            f'수수료+세금: -{fee_tax:,.0f}원\n'
            f'──────────────\n'
            f'누적 자산: {capital:,.0f}원\n'
            f'목표 달성률: {achievement:.2f}%'
        )

    def msg_error(self, module: str, error: str) -> str:
        return f'❌ 오류: {module}\n{error}'

    def handle_command(self, command: str, engine=None) -> str:
        """텔레그램 명령어 처리"""
        cmd = command.strip().lower()
        if cmd == '/status':
            if engine:
                stats = engine.risk_manager.daily_stats
                return f'현재 상태: {"실행 중" if engine.is_running else "정지"}\n' \
                       f'오늘 매매: {stats["daily_trades"]}회\n' \
                       f'오늘 손익: {stats["daily_pnl"]:+,.0f}원'
            return '엔진 연결 안됨'
        elif cmd == '/positions':
            if engine:
                positions = engine.position_mgr.get_all_positions()
                if not positions:
                    return '보유 종목 없음'
                return '\n'.join([
                    f'{code}: {pos["current_price"]:,}원'
                    for code, pos in positions.items()
                ])
            return '엔진 연결 안됨'
        elif cmd == '/stop':
            if engine:
                engine.stop()
            return '매매 중지'
        elif cmd == '/start':
            if engine:
                engine.start()
            return '매매 재개'
        elif cmd == '/kill':
            if engine:
                engine.kill_switch.kill('텔레그램 명령')
            return '킬스위치 발동'
        return f'알 수 없는 명령어: {command}'
