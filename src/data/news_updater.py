import json
from pathlib import Path
from data.news import collect_all_news
from data.news_analyzer import (
    analyze_news_for_universe,
    update_universe_from_news,
    set_sentiment_cache,
)

def run_news_update():
    """매일 07:00 실행 — 뉴스 수집 + universe 업데이트 + 감성캐시 세팅"""
    from alerts.telegram import send_message

    print("\n📰 뉴스 기반 universe 업데이트 시작...")

    # 현재 watchlist 종목들 뉴스 수집
    try:
        watchlist = json.loads(Path("data/watchlist.json").read_text())
        tickers = [w["ticker"] for w in watchlist]
    except:
        tickers = []

    # 뉴스 수집
    articles = collect_all_news(tickers)
    if not articles:
        print("  ⚠️ 뉴스 없음")
        return

    # Claude 분석
    print("  🤖 Claude 뉴스 분석 중...")
    analysis = analyze_news_for_universe(articles)

    # A) universe 업데이트
    added = update_universe_from_news(analysis)

    # B) 감성점수 캐시 세팅 (당일 스크리닝에 반영)
    sentiment = analysis.get("sentiment_scores", {})
    set_sentiment_cache(sentiment)

    # 텔레그램 알림
    lines = ["📰 *뉴스 기반 업데이트*\n"]

    if added:
        lines.append("*신규 종목 추가:*")
        for a in added:
            lines.append(f"  • {a}")
    else:
        lines.append("신규 종목 없음")

    if sentiment:
        lines.append("\n*감성점수 반영:*")
        for ticker, score in sorted(sentiment.items(),
                                    key=lambda x: abs(x[1]), reverse=True)[:5]:
            emoji = "📈" if score > 0 else "📉"
            lines.append(f"  {emoji} {ticker}: {score:+d}")

    send_message("\n".join(lines))
    print("✅ 뉴스 업데이트 완료")

if __name__ == "__main__":
    run_news_update()