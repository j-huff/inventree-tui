import os
import sys

from typing import Generic, TypeVar, Type
from dotenv import load_dotenv
from inventree.api import InvenTreeAPI
from inventree.base import InventreeObject
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

class ApiException(Exception):
    def __init__(self, message, status_code=None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message} (Status Code: {self.status_code})'

load_dotenv()
host = os.environ.get("INVENTREE_API_HOST")
token = os.environ.get("INVENTREE_API_TOKEN")

def error_msg(name, envname, sample):
    print(f"{name} not set - set `{envname}` to fix this\nExample: `export {envname}={sample}`\n")

if not host or not token:
    print("Missing configuration\n")

    if not host:
        error_msg("InvenTree API host", "INVENTREE_API_HOST", "https://inventree.localhost")

    if not token:
        error_msg("InvenTree API token",
            "INVENTREE_API_TOKEN",
            "inv-f0e03dc3a7e0a6421ffba5d219858f52a85da3ca-20240607"
        )

    sys.exit(1)

api = InvenTreeAPI(host=host, token=token)

T = TypeVar('T', bound=InventreeObject)
class CachedInventreeObject(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    obj : T = Field(frozen=True)
    _base_class : Type[T] = PrivateAttr(default=T)

    @classmethod
    def base_class(cls):
        return cls.model_fields["obj"].annotation

    @classmethod
    def list(cls, api, **kwargs):
        l = cls.base_class().list(api, **kwargs)
        return [cls(obj=i) for i in l]

# Converts whole number floats to ints
# If a dict is given, it will convert all items in the dict
def f2i(obj):
    if isinstance(obj, dict):
        return {key : f2i(val) for key,val in obj.items()}
    elif isinstance(obj, float) and obj.is_integer():
        return int(obj)
    else:
        return obj
