"""
Database module for SevenSplit trading bot.
Uses SQLite with SQLAlchemy ORM.
"""

from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime, timezone, timedelta
import json
import os
import logging

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
    strategy_mode = Column(String(20), nullable=False, default="PRICE") # PRICE or RSI
    rsi_period = Column(Integer, nullable=False, default=14)
    rsi_timeframe = Column(String(20), nullable=False, default="minutes/60")
    
    # RSI Buying (Accumulation)
    rsi_buy_max = Column(Float, nullable=False, default=30.0)
    rsi_buy_first_threshold = Column(Float, nullable=False, default=5.0)
    rsi_buy_first_amount = Column(Integer, nullable=False, default=1)
    rsi_buy_next_threshold = Column(Float, nullable=False, default=1.0)
    rsi_buy_next_amount = Column(Integer, nullable=False, default=1)

    # RSI Selling (Distribution)
    rsi_sell_min = Column(Float, nullable=False, default=70.0)
    rsi_sell_first_threshold = Column(Float, nullable=False, default=5.0)
    rsi_sell_first_amount = Column(Integer, nullable=False, default=1)
    rsi_sell_next_threshold = Column(Float, nullable=False, default=1.0)
    rsi_sell_next_threshold = Column(Float, nullable=False, default=1.0)
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
    
    # Price Segments (JSON List)
    price_segments = Column(JSON, nullable=True)

    # Trailing Buy State
    is_watching = Column(Boolean, default=False, nullable=False)
    watch_lowest_price = Column(Float, nullable=True)
    pending_buy_units = Column(Integer, default=0, nullable=False)    # Accumulated buy units
    manual_target_price = Column(Float, nullable=True) # Manual override for next buy target

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
    mode = Column(String(10), nullable=False, default='MOCK')  # 'MOCK' or 'REAL'
    upbit_access_key = Column(String(100), nullable=True)
    upbit_secret_key = Column(String(100), nullable=True)

    # Timestamps
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MockAccount(Base):
    """Mock exchange account balances"""
    __tablename__ = 'mock_accounts'

    id = Column(Integer, primary_key=True)
    currency = Column(String(20), unique=True, nullable=False, index=True)
    balance = Column(Float, nullable=False, default=0.0)
    avg_buy_price = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MockOrder(Base):
    """Mock exchange orders (persisted for restart recovery)"""
    __tablename__ = 'mock_orders'

    id = Column(Integer, primary_key=True)
    uuid = Column(String(100), unique=True, nullable=False, index=True)
    market = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # bid or ask
    ord_type = Column(String(20), nullable=False)  # limit, market, price
    price = Column(String(50), nullable=True)
    volume = Column(String(50), nullable=True)
    state = Column(String(20), nullable=False, default='wait')  # wait, done, cancel
    
    # Order details
    remaining_volume = Column(String(50), nullable=True)
    reserved_fee = Column(String(50), nullable=True)
    remaining_fee = Column(String(50), nullable=True)
    paid_fee = Column(String(50), nullable=True)
    locked = Column(String(50), nullable=True)
    executed_volume = Column(String(50), nullable=True)
    trades_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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


class DatabaseManager:
    """Database manager for SevenSplit bot"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Check environment variable first
            env_db_path = os.getenv("DB_PATH")
            if env_db_path:
                db_path = env_db_path
            else:
                # Derive from MODE if not explicitly set
                mode = os.getenv("MODE", "MOCK").upper()
                db_filename = "sevensplit_real.db" if mode == "REAL" else "sevensplit_mock.db"
                
                # Default to backend directory
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(backend_dir, db_filename)

        self.db_path = db_path
        print(f"Using Database: {self.db_path}")
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        
        # Enable WAL mode for better concurrency
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()

        Base.metadata.create_all(self.engine)
        self._migrate_schema()
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _migrate_schema(self):
        """Check and update database schema for new columns"""
        from sqlalchemy import text
        
        with self.engine.connect() as conn:
            # 1. Check strategies.max_trades_per_day
            try:
                result = conn.execute(text("PRAGMA table_info(strategies)"))
                columns = [row[1] for row in result.fetchall()]
                if 'max_trades_per_day' not in columns:
                    print("Migrating: Adding max_trades_per_day to strategies table")
                    conn.execute(text("ALTER TABLE strategies ADD COLUMN max_trades_per_day INTEGER DEFAULT 100 NOT NULL"))
                    conn.commit()
            except Exception as e:
                print(f"Migration warning (strategies): {e}")

            # 2. Check trades.bought_at
            try:
                result = conn.execute(text("PRAGMA table_info(trades)"))
                columns = [row[1] for row in result.fetchall()]
                if 'bought_at' not in columns:
                    print("Migrating: Adding bought_at to trades table")
                    conn.execute(text("ALTER TABLE trades ADD COLUMN bought_at DATETIME"))
                    conn.commit()
            except Exception as e:
                print(f"Migration warning (trades): {e}")

            # 3. Check strategies.strategy_mode (RSI Migration)
            try:
                result = conn.execute(text("PRAGMA table_info(strategies)"))
                columns = [row[1] for row in result.fetchall()]
                
                # List of new columns to check and add
                new_columns = [
                    ('strategy_mode', "VARCHAR(20) DEFAULT 'PRICE' NOT NULL"),
                    ('rsi_period', "INTEGER DEFAULT 14 NOT NULL"),
                    ('rsi_timeframe', "VARCHAR(20) DEFAULT 'minutes/60' NOT NULL"),
                    ('rsi_buy_max', "FLOAT DEFAULT 30.0 NOT NULL"),
                    ('rsi_buy_first_threshold', "FLOAT DEFAULT 5.0 NOT NULL"),
                    ('rsi_buy_first_amount', "INTEGER DEFAULT 1 NOT NULL"),
                    ('rsi_buy_next_threshold', "FLOAT DEFAULT 1.0 NOT NULL"),
                    ('rsi_buy_next_amount', "INTEGER DEFAULT 1 NOT NULL"),
                    ('rsi_sell_min', "FLOAT DEFAULT 70.0 NOT NULL"),
                    ('rsi_sell_first_threshold', "FLOAT DEFAULT 5.0 NOT NULL"),
                    ('rsi_sell_first_amount', "INTEGER DEFAULT 1 NOT NULL"),
                    ('rsi_sell_next_threshold', "FLOAT DEFAULT 1.0 NOT NULL"),
                    ('rsi_sell_next_amount', "INTEGER DEFAULT 1 NOT NULL"),
                    ('stop_loss', "FLOAT DEFAULT -10.0 NOT NULL"),
                    ('max_holdings', "INTEGER DEFAULT 20 NOT NULL")
                ]

                for col_name, col_def in new_columns:
                    if col_name not in columns:
                        print(f"Migrating: Adding {col_name} to strategies table")
                        conn.execute(text(f"ALTER TABLE strategies ADD COLUMN {col_name} {col_def}"))
                
                conn.commit()
            except Exception as e:
                print(f"Migration warning (strategies RSI): {e}")

            # 4. Check strategies.is_watching (Trailing Buy State Migration)
            try:
                result = conn.execute(text("PRAGMA table_info(strategies)"))
                columns = [row[1] for row in result.fetchall()]
                
                # State Variables
                new_state_columns = [
                    ('is_watching', "BOOLEAN DEFAULT False NOT NULL"),
                    ('watch_lowest_price', "FLOAT"),
                    ('pending_buy_units', "INTEGER DEFAULT 0 NOT NULL")
                ]
                for col_name, col_def in new_state_columns:
                    if col_name not in columns:
                        print(f"Migrating: Adding {col_name} to strategies table")
                        conn.execute(text(f"ALTER TABLE strategies ADD COLUMN {col_name} {col_def}"))
                
                # Config Variables
                new_config_columns = [
                    ('use_trailing_buy', "BOOLEAN DEFAULT FALSE NOT NULL"),
                    ('trailing_buy_rebound_percent', "FLOAT DEFAULT 0.2 NOT NULL"),
                    ('trailing_buy_batch', "BOOLEAN DEFAULT TRUE NOT NULL")
                ]
                for col_name, col_def in new_config_columns:
                    if col_name not in columns:
                        print(f"Migrating: Adding {col_name} to strategies table")
                        conn.execute(text(f"ALTER TABLE strategies ADD COLUMN {col_name} {col_def}"))

                # Price Segments Migration
                if 'price_segments' not in columns:
                    print(f"Migrating: Adding price_segments to strategies table")
                    conn.execute(text("ALTER TABLE strategies ADD COLUMN price_segments JSON"))

                # Manual Target Migration
                if 'manual_target_price' not in columns:
                    print(f"Migrating: Adding manual_target_price to strategies table")
                    conn.execute(text("ALTER TABLE strategies ADD COLUMN manual_target_price FLOAT"))

                conn.commit()
            except Exception as e:
                print(f"Migration warning (strategies Trailing Buy/Segments): {e}")
                columns = [row[1] for row in result.fetchall()]
                
                # List of new columns for Trailing Buy
                trailing_columns = [
                    ('is_watching', "BOOLEAN DEFAULT 0"),
                    ('watch_lowest_price', "FLOAT"),
                    ('pending_buy_units', "INTEGER DEFAULT 0")
                ]

                for col_name, col_def in trailing_columns:
                    if col_name not in columns:
                        print(f"Migrating: Adding {col_name} to strategies table (Trailing Buy)")
                        conn.execute(text(f"ALTER TABLE strategies ADD COLUMN {col_name} {col_def}"))
                
                if 'price_segments' not in columns:
                    print(f"Migrating: Adding price_segments to strategies table (Retry)")
                    conn.execute(text("ALTER TABLE strategies ADD COLUMN price_segments JSON"))

                conn.commit()
            except Exception as e:
                print(f"Migration warning (strategies Trailing Buy/Segments Retry): {e}")

            # 5. Check splits.is_accumulated (Observability Migration)
            try:
                result = conn.execute(text("PRAGMA table_info(splits)"))
                columns = [row[1] for row in result.fetchall()]
                
                observability_cols = [
                    ('is_accumulated', "BOOLEAN DEFAULT FALSE NOT NULL"),
                    ('buy_rsi', "FLOAT")
                ]
                for col_name, col_def in observability_cols:
                    if col_name not in columns:
                        print(f"Migrating: Adding {col_name} to splits table")
                        conn.execute(text(f"ALTER TABLE splits ADD COLUMN {col_name} {col_def}"))
                
                # Check trades table as well
                result = conn.execute(text("PRAGMA table_info(trades)"))
                columns = [row[1] for row in result.fetchall()]
                
                for col_name, col_def in observability_cols:
                    if col_name not in columns:
                        print(f"Migrating: Adding {col_name} to trades table")
                        conn.execute(text(f"ALTER TABLE trades ADD COLUMN {col_name} {col_def}"))

                conn.commit()
            except Exception as e:
                print(f"Migration warning (Observability): {e}")

            # 6. Check system_events (New Table)
            try:
                # We can explicitly create it if missing, but create_all usually handles it.
                # However, for migration robustness:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='system_events'"))
                if not result.fetchone():
                    print("Migrating: Creating system_events table")
                    # Let SQLAlchemy create_all handle it on next restart, or do it here?
                    # Base.metadata.create_all(self.engine) is called in __init__.
                    # So if we are running this update, the table might not exist until restart.
                    # But since this is a code update, the server will restart. 
                    # So create_all in __init__ will catch it.
                    pass
            except Exception:
                pass

            # 7. Check candle tables for utc_time
            candle_tables = ['candles_min_5', 'candles_min_60', 'candles_days']
            for table in candle_tables:
                try:
                    result = conn.execute(text(f"PRAGMA table_info({table})"))
                    columns = [row[1] for row in result.fetchall()]
                    if 'utc_time' not in columns:
                        print(f"Migrating: Adding utc_time to {table} table")
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN utc_time TEXT"))
                        conn.commit()
                except Exception as e:
                    print(f"Migration warning ({table}): {e}")

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()

    # Strategy operations
    def create_strategy(self, name: str, ticker: str, config: dict, budget: float = 1000000.0) -> Strategy:
        """Create a new strategy"""
        session = self.get_session()
        try:
            strategy = Strategy(
                name=name,
                ticker=ticker,
                budget=budget,
                **config,
                # max_trades_per_day=100, # Removed to avoid duplicate argument error
                is_running=False,
                next_split_id=1
            )
            session.add(strategy)
            session.commit()
            session.refresh(strategy)
            return strategy
        finally:
            session.close()

    def get_strategy(self, strategy_id: int) -> Strategy:
        """Get strategy by ID"""
        session = self.get_session()
        try:
            return session.query(Strategy).filter_by(id=strategy_id).first()
        finally:
            session.close()

    def get_all_strategies(self):
        """Get all strategies"""
        session = self.get_session()
        try:
            return session.query(Strategy).all()
        finally:
            session.close()

    def delete_strategy(self, strategy_id: int):
        """Delete a strategy and its splits/trades"""
        session = self.get_session()
        try:
            strategy = session.query(Strategy).filter_by(id=strategy_id).first()
            if strategy:
                session.delete(strategy)
                session.commit()
        finally:
            session.close()

    def update_strategy(self, strategy_id: int, **kwargs):
        """Alias for update_strategy_state"""
        return self.update_strategy_state(strategy_id, **kwargs)

    def update_strategy_state(self, strategy_id: int, **kwargs):
        """Update strategy state with robust error handling"""
        session = self.get_session()
        try:
            strategy = session.query(Strategy).filter_by(id=strategy_id).first()
            if strategy:
                for key, value in kwargs.items():
                    if hasattr(strategy, key):
                        try:
                            setattr(strategy, key, value)
                        except Exception as attr_e:
                            logging.error(f"❌ [DATABASE] Failed to set attribute {key}={value}: {attr_e}")
                session.commit()
            else:
                logging.warning(f"⚠️ [DATABASE] Strategy {strategy_id} not found for update")
        except Exception as e:
            logging.error(f"❌ [DATABASE] Failed to update strategy {strategy_id} state: {e}")
            session.rollback()
            raise e # Bubble up to let the caller (API) know
        finally:
            session.close()

    def update_strategy_name(self, strategy_id: int, name: str):
        """Update strategy name"""
        session = self.get_session()
        try:
            strategy = session.query(Strategy).filter_by(id=strategy_id).first()
            if strategy:
                strategy.name = name
                session.commit()
        finally:
            session.close()

    # Split operations
    def get_splits(self, strategy_id: int):
        """Get all active splits for a strategy"""
        session = self.get_session()
        try:
            return session.query(Split).filter_by(strategy_id=strategy_id).all()
        finally:
            session.close()

    def add_split(self, strategy_id: int, ticker: str, split_data: dict) -> Split:
        """Add a new split"""
        session = self.get_session()
        try:
            split = Split(strategy_id=strategy_id, ticker=ticker, **split_data)
            session.add(split)
            session.commit()
            session.refresh(split)
            return split
        finally:
            session.close()

    def update_split(self, strategy_id: int, split_id: int, **kwargs):
        """Update a split"""
        session = self.get_session()
        try:
            split = session.query(Split).filter_by(
                strategy_id=strategy_id,
                split_id=split_id
            ).first()
            if split:
                for key, value in kwargs.items():
                    if hasattr(split, key):
                        setattr(split, key, value)
                session.commit()
        finally:
            session.close()

    def delete_split(self, strategy_id: int, split_id: int):
        """Delete a split"""
        session = self.get_session()
        try:
            split = session.query(Split).filter_by(
                strategy_id=strategy_id,
                split_id=split_id
            ).first()
            if split:
                session.delete(split)
                session.commit()
        finally:
            session.close()

    def delete_all_splits(self, strategy_id: int):
        """Delete all splits for a specific strategy"""
        session = self.get_session()
        try:
            session.query(Split).filter_by(strategy_id=strategy_id).delete()
            session.commit()
        finally:
            session.close()

    def delete_all_trades(self, strategy_id: int):
        """Delete all trades for a specific strategy"""
        session = self.get_session()
        try:
            session.query(Trade).filter_by(strategy_id=strategy_id).delete()
            session.commit()
        finally:
            session.close()

    def delete_events(self, strategy_id: int):
        """Delete all system events for a strategy"""
        session = self.get_session()
        try:
            session.query(SystemEvent).filter_by(strategy_id=strategy_id).delete()
            session.commit()
        finally:
            session.close()

    # Trade operations
    def add_trade(self, strategy_id: int, ticker: str, trade_data: dict) -> Trade:
        """Add a completed trade to history"""
        session = self.get_session()
        try:
            trade = Trade(strategy_id=strategy_id, ticker=ticker, **trade_data)
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade
        finally:
            session.close()

    def get_trades(self, strategy_id: int, limit: int = None):
        """Get trade history for a strategy"""
        session = self.get_session()
        try:
            query = session.query(Trade).filter_by(strategy_id=strategy_id).order_by(Trade.timestamp.desc())
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_all_trades(self, limit: int = None):
        """Get all trades across all strategies"""
        session = self.get_session()
        try:
            query = session.query(Trade).order_by(Trade.timestamp.desc())
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def reset_all_data(self):
        """Reset all data in the database (for testing/mock mode)"""
        session = self.get_session()
        try:
            # Delete all events
            session.query(SystemEvent).delete()
            # Delete all splits
            session.query(Split).delete()
            # Delete all trades
            session.query(Trade).delete()
            # Delete all strategies
            session.query(Strategy).delete()
            # Reset mock accounts to defaults
            session.query(MockAccount).delete()
            session.add(MockAccount(currency="KRW", balance=10000000.0, avg_buy_price=0.0))
            session.query(MockOrder).delete()
            session.commit()
        finally:
            session.close()

    def reset_trading_data(self):
        """Reset active trading state but preserve strategies and trade history (for soft reset)"""
        session = self.get_session()
        try:
            # Delete all active splits (since assets are being reset)
            session.query(Split).delete()
            
            # Note: We preserve Trade history so the user can see past performance
            # session.query(Trade).delete() 
            
            # Reset strategy state (but keep config)
            strategies = session.query(Strategy).all()
            for s in strategies:
                s.is_running = False
                s.next_split_id = 1
                s.last_buy_price = None
                s.last_sell_price = None
            
            # Reset mock accounts to defaults
            session.query(MockAccount).delete()
            session.add(MockAccount(currency="KRW", balance=10000000.0, avg_buy_price=0.0))
            
            # Reset mock orders
            session.query(MockOrder).delete()
            
            session.commit()
        finally:
            session.close()

    # System Configuration operations
    def get_system_config(self) -> SystemConfig:
        """Get or create system configuration"""
        session = self.get_session()
        try:
            config = session.query(SystemConfig).first()
            if config is None:
                config = SystemConfig(mode='MOCK')
                session.add(config)
                session.commit()
                session.refresh(config)
            return config
        finally:
            session.close()

    def set_system_mode(self, mode: str, access_key: str = None, secret_key: str = None):
        """Set system mode and optionally save API keys"""
        session = self.get_session()
        try:
            config = session.query(SystemConfig).first()
            if config is None:
                config = SystemConfig()
                session.add(config)

            config.mode = mode
            if access_key:
                config.upbit_access_key = access_key
            if secret_key:
                config.upbit_secret_key = secret_key

            session.commit()
        finally:
            session.close()

    # Mock account operations
    def get_mock_account(self, currency: str, create_if_missing: bool = True) -> MockAccount:
        session = self.get_session()
        try:
            account = session.query(MockAccount).filter_by(currency=currency).first()
            if account is None and create_if_missing:
                # Default KRW balance 10M, others 0
                default_balance = 10000000.0 if currency == "KRW" else 0.0
                account = MockAccount(currency=currency, balance=default_balance, avg_buy_price=0.0)
                session.add(account)
                session.commit()
                session.refresh(account)
            return account
        finally:
            session.close()

    def get_mock_accounts(self):
        session = self.get_session()
        try:
            accounts = session.query(MockAccount).all()
            if not accounts:
                # Seed KRW if empty
                krw = MockAccount(currency="KRW", balance=10000000.0, avg_buy_price=0.0)
                session.add(krw)
                session.commit()
                session.refresh(krw)
                accounts = [krw]
            return accounts
        finally:
            session.close()

    def set_mock_balance(self, currency: str, balance: float, avg_buy_price: float = None):
        session = self.get_session()
        try:
            account = session.query(MockAccount).filter_by(currency=currency).first()
            if account is None:
                account = MockAccount(currency=currency, balance=balance, avg_buy_price=avg_buy_price or 0.0)
                session.add(account)
            else:
                account.balance = balance
                if avg_buy_price is not None:
                    account.avg_buy_price = avg_buy_price
            session.commit()
        finally:
            session.close()

    # Mock order operations
    def add_mock_order(self, order_data: dict) -> MockOrder:
        """Add a new mock order to DB"""
        session = self.get_session()
        try:
            order = MockOrder(**order_data)
            session.add(order)
            session.commit()
            session.refresh(order)
            return order
        finally:
            session.close()

    def get_mock_order(self, uuid: str) -> MockOrder:
        """Get a mock order by UUID"""
        session = self.get_session()
        try:
            return session.query(MockOrder).filter_by(uuid=uuid).first()
        finally:
            session.close()

    def get_mock_orders(self, state: str = None):
        """Get all mock orders, optionally filtered by state"""
        session = self.get_session()
        try:
            query = session.query(MockOrder)
            if state:
                query = query.filter_by(state=state)
            return query.all()
        finally:
            session.close()

    def update_mock_order(self, uuid: str, **kwargs):
        """Update a mock order"""
        session = self.get_session()
        try:
            order = session.query(MockOrder).filter_by(uuid=uuid).first()
            if order:
                for key, value in kwargs.items():
                    if hasattr(order, key):
                        setattr(order, key, value)
                session.commit()
        finally:
            session.close()

    def delete_mock_order(self, uuid: str):
        """Delete a mock order"""
        session = self.get_session()
        try:
            order = session.query(MockOrder).filter_by(uuid=uuid).first()
            if order:
                session.delete(order)
                session.commit()
        finally:
            session.close()

    # System Event Operations
    def add_event(self, strategy_id: int, level: str, event_type: str, message: str):
        """Add a system event with log rotation (max 200)"""
        session = self.get_session()
        try:
            # 1. Insert new event
            event = SystemEvent(
                strategy_id=strategy_id,
                level=level,
                event_type=event_type,
                message=message,
                # Use UTC for storage to allow consistent cross-timezone display
                timestamp=datetime.now(timezone.utc)
            )
            session.add(event)
            
            # 2. Check and rotate (Keep max 200 per strategy)
            # Optimization: Only check occasionally or check every time? 200 is small.
            count = session.query(SystemEvent).filter_by(strategy_id=strategy_id).count()
            if count > 200:
                # Delete oldest (count - 200 + buffer)
                # Let's delete excess
                num_to_delete = count - 200
                if num_to_delete > 0:
                    subq = session.query(SystemEvent.id).\
                        filter_by(strategy_id=strategy_id).\
                        order_by(SystemEvent.timestamp.asc()).\
                        limit(num_to_delete).subquery()
                    
                    session.query(SystemEvent).filter(SystemEvent.id.in_(subq)).delete(synchronize_session=False)

            session.commit()
            return event
        except Exception as e:
            print(f"Failed to add event: {e}")
            session.rollback()
        finally:
            session.close()

    def get_events(self, strategy_id: int, page: int = 1, limit: int = 10):
        """Get events with pagination"""
        session = self.get_session()
        try:
            query = session.query(SystemEvent).filter_by(strategy_id=strategy_id).order_by(SystemEvent.timestamp.desc())
            
            total = query.count()
            
            # Pagination
            offset = (page - 1) * limit
            events = query.offset(offset).limit(limit).all()
            
            return {
                "events": [{
                    "id": ev.id,
                    "event_type": ev.event_type,
                    "level": ev.level,
                    "message": ev.message,
                    "timestamp": ev.timestamp.strftime('%Y-%m-%dT%H:%M:%S') + 'Z' if ev.timestamp else None
                } for ev in events],
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        finally:
            session.close()

    def _get_candle_model(self, interval: str):
        """Map interval string to appropriate SQLAlchemy model"""
        mapping = {
            "minutes/5": CandleMinutes5,
            "minutes/60": CandleMinutes60,
            "days": CandleDays
        }
        return mapping.get(interval)

    # Candle cache operations
    def save_candles(self, ticker: str, interval: str, candle_list: list):
        """Save a list of candles to DB using UPSERT (Replace if exists)"""
        session = self.get_session()
        try:
            from sqlalchemy.dialects.sqlite import insert
            from datetime import datetime, timezone

            model = self._get_candle_model(interval)
            if not model:
                logging.warning(f"No database model for interval: {interval}")
                return

            # Prepare and Sort data by time ascending to ensure interval check works
            prepared_data = []
            for c in candle_list:
                # 1. Normalize Timestamp - Use numeric timestamp first (it's always UTC)
                ts_raw = c.get('timestamp') or c.get('time')
                if ts_raw:
                    ts = float(ts_raw)
                    if ts > 10000000000: ts /= 1000.0 # Convert MS to S
                else:
                    # Fallback to string only if numeric is missing
                    utc_str = c.get('candle_date_time_utc') or c.get('utc_time')
                    if not utc_str: continue
                    try:
                        dt_str = utc_str.replace('Z', '+00:00')
                        ts = datetime.fromisoformat(dt_str).timestamp()
                    except: continue

                # 2. Normalize to Interval Start
                if interval == "minutes/5": ts = (ts // 300) * 300
                elif interval == "minutes/60": ts = (ts // 3600) * 3600
                elif interval == "days": ts = (ts // 86400) * 86400

                prepared_data.append((ts, c))

            # Sort by timestamp ASC
            prepared_data.sort(key=lambda x: x[0])

            last_valid_ts = None
            for ts, c in prepared_data:
                opening = c.get('opening_price') or c.get('open')
                high = c.get('high_price') or c.get('high')
                low = c.get('low_price') or c.get('low')
                close = c.get('trade_price') or c.get('close') or c.get('c')
                volume = c.get('candle_acc_trade_volume') or c.get('volume') or 0.0
                kst = c.get('candle_date_time_kst') or c.get('kst_time')

                if opening is None or close is None:
                    continue

                candle_data = {
                    'ticker': ticker,
                    'timestamp': float(ts),
                    'open': float(opening),
                    'high': float(high or opening),
                    'low': float(low or opening),
                    'close': float(close),
                    'volume': float(volume),
                    'kst_time': kst,
                    'utc_time': datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
                }
                
                index_elements = ['ticker', 'timestamp']
                
                stmt = insert(model).values(**candle_data)
                # SQLite Specific: ON CONFLICT REPLACE
                stmt = stmt.on_conflict_do_update(
                    index_elements=index_elements,
                    set_={
                        'open': candle_data['open'],
                        'high': candle_data['high'],
                        'low': candle_data['low'],
                        'close': candle_data['close'],
                        'volume': candle_data['volume'],
                        'kst_time': candle_data['kst_time'],
                        'utc_time': candle_data['utc_time']
                    }
                )
                session.execute(stmt)
            
            session.commit()
            logging.info(f"✅ [DATABASE] Successfully saved {len(prepared_data)} candles for {ticker} ({interval})")
        except Exception as e:
            logging.error(f"❌ [DATABASE] Error saving candles for {ticker} ({interval}): {e}")
            import traceback
            logging.error(traceback.format_exc())
            session.rollback()
        finally:
            session.close()

    def get_candles(self, ticker: str, interval: str, start_ts: float, end_ts: float = None) -> list:
        """Fetch candles from DB for a given range"""
        session = self.get_session()
        try:
            model = self._get_candle_model(interval)
            if not model:
                return []
                
            query = session.query(model).filter(model.ticker == ticker)
            
            if start_ts:
                query = query.filter(model.timestamp >= start_ts)
            
            if end_ts:
                query = query.filter(model.timestamp <= end_ts)
            
            candles = query.order_by(model.timestamp.asc()).all()
            
            # Convert to dict for compatibility
            results = []
            for c in candles:
                from datetime import datetime, timezone
                utc_val = datetime.fromtimestamp(c.timestamp, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

                results.append({
                    'ticker': c.ticker,
                    'interval': interval, # Return requested interval
                    'timestamp': c.timestamp,
                    'open': c.open,
                    'opening_price': c.open,
                    'high': c.high,
                    'high_price': c.high,
                    'low': c.low,
                    'low_price': c.low,
                    'close': c.close,
                    'trade_price': c.close,
                    'volume': c.volume,
                    'candle_acc_trade_volume': c.volume,
                    'candle_date_time_kst': c.kst_time,
                    'candle_date_time_utc': utc_val
                })
            return results
        finally:
            session.close()


# Global database instances
_db_manager = None
_candle_db_manager = None

def get_db() -> DatabaseManager:
    """Get global strategy database manager instance (MOCK/REAL depending on ENV)"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager

def get_candle_db() -> DatabaseManager:
    """Get global market data database manager instance (Exchange DB)"""
    global _candle_db_manager
    if _candle_db_manager is None:
        # Market data default (override with CANDLE_DB_PATH in production)
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        market_db_path = os.getenv("CANDLE_DB_PATH")
        if not market_db_path:
            market_db_path = os.path.join(backend_dir, "..", "mock-exchange", "sevensplit.db")
        market_db_dir = os.path.dirname(os.path.abspath(market_db_path))
        os.makedirs(market_db_dir, exist_ok=True)
        _candle_db_manager = DatabaseManager(db_path=market_db_path)
    return _candle_db_manager
