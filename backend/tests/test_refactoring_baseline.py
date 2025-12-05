import sys
import os
import unittest
import logging
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategy import SevenSplitStrategy, StrategyConfig

# Configure logging to capture output during tests
logging.basicConfig(level=logging.INFO)

class SimpleMockExchange:
    def __init__(self):
        self.prices = {}
        self.orders = {}
        self.balances = {"KRW": 100000000.0, "BTC": 0.0}
        self.commission_rate = 0.0005

    def set_mock_price(self, ticker, price):
        self.prices[ticker] = price

    def get_current_price(self, ticker="KRW-BTC"):
        return self.prices.get(ticker, 0)

    def get_balance(self, ticker):
        return self.balances.get(ticker, 0.0)
    
    def get_tick_size(self, price):
        if price >= 2000000: return 1000
        if price >= 1000000: return 500
        if price >= 500000: return 100
        if price >= 100000: return 50
        if price >= 10000: return 10
        if price >= 1000: return 5
        if price >= 100: return 1
        if price >= 10: return 0.1
        return 0.01

    def normalize_price(self, price):
        tick_size = self.get_tick_size(price)
        return (price // tick_size) * tick_size

    def buy_limit_order(self, ticker, price, volume):
        uuid = f"buy_{len(self.orders)}"
        cost = price * volume
        fee = cost * self.commission_rate
        
        # In a real exchange, balance is locked here. 
        # For this simple mock, we'll just check if we have enough KRW
        if self.balances["KRW"] < cost + fee:
            return {'uuid': None, 'error': 'Insufficient funds'}

        self.orders[uuid] = {
            'uuid': uuid,
            'side': 'bid',
            'price': price,
            'volume': volume,
            'state': 'wait',
            'created_at': datetime.now().isoformat(),
            'trades': []
        }
        return {'uuid': uuid}

    def sell_limit_order(self, ticker, price, volume):
        uuid = f"sell_{len(self.orders)}"
        
        if self.balances["BTC"] < volume:
             return {'uuid': None, 'error': 'Insufficient funds'}

        self.orders[uuid] = {
            'uuid': uuid,
            'side': 'ask',
            'price': price,
            'volume': volume,
            'state': 'wait',
            'created_at': datetime.now().isoformat(),
            'trades': []
        }
        return {'uuid': uuid}

    def get_order(self, uuid):
        print(f"DEBUG: get_order called for {uuid}")
        if uuid not in self.orders:
            return {'uuid': uuid, 'state': 'cancel'} # Not found
        
        order = self.orders[uuid]
        current_price = self.get_current_price("KRW-BTC") # Assume ticker
        
        # Simple matching logic
        if order['state'] == 'wait':
            if order['side'] == 'bid':
                 if current_price <= order['price']:
                    # Fill Buy
                    print(f"DEBUG: Filling BUY order {uuid}. Price: {current_price} <= {order['price']}")
                    order['state'] = 'done'
                    cost = order['price'] * order['volume']
                    fee = cost * self.commission_rate
                    self.balances["KRW"] -= (cost + fee)
                    self.balances["BTC"] += order['volume']
                    order['executed_volume'] = order['volume'] # Add this
                    order['trades'].append({'price': order['price'], 'volume': order['volume'], 'funds': cost})
                 else:
                    print(f"DEBUG: NOT Filling BUY order {uuid}. Price: {current_price} > {order['price']}")
                
            elif order['side'] == 'ask':
                 if current_price >= order['price']:
                    # Fill Sell
                    print(f"DEBUG: Filling SELL order {uuid}. Price: {current_price} >= {order['price']}")
                    order['state'] = 'done'
                    revenue = order['price'] * order['volume']
                    fee = revenue * self.commission_rate
                    self.balances["KRW"] += (revenue - fee)
                    self.balances["BTC"] -= order['volume']
                    order['executed_volume'] = order['volume'] # Add this
                    order['trades'].append({'price': order['price'], 'volume': order['volume'], 'funds': revenue})
                 else:
                    print(f"DEBUG: NOT Filling SELL order {uuid}. Price: {current_price} < {order['price']}")
                
        return order

    def cancel_order(self, uuid):
        if uuid in self.orders:
            self.orders[uuid]['state'] = 'cancel'
            return {'uuid': uuid}
        return None

    def buy_market_order(self, ticker, amount):
        uuid = f"buy_market_{len(self.orders)}"
        price = self.get_current_price(ticker)
        if price == 0: return {'uuid': None, 'error': 'No price'}
        
        volume = amount / price
        cost = amount
        fee = cost * self.commission_rate
        
        if self.balances["KRW"] < cost + fee:
            return {'uuid': None, 'error': 'Insufficient funds'}

        self.orders[uuid] = {
            'uuid': uuid,
            'side': 'bid',
            'ord_type': 'market',
            'price': price, # Executed price
            'volume': volume,
            'executed_volume': volume, # REQUIRED for strategy to recognize fill
            'state': 'done', # Market orders fill immediately in this mock
            'created_at': datetime.now().isoformat(),
            'trades': [{'price': price, 'volume': volume, 'funds': cost}]
        }
        
        self.balances["KRW"] -= (cost + fee)
        self.balances["BTC"] += volume
        
        return {'uuid': uuid}

    def get_orders(self, ticker=None, state='wait', page=1, limit=100):
        # Proactively check for fills before returning
        # This is needed because SevenSplitStrategy optimization relies on get_orders NOT returning filled orders
        current_price = self.get_current_price(ticker)
        for uuid, order in list(self.orders.items()):
            if order['state'] == 'wait':
                 # Re-use get_order logic to update status
                 self.get_order(uuid)
                 
        return [o for o in self.orders.values() if o['state'] == state]

    def get_candles(self, ticker, count=200, interval="minutes/5"):
        # Return dummy candles to satisfy RSI calculation
        # We just need a list of dicts with 'trade_price' and 'candle_date_time_kst'
        current_price = self.get_current_price(ticker)
        now = datetime.now()
        candles = []
        for i in range(count):
            # Create dummy timestamps
            candles.append({
                'trade_price': current_price,
                'candle_date_time_kst': now.isoformat() # Sorting key
            })
        return candles


class TestRefactoringBaseline(unittest.TestCase):
    def setUp(self):
        self.mock_exchange = SimpleMockExchange()
        from services.exchange_service import ExchangeService
        self.exchange_service = ExchangeService(self.mock_exchange)
        
        # Initialize Strategy with ExchangeService
        self.strategy = SevenSplitStrategy(self.exchange_service, strategy_id=1, ticker="KRW-BTC", budget=1000000.0)
        # Reset strategy state just in case (though it's a fresh instance)
        self.strategy.splits = [] 
        self.strategy.trade_history = []
        
        self.config = StrategyConfig(
            investment_per_split=100000.0,
            min_price=50000000.0,
            max_price=100000000.0,
            buy_rate=0.01, # 1% drop
            sell_rate=0.01, # 1% rise
            fee_rate=0.0005
        )
        self.strategy.update_config(self.config)

    def wait_for_status(self, split_index, target_status, max_ticks=5, price=None):
        print(f"DEBUG: Waiting for split {split_index} to be {target_status}...")
        for i in range(max_ticks):
            if len(self.strategy.splits) > split_index:
                 print(f"DEBUG: Tick {i}: Split {split_index} status is {self.strategy.splits[split_index].status}")
                 if self.strategy.splits[split_index].status == target_status:
                    return
            else:
                 print(f"DEBUG: Tick {i}: Split {split_index} not found yet")
            
            self.strategy.tick(current_price=price)
        
        # Final check
        if len(self.strategy.splits) > split_index:
             print(f"DEBUG: Split {split_index} status: {self.strategy.splits[split_index].status}, Expected: {target_status}")

    def test_complete_cycle(self):
        initial_price = 100000000.0
        self.mock_exchange.set_mock_price("KRW-BTC", initial_price)
        
        # 1. Start (should create Split 0 buy order)
        self.strategy.start(current_price=initial_price)
        self.strategy.tick(current_price=initial_price)
        
        # Wait for Split 0 to be PENDING_SELL
        self.wait_for_status(0, "PENDING_SELL", price=initial_price)
        self.assertEqual(self.strategy.splits[0].status, "PENDING_SELL")
        
        # 2. Price Drop (should create Split 1)
        drop_price = initial_price * 0.99 # 1% drop
        self.mock_exchange.set_mock_price("KRW-BTC", drop_price)
        self.strategy.tick(current_price=drop_price)
        
        # Wait for Split 1 to be PENDING_SELL (Limit order might take time to fill and then sell)
        self.wait_for_status(1, "PENDING_SELL", price=drop_price)
        self.assertEqual(self.strategy.splits[1].status, "PENDING_SELL")
        split_1_id = self.strategy.splits[1].id # Capture ID before it's removed
        
        # 3. Price Rise (should sell Split 1)
        rise_price = drop_price * 1.01 # 1% rise from drop
        self.mock_exchange.set_mock_price("KRW-BTC", rise_price)
        self.strategy.tick(current_price=rise_price)
        
        # Split 1 should be sold. Status might be SELL_FILLED or removed (if cleanup runs)
        # Let's check trade history instead, or wait for it to disappear from splits?
        # SevenSplitStrategy._cleanup_filled_splits removes SELL_FILLED splits.
        
        # Tick a few times to ensure cleanup
        for _ in range(3):
            self.strategy.tick(current_price=rise_price)
            
        # Check if we have a trade in history
        self.assertTrue(len(self.strategy.trade_history) > 0)
        last_trade = self.strategy.trade_history[-1]
        self.assertEqual(last_trade['split_id'], split_1_id)
        
        print("\nBaseline Test Passed: Cycle verified.")

if __name__ == '__main__':
    unittest.main()
