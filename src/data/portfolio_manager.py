import json
from pathlib import Path

PORTFOLIO_PATH = Path("data/portfolio.json")

def load_portfolio() -> list:
    return json.loads(PORTFOLIO_PATH.read_text())

def save_portfolio(portfolio: list):
    PORTFOLIO_PATH.write_text(json.dumps(portfolio, ensure_ascii=False, indent=2))

def add_holding(ticker: str, name: str, qty: int, avg_price: float, market: str = "KRX"):
    portfolio = load_portfolio()

    # 이미 있으면 평균단가 재계산
    for holding in portfolio:
        if holding["ticker"] == f"{ticker}.KS" or holding["ticker"] == ticker:
            existing_qty   = holding["qty"]
            existing_avg   = holding["avg_price"]
            new_qty        = existing_qty + qty
            new_avg        = ((existing_avg * existing_qty) + (avg_price * qty)) / new_qty
            holding["qty"]       = new_qty
            holding["avg_price"] = round(new_avg, 2)
            save_portfolio(portfolio)
            return f"업데이트: {name} {existing_qty}주 → {new_qty}주 (평균단가 {new_avg:,.0f}원)"

    # 없으면 새로 추가
    suffix = ".KS" if market == "KRX" else ""
    portfolio.append({
        "ticker":    f"{ticker}{suffix}",
        "name":      name,
        "market":    market,
        "qty":       qty,
        "avg_price": avg_price,
    })
    save_portfolio(portfolio)
    return f"추가: {name} {qty}주 ({avg_price:,.0f}원)"

def remove_holding(ticker: str, name: str, qty: int):
    portfolio = load_portfolio()

    for i, holding in enumerate(portfolio):
        if holding["ticker"] == f"{ticker}.KS" or holding["ticker"] == ticker:
            existing_qty = holding["qty"]

            if qty >= existing_qty:
                # 전량 매도 → 목록에서 제거
                portfolio.pop(i)
                save_portfolio(portfolio)
                return f"제거: {name} 전량 매도 ({existing_qty}주)"
            else:
                # 일부 매도 → 수량 차감
                holding["qty"] = existing_qty - qty
                save_portfolio(portfolio)
                return f"업데이트: {name} {existing_qty}주 → {holding['qty']}주"

    return f"⚠️ {name} portfolio.json에서 찾을 수 없음"