import yfinance as yf
import json
from pathlib import Path

def get_portfolio_snapshot(portfolio_path="data/portfolio.json"):
    holdings = json.loads(Path(portfolio_path).read_text())
    result = []
    for h in holdings:
        try:
            ticker = yf.Ticker(h["ticker"])
            current = ticker.fast_info.last_price
            if not current:
                print(f"⚠️  {h['name']} 가격 조회 실패, 스킵")
                continue
            pnl_pct = (current - h["avg_price"]) / h["avg_price"] * 100
            result.append({
                **h,
                "current_price": round(current, 2),
                "pnl_pct":       round(pnl_pct, 2),
                "market_value":  round(current * h["qty"], 2),
            })
        except Exception as e:
            print(f"⚠️  {h['name']} 오류: {e}")
    return result

def print_snapshot(snapshot):
    print("\n📊 포트폴리오 현황")
    print("─" * 55)
    total_value = 0
    for h in snapshot:
        sign = "▲" if h["pnl_pct"] >= 0 else "▼"
        color = "\033[32m" if h["pnl_pct"] >= 0 else "\033[31m"
        reset = "\033[0m"
        print(f"{color}{sign} {h['name']:<12} {h['pnl_pct']:>+6.2f}%  "
              f"현재가: {h['current_price']:>10,.2f}  "
              f"평가액: {h['market_value']:>12,.0f}{reset}")
        total_value += h["market_value"]
    print("─" * 55)
    print(f"  총 평가금액: {total_value:>,.0f}")

if __name__ == "__main__":
    snapshot = get_portfolio_snapshot()
    print_snapshot(snapshot)