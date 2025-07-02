"""
Beancounting, faster. For the novice. For the expert. For you.
"""
from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import logging

import toga

from beanquick.services.logging import get_logger, setup_logging


logger = get_logger()

class Beanquick(toga.App):
    def __init__(self, formal_name="Beanquick", app_id="com.twobitsware.beanbot", **kwargs):
        """
        Initialize the Beanquick application.
        """
        super().__init__(formal_name, app_id, **kwargs)

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

        logger.info(f"{self.formal_name} starting up...")

    def startup(self):
        """Construct and show the Toga application.

        Usually, you would add your application to a main content box.
        We then create a main window (with a name matching the app), and
        show the main window.
        """
        main_box = toga.Box()

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()


def main():
    return Beanquick()
