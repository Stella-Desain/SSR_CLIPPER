# Catatan Teknis Lintas-Halaman (Bukan Soal GUI)

## 1. `webview_app.py` duplikat basi dari `app.py`
- `webview_app.py` TIDAK punya 4 endpoint yang sudah dipakai `web/`: `get_dashboard_stats`, `get_stock_clips`, `open_output_folder`, `check_dependencies`
- `build_web.spec` masih pakai `webview_app.py` sebagai entry point, sedangkan `build.spec`/`build_macos.spec` pakai `app.py` -> build web bisa menghasilkan app dengan UI rusak
- Aksi: HAPUS `webview_app.py` ATAU sinkronkan isinya dengan `app.py`; ubah `build_web.spec` untuk pakai `app.py`
