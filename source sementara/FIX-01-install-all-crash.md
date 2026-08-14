# FIX 01 — "Install All" Crash + yt-dlp Status Tidak Pernah Dicek

## Context
Repo: `https://github.com/Stella-Desain/clip-v2/tree/feature/pywebview-desktop-integration`
Stack: Python (pywebview backend di `app.py`) + vanilla JS frontend (`web/app.js`, `web/components/ai-settings.js`).

Scope kamu **HANYA** 2 file ini:
- `utils/dependency_manager.py`
- `app.py`
- `web/app.js`

Jangan sentuh file lain. Jangan refactor hal yang gak diminta di sini.

---

## BUG 1 (CRITICAL): Tombol "Install All" selalu error

**Lokasi:** `app.py`, method `install_dependencies` (~line 1054):
```python
def install_dependencies(self):
    try:
        from utils.dependency_manager import DependencyManager
        dm = DependencyManager()
        t = threading.Thread(target=dm.install_all, daemon=True)
        t.start()
        return {"status": "started"}
    except Exception as e:
        print(f"Error starting install: {e}")
        return {"status": "error", "message": str(e)}
```

**Root cause:** Buka `utils/dependency_manager.py`. Class `DependencyManager` **tidak ada di file itu sama sekali**. Yang ada cuma function lepas: `setup_ffmpeg(app_dir, progress_callback)`, `setup_deno(app_dir, progress_callback)`, `check_dependency(name, app_dir)`. Jadi `from utils.dependency_manager import DependencyManager` selalu `ImportError`, tertangkap try/except, dan user cuma lihat tombol berubah jadi "Error" tanpa tahu kenapa.

**Fix yang harus dikerjakan:**

1. Di `utils/dependency_manager.py`, tambahkan class `DependencyManager` di paling bawah file (jangan hapus/ubah function yang sudah ada, tinggal wrap):

```python
import subprocess
import sys


class DependencyManager:
    """Wrapper agar app.py bisa memanggil satu method install_all()."""

    def __init__(self, app_dir=None):
        if app_dir is None:
            if getattr(sys, 'frozen', False):
                app_dir = Path(sys.executable).parent
            else:
                app_dir = Path(__file__).parent.parent
        self.app_dir = Path(app_dir)

    def install_all(self, progress_callback=None):
        """Install ffmpeg, deno, yt-dlp, dan whisper. Dipanggil dari background thread."""
        results = {}

        debug_log("Starting install_all...")

        if not check_dependency('ffmpeg', self.app_dir):
            results['ffmpeg'] = setup_ffmpeg(self.app_dir, progress_callback)
        else:
            results['ffmpeg'] = True

        if not check_dependency('deno', self.app_dir):
            results['deno'] = setup_deno(self.app_dir, progress_callback)
        else:
            results['deno'] = True

        results['ytdlp'] = self._install_ytdlp()
        results['whisper'] = self._install_whisper()

        debug_log(f"install_all finished: {results}")
        return results

    def _install_ytdlp(self):
        try:
            import yt_dlp  # noqa
            return True
        except ImportError:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    check=True, timeout=120
                )
                return True
            except Exception as e:
                debug_log(f"yt-dlp install error: {e}")
                return False

    def _install_whisper(self):
        try:
            import faster_whisper  # noqa
            return True
        except ImportError:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "faster-whisper"],
                    check=True, timeout=300
                )
                return True
            except Exception as e:
                debug_log(f"whisper install error: {e}")
                return False
```

2. Cek bagian import di paling atas `utils/dependency_manager.py` — pastikan `from pathlib import Path` sudah ada (biasanya sudah, tinggal cek jangan sampai duplikat import).

3. **Jangan ubah** signature `setup_ffmpeg`, `setup_deno`, `check_dependency` yang sudah ada. Class baru ini cuma manggil mereka.

---

## BUG 2: yt-dlp gak pernah dicek statusnya + dot status ketuker

**Lokasi A — `app.py`, method `check_dependencies` (~line 905):**
```python
def check_dependencies(self):
    ...
    ffmpeg_ok = Path(get_ffmpeg_path()).exists() if get_ffmpeg_path() else False
    import shutil
    deno_ok = shutil.which("deno") is not None
    ...
    return {
        "cookies": has_cookies,
        "ffmpeg": ffmpeg_ok,
        "deno": deno_ok,
        "whisper": whisper_ok
    }
```
Gak ada key `ytdlp` di return dict ini sama sekali.

**Fix:** tambahkan pengecekan yt-dlp pakai helper yang SUDAH ADA di `utils/helpers.py` (`get_ytdlp_path`, `is_ytdlp_module_available` — cek dulu nama function persisnya di file itu, pakai yang sudah ada, jangan bikin baru). Tambahkan di `check_dependencies`:

```python
from utils.helpers import get_app_dir, get_bundle_dir, get_ffmpeg_path, get_ytdlp_path
# ^ get_ytdlp_path sudah diimport di top file app.py, tinggal dipakai

def check_dependencies(self):
    ...
    ytdlp_path = get_ytdlp_path()
    ytdlp_ok = ytdlp_path is not None and ytdlp_path != ""
    if ytdlp_path not in ("yt_dlp_module",):
        # kalau bukan python module, pastikan path/command-nya beneran ada
        import shutil as _shutil
        ytdlp_ok = _shutil.which(ytdlp_path) is not None or Path(ytdlp_path).exists()
    ...
    return {
        "cookies": has_cookies,
        "ffmpeg": ffmpeg_ok,
        "deno": deno_ok,
        "whisper": whisper_ok,
        "ytdlp": ytdlp_ok
    }
```

**Lokasi B — `web/app.js`, function `loadDepStatus` (~line 896):**
```js
const deps = await window.pywebview.api.check_dependencies();
const dots = aiView.element.querySelectorAll('.dep-dot');
// Map: yt-dlp, ffmpeg, deno, whisper
const depMap = [deps.ffmpeg, deps.ffmpeg, deps.deno, deps.whisper];
```
Dot pertama (yt-dlp) dan kedua (ffmpeg) sama-sama pakai `deps.ffmpeg`. Ganti jadi:
```js
const depMap = [deps.ytdlp, deps.ffmpeg, deps.deno, deps.whisper];
```

---

## BUG 3 (minor tapi ganggu UX): tombol Install gak refresh status beneran

**Lokasi — `web/app.js` (~line 372-384):**
```js
installBtn.addEventListener('click', async () => {
    installBtn.disabled = true;
    installBtn.textContent = 'Installing...';
    try {
      await window.pywebview.api.install_dependencies();
      installBtn.textContent = 'Installing (bg)';
      setTimeout(() => { installBtn.disabled = false; installBtn.textContent = 'Install All'; }, 5000);
    } catch(e) {
      installBtn.textContent = 'Error';
      installBtn.disabled = false;
    }
});
```
Ini asumsi install selesai dalam 5 detik apapun kondisinya (padahal download ffmpeg/deno bisa lebih lama), dan gak pernah manggil ulang `loadDepStatus()` buat update dot ijo/merah setelah install kelar.

**Fix:** ganti `setTimeout` 5 detik jadi polling `check_dependencies` tiap 3 detik sampai 4 dependency ok atau max 2 menit, lalu panggil `loadDepStatus()`:

```js
installBtn.addEventListener('click', async () => {
    installBtn.disabled = true;
    installBtn.textContent = 'Installing...';
    try {
      await window.pywebview.api.install_dependencies();
      installBtn.textContent = 'Installing (bg)...';

      const maxAttempts = 40; // 40 x 3s = 2 menit
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        await loadDepStatus();
        const deps = await window.pywebview.api.check_dependencies();
        const allOk = deps.ffmpeg && deps.deno && deps.whisper && deps.ytdlp;
        if (allOk || attempts >= maxAttempts) {
          clearInterval(poll);
          installBtn.disabled = false;
          installBtn.textContent = 'Install All';
        }
      }, 3000);
    } catch(e) {
      installBtn.textContent = 'Error';
      installBtn.disabled = false;
    }
});
```

---

## Acceptance Criteria (WAJIB dicek sebelum lapor selesai)
1. Klik "Install All" tidak lagi menyebabkan `ImportError` di console/log.
2. `check_dependencies()` return dict punya key `ytdlp`.
3. Dot status "yt-dlp" di header Settings sekarang independen dari dot "ffmpeg" — kalau cuma ffmpeg yang terinstall, dot yt-dlp tetap merah (kecuali yt-dlp memang juga terinstall).
4. Setelah proses install selesai, dot-dot status otomatis update jadi hijau tanpa perlu reload halaman manual.
5. Tulis di laporan akhir kamu: apa saja yang diubah, dan hasil test manual (screenshot/log console) dari langkah 1-4.

## JANGAN
- Jangan ubah struktur `check_dependency()`, `setup_ffmpeg()`, `setup_deno()` yang lama.
- Jangan ubah UI/CSS di `ai-settings.js`.
- Jangan tambah dependency baru di `requirements.txt` kecuali `faster-whisper`/`yt-dlp` yang sudah dipakai project ini.
