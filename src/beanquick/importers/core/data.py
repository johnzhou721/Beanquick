"""
Data structures for the pluggable importer architecture.

This module defines the standardized data transfer objects used throughout
the importer system to ensure consistent data format across all importers.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Dict, Any, Set
from enum import Enum


class ImporterCapability(Enum):
    BASIC_TRANSACTIONS = "basic_transactions"
    MULTI_CURRENCY = "multi_currency"
    DIGITAL_WALLET = "digital_wallet"
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"

@dataclass
class ImporterMetadata:
    """Metadata describing an importer's capabilities."""
    name: str
    icon: str
    description: str
    region: str
    institution: str
    supported_file_types: Set[str]
    capabilities: Set[ImporterCapability]
    default_account_prefix: str
    currency: str = "USD"
    priority: int = 0

@dataclass
class TransactionData:
    """A standardized Data Transfer Object (DTO) representing a single transaction.
    
    This class serves as the universal contract between the importer layer
    and the UI layer, ensuring consistent data format across all importers.
    
    Attributes:
        date: The transaction date
        payee: The payee or merchant name
        narration: Optional transaction description or memo
        amount: The transaction amount as a Decimal for precise calculations
        currency: The currency code (e.g., 'USD', 'CNY')
        metadata: Optional dictionary for storing additional data like original row data
    """
    date: date
    payee: str
    narration: Optional[str]
    amount: Decimal
    currency: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate and normalize data after initialization.
        
        This method ensures data integrity by:
        - Converting amount to Decimal if it's not already
        - Initializing metadata as empty dict if None
        - Validating required fields are not empty
        
        Raises:
            ValueError: If required fields are invalid or empty
            TypeError: If amount cannot be converted to Decimal
        """
        # Convert amount to Decimal if it's not already
        if not isinstance(self.amount, Decimal):
            try:
                self.amount = Decimal(str(self.amount))
            except (ValueError, TypeError, Exception) as e:
                raise TypeError(f"Amount must be convertible to Decimal: {e}") from e
        
        # Initialize metadata as empty dict if None
        if self.metadata is None:
            self.metadata = {}
        
        # Validate required string fields are not empty
        if not self.payee or not self.payee.strip():
            raise ValueError("Payee cannot be empty")
        
        if not self.currency or not self.currency.strip():
            raise ValueError("Currency cannot be empty")
        
        # Ensure payee is stripped of whitespace
        self.payee = self.payee.strip()
        
        # Ensure currency is uppercase and stripped
        self.currency = self.currency.strip().upper()
        
        # Strip narration if it exists
        if self.narration is not None:
            self.narration = self.narration.strip() if self.narration.strip() else None