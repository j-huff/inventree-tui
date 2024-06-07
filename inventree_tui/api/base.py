import os

from dotenv import load_dotenv
from inventree.api import InvenTreeAPI

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
        error_msg("InvenTree API token", "INVENTREE_API_TOKEN", "inv-f0e03dc3a7e0a6421ffba5d219858f52a85da3ca-20240607")
    exit(1)

api = InvenTreeAPI(host=host, token=token)
