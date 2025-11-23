import unittest
from backend.strategy import SevenSplitStrategy, StrategyConfig
from backend.exchange import MockExchange

class TestSevenSplitStrategy(unittest.TestCase):
    def setUp(self):
        self.exchange = MockExchange()
        self.strategy = SevenSplitStrategy(self.exchange)
        self.strategy.start()

    def test_initial_buy(self):
        # Initial state: all empty
        self.assertEqual(self.strategy.splits[0].status, "EMPTY")
        
        # Tick with price
        self.exchange.set_mock_price(100000)
        self.strategy.tick()
        
        # Split 1 should be bought
        self.assertEqual(self.strategy.splits[0].status, "BOUGHT")
        self.assertEqual(self.strategy.splits[0].buy_price, 100000)

    def test_buy_dip(self):
        # Setup: Split 1 bought at 100000
        self.exchange.set_mock_price(100000)
        self.strategy.tick()
        
        # Drop price by 4% (config is 3%)
        self.exchange.set_mock_price(96000)
        self.strategy.tick()
        
        # Split 2 should be bought
        self.assertEqual(self.strategy.splits[1].status, "BOUGHT")
        self.assertEqual(self.strategy.splits[1].buy_price, 96000)

    def test_sell_profit(self):
        # Setup: Split 1 bought at 100000
        self.exchange.set_mock_price(100000)
        self.strategy.tick()
        
        # Increase price by 4% (config is 3%)
        self.exchange.set_mock_price(104000)
        self.strategy.tick()
        
        # Split 1 should be sold (EMPTY)
        self.assertEqual(self.strategy.splits[0].status, "EMPTY")

if __name__ == '__main__':
    unittest.main()
