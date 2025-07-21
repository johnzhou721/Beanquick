"""Event directive form implementation."""
from __future__ import annotations

import logging
from typing import Dict, Any, List

import toga
from toga.style import Pack
from toga.style.pack import ROW, COLUMN  # type: ignore

from beanquick.ui.forms.base_form import BaseDirectiveForm
from beanquick.ui.forms.form_utils import MacOSTabChainMixin, FormValidationMixin, get_text_input_widgets_from_dict


logger = logging.getLogger(__name__)

WIDGET_SPACING = 5

class EventForm(BaseDirectiveForm, MacOSTabChainMixin, FormValidationMixin):
    """Form for creating Event directives."""
    
    def __init__(self, on_change=None, **kwargs):
        super().__init__(on_change)
        self._setup_event_fields()

    def _setup_event_fields(self):
        """Set up event-specific fields."""
        self.type_field = toga.TextInput(
            placeholder="Event type",
            on_change=self._on_field_change,
            style=Pack(flex=1, margin=(0, WIDGET_SPACING)),
        )
        
        self.description_field = toga.TextInput(
            placeholder="Event description",
            on_change=self._on_field_change,
            style=Pack(flex=2),
        )
        
        # Store references
        self._widgets.update({
            "type": self.type_field,
            "description": self.description_field,
        })

        # Fix macOS tab chain using the mixin
        text_inputs = get_text_input_widgets_from_dict(self._widgets)
        self.fix_macos_tab_chain(text_inputs)

    def create_form_widget(self) -> toga.Widget:
        """Create the main form widget."""
        
        # Create the main fields row
        main_row = toga.Box(
            style=Pack(direction=ROW, margin_bottom=10),
            children=[
                self.date_field.widget,
                self.type_field,
                self.description_field,
            ]
        )

        form_box = toga.Box(
            style=Pack(direction=COLUMN, margin=WIDGET_SPACING),
            children=[
                main_row,
            ]
        )
        
        # Wrap in scroll container for consistency
        scroll_container = toga.ScrollContainer(
            horizontal=False,
            vertical=True,
            content=form_box,
            style=Pack(flex=1),
        )
        
        return scroll_container
    
    def build_directive_dict(self) -> Dict[str, Any]:
        """Build dictionary for Event serialization."""
        return {
            "t": "Event",
            "meta": {},
            "date": self.get_date_value(),
            "type": self.type_field.value.strip(),
            "description": self.description_field.value.strip(),
        }

    def clear_form(self):
        """Clear all form data."""
        self.clear_common_fields()
        self.type_field.value = ""
        self.description_field.value = ""
    
    def is_form_valid(self) -> bool:
        """Check if form data is valid."""
        errors = self.get_form_errors()
        return len(errors) == 0
    
    def get_form_errors(self) -> List[str]:
        """Get validation errors."""
        errors = []
        
        self.validate_date_field(self.get_date_value(), errors)
        self.validate_required_field(self.type_field.value, "Event type", errors)
        self.validate_required_field(self.description_field.value, "Description", errors)
        
        return errors
    
    def is_form_empty(self) -> bool:
        """Check if form is empty."""
        return (self.is_common_fields_empty() and 
                not self.type_field.value.strip() and 
                not self.description_field.value.strip())
