from __future__ import annotations
from typing import cast, Generic, TypeVar, get_args, Type
from pydantic import BaseModel, ConfigDict, PrivateAttr, Field
import logging
from datetime import datetime, timedelta
from threading import Semaphore

from inventree.stock import StockItem, StockItemTracking
from inventree.base import InventreeObject

from textual import work, on
from textual.validation import Function, Number, ValidationResult, Validator
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.message import Message
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
from inventree_tui.sound import Sound, tts
from inventree_tui.settings import settings

class StockAdjustmentScreen(ModalScreen):
    dialog_title = reactive("Row Edit", recompose=True)

    def __init__(self, item : CachedStockItem, method):
        self.item = item
        self.method = method
        super().__init__()
        self.dialog_title = f"Adjust Stock: {self.item.title_name()} ({self.item.part.name})"

        operations = {
            "add":"Adding to",
            "remove":"Removing from",
            "count":"Counting",
        }
        def sound_fn():
            tts(f"{operations[method]} {item.part.name}").play()
        self.post_message(Sound(self, fn=sound_fn))

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
                    value="1",
                )
            elif self.method == "add":
                yield Input(
                    type="number",
                    placeholder="Enter a number...",
                    validators=[
                        GreaterThan(0),
                    ],
                    value="1",
                )
            elif self.method == "count":
                yield Input(
                    type="number",
                    placeholder="Enter a number...",
                    validators=[
                        Number(minimum=0),
                    ],
                    value=str(self.item.original_quantity),
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

    @on(Input.Submitted)
    def move_to_button(self, event: Input.Submitted) -> None:
        if event.validation_result.is_valid:
            btn = self.query_one("#adjust_confirm_button")
            btn.focus()

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
    short_label_: str = Field(frozen=True)
    part_name: str = Field(frozen=False)
    op_string_: str = Field(frozen=True)
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
            short_label_ = item.short_label(),
            stock_pk = obj.item,
            part_name = "loading...", #item.stock_item.part.name,
            pk = obj.pk,
            op_string_ = item.op_string(),
            timestamp = item.datetime()
        )

    def load_name(self):
        self.part_name = self.stock_item.part.name

    @classmethod
    def field_display_dict(cls):
        return {
            "pk": "#",
            "timestamp_str": "Timestamp",
            "timestamp": None,
            "stock_pk": "Stk#",
            "part_name": "Part",
            "label": None,
            "short_label_": "Label",
            "op_string_": "Info",
            "info": None,
            "obj": None,
        }

    def update(self, other, validate=False):
        pass

    def title_name(self):
        return f"Tracking Item #{self.obj.pk}"

class MyRadioSet(RadioSet):

    DEFAULT_CSS = """
    MyRadioSet {
        border: tall transparent;
        background: $boost;
        padding: 0 1 0 0;
        height: auto;
        width: auto;
    }

    MyRadioSet:focus {
        border: tall $accent;
    }

    /* The following rules/styles mimic similar ToggleButton:focus rules in
     * ToggleButton. If those styles ever get updated, these should be too.
     */

    MyRadioSet > * {
        background: transparent;
        border: none;
        padding: 0 1;
    }

    MyRadioSet:focus > RadioButton.-selected > .toggle--label {
        text-style: underline;
    }

    MyRadioSet:focus ToggleButton.-selected > .toggle--button {
        background: $foreground 25%;
    }

    MyRadioSet:focus > RadioButton.-on.-selected > .toggle--button {
        background: $foreground 25%;
    }
    """

    def _on_radio_button_changed(self, event: RadioButton.Changed) -> None:
        """Respond to the value of a button in the set being changed.

        Args:
            event: The event.
        """
        # We're going to consume the underlying radio button events, making
        # it appear as if they don't emit their own, as far as the caller is
        # concerned. As such, stop the event bubbling and also prohibit the
        # same event being sent out if/when we make a value change in here.
        event.stop()
        with self.prevent(RadioButton.Changed):
            # If the message pertains to a button being clicked to on...
            if event.radio_button.value:
                # If there's a button pressed right now and it's not really a
                # case of the user mashing on the same button...
                if (
                    self._pressed_button is not None
                    and self._pressed_button != event.radio_button
                ):
                    self._pressed_button.value = False
                # Make the pressed button this new button.
                self._pressed_button = event.radio_button
                # Emit a message to say our state has changed.
                self.post_message(self.Changed(self, event.radio_button))
            else:
                # We're being clicked off, we don't want that.
                event.radio_button.value = True
                self.post_message(self.Reselected(self))

    class Changed(RadioSet.Changed):
        pass

    class Reselected(Message):
        def __init__(self, radio_set: MyRadioSet) -> None:
            super().__init__()
            self.radio_set = radio_set

        @property
        def control(self) -> MyRadioSet:
            return self.radio_set

class StockOpsTab(Container):
    def __init__(self):
        super().__init__()
        self.creation_time = datetime.now()
        self.default_oldest_delta = timedelta(
            minutes=settings.stock_ops_tab.history_delta_minutes,
            hours=settings.stock_ops_tab.history_delta_hours,
            days=settings.stock_ops_tab.history_delta_days,
        )
        # Limits the number of concurrent works making API calls
        self.semaphore = Semaphore(5)

    def compose(self) -> ComposeResult:
        yield InventreeScanner(
            id="stock_ops_items_scanner",
            whitelist=[StockItem],
            placeholder="Scan Items",
            input_id="stock_ops_item_input",
            autocomplete=False,
            sound=True,
        )
        with MyRadioSet(id="stock_ops_radio_set"):
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

    #TODO: implement lazy loading of part names. 
    @work(exclusive=False, thread=True)
    async def load_row(self, row_key, row):
        self.semaphore.acquire()
        max_retries = 3
        for i in range(max_retries):
            try:
                row.load_name();
                break
            except Exception as e:
                if i+1 == max_retries:
                    raise e
        self.semaphore.release()
        table = cast(ModelDataTable, self.query_one("#stock_ops_table"))
        self.app.call_from_thread(table.update)
        #await table.update()

    # Will fetch recent items until it starts overlapping with the data
    # already in the table. If no data is in the table, it will fetch all of the data until
    # it reaches the 'oldest' limit
    @work(exclusive=False, thread=True)
    async def fetch_recent(self, increment = settings.stock_ops_tab.history_chunk_size, oldest_delta : timedelta | None = None):

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
                row_key = await table.add_item(row)
                self.load_row(row_key, row)
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

    def on_my_radio_set_changed(self, event: MyRadioSet.Changed) -> None:
        if event.control.id == "stock_ops_radio_set":
            self.query_one("#stock_ops_item_input").focus()

    def on_my_radio_set_reselected(self, event: MyRadioSet.Reselected) -> None:
        if event.control.id == "stock_ops_radio_set":
            self.query_one("#stock_ops_item_input").focus()

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
