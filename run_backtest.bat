@echo off
REM ┌──────────────────────────────────────────────────────────────────┐
REM │  AI 자동매매 — 백테스트 모드                                     │
REM │  수수료 0.015% + 세금 0.23% + 슬리피지 포함                      │
REM └──────────────────────────────────────────────────────────────────┘
title AI 자동매매 - 백테스트

echo ============================================================
echo   백테스트 엔진
echo   수수료+세금+슬리피지 실전 동일 환경
echo ============================================================

set PYTHON32=C:\Python310_32\python.exe
if not exist %PYTHON32% set PYTHON32=python

set PROJ=C:\trading

REM 결과 저장 디렉토리
if not exist D:\trading_data\backtest\results mkdir D:\trading_data\backtest\results 2>nul

echo 의존성 확인 중...
%PYTHON32% -m pip install -q numpy scipy plotly 2>nul

echo 백테스트 UI 실행...
cd /d %PROJ%
%PYTHON32% -c "
import sys
sys.path.insert(0, r'C:\trading')
from PyQt5.QtWidgets import QApplication
from ui.tab_backtest_ui import TabBacktestUI
app = QApplication(sys.argv)
w = TabBacktestUI()
w.setWindowTitle('백테스트')
w.resize(1200, 800)
w.show()
sys.exit(app.exec_())
" 2>nul

if errorlevel 1 (
    REM UI 없으면 CLI 백테스트
    echo UI 실패 — CLI 모드로 백테스트
    %PYTHON32% -c "
import sys
sys.path.insert(0, r'C:\trading')
from backtest.backtest_engine import BacktestEngine
import random, json

# 더미 데이터로 테스트
data = []
price = 10000
for i in range(500):
    import math
    change = random.gauss(0, 0.015)
    op = price
    cl = int(price * (1 + change))
    hi = int(max(op,cl) * 1.005)
    lo = int(min(op,cl) * 0.995)
    data.append({'open':op,'high':hi,'low':lo,'close':cl,'volume':1000000})
    price = cl

def strategy(d):
    if len(d) < 5: return False, 0
    closes = [x['close'] for x in d]
    ma5 = sum(closes[-5:])/5
    return closes[-1] > ma5 * 1.005, 70

engine = BacktestEngine()
result = engine.run(data, strategy)
print('=== 백테스트 결과 ===')
print(f'총 매매: {result[\"total_trades\"]}회')
print(f'승률: {result[\"win_rate\"]:.1f}%')
print(f'손익비: {min(result[\"profit_factor\"],99):.2f}')
print(f'총수익률: {result[\"total_profit_rate\"]:+.2f}%')
print(f'MDD: -{result[\"max_drawdown\"]:.1f}%')
print(f'수수료+세금: {result[\"total_fee_tax\"]:,.0f}원')
"
    pause
)
