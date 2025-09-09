"""
Multi-Rule View Container - Displays multiple rules for a transaction.

This module provides a container that displays multiple RuleManagementContainer instances,
each showing a rule that was applied to the transaction. This provides complete visibility
into all rules affecting a transaction and allows individual rule management.
"""
import logging
from typing import Optional, Callable, List, Dict

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD  # type: ignore
from toga.constants import DODGERBLUE

from beanquick.importers.rules import TransactionRule
from beanquick.importers.rules.engine import RuleEngine
from beanquick.ui.importer.transaction_review.models import TransactionDisplayData

from .rule_management_container import RuleManagementContainer

logger = logging.getLogger(__name__)

WIDGET_SPACING = 10


class MultiRuleViewContainer:
    """Container that displays multiple rules applied to a transaction with rule creation capability.
    
    This component creates and manages multiple RuleManagementContainer instances,
    each showing a rule in read-only view mode. It provides a unified interface
    for viewing all rules that have been applied to a transaction and allows
    creation of new rules for the same transaction.
    
    Key features:
    - Displays all applied rules in individual containers
    - Each rule container shows full rule details (conditions, actions)
    - Individual delete buttons for each rule
    - Expandable "Add New Rule" section with full rule creation capabilities
    - Progressive disclosure UI pattern (view rules first, create when needed)
    - Clean vertical layout with clear separation
    - Automatic layout updates when rules are added/removed
    - Seamless integration with existing rule creation workflow
    """
    
    def __init__(
        self,
        rule_engine: RuleEngine,
        on_rule_deleted: Optional[Callable[[str], None]] = None,
        on_rule_created: Optional[Callable[[TransactionRule], Optional[List[str]]]] = None,
        on_rule_edited: Optional[Callable[[TransactionRule], Optional[List[str]]]] = None,
        on_scroll_to_bottom: Optional[Callable[[], None]] = None,
        on_no_valid_rules: Optional[Callable[[], None]] = None,
    ):
        """Initialize the multi-rule view container.
        
        Args:
            rule_engine: Engine for rule fetching and management
            on_rule_deleted: Optional callback when a rule is deleted
            on_rule_created: Optional callback when a rule is successfully created
            on_rule_edited: Optional callback when a rule is successfully edited
            on_scroll_to_bottom: Optional callback to request scrolling to bottom
            on_no_valid_rules: Optional callback when no valid rules are found for a transaction
        """
        self._rule_engine = rule_engine
        self._on_rule_deleted = on_rule_deleted
        self._on_rule_created = on_rule_created
        self._on_rule_edited = on_rule_edited
        self._on_scroll_to_bottom = on_scroll_to_bottom
        self._on_no_valid_rules = on_no_valid_rules
        
        # Container state
        self._rule_ids: List[str] = []
        self._rule_containers: Dict[str, RuleManagementContainer] = {}
        self._transaction_data: Optional[TransactionDisplayData] = None
        self._all_transactions: List[TransactionDisplayData] = []
        
        # Container state
        self._rule_ids: List[str] = []
        self._rule_containers: Dict[str, RuleManagementContainer] = {}
        self._transaction_data: Optional[TransactionDisplayData] = None
        
        # Rule creation state
        self._is_creation_expanded: bool = False
        self._rule_creation_container: Optional[RuleManagementContainer] = None
        
        # UI components
        self._main_container: Optional[toga.Box] = None
        self._rules_container: Optional[toga.Box] = None
        self._header_section: Optional[toga.Box] = None
        self._header_label: Optional[toga.Label] = None
        self._add_rule_button: Optional[toga.Button] = None
        self._creation_section: Optional[toga.Box] = None
        
        logger.debug("MultiRuleViewContainer initialized")
    
    def update_data(self, transaction_data: Optional[TransactionDisplayData]) -> None:
        """Update the container with new transaction data.
        
        Args:
            transaction_data: Transaction data containing applied rule IDs
        """
        # Store previous rule IDs for comparison
        previous_rule_ids = self._rule_ids.copy()
        
        # Store previous transaction data
        previous_transaction_data = self._transaction_data
        
        self._transaction_data = transaction_data
        
        if not transaction_data or not transaction_data.applied_rule_ids:
            new_rule_ids = []
        else:
            new_rule_ids = transaction_data.applied_rule_ids.copy()
        
        # Check if rule IDs actually changed
        rule_ids_changed = previous_rule_ids != new_rule_ids
        
        # Special case: If our current _rule_ids already match the new_rule_ids,
        # it means we've already handled this change through an optimized method
        # (like _add_rule_container or _remove_rule_container)
        already_handled = self._rule_ids == new_rule_ids
        
        logger.debug(f"MultiRuleViewContainer updated with {len(new_rule_ids)} rules (changed: {rule_ids_changed}, already_handled: {already_handled})")
        
        # Update rule IDs to match the transaction data
        self._rule_ids = new_rule_ids
        
        # Reset rule creation section when new data comes in
        if self._is_creation_expanded:
            self._collapse_rule_creation()
        
        # Only rebuild the UI if the rule IDs actually changed AND we haven't already handled it
        if rule_ids_changed and not already_handled:
            logger.debug("Rule IDs changed and not already handled, rebuilding UI")
            self._rebuild_rules_ui()
        else:
            if already_handled:
                logger.debug("Rule IDs change already handled by optimized method, skipping rebuild")
            else:
                logger.debug("Rule IDs unchanged, skipping UI rebuild")
            # Just update the header in case rule names changed
            self._update_header_count()
    
    def set_all_transactions(self, transactions: List[TransactionDisplayData]) -> None:
        """Set the complete list of transactions for rule application.
        
        Args:
            transactions: Complete list of TransactionDisplayData objects
        """
        self._all_transactions = transactions or []
        logger.debug(f"MultiRuleViewContainer set with {len(self._all_transactions)} transactions")
    
    def create_widget(self) -> toga.Box:
        """Create the main widget for the multi-rule view.
        
        Returns:
            toga.Box: Container widget with all rule displays
        """
        if self._main_container:
            return self._main_container
        
        # Create main container
        main_container = toga.Box(
            style=Pack(direction=COLUMN, margin=(0, 0, WIDGET_SPACING))
        )
        self._main_container = main_container
        
        # Create enhanced header section with "Add New Rule" button
        self._create_enhanced_header()
        
        # Create container for individual rule containers
        rules_container = toga.Box(
            style=Pack(direction=COLUMN, margin_top=WIDGET_SPACING)
        )
        self._rules_container = rules_container
        
        # Create expandable creation section
        creation_section = toga.Box(
            style=Pack(direction=COLUMN, margin_top=WIDGET_SPACING)
        )
        self._creation_section = creation_section
        
        # Add components to main container
        main_container.add(self._header_section)
        main_container.add(rules_container)
        main_container.add(creation_section)
        
        # Build initial content
        self._rebuild_rules_ui()
        
        return main_container
    
    def _create_header(self) -> None:
        """Create the header section showing rule count."""
        rule_count = len(self._rule_ids)
        if rule_count == 0:
            header_text = "No rules applied"
        elif rule_count == 1:
            header_text = "Applied Rule (1)"
        else:
            header_text = f"Applied Rules ({rule_count})"
        
        self._header_label = toga.Label(
            header_text,
            style=Pack(
                font_weight=BOLD,
                margin_bottom=WIDGET_SPACING // 2
            )
        )
    
    def _create_enhanced_header(self) -> None:
        """Create the enhanced header section with title and Add New Rule button."""
        # Create header container
        header_container = toga.Box(
            style=Pack(
                direction=ROW,
                margin_bottom=WIDGET_SPACING // 2
            )
        )
        self._header_section = header_container
        
        # Create header label
        self._create_header()
        
        # Create "New Rule" button
        self._add_rule_button = toga.Button(
            "New Rule",
            on_press=self._toggle_rule_creation,
            style=Pack(
                margin_left=WIDGET_SPACING,
                background_color=DODGERBLUE
            )
        )
        
        # Add components to header container
        header_container.add(self._header_label)
        header_container.add(toga.Box(style=Pack(flex=1)))  # Spacer to push button to right
        header_container.add(self._add_rule_button)
    
    def _rebuild_rules_ui(self) -> None:
        """Rebuild the rules UI to show current applied rules."""
        if not self._rules_container:
            return
        
        # Clear existing content
        self._rules_container.clear()
        
        # Clear old rule containers
        for container in self._rule_containers.values():
            container.cleanup()
        self._rule_containers.clear()
        
        # Track which rules were successfully found and displayed
        successfully_displayed_rules = []
        
        # Create rule containers for each applied rule
        for i, rule_id in enumerate(self._rule_ids):
            try:
                # Create a rule container for this rule
                rule_container = self._create_rule_container(rule_id, i)
                if rule_container:
                    self._rule_containers[rule_id] = rule_container
                    successfully_displayed_rules.append(rule_id)
                    
                    # Add to UI with spacing
                    display_index = len(successfully_displayed_rules) - 1  # Use actual display index
                    if display_index > 0:
                        # Add separator between rules
                        separator = toga.Divider(
                            style=Pack(margin=(WIDGET_SPACING, 0))
                        )
                        self._rules_container.add(separator)
                    
                    self._rules_container.add(rule_container.create_widget())
                    
            except Exception as e:
                logger.error(f"Failed to create container for rule {rule_id}: {e}")
                continue
        
        # Update our internal rule list to only contain successfully displayed rules
        original_rule_count = len(self._rule_ids)
        self._rule_ids = successfully_displayed_rules
        
        # Update header to reflect actual displayed rule count
        self._update_header_count()
        
        logger.debug(f"Rebuilt rules UI with {len(self._rule_containers)} rule containers")
        
        # If we had rule IDs but none were successfully displayed, notify the parent
        if original_rule_count > 0 and len(self._rule_ids) == 0:
            logger.warning(f"Transaction had {original_rule_count} applied rule IDs but none were found in repository")
            if self._on_no_valid_rules:
                self._on_no_valid_rules()
    
    def _toggle_rule_creation(self, widget: toga.Button) -> None:
        """Toggle between collapsed/expanded rule creation.
        
        Args:
            widget: The button that was pressed
        """
        if self._is_creation_expanded:
            self._collapse_rule_creation()
        else:
            self._expand_rule_creation()
    
    def _expand_rule_creation(self) -> None:
        """Show rule creation UI."""
        logger.debug("Expanding rule creation section")
        self._is_creation_expanded = True
        
        # Update button text
        if self._add_rule_button:
            self._add_rule_button.text = "Cancel New Rule"
        
        # Create and show rule creation container
        if not self._rule_creation_container:
            self._rule_creation_container = RuleManagementContainer(
                rule_engine=self._rule_engine,
                on_rule_created=self._handle_rule_created,
                on_cancel=self._handle_rule_creation_cancelled
            )
            # Update with transaction data BUT without applied_rule_ids to ensure edit mode
            if self._transaction_data:
                # Create a copy of transaction data without applied rules for rule creation
                creation_transaction_data = TransactionDisplayData(
                    transaction_data=self._transaction_data.transaction_data,
                    applied_rule_ids=[]  # Empty list ensures edit mode, not view mode
                )
                self._rule_creation_container.update_data(creation_transaction_data)
            else:
                self._rule_creation_container.update_data(None)
        
        # Add creation widget to UI
        if self._creation_section and self._rule_creation_container:
            # Add a visual separator
            separator = toga.Divider(
                style=Pack(margin=(WIDGET_SPACING, 0))
            )
            self._creation_section.add(separator)
            
            # Add the rule creation widget
            creation_widget = self._rule_creation_container.create_widget()
            self._creation_section.add(creation_widget)
            
            # Request scroll to bottom to show the new rule creation section
            if self._on_scroll_to_bottom:
                logger.debug("Requesting scroll to bottom after rule creation expansion")
                self._on_scroll_to_bottom()
            else:
                logger.debug("No scroll callback available")
    
    def _collapse_rule_creation(self) -> None:
        """Hide rule creation UI."""
        logger.debug("Collapsing rule creation section")
        self._is_creation_expanded = False
        
        # Update button text
        if self._add_rule_button:
            self._add_rule_button.text = "New Rule"
        
        # Clear creation section
        if self._creation_section:
            self._creation_section.clear()
        
        # Clean up creation container
        if self._rule_creation_container:
            self._rule_creation_container.cleanup()
            self._rule_creation_container = None
    
    def _handle_rule_created(self, rule: TransactionRule) -> Optional[List[str]]:
        """Handle successful rule creation.
        
        This method directly applies the rule to all transactions using the rule engine,
        eliminating the need for callback chains and making the logic straightforward.
        
        Args:
            rule: The newly created rule
            
        Returns:
            Optional[List[str]]: List of updated transaction IDs if rule was applied
        """
        logger.info(f"New rule created: {rule.rule_id} ({rule.name})")
        
        # Apply rule to all transactions directly using the rule engine
        updated_transaction_ids = None
        if self._all_transactions:
            try:
                updated_transaction_ids = self._rule_engine.apply_rule_to_transactions(
                    rule, self._all_transactions
                )
                if updated_transaction_ids:
                    logger.info(f"Rule applied to {len(updated_transaction_ids)} transactions")
            except Exception as e:
                logger.error(f"Error applying rule: {e}")
                # Continue with local UI updates even if application fails
        
        # Update local transaction state if current transaction was affected
        if self._transaction_data and updated_transaction_ids:
            # Check if current transaction was in the updated list
            current_tx_updated = self._transaction_data.display_id in updated_transaction_ids
            if current_tx_updated and rule.rule_id not in self._transaction_data.applied_rule_ids:
                self._transaction_data.add_applied_rule(rule.rule_id)
                
                # Add new rule container to UI (optimized approach)
                if self._add_rule_container(rule.rule_id):
                    logger.debug(f"Successfully added rule container for new rule {rule.rule_id}")
                else:
                    logger.warning(f"Failed to add rule container for {rule.rule_id}, falling back to rebuild")
                    # Fallback to rebuild if targeted addition failed
                    self._rule_ids.append(rule.rule_id)  # Ensure it's in our tracking
                    self._rebuild_rules_ui()
        
        # Collapse creation section
        self._collapse_rule_creation()
        
        # Notify parent component about the rule creation (for UI coordination)
        if self._on_rule_created:
            self._on_rule_created(rule)
        
        # Return the updated transaction IDs for external coordination if needed
        return updated_transaction_ids
    
    def _handle_rule_creation_cancelled(self) -> None:
        """Handle rule creation cancellation."""
        logger.debug("Rule creation cancelled")
        self._collapse_rule_creation()
    
    def _create_rule_container(self, rule_id: str, index: int) -> Optional[RuleManagementContainer]:
        """Create a RuleManagementContainer for a specific rule.
        
        Args:
            rule_id: ID of the rule to display
            index: Index of this rule in the list (for display purposes)
            
        Returns:
            RuleManagementContainer configured for view mode, or None if rule not found
        """
        try:
            # Fetch the rule from the engine
            rule = self._rule_engine.get_rule_by_id(rule_id)
            if not rule:
                logger.warning(f"Rule {rule_id} not found in repository")
                return None
            
            # Create container for this rule
            container = RuleManagementContainer(
                rule_engine=self._rule_engine,
                on_rule_created=lambda r: None,  # No-op since this is view mode
                on_cancel=lambda: None,  # No-op since this is view mode
                on_rule_deleted=lambda rule_id=rule_id: self._handle_rule_deleted(rule_id),
                on_rule_edited=lambda r: self._handle_rule_edited(r)
            )
            
            # Create a transaction data object that will put the container in view mode
            # We need transaction data to exist for the container to work properly
            if not self._transaction_data or not self._transaction_data.transaction_data:
                logger.warning(f"No transaction data available for rule {rule_id}")
                return None
            
            # Create a minimal transaction data with just this rule applied
            view_transaction_data = TransactionDisplayData(
                transaction_data=self._transaction_data.transaction_data,
                applied_rule_ids=[rule_id]  # Only this rule for this container
            )
            
            # Update the container with the transaction data (this will put it in view mode)
            container.update_data(view_transaction_data)
            
            logger.debug(f"Created rule container for rule {rule_id} ({rule.name})")
            return container
            
        except Exception as e:
            logger.error(f"Error creating rule container for {rule_id}: {e}")
            return None
    
    def _handle_rule_deleted(self, rule_id: str) -> None:
        """Handle deletion of a specific rule.
        
        Args:
            rule_id: ID of the rule that was deleted
        """
        logger.info(f"Rule {rule_id} deleted from multi-rule view")
        
        # Remove the specific rule container from UI (optimized approach)
        if self._remove_rule_container(rule_id):
            logger.debug(f"Successfully removed rule container for {rule_id}")
        else:
            logger.warning(f"Failed to remove rule container for {rule_id}, falling back to rebuild")
            # Fallback to rebuild if targeted removal failed
            self._rebuild_rules_ui()
        
        # NOTE: Do NOT modify transaction data here - let the parent workspace handle it
        # The workspace will modify the transaction data and then update all components
        # This prevents double-modification which causes the remaining rules bug
        
        # Notify parent component (which will handle transaction data updates)
        if self._on_rule_deleted:
            self._on_rule_deleted(rule_id)
    
    def _handle_rule_edited(self, rule: TransactionRule) -> Optional[List[str]]:
        """Handle editing of a specific rule.
        
        Args:
            rule: The updated rule
            
        Returns:
            Optional[List[str]]: List of updated transaction IDs if rule was applied
        """
        logger.info(f"Rule {rule.rule_id} edited in multi-rule view")
        
        # Apply rule to all transactions directly using the rule engine
        updated_transaction_ids = None
        if self._all_transactions:
            try:
                # Apply the updated rule to all transactions
                updated_transaction_ids = []
                for transaction_display in self._all_transactions:
                    if rule.matches(transaction_display.transaction_data):
                        # Execute rule actions and collect updated transaction IDs
                        # This is simplified - in practice you'd use ActionExecutor
                        updated_transaction_ids.append(transaction_display.display_id)
                        
                logger.info(f"Updated rule applied to {len(updated_transaction_ids)} transactions")
            except Exception as e:
                logger.error(f"Error applying updated rule to transactions: {e}")
        
        # Instead of rebuilding UI, the existing rule container should already reflect changes
        # since it's backed by the same rule object that was just updated
        # We only need to ensure the container is in view mode if it was in edit mode
        if rule.rule_id in self._rule_containers:
            try:
                container = self._rule_containers[rule.rule_id]
                # The container will automatically reflect the updated rule data
                # Just ensure it's in the correct mode (should already be view mode)
                logger.debug(f"Rule container for {rule.rule_id} should reflect updated rule data")
            except Exception as e:
                logger.error(f"Error updating rule container for {rule.rule_id}: {e}")
                # Fallback to rebuilding this specific rule container if needed
                self._rebuild_rules_ui()
        
        # Notify parent component about the rule edit
        if self._on_rule_edited:
            try:
                return self._on_rule_edited(rule)
            except Exception as e:
                logger.error(f"Error in rule edit callback: {e}")
        
        return updated_transaction_ids

    def _add_rule_container(self, rule_id: str) -> bool:
        """Add a new rule container to the UI without rebuilding everything.
        
        Args:
            rule_id: ID of the rule to add
            
        Returns:
            bool: True if container was successfully added, False otherwise
        """
        if not self._rules_container or rule_id in self._rule_containers:
            return False
            
        try:
            # Create the new rule container
            container = self._create_rule_container(rule_id, len(self._rule_ids))
            if not container:
                return False
            
            # Add to internal tracking
            self._rule_containers[rule_id] = container
            self._rule_ids.append(rule_id)
            
            # Add separator if not the first rule
            if len(self._rule_ids) > 1:
                separator = toga.Divider(
                    style=Pack(margin=(WIDGET_SPACING, 0))
                )
                self._rules_container.add(separator)
            
            # Add the container widget
            self._rules_container.add(container.create_widget())
            
            # Update header count
            self._update_header_count()
            
            logger.debug(f"Added rule container for {rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add rule container for {rule_id}: {e}")
            return False
    
    def _remove_rule_container(self, rule_id: str) -> bool:
        """Remove a specific rule container from the UI without rebuilding everything.
        
        Args:
            rule_id: ID of the rule to remove
            
        Returns:
            bool: True if container was successfully removed, False otherwise
        """
        if not self._rules_container or rule_id not in self._rule_containers:
            return False
            
        try:
            # Get the container to remove
            container = self._rule_containers[rule_id]
            container_widget = container.create_widget()
            
            # Find the position of this rule in the UI
            rule_index = self._rule_ids.index(rule_id)
            
            # Remove the container widget using the proper Toga method
            try:
                self._rules_container.remove(container_widget)
                logger.debug(f"Removed container widget for rule {rule_id}")
            except Exception as widget_error:
                logger.warning(f"Could not remove container widget for {rule_id}: {widget_error}")
            
            # Remove separator if this rule had one (not the first rule)
            # We need to find and remove the separator that was added before this rule
            if rule_index > 0 and len(self._rules_container.children) > 0:
                try:
                    # Look for separators in the remaining children
                    # Since we just removed the container, we need to find the separator that belonged to it
                    children_to_remove = []
                    for child in self._rules_container.children:
                        if hasattr(child, '__class__') and 'Divider' in child.__class__.__name__:
                            children_to_remove.append(child)
                    
                    # Remove the first separator found (there might be multiple, we only want to remove one)
                    if children_to_remove:
                        separator_to_remove = children_to_remove[0]
                        self._rules_container.remove(separator_to_remove)
                        logger.debug(f"Removed separator for rule {rule_id}")
                        
                except Exception as separator_error:
                    logger.warning(f"Could not remove separator for {rule_id}: {separator_error}")
            
            # Clean up the container
            container.cleanup()
            
            # Remove from internal tracking
            del self._rule_containers[rule_id]
            self._rule_ids.remove(rule_id)
            
            # Update header count
            self._update_header_count()
            
            logger.debug(f"Successfully removed rule container for {rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove rule container for {rule_id}: {e}")
            return False
    
    def _update_header_count(self) -> None:
        """Update the header label to reflect current rule count."""
        if not self._header_label:
            return
            
        rule_count = len(self._rule_ids)
        if rule_count == 0:
            header_text = "No rules applied"
        elif rule_count == 1:
            header_text = "Applied Rule (1)"
        else:
            header_text = f"Applied Rules ({rule_count})"
        
        self._header_label.text = header_text
        logger.debug(f"Updated header count to {rule_count}")

    def cleanup(self) -> None:
        """Clean up resources and child components."""
        # Clean up all rule containers
        for container in self._rule_containers.values():
            container.cleanup()
        
        # Clean up rule creation container
        if self._rule_creation_container:
            self._rule_creation_container.cleanup()
            self._rule_creation_container = None
        
        # Reset state
        self._rule_containers.clear()
        self._rule_ids.clear()
        self._transaction_data = None
        self._is_creation_expanded = False
        
        logger.debug("MultiRuleViewContainer cleanup completed")
    
    # Properties for external access
    
    @property
    def rule_count(self) -> int:
        """Get the number of rules currently displayed."""
        return len(self._rule_ids)
    
    @property
    def rule_ids(self) -> List[str]:
        """Get the list of rule IDs currently displayed."""
        return self._rule_ids.copy()
    
    @property
    def is_empty(self) -> bool:
        """Check if no rules are currently displayed."""
        return len(self._rule_ids) == 0
    
    @property
    def is_creation_expanded(self) -> bool:
        """Check if rule creation section is currently expanded."""
        return self._is_creation_expanded
