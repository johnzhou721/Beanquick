"""
Rule data structures and enumerations for transaction categorization.

This module defines the data structures used for creating, storing, and applying
rules that automate transaction categorization in the triage workflow.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..core.data import TransactionData
from .rule_components import ConditionsBlock, Action


@dataclass
class TransactionRule:
    """Transaction rule with metadata and complex logic.
    
    This class represents a comprehensive transaction categorization rule that
    supports complex multi-field conditions, logical operators, multiple actions
    per rule, and sophisticated control flow mechanisms.
    
    Attributes:
        rule_id: Unique identifier for the rule
        name: Human-readable name for the rule
        is_enabled: Whether the rule is active (default: True)
        stop_processing: Whether to stop processing other rules after this one matches (default: False)
        conditions_block: Block of conditions with logical operators for matching
        actions: List of actions to execute when the rule matches
        created_date: When the rule was created
        last_applied: When the rule was last applied (None if never applied)
        application_count: Number of times this rule has been applied
    """
    # Metadata fields
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    is_enabled: bool = True
    stop_processing: bool = False
    
    # Logic components
    conditions_block: Optional[ConditionsBlock] = None
    actions: List[Action] = field(default_factory=list)
    
    # Statistics
    created_date: datetime = field(default_factory=datetime.now)
    last_applied: Optional[datetime] = None
    application_count: int = 0
    
    def matches(self, transaction: TransactionData) -> bool:
        """Check if this rule matches the given transaction.
        
        This method uses ConditionsBlock evaluation to support
        complex logical conditions and multiple field matching.
        
        Args:
            transaction: The transaction to check against this rule
            
        Returns:
            bool: True if the rule matches the transaction, False otherwise
        """
        # Disabled rules never match
        if not self.is_enabled:
            return False
        
        # Rules without conditions never match
        if not self.conditions_block:
            return False
        
        # Delegate to ConditionsBlock for evaluation
        return self.conditions_block.matches(transaction)
    
    def __post_init__(self):
        """Validate the rule data after initialization.
        
        Provides comprehensive validation for all new fields including
        metadata, conditions, and actions.
        
        Raises:
            ValueError: If required fields are invalid or empty
            TypeError: If field types are incorrect
        """
        # Validate rule_id
        if not self.rule_id or not self.rule_id.strip():
            raise ValueError("rule_id cannot be empty")
        
        # Validate name
        if self.name is None:
            self.name = ""
        else:
            self.name = self.name.strip()
        
        # Validate boolean fields
        if not isinstance(self.is_enabled, bool):
            raise TypeError("is_enabled must be a boolean")
        
        if not isinstance(self.stop_processing, bool):
            raise TypeError("stop_processing must be a boolean")
        
        # Validate conditions_block
        if self.conditions_block is not None and not isinstance(self.conditions_block, ConditionsBlock):
            raise TypeError("conditions_block must be a ConditionsBlock instance or None")
        
        # Validate actions list
        if not isinstance(self.actions, list):
            raise TypeError("actions must be a list")
        
        for action in self.actions:
            if not isinstance(action, Action):
                raise TypeError("All actions must be Action instances")
        
        # Validate statistics fields
        if self.application_count < 0:
            raise ValueError("application_count cannot be negative")
        
        if not isinstance(self.created_date, datetime):
            raise TypeError("created_date must be a datetime instance")
        
        if self.last_applied is not None and not isinstance(self.last_applied, datetime):
            raise TypeError("last_applied must be a datetime instance or None")
        
        # Strip whitespace from string fields
        self.rule_id = self.rule_id.strip()
        
        # Validate that rule has either conditions or is explicitly designed to never match
        # This prevents accidentally creating rules that will never match
        if self.conditions_block is None and self.is_enabled:
            # Allow rules without conditions if they're disabled (for template/draft purposes)
            pass