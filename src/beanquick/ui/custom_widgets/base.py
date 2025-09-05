"""
Base classes and interfaces for custom widget implementations.
"""
from abc import ABC, abstractmethod
from typing import Type, Dict
import sys


class CustomWidgetInterface(ABC):
    """Interface that all custom widget implementations must follow."""
    
    @property
    @abstractmethod
    def widget_name(self) -> str:
        """Return the name of the widget (e.g., 'Table', 'Button')."""
        pass
    
    @property
    @abstractmethod
    def widget_class(self) -> Type:
        """Return the actual widget implementation class."""
        pass
    
    @property
    @abstractmethod
    def supported_platforms(self) -> list[str]:
        """Return list of supported platforms (e.g., ['darwin', 'linux', 'win32'])."""
        pass
    
    def is_supported_platform(self) -> bool:
        """Check if current platform is supported by this widget."""
        return sys.platform in self.supported_platforms


class WidgetRegistrationError(Exception):
    """Raised when widget registration fails."""
    pass


class PlatformWidgetRegistry:
    """Registry for platform-specific custom widgets."""
    
    def __init__(self):
        self._widgets: Dict[str, CustomWidgetInterface] = {}
    
    def register_widget(self, widget_interface: CustomWidgetInterface) -> None:
        """Register a custom widget implementation."""
        if not isinstance(widget_interface, CustomWidgetInterface):
            raise WidgetRegistrationError(
                f"Widget must implement CustomWidgetInterface, got {type(widget_interface)}"
            )
        
        if not widget_interface.is_supported_platform():
            raise WidgetRegistrationError(
                f"Widget {widget_interface.widget_name} does not support platform {sys.platform}"
            )
        
        widget_name = widget_interface.widget_name
        if widget_name in self._widgets:
            raise WidgetRegistrationError(
                f"Widget {widget_name} is already registered"
            )
        
        self._widgets[widget_name] = widget_interface
    
    def get_widget(self, widget_name: str) -> CustomWidgetInterface | None:
        """Get a registered widget by name."""
        return self._widgets.get(widget_name)
    
    def get_all_widgets(self) -> Dict[str, CustomWidgetInterface]:
        """Get all registered widgets."""
        return self._widgets.copy()
    
    def clear(self) -> None:
        """Clear all registered widgets."""
        self._widgets.clear()
