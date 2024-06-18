from datetime import datetime
from textwrap import dedent
from inventree.stock import StockItemTracking, StockItem
from inventree.part import Part

from inventree_tui.api.base import f2i, CachedInventreeObject, api
from inventree_tui.api.stock_item import CachedStockItem
from pydantic import PrivateAttr

class CachedStockItemTracking(CachedInventreeObject[StockItemTracking]):
    
    _stock_item : CachedStockItem = PrivateAttr(default=None)

    @property
    def stock_item(self):
        if self._stock_item is None:
            self._stock_item = CachedStockItem(stock_item=StockItem(api,self.obj.item))
        return self._stock_item

    @classmethod
    def timestamp_format(cls):
        return "%Y-%m-%d %H:%M"

    def datetime(self) -> datetime:
        return datetime.strptime(self.obj.date, self.timestamp_format())

    def datetime_string(self, timestamp_format : str | None = None) -> str:
        if timestamp_format is None:
            timestamp_format = self.timestamp_format()
        return self.datetime().strftime(timestamp_format)

    def op_string(self):
        obj = self.obj

        item = f"#{obj.item}"
        if obj.deltas is not None:
            obj.deltas = f2i(obj.deltas)

        # Location Changed
        if obj.tracking_type == 20:
            s = f"moved -> {obj.deltas['location']}"
        # Remove
        elif obj.tracking_type == 12:
            removed = obj.deltas['removed']
            quantity = obj.deltas['quantity']
            s = f"{quantity+removed} - {removed} = {quantity}"
        # Add
        elif obj.tracking_type == 11:
            added = obj.deltas['added']
            quantity = obj.deltas['quantity']
            s = f"{quantity-added} + {added} = {quantity}"
        # Count
        elif obj.tracking_type == 10:
            quantity = obj.deltas['quantity']
            s = f"= {quantity}"
        # Status updated
        elif obj.tracking_type == 25:
            status = obj.deltas['status']
            s = f"status -> {status}"
        else:
            s = f"""\
                [{obj.tracking_type}] : {dict(obj)}\
            """
        return dedent(s)

    def short_label(self):
        d = {
                20: "Moved",
                12: "Removed",
                11: "Add",
                10: "Count",
                25: "Updated",
        }
        if self.obj.tracking_type in d:
            return d[self.obj.tracking_type]

        # Default to label
        return self.obj.label

    def to_string(self, date=False):
        obj = self.obj

        if date:
            header = f"[{obj.date}] {obj.label}"
        else:
            header = f"{obj.label}"

        return f"{header}: {self.op_string()}"
