import logging
import time
import math
from datetime import datetime, timezone, timedelta
from models.strategy_state import SplitState

from .logic_watch import WatchModeLogic

class PriceStrategyLogic:
    def __init__(self, strategy):
        self.strategy = strategy
        # self.watch_logic is now accessible via self.strategy.watch_logic
        self._insufficient_funds_until = 0

    def execute_buy_logic(self, current_price: float, rsi_5m: float, just_exited_watch: bool = False, market_context: dict = None):
        """
        Execute core buy logic.
        Called by WatchModeLogic after passing safety checks.

        just_exited_watch: If True, buy immediately at current price (WATCH_END trigger)
        """
        # 1. Guard: Check Budget & Trade Limits
        if not self.strategy.has_sufficient_budget(market_context=market_context):
             msg = "Price Logic: Buy skipped due to insufficient budget."
             logging.info(msg)
             self.strategy.last_status_msg = msg
             return
        if not self.strategy.check_trade_limit():
             msg = "Price Logic: Buy skipped due to trade limit (24h)."
             logging.info(msg)
             self.strategy.last_status_msg = msg
             return

        # Check active positions
        active_splits = [s for s in self.strategy.splits if s.status in ["PENDING_BUY", "BUY_FILLED", "PENDING_SELL"]]
        has_active_positions = len(active_splits) > 0

        # Determine the target price for the NEXT buy
        target_price = None
        reference_msg = ""
        is_grid_buy = False
        levels_crossed = 1

        # --- PRIORITY: Manual Target Overrides All ---
        if self.strategy.manual_target_price is not None:
            target_price = self.strategy.manual_target_price
            reference_msg = "Manual Override Target"
        elif just_exited_watch:
            # WATCH_END: Buy immediately at current price
            target_price = current_price
            reference_msg = "Watch Mode Exit - Rebound Confirmed"
            if has_active_positions and self.strategy.last_buy_price:
                is_grid_buy = True  # Treat as grid buy for proper next target calculation
        elif not has_active_positions:
            # --- CASE A: EMPTY POSITION ---
            min_price = self.strategy.config.min_price
            max_price = self.strategy.config.max_price

            if current_price < min_price:
                msg = f"Price Logic: Current price {current_price} below min_price {min_price}"
                logging.debug(msg)
                self.strategy.last_status_msg = msg
                return
            if max_price > 0 and current_price > max_price:
                msg = f"Price Logic: Current price {current_price} above max_price {max_price}"
                logging.debug(msg)
                self.strategy.last_status_msg = msg
                return

            if self.strategy.config.rebuy_strategy == "reset_on_clear":
                 target_price = current_price
                 reference_msg = "Initial Entry (Reset on Clear)"
            elif self.strategy.config.rebuy_strategy == "last_sell_price":
                 ref_price = self.strategy.last_sell_price if self.strategy.last_sell_price else current_price
                 target_price = ref_price * (1 - self.strategy.config.buy_rate)
                 reference_msg = f"Rebuy from Last Sell {ref_price}"
        else:
            # --- CASE B: ACTIVE POSITION ---
            if self.strategy.last_buy_price is None:
                 target_price = current_price
                 reference_msg = "Safety Entry (No last_buy_price)"
            else:
                 target_price = self.strategy.last_buy_price * (1 - self.strategy.config.buy_rate)
                 reference_msg = f"Grid Level from {self.strategy.last_buy_price}"
                 is_grid_buy = True

        # Execution check
        if target_price is not None:
             # STRICT CHECK: Even if exiting watch mode, price MUST be below target
             if current_price <= target_price:
                  if not self.validate_buy(current_price):
                       msg = f"Price Logic: Buy at {current_price} blocked by validation : {self.strategy.last_status_msg}"
                       logging.info(msg)
                       self.strategy.last_status_msg = msg
                       return

                  if is_grid_buy:
                      levels_crossed = self._calculate_levels_crossed(self.strategy.last_buy_price, current_price)
                      # Respect the 'batch buy' configuration
                      if not self.strategy.config.trailing_buy_batch and levels_crossed > 1:
                          levels_crossed = 1

                  next_target = current_price * (1 - self.strategy.config.buy_rate)
                  msg = (f"Buy Executed.\n"
                         f"- Condition: {reference_msg}.\n"
                         f"- Current Price: {current_price}\n"
                         f"- Buy Target Was: {target_price:.1f}\n" 
                         f"- Next Buy Target: {next_target:.1f}")

                  # Batch Buy Logic: Create orders for each level crossed
                  created_count = 0
                  log_details = []
                  
                  for i in range(levels_crossed):
                      # Buy at the current market price
                      split = self._execute_single_buy(current_price, buy_rsi=rsi_5m)
                      if split:
                          created_count += 1
                          log_details.append(f"Split #{split.id}: Entry @ {current_price:.1f}")
                      else:
                          break

                  if created_count > 0:
                      # Next target is Buy Rate below the ACTUAL price we just bought at
                      final_next_target = current_price * (1 - self.strategy.config.buy_rate)
                      
                      msg = (f"Buy Executed ({'Grid' if is_grid_buy else 'Initial'}).\n"
                             f"- Condition: {reference_msg}\n"
                             f"- Market Price: {current_price:.1f}\n")
                      
                      if log_details:
                          msg += "- " + "\n- ".join(log_details) + "\n"
                          
                      msg += f"- Next Buy Target: {final_next_target:.1f}"
                      
                      self.strategy.log_event("INFO", "BUY_EXEC", msg)
                      # --- CLEAR MANUAL TARGET AFTER EXECUTION ---
                      if self.strategy.manual_target_price is not None:
                          self.strategy.set_manual_target(None)
             else:
                  # Current price is HIGHER than target
                  msg = f"Price Logic: Price ({current_price}) is currently ABOVE target ({target_price:.1f}). Waiting for dip."
                  logging.info(msg)
                  self.strategy.last_status_msg = msg
        else:
             logging.debug("Price Logic: No valid buy target price set.")

    def manage_active_positions(self, open_order_uuids: set):
        """
        Handle strategy-specific order life-cycle:
        1. Convert timed-out Limit Buys to Market Buys
        2. Create Sell orders for filled Buys
        """
        for split in list(self.strategy.splits):
            # 1. Buy Order Timeout (Limit -> Market)
            if split.status == "PENDING_BUY" and split.buy_order_uuid:
                if self._check_buy_timeout(split, open_order_uuids):
                    # Market conversion handled inside _check_buy_timeout
                    pass
            
            # 2. Sell Order Creation
            elif split.status == "BUY_FILLED":
                # Price Strategy always places sell order immediately upon fill
                self._create_sell_order(split)

    def _check_buy_timeout(self, split: SplitState, open_order_uuids: set) -> bool:
        """Check if limit buy timed out and convert to market."""
        if not split.created_at: 
            return False
            
        try:
            created_dt = datetime.fromisoformat(split.created_at)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            
            elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds()
            
            # KST Correction
            if elapsed < 0:
                 elapsed = (datetime.now(timezone.utc) - (created_dt - timedelta(hours=9))).total_seconds()

            if elapsed > self.strategy.ORDER_TIMEOUT_SEC:
                current_price = self.strategy.exchange.get_current_price(self.strategy.ticker)
                
                # Check if still within range
                if current_price and (self.strategy.config.max_price <= 0 or current_price <= self.strategy.config.max_price):
                    logging.info(f"Price Logic: Buy order {split.buy_order_uuid} timed out ({elapsed:.1f}s). Switching to Market.")
                    try:
                        self.strategy.exchange.cancel_order(split.buy_order_uuid)
                        res = self.strategy.exchange.buy_market_order(self.strategy.ticker, split.buy_amount)
                        if res:
                            split.buy_order_uuid = res.get('uuid')
                            split.created_at = datetime.now(timezone.utc).isoformat()
                            self.strategy.save_state()
                            return True
                    except Exception as e:
                        logging.warning(f"Timeout market conversion failed: {e}")
        except Exception as e:
            logging.error(f"Error checking buy timeout: {e}")
            
        return False

    def _create_sell_order(self, split: SplitState):
        """Create sell order for a filled buy split."""
        # Use actual_buy_price (real execution price) as the base for sell rate
        # to ensure users get exactly the configured profit percentage
        sell_base = split.actual_buy_price if split.actual_buy_price else split.buy_price
        raw_sell_price = sell_base * (1 + self.strategy.config.sell_rate)
        sell_price = self.strategy.exchange.normalize_price(raw_sell_price)
        split.target_sell_price = sell_price

        try:
            result = self.strategy.exchange.sell_limit_order(self.strategy.ticker, sell_price, split.buy_volume)
            if result:
                split.sell_order_uuid = result.get('uuid')
                split.status = "PENDING_SELL"
                logging.info(f"Price Logic: Created sell order {split.sell_order_uuid} at {sell_price}")
                self.strategy.save_state()
        except Exception as e:
            logging.warning(f"Price Logic: Failed to create sell order: {e}")

    def handle_split_cleanup(self):
        """
        Recalculate last_buy_price based on remaining splits AND last sell price.
        This ensures we can 'follow' the price back down 0.5% after a sell.
        """
        if not self.strategy.is_running:
            return

        # 1. Get the lowest price among active splits
        active_ref_price = None
        if self.strategy.splits:
            active_buys = [s for s in self.strategy.splits if s.status != "SELL_FILLED"]
            if active_buys:
                def get_ref_price(s):
                    return s.actual_buy_price if s.actual_buy_price and s.actual_buy_price > 0 else s.buy_price
                lowest_split = min(active_buys, key=get_ref_price)
                active_ref_price = get_ref_price(lowest_split)

        # 2. Get the anchor price from the last sell to allow 'rebuy' after 0.5% drop
        # If we just sold at 101,000, we want to be able to rebuy at 101,000 * (1 - 0.5%) = 100,500 approx.
        # So we set last_buy_price to 101,000.
        sell_ref_price = self.strategy.last_sell_price

        # 3. Determine the best anchor for 'last_buy_price'
        # Rule: To follow the price DOWN and avoid premature buys, we must anchor
        # to the LOWEST representative price (either an active buy or the last sell).
        # This prevents a high-priced stuck split (like #12 at 195k) from pulling the anchor back up.
        candidates = []
        if active_ref_price: candidates.append(active_ref_price)
        if sell_ref_price: candidates.append(sell_ref_price)

        new_anchor = min(candidates) if candidates else None

        if new_anchor and self.strategy.last_buy_price != new_anchor:
            logging.info(f"Price Logic: Adjusting buy anchor to {new_anchor:.1f} (Lowest of Active/Sell).")
            self.strategy.last_buy_price = new_anchor
            self.strategy.save_state()
        elif new_anchor is None:
            if self.strategy.last_buy_price is not None:
                logging.info("Price Logic: No active positions or sell history. Resetting anchor.")
                self.strategy.last_buy_price = None
                self.strategy.save_state()

    # _create_buy_orders removed (logic moved to execute_buy_logic for better control over levels)

    def _execute_single_buy(self, actual_market_price: float, buy_rsi: float = None) -> SplitState:
        """
        Execute a single buy order.
        actual_market_price: Current price we are buying at.
        """
        # 1. Check Global Max Holdings
        current_holdings = len([s for s in self.strategy.splits if s.status != "SELL_FILLED"])
        if current_holdings >= self.strategy.config.max_holdings:
            return None

        # 2. Determine Investment Amount
        # Use actual market price for segment calculation
        current_invested = sum(s.buy_amount for s in self.strategy.splits)
        investment_amount = self.strategy.config.investment_per_split
        
        if self.strategy.config.price_segments:
             for segment in self.strategy.config.price_segments:
                 if segment.min_price <= actual_market_price <= segment.max_price:
                     investment_amount = segment.investment_per_split
                     break
        
        if current_invested + investment_amount > self.strategy.budget:
            return None

        # 3. Order Execution
        split_id = self.strategy.next_split_id
        
        # We always use market order for immediate entry
        try:
            logging.info(f"Price Logic: Attempting buy_market_order for {investment_amount} KRW")
            result = self.strategy.exchange.buy_market_order(self.strategy.ticker, investment_amount)
            if result:
                logging.info(f"Price Logic: Buy order created! UUID={result.get('uuid')}")
                
                # Use actual market price as the base for the split and next target calculation
                rec_buy_price = actual_market_price
                
                split = SplitState(
                    id=split_id, 
                    status="PENDING_BUY", 
                    buy_price=rec_buy_price,
                    buy_amount=investment_amount, 
                    buy_volume=investment_amount / actual_market_price,
                    buy_order_uuid=result.get('uuid'), 
                    created_at=datetime.now(timezone.utc).isoformat(),
                    buy_rsi=buy_rsi
                )
                self.strategy.splits.append(split)
                self.strategy.next_split_id += 1
                self.strategy.last_buy_price = rec_buy_price
                self.strategy.save_state()
                return split
            else:
                logging.warning("Price Logic: Exchange buy_market_order returned no result.")
        except Exception as e:
            logging.error(f"Price Logic: Exchange buy_market_order failed: {e}")
            if "insufficient" in str(e).lower():
                self._insufficient_funds_until = time.time() + 3600
            return None
        return None

    def validate_buy(self, price: float) -> bool:
        if self.strategy.config.price_segments:
            match_found = False
            for segment in self.strategy.config.price_segments:
                if segment.min_price <= price <= segment.max_price:
                    match_found = True
                    active_count = sum(1 for s in self.strategy.splits if s.status != "SELL_FILLED" and segment.min_price <= s.buy_price <= segment.max_price)
                    if active_count >= segment.max_splits:
                        self.strategy.last_status_msg = f"구매 보류: 세그먼트 한도 초과 ({active_count}/{segment.max_splits})"
                        return False
                    return True
            if not match_found:
                self.strategy.last_status_msg = f"구매 보류: 현재 가격({price:,.0f})에 매칭되는 세그먼트가 없습니다."
                return False
            return True
        
        # Classic Mode Validation
        if price < self.strategy.config.min_price:
            self.strategy.last_status_msg = f"구매 보류: 현재 가격({price:,.0f})이 최소 설정가({self.strategy.config.min_price:,.0f})보다 낮습니다."
            return False
            
        if self.strategy.config.max_price > 0 and price > self.strategy.config.max_price:
            self.strategy.last_status_msg = f"구매 보류: 현재 가격({price:,.0f})이 최대 설정가({self.strategy.config.max_price:,.0f})보다 높습니다."
            return False
            
        return True

    def _calculate_levels_crossed(self, reference_price: float, current_price: float) -> int:
        levels_crossed = 0
        temp_price = reference_price
        while True:
            next_level = temp_price * (1 - self.strategy.config.buy_rate)
            if current_price > next_level: break
            levels_crossed += 1
            temp_price = next_level
            if levels_crossed >= 10: break
        return levels_crossed
