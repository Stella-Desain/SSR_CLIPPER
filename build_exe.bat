@echo off
setlocal EnableExtensions

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Tidak dapat membuka direktori proyek.
    exit /b 1
)

py -3.12 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.prefix == sys.base_prefix else 1)"
if errorlevel 1 (
    echo [ERROR] Pasang Python 3.12 beserta Python Launcher untuk membangun aplikasi.
    exit /b 1
)

py -3.12 -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller belum tersedia di Python 3.12.
    echo Jalankan: py -3.12 -m pip install -r requirements.txt pyinstaller
    exit /b 1
)

echo [1/2] Membangun SSR_CLIPPER.exe dengan Python 3.12...
py -3.12 -m PyInstaller --clean --noconfirm build.spec
if errorlevel 1 (
    echo [ERROR] Build gagal. Lihat pesan PyInstaller di atas.
    exit /b 1
)

if not exist "dist\SSR_CLIPPER.exe" (
    echo [ERROR] Build selesai tanpa menghasilkan dist\SSR_CLIPPER.exe.
    exit /b 1
)

copy /Y "dist\SSR_CLIPPER.exe" "SSR_CLIPPER.exe" >nul
if errorlevel 1 (
    echo [ERROR] EXE berhasil dibangun, tetapi tidak dapat disalin ke folder proyek.
    echo Tutup SSR_CLIPPER.exe yang sedang berjalan, lalu salin dist\SSR_CLIPPER.exe ke sini.
    exit /b 1
)

echo [2/2] Selesai: "%CD%\SSR_CLIPPER.exe"
echo Jalankan SSR_CLIPPER.exe. Data campaign tetap di folder proyek ini.
exit /b 0
