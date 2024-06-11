
import json
import logging
from datetime import datetime
from typing import List

from inventree.stock import StockItem, StockLocation
from pydantic import BaseModel, PrivateAttr
from pydantic.fields import Field, FieldInfo

from .base import api, ApiException
from .stock_item import CachedStockItem
from .part_search import CachedPart
from .scanner import InventreeScanner, WhitelistException


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

def transfer_items(items: List[CachedStockItem], location: StockLocation):
    _items = []
    for item in items:
        _items.append({"pk":item._stock_item.pk, "quantity": item.quantity})
        if item.quantity != item._stock_item.quantity:
            #TODO: implement a screen that will help you deal with the stock splits
            raise NotImplementedError("Quantity other that 'ALL' not implemented (yet)")

    StockItem.adjustStockItems(api, method='transfer', items=_items, location=location.pk)

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
                current_location=cached_stock_item.stock_location_name
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
    timestamp: datetime = Field(frozen=True)

    def title_name(self):
        return f"Stock #{self.stock_number}"

    @classmethod
    def field_display_name(cls, field: str) -> str:
        d = {
            "stock_number": "Stock#",
            "part_name":"Part Name",
            "quantity":"Q",
            "previous_location":"Prev Loc",
            "new_location":"New Loc",
            "timestamp":"Check-In Timestamp",
        }
        return d[field]

class CachedStockItemCheckInRow(CachedStockItemCheckInRowModel):
    _cached_stock_item: CachedStockItem = PrivateAttr(default=None)

    def __hash__(self):
        # This will allow for repeats
        return hash(self._cached_stock_item._stock_item)

    def __init__(self, cached_stock_item: CachedStockItem = None, **kwargs):
        if cached_stock_item is not None:
            super().__init__(
                stock_number=cached_stock_item._stock_item.pk,
                part_name=cached_stock_item.part.name,
                quantity=cached_stock_item.quantity,
                previous_location=cached_stock_item.stock_location_name,
                new_location=cached_stock_item.default_location.name,
                timestamp=datetime.now(),
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
