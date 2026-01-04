from pydantic import BaseModel
from typing import Optional, List, Union
from models.strategy_state import StrategyConfig

class CreateStrategyRequest(BaseModel):
    name: str
    ticker: str
    budget: float = 1000000.0
    config: StrategyConfig

class CommandRequest(BaseModel):
    strategy_id: int

class ConfigRequest(BaseModel):
    strategy_id: int
    config: StrategyConfig
    budget: Optional[float] = None

class ManualTargetRequest(BaseModel):
    target_price: Optional[float]

class UpdateNameRequest(BaseModel):
    name: str

class SimulationRequest(BaseModel):
    start_time: Union[str, float]

class DebugRSIRequest(BaseModel):
    strategy_id: int
    rsi: float
    prev_rsi: Optional[float] = None
    rsi_short: Optional[float] = None
