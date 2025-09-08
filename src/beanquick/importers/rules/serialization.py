"""
Rule serialization utilities for converting TransactionRule objects to/from dictionary format.

This module provides standalone functions for serializing and deserializing transaction
rules, with comprehensive validation and error handling. These utilities support the
SQLite-based persistence system by providing reliable data conversion between domain
objects and storage representations.

Enhanced to support complex nested structures including ConditionsBlock and Action lists
for the advanced rule engine. Key features include:

- Support for standard transaction field conditions (using Field enum)
- Support for original CSV row data conditions (using original_row_key)
- Comprehensive validation for both condition types
- Proper handling of field/operator compatibility
- Case-sensitive string matching options
- Regex pattern validation for regex operators

The serialization format maintains backward compatibility while extending support
for the new original_row_key functionality, allowing rules to reference any column
from the original CSV import data.
"""

from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import logging
from datetime import datetime
from typing import Dict, Any

from beanquick.importers.rules import TransactionRule
from beanquick.importers.rules.rule_components import (
    ConditionsBlock, Condition, Action, Field, Operator, LogicalOperator, ActionType
)

logger = logging.getLogger(__name__)


def condition_to_dict(condition: Condition) -> Dict[str, Any]:
    """Convert Condition to dictionary for serialization.
    
    Serializes both standard field conditions and original_row_key conditions
    to a dictionary format suitable for data persistence. The function handles
    the dual nature of conditions where either 'field' (for standard transaction
    fields) or 'original_row_key' (for CSV column references) is populated.
    
    Args:
        condition: Condition object to convert
        
    Returns:
        Dictionary representation of the condition with keys:
        - field: Field enum value (or None for original_row conditions)
        - operator: Operator enum value
        - value: String value to compare against
        - case_sensitive: Boolean flag for string comparison behavior
        - original_row_key: CSV column key (or None for standard field conditions)
        
    Raises:
        ValueError: If condition is None or invalid
        TypeError: If condition is not a Condition instance
    """
    if condition is None:
        raise ValueError("Condition cannot be None")
    
    if not isinstance(condition, Condition):
        raise TypeError("Expected Condition instance")
    
    return {
        "field": condition.field.value if condition.field is not None else None,
        "operator": condition.operator.value,
        "value": condition.value,
        "case_sensitive": condition.case_sensitive,
        "original_row_key": condition.original_row_key
    }


def dict_to_condition(data: Dict[str, Any]) -> Condition:
    """Convert dictionary to Condition object.
    
    Deserializes condition data from dictionary format, supporting both standard
    field conditions and original_row_key conditions. The function validates
    that exactly one of 'field' or 'original_row_key' is specified, ensuring
    proper condition type identification.
    
    Expected dictionary format:
    {
        "field": "field_enum_value" or None,
        "operator": "operator_enum_value", 
        "value": "comparison_value",
        "case_sensitive": boolean (optional, defaults to False),
        "original_row_key": "csv_column_name" or None
    }
    
    Args:
        data: Dictionary containing condition data
        
    Returns:
        Condition object created from the dictionary data
        
    Raises:
        ValueError: If data is invalid, missing required fields, or has
                   both field and original_row_key specified
        TypeError: If data is not a dictionary
    """
    if data is None:
        raise ValueError("Condition data cannot be None")
    
    if not isinstance(data, dict):
        raise TypeError("Expected dictionary for condition data")
    
    # Validate required fields - note that field can be None for original_row conditions
    required_fields = ["operator", "value"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Condition data missing required fields: {missing_fields}")
    
    # Check that we have either field or original_row_key
    if "field" not in data and "original_row_key" not in data:
        raise ValueError("Condition data must have either 'field' or 'original_row_key'")
    
    try:
        # Parse field enum (can be None for original_row conditions)
        field_enum = None
        if "field" in data and data["field"] is not None:
            try:
                field_enum = Field(data["field"])
            except ValueError as e:
                raise ValueError(f"Invalid field '{data['field']}': {e}") from e
        
        # Parse operator enum
        try:
            operator_enum = Operator(data["operator"])
        except ValueError as e:
            raise ValueError(f"Invalid operator '{data['operator']}': {e}") from e
        
        # Parse case_sensitive flag (default to False)
        case_sensitive = data.get("case_sensitive", False)
        if not isinstance(case_sensitive, bool):
            raise ValueError(f"case_sensitive must be a boolean, got {type(case_sensitive)}")
        
        # Parse original_row_key (optional)
        original_row_key = data.get("original_row_key")
        if original_row_key is not None and not isinstance(original_row_key, str):
            raise ValueError("original_row_key must be a string or None")
        
        # Validate value
        if not isinstance(data["value"], str):
            raise ValueError("value must be a string")
        
        return Condition(
            field=field_enum,
            operator=operator_enum,
            value=data["value"],
            case_sensitive=case_sensitive,
            original_row_key=original_row_key
        )
        
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.error(f"Failed to deserialize condition data: {e}", exc_info=True)
        raise ValueError(f"Failed to deserialize condition data: {e}") from e


def conditions_block_to_dict(block: ConditionsBlock) -> Dict[str, Any]:
    """Convert ConditionsBlock to dictionary for serialization.
    
    Serializes a complex conditions block including all nested conditions
    and sub-blocks. This supports the hierarchical logical structure where
    conditions can be grouped with AND/OR operators and nested arbitrarily deep.
    
    Args:
        block: ConditionsBlock object to convert
        
    Returns:
        Dictionary representation with keys:
        - operator: LogicalOperator enum value (AND/OR)
        - conditions: List of condition dictionaries
        - nested_blocks: List of nested ConditionsBlock dictionaries
        
    Raises:
        ValueError: If block is None or invalid
        TypeError: If block is not a ConditionsBlock instance
    """
    if block is None:
        raise ValueError("ConditionsBlock cannot be None")
    
    if not isinstance(block, ConditionsBlock):
        raise TypeError("Expected ConditionsBlock instance")
    
    return {
        "operator": block.operator.value,
        "conditions": [condition_to_dict(condition) for condition in block.conditions],
        "nested_blocks": [conditions_block_to_dict(nested_block) for nested_block in block.nested_blocks]
    }


def dict_to_conditions_block(data: Dict[str, Any]) -> ConditionsBlock:
    """Convert dictionary to ConditionsBlock object.
    
    Deserializes a hierarchical conditions block from dictionary format,
    recursively processing all nested conditions and sub-blocks. This supports
    complex logical structures with arbitrary nesting depth.
    
    Expected dictionary format:
    {
        "operator": "logical_operator_value" (AND/OR),
        "conditions": [list of condition dictionaries],
        "nested_blocks": [list of nested ConditionsBlock dictionaries]
    }
    
    Args:
        data: Dictionary containing conditions block data
        
    Returns:
        ConditionsBlock object created from the dictionary data
        
    Raises:
        ValueError: If data is invalid, missing required fields, or contains
                   invalid nested structures
        TypeError: If data is not a dictionary
    """
    if data is None:
        raise ValueError("ConditionsBlock data cannot be None")
    
    if not isinstance(data, dict):
        raise TypeError("Expected dictionary for conditions block data")
    
    # Validate required fields
    if "operator" not in data:
        raise ValueError("ConditionsBlock data missing required field: operator")
    
    try:
        # Parse logical operator enum
        try:
            operator_enum = LogicalOperator(data["operator"])
        except ValueError as e:
            raise ValueError(f"Invalid logical operator '{data['operator']}': {e}") from e
        
        # Parse conditions list (default to empty)
        conditions_data = data.get("conditions", [])
        if not isinstance(conditions_data, list):
            raise ValueError("conditions must be a list")
        
        conditions = []
        for i, condition_data in enumerate(conditions_data):
            try:
                condition = dict_to_condition(condition_data)
                conditions.append(condition)
            except Exception as e:
                raise ValueError(f"Failed to parse condition at index {i}: {e}") from e
        
        # Parse nested blocks list (default to empty)
        nested_blocks_data = data.get("nested_blocks", [])
        if not isinstance(nested_blocks_data, list):
            raise ValueError("nested_blocks must be a list")
        
        nested_blocks = []
        for i, block_data in enumerate(nested_blocks_data):
            try:
                nested_block = dict_to_conditions_block(block_data)
                nested_blocks.append(nested_block)
            except Exception as e:
                raise ValueError(f"Failed to parse nested block at index {i}: {e}") from e
        
        return ConditionsBlock(
            operator=operator_enum,
            conditions=conditions,
            nested_blocks=nested_blocks
        )
        
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.error(f"Failed to deserialize conditions block data: {e}", exc_info=True)
        raise ValueError(f"Failed to deserialize conditions block data: {e}") from e


def action_to_dict(action: Action) -> Dict[str, Any]:
    """Convert Action to dictionary for serialization.
    
    Serializes an action object to dictionary format suitable for data persistence.
    Actions define what modifications to apply to transactions when rule conditions
    are met (e.g., setting payee, adding narration, etc.).
    
    Args:
        action: Action object to convert
        
    Returns:
        Dictionary representation with keys:
        - action_type: ActionType enum value
        - parameters: Dictionary of action-specific parameters
        
    Raises:
        ValueError: If action is None or invalid
        TypeError: If action is not an Action instance
    """
    if action is None:
        raise ValueError("Action cannot be None")
    
    if not isinstance(action, Action):
        raise TypeError("Expected Action instance")
    
    return {
        "action_type": action.action_type.value,
        "parameters": action.parameters.copy()  # Create a copy to avoid mutation
    }


def dict_to_action(data: Dict[str, Any]) -> Action:
    """Convert dictionary to Action object.
    
    Deserializes action data from dictionary format. Actions specify what
    modifications to apply to transactions when rule conditions match.
    
    Expected dictionary format:
    {
        "action_type": "action_type_enum_value",
        "parameters": {action-specific parameters dictionary}
    }
    
    Args:
        data: Dictionary containing action data
        
    Returns:
        Action object created from the dictionary data
        
    Raises:
        ValueError: If data is invalid or missing required fields
        TypeError: If data is not a dictionary
    """
    if data is None:
        raise ValueError("Action data cannot be None")
    
    if not isinstance(data, dict):
        raise TypeError("Expected dictionary for action data")
    
    # Validate required fields
    if "action_type" not in data:
        raise ValueError("Action data missing required field: action_type")
    
    try:
        # Parse action type enum
        try:
            action_type_enum = ActionType(data["action_type"])
        except ValueError as e:
            raise ValueError(f"Invalid action type '{data['action_type']}': {e}") from e
        
        # Parse parameters (default to empty dict)
        parameters = data.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be a dictionary")
        
        return Action(
            action_type=action_type_enum,
            parameters=parameters
        )
        
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.error(f"Failed to deserialize action data: {e}", exc_info=True)
        raise ValueError(f"Failed to deserialize action data: {e}") from e


def rule_to_dict(rule: TransactionRule) -> Dict[str, Any]:
    """Convert TransactionRule to dictionary for data serialization.
    
    This function converts a complete TransactionRule object into a dictionary format
    suitable for data persistence. It handles the full complexity of the enhanced
    rule system including:
    
    - Complex nested ConditionsBlock structures with logical operators
    - Mixed condition types (standard fields and original_row_key references)
    - Multiple action lists with various action types
    - Rule metadata including application statistics and timestamps
    
    The serialized format preserves all rule information while maintaining
    structured data format for storage and retrieval operations.
    
    Args:
        rule: TransactionRule object to convert
        
    Returns:
        Dictionary representation of the rule with ISO-formatted dates and
        complete nested structure preservation
        
    Raises:
        ValueError: If rule is None or invalid
        TypeError: If rule is not a TransactionRule instance
    """
    if rule is None:
        raise ValueError("Rule cannot be None")
    
    if not isinstance(rule, TransactionRule):
        raise TypeError("Expected TransactionRule instance")
    
    try:
        result = {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "is_enabled": rule.is_enabled,
            "stop_processing": rule.stop_processing,
            "created_date": rule.created_date.isoformat(),
            "last_applied": rule.last_applied.isoformat() if rule.last_applied else None,
            "application_count": rule.application_count
        }
        
        # Serialize conditions_block if present
        if rule.conditions_block is not None:
            result["conditions_block"] = conditions_block_to_dict(rule.conditions_block)
        else:
            result["conditions_block"] = None
        
        # Serialize actions list
        result["actions"] = [action_to_dict(action) for action in rule.actions]
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to serialize rule {rule.rule_id}: {e}", exc_info=True)
        raise ValueError(f"Failed to serialize rule: {e}") from e


def dict_to_rule(data: Dict[str, Any]) -> TransactionRule:
    """Convert dictionary to TransactionRule.
    
    This function converts a dictionary back into a complete TransactionRule object. 
    It provides comprehensive validation for the enhanced rule system including:
    
    - Nested ConditionsBlock structures with recursive validation
    - Mixed condition types supporting both standard fields and original_row_key
    - Multiple action lists with parameter validation  
    - Rule metadata with proper type conversion and date parsing
    - Backward compatibility with existing rule formats
    
    The function performs extensive validation to ensure data integrity and
    provides detailed error messages for debugging configuration issues.
    
    Expected dictionary format includes all rule components:
    - Basic metadata (rule_id, name, is_enabled, etc.)
    - Complex conditions_block with nested structure
    - Actions list with type-specific parameters
    - Timestamps and application statistics
    
    Args:
        data: Dictionary containing rule data
        
    Returns:
        TransactionRule object created from the dictionary data with full
        validation and proper type conversion
        
    Raises:
        ValueError: If data is invalid, missing required fields, contains
                   invalid nested structures, or has malformed dates
        TypeError: If data is not a dictionary or contains incorrect types
    """
    if data is None:
        raise ValueError("Rule data cannot be None")
    
    if not isinstance(data, dict):
        raise TypeError("Expected dictionary for rule data")
    
    required_fields = ["rule_id", "created_date"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Rule data missing required fields: {missing_fields}")
    
    try:
        # Parse rule_id
        rule_id = data["rule_id"]
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ValueError("rule_id must be a non-empty string")
        
        # Parse name (optional, default to empty string)
        name = data.get("name", "")
        if not isinstance(name, str):
            raise ValueError("name must be a string")
        
        # Parse is_enabled (optional, default to True)
        is_enabled = data.get("is_enabled", True)
        if not isinstance(is_enabled, bool):
            raise ValueError("is_enabled must be a boolean")
        
        # Parse stop_processing (optional, default to False)
        stop_processing = data.get("stop_processing", False)
        if not isinstance(stop_processing, bool):
            raise ValueError("stop_processing must be a boolean")
        
        # Parse created date
        try:
            created_date_value = data["created_date"]
            if isinstance(created_date_value, datetime):
                created_date = created_date_value
            elif isinstance(created_date_value, str):
                created_date = datetime.fromisoformat(created_date_value)
            else:
                raise ValueError(f"created_date must be datetime or string, got {type(created_date_value)}")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid created_date '{data['created_date']}': {e}") from e
        
        # Parse last_applied date (optional)
        last_applied = None
        if data.get("last_applied"):
            try:
                last_applied_value = data["last_applied"]
                if isinstance(last_applied_value, datetime):
                    last_applied = last_applied_value
                elif isinstance(last_applied_value, str):
                    last_applied = datetime.fromisoformat(last_applied_value)
                else:
                    raise ValueError(f"last_applied must be datetime or string, got {type(last_applied_value)}")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid last_applied '{data['last_applied']}': {e}") from e
        
        # Parse application count
        application_count = data.get("application_count", 0)
        if not isinstance(application_count, int):
            try:
                application_count = int(application_count)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid application_count '{application_count}': {e}") from e
        
        if application_count < 0:
            raise ValueError(f"application_count cannot be negative: {application_count}")
        
        # Parse conditions_block (optional)
        conditions_block = None
        if "conditions_block" in data and data["conditions_block"] is not None:
            try:
                conditions_block = dict_to_conditions_block(data["conditions_block"])
            except Exception as e:
                raise ValueError(f"Failed to parse conditions_block: {e}") from e
        
        # Parse actions list (optional, default to empty list)
        actions_data = data.get("actions", [])
        if not isinstance(actions_data, list):
            raise ValueError("actions must be a list")
        
        actions = []
        for i, action_data in enumerate(actions_data):
            try:
                action = dict_to_action(action_data)
                actions.append(action)
            except Exception as e:
                raise ValueError(f"Failed to parse action at index {i}: {e}") from e
        
        return TransactionRule(
            rule_id=rule_id.strip(),
            name=name.strip(),
            is_enabled=is_enabled,
            stop_processing=stop_processing,
            conditions_block=conditions_block,
            actions=actions,
            created_date=created_date,
            last_applied=last_applied,
            application_count=application_count
        )
        
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.error(f"Failed to deserialize rule data: {e}", exc_info=True)
        raise ValueError(f"Failed to deserialize rule data: {e}") from e
