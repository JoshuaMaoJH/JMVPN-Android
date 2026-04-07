import socket, struct
from unittest.mock import MagicMock, patch
from core.socks5 import parse_socks5_request, Socks5Request

def test_parse_ipv4_request():
    # CONNECT 1.2.3.4:80
    data = bytes([5, 1, 0, 1, 1, 2, 3, 4, 0, 80])
    req = parse_socks5_request(data)
    assert req.host == "1.2.3.4"
    assert req.port == 80

def test_parse_domain_request():
    hostname = b"example.com"
    data = bytes([5, 1, 0, 3, len(hostname)]) + hostname + struct.pack(">H", 443)
    req = parse_socks5_request(data)
    assert req.host == "example.com"
    assert req.port == 443

def test_parse_ipv6_request():
    ipv6_bytes = bytes(16)  # all zeros = ::
    data = bytes([5, 1, 0, 4]) + ipv6_bytes + struct.pack(">H", 8080)
    req = parse_socks5_request(data)
    assert req.port == 8080
