from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from core.config import ServerConfig, ForwardRule, ConfigManager
from utils.keyring_helper import set_credential, delete_credential


def _labeled_input(label_text, default="", password=False, input_filter=None, width=None):
    row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
    row.add_widget(Label(text=label_text, size_hint_x=None, width=dp(90), halign='left', valign='middle'))
    inp = TextInput(
        text=str(default), multiline=False, password=password,
        input_filter=input_filter, size_hint_x=1,
    )
    row.add_widget(inp)
    return row, inp


class ServerEditDialog(Popup):
    """Popup dialog for adding or editing a server profile."""

    def __init__(self, config: ConfigManager,
                 server: ServerConfig | None = None,
                 on_save=None, **kwargs):
        self._config = config
        self._server = server
        self._on_save = on_save
        self._forward_rows: list[dict] = []
        self._inputs: dict[str, TextInput] = {}

        content = self._build_form()
        super().__init__(
            title="Edit Server" if server else "Add Server",
            content=content,
            size_hint=(0.95, 0.9),
            auto_dismiss=False,
            **kwargs,
        )
        if server:
            self._populate(server)

    def _build_form(self) -> BoxLayout:
        root = BoxLayout(orientation='vertical', spacing=dp(4), padding=dp(4))

        scroll = ScrollView(size_hint=(1, 1))
        self._form = BoxLayout(orientation='vertical', spacing=dp(4), size_hint_y=None)
        self._form.bind(minimum_height=self._form.setter('height'))

        fields = [
            ("Name", "name", ""),
            ("Host", "host", ""),
            ("SSH Port", "port", "22"),
            ("Username", "username", ""),
            ("SOCKS5 Port", "socks5_port", "1080"),
        ]
        for label, key, default in fields:
            filt = 'int' if key in ('port', 'socks5_port') else None
            row, inp = _labeled_input(label, default, input_filter=filt)
            self._inputs[key] = inp
            self._form.add_widget(row)

        # Auth type row
        auth_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
        auth_row.add_widget(Label(text="Auth", size_hint_x=None, width=dp(90), halign='left', valign='middle'))
        self._auth_pass_btn = ToggleButton(text="Password", group='auth', state='down')
        self._auth_pass_btn.bind(on_release=lambda *_: self._on_auth_change("password"))
        auth_row.add_widget(self._auth_pass_btn)
        self._auth_key_btn = ToggleButton(text="Key File", group='auth')
        self._auth_key_btn.bind(on_release=lambda *_: self._on_auth_change("key"))
        auth_row.add_widget(self._auth_key_btn)
        self._form.add_widget(auth_row)

        # Password field
        self._pass_row, self._password_input = _labeled_input("Password", password=True)
        self._form.add_widget(self._pass_row)

        # Key path field
        self._key_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
        self._key_row.add_widget(Label(text="Key Path", size_hint_x=None, width=dp(90), halign='left', valign='middle'))
        self._key_path_input = TextInput(multiline=False, size_hint_x=1)
        self._key_row.add_widget(self._key_path_input)
        # Key path is entered manually (cross-platform; no native file dialog in Kivy on Android)

        # Passphrase row
        self._passphrase_row, self._passphrase_input = _labeled_input("Passphrase", password=True)

        # Auth type defaults to password - key rows hidden initially
        self._auth_type = "password"

        # Port forwards section
        self._form.add_widget(Label(
            text="Port Forwarding Rules", size_hint_y=None, height=dp(30),
            halign='left', valign='middle',
        ))
        self._fwd_container = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(2))
        self._fwd_container.bind(minimum_height=self._fwd_container.setter('height'))
        self._form.add_widget(self._fwd_container)

        add_rule_btn = Button(text="+ Add Rule", size_hint_y=None, height=dp(36), size_hint_x=None, width=dp(120))
        add_rule_btn.bind(on_release=lambda *_: self._add_forward_row())
        self._form.add_widget(add_rule_btn)

        scroll.add_widget(self._form)
        root.add_widget(scroll)

        # Save / Cancel buttons
        btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel_btn = Button(text="Cancel", background_color=(0.5, 0.5, 0.5, 1))
        cancel_btn.bind(on_release=lambda *_: self.dismiss())
        btn_row.add_widget(cancel_btn)
        save_btn = Button(text="Save")
        save_btn.bind(on_release=lambda *_: self._save())
        btn_row.add_widget(save_btn)
        root.add_widget(btn_row)

        return root

    def _on_auth_change(self, auth_type: str):
        self._auth_type = auth_type
        if auth_type == "password":
            # Show password row, hide key rows
            if self._pass_row.parent is None:
                idx = list(self._form.children).index(self._auth_pass_btn.parent) if self._auth_pass_btn.parent in self._form.children else 0
                self._form.add_widget(self._pass_row, index=idx)
            if self._key_row.parent is not None:
                self._form.remove_widget(self._key_row)
            if self._passphrase_row.parent is not None:
                self._form.remove_widget(self._passphrase_row)
        else:
            # Show key rows, hide password row
            if self._pass_row.parent is not None:
                self._form.remove_widget(self._pass_row)
            if self._key_row.parent is None:
                idx = list(self._form.children).index(self._auth_pass_btn.parent) if self._auth_pass_btn.parent in self._form.children else 0
                self._form.add_widget(self._key_row, index=idx)
                self._form.add_widget(self._passphrase_row, index=idx)

    def _add_forward_row(self, local="", remote_host="localhost", remote_port=""):
        row_frame = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(2))

        row_frame.add_widget(Label(text="L:", size_hint_x=None, width=dp(20)))
        lport_inp = TextInput(text=str(local), multiline=False, input_filter='int',
                              size_hint_x=None, width=dp(60))
        row_frame.add_widget(lport_inp)

        row_frame.add_widget(Label(text="->", size_hint_x=None, width=dp(24)))
        rhost_inp = TextInput(text=remote_host, multiline=False, size_hint_x=1)
        row_frame.add_widget(rhost_inp)

        row_frame.add_widget(Label(text=":", size_hint_x=None, width=dp(12)))
        rport_inp = TextInput(text=str(remote_port), multiline=False, input_filter='int',
                              size_hint_x=None, width=dp(60))
        row_frame.add_widget(rport_inp)

        row_data = {"frame": row_frame, "lport": lport_inp, "rhost": rhost_inp, "rport": rport_inp}
        self._forward_rows.append(row_data)

        remove_btn = Button(text="X", size_hint_x=None, width=dp(36))
        remove_btn.bind(on_release=lambda *_: self._remove_forward_row(row_data))
        row_frame.add_widget(remove_btn)

        self._fwd_container.add_widget(row_frame)

    def _remove_forward_row(self, row_data: dict):
        self._fwd_container.remove_widget(row_data["frame"])
        self._forward_rows.remove(row_data)

    def _populate(self, server: ServerConfig):
        self._inputs["name"].text = server.name
        self._inputs["host"].text = server.host
        self._inputs["port"].text = str(server.port)
        self._inputs["username"].text = server.username
        self._inputs["socks5_port"].text = str(server.socks5_port)

        if server.auth_type == "key":
            self._auth_key_btn.state = 'down'
            self._auth_pass_btn.state = 'normal'
            self._on_auth_change("key")
        self._key_path_input.text = server.key_path

        for rule in server.forwards:
            self._add_forward_row(rule.local_port, rule.remote_host, rule.remote_port)

    def _save(self):
        forwards = []
        for row in self._forward_rows:
            try:
                forwards.append(ForwardRule(
                    local_port=int(row["lport"].text),
                    remote_host=row["rhost"].text,
                    remote_port=int(row["rport"].text),
                ))
            except ValueError:
                continue

        auth_type = self._auth_type
        kwargs = dict(
            name=self._inputs["name"].text,
            host=self._inputs["host"].text,
            port=int(self._inputs["port"].text or "22"),
            username=self._inputs["username"].text,
            auth_type=auth_type,
            key_path=self._key_path_input.text,
            socks5_port=int(self._inputs["socks5_port"].text or "1080"),
            forwards=forwards,
        )

        if self._server:
            self._config.update(self._server.id, **kwargs)
            server_id = self._server.id
        else:
            s = ServerConfig(**kwargs)
            self._config.add(s)
            server_id = s.id

        # Store credential
        if auth_type == "password":
            secret = self._password_input.text
        else:
            secret = self._passphrase_input.text
        if secret:
            set_credential(server_id, secret)
        elif not self._server:
            delete_credential(server_id)

        if self._on_save:
            self._on_save()
        self.dismiss()
