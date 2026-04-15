import schedule
import time
from dotenv import load_dotenv
from sys import path
path.insert(0, "src")

load_dotenv()

from agents.analyzer import morning_briefing, closing_review
from agents.trader import run_trading_cycle, flush_pending_updates
from data.screener import update_watchlist
from data.news_updater import run_news_update
from alerts.telegram import send_message

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

for day in WEEKDAYS:
    getattr(schedule.every(), day).at("07:00").do(run_news_update)
    getattr(schedule.every(), day).at("08:40").do(update_watchlist)
    getattr(schedule.every(), day).at("08:50").do(morning_briefing)
    getattr(schedule.every(), day).at("09:30").do(run_trading_cycle)
    getattr(schedule.every(), day).at("14:00").do(run_trading_cycle)
    getattr(schedule.every(), day).at("15:35").do(closing_review)
    getattr(schedule.every(), day).at("22:00").do(update_watchlist)

if __name__ == "__main__":
    print("✅ Trading Agent 시작")
    print("   - 07:00 뉴스 분석 + universe 업데이트")
    print("   - 08:40 watchlist 스크리닝 (KRX)")
    print("   - 08:50 모닝 브리핑")
    print("   - 09:30 매매 신호 #1")
    print("   - 14:00 매매 신호 #2")
    print("   - 15:35 장 마감 리뷰")
    print("   - 22:00 watchlist 스크리닝 (US)")

    flush_pending_updates()
    send_message("🚀 *Trading Agent 시작*\n모든 스케줄이 등록됐어요.")
    morning_briefing()

    while True:
        schedule.run_pending()
        time.sleep(30)
