"""
Action execution system for the advanced rule engine.

This module provides the ActionExecutor class that handles the execution
of rule actions on transactions with comprehensive error handling and logging.
"""

import logging
from typing import List, TYPE_CHECKING
from .rule_components import ActionType

if TYPE_CHECKING:
    from .rule_components import Action
    from beanquick.ui.importer.transaction_review.models import TransactionDisplayData

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Handles execution of rule actions on transactions.
    
    This class provides a centralized system for executing actions on transactions
    with comprehensive error handling, logging, and duplicate prevention for tag
    management operations.
    
    The ActionExecutor processes actions in sequence and continues execution even
    if individual actions fail, ensuring that partial rule application doesn't
    prevent other actions from being executed.
    """
    
    def __init__(self):
        """Initialize the ActionExecutor."""
        self._execution_stats = {
            'total_actions': 0,
            'successful_actions': 0,
            'failed_actions': 0
        }
    
    def execute_actions(self, actions: List["Action"], 
                       transaction_display: "TransactionDisplayData") -> None:
        """Execute a list of actions on a transaction.
        
        This method processes all actions in sequence, logging any failures
        but continuing with remaining actions to ensure maximum rule application.
        
        Args:
            actions: List of Action objects to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If actions list or transaction_display is None
        """
        if actions is None:
            raise ValueError("actions cannot be None")
        if transaction_display is None:
            raise ValueError("transaction_display cannot be None")
        
        if not actions:
            logger.debug("No actions to execute")
            return
        
        logger.debug(f"Executing {len(actions)} actions on transaction {transaction_display.display_id}")
        
        successful_count = 0
        failed_count = 0
        
        for i, action in enumerate(actions):
            try:
                self._execute_single_action(action, transaction_display)
                successful_count += 1
                logger.debug(f"Successfully executed action {i+1}/{len(actions)}: {action.action_type.value}")
                
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to execute action {i+1}/{len(actions)} "
                    f"({action.action_type.value}) on transaction {transaction_display.display_id}: {e}"
                )
        
        # Update execution statistics
        self._execution_stats['total_actions'] += len(actions)
        self._execution_stats['successful_actions'] += successful_count
        self._execution_stats['failed_actions'] += failed_count
        
        if failed_count > 0:
            logger.warning(
                f"Action execution completed with {failed_count} failures out of {len(actions)} actions "
                f"for transaction {transaction_display.display_id}"
            )
        else:
            logger.debug(f"All {len(actions)} actions executed successfully for transaction {transaction_display.display_id}")
    
    def _execute_single_action(self, action: "Action", 
                              transaction_display: "TransactionDisplayData") -> None:
        """Execute a single action on a transaction.
        
        This method delegates to action-specific execution methods with
        comprehensive error handling and validation.
        
        Args:
            action: The Action object to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If action parameters are invalid
            AttributeError: If transaction_display is missing required attributes
            Exception: For any other execution errors
        """
        if action is None:
            raise ValueError("action cannot be None")
                
        if action.action_type == ActionType.SET_SOURCE_ACCOUNT:
            self._execute_set_source_account(action, transaction_display)
        elif action.action_type == ActionType.SET_DESTINATION_ACCOUNT:
            self._execute_set_destination_account(action, transaction_display)
        elif action.action_type == ActionType.SET_PAYEE:
            self._execute_set_payee(action, transaction_display)
        elif action.action_type == ActionType.ADD_TAG:
            self._execute_add_tag(action, transaction_display)
        elif action.action_type == ActionType.SET_NARRATION:
            self._execute_set_narration(action, transaction_display)
        elif action.action_type == ActionType.APPEND_NARRATION:
            self._execute_append_narration(action, transaction_display)
        else:
            raise NotImplementedError(f"Action type {action.action_type} is not implemented")
    
    def _execute_set_source_account(self, action: "Action", 
                            transaction_display: "TransactionDisplayData") -> None:
        """Execute SET_SOURCE_ACCOUNT action with transaction display data updates.
        
        This method updates the source_account field of the transaction display data,
        which is used for categorization in the triage workflow.
        
        Args:
            action: The SET_SOURCE_ACCOUNT action to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If account parameter is missing or empty
            AttributeError: If transaction_display doesn't support account updates
        """
        if "account" not in action.parameters:
            raise ValueError("SET_SOURCE_ACCOUNT action requires 'account' parameter")
        
        account = str(action.parameters["account"]).strip()
        if not account:
            raise ValueError("SET_SOURCE_ACCOUNT action requires non-empty 'account' parameter")
        
        # Update the source_account field using the reactive update method
        transaction_display.update_source_account(account)
        
        logger.debug(f"Set source account to '{account}' for transaction {transaction_display.display_id}")
    
    def _execute_set_destination_account(self, action: "Action", 
                            transaction_display: "TransactionDisplayData") -> None:
        """Execute SET_DESTINATION_ACCOUNT action with transaction display data updates.
        
        This method updates the destination_account field of the transaction display data,
        which is used for categorization in the triage workflow.
        
        Args:
            action: The SET_DESTINATION_ACCOUNT action to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If account parameter is missing or empty
            AttributeError: If transaction_display doesn't support account updates
        """
        if "account" not in action.parameters:
            raise ValueError("SET_DESTINATION_ACCOUNT action requires 'account' parameter")
        
        account = str(action.parameters["account"]).strip()
        if not account:
            raise ValueError("SET_DESTINATION_ACCOUNT action requires non-empty 'account' parameter")
        
        # Update the destination_account field using the reactive update method
        transaction_display.update_destination_account(account)
        
        logger.debug(f"Set destination account to '{account}' for transaction {transaction_display.display_id}")
    
    def _execute_set_payee(self, action: "Action", 
                          transaction_display: "TransactionDisplayData") -> None:
        """Execute SET_PAYEE action with transaction display data updates.
        
        This method updates the payee field of the transaction display data,
        which is used for categorization in the triage workflow.
        
        Args:
            action: The SET_PAYEE action to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If payee parameter is missing
            AttributeError: If transaction_display doesn't support payee updates
        """
        if "payee" not in action.parameters:
            raise ValueError("SET_PAYEE action requires 'payee' parameter")
        
        payee = str(action.parameters["payee"]) if action.parameters["payee"] is not None else ""
        
        # Update the payee field using the reactive update method
        transaction_display.update_payee(payee)
        
        logger.debug(f"Set payee to '{payee}' for transaction {transaction_display.display_id}")
    
    def _execute_add_tag(self, action: "Action", 
                        transaction_display: "TransactionDisplayData") -> None:
        """Execute ADD_TAG action with duplicate prevention.
        
        This method adds a tag to the transaction's tag set, ensuring no
        duplicates are created. The tags are stored in the underlying
        transaction data and properly synced with metadata.
        
        Args:
            action: The ADD_TAG action to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If tag parameter is missing or empty
        """
        if "tag" not in action.parameters:
            raise ValueError("ADD_TAG action requires 'tag' parameter")
        
        tag = str(action.parameters["tag"]).strip()
        if not tag:
            raise ValueError("ADD_TAG action requires non-empty 'tag' parameter")
        
        # Use the reactive add_tag method which handles all validation and notifications
        try:
            transaction_display.add_tag(tag)
            logger.debug(f"Added tag '{tag}' to transaction {transaction_display.display_id}")
        except ValueError as e:
            # Tag was already present or other validation error
            logger.debug(f"Tag operation for '{tag}' on transaction {transaction_display.display_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error adding tag '{tag}' to transaction {transaction_display.display_id}: {e}")
            raise
    
    def _execute_set_narration(self, action: "Action", 
                              transaction_display: "TransactionDisplayData") -> None:
        """Execute SET_NARRATION action with transaction display data updates.
        
        This method updates the narration field of the transaction display data,
        which is used for categorization in the triage workflow.
        
        Args:
            action: The SET_NARRATION action to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If narration parameter is missing
            AttributeError: If transaction_display doesn't support narration updates
        """
        if "narration" not in action.parameters:
            raise ValueError("SET_NARRATION action requires 'narration' parameter")
        
        narration = str(action.parameters["narration"]) if action.parameters["narration"] is not None else ""
        
        # Update the narration field using the reactive update method
        transaction_display.update_narration(narration if narration else None)
        
        logger.debug(f"Set narration to '{narration}' for transaction {transaction_display.display_id}")
    
    def _execute_append_narration(self, action: "Action", 
                                 transaction_display: "TransactionDisplayData") -> None:
        """Execute APPEND_NARRATION action with transaction display data updates.
        
        This method appends text to the existing narration with proper spacing,
        updating the transaction display data through the reactive update system.
        
        Args:
            action: The APPEND_NARRATION action to execute
            transaction_display: The transaction display data to modify
            
        Raises:
            ValueError: If text parameter is missing or empty
            AttributeError: If transaction_display doesn't support narration updates
        """
        if "text" not in action.parameters:
            raise ValueError("APPEND_NARRATION action requires 'text' parameter")
        
        text = str(action.parameters["text"]).strip()
        if not text:
            raise ValueError("APPEND_NARRATION action requires non-empty 'text' parameter")
        
        # Get current narration from transaction data
        current_narration = transaction_display.transaction_data.narration or ""
        
        # Append with proper spacing
        if current_narration:
            new_narration = f"{current_narration} {text}"
        else:
            new_narration = text
        
        # Update the narration field using the reactive update method
        transaction_display.update_narration(new_narration)
        
        logger.debug(f"Appended '{text}' to narration for transaction {transaction_display.display_id}")
    
    def get_execution_stats(self) -> dict:
        """Get execution statistics for monitoring and debugging.
        
        Returns:
            dict: Dictionary containing execution statistics including
                  total_actions, successful_actions, and failed_actions
        """
        return self._execution_stats.copy()
    
    def reset_execution_stats(self) -> None:
        """Reset execution statistics to zero.
        
        This method is useful for testing or when starting a new batch
        of action executions.
        """
        self._execution_stats = {
            'total_actions': 0,
            'successful_actions': 0,
            'failed_actions': 0
        }
        logger.debug("Execution statistics reset")
