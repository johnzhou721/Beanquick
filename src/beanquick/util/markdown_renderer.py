"""
Simple markdown renderer using Mistune library.
"""

import mistune
import logging

logger = logging.getLogger(__name__)


class MarkdownRenderer:
    """Simple markdown to HTML converter using Mistune."""
    
    def __init__(self):
        """Initialize the markdown renderer."""
        # Create custom renderer with header ID generation
        class CustomRenderer(mistune.HTMLRenderer):
            def heading(self, text, level, **attrs):
                """Render heading with ID for anchor navigation."""
                # Generate a URL-friendly ID from header text
                header_id = self._generate_header_id(text)
                return f'<h{level} id="{header_id}">{text}</h{level}>\n'
            
            def _generate_header_id(self, text: str) -> str:
                """Generate a URL-friendly ID from header text."""
                import re
                
                # Remove HTML tags from text
                text = re.sub(r'<[^>]+>', '', text)
                
                # Convert to lowercase
                text = text.lower()
                
                # For non-Latin characters (like Chinese), keep them intact
                # Just replace spaces with hyphens and remove some punctuation
                slug = re.sub(r'[\s]+', '-', text)
                # Remove some problematic characters for URLs but keep Unicode chars
                slug = re.sub(r'[^\w\s\u4e00-\u9fff\u3400-\u4dbf-]', '', slug)
                slug = re.sub(r'[\s_]+', '-', slug)
                slug = slug.strip('-')
                
                return slug if slug else 'header'
        
        # Create mistune markdown parser with custom renderer and plugins
        renderer = CustomRenderer()
        self.markdown = mistune.create_markdown(
            renderer=renderer,
            plugins=['strikethrough', 'table', 'task_lists']
        )
        
        # Minimal CSS based on GitHub markdown styles
        self.css = """
        <style>
        :root {
            --base-size-4: 0.25rem;
            --base-size-8: 0.5rem;
            --base-size-16: 1rem;
            --base-size-24: 1.5rem;
            --base-text-weight-normal: 400;
            --base-text-weight-semibold: 600;
            --fontStack-monospace: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
        }
        
        @media (prefers-color-scheme: dark) {
            :root {
                --fgColor-default: #f0f6fc;
                --fgColor-muted: #9198a1;
                --fgColor-accent: #4493f8;
                --bgColor-default: #0d1117;
                --bgColor-muted: #151b23;
                --bgColor-neutral-muted: #656c7633;
                --borderColor-default: #3d444d;
                --borderColor-muted: #3d444db3;
                --focus-outlineColor: #1f6feb;
            }
        }
        
        @media (prefers-color-scheme: light) {
            :root {
                --fgColor-default: #1f2328;
                --fgColor-muted: #59636e;
                --fgColor-accent: #0969da;
                --bgColor-default: #ffffff;
                --bgColor-muted: #f6f8fa;
                --bgColor-neutral-muted: #818b981f;
                --borderColor-default: #d1d9e0;
                --borderColor-muted: #d1d9e0b3;
                --focus-outlineColor: #0969da;
            }
        }
        
        body {
            margin: 0;
            color: var(--fgColor-default);
            background-color: var(--bgColor-default);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
            font-size: 16px;
            line-height: 1.5;
            word-wrap: break-word;
            padding: 20px;
            max-width: 100%;
        }
        
        h1, h2, h3, h4, h5, h6 {
            margin-top: var(--base-size-24);
            margin-bottom: var(--base-size-16);
            font-weight: var(--base-text-weight-semibold);
            line-height: 1.25;
        }
        
        h1 {
            padding-bottom: .3em;
            font-size: 2em;
            border-bottom: 1px solid var(--borderColor-muted);
        }
        
        h2 {
            padding-bottom: .3em;
            font-size: 1.5em;
            border-bottom: 1px solid var(--borderColor-muted);
        }
        
        h3 { font-size: 1.25em; }
        h4 { font-size: 1em; }
        h5 { font-size: .875em; }
        h6 { font-size: .85em; color: var(--fgColor-muted); }
        
        p {
            margin-top: 0;
            margin-bottom: var(--base-size-16);
        }
        
        a {
            color: var(--fgColor-accent);
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
        
        blockquote {
            margin: 0 0 var(--base-size-16) 0;
            padding: 0 1em;
            color: var(--fgColor-muted);
            border-left: .25em solid var(--borderColor-default);
        }
        
        code, tt {
            padding: .2em .4em;
            margin: 0;
            font-size: 85%;
            font-family: var(--fontStack-monospace);
            background-color: var(--bgColor-neutral-muted);
            border-radius: 6px;
        }
        
        pre {
            padding: var(--base-size-16);
            margin-bottom: var(--base-size-16);
            overflow: auto;
            font-size: 85%;
            line-height: 1.45;
            font-family: var(--fontStack-monospace);
            background-color: var(--bgColor-muted);
            border-radius: 6px;
        }
        
        pre code {
            padding: 0;
            margin: 0;
            background-color: transparent;
            border: 0;
        }
        
        img {
            max-width: 100%;
            box-sizing: content-box;
        }
        
        table {
            border-spacing: 0;
            border-collapse: collapse;
            width: 100%;
            margin-bottom: var(--base-size-16);
        }
        
        th, td {
            padding: 6px 13px;
            border: 1px solid var(--borderColor-default);
        }
        
        th {
            font-weight: var(--base-text-weight-semibold);
        }
        
        tr:nth-child(2n) {
            background-color: var(--bgColor-muted);
        }
        
        ul, ol {
            margin-top: 0;
            margin-bottom: var(--base-size-16);
            padding-left: 2em;
        }
        </style>
        """
    
    def markdown_to_html(self, markdown_text: str) -> str:
        """Convert markdown text to HTML document.
        
        Args:
            markdown_text: The markdown text to convert
            
        Returns:
            Complete HTML document string
        """
        try:
            # Convert markdown to HTML
            html_content = self.markdown(markdown_text)
            
            # Wrap in HTML document
            return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {self.css}
    <script>
    // Anchor navigation functionality
    document.addEventListener('DOMContentLoaded', function() {{
        // Global function for anchor navigation
        window.scrollToAnchor = function(targetId) {{
            console.log('Attempting to scroll to:', targetId);
            var target = document.getElementById(targetId);
            if (target) {{
                console.log('Target found:', target);
                target.scrollIntoView({{
                    behavior: 'smooth',
                    block: 'start',
                    inline: 'nearest'
                }});
                
                // Add visual highlight for a moment
                target.style.transition = 'background-color 0.3s ease';
                var originalBg = target.style.backgroundColor;
                target.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                
                setTimeout(function() {{
                    target.style.backgroundColor = originalBg;
                }}, 1000);
            }} else {{
                console.warn('Target not found for ID:', targetId);
                // Try decoding the targetId in case it contains encoded characters
                var decodedId = decodeURIComponent(targetId);
                if (decodedId !== targetId) {{
                    console.log('Trying with decoded ID:', decodedId);
                    target = document.getElementById(decodedId);
                    if (target) {{
                        console.log('Target found with decoded ID');
                        target.scrollIntoView({{
                            behavior: 'smooth',
                            block: 'start',
                            inline: 'nearest'
                        }});
                        
                        // Add visual highlight for a moment
                        target.style.transition = 'background-color 0.3s ease';
                        var originalBg = target.style.backgroundColor;
                        target.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                        
                        setTimeout(function() {{
                            target.style.backgroundColor = originalBg;
                        }}, 1000);
                    }}
                }}
                
                // If still not found, try a case-insensitive search
                if (!target) {{
                    console.log('Trying case-insensitive search for ID');
                    var allElements = document.querySelectorAll('[id]');
                    for (var i = 0; i < allElements.length; i++) {{
                        if (allElements[i].id.toLowerCase() === targetId.toLowerCase()) {{
                            target = allElements[i];
                            console.log('Found element with case-insensitive match:', target.id);
                            target.scrollIntoView({{
                                behavior: 'smooth',
                                block: 'start',
                                inline: 'nearest'
                            }});
                            
                            // Add visual highlight for a moment
                            target.style.transition = 'background-color 0.3s ease';
                            var originalBg = target.style.backgroundColor;
                            target.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                            
                            setTimeout(function() {{
                                target.style.backgroundColor = originalBg;
                            }}, 1000);
                            break;
                        }}
                    }}
                }}
            }}
        }};
        
        // Set up click handlers for all anchor links
        var anchorLinks = document.querySelectorAll('a[href^="#"]');
        anchorLinks.forEach(function(link) {{
            link.addEventListener('click', function(e) {{
                e.preventDefault();
                var targetId = this.getAttribute('href').substring(1);
                window.scrollToAnchor(targetId);
            }});
        }});
        
        // Debug: Log all IDs in the document
        console.log('All IDs in document:');
        var allIds = document.querySelectorAll('[id]');
        allIds.forEach(function(el) {{
            console.log(el.id);
        }});
    }});
    </script>
</head>
<body>
{html_content}
</body>
</html>"""
            
        except Exception as e:
            logger.error(f"Error converting markdown: {e}")
            return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">{self.css}</head>
<body>
    <h1>Error</h1>
    <p>Failed to convert markdown: {str(e)}</p>
</body>
</html>"""
