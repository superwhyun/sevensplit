# SevenSplit - Automated Grid Trading Bot

업비트에서 동작하는 자동 분할 매매 봇입니다.

> An intelligent cryptocurrency trading bot with grid trading strategy for Upbit exchange.

## 주요 기능

- **동적 분할 매수**: 설정한 비율(`buy_rate`)만큼 가격이 하락할 때마다 자동 매수
- **자동 매도**: 매수 체결 시 설정한 수익률(`sell_rate`)로 즉시 매도 주문 등록
- **자동 Split 관리**: 매도 체결 시 해당 split 자동 삭제
- **실시간 주문 추적**: 폴링 방식으로 주문 체결 상태 확인

## 설치

### 1. Python 의존성 설치

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 2. Frontend 의존성 설치

```bash
cd frontend
npm install
cd ..
```

### 3. 환경 변수 설정

`.env` 파일을 생성하고 업비트 API 키를 설정합니다:

```bash
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here
```

## 🚀 빠른 시작 / Quick Start

### 의존성 설치 / Install Dependencies

```bash
# Python 패키지 설치
pip install -r requirements.txt

# Frontend 패키지 설치
cd frontend && npm install && cd ..
```

### 실행 방법 / Running

**전체 시스템 시작 / Start All Services:**
```bash
./run-dev.sh
```

**개별 실행 / Individual Services:**
```bash
./run-exchange.sh      # 가상 거래소 서버 / Mock Exchange (Port 5001)
./run-trading-bot.sh   # 트레이딩봇 백엔드 / Trading Bot Backend (Port 8000)
./run-frontend.sh      # 봇 모니터링 UI / Bot Dashboard (Port 5173)
```

### 접속 URL / Access

- 🏦 **거래소 관리 / Exchange Control**: http://localhost:5001
- 🤖 **봇 API / Bot API**: http://localhost:8000
- 📊 **봇 대시보드 / Dashboard**: http://localhost:5173
- 📖 **API 문서 / API Docs**: http://localhost:8000/docs

## 📚 문서 / Documentation

- [설치 가이드 / Setup Guide](SETUP.md) - 상세 설치 및 문제 해결
- [아키텍처 / Architecture](ARCHITECTURE.md) - 시스템 구조 및 구성요소

## 전략 설정

### StrategyConfig 파라미터

- `investment_per_split`: 각 split당 투자 금액 (KRW)
- `min_price`: 최소 매수 가격 (이 가격 이하로는 매수하지 않음)
- `max_price`: 최대 가격 (참고용)
- `buy_rate`: 매수 간격 비율 (예: 0.01 = 1% 하락마다 매수)
- `sell_rate`: 매도 수익률 (예: 0.01 = 1% 수익률로 매도)
- `fee_rate`: 거래 수수료 (기본: 0.0005 = 0.05%)

### 사용 예시

1% 간격으로 분할 매수, 1% 수익으로 매도:

```json
{
  "investment_per_split": 100000.0,
  "min_price": 50000000.0,
  "buy_rate": 0.01,
  "sell_rate": 0.01
}
```

## 동작 방식

1. **시작**: 현재가에 첫 번째 지정가 매수 주문 등록
2. **가격 하락**:
   - 이전 매수가 대비 `buy_rate`만큼 하락 시 새로운 매수 주문 생성
   - `min_price`까지 반복
3. **매수 체결**:
   - 자동으로 `sell_rate` 수익률로 지정가 매도 주문 등록
4. **매도 체결**:
   - 해당 split 삭제
   - 수익 거래 내역 기록

## 테스트

```bash
cd backend

# 기본 전략 테스트
python test_new_strategy.py

# 완전 사이클 테스트
python test_complete_cycle.py
```

## 프로젝트 구조

```
SevenSplit/
├── backend/
│   ├── exchange.py          # 거래소 API 추상화
│   ├── strategy.py          # 매매 전략 로직
│   ├── main.py             # FastAPI 서버
│   ├── requirements.txt    # Python 의존성
│   └── tests/              # 테스트 파일
├── frontend/
│   ├── src/
│   │   └── main.jsx        # React 앱
│   ├── package.json
│   └── vite.config.js      # Vite 설정
├── run-dev.sh              # 개발 서버 통합 실행
├── run-backend.sh          # Backend만 실행
└── run-frontend.sh         # Frontend만 실행
```

## API 엔드포인트

- `GET /status?ticker=KRW-BTC` - 전략 상태 조회
- `POST /start` - 전략 시작
- `POST /stop` - 전략 중지
- `POST /config` - 설정 업데이트
- `POST /reset` - Mock 거래소 리셋 (테스트용)

## 자동 재시작

- **Backend**: uvicorn의 `--reload` 옵션으로 `.py` 파일 변경 시 자동 재시작
- **Frontend**: Vite의 HMR(Hot Module Replacement)로 즉시 반영

## 주의사항

⚠️ **실제 거래 전 반드시 Mock 모드로 충분히 테스트하세요!**

- Mock 모드: `.env` 파일 없이 실행
- Real 모드: `.env` 파일에 API 키 설정 후 실행
