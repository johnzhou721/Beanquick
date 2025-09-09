"""
Transaction categorization component for comprehensive field management.

This module provides the TransactionCategorizer that handles all
transaction field management including accounts, payee, and narration.
Enhanced with reactive updates and observer pattern integration.
"""

import logging
import sys
from typing import Optional, Set, List, Callable

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, BOLD  # type: ignore

from beanquick.ui.importer.transaction_review.models import TransactionDisplayData, ObserverType

from ...components.autocomplete_account_field import AutocompleteAccountField

logger = logging.getLogger(__name__)

WIDGET_SPACING = 5
LABEL_WIDTH = 80

class TransactionCategorizer():
    """Component for managing comprehensive transaction categorization fields.

    This component handles all transaction fields including source_account, destination_account,
    payee, and narration with support for autocomplete on account fields.
    It provides reactive updates through the observer pattern.
    Enhanced to use TransactionDisplayData reactive update methods.
    """

    def __init__(self, account_completer):
        """Initialize the transaction categorization component.
        
        Args:
            account_completer: AccountCompleter service for account field suggestions
        
        Observer Pattern:
            - Subscribes to DATA_CHANGED event
            - Updates UI automatically when TransactionDisplayData changes
            - Optimizes updates using field-specific change detection
        
        Lifecycle:
            1. update_data() -> sets up observers
            2. User changes field -> _handle_field_change()
            3. Reactive update -> _update_transaction_data()
            4. Model notifies -> _on_data_changed()
            5. clear_fields() -> cleanup observers
        """
        self._account_completer = account_completer

        # UI components
        self._source_account_field: Optional[AutocompleteAccountField] = None
        self._destination_account_field: Optional[AutocompleteAccountField] = None
        self._payee_field: Optional[toga.TextInput] = None
        self._narration_field: Optional[toga.TextInput] = None
        self._create_rule_switch: Optional[toga.Switch] = None
        self._rule_switch_container: Optional[toga.Box] = None
        self._main_container: Optional[toga.Box] = None

        # Reactive state management
        self._current_source_account: str = ""
        self._current_destination_account: str = ""
        self._current_payee: str = ""
        self._current_narration: str = ""
        self._transaction_display_data: Optional[TransactionDisplayData] = None
        self._data_observer_id: Optional[str] = None
        self._validation_observer_id: Optional[str] = None
        
        # Create rule switch observers
        self._switch_observers: List[Callable[[bool], None]] = []

    def create_widget(self) -> toga.Box:
        """Create the comprehensive transaction categorization widget.
        
        Returns:
            toga.Box: Container with all transaction field rows (label + input per row)
        """
        container = toga.Box(style=Pack(direction=COLUMN, margin=(WIDGET_SPACING*2, 0)))
        self._main_container = container

        # Title label
        title_label = toga.Label(
            "Transaction Categorization",
            style=Pack(font_weight=BOLD, margin_bottom=WIDGET_SPACING*2)
        )

        container.add(title_label)

        # Source Account Row
        source_account_row = self._create_field_row(
            "Source:",
            "source_account",
            "e.g., Assets:Checking",
            is_account_field=True
        )
        container.add(source_account_row)
        
        # Destination Account Row
        destination_account_row = self._create_field_row(
            "Destination:",
            "destination_account", 
            "e.g., Expenses:Food:Groceries",
            is_account_field=True
        )
        container.add(destination_account_row)
        
        # Payee Row
        payee_row = self._create_field_row(
            "Payee:",
            "payee",
            "e.g., Safeway"
        )
        container.add(payee_row)
        
        # Narration Row
        narration_row = self._create_field_row(
            "Narration:",
            "narration",
            "e.g., Weekly grocery shopping"
        )
        container.add(narration_row)

        container.add(toga.Divider(style=Pack(margin=(WIDGET_SPACING, 0))))

        # Create rule switch container (initially hidden)
        self._rule_switch_container = self._create_rule_switch_container()

        # macOS-specific fix for tab navigation
        if sys.platform == "darwin":
            self._fix_macos_tab_chain()

        return container
    
    def _create_field_row(self, label_text: str, field_key: str, placeholder: str, 
                         is_account_field: bool = False) -> toga.Box:
        """Create a uniform field row with label and input.
        
        Args:
            label_text: Text for the label
            field_key: Key identifying the field type
            placeholder: Placeholder text for the input
            is_account_field: Whether this field should use autocomplete
            
        Returns:
            toga.Box: Row container with label and input field
        """
        row = toga.Box(style=Pack(direction=ROW, margin_bottom=WIDGET_SPACING))
        
        # Label (fixed width for alignment)
        label = toga.Label(
            label_text,
            style=Pack(
                width=LABEL_WIDTH,
                text_align=LEFT,
            )
        )
        row.add(label)
        
        # Input field container
        field_container = toga.Box(style=Pack(direction=COLUMN, flex=1))
        
        if is_account_field:
            # Create autocomplete account field
            if field_key == "source_account":
                self._source_account_field = AutocompleteAccountField(
                    placeholder=placeholder,
                    account_completer=self._account_completer,
                    on_change=lambda widget, **kwargs: self._handle_field_change("source_account", widget, **kwargs)
                )
                field_container.add(self._source_account_field.widget)
                self._source_account_field.setup_in_container(field_container)
            elif field_key == "destination_account":
                self._destination_account_field = AutocompleteAccountField(
                    placeholder=placeholder,
                    account_completer=self._account_completer,
                    on_change=lambda widget, **kwargs: self._handle_field_change("destination_account", widget, **kwargs)
                )
                field_container.add(self._destination_account_field.widget)
                self._destination_account_field.setup_in_container(field_container)
        else:
            # Create regular text input
            text_input = toga.TextInput(
                placeholder=placeholder,
                style=Pack(flex=1),
                on_change=lambda widget, **kwargs: self._handle_field_change(field_key, widget, **kwargs)
            )
            
            if field_key == "payee":
                self._payee_field = text_input
            elif field_key == "narration":
                self._narration_field = text_input
                
            field_container.add(text_input)
        
        row.add(field_container)
        return row
    
    def _create_rule_switch_container(self) -> toga.Box:
        """Create the rule switch container with proper layout.
        
        Returns:
            toga.Box: Container with the create rule switch
        """
        row = toga.Box(style=Pack(direction=ROW, margin_bottom=WIDGET_SPACING))

        # Add spacing to align with field labels
        # row.add(toga.Box(style=Pack(width=LABEL_WIDTH)))

        # Create the switch
        self._create_rule_switch = toga.Switch(
            "Save this categorization as a new rule",
            style=Pack(margin_top=WIDGET_SPACING),
            on_change=self._on_create_rule_switch_changed
        )
        row.add(self._create_rule_switch)
        
        return row
    
    def set_fields(self, source_account: str = "", destination_account: str = "", 
                  payee: str = "", narration: str = "") -> None:
        """Set all field values.
        
        Args:
            source_account: The source account value to set
            destination_account: The destination account value to set
            payee: The payee value to set
            narration: The narration value to set
        """
        self._current_source_account = source_account or ""
        self._current_destination_account = destination_account or ""
        self._current_payee = payee or ""
        self._current_narration = narration or ""

        if self._source_account_field:
            self._source_account_field.value = self._current_source_account
        if self._destination_account_field:
            self._destination_account_field.value = self._current_destination_account
        if self._payee_field:
            self._payee_field.value = self._current_payee
        if self._narration_field:
            self._narration_field.value = self._current_narration

        # Reset rule switch state
        if self._create_rule_switch:
            self._create_rule_switch.value = False

    def _handle_field_change(self, field_key: str, widget, **kwargs) -> None:
        """Handle value change in any field.
        
        Uses reactive update methods to notify observers.
        
        Args:
            field_key: Which field changed ('source_account', 'destination_account', 'payee', 'narration')
            widget: The widget that triggered the change
            **kwargs: Additional event arguments
        """
        new_value = ""
        
        if field_key == "source_account" and self._source_account_field:
            new_value = self._source_account_field.value or ""
            if new_value != self._current_source_account:
                self._current_source_account = new_value
                self._update_transaction_field("source_account", new_value)
                
        elif field_key == "destination_account" and self._destination_account_field:
            new_value = self._destination_account_field.value or ""
            if new_value != self._current_destination_account:
                self._current_destination_account = new_value
                self._update_transaction_field("destination_account", new_value)
                
        elif field_key == "payee" and self._payee_field:
            new_value = self._payee_field.value or ""
            if new_value != self._current_payee:
                self._current_payee = new_value
                self._update_transaction_field("payee", new_value)
                
        elif field_key == "narration" and self._narration_field:
            new_value = self._narration_field.value or ""
            if new_value != self._current_narration:
                self._current_narration = new_value
                self._update_transaction_field("narration", new_value)
    
    def _update_transaction_field(self, field_key: str, value: str) -> None:
        """Update TransactionDisplayData using reactive update methods.
        
        This method uses the appropriate reactive update method based on the field key,
        which notifies all observers automatically.
        
        Args:
            field_key: The field to update
            value: The new value
        """
        if not self._transaction_display_data:
            return
        
        try:
            # Use reactive update methods based on field key
            if field_key == 'source_account':
                self._transaction_display_data.update_source_account(value)
            elif field_key == 'destination_account':
                self._transaction_display_data.update_destination_account(value)
            elif field_key == 'payee':
                self._transaction_display_data.update_payee(value)
            elif field_key == 'narration':
                self._transaction_display_data.update_narration(value)
            else:
                logger.warning(f"Unknown field key: {field_key}")
        except Exception as e:
            logger.error(f"Error updating transaction field {field_key}: {e}")

    def update_data(self, transaction_display_data: TransactionDisplayData) -> None:
        """Update the component with new transaction display data.
        
        Sets up observer subscriptions for reactive updates.
        
        Args:
            transaction_display_data: TransactionDisplayData to observe and update
        """
        # Clean up previous observers
        self._cleanup_observers()
        
        # Store new transaction data
        self._transaction_display_data = transaction_display_data
        
        # Set up observers for reactive updates
        self._setup_observers()
        
        # Update UI with current data
        source_account = getattr(transaction_display_data, 'source_account', "")
        destination_account = getattr(transaction_display_data, 'destination_account', "")
        
        # Get payee and narration directly from TransactionData
        payee = transaction_display_data.transaction_data.payee or ""
        narration = transaction_display_data.transaction_data.narration or ""
        
        self.set_fields(source_account, destination_account, payee, narration)
        
        # Initial validation check for rule switch visibility
        self._update_rule_switch_visibility()

    def clear_fields(self) -> None:
        """Clear all fields and reset internal state."""
        # Clean up observers
        self._cleanup_observers()
        
        # Reset state
        self._current_source_account = ""
        self._current_destination_account = ""
        self._current_payee = ""
        self._current_narration = ""
        self._transaction_display_data = None

        # Clear UI
        if self._source_account_field and hasattr(self._source_account_field, 'clear'):
            self._source_account_field.clear()
        if self._destination_account_field and hasattr(self._destination_account_field, 'clear'):
            self._destination_account_field.clear()
        if self._payee_field:
            self._payee_field.value = ""
        if self._narration_field:
            self._narration_field.value = ""
        
        # Reset rule switch state and hide it
        if self._create_rule_switch:
            self._create_rule_switch.value = False
        self._hide_rule_switch()
    
    def _setup_observers(self) -> None:
        """Set up observer subscriptions for reactive updates.
        
        Subscribes to data changes and validation changes with field-specific optimization.
        """
        if not self._transaction_display_data:
            return
        
        try:
            # Subscribe to data changes
            self._data_observer_id = self._transaction_display_data.add_observer(
                self._on_data_changed,
                ObserverType.DATA_CHANGED
            )
            
            # Subscribe to validation changes for rule switch visibility
            # self._validation_observer_id = self._transaction_display_data.add_observer(
            #     self._on_validation_changed,
            #     ObserverType.VALIDATION_CHANGED
            # )
        except Exception as e:
            logger.error(f"Error setting up observers: {e}")
    
    def _cleanup_observers(self) -> None:
        """Clean up observer subscriptions."""
        if not self._transaction_display_data:
            return
        
        try:
            if self._data_observer_id:
                self._transaction_display_data.remove_observer(
                    self._data_observer_id, 
                    ObserverType.DATA_CHANGED
                )
                self._data_observer_id = None
                
            if self._validation_observer_id:
                self._transaction_display_data.remove_observer(
                    self._validation_observer_id,
                    ObserverType.VALIDATION_CHANGED
                )
                self._validation_observer_id = None
        except Exception as e:
            logger.error(f"Error cleaning up observers: {e}")
    
    def _on_data_changed(self, data: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle data changes from TransactionDisplayData.
        
        Updates UI only if relevant fields changed for optimization.
        
        Args:
            data: The TransactionDisplayData that changed
            changed_fields: Set of field names that changed
        """
        if not self._should_update_for_fields(changed_fields):
            return
        
        try:
            # Field mappings: field_name -> (data_getter, current_value_attr, ui_widget_attr)
            field_mappings = {
                'source_account': (
                    lambda d: getattr(d, 'source_account', ""),
                    '_current_source_account',
                    '_source_account_field'
                ),
                'destination_account': (
                    lambda d: getattr(d, 'destination_account', ""),
                    '_current_destination_account', 
                    '_destination_account_field'
                ),
                'payee': (
                    lambda d: d.transaction_data.payee or "",
                    '_current_payee',
                    '_payee_field'
                ),
                'narration': (
                    lambda d: d.transaction_data.narration or "",
                    '_current_narration',
                    '_narration_field'
                )
            }
            
            for field_name, (data_getter, current_attr, widget_attr) in field_mappings.items():
                if changed_fields and field_name not in changed_fields:
                    continue
                    
                new_value = data_getter(data)
                current_value = getattr(self, current_attr)
                
                if new_value != current_value:
                    setattr(self, current_attr, new_value)
                    widget = getattr(self, widget_attr)
                    if widget:
                        widget.value = new_value
                        
        except Exception as e:
            logger.error(f"Error handling data change: {e}")
    
    def _should_update_for_fields(self, changed_fields: Optional[Set[str]]) -> bool:
        """Check if this component should update based on changed fields.
        
        Implements field-specific update optimization to avoid unnecessary UI updates.
        
        Args:
            changed_fields: Set of field names that changed
            
        Returns:
            bool: True if this component should update
        """
        if not changed_fields:
            return True  # Update for any change if no specific fields provided
        
        # Update if any of our managed fields changed
        relevant_fields = {'source_account', 'destination_account', 'payee', 'narration'}
        return bool(changed_fields.intersection(relevant_fields))
    
    def _on_validation_changed(self, data: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle validation changes from TransactionDisplayData.
        
        Updates rule switch visibility based on validation results.
        
        Args:
            data: The TransactionDisplayData that had validation changes
            changed_fields: Set of field names that changed (optional)
        """
        try:
            self._update_rule_switch_visibility()
        except Exception as e:
            logger.error(f"Error handling validation change: {e}")
    
    def _update_rule_switch_visibility(self) -> None:
        """Update the visibility of the rule switch based on transaction state.
        
        Rules:
        - Hide switch if transaction has applied_rule_ids (already categorized by rules)
        - Show switch if transaction has no applied_rule_ids AND validation passes
        """
        if not self._transaction_display_data or not self._main_container or not self._rule_switch_container:
            return
        
        try:
            # Check if transaction is already categorized by any rules
            has_applied_rules = bool(self._transaction_display_data.applied_rule_ids)

            should_show_switch = not has_applied_rules

            # Check current visibility state
            is_currently_visible = self._is_rule_switch_visible()
            
            # Update visibility if needed
            if should_show_switch and not is_currently_visible:
                self._show_rule_switch()
            elif not should_show_switch and is_currently_visible:
                self._hide_rule_switch()
                
        except Exception as e:
            logger.error(f"Error updating rule switch visibility: {e}")
    
    def _is_rule_switch_visible(self) -> bool:
        """Check if the rule switch is currently visible in the container.
        
        Returns:
            bool: True if the switch is visible, False otherwise
        """
        if not self._main_container or not self._rule_switch_container:
            return False
        
        # Check if the switch container is in the main container's children
        return self._rule_switch_container in self._main_container.children
    
    def _show_rule_switch(self) -> None:
        """Add the rule switch container to the main container."""
        if self._main_container and self._rule_switch_container:
            self._main_container.add(self._rule_switch_container)
    
    def _hide_rule_switch(self) -> None:
        """Remove the rule switch container from the main container."""
        if self._main_container and self._rule_switch_container:
            try:
                self._main_container.remove(self._rule_switch_container)
            except ValueError:
                # Container might not be in the parent, which is fine
                pass
    
    @property
    def create_rule_enabled(self) -> bool:
        """Get the current state of the create rule switch.
        
        Returns:
            bool: True if the switch is enabled and checked, False otherwise
        """
        return (self._create_rule_switch is not None and 
                self._is_rule_switch_visible() and 
                self._create_rule_switch.value)
    
    def get_create_rule_value(self) -> bool:
        """Get the current value of the create rule switch.
        
        Returns:
            bool: True if switch exists and is checked, False otherwise
        """
        if self._create_rule_switch is not None:
            return self._create_rule_switch.value
        return False

    def add_switch_observer(self, callback: Callable[[bool], None]) -> None:
        """Add an observer for create rule switch changes.
        
        Args:
            callback: Function to call when switch state changes. 
                     Receives bool indicating switch state.
        """
        self._switch_observers.append(callback)

    def remove_switch_observer(self, callback: Callable[[bool], None]) -> None:
        """Remove an observer for create rule switch changes.
        
        Args:
            callback: Function to remove from observers
        """
        if callback in self._switch_observers:
            self._switch_observers.remove(callback)

    def _on_create_rule_switch_changed(self, widget: toga.Switch) -> None:
        """Handle create rule switch state changes.
        
        Notifies all registered observers about the switch state change.
        
        Args:
            widget: The switch widget that changed
        """
        try:
            # Notify all observers about the switch state change
            for observer in self._switch_observers:
                observer(widget.value)
        except Exception as e:
            logger.error(f"Error notifying switch observers: {e}")

    def _fix_macos_tab_chain(self):
        """Fix tab navigation chain on macOS for TextInputs.
        
        This addresses the macOS-specific issue where dynamically created or modified
        TextInput widgets may not properly participate in tab navigation.
        See: https://github.com/beeware/toga/issues/2766
        """
        try:
            if sys.platform != "darwin":
                return
                
            from toga_cocoa.libs import appkit
            from rubicon.objc import ObjCClass
            
            # Get all TextInput widgets in logical order
            text_inputs = []
            
            # Add account fields if they exist
            if self._source_account_field and hasattr(self._source_account_field, 'widget'):
                text_inputs.append(self._source_account_field.widget)
            if self._destination_account_field and hasattr(self._destination_account_field, 'widget'):
                text_inputs.append(self._destination_account_field.widget)
                
            # Add text fields
            if self._payee_field:
                text_inputs.append(self._payee_field)
            if self._narration_field:
                text_inputs.append(self._narration_field)

            # Get native NSTextField objects
            native_fields = []
            for text_input in text_inputs:
                try:
                    if hasattr(text_input, '_impl') and hasattr(text_input._impl, 'native'):
                        native_field = text_input._impl.native
                        if native_field:
                            native_fields.append(native_field)
                except Exception as e:
                    logger.debug(f"Could not get native field for text input: {e}")
            
            # Rebuild the responder chain
            if len(native_fields) > 1:
                for i in range(len(native_fields)):
                    current_field = native_fields[i]
                    next_field = native_fields[(i + 1) % len(native_fields)]
                    current_field.setNextKeyView_(next_field)
            
            logger.debug(f"Updated macOS tab chain for {len(native_fields)} text fields in TransactionCategorizer")
            
        except Exception as e:
            logger.debug(f"Error fixing macOS tab chain in TransactionCategorizer: {e}")
