"""
설정 탭 — 매매 파라미터 실시간 수정
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QCheckBox, QPushButton, QGroupBox, QMessageBox, QGridLayout
)
from PyQt5.QtCore import Qt


class TabSettings(QWidget):
    def __init__(self, config: dict = None, engine=None):
        super().__init__()
        self.config = config or {}
        self.engine = engine
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 매매 설정
        g1 = QGroupBox('매매 설정')
        g1_grid = QGridLayout(g1)

        # 손절폭 슬라이더 (-0.5% ~ -5%)
        g1_grid.addWidget(QLabel('손절폭'), 0, 0)
        self.sl_stoploss = QSlider(Qt.Horizontal)
        self.sl_stoploss.setRange(5, 50)   # 0.5~5% (×0.1)
        self.sl_stoploss.setValue(20)
        self.lbl_sl = QLabel('-2.0%')
        self.sl_stoploss.valueChanged.connect(lambda v: self.lbl_sl.setText(f'-{v/10:.1f}%'))
        g1_grid.addWidget(self.sl_stoploss, 0, 1)
        g1_grid.addWidget(self.lbl_sl, 0, 2)

        # 익절폭 슬라이더 (+1% ~ +10%)
        g1_grid.addWidget(QLabel('익절폭'), 1, 0)
        self.sl_takeprofit = QSlider(Qt.Horizontal)
        self.sl_takeprofit.setRange(10, 100)  # 1~10% (×0.1)
        self.sl_takeprofit.setValue(30)
        self.lbl_tp = QLabel('+3.0%')
        self.sl_takeprofit.valueChanged.connect(lambda v: self.lbl_tp.setText(f'+{v/10:.1f}%'))
        g1_grid.addWidget(self.sl_takeprofit, 1, 1)
        g1_grid.addWidget(self.lbl_tp, 1, 2)

        # 트레일링 스탑
        g1_grid.addWidget(QLabel('트레일링스탑'), 2, 0)
        self.chk_trailing = QCheckBox('활성화')
        self.chk_trailing.setChecked(True)
        g1_grid.addWidget(self.chk_trailing, 2, 1)

        layout.addWidget(g1)

        # 매매 횟수 제한
        g2 = QGroupBox('매매 횟수 제한')
        g2_grid = QGridLayout(g2)

        g2_grid.addWidget(QLabel('일일 최대 매수'), 0, 0)
        self.sl_max_buy = QSlider(Qt.Horizontal)
        self.sl_max_buy.setRange(1, 15)
        self.sl_max_buy.setValue(10)
        self.lbl_max_buy = QLabel('10회')
        self.sl_max_buy.valueChanged.connect(lambda v: self.lbl_max_buy.setText(f'{v}회'))
        g2_grid.addWidget(self.sl_max_buy, 0, 1)
        g2_grid.addWidget(self.lbl_max_buy, 0, 2)

        g2_grid.addWidget(QLabel('일일 최대 매도'), 1, 0)
        self.sl_max_sell = QSlider(Qt.Horizontal)
        self.sl_max_sell.setRange(1, 15)
        self.sl_max_sell.setValue(10)
        self.lbl_max_sell = QLabel('10회')
        self.sl_max_sell.valueChanged.connect(lambda v: self.lbl_max_sell.setText(f'{v}회'))
        g2_grid.addWidget(self.sl_max_sell, 1, 1)
        g2_grid.addWidget(self.lbl_max_sell, 1, 2)

        layout.addWidget(g2)

        # 조건 ON/OFF
        g3 = QGroupBox('조건 활성화')
        g3_layout = QHBoxLayout(g3)
        self.condition_checks = {}
        conditions = ['급등초기', 'VI돌파', '상한가근접', '눌림목반등', 'BB스퀴즈', '골든크로스']
        for cond in conditions:
            chk = QCheckBox(cond)
            chk.setChecked(True)
            self.condition_checks[cond] = chk
            g3_layout.addWidget(chk)
        layout.addWidget(g3)

        # 버튼
        btn_layout = QHBoxLayout()
        btn_save    = QPushButton('💾 저장')
        btn_reset   = QPushButton('↺ 초기화')
        btn_apply   = QPushButton('✅ 적용')
        btn_save.clicked.connect(self._save)
        btn_reset.clicked.connect(self._reset)
        btn_apply.clicked.connect(self._apply)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def _validate(self) -> bool:
        sl = self.sl_stoploss.value() / 10
        tp = self.sl_takeprofit.value() / 10
        if sl >= tp:
            QMessageBox.warning(self, '설정 오류', f'손절폭({sl}%)이 익절폭({tp}%)보다 크거나 같습니다.')
            return False
        return True

    def _save(self):
        if not self._validate():
            return
        self.config['stop_loss']    = -(self.sl_stoploss.value() / 100)
        self.config['take_profit']  = self.sl_takeprofit.value() / 100
        self.config['trailing']     = self.chk_trailing.isChecked()
        self.config['max_buy']      = self.sl_max_buy.value()
        self.config['max_sell']     = self.sl_max_sell.value()
        self.config['conditions']   = {k: v.isChecked() for k, v in self.condition_checks.items()}
        QMessageBox.information(self, '저장', '설정이 저장되었습니다.')

    def _reset(self):
        self.sl_stoploss.setValue(20)
        self.sl_takeprofit.setValue(30)
        self.chk_trailing.setChecked(True)
        self.sl_max_buy.setValue(10)
        self.sl_max_sell.setValue(10)
        for chk in self.condition_checks.values():
            chk.setChecked(True)

    def _apply(self):
        if not self._validate():
            return
        if self.engine:
            self.engine.config['stop_loss']   = -(self.sl_stoploss.value() / 100)
            self.engine.config['take_profit'] = self.sl_takeprofit.value() / 100
        QMessageBox.information(self, '적용', '설정이 즉시 적용되었습니다.')
