from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import logging
import sys
from typing import Any, TYPE_CHECKING
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from beancount.parser import parser

import toga
from toga.style import Pack
from toga.style.pack import CENTER, ROW, COLUMN, MONOSPACE  # type: ignore
from toga.constants import Direction, DODGERBLUE

from beanquick.services.account_completer import AccountCompleter
from beanquick.serialisation import deserialise
from beanquick.beans.str import to_string
from beanquick.helpers import BeanquickError
from beanquick.ui.syntax_highlighter import BeanquickSyntaxHighlighter

if TYPE_CHECKING:
    from beanquick.app import Beanquick

logger = logging.getLogger(__name__)

WIDGET_SPACING = 5

class EntryMode(Enum):
    NORMAL = "normal"
    QUICK = "quick"

class BaseEntryBox(toga.Box, ABC):
    def __init__(self, app_instance: Beanquick, **kwargs: Any):
        """Base class for all directive entry boxes."""
        super().__init__(style=Pack(direction=COLUMN, align_items=CENTER, margin=10), **kwargs)

        self.app = app_instance

        # Common state
        self._entry_widgets: dict[str, toga.Widget] = {}
        self._entry_preview: toga.MultilineTextInput = None
        self._syntax_highlighter = None
        self._clearing_form: bool = False
        self._current_mode = EntryMode.NORMAL
        self.main_box = toga.Box(style=Pack(direction=COLUMN, align_items=CENTER, flex=1))

        # Initialize account completion
        self._setup_account_completion()
        
        self._create_ui()

    def _setup_account_completion(self):
        """Set up account autocompletion."""
        try:
            # Get sorted accounts from the ledger
            accounts = list(self.app.active_ledger_data.accounts) if self.app.active_ledger_data else []
            self.account_completer = AccountCompleter(accounts)
            self._completion_timers = {}
            logger.debug(f"Initialized account completion with {len(accounts)} accounts")
        except Exception as e:
            logger.error(f"Error setting up account completion: {e}", exc_info=True)
            self.account_completer = None
            self._completion_timers = {}
    
    def _create_ui(self, mode: EntryMode | None = None):
        """Create the main UI components."""
        if mode is None:
            mode = self._current_mode

        entry_header = self._create_entry_header(mode)
        entry_form = self._create_entry_form(mode)
        entry_preview = self._create_entry_preview()

        self._entry_widgets["entry_header"] = entry_header
        self._entry_widgets["entry_form"] = entry_form
        self._entry_widgets["entry_preview"] = entry_preview

        split_container = toga.SplitContainer(
            content=[(entry_form, 1), (entry_preview, 1)],
            direction=Direction.HORIZONTAL,
            style=Pack(flex=1),
        )
        
        action_box = self._create_action_buttons()

        self.main_box.add(entry_header)
        self.main_box.add(split_container)
        self.main_box.add(action_box)

        self.add(self.main_box)

        self._update_preview()
    
    @abstractmethod
    def _create_entry_header(self, mode: EntryMode | None = None):
        """Create the header for the entry window."""
        pass

    @abstractmethod
    def _create_entry_form(self, mode: EntryMode | None = None):
        """Create the form content specific to the directive type."""
        pass

    @abstractmethod
    def _build_entry_dict(self) -> dict[str, Any]:
        """Build a dictionary from form data for serialization."""
        pass

    @abstractmethod
    def _build_quick_entry_output(self) -> str:
        """Build the Beancount output for quick entry mode."""
        pass

    @abstractmethod
    def _clear_form(self):
        """Clear all form data."""
        pass

    @abstractmethod
    def _is_form_empty(self) -> bool:
        """Check if the form is essentially empty."""
        pass

    @abstractmethod
    def _is_form_valid(self) -> bool:
        """Check if the form is valid."""
        pass

    @abstractmethod
    def _get_form_errors(self) -> list[str]:
        """Get validation errors from the form."""
        pass

    @abstractmethod
    def _load_entry_form(self, mode: EntryMode):
        """Load the entry form based on the current mode."""
        pass

    @abstractmethod
    def _get_beanquick_preview_content(self) -> str:
        """Get the preview content for Beanquick input.
        
        This must be implemented by subclasses that support Beanquick.
        
        Returns:
            String content for the preview pane.
        """
        pass
    
    def _create_entry_preview(self):
        """Create the entry preview pane."""        
        self._entry_preview = toga.MultilineTextInput(
            style=Pack(flex=1, font_family=MONOSPACE),
            placeholder="A real-time preview will display as you enter data."
        )

        if sys.platform == "darwin":
            self._entry_preview._impl.native_text.setAutomaticQuoteSubstitutionEnabled_(False)
            
            # Initialize syntax highlighter
            try:
                # Get user preference for color scheme (default to light_classic)
                color_scheme = getattr(self.app.config, 'syntax_color_scheme', 'github_light')
                self._syntax_highlighter = BeanquickSyntaxHighlighter(
                    self._entry_preview._impl.native_text,
                    color_scheme=color_scheme
                )
            except Exception as e:
                logger.warning(f"Failed to initialize syntax highlighter: {e}")
                self._syntax_highlighter = None

        view_box = toga.Box(
            style=Pack(flex=1, direction=COLUMN),
            children=[self._entry_preview]
        )
        return view_box

    def _create_action_buttons(self):
        """Create the action buttons for the window."""
        save_button = toga.Button(
            "Save",
            style=Pack(background_color=DODGERBLUE),
            on_press=self._on_save
        )
        
        clear_button = toga.Button(
            "Clear",
            style=Pack(margin_right=WIDGET_SPACING),
            on_press=self._on_clear
        )

        file_paths = self.app.active_ledger.options["include"] if self.app.active_ledger else []
        beancount_file_path = self.app.active_ledger.beancount_file_path if self.app.active_ledger else ""
        selection_items = self._transform_file_paths_for_selection(list(file_paths), beancount_file_path)
        save_to_file_selector = toga.Selection(
            items=selection_items,
            accessor="name",
            style=Pack(flex=1, margin_right=WIDGET_SPACING),
            on_change=self._on_save_to_file_change,
        )

        # Set default file value
        default_file = self.app.active_ledger.beanquick_options.default_file if self.app.active_ledger else None
        default_value = default_file or beancount_file_path
        default_selection = save_to_file_selector.items.find({"value": default_value})
        if default_selection:
            save_to_file_selector.value = default_selection

        save_to_box = toga.Box(
            style=Pack(direction=ROW, flex=1),
            children=[
                toga.Label("Save to:"),
                save_to_file_selector
            ]
        )
        
        self._entry_widgets["save_button"] = save_button
        # self._entry_widgets["clear_button"] = clear_button
        self._entry_widgets["clear_button"] = clear_button
        
        button_box = toga.Box(
            style=Pack(direction=ROW),
            children=[
                clear_button,
                save_button,
            ]
        )

        action_box = toga.Box(
            style=Pack(direction=ROW, margin_top=10),
            children=[
                save_to_box,
                button_box
            ]
        )

        return action_box

    def _transform_file_paths_for_selection(self, file_paths: list[str], main_file: str) -> list[dict[str, str]]:
        """Transform file paths into display format for toga.Selection.
        
        Args:
            file_paths: List of absolute file paths
            main_file: Path to the main file used for common path detection
            
        Returns:
            List of dictionaries with 'name' and 'value' keys for toga.Selection
        """
        if not file_paths:
            return []
        
        # Convert to Path objects for easier manipulation
        paths = [Path(path) for path in file_paths]
        main_path = Path(main_file)
        
        # Find common parent directory using the main file's parent
        # We'll use the main file's parent as reference point
        main_parent = main_path.parent
        
        # Find the deepest common parent among all paths including main file
        all_paths = paths + [main_path]
        common_parent = None
        
        # Start from main file's parent and work upwards
        current_parent = main_parent
        while current_parent != current_parent.parent:  # Not root
            if all(current_parent in path.parents or path == current_parent for path in all_paths):
                common_parent = current_parent
                break
            current_parent = current_parent.parent
        
        # If no common parent found, use the main file's parent
        if common_parent is None:
            common_parent = main_parent
        
        # Create selection items with relative paths
        selection_items = []
        for path in paths:
            try:
                # Get relative path from common parent
                relative_path = path.relative_to(common_parent)
                display_name = str(relative_path)
            except ValueError:
                # If relative path fails, just use the filename
                display_name = path.name
            
            selection_items.append({
                "name": display_name,
                "value": str(path)
            })
        
        return selection_items
    
    def _on_save_to_file_change(self, widget, **kwargs):
        """Handle changes to the 'Save to' file selector."""
        selected_row = widget.value
        selected_file = selected_row.value if selected_row else None
        if not selected_file:
            logger.warning("No file selected for saving")
            return
        beancount_file_path = self.app.active_ledger.beancount_file_path if self.app.active_ledger else ""
        logger.info(f"Selected file for saving: {selected_file}")
        if self.app.active_ledger:
            self.app.active_ledger.beanquick_options.set_default_file(selected_file, beancount_file_path)

    def on_toggle_mode(self):
        """Toggle between normal and quick entry modes."""
        # Toggle mode
        new_mode = EntryMode.QUICK if self._current_mode == EntryMode.NORMAL else EntryMode.NORMAL
        self._switch_mode(new_mode)

    def _switch_mode(self, new_mode: EntryMode):
        """Switch between normal and quick entry modes."""
        if new_mode == self._current_mode:
            return
        
        old_mode = self._current_mode
        self._current_mode = new_mode

        # Recreate UI for new mode
        new_header = self._create_entry_header(new_mode)
        old_header = self._entry_widgets["entry_header"]
        self.main_box.replace(old_header, new_header)
        self._entry_widgets["entry_header"] = new_header

        self._load_entry_form(new_mode)

        # # Update button text
        # widget.text = "Normal Mode" if new_mode == EntryMode.QUICK else "quick Mode"
        # # Update window title
        # if new_mode == EntryMode.QUICK:
        #     self.title = "Beanquick"

        logger.debug(f"Switched from {old_mode.value} to {new_mode.value} mode")

    def _update_preview(self):
        """Update the entry preview with current form data."""
        if not self._entry_preview:
            return
        
        try:
            # Handle quick mode specially
            if self._current_mode == EntryMode.QUICK:
                preview_content = self._get_quick_mode_preview()
            else:
                # Normal mode - use existing logic
                preview_content = self._get_normal_mode_preview()
            
            self._entry_preview.value = preview_content
            
            # Apply syntax highlighting if available
            if self._syntax_highlighter and preview_content:
                self._syntax_highlighter.apply_highlighting(preview_content)
            
        except Exception as e:
            logger.error(f"Error updating preview: {e}", exc_info=True)
            self._entry_preview.value = f"; Error generating preview:\n; {e}"

    def _get_quick_mode_preview(self) -> str:
        """Get preview content for quick mode.
        
        Returns:
            Preview content string for quick mode.
        """
        # Check if we have quick text input
        if not hasattr(self, 'quick_text_input'):
            return "; Quick entry mode not properly initialized"
        
        input_text = self.quick_text_input.value if self.quick_text_input.value else ""
        
        # Handle empty input
        if not input_text.strip():
            return ""
        
        return self._get_beanquick_preview_content()
    
    def _get_normal_mode_preview(self) -> str:
        """Get preview content for normal mode.
        
        Returns:
            Preview content string for normal mode.
        """
        # If form is empty, show placeholder text
        if self._is_form_empty():
            return ""

        # If form is invalid, show error message
        if not self._is_form_valid():
            errors = self._get_form_errors()
            return "; Invalid entry details:\n" + "\n".join(f"; - {error}" for error in errors)

        try:
            # Build the dictionary from form data
            entry_dict = self._build_entry_dict()

            # Create the Beancount object - this validates the entry
            entry_object = deserialise(entry_dict)

            # Convert the object to a string for the preview
            currency_column = getattr(self.app.active_ledger.beanquick_options, 'currency_column', 61) if self.app.active_ledger else 61
            preview_text = to_string(entry_object, currency_column)
            return preview_text

        except (BeanquickError, KeyError, Exception) as e:
            # Catch errors from deserialise and display them to the user
            return f"; Error: {e}"

    async def _on_save(self, widget, **kwargs):
        """Handle save button press."""
        try:
            # Validate form
            # Validation is processed by _parse_string
            # if not self._is_form_valid():
            #     errors = self._get_form_errors()
            #     error_msg = "Please fix the following errors:\n" + "\n".join(f"• {error}" for error in errors)
            #     await self.app.main_window.dialog(
            #         toga.ErrorDialog("Validation Error", error_msg)
            #     )
            #     return

            # Handle Beanquick entries specially
            if self._current_mode == EntryMode.QUICK:
                self._save_beanquick_entry()
            else:
                # Build the final dictionary from the form data
                # entry_dict = self._build_entry_dict()
                # self._save_regular_entry(entry_dict)
                self._save_beanquick_entry()

            # Show success message and clear the form
            await self.app.main_window.dialog(
                toga.InfoDialog("Success", "Entry saved successfully!")
            )
            self._clear_form()
            
            if self.current_form:
                self.current_form.focus_first_input()

        except (BeanquickError, Exception) as e:
            # If deserialisation or file writing fails, show an error
            logger.debug(f"Error saving entry: {e}", exc_info=True)
            await self.app.main_window.dialog(
                toga.StackTraceDialog("Save Error", "Failed to save entry", f"{e}")
            )

    def _save_beanquick_entry(self):
        """Save a Beanquick-generated entry.
        
        Args:
            entry_dict: Dictionary containing Beanquick entry data
        """
        # beancount_output = self._build_quick_entry_output()
        beancount_output = self._entry_preview.value
        if not beancount_output:
            raise ValueError("No Beancount output available for entry")
        
        try:
            # Parse the Beancount output to validate it
            # This ensures the Beanquick-generated output is valid before saving
            entries, errors, _ = parser.parse_string(beancount_output)
            
            if errors:
                error_messages = [str(error) for error in errors]
                raise ValueError(f"{'\n\n'.join(error_messages)}")
            
            if not entries:
                raise ValueError("No valid entries generated from input")
            
            # Insert the parsed entries
            if not self.app.active_ledger:
                raise ValueError("No active ledger available")
            self.app.active_ledger.file.insert_entries(entries)
            
            logger.debug(f"Successfully saved Beanquick entry: {len(entries)} entries")
            
        except Exception as e:
            raise

    def _save_regular_entry(self, entry_dict: dict[str, Any]):
        """Save a regular entry using the normal serialization process.
        
        Args:
            entry_dict: Dictionary containing regular entry data
        """
        # Create the final Beancount entry object - this validates the entry
        entry_to_save = deserialise(entry_dict)

        # Insert the entry using the ledger's file module
        if not self.app.active_ledger:
                raise ValueError("No active ledger available")
        self.app.active_ledger.file.insert_entries([entry_to_save])
        
        logger.debug(f"Successfully saved regular entry: {entry_dict.get('type', 'unknown')}")

    def _on_clear(self, widget, **kwargs):
        """Handle clear button press."""
        self._clear_form()

    def _on_cancel(self, widget, **kwargs):
        """Handle cancel button press."""
        self.close()

    def _on_entry_changed(self, widget, **kwargs):
        """Central handler for all entry changes."""
        if getattr(self, '_clearing_form', False):
            return
            
        logger.debug(f"Entry changed: {widget}")
        self._update_preview()

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
