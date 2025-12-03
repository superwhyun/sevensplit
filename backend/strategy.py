from pydantic import BaseModel
from typing import List, Optional
import logging
import json
import threading
from datetime import datetime
from database import get_db

class StrategyConfig(BaseModel):
    investment_per_split: float = 100000.0 # KRW per split
    min_price: float = 0.0 # Min Price (0.0 means uninitialized)
    max_price: float = 0.0 # Max Price (0.0 means uninitialized)
    buy_rate: float = 0.005 # 0.5% - price drop rate to trigger next buy
    sell_rate: float = 0.005 # 0.5% - profit rate for sell order
    fee_rate: float = 0.0005 # 0.05% fee
    tick_interval: float = 1.0 # seconds - how often to check prices
    rebuy_strategy: str = "reset_on_clear" # Options: "last_buy_price", "last_sell_price", "reset_on_clear"
    max_trades_per_day: int = 100 # Max trades allowed per 24 hours

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
    def __init__(self, exchange, strategy_id: int, ticker: str, budget: float = 1000000.0):
        self.exchange = exchange
        self.strategy_id = strategy_id
        self.ticker = ticker
        self.budget = budget
        self.db = get_db()
        self.config = StrategyConfig()
        self.lock = threading.RLock()
        self.splits: List[SplitState] = []
        self.is_running = False
        self.trade_history = []
        self.next_split_id = 1
        self.last_buy_price = None # Track the last buy price for creating next split
        self.last_sell_price = None # Track the last sell price for rebuy strategy

        # Load state first to see if we have existing config
        state_loaded = self.load_state()

        # Check for "bad defaults" from previous runs (e.g. BTC defaults applied to ETH/SOL)
        # Old default was 50,000,000. If we see this for non-BTC, it's likely wrong.
        has_bad_default = (self.config.min_price == 50000000.0 and self.ticker != "KRW-BTC")
        
        # If no state loaded, or we have bad defaults, or uninitialized (0.0), try to set from current price
        if not state_loaded or has_bad_default or self.config.min_price == 0.0:
            current_price = self.exchange.get_current_price(self.ticker)
            if current_price:
                # Default grid range: -15% ~ +15% around the current price
                self.config.min_price = current_price * 0.85
                self.config.max_price = current_price * 1.15
                # Ensure buy/sell rates are default 0.005 if they look wrong (optional, but requested)
                if self.config.buy_rate != 0.005:
                    self.config.buy_rate = 0.005
                if self.config.sell_rate != 0.005:
                    self.config.sell_rate = 0.005
                    
                logging.info(f"Initialized default config for {ticker} (Strategy {strategy_id}): min_price={self.config.min_price}, max_price={self.config.max_price}")
                self.save_state()

    def save_state(self):
        """Save state to database"""
        try:
            # Update strategy state
            config_dict = self.config.dict()
            self.db.update_strategy_state(
                self.strategy_id,
                investment_per_split=config_dict['investment_per_split'],
                min_price=config_dict['min_price'],
                max_price=config_dict['max_price'],
                buy_rate=config_dict['buy_rate'],
                sell_rate=config_dict['sell_rate'],
                fee_rate=config_dict['fee_rate'],
                tick_interval=config_dict['tick_interval'],
                rebuy_strategy=config_dict['rebuy_strategy'],
                max_trades_per_day=config_dict['max_trades_per_day'],
                is_running=self.is_running,
                next_split_id=self.next_split_id,
                last_buy_price=self.last_buy_price,
                last_sell_price=self.last_sell_price,
                budget=self.budget
            )

            # Sync splits to database
            db_splits = self.db.get_splits(self.strategy_id)
            db_split_ids = {s.split_id for s in db_splits}
            mem_split_ids = {s.id for s in self.splits}

            # Delete splits that are in DB but not in memory
            for split_id in db_split_ids - mem_split_ids:
                self.db.delete_split(self.strategy_id, split_id)

            # Update or add splits from memory to DB
            for split in self.splits:
                split_data = {
                    'split_id': split.id,
                    'status': split.status,
                    'buy_price': split.buy_price,
                    'target_sell_price': split.target_sell_price,
                    'investment_amount': split.buy_amount,
                    'coin_volume': split.buy_volume,
                    'buy_order_id': split.buy_order_uuid,
                    'sell_order_id': split.sell_order_uuid,
                    'buy_filled_at': datetime.fromisoformat(split.bought_at) if split.bought_at else None
                }

                if split.id in db_split_ids:
                    # For update, remove split_id from kwargs as it's already passed as argument
                    update_data = {k: v for k, v in split_data.items() if k != 'split_id'}
                    self.db.update_split(self.strategy_id, split.id, **update_data)
                else:
                    self.db.add_split(self.strategy_id, self.ticker, split_data)

        except Exception as e:
            logging.error(f"Failed to save state to database: {e}")

    def load_state(self):
        """Load state from database. Returns True if state was loaded, False otherwise."""
        try:
            # Load strategy state
            state = self.db.get_strategy(self.strategy_id)
            if not state:
                return False

            # Update config
            self.config = StrategyConfig(
                investment_per_split=state.investment_per_split,
                min_price=state.min_price,
                max_price=state.max_price,
                buy_rate=state.buy_rate,
                sell_rate=state.sell_rate,
                fee_rate=state.fee_rate,
                tick_interval=state.tick_interval,
                rebuy_strategy=state.rebuy_strategy,
                max_trades_per_day=getattr(state, 'max_trades_per_day', 100) # Default 100 if missing
            )

            self.is_running = state.is_running
            self.next_split_id = state.next_split_id
            self.last_buy_price = state.last_buy_price
            self.last_sell_price = state.last_sell_price
            self.budget = state.budget

            # Load splits
            db_splits = self.db.get_splits(self.strategy_id)
            self.splits = []
            for db_split in db_splits:
                split = SplitState(
                    id=db_split.split_id,
                    status=db_split.status,
                    buy_order_uuid=db_split.buy_order_id,
                    sell_order_uuid=db_split.sell_order_id,
                    buy_price=db_split.buy_price,
                    actual_buy_price=db_split.buy_price,  # Assuming they're the same
                    buy_amount=db_split.investment_amount,
                    buy_volume=db_split.coin_volume or 0.0,
                    target_sell_price=db_split.target_sell_price,
                    created_at=db_split.created_at.isoformat() if db_split.created_at else None,
                    bought_at=db_split.buy_filled_at.isoformat() if db_split.buy_filled_at else None
                )
                self.splits.append(split)

            # Load recent trade history for limit checking (last 200 should be enough for 24h check)
            trades = self.db.get_trades(self.strategy_id, limit=200)
            self.trade_history = []
            for t in trades:
                self.trade_history.append({
                    'split_id': t.split_id,
                    'buy_price': t.buy_price,
                    'sell_price': t.sell_price,
                    'buy_amount': t.buy_amount,
                    'sell_amount': t.sell_amount,
                    'volume': t.coin_volume,
                    'gross_profit': t.gross_profit,
                    'total_fee': t.total_fee,
                    'net_profit': t.net_profit,
                    'profit_rate': t.profit_rate,
                    'timestamp': t.timestamp.isoformat() if t.timestamp else None,
                    'bought_at': t.bought_at.isoformat() if t.bought_at else None
                })

            return True
        except Exception as e:
            logging.error(f"Failed to load state from database: {e}")
            return False

    def start(self, current_price=None):
        """Start the strategy. Create first buy order at current price."""
        with self.lock:
            # Always create the first split at current price when starting
            if current_price is None:
                current_price = self.exchange.get_current_price(self.ticker)
            if current_price and not self.splits:
                logging.info(f"Starting strategy {self.strategy_id} at current price: {current_price}")
                # Use market order for initial entry to ensure execution
                self._create_buy_split(current_price, use_market_order=True)

            self.is_running = True
            self.save_state()

    def stop(self):
        """Stop the strategy and cancel all pending orders."""
        with self.lock:
            self.is_running = False

            # Cancel all pending orders
            for split in self.splits:
                if split.status == "PENDING_BUY" and split.buy_order_uuid:
                    try:
                        self.exchange.cancel_order(split.buy_order_uuid)
                        logging.info(f"Cancelled buy order {split.buy_order_uuid} for split {split.id}")
                    except Exception as e:
                        logging.error(f"Failed to cancel buy order {split.buy_order_uuid}: {e}")
                    # Reset order info so it can be recreated on start
                    split.buy_order_uuid = None
                    
                elif split.status == "PENDING_SELL" and split.sell_order_uuid:
                    try:
                        self.exchange.cancel_order(split.sell_order_uuid)
                        logging.info(f"Cancelled sell order {split.sell_order_uuid} for split {split.id}")
                    except Exception as e:
                        logging.error(f"Failed to cancel sell order {split.sell_order_uuid}: {e}")
                    # Reset order info and revert status so it creates a new sell order on start
                    split.sell_order_uuid = None
                    split.status = "BUY_FILLED"

            self.save_state()

    def update_config(self, config: StrategyConfig):
        """Update configuration."""
        with self.lock:
            logging.info(f"Updating config for Strategy {self.strategy_id}. Old: {self.config}, New: {config}")
            self.config = config
            self.save_state()

    def check_trade_limit(self) -> bool:
        """Check if total trade actions (buys + sells) in last 24 hours is within limit"""
        if self.config.max_trades_per_day <= 0:
            return True # No limit
            
        now = datetime.now()
        one_day_ago = now.timestamp() - 86400
        recent_count = 0
        
        # 1. Count from completed trades history
        for t in self.trade_history:
            # Check Sell Time
            ts = t.get('timestamp')
            if ts:
                try:
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts)
                        ts_val = dt.timestamp()
                    else:
                        ts_val = float(ts)
                    
                    if ts_val > one_day_ago:
                        recent_count += 1
                except Exception:
                    pass

            # Check Buy Time
            bought_at = t.get('bought_at')
            if bought_at:
                try:
                    if isinstance(bought_at, str):
                        dt = datetime.fromisoformat(bought_at)
                        ba_val = dt.timestamp()
                    else:
                        ba_val = float(bought_at)
                    
                    if ba_val > one_day_ago:
                        recent_count += 1
                except Exception:
                    pass
        
        # 2. Count from active splits (Buys that haven't been sold yet)
        for split in self.splits:
            # Only count if bought (BUY_FILLED or PENDING_SELL)
            # PENDING_BUY hasn't happened yet.
            if split.status in ["BUY_FILLED", "PENDING_SELL"] and split.bought_at:
                try:
                    if isinstance(split.bought_at, str):
                        dt = datetime.fromisoformat(split.bought_at)
                        ba_val = dt.timestamp()
                    else:
                        ba_val = float(split.bought_at)
                    
                    if ba_val > one_day_ago:
                        recent_count += 1
                except Exception:
                    pass

        if recent_count >= self.config.max_trades_per_day:
            # Only log once per minute to avoid spam (TODO: Implement rate limiting for logs)
            logging.warning(f"Trade limit reached ({recent_count}/{self.config.max_trades_per_day} actions in 24h). Skipping buy.")
            return False
            
        return True

    def tick(self, current_price: float = None):
        """Main tick function called periodically to check and update splits."""
        with self.lock:
            if not self.is_running:
                return

            # Self-healing: Remove duplicate splits by ID if any exist
            unique_splits = {}
            for s in self.splits:
                if s.id not in unique_splits:
                    unique_splits[s.id] = s
                else:
                    logging.warning(f"Found duplicate split ID {s.id} in memory. Removing duplicate.")
            
            if len(unique_splits) != len(self.splits):
                self.splits = list(unique_splits.values())
                self.splits.sort(key=lambda x: x.id)

            if current_price is None:
                current_price = self.exchange.get_current_price(self.ticker)

            if not current_price:
                return

            # Check all splits for order status updates
            # Create a copy of the list to safely modify self.splits during iteration if needed
            for split in list(self.splits):
                if split.status == "PENDING_BUY":
                    if split.buy_order_uuid:
                        self._check_buy_order(split)
                    else:
                        # Zombie split (PENDING_BUY with no UUID). Remove it to allow recreation.
                        logging.info(f"Found zombie split {split.id} (PENDING_BUY with no UUID). Removing to reset.")
                        self.splits.remove(split)
                        self.save_state()

                elif split.status == "BUY_FILLED":
                    # Buy filled, create sell order
                    self._create_sell_order(split)

                elif split.status == "PENDING_SELL":
                    if split.sell_order_uuid:
                        self._check_sell_order(split)
                    else:
                        # Zombie split (PENDING_SELL with no UUID). Revert to BUY_FILLED to recreate sell order.
                        logging.info(f"Found zombie split {split.id} (PENDING_SELL with no UUID). Reverting to BUY_FILLED.")
                        split.status = "BUY_FILLED"
                        self.save_state()
                        # It will be picked up in the next tick as BUY_FILLED

            # Remove completed splits
            self._cleanup_filled_splits()

            # Check if we need to create new buy split based on price drop
            if self.check_trade_limit():
                self._check_create_new_buy_split(current_price)

    def _cleanup_filled_splits(self):
        """Remove SELL_FILLED splits and update state."""
        splits_to_remove = [s for s in self.splits if s.status == "SELL_FILLED"]
        
        for split in splits_to_remove:
            logging.info(f"Removing completed split {split.id}")
            self.splits.remove(split)
            self.save_state()

        # Update last_buy_price to the lowest buy price of remaining splits
        if splits_to_remove:
            if self.splits:
                # Find the split with the lowest buy_price
                lowest_split = min(self.splits, key=lambda s: s.buy_price)
                if self.last_buy_price != lowest_split.buy_price:
                    logging.info(f"Adjusting last_buy_price from {self.last_buy_price} to {lowest_split.buy_price} (lowest active split)")
                    self.last_buy_price = lowest_split.buy_price
                    self.save_state()
            else:
                # If no splits remain, last_buy_price will be handled by the rebuy strategy in _check_create_new_buy_split
                if self.last_buy_price is not None:
                    logging.info(f"All splits cleared. Resetting last_buy_price to None.")
                    self.last_buy_price = None
                    self.save_state()

    def _create_buy_split(self, target_price: float, use_market_order: bool = False):
        """Create a new buy split at the given target price."""
        if target_price < self.config.min_price:
            logging.warning(f"Target price {target_price} below min_price {self.config.min_price}. Skipping.")
            return None

        # Check Budget
        total_invested = sum(s.buy_amount for s in self.splits)
        if total_invested + self.config.investment_per_split > self.budget:
            logging.warning(f"Budget exceeded for Strategy {self.strategy_id}. Invested: {total_invested}, Budget: {self.budget}. Skipping buy.")
            return None

        split = SplitState(
            id=self.next_split_id,
            status="PENDING_BUY",
            buy_price=target_price,
            created_at=datetime.now().isoformat()
        )

        # Normalize price to valid tick size
        target_price = self.exchange.normalize_price(target_price)

        # Calculate volume for limit order
        amount = self.config.investment_per_split
        
        if amount < 5000:
            logging.error(f"Investment amount {amount} is less than minimum order amount (5000 KRW). Skipping.")
            return None

        # Calculate volume ensuring it meets the minimum amount (round up to 8 decimal places)
        # 1.00000001 BTC * price > amount
        import math
        volume = math.ceil((amount / target_price) * 100000000) / 100000000

        logging.info(f"Attempting buy order: {self.ticker}, Price: {target_price}, Volume: {volume}, Total: {target_price * volume}, MarketOrder: {use_market_order}")

        try:
            result = None
            if use_market_order:
                # Place market buy order (price = amount in KRW)
                result = self.exchange.buy_market_order(self.ticker, amount)
            else:
                # Place limit buy order
                result = self.exchange.buy_limit_order(self.ticker, target_price, volume)

            if result:
                split.buy_order_uuid = result.get('uuid')
                split.buy_amount = amount
                
                if use_market_order:
                    # Estimate volume for now, will be updated when filled
                    split.buy_volume = amount / target_price
                else:
                    split.buy_volume = volume
                
                # Prevent duplicate append
                if not any(s.id == split.id for s in self.splits):
                    self.splits.append(split)
                    self.next_split_id += 1
                    self.last_buy_price = target_price
                    logging.info(f"Created buy split {split.id} at {target_price} with order {split.buy_order_uuid} (Market: {use_market_order})")
                    self.save_state()
                return split
        except Exception as e:
            logging.warning(f"Failed to create buy order at {target_price}: {e}")
            # Retry logic
            if "invalid_price" in str(e) or "400" in str(e):
                logging.info(f"Retrying buy order with re-normalization...")
                try:
                    new_target_price = self.exchange.normalize_price(target_price)
                    logging.info(f"Retry normalization: {target_price} -> {new_target_price}")
                    result = self.exchange.buy_limit_order(self.ticker, new_target_price, volume)
                    if result:
                        split.buy_order_uuid = result.get('uuid')
                        split.buy_amount = amount
                        split.buy_volume = volume
                        
                        if not any(s.id == split.id for s in self.splits):
                            self.splits.append(split)
                            self.next_split_id += 1
                            self.last_buy_price = new_target_price
                            logging.info(f"Retry successful: Created buy split {split.id} at {new_target_price}")
                            self.save_state()
                        return split
                except Exception as retry_e:
                    logging.error(f"Retry failed: {retry_e}")
            return None

    def _check_buy_order(self, split: SplitState):
        """Check if buy order is filled."""
        if not split.buy_order_uuid:
            return

        # Timeout Logic: If pending for > 30 minutes (1800s), switch to market order
        if split.status == "PENDING_BUY" and split.created_at:
            try:
                created_dt = datetime.fromisoformat(split.created_at)
                elapsed = (datetime.now() - created_dt).total_seconds()
                if elapsed > 1800:  # 30 minutes timeout
                    current_price = self.exchange.get_current_price(self.ticker)
                    # Check if current price is within max_price (if set)
                    if current_price and (self.config.max_price <= 0 or current_price <= self.config.max_price):
                        logging.info(f"Buy order {split.buy_order_uuid} timed out ({elapsed:.1f}s). Switching to Market Order.")
                        try:
                            # Attempt to cancel existing limit order
                            self.exchange.cancel_order(split.buy_order_uuid)
                            
                            # Place market buy order
                            res = self.exchange.buy_market_order(self.ticker, split.buy_amount)
                            if res:
                                split.buy_order_uuid = res.get('uuid')
                                split.created_at = datetime.now().isoformat()  # Reset timer
                                logging.info(f"Placed market order {split.buy_order_uuid} for split {split.id}")
                                self.save_state()
                                return
                        except Exception as e:
                            logging.warning(f"Failed to switch to market order (cancel failed?): {e}")
            except Exception as e:
                logging.error(f"Error in buy timeout check: {e}")

        try:
            order = self.exchange.get_order(split.buy_order_uuid)
            if not order:
                return

            state = order.get('state')
            
            # Handle 'done' (Filled) OR 'cancel' (Partial Fill or Cancelled)
            if state == 'done' or state == 'cancel':
                # Check executed volume
                executed_vol = float(order.get('executed_volume', 0))
                
                if executed_vol > 0:
                    # Filled or Partially Filled -> Treat as success
                    split.status = "BUY_FILLED"
                    split.bought_at = datetime.now().isoformat()
                    
                    # Calculate actual buy price and volume from trades
                    trades = order.get('trades', [])
                    if trades:
                        total_funds = sum(float(t.get('funds', 0)) for t in trades)
                        total_volume = sum(float(t.get('volume', 0)) for t in trades)
                        if total_volume > 0:
                            split.actual_buy_price = total_funds / total_volume
                            split.buy_volume = total_volume
                        else:
                            split.actual_buy_price = float(order.get('price', split.buy_price))
                    else:
                        # No trades data (legacy or error or cancelled with partial fill but no trades info returned?)
                        # For Market Buy ('price'), order['price'] is the AMOUNT, not unit price!
                        if order.get('ord_type') == 'price':
                            paid_amount = float(order.get('price', 0)) # Target amount
                            # If cancelled, paid_amount might be the original target, but we only spent executed_vol * avg_price
                            # But we don't have avg_price easily if no trades.
                            # Try to use 'locked' or 'remaining_fee' to reverse calc? Too complex.
                            # Fallback: Use current price or split.buy_price as estimate if we can't calc
                            if executed_vol > 0:
                                 # We don't have total funds spent if no trades. 
                                 # But usually 'done' order has trades. 'cancel' might not?
                                 # Let's try to trust order['price'] if it's not market order, but this IS market order.
                                 # If we can't calculate, log warning and use target price.
                                 logging.warning(f"Market buy {state} with vol {executed_vol} but no trades data. Using target price.")
                                 split.actual_buy_price = split.buy_price 
                                 split.buy_volume = executed_vol
                            else:
                                 # Should be caught by executed_vol > 0 check, but just in case
                                 split.actual_buy_price = split.buy_price
                        else:
                            # Limit order
                            split.actual_buy_price = float(order.get('price', split.buy_price))
                            split.buy_volume = executed_vol

                    logging.info(f"Buy order {state} for split {split.id}. Price: {split.actual_buy_price}, Vol: {split.buy_volume}")
                    self.save_state()
                
                elif state == 'cancel':
                    # Cancelled with 0 executed volume -> Failed
                    logging.warning(f"Buy order {split.buy_order_uuid} was cancelled with 0 volume. Resetting split {split.id}.")
                    split.buy_order_uuid = None
                    split.status = "PENDING_BUY"
                    self.save_state()

        except Exception as e:
            # Handle 404 or "Order not found"
            error_msg = str(e)
            if "404" in error_msg or "Order not found" in error_msg:
                logging.warning(f"Buy order {split.buy_order_uuid} not found (likely mock restart). Resetting split {split.id}.")
                split.buy_order_uuid = None
                split.status = "PENDING_BUY"
                self.save_state()
            else:
                logging.error(f"Error checking buy order {split.buy_order_uuid}: {e}")

    def _create_sell_order(self, split: SplitState):
        """Create sell order after buy is filled."""
        # Calculate sell price based on sell_rate
        raw_sell_price = split.actual_buy_price * (1 + self.config.sell_rate)
        # Normalize price to valid tick size
        sell_price = self.exchange.normalize_price(raw_sell_price)
        
        # Debug log for price calculation
        tick_size = self.exchange.get_tick_size(raw_sell_price)
        logging.info(f"Sell Order Debug: Raw={raw_sell_price}, Normalized={sell_price}, TickSize={tick_size}, Ticker={self.ticker}")

        split.target_sell_price = sell_price

        try:
            # Place limit sell order
            result = self.exchange.sell_limit_order(self.ticker, sell_price, split.buy_volume)

            if result:
                split.sell_order_uuid = result.get('uuid')
                split.status = "PENDING_SELL"
                logging.info(f"Created sell order {split.sell_order_uuid} for split {split.id} at {sell_price}")
                self.save_state()
        except Exception as e:
            logging.warning(f"Failed to create sell order for split {split.id} at {sell_price}: {e}")
            # Retry logic
            if "invalid_price" in str(e) or "400" in str(e):
                logging.info(f"Retrying sell order for split {split.id} with re-normalization...")
                try:
                    sell_price = self.exchange.normalize_price(raw_sell_price)
                    result = self.exchange.sell_limit_order(self.ticker, sell_price, split.buy_volume)
                    if result:
                        split.sell_order_uuid = result.get('uuid')
                        split.status = "PENDING_SELL"
                        logging.info(f"Retry successful: Created sell order {split.sell_order_uuid} for split {split.id} at {sell_price}")
                        self.save_state()
                except Exception as retry_e:
                    logging.error(f"Retry failed for split {split.id}: {retry_e}")

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

                # Save to database
                trade_data = {
                    "split_id": split.id,
                    "buy_price": split.actual_buy_price,
                    "sell_price": actual_sell_price,
                    "coin_volume": split.buy_volume,
                    "buy_amount": buy_total,
                    "sell_amount": sell_total,
                    "gross_profit": sell_total - buy_total,
                    "total_fee": total_fee,
                    "net_profit": net_profit,
                    "profit_rate": profit_rate,
                    "buy_order_id": split.buy_order_uuid,
                    "sell_order_id": split.sell_order_uuid,
                    "bought_at": datetime.fromisoformat(split.bought_at) if split.bought_at else None
                }
                self.db.add_trade(self.strategy_id, self.ticker, trade_data)

                # Also keep in memory for quick access
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
                    "timestamp": datetime.now().isoformat(),
                    "bought_at": split.bought_at
                })

                # Removed cap of 50 to ensure trade limit check works correctly
                # if len(self.trade_history) > 50:
                #     self.trade_history.pop()

                split.status = "SELL_FILLED"
                self.last_sell_price = actual_sell_price
                logging.info(f"Sell order filled for split {split.id} at {actual_sell_price}. Net Profit: {net_profit} KRW ({profit_rate:.2f}%) after fees: {total_fee} KRW")
                self.save_state()
        except Exception as e:
            # Handle 404 or "Order not found"
            error_msg = str(e)
            if "404" in error_msg or "Order not found" in error_msg:
                logging.warning(f"Sell order {split.sell_order_uuid} not found (likely mock restart). Resetting split {split.id} to PENDING_BUY.")
                split.sell_order_uuid = None
                split.status = "PENDING_BUY"
                # Also reset buy info since we are restarting the cycle
                split.buy_order_uuid = None
                self.save_state()
            else:
                logging.error(f"Error checking sell order {split.sell_order_uuid}: {e}")

    def _check_create_new_buy_split(self, current_price: float):
        """Check if we should create a new buy split based on price drop and rebuy strategy."""

        # Check if all positions are cleared
        has_active_positions = any(
            s.status in ["PENDING_BUY", "BUY_FILLED", "PENDING_SELL"]
            for s in self.splits
        )

        # Handle different rebuy strategies when all positions are cleared
        if not has_active_positions:
            if self.config.rebuy_strategy == "reset_on_clear":
                # Strategy 1: Reset and start at current price
                logging.info(f"All positions cleared. Resetting and starting at current price: {current_price}")
                self.last_buy_price = None
                # Use market order to ensure immediate re-entry
                self._create_buy_split(current_price, use_market_order=True)
                return
            elif self.config.rebuy_strategy == "last_sell_price":
                # Strategy 2: Use last sell price as reference
                if self.last_sell_price is not None:
                    reference_price = self.last_sell_price
                    logging.info(f"All positions cleared. Using last sell price {reference_price} as reference")
                else:
                    # Fallback to current price if no sell price
                    reference_price = current_price
                    logging.info(f"No last sell price, using current price: {current_price}")

                next_buy_price = reference_price * (1 - self.config.buy_rate)
                if current_price <= next_buy_price:
                    # Buy at current price (not at next_buy_price)
                    logging.info(f"Price dropped to {current_price} (trigger: {next_buy_price}), creating buy split at current price")
                    # Use market order to ensure immediate re-entry
                    self._create_buy_split(current_price, use_market_order=True)
                return
            # Strategy 3: "last_buy_price" - continue with existing logic below

        # Standard logic for ongoing positions or "last_buy_price" strategy
        if self.last_buy_price is None:
            # No previous buy, create one at current price
            logging.info(f"No previous buy, creating first split at current price: {current_price}")
            self._create_buy_split(current_price)
            return

        # Calculate how many buy levels we've crossed
        # Count the number of levels crossed, then buy that many splits at current price
        reference_price = self.last_buy_price
        levels_crossed = 0
        temp_price = reference_price
        
        while True:
            next_level = temp_price * (1 - self.config.buy_rate)
            
            # If current price is still above the next level, we're done
            if current_price > next_level:
                break
            
            levels_crossed += 1
            temp_price = next_level
            
            # Safety limit: don't create too many splits at once
            if levels_crossed >= 10:
                logging.warning(f"Price drop too severe. Limiting to 10 buy splits.")
                break
        
        # Create multiple buy orders at current price
        if levels_crossed > 0:
            # Check if we already have a pending buy at current price
            has_pending_buy = any(
                s.status == "PENDING_BUY" and abs(s.buy_price - current_price) / current_price < 0.001
                for s in self.splits
            )
            
            if has_pending_buy:
                logging.debug(f"Already have pending buy near {current_price}, skipping")
                return
            
            logging.info(f"Price dropped from {reference_price} to {current_price}, crossed {levels_crossed} levels. Creating {levels_crossed} buy splits at {current_price}")
            
            for i in range(levels_crossed):
                split = self._create_buy_split(current_price)
                if not split:
                    # Failed to create split (e.g., insufficient balance), stop creating more
                    logging.warning(f"Failed to create buy split {i+1}/{levels_crossed} at {current_price}, stopping")
                    break
                logging.info(f"Created buy split {i+1}/{levels_crossed} at {current_price}")

    def get_state(self, current_price=None):
        with self.lock:
            if current_price is None:
                current_price = self.exchange.get_current_price(self.ticker)

            # Calculate aggregated profit for active positions
            total_invested = 0.0
            total_valuation = 0.0
            total_coin_volume = 0.0

            for split in self.splits:
                # Count splits with buy filled or pending sell as active positions
                if split.status in ["BUY_FILLED", "PENDING_SELL"]:
                    invested = split.buy_amount
                    valuation = split.buy_volume * current_price if current_price else 0
                    total_invested += invested
                    total_valuation += valuation
                    total_coin_volume += split.buy_volume

            total_profit_amount = total_valuation - total_invested
            total_profit_rate = (total_profit_amount / total_invested * 100) if total_invested > 0 else 0.0

            # Count splits by status
            status_counts = {
                "pending_buy": sum(1 for s in self.splits if s.status == "PENDING_BUY"),
                "buy_filled": sum(1 for s in self.splits if s.status == "BUY_FILLED"),
                "pending_sell": sum(1 for s in self.splits if s.status == "PENDING_SELL"),
                "sell_filled": sum(1 for s in self.splits if s.status == "SELL_FILLED")
            }

            # Get strategy name from DB (optimization: could cache this)
            strategy_name = "Unknown"
            strategy_rec = self.db.get_strategy(self.strategy_id)
            if strategy_rec:
                strategy_name = strategy_rec.name

            return {
                "id": self.strategy_id,
                "name": strategy_name,
                "ticker": self.ticker,
                "budget": self.budget,
                "is_running": self.is_running,
                "config": self.config.dict(),
                "splits": [s.dict() for s in self.splits],
                "current_price": current_price,
                "total_profit_amount": total_profit_amount,
                "total_profit_rate": total_profit_rate,
                "total_invested": total_invested,
                "total_coin_volume": total_coin_volume,
                "total_valuation": total_valuation,
                "status_counts": status_counts,
                "last_buy_price": self.last_buy_price,
                "trade_history": self.trade_history[:10] # Return last 10 trades
            }
