import logging
import time
from datetime import datetime, timezone, timedelta

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
        self.current_rsi_daily_short = None
        self.last_rsi_update = 0
        self.last_hourly_rsi_update = 0 # Track hourly RSI update for UI
        self.last_tick_date = None # Track execution by date (YYYY-MM-DD)

    def tick(self, current_price: float, open_order_uuids: set):
        """RSI Daily Delta Strategy Logic"""
        self.strategy._manage_orders(open_order_uuids)
        
        # Determine current time (Simulation or Real)
        # We need to ensure we are working with KST because Upbit daily close is 9 AM KST.
        KST = timezone(timedelta(hours=9))
        
        # Default to system time, assume UTC if naive, then convert to KST
        # Actually, datetime.now() returns local time. datetime.now(timezone.utc) returns UTC.
        # Let's get UTC time first to be safe, then convert to KST.
        now_utc = datetime.now(timezone.utc)
        current_dt_kst = now_utc.astimezone(KST)
        
        # Check if running in simulation
        if hasattr(self.strategy, 'current_candle') and self.strategy.current_candle:
            ts = self.strategy.current_candle.get('timestamp')
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        if ts > 10000000000: ts = ts / 1000.0
                        # Unix timestamp is always UTC
                        dt_utc = datetime.fromtimestamp(ts, timezone.utc)
                        current_dt_kst = dt_utc.astimezone(KST)
                    elif isinstance(ts, str):
                        # ISO string (usually UTC with Z)
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        current_dt_kst = dt.astimezone(KST)
                except Exception:
                    pass

        # Execute only once per day, after 9 AM KST
        if current_dt_kst.hour < 9:
            return

        current_date_str = current_dt_kst.strftime("%Y-%m-%d")
        if current_date_str == self.last_tick_date:
            return
            
        self.last_tick_date = current_date_str
        
        # Ensure we have enough history
        if self.prev_rsi is None or self.prev_prev_rsi is None:
            return

        # DEBUG LOGGING for Simulation
        logging.info(f"RSI Logic Tick [{current_date_str}]: Prev={self.prev_rsi:.2f}, PrevPrev={self.prev_prev_rsi:.2f}")

        # --- Buying Logic (Daily Delta - Confirmed Close) ---
        # Condition: Rebounding (Prev > PrevPrev) BUT still in Buy Zone (Prev < Max Buy)
        # User Request: "Max Buy RSI보다 아래인데, 어제(PrevPrev)보다 오늘(Prev)이 높은데, 아직 여전히 RSI값이 Max Buy RSI 이하인 경우"
        
        buy_cond_1 = self.prev_rsi < self.strategy.config.rsi_buy_max
        buy_cond_2 = self.prev_rsi > self.prev_prev_rsi
        
        # Calculate Delta (Yesterday - DayBefore)
        rsi_delta = self.prev_rsi - self.prev_prev_rsi
        
        # DEBUG LOGGING: Log whenever we are in Buy Zone (Prev is low)
        if self.prev_rsi < self.strategy.config.rsi_buy_max:
             logging.info(f"  [Buy Zone Debug] Date={current_date_str}, Prev={self.prev_rsi:.2f}, PrevPrev={self.prev_prev_rsi:.2f}, MaxBuy={self.strategy.config.rsi_buy_max}")
             logging.info(f"    -> Cond1(Prev<Max): {buy_cond_1}, Cond2(Prev>PrevPrev): {buy_cond_2}, Delta: {rsi_delta:.2f}")

        if buy_cond_1 and buy_cond_2:
            buy_amount_splits = 0
            
            if rsi_delta >= self.strategy.config.rsi_buy_first_threshold:
                logging.info(f"RSI Buy Signal (Daily Close): Prev RSI {self.prev_rsi:.2f} > DayBefore {self.prev_prev_rsi:.2f} (Delta +{rsi_delta:.2f})")
                buy_amount_splits = self.strategy.config.rsi_buy_first_amount
            else:
                logging.info(f"    -> Delta too small ({rsi_delta:.2f} < {self.strategy.config.rsi_buy_first_threshold})")
            
            # Execute Buy
            if buy_amount_splits > 0:
                if self.strategy.check_trade_limit():
                    # Check Max Holdings
                    current_holdings = len([s for s in self.strategy.splits if s.status != "SELL_FILLED"])
                    max_holdings = self.strategy.config.max_holdings
                    
                    if current_holdings + buy_amount_splits <= max_holdings:
                        for _ in range(buy_amount_splits):
                            self.strategy._create_buy_split(current_price, use_market_order=True)
                    else:
                        logging.warning(f"Max holdings reached ({current_holdings}). Skipping RSI buy.")

        # --- Selling Logic (Daily Delta - Confirmed Close) ---
        # Condition: DayBefore RSI (prev_prev_rsi) is in Sell Zone AND Decreased to Yesterday (prev_rsi)
        # "Min Sell RSI 위에서 천장을 찍고 내려올때"
        # Top was prev_prev. prev_prev > Min Sell RSI.
        # Turned down: prev < prev_prev.
        
        sell_cond_1 = self.prev_prev_rsi > self.strategy.config.rsi_sell_min
        sell_cond_2 = self.prev_rsi < self.prev_prev_rsi
        
        # Calculate Delta (DayBefore - Yesterday) -> Positive means drop
        rsi_drop = self.prev_prev_rsi - self.prev_rsi
        
        # DEBUG LOGGING
        if sell_cond_1:
            logging.info(f"  [Sell Check] Zone OK (PrevPrev {self.prev_prev_rsi:.2f} > {self.strategy.config.rsi_sell_min}). Inverted V: {sell_cond_2} ({self.prev_rsi:.2f} < {self.prev_prev_rsi:.2f}). Drop: {rsi_drop:.2f}")

        if sell_cond_1 and sell_cond_2:
            sell_amount_splits = 0
            
            if rsi_drop >= self.strategy.config.rsi_sell_first_threshold:
                logging.info(f"RSI Sell Signal (Daily Close): Prev RSI {self.prev_rsi:.2f} < DayBefore {self.prev_prev_rsi:.2f} (Drop -{rsi_drop:.2f})")
                # We don't set fixed amount here anymore, we calculate based on % later
                sell_amount_splits = -1 # Flag to proceed
            else:
                logging.info(f"  [Sell Check] Drop too small ({rsi_drop:.2f} < {self.strategy.config.rsi_sell_first_threshold})")

            # Execute Sell
            if sell_amount_splits != 0:
                candidates = [s for s in self.strategy.splits if s.status in ["BUY_FILLED", "PENDING_SELL"]]
                
                # Calculate profit for each and store as tuple (split, profit_rate)
                candidates_with_profit = []
                for s in candidates:
                    profit_rate = (current_price - s.actual_buy_price) / s.actual_buy_price
                    candidates_with_profit.append((s, profit_rate))

                # Filter by Min Profit
                min_profit = self.strategy.config.sell_rate 
                candidates_with_profit = [item for item in candidates_with_profit if item[1] >= min_profit]
                
                # Calculate Sell Amount based on Percentage
                # rsi_sell_first_amount is now treated as Percentage (0-100)
                sell_percent = self.strategy.config.rsi_sell_first_amount
                total_candidates = len(candidates_with_profit)
                
                if total_candidates > 0 and sell_percent > 0:
                    # Calculate count: e.g. 10 items * 50% = 5 items
                    count = int(total_candidates * (sell_percent / 100.0))
                    # Ensure at least 1 if percent > 0 (unless count becomes 0 due to very small percent?)
                    # Let's say 1 item * 50% = 0.5 -> int(0) -> 0. Should we sell 1?
                    # Usually yes, if user wants to sell, we sell at least 1.
                    if count == 0 and sell_percent > 0:
                        count = 1
                    
                    sell_amount_splits = count
                else:
                    sell_amount_splits = 0

                # Sort by Profit Descending
                candidates_with_profit.sort(key=lambda item: item[1], reverse=True)
                
                # Take top N splits
                to_sell = [item[0] for item in candidates_with_profit[:sell_amount_splits]]
                
                for split in to_sell:
                    # Recalculate profit for logging (or use stored value)
                    profit_rate = (current_price - split.actual_buy_price) / split.actual_buy_price
                    logging.info(f"RSI Sell Execution: Split {split.id} (Profit: {profit_rate*100:.2f}%)")
                    # If PENDING_SELL, cancel first
                    if split.status == "PENDING_SELL" and split.sell_order_uuid:
                        try:
                            self.strategy.exchange.cancel_order(split.sell_order_uuid)
                        except Exception as e:
                            logging.error(f"Failed to cancel existing sell for RSI exit: {e}")
                            continue
                    
                    # Place Market Sell Order (Immediate Exit)
                    try:
                        res = self.strategy.exchange.sell_market_order(self.strategy.ticker, split.buy_volume)
                        if res:
                            split.sell_order_uuid = res.get('uuid')
                            split.status = "PENDING_SELL" # Will be checked in _manage_orders
                            self.strategy.save_state()
                    except Exception as e:
                        logging.error(f"Failed to place RSI market sell: {e}")
