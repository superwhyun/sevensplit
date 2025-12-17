
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from strategy import SevenSplitStrategy
from models.strategy_state import StrategyConfig, SplitState

class TestObservability(unittest.TestCase):
    def setUp(self):
        self.mock_exchange = MagicMock()
        self.mock_db = MagicMock()
        
        # Patch get_db to return our mock
        patcher = patch('strategy.get_db', return_value=self.mock_db)
        self.mock_get_db = patcher.start()
        self.addCleanup(patcher.stop)
        
        # Ensure load_state returns False (no existing state) to avoid Pydantic validation errors on Mocks
        self.mock_db.get_strategy.return_value = None
        
        # Configure Exchange Mock to return valid price
        self.mock_exchange.get_current_price.return_value = 10000.0
        self.mock_exchange.normalize_price.side_effect = lambda x: float(x) # Simply return float
        self.mock_exchange.buy_limit_order.return_value = {'uuid': 'mock-buy-uuid'}
        self.mock_exchange.get_balance.return_value = 10000000.0
        
        self.strategy = SevenSplitStrategy(self.mock_exchange, 1, "KRW-BTC")
        self.strategy.budget = 10000000.0 # Set sufficient budget
        self.strategy.config.use_trailing_buy = True
        self.strategy.config.trailing_buy_rebound_percent = 1.0 # 1%
        self.strategy.config.buy_rate = 0.01 # 1%
        self.strategy.last_buy_price = 10000.0
        self.strategy.is_running = True
        
        # Add a dummy existing split so it treats as "Active Positions"
        self.strategy.splits = [
            SplitState(id=1, status="BUY_FILLED", buy_price=10000.0, buy_amount=100000.0)
        ]
        self.strategy.next_split_id = 2
        
        # Mock get_rsi_5m to return a safe value
        self.strategy.get_rsi_5m = MagicMock(return_value=40.0)

    def test_trailing_buy_accumulation_stats(self):
        # 1. Start Watching (Drop 2%)
        # Next buy level: 10000 * 0.99 = 9900
        # Drop to 9800 (>1% drop)
        self.strategy.tick(current_price=9800.0)
        
        self.assertTrue(self.strategy.is_watching)
        self.assertEqual(self.strategy.watch_lowest_price, 9800.0)
        # Pending Units calculation: (10000 - 9800) / (10000 * 0.01) = 200 / 100 = 2 units
        self.assertEqual(self.strategy.pending_buy_units, 2)
        
        # 2. Update Low (Drop further to 9700)
        self.strategy.tick(current_price=9700.0)
        self.assertEqual(self.strategy.watch_lowest_price, 9700.0)
        # Pending Units: (10000 - 9700) / 100 = 3 units
        self.assertEqual(self.strategy.pending_buy_units, 3)
        
        # 3. Rebound (Rise to 9800)
        # Rebound target: 9700 * 1.01 = 9797
        # 9800 > 9797 -> Trigger Buy!
        
        # Mock _create_buy_split to check arguments
        with patch.object(self.strategy, '_create_buy_split') as mock_create_split:
            self.strategy.tick(current_price=9800.0)
            
            # Assert _create_buy_split called 3 times
            self.assertEqual(mock_create_split.call_count, 3)
            
            # Check arguments of the last call
            args, kwargs = mock_create_split.call_args
            
            # Verify is_accumulated=True
            self.assertTrue(kwargs.get('is_accumulated'), "is_accumulated should be True")
            
            # Verify buy_rsi=40.0
            self.assertEqual(kwargs.get('buy_rsi'), 40.0, "buy_rsi should be 40.0")
            
            print("Verfication Successful: Trailing Buy triggered with is_accumulated=True and correct RSI.")

if __name__ == '__main__':
    unittest.main()
