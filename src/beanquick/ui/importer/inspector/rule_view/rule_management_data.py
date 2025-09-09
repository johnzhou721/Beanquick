"""
Data models and utilities for the advanced rule management UI.

This module provides UI-specific data structures that bridge between the user
interface components and the enhanced rule engine system. It includes conversion
methods, validation utilities, and field-to-operator mappings for dynamic UI updates.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from beanquick.importers.rules.rule_components import (
    Field, Operator, ActionType, LogicalOperator,
    Condition, Action, ConditionsBlock
)


@dataclass
class ConditionData:
    """UI data structure for condition input with conversion methods.
    
    This mutable dataclass represents condition data as entered by the user
    in the UI, with methods to convert to the immutable enhanced rule system
    Condition objects.
    
    Attributes:
        field: The transaction field to match against (None if using original_row_key)
        operator: The comparison operator to use
        value: The value to compare with (as string from UI input)
        case_sensitive: Whether string comparisons should be case-sensitive
        original_row_key: Key from original_row metadata (used when field is None)
    """
    field: Optional[Field] = None
    operator: Optional[Operator] = None
    value: str = ""
    case_sensitive: bool = False
    original_row_key: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if this condition has all required fields filled.
        
        Returns:
            bool: True if field, operator, and value are all set
        """
        # We need either a standard field OR an original_row_key
        has_valid_field = (
            self.field is not None or
            self.original_row_key is not None
        )
        
        return (
            has_valid_field and 
            self.operator is not None and 
            bool(self.value.strip())
        )
    
    def validate(self) -> List[str]:
        """Validate the condition data and return any errors.
        
        Returns:
            List[str]: List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check that we have either a standard field or an original_row_key
        if self.field is None and self.original_row_key is None:
            errors.append("Field selection is required")
        
        if self.operator is None:
            errors.append("Operator selection is required")
        
        if not self.value or not self.value.strip():
            errors.append("Value is required")
        
        # Validate field/operator compatibility
        if self.field is not None and self.operator is not None:
            if not is_operator_valid_for_field(self.field, self.operator):
                errors.append(f"Operator {self.operator.value} is not valid for field {self.field.value}")
        
        # Validate regex patterns if using regex operator
        if self.operator == Operator.REGEX_MATCH and self.value.strip():
            import re
            try:
                re.compile(self.value)
            except re.error as e:
                errors.append(f"Invalid regex pattern: {e}")
        
        # Validate numeric values for numeric operators
        if (self.field == Field.AMOUNT and 
            self.operator in get_numeric_operators() and 
            self.value.strip()):
            try:
                float(self.value)
            except ValueError:
                errors.append("Amount value must be a valid number")
        
        # Validate date values for date operators
        if (self.field == Field.DATE and 
            self.operator in get_date_operators() and 
            self.value.strip()):
            from datetime import datetime
            try:
                # Try to parse as ISO date format
                if 'T' in self.value or ' ' in self.value:
                    date_part = self.value.split('T')[0].split(' ')[0]
                    datetime.fromisoformat(date_part)
                else:
                    datetime.fromisoformat(self.value)
            except ValueError:
                errors.append("Date value must be in ISO format (YYYY-MM-DD)")
        
        return errors
    
    def to_condition(self) -> Condition:
        """Convert to enhanced rule system Condition object.
        
        Returns:
            Condition: Immutable condition object for the rule engine
            
        Raises:
            ValueError: If the condition data is incomplete or invalid
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ValueError(f"Cannot convert invalid condition: {'; '.join(validation_errors)}")
        
        # Ensure operator is not None (validation should have caught this)
        if self.operator is None:
            raise ValueError("Operator cannot be None")
        
        return Condition(
            field=self.field,  # Can be None for original_row fields
            operator=self.operator,
            value=self.value.strip(),
            case_sensitive=self.case_sensitive,
            original_row_key=self.original_row_key
        )
    
    @classmethod
    def from_condition(cls, condition: Condition) -> 'ConditionData':
        """Create ConditionData from an existing Condition object.
        
        Args:
            condition: The Condition object to convert from
            
        Returns:
            ConditionData: Mutable UI data structure
        """
        return cls(
            field=condition.field,
            operator=condition.operator,
            value=condition.value,
            case_sensitive=condition.case_sensitive,
            original_row_key=condition.original_row_key
        )
    
    def copy(self) -> 'ConditionData':
        """Create a copy of this condition data.
        
        Returns:
            ConditionData: A new instance with the same values
        """
        return ConditionData(
            field=self.field,
            operator=self.operator,
            value=self.value,
            case_sensitive=self.case_sensitive,
            original_row_key=self.original_row_key
        )


@dataclass
class ActionData:
    """UI data structure for action input with conversion methods.
    
    This mutable dataclass represents action data as entered by the user
    in the UI, with methods to convert to the immutable enhanced rule system
    Action objects.
    
    Attributes:
        action_type: The type of action to perform
        parameters: Dictionary of parameters for the action (mutable for UI)
    """
    action_type: Optional[ActionType] = None
    parameters: Dict[str, str] = field(default_factory=dict)
    
    def is_complete(self) -> bool:
        """Check if this action has all required fields filled.
        
        Returns:
            bool: True if action_type is set and required parameters are present
        """
        if self.action_type is None:
            return False
        
        required_param = get_required_parameter_for_action(self.action_type)
        if required_param:
            return required_param in self.parameters and bool(self.parameters[required_param].strip())
        
        return True
    
    def validate(self) -> List[str]:
        """Validate the action data and return any errors.
        
        Returns:
            List[str]: List of validation error messages (empty if valid)
        """
        errors = []
        
        if self.action_type is None:
            errors.append("Action type selection is required")
            return errors
        
        # Validate required parameters based on action type
        required_param = get_required_parameter_for_action(self.action_type)
        if required_param:
            if required_param not in self.parameters:
                param_display = get_parameter_display_name(required_param)
                errors.append(f"{param_display} is required for {self.action_type.value}")
            elif not self.parameters[required_param].strip():
                param_display = get_parameter_display_name(required_param)
                errors.append(f"{param_display} cannot be empty")
        
        # Validate account names for SET_SOURCE_ACCOUNT action
        if (self.action_type == ActionType.SET_SOURCE_ACCOUNT and 
            "account" in self.parameters and 
            self.parameters["account"].strip()):
            account_name = self.parameters["account"].strip()
            if not _is_valid_account_name(account_name):
                errors.append("Account name must follow Beancount format (e.g., Assets:Checking)")
        
        # Validate account names for SET_DESTINATION_ACCOUNT action
        if (self.action_type == ActionType.SET_DESTINATION_ACCOUNT and 
            "account" in self.parameters and 
            self.parameters["account"].strip()):
            account_name = self.parameters["account"].strip()
            if not _is_valid_account_name(account_name):
                errors.append("Account name must follow Beancount format (e.g., Assets:Checking)")
        
        return errors
    
    def to_action(self) -> Action:
        """Convert to enhanced rule system Action object.
        
        Returns:
            Action: Immutable action object for the rule engine
            
        Raises:
            ValueError: If the action data is incomplete or invalid
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ValueError(f"Cannot convert invalid action: {'; '.join(validation_errors)}")
        
        # Ensure action_type is not None (validation should have caught this)
        if self.action_type is None:
            raise ValueError("Action type cannot be None")
        
        # Clean parameters (strip whitespace)
        clean_parameters = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in self.parameters.items()
            if value and (not isinstance(value, str) or value.strip())
        }
        
        return Action(
            action_type=self.action_type,
            parameters=clean_parameters
        )
    
    @classmethod
    def from_action(cls, action: Action) -> 'ActionData':
        """Create ActionData from an existing Action object.
        
        Args:
            action: The Action object to convert from
            
        Returns:
            ActionData: Mutable UI data structure
        """
        return cls(
            action_type=action.action_type,
            parameters=action.parameters.copy()
        )
    
    def copy(self) -> 'ActionData':
        """Create a copy of this action data.
        
        Returns:
            ActionData: A new instance with the same values
        """
        return ActionData(
            action_type=self.action_type,
            parameters=self.parameters.copy()
        )
    
    def get_parameter_value(self, parameter_name: str) -> str:
        """Get a parameter value, returning empty string if not set.
        
        Args:
            parameter_name: The parameter name to get
            
        Returns:
            str: The parameter value or empty string
        """
        return self.parameters.get(parameter_name, "")
    
    def set_parameter_value(self, parameter_name: str, value: str) -> None:
        """Set a parameter value.
        
        Args:
            parameter_name: The parameter name to set
            value: The value to set
        """
        if value:
            self.parameters[parameter_name] = value
        elif parameter_name in self.parameters:
            del self.parameters[parameter_name]


# Field-to-operator mapping utilities

def get_string_operators() -> Set[Operator]:
    """Get operators valid for string fields.
    
    Returns:
        Set[Operator]: Set of operators for string fields
    """
    return {
        Operator.CONTAINS,
        Operator.EQUALS,
        Operator.STARTS_WITH,
        Operator.ENDS_WITH,
        Operator.REGEX_MATCH
    }


def get_numeric_operators() -> Set[Operator]:
    """Get operators valid for numeric fields.
    
    Returns:
        Set[Operator]: Set of operators for numeric fields
    """
    return {
        Operator.GREATER_THAN,
        Operator.LESS_THAN,
        Operator.GREATER_EQUAL,
        Operator.LESS_EQUAL,
        Operator.EQUAL,
        Operator.NOT_EQUAL
    }


def get_date_operators() -> Set[Operator]:
    """Get operators valid for date fields.
    
    Returns:
        Set[Operator]: Set of operators for date fields
    """
    return {
        Operator.BEFORE,
        Operator.AFTER,
        Operator.ON_DATE,
        Operator.EQUAL,
        Operator.NOT_EQUAL
    }


def get_operators_for_field(field: Field) -> List[Operator]:
    """Get valid operators for a specific field type.
    
    Args:
        field: The field to get operators for
        
    Returns:
        List[Operator]: List of valid operators for the field, sorted by common usage
    """
    if field in {Field.PAYEE, Field.NARRATION, Field.CURRENCY}:
        # String fields - order by common usage
        return [
            Operator.CONTAINS,
            Operator.EQUALS,
            Operator.STARTS_WITH,
            Operator.ENDS_WITH,
            Operator.REGEX_MATCH
        ]
    elif field == Field.AMOUNT:
        # Numeric field
        return [
            Operator.EQUAL,
            Operator.GREATER_THAN,
            Operator.LESS_THAN,
            Operator.GREATER_EQUAL,
            Operator.LESS_EQUAL,
            Operator.NOT_EQUAL
        ]
    elif field == Field.DATE:
        # Date field
        return [
            Operator.EQUAL,
            Operator.BEFORE,
            Operator.AFTER,
            Operator.ON_DATE,
            Operator.NOT_EQUAL
        ]
    else:
        return []


def get_operators_for_original_row() -> List[Operator]:
    """Get valid operators for original_row fields (treated as string fields).
    
    Returns:
        List[Operator]: List of valid operators for original_row fields
    """
    return [
        Operator.CONTAINS,
        Operator.EQUALS,
        Operator.STARTS_WITH,
        Operator.ENDS_WITH,
        Operator.REGEX_MATCH
    ]


def is_operator_valid_for_field(field: Field, operator: Operator) -> bool:
    """Check if an operator is valid for a specific field.
    
    Args:
        field: The field to check
        operator: The operator to validate
        
    Returns:
        bool: True if the operator is valid for the field
    """
    valid_operators = get_operators_for_field(field)
    return operator in valid_operators


def get_field_display_name(field: Field) -> str:
    """Get user-friendly display name for a field.
    
    Args:
        field: The field to get display name for
        
    Returns:
        str: Human-readable field name
    """
    display_names = {
        Field.PAYEE: "Payee",
        Field.NARRATION: "Narration",
        Field.AMOUNT: "Amount",
        Field.DATE: "Date",
        Field.CURRENCY: "Currency"
    }
    return display_names.get(field, field.value)


def get_operator_display_name(operator: Operator) -> str:
    """Get user-friendly display name for an operator.
    
    Args:
        operator: The operator to get display name for
        
    Returns:
        str: Human-readable operator name
    """
    display_names = {
        # String operators
        Operator.CONTAINS: "contains",
        Operator.EQUALS: "equals",
        Operator.STARTS_WITH: "starts with",
        Operator.ENDS_WITH: "ends with",
        Operator.REGEX_MATCH: "matches regex",
        
        # Numeric operators
        Operator.GREATER_THAN: "greater than",
        Operator.LESS_THAN: "less than",
        Operator.GREATER_EQUAL: "greater than or equal",
        Operator.LESS_EQUAL: "less than or equal",
        Operator.EQUAL: "equals",
        Operator.NOT_EQUAL: "not equal",
        
        # Date operators
        Operator.BEFORE: "before",
        Operator.AFTER: "after",
        Operator.ON_DATE: "on date"
    }
    return display_names.get(operator, operator.value)


# Action parameter utilities

def get_required_parameter_for_action(action_type: ActionType) -> Optional[str]:
    """Get the required parameter name for an action type.
    
    Args:
        action_type: The action type to get parameter for
        
    Returns:
        Optional[str]: The required parameter name, or None if no parameters required
    """
    parameter_map = {
        ActionType.SET_SOURCE_ACCOUNT: "account",
        ActionType.SET_DESTINATION_ACCOUNT: "account",
        ActionType.SET_PAYEE: "payee",
        ActionType.ADD_TAG: "tag",
        ActionType.SET_NARRATION: "narration",
        ActionType.APPEND_NARRATION: "text"
    }
    return parameter_map.get(action_type)


def get_parameter_placeholder(action_type: ActionType) -> str:
    """Get placeholder text for action parameter input.
    
    Args:
        action_type: The action type to get placeholder for
        
    Returns:
        str: Placeholder text for the parameter input
    """
    placeholders = {
        ActionType.SET_SOURCE_ACCOUNT: "Account name (e.g., Assets:Checking)",
        ActionType.SET_DESTINATION_ACCOUNT: "Account name (e.g., Expenses:Groceries)",
        ActionType.SET_PAYEE: "Payee name",
        ActionType.ADD_TAG: "Tag name",
        ActionType.SET_NARRATION: "New narration text",
        ActionType.APPEND_NARRATION: "Text to append"
    }
    return placeholders.get(action_type, "Parameter value")


def get_parameter_display_name(parameter_name: str) -> str:
    """Get user-friendly display name for a parameter.
    
    Args:
        parameter_name: The parameter name to get display name for
        
    Returns:
        str: Human-readable parameter name
    """
    display_names = {
        "account": "Account",
        "payee": "Payee",
        "tag": "Tag",
        "narration": "Narration",
        "text": "Text"
    }
    return display_names.get(parameter_name, parameter_name.title())


def get_action_display_name(action_type: ActionType) -> str:
    """Get user-friendly display name for an action type.
    
    Args:
        action_type: The action type to get display name for
        
    Returns:
        str: Human-readable action type name
    """
    display_names = {
        ActionType.SET_SOURCE_ACCOUNT: "Set Source Account",
        ActionType.SET_DESTINATION_ACCOUNT: "Set Destination Account",
        ActionType.SET_PAYEE: "Set Payee",
        ActionType.ADD_TAG: "Add Tag",
        ActionType.SET_NARRATION: "Set Narration",
        ActionType.APPEND_NARRATION: "Append Narration"
    }
    return display_names.get(action_type, action_type.value)


# Validation utilities

def _is_valid_account_name(account_name: str) -> bool:
    """Validate that an account name follows Beancount format.
    
    Args:
        account_name: The account name to validate
        
    Returns:
        bool: True if the account name is valid
    """
    if not account_name or not account_name.strip():
        return False
    
    # Basic Beancount account validation
    # Must start with a capital letter and contain at least one colon
    parts = account_name.split(':')
    if len(parts) < 2:
        return False
    
    for part in parts:
        if not part or not part[0].isupper():
            return False
        # Check that part contains only letters, numbers, and hyphens
        if not all(c.isalnum() or c in '-_' for c in part):
            return False
    
    return True


# Conversion utilities for complete rule data

def create_conditions_block_from_ui_data(
    logical_operator: LogicalOperator,
    conditions_data: List[ConditionData]
) -> ConditionsBlock:
    """Create a ConditionsBlock from UI condition data.
    
    Args:
        logical_operator: The logical operator (ALL/ANY)
        conditions_data: List of condition data from UI
        
    Returns:
        ConditionsBlock: Immutable conditions block for rule engine
        
    Raises:
        ValueError: If any condition data is invalid
    """
    if not conditions_data:
        raise ValueError("At least one condition is required")
    
    conditions = []
    for i, condition_data in enumerate(conditions_data):
        try:
            conditions.append(condition_data.to_condition())
        except ValueError as e:
            raise ValueError(f"Condition {i+1} is invalid: {e}")
    
    return ConditionsBlock(
        operator=logical_operator,
        conditions=conditions
    )


def create_actions_from_ui_data(actions_data: List[ActionData]) -> List[Action]:
    """Create Action objects from UI action data.
    
    Args:
        actions_data: List of action data from UI
        
    Returns:
        List[Action]: List of immutable action objects for rule engine
        
    Raises:
        ValueError: If any action data is invalid
    """
    if not actions_data:
        raise ValueError("At least one action is required")
    
    actions = []
    for i, action_data in enumerate(actions_data):
        try:
            actions.append(action_data.to_action())
        except ValueError as e:
            raise ValueError(f"Action {i+1} is invalid: {e}")
    
    return actions


def validate_rule_ui_data(
    name: str,
    logical_operator: LogicalOperator,
    conditions_data: List[ConditionData],
    actions_data: List[ActionData]
) -> List[str]:
    """Validate complete rule data from UI.
    
    Args:
        name: Rule name
        logical_operator: Logical operator for conditions
        conditions_data: List of condition data
        actions_data: List of action data
        
    Returns:
        List[str]: List of validation error messages (empty if valid)
    """
    errors = []
    
    # Validate name
    if not name or not name.strip():
        errors.append("Rule name is required")
    
    # Validate conditions
    if not conditions_data:
        errors.append("At least one condition is required")
    else:
        for i, condition_data in enumerate(conditions_data):
            condition_errors = condition_data.validate()
            for error in condition_errors:
                errors.append(f"Condition {i+1}: {error}")
    
    # Validate actions
    if not actions_data:
        errors.append("At least one action is required")
    else:
        for i, action_data in enumerate(actions_data):
            action_errors = action_data.validate()
            for error in action_errors:
                errors.append(f"Action {i+1}: {error}")
    
    return errors