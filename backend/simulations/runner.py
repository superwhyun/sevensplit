import logging
import pandas as pd
from datetime import datetime, timezone
from .config import SimulationConfig
from .price import PriceSimulationStrategy
from .rsi import RSISimulationStrategy

def run_simulation(sim_config: SimulationConfig):
    # Configure logging for the simulation process
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # All simulations now use actual 5-minute candles provided via SimConfig
    candles = sim_config.candles
    
    # [Safety] Enforce Ascending Sort by Timestamp
    def get_sort_key(c):
        ts = c.get('timestamp') or c.get('time')
        if ts:
             # Normalize ms to s
             if ts > 10000000000: ts /= 1000.0
             return float(ts)
        # Fallback to ISO string comparison if no numeric timestamp
        return c.get('candle_date_time_utc') or c.get('candle_date_time_kst') or ""
        
    candles.sort(key=get_sort_key)
    sim_config.candles = candles # Update config
    
    # Initialize Strategy
    if sim_config.strategy_config.strategy_mode == "RSI":
        strategy = RSISimulationStrategy(sim_config.strategy_config, sim_config.budget, sim_config.candles)
    else:
        strategy = PriceSimulationStrategy(sim_config.strategy_config, sim_config.budget, sim_config.candles)

    sim_logs = [] # Init here to capture early logs

    # Synch budget to config-based budget to ensure it matches UI expectations
    strategy.budget = sim_config.budget
    strategy.splits = [] # Clear any leftover splits from previous runs
    
    # [CRITICAL] Bypass any startup delays
    strategy.initial_rsi_delay = 0
    import time
    strategy.start_time = time.time() - 86400 # Mock that it's been running for 24h
    
    try:
        msg = f"SIM START CALLED: User Requested {datetime.fromtimestamp(sim_config.start_time, timezone.utc)} (UTC)"
        print(f"\n{msg}")
        sim_logs.append(msg)
    except:
        pass

    candles = sim_config.candles
    start_idx = sim_config.start_index
    
    sim_logs.append(f"DEBUG: Runner received total_candles={len(candles)}")

    # Precise Start Time Search (Ignore start_index hint, use exact timestamp)
    if sim_config.start_time > 0:
        found_idx = -1
        for i, c in enumerate(candles):
            ts = c.get('timestamp') or c.get('time')
            if ts:
                if ts > 10000000000: ts /= 1000.0
                if ts >= sim_config.start_time:
                    found_idx = i
                    break
        
        if found_idx != -1:
            start_idx = found_idx
            msg = f"SIM: Timestamp search matched start_idx={start_idx} (Time: {datetime.fromtimestamp(sim_config.start_time, timezone.utc)})"
            sim_logs.append(msg)
            logging.info(msg)
        else:
            msg = f"SIM WARNING: start_time {sim_config.start_time} not found in candles. Using fallback start_index."
            sim_logs.append(msg)
            logging.warning(msg)

    # Initialize strategy config using start_idx price
    if start_idx < len(candles):
        start_price = candles[start_idx].get('close') or candles[start_idx].get('trade_price')
    else:
        start_price = 0
            
    # Initialize strategy state to prevent "Flash Buying" on the first tick
    if start_price:
        strategy.last_buy_price = start_price

    if strategy.config.min_price == 0.0 and start_price:
        strategy.config.min_price = start_price * 0.5 # Wide range for sim
        strategy.config.max_price = start_price * 1.5
        msg = f"SIM: Initialized config with min={strategy.config.min_price}, max={strategy.config.max_price}"
        sim_logs.append(msg)
    else:
        msg = f"SIM: Config min={strategy.config.min_price}, max={strategy.config.max_price}, mode={strategy.config.strategy_mode}"
        sim_logs.append(msg)
        
    # DEBUG: Log Trailing Buy Config
    msg = f"SIM: Trailing Buy Config: Use={strategy.config.use_trailing_buy}, Rebound={strategy.config.trailing_buy_rebound_percent}"
    sim_logs.append(msg)

    # Pre-compute daily candles (for RSI calculation)
    if strategy.config.strategy_mode == "RSI":
        daily_candles = strategy._precompute_daily_candles()
        msg = f"SIM: Pre-computed {len(daily_candles)} daily candles for RSI calculation"
        sim_logs.append(msg)
        logging.info(msg)
        
    # Track Trailing Buy Watch Intervals
    watch_intervals = []

    # Run simulation loop
    for i in range(start_idx, len(candles)):
        candle = candles[i]
        
        # Normalize candle keys
        if 'time' in candle and 'timestamp' not in candle:
            candle['timestamp'] = candle['time']
        if 'opening_price' in candle:
            candle['open'] = candle['opening_price']
        if 'high_price' in candle:
            candle['high'] = candle['high_price']
        if 'low_price' in candle:
            candle['low'] = candle['low_price']
        if 'trade_price' in candle:
            candle['close'] = candle['trade_price']

        strategy.current_candle = candle
        tick_price = candle['close']

        # Prepare Mock Market Context
        def normalize_ts(c):
            ts = c.get('timestamp') or c.get('time') or 0
            return ts / 1000.0 if ts > 10000000000 else ts

        current_ts = normalize_ts(candle)
        visible_candles_5m = [c for c in strategy.candles if normalize_ts(c) <= current_ts]
        visible_candles_daily = [c for c in strategy._precompute_daily_candles() if normalize_ts(c) <= current_ts]

        market_context = {
            'prices': {strategy.ticker: tick_price},
            'open_orders': strategy.exchange.get_orders(strategy.ticker, state='wait'),
            'accounts': [{'currency': 'KRW', 'balance': strategy.exchange.balance_krw}],
            'candles': {strategy.ticker: {
                "minutes/5": visible_candles_5m,
                "days": visible_candles_daily
            }}
        }

        # Run strategy tick
        try:
            strategy.tick(current_price=tick_price, market_context=market_context)
            
            # Capture simulation logs from strategy
            if hasattr(strategy, 'sim_logs') and strategy.sim_logs:
                sim_logs.extend(strategy.sim_logs)
                strategy.sim_logs = []
        except Exception as e:
            logging.error(f"SIM ERROR: Strategy tick failed at step {i}: {e}")

    # Collect results
    import math
    trades = strategy.db.trades
    total_realized_profit = 0.0
    for t in trades:
        p = t.get('net_profit')
        if p is not None:
            try:
                fp = float(p)
                if not math.isnan(fp):
                    total_realized_profit += fp
            except:
                pass
    
    # Calculate Unrealized Profit
    unrealized_profit = 0
    final_price = 0
    if strategy.current_candle:
        c = strategy.current_candle
        final_price = float(c.get('trade_price') or c.get('close') or 0)
        
        for split in strategy.splits:
            if split.status in ["BUY_FILLED", "PENDING_SELL"]:
                if split.actual_buy_price and split.buy_volume:
                    current_val = final_price * split.buy_volume
                    buy_cost = split.actual_buy_price * split.buy_volume
                    unrealized_profit += (current_val - buy_cost)

    final_balance = strategy.budget + total_realized_profit + unrealized_profit
    
    return {
        "trades": trades,
        "trade_count": len(trades),
        "debug_logs": sim_logs,
        "total_realized_profit": total_realized_profit,
        "total_profit": total_realized_profit,
        "unrealized_profit": unrealized_profit,
        "final_balance": final_balance,
        "final_price": final_price,
        "splits": [s.__dict__ for s in strategy.splits],
        "events": strategy.sim_events,
        "config": strategy.config.model_dump(),
        "watch_intervals": watch_intervals
    }
