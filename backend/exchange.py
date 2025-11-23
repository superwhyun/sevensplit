import pyupbit
import logging
from datetime import datetime

class Exchange:
    def get_balance(self, ticker):
        raise NotImplementedError

    def get_current_price(self, ticker):
        raise NotImplementedError

    def buy_market_order(self, ticker, amount):
        raise NotImplementedError

    def sell_market_order(self, ticker, volume):
        raise NotImplementedError

    def buy_limit_order(self, ticker, price, volume):
        raise NotImplementedError

    def sell_limit_order(self, ticker, price, volume):
        raise NotImplementedError

    def get_order(self, uuid):
        raise NotImplementedError

    def cancel_order(self, uuid):
        raise NotImplementedError

class UpbitExchange(Exchange):
    def __init__(self, access_key, secret_key):
        self.upbit = pyupbit.Upbit(access_key, secret_key)

    def get_balance(self, ticker="KRW"):
        return self.upbit.get_balance(ticker)

    def get_avg_buy_price(self, ticker):
        # ticker e.g., "KRW-BTC" -> "BTC"
        currency = ticker.split("-")[1] if "-" in ticker else ticker
        return self.upbit.get_avg_buy_price(currency)

    def get_current_price(self, ticker="KRW-BTC"):
        return pyupbit.get_current_price(ticker)

    def buy_market_order(self, ticker, amount):
        return self.upbit.buy_market_order(ticker, amount)

    def sell_market_order(self, ticker, volume):
        return self.upbit.sell_market_order(ticker, volume)

    def buy_limit_order(self, ticker, price, volume):
        return self.upbit.buy_limit_order(ticker, price, volume)

    def sell_limit_order(self, ticker, price, volume):
        return self.upbit.sell_limit_order(ticker, price, volume)

    def get_order(self, uuid):
        return self.upbit.get_order(uuid)

    def cancel_order(self, uuid):
        return self.upbit.cancel_order(uuid)

class MockExchange(Exchange):
    def __init__(self, initial_balance=10000000):
        self.balance = {"KRW": initial_balance, "BTC": 0, "ETH": 0, "SOL": 0}
        self.price = {} # ticker -> manual price override
        self.price_held = {} # ticker -> is price held
        self.orders = {} # uuid -> order info
        self.order_counter = 1

    def set_mock_price(self, ticker, price):
        self.price[ticker] = price

    def hold_price(self, ticker, hold=True):
        self.price_held[ticker] = hold

    def is_price_held(self, ticker):
        return self.price_held.get(ticker, False)

    def get_balance(self, ticker="KRW"):
        if ticker == "KRW":
            return self.balance["KRW"]
        
        # Handle "KRW-BTC" -> "BTC"
        currency = ticker.split("-")[1] if "-" in ticker else ticker
        return self.balance.get(currency, 0)

    def get_avg_buy_price(self, ticker):
        # Mock implementation: simplified, just return current price or 0
        # In a real mock, we should track weighted average. 
        # For now, let's return 0 to avoid complexity or implement simple tracking if needed.
        # Let's return 0 for now as Seven Split tracks its own buy prices per split.
        return 0

    def get_current_price(self, ticker="KRW-BTC"):
        # If price is held and a manual price is set, use it
        if self.is_price_held(ticker) and ticker in self.price:
            return self.price[ticker]

        # If not held but manual price exists, update from live
        if not self.is_price_held(ticker):
            try:
                live_price = pyupbit.get_current_price(ticker)
                self.price[ticker] = live_price
                return live_price
            except Exception as e:
                logging.error(f"Failed to fetch real price: {e}")
                return self.price.get(ticker, 100000000) # Fallback to stored or default

        # Otherwise, fetch real price from Upbit (no API key needed for public data)
        try:
            return pyupbit.get_current_price(ticker)
        except Exception as e:
            logging.error(f"Failed to fetch real price: {e}")
            return 100000000 # Fallback

    def buy_market_order(self, ticker, amount):
        current_price = self.get_current_price(ticker)
        if self.balance["KRW"] < amount:
            return None
        
        currency = ticker.split("-")[1]
        volume = amount / current_price
        fee = amount * 0.0005 # 0.05% fee
        self.balance["KRW"] -= (amount + fee)
        self.balance[currency] = self.balance.get(currency, 0) + volume
        return {"uuid": "mock_buy_uuid", "volume": volume, "price": current_price}

    def sell_market_order(self, ticker, volume):
        current_price = self.get_current_price(ticker)
        currency = ticker.split("-")[1]

        if self.balance.get(currency, 0) < volume:
            return None

        amount = volume * current_price
        fee = amount * 0.0005
        self.balance[currency] -= volume
        self.balance["KRW"] += (amount - fee)
        return {"uuid": "mock_sell_uuid", "volume": volume, "price": current_price}

    def buy_limit_order(self, ticker, price, volume):
        """Place a limit buy order"""
        currency = ticker.split("-")[1]
        amount = price * volume
        fee = amount * 0.0005
        total_cost = amount + fee

        if self.balance["KRW"] < total_cost:
            return None

        uuid = f"mock_buy_limit_{self.order_counter}"
        self.order_counter += 1

        self.orders[uuid] = {
            "uuid": uuid,
            "side": "bid",
            "ord_type": "limit",
            "price": str(price),
            "state": "wait",
            "market": ticker,
            "created_at": datetime.now().isoformat(),
            "volume": str(volume),
            "remaining_volume": str(volume),
            "reserved_fee": str(fee),
            "remaining_fee": str(fee),
            "paid_fee": "0",
            "locked": str(total_cost),
            "executed_volume": "0",
            "trades_count": 0
        }

        # Reserve the KRW
        self.balance["KRW"] -= total_cost

        return self.orders[uuid]

    def sell_limit_order(self, ticker, price, volume):
        """Place a limit sell order"""
        currency = ticker.split("-")[1]

        if self.balance.get(currency, 0) < volume:
            return None

        uuid = f"mock_sell_limit_{self.order_counter}"
        self.order_counter += 1

        self.orders[uuid] = {
            "uuid": uuid,
            "side": "ask",
            "ord_type": "limit",
            "price": str(price),
            "state": "wait",
            "market": ticker,
            "created_at": datetime.now().isoformat(),
            "volume": str(volume),
            "remaining_volume": str(volume),
            "reserved_fee": "0",
            "remaining_fee": "0",
            "paid_fee": "0",
            "locked": str(volume),
            "executed_volume": "0",
            "trades_count": 0
        }

        # Lock the currency
        self.balance[currency] -= volume

        return self.orders[uuid]

    def get_order(self, uuid):
        """Get order status. In mock, we auto-fill orders based on current price"""
        if uuid not in self.orders:
            return None

        order = self.orders[uuid]

        # Auto-fill logic for mock: check if price condition is met
        if order["state"] == "wait":
            current_price = self.get_current_price(order["market"])
            order_price = float(order["price"])

            filled = False
            if order["side"] == "bid" and current_price <= order_price:
                # Buy order filled
                filled = True
            elif order["side"] == "ask" and current_price >= order_price:
                # Sell order filled
                filled = True

            if filled:
                currency = order["market"].split("-")[1]
                volume = float(order["volume"])
                amount = order_price * volume
                fee = amount * 0.0005

                if order["side"] == "bid":
                    # Buy filled: add currency
                    self.balance[currency] = self.balance.get(currency, 0) + volume
                else:
                    # Sell filled: add KRW (already deducted currency when order placed)
                    self.balance["KRW"] += (amount - fee)

                order["state"] = "done"
                order["remaining_volume"] = "0"
                order["executed_volume"] = order["volume"]
                order["paid_fee"] = str(fee)
                order["trades_count"] = 1

        return order

    def cancel_order(self, uuid):
        """Cancel an order and return reserved funds"""
        if uuid not in self.orders:
            return None

        order = self.orders[uuid]

        if order["state"] != "wait":
            return None

        currency = order["market"].split("-")[1]

        if order["side"] == "bid":
            # Return reserved KRW
            locked = float(order["locked"])
            self.balance["KRW"] += locked
        else:
            # Return locked currency
            volume = float(order["volume"])
            self.balance[currency] = self.balance.get(currency, 0) + volume

        order["state"] = "cancel"
        return order
