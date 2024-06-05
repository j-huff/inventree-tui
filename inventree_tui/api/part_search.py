from .base import api
from inventree.part import Part
from inventree.stock import StockItem
from typing import List
from .stock_item import CachedStockItem

class CachedPart():

    def __init__(self, part: Part):
        self.part = part
        self._stock_items = None

    @property
    def stock_items(self) -> List[CachedStockItem]:
        if self._stock_items is None:
            stock_items = StockItem.list(api, part=self.part.pk)
            self._stock_items = [CachedStockItem(item) for item in stock_items]
        return self._stock_items

def part_search(search_term="") -> List[CachedPart]:
    parts = Part.list(api, search=search_term)
    return [CachedPart(p) for p in parts]
