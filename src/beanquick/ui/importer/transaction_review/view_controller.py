"""
Triage View Controller for workflow coordination.

This module provides the TriageViewController class that coordinates the
enhanced inspector panel workflow, managing state between table and inspector
components, handling confirmation workflows, and managing rule creation and application.
"""

from typing import Optional, List, TYPE_CHECKING
import logging

from .models import SuccessData

if TYPE_CHECKING:
    from .view import TransactionTriageView
    from beanquick.importers.rules.engine import RuleEngine

logger = logging.getLogger(__name__)


class TriageViewController:
    """Central coordinator for the enhanced triage workflow.
    
    This controller manages state between the table and inspector components,
    handles the keyboard-driven confirmation workflow, coordinates automatic
    progression to the next transaction, and manages rule creation and application.
    
    Attributes:
        _triage_view: Reference to the main TransactionTriageView
        _rule_engine: Service for rule creation and application
    """
    
    def __init__(self, triage_view: "TransactionTriageView", 
                 rule_engine: "RuleEngine"):
        """Initialize the triage view controller.
        
        Args:
            triage_view: The main TransactionTriageView instance
            rule_engine: Service for rule creation and application
            
        Raises:
            ValueError: If any required parameter is None or invalid
        """
        required_params = [
            (triage_view, "triage_view cannot be None"),
            (rule_engine, "rule_engine cannot be None"), 
        ]
        
        for param, error_msg in required_params:
            if not param:
                raise ValueError(error_msg)
        
        self._triage_view = triage_view
        self._rule_engine = rule_engine
    
    def handle_save_completion(self, success_data: SuccessData):
        """Handle completion of the entry saving process.
        
        This method is called when the user has successfully saved their
        Beancount entries. It triggers the transition to the success view
        and manages the workflow completion state.
        
        Args:
            success_data: Comprehensive data about the completed import process
        """
        try:
            logger.info("Handling save completion, transitioning to success view")
            
            # Validate the success data
            if not success_data:
                raise ValueError("Success data cannot be None")
            
            # Trigger the transition to success view
            self.transition_to_success_view(success_data)
            
            logger.info(f"Successfully transitioned to success view. "
                       f"Processed {success_data.transaction_count} transactions, "
                       f"created {success_data.rules_created} rules")
            
        except Exception as e:
            logger.error(f"Error handling save completion: {e}", exc_info=True)
            # Could show an error dialog here if needed
    
    def collect_success_statistics(self, 
                                 source_file_path: str, 
                                 saved_file_path: str,
                                 rules_created_count: int = 0,
                                 rules_applied_count: int = 0,
                                 rule_ids_created: Optional[List[str]] = None) -> SuccessData:
        """Collect and compile success statistics from the current triage session.
        
        This method analyzes the current state of all transactions and compiles
        comprehensive statistics for display in the success view.
        
        Args:
            source_file_path: Path to the original statement file
            saved_file_path: Path where entries were saved
            rules_created_count: Number of new rules created during import (default: 0)
            rules_applied_count: Number of rules applied during extraction (default: 0)
            rule_ids_created: List of rule IDs created during import (optional)
            
        Returns:
            SuccessData: Compiled success statistics
            
        Raises:
            ValueError: If required data is missing or invalid
        """
        try:
            # Get all transactions from the triage view
            if not hasattr(self._triage_view, '_display_transactions'):
                raise ValueError("No display transactions available for statistics")
            
            transactions = self._triage_view._display_transactions
            
            if not transactions:
                logger.warning("No transactions found for success statistics")
                transactions = []
            
            # Use the SuccessData factory method to build the object
            success_data = SuccessData.from_transactions(
                transactions=transactions,
                source_file_path=source_file_path,
                saved_file_path=saved_file_path,
                rules_created=rules_created_count,
                rules_applied=rules_applied_count,
                rule_ids_created=rule_ids_created
            )
            
            logger.debug(f"Collected success statistics: {success_data.transaction_count} transactions, "
                        f"{success_data.categorized_count} categorized, "
                        f"{success_data.rules_created} rules created")
            
            return success_data
            
        except Exception as e:
            logger.error(f"Error collecting success statistics: {e}", exc_info=True)
            # Create minimal success data as fallback
            return SuccessData(
                transaction_count=0,
                categorized_count=0,
                completed_count=0,
                rules_created=rules_created_count,
                rules_applied=rules_applied_count,
                source_file_name="Unknown",
                source_file_path=source_file_path,
                saved_file_path=saved_file_path,
            )
    
    def transition_to_success_view(self, success_data: SuccessData):
        """Trigger the transition to the success view.
        
        This method coordinates with the TransactionTriageView to display
        the success view with the provided statistics and completion data.
        
        Args:
            success_data: The success statistics to display
            
        Raises:
            ValueError: If success_data is invalid
        """
        try:
            if not success_data:
                raise ValueError("Success data cannot be None for transition")
            
            # Check if the triage view supports success view transition
            if not hasattr(self._triage_view, 'show_success_view'):
                raise ValueError("Triage view does not support success view transition")
            
            # Trigger the view transition
            self._triage_view.show_success_view(success_data)
            
            logger.info("Successfully triggered transition to success view")
            
        except Exception as e:
            logger.error(f"Error transitioning to success view: {e}", exc_info=True)
            raise ValueError(f"Failed to transition to success view: {e}")
    
    def reset_for_new_import(self):
        """Reset the controller state for a new import workflow.
        
        This method cleans up the current triage session state and prepares
        the controller for handling a new import. It's typically called when
        the user chooses to import another file from the success view.
        """
        try:
            logger.info("Resetting triage controller for new import")
            
            # Clear any cached state
            # Note: Most state is managed by the triage view itself,
            # so we primarily need to ensure the controller is ready for new data
            
            # Log the reset for debugging
            logger.debug("Triage controller reset completed")
            
        except Exception as e:
            logger.error(f"Error resetting controller for new import: {e}", exc_info=True)
