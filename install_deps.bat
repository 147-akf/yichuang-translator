@echo off
cd /d "%~dp0"

echo Installing optional wallpaper dependencies...
echo (Pillow for images, OpenCV for videos)
echo.

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Installation failed. Check your network and Python installation.
    pause
    exit /b 1
)

echo.
echo Done. You can now choose image and video wallpapers.
pause
