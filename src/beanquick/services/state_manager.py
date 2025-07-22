"""State management for Beanquick application."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, CENTER, BOLD  # type: ignore

from beanquick.core import BeanquickLedger
from beanquick.ui.welcome_box import WelcomeBox
from beanquick.ui.setup_box import SetupBox
from beanquick.ui.loading_box import LoadingBox
from beanquick.ui.entry_box import EntryBox
from beanquick.ui.base_entry_box import EntryMode
from beanquick.services.ledger_manager import get_ledger_data

if TYPE_CHECKING:
    from beanquick.app import Beanquick


logger = logging.getLogger(__name__)

class AppState(Enum):
    INITIALIZING = auto()
    SHOWING_WELCOME = auto()
    SHOWING_SETUP = auto()
    LOADING_MAIN = auto()
    SHOWING_MAIN = auto()
    ERROR = auto()

class StateHandler(ABC):
    """Abstract base class for state handlers."""

    def __init__(self, app: Beanquick):
        self.app = app
    
    @abstractmethod
    def enter(self, **kwargs) -> toga.Box:
        """Called when entering this state. Returns the UI widget to display."""
        pass
    
    def exit(self) -> None:
        """Called when exiting this state. Used for cleanup."""
        pass
    
    def get_title(self) -> str:
        """Returns the window title for this state."""
        return self.app.formal_name
    
class StateManager:
    """Manages application state transitions."""
    def __init__(self, app: Beanquick):
        self.app = app
        self.current_state: AppState = AppState.INITIALIZING
        self.state_handlers: dict[AppState, StateHandler] = {
            AppState.SHOWING_WELCOME: WelcomeState(app),
            AppState.SHOWING_SETUP: SetupState(app),
            AppState.LOADING_MAIN: LoadingMainState(app),
            AppState.SHOWING_MAIN: MainState(app),
            AppState.ERROR: ErrorState(app),
            # Add other state handlers as needed
        }
        self._active_handler: StateHandler | None = None

        # Valid state transitions
        self.valid_transitions: dict[AppState, set[AppState]] = {
            AppState.INITIALIZING: {
                AppState.SHOWING_WELCOME, AppState.SHOWING_SETUP,
                AppState.LOADING_MAIN, AppState.ERROR
            },
            AppState.SHOWING_WELCOME: { AppState.SHOWING_SETUP, AppState.ERROR },
            AppState.SHOWING_SETUP: { AppState.LOADING_MAIN, AppState.ERROR },
            AppState.LOADING_MAIN: { AppState.SHOWING_MAIN, AppState.ERROR },
            AppState.SHOWING_MAIN: { AppState.LOADING_MAIN, AppState.ERROR },
            # Error state can transition to any state except itself to allow recovery
            AppState.ERROR: {
                AppState.SHOWING_WELCOME, AppState.SHOWING_SETUP
            }
        }


    def initialize_app_state(self) -> None:
        """Initialize the application state based on the app configuration."""
        logger.info("Initializing application state...")
        if not self.app.config.is_first_run_complete:
            self.transition_to(AppState.SHOWING_WELCOME)
        elif not self.app.config.is_setup_complete:
            self.transition_to(AppState.SHOWING_SETUP)
        else:
            # If first run and setup are complete, transition to loading main state
            active_file = self.app.config.active_beancount_file
            if active_file and Path(active_file).exists():
                logger.info(f"Active Beancount file found: {active_file}")
                self.transition_to(AppState.LOADING_MAIN, ledger_file_path=active_file)
            elif active_file:  # File path exists in config but file itself doesn't
                logger.warning(f"Active Beancount file not found: {active_file}")
                self.app.config.remove_beancount_file(active_file, update_active=True)
                self.transition_to(AppState.SHOWING_SETUP, error_message=f"The last used ledger file '{Path(active_file).name}' was not found.")
            else:
                logger.warning("No active Beancount file found, transitioning to setup.")
                self.transition_to(AppState.SHOWING_SETUP)

    def transition_to(self, new_state: AppState, **kwargs) -> None:
        """Transition to a new application state."""
        # Check if the transition is valid
        if new_state not in self.valid_transitions.get(self.current_state, set()):
            logger.error(f"Invalid state transition from {self.current_state} to {new_state}.")
            
            # Handle invalid transition by going to error state
            # Only if not already in error state
            if new_state != AppState.ERROR:
                self.transition_to(AppState.ERROR,
                                   error_message=f"Invalid state transition from {self.current_state} to {new_state}")
                return

        logger.info(f"State transition: {self.current_state} -> {new_state} (params: {kwargs})")

        # Exit the current state handler if it exists
        if self._active_handler:
            self._active_handler.exit()
            self._active_handler = None

        previous_state = self.current_state
        self.current_state = new_state

        handler = self.state_handlers.get(new_state)
        if not handler:
            logger.error(f"No handler found for state {new_state}.")
            # Fall back to error state
            self.current_state = previous_state
            self.transition_to(AppState.ERROR, error_message=f"No handler found for state {new_state}")
            return
        
        # Enter the new state
        self._active_handler = handler
        try:
            content = handler.enter(**kwargs)
            
            # Update the main window content
            self.app.main_window.content = content
            # Update the window title
            self.app.main_window.title = handler.get_title()

            # focus only takes effect after the UI is rendered
            if isinstance(content, EntryBox):
                if content.current_form:
                    # If the content is an EntryBox, focus the first input field
                    content.current_form.focus_first_input()

            logger.info(f"Transitioned to state {new_state} with handler {handler.__class__.__name__}")
        except Exception as e:
            logger.error(f"Error entering state {new_state}: {e}", exc_info=True)
            self.transition_to(AppState.ERROR, error_message=str(e))
            return

class ErrorState(StateHandler):
    """State handler for displaying error messages."""
    
    def enter(self, **kwargs) -> toga.Box:
        error_message = kwargs.get("error_message", "An unknown error occurred")
        logger.error(f"Entering Error State: {error_message}")
        # Create and return an error UI
        error_box = toga.Box(style=Pack(direction=COLUMN, margin=50, align_items=CENTER))
        error_box.add(toga.Label("Application Error", style=Pack(font_size=24, color='red', margin_bottom=20, text_align=CENTER)))
        error_box.add(toga.Label(error_message, style=Pack(text_align=CENTER, margin_bottom=20)))

        retry_button = toga.Button(
            "Try Again",
            style=Pack(width=350, height=28, font_weight=BOLD),
            on_press=self._handle_retry
        )
        error_box.add(retry_button)

        return error_box
    
    def get_title(self) -> str:
        return f"{self.app.formal_name} - Error"
    
    def _handle_retry(self, widget):
        """Attempt to recover from error state."""
        # Default fallback to setup screen
        # TODO: Implement more robust error recovery logic
        self.app.state_manager.transition_to(AppState.SHOWING_SETUP)


class WelcomeState(StateHandler):
    """State handler for showing the welcome screen."""
    
    def enter(self, **kwargs) -> toga.Box:
        logger.info("Entering Welcome State")
        # Create and return the welcome UI
        welcome_box = WelcomeBox(on_complete=self.complete_handler)
        return welcome_box
    
    def get_title(self) -> str:
        return f"{self.app.formal_name} - Welcome"
    
    def complete_handler(self) -> None:
        """Called when the user completes the welcome process."""
        logger.info("Welcome process completed, transitioning to main app state.")
        # Mark first run complete in config
        self.app.config.is_first_run_complete = True
        
        # Transition to main app state (could be a dashboard or main view)
        self.app.state_manager.transition_to(AppState.SHOWING_SETUP)

class SetupState(StateHandler):
    """State handler for the setup process where users select or create a Beancount ledger."""
    
    def enter(self, **kwargs) -> toga.Box:
        logger.info("Entering Setup State")
        # Create and return the setup UI
        setup_box = SetupBox(
            on_ledger_selected=self.setup_complete_handler,
        )
        return setup_box
    
    def get_title(self) -> str:
        return f"{self.app.formal_name} - Setup"
    
    def setup_complete_handler(self, ledger_file_path: str):
        """Handler after the setup page is completed"""
        logger.info(f"Setup page completed, ledger file path: {ledger_file_path}")
        # Add the selected ledger file to the config, it will also set the `active_beancount_file`
        if self.app.config.add_beancount_file(ledger_file_path, set_active=True):
            # Mark setup as complete
            self.app.config.is_setup_complete = True
            
            # Transition to main app state
            active_file = self.app.config.active_beancount_file
            if active_file:
                logger.info(f"Active Beancount file set to: {active_file}")
                # Transition to loading main state
                self.app.state_manager.transition_to(AppState.LOADING_MAIN, ledger_file_path=active_file)

class LoadingMainState(StateHandler):
    """State handler for loading the main application view."""
    
    def enter(self, **kwargs) -> toga.Box:
        logger.info("Entering Loading Main State")
        ledger_file_path = kwargs.get("ledger_file_path")

        if not ledger_file_path:
            logger.error("No ledger file path provided for loading main state.")

            # Attempt to get the active Beancount file from config
            ledger_file_path = self.app.config.active_beancount_file
            if not ledger_file_path:
                logger.error("No active Beancount file found, transitioning to setup state.")
                self.app.state_manager.transition_to(AppState.SHOWING_SETUP, error_message="No active Beancount file found.")
                return toga.Box()
            logger.info(f"Using active Beancount file from config: {ledger_file_path}")
        
        if ledger_file_path != self.app.config.active_beancount_file:
            # This might happen if a recent file is opened that wasn't the last active one
            logger.info(f"Ledger to load ({ledger_file_path}) differs from current active in config ({self.app.config.active_beancount_file}). Updating active file.")
            self.app.config.active_beancount_file = ledger_file_path
        
        # Create a loading UI
        loading_box = LoadingBox()

        # Start the asynchronous ledger loading task
        try:
            ledger = BeanquickLedger(path=ledger_file_path)
        except ValueError as e:
            logger.error(f"Failed to instantiate ledger for '{ledger_file_path}' on demand: {e}")
            self.app.state_manager.transition_to(AppState.ERROR, error_message=str(e))
            return toga.Box()
        logger.info(f"Creating asyncio task to load ledger from {ledger_file_path}")
        self.app.current_load_task = asyncio.create_task(self._async_load_ledger(ledger))

        return loading_box

    def get_title(self) -> str:
        return f"{self.app.formal_name} - Loading"

    async def _async_load_ledger(self, ledger: BeanquickLedger):
        """Asynchronous task to load the ledger."""
        logger.info(f"Starting async ledger load task for {ledger.beancount_file_path}")
        try:
            await ledger.async_load_file()
            logger.info(f"Async task completed: Data loading finished for {ledger.beancount_file_path}, success: {ledger.is_loaded}")
            self._activate_ledger(ledger)
        except asyncio.CancelledError:
            logger.info("Ledger loading task was cancelled.")
            self.app.state_manager.transition_to(AppState.ERROR, error_message="Ledger loading was cancelled.")
        except Exception as e:
            logger.error(f"Async task error: Exception during ledger load for {ledger.beancount_file_path}: {e}", exc_info=True)
            self.app.state_manager.transition_to(AppState.ERROR, error_message=str(e))
        finally:
            if self.app.current_load_task and self.app.current_load_task.done():
                self.app.current_load_task = None
    
    def _activate_ledger(self, ledger: BeanquickLedger):
        """Activate the loaded ledger and transition to the main application state."""
        logger.info(f"Activating ledger: {ledger.beancount_file_path}")

        if self.app.active_ledger and self.app.active_ledger.beancount_file_path != ledger.beancount_file_path:
            logger.info(f"Switching active ledger from {self.app.active_ledger.beancount_file_path} to {ledger.beancount_file_path}. Stopping old watcher.")
            self.app.active_ledger.stop_watcher()
        
        with self.app.ledger_management_lock:
            self.app.active_ledger = ledger
            self.app.active_ledger_data = get_ledger_data(ledger)

            # Transition to the main application state
            logger.info(f"Transitioning to main application state with ledger: {ledger.beancount_file_path}")
            self.app.state_manager.transition_to(AppState.SHOWING_MAIN)
    
class MainState(StateHandler):
    """State handler for the main application view."""
    def __init__(self, app: Beanquick):
        super().__init__(app)

        self.main_box: EntryBox | None = None
        self._quick_mode_command: toga.Command | None = None
        self._normal_mode_command: toga.Command | None = None
    
    def enter(self, **kwargs) -> toga.Box:
        logger.info("Entering Main State")
        active_ledger = self.app.active_ledger
        if not active_ledger or not active_ledger.is_loaded:
            logger.error("No active ledger found or it is not loaded. Transitioning to setup state.")
            self.app.state_manager.transition_to(AppState.SHOWING_SETUP, error_message="No active ledger found or it is not loaded.")
            return toga.Box()
        
        self.main_box = EntryBox(app_instance=self.app)

        # Setup commands
        self._setup_commands(self.main_box)

        return self.main_box
    
    def get_title(self) -> str:
        return f"{self.app.formal_name}"
    
    def _setup_commands(self, entry_box: EntryBox):
        """Setup application commands for the main window."""
        # Add Help command to the menu
        self._quick_mode_command = toga.Command(
            lambda widget: self._toggle_mode(entry_box, widget),
            text='Quick Mode',
            shortcut=toga.Key.MOD_1 + "/",
            group=toga.Group.COMMANDS,
            section=1,
            order=0,
            icon="resources/images/NotoHighVoltage.png",
        )
        self._normal_mode_command = toga.Command(
            lambda widget: self._toggle_mode(entry_box, widget),
            text='Normal Mode',
            shortcut=toga.Key.MOD_1 + "/",
            group=toga.Group.COMMANDS,
            section=1,
            order=0,
            icon="resources/images/NotoMemo.png",
        )
        help_command = toga.Command(
            self._show_help,
            text='Help',
            group=toga.Group.HELP,  # Standard Help group
            section=1,
            icon="resources/images/NotoRingBuoy.png",
        )
        preferences_command = toga.Command.standard(self.app, toga.Command.PREFERENCES)
        self.app.commands.add(preferences_command)
        self.app.main_window.toolbar.add(self._quick_mode_command, help_command)
        
    def _toggle_mode(self, entry_box: EntryBox, widget):
        """Switch to quick entry mode in the main application."""
        logger.info("Switching to quick entry mode")
        entry_box.on_toggle_mode()
        if entry_box._current_mode == EntryMode.QUICK:
            self.app.main_window.toolbar.add(self._normal_mode_command)
            self.app.main_window.toolbar.discard(self._quick_mode_command)
            self.app.commands.discard(self._quick_mode_command)
        else:
            self.app.main_window.toolbar.add(self._quick_mode_command)
            self.app.main_window.toolbar.discard(self._normal_mode_command)
            self.app.commands.discard(self._normal_mode_command)
    
    def _show_help(self, widget=None, **kwargs):
        """Show the help window."""
        logger.info("Showing help window")
        from beanquick.ui.help_window import show_help_window
        # Show the manual help topic using the i18n-aware help system
        # The help system will automatically use the current locale
        show_help_window(self.app, topic="manual.md")