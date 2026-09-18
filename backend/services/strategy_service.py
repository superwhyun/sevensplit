import logging
import time
from typing import Dict, List, Optional
from strategy import SevenSplitStrategy
from models.strategy_state import StrategyConfig

class StrategyService:
    def __init__(self, db, exchange_service):
        self.db = db
        self.exchange_service = exchange_service
        self.strategies: Dict[int, SevenSplitStrategy] = {}
        # Execution mode the loaded strategies belong to (REAL / DEV).
        self.current_mode: Optional[str] = None
        # Strategies that were running before a restart but were held (not resumed) on boot.
        self.held_on_boot_ids: set = set()

    def load_strategies(self, mode: Optional[str] = None):
        """Load strategies from DB. With a mode, only strategies of that mode are loaded."""
        self.strategies = {}
        self.current_mode = mode
        self.held_on_boot_ids = set()
        db_strategies = self.db.get_all_strategies(mode=mode) if mode is not None else self.db.get_all_strategies()

        if not db_strategies:
            logging.info(f"No strategies found in DB (mode={mode}).")
        else:
            logging.info(f"Loading {len(db_strategies)} strategies from DB (mode={mode}).")
            for s in db_strategies:
                self.strategies[s.id] = SevenSplitStrategy(
                    self.exchange_service,
                    s.id,
                    s.ticker,
                    s.budget
                )

    def get_strategy(self, strategy_id: int) -> Optional[SevenSplitStrategy]:
        return self.strategies.get(strategy_id)

    def get_all_strategies(self) -> List[SevenSplitStrategy]:
        return list(self.strategies.values())

    def create_strategy(self, name: str, ticker: str, budget: float, config: dict) -> int:
        try:
            s = self.db.create_strategy(
                name=name,
                ticker=ticker,
                budget=budget,
                config=config,
                mode=self.current_mode,
            )
            self.strategies[s.id] = SevenSplitStrategy(
                self.exchange_service,
                s.id,
                s.ticker,
                s.budget
            )
            return s.id
        except Exception as e:
            logging.error(f"Failed to create strategy: {e}")
            raise

    def delete_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")

        try:
            strategy = self.strategies[strategy_id]
            # Delete must be a full teardown regardless of running state.
            strategy.hard_stop()

            # Remove from memory
            del self.strategies[strategy_id]

            # Remove from DB
            self.db.delete_strategy(strategy_id)
        except Exception as e:
            logging.error(f"Failed to delete strategy: {e}")
            raise

    def hold_running_strategies(self, reason: str) -> int:
        """Flip every running strategy to stopped without touching its orders.
        Fills keep being reconciled by the engine; only the buy logic is disabled."""
        held = 0
        for strategy in self.strategies.values():
            if not strategy.is_running:
                continue
            with strategy.lock:
                strategy.is_running = False
                strategy.save_state()
            self.held_on_boot_ids.add(strategy.strategy_id)
            try:
                strategy.log_event("WARNING", "HELD_ON_BOOT", reason)
            except Exception:
                pass
            held += 1
        if held:
            logging.warning(f"Held {held} running strategies on boot: {reason}")
        return held

    def start_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")

        strategy = self.strategies[strategy_id]
        self.held_on_boot_ids.discard(strategy_id)

        # Fetch current price
        try:
            current_price = self.exchange_service.get_current_price(strategy.ticker)
        except Exception as e:
            logging.error(f"Failed to fetch price for {strategy.ticker}: {e}")
            current_price = None

        strategy.start(current_price=current_price)

    def stop_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")
        self.strategies[strategy_id].stop()

    def hard_stop_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")
        self.strategies[strategy_id].hard_stop()

    def update_config(self, strategy_id: int, config: StrategyConfig, budget: float = None):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")

        strategy = self.strategies[strategy_id]

        if budget is not None:
            strategy.budget = budget

        strategy.update_config(config)
        if hasattr(strategy, "price_logic") and hasattr(strategy.price_logic, "_last_buy_gate_code"):
            strategy.price_logic._last_buy_gate_code = None
        if hasattr(strategy, "adaptive_buy_controller"):
            strategy.adaptive_buy_controller.refresh_runtime()

        # Re-evaluate immediately so config changes (e.g. segment max_splits) are reflected
        # without waiting for the next scheduler/websocket cycle.
        # NOTE: Real strategy loop will pick up changes on the next regular tick.

    def set_manual_target(self, strategy_id: int, price: Optional[float]):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")
        self.strategies[strategy_id].set_manual_target(price)

    def reset_strategy(self, strategy_id: int):
        if strategy_id not in self.strategies:
            raise ValueError("Strategy not found")

        try:
            # Stop
            if self.strategies[strategy_id].is_running:
                self.strategies[strategy_id].stop()

            # Cancel orders
            strategy = self.strategies[strategy_id]
            for split in strategy.splits:
                if split.buy_order_uuid:
                    try:
                        self.exchange_service.cancel_order(split.buy_order_uuid)
                    except Exception:
                        pass
                if split.sell_order_uuid:
                    try:
                        self.exchange_service.cancel_order(split.sell_order_uuid)
                    except Exception:
                        pass

            # Clear DB data
            self.db.delete_all_splits(strategy_id)
            self.db.delete_all_trades(strategy_id)

            # Reset state
            self.db.update_strategy_state(
                strategy_id,
                next_split_id=1,
                last_buy_price=None,
                last_sell_price=None,
                next_buy_target_price=None,
                adaptive_reentry_pressure=0.0,
            )

            # Recreate instance
            s_rec = self.db.get_strategy(strategy_id)
            self.strategies[strategy_id] = SevenSplitStrategy(
                self.exchange_service,
                strategy_id,
                s_rec.ticker,
                s_rec.budget
            )
            if getattr(self.strategies[strategy_id].config, "use_adaptive_buy_control", False):
                self.strategies[strategy_id].log_event(
                    "INFO",
                    "ADAPTIVE_PRESSURE",
                    "Pressure: 0.0000 | Multiplier: 1.0000x | Cause: RESET",
                )
            logging.info(f"Reset strategy {strategy_id}")

        except Exception as e:
            logging.error(f"Failed to reset strategy {strategy_id}: {e}")
            raise
