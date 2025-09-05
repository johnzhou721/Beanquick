"""
Custom widget package - provides platform-specific widget implementations.

This package automatically discovers and provides custom widget implementations
for the current platform, with graceful fallbacks to default toga widgets.
"""

import sys
import importlib
from typing import Dict
import logging

from .base import CustomWidgetInterface, WidgetRegistrationError, PlatformWidgetRegistry

# Global registry for discovered widgets
_platform_registry = PlatformWidgetRegistry()

logger = logging.getLogger(__name__)


def discover_platform_widgets() -> Dict[str, CustomWidgetInterface]:
    """
    Discover and load custom widgets for the current platform.
    
    Returns:
        Dictionary mapping widget names to their implementations
    """
    platform_module_map = {
        'darwin': 'cocoa',
        'linux': 'gtk',
        'win32': 'winforms',
    }
    
    current_platform = sys.platform
    platform_module = platform_module_map.get(current_platform)
    
    if not platform_module:
        logger.info(f"No custom widgets available for platform: {current_platform}")
        return {}
    
    try:
        # Import platform-specific module which will register its widgets
        module_name = f"beanquick.ui.custom_widgets.{platform_module}"
        importlib.import_module(module_name)
        logger.info(f"Successfully loaded custom widgets for {current_platform}")
        
    except ImportError as e:
        logger.warning(f"Could not load custom widgets for {current_platform}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading custom widgets for {current_platform}: {e}")
    
    return _platform_registry.get_all_widgets()


def register_widget(widget_interface: CustomWidgetInterface) -> None:
    """
    Register a custom widget implementation.
    
    Args:
        widget_interface: The widget implementation to register
        
    Raises:
        WidgetRegistrationError: If registration fails
    """
    try:
        _platform_registry.register_widget(widget_interface)
        logger.debug(f"Registered custom widget: {widget_interface.widget_name}")
    except WidgetRegistrationError as e:
        logger.error(f"Failed to register widget {widget_interface.widget_name}: {e}")
        raise


def get_widget(widget_name: str) -> CustomWidgetInterface | None:
    """Get a registered custom widget by name."""
    return _platform_registry.get_widget(widget_name)


def get_all_widgets() -> Dict[str, CustomWidgetInterface]:
    """Get all registered custom widgets."""
    return _platform_registry.get_all_widgets()


# Auto-discover widgets when module is imported
_discovered_widgets = discover_platform_widgets()

__all__ = [
    'CustomWidgetInterface',
    'WidgetRegistrationError', 
    'discover_platform_widgets',
    'register_widget',
    'get_widget',
    'get_all_widgets',
]
