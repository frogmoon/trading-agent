import os
import json
import re
import anthropic
import yfinance as yf
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MAX_ORDER_AMT  = 1_000_000  # 1회 최대 100만원
MAX_DAILY_ORDERS = 5
STOP_LOSS_PCT  = -5.0
ENERGY_TICKERS = ["XOM", "CVX", "COP", "SLB", "EOG"]

def get_watchlist() -> list:
    return json.loads(Path("data/watchlist.json").read_text())

def get_price_data(ticker: str, market: str = "KRX") -> dict:
    """현재가 + 기술지표"""
    yf_ticker = f"{ticker}.KS" if market == "KRX" else ticker
    try:
        t    = yf.Ticker(yf_ticker)
        hist = t.history(period="20d")
        if hist.empty:
            return {}
        close   = hist["Close"]
        current = float(close.iloc[-1])
        ma5     = float(close.tail(5).mean())
        ma20    = float(close.tail(20).mean())
        delta   = close.diff()
        gain    = delta.where(delta > 0, 0).tail(14).mean()
        loss    = (-delta.where(delta < 0, 0)).tail(14).mean()
        rsi     = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50
        return {
            "current": round(current),
            "ma5":     round(ma5),
            "ma20":    round(ma20),
            "rsi":     round(float(rsi), 1),
            "trend":   "상승" if ma5 > ma20 else "하락",
        }
    except:
        return {}

def calc_max_qty(current_price: int, deposit: int) -> int:
    """예수금 + 1회 한도 기반 최대 매수 수량"""
    budget = min(MAX_ORDER_AMT, deposit)
    if current_price <= 0 or budget <= 0:
        return 0
    return max(1, budget // current_price)

def generate_signal(ticker: str, name: str,
                    holding: dict = None,
                    market: str = "KRX",
                    deposit: int = 0) -> dict:
    """Claude 매매 신호 생성 — 예수금 + 종목명 반영"""

    price_data = get_price_data(ticker, market)
    if not price_data:
        return {"action": "hold", "reason": "데이터 없음",
                "ticker": ticker, "name": name, "price": 0}

    current_price = price_data["current"]
    max_qty       = calc_max_qty(current_price, deposit)

    holding_str = ""
    if holding:
        holding_str = (
            f"현재 보유: {holding['qty']}주 | "
            f"평균단가: {holding['avg_price']:,.0f}원 | "
            f"수익률: {holding['pnl_pct']:+.2f}%\n"
        )

    # 에너지 종목은 신뢰도 기준 강화
    min_confidence = 8 if ticker in ENERGY_TICKERS else 7

    prompt = f"""당신은 퀀트 트레이더입니다. 아래 데이터를 보고 매매 신호를 판단하세요.

종목: {name} ({ticker}) [{market}]
현재가: {current_price:,}원
5일MA: {price_data['ma5']:,} | 20일MA: {price_data['ma20']:,}
RSI: {price_data['rsi']} | 추세: {price_data['trend']}
{holding_str}
주문가능 예수금: {deposit:,}원
1회 최대 매수가능 수량: {max_qty}주 (예수금·한도 반영)

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "action": "buy" or "sell" or "hold",
  "qty": 매수/매도 수량 (hold면 0),
  "reason": "판단 근거 한 줄",
  "confidence": 1~10
}}

제약조건:
- buy 수량은 반드시 {max_qty}주 이하
- buy: 현재가 x qty <= {min(MAX_ORDER_AMT, deposit):,}원
- confidence {min_confidence} 이상일 때만 buy/sell 추천
- 보유 종목 아니면 sell 불가
- 예수금 {deposit:,}원 초과 주문 불가"""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    raw   = msg.content[0].text.strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return {"action": "hold", "reason": "파싱 실패",
                "ticker": ticker, "name": name, "price": current_price}

    signal = json.loads(match.group())

    # 안전장치: 수량이 max_qty 초과하면 강제 조정
    if signal.get("action") == "buy" and signal.get("qty", 0) > max_qty:
        signal["qty"] = max_qty

    signal["ticker"] = ticker
    signal["name"]   = name        # ← 종목명 항상 포함
    signal["price"]  = current_price
    signal["market"] = market
    return signal

if __name__ == "__main__":
    from data.kis_client import get_deposit
    deposit  = get_deposit()
    watchlist = get_watchlist()

    print(f"💰 주문가능 예수금: {deposit:,}원\n")
    print("🤖 Claude 신호 분석 중...\n")

    for item in watchlist[:3]:
        signal = generate_signal(
            ticker  = item["ticker"],
            name    = item.get("name", item["ticker"]),
            market  = item.get("market", "KRX"),
            deposit = deposit,
        )
        emoji = {"buy": "🟢", "sell": "🔴", "hold": "⚪"}.get(signal["action"], "⚪")
        print(f"{emoji} {signal['name']}({signal['ticker']}): "
              f"{signal['action'].upper()} {signal.get('qty', 0)}주 | "
              f"신뢰도: {signal.get('confidence', '-')}/10 | "
              f"{signal.get('reason', '')}")