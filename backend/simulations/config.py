from typing import List, Dict, Any
from pydantic import BaseModel
from models.strategy_state import StrategyConfig

class SimulationConfig(BaseModel):
    strategy_config: StrategyConfig
    candles: List[Dict[str, Any]] # {timestamp, open, high, low, close}
    start_index: int
    ticker: str = "KRW-BTC"
    budget: float = 1000000.0
