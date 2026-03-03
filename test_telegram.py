import sys
print("0. 시작")
sys.path.insert(0, r"C:\trading\app")

from notify.telegram_bot import TelegramBot

# ── enabled=False → 실제 전송 없이 로그만 출력 ──
bot = TelegramBot(
    token   = "YOUR_BOT_TOKEN",
    chat_id = "YOUR_CHAT_ID",
    enabled = False,   # 테스트 모드
)

print("\n[ 테스트 1: 매수 알림 ]")
bot.send_buy(
    ticker   = "005930",
    name     = "삼성전자",
    price    = 82000,
    qty      = 36,
    strategy = "TrendStrategy",
)

print("\n[ 테스트 2: 매도 알림 (수익) ]")
bot.send_sell(
    ticker   = "005930",
    name     = "삼성전자",
    price    = 87300,
    qty      = 36,
    pnl      = 190800,
    pnl_rate = 6.46,
    reason   = "익절",
)

print("\n[ 테스트 3: 매도 알림 (손실) ]")
bot.send_sell(
    ticker   = "000660",
    name     = "SK하이닉스",
    price    = 88000,
    qty      = 11,
    pnl      = -22000,
    pnl_rate = -2.22,
    reason   = "손절",
)

print("\n[ 테스트 4: 리스크 차단 알림 ]")
bot.send_risk_block("연속손실 3회 도달")

print("\n[ 테스트 5: 에러 알림 ]")
bot.send_error("TradeEngine.on_bar", "KIS API 연결 오류: timeout")

print("\n[ 테스트 6: 일일 요약 리포트 ]")
bot.send_daily_report(
    date       = "2026-02-21",
    total_asset= 10_350_000,
    pnl        =    350_000,
    pnl_rate   =       3.5,
    buy_count  =         5,
    sell_count =         5,
    win_count  =         4,
    lose_count =         1,
)

print("\n[ 테스트 7: 시스템 시작 알림 ]")
bot.send_start(
    capital    = 10_000_000,
    strategies = ["TrendStrategy", "VolumeStrategy", "CombinedStrategy"],
)

print("\n[ 테스트 8: 시스템 종료 알림 ]")
bot.send_stop(
    total_asset = 10_350_000,
    pnl         =    350_000,
    pnl_rate    =       3.5,
)

print("\n완료 ���")