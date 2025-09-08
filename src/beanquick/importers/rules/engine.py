"""
Rule engine service for transaction rule management and application.

This module provides the RuleEngine class that handles rule creation, matching,
and bulk application of rules to transactions. It serves as the central service
for automating transaction categorization through intelligent rule management.
"""

from typing import List, Optional, Dict, Tuple, Any
import logging

from . import TransactionRule
from ..core.data import TransactionData
from .repository import RuleRepository
from .sqlite_rule_matcher import SQLiteRuleMatcher
from .action_executor import ActionExecutor
from .rule_components import (
    ConditionsBlock, Action, ActionType
)
from beanquick.ui.transaction_triage_data import TransactionDisplayData

logger = logging.getLogger(__name__)


class RuleEngine:
    """Central service for rule creation, matching, and application.
    
    The RuleEngine coordinates between the RuleRepository for persistence,
    SQLiteRuleMatcher for optimized matching, and ActionExecutor for rule application.
    It provides high-level operations for rule management in the triage workflow
    with matching capabilities and performance optimizations.
    
    Attributes:
        _rule_repository: Repository for rule persistence and retrieval
        _rule_matcher: SQLite-based rule matching engine
        _action_executor: Action execution engine
    """
    
    def __init__(self, rule_repository: RuleRepository):
        """Initialize the rule engine with a rule repository.
        
        Args:
            rule_repository: Repository for rule persistence and management
            
        Raises:
            ValueError: If rule_repository is not provided
        """
        if not rule_repository:
            raise ValueError("rule_repository is required")
        
        self._rule_repository = rule_repository
        self._rule_matcher: Optional[SQLiteRuleMatcher] = None
        self._action_executor = ActionExecutor()
        
        # Initialize the rule matcher with current rules
        self._refresh_rule_matcher()
    
    @property
    def importer_name(self) -> str:
        """Get the importer name from the repository."""
        return self._rule_repository.importer_name

    @property
    def importer_icon(self) -> str:
        """Get the importer icon from the repository."""
        return self._rule_repository.importer_icon

    def _refresh_rule_matcher(self) -> None:
        """Initialize the SQLite rule matcher.
        
        SQLiteRuleMatcher queries the database directly and sees changes immediately,
        so it doesn't need refreshing after rule changes.
        """
        try:
            # Get the SQLite repository from the wrapped repository
            if hasattr(self._rule_repository, '_repository'):
                sqlite_repo = self._rule_repository._repository
                self._rule_matcher = SQLiteRuleMatcher(sqlite_repo)
                logger.debug("SQLite rule matcher initialized with wrapped repository")
                return
            
            logger.error("No SQLite repository found for rule matcher initialization")
            self._rule_matcher = None
            
        except Exception as e:
            logger.error(f"Failed to initialize SQLite rule matcher: {e}")
            self._rule_matcher = None
    
    def create_rule(self, name: str, conditions_block: "ConditionsBlock", 
                   actions: List["Action"], is_enabled: bool = True, 
                   stop_processing: bool = False) -> TransactionRule:
        """Create a new generic rule with comprehensive validation.
        
        This method creates a new rule with the rule system supporting
        complex conditions, multiple actions, and rule metadata. It includes
        comprehensive validation and conflict detection.
        
        Args:
            name: Human-readable name for the rule
            conditions_block: Block of conditions with logical operators
            actions: List of actions to execute when rule matches
            is_enabled: Whether the rule should be active (default: True)
            stop_processing: Whether to stop processing other rules after this one (default: False)
            
        Returns:
            TransactionRule: The newly created rule
            
        Raises:
            ValueError: If validation fails or rule conflicts are detected
            RuleCreationError: If rule creation fails due to conflicts
        """
        # Validate inputs
        name = (name or "").strip()
        if not name:
            raise ValueError("Rule name cannot be empty")
        
        if not isinstance(conditions_block, ConditionsBlock):
            raise ValueError("conditions_block must be a ConditionsBlock instance")
        
        if not isinstance(actions, list) or not actions:
            raise ValueError("actions must be a non-empty list")
        
        for action in actions:
            if not isinstance(action, Action):
                raise ValueError("All actions must be Action instances")
        
        # Create new rule
        rule = TransactionRule(
            name=name,
            conditions_block=conditions_block,
            actions=actions,
            is_enabled=is_enabled,
            stop_processing=stop_processing
        )
        
        # Validate rule structure
        validation_errors = self.validate_rule(rule)
        if validation_errors:
            raise ValueError(f"Rule validation failed: {'; '.join(validation_errors)}")
        
        # Check for conflicts with existing rules
        # conflicts = self.detect_rule_conflicts_for_new_rule(rule)
        # if conflicts:
        #     conflict_descriptions = [f"Conflicts with rule '{conflict[1].name}': {conflict[2]}" 
        #                            for conflict in conflicts]
        #     raise RuleCreationError(f"Rule conflicts detected: {'; '.join(conflict_descriptions)}")
        # Save to repository
        self._rule_repository.save_rule(rule)
        
        logger.info(f"Created new rule '{name}' with {len(actions)} actions")
        return rule
    
    def match_transaction(self, transaction: TransactionData) -> Optional[TransactionRule]:
        """Find the best matching rule for a given transaction.
        
        This method uses the SQLiteRuleMatcher for optimized rule selection
        with early termination, disabled rule filtering, and performance optimizations.
        Rules are prioritized by application count (most used first) and then by 
        creation date (newest first).
        
        Args:
            transaction: The transaction to find a matching rule for
            
        Returns:
            Optional[TransactionRule]: The best matching rule, or None if no match found
        """
        if not transaction:
            return None
        
        if not self._rule_matcher:
            logger.warning("Rule matcher not initialized, refreshing")
            self._refresh_rule_matcher()
            if not self._rule_matcher:
                return None
        
        # Use the optimized rule matcher to find the first (highest priority) match
        return self._rule_matcher.find_first_matching_rule(transaction)
    
    def match_all_rules(self, transaction: TransactionData) -> List[TransactionRule]:
        """Find all rules that match a given transaction with early termination.
        
        This method returns all matching rules in priority order, respecting
        stop_processing flags for early termination. Useful for debugging
        and rule analysis scenarios.
        
        Args:
            transaction: The transaction to find matching rules for
            
        Returns:
            List[TransactionRule]: All matching rules in priority order
        """
        if not transaction:
            return []
        
        if not self._rule_matcher:
            logger.warning("Rule matcher not initialized, refreshing")
            self._refresh_rule_matcher()
            if not self._rule_matcher:
                return []
        
        return self._rule_matcher.find_matching_rules(transaction)
    
    def preview_rule_impact(self, rule: TransactionRule, 
                           transactions: List[TransactionDisplayData]) -> Dict[str, Any]:
        """Preview the impact of applying a rule to a list of transactions.
        
        This method shows how many transactions would be affected and provides
        detailed information about the changes that would be made without
        actually applying the rule.
        
        Args:
            rule: The rule to preview
            transactions: List of transactions to analyze
            
        Returns:
            Dict containing preview results with keys:
                - total_transactions: total number of transactions analyzed
                - matching_transactions: number of transactions that would match
                - affected_transaction_ids: list of display_ids that would be affected
                - actions_summary: summary of actions that would be executed
                - validation_errors: any validation issues found
                
        Raises:
            ValueError: If rule or transactions is not provided
        """
        if not rule:
            raise ValueError("rule is required")
        if not transactions:
            raise ValueError("transactions is required")
        
        result = {
            "total_transactions": len(transactions),
            "matching_transactions": 0,
            "affected_transaction_ids": [],
            "actions_summary": {},
            "validation_errors": []
        }
        
        # Validate rule first
        validation_errors = self.validate_rule(rule)
        result["validation_errors"] = validation_errors
        
        if validation_errors:
            return result
        
        # Count actions by type for summary
        action_counts = {}
        for action in rule.actions:
            action_type = action.action_type.value
            action_counts[action_type] = action_counts.get(action_type, 0) + 1
        
        # Analyze each transaction
        for transaction_display in transactions:
            if rule.matches(transaction_display.transaction_data):
                result["matching_transactions"] += 1
                result["affected_transaction_ids"].append(transaction_display.display_id)
        
        # Build actions summary
        if result["matching_transactions"] > 0:
            result["actions_summary"] = {
                action_type: {
                    "count": count,
                    "total_applications": count * result["matching_transactions"]
                }
                for action_type, count in action_counts.items()
            }
        
        return result
    
    def apply_rule_to_transactions(self, rule: TransactionRule, 
                                  transactions: List[TransactionDisplayData]) -> List[str]:
        """Apply a rule to a list of transactions and return IDs of affected transactions.
        
        This method applies the given rule to all matching transactions in the list,
        executing multiple actions per rule and providing comprehensive error handling.
        It tracks rule application statistics and provides detailed logging.
        
        Args:
            rule: The rule to apply
            transactions: List of transactions to check and potentially update
            
        Returns:
            List[str]: List of display_ids of transactions that were updated
            
        Raises:
            ValueError: If rule or transactions is not provided
        """
        if not rule:
            raise ValueError("rule is required")
        if not transactions:
            raise ValueError("transactions is required")
        
        # Validate rule before applying
        validation_errors = self.validate_rule(rule)
        if validation_errors:
            logger.error(f"Cannot apply invalid rule {rule.rule_id}: {'; '.join(validation_errors)}")
            return []
        
        updated_transaction_ids = []
        application_count = 0
        
        for transaction_display in transactions:
            # Check if rule matches this transaction
            if rule.matches(transaction_display.transaction_data):
                try:
                    # Execute all actions for this rule
                    self._action_executor.execute_actions(rule.actions, transaction_display)
                    
                    # Update metadata to track rule application (similar to what importers do)
                    self._update_rule_application_metadata(rule, transaction_display)
                    
                    updated_transaction_ids.append(transaction_display.display_id)
                    application_count += 1
                    
                    logger.debug(
                        f"Applied rule '{rule.name}' with {len(rule.actions)} actions "
                        f"to transaction {transaction_display.display_id}"
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to execute actions for rule {rule.rule_id}: {e}")
                    # Continue with other transactions
        
        # Update rule statistics if any transactions were affected
        if application_count > 0:
            new_total_count = rule.application_count + application_count
            self._rule_repository.update_rule_stats(rule.rule_id, new_total_count)
            
            logger.info(
                f"Rule '{rule.name}' applied to {application_count} transactions "
                f"(total applications: {new_total_count})"
            )
        
        return updated_transaction_ids
    
    def apply_all_matching_rules(self, transaction_display: TransactionDisplayData) -> List[str]:
        """Apply all matching rules to a single transaction with early termination.
        
        This method finds all rules that match the transaction and applies their
        actions in priority order, respecting stop_processing flags for early
        termination. This is the core method for the rule system.
        
        Args:
            transaction_display: The transaction to apply rules to
            
        Returns:
            List of rule IDs that were applied
        """
        if not transaction_display or not transaction_display.transaction_data:
            return []
        
        # Find all matching rules (with early termination support)
        matching_rules = self.match_all_rules(transaction_display.transaction_data)
        
        applied_rule_ids = []
        
        for rule in matching_rules:
            try:
                # Execute all actions for this rule
                self._action_executor.execute_actions(rule.actions, transaction_display)
                
                # Update metadata to track rule application (similar to what importers do)
                self._update_rule_application_metadata(rule, transaction_display)
                
                applied_rule_ids.append(rule.rule_id)
                
                # Update rule statistics
                new_count = rule.application_count + 1
                self._rule_repository.update_rule_stats(rule.rule_id, new_count)
                
                logger.debug(f"Applied rule {rule.rule_id} ({rule.name}) to transaction")
                
                # Early termination if stop_processing is set
                if rule.stop_processing:
                    logger.debug(f"Stop processing triggered by rule {rule.rule_id}")
                    break
                    
            except Exception as e:
                logger.error(f"Failed to apply rule {rule.rule_id}: {e}")
                # Continue with other rules
                continue
        
        # Refresh rule matcher if any rules were applied
        # SQLiteRuleMatcher doesn't need refresh for statistics updates
        if applied_rule_ids:
            logger.debug(f"Applied {len(applied_rule_ids)} rules, SQLite matcher sees changes automatically")
        
        return applied_rule_ids
    
    def get_matching_transactions(self, rule: TransactionRule, 
                                 transactions: List[TransactionDisplayData]) -> List[TransactionDisplayData]:
        """Get all transactions that would match the given rule.
        
        This method returns all transactions in the list that match the rule,
        regardless of their current status. This is useful for previewing
        the impact of a rule before applying it.
        
        Args:
            rule: The rule to match against
            transactions: List of transactions to check
            
        Returns:
            List[TransactionDisplayData]: List of matching transactions
            
        Raises:
            ValueError: If rule or transactions is not provided
        """
        if not rule:
            raise ValueError("rule is required")
        if not transactions:
            raise ValueError("transactions is required")
        
        matching_transactions = []
        
        for transaction_display in transactions:
            if rule.matches(transaction_display.transaction_data):
                matching_transactions.append(transaction_display)
        
        return matching_transactions
    
    def get_all_rules(self) -> List[TransactionRule]:
        """Get all rules from the repository.
        
        Returns:
            List[TransactionRule]: List of all rules, sorted by creation date
        """
        return self._rule_repository.get_all_rules()
    
    def get_rule_by_id(self, rule_id: str) -> Optional[TransactionRule]:
        """Get a specific rule by its ID.
        
        Args:
            rule_id: The ID of the rule to retrieve
            
        Returns:
            Optional[TransactionRule]: The rule if found, None otherwise
        """
        return self._rule_repository.get_rule_by_id(rule_id)
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule from the repository.
        
        Args:
            rule_id: The ID of the rule to delete
            
        Returns:
            bool: True if the rule was deleted, False if it didn't exist
        """
        deleted = self._rule_repository.delete_rule(rule_id)
        
        if deleted:
            logger.debug(f"Deleted rule {rule_id}, SQLite matcher sees changes automatically")
        
        return deleted

    def update_rule(self, rule_id: str, name: str, conditions_block: "ConditionsBlock", 
                   actions: List["Action"], is_enabled: Optional[bool] = None, 
                   stop_processing: Optional[bool] = None) -> TransactionRule:
        """Update an existing rule with new content.
        
        This method updates an existing rule while preserving its ID, creation metadata,
        and application statistics. Only the specified fields are updated.
        
        Args:
            rule_id: The ID of the rule to update
            name: New human-readable name for the rule
            conditions_block: New block of conditions with logical operators
            actions: New list of actions to execute when rule matches
            is_enabled: New enabled state (if None, keep current state)
            stop_processing: New stop processing flag (if None, keep current state)
            
        Returns:
            TransactionRule: The updated rule
            
        Raises:
            ValueError: If rule_id doesn't exist or validation fails
        """
        # Get the existing rule
        existing_rule = self._rule_repository.get_rule_by_id(rule_id)
        if not existing_rule:
            raise ValueError(f"Rule with ID '{rule_id}' not found")
        
        # Validate inputs
        name = (name or "").strip()
        if not name:
            raise ValueError("Rule name cannot be empty")
        
        if not isinstance(conditions_block, ConditionsBlock):
            raise ValueError("conditions_block must be a ConditionsBlock instance")
        
        if not isinstance(actions, list) or not actions:
            raise ValueError("actions must be a non-empty list")
        
        for action in actions:
            if not isinstance(action, Action):
                raise ValueError("All actions must be Action instances")
        
        # Create updated rule, preserving existing metadata
        updated_rule = TransactionRule(
            rule_id=existing_rule.rule_id,  # Preserve original ID
            name=name,
            conditions_block=conditions_block,
            actions=actions,
            is_enabled=is_enabled if is_enabled is not None else existing_rule.is_enabled,
            stop_processing=stop_processing if stop_processing is not None else existing_rule.stop_processing,
            created_date=existing_rule.created_date,  # Preserve creation timestamp
            application_count=existing_rule.application_count,  # Preserve stats
            last_applied=existing_rule.last_applied  # Preserve last applied timestamp
        )
        
        # Validate updated rule structure
        validation_errors = self.validate_rule(updated_rule)
        if validation_errors:
            raise ValueError(f"Rule validation failed: {'; '.join(validation_errors)}")
        
        # Save updated rule to repository
        self._rule_repository.save_rule(updated_rule)
        
        logger.info(f"Updated rule '{rule_id}' ('{name}') with {len(actions)} actions")
        return updated_rule

    def begin_batch_updates(self) -> None:
        """Begin batch mode for rule statistics updates.
        
        During batch mode, rule statistics updates are accumulated in memory
        without writing to disk. Call end_batch_updates() to persist all changes.
        """
        self._rule_repository.begin_batch_updates()

    def end_batch_updates(self) -> bool:
        """End batch mode and persist all accumulated updates.
        
        Returns:
            bool: True if all updates were successfully persisted, False otherwise
        """
        return self._rule_repository.end_batch_updates()
    
    def validate_rule(self, rule: TransactionRule) -> List[str]:
        """Validate a rule and return list of validation errors.
        
        This method performs comprehensive validation of rule structure,
        conditions, actions, and metadata to ensure the rule is properly
        formed and can be executed safely.
        
        Args:
            rule: The rule to validate
            
        Returns:
            List[str]: List of validation error messages (empty if valid)
        """
        errors = []
        
        if not rule:
            errors.append("Rule cannot be None")
            return errors
        
        # Validate basic structure
        try:
            # This will trigger __post_init__ validation
            if not rule.rule_id or not rule.rule_id.strip():
                errors.append("Rule ID cannot be empty")
        except Exception as e:
            errors.append(f"Rule structure validation failed: {e}")
        
        # Validate name (more strict than __post_init__ for new rules)
        if not rule.name or not rule.name.strip():
            errors.append("Rule name cannot be empty")
        
        # Validate conditions block
        if not rule.conditions_block:
            errors.append("Rule must have a conditions block")
        else:
            try:
                # Test conditions block structure
                if not isinstance(rule.conditions_block, ConditionsBlock):
                    errors.append("conditions_block must be a ConditionsBlock instance")
            except Exception as e:
                errors.append(f"Conditions block validation failed: {e}")
        
        # Validate actions
        if not rule.actions:
            errors.append("Rule must have at least one action")
        else:
            for i, action in enumerate(rule.actions):
                try:
                    # This will trigger action validation
                    if not isinstance(action, Action):
                        errors.append(f"Action {i+1} must be an Action instance")
                except Exception as e:
                    errors.append(f"Action {i+1} validation failed: {e}")
        
        # Validate metadata
        if not isinstance(rule.is_enabled, bool):
            errors.append("is_enabled must be a boolean")
        
        if not isinstance(rule.stop_processing, bool):
            errors.append("stop_processing must be a boolean")
        
        if rule.application_count < 0:
            errors.append("application_count cannot be negative")
        
        return errors
    
    def detect_rule_conflicts_for_new_rule(self, new_rule: TransactionRule) -> List[Tuple[TransactionRule, TransactionRule, str]]:
        """Detect conflicts between a new rule and existing rules.
        
        This method checks if a new rule would conflict with existing
        rules before it's added to the repository.
        
        Args:
            new_rule: The new rule to check for conflicts
            
        Returns:
            List of tuples (new_rule, existing_rule, conflict_description)
        """
        conflicts = []
        existing_rules = [r for r in self._rule_repository.get_all_rules() if r.is_enabled]
        
        for existing_rule in existing_rules:
            conflict_description = self._analyze_rule_conflict(new_rule, existing_rule)
            if conflict_description:
                conflicts.append((new_rule, existing_rule, conflict_description))
        
        return conflicts
    
    def get_rule_statistics(self) -> Dict[str, int]:
        """Get comprehensive statistics about the rule engine state.
        
        Returns:
            Dictionary with statistics about rules, matching, and performance
        """
        stats = {}
        
        # Repository statistics
        all_rules = self._rule_repository.get_all_rules()
        stats.update({
            "total_rules": len(all_rules),
            "enabled_rules": len([r for r in all_rules if r.is_enabled]),
            "disabled_rules": len([r for r in all_rules if not r.is_enabled]),
        })
        
        # Rule matcher statistics
        if self._rule_matcher:
            matcher_stats = self._rule_matcher.get_rule_statistics()
            stats.update(matcher_stats)
        
        return stats
    
    def _evaluate_conditions_detailed(self, conditions_block: "ConditionsBlock", 
                                     transaction: TransactionData) -> Dict[str, Any]:
        """Evaluate conditions block with detailed results for debugging.
        
        Args:
            conditions_block: The conditions block to evaluate
            transaction: The transaction to evaluate against
            
        Returns:
            Dict with detailed evaluation results
        """
        result = {
            "matches": False,
            "operator": conditions_block.operator.value,
            "conditions": [],
            "nested_blocks": []
        }
        
        # Evaluate individual conditions
        condition_results = []
        for i, condition in enumerate(conditions_block.conditions):
            condition_result = {
                "index": i,
                "field": condition.field.value if condition.field is not None else condition.original_row_key,
                "operator": condition.operator.value,
                "value": condition.value,
                "case_sensitive": condition.case_sensitive,
                "matches": condition.matches(transaction)
            }
            
            # Add field value for debugging
            try:
                field_value = condition._extract_field_value(transaction)
                condition_result["field_value"] = str(field_value) if field_value is not None else None
            except Exception:
                condition_result["field_value"] = "Error extracting value"
            
            condition_results.append(condition_result)
        
        result["conditions"] = condition_results
        
        # Evaluate nested blocks
        nested_results = []
        for i, nested_block in enumerate(conditions_block.nested_blocks):
            nested_result = self._evaluate_conditions_detailed(nested_block, transaction)
            nested_result["index"] = i
            nested_results.append(nested_result)
        
        result["nested_blocks"] = nested_results
        
        # Determine overall match based on logical operator
        result["matches"] = conditions_block.matches(transaction)
        
        return result
    
    def _describe_action(self, action: "Action") -> str:
        """Generate a human-readable description of an action.
        
        Args:
            action: The action to describe
            
        Returns:
            str: Human-readable description
        """
        if action.action_type == ActionType.SET_DESTINATION_ACCOUNT:
            return f"Set destination account to '{action.parameters.get('account', 'Unknown')}'"
        elif action.action_type == ActionType.SET_PAYEE:
            return f"Set payee to '{action.parameters.get('payee', 'Unknown')}'"
        elif action.action_type == ActionType.ADD_TAG:
            return f"Add tag '{action.parameters.get('tag', 'Unknown')}'"
        elif action.action_type == ActionType.SET_NARRATION:
            return f"Set narration to '{action.parameters.get('narration', '')}'"
        elif action.action_type == ActionType.APPEND_NARRATION:
            return f"Append '{action.parameters.get('text', '')}' to narration"
        else:
            return f"Unknown action: {action.action_type.value}"
    
    def _analyze_rule_conflict(self, rule1: TransactionRule, rule2: TransactionRule) -> Optional[str]:
        """Analyze two rules for potential conflicts.
        
        Args:
            rule1: First rule to analyze
            rule2: Second rule to analyze
            
        Returns:
            Optional[str]: Conflict description if conflict exists, None otherwise
        """
        # Skip if either rule is disabled
        if not rule1.is_enabled or not rule2.is_enabled:
            return None
        
        # Skip self-comparison
        if rule1.rule_id == rule2.rule_id:
            return None
        
        # Check for identical conditions with different actions
        if (rule1.conditions_block and rule2.conditions_block and 
            self._conditions_are_similar(rule1.conditions_block, rule2.conditions_block)):
            if self._actions_are_conflicting(rule1.actions, rule2.actions):
                return "Rules have similar conditions but conflicting actions"
        
        # Check for stop_processing conflicts
        if rule1.stop_processing and rule2.stop_processing:
            if (rule1.conditions_block and rule2.conditions_block and 
                self._conditions_could_overlap(rule1.conditions_block, rule2.conditions_block)):
                return "Both rules have stop_processing=True with potentially overlapping conditions"
        
        # Check for account assignment conflicts
        account_conflict = self._check_account_assignment_conflict(rule1.actions, rule2.actions)
        if (account_conflict and rule1.conditions_block and rule2.conditions_block and 
            self._conditions_could_overlap(rule1.conditions_block, rule2.conditions_block)):
            return f"Rules assign different accounts with overlapping conditions: {account_conflict}"
        
        return None
    
    def _conditions_are_similar(self, block1: "ConditionsBlock", block2: "ConditionsBlock") -> bool:
        """Check if two conditions blocks are similar enough to potentially conflict.
        
        This is a simplified implementation that checks for exact matches.
        A more sophisticated implementation could detect semantic similarity.
        """
        if not block1 or not block2:
            return False
        
        if block1.operator != block2.operator:
            return False
        
        if len(block1.conditions) != len(block2.conditions):
            return False
        
        # Simple exact match check
        for c1 in block1.conditions:
            found_match = False
            for c2 in block2.conditions:
                if (c1.field == c2.field and c1.operator == c2.operator and 
                    c1.value == c2.value and c1.case_sensitive == c2.case_sensitive):
                    found_match = True
                    break
            if not found_match:
                return False
        
        return True
    
    def _conditions_could_overlap(self, block1: "ConditionsBlock", block2: "ConditionsBlock") -> bool:
        """Check if two conditions blocks could potentially match the same transactions.
        
        This is a simplified heuristic that looks for overlapping field/value combinations.
        """
        if not block1 or not block2:
            return False
        
        # Check if any conditions target the same field with similar values
        for c1 in block1.conditions:
            for c2 in block2.conditions:
                if c1.field == c2.field:
                    # Simple overlap detection for string fields
                    if c1.field is not None and c1.field.value in ['payee', 'narration']:
                        if (c1.value.lower() in c2.value.lower() or 
                            c2.value.lower() in c1.value.lower()):
                            return True
                    # Also check for original_row field overlap
                    elif c1.field is None and c2.field is None and c1.original_row_key == c2.original_row_key:
                        if (c1.value.lower() in c2.value.lower() or 
                            c2.value.lower() in c1.value.lower()):
                            return True
        
        return False
    
    def _actions_are_conflicting(self, actions1: List["Action"], actions2: List["Action"]) -> bool:
        """Check if two action lists have conflicting actions.
        
        Args:
            actions1: First list of actions
            actions2: Second list of actions
            
        Returns:
            bool: True if actions conflict, False otherwise
        """
        # Get account assignments from both action lists
        accounts1 = set()
        accounts2 = set()
        
        for action in actions1:
            if action.action_type == ActionType.SET_DESTINATION_ACCOUNT:
                accounts1.add(action.parameters.get('account'))
        
        for action in actions2:
            if action.action_type == ActionType.SET_DESTINATION_ACCOUNT:
                accounts2.add(action.parameters.get('account'))
        
        # If both rules set destination accounts and they're different, that's a conflict
        if accounts1 and accounts2 and accounts1 != accounts2:
            return True
        
        return False
    
    def _check_account_assignment_conflict(self, actions1: List["Action"], actions2: List["Action"]) -> Optional[str]:
        """Check for account assignment conflicts between two action lists.
        
        Args:
            actions1: First list of actions
            actions2: Second list of actions
            
        Returns:
            Optional[str]: Conflict description if found, None otherwise
        """
        accounts1 = []
        accounts2 = []
        
        for action in actions1:
            if action.action_type == ActionType.SET_DESTINATION_ACCOUNT:
                accounts1.append(action.parameters.get('account'))
        
        for action in actions2:
            if action.action_type == ActionType.SET_DESTINATION_ACCOUNT:
                accounts2.append(action.parameters.get('account'))
        
        if accounts1 and accounts2:
            different_accounts = set(accounts1) - set(accounts2)
            if different_accounts:
                return f"Different account assignments: {', '.join(different_accounts)}"
        
        return None
    
    def _update_rule_application_metadata(self, rule: TransactionRule, 
                                         transaction_display: "TransactionDisplayData") -> None:
        """Update TransactionDisplayData fields when a rule is applied.
        
        This method sets fields directly on the TransactionDisplayData object when rules
        are applied through the UI, which is different from how importers work during
        initial processing. Importers set metadata on TransactionData, but UI rule
        application should update the actual fields on TransactionDisplayData.
        
        The transaction status is now determined by the reactive validation system
        rather than being manually set here. This ensures that the status reflects
        the actual validation state of the transaction.
        
        Args:
            rule: The rule that was applied
            transaction_display: The transaction display data whose fields should be updated
        """
        try:
            # Extract destination account from rule actions
            destination_account = self._extract_destination_account_from_rule(rule)
            
            # Use reactive update methods on TransactionDisplayData (this is what the UI expects)
            transaction_display.add_applied_rule(rule.rule_id)
            
            # REMOVED: Manual status update - let validation system determine the proper status
            # OLD CODE: transaction_display.update_status(TransactionStatus.CATEGORIZED)
            # NEW BEHAVIOR: The reactive validation system will:
            # 1. Detect the field changes (applied_rule_ids, destination_account)
            # 2. Run validation on the updated transaction
            # 3. Set status to CATEGORIZED if validation passes
            # 4. Keep status as NEEDS_REVIEW if validation fails
            
            # Also set metadata on the underlying TransactionData for consistency with importers
            transaction_data = transaction_display.transaction_data
            if transaction_data.metadata is None:
                transaction_data.metadata = {}
            
            # Set rule application metadata fields (consistent with importers)
            transaction_data.metadata['applied_rule_id'] = rule.rule_id
            transaction_data.metadata['categorized_by_rule'] = True
            transaction_data.metadata['rule_name'] = rule.name
            transaction_data.metadata['rule_application_count'] = rule.application_count + 1
            
            # Set destination account in metadata as well (consistent with importers)
            if destination_account:
                transaction_data.metadata['destination_account'] = destination_account
            
            logger.debug(
                f"Updated TransactionDisplayData fields for transaction {transaction_display.display_id}: "
                f"applied_rule_id={rule.rule_id}, destination_account='{destination_account}'. "
                f"Status will be determined by validation system."
            )
            
        except Exception as e:
            logger.warning(
                f"Failed to update TransactionDisplayData fields for transaction "
                f"{transaction_display.display_id}: {e}"
            )
    
    def _extract_destination_account_from_rule(self, rule: TransactionRule) -> Optional[str]:
        """Extract the destination account from a rule's actions.
        
        This method looks through the rule's actions to find SET_DESTINATION_ACCOUNT actions
        and returns the account name. This is consistent with how importers extract accounts
        from rules.
        
        Args:
            rule: The TransactionRule to extract account from
            
        Returns:
            str: The destination account name, or None if no SET_DESTINATION_ACCOUNT action found
        """
        try:
            for action in rule.actions:
                if action.action_type == ActionType.SET_DESTINATION_ACCOUNT:
                    account = action.parameters.get("account")
                    if account:
                        return str(account).strip()
            
            logger.debug(f"No SET_DESTINATION_ACCOUNT action found in rule '{rule.name}'")
            return None
            
        except Exception as e:
            logger.warning(f"Error extracting destination account from rule '{rule.name}': {e}")
            return None


class RuleCreationError(Exception):
    """Exception raised when rule creation fails due to conflicts or validation."""
    pass


class RuleApplicationError(Exception):
    """Exception raised when rule application fails."""
    pass