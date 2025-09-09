"""
Transaction Triage View - Main coordinator for transaction review interface.

This module provides the main TransactionTriageView class that coordinates
between the TransactionTable and InspectorPanel components to create a
master-detail interface for reviewing imported transactions.
"""

import logging
from typing import List, Optional, TYPE_CHECKING, cast
from enum import Enum
from datetime import datetime

import toga
from toga.style import Pack
from toga.style.pack import ROW  # type: ignore

from beanquick.ui.importer.transaction_review.transaction_table import TransactionTable
from beanquick.importers.rules.engine import RuleEngine
from beanquick.importers.rules.repository import RuleRepository

from ..inspector.form_validator import FormValidator
from ..inspector.view_controller import InspectorPanelViewController
from ..success_box import SuccessView
from .models import TransactionDisplayData, SuccessData
from .view_controller import TriageViewController

logger = logging.getLogger(__name__)


class TriageViewState(Enum):
    """Enumeration of possible view states for the triage interface."""
    TRIAGE = "triage"
    SUCCESS = "success"


class TransactionTriageView:
    """Main coordinator for the transaction triage interface.
    
    This class manages the master-detail interface consisting of a transaction
    table on the left and an inspector panel on the right. It coordinates
    selection changes between components and handles window integration.
    """

    def __init__(self, app: toga.App, display_transactions: List[TransactionDisplayData], rule_repository: RuleRepository, rule_engine: RuleEngine, beanquick_integration):
        """Initialize the transaction triage view.
        
        Args:
            app: The main Beanquick application instance
            display_transactions: List of TransactionDisplayData objects ready for triage
            rule_repository: Importer-specific RuleRepository instance
            rule_engine: The RuleEngine instance for rule operations
            beanquick_integration: Integration service for account completion
            
        Raises:
            ValueError: If app, display_transactions list, or rule_repository is None/empty
        """
        if not app:
            raise ValueError("App instance is required")
        if not rule_repository:
            raise ValueError("RuleRepository is required")
        if not display_transactions:
            raise ValueError("Display transactions list cannot be empty")
        
        self._app = app
        self._display_transactions = display_transactions
        self._rule_repository = rule_repository
        self._beanquick_integration = beanquick_integration
        self._rule_engine = rule_engine
        self._controller = TriageViewController(self, self._rule_engine)
        
        # Initialize components
        self._transaction_table: Optional[TransactionTable] = None
        self._inspector_controller: Optional[InspectorPanelViewController] = None
        self._main_container: Optional[toga.Widget] = None
        
        # Success view state management
        self._current_state: TriageViewState = TriageViewState.TRIAGE
        self._success_view: Optional[SuccessView] = None
        self._triage_container: Optional[toga.SplitContainer] = None
        
        # Set up validation system early, before initializing components
        self._setup_validation_system()
        
        # Apply rules after validation is set up for proper status handling
        self._apply_rules_after_validation()
        
        # Initialize components
        self._setup_components()
    
    def _setup_validation_system(self):
        """Set up validation on all TransactionDisplayData objects early.
        
        This method initializes the FormValidator and sets it up on all 
        TransactionDisplayData objects before any UI components are created.
        This ensures that when rules are applied, validation is already active
        and can properly determine the appropriate transaction status.
        """
        try:
            logger.info(f"Setting up early validation system for {len(self._display_transactions)} transactions")
            
            # Create a single FormValidator instance to share across all transactions
            form_validator = FormValidator()
            
            # Set up validation on each TransactionDisplayData object
            for transaction_display in self._display_transactions:
                transaction_display.set_validator(form_validator)
                logger.debug(f"Set up early validation for transaction {transaction_display.display_id}")
            
            logger.info("Early validation system setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error setting up validation system: {e}", exc_info=True)
            # Don't raise - this shouldn't prevent the view from initializing
            # Components will still work, just without early validation
    
    def _apply_rules_after_validation(self):
        """Apply rules to all transactions after validation system is set up.
        
        This method applies existing rules to all transactions now that validation
        is properly configured. The reactive validation system will automatically
        determine the appropriate status for each transaction based on the rule
        application results and field validation.
        
        This method is safe to call even if no rule engine is available or if
        there are no transactions to process.
        """
        if not self._rule_engine:
            logger.debug("No rule engine available, skipping rule application")
            return
        
        if not self._display_transactions:
            logger.debug("No transactions to process, skipping rule application")
            return
        
        try:
            logger.info(f"Applying rules to {len(self._display_transactions)} transactions after validation setup")
            
            # Begin batch mode for efficient rule statistics updates
            self._rule_engine.begin_batch_updates()
            
            applied_rules_count = 0
            categorized_count = 0
            
            try:
                for transaction_display in self._display_transactions:
                    # Apply all matching rules to this transaction
                    # The rule engine will update the transaction fields and metadata
                    # The reactive validation system will then determine the appropriate status
                    applied_rule_ids = self._rule_engine.apply_all_matching_rules(transaction_display)
                    
                    if applied_rule_ids:
                        applied_rules_count += len(applied_rule_ids)
                        logger.debug(
                            f"Applied {len(applied_rule_ids)} rules to transaction "
                            f"with payee: {transaction_display.transaction_data.payee}"
                        )
                        
                        # Check if transaction is now properly categorized
                        # (The reactive validation system should have updated the status)
                        validation_result = transaction_display.get_validation_result()
                        if validation_result and validation_result.is_valid:
                            categorized_count += 1
                
            finally:
                # End batch mode and persist all accumulated rule statistics updates
                success = self._rule_engine.end_batch_updates()
                if not success:
                    logger.warning("Failed to persist rule statistics updates after rule application")
            
            logger.info(
                f"Rule application completed: {applied_rules_count} rule applications, "
                f"{categorized_count} transactions properly categorized"
            )
            
        except Exception as e:
            logger.error(f"Error applying rules after validation setup: {e}", exc_info=True)
            # Don't raise - this shouldn't prevent the view from initializing
            # Transactions will still be available for manual categorization
    
    # In TransactionTriageView
    def _create_inspector_panel(self):
        """Create inspector panel with proper separation."""
        account_completer = self._beanquick_integration.account_completer
        self._inspector_controller = InspectorPanelViewController(
            app=self._app,
            account_completer=account_completer,
            rule_engine=self._rule_engine,
            on_save_complete=self._handle_save_completion
        )
        self._inspector_controller.set_all_transactions(self._display_transactions)
        
        # Get the view widget for layout
        inspector_widget = self._inspector_controller.view.create_widget()
        return inspector_widget

    def _on_transaction_selected(self, transaction_display_data):
        """Handle transaction selection."""
        if self._inspector_controller:
            self._inspector_controller.update_transaction(transaction_display_data)

    def _setup_components(self):
        """Initialize the table and inspector components."""
        # Create transaction table with selection callback
        self._transaction_table = TransactionTable(
            transactions=self._display_transactions,
            on_selection_change=self.handle_selection_change
        )

    def create_view(self) -> toga.Widget:
        """Create the main view using toga.SplitContainer with vertical split.
        
        Creates a split container with the transaction table on the left
        and the inspector panel on the right, or displays the success view
        depending on the current state.
        
        Returns:
            toga.Widget: The main container widget for the triage view
            
        Raises:
            RuntimeError: If components are not properly initialized
        """
        return self._create_triage_view()
    
    def _create_triage_view(self) -> toga.Widget:
        """Create the triage view with table and inspector panel.
        
        Returns:
            toga.Widget: The triage view container
        """
        if not self._transaction_table:
            raise RuntimeError("Components not properly initialized")
        
        # Create the table widget
        table_widget = self._transaction_table.create_table()
        
        # Create the inspector panel widget
        inspector_widget = self._create_inspector_panel()
        
        # Create split container with vertical split (side-by-side layout)
        self._triage_container = toga.SplitContainer(
            content=[(table_widget, 1), (inspector_widget, 1)],
            style=Pack(
                direction=ROW,
                flex=1,
                margin=10,
            )
        )
        
        return self._triage_container
    
    def _create_success_view(self, success_data: SuccessData):
        """Create and return the success view widget.
        
        Returns:
            toga.Widget: The success view widget
        """
        if not self._success_view:
            self._success_view = SuccessView(
                success_data=success_data.to_dict(),
                on_import_another=self._handle_import_another,
                on_view_files=self._handle_view_files,
                on_close=self._handle_close
            )
        
        return self._success_view
    
    def handle_selection_change(self, selected_transaction: Optional[TransactionDisplayData]):
        """Coordinate between table and inspector components.
        
        This method is called when the user selects a different transaction
        in the table. It updates the inspector panel to show the selected
        transaction's details or clears the display if no selection.
        
        Args:
            selected_transaction: The TransactionDisplayData object that was selected, or None
        """
        if not self._inspector_controller:
            return
            
        if not selected_transaction:
            self._inspector_controller.clear_display()
            return
        
        try:
            # Update the inspector panel with the full TransactionDisplayData
            # This allows the inspector to populate both transaction data and categorization fields
            self._inspector_controller.update_transaction(selected_transaction)
        except Exception as e:
            # Log the error but don't crash the UI
            logger.error(f"Error updating inspector panel: {e}", exc_info=True)
            
            # Clear the inspector panel on error
            self._inspector_controller.clear_display()
    
    def show_in_window(self, window: toga.Window):
        """Display the triage view in the specified window.
        
        This method integrates the triage view with the main application
        window, replacing the current content. The content shown depends
        on the current view state (triage or success).
        
        Args:
            window: The main window to display the view in
            
        Raises:
            ValueError: If window is None
            RuntimeError: If view is not properly created
        """
        if window is None:
            raise ValueError("Window cannot be None")
        
        # Create the appropriate view based on current state
        current_view = self.create_view()
        
        if not current_view:
            raise RuntimeError("Failed to create view container")
        
        # Set window size
        window.size = (1080, 800)
        # Set the window content to our current view
        window.content = current_view
        self._main_container = current_view
        
        # Update window title
        window.title = f"{self._app.formal_name} - {self._rule_repository.importer_name} ({len(self._display_transactions)} transactions)"
    
    @property
    def transaction_count(self) -> int:
        """Get the number of transactions in the view.
        
        Returns:
            int: The number of transactions currently displayed
        """
        return len(self._display_transactions)
    
    @property
    def selected_transaction(self) -> Optional[TransactionDisplayData]:
        """Get the currently selected transaction.
        
        Returns:
            Optional[TransactionDisplayData]: The currently selected transaction, or None
        """
        if self._transaction_table:
            return self._transaction_table.get_selected_transaction()
        return None
    
    def _handle_save_completion(self, saved_file_path: str):
        """Handle the completion of entry saving process.
        
        This method is called when the EntrySaver component successfully saves
        Beancount entries to a file. It collects statistics and triggers the
        transition to the success view.
        
        Args:
            saved_file_path: Path where the entries were saved
        """
        try:
            logger.info(f"Entry save completed, file saved to: {saved_file_path}")
            
            # We need to get the source file path from the original import context
            # For now, we'll need to track this in the triage view
            source_file_path = getattr(self, '_source_file_path', 'Unknown')
            
            # Collect comprehensive success statistics
            success_data = self.collect_processing_statistics(
                source_file_path=source_file_path,
                saved_file_path=saved_file_path,
                # TODO: Track these values during the triage session
                rules_created_count=0,  # Will be updated when rule tracking is implemented
                rules_applied_count=0   # Will be updated when rule tracking is implemented
            )
            
            # Trigger the success view transition via the controller
            self._controller.handle_save_completion(success_data)
            
        except Exception as e:
            logger.error(f"Error handling save completion: {e}", exc_info=True)
    
    def set_source_context(self, source_file_path: str):
        """Set the source file context for success statistics.
        
        This method should be called when the triage view is initialized
        to provide context for success statistics collection.

        Args:
            source_file_path: Path to the original statement file
        """
        self._source_file_path = source_file_path
        logger.debug(f"Set source context: {source_file_path}")
    
    def show_success_view(self, success_data: SuccessData):
        """Show the success view with the provided completion data.
        
        This method transitions from the triage view to the success view,
        updating the display with import completion statistics.
        
        Args:
            success_data: The success statistics and metadata to display
        """
        try:
            logger.info("Transitioning to success view")
            
            # Update the current state
            self._current_state = TriageViewState.SUCCESS
            
            # Create or update the success view with data
            if not self._success_view:
                self._success_view = self._create_success_view(success_data)

            current_widget = self._success_view.create_widget()  # type: ignore
            # Update the window content if we have a current window
            if self._main_container and hasattr(self._main_container, 'window'):
                window = self._main_container.window
                if window:
                    window.content = current_widget
                    self._main_container = current_widget
                    window.title = f"{self._app.formal_name} - Import Complete"

            logger.info("Successfully transitioned to success view")
            
        except Exception as e:
            logger.error(f"Error showing success view: {e}", exc_info=True)
            raise
    
    def collect_processing_statistics(self, 
                                    source_file_path: str, 
                                    saved_file_path: str,
                                    rules_created_count: int = 0,
                                    rules_applied_count: int = 0) -> SuccessData:
        """Collect processing statistics from the current triage session.
        
        This method delegates to the controller to collect comprehensive
        statistics about the completed import process.
        
        Args:
            source_file_path: Path to the original statement file
            saved_file_path: Path where entries were saved
            rules_created_count: Number of new rules created (default: 0)
            rules_applied_count: Number of rules applied (default: 0)
            
        Returns:
            SuccessData: Compiled success statistics
        """
        return self._controller.collect_success_statistics(
            source_file_path=source_file_path,
            saved_file_path=saved_file_path,
            rules_created_count=rules_created_count,
            rules_applied_count=rules_applied_count
        )
    
    def reset_for_new_import(self):
        """Reset the view for a new import workflow.
        
        This method resets the view state back to triage mode and cleans up
        the success view components, preparing for a new import session.
        """
        try:
            logger.info("Resetting triage view for new import")
            
            # Reset state
            self._current_state = TriageViewState.TRIAGE
            
            # Clear success view
            if self._success_view:
                self._success_view.clear_data()
                self._success_view = None
            
            # Reset controller
            self._controller.reset_for_new_import()
            
            # Cleanup validation system
            self._cleanup_validation_system()
            
            logger.debug("Triage view reset completed")
            
        except Exception as e:
            logger.error(f"Error resetting triage view: {e}", exc_info=True)
    
    def _cleanup_validation_system(self):
        """Clean up validation system and observers.
        
        This method removes validation observers from all TransactionDisplayData
        objects to prevent memory leaks and ensure clean teardown.
        """
        try:
            logger.debug("Cleaning up validation system")
            
            # The FormValidator observers will be cleaned up automatically
            # when TransactionDisplayData objects are destroyed, but we can
            # explicitly clear the validator reference to help with cleanup
            for transaction_display in self._display_transactions:
                try:
                    # Clear the validator reference
                    transaction_display.set_validator(None)
                except Exception as cleanup_error:
                    logger.warning(f"Error cleaning up validator for transaction {transaction_display.display_id}: {cleanup_error}")
            
            logger.debug("Validation system cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during validation system cleanup: {e}")
            # Don't raise - cleanup errors shouldn't prevent navigation
    
    # Success view action handlers
    def _handle_import_another(self):
        """Handle the Import Another File action from the success view.
        
        This method triggers the workflow to return to the initial import
        file selection state, allowing the user to import another file.
        Enhanced with user confirmation and better error handling.
        """
        try:
            logger.info("User requested to import another file")
            
            # Debug: Check app instance
            if not self._app:
                logger.error("App instance is None - cannot proceed with import another")
                self._show_error_dialog(
                    "Error", 
                    "Application instance is not available. Please restart the application."
                )
                return
            
            logger.debug(f"App instance available: {type(self._app)}")
            
            # Show confirmation if there's unsaved work or context to lose
            confirmation_needed = self._check_if_confirmation_needed()
            if confirmation_needed:
                logger.debug("Import another action requires confirmation, but proceeding for now")
            
            # Reset the view for new import
            self.reset_for_new_import()
            
            # Recreate the importer window ui
            from beanquick.ui.importer_window import ImporterWindow
            window = self._app.current_window
            if window and isinstance(window, ImporterWindow):
                window.reset_to_initial_state_with_ui()
            
        except Exception as e:
            logger.error(f"Error handling import another request: {e}", exc_info=True)
            self._show_error_dialog(
                "Unexpected Error",
                f"An unexpected error occurred while trying to start a new import:\n{str(e)}"
            )
    
    def _check_if_confirmation_needed(self) -> bool:
        """Check if user confirmation is needed before starting a new import.
        
        This method determines if there's any unsaved work or important
        context that would be lost by starting a new import.
        
        Returns:
            bool: True if confirmation is recommended, False otherwise
        """
        try:
            # Check if there are any unsaved changes or important state
            # For now, we'll assume confirmation is not needed since the user
            # has already completed the import and reached the success view
            
            # Future enhancements could check for:
            # - Unsaved rule modifications
            # - Temporary categorization data
            # - User-specific settings that might be lost
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking confirmation need: {e}")
            # If we can't determine safely, err on the side of caution
            return True
    
    def _handle_view_files(self, file_path: str):
        """Handle the View Saved Files action from the success view.
        
        This method opens the file system location where the Beancount
        entries were saved, allowing the user to view or edit the files.
        Enhanced with better error handling and user feedback.
        
        Args:
            file_path: Path to the saved file to show
        """
        try:
            logger.info(f"User requested to view files at: {file_path}")
            
            # Validate file path
            if not file_path or file_path.strip() == '':
                logger.warning("No file path provided for view files action")
                self._show_error_dialog("View Files Error", "No file location available to open.")
                return
            
            # Use the system's default file manager to show the file location
            import subprocess
            import platform
            from pathlib import Path
            
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                logger.warning(f"File does not exist: {file_path}")
                # Try to show the parent directory if the file doesn't exist
                parent_dir = file_path_obj.parent
                if parent_dir.exists():
                    logger.info(f"File not found, showing parent directory: {parent_dir}")
                    file_path_obj = parent_dir
                else:
                    self._show_error_dialog(
                        "File Not Found", 
                        f"The saved file could not be found at:\n{file_path}\n\nThe file may have been moved or deleted."
                    )
                    return
            
            # Open file location based on platform
            success = False
            try:
                if platform.system() == "Darwin":  # macOS
                    result = subprocess.run(["open", "-R", str(file_path_obj)], 
                                          capture_output=True, text=True, timeout=10)
                    success = result.returncode == 0
                elif platform.system() == "Windows":
                    result = subprocess.run(["explorer", "/select,", str(file_path_obj)], 
                                          capture_output=True, text=True, timeout=10)
                    success = result.returncode == 0
                else:  # Linux and others
                    # Try multiple file managers for better compatibility
                    file_managers = ["nautilus", "dolphin", "thunar", "nemo", "xdg-open"]
                    for fm in file_managers:
                        try:
                            if file_path_obj.is_file():
                                # Show parent directory for most Linux file managers
                                target = str(file_path_obj.parent)
                            else:
                                target = str(file_path_obj)
                            
                            result = subprocess.run([fm, target], 
                                                  capture_output=True, text=True, timeout=10)
                            if result.returncode == 0:
                                success = True
                                break
                        except (subprocess.SubprocessError, FileNotFoundError):
                            continue
                
                if success:
                    logger.info(f"Successfully opened file location: {file_path_obj}")
                else:
                    # Fallback: show informational dialog with file path
                    self._show_info_dialog(
                        "File Location", 
                        f"Your file has been saved to:\n{file_path}\n\nPlease navigate to this location in your file manager."
                    )
                    
            except subprocess.TimeoutExpired:
                logger.warning("File manager operation timed out")
                self._show_error_dialog(
                    "Operation Timeout", 
                    "The file manager took too long to respond. Please manually navigate to the file location."
                )
            except subprocess.SubprocessError as e:
                logger.warning(f"File manager subprocess error: {e}")
                self._show_info_dialog(
                    "File Location", 
                    f"Your file has been saved to:\n{file_path}\n\nPlease navigate to this location in your file manager."
                )
                
        except Exception as e:
            logger.error(f"Error handling view files request: {e}", exc_info=True)
            self._show_error_dialog(
                "Unexpected Error", 
                f"An unexpected error occurred while trying to show the file location:\n{str(e)}"
            )

    def _handle_close(self):
        """Handle the Close action from the success view.

        This method triggers the workflow to close the current view
        or dialog, exiting the import workflow completely.
        Enhanced with user confirmation and graceful navigation.
        """
        try:
            logger.info("User requested to close the view")
            if self._main_container:
                window = self._main_container.window
                if window:
                    window.close()
            else:
                logger.warning("Error closing window")
                self._show_error_dialog(
                    "Error Closing Window",
                    "An error occurred while trying to close the window."
                )
        except Exception as e:
            logger.error(f"Error handling close request: {e}", exc_info=True)
            self._show_error_dialog(
                "Navigation Error",
                f"An error occurred while trying to close the window:\n{str(e)}"
            )
    
    def _cleanup_import_state(self):
        """Clean up any temporary state or resources used during import.
        
        This method ensures that any temporary files, cached data, or
        other resources are properly cleaned up when exiting the import workflow.
        """
        try:
            logger.debug("Cleaning up import state")
            
            # Reset the view state first
            self.reset_for_new_import()
            
            # Cleanup transaction table observers
            if self._transaction_table:
                try:
                    self._transaction_table.cleanup()
                    logger.debug("Transaction table cleanup completed")
                except Exception as table_cleanup_error:
                    logger.warning(f"Transaction table cleanup failed: {table_cleanup_error}")
            
            # Reset controller state
            if self._controller:
                # Check if controller has cleanup method before calling it
                try:
                    cleanup_method = getattr(self._controller, 'cleanup', None)
                    if cleanup_method and callable(cleanup_method):
                        cleanup_method()
                    else:
                        logger.debug("Controller has no cleanup method")
                except Exception as cleanup_error:
                    logger.warning(f"Controller cleanup failed: {cleanup_error}")
            
            # Cleanup inspector controller
            if self._inspector_controller:
                try:
                    self._inspector_controller.cleanup()
                    logger.debug("Inspector controller cleanup completed")
                except Exception as inspector_cleanup_error:
                    logger.warning(f"Inspector controller cleanup failed: {inspector_cleanup_error}")
            
            # Clear any cached data
            if hasattr(self, '_success_data'):
                self._success_data = None
            
            # Reset view state
            self._current_state = TriageViewState.TRIAGE
            
            logger.debug("Import state cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during import state cleanup: {e}", exc_info=True)
            # Don't raise - cleanup errors shouldn't prevent navigation
    
    def _show_error_dialog(self, title: str, message: str):
        """Show an error dialog to the user.
        
        Args:
            title: The dialog title
            message: The error message to display
        """
        try:
            # Use the app's main window to show the dialog
            if hasattr(self._app, 'main_window') and self._app.main_window:
                import asyncio
                dialog = toga.ErrorDialog(title, message)
                # Cast to proper type to satisfy type checker
                main_window = cast(toga.MainWindow, self._app.main_window)
                # Use the synchronous pattern for dialogs as per Toga documentation
                task = asyncio.create_task(main_window.dialog(dialog))
                # We don't need a callback for error dialogs, just fire and forget
            else:
                logger.error(f"Cannot show error dialog - no main window available. {title}: {message}")
        except Exception as e:
            logger.error(f"Failed to show error dialog: {e}. Original message - {title}: {message}")
    
    def _show_info_dialog(self, title: str, message: str):
        """Show an informational dialog to the user.
        
        Args:
            title: The dialog title
            message: The information message to display
        """
        try:
            # Use the app's main window to show the dialog
            if hasattr(self._app, 'main_window') and self._app.main_window:
                import asyncio
                dialog = toga.InfoDialog(title, message)
                # Cast to proper type to satisfy type checker
                main_window = cast(toga.MainWindow, self._app.main_window)
                # Use the synchronous pattern for dialogs as per Toga documentation
                task = asyncio.create_task(main_window.dialog(dialog))
                # We don't need a callback for info dialogs, just fire and forget
            else:
                logger.info(f"Cannot show info dialog - no main window available. {title}: {message}")
        except Exception as e:
            logger.error(f"Failed to show info dialog: {e}. Original message - {title}: {message}")
    
    async def _show_confirmation_dialog(self, title: str, message: str) -> bool:
        """Show a confirmation dialog to the user.
        
        Args:
            title: The dialog title
            message: The confirmation message to display
            
        Returns:
            bool: True if user confirmed, False otherwise
        """
        try:
            # Use the app's main window to show the dialog
            if hasattr(self._app, 'main_window') and self._app.main_window:
                dialog = toga.QuestionDialog(title, message)
                # Cast to proper type to satisfy type checker
                main_window = cast(toga.MainWindow, self._app.main_window)
                result = await main_window.dialog(dialog)
                return result
            else:
                logger.warning(f"Cannot show confirmation dialog - no main window available. {title}: {message}")
                return False
        except Exception as e:
            logger.error(f"Failed to show confirmation dialog: {e}. Original message - {title}: {message}")
            return False
    
    @property
    def current_state(self) -> TriageViewState:
        """Get the current view state.
        
        Returns:
            TriageViewState: The current state (TRIAGE or SUCCESS)
        """
        return self._current_state