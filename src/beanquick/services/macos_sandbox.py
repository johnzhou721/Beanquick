from __future__ import annotations

__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import sys
import ctypes
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Conditional imports for macOS native APIs
_MACOS_NATIVE_APIS_AVAILABLE = False
try:
    if sys.platform == 'darwin':
        from rubicon.objc import ObjCClass
        from toga_cocoa.libs import NSURL
        NSUserDefaults = ObjCClass("NSUserDefaults")
        NSURLBookmarkCreationWithSecurityScope = 2048  # 1 << 11
        NSURLBookmarkResolutionWithSecurityScope = 1024 # 1 << 10
        _MACOS_NATIVE_APIS_AVAILABLE = True
except ImportError as e:
    # Native APIs not available - will fall back to standard behavior
    logger.warning("macOS native APIs not available, sandbox support disabled: %s", e)
    pass


# NSUserDefaults keys for bookmark storage
BOOKMARK_DATA_KEY = "beanquick_ledger_directory_bookmark"
RELATIVE_FILE_PATH_KEY = "beanquick_ledger_file_relative_path"


def is_macos_sandbox_supported() -> bool:
    """
    Detect if macOS sandbox support is available.
    
    Returns:
        True if running on macOS with native APIs available, False otherwise.
    """
    return _MACOS_NATIVE_APIS_AVAILABLE and sys.platform == 'darwin'


@dataclass
class BookmarkData:
    """
    Data class for managing security-scoped bookmark storage.
    """
    directory_bookmark: bytes
    relative_file_path: str
    
    def to_user_defaults(self) -> None:
        """Store bookmark data in NSUserDefaults."""
        if not is_macos_sandbox_supported():
            return
            
        try:
            defaults = NSUserDefaults.standardUserDefaults
            defaults.setObject_forKey_(self.directory_bookmark, BOOKMARK_DATA_KEY)
            defaults.setObject_forKey_(self.relative_file_path, RELATIVE_FILE_PATH_KEY)
            defaults.synchronize()
        except Exception:
            # Silently fail if bookmark storage fails - this is not critical
            pass
    
    @classmethod
    def from_user_defaults(cls) -> 'BookmarkData | None':
        """Load bookmark data from NSUserDefaults."""
        if not is_macos_sandbox_supported():
            return None
            
        try:
            defaults = NSUserDefaults.standardUserDefaults
            bookmark_data = defaults.objectForKey_(BOOKMARK_DATA_KEY)
            relative_file_path = defaults.objectForKey_(RELATIVE_FILE_PATH_KEY)
            
            if bookmark_data and relative_file_path:
                return cls(ctypes.string_at(bookmark_data.bytes, bookmark_data.length), str(relative_file_path))
            return None
        except Exception as e:
            # Return None if retrieval fails
            return None
    
    @classmethod
    def clear_from_user_defaults(cls) -> None:
        """Clear stored bookmark data from NSUserDefaults."""
        if not is_macos_sandbox_supported():
            return
            
        try:
            defaults = NSUserDefaults.standardUserDefaults
            defaults.removeObjectForKey_(BOOKMARK_DATA_KEY)
            defaults.removeObjectForKey_(RELATIVE_FILE_PATH_KEY)
            defaults.synchronize()
        except Exception:
            # Silently fail if cleanup fails
            pass


class MacOSSandboxService:
    """
    Service for handling macOS sandbox security-scoped bookmarks.
    
    This service manages the creation, storage, and restoration of security-scoped
    bookmarks that allow sandboxed macOS applications to maintain access to
    user-selected files and directories across app launches.
    """
    
    def __init__(self):
        """Initialize the macOS sandbox service."""
        pass
    
    def is_supported(self) -> bool:
        """
        Check if macOS sandbox support is available.
        
        Returns:
            True if running on macOS with native APIs available, False otherwise.
        """
        return is_macos_sandbox_supported()
    
    def create_security_scoped_bookmark(self, directory_url: 'NSURL') -> Optional[bytes]:
        """
        Create a security-scoped bookmark from an NSURL.
        
        Args:
            directory_url: The NSURL of the directory to create a bookmark for
            
        Returns:
            The bookmark data as bytes, or None if creation failed
        """
        if not self.is_supported():
            return None
        
        try:
            # Create security-scoped bookmark
            bookmark_data = directory_url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
                NSURLBookmarkCreationWithSecurityScope,
                None,  # No specific resource keys needed
                None,  # Not relative to another URL
                None   # Error parameter (we'll handle exceptions instead)
            )
            if bookmark_data:
                return ctypes.string_at(bookmark_data.bytes, bookmark_data.length)
            return None
        except Exception:
            return None
    
    def resolve_security_scoped_bookmark(self, bookmark_data: bytes) -> Optional['NSURL']:
        """
        Resolve a security-scoped bookmark to an NSURL.
        
        Args:
            bookmark_data: The bookmark data as bytes
            
        Returns:
            The resolved NSURL, or None if resolution failed (including stale bookmarks)
        """
        if not self.is_supported():
            return None
            
        try:
            # Resolve the bookmark with security scope
            resolved_url = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
                bookmark_data,
                NSURLBookmarkResolutionWithSecurityScope,
                None,  # Not relative to another URL
                None,  # We'll detect staleness through other means
                None   # Error parameter (we'll handle exceptions instead)
            )
            
            # Additional validation: check if the resolved URL actually exists and is accessible
            if resolved_url:
                # Try to access the path to verify the bookmark is still valid
                path_str = str(resolved_url.path)
                path_obj = Path(path_str)
                
                # If the directory doesn't exist, the bookmark is stale
                if not path_obj.exists() or not path_obj.is_dir():
                    return None
            
            return resolved_url
        except Exception as e:
            # Return None if bookmark resolution fails for any reason
            # This includes cases where the bookmark data is corrupted, invalid, or stale
            # Log the error but don't show it to user as this is expected for stale bookmarks
            logger.warning("Bookmark resolution failed: %s", e)
            return None
    
    def start_accessing_security_scoped_resource(self, url: 'NSURL') -> bool:
        """
        Start accessing a security-scoped resource.
        
        Args:
            url: The NSURL to start accessing
            
        Returns:
            True if access was successfully started, False otherwise
        """
        if not self.is_supported():
            return False
            
        try:
            return bool(url.startAccessingSecurityScopedResource())
        except Exception as e:
            # Log the error but don't show it to user as this might be expected in some cases
            logger.warning("Failed to start accessing security-scoped resource: %s", e)
            return False
    
    def stop_accessing_security_scoped_resource(self, url: 'NSURL') -> None:
        """
        Stop accessing a security-scoped resource.
        
        Args:
            url: The NSURL to stop accessing
        """
        if not self.is_supported():
            return
            
        try:
            url.stopAccessingSecurityScopedResource()
        except AttributeError as e:
            # Handle missing native API methods - log but don't show error to user
            logger.debug("Native security-scoped resource API not available: %s", e)
        except Exception as e:
            # Log the error but don't show it to user as this is cleanup code
            logger.warning("Failed to stop accessing security-scoped resource: %s", e)
            pass
    
    def store_bookmark_data(self, bookmark_data: bytes, relative_file_path: str) -> None:
        """
        Store bookmark data and relative file path in NSUserDefaults.
        
        Args:
            bookmark_data: The security-scoped bookmark data as bytes
            relative_file_path: The relative path to the ledger file within the bookmarked directory
        """
        bookmark = BookmarkData(bookmark_data, relative_file_path)
        bookmark.to_user_defaults()
    
    def retrieve_bookmark_data(self) -> Optional[tuple[bytes, str]]:
        """
        Retrieve bookmark data and relative file path from NSUserDefaults.
        
        Returns:
            A tuple of (bookmark_data, relative_file_path) if both exist, None otherwise
        """
        bookmark = BookmarkData.from_user_defaults()
        if bookmark:
            return (bookmark.directory_bookmark, bookmark.relative_file_path)
        return None
    
    def clear_stored_bookmark(self) -> None:
        """
        Clear stored bookmark data and relative file path from NSUserDefaults.
        """
        BookmarkData.clear_from_user_defaults()
    
    def restore_access_from_bookmark(self) -> Optional[tuple[Path, 'NSURL']]:
        """
        Try to restore directory access from a stored security-scoped bookmark.
        
        Returns:
            A tuple of (full_file_path, directory_url) if restoration succeeded, None otherwise.
            The directory_url should be used to stop accessing the resource when done.
        """
        if not self.is_supported():
            return None
            
        # Retrieve stored bookmark data
        bookmark_info = self.retrieve_bookmark_data()
        if not bookmark_info:
            return None
            
        bookmark_data, relative_file_path = bookmark_info
        
        # Resolve the bookmark to get the directory URL
        directory_url = self.resolve_security_scoped_bookmark(bookmark_data)
        if not directory_url:
            # Bookmark is stale or invalid, clear it automatically
            self.clear_stored_bookmark()
            return None
        
        # Start accessing the security-scoped resource
        if not self.start_accessing_security_scoped_resource(directory_url):
            # Failed to start accessing, clear the bookmark automatically
            self.clear_stored_bookmark()
            return None
        
        try:
            # Convert NSURL to Path and construct full file path
            directory_path = Path(str(directory_url.path))
            full_file_path = directory_path / relative_file_path
            
            # Verify the file still exists
            if full_file_path.exists() and full_file_path.is_file():
                return (full_file_path, directory_url)
            else:
                # File no longer exists, clear the bookmark automatically
                self.stop_accessing_security_scoped_resource(directory_url)
                self.clear_stored_bookmark()
                return None
                
        except Exception as e:
            # Error constructing or checking file path, clear the bookmark automatically
            self.stop_accessing_security_scoped_resource(directory_url)
            self.clear_stored_bookmark()
            return None
    
    def create_bookmark_for_file_selection(self, directory_url: 'NSURL', file_path: Path) -> None:
        """
        Create and store a security-scoped bookmark for a file selection.
        
        This is a convenience method that handles the common pattern of creating
        a bookmark for a parent directory when a file is selected.
        
        Args:
            directory_url: The NSURL of the selected directory
            file_path: The Path object of the selected file
        """
        if not self.is_supported():
            return
            
        try:
            # Create security-scoped bookmark for the parent directory
            bookmark_data = self.create_security_scoped_bookmark(directory_url)
            if bookmark_data:
                # Calculate relative path from parent directory to the selected file
                directory_path = Path(str(directory_url.path))
                relative_file_path = file_path.relative_to(directory_path)
                
                # Store bookmark data and relative file path
                self.store_bookmark_data(bookmark_data, str(relative_file_path))
        except Exception as e:
            # If bookmark creation fails, log but don't raise
            logger.warning("Failed to create security-scoped bookmark: %s", e)
    
    def try_restore_ledger_access(self) -> Optional[Path]:
        """
        High-level method to try restoring ledger access from stored bookmark.
        
        This method encapsulates the complete restoration flow including error handling
        and logging, providing a clean interface for application code.
        
        Returns:
            The Path to the restored ledger file if successful, None otherwise
        """
        if not self.is_supported():
            return None
            
        try:
            result = self.restore_access_from_bookmark()
            if result:
                restored_path, directory_url = result
                logger.info(f"Successfully restored ledger access from bookmark: {restored_path}")
                return restored_path
            else:
                logger.debug("No valid bookmark found or bookmark restoration failed")
                return None
        except Exception as e:
            logger.error(f"Error during bookmark restoration: {e}", exc_info=True)
            return None


# Global service instance
_sandbox_service = MacOSSandboxService()


def get_sandbox_service() -> MacOSSandboxService:
    """
    Get the global macOS sandbox service instance.
    
    Returns:
        The singleton MacOSSandboxService instance
    """
    return _sandbox_service