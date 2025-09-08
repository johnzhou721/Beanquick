"""
Alipay CSV Importer

This module provides a comprehensive importer for Alipay CSV statements.
It implements the BeanquickImporter interface to work directly with
TransactionData objects and handles the complex Alipay CSV format.
"""

import csv
import chardet
import logging
from pathlib import Path
from typing import Set, List, Optional
from datetime import datetime
from decimal import Decimal

from ...core.abc import BeanquickImporter
from ...core.exceptions import DataExtractionError
from ...core.data import TransactionData, ImporterMetadata, ImporterCapability

logger = logging.getLogger(__name__)

# Maximum number of bytes to read in order to detect the encoding of a file.
HEAD_DETECT_MAX_BYTES = 128 * 1024

class AlipayCSVImporter(BeanquickImporter):
    """Comprehensive importer for Alipay CSV statements.
    
    This importer implements the BeanquickImporter interface to work directly
    with TransactionData objects. It identifies Alipay CSV files by checking
    for specific Chinese column headers and handles the complex multi-section
    format of Alipay export files.
    
    Expected CSV format:
    - Encoding: UTF-8 or GBK (Chinese encoding)
    - Complex header section with metadata (ignored during processing)
    - Headers must include: 交易时间, 交易对方, 商品说明, 收/支, 金额
    - Date format: YYYY-MM-DD HH:MM:SS
    - Amount format: Decimal numbers, may include commas
    - Transaction direction: 收入/支出/不计收支
    """
    
    # Expected column headers for Alipay CSV files
    EXPECTED_HEADERS: Set[str] = {'交易时间', '交易对方', '商品说明', '收/支', '金额'}
    
    # Additional headers that help with identification
    SECONDARY_HEADERS: Set[str] = {'交易分类', '交易状态', '收/付款方式'}
    
    def __init__(self, default_account: str = "Assets:Alipay"):
        """Initialize the Alipay importer.
        
        Args:
            default_account: The default account name to use for transactions.
                           Defaults to "Assets:Alipay"
        """
        super().__init__(default_account)
        self.metadata = ImporterMetadata(
            name="Alipay CSV Importer",
            icon="alipay_logo.svg",
            description="Import Alipay transaction CSV files",
            region="china",
            institution="alipay",
            supported_file_types={".csv"},
            capabilities={
                ImporterCapability.BASIC_TRANSACTIONS,
                ImporterCapability.DIGITAL_WALLET
            },
            default_account_prefix="Assets:Alipay",
            currency="CNY",
            priority=10
        )
        logger.debug(f"Initialized AlipayCSVImporter with account: {default_account}")
    
    def _detect_file_encoding(self, filepath: str) -> str:
        """Detect the encoding of a file using chardet with robust validation.
        
        This method attempts to detect the file encoding automatically, with
        special handling for Chinese encodings commonly used in Alipay files.
        It validates the detected encoding by trying to read the entire file.
        
        Args:
            filepath: String path to the file to analyze
            
        Returns:
            str: The detected encoding name
            
        Raises:
            DataExtractionError: If encoding cannot be determined
        """
        try:
            # Read a sample of the file for encoding detection
            with open(filepath, 'rb') as f:
                raw_data = f.read(HEAD_DETECT_MAX_BYTES)
                
            if not raw_data:
                raise DataExtractionError(
                    "File is empty",
                    file_path=filepath,
                    importer_name=self.__class__.__name__
                )
            
            # Use chardet for automatic detection
            detection_result = chardet.detect(raw_data)
            detected_encoding = detection_result.get('encoding')
            confidence = detection_result.get('confidence', 0)
            
            logger.debug(f"Chardet detected encoding: {detected_encoding} "
                        f"(confidence: {confidence:.2f}) for file: {Path(filepath).name}")
            
            # Always try to validate encodings by attempting to read the entire file
            # Priority order: chardet result first, then fallbacks
            encodings_to_try = []
            if detected_encoding:
                encodings_to_try.append(detected_encoding)
            
            # Add common Chinese encodings as fallbacks
            fallback_encodings = ['gbk', 'gb2312', 'gb18030', 'utf-8', 'utf-8-sig']
            for enc in fallback_encodings:
                if enc not in encodings_to_try:
                    encodings_to_try.append(enc)
            
            # Try each encoding and validate by reading the entire file
            for encoding in encodings_to_try:
                try:
                    # Test if we can read the entire file with this encoding
                    with open(filepath, 'r', encoding=encoding) as f:
                        # Read the entire file to validate encoding works throughout
                        f.read()
                    logger.debug(f"Successfully validated encoding: {encoding}")
                    return encoding
                except UnicodeDecodeError as e:
                    logger.debug(f"Encoding {encoding} failed: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Unexpected error with encoding {encoding}: {e}")
                    continue
            
            # If all encodings fail, raise detailed error
            raise DataExtractionError(
                "Could not determine file encoding",
                file_path=filepath,
                importer_name=self.__class__.__name__,
                details=f"Chardet detected: {detected_encoding} (confidence: {confidence:.2f}), "
                       f"tried encodings: {encodings_to_try}"
            )
            
        except FileNotFoundError:
            raise DataExtractionError(
                f"File not found: {filepath}",
                file_path=filepath,
                importer_name=self.__class__.__name__
            )
        except PermissionError:
            raise DataExtractionError(
                f"Permission denied reading file: {filepath}",
                file_path=filepath,
                importer_name=self.__class__.__name__
            )
        except Exception as e:
            raise DataExtractionError(
                f"Error detecting file encoding: {str(e)}",
                file_path=filepath,
                importer_name=self.__class__.__name__
            ) from e
    
    def _find_data_start_line(self, filepath: str, encoding: str) -> Optional[int]:
        """Find the line number where the actual CSV data starts.
        
        Alipay CSV files have a complex header section with metadata.
        This method finds where the actual transaction data begins.
        
        Args:
            filepath: String path to the file to analyze
            encoding: File encoding to use
            
        Returns:
            Optional[int]: Line number where data starts, or None if not found
        """
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                for line_num, line in enumerate(f, 1):
                    # Look for the line that contains our expected headers
                    if '交易时间' in line and '交易对方' in line and '金额' in line:
                        logger.debug(f"Found data header at line {line_num}")
                        return line_num
            
            logger.debug("Could not find data header line in file")
            return None
            
        except Exception as e:
            logger.debug(f"Error finding data start line: {e}")
            return None
    
    def _check_alipay_indicators(self, filepath: str, encoding: str) -> bool:
        """Check for Alipay-specific indicators in the file.
        
        This method looks for content patterns that are specific to Alipay
        export files to increase identification confidence.
        
        Args:
            filepath: String path to the file
            encoding: File encoding to use
            
        Returns:
            bool: True if Alipay indicators are found
        """
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                # Read first 10 lines to look for Alipay indicators
                content = ''.join(f.readline() for _ in range(10))
                
                # Look for Alipay-specific terms
                alipay_indicators = [
                    '支付宝账户',  # Alipay account
                    '支付宝交易',  # Alipay transaction details
                ]
                
                for indicator in alipay_indicators:
                    if indicator.lower() in content.lower():
                        logger.debug(f"Found Alipay indicator: {indicator}")
                        return True
                
                return False
                
        except Exception as e:
            logger.debug(f"Error checking Alipay indicators: {e}")
            return False

    def identify(self, filepath: str) -> bool:
        """Identifies Alipay CSV files by checking headers efficiently.
        
        This method performs identification by:
        1. Checking if the file has a .csv extension
        2. Detecting encoding and searching for Alipay-specific headers
        3. Handling the complex multi-section format of Alipay files
        4. Returning False for any errors without raising exceptions
        
        Args:
            filepath: String path to the file to identify
            
        Returns:
            bool: True if this importer can handle the file, False otherwise
        """
        try:
            # Convert to Path object for easier manipulation
            file_path = Path(filepath)
            
            # Quick check: must be a CSV file
            if file_path.suffix.lower() != '.csv':
                logger.debug(f"File {file_path.name} rejected: not a CSV file")
                return False
            
            # Check if file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                logger.debug(f"File {filepath} rejected: does not exist or is not a file")
                return False
            
            # Detect file encoding automatically
            try:
                encoding = self._detect_file_encoding(filepath)
                logger.debug(f"Using encoding {encoding} for file {file_path.name}")
            except DataExtractionError:
                logger.debug(f"File {file_path.name} rejected: could not detect encoding")
                return False
            
            # Find where the actual CSV data starts
            data_start_line = self._find_data_start_line(filepath, encoding)
            if data_start_line is None:
                logger.debug(f"File {file_path.name} rejected: could not find CSV data section")
                return False
            
            # Read the header line to check for expected columns
            with open(filepath, 'r', encoding=encoding) as f:
                # Skip to the data section
                for _ in range(data_start_line - 1):
                    next(f, None)
                
                # Read the header line
                header_line = next(f, '')
                if not header_line:
                    logger.debug(f"File {file_path.name} rejected: empty header line")
                    return False
                
                # Parse headers using CSV reader to handle proper comma splitting
                headers = next(csv.reader([header_line]), [])
            
            # Clean headers by stripping whitespace and filtering empty ones
            cleaned_headers = {header.strip() for header in headers if header.strip()}
            
            # Check if required headers are present
            has_required_headers = self.EXPECTED_HEADERS.issubset(cleaned_headers)
            
            # Additional check for secondary headers to increase confidence
            has_secondary_headers = bool(self.SECONDARY_HEADERS.intersection(cleaned_headers))
            
            # Also check for Alipay-specific content patterns
            has_alipay_indicators = self._check_alipay_indicators(filepath, encoding)
            
            # File is identified as Alipay if it has required headers and either
            # secondary headers or Alipay-specific indicators
            is_alipay = has_required_headers and (has_secondary_headers or has_alipay_indicators)
            
            if is_alipay:
                logger.info(f"File {file_path.name} identified as Alipay CSV")
            else:
                logger.debug(f"File {file_path.name} rejected: missing required headers or indicators. "
                           f"Required: {self.EXPECTED_HEADERS}, Secondary: {self.SECONDARY_HEADERS}, "
                           f"Found: {cleaned_headers}")
            
            return is_alipay
            
        except UnicodeDecodeError:
            # File encoding detection failed during reading
            logger.debug(f"File {filepath} rejected: encoding issue during reading")
            return False
        except PermissionError:
            # Cannot read file due to permissions
            logger.debug(f"File {filepath} rejected: permission denied")
            return False
        except Exception as e:
            # Any other error during identification means this importer can't handle the file
            logger.debug(f"File {filepath} rejected due to error during identification: {e}")
            return False
    
    def extract(self, filepath: str) -> List[TransactionData]:
        """Extract transactions from the file as TransactionData objects.
        
        This method parses the Alipay CSV file and converts each transaction row
        into a TransactionData object, handling the complex multi-section format
        and robust encoding detection.
        
        Args:
            filepath: String path to the CSV file to extract from
            
        Returns:
            List[TransactionData]: List of TransactionData objects
            
        Raises:
            DataExtractionError: If the file cannot be parsed or contains invalid data
        """
        try:
            transactions = []
            file_path = Path(filepath)
            
            logger.info(f"Starting TransactionData extraction from {file_path.name}")
            
            # Detect file encoding automatically with robust fallback handling
            encoding = self._detect_file_encoding(filepath)
            logger.debug(f"Using encoding {encoding} for extraction from {file_path.name}")
            
            # Find where the actual CSV data starts
            data_start_line = self._find_data_start_line(filepath, encoding)
            if data_start_line is None:
                raise DataExtractionError(
                    "Could not find CSV data section in Alipay file",
                    file_path=filepath,
                    importer_name=self.__class__.__name__,
                    details="File appears to be missing the transaction data section"
                )
            
            # Open file with detected encoding for Chinese characters
            with open(filepath, 'r', encoding=encoding, errors='strict') as f:
                # Skip to the data section
                for _ in range(data_start_line - 1):
                    next(f, None)
                
                # Create CSV reader from the data section
                reader = csv.DictReader(f)
                
                # Clean up fieldnames to remove empty column names and strip whitespace
                if reader.fieldnames:
                    reader.fieldnames = [name.strip() for name in reader.fieldnames if name.strip()]
                
                # Validate that required columns are present
                if not self.EXPECTED_HEADERS.issubset(set(reader.fieldnames or [])):
                    missing_headers = self.EXPECTED_HEADERS - set(reader.fieldnames or [])
                    raise DataExtractionError(
                        f"Missing required columns in CSV file: {missing_headers}",
                        file_path=filepath,
                        importer_name=self.__class__.__name__,
                        details=f"Expected headers: {self.EXPECTED_HEADERS}, Found: {set(reader.fieldnames or [])}"
                    )
                
                for row_index, row in enumerate(reader, start=data_start_line + 1):
                    try:
                        # Skip empty rows or rows with missing essential data
                        if not row.get('交易时间', '').strip() or not row.get('金额', '').strip():
                            logger.debug(f"Row {row_index}: Skipping row with missing essential data")
                            continue
                        
                        # Parse transaction datetime (expecting YYYY-MM-DD HH:MM:SS format)
                        datetime_str = str(row['交易时间']).strip()
                        
                        try:
                            # Parse full datetime and extract date
                            transaction_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                            transaction_date = transaction_datetime.date()
                        except ValueError:
                            # Try alternative datetime formats if needed
                            try:
                                transaction_datetime = datetime.strptime(datetime_str, '%Y/%m/%d %H:%M:%S')
                                transaction_date = transaction_datetime.date()
                            except ValueError:
                                raise DataExtractionError(
                                    f"Invalid datetime format in row {row_index}: '{datetime_str}'",
                                    file_path=filepath,
                                    importer_name=self.__class__.__name__,
                                    details=f"Expected format: YYYY-MM-DD HH:MM:SS or YYYY/MM/DD HH:MM:SS"
                                )
                        
                        # Extract counterparty (payee)
                        counterparty = str(row.get('交易对方', '')).strip()
                        if not counterparty:
                            counterparty = "Unknown Counterparty"
                        
                        # Extract product description for narration
                        product_desc = str(row.get('商品说明', '')).strip()
                        transaction_category = str(row.get('交易分类', '')).strip()
                        
                        # Build comprehensive narration
                        narration_parts = []
                        if product_desc:
                            narration_parts.append(product_desc)
                        if transaction_category and transaction_category != product_desc:
                            narration_parts.append(f"[{transaction_category}]")
                        
                        narration = " - ".join(narration_parts) if narration_parts else counterparty
                        
                        # Parse amount (handle comma removal and negative values)
                        amount_str = str(row['金额']).strip()
                        
                        # Remove commas and handle different comma types
                        amount_str = amount_str.replace(',', '').replace('，', '')
                        
                        try:
                            # Convert to Decimal for precise financial calculations
                            transaction_amount = Decimal(amount_str)
                        except (ValueError, TypeError) as e:
                            raise DataExtractionError(
                                f"Invalid amount format in row {row_index}: '{amount_str}'",
                                file_path=filepath,
                                importer_name=self.__class__.__name__,
                                details=f"Amount parsing error: {str(e)}"
                            )
                        
                        # Determine transaction direction and adjust amount accordingly
                        transaction_direction = str(row.get('收/支', '')).strip()
                        
                        # For expenses (支出), we typically want positive amounts
                        # For income (收入), we also want positive amounts
                        # The direction will be handled in the account assignment
                        final_amount = abs(transaction_amount)
                        
                        # Create comprehensive metadata for the transaction
                        # Filter out empty keys and values from the original row data, and strip whitespace
                        filtered_row = {
                            str(k).strip(): str(v).strip() 
                            for k, v in row.items() 
                            if k is not None and str(k).strip()
                        }
                        
                        metadata = {
                            'original_row': filtered_row,  # Preserve filtered data for debugging
                            'importer': self.__class__.__name__,
                            'source_file': filepath,
                            'row_number': row_index,
                            'transaction_direction': transaction_direction,
                            'transaction_category': transaction_category,
                            'transaction_status': str(row.get('交易状态', '')).strip(),
                            'payment_method': str(row.get('收/付款方式', '')).strip(),
                            'counterparty_account': str(row.get('对方账号', '')).strip()
                        }
                        
                        # Create TransactionData object
                        transaction_data = TransactionData(
                            date=transaction_date,
                            payee=counterparty,
                            narration=narration,
                            amount=final_amount,
                            currency='CNY',
                            metadata=metadata
                        )
                        
                        # Store account information in metadata for later use
                        # metadata is guaranteed to be a dict after __post_init__
                        assert transaction_data.metadata is not None
                        transaction_data.metadata['source_account'] = self.default_account
                        
                        # Determine default account based on transaction direction
                        if transaction_direction == '收入':
                            # For income, default to Income account (no rule needed initially)
                            transaction_data.metadata['destination_account'] = "Income:Alipay"
                        elif transaction_direction == '支出':
                            # For expenses, set a default that can be overridden by rules
                            if transaction_category:
                                # Use transaction category for better default categorization
                                transaction_data.metadata['destination_account'] = f"Expenses:{transaction_category}"
                            else:
                                transaction_data.metadata['destination_account'] = "Expenses:Unknown"
                        
                        transactions.append(transaction_data)
                        
                    except DataExtractionError:
                        # Re-raise DataExtractionError as-is
                        raise
                    except Exception as e:
                        # Wrap unexpected errors in DataExtractionError
                        raise DataExtractionError(
                            f"Error processing row {row_index}",
                            file_path=filepath,
                            importer_name=self.__class__.__name__,
                            details=f"Row data: {dict(row)}\nError: {str(e)}"
                        ) from e
            
            logger.info(f"Successfully extracted {len(transactions)} TransactionData objects from {file_path.name}")
            return transactions
            
        except DataExtractionError:
            # Re-raise DataExtractionError as-is
            raise
        except UnicodeDecodeError as e:
            raise DataExtractionError(
                "File encoding error - unable to read Chinese characters",
                file_path=filepath,
                importer_name=self.__class__.__name__,
                details=f"Encoding error during extraction: {str(e)}"
            ) from e
        except FileNotFoundError:
            raise DataExtractionError(
                f"File not found: {filepath}",
                file_path=filepath,
                importer_name=self.__class__.__name__
            )
        except PermissionError:
            raise DataExtractionError(
                f"Permission denied reading file: {filepath}",
                file_path=filepath,
                importer_name=self.__class__.__name__
            )
        except Exception as e:
            # Catch any other unexpected errors
            raise DataExtractionError(
                f"Unexpected error during TransactionData extraction",
                file_path=filepath,
                importer_name=self.__class__.__name__,
                details=str(e)
            ) from e
    
    @property
    def name(self) -> str:
        """Human-readable name for this importer."""
        if self.metadata:
            return self.metadata.name
        return "Alipay CSV Importer"
