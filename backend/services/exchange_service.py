import logging

class ExchangeService:
    def __init__(self, exchange):
        self.exchange = exchange

    def get_current_price(self, ticker):
        return self.exchange.get_current_price(ticker)

    def get_current_prices(self, tickers):
        if hasattr(self.exchange, "get_current_prices"):
            return self.exchange.get_current_prices(tickers)
        # Fallback for exchanges that don't support batch fetch
        return {t: self.exchange.get_current_price(t) for t in tickers}

    def get_balance(self, currency):
        return self.exchange.get_balance(currency)

    def get_order(self, uuid):
        return self.exchange.get_order(uuid)

    def get_orders(self, ticker=None, state='wait'):
        return self.exchange.get_orders(ticker, state)

    def cancel_order(self, uuid):
        return self.exchange.cancel_order(uuid)

    def buy_limit_order(self, ticker, price, volume):
        return self.exchange.buy_limit_order(ticker, price, volume)

    def buy_market_order(self, ticker, amount):
        return self.exchange.buy_market_order(ticker, amount)

    def sell_limit_order(self, ticker, price, volume):
        return self.exchange.sell_limit_order(ticker, price, volume)

    def sell_market_order(self, ticker, volume):
        return self.exchange.sell_market_order(ticker, volume)

    def get_candles(self, ticker, count=200, interval="minutes/5"):
        return self.exchange.get_candles(ticker, count, interval)

    def normalize_price(self, price):
        # Some exchanges might not have this method exposed directly or named differently
        if hasattr(self.exchange, "normalize_price"):
            return self.exchange.normalize_price(price)
        return price

    def get_tick_size(self, price):
        if hasattr(self.exchange, "get_tick_size"):
            return self.exchange.get_tick_size(price)
        return 0
