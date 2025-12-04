import logging
import time
from datetime import datetime

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

    def tick(self, current_price: float, open_order_uuids: set):
        """RSI Reversal Strategy Logic"""
        self.strategy._manage_orders(open_order_uuids)
        
        if self.current_rsi is None:
            return

        # --- Buying Logic (Accumulation) ---
        # 1. Track Local Min (Lowest RSI while in Buy Zone)
        if self.current_rsi < self.strategy.config.rsi_buy_max:
            if self.current_rsi < self.rsi_lowest:
                self.rsi_lowest = self.current_rsi
                # Reset highest when we find a new low (start of new cycle)
                self.rsi_highest = 0.0 
        else:
            # Reset Lowest if we go above Max Buy (Exited Buy Zone)
            if self.rsi_lowest < 100.0:
                 self.rsi_lowest = 100.0

        # 2. Check Buy Conditions
        if self.current_rsi < self.strategy.config.rsi_buy_max:
            buy_amount_splits = 0
            
            # A. First Buy (Rebound from Low)
            if (self.current_rsi - self.rsi_lowest) >= self.strategy.config.rsi_buy_first_threshold:
                if self.prev_rsi and (self.prev_rsi - self.rsi_lowest) < self.strategy.config.rsi_buy_first_threshold:
                    logging.info(f"RSI First Buy Signal: RSI {self.current_rsi} (Low {self.rsi_lowest} + {self.strategy.config.rsi_buy_first_threshold})")
                    buy_amount_splits = self.strategy.config.rsi_buy_first_amount

            # B. Next Buy (Trend Following)
            elif (self.current_rsi - self.rsi_lowest) >= self.strategy.config.rsi_buy_first_threshold:
                if self.prev_rsi and (self.current_rsi - self.prev_rsi) >= self.strategy.config.rsi_buy_next_threshold:
                    logging.info(f"RSI Next Buy Signal: RSI {self.current_rsi} (+{self.current_rsi - self.prev_rsi} vs Prev)")
                    buy_amount_splits = self.strategy.config.rsi_buy_next_amount

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

        # --- Selling Logic (Distribution) ---
        # 1. Track Local Max (Highest RSI while in Sell Zone)
        if self.current_rsi > self.strategy.config.rsi_sell_min:
            if self.current_rsi > self.rsi_highest:
                self.rsi_highest = self.current_rsi
                self.rsi_lowest = 100.0 # Reset lowest
        else:
            if self.rsi_highest > 0.0:
                self.rsi_highest = 0.0

        # 2. Check Sell Conditions
        if self.current_rsi > self.strategy.config.rsi_sell_min:
            sell_amount_splits = 0
            
            # A. First Sell (Drop from High)
            if (self.rsi_highest - self.current_rsi) >= self.strategy.config.rsi_sell_first_threshold:
                if self.prev_rsi and (self.rsi_highest - self.prev_rsi) < self.strategy.config.rsi_sell_first_threshold:
                    logging.info(f"RSI First Sell Signal: RSI {self.current_rsi} (High {self.rsi_highest} - {self.strategy.config.rsi_sell_first_threshold})")
                    sell_amount_splits = self.strategy.config.rsi_sell_first_amount

            # B. Next Sell (Trend Following)
            elif (self.rsi_highest - self.current_rsi) >= self.strategy.config.rsi_sell_first_threshold:
                if self.prev_rsi and (self.prev_rsi - self.current_rsi) >= self.strategy.config.rsi_sell_next_threshold:
                    logging.info(f"RSI Next Sell Signal: RSI {self.current_rsi} (-{self.prev_rsi - self.current_rsi} vs Prev)")
                    sell_amount_splits = self.strategy.config.rsi_sell_next_amount

            # Execute Sell
            if sell_amount_splits > 0:
                candidates = [s for s in self.strategy.splits if s.status in ["BUY_FILLED", "PENDING_SELL"]]
                
                # Calculate profit for each
                for s in candidates:
                    s.temp_profit_rate = (current_price - s.actual_buy_price) / s.actual_buy_price

                # Filter by Min Profit
                min_profit = self.strategy.config.sell_rate 
                candidates = [s for s in candidates if s.temp_profit_rate >= min_profit]
                
                # Sort by Profit Descending
                candidates.sort(key=lambda s: s.temp_profit_rate, reverse=True)
                
                # Take top N
                to_sell = candidates[:sell_amount_splits]
                
                for split in to_sell:
                    logging.info(f"RSI Sell Execution: Split {split.id} (Profit: {split.temp_profit_rate*100:.2f}%)")
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
