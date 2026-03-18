import subprocess
import sys
import os
import difflib
import shutil
import glob
import webbrowser
from typing import Tuple

# ─────────────────────────────────────────────
# 🧠 APP ALIAS MAP
# ─────────────────────────────────────────────
APP_ALIASES: dict[str, str] = {
    # Browsers
    "chrome":             "google-chrome",
    "google chrome":      "google-chrome",
    "firefox":            "firefox",
    "brave":              "brave-browser",
    "edge":               "msedge.exe", 

    # Code editors
    "vscode":             "code",
    "vs code":            "code",
    "visual studio code": "code",
    "vs":                 "code",
    "sublime":            "subl",
    "sublime text":       "subl",

    # Terminals
    "terminal":           "wt.exe" if sys.platform == "win32" else "gnome-terminal",
    "konsole":            "konsole",
    "cmd":                "cmd.exe",
    "powershell":         "powershell.exe",

    # Media
    "vlc":                "vlc",
    "spotify":            "spotify",

    # Communication
    "discord":            "discord",
    "slack":              "slack",
    "telegram":           "telegram-desktop",
    "whatsapp":           "whatsapp",

    # Files / Utils
    "files":              "explorer.exe" if sys.platform == "win32" else "nautilus",
    "file manager":       "explorer.exe" if sys.platform == "win32" else "nautilus",
    "calculator":         "calc.exe",
    "notepad":            "notepad.exe",
    "text editor":        "notepad.exe",

    # Windows specific
    "explorer":           "explorer.exe",
    "paint":              "mspaint.exe",
    "task manager":       "taskmgr.exe",
    "settings":           "ms-settings:",
}

# Apps that open in browser
BROWSER_APPS: set[str] = {
    "youtube", "yt", "gmail", "google",
    "maps", "google maps", "drive", "google drive"
}
BROWSER_URLS: dict[str, str] = {
    "youtube":      "https://youtube.com",
    "yt":           "https://youtube.com",
    "gmail":        "https://mail.google.com",
    "google":       "https://google.com",
    "maps":         "https://maps.google.com",
    "google maps":  "https://maps.google.com",
    "drive":        "https://drive.google.com",
    "google drive": "https://drive.google.com",
}

# Filler words LLM tends to include in app_name argument
_FILLER_WORDS = [
    "please", "for me", "right now", "quickly",
    "open", "launch", "start", "run", "execute",
    "the", "my", "an", "a", "app", "application",
    "program", "software", "tool",
]


def _clean_app_input(text: str) -> str:
    text = text.lower().strip()
    for word in sorted(_FILLER_WORDS, key=len, reverse=True):
        text = text.replace(word, " ")
    return " ".join(text.split())


def _scan_system_apps() -> dict[str, str]:
    dynamic: dict[str, str] = {}
    platform = sys.platform

    try:
        if platform == "linux":
            for path in glob.glob("/usr/share/applications/*.desktop"):
                name, exec_cmd = None, None
                with open(path, "r", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Name=") and name is None:
                            name = line.split("=", 1)[1].strip().lower()
                        if line.startswith("Exec=") and exec_cmd is None:
                            # 4️⃣ Linux Desktop Exec Cleanup (Stripping quotes)
                            exec_cmd = line.split("=", 1)[1].strip().split()[0].strip('"')
                if name and exec_cmd:
                    dynamic[name] = exec_cmd

        elif platform == "darwin":
            for app_path in glob.glob("/Applications/*.app"):
                app_name = os.path.basename(app_path).replace(".app", "").lower()
                dynamic[app_name] = app_path

        elif platform == "win32":
            start_menu_paths = [
                os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
                os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs")
            ]
            for start_menu in start_menu_paths:
                for lnk in glob.glob(os.path.join(start_menu, "**", "*.lnk"), recursive=True):
                    name = os.path.basename(lnk).replace(".lnk", "").lower()
                    dynamic[name] = lnk

    except Exception as e:
        print(f"[WARN] [NEON] System app scan failed: {e}")

    return dynamic


# 2️⃣ Global Maps Built Once
_DYNAMIC_APPS: dict[str, str] = _scan_system_apps()
_COMBINED_APPS: dict[str, str] = {**_DYNAMIC_APPS, **APP_ALIASES}


def _resolve_app_name(raw_name: str) -> Tuple[str, str]:
    raw_lower = raw_name.lower().strip()

    if raw_lower in _COMBINED_APPS:
        return _COMBINED_APPS[raw_lower], raw_name

    close = difflib.get_close_matches(raw_lower, _COMBINED_APPS.keys(), n=1, cutoff=0.75)
    if close:
        matched = close[0]
        print(f"[NEON] Fuzzy matched '{raw_name}' -> '{matched}'")
        return _COMBINED_APPS[matched], matched

    return raw_lower, raw_name


def _open_in_browser(url: str, display_name: str) -> str:
    webbrowser.open(url)
    return f"Opened {display_name} in your browser."


def _suggest(raw_lower: str) -> str:
    suggestions = difflib.get_close_matches(raw_lower, _COMBINED_APPS.keys(), n=3, cutoff=0.5)
    if suggestions:
        return f"Did you mean: {', '.join(s.title() for s in suggestions)}?"
    return ""


# ─────────────────────────────────────────────
# 🚀 MAIN ENTRY POINT
# ─────────────────────────────────────────────
def open_app(app_name: str) -> str:
    if not app_name or not app_name.strip():
        return "Error: No app name provided."

    raw = _clean_app_input(app_name)
    if not raw:
        return "Error: Couldn't figure out which app to open."

    raw_lower = raw.lower()

    # 3️⃣ Precise Browser Substring Detection
    for key in BROWSER_APPS:
        if raw_lower == key or raw_lower.startswith(key + " ") or f" {key} " in f" {raw_lower} ":
            url = BROWSER_URLS.get(key, f"https://{key}.com")
            return _open_in_browser(url, key.title())

    command, display = _resolve_app_name(raw)
    platform = sys.platform

    app_exists = False
    if command.endswith(".lnk") or command.startswith("ms-") or os.path.isfile(command) or os.path.isdir(command):
        app_exists = True
    elif shutil.which(command) is not None:
        app_exists = True

    if not app_exists:
        hint = _suggest(raw_lower)
        error_msg = f"'{display}' not found on system."
        if hint:
            error_msg += f" {hint}"
        return error_msg

    try:
        # 5️⃣ Execution Logging Hook
        print(f"[LAUNCH] Executing: {command}")
        
        if platform == "win32":
            if command.endswith(".lnk"):
                os.startfile(command)
            elif command.endswith(".exe") or command.startswith("ms-"):
                # 1️⃣ Safe Windows Execution (No raw shell=True interpolation)
                subprocess.Popen(["cmd", "/c", "start", "", command])
            else:
                subprocess.Popen(["cmd", "/c", command])

        elif platform == "darwin":
            if os.path.isdir(command): 
                subprocess.Popen(["open", command])
            else:
                subprocess.Popen(["open", "-a", command])

        else:
            # Linux 
            subprocess.Popen(
                [command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        return f"Opened {display.title()}."

    except PermissionError:
        return f"Permission denied when trying to open '{display}'."
    except Exception as e:
        return f"Failed to open '{display}': {str(e)}"