import logging
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Button, Static, TabPane, Tab, TabbedContent, Label, DataTable
from textual.widgets.data_table import RowKey
from textual.widget import Widget
from textual.containers import Container, Grid, Horizontal
from textual.reactive import reactive
from inventree_tui.api import ApiException, scanBarcode, CachedStockItemRow, RowBaseModel, transfer_items
from textual.screen import Screen
import asyncio

from textual.events import Event, Key
from textual.logging import TextualHandler

from textual.message import Message
from typing import List, Type, Any, Set


logging.basicConfig(
    level="NOTSET",
    handlers=[TextualHandler()],
)

class UpdateTableMessage(Message):
    def __init__(self, data: List[RowBaseModel]):
        super().__init__()
        self.data = data

class ModelDataTable(DataTable):
    data: Set[RowBaseModel] = reactive(set([]), recompose=True)
    sort_column_key: str = None

    def __init__(self, model_class: Type[RowBaseModel], sort_column_key: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_class = model_class
        self.sort_column_key = sort_column_key
        if self.sort_column_key is not None and self.sort_column_key not in model_class.get_field_names(by_alias=True):
            raise Exception(f"Not a valid sort column, options are {model_class.get_field_names(by_alias=True)}")

    async def on_mount(self) -> None:
        columns = self.model_class.get_field_names(by_alias=True)
        self.add_columns(*columns)
        self.cursor_type = "row"
        self.zerbra_stipes = True
        await self.reload()

#    async def watch_props_and_update(self, props: List[Any]) -> None:
        #        await self.update(self.model_class.parse_obj(props))

#    async def on_message(self, message: Message) -> None:
#        if isinstance(message, UpdateTableMessage):
#            await self.watch_props_and_update(message.data)

    async def reload(self) -> None:
        await self.update()

    async def add_item(self, item: RowBaseModel):
        if item in self.data:
            return
        self.data.add(item)
        await self.update()

    def clear_data(self):
        self.data = set([])

    async def watch_data(self, data: Set[RowBaseModel]):
        logging.debug(f"DATA WATCH TRIGGERED {data}")
        await self.update(data)

    async def update(self, data: Set[RowBaseModel] = None) -> None:
        if data is None:
            data = self.data
        #self.clear()
        columns = self.model_class.get_field_names()
        for obj in data:
            if RowKey(value=obj) not in self.rows:
                values = [getattr(obj, col) for col in columns]
                self.add_row(*values, key=obj)

        keys = list(self.rows.keys())
        for row_key in keys:
            if row_key.value not in data:
                self.remove_row(row_key)

    async def on_data_table_row_selected(self, message: DataTable.RowSelected):
        # control, cursor_row, data_table, row_key
        logging.debug(f"ROW SELECTED {message}")

    async def on_key(self, event: Key) -> None:
        logging.debug(f"{event}")
        if event.name == "delete" and len(self.data) > 0:
            logging.debug(f"DELETE {self.cursor_row}")
            row = self.ordered_rows[self.cursor_row]
            row_key = row.key
            self.data.remove(row_key.value)
            self.move_cursor(row=self.cursor_row-1)
            await self.update()


class IgnorableErrorEvent(Event):
    def __init__(self, sender, title, message):
        super().__init__()
        self.sender = sender
        self.title = title
        self.message = message

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

class TransferItemsTab(Container):
    destination = reactive(None)

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Scan Location Barcode", id="destination_input")
        yield LabeledText("Destination", "None", id="destination")
        yield Input(placeholder="Scan Items", id="item_input")
        with Horizontal():
            yield ModelDataTable(
                model_class=CachedStockItemRow,
                sort_column_key="part_name",
                id="transfer-items-table",
                zebra_stripes=True,
            )
        with Horizontal (id="button-bar"):
            yield Button("Done", id="done_button", variant="success")
            yield Button("Cancel", id="cancel_button", variant="error")
        yield Static("Status Ok",id="status-text")

    async def on_mount(self):
        table = self.query_one("#transfer-items-table")
        #TODO: remove this after testing
        await self.handle_item_input('{"stockitem":338}')
        #await self.handle_item_input('{"stockitem":338}')
        #await self.handle_item_input('{"stockitem":339}')
        #await self.handle_item_input('{"stockitem":337}')
        #table.add_columns("Stock", "Part", "Quantity", "Location")

    def watch_destination(self, destination):
        logging.debug(f"WATCH DESTINATION {destination}")
        if destination is None:
            self.query_one("#destination").text = "None"
        else:
            self.query_one("#destination").text = self.destination.name


    async def handle_item_input(self, value: str):
        try:
            item = scanBarcode(value, ["stockitem"])
            table = self.query_one("#transfer-items-table")

            await table.add_item(CachedStockItemRow(item))
        except ApiException as e:
            event = IgnorableErrorEvent(self, "Scan Error", str(e))
            self.post_message(event)

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        if message.input.id == "destination_input":
            message.input.add_class("readonly")
            try:
                item = scanBarcode(message.input.value, ["stocklocation"])
                self.destination = item
                self.query_one("#item_input").focus()
            except ApiException as e:
                #message.input.value = str(e)
                event = IgnorableErrorEvent(self, "Scan Error", str(e))
                self.post_message(event)
            message.input.remove_class("readonly")
            message.input.clear()

        if message.input.id == "item_input":
            message.input.add_class("readonly")
            await self.handle_item_input(message.input.value)
            message.input.remove_class("readonly")
            message.input.clear()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        status_text = self.query_one("#status-text")
        if event.button.id == "done_button":
            # Logic to transfer items to the location
            errors = []
            table = self.query_one("#transfer-items-table")
            if len(table.data) == 0:
                errors.append("No items have been scanned yet.")
                self.query_one("#item_input").focus()
            if self.destination is None:
                errors.append("Destination not set.")
                self.query_one("#destination_input").focus()
            if len(errors) > 0:
                event = IgnorableErrorEvent(self, "Submission Error", "\n".join(errors))
                self.post_message(event)
                status_text.update(f"Error: {' '.join(errors)}")
                return

            items = [row.item for row in table.data]
            transfer_items(items, self.destination)

            status_text = self.query_one("#status-text")
            s = "s" if len(items) > 1 else ""
            status_text.update(f"Transferred {len(items)} stock item{s} to {self.destination.name}")
            table.clear_data()

        elif event.button.id == "cancel_button":
            table = self.query_one("#transfer-items-table")
            table.clear_data()

class CheckInItemsTab(Container):
    def compose(self) -> ComposeResult:
        yield Static("Check-In Items Tab")

class InventreeApp(App):
    CSS_PATH = "styles.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Transfer Items",id="transfer-items-tab"):
                yield TransferItemsTab()
            with TabPane("Check-In Items", id="checkin-items-tab"):
                yield CheckInItemsTab()

        yield Footer()

    async def on_ignorable_error_event(self, event: IgnorableErrorEvent):
        dialog = ErrorDialogScreen()
        dialog.title = event.title
        dialog.exception_message = event.message
        await self.push_screen(dialog)

    def on_mount(self):
        self.query_one("#destination_input").focus()

 #       async def handle_button_pressed(self, message: Button.Pressed) -> None:
#            if message.button.id == "exception_ok":
#                await self.pop_screen()

#app = InventreeApp()
#if __name__ == "__main__":
#    app = InventreeApp()
#    app.run()
