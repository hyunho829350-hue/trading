import sys
import os

sys.path.insert(0, r"C:\trading\app")

print("1. 임포트 시작")

from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget

print("2. PyQt5 임포트 OK")

from kiwoom.kiwoom_api import KiwoomAPI
from utils.logger import get_logger

print("3. KiwoomAPI 임포트 OK")

log = get_logger("LOGIN")


def run_login_check():
    print("4. QApplication 생성")
    app = QApplication(sys.argv)

    print("5. KiwoomAPI 생성")
    kw = KiwoomAPI()

    print("6. 로그인 요청")
    print()
    print("=" * 50)
    print("  키움 API 로그인 테스트")
    print("=" * 50)
    print("  로그인 팝업창이 뜨면 ID/PW 입력하세요.")
    print()

    ok = kw.login(timeout_sec=60)

    if not ok:
        print("  ❌ 로그인 실패")
        sys.exit(1)

    print()
    print("=" * 50)
    print("  연결 정보")
    print("=" * 50)
    print("  연결 상태 : " + str(kw.get_connect_state()))
    print("  서버 타입 : " + kw.get_server_type())
    print("  사용자 ID : " + kw.get_user_id())
    print("  사용자명  : " + kw.get_user_name())

    acc_list = kw.get_account_list()
    print("  계좌 수   : " + str(len(acc_list)) + "개")
    for i, acc in enumerate(acc_list):
        print("    [" + str(i+1) + "] " + acc)

    server = kw.get_server_type()
    if server == "실서버":
        print()
        print("  ⚠️  실서버 연결됨")
    else:
        print()
        print("  ✅ 모의투자 서버 연결됨")

    print()
    print("  ✅ Step 2-2 로그인 완료")
    print("=" * 50)

    sys.exit(0)


if __name__ == "__main__":
    print("0. login.py 시작")
    run_login_check()