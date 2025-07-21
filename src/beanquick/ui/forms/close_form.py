"""Close directive form implementation."""
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

class CloseForm(BaseDirectiveForm, MacOSTabChainMixin, FormValidationMixin):
    """Form for creating Close directives."""
    
    def __init__(self, on_change=None, account_completer=None, completion_timers=None, app=None, **kwargs):
        super().__init__(on_change)
        self.account_completer = account_completer
        self.completion_timers = completion_timers or {}
        self.app = app
        self._setup_close_fields()

    def _setup_close_fields(self):
        """Set up close-specific fields."""
        self.account_field = AutocompleteAccountField(
            placeholder="Account",
            on_change=self._on_field_change,
            account_completer=self.account_completer,
            completion_timers=self.completion_timers,
            app=self.app,
            style=Pack(flex=2, margin_left=WIDGET_SPACING),
        )
        
        # Store references
        self._widgets.update({
            "account": self.account_field.widget,
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
        """Build dictionary for Close serialization."""
        return {
            "t": "Close",
            "meta": {},
            "date": self.get_date_value(),
            "account": self.account_field.value.strip(),
        }

    def clear_form(self):
        """Clear all form data."""
        self.clear_common_fields()
        self.account_field.clear()
    
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
                not self.account_field.value.strip())
