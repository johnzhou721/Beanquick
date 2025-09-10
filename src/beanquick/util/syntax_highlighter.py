"""
Syntax highlighting for Beancount in toga MultilineTextInput.
"""

import re
import sys
from typing import List, Any, Optional
import logging

from toga.colors import Color, rgb
from toga_cocoa.colors import native_color

if sys.platform == "darwin":
    from toga_cocoa.libs import (
        NSColor, NSFont, NSRange,
        NSForegroundColorAttributeName, NSFontAttributeName
    )

logger = logging.getLogger(__name__)

class ColorScheme:
    """Color scheme definition for syntax highlighting using toga Color classes."""
    
    def __init__(self, name: str, **colors):
        """Initialize color scheme.
        
        Args:
            name: Name of the color scheme
            **colors: Color definitions as rgb tuples (r, g, b) or Color objects
        """
        self.name = name
        self.colors = {}
        
        # Convert RGB tuples to Color objects
        for key, value in colors.items():
            if isinstance(value, tuple) and len(value) == 3:
                # RGB tuple
                r, g, b = value
                self.colors[key] = rgb(r, g, b)
            elif isinstance(value, Color):
                # Already a Color object
                self.colors[key] = value
            else:
                # Invalid color format, skip
                continue
    
    def get_color(self, color_key: str) -> Optional[Color]:
        """Get a color by key.
        
        Args:
            color_key: Key for the color (e.g., 'date', 'account', etc.)
            
        Returns:
            Color object or None if not found
        """
        return self.colors.get(color_key)
    
    def get_nscolor(self, color_key: str) -> Any:
        """Convert color to NSColor if on macOS.
        
        Args:
            color_key: Key for the color
            
        Returns:
            NSColor object or None
        """
        if sys.platform != "darwin":
            return None
        
        color = self.get_color(color_key)
        if not color:
            return None
        
        # Use toga's native_color function for conversion
        return native_color(color)


# Color schemes based on popular editor themes
COLOR_SCHEMES = {
    # Classic Light Theme - Clean and readable
    'light_classic': ColorScheme(
        name="Light Classic",
        date=(0, 100, 200),           # Blue
        account=(128, 0, 128),        # Purple  
        amount=(0, 128, 0),           # Green
        currency=(255, 140, 0),       # Dark Orange
        string=(196, 26, 22),         # Dark Red
        comment=(128, 128, 128),      # Gray
        keyword=(170, 13, 145),       # Magenta
        tag=(0, 150, 136),            # Teal
        normal=(0, 0, 0),             # Black
        background=(255, 255, 255)    # White
    ),
    
    # Dark Theme - Easy on the eyes
    'dark_modern': ColorScheme(
        name="Dark Modern",
        date=(100, 200, 255),         # Light Blue
        account=(200, 150, 255),      # Light Purple
        amount=(100, 255, 100),       # Light Green  
        currency=(255, 180, 50),      # Orange
        string=(255, 120, 120),       # Light Red
        comment=(120, 120, 120),      # Light Gray
        keyword=(255, 100, 200),      # Pink
        tag=(100, 255, 200),          # Light Teal
        normal=(220, 220, 220),       # Light Gray
        background=(40, 40, 40)       # Dark Gray
    ),
    
    # Solarized Light - Inspired by the popular Solarized theme
    'solarized_light': ColorScheme(
        name="Solarized Light",
        date=(38, 139, 210),          # Blue
        account=(108, 113, 196),      # Violet
        amount=(133, 153, 0),         # Green
        currency=(203, 75, 22),       # Orange
        string=(220, 50, 47),         # Red
        comment=(147, 161, 161),      # Base1
        keyword=(211, 54, 130),       # Magenta
        tag=(42, 161, 152),           # Cyan
        normal=(101, 123, 131),       # Base00
        background=(253, 246, 227)    # Base3
    ),
    
    # Solarized Dark
    'solarized_dark': ColorScheme(
        name="Solarized Dark", 
        date=(131, 148, 150),         # Base0
        account=(108, 113, 196),      # Violet
        amount=(133, 153, 0),         # Green
        currency=(203, 75, 22),       # Orange
        string=(220, 50, 47),         # Red
        comment=(88, 110, 117),       # Base01
        keyword=(211, 54, 130),       # Magenta
        tag=(42, 161, 152),           # Cyan
        normal=(131, 148, 150),       # Base0
        background=(0, 43, 54)        # Base03
    ),
    
    # Monokai - Dark theme with vibrant colors
    'monokai': ColorScheme(
        name="Monokai",
        date=(102, 217, 239),         # Cyan
        account=(174, 129, 255),      # Purple
        amount=(166, 226, 46),        # Green
        currency=(253, 151, 31),      # Orange
        string=(230, 219, 116),       # Yellow
        comment=(117, 113, 94),       # Comment Gray
        keyword=(249, 38, 114),       # Pink/Magenta
        tag=(102, 217, 239),          # Cyan (same as date)
        normal=(248, 248, 242),       # Foreground
        background=(39, 40, 34)       # Background
    ),
    
    # VS Code Dark+ Theme
    'vscode_dark': ColorScheme(
        name="VS Code Dark+",
        date=(86, 156, 214),          # Light Blue
        account=(78, 201, 176),       # Teal
        amount=(181, 206, 168),       # Light Green
        currency=(220, 220, 170),     # Light Yellow
        string=(206, 145, 120),       # Light Orange
        comment=(106, 153, 85),       # Green Comment
        keyword=(197, 134, 192),      # Light Purple
        tag=(78, 201, 176),           # Teal (same as account)
        normal=(212, 212, 212),       # Light Gray
        background=(30, 30, 30)       # Dark Gray
    ),
    
    # GitHub Light Theme
    'github_light': ColorScheme(
        name="GitHub Light",
        date=(3, 102, 214),           # Blue
        account=(111, 66, 193),       # Purple
        amount=(40, 167, 69),         # Green
        currency=(227, 98, 9),        # Orange
        string=(3, 47, 98),           # Dark Blue
        comment=(106, 115, 125),      # Gray
        keyword=(215, 58, 73),        # Red
        tag=(0, 92, 197),             # Blue (variant)
        normal=(36, 41, 46),          # Dark Gray
        background=(255, 255, 255)    # White
    ),

    # GitHub Dark Theme
    'github_dark': ColorScheme(
        name="GitHub Dark",
        date=(121, 192, 255),         # #79c0ff - constant (light blue)
        account=(210, 168, 255),      # #d2a8ff - entity (purple)
        amount=(126, 231, 135),       # #7ee787 - string-regexp (green) 
        currency=(255, 166, 87),      # #ffa657 - variable (orange)
        string=(165, 214, 255),       # #a5d6ff - string (light blue)
        comment=(139, 148, 158),      # #8b949e - comment (gray)
        keyword=(255, 123, 114),      # #ff7b72 - keyword (red/pink)
        tag=(121, 192, 255),          # #79c0ff - constant (light blue, same as date)
        normal=(230, 237, 243),       # #e6edf3 - text (light gray)
        background=(13, 17, 23)       # #0d1117 - canvas.default (dark)
    ),
    
    # Dracula Theme
    'dracula': ColorScheme(
        name="Dracula",
        date=(139, 233, 253),         # Cyan
        account=(189, 147, 249),      # Purple
        amount=(80, 250, 123),        # Green
        currency=(255, 184, 108),     # Orange
        string=(241, 250, 140),       # Yellow
        comment=(98, 114, 164),       # Comment
        keyword=(255, 121, 198),      # Pink
        tag=(139, 233, 253),          # Cyan (same as date)
        normal=(248, 248, 242),       # Foreground
        background=(40, 42, 54)       # Background
    ),
    
    # One Dark Theme (Atom)
    'one_dark': ColorScheme(
        name="One Dark",
        date=(97, 175, 239),          # Blue
        account=(198, 120, 221),      # Purple
        amount=(152, 195, 121),       # Green
        currency=(209, 154, 102),     # Orange
        string=(224, 108, 117),       # Red
        comment=(92, 99, 112),        # Comment Gray
        keyword=(198, 120, 221),      # Purple
        tag=(97, 175, 239),           # Blue (same as date)
        normal=(171, 178, 191),       # Foreground
        background=(40, 44, 52)       # Background
    ),
    
    # High Contrast Light - For accessibility
    'high_contrast_light': ColorScheme(
        name="High Contrast Light",
        date=(0, 0, 255),             # Pure Blue
        account=(128, 0, 128),        # Purple
        amount=(0, 128, 0),           # Green
        currency=(255, 127, 0),       # Orange
        string=(255, 0, 0),           # Red
        comment=(64, 64, 64),         # Dark Gray
        keyword=(128, 0, 0),          # Dark Red
        tag=(0, 128, 128),            # Dark Cyan
        normal=(0, 0, 0),             # Black
        background=(255, 255, 255)    # White
    ),
    
    # High Contrast Dark - For accessibility  
    'high_contrast_dark': ColorScheme(
        name="High Contrast Dark",
        date=(100, 200, 255),         # Light Blue
        account=(255, 150, 255),      # Light Purple
        amount=(100, 255, 100),       # Light Green
        currency=(255, 200, 100),     # Light Orange
        string=(255, 100, 100),       # Light Red
        comment=(200, 200, 200),      # Light Gray
        keyword=(255, 150, 150),      # Light Pink
        tag=(100, 255, 255),          # Light Cyan
        normal=(255, 255, 255),       # White
        background=(0, 0, 0)          # Black
    )
}


class BeanquickSyntaxHighlighter:
    """Syntax highlighter for Beancount syntax in toga MultilineTextInput."""
    
    def __init__(self, text_view: Any = None, color_scheme: str = 'light_classic'):
        """Initialize the syntax highlighter.
        
        Args:
            text_view: The NSTextView instance to highlight
            color_scheme: Name of the color scheme to use
        """
        self.text_view = text_view
        self.current_scheme_name = color_scheme
        self.current_scheme = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES['light_classic'])
        self._setup_patterns()
    
    def set_color_scheme(self, scheme_name: str):
        """Set the color scheme.
        
        Args:
            scheme_name: Name of the color scheme
        """
        if scheme_name in COLOR_SCHEMES:
            self.current_scheme_name = scheme_name
            self.current_scheme = COLOR_SCHEMES[scheme_name]
        else:
            logger.warning(f"Warning: Color scheme '{scheme_name}' not found. Using default.")
    
    def get_available_schemes(self) -> List[str]:
        """Get list of available color scheme names."""
        return list(COLOR_SCHEMES.keys())
    
    def _setup_patterns(self):
        """Setup regex patterns for Beancount syntax elements."""
        self.patterns = [
            # Date patterns (YYYY-MM-DD)
            (r'\b\d{4}-\d{2}-\d{2}\b', 'date'),
            
            # Account patterns (Assets:Cash, Expenses:Food, etc.)
            # Must start with uppercase letter and contain at least one colon
            (r'\b[A-Z][a-zA-Z0-9-]*:[a-zA-Z0-9:-]*\b', 'account'),
            
            # Amount patterns (123.45, -50.00) - must be preceded by whitespace
            (r'(?<=\s)[-+]?\d+(?:\.\d+)?(?=\s)', 'amount'),
            
            # Currency patterns (USD, EUR, etc.) - must be at end of line or after number
            (r'(?<=\d\s)[A-Z]{3}(?=\s|$)', 'currency'),
            
            # String patterns (quoted strings)
            (r'"[^"]*"', 'string'),
            
            # Comment patterns (lines starting with ;)
            (r';.*$', 'comment'),
            
            # Tag patterns (#tag, #tag-name, #tag_name)
            (r'#[a-zA-Z0-9_-]+', 'tag'),
            
            # Beancount keywords
            (r'\b(txn|open|close|balance|pad|note|document|price|event|custom|plugin|include|option)\b', 'keyword'),
        ]
    
    def get_current_theme(self) -> ColorScheme:
        """Get the current color scheme."""
        return self.current_scheme
    
    def apply_highlighting(self, text: Optional[str] = None):
        """Apply syntax highlighting to the text view.
        
        Args:
            text: Optional text to highlight. If None, uses current text view content.
        """
        if sys.platform != "darwin" or not self.text_view:
            return
        
        try:
            if text is None:
                text = str(self.text_view.string)
            
            if not text:
                return
            
            # Get current theme
            theme = self.get_current_theme()
            
            # Get text storage
            text_storage = self.text_view.textStorage
            if not text_storage:
                return
            
            # Get full range
            full_range = NSRange(0, len(text))
            
            # Begin editing
            text_storage.beginEditing()
            
            # Reset all attributes to normal - use current font
            current_font = self.text_view.font
            if current_font:
                font = current_font
            else:
                # Fallback to system font
                try:
                    font = NSFont.systemFontOfSize_(14)
                except:
                    # If font creation fails, skip highlighting
                    text_storage.endEditing()
                    return
            
            # Get normal color
            normal_color = theme.get_nscolor('normal')
            if not normal_color:
                # Fallback to system text color
                try:
                    normal_color = NSColor.textColor
                except:
                    # If color access fails, skip highlighting
                    text_storage.endEditing()
                    return
            
            text_storage.setAttributes_range_({
                str(NSForegroundColorAttributeName): normal_color,
                str(NSFontAttributeName): font
            }, full_range)
            
            # Apply syntax highlighting using Python regex
            for pattern, token_type in self.patterns:
                nscolor = theme.get_nscolor(token_type)
                if nscolor:  # Only apply if color is available
                    self._highlight_pattern_python(text_storage, text, pattern, nscolor)
            
            # End editing
            text_storage.endEditing()
            
        except Exception as e:
            # Log error but don't crash
            logger.warning(f"Error in syntax highlighting: {e}")
    
    def _highlight_pattern_python(self, text_storage: Any, text: str, pattern: str, color: Any):
        """Apply highlighting for a specific pattern using Python regex.
        
        Args:
            text_storage: NSTextStorage instance
            text: Text to search in
            pattern: Regular expression pattern
            color: NSColor to apply
        """
        if sys.platform != "darwin":
            return
        
        try:
            # Use Python's re module
            regex = re.compile(pattern, re.MULTILINE | re.IGNORECASE)
            
            # Find all matches
            for match in regex.finditer(text):
                start, end = match.span()
                range_obj = NSRange(start, end - start)
                
                # Apply color
                text_storage.addAttribute_value_range_(
                    str(NSForegroundColorAttributeName),
                    color,
                    range_obj
                )
                    
        except Exception as e:
            # Silently ignore regex errors for now
            pass
    
    def set_text_view(self, text_view: Any):
        """Set the text view to highlight.
        
        Args:
            text_view: NSTextView instance
        """
        self.text_view = text_view
    
    def refresh_highlighting(self):
        """Refresh the syntax highlighting with current settings."""
        if self.text_view:
            self.apply_highlighting()
