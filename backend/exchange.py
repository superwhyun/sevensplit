import pyupbit
import logging
from datetime import datetime
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

    def _get_valid_markets(self):
        """Fetch and cache valid KRW markets to avoid 404s on delisted coins"""
        current_time = self.time.time()
        # Update cache every hour (3600 seconds)
        if not self.valid_markets or (current_time - self.last_markets_update > 3600):
            try:
                # Fetch all markets (warning: this is a public endpoint, no auth needed)
                # If we are in Mock mode (localhost), this might fail if mock doesn't implement /v1/market/all
                # So we try/except and fallback safely
                resp = self._request('GET', '/v1/market/all', params={'isDetails': 'false'}, auth=False)
                if isinstance(resp, list):
                    new_markets = {m['market'] for m in resp if m['market'].startswith('KRW-')}
                    if new_markets:
                        self.valid_markets = new_markets
                        self.last_markets_update = current_time
                        import os
                        is_mock = "localhost" in self.server_url or "127.0.0.1" in self.server_url or os.getenv("MODE", "").upper() == "MOCK"
                        if not is_mock:
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
        
        # Log request only if NOT in mock mode
        import os
        # is_mock = "localhost" in self.server_url or "127.0.0.1" in self.server_url or os.getenv("MODE", "").upper() == "MOCK"
        # if not is_mock:
        # logging.info(f"🌐 Upbit API Request: {method} {url} {params or ''}")

        try:
            if method == 'GET':
                resp = self.requests.get(url, params=params, headers=headers)
            elif method == 'POST':
                resp = self.requests.post(url, json=data, params=params, headers=headers)
            elif method == 'DELETE':
                resp = self.requests.delete(url, params=params, headers=headers)
            
            # Check for error response content before raising
            if not resp.ok:
                logging.error(f"Upbit API Error: {resp.status_code} {resp.text}")

            resp.raise_for_status()
            
            # Log success only if NOT in mock mode (to reduce noise)
            # We determine mock mode by checking if server_url contains localhost or 127.0.0.1
            # import os
            # is_mock = "localhost" in self.server_url or "127.0.0.1" in self.server_url or os.getenv("MODE", "").upper() == "MOCK"
            # if not is_mock:
            #     logging.info(f"✅ Upbit API Response: {len(resp) if isinstance(resp, list) else 1} items fetched")
                
            return resp.json()
        except Exception as e:
            logging.error(f"Request failed: {e} for url: {url}")
            raise

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

            # Collect tickers to batch-fetch prices
            # LIMIT: Only fetch prices for BTC, ETH, SOL to avoid rate limits
            target_coins = {"BTC", "ETH", "SOL"}
            tickers = []
            for account in accounts:
                currency = account.get('currency')
                if currency and currency != 'KRW' and currency in target_coins:
                    ticker = f"KRW-{currency}"
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

    def get_candles(self, ticker, count=200, interval="minutes/5"):
        """Fetch candle data"""
        try:
            return self._request('GET', f'/v1/candles/{interval}', params={'market': ticker, 'count': count}, auth=False)
        except Exception as e:
            logging.error(f"get_candles failed: {e}")
            return []

    def buy_market_order(self, ticker, amount):
        data = {
            'market': ticker,
            'side': 'bid',
            'price': str(amount),
            'ord_type': 'price'
        }
        return self._request('POST', '/v1/orders', data=data)

    def sell_market_order(self, ticker, volume):
        data = {
            'market': ticker,
            'side': 'ask',
            'volume': str(volume),
            'ord_type': 'market'
        }
        return self._request('POST', '/v1/orders', data=data)

    def buy_limit_order(self, ticker, price, volume):
        # Ensure price is integer string if it's a whole number
        price_str = str(int(price)) if price == int(price) else str(price)
        data = {
            'market': ticker,
            'side': 'bid',
            'volume': str(volume),
            'price': price_str,
            'ord_type': 'limit'
        }
        return self._request('POST', '/v1/orders', data=data)

    def sell_limit_order(self, ticker, price, volume):
        # Ensure price is integer string if it's a whole number
        price_str = str(int(price)) if price == int(price) else str(price)
        data = {
            'market': ticker,
            'side': 'ask',
            'volume': str(volume),
            'price': price_str,
            'ord_type': 'limit'
        }
        return self._request('POST', '/v1/orders', data=data)

    def get_orders(self, ticker=None, state='wait', page=1, limit=100):
        """Fetch orders with filtering"""
        params = {
            'state': state,
            'page': page,
            'limit': limit,
            'order_by': 'desc'
        }
        if ticker:
            params['market'] = ticker
        return self._request('GET', '/v1/orders', params=params)

    def get_order(self, uuid):
        return self._request('GET', '/v1/order', params={'uuid': uuid})

    def cancel_order(self, uuid):
        return self._request('DELETE', '/v1/order', params={'uuid': uuid})

    def set_mock_price(self, ticker, price):
        if "api.upbit.com" in self.server_url:
            logging.warning("set_mock_price called on real Upbit exchange")
            return
        try:
            self.requests.post(f"{self.server_url}/mock/price", json={"ticker": ticker, "price": price})
        except Exception as e:
            logging.error(f"set_mock_price failed: {e}")

    def hold_price(self, ticker, hold=True):
        if "api.upbit.com" in self.server_url:
            logging.warning("hold_price called on real Upbit exchange")
            return
        try:
            self.requests.post(f"{self.server_url}/mock/hold", json={"ticker": ticker, "hold": hold})
        except Exception as e:
            logging.error(f"hold_price failed: {e}")

    def is_price_held(self, ticker):
        if "api.upbit.com" in self.server_url:
            return False
        try:
            resp = self.requests.get(f"{self.server_url}/mock/hold", params={"ticker": ticker})
            if resp.status_code == 200:
                return resp.json().get("held", False)
            return False
        except Exception as e:
            logging.error(f"is_price_held failed: {e}")
            return False

class MockExchange(Exchange):
    """Removed internal mock exchange. Use external mock API server instead."""
    def __init__(self, *args, **kwargs):
        raise RuntimeError("MockExchange is removed. Use the mock API server via UpbitExchange pointing to its URL.")
