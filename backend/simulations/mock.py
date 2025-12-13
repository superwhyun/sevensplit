from datetime import datetime
import logging

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
            
            # Try to get Open and Close
            open_price = c.get('opening_price') or c.get('open') or c.get('o')
            close_price = c.get('trade_price') or c.get('close') or c.get('c')
            
            if open_price is not None and close_price is not None:
                return (float(open_price) + float(close_price)) / 2
            
            # Fallback
            price = close_price or open_price
            
            # DEBUG LOG: Check what keys are available if price is 0 or None
            if not price:
                logging.warning(f"DEBUG: get_current_price failed. Candle keys: {list(c.keys())}, Candle: {c}")
            
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

    def get_candles(self, ticker, count=200, interval="days"):
        """
        Mimic Exchange.get_candles for simulation.
        Returns pre-computed daily candles from strategy cache (much faster).
        """
        if not self.strategy:
            return []

        # Get full history
        daily_candles = self.strategy._precompute_daily_candles()
        
        # Filter based on current simulation time
        if self.strategy.current_candle:
            # Get current simulation timestamp
            current_ts = self.strategy.current_candle.get('timestamp') or self.strategy.current_candle.get('time')
            
            if current_ts:
                # Handle ms/sec differences
                if current_ts > 10000000000: current_ts /= 1000.0
                
                # Filter: Include candles where timestamp <= current_ts
                # Note: daily_candles must have 'timestamp' added in _precompute_daily_candles
                filtered_candles = []
                for dc in daily_candles:
                    dc_ts = dc.get('timestamp')
                    if dc_ts:
                        if dc_ts > 10000000000: dc_ts /= 1000.0
                        
                        # Use a small buffer (e.g. +86400) or check strictly
                        if dc_ts <= current_ts + 3600: # allow some clock skew or exact match
                            filtered_candles.append(dc)
                        else:
                            break # sorted list, so we can stop
                    else:
                        filtered_candles.append(dc)
                        
                return filtered_candles[-count:]
        
        # Fallback if no current_candle (shouldn't happen in loop)
        return daily_candles[-count:]
    
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
