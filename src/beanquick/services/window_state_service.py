"""Window state persistence service for Beanquick application."""
from __future__ import annotations

import logging
import platform
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beanquick.app import Beanquick
    from beanquick.config import AppConfig

logger = logging.getLogger(__name__)


class WindowStateService:
    """Service for managing window state persistence."""
    
    def __init__(self, app: Beanquick):
        self.app = app
        self.config: AppConfig = app.config
        self._initialized = False
        self._using_native_autosave = False
        self._save_on_transitions = False
    
    def initialize(self) -> None:
        """Initialize window state persistence."""
        if self._initialized:
            return
        
        self._restore_window_state()
        self._setup_event_handlers()
        self._initialized = True
        
        platform_info = f"macOS native autosave" if self._using_native_autosave else f"manual mode on {sys.platform}"
        logger.info(f"Window state service initialized ({platform_info})")
    
    def save_state(self) -> None:
        """Save current window state if using manual mode."""
        if self._using_native_autosave:
            return  # Native autosave handles this
        
        try:
            position = self.app.main_window.position
            size = self.app.main_window.size
            
            window_state = {
                'x': int(position[0]),
                'y': int(position[1]),
                'width': int(size[0]),
                'height': int(size[1])
            }
            self.config.set_window_state(window_state)
            logger.debug(f"Saved window state: {window_state}")
        except Exception as e:
            logger.debug(f"Failed to save window state: {e}")
    
    def _restore_window_state(self) -> None:
        """Restore window position and size from saved state."""
        try:
            # Try native macOS autosave first (macOS only)
            if self._setup_macos_native_autosave():
                self._using_native_autosave = True
                logger.info("Using native macOS NSWindow autosave for window state")
                return
            
            # Fallback to manual restore for non-macOS or when native autosave fails
            logger.info("Using manual window state management")
            window_state = self.config.get_window_state()
            if window_state:
                if 'x' in window_state and 'y' in window_state:
                    self.app.main_window.position = (window_state['x'], window_state['y'])
                
                if 'width' in window_state and 'height' in window_state:
                    self.app.main_window.size = (window_state['width'], window_state['height'])
                
                logger.info(f"Restored window state: {window_state}")
        except Exception as e:
            logger.warning(f"Failed to restore window state: {e}")
    
    def _setup_macos_native_autosave(self) -> bool:
        """Try to set up native NSWindow autosave functionality (macOS only)."""
        # NSWindow autosave is only available on macOS
        if sys.platform != 'darwin':
            logger.debug("Native window autosave is only available on macOS")
            return False
        
        try:
            # Check if we can access the native NSWindow
            if not (hasattr(self.app.main_window, '_impl') and 
                    hasattr(self.app.main_window._impl, 'native')):
                logger.debug("Cannot access native window implementation")
                return False
            
            native_window = self.app.main_window._impl.native
            if native_window is None:
                logger.debug("Native window is None")
                return False
            
            # Try to set the NSWindow autosave name
            autosave_name = f"{self.app.app_id}.MainWindow"
            if hasattr(native_window, 'setFrameAutosaveName_'):
                native_window.setFrameAutosaveName_(autosave_name)
                logger.debug(f"Set NSWindow autosave name: {autosave_name}")
                return True
            else:
                logger.debug("NSWindow does not have setFrameAutosaveName_ method")
                    
        except Exception as e:
            logger.debug(f"Could not set up macOS native autosave: {e}")
        
        return False
    
    def _setup_event_handlers(self) -> None:
        """Set up event handlers for window state persistence."""
        if self._using_native_autosave:
            return  # Native autosave handles everything
        
        try:
            self._setup_window_close_handler()
            self._setup_app_exit_handler()
            self._save_on_transitions = True
            
        except Exception as e:
            logger.warning(f"Failed to set up window event handlers: {e}")
    
    def _setup_window_close_handler(self) -> None:
        """Set up window close event handler."""
        original_on_close = getattr(self.app.main_window, 'on_close', None)
        
        def on_window_close(window):
            self.save_state()
            if original_on_close:
                original_on_close(window)
        
        self.app.main_window.on_close = on_window_close
    
    def _setup_app_exit_handler(self) -> None:
        """Set up app exit event handler."""
        original_on_exit = getattr(self.app, 'on_exit', None)
        
        def on_app_exit(app, **kwargs):
            self.save_state()
            if original_on_exit:
                original_on_exit(app, **kwargs)
            return True
        
        self.app.on_exit = on_app_exit
    
    def on_state_transition(self) -> None:
        """Called when app state transitions occur (indicates user interaction)."""
        if self._save_on_transitions:
            self.save_state()
    
    @property
    def is_using_native_autosave(self) -> bool:
        """Check if native autosave is being used."""
        return self._using_native_autosave
    
    @property
    def is_macos(self) -> bool:
        """Check if running on macOS."""
        return sys.platform == 'darwin'
    
    @property
    def supports_native_autosave(self) -> bool:
        """Check if the current platform supports native window autosave."""
        return self.is_macos