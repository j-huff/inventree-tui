from __future__ import annotations


from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets.data_table import RowKey
from textual.widgets import (
    DataTable,
    Input,
    Button,
    Static,
    Label
)

from dataclasses import dataclass
import logging
from typing import Type, Dict, cast
from pydantic import ValidationError

from inventree_tui.api import RowBaseModel

class ModelDataTable(DataTable):
    @dataclass
    class RowEdit(Message):
        table: ModelDataTable
        row_key: RowKey

    def __init__(self, model_class: Type[RowBaseModel], sort_column_key: str | None = None, *args, **kwargs):
        self.data : Dict[str, RowBaseModel] = {} #reactive(set([]), recompose=True)
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

        self.cursor_type = "row"
        self.zerbra_stipes = True
        await self.reload()

    async def reload(self) -> None:
        await self.update()

    async def add_item(self, item: RowBaseModel):
        logging.info(f"ADDING ITEM: {item} to {self.data}")
        row_key = self.obj_row_key(item)
        key = cast(str, row_key.value)
        if key in self.data:
            return
        self.data[key] = item
        await self.update()

    async def clear_data(self):
        self.data = {}
        await self.update()

    def add_row(self, *cells, height=1, key=None, label=None):
        super().add_row(*cells, height=height, key=key, label=label)

    def obj_row_key(self, obj: RowBaseModel) -> RowKey:
        return RowKey(value=str(hash(obj)))

    async def update(self, data: Dict[str, RowBaseModel] | None = None) -> None:
        if data is None:
            data = self.data

        columns = self.model_class.get_field_names()
        needs_sorted = False
        for key, obj in data.items():
            if key not in self.rows:
                values = [getattr(obj, col) for col in columns]
                self.add_row(*values, key=key)
                needs_sorted = True

        keys = list(self.rows.keys())
        for row_key in keys:
            if row_key.value not in data:
                self.remove_row(row_key)

        for row_key in self.rows.keys():
            if row_key.value is None:
                continue
            obj = self.data[row_key.value]
            cells = self.get_row(row_key)
            for col_key in self.columns.keys():
                if col_key != "delete_button" and col_key.value is not None:
                    current_value = self.get_cell(row_key, col_key)
                    new_value = getattr(obj, col_key.value)
                    if current_value != new_value:
                        needs_sorted = True
                        logging.info(f"VALUE CHANGED {current_value} -> {new_value}")
                        self.update_cell(row_key, col_key, value=new_value)
                        logging.info(f"UPDATING CELL: {row_key.value} {col_key.value}")

        if self.sort_column_key is not None and needs_sorted:
            self.sort(self.sort_column_key, reverse=True)

    async def on_data_table_row_selected(self, message: DataTable.RowSelected):
        event = self.RowEdit(self, message.row_key)
        self.post_message(event)

    async def on_key(self, event: Key) -> None:
        logging.debug(f"{event}")
        if event.name == "delete" and len(self.data) > 0:
            logging.debug(f"DELETE {self.cursor_row}")
            row = self.ordered_rows[self.cursor_row]
            row_key = row.key
            key = cast(str, row_key.value)
            del self.data[key]
            self.move_cursor(row=self.cursor_row-1)
            await self.update()

class RowEditScreen(Screen):
    dialog_title = reactive("Row Edit", recompose=True)
    start_values: reactive[Dict] = reactive({}, recompose=True)
    error_message = reactive("")

    def __init__(self, table, row_key):
        self.table = table
        self.row = reactive(row_key.value, recompose=True)
        super().__init__()
        self.dialog_title = f"Row Edit: {self.row.title_name()}"

        editable = self.row.get_editable_fields()
        logging.info(f"EDITABLE ROWS: {editable}")
        values = {}
        for name in editable:
            values[name] = getattr(self.row, name)
        self.start_values = values

    def watch_error_message(self, msg: str) -> None:
        try:
            errmsg = cast(Static, self.query_one("#errormsg"))
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
