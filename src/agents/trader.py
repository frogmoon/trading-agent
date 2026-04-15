import os
import json
import time
import requests
from dotenv import load_dotenv
from data.kis_client import place_order, get_balance
from agents.strategy import generate_signal, get_watchlist, MAX_DAILY_ORDERS
from alerts.telegram import send_message
from data.portfolio_manager import add_holding, remove_holding

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

_daily_order_count = 0
_last_update_id = None  # ← 핵심: 마지막으로 읽은 메시지 ID 추적

def get_telegram_updates() -> list:
    global _last_update_id
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 3}
    if _last_update_id:
        params["offset"] = _last_update_id + 1  # 읽은 것 이후만
    try:
        res = requests.get(url, params=params)
        updates = res.json().get("result", [])
        if updates:
            _last_update_id = updates[-1]["update_id"]
        return updates
    except:
        return []

def flush_pending_updates():
    """시작 시 기존 메시지 모두 소비 (재처리 방지)"""
    global _last_update_id
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        res = requests.get(url, params={"offset": -1})
        updates = res.json().get("result", [])
        if updates:
            _last_update_id = updates[-1]["update_id"]
            print(f"  기존 메시지 {len(updates)}건 스킵 (last_id: {_last_update_id})")
    except:
        pass

def ask_approval(signal: dict) -> dict | None:
    action_kr = "📈 매수" if signal["action"] == "buy" else "📉 매도"
    msg = (
        f"🤖 *매매 신호 승인 요청*\n\n"
        f"{action_kr} | *{signal['name']}* ({signal['ticker']})\n"
        f"AI 추천수량: {signal['qty']}주 | 가격: {signal['price']:,}원\n"
        f"AI 추천금액: {signal['qty'] * signal['price']:,}원\n"
        f"신뢰도: {signal.get('confidence')}/10\n"
        f"근거: {signal.get('reason')}\n\n"
        f"✅ 승인: `/approve {signal['ticker']} [수량]`\n"
        f"  예) `/approve {signal['ticker']} {signal['qty']}` (AI 추천)\n"
        f"  예) `/approve {signal['ticker']} 3` (직접 지정)\n"
        f"❌ 거부: `/reject {signal['ticker']}`"
    )
    send_message(msg)

    for _ in range(12):  # 60초 대기
        time.sleep(5)
        updates = get_telegram_updates()
        for update in updates:
            text = update.get("message", {}).get("text", "").strip()

            if text.startswith(f"/approve {signal['ticker']}"):
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        qty = int(parts[2])
                        if qty <= 0:
                            send_message("⚠️ 수량은 1 이상이어야 합니다.")
                            continue
                        max_qty = 1_000_000 // signal["price"]
                        if qty > max_qty:
                            send_message(f"⚠️ 100만원 한도 초과. 최대 {max_qty}주 가능.")
                            continue
                        signal["qty"] = qty
                        return signal
                    except ValueError:
                        send_message("⚠️ 수량 형식 오류. 예) `/approve 096770 5`")
                        continue
                else:
                    return signal  # AI 추천 수량 사용

            if f"/reject {signal['ticker']}" in text:
                send_message(f"❌ {signal['name']} 거부됨")
                return None

    send_message(f"⏱ {signal['name']} 승인 시간 초과 → 자동 취소")
    return None

def run_trading_cycle():
    global _daily_order_count
    if _daily_order_count >= MAX_DAILY_ORDERS:
        print(f"⚠️ 일일 최대 거래 횟수 ({MAX_DAILY_ORDERS}회) 도달")
        return

    holdings = {h["ticker"]: h for h in get_balance()}
    watchlist = get_watchlist()
    all_tickers = list(holdings.values()) + [
        w for w in watchlist if w["ticker"] not in holdings
    ]

    signals = []
    for item in all_tickers:
        ticker  = item["ticker"]
        name    = item.get("name", ticker)
        holding = holdings.get(ticker)
        signal  = generate_signal(ticker, name, holding)
        if signal["action"] != "hold":
            signals.append(signal)
        print(f"  {name}: {signal['action']} (신뢰도 {signal.get('confidence', '-')})")

    if not signals:
        send_message("🔍 분석 완료 — 매매 신호 없음")
        return

    for signal in signals:
        approved_signal = ask_approval(signal)
        if not approved_signal:
            continue
        result = place_order(
            ticker     = approved_signal["ticker"],
            qty        = approved_signal["qty"],
            order_type = approved_signal["action"],
        )
        _daily_order_count += 1
        if result.get("rt_cd") == "0":
            if approved_signal["action"] == "buy":
                update_msg = add_holding(
                    ticker    = approved_signal["ticker"],
                    name      = approved_signal["name"],
                    qty       = approved_signal["qty"],
                    avg_price = approved_signal["price"],
                )
            else:  # sell
                update_msg = remove_holding(
                    ticker = approved_signal["ticker"],
                    name   = approved_signal["name"],
                    qty    = approved_signal["qty"],
                )
            send_message(
                f"✅ 주문 완료: {approved_signal['name']} "
                f"{'매수' if approved_signal['action'] == 'buy' else '매도'} "
                f"{approved_signal['qty']}주\n"
                f"📝 {update_msg}"
            )
        else:
            send_message(f"❌ 주문 실패: {result.get('msg1', '알 수 없는 오류')}")

if __name__ == "__main__":
    print("🚀 트레이딩 사이클 실행")
    print("  기존 텔레그램 메시지 정리 중...")
    flush_pending_updates()  # ← 시작 시 반드시 호출
    run_trading_cycle()