# Dashboard — GUI Ada, Program Tidak Ada/Tidak Terhubung
File: `web/components/dashboard.js`

## 1. Button "Repliz Dashboard"
- Lokasi: `#btn-repliz-dashboard`, dashboard.js:22
- Status: program tidak ada
- Masalah: tidak ada onclick handler; tidak ada endpoint Repliz di app.py
- Aksi: buat `get_repliz_dashboard_url()` / `open_repliz_dashboard()` di WebAPI (app.py), wire click di app.js

## 2. Account stats banner (12 Campaign / +TikTok / +YouTube)
- Lokasi: dashboard.js:55-85
- Status: program tidak ada — data hardcoded di HTML
- Aksi: buat endpoint `get_account_stats()` -> {campaigns, tiktok_count, youtube_count}; render dinamis di `refresh()`

## 3. Campaign tree section (nama campaign, child account, angka 3/150/50, tombol "Restock Clip")
- Lokasi: dashboard.js:160-260
- Status: program tidak ada — semua hardcoded, expand/collapse tidak toggle state, tombol tanpa handler
- Aksi: buat endpoint `get_campaigns()` -> list{name, children[], counts}; implement toggle state on click; wire "Restock Clip"

## 4. `onEdit: () => {}` pada item Jobs Proses
- Lokasi: dashboard.js ~line 398-410
- Status: program tidak ada — callback kosong
- Aksi: definisikan aksi nyata (buka detail job / retry), tambah endpoint jika perlu
