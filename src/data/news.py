import feedparser
import yfinance as yf

RSS_FEEDS = [
    ("한국경제", "https://www.hankyung.com/feed/all-news"),
    ("매일경제", "https://www.mk.co.kr/rss/40300001/"),
    ("Investing", "https://www.investing.com/rss/news.rss"),
]

KEYWORDS = [
    "반도체", "AI", "인공지능", "데이터센터", "HBM", "엔비디아",
    "삼성", "하이닉스", "광통신", "밸류업", "배당", "자사주",
    "금융", "은행", "지주", "에너지", "유가", "전력",
    "NVDA", "MSFT", "GOOGL", "META", "AMZN"
]

def get_rss_news(max_items: int = 30) -> list[dict]:
    """RSS 뉴스 수집 + 투자 관련 키워드 필터링"""
    articles = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                content = title + summary

                # 투자 관련 키워드 포함 기사만
                if any(kw.lower() in content.lower() for kw in KEYWORDS):
                    articles.append({
                        "title":   title,
                        "summary": summary[:200],
                        "source":  source,
                        "time":    entry.get("published", ""),
                    })
                    count += 1
                    if count >= max_items:
                        break
            print(f"  {source}: {count}건 (필터 후)")
        except Exception as e:
            print(f"  ⚠️ {source} RSS 오류: {e}")
    return articles

def get_yfinance_news(tickers: list[str]) -> list[dict]:
    """보유/관심 종목 관련 영문 뉴스"""
    articles = []
    for ticker in tickers[:10]:
        try:
            t = yf.Ticker(ticker)
            for news in (t.news or [])[:3]:
                articles.append({
                    "title":   news.get("title", ""),
                    "summary": news.get("summary", ""),
                    "source":  ticker,
                    "time":    str(news.get("providerPublishTime", "")),
                })
        except:
            pass
    return articles

def collect_all_news(watchlist_tickers: list[str]) -> list[dict]:
    print("  📰 RSS 뉴스 수집 중...")
    rss = get_rss_news(30)

    print("  📰 종목별 뉴스 수집 중...")
    yf_news = get_yfinance_news(watchlist_tickers)

    all_news = rss + yf_news
    print(f"  총 {len(all_news)}건 수집")
    return all_news