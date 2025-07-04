from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import yaml
import logging
from pathlib import Path
from typing import Any, Optional


CONFIG_FILENAME = "app_settings.yaml" 
KEY_FIRST_RUN_COMPLETE = "first_run_complete"
KEY_IS_SETUP_COMPLETE = "is_setup_complete"

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
