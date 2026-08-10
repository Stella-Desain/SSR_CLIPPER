# Global/Shell — GUI Ada, Program Tidak Ada/Tidak Terhubung
File: `web/components/header.js`, `web/app.js`

## 1. Nav item "Credit"
- Lokasi: header.js:34
- Status: program tidak ada — di app.js: `if (view === 'credit') return; // Not implemented yet`
- Aksi: buat CreditView baru + endpoint `get_credit_balance()` dll, ATAU hapus nav item jika fitur tidak jadi dipakai
