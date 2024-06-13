import logging
import json
from typing import List, Type, Dict

from dataclasses import dataclass
from inventree.base import InventreeObject
from requests.exceptions import RequestException
from fuzzywuzzy import fuzz

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Event
from textual.widgets import (
    Input,
)

from textual_autocomplete import (
    AutoComplete,
    Dropdown,
    DropdownItem,
    InputState
)

from inventree_tui.error_screen import IgnorableErrorEvent
from .base import api, ApiException


class WhitelistException(Exception):
    def __init__(self, item, whitelist):
        self.message = "Item not in whitelist"
        self.item = item
        self.whitelist = whitelist
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message}: item not one of {self.whitelist}'

def item_in_whitelist(item, whitelist: List[Type[InventreeObject]]):
    for cls in whitelist:
        if cls.MODEL_TYPE in item:
            return True
    return False

# Returns the InventreeObject class of the item if it's in the whitelist,
# otherwise returns None
def item_class(item, whitelist: List[Type[InventreeObject]]) -> Type[InventreeObject] | None:
    for cls in whitelist:
        logging.info(vars(cls))
        if cls.MODEL_TYPE in item:
            return cls
    return None

def scan_to_object(item, cls: Type[InventreeObject]):
    return cls(api, item[cls.MODEL_TYPE]["pk"])

def scan_barcode(text, whitelist: List[Type[InventreeObject]]) -> Type[InventreeObject]:
    try:
        item = api.scanBarcode(text)
        cls = item_class(item, whitelist)
        if cls is None:
            raise WhitelistException(item, whitelist)
        return scan_to_object(item, cls)

    except RequestException as e:
        if e.response is not None:
            raise ApiException(f"{e.response.text}", status_code=e.response.status_code) from e

        status = e.args[0]['status_code']
        if status != 200:
            raise ApiException(f"Status Code {status}", status_code=status) from e
        try:
            body = json.loads(e.args[0]['body'])
        except json.JSONDecodeError as e2:
            raise ApiException("Failed to decode body", status_code=status) from e2

        raise ApiException(f"{body['error']}", status_code=status) from e

@dataclass
class InventreeDropdownItem(DropdownItem):
    inventree_object: InventreeObject | None = None

    @classmethod
    def create(cls, inventree_object: InventreeObject) -> "InventreeDropdownItem":
        return cls(
            inventree_object=inventree_object,
            main=inventree_object.name
        )

def search_similarity(search_term: str, string: str):
    similarity_ratio = fuzz.ratio(search_term.lower(), string.lower()) / 100
    return similarity_ratio

class InventreeScanner(Vertical):
    search_limit = 5

    class ItemScanned(Event):
        def __init__(self, sender, obj: InventreeObject):
            super().__init__()
            self.sender = sender
            self.obj = obj

    # pylint: disable=redefined-builtin,too-many-arguments
    def __init__(self,
        id: str | None = None,
        whitelist: List[Type[InventreeObject]] | None = None,
        placeholder: str = "",
        input_id: str | None = None,
        autocomplete: bool = False,
        search: bool = False,
    ) -> None:
        self.input_id = input_id
        self.whitelist = whitelist if whitelist is not None else []
        self.placeholder = placeholder
        self.autocomplete_enabled = autocomplete
        self.search_enabled = search
        self.search_cache : Dict[Type[InventreeObject], Dict[str, List[InventreeObject]]] = {}
        self.dropdown = Dropdown(
            items=self.get_dropdown_items
        )

        super().__init__(id=id)

    @work(exclusive=False, thread=True)
    def search(self, search_term: str) -> None:
        for cls in self.whitelist:
            cls_items = cls.list(api, search=search_term, limit=self.search_limit)
            self.search_cache.setdefault(cls, {})[search_term] = cls_items

        self.dropdown.sync_state(
            self.dropdown.input_widget.value,
            self.dropdown.input_widget.cursor_position
        )

    def on_input_changed(self, message: Input.Changed) -> None:
        if not self.autocomplete_enabled:
            return
        text = message.value.strip()
        # Kind of a hack: If the input starts with {, don't search
        if text.startswith("{") or len(text) <= 1:
            return
        self.search(text)

    def get_dropdown_items(self, input_state: InputState) -> list[DropdownItem]:
        if not self.autocomplete_enabled:
            return []
        text = input_state.value
        text = text.strip()
        items = {}
        for cls, d in self.search_cache.items():
            for cls_items in d.values():
                for item in cls_items:
                    items[(cls, item.pk)] = item

        minimum_similarity = 0.5

        l = [(search_similarity(text, i.name), i) for i in items.values()]
        l = [(s,i) for s,i in l if s > minimum_similarity]
        sorted_by_similarity = sorted(l, key=lambda tup: tup[0], reverse=True)

        return [InventreeDropdownItem.create(i) for s,i in  sorted_by_similarity]

    def compose(self) -> ComposeResult:
        yield AutoComplete(
            Input(id=self.input_id, placeholder=self.placeholder),
            self.dropdown
        )

    @work(exclusive=False, thread=True)
    def scan_barcode(self, text: str) -> None:
        try:
            obj = scan_barcode(text, self.whitelist)
        except ApiException as e:
            event = IgnorableErrorEvent(self, "Scan Error", str(e))
            self.post_message(event)
            return
        except WhitelistException as e:
            self.post_message(IgnorableErrorEvent(self, "Scan Error", str(e)))
            return
        self.post_message(self.ItemScanned(self, obj))

    @work(exclusive=False, thread=True)
    async def search_single_item(self, text: str) -> None:
        # Return the first item that matches in the search.
        # Could maybe use the search cache instead of doing a new search,
        # but the cache may not be updated when the user submits their input
        for cls in self.whitelist:
            try:
                cls_items = cls.list(api, search=text, limit=1)
            except RequestException as e:
                self.post_message(IgnorableErrorEvent(self, "Search Failed", str(e)))

            if len(cls_items) > 0:
                self.post_message(self.ItemScanned(self, cls_items[0]))
                return

        event = IgnorableErrorEvent(self,
            "No Results",
            f"The search term '{text}' yielded no results"
        )
        self.post_message(event)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        text = message.value.strip()
        if text.startswith("{"):
            self.scan_barcode(text)
        elif len(text) > 0 and (self.search_enabled or self.autocomplete_enabled):
            self.search_single_item(text)

        message.input.clear()
