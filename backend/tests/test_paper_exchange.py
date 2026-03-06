import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exchange import PaperExchange


class _PublicStub:
    def get_tick_size(self, price):
        return 1

    def normalize_price(self, price):
        return round(price)

    def get_current_price(self, ticker="KRW-ETH"):
        return 3_088_000.0

    def get_current_prices(self, tickers):
        return {ticker: 3_088_000.0 for ticker in tickers}

    def get_candles(self, ticker, count=200, interval="minutes/5", to=None):
        return []


class TestPaperExchange(unittest.TestCase):
    def test_sell_lock_tolerates_float_rounding_for_repeated_market_buys(self):
        exchange = PaperExchange(_PublicStub(), initial_krw=10_000_000.0)

        volumes = []
        for _ in range(3):
            order = exchange.buy_market_order("KRW-ETH", 100_000.0)
            filled = exchange.get_order(order["uuid"])
            volumes.append(float(filled["executed_volume"]))

        order_ids = []
        for volume in volumes:
            result = exchange.sell_limit_order("KRW-ETH", 3_097_000.0, volume)
            order_ids.append(result["uuid"])

        self.assertEqual(len(order_ids), 3)
        self.assertEqual(exchange.balances["ETH"]["balance"], 0.0)
        self.assertAlmostEqual(exchange.balances["ETH"]["locked"], sum(volumes))


if __name__ == "__main__":
    unittest.main()
