import json
import yfinance as yf
from pathlib import Path
from datetime import datetime
# calc_score 함수 마지막 score 반환 직전에 추가
from data.news_analyzer import get_cached_sentiment

UNIVERSE_PATH  = Path("data/universe.json")
WATCHLIST_PATH = Path("data/watchlist.json")
MAX_WATCHLIST  = 15
SLOTS = {"KRX": 8, "US": 5, "ETF": 2}

FIXED_WATCHLIST = [
    {"ticker": "AGIX", "name": "KraneShares AI ETF", "market": "ETF", "sector": "AI", "score": 100}
]

ETF_NAMES = {
    'AGIX': 'KraneShares AI & Tech ETF',
    'BOTZ': 'Global X Robotics & AI ETF',
    'AIQ':  'Global X AI & Tech ETF',
    'ARKQ': 'ARK Autonomous Tech ETF',
    'QQQ':  'Invesco QQQ Trust',
    'XLK':  'Technology Select SPDR ETF',
    'SMH':  'VanEck Semiconductor ETF',
    'SOXX': 'iShares Semiconductor ETF',
    'FIVG': 'Defiance 5G Next Gen ETF',
    'WCLD': 'WisdomTree Cloud Computing ETF',
    'XLE':  'Energy Select SPDR ETF',
    'VDE':  'Vanguard Energy ETF',
}

def load_universe():
    return json.loads(UNIVERSE_PATH.read_text())

def load_watchlist():
    try:
        return json.loads(WATCHLIST_PATH.read_text())
    except:
        return []

def save_watchlist(watchlist):
    WATCHLIST_PATH.write_text(json.dumps(watchlist, ensure_ascii=False, indent=2))

def get_yf_ticker(market, ticker):
    return f"{ticker}.KS" if market == "KRX" else ticker

def calc_score(ticker, market):
    try:
        t    = yf.Ticker(get_yf_ticker(market, ticker))
        hist = t.history(period="60d")
        if len(hist) < 20:
            return None
        close  = hist["Close"]
        volume = hist["Volume"]
        current = float(close.iloc[-1])
        ma5   = float(close.tail(5).mean())
        ma20  = float(close.tail(20).mean())
        vol20 = float(volume.tail(20).mean())
        vol5  = float(volume.tail(5).mean())
        delta = close.diff()
        gain  = delta.where(delta > 0, 0).tail(14).mean()
        loss  = (-delta.where(delta < 0, 0)).tail(14).mean()
        rsi   = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50
        high52 = float(close.tail(252).max()) if len(close) >= 252 else float(close.max())
        pct_from_high = (current - high52) / high52 * 100
        vol_ratio = vol5 / vol20 if vol20 > 0 else 1

        score = 0
        score += 25 if ma5 > ma20 else (10 if ma5 > ma20 * 0.98 else 0)
        score += 25 if vol_ratio >= 2.0 else (15 if vol_ratio >= 1.5 else (8 if vol_ratio >= 1.2 else 0))
        score += 25 if 30 <= rsi <= 60 else (15 if rsi < 30 else (10 if rsi <= 70 else 0))
        score += 25 if -10 <= pct_from_high <= 0 else (15 if -20 <= pct_from_high < -10 else (8 if -30 <= pct_from_high < -20 else 0))

        # B) 뉴스 감성점수 반영
        sentiment = get_cached_sentiment(ticker)
        score = min(100, max(0, score + sentiment))  # 0~100 범위 유지

        return {"ticker": ticker, "score": score, "rsi": round(float(rsi), 1),
                "vol_ratio": round(vol_ratio, 2), "market": market}
    except Exception as e:
        print(f"  ⚠️ {ticker}: {e}")
        return None

def run_screening(market):
    universe = load_universe()
    results  = []
    slots    = SLOTS.get(market, 5)
    for sector, tickers in universe.get(market, {}).items():
        print(f"  [{sector}]")
        for ticker in tickers:
            r = calc_score(ticker, market)
            if r and r["score"] >= 50:
                r["sector"] = sector
                results.append(r)
                print(f"    ✅ {ticker}: {r['score']}점")
            else:
                print(f"    ⬜ {ticker}: {r['score'] if r else 'N/A'}점")
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:slots]

def get_krx_name_map() -> dict:
    """KRX 전체 종목명 매핑 (FinanceDataReader)"""
    try:
        import FinanceDataReader as fdr
        df = fdr.StockListing('KRX')[['Code', 'Name']]
        return df.set_index('Code')['Name'].to_dict()
    except Exception as e:
        print(f"  ⚠️ KRX 종목명 조회 실패: {e}")
        return {}

def update_watchlist():
    from alerts.telegram import send_message
    from data.portfolio_manager import load_portfolio

    # KRX 종목명 매핑 미리 로드
    krx_names = get_krx_name_map()

    portfolio_tickers = {h["ticker"].replace(".KS", "") for h in load_portfolio()}
    new_watchlist = list(FIXED_WATCHLIST)
    summary = ["📋 *Watchlist 업데이트*\n"]

    for market in ["KRX", "US", "ETF"]:
        print(f"\n🔍 {market} 스크리닝 중...")
        top = run_screening(market)
        for item in top:
            if item["ticker"] not in {w["ticker"] for w in new_watchlist}:
                # ← 종목명 자동 반영
                if market == "KRX":
                    name = krx_names.get(item["ticker"], item["ticker"])
                elif market == "ETF":
                    name = ETF_NAMES.get(item["ticker"], item["ticker"])
                else:  # US
                    try:
                        info = yf.Ticker(item["ticker"]).info
                        name = info.get("shortName") or info.get("longName") or item["ticker"]
                    except:
                        name = item["ticker"]
                new_watchlist.append({
                    "ticker": item["ticker"],
                    "name":   name,
                    "market": market,
                    "sector": item.get("sector", ""),
                    "score":  item["score"],
                })
        summary.append(f"*{market}*: {', '.join(t['ticker'] for t in top) or '없음'}")

    # 보유 종목 강제 유지
    existing = {w["ticker"] for w in new_watchlist}
    for pt in portfolio_tickers:
        if pt not in existing:
            name = krx_names.get(pt, pt)
            new_watchlist.append({
                "ticker": pt,
                "name":   name,
                "market": "KRX",
                "sector": "보유종목",
                "score":  100,
            })

    new_watchlist = new_watchlist[:MAX_WATCHLIST]
    save_watchlist(new_watchlist)
    summary.append(f"\n총 {len(new_watchlist)}개 | {datetime.now().strftime('%m/%d %H:%M')}")
    send_message("\n".join(summary))
    print(f"✅ watchlist 업데이트: {len(new_watchlist)}개")

if __name__ == "__main__":
    update_watchlist()