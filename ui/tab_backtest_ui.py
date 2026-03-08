"""
백테스트 UI 탭 — 실행 + 결과 확인 (QThread 기반 비동기)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDateEdit, QComboBox, QPushButton, QProgressBar,
    QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt5.QtGui import QFont


class BacktestWorker(QThread):
    """백테스트 비동기 실행 (UI 멈춤 방지)"""
    progress = pyqtSignal(int)
    result_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, stock_code: str, start_date: str, end_date: str,
                 strategy: str, timeframe: str):
        super().__init__()
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date   = end_date
        self.strategy   = strategy
        self.timeframe  = timeframe

    def run(self):
        try:
            from backtest.backtest_engine import BacktestEngine

            # 더미 데이터 (실제로는 npy 로드)
            import random
            data = []
            price = 10000
            for i in range(500):
                change = random.gauss(0, 0.015)
                op = price
                cl = int(price * (1 + change))
                hi = int(max(op, cl) * (1 + random.uniform(0, 0.01)))
                lo = int(min(op, cl) * (1 - random.uniform(0, 0.01)))
                vol = int(random.uniform(100000, 5000000))
                data.append({'open': op, 'high': hi, 'low': lo, 'close': cl, 'volume': vol})
                price = cl
                if i % 50 == 0:
                    self.progress.emit(int(i / 500 * 100))

            def simple_strategy(data_slice):
                if len(data_slice) < 5:
                    return False, 0
                closes = [d['close'] for d in data_slice]
                ma5 = sum(closes[-5:]) / 5
                return closes[-1] > ma5, 60

            engine = BacktestEngine()
            result = engine.run(data, simple_strategy)
            self.progress.emit(100)
            self.result_ready.emit(result)

        except Exception as e:
            self.error.emit(str(e))


class TabBacktestUI(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._result = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 헤더 입력
        header = QHBoxLayout()
        header.addWidget(QLabel('종목코드:'))
        self.edit_code = QLineEdit('005930')
        self.edit_code.setMaximumWidth(100)
        header.addWidget(self.edit_code)

        header.addWidget(QLabel('시작일:'))
        self.date_start = QDateEdit(QDate.currentDate().addMonths(-3))
        self.date_start.setCalendarPopup(True)
        header.addWidget(self.date_start)

        header.addWidget(QLabel('종료일:'))
        self.date_end = QDateEdit(QDate.currentDate())
        self.date_end.setCalendarPopup(True)
        header.addWidget(self.date_end)

        header.addWidget(QLabel('봉타입:'))
        self.combo_tf = QComboBox()
        self.combo_tf.addItems(['1분', '5분', '일봉'])
        header.addWidget(self.combo_tf)

        header.addWidget(QLabel('전략:'))
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems(['급등초기', 'VI돌파', '눌림목반등', 'BB스퀴즈', '골든크로스'])
        header.addWidget(self.combo_strategy)

        self.btn_run = QPushButton('▶ 실행')
        self.btn_run.clicked.connect(self._run_backtest)
        header.addWidget(self.btn_run)
        header.addStretch()
        layout.addLayout(header)

        # 진행바
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # 요약 라벨
        self.lbl_summary = QLabel('백테스트를 실행하세요')
        self.lbl_summary.setFont(QFont('Consolas', 10))
        self.lbl_summary.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_summary)

        # 결과 탭
        self.result_tabs = QTabWidget()

        # 자산곡선 탭
        self.lbl_chart = QLabel('백테스트 결과 자산곡선이 여기에 표시됩니다.')
        self.lbl_chart.setAlignment(Qt.AlignCenter)
        self.result_tabs.addTab(self.lbl_chart, '자산곡선')

        # 매매 목록 탭
        self.trades_table = QTableWidget(0, 7)
        self.trades_table.setHorizontalHeaderLabels(
            ['#', '청산이유', '매수가', '매도가', '수량', '순수익', '수익률'])
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trades_table.setFont(QFont('Consolas', 8))
        self.result_tabs.addTab(self.trades_table, '매매 목록')

        # 비용 분석 탭
        self.lbl_cost = QTextEdit()
        self.lbl_cost.setReadOnly(True)
        self.result_tabs.addTab(self.lbl_cost, '비용 분석')

        layout.addWidget(self.result_tabs, stretch=1)

    def _run_backtest(self):
        if self._worker and self._worker.isRunning():
            return

        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self.lbl_summary.setText('백테스트 실행 중...')

        self._worker = BacktestWorker(
            stock_code=self.edit_code.text(),
            start_date=self.date_start.date().toString('yyyyMMdd'),
            end_date=self.date_end.date().toString('yyyyMMdd'),
            strategy=self.combo_strategy.currentText(),
            timeframe=self.combo_tf.currentText(),
        )
        self._worker.progress.connect(self.progress.setValue)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result: dict):
        self._result = result
        self.btn_run.setEnabled(True)

        wr  = result.get('win_rate', 0)
        pr  = result.get('total_profit_rate', 0)
        mdd = result.get('max_drawdown', 0)
        pf  = result.get('profit_factor', 0)
        tt  = result.get('total_trades', 0)
        fee = result.get('total_fee_tax', 0)
        slip = result.get('total_slippage', 0)

        self.lbl_summary.setText(
            f'총수익률: {pr:+.1f}% | 승률: {wr:.1f}% | 손익비: {min(pf,99):.2f} | '
            f'MDD: -{mdd:.1f}% | 매매수: {tt}회 | 수수료+세금: {fee:,.0f}원'
        )

        # 비용 분석
        self.lbl_cost.setText(
            f'수수료+세금 합계: {fee:,.0f}원\n'
            f'슬리피지 추정: {slip:,.0f}원\n'
            f'총 비용: {fee+slip:,.0f}원\n\n'
            f'초기자본: 800,000원\n'
            f'최종자본: {result.get("final_capital", 800000):,.0f}원\n'
            f'순수익: {result.get("final_capital", 800000)-800000:+,.0f}원'
        )

        # 매매 목록
        trades = result.get('trades', [])
        self.trades_table.setRowCount(len(trades))
        for i, t in enumerate(trades):
            items = [
                str(i+1), t.get('exit_reason', ''),
                f'{t["buy_price"]:,.0f}', f'{t["sell_price"]:,.0f}',
                str(t['quantity']),
                f'{t["net_profit"]:+,.0f}원',
                f'{t["net_profit_rate"]*100:+.2f}%',
            ]
            for col, val in enumerate(items):
                self.trades_table.setItem(i, col, QTableWidgetItem(str(val)))

    def _on_error(self, err: str):
        self.btn_run.setEnabled(True)
        self.lbl_summary.setText(f'오류: {err}')
