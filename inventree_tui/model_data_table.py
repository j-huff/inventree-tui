from __future__ import annotations

import logging
from typing import Type, Dict, cast, TypeVar, Generic
from pydantic import ValidationError

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Key
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

from inventree_tui.components import ButtonBar
from inventree_tui.api import RowBaseModel

T = TypeVar('T', bound=RowBaseModel)
class ModelDataTable(DataTable):
    def __init__(self,
            model_class: Type[T],
            *args,
            sort_column_key: str | None = None,
            editable: bool = False,
            allow_delete: bool = True,
            **kwargs):

        self.data : Dict[str, T] = {} #reactive(set([]), recompose=True)
        self.sort_column_key = None
        self.editable = editable
        self.allow_delete = allow_delete

        super().__init__(*args, **kwargs)
        self.model_class = model_class
        self.sort_column_key = sort_column_key
        if self.sort_column_key is not None \
            and self.sort_column_key not in model_class.get_field_names(by_alias=True):
            raise ValueError(f"""\
Not a valid sort column, options are {model_class.get_field_names(by_alias=True)}""")

    def on_mount(self) -> None:
        columns = self.model_class.column_fields()
        for col in columns:
            dn = self.model_class.field_display_name(col)
            if dn is not None:
                self.add_column(dn, key=col)

        self.cursor_type = "row"
        self.reload()

    @work
    async def reload(self) -> None:
        await self.update()

    async def add_item(self, item: T):
        row_key = self.obj_row_key(item)
        key = cast(str, row_key.value)
        if key in self.data:
            return
        self.data[key] = item
        await self.update()

    async def clear_data(self):
        self.data = {}
        await self.update()

    def obj_row_key(self, obj: T) -> RowKey:
        return RowKey(value=str(hash(obj)))

    async def update(self, data: Dict[str, T] | None = None) -> None:
        if data is None:
            data = self.data

        #columns = self.model_class.get_field_names()
        columns = self.model_class.column_fields()

        needs_sorted = False
        for key, obj in data.items():
            if key not in self.rows:
                values = [getattr(obj, col) for col in columns]
                logging.info("ADDING ROW %s", values)
                logging.info("ADDING ROW KEY %s", key)
                self.add_row(*values, key=key)
                needs_sorted = True

        keys = list(self.rows.keys())
        for row_key in keys:
            if row_key.value not in data:
                self.remove_row(row_key)

        for row_key, _ in self.rows.items():
            if row_key.value is None:
                continue
            obj = self.data[row_key.value]
            #cells = self.get_row(row_key)
            for col_key, _ in self.columns.items():
                if col_key != "delete_button" and col_key.value is not None:
                    current_value = self.get_cell(row_key, col_key)
                    new_value = getattr(obj, col_key.value)
                    if current_value != new_value:
                        needs_sorted = True
                        self.update_cell(row_key, col_key, value=new_value)

        if self.sort_column_key is not None and needs_sorted:
            self.sort(self.sort_column_key, reverse=True)

    async def on_data_table_row_selected(self, message: DataTable.RowSelected):
        if message.row_key.value is None or not self.editable:
            return
        obj = self.data[message.row_key.value]
        dialog = RowEditScreen(self, obj)
        await self.app.push_screen(dialog)

    async def on_key(self, event: Key) -> None:
        if self.allow_delete and event.name == "delete" and len(self.data) > 0:
            row = self.ordered_rows[self.cursor_row]
            row_key = row.key
            key = cast(str, row_key.value)
            del self.data[key]
            self.move_cursor(row=self.cursor_row-1)
            await self.update()

class RowEditScreen(Screen,  Generic[T]):
    dialog_title = reactive("Row Edit", recompose=True)
    start_values: reactive[Dict] = reactive({}, recompose=True)
    error_message = reactive("")

    def __init__(self, table, row: T):
        super().__init__()
        self.table = table
        self.row = row

        self.dialog_title = f"Row Edit: {self.row.title_name()}"

        editable = self.row.get_editable_fields()
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
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        with Container(id="row-edit-dialog") as container:
            container.border_title = self.dialog_title
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
            with ButtonBar (classes="button-bar"):
                yield Button("OK", variant="primary", id="ok")
                yield Static(" ")
                yield Button("Cancel", variant="error", id="cancel")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        inputs = self.query(Input)

        other = self.row.copy(deep=False)
        for i in inputs:
            if i.name is not None and i.value is not None:
                attr = getattr(other, i.name)
                setattr(other, i.name, attr.__class__(i.value))

        try:
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
