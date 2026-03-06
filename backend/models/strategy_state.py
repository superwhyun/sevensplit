from pydantic import BaseModel
from typing import Optional, List, Literal


class PriceSegment(BaseModel):
    min_price: float
    max_price: float
    investment_per_split: float
    max_splits: int

class StrategyConfig(BaseModel):
    investment_per_split: float = 100000.0 # KRW per split
    min_price: float = 0.0 # Min Price (0.0 means uninitialized)
    max_price: float = 0.0 # Max Price (0.0 means uninitialized)
    buy_rate: float = 0.005 # 0.5% - price drop rate to trigger next buy
    sell_rate: float = 0.005 # 0.5% - profit rate for sell order
    fee_rate: float = 0.0005 # 0.05% fee
    tick_interval: float = 1.0 # seconds - how often to check prices
    rebuy_strategy: str = "reset_on_clear" # Options: "last_buy_price", "last_sell_price", "reset_on_clear"
    max_trades_per_day: int = 100 # Max trades allowed per 24 hours

    # RSI Strategy Configuration
    strategy_mode: Literal["PRICE", "RSI"] = "PRICE"
    rsi_period: int = 14
    rsi_timeframe: str = "minutes/60"
    
    # RSI Buying (Accumulation)
    rsi_buy_max: float = 30.0
    rsi_buy_cross_threshold: float = 0.0
    rsi_buy_first_amount: int = 1
    rsi_buy_next_amount: int = 1

    # RSI Selling (Distribution)
    rsi_sell_min: float = 70.0
    rsi_sell_cross_threshold: float = 0.0
    rsi_sell_first_amount: int = 1
    rsi_sell_next_amount: int = 1

    # Risk Management
    stop_loss: float = -10.0
    max_holdings: int = 20

    # Trailing Buy Configuration
    use_trailing_buy: bool = False
    trailing_buy_rebound_percent: float = 0.2 # 0.2% Rebound threshold (default)
    trailing_buy_batch: bool = True # Applies on Watch-mode rebound exit: if True, catch-up buy multiple splits; else buy one.

    # Adaptive Buy Control (PRICE mode only)
    use_adaptive_buy_control: bool = False
    adaptive_sell_pressure_step: float = 1.0
    adaptive_buy_relief_step: float = 1.0
    adaptive_pressure_cap: float = 4.0
    adaptive_probe_multiplier: float = 0.5
    use_fast_drop_brake: bool = True
    fast_drop_trigger_levels: int = 2
    fast_drop_batch_cap: int = 1
    fast_drop_next_gap_levels: int = 2
    fast_drop_multiplier_cap: float = 0.75

    # Segmented Price Strategy
    price_segments: List[PriceSegment] = []

class SplitState(BaseModel):
    id: int
    status: str = "PENDING_BUY" # PENDING_BUY, BUY_FILLED, PENDING_SELL, SELL_FILLED
    buy_order_uuid: Optional[str] = None
    sell_order_uuid: Optional[str] = None
    buy_price: float = 0.0 # Target buy price
    actual_buy_price: float = 0.0 # Actual filled price
    buy_amount: float = 0.0 # KRW amount
    buy_volume: float = 0.0 # Coin volume
    target_sell_price: float = 0.0 # Target sell price
    created_at: Optional[str] = None
    bought_at: Optional[str] = None
    is_accumulated: bool = False
    buy_rsi: Optional[float] = None
