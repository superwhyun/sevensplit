"""Runtime settings: Upbit credentials, execution mode, and mode switching.

Settings live in the ``system_config`` table. Environment variables (``TRADING_MODE``,
``UPBIT_ACCESS_KEY``, ``UPBIT_SECRET_KEY``) seed the first boot of an existing deployment
and act as a fallback when nothing has been saved from the web UI yet.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

MODE_REAL = "REAL"
MODE_DEV = "DEV"
VALID_MODES = (MODE_REAL, MODE_DEV)
MODE_ALIASES = {"PAPER": MODE_DEV, "SIM": MODE_DEV, "SIMULATION": MODE_DEV, "LIVE": MODE_REAL}

DEFAULT_PAPER_INITIAL_KRW = 10_000_000.0


class SettingsError(ValueError):
    """User-facing settings problem (bad keys, unsafe switch, invalid input)."""


def normalize_mode(value: Optional[str]) -> str:
    text = str(value or "").strip().upper()
    text = MODE_ALIASES.get(text, text)
    if text not in VALID_MODES:
        raise SettingsError(f"지원하지 않는 모드입니다: {value!r} (REAL 또는 DEV)")
    return text


def mask_secret(value: Optional[str], visible: int = 4) -> Optional[str]:
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


class SettingsService:
    def __init__(
        self,
        db,
        exchange_service,
        strategy_service,
        exchange_factory: Callable[[str, Optional[str], Optional[str], float], object],
        key_validator: Callable[[str, str], Dict],
        env: Optional[Dict[str, str]] = None,
        engine_lock: Optional[threading.RLock] = None,
        accounts_cache: Optional[dict] = None,
    ):
        self.db = db
        self.exchange_service = exchange_service
        self.strategy_service = strategy_service
        self._exchange_factory = exchange_factory
        self._key_validator = key_validator
        self._env = env or {}
        self._engine_lock = engine_lock or threading.RLock()
        self._accounts_cache = accounts_cache

        self.mode: str = MODE_DEV
        self.access_key: Optional[str] = None
        self.secret_key: Optional[str] = None
        self.key_source: Optional[str] = None  # "db" | "env" | None
        self.paper_initial_krw: float = DEFAULT_PAPER_INITIAL_KRW
        self.resume_strategies_on_boot: bool = True
        self.key_valid: Optional[bool] = None
        self.key_last_validated_at: Optional[datetime] = None
        self.key_expire_at: Optional[str] = None

    # ------------------------------------------------------------------ bootstrap
    def bootstrap(self) -> None:
        """Load persisted settings (falling back to env), build the exchange, load strategies."""
        self._load_from_db_or_env()
        exchange = self._build_exchange(self.mode)
        self.exchange_service.set_exchange(exchange, self.mode)
        stamped = self.db.assign_missing_strategy_mode(self.mode)
        if stamped:
            logging.info(f"Assigned mode={self.mode} to {stamped} legacy strategies")
        self.strategy_service.load_strategies(mode=self.mode)
        self._apply_boot_hold()
        logging.info(
            f"Settings ready: mode={self.mode}, keys={'yes' if self.has_keys else 'no'} "
            f"(source={self.key_source}), paper_initial_krw={self.paper_initial_krw:,.0f}"
        )

    def _apply_boot_hold(self) -> None:
        """Honour the 'resume on boot' switch (DB) or a one-off HOLD_STRATEGIES_ON_BOOT env flag."""
        env_hold = str(self._env.get("HOLD_STRATEGIES_ON_BOOT", "")).strip().lower() in ("1", "true", "yes", "on")
        if self.resume_strategies_on_boot and not env_hold:
            return
        reason = (
            "재기동 시 자동 재개가 꺼져 있어 정지 상태로 시작했습니다. "
            "주문 체결 동기화는 계속되니, 상태를 확인한 뒤 시작을 누르세요."
        )
        self.strategy_service.hold_running_strategies(reason)

    def _load_from_db_or_env(self) -> None:
        record = self.db.get_system_config()
        env_mode = self._env.get("TRADING_MODE")
        env_access = (self._env.get("UPBIT_ACCESS_KEY") or "").strip() or None
        env_secret = (self._env.get("UPBIT_SECRET_KEY") or "").strip() or None

        if record is not None:
            try:
                self.mode = normalize_mode(record.mode)
            except SettingsError:
                self.mode = normalize_mode(env_mode) if env_mode else MODE_DEV
            self.paper_initial_krw = float(record.paper_initial_krw or DEFAULT_PAPER_INITIAL_KRW)
            resume = getattr(record, "resume_strategies_on_boot", True)
            self.resume_strategies_on_boot = True if resume is None else bool(resume)
            self.key_valid = record.key_valid
            self.key_last_validated_at = record.key_last_validated_at
            self.key_expire_at = record.key_expire_at
            if record.upbit_access_key and record.upbit_secret_key:
                self.access_key = record.upbit_access_key
                self.secret_key = record.upbit_secret_key
                self.key_source = "db"
                return
        else:
            try:
                self.mode = normalize_mode(env_mode) if env_mode else MODE_DEV
            except SettingsError:
                logging.warning(f"Invalid TRADING_MODE={env_mode!r}; defaulting to DEV")
                self.mode = MODE_DEV
            env_initial = self._env.get("DEV_INITIAL_KRW") or self._env.get("PAPER_INITIAL_KRW")
            if env_initial:
                try:
                    self.paper_initial_krw = float(env_initial)
                except ValueError:
                    pass

        if env_access and env_secret:
            self.access_key = env_access
            self.secret_key = env_secret
            self.key_source = "env"
        else:
            self.access_key = None
            self.secret_key = None
            self.key_source = None

        if self.mode == MODE_REAL and not self.has_keys:
            logging.warning("REAL mode requested but no Upbit keys available; starting in DEV mode")
            self.mode = MODE_DEV

    # ------------------------------------------------------------------ properties
    @property
    def has_keys(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def _build_exchange(self, mode: str):
        return self._exchange_factory(mode, self.access_key, self.secret_key, self.paper_initial_krw)

    # ------------------------------------------------------------------ read model
    def get_public_settings(self) -> Dict:
        return {
            "mode": self.mode,
            "has_keys": self.has_keys,
            "key_source": self.key_source,
            "access_key_masked": mask_secret(self.access_key),
            "secret_key_masked": mask_secret(self.secret_key),
            "key_valid": self.key_valid,
            "key_last_validated_at": (
                self.key_last_validated_at.isoformat() if self.key_last_validated_at else None
            ),
            "key_expire_at": self.key_expire_at,
            "paper_initial_krw": self.paper_initial_krw,
            "resume_strategies_on_boot": self.resume_strategies_on_boot,
            "held_on_boot_ids": sorted(getattr(self.strategy_service, "held_on_boot_ids", set())),
            "running_strategies": self.db.count_running_strategies(self.mode),
        }

    def get_setup_status(self) -> Dict:
        strategies = self.strategy_service.get_all_strategies()
        return {
            "mode": self.mode,
            "has_keys": self.has_keys,
            "key_valid": self.key_valid,
            "strategy_count": len(strategies),
            "running_strategies": sum(1 for s in strategies if s.is_running),
            "needs_setup": len(strategies) == 0,
        }

    # ------------------------------------------------------------------ keys
    def validate_keys(self, access_key: Optional[str] = None, secret_key: Optional[str] = None) -> Dict:
        """Check credentials against Upbit without saving them. Uses stored keys when omitted."""
        access = (access_key or "").strip() or self.access_key
        secret = (secret_key or "").strip() or self.secret_key
        if not access or not secret:
            return {"valid": False, "error": "Access Key와 Secret Key를 모두 입력하세요."}
        try:
            result = self._key_validator(access, secret) or {}
        except Exception as e:
            logging.warning(f"Key validation failed: {e}")
            return {"valid": False, "error": self._friendly_key_error(str(e))}
        result.setdefault("valid", True)
        return result

    def update_keys(self, access_key: str, secret_key: str, validate: bool = True) -> Dict:
        access = (access_key or "").strip()
        secret = (secret_key or "").strip()
        if not access or not secret:
            raise SettingsError("Access Key와 Secret Key를 모두 입력하세요.")

        validation = None
        if validate:
            validation = self.validate_keys(access, secret)
            if not validation.get("valid"):
                raise SettingsError(validation.get("error") or "키 검증에 실패했습니다.")

        now = datetime.now(timezone.utc)
        self.access_key = access
        self.secret_key = secret
        self.key_source = "db"
        self.key_valid = bool(validation.get("valid")) if validation else None
        self.key_last_validated_at = now if validation else None
        self.key_expire_at = validation.get("expire_at") if validation else None
        self.db.save_system_config(
            mode=self.mode,
            upbit_access_key=access,
            upbit_secret_key=secret,
            paper_initial_krw=self.paper_initial_krw,
            key_valid=self.key_valid,
            key_last_validated_at=self.key_last_validated_at,
            key_expire_at=self.key_expire_at,
        )

        # A live exchange must pick up the new credentials immediately.
        if self.mode == MODE_REAL:
            with self._engine_lock:
                self.exchange_service.set_exchange(self._build_exchange(MODE_REAL), MODE_REAL)
                self._reset_accounts_cache()
        return self.get_public_settings()

    def clear_keys(self) -> Dict:
        if self.mode == MODE_REAL:
            raise SettingsError("실거래 모드에서는 키를 삭제할 수 없습니다. 먼저 모의 모드로 전환하세요.")
        self.access_key = None
        self.secret_key = None
        self.key_source = None
        self.key_valid = None
        self.key_last_validated_at = None
        self.key_expire_at = None
        self.db.save_system_config(
            mode=self.mode,
            upbit_access_key=None,
            upbit_secret_key=None,
            key_valid=None,
            key_last_validated_at=None,
            key_expire_at=None,
        )
        return self.get_public_settings()

    def update_paper_initial_krw(self, amount: float) -> Dict:
        try:
            value = float(amount)
        except (TypeError, ValueError):
            raise SettingsError("모의 투자 시작 금액은 숫자여야 합니다.")
        if value < 5000:
            raise SettingsError("모의 투자 시작 금액은 최소 5,000원이어야 합니다.")
        self.paper_initial_krw = value
        self.db.save_system_config(mode=self.mode, paper_initial_krw=value)
        return self.get_public_settings()

    def update_resume_on_boot(self, enabled: bool) -> Dict:
        self.resume_strategies_on_boot = bool(enabled)
        self.db.save_system_config(mode=self.mode, resume_strategies_on_boot=self.resume_strategies_on_boot)
        return self.get_public_settings()

    # ------------------------------------------------------------------ mode switch
    def switch_mode(self, target: str) -> Dict:
        mode = normalize_mode(target)
        if mode == self.mode:
            return self.get_public_settings()

        running = self.db.count_running_strategies(self.mode)
        if running > 0:
            raise SettingsError(f"실행 중인 전략이 {running}개 있습니다. 먼저 모두 정지한 뒤 모드를 바꾸세요.")

        if mode == MODE_REAL:
            if not self.has_keys:
                raise SettingsError("실거래 모드로 전환하려면 업비트 API 키가 필요합니다.")
            validation = self.validate_keys()
            if not validation.get("valid"):
                raise SettingsError(f"업비트 키 검증 실패: {validation.get('error') or '알 수 없는 오류'}")
            self.key_valid = True
            self.key_last_validated_at = datetime.now(timezone.utc)
            self.key_expire_at = validation.get("expire_at") or self.key_expire_at

        with self._engine_lock:
            exchange = self._build_exchange(mode)
            self.exchange_service.set_exchange(exchange, mode)
            self.mode = mode
            self._reset_accounts_cache()
            self.strategy_service.load_strategies(mode=mode)

        self.db.save_system_config(
            mode=mode,
            key_valid=self.key_valid,
            key_last_validated_at=self.key_last_validated_at,
            key_expire_at=self.key_expire_at,
        )
        logging.info(f"Execution mode switched to {mode}")
        return self.get_public_settings()

    # ------------------------------------------------------------------ helpers
    def _reset_accounts_cache(self) -> None:
        if self._accounts_cache is not None:
            self._accounts_cache["data"] = []
            self._accounts_cache["timestamp"] = 0.0

    @staticmethod
    def _friendly_key_error(message: str) -> str:
        lowered = message.lower()
        if "invalid_access_key" in lowered or "401" in lowered:
            return "업비트가 키를 거부했습니다. Access Key와 Secret Key를 다시 확인하세요."
        if "no_authorization_ip" in lowered or "out_of_scope" in lowered:
            return "이 서버의 IP가 업비트 API 키 허용 IP에 등록되어 있지 않습니다."
        if "expired" in lowered:
            return "만료된 API 키입니다. 업비트에서 키를 재발급하세요."
        if "timeout" in lowered or "connection" in lowered:
            return "업비트 서버에 연결할 수 없습니다. 네트워크를 확인하세요."
        return message
