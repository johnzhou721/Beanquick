from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

from typing import Any

import toga
from toga.style import Pack
from toga.style.pack import CENTER, COLUMN  # type: ignore

LARGE_MARGIN = 20

class LoadingBox(toga.Box):
    def __init__(self, **kwargs: Any):
        """A loading box widget that displays a loading screen.
        """
        super().__init__(style=Pack(direction=COLUMN, flex=1, justify_content=CENTER, align_items=CENTER, margin=LARGE_MARGIN), **kwargs)

        progress_bar = toga.ProgressBar(max=None, value=None, running=True, 
                                        style=Pack(height=20, width=100))
        self.add(progress_bar)

