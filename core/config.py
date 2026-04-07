import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".jmvpn" / "servers.json"


@dataclass
class ForwardRule:
    local_port: int
    remote_host: str
    remote_port: int


@dataclass
class ServerConfig:
    name: str
    host: str
    port: int
    username: str
    auth_type: str  # "password" | "key"
    key_path: str
    socks5_port: int
    forwards: list[ForwardRule]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


def _server_from_dict(d: dict) -> ServerConfig:
    forwards = [ForwardRule(**f) for f in d.get("forwards", [])]
    return ServerConfig(
        id=d["id"],
        name=d["name"],
        host=d["host"],
        port=d["port"],
        username=d["username"],
        auth_type=d["auth_type"],
        key_path=d.get("key_path", ""),
        socks5_port=d.get("socks5_port", 1080),
        forwards=forwards,
    )


def _server_to_dict(s: ServerConfig) -> dict:
    d = asdict(s)
    d["forwards"] = [asdict(f) for f in s.forwards]
    return d


class ConfigManager:
    def __init__(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._servers: list[ServerConfig] = []
        self._load()

    def _load(self):
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self._servers = [_server_from_dict(s) for s in data.get("servers", [])]

    def _save(self):
        data = {"servers": [_server_to_dict(s) for s in self._servers]}
        CONFIG_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def list(self) -> list[ServerConfig]:
        return list(self._servers)

    def get(self, server_id: str) -> ServerConfig | None:
        return next((s for s in self._servers if s.id == server_id), None)

    def add(self, server: ServerConfig) -> ServerConfig:
        self._servers.append(server)
        self._save()
        return server

    def update(self, server_id: str, **kwargs: Any) -> ServerConfig:
        s = self.get(server_id)
        if s is None:
            raise KeyError(f"Server {server_id} not found")
        for k, v in kwargs.items():
            setattr(s, k, v)
        self._save()
        return s

    def delete(self, server_id: str) -> None:
        self._servers = [s for s in self._servers if s.id != server_id]
        self._save()
