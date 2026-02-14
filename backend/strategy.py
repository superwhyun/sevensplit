from typing import List, Optional
import logging
from database import get_db

from models.strategy_state import SplitState
from strategies import BaseStrategy, PriceStrategyLogic, RSIStrategyLogic
from strategies.logic_watch import WatchModeLogic
from strategies.tick_pipeline import TickPipeline
from strategies.runtime_helpers import (
    StrategyGuardService,
    StrategyLifecycleManager,
    StrategyOrderManager,
    StrategyStateManager,
    StrategyStatusPresenter,
    StrategyTickCoordinator,
)

class SevenSplitStrategy(BaseStrategy):
    def __init__(self, exchange, strategy_id: int, ticker: str, budget: float = 1000000.0):
        super().__init__(exchange, strategy_id, ticker, budget)
        self.db = get_db()
        # self.config, self.lock, self.is_running are initialized in super
        self.splits: List[SplitState] = []
        self.trade_history = []
        self.next_split_id = 1
        self.last_buy_price = None # Track the last buy price for creating next split
        self.last_sell_price = None # Track the last sell price for rebuy strategy
        self.last_sell_date = None # Track the last sell date for daily limits
        self.next_buy_target_price = None # Single source of truth for next buy target
        self.budget = budget
        self.last_status_msg = "" # Latest reason for skipping buy or bot action
        
        # Constants
        self.ORDER_TIMEOUT_SEC = 1800
        
        # Logic Modules
        self.price_logic = PriceStrategyLogic(self)
        self.rsi_logic = RSIStrategyLogic(self)
        self.watch_logic = WatchModeLogic(self)
        self.state_manager = StrategyStateManager()
        self.order_manager = StrategyOrderManager()
        self.lifecycle_manager = StrategyLifecycleManager()
        self.status_presenter = StrategyStatusPresenter()
        self.guard_service = StrategyGuardService()
        self.tick_coordinator = StrategyTickCoordinator()
        self.tick_pipeline = TickPipeline()

        
        # Load state first to see if we have existing config
        try:
            state_loaded = self.load_state()
        except Exception as e:
            logging.critical(f"❌ [CRITICAL] Strategy {strategy_id} state load failed: {e}")
            logging.critical("⚠️ Skipping default initialization to prevent data loss. Please check database connectivity or schema.")
            # Set state_loaded to True to bypass the default initialization block below
            state_loaded = True 
            self.is_running = False # Force stop safety

        # Check for "bad defaults" from previous runs
        # Old default was 50,000,000. If we see this, it's likely wrong (even for BTC, 50m is too low now).
        has_bad_default = (self.config.min_price == 50000000.0)
        
        # If no state loaded, or we have bad defaults, or uninitialized (0.0), try to set from current price
        if not state_loaded or has_bad_default or self.config.min_price == 0.0:
            current_price = self.exchange.get_current_price(self.ticker)
            if current_price:
                # Default grid range: -15% ~ +15% around the current price
                self.config.min_price = current_price * 0.85
                self.config.max_price = current_price * 1.15
                # Ensure buy/sell rates are default 0.005 if they look wrong (optional, but requested)
                if self.config.buy_rate != 0.005:
                    self.config.buy_rate = 0.005
                if self.config.sell_rate != 0.005:
                    self.config.sell_rate = 0.005
                    
                logging.info(f"Initialized default config for {ticker} (Strategy {strategy_id}): min_price={self.config.min_price}, max_price={self.config.max_price}")
                self.save_state()
                
    def log_message(self, msg: str, level: str = "info"):
        """Centralized logging method for strategy runtime."""
        if level == "error":
            logging.error(msg)
        elif level == "warning":
            logging.warning(msg)
        elif level == "debug":
            logging.debug(msg)
        else:
            logging.info(msg)

    def log_event(self, level: str, event_type: str, message: str):
        """Log critical system event to database and console."""
        # 1. Console Log
        self.log_message(f"[{event_type}] {message}", level=level.lower())
        
        # 2. DB Persistence
        try:
            self.db.add_event(self.strategy_id, level, event_type, message)
        except Exception as e:
            logging.error(f"Failed to persist event: {e}")

    def save_state(self):
        """Save state to database"""
        self.state_manager.save_state(self)

    def load_state(self):
        """Load state from database. Returns True if state was loaded, False otherwise."""
        return self.state_manager.load_state(self)

    def start(self, current_price=None):
        """Start the strategy. Create first buy order at current price."""
        with self.lock:
            self.lifecycle_manager.start(self, current_price=current_price)

    def stop(self):
        """Stop the strategy and cancel all pending orders."""
        with self.lock:
            self.lifecycle_manager.stop(self)

    def hard_stop(self):
        """Hard stop: cancel both pending buy and pending sell orders."""
        with self.lock:
            self.lifecycle_manager.stop(self, cancel_sells=True)

    # update_config is inherited from BaseStrategy

    def has_sufficient_budget(self, market_context: dict = None) -> bool:
        return self.guard_service.has_sufficient_budget(self, market_context=market_context)

    def check_trade_limit(self) -> bool:
        return self.guard_service.check_trade_limit(self)

    # buy method removed (delegated to RSIStrategyLogic)

    # RSI Calculation methods moved to specialized logic modules.

    def set_manual_target(self, price: Optional[float]):
        """Set or clear the next buy target price from user input."""
        with self.lock:
            if price is None:
                self.next_buy_target_price = None
            else:
                target = price
                try:
                    if hasattr(self.exchange, "normalize_price"):
                        target = float(self.exchange.normalize_price(target))
                except Exception:
                    pass
                self.next_buy_target_price = target
            self.save_state()
            logging.info(f"Strategy {self.strategy_id}: next_buy_target_price updated to {self.next_buy_target_price}")

    def tick(self, current_price: float = None, open_orders: list = None, market_context: dict = None):
        """Main tick function called periodically to check and update splits."""
        with self.lock:
            self.tick_pipeline.run(
                self,
                current_price=current_price,
                open_orders=open_orders,
                market_context=market_context,
            )

    def get_state(self, current_price=None):
        with self.lock:
            return self.status_presenter.get_state(self, current_price=current_price)
