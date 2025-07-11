"""Date input field with smart parsing."""
from __future__ import annotations

import logging
import toga
from toga.style import Pack

from beanquick.util.date import smart_parse_date, local_today

logger = logging.getLogger(__name__)

class DateField:
    """A date input field with smart parsing capabilities."""
    
    def __init__(self, placeholder="Date", on_change=None, **kwargs):
        self.on_change = on_change
        
        self.widget = toga.TextInput(
            placeholder=placeholder,
            on_confirm=self._handle_date_input,
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
    
    def _handle_date_input(self, widget, **kwargs):
        """Handle the date input confirmation with smart parsing."""
        value = widget.value
        if not value:
            widget.value = local_today().strftime('%Y-%m-%d')
            return
            
        parsed_date = smart_parse_date(value)
        if parsed_date:
            # Format as ISO date and update the field
            formatted_date = parsed_date.strftime('%Y-%m-%d')
            if formatted_date != value:
                widget.value = formatted_date
                logger.debug(f"Auto-formatted date from '{value}' to '{formatted_date}'")
        else:
            logger.warning(f"Could not parse date: '{value}'")
        
        # Trigger change handler
        self._on_change(widget)
    
    def _on_change(self, widget, **kwargs):
        """Handle change events."""
        if self.on_change:
            self.on_change(widget, **kwargs)
    
    def clear(self):
        """Clear the field."""
        self.widget.value = ""