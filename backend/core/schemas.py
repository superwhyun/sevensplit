from pydantic import BaseModel
from typing import Optional
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


class DebugRSIRequest(BaseModel):
    strategy_id: int
    rsi: float
    prev_rsi: Optional[float] = None
    rsi_short: Optional[float] = None


class BacktestRequest(BaseModel):
    strategy_id: int
    start_time: Optional[str] = None  # ISO8601 UTC
    end_time: Optional[str] = None    # ISO8601 UTC
    exec_interval: Optional[str] = None  # "minutes/5" or "days"
    max_candles: int = 2000
    initial_krw: float = 10000000.0


class LiveSimulationStartRequest(BaseModel):
    strategy_id: int
    exec_interval: Optional[str] = None  # default by strategy mode
    replay_days: Optional[int] = None  # warm-up replay window before live start (1/3/7...)
    poll_seconds: float = 1.0
    initial_krw: float = 10000000.0
