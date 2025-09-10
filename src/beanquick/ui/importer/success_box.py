"""
Success View Component - Displays import completion summary and next actions.

This module provides the SuccessView component that shows a summary of the completed
import process, including statistics about transactions processed, rules created,
and files saved. It provides clear next action options for the user.
"""

import logging
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import sys

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, LEFT, RIGHT, BOLD  # type: ignore
from toga.colors import GREEN, DIMGRAY, DODGERBLUE, LIGHTGRAY, WHITE

if sys.platform == 'darwin':
    from toga_cocoa.libs import NSColor

logger = logging.getLogger(__name__)

# Constants for consistent styling with ImporterWindow
LARGE_MARGIN = 20
DEFAULT_MARGIN = 10
SMALL_MARGIN = 5
TITLE_FONT_SIZE = 32
SUBTITLE_FONT_SIZE = 16
DESCRIPTION_FONT_SIZE = 10
STAT_TITLE_FONT_SIZE = 12
STAT_VALUE_FONT_SIZE = 16
BUTTON_HEIGHT = 40  # Slightly taller for better touch targets
BUTTON_WIDTH = 280
ICON_SIZE = 80  # Larger for better visual impact
CARD_MARGIN = 12

# Enhanced color palette
SUCCESS_GREEN = "#28a745"
TEXT_MUTED = "#6c757d"
ACCENT_BLUE = DODGERBLUE


class SuccessView:
    """Success view component for displaying import completion summary.
    
    This component provides a structured view of import completion statistics,
    file locations, and next action options. It maintains consistency with
    the existing UI patterns while providing clear completion feedback.
    """
    
    def __init__(self,
                 success_data: Dict[str, Any],
                 on_import_another: Optional[Callable[[], None]] = None,
                 on_view_files: Optional[Callable[[str], None]] = None,
                 on_close: Optional[Callable[[], None]] = None):
        """Initialize the success view component.
        
        Args:
            success_data: Dictionary containing success statistics and file information
            on_import_another: Callback when user wants to import another file
            on_view_files: Callback when user wants to view saved files  
            on_close: Callback when user wants to close the window
        """
        self._success_data = success_data.copy()
        self._on_import_another = on_import_another
        self._on_view_files = on_view_files
        self._on_close = on_close
        
        # UI Components
        self._main_container: Optional[toga.Box] = None
        self._statistics_section: Optional[toga.Box] = None
        self._actions_section: Optional[toga.Box] = None
        
        logger.debug(f"SuccessView initialized with data: {success_data}")
    
    def create_widget(self) -> toga.Box:
        """Create the main success view widget with populated data.
        
        Returns:
            toga.Box: The main success view container
        """
        if self._main_container is None:
            self._create_main_container()

        return self._main_container
    
    def update_success_data(self, success_data: Dict[str, Any]):
        """Update the success view with new completion data.
        
        Note: This method updates the internal data. If you need to refresh the UI,
        you'll need to recreate the widget as values are set during creation.
        
        Args:
            success_data: Dictionary containing success statistics and file information
                Expected keys:
                - transaction_count: Total number of transactions processed
                - categorized_count: Number of transactions categorized
                - rules_created: Number of new rules created
                - rules_applied: Number of rules applied during processing
                - source_file_name: Name of the original import file
                - saved_file_path: Path where entries were saved
        """
        logger.debug(f"Updating success view with new data: {success_data}")
        
        self._success_data = success_data.copy()
        
        # Note: UI components need to be recreated to reflect the new data
        # since values are populated during widget creation
        if self._main_container is not None:
            logger.info("Success data updated. Widget recreation required to reflect changes.")
    
    def _create_main_container(self):
        """Create the main container with enhanced layout and spacing."""
        # Create all sections
        self._create_header_section()
        self._create_statistics_section()
        self._create_actions_section()
        
        # Create a centered content container with maximum width
        content_container = toga.Box(
            children=[
                self._header_section,
                self._statistics_section,
                self._actions_section,
            ],
            style=Pack(
                direction=COLUMN,
                align_items=CENTER,
                width=600,  # Maximum content width for better readability
                margin=DEFAULT_MARGIN
            )
        )
        
        # Assemble main container with proper centering and spacing
        self._main_container = toga.Box(
            children=[
                toga.Box(style=Pack(flex=1)),  # Top spacer
                content_container,
                toga.Box(style=Pack(flex=1)),  # Bottom spacer
            ],
            style=Pack(
                direction=COLUMN,
                align_items=CENTER,
                margin=LARGE_MARGIN
            )
        )
    
    def _create_header_section(self):
        """Create an enhanced header section with better visual design."""
        # Success icon with better styling
        success_icon = toga.ImageView(
            image=toga.Image('resources/images/NotoPartyPopper.svg'),
            style=Pack(
                width=ICON_SIZE, 
                height=ICON_SIZE, 
                margin_bottom=DEFAULT_MARGIN
            )
        )
        
        # Main title with enhanced styling
        title_label = toga.Label(
            "Import Complete",
            style=Pack(
                font_size=TITLE_FONT_SIZE,
                font_weight=BOLD,
                color=SUCCESS_GREEN,
                margin_bottom=SMALL_MARGIN,
                text_align=CENTER
            )
        )
        
        # Subtitle with better hierarchy
        subtitle_label = toga.Label(
            "Your statement has been successfully converted!",
            style=Pack(
                font_size=SUBTITLE_FONT_SIZE,
                color=DIMGRAY,
                margin_bottom=LARGE_MARGIN,
                text_align=CENTER,
                width=500
            )
        )
        
        self._header_section = toga.Box(
            children=[success_icon, title_label, subtitle_label],
            style=Pack(
                direction=COLUMN,
                align_items=CENTER,
                margin_bottom=CARD_MARGIN
            )
        )
    
    def _create_statistics_section(self):
        """Create an enhanced statistics summary section with card design."""        
        # Create statistics in a grid-like layout with actual values
        # Row 1: Transaction stats
        transaction_count = self._success_data.get('transaction_count', 0)
        categorized_count = self._success_data.get('categorized_count', 0)
        self._transaction_stat = self._create_stat_card("Processed", str(transaction_count), 'NotoReceipt.svg')
        self._categorized_stat = self._create_stat_card("Categorized", str(categorized_count), 'NotoCardFileBox.svg')

        # Row 2: Rule stats
        # rules_created = self._success_data.get('rules_created', 0)
        # rules_applied = self._success_data.get('rules_applied', 0)
        # self._rules_created_stat = self._create_stat_card("Rules Created", str(rules_created), 'NotoNewButton.svg')
        # self._rules_applied_stat = self._create_stat_card("Rules Applied", str(rules_applied), 'NotoMagicWand.svg')
        
        # Row 3 & Row 4: Create file info rows
        source_file = self._success_data.get('source_file_name', 'No file selected')
        saved_file = self._success_data.get('saved_file_path', 'Not saved yet')
        
        # Truncate paths for display
        display_source = self._truncate_path(source_file, max_length=40) if source_file != 'No file selected' else source_file
        display_saved = self._truncate_path(saved_file, max_length=40) if saved_file != 'Not saved yet' else saved_file
        
        self._source_file_info = self._create_file_row("Source File", display_source)
        self._saved_file_info = self._create_file_row("Saved To", display_saved)

        # Arrange stats in a 2x2 grid
        stats_row1 = toga.Box(
            children=[self._transaction_stat, self._categorized_stat],
            style=Pack(
                direction=ROW,
            )
        )
        
        # stats_row2 = toga.Box(
        #     children=[self._rules_created_stat, self._rules_applied_stat],
        #     style=Pack(
        #         direction=ROW,
        #     )
        # )
        
        # Container for all statistics
        stats_container = toga.Box(
            children=[stats_row1, self._source_file_info, self._saved_file_info],
            style=Pack(
                direction=COLUMN,
                align_items=CENTER
            )
        )
        
        # Card-style container
        self._statistics_section = toga.Box(
            children=[
                stats_container,
            ],
            style=Pack(
                direction=COLUMN,
                align_items=CENTER,
                margin_bottom=LARGE_MARGIN,
                width=500
            )
        )
    
    def _create_actions_section(self):
        """Create an enhanced action buttons section."""
        # Primary action - Import Another File
        import_another_button = toga.Button(
            "Import Another File",
            on_press=self._handle_import_another,
            style=Pack(
                width=430,  # Same width as the statistics section
                height=28,
                font_weight=BOLD,
                margin_bottom=DEFAULT_MARGIN,
                background_color=DODGERBLUE
            )
        )
        
        # Secondary actions with half width, arranged in a row
        view_files_button = toga.Button(
            "View Saved Files",
            on_press=self._handle_view_files,
            style=Pack(
                width=211,  # Half width of import_another_button
                height=28,
                margin_right=DEFAULT_MARGIN // 2,
            )
        )
        
        close_button = toga.Button(
            "Close",
            on_press=self._handle_close,
            style=Pack(
                width=211,  # Half width of import_another_button
                height=28,
                margin_left=DEFAULT_MARGIN // 2,
            )
        )
        
        # Container for secondary buttons in a row
        secondary_buttons_row = toga.Box(
            children=[view_files_button, close_button],
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin_bottom=DEFAULT_MARGIN
            )
        )
        
        self._actions_section = toga.Box(
            children=[
                import_another_button,
                secondary_buttons_row,
            ],
            style=Pack(
                direction=COLUMN,
                align_items=CENTER,
                margin_top=LARGE_MARGIN
            )
        )
    
    def _create_stat_card(self, label: str, value: str, icon: str) -> toga.Box:
        """Create a statistics card with label and value.

        Args:
            label: The statistic label
            value: The statistic value
            icon: The icon image path

        Returns:
            toga.Box: Container with the enhanced statistic card
        """
        icon = toga.ImageView(
            image=toga.Image(f'resources/images/{icon}'),
            style=Pack(
                width=28, 
                height=28, 
                margin=DEFAULT_MARGIN,
                margin_right=0
            )
        )

        # Label (descriptive text)
        label_widget = toga.Label(
            label,
            style=Pack(
                font_size=STAT_TITLE_FONT_SIZE,
                color=TEXT_MUTED,
                font_weight=BOLD,
                margin=DEFAULT_MARGIN
            )
        )

         # Value (large and prominent)
        value_widget = toga.Label(
            value,
            style=Pack(
                font_size=STAT_VALUE_FONT_SIZE,
                font_weight=BOLD,
                color=SUCCESS_GREEN,
                margin=(0, DEFAULT_MARGIN, DEFAULT_MARGIN),
            )
        )

        label_value_box = toga.Box(
            children=[label_widget, value_widget],
            style=Pack(direction=COLUMN)
        )

        stat_card = toga.Box(
            children=[icon, label_value_box],
            style=Pack(
                direction=ROW,
                align_items=CENTER,
                margin=SMALL_MARGIN,
                width=210,
            )
        )
        if sys.platform == "darwin":
            # Set background color for macOS
            stat_card._impl.native.backgroundColor = NSColor.controlBackgroundColor
        
        return stat_card
    
    def _create_file_row(self, label: str, path: str) -> toga.Box:
        """Create a file information row with icon.
        
        Args:
            label: The file label
            path: The file path
            
        Returns:
            toga.Box: Container with the file info row
        """
        
        # Label
        label_widget = toga.Label(
            label,
            style=Pack(
                font_size=STAT_TITLE_FONT_SIZE,
                font_weight=BOLD,
                width=80,
                text_align=LEFT,
                color=DIMGRAY,
                margin=DEFAULT_MARGIN,
                margin_right=0,
            )
        )
        
        # Path with truncation
        path_widget = toga.Label(
            path,
            style=Pack(
                font_size=DESCRIPTION_FONT_SIZE,
                width=330,
                text_align=LEFT,
                color=TEXT_MUTED,
                margin=DEFAULT_MARGIN,
                margin_left=0,
            )
        )



        file_row = toga.Box(
            children=[label_widget, path_widget],
            style=Pack(
                direction=ROW,
                margin=SMALL_MARGIN,
            )
        )

        if sys.platform == "darwin":
            # Set background color for macOS
            file_row._impl.native.backgroundColor = NSColor.controlBackgroundColor

        return file_row

    def _truncate_path(self, path: str, max_length: int = 60) -> str:
        """Truncate a file path for display if it's too long.
        
        Args:
            path: The file path to truncate
            max_length: Maximum length for display
            
        Returns:
            str: Truncated path with ellipsis if needed
        """
        if len(path) <= max_length:
            return path
        
        # Try to show the filename and some parent directories
        path_obj = Path(path)
        filename = path_obj.name
        
        if len(filename) >= max_length - 3:
            return f"...{filename[-(max_length-3):]}"
        
        # Show ...parent/filename format
        remaining_length = max_length - len(filename) - 4  # 4 for ".../"
        parent_str = str(path_obj.parent)
        
        if len(parent_str) <= remaining_length:
            return f".../{parent_str}/{filename}"
        else:
            return f"...{parent_str[-(remaining_length):]}/{filename}"
    
    def _handle_import_another(self, widget):
        """Handle Import Another File button press.
        
        Args:
            widget: The button widget that was pressed
        """
        logger.debug("Import Another File button pressed")
        if self._on_import_another:
            try:
                self._on_import_another()
            except Exception as e:
                logger.error(f"Error in import another callback: {e}", exc_info=True)
    
    def _handle_view_files(self, widget):
        """Handle View Saved Files button press.
        
        Args:
            widget: The button widget that was pressed
        """
        logger.debug("View Saved Files button pressed")
        if self._on_view_files:
            try:
                saved_file_path = self._success_data.get('saved_file_path', '')
                self._on_view_files(saved_file_path)
            except Exception as e:
                logger.error(f"Error in view files callback: {e}", exc_info=True)
    
    def _handle_close(self, widget):
        """Handle Close button press.

        Args:
            widget: The button widget that was pressed
        """
        logger.debug("Close button pressed")
        if self._on_close:
            try:
                self._on_close()
            except Exception as e:
                logger.error(f"Error in close callback: {e}", exc_info=True)

    @property
    def success_data(self) -> Dict[str, Any]:
        """Get the current success data.
        
        Returns:
            Dict[str, Any]: Copy of the current success data
        """
        return self._success_data.copy()
    
    def clear_data(self):
        """Clear all success data and reset display."""
        logger.debug("Clearing success view data")
        self._success_data.clear()
        
        # Note: Widget needs to be recreated to reflect cleared data
        # since values are populated during widget creation
        if self._main_container is not None:
            logger.info("Success data cleared. Widget recreation required to reflect changes.")