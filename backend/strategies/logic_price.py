import logging

class PriceStrategyLogic:
    def __init__(self, strategy):
        self.strategy = strategy

    def tick(self, current_price: float, open_order_uuids: set):
        """Original Price Grid Strategy Logic"""
        self.strategy._manage_orders(open_order_uuids)

        # Check if we need to create new buy split based on price drop
        if self.strategy.check_trade_limit():
            self.strategy._check_create_new_buy_split(current_price)
