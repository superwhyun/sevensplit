import time
from database import get_db, get_candle_db
import logging
import threading
from core.config import (
    strategy_service, exchange, shared_prices, accounts_cache, 
    candle_cache, current_mode, db
)

def calculate_portfolio(prices: dict = {}, accounts_raw: list = None):
    """Internal logic to calculate portfolio status"""
    portfolio = {
        "mode": current_mode,
        "coins": {},
        "accounts": []
    }

    # Get accounts - if prices are provided, use them to avoid redundant API calls
    if hasattr(exchange, "get_accounts"):
        if accounts_raw is not None:
             # Use provided raw accounts
             accounts = []
             for account in accounts_raw:
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                locked = float(account.get('locked', 0))
                ticker = f"KRW-{currency}" if currency and currency != 'KRW' else None
                current_price = 1.0 if currency == 'KRW' else prices.get(ticker, 0.0)
                total_balance = balance + locked
                value = total_balance * current_price if current_price else 0.0
                
                accounts.append({
                    **account,
                    "ticker": ticker,
                    "current_price": current_price,
                    "balance_value": value,
                    "total_balance": total_balance
                })
        elif prices:
            # Temporarily inject prices into accounts manually to avoid extra API call
            accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
            accounts = []
            for account in accounts_raw:
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                locked = float(account.get('locked', 0))
                ticker = f"KRW-{currency}" if currency and currency != 'KRW' else None
                current_price = 1.0 if currency == 'KRW' else prices.get(ticker, 0.0)
                total_balance = balance + locked
                value = total_balance * current_price if current_price else 0.0
                
                accounts.append({
                    **account,
                    "ticker": ticker,
                    "current_price": current_price,
                    "balance_value": value,
                    "total_balance": total_balance
                })
        else:
            accounts = exchange.get_accounts()
    else:
        accounts = []

    # Normalize numeric fields in accounts to avoid stringy zeros
    normalized_accounts = []
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        normalized_accounts.append({
            **acc,
            "balance": float(acc.get("balance", 0.0) or 0.0),
            "locked": float(acc.get("locked", 0.0) or 0.0),
            "avg_buy_price": float(acc.get("avg_buy_price", 0.0) or 0.0),
            "current_price": float(acc.get("current_price", 0.0) or 0.0),
            "balance_value": float(acc.get("balance_value", 0.0) or 0.0),
            "total_balance": float(acc.get("total_balance", 0.0) or 0.0),
        })

    accounts = normalized_accounts
    portfolio["accounts"] = accounts

    # Seed KRW balance
    balance_krw = 0.0
    for acc in accounts:
        if acc.get("currency") == "KRW":
            balance_krw = float(acc.get("total_balance", acc.get("balance", 0.0)))
            break
    portfolio["balance_krw"] = balance_krw

    total_value = 0.0
    for acc in accounts:
        currency = acc.get("currency")
        ticker = acc.get("ticker")
        if currency == "KRW":
            total_value += balance_krw
            continue

        if not ticker:
            ticker = f"KRW-{currency}"
        coin = currency
        current_price = float(acc.get("current_price", 0.0) or 0.0)
        balance_val = float(acc.get("balance_value", 0.0) or 0.0)
        available = float(acc.get("balance", 0.0) or 0.0)
        locked = float(acc.get("locked", 0.0) or 0.0)
        total_balance = float(acc.get("total_balance", available + locked))

        portfolio["coins"][coin] = {
            "ticker": ticker,
            "balance": total_balance,
            "available": available,
            "locked": locked,
            "current_price": current_price,
            "value": balance_val,
            "avg_buy_price": float(acc.get("avg_buy_price", 0.0) or 0.0)
        }
        total_value += balance_val

    portfolio["total_value"] = total_value
    
    # Calculate Total Realized Profit from DB
    try:
        all_trades = db.get_all_trades()
        total_realized_profit = sum(t.net_profit for t in all_trades)
    except Exception as e:
        logging.error(f"Failed to calculate realized profit: {e}")
        total_realized_profit = 0.0

    portfolio["total_realized_profit"] = total_realized_profit
    
    for coin, data in portfolio["coins"].items():
        ticker = data["ticker"]
        try:
            coin_trades = [t for t in all_trades if t.ticker == ticker]
            coin_profit = sum(t.net_profit for t in coin_trades)
            data["realized_profit"] = coin_profit
        except Exception:
            data["realized_profit"] = 0.0

    return portfolio

def run_strategies():
    # Track last tick time for each strategy
    strategies = strategy_service.strategies
    last_tick_time = {s_id: 0.0 for s_id in strategies.keys()}
    
    while True:
        try:
            loop_start_time = time.time()
            
            # Refresh strategy list keys
            strategies = strategy_service.strategies
            current_strategy_ids = list(strategies.keys())
            
            # 1. Collect all tickers
            tickers_to_fetch = {"KRW-BTC", "KRW-ETH", "KRW-SOL"}
            for s_id in current_strategy_ids:
                if s_id in strategies:
                    tickers_to_fetch.add(strategies[s_id].ticker)
            
            # 2. Fetch Data
            prices = {}
            all_open_orders = []
            
            if tickers_to_fetch:
                ticker_list = list(tickers_to_fetch)
                if hasattr(exchange, "get_current_prices"):
                    try:
                        prices = exchange.get_current_prices(ticker_list)
                    except Exception as e:
                        logging.error(f"Failed to fetch prices: {e}")
                else:
                    for ticker in ticker_list:
                        try:
                            price = exchange.get_current_price(ticker)
                            if price:
                                prices[ticker] = price
                        except Exception as e:
                            logging.error(f"Failed to fetch price for {ticker}: {e}")

            # Update Shared Cache
            shared_prices.update(prices)

            # Fetch Orders
            try:
                if hasattr(exchange, "get_orders"):
                    all_open_orders = exchange.get_orders(state='wait')
            except Exception as e:
                logging.error(f"Failed to fetch open orders: {e}")
                all_open_orders = None

            # 3. Fetch Accounts & Candles
            current_time = time.time()
            
            if current_time - accounts_cache['timestamp'] > 10:
                try:
                    accounts_cache['data'] = exchange.get_accounts() if hasattr(exchange, "get_accounts") else []
                    accounts_cache['timestamp'] = current_time
                except Exception as e:
                    logging.error(f"Failed to fetch accounts in loop: {e}")

            for ticker in tickers_to_fetch:
                if ticker not in candle_cache['data']:
                    candle_cache['data'][ticker] = {}
                    candle_cache['timestamp'][ticker] = {}
                
                for interval in ["minutes/5", "days"]:
                    last_ts = candle_cache['timestamp'][ticker].get(interval, 0)
                    if current_time - last_ts > 30:
                        try:
                            batch = exchange.get_candles(ticker, count=200, interval=interval)
                            if batch:
                                # DEBUG: Check data spacing
                                if len(batch) >= 3:
                                    oldest_3 = [b.get('candle_date_time_utc', '') for b in batch[-3:]]
                                    logging.info(f"[ENGINE] Fetched {interval} for {ticker}: {len(batch)} candles, oldest 3: {oldest_3}")

                                candle_cache['data'][ticker][interval] = batch
                                candle_cache['timestamp'][ticker][interval] = current_time
                                try:
                                    get_candle_db().save_candles(ticker, interval, batch)
                                except Exception as e:
                                    logging.error(f"Failed to cache candles to Market DB: {e}")
                        except Exception as e:
                            logging.debug(f"Failed to fetch {interval} candles for {ticker}: {e}")

            # Create Market Context
            market_context = {
                'prices': prices,
                'open_orders': all_open_orders,
                'accounts': accounts_cache['data'],
                'candles': candle_cache['data']
            }

            # 4. Tick Strategies
            current_time = time.time()
            for s_id in current_strategy_ids:
                if s_id not in strategies: continue
                strategy = strategies[s_id]
                
                if s_id not in last_tick_time:
                    last_tick_time[s_id] = 0.0
                
                tick_interval = strategy.config.tick_interval
                if current_time - last_tick_time[s_id] >= tick_interval:
                    price = prices.get(strategy.ticker)
                    if price:
                        strategy.tick(current_price=price, open_orders=all_open_orders, market_context=market_context)
                        last_tick_time[s_id] = current_time

        except Exception as e:
            logging.error(f"Error in strategy loop: {e}")
            time.sleep(1.0)
        
        elapsed = time.time() - loop_start_time
        sleep_time = max(0.1, 1.0 - elapsed)
        time.sleep(sleep_time)

def start_engine():
    thread = threading.Thread(target=run_strategies, daemon=True)
    thread.start()
    return thread
