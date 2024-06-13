from pydantic import BaseModel, PrivateAttr, ConfigDict

from inventree.part import Part
from inventree.stock import StockItem, StockLocation

from .base import api

class CachedStockItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    stock_item : StockItem
    _part : Part | None = PrivateAttr(default=None)
    _default_location : StockLocation | None = PrivateAttr(default=None)
    _quantity : int | float | None = PrivateAttr(default=None)
    _stock_location : StockLocation | None = PrivateAttr(default=None)

    def title_name(self):
        return f"Stock #{self.stock_item.pk}"

    @property
    def item(self) -> StockItem:
        return self.stock_item

    @property
    def part(self) -> Part:
        if self._part is None:
            self._part = self.stock_item.getPart()
        return self._part

    @property
    def default_location(self) -> StockLocation:
        default_location_pk = self.part.default_location
        if default_location_pk is None:
            return None
        return StockLocation(api, default_location_pk)

    @property
    def pk(self) -> int:
        return self.stock_item.pk

    @property
    def stock_location(self) -> StockLocation:
        if self._stock_location is None:
            self._stock_location = self.stock_item.getLocation()
        return self._stock_location

    # Alias for stock_location
    @property
    def location(self) -> StockLocation:
        return self.stock_location

    @property
    def stock_location_name(self) -> str:
        if self.stock_location is None:
            return "None"
        return self.stock_location.name

    @property
    def quantity(self):
        if self._quantity is None:
            return self.stock_item.quantity
        return self._quantity

    @quantity.setter
    def quantity(self, q):
        self._quantity = q

    @property
    def original_quantity(self):
        return self.stock_item.quantity

    def __hash__(self):
        return hash(self.stock_item.pk)

    def __eq__(self, other):
        if isinstance(other, CachedStockItem):
            return self.stock_item.pk == self.stock_item.pk
        return False
