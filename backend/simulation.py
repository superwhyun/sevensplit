from typing import List, Dict, Any
from datetime import datetime
import logging
import threading
from strategy import SevenSplitStrategy
from strategies import SplitState, StrategyConfig, PriceStrategyLogic, RSIStrategyLogic
from pydantic import BaseModel

class SimulationConfig(BaseModel):
    strategy_config: StrategyConfig
    candles: List[Dict[str, Any]] # {timestamp, open, high, low, close}
    start_index: int
    ticker: str = "KRW-BTC"
    budget: float = 1000000.0

class MockDB:
    def __init__(self):
        self.trades = []
        self.splits = []
        self.strategy_state = {}

    def add_trade(self, strategy_id, ticker, trade_data):
        # Assign a fake ID
        trade_data['id'] = len(self.trades) + 1
        if 'timestamp' not in trade_data:
            trade_data['timestamp'] = datetime.now()
        self.trades.append(trade_data)

    def get_trades(self, strategy_id, limit=None):
        return self.trades

    def add_split(self, strategy_id, ticker, split_data):
        self.splits.append(split_data)

    def update_split(self, strategy_id, split_id, **kwargs):
        for s in self.splits:
            if s['split_id'] == split_id:
                s.update(kwargs)

    def delete_split(self, strategy_id, split_id):
        self.splits = [s for s in self.splits if s['split_id'] != split_id]

    def update_strategy_state(self, strategy_id, **kwargs):
        self.strategy_state.update(kwargs)

    def get_splits(self, strategy_id):
        # Return list of objects with attributes to mimic SQLAlchemy objects
        class MockSplitObj:
            def __init__(self, **entries):
                self.__dict__.update(entries)
        return [MockSplitObj(**s) for s in self.splits]

class MockExchange:
    def __init__(self, strategy=None):
        self.strategy = strategy
        self.orders = {} # uuid -> order_dict
        self.balance_krw = 100000000.0 # Default large balance for sim
        self.balance_coin = 0.0
    
    def get_current_price(self, ticker):
        if self.strategy and self.strategy.current_candle:
            return self.strategy.current_candle.get('trade_price', 0)
        return 0
    
    def normalize_price(self, price):
        # Simple mock normalization (e.g. 1000 KRW unit for Bitcoin is too rough, use 100 or 10)
        # Let's just return as is or round to 2 decimals for sim
        return round(price, 2)
    
    def get_tick_size(self, price):
        return 1000 # Dummy

    def buy_limit_order(self, ticker, price, volume):
        uuid = f'sim_buy_{datetime.now().timestamp()}_{len(self.orders)}'
        self.orders[uuid] = {
            'uuid': uuid,
            'side': 'bid',
            'ord_type': 'limit',
            'price': price,
            'volume': volume,
            'state': 'wait',
            'created_at': datetime.now().isoformat(),
            'trades': []
        }
        return {'uuid': uuid}

    def buy_market_order(self, ticker, amount):
        uuid = f'sim_buy_market_{datetime.now().timestamp()}_{len(self.orders)}'
        # Market order fills immediately at current close price (approximation)
        price = self.get_current_price(ticker)
        volume = amount / price if price > 0 else 0
        
        self.orders[uuid] = {
            'uuid': uuid,
            'side': 'bid',
            'ord_type': 'price', # Upbit market buy type
            'price': amount, # For market buy, price is the amount in KRW
            'volume': volume,
            'state': 'done',
            'created_at': datetime.now().isoformat(),
            'trades': [{'funds': amount, 'volume': volume, 'price': price}]
        }
        return {'uuid': uuid}

    def sell_limit_order(self, ticker, price, volume):
        uuid = f'sim_sell_{datetime.now().timestamp()}_{len(self.orders)}'
        self.orders[uuid] = {
            'uuid': uuid,
            'side': 'ask',
            'ord_type': 'limit',
            'price': price,
            'volume': volume,
            'state': 'wait',
            'created_at': datetime.now().isoformat(),
            'trades': []
        }
        return {'uuid': uuid}
    
    def sell_market_order(self, ticker, volume):
        uuid = f'sim_sell_market_{datetime.now().timestamp()}_{len(self.orders)}'
        price = self.get_current_price(ticker)
        funds = price * volume
        
        self.orders[uuid] = {
            'uuid': uuid,
            'side': 'ask',
            'ord_type': 'market',
            'price': price,
            'volume': volume,
            'state': 'done',
            'created_at': datetime.now().isoformat(),
            'trades': [{'funds': funds, 'volume': volume, 'price': price}]
        }
        return {'uuid': uuid}
    
    def cancel_order(self, uuid):
        if uuid in self.orders:
            self.orders[uuid]['state'] = 'cancel'
    
    def get_order(self, uuid):
        if uuid not in self.orders:
            return {'uuid': uuid, 'state': 'cancel', 'trades': []} # Not found
            
        order = self.orders[uuid]
        
        # If already done or cancel, return as is
        if order['state'] in ['done', 'cancel']:
            return order
            
        # Check if limit order can be filled based on current candle
        if self.strategy and self.strategy.current_candle:
            candle = self.strategy.current_candle
            low = candle.get('low_price')
            high = candle.get('high_price')
            
            if order['ord_type'] == 'limit':
                if order['side'] == 'bid':
                    # Buy Limit: Fill if Low <= Limit Price
                    if low <= order['price']:
                        order['state'] = 'done'
                        # Assume filled at limit price (or better? conservative: limit price)
                        order['trades'] = [{'funds': order['price'] * order['volume'], 'volume': order['volume'], 'price': order['price']}]
                elif order['side'] == 'ask':
                    # Sell Limit: Fill if High >= Limit Price
                    if high >= order['price']:
                        order['state'] = 'done'
                        order['trades'] = [{'funds': order['price'] * order['volume'], 'volume': order['volume'], 'price': order['price']}]
        
        return order

    def get_orders(self, ticker=None, state='wait', page=1, limit=100):
        """Mock get_orders"""
        return [o for o in self.orders.values() if o['state'] == state]

    def get_candles(self, ticker, count=200, interval="minutes/5"):
        """Return candles from the simulation history up to the current time."""
        if not self.strategy or not self.strategy.candles or not self.strategy.current_candle:
            return []
            
        current_ts = self.strategy.current_candle.get('timestamp')
        if not current_ts:
            return []
            
        # Filter candles: timestamp <= current_ts
        # Assuming candles are sorted by timestamp
        # We can just iterate or slice if we knew the index.
        # But get_candles might request a different count or interval?
        # For RSI simulation, we assume the interval matches the simulation interval.
        
        # Filter
        filtered = []
        for c in self.strategy.candles:
            # Try to get timestamp in order of preference: timestamp, time, candle_date_time_kst
            c_ts = c.get('timestamp') or c.get('time') or c.get('candle_date_time_kst')
            
            # Ensure we are comparing same types. 
            # current_ts is likely from current_candle['timestamp'] or 'candle_date_time_kst'
            # If current_ts is string, c_ts should be string.
            
            if not c_ts or not current_ts:
                continue
                
            # If types mismatch, try to convert to string
            if type(c_ts) != type(current_ts):
                c_ts = str(c_ts)
                current_ts = str(current_ts)
                
            if c_ts <= current_ts:
                filtered.append(c)
            else:
                # Since sorted, we can break early? 
                # Be careful if not sorted. But main.py sorts them.
                break
                
        # Return last 'count' candles
        return filtered[-count:]


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
        self.peak_price = None
        
        # Sim specific
        self.current_candle = None
        
        # Logic Modules
        self.price_logic = PriceStrategyLogic(self)
        self.rsi_logic = RSIStrategyLogic(self)
        
        # Initialize defaults if needed (similar to SevenSplitStrategy)
        if self.config.min_price == 0.0:
            # We don't have current price yet, will set in run_simulation or first tick
            pass

    def check_trade_limit(self) -> bool:
        """Bypass trade limit for simulation"""
        return True

    def save_state(self):
        pass # Do nothing

    def load_state(self):
        return False

    # Override check methods to use current_candle
    def _check_buy_order(self, split: SplitState):
        if not split.buy_order_uuid:
            return

        # Check if Low price hit the buy price
        # Assuming buy_price is the limit price
        if self.current_candle['low'] <= split.buy_price:
            split.status = "BUY_FILLED"
            split.actual_buy_price = split.buy_price # Assume filled at limit
            # Convert timestamp to ISO string for Pydantic model
            # The timestamp from frontend is already in Unix seconds (UTC)
            ts = self.current_candle.get('timestamp')
            if isinstance(ts, (int, float)):
                # Frontend sends Unix timestamp in seconds (UTC)
                # Upbit API sends timestamp in milliseconds
                if ts > 10000000000: # Heuristic for milliseconds (year 2286)
                    ts = ts / 1000.0
                dt = datetime.utcfromtimestamp(ts)
                split.bought_at = dt.isoformat()
            else:
                split.bought_at = str(ts)
            # Volume is already set
            # logging.info(f"SIM: Buy filled for split {split.id} at {split.actual_buy_price}")

    def _check_sell_order(self, split: SplitState):
        if not split.sell_order_uuid:
            return

        # Check if High price hit the sell price
        if self.current_candle['high'] >= split.target_sell_price:
            # Sell filled
            actual_sell_price = split.target_sell_price # Assume filled at limit
            
            buy_total = split.buy_amount
            buy_fee = buy_total * self.config.fee_rate
            
            sell_total = actual_sell_price * split.buy_volume
            sell_fee = sell_total * self.config.fee_rate
            
            total_fee = buy_fee + sell_fee
            net_profit = sell_total - buy_total - total_fee
            profit_rate = (net_profit / buy_total) * 100
            
            # Add to mock DB
            # Convert timestamp to datetime object for consistency
            # Convert timestamp to datetime object for consistency
            ts = self.current_candle.get('timestamp')
            if isinstance(ts, (int, float)):
                # Frontend sends Unix timestamp in seconds (UTC)
                # Upbit API sends timestamp in milliseconds
                if ts > 10000000000: # Heuristic for milliseconds
                    ts = ts / 1000.0
                sell_datetime = datetime.utcfromtimestamp(ts)
            else:
                sell_datetime = datetime.now()
            
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
                "bought_at": split.bought_at
            })
            
            split.status = "SELL_FILLED"
            self.last_sell_price = actual_sell_price
            # logging.info(f"SIM: Sell filled for split {split.id} at {actual_sell_price}")


def run_simulation(sim_config: SimulationConfig):    # Initialize Strategy
    strategy = SimulationStrategy(sim_config.strategy_config, sim_config.budget, sim_config.candles)
    
    candles = sim_config.candles
    start_idx = sim_config.start_index
    
    if start_idx < 0 or start_idx >= len(candles):
        return {"error": "Invalid start index"}

    # Initialize strategy config if needed using the start price
    sim_logs = []
    start_price = candles[start_idx].get('close') or candles[start_idx].get('trade_price')
    msg = f"SIM: Start Price: {start_price}, Start Index: {start_idx}/{len(candles)}"
    logging.info(msg)
    sim_logs.append(msg)
    
    if strategy.config.min_price == 0.0 and start_price:
        strategy.config.min_price = start_price * 0.5 # Wide range for sim
        strategy.config.max_price = start_price * 1.5
        msg = f"SIM: Initialized config with min={strategy.config.min_price}, max={strategy.config.max_price}"
        logging.info(msg)
        sim_logs.append(msg)
    else:
        msg = f"SIM: Config min={strategy.config.min_price}, max={strategy.config.max_price}, mode={strategy.config.strategy_mode}"
        logging.info(msg)
        sim_logs.append(msg)

    # Run simulation loop
    # We iterate from start_idx to the end
    for i in range(start_idx, len(candles)):
        candle = candles[i]
        # Normalize candle keys if needed (assuming frontend sends {t, o, h, l, c})
        # Map frontend keys to what we need. Frontend usually sends: x (time), y ([o, h, l, c])
        # Or we define the API to accept structured objects.
        
        # Normalize candle keys: frontend sends 'time', backend expects 'timestamp'
        if 'time' in candle and 'timestamp' not in candle:
            candle['timestamp'] = candle['time']
            
        # Normalize Upbit keys to standard keys
        if 'opening_price' in candle:
            candle['open'] = candle['opening_price']
        if 'high_price' in candle:
            candle['high'] = candle['high_price']
        if 'low_price' in candle:
            candle['low'] = candle['low_price']
        if 'trade_price' in candle:
            candle['close'] = candle['trade_price']
            
        strategy.current_candle = candle
        
        # Run strategy tick
        # We disable the internal _check_buy/sell calls in tick by overriding?
        # Actually SevenSplitStrategy.tick calls _check_buy_order etc.
        # Since we overrode them to use current_candle, calling tick is fine!
        # It will check fills again (redundant but harmless) and then create new orders.
        
        # 1. Determine the price to tick with
        tick_price = candle['close'] # Default to close

        if strategy.config.strategy_mode != "RSI":
            # Price Grid Logic (Classic)
            if strategy.last_buy_price is None:
                # First buy: Buy at Open of the starting candle
                tick_price = candle['open']
            else:
                # Subsequent buys
                next_buy_price = strategy.last_buy_price * (1 - strategy.config.buy_rate)
                if candle['low'] <= next_buy_price:
                    # Price dropped enough to trigger buy
                    # We tick at the target price so the order is placed at that price
                    tick_price = next_buy_price
                else:
                    # Price didn't drop enough, just update with close
                    tick_price = candle['close']

        # 2. Run strategy tick
        # This will:
        # - Check fills for EXISTING orders (using current_candle H/L)
        # - Create NEW orders if tick_price triggers them
        strategy.tick(current_price=tick_price)
        
        # 3. Intra-candle processing
        # Handle state transitions that can happen within the same candle:
        # PENDING_BUY -> BUY_FILLED -> PENDING_SELL -> SELL_FILLED
        
        # Pass 1: Check fills for PENDING_BUY (both existing and newly created)
        for split in list(strategy.splits):
            if split.status == "PENDING_BUY":
                strategy._check_buy_order(split)
        
        # Pass 2: Create sell orders for BUY_FILLED (just filled above or in tick)
        for split in list(strategy.splits):
            if split.status == "BUY_FILLED":
                strategy._create_sell_order(split)
                
        # Pass 3: Check fills for PENDING_SELL (existing or newly created)
        for split in list(strategy.splits):
            if split.status == "PENDING_SELL":
                strategy._check_sell_order(split)
                
        # Cleanup any splits that were filled in this candle (Pass 2 or Pass 3)
        strategy._cleanup_filled_splits()
        
        # Check if we need to create new buy split (e.g. if we sold everything and need to reset)
        # Only for Price Grid strategy. RSI strategy handles its own buy logic.
        if strategy.config.strategy_mode != "RSI":
            strategy._check_create_new_buy_split(tick_price)

    # Collect results
    trades = strategy.db.trades
    total_profit = sum(t['net_profit'] for t in trades)
    trade_count = len(trades)
    
    return {
        "trades": trades,
        "total_profit": total_profit,
        "trade_count": trade_count,
        "final_balance": strategy.budget + total_profit, # Simple approx
        "splits": [s.model_dump() for s in strategy.splits], # Return final splits
        "config": strategy.config.model_dump(), # Return used config
        "debug_logs": sim_logs
    }
