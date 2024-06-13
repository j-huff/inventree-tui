from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Dict

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
        for k, v in cls.model_fields.items():
            if by_alias and isinstance(v, FieldInfo) \
                        and v.alias is not None \
                        and isinstance(v.alias, str):
                field_names.append(v.alias)
            else:
                field_names.append(k)

        return field_names

    @classmethod
    def get_editable_fields(cls, by_alias=True) -> list[str]:
        field_names = []
        for field_name, field_info in cls.model_fields.items():

            name = None
            if by_alias and isinstance(field_info, FieldInfo) and field_info.alias is not None:
                name = field_info.alias
            else:
                name = field_name

            logging.info("FIELD %s : %s : %s", field_name, field_info, type(field_info))
            if not field_info.frozen and isinstance(name, str):
                field_names.append(name)

        return field_names


    @classmethod
    def column_fields(cls) -> List[str]:
        return [k for k, v in cls.field_display_dict().items() if v is not None]

    # This should be overwritten
    @classmethod
    def field_display_dict(cls) -> Dict[str, str | None]:
        keys = cls.get_field_names()
        return {key: key for key in keys}

    @classmethod
    def field_display_name(cls, field: str) -> str:
        d = cls.field_display_dict()
        res = d[field]
        if res is None:
            raise ValueError(f"Field should not be displayed: {field}")
        return res

    # Used for updating internal data after modification
    def update(self, other: RowBaseModel, validate=False):
        raise NotImplementedError(f"update(other) has not been implemented for {self.__class__}")

    def title_name(self):
        raise NotImplementedError(f"title_name() has not been implemented for {self.__class__}")


class CachedStockItemRowModel(RowBaseModel):
    stock_number: int = Field(frozen=True)
    part_name: str = Field(frozen=True)
    quantity: int = Field(frozen=False)
    current_location: str = Field(frozen=True)

    def update(self, other, validate=False):
        raise NotImplementedError(f"update(other) has not been implemented for {self.__class__}")

    def title_name(self):
        return f"Stock #{self.stock_number}"


def transfer_items(items: List[CachedStockItem], location: StockLocation):
    _items = []
    for item in items:
        _items.append({"pk":item.pk, "quantity": item.quantity})
        if item.quantity != item.original_quantity:
            #TODO: implement a screen that will help you deal with the stock splits
            raise NotImplementedError("Quantity other that 'ALL' not implemented (yet)")

    StockItem.adjustStockItems(api, method='transfer', items=_items, location=location.pk)

class CachedStockItemRow(CachedStockItemRowModel):
    cached_stock_item: CachedStockItem = Field(frozen=True)

    def __init__(self, cached_stock_item: CachedStockItem):
        super().__init__(
            cached_stock_item=cached_stock_item,
            stock_number=cached_stock_item.pk,
            part_name=cached_stock_item.part.name,
            quantity=cached_stock_item.quantity,
            current_location=cached_stock_item.stock_location_name
        )

    def __hash__(self):
        return hash(self.cached_stock_item)

    @classmethod
    def field_display_dict(cls):
        return {
            "stock_number": "Stock Number",
            "part_name":"Part Name",
            "quantity":"Quantity",
            "current_location":"Current Location",
            "cached_stock_item": None
        }

    def update(self, other, validate=False, allow_greater=False):
        if validate:
            oq = self.cached_stock_item.original_quantity
            if not allow_greater and other.quantity > oq:
                raise ValueError(f"Quantity is greater than the original stock quantity ({oq})")

        self.quantity = other.quantity
        self.cached_stock_item.quantity = other.quantity

        return True

    @property
    def item(self):
        return self.cached_stock_item


class CachedStockItemCheckInRowModel(RowBaseModel):
    stock_number: int = Field(frozen=True)
    part_name: str = Field(frozen=True)
    quantity: int = Field(frozen=True)
    previous_location: str = Field(frozen=True)
    new_location: str = Field(frozen=True)
    timestamp: datetime = Field(frozen=True)

    def update(self, other, validate=False):
        pass

    def title_name(self):
        return f"Stock #{self.stock_number}"

class CachedStockItemCheckInRow(CachedStockItemCheckInRowModel):
    cached_stock_item: CachedStockItem = Field(frozen=True)

    def __init__(self, cached_stock_item: CachedStockItem):
        super().__init__(
            cached_stock_item=cached_stock_item,
            stock_number=cached_stock_item.pk,
            part_name=cached_stock_item.part.name,
            quantity=cached_stock_item.quantity,
            previous_location=cached_stock_item.stock_location_name,
            new_location=cached_stock_item.default_location.name,
            timestamp=datetime.now(),
        )

    def __hash__(self):
        #allows for duplicates
        return hash(self.cached_stock_item.stock_item)

    @classmethod
    def field_display_dict(cls):
        return {
            "stock_number": "Stock#",
            "part_name":"Part Name",
            "quantity":"Q",
            "previous_location":"Prev Loc",
            "new_location":"New Loc",
            "timestamp":"Check-In Timestamp",
            "cached_stock_item": None
        }

    def update(self, other, validate=False, allow_greater=False):
        return True

    @property
    def item(self):
        return self.cached_stock_item
