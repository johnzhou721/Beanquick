"""
Rule Workspace - Composite component for rule management.

This module provides a unified interface for all rule-related functionality,
encapsulating the transaction categorizer, rule management container, and their coordination.
Uses the state machine pattern for robust state management.
"""
import logging
from typing import Optional, Callable, List

import toga
from toga.style import Pack
from toga.style.pack import COLUMN  # type: ignore

from beanquick.ui.importer.transaction_review.models import TransactionDisplayData
from beanquick.importers.rules import TransactionRule
from beanquick.importers.rules.engine import RuleEngine

from .rule_state_manager import RuleStateManager, RuleState, RuleStateTransition
from ..transaction_categorizer import TransactionCategorizer  
from .rule_management_container import RuleManagementContainer
from .multi_rule_view_container import MultiRuleViewContainer

logger = logging.getLogger(__name__)


class RuleWorkspace:
    """Composite component that encapsulates all rule management functionality.
    
    This component provides a clean, unified interface for rule management by:
    - Managing state through a central state machine
    - Coordinating between categorizer and container components
    - Handling all rule-related events and transitions
    - Providing simple interface for parent components
    
    Key Benefits:
    - Single source of truth for rule state
    - No race conditions or timing issues
    - Clear separation of concerns
    - Easy to test and maintain
    """
    
    def __init__(
        self,
        account_completer,
        rule_engine: RuleEngine,
        on_rule_save: Callable[[TransactionRule], None],
        on_scroll_to_bottom: Optional[Callable[[], None]] = None,
    ):
        """Initialize the rule workspace.
        
        Args:
            account_completer: Service for account auto-completion
            rule_engine: Engine for rule creation, validation, and management
            on_rule_save: Callback when rule is successfully saved
            on_scroll_to_bottom: Optional callback to request scrolling to bottom
        """
        # External dependencies
        self._account_completer = account_completer
        self._rule_engine = rule_engine
        self._on_rule_save = on_rule_save
        self._on_scroll_to_bottom = on_scroll_to_bottom
        
        # State management
        self._state_manager = RuleStateManager()
        self._state_manager.add_observer(self._on_state_changed)
        
        # UI components
        self._transaction_categorizer: Optional[TransactionCategorizer] = None
        self._rule_management_container: Optional[RuleManagementContainer] = None
        self._multi_rule_view_container: Optional[MultiRuleViewContainer] = None
        self._container_widget: Optional[toga.Box] = None
        
        # Current transaction context
        self._current_transaction_data: Optional[TransactionDisplayData] = None
        self._all_transactions: List[TransactionDisplayData] = []
        
        # Initialize components
        self._create_components()
        
        logger.debug("RuleWorkspace initialized")
    
    def update_data(self, transaction_display_data):
        """Update both components with new transaction data."""
        self._current_transaction_data = transaction_display_data
        if self._transaction_categorizer:
            self._transaction_categorizer.update_data(transaction_display_data)
        if self._rule_management_container:
            self._rule_management_container.update_data(transaction_display_data)
        if self._multi_rule_view_container:
            self._multi_rule_view_container.update_data(transaction_display_data)
    
    def set_all_transactions(self, transactions: List[TransactionDisplayData]) -> None:
        """Set the complete list of transactions for rule application.
        
        Args:
            transactions: Complete list of TransactionDisplayData objects
        """
        self._all_transactions = transactions or []
        
        # Pass the transactions to the multi-rule view container
        if self._multi_rule_view_container:
            self._multi_rule_view_container.set_all_transactions(self._all_transactions)
        
        logger.debug(f"RuleWorkspace set with {len(self._all_transactions)} transactions")
    
    def clear_fields(self):
        """Clear fields in the transaction categorizer."""
        if self._transaction_categorizer:
            self._transaction_categorizer.clear_fields()
    
    @property
    def is_rule_creation_enabled(self) -> bool:
        """Check if rule creation switch is enabled."""
        if self._transaction_categorizer:
            return self._transaction_categorizer.get_create_rule_value()
        return False
    
    @property
    def is_view_mode(self) -> bool:
        """Check if rule management container is in view mode."""
        if self._rule_management_container:
            return self._rule_management_container.is_view_mode
        return False
    
    def _create_components(self) -> None:
        """Create and configure child components."""
        # Create transaction categorizer
        self._transaction_categorizer = TransactionCategorizer(
            account_completer=self._account_completer
        )
        
        # Set up switch observer
        self._transaction_categorizer.add_switch_observer(self._on_switch_changed)
        
        # Create rule management container (for creating new rules)
        self._rule_management_container = RuleManagementContainer(
            rule_engine=self._rule_engine,
            on_rule_created=self._handle_rule_created,
            on_cancel=self._handle_rule_cancel,
            on_rule_deleted=self._handle_rule_deleted
        )
        
        # Create multi-rule view container (for viewing existing rules)
        self._multi_rule_view_container = MultiRuleViewContainer(
            rule_engine=self._rule_engine,
            on_rule_deleted=self._handle_rule_deleted,
            on_rule_created=self._handle_rule_created,
            on_rule_edited=self._handle_rule_edited,
            on_scroll_to_bottom=self._on_scroll_to_bottom,
            on_no_valid_rules=self._handle_no_valid_rules
        )
        
        logger.debug("RuleWorkspace components created")
    
    def create_widget(self) -> toga.Box:
        """Create the composite widget.
        
        Returns:
            toga.Box: Container with all rule management UI
        """
        if self._container_widget:
            return self._container_widget
        
        # Create main container
        container = toga.Box(
            style=Pack(direction=COLUMN, flex=1)
        )
        self._container_widget = container
        
        # Always add the categorizer (it handles its own switch visibility)
        if self._transaction_categorizer:
            container.add(self._transaction_categorizer.create_widget())
        
        # The rule management container will be added/removed based on state
        self._update_ui_for_current_state()
        
        return container
    
    def update_transaction(self, transaction_data: Optional[TransactionDisplayData]) -> None:
        """Update the workspace with new transaction data.
        
        This is the main entry point for updating the workspace state.
        The state machine will determine the appropriate state based on the transaction.
        
        Args:
            transaction_data: Transaction data to display (None to clear)
        """
        self._current_transaction_data = transaction_data
        
        if transaction_data is None:
            # Clear state
            self._state_manager.transition_to(RuleState.NO_RULE, "transaction_cleared")
            self._update_components(None)
            return
        
        # Update components with new data
        self._update_components(transaction_data)
        
        # Determine appropriate state based on transaction
        if transaction_data.applied_rule_ids:
            # Transaction has rules applied - show in view mode for all rules
            self._state_manager.transition_to(
                RuleState.VIEWING_RULES, 
                "transaction_has_rules",
                context=transaction_data.applied_rule_ids
            )
        else:
            # No rule applied - show switch but not container
            self._state_manager.transition_to(RuleState.NO_RULE, "transaction_no_rule")
    
    def clear(self) -> None:
        """Clear the workspace and reset to initial state."""
        self._current_transaction_data = None
        self._state_manager.reset()
        self._update_components(None)
    
    def _update_components(self, transaction_data: Optional[TransactionDisplayData]) -> None:
        """Update child components with transaction data.
        
        Args:
            transaction_data: Transaction data to update components with
        """
        if self._transaction_categorizer:
            if transaction_data:
                self._transaction_categorizer.update_data(transaction_data)
            else:
                self._transaction_categorizer.clear_fields()
        
        if self._rule_management_container:
            self._rule_management_container.update_data(transaction_data)
        
        if self._multi_rule_view_container:
            self._multi_rule_view_container.update_data(transaction_data)
    
    def _on_state_changed(self, transition: RuleStateTransition) -> None:
        """Handle state machine transitions.
        
        Args:
            transition: The state transition that occurred
        """
        logger.debug(f"RuleWorkspace state changed: {transition.from_state} → {transition.to_state}")
        self._update_ui_for_current_state()
    
    def _update_ui_for_current_state(self) -> None:
        """Update UI visibility based on current state."""
        if not self._container_widget:
            return
        
        state = self._state_manager.current_state
        
        # Get widgets for both containers
        rule_mgmt_widget = None
        multi_rule_widget = None
        
        if self._rule_management_container:
            rule_mgmt_widget = self._rule_management_container.create_widget()
        
        if self._multi_rule_view_container:
            multi_rule_widget = self._multi_rule_view_container.create_widget()
        
        # Check current visibility
        rule_mgmt_visible = rule_mgmt_widget and rule_mgmt_widget in self._container_widget.children
        multi_rule_visible = multi_rule_widget and multi_rule_widget in self._container_widget.children
        
        # Determine which container should be visible based on state
        should_show_rule_mgmt = state == RuleState.SWITCH_ENABLED
        should_show_multi_rule = state == RuleState.VIEWING_RULES
        
        # Remove any currently visible container that shouldn't be visible
        if rule_mgmt_visible and not should_show_rule_mgmt:
            self._container_widget.remove(rule_mgmt_widget)
            logger.debug(f"Rule management container hidden for state: {state}")
        
        if multi_rule_visible and not should_show_multi_rule:
            self._container_widget.remove(multi_rule_widget)
            logger.debug(f"Multi-rule view container hidden for state: {state}")
        
        # Add the appropriate container if it should be visible
        if should_show_rule_mgmt and not rule_mgmt_visible and rule_mgmt_widget:
            self._container_widget.add(rule_mgmt_widget)
            logger.debug(f"Rule management container shown for state: {state}")
        
        if should_show_multi_rule and not multi_rule_visible and multi_rule_widget:
            self._container_widget.add(multi_rule_widget)
            logger.debug(f"Multi-rule view container shown for state: {state}")
    
    def _on_switch_changed(self, enabled: bool) -> None:
        """Handle rule creation switch changes.
        
        Args:
            enabled: True if switch is enabled, False otherwise
        """
        current_state = self._state_manager.current_state
        
        # Only handle switch changes when not in view mode
        if current_state == RuleState.VIEWING_RULES:
            logger.debug("Ignoring switch change in view mode")
            return
        
        if enabled:
            self._state_manager.transition_to(RuleState.SWITCH_ENABLED, "switch_enabled")
        else:
            self._state_manager.transition_to(RuleState.NO_RULE, "switch_disabled")
    
    def _handle_rule_created(self, rule: TransactionRule) -> Optional[List[str]]:
        """Handle rule creation events from the container.
        
        This method handles state management and UI updates for rule creation.
        It does NOT apply the rule to transactions since that is handled by
        MultiRuleViewContainer._handle_rule_created() to avoid double application.
        
        Args:
            rule: The created rule
            
        Returns:
            Optional[List[str]]: None since rule application is handled elsewhere
        """
        logger.info(f"Rule created in workspace: {rule.name}")
        
        # NOTE: Rule application is handled by MultiRuleViewContainer._handle_rule_created()
        # to avoid duplicate rule application. This method only handles workspace state.
        updated_transaction_ids = None
        
        # Handle save logic: update workspace state
        if self._current_transaction_data:
            # Check if current transaction would be affected by the rule by testing if it matches
            current_transaction_affected = False
            try:
                if rule and rule.matches(self._current_transaction_data.transaction_data):
                    current_transaction_affected = True
            except Exception as e:
                logger.warning(f"Error checking if rule matches current transaction: {e}")
            
            if current_transaction_affected:
                # Transition to viewing all rules (including the newly created one)
                self._state_manager.transition_to(
                    RuleState.VIEWING_RULES,
                    "rule_saved",
                    context=self._current_transaction_data.applied_rule_ids
                )
            else:
                # Rule created but didn't affect current transaction - stay in no rule state
                self._state_manager.transition_to(RuleState.NO_RULE, "rule_saved_no_match")
            
            # Update components to reflect the new state
            self._update_components(self._current_transaction_data)
        
        # Notify external callback about the save
        if self._on_rule_save:
            self._on_rule_save(rule)
        
        return updated_transaction_ids

    def _handle_rule_cancel(self) -> None:
        """Handle rule cancellation events from the container."""
        logger.debug("Rule creation cancelled")
        
        # Reset switch to disabled state
        if self._transaction_categorizer and self._transaction_categorizer._create_rule_switch:
            self._transaction_categorizer._create_rule_switch.value = False
        
        # Transition back to no rule state
        self._state_manager.transition_to(RuleState.NO_RULE, "rule_cancelled")
    
    def _handle_rule_deleted(self, rule_id: str) -> None:
        """Handle rule deletion events from the container.
        
        Args:
            rule_id: ID of the deleted rule
        """
        logger.info(f"Rule deleted in workspace: {rule_id}")
        
        # Transition to deleting state briefly
        self._state_manager.transition_to(RuleState.DELETING_RULE, "rule_deleted", context=rule_id)
        
        # Remove applied_rule_id from current transaction if it matches
        if (self._current_transaction_data and 
            rule_id in self._current_transaction_data.applied_rule_ids):
            
            self._current_transaction_data.remove_applied_rule(rule_id)
            
            # Update components with the updated transaction
            self._update_components(self._current_transaction_data)
            
            # Check if there are still rules applied after deletion
            if self._current_transaction_data.applied_rule_ids:
                # Still have rules applied - stay in viewing rules state
                self._state_manager.transition_to(
                    RuleState.VIEWING_RULES, 
                    "rule_deletion_complete_with_remaining_rules",
                    context=self._current_transaction_data.applied_rule_ids
                )
            else:
                # No more rules applied - reset switch and transition to no rule state
                if self._transaction_categorizer and self._transaction_categorizer._create_rule_switch:
                    self._transaction_categorizer._create_rule_switch.value = False
                self._state_manager.transition_to(RuleState.NO_RULE, "rule_deletion_complete_no_remaining_rules")
        else:
            # Rule wasn't applied to current transaction - just transition to no rule state
            self._state_manager.transition_to(RuleState.NO_RULE, "rule_deletion_complete")
    
    def _handle_rule_edited(self, rule: TransactionRule) -> Optional[List[str]]:
        """Handle rule editing events from the container.
        
        This method handles rule updates by re-applying the updated rule to all transactions
        using the rule engine, ensuring consistency across the transaction set.
        
        Args:
            rule: The updated rule
            
        Returns:
            Optional[List[str]]: List of updated transaction IDs if rule was applied
        """
        logger.info(f"Rule edited in workspace: {rule.name} ({rule.rule_id})")
        
        # Apply rule to all transactions directly using the rule engine
        updated_transaction_ids = None
        if self._all_transactions:
            try:
                # Use the rule engine to apply the updated rule to all transactions
                # This ensures proper action execution and metadata updates
                updated_transaction_ids = self._rule_engine.apply_rule_to_transactions(rule, self._all_transactions)
                
                logger.info(f"Updated rule re-applied to {len(updated_transaction_ids)} transactions")
            except Exception as e:
                logger.error(f"Error applying updated rule to transactions: {e}")
                updated_transaction_ids = []
        
        # Handle save logic: update workspace state
        if self._current_transaction_data:
            # If current transaction has this rule applied, refresh its display
            if rule.rule_id in self._current_transaction_data.applied_rule_ids:
                # Update components to reflect any changes
                self._update_components(self._current_transaction_data)
                logger.debug(f"Refreshed current transaction display after rule edit")
        
        # Notify external callback about the rule save
        if self._on_rule_save:
            try:
                self._on_rule_save(rule)
            except Exception as e:
                logger.error(f"Error in rule save callback: {e}")
        
        return updated_transaction_ids

    def _handle_no_valid_rules(self) -> None:
        """Handle the case when no valid rules are found for a transaction.
        
        This is called by MultiRuleViewContainer when a transaction has applied_rule_ids
        but none of those rules exist in the repository. In this case, we should
        transition to NO_RULE state since there are effectively no rules to display.
        """
        logger.info("No valid rules found for transaction - transitioning to NO_RULE state")
        
        # Transition to NO_RULE state since there are no valid rules to display
        self._state_manager.transition_to(RuleState.NO_RULE, "no_valid_rules_found")
        
        # Update the transaction data to clear the invalid rule IDs
        if self._current_transaction_data:
            self._current_transaction_data.update_applied_rules([])
            
            # Reset the rule creation switch since we're now in NO_RULE state
            if self._transaction_categorizer and self._transaction_categorizer._create_rule_switch:
                self._transaction_categorizer._create_rule_switch.value = False
    
    def cleanup(self) -> None:
        """Clean up resources and observers."""
        if self._transaction_categorizer:
            self._transaction_categorizer.remove_switch_observer(self._on_switch_changed)
            self._transaction_categorizer.clear_fields()
        
        if self._rule_management_container:
            self._rule_management_container.cleanup()
        
        if self._multi_rule_view_container:
            self._multi_rule_view_container.cleanup()
        
        self._state_manager.remove_observer(self._on_state_changed)
        
        logger.debug("RuleWorkspace cleanup completed")
    
    # Properties for external access
    
    @property
    def current_state(self) -> RuleState:
        """Get the current rule state."""
        return self._state_manager.current_state
    
    @property
    def transaction_categorizer(self) -> Optional[TransactionCategorizer]:
        """Get the transaction categorizer component."""
        return self._transaction_categorizer
    
    @property
    def rule_management_container(self) -> Optional[RuleManagementContainer]:
        """Get the rule management container component."""
        return self._rule_management_container
    
    @property
    def multi_rule_view_container(self) -> Optional[MultiRuleViewContainer]:
        """Get the multi-rule view container component."""
        return self._multi_rule_view_container
