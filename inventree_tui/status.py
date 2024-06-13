from dataclasses import dataclass
from textual.widget import Widget
from textual.app import App
from textual.events import Event

@dataclass
class StatusChanged(Event):
    source: Widget | App
    value: str

    @property
    def control(self) -> Widget | App:
        """Alias for self.source."""
        return self.source
