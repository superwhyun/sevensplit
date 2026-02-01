# SevenSplit 데이터베이스 스키마

## 개요
이 문서는 SevenSplit 서비스에서 사용하는 SQLite 데이터베이스의 테이블 구조와 각 컬럼에 대한 설명을 담고 있습니다.

## 테이블 목록

| 테이블명 | 설명 |
|---|---|
| [strategies](#1-strategies) | 매매 전략 설정 및 런타임 상태 정보 |
| [splits](#2-splits) | 현재 진행 중인 분할 매매(Active Splits) 상태 |
| [trades](#3-trades) | 매매가 완료된(Buy & Sell 완료) 거래 기록 |
| [system_config](#4-system_config) | 시스템 전역 설정 (모드, API 키 등) |
| [mock_accounts](#5-mock_accounts) | 모의 투자용 계좌 잔고 |
| [mock_orders](#6-mock_orders) | 모의 투자용 주문 내역 |
| [system_events](#7-system_events) | 시스템 이벤트 및 로그 |
| [candles](#8-candles) | 캔들 차트 데이터 (5분, 60분, 일봉) |

---

## 상세 스키마

### 1. strategies
각 코인별 매매 전략의 설정값과 현재 운영 상태를 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | Integer | PK |
| name | String(50) | 전략 이름 |
| ticker | String(20) | 코인 심볼 (예: KRW-BTC) |
| budget | Float | 총 운용 예산 (KRW) |
| investment_per_split | Float | 분할당 투자금액 (KRW) |
| min_price | Float | 투자를 시작할 최저 가격 (그리드 하한선) |
| max_price | Float | 투자를 멈출 최고 가격 (그리드 상한선) |
| buy_rate | Float | 추가 매수 하락률 (예: 0.005 = 0.5%) |
| sell_rate | Float | 목표 수익률 (예: 0.005 = 0.5%) |
| fee_rate | Float | 거래 수수료율 |
| tick_interval | Float | 가격 체크 주기(초) |
| rebuy_strategy | String(50) | 재매수 전략 (reset_on_clear 등) |
| max_trades_per_day | Integer | 일일 최대 거래 횟수 제한 |
| **RSI 설정** | | |
| strategy_mode | String(20) | 전략 모드 ('PRICE' 또는 'RSI') |
| rsi_period | Integer | RSI 계산 기간 (기본 14) |
| rsi_timeframe | String(20) | RSI 계산 캔들 단위 (예: minutes/60) |
| rsi_buy_max | Float | RSI 매수 상한선 (이 이하일 때 매수 고려) |
| rsi_sell_min | Float | RSI 매도 하한선 (이 이상일 때 매도 고려) |
| **리스크 관리** | | |
| stop_loss | Float | 손절매 기준율 (%) |
| max_holdings | Integer | 최대 보유 분할 개수 |
| **트레일링 바이** | | |
| use_trailing_buy | Boolean | 트레일링 바이 사용 여부 |
| trailing_buy_rebound_percent | Float | 반등 인식 비율 (%) |
| is_watching | Boolean | 현재 트레일링 감시 중인지 여부 |
| watch_lowest_price | Float | 감시 중 기록된 최저 가격 |
| **상태 정보** | | |
| is_running | Boolean | 봇 동작 여부 |
| next_split_id | Integer | 다음 생성될 Split ID |
| last_buy_price | Float | 마지막 매수 가격 |
| last_sell_price | Float | 마지막 매도 가격 |
| manual_target_price | Float | 수동으로 설정한 다음 매수 목표가 |
| price_segments | JSON | 가격대별 세그먼트 설정 (JSON 배열) |
| created_at | DateTime | 생성 시각 |
| updated_at | DateTime | 수정 시각 |

### 2. splits
현재 보유 중이거나 매수/매도 대기 중인 분할 매매 건들을 관리합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | Integer | PK |
| strategy_id | Integer | FK (strategies.id) |
| ticker | String(20) | 코인 심볼 |
| split_id | Integer | 전략 내에서의 순차 ID |
| status | String(20) | 상태 (PENDING_BUY, BUY_FILLED, PENDING_SELL) |
| buy_price | Float | 목표 또는 체결된 매수 가격 |
| target_sell_price | Float | 목표 매도 가격 |
| investment_amount | Float | 투자 금액 (KRW) |
| coin_volume | Float | 보유 코인 수량 |
| is_accumulated | Boolean | 매집(Accumulation) 여부 |
| buy_rsi | Float | 매수 시점의 RSI 값 |
| buy_order_id | String(100) | 거래소 매수 주문 UUID |
| sell_order_id | String(100) | 거래소 매도 주문 UUID |
| buy_filled_at | DateTime | 매수 체결 시각 |
| created_at | DateTime | 생성 시각 |
| updated_at | DateTime | 수정 시각 |

### 3. trades
매매가 완료된(Buy & Sell 완료) 거래 기록을 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | Integer | PK |
| strategy_id | Integer | FK (strategies.id) |
| ticker | String(20) | 코인 심볼 |
| split_id | Integer | 전략 내에서의 순차 ID |
| buy_price | Float | 평균 매수 가격 |
| sell_price | Float | 평균 매도 가격 |
| coin_volume | Float | 거래 코인 수량 |
| buy_amount | Float | 총 매수 금액 (KRW) |
| sell_amount | Float | 총 매도 금액 (KRW) |
| gross_profit | Float | 매매 차익 (수수료 제외 전) |
| total_fee | Float | 총 수수료 (매수+매도) |
| net_profit | Float | 순이익 (매매 차익 - 수수료) |
| profit_rate | Float | 수익률 (%) |
| is_accumulated | Boolean | 매집 여부 |
| buy_rsi | Float | 매수 시점 RSI |
| bought_at | DateTime | 매수 체결 시각 |
| timestamp | DateTime | 거래 완료(매도) 시각 |

### 4. system_config
시스템 전역 설정을 저장합니다. (싱글톤)

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | Integer | PK |
| mode | String(10) | 시스템 모드 ('MOCK', 'REAL') |
| upbit_access_key | String(100) | 업비트 Access Key |
| upbit_secret_key | String(100) | 업비트 Secret Key |
| updated_at | DateTime | 수정 시각 |

### 5. mock_accounts
모의 투자(Mock) 모드일 때 사용하는 가상 계좌 잔고입니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | Integer | PK |
| currency | String(20) | 화폐 단위 (KRW, BTC, ETH 등) |
| balance | Float | 잔고 수량 |
| avg_buy_price | Float | 평균 매수 단가 (평단가) |
| updated_at | DateTime | 수정 시각 |

### 6. mock_orders
모의 투자(Mock) 모드일 때 활성화된 가상 주문 목록입니다. 서버 재시작 시 복구를 위해 사용됩니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | Integer | PK |
| uuid | String(100) | 주문 UUID |
| market | String(20) | 마켓 (KRW-BTC) |
| side | String(10) | 주문 종류 (bid:매수, ask:매도) |
| ord_type | String(20) | 주문 타입 (limit, market, price) |
| price | String(50) | 주문 가격 |
| volume | String(50) | 주문 수량 |
| state | String(20) | 주문 상태 (wait, done, cancel) |
| executed_volume | String(50) | 체결된 수량 |
| created_at | DateTime | 생성 시각 |

### 7. system_events
전략 실행 중 발생하는 중요 이벤트를 기록합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | Integer | PK |
| strategy_id | Integer | FK (strategies.id) |
| level | String(20) | 로그 레벨 (INFO, WARNING, ERROR) |
| event_type | String(50) | 이벤트 타입 (WATCH_START, WATCH_END 등) |
| message | Text | 메시지 내용 |
| timestamp | DateTime | 발생 시각 |

### 8. candles
캔들 차트 데이터를 캐싱하여 저장합니다. 테이블은 `candles_min_5`, `candles_min_60`, `candles_days`로 나뉩니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| ticker | String(20) | 코인 심볼 (PK) |
| timestamp | Float | 캔들 시작 시간 (Unix Timestamp, PK) |
| open | Float | 시가 |
| high | Float | 고가 |
| low | Float | 저가 |
| close | Float | 종가 |
| volume | Float | 거래량 |
| kst_time | String(30) | KST 시간 문자열 |
| utc_time | String(30) | UTC 시간 문자열 |
