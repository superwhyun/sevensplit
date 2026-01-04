import logging
from datetime import datetime, timezone, timedelta
from database import get_db, get_candle_db
from fastapi import HTTPException
from core.config import exchange, real_exchange, db
from models.strategy_state import StrategyConfig
from simulation import run_simulation, SimulationConfig

def simulate_strategy_from_time_logic(strategy_id: int, start_time_str: str):
    """Run simulation for a specific strategy starting from a given time"""
    logging.info(f"Received simulation request for strategy {strategy_id} from {start_time_str}")
    
    s_rec = db.get_strategy(strategy_id)
    if not s_rec:
        logging.error(f"Strategy {strategy_id} not found in DB")
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    config_dict = {
        'investment_per_split': s_rec.investment_per_split,
        'min_price': s_rec.min_price,
        'max_price': s_rec.max_price,
        'buy_rate': s_rec.buy_rate,
        'sell_rate': s_rec.sell_rate,
        'fee_rate': s_rec.fee_rate,
        'tick_interval': s_rec.tick_interval,
        'rebuy_strategy': s_rec.rebuy_strategy,
        'max_trades_per_day': s_rec.max_trades_per_day,
        
        'strategy_mode': s_rec.strategy_mode,
        'rsi_period': s_rec.rsi_period,
        'rsi_timeframe': s_rec.rsi_timeframe,

        'rsi_buy_max': s_rec.rsi_buy_max,
        'rsi_buy_first_threshold': s_rec.rsi_buy_first_threshold,
        'rsi_buy_first_amount': s_rec.rsi_buy_first_amount,
        'rsi_buy_next_threshold': s_rec.rsi_buy_next_threshold,
        'rsi_buy_next_amount': s_rec.rsi_buy_next_amount,

        'rsi_sell_min': s_rec.rsi_sell_min,
        'rsi_sell_first_threshold': s_rec.rsi_sell_first_threshold,
        'rsi_sell_first_amount': s_rec.rsi_sell_first_amount,
        'rsi_sell_next_threshold': s_rec.rsi_sell_next_threshold,
        'rsi_sell_next_amount': s_rec.rsi_sell_next_amount,

        'stop_loss': s_rec.stop_loss,
        'max_holdings': s_rec.max_holdings,

        'use_trailing_buy': s_rec.use_trailing_buy,
        'trailing_buy_rebound_percent': s_rec.trailing_buy_rebound_percent,
        'trailing_buy_batch': getattr(s_rec, 'trailing_buy_batch', True),
        'price_segments': getattr(s_rec, 'price_segments', []) or []
    }
    candle_db = get_candle_db()
    config = StrategyConfig(**config_dict)
    ticker = s_rec.ticker
    budget = s_rec.budget
    
    logging.info(f"SIM START: Loaded Strategy {strategy_id} ({ticker}) from DB. Budget={budget}")

    interval = "minutes/5"
    
    start_dt = None
    try:
        if isinstance(start_time_str, (int, float)):
            start_dt = datetime.fromtimestamp(start_time_str, tz=timezone.utc)
        else:
            start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
    except Exception as e:
        logging.warning(f"Failed to parse start_time {start_time_str}: {e}")
        start_dt = datetime.now(timezone.utc)

    # Determine required time range
    # Standard RSI(14) needs at least 15 candles. Let's take 1 day (288 candles) for robust indicators.
    start_ts = start_dt.timestamp()
    history_buffer = 24 * 60 * 60 # 1 day
    warmup_start_ts = start_ts - history_buffer
    now_ts = datetime.now(timezone.utc).timestamp()

    # 1. Try to get from local Market DB cache
    candles = candle_db.get_candles(ticker, interval, warmup_start_ts)
    
    # 2. Check if we have sufficient data
    needs_fetch = False
    if not candles:
        needs_fetch = True
    else:
        oldest_ts = candles[0]['timestamp']
        latest_ts = candles[-1]['timestamp']
        if oldest_ts > warmup_start_ts + 600: # Allow 10 min tolerance
            needs_fetch = True
        elif latest_ts < now_ts - 1200: # More than 20 min gap from now
            needs_fetch = True

    fetch_logs = []
    if needs_fetch:
        logging.info(f"🌐 [UPBIT API] (SIM) Market Cache miss for {ticker} ({interval}). Fetching from exchange...")
        to_cursor = None
        max_pages = 20 
        pages_fetched = 0
        
        while pages_fetched < max_pages:
            try:
                batch = real_exchange.get_candles(ticker, count=200, interval=interval, to=to_cursor)
                if not batch:
                    break
                
                candle_db.save_candles(ticker, interval, batch)
                
                # Check how far back we've reached
                oldest_in_batch = batch[-1]
                o_ts = oldest_in_batch.get('timestamp') or oldest_in_batch.get('time')
                if o_ts and o_ts > 10000000000: o_ts /= 1000.0
                
                msg = f"FETCH: Page {pages_fetched+1}, Oldest={oldest_in_batch.get('candle_date_time_kst')}"
                fetch_logs.append(msg)
                logging.info(msg)

                if o_ts and o_ts < warmup_start_ts:
                    break
                
                to_cursor = oldest_in_batch.get('candle_date_time_kst')
                pages_fetched += 1
                import time
                time.sleep(0.1) 
                
                if len(batch) < 200:
                    break
            except Exception as e:
                logging.error(f"Error during simulation fetch: {e}")
                break
        
        # Re-load from Market DB after fetching
        candles = candle_db.get_candles(ticker, interval, warmup_start_ts)

    if not candles:
        logging.error("No 5-minute candles available for simulation")
        raise HTTPException(status_code=500, detail="Failed to retrieve candle data for simulation")

    logging.info(f"SIM: Prepared {len(candles)} candles for ticker {ticker}")
    
    # Find start_index for the runner (the first candle at or after start_dt)
    start_index = 0
    for i, c in enumerate(candles):
        if c['timestamp'] >= start_ts:
            start_index = i
            break
            
    if start_index == -1:
        start_index = 0

    sim_config = SimulationConfig(
        strategy_config=config,
        candles=candles,
        start_index=start_index,
        start_time=start_dt.timestamp(),
        ticker=ticker,
        budget=budget
    )

    try:
        result = run_simulation(sim_config)
        if 'debug_logs' in result:
             result['debug_logs'].extend(fetch_logs)
        return result
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        logging.error(f"Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=error_detail)
