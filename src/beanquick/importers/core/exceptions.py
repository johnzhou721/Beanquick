"""
Custom exception classes for the Beanquick importer system.

This module provides a hierarchy of exceptions for clean error handling
throughout the importer system, from file identification through beancount
entry creation.
"""


class BeanquickImporterError(Exception):
    """Base exception for all importer-related errors.
    
    This serves as the root exception class for all errors that can occur
    within the Beanquick importer system. It allows for broad exception
    handling when needed while still providing specific error types.
    """
    pass


class UnsupportedFileTypeError(BeanquickImporterError):
    """Raised when no importer can handle a file.
    
    This exception is raised by the importer registry when no registered
    importer can identify and process a given file.
    
    Attributes:
        filepath: The path to the unsupported file
        attempted_importers: List of importer names that were tried
    """
    
    def __init__(self, message: str, filepath: str = "", attempted_importers: list | None = None):
        super().__init__(message)
        self.filepath = filepath
        self.attempted_importers = attempted_importers or []


class FileIdentificationError(BeanquickImporterError):
    """Raised when file identification fails.
    
    This exception is raised when an importer encounters an error while
    trying to identify if it can handle a file.
    
    Attributes:
        file_path: Path to the file that failed identification
        details: Additional details about the failure
    """
    
    def __init__(self, message: str, file_path: str = "", details: str = ""):
        super().__init__(message)
        self.file_path = file_path
        self.details = details


class DataExtractionError(BeanquickImporterError):
    """Raised when data extraction fails.
    
    This exception is raised when an importer encounters an error while
    trying to extract transaction data from a file. It provides detailed
    context about the failure to help with debugging and user feedback.
    
    Attributes:
        file_path: Path to the file that failed extraction
        importer_name: Name of the importer that failed
        details: Additional details about the failure
        line_number: Line number where the error occurred (if applicable)
    """
    
    def __init__(self, message: str, file_path: str = "", importer_name: str = "", 
                 details: str = "", line_number: int | None = None):
        super().__init__(message)
        self.file_path = file_path
        self.importer_name = importer_name
        self.details = details
        self.line_number = line_number
    
    def __str__(self):
        """Provide detailed error message with context."""
        parts = [super().__str__()]
        
        if self.importer_name:
            parts.append(f"Importer: {self.importer_name}")
        
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        
        if self.line_number is not None:
            parts.append(f"Line: {self.line_number}")
        
        if self.details:
            parts.append(f"Details: {self.details}")
        
        return " | ".join(parts)


class BeancountEntryCreationError(BeanquickImporterError):
    """Raised when beancount entry creation fails.
    
    This exception is raised by the BeancountEntryFactory when it cannot
    create a valid beancount entry from the provided TransactionData and
    account information.
    
    Attributes:
        transaction_data: The TransactionData that failed conversion (optional)
        source_account: The source account that was specified
        destination_account: The destination account that was specified
        validation_errors: List of specific validation errors
    """
    
    def __init__(self, message: str, transaction_data=None, source_account: str = "", 
                 destination_account: str = "", validation_errors: list | None = None):
        super().__init__(message)
        self.transaction_data = transaction_data
        self.source_account = source_account
        self.destination_account = destination_account
        self.validation_errors = validation_errors or []
    
    def __str__(self):
        """Provide detailed error message with context."""
        parts = [super().__str__()]
        
        if self.source_account:
            parts.append(f"Source Account: {self.source_account}")
        
        if self.destination_account:
            parts.append(f"Destination Account: {self.destination_account}")
        
        if self.validation_errors:
            parts.append(f"Validation Errors: {', '.join(self.validation_errors)}")
        
        return " | ".join(parts)


class InvalidAccountError(BeancountEntryCreationError):
    """Raised when an account name is invalid.
    
    This exception is raised when an account name doesn't follow beancount
    formatting rules (e.g., doesn't start with capital letter, contains
    invalid characters, etc.).
    """
    pass


class InvalidAmountError(BeancountEntryCreationError):
    """Raised when an amount cannot be converted to beancount format.
    
    This exception is raised when a transaction amount cannot be converted
    to a valid beancount Amount object (e.g., invalid decimal format,
    missing currency, etc.).
    """
    pass


class InvalidTransactionDataError(BeancountEntryCreationError):
    """Raised when TransactionData is incomplete or invalid.
    
    This exception is raised when TransactionData is missing required fields
    or contains invalid data that prevents beancount entry creation.
    """
    pass