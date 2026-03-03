import sys
import time
print("0. 시작")
sys.path.insert(0, r"C:\trading\app")

from web.app import run_server_thread, update_state, add_log

# ── 백그라운드로 웹서버 시작 ─────────────────
run_server_thread(port=5000)
time.sleep(1)

# ── 더미 데이터 주입 ─────────────────────────
update_state({
    "capital":         7_200_000,
    "eval_value":      3_142_800,
    "total_asset":    10_342_800,
    "initial_capital":10_000_000,
    "pnl":               342_800,
    "pnl_rate":              3.43,
    "buy_count":               3,
    "sell_count":              2,
    "positions": {
        "005930": {"qty": 36, "avg_price": 82000, "pnl_rate":  2.5},
        "000660": {"qty": 11, "avg_price": 90000, "pnl_rate": -1.2},
    },
    "risk": {
        "blocked":          False,
        "block_reason":     "",
        "daily_pnl":        342_800,
        "daily_pnl_rate":     3.43,
        "daily_trades":         3,
        "consecutive_loss":     0,
    },
})

add_log("🟢 005930 삼성전자 매수 82,000원 × 36주")
add_log("🟢 000660 SK하이닉스 매수 90,000원 × 11주")
add_log("🔵 035420 NAVER 매도 215,000원 손익 +142,800원")
add_log("⛔ 리스�� 체크 통과")
add_log("🚀 매매 시스템 시작")

print("\n✅ 웹 대시보드 실행 중")
print("브라우저에서 열어주세요 → http://localhost:5000")
print("종료: Ctrl+C\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n종료 ✅")