from typing import List, Dict, Any
from strategies import StrategyConfig, PriceStrategyLogic
from .base import SimulationStrategy

class PriceSimulationStrategy(SimulationStrategy):
    def __init__(self, config: StrategyConfig, budget: float, candles: List[Dict[str, Any]]):
        super().__init__(config, budget, candles)
        self.price_logic = PriceStrategyLogic(self)
        
    def tick(self, current_price: float = None, open_orders: list = None):
        # Call base tick to establish common state and get open orders
        open_order_uuids = super().tick(current_price, open_orders)
        
        # If open_order_uuids is None, it means we shouldn't proceed (e.g. not running or error)
        # However, super().tick returns None if !is_running or error.
        # But wait, open_order_uuids is a set, so empty set is valid. None is invalid.
        if open_order_uuids is None:
            return

        if current_price is None:
            current_price = self.exchange.get_current_price(self.ticker)
            
        self.price_logic.tick(current_price, open_order_uuids)
