"""Multiple image layers survive saving, deletion, snapshots and real rendering."""
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from services.additionals import normalize_additionals, render_watermarks, validate_additionals
from services.campaigns import normalize_campaign
from services.editing import EditingValidationError, file_sha256, probe_media
from test_workflow import Harness
from test_campaign_additionals import addition


class MultiWatermarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        self.red = self.root / "red.png"; self.green = self.root / "green.png"
        Image.new("RGBA", (40, 40), (255, 0, 0, 255)).save(self.red)
        Image.new("RGBA", (40, 40), (0, 255, 0, 255)).save(self.green)
        self.item = {"id": "logos", "type": "watermark", "ratios": ["9:16"], "images": [
            {"id": "red", "image": addition(self.red)["image"], "layout": {"x": 1, "y": 1, "width": .2}},
            {"id": "green", "image": addition(self.green)["image"], "layout": {"x": 0, "y": 0, "width": .3}}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_delete_one_and_delete_last_preserve_old_snapshots(self):
        result = self.api.save_campaign_workspace(None, {"name": "Many logos", "editing": {"additional": [self.item]}})
        self.assertEqual(result["status"], "ok", result)
        campaign = result["campaign"]; original = copy.deepcopy(campaign["editing"]["additional"][0]["images"])
        self.red.unlink(); self.green.unlink()
        for layer in original:
            self.assertTrue(Path(layer["image"]["path"]).is_file())
            self.assertEqual(file_sha256(layer["image"]["path"]), layer["image"]["sha256"])
        item = copy.deepcopy(campaign["editing"]["additional"][0]); item["images"].pop(0)
        saved = self.api.save_campaign_workspace(campaign["id"], {"editing": {"additional": [item]}})
        self.assertEqual(saved["status"], "ok", saved)
        self.assertEqual(saved["campaign"]["editing"]["additional"][0]["images"], [original[1]])
        old = self.api._get_store().get("campaign_version", campaign["version_id"])
        self.assertEqual(old["campaign"]["editing"]["additional"][0]["images"], original)
        item["images"] = []
        # Old single-image fields must not resurrect a deleted layer.
        item.update(image=original[0]["image"], layout=original[0]["layout"])
        empty = self.api.save_campaign_workspace(campaign["id"], {"editing": {"additional": [item]}})
        self.assertEqual(empty["status"], "ok", empty)
        self.assertEqual(empty["campaign"]["editing"]["additional"][0]["images"], [])
        self.assertFalse(empty["readiness"]["production_ready"])
        self.assertIn("minimal satu gambar", " ".join(empty["readiness"]["production_blockers"]))
        self.assertTrue(all(Path(layer["image"]["path"]).is_file() for layer in original))

    def test_legacy_layer_identity_and_validation_for_every_image(self):
        legacy = addition(self.red)
        new = normalize_additionals([legacy])[0]
        self.assertEqual(new["images"][0]["id"], legacy["id"])
        self.assertEqual(new["images"][0]["layout"], legacy["layout"])
        self.assertNotIn("image", new)
        for layers in (None, [None], [self.item["images"][0]] * 2, self.item["images"] * 13,
                       [{"id": "bad", "image": {"sha256": "invalid"}}],
                       [{"id": "bad", "image": {}, "layout": {"width": 0}}]):
            with self.subTest(layers=layers), self.assertRaises(EditingValidationError):
                normalize_additionals([{**self.item, "images": layers}])
        campaign = normalize_campaign({"editing": {"additional": [self.item]}})
        Image.new("RGBA", (40, 40), (255, 255, 0, 255)).save(self.green)
        blockers, _ = validate_additionals(campaign)
        self.assertIn("berubah", " ".join(blockers), "The second layer is also hash-verified")

    def test_batch_import_reports_invalid_files_and_dialog_enables_multiple(self):
        invalid = self.root / "broken.png"; invalid.write_bytes(b"invalid")
        result = self.api.import_additional_images([str(self.red), str(invalid), str(self.green)])
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(len(result["images"]), 2)
        self.assertEqual(result["errors"][0]["name"], "broken.png")
        self.assertEqual(self.api.import_additional_images([str(invalid)])["status"], "error")
        window = Mock(); window.create_file_dialog.return_value = [str(self.red), str(self.green)]
        # Test the bridge with a fake dialog; never open a desktop window.
        with patch("webview.windows", [window]):
            chosen = self.api.browse_additional_images()
            self.assertEqual(len(chosen["images"]), 2)
            self.assertTrue(window.create_file_dialog.call_args.kwargs["allow_multiple"])
            window.create_file_dialog.return_value = None
            self.assertEqual(self.api.browse_additional_images()["status"], "cancelled")

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_real_render_contains_both_independent_layers_and_removes_only_deleted_layer(self):
        import cv2
        source = self.root / "source.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=180x320:d=1.2:r=15",
                        "-f", "lavfi", "-i", "sine=frequency=400:duration=1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(source)], check=True, capture_output=True, timeout=30)
        items = normalize_additionals([self.item])
        for attempt in (0, 1):
            if attempt:
                items[0]["images"].pop(0)
            output = self.root / f"output-{attempt}.mp4"
            evidence = render_watermarks(source, output, items)
            self.assertEqual([m["image_id"] for m in evidence], ["red", "green"] if not attempt else ["green"])
            info = probe_media(output)
            self.assertTrue(info["has_audio"]); self.assertAlmostEqual(info["duration"], 1.2, delta=.1)
            cap = cv2.VideoCapture(str(output)); ok, frame = cap.read(); cap.release()
            self.assertTrue(ok)
            self.assertGreater(int(frame[10, 10, 1]), 180)
            self.assertEqual(int(frame[-10, -10, 2]) > 180, not attempt)
            self.assertGreater(int(frame[-10, -10, 0]), 180 if attempt else -1)


if __name__ == "__main__": unittest.main()
