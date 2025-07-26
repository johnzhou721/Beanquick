from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import os
import logging
from pathlib import Path
from typing import Protocol

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD, START  # type: ignore
from toga.colors import DODGERBLUE, DIMGRAY

from beanquick.services import get_sandbox_service

logger = logging.getLogger(__name__)


LARGE_MARGIN = 20
DEFAULT_MARGIN = 8
TITLE_FONT_SIZE = 36
DESCRIPTION_FONT_SIZE = 10


class LedgerCallback(Protocol):
    def __call__(self, ledger_file_path: str) -> None: ...
    
class SetupBox(toga.Box):
    """
    A Toga Box representing the initial setup screen where users choose
    to create a new Beancount ledger or connect to an existing one.
    """
    def __init__(self, on_ledger_selected: LedgerCallback):
        """
        Initializes the SetupBox.

        Args:
            on_ledger_selected: A callback function that will be invoked
                                when a ledger file is successfully created or selected.
                                It receives the path of the file as an argument.
        """
        super().__init__(style=Pack(direction=ROW, align_items=START, margin=LARGE_MARGIN))

        self.on_ledger_selected = on_ledger_selected
        self.sandbox_service = get_sandbox_service()

        self._build_ui()

    def _build_ui(self):
        """Constructs the user interface elements."""

        # --- 1. Top Area (Logo/App Name & Slogan) ---
        logo = toga.ImageView(
            image = toga.Image('resources/images/logo.png'),
            style=Pack(width=128, height=128)
        )

        app_title = toga.Label(
            "Beanquick",
            style=Pack(font_size=TITLE_FONT_SIZE, font_weight=BOLD, margin_bottom=DEFAULT_MARGIN)
        )
        slogan_label = toga.Label(
            "For the novice. For the expert. For you.",
            style=Pack(font_size=12, color=DIMGRAY)
        )
        header = toga.Box(
            children=[
                logo,
                app_title,
                slogan_label
            ],
            style=Pack(direction=COLUMN, margin_bottom=60, align_items=CENTER)
        )

        # --- Core Options Area ---

        # --- 2.1 Create New Ledger Option ---
        create_button = toga.Button(
            "Create New Ledger",
            on_press=self.create_ledger_handler,
            style=Pack(
                width=350,
                height=28,
                font_weight=BOLD,
                margin_bottom=DEFAULT_MARGIN,
                background_color=DODGERBLUE
            )
        )
        create_label = toga.Label(
            "Start a brand new ledger for your financial data.",
            style=Pack(font_size=DESCRIPTION_FONT_SIZE, color=DIMGRAY)
        )
        create_box = toga.Box(
            children=[create_button, create_label],
            style=Pack(direction=COLUMN, margin_bottom=40, align_items=CENTER)
        )

        # --- 2.2 Connect Existing Ledger Option ---
        connect_button = toga.Button(
            "Open Existing Ledger",
            on_press=self.open_ledger_handler,
            style=Pack(
                width=350,
                height=28,
                font_weight=BOLD,
                margin_bottom=DEFAULT_MARGIN,
            )
        )
        connect_label = toga.Label(
            "Connect to your existing Beancount ledger file.",
            style=Pack(font_size=DESCRIPTION_FONT_SIZE, color=DIMGRAY)
        )
        connect_box = toga.Box(
            children=[connect_button, connect_label],
            style=Pack(direction=COLUMN, align_items=CENTER)
        )

        content_box = toga.Box(
            children=[
                header,
                create_box,
                connect_box,
            ],
            style=Pack(direction=COLUMN, align_items=CENTER)
        )

        # --- Add all components to the main box ---
        self.add(
            toga.Box(style=Pack(flex=1)),
            content_box,
            toga.Box(style=Pack(flex=1))
        )

    async def _show_error(self, message: str):
        """Displays an error message to the user."""
        await self.window.dialog(
            toga.ErrorDialog(
                "Error",
                message,
            )
        )

    async def _show_error_with_details(self, message: str, details: str):
        """Displays an error message with additional details."""
        await self.window.dialog(
            toga.StackTraceDialog(
                "Error",
                message,
                details
            )
        )

    async def create_ledger_handler(self, widget, **kwargs):
        """Handles the 'Create New Ledger' button press."""
        try:
            save_file_dialog = toga.SaveFileDialog(
                title="Create New Ledger",
                suggested_filename="ledger.beancount",
                file_types=['beancount', 'bean']
            )
            file_path_obj = await self.window.dialog(save_file_dialog)

            if file_path_obj is not None:
                if file_path_obj.suffix.lower()[1:] not in ['beancount', 'bean']:
                    file_path_obj = file_path_obj.with_suffix('.beancount')

                try:
                    with open(file_path_obj, 'w', encoding='utf-8') as f:
                        # TODO: Provide a minimal Beancount structure
                        f.write('option "title" "My Ledger"\n')
                        f.write('option "operating_currency" "USD"\n\n')
                        f.write('; Beancount ledger created by Beanquick\n')
                    self.on_ledger_selected(file_path_obj)
                except OSError as e:
                    await self._show_error_with_details("Unable to create file", str(e))
                except Exception as e:
                    await self._show_error_with_details("An unexpected error occurred while creating the file",  str(e))
                
                # macOS sandbox support
                if self.sandbox_service.is_supported():
                    try:
                        # Get the selected file's URL from the native dialog
                        selected_url = save_file_dialog._impl.selected_path()  # This returns NSURL
                        if selected_url:
                            self.sandbox_service.create_bookmark_for_file_selection(selected_url, file_path_obj)
                    except Exception as e:
                        # If bookmark creation fails, still proceed with the callback
                        logger.warning("Failed to create security-scoped bookmark: %s", e)
            else:
                # User cancelled the dialog
                # Stay on the setup page
                pass

        except Exception as e:
            # Catch potential errors with the dialog itself
            await self._show_error_with_details("Error during ledger file creation", str(e))

    async def open_ledger_handler(self, widget, **kwargs):
        """Handles the 'Open Existing Ledger' button press."""
        try: 
            open_file_dialog = toga.OpenFileDialog(
                title="Open Existing Ledger",
                file_types=["beancount", "bean"],
                multiple_select=False,
                # initial_directory=initial_dir
            )
            file_path_obj = await self.window.dialog(open_file_dialog)

            if file_path_obj is not None:
                # Basic validation (check if file exists and suffix)
                if not file_path_obj.is_file():
                        await self._show_error("The selected path is not a valid file.")
                        return # Stay on setup page
                if file_path_obj.suffix.lower()[1:] not in ['beancount', 'bean']:
                        await self._show_error("Please select a .beancount file.")
                        return # Stay on setup page
                
                # Get parent directory's native URL if on macOS
                if self.sandbox_service.is_supported() and hasattr(open_file_dialog, '_impl') and hasattr(open_file_dialog._impl, 'native'):
                    try:
                        # Get the selected file's URL from the native dialog
                        selected_url = open_file_dialog._impl.selected_path()  # This returns NSURL
                        if selected_url:
                            self.sandbox_service.create_bookmark_for_file_selection(selected_url, file_path_obj)
                    except Exception as e:
                        # If bookmark creation fails, still proceed with the callback
                        logger.warning("Failed to create security-scoped bookmark: %s", e)

                # Further validation (e.g., read permissions) could be done here
                # or preferably by the part of the app that loads the ledger.
                self.on_ledger_selected(file_path_obj) # Notify the app

            else:
                # User cancelled the dialog
                # Stay on the setup page
                pass

        except Exception as e:
            # Catch potential errors with the dialog itself
            await self._show_error_with_details("Unable to open file selection dialog.", str(e))
