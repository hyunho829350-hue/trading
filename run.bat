@echo off
:: ============================================================
:: run.bat  –  스캘핑 자동매매 시스템 실행 스크립트
:: ============================================================

:: 스크립트가 있는 폴더로 이동
cd /d "%~dp0"

:: Python 설치 여부 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python 이 설치되어 있지 않습니다.
    echo       https://www.python.org 에서 Python 3.10 이상을 설치하세요.
    pause
    exit /b 1
)

:: 패키지 설치 (requirements.txt)
echo [설치] 필요 패키지를 확인합니다...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [오류] 패키지 설치에 실패했습니다. 로그를 확인하세요.
    pause
    exit /b 1
)

:: 메인 프로그램 실행
echo [시작] 자동매매 시스템을 실행합니다...
python main.py

:: 비정상 종료 시 메시지 표시
if errorlevel 1 (
    echo.
    echo [오류] 프로그램이 비정상 종료되었습니다 (종료 코드: %errorlevel%).
    pause
)
