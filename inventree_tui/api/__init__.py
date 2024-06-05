import logging
from inventree.stock import StockItem, StockLocation
from requests.exceptions import RequestException
from inventree.part import Part
import os
import json
from dotenv import load_dotenv
from inventree.api import InvenTreeAPI

from pydantic import BaseModel, PrivateAttr, ValidationError
from pydantic.fields import Field, FieldInfo
from typing import List, Type, Any

load_dotenv()

host = os.environ.get("INVENTREE_API_HOST")
token = os.environ.get("INVENTREE_API_TOKEN")
api = InvenTreeAPI(host=host, token=token)

class ApiException(Exception):
    pass

class RowBaseModel(BaseModel):
    @classmethod
    def get_field_names(cls, by_alias=False) -> list[str]:
        field_names = []
        for k, v in cls.__fields__.items():
            if by_alias and isinstance(v, FieldInfo) and v.alias is not None:
                field_names.append(v.alias)
            else:
                field_names.append(k)

        return field_names

    @classmethod
    def get_editable_fields(cls, by_alias=True) -> list[str]:
        field_names = []
        for k, v in cls.__fields__.items():
            name = None
            if by_alias and isinstance(v, FieldInfo) and v.alias is not None:
                name = v.alias
            else:
                name = k

            logging.info(f"FIELD {k} : {v} : {type(v)}")
            if v.frozen == False:
                field_names.append(name)

        return field_names

    @classmethod
    def field_display_name(cls, field: str) -> str:
        return field

    # Used for updating internal data after modification 
    def update(self, other, validate=False):
        NotImplementedError(f"update(other) has not been implemented for {self.__class__}");

    def title_name(self):
        NotImplementedError(f"title_name() has not been implemented for {self.__class__}");


class CachedStockItemRowModel(RowBaseModel):
    stock_number: int = Field(frozen=True) 
    part_name: str = Field(frozen=True)
    quantity: int = Field(frozen=False)
    current_location: str = Field(frozen=True)

    def title_name(self):
        return f"Stock #{self.stock_number}"

    @classmethod
    def field_display_name(cls, field: str) -> str:
        d = {
            "stock_number": "Stock Number",
            "part_name":"Part Name",
            "quantity":"Quantity",
            "current_location":"Current Location",
        }
        return d[field]

class CachedStockItem():
    _stock_item: StockItem

    def title_name(self):
        return f"Stock #{self._stock_item.pk}"

    def __init__(self, _stock_item: StockItem):
        self._stock_item = _stock_item
        self._part = None
        self._default_location = None
        self._quantity = None
        self._stock_location = None
        self._destination = None

    def transfer(self, destination=None):
        if destination is not None:
            self._destination = destination
        if self._destination is None:
            raise Exception("Cannot transfer, no destination")
        transfer_items([self], self._destination)

    @property
    def part(self) -> Part:
        if self._part == None:
            self._part = self._stock_item.getPart()
        return self._part

    @property
    def default_location(self) -> StockLocation:
        default_location_pk = self.part.default_location
        if default_location_pk is None:
            return None
        return StockLocation(api, default_location_pk)

    @property
    def stock_location(self) -> StockLocation:
        if self._stock_location is None:
            self._stock_location = self._stock_item.getLocation()
        return self._stock_location

    @property
    def quantity(self):
        if self._quantity is None:
            return self._stock_item.quantity
        return self._quantity

    @quantity.setter
    def quantity(self, q):
        self._quantity = q

    def __hash__(self):
        return hash(self._stock_item.pk)

    def __eq__(self, other):
        if isinstance(other, CachedStockItem):
            return self._stock_item.pk == self._stock_item.pk
        return False

def transfer_items(items: List[CachedStockItem], location: StockLocation):
    _items = []
    for item in items:
        _items.append({"pk":item._stock_item.pk, "quantity": item.quantity})
        if item.quantity != item._stock_item.quantity:
            #TODO: implement a screen that will help you deal with the stock splits
            raise NotImplementedError("Quantity other that 'ALL' not implemented (yet)")

    StockItem.adjustStockItems(api, method='transfer', items=_items, location=location.pk)

def item_in_whitelist(item, whitelist):
    if whitelist is None:
        return True
    for s in whitelist:
        if s in item:
            return True
    return False


def scanToObject(item):
    if "stocklocation" in item:
        return StockLocation(api, item["stocklocation"]["pk"])
    elif "stockitem" in item:
        return CachedStockItem(StockItem(api, item["stockitem"]["pk"]))

def scanBarcode(text, whitelist=None):
    try:
        item = api.scanBarcode(text)
        if item_in_whitelist(item, whitelist):
            return scanToObject(item)
        else:
            raise ApiException(f"Item found but not in whitelist: {item}")

    except RequestException as e:
        if e.response is not None:
            raise ApiException(f"{e.response.status_code}")
        else:
            status = json.loads(e.args[0]['status'])
            if status != 200:
                raise ApiException(f"Status Code {status}")
            try:
                body = json.loads(e.args[0]['body'])
            except json.JSONDecodeError:
                raise ApiException(f"failed to decode body")

            raise ApiException(f"{body['error']}")
    return item


class CachedStockItemRow(CachedStockItemRowModel):
    _cached_stock_item: CachedStockItem = PrivateAttr(default=None)

    def __hash__(self):
        return hash(self._cached_stock_item)

    def __init__(self, cached_stock_item: CachedStockItem = None, **kwargs):
        if cached_stock_item is not None:
            super().__init__(
                stock_number=cached_stock_item._stock_item.pk,
                part_name=cached_stock_item.part.name,
                quantity=cached_stock_item.quantity,
                current_location=cached_stock_item.stock_location.name
            )
            self._cached_stock_item=cached_stock_item
        else:
            super().__init__(**kwargs)

    def update(self, other, validate=False, allow_greater=False):
        if validate:
            oq = self._cached_stock_item._stock_item.quantity
            if not allow_greater and other.quantity > oq:
                raise ValueError(f"Quantity is greater than the original stock quantity ({oq})")

        self.quantity = other.quantity
        self._cached_stock_item.quantity = other.quantity

        return True

    @property
    def item(self):
        return self._cached_stock_item


class CachedStockItemCheckInRowModel(RowBaseModel):
    stock_number: int = Field(frozen=True) 
    part_name: str = Field(frozen=True)
    quantity: int = Field(frozen=True)
    previous_location: str = Field(frozen=True)
    new_location: str = Field(frozen=True)

    def title_name(self):
        return f"Stock #{self.stock_number}"

    @classmethod
    def field_display_name(cls, field: str) -> str:
        d = {
            "stock_number": "Stock Number",
            "part_name":"Part Name",
            "quantity":"Quantity",
            "previous_location":"Previous Location",
            "new_location":"New Location",
        }
        return d[field]

class CachedStockItemCheckInRow(CachedStockItemCheckInRowModel):
    _cached_stock_item: CachedStockItem = PrivateAttr(default=None)

    def __hash__(self):
        return hash(self._cached_stock_item)

    def __init__(self, cached_stock_item: CachedStockItem = None, **kwargs):
        if cached_stock_item is not None:
            super().__init__(
                stock_number=cached_stock_item._stock_item.pk,
                part_name=cached_stock_item.part.name,
                quantity=cached_stock_item.quantity,
                previous_location=cached_stock_item.stock_location.name,
                new_location=cached_stock_item.default_location.name
            )
            self._cached_stock_item=cached_stock_item
        else:
            super().__init__(**kwargs)

    def update(self, other, validate=False, allow_greater=False):
        if validate:
            oq = self._cached_stock_item._stock_item.quantity
            if not allow_greater and other.quantity > oq:
                raise ValueError(f"Quantity is greater than the original stock quantity ({oq})")

        self.quantity = other.quantity
        self._cached_stock_item.quantity = other.quantity

        return True

    @property
    def item(self):
        return self._cached_stock_item
