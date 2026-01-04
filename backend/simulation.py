"""
Backward compatibility facade for simulation modules.

This module provides backward-compatible imports for code that was previously
using `simulation.py`. All functionality has been moved to the `simulations/`
package for better organization.

For new code, prefer importing directly from the submodules:
    - from simulations.config import SimulationConfig
    - from simulations.runner import run_simulation, expand_daily_to_hourly
    - from simulations.base import SimulationStrategy
    - from simulations.mock import MockDB, MockExchange
    - from simulations.price import PriceSimulationStrategy
    - from simulations.rsi import RSISimulationStrategy
"""

from simulations.config import SimulationConfig
from simulations.runner import run_simulation
from simulations.base import SimulationStrategy
from simulations.mock import MockDB, MockExchange
from simulations.price import PriceSimulationStrategy
from simulations.rsi import RSISimulationStrategy

__all__ = [
    "SimulationConfig",
    "run_simulation",
    "SimulationStrategy",
    "MockDB",
    "MockExchange",
    "PriceSimulationStrategy",
    "RSISimulationStrategy",
]
