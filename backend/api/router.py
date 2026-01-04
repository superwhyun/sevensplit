import io
import csv
import time
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from core.config import db, strategy_service, exchange, real_exchange, shared_prices, accounts_cache
from database import get_candle_db
from core.schemas import (
    CreateStrategyRequest, CommandRequest, ConfigRequest, 
    ManualTargetRequest, UpdateNameRequest, SimulationRequest,
    DebugRSIRequest
)
from core.engine import calculate_portfolio
from services.simulation_service import simulate_strategy_from_time_logic

router = APIRouter()

@router.get("/strategies")
def get_strategies():
    """List all strategies"""
    return [
        {
            "id": s.strategy_id,
            "name": db.get_strategy(s.strategy_id).name,
            "ticker": s.ticker,
            "budget": s.budget,
            "is_running": s.is_running
        }
        for s in strategy_service.get_all_strategies()
    ]

@router.post("/strategies")
def create_strategy(req: CreateStrategyRequest):
    """Create a new strategy"""
    try:
        s_id = strategy_service.create_strategy(
            name=req.name,
            ticker=req.ticker,
            budget=req.budget,
            config=req.config.model_dump()
        )
        return {"status": "success", "strategy_id": s_id, "message": "Strategy created"}
    except Exception as e:
        logging.error(f"Failed to create strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int):
    """Delete a strategy"""
    try:
        strategy_service.delete_strategy(strategy_id)
        return {"status": "success", "message": "Strategy deleted"}
    except Exception as e:
        logging.error(f"Failed to delete strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies/{strategy_id}/events")
def get_strategy_events(strategy_id: int, page: int = 1, limit: int = 10):
    """Get system events for a strategy"""
    try:
        return db.get_events(strategy_id, page=page, limit=limit)
    except Exception as e:
        logging.error(f"Failed to fetch events: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch events")

@router.delete("/strategies/{strategy_id}/events")
def delete_strategy_events(strategy_id: int):
    """Delete all system events for a strategy"""
    try:
        db.delete_events(strategy_id)
        return {"status": "success", "message": "Events cleared"}
    except Exception as e:
        logging.error(f"Failed to clear events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies/{strategy_id}/export")
def export_trades(strategy_id: int):
    """Export trades to CSV"""
    trades = db.get_trades(strategy_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Ticker", "Buy Price", "Sell Price", "Volume", "Gross Profit", "Net Profit", "Fee", "Hold Time", "Closed At"])
    for t in trades:
        writer.writerow([t.id, t.ticker, t.avg_buy_price, t.sell_price, t.volume, t.gross_profit, t.net_profit, t.total_fee, t.hold_time_seconds, t.closed_at])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=trades_strategy_{strategy_id}.csv"}
    )

@router.get("/strategies/{strategy_id}/status")
def get_status(strategy_id: int):
    strategy = strategy_service.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    current_price = shared_prices.get(strategy.ticker)
    if not current_price:
        try:
            current_price = exchange.get_current_price(strategy.ticker)
        except:
            current_price = 0.0

    state = strategy.get_state(current_price=current_price)

    # Return the complete state from strategy
    return state

@router.get("/snapshot")
def get_full_snapshot():
    """Aggregate all strategies' status plus portfolio for websocket push."""
    strategies_data = []

    # Use cached accounts if possible in _calculate_portfolio
    portfolio = calculate_portfolio(prices=shared_prices, accounts_raw=accounts_cache.get('data'))

    for s_id, strategy in strategy_service.strategies.items():
        current_price = shared_prices.get(strategy.ticker, 0.0)
        state = strategy.get_state(current_price=current_price)

        # Optimization: Don't send config over websocket to prevent unwanted form resets 
        # on the frontend. Other dynamic data like splits and trade_history are kept.
        state.pop('config', None)

        strategies_data.append(state)

    return {
        "portfolio": portfolio,
        "strategies": strategies_data,
        "timestamp": time.time()
    }

@router.get("/accounts")
def get_accounts():
    """Expose detailed exchange account info for dashboard or debugging."""
    try:
        return exchange.get_accounts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/candles")
def get_candles(market: str, count: int = 200, interval: str = "minutes/5", to: Optional[str] = None):
    try:
        candle_db = get_candle_db()
        
        # Calculate exact interval unit in seconds
        if "minutes" in interval:
            unit_secs = int(interval.split('/')[-1]) * 60
        else:
            unit_secs = 86400

        # Determine reference end time
        if to:
            try:
                from datetime import datetime
                to_dt = datetime.fromisoformat(to.replace('Z', '+00:00'))
                ref_end_ts = to_dt.timestamp()
            except:
                ref_end_ts = time.time()
        else:
            ref_end_ts = time.time()

        # Align to interval boundary for deterministic cache check
        aligned_end_ts = (ref_end_ts // unit_secs) * unit_secs
        start_ts = aligned_end_ts - (unit_secs * (count - 1))
        
        # 1. Check Cache
        db_candles = candle_db.get_candles(market, interval, start_ts, aligned_end_ts)
        
        # 2. Strict Gap/Staleness Detection
        needs_fetch = False
        reason = ""
        if len(db_candles) < count:
            # Count mismatch: gaps detected or missing history
            needs_fetch = True
            reason = f"Insufficient count (found {len(db_candles)}/{count})"
        elif not to:
            # For live requests, check if the latest candle in DB is current
            if (time.time() - db_candles[-1]['timestamp']) > unit_secs * 1.5:
                needs_fetch = True
                stale_sec = int(time.time() - db_candles[-1]['timestamp'])
                reason = f"Stale data (last candle {stale_sec}s ago)"
        
        # 3. If cache is complete, return it
        if not needs_fetch:
             logging.info(f"📦 [CACHE] Serving {len(db_candles)} {interval} candles from DB for {market}")
             # Sort DESC (latest first) for frontend compatibility
             db_candles.sort(key=lambda x: x['timestamp'], reverse=True)
             return [{
                 **c,
                 'market': c['ticker'],
                 'timestamp': int(c['timestamp'] * 1000)
             } for c in db_candles[:count]]

        # 4. Fetch from Exchange & Save to Cache (Gap filling)
        logging.info(f"🌐 [UPBIT API] Fetching {interval} for {market} (to={to}) - Reason: {reason}")
        fetched = real_exchange.get_candles(market, count=count, interval=interval, to=to)
        if fetched:
            # DEBUG: Log the first and last candle to verify interval
            if len(fetched) >= 2:
                f_ts = fetched[0].get('timestamp', 0)
                l_ts = fetched[-1].get('timestamp', 0)
                if f_ts > 10000000000: f_ts /= 1000.0 # Normalize MS
                if l_ts > 10000000000: l_ts /= 1000.0
                logging.info(f"✅ [UPBIT API] Fetched {len(fetched)} candles. Range: {f_ts} to {l_ts}")

            candle_db.save_candles(market, interval, fetched)
            return fetched
            
        # Fallback to whatever cache we have if API fails
        db_candles.sort(key=lambda x: x['timestamp'], reverse=True)
        return [{
            **c,
            'market': c['ticker'],
            'timestamp': int(c['timestamp'] * 1000)
        } for c in db_candles]
    except Exception as e:
        logging.error(f"Error in get_candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bot/start")
def start_bot(cmd: CommandRequest):
    try:
        strategy_service.start_strategy(cmd.strategy_id)
        return {"status": "success", "message": "Bot started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bot/stop")
def stop_bot(cmd: CommandRequest):
    try:
        strategy_service.stop_strategy(cmd.strategy_id)
        return {"status": "success", "message": "Bot stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/config")
def update_config(req: ConfigRequest):
    try:
        logging.info(f"[update_config] Received config update for strategy {req.strategy_id}")
        logging.info(f"[update_config] Config: {req.config.model_dump()}")
        logging.info(f"[update_config] Budget: {req.budget}")
        strategy_service.update_config(req.strategy_id, req.config, req.budget)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        logging.error(f"[update_config] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{strategy_id}/manual-target")
def set_manual_target(strategy_id: int, req: ManualTargetRequest):
    try:
        strategy_service.set_manual_target(strategy_id, req.target_price)
        return {"status": "success", "message": "Manual target updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{strategy_id}/name")
def update_strategy_name(strategy_id: int, req: UpdateNameRequest):
    try:
        strategy = db.get_strategy(strategy_id)
        if not strategy:
             raise HTTPException(status_code=404, detail="Strategy not found")
        strategy.name = req.name
        db.session.commit()
        return {"status": "success", "message": "Strategy name updated"}
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{strategy_id}/simulate")
def simulate_strategy_from_time(strategy_id: int, req: SimulationRequest):
    return simulate_strategy_from_time_logic(strategy_id, req.start_time)

@router.post("/bot/reset")
def reset_strategy(cmd: CommandRequest):
    """Reset a specific strategy"""
    try:
        strategy_service.reset_strategy(cmd.strategy_id)
        return {"status": "success", "message": "Strategy reset"}
    except Exception as e:
        logging.error(f"Failed to reset strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/debug/rsi")
def set_debug_rsi(req: DebugRSIRequest):
    """[MOCK ONLY] Force set RSI values for testing."""
    strategy = strategy_service.get_strategy(req.strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Set values on strategy instance
    strategy.debug_rsi = req.rsi
    if req.prev_rsi is not None:
        strategy.debug_prev_rsi = req.prev_rsi
    if req.rsi_short is not None:
        strategy.debug_rsi_short = req.rsi_short
        
    return {"status": "success", "rsi": req.rsi, "prev_rsi": req.prev_rsi}

@router.post("/debug/reset-all")
def reset_all_mock():
    """Reset all strategies and exchange (MOCK mode only)"""
    try:
        if not hasattr(exchange, "reset_all"):
             raise HTTPException(status_code=400, detail="Reset only supported in MOCK mode")
        
        # 1. Stop all strategies
        for s_id in list(strategy_service.strategies.keys()):
            strategy_service.stop_strategy(s_id)
        
        # 2. Reset Exchange (Mock server)
        exchange.reset_all()
        
        # 3. Clear DB and reload
        db.clear_all_data()
        strategy_service.strategies.clear()
        strategy_service.load_strategies()
        
        return {"status": "success", "message": "System reset completed"}
    except Exception as e:
        logging.error(f"Failed to reset system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio")
def get_portfolio():
    # Use cached accounts if available and valid
    current_time = time.time()
    accounts_raw = None
    
    try:
        if current_time - accounts_cache['timestamp'] < 10 and accounts_cache['data']:
            accounts_raw = accounts_cache['data']
        else:
             accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
             accounts_cache['data'] = accounts_raw
             accounts_cache['timestamp'] = current_time
    except Exception:
        pass

    return calculate_portfolio(prices=shared_prices, accounts_raw=accounts_raw)
