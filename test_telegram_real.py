import sys
print("0. 시작")
sys.path.insert(0, r"C:\trading\app")

from utils.env_loader import load_env
from notify.telegram_bot import TelegramBot

env = load_env()

bot = TelegramBot(
    token   = env["TELEGRAM_TOKEN"],
    chat_id = env["TELEGRAM_CHAT_ID"],
    enabled = True,
)

print("\n[ 실제 전송 테스트 ]")
bot.send_buy(
    ticker   = "005930",
    name     = "삼성전자",
    price    = 82000,
    qty      = 36,
    strategy = "TrendStrategy",
)

bot.send_daily_report(
    date        = "2026-02-21",
    total_asset = 10_350_000,
    pnl         =    350_000,
    pnl_rate    =        3.5,
    buy_count   =          5,
    sell_count  =          5,
    win_count   =          4,
    lose_count  =          1,
)

print("\n완료 ✅")