import logging
import math
import time
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta
from models.strategy_state import SplitState

class PriceStrategyLogic:
    def __init__(self, strategy):
        self.strategy = strategy
        # self.watch_logic is now accessible via self.strategy.watch_logic
        self._insufficient_funds_until = 0
        self._last_buy_gate_code = None

    def _set_buy_gate(self, code: str, message: str, level: str = "INFO"):
        """Record buy gate transitions as system events (only on state change)."""
        self.strategy.last_status_msg = message
        if self._last_buy_gate_code != code:
            self._last_buy_gate_code = code
            self.strategy.log_event(level, "BUY_GATE", f"{code}: {message}")

    def plan_buy(
        self,
        current_price: float,
        rsi_5m: float,
        just_exited_watch: bool = False,
        market_context: dict = None,
        rsi_daily: float = None,
    ):
        """
        Build a buy execution plan.
        Returns None when buy should be skipped this tick.
        """
        # Check active positions
        active_splits = [s for s in self.strategy.splits if s.status in ["PENDING_BUY", "BUY_FILLED", "PENDING_SELL"]]
        has_active_positions = len(active_splits) > 0

        decision = self._resolve_buy_target(
            current_price=current_price,
            just_exited_watch=just_exited_watch,
            has_active_positions=has_active_positions,
        )
        if decision is None:
            return None

        target_price = decision["target_price"]
        current_price = decision["effective_price"]
        reference_msg = decision["reference_msg"]
        is_grid_buy = decision["is_grid_buy"]
        allow_batch_buy = bool(decision.get("allow_batch_buy", False))

        if current_price > target_price:
            msg = f"Price Logic: Price ({current_price}) is currently ABOVE target ({target_price:.1f}). Waiting for dip."
            logging.info(msg)
            self._set_buy_gate("WAIT_PRICE_BELOW_TARGET", msg, level="INFO")
            return None

        if not self._validate_segment_buy(current_price):
            msg = f"Price Logic: Buy at {current_price} blocked by segment validation: {self.strategy.last_status_msg}"
            logging.info(msg)
            return None

        raw_levels_crossed = self._calculate_raw_levels_crossed(is_grid_buy, current_price)
        adaptive_controls = self.strategy.adaptive_buy_controller.resolve_execution_controls(
            raw_levels_crossed=raw_levels_crossed,
            allow_batch_buy=allow_batch_buy,
        )
        required_amount = self._estimate_buy_amount(current_price, adaptive_controls["buy_multiplier"])
        if not self._passes_buy_guards(market_context=market_context, required_amount=required_amount):
            return None

        self._set_buy_gate("BUY_READY", "Price strategy buy conditions satisfied.", level="INFO")
        return {
            "current_price": current_price,
            "rsi_5m": rsi_5m,
            "rsi_daily": rsi_daily,
            "reference_msg": reference_msg,
            "is_grid_buy": is_grid_buy,
            "allow_batch_buy": allow_batch_buy,
            "raw_levels_crossed": raw_levels_crossed,
            "adaptive_controls": adaptive_controls,
        }

    def execute_buy_logic(
        self,
        current_price: float,
        rsi_5m: float,
        just_exited_watch: bool = False,
        market_context: dict = None,
        planned_buy: dict = None,
        rsi_daily: float = None,
    ):
        """
        Execute core buy logic after plan/validation.
        """
        buy_plan = planned_buy or self.plan_buy(
            current_price=current_price,
            rsi_5m=rsi_5m,
            just_exited_watch=just_exited_watch,
            market_context=market_context,
            rsi_daily=rsi_daily,
        )
        if buy_plan is None:
            return

        current_price = buy_plan["current_price"]
        rsi_5m = buy_plan["rsi_5m"]
        rsi_daily = buy_plan.get("rsi_daily")
        reference_msg = buy_plan["reference_msg"]
        is_grid_buy = buy_plan["is_grid_buy"]
        allow_batch_buy = bool(buy_plan.get("allow_batch_buy", False))
        adaptive_controls = buy_plan.get("adaptive_controls", {})
        buy_multiplier = float(adaptive_controls.get("buy_multiplier", 1.0) or 1.0)
        next_gap_levels = max(1, int(adaptive_controls.get("next_gap_levels", 1) or 1))
        batch_cap = adaptive_controls.get("batch_cap")

        levels_crossed = self._resolve_levels_crossed(is_grid_buy, current_price, allow_batch_buy=allow_batch_buy)
        if batch_cap is not None:
            levels_crossed = min(levels_crossed, max(1, int(batch_cap)))
        
        # Use rsi_daily for the recorded buy_rsi if available
        buy_rsi_to_record = rsi_daily if rsi_daily is not None else rsi_5m
        created_count, log_details = self._execute_batch_buys(
            levels_crossed,
            current_price,
            buy_rsi_to_record,
            buy_multiplier,
        )
        if created_count <= 0:
            return

        self.strategy.log_event(
            "INFO",
            "BUY_EXEC",
            self._build_buy_exec_message(
                is_grid_buy,
                reference_msg,
                current_price,
                log_details,
                buy_multiplier=buy_multiplier,
                next_gap_levels=next_gap_levels,
                fast_drop_active=bool(adaptive_controls.get("fast_drop_active", False)),
            ),
        )
        self.strategy.next_buy_target_price = current_price * (
            1 - (self.strategy.config.buy_rate * next_gap_levels)
        )

    def _passes_buy_guards(self, market_context: dict = None, required_amount: float = None) -> bool:
        if not self.strategy.has_sufficient_budget(
            market_context=market_context,
            required_amount=required_amount,
        ):
            msg = "Price Logic: Buy skipped due to insufficient budget."
            logging.info(msg)
            self._set_buy_gate("WAIT_INSUFFICIENT_BUDGET", msg, level="WARNING")
            return False
        if not self.strategy.check_trade_limit():
            msg = "Price Logic: Buy skipped due to trade limit (24h)."
            logging.info(msg)
            self._set_buy_gate("WAIT_TRADE_LIMIT", msg, level="WARNING")
            return False
        return True

    def _resolve_buy_target(
        self,
        current_price: float,
        just_exited_watch: bool,
        has_active_positions: bool,
    ):
        auto_target_price = None
        reference_msg = ""
        is_grid_buy = False
        if just_exited_watch:
            auto_target_price = current_price
            reference_msg = "Watch Mode Exit - Rebound Confirmed"
            is_grid_buy = has_active_positions and bool(self.strategy.last_buy_price)
        elif not has_active_positions:
            initial = self._resolve_initial_target(current_price)
            if initial is None:
                return None
            auto_target_price = initial["target_price"]
            reference_msg = initial["reference_msg"]
            is_grid_buy = False
        elif self.strategy.last_buy_price is None:
            auto_target_price = current_price
            reference_msg = "Safety Entry (No last_buy_price)"
            is_grid_buy = False
        else:
            auto_target_price = self.strategy.last_buy_price * (1 - self.strategy.config.buy_rate)
            reference_msg = f"Grid Level from {self.strategy.last_buy_price}"
            is_grid_buy = True

        if auto_target_price is None:
            return None

        if self.strategy.next_buy_target_price is None:
            self.strategy.next_buy_target_price = self._normalize_target_price(auto_target_price)

        return {
            "target_price": self.strategy.next_buy_target_price,
            "effective_price": current_price,
            "reference_msg": reference_msg,
            "is_grid_buy": is_grid_buy,
            # Batch catch-up buy is only allowed right after watch-mode rebound confirmation.
            "allow_batch_buy": (
                bool(just_exited_watch)
                and bool(self.strategy.config.use_trailing_buy)
                and bool(self.strategy.config.trailing_buy_batch)
            ),
        }

    def _resolve_initial_target(self, current_price: float):
        if self._find_matching_segment(current_price) is None:
            msg = (
                f"Price Logic: Current price {current_price} is outside configured segments. "
                f"Ranges: {self._segment_ranges_text()}"
            )
            logging.debug(msg)
            self._set_buy_gate("WAIT_OUTSIDE_SEGMENT_RANGE", msg, level="WARNING")
            return None

        if self.strategy.config.rebuy_strategy == "last_sell_price":
            ref_price = self.strategy.last_sell_price if self.strategy.last_sell_price else current_price
            return {
                "target_price": ref_price * (1 - self.strategy.config.buy_rate),
                "reference_msg": f"Rebuy from Last Sell {ref_price}",
            }

        if self.strategy.config.rebuy_strategy == "last_buy_price":
            ref_price = self.strategy.last_buy_price if self.strategy.last_buy_price else current_price
            return {
                "target_price": ref_price * (1 - self.strategy.config.buy_rate),
                "reference_msg": f"Rebuy from Last Buy {ref_price}",
            }

        return {
            "target_price": current_price,
            "reference_msg": "Initial Entry (Reset on Clear)",
        }

    def _normalize_target_price(self, target_price: float) -> float:
        try:
            if hasattr(self.strategy.exchange, "normalize_price"):
                return float(self.strategy.exchange.normalize_price(target_price))
        except Exception as e:
            logging.debug(f"Price Logic: Failed to normalize manual target {target_price}: {e}")
        return target_price

    def _calculate_raw_levels_crossed(self, is_grid_buy: bool, current_price: float) -> int:
        if not is_grid_buy or self.strategy.last_buy_price is None:
            return 1
        return max(1, self._calculate_levels_crossed(self.strategy.last_buy_price, current_price))

    def _resolve_levels_crossed(self, is_grid_buy: bool, current_price: float, allow_batch_buy: bool = False) -> int:
        if not is_grid_buy:
            return 1
        levels_crossed = self._calculate_levels_crossed(self.strategy.last_buy_price, current_price)
        if not allow_batch_buy and levels_crossed > 1:
            return 1
        return levels_crossed

    def _estimate_buy_amount(self, price: float, buy_multiplier: float) -> float:
        segment = self._find_matching_segment(price)
        if segment is None:
            return 0.0
        raw_amount = float(segment.investment_per_split or 0.0) * max(float(buy_multiplier or 0.0), 0.0)
        return self._round_order_amount(raw_amount)

    @staticmethod
    def _round_order_amount(amount: float) -> float:
        normalized = max(float(amount or 0.0), 0.0)
        return float(math.floor(normalized + 0.5))

    def _execute_batch_buys(self, levels_crossed: int, current_price: float, buy_rsi: float, buy_multiplier: float):
        created_count = 0
        log_details = []
        for _ in range(levels_crossed):
            split = self._execute_single_buy(current_price, buy_rsi=buy_rsi, buy_multiplier=buy_multiplier)
            if not split:
                break
            created_count += 1
            log_details.append(
                f"Split #{split.id}: Entry @ {current_price:.1f} / ₩{split.buy_amount:,.0f}"
            )
        return created_count, log_details

    def _build_buy_exec_message(
        self,
        is_grid_buy: bool,
        reference_msg: str,
        current_price: float,
        log_details: list,
        buy_multiplier: float = 1.0,
        next_gap_levels: int = 1,
        fast_drop_active: bool = False,
    ) -> str:
        final_next_target = current_price * (1 - (self.strategy.config.buy_rate * next_gap_levels))
        msg = (
            f"Buy Executed ({'Grid' if is_grid_buy else 'Initial'}).\n"
            f"- Condition: {reference_msg}\n"
            f"- Market Price: {current_price:.1f}\n"
        )
        if buy_multiplier < 0.999 or fast_drop_active:
            msg += f"- Buy Size Multiplier: {buy_multiplier:.2f}x\n"
        if fast_drop_active:
            msg += f"- Fast Drop Brake: ON ({next_gap_levels} levels)\n"
        if log_details:
            msg += "- " + "\n- ".join(log_details) + "\n"
        msg += f"- Next Buy Target: {final_next_target:.1f}"
        return msg

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
            
            now_utc = self.strategy.get_now_utc()
            elapsed = (now_utc - created_dt).total_seconds()
            
            # KST Correction
            if elapsed < 0:
                 elapsed = (now_utc - (created_dt - timedelta(hours=9))).total_seconds()

            if elapsed > self.strategy.ORDER_TIMEOUT_SEC:
                current_price = self.strategy.exchange.get_current_price(self.strategy.ticker)
                
                # Check if current price is still in configured segment range.
                if current_price and self._is_price_in_any_segment(current_price):
                    logging.info(f"Price Logic: Buy order {split.buy_order_uuid} timed out ({elapsed:.1f}s). Switching to Market.")
                    try:
                        self.strategy.exchange.cancel_order(split.buy_order_uuid)
                        res = self.strategy.exchange.buy_market_order(self.strategy.ticker, split.buy_amount)
                        if res:
                            split.buy_order_uuid = res.get('uuid')
                            split.created_at = self.strategy.get_now_utc().isoformat()
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

    def handle_split_cleanup(self, target_refresh_requested: bool = False):
        """
        Recalculate last_buy_price based on remaining splits AND last sell price.
        This ensures we can 'follow' the price back down 0.5% after a sell.
        """
        if not self.strategy.is_running:
            return

        state_changed = False
        prev_target = self.strategy.next_buy_target_price

        # 1. Get the lowest price among actual holdings.
        # PENDING_BUY orders are not filled inventory yet, so they must not
        # keep the rebuy anchor pinned below a realized sell.
        active_ref_price = None
        has_active_positions = False
        if self.strategy.splits:
            active_buys = [
                s for s in self.strategy.splits if s.status in ["BUY_FILLED", "PENDING_SELL"]
            ]
            if active_buys:
                has_active_positions = True
                def get_ref_price(s):
                    return s.actual_buy_price if s.actual_buy_price and s.actual_buy_price > 0 else s.buy_price
                lowest_split = min(active_buys, key=get_ref_price)
                active_ref_price = get_ref_price(lowest_split)

        # 2. Determine rebuy anchor based on configured strategy.
        if has_active_positions:
            # While positions exist, keep anchor synchronized to the lowest active entry.
            if active_ref_price and self.strategy.last_buy_price != active_ref_price:
                logging.info(f"Price Logic: Syncing buy anchor to active split {active_ref_price:.1f}.")
                self.strategy.last_buy_price = active_ref_price
                state_changed = True
        else:
            rebuy = self.strategy.config.rebuy_strategy
            if rebuy == "reset_on_clear":
                if self.strategy.last_buy_price is not None:
                    logging.info("Price Logic: reset_on_clear -> clearing last_buy_price anchor.")
                    self.strategy.last_buy_price = None
                    state_changed = True
            elif rebuy == "last_sell_price":
                anchor = self.strategy.last_sell_price
                if anchor is not None and self.strategy.last_buy_price != anchor:
                    logging.info(f"Price Logic: last_sell_price -> anchoring to last sell {anchor:.1f}.")
                    self.strategy.last_buy_price = anchor
                    state_changed = True
            elif rebuy == "last_buy_price":
                # Keep previous last_buy_price as-is by design.
                pass

        # Next target should be recalculated only when split lifecycle changes
        # (e.g. sell-filled split cleanup), not on every tick.
        if target_refresh_requested:
            desired_target = None
            if self.strategy.last_buy_price is not None:
                desired_target = self._normalize_target_price(
                    self.strategy.last_buy_price * (1 - self.strategy.config.buy_rate)
                )

            if has_active_positions:
                if self.strategy.next_buy_target_price != desired_target:
                    self.strategy.next_buy_target_price = desired_target
                    state_changed = True
            else:
                rebuy = self.strategy.config.rebuy_strategy
                if rebuy == "reset_on_clear":
                    if self.strategy.next_buy_target_price is not None:
                        logging.info("Price Logic: All positions closed. Resetting next_buy_target_price.")
                        self.strategy.next_buy_target_price = None
                        state_changed = True
                else:
                    # For last_sell_price / last_buy_price, maintain immediate rebuy target from anchor.
                    if desired_target is not None and self.strategy.next_buy_target_price != desired_target:
                        self.strategy.next_buy_target_price = desired_target
                        state_changed = True

        target_changed = prev_target != self.strategy.next_buy_target_price
        if target_changed:
            if self.strategy.next_buy_target_price is None:
                self.strategy.log_event("INFO", "TARGET_UPDATE", "Next Buy Target: NONE")
            else:
                self.strategy.log_event(
                    "INFO",
                    "TARGET_UPDATE",
                    f"Next Buy Target: {float(self.strategy.next_buy_target_price):.1f}",
                )

        if state_changed:
            self.strategy.save_state()

    # _create_buy_orders removed (logic moved to execute_buy_logic for better control over levels)

    def _execute_single_buy(
        self,
        actual_market_price: float,
        buy_rsi: float = None,
        buy_multiplier: float = 1.0,
    ) -> SplitState:
        """
        Execute a single buy order.
        actual_market_price: Current price we are buying at.
        """
        # 1. Determine Investment Amount
        # Use actual market price for segment calculation
        current_invested = sum(s.buy_amount for s in self.strategy.splits)
        segment = self._find_matching_segment(actual_market_price)
        if segment is None:
            self.strategy.last_status_msg = (
                f"구매 보류: 현재 가격({actual_market_price:,.0f})에 매칭되는 세그먼트가 없습니다."
            )
            return None
        base_investment_amount = float(segment.investment_per_split or 0.0)
        investment_amount = self._round_order_amount(
            base_investment_amount * max(float(buy_multiplier or 0.0), 0.0)
        )

        min_buy_amount = self.strategy.adaptive_buy_controller.get_minimum_buy_amount()
        if investment_amount < min_buy_amount:
            msg = (
                f"Price Logic: Adaptive buy amount ₩{investment_amount:,.0f} is below minimum "
                f"order size ₩{min_buy_amount:,.0f}. Skipping buy."
            )
            logging.info(msg)
            self._set_buy_gate("WAIT_BUY_AMOUNT_TOO_SMALL", msg, level="WARNING")
            return None
        
        if current_invested + investment_amount > self.strategy.budget:
            return None

        # 2. Order Execution
        split_id = self.strategy.next_split_id
        
        # We always use market order for immediate entry
        try:
            logging.info(f"Price Logic: Attempting buy_market_order for {investment_amount} KRW")
            result = self.strategy.exchange.buy_market_order(self.strategy.ticker, investment_amount)
            if result and result.get('uuid'):
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
                    created_at=self.strategy.get_now_utc().isoformat(),
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

    def _validate_segment_buy(self, price: float) -> bool:
        segment = self._find_matching_segment(price)
        if segment is None:
            segment_ranges = self._segment_ranges_text()
            logging.warning(
                f"Strategy {self.strategy.strategy_id} [{self.strategy.ticker}]: "
                f"No segment matching {price:,.0f}. Ranges: {segment_ranges}"
            )
            self._set_buy_gate("WAIT_OUTSIDE_SEGMENT_RANGE", (
                f"구매 보류: 현재 가격({price:,.0f})에 매칭되는 세그먼트가 없습니다. "
                f"(범위: {segment_ranges})"
            ), level="WARNING")
            return False

        active_count = sum(
            1
            for s in self.strategy.splits
            if s.status != "SELL_FILLED" and segment.min_price <= s.buy_price <= segment.max_price
        )
        if active_count >= segment.max_splits:
            self._set_buy_gate(
                "WAIT_SEGMENT_MAX_SPLITS",
                f"구매 보류: 세그먼트 한도 초과 ({active_count}/{segment.max_splits})",
                level="WARNING",
            )
            return False
        return True

    def _effective_segments(self):
        segments = self.strategy.config.price_segments or []
        if segments:
            return segments

        min_price = float(self.strategy.config.min_price or 0.0)
        max_price = float(self.strategy.config.max_price or 0.0)
        if max_price <= min_price:
            max_price = float("inf")

        return [
            SimpleNamespace(
                min_price=min_price,
                max_price=max_price,
                investment_per_split=float(self.strategy.config.investment_per_split),
                max_splits=float("inf"),
            )
        ]

    def _find_matching_segment(self, price: float):
        for segment in self._effective_segments():
            if segment.min_price <= price <= segment.max_price:
                return segment
        return None

    def _is_price_in_any_segment(self, price: float) -> bool:
        return self._find_matching_segment(price) is not None

    def _segment_ranges_text(self) -> str:
        ranges = []
        for segment in self._effective_segments():
            upper = "∞" if segment.max_price == float("inf") else f"{segment.max_price:,.0f}"
            ranges.append(f"{segment.min_price:,.0f}~{upper}")
        return ", ".join(ranges)

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
