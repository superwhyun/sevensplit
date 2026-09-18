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

### 3. 환경 변수 설정 (선택)

업비트 API 키와 실행 모드(모의/실거래)는 **웹 대시보드의 첫 실행 마법사와 설정 화면에서 입력**합니다.
입력한 값은 서버 DB(`system_config` 테이블)에 저장되고, 키는 화면과 API 응답에 마지막 네 자리만 노출됩니다.

환경 변수는 첫 부팅의 초기값이자 DB에 값이 없을 때의 대체값으로만 쓰입니다.

| 변수 | 설명 | 기본값 |
| :--- | :--- | :--- |
| `TRADING_MODE` | 첫 부팅 시 모드 (`DEV` 모의 / `REAL` 실거래). 이후에는 웹 설정이 우선 | `DEV` |
| `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` | 첫 부팅 시 시드할 업비트 키. 웹에서 저장하면 DB 값이 우선 | 없음 |
| `DASHBOARD_PASSWORD` | 설정하면 변경 요청(POST/PUT/DELETE)과 `/settings`에 비밀번호 요구. 외부 노출 서버라면 반드시 설정 | 없음 (보호 안 함) |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` | `INFO` |
| `DB_PATH`, `CANDLE_DB_PATH` | SQLite 파일 경로 | `backend/database/*.db` |

로컬 개발용으로는 `backend/.env.dev`(모의)와 `backend/.env.real`(실거래 시드)을 그대로 써도 됩니다.

## 🚀 실행 방법 / Running

한 프로세스가 모의 투자와 실거래를 모두 처리합니다. 모드는 웹 **설정 → 실행 방식**에서 전환하며,
실행 중인 전략이 있으면 전환이 거부됩니다. 모의와 실거래의 전략·거래 기록은 같은 DB 안에서 `mode` 컬럼으로 분리됩니다.

### 처음 실행하면

1. 대시보드에 접속하면 3단계 마법사가 뜹니다: 업비트 키 입력(또는 건너뛰기) → 모의/실거래 선택 → 첫 전략(코인, 예산, 프리셋).
2. "전략 만들고 시작"을 누르면 저장과 기동이 한 번에 끝납니다.
3. 이후에는 상단 **설정**에서 키 교체, 모드 전환, 모의 잔고 변경이 가능합니다.

### 로컬 개발

```bash
npm run dev            # 백엔드(8000) + 프론트 개발 서버(5173)
./scripts/run-real.sh  # backend/.env.real 로 시드해 백엔드만 실행 (8000, 정적 프론트 포함)
```

### 🐳 Docker & Versioning

You can run specific versions of the bot using Docker Compose.

- **Run Latest Version** (Default):
  ```bash
  docker compose up -d
  ```

- **Run Specific Version**:
  ```bash
  IMAGE_TAG=1.0.0 docker compose up -d
  ```

- **Build Specific Version**:
  ```bash
  IMAGE_TAG=1.0.0 docker compose build
  ```

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

### 3. 이미지 업데이트 및 재실행

이미지를 다시 빌드했거나 설정을 변경하여 컨테이너를 재생성해야 할 경우 `--force-recreate` 옵션을 사용합니다.

```bash
docker-compose up -d --force-recreate
```

> **참고:** 컨테이너가 시작될 때 자동으로 데이터베이스 스키마를 확인하고, 필요한 경우 업데이트를 수행합니다. 따라서 기존 데이터를 유지하면서 안전하게 최신 버전으로 업그레이드할 수 있습니다.

### 4. 멀티 유저 설정

`docker-compose.yml` 파일을 수정하여 사용자별로 봇을 추가할 수 있습니다.

```yaml
  bot-user2:
    image: sevensplit-v2:latest
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

- [설치 가이드 / Setup Guide](docs/SETUP.md) - 상세 설치 및 문제 해결
- [아키텍처 / Architecture](docs/ARCHITECTURE.md) - 시스템 구조 및 구성요소

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

# 완전 사이클 테스트
python -m pytest tests/test_refactoring_baseline.py
```

## 프로젝트 구조

```
SevenSplit/
├── backend/
│   ├── exchange.py          # 거래소 API 추상화
│   ├── strategy.py          # 매매 전략 로직
│   ├── main.py             # FastAPI 서버
│   ├── requirements.txt    # Python 의존성
│   ├── .env.real           # Real 모드 설정 (사용자 생성 필요)
│   ├── tools/              # 유지보수 유틸 스크립트
│   └── tests/              # 테스트 파일
├── docs/                   # 문서
├── frontend/
│   ├── src/
│   │   └── main.jsx        # React 앱
│   ├── package.json
│   └── vite.config.js      # Vite 설정
├── scripts/
│   ├── run-real.sh         # Real 모드 실행 스크립트
│   └── docker-build.sh     # 도커 빌드 스크립트
└── README.md
```

## API 엔드포인트

설정·온보딩

- `GET /setup/status` - 키 유무, 모드, 전략 수 (첫 화면 판단용)
- `GET /settings` - 현재 설정 (키는 마스킹)
- `PUT /settings` - 업비트 키 저장(업비트에 검증 후) / 모의 잔고 변경
- `POST /settings/validate` - 키 검증만 (잔고, 만료일 반환)
- `POST /settings/mode` - `{"mode": "DEV"|"REAL"}` 모드 전환
- `DELETE /settings/keys` - 저장된 키 삭제 (모의 모드에서만)
- `GET /auth/status`, `POST /auth/check` - 대시보드 비밀번호 상태/확인
- `GET /market/tickers`, `GET /market/price?ticker=KRW-BTC` - 마켓 목록, 현재가

전략·봇

- `GET /strategies`, `POST /strategies`, `DELETE /strategies/{id}` - 전략 목록/생성/삭제 (현재 모드 기준)
- `GET /strategies/{id}/status` - 전략 상태 조회
- `POST /bot/start`, `POST /bot/stop`, `POST /bot/hard-stop` - 시작 / 매수 정지 / 전량 정지
- `POST /strategies/config` - 설정 업데이트
- `POST /bot/reset` - 전략 리셋 (주문 취소 및 DB 데이터 삭제)
- `POST /simulations/backtest` - 캔들 기반 백테스트 실행
- `POST /simulations/live/start` - 라이브 시뮬 시작 (실주문 없음)
- `POST /simulations/live/{session_id}/stop` - 라이브 시뮬 중지
- `GET /simulations/live/{session_id}` - 라이브 시뮬 상태 조회
- `GET /simulations/live` - 라이브 시뮬 세션 목록

`DASHBOARD_PASSWORD`가 설정된 서버에서는 변경 요청에 `X-Dashboard-Password` 헤더가 필요합니다.

예시 (백테스트):
```bash
curl -X POST http://localhost:8000/simulations/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "exec_interval": "minutes/5",
    "max_candles": 1500
  }'
```

## 주의사항

⚠️ **실제 거래 전 반드시 소액으로 충분히 검증하세요.**

- **실거래 모드**: 웹 설정에서 검증된 키를 저장하고 모드를 실거래로 전환하면 실제 자산이 사용됩니다. 상단 배지가 빨간색이면 실거래입니다.
