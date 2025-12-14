import logging
import time

class PriceStrategyLogic:
    def __init__(self, strategy):
        self.strategy = strategy
        
        # Trailing Buy State (Moved from Strategy or newly initialized)
        self.is_watching = False
        self.watch_lowest_price = None

    def tick(self, current_price: float, open_order_uuids: set):
        """Original Price Grid Strategy Logic"""
        self.strategy._manage_orders(open_order_uuids)

        # Check if we need to create new buy split based on price drop
        if self.strategy.check_trade_limit():
            self._check_create_new_buy_split(current_price)

    def _check_create_new_buy_split(self, current_price: float):
        """Check if we should create a new buy split based on price drop and rebuy strategy."""
        
        # Check if all positions are cleared
        has_active_positions = any(
            s.status in ["PENDING_BUY", "BUY_FILLED", "PENDING_SELL"]
            for s in self.strategy.splits
        )

        if not has_active_positions:
            # Try to handle empty state logic
            if self._handle_empty_positions(current_price):
                return

        # Standard logic for ongoing positions or "last_buy_price" strategy
        self._handle_active_positions(current_price)

    def _handle_empty_positions(self, current_price: float) -> bool:
        """Handle logic when no active positions exist. Returns True if action taken."""
        if self.strategy.config.rebuy_strategy == "reset_on_clear":
            # Strategy 1: Reset and start at current price
            logging.info(f"All positions cleared. Resetting and starting at current price: {current_price}")
            self.strategy.last_buy_price = None
            self.strategy._create_buy_split(current_price, use_market_order=True)
            return True
            
        elif self.strategy.config.rebuy_strategy == "last_sell_price":
            # Strategy 2: Use last sell price as reference
            reference_price = self.strategy.last_sell_price if self.strategy.last_sell_price is not None else current_price
            
            if self.strategy.last_sell_price is not None:
                logging.info(f"All positions cleared. Using last sell price {reference_price} as reference")
            else:
                logging.info(f"No last sell price, using current price: {current_price}")

            next_buy_price = reference_price * (1 - self.strategy.config.buy_rate)
            if current_price <= next_buy_price:
                # Buy at current price
                logging.info(f"Price dropped to {current_price} (trigger: {next_buy_price}), creating buy split at current price")
                self.strategy._create_buy_split(current_price, use_market_order=True)
            return True
        
        return False

    def _handle_active_positions(self, current_price: float):
        if self.strategy.last_buy_price is None:
            # No previous buy, create one at current price
            logging.info(f"No previous buy, creating first split at current price: {current_price}")
            rsi_15m = self.strategy.get_rsi_15m()
            self.strategy._create_buy_split(current_price, buy_rsi=rsi_15m)
            return

        # Config
        next_buy_level = self.strategy.last_buy_price * (1 - self.strategy.config.buy_rate)
        is_trailing_active = self.strategy.config.use_trailing_buy
        REBOUND_THRESHOLD = self.strategy.config.trailing_buy_rebound_percent / 100.0

        # --- A. Watching Mode (Already waiting) ---
        if self.is_watching:
            # 1. Update Lowest Price
            if self.watch_lowest_price is None or current_price < self.watch_lowest_price:
                self.watch_lowest_price = current_price
                # self.strategy.log_message(f"Trailing Buy [UPDATE]: New lowest price {self.watch_lowest_price}", level="debug")
                self.strategy.save_state() # Save lowest price if possible (needs schema update but memory works for now)

            # 2. Check Exit Conditions (BOTH must be true)
            # Cond 1: Price Rebound
            rebound_target = self.watch_lowest_price * (1 + REBOUND_THRESHOLD)
            is_rebound_ok = current_price >= rebound_target
            
            # Cond 2: RSI Strength (Lazy Check)
            # Only fetch RSI if rebound condition is met to save API calls
            is_rsi_ok = False
            rsi_5m = None
            
            if is_rebound_ok:
                rsi_5m = self.strategy.get_rsi_5m()
                is_rsi_ok = (rsi_5m is not None and rsi_5m > 30.0)

            if is_rebound_ok and is_rsi_ok:
                # Trigger Buy!
                levels_crossed = self._calculate_levels_crossed(self.strategy.last_buy_price, current_price)
                if levels_crossed > 0:
                     self.strategy.log_message(f"Trailing Buy [TRIGGER]: Rebound({current_price}>={rebound_target:.1f}) AND RSI({rsi_5m:.1f})>30. Executing {levels_crossed} buys.")
                     rsi_15m = self.strategy.get_rsi_15m()
                     self._execute_batch_buy(current_price, levels_crossed, buy_rsi=rsi_15m, is_accumulated=(levels_crossed > 1))
                else:
                     logging.info(f"Trailing Buy [RESET]: Rebound met but price {current_price} is above target {next_buy_level}. No buy needed.")
                
                # Reset Watch Mode
                self.is_watching = False
                self.watch_lowest_price = None
                self.strategy.save_state()
            else:
                # Waiting
                if is_rebound_ok and not is_rsi_ok:
                     logging.debug(f"Trailing Buy [WAIT]: Rebound OK({current_price}) but RSI({rsi_5m:.1f}) <= 30.")
                elif not is_rebound_ok:
                     # Log the Hold reason
                     self.strategy.log_message(f"Trailing Buy [HOLD]: Current {current_price} < Target {rebound_target:.1f}. Waiting for rebound.", level="debug")

            # Safety: If user turned off Trailing Buy mid-watch
            if not is_trailing_active:
                 logging.info("Trailing Buy disabled mid-watch. Exiting watch mode.")
                 self.is_watching = False
                 self.watch_lowest_price = None
                 # Check if we should buy immediately
                 levels_crossed = self._calculate_levels_crossed(self.strategy.last_buy_price, current_price)
                 if levels_crossed > 0:
                     rsi_15m = self.strategy.get_rsi_15m()
                     self._execute_batch_buy(current_price, levels_crossed, buy_rsi=rsi_15m)
            return

        # --- B. Normal Mode (Checking for new drop) ---
        levels_crossed = self._calculate_levels_crossed(self.strategy.last_buy_price, current_price)
        if levels_crossed > 0:
            rsi_5m = self.strategy.get_rsi_5m()
            
            # --- DEBUG LOGGING ---
            self.strategy.log_message(f"DEBUG CHECK: Drop Detected. Levels={levels_crossed}, TrailingActive={is_trailing_active}, RSI(5m)={rsi_5m}, Price={current_price}", level="debug")
            # ---------------------
            
            should_watch = False
            if is_trailing_active:
                if rsi_5m is not None and rsi_5m <= 30.0:
                    should_watch = True
            
            if should_watch:
                # Enter Watch Mode
                self.is_watching = True
                self.watch_lowest_price = current_price
                self.strategy.log_message(f"Trailing Buy [START]: Price target met but RSI(5m) {rsi_5m:.1f} <= 30. Entering Watch Mode.")
                self.strategy.save_state()
            else:
                # Immediate Buy (Standard Grid OR Trailing Active but RSI is safe)
                # User request: In Normal Mode, do NOT batch buy. Limit to 1 to avoid "Panic Buy" appearance.
                if levels_crossed > 1:
                     self.strategy.log_message(f"Normal Mode Drop: Levels crossed {levels_crossed}, but clamping to 1 (RSI {rsi_5m:.1f} Safe).")
                     levels_crossed = 1 
                
                self.strategy.log_message(f"Buy Trigger: Price met target. Trailing={is_trailing_active}, RSI={rsi_5m}. Executing {levels_crossed}.")
                rsi_15m = self.strategy.get_rsi_15m()
                self._execute_batch_buy(current_price, levels_crossed, buy_rsi=rsi_15m, is_accumulated=False)

    def _calculate_levels_crossed(self, reference_price: float, current_price: float) -> int:
        levels_crossed = 0
        temp_price = reference_price
        
        while True:
            next_level = temp_price * (1 - self.strategy.config.buy_rate)
            if current_price > next_level:
                break
            
            levels_crossed += 1
            temp_price = next_level
            
            # Safety limit
            if levels_crossed >= 10:
                logging.warning(f"Price drop too severe. Limiting to 10 buy splits.")
                break
        return levels_crossed

    def _execute_batch_buy(self, current_price: float, count: int, buy_rsi: float = None, is_accumulated: bool = False):
        # Check if we already have a pending buy at current price
        has_pending_buy = any(
            s.status == "PENDING_BUY" and abs(s.buy_price - current_price) / current_price < 0.001
            for s in self.strategy.splits
        )
        
        if has_pending_buy:
            logging.debug(f"Already have pending buy near {current_price}, skipping")
            return
        
        logging.info(f"Price dropped from {self.strategy.last_buy_price} to {current_price}. Creating {count} buy splits at {current_price}")
        
        for i in range(count):
            split = self.strategy._create_buy_split(current_price, buy_rsi=buy_rsi)
            if split and is_accumulated:
                split.is_accumulated = True
                
            if not split:
                logging.warning(f"Failed to create buy split {i+1}/{count}, stopping")
                break
            logging.info(f"Created buy split {i+1}/{count} at {current_price}")
