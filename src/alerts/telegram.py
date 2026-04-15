import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

def send_message(text: str) -> bool:
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, data=data, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"⚠️  텔레그램 전송 실패: {e}")
        return False

if __name__ == "__main__":
    ok = send_message("✅ *Trading Agent 연결 테스트*\n\n봇이 정상 작동 중입니다!")
    print("전송 성공 ✅" if ok else "전송 실패 ❌")