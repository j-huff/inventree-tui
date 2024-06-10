import logging
from textual.app import ComposeResult
from textual.widget import Widget
from typing import List, Type
from inventree.base import InventreeObject
from .base import api
from requests.exceptions import RequestException

from textual_autocomplete import (
    AutoComplete,
    Dropdown,
    DropdownItem,
)

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

def Scanner(Widget):
    def __init__(self, input_id: str | None = None):
        pass

    def compose(self) -> ComposeResult:
        pass
        #yield AutoComplete(tooltip
