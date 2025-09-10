"""
Beancount Entry Factory

This module provides a centralized factory for creating beancount entries from
TransactionData objects.
"""

import re
from typing import List, Tuple
from datetime import date
from decimal import Decimal
from enum import Enum

from beancount.core import data, amount, account
from beancount.core.number import D

from .core.data import TransactionData
from .core.exceptions import (
    BeancountEntryCreationError,
    InvalidAccountError,
    InvalidAmountError,
    InvalidTransactionDataError
)


class BeancountEntryFactory:
    """Factory for creating beancount entries from TransactionData.
    
    This factory implements the creation pattern where beancount entries
    are created only when actually needed (preview display, final export),
    while maintaining TransactionData as the primary working format throughout
    the application lifecycle.
    """
    
    @staticmethod
    def create_transaction(
        transaction_data: TransactionData,
        source_account: str,
        destination_account: str,
        source_file: str = "preview",
        line_number: int = 1
    ) -> data.Transaction:
        """Create a beancount Transaction from TransactionData and account assignments.
        
        This method converts a TransactionData object into a proper beancount
        Transaction with correct postings and metadata. It handles amount
        conversion from Decimal to beancount Amount objects and validates
        account names.
        
        Args:
            transaction_data: The TransactionData object to convert
            source_account: The source account (e.g., credit card account)
            destination_account: The destination account (e.g., expense account)
            source_file: The source file name for metadata (defaults to "preview")
            line_number: The line number for metadata (defaults to 1)
            
        Returns:
            data.Transaction: A properly formatted beancount Transaction
            
        Raises:
            InvalidAccountError: If account names are invalid
            InvalidAmountError: If amount cannot be converted
            BeancountEntryCreationError: For other creation failures
        """
        try:
            # Validate inputs
            BeancountEntryFactory._validate_transaction_data(transaction_data)
            BeancountEntryFactory._validate_account_name(source_account, "source_account")
            BeancountEntryFactory._validate_account_name(destination_account, "destination_account")
            
            # Convert amount to beancount Amount object with comprehensive error handling
            transaction_amount = BeancountEntryFactory._convert_amount(transaction_data)
            
            # Create metadata for the transaction
            # meta = data.new_metadata(source_file, line_number)
            # meta['__tolerances__'] = {}
            # meta['importer'] = 'BeancountEntryFactory'
            
            # # Preserve original TransactionData metadata if present, with validation
            # if transaction_data.metadata:
            #     for key, value in transaction_data.metadata.items():
            #         # Avoid overwriting beancount-specific metadata
            #         if key not in ['__tolerances__', 'importer']:
            #             # Convert metadata value to beancount-compatible type
            #             cleaned_value = BeancountEntryFactory._clean_metadata_value(key, value)
            #             if cleaned_value is not None:
            #                 meta[key] = cleaned_value
            
            # Create postings - standard double-entry bookkeeping
            postings = [
                data.Posting(
                    account=source_account,
                    units=-transaction_amount,
                    cost=None,
                    price=None,
                    flag=None,
                    meta={}
                ),
                data.Posting(
                    account=destination_account,
                    units=transaction_amount,
                    cost=None,
                    price=None,
                    flag=None,
                    meta={}
                )
            ]
            
            # Convert tags from TransactionData to beancount format
            beancount_tags = frozenset(transaction_data.tags) if transaction_data.tags else frozenset()
            
            # Create the beancount Transaction entry
            transaction = data.Transaction(
                # meta=meta,
                meta={},
                date=transaction_data.date,
                flag="*",  # Mark as cleared
                payee=transaction_data.payee,
                narration=transaction_data.narration,
                tags=beancount_tags,
                links=frozenset(),
                postings=postings
            )
            
            return transaction
            
        except Exception as e:
            # Wrap all errors in BeancountEntryCreationError
            raise BeancountEntryCreationError(
                f"Error creating beancount transaction: {e}",
                transaction_data=transaction_data,
                source_account=source_account,
                destination_account=destination_account
            ) from e
    
    @staticmethod
    def create_transactions_batch(
        transactions_with_accounts: List[Tuple[TransactionData, str, str]],
        source_file: str
    ) -> List[data.Transaction]:
        """Create multiple beancount transactions efficiently.
        
        This method creates multiple beancount transactions in a batch operation,
        optimized for export scenarios with many transactions. It maintains
        consistent metadata and formatting across the batch while providing
        efficient processing.
        
        Args:
            transactions_with_accounts: List of (TransactionData, source_account, destination_account) tuples
            source_file: Source file name for metadata
            
        Returns:
            List[data.Transaction]: List of beancount transactions
            
        Raises:
            BeancountEntryCreationError: If any transaction creation fails
        """
        if not transactions_with_accounts:
            return []
        
        transactions = []
        errors = []
        
        for i, (transaction_data, source_account, destination_account) in enumerate(transactions_with_accounts):
            try:
                transaction = BeancountEntryFactory.create_transaction(
                    transaction_data=transaction_data,
                    source_account=source_account,
                    destination_account=destination_account,
                    source_file=source_file,
                    line_number=i + 1  # Use index as line number for batch
                )
                transactions.append(transaction)
            except BeancountEntryCreationError as e:
                # Collect errors but continue processing other transactions
                errors.append(f"Transaction {i}: {e}")
        
        # If there were any errors, raise an exception with all error details
        if errors:
            error_summary = f"Failed to create {len(errors)} out of {len(transactions_with_accounts)} transactions"
            error_details = "; ".join(errors)
            raise BeancountEntryCreationError(
                f"{error_summary}: {error_details}",
                validation_errors=errors
            )
        
        return transactions
    
    @staticmethod
    def _validate_transaction_data(transaction_data: TransactionData) -> None:
        """Validate that TransactionData is complete and valid.
        
        Args:
            transaction_data: The TransactionData object to validate
            
        Raises:
            InvalidTransactionDataError: If the transaction data is invalid
        """
        if not transaction_data:
            raise InvalidTransactionDataError("TransactionData cannot be None")
        
        # Validate date
        if not transaction_data.date:
            raise InvalidTransactionDataError("Transaction date cannot be None", transaction_data=transaction_data)
        
        # Validate payee
        # if not transaction_data.payee or not transaction_data.payee.strip():
        #     raise InvalidTransactionDataError("Transaction payee cannot be empty", transaction_data=transaction_data)
        
        # Validate amount
        if transaction_data.amount is None:
            raise InvalidTransactionDataError("Transaction amount cannot be None", transaction_data=transaction_data)
        
        # Validate currency
        if not transaction_data.currency or not transaction_data.currency.strip():
            raise InvalidTransactionDataError("Transaction currency cannot be empty", transaction_data=transaction_data)
        
        # Validate currency format using beancount's official currency regex
        currency = transaction_data.currency.strip()
        if not re.fullmatch(amount.CURRENCY_RE, currency):
            raise InvalidTransactionDataError(
                f"Currency '{transaction_data.currency}' is not a valid beancount currency. "
                f"Currencies must follow beancount naming conventions (e.g., 'USD', 'CNY', 'BTC').",
                transaction_data=transaction_data
            )
    
    @staticmethod
    def _convert_amount(transaction_data: TransactionData) -> amount.Amount:
        """Convert TransactionData amount to beancount Amount with error handling.
        
        Args:
            transaction_data: The TransactionData containing amount and currency
            
        Returns:
            amount.Amount: The converted beancount Amount object
            
        Raises:
            InvalidAmountError: If amount cannot be converted
        """
        try:
            # Ensure amount is a Decimal
            if isinstance(transaction_data.amount, Decimal):
                decimal_amount = transaction_data.amount
            else:
                decimal_amount = Decimal(str(transaction_data.amount))
            
            # Check for extremely large amounts (likely data error)
            if abs(decimal_amount) > Decimal('999999999.99'):
                raise InvalidAmountError(
                    f"Transaction amount '{decimal_amount}' is unreasonably large",
                    transaction_data=transaction_data
                )
            
            # Create beancount Amount
            return amount.Amount(D(str(decimal_amount)), transaction_data.currency.upper())
            
        except (ValueError, TypeError, Exception) as e:
            raise InvalidAmountError(
                f"Cannot convert amount '{transaction_data.amount}' "
                f"with currency '{transaction_data.currency}': {e}",
                transaction_data=transaction_data
            ) from e
    
    @staticmethod
    def _validate_account_name(account_name: str, field_name: str = "account") -> None:
        """Validate that an account name follows beancount format rules.
        
        Uses the official beancount account validation function to ensure
        proper account name format according to beancount standards.
        
        Args:
            account_name: The account name to validate
            field_name: The name of the field being validated (for error messages)
            
        Raises:
            InvalidAccountError: If the account name is invalid
        """
        if not account_name or not account_name.strip():
            raise InvalidAccountError(f"{field_name} cannot be empty")
        
        account_name = account_name.strip()
        
        # Use the official beancount account validation function
        if not account.is_valid(account_name):
            raise InvalidAccountError(
                f"{field_name} '{account_name}' is not a valid beancount account name. "
                f"Account names must follow beancount naming conventions (e.g., 'Assets:Checking')."
            )
    
    @staticmethod
    def _clean_metadata_value(key: str, value):
        """Clean a metadata value for beancount compatibility.
        
        Converts unsupported types to supported ones based on beancount printer requirements:
        - Supported: str, Decimal, datetime.date, amount.Amount, enum.Enum, bool, dict, None
        - int/float -> str (convert to string representation)
        - Complex objects -> None (remove them)
        
        Args:
            key: The metadata key (for logging)
            value: The value to clean
            
        Returns:
            The cleaned value, or None if the value should be removed
        """
        # Handle None explicitly
        if value is None:
            return None
        
        # Handle types that beancount printer already supports
        if isinstance(value, str):
            return value
        elif isinstance(value, (Decimal, date, amount.Amount, Enum)):
            return value
        elif isinstance(value, bool):
            return value
        elif isinstance(value, dict):
            # Recursively clean dict values
            try:
                cleaned_dict = {}
                for k, v in value.items():
                    cleaned_v = BeancountEntryFactory._clean_metadata_value(f"{key}.{k}", v)
                    if cleaned_v is not None:
                        cleaned_dict[str(k)] = cleaned_v  # Ensure keys are strings
                return cleaned_dict if cleaned_dict else None
            except Exception:
                # If dict cleaning fails, convert to string representation
                try:
                    str_repr = str(value)
                    return str_repr if len(str_repr) <= 100 else None
                except Exception:
                    return None
        
        # Handle numeric types that beancount doesn't support by converting to string
        elif isinstance(value, (int, float)):
            return str(value)
        
        # Handle lists/tuples by converting to string representation
        elif isinstance(value, (list, tuple)):
            try:
                # Convert to string representation, but only for simple lists
                str_repr = str(value)
                # Only keep if it's reasonably short (avoid huge data dumps)
                return str_repr if len(str_repr) <= 100 else None
            except Exception:
                return None
        
        # For any other complex type, try to convert to string if reasonable
        else:
            try:
                str_repr = str(value)
                # Only keep if it's reasonably short and doesn't look like an object representation
                if len(str_repr) <= 100 and not str_repr.startswith('<'):
                    return str_repr
                else:
                    return None
            except Exception:
                return None  
