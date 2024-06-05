from dotenv import load_dotenv
import os
from inventree.api import InvenTreeAPI
load_dotenv()
host = os.environ.get("INVENTREE_API_HOST")
token = os.environ.get("INVENTREE_API_TOKEN")
api = InvenTreeAPI(host=host, token=token)
