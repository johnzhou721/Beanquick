"""Base class for the "modules" of BeanquickLedger."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from beanquick.core import BeanquickLedger


class FavaModule:
    """Base class for the "modules" of BeanquickLedger."""

    def __init__(self, ledger: BeanquickLedger) -> None:
        self.ledger = ledger

    def load_file(self) -> None:
        """Run when the file has been (re)loaded."""
