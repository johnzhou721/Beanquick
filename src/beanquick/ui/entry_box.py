from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import logging
from typing import Any, TYPE_CHECKING
import sys

import toga
from toga.style import Pack
from toga.style.pack import ROW, COLUMN  # type: ignore

from beanquick.ui.base_entry_box import BaseEntryBox
from beanquick.services.directive_factory import DirectiveFactory
from beanquick.ui.forms.base_form import BaseDirectiveForm
from beanquick.ui.base_entry_box import EntryMode
from beanquick.services.beanquick_integration import get_beanquick_integration, BeanquickResult

if TYPE_CHECKING:
    from beanquick.app import Beanquick

logger = logging.getLogger(__name__)

LARGE_MARGIN = 20

class EntryBox(BaseEntryBox):
    def __init__(self, app_instance: Beanquick, initial_directive_type="transaction", **kwargs: Any):
        """A entry box widget for beancount bookkeeping.
        """
        # Store directive state
        self.directive_forms: dict[str, BaseDirectiveForm] = {}
        self.current_directive_type = initial_directive_type
        self.current_form: BaseDirectiveForm | None = None
        self.directive_selector: toga.Selection | None = None
        self.form_container: toga.Box | None = None

        self._beanquick_config_box: toga.Box | None = None

        super().__init__(app_instance, **kwargs)

        # Beanquick integration
        self._beanquick_integration = get_beanquick_integration(self.app)
        self._last_beanquick_result: list[BeanquickResult] = []
    
    def _create_entry_header(self, mode: EntryMode | None = None):
        """Create the header with directive type selector."""        
        header_box = toga.Box(
            style=Pack(direction=ROW, margin_bottom=10),
        )

        if mode == EntryMode.QUICK:
            header_title = toga.Label(
                "Quick Entry", 
                style=Pack(font_size=12, font_weight="bold")
            )
            
            header_box.add(header_title)
            header_box.add(toga.Box(style=Pack(flex=1)))  # Spacer
        else:
            header_title = toga.Label(
                "New Entry", 
                style=Pack(font_size=12, font_weight="bold")
            )
            header_box.add(header_title)

            # Add directive type selector for normal mode
            if mode == EntryMode.NORMAL:
                # Create directive type selector
                directive_display_names = DirectiveFactory.get_directive_display_names()
                self.directive_selector = toga.Selection(
                    items=directive_display_names,
                    style=Pack(width=150),
                    on_change=self._on_directive_type_changed
                )
                
                # Set initial selection
                try:
                    initial_metadata = DirectiveFactory.get_directive_metadata(self.current_directive_type)
                    self.directive_selector.value = initial_metadata.display_name  # type: ignore
                except (ValueError, AttributeError):
                    # Fallback to first option if initial type is invalid
                    if directive_display_names:
                        self.directive_selector.value = directive_display_names[0]  # type: ignore
                        self.current_directive_type = DirectiveFactory.get_directive_type_by_display_name(directive_display_names[0])

                spacer = toga.Box(style=Pack(flex=1))
                header_box.add(spacer)
                header_box.add(self.directive_selector)

        return header_box

    def _create_entry_form(self, mode: EntryMode | None = None):
        """Create the form container and initial form."""
        # Create a container that will hold the current form
        self.form_container = toga.Box(
            style=Pack(flex=1, direction=COLUMN),
        )
        
        # Load the initial form
        self._load_entry_form(mode)
        
        return self.form_container

    def _load_entry_form(self, mode: EntryMode | None):
        """Load the entry form based on the current mode."""
        if mode == EntryMode.QUICK:
            self._switch_to_quick_entry()
        else:
            self._switch_directive_type(self.current_directive_type)

    def _on_directive_type_changed(self, widget, **kwargs):
        """Handle directive type selection change."""
        if not widget.value:
            return
        
        try:
            # Get the directive type from the display name
            new_directive_type = DirectiveFactory.get_directive_type_by_display_name(widget.value)
            
            if new_directive_type != self.current_directive_type:
                logger.debug(f"Switching directive type from {self.current_directive_type} to {new_directive_type}")
                self._switch_directive_type(new_directive_type)
                
        except ValueError as e:
            logger.error(f"Error switching directive type: {e}")
    
    def _switch_directive_type(self, directive_type: str):
        """Switch to a different directive type."""
        if not DirectiveFactory.is_directive_supported(directive_type):
            logger.error(f"Unsupported directive type: {directive_type}")
            return
        
        # Get or create the form for this directive type
        if directive_type not in self.directive_forms:
            logger.debug(f"Creating new form for directive type: {directive_type}")
            self.directive_forms[directive_type] = DirectiveFactory.create_form(
                directive_type,
                on_change=self._on_entry_changed,
                account_completer=getattr(self, 'account_completer', None),
                completion_timers=getattr(self, '_completion_timers', {}),
                app=self.app,
            )
        
        # Update current references
        self.current_directive_type = directive_type
        self.current_form = self.directive_forms[directive_type]
        
        # Clear the form container and add the new form
        if self.form_container:
            self.form_container.clear()
            form_widget = self.current_form.create_form_widget()
            self.form_container.add(form_widget)

        # Focus the first input field
        self.current_form.focus_first_input()

        # Update window title
        metadata = DirectiveFactory.get_directive_metadata(directive_type)
        self.title = f"New {metadata.display_name}"
        
        # Update preview
        self._update_preview()
        
        logger.debug(f"Switched to directive type: {directive_type}")

    def _switch_to_quick_entry(self):
        """Create the quick entry form."""
        self.quick_text_input = toga.MultilineTextInput(
            style=Pack(flex=1),
            placeholder="Enter Beanquick syntax (e.g., '25 from:cash to:food'), for more info see the help.",
            on_change=self._on_quick_entry_changed
        )

        if sys.platform == "darwin":
            self.quick_text_input._impl.native_text.setAutomaticQuoteSubstitutionEnabled_(False)

        if self.form_container:
            self.form_container.clear()
            self.form_container.add(self.quick_text_input)

        self.quick_text_input.focus()

        # Update preview
        self._update_preview()

    def _on_quick_entry_changed(self, widget, **kwargs):
        """Handle changes in the quick entry text input with comprehensive error handling."""
        # Avoid recursive updates during form clearing
        if getattr(self, '_clearing_form', False):
            return
        
        try:
            # Get the current input text safely
            input_text = getattr(widget, 'value', '') or ""
            
            # Process Beanquick input
            self._process_beanquick_input(input_text)
            
            # Always call the parent handler to update preview
            self._on_entry_changed(widget, **kwargs)
            
        except Exception as e:
            logger.error(f"Error in quick entry changed handler: {e}", exc_info=True)
            # Don't crash the UI - just log the error
            self._last_beanquick_result = [BeanquickResult(
                success=False,
                error_message=f"Handler error: {e}",
                error_type="handler_error"
            )]

    def _process_beanquick_input(self, input_text: str):
        """Safely process Beanquick input with comprehensive error handling.
        
        Args:
            input_text: The Beanquick input text to process.
        """
        try:
            # Check Beanquick integration health
            if not hasattr(self, '_beanquick_integration') or not self._beanquick_integration:
                self._last_beanquick_result = [BeanquickResult(
                    success=False,
                    error_message="Beanquick integration not available",
                    error_type="integration_error",
                    suggestions=["Restart the application", "Check Beanquick installation"]
                )]
                return
            
            # Parse the Beanquick input
            results = self._beanquick_integration.parse_beanquick_multiline(input_text)
            self._last_beanquick_result = results
            
        except Exception as e:
            # Fallback error handling - should not happen with our robust integration
            logger.error(f"Unexpected error processing Beanquick input: {e}", exc_info=True)
            self._last_beanquick_result = [BeanquickResult(
                success=False,
                error_message=f"Unexpected processing error: {e}",
                error_type="unexpected_error",
                suggestions=["Try restarting the application", "Check the input for special characters"]
            )]

    def _build_entry_dict(self) -> dict[str, Any]:
        """Build a dictionary from current form data for serialization."""
        if not self.current_form:
            raise ValueError("No form selected")
        
        return self.current_form.build_directive_dict()
    
    def _build_quick_entry_output(self) -> str:
        """Build the output string from all Beanquick results."""
        if not self._last_beanquick_result:
            return ""
        
        outputs = []
        for result in self._last_beanquick_result:
            if result.success and result.beancount_output:
                outputs.append(result.beancount_output)
        
        return "\n".join(outputs)
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp for metadata.
        
        Returns:
            ISO format timestamp string
        """
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _clear_form(self):
        """Clear the current form data."""
        self._clearing_form = True
        
        try:
            if self._current_mode == EntryMode.QUICK:
                if hasattr(self, 'quick_text_input'):
                    self.quick_text_input.value = ""
                # Clear Beanquick result
                self._last_beanquick_result = []
            elif self.current_form:
                self.current_form.clear_form()
        finally:
            self._clearing_form = False
        
        self._update_preview()
        logger.debug("Form cleared")

    def _has_beanquick_content(self) -> bool:
        """Check if current quick entry contains Beanquick content.
        
        Returns:
            True if the quick entry contains Beanquick syntax.
        """
        if not (hasattr(self, 'quick_text_input') and self.quick_text_input.value):
            return False
        
        return True

    def _get_beanquick_preview_content(self) -> str:
        if not self._last_beanquick_result:
            return ""
        
        outputs = []
        for result in self._last_beanquick_result:
            outputs.append(self._get_beanquick_result_content(result))
        
        return "\n".join(outputs)

    def _get_beanquick_result_content(self, result: BeanquickResult) -> str:
        """Get the preview content for Beanquick input with enhanced error handling.
        
        Returns:
            String content for the preview pane.
        """
        try:
            if not result:
                return "# Processing Beanquick input..."
            
            if result.success and result.beancount_output:
                # Show successful parse result
                return result.beancount_output
            else:
                # Show error with suggestions
                error_msg = result.error_message or "Unknown error"
                error_type = result.error_type or "error"
                
                preview_lines = [
                    f"; Beanquick {error_type.replace('_', ' ').title()}:",
                    f"; {error_msg}",
                ]
                
                # Add suggestions if available
                if result.suggestions:
                    preview_lines.append(";")
                    preview_lines.append("; Suggestions:")
                    for suggestion in result.suggestions:
                        preview_lines.append(f"; • {suggestion}")
                
                # Add health status if there are initialization issues
                if error_type == "initialization_error":
                    preview_lines.append(";")
                    preview_lines.append("; System Status:")
                    health = self._beanquick_integration.get_health_status()
                    preview_lines.append(f"; Config file: {'✓' if health.get('config_file_exists') else '✗'}")
                    preview_lines.append(f"; Lexer: {'✓' if health.get('lexer_available') else '✗'}")
                    preview_lines.append(f"; Parser: {'✓' if health.get('parser_available') else '✗'}")
                
                preview_lines.append(f"; {"-" * 50}")
                
                return "\n".join(preview_lines)
                
        except Exception as e:
            logger.error(f"Error generating Beanquick preview: {e}", exc_info=True)
            return f"# Error generating preview:\n# {e}\n# Please check the application logs"
        
    def _is_form_empty(self) -> bool:
        """Check if the current form is essentially empty."""
        if self._current_mode == EntryMode.QUICK:
            return not (hasattr(self, 'quick_text_input') and
                        self.quick_text_input.value and 
                        self.quick_text_input.value.strip())
        
        if not self.current_form:
            return True
        
        return self.current_form.is_form_empty()
    
    def _is_form_valid(self):
        """Check if the current form is valid."""
        if self._current_mode == EntryMode.QUICK:
            return self._is_quick_form_valid()
        
        if not self.current_form:
            return False

        return self.current_form.is_form_valid()
    
    def _is_beanquick_result_valid(self, result: BeanquickResult) -> bool:
        """Check if the Beanquick result is valid."""
        return (result.success and bool(result.beancount_output))

    def _is_quick_form_valid(self) -> bool:
        """Check if the quick form is valid.
        
        Returns:
            True if quick form has valid content
        """
        # Check if we have any content
        if not (hasattr(self, 'quick_text_input') and self.quick_text_input.value.strip()):
            return False
        
        input_text = self.quick_text_input.value
        
        # If it's Beanquick input, check if parsing was successful
        return all(self._is_beanquick_result_valid(result) for result in self._last_beanquick_result)
    
    def _get_form_errors(self) -> list[str]:
        """Get validation errors from the current form."""
        if self._current_mode == EntryMode.QUICK:
            return self._get_quick_form_errors()
        
        if not self.current_form:
            return []

        return self.current_form.get_form_errors()
    
    def _get_beanquick_result_errors(self, result: BeanquickResult) -> list[str]:
        """Get validation errors from a Beanquick result."""
        errors = []
        if not result.success:
            errors.append(f"Beanquick processing failed: {result.error_message}")
        if not result.beancount_output:
            errors.append("No Beancount output generated")
        if result.suggestions:
            for suggestion in result.suggestions[:3]:  # Limit suggestions
                errors.append(f"💡 {suggestion}")
        if not result.beancount_output and not result.success:
            errors.append("No valid Beancount output generated")
        return errors

    def _get_quick_form_errors(self) -> list[str]:
        """Get validation errors for quick form with enhanced error reporting.
        
        Returns:
            List of detailed error messages with suggestions
        """
        errors = []
        
        # Check if we have the quick text input widget
        if not hasattr(self, 'quick_text_input'):
            errors.append("quick text input not available")
            return errors
        
        try:
            input_text = getattr(self.quick_text_input, 'value', None)
            
            if not input_text or not input_text.strip():
                errors.append("Please enter some content")
                return errors
            
            # Check Beanquick parsing errors
            if not self._last_beanquick_result:
                errors.append("Beanquick input not processed")
            else:
                for result in self._last_beanquick_result:
                    errors.extend(self._get_beanquick_result_errors(result))
                
            # Check for Beanquick integration health issues
            if not self._beanquick_integration.is_initialized:
                init_error = self._beanquick_integration.initialization_error
                if init_error:
                    errors.append(f"Beanquick not available: {init_error}")
                    
                    # Get health status for additional info
                    health = self._beanquick_integration.get_health_status()
                    if not health.get('config_file_exists', True):
                        errors.append("💡 Config file missing - will be created automatically")
                else:
                    errors.append("Beanquick not initialized")
                    errors.append("💡 Try restarting the application")
            
        except Exception as e:
            logger.error(f"Error getting quick form errors: {e}", exc_info=True)
            errors.append(f"Error checking form: {e}")
        
        return errors

