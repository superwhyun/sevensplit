import logging
import time
from datetime import datetime, timezone
from utils.indicators import calculate_rsi
from models.strategy_state import SplitState

class RSIStrategyLogic:
    def __init__(self, strategy):
        self.strategy = strategy
        
        # RSI Indicator State
        self.rsi_lowest = 100.0
        self.rsi_highest = 0.0
        self.prev_rsi = None
        self.current_rsi = None
        self.prev_rsi_short = None
        self.current_rsi_short = None
        self.current_rsi_daily = None
        self.current_rsi_daily_short = None
        
        self.last_rsi_update = 0
        self.last_tick_date = None
        self.last_failed_buy_date = None
        self._insufficient_funds_until = 0

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
        return self.prev_rsi is not None and self.current_rsi_daily is not None

    def _sync_rsi_runtime_context(self) -> str:
        current_date_str = self.strategy.get_current_time_kst().strftime("%Y-%m-%d")
        if self.last_tick_date != current_date_str:
            self.rsi_highest = 0.0
            self.rsi_lowest = 100.0
            self.last_tick_date = current_date_str

        if self.current_rsi_daily is not None:
            if self.current_rsi_daily > self.rsi_highest:
                self.rsi_highest = self.current_rsi_daily
            if self.current_rsi_daily < self.rsi_lowest:
                self.rsi_lowest = self.current_rsi_daily
        return current_date_str

    def _build_rsi_action_plan(self, current_price: float, current_date_str: str, market_context: dict = None):
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
        """Update daily RSI using robust ascending sorting."""
        try:
            candles = None
            if market_context and 'candles' in market_context:
                candles = market_context['candles'].get(self.strategy.ticker, {}).get("days")
            
            if not candles:
                candles = self.strategy.exchange.get_candles(self.strategy.ticker, count=200, interval="days")
            
            if not candles: return

            # --- CRITICAL FIX: Robust Chronological Sorting ---
            # Sort by timestamp (integer) to avoid TypeError in Python 3
            sorted_candles = sorted(candles, key=lambda x: x.get('timestamp') or 0)

            # Extract closes safely
            closes = []
            for c in sorted_candles:
                price = c.get('trade_price') or c.get('close') or c.get('close_price')
                if price is not None:
                    closes.append(float(price))
            
            if not closes: return

            # --- LIVE UPDATE: Inject current price ---
            if closes:
                closes[-1] = current_price
                
            # Standard RSI (14)
            rsi_now = calculate_rsi(closes, self.strategy.config.rsi_period)
            rsi_prev = calculate_rsi(closes[:-1], self.strategy.config.rsi_period)
            
            # Short RSI (4) for UI (Dashboard shows RSI(4)/D)
            rsi_short_now = calculate_rsi(closes, 4)

            # --- LOGGING ---
            if rsi_now is not None:
                logging.info(f"[Daily RSI] Updated: {rsi_now:.2f} (Prev: {rsi_prev if rsi_prev is not None else 0:.2f}), Short: {rsi_short_now if rsi_short_now is not None else 0:.2f}")
            else:
                logging.warning(f"[Daily RSI] Calculation resulted in None. Closes count: {len(closes)}")

            self.current_rsi_daily = rsi_now
            self.prev_rsi = rsi_prev
            self.current_rsi_daily_short = rsi_short_now
            
            # Internal Sync
            self.strategy.rsi_logic.current_rsi_daily = rsi_now
            self.strategy.rsi_logic.prev_rsi = rsi_prev
            self.strategy.rsi_logic.current_rsi_daily_short = rsi_short_now
            
        except Exception as e:
            logging.error(f"Failed to update Daily RSI: {e}")

    def _plan_rsi_buy(self, current_price: float, current_date_str: str, market_context: dict = None):
        if self.prev_rsi is None or self.current_rsi_daily is None:
            return
        if self.strategy.last_buy_date == current_date_str:
            return None
        if not self.strategy.has_sufficient_budget(market_context=market_context):
            return None

        rsi_delta = self.current_rsi_daily - self.prev_rsi
        if not self._validate_rsi_buy_trigger(rsi_delta):
            return None
        if not self.strategy.check_trade_limit():
            return None
        if not self._validate_rsi_buy_zone(rsi_delta):
            return None

        return {"type": "buy", "count": self.strategy.config.rsi_buy_first_amount or 1}

    def _validate_rsi_buy_trigger(self, rsi_delta: float) -> bool:
        buy_cond_1 = self.prev_rsi < self.strategy.config.rsi_buy_max
        buy_cond_2 = rsi_delta >= self.strategy.config.rsi_buy_first_threshold
        return buy_cond_1 and buy_cond_2

    def _validate_rsi_buy_zone(self, rsi_delta: float) -> bool:
        is_rebound = rsi_delta >= self.strategy.config.rsi_buy_first_threshold
        is_safe_zone = self.current_rsi_daily <= (self.strategy.config.rsi_buy_max + 5)
        return is_rebound and is_safe_zone

    def _execute_rsi_buy(self, price: float, count: int, buy_rsi: float) -> bool:
        success_count = 0
        for i in range(count):
            if time.time() < self._insufficient_funds_until: break
            current_holdings = len([s for s in self.strategy.splits if s.status != "SELL_FILLED"])
            if current_holdings >= self.strategy.config.max_holdings: break
            split = self._create_buy_order(price, buy_rsi)
            if split: success_count += 1
            else: break
        return success_count > 0

    def _create_buy_order(self, target_price: float, buy_rsi: float) -> SplitState:
        amount = self.strategy.config.investment_per_split
        total_invested = sum(s.buy_amount for s in self.strategy.splits)
        if total_invested + amount > self.strategy.budget: return None

        try:
             result = self.strategy.exchange.buy_market_order(self.strategy.ticker, amount)
             if result:
                 split = SplitState(
                     id=self.strategy.next_split_id, status="BUY_FILLED", buy_price=target_price,
                     actual_buy_price=target_price, buy_amount=amount, buy_volume=amount / target_price,
                     buy_order_uuid=result.get('uuid'), bought_at=self.strategy.get_now_utc().isoformat(),
                     created_at=self.strategy.get_now_utc().isoformat(), buy_rsi=buy_rsi
                 )
                 self.strategy.splits.append(split)
                 self.strategy.next_split_id += 1
                 self.strategy.last_buy_price = target_price
                 self.strategy.save_state()
                 return split
        except Exception as e:
             if "insufficient" in str(e).lower(): self._insufficient_funds_until = time.time() + 3600
        return None

    def _plan_rsi_sell(self, current_price: float, current_date_str: str):
        if self.current_rsi_daily is None:
            return None
        reference_peak = max(self.prev_rsi or 0, self.rsi_highest, self.current_rsi_daily or 0)
        rsi_drop = reference_peak - self.current_rsi_daily
        sell_cond_1 = reference_peak > self.strategy.config.rsi_sell_min
        sell_cond_2 = rsi_drop >= self.strategy.config.rsi_sell_first_threshold

        if not (sell_cond_1 and sell_cond_2):
            return None
        if self.strategy.last_sell_date == current_date_str:
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
            try: self.strategy.exchange.cancel_order(split.sell_order_uuid)
            except: pass
        try:
            res = self.strategy.exchange.sell_market_order(self.strategy.ticker, split.buy_volume)
            if res:
                split.sell_order_uuid = res.get('uuid')
                split.status = "PENDING_SELL"
                self.strategy.save_state()
        except: pass
