"""
Transaction Table component for Transaction Triage View.

This module provides the TransactionTable component that displays transactions
in a tabular format with proper formatting, status indicators, and selection
handling capabilities. Enhanced with observer pattern for reactive updates.
"""

from typing import List, Optional, Callable, Dict, Set
import logging

import toga
from toga.sources import ListSource
from toga.style import Pack
from toga.style.pack import RIGHT, CENTER  # type: ignore

from .models import TransactionDisplayData, ObserverType

logger = logging.getLogger(__name__)


class TransactionTable:
    """Transaction table component for displaying transaction data.
    
    This component provides a structured table view of transactions with
    columns for Status, Date, Payee, Narration, Amount.
    Enhanced with observer pattern for automatic updates when transaction data changes.
    """
    
    def __init__(self, transactions: List[TransactionDisplayData], on_selection_change: Optional[Callable[[Optional[TransactionDisplayData]], None]] = None):
        """Initialize the transaction table.
        
        Args:
            transactions: List of TransactionDisplayData objects to display
            on_selection_change: Optional callback function called when selection changes
        """
        self._transactions = transactions or []
        self._on_selection_change = on_selection_change
        self._table: Optional[toga.Table] = None
        self._data_store: Optional[ListSource] = None
        self._selected_transaction: Optional[TransactionDisplayData] = None
        
        # Observer management for reactive updates
        self._observer_ids: Dict[str, Dict[ObserverType, str]] = {}  # transaction_id -> observer_type -> observer_id
    
    def create_table(self) -> toga.Table:
        """Create the toga.Table widget with proper column configuration.
        
        Creates a table with columns for Status, Date, Payee, Narration, Amount
        with appropriate styling and data binding.
        
        Returns:
            toga.Table: The configured table widget
        """
        # Define column headers and accessors (added narration column)
        column_headers = ["Status", "Date", "Payee", "Narration", "Amount"]
        column_accessors = ["status", "date", "payee", "narration", "amount"]

        # Create the data source with accessors
        self._data_store = ListSource(
            accessors=column_accessors,
            data=[]
        )
        
        # Create the table widget
        self._table = toga.Table(
            headings=column_headers,
            data=self._data_store,
            style=Pack(flex=1),
            on_select=self._handle_selection_change
        )
        
        # Set up column options for alignment and width
        # This must be set before any operations that trigger rehint()
        try:
            self._table.column_options = {
                "status": {
                    "alignment": CENTER,
                    "min_width": 40,  # set width only will cause the table horizontal scrollbar to appear
                    "max_width": 60,  # so we set min_width and max_width
                },
                "amount": {
                    "alignment": RIGHT
                }
            }
        except AttributeError:
            # Fallback if column_options is not available on this table implementation
            pass
        
        # Populate with initial data and setup observers
        self.populate_data(self._transactions)
        
        return self._table
    
    def populate_data(self, transactions: List[TransactionDisplayData]):
        """Convert TransactionData list to table format.
        
        Converts the list of TransactionDisplayData objects into the format
        required by the toga.Table widget, applying proper formatting.
        
        Args:
            transactions: List of TransactionDisplayData objects to display
        """
        if self._data_store is None:
            return
        
        # Remove observers from old transactions
        self._cleanup_observers()
        
        self._transactions = transactions or []
        
        # Clear existing data
        self._data_store.clear()
        
        # Convert transactions to table format
        for transaction_display in self._transactions:
            transaction = transaction_display.transaction_data
            
            # Format the data for display
            formatted_row = {
                "status": transaction_display.status_icon,
                "date": str(transaction.date),
                "payee": transaction.payee,
                "narration": transaction.narration or "",  # Handle None narration
                "amount": self._format_amount(transaction.amount),
                "_transaction_ref": transaction_display  # Hidden reference for selection
            }
            
            self._data_store.append(formatted_row)
        
        # Setup observers for new transactions
        self._setup_observers()
    
    def _format_amount(self, amount) -> str:
        """Format amount for right-aligned display.
        
        Formats the amount with proper decimal places and right-alignment
        padding for consistent display.
        
        Args:
            amount: The amount to format (Decimal or numeric type)
            
        Returns:
            str: Formatted amount string with right-alignment padding
        """
        # Convert to string with 2 decimal places
        amount_str = f"{float(amount):.2f}"
        
        # Add right-alignment padding (spaces on the left)
        # This helps with visual alignment in the table
        return f"{amount_str:>12}"
    
    def _handle_selection_change(self, widget, **kwargs):
        """Handle table selection change events.
        
        Called when a user selects a different row in the table.
        Retrieves the associated TransactionDisplayData and calls
        the selection change callback if provided.
        
        Args:
            widget: The table widget that triggered the event
            **kwargs: Additional arguments for future compatibility
        """
        # Get the selected row from the widget's selection property
        row = widget.selection

        if not row:
            self._selected_transaction = None
            if self._on_selection_change:
                self._on_selection_change(None)
            return
        
        # Find the transaction data associated with this row
        selected_transaction = None
        
        # Get the row index to find the corresponding transaction
        try:
            if hasattr(row, '_transaction_ref'):
                selected_transaction = row._transaction_ref
            else:
                # Fallback: find by matching data using Row attributes
                if self._data_store:
                    for i in range(len(self._data_store)):
                        data_row = self._data_store[i]
                        if (data_row.status == row.status and 
                            data_row.date == row.date and 
                            data_row.payee == row.payee and
                            data_row.narration == row.narration and
                            data_row.amount == row.amount):
                            if i < len(self._transactions):
                                selected_transaction = self._transactions[i]
                            break
        except (AttributeError, IndexError):
            # If we can't find the transaction, try by index
            try:
                if self._data_store is not None:
                    row_index = self._data_store.index(row)
                    if 0 <= row_index < len(self._transactions):
                        selected_transaction = self._transactions[row_index]
            except (ValueError, IndexError):
                selected_transaction = None
        
        self._selected_transaction = selected_transaction
        
        # Call the selection change callback if provided
        if self._on_selection_change:
            self._on_selection_change(selected_transaction)
    
    def get_selected_transaction(self) -> Optional[TransactionDisplayData]:
        """Get the currently selected transaction.
        
        Returns:
            Optional[TransactionDisplayData]: The currently selected transaction, or None
        """
        return self._selected_transaction
    
    @property
    def transaction_count(self) -> int:
        """Get the number of transactions in the table.
        
        Returns:
            int: The number of transactions currently displayed
        """
        return len(self._transactions)
    
    @property
    def has_transactions(self) -> bool:
        """Check if the table has any transactions.
        
        Returns:
            bool: True if there are transactions to display, False otherwise
        """
        return len(self._transactions) > 0
    
    @property
    def is_selection_valid(self) -> bool:
        """Check if the current selection is valid.
        
        Returns:
            bool: True if there is a valid selection, False otherwise
        """
        return (self._selected_transaction is not None and 
                self._selected_transaction in self._transactions)
    
    def _setup_observers(self) -> None:
        """Setup observers for all transactions to enable reactive updates."""
        for transaction_display in self._transactions:
            self._add_transaction_observers(transaction_display)
    
    def _add_transaction_observers(self, transaction_display: TransactionDisplayData) -> None:
        """Add observers for a specific transaction.
        
        This method is idempotent - it won't add duplicate observers if they're already present.
        
        Args:
            transaction_display: TransactionDisplayData to observe
        """
        transaction_id = transaction_display.display_id
        
        # Skip if already observing this transaction (idempotent behavior)
        if transaction_id in self._observer_ids:
            logger.debug(f"Observers already set up for transaction {transaction_id}, skipping duplicate setup")
            return
        
        self._observer_ids[transaction_id] = {}
        
        try:
            # Add data change observer
            data_observer_id = transaction_display.add_observer(
                self._on_transaction_data_changed,
                ObserverType.DATA_CHANGED
            )
            self._observer_ids[transaction_id][ObserverType.DATA_CHANGED] = data_observer_id
            
            # Add status change observer
            status_observer_id = transaction_display.add_observer(
                self._on_transaction_status_changed,
                ObserverType.STATUS_CHANGED
            )
            self._observer_ids[transaction_id][ObserverType.STATUS_CHANGED] = status_observer_id
            
            # Add validation change observer
            validation_observer_id = transaction_display.add_observer(
                self._on_transaction_validation_changed,
                ObserverType.VALIDATION_CHANGED
            )
            self._observer_ids[transaction_id][ObserverType.VALIDATION_CHANGED] = validation_observer_id
            
            logger.debug(f"Set up observers for transaction {transaction_id}")
            
        except Exception as e:
            logger.error(f"Error setting up observers for transaction {transaction_id}: {e}")
            # Clean up partial observer setup on error
            if transaction_id in self._observer_ids:
                del self._observer_ids[transaction_id]
    
    def _cleanup_observers(self) -> None:
        """Remove all observers from current transactions."""
        for transaction_display in self._transactions:
            self._remove_transaction_observers(transaction_display)
        self._observer_ids.clear()
    
    def _remove_transaction_observers(self, transaction_display: TransactionDisplayData) -> None:
        """Remove observers for a specific transaction.
        
        Args:
            transaction_display: TransactionDisplayData to stop observing
        """
        transaction_id = transaction_display.display_id
        
        if transaction_id not in self._observer_ids:
            return
        
        try:
            # Remove all observer types for this transaction
            for observer_type, observer_id in self._observer_ids[transaction_id].items():
                transaction_display.remove_observer(observer_id, observer_type)
            
            # Clean up the observer ID tracking
            del self._observer_ids[transaction_id]
            
        except Exception as e:
            logger.error(f"Error removing observers for transaction {transaction_id}: {e}")
    
    def _on_transaction_data_changed(self, transaction_display: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle data changes in observed transactions.
        
        Args:
            transaction_display: The transaction that changed
            changed_fields: Set of field names that changed
        """
        try:
            self._update_transaction_row(transaction_display, changed_fields)
        except Exception as e:
            logger.error(f"Error handling transaction data change: {e}")

    def _on_transaction_status_changed(self, transaction_display: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle status changes in observed transactions.
        
        Args:
            transaction_display: The transaction whose status changed
            changed_fields: Set of field names that changed
        """
        try:
            # Update status-related display elements
            self._update_transaction_status(transaction_display)
        except Exception as e:
            logger.error(f"Error handling transaction status change: {e}")
    
    def _on_transaction_validation_changed(self, transaction_display: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle validation changes in observed transactions.
        
        This is a UI-only handler that updates display elements when validation changes.
        The business logic for status updates is handled in TransactionDisplayData itself.
        
        Args:
            transaction_display: The transaction whose validation changed
            changed_fields: Set of field names that changed
        """
        try:
            # Just update any validation-related UI elements
            # The business logic for status updates is handled by TransactionDisplayData
            self._update_transaction_row(transaction_display, changed_fields)
        except Exception as e:
            logger.error(f"Error handling transaction validation change: {e}")
    
    def _update_transaction_row(self, transaction_display: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Update a specific transaction row in the table efficiently.
        
        Args:
            transaction_display: The transaction to update
            changed_fields: Set of field names that changed for optimization
        """
        if self._data_store is None:
            return
        
        # Find the row index for this transaction
        row_index = self._find_transaction_row_index(transaction_display)
        if row_index == -1:
            return
        
        try:
            # Update the row data efficiently based on changed fields
            # Since ListSource is reactive, modifying the data will automatically update the table
            row_data = self._data_store[row_index]
            
            if not changed_fields or 'status' in changed_fields:
                row_data.status = transaction_display.status_icon
            
            # The ListSource will automatically notify the table of changes
            # No need to manually refresh the table
            
        except Exception as e:
            logger.error(f"Error updating transaction row: {e}")

    def _update_transaction_status(self, transaction_display: TransactionDisplayData) -> None:
        """Update only the status indicator for a specific transaction.
        
        Args:
            transaction_display: The transaction whose status changed
        """
        if self._data_store is None:
            return
        
        row_index = self._find_transaction_row_index(transaction_display)
        if row_index == -1:
            return
        
        try:
            # Update only the status column - ListSource will handle the UI update
            self._data_store[row_index].status = transaction_display.status_icon
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
    
    def _find_transaction_row_index(self, transaction_display: TransactionDisplayData) -> int:
        """Find the row index for a specific transaction.
        
        Args:
            transaction_display: The transaction to find
            
        Returns:
            int: Row index, or -1 if not found
        """
        try:
            return self._transactions.index(transaction_display)
        except ValueError:
            return -1
    
    def _get_transaction_from_row(self, row) -> Optional[TransactionDisplayData]:
        """Get the TransactionDisplayData associated with a table row.
        
        Args:
            row: Table row object
            
        Returns:
            Optional[TransactionDisplayData]: Associated transaction or None
        """
        try:
            if hasattr(row, '_transaction_ref'):
                return row._transaction_ref
            
            # Fallback: find by row index
            if self._data_store:
                row_index = self._data_store.index(row)
                if 0 <= row_index < len(self._transactions):
                    return self._transactions[row_index]
        except (AttributeError, ValueError, IndexError):
            pass
        
        return None
    
    def cleanup(self) -> None:
        """Cleanup all observers when the table is destroyed."""
        self._cleanup_observers()