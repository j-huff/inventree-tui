from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Label,
)

class LabeledText(Widget):
    """Generates a greeting."""
    text = reactive("", recompose=True)
    label = reactive("", recompose=True)
    DEFAULT_CSS = """
    LabeledText {
        layout: horizontal;
        height: auto;
    }
    """

    def __init__(self, label, placeholder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label = label
        self.text = placeholder
    def compose(self) -> ComposeResult:
        yield Label(f"{self.label}: {self.text}")
