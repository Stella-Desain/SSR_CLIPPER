@echo off
setlocal
cd /d "%~dp0"
py -3.12 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.prefix == sys.base_prefix else 1)" >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 belum terpasang. Pasang Python 3.12 beserta Python Launcher.
    pause
    exit /b 1
)

py -3.12 "%~dp0app.py"
if errorlevel 1 (
    echo Aplikasi gagal berjalan. Periksa error.log.
    pause
    exit /b 1
)
