from inventree.stock import StockItem, StockLocation
from inventree.part import Part
from .base import api

class CachedStockItem():

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
    def item(self) -> StockItem:
        return self._stock_item

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
    def location(self) -> StockLocation:
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

