from __future__ import annotations

from typing import Optional


class AdaptiveBuyController:
    MINIMUM_KRW_ORDER = 5000.0

    def __init__(self, strategy):
        self.strategy = strategy

    def is_enabled(self) -> bool:
        config = self.strategy.config
        return bool(
            getattr(config, "strategy_mode", "PRICE") == "PRICE"
            and getattr(config, "use_adaptive_buy_control", False)
        )

    def refresh_runtime(self) -> None:
        multiplier = self.get_pressure_multiplier()
        self.strategy.adaptive_effective_buy_multiplier = multiplier
        self.strategy.adaptive_fast_drop_active = False

    def get_pressure_multiplier(self) -> float:
        if not self.is_enabled():
            return 1.0

        cap = max(float(getattr(self.strategy.config, "adaptive_pressure_cap", 4.0) or 4.0), 1e-9)
        probe = self._clamp_multiplier(getattr(self.strategy.config, "adaptive_probe_multiplier", 0.5))
        pressure = self._clamp(
            float(getattr(self.strategy, "adaptive_reentry_pressure", 0.0) or 0.0),
            0.0,
            cap,
        )
        raw = 1.0 - (pressure * (1.0 - probe) / cap)
        return self._clamp(max(probe, raw), probe, 1.0)

    def resolve_execution_controls(self, raw_levels_crossed: int, allow_batch_buy: bool) -> dict:
        multiplier = self.get_pressure_multiplier()
        fast_drop_active = self._should_activate_fast_drop_brake(raw_levels_crossed, allow_batch_buy)
        batch_cap = None
        next_gap_levels = 1

        if fast_drop_active:
            batch_cap = max(1, int(getattr(self.strategy.config, "fast_drop_batch_cap", 1) or 1))
            next_gap_levels = max(
                1,
                int(getattr(self.strategy.config, "fast_drop_next_gap_levels", 2) or 2),
            )
            fast_drop_cap = self._clamp_multiplier(
                getattr(self.strategy.config, "fast_drop_multiplier_cap", 0.75)
            )
            multiplier = min(multiplier, fast_drop_cap)

        self.strategy.adaptive_fast_drop_active = fast_drop_active
        self.strategy.adaptive_effective_buy_multiplier = multiplier
        return {
            "buy_multiplier": multiplier,
            "batch_cap": batch_cap,
            "next_gap_levels": next_gap_levels,
            "fast_drop_active": fast_drop_active,
        }

    def get_minimum_buy_amount(self) -> float:
        return self.MINIMUM_KRW_ORDER

    def apply_sell_fill(self, sell_amount: float, reference_price: Optional[float]) -> float:
        if not self.is_enabled():
            return float(getattr(self.strategy, "adaptive_reentry_pressure", 0.0) or 0.0)

        base_amount = self._resolve_base_split_amount(reference_price)
        step = max(float(getattr(self.strategy.config, "adaptive_sell_pressure_step", 1.0) or 1.0), 0.0)
        delta = (float(sell_amount or 0.0) / base_amount) * step if base_amount > 0 else 0.0
        return self._set_pressure(self.strategy.adaptive_reentry_pressure + delta, cause="SELL_FILL")

    def apply_buy_fill(self, buy_amount: float, reference_price: Optional[float]) -> float:
        if not self.is_enabled():
            return float(getattr(self.strategy, "adaptive_reentry_pressure", 0.0) or 0.0)

        base_amount = self._resolve_base_split_amount(reference_price)
        step = max(float(getattr(self.strategy.config, "adaptive_buy_relief_step", 1.0) or 1.0), 0.0)
        delta = (float(buy_amount or 0.0) / base_amount) * step if base_amount > 0 else 0.0
        return self._set_pressure(self.strategy.adaptive_reentry_pressure - delta, cause="BUY_FILL")

    def _should_activate_fast_drop_brake(self, raw_levels_crossed: int, allow_batch_buy: bool) -> bool:
        if not self.is_enabled() or not getattr(self.strategy.config, "use_fast_drop_brake", True):
            return False

        trigger_levels = max(
            1,
            int(getattr(self.strategy.config, "fast_drop_trigger_levels", 2) or 2),
        )
        return raw_levels_crossed >= trigger_levels or (allow_batch_buy and raw_levels_crossed > 1)

    def _set_pressure(self, value: float, cause: str = "UPDATE") -> float:
        cap = max(float(getattr(self.strategy.config, "adaptive_pressure_cap", 4.0) or 4.0), 0.0)
        previous = float(getattr(self.strategy, "adaptive_reentry_pressure", 0.0) or 0.0)
        clamped = self._clamp(float(value or 0.0), 0.0, cap)
        self.strategy.adaptive_reentry_pressure = clamped
        self.refresh_runtime()
        if abs(clamped - previous) > 1e-9 and hasattr(self.strategy, "log_event"):
            self.strategy.log_event(
                "INFO",
                "ADAPTIVE_PRESSURE",
                (
                    f"Pressure: {clamped:.4f} | "
                    f"Multiplier: {self.strategy.adaptive_effective_buy_multiplier:.4f}x | "
                    f"Cause: {cause}"
                ),
            )
        return clamped

    def _resolve_base_split_amount(self, price: Optional[float]) -> float:
        if price is not None:
            for segment in getattr(self.strategy.config, "price_segments", []) or []:
                if segment.min_price <= price <= segment.max_price:
                    return max(float(segment.investment_per_split or 0.0), 0.0)
        return max(float(getattr(self.strategy.config, "investment_per_split", 0.0) or 0.0), 0.0)

    def _clamp_multiplier(self, value: float) -> float:
        return self._clamp(float(value or 1.0), 1e-6, 1.0)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
