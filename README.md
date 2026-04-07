# JMVPN

A Windows desktop VPN client that tunnels traffic through an overseas SSH server. Built with CustomTkinter.

## Features

- **SOCKS5 Global Proxy** — sets Windows system proxy automatically, all browsers work without extra configuration
- **Port Forwarding** — forward specific local ports to remote hosts via SSH `-L` tunnels
- **Multiple server profiles** — save and switch between multiple SSH servers
- **Two auth methods** — password or SSH key file (with or without passphrase)
- **Secure credential storage** — passwords and passphrases stored in Windows Credential Manager, never on disk in plaintext
- **System tray** — minimizes to tray, green/grey icon reflects connection state
- **Connection log** — collapsible log panel shows tunnel status and latency

## How It Works

```
Browser → HTTP CONNECT Proxy (127.0.0.1:1081)
              ↓ hostname passed as-is (no local DNS)
          SOCKS5 (127.0.0.1:1080)
              ↓ SSH tunnel
          Remote server resolves DNS → fetches content
```

DNS is resolved on the remote server, bypassing local DNS pollution.

## Requirements

- Windows 10 / 11
- Python 3.11+
- An overseas SSH server

## Installation

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Or use the prebuilt `dist/JMVPN.exe` — no Python required.

## Build Executable

```bash
python -m PyInstaller --noconfirm --onefile --windowed --name JMVPN \
    --collect-all customtkinter \
    --hidden-import keyring.backends.Windows \
    --hidden-import pystray._win32 \
    main.py
```

Output: `dist/JMVPN.exe`

## Usage

1. Click **+** to add a server profile (host, port, username, auth method)
2. Select **SOCKS5 Global Proxy** or **Port Forwarding** mode
3. Click **Connect**
4. On success, Windows system proxy is set automatically — open any browser and browse freely

To disconnect, click **Disconnect**. The system proxy is restored to its previous state automatically.

## SSH Key Setup (Tencent Cloud / other providers)

1. In the cloud console, create a new SSH key pair and download the `.pem` file
2. Fix key file permissions (required by OpenSSH):
   ```powershell
   $path = "C:\path\to\key.pem"
   icacls $path /inheritance:r
   icacls $path /grant ${env:USERNAME}:R
   ```
3. In JMVPN, select **Key File** auth and browse to the `.pem` file
4. Leave **Passphrase** blank (cloud-generated keys have no passphrase)
5. Set **Username** to `ubuntu` (not `root`) for Ubuntu-based cloud servers

## Project Structure

```
JMVPN/
├── main.py                  # Entry point
├── core/
│   ├── config.py            # Server profile CRUD (JSON)
│   ├── tunnel.py            # SSH tunnel (subprocess + paramiko)
│   ├── socks5.py            # SOCKS5 server backed by paramiko
│   ├── http_proxy.py        # HTTP CONNECT proxy (remote DNS via SOCKS5)
│   └── proxy.py             # Windows system proxy toggle (winreg)
├── ui/
│   ├── app.py               # Main window + tray icon
│   ├── connect_panel.py     # Server selector, mode, connect button
│   ├── server_panel.py      # Add/edit server dialog
│   └── log_panel.py         # Collapsible log panel
└── utils/
    └── keyring_helper.py    # Windows Credential Manager wrapper
```

## Running Tests

```bash
pytest -v
```

## Dependencies

| Package | Purpose |
|---------|---------|
| customtkinter | UI framework |
| paramiko | SSH (password auth, key-with-passphrase) |
| PySocks | SOCKS5 client for HTTP proxy remote DNS |
| keyring | Windows Credential Manager |
| pystray + Pillow | System tray icon |
