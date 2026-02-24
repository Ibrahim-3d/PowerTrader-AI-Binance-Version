#!/usr/bin/env python3
"""
PowerTrader AI+ Repository Reorganization Script
Moves Python modules from root to app/ directory for better organization.
"""

import os
import shutil
from pathlib import Path


def reorganize_repository():
    """Move Python files from root to app/ directory."""

    # Files that should stay in root (configuration, setup, docs)
    keep_in_root = {
        "setup.py",
        "requirements.txt",
        "README.md",
        "LICENSE",
        ".gitignore",
        ".pre-commit-config.yaml",
        "verify_implementation.py",  # Keep this as it's likely a repo verification script
        "reorganize_repo.py",  # Don't move the reorganization script itself
    }

    # Get all Python files in root
    root_dir = Path(".")
    app_dir = Path("./app")

    # Ensure app directory exists
    app_dir.mkdir(exist_ok=True)

    files_to_move = []
    files_kept = []

    print("🔍 Scanning root directory for Python files...")

    for file_path in root_dir.glob("*.py"):
        filename = file_path.name

        if filename not in keep_in_root:
            files_to_move.append(filename)
        else:
            files_kept.append(filename)

    print(f"\n📁 Found {len(files_to_move)} files to move to app/")
    print(f"📁 Keeping {len(files_kept)} files in root")

    # Show what will be moved
    if files_to_move:
        print("\n📦 Files to move to app/:")
        for filename in sorted(files_to_move):
            print(f"  • {filename}")

    if files_kept:
        print("\n🏠 Files staying in root:")
        for filename in sorted(files_kept):
            print(f"  • {filename}")

    # Auto-proceed with reorganization
    print(f"\n🚀 Proceeding with reorganization...")

    # Move files
    print(f"\n🚀 Moving files...")
    moved_count = 0

    for filename in files_to_move:
        src = root_dir / filename
        dst = app_dir / filename

        try:
            # Check if destination already exists
            if dst.exists():
                print(f"⚠️  {filename} already exists in app/ - skipping")
                continue

            shutil.move(str(src), str(dst))
            print(f"✅ {filename}")
            moved_count += 1

        except Exception as e:
            print(f"❌ Error moving {filename}: {e}")

    print(f"\n🎉 Successfully moved {moved_count} files to app/")

    # Update any import statements if needed
    print("\n📝 Checking for import updates needed...")
    check_imports()


def check_imports():
    """Check for import statements that might need updating."""
    import_issues = []

    app_dir = Path("./app")

    for py_file in app_dir.glob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Look for imports of moved files
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if line.strip().startswith(("import ", "from ")):
                    # Check if importing files that were moved
                    if any(
                        moved_file.replace(".py", "") in line
                        for moved_file in [
                            "pt_hub.py",
                            "pt_trader.py",
                            "pt_trainer.py",
                            "pt_thinker.py",
                        ]
                    ):
                        import_issues.append((py_file.name, i, line.strip()))

        except Exception as e:
            print(f"⚠️  Could not check {py_file.name}: {e}")

    if import_issues:
        print(f"⚠️  Found {len(import_issues)} potential import issues:")
        for filename, line_num, line in import_issues:
            print(f"  {filename}:{line_num} - {line}")
    else:
        print("✅ No obvious import issues detected")


if __name__ == "__main__":
    reorganize_repository()
