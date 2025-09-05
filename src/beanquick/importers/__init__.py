"""
Beanquick Importers Package

This package provides a pluggable architecture for importing financial statement data
from various sources. It includes a clean, simple BeanquickImporter interface that
works directly with TransactionData objects, eliminating beangulp dependencies.
"""

from .core.abc import BeanquickImporter
from .beancount_entry_factory import BeancountEntryFactory
from .core.data import TransactionData
from .core.exceptions import (
    BeanquickImporterError,
    UnsupportedFileTypeError,
    FileIdentificationError,
    DataExtractionError,
    BeancountEntryCreationError
)

__all__ = [
    'BeanquickImporter',
    'BeancountEntryFactory',
    'TransactionData',
    'BeanquickImporterError',
    'UnsupportedFileTypeError',
    'FileIdentificationError',
    'DataExtractionError',
    'BeancountEntryCreationError'
]