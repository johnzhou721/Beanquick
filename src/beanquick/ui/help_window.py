"""Help window implementation for Beanquick with markdown rendering.

This help window displays documentation from the help folder using a WebView
for reliable cross-platform markdown rendering.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
import base64


import toga
from toga.style import Pack

from beanquick.util.markdown_renderer import MarkdownRenderer

logger = logging.getLogger(__name__)

# Find the help directory relative to this file
BASE_HELP_DIR = Path(__file__).parent.parent / "help"
DEFAULT_LOCALE = "en_US"


class HelpWindow(toga.Window):
    """Help window that displays documentation with markdown rendering."""
    
    def __init__(self, title="Help", topic=None):
        """Initialize the help window.
        
        Args:
            title: Window title
            topic: Optional specific help topic to display
        """
        super().__init__(title=title, size=(800, 600))
        self.locale = self._get_current_locale()
        self._topic_path = None
        self._markdown_renderer = None
        self._build_ui()
        
        # If a specific topic is provided, display it
        if topic:
            self.set_topic_by_path(topic)
    
    def _get_current_locale(self) -> str:
        """Get the current locale from the app."""
        try:
            # Try to get locale from the app's babel instance
            from beanquick.app import babel
            return str(babel.get_locale())
        except (ImportError, AttributeError) as e:
            logger.warning(f"Failed to get current locale: {e}")
        
        # Default fallback
        return DEFAULT_LOCALE
    
    def _get_available_locales(self) -> List[str]:
        """Get all available locales with help content."""
        if not BASE_HELP_DIR.exists():
            return [DEFAULT_LOCALE]
        
        locales = []
        for path in BASE_HELP_DIR.iterdir():
            if path.is_dir() and not path.name.startswith('.'):
                locales.append(path.name)
        
        # If the list is empty, add at least the default locale
        if not locales:
            locales.append(DEFAULT_LOCALE)
        
        return locales
    
    def _resolve_help_file_path(self, topic_path: Union[str, Path]) -> Optional[Path]:
        """
        Resolve a help file path with locale support.
        
        Args:
            topic_path: Original topic path or relative path
            
        Returns:
            Path to the localized help file or None if not found
        """
        if not topic_path:
            return None
        
        # Convert to Path object if it's a string
        if isinstance(topic_path, str):
            topic_path = Path(topic_path)
        
        # If it's already an absolute path and exists, use it directly
        if topic_path.is_absolute() and topic_path.exists():
            return topic_path
        
        # If it's a relative path, try to find it in the localized help folders
        topic_file = topic_path.name
        
        # Try current locale first
        localized_path = BASE_HELP_DIR / self.locale / topic_file
        if localized_path.exists():
            return localized_path
        
        # Try default locale if different from current
        if self.locale != DEFAULT_LOCALE:
            default_path = BASE_HELP_DIR / DEFAULT_LOCALE / topic_file
            if default_path.exists():
                return default_path
        
        # Try non-localized path in the base directory
        base_path = BASE_HELP_DIR / topic_file
        if base_path.exists():
            return base_path
        
        # If not found and the path looks like a full path within help dir
        if len(topic_path.parts) > 1:
            # If it contains locale info already, try as is
            constructed_path = BASE_HELP_DIR.joinpath(*topic_path.parts)
            if constructed_path.exists():
                return constructed_path
        
        # If original path exists, use it
        if topic_path.exists():
            return topic_path
            
        logger.warning(f"Could not find help file for: {topic_path}")
        return None
        
    def _build_ui(self):
        """Build the help window UI."""
        # Main container
        main_box = toga.Box(style=Pack(direction=toga.style.pack.COLUMN, margin=10, flex=1))
        
        # Create split view with topics on left, content on right
        split_container = toga.SplitContainer(style=Pack(flex=1))
        
        # Topics list on the left
        topics_box = toga.Box(style=Pack(direction=toga.style.pack.COLUMN, flex=1))
        self.topics_list = self._create_topics_list()
        topics_box.add(self.topics_list)
        
        # Add locale selector if multiple locales are available
        available_locales = self._get_available_locales()
        if len(available_locales) > 1:
            self.locale_selector = toga.Selection(
                items=available_locales,
                on_change=self._on_locale_changed,
            )
            self.locale_selector.value = self.locale if self.locale in available_locales else DEFAULT_LOCALE
            locale_box = toga.Box(
                style=Pack(direction=toga.style.pack.ROW, margin_top=10),
                children=[
                    toga.Label("Language:", style=Pack(margin_right=10)),
                    self.locale_selector
                ]
            )
            topics_box.add(locale_box)
        else:
            self.locale_selector = None
        
        # Content view on the right - use WebView for markdown rendering
        self.content_view = toga.WebView(style=Pack(flex=1))

        # Initialize markdown renderer with adaptive theming
        try:
            self._markdown_renderer = MarkdownRenderer()
            logger.debug("Markdown renderer initialized with adaptive theming")
        except Exception as e:
            logger.warning(f"Failed to initialize markdown renderer: {e}")
            self._markdown_renderer = None

        # Add both sides to the split container
        split_container.content = [(topics_box, 1), (self.content_view, 3)]
        
        # Add the split container to the main box
        main_box.add(split_container)
        
        # Set the window content
        self.content = main_box
    
    def _on_locale_changed(self, widget):
        """Handle locale selection change."""
        if widget.value == self.locale:
            return
        
        # Save current topic for potential reload
        current_topic = self._topic_path
        
        # Update locale
        self.locale = widget.value
        logger.info(f"Help locale changed to: {self.locale}")
        
        # Reload topics list
        self._refresh_topics_list()
        
        # Try to load equivalent topic in the new locale
        if current_topic:
            # Extract the base filename without locale info
            if isinstance(current_topic, str):
                current_topic = Path(current_topic)
            
            # Try to load equivalent topic in the new locale
            self.set_topic_by_name(current_topic.stem)
    
    def _refresh_topics_list(self):
        """Refresh the topics list for the current locale."""
        # Get updated topics data
        topics_data = self._get_topics_data()
        
        # Update the table data
        self.topics_list.data = topics_data
    
    def load_topic_file(self, file_path: str):
        """Load content from a help file.
        
        Args:
            file_path: Path to the help file to load
        """
        # Resolve the path with locale support
        resolved_path = self._resolve_help_file_path(file_path)
        if not resolved_path:
            logger.error(f"Could not resolve help file path: {file_path}")
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        color: #d32f2f;
                        margin: 20px;
                    }}
                </style>
            </head>
            <body>Could not find help file: {file_path}</body>
            </html>
            """
            self.content_view.set_content("", error_html)
            return
        
        try:
            with open(resolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if it's a markdown file and we have a renderer
            if (resolved_path.suffix.lower() in ['.md', '.markdown']) and self._markdown_renderer:
                # Render markdown to HTML
                html_content = self._markdown_renderer.markdown_to_html(content)
                
                # Process links in the HTML content
                html_content = self._process_links_in_html(html_content)
                
                # Process images in the HTML content
                html_content = self._process_images_in_html(html_content, resolved_path)
                
                self.content_view.set_content("", html_content)
            else:
                # Display as plain text in a simple HTML wrapper
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                            font-size: 14px;
                            line-height: 1.6;
                            color: #333;
                            margin: 20px;
                            white-space: pre-wrap;
                        }}
                    </style>
                </head>
                <body>{content}</body>
                </html>
                """
                self.content_view.set_content("", html_content)
                
        except Exception as e:
            logger.error(f"Error loading help content: {e}")
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        color: #d32f2f;
                        margin: 20px;
                    }}
                </style>
            </head>
            <body>Error loading help content: {str(e)}</body>
            </html>
            """
            self.content_view.set_content("", error_html)
    
    def _process_links_in_html(self, html_content: str) -> str:
        """Process links in HTML content to handle internal navigation.
        
        Args:
            html_content: The HTML content to process
            
        Returns:
            HTML content with processed links
        """
        import re
        
        def replace_internal_link(match):
            href = match.group(1)  # href is group 1, text is group 2
            text = match.group(2)
            
            # Define adaptive link styles using CSS custom properties and media queries
            link_styles = '''
                /* Light theme styles (default) */
                color: #0969da;
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 8px;
                margin: 2px;
                display: inline-block;
                font-size: 0.9em;
                transition: color 0.3s ease, background-color 0.3s ease, border-color 0.3s ease;
            '''
            
            external_link_styles = '''
                /* Light theme styles (default) */
                color: #0969da;
                background-color: #f6f8fa;
                border: 1px solid #0969da;
                border-radius: 6px;
                padding: 4px 8px;
                margin: 2px;
                display: inline-block;
                font-size: 0.75em;
                transition: color 0.3s ease, background-color 0.3s ease, border-color 0.3s ease;
            '''
            
            small_text_styles = '''
                /* Light theme styles (default) */
                color: #656d76;
                transition: color 0.3s ease;
            '''
            
            anchor_styles = '''
                /* Light theme styles (default) */
                color: #0969da;
                text-decoration: none;
                transition: color 0.3s ease;
            '''
            
            if href.startswith('http://') or href.startswith('https://'):
                # Convert external links to copyable text with clear instructions
                return f'''<span style="{external_link_styles}">
                    🔗 {text}: <strong>{href}</strong>
                    <small style="{small_text_styles}">(Copy this URL to your browser)</small>
                </span>
                <style>
                    @media (prefers-color-scheme: dark) {{
                        span[style*="border: 1px solid #0969da"] {{
                            color: #64c8ff !important;
                            background-color: rgba(100, 200, 255, 0.1) !important;
                            border-color: rgba(100, 200, 255, 0.3) !important;
                        }}
                        span[style*="border: 1px solid #0969da"] small {{
                            color: #969696 !important;
                        }}
                    }}
                </style>'''
            elif href.startswith('#'):
                # Handle anchor links with JavaScript for proper navigation
                target_id = href[1:]  # Remove the # symbol
                # Ensure the target_id is properly escaped for JavaScript
                js_escaped_id = target_id.replace("'", "\\'").replace('"', '\\"')
                return f'''<a href="{href}" style="{anchor_styles}" onclick="scrollToAnchor('{js_escaped_id}'); return false;">{text}</a>
                <style>
                    @media (prefers-color-scheme: dark) {{
                        a[href^="#"] {{
                            color: #64c8ff !important;
                        }}
                    }}
                </style>'''
            else:
                # Convert internal links to a visual navigation hint
                topic_name = href.replace('.md', '').replace('.markdown', '')
                return f'''<span style="{link_styles}">
                    📄 {text} → <strong>{topic_name.title()}</strong>
                    <small style="{small_text_styles}">(Select "{topic_name.title()}" from the topics list)</small>
                </span>
                <style>
                    @media (prefers-color-scheme: dark) {{
                        span[style*="border: 1px solid #d0d7de"] {{
                            color: #64c8ff !important;
                            background-color: rgba(100, 200, 255, 0.1) !important;
                            border-color: rgba(100, 200, 255, 0.3) !important;
                        }}
                        span[style*="border: 1px solid #d0d7de"] small {{
                            color: #969696 !important;
                        }}
                    }}
                </style>'''
        
        # Replace all <a href="...">text</a> patterns
        html_content = re.sub(r'<a href="([^"]+)">([^<]+)</a>', replace_internal_link, html_content)
        
        return html_content
    
    def _encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        """Convert an image file to base64 data URL.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 data URL string or None if failed
        """
        try:
            if not image_path.exists():
                logger.warning(f"Image file not found: {image_path}")
                return None
            
            # Read and encode the image
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
                base64_data = base64.b64encode(img_data).decode('utf-8')
                return f"data:image/png;base64,{base64_data}"
                
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            return None
    
    def _process_images_in_html(self, html_content: str, base_path: Path, use_file_urls: bool = False) -> str:
        """Process image references in HTML content.
        
        Args:
            html_content: The HTML content to process
            base_path: Base path for resolving relative image paths
            use_file_urls: If True, use file:// URLs instead of base64 embedding
            
        Returns:
            HTML content with processed images
        """
        import re
        
        def replace_image_src(match):
            src = match.group(1)  # The src attribute value
            rest = match.group(2)  # Everything after src="..."
            
            # Skip if already a data URL or absolute URL
            if src.startswith('data:') or src.startswith('http://') or src.startswith('https://') or src.startswith('file://'):
                return match.group(0)  # Return unchanged
            
            # Resolve relative path
            image_path = base_path.parent / src if not Path(src).is_absolute() else Path(src)
            
            if use_file_urls:
                # Use file:// URL (may not work on all platforms)
                if image_path.exists():
                    file_url = image_path.as_uri()
                    return f'<img src="{file_url}"{rest}'
                else:
                    # Replace with placeholder if image not found
                    placeholder = f"data:image/svg+xml;base64,{base64.b64encode(self._create_placeholder_svg(src).encode()).decode()}"
                    return f'<img src="{placeholder}"{rest}'
            else:
                # Try to encode to base64 (default behavior)
                base64_url = self._encode_image_to_base64(image_path)
                if base64_url:
                    return f'<img src="{base64_url}"{rest}'
                else:
                    # Replace with placeholder if image not found
                    placeholder = f"data:image/svg+xml;base64,{base64.b64encode(self._create_placeholder_svg(src).encode()).decode()}"
                    return f'<img src="{placeholder}"{rest}'
        
        # Replace all <img src="..."> patterns
        html_content = re.sub(r'<img src="([^"]+)"([^>]*>)', replace_image_src, html_content)
        
        return html_content
    
    def _create_placeholder_svg(self, original_src: str) -> str:
        """Create an SVG placeholder for missing images.
        
        Args:
            original_src: The original image source that couldn't be loaded
            
        Returns:
            SVG markup as string
        """
        return f'''<svg width="200" height="150" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="150" fill="#f0f0f0" stroke="#ccc" stroke-width="2"/>
            <text x="100" y="75" text-anchor="middle" fill="#666" font-size="12" font-family="Arial">
                Image not found:
            </text>
            <text x="100" y="95" text-anchor="middle" fill="#666" font-size="10" font-family="Arial">
                {original_src}
            </text>
        </svg>'''
    
    def _get_topics_data(self) -> List[Dict[str, Any]]:
        """Get topics data for the current locale."""
        topics = []
        
        # Get locale-specific help directory
        locale_help_dir = BASE_HELP_DIR / self.locale
        
        # Check if localized help directory exists
        if locale_help_dir.exists():
            # Get all .md files in the localized directory
            for file_path in locale_help_dir.glob('*.md'):
                topic_name = file_path.stem.title()
                topics.append({
                    "name": topic_name,
                    "path": str(file_path)
                })
            
            # Also check for README.rst files
            for file_path in locale_help_dir.glob('README.rst'):
                topics.append({
                    "name": "Introduction",
                    "path": str(file_path)
                })
        
        # If no topics found in the current locale, try the default locale
        if not topics and self.locale != DEFAULT_LOCALE:
            default_locale_dir = BASE_HELP_DIR / DEFAULT_LOCALE
            if default_locale_dir.exists():
                for file_path in default_locale_dir.glob('*.md'):
                    topic_name = file_path.stem.title()
                    topics.append({
                        "name": topic_name,
                        "path": str(file_path)
                    })
                
                # Also check for README.rst files
                for file_path in default_locale_dir.glob('README.rst'):
                    topics.append({
                        "name": "Introduction",
                        "path": str(file_path)
                    })
        
        # If still no topics, check base help directory
        if not topics:
            for file_path in BASE_HELP_DIR.glob('*.md'):
                topic_name = file_path.stem.title()
                topics.append({
                    "name": topic_name,
                    "path": str(file_path)
                })
            
            # Also check for README.rst files
            for file_path in BASE_HELP_DIR.glob('README.rst'):
                topics.append({
                    "name": "Introduction",
                    "path": str(file_path)
                })
        
        # Sort topics alphabetically
        topics.sort(key=lambda t: t["name"])
        
        # If we have no topics, add a default entry
        if not topics:
            topics.append({
                "name": "No help available",
                "path": None
            })
        
        return topics
    
    def _create_topics_list(self):
        """Create and populate the topics list."""
        topics_data = self._get_topics_data()
        
        # Create table with topics
        table = toga.Table(
            headings=["Help Topic"],
            accessors=["name"],
            data=topics_data,
            on_select=self._on_topic_selected,
            style=Pack(margin=1, flex=1)
        )
        
        return table
    
    def _on_topic_selected(self, widget):
        """Handle topic selection."""
        if widget.selection and widget.selection.path:
            self.set_topic_by_path(widget.selection.path)
    
    def set_topic_by_path(self, path):
        """Set the current topic by path and load its content."""
        self._topic_path = path
        
        if not path:
            # Show welcome message
            welcome_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        color: #666;
                        margin: 20px;
                        text-align: center;
                    }
                </style>
            </head>
            <body>
                <h2>Beanquick Help</h2>
                <p>Please select a help topic from the list on the left.</p>
            </body>
            </html>
            """
            self.content_view.set_content("", welcome_html)
            return
        
        self.load_topic_file(path)
    
    def set_topic_by_name(self, topic_name):
        """Set the current topic by name."""
        if not topic_name:
            return
        
        # Try to find the topic in the current locale
        locale_help_dir = BASE_HELP_DIR / self.locale
        if locale_help_dir.exists():
            # Look for .md file matching the topic name
            topic_path = locale_help_dir / f"{topic_name}.md"
            if topic_path.exists():
                self.set_topic_by_path(str(topic_path))
                return
            
            # If topic is "introduction", look for README.rst
            if topic_name.lower() == "introduction":
                readme_path = locale_help_dir / "README.rst"
                if readme_path.exists():
                    self.set_topic_by_path(str(readme_path))
                    return
        
        # If not found, try default locale
        if self.locale != DEFAULT_LOCALE:
            default_locale_dir = BASE_HELP_DIR / DEFAULT_LOCALE
            if default_locale_dir.exists():
                topic_path = default_locale_dir / f"{topic_name}.md"
                if topic_path.exists():
                    self.set_topic_by_path(str(topic_path))
                    return
                
                # If topic is "introduction", look for README.rst
                if topic_name.lower() == "introduction":
                    readme_path = default_locale_dir / "README.rst"
                    if readme_path.exists():
                        self.set_topic_by_path(str(readme_path))
                        return
        
        # If still not found, try base directory
        topic_path = BASE_HELP_DIR / f"{topic_name}.md"
        if topic_path.exists():
            self.set_topic_by_path(str(topic_path))
            return
        
        # If topic is "introduction", look for README.rst in base directory
        if topic_name.lower() == "introduction":
            readme_path = BASE_HELP_DIR / "README.rst"
            if readme_path.exists():
                self.set_topic_by_path(str(readme_path))
                return
        
        logger.warning(f"Could not find help topic: {topic_name}")
        # Show error message
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    color: #d32f2f;
                    margin: 20px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>Could not find help topic: {topic_name}</body>
        </html>
        """
        self.content_view.set_content("", error_html)


def show_help_window(app, topic=None):
    """Show the help window. If one already exists, bring it to front.
    
    Args:
        app: The main application instance
        topic: Optional specific topic to display
    """
    # Check if there's already a help window
    existing_help_window = None
    for window in app.windows:
        if isinstance(window, HelpWindow):
            existing_help_window = window
            break
    
    if existing_help_window:
        # If the window already exists, just show it and update the topic
        if topic:
            existing_help_window.set_topic_by_path(topic)
        app.current_window = existing_help_window
        return

    try:
        # Create a new help window
        help_window = HelpWindow(topic=topic)
        help_window.show()
    except Exception as e:
        logger.error(f"Error showing help window: {e}", exc_info=True)
        if app.main_window:
            app.main_window.error_dialog(
                "Error",
                f"Could not open help window: {str(e)}"
            )
