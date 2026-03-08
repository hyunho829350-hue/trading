@echo off
:: ============================================================
:: run.bat  –  스캘핑 자동매매 시스템 실행 스크립트
::             시뮬레이션(Mock) 모드 전용 – 64비트 Python 사용
::
:: 실제 키움 OpenAPI+ 연동이 필요하면 run_kiwoom.bat 을 사용하세요.
:: ============================================================
setlocal

:: 스크립트가 있는 폴더로 이동
cd /d "%~dp0"

:: ── Python 탐지 (py 런처 우선 → python 폴백) ────────────────────
set PY=
where py >nul 2>&1
if not errorlevel 1 (
    :: py 런처가 있으면 64비트 Python 3 지정
    py -3-64 --version >nul 2>&1
    if not errorlevel 1 (
        set PY=py -3-64
    ) else (
        :: 64비트가 없으면 기본 py -3 사용
        py -3 --version >nul 2>&1
        if not errorlevel 1 (
            set PY=py -3
        )
    )
)

if "%PY%"=="" (
    :: py 런처 없음 → python 명령으로 폴백
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [오류] Python 이 설치되어 있지 않습니다.
        echo       https://www.python.org 에서 Python 3.10 이상 ^(64비트^)를 설치하세요.
        pause
        exit /b 1
    )
    set PY=python
)

:: ── 32비트 Python 경고 ──────────────────────────────────────────
:: struct.calcsize('P') == 8  →  64비트 Python
:: struct.calcsize('P') == 4  →  32비트 Python
%PY% -c "import struct; exit(0 if struct.calcsize('P')==8 else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [경고] 32비트 Python 이 감지되었습니다.
    echo        PyQt5 는 64비트 Python 에서 실행해야 합니다.
    echo        64비트 Python 3 을 설치하거나 py -3-64 명령을 사용하세요.
    echo        실제 키움 API 모드라면 run_kiwoom.bat 을 사용하세요.
    echo.
    pause
    exit /b 1
)

:: ── 패키지 설치 (requirements.txt) ───────────────────────────────
echo [설치] 필요 패키지를 확인합니다...
%PY% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [오류] 패키지 설치에 실패했습니다. 아래 명령으로 수동 설치하세요:
    echo        %PY% -m pip install -r requirements.txt
    pause
    exit /b 1
)

:: ── 메인 프로그램 실행 ────────────────────────────────────────────
echo [시작] 자동매매 시스템을 실행합니다... ^(시뮬레이션 모드^)
%PY% main.py

:: 비정상 종료 시 메시지 표시
if errorlevel 1 (
    echo.
    echo [오류] 프로그램이 비정상 종료되었습니다 ^(종료 코드: %errorlevel%^).
    pause
)

endlocal
