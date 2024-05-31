from typing import List
from inventree.stock import StockItem, StockLocation
from requests.exceptions import RequestException
from inventree.part import Part
import os
import json
from dotenv import load_dotenv
from inventree.api import InvenTreeAPI
load_dotenv()

host = os.environ.get("INVENTREE_API_HOST")
token = os.environ.get("INVENTREE_API_TOKEN")
api = InvenTreeAPI(host=host, token=token)

class ApiException(Exception):
    pass

class CachedStockItem():
    def __init__(self, stock_item: StockItem):
        self.stock_item = stock_item
        self._part = None
        self._default_location = None
        self._quantity = None
        self._stock_location = None
        self.destination = None

    def transfer(self, destination=None):
        if destination is not None:
            self.destination = destination
        if self.destination is None:
            raise Exception("Cannot transfer, no destination")
        transfer_items([self], self.destination)

    @property
    def part(self) -> Part:
        if self._part == None:
            self._part = self.stock_item.getPart()
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
            self._stock_location = self.stock_item.getLocation()
        return self._stock_location

    @property
    def quantity(self):
        if self._quantity is None:
            return self.stock_item.quantity
        return self._quantity

def transfer_items(items: List[CachedStockItem], location: StockLocation):
    _items = []
    for item in items:
        _items.append({"pk":item.stock_item.pk, "quantity": item.quantity})
        if item.quantity != item.stock_item.quantity:
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

def scanBarcode(text, whitelist=None) -> CachedStockItem:
    try:
        item = api.scanBarcode(text)

        if item_in_whitelist(item, whitelist):
            return CachedStockItem(item)
        else:
            raise ApiException(f"Item found but not in whitelist: {item}")

    except RequestException as e:
        if e.response is not None:
            raise ApiException(f"{e.response.status_code}")
        else:
            body = json.loads(e.args[0]['body'])
            raise ApiException(f"{body['error']}")
    return item

