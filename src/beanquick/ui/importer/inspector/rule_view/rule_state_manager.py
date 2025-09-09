"""
Rule State Manager - Centralized state machine for rule management.

This module provides a state machine that manages all rule-related states and transitions,
eliminating race conditions and providing a single source of truth for rule state.
"""
import logging
from enum import Enum
from typing import Optional, List, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RuleState(Enum):
    """All possible states for rule management."""
    NO_RULE = "no_rule"                    # No rule applied, switch visible but off
    SWITCH_ENABLED = "switch_enabled"      # Switch on, container visible in create mode
    VIEWING_RULES = "viewing_rules"        # One or more rules applied, container shows all rules
    EDITING_RULE = "editing_rule"          # Editing an existing rule
    DELETING_RULE = "deleting_rule"        # Transitional state during rule deletion


@dataclass
class RuleStateTransition:
    """Represents a state transition with context."""
    from_state: RuleState
    to_state: RuleState
    trigger: str
    context: Optional[Any] = None


class RuleStateManager:
    """State machine for managing rule-related states.
    
    This class provides:
    - Single source of truth for rule state
    - Explicit state transitions with validation
    - Observer pattern for state changes
    - Debugging and logging support
    """
    
    def __init__(self):
        """Initialize the state manager."""
        self._current_state = RuleState.NO_RULE
        self._observers: List[Callable[[RuleStateTransition], None]] = []
        self._transition_history: List[RuleStateTransition] = []
        
        logger.debug(f"RuleStateManager initialized with state: {self._current_state}")
    
    @property
    def current_state(self) -> RuleState:
        """Get the current state."""
        return self._current_state
    
    @property
    def should_show_switch(self) -> bool:
        """Determine if the rule switch should be visible."""
        return self._current_state in [RuleState.NO_RULE, RuleState.SWITCH_ENABLED]
    
    @property
    def should_show_container(self) -> bool:
        """Determine if the rule container should be visible."""
        return self._current_state in [RuleState.SWITCH_ENABLED, RuleState.VIEWING_RULES]
    
    @property
    def container_is_view_mode(self) -> bool:
        """Determine if the container should be in view mode (read-only)."""
        return self._current_state == RuleState.VIEWING_RULES
    
    def add_observer(self, observer: Callable[[RuleStateTransition], None]) -> None:
        """Add an observer for state transitions.
        
        Args:
            observer: Function called when state transitions occur
        """
        self._observers.append(observer)
    
    def remove_observer(self, observer: Callable[[RuleStateTransition], None]) -> None:
        """Remove an observer.
        
        Args:
            observer: Function to remove from observers
        """
        if observer in self._observers:
            self._observers.remove(observer)
    
    def transition_to(self, new_state: RuleState, trigger: str, context: Any = None) -> bool:
        """Transition to a new state.
        
        Args:
            new_state: The state to transition to
            trigger: Description of what triggered the transition
            context: Optional context data for the transition
            
        Returns:
            bool: True if transition was successful, False if invalid
        """
        if not self._is_valid_transition(self._current_state, new_state):
            logger.warning(f"Invalid transition from {self._current_state} to {new_state} (trigger: {trigger})")
            return False
        
        if self._current_state == new_state:
            logger.debug(f"No-op transition to same state {new_state} (trigger: {trigger})")
            return True
        
        # Create transition record
        transition = RuleStateTransition(
            from_state=self._current_state,
            to_state=new_state,
            trigger=trigger,
            context=context
        )
        
        # Update state
        old_state = self._current_state
        self._current_state = new_state
        
        # Record transition
        self._transition_history.append(transition)
        
        # Notify observers
        self._notify_observers(transition)
        
        logger.info(f"State transition: {old_state} → {new_state} (trigger: {trigger})")
        return True
    
    def _is_valid_transition(self, from_state: RuleState, to_state: RuleState) -> bool:
        """Validate if a state transition is allowed.
        
        Args:
            from_state: Current state
            to_state: Proposed new state
            
        Returns:
            bool: True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            RuleState.NO_RULE: [
                RuleState.SWITCH_ENABLED,
                RuleState.VIEWING_RULES,
                RuleState.NO_RULE  # Allow no-op
            ],
            RuleState.SWITCH_ENABLED: [
                RuleState.NO_RULE,
                RuleState.VIEWING_RULES,
                RuleState.SWITCH_ENABLED  # Allow no-op
            ],
            RuleState.VIEWING_RULES: [
                RuleState.EDITING_RULE,
                RuleState.DELETING_RULE,
                RuleState.NO_RULE,
                RuleState.VIEWING_RULES  # Allow no-op
            ],
            RuleState.EDITING_RULE: [
                RuleState.VIEWING_RULES,  # Save or cancel returns to viewing
                RuleState.NO_RULE,       # Cancel might go to no rule if transaction cleared
                RuleState.EDITING_RULE   # Allow no-op
            ],
            RuleState.DELETING_RULE: [
                RuleState.NO_RULE,
                RuleState.SWITCH_ENABLED,
                RuleState.VIEWING_RULES  # Allow returning to viewing if rules remain
            ]
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def _notify_observers(self, transition: RuleStateTransition) -> None:
        """Notify all observers of a state transition.
        
        Args:
            transition: The transition that occurred
        """
        for observer in self._observers:
            try:
                observer(transition)
            except Exception as e:
                logger.error(f"Error in state transition observer: {e}")
    
    def get_transition_history(self) -> List[RuleStateTransition]:
        """Get the history of state transitions for debugging.
        
        Returns:
            List[RuleStateTransition]: All transitions that have occurred
        """
        return self._transition_history.copy()
    
    def reset(self) -> None:
        """Reset the state manager to initial state."""
        self.transition_to(RuleState.NO_RULE, "reset")
        self._transition_history.clear()
        logger.debug("RuleStateManager reset to initial state")
