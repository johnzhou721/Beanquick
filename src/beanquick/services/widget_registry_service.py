"""
Widget Registry Service - Manages custom widget registration and integration with Toga.

This service automatically discovers, registers, and integrates custom widget
implementations with the Toga framework, providing seamless fallback to 
default widgets when custom implementations are not available.
"""

import sys
import logging
from typing import TYPE_CHECKING, Dict, Any, Union, List

if TYPE_CHECKING:
    import toga

logger = logging.getLogger(__name__)


class WidgetRegistryService:
    """
    Service for managing custom widget registration and integration.
    
    This service:
    - Discovers platform-specific custom widgets
    - Registers them with the Toga app factory  
    - Provides logging and error handling
    - Gracefully falls back to default widgets on failure
    """
    
    def __init__(self, app: 'toga.App'):
        """
        Initialize the widget registry service.
        
        Args:
            app: The Toga application instance
        """
        self.app = app
        self.registered_widgets: Dict[str, Any] = {}
        self.original_widgets: Dict[str, Any] = {}
        
        # Initialize the registry
        self._initialize_registry()
    
    def _initialize_registry(self) -> None:
        """Initialize the widget registry and register custom widgets."""
        logger.info("Initializing custom widget registry...")
        
        try:
            # Import and discover custom widgets
            from beanquick.ui.custom_widgets import get_all_widgets
            available_widgets = get_all_widgets()
            
            if not available_widgets:
                logger.info("No custom widgets available for current platform")
                return
            
            # Register each discovered widget
            registered_count = 0
            for widget_name, widget_interface in available_widgets.items():
                try:
                    self._register_widget_with_factory(widget_name, widget_interface)
                    registered_count += 1
                except Exception as e:
                    logger.warning(f"Failed to register {widget_name} widget: {e}")
            
            if registered_count > 0:
                logger.info(f"✅ Successfully registered {registered_count} custom widgets")
            else:
                logger.warning("⚠️ No custom widgets were successfully registered")
                
        except Exception as e:
            logger.error(f"Critical error during widget registry initialization: {e}", exc_info=True)
    
    def _register_widget_with_factory(self, widget_name: str, widget_interface) -> None:
        """
        Register a custom widget with the Toga app factory.
        
        Args:
            widget_name: Name of the widget (e.g., 'Table')
            widget_interface: The widget interface containing the implementation
        """
        try:
            # Get the custom widget class
            custom_widget_class = widget_interface.widget_class
            
            # Store original widget for potential restoration
            if hasattr(self.app.factory, widget_name):
                original_widget = getattr(self.app.factory, widget_name)
                self.original_widgets[widget_name] = original_widget
            
            # Register the custom widget with the factory
            setattr(self.app.factory, widget_name, custom_widget_class)
            self.registered_widgets[widget_name] = custom_widget_class
            
            logger.info(f"✅ Successfully registered custom {widget_name} widget")
            
        except Exception as e:
            logger.error(f"Failed to register {widget_name} with app factory: {e}")
            raise
    
    def restore_original_widgets(self) -> None:
        """
        Restore original Toga widgets (useful for testing or fallback).
        """
        logger.info("Restoring original Toga widgets...")
        
        for widget_name, original_widget in self.original_widgets.items():
            try:
                setattr(self.app.factory, widget_name, original_widget)
                logger.debug(f"Restored original {widget_name} widget")
            except Exception as e:
                logger.warning(f"Failed to restore original {widget_name} widget: {e}")
        
        self.registered_widgets.clear()
        logger.info("Original widgets restored")
    
    def get_registered_widgets(self) -> Dict[str, Any]:
        """
        Get a dictionary of all registered custom widgets.
        
        Returns:
            Dictionary mapping widget names to their custom implementations
        """
        return self.registered_widgets.copy()
    
    def is_widget_customized(self, widget_name: str) -> bool:
        """
        Check if a widget has been replaced with a custom implementation.
        
        Args:
            widget_name: Name of the widget to check
            
        Returns:
            True if widget has custom implementation, False otherwise
        """
        return widget_name in self.registered_widgets
    
    def get_platform_info(self) -> Dict[str, Union[str, int, List[str]]]:
        """
        Get information about the current platform and widget support.
        
        Returns:
            Dictionary with platform information
        """
        return {
            "platform": sys.platform,
            "custom_widgets_count": len(self.registered_widgets),
            "custom_widgets": list(self.registered_widgets.keys()),
        }
