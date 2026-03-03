import sys
print("0. 시작")
sys.path.insert(0, r"C:\trading\app")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEventLoop, QTimer
from kiwoom.kiwoom_api import KiwoomAPI
from kiwoom.ohlcv import OHLCV

app = QApplication(sys.argv)
kw  = KiwoomAPI()

print("로그인 중...")
ok = kw.login(timeout_sec=60)
if not ok:
    print("로그인 실패")
    sys.exit(1)
print("로그인 성공")

ov = OHLCV(kw)

# 보유종목 35개
codes = [
    "000120", "005380", "008830", "012450", "015760",
    "018880", "024060", "028260", "028300", "033100",
    "035420", "039030", "042660", "047040", "056080",
    "064350", "068270", "086520", "087010", "090430",
    "090710", "141080", "187870", "200470", "233740",
    "251270", "257720", "267260", "277810", "278470",
    "289080", "298040", "299660", "403870", "454910",
]

print()
print("일봉 다운로드 시작: " + str(len(codes)) + "개 종목")
print()

ok_list   = []
fail_list = []

for i, code in enumerate(codes):
    try:
        rows = ov.get_day_ohlcv(code, max_pages=2)
        if rows:
            ov.save_csv(code, rows, "day")
            ok_list.append(code)
            print("  [" + str(i+1).rjust(2) + "/" + str(len(codes)) + "]" +
                  " " + code + " → " + str(len(rows)) + "개 저장")
        else:
            fail_list.append(code)
            print("  [" + str(i+1).rjust(2) + "/" + str(len(codes)) + "]" +
                  " " + code + " → 데이터 없음")
    except Exception as e:
        fail_list.append(code)
        print("  [" + str(i+1).rjust(2) + "/" + str(len(codes)) + "]" +
              " " + code + " → 오류: " + str(e))

    # TR 요청 간격 (0.5초)
    loop = QEventLoop()
    t = QTimer()
    t.setSingleShot(True)
    t.timeout.connect(loop.quit)
    t.start(500)
    loop.exec_()
    t.stop()

print()
print("=" * 40)
print("  다운로드 완료")
print("  성공: " + str(len(ok_list)) + "개")
print("  실패: " + str(len(fail_list)) + "개")
if fail_list:
    print("  실패목록: " + str(fail_list))
print("=" * 40)
print()
print("Step 3-5 다운로드 완료")
sys.exit(0)