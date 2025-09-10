"""Transaction form implementation."""
from __future__ import annotations

import sys
import logging
import re
from typing import Dict, Any, List, TYPE_CHECKING

import toga
from toga.style import Pack
from toga.style.pack import ROW, COLUMN, START, CENTER  # type: ignore

from beanquick.beans.flags import FLAG_OKAY, FLAG_WARNING
from beanquick.ui.forms.base_form import BaseDirectiveForm
from beanquick.ui.components.posting_line import PostingLineComponent
from beanquick.ui.forms.form_utils import MacOSTabChainMixin, FormValidationMixin, get_text_input_widgets_from_dict
from beanquick.services.beanquick_integration import get_beanquick_integration


if TYPE_CHECKING:
    from beanquick.app import Beanquick

logger = logging.getLogger(__name__)

WIDGET_SPACING = 5

class TransactionForm(BaseDirectiveForm, MacOSTabChainMixin, FormValidationMixin):
    """Form for creating Transaction directives."""

    def __init__(self, on_change=None, account_completer=None, completion_timers=None, app: Beanquick | None = None):
        self.account_completer = account_completer
        self.completion_timers = completion_timers or {}
        self._posting_lines: List[PostingLineComponent] = []
        self.app = app

        super().__init__(on_change)
        self._setup_transaction_fields()

        # Beanquick integration
        self._beanquick_integration = get_beanquick_integration(self.app)
        
    def _setup_transaction_fields(self):
        """Set up transaction-specific fields."""
        # Flag toggle
        self.flag_toggle = toga.Button(
            FLAG_OKAY,
            style=Pack(align_items=CENTER, width=18, margin=(0, WIDGET_SPACING)),
            on_press=self._on_flag_press
        )
        
        # Payee input
        self.payee_input = toga.TextInput(
            style=Pack(flex=1),
            placeholder="Payee",
            on_change=self._on_field_change,
        )
        
        # Narration input
        self.narration_input = toga.TextInput(
            style=Pack(flex=2, margin_left=WIDGET_SPACING),
            placeholder="Narration",
            on_change=self._on_field_change,
        )
        
        # Store references
        self._widgets.update({
            "flag": self.flag_toggle,
            "payee": self.payee_input,
            "narration": self.narration_input,
        })
    
    def create_form_widget(self) -> toga.Widget:
        """Create the main form widget."""
        # Create the main transaction fields row
        main_row = toga.Box(
            style=Pack(direction=ROW, align_items=START),
            children=[
                self.date_field.widget,
                self.flag_toggle,
                self.payee_input,
                self.narration_input,
            ]
        )
        
        # Create postings container
        self.postings_box = toga.Box(
            style=Pack(direction=COLUMN),
            children=[]
        )
        
        # Initialize with one empty posting line
        self._add_posting_line()
        
        # Create the main form box
        form_box = toga.Box(
            style=Pack(direction=COLUMN, margin=WIDGET_SPACING),
            children=[main_row, self.postings_box]
        )
        
        # Wrap in scroll container
        scroll_container = toga.ScrollContainer(
            horizontal=False,
            vertical=True,
            content=form_box,
            style=Pack(flex=1),
        )

        self._widgets["scroll"] = scroll_container

        return scroll_container
    
    def build_directive_dict(self) -> Dict[str, Any]:
        """Build dictionary for Transaction serialization."""
        # Get basic transaction data
        date_text = self.get_date_value()
        flag_text = self.flag_toggle.text
        payee_text = self.payee_input.value.strip() if self.payee_input.value else ""
        narration_text = self.narration_input.value.strip() if self.narration_input.value else ""
        default_currency = "USD"
        default_narration = "Transaction"
        
        # Get default currency from config
        if self._beanquick_integration._ensure_initialized():
            config = self._beanquick_integration.config or {}
            default_currency = config.get("defaults", {}).get("currency", "USD")
            default_narration = config.get("defaults", {}).get("narration", "Transaction")
    
        # Build postings list
        postings = []
        for line in self._posting_lines:
            # Only include lines where account is specified
            if line.account_text:
                formatted_amount = self._format_amount_with_currency(line.amount_text, default_currency)
                postings.append({
                    "account": line.account_text,
                    "amount": formatted_amount
                })
        
        return {
            "t": "Transaction",
            "meta": {},
            "date": date_text,
            "flag": "!" if flag_text == FLAG_WARNING else "*",
            "payee": payee_text,
            "narration": narration_text or default_narration,
            "tags": [],
            "links": [],
            "postings": postings
        }
    
    def _format_amount_with_currency(self, amount_text: str, default_currency: str) -> str:
        """Format amount text by adding default currency if it's just a number."""
        if not amount_text or not default_currency:
            return amount_text
        
        # Check if the amount is just a number or arithmetic expression (positive or negative)
        # This regex matches: optional minus, digits, optional decimal point and digits, or arithmetic expressions
        import re
        # Match numbers and arithmetic expressions with parentheses, operators (+, -, *, /), and decimal numbers
        if re.match(r'^-?[\d\.\+\-\*/\(\)\s]+$', amount_text) and not re.search(r'[a-zA-Z]', amount_text):
            # It's just a number or arithmetic expression, add the default currency
            return f"{amount_text} {default_currency}"
        
        # If it already has currency or other formatting, return as-is
        return amount_text

    def clear_form(self):
        """Clear all form data."""
        # Clear common fields
        self.clear_common_fields()
        
        # Clear transaction-specific fields
        self.payee_input.value = ""
        self.narration_input.value = ""
        self.flag_toggle.text = FLAG_OKAY

        # Remove all but the first line
        while len(self._posting_lines) > 1:
            self._remove_posting_line(len(self._posting_lines) - 1)
        
        # Clear all posting lines
        for line in self._posting_lines:
            line.clear()
    
    def is_form_valid(self) -> bool:
        """Check if form data is valid."""
        errors = self.get_form_errors()
        return len(errors) == 0
    
    def get_form_errors(self) -> List[str]:
        """Get validation errors."""
        errors = []
        
        self.validate_date_field(self.get_date_value(), errors)
        
        # Check for at least two postings with accounts
        posting_accounts = [line.account_text for line in self._posting_lines if line.account_text]
        if len(posting_accounts) < 2:
            errors.append("At least two postings are required")
        
        return errors
    
    def is_form_empty(self) -> bool:
        """Check if form is empty."""
        if not self.is_common_fields_empty():
            return False
        
        payee_text = self.payee_input.value.strip() if self.payee_input.value else ""
        narration_text = self.narration_input.value.strip() if self.narration_input.value else ""
        
        # Check if any posting lines have data
        has_posting_data = any(line.has_data for line in self._posting_lines)
        
        return not any([payee_text, narration_text]) and not has_posting_data

    def _add_posting_line(self):
        """Add a new posting line to the form."""
        # Create a new posting line component
        posting_line = PostingLineComponent(
            account_completer=self.account_completer,
            completion_timers=self.completion_timers,
            app=self.app,
            on_change=self._on_field_change,
            on_erase=self._on_posting_line_erase,
            on_scroll_request=self._scroll_to_widget,
            on_gain_focus=self._on_input_gain_focus,
        )
        
        # Add to our tracking list
        self._posting_lines.append(posting_line)

        # Set up the posting line in the container (for suggestion popup support)
        posting_line.setup_in_container(self.postings_box)

        # macOS-specific fix for tab navigation on dynamically added TextInputs
        if sys.platform == "darwin":
            self._fix_macos_tab_chain()
        
        logger.debug(f"Added posting line. Total lines: {len(self._posting_lines)}")
    
    def _on_posting_line_erase(self, posting_line: PostingLineComponent, **kwargs):
        """Handle erase button press for a posting line."""
        # Find the index of the posting line
        for i, line in enumerate(self._posting_lines):
            if line == posting_line:
                if len(self._posting_lines) > 1:
                    self._remove_posting_line(i)
                    self._on_field_change(None)
                else:
                    # If it's the last line, just clear it
                    line.clear()
                    self._on_field_change(None)
                return
        
        logger.warning("Erase button pressed but no matching posting line found")
    
    # https://github.com/beeware/toga/issues/2766
    # Set initial focus will cause tab navigation issues
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
            text_inputs.append(self._widgets["payee"])
            text_inputs.append(self._widgets["narration"])

            # Add posting inputs in order
            for line in self._posting_lines:
                text_inputs.append(line.account_field.widget)
                text_inputs.append(line.amount_input)

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

    def _remove_posting_line(self, line_index: int):
        """Remove a posting line from the form."""
        if line_index < 0 or line_index >= len(self._posting_lines):
            logger.warning(f"Attempted to remove invalid posting line index: {line_index}")
            return
            
        # Safety check: don't remove if only one line remains
        if len(self._posting_lines) <= 1:
            logger.debug("Cannot remove posting line - minimum one line required")
            return

        line = self._posting_lines[line_index]

        # Hide suggestion popup before removing
        if line.account_field.suggestion_popup:
            line.account_field.suggestion_popup.hide()

        # Remove from UI container - find and remove the wrapper
        for child in self.postings_box.children:
            if hasattr(child, 'children') and line.container in child.children:
                self.postings_box.remove(child)
                break
        
        # Remove from our tracking list
        self._posting_lines.pop(line_index)
        
        logger.debug(f"Removed posting line {line_index}. Total lines: {len(self._posting_lines)}")
    
    def _manage_posting_lines(self):
        """Manage dynamic addition and removal of posting lines."""
        # Remove empty intermediate lines (not the last line)
        lines_to_remove = []
        for i in range(len(self._posting_lines) - 1):  # Exclude last line
            line = self._posting_lines[i]
            if not line.has_data:
                lines_to_remove.append(i)
        
        # Remove lines in reverse order to maintain correct indices
        for line_index in reversed(lines_to_remove):
            self._remove_posting_line(line_index)

        # Check if we need to add a new line
        if len(self._posting_lines) > 0:
            last_line = self._posting_lines[-1]
            
            # Add new line if last line has both account and amount filled
            if last_line.is_complete:
                self._add_posting_line()
        
        # Enable the erase buttons for lines with data
        for i in range(len(self._posting_lines) - 1):  # Exclude last line
            line = self._posting_lines[i]
            line.update_erase_button()

    def _is_widget_out_of_view(self, widget) -> bool:
        """Test whether a widget is out of view in the scroll container."""
        try:
            entry_scroll = self._widgets["scroll"]
            
            # Get widget's absolute position from layout
            widget_top = widget.layout.absolute_content_top
            widget_bottom = widget.layout.absolute_content_bottom
            
            # Get scroll container's visible area
            scroll_top = entry_scroll.layout.absolute_content_top
            scroll_bottom = entry_scroll.layout.absolute_content_bottom
            
            # Account for current scroll position
            current_scroll_position = entry_scroll.vertical_position
            visible_top = scroll_top + current_scroll_position
            visible_bottom = scroll_bottom + current_scroll_position
            
            # Widget is completely visible if:
            # - its top is at or below the visible top AND
            # - its bottom is at or above the visible bottom
            is_completely_visible = (widget_top >= visible_top and 
                                widget_bottom <= visible_bottom)
            
            # Return True if ANY part is out of view
            return not is_completely_visible
            
        except Exception as e:
            logger.debug(f"Error checking widget visibility: {e}")
            return True  # If we can't determine, err on the side of scrolling

    def _scroll_to_widget(self, widget):
        """Scroll the entry form to make a specific widget visible, accounting for suggestion popup."""
        try:
            entry_scroll = self._widgets["scroll"]
            
            # Get widget's absolute position and dimensions from layout
            widget_top = widget.layout.absolute_content_top
            widget_bottom = widget.layout.absolute_content_bottom
            widget_height = widget.layout.content_height
            
            # Get scroll container's position and size
            scroll_top = entry_scroll.layout.absolute_content_top
            scroll_bottom = entry_scroll.layout.absolute_content_bottom
            scroll_height = entry_scroll.layout.content_height
            
            # Find the suggestion popup for this widget and get its height
            suggestion_popup = None
            popup_height = 0
            for line in self._posting_lines:
                if line.account_field.widget == widget:
                    suggestion_popup = line.account_field.suggestion_popup
                    break
            
            # Get popup height if it's visible
            if suggestion_popup and hasattr(suggestion_popup, 'is_visible') and suggestion_popup.is_visible:
                try:
                    popup_height = suggestion_popup.popup_box.layout.content_height
                except Exception:
                    popup_height = 110  # Fallback height
            
            # Calculate total height needed (widget + popup)
            total_content_height = widget_height + popup_height
            
            # Calculate the widget's position relative to the scroll container's content
            widget_relative_top = widget_top - scroll_top
            widget_relative_bottom = widget_relative_top + widget_height
            
            # Account for current scroll position to get visible area
            current_scroll_position = entry_scroll.vertical_position
            visible_top = current_scroll_position
            visible_bottom = current_scroll_position + scroll_height
            
            # Determine scroll behavior based on widget position and content size
            target_position = current_scroll_position  # Default: don't scroll
            
            # Check if total content (widget + popup) is larger than scroll container
            if total_content_height >= scroll_height:
                # If total height is larger than container, align widget top with container top (with spacing)
                target_position = widget_relative_top - WIDGET_SPACING
                logger.debug(f"Total content ({total_content_height}) >= scroll height ({scroll_height}), aligning top with spacing")
            
            elif widget_relative_bottom > visible_bottom:
                # Widget is below visible area, align widget bottom (+ popup) with container bottom (with spacing)
                target_position = widget_relative_top + total_content_height - scroll_height + WIDGET_SPACING
                logger.debug(f"Widget below view, aligning bottom with popup space and spacing")
            
            elif widget_relative_top < visible_top:
                # Widget is above visible area, align widget top with container top (with spacing)
                target_position = widget_relative_top - WIDGET_SPACING
                logger.debug(f"Widget above view, aligning top with spacing")
            
            else:
                # Widget is already visible, but check if popup would be cut off
                if suggestion_popup and hasattr(suggestion_popup, 'is_visible') and suggestion_popup.is_visible:
                    popup_bottom = widget_relative_bottom + popup_height
                    if popup_bottom > visible_bottom:
                        # Popup would be cut off, scroll to show it (with spacing)
                        target_position = widget_relative_top + total_content_height - scroll_height + WIDGET_SPACING
                        logger.debug(f"Widget visible but popup cut off, adjusting scroll with spacing")
            
            # Ensure we don't scroll beyond bounds
            target_position = max(0, target_position)
            
            # Only scroll if the position actually needs to change
            if abs(target_position - current_scroll_position) > 1:  # Small tolerance for floating point
                entry_scroll.vertical_position = target_position
                logger.debug(f"Scrolled from {current_scroll_position} to {target_position} (widget: {widget_relative_top}-{widget_relative_bottom}, popup: {popup_height})")
            else:
                logger.debug(f"No scroll needed - widget already in optimal position")
            
        except Exception as e:
            logger.debug(f"Error scrolling to widget: {e}")

    def _on_input_gain_focus(self, widget, **kwargs):
        """Handle input gaining focus, scroll only if out of view."""
        if self._is_widget_out_of_view(widget):
            self._scroll_to_widget(widget)
            
    def _on_flag_press(self, widget, **kwargs):
        """Handle the flag toggle action."""
        if widget.text == FLAG_OKAY:
            widget.text = FLAG_WARNING
        else:
            widget.text = FLAG_OKAY
        
        # Trigger change event
        self._on_field_change(widget)
    
    def _on_field_change(self, widget, **kwargs):
        """Handle field changes."""
        # Manage dynamic posting lines
        self._manage_posting_lines()
        
        # Call parent change handler
        super()._on_field_change(widget, **kwargs)