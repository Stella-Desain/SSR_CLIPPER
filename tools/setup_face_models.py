"""Install hash-pinned official OpenCV models; no GUI or provider/API keys."""
from pathlib import Path
import sys
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.editing import file_sha256
from services.target_faces import MODEL_COMMIT, MODELS, model_root


def main():
    root = model_root()
    root.mkdir(parents=True, exist_ok=True)
    for name, (folder, digest, size) in MODELS.items():
        target = root / name
        if target.is_file() and file_sha256(target) == digest:
            print(f"Verified {name}")
            continue
        temp = root / ("." + uuid.uuid4().hex + ".download")
        url = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{MODEL_COMMIT}/models/{folder}/{name}"
        try:
            print(f"Downloading {name} ({size:,} bytes)", flush=True)
            with urllib.request.urlopen(url, timeout=90) as source, temp.open("wb") as output:
                downloaded = 0
                while chunk := source.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > size:
                        raise ValueError("Model download exceeds expected size")
                    output.write(chunk)
            if downloaded != size or file_sha256(temp) != digest:
                raise ValueError("Model fingerprint mismatch")
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
        # Keep upstream license beside the model for redistribution.
        license_path = root / f"{folder}.LICENSE"
        license_path.write_bytes(urllib.request.urlopen(
            f"https://raw.githubusercontent.com/opencv/opencv_zoo/{MODEL_COMMIT}/models/{folder}/LICENSE", timeout=30).read())
    print(f"Face models ready: {root}")


if __name__ == "__main__":
    main()
