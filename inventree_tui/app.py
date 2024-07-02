from typing import cast
import logging
import importlib

import httpx

from textual import work
from textual.app import App, ComposeResult, Binding
from textual.containers import Vertical
from textual.logging import TextualHandler
from textual.reactive import reactive
from textual.widgets import (
    Header,
    Input,
    Label,
    TabbedContent,
    TabPane,
)

from .error_screen import ErrorDialogScreen, IgnorableErrorEvent
from .status import StatusChanged
from .tabs import (
    TransferItemsTab,
    CheckInItemsTab,
    PartSearchTab,
    StockOpsTab
)
from inventree_tui.sound import Sound, play_sound
from inventree_tui.settings import settings

handlers = [TextualHandler()]
if settings.log_filename is not None:
    file_handler = logging.FileHandler(settings.log_filename)
    file_handler.setLevel(settings.log_level)
    handlers.append(file_handler)

logging.basicConfig(
    level=settings.log_level,
    handlers=handlers,
)

class InventreeApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = settings.app_name
    BINDINGS = [
        Binding("ctrl+t", "show_tab('transfer-items-tab')", "Transfer", priority=True),
        Binding("ctrl+s", "show_tab('stock-ops-tab')", "Stock Ops", priority=True),
        Binding("ctrl+p", "show_tab('part-search-tab')", "Part Search", priority=True),
        Binding("ctrl+i", "show_tab('checkin-items-tab')", "Check-In", priority=True),
    ]

    status_message = reactive("")

    def __init__(self):
        self.app_status_text = None
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Transfer Items",id="transfer-items-tab"):
                yield TransferItemsTab()
            with TabPane("Check-In Items", id="checkin-items-tab"):
                yield CheckInItemsTab()
            with TabPane("Stock Ops", id="stock-ops-tab"):
                yield StockOpsTab()
            with TabPane("Part Search", id="part-search-tab"):
                yield PartSearchTab()
        with Vertical(id="footer"):
            self.app_status_text = Label(self.status_message,id="app_status_text")
            yield self.app_status_text

    async def on_ignorable_error_event(self, event: IgnorableErrorEvent):
        dialog = ErrorDialogScreen()
        dialog.title = event.title
        dialog.exception_message = event.message
        self.play_sound("failure")
        await self.push_screen(dialog)


    @work(exclusive=True)
    async def check_for_updates(self):
        # Get the currently installed version of your package
        package_name = __package__ or "inventree_tui"
        current_version = importlib.metadata.version(package_name)

        # Make a request to the PyPI API to get the latest version information
        package_url = f"https://pypi.org/pypi/{package_name}/json"
        async with httpx.AsyncClient() as client:
            response = await client.get(package_url)

        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            latest_version = data["info"]["version"]

            # Compare the versions
            if latest_version > current_version:
                s = f"""\
A new version of {package_name} is available: {latest_version}\n\
You can upgrade to it by running: `pip install --upgrade {package_name}`"""
                self.post_message(IgnorableErrorEvent(self, "New Version Available", s))
                self.post_message(StatusChanged(self,f"""\
New Version Available ({latest_version}). Please Upgrade."""))
            else:
                self.post_message(StatusChanged(self,f"""\
InvenTree TUI up to date ({current_version})"""))
        else:
            self.post_message(StatusChanged(self, "Failed to check for update"))

    def on_status_changed(self, message: StatusChanged):
        self.status_message = message.value

    def watch_status_message(self, status_message: str) -> None:
        if self.app_status_text is not None:
            self.app_status_text.update(status_message)

    def initialization(self):
        if settings.check_for_updates:
            self.check_for_updates()

    def on_mount(self):
        _input = cast(Input, self.query_one("#transfer_destination_input"))
        _input.focus()
        self.call_after_refresh(self.initialization)


    @work(exclusive=False, thread=True)
    def play_sound(self, sound_name: str):
        play_sound(sound_name)

    @work(exclusive=False, thread=True)
    def play_sound_fn(self, fn):
        fn()

    def on_sound(self, event: Sound):
        if not settings.sound_enabled:
            return
        if event.name is not None:
            self.play_sound(event.name)
        if event.fn is not None:
            self.play_sound_fn(event.fn)

    def action_show_tab(self, tab: str) -> None:
        """Switch to a new tab."""
        self.get_child_by_type(TabbedContent).active = tab
        # Select the first input field in the tab
        self.query(f'#{tab} Input').first().focus()
