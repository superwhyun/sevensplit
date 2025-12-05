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
        """Update strategy configuration."""
        with self.lock:
            logging.info(f"Updating config for Strategy {self.strategy_id}")
            self.config = config
            self.save_state()
            
    @abstractmethod
    def get_state(self, current_price=None):
        """Get current strategy state for UI/API."""
        pass
