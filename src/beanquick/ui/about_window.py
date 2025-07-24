"""
About window.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, TYPE_CHECKING

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD

if TYPE_CHECKING:
    from beanquick.app import Beanquick

logger = logging.getLogger(__name__)

class AboutWindow(toga.Window):
    """About window."""
    
    def __init__(self, title="About"):
        super().__init__(title=title, size=(280, 350), resizable=False, minimizable=False)
        
        """Show the about window."""
        self._create_ui()

        logger.info("About window shown")

    def _create_ui(self):
        """Create the UI components."""
        main_box = toga.Box(style=Pack(direction=COLUMN, margin_top=8))

        # App icon
        icon_box = toga.Box(style=Pack(direction=ROW, align_items=CENTER))
        app_icon = toga.ImageView(
            image="resources/images/icon.png",
            style=Pack(width=64, height=64)
        )
        icon_box.add(toga.Box(style=Pack(flex=1)),app_icon, toga.Box(style=Pack(flex=1)))

        # App name
        app_name = toga.Label(
            self.app.formal_name,
            style=Pack(
                font_size=10,
                font_weight=BOLD,
                text_align=CENTER,
                margin_top=8)
        )

        # App version
        app_version = toga.Label(
            self.app.version,
            style=Pack(
                font_size=8,
                text_align=CENTER,
                margin_top=8)
        )

        # App description, Disclaimer, License
        about_text = """
ACKNOWLEDGEMENTS
------------------------------

Beanquick is made possible by the vibrant open-source community and stands on the shoulders of several key projects. We extend our sincere gratitude to the creators and maintainers of these essential tools:

* Beancount: The core of our workflow, Beanquick is a syntax designed to compile into the powerful, plain-text Beancount format. We are immensely grateful for the robust and reliable foundation that Beancount provides for double-entry accounting.

* Fava: A special acknowledgement goes to the Fava project. Beanquick incorporates a substantial amount of source code from Fava, the popular web interface for Beancount, which has been fundamental to building our application.

* Jinja2: The powerful templating feature within Beanquick, which allows for the automation of complex and recurring entries, is powered by the Jinja2 templating engine.

Our thanks also go to the broader open-source community for creating the libraries and tools that have been instrumental in the development of Beanquick.


OPEN SOURCE DECLARATION
------------------------------

Beanquick is proud to utilize and contribute to the open-source community. This software is built using the following open-source projects:

* Beancount: A powerful, plain-text accounting system.
  (https://github.com/beancount/beancount/)

* Jinja2: A modern and designer-friendly templating engine for Python.
  (https://jinja.palletsprojects.com/)

The source code for Beanquick is available on GitHub. We welcome community involvement, including contributions, feature requests, and bug reports.

* Beanquick on GitHub: https://github.com/TwoBitsWare/Beanquick


DISCLAIMER
------------------------------

This software is provided "as is" and without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.

While Beanquick is a tool designed to facilitate fast and precise financial data entry, the user is solely responsible for the accuracy and validity of the data entered and the resulting financial records. The developers and contributors of Beanquick shall not be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

Users are advised to regularly verify account balances and review the generated Beancount entries for correctness. For a deeper understanding of the underlying accounting principles, please refer to the official Beancount documentation.
"""

        content_box = toga.MultilineTextInput(
            value=about_text,
            readonly=True,
            style=Pack(flex=1, margin_top=8, font_size=8)
        )

        # App copyright
        app_copyright = toga.Label(
            f"Copyright © 2025 {self.app.author}. All rights reserved.",
            style=Pack(
                font_size=8,
                text_align=CENTER,
                margin=(8,0))
        )
        
        main_box.add(icon_box, app_name, app_version, content_box, app_copyright)
        self.content = main_box

def show_about_window(app: Beanquick):
    """Show the about window."""
    # Check if there's already a about window open
    existing_window = None
    for window in app.windows:
        if isinstance(window, AboutWindow):
            existing_window = window
            break

    if existing_window:
        app.current_window = existing_window
        return

    try:
        about_window = AboutWindow()
        about_window.show()
    except Exception as e:
        logger.error(f"Error showing about window: {e}", exc_info=True)
        for window in app.windows:
            if isinstance(window, AboutWindow):
                app.windows.discard(window)
                break

        if app.main_window:
            asyncio.create_task(
                app.main_window.dialog(
                    toga.ErrorDialog(
                        "Error",
                        f"Could not open about window: {str(e)}"
                    )
                )
            )
