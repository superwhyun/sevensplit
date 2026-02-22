# RSI 전략 (RSI Strategy) - 일봉 기준

이 문서는 `backend/strategies/logic_rsi.py` 파일에 구현된 *RSI 전략(RSI Strategy)*의 동작 로직을 설명합니다.

## 개요
RSI 전략은 일반적인 분할 매수(그리드)와는 완전히 다릅니다. **일봉(Daily) 기준의 RSI(상대강도지수)**를 분석하여 "과매도 구간에서 반등할 때 매수"하고 "과매수 구간에서 꺾일 때 매도"하는 추세 역행 전략입니다.

## 핵심 로직

### 1. 기준 시간 (Timeframe)
*   **메인 기준**: **일봉 (Daily Candles)**.
*   **비교 대상**: `어제 RSI(Prev RSI, 확정된 봉)` vs `오늘 실시간 RSI(Current RSI, 진행 중인 봉)`.

### 2. 판단 주기
*   실제 매매 판단은 틱(Tick) 단위 또는 30분 단위로 자주 수행합니다.
*   이유: 일봉 종가까지 기다리지 않고, 장중에 급격한 변동(Intraday moves)이 발생하여 조건이 충족되면 즉시 진입하기 위함입니다.

### 3. 매수 로직 (진입)
*   **전제 조건**: `어제 RSI` < `rsi_buy_max` (예: 30). (과매도 상태였음)
*   **발동 조건**: `실시간 RSI` >= `rsi_buy_max`. (과매도 구간을 뚫고 올라오는 순간)
*   **동작**: 설정된 수량(`rsi_buy_first_amount`)만큼 시장가로 매수합니다.

### 4. 매도 로직 (청산)
*   **전제 조건**: `어제 RSI` > `rsi_sell_min` (예: 70). (과매수 상태였음)
*   **발동 조건**: `실시간 RSI` <= `rsi_sell_min`. (과매수 구간을 뚫고 내려오는 순간)
*   **동작**: 현재 수익 중인 분할분의 일정 비율(`rsi_sell_first_amount` %)을 매도합니다. (익절 수익률 가드 적용 시)

---

## 주요 설정 항목 (Configuration)

### RSI 공통 설정
*   **`rsi_period`**: RSI 계산 기간 (기본 14일).

### 매수 설정 (Buy)
*   **`rsi_buy_max`**: 매수 대기 기준점 (Piercing Line). RSI가 이 값 아래에 있다가 위로 올라올 때 매수합니다.
*   **`rsi_buy_first_amount`**: 진입 시 매수할 수량 (분할 수).

### 매도 설정 (Sell)
*   **`rsi_sell_min`**: 매도 대기 기준점 (Piercing Line). RSI가 이 값 위에 있다가 아래로 내려올 때 매수합니다.
*   **`rsi_sell_first_amount`**: 익절 시 매도할 비율 (%).
*   **`strategy_mode`**: 이 로직을 사용하려면 반드시 `"RSI"`로 설정되어 있어야 합니다.

## 구현 상세
*   **파일**: `backend/strategies/logic_rsi.py`
*   **클래스**: `RSIStrategyLogic`
*   **의존성**: `backend/strategy.py` (일봉 RSI를 계산하여 로직 클래스에 전달해줌)
