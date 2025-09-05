"""
Utility functions for working with importers.

This module provides utility functions for importer identification and management,
supporting the rule persistence system by providing consistent importer ID generation.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core.abc import BeanquickImporter


def get_importer_id(importer: "BeanquickImporter") -> str:
    """Extract importer identifier from BeanquickImporter instance.
    
    This function generates a consistent identifier for importers by transforming
    the class name of the importer. The transformation follows these rules:
    
    1. Take the class name of the importer
    2. Convert CamelCase to snake_case
    3. Convert to lowercase
    4. Remove 'importer' suffix if present
    5. Remove 'csv' suffix if present
    
    Examples:
        CMBCreditCardCSVImporter -> "cmb_credit_card"
        AlipayImporter -> "alipay"
        BankOfAmericaCSVImporter -> "bank_of_america"
        SimpleImporter -> "simple"
    
    Args:
        importer: BeanquickImporter instance
        
    Returns:
        str: Consistent identifier for the importer
        
    Raises:
        TypeError: If the importer doesn't have a __class__ attribute
    """
    if not hasattr(importer, '__class__'):
        raise TypeError("importer must have a __class__ attribute")
    
    # Get the class name
    class_name = importer.__class__.__name__
    
    # Convert CamelCase to snake_case
    # First, handle sequences of uppercase letters followed by lowercase (e.g., "HSBCUKImporter" -> "HSBCUK_Importer")
    name = re.sub('([A-Z]+)([A-Z][a-z])', r'\1_\2', class_name)
    # Then handle lowercase/digit followed by uppercase (e.g., "word1Word" -> "word1_Word")
    name = re.sub('([a-z\\d])([A-Z])', r'\1_\2', name)
    # Convert to lowercase
    name = name.lower()
    
    # Remove common suffixes
    name = name.replace('_importer', '').replace('_csv', '')
    name = name.replace('importer', '').replace('csv', '')
    
    # Clean up any double underscores or leading/trailing underscores
    name = re.sub('_+', '_', name).strip('_')
    
    # Ensure we have a non-empty result
    if not name:
        # Fallback to original class name if transformation results in empty string
        name = class_name.lower()
    
    return name