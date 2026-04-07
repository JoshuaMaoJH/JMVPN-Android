# JMVPN Design Spec
Date: 2026-03-28

## Overview

A desktop VPN client for Windows built with CustomTkinter, tunneling traffic through an overseas SSH server via system `ssh` subprocess. Supports multiple server profiles, two tunnel modes (SOCKS5 global proxy and port forwarding), and stores credentials securely in Windows Credential Manager.

---

## Architecture

```
JMVPN/
├── main.py                  # Entry point, launches App
├── core/
│   ├── tunnel.py            # SSH subprocess management
│   ├── proxy.py             # Windows system proxy toggle (winreg)
│   └── config.py            # Server config CRUD + Credential Manager
├── ui/
│   ├── app.py               # CustomTkinter main window
│   ├── server_panel.py      # Server list + add/edit/delete
│   ├── connect_panel.py     # Connection control + status display
│   └── log_panel.py         # Collapsible log panel
└── utils/
    └── keyring_helper.py    # keyring wrapper for passwords/passphrases
```

**Data flow:**
1. User selects server → selects mode (SOCKS5 / port forwarding) → clicks Connect
2. `tunnel.py` builds ssh arguments, spawns subprocess, monitors stdout/stderr
3. If SOCKS5 global proxy mode, `proxy.py` writes registry keys to enable system proxy
4. On disconnect: kill ssh process, restore system proxy settings

---

## Server Configuration & Credential Storage

Non-sensitive fields saved to `~/.jmvpn/servers.json`:

```json
{
  "servers": [
    {
      "id": "uuid",
      "name": "My Server",
      "host": "1.2.3.4",
      "port": 22,
      "username": "root",
      "auth_type": "password | key",
      "key_path": "/path/to/id_rsa",
      "socks5_port": 1080,
      "forwards": [
        { "local_port": 8080, "remote_host": "localhost", "remote_port": 80 }
      ]
    }
  ]
}
```

**Sensitive fields** (password, key passphrase) stored in Windows Credential Manager via `keyring` library, keyed as `jmvpn-<server-id>`. Never written to disk in plaintext.

---

## SSH Tunnel Management (tunnel.py)

**SOCKS5 mode:**
```
ssh -N -D 127.0.0.1:<socks5_port> -p <port> <user>@<host>
```

**Port forwarding mode** (one `-L` per rule):
```
ssh -N -L 8080:localhost:80 -L 3306:localhost:3306 -p <port> <user>@<host>
```

**Authentication:**
- Key auth (no passphrase): `-i /path/to/key` passed to system `ssh` directly
- Key auth (with passphrase) + Password auth: handled via `paramiko` to avoid Windows `SSH_ASKPASS` / `sshpass` issues; `paramiko` reads credential from `keyring` at connect time

**Process monitoring:**
- Dedicated thread reads stderr for connection signals
- Connection success: process alive + local port reachable (socket probe)
- Unexpected disconnect: triggers UI state update + auto-restores system proxy

---

## Windows System Proxy (proxy.py)

Uses `winreg` to write/read/restore `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings`:
- `ProxyEnable` = 1 / 0
- `ProxyServer` = `socks=127.0.0.1:<port>`

Saves original proxy state before modifying, restores on disconnect or app exit.

---

## UI Layout

Main window (~400px wide, resizable height):

```
┌─────────────────────────────────┐
│  JMVPN              [Minimize]  │
├─────────────────────────────────┤
│  Server: [dropdown ▼]  [+] [Edit]│
├─────────────────────────────────┤
│  Mode: ◉ SOCKS5 Global Proxy    │
│         ○ Port Forwarding       │
│  SOCKS5 Port: [1080]            │
├─────────────────────────────────┤
│  ● Disconnected  [  Connect  ]  │
│  Latency: --                    │
├─────────────────────────────────┤
│  [▶ Logs]  ← collapsible        │
│  ┌───────────────────────────┐  │
│  │ 12:00 Connected           │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**Server edit dialog:** host, port, username, auth type (password / key file), port forwarding rules table (add/remove rows).

**System tray:** minimizes to tray, right-click menu for quick connect/disconnect/quit. Tray icon color reflects connection state (green = connected, grey = disconnected).

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `customtkinter` | UI framework |
| `keyring` | Windows Credential Manager access |
| `paramiko` | SSH for password auth and key-with-passphrase |
| `pystray` + `Pillow` | System tray icon |
| `winreg` | System proxy toggle (stdlib) |

---

## Error Handling

- SSH process fails to start: show error in log, reset UI to disconnected
- SSH process dies unexpectedly: detect via thread, auto-restore proxy, notify user
- Credential not found in keyring: prompt user to re-enter password
- Port already in use: detect before launching, suggest alternative port
