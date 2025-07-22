"""
Beanquick Integration Module - Provides a clean interface for Beanquick parsing in the UI.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, TYPE_CHECKING
from dataclasses import dataclass
import time
import yaml

import toga

from beanquick.beans.str import to_string

from beanquick.engine.lexer import BeanquickLexer
from beanquick.engine.parser import BeanquickParser
from beanquick.engine.processor import BeanquickProcessor
from beanquick.engine.create import to_native
from beanquick.engine.config import load_config, save_config
from beanquick.engine.data import BeanquickStatement, BeanquickCommand
from beanquick.engine.helpers import BeanquickError, BeanquickConfigError, BeanquickParseError
from beanquick.services.account_completer import AccountCompleter

if TYPE_CHECKING:
    from beanquick.app import Beanquick

logger = logging.getLogger(__name__)


@dataclass
class BeanquickResult:
    """Result of Beanquick parsing and processing."""
    success: bool
    beancount_output: Optional[str] = None
    error_message: Optional[str] = None
    ast: Optional[BeanquickStatement] = None
    error_type: Optional[str] = None
    suggestions: Optional[List[str]] = None

class BeanquickIntegration:
    """Handles Beanquick parsing and integration with the UI."""
    
    CONFIG_FILENAME = "beanquick.yaml"
    MAX_INPUT_LENGTH = 1000

    def __init__(self, app: Optional[Beanquick] = None):
        """Initialize the Beanquick integration.
        
        Args:
            app: The Beanquick application instance for accessing app paths.
        """
        self._app = app
        self._lexer: Optional[BeanquickLexer] = None
        self._parser: Optional[BeanquickParser] = None
        self._processor: Optional[BeanquickProcessor] = None
        self._config: Optional[Dict[str, Any]] = None
        self._config_path: Optional[Path] = None
        self._initialized = False
        self._initialization_error: Optional[str] = None
        self._last_initialization_attempt: Optional[float] = None
        self._retry_initialization_after_seconds = 30  # Retry after 30 seconds
        
        # Set up config path using app paths
        self._setup_config_path()
        
        logger.debug(f"Beanquick integration initialized with config path: {self._config_path}")
    
    def _setup_config_path(self):
        """Set up the configuration file path using Toga app paths."""
        try:
            if self._app:
                 # Use Toga's config directory
                config_dir = self._app.paths.config
                self._config_path = config_dir / self.CONFIG_FILENAME
                
                # Ensure the config directory exists
                config_dir.mkdir(parents=True, exist_ok=True)
                
                logger.debug(f"Using app config directory: {config_dir}")
            else:
                # Fallback to user config directory
                fallback_dir = Path.home() / ".config" / "beanquick"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                self._config_path = fallback_dir / self.CONFIG_FILENAME
                
                logger.debug(f"Using fallback config directory: {fallback_dir}")
                
        except Exception as e:
            logger.error(f"Error setting up config path: {e}", exc_info=True)
            # Ultimate fallback - current directory
            self._config_path = Path.cwd() / self.CONFIG_FILENAME
    
    def _ensure_initialized(self) -> bool:
        """Ensure the Beanquick components are initialized.
        
        Returns:
            True if initialization was successful, False otherwise.
        """
        if self._initialized:
            return True
        
        if self._initialization_error:
            current_time = time.time()

            if (self._last_initialization_attempt and 
                current_time - self._last_initialization_attempt < self._retry_initialization_after_seconds):
                # Don't retry too frequently
                return False
            # Clear error to allow retry
            logger.info("Retrying Beanquick initialization...")
            self._initialization_error = None
        
        self._last_initialization_attempt = time.time()
        try:
            # Initialize lexer with error handling
            try:
                self._lexer = BeanquickLexer()
                self._lexer.build()
            except Exception as e:
                raise BeanquickError(f"Failed to initialize lexer: {e}")
            
            # Initialize parser with error handling
            try:
                self._parser = BeanquickParser()
                self._parser.build(write_tables=True)
            except Exception as e:
                raise BeanquickError(f"Failed to initialize parser: {e}")
            
            # Load configuration with error handling
            try:
                self._config = self._ensure_config_exists()
            except Exception as e:
                raise BeanquickError(f"Failed to load configuration: {e}")

            # Initialize processor with error handling
            try:
                self._processor = BeanquickProcessor(self._config)
            except Exception as e:
                raise BeanquickError(f"Failed to initialize processor: {e}")

            self._initialized = True
            logger.info("Beanquick integration initialized successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize Beanquick: {e}"
            self._initialization_error = error_msg
            logger.error(error_msg, exc_info=True)
            return False
    
    def _ensure_config_exists(self) -> Dict[str, Any]:
        """Ensure configuration file exists, creating it if necessary.
        
        Returns:
            Configuration dictionary.
        """
        if not self._config_path:
            logger.warning("No config path available, using default config")
            return self._get_default_config()
        
        # Check if config file exists
        if self._config_path.exists():
            try:
                config = load_config(str(self._config_path))
                logger.info(f"Loaded Beanquick config from: {self._config_path}")
                return config
            except BeanquickConfigError as e:
                logger.error(f"Error loading config from {self._config_path}: {e}")
                # Try to create a backup and recreate
                self._backup_invalid_config()
                return self._create_default_config()
            except Exception as e:
                logger.error(f"Unexpected error loading config from {self._config_path}: {e}")
                return self._create_default_config()
        else:
            # Config file doesn't exist, create it
            logger.info(f"Config file not found at {self._config_path}, creating default config")
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Create a default configuration file.
        
        Returns:
            Default configuration dictionary.
        """
        try:
            default_config = self._get_default_config()
            
            # Write the config file
            config_yaml = self._generate_default_config_yaml()
            
            if self._config_path is not None:
                with open(self._config_path, 'w', encoding='utf-8') as f:
                    f.write(config_yaml)
                
                logger.info(f"Created default Beanquick config at: {self._config_path}")
            else:
                logger.warning("Config path is None, cannot create config file")
            
            return default_config
            
        except Exception as e:
            logger.error(f"Failed to create default config file: {e}", exc_info=True)
            # Return default config even if file creation failed
            return self._get_default_config()

    def _backup_invalid_config(self):
        """Create a backup of an invalid config file."""
        try:
            if self._config_path and self._config_path.exists():
                backup_path = self._config_path.with_suffix('.yaml.backup')
                import shutil
                shutil.copy2(self._config_path, backup_path)
                logger.info(f"Backed up invalid config to: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup invalid config: {e}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default Beanquick configuration.
        
        Returns:
            Default configuration dictionary.
        """
        return {
            "defaults": {
                "currency": "USD",
                "flag": "*",
                "narration": "Transaction"
            },
            "aliases": {
                # Common asset accounts
                "cash": "Assets:Cash",
                "coffee": "Expenses:Food:Coffee"
            },
            "command_templates": {
                # Templates for common transactions
                "coffee": {
                    "template": """{{ today }} * "morning coffee"
    Assets:Cash           -{{ args[0] }} USD
    Expenses:Food:Coffee   {{ args[0] }} USD"""
                }
            }
        }
    
    def _generate_default_config_yaml(self) -> str:
        """Generate default config file content as YAML.
        
        Returns:
            YAML string for default configuration.
        """
        # Get the default config as a dict and convert to YAML
        default_config = self._get_default_config()

        # Add comments for the YAML file
        header_comment = """# Beanquick Configuration File
# This file configures Beanquick shortcuts and aliases
# 
# Beanquick allows you to quickly enter transactions using simple syntax:
# Examples:
#   25 from:cash to:food |Coffee                     - Simple expense
#   100 from:checking to:savings"                    - Transfer between accounts
#   @yesterday 50 from:credit to:gas |Gas station"   - Yesterday's transaction
#
# For more information, see the Beanquick documentation.
"""
        yaml_content = yaml.dump(default_config, default_flow_style=False, sort_keys=False)
        return header_comment + yaml_content

    def parse_beanquick_multiline(self, input_text: str) -> List[BeanquickResult]:
        """Parse multiple Beanquick inputs separated by newlines.
        
        Args:
            input_text: The Beanquick input string containing multiple lines.
            
        Returns:
            List of BeanquickResult objects, one for each line.
        """
        results = []
        
        if not input_text:
            return results
        
        lines = input_text.split('\n')
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
                
            # Parse each non-empty line
            result = self.parse_beanquick(line)
            results.append(result)
        
        return results
    
    def parse_beanquick(self, input_text: str) -> BeanquickResult:
        """Parse Beanquick input and return the result with comprehensive error handling.
        
        Args:
            input_text: The Beanquick input string to parse.
            
        Returns:
            BeanquickResult containing the parsing result.
        """
        try:
            # Input validation
            validation_result = self._validate_input(input_text)
            if not validation_result.success:
                return validation_result
            
            # Ensure components are initialized
            if not self._ensure_initialized():
                return BeanquickResult(
                    success=False,
                    error_message=self._initialization_error or "Beanquick initialization failed",
                    error_type="initialization_error",
                    suggestions=["Check Beanquick configuration", "Restart the application", "Check log files for details"]
                )
            
            # Parse with error handling
            try:
                ast = self._safe_parse(input_text.strip())
                logger.debug(f"AST: {ast}")  # Debug output
                if not ast:
                    return BeanquickResult(
                        success=False,
                        error_message="Failed to parse input - invalid syntax",
                        error_type="parse_error",
                        suggestions=self._get_syntax_suggestions(input_text)
                    )
            except BeanquickParseError as e:
                return BeanquickResult(
                    success=False,
                    error_message=str(e),
                    error_type="parse_error",
                    suggestions=self._get_syntax_suggestions(input_text)
                )
            
            # Process AST with error handling
            try:
                beancount_output = self._safe_process_ast(ast)
                
                return BeanquickResult(
                    success=True,
                    beancount_output=beancount_output,
                    ast=ast
                )
                
            except BeanquickError as e:
                return BeanquickResult(
                    success=False,
                    error_message=str(e),
                    error_type="processing_error",
                    suggestions=self._get_processing_suggestions(ast)
                )
            
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Unexpected error parsing Beanquick input: {e}", exc_info=True)
            return BeanquickResult(
                success=False,
                error_message=str(e),
                error_type="unexpected_error",
                suggestions=["Try a simpler input", "Check the Beanquick syntax", "Report this issue if it persists"]
            )

    def _validate_input(self, input_text: str) -> BeanquickResult:
        """Validate Beanquick input before parsing.
        
        Args:
            input_text: Input text to validate
            
        Returns:
            BeanquickResult with validation status
        """
        # Handle None input
        if input_text is None:
            return BeanquickResult(
                success=False,
                error_message="Input is None",
                error_type="validation_error",
                suggestions=["Enter some text"]
            )
        
        # Handle empty input
        if not input_text or not input_text.strip():
            return BeanquickResult(
                success=False,
                error_message="Input is empty",
                error_type="validation_error",
                suggestions=["Enter Beanquick syntax like '25 from:cash to:coffee'"]
            )
        
        # Check input length
        if len(input_text) > self.MAX_INPUT_LENGTH:
            return BeanquickResult(
                success=False,
                error_message=f"Input too long (max {self.MAX_INPUT_LENGTH} characters)",
                error_type="validation_error",
                suggestions=["Use shorter input", "Split into multiple entries"]
            )
        
        # Check for potentially dangerous characters
        dangerous_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05']
        if any(char in input_text for char in dangerous_chars):
            return BeanquickResult(
                success=False,
                error_message="Input contains invalid characters",
                error_type="validation_error",
                suggestions=["Remove special control characters", "Use plain text only"]
            )
        
        # Validation passed
        return BeanquickResult(success=True)

    def _safe_parse(self, input_text: str) -> Optional[BeanquickStatement]:
        """Safely parse input.
        
        Args:
            input_text: Input to parse
            
        Returns:
            Parsed AST or None if parsing failed
        """
        try:
            # Check if parser and lexer are available
            if self._parser is None:
                raise BeanquickParseError("Parser not initialized")
            if self._lexer is None:
                raise BeanquickParseError("Lexer not initialized")
            
            ast = self._parser.parse(input_text, lexer_instance=self._lexer)
            return ast
        except RecursionError:
            raise BeanquickParseError("Input too complex (recursion limit exceeded)")
        except MemoryError:
            raise BeanquickParseError("Input too large (memory limit exceeded)")
        except Exception as e:
            # Re-raise as BeanquickParseError for consistent handling
            raise BeanquickParseError(str(e))

    def _safe_process_ast(self, ast: BeanquickStatement) -> str:
        """Safely process AST to Beancount output.
        
        Args:
            ast: Parsed AST
            
        Returns:
            Beancount output string
        """
        try:
            if not self._config:
                raise BeanquickError("Configuration not available")
            if not self._processor:
                raise BeanquickError("Processor not available")
            if isinstance(ast, BeanquickCommand):
                # If it's a command, expand it
                beancount_output = self._processor.expand_command(ast)
            else:
                beanquick_stmt = self._processor.process_statement(ast)
                beancount_directive = to_native(beanquick_stmt)
                # Convert the object to a string for the preview
                currency_column = 61  # Default currency column
                if self._app and hasattr(self._app, 'active_ledger') and self._app.active_ledger:
                    currency_column = getattr(self._app.active_ledger.beanquick_options, 'currency_column', 61)
                beancount_output = to_string(beancount_directive, currency_column)

            # Validate the output is reasonable
            if not beancount_output or not beancount_output.strip():
                raise BeanquickError("Generated empty Beancount output")
            
            # Check output length is reasonable
            if len(beancount_output) > 10000:  # 10KB limit
                logger.warning(f"Generated very large Beancount output: {len(beancount_output)} chars")
            
            return beancount_output
            
        except BeanquickError:
            raise  # Re-raise Beanquick errors as-is
        except Exception as e:
            raise BeanquickError(f"AST processing failed: {e}")

    def _get_syntax_suggestions(self, input_text: str) -> List[str]:
        """Get syntax suggestions for parse errors.
        
        Args:
            input_text: The input that failed to parse
            
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        # Common syntax patterns
        suggestions.extend([
            "Example: 25 from:cash to:food |Coffee",
            "Example: 100 from:checking to:savings",
            "Example: @yesterday 50 from:credit to:gas |Gas station",
            "Example: 25 USD from:cash to:food |Starbucks|Morning coffee",
            "Example: bal checking 1000 USD",
            "Example: pad from:checking to:equity",
            "Example: px AAPL 220 USD",
            "Payee/narration in pipes: |payee|narration or |narration",
            "Tags with # and links with ^",
            "Metadata in braces {key: value}",
            "Multiple 'to:' accounts supported",
            "Check spacing between elements",
            "Ensure account aliases are defined"
        ])
        
        # Check for common mistakes
        if '"' in input_text and input_text.count('"') % 2 != 0:
            suggestions.append("Check that quotes are properly closed")
        
        if '#' in input_text and not input_text.split('#')[1].strip():
            suggestions.append("Tags should have content after #")
        
        return suggestions[:5]  # Limit to 5 suggestions

    def _get_processing_suggestions(self, ast: Optional[BeanquickStatement]) -> List[str]:
        """Get processing suggestions for AST processing errors.
        
        Args:
            ast: The AST that failed to process
            
        Returns:
            List of suggestion strings
        """
        suggestions = [
            "Check that account aliases are defined in config",
            "Check date format (YYYY-MM-DD or MM-DD)",
            "Verify currency codes are valid (e.g., USD, EUR)",
            "Payee/narration should be in format |payee|narration or |narration",
            "Tags should be in format #tagname",
            "Links should be in format ^linkname",
            "Metadata should be in format {key: value}",
        ]
        
        # Add AST-specific suggestions if available
        if ast:
            # Command suggestions
            if isinstance(ast, BeanquickCommand):
                suggestions.extend([
                    f"Command '/{ast.trigger}' may not be defined in config",
                    "Check command_templates section in config",
                    "Verify command parameters are correct",
                ])
            # TODO: Add more AST-specific suggestions as needed
        
        return suggestions[:5]  # Limit to 5 suggestions
    
    def get_config_info(self) -> Tuple[bool, Optional[str]]:
        """Get information about the configuration status with error handling.
        
        Returns:
            Tuple of (config_file_exists, config_path_str)
        """
        try:
            config_exists = self._config_path.exists() if self._config_path else False
            config_path_str = str(self._config_path) if self._config_path else None
            
            return config_exists, config_path_str
            
        except Exception as e:
            logger.error(f"Error getting config info: {e}", exc_info=True)
            return False, None
    
    def safe_save_config(self, config):
        """Safely save configuration with error reporting.

        Args:
            config: The configuration data to save.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            if self._config_path is None:
                return False, "No config path available"
            save_config(config, str(self._config_path))
            logger.info(f"Successfully saved Beanquick config to {self._config_path}")
            return True, None
        except Exception as e:
            error_msg = f"Failed to save config: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def safe_reload_config(self) -> Tuple[bool, Optional[str]]:
        """Safely reload configuration with error reporting.
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            self._config = self._ensure_config_exists()
            if self._processor:
                self._processor.config = self._config
            logger.info(f"Successfully reloaded Beanquick config from {self._config_path}")
            return True, None
        except Exception as e:
            error_msg = f"Failed to reload config: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of Beanquick integration.
        
        Returns:
            Dictionary with health status information
        """
        status = {
            'initialized': self._initialized,
            'initialization_error': self._initialization_error,
            'config_available': self._config is not None,
            'config_path': str(self._config_path) if self._config_path else None,
            'lexer_available': self._lexer is not None,
            'parser_available': self._parser is not None,
            'last_initialization_attempt': self._last_initialization_attempt,
        }
        
        # Add config file status
        try:
            if self._config_path:
                status['config_file_exists'] = self._config_path.exists()
                if self._config_path.exists():
                    status['config_file_size'] = self._config_path.stat().st_size
                    status['config_file_modified'] = self._config_path.stat().st_mtime
        except Exception as e:
            status['config_status_error'] = str(e)
        
        return status
    
    def open_config_file(self) -> bool:
        """Open the configuration file in the default editor.
        
        Returns:
            True if file was opened successfully.
        """
        try:
            if not self._config_path or not self._config_path.exists():
                logger.error("Config file does not exist")
                return False
            
            import subprocess
            import sys
            
            if sys.platform == "darwin":  # macOS
                subprocess.run(["open", str(self._config_path)])
            elif sys.platform == "win32":  # Windows
                subprocess.run(["start", str(self._config_path)], shell=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", str(self._config_path)])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to open config file: {e}", exc_info=True)
            return False

    @property
    def is_initialized(self) -> bool:
        """Check if the integration is initialized."""
        return self._initialized
    
    @property
    def initialization_error(self) -> Optional[str]:
        """Get the initialization error message if any."""
        return self._initialization_error
    
    @property 
    def config_path(self) -> Optional[Path]:
        """Get the current config file path."""
        return self._config_path
    
    @property
    def config(self) -> Optional[Dict[str, Any]]:
        """Get the current configuration."""
        return self._config

    @property
    def account_completer(self) -> AccountCompleter:
        """Get the account completer instance."""
        if not hasattr(self, '_account_completer'):
            accounts = []
            if self._app:
                accounts = list(self._app.active_ledger_data.accounts) if self._app.active_ledger_data else []
            self._account_completer = AccountCompleter(accounts)
        return self._account_completer

# Global instance for use throughout the application
_beanquick_integration: Optional[BeanquickIntegration] = None

def get_beanquick_integration(app: Optional[toga.App] = None) -> BeanquickIntegration:
    """Get or create the global Beanquick integration instance.
    
    Args:
        app: The Toga application instance.
        
    Returns:
        The Beanquick integration instance.
    """
    global _beanquick_integration
    
    if _beanquick_integration is None:
        _beanquick_integration = BeanquickIntegration(app)
    
    return _beanquick_integration

def reset_beanquick_integration():
    """Reset the global Beanquick integration instance."""
    global _beanquick_integration
    _beanquick_integration = None