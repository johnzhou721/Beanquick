"""Account input field with autocompletion."""
from __future__ import annotations

import logging
import toga
from toga.style import Pack

logger = logging.getLogger(__name__)

class AccountField:
    """An account input field with autocompletion."""
    
    def __init__(self, placeholder="Account", on_change=None, **kwargs):
        self.on_change = on_change
        
        self.widget = toga.TextInput(
            placeholder=placeholder,
            on_change=self._on_change,
            **kwargs
        )
    
    @property
    def value(self) -> str:
        """Get the current value."""
        return self.widget.value or ""
    
    @value.setter
    def value(self, val: str):
        """Set the value."""
        self.widget.value = val or ""
    
    def _on_change(self, widget, **kwargs):
        """Handle change events."""
        if self.on_change:
            self.on_change(widget, **kwargs)
    
    def clear(self):
        """Clear the field."""
        self.widget.value = ""