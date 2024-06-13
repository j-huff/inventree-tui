from typing import cast, List
from inventree.stock import StockItem, StockLocation

from textual import work
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import (
    Button,
    Static,
)

from inventree_tui.api import (
    CachedStockItemRow,
    CachedStockItem,
    transfer_items,
    InventreeScanner,
)
from inventree_tui.components import LabeledText, ButtonBar
from inventree_tui.error_screen import IgnorableErrorEvent
from inventree_tui.status import StatusChanged
from inventree_tui.model_data_table import ModelDataTable

class TransferItemsTab(Container):
    destination : StockLocation | None = reactive(None)

    def compose(self) -> ComposeResult:
        yield InventreeScanner(
            id="transfer_destination_scanner",
            whitelist=[StockLocation],
            placeholder="Scan Location Barcode",
            input_id="transfer_destination_input",
            autocomplete=True
        )
        yield LabeledText("Destination", "None", id="destination")
        yield InventreeScanner(
            id="transfer_items_scanner",
            whitelist=[StockItem],
            placeholder="Scan Items",
            input_id="transfer_item_input",
            autocomplete=False
        )
        with Horizontal():
            yield ModelDataTable(
                model_class=CachedStockItemRow,
                sort_column_key="part_name",
                id="transfer-items-table",
                zebra_stripes=True,
            )
        with ButtonBar (classes="button-bar"):
            yield Button("Done", id="transfer_done_button", variant="primary")
            yield Static(" ")
            yield Button("Cancel", id="cancel_button", variant="default")

    def watch_destination(self, destination):
        if destination is None:
            self.query_one("#destination").text = "None"
        else:
            dest = self.query_one("#destination")
            dest.text = self.destination.name
            self.get_destination_full_path()

    @work(exclusive=True, thread=True)
    def get_destination_full_path(self):
        dest = self.query_one("#destination")
        cur = self.destination
        path = []
        while cur is not None:
            path = [cur.name] + path
            cur = cur.getParentLocation()

        fullpath = "/".join(path)
        dest.text = f"{self.destination.name} ({fullpath})"

    async def on_inventree_scanner_item_scanned(self, message: InventreeScanner.ItemScanned) -> None:
        if message.sender.id == "transfer_destination_scanner":
            self.destination = message.obj
            self.query_one("#transfer_item_input").focus()
        elif message.sender.id == "transfer_items_scanner":
            item = CachedStockItem(stock_item=message.obj)
            table = cast(ModelDataTable, self.query_one("#transfer-items-table"))
            await table.add_item(CachedStockItemRow(item))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "transfer_done_button":
            # Logic to transfer items to the location
            errors = []
            table = cast(ModelDataTable, self.query_one("#transfer-items-table"))
            if len(table.data) == 0:
                errors.append("No items have been scanned yet.")
                self.query_one("#transfer_item_input").focus()
            if self.destination is None:
                errors.append("Destination not set.")
                self.query_one("#transfer_destination_input").focus()
            if len(errors) > 0:
                self.post_message(IgnorableErrorEvent(self, "Submission Error", "\n".join(errors)))
                self.post_message(StatusChanged(self, f"Error: {' '.join(errors)}"))
                return

            destination = cast(StockLocation, self.destination)

            table_data = cast(List[CachedStockItemRow], table.data.values())
            items = [row.item for row in table_data]
            transfer_items(items, destination)

            s = "s" if len(items) > 1 else ""
            self.post_message(StatusChanged(self, f"Transferred {len(items)} stock item{s} to {destination.name}"))
            await table.clear_data()

        elif event.button.id == "cancel_button":
            table = cast(ModelDataTable, self.query_one("#transfer-items-table"))
            await table.clear_data()
