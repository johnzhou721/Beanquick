"""
ImporterRegistry - Registry for BeanquickImporter management.

This module provides the ImporterRegistry class that manages BeanquickImporter
instances directly.
The registry provides automatic file type identification and importer selection
with a clean, simple interface.
"""

from typing import List, Optional, Dict, Type
import logging
import pkgutil
import inspect
import importlib

from .abc import BeanquickImporter
from .exceptions import UnsupportedFileTypeError, DataExtractionError

logger = logging.getLogger(__name__)


class ImporterRegistry:
    """Registry that manages BeanquickImporter instances directly.
    
    This registry works directly with BeanquickImporter instances without any
    adapter layers, providing a clean and efficient interface for file type
    identification and transaction extraction.
    
    The registry follows the Registry design pattern to enable easy addition
    of new importers without modifying core application code.
    
    Attributes:
        _importers: List of BeanquickImporter instances
    """
    
    def __init__(self):
        """Initialize the registry and register all known importers.
        
        The registry starts with an empty list and then calls _discover_plugins()
        to populate it with all known BeanquickImporter instances.
        """
        self._importers: List[BeanquickImporter] = []
        self._importer_classes: Dict[str, Type[BeanquickImporter]] = {}
        logger.info("Initializing ImporterRegistry")
        self._discover_plugins()
        logger.info(f"ImporterRegistry initialized with {len(self._importers)} importers")
    
    def _discover_plugins(self):
        """Automatically discover importer plugins in the plugins directory."""
        try:
            # Import the plugins package
            from ..plugins import china, us, international, formats
            
            # List of plugin modules to scan
            plugin_modules = [china, us, international, formats]
            
            for plugin_module in plugin_modules:
                self._scan_module_for_importers(plugin_module)
                
                # Also scan submodules if they exist
                if hasattr(plugin_module, '__path__'):
                    for importer_info in pkgutil.iter_modules(plugin_module.__path__):
                        try:
                            submodule = importlib.import_module(
                                f"{plugin_module.__name__}.{importer_info.name}"
                            )
                            self._scan_module_for_importers(submodule)
                        except ImportError as e:
                            logger.warning(f"Failed to import {importer_info.name}: {e}")
            
        except ImportError as e:
            logger.warning(f"Plugin discovery failed: {e}")
            # Fallback to manual registration
            self._register_fallback_importers()
    
    def _scan_module_for_importers(self, module):
        """Scan a module for BeanquickImporter classes."""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BeanquickImporter) and 
                obj != BeanquickImporter and
                not inspect.isabstract(obj)):
                
                try:
                    # Create instance with a default account name based on the class name
                    class_name = obj.__name__
                    # Remove "Importer" or "CSVImporter" suffix if present
                    account_name = class_name.replace('CSVImporter', '').replace('Importer', '')
                    default_account = f"Assets:{account_name}"
                    
                    importer_instance = obj(default_account)
                    self.register(importer_instance)
                    
                    # Store class for future reference
                    class_key = f"{module.__name__}.{name}"
                    self._importer_classes[class_key] = obj
                    
                    logger.debug(f"Auto-discovered and registered: {class_key}")
                    
                except Exception as e:
                    logger.warning(f"Failed to instantiate {name}: {e}")
    
    def _register_fallback_importers(self):
        """Fallback manual registration if auto-discovery fails."""
        logger.info("Using fallback manual registration")
        
        try:
            from ..plugins.china.alipay import AlipayCSVImporter
            
            self.register(AlipayCSVImporter())
            
        except ImportError as e:
            logger.error(f"Fallback registration failed: {e}")
    
    def register(self, importer: BeanquickImporter):
        """Registers a new BeanquickImporter with the registry.
        
        This method validates that the importer implements the BeanquickImporter
        interface and adds it directly to the registry without any adapter layer.
        
        Args:
            importer: An instance implementing the BeanquickImporter interface.
                     Must have identify(), extract(), and name property.
        
        Raises:
            TypeError: If the importer doesn't implement the required interface methods.
            ValueError: If the importer is None or invalid.
        """
        if importer is None:
            raise ValueError("Cannot register None as an importer")
        
        # Validate that the importer implements the BeanquickImporter interface
        if not isinstance(importer, BeanquickImporter):
            raise TypeError(
                f"Importer {importer.__class__.__name__} must inherit from BeanquickImporter"
            )
        
        # Validate required methods are callable
        required_methods = ['identify', 'extract']
        for method in required_methods:
            if not hasattr(importer, method) or not callable(getattr(importer, method)):
                raise TypeError(
                    f"Importer {importer.__class__.__name__} method '{method}' "
                    f"must be callable"
                )
        
        # Validate name property exists
        if not hasattr(importer, 'name'):
            raise TypeError(
                f"Importer {importer.__class__.__name__} must have a 'name' property"
            )
        
         # Prevent duplicate registration
        importer_class_name = importer.__class__.__name__
        for existing in self._importers:
            if existing.__class__.__name__ == importer_class_name:
                logger.debug(f"Importer {importer_class_name} already registered, skipping")
                return
        
        try:
            # Add the importer directly to the registry
            self._importers.append(importer)
            
            logger.info(f"Successfully registered importer: {importer.__class__.__name__}")
            logger.debug(f"Total registered importers: {len(self._importers)}")
            
        except Exception as e:
            logger.error(
                f"Failed to register importer {importer.__class__.__name__}: {e}",
                exc_info=True
            )
            raise TypeError(
                f"Failed to register importer {importer.__class__.__name__}: {e}"
            ) from e
    

    def find_importer_for_file(self, filepath: str) -> Optional[BeanquickImporter]:
        """Finds the first importer that can handle the given file.
        
        Iterates through all registered importers in registration order,
        calling their identify() method until one returns True. This follows
        the first-match strategy where the first importer that can handle
        the file is selected.
        
        Args:
            filepath: String path to the file to be processed.
            
        Returns:
            The first BeanquickImporter instance that can handle the file,
            or None if no suitable importer is found.
        """
        if not filepath:
            raise ValueError("filepath parameter cannot be empty")
        
        logger.info(f"Finding importer for file: {filepath}")
        logger.debug(f"Checking against {len(self._importers)} registered importers")
        
        # Sort importers by priority if they have metadata
        sorted_importers = sorted(
            self._importers,
            key=lambda imp: getattr(getattr(imp, 'metadata', None), 'priority', 0),
            reverse=True
        )

        for i, importer in enumerate(sorted_importers):
            importer_name = importer.__class__.__name__
            logger.debug(f"Testing importer {i+1}/{len(sorted_importers)}: {importer_name}")

            try:
                if importer.identify(filepath):
                    logger.info(f"Found matching importer: {importer_name}")
                    logger.debug(f"File {filepath} will be processed by {importer_name}")
                    return importer
                else:
                    logger.debug(f"Importer {importer_name} cannot handle file {filepath}")
                    
            except Exception as e:
                # Log the error but continue trying other importers
                logger.warning(
                    f"Error in {importer_name}.identify() for file {filepath}: {e}",
                    exc_info=True
                )
                continue
        
        logger.warning(f"No suitable importer found for file: {filepath}")
        logger.debug(f"Tested {len(self._importers)} importers, none could handle the file")
        return None
    
    def extract_transactions(self, filepath: str) -> List:
        """Extract transactions from the file.
        
        This method extracts raw TransactionData objects from the file using
        the appropriate importer. The core layer only deals with domain objects
        and leaves UI-specific data transformation to the UI layer.
        
        Args:
            filepath: String path to the file to extract from
            
        Returns:
            List[TransactionData]: List of raw transaction data objects
            
        Raises:
            UnsupportedFileTypeError: If no importer can handle the file
            DataExtractionError: If extraction fails
        """
        importer = self.find_importer_for_file(filepath)
        if not importer:
            raise UnsupportedFileTypeError(f"No importer found for file: {filepath}")
        
        try:
            logger.info(f"Extracting transactions from {filepath} using {importer.name}")
            transactions = importer.extract(filepath)
            logger.info(f"Successfully extracted {len(transactions)} transactions from {filepath}")
            
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to extract transactions from {filepath}: {e}", exc_info=True)
            raise DataExtractionError(
                message=f"Failed to extract transactions using {importer.name}",
                file_path=filepath,
                importer_name=importer.__class__.__name__,
                details=str(e)
            ) from e
    
    def get_importers_by_region(self, region: str) -> List[BeanquickImporter]:
        """Get all importers for a specific region."""
        return [
            imp for imp in self._importers 
            if hasattr(imp, 'metadata') and 
            getattr(imp.metadata, 'region', None) == region
        ]
    
    def get_importers_by_institution(self, institution: str) -> List[BeanquickImporter]:
        """Get all importers for a specific institution."""
        return [
            imp for imp in self._importers 
            if hasattr(imp, 'metadata') and 
            getattr(imp.metadata, 'institution', None) == institution
        ]
    
    def get_supported_file_types(self) -> set:
        """Get all supported file types across all importers."""
        file_types = set()
        for importer in self._importers:
            if hasattr(importer, 'metadata'):
                file_types.update(getattr(importer.metadata, 'supported_file_types', set()))
        return file_types
    
    def get_registered_importers(self) -> List[str]:
        """Returns a list of registered importer class names for debugging.
        
        This method provides a way to inspect which importers are currently
        registered in the registry, useful for debugging and monitoring.
        
        Returns:
            List of string class names of all registered importers.
        """
        importer_names = []
        for importer in self._importers:
            importer_names.append(importer.__class__.__name__)
        
        logger.debug(f"Returning {len(importer_names)} registered importer names")
        return importer_names
    
    def get_importer_count(self) -> int:
        """Returns the number of registered importers.
        
        Returns:
            Integer count of registered importers.
        """
        return len(self._importers)
    
    def clear_importers(self):
        """Clears all registered importers.
        
        This method is primarily intended for testing purposes to reset
        the registry to a clean state.
        """
        logger.info(f"Clearing {len(self._importers)} registered importers")
        self._importers.clear()
        logger.debug("All importers cleared from registry")
    
    def __repr__(self) -> str:
        """Return string representation of the registry."""
        return f"ImporterRegistry(importers={len(self._importers)})"
    
    def __str__(self) -> str:
        """Return human-readable string representation."""
        importer_names = self.get_registered_importers()
        return f"ImporterRegistry with {len(importer_names)} importers: {', '.join(importer_names)}"


# Create a single, globally accessible instance
# This singleton pattern ensures consistent importer registry across the application
logger.info("Creating global importer_registry instance")
importer_registry = ImporterRegistry()
logger.info("Global importer_registry instance created successfully")