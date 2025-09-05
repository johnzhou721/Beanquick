"""
Beancounting, faster. For the novice. For the expert. For you.
"""
from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import asyncio
import threading
import logging
from typing import TYPE_CHECKING

import toga

from beanquick.core import BeanquickLedger
from beanquick.services.logging import get_logger, setup_logging
from beanquick.services.state_manager import StateManager
from beanquick.services.locale_service import LocaleService
from beanquick.services.widget_registry_service import WidgetRegistryService
from beanquick.config import AppConfig
from beanquick.toga_babel import _, TogaBabel
from beanquick.constants import DEFAULT_USER_LOCALE


if TYPE_CHECKING:
    from beanquick.services.ledger_manager import LedgerData


logger = get_logger()
babel = TogaBabel()

class Beanquick(toga.App):
    def __init__(self, formal_name="Beanquick", app_id="com.twobitsware.beanquick", **kwargs):
        """
        Initialize the Beanquick application.
        """
        super().__init__(formal_name, app_id, **kwargs)
        # Initialize basic app properties
        self.config: AppConfig = AppConfig(self.paths)
        self.state_manager = StateManager(self)

        # Initialize ledger management
        self.ledger_management_lock = threading.Lock()
        self.active_ledger: BeanquickLedger | None = None
        self.active_ledger_data: LedgerData | None = None
        self.current_load_task: asyncio.Task | None = None

        # Set up logging
        try:
            logs_path = self.paths.logs
            app_file_log_level = logging.INFO
            console_log_level = logging.DEBUG
            setup_logging(logs_path, app_file_log_level, console_log_level)
        except (OSError, ValueError) as e:
            logger.error(f"Critical error: Logging system initialization failed, the application may not log properly: {e}")
            logging.basicConfig(level=logging.INFO)
        except Exception as e:
            logger.error(f"Unexpected error during logging setup: {e}", exc_info=True)
            logging.basicConfig(level=logging.INFO)
        
        # Initialize LocaleService
        self.locale_service = LocaleService(self.config, logger)

        # Setting up i18n/l10n with Babel
        babel.init_app(
            self,
            default_locale=DEFAULT_USER_LOCALE,
            default_timezone='UTC',
            translation_directories='translations',
            locale_selector=self.locale_service.locale_selector_handler
        )

        # Initialize custom widget registry
        self.widget_registry = WidgetRegistryService(self)

    def startup(self):
        """Construct and show the Toga application.
        """
        logger.info(f"{self.formal_name} starting up...")

        # Create main window with default size (will be overridden by saved state if available)
        self.main_window = toga.MainWindow(title=self.formal_name, size=(740, 600))

        # Determine initial state and navigate there
        self.state_manager.initialize_app_state()

        # Show the main window
        self.main_window.show()

    def preferences(self, widget=None, **kwargs):
        """Show the settings window."""
        logger.info("Showing settings window")
        from beanquick.ui.preferences_window import show_preferences_window
        show_preferences_window(self)

    def about(self, widget=None, **kwargs):
        logger.info("Showing settings window")
        from beanquick.ui.about_window import show_about_window
        show_about_window(self)
        

def main():
    return Beanquick()
