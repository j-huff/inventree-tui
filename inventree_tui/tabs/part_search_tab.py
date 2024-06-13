from textual import work
from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import (
    Input,
    Static,
    Tree,
)

from inventree_tui.api import CachedStockItem
from inventree_tui.api.part_search import part_search, CachedPart
from inventree_tui.error_screen import IgnorableErrorEvent
from inventree_tui.status import StatusChanged

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
        node = self.part_tree.root.add(
            cached_part.part.name,
            data=cached_part,
            allow_expand=False,
            expand=False,
        )
        if expand:
            self.expand_part_node(node)
        return node

    def add_stock_item(self, node, stock_item: CachedStockItem):
        location = stock_item.location.name if stock_item.location else ''
        node.add(f"""\
Stock #{stock_item.item.pk}, location: {location}, Q: {stock_item.item.quantity}""",
                data=stock_item, allow_expand=False, expand=False)

    @work(exclusive=False, thread=True)
    async def expand_part_node(self, node):
        self.add_stock_items(node)
        node.allow_expand = True
        node.expand()

    def add_stock_items(self, node):
        s = node.label
        node.label = f"{s} - Loading..."
        for stock_item in node.data.stock_items:
            self.add_stock_item(node, stock_item)
        node.label = s

    def on_tree_node_selected(self, message: Tree.NodeSelected):
        node = message.node
        if isinstance(node.data, CachedPart) and len(node.children) == 0:
            self.expand_part_node(node)

class PartSearchTab(Container):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search Parts", id="part_search_input")
        yield Static("Results", id="part_search_table_title", classes="table-title")
        yield PartSearchTree()

    @work(exclusive=True, thread=True)
    async def handle_part_search_input(self, value: str):
        tree = self.query_one(PartSearchTree)
        tree.clear()
        tree.set_root_label("Searching...")

        parts = part_search(value)
        tree.set_root_label(f"Results: Found {len(parts)} parts")

        if len(parts) == 0:
            msg = "The part search yielded no results."
            event = IgnorableErrorEvent(self, "No Parts Found", msg)
            self.post_message(event)
            self.post_message(StatusChanged(self, msg))
            return

        self.post_message(StatusChanged(self, f"Search found {len(parts)} parts"))
        #TODO: make this configurable
        max_expanded = 5
        for i, part in enumerate(parts):
            tree.add_part(part, expand = i < max_expanded)

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        if message.input.id == "part_search_input":
            self.handle_part_search_input(message.input.value)
            message.input.clear()
