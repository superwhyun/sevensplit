"""ORM models for SevenSplit databases."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Strategy(Base):
    """Strategy configuration and runtime state"""
    __tablename__ = 'strategies'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, default="Default Strategy")
    ticker = Column(String(20), nullable=False, index=True) # Not unique anymore
    budget = Column(Float, nullable=False, default=1000000.0)

    # Configuration
    investment_per_split = Column(Float, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    buy_rate = Column(Float, nullable=False)
    sell_rate = Column(Float, nullable=False)
    fee_rate = Column(Float, nullable=False)
    tick_interval = Column(Float, nullable=False, default=1.0)
    rebuy_strategy = Column(String(50), nullable=False)
    max_trades_per_day = Column(Integer, nullable=False, default=100)

    # RSI Strategy Configuration
    strategy_mode = Column(String(20), nullable=False, default="PRICE") # PRICE or RSI (ALL removed)
    rsi_period = Column(Integer, nullable=False, default=14)
    rsi_timeframe = Column(String(20), nullable=False, default="minutes/60")
    
    # RSI Buying (Accumulation)
    rsi_buy_max = Column(Float, nullable=False, default=30.0)
    rsi_buy_cross_threshold = Column(Float, nullable=False, default=0.0)
    rsi_buy_first_amount = Column(Integer, nullable=False, default=1)
    rsi_buy_next_amount = Column(Integer, nullable=False, default=1)

    # RSI Selling (Distribution)
    rsi_sell_min = Column(Float, nullable=False, default=70.0)
    rsi_sell_cross_threshold = Column(Float, nullable=False, default=0.0)
    rsi_sell_first_amount = Column(Integer, nullable=False, default=1)
    rsi_sell_next_amount = Column(Integer, nullable=False, default=1)

    # Risk Management
    stop_loss = Column(Float, nullable=False, default=-10.0) # Percentage (e.g. -10.0)

    # Runtime state
    is_running = Column(Boolean, default=False)
    next_split_id = Column(Integer, default=1)
    last_buy_price = Column(Float, nullable=True)
    last_sell_price = Column(Float, nullable=True)
    max_holdings = Column(Integer, default=20, nullable=False)
    
    # Trailing Buy Configuration
    use_trailing_buy = Column(Boolean, default=False, nullable=False)
    trailing_buy_rebound_percent = Column(Float, default=0.2, nullable=False)
    trailing_buy_batch = Column(Boolean, default=True, nullable=False)
    use_adaptive_buy_control = Column(Boolean, default=False, nullable=False)
    adaptive_sell_pressure_step = Column(Float, default=1.0, nullable=False)
    adaptive_buy_relief_step = Column(Float, default=1.0, nullable=False)
    adaptive_pressure_cap = Column(Float, default=4.0, nullable=False)
    adaptive_probe_multiplier = Column(Float, default=0.5, nullable=False)
    use_fast_drop_brake = Column(Boolean, default=True, nullable=False)
    fast_drop_trigger_levels = Column(Integer, default=2, nullable=False)
    fast_drop_batch_cap = Column(Integer, default=1, nullable=False)
    fast_drop_next_gap_levels = Column(Integer, default=2, nullable=False)
    fast_drop_multiplier_cap = Column(Float, default=0.75, nullable=False)
    
    # Price Segments (JSON List)
    price_segments = Column(JSON, nullable=True)

    # Trailing Buy State
    is_watching = Column(Boolean, default=False, nullable=False)
    watch_lowest_price = Column(Float, nullable=True)
    pending_buy_units = Column(Integer, default=0, nullable=False)    # Accumulated buy units
    adaptive_reentry_pressure = Column(Float, default=0.0, nullable=False)
    next_buy_target_price = Column(Float, nullable=True)  # Next buy target (user-set/auto-updated)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    splits = relationship("Split", back_populates="strategy", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="strategy", cascade="all, delete-orphan")


class Split(Base):
    """Active trading splits"""
    __tablename__ = 'splits'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False, index=True)
    ticker = Column(String(20), nullable=False)
    split_id = Column(Integer, nullable=False)  # Strategy-specific ID

    status = Column(String(20), nullable=False)  # PENDING_BUY, BUY_FILLED, PENDING_SELL
    buy_price = Column(Float, nullable=False)
    target_sell_price = Column(Float, nullable=False)
    investment_amount = Column(Float, nullable=False)
    coin_volume = Column(Float, nullable=True)
    is_accumulated = Column(Boolean, default=False, nullable=False)
    buy_rsi = Column(Float, nullable=True)

    # Order IDs
    buy_order_id = Column(String(100), nullable=True)
    sell_order_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    buy_filled_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship
    strategy = relationship("Strategy", back_populates="splits")


class Trade(Base):
    """Completed trade history"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False, index=True)
    ticker = Column(String(20), nullable=False)
    split_id = Column(Integer, nullable=False)

    # Trade details
    buy_price = Column(Float, nullable=False)
    sell_price = Column(Float, nullable=False)
    coin_volume = Column(Float, nullable=False)

    # Amounts
    buy_amount = Column(Float, nullable=False)
    sell_amount = Column(Float, nullable=False)
    gross_profit = Column(Float, nullable=False)
    total_fee = Column(Float, nullable=False)
    net_profit = Column(Float, nullable=False)
    profit_rate = Column(Float, nullable=False)
    is_accumulated = Column(Boolean, default=False, nullable=False)
    buy_rsi = Column(Float, nullable=True)

    # Order IDs
    buy_order_id = Column(String(100), nullable=True)
    sell_order_id = Column(String(100), nullable=True)

    # Timestamps
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    bought_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    strategy = relationship("Strategy", back_populates="trades")


class SystemConfig(Base):
    """System-wide configuration (singleton table)"""
    __tablename__ = 'system_config'

    id = Column(Integer, primary_key=True)
    mode = Column(String(10), nullable=False, default='REAL')
    upbit_access_key = Column(String(100), nullable=True)
    upbit_secret_key = Column(String(100), nullable=True)

    # Timestamps
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SystemEvent(Base):
    """System events log (persistent)"""
    __tablename__ = 'system_events'

    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False, index=True)
    level = Column(String(20), nullable=False) # INFO, WARNING, ERROR
    event_type = Column(String(50), nullable=False) # WATCH_START, WATCH_END, SYSTEM_ERROR, etc.
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationship
    strategy = relationship("Strategy")


class CandleMinutes5(Base):
    """5-minute candles"""
    __tablename__ = 'candles_min_5'
    ticker = Column(String(20), primary_key=True)
    timestamp = Column(Float, primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    kst_time = Column(String(30), nullable=True)
    utc_time = Column(String(30), nullable=True)

class CandleMinutes60(Base):
    """1-hour candles"""
    __tablename__ = 'candles_min_60'
    ticker = Column(String(20), primary_key=True)
    timestamp = Column(Float, primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    kst_time = Column(String(30), nullable=True)
    utc_time = Column(String(30), nullable=True)

class CandleDays(Base):
    """Daily candles"""
    __tablename__ = 'candles_days'
    ticker = Column(String(20), primary_key=True)
    timestamp = Column(Float, primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    kst_time = Column(String(30), nullable=True)
    utc_time = Column(String(30), nullable=True)
