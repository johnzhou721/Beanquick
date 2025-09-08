"""
SQLite-based repository implementation for transaction rules.

This module provides a high-performance SQLite repository that replaces the
YAML-based storage with significant improvements in speed, reliability, and
scalability while maintaining the same interface.
"""

from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .database_manager import DatabaseManager
from .models import RuleData, RuleQuery, RuleStatistics
from .converters import TransactionRuleConverter, RuleStatisticsConverter
from .. import TransactionRule

logger = logging.getLogger(__name__)


class SQLiteRuleRepository:
    """SQLite-based rule repository with optimized performance."""
    
    def __init__(self, importer_id: str, db_path: Path):
        """Initialize SQLite repository for the specified importer.
        
        Args:
            importer_id: Identifier for the importer
            db_path: Path to the SQLite database file
            
        Raises:
            ValueError: If importer_id is empty or None
        """
        if not importer_id:
            raise ValueError("importer_id is required and cannot be None or empty")
        
        self.importer_id = importer_id
        self._db_manager = DatabaseManager(db_path)
        self._converter = TransactionRuleConverter()
        self._stats_converter = RuleStatisticsConverter()
        
        logger.debug(f"SQLiteRuleRepository initialized for importer: {importer_id}")
    
    def save_rule(self, rule: TransactionRule) -> None:
        """Save or update a rule in the database.
        
        Args:
            rule: TransactionRule to save
            
        Raises:
            ValueError: If rule is invalid
            RuntimeError: If database operation fails
        """
        if not rule:
            raise ValueError("Rule cannot be None")
        
        if not rule.rule_id:
            raise ValueError("Rule must have a valid rule_id")
        
        try:
            rule_data = self._converter.to_data_model(rule, self.importer_id)
            
            with self._db_manager.transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO rules (
                        rule_id, importer_id, name, is_enabled, stop_processing, priority,
                        conditions_json, actions_json, created_date, updated_date,
                        application_count, last_applied, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rule_data.rule_id, rule_data.importer_id, rule_data.name,
                    rule_data.is_enabled, rule_data.stop_processing, rule_data.priority,
                    rule_data.conditions_json, rule_data.actions_json,
                    rule_data.created_date.isoformat() if rule_data.created_date else datetime.now().isoformat(),
                    rule_data.updated_date.isoformat() if rule_data.updated_date else datetime.now().isoformat(),
                    rule_data.application_count,
                    rule_data.last_applied.isoformat() if rule_data.last_applied else None,
                    rule_data.metadata_json
                ))
            
            logger.debug(f"Rule saved: {rule.rule_id}")
            
        except Exception as e:
            logger.error(f"Failed to save rule {rule.rule_id}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to save rule: {e}") from e
    
    def get_rule_by_id(self, rule_id: str) -> Optional[TransactionRule]:
        """Get a rule by its ID.
        
        Args:
            rule_id: ID of the rule to retrieve
            
        Returns:
            TransactionRule instance or None if not found
        """
        if not rule_id:
            return None
        
        try:
            with self._db_manager.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM rules WHERE rule_id = ? AND importer_id = ?",
                    (rule_id, self.importer_id)
                ).fetchone()
                
                return self._converter.from_row(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get rule {rule_id}: {e}", exc_info=True)
            return None
    
    def get_all_enabled_rules(self) -> List[TransactionRule]:
        """Get all enabled rules ordered by priority and usage.
        
        Returns:
            List of enabled TransactionRule instances
        """
        return self.query_rules(RuleQuery(
            importer_id=self.importer_id,
            is_enabled=True,
            order_by="priority DESC, application_count DESC"
        ))
    
    def get_all_rules(self) -> List[TransactionRule]:
        """Get all rules for this importer.
        
        Returns:
            List of all TransactionRule instances
        """
        return self.query_rules(RuleQuery(
            importer_id=self.importer_id,
            order_by="created_date DESC"
        ))
    
    def query_rules(self, query: RuleQuery) -> List[TransactionRule]:
        """Query rules with flexible criteria.
        
        Args:
            query: RuleQuery object specifying search criteria
            
        Returns:
            List of matching TransactionRule instances
        """
        try:
            where_clause, where_params = query.build_where_clause()
            order_clause = query.build_order_clause()
            limit_clause, limit_params = query.build_limit_clause()
            
            sql_parts = [
                "SELECT * FROM rules",
                f"WHERE {where_clause}",
                order_clause
            ]
            
            if limit_clause:
                sql_parts.append(limit_clause)
            
            sql = " ".join(sql_parts)
            params = where_params + limit_params
            
            with self._db_manager.get_connection() as conn:
                rows = conn.execute(sql, params).fetchall()
                
                rules = []
                for row in rows:
                    rule = self._converter.from_row(row)
                    if rule:
                        rules.append(rule)
                    else:
                        logger.warning(f"Failed to convert row to rule: {dict(row)}")
                
                logger.debug(f"Query returned {len(rules)} rules for importer {self.importer_id}")
                return rules
                
        except Exception as e:
            logger.error(f"Failed to query rules: {e}", exc_info=True)
            return []
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule from the database.
        
        Args:
            rule_id: ID of the rule to delete
            
        Returns:
            True if rule was deleted, False if not found
        """
        if not rule_id:
            return False
        
        try:
            with self._db_manager.transaction() as conn:
                cursor = conn.execute(
                    "DELETE FROM rules WHERE rule_id = ? AND importer_id = ?",
                    (rule_id, self.importer_id)
                )
                
                success = cursor.rowcount > 0
                logger.debug(f"Rule deletion {'successful' if success else 'failed'}: {rule_id}")
                return success
                
        except Exception as e:
            logger.error(f"Failed to delete rule {rule_id}: {e}", exc_info=True)
            return False
    
    def update_rule_stats(self, rule_id: str, application_count: int) -> bool:
        """Update rule statistics efficiently.
        
        Args:
            rule_id: ID of the rule to update
            application_count: New application count
            
        Returns:
            True if update was successful, False otherwise
        """
        if not rule_id or application_count < 0:
            return False
        
        try:
            with self._db_manager.transaction() as conn:
                cursor = conn.execute("""
                    UPDATE rules 
                    SET application_count = ?, last_applied = ?, updated_date = ?
                    WHERE rule_id = ? AND importer_id = ?
                """, (
                    application_count,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    rule_id,
                    self.importer_id
                ))
                
                success = cursor.rowcount > 0
                if success:
                    logger.debug(f"Updated stats for rule {rule_id}: count={application_count}")
                else:
                    logger.warning(f"No rule found to update stats: {rule_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to update rule stats {rule_id}: {e}", exc_info=True)
            return False
    
    def batch_update_stats(self, updates: List[tuple]) -> int:
        """Batch update multiple rule statistics.
        
        Args:
            updates: List of (rule_id, application_count) tuples
            
        Returns:
            Number of rules successfully updated
        """
        if not updates:
            return 0
        
        try:
            updated_count = 0
            now = datetime.now().isoformat()
            
            with self._db_manager.transaction() as conn:
                for rule_id, application_count in updates:
                    if not rule_id or application_count < 0:
                        continue
                    
                    cursor = conn.execute("""
                        UPDATE rules 
                        SET application_count = ?, last_applied = ?, updated_date = ?
                        WHERE rule_id = ? AND importer_id = ?
                    """, (
                        application_count,
                        now,
                        now,
                        rule_id,
                        self.importer_id
                    ))
                    updated_count += cursor.rowcount
                
                logger.debug(f"Batch updated {updated_count} rule statistics")
                return updated_count
                
        except Exception as e:
            logger.error(f"Failed to batch update rule stats: {e}", exc_info=True)
            return 0
    
    def get_statistics(self) -> RuleStatistics:
        """Get comprehensive repository statistics.
        
        Returns:
            Dictionary containing various statistics about the rules
        """
        try:
            with self._db_manager.get_connection() as conn:
                # Basic counts
                stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total_rules,
                        COUNT(CASE WHEN is_enabled = 1 THEN 1 END) as enabled_rules,
                        COUNT(CASE WHEN is_enabled = 0 THEN 1 END) as disabled_rules,
                        COUNT(CASE WHEN stop_processing = 1 THEN 1 END) as stop_processing_rules,
                        SUM(application_count) as total_applications,
                        AVG(application_count) as avg_applications,
                        MAX(application_count) as max_applications,
                        COUNT(CASE WHEN last_applied IS NOT NULL THEN 1 END) as applied_rules
                    FROM rules 
                    WHERE importer_id = ?
                """, (self.importer_id,)).fetchone()
                
                # Most used rule
                most_used = conn.execute("""
                    SELECT rule_id, name, application_count
                    FROM rules 
                    WHERE importer_id = ? AND application_count > 0
                    ORDER BY application_count DESC
                    LIMIT 1
                """, (self.importer_id,)).fetchone()
                
                # Newest rule
                newest = conn.execute("""
                    SELECT rule_id, name, created_date
                    FROM rules 
                    WHERE importer_id = ?
                    ORDER BY created_date DESC
                    LIMIT 1
                """, (self.importer_id,)).fetchone()
                
                result = dict(stats) if stats else {}
                
                if most_used:
                    result['most_used_rule'] = {
                        'rule_id': most_used['rule_id'],
                        'name': most_used['name'],
                        'application_count': most_used['application_count']
                    }
                
                if newest:
                    result['newest_rule'] = {
                        'rule_id': newest['rule_id'],
                        'name': newest['name'],
                        'created_date': newest['created_date']
                    }
                
                # Set defaults for missing values
                for key in ['total_rules', 'enabled_rules', 'disabled_rules', 
                           'stop_processing_rules', 'total_applications', 'applied_rules']:
                    if key not in result:
                        result[key] = 0
                
                if 'avg_applications' not in result:
                    result['avg_applications'] = 0.0
                elif result['avg_applications']:
                    result['avg_applications'] = round(result['avg_applications'], 2)
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return {}
    
    def rule_exists(self, rule_id: str) -> bool:
        """Check if a rule exists.
        
        Args:
            rule_id: ID of the rule to check
            
        Returns:
            True if rule exists, False otherwise
        """
        if not rule_id:
            return False
        
        try:
            with self._db_manager.get_connection() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM rules WHERE rule_id = ? AND importer_id = ?",
                    (rule_id, self.importer_id)
                ).fetchone()[0]
                
                return count > 0
                
        except Exception as e:
            logger.error(f"Failed to check rule existence {rule_id}: {e}", exc_info=True)
            return False
    
    def get_rule_count(self) -> int:
        """Get total number of rules for this importer.
        
        Returns:
            Number of rules
        """
        try:
            with self._db_manager.get_connection() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM rules WHERE importer_id = ?",
                    (self.importer_id,)
                ).fetchone()[0]
                
                return count
                
        except Exception as e:
            logger.error(f"Failed to get rule count: {e}", exc_info=True)
            return 0
    
    def clear_all_rules(self) -> bool:
        """Clear all rules for this importer.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._db_manager.transaction() as conn:
                cursor = conn.execute(
                    "DELETE FROM rules WHERE importer_id = ?",
                    (self.importer_id,)
                )
                
                deleted_count = cursor.rowcount
                logger.debug(f"Cleared {deleted_count} rules for importer {self.importer_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear rules: {e}", exc_info=True)
            return False
    
    def vacuum_database(self) -> None:
        """Optimize the database by running VACUUM."""
        try:
            self._db_manager.vacuum()
            logger.debug("Database vacuum completed")
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}", exc_info=True)
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics."""
        try:
            db_info = self._db_manager.get_database_info()
            db_info['importer_id'] = self.importer_id
            return db_info
        except Exception as e:
            logger.error(f"Failed to get database info: {e}", exc_info=True)
            return {'importer_id': self.importer_id}
