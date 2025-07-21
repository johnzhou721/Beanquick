"""Commodity directive form implementation."""
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

class CommodityForm(BaseDirectiveForm, MacOSTabChainMixin, FormValidationMixin):
    """Form for creating Commodity directives."""
    
    def __init__(self, on_change=None, **kwargs):
        super().__init__(on_change)
        self._setup_commodity_fields()

    def _setup_commodity_fields(self):
        """Set up commodity-specific fields."""
        self.currency_field = toga.TextInput(
            placeholder="Currency (e.g., USD, EUR, BTC)",
            on_change=self._on_field_change,
            style=Pack(flex=1, margin_left=WIDGET_SPACING),
        )
        
        # Store references
        self._widgets.update({
            "currency": self.currency_field,
        })

        # Fix macOS tab chain using the mixin
        text_inputs = get_text_input_widgets_from_dict(self._widgets)
        self.fix_macos_tab_chain(text_inputs)

    def create_form_widget(self) -> toga.Widget:
        """Create the main form widget."""
        
        # Create the main fields
        date_row = toga.Box(
            style=Pack(direction=ROW, margin_bottom=10),
            children=[
                self.date_field.widget,
                self.currency_field,
            ]
        )

        form_box = toga.Box(
            style=Pack(direction=COLUMN, margin=WIDGET_SPACING),
            children=[
                date_row,
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
        """Build dictionary for Commodity serialization."""
        return {
            "t": "Commodity",
            "meta": {},
            "date": self.get_date_value(),
            "currency": self.currency_field.value.strip(),
        }

    def clear_form(self):
        """Clear all form data."""
        self.clear_common_fields()
        self.currency_field.value = ""
    
    def is_form_valid(self) -> bool:
        """Check if form data is valid."""
        errors = self.get_form_errors()
        return len(errors) == 0
    
    def get_form_errors(self) -> List[str]:
        """Get validation errors."""
        errors = []
        
        self.validate_date_field(self.get_date_value(), errors)
        self.validate_required_field(self.currency_field.value, "Currency", errors)
        
        # Additional validation for currency format
        currency = self.currency_field.value.strip()
        if currency:
            # Basic validation - currency should be uppercase letters/numbers
            if not currency.replace("-", "").replace(".", "").isalnum():
                errors.append("Currency should contain only letters, numbers, hyphens, and dots")
            elif len(currency) < 2 or len(currency) > 10:
                errors.append("Currency should be between 2 and 10 characters")
        
        return errors
    
    def is_form_empty(self) -> bool:
        """Check if form is empty."""
        return (self.is_common_fields_empty() and 
                not self.currency_field.value.strip())