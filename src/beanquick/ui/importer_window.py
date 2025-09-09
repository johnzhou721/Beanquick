"""
Statement importer window.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, cast

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD, START  # type: ignore
from toga.colors import DODGERBLUE, DIMGRAY

from beanquick.importers.core.registry import importer_registry
from beanquick.importers.core.exceptions import BeanquickImporterError, FileIdentificationError, DataExtractionError
from beanquick.importers.importer_utils import get_importer_id
from beanquick.importers.rules.repository import RuleRepository
from beanquick.importers.rules.engine import RuleEngine

from .importer.transaction_review.view import TransactionTriageView
from .importer.transaction_review.factory import create_display_transactions
from beanquick.services.beanquick_integration import get_beanquick_integration


logger = logging.getLogger(__name__)


LARGE_MARGIN = 20
DEFAULT_MARGIN = 8
TITLE_FONT_SIZE = 32
DESCRIPTION_FONT_SIZE = 10


class ImportState(Enum):
    """Enumeration of import workflow states for progressive disclosure."""
    INITIAL = "initial"
    FILE_SELECTED = "file_selected"
    CONFIGURING = "configuring"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class FileSelection:
    """Represents a selected statement file.
    
    This dataclass encapsulates information about a file selected by the user
    for import processing, including validation capabilities for supported formats.
    
    Attributes:
        path: Path object representing the file location
        filename: Name of the file including extension
        extension: File extension (e.g., '.pdf', '.csv')
        size: File size in bytes
    """
    path: Path
    filename: str
    extension: str
    size: int
    
    @property
    def is_supported_format(self) -> bool:
        """Check if file format is supported for import.
        
        Validates that the file extension is one of the supported formats
        for statement import processing.
        
        Returns:
            bool: True if the file format is supported (PDF or CSV), False otherwise
        """
        return self.extension.lower() in ['.pdf', '.csv']


@dataclass
class ImportConfiguration:
    """Configuration for the import process.
    
    This dataclass holds all the settings and parameters needed to configure
    the statement import process, including source file, destination account,
    target Beancount file, and formatting preferences.
    
    Attributes:
        source_file: Path to the statement file to be imported
        destination_account: Target Beancount account for imported transactions
        beancount_file: Path to the Beancount file where entries will be written
        date_format: Date format string for parsing statement dates
    """
    source_file: Path
    destination_account: str | None = None
    beancount_file: Path | None = None
    date_format: str | None = None
    
    def is_complete(self) -> bool:
        """Check if configuration is complete for processing.
        
        Validates that all required fields are populated with valid values
        to proceed with the import process.
        
        Returns:
            bool: True if all required configuration is present, False otherwise
        """
        return all([
            self.source_file,
            self.destination_account,
            self.beancount_file
        ])


class ImporterWindow(toga.Window):
    """Statement importer window with essentialist design."""
    
    def __init__(self, title="Beanquick Importer"):
        """Initialize the importer window.
        
        Args:
            title: Window title
        """
        super().__init__(
            title=title, 
            size=(800, 580),
        )
        
        # Initialize state management for progressive disclosure
        self._current_state = ImportState.INITIAL
        self._selected_file: Optional[FileSelection] = None
        self._import_config: Optional[ImportConfiguration] = None
        self._workflow_context: Dict[str, Any] = {}
        
        self._create_ui()
        logger.info("Importer window initialized")

    def _create_ui(self):
        """Create the UI components."""
        # --- 1. Top Area (Logo/App Name & Title) ---
        logo = toga.ImageView(
            image=toga.Image('resources/images/NotoMagicWand.png'),
            style=Pack(width=108, height=108)
        )

        app_title = toga.Label(
            "Statement Importer",
            style=Pack(font_size=TITLE_FONT_SIZE, font_weight=BOLD, margin_bottom=DEFAULT_MARGIN)
        )
        
        subtitle_label = toga.Label(
            "Turn your statements into Beancount entries.",
            style=Pack(font_size=14, color=DIMGRAY, margin_bottom=DEFAULT_MARGIN)
        )
        
        header = toga.Box(
            children=[
                logo,
                app_title,
                subtitle_label,
            ],
            style=Pack(direction=COLUMN, margin=(20, 0, 60), align_items=CENTER)
        )

        # --- 2. Import Action Area ---
        self.import_button = toga.Button(
            "Import Statement",
            on_press=self._on_import_clicked,
            style=Pack(
                width=400,
                height=28,
                font_weight=BOLD,
                margin_bottom=DEFAULT_MARGIN,
                background_color=DODGERBLUE
            )
        )
        
        import_description = toga.Label(
            "Select a PDF or CSV statement file to convert.",
            style=Pack(font_size=DESCRIPTION_FONT_SIZE, color=DIMGRAY)
        )
        
        import_box = toga.Box(
            children=[self.import_button, import_description],
            style=Pack(direction=COLUMN, align_items=CENTER)
        )

        content_box = toga.Box(
            children=[
                header,
                import_box,
            ],
            style=Pack(direction=COLUMN, align_items=CENTER)
        )

        # --- Create main container with flexible spacing ---
        main_box = toga.Box(
            children=[
                toga.Box(style=Pack(flex=1)),
                content_box,
                toga.Box(style=Pack(flex=1))
            ],
            style=Pack(direction=ROW, align_items=START, margin=LARGE_MARGIN)
        )
        
        # Set the main box as the window content
        self.content = main_box
        
        logger.debug("Importer window UI created")

    async def _on_import_clicked(self, widget):
        """Handle import button click event.
        
        Opens a native file dialog to allow the user to select a statement file
        for conversion. Supports PDF and CSV formats only with single file selection.
        Implements graceful error recovery and ensures interface stability.
        
        Args:
            widget: The button widget that was clicked
        """
        logger.debug("Import button clicked")
        
        # Disable button during operation to prevent multiple simultaneous dialogs
        self.import_button.enabled = False
        
        try:
            # Open native file dialog with specified configuration
            file_dialog = toga.OpenFileDialog(
                title="Please select the statement file to convert",
                file_types=['pdf', 'csv'],
                multiple_select=False
            )
            
            selected_file = await self.dialog(file_dialog)
            
            if selected_file:
                logger.info(f"File selected: {selected_file}")
                
                # Validate the selected file
                if await self._validate_file_selection(selected_file):
                    # File validation successful, proceed to next step in workflow
                    logger.debug("File validation successful, proceeding to next step")
                    await self._proceed_to_next_step(selected_file)
                else:
                    # Validation failed, graceful recovery handled by validation method
                    logger.debug("File validation failed, interface reset by validation method")
            else:
                logger.debug("File selection cancelled by user")
                # User cancelled dialog - return interface to initial state (requirement 4.5)
                await self._reset_to_initial_state()
                
        except Exception as e:
            logger.error(f"Error during file selection: {e}", exc_info=True)
            await self._handle_file_selection_error(e)
        finally:
            # Ensure button is re-enabled even if an error occurred
            self.import_button.enabled = True

    async def _validate_file_selection(self, file_path: Path) -> bool:
        """Validate selected file meets requirements.
        
        Checks file existence and format to ensure it can be processed.
        Shows user-friendly error messages for validation failures and
        implements graceful error recovery.
        
        Args:
            file_path: Path to the selected file
            
        Returns:
            bool: True if file is valid, False otherwise
        """
        logger.debug(f"Validating file selection: {file_path}")
        
        try:
            # Check if file exists
            if not file_path.exists():
                await self._show_error(
                    "File Not Found",
                    f"The selected file does not exist:\n{file_path}\n\nPlease try selecting the file again."
                )
                await self._reset_to_initial_state()
                return False
            
            # Check if file format is supported
            file_extension = file_path.suffix.lower()
            supported_formats = ['.pdf', '.csv']
            
            if file_extension not in supported_formats:
                await self._show_error(
                    "Unsupported File Format",
                    f"Unsupported file format '{file_extension}'. "
                    f"Please select a PDF or CSV file.\n\n"
                    f"Supported formats: {', '.join(supported_formats)}"
                )
                await self._reset_to_initial_state()
                return False
            
            # Additional validation: check if file is readable
            try:
                with open(file_path, 'rb') as f:
                    # Try to read first few bytes to ensure file is accessible
                    f.read(1024)
            except PermissionError:
                await self._show_error(
                    "Permission Denied",
                    f"Permission denied accessing the file:\n{file_path}\n\n"
                    f"Please check file permissions and try again."
                )
                await self._reset_to_initial_state()
                return False
            except OSError as e:
                await self._show_error(
                    "File Access Error",
                    f"Could not access the file:\n{file_path}\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please ensure the file is not in use by another application."
                )
                await self._reset_to_initial_state()
                return False
            
            logger.info(f"File validation successful: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error during file validation: {e}", exc_info=True)
            await self._show_error(
                "Validation Error",
                f"An unexpected error occurred while validating the file:\n{str(e)}\n\n"
                f"Please try selecting the file again."
            )
            await self._reset_to_initial_state()
            return False

    async def _show_error(self, title: str, message: str):
        """Display an error dialog to the user.
        
        Shows a user-friendly error dialog with the specified title and message.
        This method provides consistent error presentation across the application
        and ensures proper logging of error events.
        
        Args:
            title: Error dialog title
            message: Error message to display
        """
        logger.warning(f"Showing error dialog: {title} - {message}")
        
        try:
            await self.dialog(
                toga.ErrorDialog(
                    title,
                    message,
                )
            )
        except Exception as dialog_error:
            # Fallback error handling if dialog fails
            logger.error(f"Failed to show error dialog: {dialog_error}", exc_info=True)
            # Ensure the interface returns to initial state even if dialog fails
            await self._reset_to_initial_state()

    async def _handle_file_selection_error(self, error: Exception):
        """Handle errors during file selection process.
        
        Provides specialized error handling for file selection operations,
        including graceful error recovery and user guidance. Ensures the
        interface returns to a stable state after error handling.
        
        Args:
            error: The exception that occurred during file selection
        """
        logger.error(f"File selection error: {error}", exc_info=True)
        
        # Determine appropriate error message based on error type
        if isinstance(error, FileNotFoundError):
            title = "File Not Found"
            message = "The selected file could not be found. Please try selecting the file again."
        elif isinstance(error, PermissionError):
            title = "Permission Denied"
            message = "Permission denied accessing the selected file. Please check file permissions and try again."
        elif isinstance(error, OSError):
            title = "File Access Error"
            message = f"Could not access the selected file: {str(error)}\n\nPlease ensure the file is not in use by another application."
        else:
            title = "File Selection Error"
            message = f"An unexpected error occurred while selecting the file:\n{str(error)}\n\nPlease try again."
        
        # Show error dialog with recovery guidance
        await self._show_error(title, message)
        
        # Ensure graceful recovery to initial state
        await self._reset_to_initial_state()

    async def _reset_to_initial_state(self):
        """Reset the interface to its initial state for graceful error recovery.
        
        This method ensures that after any error or cancellation, the interface
        returns to a clean, usable state. It re-enables controls, clears any
        temporary state, and prepares the interface for the next user interaction.
        """
        logger.debug("Resetting interface to initial state")
        
        try:
            # Re-enable the import button if it was disabled
            self.import_button.enabled = True
            
            # Clear progressive disclosure state
            self._current_state = ImportState.INITIAL
            self._selected_file = None
            self._import_config = None
            self._workflow_context.clear()
            
            # Clear any temporary state or progress indicators
            # (This will be expanded in future tasks that add progress indicators)
            
            # Log successful reset
            logger.debug("Interface successfully reset to initial state")
            
        except Exception as reset_error:
            # Log reset errors but don't propagate them to avoid error loops
            logger.error(f"Error during interface reset: {reset_error}", exc_info=True)

    def reset_to_initial_state_with_ui(self):
        """Public method to reset window to initial state including UI content.
        
        This method resets both the internal state and restores the original
        importer UI content. This is useful when transitioning back from other
        views to the original importer interface.
        """
        try:
            logger.debug("Resetting importer window to initial state with UI")
            
            # Reset internal state first
            self._current_state = ImportState.INITIAL
            self._selected_file = None
            self._import_config = None
            self._workflow_context.clear()
            
            # Recreate the original UI content
            self._create_ui()

            self.size = (800, 580)
            
            # Update window title
            self.title = "Beanquick Importer"
            
            logger.debug("Successfully reset importer window to initial state with UI")
            
        except Exception as e:
            logger.error(f"Error resetting importer window to initial state: {e}", exc_info=True)
            raise

    
    async def _proceed_to_next_step(self, selected_file: Path):
        """Proceed to the next step in the import workflow after file selection.
        
        This method implements progressive disclosure by transitioning from the initial
        file selection state to the next appropriate step in the import process.
        It uses the importer registry to find a suitable importer and processes the file
        in the background to keep the UI responsive.
        
        Args:
            selected_file: Path to the successfully selected and validated file
        """
        logger.info(f"Proceeding to next step with file: {selected_file}")
        
        try:
            # Create FileSelection object with file metadata
            file_stats = selected_file.stat()
            self._selected_file = FileSelection(
                path=selected_file,
                filename=selected_file.name,
                extension=selected_file.suffix,
                size=file_stats.st_size
            )
            
            # Update state to indicate file has been selected
            self._current_state = ImportState.FILE_SELECTED
            
            # Initialize import configuration with the selected file
            self._import_config = ImportConfiguration(source_file=selected_file)
            
            # Find suitable importer using the registry
            logger.debug(f"Finding importer for file: {selected_file}")
            selected_importer = importer_registry.find_importer_for_file(str(selected_file))
            
            if selected_importer is None:
                # No suitable importer found - show user-friendly error
                logger.warning(f"No suitable importer found for file: {selected_file}")
                await self._show_error(
                    "Unsupported File Format",
                    f"No importer could be found for the selected file:\n{selected_file.name}\n\n"
                    f"Please ensure the file is a supported statement format and try again.\n\n"
                    f"Supported formats include CMB Credit Card CSV files."
                )
                await self._reset_to_initial_state()
                return
            
            logger.info(f"Found importer: {selected_importer.__class__.__name__}")
            
            # Extract importer ID for rule repository configuration
            importer_id = get_importer_id(selected_importer)
            importer_metadata = selected_importer.metadata
            logger.debug(f"Extracted importer ID: {importer_id}")
            
            # Update state to indicate processing has begun
            self._current_state = ImportState.PROCESSING
            
            # Disable the import button during processing
            self.import_button.enabled = False
            self.import_button.text = "Processing..."
            
            # Create importer-specific RuleRepository before extraction
            logger.debug(f"Creating RuleRepository for importer: {importer_id}")
            rule_repository = RuleRepository(importer_id, importer_metadata, self.app.paths)
            rule_engine = RuleEngine(rule_repository)
            # Execute extraction in background thread to keep UI responsive
            logger.debug("Starting background file processing")
            loop = asyncio.get_event_loop()
            
            try:
                # Run the extraction in a background thread with rule repository
                extracted_transactions = await loop.run_in_executor(
                    None,  # Use default thread pool executor
                    self._extract_transactions_sync,
                    selected_importer,
                    selected_file,
                    rule_repository,
                    rule_engine
                )
                
                # Use a default account since BeanquickImporter doesn't have file_account method
                default_account = "Assets:Unknown"
                logger.info(f"Extraction completed. Found {len(extracted_transactions)} transactions")
                logger.debug(f"Default account: {default_account}")
                
                # Store extracted data in workflow context
                self._workflow_context.update({
                    'selected_file': self._selected_file,
                    'import_config': self._import_config,
                    'extracted_transactions': extracted_transactions,
                    'default_account': default_account,
                    'selected_importer': selected_importer.__class__.__name__,
                    'importer_id': importer_id,
                    'processing_completed_at': asyncio.get_event_loop().time()
                })
                
                # Transition to next step with extracted data and rule repository
                await self._transition_to_triage_view(extracted_transactions, default_account, rule_repository, rule_engine)

            except Exception as processing_error:
                logger.error(f"Error during background processing: {processing_error}", exc_info=True)
                await self._handle_import_processing_error(processing_error, selected_file.name)
            
        except Exception as e:
            logger.error(f"Error proceeding to next step: {e}", exc_info=True)
            await self._handle_workflow_error(e, "Failed to proceed to next step")
        finally:
            # Ensure button is re-enabled even if an error occurred
            self.import_button.enabled = True
            self.import_button.text = "Import Statement..."

    async def _begin_import_processing(self):
        """Begin the import processing workflow.
        
        This method is called after all necessary configuration has been collected
        and initiates the actual import processing. It serves as a placeholder
        for integration with the import processing system.
        """
        logger.info("Beginning import processing")
        
        try:
            # Update state to indicate processing has begun
            self._current_state = ImportState.PROCESSING
            
            # Validate that we have complete configuration
            if not self._import_config or not self._import_config.is_complete():
                raise ValueError("Import configuration is incomplete")
            
            # Store workflow context for processing
            self._workflow_context.update({
                'selected_file': self._selected_file,
                'import_config': self._import_config,
            })
            
            # Placeholder for actual import processing
            # This will be implemented in future tasks that handle the import pipeline
            logger.info("Import processing would begin here with configuration:")
            logger.info(f"  Source file: {self._import_config.source_file}")
            logger.info(f"  Destination account: {self._import_config.destination_account}")
            logger.info(f"  Beancount file: {self._import_config.beancount_file}")
            logger.info(f"  Date format: {self._import_config.date_format}")
            
            # For now, show a success message and reset
            await self._show_processing_complete()
            
        except Exception as e:
            logger.error(f"Error beginning import processing: {e}", exc_info=True)
            await self._handle_workflow_error(e, "Failed to begin import processing")

    async def _show_processing_complete(self):
        """Show completion message and reset interface.
        
        Placeholder method for showing import completion status.
        Will be expanded in future tasks that implement actual processing.
        """
        logger.debug("Showing processing complete message")
        
        try:
            filename = self._selected_file.filename if self._selected_file else "Unknown"
            account = self._import_config.destination_account if self._import_config else "Unknown"
            target = self._import_config.beancount_file.name if self._import_config and self._import_config.beancount_file else "Unknown"
            
            await self.dialog(
                toga.InfoDialog(
                    "Import Ready",
                    f"Configuration complete! Import would process:\n\n"
                    f"File: {filename}\n"
                    f"Account: {account}\n"
                    f"Target: {target}\n\n"
                    f"(Actual processing will be implemented in future tasks)"
                )
            )
            
            # Update state and reset for next import
            self._current_state = ImportState.COMPLETED
            await self._reset_to_initial_state()
            
        except Exception as e:
            logger.error(f"Error showing processing complete: {e}", exc_info=True)
            await self._reset_to_initial_state()

    def _extract_transactions_sync(self, importer, file_path: Path, rule_repository: RuleRepository, rule_engine: RuleEngine) -> List:
        """Synchronous method to extract transactions for triage with rule application.
        
        This method is designed to run in a background thread via run_in_executor
        to keep the UI responsive during file processing. It extracts core TransactionData
        objects and converts them to TransactionDisplayData using the UI factory.
        
        Args:
            importer: The BeanquickImporter instance to use for extraction
            file_path: Path to the file to process
            rule_repository: The RuleRepository instance for applying rules during extraction
            rule_engine: The RuleEngine instance for applying rules during extraction

        Returns:
            List[TransactionDisplayData]: List of extracted transactions converted to display objects
            
        Raises:
            BeanquickImporterError: If extraction fails
        """
        logger.debug(f"Starting synchronous extraction for triage: {file_path}")
        
        try:
            # Use the registry's extraction method to get core TransactionData objects
            core_transactions = importer_registry.extract_transactions(str(file_path))
            logger.info(f"Successfully extracted {len(core_transactions)} core transactions")
            
            # Convert core transactions to display objects using UI factory
            display_transactions = create_display_transactions(core_transactions)
            logger.info(f"Successfully converted to {len(display_transactions)} display transactions for triage")
            
            return display_transactions
            
        except BeanquickImporterError:
            # Re-raise BeanquickImporterError as-is for proper error handling
            raise
        except Exception as e:
            # Wrap unexpected errors in DataExtractionError
            logger.error(f"Unexpected error during extraction: {e}", exc_info=True)
            raise DataExtractionError(f"Failed to extract data from file: {str(e)}") from e

    async def _handle_import_processing_error(self, error: Exception, file_name: str):
        """Handle errors that occur during import processing.
        
        Provides specialized error handling for importer-specific errors,
        including beangulp-specific exceptions and conversion errors.
        Maintains existing error dialog patterns from importer window.
        
        Args:
            error: The exception that occurred during processing
            file_name: Name of the file being processed
        """
        logger.error(f"Import processing error for {file_name}: {error}", exc_info=True)
        
        try:
            # Update state to indicate error
            self._current_state = ImportState.ERROR
            
            # Handle BeanquickImporterError exceptions with user-friendly messages
            if isinstance(error, FileIdentificationError):
                await self._show_error(
                    "File Format Not Supported",
                    f"Unable to identify the format of '{file_name}'.\n\n"
                    f"{str(error)}\n\n"
                    f"Please ensure the file is a supported statement format (e.g., CMB Credit Card CSV) and try again."
                )
            elif isinstance(error, DataExtractionError):
                await self._show_error(
                    "Data Extraction Failed",
                    f"Failed to extract transaction data from '{file_name}'.\n\n"
                    f"{str(error)}\n\n"
                    f"The file may be corrupted, incomplete, or in an unexpected format. "
                    f"Please verify the file contents and try again."
                )
            elif isinstance(error, BeanquickImporterError):
                # Generic BeanquickImporterError with specific message
                await self._show_error(
                    "Import Processing Error",
                    f"Failed to process '{file_name}':\n\n"
                    f"{str(error)}\n\n"
                    f"Please check the file format and try again."
                )
            
            # Handle beangulp-specific exceptions
            elif hasattr(error, '__module__') and 'beangulp' in str(error.__module__):
                logger.warning(f"Beangulp-specific error: {error}")
                await self._show_error(
                    "Importer Error",
                    f"The importer encountered an error while processing '{file_name}':\n\n"
                    f"{str(error)}\n\n"
                    f"This may indicate an issue with the file format or content. "
                    f"Please verify the file is a valid statement and try again."
                )
            
            # Handle beancount-specific exceptions
            elif hasattr(error, '__module__') and 'beancount' in str(error.__module__):
                logger.warning(f"Beancount-specific error: {error}")
                await self._show_error(
                    "Transaction Processing Error",
                    f"Error processing transaction data from '{file_name}':\n\n"
                    f"{str(error)}\n\n"
                    f"The file data may contain invalid transaction information. "
                    f"Please check the file contents and try again."
                )
            
            # Handle conversion errors (e.g., Decimal conversion, date parsing)
            elif isinstance(error, (ValueError, TypeError)) and any(keyword in str(error).lower() 
                    for keyword in ['decimal', 'date', 'convert', 'parse', 'format']):
                logger.warning(f"Data conversion error: {error}")
                await self._show_error(
                    "Data Format Error",
                    f"Unable to process data from '{file_name}' due to formatting issues:\n\n"
                    f"{str(error)}\n\n"
                    f"The file may contain invalid dates, amounts, or other data formats. "
                    f"Please verify the file contents match the expected format."
                )
            
            # Handle encoding errors (common with CSV files)
            elif isinstance(error, UnicodeDecodeError):
                logger.warning(f"File encoding error: {error}")
                await self._show_error(
                    "File Encoding Error",
                    f"Unable to read '{file_name}' due to character encoding issues.\n\n"
                    f"The file may be saved in an unsupported encoding format. "
                    f"Please ensure the file is saved with UTF-8 or GBK encoding and try again."
                )
            
            # Handle file system errors
            elif isinstance(error, FileNotFoundError):
                await self._show_error(
                    "File Not Found",
                    f"The file '{file_name}' could not be found during processing.\n\n"
                    f"The file may have been moved or deleted. "
                    f"Please ensure the file still exists and try again."
                )
            elif isinstance(error, PermissionError):
                await self._show_error(
                    "Permission Error",
                    f"Permission denied while processing '{file_name}'.\n\n"
                    f"Please check that you have read access to the file and try again."
                )
            elif isinstance(error, OSError):
                await self._show_error(
                    "File Access Error",
                    f"Unable to access '{file_name}' during processing:\n\n"
                    f"{str(error)}\n\n"
                    f"The file may be in use by another application or corrupted. "
                    f"Please close any other programs using the file and try again."
                )
            
            # Handle memory errors (for large files)
            elif isinstance(error, MemoryError):
                logger.error(f"Memory error processing {file_name}: {error}")
                await self._show_error(
                    "Memory Error",
                    f"Insufficient memory to process '{file_name}'.\n\n"
                    f"The file may be too large for processing. "
                    f"Please try with a smaller file or close other applications to free up memory."
                )
            
            # Handle timeout errors (for slow processing)
            elif isinstance(error, TimeoutError):
                logger.warning(f"Timeout error processing {file_name}: {error}")
                await self._show_error(
                    "Processing Timeout",
                    f"Processing '{file_name}' took too long and was cancelled.\n\n"
                    f"The file may be very large or complex. "
                    f"Please try again or contact support if the problem persists."
                )
            
            else:
                # Unexpected error - log details but show generic message
                logger.error(f"Unexpected error processing {file_name}: {error}", exc_info=True)
                await self._show_error(
                    "Processing Error",
                    f"An unexpected error occurred while processing '{file_name}'.\n\n"
                    f"Please check the file format and try again. "
                    f"If the problem persists, please contact support."
                )
            
            # Reset to initial state for recovery
            await self._reset_to_initial_state()
            
        except Exception as recovery_error:
            logger.error(f"Error during processing error recovery: {recovery_error}", exc_info=True)
            # Force reset even if error handling fails
            await self._reset_to_initial_state()

    async def _transition_to_triage_view(self, display_transactions: List, default_account: str, rule_repository: RuleRepository, rule_engine: RuleEngine):
        """Transition to the triage view with extracted transaction display data.
        
        This method creates and displays the TransactionTriageView with the extracted
        TransactionDisplayData objects, replacing the importer window content with 
        the triage interface. Implements proper error handling for transition failures 
        and ensures cleanup of importer window state.
        
        Args:
            display_transactions: List of extracted TransactionDisplayData objects
            default_account: Default account for the transactions
            rule_repository: Importer-specific RuleRepository instance
            rule_engine: RuleEngine instance for applying rules

        Raises:
            ValueError: If transactions list is empty or rule_repository is None
            RuntimeError: If app instance is not available
        """
        logger.info(f"Transitioning to triage view with {len(display_transactions)} display transactions")
        logger.debug(f"Default account: {default_account}")
        
        try:
            # Validate inputs
            if not display_transactions:
                raise ValueError("Display transactions list cannot be empty for triage view")
            
            if not rule_repository:
                raise ValueError("RuleRepository is required for triage view")
            
            # Get the app instance from the window
            app = self.app
            if not app:
                raise RuntimeError("App instance not available for triage view creation")
            
            # Update workflow context with transition details
            self._workflow_context.update({
                'transition_started_at': asyncio.get_event_loop().time(),
                'transition_target': 'triage_view',
                'transaction_count': len(display_transactions),
                'default_account': default_account,
                'rule_repository_importer_id': rule_repository._importer_id
            })
            
            # Create the triage view with extracted display transactions and importer-specific rule repository
            logger.debug(f"Creating TransactionTriageView instance with rule repository for importer: {rule_repository._importer_id}")
            beanquick_integration = get_beanquick_integration(self.app)
            triage_view = TransactionTriageView(app, display_transactions, rule_repository, rule_engine, beanquick_integration)
            
            # Set source context for success statistics collection
            source_file_path = str(self._selected_file.path) if self._selected_file else "Unknown"
            
            triage_view.set_source_context(source_file_path)

            # Create and display the triage view in the importer window
            logger.debug("Displaying triage view in importer window")
            triage_view.show_in_window(self)
            
            # Update state to indicate successful completion
            self._current_state = ImportState.COMPLETED
            
            # Store successful transition context
            self._workflow_context.update({
                'transition_completed_at': asyncio.get_event_loop().time(),
                'triage_view_created': True
            })
            
            # Clean up importer window state after successful transition
            await self._cleanup_after_transition()
            
            logger.info(f"Successfully transitioned to triage view with {len(display_transactions)} transactions")
            
        except ValueError as ve:
            logger.error(f"Validation error during triage transition: {ve}", exc_info=True)
            await self._handle_transition_error(ve, "Invalid data for triage view")
        except RuntimeError as re:
            logger.error(f"Runtime error during triage transition: {re}", exc_info=True)
            await self._handle_transition_error(re, "System error during transition")
        except ImportError as ie:
            logger.error(f"Import error during triage transition: {ie}", exc_info=True)
            await self._handle_transition_error(ie, "Failed to load triage view components")
        except Exception as e:
            logger.error(f"Unexpected error during triage transition: {e}", exc_info=True)
            await self._handle_transition_error(e, "Unexpected error during transition to triage view")

    async def _cleanup_after_transition(self):
        """Clean up importer window state after successful transition to triage view.
        
        This method performs necessary cleanup operations after the triage view
        has been successfully created and displayed. It ensures that the importer
        window state is properly reset and resources are freed.
        """
        logger.debug("Cleaning up importer window state after transition")
        
        try:
            # Clear workflow context to free memory
            self._workflow_context.clear()
            
            # Reset file selection state
            self._selected_file = None
            self._import_config = None
            
            # Reset UI state
            self.import_button.enabled = True
            self.import_button.text = "Import Statement..."
            
            # Close the importer window since we've transitioned to triage view
            # The main window now contains the triage view
            # logger.debug("Closing importer window after successful transition")
            # self.close()
            
        except Exception as cleanup_error:
            # Log cleanup errors but don't propagate them
            logger.warning(f"Error during post-transition cleanup: {cleanup_error}", exc_info=True)

    async def _handle_transition_error(self, error: Exception, context: str):
        """Handle errors that occur during transition to triage view.
        
        Provides specialized error handling for triage view transition failures,
        ensuring graceful recovery and appropriate user feedback. Maintains
        the importer window in a usable state for retry.
        
        Args:
            error: The exception that occurred during transition
            context: Description of the context where the error occurred
        """
        logger.error(f"Transition error in {context}: {error}", exc_info=True)
        
        try:
            # Update state to indicate error
            self._current_state = ImportState.ERROR
            
            # Store error context for debugging
            self._workflow_context.update({
                'transition_error': str(error),
                'transition_error_context': context,
                'transition_failed_at': asyncio.get_event_loop().time()
            })
            
            # Determine appropriate error message based on error type
            if isinstance(error, ValueError):
                title = "Invalid Transaction Data"
                message = (f"Cannot display triage view due to invalid transaction data:\n\n"
                          f"{str(error)}\n\n"
                          f"Please try importing the file again.")
            elif isinstance(error, RuntimeError):
                title = "System Error"
                message = (f"A system error occurred while opening the triage view:\n\n"
                          f"{str(error)}\n\n"
                          f"Please restart the application and try again.")
            elif isinstance(error, ImportError):
                title = "Component Loading Error"
                message = (f"Failed to load required components for the triage view:\n\n"
                          f"{str(error)}\n\n"
                          f"The application may need to be reinstalled.")
            else:
                title = "Transition Error"
                message = (f"An unexpected error occurred while opening the triage view:\n\n"
                          f"{str(error)}\n\n"
                          f"Please try importing the file again.")
            
            # Show error dialog with recovery guidance
            await self._show_error(title, message)
            
            # Reset to initial state for recovery, but keep extracted data
            # so user can retry the transition without re-importing
            await self._reset_for_retry()
            
        except Exception as recovery_error:
            logger.error(f"Error during transition error recovery: {recovery_error}", exc_info=True)
            # Force reset to initial state if error handling fails
            await self._reset_to_initial_state()

    async def _reset_for_retry(self):
        """Reset the interface for retry after transition failure.
        
        This method resets the interface to allow the user to retry the transition
        without losing the extracted transaction data. It maintains the processing
        state but re-enables the interface for user interaction.
        """
        logger.debug("Resetting interface for retry after transition failure")
        
        try:
            # Re-enable the import button for retry
            self.import_button.enabled = True
            self.import_button.text = "Import Statement..."
            
            # Keep the current state as COMPLETED since extraction was successful
            # This allows for potential retry mechanisms in the future
            self._current_state = ImportState.COMPLETED
            
            # Keep workflow context with extracted data for potential retry
            # Remove only the error-specific context
            error_keys = ['transition_error', 'transition_error_context', 'transition_failed_at']
            for key in error_keys:
                self._workflow_context.pop(key, None)
            
            logger.debug("Interface reset for retry - extracted data preserved")
            
        except Exception as reset_error:
            logger.error(f"Error during retry reset: {reset_error}", exc_info=True)
            # Fall back to full reset if retry reset fails
            await self._reset_to_initial_state()

    async def _handle_workflow_error(self, error: Exception, context: str):
        """Handle errors that occur during the import workflow.
        
        Provides specialized error handling for workflow-related errors,
        ensuring graceful recovery and appropriate user feedback.
        
        Args:
            error: The exception that occurred
            context: Description of the context where the error occurred
        """
        logger.error(f"Workflow error in {context}: {error}", exc_info=True)
        
        try:
            # Update state to indicate error
            self._current_state = ImportState.ERROR
            
            # Show user-friendly error message
            await self._show_error(
                "Import Workflow Error",
                f"{context}:\n\n{str(error)}\n\n"
                f"The import process has been reset. Please try again."
            )
            
            # Reset to initial state for recovery
            await self._reset_to_initial_state()
            
        except Exception as recovery_error:
            logger.error(f"Error during workflow error recovery: {recovery_error}", exc_info=True)
            # Force reset even if error handling fails
            self._current_state = ImportState.INITIAL
            self._selected_file = None
            self._import_config = None
            self._workflow_context.clear()

    def get_current_state(self) -> ImportState:
        """Get the current state of the import workflow.
        
        Returns:
            ImportState: Current workflow state
        """
        return self._current_state

    def get_workflow_context(self) -> Dict[str, Any]:
        """Get the current workflow context information.
        
        Returns:
            Dict[str, Any]: Copy of current workflow context
        """
        return self._workflow_context.copy()

def show_importer_window(app: toga.App):
    """Show the importer window."""
    # Check if there's already a window open
    existing_window = None
    for window in app.windows:
        if isinstance(window, ImporterWindow):
            existing_window = window
            break

    if existing_window:
        app.current_window = existing_window
        return

    try:
        importer_window = ImporterWindow()
        importer_window.show()
    except Exception as e:
        logger.error(f"Error showing importer window: {e}", exc_info=True)
        for window in app.windows:
            if isinstance(window, ImporterWindow):
                app.windows.discard(window)
                break

        if app.main_window:
            window = cast(toga.Window, app.main_window)
            asyncio.create_task(
                window.dialog(
                    toga.ErrorDialog(
                        "Error",
                        f"Could not open importer window: {str(e)}"
                    )
                )
            )