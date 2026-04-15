import os
import json
import anthropic
import yfinance as yf
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MAX_ORDER_AMT = 1_000_000  # 1회 최대 100만원
MAX_DAILY_ORDERS = 5
STOP_LOSS_PCT = -5.0

def get_watchlist():
    return json.loads(Path("data/watchlist.json").read_text())

def get_price_data(ticker: str) -> dict:
    """최근 5일 가격 + 기술지표"""
    t = yf.Ticker(f"{ticker}.KS")
    hist = t.history(period="20d")
    if hist.empty:
        return {}
    close = hist["Close"]
    current = float(close.iloc[-1])
    ma5  = float(close.tail(5).mean())
    ma20 = float(close.tail(20).mean())
    # RSI 계산
    delta = close.diff()
    gain  = delta.where(delta > 0, 0).tail(14).mean()
    loss  = (-delta.where(delta < 0, 0)).tail(14).mean()
    rsi   = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50

    return {
        "current": round(current),
        "ma5":     round(ma5),
        "ma20":    round(ma20),
        "rsi":     round(rsi, 1),
        "trend":   "상승" if ma5 > ma20 else "하락",
    }

def generate_signal(ticker: str, name: str, holding: dict = None) -> dict:
    """Claude로 매매 신호 생성"""
    price_data = get_price_data(ticker)
    if not price_data:
        return {"action": "hold", "reason": "데이터 없음"}

    holding_str = ""
    if holding:
        holding_str = f"""
현재 보유: {holding['qty']}주 | 평균단가: {holding['avg_price']:,.0f}원
현재 수익률: {holding['pnl_pct']:+.2f}%
"""

    prompt = f"""당신은 퀀트 트레이더입니다. 아래 데이터를 보고 매매 신호를 판단하세요.

종목: {name} ({ticker})
현재가: {price_data['current']:,}원
5일MA: {price_data['ma5']:,} | 20일MA: {price_data['ma20']:,}
RSI: {price_data['rsi']} | 추세: {price_data['trend']}
{holding_str}

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "action": "buy" or "sell" or "hold",
  "qty": 매수/매도 수량 (hold면 0),
  "reason": "판단 근거 한 줄",
  "confidence": 1~10
}}

제약조건:
- buy: 현재가 x qty <= {MAX_ORDER_AMT:,}원
- confidence 7 이상일 때만 buy/sell 추천
- 보유 종목 아니면 sell 불가"""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = msg.content[0].text.strip()
    # JSON 파싱
    import re
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return {"action": "hold", "reason": "파싱 실패"}
    signal = json.loads(match.group())
    signal["ticker"] = ticker
    signal["name"]   = name
    signal["price"]  = price_data["current"]
    return signal

if __name__ == "__main__":
    watchlist = get_watchlist()
    print("🤖 Claude 신호 분석 중...\n")
    for item in watchlist[:3]:  # 테스트는 3종목만
        signal = generate_signal(item["ticker"], item["name"])
        action_emoji = {"buy": "🟢", "sell": "🔴", "hold": "⚪"}.get(signal["action"], "⚪")
        print(f"{action_emoji} {signal['name']}: {signal['action'].upper()} "
              f"| 신뢰도: {signal.get('confidence', '-')}/10 "
              f"| {signal.get('reason', '')}")