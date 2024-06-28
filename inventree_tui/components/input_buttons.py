from textual.containers import Container

from textual.widgets import (
    Checkbox,
    Input,
)

class input_buttons(Container):
    def __init__(
        self,
        input: str | Checkbox,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
    ) -> None:
