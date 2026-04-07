import socket, struct, threading
from dataclasses import dataclass
from typing import Callable
import paramiko

@dataclass
class Socks5Request:
    host: str
    port: int

def parse_socks5_request(data: bytes) -> Socks5Request:
    # data starts after initial greeting/auth, at the CONNECT request
    # format: VER CMD RSV ATYP [addr] PORT
    atyp = data[3]
    if atyp == 1:  # IPv4
        host = socket.inet_ntoa(data[4:8])
        port = struct.unpack(">H", data[8:10])[0]
    elif atyp == 3:  # Domain
        length = data[4]
        host = data[5:5 + length].decode()
        port = struct.unpack(">H", data[5 + length:7 + length])[0]
    elif atyp == 4:  # IPv6
        host = socket.inet_ntop(socket.AF_INET6, data[4:20])
        port = struct.unpack(">H", data[20:22])[0]
    else:
        raise ValueError(f"Unsupported ATYP: {atyp}")
    return Socks5Request(host=host, port=port)

class Socks5Server:
    def __init__(self, transport: paramiko.Transport, bind_host: str = "127.0.0.1", bind_port: int = 1080):
        self._transport = transport
        self._bind_host = bind_host
        self._bind_port = bind_port
        self._server_sock: socket.socket | None = None
        self._running = False

    def start(self) -> None:
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._bind_host, self._bind_port))
        self._server_sock.listen(10)
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
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except OSError:
                break

    def _handle_client(self, client: socket.socket) -> None:
        try:
            # Greeting
            client.recv(256)
            client.sendall(b"\x05\x00")  # no auth
            # Request
            request_data = client.recv(256)
            req = parse_socks5_request(request_data)
            # Open paramiko channel
            chan = self._transport.open_channel(
                "direct-tcpip", (req.host, req.port), (self._bind_host, 0)
            )
            # Success response
            client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            # Relay
            self._relay(client, chan)
        except Exception:
            client.close()

    def _relay(self, sock: socket.socket, chan: paramiko.Channel) -> None:
        sock.setblocking(False)
        chan.setblocking(False)
        import select
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
