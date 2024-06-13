from typing import List

from inventree.part import Part
from inventree.stock import StockItem

from .base import api
from .stock_item import CachedStockItem


class CachedPart(): # pylint: disable=too-few-public-methods
    def __init__(self, part: Part):
        self.part = part
        self._stock_items : List[CachedStockItem] | None = None

    @property
    def stock_items(self) -> List[CachedStockItem]:
        if self._stock_items is None:
            stock_items = StockItem.list(api, part=self.part.pk)
            self._stock_items = [CachedStockItem(stock_item=item) for item in stock_items]
        return self._stock_items

def part_search(search_term="") -> List[CachedPart]:
    parts = Part.list(api, search=search_term)
    return [CachedPart(p) for p in parts]
