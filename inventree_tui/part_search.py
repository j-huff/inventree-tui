import logging

from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import (
    Input,
    Static,
    Tree,
)

from .api import CachedStockItem
from .api.part_search import part_search, CachedPart
from .error_screen import IgnorableErrorEvent
from .status import StatusChanged

class PartSearchTree(Widget):
    def __init__(self, *args, **kwargs):
        self.part_tree = Tree("Results")
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.part_tree.root.expand()
        yield self.part_tree

    def clear(self):
        self.part_tree.reset("Results")

    def set_root_label(self, label):
        self.part_tree.root.set_label(label)

    def add_part(self, cached_part: CachedPart, expand=False):
        node = self.part_tree.root.add(cached_part.part.name, data=cached_part, allow_expand=False, expand=False)
        if expand:
            self.add_stock_items(node)
            node.allow_expand = True
            node.expand()

    def add_stock_item(self, node, stock_item: CachedStockItem):
        location = stock_item.location.name if stock_item.location else ''
        node.add(f"Stock #{stock_item.item.pk}, location: {location}, Q: {stock_item.item.quantity}",
                data=stock_item, allow_expand=False, expand=False)

    def add_stock_items(self, node):
        for stock_item in node.data.stock_items:
            self.add_stock_item(node, stock_item)

    def on_tree_node_selected(self, message: Tree.NodeSelected):
        tree = message.control
        node = message.node
        logging.info(f"NODE SELECTED {node} {node.data}")
        if isinstance(node.data, CachedPart) and len(node.children) == 0:
            self.add_stock_items(node)
            node.allow_expand = True
            node.expand()
            return



class PartSearchTab(Container):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search Parts", id="part_search_input")
        yield Static("Results",id="part_search_table_title", classes="table-title")
        yield PartSearchTree()

    async def handle_part_search_input(self, value: str):
        parts = part_search(value)

        if len(parts) == 0:
            msg = "The part search yielded no results."
            event = IgnorableErrorEvent(self, "No Parts Found", msg)
            self.post_message(event)
            self.post_message(StatusChanged(self, msg))
            return

        tree = self.query_one(PartSearchTree)
        tree.clear()

        self.post_message(StatusChanged(self, f"Search found {len(parts)} parts"))
        tree.set_root_label(f"Results: Found {len(parts)} parts")
        max_expanded = 5
        for i, part in enumerate(parts):
            tree.add_part(part, expand = i < max_expanded)


    async def on_input_submitted(self, message: Input.Submitted) -> None:
        if message.input.id == "part_search_input":
            message.input.add_class("readonly")
            await self.handle_part_search_input(message.input.value)
            message.input.remove_class("readonly")
            message.input.clear()

