"""
Beanquick Configuration Box
"""
from __future__ import annotations

import sys
from typing import Callable, Dict, Any, Optional, NamedTuple
import logging

import toga
from toga.style import Pack
from toga.style.pack import ROW, COLUMN, MONOSPACE  # type: ignore
from toga.constants import DODGERBLUE

from beanquick.ui.suggestion_popup import SuggestionPopup
from beanquick.services.account_completer import AccountCompleter


WIDGET_SPACING = 5

class KeyValueLine(NamedTuple):
    """Key-value pair for configuration lines."""
    key_input: toga.TextInput
    value_input: toga.TextInput

    @property
    def key_text(self) -> str:
        """Get the trimmed value"""
        return self.key_input.value.strip() if self.key_input.value else ""

    @property
    def value_text(self) -> str:
        """Get the trimmed value"""
        return self.value_input.value.strip() if self.value_input.value else ""
    
    @property
    def has_data(self) -> bool:
        """Check if either key or value has data."""
        return bool(self.key_text) or bool(self.value_text)
    
    @property
    def is_complete(self) -> bool:
        """Check if both key and value have data."""
        return bool(self.key_text) and bool(self.value_text)

logger = logging.getLogger(__name__)

class ConfigBox(toga.Box):
    def __init__(self,
                 config: dict[str, Any] | None,
                 on_save: Callable[[dict], None],
                 on_cancel: Callable[[], None],
                 account_completer: AccountCompleter | None,
                 app: toga.App,
                 **kwargs):
        super().__init__(
            style=Pack(direction=COLUMN, flex=1, margin=10),
            **kwargs
        )

        self.config = config.copy() if config else self._get_default_config()
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.account_completer = account_completer
        self.app = app
        
        # Store widgets for easy access
        self.config_widgets = {}
        self._current_config_widget = None

        # Create completion timers dictionary
        self.completion_timers = {}
        self._setting_suggestion: bool = False

        self._create_ui()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure."""
        return {
            "defaults": {
                "currency": "USD",
                "flag": "*",
                "narration": "Transaction"
            },
            "aliases": {},
            "command_templates": {}
        }
    
    def _create_ui(self):
        """Create the UI components."""
        
        # Create option container with categorized tabs
        self.option_container = toga.OptionContainer(
            style=Pack(flex=1, margin_bottom=10)
        )
        
        # Add config tabs
        self._create_defaults_tab()
        self._create_aliases_tab()
        self._create_templates_tab()
        
        # Create button row
        button_box = self._create_button_row()
        
        # Assemble main layout
        self.add(self.option_container)
        self.add(button_box)

    def _create_defaults_tab(self):
        """Create the defaults configuration tab."""
        defaults_box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        
        # Title
        title_label = toga.Label(
            "Default Settings",
            style=Pack(font_size=16, font_weight="bold", margin_bottom=10)
        )
        defaults_box.add(title_label)
        
        # Description
        desc_label = toga.Label(
            "Configure default values for new transactions:",
            style=Pack(margin_bottom=15, color="#666666")
        )
        defaults_box.add(desc_label)
        
        defaults_config = self.config.get("defaults", {})
        
        # Currency setting
        currency_box = self._create_labeled_input(
            "Default Currency:",
            defaults_config.get("currency", "USD"),
            "currency",
            placeholder="e.g., USD, EUR, CNY"
        )
        defaults_box.add(currency_box)
        
        # Flag setting
        flag_box = self._create_labeled_input(
            "Default Flag:",
            defaults_config.get("flag", "*"),
            "flag",
            placeholder="* for cleared, ! for pending"
        )
        defaults_box.add(flag_box)
        
        # Default narration
        narration_box = self._create_labeled_input(
            "Default Narration:",
            defaults_config.get("narration", "Transaction"),
            "narration",
            placeholder="e.g., Transaction"
        )
        defaults_box.add(narration_box)
        
        # Add spacer
        defaults_box.add(toga.Box(style=Pack(flex=1)))

        self.option_container.content.append("Defaults", defaults_box)

    def _create_aliases_tab(self):
        """Create the aliases configuration tab."""
        aliases_box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        
        # Title and description
        title_label = toga.Label(
            "Account Aliases",
            style=Pack(font_size=16, font_weight="bold", margin_bottom=10)
        )
        aliases_box.add(title_label)
        
        desc_label = toga.Label(
            "Create shortcuts for your account names. Use short aliases in Beanquick entries:",
            style=Pack(margin_bottom=15, color="#666666")
        )
        aliases_box.add(desc_label)
        
        # Create scrollable container for aliases
        scroll_container = toga.ScrollContainer(
            style=Pack(flex=1, margin_bottom=10)
        )
        
        aliases_content = toga.Box(style=Pack(direction=COLUMN, margin=WIDGET_SPACING))
        
        # Add existing aliases
        aliases_config = self.config.get("aliases", {})
        for alias, account in aliases_config.items():
            alias_row = self._create_alias_row(alias, account)
            aliases_content.add(alias_row)
        
        # Add empty row for new alias
        empty_row = self._create_alias_row("", "")
        aliases_content.add(empty_row)
        
        scroll_container.content = aliases_content
        aliases_box.add(scroll_container)
        
        # Add alias button
        add_button = toga.Button(
            "Add New Alias",
            on_press=self._add_new_alias_row,
        )
        aliases_box.add(add_button)

        # Create suggestion popup for account completion
        self.suggestion_popup = SuggestionPopup(
            aliases_content,
            self._on_suggestion_selected
        )

        self.option_container.content.append("Aliases", aliases_box)

    def _create_templates_tab(self):
        """Create the templates configuration tab."""
        templates_box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        
        # Title and description
        title_label = toga.Label(
            "Templates",
            style=Pack(font_size=16, font_weight="bold", margin_bottom=10)
        )
        templates_box.add(title_label)
        
        desc_label = toga.Label(
            "Define reusable templates for quick entry:",
            style=Pack(margin_bottom=15, color="#666666")
        )
        templates_box.add(desc_label)
        
        # Create scrollable container for templates
        scroll_container = toga.ScrollContainer(
            style=Pack(flex=1, margin_bottom=10)
        )

        templates_content = toga.Box(style=Pack(direction=COLUMN, margin=WIDGET_SPACING))

        # Add existing templates
        templates_config = self.config.get("command_templates", {})
        for template_name, template_value in templates_config.items():
            template_row = self._create_template_row(template_name, template_value)
            templates_content.add(template_row)

        # Add empty row for new template
        empty_row = self._create_template_row("", {})
        templates_content.add(empty_row)

        scroll_container.content = templates_content
        templates_box.add(scroll_container)

        # Add template button
        add_button = toga.Button(
            "Add New Template",
            on_press=self._add_new_template_row,
        )

        templates_box.add(add_button)

        self.option_container.content.append("Templates", templates_box)

    def _create_labeled_input(self, label_text: str, value: str, key: str, placeholder: str = "") -> toga.Box:
        """Create a labeled input widget."""
        container = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        
        label = toga.Label(
            label_text,
            style=Pack(width=200, text_align="right", margin_right=10)
        )
        
        input_widget = toga.TextInput(
            value=value,
            placeholder=placeholder,
            style=Pack(flex=1)
        )
        
        # Store widget reference
        if "defaults" not in self.config_widgets:
            self.config_widgets["defaults"] = {}
        self.config_widgets["defaults"][key] = input_widget
        
        container.add(label)
        container.add(input_widget)
        
        return container

    def _create_alias_row(self, alias: str, account: str) -> toga.Box:
        """Create a row for alias configuration."""
        row_box = toga.Box(style=Pack(direction=COLUMN))
        
        row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        
        # Remove button
        remove_button = toga.Button(
            "⌦",
            on_press=lambda widget, r=row_box: self._remove_row(r),
            style=Pack(width=24, margin_right=WIDGET_SPACING)
        )

        alias_input = toga.TextInput(
            value=alias,
            placeholder="Alias (e.g., cash)",
            style=Pack(flex=1)
        )
        
        account_input = toga.TextInput(
            value=account,
            placeholder="Full Account Name (e.g., Assets:Cash)",
            on_change=self._on_alias_account_input_change,
            on_lose_focus=self._on_alias_account_input_lose_focus,
            on_confirm=self._on_alias_account_input_confirm,
            style=Pack(flex=3, margin_left=WIDGET_SPACING)
        )
        
        # Store widget references
        if "aliases" not in self.config_widgets:
            self.config_widgets["aliases"] = []
        
        self.config_widgets["aliases"].append({
            "row": row_box,
            "alias": alias_input,
            "account": account_input
        })
        
        row.add(remove_button)
        row.add(alias_input)
        row.add(account_input)

        row_box.add(row)
        return row_box
    
    def _on_alias_account_input_confirm(self, widget):
        """Handle confirmation of the account input field in alias rows."""
        if self.suggestion_popup and self.suggestion_popup.is_visible:
            self.suggestion_popup.select_current()

    def _on_alias_account_input_lose_focus(self, widget):
        """Handle losing focus on the account input field in alias rows."""
        if self.suggestion_popup and self.suggestion_popup.is_visible:
            self.suggestion_popup.hide()

    def _on_alias_account_input_change(self, widget, **kwargs):
        """Handle changes to the account input field in alias rows."""
        if self._setting_suggestion:
            return
        # Find the row associated with the changed widget
        for alias_config in self.config_widgets.get("aliases", []):
            if alias_config["account"] == widget:
                self._current_config_widget = alias_config
                # Check for special navigation characters (if keyboard events aren't available)
                value = widget.value
                if value and len(value) > 0:
                    last_char = value[-1]

                    if self.suggestion_popup and self.suggestion_popup.is_visible:
                        # Handle special navigation (this is a fallback approach)
                        if last_char == ',':  # Comma key
                            self._setting_suggestion = True
                            try:
                                # Remove the comma character
                                widget.value = value[:-1]
                                self.suggestion_popup.navigate_up()
                            finally:
                                self._setting_suggestion = False
                            return
                        
                        if last_char == '.':  # Period key
                            self._setting_suggestion = True
                            try:
                                # Remove the period character
                                widget.value = value[:-1]
                                self.suggestion_popup.navigate_down()
                            finally:
                                self._setting_suggestion = False
                            return

                        if last_char == ' ':  # Space key
                            self._setting_suggestion = True
                            try:
                                # Remove the space character
                                widget.value = value[:-1]
                                self.suggestion_popup.select_current()
                            finally:
                                self._setting_suggestion = False
                            return
                
                # Handle autocompletion with debouncing
                self._debounced_account_completion(widget)
                
    
    def _debounced_account_completion(self, widget: toga.TextInput):
        """Handle debounced account completion."""
        # Create a unique key for this widget's completion timer
        widget_id = id(widget)
        
        # Cancel any existing timer for this widget
        if widget_id in self.completion_timers and self.completion_timers[widget_id]:
            self.completion_timers[widget_id].cancel()
        
        # Start new debounced timer
        # schedule_delayed_callback
        self.completion_timers[widget_id] = self.app.loop.call_later(
            0.3,  # 300ms delay
            lambda: self._debounced_account_completion_handler(widget)
        )
    
    def _debounced_account_completion_handler(self, widget):
        """Actual completion handling logic after debouncing."""
        try:
            # Get the query and find the suggestion popup
            query = widget.value
            
            if not self.suggestion_popup:
                return
            
            if not query or not query.strip():
                self.suggestion_popup.hide()
                return
            
            # Get suggestions directly (no async needed)
            if self.account_completer:
                suggestions = self.account_completer.get_suggestions(query.strip())
                if suggestions:
                    # Scroll to bring the current input to the top, accounting for popup space
                    if self._current_config_widget:
                        row_box = self._current_config_widget["row"]
                        self.suggestion_popup.parent_container = row_box
                        self.suggestion_popup.show_suggestions(suggestions)
                else:
                    self.suggestion_popup.hide()

        except Exception as e:
            logger.debug(f"Error in debounced completion: {e}")

    def _on_suggestion_selected(self, suggestion: str):
        """Handle selection of a suggestion from the popup."""
        self._setting_suggestion = True
        try:
            if self._current_config_widget:
                self._current_config_widget["account"].value = suggestion
        finally:
            self._setting_suggestion = False

    def _create_template_row(self, template_name: str, template_values: dict[str, str]) -> toga.Box:
        """Create a row for command template configuration."""
        row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        
        # Remove button
        remove_button = toga.Button(
            "⌦",
            on_press=lambda widget, r=row: self._remove_row(r),
            style=Pack(width=24, margin_right=WIDGET_SPACING)
        )

        template_name_input = toga.TextInput(
            value=template_name,
            placeholder="Template Name (e.g., coffee)",
            style=Pack(width=150, margin_right=WIDGET_SPACING)
        )

        user_defaults = {
            key: value
            for key, value in template_values.items()
            if key != 'template'  # 'template' 字段本身不是一个变量
        }
        
        # Create a box for the template value inputs
        template_box = toga.Box(style=Pack(flex=1, direction=COLUMN))

        # Create a box for user-defined variables
        user_defaults_box = toga.Box(style=Pack(direction=COLUMN))
        user_defaults_lines = []
        for key, value in user_defaults.items():
            line_box, line = self._create_user_default_row(key, value, row)
            user_defaults_box.add(line_box)
            user_defaults_lines.append(line)
        
        # Create an empty row for new user-defined variables
        new_var_row, new_line = self._create_user_default_row(row=row)
        user_defaults_box.add(new_var_row)
        user_defaults_lines.append(new_line)

        template_box.add(user_defaults_box)

        # Create a multiline text input for the template value
        jinja_template_input = toga.MultilineTextInput(
            value=template_values.get("template", ""),
            placeholder="Template Value (e.g., {{date}} Buy coffee for {{args[0]}})",
            style=Pack(flex=1, font_family=MONOSPACE)
        )
        if sys.platform == "darwin":
            jinja_template_input._impl.native_text.setAutomaticQuoteSubstitutionEnabled_(False)

        template_box.add(jinja_template_input)
        
        # Store widget references
        if "command_templates" not in self.config_widgets:
            self.config_widgets["command_templates"] = []
        
        self.config_widgets["command_templates"].append({
            "row": row,
            "template_name": template_name_input,
            "jinja_template": jinja_template_input,
            "user_defaults": user_defaults_box,
            "user_defaults_lines": user_defaults_lines
        })
        
        row.add(remove_button)
        row.add(template_name_input)
        row.add(template_box)
        
        return row
    
    def _create_user_default_row(self, key: str = "", value: str = "", row: Optional[toga.Box] = None) -> tuple:
        """Add a new user-defined variable row."""
        line_box = toga.Box(style=Pack(flex=1, direction=ROW, margin_bottom=5))
        key_input = toga.TextInput(
            value=key,
            placeholder=f"Variable Name",
            style=Pack(flex=1),
            on_change=lambda widget, row=row: self._on_user_default_change(widget, row),
        )
        value_input = toga.TextInput(
            value=value,
            placeholder=f"Default Value",
            style=Pack(flex=1),
            on_change=lambda widget, row=row: self._on_user_default_change(widget, row),
        )
        
        line_box.add(key_input)
        line_box.add(value_input)

        line = KeyValueLine(key_input, value_input)

        return (line_box, line)
        
    def _on_user_default_change(self, widget, row):
        """Handle changes to user-defined variable inputs."""
        self._manage_key_value_lines(widget, row)

    def _manage_key_value_lines(self, widget: toga.TextInput, row):
        """Manage dynamic addition/removal of key-value lines."""
        for command_template in self.config_widgets.get("command_templates", []):
            if command_template["row"] == row:
                # Find the user defaults box
                user_defaults_box = command_template["user_defaults"]
                user_defaults_lines = command_template["user_defaults_lines"]
                
                # Remove empty lines (not the last line)
                for i in range(len(user_defaults_lines) - 1):
                    line = user_defaults_lines[i]
                    if not line.has_data:
                        user_defaults_box.remove(line.key_input.parent)
                        user_defaults_lines.remove(line)
                
                # Check if we need to add a new line
                if len(user_defaults_lines) > 0:
                    last_line = user_defaults_lines[-1]
                    if last_line.is_complete:
                        new_line_box, new_line = self._create_user_default_row(row=row)
                        user_defaults_box.add(new_line_box)
                        user_defaults_lines.append(new_line)

    def _add_new_alias_row(self, widget):
        """Add a new empty alias row."""
        try:
            # Find the aliases tab content
            aliases_tab = self.option_container.current_tab
            if aliases_tab:
                # Find the scroll container
                scroll_container = None
                for child in aliases_tab.content.children:
                    if isinstance(child, toga.ScrollContainer):
                        scroll_container = child
                        break
                
                if scroll_container:
                    new_row = self._create_alias_row("", "")
                    scroll_container.content.add(new_row)
        except Exception as e:
            logger.error(f"Error adding new alias row: {e}")

    def _add_new_template_row(self, widget):
        """Add a new empty template row."""
        try:
            # Find the templates tab content
            templates_tab = self.option_container.current_tab
            
            if templates_tab:
                # Find the scroll container
                scroll_container = None
                for child in templates_tab.content.children:
                    if isinstance(child, toga.ScrollContainer):
                        scroll_container = child
                        break
                
                if scroll_container:
                    new_row = self._create_template_row("", {})
                    scroll_container.content.add(new_row)
        except Exception as e:
            logger.error(f"Error adding new template row: {e}")

    def _remove_row(self, row: toga.Box):
        """Remove a configuration row."""
        try:
            # Find and remove from config_widgets
            for category in ["aliases", "command_templates"]:
                if category in self.config_widgets:
                    self.config_widgets[category] = [
                        item for item in self.config_widgets[category]
                        if item["row"] != row
                    ]
            
            # Remove from UI
            if row.parent:
                row.parent.remove(row)
        except Exception as e:
            logger.error(f"Error removing row: {e}")

    def _create_button_row(self):
        """Create the footer for the config box."""
        save_button = toga.Button(
            "Save",
            on_press=self._on_save,
            style=Pack(background_color=DODGERBLUE, color="white")
        )

        cancel_button = toga.Button(
            "Cancel",
            on_press=self._on_cancel,
            style=Pack(margin_right=WIDGET_SPACING)
        )

        footer = toga.Box(
            style=Pack(direction=ROW),
            children=[
                toga.Box(style=Pack(flex=1)),
                cancel_button,
                save_button,
            ]
        )
        return footer

    def _collect_config_data(self) -> Dict[str, Any]:
        """Collect configuration data from all widgets."""
        config = {}
        
        try:
            # Collect defaults
            if "defaults" in self.config_widgets:
                config["defaults"] = {}
                for key, widget in self.config_widgets["defaults"].items():
                    config["defaults"][key] = widget.value.strip()
            
            # Collect aliases
            config["aliases"] = {}
            if "aliases" in self.config_widgets:
                for item in self.config_widgets["aliases"]:
                    alias = item["alias"].value.strip()
                    account = item["account"].value.strip()
                    if alias and account:  # Only add non-empty pairs
                        config["aliases"][alias] = account
            
            # Collect templates
            config["command_templates"] = {}
            if "command_templates" in self.config_widgets:
                for item in self.config_widgets["command_templates"]:
                    template_name = item["template_name"].value.strip()
                    jinja_template = item["jinja_template"].value.strip()
                    user_defaults_lines = item["user_defaults_lines"]
                    template_config = {}
                    if template_name and jinja_template:  # Only add non-empty pairs
                        template_config["template"] = jinja_template
                        if user_defaults_lines:
                            for line in user_defaults_lines:
                                if line.is_complete:
                                    template_config[line.key_text] = line.value_text
                    if template_config:
                        config["command_templates"][template_name] = template_config
            return config
            
        except Exception as e:
            logger.error(f"Error collecting config data: {e}")
            return self.config  # Return original config if collection fails

    def _validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate the collected configuration."""
        try:
            # Validate defaults
            defaults = config.get("defaults", {})
            
            # # Check currency format (should be 3 letters)
            # currency = defaults.get("currency", "").strip()
            # if currency and (len(currency) != 3 or not currency.isalpha()):
            #     return False, "Currency should be a 3-letter code (e.g., USD, EUR)"
            
            # Check flag format
            flag = defaults.get("flag", "").strip()
            if flag and flag not in ["*", "!"]:
                return False, "Flag should be either '*' (cleared) or '!' (pending)"
            
            # Validate aliases (check for duplicate aliases)
            aliases = config.get("aliases", {})
            alias_names = list(aliases.keys())
            if len(alias_names) != len(set(alias_names)):
                return False, "Duplicate alias names found"
            
            # Validate account names (basic format check)
            for alias, account in aliases.items():
                if account and not account.replace(":", "").replace("-", "").replace("_", "").replace(" ", "").isalnum():
                    return False, f"Invalid account name format: {account}"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _on_save(self, widget):
        """Handle save button press."""
        try:
            # Collect data from widgets
            new_config = self._collect_config_data()
            
            # Validate configuration
            is_valid, error_message = self._validate_config(new_config)
            if not is_valid:
                # TODO: Show error dialog when available in Toga
                logger.error(f"Configuration validation failed: {error_message}")
                return
            
            # Call the save callback
            if self.on_save:
                self.on_save(new_config)
                
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def _on_cancel(self, widget):
        """Handle cancel button press."""
        if self.on_cancel:
            self.on_cancel()

    def refresh_config(self, config: Dict[str, Any]):
        """Refresh the UI with new configuration data."""
        self.config = config.copy() if config else self._get_default_config()
        
        # Clear existing widgets
        self.config_widgets.clear()
        
        # Recreate UI
        self.clear()
        self._create_ui()