"""
Suggestion popup widget for autocompletion.
"""
import toga
from toga.style import Pack
from toga.style.pack import COLUMN  # type: ignore
from toga.constants import DODGERBLUE
from typing import List, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class SuggestionPopup:
    """A popup widget that displays autocompletion suggestions."""
    
    def __init__(self, parent_container: toga.Box, on_selection: Callable[[str], None]):
        """
        Initialize the suggestion popup.
        
        Args:
            parent_container: The container to add the popup to
            on_selection: Callback when a suggestion is selected
        """
        self.parent_container = parent_container
        self.on_selection = on_selection
        self.suggestions: List[str] = []
        self.selected_index = 0
        self.is_visible = False
        
        # Create the popup container
        self.popup_box = toga.Box(
            style=Pack(
                direction=COLUMN,
            )
        )
        
        # List of suggestion buttons
        self.suggestion_buttons: List[toga.Button] = []
    
    def show_suggestions(self, suggestions: List[str]):
        """
        Show the suggestions popup.
        
        Args:
            suggestions: List of suggestion strings to display
        """
        self.suggestions = suggestions
        self.selected_index = 0
        
        if not suggestions:
            self.hide()
            return
        
        # Clear existing buttons
        for button in self.suggestion_buttons:
            try:
                self.popup_box.remove(button)
            except ValueError:
                pass  # Button already removed
        self.suggestion_buttons.clear()
        
        # Create new suggestion buttons
        for i, suggestion in enumerate(suggestions):
            button = toga.Button(
                suggestion,
                style=Pack(
                    margin_top=2,
                ),
                on_press=lambda widget, text=suggestion: self._on_suggestion_click(text)
            )
            if i == 0:
                button.style.background_color = DODGERBLUE

            self.suggestion_buttons.append(button)
            self.popup_box.add(button)
        
        # Add to parent if not already visible
        if not self.is_visible:
            try:
                self.parent_container.add(self.popup_box)
                self.is_visible = True
            except Exception as e:
                logger.debug(f"Could not add suggestion popup: {e}")
    
    def hide(self):
        """Hide the suggestions popup."""
        if self.is_visible:
            try:
                self.parent_container.remove(self.popup_box)
                self.is_visible = False
                self.suggestions.clear()
            except ValueError:
                pass  # Already removed
    
    def navigate_up(self) -> bool:
        """
        Navigate up in the suggestions list.
        
        Returns:
            True if navigation occurred, False if at top
        """
        if not self.suggestions or self.selected_index <= 0:
            return False
        
        self._update_selection(self.selected_index - 1)
        return True
    
    def navigate_down(self) -> bool:
        """
        Navigate down in the suggestions list.
        
        Returns:
            True if navigation occurred, False if at bottom
        """
        if not self.suggestions or self.selected_index >= len(self.suggestions) - 1:
            return False
        
        self._update_selection(self.selected_index + 1)
        return True
    
    def select_current(self) -> Optional[str]:
        """
        Select the currently highlighted suggestion.
        
        Returns:
            The selected suggestion text, or None if no suggestions
        """
        if not self.suggestions or self.selected_index >= len(self.suggestions):
            return None
        
        selected = self.suggestions[self.selected_index]
        self.on_selection(selected)
        self.hide()
        return selected
    
    def _update_selection(self, new_index: int):
        """Update the visual selection."""
        old_index = self.selected_index
        self.selected_index = new_index
        
        # Update button styles
        if 0 <= old_index < len(self.suggestion_buttons):
            del self.suggestion_buttons[old_index].style.background_color

        if 0 <= new_index < len(self.suggestion_buttons):
            self.suggestion_buttons[new_index].style.background_color = DODGERBLUE

    def _on_suggestion_click(self, suggestion: str):
        """Handle suggestion button click."""
        self.on_selection(suggestion)
        self.hide()