import logging
from typing import cast
from textual.app import ComposeResult
from textual.widget import Widget
from typing import List, Type
from inventree.base import InventreeObject
from .base import api
from requests.exceptions import RequestException
from dataclasses import dataclass
import json

from textual.widgets import (
    Input,
)

from textual_autocomplete import (
    AutoComplete,
    Dropdown,
    DropdownItem,
    InputState
)

from textual.containers import Vertical

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
            raise ApiException(f"Item found but not in whitelist: {item}")
        else:
            return scan_to_object(item, cls)

    except RequestException as e:
        if e.response is not None:
            raise ApiException(f"{e.response.status_code}")
        else:
            status = json.loads(e.args[0]['status_code'])
            if status != 200:
                raise ApiException(f"Status Code {status}")
            try:
                body = json.loads(e.args[0]['body'])
            except json.JSONDecodeError:
                raise ApiException(f"failed to decode body")

            raise ApiException(f"{body['error']}")

@dataclass
class InventreeDropdownItem(DropdownItem):
    inventree_object: InventreeObject | None = None

    @classmethod
    def create(cls, inventree_object: InventreeObject) -> "InventreeDropdownItem":
        return cls(inventree_object=inventree_object, main=inventree_object.name)

#def get_items(input_state: InputState) -> list[DropdownItem]:
    #    logging.info("RETURNING []")
#    return list([DropdownItem("test") for i in range(3)])

class InventreeScanner(Vertical):
    classes = "autocomplete_container"

    def __init__(self,
        whitelist: List[Type[InventreeObject]] = [],
        placeholder: str | None = None,
        input_id: str | None = None,
    ) -> None:
        self.input_id = input_id
        self.whitelist = whitelist
        self.placeholder = placeholder
        super().__init__();

    def get_dropdown_items(self, input_state: InputState) -> list[DropdownItem]:
        text = input_state.value
        text = text.strip()
        items = []
        if len(text) > 2:
            for cls in self.whitelist:
                cls_items = cls.list(api, search=text)
                items = items + cls_items

        #return [DropdownItem("TEST") for i in items]
        return [cast(DropdownItem,InventreeDropdownItem.create(i)) for i in items]

    def compose(self) -> ComposeResult:
        yield AutoComplete(
            Input(id=self.input_id, placeholder=self.placeholder),
            Dropdown(items=self.get_dropdown_items),
        )
