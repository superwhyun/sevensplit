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
        """RSI Daily Delta Strategy Logic"""
        self.strategy._manage_orders(open_order_uuids)
        
        if self.current_rsi is None or self.prev_rsi is None:
            return

        # --- Buying Logic (Daily Delta) ---
        # Condition: RSI is in Buy Zone AND RSI increased by threshold compared to yesterday
        if self.current_rsi < self.strategy.config.rsi_buy_max:
            buy_amount_splits = 0
            
            # Calculate Delta (Today - Yesterday)
            rsi_delta = self.current_rsi - self.prev_rsi
            
            if rsi_delta >= self.strategy.config.rsi_buy_first_threshold:
                logging.info(f"RSI Buy Signal: RSI {self.current_rsi} (Yesterday {self.prev_rsi}, Delta +{rsi_delta:.2f} >= {self.strategy.config.rsi_buy_first_threshold})")
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

        # --- Selling Logic (Daily Delta) ---
        # Condition: RSI is in Sell Zone AND RSI decreased by threshold compared to yesterday
        if self.current_rsi > self.strategy.config.rsi_sell_min:
            sell_amount_splits = 0
            
            # Calculate Delta (Yesterday - Today) -> Positive means drop
            rsi_drop = self.prev_rsi - self.current_rsi
            
            if rsi_drop >= self.strategy.config.rsi_sell_first_threshold:
                logging.info(f"RSI Sell Signal: RSI {self.current_rsi} (Yesterday {self.prev_rsi}, Drop -{rsi_drop:.2f} >= {self.strategy.config.rsi_sell_first_threshold})")
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
