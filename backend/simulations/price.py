from typing import List, Dict, Any
from strategies import StrategyConfig
from .base import SimulationStrategy

class PriceSimulationStrategy(SimulationStrategy):
    def __init__(self, config: StrategyConfig, budget: float, candles: List[Dict[str, Any]]):
        super().__init__(config, budget, candles)
        self.sim_logs = []
        
    def log_message(self, msg: str, level: str = "info"):
        self.sim_logs.append(msg)

    def tick(self, current_price: float = None, open_orders: list = None, market_context: dict = None):
        # Simply delegate to base class, which now handles full logic
        super().tick(current_price, open_orders, market_context=market_context)
