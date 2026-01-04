import logging
import time
from utils.indicators import calculate_rsi

class WatchModeLogic:
    def __init__(self, strategy):
        self.strategy = strategy

    def get_rsi_5m(self, current_price: float, market_context: dict = None) -> float:
        """
        Calculate Real-time 5-minute RSI(14) and RSI(5).
        Uses cached candles and injects current_price for live accuracy.
        """
        try:
            candles = None
            if market_context and 'candles' in market_context:
                ticker_candles = market_context['candles'].get(self.strategy.ticker, {})
                candles = ticker_candles.get("minutes/5")
            
            if not candles:
                candles = self.strategy.exchange.get_candles(self.strategy.ticker, interval="minutes/5", count=100)
                
            if not candles or len(candles) < 15:
                return None
            
            # --- CRITICAL FIX: Robust Chronological Sorting ---
            # Create a copy to avoid mutating the shared context data order
            sorted_candles = sorted(candles, key=lambda x: x.get('timestamp') or x.get('candle_date_time_kst') or 0)

            # Extract closes in ascending order
            closes = [float(c.get('trade_price') or c.get('close')) for c in sorted_candles]

            # --- LIVE UPDATE: Inject current price ---
            if closes:
                closes[-1] = current_price

            # Calculate RSI (14) - Logic Use
            rsi_14 = calculate_rsi(closes, 14)

             # Calculate RSI (5) - UI Use
            rsi_5 = calculate_rsi(closes, 5)

            # --- DEBUG LOG: Show data points ---
            if len(closes) >= 14:
                sample_closes = [round(c, 1) for c in closes[-5:]]
                logging.debug(f"RSI(5m) Calc: Count={len(closes)}, Recent Closes={sample_closes}, Result={rsi_14:.1f}")

            # Update State for Dashboard
            self.strategy.rsi_logic.current_rsi = rsi_14
            self.strategy.rsi_logic.current_rsi_short = rsi_5
            
            return rsi_14
            
        except Exception as e:
            logging.warning(f"Failed to calculate 5m RSI: {e}")
            return None

    def run_tick(self, current_price: float, market_context: dict = None):
        """Dispatcher for Strategy Logic"""
        # 1. Update Indicators (RSI 5m/Daily) - Always run for UI visibility
        rsi_5m = self.get_rsi_5m(current_price, market_context=market_context)
        if hasattr(self.strategy.rsi_logic, 'tick'):
            self.strategy.rsi_logic.tick(current_price, market_context=market_context)

        mode = self.strategy.config.strategy_mode

        # 2. Dispatch Logic (Only if appropriate mode)
        # PRICE Strategy Logic
        if mode in ["PRICE", "ALL"] or mode not in ["RSI"]:
            proceed, just_exited_watch = self.check_proceed_to_buy(current_price, rsi_5m)
            if proceed:
                # If we just exited watch mode or are in normal mode, proceed to buy
                self.strategy.price_logic.execute_buy_logic(current_price, rsi_5m, just_exited_watch=just_exited_watch, market_context=market_context)
            else:
                # Still in watch mode
                pass

    def check_proceed_to_buy(self, current_price: float, rsi_5m: float) -> tuple[bool, bool]:
        """
        Safety gate (Watch Mode)
        Returns: (proceed_to_buy, just_exited_watch)
        """
        # --- PRIORITY 1: Manual Target Overrides All Safety Filters ---
        if self.strategy.manual_target_price is not None:
            if self.strategy.is_watching:
                self.strategy.is_watching = False
                self.strategy.watch_lowest_price = None
                self.strategy.save_state()
            return (True, False)

        # --- PRIORITY 2: If Trailing Buy is OFF, bypass all watch logic ---
        if not self.strategy.config.use_trailing_buy:
            if self.strategy.is_watching:
                # Cleanup if it was previously watching before the config change
                self.strategy.is_watching = False
                self.strategy.watch_lowest_price = None
                self.strategy.save_state()
            return (True, False)

        rsi_threshold = self.strategy.config.rsi_buy_max
        rebound_threshold_pct = self.strategy.config.trailing_buy_rebound_percent / 100.0
        is_rsi_low = (rsi_5m is None or rsi_5m < rsi_threshold)

        # --- 1. RSI Level Check (Safety First) ---
        if is_rsi_low:
            # RSI is too low. Always enter/maintain watch mode to prevent buying during a crash.
            if not self.strategy.is_watching:
                self.strategy.is_watching = True
                self.strategy.watch_lowest_price = current_price
                val_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                self.strategy.log_event("WARNING", "WATCH_START", f"RSI(5m) {val_str} < {rsi_threshold}. Entering Watch Mode.")
                self.strategy.save_state()
            else:
                if self.strategy.watch_lowest_price is None or current_price < self.strategy.watch_lowest_price:
                    self.strategy.watch_lowest_price = current_price
                    self.strategy.save_state()
            return (False, False)

        # --- 2. RSI IS SAFE (> Threshold): Check Rebound from LOWEST PRICE ---
        else:
            if not self.strategy.is_watching:
                # We haven't entered watch mode, and RSI is safe.
                return (True, False)

            # Track lowest price during watch mode
            if self.strategy.watch_lowest_price is None:
                self.strategy.watch_lowest_price = current_price

            if current_price < self.strategy.watch_lowest_price:
                self.strategy.watch_lowest_price = current_price
                self.strategy.save_state()
                return (False, False)

            # Check rebound from LOWEST price tracked during watch mode
            # BOTH conditions required: RSI >= 30 AND rebound >= threshold
            rebound_target = self.strategy.watch_lowest_price * (1 + rebound_threshold_pct)
            if current_price >= rebound_target:
                rebound_pct = ((current_price - self.strategy.watch_lowest_price) / self.strategy.watch_lowest_price) * 100
                rsi_str = f"{rsi_5m:.1f}" if rsi_5m is not None else "None"
                self.strategy.log_event("INFO", "WATCH_END", f"Watch End: Rebound {rebound_pct:.2f}% from lowest ({self.strategy.watch_lowest_price:.1f}) and RSI Safe ({rsi_str}).")
                self.strategy.is_watching = False
                self.strategy.watch_lowest_price = None
                self.strategy.save_state()
                return (True, True)  # CRITICAL: just_exited_watch = True, buy immediately
            else:
                return (False, False)
