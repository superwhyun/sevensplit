import io
import csv
import time
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from core.config import (
    db,
    strategy_service,
    settings_service,
    exchange_service,
    real_exchange,
    shared_prices,
    accounts_cache,
    simulation_service,
)
from database import get_candle_db
from core.schemas import (
    CreateStrategyRequest, CommandRequest, ConfigRequest,
    ManualTargetRequest, UpdateNameRequest,
    DebugRSIRequest,
    BacktestRequest,
    LiveSimulationStartRequest,
    SettingsUpdateRequest, ValidateKeysRequest, ModeSwitchRequest,
)
from core.engine import calculate_portfolio
from services.settings_service import SettingsError

router = APIRouter()


# ---------------------------------------------------------------- settings / setup
@router.get("/setup/status")
def get_setup_status():
    """What the first screen needs: keys present, mode, whether any strategy exists."""
    return settings_service.get_setup_status()


@router.get("/settings")
def get_settings():
    """Runtime settings with secrets masked."""
    return settings_service.get_public_settings()


@router.put("/settings")
def update_settings(req: SettingsUpdateRequest):
    """Save Upbit keys (validated against Upbit first) and/or the paper starting balance."""
    try:
        result = None
        if req.access_key is not None or req.secret_key is not None:
            result = settings_service.update_keys(
                req.access_key or "",
                req.secret_key or "",
                validate=req.validate_keys,
            )
        if req.paper_initial_krw is not None:
            result = settings_service.update_paper_initial_krw(req.paper_initial_krw)
        if req.resume_strategies_on_boot is not None:
            result = settings_service.update_resume_on_boot(req.resume_strategies_on_boot)
        return result or settings_service.get_public_settings()
    except SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"[settings] update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/settings/keys")
def delete_settings_keys():
    try:
        return settings_service.clear_keys()
    except SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settings/validate")
def validate_settings_keys(req: ValidateKeysRequest):
    """Check keys against Upbit without saving. Omit both fields to re-check the stored keys."""
    return settings_service.validate_keys(req.access_key, req.secret_key)


@router.post("/settings/mode")
def switch_settings_mode(req: ModeSwitchRequest):
    """Switch between paper (DEV) and live (REAL) trading. Refused while any strategy runs."""
    try:
        return settings_service.switch_mode(req.mode)
    except SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"[settings] mode switch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies")
def get_strategies():
    """List all strategies"""
    return [
        {
            "id": s.strategy_id,
            "name": db.get_strategy(s.strategy_id).name,
            "ticker": s.ticker,
            "budget": s.budget,
            "is_running": s.is_running,
            "mode": strategy_service.current_mode,
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
def get_strategy_events(strategy_id: int, page: int = 1, limit: int = 10, event_types: Optional[str] = None):
    """Get system events for a strategy"""
    try:
        types = None
        if event_types:
            types = [t.strip() for t in event_types.split(",") if t.strip()]
        return db.get_events(strategy_id, page=page, limit=limit, event_types=types)
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
    writer.writerow([
        "ID", "Ticker", "Split ID", "Buy Price", "Sell Price", "Volume",
        "Buy Amount", "Sell Amount", "Gross Profit", "Net Profit", "Fee",
        "Profit Rate (%)", "Hold Time (s)", "Bought At", "Closed At",
    ])
    for t in trades:
        hold_time_seconds = None
        if t.bought_at and t.timestamp:
            hold_time_seconds = int((t.timestamp - t.bought_at).total_seconds())
        writer.writerow([
            t.id, t.ticker, t.split_id, t.buy_price, t.sell_price, t.coin_volume,
            t.buy_amount, t.sell_amount, t.gross_profit, t.net_profit, t.total_fee,
            t.profit_rate, hold_time_seconds,
            t.bought_at.isoformat() if t.bought_at else "",
            t.timestamp.isoformat() if t.timestamp else "",
        ])

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
            current_price = exchange_service.get_current_price(strategy.ticker)
        except Exception:
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
        return exchange_service.get_accounts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

_POPULAR_TICKERS = ("KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-DOGE")
_markets_cache = {"data": [], "timestamp": 0.0}


@router.get("/market/tickers")
def get_market_tickers():
    """KRW markets for pickers. Popular coins first, then alphabetical. Cached for an hour."""
    now = time.time()
    if not _markets_cache["data"] or now - _markets_cache["timestamp"] > 3600:
        try:
            markets = real_exchange.get_markets()
            if markets:
                _markets_cache["data"] = markets
                _markets_cache["timestamp"] = now
        except Exception as e:
            logging.warning(f"Market list refresh failed: {e}")
    markets = _markets_cache["data"] or [
        {"market": t, "korean_name": t.split("-")[1], "english_name": t.split("-")[1]} for t in _POPULAR_TICKERS
    ]
    by_market = {m["market"]: m for m in markets}
    ordered = [by_market[t] for t in _POPULAR_TICKERS if t in by_market]
    rest = sorted((m for m in markets if m["market"] not in _POPULAR_TICKERS), key=lambda m: m["market"])
    return {"popular": [m["market"] for m in ordered], "markets": ordered + rest}


@router.get("/market/price")
def get_market_price(ticker: str):
    """Current price for one KRW market (public data, works in both modes)."""
    ticker = (ticker or "").strip().upper()
    if not ticker.startswith("KRW-"):
        raise HTTPException(status_code=400, detail="ticker must look like KRW-BTC")
    price = shared_prices.get(ticker)
    if not price:
        try:
            price = real_exchange.get_current_price(ticker)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"시세 조회 실패: {e}")
    if not price:
        raise HTTPException(status_code=404, detail=f"{ticker} 시세를 찾을 수 없습니다.")
    return {"ticker": ticker, "price": float(price), "timestamp": time.time()}


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

@router.post("/bot/hard-stop")
def hard_stop_bot(cmd: CommandRequest):
    try:
        strategy_service.hard_stop_strategy(cmd.strategy_id)
        return {"status": "success", "message": "Bot hard-stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/config")
def update_config(req: ConfigRequest):
    try:
        logging.info(f"[update_config] Received config update for strategy {req.strategy_id}")
        logging.info(f"[update_config] Config: {req.config.model_dump()}")
        logging.info(f"[update_config] Budget: {req.budget}")
        strategy_service.update_config(req.strategy_id, req.config, req.budget)
        synced = simulation_service.update_live_config(req.strategy_id, req.config, req.budget)
        if synced > 0:
            logging.info(f"[update_config] Synced config to {synced} live simulation session(s)")
        return {
            "status": "success",
            "message": "Configuration updated",
            "synced_live_sessions": synced,
        }
    except Exception as e:
        logging.error(f"[update_config] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{strategy_id}/manual-target")
def set_manual_target(strategy_id: int, req: ManualTargetRequest):
    try:
        strategy_service.set_manual_target(strategy_id, req.target_price)
        synced = simulation_service.update_live_manual_target(strategy_id, req.target_price)
        if synced > 0:
            logging.info(f"[manual_target] Synced manual target to {synced} live simulation session(s)")
        return {
            "status": "success",
            "message": "Next buy target updated",
            "synced_live_sessions": synced,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{strategy_id}/name")
def update_strategy_name(strategy_id: int, req: UpdateNameRequest):
    strategy = db.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    try:
        db.update_strategy_name(strategy_id, req.name)
        return {"status": "success", "message": "Strategy name updated"}
    except Exception as e:
        logging.error(f"Failed to update strategy name for {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bot/reset")
def reset_strategy(cmd: CommandRequest):
    """Reset a specific strategy"""
    try:
        # 1. Stop any active simulations for this strategy
        try:
            simulation_service.stop_all_live_by_strategy(cmd.strategy_id)
        except Exception as sim_err:
            logging.warning(f"Failed to stop simulation during reset: {sim_err}")

        # 2. Reset strategy data (splits, trades, state)
        strategy_service.reset_strategy(cmd.strategy_id)
        
        return {"status": "success", "message": "Strategy reset"}
    except Exception as e:
        logging.error(f"Failed to reset strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/debug/rsi")
def set_debug_rsi(req: DebugRSIRequest):
    """Force set RSI values for testing."""
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

@router.get("/portfolio")
def get_portfolio():
    # Use cached accounts if available and valid
    current_time = time.time()
    accounts_raw = None
    
    try:
        if current_time - accounts_cache['timestamp'] < 10 and accounts_cache['data']:
            accounts_raw = accounts_cache['data']
        else:
            accounts_raw = exchange_service.get_accounts() or []
            accounts_cache['data'] = accounts_raw
            accounts_cache['timestamp'] = current_time
    except Exception as e:
        logging.debug(f"Portfolio accounts refresh skipped: {e}")

    return calculate_portfolio(prices=shared_prices, accounts_raw=accounts_raw)


@router.get("/daily-profits")
def get_daily_profits(days: int = 30):
    """Get daily realized profit aggregation in KST."""
    return db.get_daily_profits(days=days)


@router.post("/simulations/backtest")
def run_backtest(req: BacktestRequest):
    try:
        return simulation_service.run_backtest(
            strategy_id=req.strategy_id,
            start_time=req.start_time,
            end_time=req.end_time,
            exec_interval=req.exec_interval,
            max_candles=req.max_candles,
            initial_krw=req.initial_krw,
        )
    except Exception as e:
        logging.error(f"Backtest failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulations/live/start")
def start_live_simulation(req: LiveSimulationStartRequest):
    try:
        return simulation_service.start_live(
            strategy_id=req.strategy_id,
            exec_interval=req.exec_interval,
            replay_days=req.replay_days,
            poll_seconds=req.poll_seconds,
            initial_krw=req.initial_krw,
        )
    except Exception as e:
        logging.error(f"Live simulation start failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulations/live/{session_id}/stop")
def stop_live_simulation(session_id: str):
    try:
        return simulation_service.stop_live(session_id)
    except Exception as e:
        logging.error(f"Live simulation stop failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulations/live/{session_id}/pause-buying")
def pause_live_buying(session_id: str):
    try:
        return simulation_service.pause_live_buying(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Live simulation pause failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulations/live/{session_id}/resume-buying")
def resume_live_buying(session_id: str):
    try:
        return simulation_service.resume_live_buying(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Live simulation resume failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/simulations/live/{session_id}")
def get_live_simulation(session_id: str):
    try:
        return simulation_service.get_live(session_id)
    except Exception as e:
        logging.error(f"Live simulation status failed: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/simulations/live")
def list_live_simulations():
    return {"sessions": simulation_service.list_live()}
