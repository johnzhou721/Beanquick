"""
Preferences window for configuring application settings.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, TYPE_CHECKING
from pathlib import Path

import toga

from beanquick.ui.config_box import ConfigBox
from beanquick.services.beanquick_integration import get_beanquick_integration

if TYPE_CHECKING:
    from beanquick.app import Beanquick 

logger = logging.getLogger(__name__)

class PreferencesWindow(toga.Window):
    """Preferences window with categorized settings using OptionContainer."""
    
    def __init__(self, title="Settings"):
        super().__init__(title=title, size=(600, 500))
        self.config = self.app.config

        # Beanquick integration
        self._beanquick_integration = get_beanquick_integration(self.app)
        
        """Show the preferences window."""
        self._create_ui()

        logger.info("Preferences window shown")

    def _create_ui(self):
        """Create the UI components."""
        config_box = self._get_config_box()
        
        self.content = config_box
    
    def _get_config_box(self) -> toga.Box:
        """Create the configuration box with settings."""
        try:
            config_exists, config_path = self._beanquick_integration.get_config_info()
                    
            if config_exists:
                return self._create_config_box()
            else:
                if not self._beanquick_integration.is_initialized:
                    self._beanquick_integration._create_default_config()
                    return self._create_config_box()
                else:
                    health = self._beanquick_integration.get_health_status()
                    error_info = health.get('initialization_error', 'Unknown error')
                    raise ValueError(
                        f"Beanquick configuration not found at {config_path}. "
                        f"Initialization error: {error_info}"
                    )
        except Exception as e:
            logger.error(f"Error in config dialog: {e}", exc_info=True)
            raise ValueError(
                f"Could not load Beanuick configuration: {str(e)}"
            ) from e

    def _create_config_box(self) -> ConfigBox:
        """Create the configuration box with settings."""
        self._beanquick_integration.safe_reload_config()
        config_box = ConfigBox(
            self._beanquick_integration.config,
            on_save=self._on_save_handler,
            on_cancel=self._on_cancel_handler,
            account_completer=self._beanquick_integration.account_completer,
            app=self.app,
        )
        return config_box

    def _on_save_handler(self, config: Dict[str, Any]):
        if self._beanquick_integration:
            success, error_message = self._beanquick_integration.safe_save_config(config)
            if success:
                task = self.app.loop.create_task(
                    self.dialog(
                        toga.InfoDialog(
                            "Config Saved",
                            "Beanquick config saved successfully."
                        )
                    )
                )
                def on_task_done(task):
                    self._beanquick_integration.safe_reload_config()
                task.add_done_callback(on_task_done)
            if not success:
                self.app.loop.create_task(
                    self.dialog(
                        toga.ErrorDialog(
                            "Config Save Error",
                            f"Could not save Beanquick config: {error_message}"
                        )
                    )
                )
    def _on_cancel_handler(self):
        """Handle cancel action."""
        self.close()

def show_preferences_window(app: Beanquick):
    """Show the preferences window."""
    # Check if there's already a preferences window open
    existing_window = None
    for window in app.windows:
        if isinstance(window, PreferencesWindow):
            existing_window = window
            break

    if existing_window:
        app.current_window = existing_window
        return

    try:
        prefs_window = PreferencesWindow()
        prefs_window.show()
    except Exception as e:
        logger.error(f"Error showing preferences window: {e}", exc_info=True)
        for window in app.windows:
            if isinstance(window, PreferencesWindow):
                app.windows.discard(window)
                break

        if app.main_window:
            asyncio.create_task(
                app.main_window.dialog(
                    toga.ErrorDialog(
                        "Error",
                        f"Could not open preferences window: {str(e)}"
                    )
                )
            )
