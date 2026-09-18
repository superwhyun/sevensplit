import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set
try:
    from zoneinfo import ZoneInfo
    _KST = ZoneInfo("Asia/Seoul")
except ImportError:
    _KST = timezone(timedelta(hours=9))

from models.strategy_state import SplitState, StrategyConfig


class StrategyStateManager:
    """Persistence manager for strategy state/splits/trade snapshots."""

    def save_state(self, strategy) -> None:
        try:
            state_data = self._build_state_payload(strategy)
            strategy.db.update_strategy_state(strategy.strategy_id, **state_data)
            logging.debug(f"✅ Strategy {strategy.strategy_id} state successfully persisted.")
            self._sync_splits(strategy)

        except Exception as e:
            logging.error(f"❌ Failed to save state for Strategy {strategy.strategy_id} to database: {e}")
            import traceback

            logging.error(traceback.format_exc())

    def load_state(self, strategy) -> bool:
        try:
            state = strategy.db.get_strategy(strategy.strategy_id)
            if not state:
                return False

            strategy.config = self._build_config_from_state(state)
            self._apply_runtime_state(strategy, state)
            self._load_splits(strategy)
            self._restore_last_buy_price(strategy)
            self._load_trade_history(strategy)

            return True
        except Exception as e:
            logging.error(f"Failed to load state from database: {e}")
            import traceback

            logging.error(traceback.format_exc())
            raise e

    def _build_state_payload(self, strategy) -> Dict[str, Any]:
        payload = strategy.config.model_dump(mode="json")
        payload.update(
            {
                "is_running": strategy.is_running,
                "next_split_id": strategy.next_split_id,
                "last_buy_price": strategy.last_buy_price,
                "last_sell_price": strategy.last_sell_price,
                "budget": strategy.budget,
                "next_buy_target_price": strategy.next_buy_target_price,
                "is_watching": strategy.is_watching,
                "watch_lowest_price": strategy.watch_lowest_price,
                "pending_buy_units": strategy.pending_buy_units,
                "adaptive_reentry_pressure": strategy.adaptive_reentry_pressure,
                "rsi_last_buy_date": getattr(strategy, "last_buy_date", None),
                "rsi_last_sell_date": getattr(strategy, "last_sell_date", None),
                "rsi_last_evaluated_candle_ts": (
                    float(getattr(strategy.rsi_logic, "_last_evaluated_candle_ts", 0.0) or 0.0)
                    if hasattr(strategy, "rsi_logic") else 0.0
                ),
            }
        )
        return payload

    def _sync_splits(self, strategy) -> None:
        db_splits = strategy.db.get_splits(strategy.strategy_id)
        db_split_ids = {s.split_id for s in db_splits}
        mem_split_ids = {s.id for s in strategy.splits}

        for split_id in db_split_ids - mem_split_ids:
            strategy.db.delete_split(strategy.strategy_id, split_id)

        for split in strategy.splits:
            split_data = self._serialize_split(split)
            if split.id in db_split_ids:
                update_data = {k: v for k, v in split_data.items() if k != "split_id"}
                strategy.db.update_split(strategy.strategy_id, split.id, **update_data)
            else:
                strategy.db.add_split(strategy.strategy_id, strategy.ticker, split_data)

    def _serialize_split(self, split: SplitState) -> Dict[str, Any]:
        return {
            "split_id": split.id,
            "status": split.status,
            "buy_price": split.buy_price,
            "target_sell_price": split.target_sell_price,
            "investment_amount": split.buy_amount,
            "coin_volume": split.buy_volume,
            "buy_order_id": split.buy_order_uuid,
            "sell_order_id": split.sell_order_uuid,
            "buy_filled_at": datetime.fromisoformat(split.bought_at) if split.bought_at else None,
            "is_accumulated": split.is_accumulated,
            "buy_rsi": split.buy_rsi,
            "buy_fee": split.buy_fee,
        }

    def _build_config_from_state(self, state) -> StrategyConfig:
        raw_mode = getattr(state, "strategy_mode", "PRICE")
        normalized_mode = str(raw_mode).upper().strip()
        if normalized_mode not in ("PRICE", "RSI"):
            normalized_mode = "PRICE"
        return StrategyConfig(
            investment_per_split=state.investment_per_split,
            min_price=state.min_price,
            max_price=state.max_price,
            buy_rate=state.buy_rate,
            sell_rate=state.sell_rate,
            fee_rate=state.fee_rate,
            tick_interval=state.tick_interval,
            rebuy_strategy=state.rebuy_strategy,
            max_trades_per_day=getattr(state, "max_trades_per_day", 100),
            strategy_mode=normalized_mode,
            rsi_period=getattr(state, "rsi_period", 14),
            rsi_buy_max=getattr(state, "rsi_buy_max", 30.0),
            rsi_buy_cross_threshold=getattr(state, "rsi_buy_cross_threshold", 0.0),
            rsi_buy_first_amount=getattr(state, "rsi_buy_first_amount", 1),
            rsi_sell_min=getattr(state, "rsi_sell_min", 70.0),
            rsi_sell_cross_threshold=getattr(state, "rsi_sell_cross_threshold", 0.0),
            rsi_sell_first_amount=getattr(state, "rsi_sell_first_amount", 1),
            max_holdings=getattr(state, "max_holdings", 20),
            use_trailing_buy=getattr(state, "use_trailing_buy", False),
            watch_rsi_threshold=getattr(state, "watch_rsi_threshold", None) or getattr(state, "rsi_buy_max", 30.0),
            trailing_buy_rebound_percent=getattr(state, "trailing_buy_rebound_percent", 0.2),
            trailing_buy_batch=getattr(state, "trailing_buy_batch", True),
            use_adaptive_buy_control=getattr(state, "use_adaptive_buy_control", False),
            adaptive_sell_pressure_step=getattr(state, "adaptive_sell_pressure_step", 1.0),
            adaptive_buy_relief_step=getattr(state, "adaptive_buy_relief_step", 1.0),
            adaptive_pressure_cap=getattr(state, "adaptive_pressure_cap", 4.0),
            adaptive_probe_multiplier=getattr(state, "adaptive_probe_multiplier", 0.5),
            use_fast_drop_brake=getattr(state, "use_fast_drop_brake", True),
            fast_drop_trigger_levels=getattr(state, "fast_drop_trigger_levels", 2),
            fast_drop_batch_cap=getattr(state, "fast_drop_batch_cap", 1),
            fast_drop_next_gap_levels=getattr(state, "fast_drop_next_gap_levels", 2),
            fast_drop_multiplier_cap=getattr(state, "fast_drop_multiplier_cap", 0.75),
            price_segments=getattr(state, "price_segments", []) or [],
        )

    def _apply_runtime_state(self, strategy, state) -> None:
        strategy.is_running = state.is_running
        strategy.next_split_id = state.next_split_id
        strategy.last_buy_price = state.last_buy_price
        strategy.last_sell_price = state.last_sell_price
        strategy.budget = state.budget
        strategy.next_buy_target_price = getattr(state, "next_buy_target_price", None)
        strategy.is_watching = getattr(state, "is_watching", False)
        strategy.watch_lowest_price = getattr(state, "watch_lowest_price", None)
        strategy.pending_buy_units = getattr(state, "pending_buy_units", 0)
        strategy.adaptive_reentry_pressure = getattr(state, "adaptive_reentry_pressure", 0.0) or 0.0
        # RSI once-per-day guards must survive a restart, or the same daily signal fires twice.
        strategy.last_buy_date = getattr(state, "rsi_last_buy_date", None) or None
        strategy.last_sell_date = getattr(state, "rsi_last_sell_date", None) or None
        if hasattr(strategy, "rsi_logic"):
            strategy.rsi_logic._last_evaluated_candle_ts = float(
                getattr(state, "rsi_last_evaluated_candle_ts", 0.0) or 0.0
            )
        strategy.adaptive_effective_buy_multiplier = 1.0
        strategy.adaptive_fast_drop_active = False
        if hasattr(strategy, "adaptive_buy_controller"):
            strategy.adaptive_buy_controller.refresh_runtime()

    def _load_splits(self, strategy) -> None:
        db_splits = strategy.db.get_splits(strategy.strategy_id)
        strategy.splits = [self._deserialize_split(db_split) for db_split in db_splits]

    def _deserialize_split(self, db_split) -> SplitState:
        return SplitState(
            id=db_split.split_id,
            status=db_split.status,
            buy_order_uuid=db_split.buy_order_id,
            sell_order_uuid=db_split.sell_order_id,
            buy_price=db_split.buy_price,
            actual_buy_price=db_split.buy_price,
            buy_amount=db_split.investment_amount,
            buy_volume=db_split.coin_volume or 0.0,
            target_sell_price=db_split.target_sell_price,
            created_at=db_split.created_at.isoformat() + "Z" if db_split.created_at else None,
            bought_at=db_split.buy_filled_at.isoformat() + "Z" if db_split.buy_filled_at else None,
            is_accumulated=db_split.is_accumulated,
            buy_rsi=db_split.buy_rsi,
            buy_fee=getattr(db_split, "buy_fee", None),
        )

    def _restore_last_buy_price(self, strategy) -> None:
        if strategy.last_buy_price is not None or not strategy.splits:
            return

        latest_split = max(strategy.splits, key=lambda s: s.id)
        if latest_split.actual_buy_price > 0:
            strategy.last_buy_price = latest_split.actual_buy_price
            logging.info(f"Restored missing last_buy_price from split history: {strategy.last_buy_price}")
            return

        strategy.last_buy_price = latest_split.buy_price
        logging.info(
            "Restored missing last_buy_price from split history "
            f"(using target price): {strategy.last_buy_price}"
        )

    def _load_trade_history(self, strategy) -> None:
        trades = strategy.db.get_trades(strategy.strategy_id, limit=200)
        strategy.trade_history = [self._serialize_trade_record(t) for t in trades]

    def _serialize_trade_record(self, trade) -> Dict[str, Any]:
        return {
            "split_id": trade.split_id,
            "buy_price": trade.buy_price,
            "sell_price": trade.sell_price,
            "buy_amount": trade.buy_amount,
            "sell_amount": trade.sell_amount,
            "volume": trade.coin_volume,
            "gross_profit": trade.gross_profit,
            "total_fee": trade.total_fee,
            "net_profit": trade.net_profit,
            "profit_rate": trade.profit_rate,
            "timestamp": trade.timestamp.isoformat() + "Z" if trade.timestamp else None,
            "bought_at": trade.bought_at.isoformat() + "Z" if trade.bought_at else None,
            "buy_rsi": trade.buy_rsi,
        }


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 string into a UTC-aware datetime. Returns None on failure."""
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_order_not_found_error(error: Exception) -> bool:
    message = str(error)
    return "404" in message or "Order not found" in message


class StrategyOrderManager:
    """Order synchronization/fill handling for a strategy."""

    # A single 404 from the exchange must never drop a real holding. Only after this many
    # consecutive not-found responses for the same order do we treat it as truly gone.
    NOT_FOUND_DROP_THRESHOLD = 5
    # Pending sells below the current price are normally skipped to save API calls.
    # Every FULL_SYNC_INTERVAL_SEC (and on the very first tick) we check all of them anyway,
    # so fills that happened while the bot was offline are always reconciled.
    FULL_SYNC_INTERVAL_SEC = 300
    _VOLUME_EPSILON = 1e-9

    def __init__(self):
        self._not_found_counts: Dict[str, int] = {}
        self._last_full_sync: Dict[int, float] = {}

    def manage_orders(self, strategy, open_order_uuids: set, current_price: float = None) -> None:
        force_full_check = self._should_run_full_sync(strategy)
        for split in list(strategy.splits):
            if split.status == "PENDING_BUY":
                self._process_pending_buy_split(strategy, split, open_order_uuids)

            elif split.status == "PENDING_SELL":
                self._process_pending_sell_split(
                    strategy,
                    split,
                    open_order_uuids,
                    current_price,
                    force_check=force_full_check,
                )

        if strategy.config.strategy_mode != "RSI":
            strategy.price_logic.manage_active_positions(open_order_uuids)

        self.cleanup_filled_splits(strategy)

    def _should_run_full_sync(self, strategy) -> bool:
        now_ts = strategy.get_now_utc().timestamp()
        last_ts = self._last_full_sync.get(strategy.strategy_id)
        if last_ts is not None and (now_ts - last_ts) < self.FULL_SYNC_INTERVAL_SEC:
            return False
        self._last_full_sync[strategy.strategy_id] = now_ts
        return True

    def _register_not_found(self, order_uuid: str) -> int:
        count = self._not_found_counts.get(order_uuid, 0) + 1
        self._not_found_counts[order_uuid] = count
        return count

    def _clear_not_found(self, order_uuid: Optional[str]) -> None:
        if order_uuid:
            self._not_found_counts.pop(order_uuid, None)

    @staticmethod
    def resolve_fill_time(order: dict, fallback: datetime) -> datetime:
        """Best-effort actual fill time from the exchange order payload (UTC)."""
        fill_times = [
            parsed
            for parsed in (_parse_iso_datetime(t.get("created_at")) for t in (order.get("trades") or []))
            if parsed is not None
        ]
        if fill_times:
            return max(fill_times)
        order_created = _parse_iso_datetime(order.get("created_at"))
        if order_created is not None:
            return order_created
        if fallback.tzinfo is None:
            return fallback.replace(tzinfo=timezone.utc)
        return fallback.astimezone(timezone.utc)

    def sync_pending_orders(self, strategy) -> None:
        for split in strategy.splits:
            if split.status == "PENDING_BUY" and split.buy_order_uuid:
                self._safe_check_buy_order(strategy, split, context="sync")
            elif split.status == "PENDING_SELL" and split.sell_order_uuid:
                self._safe_check_sell_order(strategy, split, context="sync")

    def cleanup_filled_splits(self, strategy) -> None:
        splits_to_remove = [s for s in strategy.splits if s.status == "SELL_FILLED"]
        for split in splits_to_remove:
            logging.info(f"Removing completed split {split.id}")
            strategy.splits.remove(split)
            strategy.save_state()

        if strategy.config.strategy_mode != "RSI":
            strategy.price_logic.handle_split_cleanup(target_refresh_requested=bool(splits_to_remove))

    def check_buy_order(self, strategy, split: SplitState) -> None:
        if not split.buy_order_uuid:
            return

        try:
            order = strategy.exchange.get_order(split.buy_order_uuid)
            if not order:
                return
            self._clear_not_found(split.buy_order_uuid)

            state = order.get("state")
            if state in ("done", "cancel"):
                executed_vol = float(order.get("executed_volume", 0))
                if executed_vol > 0:
                    self._mark_buy_filled(strategy, split, order, state, executed_vol)
                elif state == "cancel":
                    self._reset_buy_split(strategy, split, "order cancelled with 0 volume")

        except Exception as e:
            if not _is_order_not_found_error(e):
                logging.error(f"Error checking buy order {split.buy_order_uuid}: {e}")
                return
            count = self._register_not_found(split.buy_order_uuid)
            if count < self.NOT_FOUND_DROP_THRESHOLD:
                logging.warning(
                    f"Buy order {split.buy_order_uuid} for split {split.id} not found "
                    f"({count}/{self.NOT_FOUND_DROP_THRESHOLD}). Keeping split until confirmed."
                )
                return
            self._clear_not_found(split.buy_order_uuid)
            self._reset_buy_split(
                strategy,
                split,
                f"order not found {count} consecutive times",
            )

    @staticmethod
    def order_paid_fee(order: dict) -> Optional[float]:
        """Actual fee the exchange charged for this order, or None when the payload lacks it."""
        raw = (order or {}).get("paid_fee")
        if raw is None or raw == "":
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def calculate_execution_metrics(self, order: dict, fallback_price: float) -> tuple[float, float]:
        trades = order.get("trades", [])
        if trades:
            total_funds = sum(
                float(t.get("funds", 0)) if t.get("funds") else float(t.get("price", 0)) * float(t.get("volume", 0))
                for t in trades
            )
            total_volume = sum(float(t.get("volume", 0)) for t in trades)
            if total_volume > 0:
                return (total_funds / total_volume), total_volume

        executed_vol = float(order.get("executed_volume", 0))
        ord_type = order.get("ord_type")
        if ord_type == "price":
            return fallback_price, executed_vol

        price = float(order.get("price") or fallback_price or 0.0)
        return price, executed_vol

    def check_sell_order(self, strategy, split: SplitState) -> None:
        if not split.sell_order_uuid:
            return

        try:
            order = strategy.exchange.get_order(split.sell_order_uuid)
            if not order:
                return
            self._clear_not_found(split.sell_order_uuid)

            state = order.get("state")
            if state == "done":
                actual_sell_price, _ = self.calculate_execution_metrics(
                    order,
                    fallback_price=split.target_sell_price,
                )
                if actual_sell_price == 0.0:
                    logging.warning(f"Sell filled but price is 0. Order: {order}")
                filled_at = self.resolve_fill_time(order, strategy.get_now_utc())
                self.finalize_sell_trade(
                    strategy, split, actual_sell_price, filled_at=filled_at, sell_fee=self.order_paid_fee(order),
                )
            elif state == "cancel":
                self._handle_cancelled_sell(strategy, split, order)

        except Exception as e:
            if not _is_order_not_found_error(e):
                logging.error(f"Error checking sell order {split.sell_order_uuid}: {e}")
                return
            count = self._register_not_found(split.sell_order_uuid)
            if count < self.NOT_FOUND_DROP_THRESHOLD:
                logging.warning(
                    f"Sell order {split.sell_order_uuid} for split {split.id} not found "
                    f"({count}/{self.NOT_FOUND_DROP_THRESHOLD}). Keeping position until confirmed."
                )
                return
            self._clear_not_found(split.sell_order_uuid)
            self._revert_sell_split_to_buy_filled(
                strategy,
                split,
                f"sell order not found {count} consecutive times; re-placing sell for held coins",
            )

    def _handle_cancelled_sell(self, strategy, split: SplitState, order: dict) -> None:
        """A cancelled limit sell may still have executed partially. Never lose the coins."""
        executed_vol = float(order.get("executed_volume") or 0.0)
        held_vol = float(split.buy_volume or 0.0)

        if executed_vol <= self._VOLUME_EPSILON:
            self._revert_sell_split_to_buy_filled(
                strategy,
                split,
                "sell order cancelled with 0 volume; re-placing sell",
            )
            return

        actual_sell_price, _ = self.calculate_execution_metrics(order, fallback_price=split.target_sell_price)
        filled_at = self.resolve_fill_time(order, strategy.get_now_utc())
        sell_fee = self.order_paid_fee(order)

        if executed_vol + self._VOLUME_EPSILON >= held_vol:
            self.finalize_sell_trade(strategy, split, actual_sell_price, filled_at=filled_at, sell_fee=sell_fee)
            return

        ratio = executed_vol / held_vol if held_vol > 0 else 0.0
        sold_buy_amount = split.buy_amount * ratio
        sold_buy_fee = split.buy_fee * ratio if split.buy_fee is not None else None
        self._record_sell_trade(
            strategy,
            split,
            actual_sell_price,
            volume=executed_vol,
            buy_amount=sold_buy_amount,
            filled_at=filled_at,
            buy_fee=sold_buy_fee,
            sell_fee=sell_fee,
        )
        split.buy_volume = held_vol - executed_vol
        split.buy_amount = split.buy_amount - sold_buy_amount
        if split.buy_fee is not None and sold_buy_fee is not None:
            split.buy_fee = split.buy_fee - sold_buy_fee
        split.sell_order_uuid = None
        split.status = "BUY_FILLED"
        strategy.last_sell_price = actual_sell_price
        strategy.log_event(
            "WARNING",
            "SELL_PARTIAL",
            f"Split #{split.id}: sell order cancelled after partial fill "
            f"({executed_vol:.8f} of {held_vol:.8f}). Remaining volume will be re-listed.",
        )
        strategy.save_state()

    def _record_sell_trade(
        self,
        strategy,
        split: SplitState,
        actual_sell_price: float,
        volume: float,
        buy_amount: float,
        filled_at: datetime,
        buy_fee: Optional[float] = None,
        sell_fee: Optional[float] = None,
    ) -> Dict[str, float]:
        # Prefer the fees the exchange actually charged; fall back to the configured rate
        # only when the order payload did not report them (older records, stub exchanges).
        sell_total = actual_sell_price * volume
        if buy_fee is None:
            buy_fee = buy_amount * strategy.config.fee_rate
        if sell_fee is None:
            sell_fee = sell_total * strategy.config.fee_rate
        total_fee = buy_fee + sell_fee
        net_profit = sell_total - buy_amount - total_fee
        profit_rate = (net_profit / buy_amount) * 100 if buy_amount > 0 else 0.0

        trade_data = {
            "split_id": split.id,
            "buy_price": split.actual_buy_price,
            "sell_price": actual_sell_price,
            "coin_volume": volume,
            "buy_amount": buy_amount,
            "sell_amount": sell_total,
            "gross_profit": sell_total - buy_amount,
            "total_fee": total_fee,
            "net_profit": net_profit,
            "profit_rate": profit_rate,
            "buy_order_id": split.buy_order_uuid,
            "sell_order_id": split.sell_order_uuid,
            "bought_at": _parse_iso_datetime(split.bought_at),
            "is_accumulated": split.is_accumulated,
            "buy_rsi": split.buy_rsi,
            "timestamp": filled_at,
        }
        strategy.db.add_trade(strategy.strategy_id, strategy.ticker, trade_data)

        strategy.trade_history.insert(
            0,
            {
                "split_id": split.id,
                "buy_price": split.actual_buy_price,
                "buy_amount": buy_amount,
                "sell_price": actual_sell_price,
                "sell_amount": sell_total,
                "volume": volume,
                "buy_fee": buy_fee,
                "sell_fee": sell_fee,
                "total_fee": total_fee,
                "gross_profit": sell_total - buy_amount,
                "net_profit": net_profit,
                "profit_rate": profit_rate,
                "timestamp": filled_at.isoformat(),
                "bought_at": split.bought_at,
                "buy_rsi": split.buy_rsi,
            },
        )
        return {
            "sell_total": sell_total,
            "total_fee": total_fee,
            "net_profit": net_profit,
            "profit_rate": profit_rate,
        }

    def finalize_sell_trade(
        self,
        strategy,
        split: SplitState,
        actual_sell_price: float,
        filled_at: Optional[datetime] = None,
        sell_fee: Optional[float] = None,
    ) -> None:
        if filled_at is None:
            filled_at = strategy.get_now_utc()
        if filled_at.tzinfo is None:
            filled_at = filled_at.replace(tzinfo=timezone.utc)
        filled_at = filled_at.astimezone(timezone.utc)

        result = self._record_sell_trade(
            strategy,
            split,
            actual_sell_price,
            volume=split.buy_volume,
            buy_amount=split.buy_amount,
            filled_at=filled_at,
            buy_fee=split.buy_fee,
            sell_fee=sell_fee,
        )

        split.status = "SELL_FILLED"
        strategy.last_sell_price = actual_sell_price
        if hasattr(strategy, "adaptive_buy_controller"):
            strategy.adaptive_buy_controller.apply_sell_fill(
                result["sell_total"],
                split.actual_buy_price or split.buy_price,
            )
        logging.info(
            f"Sell order filled for split {split.id} at {actual_sell_price} ({filled_at.isoformat()}). "
            f"Net Profit: {result['net_profit']} KRW ({result['profit_rate']:.2f}%) "
            f"after fees: {result['total_fee']} KRW"
        )
        strategy.save_state()

    def _process_pending_buy_split(self, strategy, split: SplitState, open_order_uuids: set) -> None:
        if not split.buy_order_uuid:
            self._drop_zombie_pending_buy(strategy, split)
            return

        should_recheck = self._is_buy_timeout(strategy, split) or split.buy_order_uuid not in open_order_uuids
        if should_recheck:
            self._safe_check_buy_order(strategy, split, context="manage")

    def _process_pending_sell_split(
        self,
        strategy,
        split: SplitState,
        open_order_uuids: set,
        current_price: float = None,
        force_check: bool = False,
    ) -> None:
        if not split.sell_order_uuid:
            self._recover_zombie_pending_sell(strategy, split)
            return

        if split.sell_order_uuid in open_order_uuids:
            return

        # Limit sell orders can only fill when price reaches the target.
        # Skip the API call when price is still below target to avoid unnecessary requests,
        # except during a periodic full sync (fills may have happened while offline).
        if (
            not force_check
            and current_price
            and split.target_sell_price
            and current_price < split.target_sell_price
        ):
            return

        self._safe_check_sell_order(strategy, split, context="manage")

    def _safe_check_buy_order(self, strategy, split: SplitState, context: str) -> None:
        try:
            self.check_buy_order(strategy, split)
        except Exception as e:
            log_fn = logging.warning if context == "sync" else logging.error
            log_fn(f"Error checking buy order {split.buy_order_uuid}: {e}")

    def _safe_check_sell_order(self, strategy, split: SplitState, context: str) -> None:
        try:
            self.check_sell_order(strategy, split)
        except Exception as e:
            log_fn = logging.warning if context == "sync" else logging.error
            log_fn(f"Error checking sell order {split.sell_order_uuid}: {e}")

    def _drop_zombie_pending_buy(self, strategy, split: SplitState) -> None:
        logging.info(f"Found zombie split {split.id} (PENDING_BUY with no UUID). Removing to reset.")
        strategy.splits.remove(split)
        strategy.save_state()

    def _recover_zombie_pending_sell(self, strategy, split: SplitState) -> None:
        logging.info(f"Found zombie split {split.id} (PENDING_SELL with no UUID). Reverting to BUY_FILLED.")
        split.status = "BUY_FILLED"
        strategy.save_state()

    def _mark_buy_filled(
        self,
        strategy,
        split: SplitState,
        order: dict,
        state: str,
        executed_vol: float,
    ) -> None:
        split.status = "BUY_FILLED"
        split.bought_at = self.resolve_fill_time(order, strategy.get_now_utc()).isoformat()
        actual_price, volume = self.calculate_execution_metrics(order, split.buy_price or 0.0)
        split.actual_buy_price = actual_price
        split.buy_price = actual_price
        split.buy_volume = volume if volume > 0 else executed_vol
        split.buy_fee = self.order_paid_fee(order)
        if hasattr(strategy, "adaptive_buy_controller"):
            strategy.adaptive_buy_controller.apply_buy_fill(split.buy_amount, split.actual_buy_price)

        logging.info(
            f"Buy order {state} for split {split.id}. "
            f"Price: {split.actual_buy_price}, Vol: {split.buy_volume}"
        )
        strategy.save_state()

    def _reset_buy_split(self, strategy, split: SplitState, reason: str) -> None:
        logging.warning(f"Resetting split {split.id} to PENDING_BUY: {reason}")
        split.buy_order_uuid = None
        split.status = "PENDING_BUY"
        strategy.save_state()

    def _revert_sell_split_to_buy_filled(self, strategy, split: SplitState, reason: str) -> None:
        """The coins are still held; drop only the sell order so a fresh one gets placed."""
        logging.warning(f"Reverting split {split.id} to BUY_FILLED: {reason}")
        strategy.log_event(
            "WARNING",
            "SELL_ORDER_LOST",
            f"Split #{split.id}: {reason}",
        )
        split.sell_order_uuid = None
        split.status = "BUY_FILLED"
        strategy.save_state()

    def _is_buy_timeout(self, strategy, split: SplitState) -> bool:
        if not split.created_at:
            return False
        created_dt = _parse_iso_datetime(split.created_at)
        if created_dt is None:
            return False
        try:
            now_utc = strategy.get_now_utc()
            if now_utc.tzinfo is None:
                now_utc = now_utc.replace(tzinfo=timezone.utc)
            elapsed = (now_utc - created_dt).total_seconds()
            if elapsed < 0:
                # Legacy rows stored naive KST timestamps; treat them as KST.
                elapsed = (now_utc - (created_dt - timedelta(hours=9))).total_seconds()
            return elapsed > strategy.ORDER_TIMEOUT_SEC
        except Exception:
            return False


class StrategyLifecycleManager:
    """Start/stop lifecycle manager."""

    def start(self, strategy, current_price=None) -> None:
        if current_price is None:
            current_price = strategy.exchange.get_current_price(strategy.ticker)

        if current_price and not strategy.splits:
            if strategy.config.strategy_mode == "RSI":
                logging.info(
                    f"Starting strategy {strategy.strategy_id} in RSI Mode. "
                    f"Waiting for signal (Current Price: {current_price})"
                )
            else:
                logging.info(f"Starting strategy {strategy.strategy_id} at current price: {current_price}")
                rsi_5m = strategy.watch_logic.get_rsi_5m(current_price)
                buy_multiplier = (
                    strategy.adaptive_buy_controller.get_pressure_multiplier()
                    if hasattr(strategy, "adaptive_buy_controller")
                    else 1.0
                )
                split = strategy.price_logic._execute_single_buy(
                    current_price,
                    buy_rsi=rsi_5m,
                    buy_multiplier=buy_multiplier,
                )
                if split:
                    next_target = current_price * (1 - strategy.config.buy_rate)
                    msg = (
                        "Initial Buy Executed (On Start).\n"
                        "- Condition: Strategy Started with no positions.\n"
                        f"- Current Price: {current_price}\n"
                        f"- Next Buy Target: {next_target:.1f}"
                    )
                    strategy.log_event("INFO", "BUY_EXEC", msg)

        logging.info(f"Syncing pending orders for strategy {strategy.strategy_id}...")
        strategy.order_manager.sync_pending_orders(strategy)
        strategy.is_running = True
        strategy.save_state()

    def stop(self, strategy, cancel_sells: bool = False) -> None:
        strategy.is_running = False
        for split in strategy.splits:
            if split.status == "PENDING_BUY" and split.buy_order_uuid:
                try:
                    strategy.exchange.cancel_order(split.buy_order_uuid)
                    logging.info(f"Cancelled buy order {split.buy_order_uuid} for split {split.id}")
                except Exception as e:
                    logging.error(f"Failed to cancel buy order {split.buy_order_uuid}: {e}")
                split.buy_order_uuid = None
            elif cancel_sells and split.status == "PENDING_SELL" and split.sell_order_uuid:
                try:
                    strategy.exchange.cancel_order(split.sell_order_uuid)
                    logging.info(f"Cancelled sell order {split.sell_order_uuid} for split {split.id}")
                except Exception as e:
                    logging.error(f"Failed to cancel sell order {split.sell_order_uuid}: {e}")
                split.sell_order_uuid = None
                split.status = "BUY_FILLED"

        strategy.save_state()


class StrategyStatusPresenter:
    """State serialization for API/UI consumers."""

    def get_state(self, strategy, current_price=None) -> dict:
        resolved_price = self._resolve_current_price(strategy, current_price)
        totals = self._compute_totals(strategy, resolved_price)
        status_counts = self._build_status_counts(strategy)
        strategy_name = self._resolve_strategy_name(strategy)
        logic_status = self._derive_logic_status(strategy, status_counts)
        return self._build_state_payload(
            strategy=strategy,
            strategy_name=strategy_name,
            logic_status=logic_status,
            resolved_price=resolved_price,
            totals=totals,
            status_counts=status_counts,
        )

    def _resolve_current_price(self, strategy, current_price):
        if current_price is not None:
            return current_price
        return strategy.exchange.get_current_price(strategy.ticker)

    def _compute_totals(self, strategy, current_price) -> Dict[str, float]:
        total_invested = 0.0
        total_valuation = 0.0
        total_coin_volume = 0.0

        for split in strategy.splits:
            if split.status in ["BUY_FILLED", "PENDING_SELL"]:
                invested = split.buy_amount
                valuation = split.buy_volume * current_price if current_price else 0
                total_invested += invested
                total_valuation += valuation
                total_coin_volume += split.buy_volume

        total_profit_amount = total_valuation - total_invested
        total_profit_rate = (total_profit_amount / total_invested * 100) if total_invested > 0 else 0.0
        return {
            "total_invested": total_invested,
            "total_valuation": total_valuation,
            "total_coin_volume": total_coin_volume,
            "total_profit_amount": total_profit_amount,
            "total_profit_rate": total_profit_rate,
        }

    def _build_status_counts(self, strategy) -> Dict[str, int]:
        return {
            "pending_buy": sum(1 for s in strategy.splits if s.status == "PENDING_BUY"),
            "buy_filled": sum(1 for s in strategy.splits if s.status == "BUY_FILLED"),
            "pending_sell": sum(1 for s in strategy.splits if s.status == "PENDING_SELL"),
            "sell_filled": sum(1 for s in strategy.splits if s.status == "SELL_FILLED"),
        }

    def _resolve_strategy_name(self, strategy) -> str:
        strategy_name = "Unknown"
        strategy_rec = strategy.db.get_strategy(strategy.strategy_id)
        if strategy_rec:
            strategy_name = strategy_rec.name
        return strategy_name

    def _derive_logic_status(self, strategy, status_counts: Dict[str, int]) -> str:
        active_splits_count = status_counts["buy_filled"] + status_counts["pending_sell"]
        is_max_holdings_reached = (
            strategy.config.strategy_mode == "RSI" and active_splits_count >= strategy.config.max_holdings
        )

        if not strategy.is_running:
            return "Stopped"
        if not strategy.has_sufficient_budget() or is_max_holdings_reached:
            return "Max Limit"
        if strategy.config.strategy_mode == "PRICE" and strategy.config.use_trailing_buy and strategy.is_watching:
            return "Watching"
        return "Normal"

    def _build_state_payload(
        self,
        strategy,
        strategy_name: str,
        logic_status: str,
        resolved_price,
        totals: Dict[str, float],
        status_counts: Dict[str, int],
    ) -> Dict[str, Any]:
        realized_total = sum(float(t.get("net_profit", 0.0)) for t in strategy.trade_history)
        now_utc = datetime.now(timezone.utc)
        now_kst = now_utc.astimezone(_KST)
        today_midnight_utc = now_kst.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        realized_today = 0.0
        try:
            realized_total = strategy.db.get_realized_profit_sum(strategy.strategy_id)
            realized_today = strategy.db.get_realized_profit_sum(
                strategy.strategy_id,
                since=today_midnight_utc,
            )
        except Exception as e:
            logging.debug(f"Realized profit aggregation fallback to in-memory history: {e}")
            for trade in strategy.trade_history:
                ts = trade.get("timestamp")
                if not ts:
                    continue
                try:
                    trade_ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except Exception:
                    continue
                if trade_ts >= today_midnight_utc:
                    realized_today += float(trade.get("net_profit", 0.0))

        return {
            "id": strategy.strategy_id,
            "name": strategy_name,
            "ticker": strategy.ticker,
            "status": logic_status,
            "budget": strategy.budget,
            "is_running": strategy.is_running,
            "config": strategy.config.model_dump(),
            "splits": [s.model_dump() for s in strategy.splits],
            "current_price": resolved_price,
            "total_profit_amount": totals["total_profit_amount"],
            "total_profit_rate": totals["total_profit_rate"],
            "total_invested": totals["total_invested"],
            "total_coin_volume": totals["total_coin_volume"],
            "total_valuation": totals["total_valuation"],
            "status_counts": status_counts,
            "last_buy_price": strategy.last_buy_price,
            "next_buy_target_price": strategy.next_buy_target_price,
            "realized_profit_total": realized_total,
            "realized_profit_24h": realized_today,
            "trade_history": strategy.trade_history[:200],
            "rsi": strategy.rsi_logic.current_rsi,
            "rsi_short": strategy.rsi_logic.current_rsi_short,
            "rsi_daily": strategy.rsi_logic.current_rsi_daily,
            "rsi_daily_short": strategy.rsi_logic.current_rsi_daily_short,
            "is_watching": strategy.is_watching,
            "watch_lowest_price": strategy.watch_lowest_price,
            "adaptive_reentry_pressure": strategy.adaptive_reentry_pressure,
            "adaptive_effective_buy_multiplier": (
                strategy.adaptive_effective_buy_multiplier
                if strategy.adaptive_fast_drop_active
                else strategy.adaptive_buy_controller.get_pressure_multiplier()
            ) if hasattr(strategy, "adaptive_buy_controller") else 1.0,
            "adaptive_fast_drop_active": strategy.adaptive_fast_drop_active,
            "status_msg": strategy.last_status_msg,
        }


class StrategyGuardService:
    """Budget and trade-limit guards."""

    def has_sufficient_budget(self, strategy, market_context: dict = None, required_amount: Optional[float] = None) -> bool:
        if required_amount is not None:
            required_amount = float(required_amount)
        elif getattr(strategy.config, "price_segments", None):
            required_amount = min(float(s.investment_per_split) for s in strategy.config.price_segments)
        else:
            required_amount = float(strategy.config.investment_per_split)
        total_invested = sum(s.buy_amount for s in strategy.splits if s.status != "SELL_FILLED")
        if total_invested + required_amount > strategy.budget:
            return False

        if market_context and "accounts" in market_context:
            try:
                krw_balance = 0.0
                for acc in market_context["accounts"]:
                    if acc.get("currency") == "KRW":
                        krw_balance = float(acc.get("balance", 0))
                        break

                if krw_balance < required_amount:
                    logging.warning(f"Insufficient KRW balance in account: {krw_balance}")
                    return False
            except Exception as e:
                logging.debug(f"Budget balance check skipped due to error: {e}")

        return True

    def check_trade_limit(self, strategy) -> bool:
        if strategy.config.max_trades_per_day <= 0:
            return True

        now = strategy.get_now_utc()
        one_day_ago = now.timestamp() - 86400
        recent_events = set()

        def _to_ts(val):
            if not val:
                return None
            try:
                if isinstance(val, str):
                    return datetime.fromisoformat(val).timestamp()
                return float(val)
            except Exception:
                return None

        for t in strategy.trade_history:
            split_id = t.get("split_id")
            ts = t.get("timestamp")
            ts_val = _to_ts(ts)
            if ts_val and ts_val > one_day_ago:
                # One sell-side action per closed trade record.
                recent_events.add(("SELL", split_id, int(ts_val)))

            bought_at = t.get("bought_at")
            ba_val = _to_ts(bought_at)
            if ba_val and ba_val > one_day_ago:
                # One buy-side action per trade record.
                recent_events.add(("BUY", split_id, int(ba_val)))

        for split in strategy.splits:
            if split.status in ["BUY_FILLED", "PENDING_SELL"] and split.bought_at:
                ba_val = _to_ts(split.bought_at)
                if ba_val and ba_val > one_day_ago:
                    # Open positions may not exist in trade_history yet; key by split id.
                    recent_events.add(("BUY_OPEN", split.id, int(ba_val)))

        recent_count = len(recent_events)

        if recent_count >= strategy.config.max_trades_per_day:
            logging.warning(
                f"Trade limit reached ({recent_count}/{strategy.config.max_trades_per_day} actions in 24h). "
                "Skipping buy."
            )
            return False

        return True


class StrategyTickCoordinator:
    """Pre/post steps for one strategy tick."""

    def dedupe_splits(self, strategy) -> None:
        unique_splits = {}
        for split in strategy.splits:
            if split.id not in unique_splits:
                unique_splits[split.id] = split
            else:
                logging.warning(f"Found duplicate split ID {split.id} in memory. Removing duplicate.")

        if len(unique_splits) != len(strategy.splits):
            strategy.splits = sorted(unique_splits.values(), key=lambda s: s.id)

    def resolve_current_price(self, strategy, current_price: Optional[float]) -> Optional[float]:
        if current_price is None:
            current_price = strategy.exchange.get_current_price(strategy.ticker)
        return current_price

    def update_indicators(self, strategy, current_price: float, market_context: dict = None) -> Dict[str, Any]:
        indicators: Dict[str, Any] = {"rsi_5m": None, "rsi_daily": None}
        try:
            indicators["rsi_5m"] = strategy.watch_logic.get_rsi_5m(current_price, market_context=market_context)
            if hasattr(strategy.rsi_logic, "_update_daily_rsi"):
                strategy.rsi_logic._update_daily_rsi(current_price, market_context=market_context)
                indicators["rsi_daily"] = getattr(strategy.rsi_logic, "current_rsi_daily", None)
        except Exception as e:
            logging.debug(f"RSI indicator update failed: {e}")
        return indicators

    def build_open_order_uuids(
        self,
        strategy,
        open_orders: Optional[list] = None,
    ) -> Optional[Set[str]]:
        try:
            if open_orders is not None:
                return {order["uuid"] for order in open_orders}

            fetched_orders = strategy.exchange.get_orders(ticker=strategy.ticker, state="wait")
            if not fetched_orders:
                return set()
            return {order["uuid"] for order in fetched_orders}
        except Exception as e:
            logging.error(f"Failed to process open orders: {e}")
            return None
