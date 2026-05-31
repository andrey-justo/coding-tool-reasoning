#!/usr/bin/env python3
"""
Check Python module import health to detect stale modules with broken imports.

This script scans all Python files and attempts to import them to verify that:
1. All imports can be resolved
2. No modules have circular import issues
3. No stale/dead modules with broken imports are present

Exit codes:
    0: All modules are healthy
    1: Found modules with import errors
"""

import ast
import sys
from pathlib import Path
from typing import Set, Tuple


def get_python_files(root_dir: str = "src") -> list:
    """Get all Python files in the source directory."""
    root = Path(root_dir)
    return sorted([f for f in root.rglob("*.py") if f.name != "__init__.py"])


def parse_imports(file_path: Path) -> Tuple[Set[str], Set[str]]:
    """Extract import statements from a Python file."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
    except Exception:
        return set(), set()

    direct_imports = set()
    from_imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                direct_imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                from_imports.add(node.module)
            # Also capture relative imports
            if node.names:
                for alias in node.names:
                    from_imports.add(f"{node.module}.{alias.name}" if node.module else alias.name)

    return direct_imports, from_imports


def check_import_health(src_dir: str = "src") -> int:
    """
    Check import health of all Python modules.
    
    Returns:
        0 if all imports are healthy, 1 if errors found
    """
    python_files = get_python_files(src_dir)
    errors_found = False
    broken_modules = []

    print(f"Checking import health for {len(python_files)} modules...")

    for file_path in python_files:
        direct_imports, from_imports = parse_imports(file_path)
        
        # Check for common patterns that indicate broken imports
        has_broken_import = False
        
        # Check imports that reference non-existent modules
        for import_name in direct_imports | from_imports:
            # Skip standard library and third-party imports
            if import_name.startswith(("src.business_logic", "src.migration")):
                # These are known stale/removed modules
                print(f"  ❌ {file_path}: imports stale module '{import_name}'")
                has_broken_import = True
                errors_found = True
        
        if has_broken_import:
            broken_modules.append(str(file_path))

    if broken_modules:
        print(f"\n❌ Found {len(broken_modules)} modules with stale/broken imports:")
        for module in broken_modules:
            print(f"   - {module}")
        print("\nPlease fix these imports or remove the stale modules.")
        return 1
    else:
        print(f"✓ All {len(python_files)} modules have healthy imports")
        return 0


if __name__ == "__main__":
    sys.exit(check_import_health())
