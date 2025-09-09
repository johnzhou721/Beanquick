"""
Factory for creating UI-specific transaction objects from core data.

This module provides factory functions to convert core TransactionData objects
into UI-specific TransactionDisplayData objects, maintaining clean separation
between the core and UI layers.
"""

import logging
from typing import List

from beanquick.importers.core.data import TransactionData

from .models import TransactionDisplayData, TransactionStatus

logger = logging.getLogger(__name__)


def create_display_transactions(transactions: List[TransactionData]) -> List[TransactionDisplayData]:
    """Convert core TransactionData objects to UI TransactionDisplayData objects.
    
    This factory function creates TransactionDisplayData objects ready for the
    triage workflow. Each transaction starts with NEEDS_REVIEW status and can
    be processed by the validation and rule systems.
    
    Args:
        transactions: List of core TransactionData objects
        
    Returns:
        List[TransactionDisplayData]: List of UI-ready transaction objects
    """
    logger.info(f"Converting {len(transactions)} TransactionData objects to TransactionDisplayData")
    
    display_transactions = []
    
    for transaction in transactions:
        # Create TransactionDisplayData with initial NEEDS_REVIEW status
        # Rule application and status updates will be handled by the triage view
        # after validation is properly set up
        transaction_display = TransactionDisplayData(
            transaction_data=transaction,
            status=TransactionStatus.NEEDS_REVIEW,
            display_id=f"triage_{id(transaction)}"
        )
        
        # Set source account from metadata if available (from importer)
        if transaction.metadata and transaction.metadata.get('source_account'):
            transaction_display.source_account = transaction.metadata['source_account']
        
        display_transactions.append(transaction_display)
    
    logger.info(f"Created {len(display_transactions)} TransactionDisplayData objects for triage")
    return display_transactions

