@echo off
REM ┌──────────────────────────────────────────────────────────────────┐
REM │  AI 64bit 서버 — ZMQ 기반 예측 서버                              │
REM │  PyTorch (64bit) / LightGBM                                     │
REM └──────────────────────────────────────────────────────────────────┘
title AI 서버 - 64bit ZMQ

echo ============================================================
echo   AI 예측 서버 (64bit)
echo   포트: 5555 / ZMQ REP 소켓
echo ============================================================

set PYTHON64=C:\Python310\python.exe
if not exist %PYTHON64% set PYTHON64=python3

set PROJ=C:\trading

echo AI 서버 의존성 확인...
%PYTHON64% -m pip install -q pyzmq lightgbm numpy 2>nul

echo AI 서버 시작...
cd /d %PROJ%
%PYTHON64% -c "
import sys, os
sys.path.insert(0, r'C:\trading')

try:
    import zmq
    import numpy as np
    import json
    import time
    from ai.ai_brain_simple import AIBrainSimple

    brain = AIBrainSimple()
    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind('tcp://127.0.0.1:5555')
    print('[AI Server] ZMQ REP 서버 시작 — 포트 5555')

    while True:
        try:
            msg = socket.recv_json(flags=zmq.NOBLOCK)
            features = msg.get('features', [])
            result = brain.predict(features)
            socket.send_json(result)
        except zmq.Again:
            time.sleep(0.01)
        except KeyboardInterrupt:
            break
        except Exception as e:
            try:
                socket.send_json({'error': str(e), 'BUY': 0.3, 'HOLD': 0.5, 'SELL': 0.2})
            except Exception:
                pass
    ctx.destroy()
except Exception as e:
    print(f'AI 서버 오류: {e}')
    input('Enter로 종료...')
"
