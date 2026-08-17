@echo off
echo ==============================================
echo SSR_CLIPPER - EXE Builder
echo ==============================================
echo.

echo [1/3] Memastikan pyinstaller terinstall...
pip install pyinstaller

echo.
echo [2/3] Build EXE dengan PyInstaller (ini bisa makan waktu agak lama)...
python -m PyInstaller --clean --noconfirm build.spec

echo.
echo [3/3] Selesai!
echo File EXE berhasil dibuat di dalam folder 'dist\SSR_CLIPPER'.
echo Kamu bisa memindahkan folder tersebut ke tempat lain.
echo.
pause
