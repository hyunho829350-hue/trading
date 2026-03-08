@echo off
REM ┌──────────────────────────────────────────────────────────────────┐
REM │  AI 자동매매 — LIVE 모드 (실전 매매)                             │
REM │  ⚠️ 실제 돈 사용 — 신중히 실행!                                  │
REM └──────────────────────────────────────────────────────────────────┘
title AI 자동매매 - LIVE MODE ⚠️ 실전

echo ============================================================
echo   ⚠️  경고: LIVE (실전) 모드입니다!
echo   실제 계좌에서 실제 자금으로 매매합니다.
echo ============================================================
echo.

REM 사용자 확인
set /p CONFIRM=실전 매매를 시작하시겠습니까? (yes 입력 후 Enter): 
if /i not "%CONFIRM%"=="yes" (
    echo 취소되었습니다.
    pause
    exit /b
)

set PYTHON32=C:\Python310_32\python.exe
if not exist %PYTHON32% set PYTHON32=python

set PROJ=C:\trading

if not exist D:\trading_data\logs\trade mkdir D:\trading_data\logs\trade 2>nul

for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set dt=%%a
set LOG_FILE=D:\trading_data\logs\trade\live_%dt:~0,8%_%dt:~8,6%.log

echo [%time%] LIVE 모드 시작 >> %LOG_FILE%

echo [1/3] 의존성 확인 중...
%PYTHON32% -m pip install -q numpy scipy pyzmq requests apscheduler 2>nul

echo [2/3] LIVE 모드 시스템 시작...
cd /d %PROJ%
%PYTHON32% main.py --ui --mode live 2>> %LOG_FILE%

if errorlevel 1 (
    echo.
    echo [오류] 실행 실패. 로그 확인: %LOG_FILE%
    pause
)
