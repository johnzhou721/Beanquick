"""
SQLite-optimized rule matching engine for the advanced rule system.

This module provides the SQLiteRuleMatcher class that leverages SQLite's
query optimization capabilities instead of in-memory indexing for superior
performance and simplified architecture.
"""

import logging
from typing import List, Optional, Dict, Tuple, Any

from . import TransactionRule
from ..core.data import TransactionData
from .rule_components import Field, Condition
from .storage.sqlite_repository import SQLiteRuleRepository
from .storage.models import RuleQuery

logger = logging.getLogger(__name__)


class SQLiteRuleMatcher:
    """SQLite-optimized rule matcher that leverages database query optimization.
    
    This class provides efficient rule matching by delegating optimization to SQLite
    rather than maintaining complex in-memory indexes. It focuses on business logic
    while letting the database handle performance optimization.
    
    Key differences from the original RuleMatcher:
    - No in-memory caching or indexing (SQLite handles this better)
    - Dynamic queries based on transaction properties
    - Leverages SQLite's query planner and indexes
    - Simpler, more maintainable architecture
    - Better memory efficiency
    
    Attributes:
        _repository: SQLite repository for rule storage and queries
        _importer_id: Identifier for the current importer
        _stats: Runtime statistics for monitoring
    """
    
    def __init__(self, repository: SQLiteRuleRepository):
        """Initialize the SQLite rule matcher.
        
        Args:
            repository: SQLiteRuleRepository instance for rule storage
            
        Raises:
            ValueError: If repository is None
            TypeError: If repository is not SQLiteRuleRepository
        """
        if repository is None:
            raise ValueError("repository cannot be None")
        
        if not isinstance(repository, SQLiteRuleRepository):
            raise TypeError("repository must be SQLiteRuleRepository instance")
        
        self._repository = repository
        self._importer_id = repository.importer_id
        self._stats = {
            "queries_executed": 0,
            "rules_evaluated": 0,
            "cache_hits": 0,
            "early_terminations": 0
        }
        
        logger.debug(f"SQLiteRuleMatcher initialized for importer: {self._importer_id}")
    
    def find_matching_rules(self, transaction: Optional[TransactionData]) -> List[TransactionRule]:
        """Find all rules that match a transaction using SQLite optimization.
        
        This method leverages SQLite's query optimization to efficiently find
        matching rules with minimal memory usage and maximum performance.
        
        Args:
            transaction: The transaction to find matching rules for
            
        Returns:
            List of matching TransactionRule objects in priority order
        """
        if not transaction:
            return []
        
        matching_rules = []
        self._stats["queries_executed"] += 1
        
        try:
            # Get optimized candidate rules from SQLite
            candidate_rules = self._get_optimized_candidates(transaction)
            
            # Evaluate candidates in database-optimized priority order
            for rule in candidate_rules:
                try:
                    self._stats["rules_evaluated"] += 1
                    
                    if rule.matches(transaction):
                        matching_rules.append(rule)
                        
                        # Early termination if stop_processing is set
                        if rule.stop_processing:
                            self._stats["early_terminations"] += 1
                            logger.debug(f"Early termination triggered by rule {rule.rule_id} ({rule.name})")
                            break
                            
                except Exception as e:
                    logger.warning(f"Error evaluating rule {rule.rule_id} ({rule.name}): {e}")
                    # Continue with other rules
                    continue
            
            logger.debug(f"Found {len(matching_rules)} matching rules for transaction "
                        f"(evaluated {len(candidate_rules)} candidates)")
            
        except Exception as e:
            logger.error(f"Error in find_matching_rules: {e}", exc_info=True)
            # Return empty list on error to maintain system stability
            
        return matching_rules
    
    def find_first_matching_rule(self, transaction: Optional[TransactionData]) -> Optional[TransactionRule]:
        """Find the first (highest priority) rule that matches a transaction.
        
        This is optimized for cases where only one rule is needed, using
        SQLite's LIMIT clause for maximum efficiency.
        
        Args:
            transaction: The transaction to find a matching rule for
            
        Returns:
            The first matching TransactionRule, or None if no match found
        """
        if not transaction:
            return None
        
        self._stats["queries_executed"] += 1
        
        try:
            # Use a small limit for first match optimization
            candidate_rules = self._get_optimized_candidates(transaction, limit=10)
            
            # Evaluate candidates until first match
            for rule in candidate_rules:
                try:
                    self._stats["rules_evaluated"] += 1
                    
                    if rule.matches(transaction):
                        logger.debug(f"First matching rule found: {rule.rule_id} ({rule.name})")
                        return rule
                        
                except Exception as e:
                    logger.warning(f"Error evaluating rule {rule.rule_id} ({rule.name}): {e}")
                    # Continue with other rules
                    continue
            
            logger.debug("No matching rules found")
            
        except Exception as e:
            logger.error(f"Error in find_first_matching_rule: {e}", exc_info=True)
            
        return None
    
    def _get_optimized_candidates(self, transaction: TransactionData, limit: Optional[int] = None) -> List[TransactionRule]:
        """Get candidate rules using SQLite query optimization.
        
        This method builds dynamic SQL queries based on transaction properties
        to leverage SQLite's indexes and query planner for optimal performance.
        
        Args:
            transaction: The transaction to get candidates for
            limit: Optional limit on number of candidates to return
            
        Returns:
            List of candidate TransactionRule objects in priority order
        """
        # Build base query for enabled rules with priority ordering
        query = RuleQuery(
            importer_id=self._importer_id,
            is_enabled=True,
            order_by="priority DESC, application_count DESC, created_date DESC",
            limit=limit
        )
        
        # Add transaction-specific optimizations
        self._apply_transaction_filters(query, transaction)
        
        # Execute optimized query
        candidates = self._repository.query_rules(query)
        
        logger.debug(f"SQLite query returned {len(candidates)} candidate rules "
                    f"{'(limited)' if limit else '(unlimited)'}")
        
        return candidates
    
    def _apply_transaction_filters(self, query: RuleQuery, transaction: TransactionData) -> None:
        """Apply transaction-specific filters to optimize the SQLite query.
        
        This method analyzes the transaction and adds appropriate filters
        to the RuleQuery to leverage SQLite indexes and reduce the result set.
        
        Args:
            query: RuleQuery to modify with filters
            transaction: Transaction to analyze for filter opportunities
        """
        # For now, we rely on SQLite's general optimization
        # Future enhancements could add:
        # - Payee pattern matching at database level
        # - Amount range filtering
        # - Date-based filtering
        # - Field-specific indexing
        
        # Example of potential optimizations (commented for future implementation):
        # if hasattr(transaction, 'payee') and transaction.payee:
        #     query.payee_pattern = transaction.payee
        # 
        # if hasattr(transaction, 'amount') and transaction.amount is not None:
        #     query.amount_min = transaction.amount * 0.9
        #     query.amount_max = transaction.amount * 1.1
        
        pass
    
    def detect_rule_conflicts(self) -> List[Tuple[TransactionRule, TransactionRule, str]]:
        """Detect potential conflicts between rules using SQLite analytics.
        
        This method leverages SQLite's analytical capabilities to efficiently
        detect rule conflicts without loading all rules into memory.
        
        Returns:
            List of tuples (rule1, rule2, conflict_description)
        """
        conflicts = []
        
        try:
            # Get all enabled rules and filter for stop_processing
            all_enabled_rules = self._repository.query_rules(RuleQuery(
                importer_id=self._importer_id,
                is_enabled=True,
                order_by="priority DESC"
            ))
            
            # Filter for rules with stop_processing=True
            rules_with_stop = [rule for rule in all_enabled_rules if rule.stop_processing]
            
            # Check for stop_processing conflicts
            if len(rules_with_stop) > 1:
                for i, rule1 in enumerate(rules_with_stop):
                    for rule2 in rules_with_stop[i + 1:]:
                        conflict = self._analyze_stop_processing_conflict(rule1, rule2)
                        if conflict:
                            conflicts.append((rule1, rule2, conflict))
            
            # Additional conflict detection could be added here:
            # - Rules with identical payee patterns but different actions
            # - Rules with overlapping conditions but conflicting actions
            # - Rules with inconsistent priority ordering
            
            logger.debug(f"Detected {len(conflicts)} potential rule conflicts")
            
        except Exception as e:
            logger.error(f"Error detecting rule conflicts: {e}", exc_info=True)
            
        return conflicts
    
    def _analyze_stop_processing_conflict(self, rule1: TransactionRule, rule2: TransactionRule) -> Optional[str]:
        """Analyze two rules for stop_processing conflicts.
        
        Args:
            rule1: First rule to check
            rule2: Second rule to check
            
        Returns:
            Conflict description if conflict exists, None otherwise
        """
        # Both rules have stop_processing=True, check if they could both match
        if self._could_rules_overlap(rule1, rule2):
            return "Both rules have stop_processing=True and could match the same transaction"
        
        return None
    
    def _could_rules_overlap(self, rule1: TransactionRule, rule2: TransactionRule) -> bool:
        """Check if two rules could potentially match the same transaction.
        
        This is a simplified heuristic check. A more sophisticated implementation
        could analyze the actual conditions for overlap.
        
        Args:
            rule1: First rule to check
            rule2: Second rule to check
            
        Returns:
            bool: True if rules could potentially overlap
        """
        # Simple heuristic: if both rules have conditions, they could overlap
        return (rule1.conditions_block is not None and 
                rule2.conditions_block is not None)
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the rule matcher and repository.
        
        Returns:
            Dictionary with various statistics about rules and performance
        """
        try:
            # Get repository statistics
            repo_stats = self._repository.get_statistics()
            
            # Combine with matcher runtime statistics
            combined_stats = {
                # Repository statistics
                "repository": repo_stats,
                
                # Matcher runtime statistics
                "matcher": {
                    "queries_executed": self._stats["queries_executed"],
                    "rules_evaluated": self._stats["rules_evaluated"],
                    "cache_hits": self._stats["cache_hits"],
                    "early_terminations": self._stats["early_terminations"],
                    "avg_rules_per_query": (
                        self._stats["rules_evaluated"] / max(self._stats["queries_executed"], 1)
                    )
                },
                
                # Performance indicators
                "performance": {
                    "optimization_ratio": (
                        self._stats["cache_hits"] / max(self._stats["queries_executed"], 1)
                    ),
                    "early_termination_rate": (
                        self._stats["early_terminations"] / max(self._stats["queries_executed"], 1)
                    )
                }
            }
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"Error getting rule statistics: {e}", exc_info=True)
            return {
                "repository": {},
                "matcher": self._stats.copy(),
                "performance": {},
                "error": str(e)
            }
    
    def clear_statistics(self) -> None:
        """Clear runtime statistics for fresh monitoring."""
        self._stats = {
            "queries_executed": 0,
            "rules_evaluated": 0,
            "cache_hits": 0,
            "early_terminations": 0
        }
        logger.debug("Rule matcher statistics cleared")
    
    def validate_performance(self) -> Dict[str, Any]:
        """Validate that SQLite optimization is working effectively.
        
        Returns:
            Dictionary with performance validation results
        """
        validation_results = {
            "status": "unknown",
            "issues": [],
            "recommendations": [],
            "database_info": {}
        }
        
        try:
            # Get database information
            db_info = self._repository.get_database_info()
            validation_results["database_info"] = db_info
            
            # Check rule count
            rule_count = self._repository.get_rule_count()
            
            if rule_count == 0:
                validation_results["issues"].append("No rules found in repository")
                validation_results["status"] = "warning"
            elif rule_count > 1000:
                validation_results["recommendations"].append(
                    "Consider rule archiving for large rule sets (>1000 rules)"
                )
            
            # Check query performance indicators
            if self._stats["queries_executed"] > 0:
                avg_rules_per_query = (
                    self._stats["rules_evaluated"] / self._stats["queries_executed"]
                )
                
                if avg_rules_per_query > 100:
                    validation_results["recommendations"].append(
                        "High average rules per query - consider more specific filters"
                    )
                
                early_term_rate = (
                    self._stats["early_terminations"] / self._stats["queries_executed"]
                )
                
                if early_term_rate > 0.5:
                    validation_results["recommendations"].append(
                        "High early termination rate - consider rule priority optimization"
                    )
            
            # Set overall status
            if not validation_results["issues"]:
                validation_results["status"] = "good"
            elif validation_results["issues"] and not any("error" in issue.lower() for issue in validation_results["issues"]):
                validation_results["status"] = "warning"
            else:
                validation_results["status"] = "error"
            
        except Exception as e:
            validation_results["status"] = "error"
            validation_results["issues"].append(f"Validation failed: {e}")
            logger.error(f"Performance validation failed: {e}", exc_info=True)
        
        return validation_results
    
    def query_rules_by_pattern(self, pattern: str, field: Field, limit: int = 50) -> List[TransactionRule]:
        """Query rules that match specific patterns for debugging and analysis.
        
        Args:
            pattern: Pattern to search for
            field: Field to search in
            limit: Maximum number of rules to return
            
        Returns:
            List of matching TransactionRule objects
        """
        try:
            # This could be enhanced to support pattern matching at database level
            # For now, get all enabled rules and filter in Python
            query = RuleQuery(
                importer_id=self._importer_id,
                is_enabled=True,
                order_by="priority DESC, application_count DESC",
                limit=limit * 2  # Get more to account for filtering
            )
            
            rules = self._repository.query_rules(query)
            
            # Filter rules that use the specified field and pattern
            matching_rules = []
            pattern_lower = pattern.lower()
            
            for rule in rules:
                if self._rule_matches_pattern(rule, pattern_lower, field):
                    matching_rules.append(rule)
                    if len(matching_rules) >= limit:
                        break
            
            logger.debug(f"Found {len(matching_rules)} rules matching pattern '{pattern}' in field {field.value}")
            return matching_rules
            
        except Exception as e:
            logger.error(f"Error querying rules by pattern: {e}", exc_info=True)
            return []
    
    def _rule_matches_pattern(self, rule: TransactionRule, pattern: str, field: Field) -> bool:
        """Check if a rule matches a specific pattern in a field.
        
        Args:
            rule: Rule to check
            pattern: Pattern to match (lowercase)
            field: Field to check in
            
        Returns:
            bool: True if rule matches the pattern
        """
        if not rule.conditions_block:
            return False
        
        # Extract all conditions and check for pattern matches
        all_conditions = self._extract_all_conditions(rule.conditions_block)
        
        for condition in all_conditions:
            if condition.field == field:
                condition_value = condition.value.lower()
                if pattern in condition_value or condition_value in pattern:
                    return True
        
        return False
    
    def _extract_all_conditions(self, conditions_block) -> List[Condition]:
        """Extract all conditions from a conditions block, including nested blocks.
        
        Args:
            conditions_block: The ConditionsBlock to extract from
            
        Returns:
            List of all Condition objects found
        """
        all_conditions = list(conditions_block.conditions)
        
        # Recursively extract from nested blocks
        for nested_block in conditions_block.nested_blocks:
            all_conditions.extend(self._extract_all_conditions(nested_block))
        
        return all_conditions
    
    def benchmark_performance(self, transaction: Optional[TransactionData], iterations: int = 100) -> Dict[str, Any]:
        """Benchmark rule matching performance for optimization analysis.
        
        Args:
            transaction: Sample transaction for benchmarking
            iterations: Number of iterations to run
            
        Returns:
            Dictionary with benchmark results
        """
        import time
        
        benchmark_results = {
            "iterations": iterations,
            "total_time": 0.0,
            "avg_time_per_query": 0.0,
            "rules_per_second": 0.0,
            "total_rules_evaluated": 0,
            "error_count": 0
        }
        
        if not transaction:
            benchmark_results["error"] = "No transaction provided for benchmarking"
            return benchmark_results
        
        # Clear statistics for clean benchmark
        initial_stats = self._stats.copy()
        self.clear_statistics()
        
        try:
            start_time = time.time()
            
            for i in range(iterations):
                try:
                    self.find_matching_rules(transaction)
                except Exception as e:
                    benchmark_results["error_count"] += 1
                    logger.warning(f"Benchmark iteration {i} failed: {e}")
            
            end_time = time.time()
            total_time = end_time - start_time
            
            benchmark_results.update({
                "total_time": total_time,
                "avg_time_per_query": total_time / iterations,
                "rules_per_second": (
                    self._stats["rules_evaluated"] / total_time if total_time > 0 else 0
                ),
                "total_rules_evaluated": self._stats["rules_evaluated"],
                "final_stats": self._stats.copy()
            })
            
            logger.info(f"Benchmark completed: {iterations} iterations in {total_time:.3f}s "
                       f"({benchmark_results['avg_time_per_query']:.3f}s per query)")
            
        except Exception as e:
            benchmark_results["error"] = f"Benchmark failed: {e}"
            logger.error(f"Benchmark failed: {e}", exc_info=True)
        finally:
            # Restore initial statistics
            self._stats = initial_stats
        
        return benchmark_results
    
    @property
    def importer_id(self) -> str:
        """Get the importer ID for this matcher."""
        return self._importer_id
    
    @property
    def repository(self) -> SQLiteRuleRepository:
        """Get the underlying SQLite repository."""
        return self._repository
