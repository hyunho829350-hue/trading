@echo off
REM ┌──────────────────────────────────────────────────────────────────┐
REM │  AI 자동매매 — PAPER 모드 (실전 모의 투자)                       │
REM │  초기자본: 80만원 / 손절 -2% / 익절 +3% / 트레일링 -1.5%        │
REM └──────────────────────────────────────────────────────────────────┘
title AI 자동매매 - PAPER MODE

echo ============================================================
echo   AI 자동매매 시스템 — PAPER (모의) 모드
echo   키움 32bit Python 3.10 필요
echo ============================================================

REM Python 32bit 경로 (환경에 따라 수정)
set PYTHON32=C:\Python310_32\python.exe
if not exist %PYTHON32% set PYTHON32=python

REM 프로젝트 경로
set PROJ=C:\trading

REM 로그 디렉토리 생성
if not exist D:\trading_data\logs\trade mkdir D:\trading_data\logs\trade 2>nul

REM 현재 날짜/시간으로 로그 파일명
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set dt=%%a
set LOG_FILE=D:\trading_data\logs\trade\paper_%dt:~0,8%_%dt:~8,6%.log

echo [%time%] PAPER 모드 시작 >> %LOG_FILE%

REM 의존성 확인 및 설치
echo [1/3] 의존성 확인 중...
%PYTHON32% -m pip install -q numpy scipy pyzmq requests apscheduler 2>nul

REM 메인 실행 (UI 포함)
echo [2/3] 시스템 시작...
cd /d %PROJ%
%PYTHON32% main.py --ui --mode paper 2>> %LOG_FILE%

REM 오류 시 종료 코드 확인
if errorlevel 1 (
    echo.
    echo [오류] 실행 실패. 로그 확인: %LOG_FILE%
    pause
)
