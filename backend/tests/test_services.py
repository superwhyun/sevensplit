import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import MagicMock
from services.exchange_service import ExchangeService
from services.strategy_service import StrategyService
from models.strategy_state import StrategyConfig

class MockExchange:
    def get_current_price(self, ticker):
        return 100000.0
    def get_orders(self, ticker=None, state='wait'):
        return []
    def cancel_order(self, uuid):
        pass

class MockDB:
    def get_all_strategies(self):
        return []
    def create_strategy(self, name, ticker, budget, config):
        mock_s = MagicMock()
        mock_s.id = 1
        mock_s.ticker = ticker
        mock_s.budget = budget
        return mock_s
    def delete_strategy(self, strategy_id):
        pass

class TestServices(unittest.TestCase):
    def setUp(self):
        self.mock_exchange = MockExchange()
        self.exchange_service = ExchangeService(self.mock_exchange)
        self.mock_db = MockDB()
        self.strategy_service = StrategyService(self.mock_db, self.exchange_service)

    def test_exchange_service_delegation(self):
        price = self.exchange_service.get_current_price("KRW-BTC")
        self.assertEqual(price, 100000.0)

    def test_strategy_service_lifecycle(self):
        # Create
        config = StrategyConfig().model_dump()
        s_id = self.strategy_service.create_strategy("Test", "KRW-BTC", 1000000.0, config)
        self.assertEqual(s_id, 1)
        self.assertIn(1, self.strategy_service.strategies)
        
        # Get
        strategy = self.strategy_service.get_strategy(1)
        self.assertIsNotNone(strategy)
        self.assertEqual(strategy.ticker, "KRW-BTC")
        
        # Start
        self.strategy_service.start_strategy(1)
        self.assertTrue(strategy.is_running)
        
        # Stop
        self.strategy_service.stop_strategy(1)
        self.assertFalse(strategy.is_running)
        
        # Delete
        self.strategy_service.delete_strategy(1)
        self.assertNotIn(1, self.strategy_service.strategies)

if __name__ == '__main__':
    unittest.main()
