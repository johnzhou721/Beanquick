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
KEY_BEANCOUNT_FILES = "beancount_files"
KEY_ACTIVE_BEANCOUNT_FILE = "active_beancount_file"

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
            KEY_BEANCOUNT_FILES: [],
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
    def beancount_files(self) -> list[str]:
        """Get the list of Beancount files."""
        files = self.get_setting(KEY_BEANCOUNT_FILES, [])
        return files if isinstance(files, list) else []
    
    @property
    def active_beancount_file(self) -> str | None:
        """Get the currently active Beancount file, if any."""
        # Ensure the stored value (if present) is actually in the list of files
        active_file = self.get_setting(KEY_ACTIVE_BEANCOUNT_FILE)
        if active_file and active_file in self.beancount_files:
            return active_file
        elif self.beancount_files: # If no active file is set, return the most recent one
            logger.debug("No active Beancount file set, returning most recent file.")
            self.active_beancount_file = self.beancount_files[-1]
            return self.beancount_files[-1]
        return None
    
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
                # Save config if it was modified by an add_beancount_file attempt that failed before this check.
                if not self.save_config(): logger.warning("Config save failed after invalid active file attempt.")
                return
            
            # Use property getter which handles list validation
            current_files = self.beancount_files 
            if abs_file_path not in self.beancount_files:
                logger.info(f"Active file '{abs_file_path}' not in known files. Adding it.")
                # Use the add_beancount_file logic to also handle recency
                # set_active=False here to avoid recursion with this setter, we'll set it below.
                self.add_beancount_file(abs_file_path, set_active=False)
                # add_beancount_file now handles its own saving, or defers to this setter.
            
            # Ensure it's at the end of the list for recency
            current_files = self.beancount_files
            if abs_file_path in current_files:
                updated_files = [f for f in current_files if f != abs_file_path]
                updated_files.append(abs_file_path)
                if updated_files != current_files:
                    self.set_setting(KEY_BEANCOUNT_FILES, updated_files, auto_save=False) # Defer save
            
            new_active_file = abs_file_path

         # Only update and save if the value has actually changed
        if self.get_setting(KEY_ACTIVE_BEANCOUNT_FILE) != new_active_file:
            self.set_setting(KEY_ACTIVE_BEANCOUNT_FILE, new_active_file, auto_save=True)
        elif not self.save_config(): # If other changes (like beancount_files list) occurred, ensure save
             logger.warning(f"Config save failed in active_beancount_file setter even if active file itself didn't change.")

    def add_beancount_file(self, file_path: str, set_active: bool = False) -> bool:
        """Adds a Beancount file to the list if it's valid and not already present. 
           Moves the file to the end of the list if it already exists (to mark as most recent).
           Returns True if added or moved. 
        """
        try:
            abs_file_path = str(Path(file_path).resolve())
        except OSError as e:
            logger.error(f"Failed to resolve path for {file_path}: {e}", exc_info=True)
            return False
        
        if not Path(abs_file_path).is_file():
            logger.error(f"File {abs_file_path} does not exist or is not a file.")
            return False
        
        # Early return if the file is already at the end (most recent)
        current_files = self.beancount_files
        if current_files and current_files[-1] == abs_file_path and not set_active:
            logger.debug(f"File {abs_file_path} is already the most recent, not adding.")
            return True
        
        # Update the list of files
        updated_files = [f for f in current_files if f != abs_file_path]
        updated_files.append(abs_file_path)
        self.set_setting(KEY_BEANCOUNT_FILES, updated_files, auto_save=False)

        # Handle active file setting if needed
        should_set_active = set_active or self.active_beancount_file is None

        if should_set_active:
            self.active_beancount_file = abs_file_path
        else:
            if not self.save_config():
                logger.warning("Failed to auto-save configuration after adding Beancount file.")

        logger.info(f"Ensured Beancount file is in list and marked as recent: {abs_file_path}")
        return True
    
    def remove_beancount_file(self, file_path: str, update_active: bool = False) -> bool:
        """Removes a Beancount file from the list. Returns True if removed."""
        try:
            # Normalize path for comparison
            abs_file_path = str(Path(file_path).resolve()) 
        except OSError as e:
            logger.warning(f"Could not resolve file path for removal '{file_path}': {e}")
            return False

        current_files = self.beancount_files
        if abs_file_path in current_files:
            updated_files = [f for f in current_files if f != abs_file_path]
            self.set_setting(KEY_BEANCOUNT_FILES, updated_files, auto_save=False) # Defer save
            logger.info(f"Removed Beancount file: {abs_file_path}")
            # Update active file if the removed one was active
            if update_active and self.active_beancount_file == abs_file_path:
                self.active_beancount_file = updated_files[-1] if updated_files else None
            elif not self.save_config(): # Save if active file not changed by setter
                 logger.warning(f"Failed to auto-save configuration after removing file.")
            return True
        logger.warning(f"Attempting to remove non-existent Beancount file: {abs_file_path}")
        return False
        
