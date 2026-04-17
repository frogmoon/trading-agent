# Trading Agent

AI 기반 주식 자동매매 시스템

## 구조
- `src/data/` — 데이터 수집 (KIS API, yfinance, 뉴스)
- `src/agents/` — Claude AI 분석 + 매매 신호
- `src/alerts/` — 텔레그램 알림
- `scheduler.py` — 자동 스케줄러

## 스케줄
| 시간 | 작업 |
|------|------|
| 07:00 | 뉴스 분석 + universe 업데이트 |
| 08:40 | watchlist 스크리닝 |
| 08:50 | 모닝 브리핑 |
| 09:30 | 매매 신호 #1 |
| 14:00 | 매매 신호 #2 |
| 15:35 | 장 마감 리뷰 |
| 22:00 | US watchlist 갱신 |
