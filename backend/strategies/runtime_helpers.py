import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

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
        }

    def _build_config_from_state(self, state) -> StrategyConfig:
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
            strategy_mode=getattr(state, "strategy_mode", "PRICE"),
            rsi_period=getattr(state, "rsi_period", 14),
            rsi_timeframe=getattr(state, "rsi_timeframe", "minutes/60"),
            rsi_buy_max=getattr(state, "rsi_buy_max", 30.0),
            rsi_buy_first_threshold=getattr(state, "rsi_buy_first_threshold", 5.0),
            rsi_buy_first_amount=getattr(state, "rsi_buy_first_amount", 1),
            rsi_buy_next_threshold=getattr(state, "rsi_buy_next_threshold", 1.0),
            rsi_buy_next_amount=getattr(state, "rsi_buy_next_amount", 1),
            rsi_sell_min=getattr(state, "rsi_sell_min", 70.0),
            rsi_sell_first_threshold=getattr(state, "rsi_sell_first_threshold", 5.0),
            rsi_sell_first_amount=getattr(state, "rsi_sell_first_amount", 1),
            rsi_sell_next_threshold=getattr(state, "rsi_sell_next_threshold", 1.0),
            rsi_sell_next_amount=getattr(state, "rsi_sell_next_amount", 1),
            stop_loss=getattr(state, "stop_loss", -10.0),
            max_holdings=getattr(state, "max_holdings", 20),
            use_trailing_buy=getattr(state, "use_trailing_buy", False),
            trailing_buy_rebound_percent=getattr(state, "trailing_buy_rebound_percent", 0.2),
            trailing_buy_batch=getattr(state, "trailing_buy_batch", True),
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


class StrategyOrderManager:
    """Order synchronization/fill handling for a strategy."""

    def manage_orders(self, strategy, open_order_uuids: set) -> None:
        for split in list(strategy.splits):
            if split.status == "PENDING_BUY":
                self._process_pending_buy_split(strategy, split, open_order_uuids)

            elif split.status == "PENDING_SELL":
                self._process_pending_sell_split(strategy, split, open_order_uuids)

        if strategy.config.strategy_mode != "RSI":
            strategy.price_logic.manage_active_positions(open_order_uuids)

        self.cleanup_filled_splits(strategy)

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
            strategy.price_logic.handle_split_cleanup()

    def check_buy_order(self, strategy, split: SplitState) -> None:
        if not split.buy_order_uuid:
            return

        try:
            order = strategy.exchange.get_order(split.buy_order_uuid)
            if not order:
                return

            state = order.get("state")
            if state in ("done", "cancel"):
                executed_vol = float(order.get("executed_volume", 0))
                if executed_vol > 0:
                    self._mark_buy_filled(strategy, split, order, state, executed_vol)
                elif state == "cancel":
                    self._reset_buy_split(strategy, split, "order cancelled with 0 volume")

        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "Order not found" in error_msg:
                self._reset_buy_split(strategy, split, "order not found (likely exchange restart)")
            else:
                logging.error(f"Error checking buy order {split.buy_order_uuid}: {e}")

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
            if order and order.get("state") == "done":
                actual_sell_price, _ = self.calculate_execution_metrics(
                    order,
                    fallback_price=split.target_sell_price,
                )
                if actual_sell_price == 0.0:
                    logging.warning(f"Sell filled but price is 0. Order: {order}")
                self.finalize_sell_trade(strategy, split, actual_sell_price)

        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "Order not found" in error_msg:
                self._reset_sell_split_to_pending_buy(
                    strategy,
                    split,
                    "sell order not found (likely exchange restart)",
                )
            else:
                logging.error(f"Error checking sell order {split.sell_order_uuid}: {e}")

    def finalize_sell_trade(self, strategy, split: SplitState, actual_sell_price: float) -> None:
        buy_total = split.buy_amount
        buy_fee = buy_total * strategy.config.fee_rate

        sell_total = actual_sell_price * split.buy_volume
        sell_fee = sell_total * strategy.config.fee_rate

        total_fee = buy_fee + sell_fee
        net_profit = sell_total - buy_total - total_fee
        profit_rate = (net_profit / buy_total) * 100

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
            "bought_at": datetime.fromisoformat(split.bought_at) if split.bought_at else None,
            "is_accumulated": split.is_accumulated,
            "buy_rsi": split.buy_rsi,
        }
        strategy.db.add_trade(strategy.strategy_id, strategy.ticker, trade_data)

        strategy.trade_history.insert(
            0,
            {
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
                "timestamp": strategy.get_now_utc().isoformat(),
                "bought_at": split.bought_at,
                "buy_rsi": split.buy_rsi,
            },
        )

        split.status = "SELL_FILLED"
        strategy.last_sell_price = actual_sell_price
        logging.info(
            f"Sell order filled for split {split.id} at {actual_sell_price}. "
            f"Net Profit: {net_profit} KRW ({profit_rate:.2f}%) after fees: {total_fee} KRW"
        )
        strategy.save_state()

    def _process_pending_buy_split(self, strategy, split: SplitState, open_order_uuids: set) -> None:
        if not split.buy_order_uuid:
            self._drop_zombie_pending_buy(strategy, split)
            return

        should_recheck = self._is_buy_timeout(strategy, split) or split.buy_order_uuid not in open_order_uuids
        if should_recheck:
            self._safe_check_buy_order(strategy, split, context="manage")

    def _process_pending_sell_split(self, strategy, split: SplitState, open_order_uuids: set) -> None:
        if not split.sell_order_uuid:
            self._recover_zombie_pending_sell(strategy, split)
            return

        if split.sell_order_uuid not in open_order_uuids:
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
        split.bought_at = strategy.get_now_utc().isoformat()
        actual_price, volume = self.calculate_execution_metrics(order, split.buy_price or 0.0)
        split.actual_buy_price = actual_price
        split.buy_price = actual_price
        split.buy_volume = volume if volume > 0 else executed_vol

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

    def _reset_sell_split_to_pending_buy(self, strategy, split: SplitState, reason: str) -> None:
        logging.warning(f"Resetting split {split.id} to PENDING_BUY: {reason}")
        split.sell_order_uuid = None
        split.status = "PENDING_BUY"
        split.buy_order_uuid = None
        strategy.save_state()

    def _is_buy_timeout(self, strategy, split: SplitState) -> bool:
        if not split.created_at:
            return False
        try:
            created_dt = datetime.fromisoformat(split.created_at)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)

            now_utc = strategy.get_now_utc()
            elapsed = (now_utc - created_dt).total_seconds()
            if elapsed < 0:
                created_dt_corrected = created_dt - timedelta(hours=9)
                elapsed = (now_utc - created_dt_corrected).total_seconds()

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
                split = strategy.price_logic._execute_single_buy(current_price, buy_rsi=rsi_5m)
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

    def stop(self, strategy) -> None:
        strategy.is_running = False
        for split in strategy.splits:
            if split.status == "PENDING_BUY" and split.buy_order_uuid:
                try:
                    strategy.exchange.cancel_order(split.buy_order_uuid)
                    logging.info(f"Cancelled buy order {split.buy_order_uuid} for split {split.id}")
                except Exception as e:
                    logging.error(f"Failed to cancel buy order {split.buy_order_uuid}: {e}")
                split.buy_order_uuid = None
            elif split.status == "PENDING_SELL" and split.sell_order_uuid:
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
            "trade_history": strategy.trade_history[:200],
            "rsi": strategy.rsi_logic.current_rsi,
            "rsi_short": strategy.rsi_logic.current_rsi_short,
            "rsi_daily": strategy.rsi_logic.current_rsi_daily,
            "rsi_daily_short": strategy.rsi_logic.current_rsi_daily_short,
            "is_watching": strategy.is_watching,
            "watch_lowest_price": strategy.watch_lowest_price,
            "status_msg": strategy.last_status_msg,
        }


class StrategyGuardService:
    """Budget and trade-limit guards."""

    def has_sufficient_budget(self, strategy, market_context: dict = None) -> bool:
        total_invested = sum(s.buy_amount for s in strategy.splits if s.status != "SELL_FILLED")
        if total_invested + strategy.config.investment_per_split > strategy.budget:
            return False

        if market_context and "accounts" in market_context:
            try:
                krw_balance = 0.0
                for acc in market_context["accounts"]:
                    if acc.get("currency") == "KRW":
                        krw_balance = float(acc.get("balance", 0))
                        break

                if krw_balance < strategy.config.investment_per_split:
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
        recent_count = 0

        for t in strategy.trade_history:
            ts = t.get("timestamp")
            if ts:
                try:
                    ts_val = datetime.fromisoformat(ts).timestamp() if isinstance(ts, str) else float(ts)
                    if ts_val > one_day_ago:
                        recent_count += 1
                except Exception:
                    pass

            bought_at = t.get("bought_at")
            if bought_at:
                try:
                    ba_val = (
                        datetime.fromisoformat(bought_at).timestamp()
                        if isinstance(bought_at, str)
                        else float(bought_at)
                    )
                    if ba_val > one_day_ago:
                        recent_count += 1
                except Exception:
                    pass

        for split in strategy.splits:
            if split.status in ["BUY_FILLED", "PENDING_SELL"] and split.bought_at:
                try:
                    ba_val = (
                        datetime.fromisoformat(split.bought_at).timestamp()
                        if isinstance(split.bought_at, str)
                        else float(split.bought_at)
                    )
                    if ba_val > one_day_ago:
                        recent_count += 1
                except Exception:
                    pass

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
        indicators: Dict[str, Any] = {"rsi_5m": None}
        try:
            indicators["rsi_5m"] = strategy.watch_logic.get_rsi_5m(current_price, market_context=market_context)
            if hasattr(strategy.rsi_logic, "_update_daily_rsi"):
                strategy.rsi_logic._update_daily_rsi(current_price, market_context=market_context)
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
