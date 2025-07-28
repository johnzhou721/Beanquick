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
from beanquick.services.ledger_manager import create_ledger_dialog, open_ledger_dialog

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
    def __init__(self, app_instance, on_ledger_selected: LedgerCallback):
        """
        Initializes the SetupBox.

        Args:
            on_ledger_selected: A callback function that will be invoked
                                when a ledger file is successfully created or selected.
                                It receives the path of the file as an argument.
        """
        super().__init__(style=Pack(direction=ROW, align_items=START, margin=LARGE_MARGIN))

        self.app_instance = app_instance
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
        ledger_file_path = await create_ledger_dialog(self.window, self.app_instance)
        if ledger_file_path:
            self.on_ledger_selected(ledger_file_path)

    async def open_ledger_handler(self, widget, **kwargs):
        """Handles the 'Open Existing Ledger' button press."""
        ledger_file_path = await open_ledger_dialog(self.window, self.app_instance)
        self.on_ledger_selected(ledger_file_path)
