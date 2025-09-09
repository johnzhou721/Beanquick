"""
Source Data Display component for showing imported transaction source data.

This module provides the SourceDataDisplay component that displays the
original_row metadata from TransactionDisplayData in a formatted key-value view.
"""

import logging
import sys
from typing import Optional, Dict, Any

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT  # type: ignore

from beanquick.ui.importer.transaction_review.models import TransactionDisplayData
from beanquick.util.syntax_highlighter import BeanquickSyntaxHighlighter

logger = logging.getLogger(__name__)


class SourceDataDisplay:
    """Component for displaying original transaction source data in a formatted view.
    
    This component extracts and displays the original_row metadata from
    TransactionDisplayData, showing the source import data in a readable format.
    """
    
    def __init__(self):
        """Initialize the source data display component."""
        self._container: Optional[toga.Box] = None
        self._content_text: Optional[toga.MultilineTextInput] = None
        self._current_transaction: Optional[TransactionDisplayData] = None
        self._syntax_highlighter: Optional[BeanquickSyntaxHighlighter] = None  # Syntax highlighter
    
    def create_widget(self) -> toga.Box:
        """Create the source data display widget.
        
        Returns:
            toga.Box: Container with title and content areas
        """
        self._container = toga.Box(style=Pack(direction=COLUMN, margin_top=10))
        
        # Title label
        title_label = toga.Label(
            "Original Transaction Data",
            style=Pack(
                font_weight="bold",
                margin_bottom=5,
                text_align=LEFT
            )
        )
        
        # Content text area - readonly multiline text for key-value display
        self._content_text = toga.MultilineTextInput(
            readonly=True,
            style=Pack(
                font_family="monospace",
                height=120,
            ),
            placeholder="No source data available"
        )
        
        assert self._container is not None
        assert self._content_text is not None
        
        # Initialize syntax highlighter for macOS
        if sys.platform == "darwin":
            self._content_text._impl.native_text.setAutomaticQuoteSubstitutionEnabled_(False)
            
            # Initialize syntax highlighter
            try:
                # Default to light theme for now - could be made configurable
                color_scheme = 'github_light'
                self._syntax_highlighter = BeanquickSyntaxHighlighter(
                    self._content_text._impl.native_text,
                    color_scheme=color_scheme
                )
            except Exception as e:
                logger.warning(f"Failed to initialize syntax highlighter: {e}")
                self._syntax_highlighter = None
        
        self._container.add(title_label)
        self._container.add(self._content_text)
        
        return self._container
    
    def update_display(self, transaction_display: Optional[TransactionDisplayData]) -> None:
        """Update the display with transaction data.
        
        Args:
            transaction_display: The TransactionDisplayData to display original row for
        """
        self._current_transaction = transaction_display
        
        if not self._content_text:
            logger.warning("Content text widget not initialized")
            return
        
        if not transaction_display:
            self._content_text.value = ""
            return
        
        # Extract original_row from metadata
        original_row = self._get_original_row_data(transaction_display)
        
        if not original_row:
            self._content_text.value = "No source import data available"
            return
        
        # Format the original row data as key-value pairs
        formatted_content = self._format_original_row_data(original_row)
        self._content_text.value = formatted_content
        
        # Apply syntax highlighting if available
        if self._syntax_highlighter and formatted_content:
            self._syntax_highlighter.apply_highlighting(formatted_content)
    
    def clear_display(self) -> None:
        """Clear the display content."""
        if self._content_text:
            self._content_text.value = ""
        self._current_transaction = None
    
    def set_syntax_color_scheme(self, scheme_name: str):
        """Set the syntax highlighting color scheme.
        
        Args:
            scheme_name: Name of the color scheme to use
        """
        if self._syntax_highlighter:
            self._syntax_highlighter.set_color_scheme(scheme_name)
            self._syntax_highlighter.refresh_highlighting()
    
    def get_available_color_schemes(self) -> list[str]:
        """Get list of available color schemes.
        
        Returns:
            List of available color scheme names
        """
        if self._syntax_highlighter:
            return self._syntax_highlighter.get_available_schemes()
        return []
    
    def cleanup(self) -> None:
        """Clean up syntax highlighter resources."""
        self._syntax_highlighter = None
        self._current_transaction = None
    
    def _get_original_row_data(self, transaction_display: TransactionDisplayData) -> Optional[Dict[str, Any]]:
        """Extract original_row data from transaction metadata.
        
        Args:
            transaction_display: The transaction to extract data from
            
        Returns:
            Dictionary containing original row data or None if not available
        """
        try:
            metadata = transaction_display.transaction_data.metadata
            if not metadata:
                return None
            
            return metadata.get('original_row')
        except Exception as e:
            logger.warning(f"Error extracting original row data: {e}")
            return None
    
    def _format_original_row_data(self, original_row: Dict[str, Any]) -> str:
        """Format original row data as readable key-value pairs.
        
        Args:
            original_row: Dictionary containing the original row data
            
        Returns:
            Formatted string representation of the data
        """
        if not original_row:
            return "No data available"
        
        formatted_lines = []
        
        for key, value in original_row.items():
            # Convert value to string and handle None/empty values
            value_str = str(value) if value is not None else ""
            
            # Skip completely empty values for cleaner display
            if not value_str.strip():
                value_str = "(empty)"
            
            # Format with alignment
            formatted_line = f"{str(key)}: {value_str}"
            formatted_lines.append(formatted_line)
        
        return "\n".join(formatted_lines)
