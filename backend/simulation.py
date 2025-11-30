from typing import List, Dict, Any
from datetime import datetime
import logging
import threading
from strategy import SevenSplitStrategy, SplitState, StrategyConfig
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
    def __init__(self):
        pass
    
    def get_current_price(self, ticker):
        return 0 # Should not be called directly in sim if we push price
    
    def normalize_price(self, price):
        # Simple mock normalization (e.g. 1000 KRW unit for Bitcoin is too rough, use 100 or 10)
        # Let's just return as is or round to 2 decimals for sim
        return round(price, 2)
    
    def get_tick_size(self, price):
        return 1000 # Dummy

    def buy_limit_order(self, ticker, price, volume):
        return {'uuid': f'sim_buy_{datetime.now().timestamp()}'}

    def sell_limit_order(self, ticker, price, volume):
        return {'uuid': f'sim_sell_{datetime.now().timestamp()}'}
    
    def cancel_order(self, uuid):
        pass
    
    def get_order(self, uuid):
        return {'state': 'wait'} # Default

class SimulationStrategy(SevenSplitStrategy):
    def __init__(self, config: StrategyConfig, budget: float):
        # Bypass super().__init__ to avoid DB/Exchange setup
        self.strategy_id = 9999
        self.ticker = "SIM-TEST"
        self.budget = budget
        self.db = MockDB()
        self.exchange = MockExchange()
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
        
        # Initialize defaults if needed (similar to SevenSplitStrategy)
        if self.config.min_price == 0.0:
            # We don't have current price yet, will set in run_simulation or first tick
            pass

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
            ts = self.current_candle['timestamp']
            if isinstance(ts, (int, float)):
                # Frontend sends Unix timestamp in seconds (UTC)
                # Use utcfromtimestamp to ensure UTC interpretation
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
            ts = self.current_candle['timestamp']
            if isinstance(ts, (int, float)):
                # Frontend sends Unix timestamp in seconds (UTC)
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


def run_simulation(sim_config: SimulationConfig):
    strategy = SimulationStrategy(sim_config.strategy_config, sim_config.budget)
    
    candles = sim_config.candles
    start_idx = sim_config.start_index
    
    if start_idx < 0 or start_idx >= len(candles):
        return {"error": "Invalid start index"}

    # Initialize strategy config if needed using the start price
    start_price = candles[start_idx].get('close') or candles[start_idx].get('trade_price')
    if strategy.config.min_price == 0.0 and start_price:
        strategy.config.min_price = start_price * 0.5 # Wide range for sim
        strategy.config.max_price = start_price * 1.5
        logging.info(f"SIM: Initialized config with min={strategy.config.min_price}, max={strategy.config.max_price}")

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
            
        strategy.current_candle = candle
        
        # 1. Tick with Low price to catch buy triggers (dips)
        # We use Low because the strategy buys when price drops.
        # If we used Close, we might miss a dip that happened during the candle.
        
        # IMPORTANT: We must check fills BEFORE creating new orders?
        # Or check fills, then tick (create orders), then check fills again?
        # Standard backtest:
        # 1. Check if pending orders match this candle's H/L
        # 2. Run strategy logic with Close price (to place new orders for NEXT candle)
        
        # Check fills first
        # We need to iterate a copy because splits might be removed
        # Check fills first
        # We REMOVED the manual loop here because strategy.tick() handles it.
        # The manual loop was bypassing the logic in strategy.tick() that updates
        # last_buy_price when splits are removed.
        # By relying on strategy.tick(), we ensure consistent behavior with the real bot.

        # Run strategy tick
        # We disable the internal _check_buy/sell calls in tick by overriding?
        # Actually SevenSplitStrategy.tick calls _check_buy_order etc.
        # Since we overrode them to use current_candle, calling tick is fine!
        # It will check fills again (redundant but harmless) and then create new orders.
        
        # 1. Determine the price to tick with
        # We want to simulate Limit Orders.
        # If we have a position, we buy at (last_buy_price * (1 - buy_rate)).
        # If the candle Low hit that price, we should trigger the strategy at that EXACT price, not the Low price.
        
        tick_price = candle['close'] # Default to close
        
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
        "splits": [s.dict() for s in strategy.splits], # Return final splits
        "config": strategy.config.dict() # Return used config
    }
