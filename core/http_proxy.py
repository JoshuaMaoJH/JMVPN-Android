import select, socket, threading
import socks

class HttpConnectProxy:
    """Local HTTP CONNECT proxy that routes through SOCKS5 with remote DNS.

    Browsers connect here over plain HTTP.  For each CONNECT request the proxy
    opens a SOCKS5 connection to the upstream with rdns=True so the hostname is
    resolved on the remote server — bypassing local (potentially poisoned) DNS.
    """

    def __init__(self, socks5_port: int = 1080, bind_port: int = 1081):
        self._socks5_port = socks5_port
        self._bind_port = bind_port
        self._server_sock: socket.socket | None = None
        self._running = False

    @property
    def port(self) -> int:
        return self._bind_port

    def start(self) -> None:
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("127.0.0.1", self._bind_port))
        self._server_sock.listen(20)
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        if self._server_sock:
            self._server_sock.close()

    def _accept_loop(self) -> None:
        while self._running:
            try:
                client, _ = self._server_sock.accept()
                threading.Thread(target=self._handle, args=(client,), daemon=True).start()
            except OSError:
                break

    def _handle(self, client: socket.socket) -> None:
        try:
            # Read request headers
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client.recv(4096)
                if not chunk:
                    return
                data += chunk

            first_line = data.split(b"\r\n")[0].decode(errors="replace")
            parts = first_line.split()
            if len(parts) < 2 or parts[0].upper() != "CONNECT":
                client.close()
                return

            host, port_str = parts[1].rsplit(":", 1)
            port = int(port_str)

            # Connect through SOCKS5; rdns=True means the hostname is sent to
            # the remote server for resolution, not resolved locally.
            remote = socks.socksocket()
            remote.set_proxy(socks.SOCKS5, "127.0.0.1", self._socks5_port, rdns=True)
            remote.settimeout(15)
            remote.connect((host, port))
            remote.settimeout(None)

            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._relay(client, remote)
        except Exception:
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            except Exception:
                pass
            client.close()

    def _relay(self, a: socket.socket, b: socket.socket) -> None:
        a.setblocking(False)
        b.setblocking(False)
        try:
            while True:
                r, _, _ = select.select([a, b], [], [], 1.0)
                if a in r:
                    data = a.recv(4096)
                    if not data:
                        break
                    b.sendall(data)
                if b in r:
                    data = b.recv(4096)
                    if not data:
                        break
                    a.sendall(data)
        finally:
            a.close()
            b.close()
