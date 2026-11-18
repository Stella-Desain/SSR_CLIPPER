# Menjalankan SSR_CLIPPER di Windows tanpa venv

Proyek memakai Python 3.12 yang terpasang di Windows untuk menjalankan source dan membangun EXE. Venv tidak diperlukan. `SSR_CLIPPER.exe` adalah aplikasi mandiri dan dapat dijalankan tanpa memasang Python.

## Jalankan dari source

Klik dua kali **`app.py`** di Explorer. Baris pertama file memilih Python 3.12 melalui Python Launcher Windows. Jika file dijalankan memakai interpreter lain atau venv, entry point membuka ulang aplikasi dengan Python 3.12 yang terpasang di Windows, sebelum memuat library aplikasi.

Alternatifnya, klik dua kali `run_app.bat` atau jalankan `py -3.12 app.py` dari PowerShell. Semua cara ini membuka data proyek yang sama.

Siapkan atau lengkapi dependency source dengan:

```powershell
py -3.12 -m pip install -r requirements.txt
.\run_app.bat
```

`mediapipe==0.10.14` di proyek ini menyediakan paket Windows untuk Python 3.12, tetapi bukan Python 3.14. Pemilihan versi oleh shebang dijelaskan di [dokumentasi Python Launcher](https://docs.python.org/3.12/using/windows.html#shebang-lines).

## Build

Jalankan dari PowerShell di direktori proyek:

```powershell
.\build_exe.bat
```

Script memakai `py -3.12` agar tidak tanpa sengaja memilih Python lain dari `PATH`. Jika dependensi build belum ada, pasang satu kali:

```powershell
py -3.12 -m pip install -r requirements.txt pyinstaller
```

Hasilnya adalah **satu file** `dist\SSR_CLIPPER.exe`, yang juga disalin ke direktori proyek sebagai `SSR_CLIPPER.exe`. Build gagal dengan pesan yang jelas jika interpreter atau PyInstaller tidak tersedia.

## Jalankan dan pertahankan data

Aplikasi membaca `config.json`, `output\`, `ffmpeg\`, dan `bin\` dari folder yang berisi EXE. Jalankan `SSR_CLIPPER.exe` di direktori proyek agar campaign dan pekerjaan yang sudah ada tetap terbaca. Jika dijalankan langsung dari `dist\`, aplikasi menggunakan data di `dist\` dan dapat terlihat seperti instalasi baru.

Dependency source dan build terpasang langsung di Python 3.12. Folder venv tidak diperlukan untuk menjalankan aplikasi atau membangun ulang EXE.
