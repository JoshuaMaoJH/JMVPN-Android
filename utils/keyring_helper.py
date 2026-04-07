import json, os, sys
from pathlib import Path

_SERVICE = "jmvpn"


def _key(server_id: str) -> str:
    return f"jmvpn-{server_id}"


def _use_file_backend() -> bool:
    return sys.platform not in ("win32", "darwin")


# --- File-based fallback for Android/Linux ---

def _cred_path() -> Path:
    return Path.home() / ".jmvpn" / "credentials.json"


def _load_creds() -> dict:
    p = _cred_path()
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _save_creds(data: dict) -> None:
    p = _cred_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


# --- Public API ---

def get_credential(server_id: str) -> str | None:
    if _use_file_backend():
        return _load_creds().get(_key(server_id))
    import keyring
    return keyring.get_password(_SERVICE, _key(server_id))


def set_credential(server_id: str, secret: str) -> None:
    if _use_file_backend():
        creds = _load_creds()
        creds[_key(server_id)] = secret
        _save_creds(creds)
        return
    import keyring
    keyring.set_password(_SERVICE, _key(server_id), secret)


def delete_credential(server_id: str) -> None:
    if _use_file_backend():
        creds = _load_creds()
        creds.pop(_key(server_id), None)
        _save_creds(creds)
        return
    import keyring, keyring.errors
    try:
        keyring.delete_password(_SERVICE, _key(server_id))
    except keyring.errors.PasswordDeleteError:
        pass
