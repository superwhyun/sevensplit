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

        # --- Buying Logic (Daily Delta - Confirmed Close) ---
        # Condition: Yesterday's RSI (prev_rsi) is in Buy Zone AND Increased from Day Before (prev_prev_rsi)
        # AND V-Shape Check: DayBefore >= Yesterday (It was going down or flat, then turned up)
        
        if self.prev_rsi < self.strategy.config.rsi_buy_max and self.prev_prev_rsi >= self.prev_rsi:
            buy_amount_splits = 0
            
            # Calculate Delta (Yesterday - DayBefore)
            rsi_delta = self.prev_rsi - self.prev_prev_rsi # Wait, if prev_prev >= prev, delta is <= 0?
            
            # Ah, logic error in my thought.
            # V-Shape:
            # DayBefore (e.g. 30) -> Yesterday (e.g. 25) -> Today (Confirmed Close? No, Yesterday IS the confirmed close)
            
            # Let's re-read: "RSI가 Max Buy RSI 이하에서 가장 낮은 지점에서 양전하게 되면 매수"
            # This implies we are looking at:
            # DayBefore (Down) -> Yesterday (Bottom) -> Today (Up)?
            # But we only act on Confirmed Close.
            # So we need:
            # DayBeforeYesterday (e.g. 30) -> Yesterday (e.g. 25) -> Today (Confirmed Close, e.g. 28)
            # So we need 3 points: prev_prev_prev, prev_prev, prev?
            
            # Or does user mean:
            # Yesterday (Confirmed) was the turning point?
            # If Yesterday (28) > DayBefore (25), it turned up.
            # And DayBefore (25) < DayBeforeBefore (30).
            
            # Current variables:
            # prev_rsi: Yesterday's Close RSI (Confirmed)
            # prev_prev_rsi: DayBefore's Close RSI (Confirmed)
            
            # If prev > prev_prev: It went UP yesterday.
            # To be a "Bottom", prev_prev must have been lower than prev_prev_prev.
            
            # But maybe simple "Turn Up" is enough?
            # User said: "Max Buy RSI 이하에서 가장 낮은 지점에서 양전하게 되면"
            # "양전" means Positive Transition (Down -> Up).
            # So: prev_prev (Low) -> prev (High) is a turn up.
            # And prev_prev should be < Max Buy RSI.
            
            # Let's stick to:
            # 1. prev_prev < Max Buy RSI (It was in buy zone)
            # 2. prev > prev_prev (It turned up)
            # 3. Delta >= Threshold
            
            # Wait, user said "Max Buy RSI 이하에서 가장 낮은 지점에서".
            # If prev_prev was the bottom, then prev_prev < prev.
            
            # So:
            # if self.prev_prev_rsi < self.strategy.config.rsi_buy_max: (The bottom was in buy zone)
            # and self.prev_rsi > self.prev_prev_rsi: (It turned up)
            
            # Let's adjust the condition.
            pass

        if self.prev_prev_rsi < self.strategy.config.rsi_buy_max:
            buy_amount_splits = 0
            
            # Calculate Delta (Yesterday - DayBefore)
            # Yesterday (prev) should be higher than DayBefore (prev_prev)
            rsi_delta = self.prev_rsi - self.prev_prev_rsi
            
            if rsi_delta >= self.strategy.config.rsi_buy_first_threshold:
                logging.info(f"RSI Buy Signal (Daily Close): Prev RSI {self.prev_rsi:.2f} > DayBefore {self.prev_prev_rsi:.2f} (Delta +{rsi_delta:.2f})")
                buy_amount_splits = self.strategy.config.rsi_buy_first_amount
            
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
        
        if self.prev_prev_rsi > self.strategy.config.rsi_sell_min:
            sell_amount_splits = 0
            
            # Calculate Delta (DayBefore - Yesterday) -> Positive means drop
            rsi_drop = self.prev_prev_rsi - self.prev_rsi
            
            if rsi_drop >= self.strategy.config.rsi_sell_first_threshold:
                logging.info(f"RSI Sell Signal (Daily Close): Prev RSI {self.prev_rsi:.2f} < DayBefore {self.prev_prev_rsi:.2f} (Drop -{rsi_drop:.2f})")
                sell_amount_splits = self.strategy.config.rsi_sell_first_amount

            # Execute Sell
            if sell_amount_splits > 0:
                candidates = [s for s in self.strategy.splits if s.status in ["BUY_FILLED", "PENDING_SELL"]]
                
                # Calculate profit for each and store as tuple (split, profit_rate)
                candidates_with_profit = []
                for s in candidates:
                    profit_rate = (current_price - s.actual_buy_price) / s.actual_buy_price
                    candidates_with_profit.append((s, profit_rate))

                # Filter by Min Profit
                min_profit = self.strategy.config.sell_rate 
                candidates_with_profit = [item for item in candidates_with_profit if item[1] >= min_profit]
                
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
