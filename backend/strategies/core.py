from abc import ABC, abstractmethod
import threading
import logging
from models.strategy_state import StrategyConfig

class BaseStrategy(ABC):
    def __init__(self, exchange_service, strategy_id: int, ticker: str, budget: float):
        self.exchange = exchange_service
        self.strategy_id = strategy_id
        self.ticker = ticker
        self.budget = budget
        self.is_running = False
        self.lock = threading.RLock()
        self.config = StrategyConfig()

    @abstractmethod
    def start(self, current_price=None):
        """Start the strategy."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the strategy."""
        pass

    @abstractmethod
    def tick(self, current_price=None, open_orders=None):
        """Main loop tick."""
        pass

    @abstractmethod
    def save_state(self):
        """Save strategy state to storage."""
        pass

    @abstractmethod
    def load_state(self):
        """Load strategy state from storage."""
        pass
        
    def update_config(self, config: StrategyConfig):
        """Update strategy configuration with defensive logging."""
        with self.lock:
            if not config:
                logging.error(f"❌ Strategy {self.strategy_id}: Received empty config update!")
                return
                
            logging.info(f"🔄 Updating config for Strategy {self.strategy_id}")
            logging.info(f"   - Mode: {config.strategy_mode}")
            logging.info(f"   - Min: {config.min_price:,.0f}, Max: {config.max_price:,.0f}")
            logging.info(f"   - Segments: {len(config.price_segments) if config.price_segments else 0}")
            
            try:
                self.config = config
                self.save_state()
                logging.info(f"✅ Strategy {self.strategy_id} config updated and saved.")
            except Exception as e:
                logging.error(f"❌ Strategy {self.strategy_id} failed to update/save config: {e}")
                raise e
            
    @abstractmethod
    def get_state(self, current_price=None):
        """Get current strategy state for UI/API."""
        pass

    def get_current_time_kst(self):
        """Get current time in KST timezone. Can be overridden for simulation."""
        from datetime import datetime, timezone, timedelta
        KST = timezone(timedelta(hours=9))
        now_utc = datetime.now(timezone.utc)
        return now_utc.astimezone(KST)
