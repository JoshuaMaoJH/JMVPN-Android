from datetime import datetime
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.metrics import dp


class LogPanel(BoxLayout):
    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        super().__init__(**kwargs)
        self._expanded = False

        self._toggle_btn = Button(
            text="> Log",
            size_hint_y=None,
            height=dp(36),
            background_color=(0.3, 0.3, 0.3, 1),
            halign='left',
        )
        self._toggle_btn.bind(on_release=lambda *_: self._toggle())
        self.add_widget(self._toggle_btn)

        self._textbox = TextInput(
            readonly=True,
            multiline=True,
            font_size=dp(13),
            background_color=(0.12, 0.12, 0.12, 1),
            foreground_color=(0.9, 0.9, 0.9, 1),
        )

    def _toggle(self):
        if self._expanded:
            self.remove_widget(self._textbox)
            self._toggle_btn.text = "> Log"
        else:
            self.add_widget(self._textbox)
            self._toggle_btn.text = "v Log"
        self._expanded = not self._expanded

    def add_message(self, message: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        prefixes = {"info": "", "error": "[ERROR] ", "warn": "[WARN] "}
        prefix = prefixes.get(level, "")
        line = f"{ts} {prefix}{message}\n"
        self._textbox.text += line
        # Scroll to end
        self._textbox.cursor = (0, len(self._textbox.text))

    def clear(self) -> None:
        self._textbox.text = ""
