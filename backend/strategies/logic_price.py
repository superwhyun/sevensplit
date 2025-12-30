import logging
import time

class PriceStrategyLogic:
    def __init__(self, strategy):
        self.strategy = strategy
        
        # Trailing Buy State (Moved from Strategy or newly initialized)
        self.is_watching = False
        self.watch_lowest_price = None

    def validate_buy(self, price: float) -> bool:
        """Validate buy price against strategy constraints (Price Range)."""
        if price < self.strategy.config.min_price:
            logging.warning(f"Price Logic: Target price {price} below min_price {self.strategy.config.min_price}. Skipping.")
            return False
            
        if self.strategy.config.max_price > 0 and price > self.strategy.config.max_price:
            logging.warning(f"Price Logic: Target price {price} above max_price {self.strategy.config.max_price}. Skipping.")
            return False
            
        return True

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
        should_buy = False
        reference_price_log = ""

        if self.strategy.config.rebuy_strategy == "reset_on_clear":
            # Strategy 1: Reset and start at current price
            should_buy = True
            reference_price_log = f"Reset on clear (Start Price: {current_price})"
            
        elif self.strategy.config.rebuy_strategy == "last_sell_price":
            # Strategy 2: Use last sell price as reference
            reference_price = self.strategy.last_sell_price if self.strategy.last_sell_price is not None else current_price
            
            if self.strategy.last_sell_price is not None:
                logging.info(f"All positions cleared. Using last sell price {reference_price} as reference")
            else:
                logging.info(f"No last sell price, using current price: {current_price}")

            next_buy_price = reference_price * (1 - self.strategy.config.buy_rate)
            
            if current_price <= next_buy_price:
                should_buy = True
                reference_price_log = f"Price drop from last sell {reference_price} -> {current_price}"

        if should_buy:
             # Safety Check: Enforce Trailing Buy (RSI) even for re-entry
             if self.strategy.config.use_trailing_buy:
                 rsi_5m = self.strategy.get_rsi_5m()
                 threshold = self.strategy.config.rsi_buy_max
                 
                 # --- WATCH MODE HANDLING ---
                 if self.is_watching:
                     # 1. Update Lowest Price
                     if self.watch_lowest_price is None or current_price < self.watch_lowest_price:
                         self.watch_lowest_price = current_price
                         self.strategy.save_state()

                     # 2. Check Rebound
                     REBOUND_THRESHOLD = self.strategy.config.trailing_buy_rebound_percent / 100.0
                     rebound_target = self.watch_lowest_price * (1 + REBOUND_THRESHOLD)
                     is_rebound_ok = current_price >= rebound_target
                     
                     # 3. Check RSI (Lazy)
                     is_rsi_ok = False
                     if is_rebound_ok:
                         is_rsi_ok = (rsi_5m is not None and rsi_5m > threshold)
                     
                     if is_rebound_ok and is_rsi_ok:
                         # Confirmation: Check if we are still below the ORIGINAL target price
                         # (Don't buy if we rebounded way above the entry point)
                         target_price = reference_price * (1 - self.strategy.config.buy_rate)
                         if current_price > target_price:
                             logging.info(f"Trailing Buy [RESET]: Rebound met but price {current_price} > Target {target_price}. Resetting Watch Mode.")
                             self.is_watching = False
                             self.watch_lowest_price = None
                             self.strategy.save_state()
                             return False # No action (wait for next drop)
                         
                         # Proceed to Buy
                         logging.info(f"Trailing Buy [EXEC]: Rebound met (Low {self.watch_lowest_price} -> {current_price}) and RSI Safe.")
                         self.is_watching = False
                         self.watch_lowest_price = None
                         self.strategy.save_state()
                         # Continue to execution code below...
                     else:
                         # Continue Watching
                         if is_rebound_ok and not is_rsi_ok:
                             val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                             logging.debug(f"Trailing Buy [WAIT]: Rebound OK({current_price}) but RSI({val_str}) <= {threshold}.")
                         return True # Handled (Wait)

                 # --- ENTER WATCH MODE ---
                 # Same logic as before: If not watching, check if we SHOULD watch
                 should_watch = False
                 if rsi_5m is None: # Fail-safe
                     should_watch = True
                 elif rsi_5m <= threshold:
                     should_watch = True
                 
                 if should_watch:
                     self.is_watching = True
                     self.watch_lowest_price = current_price
                     rsi_val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                     self.strategy.log_event("WARNING", "WATCH_START", f"Trailing Buy [START]: Re-entry trigger met but RSI(5m) {rsi_val_str} <= {threshold}. Entering Watch Mode.")
                     self.strategy.save_state()
                     return True # Handled (entered watch mode)
            
             # If safe or trailing off, execute buy
             # New Logging for Rebuy
             next_target = current_price * (1 - self.strategy.config.buy_rate)
             msg = (f"Rebuy/First Buy Executed.\n"
                    f"- Condition: {reference_price_log}.\n"
                    f"- Current Price: {current_price}\n"
                    f"- Next Buy Target: {next_target:.1f}")
             self.strategy.log_event("INFO", "BUY_EXEC", msg)

             logging.info(f"{reference_price_log}. Creating buy split at current price")
             # Use 5m RSI
             rsi_5m = self.strategy.get_rsi_5m()
             self.strategy._create_buy_split(current_price, use_market_order=True, buy_rsi=rsi_5m)
             # Also update last_buy_price conceptually if needed? 
             # _create_buy_split updates last_buy_price.
             return True
        
        return False

    def _handle_active_positions(self, current_price: float):
        if self.strategy.last_buy_price is None:
            # No previous buy, check check safety before creating one
            
            # Safety Check: Enforce Trailing Buy (RSI) for First Buy
            if self.strategy.config.use_trailing_buy:
                 rsi_5m = self.strategy.get_rsi_5m()
                 threshold = self.strategy.config.rsi_buy_max
                 
                 # --- WATCH MODE HANDLING (First Buy) ---
                 if self.is_watching:
                     # 1. Update Lowest Price
                     if self.watch_lowest_price is None or current_price < self.watch_lowest_price:
                         self.watch_lowest_price = current_price
                         self.strategy.save_state()

                     # 2. Check Rebound
                     REBOUND_THRESHOLD = self.strategy.config.trailing_buy_rebound_percent / 100.0
                     rebound_target = self.watch_lowest_price * (1 + REBOUND_THRESHOLD)
                     is_rebound_ok = current_price >= rebound_target
                     
                     # 3. Check RSI (Lazy)
                     is_rsi_ok = False
                     if is_rebound_ok:
                         is_rsi_ok = (rsi_5m is not None and rsi_5m > threshold)
                     
                     if is_rebound_ok and is_rsi_ok:
                         # Confirmation: No Target Price check for First Buy (Market Entry)
                         # OR do we want to respect min_price? validate_buy handles min_price.
                         
                         # Proceed to Buy
                         logging.info(f"Trailing Buy [EXEC]: First Buy Rebound met (Low {self.watch_lowest_price} -> {current_price}) and RSI Safe.")
                         self.is_watching = False
                         self.watch_lowest_price = None
                         self.strategy.save_state()
                         # Continue to execution code below...
                     else:
                         # Continue Watching
                         if is_rebound_ok and not is_rsi_ok:
                             val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                             logging.debug(f"Trailing Buy [WAIT-First]: Rebound OK({current_price}) but RSI({val_str}) <= {threshold}.")
                         return # Handled (Wait)

                 # --- ENTER WATCH MODE ---
                 should_watch = False
                 if rsi_5m is None:
                     should_watch = True
                 elif rsi_5m <= threshold:
                     should_watch = True
                 
                 if should_watch:
                     self.is_watching = True
                     self.watch_lowest_price = current_price
                     rsi_val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                     self.strategy.log_event("WARNING", "WATCH_START", f"Trailing Buy [START]: First Buy trigger but RSI(5m) {rsi_val_str} <= {threshold}. Entering Watch Mode.")
                     self.strategy.save_state()
                     return

            # New Logging for First Buy (Active Positions Logic)
            next_target = current_price * (1 - self.strategy.config.buy_rate)
            msg = (f"First Buy Executed (Safe Mode).\n"
                   f"- Condition: No previous buy recorded and conditions safe.\n"
                   f"- Current Price: {current_price}\n"
                   f"- Next Buy Target: {next_target:.1f}")
            self.strategy.log_event("INFO", "BUY_EXEC", msg)

            logging.info(f"No previous buy, and conditions safe (or trailing off). Creating first split at current price: {current_price}")
            rsi_5m = self.strategy.get_rsi_5m()
            self.strategy._create_buy_split(current_price, buy_rsi=rsi_5m)
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
                # Use Configured Threshold
                threshold = self.strategy.config.rsi_buy_max
                is_rsi_ok = (rsi_5m is not None and rsi_5m > threshold)

            if is_rebound_ok and is_rsi_ok:
                # Trigger Buy!
                levels_crossed = self._calculate_levels_crossed(self.strategy.last_buy_price, current_price)
                
                # Check Batch Buy Config
                if not self.strategy.config.trailing_buy_batch:
                    if levels_crossed > 1:
                        self.strategy.log_message(f"Trailing Buy: Batch buy disabled. Reducing {levels_crossed} splits to 1.", level="info")
                        levels_crossed = 1
                
                # Double Check Fail-safe for logging
                rsi_val = rsi_5m if rsi_5m is not None else 0.0

                if levels_crossed > 0:
                     self.is_watching = False
                     self.watch_lowest_price = None
                     
                     # Detailed Log for Trailing Buy
                     next_target = current_price * (1 - self.strategy.config.buy_rate)
                     rebound_pct = ((current_price - self.watch_lowest_price) / self.watch_lowest_price) * 100 if self.watch_lowest_price else 0.0
                     msg = (f"Trailing Buy Executed.\n"
                            f"- Condition: Rebound {rebound_pct:.2f}% (Low {self.watch_lowest_price} -> Cur {current_price}) AND RSI {rsi_5m:.1f} > {threshold}.\n"
                            f"- Next Buy Target: {next_target:.1f}")
                     self.strategy.log_event("INFO", "BUY_EXEC", msg)
                     
                     self.strategy.save_state()
                     # Use 5m RSI for record
                     self._execute_batch_buy(current_price, levels_crossed, buy_rsi=rsi_val, is_accumulated=(levels_crossed > 1))
                else:
                     logging.info(f"Trailing Buy [RESET]: Rebound met but price {current_price} is above target {next_buy_level}. No buy needed.")
                
                # Reset Watch Mode
                self.is_watching = False
                self.watch_lowest_price = None
                self.strategy.save_state()
            else:
                # Waiting
                if is_rebound_ok and not is_rsi_ok:
                     val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                     logging.debug(f"Trailing Buy [WAIT]: Rebound OK({current_price}) but RSI({val_str}) <= {self.strategy.config.rsi_buy_max}.")
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
                     # Use 5m RSI
                     rsi_5m = self.strategy.get_rsi_5m()
                     self._execute_batch_buy(current_price, levels_crossed, buy_rsi=rsi_5m)
            return

        # --- B. Normal Mode (Checking for new drop) ---
        levels_crossed = self._calculate_levels_crossed(self.strategy.last_buy_price, current_price)
        if levels_crossed > 0:
            rsi_5m = self.strategy.get_rsi_5m()
            
            # --- DEBUG LOGGING ---
            rsi_val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
            self.strategy.log_message(f"DEBUG CHECK: Drop Detected. Levels={levels_crossed}, TrailingActive={is_trailing_active}, RSI(5m)={rsi_val_str}, Price={current_price}", level="debug")
            # ---------------------
            
            should_watch = False
            if is_trailing_active:
                threshold = self.strategy.config.rsi_buy_max
                
                # Fail-safe: If RSI is None, assume unsafe and watch
                if rsi_5m is None:
                    should_watch = True
                    self.strategy.log_event("WARNING", "SYSTEM_WARNING", "Trailing Buy: RSI(5m) is None. Enforcing Watch Mode for safety.")
                elif rsi_5m <= threshold:
                    should_watch = True
            
            if should_watch:
                # Enter Watch Mode
                self.is_watching = True
                self.watch_lowest_price = current_price
                rsi_val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                self.strategy.log_event("WARNING", "WATCH_START", f"Trailing Buy [START]: Price target met but RSI(5m) {rsi_val_str} <= {threshold}. Entering Watch Mode.")
                self.strategy.save_state()
            else:
                # Immediate Buy (Standard Grid OR Trailing Active but RSI is safe)
                # User request: In Normal Mode, do NOT batch buy. Limit to 1 to avoid "Panic Buy" appearance.
                if levels_crossed > 1:
                     val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                     self.strategy.log_message(f"Normal Mode Drop: Levels crossed {levels_crossed}, but clamping to 1 (RSI {val_str} Safe).")
                     levels_crossed = 1 
                
                val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                
                # Detailed Log for Grid Buy
                next_target = current_price * (1 - self.strategy.config.buy_rate)
                target_price = self.strategy.last_buy_price * (1 - self.strategy.config.buy_rate)
                
                msg = (f"Grid Buy Executed.\n"
                       f"- Condition: Price {current_price} <= Target {target_price:.1f}.\n"
                       f"- RSI Safety: {val_str} (Limit: {self.strategy.config.rsi_buy_max}, TrailingActive: {is_trailing_active}).\n"
                       f"- Next Buy Target: {next_target:.1f}")
                self.strategy.log_event("INFO", "BUY_EXEC", msg)

                # Use 5m RSI instead of 15m
                self._execute_batch_buy(current_price, levels_crossed, buy_rsi=rsi_5m, is_accumulated=False)

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
