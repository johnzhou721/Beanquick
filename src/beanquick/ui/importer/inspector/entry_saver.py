"""
Transaction Saver Component - Handles saving preview content to files.
"""
import logging
from typing import Optional, Callable, Protocol

import toga
from toga.style import Pack
from toga.style.pack import ROW  # type: ignore
from toga.constants import DODGERBLUE

logger = logging.getLogger(__name__)


class SaveableContent(Protocol):
    """Protocol for objects that can provide saveable content."""
    
    def get_save_content(self) -> str:
        """Get the content to be saved.
        
        Returns:
            String content ready for saving to file
        """
        ...


class EntrySaver:
    """Component for saving entry content to selected files.

    Responsibilities:
    - Provide file selection UI
    - Handle save operations
    - Validate content before saving
    - Delegate actual file operations to external handler
    """
    
    def __init__(
        self,
        available_files: list[dict[str, str]],
        default_file: Optional[str] = None,
        on_save: Optional[Callable[[str, str], None]] = None,
        on_file_change: Optional[Callable[[str], None]] = None
    ):
        """Initialize the transaction saver.
        
        Args:
            available_files: List of dicts with 'name' and 'value' keys for file selection
            default_file: Default file path to select
            on_save: Callback for save operations (content, file_path)
            on_file_change: Callback for file selection changes (file_path)
        """
        self._available_files = available_files
        self._default_file = default_file
        self._on_save = on_save
        self._on_file_change = on_file_change
        
        # UI components
        self._file_selector: Optional[toga.Selection] = None
        self._save_button: Optional[toga.Button] = None
        self._container: Optional[toga.Box] = None
        
        # Content source
        self._content_source: Optional[SaveableContent] = None
    
    def create_widget(self) -> toga.Box:
        """Create the saver widget.
        
        Returns:
            toga.Box: Container with file selector and save button
        """
        if self._container is None:
            self._create_components()
        
        return self._container
    
    def set_content_source(self, content_source: SaveableContent) -> None:
        """Set the source for content to be saved.
        
        Args:
            content_source: Object implementing SaveableContent protocol
        """
        self._content_source = content_source
        self._update_save_button_state()
    
    def set_available_files(self, files: list[dict[str, str]]) -> None:
        """Update the available files for selection.
        
        Args:
            files: List of dicts with 'name' and 'value' keys
        """
        self._available_files = files
        if self._file_selector:
            # Clear and repopulate
            self._file_selector.items.clear()
            for file_data in files:
                self._file_selector.items.append(file_data)
    
    def get_selected_file(self) -> Optional[str]:
        """Get the currently selected file path.
        
        Returns:
            Selected file path or None if nothing selected
        """
        if not self._file_selector or not self._file_selector.value:
            return None
        selected_item = self._file_selector.value
        return getattr(selected_item, 'value', None) if selected_item else None
    
    def _create_components(self) -> None:
        """Create the UI components."""
        # File selector
        self._file_selector = toga.Selection(
            items=self._available_files,
            accessor="name",
            style=Pack(flex=1, margin_right=5),
            on_change=self._on_file_selection_change,
        )
        
        # Set default selection
        if self._default_file:
            default_selection = self._file_selector.items.find({"value": self._default_file})
            if default_selection:
                self._file_selector.value = default_selection
        
        # Save button
        self._save_button = toga.Button(
            "Save",
            style=Pack(background_color=DODGERBLUE),
            on_press=self._on_save_pressed,
            enabled=False  # Initially disabled
        )
        
        # Container
        self._container = toga.Box(
            style=Pack(direction=ROW, margin_top=10),
            children=[
                toga.Label("Save to:", style=Pack(margin_right=5)),
                self._file_selector,
                self._save_button
            ]
        )
    
    def _on_file_selection_change(self, widget: toga.Selection, **kwargs) -> None:
        """Handle file selection changes.
        
        Args:
            widget: The selection widget
            **kwargs: Additional arguments
        """
        selected_file = self.get_selected_file()
        if selected_file and self._on_file_change:
            self._on_file_change(selected_file)
        
        self._update_save_button_state()
    
    def _on_save_pressed(self, widget: toga.Button, **kwargs) -> None:
        """Handle save button press.
        
        Args:
            widget: The button widget
            **kwargs: Additional arguments
        """
        if not self._content_source:
            logger.warning("No content source set for saving")
            return
        
        selected_file = self.get_selected_file()
        if not selected_file:
            logger.warning("No file selected for saving")
            return
        
        try:
            content = self._content_source.get_save_content()
            if not content.strip():
                logger.warning("No content to save")
                return
            
            if self._on_save:
                self._on_save(content, selected_file)
            
        except Exception as e:
            logger.error(f"Error getting content for save: {e}", exc_info=True)
    
    def _update_save_button_state(self) -> None:
        """Update the enabled state of the save button."""
        if not self._save_button:
            return
        
        has_content = self._content_source is not None
        has_file = self.get_selected_file() is not None

        print(has_content, has_file)
        
        self._save_button.enabled = has_content and has_file


class PreviewContentAdapter:
    """Adapter to make preview components compatible with SaveableContent protocol."""
    
    def __init__(self, preview_component):
        """Initialize with a preview component.
        
        Args:
            preview_component: Component that has a get_preview_content() method
        """
        self._preview_component = preview_component
    
    def get_save_content(self) -> str:
        """Get content from the preview component.
        
        Returns:
            Content string from the preview component
        """
        if hasattr(self._preview_component, 'get_preview_content'):
            return self._preview_component.get_preview_content()
        elif hasattr(self._preview_component, '_entry_preview') and self._preview_component._entry_preview:
            return self._preview_component._entry_preview.value or ""
        else:
            return ""