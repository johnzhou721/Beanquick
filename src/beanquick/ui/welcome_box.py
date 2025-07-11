from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

from typing import Any, Callable

import toga
from toga.style import Pack
from toga.fonts import BOLD  # type: ignore
from toga.style.pack import START, CENTER, COLUMN, ROW  # type: ignore
from toga.constants import DODGERBLUE

from beanquick.constants import DEFAULT_BUTTON_HEIGHT

LARGE_MARGIN = 20
DEFAULT_MARGIN = 8
TITLE_FONT_SIZE = 36

class WelcomeBox(toga.Box):
    def __init__(self, on_complete: Callable[[], None], **kwargs: Any):
        """A welcome box widget that displays a greeting screen.
        """
        super().__init__(style=Pack(direction=COLUMN, align_items=CENTER, margin=LARGE_MARGIN), **kwargs)

        self.on_complete = on_complete

        logo = toga.ImageView(
            image=toga.Image("resources/images/icon.png"),
            style=Pack(height=128, width=128)
        )

        title_label = toga.Label(
            "Welcome to Beanquick",
            style=Pack(
                text_align=CENTER,
                font_size=TITLE_FONT_SIZE,
                font_weight=BOLD,
                margin_bottom=DEFAULT_MARGIN,
            )
        )
        slogan_label = toga.Label(
            "A lightweight and rapid desktop entry tool, built for Beancount.",
            style=Pack(
                text_align=CENTER,
                font_size=12,
                margin_bottom=40
            )
        )
        content_box = self.build_content_box()

        continue_button = toga.Button(
            "Continue",
            on_press=self.on_continue_pressed,
            style=Pack(
                font_weight=BOLD,
                margin_bottom=LARGE_MARGIN,
                height=DEFAULT_BUTTON_HEIGHT,
                width=480,
                background_color=DODGERBLUE)
        )
        self.add(logo, title_label, slogan_label, content_box, continue_button)
    
    def on_continue_pressed(self, widget):
        if self.on_complete:
            self.on_complete()

    @classmethod
    def build_content_box(cls):
        WELCOME_BOX_CONTENT = [
            {
                "id": "NotoHighVoltage",
                "title": "Instant Entry",
                "description": "Designed for efficient entry, making every one of your transactions lightning-fast."
            },
            {
                "id": "EmojioneCardFileBox",
                "title": "Ready Out of the Box",
                "description": "Just link your Beancount file and start immediately. For the novice. For the expert. For you."
            },
            {
                "id": "EmojioneShield",
                "title": "Locally Stored Data",
                "description": "All your financial records are securely stored directly on your device, private and future-proof."
            }
        ]
        content_box = toga.Box(style=Pack(direction=COLUMN, align_items=START))
        for item in WELCOME_BOX_CONTENT:
            content_box.add(
                toga.Box(
                    children=[
                        toga.ImageView(
                            image=toga.Image(f"resources/images/{item["id"]}.png"),
                            style=Pack(height=36, width=36, margin_top=5)
                        ),
                        toga.Box(
                            children=[
                                toga.Label(item["title"], style=Pack(font_size=14, font_weight=BOLD)),
                                toga.Label(item["description"], style=Pack(margin_top=5, width=360, height=36)),
                            ],
                            style=Pack(direction=COLUMN, margin_left=16)
                        )
                    ],
                    style=Pack(direction=ROW, align_items=START, margin=(8, 0))
                ),
            )
        return toga.Box(
            children=[
                toga.Box(style=Pack(flex=1)),
                content_box,
                toga.Box(style=Pack(flex=1)),
            ],
            style=Pack(direction=ROW, flex=1, align_items=START, margin=(0, 45))
        )

