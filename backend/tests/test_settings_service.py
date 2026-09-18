"""Runtime settings: bootstrap from DB/env, key validation, mode switching guards."""
import os
import sys
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.exchange_service import ExchangeService
from services.settings_service import (
    MODE_DEV,
    MODE_REAL,
    SettingsError,
    SettingsService,
    mask_secret,
    normalize_mode,
)


class _StubDB:
    def __init__(self, record=None, running_by_mode=None):
        self.record = record
        self.saved = []
        self.running_by_mode = running_by_mode or {}
        self.assigned_modes = []

    def get_system_config(self):
        return self.record

    def save_system_config(self, **fields):
        self.saved.append(fields)
        base = vars(self.record) if self.record is not None else {}
        merged = {**base, **fields}
        self.record = SimpleNamespace(**merged)
        return self.record

    def assign_missing_strategy_mode(self, mode):
        self.assigned_modes.append(mode)
        return 0

    def count_running_strategies(self, mode=None):
        return self.running_by_mode.get(mode, 0)


class _StubStrategyService:
    def __init__(self):
        self.loaded_modes = []
        self.strategies = {}

    def load_strategies(self, mode=None):
        self.loaded_modes.append(mode)

    def get_all_strategies(self):
        return list(self.strategies.values())


class _FakeExchange:
    def __init__(self, mode, access_key, secret_key, initial_krw):
        self.mode = mode
        self.access_key = access_key
        self.secret_key = secret_key
        self.initial_krw = initial_krw


def _factory(mode, access_key, secret_key, initial_krw):
    if mode == MODE_REAL and not (access_key and secret_key):
        raise RuntimeError("keys required")
    return _FakeExchange(mode, access_key, secret_key, initial_krw)


def _make_service(db=None, env=None, validator=None, strategy_service=None):
    db = db or _StubDB()
    exchange_service = ExchangeService(None)
    strategy_service = strategy_service or _StubStrategyService()
    validator = validator or (lambda a, s: {"valid": True, "krw_balance": 1234.0, "expire_at": "2027-01-01"})
    service = SettingsService(
        db=db,
        exchange_service=exchange_service,
        strategy_service=strategy_service,
        exchange_factory=_factory,
        key_validator=validator,
        env=env or {},
        engine_lock=threading.RLock(),
        accounts_cache={"data": [{"currency": "KRW"}], "timestamp": 99.0},
    )
    return service, db, exchange_service, strategy_service


class TestBootstrap(unittest.TestCase):
    def test_env_seeds_first_boot_and_stamps_legacy_strategies(self):
        env = {"TRADING_MODE": "REAL", "UPBIT_ACCESS_KEY": "AK123456", "UPBIT_SECRET_KEY": "SK123456"}
        service, db, exchange_service, strategy_service = _make_service(env=env)

        service.bootstrap()

        self.assertEqual(service.mode, MODE_REAL)
        self.assertEqual(service.key_source, "env")
        self.assertEqual(exchange_service.mode, MODE_REAL)
        self.assertEqual(exchange_service.exchange.access_key, "AK123456")
        self.assertEqual(db.assigned_modes, [MODE_REAL])
        self.assertEqual(strategy_service.loaded_modes, [MODE_REAL])

    def test_db_settings_take_precedence_over_env(self):
        record = SimpleNamespace(
            mode="DEV", upbit_access_key="DBAK0001", upbit_secret_key="DBSK0001",
            paper_initial_krw=5_000_000.0, key_valid=True, key_last_validated_at=None, key_expire_at=None,
        )
        env = {"TRADING_MODE": "REAL", "UPBIT_ACCESS_KEY": "ENVAK", "UPBIT_SECRET_KEY": "ENVSK"}
        service, _, exchange_service, _ = _make_service(db=_StubDB(record=record), env=env)

        service.bootstrap()

        self.assertEqual(service.mode, MODE_DEV)
        self.assertEqual(service.key_source, "db")
        self.assertEqual(service.access_key, "DBAK0001")
        self.assertEqual(exchange_service.exchange.initial_krw, 5_000_000.0)

    def test_real_mode_without_keys_falls_back_to_dev(self):
        service, _, exchange_service, _ = _make_service(env={"TRADING_MODE": "REAL"})

        service.bootstrap()

        self.assertEqual(service.mode, MODE_DEV)
        self.assertEqual(exchange_service.mode, MODE_DEV)

    def test_public_settings_mask_secrets(self):
        env = {"UPBIT_ACCESS_KEY": "ABCDEFGH1234", "UPBIT_SECRET_KEY": "ZYXWVUTS9876"}
        service, _, _, _ = _make_service(env=env)
        service.bootstrap()

        public = service.get_public_settings()

        self.assertEqual(public["access_key_masked"], "********1234")
        self.assertEqual(public["secret_key_masked"], "********9876")
        self.assertNotIn("ABCDEFGH1234", str(public))
        self.assertTrue(public["has_keys"])


class TestKeys(unittest.TestCase):
    def test_update_keys_validates_and_persists(self):
        service, db, _, _ = _make_service()
        service.bootstrap()

        result = service.update_keys("NEWAK0001", "NEWSK0001")

        self.assertEqual(service.key_source, "db")
        self.assertTrue(result["key_valid"])
        self.assertEqual(result["key_expire_at"], "2027-01-01")
        self.assertEqual(db.saved[-1]["upbit_access_key"], "NEWAK0001")

    def test_update_keys_rejected_when_upbit_refuses(self):
        def validator(a, s):
            raise Exception("Upbit API Error: 401 {'error': {'name': 'invalid_access_key'}}")

        service, db, _, _ = _make_service(validator=validator)
        service.bootstrap()

        with self.assertRaises(SettingsError) as ctx:
            service.update_keys("BADAK", "BADSK")

        self.assertIn("거부", str(ctx.exception))
        self.assertFalse(service.has_keys)
        self.assertEqual(db.saved, [])

    def test_update_keys_in_real_mode_rebuilds_live_exchange(self):
        env = {"TRADING_MODE": "REAL", "UPBIT_ACCESS_KEY": "OLDAK000", "UPBIT_SECRET_KEY": "OLDSK000"}
        service, _, exchange_service, _ = _make_service(env=env)
        service.bootstrap()

        service.update_keys("NEWAK000", "NEWSK000")

        self.assertEqual(exchange_service.exchange.access_key, "NEWAK000")
        self.assertEqual(exchange_service.mode, MODE_REAL)

    def test_validate_keys_without_any_keys_reports_error(self):
        service, _, _, _ = _make_service()
        service.bootstrap()

        result = service.validate_keys()

        self.assertFalse(result["valid"])
        self.assertIn("입력", result["error"])

    def test_clear_keys_refused_in_real_mode(self):
        env = {"TRADING_MODE": "REAL", "UPBIT_ACCESS_KEY": "AK000000", "UPBIT_SECRET_KEY": "SK000000"}
        service, _, _, _ = _make_service(env=env)
        service.bootstrap()

        with self.assertRaises(SettingsError):
            service.clear_keys()


class TestModeSwitch(unittest.TestCase):
    def test_switch_to_real_requires_keys(self):
        service, _, _, _ = _make_service()
        service.bootstrap()

        with self.assertRaises(SettingsError) as ctx:
            service.switch_mode("REAL")

        self.assertIn("API 키", str(ctx.exception))
        self.assertEqual(service.mode, MODE_DEV)

    def test_switch_refused_while_strategies_run(self):
        db = _StubDB(running_by_mode={MODE_DEV: 2})
        env = {"UPBIT_ACCESS_KEY": "AK000000", "UPBIT_SECRET_KEY": "SK000000"}
        service, _, _, _ = _make_service(db=db, env=env)
        service.bootstrap()

        with self.assertRaises(SettingsError) as ctx:
            service.switch_mode("REAL")

        self.assertIn("실행 중", str(ctx.exception))

    def test_switch_to_real_swaps_exchange_reloads_strategies_and_persists(self):
        env = {"UPBIT_ACCESS_KEY": "AK000000", "UPBIT_SECRET_KEY": "SK000000"}
        service, db, exchange_service, strategy_service = _make_service(env=env)
        service.bootstrap()
        accounts_cache = service._accounts_cache

        result = service.switch_mode("real")

        self.assertEqual(result["mode"], MODE_REAL)
        self.assertEqual(exchange_service.mode, MODE_REAL)
        self.assertEqual(exchange_service.exchange.access_key, "AK000000")
        self.assertEqual(strategy_service.loaded_modes, [MODE_DEV, MODE_REAL])
        self.assertEqual(db.saved[-1]["mode"], MODE_REAL)
        self.assertEqual(accounts_cache["data"], [])
        self.assertEqual(accounts_cache["timestamp"], 0.0)
        self.assertTrue(service.key_valid)

    def test_switch_to_real_refused_when_stored_keys_no_longer_validate(self):
        def validator(a, s):
            raise Exception("Upbit API Error: 401 expired")

        env = {"UPBIT_ACCESS_KEY": "AK000000", "UPBIT_SECRET_KEY": "SK000000"}
        service, _, exchange_service, _ = _make_service(env=env, validator=validator)
        service.bootstrap()

        with self.assertRaises(SettingsError):
            service.switch_mode("REAL")

        self.assertEqual(exchange_service.mode, MODE_DEV)

    def test_switch_back_to_dev_uses_paper_initial_krw(self):
        env = {"TRADING_MODE": "REAL", "UPBIT_ACCESS_KEY": "AK000000", "UPBIT_SECRET_KEY": "SK000000"}
        service, _, exchange_service, _ = _make_service(env=env)
        service.bootstrap()
        service.update_paper_initial_krw(2_500_000)

        service.switch_mode("DEV")

        self.assertEqual(exchange_service.mode, MODE_DEV)
        self.assertEqual(exchange_service.exchange.initial_krw, 2_500_000.0)

    def test_same_mode_switch_is_a_noop(self):
        service, db, _, strategy_service = _make_service()
        service.bootstrap()

        service.switch_mode("DEV")

        self.assertEqual(strategy_service.loaded_modes, [MODE_DEV])
        self.assertEqual(db.saved, [])


class TestHelpers(unittest.TestCase):
    def test_normalize_mode_accepts_aliases(self):
        self.assertEqual(normalize_mode("paper"), MODE_DEV)
        self.assertEqual(normalize_mode("live"), MODE_REAL)
        with self.assertRaises(SettingsError):
            normalize_mode("nope")

    def test_mask_secret(self):
        self.assertIsNone(mask_secret(None))
        self.assertEqual(mask_secret("abc"), "***")
        self.assertEqual(mask_secret("abcdefgh"), "****efgh")

    def test_paper_initial_krw_validation(self):
        service, _, _, _ = _make_service()
        service.bootstrap()
        with self.assertRaises(SettingsError):
            service.update_paper_initial_krw(100)
        with self.assertRaises(SettingsError):
            service.update_paper_initial_krw("abc")


if __name__ == "__main__":
    unittest.main()


class _HoldStrategy:
    def __init__(self, sid, running):
        import threading
        self.strategy_id = sid; self.is_running = running; self.lock = threading.RLock(); self.saved = 0; self.events = []
    def save_state(self): self.saved += 1
    def log_event(self, level, t, msg): self.events.append(t)


class _HoldStrategyService(_StubStrategyService):
    def __init__(self):
        super().__init__(); self.held_on_boot_ids = set()
    def load_strategies(self, mode=None):
        super().load_strategies(mode)
        self.strategies = {1: _HoldStrategy(1, True), 2: _HoldStrategy(2, False), 3: _HoldStrategy(3, True)}
    def hold_running_strategies(self, reason):
        from services.strategy_service import StrategyService
        return StrategyService.hold_running_strategies(self, reason)


class TestBootHold(unittest.TestCase):
    def test_default_resumes_running_strategies(self):
        svc = _HoldStrategyService()
        service, _, _, _ = _make_service(strategy_service=svc)
        service.bootstrap()
        self.assertTrue(svc.strategies[1].is_running)
        self.assertEqual(svc.held_on_boot_ids, set())

    def test_switch_off_holds_every_running_strategy_without_cancelling(self):
        record = SimpleNamespace(mode="DEV", upbit_access_key=None, upbit_secret_key=None, paper_initial_krw=1e7,
                                 key_valid=None, key_last_validated_at=None, key_expire_at=None, resume_strategies_on_boot=False)
        svc = _HoldStrategyService()
        service, _, _, _ = _make_service(db=_StubDB(record=record), strategy_service=svc)
        service.bootstrap()
        self.assertFalse(svc.strategies[1].is_running); self.assertFalse(svc.strategies[3].is_running)
        self.assertEqual(svc.held_on_boot_ids, {1, 3})
        self.assertEqual(svc.strategies[1].events, ["HELD_ON_BOOT"])
        self.assertEqual(svc.strategies[2].events, [])  # was not running, untouched
        self.assertEqual(service.get_public_settings()["held_on_boot_ids"], [1, 3])

    def test_env_flag_holds_for_one_boot(self):
        svc = _HoldStrategyService()
        service, _, _, _ = _make_service(env={"HOLD_STRATEGIES_ON_BOOT": "1"}, strategy_service=svc)
        service.bootstrap()
        self.assertEqual(svc.held_on_boot_ids, {1, 3})
