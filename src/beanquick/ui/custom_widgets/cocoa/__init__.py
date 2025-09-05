"""
macOS (Cocoa) custom widget implementations.

This module registers all custom widget implementations available for macOS.
"""

import sys
import logging

from .. import register_widget
from ..base import CustomWidgetInterface

logger = logging.getLogger(__name__)


class CustomTableWidget(CustomWidgetInterface):
    """Custom Table widget implementation for macOS."""
    
    @property
    def widget_name(self) -> str:
        return "Table"
    
    @property
    def widget_class(self):
        from .table import Table
        return Table
    
    @property
    def supported_platforms(self) -> list[str]:
        return ["darwin"]


def register_cocoa_widgets():
    """Register all available macOS custom widgets."""
    if sys.platform != "darwin":
        logger.debug("Skipping Cocoa widget registration - not on macOS")
        return
    
    widgets_to_register = [
        CustomTableWidget(),
        # Add more custom widgets here as they are implemented
        # CustomButtonWidget(),
        # CustomTextInputWidget(),
    ]
    
    registered_count = 0
    for widget in widgets_to_register:
        try:
            register_widget(widget)
            registered_count += 1
            logger.info(f"✅ Registered custom {widget.widget_name} widget for macOS")
        except Exception as e:
            logger.warning(f"⚠️ Failed to register {widget.widget_name} widget: {e}")
    
    if registered_count > 0:
        logger.info(f"Successfully registered {registered_count} custom widgets for macOS")
    else:
        logger.warning("No custom widgets were registered for macOS")


# Auto-register widgets when this module is imported
register_cocoa_widgets()