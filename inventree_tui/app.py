from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Button, Static, TabPane, Tab, TabbedContent
from textual.containers import Container
from inventree_tui.api import ApiException, scanBarcode
import asyncio

class TransferItemsTab(Container):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Scan Location Barcode", id="location_input")
        yield Static("Destination: ", id="destination")
        yield Input(placeholder="Scan Items", id="item_input")
        yield Static("Item List:", id="item_list")
        yield Button("Done", id="done_button", variant="success")
        yield Button("Cancel", id="cancel_button", variant="error")

#    def on_input_changed(self, event: Input.Changed) -> None:
#        if event.input.id == "location_input":
#            self.query_one("#destination", Static).update(f"Destination: {event.value}")
#        elif event.input.id == "item_input":
#            self.query_one("#item_list", Static).update(
#                self.query_one("#item_list", Static).renderable + f"\n{event.value}"
#            )
#    def on_(self) -> None:
#        self.query_one("#transfer-items-tab").active_index = 0
    async def on_input_submitted(self, message: Input.Submitted) -> None:

        if message.input.id == "location_input":
            message.input.add_class("readonly")
            try:
                item = scanBarcode(message.input.value, ["stocklocation"])
            except ApiException as e:
                message.input.value = str(e)
                return
            message.input.remove_class("readonly")
            message.input.clear()


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "done_button":
            # Logic to transfer items to the location
            pass
        elif event.button.id == "cancel_button":
            self.query_one("#item_list", Static).update("Item List:")
            self.query_one("#destination", Static).update("Destination: ")

class CheckInItemsTab(Container):
    def compose(self) -> ComposeResult:
        yield Static("Check-In Items Tab")

class InventreeApp(App):
    CSS_PATH = "styles.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Transfer Items",id="transfer-items-tab"):
                yield TransferItemsTab()
            with TabPane("Check-In Items", id="checkin-items-tab"):
                yield CheckInItemsTab()

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#transfer-items-tab").active_index = 0

#app = InventreeApp()
#if __name__ == "__main__":
#    app = InventreeApp()
#    app.run()
