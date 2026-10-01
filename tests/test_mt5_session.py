from types import SimpleNamespace

from xau_detective.environment import TradingEnvironment
from xau_detective.mt5_session import MT5SessionMonitor


def account(login=123, server="Demo-Server", trade_mode=0, trade_allowed=True):
    return SimpleNamespace(
        login=login,
        server=server,
        trade_mode=trade_mode,
        trade_allowed=trade_allowed,
    )


def test_first_refresh_creates_demo_session():
    monitor = MT5SessionMonitor()
    state = monitor.refresh(
        account(),
        connected=True,
        connection_healthy=True,
        execution_enabled=True,
    )
    assert state.identity.login == "123"
    assert state.identity.server == "Demo-Server"
    assert state.identity.environment is TradingEnvironment.DEMO
    assert monitor.session_changed(account()) is False


def test_monitor_detects_account_switch():
    monitor = MT5SessionMonitor()
    monitor.refresh(
        account(login=123, server="Demo-A", trade_mode=0),
        connected=True,
        connection_healthy=True,
        execution_enabled=True,
    )
    assert monitor.session_changed(account(login=456, server="Demo-B", trade_mode=0)) is True


def test_monitor_detects_demo_to_live_switch():
    monitor = MT5SessionMonitor()
    monitor.refresh(
        account(login=123, server="Broker-Demo", trade_mode=0),
        connected=True,
        connection_healthy=True,
        execution_enabled=True,
    )
    assert monitor.session_changed(
        account(login=123, server="Broker-Live", trade_mode=2)
    ) is True


def test_refresh_updates_capabilities_after_switch():
    monitor = MT5SessionMonitor()
    monitor.refresh(
        account(login=123, server="Demo", trade_mode=0),
        connected=True,
        connection_healthy=True,
        execution_enabled=True,
    )
    state = monitor.refresh(
        account(login=123, server="Live", trade_mode=2),
        connected=True,
        connection_healthy=True,
        execution_enabled=False,
    )
    assert state.capabilities.environment is TradingEnvironment.LIVE
    assert state.capabilities.execution_enabled is False
