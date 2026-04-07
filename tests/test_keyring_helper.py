from unittest.mock import patch, call
from utils.keyring_helper import get_credential, set_credential, delete_credential

SERVICE = "jmvpn"

def test_get_credential_returns_password(mocker):
    mocker.patch("keyring.get_password", return_value="secret")
    result = get_credential("server-uuid-1")
    assert result == "secret"

def test_get_credential_returns_none_when_missing(mocker):
    mocker.patch("keyring.get_password", return_value=None)
    assert get_credential("server-uuid-1") is None

def test_set_credential(mocker):
    mock_set = mocker.patch("keyring.set_password")
    set_credential("server-uuid-1", "mysecret")
    mock_set.assert_called_once_with(SERVICE, "jmvpn-server-uuid-1", "mysecret")

def test_delete_credential(mocker):
    mock_del = mocker.patch("keyring.delete_password")
    delete_credential("server-uuid-1")
    mock_del.assert_called_once_with(SERVICE, "jmvpn-server-uuid-1")

def test_delete_credential_ignores_missing(mocker):
    import keyring.errors
    mocker.patch("keyring.delete_password", side_effect=keyring.errors.PasswordDeleteError("not found"))
    delete_credential("server-uuid-1")  # should not raise
