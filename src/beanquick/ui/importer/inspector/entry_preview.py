"""
Preview component for beancount entry generation and display.

This module provides the EntryPreview that handles the generation
and display of beancount entry previews from transaction data and account assignments.
Enhanced with observer pattern for reactive updates and validation error display.
"""

import logging
import sys
from typing import Optional, List, Set

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, BOLD  # type: ignore
from beancount.parser import printer

from beanquick.ui.importer.transaction_review.models import TransactionDisplayData, ObserverType
from beanquick.util.syntax_highlighter import BeanquickSyntaxHighlighter
from beanquick.importers.beancount_entry_factory import (
    BeancountEntryFactory,
    BeancountEntryCreationError,
    InvalidAccountError,
    InvalidAmountError,
    InvalidTransactionDataError
)

logger = logging.getLogger(__name__)

WIDGET_SPACING = 5
DEFAULT_PREVIEW_HEIGHT = 120

class EntryPreview:
    """Component for displaying beancount entry previews with reactive updates.
    
    This component handles the generation and display of beancount entry previews
    from TransactionDisplayData objects. It provides comprehensive error handling,
    user-friendly error messages, and automatic updates via the observer pattern.
    Enhanced with validation error display and field-specific update optimization.
    """

    def __init__(self, title: Optional[str] = None, auto_height: bool = False):
        """Initialize the preview component."""
        self._preview_text: Optional[toga.MultilineTextInput] = None
        self._validation_text: Optional[toga.MultilineTextInput] = None
        self._current_display_transactions: List[TransactionDisplayData] = []
        self._title = title
        self._auto_height = auto_height
        self._observer_ids: List[tuple] = []  # List of (transaction, observer_id, observer_type) tuples
        self._last_preview_hash: Optional[int] = None  # For optimization
        self._container: Optional[toga.Box] = None  # Container reference for dynamic widget management
        self._validation_text_visible: bool = False  # Track validation text visibility
        self._syntax_highlighter: Optional[BeanquickSyntaxHighlighter] = None  # Syntax highlighter
    
    def create_widget(self) -> toga.Box:
        """Create the preview section widget with validation display.
        
        Returns:
            toga.Box: Container with preview and validation areas
        """
        self._container = toga.Box(style=Pack(direction=COLUMN))

        assert self._container is not None

        if self._title:
            title_label = toga.Label(
                self._title,
                style=Pack(font_weight=BOLD, margin_bottom=WIDGET_SPACING*2)
            )
            self._container.add(title_label)

        # Preview text area
        self._preview_text = toga.MultilineTextInput(
            readonly=True,
            style=Pack(
                font_family="monospace"
            )
        )
        
        # Validation errors text area (smaller, initially hidden)
        self._validation_text = toga.MultilineTextInput(
            readonly=True,
            style=Pack(
                font_family="monospace",
                background_color="#fff5f5",  # Light red background for errors
                color="#d32f2f"  # Red text for errors
            )
        )

        assert self._preview_text is not None
        
        # Initialize syntax highlighter for macOS
        if sys.platform == "darwin":
            self._preview_text._impl.native_text.setAutomaticQuoteSubstitutionEnabled_(False)
            
            # Initialize syntax highlighter
            try:
                # Default to light theme for now - could be made configurable
                color_scheme = 'github_light'
                self._syntax_highlighter = BeanquickSyntaxHighlighter(
                    self._preview_text._impl.native_text,
                    color_scheme=color_scheme
                )
            except Exception as e:
                logger.warning(f"Failed to initialize syntax highlighter: {e}")
                self._syntax_highlighter = None
        
        if self._auto_height:
            self._container.style.flex = 1
            self._preview_text.style.flex = 1
        else:
            self._preview_text.style.height = DEFAULT_PREVIEW_HEIGHT

        self._container.add(self._preview_text)
        # Don't add validation text initially - it will be added when needed
        
        return self._container
    
    def observe_transactions(self, display_transactions: List[TransactionDisplayData]) -> None:
        """Start observing a list of transactions for automatic updates.
        
        Args:
            display_transactions: List of TransactionDisplayData objects to observe
        """
        # Remove existing observers
        self._remove_all_observers()
        
        # Store current data for reference
        self._current_display_transactions = display_transactions
        
        # Add observers for each transaction
        for transaction in display_transactions:
            # Observe data changes
            data_observer_id = transaction.add_observer(
                self._on_data_changed, 
                ObserverType.DATA_CHANGED
            )
            self._observer_ids.append((transaction, data_observer_id, ObserverType.DATA_CHANGED))
            
            # Observe validation changes
            validation_observer_id = transaction.add_observer(
                self._on_validation_changed,
                ObserverType.VALIDATION_CHANGED
            )
            self._observer_ids.append((transaction, validation_observer_id, ObserverType.VALIDATION_CHANGED))
        
        # Initial update
        self._update_preview_content()
    
    def observe_single_transaction(self, display_transaction: TransactionDisplayData) -> None:
        """Start observing a single transaction for automatic updates (convenience method).
        
        Args:
            display_transaction: The TransactionDisplayData object to observe
        """
        self.observe_transactions([display_transaction])
    
    def update_preview(self, display_transactions: List[TransactionDisplayData]) -> None:
        """Update the preview with transaction display data (legacy method for compatibility).
        
        This method is kept for backward compatibility but now uses the observer pattern.
        
        Args:
            display_transactions: List of TransactionDisplayData objects to preview
        """
        self.observe_transactions(display_transactions)
    
    def get_preview_content(self) -> str | None:
        """Get the current preview text.

        Returns:
            The current preview text or None if not available
        """
        if not self._preview_text:
            logger.warning("Preview text widget not initialized")
            return None
        return self._preview_text.value
    
    def update_single_preview(self, display_transaction: TransactionDisplayData) -> None:
        """Update the preview with a single transaction (legacy method for compatibility).
        
        Args:
            display_transaction: The TransactionDisplayData object to preview
        """
        self.observe_single_transaction(display_transaction)
        self._update_validation_display()
        
    def clear_preview(self) -> None:
        """Clear the preview display and remove all observers."""
        if self._preview_text:
            self._preview_text.value = ""
        
        if self._validation_text and self._validation_text_visible:
            self._validation_text.value = ""
            self._hide_validation_text()

        self._remove_all_observers()
        self._current_display_transactions = []
        self._last_preview_hash = None
    
    def _on_data_changed(self, transaction: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle data changes in observed transactions.
        
        Args:
            transaction: The transaction that changed
            changed_fields: Set of field names that changed (optional)
        """
        # Only update if the change affects preview generation
        if self._should_update_for_fields(changed_fields):
            self._update_preview_content()
    
    def _on_validation_changed(self, transaction: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle validation changes in observed transactions.
        
        Args:
            transaction: The transaction with validation changes
            changed_fields: Set of field names that changed (optional)
        """
        self._update_validation_display()
    
    def _should_update_for_fields(self, changed_fields: Optional[Set[str]]) -> bool:
        """Check if preview should update based on changed fields.
        
        Args:
            changed_fields: Set of field names that changed
            
        Returns:
            bool: True if preview should be updated
        """
        if not changed_fields:
            return True  # Update for any unspecified change
        
        # Preview depends on account fields primarily
        preview_relevant_fields = {'source_account', 'destination_account', 'payee', 'narration', 'status'}
        return bool(preview_relevant_fields.intersection(changed_fields))
    
    def _update_preview_content(self) -> None:
        """Update the preview content with optimization."""
        if not self._preview_text:
            logger.warning("Preview text widget not initialized")
            return
        
        # Generate preview text
        preview_text = self._generate_preview_text()
        
        # Optimization: only update if content actually changed
        preview_hash = hash(preview_text)
        if preview_hash != self._last_preview_hash:
            self._preview_text.value = preview_text
            self._last_preview_hash = preview_hash
            
            # Apply syntax highlighting if available
            if self._syntax_highlighter and preview_text:
                self._syntax_highlighter.apply_highlighting(preview_text)
            
            logger.debug("Preview content updated")
        else:
            logger.debug("Preview content unchanged, skipping update")
    
    def _update_validation_display(self) -> None:
        """Update the validation error display."""
        if not self._validation_text:
            return
        
        validation_messages = []
        has_errors = False
        
        for transaction in self._current_display_transactions:
            validation_result = transaction.get_validation_result()
            print('validation result', validation_result)
            if validation_result and not validation_result.is_valid:
                has_errors = True
                
                # Add field-specific errors
                for field_name, errors in validation_result.field_errors.items():
                    for error in errors:
                        validation_messages.append(f"• {field_name}: {error.message}")
                        if error.suggestion:
                            validation_messages.append(f"  Suggestion: {error.suggestion}")
                
                # Add global errors
                for error in validation_result.global_errors:
                    validation_messages.append(f"• {error.message}")
                    if error.suggestion:
                        validation_messages.append(f"  Suggestion: {error.suggestion}")
        
        if has_errors:
            self._validation_text.value = "\n".join(validation_messages)
            self._show_validation_text()
        else:
            self._validation_text.value = ""
            self._hide_validation_text()
    
    def _show_validation_text(self) -> None:
        """Show the validation text widget."""
        if not self._validation_text_visible and self._container and self._validation_text:
            self._container.add(self._validation_text)
            self._validation_text_visible = True
    
    def _hide_validation_text(self) -> None:
        """Hide the validation text widget."""
        if self._validation_text_visible and self._container and self._validation_text:
            try:
                self._container.remove(self._validation_text)
                self._validation_text_visible = False
            except ValueError:
                # Widget might not be in container, ignore
                self._validation_text_visible = False
    
    def _remove_all_observers(self) -> None:
        """Remove all observers from transactions."""
        for transaction, observer_id, observer_type in self._observer_ids:
            try:
                transaction.remove_observer(observer_id, observer_type)
            except Exception as e:
                logger.warning(f"Error removing observer {observer_id}: {e}")
        
        self._observer_ids.clear()
    
    def _generate_preview_text(self) -> str:
        """Generate the preview text for the current transactions.
        
        Returns:
            str: The formatted preview text or error message
        """
        if not self._current_display_transactions:
            return "No transactions confirmed"

        # Sort transactions by date in ascending order
        sorted_transactions = sorted(
            self._current_display_transactions,
            key=lambda t: t.transaction_data.date
        )

        # Generate previews for all transactions
        preview_parts = []
        
        for i, display_transaction in enumerate(sorted_transactions):
            source_account = display_transaction.source_account or ""
            destination_account = display_transaction.destination_account or ""
            
            if not source_account.strip() or not destination_account.strip():
                preview_parts.append(f"; Please specify both source and destination accounts")
                continue
            
            try:
                # Generate beancount entry with error handling
                entry = self._generate_beancount_entry_with_error_handling(
                    display_transaction, source_account.strip(), destination_account.strip()
                )
                
                if entry is None:
                    preview_parts.append(f"; Unable to generate preview")
                    continue
                
                # Check if the result is an error message string
                if isinstance(entry, str):
                    preview_parts.append(f"; {entry}")
                    continue
                
                # Format entry using beancount printer
                try:
                    formatted_entry = printer.format_entry(entry)
                    preview_parts.append(formatted_entry)
                except ValueError as e:
                    # Handle specific beancount printer errors
                    error_msg = str(e)
                    if "Unexpected value" in error_msg:
                        logger.warning(f"Beancount printer rejected metadata: {error_msg}")
                        preview_parts.append(
                            f"; Metadata Error\n"
                            f"; The transaction contains metadata that cannot be displayed in the preview.\n"
                            f"; This won't affect the actual beancount entry generation."
                        )
                    else:
                        logger.warning(f"Beancount printer error: {error_msg}")
                        preview_parts.append(f"; Preview format error: {error_msg}")
                except Exception as e:
                    logger.warning(f"Unexpected error in beancount printer: {e}")
                    preview_parts.append(f"; Preview formatting failed: {str(e)}")
                
            except Exception as e:
                logger.error(f"Unexpected error generating preview: {e}")
                preview_parts.append(f"; Error generating preview: {str(e)}")
        
        # Join all preview parts with double newlines for separation
        return "\n\n".join(preview_parts)
    
    def _generate_beancount_entry_with_error_handling(self, display_transaction: TransactionDisplayData,
                                                     source_account: str, destination_account: str):
        """Generate beancount entry with comprehensive error handling.
        
        Args:
            display_transaction: The TransactionDisplayData object
            source_account: The source account
            destination_account: The destination account
        
        Returns:
            The beancount entry or an error message string if generation fails
        """
        try:
            return BeancountEntryFactory.create_transaction(
                transaction_data=display_transaction.transaction_data,
                source_account=source_account,
                destination_account=destination_account,
                source_file="preview",
                line_number=1
            )
            
        except InvalidAccountError as e:
            logger.debug(f"Invalid account error: {e}")
            # Return a helpful error message for invalid accounts
            if "source_account" in str(e).lower():
                return self._create_error_message(
                    "Invalid Source Account",
                    f"The source account '{source_account}' is not valid.",
                    "Account names must start with a capital letter and use colons to separate components (e.g., 'Assets:Checking')."
                )
            elif "destination_account" in str(e).lower():
                return self._create_error_message(
                    "Invalid Destination Account", 
                    f"The destination account '{destination_account}' is not valid.",
                    "Account names must start with a capital letter and use colons to separate components (e.g., 'Expenses:Food')."
                )
            else:
                return self._create_error_message(
                    "Invalid Account",
                    str(e),
                    "Account names must start with a capital letter and use colons to separate components."
                )
                
        except InvalidAmountError as e:
            logger.debug(f"Invalid amount error: {e}")
            return self._create_error_message(
                "Invalid Amount",
                f"The transaction amount cannot be processed: {str(e)}",
                "Please check that the amount is a valid number."
            )
            
        except InvalidTransactionDataError as e:
            logger.debug(f"Invalid transaction data error: {e}")
            return self._create_error_message(
                "Invalid Transaction Data",
                str(e),
                "Please check that all required transaction fields are properly filled."
            )
            
        except BeancountEntryCreationError as e:
            logger.debug(f"Beancount entry creation error: {e}")
            return self._create_error_message(
                "Entry Creation Error",
                str(e),
                "Please check your account names and transaction data."
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in beancount entry generation: {e}")
            return self._create_error_message(
                "Unexpected Error",
                f"An unexpected error occurred: {str(e)}",
                "Please try again or contact support if the problem persists."
            )
    
    def _create_error_message(self, title: str, message: str, suggestion: str) -> str:
        """Create a formatted error message for display.
        
        Args:
            title: The error title
            message: The main error message
            suggestion: A helpful suggestion for the user
            
        Returns:
            str: Formatted error message
        """
        return f"; {title}\n; {message}\n; \n; Suggestion: {suggestion}"
    
    def cleanup(self) -> None:
        """Clean up observers and resources."""
        self._remove_all_observers()
        self._current_display_transactions = []
        self._last_preview_hash = None
        self._syntax_highlighter = None
        logger.debug("EntryPreview cleanup completed")
    
    def set_syntax_color_scheme(self, scheme_name: str):
        """Set the syntax highlighting color scheme.
        
        Args:
            scheme_name: Name of the color scheme to use
        """
        if self._syntax_highlighter:
            self._syntax_highlighter.set_color_scheme(scheme_name)
            self._syntax_highlighter.refresh_highlighting()
    
    def get_available_color_schemes(self) -> List[str]:
        """Get list of available color schemes.
        
        Returns:
            List of available color scheme names
        """
        if self._syntax_highlighter:
            return self._syntax_highlighter.get_available_schemes()
        return []
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception as e:
            logger.warning(f"Error during EntryPreview cleanup: {e}")