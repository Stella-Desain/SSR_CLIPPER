"""Install a pinned official KDE MLT runtime, without running/installing Kdenlive.

Only render dependencies are copied. No editor executable or authoring project
is installed. On Windows use an existing 7-Zip CLI (no GUI is opened).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

VERSION = "26.08.1"
URL = f"https://download.kde.org/stable/kdenlive/26.08/windows/kdenlive-{VERSION}_standalone.exe"
SHA256 = "9335b59356a7fd6fb4b836c09a518db6547ad4189717cae872474e798b72a67b"
RENDER_MODULES = {"libmltcore.dll", "libmltavformat.dll", "libmltresample.dll", "libmltxml.dll",
                  "libmltqt6.dll", "libmltfrei0r.dll", "libmltplus.dll", "libmltplusgpl.dll", "libmltoldfilm.dll"}


def install(destination, *, archive=None, seven_zip=None):
    if os.name != "nt":
        raise RuntimeError("For Linux/macOS install MLT/melt through the platform package manager, then set SSR_MLT_PATH.")
    destination = Path(destination).resolve()
    if destination.exists():
        raise RuntimeError("Runtime destination already exists. Keep the existing version or choose a new destination.")
    candidates = [seven_zip, shutil.which("7z"), r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"]
    extractor = next((str(p) for p in candidates if p and Path(p).is_file()), None)
    if not extractor:
        raise RuntimeError("Install the 7-Zip CLI or pass --seven-zip. The installer never opens its GUI.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mlt-setup-", dir=destination.parent) as temp:
        temp = Path(temp)
        package = Path(archive).resolve() if archive else temp / "official.exe"
        if not archive:
            with urlopen(URL, timeout=60) as response, package.open("wb") as stream:
                shutil.copyfileobj(response, stream)
        digest = hashlib.sha256()
        with package.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != SHA256:
            raise RuntimeError("Official KDE archive checksum mismatch.")
        extracted = temp / "extracted"
        subprocess.run([extractor, "x", str(package), "-o" + str(extracted), "-y"], check=True,
                       stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        original = extracted / f"kdenlive-{VERSION}_standalone"
        runtime = temp / "runtime"
        runtime.mkdir()
        for folder in ("bin", "lib", "plugins", "share", "etc"):
            if (original / folder).is_dir():
                shutil.copytree(original / folder, runtime / folder, ignore=lambda _path, names:
                    [name for name in names if name.lower().endswith(".exe") and name.lower() not in {"melt.exe", "ffmpeg.exe", "ffprobe.exe"}])
        # Don't initialize hardware I/O, global OFX plug-ins, or unrelated editors'
        # integrations. Rendering uses only the modules in the supported contract.
        repository = runtime / "lib" / "render-mlt"
        repository.mkdir()
        for module in RENDER_MODULES:
            shutil.copy2(runtime / "lib" / "mlt" / module, repository / module)
        # Retain license/source information from the official binary distribution.
        for name in ("COPYING", "COPYING.txt", "LICENSE", "LICENSE.txt", "licenses"):
            path = original / name
            if path.is_file():
                shutil.copy2(path, runtime / name)
            elif path.is_dir():
                shutil.copytree(path, runtime / name)
        (runtime / "runtime-source.json").write_text(json.dumps({"distribution": "KDE Kdenlive standalone",
            "version": VERSION, "url": URL, "archive_sha256": SHA256, "editor_executables_included": False,
            "source": "https://invent.kde.org/multimedia/kdenlive", "mlt_source": "https://github.com/mltframework/mlt"}, indent=2), encoding="utf-8")
        if not (runtime / "bin" / "melt.exe").is_file():
            raise RuntimeError("Official archive did not include melt.exe.")
        runtime.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default=str(Path(__file__).resolve().parents[1] / "_runtime" / "mlt"))
    parser.add_argument("--archive", help="Already downloaded official archive (still checksum validated)")
    parser.add_argument("--seven-zip")
    args = parser.parse_args()
    try:
        result = install(args.destination, archive=args.archive, seven_zip=args.seven_zip)
    except Exception as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"MLT runtime installed: {result}. No editor was installed or started.")


if __name__ == "__main__":
    main()
