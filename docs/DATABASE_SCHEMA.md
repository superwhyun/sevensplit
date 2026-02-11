# Database Schema (Current)

Core tables:
- `strategies`
- `splits`
- `trades`
- `system_events`
- candle cache tables:
  - `candles_min_5`
  - `candles_min_60`
  - `candles_days`

Notes:
- Trading DB path is controlled by `DB_PATH`.
- Candle DB path is controlled by `CANDLE_DB_PATH`.
