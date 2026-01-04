from typing import List, Dict, Any
from strategies import StrategyConfig
from .base import SimulationStrategy

class RSISimulationStrategy(SimulationStrategy):
    def __init__(self, config: StrategyConfig, budget: float, candles: List[Dict[str, Any]]):
        super().__init__(config, budget, candles)
        
    def tick(self, current_price: float = None, open_orders: list = None, market_context: dict = None):
        # Simply delegate to base class, which now handles full logic
        super().tick(current_price, open_orders, market_context=market_context)
