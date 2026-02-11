# Chart Data Flow

- Backend gets candles via `exchange.get_candles(...)`.
- Frontend chart uses normalized candle data (`open/high/low/close/time`).

## Timestamp rules
- Upbit timestamp may be milliseconds.
- Internal chart logic normalizes to seconds.
