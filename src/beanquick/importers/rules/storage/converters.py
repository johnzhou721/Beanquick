"""
Converters between TransactionRule entities and SQLite data models.

This module provides conversion utilities to bridge the gap between the domain
entities (TransactionRule) and the data models used for SQLite storage.
"""

from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional

from .models import RuleData
from .. import TransactionRule
from ..serialization import rule_to_dict, dict_to_rule

logger = logging.getLogger(__name__)


class TransactionRuleConverter:
    """Converts between TransactionRule entities and SQLite data models."""
    
    def to_data_model(self, rule: TransactionRule, importer_id: str) -> RuleData:
        """Convert TransactionRule to RuleData for storage.
        
        Args:
            rule: TransactionRule entity to convert
            importer_id: ID of the importer this rule belongs to
            
        Returns:
            RuleData instance ready for SQLite storage
            
        Raises:
            ValueError: If rule or importer_id is invalid
            TypeError: If rule is not a TransactionRule instance
        """
        if not rule:
            raise ValueError("Rule cannot be None")
        
        if not isinstance(rule, TransactionRule):
            raise TypeError("Expected TransactionRule instance")
        
        if not importer_id:
            raise ValueError("importer_id cannot be None or empty")
        
        try:
            # Convert rule to dictionary using existing serialization
            rule_dict = rule_to_dict(rule)
            
            return RuleData(
                rule_id=rule.rule_id,
                importer_id=importer_id,
                name=rule.name,
                is_enabled=rule.is_enabled,
                stop_processing=rule.stop_processing,
                priority=getattr(rule, 'priority', 0),
                conditions_json=json.dumps(rule_dict.get('conditions_block', {}), ensure_ascii=False),
                actions_json=json.dumps(rule_dict.get('actions', []), ensure_ascii=False),
                created_date=rule.created_date,
                updated_date=datetime.now(),
                application_count=rule.application_count,
                last_applied=rule.last_applied,
                metadata_json=json.dumps(rule_dict.get('metadata', {}), ensure_ascii=False)
            )
            
        except Exception as e:
            logger.error(f"Failed to convert rule {rule.rule_id} to data model: {e}", exc_info=True)
            raise ValueError(f"Rule conversion failed: {e}") from e
    
    def _safe_datetime_conversion(self, value) -> Optional[datetime]:
        """Safely convert a value to datetime, handling both string and datetime inputs.
        
        Args:
            value: String, datetime, or None
            
        Returns:
            datetime object or None
        """
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as e:
                logger.warning(f"Failed to parse datetime string '{value}': {e}")
                return None
        
        logger.warning(f"Unexpected datetime value type: {type(value)}")
        return None
    
    def from_row(self, row: sqlite3.Row) -> Optional[TransactionRule]:
        """Convert SQLite row to TransactionRule entity.
        
        Args:
            row: SQLite row containing rule data
            
        Returns:
            TransactionRule instance or None if conversion fails
        """
        if not row:
            return None
        
        try:
            # Reconstruct rule dictionary for deserialization
            rule_dict = {
                'rule_id': row['rule_id'],
                'name': row['name'],
                'is_enabled': bool(row['is_enabled']),
                'stop_processing': bool(row['stop_processing']),
                'conditions_block': json.loads(row['conditions_json']),
                'actions': json.loads(row['actions_json']),
                'created_date': self._safe_datetime_conversion(row['created_date']),
                'application_count': row['application_count'],
                'last_applied': self._safe_datetime_conversion(row['last_applied']),
                'metadata': json.loads(row['metadata_json'])
            }
            
            # Add priority if present
            if 'priority' in row.keys():
                rule_dict['priority'] = row['priority']
            
            # Use existing deserialization logic
            return dict_to_rule(rule_dict)
            
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            logger.error(f"Failed to convert row to rule: {e}", exc_info=True)
            logger.debug(f"Row data: {dict(row) if row else 'None'}")
            return None
    
    def from_data_model(self, rule_data: RuleData) -> Optional[TransactionRule]:
        """Convert RuleData to TransactionRule entity.
        
        Args:
            rule_data: RuleData instance to convert
            
        Returns:
            TransactionRule instance or None if conversion fails
        """
        if not rule_data:
            return None
        
        try:
            # Build rule dictionary
            rule_dict = {
                'rule_id': rule_data.rule_id,
                'name': rule_data.name,
                'is_enabled': rule_data.is_enabled,
                'stop_processing': rule_data.stop_processing,
                'conditions_block': rule_data.conditions,
                'actions': rule_data.actions,
                'created_date': rule_data.created_date,
                'application_count': rule_data.application_count,
                'last_applied': rule_data.last_applied,
                'metadata': rule_data.metadata
            }
            
            # Add priority if present
            if hasattr(rule_data, 'priority'):
                rule_dict['priority'] = rule_data.priority
            
            return dict_to_rule(rule_dict)
            
        except Exception as e:
            logger.error(f"Failed to convert data model to rule: {e}", exc_info=True)
            return None
    
    def update_rule_from_data(self, rule: TransactionRule, rule_data: RuleData) -> TransactionRule:
        """Update a TransactionRule with data from RuleData.
        
        Args:
            rule: Existing TransactionRule to update
            rule_data: RuleData containing new values
            
        Returns:
            Updated TransactionRule instance
        """
        if not rule or not rule_data:
            raise ValueError("Both rule and rule_data are required")
        
        try:
            # Update basic fields
            rule.name = rule_data.name
            rule.is_enabled = rule_data.is_enabled
            rule.stop_processing = rule_data.stop_processing
            rule.application_count = rule_data.application_count
            rule.last_applied = rule_data.last_applied
            
            # Update priority if supported
            if hasattr(rule, 'priority') and hasattr(rule_data, 'priority'):
                setattr(rule, 'priority', rule_data.priority)
            
            # Note: We don't update conditions and actions here as they require
            # complex object reconstruction. For those changes, use from_data_model.
            
            logger.debug(f"Updated rule {rule.rule_id} from data model")
            return rule
            
        except Exception as e:
            logger.error(f"Failed to update rule from data model: {e}", exc_info=True)
            raise ValueError(f"Rule update failed: {e}") from e


class RuleStatisticsConverter:
    """Converter for rule statistics and metadata."""
    
    @staticmethod
    def extract_statistics(rule: TransactionRule) -> dict:
        """Extract statistics from a TransactionRule.
        
        Args:
            rule: TransactionRule to extract statistics from
            
        Returns:
            Dictionary containing rule statistics
        """
        return {
            'rule_id': rule.rule_id,
            'name': rule.name,
            'is_enabled': rule.is_enabled,
            'application_count': rule.application_count,
            'last_applied': rule.last_applied.isoformat() if rule.last_applied else None,
            'created_date': rule.created_date.isoformat(),
            'has_conditions': bool(rule.conditions_block),
            'action_count': len(rule.actions),
            'stop_processing': rule.stop_processing
        }
    
    @staticmethod
    def build_summary_statistics(rules: list[TransactionRule]) -> dict:
        """Build summary statistics for a collection of rules.
        
        Args:
            rules: List of TransactionRule instances
            
        Returns:
            Dictionary containing summary statistics
        """
        if not rules:
            return {
                'total_rules': 0,
                'enabled_rules': 0,
                'disabled_rules': 0,
                'total_applications': 0,
                'rules_with_applications': 0,
                'stop_processing_rules': 0,
                'average_applications': 0.0,
                'most_used_rule': None,
                'newest_rule': None
            }
        
        enabled_rules = [r for r in rules if r.is_enabled]
        disabled_rules = [r for r in rules if not r.is_enabled]
        rules_with_applications = [r for r in rules if r.application_count > 0]
        stop_processing_rules = [r for r in enabled_rules if r.stop_processing]
        
        total_applications = sum(r.application_count for r in rules)
        avg_applications = total_applications / len(rules) if rules else 0.0
        
        most_used_rule = max(rules, key=lambda r: r.application_count) if rules else None
        newest_rule = max(rules, key=lambda r: r.created_date) if rules else None
        
        return {
            'total_rules': len(rules),
            'enabled_rules': len(enabled_rules),
            'disabled_rules': len(disabled_rules),
            'total_applications': total_applications,
            'rules_with_applications': len(rules_with_applications),
            'stop_processing_rules': len(stop_processing_rules),
            'average_applications': round(avg_applications, 2),
            'most_used_rule': {
                'rule_id': most_used_rule.rule_id,
                'name': most_used_rule.name,
                'application_count': most_used_rule.application_count
            } if most_used_rule else None,
            'newest_rule': {
                'rule_id': newest_rule.rule_id,
                'name': newest_rule.name,
                'created_date': newest_rule.created_date.isoformat()
            } if newest_rule else None
        }
