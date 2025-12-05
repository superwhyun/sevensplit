from pydantic import BaseModel
from typing import Optional

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
    strategy_mode: str = "PRICE" # PRICE or RSI
    rsi_period: int = 14
    rsi_timeframe: str = "minutes/60"
    
    # RSI Buying (Accumulation)
    rsi_buy_max: float = 30.0
    rsi_buy_first_threshold: float = 5.0
    rsi_buy_first_amount: int = 1
    rsi_buy_next_threshold: float = 1.0
    rsi_buy_next_amount: int = 1

    # RSI Selling (Distribution)
    rsi_sell_min: float = 70.0
    rsi_sell_first_threshold: float = 5.0
    rsi_sell_first_amount: int = 1
    rsi_sell_next_threshold: float = 1.0
    rsi_sell_next_amount: int = 1

    # Risk Management
    stop_loss: float = -10.0
    max_holdings: int = 20

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
