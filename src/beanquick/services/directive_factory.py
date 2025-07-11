"""
Directive Factory - Maps directive types to their form classes and metadata.
"""
from __future__ import annotations

import logging
from typing import Dict, Type, List
from dataclasses import dataclass

from beanquick.ui.forms.base_form import BaseDirectiveForm
from beanquick.ui.forms.transaction_form import TransactionForm
from beanquick.ui.forms.balance_form import BalanceForm

logger = logging.getLogger(__name__)

@dataclass
class DirectiveMetadata:
    """Metadata about a directive type."""
    name: str
    display_name: str
    description: str
    form_class: Type[BaseDirectiveForm]
    icon: str = ""
    category: str = "General"

class DirectiveFactory:
    """Factory for creating directive forms and managing directive metadata."""
    
    # Registry of all supported directive types
    _DIRECTIVE_REGISTRY: Dict[str, DirectiveMetadata] = {
        "transaction": DirectiveMetadata(
            name="transaction",
            display_name="Transaction",
            description="Record income, expenses, and transfers between accounts",
            form_class=TransactionForm,
            icon="💸",
            category="Core"
        ),
        "balance": DirectiveMetadata(
            name="balance",
            display_name="Balance",
            description="Assert the balance of an account at a specific date",
            form_class=BalanceForm,
            icon="⚖️",
            category="Validation"
        ),
        # TODO: Add other directive types as we implement their forms
        # "open": DirectiveMetadata(
        #     name="open",
        #     display_name="Open",
        #     description="Open a new account",
        #     form_class=OpenForm,
        #     icon="🔓",
        #     category="Account Management"
        # ),
        # "close": DirectiveMetadata(
        #     name="close",
        #     display_name="Close",
        #     description="Close an existing account",
        #     form_class=CloseForm,
        #     icon="🔒",
        #     category="Account Management"
        # ),
    }
    
    @classmethod
    def get_directive_types(cls) -> List[str]:
        """Get all supported directive type names."""
        return list(cls._DIRECTIVE_REGISTRY.keys())
    
    @classmethod
    def get_directive_display_names(cls) -> List[str]:
        """Get display names for all directive types."""
        return [meta.display_name for meta in cls._DIRECTIVE_REGISTRY.values()]
    
    @classmethod
    def get_directive_metadata(cls, directive_type: str) -> DirectiveMetadata:
        """Get metadata for a specific directive type."""
        if directive_type not in cls._DIRECTIVE_REGISTRY:
            raise ValueError(f"Unknown directive type: {directive_type}")
        return cls._DIRECTIVE_REGISTRY[directive_type]
    
    @classmethod
    def create_form(cls, directive_type: str, **kwargs) -> BaseDirectiveForm:
        """Create a form instance for the specified directive type."""
        metadata = cls.get_directive_metadata(directive_type)
        logger.debug(f"Creating form for directive type: {directive_type}")
        return metadata.form_class(**kwargs)
    
    @classmethod
    def get_directive_type_by_display_name(cls, display_name: str) -> str:
        """Get directive type name by its display name."""
        for directive_type, metadata in cls._DIRECTIVE_REGISTRY.items():
            if metadata.display_name == display_name:
                return directive_type
        raise ValueError(f"Unknown directive display name: {display_name}")
    
    @classmethod
    def get_directive_categories(cls) -> Dict[str, List[str]]:
        """Get directive types grouped by category."""
        categories: Dict[str, List[str]] = {}
        for directive_type, metadata in cls._DIRECTIVE_REGISTRY.items():
            category = metadata.category
            if category not in categories:
                categories[category] = []
            categories[category].append(directive_type)
        return categories
    
    @classmethod
    def register_directive(cls, directive_type: str, metadata: DirectiveMetadata):
        """Register a new directive type (for extensibility)."""
        cls._DIRECTIVE_REGISTRY[directive_type] = metadata
        logger.info(f"Registered new directive type: {directive_type}")
    
    @classmethod
    def is_directive_supported(cls, directive_type: str) -> bool:
        """Check if a directive type is supported."""
        return directive_type in cls._DIRECTIVE_REGISTRY