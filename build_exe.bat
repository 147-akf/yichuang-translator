@echo off
cd /d "%~dp0"

echo Building a single-file executable with PyInstaller...
echo.

python -m pip install -r requirements.txt
if errorlevel 1 goto :error

python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "YiChuangTranslator" ^
    --icon "icon.ico" ^
    --add-data "icon.ico;." ^
    --collect-all cv2 ^
    translator.pyw
if errorlevel 1 goto :error

echo.
echo Build complete: %~dp0dist\YiChuangTranslator.exe
echo.
pause
exit /b 0

:error
echo.
echo Build failed. Make sure Python and PyInstaller are installed.
pause
exit /b 1
