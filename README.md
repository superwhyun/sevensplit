# SevenSplit - Automated Grid Trading Bot

업비트에서 동작하는 자동 분할 매매 봇입니다.

> An intelligent cryptocurrency trading bot with grid trading strategy for Upbit exchange.

## 주요 기능

- **동적 분할 매수**: 설정한 비율(`buy_rate`)만큼 가격이 하락할 때마다 자동 매수
- **자동 매도**: 매수 체결 시 설정한 수익률(`sell_rate`)로 즉시 매도 주문 등록
- **자동 Split 관리**: 매도 체결 시 해당 split 자동 삭제
- **실시간 주문 추적**: 폴링 방식으로 주문 체결 상태 확인

## 설치 및 설정

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

### 3. 환경 변수 설정 (Real Mode)

실제 거래(Real Mode)를 위해서는 `backend` 디렉토리 안에 `.env.real` 파일을 생성하고 업비트 API 키를 설정해야 합니다.

**`backend/.env.real` 파일 생성:**

```bash
MODE=REAL
UPBIT_ACCESS_KEY=your_actual_access_key_here
UPBIT_SECRET_KEY=your_actual_secret_key_here
```

> **참고:** Mock 모드는 별도의 설정 없이 자동으로 가상 환경에서 실행됩니다.

## 🚀 실행 방법 / Running

### 1. Mock 모드 실행 (테스트용)

가상 거래소와 가상 자산을 사용하여 안전하게 전략을 테스트할 수 있습니다.

```bash
./run-mock.sh
```

- **Mock Exchange**: http://localhost:5001 (가격 조작 및 가상 계좌 확인)
- **Dashboard**: http://localhost:5173

### 2. Real 모드 실행 (실전 매매)

실제 업비트 계좌와 연동하여 매매를 수행합니다. **주의: 실제 자산이 사용됩니다.**

```bash
./run-real.sh
```

- **Dashboard**: http://localhost:5173

## 🐳 Docker 배포 (멀티 유저 / 서버 운영)

Docker를 사용하면 여러 개의 봇을 격리된 환경에서 안정적으로 운영할 수 있습니다.

### 1. 이미지 빌드

```bash
docker-compose build
```

### 2. 컨테이너 실행

```bash
# 백그라운드 실행
docker-compose up -d
```

### 3. 멀티 유저 설정

`docker-compose.yml` 파일을 수정하여 사용자별로 봇을 추가할 수 있습니다.

```yaml
  bot-user2:
    image: sevensplit-bot:latest
    ports:
      - "8002:8000"  # 다른 포트 사용
    environment:
      - UPBIT_ACCESS_KEY=사용자2_키
      - UPBIT_SECRET_KEY=사용자2_시크릿
    volumes:
      - ./data/user2.db:/app/backend/sevensplit.db
```

- **User 1 Dashboard**: http://localhost:8001
- **User 2 Dashboard**: http://localhost:8002

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
│   ├── .env.mock           # Mock 모드 설정 (기본 제공)
│   ├── .env.real           # Real 모드 설정 (사용자 생성 필요)
│   └── tests/              # 테스트 파일
├── frontend/
│   ├── src/
│   │   └── main.jsx        # React 앱
│   ├── package.json
│   └── vite.config.js      # Vite 설정
├── run-mock.sh             # Mock 모드 실행 스크립트
├── run-real.sh             # Real 모드 실행 스크립트
└── README.md
```

## API 엔드포인트

- `GET /status?ticker=KRW-BTC` - 전략 상태 조회
- `POST /start` - 전략 시작
- `POST /stop` - 전략 중지
- `POST /config` - 설정 업데이트
- `POST /reset` - 전략 리셋 (주문 취소 및 DB 데이터 삭제)

## 주의사항

⚠️ **실제 거래 전 반드시 Mock 모드로 충분히 테스트하세요!**

- **Mock 모드**: `./run-mock.sh` 실행. 가상 자산 사용.
- **Real 모드**: `backend/.env.real` 파일 설정 후 `./run-real.sh` 실행. 실제 자산 사용.
