#!/usr/bin/env python3
"""
Installation verification script for the Spot Hedging Bot.
Run this to ensure all dependencies are properly installed.
"""

import sys
import importlib
from typing import List, Tuple

def check_package(package_name: str, import_name: str = None) -> Tuple[str, bool, str]:
    """Check if a package is installed and importable."""
    if import_name is None:
        import_name = package_name
    
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'unknown')
        return package_name, True, version
    except ImportError as e:
        return package_name, False, str(e)

def main():
    """Run installation verification."""
    print("🔍 Verifying Spot Hedging Bot Installation...")
    print("=" * 50)
    
    # Core packages to check
    packages = [
        ("numpy", None),
        ("pandas", None),
        ("scipy", None),
        ("yfinance", None),
        ("ccxt", None),
        ("telegram", None),
        ("sqlalchemy", None),
        ("yaml", "yaml"),
        ("loguru", None),
        ("aiohttp", None),
        ("matplotlib", None),
        ("plotly", None),
        ("pytest", None),
    ]
    
    print(f"🐍 Python Version: {sys.version}")
    print("-" * 50)
    
    failed_packages = []
    
    for package, import_name in packages:
        name, success, version = check_package(package, import_name)
        
        if success:
            print(f"✅ {name:<15} - v{version}")
        else:
            print(f"❌ {name:<15} - FAILED: {version}")
            failed_packages.append(name)
    
    print("-" * 50)
    
    if failed_packages:
        print(f"❌ {len(failed_packages)} packages failed to import:")
        for pkg in failed_packages:
            print(f"   - {pkg}")
        print("\n💡 Try: pip install -r requirements.txt")
        return False
    else:
        print("✅ All core packages installed successfully!")
        print("🚀 Ready to proceed to Step 2!")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
