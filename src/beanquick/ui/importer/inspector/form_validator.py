"""
FormValidator with optimized validation rules for reactive form architecture.

This module provides a comprehensive validation system with field dependency optimization,
priority-based rule execution, and detailed error reporting for the inspector panel.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any
import re

logger = logging.getLogger(__name__)


class ValidationErrorType(Enum):
    """Types of validation errors for categorization and styling."""
    REQUIRED_FIELD = "required_field"
    INVALID_FORMAT = "invalid_format"
    BUSINESS_RULE = "business_rule"
    ACCOUNT_VALIDATION = "account_validation"
    AMOUNT_VALIDATION = "amount_validation"


@dataclass
class ValidationError:
    """Detailed validation error with field context and suggestions."""
    field_name: str
    error_type: ValidationErrorType
    message: str
    suggestion: Optional[str] = None
    error_code: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.field_name}: {self.message}"


@dataclass
class ValidationWarning:
    """Non-blocking validation warning with suggestions."""
    field_name: str
    message: str
    suggestion: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.field_name}: {self.message}"


@dataclass
class ValidationSuggestion:
    """Actionable suggestion for improving form data."""
    field_name: str
    suggestion: str
    action_type: str = "improvement"  # improvement, correction, optimization
    
    def __str__(self) -> str:
        return f"{self.field_name}: {self.suggestion}"


@dataclass
class ValidationResult:
    """Comprehensive validation result with detailed error reporting and suggestions.
    
    The data_id field is used to track which data object this result belongs to,
    preventing validation results from one TransactionDisplayData from being
    incorrectly reused for another TransactionDisplayData during incremental validation.
    """
    is_valid: bool
    field_errors: Dict[str, List[ValidationError]] = field(default_factory=dict)
    global_errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    suggestions: List[ValidationSuggestion] = field(default_factory=list)
    data_id: Optional[str] = None  # ID of the data object this result belongs to
    
    def has_errors_for_field(self, field_name: str) -> bool:
        """Check if there are validation errors for a specific field.
        
        Args:
            field_name: Name of the field to check
            
        Returns:
            bool: True if the field has validation errors
        """
        return field_name in self.field_errors and len(self.field_errors[field_name]) > 0
    
    def get_field_errors(self, field_name: str) -> List[ValidationError]:
        """Get all validation errors for a specific field.
        
        Args:
            field_name: Name of the field
            
        Returns:
            List[ValidationError]: List of errors for the field
        """
        return self.field_errors.get(field_name, [])
    
    def get_all_errors(self) -> List[ValidationError]:
        """Get all validation errors (field-specific and global).
        
        Returns:
            List[ValidationError]: All validation errors
        """
        all_errors = self.global_errors.copy()
        for field_errors in self.field_errors.values():
            all_errors.extend(field_errors)
        return all_errors
    
    def add_field_error(self, field_name: str, error: ValidationError) -> None:
        """Add a field-specific validation error.
        
        Args:
            field_name: Name of the field
            error: ValidationError to add
        """
        if field_name not in self.field_errors:
            self.field_errors[field_name] = []
        self.field_errors[field_name].append(error)
        self.is_valid = False
    
    def add_global_error(self, error: ValidationError) -> None:
        """Add a global validation error.
        
        Args:
            error: ValidationError to add
        """
        self.global_errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: ValidationWarning) -> None:
        """Add a validation warning.
        
        Args:
            warning: ValidationWarning to add
        """
        self.warnings.append(warning)
    
    def add_suggestion(self, suggestion: ValidationSuggestion) -> None:
        """Add a validation suggestion.
        
        Args:
            suggestion: ValidationSuggestion to add
        """
        self.suggestions.append(suggestion)
    
    def clear_fields(self, field_names: Set[str]) -> None:
        """Clear validation results for specific fields.
        
        Args:
            field_names: Set of field names to clear validation for
        """
        for field_name in field_names:
            if field_name in self.field_errors:
                del self.field_errors[field_name]
        
        # Remove global errors that are specific to the cleared fields
        # (This is a simple implementation - could be more sophisticated)
        self.global_errors = [error for error in self.global_errors 
                             if error.field_name not in field_names]
        
        # Remove warnings and suggestions for cleared fields
        self.warnings = [warning for warning in self.warnings 
                        if warning.field_name not in field_names]
        self.suggestions = [suggestion for suggestion in self.suggestions 
                           if suggestion.field_name not in field_names]
        
        # Recalculate validity
        self._recalculate_validity()
    
    def _recalculate_validity(self) -> None:
        """Recalculate the is_valid flag based on current errors."""
        self.is_valid = (len(self.global_errors) == 0 and 
                        all(len(errors) == 0 for errors in self.field_errors.values()))

    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one.
        
        Args:
            other: ValidationResult to merge
        """
        # Merge field errors
        for field_name, errors in other.field_errors.items():
            if field_name not in self.field_errors:
                self.field_errors[field_name] = []
            self.field_errors[field_name].extend(errors)
        
        # Merge other collections
        self.global_errors.extend(other.global_errors)
        self.warnings.extend(other.warnings)
        self.suggestions.extend(other.suggestions)
        
        # Update validity
        self.is_valid = self.is_valid and other.is_valid
        
        # When merging, keep the current data_id if it exists, otherwise use the other's data_id
        if self.data_id is None:
            self.data_id = other.data_id


class ValidationRule(ABC):
    """Abstract base class for validation rules with field dependency optimization."""
    
    @abstractmethod
    def validate(self, data: Any) -> List[ValidationError]:
        """Validate the transaction data and return any errors.
        
        Args:
            data: TransactionDisplayData to validate
            
        Returns:
            List[ValidationError]: List of validation errors found
        """
        pass
    
    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Get the name of this validation rule.
        
        Returns:
            str: Human-readable name of the rule
        """
        pass
    
    @property
    def priority(self) -> int:
        """Get the priority of this rule (lower = higher priority).
        
        Returns:
            int: Priority value (default: 100)
        """
        return 100
    
    @property
    def depends_on_fields(self) -> List[str]:
        """Get the fields this rule depends on for optimization.
        
        Returns:
            List[str]: List of field names this rule depends on.
                      Empty list means depends on all fields.
        """
        return []
    
    def should_run(self, changed_fields: Set[str]) -> bool:
        """Check if this rule should run based on changed fields.
        
        Args:
            changed_fields: Set of field names that changed
            
        Returns:
            bool: True if the rule should run
        """
        if not self.depends_on_fields:
            return True  # Run for any change if no dependencies specified
        return bool(set(self.depends_on_fields).intersection(changed_fields))


class AccountValidationRule(ValidationRule):
    """Validation rule for Beancount account names."""
    
    # Beancount account pattern: starts with capital letter, segments separated by colons
    ACCOUNT_PATTERN = re.compile(r'^[A-Z][A-Za-z0-9-]*(?::[A-Z][A-Za-z0-9-]*)*$')
    
    @property
    def rule_name(self) -> str:
        return "Account Name Validation"
    
    @property
    def priority(self) -> int:
        return 10  # High priority - basic format validation
    
    @property
    def depends_on_fields(self) -> List[str]:
        return ["source_account", "destination_account"]
    
    def validate(self, data: Any) -> List[ValidationError]:
        """Validate account names for Beancount compliance.
        
        Args:
            data: TransactionDisplayData to validate
            
        Returns:
            List[ValidationError]: List of account validation errors
        """
        errors = []
        
        # Validate source_account
        if data.source_account:
            source_account = data.source_account.strip()
            if not self.ACCOUNT_PATTERN.match(source_account):
                errors.append(ValidationError(
                    field_name="source_account",
                    error_type=ValidationErrorType.INVALID_FORMAT,
                    message="Invalid account format",
                    suggestion="Use format like 'Assets:Checking' or 'Expenses:Food:Groceries'",
                    error_code="INVALID_ACCOUNT_FORMAT"
                ))
        
        # Validate destination_account
        if data.destination_account:
            destination_account = data.destination_account.strip()
            if not self.ACCOUNT_PATTERN.match(destination_account):
                errors.append(ValidationError(
                    field_name="destination_account",
                    error_type=ValidationErrorType.INVALID_FORMAT,
                    message="Invalid account format",
                    suggestion="Use format like 'Assets:Checking' or 'Expenses:Food:Groceries'",
                    error_code="INVALID_ACCOUNT_FORMAT"
                ))
        
        return errors


class RequiredFieldsValidationRule(ValidationRule):
    """Validation rule for mandatory field checking."""
    
    @property
    def rule_name(self) -> str:
        return "Required Fields Validation"
    
    @property
    def priority(self) -> int:
        return 5  # Highest priority - check required fields first
    
    @property
    def depends_on_fields(self) -> List[str]:
        return ["source_account", "destination_account"]
    
    def validate(self, data: Any) -> List[ValidationError]:
        """Validate that required fields are present.
        
        Args:
            data: TransactionDisplayData to validate
            
        Returns:
            List[ValidationError]: List of required field errors
        """
        errors = []
        
        # Check source_account
        if not data.source_account or not data.source_account.strip():
            errors.append(ValidationError(
                field_name="source_account",
                error_type=ValidationErrorType.REQUIRED_FIELD,
                message="Source account is required",
                suggestion="Select or enter the source account for this transaction",
                error_code="REQUIRED_source_account"
            ))
        
        # Check destination_account
        if not data.destination_account or not data.destination_account.strip():
            errors.append(ValidationError(
                field_name="destination_account",
                error_type=ValidationErrorType.REQUIRED_FIELD,
                message="Destination account is required",
                suggestion="Select or enter the destination account for this transaction",
                error_code="REQUIRED_destination_account"
            ))
        
        return errors


class BusinessLogicValidationRule(ValidationRule):
    """Validation rule for transaction-specific business logic."""
    
    @property
    def rule_name(self) -> str:
        return "Business Logic Validation"
    
    @property
    def priority(self) -> int:
        return 50  # Medium priority - after basic validation
    
    @property
    def depends_on_fields(self) -> List[str]:
        return ["source_account", "destination_account"]
    
    def validate(self, data: Any) -> List[ValidationError]:
        """Validate business logic rules for transactions.
        
        Args:
            data: TransactionDisplayData to validate
            
        Returns:
            List[ValidationError]: List of business logic errors
        """
        errors = []
        
        # Check that source_account and destination_account are different
        if (data.source_account and data.destination_account and 
            data.source_account.strip() == data.destination_account.strip()):
            errors.append(ValidationError(
                field_name="destination_account",
                error_type=ValidationErrorType.BUSINESS_RULE,
                message="Source and destination accounts must be different",
                suggestion="Choose a different destination account",
                error_code="SAME_ACCOUNTS"
            ))
        
        # Validate account type consistency (basic heuristics)
        if data.source_account and data.destination_account:
            source_account = data.source_account.strip()
            destination_account = data.destination_account.strip()
            
            # Check for common account type mismatches
            if (source_account.startswith("Expenses:") and destination_account.startswith("Expenses:")):
                errors.append(ValidationError(
                    field_name="destination_account",
                    error_type=ValidationErrorType.BUSINESS_RULE,
                    message="Both accounts are expense accounts",
                    suggestion="Consider using an asset account (like Assets:Checking) as the source",
                    error_code="EXPENSE_TO_EXPENSE"
                ))
            
            if (source_account.startswith("Income:") and destination_account.startswith("Income:")):
                errors.append(ValidationError(
                    field_name="destination_account",
                    error_type=ValidationErrorType.BUSINESS_RULE,
                    message="Both accounts are income accounts",
                    suggestion="Consider using an asset account (like Assets:Checking) as the destination",
                    error_code="INCOME_TO_INCOME"
                ))
        
        return errors


class FormValidator:
    """Optimized form validator with priority-based rule execution and field filtering."""
    
    def __init__(self):
        """Initialize the form validator with default rules."""
        self._rules: List[ValidationRule] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Set up the default validation rules."""
        self.add_rule(RequiredFieldsValidationRule())
        self.add_rule(AccountValidationRule())
        self.add_rule(BusinessLogicValidationRule())
    
    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule to the validator.
        
        Args:
            rule: ValidationRule to add
        """
        self._rules.append(rule)
        # Keep rules sorted by priority (lower priority number = higher priority)
        self._rules.sort(key=lambda r: r.priority)
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove a validation rule by name.
        
        Args:
            rule_name: Name of the rule to remove
            
        Returns:
            bool: True if rule was found and removed
        """
        original_count = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_name != rule_name]
        return len(self._rules) < original_count
    
    def get_field_errors(self, field_name: str, validation_result: ValidationResult) -> List[str]:
        """Get error messages for a specific field.
        
        Args:
            field_name: Name of the field
            validation_result: ValidationResult to extract errors from
            
        Returns:
            List[str]: List of error messages for the field
        """
        if not validation_result.has_errors_for_field(field_name):
            return []
        
        return [error.message for error in validation_result.get_field_errors(field_name)]
    
    def validate(self, data: Any, changed_fields: Optional[Set[str]] = None, 
                previous_result: Optional['ValidationResult'] = None) -> ValidationResult:
        """Validate transaction data with optimized rule execution.
        
        Args:
            data: TransactionDisplayData to validate
            changed_fields: Optional set of field names that changed for optimization
            previous_result: Previous validation result to merge with (for incremental validation)
            
        Returns:
            ValidationResult: Comprehensive validation result
        """
        # Get the data ID for tracking validation result ownership
        data_id = getattr(data, 'display_id', None)
        
        # Check if previous result belongs to the same data object
        use_previous_result = (
            previous_result is not None and 
            changed_fields is not None and 
            getattr(previous_result, 'data_id', None) == data_id and
            data_id is not None  # Only use if we have a valid data_id
        )
        
        # Start with previous result if it belongs to the same data, otherwise create new one
        if use_previous_result:
            # For incremental validation, start with the previous result
            # We know previous_result and changed_fields are not None due to use_previous_result check
            assert previous_result is not None
            assert changed_fields is not None
            
            # Need to deep copy field_errors to avoid shared list references
            field_errors_copy = {
                field_name: errors.copy() 
                for field_name, errors in previous_result.field_errors.items()
            }
            result = ValidationResult(
                is_valid=previous_result.is_valid,
                field_errors=field_errors_copy,
                global_errors=previous_result.global_errors.copy(),
                warnings=previous_result.warnings.copy(),
                suggestions=previous_result.suggestions.copy(),
                data_id=data_id
            )
            
            # Get applicable rules based on changed fields
            applicable_rules = self._get_applicable_rules(changed_fields)
            
            # Clear validation results for ALL fields that the applicable rules might validate
            fields_to_clear = set()
            for rule in applicable_rules:
                # If a rule depends on specific fields, it might validate those fields
                if rule.depends_on_fields:
                    fields_to_clear.update(rule.depends_on_fields)
                else:
                    # If rule has no dependencies, it might validate any field
                    # In this case, we should clear all fields (conservative approach)
                    fields_to_clear.update(changed_fields)
            
            result.clear_fields(fields_to_clear)
        else:
            # For full validation, start with a clean result
            result = ValidationResult(is_valid=True, data_id=data_id)
            applicable_rules = self._get_applicable_rules(changed_fields or set())
        
        try:
            # Sort rules by priority (already sorted, but ensure consistency)
            sorted_rules = self._sort_rules_by_priority(applicable_rules)
            
            # Execute rules in priority order
            for rule in sorted_rules:
                try:
                    rule_errors = rule.validate(data)
                    
                    # Add errors to result
                    for error in rule_errors:
                        if error.field_name:
                            result.add_field_error(error.field_name, error)
                        else:
                            result.add_global_error(error)
                    
                except Exception as e:
                    # Log rule execution error but continue with other rules
                    logger.error(f"Error executing validation rule '{rule.rule_name}': {e}")
                    result.add_global_error(ValidationError(
                        field_name="",
                        error_type=ValidationErrorType.BUSINESS_RULE,
                        message=f"Validation error in rule '{rule.rule_name}'",
                        error_code="RULE_EXECUTION_ERROR"
                    ))
            
            # Add suggestions based on validation results
            self._add_contextual_suggestions(data, result)
            
        except Exception as e:
            # Handle unexpected validation errors
            logger.error(f"Unexpected error during validation: {e}")
            result.add_global_error(ValidationError(
                field_name="",
                error_type=ValidationErrorType.BUSINESS_RULE,
                message="Unexpected validation error occurred",
                error_code="VALIDATION_SYSTEM_ERROR"
            ))
            result.is_valid = False
        
        return result
    
    def _get_applicable_rules(self, changed_fields: Set[str]) -> List[ValidationRule]:
        """Get rules that should run based on changed fields.
        
        Args:
            changed_fields: Set of field names that changed
            
        Returns:
            List[ValidationRule]: Rules that should be executed
        """
        if not changed_fields:
            # If no specific fields changed, run all rules
            return self._rules.copy()
        
        applicable_rules = []
        for rule in self._rules:
            if rule.should_run(changed_fields):
                applicable_rules.append(rule)
        
        return applicable_rules
    
    def _sort_rules_by_priority(self, rules: List[ValidationRule]) -> List[ValidationRule]:
        """Sort rules by priority (lower number = higher priority).
        
        Args:
            rules: List of rules to sort
            
        Returns:
            List[ValidationRule]: Sorted rules
        """
        return sorted(rules, key=lambda r: r.priority)
    
    def _add_contextual_suggestions(self, data: Any, result: ValidationResult) -> None:
        """Add contextual suggestions based on validation results and data.
        
        Args:
            data: TransactionDisplayData being validated
            result: ValidationResult to add suggestions to
        """
        # Add suggestions based on transaction data patterns
        if hasattr(data, 'transaction_data') and data.transaction_data:
            transaction_data = data.transaction_data
            
            # Suggest account categorization based on narration or payee
            description = ""
            if hasattr(transaction_data, 'narration') and transaction_data.narration:
                description = transaction_data.narration.lower()
            elif hasattr(transaction_data, 'payee') and transaction_data.payee:
                description = transaction_data.payee.lower()
                
            if description:
                # Common patterns for account suggestions
                if any(word in description for word in ['grocery', 'food', 'restaurant', 'cafe']):
                    if not data.destination_account or not data.destination_account.startswith('Expenses:Food'):
                        result.add_suggestion(ValidationSuggestion(
                            field_name="destination_account",
                            suggestion="Consider using 'Expenses:Food:Groceries' or 'Expenses:Food:Restaurant'",
                            action_type="improvement"
                        ))
                
                elif any(word in description for word in ['gas', 'fuel', 'station']):
                    if not data.destination_account or not data.destination_account.startswith('Expenses:Transportation'):
                        result.add_suggestion(ValidationSuggestion(
                            field_name="destination_account",
                            suggestion="Consider using 'Expenses:Transportation:Gas'",
                            action_type="improvement"
                        ))
                
                elif any(word in description for word in ['amazon', 'online', 'shopping']):
                    if not data.destination_account or not data.destination_account.startswith('Expenses:Shopping'):
                        result.add_suggestion(ValidationSuggestion(
                            field_name="destination_account",
                            suggestion="Consider using 'Expenses:Shopping:Online'",
                            action_type="improvement"
                        ))
        
        # Add suggestions for common account patterns
        if data.source_account and not data.destination_account:
            if data.source_account.startswith('Assets:'):
                result.add_suggestion(ValidationSuggestion(
                    field_name="destination_account",
                    suggestion="For expenses from an asset account, use an Expenses: account",
                    action_type="improvement"
                ))
        
        # Add warnings for unusual patterns
        if data.source_account and data.destination_account:
            if (data.source_account.startswith('Assets:') and 
                data.destination_account.startswith('Assets:') and
                data.source_account != data.destination_account):
                result.add_warning(ValidationWarning(
                    field_name="destination_account",
                    message="Transfer between asset accounts",
                    suggestion="Verify this is an account transfer, not an expense"
                ))    

    def get_rules(self) -> List[ValidationRule]:
        """Get all registered validation rules.
        
        Returns:
            List[ValidationRule]: Copy of all registered rules
        """
        return self._rules.copy()
    
    def get_rule_by_name(self, rule_name: str) -> Optional[ValidationRule]:
        """Get a validation rule by name.
        
        Args:
            rule_name: Name of the rule to find
            
        Returns:
            Optional[ValidationRule]: The rule if found, None otherwise
        """
        for rule in self._rules:
            if rule.rule_name == rule_name:
                return rule
        return None
    
    def clear_rules(self) -> None:
        """Clear all validation rules."""
        self._rules.clear()
    
    def validate_field(self, data: Any, field_name: str) -> ValidationResult:
        """Validate a specific field using only relevant rules.
        
        Args:
            data: TransactionDisplayData to validate
            field_name: Name of the field to validate
            
        Returns:
            ValidationResult: Validation result for the specific field
        """
        return self.validate(data, changed_fields={field_name})
    
    def has_rule(self, rule_name: str) -> bool:
        """Check if a rule with the given name is registered.
        
        Args:
            rule_name: Name of the rule to check
            
        Returns:
            bool: True if the rule is registered
        """
        return any(rule.rule_name == rule_name for rule in self._rules)
    
    def get_rule_count(self) -> int:
        """Get the number of registered validation rules.
        
        Returns:
            int: Number of registered rules
        """
        return len(self._rules)