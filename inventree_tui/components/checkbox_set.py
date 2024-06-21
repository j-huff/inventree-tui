from __future__ import annotations

from typing import ClassVar, Optional

import rich.repr
from rich.console import RenderableType

from textual import _widget_navigation
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.events import Click, Mount
from textual.message import Message
from textual.reactive import var
from textual.widgets import Checkbox


class CheckboxSet(Container, can_focus=True, can_focus_children=False):
    """Widget for grouping a collection of checkboxes int a set.
    """

    DEFAULT_CSS = """
    CheckboxSet {
        border: tall transparent;
        background: $boost;
        padding: 0 1 0 0;
        height: auto;
        width: auto;
    }

    CheckboxSet:focus {
        border: tall $accent;
    }

    /* The following rules/styles mimic similar ToggleButton:focus rules in
     * ToggleButton. If those styles ever get updated, these should be too.
     */

    CheckboxSet > * {
        background: transparent;
        border: none;
        padding: 0 1;
    }

    CheckboxSet:focus > Checkbox.-selected > .toggle--label {
        text-style: underline;
    }

    CheckboxSet:focus ToggleButton.-selected > .toggle--button {
        background: $foreground 25%;
    }

    CheckboxSet:focus > Checkbox.-on.-selected > .toggle--button {
        background: $foreground 25%;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("down,right", "next_button", "", show=False),
        Binding("enter,space", "toggle_button", "Toggle", show=False),
        Binding("up,left", "previous_button", "", show=False),
    ]
    """
    | Key(s) | Description |
    | :- | :- |
    | enter, space | Toggle the currently-selected button. |
    | left, up | Select the previous checkbox in the set. |
    | right, down | Select the next checkbox in the set. |
    """

    _selected: var[int | None] = var[Optional[int]](None)
    """The index of the currently-selected checkbox."""

    def __init__(
        self,
        *buttons: str | Checkbox,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
    ) -> None:
        """Initialise the checkbox set.

        Args:
            buttons: The labels or [`Checkbox`][textual.widgets.Checkbox]s to group together.
            name: The name of the checkbox set.
            id: The ID of the checkbox set in the DOM.
            classes: The CSS classes of the checkbox set.
            disabled: Whether the checkbox set is disabled or not.
            tooltip: Optional tooltip.

        Note:
            When a `str` label is provided, a
            [Checkbox][textual.widgets.Checkbox] will be created from
            it.
        """

        super().__init__(
            *[
                (button if isinstance(button, Checkbox) else Checkbox(button))
                for button in buttons
            ],
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        if tooltip is not None:
            self.tooltip = tooltip

    def _on_mount(self, _: Mount) -> None:
        """Perform some processing once mounted in the DOM."""

        # If there are checkbox buttons, select the first available one.
        self.action_next_button()

        # Get all the buttons within us; we'll be doing a couple of things
        # with that list.
        buttons = list(self.query(Checkbox))

        # Checkboxes can have focus, by default. But we're going to take
        # that over and handle movement between them. So here we tell them
        # all they can't focus.
        for button in buttons:
            button.can_focus = False

        # It's possible for the user to pass in a collection of checkbox
        # buttons, with more than one set to on; they shouldn't, but we
        # can't stop them. So here we check for that and, for want of a
        # better approach, we keep the first one on and turn all the others
        # off.
        switched_on = [button for button in buttons if button.value]
        with self.prevent(Checkbox.Changed):
            for button in switched_on[1:]:
                button.value = False

    def watch__selected(self) -> None:
        self.query(Checkbox).remove_class("-selected")
        if self._selected is not None:
            self._nodes[self._selected].add_class("-selected")


    async def _on_click(self, _: Click) -> None:
        """Handle a click on or within the checkbox set.

        This handler ensures that focus moves to the clicked checkbox set, even
        if there's a click on one of the checkboxes it contains.
        """
        self.focus()

    def action_previous_button(self) -> None:
        """Navigate to the previous button in the set.

        Note that this will wrap around to the end if at the start.
        """
        self._selected = _widget_navigation.find_next_enabled(
            self.children,
            anchor=self._selected,
            direction=-1,
        )

    def action_next_button(self) -> None:
        """Navigate to the next button in the set.

        Note that this will wrap around to the start if at the end.
        """
        self._selected = _widget_navigation.find_next_enabled(
            self.children,
            anchor=self._selected,
            direction=1,
        )

    def action_toggle_button(self) -> None:
        """Toggle the state of the currently-selected button."""
        if self._selected is not None:
            button = self._nodes[self._selected]
            assert isinstance(button, Checkbox)
            button.toggle()
