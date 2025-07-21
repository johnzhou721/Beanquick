"""Posting line component for transaction forms."""
from __future__ import annotations

import logging
from typing import NamedTuple, Callable, Optional, Dict, Any

import toga
from toga.style import Pack
from toga.style.pack import ROW, CENTER  # type: ignore

from beanquick.ui.components.autocomplete_account_field import AutocompleteAccountField

logger = logging.getLogger(__name__)

WIDGET_SPACING = 5


class PostingLineComponent:
    """A complete posting line with account input, amount input, and erase button."""
    
    def __init__(
        self,
        on_change: Optional[Callable] = None,
        on_erase: Optional[Callable] = None,
        on_scroll_request: Optional[Callable] = None,
        on_gain_focus: Optional[Callable] = None,
        account_completer=None,
        completion_timers: Optional[Dict] = None,
        app=None,
    ):
        self.on_change = on_change
        self.on_erase = on_erase
        self.on_scroll_request = on_scroll_request
        self.on_gain_focus = on_gain_focus
        
        # Create the erase button
        self.erase_button = toga.Button(
            "⌦",
            style=Pack(width=24, margin_right=WIDGET_SPACING),
            enabled=False,
            on_press=self._on_erase_press
        )
        
        # Create the account field with autocompletion
        self.account_field = AutocompleteAccountField(
            placeholder="Account",
            on_change=self._on_account_change,
            on_confirm=self._on_account_confirm,
            on_gain_focus=self.on_gain_focus,
            on_scroll_request=self.on_scroll_request,
            account_completer=account_completer,
            completion_timers=completion_timers,
            app=app,
            style=Pack(flex=3),
        )
        
        # Create the amount input
        self.amount_input = toga.TextInput(
            style=Pack(flex=1, margin_left=WIDGET_SPACING),
            placeholder="Amount",
            on_change=self._on_amount_change,
            on_gain_focus=self.on_gain_focus,
        )
        
        # Create the posting line container
        self.container = toga.Box(
            style=Pack(direction=ROW, align_items=CENTER, margin_top=WIDGET_SPACING),
            children=[
                self.erase_button,
                self.account_field.widget,
                self.amount_input,
            ]
        )
        
        # Parent container for suggestion popup
        self.parent_container = None
    
    def setup_in_container(self, parent_container: toga.Box):
        """Set up the posting line within a parent container to enable suggestion popup."""
        self.parent_container = parent_container
        
        # Create a wrapper for this posting line and its suggestions
        wrapper = toga.Box(
            style=Pack(direction=toga.style.pack.COLUMN),
            children=[self.container]
        )
        
        # Set up the account field's suggestion popup
        self.account_field.setup_in_container(wrapper)
        
        # Add wrapper to parent
        parent_container.add(wrapper)
        
        return wrapper
    
    @property
    def account_text(self) -> str:
        """Get the trimmed account text."""
        return self.account_field.value.strip()
    
    @property
    def amount_text(self) -> str:
        """Get the trimmed amount text."""
        return self.amount_input.value.strip() if self.amount_input.value else ""
    
    @property
    def has_data(self) -> bool:
        """Check if this posting line has any data."""
        return bool(self.account_text or self.amount_text)
    
    @property
    def is_complete(self) -> bool:
        """Check if this posting line has both account and amount."""
        return bool(self.account_text and self.amount_text)
    
    def clear(self):
        """Clear all data in this posting line."""
        self.account_field.clear()
        self.amount_input.value = ""
        self.erase_button.enabled = False
    
    def update_erase_button(self):
        """Update the erase button state based on data presence."""
        self.erase_button.enabled = self.has_data
    
    def focus_account(self):
        """Focus the account input."""
        self.account_field.focus()
    
    def focus_amount(self):
        """Focus the amount input."""
        self.amount_input.focus()
    
    def _on_account_change(self, widget, **kwargs):
        """Handle account input changes."""
        self.update_erase_button()
        if self.on_change:
            self.on_change(widget, **kwargs)
    
    def _on_account_confirm(self, widget: toga.Widget):
        """Handle account confirmation."""
        self.focus_amount()

    def _on_amount_change(self, widget, **kwargs):
        """Handle amount input changes."""
        self.update_erase_button()
        if self.on_change:
            self.on_change(widget, **kwargs)
    
    def _on_erase_press(self, widget, **kwargs):
        """Handle erase button press."""
        if self.on_erase:
            self.on_erase(self, **kwargs)
