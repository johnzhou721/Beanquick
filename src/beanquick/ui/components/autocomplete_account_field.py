"""Enhanced account field with built-in autocompletion and suggestion popup."""
from __future__ import annotations

import logging
import sys
from typing import Callable, Optional, Dict, Any

import toga
from toga.style import Pack

from beanquick.ui.suggestion_popup import SuggestionPopup

logger = logging.getLogger(__name__)


class AutocompleteAccountField:
    """An account input field with built-in autocompletion and suggestion popup."""
    
    def __init__(
        self, 
        placeholder: str = "Account",
        on_change: Optional[Callable] = None,
        on_lose_focus: Optional[Callable] = None,
        on_confirm: Optional[Callable] = None,
        on_gain_focus: Optional[Callable] = None,
        on_scroll_request: Optional[Callable] = None,
        account_completer=None,
        completion_timers: Optional[Dict] = None,
        app=None,
        **kwargs
    ):
        self.on_change = on_change
        self.on_lose_focus = on_lose_focus
        self.on_confirm = on_confirm
        self.on_gain_focus = on_gain_focus
        self.on_scroll_request = on_scroll_request
        self.account_completer = account_completer
        self.completion_timers = completion_timers or {}
        self.app = app
        self._setting_suggestion = False
        
        # Create the text input widget
        self.widget = toga.TextInput(
            placeholder=placeholder,
            on_change=self._on_account_input_change,
            on_lose_focus=self._on_account_input_lose_focus,
            on_confirm=self._on_account_input_confirm,
            on_gain_focus=self._on_account_input_gain_focus,
            **kwargs
        )
        
        # Container for the field and its popup
        self.container = None
        self.suggestion_popup = None
    
    def setup_in_container(self, parent_container: toga.Box):
        """Set up the field within a parent container to enable suggestion popup."""
        self.container = parent_container
        self.suggestion_popup = SuggestionPopup(
            parent_container,
            lambda selected: self._on_suggestion_selected(selected)
        )
    
    @property
    def value(self) -> str:
        """Get the current value."""
        return self.widget.value or ""
    
    @value.setter
    def value(self, val: str):
        """Set the value programmatically without triggering autocompletion."""
        self._setting_suggestion = True
        try:
            self.widget.value = val or ""
        finally:
            self._setting_suggestion = False
    
    def clear(self):
        """Clear the field."""
        self.widget.value = ""
        if self.suggestion_popup:
            self.suggestion_popup.hide()
    
    def focus(self):
        """Focus the input widget."""
        self.widget.focus()
    
    def _on_account_input_change(self, widget, **kwargs):
        """Handle account input changes for autocompletion."""
        # First call the user's change handler
        if self.on_change:
            self.on_change(widget, **kwargs)

        if self._setting_suggestion:
            return
        
        # Check for special navigation characters (if keyboard events aren't available)
        value = widget.value
        if value and len(value) > 0 and self.suggestion_popup:
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
        if not self.account_completer or not self.suggestion_popup:
            return
            
        # Create a unique key for this widget's completion timer
        widget_id = id(widget)
        
        # Cancel any existing timer for this widget
        if widget_id in self.completion_timers and self.completion_timers[widget_id]:
            self.completion_timers[widget_id].cancel()
        
        # Start new debounced timer
        if self.app and hasattr(self.app, 'loop') and self.app.loop:
            self.completion_timers[widget_id] = self.app.loop.call_later(
                0.3,  # 300ms delay
                lambda: self._debounced_account_completion_handler(widget)
            )
        else:
            # Fallback to immediate execution if loop is not available
            self._debounced_account_completion_handler(widget)
    
    def _debounced_account_completion_handler(self, widget):
        """Actual completion handling logic after debouncing."""
        try:
            # Get the query
            query = widget.value
            
            if not query or not query.strip():
                if self.suggestion_popup:
                    self.suggestion_popup.hide()
                return
            
            # Get suggestions directly (no async needed)
            if self.account_completer and self.suggestion_popup:
                suggestions = self.account_completer.get_suggestions(query.strip())
                if suggestions:
                    self.suggestion_popup.show_suggestions(suggestions)
                    # Request scroll to make sure popup is visible
                    if self.on_scroll_request:
                        self.on_scroll_request(self.widget)
                else:
                    self.suggestion_popup.hide()

        except Exception as e:
            logger.debug(f"Error in debounced completion: {e}")

    def _on_suggestion_selected(self, selected_account: str):
        """Handle suggestion selection."""
        self._setting_suggestion = True
        try:
            self.widget.value = selected_account
            if self.on_change:
                self.on_change(self.widget)
        finally:
            self._setting_suggestion = False
    
    def _on_account_input_gain_focus(self, widget):
        """Handle account input gaining focus."""
        if self.on_gain_focus:
            self.on_gain_focus(widget)
    
    def _on_account_input_lose_focus(self, widget):
        """Handle account input losing focus."""
        if self.suggestion_popup:
            self.suggestion_popup.hide()
        
        if self.on_lose_focus:
            self.on_lose_focus(widget)

    def _on_account_input_confirm(self, widget):
        """Handle account input confirmation."""
        if self.suggestion_popup:
            self.suggestion_popup.select_current()
        
        if self.on_confirm:
            self.on_confirm(widget)
