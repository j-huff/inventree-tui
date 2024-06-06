import logging
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Button, Static, TabPane, Tab, TabbedContent, Label, DataTable
from textual.widgets.data_table import RowKey
from textual.widget import Widget
from textual.containers import Container, Grid, Horizontal
from textual.reactive import reactive
from inventree_tui.api import ApiException, scanBarcode, CachedStockItemRow, RowBaseModel, transfer_items, CachedStockItemCheckInRow
from textual.screen import Screen, ModalScreen
import asyncio

from textual.events import Event, Key
from textual.logging import TextualHandler

from textual.message import Message
from typing import List, Type, Any, Set
from pydantic import ValidationError

from .part_search import PartSearchTab
from .error_screen import IgnorableErrorEvent, ErrorDialogScreen


logging.basicConfig(
    level="NOTSET",
    handlers=[TextualHandler()],
)

class UpdateTableMessage(Message):
    def __init__(self, data: List[RowBaseModel]):
        super().__init__()
        self.data = data

class ModelDataTable(DataTable):

    # these can't be class attributes...
    #data: Set[RowBaseModel] = reactive(set([]), recompose=True)
    #sort_column_key: str = None

    def __init__(self, model_class: Type[RowBaseModel], sort_column_key: str = None, *args, **kwargs):
        self.data = set([]) #reactive(set([]), recompose=True)
        self.sort_column_key = None

        super().__init__(*args, **kwargs)
        self.model_class = model_class
        logging.info(f"CREATED MODEL DATA TABLE WITH CLASS: {model_class}")
        self.sort_column_key = sort_column_key
        if self.sort_column_key is not None and self.sort_column_key not in model_class.get_field_names(by_alias=True):
            raise Exception(f"Not a valid sort column, options are {model_class.get_field_names(by_alias=True)}")

    async def on_mount(self) -> None:
        columns = self.model_class.get_field_names(by_alias=True)
        for col in columns:
            dn = self.model_class.field_display_name(col)
            self.add_column(dn, key=col)

        #self.add_column("Del", key="delete_button")
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
        logging.info(f"ADDING ITEM: {item} to {self.data}")
        if item in self.data:
            return
        self.data.add(item)
        await self.update()

    async def clear_data(self):
        self.data = set([])
        await self.update()

    #async def watch_data(self, data: Set[RowBaseModel]):
    #    logging.debug(f"DATA WATCH TRIGGERED {data}")
    #    await self.update(data)

    def add_row(self, *cells, height=1, key=None, label=None):
        #cells = (*cells, "X") 
        super().add_row(*cells, height=height, key=key, label=label)

    async def update(self, data: Set[RowBaseModel] = None) -> None:
        if data is None:
            data = self.data
        #self.clear()
        columns = self.model_class.get_field_names()
        needs_sorted = False
        for obj in data:
            if RowKey(value=obj) not in self.rows:
                values = [getattr(obj, col) for col in columns]
                self.add_row(*values, key=obj)
                needs_sorted = True

        keys = list(self.rows.keys())
        for row_key in keys:
            if row_key.value not in data:
                self.remove_row(row_key)

        for row_key in self.rows.keys():
            cells = self.get_row(row_key)
            for col_key in self.columns.keys():
                if col_key != "delete_button":
                    current_value = self.get_cell(row_key, col_key)
                    new_value = getattr(row_key.value, col_key.value)
                    if current_value != new_value:
                        needs_sorted = True
                        logging.info(f"VALUE CHANGED {current_value} -> {new_value}")
                        self.update_cell(row_key, col_key, value=new_value)
                        logging.info(f"UPDATING CELL: {row_key.value} {col_key.value}")
        if needs_sorted:
            self.sort(self.sort_column_key, reverse=True)

    async def on_data_table_row_selected(self, message: DataTable.RowSelected):
        #TODO: Add stock splitting to allow the row editor
        return
        # control, cursor_row, data_table, row_key
        event = RowEditEvent(message.data_table, message.row_key)
        self.post_message(event)

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


class CheckInBeginEvent(Event):
    def __init__(self, item):
        super().__init__()
        self.item = item

class RowEditEvent(Event):
    def __init__(self, table, row_key):
        super().__init__()
        self.table = table
        self.row_key = row_key

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

class CheckInScreen(ModalScreen):
    dialog_title = reactive("Row Edit", recompose=True)
    error_message = reactive("")
    def __init__(self, item):
        super().__init__()
        self.item = item
        self.dialog_title = f"Check-In: {self.item.title_name()}"

    def compose(self) -> ComposeResult:
        with Container(id="checkin-dialog") as container:
            container.border_title = self.dialog_title
            yield Static(f"Current Location: {self.item.stock_location.name}")
            yield Static(f"Default Location: {self.item.default_location.name}")
            yield Static(f"Confirm Check-In?", classes="dialog-question")
            static = Static(self.error_message, id="check-errormsg", classes="error-msg")
            static.styles.display = "none"
            yield static
            with Horizontal (classes="button-bar"):
                yield Button("Confirm", variant="success", id="checkin-confirm")
                yield Static(" ")
                yield Button("Cancel", variant="error", id="checkin-cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "checkin-cancel":
            self.dismiss(None)
            return
        elif event.button.id == "checkin-confirm":
            self.dismiss((self.item, self.item.default_location))
            return

    def watch_error_message(self, msg: str) -> None:
        try:
            errmsg = self.query_one("#checkin-errormsg")
            errmsg.update(msg)
            if len(msg) == 0:
                errmsg.styles.display = "none"
            else:
                errmsg.styles.display = "block"
        except:
            pass

#class RowEditScreen(ModalScreen[RowBaseModel]):
class RowEditScreen(Screen):
    dialog_title = reactive("Row Edit", recompose=True)
    row = reactive(None, recompose=True)
    start_values = reactive({}, recompose=True)
    error_message = reactive("")

    def __init__(self, table, row_key):
        super().__init__()
        self.table = table
        self.row = row_key.value
        self.dialog_title = f"Row Edit: {self.row.title_name()}"

        editable = self.row.get_editable_fields()
        logging.info(f"EDITABLE ROWS: {editable}")
        values = {}
        for name in editable:
            values[name] = getattr(self.row, name)
        self.start_values = values

    def watch_error_message(self, msg: str) -> None:
        try:
            errmsg = self.query_one("#errormsg")
            errmsg.update(msg)
            if len(msg) == 0:
                self.query_one("#errormsg").styles.display = "none"
            else:
                self.query_one("#errormsg").styles.display = "block"
        except:
            pass

    def compose(self) -> ComposeResult:
        with Container(id="row-edit-dialog") as container:
            container.border_title = self.dialog_title
            logging.info(f"TITLE {self.dialog_title}")
            for key, val in self.start_values.items():
                with Horizontal(classes="input_row"):
                    yield Label(f"{self.table.model_class.field_display_name(key)}:")
                    if isinstance(val, str):
                        yield Input(f"{val}", name=key, type="text")
                    elif isinstance(val, int):
                        yield Input(f"{val}", name=key, type="integer")
                    elif isinstance(val, float):
                        yield Input(f"{val}", name=key, type="number")

            static = Static(self.error_message, id="errormsg", classes="error-msg")
            static.styles.display = "none"
            yield static
            with Horizontal (classes="button-bar"):
                yield Button("OK", variant="primary", id="ok")
                yield Static(" ")
                yield Button("Cancel", variant="error", id="cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        elif event.button.id != "ok":
            return
        inputs = self.query(Input)
        values = {}
        for i in inputs:
            values[i.name] = i.value 

        values = self.row.dict() | values
        try:
            other = self.row.__class__(**values)
            self.row.update(other, validate=True)
        except ValidationError as e:
            msgs = [e2['msg'] for e2 in e.errors()]
            self.error_message = str(". ".join(msgs))
            return
        except ValueError as e:
            self.error_message = str(e)
            return

        await self.table.update()
        self.dismiss(None)


class TransferItemsTab(Container):
    destination = reactive(None)

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Scan Location Barcode", id="transfer_destination_input")
        yield LabeledText("Destination", "None", id="destination")
        yield Input(placeholder="Scan Items", id="transfer_item_input")
        with Horizontal():
            yield ModelDataTable(
                model_class=CachedStockItemRow,
                sort_column_key="part_name",
                id="transfer-items-table",
                zebra_stripes=True,
            )
        with Horizontal (classes="button-bar"):
            yield Button("Done", id="transfer_done_button", variant="primary")
            yield Static(" ")
            yield Button("Cancel", id="cancel_button", variant="default")
        yield Static("Status Ok",id="transfer_status_text", classes="status_text")

    async def on_mount(self):

        table = self.query_one("#transfer-items-table")
        #TODO: remove this after testing
        #await self.handle_item_input('{"stockitem":338}')
        #await self.handle_item_input('{"stockitem":338}')
        #await self.handle_item_input('{"stockitem":339}')
        #await self.handle_item_input('{"stockitem":337}')

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
        if message.input.id == "transfer_destination_input":
            message.input.add_class("readonly")
            try:
                item = scanBarcode(message.input.value, ["stocklocation"])
                self.destination = item
                self.query_one("#transfer_item_input").focus()
            except ApiException as e:
                #message.input.value = str(e)
                event = IgnorableErrorEvent(self, "Scan Error", str(e))
                self.post_message(event)
            message.input.remove_class("readonly")
            message.input.clear()

        if message.input.id == "transfer_item_input":
            message.input.add_class("readonly")
            await self.handle_item_input(message.input.value)
            message.input.remove_class("readonly")
            message.input.clear()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        status_text = self.query_one("#transfer_status_text")
        if event.button.id == "transfer_done_button":
            # Logic to transfer items to the location
            errors = []
            table = self.query_one("#transfer-items-table")
            if len(table.data) == 0:
                errors.append("No items have been scanned yet.")
                self.query_one("#transfer_item_input").focus()
            if self.destination is None:
                errors.append("Destination not set.")
                self.query_one("#transfer_destination_input").focus()
            if len(errors) > 0:
                event = IgnorableErrorEvent(self, "Submission Error", "\n".join(errors))
                self.post_message(event)
                status_text.update(f"Error: {' '.join(errors)}")
                return

            items = [row.item for row in table.data]
            transfer_items(items, self.destination)

            status_text = self.query_one("#transfer_status_text")
            s = "s" if len(items) > 1 else ""
            status_text.update(f"Transferred {len(items)} stock item{s} to {self.destination.name}")
            await table.clear_data()

        elif event.button.id == "cancel_button":
            table = self.query_one("#transfer-items-table")
            await table.clear_data()

#class CheckInItemsTab(Container):
#    def compose(self) -> ComposeResult:
#        yield Static("Check-In Items Tab")

class CheckInItemsTab(Container):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Scan Items", id="checkin_item_input")
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
        yield Static("Status Ok",id="checkin_status_text", classes="status_text")

    async def on_mount(self):

        table = self.query_one("#checkin_items_table")
        #TODO: remove this after testing
        #await self.handle_item_input('{"stockitem":338}')
        #await self.handle_item_input('{"stockitem":338}')
        #await self.handle_item_input('{"stockitem":339}')
        #await self.handle_item_input('{"stockitem":9}')

    async def handle_item_input(self, value: str):
        status_text = self.query_one("#checkin_status_text")
        try:
            item = scanBarcode(value, ["stockitem"])
            #table = self.query_one("#checkin_items_table")
            if item.default_location is None:
                errmsg = f"Cannot check-in Stock #{item._stock_item.pk}: No default location"
                status_text.update(errmsg)
                event = IgnorableErrorEvent(self, "Check-In Error", errmsg)
                self.post_message(event)
                return

            logging.info(f"POSTING CHECK IN BEGIN {item}")
            event = CheckInBeginEvent(item)
            self.post_message(event)
            #await table.add_item(CachedStockItemRow(item))
        except ApiException as e:
            event = IgnorableErrorEvent(self, "Scan Error", str(e))
            self.post_message(event)

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        if message.input.id == "checkin_item_input":
            message.input.add_class("readonly")
            await self.handle_item_input(message.input.value)
            message.input.remove_class("readonly")
            message.input.clear()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        status_text = self.query_one("#checkin_status_text")
        table = self.query_one("#checkin_items_table")
        if event.button.id == "checkin_clear_button":
            status_text.update("Cleared history")
            await table.clear_data()

class InventreeApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "InvenTree TUI"

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Transfer Items",id="transfer-items-tab"):
                yield TransferItemsTab()
            with TabPane("Check-In Items", id="checkin-items-tab"):
                yield CheckInItemsTab()
            with TabPane("Part Search", id="part-search-tab"):
                yield PartSearchTab()
        #yield Footer()

    async def on_ignorable_error_event(self, event: IgnorableErrorEvent):
        dialog = ErrorDialogScreen()
        dialog.title = event.title
        dialog.exception_message = event.message
        await self.push_screen(dialog)

    async def on_row_edit_event(self, event: RowEditEvent):
        dialog = RowEditScreen(event.table, event.row_key)
        await self.push_screen(dialog)

    async def on_check_in_begin_event(self, event: CheckInBeginEvent):
        logging.info("PUSHING CHECKIN SCREEN")
        dialog = CheckInScreen(event.item)

        async def checkin_dialog_callback(args) -> None:
            if args is None:
                return
            (item, destination) = args

            try:
                if item.stock_location.pk == destination.pk:
                    status_text = self.query_one("#checkin_status_text")
                    status_text.update(f"Stock #{item._stock_item.pk} was already at {destination.name}")
                else:
                    transfer_items([item], destination)
            except Exception as e:
                event = IgnorableErrorEvent(self, "Transfer Failed", str(e))
                self.post_message(event)
                return

            table = self.query_one("#checkin_items_table")
            await table.add_item(CachedStockItemCheckInRow(item))


        await self.push_screen(dialog, checkin_dialog_callback)

    def on_mount(self):
        self.query_one("#transfer_destination_input").focus()
        #self.query_one("#checkin_item_input").focus()

 #       async def handle_button_pressed(self, message: Button.Pressed) -> None:
#            if message.button.id == "exception_ok":
#                await self.pop_screen()

#app = InventreeApp()
#if __name__ == "__main__":
#    app = InventreeApp()
#    app.run()
