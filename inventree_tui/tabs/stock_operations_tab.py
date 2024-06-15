from typing import cast, Generic, TypeVar, get_args, Type
from pydantic import BaseModel, ConfigDict, PrivateAttr, Field
import logging
from datetime import datetime, timedelta

from inventree.stock import StockItem, StockItemTracking
from inventree.base import InventreeObject

from textual import work, on
from textual.validation import Function, Number, ValidationResult, Validator
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Pretty,
    Input,
    Button,
    Static,
    RadioSet,
    RadioButton
)

from inventree_tui.api import (
    CachedStockItem,
    CachedStockItemCheckInRow,
    transfer_items,
    InventreeScanner,
)

from inventree_tui.api.stock_item_tracking import CachedStockItemTracking
from inventree_tui.error_screen import IgnorableErrorEvent
from inventree_tui.status import StatusChanged
from inventree_tui.model_data_table import ModelDataTable
from inventree_tui.components import ButtonBar
from inventree_tui.api import api, RowBaseModel
from inventree_tui.validation import GreaterThan

class StockAdjustmentScreen(ModalScreen):
    dialog_title = reactive("Row Edit", recompose=True)

    def __init__(self, item, method):
        self.item = item
        self.method = method
        super().__init__()
        self.dialog_title = f"Adjust Stock: {self.item.title_name()} ({method})"

    def compose(self) -> ComposeResult:
        with Container(id="adjust-dialog") as container:
            container.border_title = self.dialog_title
            yield Static(f"Adjust Method: {self.method}")
            #yield Static(f"Default Location: {self.item.default_location.name}"
            if self.method == "remove":
                yield Input(
                    type="number",
                    placeholder="Enter a number...",
                    validators=[
                        Number(maximum=self.item.original_quantity),
                        GreaterThan(0),
                    ],
                )
            elif self.method == "add":
                yield Input(
                    type="number",
                    placeholder="Enter a number...",
                    validators=[
                        GreaterThan(0),
                    ],
                )
            elif self.method == "count":
                yield Input(
                    type="number",
                    placeholder="Enter a number...",
                    validators=[
                        Number(minimum=0),
                    ],
                )
            else:
                raise NotImplemented(f"method not implemented: {self.method}")
            static = Static("", id="adjust_number_error_msg")
            static.styles.display = "none"
            yield static
            yield Static("Confirm adjustment?", classes="dialog-question")
            with ButtonBar (classes="button-bar"):
                button = Button("Confirm", variant="success", id="adjust_confirm_button")
                button.disabled = True
                yield button
                yield Static(" ")
                yield Button("Cancel", variant="error", id="adjust-cancel")

    @on(Input.Changed)
    def show_invalid_reasons(self, event: Input.Changed) -> None:
        # Updating the UI to show the reasons why validation failed
        err = self.query_one("#adjust_number_error_msg")
        button = self.query_one("#adjust_confirm_button")

        if not event.validation_result.is_valid:
            err.update(". ".join(event.validation_result.failure_descriptions))
            err.styles.display = "block"
            button.disabled = True
        else:
            err.update("")
            err.styles.display = "none"
            button.disabled = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "adjust-cancel":
            self.dismiss(None)
            return
        if event.button.id == "adjust_confirm_button":
            q = float(self.query_one(Input).value)
            item = {"pk": self.item.pk, "quantity": q}
            self.dismiss((item, self.method))
            return

class CachedStockItemTrackingRowModel(RowBaseModel, CachedStockItemTracking):
    timestamp_str: str = Field(frozen=True)
    stock_pk: int = Field(frozen=True)
    pk: int = Field(frozen=True)
    label: str = Field(frozen=True)
    op_string: str = Field(frozen=True)
    info: str = Field(frozen=True)

    timestamp: datetime = Field(frozen=True)

    # no repeats
    def __hash__(self):
        return self.obj.pk

    def __init__(self, item: CachedStockItemTracking):
        obj = item.obj
        super().__init__(
            obj = obj,
            timestamp_str = item.datetime_string(),
            info = item.to_string(),
            label = obj.label,
            stock_pk = obj.item,
            pk = obj.pk,
            op_string = item.op_string(),
            timestamp = item.datetime()
        )

    @classmethod
    def field_display_dict(cls):
        return {
            "pk": "#",
            "timestamp_str": "Timestamp",
            "timestamp": None,
            "stock_pk": "Stock#",
            "label": "Label",
            "op_string": "Info",
            "info": None,
            "obj": None,
        }

    def update(self, other, validate=False):
        pass

    def title_name(self):
        return f"Tracking Item #{self.obj.pk}"

class StockOpsTab(Container):
    def __init__(self):
        super().__init__()
        self.creation_time = datetime.now()
        self.default_oldest_delta = timedelta(hours=8)

    def compose(self) -> ComposeResult:
        yield InventreeScanner(
            id="stock_ops_items_scanner",
            whitelist=[StockItem],
            placeholder="Scan Items",
            input_id="stock_ops_item_input",
            autocomplete=False
        )
        with RadioSet(id="stock_ops_radio_set"):
            yield RadioButton("Remove", value=True, name="remove")
            yield RadioButton("Add", name="add")
            yield RadioButton("Count", name="count")
        yield ModelDataTable(
            model_class=CachedStockItemTrackingRowModel,
            sort_column_key="pk",
            id="stock_ops_table",
            zebra_stripes=True,
            allow_delete=False,
        )

    def on_mount(self):
        self.fetch_recent()

    # Will fetch recent items until it starts overlapping with the data
    # already in the table. If no data is in the table, it will fetch all of the data until
    # it reaches the 'oldest' limit

    @work(exclusive=False, thread=True)
    async def fetch_recent(self, increment = 10, oldest_delta : timedelta | None = None):

        if oldest_delta is None:
            oldest_delta = self.default_oldest_delta

        table = cast(ModelDataTable, self.query_one("#stock_ops_table"))

        oldest = self.creation_time - oldest_delta

        most_recent = 1
        for k,v in table.data.items():
            most_recent = max(v.obj.pk, most_recent)

        # Returns true if the fetched items did not hit most_recent, otherwise false
        async def add_items(table, limit, offset, most_recent, oldest):
            new_data = CachedStockItemTracking.list(api, limit=limit, offset=offset)
            hit_most_recent = False
            hit_oldest = False
            for item in new_data:
                row = CachedStockItemTrackingRowModel(item)
                await table.add_item(row)
                if row.obj.pk  <= most_recent:
                    hit_most_recent = True
                if row.timestamp <= oldest:
                    hit_oldest = True

            return not (hit_most_recent or hit_oldest)

        offset = 0
        limit = increment
        while await add_items(table, limit, offset, most_recent, oldest):
            offset += limit


    @work(exclusive=False, thread=True)
    async def fetch_items(self, limit=10, **kwargs):
        new_data = CachedStockItemTracking.list(api, limit=limit, **kwargs)
        table = cast(ModelDataTable, self.query_one("#stock_ops_table"))
        for item in new_data:
            await table.add_item(CachedStockItemTrackingRowModel(item))


    def get_selected_method(self) -> str:
        table = cast(RadioSet, self.query_one("#stock_ops_radio_set"))
        radio_button = cast(RadioButton, table.pressed_button)
        return radio_button.name

    def on_inventree_scanner_item_scanned(self, message: InventreeScanner.ItemScanned) -> None:
        #if message.sender.id == "stock_ops_items_scanner":
        item = CachedStockItem(stock_item=message.obj)
        #TODO: check for any reason why we shouldnt be able to 
        # operate on this stock item
        method = self.get_selected_method()
        self.open_stock_adjustment_dialog(item, method)

    def open_stock_adjustment_dialog(self, item: CachedStockItem, method: str):
        dialog = StockAdjustmentScreen(item, method)

        async def stock_adjust_dialog_callback(args) -> None:
            if args is None:
                return

            (item, method) = args

            try:
                StockItem.adjustStockItems(api, method, [item])
            except Exception as e:
                event = IgnorableErrorEvent(self, "Transfer Failed", str(e))
                self.post_message(event)
                return

            self.fetch_recent()
            self.post_message(StatusChanged(self,f"""\
Stock item adjusted ({method})"""))

            #table = cast(ModelDataTable, self.query_one("#checkin_items_table"))
            #await table.add_item(CachedStockItemCheckInRow(item))

        self.app.push_screen(dialog, stock_adjust_dialog_callback)
