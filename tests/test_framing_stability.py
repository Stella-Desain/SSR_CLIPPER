"""Frame-by-frame regression checks for brief full-frame flashes during cropping."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.face_tracking import FramingDecisionBuffer
from services.framing import frame_video
from services.editing import probe_media


def decision(mode, x=50, cut=False, track_id=1):
    return {"mode": mode, "x": x, "scene_cut": cut,
            "track_id": track_id if mode == "speaker" else None}


class FramingBufferTests(unittest.TestCase):
    def resolve(self, decisions, confirmation=5):
        buffer = FramingDecisionBuffer(confirmation)
        result = []
        for index, item in enumerate(decisions):
            result.extend(buffer.push(index, item))
            self.assertLess(len(buffer.pending), confirmation)
        result.extend(buffer.flush())
        self.assertEqual([index for index, _ in result], list(range(len(decisions))))
        return [item for _, item in result]

    def test_one_and_two_uncertain_frames_do_not_flash_fit(self):
        for gap in (1, 2):
            with self.subTest(gap=gap):
                result = self.resolve([decision("speaker")] * 10 + [decision("fit")] * gap
                                      + [decision("speaker")] * 10)
                self.assertTrue(all(item["mode"] == "speaker" for item in result))
                self.assertEqual(sum(item.get("stabilized", False) for item in result), gap)

    def test_beginning_and_ending_gaps_keep_the_same_crop(self):
        result = self.resolve([decision("fit")] * 2 + [decision("speaker")] * 10 + [decision("fit")] * 2)
        self.assertTrue(all(item["mode"] == "speaker" for item in result))

    def test_persistent_uncertainty_keeps_all_full_frames(self):
        result = self.resolve([decision("speaker")] * 10 + [decision("fit")] * 12
                              + [decision("speaker")] * 10)
        self.assertEqual([item["mode"] for item in result[10:22]], ["fit"] * 12)

    def test_no_faces_never_invents_a_crop(self):
        result = self.resolve([decision("fit")] * 30)
        self.assertTrue(all(item["mode"] == "fit" for item in result))
        self.assertFalse(any(item.get("stabilized") for item in result))

    def test_short_confident_island_does_not_flash_crop_in_a_wide_shot(self):
        result = self.resolve([decision("fit")] * 10 + [decision("speaker")] * 2 + [decision("fit")] * 10)
        self.assertTrue(all(item["mode"] == "fit" for item in result))

    def test_scene_cut_uses_new_shots_future_face_never_the_old_crop(self):
        result = self.resolve([decision("speaker", x=10)] * 10
                              + [decision("fit", cut=True), decision("fit")]
                              + [decision("speaker", x=140, track_id=2)] * 10)
        self.assertTrue(result[10]["scene_cut"])
        self.assertEqual([item["x"] for item in result[10:]], [140] * 12)
        self.assertEqual([item["track_id"] for item in result[10:]], [2] * 12)

    def test_scene_cut_without_recovery_keeps_new_shot_full(self):
        result = self.resolve([decision("speaker", x=10)] * 10 + [decision("fit", cut=True), decision("fit")])
        self.assertEqual([item["mode"] for item in result[-2:]], ["fit", "fit"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class FramingStabilityRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.source = cls.root / "source.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
            "color=c=blue:s=480x270:r=30:d=2.4", "-f", "lavfi", "-i", "sine=frequency=440:duration=2.4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.source)],
            check=True, capture_output=True, timeout=60)
        cls.wide_source = cls.root / "wide-source.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
            "color=c=blue:s=640x270:r=30:d=2.4", "-f", "lavfi", "-i", "sine=frequency=440:duration=2.4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.wide_source)],
            check=True, capture_output=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def render(self, name, width, height, fit_indices, mode="speaker", wide=False):
        root = self.root / name
        root.mkdir(exist_ok=True)
        out = root / "framed.mp4"
        core = SimpleNamespace(ffmpeg_path="ffmpeg", mediapipe_settings={}, face_tracking_mode="opencv",
            campaign_config={"editing": {"framing": mode}}, is_cancelled=lambda:False, log=lambda *_:None)
        x = max(0, round(((640 if wide else 480)-270*width/height)/2))
        def sample(_tracks, seconds, cut=False):
            return decision("fit" if round(seconds*30) in fit_indices else "speaker", x=x, cut=cut)
        with patch("services.framing.CameraPlanner.update", side_effect=sample):
            frame_video(core, self.wide_source if wide else self.source, out, lambda *_:None,
                        output_width=width, output_height=height, output_fps=30)
        return out, json.loads((root / "camera.json").read_text(encoding="utf-8"))

    def decoded_fit_frames(self, path):
        import cv2
        capture = cv2.VideoCapture(str(path))
        count, fit = 0, []
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                # Blue reaches this point only when cropped; fit has dark padding.
                b, g, r = map(int, frame[frame.shape[0]//8, frame.shape[1]//2])
                if b < 100:
                    fit.append(count)
                count += 1
        finally:
            capture.release()
        return count, fit

    def test_every_frame_keeps_crop_through_transient_failures_in_all_builtin_aspect_ratios(self):
        from services.podcast_template import render_layout
        gaps = {0, 1, 24, 25, 70, 71}
        for width, height in ((720,720), (180,180), (180,320), (360,270), (480,270)):
            with self.subTest(canvas=(width,height)):
                out, camera = self.render(f"crop-{width}-{height}", width, height, gaps, wide=width == 480)
                if width == height == 720:
                    bordered = out.with_name("bordered.mp4")
                    render_layout(out, bordered)
                    out = bordered
                count, fit = self.decoded_fit_frames(out)
                self.assertEqual(count, 72)
                self.assertEqual(fit, [])
                self.assertEqual(camera["stabilized_frames"], len(gaps))
                self.assertEqual(camera["fit_frames"], 0)
                info = probe_media(out)
                self.assertEqual((info["width"], info["height"]), (width,height))
                self.assertAlmostEqual(info["duration"], 2.4, delta=.04)
                self.assertTrue(info["has_audio"])
    def test_persistent_fallback_and_explicit_fit_remain_available(self):
        gaps = set(range(20,35))
        out, camera = self.render("persistent", 180,180,gaps)
        count, fit = self.decoded_fit_frames(out)
        self.assertEqual(count,72)
        self.assertEqual(fit,sorted(gaps))
        self.assertEqual(camera["fit_frames"],len(gaps))
        out, camera = self.render("explicit-fit",180,180,set(),mode="fit")
        count, fit = self.decoded_fit_frames(out)
        self.assertEqual(fit,list(range(72)))
        self.assertEqual(camera["stabilized_frames"],0)


class LegacyFramingEntryPointTests(unittest.TestCase):
    def test_both_legacy_detectors_use_shared_renderer_without_changing_worker_settings(self):
        from clipper_core import AutoClipperCore
        core = SimpleNamespace(face_tracking_mode="mediapipe")
        progress = lambda *_: None
        for mode in ("opencv", "mediapipe"):
            with self.subTest(mode=mode), patch("services.framing.frame_video") as renderer:
                method = getattr(AutoClipperCore, f"convert_to_portrait_{mode}_with_progress")
                method(core, "source.mp4", "final.mp4", progress)
                renderer.assert_called_once_with(core, "source.mp4", "final.mp4", progress, tracking_mode=mode)
                self.assertEqual(core.face_tracking_mode, "mediapipe")


if __name__ == "__main__":
    unittest.main()
