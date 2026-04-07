import sys
from dataclasses import dataclass


class SystemProxy:
    """System proxy control. Only functional on Windows; no-op on other platforms."""

    def __init__(self):
        self._original = None

    def enable(self, host: str, port: int) -> None:
        if sys.platform != "win32":
            return
        self._original = self._read_current()
        self._write(_ProxyState(enabled=1, server=f"{host}:{port}"))

    def restore(self) -> None:
        if sys.platform != "win32":
            return
        if self._original is not None:
            self._write(self._original)
            self._original = None
        else:
            self._write(_ProxyState(enabled=0, server=""))

    # --- Windows-only internals ---

    def _open_key(self, access=None):
        import winreg
        if access is None:
            access = winreg.KEY_READ
        return winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0, access,
        )

    def _read_current(self):
        import winreg
        with self._open_key() as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            try:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except FileNotFoundError:
                server = ""
        return _ProxyState(enabled=enabled, server=server)

    def _write(self, state) -> None:
        import winreg, ctypes
        with self._open_key(winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, state.enabled)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, state.server)
        try:
            wininet = ctypes.windll.wininet
            wininet.InternetSetOptionW(0, 39, 0, 0)
            wininet.InternetSetOptionW(0, 37, 0, 0)
        except Exception:
            pass


@dataclass
class _ProxyState:
    enabled: int
    server: str
