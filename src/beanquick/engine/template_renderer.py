from __future__ import annotations

import datetime
from typing import Dict, List, Any

from jinja2 import Environment, exceptions

class TemplateRenderer:
    """
    Use Jinja2 engine to render command templates.
    Follow the "merge and override" strategy to build the rendering context.
    """

    def __init__(self):
        """Initialize Jinja2 environment."""
        self.env = Environment(
            trim_blocks=True, 
            lstrip_blocks=True,
        )

    def render(self, template_config: Dict[str, Any], params: List[str | float]) -> str:
        """
        Renders the final Beancount transaction string based on template configuration and user parameters.

        Args:
            template_config: Configuration dictionary for a single command
            params: List of user input parameters.

        Returns:
            The rendered string.
            
        Raises:
            ValueError: When template configuration or rendering fails.
        """
        template_str = template_config.get("template")
        if not template_str:
            raise ValueError("Template configuration error: 'template' field not found.")

        # 1. Extract all user-defined default values
        user_defaults = {
            key: value
            for key, value in template_config.items()
            if key != 'template'
        }

        # 2. Define system built-in variables
        system_vars = {
            'date': datetime.date.today().isoformat(),
            'yesterday': (datetime.date.today() - datetime.timedelta(days=1)).isoformat(),
            'args': params,
        }

        # 3. Merge context, ensuring system variables override user-defined variables with the same name
        final_context = {**user_defaults, **system_vars}

        # 4. Render template and handle possible errors
        try:
            template = self.env.from_string(template_str)
            return template.render(final_context)
        except exceptions.TemplateSyntaxError as e:
            raise ValueError(f"Template syntax error: {e}")
        except exceptions.UndefinedError as e:
            raise ValueError(f"Template rendering error: {e}")
        except Exception as e:
            raise ValueError(f"Unknown error occurred while rendering template: {e}")