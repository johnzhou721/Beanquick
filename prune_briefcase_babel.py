# prune_briefcase_babel.py
import sys
import shutil
from pathlib import Path

# --- Configuration ---
# Define the locales you want to KEEP.
# This should match the languages your Toga app supports.
LOCALES_TO_KEEP = {'en', 'ja', 'zh'} # Example: Keep English and Japanese

def prune_babel_locales(app_packages_path: Path):
    """
    Finds the Babel installation in a briefcase app_packages directory
    and prunes its locale data.
    """
    if not app_packages_path.is_dir():
        print(f"Error: Provided path '{app_packages_path}' is not a valid directory.")
        sys.exit(1)

    # The babel data is inside the babel package itself
    localedata_path = app_packages_path / 'babel' / 'locale-data'

    if not localedata_path.is_dir():
        print(f"Error: Babel localedata directory not found at '{localedata_path}'")
        print("Did you run 'briefcase build' first? Is 'babel' in your requirements?")
        sys.exit(1)

    print(f"Found Babel localedata at: {localedata_path}")
    
    deleted_count = 0
    for f in localedata_path.iterdir():
        # Keep files whose stem matches or starts with any of the LOCALES_TO_KEEP
        if f.suffix == '.dat':
            keep = False
            for locale in LOCALES_TO_KEEP:
                if f.stem == locale or f.stem.startswith(locale + '_'):
                    keep = True
                    break
            if not keep:
                print(f"  Deleting {f.name}...")
                f.unlink()  # Delete the file
                deleted_count += 1
    if deleted_count > 0:
        print(f"\nPruning complete. Deleted {deleted_count} unused locale files.")
    else:
        print("\nNo unused locale files to delete.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python prune_briefcase_babel.py <path_to_app_packages_dir>")
        sys.exit(1)
        
    target_path = Path(sys.argv[1])
    prune_babel_locales(target_path)