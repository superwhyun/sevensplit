import logging
import time
from typing import Dict, List, Optional
from strategy import SevenSplitStrategy
from models.strategy_state import StrategyConfig

class StrategyService:
    def __init__(self, db, exchange_service):
        self.db = db
        self.exchange_service = exchange_service
        self.strategies: Dict[int, SevenSplitStrategy] = {}

    def load_strategies(self):
        """Load strategies from DB."""
        self.strategies = {}
        db_strategies = self.db.get_all_strategies()
        
        if not db_strategies:
            logging.info("No strategies found in DB.")
        else:
            logging.info(f"Loading {len(db_strategies)} strategies from DB.")
            for s in db_strategies:
                self.strategies[s.id] = SevenSplitStrategy(
                    self.exchange_service, 
                    s.id, 
                    s.ticker, 
                    s.budget
                )

    def get_strategy(self, strategy_id: int) -> Optional[SevenSplitStrategy]:
        return self.strategies.get(strategy_id)

    def get_all_strategies(self) -> List[SevenSplitStrategy]:
        return list(self.strategies.values())

    def create_strategy(self, name: str, ticker: str, budget: float, config: dict) -> int:
        try:
            s = self.db.create_strategy(
                name=name,
                ticker=ticker,
                budget=budget,
                config=config
            )
            self.strategies[s.id] = SevenSplitStrategy(
                self.exchange_service, 
                s.id, 
                s.ticker, 
                s.budget
            )
            return s.id
        except Exception as e:
            logging.error(f"Failed to create strategy: {e}")
            raise

    def delete_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")
        
        try:
            # Stop if running
            if self.strategies[strategy_id].is_running:
                self.strategies[strategy_id].stop()
                
            # Remove from memory
            del self.strategies[strategy_id]
            
            # Remove from DB
            self.db.delete_strategy(strategy_id)
        except Exception as e:
            logging.error(f"Failed to delete strategy: {e}")
            raise

    def start_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")
        
        strategy = self.strategies[strategy_id]
        
        # Fetch current price
        try:
            current_price = self.exchange_service.get_current_price(strategy.ticker)
        except Exception as e:
            logging.error(f"Failed to fetch price for {strategy.ticker}: {e}")
            current_price = None
        
        strategy.start(current_price=current_price)

    def stop_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")
        self.strategies[strategy_id].stop()

    def update_config(self, strategy_id: int, config: StrategyConfig, budget: float = None):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")
        
        if budget is not None:
            self.strategies[strategy_id].budget = budget
            
        self.strategies[strategy_id].update_config(config)

    def reset_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")

        try:
            # Stop
            if self.strategies[strategy_id].is_running:
                self.strategies[strategy_id].stop()

            # Cancel orders
            strategy = self.strategies[strategy_id]
            for split in strategy.splits:
                if split.buy_order_uuid:
                    try:
                        self.exchange_service.cancel_order(split.buy_order_uuid)
                    except Exception:
                        pass
                if split.sell_order_uuid:
                    try:
                        self.exchange_service.cancel_order(split.sell_order_uuid)
                    except Exception:
                        pass

            # Clear DB data
            self.db.delete_all_splits(strategy_id)
            self.db.delete_all_trades(strategy_id)
            
            # Reset state
            self.db.update_strategy_state(
                strategy_id,
                next_split_id=1,
                last_buy_price=None,
                last_sell_price=None
            )

            # Recreate instance
            s_rec = self.db.get_strategy(strategy_id)
            self.strategies[strategy_id] = SevenSplitStrategy(
                self.exchange_service, 
                strategy_id, 
                s_rec.ticker, 
                s_rec.budget
            )
            logging.info(f"Reset strategy {strategy_id}")

        except Exception as e:
            logging.error(f"Failed to reset strategy {strategy_id}: {e}")
            raise
