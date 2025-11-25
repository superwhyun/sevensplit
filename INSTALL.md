# 설치 가이드

## ⚠️ 중요: Python 환경 문제 해결

시스템에 여러 Python이 설치되어 있을 경우, FastAPI를 찾을 수 없다는 에러가 발생할 수 있습니다.

### 해결 방법 1: Conda 환경 사용 (추천)

현재 시스템에 miniconda가 설치되어 있으므로, conda 환경에 의존성을 설치하세요:

```bash
# Conda 환경 활성화 확인
which python3
# 출력: /opt/miniconda3/bin/python3 이어야 함

# 의존성 설치
pip install -r requirements.txt

# 설치 확인
python3 -c "import fastapi; print('FastAPI OK')"
```

### 해결 방법 2: 가상환경 생성 (권장)

```bash
# 1. 가상환경 생성
python3 -m venv venv

# 2. 가상환경 활성화
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 프론트엔드 의존성 설치
cd frontend && npm install && cd ..

# 5. 실행
./run-dev.sh
```

가상환경을 사용하면 `run-*.sh` 스크립트가 자동으로 venv를 활성화합니다.

## 빠른 설치 (Conda 사용자)

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 프론트엔드 설치
cd frontend && npm install && cd ..

# 3. 실행
./run-dev.sh
```

## 실행 확인

모든 서버가 정상적으로 시작되면 다음과 같이 표시됩니다:

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

## 문제 해결

### 1. "ModuleNotFoundError: No module named 'fastapi'"

**원인**: Python 의존성이 올바른 Python 환경에 설치되지 않았습니다.

**해결책**:
```bash
# 현재 사용 중인 Python 확인
which python3

# 해당 Python에 pip로 설치
python3 -m pip install -r requirements.txt

# 또는 가상환경 생성 (위 "해결 방법 2" 참고)
```

### 2. "Address already in use"

**원인**: 포트가 이미 사용 중입니다.

**해결책**:
```bash
# 기존 프로세스 종료
lsof -ti:5001,8000,5173 | xargs kill -9

# 다시 실행
./run-dev.sh
```

### 3. Frontend 실행 안 됨

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
cd ..
./run-dev.sh
```

## 개별 서비스 실행

```bash
# 거래소만
./run-exchange.sh

# 트레이딩봇만
./run-trading-bot.sh

# 프론트엔드만
./run-frontend.sh
```

## 다음 단계

- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작 가이드
- [ARCHITECTURE.md](ARCHITECTURE.md) - 시스템 아키텍처
- [README.md](README.md) - 전체 문서
