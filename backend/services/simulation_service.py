import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, Optional

from exchange import PaperExchange, UpbitExchange
from models.strategy_state import StrategyConfig
from strategy import SevenSplitStrategy

MAX_SIM_EVENTS = 200


def _parse_iso_to_ts(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


class _InMemorySimDB:
    """Minimal DB adapter used by simulation strategy to avoid real DB writes."""

    def __init__(self, strategy_id: int, name: str):
        self._strategy = SimpleNamespace(id=strategy_id, name=name)

    def get_strategy(self, strategy_id: int):
        if strategy_id != self._strategy.id:
            return None
        return self._strategy

    def get_splits(self, strategy_id: int):
        return []

    def get_trades(self, strategy_id: int, limit: int = None):
        return []

    def update_strategy_state(self, strategy_id: int, **kwargs):
        return None

    def add_split(self, strategy_id: int, ticker: str, split_data: dict):
        return None

    def update_split(self, strategy_id: int, split_id: int, **kwargs):
        return None

    def delete_split(self, strategy_id: int, split_id: int):
        return None

    def add_trade(self, strategy_id: int, ticker: str, trade_data: dict):
        return None

    def add_event(self, strategy_id: int, level: str, event_type: str, message: str):
        return None


class _ReplayPaperExchange(PaperExchange):
    def __init__(self, public_client: UpbitExchange, initial_krw: float, candle_db=None):
        super().__init__(public_client=public_client, initial_krw=initial_krw)
        self._price_map: Dict[str, float] = {}
        self._candle_db = candle_db
        self._current_sim_ts: Optional[float] = None

    def set_price(self, ticker: str, price: float):
        self._price_map[ticker] = float(price)

    def set_tick(self, ticker: str, close_price: float, high_price: Optional[float] = None, low_price: Optional[float] = None):
        close_v = float(close_price)
        self._price_map[ticker] = close_v
        hi = float(high_price) if high_price is not None else close_v
        lo = float(low_price) if low_price is not None else close_v
        if hi <= 0:
            hi = close_v
        if lo <= 0:
            lo = close_v
        if lo > hi:
            lo, hi = hi, lo
        self._tick_bounds[ticker] = {"high": hi, "low": lo}

    def get_current_price(self, ticker="KRW-BTC"):
        if ticker in self._price_map:
            return float(self._price_map[ticker])
        return super().get_current_price(ticker)

    def get_current_prices(self, tickers):
        result = {}
        for t in tickers:
            result[t] = self.get_current_price(t)
        return result

    def get_candles(self, ticker, count=200, interval="minutes/5", to=None):
        """Read from candle DB using simulation timestamp. Never calls real API."""
        if self._candle_db is not None:
            ref_ts = self._current_sim_ts or time.time()
            if to:
                try:
                    from datetime import datetime
                    ref_ts = datetime.fromisoformat(str(to).replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
            unit_secs = 86400 if interval == "days" else int(interval.split("/")[-1]) * 60
            start_ts = ref_ts - (unit_secs * count * 2)
            candles = self._candle_db.get_candles(ticker, interval, start_ts, ref_ts)
            return candles[-count:] if candles else []
        return super().get_candles(ticker, count=count, interval=interval, to=to)


class _SimulationStrategy(SevenSplitStrategy):
    """SevenSplitStrategy variant that never persists to real DB."""

    def __init__(self, exchange, strategy_id: int, ticker: str, budget: float, name: str = "Simulation"):
        super().__init__(exchange, strategy_id=strategy_id, ticker=ticker, budget=budget)
        self.db = _InMemorySimDB(strategy_id=strategy_id, name=name)
        # Runtime defaults that are normally restored from DB state
        self.is_watching = False
        self.watch_lowest_price = None
        self.pending_buy_units = 0
        self.last_buy_date = None
        self.debug_rsi = None
        self.debug_prev_rsi = None
        self.debug_rsi_short = None
        self._sim_now_utc = None
        self.sim_events = []
        self._sim_event_seq = 1

    def load_state(self):
        return False

    def save_state(self):
        return None

    def log_event(self, level: str, event_type: str, message: str):
        self.log_message(f"[{event_type}] {message}", level=level.lower())
        self.sim_events.insert(
            0,
            {
                "id": self._sim_event_seq,
                "level": level,
                "event_type": event_type,
                "message": message,
                "timestamp": self.get_now_utc().isoformat(),
            },
        )
        if len(self.sim_events) > MAX_SIM_EVENTS:
            self.sim_events = self.sim_events[:MAX_SIM_EVENTS]
        self._sim_event_seq += 1


@dataclass
class LiveSession:
    id: str
    strategy_id: int
    ticker: str
    exec_interval: str
    started_at: float
    replay_days: int = 0
    status: str = "running"
    last_candle_ts: float = 0.0
    last_tick_price: float = 0.0
    last_error: Optional[str] = None


class SimulationService:
    def __init__(self, db, candle_db, public_exchange: UpbitExchange):
        self.db = db
        self.candle_db = candle_db
        self.public_exchange = public_exchange
        self.live_sessions: Dict[str, LiveSession] = {}
        self._live_runtime: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def _build_strategy_config(self, strategy_rec) -> StrategyConfig:
        return StrategyConfig(
            investment_per_split=strategy_rec.investment_per_split,
            min_price=strategy_rec.min_price,
            max_price=strategy_rec.max_price,
            buy_rate=strategy_rec.buy_rate,
            sell_rate=strategy_rec.sell_rate,
            fee_rate=strategy_rec.fee_rate,
            tick_interval=0.0,
            rebuy_strategy=getattr(strategy_rec, "rebuy_strategy", "reset_on_clear"),
            max_trades_per_day=getattr(strategy_rec, "max_trades_per_day", 100),
            strategy_mode=getattr(strategy_rec, "strategy_mode", "PRICE"),
            rsi_period=getattr(strategy_rec, "rsi_period", 14),
            rsi_timeframe=getattr(strategy_rec, "rsi_timeframe", "minutes/60"),
            rsi_buy_max=getattr(strategy_rec, "rsi_buy_max", 30.0),
            rsi_buy_cross_threshold=getattr(strategy_rec, "rsi_buy_cross_threshold", 0.0),
            rsi_buy_first_amount=getattr(strategy_rec, "rsi_buy_first_amount", 1),
            rsi_buy_next_amount=getattr(strategy_rec, "rsi_buy_next_amount", 1),
            rsi_sell_min=getattr(strategy_rec, "rsi_sell_min", 70.0),
            rsi_sell_cross_threshold=getattr(strategy_rec, "rsi_sell_cross_threshold", 0.0),
            rsi_sell_first_amount=getattr(strategy_rec, "rsi_sell_first_amount", 1),
            rsi_sell_next_amount=getattr(strategy_rec, "rsi_sell_next_amount", 1),
            stop_loss=getattr(strategy_rec, "stop_loss", -10.0),
            max_holdings=getattr(strategy_rec, "max_holdings", 20),
            use_trailing_buy=getattr(strategy_rec, "use_trailing_buy", False),
            trailing_buy_rebound_percent=getattr(strategy_rec, "trailing_buy_rebound_percent", 0.2),
            trailing_buy_batch=getattr(strategy_rec, "trailing_buy_batch", True),
            use_adaptive_buy_control=getattr(strategy_rec, "use_adaptive_buy_control", False),
            adaptive_sell_pressure_step=getattr(strategy_rec, "adaptive_sell_pressure_step", 1.0),
            adaptive_buy_relief_step=getattr(strategy_rec, "adaptive_buy_relief_step", 1.0),
            adaptive_pressure_cap=getattr(strategy_rec, "adaptive_pressure_cap", 4.0),
            adaptive_probe_multiplier=getattr(strategy_rec, "adaptive_probe_multiplier", 0.5),
            use_fast_drop_brake=getattr(strategy_rec, "use_fast_drop_brake", True),
            fast_drop_trigger_levels=getattr(strategy_rec, "fast_drop_trigger_levels", 2),
            fast_drop_batch_cap=getattr(strategy_rec, "fast_drop_batch_cap", 1),
            fast_drop_next_gap_levels=getattr(strategy_rec, "fast_drop_next_gap_levels", 2),
            fast_drop_multiplier_cap=getattr(strategy_rec, "fast_drop_multiplier_cap", 0.75),
            price_segments=getattr(strategy_rec, "price_segments", []) or [],
        )

    def _compute_trade_metrics(self, strategy) -> dict:
        """Compute cumulative buy/sell and max concurrent invested capital."""
        cumulative_buy = 0.0
        cumulative_sell = 0.0
        events = []  # (timestamp, delta_invested)

        def _to_ts(val):
            if not val:
                return None
            try:
                if isinstance(val, str):
                    return datetime.fromisoformat(val).timestamp()
                return float(val)
            except Exception:
                return None

        for trade in strategy.trade_history:
            buy_amt = float(trade.get("buy_amount", 0.0) or 0.0)
            sell_amt = float(trade.get("sell_amount", 0.0) or 0.0)
            cumulative_buy += buy_amt
            cumulative_sell += sell_amt

            buy_ts = _to_ts(trade.get("bought_at"))
            sell_ts = _to_ts(trade.get("timestamp"))
            if buy_ts is not None and buy_amt > 0:
                events.append((buy_ts, buy_amt))
            if sell_ts is not None and buy_amt > 0:
                events.append((sell_ts, -buy_amt))

        # Include currently open filled positions in cumulative buy and peak-invested math.
        for split in strategy.splits:
            if split.status not in ("BUY_FILLED", "PENDING_SELL"):
                continue
            buy_amt = float(getattr(split, "buy_amount", 0.0) or 0.0)
            if buy_amt <= 0:
                continue
            cumulative_buy += buy_amt
            buy_ts = _to_ts(getattr(split, "bought_at", None))
            if buy_ts is not None:
                events.append((buy_ts, buy_amt))

        invested = 0.0
        peak_invested = 0.0
        for _, delta in sorted(events, key=lambda x: x[0]):
            invested += delta
            if invested > peak_invested:
                peak_invested = invested

        return {
            "cumulative_buy_amount": cumulative_buy,
            "cumulative_sell_amount": cumulative_sell,
            "max_invested_amount": peak_invested,
        }

    def _default_exec_interval(self, config: StrategyConfig) -> str:
        return "days" if config.strategy_mode == "RSI" else "minutes/5"

    def _get_strategy_record_or_raise(self, strategy_id: int):
        s = self.db.get_strategy(strategy_id)
        if not s:
            raise ValueError(f"Strategy not found: {strategy_id}")
        return s

    def _ensure_historical_candles(self, ticker: str, total_days: int):
        """Pre-fetch historical daily candles so simulation can run without hitting the real API."""
        end_ts = time.time()
        needed_start_ts = end_ts - (total_days * 86400)

        existing = self.candle_db.get_candles(ticker, "days", needed_start_ts, end_ts)
        if len(existing) >= int(total_days * 0.9):
            logging.info(f"[SIM] Candle DB already has {len(existing)} daily candles for {ticker}. Skipping pre-fetch.")
            return

        logging.info(f"[SIM] Pre-fetching {total_days} days of daily candles for {ticker} (have {len(existing)})...")
        to_ts = end_ts
        fetched_total = 0

        while to_ts > needed_start_ts:
            try:
                to_dt = datetime.fromtimestamp(to_ts, tz=timezone.utc)
                to_str = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                candles = self.public_exchange.get_candles(ticker, count=200, interval="days", to=to_str)
                if not candles:
                    break
                self.candle_db.save_candles(ticker, "days", candles)
                fetched_total += len(candles)

                oldest_ts = min(float(c.get("timestamp") or 0) for c in candles)
                # Upbit returns timestamps in milliseconds — normalize to seconds
                if oldest_ts > 10_000_000_000:
                    oldest_ts /= 1000.0
                if oldest_ts <= 0 or oldest_ts <= needed_start_ts:
                    break
                to_ts = oldest_ts - 86400  # step back one day (in seconds)
                time.sleep(0.3)  # rate limit guard
            except Exception as e:
                logging.warning(f"[SIM] Pre-fetch candles failed: {e}")
                break

        logging.info(f"[SIM] Pre-fetch complete: {fetched_total} candles saved for {ticker}.")

    def _get_market_context(self, ticker: str, ts: float):
        # Use ts - 1 (strict less than) so the current tick's candle is excluded.
        # A daily candle with timestamp=ts opens at ts and closes at ts+86400.
        # Including it in RSI would be look-ahead — the close price isn't known yet.
        # Real trading also only sees candles that have already closed.
        m5 = self.candle_db.get_candles(ticker, "minutes/5", ts - (300 * 300), ts - 1)
        days = self.candle_db.get_candles(ticker, "days", ts - (86400 * 300), ts - 1)
        return {
            "candles": {
                ticker: {
                    "minutes/5": m5[-300:],
                    "days": days[-300:],
                }
            }
        }

    def update_live_config(self, strategy_id: int, config: StrategyConfig, budget: Optional[float] = None) -> int:
        """Apply updated config to running live simulation sessions for the same strategy."""
        updated = 0
        with self._lock:
            targets = []
            for session_id, session in self.live_sessions.items():
                if session.strategy_id != strategy_id:
                    continue
                runtime = self._live_runtime.get(session_id)
                if not runtime:
                    continue
                targets.append((session, runtime))

        for session, runtime in targets:
            strategy = runtime.get("strategy")
            if not strategy:
                continue
            try:
                if budget is not None:
                    strategy.budget = float(budget)
                strategy.update_config(config)
                if hasattr(strategy, "price_logic") and hasattr(strategy.price_logic, "_last_buy_gate_code"):
                    strategy.price_logic._last_buy_gate_code = None
                runtime["force_recalc"] = True
                strategy.log_event(
                    "INFO",
                    "CONFIG_UPDATE",
                    "Live simulation config synced.",
                )
                updated += 1
            except Exception as e:
                logging.warning(f"[SIM] Failed to sync live config for session {session.id}: {e}")
        return updated

    def update_live_manual_target(self, strategy_id: int, target_price: Optional[float]) -> int:
        """Apply manual next-buy target to running live simulation sessions for the same strategy."""
        updated = 0
        with self._lock:
            targets = []
            for session_id, session in self.live_sessions.items():
                if session.strategy_id != strategy_id:
                    continue
                runtime = self._live_runtime.get(session_id)
                if not runtime:
                    continue
                targets.append((session, runtime))

        for session, runtime in targets:
            strategy = runtime.get("strategy")
            if not strategy:
                continue
            try:
                strategy.set_manual_target(target_price)
                if hasattr(strategy, "price_logic") and hasattr(strategy.price_logic, "_last_buy_gate_code"):
                    strategy.price_logic._last_buy_gate_code = None
                runtime["force_recalc"] = True
                if target_price is None:
                    strategy.log_event("INFO", "TARGET_UPDATE", "Manual target cleared (live sync).")
                else:
                    strategy.log_event("INFO", "TARGET_UPDATE", f"Manual target set (live sync): {float(target_price):.1f}")
                updated += 1
            except Exception as e:
                logging.warning(f"[SIM] Failed to sync manual target for session {session.id}: {e}")
        return updated

    def run_backtest(
        self,
        strategy_id: int,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        exec_interval: Optional[str] = None,
        max_candles: int = 2000,
        initial_krw: float = 10_000_000.0,
    ) -> dict:
        strategy_rec = self._get_strategy_record_or_raise(strategy_id)
        config = self._build_strategy_config(strategy_rec)
        exec_interval = exec_interval or self._default_exec_interval(config)

        start_ts = _parse_iso_to_ts(start_time) or 0.0
        end_ts = _parse_iso_to_ts(end_time) or time.time()

        candles = self.candle_db.get_candles(strategy_rec.ticker, exec_interval, start_ts, end_ts)
        if not candles:
            raise ValueError(f"No candles in DB for {strategy_rec.ticker} ({exec_interval})")
        if max_candles > 0 and len(candles) > max_candles:
            candles = candles[-max_candles:]

        sim_exchange = _ReplayPaperExchange(self.public_exchange, initial_krw=initial_krw)
        sim_strategy = _SimulationStrategy(
            sim_exchange,
            strategy_id=strategy_id,
            ticker=strategy_rec.ticker,
            budget=float(strategy_rec.budget),
            name=f"[SIM] {strategy_rec.name}",
        )
        sim_strategy.update_config(config)

        first_price = float(candles[0].get("trade_price") or candles[0].get("close") or 0.0)
        first_ts = float(candles[0].get("timestamp") or 0.0)
        if first_price <= 0:
            raise ValueError("Invalid first candle price")

        if first_ts > 0:
            sim_strategy._sim_now_utc = datetime.fromtimestamp(first_ts, tz=timezone.utc)
        first_high = float(candles[0].get("high_price") or candles[0].get("high") or first_price)
        first_low = float(candles[0].get("low_price") or candles[0].get("low") or first_price)
        sim_exchange.set_tick(strategy_rec.ticker, first_price, high_price=first_high, low_price=first_low)
        sim_strategy.start(current_price=first_price)

        for candle in candles:
            ts = float(candle.get("timestamp") or 0.0)
            price = float(candle.get("trade_price") or candle.get("close") or 0.0)
            high = float(candle.get("high_price") or candle.get("high") or price)
            low = float(candle.get("low_price") or candle.get("low") or price)
            if ts <= 0 or price <= 0:
                continue
            sim_strategy._sim_now_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            sim_exchange.set_tick(strategy_rec.ticker, price, high_price=high, low_price=low)
            market_context = self._get_market_context(strategy_rec.ticker, ts)
            sim_strategy.tick(current_price=price, market_context=market_context)

        sim_strategy.stop()

        realized = sum(float(t.get("net_profit", 0.0)) for t in sim_strategy.trade_history)
        return {
            "strategy_id": strategy_id,
            "ticker": strategy_rec.ticker,
            "mode": "backtest",
            "exec_interval": exec_interval,
            "start_ts": candles[0].get("timestamp"),
            "end_ts": candles[-1].get("timestamp"),
            "candles_used": len(candles),
            "trades": len(sim_strategy.trade_history),
            "realized_profit": realized,
            "final_state": sim_strategy.get_state(current_price=sim_exchange.get_current_price(strategy_rec.ticker)),
            "trade_history": sim_strategy.trade_history[:200],
            "sim_events": sim_strategy.sim_events[:MAX_SIM_EVENTS],
        }

    def start_live(
        self,
        strategy_id: int,
        exec_interval: Optional[str] = None,
        replay_days: Optional[int] = None,
        poll_seconds: float = 1.0,
        initial_krw: float = 10_000_000.0,
    ) -> dict:
        strategy_rec = self._get_strategy_record_or_raise(strategy_id)
        config = self._build_strategy_config(strategy_rec)
        exec_interval = exec_interval or self._default_exec_interval(config)

        session_id = str(uuid.uuid4())

        # Pre-populate candle DB with historical daily candles before replay starts.
        # This prevents _update_daily_rsi from falling back to the real API (→ 429).
        if replay_days and int(replay_days) > 0 and exec_interval == "days":
            rsi_lookback = 200  # daily candles needed for RSI calculation
            total_days = int(replay_days) + rsi_lookback
            self._ensure_historical_candles(strategy_rec.ticker, total_days)

        sim_exchange = _ReplayPaperExchange(
            self.public_exchange, initial_krw=initial_krw, candle_db=self.candle_db
        )
        sim_strategy = _SimulationStrategy(
            sim_exchange,
            strategy_id=strategy_id,
            ticker=strategy_rec.ticker,
            budget=float(strategy_rec.budget),
            name=f"[LIVE-SIM] {strategy_rec.name}",
        )
        sim_strategy.update_config(config)

        session = LiveSession(
            id=session_id,
            strategy_id=strategy_id,
            ticker=strategy_rec.ticker,
            exec_interval=exec_interval,
            started_at=time.time(),
            replay_days=max(0, int(replay_days or 0)),
        )

        with self._lock:
            self.live_sessions[session_id] = session
            self._live_runtime[session_id] = {
                "strategy": sim_strategy,
                "exchange": sim_exchange,
                "poll_seconds": max(1.0, float(poll_seconds)),
                "bootstrapped": False,
                "force_recalc": False,
                "last_market_context_ts": 0.0,
                "last_market_context": None,
            }

        # Optional warm-up replay: run past candles first, then continue realtime.
        if replay_days and int(replay_days) > 0:
            days = max(1, int(replay_days))
            end_ts = time.time()
            start_ts = end_ts - (days * 86400)
            candles = self.candle_db.get_candles(strategy_rec.ticker, exec_interval, start_ts, end_ts)
            if candles:
                first = candles[0]
                first_price = float(first.get("trade_price") or first.get("close") or 0.0)
                first_high = float(first.get("high_price") or first.get("high") or first_price)
                first_low = float(first.get("low_price") or first.get("low") or first_price)
                first_ts = float(first.get("timestamp") or 0.0)
                if first_price > 0:
                    if first_ts > 0:
                        sim_strategy._sim_now_utc = datetime.fromtimestamp(first_ts, tz=timezone.utc)
                    sim_exchange.set_tick(strategy_rec.ticker, first_price, high_price=first_high, low_price=first_low)
                    sim_strategy.start(current_price=first_price)

                    for candle in candles:
                        ts = float(candle.get("timestamp") or 0.0)
                        price = float(candle.get("trade_price") or candle.get("close") or 0.0)
                        high = float(candle.get("high_price") or candle.get("high") or price)
                        low = float(candle.get("low_price") or candle.get("low") or price)
                        if ts <= 0 or price <= 0:
                            continue
                        sim_strategy._sim_now_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
                        sim_exchange._current_sim_ts = ts
                        sim_exchange.set_tick(strategy_rec.ticker, price, high_price=high, low_price=low)
                        market_context = self._get_market_context(strategy_rec.ticker, ts)
                        sim_strategy.tick(current_price=price, market_context=market_context)

                    with self._lock:
                        runtime = self._live_runtime.get(session_id)
                        if runtime:
                            runtime["bootstrapped"] = True
                            runtime["last_market_context_ts"] = float(candles[-1].get("timestamp") or 0.0)
                            runtime["last_market_context"] = self._get_market_context(
                                strategy_rec.ticker,
                                runtime["last_market_context_ts"] or end_ts,
                            )
                    session.last_candle_ts = float(candles[-1].get("timestamp") or 0.0)
                    session.last_tick_price = float(candles[-1].get("trade_price") or candles[-1].get("close") or first_price)
                    sim_strategy.log_event(
                        "INFO",
                        "SIM_REPLAY",
                        f"Warm-up replay completed ({days}d, candles={len(candles)}). Continuing live simulation.",
                    )

        thread = threading.Thread(target=self._run_live_session, args=(session_id,), daemon=True)
        thread.start()
        return {
            "session_id": session_id,
            "status": "running",
            "strategy_id": strategy_id,
            "ticker": strategy_rec.ticker,
            "replay_days": int(replay_days) if replay_days else 0,
        }

    def _run_live_session(self, session_id: str):
        while True:
            with self._lock:
                session = self.live_sessions.get(session_id)
                runtime = self._live_runtime.get(session_id)
            if not session or not runtime:
                return
            if session.status != "running":
                return

            try:
                self._tick_live_session(session, runtime)
            except Exception as e:
                logging.error(f"[SIM] Live session error: {e}")
                session.last_error = str(e)

            time.sleep(runtime["poll_seconds"])

    def _tick_live_session(self, session: LiveSession, runtime: dict):
        strategy = runtime["strategy"]
        exchange = runtime["exchange"]
        ticker = session.ticker

        now = time.time()
        lookback = 86400 * 14 if session.exec_interval == "days" else 300 * 1000
        candles = self.candle_db.get_candles(ticker, session.exec_interval, now - lookback, now)
        if not candles:
            return

        latest = candles[-1]
        latest_ts = float(latest.get("timestamp") or 0.0)
        latest_close = float(latest.get("trade_price") or latest.get("close") or 0.0)
        latest_high = float(latest.get("high_price") or latest.get("high") or latest_close)
        latest_low = float(latest.get("low_price") or latest.get("low") or latest_close)
        if latest_ts <= 0 or latest_close <= 0:
            return

        # Live mode must react to realtime price, not only closed candle updates.
        # Use current market price each poll, with candle bounds as soft context.
        try:
            live_price = float(self.public_exchange.get_current_price(ticker))
        except Exception:
            live_price = latest_close
        if live_price <= 0:
            live_price = latest_close

        eff_high = max(latest_high, live_price)
        eff_low = min(latest_low, live_price)
        exchange.set_tick(ticker, live_price, high_price=eff_high, low_price=eff_low)
        strategy._sim_now_utc = datetime.fromtimestamp(now, tz=timezone.utc)
        if not runtime["bootstrapped"]:
            strategy.start(current_price=live_price)
            runtime["bootstrapped"] = True

        market_context = runtime.get("last_market_context")
        if market_context is None or runtime.get("last_market_context_ts") != latest_ts:
            market_context = self._get_market_context(ticker, latest_ts)
            runtime["last_market_context"] = market_context
            runtime["last_market_context_ts"] = latest_ts

        strategy.tick(current_price=live_price, market_context=market_context)
        runtime["force_recalc"] = False

        if latest_ts > session.last_candle_ts:
            session.last_candle_ts = latest_ts
        session.last_tick_price = live_price

    def stop_live(self, session_id: str):
        with self._lock:
            session = self.live_sessions.get(session_id)
            runtime = self._live_runtime.get(session_id)
            if not session:
                raise ValueError("Live simulation session not found")
            session.status = "stopped"
            if runtime and runtime.get("strategy"):
                try:
                    runtime["strategy"].stop()
                except Exception:
                    pass
        return {"session_id": session_id, "status": "stopped"}

    def stop_all_live_by_strategy(self, strategy_id: int):
        """Stop all active live simulation sessions for a specific strategy."""
        stopped_sessions = []
        with self._lock:
            for session_id, session in self.live_sessions.items():
                if session.strategy_id == strategy_id and session.status == "running":
                    session.status = "stopped"
                    runtime = self._live_runtime.get(session_id)
                    if runtime and runtime.get("strategy"):
                        try:
                            runtime["strategy"].stop()
                        except Exception:
                            pass
                    stopped_sessions.append(session_id)
        if stopped_sessions:
            logging.info(f"[SIM] Stopped {len(stopped_sessions)} live sessions for strategy {strategy_id}")
        return stopped_sessions

    def get_live(self, session_id: str) -> dict:
        with self._lock:
            session = self.live_sessions.get(session_id)
            runtime = self._live_runtime.get(session_id)
        if not session or not runtime:
            raise ValueError("Live simulation session not found")

        strategy = runtime["strategy"]
        exchange = runtime["exchange"]
        current_price = exchange.get_current_price(session.ticker)
        realized = sum(float(t.get("net_profit", 0.0)) for t in strategy.trade_history)
        metrics = self._compute_trade_metrics(strategy)

        return {
            "session_id": session.id,
            "status": session.status,
            "mode": "live",
            "strategy_id": session.strategy_id,
            "ticker": session.ticker,
            "exec_interval": session.exec_interval,
            "started_at": session.started_at,
            "replay_days": session.replay_days,
            "last_candle_ts": session.last_candle_ts,
            "last_tick_price": session.last_tick_price,
            "last_error": session.last_error,
            "trades": len(strategy.trade_history),
            "realized_profit": realized,
            **metrics,
            "final_state": strategy.get_state(current_price=current_price),
            "trade_history": strategy.trade_history[:200],
            "sim_events": strategy.sim_events[:MAX_SIM_EVENTS],
        }

    def list_live(self) -> list:
        with self._lock:
            sessions = list(self.live_sessions.values())
        return [
            {
                "session_id": s.id,
                "strategy_id": s.strategy_id,
                "ticker": s.ticker,
                "status": s.status,
                "exec_interval": s.exec_interval,
                "started_at": s.started_at,
                "replay_days": s.replay_days,
                "last_candle_ts": s.last_candle_ts,
                "last_tick_price": s.last_tick_price,
            }
            for s in sessions
        ]
