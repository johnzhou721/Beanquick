"""
Data structures for the Transaction Triage View.

This module defines the data structures and enumerations used specifically
for the transaction triage functionality, extending the base TransactionData
with status tracking and display-specific properties.
"""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable, Set

from beanquick.importers.core.data import TransactionData

logger = logging.getLogger(__name__)

class TransactionStatus(Enum):
    """Enumeration of possible transaction states in the triage workflow.
    
    Status Transition Logic:
    - NEEDS_REVIEW: Default state, or when validation fails and no rules are applied
    - CATEGORIZED: When rules have been applied to the transaction  
    - COMPLETED: When the transaction passes form validation
    
    Automatic transitions:
    - Rules applied -> CATEGORIZED
    - Validation passes -> COMPLETED
    - Validation fails -> CATEGORIZED (if rules applied) or NEEDS_REVIEW (if no rules)
    - Rules removed -> NEEDS_REVIEW (then validation determines final status)
    """
    NEEDS_REVIEW = "needs_review"
    CATEGORIZED = "categorized"
    COMPLETED = "completed"


class ObserverType(Enum):
    """Enumeration of observer types for granular notifications.
    
    This enum defines the different types of changes that observers
    can subscribe to for optimized update handling.
    """
    DATA_CHANGED = "data_changed"
    VALIDATION_CHANGED = "validation_changed"
    STATUS_CHANGED = "status_changed"


@dataclass
class TransactionDisplayData:
    """Extended transaction data for display purposes in the triage view.
    
    This class wraps the base TransactionData with additional display-specific
    properties including status tracking, visual indicators, and categorization
    information for the inspector panel workflow.
    
    Enhanced with observer pattern for reactive updates and automatic validation.
    TODO: Refactor with blinker

    Reactive Update Methods:
        - update_source_account(account): Updates source_account and triggers observers
        - update_destination_account(account): Updates destination_account and triggers observers  
        - update_applied_rules(rule_ids): Updates applied_rule_ids and triggers observers
        - add_applied_rule(rule_id): Adds a rule_id to applied_rule_ids and triggers observers
        - remove_applied_rule(rule_id): Removes a rule_id from applied_rule_ids and triggers observers
        - update_status(status): Updates status and triggers observers
    
    Observer Pattern:
        - add_observer(callback, type): Subscribe to data/validation/status changes
        - remove_observer(id, type): Unsubscribe from notifications
        - Automatic validation triggering on all field changes
    
    Attributes:
        transaction_data: The underlying TransactionData object
        status: Current status of the transaction in the triage workflow
        display_id: Unique identifier for display purposes
        source_account: Source account for categorization (optional)
        destination_account: Destination account for categorization (optional)
        applied_rule_ids: List of rule IDs that were applied to categorize this transaction
        categorization_timestamp: When the transaction was categorized (optional)
    """
    transaction_data: TransactionData
    status: TransactionStatus = TransactionStatus.NEEDS_REVIEW
    display_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_account: Optional[str] = None
    destination_account: Optional[str] = None
    applied_rule_ids: List[str] = field(default_factory=list)
    categorization_timestamp: Optional[datetime] = None
    
    # Observer pattern fields (not included in __init__)
    _observers: Dict[ObserverType, Dict[str, Callable]] = field(default_factory=dict, init=False)
    _validator: Optional[Any] = field(default=None, init=False)  # FormValidator will be defined later
    _validation_result: Optional[Any] = field(default=None, init=False)
    
    def add_observer(self, callback: Callable[['TransactionDisplayData', Optional[Set[str]]], None], 
                    observer_type: ObserverType = ObserverType.DATA_CHANGED) -> str:
        """Add an observer for the specified event type.
        
        Args:
            callback: Function to call when the event occurs. Should accept (transaction_display, changed_fields)
            observer_type: Type of events to observe
            
        Returns:
            str: Unique observer ID for later removal
        """
        if observer_type not in self._observers:
            self._observers[observer_type] = {}
        
        observer_id = str(uuid.uuid4())
        self._observers[observer_type][observer_id] = callback
        return observer_id
    
    def remove_observer(self, observer_id: str, observer_type: ObserverType) -> None:
        """Remove an observer by ID and type.
        
        Args:
            observer_id: The ID returned by add_observer
            observer_type: The type of observer to remove
        """
        if observer_type in self._observers and observer_id in self._observers[observer_type]:
            del self._observers[observer_type][observer_id]
    
    def _notify_observers(self, observer_type: ObserverType, changed_fields: Optional[Set[str]] = None) -> None:
        """Notify all observers of the specified type.
        
        Args:
            observer_type: Type of event that occurred
            changed_fields: Set of field names that changed (optional)
        """
        if observer_type not in self._observers:
            return
        
        for callback in self._observers[observer_type].values():
            try:
                # Call with both self and changed_fields for flexibility
                callback(self, changed_fields)
            except Exception as e:
                # Log error but don't break other observers
                logger.error(f"Error in observer callback: {e}")
    
    def set_validator(self, validator: Any) -> None:
        """Set the validator for automatic validation.
        
        Args:
            validator: FormValidator instance (typed as Any to avoid circular imports)
        """
        self._validator = validator
    
    def get_validation_result(self) -> Optional[Any]:
        """Get the current validation result.
        
        Returns:
            ValidationResult or None if no validation has been performed
        """
        return self._validation_result
    
    def _validate_and_notify(self, changed_fields: Set[str]) -> None:
        """Trigger validation and notify observers of validation changes.
        
        This method implements the core business logic for validation-driven status updates:
        - If validation passes, automatically update to COMPLETED
        - If validation fails, revert to appropriate status (CATEGORIZED if rules applied, else NEEDS_REVIEW)
        - This ensures status changes are driven by validation results, not manual setting
        
        Args:
            changed_fields: Set of field names that changed
        """
        if self._validator is not None:
            try:
                # Call validator.validate with previous result for incremental validation
                self._validation_result = self._validator.validate(
                    self, 
                    changed_fields, 
                    previous_result=self._validation_result
                )
                
                # Core business logic: validation-driven status updates
                if (self._validation_result is not None and 
                    hasattr(self._validation_result, 'is_valid')):
                    
                    old_status = self.status
                    
                    # Always set the correct status based on current validation state
                    if self._validation_result.is_valid:
                        # Validation passed -> COMPLETED
                        if self.status != TransactionStatus.COMPLETED:
                            self.status = TransactionStatus.COMPLETED
                            logger.debug(f"Auto-promoting transaction {self.display_id} to COMPLETED due to successful validation")
                    else:
                        # Validation failed -> revert to appropriate status
                        if self.applied_rule_ids:
                            # Rules are applied -> CATEGORIZED
                            if self.status != TransactionStatus.CATEGORIZED:
                                self.status = TransactionStatus.CATEGORIZED
                                logger.debug(f"Auto-setting transaction {self.display_id} to CATEGORIZED (rules applied, validation failed)")
                        else:
                            # No rules applied -> NEEDS_REVIEW
                            if self.status != TransactionStatus.NEEDS_REVIEW:
                                self.status = TransactionStatus.NEEDS_REVIEW
                                logger.debug(f"Auto-setting transaction {self.display_id} to NEEDS_REVIEW (no rules, validation failed)")
                    
                    # Notify status observers if status actually changed
                    if old_status != self.status:
                        self._notify_observers(ObserverType.STATUS_CHANGED, {'status'})
                
                # Notify validation observers
                self._notify_observers(ObserverType.VALIDATION_CHANGED, changed_fields)
                
            except Exception as e:
                # Log error but don't break the update flow
                logger.error(f"Error during validation: {e}")
    
    def _notify_data_change_and_validate(self, changed_fields: Set[str]) -> None:
        """Notify observers of data changes and trigger validation.
        
        This is the main method for reactive updates that:
        1. Notifies DATA_CHANGED observers
        2. Triggers validation 
        3. Notifies VALIDATION_CHANGED observers
        
        Args:
            changed_fields: Set of field names that changed
        """
        # First notify that data changed
        self._notify_observers(ObserverType.DATA_CHANGED, changed_fields)
        
        # Then validate and notify validation observers
        self._validate_and_notify(changed_fields)
    
    @property
    def status_icon(self) -> str:
        """Get the visual icon for the current status.
        
        Returns:
            str: Unicode symbol representing the current transaction status
                - 🟡 for NEEDS_REVIEW
                - 🔵 for CATEGORIZED
                - 🟢 for COMPLETED
        """
        status_icons: Dict[TransactionStatus, str] = {
            TransactionStatus.NEEDS_REVIEW: "🟡",
            TransactionStatus.CATEGORIZED: "🔵",
            TransactionStatus.COMPLETED: "🟢"
        }
        return status_icons.get(self.status, "🟡")
    
    @property
    def is_categorized(self) -> bool:
        """Check if the transaction has been categorized.
        
        A transaction is considered categorized if it has both source_account
        and destination_account values assigned.
        
        Returns:
            bool: True if the transaction has been categorized, False otherwise
        """
        return self.source_account is not None and self.destination_account is not None

    def update_fields(self, **fields) -> None:
        """Update multiple fields atomically with single validation/notification.
        
        Args:
            **fields: Field names and values to update
            
        Example:
            transaction.update_fields(
                source_account="Assets:Checking",
                destination_account="Expenses:Food",
                status=TransactionStatus.COMPLETED
            )
        """
        if not fields:
            return
        
        # Validate all fields upfront
        valid_fields = {'source_account', 'destination_account', 'applied_rule_ids', 'status', 'payee', 'narration', 'tags'}
        invalid_fields = set(fields.keys()) - valid_fields
        if invalid_fields:
            raise ValueError(f"Invalid fields: {', '.join(invalid_fields)}")
        
        # Track actual changes
        changed_fields = set()
        
        # Apply changes and track what actually changed
        for field_name, new_value in fields.items():
            old_value = None  # Initialize to avoid unbound variable
            
            if field_name == 'status':
                old_value = self.status
                if not isinstance(new_value, TransactionStatus):
                    raise TypeError("status must be a TransactionStatus enum value")
                self.status = new_value
            elif field_name in ['source_account', 'destination_account']:
                old_value = getattr(self, field_name)
                # Handle string fields (accounts)
                processed_value = new_value.strip() if new_value else None
                setattr(self, field_name, processed_value)
                
                # Sync with transaction metadata
                if self.transaction_data.metadata is None:
                    self.transaction_data.metadata = {}
                self.transaction_data.metadata[field_name] = processed_value
                new_value = processed_value  # For comparison below
            elif field_name == 'applied_rule_ids':
                old_value = self.applied_rule_ids.copy() if self.applied_rule_ids else []
                # Handle list of rule IDs
                if new_value is None:
                    processed_value = []
                elif isinstance(new_value, list):
                    processed_value = [rule_id.strip() for rule_id in new_value if rule_id and rule_id.strip()]
                else:
                    raise TypeError("applied_rule_ids must be a list or None")
                
                self.applied_rule_ids = processed_value
                
                # Sync with transaction metadata (both old and new formats for compatibility)
                if self.transaction_data.metadata is None:
                    self.transaction_data.metadata = {}
                self.transaction_data.metadata['applied_rule_ids'] = processed_value
                # Keep backward compatibility
                self.transaction_data.metadata['applied_rule_id'] = processed_value[-1] if processed_value else None
                new_value = processed_value  # For comparison below
            elif field_name == 'payee':
                old_value = self.transaction_data.payee
                processed_value = new_value.strip() if new_value else ""
                self.transaction_data.payee = processed_value
                # Sync metadata
                if self.transaction_data.metadata is None:
                    self.transaction_data.metadata = {}
                self.transaction_data.metadata['payee'] = processed_value
                new_value = processed_value  # For comparison below
            elif field_name == 'narration':
                old_value = self.transaction_data.narration
                processed_value = new_value.strip() if new_value else None
                self.transaction_data.narration = processed_value
                # Sync metadata
                if self.transaction_data.metadata is None:
                    self.transaction_data.metadata = {}
                self.transaction_data.metadata['narration'] = processed_value
                new_value = processed_value  # For comparison below
            elif field_name == 'tags':
                old_value = set(self.transaction_data.tags) if self.transaction_data.tags else set()
                # Handle set of tags
                if new_value is None:
                    processed_value = set()
                elif isinstance(new_value, set):
                    processed_value = {tag.strip() for tag in new_value if tag and tag.strip()}
                elif hasattr(new_value, '__iter__'):
                    # Convert from list/tuple/other iterable
                    processed_value = {str(tag).strip() for tag in new_value if tag and str(tag).strip()}
                else:
                    raise TypeError("tags must be a set, list, or other iterable")
                
                self.transaction_data.tags = processed_value
                # Sync metadata
                if self.transaction_data.metadata is None:
                    self.transaction_data.metadata = {}
                self.transaction_data.metadata['tags'] = list(processed_value) if processed_value else []
                new_value = processed_value  # For comparison below
            
            # Track if value actually changed
            if old_value != new_value:
                changed_fields.add(field_name)
        
        # Single notification for all changes
        if changed_fields:
            self._notify_data_change_and_validate(changed_fields)
            if 'status' in changed_fields:
                self._notify_observers(ObserverType.STATUS_CHANGED, changed_fields)

    def update_field(self, field_name: str, value: Any) -> None:
        """Generic field update method with validation and notification.

        Args:
            field_name: Name of the field to update
            value: New value for the field
            
        Raises:
            ValueError: If field_name is not a valid updatable field
        """
        # Define updatable fields mapping to existing methods
        updatable_fields = {
            'source_account': lambda v: self.update_source_account(v),
            'destination_account': lambda v: self.update_destination_account(v),
            'applied_rule_ids': lambda v: self.update_applied_rules(v),
            'status': lambda v: self.update_status(v),
            'payee': lambda v: self.update_payee(v),
            'narration': lambda v: self.update_narration(v),
            'tags': lambda v: self.update_tags(v)
        }
        
        if field_name not in updatable_fields:
            raise ValueError(f"Field '{field_name}' is not updatable")
        
        # Call the appropriate existing update method
        updatable_fields[field_name](value)

    def update_source_account(self, source_account: str) -> None:
        """Update the source_account and sync with underlying transaction metadata.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            source_account: The new source account value
        """
        old_value = self.source_account
        self.source_account = source_account.strip() if source_account else None
        
        # Keep the underlying transaction metadata in sync
        if self.transaction_data.metadata is None:
            self.transaction_data.metadata = {}
        self.transaction_data.metadata['source_account'] = self.source_account
        
        # Only notify if value actually changed
        if old_value != self.source_account:
            changed_fields = {'source_account'}
            self._notify_data_change_and_validate(changed_fields)
    
    def update_destination_account(self, destination_account: str) -> None:
        """Update the destination_account and sync with underlying transaction metadata.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            destination_account: The new destination account value
        """
        old_value = self.destination_account
        self.destination_account = destination_account.strip() if destination_account else None
        
        # Keep the underlying transaction metadata in sync
        if self.transaction_data.metadata is None:
            self.transaction_data.metadata = {}
        self.transaction_data.metadata['destination_account'] = self.destination_account
        
        # Only notify if value actually changed
        if old_value != self.destination_account:
            changed_fields = {'destination_account'}
            self._notify_data_change_and_validate(changed_fields)
    
    def update_applied_rules(self, rule_ids: List[str]) -> None:
        """Update the list of applied rule IDs and sync with underlying transaction metadata.
        
        This method triggers validation and notifies observers of the change.
        When rules are applied, status is automatically updated to CATEGORIZED.
        When rules are removed, status reverts to NEEDS_REVIEW (unless validation passes).
        
        Args:
            rule_ids: The new list of rule IDs (can be empty list to clear all rules)
        """
        old_value = self.applied_rule_ids.copy() if self.applied_rule_ids else []
        
        # Process the input - ensure it's a list and clean up strings
        if rule_ids is None:
            processed_value = []
        elif isinstance(rule_ids, list):
            processed_value = [rule_id.strip() for rule_id in rule_ids if rule_id and rule_id.strip()]
        else:
            raise TypeError("rule_ids must be a list or None")
        
        self.applied_rule_ids = processed_value
        
        # Keep the underlying transaction metadata in sync (both old and new formats)
        if self.transaction_data.metadata is None:
            self.transaction_data.metadata = {}
        self.transaction_data.metadata['applied_rule_ids'] = self.applied_rule_ids
        # Maintain backward compatibility with single applied_rule_id
        self.transaction_data.metadata['applied_rule_id'] = self.applied_rule_ids[-1] if self.applied_rule_ids else None
        
        # Only notify if value actually changed
        if old_value != self.applied_rule_ids:
            # Business logic: Update status based on rule application
            old_status = self.status
            had_rules = bool(old_value)
            has_rules = bool(self.applied_rule_ids)
            
            # Status update logic based on rule changes
            if has_rules and not had_rules:
                # Rules were added -> CATEGORIZED
                self.status = TransactionStatus.CATEGORIZED
                logger.debug(f"Auto-setting transaction {self.display_id} to CATEGORIZED due to rule application")
            elif had_rules and not has_rules:
                # Rules were removed -> NEEDS_REVIEW (validation will determine final status)
                self.status = TransactionStatus.NEEDS_REVIEW
                logger.debug(f"Auto-setting transaction {self.display_id} to NEEDS_REVIEW due to rule removal")
            
            changed_fields = {'applied_rule_ids'}
            
            # Add status to changed fields if it changed
            if old_status != self.status:
                changed_fields.add('status')
            
            # Notify observers and trigger validation
            self._notify_data_change_and_validate(changed_fields)
            
            # Notify status observers if status changed
            if old_status != self.status:
                self._notify_observers(ObserverType.STATUS_CHANGED, {'status'})
    
    def add_applied_rule(self, rule_id: str) -> None:
        """Add a rule ID to the list of applied rules.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            rule_id: The rule ID to add to the list (must not be None or empty)
        """
        if not rule_id or not rule_id.strip():
            raise ValueError("rule_id cannot be None or empty")
        
        rule_id = rule_id.strip()
        
        # Only add if not already present
        if rule_id not in self.applied_rule_ids:
            new_list = self.applied_rule_ids + [rule_id]
            self.update_applied_rules(new_list)
    
    def remove_applied_rule(self, rule_id: str) -> None:
        """Remove a rule ID from the list of applied rules.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            rule_id: The rule ID to remove from the list
        """
        if not rule_id or not rule_id.strip():
            return  # Nothing to remove
        
        rule_id = rule_id.strip()
        
        # Only update if the rule was actually present
        if rule_id in self.applied_rule_ids:
            new_list = [rid for rid in self.applied_rule_ids if rid != rule_id]
            self.update_applied_rules(new_list)
    
    def update_status(self, status: TransactionStatus) -> None:
        """Update the transaction status.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            status: The new transaction status
        """
        if not isinstance(status, TransactionStatus):
            raise TypeError("status must be a TransactionStatus enum value")
        
        old_value = self.status
        self.status = status
        
        # Only notify if value actually changed
        if old_value != self.status:
            changed_fields = {'status'}
            # Notify data changed observers
            self._notify_observers(ObserverType.DATA_CHANGED, changed_fields)
            # Also notify status-specific observers
            self._notify_observers(ObserverType.STATUS_CHANGED, changed_fields)
    
    def update_payee(self, payee: str) -> None:
        """Update the payee and sync with underlying transaction data.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            payee: The new payee value
        """
        old_value = self.transaction_data.payee
        new_payee = payee.strip() if payee else ""
        
        # Update the underlying transaction data
        self.transaction_data.payee = new_payee
        
        # Keep metadata in sync for backward compatibility
        if self.transaction_data.metadata is None:
            self.transaction_data.metadata = {}
        self.transaction_data.metadata['payee'] = new_payee
        
        # Only notify if value actually changed
        if old_value != new_payee:
            changed_fields = {'payee'}
            self._notify_data_change_and_validate(changed_fields)
    
    def update_narration(self, narration: Optional[str]) -> None:
        """Update the narration and sync with underlying transaction data.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            narration: The new narration value (can be None or empty)
        """
        old_value = self.transaction_data.narration
        new_narration = narration.strip() if narration else None
        
        # Update the underlying transaction data
        self.transaction_data.narration = new_narration
        
        # Keep metadata in sync for backward compatibility
        if self.transaction_data.metadata is None:
            self.transaction_data.metadata = {}
        self.transaction_data.metadata['narration'] = new_narration
        
        # Only notify if value actually changed
        if old_value != new_narration:
            changed_fields = {'narration'}
            self._notify_data_change_and_validate(changed_fields)
    
    @property
    def tags(self) -> Set[str]:
        """Get the transaction tags from the underlying transaction data.
        
        Returns:
            Set[str]: Set of tags associated with the transaction
        """
        if isinstance(self.transaction_data.tags, set):
            return self.transaction_data.tags
        else:
            return set(self.transaction_data.tags) if self.transaction_data.tags else set()
    
    @tags.setter
    def tags(self, value: Set[str]) -> None:
        """Set the transaction tags and sync with underlying transaction data.
        
        Args:
            value: New set of tags for the transaction
        """
        old_value = set(self.transaction_data.tags) if self.transaction_data.tags else set()
        
        # Ensure value is a set and clean tag values
        if value is None:
            new_tags = set()
        elif isinstance(value, set):
            new_tags = {tag.strip() for tag in value if tag and tag.strip()}
        else:
            # Convert from other collection types
            try:
                new_tags = {str(tag).strip() for tag in value if tag and str(tag).strip()}
            except (TypeError, AttributeError):
                new_tags = set()
        
        # Update the underlying transaction data
        self.transaction_data.tags = new_tags
        
        # Keep metadata in sync for backward compatibility
        if self.transaction_data.metadata is None:
            self.transaction_data.metadata = {}
        self.transaction_data.metadata['tags'] = list(new_tags) if new_tags else []
        
        # Only notify if value actually changed
        if old_value != new_tags:
            changed_fields = {'tags'}
            self._notify_data_change_and_validate(changed_fields)
    
    def update_tags(self, tags: Set[str]) -> None:
        """Update the transaction tags using the property setter.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            tags: New set of tags for the transaction
        """
        self.tags = tags
    
    def add_tag(self, tag: str) -> None:
        """Add a single tag to the transaction.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            tag: The tag to add (must not be None or empty)
        """
        if not tag or not tag.strip():
            raise ValueError("tag cannot be None or empty")
        
        tag = tag.strip()
        
        # Only update if tag is not already present
        if tag not in self.transaction_data.tags:
            new_tags = set(self.transaction_data.tags) if self.transaction_data.tags else set()
            new_tags.add(tag)
            self.update_tags(new_tags)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the transaction.
        
        This method triggers validation and notifies observers of the change.
        
        Args:
            tag: The tag to remove
        """
        if not tag or not tag.strip():
            return  # Nothing to remove
        
        tag = tag.strip()
        
        # Only update if tag was actually present
        if tag in self.transaction_data.tags:
            new_tags = set(self.transaction_data.tags) if self.transaction_data.tags else set()
            new_tags.discard(tag)
            self.update_tags(new_tags)
    
    def __post_init__(self):
        """Validate the transaction display data after initialization.
        
        Raises:
            ValueError: If transaction_data is None or invalid
            TypeError: If status is not a TransactionStatus enum value
        """
        if self.transaction_data is None:
            raise ValueError("transaction_data cannot be None")
        
        if not isinstance(self.status, TransactionStatus):
            raise TypeError("status must be a TransactionStatus enum value")
        
        if not self.display_id or not self.display_id.strip():
            raise ValueError("display_id cannot be empty")
        
        # Initialize observer dictionaries
        if not hasattr(self, '_observers'):
            self._observers = {}
        if not hasattr(self, '_validator'):
            self._validator = None
        if not hasattr(self, '_validation_result'):
            self._validation_result = None
        
@dataclass
class SuccessData:
    """Data structure for import completion statistics and metadata.
    
    This dataclass contains comprehensive information about a completed import
    process, including transaction counts, rule statistics, file information,
    and processing metadata for display in the success view.
    
    Attributes:
        transaction_count: Total number of transactions processed
        categorized_count: Number of transactions that were categorized
        completed_count: Number of transactions marked as completed
        rules_created: Number of new rules created during the import
        rules_applied: Number of rules applied automatically during extraction
        source_file_name: Name of the original statement file
        source_file_path: Full path to the original statement file
        saved_file_path: Path where the Beancount entries were saved
        rule_ids_created: List of IDs for rules created during this import
        transaction_ids_processed: List of display IDs for all processed transactions
    """
    transaction_count: int
    categorized_count: int
    completed_count: int
    rules_created: int
    rules_applied: int
    source_file_name: str
    source_file_path: str
    saved_file_path: str
    rule_ids_created: List[str] = field(default_factory=list)
    transaction_ids_processed: List[str] = field(default_factory=list)
    
    @property
    def categorization_rate(self) -> float:
        """Calculate the percentage of transactions that were categorized.
        
        Returns:
            float: Percentage (0.0 to 100.0) of transactions categorized
        """
        if self.transaction_count == 0:
            return 0.0
        return (self.categorized_count / self.transaction_count) * 100.0
    
    @property
    def completion_rate(self) -> float:
        """Calculate the percentage of transactions that were completed.
        
        Returns:
            float: Percentage (0.0 to 100.0) of transactions completed
        """
        if self.transaction_count == 0:
            return 0.0
        return (self.completed_count / self.transaction_count) * 100.0
    
    @property
    def source_file_name_display(self) -> str:
        """Get a display-friendly version of the source file name.
        
        Returns:
            str: Truncated file name if too long, otherwise the full name
        """
        max_length = 40
        if len(self.source_file_name) <= max_length:
            return self.source_file_name
        
        # Truncate with ellipsis in the middle to preserve extension
        path_obj = Path(self.source_file_name)
        name_part = path_obj.stem
        extension = path_obj.suffix
        
        if len(name_part) + len(extension) <= max_length:
            return self.source_file_name
        
        # Calculate how much of the name we can show
        available_for_name = max_length - len(extension) - 3  # 3 for "..."
        if available_for_name > 0:
            truncated_name = name_part[:available_for_name]
            return f"{truncated_name}...{extension}"
        else:
            return f"...{extension}"
    
    @property
    def saved_file_name_display(self) -> str:
        """Get a display-friendly version of the saved file path.
        
        Returns:
            str: File name from the saved file path
        """
        return Path(self.saved_file_path).name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the SuccessData to a dictionary for easy serialization.
        
        Returns:
            Dict[str, any]: Dictionary representation of the success data
        """
        return {
            'transaction_count': self.transaction_count,
            'categorized_count': self.categorized_count,
            'completed_count': self.completed_count,
            'rules_created': self.rules_created,
            'rules_applied': self.rules_applied,
            'source_file_name': self.source_file_name,
            'source_file_path': self.source_file_path,
            'saved_file_path': self.saved_file_path,
            'categorization_rate': f"{self.categorization_rate:.1f}%",
            'completion_rate': f"{self.completion_rate:.1f}%",
            'rule_ids_created': self.rule_ids_created.copy(),
            'transaction_ids_processed': self.transaction_ids_processed.copy(),
        }
    
    @classmethod
    def from_transactions(cls, 
                         transactions: List['TransactionDisplayData'],
                         source_file_path: str,
                         saved_file_path: str,
                         rules_created: int = 0,
                         rules_applied: int = 0,
                         rule_ids_created: Optional[List[str]] = None) -> 'SuccessData':
        """Create SuccessData from a list of transactions and metadata.
        
        This class method provides a convenient way to generate SuccessData
        from processed transactions and other import metadata.
        
        Args:
            transactions: List of TransactionDisplayData objects
            source_file_path: Path to the original statement file
            saved_file_path: Path where entries were saved
            rules_created: Number of new rules created (default: 0)
            rules_applied: Number of rules applied (default: 0)
            rule_ids_created: List of rule IDs created (optional)
            
        Returns:
            SuccessData: Populated success data object
        """
        # Calculate transaction statistics
        transaction_count = len(transactions)
        categorized_count = sum(1 for t in transactions if t.is_categorized)
        completed_count = sum(1 for t in transactions if t.status == TransactionStatus.COMPLETED)
        
        # Extract transaction IDs
        transaction_ids = [t.display_id for t in transactions]
        
        # Get file names
        source_file_name = Path(source_file_path).name
        
        return cls(
            transaction_count=transaction_count,
            categorized_count=categorized_count,
            completed_count=completed_count,
            rules_created=rules_created,
            rules_applied=rules_applied,
            source_file_name=source_file_name,
            source_file_path=source_file_path,
            saved_file_path=saved_file_path,
            rule_ids_created=rule_ids_created or [],
            transaction_ids_processed=transaction_ids
        )
    
    def __post_init__(self):
        """Validate the success data after initialization.
        
        Raises:
            ValueError: If any required fields are invalid or missing
        """
        if self.transaction_count < 0:
            raise ValueError("transaction_count cannot be negative")
        
        if self.categorized_count < 0 or self.categorized_count > self.transaction_count:
            raise ValueError("categorized_count must be between 0 and transaction_count")
        
        if self.completed_count < 0 or self.completed_count > self.transaction_count:
            raise ValueError("completed_count must be between 0 and transaction_count")
        
        if self.rules_created < 0:
            raise ValueError("rules_created cannot be negative")
        
        if self.rules_applied < 0:
            raise ValueError("rules_applied cannot be negative")
        
        if not self.source_file_name or not self.source_file_name.strip():
            raise ValueError("source_file_name cannot be empty")
        
        if not self.saved_file_path or not self.saved_file_path.strip():
            raise ValueError("saved_file_path cannot be empty")
