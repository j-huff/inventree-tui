from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Label,
)

from textual.containers import Horizontal
from textual.binding import Binding

class ButtonBar(Horizontal):
    BINDINGS = [
        Binding(key="left", action="cursor_left", description="Focus previous button"),
        Binding(key="right", action="cursor_right", description="Focus next button"),
        Binding(key="up", action="cursor_up", description="Focus previous widget"),
        Binding(key="down", action="cursor_down", description="Focus next widget"),
    ]

    COMPONENT_CLASSES = {
        "button",
    }

    DEFAULT_CSS = """
        ButtonBar {
            align: center middle;
            height: auto;
        }
        Button {
            width: 1fr;
            margin: 1;
        }
        Static {
          width: 1;
        }
    """

    def action_cursor_left(self):
        if len(self.children) == 0:
            return

        first = self.children[0]
        #If this is the first button, do nothing
        if first == self.screen.focused:
            return
        self.screen.focus_previous()

    def action_cursor_right(self):
        if len(self.children) == 0:
            return

        last = self.children[-1]
        #If this is the last button, do nothing
        if last == self.screen.focused:
            return

        self.screen.focus_next()

    def action_cursor_down(self):
        if len(self.children) == 0:
            self.screen.focus_next()
            return

        last = self.children[-1]
        self.screen.set_focus(last)
        self.screen.focus_next()

    def action_cursor_up(self):
        if len(self.children) == 0:
            self.screen.focus_previous()
            return
        first = self.children[0]
        self.screen.set_focus(first)
        self.screen.focus_previous()

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
