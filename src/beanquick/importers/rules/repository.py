"""
Enhanced Rule Repository with SQLite Backend.

This module provides an updated RuleRepository class that uses SQLite for
high-performance rule storage while maintaining the same interface as the
original YAML-based implementation.
"""

from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import logging
from typing import Optional, List, Dict, Any

from beanquick.importers.core.data import ImporterMetadata
from . import TransactionRule
from .storage.sqlite_repository import SQLiteRuleRepository

logger = logging.getLogger(__name__)


class RuleRepository:
    """Enhanced rule repository with SQLite backend.
    
    This repository provides significant performance improvements over the
    YAML-based approach while maintaining full API compatibility.
    """
    
    def __init__(self, importer_id: str, importer_metadata: Optional[ImporterMetadata] = None, app_paths=None):
        """Initialize the rule repository.
        
        Args:
            importer_id: Identifier for the importer (required)
            importer_metadata: Metadata for the importer (optional)
            app_paths: Application paths object with config directory (required)
        """
        if not importer_id:
            raise ValueError("importer_id is required and cannot be None or empty")
        
        if app_paths is None:
            raise ValueError("app_paths is required and cannot be None")
        
        self._importer_id = importer_id
        self._importer_metadata = importer_metadata
        
        # Create SQLite repository
        db_path = app_paths.config / "rules.db"
        self._repository = SQLiteRuleRepository(importer_id, db_path)
        
        # Batch mode state
        self._batch_updates: List[tuple] = []
        self._batch_mode = False
        
        logger.debug(f"Enhanced RuleRepository initialized for importer: {importer_id}")
    
    @property
    def importer_name(self) -> str:
        """Get the importer name from the metadata."""
        if self._importer_metadata and self._importer_metadata.name:
            return self._importer_metadata.name
        return self._importer_id
    
    @property
    def importer_icon(self) -> str:
        """Get the importer icon from the metadata."""
        if self._importer_metadata and self._importer_metadata.icon:
            return self._importer_metadata.icon
        return ""
    
    def save_rule(self, rule: TransactionRule) -> None:
        """Save a rule to the repository.
        
        Args:
            rule: The TransactionRule to save
            
        Raises:
            ValueError: If the rule is invalid
        """
        self._repository.save_rule(rule)
    
    def get_rule_by_id(self, rule_id: str) -> Optional[TransactionRule]:
        """Get a specific rule by its ID.
        
        Args:
            rule_id: The ID of the rule to retrieve
            
        Returns:
            The rule if found, None otherwise
        """
        return self._repository.get_rule_by_id(rule_id)
    
    def get_all_rules(self) -> List[TransactionRule]:
        """Get all rules from the repository.
        
        Returns:
            List of all rules, sorted by creation date (newest first)
        """
        return self._repository.get_all_rules()
    
    def get_all_enabled_rules(self) -> List[TransactionRule]:
        """Get all enabled rules from the repository.
        
        Returns:
            List of enabled rules, sorted by priority and usage
        """
        return self._repository.get_all_enabled_rules()
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule from the repository.
        
        Args:
            rule_id: The ID of the rule to delete
            
        Returns:
            True if the rule was deleted, False if not found
        """
        return self._repository.delete_rule(rule_id)
    
    def update_rule_stats(self, rule_id: str, application_count: int) -> bool:
        """Update rule statistics.
        
        Args:
            rule_id: The ID of the rule to update
            application_count: The new application count
            
        Returns:
            True if update was successful, False otherwise
        """
        if self._batch_mode:
            # Collect updates for batch processing
            self._batch_updates.append((rule_id, application_count))
            return True
        else:
            # Update immediately
            return self._repository.update_rule_stats(rule_id, application_count)
    
    def rule_exists(self, rule_id: str) -> bool:
        """Check if a rule exists in the repository.
        
        Args:
            rule_id: The ID of the rule to check
            
        Returns:
            True if the rule exists, False otherwise
        """
        return self._repository.rule_exists(rule_id)
    
    def get_rule_count(self) -> int:
        """Get the total number of rules in the repository.
        
        Returns:
            Number of rules
        """
        return self._repository.get_rule_count()
    
    @property
    def rule_count(self) -> int:
        """Get the total number of rules (property version)."""
        return self.get_rule_count()
    
    @property
    def enabled_rule_count(self) -> int:
        """Get the number of enabled rules."""
        stats = self._repository.get_statistics()
        return stats.get('enabled_rules', 0)
    
    def begin_batch_updates(self) -> None:
        """Begin batch mode for rule statistics updates.
        
        During batch mode, rule statistics updates are accumulated in memory
        without writing to disk. Call end_batch_updates() to persist all changes.
        """
        self._batch_mode = True
        self._batch_updates.clear()
        logger.debug(f"Batch mode started for importer {self._importer_id}")
    
    def end_batch_updates(self) -> bool:
        """End batch mode and persist all accumulated updates.
        
        Returns:
            True if all updates were successfully persisted, False otherwise
        """
        if not self._batch_mode:
            return True
        
        try:
            if self._batch_updates:
                count = self._repository.batch_update_stats(self._batch_updates)
                logger.debug(f"Batch updated {count} rule statistics for importer {self._importer_id}")
                success = count == len(self._batch_updates)
            else:
                success = True
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to process batch updates: {e}", exc_info=True)
            return False
            
        finally:
            self._batch_mode = False
            self._batch_updates.clear()

    def get_rule_statistics(self) -> Dict[str, int]:
        """Get statistics about the rules in this repository.
        
        Returns:
            Dictionary containing rule statistics
        """
        stats = self._repository.get_statistics()
        
        # Convert to the expected format for backwards compatibility
        return {
            "total_rules": stats.get('total_rules', 0),
            "enabled_rules": stats.get('enabled_rules', 0),
            "disabled_rules": stats.get('disabled_rules', 0),
            "stop_processing_rules": stats.get('stop_processing_rules', 0),
            "rules_with_actions": stats.get('total_rules', 0)  # Assume all rules have actions
        }
    
    def get_rules_by_enabled_status(self, enabled: bool) -> List[TransactionRule]:
        """Get rules filtered by enabled status.
        
        Args:
            enabled: True for enabled rules, False for disabled rules
            
        Returns:
            List of rules matching the enabled status
        """
        from .storage.models import RuleQuery
        
        query = RuleQuery(
            importer_id=self._importer_id,
            is_enabled=enabled,
            order_by="created_date DESC"
        )
        
        return self._repository.query_rules(query)
    
    def get_rules_with_stop_processing(self) -> List[TransactionRule]:
        """Get all enabled rules that have stop_processing=True.
        
        Returns:
            List of rules with stop processing enabled
        """
        # Since we don't have a direct query for stop_processing in RuleQuery,
        # we'll get all enabled rules and filter
        enabled_rules = self.get_all_enabled_rules()
        return [rule for rule in enabled_rules if rule.stop_processing]
    
    def clear_all_rules(self) -> None:
        """Clear all rules from the repository.
        
        This method is primarily intended for testing purposes.
        """
        success = self._repository.clear_all_rules()
        if success:
            logger.debug(f"Successfully cleared all rules for importer {self._importer_id}")
        else:
            logger.warning(f"Failed to clear rules for importer {self._importer_id}")
    
    def reload_rules(self) -> None:
        """Reload rules from persistent storage.
        
        Note: For SQLite backend, this is essentially a no-op since rules
        are always loaded fresh from the database.
        """
        logger.debug(f"Reload requested for importer {self._importer_id} (SQLite backend always fresh)")
    
    def validate_all_rules(self) -> Dict[str, List[str]]:
        """Validate all rules in the repository.
        
        Returns:
            Dictionary mapping rule_id to list of validation errors
        """
        validation_results = {}
        all_rules = self.get_all_rules()
        
        for rule in all_rules:
            # Use the same validation logic as the original repository
            validation_errors = self._validate_rule(rule)
            validation_results[rule.rule_id] = validation_errors
        
        return validation_results
    
    def _validate_rule(self, rule: TransactionRule) -> List[str]:
        """Validate a single rule (internal method).
        
        Args:
            rule: Rule to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not rule:
            errors.append("Rule cannot be None")
            return errors
        
        if not rule.rule_id or not rule.rule_id.strip():
            errors.append("Rule must have a non-empty rule_id")
        
        if not rule.name or not rule.name.strip():
            errors.append("Rule must have a non-empty name")
        
        if not isinstance(rule.is_enabled, bool):
            errors.append("is_enabled must be a boolean")
        
        if not isinstance(rule.stop_processing, bool):
            errors.append("stop_processing must be a boolean")
        
        if rule.application_count < 0:
            errors.append("application_count cannot be negative")
        
        if not rule.conditions_block:
            errors.append("Rule must have a conditions block")
        
        if not rule.actions:
            errors.append("Rule must have at least one action")
        
        return errors
    
    # Performance and maintenance methods
    
    def vacuum_database(self) -> None:
        """Optimize the database storage."""
        self._repository.vacuum_database()
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics."""
        return self._repository.get_database_info()
    
    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics about the repository."""
        return self._repository.get_statistics()
