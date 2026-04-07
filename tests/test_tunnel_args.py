from core.config import ServerConfig, ForwardRule
from core.tunnel import SubprocessTunnel

def _server(**kwargs):
    defaults = dict(id="test-id", name="T", host="1.2.3.4", port=22,
                    username="root", auth_type="key", key_path="/k/id_rsa",
                    socks5_port=1080, forwards=[])
    defaults.update(kwargs)
    return ServerConfig(**defaults)

def test_socks5_args():
    s = _server()
    args = SubprocessTunnel.build_args(s, mode="socks5")
    assert "-N" in args
    assert "-D" in args
    idx = args.index("-D")
    assert args[idx + 1] == "127.0.0.1:1080"
    assert "root@1.2.3.4" in args

def test_port_forward_args():
    rules = [ForwardRule(8080, "localhost", 80), ForwardRule(3306, "localhost", 3306)]
    s = _server(forwards=rules)
    args = SubprocessTunnel.build_args(s, mode="forward")
    assert args.count("-L") == 2
    assert "8080:localhost:80" in args
    assert "3306:localhost:3306" in args

def test_key_path_included():
    s = _server(key_path="/home/user/.ssh/id_rsa")
    args = SubprocessTunnel.build_args(s, mode="socks5")
    assert "-i" in args
    idx = args.index("-i")
    assert args[idx + 1] == "/home/user/.ssh/id_rsa"

def test_custom_ssh_port():
    s = _server(port=2222)
    args = SubprocessTunnel.build_args(s, mode="socks5")
    assert "-p" in args
    idx = args.index("-p")
    assert args[idx + 1] == "2222"
