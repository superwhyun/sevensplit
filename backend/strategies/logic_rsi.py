import logging
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
        
        self.last_rsi_update = 0
        self.last_hourly_rsi_update = 0 # Track hourly RSI update for UI
        self.last_tick_date = None # Track execution by date (YYYY-MM-DD)
        self.last_failed_buy_date = None # Track failed buy attempt date to prevent spam

    def tick(self, current_price: float, open_order_uuids: set):
        """RSI Daily Delta Strategy Logic"""
        self.strategy._manage_orders(open_order_uuids)

        # Get current time from strategy (polymorphic - works for both Real and Simulation)
        current_dt_kst = self.strategy.get_current_time_kst()

        # Execute frequently (every tick/30 mins) to catch intraday moves
        # We still track date to prevent multiple buys per day if needed
        current_date_str = current_dt_kst.strftime("%Y-%m-%d")

        # Ensure we have enough history
        if self.prev_rsi is None:
            logging.debug(f"RSI Logic Skip [{current_date_str}]: Not enough RSI history (prev={self.prev_rsi})")
            return

        # DEBUG LOGGING for Simulation
        logging.info(f"RSI Logic Tick [{current_date_str}]: Prev={self.prev_rsi:.2f}, Current_Daily={self.current_rsi_daily}")

        # --- Buying Logic (Intraday Dynamic) ---
        self._process_buy_logic(current_price, current_date_str, current_dt_kst)
        
        # --- Selling Logic (Intraday Dynamic) ---
        self._process_sell_logic(current_price, current_date_str, current_dt_kst)

    def _process_buy_logic(self, current_price: float, current_date_str: str, current_dt_kst: datetime):
        """Handle RSI Buy Logic"""
        # Condition 1: Yesterday (Prev) was in Buy Zone (Oversold)
        buy_cond_1 = self.prev_rsi < self.strategy.config.rsi_buy_max
        
        # Calculate Delta (Today - Yesterday)
        # Note: current_rsi_daily is the "Projected" RSI based on current price
        if self.current_rsi_daily is None:
            logging.debug(f"RSI Logic Skip [{current_date_str}]: current_rsi_daily is None")
            return

        rsi_delta = self.current_rsi_daily - self.prev_rsi
        # Condition 2: Today (Current) has rebounded by Threshold from Yesterday
        buy_cond_2 = rsi_delta >= self.strategy.config.rsi_buy_first_threshold
        
        # DEBUG LOGGING
        if buy_cond_1:
             logging.debug(f"  [Buy Zone Check] Date={current_date_str}, Prev(Yest)={self.prev_rsi:.2f}, Curr(Today)={self.current_rsi_daily:.2f}, MaxBuy={self.strategy.config.rsi_buy_max}")
             logging.debug(f"    -> Cond1(Prev<Max): {buy_cond_1}, Cond2(Curr>Prev+{self.strategy.config.rsi_buy_first_threshold}): {buy_cond_2} (Delta: {rsi_delta:.2f})")

        if buy_cond_1 and buy_cond_2:
            logging.info(f"RSI Buy Signal (Intraday): Prev RSI {self.prev_rsi:.2f} < Max {self.strategy.config.rsi_buy_max} AND Current {self.current_rsi_daily:.2f} > Prev + {self.strategy.config.rsi_buy_first_threshold}")
            
            already_bought_today = False
            
            # Use persistent state
            if self.strategy.last_buy_date == current_date_str:
                already_bought_today = True
            
            if already_bought_today:
                logging.debug(f"  -> Skip Buy: Already bought today ({current_date_str}).")
                return
            
            # Also check if we already failed to buy today (e.g. Budget Exceeded)
            if self.last_failed_buy_date == current_date_str:
                logging.debug(f"  -> Skip Buy: Already failed to buy today ({current_date_str}).")
                return # Skip logic entirely to prevent log spam
                
            # 1. Check Buy Condition (Only if we have budget and no active splits)
            # Limit to 1 buy per day to prevent over-trading
            if self.strategy.check_trade_limit():
                # Check RSI condition again (Redundant but safe)
                if self.prev_rsi is not None and self.current_rsi_daily is not None:
                    if self.prev_rsi <= self.strategy.config.rsi_buy_max:
                        if self.current_rsi_daily >= self.prev_rsi + self.strategy.config.rsi_buy_first_threshold:
                            # Buy Signal!
                            if self.strategy.ticker == "SIM-TEST":
                                print(f"[{current_date_str} {current_dt_kst.strftime('%H:%M:%S')}] SIM BUY SIGNAL! Confirmed: Prev({self.prev_rsi:.1f}) <= Max({self.strategy.config.rsi_buy_max}) AND Today({self.current_rsi_daily:.1f}) >= Prev+Thresh")
                            result = self.strategy.buy(current_price)
                            
                            # If buy failed (e.g. Budget), mark today as failed to prevent retries
                            if not result:
                                self.last_failed_buy_date = current_date_str
                                logging.info(f"[{current_date_str}] RSI Buy Failed (likely budget). Marking {current_date_str} as failed.")
                            else:
                                # Buy Successful -> Mark persistent date
                                self.strategy.last_buy_date = current_date_str
                                self.strategy.save_state()
                            return

    def _process_sell_logic(self, current_price: float, current_date_str: str, current_dt_kst: datetime):
        """Handle RSI Sell Logic"""
        # Condition 1: Yesterday (Prev) was in Sell Zone (Overbought)
        sell_cond_1 = self.prev_rsi > self.strategy.config.rsi_sell_min
        
        # Calculate Drop (Yesterday - Today) -> Positive means drop
        rsi_drop = self.prev_rsi - self.current_rsi_daily
        # Condition 2: Today (Current) has dropped by Threshold from Yesterday
        sell_cond_2 = rsi_drop >= self.strategy.config.rsi_sell_first_threshold
        
        if sell_cond_1:
            logging.debug(f"  [Sell Check] Zone OK (Prev {self.prev_rsi:.2f} > {self.strategy.config.rsi_sell_min}). Drop: {rsi_drop:.2f} (Threshold: {self.strategy.config.rsi_sell_first_threshold})")
        else:
            logging.debug(f"  [Sell Check] Not in sell zone (Prev {self.prev_rsi:.2f} <= {self.strategy.config.rsi_sell_min})")

        # Check existing sell date
        already_sold_today = False
        if self.strategy.last_sell_date == current_date_str:
             already_sold_today = True

        if sell_cond_1 and sell_cond_2:
            if already_sold_today:
                logging.debug(f"RSI Sell Signal Ignored: Already sold today ({current_date_str})")
                return

            logging.info(f"RSI Sell Signal (Intraday): Prev RSI {self.prev_rsi:.2f} > Min {self.strategy.config.rsi_sell_min} AND Current {self.current_rsi_daily:.2f} < Prev - {self.strategy.config.rsi_sell_first_threshold}")

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
            
            sell_amount_splits = 0
            if total_candidates > 0 and sell_percent > 0:
                # Calculate count: e.g. 10 items * 50% = 5 items
                count = int(total_candidates * (sell_percent / 100.0))
                # Ensure at least 1 if percent > 0 (unless count becomes 0 due to very small percent?)
                if count == 0 and sell_percent > 0:
                    count = 1
                
                sell_amount_splits = count

            if sell_amount_splits == 0:
                return

            # Sort by Profit Descending
            candidates_with_profit.sort(key=lambda item: item[1], reverse=True)

            # Take top N splits
            to_sell = [item[0] for item in candidates_with_profit[:sell_amount_splits]]

            logging.info(f"RSI Sell Execution: Selling {len(to_sell)} splits out of {total_candidates} candidates")

            if len(to_sell) > 0:
                 # Update persistent sell date
                 self.strategy.last_sell_date = current_date_str
                 self.strategy.save_state()

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
