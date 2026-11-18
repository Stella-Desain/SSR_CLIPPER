# Template Jedag Jedug

Template native berbasis JSON dengan contoh campaign Ironman. Definisi ada di
`output/ironman-tests-20261013/templates/achievement_jedag_jedug.json`;
recipe contoh ada di `output/ironman-tests-20261013/jedag-jedug/recipe.json`.
Ini dapat diedit melalui file recipe; belum tersedia sebagai preset dropdown
atau paket editor visual `.ssrtemplate`.

Contoh memakai bagian lagu **Drink's Afterhouse — Felixjd**, mulai detik 64.
Pengukuran lokal memperkirakan 120 BPM. Grid di-snap ke frame 30 fps; cut utama
mengikuti kelipatan beat. Lagu dan footage merupakan aset terpisah dari template.

| Bagian | Perilaku |
| --- | --- |
| 0–5,067 detik | Hook IRONMAN yang dapat diedit; gambar tanpa shake atau pulse |
| 5,067–20,067 detik | Cut mengikuti beat; punch-in hingga 7,5%, shake ringan, roll hingga 0,4°, pulse cahaya kecil |
| 20,067–23,067 detik | Film burn singkat menuju pose senyum setelah finish, lalu penutup stabil |

Font, teks, warna, posisi kartu, sumber, trim, anchor, musik, grid beat,
intensitas zoom/shake, film burn, dan CTA tersedia di recipe. Efek bekerja sebagai
transformasi kamera seragam; tidak mengubah bentuk wajah. Tidak ada rentang bahan
yang diulang di dalam contoh. Penutup memakai frame resmi Bevan di detik 746,2
yang sudah diperiksa, dengan framing lebih longgar daripada penutup lama.
CTA opsional; jika campaign mewajibkan CTA, isi `cta.required` dan adegan
ber-role `cta`. Materi tetap harus memenuhi aturan campaign tujuan.

## Render contoh

```powershell
py -3.12 tools/build_jedag_jedug.py build
py -3.12 tools/build_jedag_jedug.py render
```

Hasil ada di `output/ironman-tests-20261013/jedag-jedug/master.mp4`.
Perintah `build` menyusun ulang contoh dari aset resmi lokal. Untuk variasi yang
sudah diedit, gunakan `render` saja agar perubahan recipe tidak tertimpa.

## Pakai untuk campaign lain

Salin recipe ke folder baru, lalu ganti hook, `constraints`, `cta`, bahan adegan,
musik, dan kreditnya. Pertahankan durasi adegan sebagai kelipatan 1/30 detik.
Periksa ekspresi wajah, crop, dan relevansi setiap bahan, terutama pose penutup.

Jika lagu atau titik mulai lagu berubah, ukur ulang grid:

```powershell
py -3.12 tools/measure_montage_beats.py "E:/path/lagu.mp3" --start 0 --seconds 24 --output "E:/path/beat-analysis.json"
```

Hasil pengukuran adalah estimasi yang perlu diperiksa. Sesuaikan
`beat_effects.beats_seconds`, waktu cut, `start_seconds`, dan `end_seconds`
dengan bagian lagu baru; jangan memakai grid lagu contoh untuk lagu lain.
Sisakan setidaknya tiga detik penutup stabil dan waktu membaca hook sesuai brief.
Render salinan tersebut secara langsung:

```powershell
py -3.12 -c "from services.achievement_montage import render_recipe; render_recipe('E:/path/recipe.json', 'E:/path/master.mp4')"
```

Renderer tidak menerbitkan video. Stok dan publikasi mengikuti proses review
aplikasi; contoh baru disimpan sebagai draft tanpa upload otomatis.
