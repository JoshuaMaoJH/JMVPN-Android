import socket, threading, time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.clock import Clock
from kivy.metrics import dp

from core.config import ConfigManager, ServerConfig
from core.tunnel import TunnelManager, TunnelStatus
from core.proxy import SystemProxy

_STATUS_COLORS = {
    TunnelStatus.DISCONNECTED: (0.5, 0.5, 0.5, 1),
    TunnelStatus.CONNECTING:   (1, 0.65, 0, 1),
    TunnelStatus.CONNECTED:    (0, 0.73, 0, 1),
    TunnelStatus.ERROR:        (0.8, 0, 0, 1),
}
_STATUS_LABELS = {
    TunnelStatus.DISCONNECTED: "Disconnected",
    TunnelStatus.CONNECTING:   "Connecting...",
    TunnelStatus.CONNECTED:    "Connected",
    TunnelStatus.ERROR:        "Error",
}


class ConnectPanel(BoxLayout):
    def __init__(self, config: ConfigManager,
                 tunnel_manager: TunnelManager,
                 system_proxy: SystemProxy,
                 on_log, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)
        self._config = config
        self._tunnel = tunnel_manager
        self._proxy = system_proxy
        self._on_log = on_log
        self._latency_thread: threading.Thread | None = None
        self._latency_running = False
        self._mode_value = "socks5"
        self._build()

    def _build(self):
        # --- Server selector row ---
        srv_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
        srv_row.add_widget(Label(text="Server", size_hint_x=None, width=dp(60), halign='left', valign='middle'))

        self._server_spinner = Spinner(
            text="(none)", values=["(none)"],
            size_hint_x=1,
        )
        self._server_spinner.bind(text=self._on_server_change)
        srv_row.add_widget(self._server_spinner)

        add_btn = Button(text="+", size_hint_x=None, width=dp(36))
        add_btn.bind(on_release=lambda *_: self._open_add_dialog())
        srv_row.add_widget(add_btn)

        edit_btn = Button(text="Edit", size_hint_x=None, width=dp(50))
        edit_btn.bind(on_release=lambda *_: self._open_edit_dialog())
        srv_row.add_widget(edit_btn)

        del_btn = Button(text="Delete", size_hint_x=None, width=dp(60),
                         background_color=(0.8, 0.2, 0.2, 1))
        del_btn.bind(on_release=lambda *_: self._delete_server())
        srv_row.add_widget(del_btn)
        self.add_widget(srv_row)

        # --- Mode selector row ---
        mode_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
        mode_row.add_widget(Label(text="Mode", size_hint_x=None, width=dp(60), halign='left', valign='middle'))

        self._socks5_btn = ToggleButton(text="SOCKS5 Global Proxy", group='mode', state='down')
        self._socks5_btn.bind(on_release=lambda *_: self._set_mode("socks5"))
        mode_row.add_widget(self._socks5_btn)

        self._forward_btn = ToggleButton(text="Port Forward", group='mode')
        self._forward_btn.bind(on_release=lambda *_: self._set_mode("forward"))
        mode_row.add_widget(self._forward_btn)
        self.add_widget(mode_row)

        # --- SOCKS5 port row ---
        self._socks_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
        self._socks_row.add_widget(Label(text="SOCKS5 Port", size_hint_x=None, width=dp(90)))
        self._socks_port_input = TextInput(text="1080", multiline=False, input_filter='int',
                                           size_hint_x=None, width=dp(70))
        self._socks_row.add_widget(self._socks_port_input)
        self._socks_row.add_widget(Label(text="Proxy Port", size_hint_x=None, width=dp(80)))
        self._proxy_port_input = TextInput(text="1081", multiline=False, input_filter='int',
                                           size_hint_x=None, width=dp(70))
        self._socks_row.add_widget(self._proxy_port_input)
        self.add_widget(self._socks_row)

        # --- Status + connect button row ---
        ctrl_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(4))
        self._status_dot = Label(text="*", size_hint_x=None, width=dp(30),
                                 color=_STATUS_COLORS[TunnelStatus.DISCONNECTED])
        ctrl_row.add_widget(self._status_dot)
        self._status_label = Label(text="Disconnected", size_hint_x=1, halign='left', valign='middle')
        self._status_label.bind(size=self._status_label.setter('text_size'))
        ctrl_row.add_widget(self._status_label)
        self._connect_btn = Button(text="Connect", size_hint_x=None, width=dp(100))
        self._connect_btn.bind(on_release=lambda *_: self._on_connect_click())
        ctrl_row.add_widget(self._connect_btn)
        self.add_widget(ctrl_row)

        # --- Latency row ---
        lat_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(4))
        lat_row.add_widget(Label(text="Latency", size_hint_x=None, width=dp(60), halign='left', valign='middle'))
        self._latency_label = Label(text="--", halign='left', valign='middle')
        self._latency_label.bind(size=self._latency_label.setter('text_size'))
        lat_row.add_widget(self._latency_label)
        self.add_widget(lat_row)

        self.refresh_server_list()

    def get_mode(self) -> str:
        return self._mode_value

    def _set_mode(self, mode: str):
        self._mode_value = mode
        if mode == "socks5":
            if self._socks_row.parent is None:
                children = list(self.children)
                # Insert socks_row after mode_row (index 3 from end)
                idx = len(children) - 2  # after mode_row
                self.add_widget(self._socks_row, index=len(children) - idx)
        else:
            if self._socks_row.parent is not None:
                self.remove_widget(self._socks_row)

    def refresh_server_list(self):
        servers = self._config.list()
        names = [s.name for s in servers] if servers else ["(none)"]
        self._server_spinner.values = names
        if servers:
            self._server_spinner.text = servers[0].name
        else:
            self._server_spinner.text = "(none)"

    def _get_selected_server(self) -> ServerConfig | None:
        name = self._server_spinner.text
        return next((s for s in self._config.list() if s.name == name), None)

    def _on_server_change(self, spinner, text):
        server = self._get_selected_server()
        if server:
            self._socks_port_input.text = str(server.socks5_port)

    def _open_add_dialog(self):
        from ui.server_panel import ServerEditDialog
        ServerEditDialog(self._config, on_save=self.refresh_server_list).open()

    def _open_edit_dialog(self):
        server = self._get_selected_server()
        if not server:
            return
        from ui.server_panel import ServerEditDialog
        ServerEditDialog(self._config, server=server, on_save=self.refresh_server_list).open()

    def _delete_server(self):
        server = self._get_selected_server()
        if server:
            self._config.delete(server.id)
            self.refresh_server_list()

    def _on_connect_click(self):
        if self._tunnel.status in (TunnelStatus.CONNECTED, TunnelStatus.CONNECTING):
            self._do_disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        server = self._get_selected_server()
        if not server:
            self._on_log("Please select a server first", "warn")
            return
        try:
            port = int(self._socks_port_input.text)
            if port != server.socks5_port:
                self._config.update(server.id, socks5_port=port)
                server = self._config.get(server.id)
        except ValueError:
            pass
        mode = self._mode_value
        try:
            proxy_port = int(self._proxy_port_input.text)
        except ValueError:
            proxy_port = 1081
        self._tunnel.connect(server, mode, proxy_port=proxy_port)

    def _do_disconnect(self):
        self._tunnel.disconnect()
        self._proxy.restore()
        self._on_log("Disconnected")

    def set_status(self, status: TunnelStatus):
        color = _STATUS_COLORS[status]
        self._status_dot.color = color
        self._status_label.text = _STATUS_LABELS[status]
        if status == TunnelStatus.CONNECTED:
            self._connect_btn.text = "Disconnect"
            self._start_latency_probe()
        else:
            self._connect_btn.text = "Connect"
            self._stop_latency_probe()
            self._latency_label.text = "--"

    def _start_latency_probe(self):
        self._latency_running = True
        self._latency_thread = threading.Thread(target=self._latency_loop, daemon=True)
        self._latency_thread.start()

    def _stop_latency_probe(self):
        self._latency_running = False

    def _latency_loop(self):
        server = self._get_selected_server()
        if not server:
            return
        while self._latency_running:
            start = time.monotonic()
            try:
                with socket.create_connection((server.host, server.port), timeout=3):
                    pass
                ms = int((time.monotonic() - start) * 1000)
                Clock.schedule_once(lambda dt, m=ms: setattr(self._latency_label, 'text', f"{m} ms"), 0)
            except OSError:
                Clock.schedule_once(lambda dt: setattr(self._latency_label, 'text', "Timeout"), 0)
            time.sleep(5)
