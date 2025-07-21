"""Pad directive form implementation."""
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

class PadForm(BaseDirectiveForm, MacOSTabChainMixin, FormValidationMixin):
    """Form for creating Pad directives."""
    
    def __init__(self, on_change=None, account_completer=None, completion_timers=None, app=None, **kwargs):
        super().__init__(on_change)
        self.account_completer = account_completer
        self.completion_timers = completion_timers or {}
        self.app = app
        self._setup_pad_fields()

    def _setup_pad_fields(self):
        """Set up pad-specific fields."""
        self.account_field = AutocompleteAccountField(
            placeholder="Account to pad",
            on_change=self._on_field_change,
            on_confirm=self._on_account_confirm,
            account_completer=self.account_completer,
            completion_timers=self.completion_timers,
            app=self.app,
            style=Pack(flex=2, margin=(0, WIDGET_SPACING)),
        )
        
        self.source_account_field = AutocompleteAccountField(
            placeholder="Source account",
            on_change=self._on_field_change,
            account_completer=self.account_completer,
            completion_timers=self.completion_timers,
            app=self.app,
            style=Pack(flex=2),
        )
        
        # Store references
        self._widgets.update({
            "account": self.account_field.widget,
            "source_account": self.source_account_field.widget,
        })

        # Fix macOS tab chain using the mixin
        text_inputs = get_text_input_widgets_from_dict(self._widgets)
        self.fix_macos_tab_chain(text_inputs)

    def _on_account_confirm(self, widget: toga.Widget):
        """Handle account confirmation."""
        self.source_account_field.focus()

    def create_form_widget(self) -> toga.Widget:
        """Create the main form widget."""
        
        # Create the main fields row
        main_row = toga.Box(
            style=Pack(direction=ROW, margin_bottom=10),
            children=[
                self.date_field.widget,
                self.account_field.widget,
                self.source_account_field.widget,
            ]
        )

        form_box = toga.Box(
            style=Pack(direction=COLUMN, margin=WIDGET_SPACING),
            children=[
                main_row,
            ]
        )

        # Set up the account fields' suggestion popups
        self.account_field.setup_in_container(form_box)
        self.source_account_field.setup_in_container(form_box)
        
        # Wrap in scroll container for consistency
        scroll_container = toga.ScrollContainer(
            horizontal=False,
            vertical=True,
            content=form_box,
            style=Pack(flex=1),
        )
        
        return scroll_container
    
    def build_directive_dict(self) -> Dict[str, Any]:
        """Build dictionary for Pad serialization."""
        return {
            "t": "Pad",
            "meta": {},
            "date": self.get_date_value(),
            "account": self.account_field.value.strip(),
            "source_account": self.source_account_field.value.strip(),
        }

    def clear_form(self):
        """Clear all form data."""
        self.clear_common_fields()
        self.account_field.clear()
        self.source_account_field.clear()
    
    def is_form_valid(self) -> bool:
        """Check if form data is valid."""
        errors = self.get_form_errors()
        return len(errors) == 0
    
    def get_form_errors(self) -> List[str]:
        """Get validation errors."""
        errors = []
        
        self.validate_date_field(self.get_date_value(), errors)
        self.validate_required_field(self.account_field.value, "Account", errors)
        self.validate_required_field(self.source_account_field.value, "Source account", errors)
        
        # Additional validation to ensure accounts are different
        account = self.account_field.value.strip()
        source_account = self.source_account_field.value.strip()
        if account and source_account and account == source_account:
            errors.append("Account and source account must be different")
        
        return errors
    
    def is_form_empty(self) -> bool:
        """Check if form is empty."""
        return (self.is_common_fields_empty() and 
                not self.account_field.value.strip() and 
                not self.source_account_field.value.strip())
