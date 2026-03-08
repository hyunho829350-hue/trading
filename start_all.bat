@echo off
REM ┌──────────────────────────────────────────────────────────────────┐
REM │  전체 시스템 원클릭 실행                                          │
REM │  1. AI 서버(64bit) 먼저 시작                                     │
REM │  2. 메인 대시보드(32bit) 시작                                    │
REM └──────────────────────────────────────────────────────────────────┘
title AI 자동매매 — 전체 시스템 시작

echo ============================================================
echo   AI 자동매매 전체 시스템 시작
echo   80만원 ^→ 1억 프로젝트
echo ============================================================

set PROJ=C:\trading

REM 1. AI 서버를 별도 창에서 먼저 시작
echo [1/2] AI 서버(64bit) 시작 중...
start "AI Server (64bit)" /min cmd /c "%PROJ%\run_ai_server.bat"

REM AI 서버 초기화 대기 (3초)
timeout /t 3 /nobreak > nul

REM 2. 메인 대시보드 시작
echo [2/2] 메인 대시보드(32bit) 시작 중...
start "AI Trading (32bit)" cmd /c "%PROJ%\run.bat"

echo.
echo 시스템이 시작되었습니다.
echo - AI 서버: 별도 창에서 실행 중 (포트 5555)
echo - 메인 대시보드: 별도 창에서 실행 중
echo.
echo 이 창은 닫으셔도 됩니다.
timeout /t 5
