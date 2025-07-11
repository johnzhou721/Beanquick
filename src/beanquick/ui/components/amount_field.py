"""Amount input field with currency handling."""
from __future__ import annotations

import re
import logging
import toga
from toga.style import Pack

logger = logging.getLogger(__name__)

class AmountField:
    """An amount input field with currency formatting."""
    
    def __init__(self, placeholder="Amount", on_change=None, **kwargs):
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
    
    def format_with_currency(self, default_currency: str) -> str:
        """Format amount text by adding default currency if it's just a number."""
        amount_text = self.value.strip()
        if not amount_text or not default_currency:
            return amount_text
        
        # Check if the amount is just a number (positive or negative)
        if re.match(r'^-?\d+(\.\d+)?$', amount_text):
            return f"{amount_text} {default_currency}"
        
        return amount_text
    
    def clear(self):
        """Clear the field."""
        self.widget.value = ""