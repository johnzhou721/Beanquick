from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import yaml
import logging
from pathlib import Path
from typing import Any


CONFIG_FILENAME = "app_settings.yaml"
KEY_FIRST_RUN_COMPLETE = "first_run_complete"
KEY_IS_SETUP_COMPLETE = "is_setup_complete"
KEY_USER_LOCALE = "user_locale"
KEY_ACTIVE_BEANCOUNT_FILE = "active_beancount_file"
KEY_WINDOW_STATE = "window_state"

logger = logging.getLogger(__name__)

class AppConfig:
    def __init__(self, app_paths):
        if hasattr(app_paths, 'config'):
            self.config_path: Path = app_paths.config / CONFIG_FILENAME
        else:
            base_path = Path(app_paths) if isinstance(app_paths, (str, Path)) else Path('.')
            self.config_path: Path = base_path / CONFIG_FILENAME
            logger.warning(f"AppConfig initialized outside app context or with raw path: {app_paths}. Using path: {self.config_path}")

        self.settings: dict[str, Any] = self._load_config()

    def _default_settings(self) -> dict[str, Any]:
        return {
            KEY_FIRST_RUN_COMPLETE: False,
            KEY_USER_LOCALE: None,
            KEY_ACTIVE_BEANCOUNT_FILE: None,
        }

    def _load_config(self) -> dict[str, Any]:
        defaults = self._default_settings()
        if not self.config_path.exists():
            logger.info(f"App config file {self.config_path} does not exist, using default settings.")
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                 logger.error(f"Failed to create directory for config file {self.config_path.parent}: {e}", exc_info=True)
            return defaults.copy()
            
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded_settings = yaml.safe_load(f)
                
                # Handle case where file is empty or contains invalid YAML resulting in None
                if loaded_settings is None:
                    logger.warning(f"Config file {self.config_path} is empty or invalid. Using default settings.")
                    return defaults.copy()
                
                # Ensure loaded_settings is a dictionary
                if not isinstance(loaded_settings, dict):
                     logger.error(f"Config file {self.config_path} does not contain a valid dictionary structure. Using default settings.")
                     return defaults.copy()

                final_settings = defaults.copy()
                final_settings.update(loaded_settings)
                
                # type checks for critical settings
                if not isinstance(final_settings[KEY_FIRST_RUN_COMPLETE], bool):
                    logger.warning(f"Config item '{KEY_FIRST_RUN_COMPLETE}' has incorrect type, resetting to default value.")
                    final_settings[KEY_FIRST_RUN_COMPLETE] = defaults[KEY_FIRST_RUN_COMPLETE]

                logger.info(f"App config file {self.config_path} loaded successfully.")
                return final_settings
        except (IOError, yaml.YAMLError, TypeError) as e: 
            logger.error(f"Loading app config file {self.config_path} failed: {e}. Using default settings.", exc_info=True)
            return defaults.copy()

    def save_config(self) -> bool:
        """Save current configuration to file.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.settings, f, default_flow_style=False, allow_unicode=True, sort_keys=False) 
            logger.info(f"App config file saved to {self.config_path}")
            return True
        except (IOError, yaml.YAMLError) as e: 
            logger.error(f"Saving app config file {self.config_path} failed: {e}. Settings may not be persisted.", exc_info=True)
            return False


    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any, auto_save: bool = True) -> None:
        """Set configuration item, with an option to auto-save."""
        logger.debug(f"Setting '{key}' to '{value}'")
        self.settings[key] = value
        if auto_save:
            if not self.save_config():
                logger.warning(f"Setting '{key}' failed to auto-save configuration.")

    def reset_to_defaults(self, auto_save: bool = True) -> None:
        """Reset all configuration to default values"""
        logger.warning("Resetting configuration to default values.")
        self.settings = self._default_settings()
        if auto_save:
            if not self.save_config():
                logger.warning("Failed to auto-save configuration after reset.")

    # Properties for specific settings
    @property
    def is_first_run_complete(self) -> bool:
        # Ensure correct type casting/handling in case of load failure/corruption
        return bool(self.get_setting(KEY_FIRST_RUN_COMPLETE, False))

    @is_first_run_complete.setter
    def is_first_run_complete(self, value: bool):
        self.set_setting(KEY_FIRST_RUN_COMPLETE, bool(value), auto_save=True) # Ensure boolean
    
    @property
    def is_setup_complete(self) -> bool:
        """Check if the setup is complete."""
        return bool(self.get_setting(KEY_IS_SETUP_COMPLETE, False))
    
    @is_setup_complete.setter
    def is_setup_complete(self, value: bool):
        """Set the setup completion status."""
        self.set_setting(KEY_IS_SETUP_COMPLETE, bool(value), auto_save=True)
    
    @property
    def user_locale(self) -> str | None:
        loc = self.get_setting(KEY_USER_LOCALE)
        return loc if isinstance(loc, str) else None # Ensure correct type

    @user_locale.setter
    def user_locale(self, value: str | None):
         # Ensure value is string or None before setting
        valid_value = str(value) if value is not None else None
        # Only set if the value actually changes
        if self.get_setting(KEY_USER_LOCALE) != valid_value:
            self.set_setting(KEY_USER_LOCALE, valid_value, auto_save=True)
    
    @property
    def active_beancount_file(self) -> str | None:
        """Get the currently active Beancount file, if any."""
        active_file = self.get_setting(KEY_ACTIVE_BEANCOUNT_FILE)
        return active_file
    
    @active_beancount_file.setter
    def active_beancount_file(self, file_path: str | None) -> None:
        new_active_file = None
        abs_file_path = None
        if file_path is not None:
            try:
                # Normalize path before checking/setting
                abs_file_path = str(Path(file_path).resolve())
            except OSError as e:
                 logger.error(f"Could not resolve path '{file_path}' to set as active file: {e}")
                 return

            if not Path(abs_file_path).is_file():
                # Do not change the active file if the new path is invalid.
                return
            
            new_active_file = abs_file_path

         # Only update and save if the value has actually changed
        if self.get_setting(KEY_ACTIVE_BEANCOUNT_FILE) != new_active_file:
            self.set_setting(KEY_ACTIVE_BEANCOUNT_FILE, new_active_file, auto_save=True)

    def get_window_state(self) -> dict[str, int] | None:
        """Get the saved window state (position and size)."""
        window_state = self.get_setting(KEY_WINDOW_STATE)
        if isinstance(window_state, dict):
            # Validate that all required keys are present and are floats
            required_keys = ['x', 'y', 'width', 'height']
            if all(key in window_state and isinstance(window_state[key], float) for key in required_keys):
                return window_state
        return None

    def set_window_state(self, window_state: dict[str, int]) -> None:
        """Save the current window state (position and size)."""
        if not isinstance(window_state, dict):
            logger.warning("Invalid window state format, expected dict")
            return
        
        # Validate required keys
        required_keys = ['x', 'y', 'width', 'height']
        if not all(key in window_state and isinstance(window_state[key], float) for key in required_keys):
            logger.warning("Invalid window state format, missing or invalid keys")
            return
        
        # Only save if the state has actually changed
        current_state = self.get_setting(KEY_WINDOW_STATE)
        if current_state != window_state:
            self.set_setting(KEY_WINDOW_STATE, window_state, auto_save=True)
        
