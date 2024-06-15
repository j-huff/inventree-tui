from datetime import datetime
from textwrap import dedent
from inventree.stock import StockItemTracking

from inventree_tui.api.base import f2i, CachedInventreeObject

class CachedStockItemTracking(CachedInventreeObject[StockItemTracking]):

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

    def to_string(self, date=False):
        obj = self.obj

        if date:
            header = f"[{obj.date}] {obj.label}"
        else:
            header = f"{obj.label}"

        return f"{header}: {self.op_string()}"
