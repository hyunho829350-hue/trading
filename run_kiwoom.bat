@echo off
:: ============================================================
:: run_kiwoom.bat  –  키움 OpenAPI+ 실거래 모드 실행 스크립트
::
:: 키움 OpenAPI+ COM 오브젝트는 32비트 전용입니다.
:: 이 배치 파일은 32비트 Python 3 으로 실행합니다.
::
:: 사전 준비:
::   1. 키움 OpenAPI+ 설치 (32비트 COM)
::      https://www1.kiwoom.com/nkw.templateFrameSet.do?m=m1408000000
::   2. 32비트 Python 3.10 이상 설치
::      https://www.python.org  →  Windows installer (32-bit)
::   3. config.py 에서  API_MOCK_MODE = False  로 변경
::   4. config.py 에서  KIWOOM_ACCOUNT = "실제계좌번호"  로 변경
::
:: 시뮬레이션 모드라면 run.bat 을 사용하세요.
:: ============================================================
setlocal

:: 스크립트가 있는 폴더로 이동
cd /d "%~dp0"

:: ── 32비트 Python 탐지 ────────────────────────────────────────────
set PY=
where py >nul 2>&1
if not errorlevel 1 (
    py -3-32 --version >nul 2>&1
    if not errorlevel 1 (
        set PY=py -3-32
    )
)

if "%PY%"=="" (
    echo [오류] 32비트 Python 3 을 찾을 수 없습니다.
    echo        키움 OpenAPI+ 는 32비트 Python 이 필요합니다.
    echo        https://www.python.org 에서 Windows installer ^(32-bit^) 를 설치하세요.
    pause
    exit /b 1
)

:: ── 32비트 확인 ─────────────────────────────────────────────────
:: struct.calcsize('P') == 4  →  32비트 Python
:: struct.calcsize('P') == 8  →  64비트 Python
%PY% -c "import struct; exit(0 if struct.calcsize('P')==4 else 1)" >nul 2>&1
if errorlevel 1 (
    echo [오류] 32비트 Python 확인에 실패했습니다.
    echo        py -3-32 이 64비트 Python 을 가리키고 있을 수 있습니다.
    pause
    exit /b 1
)

:: ── config.py 에서 API_MOCK_MODE 확인 ────────────────────────────
:: API_MOCK_MODE=True 이면 경고 후 계속 여부를 묻는다
%PY% -c "import config; exit(0 if not config.API_MOCK_MODE else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [경고] config.py 의 API_MOCK_MODE 가 True 로 설정되어 있습니다.
    echo        실거래를 원하시면 config.py 에서 API_MOCK_MODE = False 로 변경하세요.
    echo        계속하면 시뮬레이션 모드로 실행됩니다.
    echo.
    choice /c YN /m "계속 진행하시겠습니까?"
    if errorlevel 2 exit /b 0
)

:: ── 패키지 설치 ───────────────────────────────────────────────────
echo [설치] 필요 패키지를 확인합니다...
%PY% -m pip install -r requirements.txt -r requirements-kiwoom.txt --quiet
if errorlevel 1 (
    echo [오류] 패키지 설치에 실패했습니다.
    echo        %PY% -m pip install -r requirements.txt -r requirements-kiwoom.txt
    pause
    exit /b 1
)

:: ── 메인 프로그램 실행 ────────────────────────────────────────────
echo [시작] 자동매매 시스템을 실행합니다... ^(키움 OpenAPI+ 모드^)
%PY% main.py

if errorlevel 1 (
    echo.
    echo [오류] 프로그램이 비정상 종료되었습니다 ^(종료 코드: %errorlevel%^).
    pause
)

endlocal
