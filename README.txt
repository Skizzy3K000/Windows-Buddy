WINDOWS BUDDY 0.1.0
===================

WHAT IT IS
A lightweight Python/Tkinter desktop assistant with retro mini-window pop-ups.
The pop-ups are separate rectangular windows with title bars and buttons, not speech
bubbles or notification balloons.

REQUIREMENTS
- Windows 10/11
- Python 3.13 (install from python.org and tick "Add python.exe to PATH")
- Tkinter (included with the standard Windows Python installer)
- Optional packages: psutil, pystray, Pillow

INSTALL FROM SOURCE
1. Extract this ZIP to a folder, e.g. Desktop\Windows_Buddy.
2. Open Command Prompt in that folder.
3. Run:
   python -m pip install -r requirements.txt
4. Start:
   python windows_buddy.py

If optional packages fail to install, try:
   python -m pip install psutil pystray Pillow

SYSTEM TRAY
Install pystray and Pillow for the tray icon. Clicking X hides Buddy to the tray
when tray support is available and "Minimise to tray" is enabled in Permissions.
Use the tray icon menu to reopen Buddy or quit it. If tray support is unavailable,
Buddy warns before hiding/quitting. Timers/reminders only run while Buddy's process
is running; they are not scheduled as Windows background tasks.

POP-UP WINDOWS
Classic compact rectangular mini-windows are used for timers, reminders, errors,
and security alerts. Notifications can be disabled in Permissions. Security checks
only read Windows Defender status and do not scan files or replace antivirus.

OFFLINE COMMANDS
help, time, date, stats, joke, open notepad, open calculator
timer 5m
remind 10m Take a break
Delay formats: 30s, 5m, 2h (maximum 7 days).

API KEYS
OpenAI and Gemini keys are saved in %APPDATA%\WindowsBuddy\settings.json.
This file is local but not encrypted. Keep your Windows account secure and delete
the key in API Keys then save if you no longer want it stored. API test checks
connectivity/authentication; the current chat intentionally uses the offline
response engine and does not yet send chat messages to the providers.

PC STATS AND SECURITY
PC Stats uses psutil when installed. Defender status uses a read-only PowerShell
Get-MpComputerStatus query on Windows. If access fails, check the Windows Security
app directly. No statistics are uploaded.

UPDATES
The Updates page checks the latest GitHub release for a repository you enter as
owner/repository. No repository is hardcoded. It does not download or install code.

BUILD A PORTABLE WINDOWS EXE
On Windows, install dependencies then run build_windows.bat.
The script uses `python`, not `py`. It builds a one-folder distribution in dist\WindowsBuddy
which is generally more reliable than a one-file executable. Copy the whole folder to
another PC. PyInstaller output is not built by this source ZIP itself.

BUILD AN INSTALLER
Install Inno Setup 6 from https://jrsoftware.org/isinfo.php, build the portable folder
first, then open WindowsBuddy.iss in Inno Setup Compiler and click Compile.

DATA
Settings and reminders are stored in %APPDATA%\WindowsBuddy. Corrupt JSON files
are handled by falling back to defaults; they may need manual repair if data recovery
is desired.

LIMITATIONS IN THIS FIRST BUILD
- GUI runtime has not been tested on Windows in this environment.
- Full online AI chat integration, startup integration, and persistent timers after
  app exit are not implemented.
- Visual theme/accent changes are saved, but full theme repaint is best after restart.
- The tray depends on optional pystray/Pillow support and platform integration.
