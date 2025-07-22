from __future__ import annotations

import locale
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beanquick.config import AppConfig


class LocaleService:
    """
    Handles locale detection and selection for the application.
    """
    def __init__(self, config: AppConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def get_system_locale_code(self) -> str:
        """
        Safely attempts to detect the system's default locale language code.
        Falls back to 'en' if detection fails.
        """
        default_fallback = 'en'
        try:
            lang_code, encoding = locale.getlocale()
            if lang_code:
                # Format needed by Babel (e.g., 'en_US', 'fr_FR')
                # Replace '-' often used in LANG (e.g., 'zh-CN') with '_'
                formatted_code = lang_code.replace('-', '_')
                self.logger.info(f"Detected system locale via getlocale: {formatted_code} (from {lang_code})")
                return formatted_code
            else:
                self.logger.warning("Could not detect system locale via getlocale. Falling back.")
                return default_fallback
        except ValueError:
            self.logger.warning("ValueError detecting system locale. Falling back.")
            return default_fallback
        except Exception as e:
            self.logger.error(f"Unexpected error detecting system locale: {e}. Falling back.", exc_info=True)
            return default_fallback

    def locale_selector_handler(self) -> str:
        """
        Selects locale: checks settings first, then falls back to system locale.
        This function will be passed to TogaBabel.init_app.
        """
        # Reading the preferred locale from Toga settings
        stored_locale = self.config.user_locale

        if stored_locale and isinstance(stored_locale, str) and stored_locale.strip():
            self.logger.info(f"Using locale from settings: '{stored_locale}'")
            return stored_locale

        # If not found or empty in settings, detect and use system locale
        system_locale = self.get_system_locale_code()
        self.logger.info(f"Using detected system locale: '{system_locale}'")
        return system_locale
