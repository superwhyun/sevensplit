# SevenSplit Architecture

## Overview

SevenSplit은 3개의 독립적인 서버로 구성된 트레이딩 봇 시스템입니다.

```
┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│  Mock Exchange      │      │  Trading Bot        │      │  Bot Monitoring     │
│  Server             │◄─────┤  Backend            │◄─────┤  UI (Frontend)      │
│                     │      │                     │      │                     │
│  Port: 5001         │      │  Port: 8000         │      │  Port: 5173         │
│  - API Server       │      │  - Python Daemon    │      │  - React Dashboard  │
│  - Control Panel UI │      │  - Strategy Logic   │      │  - Portfolio View   │
│  - Price Control    │      │  - Trade Execution  │      │  - Trade History    │
└─────────────────────┘      └─────────────────────┘      └─────────────────────┘
```

## Components

### 1. 가상 거래소 서버 (Mock Exchange Server)
**포트**: 5001
**위치**: `backend/mock_api_server.py` + `exchange-ui/index.html`

**역할**:
- Upbit API 호환 가상 거래소 API 제공
- 거래소 관리 웹 UI 제공
- 실시간 가격 제어 (Live/Hold 모드)
- 계좌 잔액 관리
- 주문 매칭 엔진

**주요 기능**:
- `/v1/accounts` - 계좌 조회
- `/v1/ticker` - 시세 조회
- `/v1/orders` - 주문 조회/생성
- `/mock/hold` - 가격 홀드/라이브 전환
- `/mock/price` - 수동 가격 설정
- `/` - 거래소 관리 UI

**사용법**:
```bash
./run-exchange.sh
# http://localhost:5001 접속
```

### 2. 트레이딩봇 백엔드 (Trading Bot Backend)
**포트**: 8000
**위치**: `backend/main.py`

**역할**:
- SevenSplit 전략 실행
- 거래소 API 호출
- 전략 상태 관리
- 자동 매수/매도 실행

**주요 기능**:
- `/status` - 봇 상태 조회
- `/portfolio` - 전체 포트폴리오 조회
- `/start` - 봇 시작
- `/stop` - 봇 중지
- `/config` - 전략 설정 변경
- `/reset` - Mock 모드 리셋

**사용법**:
```bash
./run-trading-bot.sh
# http://localhost:8000/docs 에서 API 문서 확인
```

### 3. 봇 모니터링 UI (Bot Monitoring UI)
**포트**: 5173
**위치**: `frontend/src/`

**역할**:
- 봇 상태 실시간 모니터링
- 포트폴리오 현황 표시
- 거래 내역 조회
- 전략 설정 관리
- Mock/Real 모드 전환

**주요 화면**:
- 전체 포트폴리오 요약
- 코인별 탭 (BTC, ETH, SOL)
- 그리드 상태 표
- 거래 내역 테이블
- 설정 패널

**사용법**:
```bash
./run-frontend.sh
# http://localhost:5173 접속
```

## 실행 방법

### 전체 시스템 실행
```bash
./run-dev.sh
```

세 개의 서버가 모두 실행되고, 다음 URL에서 접근 가능합니다:
- 🏦 거래소 관리: http://localhost:5001
- 🤖 봇 API: http://localhost:8000
- 📊 봇 대시보드: http://localhost:5173

### 개별 서버 실행
```bash
# 거래소만 실행
./run-exchange.sh

# 트레이딩봇만 실행
./run-trading-bot.sh

# 프론트엔드만 실행
./run-frontend.sh
```

## 데이터 흐름

1. **거래소 → 봇**
   - 봇이 거래소 API를 호출하여 가격/잔액 조회
   - 봇이 거래소 API에 주문 생성/취소

2. **봇 → 프론트엔드**
   - 프론트엔드가 봇 API를 호출하여 상태 조회
   - 프론트엔드가 봇 API로 명령 전송 (시작/중지/설정)

3. **거래소 ← 사용자**
   - 사용자가 거래소 UI에서 가격 직접 제어
   - Live 모드: pyupbit에서 실시간 가격 가져오기
   - Hold 모드: 사용자가 설정한 가격 고정

## Mock vs Real 모드

### Mock 모드 (기본)
- 가상 거래소 서버 사용 (localhost:5001)
- 초기 자본: 10,000,000 KRW
- 실제 돈 사용 안 함
- 가격 제어 가능

### Real 모드
- 실제 Upbit API 사용
- API 키 필요
- 실제 거래 실행
- 가격 제어 불가 (실제 시장 가격)

## 파일 구조

```
SevenSplit/
├── backend/
│   ├── main.py              # 트레이딩봇 백엔드
│   ├── mock_api_server.py   # 가상 거래소 서버
│   ├── strategy.py          # SevenSplit 전략
│   ├── exchange.py          # 거래소 추상화
│   └── state_*.json         # 전략 상태 파일
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── Dashboard.jsx # 봇 모니터링 UI
│           ├── Config.jsx
│           └── SplitCard.jsx
├── exchange-ui/
│   └── index.html           # 거래소 관리 UI
├── run-dev.sh               # 전체 시스템 실행
├── run-exchange.sh          # 거래소 서버 실행
├── run-trading-bot.sh       # 트레이딩봇 실행
└── run-frontend.sh          # 프론트엔드 실행
```

## 개발 팁

### 가격 테스트
1. 거래소 UI (localhost:5001)에서 Hold 모드로 전환
2. 가격을 원하는 값으로 설정
3. 봇 대시보드 (localhost:5173)에서 매수/매도 발생 확인

### 디버깅
- 거래소 서버 로그: 터미널에서 직접 확인
- 봇 백엔드 로그: 터미널에서 직접 확인
- 프론트엔드 로그: 브라우저 개발자 도구 콘솔

### 상태 리셋
Mock 모드에서만 가능:
1. 봇 대시보드에서 "Reset" 버튼 클릭
2. 또는 API 직접 호출: `POST http://localhost:8000/reset`
