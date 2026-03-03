import sys
import time
print("0. 시작")
sys.path.insert(0, r"C:\trading\app")

from scheduler.market_scheduler import MarketScheduler
from utils.logger import get_logger

log = get_logger("TEST")


# ── 콜백 함수 정의 ───────────────────────────
def on_reset(dt):
    log.info("▶ 일일 리셋 콜백 호출 " + str(dt))

def on_start(dt):
    log.info("▶ 장 시작 콜백 호출 → 매매 시작! " + str(dt))

def on_pre_close(dt):
    log.info("▶ 신규 매수 중단 콜백 호출 " + str(dt))

def on_stop(dt):
    log.info("▶ 장 종료 콜백 호출 → 청산 + 리포트! " + str(dt))


# ── 스케줄러 생성 및 콜백 등록 ──────────────
scheduler = MarketScheduler()
scheduler.on_reset(on_reset)
scheduler.on_start(on_start)
scheduler.on_pre_close(on_pre_close)
scheduler.on_stop(on_stop)

# ── 현재 상태 출력 ───────────────────────────
scheduler.print_status()

# ── 스케줄러 시작 ────────────────────────────
scheduler.start()

print("\n스케줄러 실행 중... (10초 후 종료)")
print("현재 시각에 따라 콜백이 자동 호출됩니다.\n")

for i in range(10):
    time.sleep(1)
    s = scheduler.status()
    print(
        "[" + str(i+1) + "초] "
        "거래일=" + str(s["is_trading_day"]) +
        " 장시작=" + str(s["market_opened"]) +
        " 매수중단=" + str(s["pre_closed"]) +
        " 장종���=" + str(s["market_closed"])
    )

scheduler.stop()
scheduler.print_status()
print("\n완료 ✅")