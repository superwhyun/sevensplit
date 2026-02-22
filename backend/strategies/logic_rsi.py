import logging
import time
from datetime import timedelta, timezone, datetime
from utils.indicators import calculate_rsi
from models.strategy_state import SplitState


class RSIStrategyLogic:
    def __init__(self, strategy):
        self.strategy = strategy

        # RSI indicator state used by dashboard and trade decision checks.
        self.rsi_lowest = 100.0
        self.rsi_highest = 0.0
        self.prev_rsi = None
        self.current_rsi = None
        self.prev_rsi_short = None
        self.current_rsi_short = None
        self.current_rsi_daily = None
        self.current_rsi_daily_short = None
        self.prev_prev_rsi = None

        # Signal RSI snapshot from completed daily candles (informational/high-low tracking).
        self._signal_rsi_now: float = None
        self._signal_rsi_prev: float = None
        self._last_evaluated_candle_ts: float = 0.0
        self._new_candle_available: bool = False

        self.last_rsi_update = 0
        self.last_tick_date = None
        self.last_failed_buy_date = None
        self._insufficient_funds_until = 0
        
        # Candle cache for performance
        self._cached_candles = None
        self._last_candle_fetch_time = 0
        self._candle_fetch_interval = 60 # Fetch every 60 seconds

    def tick(self, current_price: float, market_context: dict = None, indicators_updated: bool = False):
        """RSI strategy tick: data -> evaluate -> plan -> execute."""
        # 1) Data refresh
        if not indicators_updated:
            self._update_daily_rsi(current_price, market_context=market_context)

        # 2) Mode guard
        if self.strategy.config.strategy_mode != "RSI":
            return

        # 3) Data readiness guard
        if not self._has_rsi_inputs():
            return

        # 4) Runtime context sync
        current_date_str = self._sync_rsi_runtime_context()

        # 5) Condition evaluation / action planning
        action_plan = self._build_rsi_action_plan(
            current_price=current_price,
            current_date_str=current_date_str,
            market_context=market_context,
        )

        # 6) Execute planned actions
        self._execute_rsi_action_plan(action_plan, current_price, current_date_str)

    def _has_rsi_inputs(self) -> bool:
        return self.prev_prev_rsi is not None and self.prev_rsi is not None

    def _sync_rsi_runtime_context(self) -> str:
        current_date_str = self.strategy.get_current_time_kst().strftime("%Y-%m-%d")
        if self.last_tick_date != current_date_str:
            self.rsi_highest = 0.0
            self.rsi_lowest = 100.0
            self.last_tick_date = current_date_str

        # Track daily high/low from completed-candle signal RSI, not live-injected RSI.
        rsi_to_track = self._signal_rsi_now
        if rsi_to_track is not None:
            if rsi_to_track > self.rsi_highest:
                self.rsi_highest = rsi_to_track
            if rsi_to_track < self.rsi_lowest:
                self.rsi_lowest = rsi_to_track
        return current_date_str

    def _build_rsi_action_plan(self, current_price: float, current_date_str: str, market_context: dict = None):
        # Daily RSI strategy should evaluate once when a new daily candle is confirmed.
        if not self._new_candle_available:
            logging.debug(
                f"[RSI EVAL SKIP] new_candle=False last_eval_ts={self._last_evaluated_candle_ts}"
            )
            return []

        actions = []

        buy_plan = self._plan_rsi_buy(
            current_price=current_price,
            current_date_str=current_date_str,
            market_context=market_context,
        )
        if buy_plan is not None:
            actions.append(buy_plan)

        sell_plan = self._plan_rsi_sell(
            current_price=current_price,
            current_date_str=current_date_str,
        )
        if sell_plan is not None:
            actions.append(sell_plan)

        return actions

    def _execute_rsi_action_plan(self, actions: list, current_price: float, current_date_str: str):
        for action in actions:
            action_type = action.get("type")
            if action_type == "buy":
                success = self._execute_rsi_buy(
                    price=current_price,
                    count=action.get("count", 1),
                    buy_rsi=self.current_rsi_daily,
                )
                if success:
                    self.strategy.last_buy_date = current_date_str
                    self.strategy.save_state()
            elif action_type == "sell":
                self.strategy.last_sell_date = current_date_str
                self.strategy.save_state()
                for split in action.get("splits", []):
                    self._execute_market_sell(split)

    def _update_daily_rsi(self, current_price: float, market_context: dict = None):
        """Update daily RSI indicators from candle data (completed daily candles only)."""
        try:
            now = time.time()
            candles = None
            
            # 1. Fetch or use cached candles
            if market_context and "candles" in market_context:
                candles = market_context["candles"].get(self.strategy.ticker, {}).get("days")
            
            if not candles:
                # Use cache if within interval
                if self._cached_candles and (now - self._last_candle_fetch_time < self._candle_fetch_interval):
                    candles = self._cached_candles
                else:
                    logging.info(f"RSI Logic: Fetching daily candles from exchange for {self.strategy.ticker}...")
                    candles = self.strategy.exchange.get_candles(self.strategy.ticker, count=500, interval="days")
                    if candles:
                        self._cached_candles = candles
                        self._last_candle_fetch_time = now

            if not candles:
                return

            # 2. Extract closes/timestamps
            sorted_candles = sorted(candles, key=lambda x: x.get("timestamp") or 0)
            candle_points = []
            for c in sorted_candles:
                price = c.get("trade_price") or c.get("close") or c.get("close_price")
                if price is not None:
                    ts = float(c.get("timestamp") or 0.0)
                    if ts > 10000000000:  # ms -> s
                        ts /= 1000.0
                    candle_points.append((ts, float(price)))

            if not candle_points:
                return

            # Determine whether latest daily candle is still in-progress for current KST date.
            latest_ts = candle_points[-1][0]
            kst = timezone(timedelta(hours=9))
            latest_kst_date = datetime.fromtimestamp(latest_ts, tz=timezone.utc).astimezone(kst).date()
            current_kst_date = self.strategy.get_current_time_kst().date()
            has_in_progress_today = latest_kst_date == current_kst_date

            closed_points = candle_points[:-1] if has_in_progress_today else candle_points
            closed_closes = [p for _, p in closed_points]
            if not closed_closes:
                return

            latest_closed_ts = closed_points[-1][0]
            self._new_candle_available = (latest_closed_ts != self._last_evaluated_candle_ts)

            if self._new_candle_available:
                self._last_evaluated_candle_ts = latest_closed_ts
                self._signal_rsi_now = calculate_rsi(closed_closes, self.strategy.config.rsi_period)
                self._signal_rsi_prev = calculate_rsi(closed_closes[:-1], self.strategy.config.rsi_period)

            # D-1 = latest closed candle RSI, D-2 = one candle before that.
            period = self.strategy.config.rsi_period
            rsi_d1 = calculate_rsi(closed_closes, period) if len(closed_closes) >= (period + 1) else None
            rsi_d2 = calculate_rsi(closed_closes[:-1], period) if len(closed_closes) >= (period + 2) else None
            rsi_short_d1 = calculate_rsi(closed_closes, 4) if len(closed_closes) >= 5 else None

            if rsi_d1 is not None:
                logging.info(
                    f"[Daily RSI] Updated(confirmed): D-1={rsi_d1:.2f} "
                    f"(D-2: {rsi_d2 if rsi_d2 is not None else 0:.2f}), "
                    f"Short(4) D-1: {rsi_short_d1 if rsi_short_d1 is not None else 0:.2f}, "
                    f"Period: {self.strategy.config.rsi_period}, "
                    f"new_candle={self._new_candle_available}, "
                    f"has_in_progress_today={has_in_progress_today}"
                )
            else:
                logging.warning(
                    f"[Daily RSI] Confirmed RSI calculation resulted in None. "
                    f"closed_closes={len(closed_closes)}, period={period}"
                )

            # Expose confirmed RSI values only (no current-day/in-progress RSI).
            self.current_rsi_daily = rsi_d1
            self.prev_rsi = rsi_d1
            self.prev_prev_rsi = rsi_d2
            self.current_rsi_daily_short = rsi_short_d1

        except Exception as e:
            logging.error(f"RSI Logic: Failed to update Daily RSI: {e}")

    def _passes_buy_guards(self, current_date_str: str, market_context: dict = None):
        if self.strategy.last_buy_date == current_date_str:
            return False, "ALREADY_BOUGHT_TODAY"
        if not self.strategy.has_sufficient_budget(market_context=market_context):
            return False, "INSUFFICIENT_BUDGET"
        if not self.strategy.check_trade_limit():
            return False, "TRADE_LIMIT"
        return True, "OK"

    def _plan_rsi_buy(self, current_price: float, current_date_str: str, market_context: dict = None):
        if self.prev_prev_rsi is None or self.prev_rsi is None:
            return None
        
        # Only evaluate if not already bought today
        guards_ok, guard_reason = self._passes_buy_guards(current_date_str, market_context=market_context)
        if not guards_ok:
            logging.info(
                f"[RSI BUY SKIP] reason={guard_reason} date={current_date_str} "
                f"prev_prev={self.prev_prev_rsi:.2f} prev={self.prev_rsi:.2f}"
            )
            return None

        # Strict daily crossing (D-2 -> D-1) with minimum delta threshold.
        buy_max = self.strategy.config.rsi_buy_max
        buy_threshold = max(0.0, float(getattr(self.strategy.config, "rsi_buy_cross_threshold", 0.0)))
        delta_up = self.prev_rsi - self.prev_prev_rsi
        crossed_up = (self.prev_prev_rsi <= buy_max) and (self.prev_rsi >= buy_max)
        threshold_ok = delta_up >= buy_threshold
        should_buy = crossed_up and threshold_ok
        logging.info(
            f"[RSI BUY CHECK] prev_prev={self.prev_prev_rsi:.2f}, prev={self.prev_rsi:.2f}, "
            f"buy_max={buy_max:.2f}, delta_up={delta_up:.2f}, threshold={buy_threshold:.2f}, "
            f"crossed_up={crossed_up}, threshold_ok={threshold_ok}, result={should_buy}"
        )
        
        if not should_buy:
            return None

        return {"type": "buy", "count": self.strategy.config.rsi_buy_first_amount or 1}


    def _execute_rsi_buy(self, price: float, count: int, buy_rsi: float) -> bool:
        success_count = 0
        for _ in range(count):
            if time.time() < self._insufficient_funds_until:
                break
            current_holdings = len([s for s in self.strategy.splits if s.status != "SELL_FILLED"])
            if current_holdings >= self.strategy.config.max_holdings:
                break
            split = self._create_buy_order(price, buy_rsi)
            if split:
                success_count += 1
            else:
                break
        return success_count > 0

    def _create_buy_order(self, target_price: float, buy_rsi: float) -> SplitState:
        amount = self.strategy.config.investment_per_split
        total_invested = sum(s.buy_amount for s in self.strategy.splits)
        if total_invested + amount > self.strategy.budget:
            return None

        try:
            logging.info(f"RSI Logic: Attempting buy_market_order for {amount} KRW")
            result = self.strategy.exchange.buy_market_order(self.strategy.ticker, amount)
            if result:
                logging.info(f"RSI Logic: Buy order created! UUID={result.get('uuid')}")
                split = SplitState(
                    id=self.strategy.next_split_id,
                    status="PENDING_BUY",
                    buy_price=target_price,
                    buy_amount=amount,
                    buy_volume=amount / target_price,
                    buy_order_uuid=result.get("uuid"),
                    created_at=self.strategy.get_now_utc().isoformat(),
                    buy_rsi=buy_rsi,
                )
                self.strategy.splits.append(split)
                self.strategy.next_split_id += 1
                self.strategy.last_buy_price = target_price
                self.strategy.save_state()
                # Market orders are usually done immediately. Sync fill now to avoid
                # next-tick lag (which appears as 1+ candle marker delay in replay).
                try:
                    self.strategy.order_manager.check_buy_order(self.strategy, split)
                except Exception as sync_err:
                    logging.debug(f"RSI Logic: immediate buy fill sync skipped: {sync_err}")
                return split
            else:
                logging.warning("RSI Logic: Exchange buy_market_order returned no result.")
        except Exception as e:
            logging.error(f"RSI Logic: Exchange buy_market_order failed: {e}")
            if "insufficient" in str(e).lower():
                self._insufficient_funds_until = time.time() + 3600
        return None

    def _plan_rsi_sell(self, current_price: float, current_date_str: str):
        if self.prev_prev_rsi is None or self.prev_rsi is None:
            return None

        # Only evaluate if not already sold today
        if self.strategy.last_sell_date == current_date_str:
            logging.info(
                f"[RSI SELL SKIP] reason=ALREADY_SOLD_TODAY date={current_date_str} "
                f"prev_prev={self.prev_prev_rsi:.2f} prev={self.prev_rsi:.2f}"
            )
            return None

        # Strict daily crossing (D-2 -> D-1) with minimum delta threshold.
        sell_min = self.strategy.config.rsi_sell_min
        sell_threshold = max(0.0, float(getattr(self.strategy.config, "rsi_sell_cross_threshold", 0.0)))
        delta_down = self.prev_prev_rsi - self.prev_rsi
        crossed_down = (self.prev_prev_rsi >= sell_min) and (self.prev_rsi <= sell_min)
        threshold_ok = delta_down >= sell_threshold
        should_sell = crossed_down and threshold_ok
        logging.info(
            f"[RSI SELL CHECK] prev_prev={self.prev_prev_rsi:.2f}, prev={self.prev_rsi:.2f}, "
            f"sell_min={sell_min:.2f}, delta_down={delta_down:.2f}, threshold={sell_threshold:.2f}, "
            f"crossed_down={crossed_down}, threshold_ok={threshold_ok}, result={should_sell}"
        )

        if not should_sell:
            return None

        candidates_with_profit = self._select_sell_candidates(current_price)
        if not candidates_with_profit:
            return None

        sell_percent = self.strategy.config.rsi_sell_first_amount or 100
        count = max(1, int(len(candidates_with_profit) * (sell_percent / 100.0)))
        to_sell = candidates_with_profit[:count]
        return {"type": "sell", "splits": to_sell}

    def _select_sell_candidates(self, current_price: float):
        candidates = [s for s in self.strategy.splits if s.status in ["BUY_FILLED", "PENDING_SELL"]]
        candidates_with_profit = []
        for split in candidates:
            profit_rate = (current_price - split.actual_buy_price) / split.actual_buy_price
            if profit_rate >= self.strategy.config.sell_rate:
                candidates_with_profit.append(split)
        return candidates_with_profit

    def _execute_market_sell(self, split: SplitState):
        if split.status == "PENDING_SELL" and split.sell_order_uuid:
            try:
                self.strategy.exchange.cancel_order(split.sell_order_uuid)
            except Exception as e:
                logging.warning(f"RSI Logic: Failed to cancel sell order {split.sell_order_uuid}: {e}")
        try:
            res = self.strategy.exchange.sell_market_order(self.strategy.ticker, split.buy_volume)
            if res:
                split.sell_order_uuid = res.get("uuid")
                split.status = "PENDING_SELL"
                self.strategy.save_state()
                # Market sells are usually done immediately. Sync now to avoid delayed
                # sell markers/trade finalization on next tick.
                try:
                    self.strategy.order_manager.check_sell_order(self.strategy, split)
                except Exception as sync_err:
                    logging.debug(f"RSI Logic: immediate sell fill sync skipped: {sync_err}")
            else:
                logging.warning(f"RSI Logic: sell_market_order returned no result for split {split.id}")
        except Exception as e:
            logging.warning(f"RSI Logic: sell_market_order failed for split {split.id}: {e}")
