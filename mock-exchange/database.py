"""
Database module for SevenSplit trading bot.
Uses SQLite with SQLAlchemy ORM.
"""

from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timezone
import json
import os
import logging

Base = declarative_base()

class StrategyState(Base):
    """Strategy configuration and runtime state"""
    __tablename__ = 'strategy_states'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)

    # Configuration
    investment_per_split = Column(Float, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    buy_rate = Column(Float, nullable=False)
    sell_rate = Column(Float, nullable=False)
    fee_rate = Column(Float, nullable=False)
    tick_interval = Column(Float, nullable=False, default=1.0)
    rebuy_strategy = Column(String(50), nullable=False)

    # Runtime state
    is_running = Column(Boolean, default=False)
    next_split_id = Column(Integer, default=1)
    last_buy_price = Column(Float, nullable=True)
    last_sell_price = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Split(Base):
    """Active trading splits"""
    __tablename__ = 'splits'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    split_id = Column(Integer, nullable=False)  # Strategy-specific ID

    status = Column(String(20), nullable=False)  # PENDING_BUY, BUY_FILLED, PENDING_SELL
    buy_price = Column(Float, nullable=False)
    target_sell_price = Column(Float, nullable=False)
    investment_amount = Column(Float, nullable=False)
    coin_volume = Column(Float, nullable=True)

    # Order IDs
    buy_order_id = Column(String(100), nullable=True)
    sell_order_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    buy_filled_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Trade(Base):
    """Completed trade history"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
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

    # Order IDs
    buy_order_id = Column(String(100), nullable=True)
    sell_order_id = Column(String(100), nullable=True)

    # Timestamps
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


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
            # Default to backend directory
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(backend_dir, "sevensplit.db")

        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        
        # Enable WAL mode for better concurrency
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()

        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()

    # Strategy State operations
    def get_strategy_state(self, ticker: str) -> StrategyState:
        """Get or create strategy state for a ticker"""
        session = self.get_session()
        try:
            state = session.query(StrategyState).filter_by(ticker=ticker).first()
            if state is None:
                # Create default state
                state = StrategyState(
                    ticker=ticker,
                    investment_per_split=100000.0,
                    min_price=0.0,
                    max_price=999999999.0,
                    buy_rate=0.005,
                    sell_rate=0.005,
                    fee_rate=0.0005,
                    tick_interval=1.0,
                    rebuy_strategy="reset_on_clear",
                    is_running=False,
                    next_split_id=1
                )
                session.add(state)
                session.commit()
                session.refresh(state)
            return state
        finally:
            session.close()

    def update_strategy_state(self, ticker: str, **kwargs):
        """Update strategy state"""
        session = self.get_session()
        try:
            state = session.query(StrategyState).filter_by(ticker=ticker).first()
            if state:
                for key, value in kwargs.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
                session.commit()
        finally:
            session.close()

    # Split operations
    def get_splits(self, ticker: str):
        """Get all active splits for a ticker"""
        session = self.get_session()
        try:
            return session.query(Split).filter_by(ticker=ticker).all()
        finally:
            session.close()

    def add_split(self, ticker: str, split_data: dict) -> Split:
        """Add a new split"""
        session = self.get_session()
        try:
            split = Split(ticker=ticker, **split_data)
            session.add(split)
            session.commit()
            session.refresh(split)
            return split
        finally:
            session.close()

    def update_split(self, ticker: str, split_id: int, **kwargs):
        """Update a split"""
        session = self.get_session()
        try:
            split = session.query(Split).filter_by(
                ticker=ticker,
                split_id=split_id
            ).first()
            if split:
                for key, value in kwargs.items():
                    if hasattr(split, key):
                        setattr(split, key, value)
                session.commit()
        finally:
            session.close()

    def delete_split(self, ticker: str, split_id: int):
        """Delete a split"""
        session = self.get_session()
        try:
            split = session.query(Split).filter_by(
                ticker=ticker,
                split_id=split_id
            ).first()
            if split:
                session.delete(split)
                session.commit()
        finally:
            session.close()

    def delete_all_splits(self, ticker: str):
        """Delete all splits for a specific ticker"""
        session = self.get_session()
        try:
            session.query(Split).filter_by(ticker=ticker).delete()
            session.commit()
        finally:
            session.close()

    def delete_all_trades(self, ticker: str):
        """Delete all trades for a specific ticker"""
        session = self.get_session()
        try:
            session.query(Trade).filter_by(ticker=ticker).delete()
            session.commit()
        finally:
            session.close()

    # Trade operations
    def add_trade(self, ticker: str, trade_data: dict) -> Trade:
        """Add a completed trade to history"""
        session = self.get_session()
        try:
            trade = Trade(ticker=ticker, **trade_data)
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade
        finally:
            session.close()

    def get_trades(self, ticker: str, limit: int = None):
        """Get trade history for a ticker"""
        session = self.get_session()
        try:
            query = session.query(Trade).filter_by(ticker=ticker).order_by(Trade.timestamp.desc())
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_all_trades(self, limit: int = None):
        """Get all trades across all tickers"""
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
            # Delete all splits
            session.query(Split).delete()
            # Delete all trades
            session.query(Trade).delete()
            # Reset mock accounts to defaults
            session.query(MockAccount).delete()
            session.add(MockAccount(currency="KRW", balance=10000000.0, avg_buy_price=0.0))
            # Reset strategy states to default
            for state in session.query(StrategyState).all():
                state.is_running = False
                state.next_split_id = 1
                state.last_buy_price = None
                state.last_sell_price = None
            session.query(MockOrder).delete()
            session.commit()
        finally:
            session.close()

    def reset_trading_data(self):
        """Reset active trading state but preserve strategies and trade history (for soft reset)"""
        session = self.get_session()
        try:
            # Delete all active splits
            session.query(Split).delete()
            
            # Preserve Trade history
            # session.query(Trade).delete()
            
            # Reset strategy state (but keep config)
            # ... (StrategyState reset logic if needed, but mock exchange doesn't really manage this)
            
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
    def _get_candle_model(self, interval: str):
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
                return

            # Prepare and Sort data by time ascending
            prepared_data = []
            for c in candle_list:
                # 1. Normalize Timestamp - Use numeric timestamp first
                ts_raw = c.get('timestamp') or c.get('time')
                if ts_raw:
                    ts = float(ts_raw)
                    if ts > 10000000000: ts /= 1000.0
                else:
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
        except Exception as e:
            print(f"Error saving candles: {e}")
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
            
            # Convert to dict for compatibility with Upbit API format
            results = []
            for c in candles:
                # Always ignore stored utc_val and use timestamp for truth
                from datetime import datetime, timezone
                utc_val = datetime.fromtimestamp(c.timestamp, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
                
                results.append({
                    'market': c.ticker,
                    'candle_date_time_kst': c.kst_time,
                    'candle_date_time_utc': utc_val,
                    'opening_price': c.open,
                    'high_price': c.high,
                    'low_price': c.low,
                    'trade_price': c.close,
                    'candle_acc_trade_volume': c.volume,
                    'unit': 5,
                    'timestamp': int(c.timestamp * 1000), # ms for API compliance
                    'ticker': c.ticker,
                    'interval': interval
                })
            return results
        finally:
            session.close()


# Global database instance
_db_manager = None

def get_db() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
