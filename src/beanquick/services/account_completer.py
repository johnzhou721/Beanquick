"""
Account autocompletion helper with fuzzy matching and frequency ranking.
"""
import logging
from rapidfuzz import process, fuzz, utils

logger = logging.getLogger(__name__)


class AccountCompleter:
    """Handles fuzzy matching and ranking for account autocompletion."""
    
    def __init__(self, accounts: list[str], min_score: float = 30.0, max_suggestions: int = 5):
        """
        Initialize the account completer.
        
        Args:
            accounts: List of account names, pre-sorted by frequency (most used first)
            min_score: Minimum fuzzy match score to include in suggestions
            max_suggestions: Maximum number of suggestions to return
        """
        self.accounts = accounts
        self.min_score = min_score
        self.max_suggestions = max_suggestions
        
        # Create frequency rank mapping (lower index = higher frequency)
        self.frequency_ranks = {account: idx for idx, account in enumerate(accounts)}
    
    def get_suggestions(self, query: str) -> list[str]:
        """
        Get ranked suggestions for the given query.
        
        Args:
            query: The search query string
            
        Returns:
            List of account names ranked by composite score
        """
        if not query or not query.strip():
            return []
        
        query = query.strip()
        
        # Get fuzzy matches with scores
        fuzzy_matches = process.extract(
            query,
            self.accounts,
            scorer=fuzz.WRatio,
            processor=utils.default_process,
            limit=min(len(self.accounts), self.max_suggestions * 2)  # Get more to filter
        )
        
        # Filter by minimum score and calculate composite scores
        suggestions = []
        for account, fuzzy_score, _ in fuzzy_matches:
            if fuzzy_score >= self.min_score:
                composite_score = self._calculate_composite_score(account, fuzzy_score)
                suggestions.append((account, composite_score))
        
        # Sort by composite score (descending) and return account names
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return [account for account, _ in suggestions[:self.max_suggestions]]
    
    def _calculate_composite_score(self, account: str, fuzzy_score: float) -> float:
        """
        Calculate a composite score combining fuzzy match and frequency rank.
        
        Args:
            account: The account name
            fuzzy_score: The fuzzy match score (0-100)
            
        Returns:
            Composite score for ranking
        """
        # Get frequency rank (0 = most frequent)
        frequency_rank = self.frequency_ranks.get(account, len(self.accounts))
        
        # Convert frequency rank to a score (0-100, where 100 = most frequent)
        if len(self.accounts) > 0:
            frequency_score = 100 * (1 - frequency_rank / len(self.accounts))
        else:
            frequency_score = 0
        
        # Weighted combination: 70% fuzzy match, 30% frequency
        # This prioritizes good matches while giving boost to frequently used accounts
        composite_score = (0.7 * fuzzy_score) + (0.3 * frequency_score)
        
        return composite_score
