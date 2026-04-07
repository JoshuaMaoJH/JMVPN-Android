from unittest.mock import patch, MagicMock, call
import pytest

@pytest.fixture(autouse=True)
def mock_winreg(mocker):
    mock = mocker.patch("core.proxy.winreg")
    mock.OpenKey.return_value.__enter__ = lambda s: s
    mock.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    mock.QueryValueEx.side_effect = [
        (0, 1),   # ProxyEnable original value
        ("", 1),  # ProxyServer original value
    ]
    return mock

def test_enable_sets_registry(mock_winreg):
    from core.proxy import SystemProxy
    p = SystemProxy()
    p.enable("127.0.0.1", 1080)
    calls = mock_winreg.SetValueEx.call_args_list
    servers = {c.args[1]: c.args[4] for c in calls}
    assert servers["ProxyEnable"] == 1
    assert servers["ProxyServer"] == "socks=127.0.0.1:1080"

def test_restore_resets_registry(mock_winreg):
    from core.proxy import SystemProxy
    p = SystemProxy()
    p.enable("127.0.0.1", 1080)
    mock_winreg.SetValueEx.reset_mock()
    p.restore()
    calls = mock_winreg.SetValueEx.call_args_list
    restored = {c.args[1]: c.args[4] for c in calls}
    assert restored["ProxyEnable"] == 0

def test_restore_without_enable_is_safe(mock_winreg):
    from core.proxy import SystemProxy
    p = SystemProxy()
    p.restore()  # should not raise
