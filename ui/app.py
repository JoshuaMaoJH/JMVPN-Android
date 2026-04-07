import atexit, os, sys, threading
from kivy.app import App as KivyApp
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.utils import platform

from core.config import ConfigManager
from core.tunnel import TunnelManager, TunnelStatus
from core.proxy import SystemProxy
from ui.connect_panel import ConnectPanel
from ui.log_panel import LogPanel


class App(KivyApp):
    title = "JMVPN"

    def build(self):
        icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(__file__))), "icon.ico")
        if os.path.exists(icon_path):
            self.icon = icon_path

        if platform not in ('android', 'ios'):
            from kivy.core.window import Window
            Window.size = (420, 560)
            Window.minimum_width = 380
            Window.minimum_height = 400

        self._config = ConfigManager()
        self._proxy = SystemProxy()
        self._tunnel = TunnelManager(
            on_log=self._on_log,
            on_status_change=self._on_status_change,
        )

        root = BoxLayout(orientation='vertical', padding=8, spacing=8)

        self._connect_panel = ConnectPanel(
            config=self._config,
            tunnel_manager=self._tunnel,
            system_proxy=self._proxy,
            on_log=self._on_log,
            size_hint_y=None,
            height=280,
        )
        self._log_panel = LogPanel()

        root.add_widget(self._connect_panel)
        root.add_widget(self._log_panel)

        atexit.register(self._cleanup)
        return root

    def _on_log(self, message: str, level: str = "info"):
        Clock.schedule_once(lambda dt: self._log_panel.add_message(message, level), 0)

    def _on_status_change(self, status: TunnelStatus):
        def _update(dt):
            self._connect_panel.set_status(status)
            if status == TunnelStatus.CONNECTED:
                if self._connect_panel.get_mode() == "socks5":
                    http_port = self._tunnel.http_proxy_port
                    if http_port:
                        self._proxy.enable("127.0.0.1", http_port)
                        self._on_log(f"System proxy enabled → 127.0.0.1:{http_port}")
            elif status == TunnelStatus.DISCONNECTED:
                self._proxy.restore()
        Clock.schedule_once(_update, 0)

    def _cleanup(self):
        self._tunnel.disconnect()
        self._proxy.restore()

    def on_stop(self):
        self._cleanup()
