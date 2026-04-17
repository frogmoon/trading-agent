import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

APP_KEY    = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")
ACCOUNT    = os.getenv("KIS_ACCOUNT")
ACCOUNT_SUFFIX = os.getenv("KIS_ACCOUNT_SUFFIX")
BASE_URL   = "https://openapi.koreainvestment.com:9443"

_token_cache = {"token": None, "expires": None}

def get_access_token() -> str:
    """액세스 토큰 발급 (캐싱)"""
    now = datetime.now()
    if _token_cache["token"] and _token_cache["expires"] > now:
        return _token_cache["token"]

    res = requests.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey": APP_KEY,
            "appsecret": APP_SECRET,
        }
    )
    data = res.json()
    _token_cache["token"]   = data["access_token"]
    _token_cache["expires"] = now + timedelta(hours=23)
    return _token_cache["token"]

def get_headers(tr_id: str) -> dict:
    return {
        "authorization": f"Bearer {get_access_token()}",
        "appkey":        APP_KEY,
        "appsecret":     APP_SECRET,
        "tr_id":         tr_id,
        "Content-Type":  "application/json",
    }

def get_balance() -> list:
    """잔고 조회"""
    res = requests.get(
        f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
        headers=get_headers("TTTC8434R"),
        params={
            "CANO":            ACCOUNT,
            "ACNT_PRDT_CD":    ACCOUNT_SUFFIX,
            "AFHR_FLPR_YN":    "N",
            "OFL_YN":          "N",
            "INQR_DVSN":       "02",
            "UNPR_DVSN":       "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN":       "01",
            "CTX_AREA_FK100":  "",
            "CTX_AREA_NK100":  "",
        }
    )
    data = res.json()
    holdings = []
    for item in data.get("output1", []):
        if int(item.get("hldg_qty", 0)) > 0:
            holdings.append({
                "ticker":        item["pdno"],
                "name":          item["prdt_name"],
                "qty":           int(item["hldg_qty"]),
                "avg_price":     float(item["pchs_avg_pric"]),
                "current_price": float(item["prpr"]),
                "pnl_pct":       float(item["evlu_pfls_rt"]),
                "market_value":  float(item["evlu_amt"]),
            })
    return holdings

def get_deposit() -> int:
    """주문가능 예수금 조회"""
    res = requests.get(
        f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-psbl-order",
        headers=get_headers("TTTC8908R"),
        params={
            "CANO":                  ACCOUNT,
            "ACNT_PRDT_CD":          ACCOUNT_SUFFIX,
            "PDNO":                  "005930",   # 아무 종목코드나 (형식상 필요)
            "ORD_UNPR":              "0",
            "ORD_DVSN":              "01",       # 시장가
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "OVRS_ICLD_YN":         "N",
        }
    )
    data = res.json()
    try:
        return int(data["output"]["ord_psbl_cash"])
    except:
        return 0
        
def place_order(ticker: str, qty: int, price: int = 0, order_type: str = "buy") -> dict:
    """주문 실행 (price=0이면 시장가)"""
    tr_id  = "TTTC0802U" if order_type == "buy" else "TTTC0801U"
    ord_dvsn = "01" if price == 0 else "00"  # 01=시장가, 00=지정가

    res = requests.post(
        f"{BASE_URL}/uapi/domestic-stock/v1/trading/order-cash",
        headers=get_headers(tr_id),
        json={
            "CANO":         ACCOUNT,
            "ACNT_PRDT_CD": ACCOUNT_SUFFIX,
            "PDNO":         ticker,
            "ORD_DVSN":     ord_dvsn,
            "ORD_QTY":      str(qty),
            "ORD_UNPR":     str(price),
        }
    )
    return res.json()

if __name__ == "__main__":
    print("🔑 토큰 발급 중...")
    token = get_access_token()
    print(f"✅ 토큰 발급 성공: {token[:20]}...")

    print("\n📊 실제 잔고 조회 중...")
    holdings = get_balance()
    if holdings:
        for h in holdings:
            print(f"  {h['name']}: {h['qty']}주 | 수익률 {h['pnl_pct']:+.2f}%")
    else:
        print("  보유 종목 없음 (또는 모의투자 계좌 확인 필요)")