"""Database managers for strategy, candle cache, and realtime price data."""

import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base,
    PriceBase,
    CandleDays,
    CandleMinutes5,
    CandleMinutes60,
    PriceTick,
    Split,
    Strategy,
    SystemEvent,
    Trade,
)


class DatabaseManager:
    """Database manager for SevenSplit bot"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Check environment variable first
            env_db_path = os.getenv("DB_PATH")
            if env_db_path:
                db_path = env_db_path
            else:
                # Default to backend directory
                db_filename = os.path.join("database", "sevensplit.db")
                backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(backend_dir, db_filename)

        self.db_path = db_path
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)
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

                # Next Buy Target Migration
                if 'next_buy_target_price' not in columns:
                    print("Migrating: Adding next_buy_target_price to strategies table")
                    conn.execute(text("ALTER TABLE strategies ADD COLUMN next_buy_target_price FLOAT"))
                    if 'manual_target_price' in columns:
                        conn.execute(
                            text(
                                "UPDATE strategies "
                                "SET next_buy_target_price = manual_target_price "
                                "WHERE manual_target_price IS NOT NULL "
                                "AND next_buy_target_price IS NULL"
                            )
                        )

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

                if 'next_buy_target_price' not in columns:
                    print("Migrating: Adding next_buy_target_price to strategies table (Retry)")
                    conn.execute(text("ALTER TABLE strategies ADD COLUMN next_buy_target_price FLOAT"))

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


class PriceDatabaseManager:
    """Dedicated database manager for realtime price ticks."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.getenv("PRICE_DB_PATH") or os.path.join(backend_dir, "database", "price_data.db")

        self.db_path = db_path
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)
        print(f"Using Price Database: {self.db_path}")
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)

        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()

        PriceBase.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.ttl_days = int(os.getenv("PRICE_TICK_TTL_DAYS", "7"))
        self._last_prune_ts = 0.0

    def get_session(self) -> Session:
        return self.SessionLocal()

    def save_prices(self, prices: dict, source: str = "upbit"):
        """Persist current ticker prices as tick rows."""
        if not prices:
            return

        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)
            rows = []
            for ticker, price in prices.items():
                if price is None:
                    continue
                try:
                    rows.append(
                        PriceTick(
                            ticker=str(ticker),
                            price=float(price),
                            source=source,
                            captured_at=now,
                        )
                    )
                except Exception:
                    continue

            if rows:
                session.add_all(rows)
                session.commit()
                self._prune_old_ticks_if_needed()
        except Exception as e:
            logging.error(f"❌ [PRICE_DB] Failed to save prices: {e}")
            session.rollback()
        finally:
            session.close()

    def _prune_old_ticks_if_needed(self):
        """Prune old price ticks periodically based on TTL days."""
        if self.ttl_days <= 0:
            return

        import time
        now_ts = time.time()
        # Run prune at most once per 10 minutes.
        if now_ts - self._last_prune_ts < 600:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)
        session = self.get_session()
        try:
            deleted = (
                session.query(PriceTick)
                .filter(PriceTick.captured_at < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            self._last_prune_ts = now_ts
            if deleted > 0:
                logging.info(f"[PRICE_DB] Pruned {deleted} old ticks (TTL={self.ttl_days}d)")
        except Exception as e:
            logging.error(f"[PRICE_DB] Failed to prune old ticks: {e}")
            session.rollback()
        finally:
            session.close()
