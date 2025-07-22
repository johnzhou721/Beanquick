"""
    This module provides internationalization(i18n) and localization(l10n) support for Toga applications based on Babel.
    
"""
__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import os
import logging
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from contextlib import contextmanager
from typing import List, Callable, Optional, Union, Dict, Tuple, Any

from babel.support import Translations, NullTranslations
from babel import dates, numbers, support, Locale
from babel.core import UnknownLocaleError
from pytz import timezone, UTC, UnknownTimeZoneError

import toga

# --- Logging ---
logger = logging.getLogger(__name__)

class LazyString:
    """A string that evaluates lazily using the configured TogaBabel instance."""
    def __init__(self, func_name: str, *args: Any, **kwargs: Any):
        self._func_name = func_name
        self._args = args
        self._kwargs = kwargs
        self._cached = None

    def _resolve(self) -> str:
        if self._cached is None:
            instance = get_babel_instance()
            func = getattr(instance, self._func_name)
            try:
                self._cached = str(func(*self._args, **self._kwargs))
            except Exception as e:
                logger.error(f"Error resolving LazyString for {self._func_name}: {e}", exc_info=True)
                # return a representation for debugging
                self._cached = f"<LazyString Error: {e}>"
        return self._cached

    # Proxy methods
    def __str__(self): return self._resolve()
    def __repr__(self): return f'l"{self._resolve()}"'
    def __getattr__(self, name): return getattr(self._resolve(), name)
    def __len__(self): return len(self._resolve())
    def __mod__(self, other): return self._resolve() % other
    def __eq__(self, other): return self._resolve() == other
    def __hash__(self): return hash(self._resolve())
    def __html__(self): return self._resolve()

# --- Configuration Dataclass ---
@dataclass
class TogaBabelConfig:
    """Internal configuration storage."""
    app: toga.App
    default_locale_str: str
    default_timezone_str: str
    default_domain: str
    translation_directories: List[str]
    date_formats: Dict[str, Optional[str]]
    locale_selector: Optional[Callable[[], str]] = None
    timezone_selector: Optional[Callable[[], Union[str, timezone]]] = None

# --- Main TogaBabel Class ---
class TogaBabel:
    """
    Central controller class for Toga/BeeWare i18n/l10n.

    Manages configuration, current locale/timezone state, translation loading,
    and formatting functions.
    """
    # Default date formats (can be customized via init_app)
    default_date_formats: Dict[str, Optional[str]] = {
        "time": "medium", "date": "medium", "datetime": "medium",
        "time.short": None, "time.medium": None, "time.full": None, "time.long": None,
        "date.short": None, "date.medium": None, "date.full": None, "date.long": None,
        "datetime.short": None, "datetime.medium": None, "datetime.full": None, "datetime.long": None,
    }

    def __init__(self):
        self._config: Optional[TogaBabelConfig] = None
        self._current_locale: Optional[Locale] = None
        self._current_timezone: Optional[timezone] = None
        # Cache: Key=(locale_str, domain_str), Value=Translations
        self._translations_cache: Dict[Tuple[str, str], Union[Translations, NullTranslations]] = {}
        self._is_initialized: bool = False
        self._forced_locale: Optional[Locale] = None # For force_locale context manager

        # Signal infrastructure
        self._locale_change_listeners: List[Callable[[str], None]] = []


    def _check_initialized(self):
        """Raise RuntimeError if init_app was not called."""
        if not self._is_initialized or self._config is None:
            raise RuntimeError(
                "TogaBabel is not initialized. Call init_app(app, ...) first."
            )

    # --- Initialization ---
    def init_app(
        self,
        app: toga.App,
        default_locale: str = "en",
        default_timezone: str = "UTC",
        default_domain: str = "messages",
        translation_directories: Union[str, List[str]] = "translations",
        date_formats_override: Optional[Dict[str, Optional[str]]] = None,
        locale_selector: Optional[Callable[[], str]] = None,
        timezone_selector: Optional[Callable[[], Union[str, timezone]]] = None,
    ):
        """
        Initializes TogaBabel for the given Toga App.

        Should be called once during app startup.
        """
        if self._is_initialized:
            logger.warning("TogaBabel already initialized. Ignoring subsequent call.")
            return

        # Resolve translation directories
        if isinstance(translation_directories, str):
            dirs_list = [translation_directories]
        else:
            dirs_list = translation_directories or []
        resolved_dirs = list(self._resolve_directories(dirs_list, app))

        # Combine date formats
        final_date_formats = self.default_date_formats.copy()
        if date_formats_override:
            final_date_formats.update(date_formats_override)

        # Store configuration
        self._config = TogaBabelConfig(
            app=app,
            default_locale_str=default_locale,
            default_timezone_str=default_timezone,
            default_domain=default_domain,
            translation_directories=resolved_dirs,
            date_formats=final_date_formats,
            locale_selector=locale_selector,
            timezone_selector=timezone_selector,
        )

        # Perform initial locale/timezone determination
        try:
            self._current_locale = self._determine_locale()
            self._current_timezone = self._determine_timezone()
        except Exception as e:
             logger.exception("Error during initial locale/timezone determination. Using defaults.", exc_info=True)
             # Ensure defaults are set even if determination fails
             self._current_locale = self._get_default_locale()
             self._current_timezone = self._get_default_timezone()


        self._is_initialized = True
        logger.info(
            f"TogaBabel initialized: Locale={self._current_locale}, "
            f"Timezone={self._current_timezone}"
        )

        # Register this instance globally for shortcut functions
        _register_instance(self)


    @staticmethod
    def _resolve_directories(directories: List[str], app: toga.App) -> List[str]:
        """Resolves translation directory paths relative to the app path."""
        resolved = []
        if app is None or app.paths is None:
            logger.warning("Cannot resolve relative paths: Toga App or app.paths not available.")
            # just return absolute paths as-is and log warning for relative.
            for path in directories:
                if os.path.isabs(path):
                    resolved.append(path)
                else:
                    logger.warning(f"Cannot resolve relative path '{path}' without app context. Skipping.")
            return resolved

        for path in directories:
            try:
                 if not os.path.isabs(path):
                     # Use app.paths.app for relative paths
                     abs_path = os.path.abspath(os.path.join(app.paths.app, path))
                 else:
                     abs_path = os.path.abspath(path)
                 resolved.append(abs_path)
            except Exception as e:
                 logger.error(f"Error resolving path '{path}': {e}", exc_info=True)
        return resolved

    # --- Locale and Timezone Determination ---

    def _get_default_locale(self) -> Locale:
        """Parses the default locale string, falling back gracefully."""
        if self._config is None:
             logger.error("Cannot get default locale: config not set.")
             return Locale.parse("en")
        try:
            return Locale.parse(self._config.default_locale_str)
        except (ValueError, UnknownLocaleError) as e:
            logger.error(
                f"Invalid default locale '{self._config.default_locale_str}': {e}. "
                f"Falling back to 'en'."
            )
            return Locale.parse("en")

    def _get_default_timezone(self) -> timezone:
        """Parses the default timezone string, falling back gracefully."""
        if self._config is None:
             logger.error("Cannot get default timezone: config not set.")
             return UTC
        try:
            return timezone(self._config.default_timezone_str)
        except UnknownTimeZoneError as e:
            logger.error(
                f"Invalid default timezone '{self._config.default_timezone_str}': {e}. "
                f"Falling back to UTC."
            )
            return UTC

    def _determine_locale(self) -> Locale:
        """Gets locale using selector or default, handling errors."""
        if self._config is None:
             logger.error("Cannot determine locale: config not set.")
             return Locale.parse("en")
        selected_locale_str = None
        if self._config.locale_selector:
            try:
                selected_locale_str = self._config.locale_selector()
                if selected_locale_str:
                    try:
                         return Locale.parse(selected_locale_str)
                    except (ValueError, UnknownLocaleError) as e:
                         logger.warning(
                             f"Locale selector returned invalid locale '{selected_locale_str}': {e}. "
                             f"Falling back to default."
                         )
                else:
                     logger.debug("Locale selector returned None or empty string. Falling back to default.")
            except Exception as e:
                logger.exception("Error in locale selector. Falling back to default.", exc_info=True)

        # Fallback to default
        return self._get_default_locale()

    def _determine_timezone(self) -> timezone:
        """Gets timezone using selector or default, handling errors."""
        if self._config is None:
             logger.error("Cannot determine timezone: config not set.")
             return UTC
        selected_tz = None
        if self._config.timezone_selector:
            try:
                selected_tz = self._config.timezone_selector()
                if selected_tz:
                    try:
                        if isinstance(selected_tz, str):
                            return timezone(selected_tz)
                        elif hasattr(selected_tz, 'zone') and hasattr(selected_tz, 'localize'): # Check if it looks like a pytz timezone
                            return selected_tz
                        else:
                             logger.warning(
                                 f"Timezone selector returned unexpected type '{type(selected_tz)}'. "
                                 f"Falling back to default."
                             )
                    except UnknownTimeZoneError as e:
                        logger.warning(
                            f"Timezone selector returned invalid timezone '{selected_tz}': {e}. "
                            f"Falling back to default."
                        )
                    except Exception as e: # Catch other potential errors from pytz
                         logger.warning(
                             f"Error processing timezone selector result '{selected_tz}': {e}. "
                             f"Falling back to default."
                         )
                else:
                     logger.debug("Timezone selector returned None or empty value. Falling back to default.")
            except Exception as e:
                logger.exception("Error in timezone selector. Falling back to default.", exc_info=True)

        # Fallback to default
        return self._get_default_timezone()

    # --- Public API for Locale/Timezone ---

    def get_locale(self) -> Locale:
        """Gets the currently active locale for the application."""
        self._check_initialized()
        # Return forced locale if active
        if self._forced_locale:
            return self._forced_locale
        # Re-determine if not set (should be set by init or set_locale)
        if self._current_locale is None:
            logger.warning("Current locale not set, re-determining. This shouldn't normally happen after init.")
            self._current_locale = self._determine_locale()
        return self._current_locale

    def get_timezone(self) -> timezone:
        """Gets the currently active timezone for the application."""
        self._check_initialized()
         # Re-determine if not set (should be set by init or set_timezone)
        if self._current_timezone is None:
            logger.warning("Current timezone not set, re-determining. This shouldn't normally happen after init.")
            self._current_timezone = self._determine_timezone()
        return self._current_timezone

    def set_locale(self, locale_str: str):
        """
        Explicitly sets the current locale for the application.

        Clears translation cache and notifies listeners.
        """
        self._check_initialized()
        try:
            new_locale = Locale.parse(locale_str)
            if self._current_locale != new_locale:
                logger.info(f"Setting locale from {self._current_locale} to {new_locale}")
                self._current_locale = new_locale
                self.clear_cache()
                self._notify_locale_change(str(new_locale))
            else:
                 logger.debug(f"Locale already set to {new_locale}. No change.")
        except (ValueError, UnknownLocaleError) as e:
            logger.error(f"Cannot set invalid locale '{locale_str}': {e}")
        except Exception as e:
            logger.exception(f"Error setting locale to '{locale_str}': {e}", exc_info=True)


    def set_timezone(self, tz_identifier: Union[str, timezone]):
        """Explicitly sets the current timezone for the application."""
        self._check_initialized()
        try:
            new_tz = timezone(tz_identifier) if isinstance(tz_identifier, str) else tz_identifier
            # Basic validation if it's not a string
            if not isinstance(new_tz, type(UTC)) or not hasattr(new_tz,'zone'):
                 raise ValueError("Invalid timezone object provided.")

            if self._current_timezone != new_tz:
                logger.info(f"Setting timezone from {self._current_timezone} to {new_tz}")
                self._current_timezone = new_tz
                self.clear_cache()
                self._notify_timezone_change(str(new_tz))
            else:
                logger.debug(f"Timezone already set to {new_tz}. No change.")
        except UnknownTimeZoneError as e:
             logger.error(f"Cannot set invalid timezone identifier '{tz_identifier}': {e}")
        except Exception as e:
            logger.exception(f"Error setting timezone to '{tz_identifier}': {e}", exc_info=True)

    def refresh(self):
        """
        Re-determines locale and timezone using selectors (if configured)
        or defaults, and clears the translation cache.
        """
        self._check_initialized()
        logger.debug("Refreshing locale and timezone...")
        self._current_locale = self._determine_locale()
        self._current_timezone = self._determine_timezone()
        self.clear_cache()
        logger.info(f"TogaBabel refreshed: Locale={self._current_locale}, Timezone={self._current_timezone}")
        # Notify listeners after refresh
        self._notify_locale_change(str(self._current_locale))


    @contextmanager
    def force_locale(self, locale: str):
        """
        Temporarily overrides the locale for the enclosed block.
        """
        self._check_initialized()
        original_locale = self._current_locale
        original_forced = self._forced_locale

        try:
            forced = Locale.parse(locale)
            self._forced_locale = forced
            logger.debug(f"Forcing locale to: {forced}")
            # Clear cache entries potentially affected by the forced locale
            # (More precise than clearing all might be better, but harder)
            self.clear_cache()
            yield
        except (ValueError, UnknownLocaleError) as e:
            logger.error(f"Cannot force invalid locale '{locale}': {e}")
            yield # Still yield to allow context manager to exit
        except Exception as e:
             logger.exception(f"Error forcing locale to '{locale}': {e}", exc_info=True)
             yield # Still yield
        finally:
            logger.debug(f"Restoring locale after force_locale (was {original_locale})")
            self._forced_locale = original_forced


    # --- Translation Loading ---

    def _load_translations(self, locale: Locale, domain: str) -> Union[Translations, NullTranslations]:
        """Loads translations for a specific locale and domain."""
        self._check_initialized()
        cache_key = (str(locale), domain)

        if cache_key in self._translations_cache:
            return self._translations_cache[cache_key]

        logger.debug(f"Cache miss for {cache_key}. Loading translations...")
        final_translations: Union[Translations, NullTranslations] = NullTranslations()
        loaded_catalog: Optional[Translations] = None
        found_translation = False

        for dirname in self._config.translation_directories:
            catalog = None
            try:
                logger.debug(f"Attempting load: Dir='{dirname}', Locale='{locale}', Domain='{domain}'")
                catalog = support.Translations.load(dirname, [locale], domain)

                if isinstance(catalog, Translations):
                    logger.debug(f"Successfully loaded translations from '{dirname}' for {cache_key}")
                    if found_translation:
                        # Merge if we already found translations elsewhere
                        if isinstance(final_translations, NullTranslations):
                             # This case should ideally not happen if found_translation is True, but defensively...
                             final_translations = catalog
                        else:
                             final_translations.merge(catalog)
                        logger.debug(f"Merged translations from '{dirname}'")
                    else:
                        # This is the first valid translation found
                        final_translations = catalog
                    # Keep track of the last successfully loaded catalog for plural fix
                    loaded_catalog = catalog
                    found_translation = True
                else:
                    logger.debug(f"No translations found in '{dirname}' for {cache_key}")

            except FileNotFoundError:
                 logger.debug(f"Directory not found: '{dirname}'. Skipping.")
            except Exception as e:
                logger.exception(f"Error loading translations from '{dirname}' for {cache_key}: {e}", exc_info=True)


        # Apply plural forms workaround if needed (copied from Flask-Babel)
        if loaded_catalog and hasattr(loaded_catalog, 'plural') and isinstance(final_translations, Translations):
             # Ensure final_translations is not Null before trying to set attributes
             if hasattr(final_translations, 'plural'):
                 try:
                     # Accessing potentially "private" attributes - relies on Babel internals
                     final_translations._num_plurals = loaded_catalog._num_plurals
                     final_translations._plural_expr = loaded_catalog._plural_expr
                 except AttributeError:
                     logger.warning("Could not apply plural workaround: attributes missing.")
             else:
                  logger.warning("Could not apply plural workaround: final_translations object lacks 'plural'.")


        logger.debug(f"Caching result for {cache_key}: Type={type(final_translations)}")
        self._translations_cache[cache_key] = final_translations
        return final_translations


    def get_translations(self, domain: Optional[str] = None) -> Union[Translations, NullTranslations]:
        """
        Gets the Translations object for the current locale and the specified
        or default domain.
        """
        self._check_initialized()
        current_locale = self.get_locale() # Ensures locale is determined
        target_domain = domain or self._config.default_domain
        return self._load_translations(current_locale, target_domain)

    def clear_cache(self):
        """Clears the internal translations cache."""
        logger.debug("Clearing translations cache.")
        self._translations_cache.clear()

    # --- Core Translation Methods ---

    def gettext(self, string: str, domain: Optional[str] = None, **variables) -> str:
        """Translates a string using the current locale."""
        self._check_initialized()
        t = self.get_translations(domain)
        s = t.ugettext(string) # Use ugettext for Unicode
        return s if not variables else s % variables

    def ngettext(self, singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> str:
        """Translates a pluralizable string."""
        self._check_initialized()
        variables.setdefault("num", num)
        t = self.get_translations(domain)
        s = t.ungettext(singular, plural, num)
        return s if not variables else s % variables

    def pgettext(self, context: str, string: str, domain: Optional[str] = None, **variables) -> str:
        """Translates a string with context."""
        self._check_initialized()
        t = self.get_translations(domain)
        s = t.upgettext(context, string)
        return s if not variables else s % variables

    def npgettext(self, context: str, singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> str:
        """Translates a pluralizable string with context."""
        self._check_initialized()
        variables.setdefault("num", num)
        t = self.get_translations(domain)
        s = t.unpgettext(context, singular, plural, num)
        return s if not variables else s % variables

    # --- Lazy Translation Methods ---

    def lazy_gettext(self, string: str, domain: Optional[str] = None, **variables) -> LazyString:
        """Lazy version of gettext."""
        # Pass method name and arguments to LazyString
        return LazyString("gettext", string, domain=domain, **variables)

    def lazy_ngettext(self, singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> LazyString:
        """Lazy version of ngettext."""
        return LazyString("ngettext", singular, plural, num, domain=domain, **variables)

    def lazy_pgettext(self, context: str, string: str, domain: Optional[str] = None, **variables) -> LazyString:
        """Lazy version of pgettext."""
        return LazyString("pgettext", context, string, domain=domain, **variables)

    def lazy_npgettext(self, context: str, singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> LazyString:
        """Lazy version of npgettext."""
        return LazyString("npgettext", context, singular, plural, num, domain=domain, **variables)


    # --- Formatting Methods ---

    def _get_format(self, key: str, format_specifier: Optional[str]) -> Optional[str]:
        """Helper to look up date/time format defaults from config."""
        self._check_initialized()
        formats = self._config.date_formats

        if format_specifier is None:
            format_specifier = formats.get(key, 'medium')

        if format_specifier in ("short", "medium", "full", "long"):
            specific_format_key = f"{key}.{format_specifier}"
            rv = formats.get(specific_format_key)
            if rv is not None:
                format_specifier = rv
        return format_specifier

    def to_user_timezone(self, dt: datetime) -> datetime:
        """Converts a datetime object to the user's current timezone."""
        self._check_initialized()
        tzinfo = self.get_timezone() # Ensures timezone is determined
        if dt.tzinfo is None:
            dt = UTC.localize(dt) # Assume UTC if naive
        return tzinfo.normalize(dt.astimezone(tzinfo))

    def to_utc(self, dt: datetime) -> datetime:
        """Converts a datetime object to UTC and makes it naive."""
        self._check_initialized()
        if dt.tzinfo is None:
            tzinfo = self.get_timezone()
            try:
                 dt = tzinfo.localize(dt, is_dst=None) # Handle ambiguity if needed
            except Exception as e:
                 logger.warning(f"Could not localize naive datetime {dt} with tz {tzinfo}: {e}. Assuming UTC.")
                 dt = UTC.localize(dt)
        return dt.astimezone(UTC).replace(tzinfo=None)

    def _date_format(self, formatter: Callable, obj: Optional[Union[datetime, date, time]], format_specifier: Optional[str], rebase: bool, **extra) -> str:
        """Internal helper for date/time formatting."""
        self._check_initialized()
        locale = self.get_locale()
        tzinfo = None

        if obj is None:
            if formatter in (dates.format_datetime, dates.format_date, dates.format_time):
                 obj = datetime.now() # Use current time if None
            else:
                 return "" # Should not happen for timedelta etc.

        # Handle rebasing (converting to user timezone)
        if formatter is not dates.format_date and rebase:
            tzinfo = self.get_timezone()
            if isinstance(obj, datetime):
                obj = self.to_user_timezone(obj)
            # If time object, babel handles tzinfo if passed

        # Add tzinfo to extra args for formatters that use it
        if tzinfo and formatter in (dates.format_datetime, dates.format_time):
            extra['tzinfo'] = tzinfo

        # Type adjustments for formatters
        if formatter is dates.format_date and isinstance(obj, datetime):
            obj = obj.date()
        # No adjustment needed for time/datetime as format_time handles datetime

        try:
            return formatter(obj, format_specifier, locale=locale, **extra)
        except Exception as e:
            logger.exception(f"Error during Babel formatting ({formatter.__name__}): {e}", exc_info=True)
            return f"<Format Error: {e}>" # Return error indicator


    def format_datetime(self, dt: Optional[datetime] = None, format: Optional[str] = None, rebase: bool = True) -> str:
        """Formats a datetime object."""
        format_specifier = self._get_format("datetime", format)
        return self._date_format(dates.format_datetime, dt, format_specifier, rebase)

    def format_date(self, d: Optional[Union[datetime, date]] = None, format: Optional[str] = None, rebase: bool = True) -> str:
        """Formats a date object (or the date part of a datetime)."""
        format_specifier = self._get_format("date", format)
        return self._date_format(dates.format_date, d, format_specifier, rebase)

    def format_time(self, t: Optional[Union[datetime, time]] = None, format: Optional[str] = None, rebase: bool = True) -> str:
        """Formats a time object (or the time part of a datetime)."""
        format_specifier = self._get_format("time", format)
        return self._date_format(dates.format_time, t, format_specifier, rebase)

    def format_timedelta(self, delta: Union[datetime, timedelta], granularity: str = "second", add_direction: bool = False, threshold: float = 0.85) -> str:
        """Formats a timedelta or the difference between a datetime and now."""
        self._check_initialized()
        locale = self.get_locale()
        if isinstance(delta, datetime):
            now_aware = datetime.now(self.get_timezone())
            delta_aware = delta if delta.tzinfo else self.to_user_timezone(delta) # Make delta aware
            # Ensure comparison happens with aware objects
            actual_delta = now_aware - delta_aware.astimezone(now_aware.tzinfo)
        else: # It's already a timedelta
            actual_delta = delta

        try:
            return dates.format_timedelta(
                actual_delta, granularity=granularity, threshold=threshold,
                add_direction=add_direction, locale=locale,
            )
        except Exception as e:
            logger.exception(f"Error formatting timedelta: {e}", exc_info=True)
            return f"<Delta Format Error: {e}>"

    def format_number(self, number, format=None) -> str:
        """Formats a number (decimal) using the current locale."""
        self._check_initialized()
        locale = self.get_locale()
        try:
            return numbers.format_decimal(number, format=format, locale=locale)
        except Exception as e:
             logger.exception(f"Error formatting number: {e}", exc_info=True)
             return f"<Num Format Error: {e}>"

    def format_currency(self, number, currency: str, format=None, currency_digits=True, format_type="standard") -> str:
        """Formats a number as currency using the current locale."""
        self._check_initialized()
        locale = self.get_locale()
        try:
            return numbers.format_currency(
                number, currency, format=format, locale=locale,
                currency_digits=currency_digits, format_type=format_type,
            )
        except Exception as e:
             logger.exception(f"Error formatting currency: {e}", exc_info=True)
             return f"<Currency Format Error: {e}>"

    def format_percent(self, number, format=None) -> str:
        """Formats a number as a percentage using the current locale."""
        self._check_initialized()
        locale = self.get_locale()
        try:
            return numbers.format_percent(number, format=format, locale=locale)
        except Exception as e:
             logger.exception(f"Error formatting percent: {e}", exc_info=True)
             return f"<Percent Format Error: {e}>"

    def format_scientific(self, number, format=None) -> str:
        """Formats a number using scientific notation using the current locale."""
        self._check_initialized()
        locale = self.get_locale()
        try:
            return numbers.format_scientific(number, format=format, locale=locale)
        except Exception as e:
             logger.exception(f"Error formatting scientific: {e}", exc_info=True)
             return f"<Sci Format Error: {e}>"

    # --- Signal Handling ---
    def connect_locale_changed(self, func: Callable[[str], None]):
        """Register a listener function to be called when the locale changes."""
        if func not in self._locale_change_listeners:
            self._locale_change_listeners.append(func)

    def disconnect_locale_changed(self, func: Callable[[str], None]):
        """Unregister a locale change listener."""
        try:
            self._locale_change_listeners.remove(func)
        except ValueError:
            pass # Function not connected

    def _notify_locale_change(self, new_locale_str: str):
        """Notify all registered listeners about the locale change."""
        logger.debug(f"Notifying {len(self._locale_change_listeners)} listeners of locale change to {new_locale_str}")
        # Iterate over a copy in case listeners modify the list during notification
        for listener in self._locale_change_listeners[:]:
            try:
                listener(new_locale_str)
            except Exception as e:
                logger.exception(f"Error in locale change listener {listener}: {e}", exc_info=True)


# --- Global Instance Management ---
_instance: Optional[TogaBabel] = None

def _register_instance(instance: TogaBabel):
    """Registers the TogaBabel instance for global shortcuts."""
    global _instance
    if _instance is not None:
        logger.warning("Overwriting existing global TogaBabel instance.")
    _instance = instance

def get_babel_instance() -> TogaBabel:
    """Gets the globally registered TogaBabel instance."""
    if _instance is None:
        # This indicates init_app was likely never called or failed silently
        raise RuntimeError(
            "TogaBabel instance not available. Ensure init_app() was called successfully."
        )
    return _instance

# --- Global Shortcut Functions ---
# These functions delegate to the globally registered TogaBabel instance

def gettext(string: str, domain: Optional[str] = None, **variables) -> str:
    return get_babel_instance().gettext(string, domain=domain, **variables)

_ = gettext # Common alias

def ngettext(singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> str:
    return get_babel_instance().ngettext(singular, plural, num, domain=domain, **variables)

def pgettext(context: str, string: str, domain: Optional[str] = None, **variables) -> str:
    return get_babel_instance().pgettext(context, string, domain=domain, **variables)

def npgettext(context: str, singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> str:
    return get_babel_instance().npgettext(context, singular, plural, num, domain=domain, **variables)

# --- Lazy Global Shortcuts ---
def lazy_gettext(string: str, domain: Optional[str] = None, **variables) -> LazyString:
    return LazyString("gettext", string, domain=domain, **variables)

_L = lazy_gettext # Common alias

def lazy_ngettext(singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> LazyString:
    return LazyString("ngettext", singular, plural, num, domain=domain, **variables)

def lazy_pgettext(context: str, string: str, domain: Optional[str] = None, **variables) -> LazyString:
    return LazyString("pgettext", context, string, domain=domain, **variables)

def lazy_npgettext(context: str, singular: str, plural: str, num: int, domain: Optional[str] = None, **variables) -> LazyString:
    return LazyString("npgettext", context, singular, plural, num, domain=domain, **variables)

# --- Global Formatting Shortcuts ---
def format_datetime(dt: Optional[datetime] = None, format: Optional[str] = None, rebase: bool = True) -> str:
    return get_babel_instance().format_datetime(dt, format=format, rebase=rebase)

def format_date(d: Optional[Union[datetime, date]] = None, format: Optional[str] = None, rebase: bool = True) -> str:
    return get_babel_instance().format_date(d, format=format, rebase=rebase)

def format_time(t: Optional[Union[datetime, time]] = None, format: Optional[str] = None, rebase: bool = True) -> str:
    return get_babel_instance().format_time(t, format=format, rebase=rebase)

def format_timedelta(delta: Union[datetime, timedelta], granularity: str = "second", add_direction: bool = False, threshold: float = 0.85) -> str:
    return get_babel_instance().format_timedelta(delta, granularity=granularity, add_direction=add_direction, threshold=threshold)

def format_number(number, format=None) -> str:
    return get_babel_instance().format_number(number, format=format)

def format_currency(number, currency: str, format=None, currency_digits=True, format_type="standard") -> str:
    return get_babel_instance().format_currency(number, currency, format=format, currency_digits=currency_digits, format_type=format_type)

def format_percent(number, format=None) -> str:
    return get_babel_instance().format_percent(number, format=format)

def format_scientific(number, format=None) -> str:
    return get_babel_instance().format_scientific(number, format=format)

# --- Other Global Shortcuts ---
def get_locale() -> Locale:
     return get_babel_instance().get_locale()

def get_timezone() -> timezone:
     return get_babel_instance().get_timezone()

def set_locale(locale_str: str):
     get_babel_instance().set_locale(locale_str)

def set_timezone(tz_identifier: Union[str, timezone]):
     get_babel_instance().set_timezone(tz_identifier)

def refresh():
     get_babel_instance().refresh()

def force_locale(locale: str) -> contextmanager:
     return get_babel_instance().force_locale(locale)

def clear_cache():
     get_babel_instance().clear_cache()

# --- Signal Connection (Convenience) ---
def connect_locale_changed(func: Callable[[str], None]):
    """Connects to the locale change signal of the global instance."""
    # Ensures instance exists before connecting
    get_babel_instance().connect_locale_changed(func)

def disconnect_locale_changed(func: Callable[[str], None]):
    """Disconnects from the locale change signal of the global instance."""
    # Doesn't raise error if instance doesn't exist, just logs? Or maybe should check.
    try:
        get_babel_instance().disconnect_locale_changed(func)
    except RuntimeError:
         logger.warning("Cannot disconnect locale change listener: TogaBabel not initialized.")
    except Exception as e:
         logger.exception(f"Error disconnecting locale change listener: {e}", exc_info=True)