import os
import anthropic
from dotenv import load_dotenv
from data.fetcher import get_portfolio_snapshot

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def send_long_message(text: str, header: str = ""):
    """4096자 초과 시 자동 분할 전송"""
    from alerts.telegram import send_message
    LIMIT = 4000

    if len(text) <= LIMIT:
        send_message(f"{header}\n\n{text}" if header else text)
        return

    # 헤더는 첫 메시지에만
    chunks = []
    while text:
        chunks.append(text[:LIMIT])
        text = text[LIMIT:]

    for i, chunk in enumerate(chunks):
        prefix = header if i == 0 else f"_(이어서 {i+1}/{len(chunks)})_"
        send_message(f"{prefix}\n\n{chunk}")

def analyze_portfolio(briefing_type: str = "morning") -> str:
    snapshot = get_portfolio_snapshot()

    holdings_str = "\n".join([
        f"- {h['name']}({h['ticker']}): {h['current_price']:,.0f}원 "
        f"{h['pnl_pct']:+.1f}%"
        for h in snapshot
    ])

    total_value = sum(h["market_value"] for h in snapshot)
    total_cost  = sum(h["avg_price"] * h["qty"] for h in snapshot)
    total_pnl   = (total_value - total_cost) / total_cost * 100

    if briefing_type == "morning":
        instruction = """오늘 장 시작 전 브리핑을 작성하세요.
1. 📊 포트폴리오 현황 (총평 1줄)
2. ⚠️ 오늘 주목할 리스크 (2가지)
3. ✅ 오늘 액션 아이템 (2가지)

각 항목 1~2줄로 간결하게. 전체 300자 이내."""
    else:
        instruction = """장 마감 리뷰를 작성하세요.
1. 📈 오늘 성과 (총평 1줄)
2. 🔍 눈에 띈 종목 (1~2개)
3. 🌙 내일 체크포인트 (2가지)

각 항목 1~2줄로 간결하게. 전체 300자 이내."""

    prompt = f"""포트폴리오:
{holdings_str}
총 수익률: {total_pnl:+.2f}%

{instruction}"""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

def morning_briefing():
    from alerts.telegram import send_message
    try:
        result = analyze_portfolio("morning")
        send_long_message(result, "🌅 *모닝 브리핑*")
    except Exception as e:
        send_message(f"⚠️ 모닝 브리핑 오류: {e}")

def closing_review():
    from alerts.telegram import send_message
    try:
        result = analyze_portfolio("closing")
        send_long_message(result, "🔔 *장 마감 리뷰*")
    except Exception as e:
        send_message(f"⚠️ 장 마감 리뷰 오류: {e}")

if __name__ == "__main__":
    print("🌅 모닝 브리핑 테스트")
    morning_briefing()