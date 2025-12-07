from typing import List, Dict, Any
from strategies import StrategyConfig, RSIStrategyLogic
from .base import SimulationStrategy

class RSISimulationStrategy(SimulationStrategy):
    def __init__(self, config: StrategyConfig, budget: float, candles: List[Dict[str, Any]]):
        super().__init__(config, budget, candles)
        self.rsi_logic = RSIStrategyLogic(self)
        
    def tick(self, current_price: float = None, open_orders: list = None):
        open_order_uuids = super().tick(current_price, open_orders)
        if open_order_uuids is None:
            return

        if current_price is None:
            current_price = self.exchange.get_current_price(self.ticker)
            
        self.rsi_logic.tick(current_price, open_order_uuids)
