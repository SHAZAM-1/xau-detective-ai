"""MT5 account-session monitoring and automatic environment switching."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .environment import AccountCapabilities, TradingEnvironment
from .mt5_environment import detect_environment_from_mt5


@dataclass(frozen=True)
class MT5SessionIdentity:
    login: str
    server: str
    environment: TradingEnvironment


@dataclass(frozen=True)
class MT5SessionState:
    identity: MT5SessionIdentity
    capabilities: AccountCapabilities


class MT5SessionMonitor:
    """Refresh MT5 capabilities and detect account/environment switches."""

    def __init__(self) -> None:
        self._state: MT5SessionState | None = None

    @property
    def state(self) -> MT5SessionState | None:
        return self._state

    def refresh(
        self,
        account_info: Any,
        *,
        connected: bool,
        connection_healthy: bool,
        execution_enabled: bool,
        symbol: str = "XAUUSD",
        symbol_available: bool = True,
        mt5_module: Any | None = None,
    ) -> MT5SessionState:
        environment = detect_environment_from_mt5(
            account_info,
            mt5_module=mt5_module,
        )
        identity = MT5SessionIdentity(
            login=str(getattr(account_info, "login", "")),
            server=str(getattr(account_info, "server", "")),
            environment=environment,
        )
        capabilities = AccountCapabilities(
            environment=environment,
            connected=connected,
            connection_healthy=connection_healthy,
            trading_allowed=bool(getattr(account_info, "trade_allowed", False)),
            execution_enabled=execution_enabled,
            symbol_available=symbol_available,
            symbol=symbol,
            server=getattr(account_info, "server", None),
        )
        self._state = MT5SessionState(identity=identity, capabilities=capabilities)
        return self._state

    def session_changed(self, account_info: Any, *, mt5_module: Any | None = None) -> bool:
        """Return True when login/server/environment differs from the active state."""
        if self._state is None:
            return True
        environment = detect_environment_from_mt5(account_info, mt5_module=mt5_module)
        identity = MT5SessionIdentity(
            login=str(getattr(account_info, "login", "")),
            server=str(getattr(account_info, "server", "")),
            environment=environment,
        )
        return identity != self._state.identity
