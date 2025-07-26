from __future__ import annotations

import os
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING

import toga

from beanquick.util.excel import HAVE_EXCEL

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from beanquick.beans.abc import Meta
    from beanquick.beans.abc import Query
    from beanquick.core import BeanquickLedger
    from beanquick.core.accounts import AccountDict
    # from beanquick.core.extensions import ExtensionDetails
    from beanquick.core.beanquick_options import FavaOptions
    from beanquick.helpers import BeancountError

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class SerialisedError:
    """A Beancount error, as passed to the frontend."""

    type: str
    source: Meta | None
    message: str

    @staticmethod
    def from_beancount_error(err: BeancountError) -> SerialisedError:
        """Get a serialisable error from a Beancount error."""
        source = dict(err.source) if err.source is not None else None
        if source is not None:
            source.pop("__tolerances__", None)
        return SerialisedError(err.__class__.__name__, source, err.message)


@dataclass(frozen=True)
class LedgerData:
    """This is used as report-independent data in the frontend."""

    accounts: Sequence[str]
    account_details: AccountDict
    currencies: Sequence[str]
    currency_names: dict[str, str]
    errors: Sequence[SerialisedError]
    beanquick_options: FavaOptions
    have_excel: bool
    links: Sequence[str]
    options: dict[str, str | Sequence[str]]
    payees: Sequence[str]
    precisions: dict[str, int]
    tags: Sequence[str]
    years: Sequence[str]
    user_queries: Sequence[Query]
    upcoming_events_count: int
    # extensions: Sequence[ExtensionDetails]
    sidebar_links: Sequence[tuple[str, str]]


def get_errors(ledger: BeanquickLedger) -> list[SerialisedError]:
    """Serialise errors (do not pass entry as that might fail serialisation."""
    return [SerialisedError.from_beancount_error(e) for e in ledger.errors]


def _get_options(ledger: BeanquickLedger) -> dict[str, str | Sequence[str]]:
    options = ledger.options
    return {
        "documents": options["documents"],
        "filename": options["filename"],
        "include": options["include"],
        "operating_currency": options["operating_currency"],
        "title": options["title"],
        "name_assets": options["name_assets"],
        "name_liabilities": options["name_liabilities"],
        "name_equity": options["name_equity"],
        "name_income": options["name_income"],
        "name_expenses": options["name_expenses"],
    }


def get_ledger_data(ledger: BeanquickLedger) -> LedgerData:
    """Get the report-independent ledger data."""
    all_queries = ledger.all_entries_by_type.Query

    return LedgerData(
        ledger.attributes.accounts,
        ledger.accounts,
        ledger.attributes.currencies,
        ledger.commodities.names,
        get_errors(ledger),
        ledger.beanquick_options,
        HAVE_EXCEL,
        ledger.attributes.links,
        _get_options(ledger),
        ledger.attributes.payees,
        ledger.format_decimal.precisions,
        ledger.attributes.tags,
        ledger.attributes.years,
        all_queries[: ledger.beanquick_options.sidebar_show_queries],
        len(ledger.misc.upcoming_events),
        # ledger.extensions.extension_details,
        ledger.misc.sidebar_links,
    )


async def open_ledger_dialog(window, app_instance) -> str | None:
    """
    Unified function to open a ledger file dialog.
    
    Args:
        window: The window to show dialogs on
        app_instance: app instance for config updates
        
    Returns:
        Path str of selected file, or None if cancelled/error
    """
    from beanquick.services import get_sandbox_service
    
    try:
        sandbox_service = get_sandbox_service()

        open_file_dialog = toga.OpenFileDialog(
            title="Open Existing Ledger",
            file_types=["beancount", "bean"],
            multiple_select=False,
        )
        file_path_obj = await window.dialog(open_file_dialog)

        if file_path_obj is not None:
            # Basic validation (check if file exists and suffix)
            if not file_path_obj.is_file():
                error_msg = "Please select a valid file path."
                await window.dialog(toga.ErrorDialog("Error", error_msg))
                return None
                
            if file_path_obj.suffix.lower()[1:] not in ['beancount', 'bean']:
                error_msg = "Please select a .beancount file."
                await window.dialog(toga.ErrorDialog("Error", error_msg))
                return None
            
            # Handle sandbox bookmarks for macOS
            if sandbox_service and sandbox_service.is_supported() and hasattr(open_file_dialog, '_impl'):
                try:
                    # Get the selected file's URL from the native dialog
                    selected_url = open_file_dialog._impl.selected_path()  # This returns NSURL
                    if selected_url:
                        sandbox_service.create_bookmark_for_file_selection(selected_url, file_path_obj)
                except Exception as e:
                    # If bookmark creation fails, still proceed
                    logger.warning("Failed to create security-scoped bookmark: %s", e)
            
            ledger_file_path = str(file_path_obj)

            # Add the selected file to the config
            # It will also set the active_beancount_file if applicable
            if not app_instance.config.add_beancount_file(ledger_file_path, set_active=True):
                logger.error(f"Failed to add beancount file to config: {ledger_file_path}")

            return ledger_file_path
        else:
            # User cancelled the dialog
            return None

    except Exception as e:
        error_msg = f"Unable to open file selection dialog: {str(e)}"
        logger.error(f"Error during ledger file selection: {e}")
        await window.dialog(toga.ErrorDialog("Error", "Unable to open file selection dialog."))
        return None
