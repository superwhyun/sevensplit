# 🚀 SevenSplit Quick Start Guide

## Step 1: 의존성 설치

```bash
# Python 패키지 설치 (FastAPI, Uvicorn, PyUpbit 등)
pip install -r requirements.txt

# 또는 pip3 사용
pip3 install -r requirements.txt

# Frontend 패키지 설치
cd frontend
npm install
cd ..
```

## Step 2: 전체 시스템 실행

```bash
./run-dev.sh
```

실행 후 다음 서비스들이 시작됩니다:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🏦 Mock Exchange:     http://localhost:5001
     → Control prices, view exchange accounts

  🤖 Trading Bot API:   http://localhost:8000
     → Backend API for bot operations

  📊 Bot Dashboard:     http://localhost:5173
     → Monitor bot status, trades, portfolio
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Step 3: 봇 시작하기

1. **봇 대시보드 열기**: http://localhost:5173
2. 원하는 코인 선택 (BTC, ETH, SOL 중)
3. **"Start Bot"** 버튼 클릭
4. 봇이 자동으로 매수 주문 생성

## Step 4: 가격 제어 (Mock 모드)

1. **거래소 UI 열기**: http://localhost:5001
2. 원하는 코인 선택
3. **"Hold Price"** 버튼 클릭하여 가격 고정
4. 가격 조정 버튼으로 가격 변경:
   - **▼ 버튼**: 가격 하락 (매수 트리거)
   - **▲ 버튼**: 가격 상승 (매도 트리거)
5. **"Set Price"** 버튼으로 적용

## Step 5: 거래 확인

봇 대시보드에서 실시간으로 확인:
- **Grid Status**: 활성 매수/매도 주문
- **Portfolio**: 총 자산 및 수익률
- **Trade History**: 완료된 거래 내역

## 🎯 사용 시나리오 예시

### 시나리오 1: 매수 테스트

1. 거래소 UI에서 가격 Hold
2. 현재가보다 1% 낮게 설정
3. 봇 대시보드에서 매수 체결 확인
4. Grid Status에서 매도 주문 생성 확인

### 시나리오 2: 전체 사이클 테스트

1. 거래소 UI에서 가격을 점진적으로 낮춤 → 여러 매수 체결
2. 가격을 다시 올림 → 매도 체결 및 수익 실현
3. Trade History에서 수익 확인

### 시나리오 3: 리셋 및 재시작

1. 봇 대시보드에서 **"Reset"** 버튼
2. 모든 주문 및 상태 초기화
3. 잔액 10,000,000 KRW로 리셋
4. 다시 시작

## ⚠️ 문제 해결

### Python 모듈을 찾을 수 없음

```bash
# 어떤 Python을 사용하고 있는지 확인
which python3
python3 --version

# 의존성 재설치
pip3 install -r requirements.txt
```

### 포트가 이미 사용중

```bash
# 기존 프로세스 종료
lsof -ti:5001,8000,5173 | xargs kill -9

# 다시 실행
./run-dev.sh
```

### Frontend가 시작되지 않음

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
cd ..
./run-dev.sh
```

## 🎓 다음 단계

- [ARCHITECTURE.md](ARCHITECTURE.md) - 시스템 아키텍처 이해
- [SETUP.md](SETUP.md) - 상세 설정 및 문제 해결
- [README.md](README.md) - 전체 프로젝트 문서

## 💡 팁

1. **Live 모드**: 거래소 UI에서 Hold 해제하면 실시간 시세 사용
2. **개별 실행**: 각 서비스를 독립적으로 실행 가능
3. **핫 리로드**: 코드 변경 시 자동 재시작 (Backend, Frontend 모두)
4. **API 문서**: http://localhost:8000/docs 에서 모든 API 확인

Enjoy trading! 🎉
