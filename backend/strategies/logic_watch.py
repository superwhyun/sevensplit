import logging
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
            # Create a copy and sort by timestamp (integer) to avoid TypeError in Python 3
            sorted_candles = sorted(candles, key=lambda x: x.get('timestamp') or 0)

            # Extract closes safely using multiple possible keys
            closes = []
            for c in sorted_candles:
                price = c.get('trade_price') or c.get('close') or c.get('close_price')
                if price is not None:
                    closes.append(float(price))

            # --- LIVE UPDATE: Inject current price ---
            if closes:
                closes[-1] = current_price

            # Calculate RSI (14) - Logic Use
            rsi_14 = calculate_rsi(closes, 14)

             # Calculate RSI (5) - UI Use (RSI(5)/5m)
            rsi_5 = calculate_rsi(closes, 5)

            # --- DEBUG LOG: Show data points ---
            if rsi_14 is not None:
                logging.info(f"[5m RSI] Updated: {rsi_14:.2f} (Short: {rsi_5 if rsi_5 is not None else 0:.2f}), Closes: {len(closes)}")
            else:
                logging.debug(f"RSI(5m) Calc: Count={len(closes)} - Result is None (Warmup?)")

            # Update State for Dashboard
            self.strategy.rsi_logic.current_rsi = rsi_14
            self.strategy.rsi_logic.current_rsi_short = rsi_5
            
            return rsi_14
            
        except Exception as e:
            logging.warning(f"Failed to calculate 5m RSI: {e}")
            return None

    def check_proceed_to_buy(self, current_price: float, rsi_5m: float) -> tuple[bool, bool]:
        """
        Safety gate (Watch Mode)
        Returns: (proceed_to_buy, just_exited_watch)
        """
        if self._should_bypass_watch():
            self._clear_watch_state_if_active()
            return (True, False)

        rsi_threshold = self.strategy.config.rsi_buy_max
        rebound_threshold_pct = self.strategy.config.trailing_buy_rebound_percent / 100.0
        is_rsi_low = (rsi_5m is None or rsi_5m < rsi_threshold)

        if is_rsi_low:
            return self._handle_watch_entry_or_maintenance(current_price, rsi_5m, rsi_threshold)

        return self._handle_watch_exit_or_bypass(current_price, rsi_5m, rebound_threshold_pct)

    def _should_bypass_watch(self) -> bool:
        return not self.strategy.config.use_trailing_buy

    def _clear_watch_state_if_active(self) -> None:
        if not self.strategy.is_watching:
            return
        self.strategy.is_watching = False
        self.strategy.watch_lowest_price = None
        self.strategy.save_state()

    def _handle_watch_entry_or_maintenance(
        self,
        current_price: float,
        rsi_5m: float,
        rsi_threshold: float,
    ) -> tuple[bool, bool]:
        if not self.strategy.is_watching:
            self._enter_watch_mode(current_price, rsi_5m, rsi_threshold)

        if self.strategy.watch_lowest_price is None or current_price < self.strategy.watch_lowest_price:
            self.strategy.watch_lowest_price = current_price
            self.strategy.save_state()

        self._set_watch_status_below_threshold(rsi_5m, rsi_threshold)
        return (False, False)

    def _enter_watch_mode(self, current_price: float, rsi_5m: float, rsi_threshold: float) -> None:
        self.strategy.is_watching = True
        self.strategy.watch_lowest_price = current_price
        val_str = self._format_rsi(rsi_5m)
        self.strategy.log_event(
            "WARNING",
            "WATCH_START",
            f"RSI(5m) {val_str} < {rsi_threshold}. Entering Watch Mode.",
        )
        self.strategy.save_state()

    def _handle_watch_exit_or_bypass(
        self,
        current_price: float,
        rsi_5m: float,
        rebound_threshold_pct: float,
    ) -> tuple[bool, bool]:
        if not self.strategy.is_watching:
            return (True, False)

        if self.strategy.watch_lowest_price is None:
            self.strategy.watch_lowest_price = current_price

        if current_price < self.strategy.watch_lowest_price:
            self.strategy.watch_lowest_price = current_price
            self.strategy.save_state()
            return (False, False)

        rebound_target = self.strategy.watch_lowest_price * (1 + rebound_threshold_pct)
        if current_price >= rebound_target:
            return self._exit_watch_mode(current_price, rsi_5m)

        self._set_watch_status_waiting_rebound(current_price, rsi_5m)
        return (False, False)

    def _exit_watch_mode(self, current_price: float, rsi_5m: float) -> tuple[bool, bool]:
        rebound_pct = ((current_price - self.strategy.watch_lowest_price) / self.strategy.watch_lowest_price) * 100
        self.strategy.log_event(
            "INFO",
            "WATCH_END",
            "Watch End: Rebound "
            f"{rebound_pct:.2f}% from lowest ({self.strategy.watch_lowest_price:.1f}) "
            f"and RSI Safe ({self._format_rsi(rsi_5m)}).",
        )
        self.strategy.is_watching = False
        self.strategy.watch_lowest_price = None
        self.strategy.save_state()
        return (True, True)

    def _set_watch_status_below_threshold(self, rsi_5m: float, rsi_threshold: float) -> None:
        self.strategy.last_status_msg = (
            f"Watch Mode: RSI(5m) {self._format_rsi(rsi_5m)} is below threshold {rsi_threshold}. "
            "Waiting for rebound."
        )

    def _set_watch_status_waiting_rebound(self, current_price: float, rsi_5m: float) -> None:
        rebound_pct_current = (
            (current_price - self.strategy.watch_lowest_price) / self.strategy.watch_lowest_price
        ) * 100
        self.strategy.last_status_msg = (
            f"Watch Mode: RSI Safe ({self._format_rsi(rsi_5m)}). "
            f"Waiting for rebound: {rebound_pct_current:.2f}% / "
            f"{self.strategy.config.trailing_buy_rebound_percent}% Target."
        )

    def _format_rsi(self, rsi: float) -> str:
        return f"{rsi:.1f}" if rsi is not None else "None"
