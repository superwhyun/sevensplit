import pyupbit
import logging
from datetime import datetime
from datetime import timezone
from typing import Dict
from database import get_db

class Exchange:
    def get_balance(self, ticker):
        raise NotImplementedError

    def get_accounts(self):
        """Return account information including balances and any locked amounts."""
        raise NotImplementedError

    def get_current_price(self, ticker):
        raise NotImplementedError

    def buy_market_order(self, ticker, amount):
        raise NotImplementedError

    def sell_market_order(self, ticker, volume):
        raise NotImplementedError

    def buy_limit_order(self, ticker, price, volume):
        raise NotImplementedError

    def sell_limit_order(self, ticker, price, volume):
        raise NotImplementedError

    def get_order(self, uuid):
        raise NotImplementedError

    def cancel_order(self, uuid):
        raise NotImplementedError

class UpbitExchange(Exchange):
    # (connect, read) seconds. A hung request would otherwise freeze the single-threaded engine.
    REQUEST_TIMEOUT = (3, 10)
    # Backoff schedule for HTTP 429 (rate limit) retries.
    RATE_LIMIT_BACKOFF_SEC = (0.2, 0.5, 1.0)
    # Upbit /v1/orders returns at most 100 rows per page.
    ORDERS_PAGE_LIMIT = 100
    ORDERS_MAX_PAGES = 10

    def __init__(self, access_key, secret_key, server_url="https://api.upbit.com"):
        self.access_key = access_key
        self.secret_key = secret_key
        self.server_url = server_url.rstrip('/')
        import jwt
        import hashlib
        import urllib.parse
        import requests
        import uuid
        import time
        self.jwt = jwt
        self.hashlib = hashlib
        self.urlencode = urllib.parse.urlencode
        self.requests = requests
        self.uuid = uuid
        self.time = time
        
        # Cache for valid markets
        self.valid_markets = set()
        self.last_markets_update = 0

    def get_tick_size(self, price):
        """Return the tick size for a given price in KRW market based on user provided table."""
        if price >= 1000000:
            return 1000
        elif price >= 500000:
            return 500
        elif price >= 100000:
            return 100
        elif price >= 50000:
            return 50
        elif price >= 10000:
            return 10
        elif price >= 5000:
            return 5
        elif price >= 1000:
            return 1
        elif price >= 100:
            return 1
        else:
            return 0.1 # Default for < 100

    def normalize_price(self, price):
        """Normalize price to the nearest tick size (floor)."""
        tick_size = self.get_tick_size(price)
        
        # Use Decimal for precise arithmetic
        from decimal import Decimal
        
        # Convert to string first to avoid float precision issues
        d_price = Decimal(str(price))
        d_tick = Decimal(str(tick_size))
        
        # Floor division to get number of ticks
        normalized = (d_price // d_tick) * d_tick
        
        if tick_size >= 1:
            return int(normalized)
        else:
            return float(normalized)

    def get_markets(self):
        """KRW markets with display names, e.g. [{market, korean_name, english_name}]."""
        resp = self._request('GET', '/v1/market/all', params={'isDetails': 'false'}, auth=False)
        markets = []
        for m in resp or []:
            market = m.get('market') or ''
            if not market.startswith('KRW-'):
                continue
            markets.append({
                'market': market,
                'korean_name': m.get('korean_name') or market,
                'english_name': m.get('english_name') or market,
            })
        return markets

    def _get_valid_markets(self):
        """Fetch and cache valid KRW markets to avoid 404s on delisted coins"""
        current_time = self.time.time()
        # Update cache every hour (3600 seconds)
        if not self.valid_markets or (current_time - self.last_markets_update > 3600):
            try:
                # Fetch all markets (public endpoint, no auth needed)
                resp = self._request('GET', '/v1/market/all', params={'isDetails': 'false'}, auth=False)
                if isinstance(resp, list):
                    new_markets = {m['market'] for m in resp if m['market'].startswith('KRW-')}
                    if new_markets:
                        self.valid_markets = new_markets
                        self.last_markets_update = current_time
                        logging.info(f"Refreshed valid markets: {len(self.valid_markets)} KRW pairs found")
            except Exception as e:
                logging.warning(f"Failed to fetch valid markets: {e}")
                
        return self.valid_markets

    def _request(self, method, endpoint, params=None, data=None, auth=True):
        url = f"{self.server_url}{endpoint}"
        headers = {}
        
        if auth:
            payload = {
                'access_key': self.access_key,
                'nonce': str(self.uuid.uuid4()),
            }

            query_params = params or {}
            if data:
                query_params.update(data)
            
            # Filter out None values from query_params for hash calculation
            query_params = {k: v for k, v in query_params.items() if v is not None}

            if query_params:
                query_string = self.urlencode(query_params)
                m = self.hashlib.sha512()
                m.update(query_string.encode())
                query_hash = m.hexdigest()
                payload['query_hash'] = query_hash
                payload['query_hash_alg'] = 'SHA512'
            
            token = self.jwt.encode(payload, self.secret_key, algorithm='HS256')
            headers = {'Authorization': f'Bearer {token}'}
        
        try:
            resp = self._send_with_rate_limit_retry(method, url, params, data, headers)

            # Check for error response content before raising
            if not resp.ok:
                error_msg = f"Upbit API Error: {resp.status_code} {resp.text}"

                # Downgrade 404 (Order not found) to WARNING to avoid noise in logs
                if resp.status_code == 404:
                    logging.warning(error_msg)
                else:
                    logging.error(error_msg)

                raise Exception(error_msg)

            return resp.json()
        except Exception as e:
            logging.error(f"Request failed: {e} for url: {url}")
            raise

    def _send_once(self, method, url, params, data, headers):
        if method == 'GET':
            return self.requests.get(url, params=params, headers=headers, timeout=self.REQUEST_TIMEOUT)
        if method == 'POST':
            return self.requests.post(url, json=data, params=params, headers=headers, timeout=self.REQUEST_TIMEOUT)
        if method == 'DELETE':
            return self.requests.delete(url, params=params, headers=headers, timeout=self.REQUEST_TIMEOUT)
        raise ValueError(f"Unsupported HTTP method: {method}")

    def _send_with_rate_limit_retry(self, method, url, params, data, headers):
        """Retry on HTTP 429 with a short backoff. Every other response is returned as-is."""
        resp = self._send_once(method, url, params, data, headers)
        for attempt, delay in enumerate(self.RATE_LIMIT_BACKOFF_SEC, start=1):
            if resp.status_code != 429:
                break
            logging.warning(
                f"Upbit rate limit (429) on {url}; retry {attempt}/{len(self.RATE_LIMIT_BACKOFF_SEC)} "
                f"after {delay}s (Remaining-Req: {resp.headers.get('Remaining-Req')})"
            )
            self.time.sleep(delay)
            resp = self._send_once(method, url, params, data, headers)
        return resp

    @staticmethod
    def format_volume(volume) -> str:
        """Fixed-point volume string (Upbit rejects scientific notation such as '3e-05')."""
        text = f"{float(volume):.8f}".rstrip('0').rstrip('.')
        return text if text else "0"

    @staticmethod
    def format_price(price) -> str:
        value = float(price)
        if value == int(value):
            return str(int(value))
        return f"{value:.8f}".rstrip('0').rstrip('.')

    def verify_credentials(self) -> dict:
        """Check the API keys against Upbit. Raises on rejection; returns balances and expiry."""
        accounts = self._request('GET', '/v1/accounts')
        krw_balance = 0.0
        held = []
        for account in accounts or []:
            currency = account.get('currency')
            balance = float(account.get('balance', 0) or 0)
            locked = float(account.get('locked', 0) or 0)
            if currency == 'KRW':
                krw_balance = balance + locked
            elif balance + locked > 0:
                held.append(currency)

        expire_at = None
        try:
            keys = self._request('GET', '/v1/api_keys')
            for entry in keys or []:
                if entry.get('access_key') == self.access_key:
                    expire_at = entry.get('expire_at')
                    break
            if expire_at is None and keys:
                expire_at = keys[0].get('expire_at')
        except Exception as e:
            # Expiry is informational only; a failure here must not fail validation.
            logging.debug(f"api_keys lookup skipped: {e}")

        return {
            "valid": True,
            "krw_balance": krw_balance,
            "held_currencies": held,
            "expire_at": expire_at,
        }

    def get_balance(self, ticker="KRW"):
        try:
            accounts = self._request('GET', '/v1/accounts')
            for account in accounts:
                if account['currency'] == ticker:
                    return float(account['balance'])
                if "-" in ticker:
                    coin = ticker.split("-")[1]
                    if account['currency'] == coin:
                        return float(account['balance'])
            return 0.0
        except Exception as e:
            logging.error(f"get_balance failed: {e}")
            return 0.0

    def get_accounts(self):
        """Fetch detailed account info and enrich with current price/value."""
        try:
            accounts = self._request('GET', '/v1/accounts')

            # Price every held coin that has a KRW market, in a single batched ticker request.
            valid_markets = self._get_valid_markets()
            tickers = []
            for account in accounts:
                currency = account.get('currency')
                if not currency or currency == 'KRW':
                    continue
                ticker = f"KRW-{currency}"
                if valid_markets and ticker not in valid_markets:
                    continue
                tickers.append(ticker)

            prices = self.get_current_prices(tickers) if tickers else {}

            enriched = []
            for account in accounts:
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                locked = float(account.get('locked', 0))
                ticker = f"KRW-{currency}" if currency and currency != 'KRW' else None
                
                # Use price if available, else 0
                current_price = 1.0 if currency == 'KRW' else prices.get(ticker, 0.0)
                
                total_balance = balance + locked
                value = total_balance * current_price if current_price else 0.0

                enriched.append({
                    **account,
                    "ticker": ticker,
                    "current_price": current_price,
                    "balance_value": value,
                    "total_balance": total_balance
                })

            return enriched
        except Exception as e:
            logging.error(f"get_accounts failed: {e}")
            return []

    def get_avg_buy_price(self, ticker):
        currency = ticker.split("-")[1] if "-" in ticker else ticker
        try:
            accounts = self._request('GET', '/v1/accounts')
            for account in accounts:
                if account['currency'] == currency:
                    return float(account['avg_buy_price'])
            return 0.0
        except Exception as e:
            return 0.0

    def get_current_price(self, ticker="KRW-BTC"):
        try:
            resp = self._request('GET', '/v1/ticker', params={'markets': ticker}, auth=False)
            if resp and isinstance(resp, list):
                return float(resp[0]['trade_price'])
            return 0.0
        except Exception as e:
            logging.error(f"get_current_price failed: {e}")
            return 0.0

    def get_current_prices(self, tickers):
        """Fetch prices for multiple tickers"""
        try:
            markets = ",".join(tickers)
            resp = self._request('GET', '/v1/ticker', params={'markets': markets}, auth=False)
            prices = {}
            if resp and isinstance(resp, list):
                for item in resp:
                    prices[item['market']] = float(item['trade_price'])
            return prices
        except Exception as e:
            logging.error(f"get_current_prices failed: {e}")
            return {}

    def get_candles(self, ticker, count=200, interval="minutes/5", to=None):
        """Fetch candle data"""
        try:
            params = {'market': ticker, 'count': count}
            if to:
                params['to'] = to
            return self._request('GET', f'/v1/candles/{interval}', params=params, auth=False)
        except Exception as e:
            logging.error(f"get_candles failed: {e}")
            return []

    def buy_market_order(self, ticker, amount):
        data = {
            'market': ticker,
            'side': 'bid',
            'price': self.format_price(amount),
            'ord_type': 'price'
        }
        return self._request('POST', '/v1/orders', data=data)

    def sell_market_order(self, ticker, volume):
        data = {
            'market': ticker,
            'side': 'ask',
            'volume': self.format_volume(volume),
            'ord_type': 'market'
        }
        return self._request('POST', '/v1/orders', data=data)

    def buy_limit_order(self, ticker, price, volume):
        data = {
            'market': ticker,
            'side': 'bid',
            'volume': self.format_volume(volume),
            'price': self.format_price(price),
            'ord_type': 'limit'
        }
        return self._request('POST', '/v1/orders', data=data)

    def sell_limit_order(self, ticker, price, volume):
        data = {
            'market': ticker,
            'side': 'ask',
            'volume': self.format_volume(volume),
            'price': self.format_price(price),
            'ord_type': 'limit'
        }
        return self._request('POST', '/v1/orders', data=data)

    def get_orders(self, ticker=None, state='wait', page=1, limit=None, fetch_all=True):
        """Fetch orders with filtering.

        Upbit caps each page at 100 rows. With fetch_all (default) pages are followed
        until a short page is returned, so accounts with >100 open orders are fully covered.
        """
        page_limit = int(limit or self.ORDERS_PAGE_LIMIT)
        collected = []
        current_page = int(page or 1)
        for _ in range(self.ORDERS_MAX_PAGES):
            params = {
                'state': state,
                'page': current_page,
                'limit': page_limit,
                'order_by': 'desc'
            }
            if ticker:
                params['market'] = ticker
            batch = self._request('GET', '/v1/orders', params=params) or []
            collected.extend(batch)
            if not fetch_all or len(batch) < page_limit:
                break
            current_page += 1
        else:
            logging.warning(
                f"get_orders stopped after {self.ORDERS_MAX_PAGES} pages "
                f"({len(collected)} orders); some open orders may be missing."
            )
        return collected

    def get_order(self, uuid):
        return self._request('GET', '/v1/order', params={'uuid': uuid})

    def cancel_order(self, uuid):
        return self._request('DELETE', '/v1/order', params={'uuid': uuid})


class PaperExchange(Exchange):
    """Paper trading exchange: public market data + in-memory simulated orders/fills."""

    _LOCK_EPSILON = 1e-12
    # Upbit KRW-market fee. Reported on orders as paid_fee so P/L uses the same field as live.
    FEE_RATE = 0.0005

    def __init__(self, public_client: UpbitExchange, initial_krw: float = 10_000_000.0):
        self.public_client = public_client
        self.orders: Dict[str, dict] = {}
        self.order_seq = 0
        self._tick_bounds: Dict[str, dict] = {}
        self.balances: Dict[str, dict] = {
            "KRW": {"balance": float(initial_krw), "locked": 0.0, "avg_buy_price": 1.0}
        }

    def _new_order_id(self) -> str:
        self.order_seq += 1
        return f"paper-{self.order_seq}"

    def _now(self) -> datetime:
        """Clock used to stamp orders/trades. Real-time by default; a replay/backtest
        exchange overrides this to return the simulated timestamp, so historical fills
        are recorded at their historical time instead of the moment the replay runs."""
        return datetime.now(timezone.utc)

    def get_tick_size(self, price):
        return self.public_client.get_tick_size(price)

    def normalize_price(self, price):
        return self.public_client.normalize_price(price)

    def get_current_price(self, ticker="KRW-BTC"):
        return self.public_client.get_current_price(ticker)

    def get_current_prices(self, tickers):
        return self.public_client.get_current_prices(tickers)

    def get_candles(self, ticker, count=200, interval="minutes/5", to=None):
        return self.public_client.get_candles(ticker, count=count, interval=interval, to=to)

    def _currency_from_ticker(self, ticker: str) -> str:
        if "-" in ticker:
            return ticker.split("-")[1]
        return ticker

    def _ensure_currency(self, currency: str):
        if currency not in self.balances:
            self.balances[currency] = {"balance": 0.0, "locked": 0.0, "avg_buy_price": 0.0}

    def _available(self, currency: str) -> float:
        self._ensure_currency(currency)
        return float(self.balances[currency]["balance"])

    def _lock(self, currency: str, amount: float) -> bool:
        self._ensure_currency(currency)
        balance = float(self.balances[currency]["balance"])
        epsilon = max(self._LOCK_EPSILON, abs(amount) * self._LOCK_EPSILON)
        if balance + epsilon < amount:
            return False
        new_balance = balance - amount
        if abs(new_balance) <= epsilon:
            new_balance = 0.0
        self.balances[currency]["balance"] = new_balance
        self.balances[currency]["locked"] += amount
        return True

    def _unlock(self, currency: str, amount: float):
        self._ensure_currency(currency)
        self.balances[currency]["locked"] = max(0.0, self.balances[currency]["locked"] - amount)
        self.balances[currency]["balance"] += amount

    def get_balance(self, ticker="KRW"):
        currency = self._currency_from_ticker(ticker)
        self._ensure_currency(currency)
        return float(self.balances[currency]["balance"])

    def get_accounts(self):
        tickers = [
            f"KRW-{cur}"
            for cur, data in self.balances.items()
            if cur != "KRW" and (data["balance"] > 0 or data["locked"] > 0)
        ]
        prices = self.get_current_prices(tickers) if tickers else {}

        accounts = []
        for currency, data in self.balances.items():
            balance = float(data["balance"])
            locked = float(data["locked"])
            if balance == 0 and locked == 0:
                continue
            ticker = f"KRW-{currency}" if currency != "KRW" else None
            current_price = 1.0 if currency == "KRW" else float(prices.get(ticker, 0.0))
            total_balance = balance + locked
            accounts.append(
                {
                    "currency": currency,
                    "balance": str(balance),
                    "locked": str(locked),
                    "avg_buy_price": str(float(data.get("avg_buy_price", 0.0))),
                    "ticker": ticker,
                    "current_price": current_price,
                    "balance_value": total_balance * current_price,
                    "total_balance": total_balance,
                }
            )
        return accounts

    def _fill_if_match(self, order: dict):
        if order.get("state") != "wait":
            return
        side = order.get("side")
        ticker = order.get("market")
        price = float(order.get("price") or 0.0)
        volume = float(order.get("volume") or 0.0)
        current = self.get_current_price(ticker)
        if not current:
            return

        low_price, high_price = self._get_match_bounds(ticker, current)
        should_fill = (side == "bid" and low_price <= price) or (side == "ask" and high_price >= price)
        if not should_fill:
            return

        base_currency = self._currency_from_ticker(ticker)
        # Stamp the fill at the moment it actually crosses, not when the limit order was
        # placed — a resting order can wait several ticks (or, during replay, several
        # simulated days) before price reaches it.
        fill_iso = self._now().isoformat()
        order["state"] = "done"
        order["executed_volume"] = volume
        order["paid_fee"] = price * volume * self.FEE_RATE
        order["trades"] = [{"price": price, "volume": volume, "funds": price * volume, "created_at": fill_iso}]

        if side == "bid":
            locked_krw = price * volume
            self._ensure_currency(base_currency)
            self.balances["KRW"]["locked"] = max(0.0, self.balances["KRW"]["locked"] - locked_krw)
            prev_qty = self.balances[base_currency]["balance"]
            prev_avg = self.balances[base_currency]["avg_buy_price"]
            new_qty = prev_qty + volume
            if new_qty > 0:
                self.balances[base_currency]["avg_buy_price"] = (
                    ((prev_qty * prev_avg) + (volume * price)) / new_qty
                )
            self.balances[base_currency]["balance"] = new_qty
        else:
            proceeds = price * volume
            self._ensure_currency(base_currency)
            self.balances[base_currency]["locked"] = max(0.0, self.balances[base_currency]["locked"] - volume)
            self.balances["KRW"]["balance"] += proceeds

    def _get_match_bounds(self, ticker: str, current_price: float) -> tuple[float, float]:
        bounds = self._tick_bounds.get(ticker) if hasattr(self, "_tick_bounds") else None
        if not bounds:
            return (float(current_price), float(current_price))
        low = float(bounds.get("low") or current_price)
        high = float(bounds.get("high") or current_price)
        if low > high:
            low, high = high, low
        return (low, high)

    def buy_limit_order(self, ticker, price, volume):
        price = float(price)
        volume = float(volume)
        required = price * volume
        if not self._lock("KRW", required):
            raise Exception("insufficient KRW for paper buy limit order")

        uuid = self._new_order_id()
        self.orders[uuid] = {
            "uuid": uuid,
            "market": ticker,
            "side": "bid",
            "ord_type": "limit",
            "price": price,
            "volume": volume,
            "executed_volume": 0.0,
            "state": "wait",
            "created_at": self._now().isoformat(),
            "trades": [],
        }
        return {"uuid": uuid}

    def sell_limit_order(self, ticker, price, volume):
        price = float(price)
        volume = float(volume)
        base_currency = self._currency_from_ticker(ticker)
        if not self._lock(base_currency, volume):
            raise Exception("insufficient asset for paper sell limit order")

        uuid = self._new_order_id()
        self.orders[uuid] = {
            "uuid": uuid,
            "market": ticker,
            "side": "ask",
            "ord_type": "limit",
            "price": price,
            "volume": volume,
            "executed_volume": 0.0,
            "state": "wait",
            "created_at": self._now().isoformat(),
            "trades": [],
        }
        return {"uuid": uuid}

    def buy_market_order(self, ticker, amount):
        amount = float(amount)
        price = float(self.get_current_price(ticker))
        if not price:
            raise Exception("current price unavailable for paper buy market order")
        if self._available("KRW") < amount:
            raise Exception("insufficient KRW for paper buy market order")

        volume = amount / price
        self.balances["KRW"]["balance"] -= amount
        base_currency = self._currency_from_ticker(ticker)
        self._ensure_currency(base_currency)
        prev_qty = self.balances[base_currency]["balance"]
        prev_avg = self.balances[base_currency]["avg_buy_price"]
        new_qty = prev_qty + volume
        if new_qty > 0:
            self.balances[base_currency]["avg_buy_price"] = (((prev_qty * prev_avg) + amount) / new_qty)
        self.balances[base_currency]["balance"] = new_qty

        uuid = self._new_order_id()
        now_iso = self._now().isoformat()
        self.orders[uuid] = {
            "uuid": uuid,
            "market": ticker,
            "side": "bid",
            "ord_type": "price",
            "price": price,
            "volume": volume,
            "executed_volume": volume,
            "state": "done",
            "created_at": now_iso,
            "paid_fee": amount * self.FEE_RATE,
            "trades": [{"price": price, "volume": volume, "funds": amount, "created_at": now_iso}],
        }
        return {"uuid": uuid}

    def sell_market_order(self, ticker, volume):
        volume = float(volume)
        base_currency = self._currency_from_ticker(ticker)
        available = self._available(base_currency)
        # Same rounding tolerance as _lock: a split that sells its exact recorded volume can be
        # a few 1e-18 above the float balance after earlier buys/sells were summed.
        epsilon = max(self._LOCK_EPSILON, abs(volume) * self._LOCK_EPSILON)
        if available + epsilon < volume:
            raise Exception("insufficient asset for paper sell market order")
        volume = min(volume, available)
        price = float(self.get_current_price(ticker))
        if not price:
            raise Exception("current price unavailable for paper sell market order")

        remaining = self.balances[base_currency]["balance"] - volume
        self.balances[base_currency]["balance"] = 0.0 if abs(remaining) <= epsilon else remaining
        self.balances["KRW"]["balance"] += (price * volume)

        uuid = self._new_order_id()
        now_iso = self._now().isoformat()
        self.orders[uuid] = {
            "uuid": uuid,
            "market": ticker,
            "side": "ask",
            "ord_type": "market",
            "price": price,
            "volume": volume,
            "executed_volume": volume,
            "state": "done",
            "created_at": now_iso,
            "paid_fee": price * volume * self.FEE_RATE,
            "trades": [{"price": price, "volume": volume, "funds": price * volume, "created_at": now_iso}],
        }
        return {"uuid": uuid}

    def get_order(self, uuid):
        order = self.orders.get(uuid)
        if not order:
            raise Exception("Order not found")
        self._fill_if_match(order)
        return dict(order)

    def get_orders(self, ticker=None, state='wait', page=1, limit=100):
        for order in self.orders.values():
            if order.get("state") == "wait":
                self._fill_if_match(order)

        filtered = []
        for order in self.orders.values():
            if ticker and order.get("market") != ticker:
                continue
            if state and order.get("state") != state:
                continue
            filtered.append(dict(order))
        return filtered[:limit]

    def cancel_order(self, uuid):
        order = self.orders.get(uuid)
        if not order:
            raise Exception("Order not found")
        if order.get("state") != "wait":
            return {"uuid": uuid}

        side = order.get("side")
        price = float(order.get("price") or 0.0)
        volume = float(order.get("volume") or 0.0)
        if side == "bid":
            self._unlock("KRW", price * volume)
        elif side == "ask":
            self._unlock(self._currency_from_ticker(order.get("market")), volume)
        order["state"] = "cancel"
        return {"uuid": uuid}
