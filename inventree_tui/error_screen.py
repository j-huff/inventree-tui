from textual.screen import Screen
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.widgets import Button, Static
from textual.containers import Container
from textual.events import Event

class ErrorDialogScreen(Screen):
    title = reactive("")
    exception_message = reactive("")

    def compose(self) -> ComposeResult:
        with Container(id="error-dialog") as container:
            container.border_title = self.title
            yield Static(self.exception_message)
            yield Button("OK", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

class IgnorableErrorEvent(Event):
    def __init__(self, sender, title, message):
        super().__init__()
        self.sender = sender
        self.title = title
        self.message = message

