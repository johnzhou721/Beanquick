"""
Advanced Rule Management Container for creating and managing transaction rules.

This module provides the RuleManagementContainer class that implements a comprehensive
UI for creating complex transaction rules using the enhanced rule engine capabilities.
The container is designed to be modular, reusable, and embeddable in different contexts.
"""

import sys
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict, Set

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, START, CENTER, BOLD  # type: ignore
from toga.constants import DODGERBLUE

from beanquick.importers.rules import TransactionRule
from beanquick.importers.rules.engine import RuleEngine
from beanquick.importers.rules.rule_components import (
    LogicalOperator, Field, Operator, ActionType
)
from beanquick.ui.importer.transaction_review.models import TransactionDisplayData, ObserverType
from .rule_management_data import (
    ConditionData, ActionData, 
    create_conditions_block_from_ui_data, create_actions_from_ui_data,
    validate_rule_ui_data, get_field_display_name, get_operator_display_name,
    get_operators_for_field, get_action_display_name, get_required_parameter_for_action,
    get_parameter_placeholder
)

logger = logging.getLogger(__name__)

if sys.platform == 'darwin':
    try:
        from toga_cocoa.libs import NSColor
    except ImportError:
        NSColor = None

WIDGET_SPACING = 5

# For button text
EDIT_BUTTON_TEXT = "Edit"
DELETE_BUTTON_TEXT = "Delete"
SAVE_BUTTON_TEXT = "Save"
UPDATE_BUTTON_TEXT = "Update"
CANCEL_BUTTON_TEXT = "Cancel"

@dataclass
class ConditionRowWidgets:
    """Widget references for a single condition row to enable efficient updates.
    
    This dataclass stores references to all widgets in a condition row, allowing
    for targeted updates without widget recreation. This is the core of the
    performance optimization strategy.
    """
    field_selection: toga.Selection
    operator_selection: toga.Selection
    value_input: toga.TextInput
    row_container: toga.Box
    add_button: Optional[toga.Button] = None
    remove_button: Optional[toga.Button] = None
    button_box: Optional[toga.Box] = None


@dataclass
class ActionRowWidgets:
    """Widget references for a single action row to enable efficient updates.
    
    Similar to ConditionRowWidgets, this stores action row widget references
    for performance-optimized updates.
    """
    action_type_selection: toga.Selection
    parameter_input: toga.TextInput
    row_container: toga.Box
    add_button: Optional[toga.Button] = None
    remove_button: Optional[toga.Button] = None
    button_box: Optional[toga.Box] = None


class ConditionRowHandler:
    """Dedicated handler for a single condition row.
    
    This class manages all event handlers for a condition row, properly
    binding the row index to avoid lambda closure issues.
    """
    
    def __init__(self, container: 'RuleManagementContainer', row_index: int):
        """Initialize the condition row handler.
        
        Args:
            container: The parent RuleManagementContainer instance
            row_index: The index of this condition row
        """
        self.container = container
        self.row_index = row_index
    
    def on_field_change(self, widget, **kwargs) -> None:
        """Handle field selection change."""
        self.container._on_condition_field_change(self.row_index, widget.value)
    
    def on_operator_change(self, widget, **kwargs) -> None:
        """Handle operator selection change."""
        self.container._on_condition_operator_change(self.row_index, widget.value)
    
    def on_value_change(self, widget, **kwargs) -> None:
        """Handle value input change."""
        self.container._on_condition_value_change(self.row_index, widget.value)
    
    def on_add_clicked(self, widget, **kwargs) -> None:
        """Handle add button click."""
        self.container._add_condition_after(self.row_index)
    
    def on_remove_clicked(self, widget, **kwargs) -> None:
        """Handle remove button click."""
        self.container._remove_condition(self.row_index)


class ActionRowHandler:
    """Dedicated handler for a single action row.
    
    This class manages all event handlers for an action row, properly
    binding the row index to avoid lambda closure issues.
    """
    
    def __init__(self, container: 'RuleManagementContainer', row_index: int):
        """Initialize the action row handler.
        
        Args:
            container: The parent RuleManagementContainer instance
            row_index: The index of this action row
        """
        self.container = container
        self.row_index = row_index
    
    def on_type_change(self, widget, **kwargs) -> None:
        """Handle action type selection change."""
        self.container._on_action_type_change(self.row_index, widget.value)
    
    def on_parameter_change(self, widget, **kwargs) -> None:
        """Handle parameter input change."""
        self.container._on_action_parameter_change(self.row_index, widget.value)
    
    def on_add_clicked(self, widget, **kwargs) -> None:
        """Handle add button click."""
        self.container._add_action_after(self.row_index)
    
    def on_remove_clicked(self, widget, **kwargs) -> None:
        """Handle remove button click."""
        self.container._remove_action(self.row_index)


class RuleManagementContainer:
    """Main container for advanced rule management UI.
    
    This class provides a comprehensive interface for creating and managing
    transaction rules with support for complex conditions, multiple actions,
    and full integration with the enhanced rule engine.
    
    The container supports three modes:
    1. View Mode: When transaction has applied_rule_ids, shows rule in read-only mode
    2. Create Mode: Normal rule creation with all controls enabled
    3. Edit Mode: Editing existing rule with all controls enabled and pre-populated data
    
    The container is designed to be embedded in existing views or displayed
    as a standalone interface, with clear callback mechanisms for integration.
    """
    
    def __init__(
        self,
        rule_engine: RuleEngine,
        on_rule_created: Callable[[TransactionRule], Optional[List[str]]],
        on_cancel: Callable[[], None],
        on_rule_deleted: Optional[Callable[[str], None]] = None,
        on_rule_edited: Optional[Callable[[TransactionRule], Optional[List[str]]]] = None
    ):
        """Initialize the rule management container.
        
        Args:
            rule_engine: Engine for rule creation, validation, and management
            on_rule_created: Callback when rule is created/saved.
                           Called with (rule) and should return optional list of updated transaction IDs.
                           If list is returned, rule will be applied to those transactions.
            on_cancel: Callback when user cancels rule creation
            on_rule_deleted: Optional callback when rule is deleted.
                           Called with (rule_id) to notify that the rule was deleted.
            on_rule_edited: Optional callback when rule is edited/updated.
                          Called with (rule) and should return optional list of updated transaction IDs.
                          If list is returned, rule will be applied to those transactions.
        """
        # Configuration
        self._rule_engine = rule_engine
        self._on_rule_created = on_rule_created
        self._on_cancel = on_cancel
        self._on_rule_deleted = on_rule_deleted
        self._on_rule_edited = on_rule_edited
        
        # Mode management - determines if container is in view, create, or edit mode
        self._is_view_mode: bool = False
        self._viewed_rule: Optional[TransactionRule] = None
        self._is_editing_mode: bool = False
        self._editing_rule_id: Optional[str] = None
        self._original_rule: Optional[TransactionRule] = None
        
        # Internal state management
        self._rule_name: str = ""
        self._logical_operator: LogicalOperator = LogicalOperator.ALL
        self._conditions: List[ConditionData] = []
        self._actions: List[ActionData] = []
        self._validation_errors: Dict[str, List[str]] = {}
        self._is_saving: bool = False
        
        # Widget references for efficient updates
        self._container: Optional[toga.Box] = None
        self._name_input: Optional[toga.TextInput] = None
        self._logical_operator_selection: Optional[toga.Selection] = None
        self._conditions_container: Optional[toga.Box] = None
        self._actions_container: Optional[toga.Box] = None
        self._save_button: Optional[toga.Button] = None
        self._discard_button: Optional[toga.Button] = None
        
        # Performance optimization: Widget references for dynamic rows
        self._condition_row_widgets: List[Optional[ConditionRowWidgets]] = []
        self._action_row_widgets: List[Optional[ActionRowWidgets]] = []
        
        # Transaction data integration for reactive updates
        self._transaction_data: Optional[TransactionDisplayData] = None
        self._data_observer_id: Optional[str] = None
        
        # Handler registries for row-based event handling
        self._condition_handlers: Dict[int, ConditionRowHandler] = {}
        self._action_handlers: Dict[int, ActionRowHandler] = {}
        
        # Initialize with default data
        self._initialize_default_data()
        
        # Auto-population configuration
        self._auto_populate_on_field_change = True  # Enable auto-population when field/action changes
        self._preserve_user_input = False  # Don't override existing user input
        
        logger.debug(f"RuleManagementContainer initialized.")
    
    def _initialize_default_data(self) -> None:
        """Initialize default condition and action data.
        
        Sets up the container with one empty condition and one empty action
        to provide a starting point for rule creation.
        """
        # Initialize with one empty condition
        if not self._conditions:
            self._conditions = [self._create_default_condition()]

        # Initialize with one empty action
        if not self._actions:
            self._actions = [self._create_default_action()]
        
        # Normalize all data after initialization
        for condition in self._conditions:
            self._normalize_condition_data(condition)
        for action in self._actions:
            self._normalize_action_data(action)

    def _create_default_condition(self) -> ConditionData:
        """Create a condition with sensible defaults.
        
        If transaction data is available and we're creating a new rule,
        auto-populate the condition with relevant transaction data.
        """
        condition = ConditionData()
        
        # Auto-populate from transaction data if available for new rules
        if self._transaction_data and not self._is_view_mode:
            condition = self._auto_populate_condition_from_transaction()
            if condition.field:  # Successfully auto-populated
                return condition
        
        # Fallback to defaults if no transaction data or auto-population failed
        if Field:
            condition.field = list(Field)[0]  # First available field
            # Set default operator for that field
            available_operators = get_operators_for_field(condition.field)
            if available_operators:
                condition.operator = available_operators[0]
        return condition
    
    def _create_default_action(self) -> ActionData:
        """Create an action with sensible defaults.
        
        If transaction data is available and we're creating a new rule,
        auto-populate the action with relevant transaction data.
        """
        action = ActionData()
        
        # Auto-populate from transaction data if available for new rules
        if self._transaction_data and not self._is_view_mode:
            action = self._auto_populate_action_from_transaction()
            if action.action_type:  # Successfully auto-populated
                return action
        
        # Fallback to defaults if no transaction data or auto-population failed
        if ActionType:
            action.action_type = list(ActionType)[0]  # First available action
        return action
    
    def _normalize_condition_data(self, condition_data: ConditionData) -> None:
        """Ensure condition data has valid defaults and consistent state."""
        # For original_row fields, don't set a default field enum
        # Instead, ensure we have either a field OR an original_row_key
        if not condition_data.field and not condition_data.original_row_key and Field:
            # Only set default field if we have no original_row_key either
            condition_data.field = list(Field)[0]
        
        # Determine effective field for operator selection
        if condition_data.field is not None:
            # Use standard field operators
            available_operators = get_operators_for_field(condition_data.field)
        elif condition_data.original_row_key is not None:
            # Use original_row operators (string-based)
            from .rule_management_data import get_operators_for_original_row
            available_operators = get_operators_for_original_row()
        else:
            available_operators = []
        
        # Ensure operator is valid for the effective field
        if available_operators:
            if not condition_data.operator or condition_data.operator not in available_operators:
                condition_data.operator = available_operators[0] if available_operators else None
        
        # Clear value if operator changed (could add more sophisticated value migration)
        # This is handled in the change handlers
    
    def _normalize_action_data(self, action_data: ActionData) -> None:
        """Ensure action data has valid defaults and consistent state."""
        # Ensure action type has a value
        if not action_data.action_type and ActionType:
            action_data.action_type = list(ActionType)[0]

    @property
    def is_view_mode(self) -> bool:
        """Check if the container is in view mode (read-only).
        
        Returns:
            bool: True if in view mode, False otherwise
        """
        return self._is_view_mode
    
    @property
    def is_editing_mode(self) -> bool:
        """Check if container is in edit mode (editing existing rule).
        
        Returns:
            bool: True if editing existing rule, False otherwise
        """
        return self._is_editing_mode
    
    @property
    def is_create_mode(self) -> bool:
        """Check if container is in create mode (creating new rule).
        
        Returns:
            bool: True if creating new rule, False otherwise
        """
        return not self._is_view_mode and not self._is_editing_mode
    
    @property
    def viewed_rule(self) -> Optional[TransactionRule]:
        """Get the rule being viewed (only available in view mode).
        
        Returns:
            Optional[TransactionRule]: The rule being viewed, or None if not in view mode
        """
        return self._viewed_rule if self._is_view_mode else None
    
    @property
    def editing_rule(self) -> Optional[TransactionRule]:
        """Get the rule being edited (only available in edit mode).
        
        Returns:
            Optional[TransactionRule]: The rule being edited, or None if not in edit mode
        """
        return self._original_rule if self._is_editing_mode else None

    @property
    def importer_name(self) -> str:
        """Get the importer name from the rule engine."""
        return self._rule_engine.importer_name

    @property
    def importer_icon(self) -> str:
        """Get the importer icon from the rule engine."""
        return self._rule_engine.importer_icon

    def _get_available_field_options(self) -> List[str]:
        """Get all available field options including standard fields and original_row keys.
        
        Returns:
            List[str]: List of field display names for the dropdown
        """
        # Start with standard fields
        field_options = [get_field_display_name(field) for field in Field]
        
        # Add original_row keys if transaction data is available
        if self._transaction_data and self._transaction_data.transaction_data.metadata:
            original_row = self._transaction_data.transaction_data.metadata.get('original_row', {})
            if isinstance(original_row, dict):
                # Add original row keys as field options with a prefix
                for key in sorted(original_row.keys()):
                    if key and key.strip():  # Only add non-empty keys
                        field_options.append(f"Original: {key}")
        
        return field_options
    
    def _parse_field_selection(self, field_display_name: str) -> tuple[Optional[Field], Optional[str]]:
        """Parse a field selection to determine if it's a standard field or original_row key.
        
        Args:
            field_display_name: The display name selected by the user
            
        Returns:
            tuple: (Field enum if standard field, original_row_key if original row field)
        """
        # Check if it's an original row field
        if field_display_name.startswith("Original: "):
            original_key = field_display_name[10:]  # Remove "Original: " prefix
            return None, original_key
        
        # It's a standard field - find the Field enum
        for field in Field:
            if get_field_display_name(field) == field_display_name:
                return field, None
        
        return None, None

    def update_data(self, transaction_data: Optional[TransactionDisplayData]) -> None:
        """Update the rule container with transaction data for auto-population and reactive updates.
        
        This method determines the container mode based on the transaction data:
        - If transaction_data has applied_rule_ids, enters view mode to show existing rule
        - Otherwise, enters edit mode for rule creation/editing
        
        The UI will be automatically rebuilt if the mode changes.
        
        Args:
            transaction_data: TransactionDisplayData to use for auto-population (None to clear)
        """
        # Clean up previous observers
        self._cleanup_transaction_observers()
        
        # Store previous mode for comparison
        old_mode = self._is_view_mode
        
        # Store new transaction data
        self._transaction_data = transaction_data
        
        # Determine mode based on transaction data
        self._determine_container_mode()
        
        # If mode changed, toggle UI mode or rebuild if data also changed
        if old_mode != self._is_view_mode and self._container:
            logger.debug(f"Mode changed from {'view' if old_mode else 'edit'} to {'view' if self._is_view_mode else 'edit'}")
            # Use toggle for better performance if only mode changed
            # Full rebuild is still needed if transaction data fundamentally changed
            if self._container.children:  # Container has been built before
                self._toggle_mode_without_rebuild()
            else:
                self._rebuild_container_ui()
        
        if transaction_data and not self._is_view_mode:
            # Set up observers for reactive updates
            self._setup_transaction_observers()
            
            # Auto-populate if creating new rule (not viewing existing)
            if not self._is_view_mode:
                self._auto_populate_from_transaction()
    
    def _determine_container_mode(self) -> None:
        """Determine whether container should be in view mode or edit mode.
        
        View Mode: When transaction has applied_rule_ids and rule exists in repository
        Edit Mode: When no applied_rule_ids or rule doesn't exist
        """
        # Store previous mode for comparison
        previous_mode = self._is_view_mode
        
        self._is_view_mode = False
        self._viewed_rule = None
        
        if not self._transaction_data or not self._transaction_data.applied_rule_ids:
            logger.debug("Edit mode: No transaction data or applied_rule_ids")
            # Reset state when transitioning from view to edit mode
            if previous_mode:
                self._reset_state_for_edit_mode()
            return
        
        # Try to fetch the first (most recent) applied rule from repository via rule engine
        last_rule_id = self._transaction_data.applied_rule_ids[-1] if self._transaction_data.applied_rule_ids else None
        if not last_rule_id:
            logger.debug("Edit mode: No applied rule IDs found")
            # Reset state when transitioning from view to edit mode
            if previous_mode:
                self._reset_state_for_edit_mode()
            return
            
        try:
            rule = self._rule_engine.get_rule_by_id(last_rule_id)
            if rule:
                self._is_view_mode = True
                self._viewed_rule = rule
                logger.debug(f"View mode: Found rule {rule.rule_id} (latest of {len(self._transaction_data.applied_rule_ids)} applied rules)")
                self._populate_from_rule_for_viewing(rule)
            else:
                logger.debug(f"Edit mode: Rule {last_rule_id} not found")
                # Reset state when transitioning from view to edit mode
                if previous_mode:
                    self._reset_state_for_edit_mode()
        except Exception as e:
            logger.warning(f"Edit mode: Error fetching rule {last_rule_id}: {e}")
            # Reset state when transitioning from view to edit mode
            if previous_mode:
                self._reset_state_for_edit_mode()
    
    def _populate_from_rule_for_viewing(self, rule: TransactionRule) -> None:
        """Populate UI data from a rule for viewing (read-only mode).
        
        This is similar to _populate_from_existing_rule but specifically for view mode.
        
        Args:
            rule: The TransactionRule to display
        """
        try:
            self._rule_name = rule.name
            
            if rule.conditions_block:
                self._logical_operator = rule.conditions_block.operator
                
                # Convert rule conditions to UI condition data
                self._conditions = []
                for condition in rule.conditions_block.conditions:
                    condition_data = ConditionData.from_condition(condition)
                    self._conditions.append(condition_data)
            
            # Convert rule actions to UI action data
            self._actions = []
            for action in rule.actions:
                action_data = ActionData.from_action(action)
                self._actions.append(action_data)
                
        except Exception as e:
            logger.error(f"Error populating view data from rule {rule.rule_id}: {e}")
            # Fallback to edit mode if we can't populate view data
            self._is_view_mode = False
            self._viewed_rule = None
    
    def _reset_state_for_edit_mode(self) -> None:
        """Reset internal state when transitioning from view mode to edit mode.
        
        This method clears all state that was populated from a viewed rule,
        ensuring that edit mode starts with a clean slate. It then reinitializes
        with default data and optionally auto-populates from the current transaction.
        """
        logger.debug("Resetting state for edit mode transition")
        
        # Clear all internal state that was populated during view mode
        self._rule_name = ""
        self._logical_operator = LogicalOperator.ALL
        self._conditions.clear()
        self._actions.clear()
        self._validation_errors.clear()
        
        # Clear widget references to force recreation
        self._condition_row_widgets.clear()
        self._action_row_widgets.clear()
        self._condition_handlers.clear()
        self._action_handlers.clear()
        
        # Reinitialize with default empty data
        self._initialize_default_data()
        
        # Auto-populate from current transaction if available and in edit mode
        if self._transaction_data and not self._is_view_mode:
            self._auto_populate_from_transaction()
    
    def enter_edit_mode(self, rule: TransactionRule) -> None:
        """Enter edit mode for an existing rule.
        
        This transitions the container from view mode to edit mode, making all fields
        editable and pre-populating them with the rule's current data.
        
        Args:
            rule: The rule to edit
        """
        logger.info(f"Entering edit mode for rule: {rule.name} ({rule.rule_id})")
        
        # Store the original rule for comparison and cancellation
        self._original_rule = rule
        self._editing_rule_id = rule.rule_id
        
        # Exit view mode
        self._is_view_mode = False
        self._viewed_rule = None
        
        # Enter edit mode
        self._is_editing_mode = True
        
        # Clear existing validation errors
        self._validation_errors.clear()
        
        # Populate fields from the rule being edited
        self._populate_from_rule_for_editing(rule)
        
        # Toggle to edit mode without rebuilding (prevents flicker)
        if self._container:
            self._toggle_mode_without_rebuild()
        
        logger.debug(f"Edit mode entered successfully for rule {rule.rule_id}")
    
    def exit_edit_mode(self, save_changes: bool = False) -> None:
        """Exit edit mode and return to view mode.
        
        Args:
            save_changes: If True, keep current form data. If False, revert to original rule.
        """
        if not self._is_editing_mode:
            logger.warning("Cannot exit edit mode - not currently in edit mode")
            return
        
        logger.debug(f"Exiting edit mode for rule {self._editing_rule_id}, save_changes={save_changes}")
        
        # If not saving changes, revert to original rule data
        if not save_changes and self._original_rule:
            self._populate_from_rule_for_viewing(self._original_rule)
        
        # Exit edit mode
        self._is_editing_mode = False
        self._editing_rule_id = None
        
        # Enter view mode with the rule
        self._is_view_mode = True
        self._viewed_rule = self._original_rule
        
        # Clear edit-specific state
        self._original_rule = None
        
        # Toggle to edit mode without rebuilding (prevents flicker)
        if self._container:
            self._toggle_mode_without_rebuild()
        
        logger.debug("Edit mode exited successfully")
    
    def _populate_from_rule_for_editing(self, rule: TransactionRule) -> None:
        """Populate UI data from a rule for editing mode.
        
        This method is similar to _populate_from_rule_for_viewing but prepares
        the data for editing rather than just viewing.
        
        Args:
            rule: The TransactionRule to edit
        """
        try:
            logger.debug(f"Populating edit data from rule {rule.rule_id}")
            
            # Clear existing data
            self._rule_name = ""
            self._logical_operator = LogicalOperator.ALL
            self._conditions.clear()
            self._actions.clear()
            
            # Populate basic rule data
            self._rule_name = rule.name
            
            if rule.conditions_block:
                self._logical_operator = rule.conditions_block.operator
                
                # Convert rule conditions to UI condition data
                for condition in rule.conditions_block.conditions:
                    condition_data = ConditionData.from_condition(condition)
                    self._conditions.append(condition_data)
            
            # Convert rule actions to UI action data
            for action in rule.actions:
                action_data = ActionData.from_action(action)
                self._actions.append(action_data)
            
            # Ensure we have at least one condition and action
            if not self._conditions:
                self._conditions.append(self._create_default_condition())
            
            if not self._actions:
                self._actions.append(self._create_default_action())
            
            # Normalize all data
            for condition in self._conditions:
                self._normalize_condition_data(condition)
            for action in self._actions:
                self._normalize_action_data(action)
            
            logger.debug(f"Successfully populated edit data: {len(self._conditions)} conditions, {len(self._actions)} actions")
                
        except Exception as e:
            logger.error(f"Error populating edit data from rule {rule.rule_id}: {e}")
            # Fallback to default data if we can't populate from rule
            self._initialize_default_data()
    
    def _auto_populate_from_transaction(self) -> None:
        """Auto-populate condition and action values from current transaction data."""
        if not self._transaction_data:
            return
        
        # Auto-populate conditions
        if self._conditions:
            first_condition = self._conditions[0]
            
            # Get auto-populated condition data from transaction
            field, operator, value = self._get_auto_populated_condition_data()
            
            if field:  # Only update if we have valid auto-population data
                first_condition.field = field
                first_condition.operator = operator
                first_condition.value = value
                
                # Normalize and rebuild conditions UI
                self._normalize_condition_data(first_condition)
                if self._conditions_container:
                    self._rebuild_conditions_ui()
                    
                logger.debug(f"Auto-populated first condition from transaction data: {field}={value}")
        
        # Auto-populate actions
        if self._actions:
            first_action = self._actions[0]
            
            # Get auto-populated action data from transaction
            action_type, parameter_name, parameter_value = self._get_auto_populated_action_data()
            
            logger.debug(f"Auto-populating action: type={action_type}, param={parameter_name}, value={parameter_value}")
            if action_type:  # Only update if we have valid auto-population data
                first_action.action_type = action_type
                if parameter_name and parameter_value:
                    first_action.set_parameter_value(parameter_name, parameter_value)
                
                logger.debug(f"Auto-populated first action: {first_action}")
                # Normalize and rebuild actions UI
                self._normalize_action_data(first_action)
                if self._actions_container:
                    self._rebuild_actions_ui()
                    
                logger.debug(f"Auto-populated first action from transaction data: {action_type}={parameter_value}")
    
    def _auto_populate_condition_from_transaction(self) -> ConditionData:
        """Create a condition auto-populated from transaction data.
        
        Returns:
            ConditionData: Condition with populated field, operator, and value
        """
        condition = ConditionData()
        
        if not self._transaction_data:
            return condition
        
        # Get auto-populated data from transaction
        field, operator, value = self._get_auto_populated_condition_data()
        
        if field:  # Only populate if we have valid data
            condition.field = field
            condition.operator = operator
            condition.value = value
        
        return condition
    
    def _get_auto_populated_condition_data(self) -> tuple[Optional[Field], Optional[Operator], str]:
        """Extract auto-population data from current transaction data.
        
        Returns:
            tuple: (field, operator, value) for auto-population, or (None, None, "") if no data
        """
        if not self._transaction_data:
            return None, None, ""
        
        # Priority order for auto-population
        payee = self._transaction_data.transaction_data.payee
        narration = self._transaction_data.transaction_data.narration
        amount = self._transaction_data.transaction_data.amount
        
        if payee and payee.strip():
            return Field.PAYEE, Operator.EQUALS, payee.strip()
        elif narration and narration.strip():
            return Field.NARRATION, Operator.CONTAINS, narration.strip()
        elif amount:
            return Field.AMOUNT, Operator.EQUALS, str(amount)
        
        return None, None, ""
    
    def _auto_populate_action_from_transaction(self) -> ActionData:
        """Create an action auto-populated from transaction data.
        
        Returns:
            ActionData: Action with populated type and parameters
        """
        action = ActionData()
        
        if not self._transaction_data:
            return action
        
        # Get auto-populated data from transaction
        action_type, parameter_name, parameter_value = self._get_auto_populated_action_data()
        
        if action_type:  # Only populate if we have valid data
            action.action_type = action_type
            if parameter_name and parameter_value:
                action.set_parameter_value(parameter_name, parameter_value)
        
        return action
    
    def _get_auto_populated_action_data(self) -> tuple[Optional[ActionType], Optional[str], str]:
        """Extract auto-population data for actions from current transaction data.
        
        Returns:
            tuple: (action_type, parameter_name, parameter_value) for auto-population, 
                   or (None, None, "") if no data
        """
        if not self._transaction_data:
            return None, None, ""
        
        # Priority order for action auto-population
        # Check if transaction has payee data (check transaction_data.payee if available)
        if hasattr(self._transaction_data, 'transaction_data') and self._transaction_data.transaction_data:
            payee = getattr(self._transaction_data.transaction_data, 'payee', None)
            if payee and payee.strip():
                return ActionType.SET_PAYEE, 'payee', payee.strip()
        
        destination_account = getattr(self._transaction_data, 'destination_account', None)
        
        if destination_account and destination_account.strip():
            return ActionType.SET_DESTINATION_ACCOUNT, 'account', destination_account.strip()
        
        return None, None, ""
    
    def _extract_value_for_field(self, field: Optional[Field], original_row_key: Optional[str]) -> str:
        """Extract the appropriate value from transaction data for a given field.
        
        This method supports both standard transaction fields (Field enum) and
        original_row metadata fields from CSV imports, providing comprehensive
        auto-population capabilities.
        
        Standard field examples:
        - Field.PAYEE → transaction_data.payee
        - Field.AMOUNT → formatted amount string (e.g., "18.98" not "18.980000")
        - Field.DATE → ISO format date string (e.g., "2025-07-15")
        
        Original row field examples (from CSV metadata):
        - "交易分类" → "餐饮美食"
        - "交易对方" → "淘宝闪购"
        - "商品说明" → "袁记云饺(八卦岭店)外卖订单"
        
        Args:
            field: The Field enum if it's a standard field
            original_row_key: The original_row key if it's an original row field
            
        Returns:
            str: The extracted value, or empty string if not available
        """
        if not self._transaction_data:
            return ""
        
        # Handle standard fields
        if field is not None:
            transaction_data = self._transaction_data.transaction_data
            
            if field == Field.PAYEE:
                value = transaction_data.payee or ""
                return value.strip() if value else ""
            elif field == Field.NARRATION:
                value = transaction_data.narration or ""
                return value.strip() if value else ""
            elif field == Field.AMOUNT:
                if transaction_data.amount is not None:
                    # Format amount nicely (remove trailing zeros if decimal)
                    amount_str = str(transaction_data.amount)
                    if '.' in amount_str:
                        amount_str = amount_str.rstrip('0').rstrip('.')
                    return amount_str
                return ""
            elif field == Field.CURRENCY:
                value = transaction_data.currency or ""
                return value.strip() if value else ""
            elif field == Field.DATE:
                return transaction_data.date.isoformat() if transaction_data.date else ""
        
        # Handle original_row fields
        elif original_row_key is not None:
            if (self._transaction_data.transaction_data.metadata and 
                'original_row' in self._transaction_data.transaction_data.metadata):
                original_row = self._transaction_data.transaction_data.metadata['original_row']
                if isinstance(original_row, dict) and original_row_key in original_row:
                    value = original_row[original_row_key]
                    if value is not None:
                        value_str = str(value).strip()
                        return value_str if value_str else ""
        
        return ""
    
    def _extract_parameter_for_action_type(self, action_type: Optional[ActionType]) -> str:
        """Extract the appropriate parameter value from transaction data for a given action type.
        
        This method provides intelligent auto-population for action parameters based on
        the selected action type and available transaction data.
        
        Action type examples:
        - ActionType.SET_DESTINATION_ACCOUNT → transaction_data.destination_account
        - ActionType.SET_NARRATION → transaction_data.narration
        - ActionType.APPEND_NARRATION → transaction_data.narration
        - ActionType.ADD_TAG → derived from transaction category or metadata
        
        Args:
            action_type: The ActionType enum for which to extract parameter value
            
        Returns:
            str: The extracted parameter value, or empty string if not available
        """
        if not self._transaction_data or not action_type:
            return ""
        
        transaction_data = self._transaction_data.transaction_data
        
        if action_type == ActionType.SET_DESTINATION_ACCOUNT:
            destination_account = transaction_data.metadata.get('destination_account', None) if transaction_data.metadata else None
            if destination_account and destination_account.strip():
                return destination_account.strip()

        elif action_type == ActionType.SET_SOURCE_ACCOUNT:
            source_account = transaction_data.metadata.get('source_account', None) if transaction_data.metadata else None
            if source_account and source_account.strip():
                return source_account.strip()
                
        elif action_type == ActionType.SET_PAYEE:
            if transaction_data and hasattr(transaction_data, 'payee'):
                payee = transaction_data.payee
                if payee and payee.strip():
                    return payee.strip()
                
        elif action_type in (ActionType.SET_NARRATION, ActionType.APPEND_NARRATION):
            narration = transaction_data.narration
            if narration and narration.strip():
                return narration.strip()
                
        elif action_type == ActionType.ADD_TAG:
            if hasattr(self._transaction_data, 'transaction_category'):
                category = getattr(self._transaction_data, 'transaction_category', None)
                if category and category.strip():
                    return category.strip()
            
            # Fallback: try original_row payment method or other metadata
            if (transaction_data.metadata and 
                'original_row' in transaction_data.metadata):
                original_row = transaction_data.metadata['original_row']
                if isinstance(original_row, dict):
                    # Look for useful tag candidates in priority order
                    for key in ['收/付款方式', '交易分类', '交易状态']:
                        if key in original_row and original_row[key]:
                            value = str(original_row[key]).strip()
                            if value and value != '':
                                return value
        
        return ""
    
    def configure_auto_population(self, 
                                 auto_populate_on_field_change: bool = True,
                                 preserve_user_input: bool = True) -> None:
        """Configure auto-population behavior for both conditions and actions.
        
        This method controls the intelligent auto-population feature that extracts
        appropriate values from transaction data when users select fields or action types.
        
        Args:
            auto_populate_on_field_change: Enable auto-population when field or action 
                                         type selection changes. Applies to:
                                         - Condition field selection → condition value
                                         - Action type selection → action parameter
            preserve_user_input: Don't override existing user input when auto-populating.
                               If True, only populates empty fields. If False, always
                               overwrites with transaction data.
        """
        self._auto_populate_on_field_change = auto_populate_on_field_change
        self._preserve_user_input = preserve_user_input
        
        logger.debug(f"Auto-population configured: field_change={auto_populate_on_field_change}, "
                    f"preserve_input={preserve_user_input}")
    
    def _setup_transaction_observers(self) -> None:
        """Set up observers for transaction data changes."""
        if not self._transaction_data:
            return
        
        try:
            self._data_observer_id = self._transaction_data.add_observer(
                self._on_transaction_data_changed,
                ObserverType.DATA_CHANGED
            )
            logger.debug("Transaction data observers set up successfully")
        except Exception as e:
            logger.error(f"Failed to set up transaction observers: {e}")

    def _cleanup_transaction_observers(self) -> None:
        """Clean up transaction data observers."""
        if not self._transaction_data:
            return
        
        try:
            if self._data_observer_id:
                self._transaction_data.remove_observer(
                    self._data_observer_id,
                    ObserverType.DATA_CHANGED
                )
                self._data_observer_id = None
                logger.debug("Transaction data observers cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up transaction observers: {e}")

    def _on_transaction_data_changed(self, data: TransactionDisplayData, changed_fields: Optional[Set[str]] = None) -> None:
        """Handle changes in transaction data.
        
        This could be used to update rule preview or validation in real-time.
        For now, we keep it simple and just log the change.
        
        Args:
            data: The TransactionDisplayData that changed
            changed_fields: Set of field names that changed
        """
        # Optional: Show how rule would apply to current transaction
        # Could highlight matching conditions or show preview results
        logger.debug(f"Transaction data changed, fields: {changed_fields}")
        
        # Future enhancement: Could update rule preview or validation here
        # For now, keep it simple and just acknowledge the change

    # Platform-specific decoration management
    
    def _apply_platform_decorations(self, widget: toga.TextInput, is_readonly: bool) -> None:
        """Apply platform-specific decorations to a TextInput widget based on its state.
        
        This method centralizes all platform-specific styling logic, making it easy
        to maintain and reuse across different parts of the UI.
        
        Args:
            widget: The TextInput widget to decorate
            is_readonly: Whether the widget is in readonly state (affects decoration style)
        """
        if not widget:
            return
            
        # Apply macOS-specific decorations for readonly state
        if sys.platform == 'darwin' and NSColor and is_readonly:
            try:
                # Apply disabled appearance for readonly text inputs on macOS
                widget._impl.native.backgroundColor = NSColor.windowBackgroundColor
                widget._impl.native.textColor = NSColor.disabledControlTextColor
            except AttributeError:
                # Fallback if _impl.native is not available
                # This can happen if the widget hasn't been fully initialized yet
                logger.debug(f"Could not apply macOS decorations to widget {widget}")
        elif sys.platform == 'darwin' and NSColor and not is_readonly:
            try:
                # Restore normal appearance for editable text inputs on macOS
                widget._impl.native.backgroundColor = NSColor.textBackgroundColor
                widget._impl.native.textColor = NSColor.textColor
            except AttributeError:
                # Fallback if _impl.native is not available
                logger.debug(f"Could not restore macOS decorations for widget {widget}")
        
        # Future: Add decorations for other platforms here
        # elif sys.platform == 'win32':
        #     # Windows-specific decorations
        # elif sys.platform == 'linux':
        #     # Linux-specific decorations
    
    def _apply_view_mode_decorations(self) -> None:
        """Apply all view mode decorations to current widgets.
        
        This method applies platform-specific decorations to all widgets
        that should have a readonly/disabled appearance in view mode.
        """
        # Apply decorations to main name input
        if self._name_input:
            self._apply_platform_decorations(self._name_input, is_readonly=True)
        
        # Apply decorations to all condition value inputs
        for widgets in self._condition_row_widgets:
            if widgets and widgets.value_input:
                self._apply_platform_decorations(widgets.value_input, is_readonly=True)
        
        # Apply decorations to all action parameter inputs
        for widgets in self._action_row_widgets:
            if widgets and widgets.parameter_input:
                self._apply_platform_decorations(widgets.parameter_input, is_readonly=True)
        
        logger.debug("Applied view mode decorations to all widgets")
    
    def _apply_edit_mode_decorations(self) -> None:
        """Apply all edit mode decorations to current widgets.
        
        This method applies platform-specific decorations to all widgets
        that should have an editable/enabled appearance in edit mode.
        """
        # Apply decorations to main name input
        if self._name_input:
            self._apply_platform_decorations(self._name_input, is_readonly=False)
        
        # Apply decorations to all condition value inputs
        for widgets in self._condition_row_widgets:
            if widgets and widgets.value_input:
                self._apply_platform_decorations(widgets.value_input, is_readonly=False)
        
        # Apply decorations to all action parameter inputs
        for widgets in self._action_row_widgets:
            if widgets and widgets.parameter_input:
                self._apply_platform_decorations(widgets.parameter_input, is_readonly=False)
        
        logger.debug("Applied edit mode decorations to all widgets")

    def _toggle_mode_without_rebuild(self) -> None:
        """Toggle between view and edit mode without rebuilding UI.
        
        This method provides a performance-optimized way to switch between
        view and edit modes by toggling widget properties instead of 
        recreating the entire UI. This eliminates flicker and improves UX.
        """
        if not self._container:
            logger.warning("Cannot toggle mode: container not created yet")
            return
        
        logger.debug(f"Toggling mode without rebuild: view_mode={self._is_view_mode}")
        
        # Toggle main input widgets
        self._toggle_main_widgets_mode()
        
        # Toggle condition rows
        self._toggle_condition_rows_mode()
        
        # Toggle action rows  
        self._toggle_action_rows_mode()
        
        # Update header text
        self._update_header_text()
        
        # Update button section (this is the only part that needs rebuilding)
        self._update_button_section()
        
        logger.debug("Mode toggle completed without rebuild")
    
    def _toggle_main_widgets_mode(self) -> None:
        """Toggle readonly/enabled state of main form widgets."""
        # Toggle rule name input
        if self._name_input:
            self._name_input.readonly = self._is_view_mode
            # Update placeholder based on mode
            if self._is_view_mode:
                self._name_input.placeholder = ""
                # Remove event handler in view mode
                self._name_input.on_change = None
            else:
                self._name_input.placeholder = "Enter a descriptive name for this rule"
                # Restore event handler in edit mode
                self._name_input.on_change = self._on_name_change
            # Apply appropriate decorations for the new state
            self._apply_platform_decorations(self._name_input, is_readonly=self._is_view_mode)
        
        # Toggle logical operator selection
        if self._logical_operator_selection:
            self._logical_operator_selection.enabled = not self._is_view_mode
            # Update event handler based on mode
            if self._is_view_mode:
                # Remove event handler in view mode
                self._logical_operator_selection.on_change = None
            else:
                # Restore event handler in edit mode
                self._logical_operator_selection.on_change = self._on_logical_operator_change
    
    def _toggle_condition_rows_mode(self) -> None:
        """Toggle readonly/enabled state of all condition row widgets."""
        for index, widgets in enumerate(self._condition_row_widgets):
            if widgets is None:
                continue
                
            # Toggle field selection
            widgets.field_selection.enabled = not self._is_view_mode
            # Update event handler based on mode
            if self._is_view_mode:
                widgets.field_selection.on_change = None
            else:
                # Restore event handler using the stored handler
                if index in self._condition_handlers:
                    widgets.field_selection.on_change = self._condition_handlers[index].on_field_change
            
            # Toggle operator selection  
            widgets.operator_selection.enabled = not self._is_view_mode
            # Update event handler based on mode
            if self._is_view_mode:
                widgets.operator_selection.on_change = None
            else:
                # Restore event handler using the stored handler
                if index in self._condition_handlers:
                    widgets.operator_selection.on_change = self._condition_handlers[index].on_operator_change
            
            # Toggle value input
            widgets.value_input.readonly = self._is_view_mode
            # Update event handler based on mode
            if self._is_view_mode:
                widgets.value_input.on_change = None
            else:
                # Restore event handler using the stored handler
                if index in self._condition_handlers:
                    widgets.value_input.on_change = self._condition_handlers[index].on_value_change
            
            # Toggle button visibility
            if widgets.button_box:
                if self._is_view_mode:
                    # Hide buttons by removing button_box from row_container
                    if widgets.button_box in widgets.row_container.children:
                        widgets.row_container.remove(widgets.button_box)
                else:
                    # Show buttons by adding button_box to row_container
                    if widgets.button_box not in widgets.row_container.children:
                        widgets.row_container.add(widgets.button_box)
            
            # Apply appropriate decorations for the new state
            self._apply_platform_decorations(widgets.value_input, is_readonly=self._is_view_mode)
            
            # Update placeholder based on mode
            if self._is_view_mode:
                widgets.value_input.placeholder = ""
            else:
                # Get current condition data to set appropriate placeholder
                if index < len(self._conditions):
                    condition_data = self._conditions[index]
                    placeholder = self._get_condition_value_placeholder(
                        condition_data.field, condition_data.operator
                    )
                    widgets.value_input.placeholder = placeholder
    
    def _toggle_action_rows_mode(self) -> None:
        """Toggle readonly/enabled state of all action row widgets."""
        for index, widgets in enumerate(self._action_row_widgets):
            if widgets is None:
                continue
                
            # Toggle action type selection
            widgets.action_type_selection.enabled = not self._is_view_mode
            # Update event handler based on mode
            if self._is_view_mode:
                widgets.action_type_selection.on_change = None
            else:
                # Restore event handler using the stored handler
                if index in self._action_handlers:
                    widgets.action_type_selection.on_change = self._action_handlers[index].on_type_change
            
            # Toggle parameter input
            widgets.parameter_input.readonly = self._is_view_mode
            # Update event handler based on mode
            if self._is_view_mode:
                widgets.parameter_input.on_change = None
            else:
                # Restore event handler using the stored handler
                if index in self._action_handlers:
                    widgets.parameter_input.on_change = self._action_handlers[index].on_parameter_change
            
            # Apply appropriate decorations for the new state
            self._apply_platform_decorations(widgets.parameter_input, is_readonly=self._is_view_mode)
            
            # Update placeholder based on mode
            if self._is_view_mode:
                widgets.parameter_input.placeholder = ""
            else:
                # Get current action data to set appropriate placeholder
                if index < len(self._actions):
                    action_data = self._actions[index]
                    placeholder = self._get_action_parameter_placeholder(action_data.action_type)
                    widgets.parameter_input.placeholder = placeholder
            
            # Toggle button visibility
            if widgets.button_box:
                if self._is_view_mode:
                    # Hide buttons by removing button_box from row_container
                    if widgets.button_box in widgets.row_container.children:
                        widgets.row_container.remove(widgets.button_box)
                else:
                    # Show buttons by adding button_box to row_container
                    if widgets.button_box not in widgets.row_container.children:
                        widgets.row_container.add(widgets.button_box)
    
    def _update_header_text(self) -> None:
        """Update header text based on current mode.
        
        Note: This is a simplified implementation. In a more complex UI,
        you might need to store references to header labels for direct updates.
        For now, we'll rely on the button section update to provide visual feedback.
        """
        # The header text is recreated in _create_header(), but since we're
        # avoiding full rebuilds, we'll leave this as a placeholder for now.
        # The mode change is still clearly indicated by the button changes.
        pass
    
    def _update_button_section(self) -> None:
        """Update only the button section to reflect current mode.
        
        This is the only part that truly needs rebuilding since view and edit
        modes require completely different buttons (Edit/Delete vs Save/Cancel).
        """
        if not self._container:
            return
            
        # Find and remove the current button section
        # The button section is always the last child in the container
        if len(self._container.children) > 0:
            # Remove the last child (button section)
            last_child = self._container.children[-1]
            self._container.remove(last_child)
        
        # Add the new button section for current mode
        self._container.add(self._create_button_actions())
        
        logger.debug(f"Button section updated for mode: view={self._is_view_mode}")

    def _rebuild_container_ui(self) -> None:
        """Rebuild the container UI when mode changes.
        
        This method updates the existing container in place rather than creating
        a new one, ensuring that parent views continue to display the updated UI.
        """
        if not self._container:
            return
        
        # Clear existing content
        self._container.clear()
        
        # Reset widget references since we're rebuilding
        self._name_input = None
        self._logical_operator_selection = None
        self._conditions_container = None
        self._actions_container = None
        self._save_button = None
        self._discard_button = None
        
        # Rebuild all sections with current mode
        self._container.add(self._create_header())
        self._container.add(self._create_name_input_section())
        self._container.add(toga.Divider(style=Pack(margin_bottom=WIDGET_SPACING*2)))
        self._container.add(self._create_conditions_section())
        self._container.add(self._create_actions_section())
        self._container.add(self._create_button_actions())
        
        logger.debug("Container UI rebuilt for mode change")

    def create_widget(self) -> toga.Box:
        """Create and return the main container widget.
        
        This method builds the complete UI hierarchy and returns the root
        container that can be embedded in other views.
        
        Returns:
            toga.Box: The main container widget with all UI components
        """
        if self._container:
            # Return existing container if already created
            return self._container
        
        # Create main container with enhanced styling
        self._container = toga.Box(
            style=Pack(
                direction=COLUMN,
            ),
            children=[
                self._create_header(),
                self._create_name_input_section(),
                toga.Divider(style=Pack(margin_bottom=WIDGET_SPACING*2)),
                self._create_conditions_section(),
                self._create_actions_section(),
                self._create_button_actions()
            ]
        )
        
        logger.debug("Rule management container widget created")
        return self._container
    
    def _create_header(self) -> toga.Box:
        """Create header section with importer icon and name display.
        
        Shows different title based on container mode:
        - View Mode: "View Applied Rule"
        - Edit Mode with initial_rule: "Edit Rule"  
        - Edit Mode without initial_rule: "Create New Rule"
        
        Returns:
            toga.Box: Header widget with importer icon and name
        """
        header_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                align_items=START,
                margin_bottom=WIDGET_SPACING*2,
            )
        )

        # Create a container for the icon and subtitle
        subtitle_container = toga.Box(
            style=Pack(
                direction=ROW,
                align_items=CENTER,
            )
        )

        # Importer icon with enhanced styling
        importer_icon = toga.ImageView(
            image=toga.Image(f'resources/images/{self.importer_icon}'),
            style=Pack(
                width=18,
                height=18,
                margin_right=WIDGET_SPACING,
            )
        )

        # Subtitle and importer name
        if self._is_view_mode:
            subtitle_text = f"Rule from the {self.importer_name}"
        else:
            subtitle_text = f"This rule will apply to the {self.importer_name}"

        subtitle_label = toga.Label(
            subtitle_text,
            style=Pack(
                color="#6C757D",
                font_size=8,
            )
        )

        subtitle_container.add(importer_icon)
        subtitle_container.add(subtitle_label)

        header_box.add(subtitle_container)

        return header_box
    
    def _create_name_input_section(self) -> toga.Box:
        """Create rule name input with real-time validation.
        
        In view mode, the input is disabled to show the rule name as read-only.
        
        Returns:
            toga.Box: Name input section widget with validation
        """
        section_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=WIDGET_SPACING*2,
            )
        )
        
        rule_name_label = toga.Label(
            "Rule Name",
            style=Pack(
                margin_right=WIDGET_SPACING
            )
        )
        
        self._name_input = toga.TextInput(
            value=self._rule_name,
            placeholder="Enter a descriptive name for this rule" if not self._is_view_mode else "",
            style=Pack(
                flex=1,
            ),
            readonly=self._is_view_mode,  # Make read-only in view mode
            on_change=self._on_name_change if not self._is_view_mode else None
        )

        # Apply platform-specific decorations based on current mode
        self._apply_platform_decorations(self._name_input, is_readonly=self._is_view_mode)
        
        # Help text for guidance (only show in edit mode)
        if not self._is_view_mode:
            help_text = toga.Label(
                "Choose a clear, descriptive name that explains what this rule does.",
                style=Pack(
                    color="#6C757D",
                    font_size=8,
                )
            )

        section_box.add(rule_name_label)
        section_box.add(self._name_input)
        
        # Perform initial validation if there's existing data and we're in edit mode
        if self._rule_name and not self._is_view_mode:
            self._validate_name()
        
        return section_box
    
    def _create_conditions_section(self) -> toga.Box:
        """Create conditions section with logical operator and condition rows.
        
        Returns:
            toga.Box: Conditions section widget
        """
        section_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=WIDGET_SPACING
            )
        )
        
        # Section header with logical operator
        header_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=WIDGET_SPACING,
            )
        )
        
        header_box.add(toga.Label(
            "If",
            style=Pack(margin_right=WIDGET_SPACING)
        ))
        
        # Logical operator selection
        self._logical_operator_selection = toga.Selection(
            items=["all", "any"],
            value="all" if self._logical_operator == LogicalOperator.ALL else "any",
            style=Pack(margin_right=WIDGET_SPACING, width=58),
            enabled=not self._is_view_mode,  # Disable in view mode
            on_change=self._on_logical_operator_change if not self._is_view_mode else None
        )
        header_box.add(self._logical_operator_selection)
        
        header_box.add(toga.Label(
            "of the following conditions are met:",
        ))
        
        # Conditions container for dynamic rows
        self._conditions_container = toga.Box(
            style=Pack(
                direction=COLUMN,
            )
        )
        
        section_box.add(header_box)
        section_box.add(self._conditions_container)
        
        # Build initial condition rows
        self._rebuild_conditions_ui()
        
        return section_box
    
    def _create_actions_section(self) -> toga.Box:
        """Create actions section with action rows.
        
        Returns:
            toga.Box: Actions section widget
        """
        section_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                margin_bottom=WIDGET_SPACING
            )
        )
        
        # Section header
        header_label = toga.Label(
            "Then perform the following actions:",
            style=Pack(
                margin_bottom=WIDGET_SPACING,
            )
        )
        
        # Actions container for dynamic rows
        self._actions_container = toga.Box(
            style=Pack(
                direction=COLUMN,
            )
        )
        
        section_box.add(header_label)
        section_box.add(self._actions_container)
        
        # Build initial action rows
        self._rebuild_actions_ui()
        
        return section_box
    
    def _create_button_actions(self) -> toga.Box:
        """Create action buttons based on current mode.
        
        - View mode: Shows "Edit" and "Delete" buttons
        - Edit/Create mode: Shows "Cancel" and "Save"/"Update" buttons
        
        Returns:
            toga.Box: Button actions widget
        """
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
            )
        )
        
        if self._is_view_mode:
            # View mode: Show edit and delete buttons
            edit_button = toga.Button(
                EDIT_BUTTON_TEXT,
                style=Pack(
                    margin_right=WIDGET_SPACING,
                ),
                on_press=self._handle_edit
            )
            
            delete_button = toga.Button(
                DELETE_BUTTON_TEXT,
                style=Pack(
                    background_color="#dc3545",  # Red background for delete
                ),
                on_press=self._handle_delete
            )
            
            button_box.add(toga.Box(style=Pack(flex=1)))  # Spacer to push buttons to right
            button_box.add(edit_button)
            button_box.add(delete_button)
            
        else:
            # Edit/Create mode: Show cancel and save buttons
            self._discard_button = toga.Button(
                CANCEL_BUTTON_TEXT,
                style=Pack(
                    margin_right=WIDGET_SPACING,
                ),
                on_press=self._handle_discard
            )
            
            # Save button text depends on mode
            save_text = UPDATE_BUTTON_TEXT if self._is_editing_mode else SAVE_BUTTON_TEXT
            self._save_button = toga.Button(
                save_text,
                style=Pack(
                    background_color=DODGERBLUE,
                ),
                on_press=self._handle_save
            )
            
            button_box.add(toga.Box(style=Pack(flex=1)))  # Spacer to push buttons to the right
            button_box.add(self._discard_button)
            button_box.add(self._save_button)
            
            # Initialize save button state
            self._update_save_button_state()
        
        return button_box
    
    def _rebuild_conditions_ui(self) -> None:
        """Rebuild the conditions UI from current condition data.
        
        This method clears the conditions container and rebuilds all
        condition rows from the current _conditions list. It also resets
        the widget storage for performance optimization.
        """
        if not self._conditions_container:
            return
        
        # Clear existing condition handlers
        self._condition_handlers.clear()
        
        # Clear existing condition rows
        self._conditions_container.clear()
        
        # Clear widget storage for fresh rebuild
        self._condition_row_widgets.clear()
        
        # Create condition rows with new handlers and widget storage
        for index, condition_data in enumerate(self._conditions):
            condition_row = self._create_condition_row(index, condition_data)
            self._conditions_container.add(condition_row)
    
    def _rebuild_actions_ui(self) -> None:
        """Rebuild the actions UI from current action data.
        
        This method clears the actions container and rebuilds all
        action rows from the current _actions list. It also resets
        the widget storage for performance optimization.
        """
        if not self._actions_container:
            return
        
        # Clear existing action handlers
        self._action_handlers.clear()
        
        # Clear existing action rows
        self._actions_container.clear()
        
        # Clear widget storage for fresh rebuild
        self._action_row_widgets.clear()
        
        # Create action rows with new handlers and widget storage
        for index, action_data in enumerate(self._actions):
            action_row = self._create_action_row(index, action_data)
            self._actions_container.add(action_row)
    
    def _create_condition_row(self, index: int, condition_data: ConditionData) -> toga.Box:
        """Create a single condition row widget with field, operator, value inputs and add/remove buttons.
        
        In view mode, all inputs are disabled and add/remove buttons are hidden.
        
        Args:
            index: The index of this condition in the conditions list
            condition_data: The condition data for this row
            
        Returns:
            toga.Box: The condition row widget
        """
        # Normalize the condition data before creating UI
        self._normalize_condition_data(condition_data)

        # Create handler for this row
        handler = ConditionRowHandler(self, index)
        self._condition_handlers[index] = handler

        row_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=WIDGET_SPACING,
            )
        )
        
        # Field selector - now includes both standard fields and original_row keys
        field_items = self._get_available_field_options()
        
        # Determine current value for field selection
        current_field_value = None
        if condition_data.field is not None:
            current_field_value = get_field_display_name(condition_data.field)
        elif condition_data.original_row_key is not None:
            current_field_value = f"Original: {condition_data.original_row_key}"
        
        field_selection = toga.Selection(
            items=field_items,
            value=current_field_value,
            style=Pack(flex=1, margin_right=WIDGET_SPACING),
            enabled=not self._is_view_mode,  # Disable in view mode
            on_change=handler.on_field_change if not self._is_view_mode else None
        )
        
        # Operator selector (dynamically populated based on field)
        operator_items = []
        
        # Determine operators based on field type
        if condition_data.field is not None:
            # Use standard field operators
            operator_items = [
                get_operator_display_name(op)
                for op in get_operators_for_field(condition_data.field)
            ]
        elif condition_data.original_row_key is not None:
            # Use original_row operators (string-based)
            from .rule_management_data import get_operators_for_original_row
            operator_items = [
                get_operator_display_name(op)
                for op in get_operators_for_original_row()
            ]

        operator_selection = toga.Selection(
            items=operator_items,
            value=get_operator_display_name(condition_data.operator) if condition_data.operator else None,
            style=Pack(flex=1, margin_right=WIDGET_SPACING),
            enabled=not self._is_view_mode,  # Disable in view mode
            on_change=handler.on_operator_change if not self._is_view_mode else None
        )

        # Value input with appropriate placeholder
        value_placeholder = self._get_condition_value_placeholder(condition_data.field, condition_data.operator)
        value_input = toga.TextInput(
            value=condition_data.value,
            placeholder=value_placeholder if not self._is_view_mode else "",
            style=Pack(
                flex=2,
                margin_right=WIDGET_SPACING if not self._is_view_mode else 0
            ),
            readonly=self._is_view_mode,  # Make read-only in view mode
            on_change=handler.on_value_change if not self._is_view_mode else None
        )

        # Apply platform-specific decorations based on current mode
        self._apply_platform_decorations(value_input, is_readonly=self._is_view_mode)
        
        # Add all components to row
        row_box.add(field_selection)
        row_box.add(operator_selection)
        row_box.add(value_input)
        
        # Add/Remove buttons (always create but control visibility based on mode)
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
            )
        )
        
        # Add button (always enabled)
        add_button = toga.Button(
            "+",
            style=Pack(
                width=20,
                margin_left=WIDGET_SPACING
            ),
            on_press=handler.on_add_clicked
        )
        
        # Remove button (disabled if only one condition)
        remove_button = toga.Button(
            "−",
            style=Pack(
                width=20,
            ),
            on_press=handler.on_remove_clicked,
            enabled=len(self._conditions) > 1
        )
        
        button_box.add(remove_button)
        button_box.add(add_button)
        row_box.add(button_box)
        
        # Control button visibility based on mode using add/remove instead of CSS visibility
        if self._is_view_mode:
            # Hide buttons by removing button_box from row_container
            row_box.remove(button_box)
        # In edit mode, button_box is already added above
        
        # Performance optimization: Store widget references for efficient updates
        widgets = ConditionRowWidgets(
            field_selection=field_selection,
            operator_selection=operator_selection,
            value_input=value_input,
            row_container=row_box,
            add_button=add_button,
            remove_button=remove_button,
            button_box=button_box
        )
        
        # Ensure widget storage list is properly sized and store widgets
        if index >= len(self._condition_row_widgets):
            # Extend list to accommodate the new index
            self._condition_row_widgets.extend([None] * (index + 1 - len(self._condition_row_widgets)))
        
        self._condition_row_widgets[index] = widgets
        
        return row_box
    
    def _create_action_row(self, index: int, action_data: ActionData) -> toga.Box:
        """Create a single action row widget with action type selector, parameter input, and add/remove buttons.
        
        In view mode, all inputs are disabled and add/remove buttons are hidden.
        
        Args:
            index: The index of this action in the actions list
            action_data: The action data for this row
            
        Returns:
            toga.Box: The action row widget
        """
        # Normalize the action data before creating UI
        self._normalize_action_data(action_data)

        # Create handler for this row
        handler = ActionRowHandler(self, index)
        self._action_handlers[index] = handler

        row_box = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=WIDGET_SPACING
            )
        )
        
        # Action type selector
        action_type_items = [get_action_display_name(action_type) for action_type in ActionType]
        action_type_selection = toga.Selection(
            items=action_type_items,
            value=get_action_display_name(action_data.action_type) if action_data.action_type else None,
            style=Pack(
                flex=1,
                margin_right=WIDGET_SPACING
            ),
            enabled=not self._is_view_mode,  # Disable in view mode
            on_change=handler.on_type_change if not self._is_view_mode else None
        )
        
        # Parameter input with appropriate placeholder
        parameter_placeholder = self._get_action_parameter_placeholder(action_data.action_type)
        required_param = get_required_parameter_for_action(action_data.action_type) if action_data.action_type else None
        parameter_value = action_data.get_parameter_value(required_param) if required_param else ""
        
        parameter_input = toga.TextInput(
            value=parameter_value,
            placeholder=parameter_placeholder if not self._is_view_mode else "",
            style=Pack(
                flex=2,
                margin_right=WIDGET_SPACING if not self._is_view_mode else 0
            ),
            readonly=self._is_view_mode,  # Make read-only in view mode
            on_change=handler.on_parameter_change if not self._is_view_mode else None
        )

        # Apply platform-specific decorations based on current mode
        self._apply_platform_decorations(parameter_input, is_readonly=self._is_view_mode)

        
        # Add all components to row
        row_box.add(action_type_selection)
        row_box.add(parameter_input)
        
        # Add/Remove buttons (always create but control visibility based on mode)
        button_box = toga.Box(
            style=Pack(
                direction=ROW,
            )
        )
        
        # Add button (always enabled)
        add_button = toga.Button(
            "+",
            style=Pack(
                width=20,
                margin_left=WIDGET_SPACING
            ),
            on_press=handler.on_add_clicked
        )
        
        # Remove button (disabled if only one action)
        remove_button = toga.Button(
            "−",
            style=Pack(
                width=20
            ),
            on_press=handler.on_remove_clicked,
            enabled=len(self._actions) > 1
        )
        
        button_box.add(remove_button)
        button_box.add(add_button)
        row_box.add(button_box)
        
        # Control button visibility based on mode using add/remove instead of CSS visibility
        if self._is_view_mode:
            # Hide buttons by removing button_box from row_container
            row_box.remove(button_box)
        # In edit mode, button_box is already added above
        
        # Performance optimization: Store widget references for efficient updates
        widgets = ActionRowWidgets(
            action_type_selection=action_type_selection,
            parameter_input=parameter_input,
            row_container=row_box,
            add_button=add_button,
            remove_button=remove_button,
            button_box=button_box
        )
        
        # Ensure widget storage list is properly sized and store widgets
        if index >= len(self._action_row_widgets):
            # Extend list to accommodate the new index
            self._action_row_widgets.extend([None] * (index + 1 - len(self._action_row_widgets)))
        
        self._action_row_widgets[index] = widgets
        
        return row_box
    
    def _get_condition_value_placeholder(self, field: Optional[Field], operator: Optional[Operator]) -> str:
        """Get appropriate placeholder text for condition value input.
        
        Args:
            field: The selected field
            operator: The selected operator
            
        Returns:
            str: Placeholder text for the value input
        """
        if not field:
            return "Select field first"
        
        if field == Field.PAYEE:
            if operator == Operator.REGEX_MATCH:
                return "Regular expression pattern"
            return "Payee name (e.g., Amazon, Starbucks)"
        elif field == Field.NARRATION:
            if operator == Operator.REGEX_MATCH:
                return "Regular expression pattern"
            return "Transaction description"
        elif field == Field.AMOUNT:
            return "Amount (e.g., 25.50, 100)"
        elif field == Field.DATE:
            return "Date (YYYY-MM-DD format)"
        elif field == Field.CURRENCY:
            return "Currency code (e.g., USD, EUR)"
        else:
            return "Value"
    
    def _get_action_parameter_placeholder(self, action_type: Optional[ActionType]) -> str:
        """Get appropriate placeholder text for action parameter input.
        
        Args:
            action_type: The selected action type
            
        Returns:
            str: Placeholder text for the parameter input
        """
        if not action_type:
            return "Select action type first"
        
        return get_parameter_placeholder(action_type)
    
    # Event handlers
    
    def _on_name_change(self, widget: toga.TextInput) -> None:
        """Handle rule name input changes.
        
        Args:
            widget: The TextInput widget that changed
        """
        self._rule_name = widget.value or ""
        self._validate_name()
    
    def _on_logical_operator_change(self, widget: toga.Selection) -> None:
        """Handle logical operator selection changes.
        
        Args:
            widget: The Selection widget that changed
        """
        if widget.value == "all":
            self._logical_operator = LogicalOperator.ALL
        else:
            self._logical_operator = LogicalOperator.ANY
        
        logger.debug(f"Logical operator changed to: {self._logical_operator}")
    
    def _handle_save(self, widget: toga.Button) -> None:
        """Handle save button press.
        
        Args:
            widget: The Button widget that was pressed
        """
        if self._is_saving:
            return  # Prevent double-saves
        
        try:
            self._is_saving = True
            self._save_rule()
        finally:
            self._is_saving = False
    
    def _handle_discard(self, widget: toga.Button) -> None:
        """Handle discard/cancel button press.
        
        In create mode: Clear fields and call cancel callback.
        In edit mode: Exit edit mode and return to view mode without saving.
        
        Args:
            widget: The Button widget that was pressed
        """
        if self._is_editing_mode:
            # Exit edit mode without saving changes
            logger.debug("Discarding changes and exiting edit mode")
            self.exit_edit_mode(save_changes=False)
        else:
            # Standard create mode cancellation
            logger.debug("Handling create mode cancellation")
            if self._on_cancel:
                self._on_cancel()
    
    def _handle_edit(self, widget: toga.Button) -> None:
        """Handle edit button press in view mode.
        
        Transitions from view mode to edit mode for the current rule.
        
        Args:
            widget: The Button widget that was pressed
        """
        if not self._is_view_mode or not self._viewed_rule:
            logger.warning("Edit button pressed but not in view mode or no rule to edit")
            return
        
        logger.info(f"Edit button pressed for rule: {self._viewed_rule.name}")
        
        # Enter edit mode with the current viewed rule
        self.enter_edit_mode(self._viewed_rule)

    def _handle_delete(self, widget: toga.Button) -> None:
        """Handle delete button press in view mode.
        
        Shows a confirmation dialog before deleting the rule.
        
        Args:
            widget: The Button widget that was pressed
        """
        if not self._is_view_mode or not self._viewed_rule:
            logger.warning("Delete button pressed but not in view mode or no rule to delete")
            return
        
        # If no container or window reference available, proceed without confirmation
        if not self._container or not self._container.window:
            logger.warning("No window reference available for confirmation dialog")
            self._perform_delete()
            return
        
        # Show confirmation dialog
        rule_name = self._viewed_rule.name
        confirm_dialog = toga.ConfirmDialog(
            "Delete Rule",
            f"Are you sure you want to delete the rule '{rule_name}'?\n\nThis action cannot be undone."
        )
        
        # Create async task for dialog and handle response
        task = asyncio.create_task(self._container.window.dialog(confirm_dialog))
        task.add_done_callback(self._on_delete_confirmation)
        
        logger.debug(f"Delete confirmation dialog created for rule: {rule_name}")
    
    def _on_delete_confirmation(self, task: asyncio.Task[bool]) -> None:
        """Handle the result of the delete confirmation dialog.
        
        Args:
            task: The completed asyncio task containing the dialog result
        """
        try:
            # Get the dialog result
            confirmed = task.result()
            
            if confirmed:
                logger.debug("User confirmed rule deletion")
                self._perform_delete()
            else:
                logger.debug("User cancelled rule deletion")
        except Exception as e:
            logger.error(f"Error handling delete confirmation: {e}")
    
    def _perform_delete(self) -> None:
        """Perform the actual rule deletion after confirmation.
        
        This method contains the original deletion logic, separated from
        the confirmation dialog handling.
        """
        if not self._is_view_mode or not self._viewed_rule:
            logger.warning("Cannot perform delete: not in view mode or no rule to delete")
            return
        
        try:
            rule_id = self._viewed_rule.rule_id
            rule_name = self._viewed_rule.name
            
            # Delete the rule using rule engine
            success = self._rule_engine.delete_rule(rule_id)
            
            if success:
                logger.info(f"Successfully deleted rule: {rule_name} ({rule_id})")
                
                # Notify parent about rule deletion
                if self._on_rule_deleted:
                    try:
                        self._on_rule_deleted(rule_id)
                    except Exception as callback_error:
                        logger.error(f"Error in rule deletion callback: {callback_error}")
                
                # Clear the viewed rule and switch to edit mode
                self._is_view_mode = False
                self._viewed_rule = None
                
                # Clear applied_rule_ids from transaction data so we don't switch back to view mode
                # but preserve the transaction data so original_row metadata is still available
                if self._transaction_data:
                    self._transaction_data.update_applied_rules([])
                
                # Reset to default state for new rule creation
                self._rule_name = ""
                self._logical_operator = LogicalOperator.ALL
                self._conditions.clear()
                self._actions.clear()
                self._validation_errors.clear()
                
                # Initialize with default data for edit mode
                self._initialize_default_data()
                
                # Rebuild UI to show edit mode
                if self._container:
                    self._rebuild_container_ui()
                
                logger.debug("Switched to edit mode after rule deletion")
                
            else:
                logger.error(f"Failed to delete rule: {rule_name} ({rule_id})")
                # TODO: Display error message in UI
                
        except Exception as e:
            logger.error(f"Error deleting rule: {e}")
            # TODO: Display error message in UI
    
    # Condition management event handlers
    
    def _on_condition_field_change(self, index: int, field_display_name: str) -> None:
        """Handle condition field selection changes.
        
        This method implements intelligent auto-population of condition values when
        a user selects a field. It extracts the appropriate value from the current
        transaction data and populates the value input, improving user experience
        by reducing manual data entry.
        
        Auto-population behavior:
        - Only triggers in edit mode (not view mode)
        - Respects configuration settings for preserving user input
        - Handles both standard Field enum values and original_row metadata keys
        - Formats values appropriately (e.g., amount formatting, string trimming)
        
        Args:
            index: The index of the condition that changed
            field_display_name: The display name of the selected field
        """
        if index >= len(self._conditions):
            return
        
        # Parse the field selection to determine if it's standard or original_row
        field, original_row_key = self._parse_field_selection(field_display_name)
        
        # Update condition data
        condition_data = self._conditions[index]
        condition_data.field = field
        condition_data.original_row_key = original_row_key

        # Auto-populate value from transaction data if enabled and appropriate
        if (self._auto_populate_on_field_change and 
            not self._is_view_mode and 
            self._transaction_data):
            
            # Check if we should preserve existing user input
            should_auto_populate = True
            if self._preserve_user_input and condition_data.value.strip():
                should_auto_populate = False
                logger.debug(f"Preserving existing user input for condition {index}: '{condition_data.value}'")
            
            if should_auto_populate:
                auto_value = self._extract_value_for_field(field, original_row_key)
                if auto_value:
                    condition_data.value = auto_value
                    logger.debug(f"Auto-populated condition {index} with value: '{auto_value}'")

        # Normalize after field change - this will set appropriate operator
        self._normalize_condition_data(condition_data)

        # Update only the affected row instead of rebuilding everything
        self._update_condition_row(index)
        
        logger.debug(f"Condition {index} field changed to: {field} (original_row_key: {original_row_key})")
    
    def _on_condition_operator_change(self, index: int, operator_display_name: str) -> None:
        """Handle condition operator selection changes.
        
        Args:
            index: The index of the condition that changed
            operator_display_name: The display name of the selected operator
        """
        if index >= len(self._conditions):
            return
        
        # Find the Operator enum value from display name
        operator = None
        for op in Operator:
            if get_operator_display_name(op) == operator_display_name:
                operator = op
                break
        
        condition_data = self._conditions[index]
        condition_data.operator = operator
        
        # Normalize after operator change - this might clear value if incompatible
        self._normalize_condition_data(condition_data)
        
        # Update the value input placeholder
        self._update_condition_row(index)
        
        logger.debug(f"Condition {index} operator changed to: {operator}")
    
    def _on_condition_value_change(self, index: int, value: str) -> None:
        """Handle condition value input changes.
        
        Args:
            index: The index of the condition that changed
            value: The new value
        """
        if index >= len(self._conditions):
            return
        
        # Update condition data
        self._conditions[index].value = value
        
        logger.debug(f"Condition {index} value changed to: {value}")
    
    def _add_condition_after(self, index: int) -> None:
        """Add a new condition after the specified index.
        
        Args:
            index: The index after which to add the new condition
        """
        # Create new condition with proper defaults
        new_condition = self._create_default_condition()
        
        # Insert after the specified index
        self._conditions.insert(index + 1, new_condition)
        
        # Rebuild conditions UI
        self._rebuild_conditions_ui()
        
        logger.debug(f"Added new condition after index {index}")
    
    def _remove_condition(self, index: int) -> None:
        """Remove the condition at the specified index.
        
        Args:
            index: The index of the condition to remove
        """
        if len(self._conditions) <= 1:
            # Don't allow removing the last condition
            return
        
        if index >= len(self._conditions):
            return
        
        # Remove the condition
        removed_condition = self._conditions.pop(index)
        
        # Clean up handler for removed condition
        if index in self._condition_handlers:
            del self._condition_handlers[index]
        
        # Renumber remaining handlers to maintain index consistency
        new_handlers = {}
        for old_index, handler in self._condition_handlers.items():
            if old_index > index:
                new_index = old_index - 1
                handler.row_index = new_index
                new_handlers[new_index] = handler
            else:
                new_handlers[old_index] = handler
        
        self._condition_handlers = new_handlers
        
        # Rebuild conditions UI
        self._rebuild_conditions_ui()
        
        logger.debug(f"Removed condition at index {index}: {removed_condition}")
    
    def _update_condition_row(self, index: int) -> None:
        """Update condition row with simple event disconnection pattern.
        
        This method provides fast widget updates by temporarily disconnecting
        event handlers to prevent recursion, then updating properties directly.
        """
        if not self._conditions_container or index >= len(self._conditions):
            return
        
        # Try optimized widget update if widgets exist
        if (index < len(self._condition_row_widgets) and 
            self._condition_row_widgets[index] is not None):
            
            widgets = self._condition_row_widgets[index]
            if widgets is None:  # Type guard for mypy
                return
                
            condition_data = self._conditions[index]
            
            try:
                # Temporarily disconnect all event handlers
                widgets.field_selection.on_change = None
                widgets.operator_selection.on_change = None
                widgets.value_input.on_change = None
                
                # Update field selection
                if condition_data.field is not None:
                    field_value = get_field_display_name(condition_data.field)
                elif condition_data.original_row_key is not None:
                    field_value = f"Original: {condition_data.original_row_key}"
                else:
                    field_value = None
                
                if widgets.field_selection.value != field_value:
                    widgets.field_selection.items = self._get_available_field_options()
                    widgets.field_selection.value = field_value
                
                # Update operator selection based on field
                if condition_data.field is not None:
                    available_operators = get_operators_for_field(condition_data.field)
                elif condition_data.original_row_key is not None:
                    from .rule_management_data import get_operators_for_original_row
                    available_operators = get_operators_for_original_row()
                else:
                    available_operators = []
                
                operator_items = [get_operator_display_name(op) for op in available_operators]
                operator_value = get_operator_display_name(condition_data.operator) if condition_data.operator else None
                
                if widgets.operator_selection.items != operator_items:
                    widgets.operator_selection.items = operator_items
                if widgets.operator_selection.value != operator_value:
                    widgets.operator_selection.value = operator_value
                
                # Update value input
                if widgets.value_input.value != condition_data.value:
                    widgets.value_input.value = condition_data.value
                
                # Update placeholder
                if not self._is_view_mode:
                    new_placeholder = self._get_condition_value_placeholder(condition_data.field, condition_data.operator)
                    if widgets.value_input.placeholder != new_placeholder:
                        widgets.value_input.placeholder = new_placeholder
                
                # Update button states
                if not self._is_view_mode and widgets.remove_button:
                    new_enabled = len(self._conditions) > 1
                    if widgets.remove_button.enabled != new_enabled:
                        widgets.remove_button.enabled = new_enabled
                
                logger.debug(f"Condition row {index} updated via optimized widget update")
                return
                
            finally:
                # Always reconnect event handlers using current handler instance
                if index in self._condition_handlers:
                    handler = self._condition_handlers[index]
                    widgets.field_selection.on_change = handler.on_field_change
                    widgets.operator_selection.on_change = handler.on_operator_change
                    widgets.value_input.on_change = handler.on_value_change
        
        # Fallback to widget recreation if optimization failed
        logger.debug(f"Condition row {index} falling back to widget recreation")
        condition_data = self._conditions[index]
        new_row = self._create_condition_row(index, condition_data)
        
        # Replace the row in the container
        children = list(self._conditions_container.children)
        if index < len(children):
            self._conditions_container.remove(children[index])
            self._conditions_container.insert(index, new_row)

    # Action management event handlers
    
    def _on_action_type_change(self, index: int, action_type_display_name: str) -> None:
        """Handle action type selection changes.
        
        This method implements intelligent auto-population of action parameters when
        a user selects an action type. It extracts the appropriate parameter value from 
        the current transaction data and populates the parameter input, improving user 
        experience by reducing manual data entry.
        
        Auto-population behavior:
        - Only triggers in edit mode (not view mode)
        - Respects configuration settings for preserving user input
        - Maps action types to appropriate transaction data sources
        - Formats parameter values appropriately for the selected action type
        
        Args:
            index: The index of the action that changed
            action_type_display_name: The display name of the selected action type
        """
        if index >= len(self._actions):
            return
        
        # Find the ActionType enum value from display name
        action_type = None
        for at in ActionType:
            if get_action_display_name(at) == action_type_display_name:
                action_type = at
                break
        
        action_data = self._actions[index]
        action_data.action_type = action_type

        # Auto-populate parameter from transaction data if enabled and appropriate
        if (self._auto_populate_on_field_change and 
            not self._is_view_mode and 
            self._transaction_data and
            action_type):
            
            # Get the required parameter name for this action type
            required_param = get_required_parameter_for_action(action_type)
            current_param_value = action_data.get_parameter_value(required_param) if required_param else ""
            
            # Check if we should preserve existing user input
            should_auto_populate = True
            if self._preserve_user_input and current_param_value and current_param_value.strip():
                should_auto_populate = False
                logger.debug(f"Preserving existing user input for action {index}: '{current_param_value}'")
            
            if should_auto_populate:
                auto_value = self._extract_parameter_for_action_type(action_type)
                if auto_value and required_param:
                    action_data.set_parameter_value(required_param, auto_value)
                    logger.debug(f"Auto-populated action {index} parameter '{required_param}' with value: '{auto_value}'")

        # Normalize after action type change - this will clear parameters if not auto-populated
        self._normalize_action_data(action_data)
        
        # Update the parameter input
        self._update_action_row(index)
        
        logger.debug(f"Action {index} type changed to: {action_type}")
    
    def _on_action_parameter_change(self, index: int, parameter_value: str) -> None:
        """Handle action parameter input changes.
        
        Args:
            index: The index of the action that changed
            parameter_value: The new parameter value
        """
        if index >= len(self._actions):
            return
        
        action_data = self._actions[index]
        if not action_data.action_type:
            return
        
        # Get the required parameter name for this action type
        required_param = get_required_parameter_for_action(action_data.action_type)
        if required_param:
            # Set the parameter value
            action_data.set_parameter_value(required_param, parameter_value)
        
        logger.debug(f"Action {index} parameter changed to: {parameter_value}")
    
    def _add_action_after(self, index: int) -> None:
        """Add a new action after the specified index.
        
        Args:
            index: The index after which to add the new action
        """
        # Create new action with proper defaults
        new_action = self._create_default_action()
        
        # Insert after the specified index
        self._actions.insert(index + 1, new_action)
        
        # Rebuild actions UI
        self._rebuild_actions_ui()
        
        logger.debug(f"Added new action after index {index}")
    
    def _remove_action(self, index: int) -> None:
        """Remove the action at the specified index.
        
        Args:
            index: The index of the action to remove
        """
        if len(self._actions) <= 1:
            # Don't allow removing the last action
            return
        
        if index >= len(self._actions):
            return
        
        # Remove the action
        removed_action = self._actions.pop(index)
        
        # Clean up handler for removed action
        if index in self._action_handlers:
            del self._action_handlers[index]
        
        # Renumber remaining handlers to maintain index consistency
        new_handlers = {}
        for old_index, handler in self._action_handlers.items():
            if old_index > index:
                new_index = old_index - 1
                handler.row_index = new_index
                new_handlers[new_index] = handler
            else:
                new_handlers[old_index] = handler
        
        self._action_handlers = new_handlers
        
        # Rebuild actions UI
        self._rebuild_actions_ui()
        
        logger.debug(f"Removed action at index {index}: {removed_action}")

    def _update_action_row(self, index: int) -> None:
        """Update action row with simple event disconnection pattern.
        
        This method provides fast widget updates by temporarily disconnecting
        event handlers to prevent recursion, then updating properties directly.
        """
        if not self._actions_container or index >= len(self._actions):
            return
        
        # Try optimized widget update if widgets exist
        if (index < len(self._action_row_widgets) and 
            self._action_row_widgets[index] is not None):
            
            widgets = self._action_row_widgets[index]
            if widgets is None:  # Type guard for mypy
                return
                
            action_data = self._actions[index]
            
            try:
                # Temporarily disconnect all event handlers
                widgets.action_type_selection.on_change = None
                widgets.parameter_input.on_change = None
                
                # Update action type selection
                action_type_items = [get_action_display_name(action_type) for action_type in ActionType]
                action_type_value = get_action_display_name(action_data.action_type) if action_data.action_type else None
                
                if widgets.action_type_selection.items != action_type_items:
                    widgets.action_type_selection.items = action_type_items
                if widgets.action_type_selection.value != action_type_value:
                    widgets.action_type_selection.value = action_type_value
                
                # Update parameter input
                required_param = get_required_parameter_for_action(action_data.action_type) if action_data.action_type else None
                parameter_value = action_data.get_parameter_value(required_param) if required_param else ""
                
                if widgets.parameter_input.value != parameter_value:
                    widgets.parameter_input.value = parameter_value
                
                # Update placeholder
                if not self._is_view_mode:
                    new_placeholder = self._get_action_parameter_placeholder(action_data.action_type)
                    if widgets.parameter_input.placeholder != new_placeholder:
                        widgets.parameter_input.placeholder = new_placeholder
                
                # Update button states
                if not self._is_view_mode and widgets.remove_button:
                    new_enabled = len(self._actions) > 1
                    if widgets.remove_button.enabled != new_enabled:
                        widgets.remove_button.enabled = new_enabled
                
                logger.debug(f"Action row {index} updated via optimized widget update")
                return
                
            finally:
                # Always reconnect event handlers using current handler instance
                if index in self._action_handlers:
                    handler = self._action_handlers[index]
                    widgets.action_type_selection.on_change = handler.on_type_change
                    widgets.parameter_input.on_change = handler.on_parameter_change
        
        # Fallback to widget recreation if optimization failed
        logger.debug(f"Action row {index} falling back to widget recreation")
        action_data = self._actions[index]
        new_row = self._create_action_row(index, action_data)
        
        # Replace the row in the container
        children = list(self._actions_container.children)
        if index < len(children):
            self._actions_container.remove(children[index])
            self._actions_container.insert(index, new_row)

    # Validation methods
    
    def _validate_name(self) -> None:
        """Validate the rule name with comprehensive real-time validation.
        
        Performs thorough validation of the rule name including:
        - Required field validation
        - Length validation
        - Character validation
        - Uniqueness validation (if applicable)
        
        Updates the error display with appropriate feedback.
        """
        errors = []
        name = self._rule_name.strip() if self._rule_name else ""
        
        # Required field validation
        if not name:
            errors.append("Rule name is required")
        else:
            # Length validation
            if len(name) > 50:
                errors.append("Rule name must be 50 characters or less")
            
            # Character validation - ensure reasonable characters
            if not all(c.isalnum() or c.isspace() or c in "'-_()[]{}.,!?" for c in name):
                errors.append("Rule name contains invalid characters")
            
            # Check for only whitespace or special characters
            if not any(c.isalnum() for c in name):
                errors.append("Rule name must contain at least one letter or number")
            
            # Check for duplicate names (basic check - could be enhanced with repository lookup)
            if name.lower() in ["new rule", "untitled", "rule"]:
                errors.append("Please choose a more descriptive name")
        
        # Update input field styling based on validation state
        if self._name_input:
            if errors:
                # Indicate error state (Toga has limited styling options)
                pass  # Could add border color if supported
            else:
                # Indicate valid state
                pass  # Could add success styling if supported
        
        # Store validation state for overall rule validation
        if errors:
            self._validation_errors["name"] = errors
        elif "name" in self._validation_errors:
            del self._validation_errors["name"]
        
        logger.debug(f"Name validation: {'FAILED' if errors else 'PASSED'} - {name}")
        
        # Update save button state based on overall validation
        self._update_save_button_state()
    
    def _update_save_button_state(self) -> None:
        """Update save button enabled state based on validation status.
        
        Enables the save button only when basic validation passes,
        providing immediate feedback to users about form completeness.
        """
        if not self._save_button:
            return
        
        # Check if name validation passes (minimum requirement)
        has_name_errors = "name" in self._validation_errors
        has_valid_name = bool(self._rule_name and self._rule_name.strip())
        print(self._validation_errors, self._rule_name)
        # Enable save button if basic requirements are met
        # Full validation will be performed on save attempt
        self._save_button.enabled = has_valid_name and not has_name_errors
    
    def validate_rule(self) -> List[str]:
        """Perform comprehensive rule validation.
        
        Returns:
            List[str]: List of validation error messages (empty if valid)
        """
        return validate_rule_ui_data(
            self._rule_name,
            self._logical_operator,
            self._conditions,
            self._actions
        )
    
    # Rule creation and persistence
    
    def _save_rule(self) -> None:
        """Create or update a rule with comprehensive validation."""
        try:
            # Validate the complete rule
            validation_errors = self.validate_rule()
            if validation_errors:
                logger.warning(f"Rule validation failed: {validation_errors}")
                # TODO: Display validation errors in UI (will be implemented in task 8)
                return
            
            # Get rule components for engine creation/update
            conditions_block = create_conditions_block_from_ui_data(self._logical_operator, self._conditions)
            actions = create_actions_from_ui_data(self._actions)
            
            if self._is_editing_mode:
                # Update existing rule
                self._save_existing_rule(conditions_block, actions)
            else:
                # Create new rule
                self._save_new_rule(conditions_block, actions)
            
        except Exception as e:
            logger.error(f"Error saving rule: {e}")
    
    def _save_new_rule(self, conditions_block, actions) -> None:
        """Save a new rule."""
        # Create new rule using rule engine for proper validation and conflict detection
        rule = self._rule_engine.create_rule(
            name=self._rule_name.strip(),
            conditions_block=conditions_block,
            actions=actions
        )
        
        # Create and handle rule via consolidated callback
        updated_transaction_ids = []
        if self._on_rule_created:
            try:
                # The callback handles both rule application and save notification
                # It may return a list of updated transaction IDs if rule was applied
                logger.info(f"Notifying rule creation: {rule.rule_id}")
                updated_transaction_ids = self._on_rule_created(rule) or []
                if updated_transaction_ids:
                    logger.info(f"Rule applied to {len(updated_transaction_ids)} transactions")
                else:
                    logger.info("Rule created and saved successfully")
            except Exception as e:
                logger.error(f"Error in rule creation callback: {e}")
                # Continue with save process even if callback fails
        
        # Switch to view mode to show the newly created rule
        self._is_view_mode = True
        self._viewed_rule = rule
        
        # Rebuild UI to show view mode
        if self._container:
            self._rebuild_container_ui()
        
        if updated_transaction_ids:
            logger.info(f"Rule saved successfully: {rule.rule_id}, applied to {len(updated_transaction_ids)} transactions, switched to view mode")
        else:
            logger.info(f"Rule saved successfully: {rule.rule_id}, switched to view mode")
    
    def _save_existing_rule(self, conditions_block, actions) -> None:
        """Update an existing rule using the rule engine's update method."""
        if not self._editing_rule_id or not self._original_rule:
            logger.error("Cannot save existing rule - missing rule ID or original rule")
            return
        
        try:
            # Update the rule using the rule engine's update method
            updated_rule = self._rule_engine.update_rule(
                rule_id=self._editing_rule_id,
                name=self._rule_name.strip(),
                conditions_block=conditions_block,
                actions=actions,
                is_enabled=self._original_rule.is_enabled,
                stop_processing=self._original_rule.stop_processing
            )
            
            logger.info(f"Successfully updated rule: {updated_rule.rule_id}")
            
            # Handle rule update via callback
            updated_transaction_ids = []
            if self._on_rule_edited:
                try:
                    logger.info(f"Notifying rule update: {updated_rule.rule_id}")
                    updated_transaction_ids = self._on_rule_edited(updated_rule) or []
                    if updated_transaction_ids:
                        logger.info(f"Updated rule applied to {len(updated_transaction_ids)} transactions")
                    else:
                        logger.info("Rule updated and saved successfully")
                except Exception as e:
                    logger.error(f"Error in rule edit callback: {e}")
                    # Continue with save process even if callback fails
            
            # Exit edit mode and return to view mode with updated rule
            self.exit_edit_mode(save_changes=True)
            self._viewed_rule = updated_rule  # Update the viewed rule to the new version
            
            if updated_transaction_ids:
                logger.info(f"Rule updated successfully: {updated_rule.rule_id}, applied to {len(updated_transaction_ids)} transactions, returned to view mode")
            else:
                logger.info(f"Rule updated successfully: {updated_rule.rule_id}, returned to view mode")
                
        except Exception as e:
            logger.error(f"Failed to update rule {self._editing_rule_id}: {e}")
            # TODO: Display error message in UI (will be implemented in task 8)
            # TODO: Display error message in UI (will be implemented in task 8)
    
    # Cleanup methods
    
    def cleanup(self) -> None:
        """Clean up widget references and event handlers.
        
        This method should be called when the container is no longer needed
        to prevent memory leaks and ensure proper cleanup.
        """
        # Clean up transaction observers first
        self._cleanup_transaction_observers()
        
        # Clean up event handlers
        self._condition_handlers.clear()
        self._action_handlers.clear()
        
        # Clear widget references
        self._container = None
        self._name_input = None
        self._logical_operator_selection = None
        self._conditions_container = None
        self._actions_container = None
        self._save_button = None
        self._discard_button = None
        
        # Clear performance optimization widget storage
        self._condition_row_widgets.clear()
        self._action_row_widgets.clear()
        
        # Clear transaction data references
        self._transaction_data = None
        
        # Clear data
        self._conditions.clear()
        self._actions.clear()
        self._validation_errors.clear()
        
        logger.debug("RuleManagementContainer cleaned up")