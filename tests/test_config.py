import json
import pytest
from pathlib import Path
from core.config import ServerConfig, ConfigManager, ForwardRule


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.CONFIG_PATH", tmp_path / "servers.json")
    return ConfigManager()


def test_add_and_list_server(tmp_config):
    cfg = tmp_config
    s = ServerConfig(
        name="Test",
        host="1.2.3.4",
        port=22,
        username="root",
        auth_type="password",
        key_path="",
        socks5_port=1080,
        forwards=[],
    )
    cfg.add(s)
    servers = cfg.list()
    assert len(servers) == 1
    assert servers[0].host == "1.2.3.4"
    assert servers[0].id  # uuid was assigned


def test_update_server(tmp_config):
    cfg = tmp_config
    s = ServerConfig(
        name="Old",
        host="1.1.1.1",
        port=22,
        username="u",
        auth_type="key",
        key_path="/k",
        socks5_port=1080,
        forwards=[],
    )
    cfg.add(s)
    sid = cfg.list()[0].id
    cfg.update(sid, name="New", host="2.2.2.2")
    updated = cfg.get(sid)
    assert updated.name == "New"
    assert updated.host == "2.2.2.2"


def test_delete_server(tmp_config):
    cfg = tmp_config
    s = ServerConfig(
        name="Del",
        host="3.3.3.3",
        port=22,
        username="u",
        auth_type="password",
        key_path="",
        socks5_port=1080,
        forwards=[],
    )
    cfg.add(s)
    sid = cfg.list()[0].id
    cfg.delete(sid)
    assert cfg.list() == []


def test_forward_rule_serialization(tmp_config):
    cfg = tmp_config
    rule = ForwardRule(local_port=8080, remote_host="localhost", remote_port=80)
    s = ServerConfig(
        name="Fwd",
        host="4.4.4.4",
        port=22,
        username="u",
        auth_type="key",
        key_path="/k",
        socks5_port=1080,
        forwards=[rule],
    )
    cfg.add(s)
    loaded = cfg.list()[0]
    assert loaded.forwards[0].local_port == 8080


def test_persists_to_disk(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.CONFIG_PATH", tmp_path / "servers.json")
    mgr1 = ConfigManager()
    s = ServerConfig(
        name="P",
        host="5.5.5.5",
        port=22,
        username="u",
        auth_type="password",
        key_path="",
        socks5_port=1080,
        forwards=[],
    )
    mgr1.add(s)
    mgr2 = ConfigManager()
    assert len(mgr2.list()) == 1
