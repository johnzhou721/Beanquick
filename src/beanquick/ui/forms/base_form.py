"""Base form interface and common functionality."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List

import toga
from toga.style import Pack

from beanquick.ui.components.date_field import DateField

logger = logging.getLogger(__name__)

class DirectiveFormInterface(ABC):
    """Interface for directive-specific forms."""
    
    @abstractmethod
    def build_directive_dict(self) -> Dict[str, Any]:
        """Build dictionary for serialization."""
        pass
        
    @abstractmethod
    def clear_form(self):
        """Clear all form data."""
        pass
        
    @abstractmethod
    def is_form_valid(self) -> bool:
        """Check if form data is valid."""
        pass
        
    @abstractmethod
    def get_form_errors(self) -> List[str]:
        """Get validation errors."""
        pass
    
    @abstractmethod
    def is_form_empty(self) -> bool:
        """Check if form is empty."""
        pass

    @abstractmethod
    def create_form_widget(self) -> toga.Widget:
        """Create the form widget."""
        pass

class BaseDirectiveForm(DirectiveFormInterface):
    """Base form with common directive fields."""
    
    def __init__(self, on_change=None):
        self.on_change = on_change
        self._widgets = {}
        self._setup_common_fields()
    
    def _setup_common_fields(self):
        """Set up fields common to all directives (date, meta)."""
        self.date_field = DateField(
            style=Pack(flex=1),
            placeholder="Date",
            on_change=self._on_field_change
        )
        
        # Store reference for easy access
        self._widgets["date"] = self.date_field.widget
    
    def _on_field_change(self, widget, **kwargs):
        """Handle field changes."""
        if self.on_change:
            self.on_change(widget, **kwargs)
    
    def get_date_value(self) -> str:
        """Get the date value."""
        return self.date_field.widget.value.strip()
    
    def clear_common_fields(self):
        """Clear common fields."""
        self.date_field.clear()
    
    def is_common_fields_empty(self) -> bool:
        """Check if common fields are empty."""
        return not self.get_date_value()
    
    def focus_first_input(self):
        """Focus the first input field."""
        self.date_field.widget.focus()