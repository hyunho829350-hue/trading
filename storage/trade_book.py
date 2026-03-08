"""
매매 장부 (Trade Book)
모든 매매 기록 + 수익 통계 + 80만→1억 달성률
CSV 저장
"""
import os
import csv
from datetime import datetime, date, timedelta
from typing import Optional


class TradeBook:
    """매매 장부 — CSV 저장, 수익 통계"""

    CSV_PATH = r'D:\trading_data\trade_book.csv'
    INITIAL_CAPITAL = 800_000
    TARGET_CAPITAL  = 100_000_000

    COLUMNS = [
        'date', 'time', 'stock_code', 'stock_name',
        'direction', 'price', 'quantity', 'amount',
        'fee', 'tax', 'slippage',
        'net_profit', 'net_profit_rate',
        'strategy', 'condition',
        'hold_minutes', 'exit_reason',
        'cumulative_pnl',
    ]

    BUY_FEE  = 0.00015
    SELL_FEE = 0.00015
    TAX      = 0.0023

    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path or self.CSV_PATH
        self._cumulative_pnl = 0.0
        self._pending_buys: dict = {}  # {stock_code: buy_record}
        self._ensure_csv()
        self._load_cumulative()

    def _ensure_csv(self):
        """CSV 파일 없으면 생성"""
        try:
            dirpath = os.path.dirname(self.csv_path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
            if not os.path.exists(self.csv_path):
                with open(self.csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                    csv.writer(f).writerow(self.COLUMNS)
        except Exception:
            # D드라이브 없으면 현재 디렉토리에 저장
            self.csv_path = 'trade_book.csv'
            if not os.path.exists(self.csv_path):
                with open(self.csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                    csv.writer(f).writerow(self.COLUMNS)

    def _load_cumulative(self):
        """기존 CSV에서 누적 손익 로드"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                self._cumulative_pnl = float(last.get('cumulative_pnl', 0))
        except Exception:
            self._cumulative_pnl = 0.0

    def _write_row(self, row: dict):
        try:
            with open(self.csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
                writer.writerow(row)
        except Exception:
            pass

    def record_buy(self, stock_code: str, stock_name: str, price: float,
                   quantity: int, strategy: str = '', condition: str = ''):
        """매수 체결 기록"""
        now = datetime.now()
        amount = price * quantity
        fee = amount * self.BUY_FEE

        row = {
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'stock_code': stock_code,
            'stock_name': stock_name,
            'direction': 'BUY',
            'price': price,
            'quantity': quantity,
            'amount': amount,
            'fee': round(fee, 2),
            'tax': 0,
            'slippage': 0,
            'net_profit': '',
            'net_profit_rate': '',
            'strategy': strategy,
            'condition': condition,
            'hold_minutes': '',
            'exit_reason': '',
            'cumulative_pnl': round(self._cumulative_pnl, 2),
        }
        self._pending_buys[stock_code] = {'price': price, 'quantity': quantity,
                                          'time': now, 'fee': fee, 'strategy': strategy}
        self._write_row(row)

    def record_sell(self, stock_code: str, stock_name: str, sell_price: float,
                    exit_reason: str = '', slippage: float = 0):
        """매도 체결 기록 + 순수익 계산"""
        now = datetime.now()
        buy_info = self._pending_buys.pop(stock_code, None)
        if not buy_info:
            return None

        quantity  = buy_info['quantity']
        buy_price = buy_info['price']
        hold_min  = (now - buy_info['time']).total_seconds() / 60

        amount = sell_price * quantity
        sell_fee = amount * self.SELL_FEE
        tax      = amount * self.TAX

        buy_total  = buy_price * quantity * (1 + self.BUY_FEE)
        sell_total = amount - sell_fee - tax

        net_profit = sell_total - buy_total
        net_rate   = net_profit / buy_total * 100 if buy_total > 0 else 0

        self._cumulative_pnl += net_profit

        row = {
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'stock_code': stock_code,
            'stock_name': stock_name,
            'direction': 'SELL',
            'price': sell_price,
            'quantity': quantity,
            'amount': amount,
            'fee': round(sell_fee, 2),
            'tax': round(tax, 2),
            'slippage': round(slippage, 2),
            'net_profit': round(net_profit, 2),
            'net_profit_rate': round(net_rate, 4),
            'strategy': buy_info.get('strategy', ''),
            'condition': '',
            'hold_minutes': round(hold_min, 1),
            'exit_reason': exit_reason,
            'cumulative_pnl': round(self._cumulative_pnl, 2),
        }
        self._write_row(row)
        return row

    def _read_all(self) -> list:
        try:
            with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
                return list(csv.DictReader(f))
        except Exception:
            return []

    def _filter_by_period(self, rows: list, start: date, end: date) -> list:
        result = []
        for r in rows:
            try:
                d = datetime.strptime(r['date'], '%Y-%m-%d').date()
                if start <= d <= end:
                    result.append(r)
            except Exception:
                pass
        return result

    def _calc_stats(self, rows: list) -> dict:
        sells = [r for r in rows if r['direction'] == 'SELL' and r.get('net_profit')]
        if not sells:
            return {'pnl': 0, 'trades': 0, 'win_rate': 0, 'win': 0, 'loss': 0}
        profits = [float(r['net_profit']) for r in sells]
        wins = [p for p in profits if p > 0]
        pnl = sum(profits)
        return {
            'pnl': pnl,
            'trades': len(profits),
            'win_rate': len(wins) / len(profits) * 100,
            'win': len(wins),
            'loss': len(profits) - len(wins),
        }

    def get_daily_summary(self) -> dict:
        today = date.today()
        rows = self._filter_by_period(self._read_all(), today, today)
        return self._calc_stats(rows)

    def get_weekly_summary(self) -> dict:
        today = date.today()
        start = today - timedelta(days=today.weekday())
        rows = self._filter_by_period(self._read_all(), start, today)
        return self._calc_stats(rows)

    def get_monthly_summary(self) -> dict:
        today = date.today()
        start = today.replace(day=1)
        rows = self._filter_by_period(self._read_all(), start, today)
        return self._calc_stats(rows)

    def get_cumulative(self) -> dict:
        all_rows = self._read_all()
        stats = self._calc_stats(all_rows)
        stats['cumulative_pnl'] = self._cumulative_pnl
        current_capital = self.INITIAL_CAPITAL + self._cumulative_pnl
        stats['current_capital'] = current_capital
        stats['achievement_rate'] = current_capital / self.TARGET_CAPITAL * 100
        return stats

    def get_strategy_performance(self) -> dict:
        """조건검색식별 성과 분석"""
        all_rows = [r for r in self._read_all() if r['direction'] == 'SELL' and r.get('net_profit')]
        perf: dict = {}
        for r in all_rows:
            cond = r.get('strategy', 'unknown')
            if cond not in perf:
                perf[cond] = {'count': 0, 'pnl': 0, 'wins': 0, 'max_loss': 0}
            profit = float(r['net_profit'])
            perf[cond]['count'] += 1
            perf[cond]['pnl'] += profit
            if profit > 0:
                perf[cond]['wins'] += 1
            if profit < perf[cond]['max_loss']:
                perf[cond]['max_loss'] = profit

        for cond, s in perf.items():
            s['win_rate'] = s['wins'] / s['count'] * 100 if s['count'] > 0 else 0
            s['avg_pnl'] = s['pnl'] / s['count'] if s['count'] > 0 else 0

        return perf

    def get_80만_to_target_progress(self) -> dict:
        cum = self.get_cumulative()
        capital = cum['current_capital']
        return {
            'start': self.INITIAL_CAPITAL,
            'current': capital,
            'target': self.TARGET_CAPITAL,
            'achievement_pct': capital / self.TARGET_CAPITAL * 100,
            'profit': self._cumulative_pnl,
            'profit_rate': self._cumulative_pnl / self.INITIAL_CAPITAL * 100,
        }
