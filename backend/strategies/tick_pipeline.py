from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class TickContext:
    current_price: Optional[float]
    open_orders: Optional[list]
    market_context: Optional[dict]
    indicators: Dict[str, Any] = field(default_factory=dict)
    open_order_uuids: Optional[Set[str]] = None
    planned_actions: List[Dict[str, Any]] = field(default_factory=list)


class TickPipeline:
    """
    Standardized strategy tick pipeline.

    Stages:
    1) pre_tick
    2) sync_orders
    3) update_indicators
    4) evaluate_guards
    5) decide_actions
    6) execute_actions
    7) post_tick
    """

    def run(self, strategy, current_price: float = None, open_orders: list = None, market_context: dict = None):
        ctx = TickContext(
            current_price=current_price,
            open_orders=open_orders,
            market_context=market_context,
        )
        if not self.pre_tick(strategy, ctx):
            return
        if not self.sync_orders(strategy, ctx):
            return
        if not self.update_indicators(strategy, ctx):
            return
        if not self.evaluate_guards(strategy, ctx):
            return
        if not self.decide_actions(strategy, ctx):
            return
        self.execute_actions(strategy, ctx)
        self.post_tick(strategy, ctx)

    def pre_tick(self, strategy, ctx: TickContext) -> bool:
        strategy.tick_coordinator.dedupe_splits(strategy)
        ctx.current_price = strategy.tick_coordinator.resolve_current_price(strategy, ctx.current_price)
        return bool(ctx.current_price)

    def sync_orders(self, strategy, ctx: TickContext) -> bool:
        ctx.open_order_uuids = strategy.tick_coordinator.build_open_order_uuids(
            strategy,
            open_orders=ctx.open_orders,
        )
        return ctx.open_order_uuids is not None

    def update_indicators(self, strategy, ctx: TickContext) -> bool:
        ctx.indicators = strategy.tick_coordinator.update_indicators(
            strategy,
            ctx.current_price,
            market_context=ctx.market_context,
        )
        return True

    def evaluate_guards(self, strategy, ctx: TickContext) -> bool:
        if not strategy.is_running:
            return False
        strategy.order_manager.manage_orders(strategy, ctx.open_order_uuids)
        return True

    def decide_actions(self, strategy, ctx: TickContext) -> bool:
        ctx.planned_actions.append(
            {
                "type": "run_rsi_logic",
            }
        )

        mode = strategy.config.strategy_mode
        if mode in ["PRICE", "ALL"]:
            rsi_5m = ctx.indicators.get("rsi_5m") if ctx.indicators else None
            proceed, just_exited_watch = strategy.watch_logic.check_proceed_to_buy(
                ctx.current_price,
                rsi_5m,
            )
            if proceed:
                buy_plan = strategy.price_logic.plan_buy(
                    ctx.current_price,
                    rsi_5m,
                    just_exited_watch=just_exited_watch,
                    market_context=ctx.market_context,
                )
                if buy_plan is None:
                    return True
                ctx.planned_actions.append(
                    {
                        "type": "execute_price_buy",
                        "plan": buy_plan,
                    }
                )
        return True

    def execute_actions(self, strategy, ctx: TickContext) -> None:
        for action in ctx.planned_actions:
            action_type = action.get("type")
            if action_type == "run_rsi_logic":
                strategy.rsi_logic.tick(
                    ctx.current_price,
                    market_context=ctx.market_context,
                    indicators_updated=True,
                )
            elif action_type == "execute_price_buy":
                strategy.price_logic.execute_buy_logic(
                    ctx.current_price,
                    action.get("plan", {}).get("rsi_5m"),
                    market_context=ctx.market_context,
                    planned_buy=action.get("plan"),
                )

    def post_tick(self, strategy, ctx: TickContext) -> None:
        return
