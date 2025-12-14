# Chart Data Flow & Processing Guide

이 문서는 프로젝트 내의 시세 데이터가 어떻게 수집, 변환, 계산, 그리고 시각화되는지 전체 흐름을 기술합니다. 특히 타임스탬프 단위(ms vs sec)와 타임존(UTC vs KST), 그리고 시뮬레이션 처리 로직에서의 주의사항을 중점으로 다룹니다.

## 1. 데이터 수집 (Data Fetching)

### 전체 흐름
사용자(Frontend) 또는 시뮬레이터가 데이터를 요청하면, 백엔드는 **Exchange Service**를 통해 데이터를 가져옵니다.

- **실전 모드 (Real Mode)**: `pyupbit` 라이브러리를 통해 Upbit API를 직접 호출.
- **모의 모드 (Mock Mode)**: 로컬 Mock 서버(`localhost:5001`)를 경유하여 Upbit API 호출 (Proxy 역할).

### 핵심 파일 및 함수
- **`backend/main.py`**
    - `simulate_strategy_from_time`: 시뮬레이션 요청 진입점. 과거 데이터(Candle)를 페이지네이션(Pagination)하여 수집하는 로직이 포함됨.
    - `fetch_logs`: 데이터 수집 배치가 올바르게 로드되었는지 확인하기 위한 디버그 로그 리스트.
- **`backend/services/exchange_service.py`**
    - `get_candles(ticker, count, interval)`: 거래소 추상화 계층.
- **`mock-exchange/main.py`** (Mock Server)
    - `/v1/candles/minutes/{unit}`: Upbit API를 프록시하며, **`to` 파라미터(Pagination 커서)**를 처리함.

### 중요: Pagination 로직
대량의 과거 데이터를 가져올 때 `to` 파라미터가 필수적입니다.
- **Upbit API**: `to` 파라미터는 `YYYY-MM-DD HH:MM:SS` 포맷의 **UTC** 또는 **KST** 문자열을 받습니다.
- **Backend**: 이전 배치의 가장 오래된 캔들 시간(`candle_date_time_utc` 또는 `kst`)을 `to`로 설정하여 다음 배치를 요청합니다.

## 2. 데이터 포맷 및 변환 (Data Standardization)

Upbit API가 반환하는 원본 데이터와 내부에서 사용하는 데이터 포맷의 차이를 이해해야 합니다.

### Upbit 원본 데이터 예시
```json
{
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-12-13T15:00:00",
    "candle_date_time_kst": "2025-12-14T00:00:00",
    "opening_price": 100000000,
    "timestamp": 1765638000000,  // 밀리초(ms) 단위! 주의!
    ...
}
```

### Backend 변환 로직 (`backend/main.py`)
시뮬레이션 루프(`simulate_strategy_from_time`)에서는 데이터를 다음과 같이 처리합니다:
1. **타임존 인식(Awareness)**:
   - `candle_date_time_kst` 문자열을 파싱한 후 `kst_tz` (UTC+9) 정보를 주입하여 timezone-aware 객체로 만듭니다.
   - 이를 통해 UTC 기준의 `start_time`과 정확한 비교가 가능해집니다.

### ⚠️ 주의사항: 타임스탬프 단위 (Milliseconds vs Seconds)
- **Upbit**: `timestamp` 필드는 **밀리초(ms)** 단위입니다. (예: `1765638000000`)
- **Python/Lightweight Charts**: 보통 **초(s)** 단위를 사용합니다. (예: `1765638000`)
- **버그 사례**: `runner.py`가 5분봉 간격(300초)을 계산할 때, 밀리초 단위 데이터를 초 단위로 변환하지 않고 계산하여 `Diff = 300,000`이 나옴. 이를 "하루(86,400초)보다 크다"고 착각하여 **일봉 모드(Daily Mode)**로 오작동한 사례가 있었음.
- **해결**: 타임스탬프 사용 시 반드시 `> 10,000,000,000` 체크를 통해 밀리초인지 확인하고 `/ 1000.0` 처리를 해야 함.

## 3. 시뮬레이션 처리 (Simulation Processing)

### 시작 인덱스 탐색 (`backend/main.py`)
사용자가 클릭한 시간(`start_time`)에 해당하는 캔들 인덱스를 찾는 과정입니다.
- 수집된 캔들 리스트는 **과거 -> 최신** 순으로 정렬됨.
- 루프를 돌며 `if candle_time >= start_time:` 조건이 만족되는 **첫 번째 인덱스**를 `start_index`로 선정.

### 시뮬레이션 실행기 (`backend/simulations/runner.py`)
`start_index`부터 루프를 돌며 매매 로직(`strategy.tick`)을 실행합니다.

#### 주요 로직 및 파일
- **`backend/simulations/runner.py`**
    - `run_simulation(config)`: 핵심 루프.
    - **Daily Mode 감지**: 캔들 간 간격을 계산하여 일봉 데이터를 사용 중인지 판단(`is_daily`).
        - **절대 주의**: 위에서 언급한 타임스탬프 단위 변환이 여기서 수행됨.
    - **Sim Logs**: 시뮬레이션 과정의 디버그 정보를 `debug_logs` 리스트에 담아 반환. (Frontend `simulationLogs`에 표시됨)

## 4. 지표 계산 (RSI Calculation)

### 파일: `backend/strategy.py`, `backend/simulations/mock.py`

#### 흐름
1. 전략(`logic_rsi.py` 등)에서 `get_rsi_15m()` 호출.
2. `ExchangeService` -> `MockExchange.get_candles(interval="minutes/15", count=100)` 호출.
3. **MockExchange Resampling (`backend/simulations/mock.py`)**:
    - 시뮬레이션은 보통 5분봉 데이터를 사용하지만, RSI 15분봉이 필요함.
    - 현재 시뮬레이션 시점(`current_candle`) 이전의 5분봉 데이터를 모아서 **Pandas Resample**을 통해 15분봉으로 합성.
    - 합성된 데이터로 RSI 계산.

#### 주의사항
- **데이터 부족(Warmup)**: 시뮬레이션 초기에는 과거 데이터가 충분치 않아(14개 미만) RSI가 `None`일 수 있음. 이 경우 매매가 스킵됨.

## 5. UI 시각화 (Frontend Integration)

### 파일: `frontend/src/components/StrategyChart.jsx`

#### 차트 라이브러리: Lightweight Charts
- **데이터 포맷**: `{ time: 1765638000, open: ..., ... }`. 여기서 `time`은 **초(Seconds)** 단위여야 함.
- **타임존**: 차트 설정에서 `timeScale: { timeVisible: true, secondsVisible: false }` 등을 설정.
- **클릭 이벤트**: `subscribeClick` 핸들러에서 반환되는 `param.time`은 차트의 X축 시간(초 단위 UTC)임.
    - 이를 백엔드로 보낼 때 그대로 보내거나 KST 변환 로직을 거침.

### 디버깅 팁 (Dashboard.jsx)
- **로그 확인**: 백엔드에서 `debug_logs` 키로 내려주는 로그 배열을 콘솔에 출력함.
- **시간 확인**: 클릭한 시간이 백엔드 `SIM START` 시간과 일치하는지 항상 확인. (타임존 +9시간 차이 주의)

## 6. 요약 레퍼런스 (Summary Reference)

| 구분 | 파일 위치 | 주요 역할 | 주의사항 |
|------|-----------|-----------|----------|
| **수집** | `backend/main.py` | 히스토리 데이터 페이징 수집 | `fetch_logs` 확인, Pagination 무한루프 주의 |
| **프록시** | `mock-exchange/main.py` | Upbit API 대행 (로컬) | `to` 파라미터 전달 확인 |
| **변환** | `backend/simulations/mock.py` | 5분봉 -> 15분봉 리샘플링 | Pandas 사용, 데이터 개수(Warmup) 체크 |
| **실행** | `backend/simulations/runner.py` | 시뮬레이션 루프 | **Timestamp Unit (ms vs s)** 체크 필수 |
| **화면** | `StrategyChart.jsx` | 차트 렌더링 & 클릭 이벤트 | X축 데이터는 초(Seconds) 단위 |

---
*이 문서는 시세 데이터 처리와 관련된 오류 발생 시 우선적으로 참고해야 합니다.*
