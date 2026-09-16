"""UpbitExchange HTTP client: timeouts, 429 backoff, pagination, order formatting."""
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exchange import UpbitExchange


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = str(self._payload)

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._payload


class _FakeRequests:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._next("DELETE", url, **kwargs)


class _FakeTime:
    def __init__(self):
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def time(self):
        return 0.0


def _client(responses):
    client = UpbitExchange("ak", "sk")
    client.requests = _FakeRequests(responses)
    client.time = _FakeTime()
    return client


class TestRequestTransport(unittest.TestCase):
    def test_every_request_carries_a_timeout(self):
        client = _client([_FakeResponse(200, {"ok": True})])

        client._request("GET", "/v1/accounts")
        client._request("POST", "/v1/orders", data={"market": "KRW-BTC"})
        client._request("DELETE", "/v1/order", params={"uuid": "x"})

        for _, _, kwargs in client.requests.calls:
            self.assertEqual(kwargs.get("timeout"), UpbitExchange.REQUEST_TIMEOUT)

    def test_rate_limit_is_retried_with_backoff(self):
        client = _client([
            _FakeResponse(429, {"error": "Too many requests"}, headers={"Remaining-Req": "group=order; min=0; sec=0"}),
            _FakeResponse(429, {"error": "Too many requests"}),
            _FakeResponse(200, {"uuid": "ok"}),
        ])

        result = client._request("GET", "/v1/order", params={"uuid": "x"})

        self.assertEqual(result, {"uuid": "ok"})
        self.assertEqual(len(client.requests.calls), 3)
        self.assertEqual(client.time.sleeps, list(UpbitExchange.RATE_LIMIT_BACKOFF_SEC[:2]))

    def test_rate_limit_gives_up_after_backoff_schedule(self):
        client = _client([_FakeResponse(429, {"error": "Too many requests"})])

        with self.assertRaises(Exception) as ctx:
            client._request("GET", "/v1/order", params={"uuid": "x"})

        self.assertIn("429", str(ctx.exception))
        self.assertEqual(len(client.requests.calls), 1 + len(UpbitExchange.RATE_LIMIT_BACKOFF_SEC))


class TestOpenOrdersPagination(unittest.TestCase):
    def test_get_orders_follows_pages_until_a_short_page(self):
        page_limit = UpbitExchange.ORDERS_PAGE_LIMIT
        full_page = [{"uuid": f"o{i}"} for i in range(page_limit)]
        client = _client([
            _FakeResponse(200, full_page),
            _FakeResponse(200, [{"uuid": f"p{i}"} for i in range(page_limit)]),
            _FakeResponse(200, [{"uuid": "last-1"}, {"uuid": "last-2"}]),
        ])

        orders = client.get_orders(state="wait")

        self.assertEqual(len(orders), page_limit * 2 + 2)
        self.assertEqual(len(client.requests.calls), 3)
        pages = [call[2]["params"]["page"] for call in client.requests.calls]
        self.assertEqual(pages, [1, 2, 3])

    def test_get_orders_single_page_when_fetch_all_disabled(self):
        page_limit = UpbitExchange.ORDERS_PAGE_LIMIT
        client = _client([_FakeResponse(200, [{"uuid": f"o{i}"} for i in range(page_limit)])])

        orders = client.get_orders(state="wait", fetch_all=False)

        self.assertEqual(len(orders), page_limit)
        self.assertEqual(len(client.requests.calls), 1)


class TestOrderFormatting(unittest.TestCase):
    def test_format_volume_never_uses_scientific_notation(self):
        self.assertEqual(UpbitExchange.format_volume(3e-05), "0.00003")
        self.assertEqual(UpbitExchange.format_volume(0.5), "0.5")
        self.assertEqual(UpbitExchange.format_volume(1.23456789), "1.23456789")
        self.assertEqual(UpbitExchange.format_volume(2.0), "2")
        self.assertEqual(UpbitExchange.format_volume(0.000123456789), "0.00012346")

    def test_format_price_keeps_integers_clean(self):
        self.assertEqual(UpbitExchange.format_price(150000000), "150000000")
        self.assertEqual(UpbitExchange.format_price(100000.0), "100000")
        self.assertEqual(UpbitExchange.format_price(0.1), "0.1")

    def test_sell_limit_order_sends_fixed_point_volume(self):
        client = _client([_FakeResponse(200, {"uuid": "sell"})])

        client.sell_limit_order("KRW-BTC", 150000000, 3.3e-05)

        _, _, kwargs = client.requests.calls[0]
        self.assertEqual(kwargs["json"]["volume"], "0.000033")
        self.assertEqual(kwargs["json"]["price"], "150000000")

    def test_buy_market_order_sends_whole_krw_amount(self):
        client = _client([_FakeResponse(200, {"uuid": "buy"})])

        client.buy_market_order("KRW-BTC", 100000.0)

        _, _, kwargs = client.requests.calls[0]
        self.assertEqual(kwargs["json"]["price"], "100000")


if __name__ == "__main__":
    unittest.main()
