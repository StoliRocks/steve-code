"""Main entry point for steve-code when run as a module."""

# Write debug to file since stdout might be redirected
import os
debug_file = os.path.expanduser("~/steve-code-debug.log")
with open(debug_file, "a") as f:
    f.write("DEBUG: __main__.py loaded\n")

from .cli import main

if __name__ == "__main__":
    with open(debug_file, "a") as f:
        f.write("DEBUG: __main__.py calling main()\n")
    main()