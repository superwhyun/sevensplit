import logging
import threading
import time
from typing import Dict, Iterable, List, Optional, Set

from database import get_candle_db
from core.config import (
    accounts_cache,
    candle_cache,
    current_mode,
    db,
    exchange,
    shared_prices,
    strategy_service,
)


DEFAULT_MARKET_TICKERS: Set[str] = {"KRW-BTC", "KRW-ETH", "KRW-SOL"}
CANDLE_INTERVALS: tuple[str, ...] = ("minutes/5", "days")


class PortfolioCalculator:
    def __init__(self, exchange_client, db_manager, mode: str):
        self.exchange = exchange_client
        self.db = db_manager
        self.mode = mode

    def calculate(self, prices: Optional[Dict[str, float]] = None, accounts_raw: Optional[list] = None) -> dict:
        prices = prices or {}
        accounts = self._resolve_accounts(prices, accounts_raw)
        normalized_accounts = self._normalize_accounts(accounts)

        portfolio = {
            "mode": self.mode,
            "coins": {},
            "accounts": normalized_accounts,
        }

        balance_krw = self._extract_krw_balance(normalized_accounts)
        portfolio["balance_krw"] = balance_krw

        total_value = 0.0
        for acc in normalized_accounts:
            currency = acc.get("currency")
            if currency == "KRW":
                total_value += balance_krw
                continue

            coin_data = self._build_coin_data(acc)
            portfolio["coins"][currency] = coin_data
            total_value += coin_data["value"]

        portfolio["total_value"] = total_value
        self._attach_realized_profit(portfolio)
        return portfolio

    def _resolve_accounts(self, prices: Dict[str, float], accounts_raw: Optional[list]) -> list:
        if not hasattr(self.exchange, "get_accounts"):
            return []

        if accounts_raw is not None:
            return self._attach_price_fields(accounts_raw, prices)

        if prices and hasattr(self.exchange, "_request"):
            raw = self.exchange._request("GET", "/v1/accounts")
            return self._attach_price_fields(raw or [], prices)

        return self.exchange.get_accounts() or []

    def _attach_price_fields(self, accounts_raw: list, prices: Dict[str, float]) -> list:
        accounts = []
        for account in accounts_raw:
            currency = account.get("currency")
            balance = float(account.get("balance", 0))
            locked = float(account.get("locked", 0))
            ticker = f"KRW-{currency}" if currency and currency != "KRW" else None
            current_price = 1.0 if currency == "KRW" else float(prices.get(ticker, 0.0))
            total_balance = balance + locked
            value = total_balance * current_price if current_price else 0.0
            accounts.append(
                {
                    **account,
                    "ticker": ticker,
                    "current_price": current_price,
                    "balance_value": value,
                    "total_balance": total_balance,
                }
            )
        return accounts

    def _normalize_accounts(self, accounts: list) -> list:
        normalized = []
        for acc in accounts:
            if not isinstance(acc, dict):
                continue
            normalized.append(
                {
                    **acc,
                    "balance": float(acc.get("balance", 0.0) or 0.0),
                    "locked": float(acc.get("locked", 0.0) or 0.0),
                    "avg_buy_price": float(acc.get("avg_buy_price", 0.0) or 0.0),
                    "current_price": float(acc.get("current_price", 0.0) or 0.0),
                    "balance_value": float(acc.get("balance_value", 0.0) or 0.0),
                    "total_balance": float(acc.get("total_balance", 0.0) or 0.0),
                }
            )
        return normalized

    def _extract_krw_balance(self, accounts: list) -> float:
        for acc in accounts:
            if acc.get("currency") == "KRW":
                return float(acc.get("total_balance", acc.get("balance", 0.0)))
        return 0.0

    def _build_coin_data(self, account: dict) -> dict:
        currency = account.get("currency")
        ticker = account.get("ticker") or f"KRW-{currency}"
        available = float(account.get("balance", 0.0) or 0.0)
        locked = float(account.get("locked", 0.0) or 0.0)
        total_balance = float(account.get("total_balance", available + locked))
        return {
            "ticker": ticker,
            "balance": total_balance,
            "available": available,
            "locked": locked,
            "current_price": float(account.get("current_price", 0.0) or 0.0),
            "value": float(account.get("balance_value", 0.0) or 0.0),
            "avg_buy_price": float(account.get("avg_buy_price", 0.0) or 0.0),
        }

    def _attach_realized_profit(self, portfolio: dict):
        try:
            all_trades = self.db.get_all_trades()
            portfolio["total_realized_profit"] = sum(t.net_profit for t in all_trades)
        except Exception as e:
            logging.error(f"Failed to calculate realized profit: {e}")
            portfolio["total_realized_profit"] = 0.0
            all_trades = []

        for _, data in portfolio["coins"].items():
            ticker = data["ticker"]
            try:
                data["realized_profit"] = sum(t.net_profit for t in all_trades if t.ticker == ticker)
            except Exception:
                data["realized_profit"] = 0.0


class StrategyEngine:
    def __init__(
        self,
        strategy_service_obj,
        exchange_client,
        shared_price_cache: Dict[str, float],
        accounts_state: dict,
        candles_state: dict,
        loop_interval: float = 1.0,
    ):
        self.strategy_service = strategy_service_obj
        self.exchange = exchange_client
        self.shared_prices = shared_price_cache
        self.accounts_cache = accounts_state
        self.candle_cache = candles_state
        self.loop_interval = loop_interval
        self.last_tick_time: Dict[int, float] = {}
        self.candle_db = get_candle_db()

    def run_forever(self):
        while True:
            loop_start = time.time()
            try:
                self.run_iteration()
            except Exception as e:
                logging.error(f"Error in strategy loop: {e}")
                time.sleep(1.0)

            elapsed = time.time() - loop_start
            time.sleep(max(0.1, self.loop_interval - elapsed))

    def run_iteration(self):
        strategies = self.strategy_service.strategies
        strategy_ids = list(strategies.keys())
        tickers = self._collect_tickers(strategy_ids, strategies)

        prices = self._fetch_prices(tickers)
        self.shared_prices.update(prices)

        open_orders = self._fetch_open_orders()
        now = time.time()
        self._refresh_accounts(now)
        self._refresh_candles(tickers, now)

        market_context = {
            "prices": prices,
            "open_orders": open_orders,
            "accounts": self.accounts_cache["data"],
            "candles": self.candle_cache["data"],
        }
        self._tick_strategies(strategy_ids, strategies, prices, open_orders, market_context, now)

    def _collect_tickers(self, strategy_ids: List[int], strategies: Dict[int, object]) -> Set[str]:
        tickers = set(DEFAULT_MARKET_TICKERS)
        for strategy_id in strategy_ids:
            strategy = strategies.get(strategy_id)
            if strategy:
                tickers.add(strategy.ticker)
        return tickers

    def _fetch_prices(self, tickers: Iterable[str]) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        if not tickers:
            return prices

        ticker_list = list(tickers)
        if hasattr(self.exchange, "get_current_prices"):
            try:
                return self.exchange.get_current_prices(ticker_list) or {}
            except Exception as e:
                logging.error(f"Failed to fetch prices: {e}")
                return {}

        for ticker in ticker_list:
            try:
                price = self.exchange.get_current_price(ticker)
                if price:
                    prices[ticker] = price
            except Exception as e:
                logging.error(f"Failed to fetch price for {ticker}: {e}")
        return prices

    def _fetch_open_orders(self):
        if not hasattr(self.exchange, "get_orders"):
            return []
        try:
            return self.exchange.get_orders(state="wait")
        except Exception as e:
            logging.error(f"Failed to fetch open orders: {e}")
            return None

    def _refresh_accounts(self, now: float):
        if now - self.accounts_cache["timestamp"] <= 10:
            return
        try:
            self.accounts_cache["data"] = self.exchange.get_accounts() if hasattr(self.exchange, "get_accounts") else []
            self.accounts_cache["timestamp"] = now
        except Exception as e:
            logging.error(f"Failed to fetch accounts in loop: {e}")

    def _refresh_candles(self, tickers: Iterable[str], now: float):
        for ticker in tickers:
            self.candle_cache["data"].setdefault(ticker, {})
            self.candle_cache["timestamp"].setdefault(ticker, {})

            for interval in CANDLE_INTERVALS:
                last_ts = self.candle_cache["timestamp"][ticker].get(interval, 0)
                if now - last_ts <= 30:
                    continue
                self._refresh_single_candle_batch(ticker, interval, now)

    def _refresh_single_candle_batch(self, ticker: str, interval: str, now: float):
        try:
            batch = self.exchange.get_candles(ticker, count=200, interval=interval)
            if not batch:
                return

            if len(batch) >= 3:
                oldest_3 = [b.get("candle_date_time_utc", "") for b in batch[-3:]]
                logging.info(f"[ENGINE] Fetched {interval} for {ticker}: {len(batch)} candles, oldest 3: {oldest_3}")

            self.candle_cache["data"][ticker][interval] = batch
            self.candle_cache["timestamp"][ticker][interval] = now
            try:
                self.candle_db.save_candles(ticker, interval, batch)
            except Exception as e:
                logging.error(f"Failed to cache candles to Market DB: {e}")
        except Exception as e:
            logging.debug(f"Failed to fetch {interval} candles for {ticker}: {e}")

    def _tick_strategies(
        self,
        strategy_ids: List[int],
        strategies: Dict[int, object],
        prices: Dict[str, float],
        open_orders,
        market_context: dict,
        now: float,
    ):
        for strategy_id in strategy_ids:
            strategy = strategies.get(strategy_id)
            if strategy is None:
                continue

            self.last_tick_time.setdefault(strategy_id, 0.0)
            if now - self.last_tick_time[strategy_id] < strategy.config.tick_interval:
                continue

            current_price = prices.get(strategy.ticker)
            if not current_price:
                continue

            strategy.tick(
                current_price=current_price,
                open_orders=open_orders,
                market_context=market_context,
            )
            self.last_tick_time[strategy_id] = now


_portfolio_calculator = PortfolioCalculator(exchange, db, current_mode)
_engine = StrategyEngine(strategy_service, exchange, shared_prices, accounts_cache, candle_cache)


def calculate_portfolio(prices: Optional[Dict[str, float]] = None, accounts_raw: Optional[list] = None):
    return _portfolio_calculator.calculate(prices=prices, accounts_raw=accounts_raw)


def run_strategies():
    _engine.run_forever()


def start_engine():
    thread = threading.Thread(target=run_strategies, daemon=True)
    thread.start()
    return thread
