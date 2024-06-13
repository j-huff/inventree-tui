from typing import cast

from inventree.stock import StockItem

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Static
)

from inventree_tui.api import (
    CachedStockItem,
    CachedStockItemCheckInRow,
    transfer_items,
    InventreeScanner,
)

from inventree_tui.error_screen import IgnorableErrorEvent
from inventree_tui.status import StatusChanged
from inventree_tui.model_data_table import ModelDataTable
from inventree_tui.components import ButtonBar

class CheckInScreen(ModalScreen):
    dialog_title = reactive("Row Edit", recompose=True)
    error_message = reactive("", repaint=True)

    def __init__(self, item):
        self.item = item
        super().__init__()
        self.errmsg = Static("", id="checkin-errormsg", classes="error-msg")
        self.errmsg.styles.display = "none"
        self.dialog_title = f"Check-In: {self.item.title_name()}"

    def compose(self) -> ComposeResult:
        with Container(id="checkin-dialog") as container:
            container.border_title = self.dialog_title
            yield Static(f"Current Location: {self.item.stock_location_name}")
            yield Static(f"Default Location: {self.item.default_location.name}")
            yield Static("Confirm Check-In?", classes="dialog-question")
            yield self.errmsg
            with ButtonBar (classes="button-bar"):
                yield Button("Confirm", variant="success", id="checkin-confirm")
                yield Static(" ")
                yield Button("Cancel", variant="error", id="checkin-cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "checkin-cancel":
            self.dismiss(None)
            return
        if event.button.id == "checkin-confirm":
            self.dismiss((self.item, self.item.default_location))
            return

    def watch_error_message(self, msg: str) -> None:
        self.errmsg.update(msg)
        if len(msg) == 0:
            self.errmsg.styles.display = "none"
        else:
            self.errmsg.styles.display = "block"

class CheckInItemsTab(Container):
    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        yield InventreeScanner(
            id="checkin_items_scanner",
            whitelist=[StockItem],
            placeholder="Scan Items",
            input_id="checkin_item_input",
            autocomplete=False
        )
        yield Static("History Table",id="checkin_table_title", classes="table-title")
        with Horizontal():
            yield ModelDataTable(
                model_class=CachedStockItemCheckInRow,
                sort_column_key="timestamp",
                id="checkin_items_table",
                zebra_stripes=True,
            )
        with Horizontal (classes="button-bar"):
            yield Button("Clear History", id="checkin_clear_button", variant="primary")

    def on_inventree_scanner_item_scanned(self, message: InventreeScanner.ItemScanned) -> None:
        if message.sender.id == "checkin_items_scanner":
            item = CachedStockItem(stock_item=message.obj)
            if item.default_location is None:
                errmsg = f"Cannot check-in Stock #{item.pk}: No default location"
                self.post_message(StatusChanged(self, errmsg))
                event = IgnorableErrorEvent(self, "Check-In Error", errmsg)
                self.post_message(event)
                return

            self.open_check_in_dialog(item)

    def open_check_in_dialog(self, item):
        dialog = CheckInScreen(item)

        async def checkin_dialog_callback(args) -> None:
            if args is None:
                return
            (item, destination) = args

            try:
                if item.stock_location is not None and item.stock_location.pk == destination.pk:
                    self.post_message(StatusChanged(self, f"Stock #{item.pk} was already at {destination.name}"))
                else:
                    transfer_items([item], destination)
            except Exception as e:
                event = IgnorableErrorEvent(self, "Transfer Failed", str(e))
                self.post_message(event)
                return

            table = cast(ModelDataTable, self.query_one("#checkin_items_table"))
            await table.add_item(CachedStockItemCheckInRow(item))

        self.app.push_screen(dialog, checkin_dialog_callback)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        table = cast(ModelDataTable, self.query_one("#checkin_items_table"))
        if event.button.id == "checkin_clear_button":
            self.post_message(StatusChanged(self, "Cleared History"))
            await table.clear_data()
