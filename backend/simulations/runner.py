import logging
import pandas as pd
from datetime import datetime, timezone
from .config import SimulationConfig
from .price import PriceSimulationStrategy
from .rsi import RSISimulationStrategy

def expand_daily_to_hourly(daily_candles):
    """
    Interpolate Daily candles into 24 Hourly candles.
    Path: Open -> Low -> High -> Close (Simple ZigZag approximation)
    This allows testing intraday logic using only Daily data.
    """
    hourly_candles = []
    
    for i, day in enumerate(daily_candles):
        # Extract OHLC
        o = float(day.get('opening_price') or day.get('open'))
        h = float(day.get('high_price') or day.get('high'))
        l = float(day.get('low_price') or day.get('low'))
        c = float(day.get('trade_price') or day.get('close'))
        
        # Timestamp (KST string or Unix)
        ts_raw = day.get('timestamp') or day.get('time') or day.get('candle_date_time_kst')
        start_dt = None
        if isinstance(ts_raw, (int, float)):
             if ts_raw > 10000000000: ts_raw /= 1000.0
             start_dt = datetime.fromtimestamp(ts_raw, timezone.utc)
        else:
             # Assume ISO string
             try:
                 start_dt = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                 # If KST string (no offset), assume it's KST -> convert to UTC
                 if '+' not in ts_raw and 'Z' not in ts_raw:
                     # It's naive KST. Subtract 9 hours to get UTC.
                     # And MAKE IT AWARE UTC.
                     start_dt = (start_dt - pd.Timedelta(hours=9)).replace(tzinfo=timezone.utc)
             except:
                 start_dt = datetime.now(timezone.utc) # Fallback

        # Generate 24 hours
        # Path: 
        # 0-7h: Open -> Low
        # 8-15h: Low -> High
        # 16-23h: High -> Close
        
        # Determine Trend (Bullish or Bearish)
        is_bullish = c >= o
        
        for hour in range(24):
            # Timestamp: start_dt + hour
            current_dt = start_dt + pd.Timedelta(hours=hour)
            
            # Dynamic Time Distribution
            # Short phase: 4 hours (0-3)
            # Long phase: 16 hours (4-19)
            # End phase: 4 hours (20-23)
            
            phase1_end = 4.0
            phase2_end = 20.0
            
            price = o # Default
            
            if is_bullish:
                # Pattern: Open -> Low -> High -> Close
                # 0-3h: O -> L (Dip)
                # 4-19h: L -> H (Rise)
                # 20-23h: H -> C (Settle)
                if hour < phase1_end:
                    ratio = hour / phase1_end
                    price = o + (l - o) * ratio
                elif hour < phase2_end:
                    ratio = (hour - phase1_end) / (phase2_end - phase1_end)
                    price = l + (h - l) * ratio
                else:
                    ratio = (hour - phase2_end) / (24 - phase2_end)
                    price = h + (c - h) * ratio
            else:
                # Pattern: Open -> High -> Low -> Close (Bearish standard)
                # 0-3h: O -> H (Fake rise)
                # 4-19h: H -> L (Drop)
                # 20-23h: L -> C (Recovery)
                if hour < phase1_end:
                    ratio = hour / phase1_end
                    price = o + (h - o) * ratio
                elif hour < phase2_end:
                    ratio = (hour - phase1_end) / (phase2_end - phase1_end)
                    price = h + (l - h) * ratio
                else:
                    ratio = (hour - phase2_end) / (24 - phase2_end)
                    price = l + (c - l) * ratio
            
            # Limit: Do not generate future candles
            # (Allows simulation up to 'now', avoiding confusing future trades)
            if current_dt > datetime.now(timezone.utc):
                 break

            hourly_candles.append({
                'timestamp': current_dt.timestamp(),
                'opening_price': price,
                'high_price': price,
                'low_price': price,
                'trade_price': price,
                'candle_date_time_kst': (current_dt + pd.Timedelta(hours=9)).isoformat()
            })
            
    return hourly_candles

def run_simulation(sim_config: SimulationConfig):
    # Configure logging for the simulation process
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Expand Daily Candles to Hourly if needed
    # Check if input is Daily (interval ~ 24h)
    candles = sim_config.candles
    is_daily = False
    if len(candles) >= 2:
        c1 = candles[0]
        c2 = candles[1]
        t1 = c1.get('timestamp') or c1.get('time')
        t2 = c2.get('timestamp') or c2.get('time')
        
        # Normalize to seconds if in milliseconds
        if t1 and t1 > 10000000000: t1 /= 1000.0
        if t2 and t2 > 10000000000: t2 /= 1000.0
        # print(f"SIM DEBUG: t1={t1}, t2={t2}, type={type(t1)}")
        
        if t1 and t2:
            diff = abs(t2 - t1)
            # print(f"SIM DEBUG: diff={diff}")
            if diff >= 80000: # ~24 hours
                is_daily = True
    
    # print(f"SIM DEBUG: is_daily={is_daily}")
    
    if is_daily:
        # print(f"SIM: Detected Daily Candles ({len(candles)}). Expanding to Hourly for Intraday Simulation.")
        expanded_candles = expand_daily_to_hourly(candles)
        # print(f"SIM: Expanded to {len(expanded_candles)} hourly candles.")
        # Use expanded candles for simulation loop
        sim_config.candles = expanded_candles
    
    # Initialize Strategy
    if sim_config.strategy_config.strategy_mode == "RSI":
        strategy = RSISimulationStrategy(sim_config.strategy_config, sim_config.budget, sim_config.candles)
    else:
        strategy = PriceSimulationStrategy(sim_config.strategy_config, sim_config.budget, sim_config.candles)

    candles = sim_config.candles
    start_idx = sim_config.start_index
    sim_logs = [] # Init here to capture early logs
    
    sim_logs.append(f"DEBUG: Runner received start_idx={start_idx}, total_candles={len(candles)}, is_daily={is_daily}")

    # Handle expand adjustment for start_index
    daily_closes_history = []
    if is_daily:
        original_start_idx = start_idx
        start_idx = start_idx * 24
        
        # Safety: If start_idx exceeds new length (due to future cropping), clamp it or adjust
        if start_idx >= len(candles):
            # If start index is beyond available data, try to simulate at least the last 24 hours if possible
             start_idx = max(0, len(candles) - 24)
             print(f"SIM WARNING: Adjusted start_index clamped to {start_idx} (Max available: {len(candles)})")

        # Build history from expanded candles (taking every 24th close, i.e., index 23, 47, ...)
        # Only up to the point before start_idx
        for i in range(23, start_idx, 24):
            if i < len(candles):
                c = candles[i]
                price = c.get('trade_price') or c.get('close')
                daily_closes_history.append(float(price))
                
        # print(f"SIM: Adjusted start_index from {original_start_idx} (Days) to {start_idx} (Hours). Pre-filled {len(daily_closes_history)} daily history candles.")
    
    # Initialize strategy config using start_idx price
    # Initialize strategy config using start_idx price
    # sim_logs initialized above
    if start_idx < len(candles):
        start_price = candles[start_idx].get('close') or candles[start_idx].get('trade_price')
    else:
        start_price = 0
            
    start_ts_str = candles[start_idx].get('candle_date_time_kst') or candles[start_idx].get('candle_date_time_utc')
    msg = f"SIM: Start Price: {start_price}, Start Index: {start_idx}/{len(candles)}, Start Time: {start_ts_str}"
    sim_logs.append(msg)
    
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
    print(msg) # Print to console for immediate check

    # Pre-compute daily candles (keep for get_candles usage)
    if strategy.config.strategy_mode == "RSI":
        # print(f"SIM: Pre-computing daily candles...")
        daily_candles = strategy._precompute_daily_candles()
        msg = f"SIM: Pre-computed {len(daily_candles)} daily candles for RSI calculation"
        sim_logs.append(msg)
        logging.info(msg)
        # print(msg)
        
    # Import indicators
    from utils.indicators import calculate_rsi
    
    # Track Trailing Buy Watch Intervals
    watch_intervals = []
    was_watching = False
    current_watch_start = None

    # Run simulation loop
    # print(f"SIM: Starting simulation loop from {start_idx} to {len(candles)}")
    for i in range(start_idx, len(candles)):
        # if i % 100 == 0:
        #     print(f"SIM: Processing candle {i}/{len(candles)}")

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

        # DYNAMIC RSI CALCULATION (Every Hour)
        if strategy.config.strategy_mode == "RSI":
            # 1. Update Strategy Date/Time context
            # (Handled by strategy.get_current_time_kst() reading current_candle)
            
            # 2. Calculate "Today's" Dynamic RSI
            current_close = float(tick_price)
            
            # prev_rsi (Yesterday) - Calculated from day closes UP TO yesterday
            prev_rsi = calculate_rsi(daily_closes_history, strategy.config.rsi_period)
            
            # current_rsi_daily (Dynamic Today) - Append current close to history TEMPORARILY
            current_history = daily_closes_history + [current_close]
            current_rsi_daily = calculate_rsi(current_history, strategy.config.rsi_period)
            
            # Update Strategy State
            strategy.rsi_logic.prev_rsi = prev_rsi
            strategy.rsi_logic.current_rsi_daily = current_rsi_daily
            
        # Price Grid Logic (Classic) initialization
        if strategy.config.strategy_mode != "RSI":
            # Track Watch Intervals (Trailing Buy)
            is_currently_watching = getattr(strategy.price_logic, 'is_watching', False)
            
            if is_currently_watching and not was_watching:
                # Start of a watch period
                raw_ts = candle.get('timestamp') or candle.get('time')
                if raw_ts and raw_ts > 10000000000: raw_ts /= 1000.0
                current_watch_start = raw_ts
                
            elif not is_currently_watching and was_watching:
                # End of a watch period
                if current_watch_start:
                    raw_end = candle.get('timestamp') or candle.get('time')
                    if raw_end and raw_end > 10000000000: raw_end /= 1000.0
                    watch_intervals.append({'start': current_watch_start, 'end': raw_end})
                    current_watch_start = None
            
            was_watching = is_currently_watching

        # Run strategy tick
        try:
            strategy.tick(current_price=tick_price)
            
            # Capture simulation logs from strategy (if any)
            if hasattr(strategy, 'sim_logs') and strategy.sim_logs:
                sim_logs.extend(strategy.sim_logs)
                strategy.sim_logs = []
        except Exception as e:
            print(f"SIM ERROR: Strategy tick failed at step {i}: {e}")
            import traceback
            traceback.print_exc()

        # Handle Day Boundary
        # If is_daily=True (expanded candles), then index 23, 47... is end of day.
        # i + 1 is divisible by 24 -> End of Day
        if is_daily and (i + 1) % 24 == 0:
             # End of day, commit the close to history
             daily_closes_history.append(float(candle['close']))

        # Cleanup / Intra-candle logic (Same as original)
        for split in list(strategy.splits):
            if split.status == "PENDING_BUY":
                strategy._check_buy_order(split)
        
        for split in list(strategy.splits):
            if split.status == "BUY_FILLED":
                if strategy.config.strategy_mode != "RSI":
                    strategy._create_sell_order(split)
                
        for split in list(strategy.splits):
            if split.status == "PENDING_SELL":
                strategy._check_sell_order(split)
        
        if strategy.config.strategy_mode != "RSI":
            strategy.price_logic._check_create_new_buy_split(tick_price)

    # Collect results
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
    
    # Calculate Unrealized Profit for active splits
    unrealized_profit = 0
    if strategy.current_candle:
        # Get last price (close)
        c = strategy.current_candle
        current_price = c.get('trade_price') or c.get('close') or c.get('c') or 0
        current_price = float(current_price)
        
        for split in strategy.splits:
            if split.status in ["BUY_FILLED", "PENDING_SELL"]:
                # Calculate value change: (Current Price - Buy Price) * Volume
                if split.actual_buy_price and split.buy_volume:
                    # Note: We should use current_price vs actual cost
                    current_val = current_price * split.buy_volume
                    buy_cost = split.actual_buy_price * split.buy_volume
                    diff = current_val - buy_cost
                    unrealized_profit += diff

    final_balance = strategy.budget + total_realized_profit + unrealized_profit # Total Equity
    # Logic for final balance:
    # Initial Budget - Cost of Active Splits + Realized Profit + Cash Left?
    # Actually strategy.budget tracks "available budget" usually?
    # No, strategy.budget is usually static in config or decremented?
    # In SevenSplitStrategy, budget is used to check limit.
    # self.splits[].buy_amount is invested.
    
    # Let's just return what we have
    return {
        "trades": trades,
        "trade_count": len(trades),
        "debug_logs": sim_logs,
        "total_realized_profit": total_realized_profit,
        "total_profit": total_realized_profit, # Frontend expects this key
        "unrealized_profit": unrealized_profit,
        "final_balance": final_balance, # Approximate
        "splits": [s.__dict__ for s in strategy.splits], # Return active splits
        "config": strategy.config.model_dump(),
        "watch_intervals": watch_intervals
    }
