"""
Data structures and enums for the advanced rule engine.

This module defines the new data structures that support complex conditions,
logical operators, multiple actions, and rule metadata for the refactored
transaction rule engine.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.data import TransactionData


class Field(Enum):
    """Transaction fields that can be used in conditions."""
    PAYEE = "payee"
    NARRATION = "narration"
    AMOUNT = "amount"
    DATE = "date"
    CURRENCY = "currency"


class Operator(Enum):
    """Comparison operators for condition evaluation."""
    # String operators
    CONTAINS = "contains"
    EQUALS = "equals"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX_MATCH = "regex_match"
    
    # Numeric operators
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    
    # Date operators
    BEFORE = "before"
    AFTER = "after"
    ON_DATE = "on_date"


class LogicalOperator(Enum):
    """Logical operators for combining conditions."""
    ALL = "all"  # AND logic
    ANY = "any"  # OR logic


class ActionType(Enum):
    """Types of actions that can be performed on transactions."""
    SET_SOURCE_ACCOUNT = "set_source_account"
    SET_DESTINATION_ACCOUNT = "set_destination_account"
    SET_PAYEE = "set_payee"
    ADD_TAG = "add_tag"
    SET_NARRATION = "set_narration"
    APPEND_NARRATION = "append_narration"


@dataclass(frozen=True)
class Condition:
    """Individual condition for transaction matching.
    
    This immutable dataclass represents a single condition that can be
    evaluated against a transaction. It includes field validation and
    type-safe matching logic.
    
    Attributes:
        field: The transaction field to match against (None for original_row fields)
        operator: The comparison operator to use
        value: The value to compare with (as string, will be converted as needed)
        case_sensitive: Whether string comparisons should be case-sensitive
        original_row_key: Key from original_row metadata (required when field is None)
    """
    field: Optional[Field]
    operator: Operator
    value: str
    case_sensitive: bool = False
    original_row_key: Optional[str] = None
    
    def __post_init__(self):
        """Validate condition parameters after initialization.
        
        Raises:
            ValueError: If field/operator combination is invalid or value is empty
            TypeError: If field or operator are not proper enum values
        """
        if self.field is not None and not isinstance(self.field, Field):
            raise TypeError("field must be a Field enum value or None")
        
        if not isinstance(self.operator, Operator):
            raise TypeError("operator must be an Operator enum value")
        
        if not self.value or not self.value.strip():
            raise ValueError("value cannot be empty")
        
        # Validate original_row_key requirement
        if self.field is None and (not self.original_row_key or not self.original_row_key.strip()):
            raise ValueError("original_row_key is required when field is None (for original row conditions)")
        
        # Validate field/operator compatibility
        self._validate_field_operator_compatibility()
        
        # Validate regex patterns if using regex operator
        if self.operator == Operator.REGEX_MATCH:
            try:
                re.compile(self.value)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{self.value}': {e}")
    
    def _validate_field_operator_compatibility(self) -> None:
        """Validate that the operator is compatible with the field type.
        
        Raises:
            ValueError: If the field/operator combination is invalid
        """
        string_fields = {Field.PAYEE, Field.NARRATION, Field.CURRENCY}
        numeric_fields = {Field.AMOUNT}
        date_fields = {Field.DATE}
        
        string_operators = {
            Operator.CONTAINS, Operator.EQUALS, Operator.STARTS_WITH,
            Operator.ENDS_WITH, Operator.REGEX_MATCH
        }
        numeric_operators = {
            Operator.GREATER_THAN, Operator.LESS_THAN, Operator.GREATER_EQUAL,
            Operator.LESS_EQUAL, Operator.EQUAL, Operator.NOT_EQUAL
        }
        date_operators = {
            Operator.BEFORE, Operator.AFTER, Operator.ON_DATE,
            Operator.EQUAL, Operator.NOT_EQUAL
        }
        
        # For original_row fields (field=None), treat as string fields
        if self.field is None:
            if self.operator not in string_operators:
                raise ValueError(f"Operator {self.operator.value} is not compatible with original row fields (string type)")
            return
        
        if self.field in string_fields and self.operator not in string_operators:
            raise ValueError(f"Operator {self.operator.value} is not compatible with string field {self.field.value}")
        
        if self.field in numeric_fields and self.operator not in numeric_operators:
            raise ValueError(f"Operator {self.operator.value} is not compatible with numeric field {self.field.value}")
        
        if self.field in date_fields and self.operator not in date_operators:
            raise ValueError(f"Operator {self.operator.value} is not compatible with date field {self.field.value}")
    
    def matches(self, transaction: "TransactionData") -> bool:
        """Evaluate this condition against a transaction.
        
        Args:
            transaction: The transaction to evaluate against
            
        Returns:
            bool: True if the condition matches, False otherwise
        """
        if not transaction:
            return False
        
        try:
            field_value = self._extract_field_value(transaction)
            if field_value is None:
                return False
            
            return self._evaluate_condition(field_value)
        except Exception:
            # If any error occurs during evaluation, condition doesn't match
            return False
    
    def _extract_field_value(self, transaction: "TransactionData") -> Optional[Union[str, Decimal, date]]:
        """Extract the field value from a transaction.
        
        Args:
            transaction: The transaction to extract from
            
        Returns:
            The field value or None if field doesn't exist or is empty
        """
        if self.field == Field.PAYEE:
            return transaction.payee if transaction.payee else None
        elif self.field == Field.NARRATION:
            return transaction.narration if transaction.narration else None
        elif self.field == Field.AMOUNT:
            return transaction.amount
        elif self.field == Field.DATE:
            return transaction.date
        elif self.field == Field.CURRENCY:
            return transaction.currency if transaction.currency else None
        elif self.field is None and self.original_row_key is not None:
            # Extract value from original_row metadata
            if not transaction.metadata or 'original_row' not in transaction.metadata:
                return None
            
            original_row = transaction.metadata['original_row']
            if not isinstance(original_row, dict):
                return None
            
            value = original_row.get(self.original_row_key)
            return str(value) if value is not None else None
        
        return None
    
    def _evaluate_condition(self, field_value: Union[str, Decimal, date]) -> bool:
        """Evaluate the condition against the extracted field value.
        
        Args:
            field_value: The value extracted from the transaction
            
        Returns:
            bool: True if the condition matches, False otherwise
        """
        if isinstance(field_value, str):
            return self._evaluate_string_condition(field_value)
        elif isinstance(field_value, Decimal):
            return self._evaluate_numeric_condition(field_value)
        elif isinstance(field_value, date):
            return self._evaluate_date_condition(field_value)
        
        return False
    
    def _evaluate_string_condition(self, field_value: str) -> bool:
        """Evaluate string-based conditions.
        
        Args:
            field_value: The string value from the transaction
            
        Returns:
            bool: True if the condition matches, False otherwise
        """
        if not self.case_sensitive:
            field_value = field_value.lower()
            condition_value = self.value.lower()
        else:
            condition_value = self.value
        
        if self.operator == Operator.CONTAINS:
            return condition_value in field_value
        elif self.operator == Operator.EQUALS:
            return condition_value == field_value
        elif self.operator == Operator.STARTS_WITH:
            return field_value.startswith(condition_value)
        elif self.operator == Operator.ENDS_WITH:
            return field_value.endswith(condition_value)
        elif self.operator == Operator.REGEX_MATCH:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            return bool(re.search(self.value, field_value, flags))
        
        return False
    
    def _evaluate_numeric_condition(self, field_value: Decimal) -> bool:
        """Evaluate numeric-based conditions.
        
        Args:
            field_value: The numeric value from the transaction
            
        Returns:
            bool: True if the condition matches, False otherwise
        """
        try:
            condition_value = Decimal(self.value)
        except (ValueError, TypeError):
            return False
        
        if self.operator == Operator.GREATER_THAN:
            return field_value > condition_value
        elif self.operator == Operator.LESS_THAN:
            return field_value < condition_value
        elif self.operator == Operator.GREATER_EQUAL:
            return field_value >= condition_value
        elif self.operator == Operator.LESS_EQUAL:
            return field_value <= condition_value
        elif self.operator == Operator.EQUAL:
            return field_value == condition_value
        elif self.operator == Operator.NOT_EQUAL:
            return field_value != condition_value
        
        return False
    
    def _evaluate_date_condition(self, field_value: date) -> bool:
        """Evaluate date-based conditions.
        
        Args:
            field_value: The date value from the transaction
            
        Returns:
            bool: True if the condition matches, False otherwise
        """
        try:
            # Try to parse as ISO date format first
            if 'T' in self.value or ' ' in self.value:
                # Handle datetime strings by extracting date part
                date_part = self.value.split('T')[0].split(' ')[0]
                condition_value = datetime.fromisoformat(date_part).date()
            else:
                condition_value = datetime.fromisoformat(self.value).date()
        except (ValueError, TypeError):
            return False
        
        if self.operator == Operator.BEFORE:
            return field_value < condition_value
        elif self.operator == Operator.AFTER:
            return field_value > condition_value
        elif self.operator == Operator.ON_DATE:
            return field_value == condition_value
        elif self.operator == Operator.EQUAL:
            return field_value == condition_value
        elif self.operator == Operator.NOT_EQUAL:
            return field_value != condition_value
        
        return False


@dataclass(frozen=True)
class ConditionsBlock:
    """Block of conditions with logical operator.
    
    This immutable dataclass supports nested logical operations with
    short-circuit evaluation for performance optimization.
    
    Attributes:
        operator: The logical operator (ALL/ANY) for combining conditions
        conditions: List of individual conditions
        nested_blocks: List of nested ConditionsBlocks for complex logic
    """
    operator: LogicalOperator
    conditions: List[Condition] = field(default_factory=list)
    nested_blocks: List['ConditionsBlock'] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate the conditions block after initialization.
        
        Raises:
            ValueError: If the block is empty or operator is invalid
            TypeError: If operator is not a LogicalOperator enum value
        """
        if not isinstance(self.operator, LogicalOperator):
            raise TypeError("operator must be a LogicalOperator enum value")
        
        if not self.conditions and not self.nested_blocks:
            raise ValueError("ConditionsBlock must contain at least one condition or nested block")
        
        # Validate all conditions
        for condition in self.conditions:
            if not isinstance(condition, Condition):
                raise TypeError("All conditions must be Condition instances")
        
        # Validate all nested blocks
        for block in self.nested_blocks:
            if not isinstance(block, ConditionsBlock):
                raise TypeError("All nested blocks must be ConditionsBlock instances")
    
    def matches(self, transaction: "TransactionData") -> bool:
        """Evaluate all conditions using the logical operator.
        
        This method implements short-circuit evaluation for performance:
        - For ALL (AND): returns False as soon as any condition fails
        - For ANY (OR): returns True as soon as any condition succeeds
        
        Args:
            transaction: The transaction to evaluate against
            
        Returns:
            bool: True if the logical combination of conditions matches
        """
        if not transaction:
            return False
        
        if self.operator == LogicalOperator.ALL:
            # ALL (AND) logic with short-circuit evaluation
            for condition in self.conditions:
                if not condition.matches(transaction):
                    return False
            
            for nested_block in self.nested_blocks:
                if not nested_block.matches(transaction):
                    return False
            
            return True
        
        elif self.operator == LogicalOperator.ANY:
            # ANY (OR) logic with short-circuit evaluation
            for condition in self.conditions:
                if condition.matches(transaction):
                    return True
            
            for nested_block in self.nested_blocks:
                if nested_block.matches(transaction):
                    return True
            
            return False
        
        return False


@dataclass(frozen=True)
class Action:
    """Action to perform when rule matches.
    
    This immutable dataclass represents an action that can be executed
    on a transaction when a rule matches. It includes parameter validation
    and execution delegation.
    
    Attributes:
        action_type: The type of action to perform
        parameters: Dictionary of parameters for the action
    """
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate action parameters after initialization.
        
        Raises:
            ValueError: If required parameters are missing or invalid
            TypeError: If action_type is not an ActionType enum value
        """
        if not isinstance(self.action_type, ActionType):
            raise TypeError("action_type must be an ActionType enum value")
        
        # Validate parameters based on action type
        self._validate_parameters()
    
    def _validate_parameters(self) -> None:
        """Validate that required parameters are present for the action type.
        
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if self.action_type == ActionType.SET_DESTINATION_ACCOUNT:
            if "account" not in self.parameters:
                raise ValueError("SET_DESTINATION_ACCOUNT action requires 'account' parameter")
            if not self.parameters["account"] or not str(self.parameters["account"]).strip():
                raise ValueError("SET_DESTINATION_ACCOUNT action requires non-empty 'account' parameter")
        
        elif self.action_type == ActionType.SET_PAYEE:
            if "payee" not in self.parameters:
                raise ValueError("SET_PAYEE action requires 'payee' parameter")
            # Allow empty payee for clearing
        
        elif self.action_type == ActionType.ADD_TAG:
            if "tag" not in self.parameters:
                raise ValueError("ADD_TAG action requires 'tag' parameter")
            if not self.parameters["tag"] or not str(self.parameters["tag"]).strip():
                raise ValueError("ADD_TAG action requires non-empty 'tag' parameter")
        
        elif self.action_type == ActionType.SET_NARRATION:
            if "narration" not in self.parameters:
                raise ValueError("SET_NARRATION action requires 'narration' parameter")
            # Allow empty narration for clearing
        
        elif self.action_type == ActionType.APPEND_NARRATION:
            if "text" not in self.parameters:
                raise ValueError("APPEND_NARRATION action requires 'text' parameter")
            if not self.parameters["text"] or not str(self.parameters["text"]).strip():
                raise ValueError("APPEND_NARRATION action requires non-empty 'text' parameter")
    
