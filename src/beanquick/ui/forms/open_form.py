"""Open directive form implementation."""
from __future__ import annotations

import logging
from typing import Dict, Any, List

import toga
from toga.style import Pack
from toga.style.pack import ROW, COLUMN  # type: ignore

from beanquick.ui.forms.base_form import BaseDirectiveForm
from beanquick.ui.components.autocomplete_account_field import AutocompleteAccountField
from beanquick.ui.forms.form_utils import MacOSTabChainMixin, FormValidationMixin, get_text_input_widgets_from_dict


logger = logging.getLogger(__name__)

WIDGET_SPACING = 5

class OpenForm(BaseDirectiveForm, MacOSTabChainMixin, FormValidationMixin):
    """Form for creating Open directives."""
    
    def __init__(self, on_change=None, account_completer=None, completion_timers=None, app=None, **kwargs):
        super().__init__(on_change)
        self.account_completer = account_completer
        self.completion_timers = completion_timers or {}
        self.app = app
        self._setup_open_fields()

    def _setup_open_fields(self):
        """Set up open-specific fields."""
        self.account_field = AutocompleteAccountField(
            placeholder="Account",
            on_change=self._on_field_change,
            account_completer=self.account_completer,
            completion_timers=self.completion_timers,
            app=self.app,
            style=Pack(flex=2, margin=(0, WIDGET_SPACING)),
        )
        
        self.commodities_field = toga.TextInput(
            placeholder="Commodities (optional)",
            style=Pack(flex=1),
            on_change=self._on_field_change,
        )
        
        # Store references
        self._widgets.update({
            "account": self.account_field.widget,
            "commodities": self.commodities_field,
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
                self.account_field.widget,
                self.commodities_field,
            ]
        )

        form_box = toga.Box(
            style=Pack(direction=COLUMN, margin=WIDGET_SPACING),
            children=[
                date_row,
            ]
        )

        # Set up the account field's suggestion popup
        self.account_field.setup_in_container(form_box)
        
        # Wrap in scroll container for consistency
        scroll_container = toga.ScrollContainer(
            horizontal=False,
            vertical=True,
            content=form_box,
            style=Pack(flex=1),
        )
        
        return scroll_container
    
    def build_directive_dict(self) -> Dict[str, Any]:
        """Build dictionary for Open serialization."""
        commodities_value = self.commodities_field.value.strip()
        commodities = []
        
        if commodities_value:
            # Parse comma-separated commodities
            commodities = [c.strip() for c in commodities_value.split(',') if c.strip()]

        return {
            "t": "Open",
            "meta": {},
            "date": self.get_date_value(),
            "account": self.account_field.value.strip(),
            "commodities": commodities,
        }

    def clear_form(self):
        """Clear all form data."""
        self.clear_common_fields()
        self.account_field.clear()
        self.commodities_field.value = ""
    
    def is_form_valid(self) -> bool:
        """Check if form data is valid."""
        errors = self.get_form_errors()
        return len(errors) == 0
    
    def get_form_errors(self) -> List[str]:
        """Get validation errors."""
        errors = []
        
        self.validate_date_field(self.get_date_value(), errors)
        self.validate_required_field(self.account_field.value, "Account", errors)
        
        return errors
    
    def is_form_empty(self) -> bool:
        """Check if form is empty."""
        return (self.is_common_fields_empty() and 
                not self.account_field.value.strip() and 
                not self.commodities_field.value.strip())
