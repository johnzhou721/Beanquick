"""Balance directive form implementation."""
from __future__ import annotations

import logging
from typing import Dict, Any, List

import toga
from toga.style import Pack
from toga.style.pack import ROW, COLUMN  # type: ignore

from beanquick.ui.forms.base_form import BaseDirectiveForm
from beanquick.ui.components.account_field import AccountField
from beanquick.ui.components.amount_field import AmountField
from beanquick.ui.suggestion_popup import SuggestionPopup


logger = logging.getLogger(__name__)

WIDGET_SPACING = 5

class BalanceForm(BaseDirectiveForm):
    """Form for creating Balance directives."""
    
    def __init__(self, on_change=None, account_completer=None, completion_timers=None, app=None, **kwargs):
        super().__init__(on_change)
        self.account_completer = account_completer
        self.completion_timers = completion_timers or {}
        self._setting_suggestion: bool = False
        self.app = app
        self._setup_balance_fields()

    def _setup_balance_fields(self):
        """Set up balance-specific fields."""
        self.account_field = AccountField(
            placeholder="Account",
            on_change=self._on_account_input_change,
            on_lose_focus=self._on_account_input_lose_focus,
            on_confirm=self._on_account_input_confirm,
            style=Pack(flex=2),
        )
        
        self.amount_field = AmountField(
            placeholder="Amount",
            on_change=self._on_field_change,
            style=Pack(flex=1),
        )
        
        # Store references
        self._widgets.update({
            "account": self.account_field.widget,
            "amount": self.amount_field.widget,
        })

        self._fix_macos_tab_chain()

    def create_form_widget(self) -> toga.Widget:
        """Create the main form widget."""
        
        # Create the main fields
        date_row = toga.Box(
            style=Pack(direction=ROW, margin_bottom=10),
            children=[
                self.date_field.widget,
                self.account_field.widget,
                self.amount_field.widget,
            ]
        )

        form_box = toga.Box(
            style=Pack(direction=COLUMN, margin=WIDGET_SPACING),
            children=[
                date_row,
            ]
        )

        # Create suggestion popup for this account input
        self.suggestion_popup = SuggestionPopup(
            form_box,
            lambda selected: self._on_suggestion_selected(self.account_field.widget, selected)
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
        """Build dictionary for Balance serialization."""

        return {
            "t": "Balance",
            "meta": {},
            "date": self.get_date_value(),
            "account": self.account_field.widget.value.strip(),
            "amount": self.amount_field.widget.value.strip(),
        }

    def clear_form(self):
        """Clear all form data."""
        self.clear_common_fields()
        self.account_field.clear()
        self.amount_field.clear()
    
    def is_form_valid(self) -> bool:
        """Check if form data is valid."""
        errors = self.get_form_errors()
        return len(errors) == 0
    
    def get_form_errors(self) -> List[str]:
        """Get validation errors."""
        errors = []
        
        if not self.get_date_value():
            errors.append("Date is required")
        
        if not self.account_field.value.strip():
            errors.append("Account is required")
        
        if not self.amount_field.value.strip():
            errors.append("Amount is required")
        
        return errors
    
    def is_form_empty(self) -> bool:
        """Check if form is empty."""
        return (self.is_common_fields_empty() and 
                not self.account_field.value.strip() and 
                not self.amount_field.value.strip())
    
    def _on_account_input_change(self, widget, **kwargs):
        """Handle account input changes for autocompletion."""
        # First call the regular change handler
        self._on_field_change(widget, **kwargs)

        if self._setting_suggestion:
            return
        
        # Check for special navigation characters (if keyboard events aren't available)
        value = widget.value
        if value and len(value) > 0:
            last_char = value[-1]
            
            if self.suggestion_popup.is_visible:
                # Handle special navigation (this is a fallback approach)
                if last_char == ',':  # Comma key
                    self._setting_suggestion = True
                    try:
                        # Remove the comma character
                        widget.value = value[:-1]
                        self.suggestion_popup.navigate_up()
                    finally:
                        self._setting_suggestion = False
                    return
                
                if last_char == '.':  # Period key
                    self._setting_suggestion = True
                    try:
                        # Remove the period character
                        widget.value = value[:-1]
                        self.suggestion_popup.navigate_down()
                    finally:
                        self._setting_suggestion = False
                    return

                if last_char == ' ':  # Space key
                    self._setting_suggestion = True
                    try:
                        # Remove the space character
                        widget.value = value[:-1]
                        self.suggestion_popup.select_current()
                    finally:
                        self._setting_suggestion = False
                    return

        # Handle autocompletion with debouncing
        self._debounced_account_completion(widget)
    
    def _debounced_account_completion(self, widget: toga.TextInput):
        """Handle debounced account completion."""
        # Create a unique key for this widget's completion timer
        widget_id = id(widget)
        
        # Cancel any existing timer for this widget
        if widget_id in self.completion_timers and self.completion_timers[widget_id]:
            self.completion_timers[widget_id].cancel()
        
        # Start new debounced timer
        # schedule_delayed_callback
        self.completion_timers[widget_id] = self.app.loop.call_later(
            0.3,  # 300ms delay
            lambda: self._debounced_account_completion_handler(widget)
        )
    
    def _debounced_account_completion_handler(self, widget):
        """Actual completion handling logic after debouncing."""
        try:
            # Get the query and find the suggestion popup
            query = widget.value
            
            if not query or not query.strip():
                self.suggestion_popup.hide()
                return
            
            # Get suggestions directly (no async needed)
            if self.account_completer:
                suggestions = self.account_completer.get_suggestions(query.strip())
                if suggestions:
                    # Scroll to bring the current input to the top, accounting for popup space
                    self.suggestion_popup.show_suggestions(suggestions)
                else:
                    self.suggestion_popup.hide()

        except Exception as e:
            logger.debug(f"Error in debounced completion: {e}")

    def _on_suggestion_selected(self, account_input: toga.TextInput, selected_account: str):
        """Handle suggestion selection."""
        self._setting_suggestion = True
        try:
            account_input.value = selected_account
            self._on_field_change(account_input)
        finally:
            self._setting_suggestion = False
        
        # Try to focus the amount input for this line
        self.amount_field.widget.focus()
    
    def _fix_macos_tab_chain(self):
        """Fix tab navigation chain on macOS for dynamically added TextInputs."""
        try:
            import sys
            if sys.platform != "darwin":
                return
                
            from toga_cocoa.libs import appkit
            from rubicon.objc import ObjCClass
            
            # Get all TextInput widgets in order
            text_inputs = []
            
            # Add main form inputs
            text_inputs.append(self._widgets["date"])
            text_inputs.append(self._widgets["account"])
            text_inputs.append(self._widgets["amount"])

            # Get native NSTextField objects
            native_fields = []
            for text_input in text_inputs:
                try:
                    if hasattr(text_input, '_impl') and hasattr(text_input._impl, 'native'):
                        native_field = text_input._impl.native
                        if native_field:
                            native_fields.append(native_field)
                except Exception as e:
                    logger.debug(f"Could not get native field for TextInput: {e}")
                    continue
            
            # Rebuild the responder chain
            if len(native_fields) > 1:
                for i in range(len(native_fields)):
                    current_field = native_fields[i]
                    next_field = native_fields[(i + 1) % len(native_fields)]  # Loop back to first
                    
                    try:
                        # Set the next key view (tab order)
                        current_field.setNextKeyView_(next_field)
                    except Exception as e:
                        logger.debug(f"Could not set next key view: {e}")
            
            logger.debug(f"Updated macOS tab chain for {len(native_fields)} text fields")
            
        except Exception as e:
            logger.debug(f"Error fixing macOS tab chain: {e}")

    def _on_account_input_lose_focus(self, widget):
        """Handle account input losing focus."""
        self.suggestion_popup.hide()

    def _on_account_input_confirm(self, widget):
        """Handle account input confirmation."""
        self.suggestion_popup.select_current()