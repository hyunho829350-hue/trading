"""
지수 탭 — 4대 지수 실시간 표시 + 시장 상태
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont


class IndexCard(QFrame):
    """개별 지수 카드 위젯"""
    def __init__(self, title: str):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(150)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.lbl_title  = QLabel(title)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setFont(QFont('Arial', 10, QFont.Bold))

        self.lbl_value  = QLabel('---')
        self.lbl_value.setAlignment(Qt.AlignCenter)
        self.lbl_value.setFont(QFont('Consolas', 18, QFont.Bold))

        self.lbl_change = QLabel('▲ 0.00%')
        self.lbl_change.setAlignment(Qt.AlignCenter)
        self.lbl_change.setFont(QFont('Arial', 11))

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addWidget(self.lbl_change)

    def update(self, value: float, change_rate: float):
        self.lbl_value.setText(f'{value:,.2f}')
        arrow = '▲' if change_rate >= 0 else '▼'
        color = '#00ff88' if change_rate >= 0 else '#ff4444'
        self.lbl_change.setText(f'{arrow} {abs(change_rate):.2f}%')
        self.lbl_change.setStyleSheet(f'color: {color}')
        self.setStyleSheet(f'background: {"#1b3a2a" if change_rate >= 0 else "#3a1b1b"}; '
                           f'border: 1px solid #444; border-radius: 8px;')


class TabIndex(QWidget):
    def __init__(self, api_handler=None):
        super().__init__()
        self.api_handler = api_handler
        self._index_data = {
            'kospi':   {'value': 0, 'change': 0},
            'kospi200': {'value': 0, 'change': 0},
            'kosdaq':  {'value': 0, 'change': 0},
            'kosdaq150': {'value': 0, 'change': 0},
        }
        self._setup_ui()
        self._start_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 4대 지수 카드
        cards_layout = QHBoxLayout()
        self.card_kospi    = IndexCard('코스피')
        self.card_k200     = IndexCard('코스피200')
        self.card_kosdaq   = IndexCard('코스닥')
        self.card_kq150    = IndexCard('코스닥150')
        for card in [self.card_kospi, self.card_k200, self.card_kosdaq, self.card_kq150]:
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)

        # 시장 상태
        self.lbl_market = QLabel('🟡 시장 상태 분석 중...')
        self.lbl_market.setFont(QFont('Arial', 13))
        self.lbl_market.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_market)

        # 추천 섹터
        self.lbl_sector = QLabel('추천 섹터: 분석 중')
        self.lbl_sector.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_sector)

        layout.addStretch()

    def _start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(3000)

    def _refresh(self):
        self.card_kospi.update(
            self._index_data['kospi']['value'],
            self._index_data['kospi']['change']
        )
        self.card_k200.update(
            self._index_data['kospi200']['value'],
            self._index_data['kospi200']['change']
        )
        self.card_kosdaq.update(
            self._index_data['kosdaq']['value'],
            self._index_data['kosdaq']['change']
        )
        self.card_kq150.update(
            self._index_data['kosdaq150']['value'],
            self._index_data['kosdaq150']['change']
        )

        avg = self._index_data['kospi']['change']
        if avg >= 1.0:
            state, color = '🟢 강한 상승장 — 공격적 매매 허용', '#00ff88'
            sector = '코스피 강세: 대형주/금융 주목'
        elif avg >= 0:
            state, color = '🟡 보통 상승장 — 일반 매매', '#ffee58'
            sector = '코스닥 강세: 바이오/IT/2차전지 주목'
        elif avg >= -1.0:
            state, color = '🟠 횡보장 — 선별 매매', '#ffa726'
            sector = '방어주 / 단기 스캘핑 중심'
        else:
            state, color = '🔴 하락장 — 매매 자제', '#ff4444'
            sector = '매매 최소화, 현금 보유'

        self.lbl_market.setText(state)
        self.lbl_market.setStyleSheet(f'color: {color}; font-weight: bold')
        self.lbl_sector.setText(f'추천: {sector}')

    def update_index(self, index_name: str, value: float, change_rate: float):
        """외부에서 지수 데이터 업데이트"""
        if index_name in self._index_data:
            self._index_data[index_name] = {'value': value, 'change': change_rate}
