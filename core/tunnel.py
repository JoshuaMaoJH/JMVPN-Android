import socket, subprocess, threading, time
from enum import Enum
from typing import Callable
import paramiko
from core.config import ServerConfig
from core.socks5 import Socks5Server
from core.http_proxy import HttpConnectProxy
from utils.keyring_helper import get_credential

class TunnelStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class SubprocessTunnel:
    """Uses system ssh binary. Requires key auth without passphrase."""

    @staticmethod
    def build_args(server: ServerConfig, mode: str) -> list[str]:
        args = ["ssh", "-N", "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=30",
                "-p", str(server.port),
                "-i", server.key_path]
        if mode == "socks5":
            args += ["-D", f"127.0.0.1:{server.socks5_port}"]
        elif mode == "forward":
            for r in server.forwards:
                args += ["-L", f"{r.local_port}:{r.remote_host}:{r.remote_port}"]
        args.append(f"{server.username}@{server.host}")
        return args

    def __init__(self, server: ServerConfig, mode: str,
                 on_log: Callable[[str], None],
                 on_disconnect: Callable[[], None]):
        self._server = server
        self._mode = mode
        self._on_log = on_log
        self._on_disconnect = on_disconnect
        self._proc: subprocess.Popen | None = None

    def connect(self) -> None:
        args = self.build_args(self._server, self._mode)
        self._proc = subprocess.Popen(
            args, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        threading.Thread(target=self._monitor, daemon=True).start()

    def disconnect(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _monitor(self) -> None:
        assert self._proc is not None
        for line in self._proc.stderr:
            self._on_log(line.decode(errors="replace").strip())
        self._proc.wait()
        self._on_disconnect()


class ParamikoTunnel:
    """Uses paramiko. Handles password auth and key-with-passphrase."""

    def __init__(self, server: ServerConfig, mode: str,
                 on_log: Callable[[str], None],
                 on_disconnect: Callable[[], None]):
        self._server = server
        self._mode = mode
        self._on_log = on_log
        self._on_disconnect = on_disconnect
        self._transport: paramiko.Transport | None = None
        self._socks5: Socks5Server | None = None
        self._forward_threads: list[threading.Thread] = []
        self._disconnecting = False
        self._forward_sockets: list[socket.socket] = []

    def connect(self) -> None:
        credential = get_credential(self._server.id)
        sock = socket.create_connection((self._server.host, self._server.port), timeout=15)
        self._transport = paramiko.Transport(sock)
        self._transport.start_client()

        if self._server.auth_type == "password":
            self._transport.auth_password(self._server.username, credential or "")
        else:  # key with passphrase
            key = paramiko.PKey.from_private_key_file(
                self._server.key_path, password=credential
            )
            self._transport.auth_publickey(self._server.username, key)

        self._on_log("SSH authenticated via paramiko")

        if self._mode == "socks5":
            self._socks5 = Socks5Server(self._transport, bind_port=self._server.socks5_port)
            self._socks5.start()
            self._on_log(f"SOCKS5 listening on 127.0.0.1:{self._server.socks5_port}")
        elif self._mode == "forward":
            for rule in self._server.forwards:
                t = threading.Thread(
                    target=self._accept_forward,
                    args=(rule.local_port, rule.remote_host, rule.remote_port),
                    daemon=True,
                )
                t.start()
                self._forward_threads.append(t)
                self._on_log(f"Forwarding 127.0.0.1:{rule.local_port} → {rule.remote_host}:{rule.remote_port}")

        threading.Thread(target=self._watch_transport, daemon=True).start()

    def _accept_forward(self, local_port: int, remote_host: str, remote_port: int) -> None:
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", local_port))
        srv.listen(10)
        srv.settimeout(1.0)
        self._forward_sockets.append(srv)
        while self._transport and self._transport.is_active() and not self._disconnecting:
            try:
                client, _ = srv.accept()
                chan = self._transport.open_channel(
                    "direct-tcpip", (remote_host, remote_port), ("127.0.0.1", 0)
                )
                threading.Thread(
                    target=self._relay_forward, args=(client, chan), daemon=True
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break
        srv.close()
        if srv in self._forward_sockets:
            self._forward_sockets.remove(srv)

    def _relay_forward(self, sock: socket.socket, chan: paramiko.Channel) -> None:
        import select
        sock.setblocking(False)
        chan.setblocking(False)
        try:
            while True:
                r, _, _ = select.select([sock, chan], [], [], 1.0)
                if sock in r:
                    data = sock.recv(4096)
                    if not data:
                        break
                    chan.sendall(data)
                if chan in r:
                    data = chan.recv(4096)
                    if not data:
                        break
                    sock.sendall(data)
        finally:
            sock.close()
            chan.close()

    def _watch_transport(self) -> None:
        while self._transport and self._transport.is_active():
            time.sleep(2)
        if not self._disconnecting:
            self._on_disconnect()

    def disconnect(self) -> None:
        self._disconnecting = True
        for srv_sock in self._forward_sockets:
            try:
                srv_sock.close()
            except OSError:
                pass
        if self._socks5:
            self._socks5.stop()
        if self._transport:
            self._transport.close()

    def is_alive(self) -> bool:
        return self._transport is not None and self._transport.is_active()


class TunnelManager:
    """Selects SubprocessTunnel or ParamikoTunnel and probes port for status."""

    def __init__(self, on_log: Callable[[str], None],
                 on_status_change: Callable[[TunnelStatus], None]):
        self._on_log = on_log
        self._on_status_change = on_status_change
        self._tunnel: SubprocessTunnel | ParamikoTunnel | None = None
        self._server: ServerConfig | None = None
        self._mode: str | None = None
        self._http_proxy: HttpConnectProxy | None = None
        self.status = TunnelStatus.DISCONNECTED

    @property
    def http_proxy_port(self) -> int | None:
        """Port of the local HTTP CONNECT proxy, or None if not running."""
        return self._http_proxy.port if self._http_proxy else None

    def connect(self, server: ServerConfig, mode: str, proxy_port: int = 1081) -> None:
        self._server = server
        self._mode = mode
        self._proxy_port = proxy_port
        self._set_status(TunnelStatus.CONNECTING)
        use_subprocess = (server.auth_type == "key" and not get_credential(server.id))
        if use_subprocess:
            self._tunnel = SubprocessTunnel(server, mode, self._on_log, self._handle_disconnect)
        else:
            self._tunnel = ParamikoTunnel(server, mode, self._on_log, self._handle_disconnect)
        try:
            self._tunnel.connect()
            threading.Thread(target=self._probe_until_connected, daemon=True).start()
        except Exception as e:
            self._on_log(f"Connection error: {e}")
            self._set_status(TunnelStatus.ERROR)

    def disconnect(self) -> None:
        if self._http_proxy:
            self._http_proxy.stop()
            self._http_proxy = None
        if self._tunnel:
            self._tunnel.disconnect()
        self._set_status(TunnelStatus.DISCONNECTED)

    def _handle_disconnect(self) -> None:
        self._set_status(TunnelStatus.DISCONNECTED)

    def _set_status(self, status: TunnelStatus) -> None:
        self.status = status
        self._on_status_change(status)

    def _probe_until_connected(self) -> None:
        assert self._server is not None
        if self._mode == "socks5":
            port = self._server.socks5_port
        elif self._server.forwards:
            port = self._server.forwards[0].local_port
        else:
            self._on_log("No port forwarding rules configured, cannot probe connection", "warn")
            self._set_status(TunnelStatus.ERROR)
            return
        for _ in range(30):
            time.sleep(1)
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    if self._mode == "socks5":
                        self._http_proxy = HttpConnectProxy(
                            socks5_port=self._server.socks5_port, bind_port=self._proxy_port
                        )
                        self._http_proxy.start()
                        self._on_log(f"HTTP proxy listening on 127.0.0.1:{self._proxy_port}")
                    self._set_status(TunnelStatus.CONNECTED)
                    self._on_log("Tunnel established")
                    return
            except OSError:
                continue
        self._on_log("Timeout waiting for tunnel port")
        self._set_status(TunnelStatus.ERROR)
