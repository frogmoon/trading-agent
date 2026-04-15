import os
import json
import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

UNIVERSE_PATH = Path("data/universe.json")

def load_universe() -> dict:
    return json.loads(UNIVERSE_PATH.read_text())

def save_universe(universe: dict):
    UNIVERSE_PATH.write_text(json.dumps(universe, ensure_ascii=False, indent=2))

def analyze_news_for_universe(articles: list[dict]) -> dict:
    """
    A) 신규 종목 발굴
    B) 기존 종목 감성점수 반환
    """
    universe = load_universe()

    # 현재 universe 전체 종목 목록
    existing_tickers = set()
    for market in universe.values():
        for tickers in market.values():
            existing_tickers.update(tickers)

    news_text = "\n".join([
        f"- {a['title']} ({a['source']})"
        for a in articles[:30]
    ])

    prompt = f"""당신은 한국/미국 주식 전문 애널리스트입니다.
아래 오늘의 주요 뉴스를 분석하세요.

## 오늘의 뉴스
{news_text}

## 현재 관심 종목 (이미 추적 중)
{', '.join(sorted(existing_tickers)[:30])}

다음 두 가지를 JSON으로 응답하세요:

1. **신규 종목 발굴**: 뉴스에서 수혜가 예상되지만 현재 목록에 없는 종목
2. **감성 점수**: 현재 목록 중 뉴스에 언급된 종목의 감성 (-20 ~ +20)

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "new_tickers": [
    {{
      "ticker": "종목코드",
      "name": "종목명",
      "market": "KRX 또는 US 또는 ETF",
      "sector": "섹터명 (반도체/밸류업_금융/밸류업_지주/광통신/AI_빅테크/AI_인프라/AI_애플리케이션/에너지_헤지)",
      "reason": "추가 이유 한 줄",
      "confidence": 1~10
    }}
  ],
  "sentiment_scores": {{
    "종목코드": 감성점수,
    "종목코드": 감성점수
  }}
}}

제약조건:
- new_tickers: confidence 7 이상만, 최대 5개
- KRX 종목코드는 6자리 숫자 (예: 005930)
- US 종목코드는 영문 티커 (예: NVDA)
- 확실하지 않으면 추가하지 마세요"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()

        # JSON 파싱
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return {"new_tickers": [], "sentiment_scores": {}}
        return json.loads(match.group())
    except Exception as e:
        print(f"  ⚠️ Claude 분석 오류: {e}")
        return {"new_tickers": [], "sentiment_scores": {}}

def update_universe_from_news(analysis: dict) -> list[str]:
    """A) 신규 종목을 universe.json에 추가"""
    universe = load_universe()
    added = []

    # 전체 universe에서 이미 존재하는 ticker 목록 (시장 구분 없이)
    existing_all = set()
    for market_data in universe.values():
        for tickers in market_data.values():
            existing_all.update(tickers)

    for item in analysis.get("new_tickers", []):
        ticker  = item.get("ticker", "").strip()
        market  = item.get("market", "KRX")
        sector  = item.get("sector", "AI_빅테크")
        name    = item.get("name", ticker)
        reason  = item.get("reason", "")

        if not ticker:
            continue

        # ← 핵심: 전체 universe에서 중복 체크
        if ticker in existing_all:
            print(f"  ⏭️ 이미 존재: {ticker} → 스킵")
            continue

        if market not in universe:
            universe[market] = {}
        if sector not in universe[market]:
            universe[market][sector] = []

        universe[market][sector].append(ticker)
        existing_all.add(ticker)  # 같은 실행 내 중복 방지
        added.append(f"{name}({ticker}) → {market}/{sector}: {reason}")
        print(f"  ✅ universe 추가: {ticker} [{market}/{sector}]")

    if added:
        save_universe(universe)

    return added

def get_sentiment_scores(analysis: dict) -> dict:
    """B) 감성 점수 반환 (screener에서 활용)"""
    return analysis.get("sentiment_scores", {})

# 전역 감성점수 캐시 (당일 스크리닝에서 참조)
_sentiment_cache: dict = {}

def set_sentiment_cache(scores: dict):
    global _sentiment_cache
    _sentiment_cache = scores

def get_cached_sentiment(ticker: str) -> int:
    return _sentiment_cache.get(ticker, 0)