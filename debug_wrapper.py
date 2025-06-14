#!/usr/bin/env python3
"""Debug wrapper to trace steve-code execution."""

import os
import sys
import traceback

debug_file = os.path.expanduser("~/steve-code-debug.log")

# Clear previous debug log
with open(debug_file, "w") as f:
    f.write("=== Steve Code Debug Log ===\n")
    f.write(f"Python: {sys.version}\n")
    f.write(f"Path: {sys.path}\n")
    f.write("===========================\n\n")

try:
    with open(debug_file, "a") as f:
        f.write("DEBUG: Starting import of ai_code_assistant\n")
    
    # Try to import the package
    import ai_code_assistant
    
    with open(debug_file, "a") as f:
        f.write("DEBUG: Package imported successfully\n")
        f.write(f"DEBUG: Package location: {ai_code_assistant.__file__}\n")
    
    # Try to import cli module
    with open(debug_file, "a") as f:
        f.write("DEBUG: Importing cli module\n")
    
    from ai_code_assistant.cli import main
    
    with open(debug_file, "a") as f:
        f.write("DEBUG: cli.main imported successfully\n")
        f.write("DEBUG: Calling main()\n")
    
    # Call main
    main()
    
except Exception as e:
    with open(debug_file, "a") as f:
        f.write(f"\n\n=== EXCEPTION ===\n")
        f.write(f"Type: {type(e).__name__}\n")
        f.write(f"Message: {str(e)}\n")
        f.write(f"\nTraceback:\n")
        traceback.print_exc(file=f)
    
    # Also print to stderr
    print(f"ERROR: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)