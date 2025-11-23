from pydantic import BaseModel
from typing import List, Optional
import logging
import json
from datetime import datetime

class StrategyConfig(BaseModel):
    investment_per_split: float = 100000.0 # KRW per split
    min_price: float = 50000000.0 # Min Price (e.g., 50M KRW)
    max_price: float = 100000000.0 # Max Price (e.g., 100M KRW) - not used for buy, just reference
    buy_rate: float = 0.005 # 0.5% - price drop rate to trigger next buy
    sell_rate: float = 0.005 # 0.5% - profit rate for sell order
    fee_rate: float = 0.0005 # 0.05% fee

class SplitState(BaseModel):
    id: int
    status: str = "PENDING_BUY" # PENDING_BUY, BUY_FILLED, PENDING_SELL, SELL_FILLED
    buy_order_uuid: Optional[str] = None
    sell_order_uuid: Optional[str] = None
    buy_price: float = 0.0 # Target buy price
    actual_buy_price: float = 0.0 # Actual filled price
    buy_amount: float = 0.0 # KRW amount
    buy_volume: float = 0.0 # Coin volume
    target_sell_price: float = 0.0 # Target sell price
    created_at: Optional[str] = None
    bought_at: Optional[str] = None

class SevenSplitStrategy:
    def __init__(self, exchange, ticker="KRW-BTC"):
        self.exchange = exchange
        self.ticker = ticker
        self.config = StrategyConfig()
        self.splits: List[SplitState] = []
        self.is_running = False
        self.trade_history = []
        self.next_split_id = 1
        self.last_buy_price = None # Track the last buy price for creating next split

        # Load state first to see if we have existing config
        state_loaded = self.load_state()

        # If no state was loaded (fresh start), set default prices based on current price
        if not state_loaded:
            current_price = self.exchange.get_current_price(self.ticker)
            if current_price:
                self.config.min_price = current_price * 0.8  # 20% below current price
                self.config.max_price = current_price * 1.2  # 20% above current price
                logging.info(f"Initialized default config for {ticker}: min_price={self.config.min_price}, max_price={self.config.max_price}")
                self.save_state()

    def save_state(self):
        state = {
            "config": self.config.dict(),
            "is_running": self.is_running,
            "splits": [s.dict() for s in self.splits],
            "trade_history": self.trade_history,
            "next_split_id": self.next_split_id,
            "last_buy_price": self.last_buy_price
        }
        try:
            with open(f"state_{self.ticker}.json", "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save state: {e}")

    def load_state(self):
        """Load state from file. Returns True if state was loaded, False otherwise."""
        try:
            with open(f"state_{self.ticker}.json", "r") as f:
                state = json.load(f)
                self.config = StrategyConfig(**state.get("config", {}))
                self.is_running = state.get("is_running", False)
                self.trade_history = state.get("trade_history", [])
                self.next_split_id = state.get("next_split_id", 1)
                self.last_buy_price = state.get("last_buy_price")

                splits_data = state.get("splits", [])
                if splits_data:
                    self.splits = [SplitState(**s) for s in splits_data]
                return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logging.error(f"Failed to load state: {e}")
            return False

    def start(self):
        """Start the strategy. Create first buy order at current price."""
        self.is_running = True

        # Always create the first split at current price when starting
        current_price = self.exchange.get_current_price(self.ticker)
        if current_price and not self.splits:
            logging.info(f"Starting strategy at current price: {current_price}")
            self._create_buy_split(current_price)

        self.save_state()

    def stop(self):
        """Stop the strategy and cancel all pending orders."""
        self.is_running = False

        # Cancel all pending orders
        for split in self.splits:
            if split.status == "PENDING_BUY" and split.buy_order_uuid:
                try:
                    self.exchange.cancel_order(split.buy_order_uuid)
                    logging.info(f"Cancelled buy order {split.buy_order_uuid} for split {split.id}")
                except Exception as e:
                    logging.error(f"Failed to cancel buy order {split.buy_order_uuid}: {e}")
            elif split.status == "PENDING_SELL" and split.sell_order_uuid:
                try:
                    self.exchange.cancel_order(split.sell_order_uuid)
                    logging.info(f"Cancelled sell order {split.sell_order_uuid} for split {split.id}")
                except Exception as e:
                    logging.error(f"Failed to cancel sell order {split.sell_order_uuid}: {e}")

        self.save_state()

    def update_config(self, config: StrategyConfig):
        """Update configuration."""
        logging.info(f"Updating config. Old: {self.config}, New: {config}")
        self.config = config
        self.save_state()

    def tick(self, current_price: float = None):
        """Main tick function called periodically to check and update splits."""
        if not self.is_running:
            return

        if current_price is None:
            current_price = self.exchange.get_current_price(self.ticker)

        if not current_price:
            return

        # Check all splits for order status updates
        splits_to_remove = []

        for split in self.splits:
            if split.status == "PENDING_BUY":
                self._check_buy_order(split)

            elif split.status == "BUY_FILLED":
                # Buy filled, create sell order
                self._create_sell_order(split)

            elif split.status == "PENDING_SELL":
                self._check_sell_order(split)

            elif split.status == "SELL_FILLED":
                # Sell completed, mark for removal
                splits_to_remove.append(split)

        # Remove completed splits
        for split in splits_to_remove:
            logging.info(f"Removing completed split {split.id}")
            self.splits.remove(split)
            self.save_state()

        # Check if we need to create new buy split based on price drop
        self._check_create_new_buy_split(current_price)

    def _create_buy_split(self, target_price: float):
        """Create a new buy split at the given target price."""
        if target_price < self.config.min_price:
            logging.warning(f"Target price {target_price} below min_price {self.config.min_price}. Skipping.")
            return None

        split = SplitState(
            id=self.next_split_id,
            status="PENDING_BUY",
            buy_price=target_price,
            created_at=datetime.now().isoformat()
        )

        # Calculate volume for limit order
        amount = self.config.investment_per_split
        volume = amount / target_price

        # Place limit buy order
        result = self.exchange.buy_limit_order(self.ticker, target_price, volume)

        if result:
            split.buy_order_uuid = result.get('uuid')
            split.buy_amount = amount
            split.buy_volume = volume
            self.splits.append(split)
            self.next_split_id += 1
            self.last_buy_price = target_price
            logging.info(f"Created buy split {split.id} at {target_price} with order {split.buy_order_uuid}")
            self.save_state()
            return split
        else:
            logging.error(f"Failed to create buy order at {target_price}")
            return None

    def _check_buy_order(self, split: SplitState):
        """Check if buy order is filled."""
        if not split.buy_order_uuid:
            return

        try:
            order = self.exchange.get_order(split.buy_order_uuid)
            if order and order.get('state') == 'done':
                # Buy order filled
                split.status = "BUY_FILLED"
                split.actual_buy_price = float(order.get('price', split.buy_price))
                split.bought_at = datetime.now().isoformat()
                # Update volume with actual executed volume
                executed_volume = float(order.get('executed_volume', split.buy_volume))
                split.buy_volume = executed_volume
                logging.info(f"Buy order filled for split {split.id} at {split.actual_buy_price}")
                self.save_state()
        except Exception as e:
            logging.error(f"Error checking buy order {split.buy_order_uuid}: {e}")

    def _create_sell_order(self, split: SplitState):
        """Create sell order after buy is filled."""
        # Calculate sell price based on sell_rate
        sell_price = split.actual_buy_price * (1 + self.config.sell_rate)
        split.target_sell_price = sell_price

        # Place limit sell order
        result = self.exchange.sell_limit_order(self.ticker, sell_price, split.buy_volume)

        if result:
            split.sell_order_uuid = result.get('uuid')
            split.status = "PENDING_SELL"
            logging.info(f"Created sell order {split.sell_order_uuid} for split {split.id} at {sell_price}")
            self.save_state()
        else:
            logging.error(f"Failed to create sell order for split {split.id}")

    def _check_sell_order(self, split: SplitState):
        """Check if sell order is filled."""
        if not split.sell_order_uuid:
            return

        try:
            order = self.exchange.get_order(split.sell_order_uuid)
            if order and order.get('state') == 'done':
                # Sell order filled
                actual_sell_price = float(order.get('price', split.target_sell_price))

                # Calculate detailed profit breakdown
                buy_total = split.buy_amount
                buy_fee = buy_total * self.config.fee_rate

                sell_total = actual_sell_price * split.buy_volume
                sell_fee = sell_total * self.config.fee_rate

                total_fee = buy_fee + sell_fee
                net_profit = sell_total - buy_total - total_fee
                profit_rate = (net_profit / buy_total) * 100

                self.trade_history.insert(0, {
                    "split_id": split.id,
                    "buy_price": split.actual_buy_price,
                    "buy_amount": buy_total,
                    "sell_price": actual_sell_price,
                    "sell_amount": sell_total,
                    "volume": split.buy_volume,
                    "buy_fee": buy_fee,
                    "sell_fee": sell_fee,
                    "total_fee": total_fee,
                    "gross_profit": sell_total - buy_total,
                    "net_profit": net_profit,
                    "profit_rate": profit_rate,
                    "timestamp": datetime.now().isoformat()
                })

                if len(self.trade_history) > 50:
                    self.trade_history.pop()

                split.status = "SELL_FILLED"
                logging.info(f"Sell order filled for split {split.id} at {actual_sell_price}. Net Profit: {net_profit} KRW ({profit_rate:.2f}%) after fees: {total_fee} KRW")
                self.save_state()
        except Exception as e:
            logging.error(f"Error checking sell order {split.sell_order_uuid}: {e}")

    def _check_create_new_buy_split(self, current_price: float):
        """Check if we should create a new buy split based on price drop."""
        # Calculate what the next buy price should be
        if self.last_buy_price is None:
            # No previous buy, create one at current price
            logging.info(f"No previous buy, creating first split at current price: {current_price}")
            self._create_buy_split(current_price)
            return

        # Calculate the next buy trigger price
        next_buy_price = self.last_buy_price * (1 - self.config.buy_rate)
        logging.debug(f"Current price: {current_price}, Last buy: {self.last_buy_price}, Next buy trigger: {next_buy_price}")

        # Check if current price has dropped enough and we don't already have a pending buy at this level
        if current_price <= next_buy_price:
            # Check if there's already a pending buy near this price
            has_pending_buy = any(
                s.status == "PENDING_BUY" and abs(s.buy_price - next_buy_price) / next_buy_price < 0.001
                for s in self.splits
            )

            if not has_pending_buy:
                logging.info(f"Price dropped to {current_price}, creating new buy split at {next_buy_price}")
                self._create_buy_split(next_buy_price)
            else:
                logging.debug(f"Already have pending buy near {next_buy_price}, skipping")

    def get_state(self):
        current_price = self.exchange.get_current_price(self.ticker)

        # Calculate aggregated profit for active positions
        total_invested = 0.0
        total_valuation = 0.0

        for split in self.splits:
            # Count splits with buy filled or pending sell as active positions
            if split.status in ["BUY_FILLED", "PENDING_SELL"]:
                invested = split.buy_amount
                valuation = split.buy_volume * current_price if current_price else 0
                total_invested += invested
                total_valuation += valuation

        total_profit_amount = total_valuation - total_invested
        total_profit_rate = (total_profit_amount / total_invested * 100) if total_invested > 0 else 0.0

        # Count splits by status
        status_counts = {
            "pending_buy": sum(1 for s in self.splits if s.status == "PENDING_BUY"),
            "buy_filled": sum(1 for s in self.splits if s.status == "BUY_FILLED"),
            "pending_sell": sum(1 for s in self.splits if s.status == "PENDING_SELL"),
            "sell_filled": sum(1 for s in self.splits if s.status == "SELL_FILLED")
        }

        return {
            "ticker": self.ticker,
            "is_running": self.is_running,
            "config": self.config.dict(),
            "splits": [s.dict() for s in self.splits],
            "current_price": current_price,
            "total_profit_amount": total_profit_amount,
            "total_profit_rate": total_profit_rate,
            "total_invested": total_invested,
            "status_counts": status_counts,
            "trade_history": self.trade_history[:10] # Return last 10 trades
        }
