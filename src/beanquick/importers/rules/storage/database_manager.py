"""
Database connection and schema management for SQLite rule storage.

This module provides centralized database management with proper connection handling,
schema initialization, and performance optimizations for transaction rule storage.
"""

from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Centralized database connection and schema management."""
    
    def __init__(self, db_path: Path):
        """Initialize database manager with schema setup.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self) -> None:
        """Initialize database with schema if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self.get_connection() as conn:
            self._create_schema(conn)
            self._create_indexes(conn)
    
    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with proper configuration."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,  # 30 second timeout
            check_same_thread=False
        )
        
        try:
            # Configure SQLite for optimal performance
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            conn.execute("PRAGMA synchronous=NORMAL")  # Balanced safety/performance
            conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
            conn.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
            
            # Row factory for easier data access
            conn.row_factory = sqlite3.Row
            
            yield conn
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Get a connection within an explicit transaction."""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")  # Start transaction immediately
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction failed: {e}", exc_info=True)
                raise
    
    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create database schema if it doesn't exist."""
        # Check if tables already exist
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='rules'
        """)
        
        if cursor.fetchone():
            logger.debug("Database schema already exists")
            return
        
        logger.debug("Creating database schema")
        
        # Core rules table with optimized structure
        conn.execute("""
            CREATE TABLE rules (
                rule_id TEXT PRIMARY KEY,
                importer_id TEXT NOT NULL,
                name TEXT NOT NULL,
                is_enabled BOOLEAN NOT NULL DEFAULT 1,
                stop_processing BOOLEAN NOT NULL DEFAULT 0,
                priority INTEGER NOT NULL DEFAULT 0,
                
                -- Rule definition (JSON for flexibility)
                conditions_json TEXT NOT NULL,
                actions_json TEXT NOT NULL,
                
                -- Metadata
                created_date TEXT NOT NULL,
                updated_date TEXT NOT NULL,
                
                -- Statistics
                application_count INTEGER NOT NULL DEFAULT 0,
                last_applied TEXT,
                
                -- Extensibility
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        
        # Optional: Importers metadata table
        conn.execute("""
            CREATE TABLE importers (
                importer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT,
                region TEXT,
                institution TEXT,
                created_date TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        
        # Optional: Rule application history for analytics
        conn.execute("""
            CREATE TABLE rule_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT NOT NULL,
                importer_id TEXT NOT NULL,
                transaction_hash TEXT,
                applied_date TEXT NOT NULL,
                execution_time_ms INTEGER,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                
                FOREIGN KEY (rule_id) REFERENCES rules(rule_id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        logger.debug("Database schema created successfully")
    
    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Create performance indexes."""
        # Check if indexes already exist
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_rules_importer_enabled'
        """)
        
        if cursor.fetchone():
            logger.debug("Database indexes already exist")
            return
        
        logger.debug("Creating database indexes")
        
        # Performance indexes for rules table
        conn.execute("""
            CREATE INDEX idx_rules_importer_enabled 
            ON rules(importer_id, is_enabled)
        """)
        
        conn.execute("""
            CREATE INDEX idx_rules_priority 
            ON rules(importer_id, priority DESC, application_count DESC)
        """)
        
        conn.execute("""
            CREATE INDEX idx_rules_last_applied 
            ON rules(last_applied DESC)
        """)
        
        conn.execute("""
            CREATE INDEX idx_rules_created 
            ON rules(created_date DESC)
        """)
        
        # Indexes for rule_applications table
        conn.execute("""
            CREATE INDEX idx_applications_rule 
            ON rule_applications(rule_id, applied_date DESC)
        """)
        
        conn.execute("""
            CREATE INDEX idx_applications_date 
            ON rule_applications(applied_date DESC)
        """)
        
        conn.commit()
        logger.debug("Database indexes created successfully")
    
    def vacuum(self) -> None:
        """Optimize database by running VACUUM."""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
        logger.debug("Database vacuum completed")
    
    def get_database_info(self) -> dict:
        """Get database statistics and information."""
        with self.get_connection() as conn:
            # Get table sizes
            rule_count = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
            importer_count = conn.execute("SELECT COUNT(*) FROM importers").fetchone()[0]
            application_count = conn.execute("SELECT COUNT(*) FROM rule_applications").fetchone()[0]
            
            # Get database file size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return {
                "db_path": str(self.db_path),
                "db_size_bytes": db_size,
                "rule_count": rule_count,
                "importer_count": importer_count,
                "application_count": application_count
            }
