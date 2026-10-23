"""Create a desktop shortcut for 译窗 Translator (Windows only).

Run this file with Python:  python create_shortcut.py
It uses the Python installation that runs this script, so the shortcut keeps
working without a hard-coded interpreter path.
"""

from __future__ import annotations

import base64
import ctypes
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "translator.pyw"
ICON = HERE / "icon.ico"
SHORTCUT_NAME = "译窗 Translator.lnk"


def desktop_directory() -> Path:
    """Return the real desktop path (handles OneDrive-redirected desktops)."""
    buffer = ctypes.create_unicode_buffer(260)
    # CSIDL_DESKTOPDIRECTORY = 0x0010
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buffer)
    if result == 0 and buffer.value:
        return Path(buffer.value)
    return Path.home() / "Desktop"


def main() -> int:
    if sys.platform != "win32":
        print("This script only works on Windows.")
        return 1
    if not SCRIPT.exists():
        print(f"translator.pyw not found next to this script: {SCRIPT}")
        return 1

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)

    desktop = desktop_directory()
    desktop.mkdir(parents=True, exist_ok=True)
    shortcut = desktop / SHORTCUT_NAME

    icon_line = f'$s.IconLocation = "{ICON}"' if ICON.exists() else ""
    commands = f"""
$ProgressPreference = 'SilentlyContinue'
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("{shortcut}")
$s.TargetPath = "{pythonw}"
$s.Arguments = '"{SCRIPT}"'
$s.WorkingDirectory = "{HERE}"
{icon_line}
$s.Description = "Always-on-top Chinese / English translator"
$s.Save()
"""
    encoded = base64.b64encode(commands.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        check=False,
    )
    if result.returncode != 0:
        print("Failed to create the shortcut.")
        return result.returncode

    print(f"Shortcut created: {shortcut}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
