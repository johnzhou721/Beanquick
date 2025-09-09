"""
Inspector Panel View Controller - Business logic and coordination.
Enhanced with reactive architecture coordination and FormValidator integration.
"""
import logging
from typing import Optional, List

from beancount.parser import parser

from beanquick.util import transform_file_paths_for_selection
from beanquick.importers.core.data import TransactionData
from beanquick.ui.importer.transaction_review.models import TransactionDisplayData
from beanquick.importers.rules import TransactionRule

from .entry_preview import EntryPreview
from .entry_saver import EntrySaver
from .source_data_display import SourceDataDisplay
from .form_validator import FormValidator
from .view import InspectorPanelView
from .rule_view.rule_workspace import RuleWorkspace

logger = logging.getLogger(__name__)


class InspectorPanelViewController():
    """Controller for Inspector Panel - handles business logic and coordination.
    Enhanced with reactive architecture coordination and FormValidator integration.
    
    Responsibilities:
    - Manage application state and data
    - Coordinate between View and business services
    - Handle user events from View
    - Orchestrate child components with reactive updates
    - Set up FormValidator on TransactionDisplayData instances
    """
    
    def __init__(self, app, account_completer, rule_engine, on_save_complete=None):
        """Initialize the controller with business dependencies.
        
        Args:
            account_completer: Service for account auto-completion
            rule_engine: Engine for applying rules to transactions
            on_save_complete: Callback when entry saving is completed (optional)
        """
        # Business services
        self._app = app
        self._account_completer = account_completer
        self._rule_engine = rule_engine
        self._on_save_complete = on_save_complete
        
        # Reactive architecture components
        self._form_validator = FormValidator()
        
        # Application state
        self._current_transaction: Optional[TransactionData] = None
        self._current_transaction_display_data: Optional[TransactionDisplayData] = None
        self._all_display_transactions: List[TransactionDisplayData] = []
        
        # Create View and components
        self._view = InspectorPanelView(on_tab_select=self._handle_tab_select)
        self._create_components()
        
        # Inject components into view
        self._view.set_components(
            self._entry_preview,
            self._all_transactions_preview,
            self._entry_saver,
            self._rule_workspace,
            self._source_data_display,
        )
    
    def _create_components(self):
        """Create and configure child components with reactive architecture support."""
        # Create reactive components that use observer pattern
        self._entry_preview = EntryPreview(title="Beancount Entry Preview")
        self._all_transactions_preview = EntryPreview(auto_height=True)
        
        # Create source data display component
        self._source_data_display = SourceDataDisplay()

        file_paths = self._app.active_ledger.options["include"] if self._app.active_ledger else []
        beancount_file_path = self._app.active_ledger.beancount_file_path if self._app.active_ledger else ""
        selection_items = transform_file_paths_for_selection(list(file_paths), beancount_file_path)

        self._entry_saver = EntrySaver(selection_items, on_save=self._handle_entry_save)

        # Create rule workspace - this replaces the complex coordination logic
        # The RuleWorkspace encapsulates:
        # - TransactionCategorizer (with rule creation switch)
        # - RuleManagementContainer (with view/edit modes)  
        # - State machine for coordinating between them
        # - Observer patterns for automatic visibility updates
        # This eliminates race conditions and simplifies state management
        self._rule_workspace = RuleWorkspace(
            account_completer=self._account_completer,
            rule_engine=self._rule_engine,
            on_rule_save=self._handle_rule_save,
            on_scroll_to_bottom=self._handle_scroll_to_bottom
        )

    def _handle_rule_save(self, rule: TransactionRule) -> None:
        logger.info(f"Rule to be saved: {rule}")

    def _handle_rule_cancel(self) -> None:
        """Handle rule cancellation events from the RuleManagementContainer."""
        logger.info("Rule creation/editing cancelled")

    def _handle_scroll_to_bottom(self) -> None:
        """Handle scroll to bottom request from rule components."""
        logger.debug("Scroll to bottom requested")
        # Access the scroll container in the view and scroll to bottom
        if hasattr(self._view, '_transaction_panel') and self._view._transaction_panel:
            scroll_container = self._view._transaction_panel
            scroll_container.vertical_position = scroll_container.max_vertical_position
            logger.debug(f"Scrolled to bottom: position={scroll_container.vertical_position}, max={scroll_container.max_vertical_position}")
        else:
            logger.warning("Cannot scroll: transaction panel not available")

    def _handle_rule_deleted(self, rule_id: str) -> None:
        """Handle rule deletion from the RuleManagementContainer.
        
        This method removes the deleted rule ID from applied_rule_ids of affected transactions
        and updates the UI state accordingly.
        
        Args:
            rule_id: The ID of the rule that was deleted
        """
        try:
            # Set flag to prevent visibility updates during deletion processing
            self._rule_deletion_in_progress = True
            
            # Remove rule_id from current transaction if it's in the list
            if (self._current_transaction_display_data and 
                rule_id in self._current_transaction_display_data.applied_rule_ids):
                
                # Remove the deleted rule ID from the list
                self._current_transaction_display_data.remove_applied_rule(rule_id)
                logger.info(f"Removed rule {rule_id} from current transaction applied_rule_ids after rule deletion")
                
                # Update rule workspace with the updated transaction data
                # This will trigger the state machine to transition appropriately
                self._rule_workspace.update_transaction(self._current_transaction_display_data)
            
            # Also remove rule_id from any other transactions in the list
            for transaction_data in self._all_display_transactions:
                if rule_id in transaction_data.applied_rule_ids:
                    transaction_data.remove_applied_rule(rule_id)
                    logger.debug(f"Removed rule {rule_id} from transaction {transaction_data.display_id} applied_rule_ids")
                    
        except Exception as e:
            logger.error(f"Error handling rule deletion: {e}")
        finally:
            # Clear the deletion flag
            self._rule_deletion_in_progress = False

    def _handle_entry_save(self, content: str, file_path: str):
        """Handle entry save events from the EntrySaver component.

        Args:
            content: The content to save
            file_path: The file path to save the content to
        """
        logger.debug(f"Saving entry to {file_path}")

        if not content.strip():
            logger.warning(f"Empty content provided for {file_path}, skipping save.")
            return

        try:
            # Parse the Beancount output to validate it
            # This ensures the Beanquick-generated output is valid before saving
            entries, errors, _ = parser.parse_string(content)
            
            if errors:
                error_messages = [str(error) for error in errors]
                raise ValueError(f"{'\n\n'.join(error_messages)}")
            
            if not entries:
                raise ValueError("No valid entries generated from input")
            
            # Insert the parsed entries
            if not self._app.active_ledger:
                raise ValueError("No active ledger available")
            self._app.active_ledger.file.insert_entries_to_file(entries, file_path)

            logger.debug(f"Successfully saved Beanquick entry: {len(entries)} entries")
            
            # Trigger save completion callback if available
            if self._on_save_complete:
                try:
                    logger.debug("Triggering save completion callback")
                    # Pass the file path to the callback for success data collection
                    self._on_save_complete(file_path)
                except Exception as callback_error:
                    logger.error(f"Error in save completion callback: {callback_error}", exc_info=True)
                    # Don't re-raise callback errors as the save itself was successful
            
        except Exception as e:
            logger.error(f"Error saving entry: {e}", exc_info=True)
            raise

    def _handle_tab_select(self, tab_name: str):
        """Handle tab selection changes with reactive architecture support.
        
        Args:
            tab_name: Name of the selected tab
        """
        logger.debug(f"Tab selected: {tab_name}")
        
        if tab_name == "Preview":
            # Update preview with all categorized transactions when Preview tab is selected
            categorized_transactions = [
                t for t in self._all_display_transactions 
                if t.is_categorized
            ]
            
            # Use reactive observer pattern for all transactions preview
            if self._all_transactions_preview:
                self._all_transactions_preview.update_preview(categorized_transactions)
            
            logger.debug(f"Updated preview with {len(categorized_transactions)} categorized transactions using reactive observers")
    
    def set_all_transactions(self, display_transactions: List[TransactionDisplayData]):
        """Set the complete list of transactions for preview generation.
        
        Sets up FormValidator on all TransactionDisplayData instances for reactive validation.
        
        Args:
            display_transactions: Complete list of TransactionDisplayData objects
        """
        self._all_display_transactions = display_transactions
        
        # Pass transactions to rule workspace for direct rule application
        self._rule_workspace.set_all_transactions(display_transactions)

        logger.debug(f"Set {len(display_transactions)} transactions for preview and rule application")

    @property
    def view(self) -> InspectorPanelView:
        """Get the view instance."""
        return self._view
    
    @property
    def current_transaction(self) -> Optional[TransactionData]:
        """Get the currently displayed transaction."""
        return self._current_transaction
    
    def update_transaction(self, transaction_display_data: TransactionDisplayData):
        """Update the displayed transaction with reactive architecture support.
        
        Sets up FormValidator and uses observer pattern for component coordination.
        
        Args:
            transaction_display_data: Transaction data and categorization info
        """
        if transaction_display_data is None:
            raise ValueError("Transaction display data cannot be None")
        
        # Update state
        self._current_transaction_display_data = transaction_display_data
        self._current_transaction = transaction_display_data.transaction_data
        
        # Update view
        self._view.show_transaction_content()
        
        # Update components that use reactive updates
        self._entry_preview.update_single_preview(transaction_display_data)
        self._source_data_display.update_display(transaction_display_data)
        self._rule_workspace.update_transaction(transaction_display_data)
        
        # Note: Rule container visibility is now handled automatically by RuleWorkspace state machine

    def clear_display(self):
        """Clear the display and return to no-selection state."""
        # Clear state
        self._current_transaction = None
        self._current_transaction_display_data = None
        
        # Clear reactive components (they handle their own observer cleanup)
        self._entry_preview.clear_preview()
        self._source_data_display.clear_display()
        self._rule_workspace.update_transaction(None)  # This will clear and reset state
        
        # Update view
        self._view.show_no_selection()

    def cleanup(self):
        """Clean up resources and observers for proper shutdown."""
        # Clear current transaction state
        self._current_transaction = None
        self._current_transaction_display_data = None
        
        # Clean up reactive components
        if self._entry_preview:
            self._entry_preview.cleanup()
        
        if self._all_transactions_preview:
            self._all_transactions_preview.cleanup()
        
        self._rule_workspace.clear_fields()
        
        # Clear transaction list
        self._all_display_transactions.clear()
        
        logger.debug("InspectorPanelViewController cleanup completed")
    
    def get_form_validator(self) -> FormValidator:
        """Get the FormValidator instance for external access.
        
        Returns:
            FormValidator: The validator instance used by this controller
        """
        return self._form_validator