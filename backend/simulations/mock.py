from datetime import datetime
import logging
import pandas as pd

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

    def get_strategy(self, strategy_id):
        # Mimic DB.get_strategy return object
        class MockStrategyState:
             def __init__(self, **entries):
                 self.__dict__.update(entries)
        if not self.strategy_state:
            return None
        return MockStrategyState(**self.strategy_state)


class MockExchange:
    def __init__(self, strategy=None):
        self.strategy = strategy
        self.orders = {} # uuid -> order_dict
        self.balance_krw = 100000000.0 # Default large balance for sim
        self.balance_coin = 0.0

    def get_balance(self, ticker="KRW"):
        if ticker == "KRW":
            return self.balance_krw
        return self.balance_coin
    
    def get_current_price(self, ticker):
        if self.strategy and self.strategy.current_candle:
            c = self.strategy.current_candle
            # Use Close price for the current tick consistency
            price = c.get('trade_price') or c.get('close') or c.get('c')
            if not price:
                 price = c.get('opening_price') or c.get('open') or c.get('o')
            if price:
                return float(price)
        else:
            logging.warning("DEBUG: get_current_price failed. No current_candle set.")
            
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

    def get_candles(self, ticker, count=200, interval="days", to=None):
        """
        Mimic Exchange.get_candles for simulation.
        Returns pre-computed daily candles from strategy cache (much faster).
        """
        if not self.strategy:
            return []

        # Get full history
        if "minutes" in interval:
             # For minute intervals, use raw candles directly (assuming sim is running with minute data)
             raw_history = self.strategy.candles
        else:
             # Default to Daily pre-computed for Days
             raw_history = self.strategy._precompute_daily_candles()
        
        # Determine strict cut-off time
        cutoff_ts = float('inf')
        
        # 1. First bound by Simulation Current Time (to prevent lookahead)
        if self.strategy.current_candle:
            c_ts = self.strategy.current_candle.get('timestamp') or self.strategy.current_candle.get('time')
            if c_ts:
                if c_ts > 10000000000: c_ts /= 1000.0
                cutoff_ts = c_ts + 60 # Allow small buffer for current candle itself to be included? 
                # Actually, current candle timestamp is usually the open time.
                # If we want to include the current candle which is "closed" effectively in simulation (we are processing it),
                # we should allow it. Upbit timestamps are Open Time.
                # If current simulation tick is "Processing 12:00 Candle", it means 12:00 candle is DONE.
                # So we should include 12:00 candle.
                # If cutoff == 12:00, and dc_ts == 12:00. dc_ts <= cutoff (True).
                # 12:05 candle > cutoff (False).
                # So +0 or +epsilon is fine. +3600 was definitely huge lookahead.
                cutoff_ts = c_ts + 1 # +1 sec to be safe against float precision
        
        # 2. Second bound by Pagination 'to' cursor (if provided)
        if to:
            try:
                # 'to' is ISO string (e.g. 2023-10-27T10:00:00)
                # Upbit 'to' excludes the candle at that exact time usually? Or includes?
                # Usually 'to' means "older than this".
                # But to be safe, we parse and use as upper bound.
                dt_to = datetime.fromisoformat(to.replace('Z', '+00:00'))
                ts_to = dt_to.timestamp()
                
                # Update cutoff if 'to' is earlier than current simulation time
                if ts_to < cutoff_ts:
                    cutoff_ts = ts_to
            except Exception as e:
                logging.warning(f"Failed to parse 'to' cursor in MockExchange: {e}")

        # Filter candles
        filtered_candles = []
        for dc in raw_history:
            dc_ts = dc.get('timestamp') or dc.get('time')
            if dc_ts:
                if dc_ts > 10000000000: dc_ts /= 1000.0
                
                # Check <= cutoff
                # Note: Upbit 'to' fetches candles BEFORE 'to'.
                # So checks should be strictly < ? 
                # Let's say <= for now to ensure overlap isn't missed, main.py handles duplicates/sorting.
                if dc_ts <= cutoff_ts: 
                    filtered_candles.append(dc)
                else:
                    break # sorted list?
            else:
                filtered_candles.append(dc)
                        
                if "minutes/15" in interval:
                    # Logic to resample 5m/1m candles to 15m
                    # This enables correct calculation of 15m RSI even if sim is running on 5m data
                    try:
                        if len(filtered_candles) >= 3:
                           # Convert to DataFrame
                           df = pd.DataFrame(filtered_candles)
                           # Ensure timestamp is datetime
                           # handle timestamp/time keys
                           df['ts_val'] = df['timestamp'].fillna(df.get('time'))
                           # Handle ms
                           df['ts_val'] = df['ts_val'].apply(lambda x: x if x < 10000000000 else x / 1000.0)
                           df['dt'] = pd.to_datetime(df['ts_val'], unit='s', utc=True)
                           df.set_index('dt', inplace=True)
                           
                           # Ensure numeric columns
                           for col in ['open', 'high', 'low', 'close', 'trade_price']:
                               if col in df.columns:
                                   df[col] = pd.to_numeric(df[col])
                               elif col == 'trade_price' and 'close' in df.columns:
                                   df['trade_price'] = df['close'] 
                                   
                           # Map keys if needed (Upbit keys are messy in sim)
                           if 'trade_price' not in df.columns and 'close' in df.columns:
                               df['trade_price'] = df['close']

                           # Resample
                           # OHLC agggregation
                           agg_dict = {
                               'open': 'first',
                               'high': 'max',
                               'low': 'min',
                               'close': 'last',
                               'trade_price': 'last'
                           }
                           # Filter only existing columns
                           agg_dict = {k:v for k,v in agg_dict.items() if k in df.columns}
                           
                           resampled = df.resample('15min').agg(agg_dict).dropna()
                           
                           # Convert back to list of dicts
                           # We need to preserve Upbit structure loosely
                           final_candles = []
                           for idx, row in resampled.iterrows():
                               c = row.to_dict()
                               c['timestamp'] = idx.timestamp()
                               c['candle_date_time_utc'] = idx.isoformat()
                               final_candles.append(c)
                               
                           return final_candles[-count:]
                    except Exception as e:
                         # Fallback to standard filtered if resampling fails (better than crash)
                         logging.warning(f"Resampling failed in MockExchange: {e}")
                         return filtered_candles[-count:]

                # Debugging Trailing Buy RSI freeze
        if "minutes/5" in interval and self.strategy and hasattr(self.strategy, 'log_message'):
             last_ts = 0
             if filtered_candles:
                 last_c = filtered_candles[-1]
                 last_ts = last_c.get('timestamp') or last_c.get('time') or 0
             self.strategy.log_message(f"MOCK CANDLES: Cutoff={cutoff_ts}, Len={len(filtered_candles)}, TopTimestamp={last_ts}", level="debug")

        # Default return for other intervals or if resampling not applicable
        return filtered_candles[-count:][::-1]
        
        # Fallback if no current_candle (shouldn't happen in loop)
        return raw_history[-count:][::-1]
    
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
            low = candle.get('low_price') or candle.get('low')
            high = candle.get('high_price') or candle.get('high')
            
            if order['ord_type'] == 'limit':
                if order['side'] == 'bid':
                    # Buy Limit: Fill if Low <= Limit Price
                    if low is not None and low <= order['price']:
                        order['state'] = 'done'
                        # Assume filled at limit price (or better? conservative: limit price)
                        order['trades'] = [{'funds': order['price'] * order['volume'], 'volume': order['volume'], 'price': order['price']}]
                elif order['side'] == 'ask':
                    # Sell Limit: Fill if High >= Limit Price
                    if high is not None and high >= order['price']:
                        order['state'] = 'done'
                        order['trades'] = [{'funds': order['price'] * order['volume'], 'volume': order['volume'], 'price': order['price']}]
        
        return order

    def get_orders(self, ticker=None, state='wait', page=1, limit=100):
        """Mock get_orders"""
        # Force check details for all wait orders to ensure passive fills are processed
        for uuid, order in list(self.orders.items()):
            if order['state'] == 'wait':
                 self.get_order(uuid) # Side-effect: updates state if filled

        return [o for o in self.orders.values() if o['state'] == state]
