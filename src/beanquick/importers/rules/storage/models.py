"""
Data models for SQLite rule storage.

This module provides dataclass models for representing rule data in the SQLite
storage layer, with built-in JSON serialization/deserialization for complex fields.
"""

from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RuleData:
    """Data model for SQLite rule storage."""
    rule_id: str
    importer_id: str
    name: str
    is_enabled: bool = True
    stop_processing: bool = False
    priority: int = 0
    conditions_json: str = "{}"
    actions_json: str = "[]"
    created_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    application_count: int = 0
    last_applied: Optional[datetime] = None
    metadata_json: str = "{}"
    
    def __post_init__(self):
        """Set default timestamps."""
        now = datetime.now()
        if self.created_date is None:
            self.created_date = now
        if self.updated_date is None:
            self.updated_date = now
    
    @property
    def conditions(self) -> Dict[str, Any]:
        """Parse conditions from JSON."""
        try:
            return json.loads(self.conditions_json)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse conditions JSON for rule {self.rule_id}: {e}")
            return {}
    
    @conditions.setter
    def conditions(self, value: Dict[str, Any]) -> None:
        """Serialize conditions to JSON."""
        try:
            self.conditions_json = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize conditions for rule {self.rule_id}: {e}")
            self.conditions_json = "{}"
    
    @property
    def actions(self) -> List[Dict[str, Any]]:
        """Parse actions from JSON."""
        try:
            return json.loads(self.actions_json)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse actions JSON for rule {self.rule_id}: {e}")
            return []
    
    @actions.setter
    def actions(self, value: List[Dict[str, Any]]) -> None:
        """Serialize actions to JSON."""
        try:
            self.actions_json = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize actions for rule {self.rule_id}: {e}")
            self.actions_json = "[]"
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Parse metadata from JSON."""
        try:
            return json.loads(self.metadata_json)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse metadata JSON for rule {self.rule_id}: {e}")
            return {}
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        """Serialize metadata to JSON."""
        try:
            self.metadata_json = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize metadata for rule {self.rule_id}: {e}")
            self.metadata_json = "{}"


@dataclass
class RuleQuery:
    """Query parameters for rule searching and filtering."""
    importer_id: Optional[str] = None
    is_enabled: Optional[bool] = None
    name_pattern: Optional[str] = None
    priority_min: Optional[int] = None
    priority_max: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    last_applied_after: Optional[datetime] = None
    last_applied_before: Optional[datetime] = None
    application_count_min: Optional[int] = None
    application_count_max: Optional[int] = None
    limit: Optional[int] = None
    offset: int = 0
    order_by: str = "priority DESC, application_count DESC"
    
    def build_where_clause(self) -> tuple[str, list]:
        """Build SQL WHERE clause and parameters from query criteria.
        
        Returns:
            Tuple of (where_clause, parameters)
        """
        conditions = ["1=1"]  # Always true base condition
        params = []
        
        if self.importer_id:
            conditions.append("importer_id = ?")
            params.append(self.importer_id)
        
        if self.is_enabled is not None:
            conditions.append("is_enabled = ?")
            params.append(self.is_enabled)
        
        if self.name_pattern:
            conditions.append("name LIKE ?")
            params.append(f"%{self.name_pattern}%")
        
        if self.priority_min is not None:
            conditions.append("priority >= ?")
            params.append(self.priority_min)
        
        if self.priority_max is not None:
            conditions.append("priority <= ?")
            params.append(self.priority_max)
        
        if self.created_after:
            conditions.append("created_date >= ?")
            params.append(self.created_after.isoformat())
        
        if self.created_before:
            conditions.append("created_date <= ?")
            params.append(self.created_before.isoformat())
        
        if self.last_applied_after:
            conditions.append("last_applied >= ?")
            params.append(self.last_applied_after.isoformat())
        
        if self.last_applied_before:
            conditions.append("last_applied <= ?")
            params.append(self.last_applied_before.isoformat())
        
        if self.application_count_min is not None:
            conditions.append("application_count >= ?")
            params.append(self.application_count_min)
        
        if self.application_count_max is not None:
            conditions.append("application_count <= ?")
            params.append(self.application_count_max)
        
        where_clause = " AND ".join(conditions)
        return where_clause, params
    
    def build_order_clause(self) -> str:
        """Build SQL ORDER BY clause."""
        return f"ORDER BY {self.order_by}"
    
    def build_limit_clause(self) -> tuple[str, list]:
        """Build SQL LIMIT clause with parameters.
        
        Returns:
            Tuple of (limit_clause, parameters)
        """
        if self.limit:
            return "LIMIT ? OFFSET ?", [self.limit, self.offset]
        elif self.offset > 0:
            return "OFFSET ?", [self.offset]
        else:
            return "", []


@dataclass
class ImporterData:
    """Data model for importer metadata storage."""
    importer_id: str
    name: str
    icon: Optional[str] = None
    region: Optional[str] = None
    institution: Optional[str] = None
    created_date: Optional[datetime] = None
    metadata_json: str = "{}"
    
    def __post_init__(self):
        """Set default timestamp."""
        if self.created_date is None:
            self.created_date = datetime.now()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Parse metadata from JSON."""
        try:
            return json.loads(self.metadata_json)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse metadata JSON for importer {self.importer_id}: {e}")
            return {}
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        """Serialize metadata to JSON."""
        try:
            self.metadata_json = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize metadata for importer {self.importer_id}: {e}")
            self.metadata_json = "{}"


@dataclass
class RuleApplicationData:
    """Data model for rule application history."""
    rule_id: str
    importer_id: str
    transaction_hash: Optional[str] = None
    applied_date: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    id: Optional[int] = None  # Auto-generated primary key
    
    def __post_init__(self):
        """Set default timestamp."""
        if self.applied_date is None:
            self.applied_date = datetime.now()


# Type aliases for better documentation
RuleStatistics = Dict[str, Any]
ImporterStatistics = Dict[str, Any]
