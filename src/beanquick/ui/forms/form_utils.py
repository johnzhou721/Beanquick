"""Common form utilities and mixins."""
from __future__ import annotations

import logging
import sys
from typing import List, Dict, Any

import toga

logger = logging.getLogger(__name__)


class MacOSTabChainMixin:
    """Mixin for fixing macOS tab chain issues."""
    
    def fix_macos_tab_chain(self, text_input_widgets: List[toga.TextInput]):
        """Fix tab navigation chain on macOS for TextInput widgets."""
        try:
            if sys.platform != "darwin":
                return
                
            from toga_cocoa.libs import appkit
            from rubicon.objc import ObjCClass
            
            # Get native NSTextField objects
            native_fields = []
            for text_input in text_input_widgets:
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


class FormValidationMixin:
    """Mixin for common form validation functionality."""
    
    def validate_required_field(self, field_value: str, field_name: str, errors: List[str]):
        """Validate that a required field has a value."""
        if not field_value.strip():
            errors.append(f"{field_name} is required")
    
    def validate_date_field(self, date_value: str, errors: List[str]):
        """Validate date field."""
        if not date_value:
            errors.append("Date is required")


def get_text_input_widgets_from_dict(widgets_dict: Dict[str, Any]) -> List[toga.TextInput]:
    """Extract TextInput widgets from a widgets dictionary."""
    text_inputs = []
    for widget in widgets_dict.values():
        if isinstance(widget, toga.TextInput):
            text_inputs.append(widget)
    return text_inputs
