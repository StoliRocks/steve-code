# v0.2.5: Bug Fixes and Update Improvements

## 🐛 Bug Fixes

- **Fixed interactive mode exit bug**: Program no longer exits when tkinter is missing
- **Fixed syntax errors**: Corrected indentation issues in interactive.py
- **Improved pyautogui handling**: Screenshot functionality now gracefully degrades

## 🚀 Improvements

- **Better update notifications**: Updates are now checked after 5 seconds on startup
- **Background update checks**: Automatically checks every 30 minutes while running
- **Added `/check-update` command**: Debug command to manually check for updates
- **Improved error handling**: More robust handling of missing dependencies

## 🔧 Technical Changes

- Lazy loading of ScreenshotCapture to prevent import-time failures
- Subprocess-based tkinter detection to avoid sys.exit() calls
- Fixed exception handler indentation in interactive mode
- Enhanced update checker with force refresh and debug logging

## 📝 Notes

- Screenshot functionality requires pyautogui and tkinter (optional)
- Update notifications will appear automatically when new versions are available
- Use `/update` in interactive mode or `sc --update` to install updates

## Installation

```bash
pip install --upgrade git+https://github.com/StoliRocks/steve-code.git@v0.2.5
```