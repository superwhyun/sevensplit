from typing import List, Dict, Any
from datetime import datetime, timezone
import logging
import threading
import pandas as pd

from strategy import SevenSplitStrategy
from strategies import SplitState, StrategyConfig, PriceStrategyLogic, RSIStrategyLogic
from strategies.logic_watch import WatchModeLogic
from .mock import MockDB, MockExchange

class SimulationStrategy(SevenSplitStrategy):
    def __init__(self, config: StrategyConfig, budget: float, candles: List[Dict[str, Any]]):
        # Bypass super().__init__ to avoid DB/Exchange setup
        self.strategy_id = 9999
        self.ticker = "SIM-TEST"
        self.budget = budget
        self.candles = candles
        self.db = MockDB()
        self.exchange = MockExchange(strategy=self)
        self.config = config
        self.lock = threading.RLock() # Lock needed for parent class methods
        self.splits: List[SplitState] = []
        self.is_running = True
        self.trade_history = []
        self.next_split_id = 1
        self.last_buy_price = None
        self.last_sell_price = None
        self.last_buy_date = None
        self.last_sell_date = None
        
        # Risk & Trailing
        self.is_watching = False
        self.watch_lowest_price = None

        # Logic Components (The new Refactored Core)
        self.price_logic = PriceStrategyLogic(self)
        self.rsi_logic = RSIStrategyLogic(self)
        self.watch_logic = WatchModeLogic(self)
        
        # Sim specific
        self.current_candle = None
        
        # Trailing Buy State (Mirrors SevenSplitStrategy)
        self.is_watching = False
        self.watch_lowest_price = None
        self.pending_buy_units = 0
        self.manual_target_price = None

        # Pre-computed daily candles cache for RSI calculation
        self._daily_candles_cache = None
        
        # Initialize start_time (needed for some logic, though less relevant in sim)
        import time
        self.start_time = time.time()
        self.initial_rsi_delay = 0
        
        # Missing attributes from SevenSplitStrategy
        self._insufficient_funds_until = 0
        self.MIN_ORDER_AMOUNT_KRW = 5000
        self.ORDER_TIMEOUT_SEC = 1800
        self.RSI_UPDATE_INTERVAL_SEC = 1800
        
        # Captured events during simulation
        self.sim_events = []

        # Initialize defaults if needed (similar to SevenSplitStrategy)
        if self.config.min_price == 0.0:
            pass

    def get_current_time_kst(self):
        """Override to use simulation candle timestamp instead of system time."""
        from datetime import datetime, timezone, timedelta
        KST = timezone(timedelta(hours=9))

        if self.current_candle:
            ts = self.current_candle.get('timestamp')
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        if ts > 10000000000:
                            ts = ts / 1000.0
                        dt_utc = datetime.fromtimestamp(ts, timezone.utc)
                        return dt_utc.astimezone(KST)
                    elif isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        return dt.astimezone(KST)
                except Exception:
                    pass

        # Fallback to parent implementation (real time)
        return super().get_current_time_kst()

    def log_event(self, level: str, event_type: str, message: str):
        """
        Override parent log_event to capture events for simulation result
        and avoid writing to real database.
        """
        # 1. Console Log
        self.log_message(f"[{event_type}] {message}", level=level.lower())
        
        # 2. Capture for simulation output
        event_time = self.get_current_time_kst()
        self.sim_events.append({
            "created_at": event_time.isoformat() if event_time else None,
            "level": level,
            "event_type": event_type,
            "message": message
        })

    def _precompute_daily_candles(self):
        """
        Pre-compute all daily candles from hourly simulation data once at initialization.
        This avoids repeated resample operations during simulation loop.
        """
        if self._daily_candles_cache is not None:
            return self._daily_candles_cache

        if not self.candles:
            self._daily_candles_cache = []
            return []

        try:
            # Create DataFrame from ALL candles
            df = pd.DataFrame(self.candles)

            # Normalize columns
            rename_map = {
                'opening_price': 'open', 'high_price': 'high', 'low_price': 'low', 'trade_price': 'close',
                'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close'
            }
            df = df.rename(columns=rename_map)

            # Ensure numeric
            for col in ['open', 'high', 'low', 'close']:
                if col in df.columns:
                    df[col] = df[col].astype(float)

            # Handle Timestamp
            if 'timestamp' in df.columns:
                if df['timestamp'].iloc[-1] > 10000000000:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df = df.set_index('timestamp')
            elif 'time' in df.columns:
                if df['time'].iloc[-1] > 10000000000:
                    df['time'] = pd.to_datetime(df['time'], unit='ms')
                else:
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                df = df.set_index('time')
            elif 'candle_date_time_kst' in df.columns:
                df.index = pd.to_datetime(df['candle_date_time_kst'])

            # Resample to Daily
            df_daily = df.resample('D').agg({
                'open': lambda x: x.iloc[0] if not x.empty else None,
                'high': 'max',
                'low': 'min',
                'close': lambda x: x.iloc[-1] if not x.empty else None
            }).dropna()

            # Handle edge case: df_daily might be a Series
            if isinstance(df_daily, pd.Series):
                if isinstance(df_daily.index, pd.DatetimeIndex):
                    df_daily = df_daily.to_frame()
                else:
                    ts = df_daily.name
                    df_daily = df_daily.to_frame().T
                    if ts:
                        df_daily.index = [ts]

            # Convert to list of dicts
            result = []
            if isinstance(df_daily, pd.DataFrame):
                for dt, row in df_daily.iterrows():
                    if not isinstance(dt, (pd.Timestamp, datetime)):
                        try:
                            dt = pd.to_datetime(dt)
                        except:
                            continue

                    dt_kst = dt + pd.Timedelta(hours=9)

                    # Helper to extract scalar
                    def get_scalar(val):
                        if isinstance(val, pd.Series):
                            val = val.iloc[0]
                        if hasattr(val, 'item'):
                            return float(val.item())
                        return float(val)

                    result.append({
                        'opening_price': get_scalar(row['open']),
                        'high_price': get_scalar(row['high']),
                        'low_price': get_scalar(row['low']),
                        'trade_price': get_scalar(row['close']),
                        'timestamp': dt.timestamp(),
                        'candle_date_time_kst': dt_kst.strftime('%Y-%m-%dT%H:%M:%S')
                    })

            self._daily_candles_cache = result
            return result

        except Exception as e:
            logging.error(f"Failed to precompute daily candles: {e}")
            import traceback
            traceback.print_exc()
            self._daily_candles_cache = []
            return []

    def tick(self, current_price: float = None, open_orders: list = None, market_context: dict = None):
        """
        Common tick logic (cleanup, get open orders).
        Subclasses should call super().tick() and then run their logic, OR
        we can structure it as template method.
        Here we just do common setup and return the open_orders set for subclass to use.
        """
        with self.lock:
            if not self.is_running:
                return None

            # Self-healing: Remove duplicate splits by ID if any exist
            unique_splits = {}
            for s in self.splits:
                if s.id not in unique_splits:
                    unique_splits[s.id] = s
                else:
                    logging.warning(f"Found duplicate split ID {s.id} in memory. Removing duplicate.")

            if len(unique_splits) != len(self.splits):
                self.splits = list(unique_splits.values())
                self.splits.sort(key=lambda x: x.id)

            if current_price is None:
                current_price = self.exchange.get_current_price(self.ticker)

            if not current_price:
                return None

            # Prepare open orders list (Common)
            open_order_uuids = set()
            try:
                if open_orders is not None:
                    open_order_uuids = {order['uuid'] for order in open_orders}
                else:
                    fetched_orders = self.exchange.get_orders(ticker=self.ticker, state='wait')
                    if fetched_orders:
                        open_order_uuids = {order['uuid'] for order in fetched_orders}
            except Exception as e:
                logging.error(f"Failed to process open orders: {e}")
                return None
            
            # 1. Manage Orders (Check fills, creation of sells, cleanups)
            self._manage_orders(open_order_uuids)

            # 2. Dispatch via WatchModeLogic (to handle RSI + Buying Logic)
            self.watch_logic.run_tick(current_price, market_context=market_context)

            return open_order_uuids

    def check_trade_limit(self) -> bool:
        """Bypass trade limit for simulation"""
        return True

    def save_state(self):
        pass # Do nothing

    def load_state(self):
        return False



    # Override check methods to use current_candle from MockExchange's aggregated candle
    def _check_buy_order(self, split: SplitState):
        if not split.buy_order_uuid:
            return

        # Check order status from exchange first (Handles Market Orders)
        order = self.exchange.get_order(split.buy_order_uuid)
        is_filled = False
        
        if order and order.get('state') == 'done':
            is_filled = True
            # For market orders or filled limits, use order price/volume if available
            # But MockExchange returns simple trades, let's just stick to simulation price logic 
            # OR use executed details if we trust MockExchange completely.
            # Let's simple simulation logic: if done, it's done.
        elif self.current_candle['close'] <= split.buy_price:
             # Limit hit simulation (using Close)
             is_filled = True

        if is_filled:
            split.status = "BUY_FILLED"
            # User request: Trade at 5m Close Price
            split.actual_buy_price = float(self.current_candle['close']) 
            ts = self.current_candle.get('timestamp')
            if isinstance(ts, (int, float)):
                if ts > 10000000000:
                    ts = ts / 1000.0
                dt = datetime.fromtimestamp(ts, timezone.utc)
                split.bought_at = dt.isoformat()
            else:
                split.bought_at = str(ts)

    def _check_sell_order(self, split: SplitState):
        if not split.sell_order_uuid:
            return

        # Check order status from exchange first
        order = self.exchange.get_order(split.sell_order_uuid)
        if not order:
            return

        is_filled = False
        actual_sell_price = 0.0

        if order.get('ord_type') == 'market':
            if order.get('state') == 'done':
                is_filled = True
                actual_sell_price = float(order.get('price', 0))
        else:
            if split.target_sell_price and self.current_candle['close'] >= split.target_sell_price:
                is_filled = True
                # User request: Trade at 5m Close Price
                actual_sell_price = float(self.current_candle['close'])

        if is_filled:
            # Safety check for NaN propagation
            if actual_sell_price <= 0 or not split.buy_volume:
                logging.warning(f"SIM: Invalid sell params for split {split.id}. Price: {actual_sell_price}, Vol: {split.buy_volume}")
                return

            buy_total = split.buy_amount
            buy_fee = buy_total * self.config.fee_rate
            
            sell_total = actual_sell_price * split.buy_volume
            sell_fee = sell_total * self.config.fee_rate
            
            total_fee = buy_fee + sell_fee
            net_profit = sell_total - buy_total - total_fee
            
            if buy_total > 0:
                profit_rate = (net_profit / buy_total) * 100
            else:
                profit_rate = 0.0
            
            ts = self.current_candle.get('timestamp')
            if isinstance(ts, (int, float)):
                if ts > 10000000000:
                    ts = ts / 1000.0
                sell_datetime = datetime.fromtimestamp(ts, timezone.utc)
            else:
                sell_datetime = datetime.now(timezone.utc)
            
            self.db.add_trade(self.strategy_id, self.ticker, {
                "split_id": split.id,
                "buy_price": split.actual_buy_price,
                "sell_price": actual_sell_price,
                "coin_volume": split.buy_volume,
                "buy_amount": buy_total,
                "sell_amount": sell_total,
                "gross_profit": sell_total - buy_total,
                "total_fee": total_fee,
                "net_profit": net_profit,
                "profit_rate": profit_rate,
                "timestamp": sell_datetime,
                "bought_at": split.bought_at,
                "is_accumulated": split.is_accumulated,
                "buy_rsi": split.buy_rsi
            })
            
            split.status = "SELL_FILLED"
            self.last_sell_price = actual_sell_price
