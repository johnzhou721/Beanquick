"""
Abstract base class for Beanquick importers.

This module provides a clean, simple interface for all importers that works
directly with TransactionData objects, eliminating beangulp dependencies
and complexity.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from .data import TransactionData

from .data import ImporterMetadata

class BeanquickImporter(ABC):
    """Simple, clean importer interface that works directly with TransactionData.
    
    This abstract base class defines the minimal interface required for all
    importers in the Beanquick system. It eliminates beangulp dependencies
    and provides a clean, focused interface with only the necessary methods.
    
    Importers implementing this interface should:
    1. Work directly with TransactionData objects
    2. Handle file identification through the identify() method
    3. Extract transactions through the extract() method
    4. Provide a human-readable name through the name property
    """
    def __init__(self, default_account: str):
        self.default_account = default_account
        self._rule_repository = None
        self.metadata: Optional[ImporterMetadata] = None

    @abstractmethod
    def identify(self, filepath: str) -> bool:
        """Check if this importer can handle the given file.
        
        This method should examine the file (typically by checking headers,
        file extension, or content format) to determine if this importer
        can process it.
        
        Args:
            filepath: Path to the file to check
            
        Returns:
            bool: True if this importer can handle the file, False otherwise
            
        Note:
            This method should be fast and not perform full file parsing.
            It should only do minimal checks needed to identify compatibility.
        """
        pass
    
    @abstractmethod
    def extract(self, filepath: str) -> List[TransactionData]:
        """Extract transactions from the file as TransactionData objects.
        
        This method should parse the file and return a list of TransactionData
        objects representing all transactions found in the file. The method
        should work directly with TransactionData without creating any
        beancount data.Transaction objects.
        
        Args:
            filepath: Path to the file to extract from
            
        Returns:
            List[TransactionData]: List of extracted transactions
            
        Raises:
            DataExtractionError: If extraction fails due to file format issues,
                                encoding problems, or other parsing errors
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this importer.
        
        This should return a descriptive name that identifies the importer
        type and the financial institution or file format it handles.
        
        Returns:
            str: Human-readable importer name (e.g., "Chase Bank CSV Importer")
        """
        pass