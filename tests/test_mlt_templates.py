"""Portable package, immutable campaign selection and real headless MLT tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from template_sdk.ssr_template_engine import TemplateError, export_template, inspect_package, install_package, instantiate, load_template
from services.campaigns import normalize_campaign, campaign_processing_options, resolve_editing_preset
from services.editing import build_clip_plan, probe_media
from services.external_templates import resolve_preset
from services.mlt_runtime import render_template, runtime_executable, runtime_status
from services.template_selection import choose_template

EXAMPLE = Path(__file__).resolve().parents[1] / "template_studio" / "examples" / "portrait.mlt"


class TemplatePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "placeholder.mp4"
        self.source.write_bytes(b"test video stand-in; package tests do not decode it")
        self.timeline = self.root / "render.mlt"
        self.timeline.write_bytes(EXAMPLE.read_bytes())
        self.package = self.root / "example.ssrtemplate"
        self.library = self.root / "library"
        self.manifest = self.export()
        self.directory, _ = install_package(self.package, self.library)

    def tearDown(self):
        self.temp.cleanup()

    def export(self, **changes):
        args = {"source": self.source, "template_id": "demo", "name": "Demo", "version": 1}
        args.update(changes)
        return export_template(self.timeline, self.package, **args)

    def test_package_replaces_source_without_bundling_author_video(self):
        with zipfile.ZipFile(self.package) as z:
            self.assertEqual(set(z.namelist()), {"manifest.json", "timeline.mlt"})
            self.assertNotIn(str(self.source).encode(), z.read("timeline.mlt"))
        self.assertEqual(inspect_package(self.package), self.manifest)

    def test_render_instance_extends_longer_source_and_preserves_escaping(self):
        before = (self.directory / "timeline.mlt").read_bytes()
        data, manifest, count = instantiate(self.directory, self.source, 70.2, 'Cerita & <judul> "bagus"')
        root = ET.fromstring(data)
        self.assertEqual(count, 2106)
        self.assertEqual(root.find("tractor").get("out"), "2105")
        self.assertEqual(root.find("playlist/entry").get("out"), "2105")
        self.assertEqual(root.find("producer").get("out"), "2105")
        self.assertEqual(root.find("producer/filter[2]/property[@name='argument']").text, 'Cerita & <judul> "bagus"')
        self.assertEqual(before, (self.directory / "timeline.mlt").read_bytes())

    def test_source_cuts_are_refused(self):
        root = ET.fromstring(self.timeline.read_bytes())
        root.find("playlist/entry").set("out", "30")
        self.timeline.write_bytes(ET.tostring(root))
        with self.assertRaisesRegex(TemplateError, "full prepared"):
            self.export()

    def test_source_offset_and_intro_are_refused(self):
        root = ET.fromstring(self.timeline.read_bytes())
        ET.SubElement(root.find("playlist"), "entry", {"producer": "source", "in": "10", "out": "89"})
        self.timeline.write_bytes(ET.tostring(root))
        with self.assertRaisesRegex(TemplateError, "continuous"):
            self.export()

    def test_script_dtd_and_unsupported_effect_are_refused(self):
        for text in [b'<!DOCTYPE mlt [<!ENTITY x SYSTEM "file:///secret">]><mlt/>',
                     EXAMPLE.read_bytes().replace(b"brightness", b"arbitrary_plugin"),
                     EXAMPLE.read_bytes().replace(b'name="level"', b'name="script"')]:
            self.timeline.write_bytes(text)
            with self.assertRaises(TemplateError):
                self.export()

    def test_path_traversal_duplicate_and_unlisted_files_are_refused(self):
        for extra in ["../outside.txt", "MANIFEST.JSON", "hidden.py"]:
            evil = self.root / "evil.ssrtemplate"
            with zipfile.ZipFile(self.package) as source, zipfile.ZipFile(evil, "w") as target:
                for item in source.infolist():
                    target.writestr(item.filename, source.read(item.filename))
                target.writestr(extra, "extra")
            with self.assertRaises(TemplateError):
                install_package(evil, self.root / "evil-library")
            self.assertFalse((self.root / "outside.txt").exists())

    def test_tampered_timeline_refused_and_same_version_is_immutable(self):
        self.timeline.write_bytes(self.timeline.read_bytes().replace(b"0.8", b"0.4"))
        self.export()
        with self.assertRaisesRegex(TemplateError, "new version"):
            install_package(self.package, self.library)
        (self.directory / "timeline.mlt").write_text("<mlt/>")
        with self.assertRaisesRegex(TemplateError, "changed"):
            load_template(self.directory)

    def test_imported_template_enters_campaign_random_pool_and_plan(self):
        with patch("services.external_templates.library_root", return_value=self.library):
            campaign = normalize_campaign({"editing": {"selection_mode": "weighted_random", "template_pool": [
                {"preset_id": "standard", "enabled": False, "weight": 50},
                {"preset_id": "mlt:demo:v1", "enabled": True, "weight": 75}]}})
            choice = choose_template(campaign, "job:clip")
            self.assertEqual(choice["preset_id"], "mlt:demo:v1")
            self.assertFalse(choice["features"]["portrait"])
            self.assertTrue(campaign_processing_options(campaign)["add_captions"])
            highlight = {"start_time": "00:00:00", "end_time": "00:01:00", "editing_template": choice}
            plan = build_clip_plan({"source_id": "test", "path": str(self.source)}, highlight, campaign)
            self.assertEqual(plan["template"]["id"], "mlt:demo:v1")
            self.assertEqual(plan["template"]["canvas"]["width"], 360)
            self.assertEqual(choose_template(campaign, "different seed", existing=choice), choice)

    def test_fixed_external_campaign_plan_uses_mlt_composition(self):
        with patch("services.external_templates.library_root", return_value=self.library):
            campaign = normalize_campaign({"editing": {"preset_id": "mlt:demo:v1"}})
            plan = build_clip_plan({"source_id": "test"}, {"start_time": "00:00:00", "end_time": "00:00:40"}, campaign)
            self.assertEqual(plan["template"]["external_template"]["engine"], "mlt")

    def test_snapshot_rejects_rewritten_manifest_even_with_new_valid_checksums(self):
        with patch("services.external_templates.library_root", return_value=self.library):
            campaign = normalize_campaign({"editing": {"preset_id": "mlt:demo:v1"}})
            old_choice = choose_template(campaign, "clip")
            manifest = json.loads((self.directory / "manifest.json").read_text())
            manifest["name"] = "Different design identity"
            (self.directory / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "berubah"):
                choose_template(campaign, "clip")
            with self.assertRaisesRegex(ValueError, "berubah"):
                choose_template({}, "clip", existing=old_choice)

    def test_asset_is_copied_and_survives_author_folder_removal(self):
        asset = self.root / "logo.png"
        asset.write_bytes(b"fixture image")
        root = ET.fromstring(self.timeline.read_bytes())
        producer = ET.Element("producer", {"id": "logo", "in": "0", "out": "89"})
        ET.SubElement(producer, "property", {"name": "mlt_service"}).text = "qimage"
        ET.SubElement(producer, "property", {"name": "resource"}).text = str(asset)
        root.insert(2, producer)
        self.timeline.write_bytes(ET.tostring(root))
        self.export(version=2)
        directory, manifest = install_package(self.package, self.library)
        asset.unlink()
        self.source.unlink()
        self.timeline.unlink()
        self.package.unlink()
        self.assertEqual(load_template(directory), manifest)


class HeadlessRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            runtime_executable()
        except TemplateError as exc:
            raise unittest.SkipTest(str(exc))
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("ffmpeg unavailable")

    def test_actual_render_without_editor_or_author_project_for_two_durations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            author = root / "author"
            author.mkdir()
            placeholder = author / "placeholder.mp4"
            placeholder.write_bytes(b"not loaded at render time")
            timeline = author / "render.mlt"
            timeline.write_bytes(EXAMPLE.read_bytes())
            archive = author / "example.ssrtemplate"
            export_template(timeline, archive, source=placeholder, template_id="renderdemo", name="Render Demo")
            directory, _ = install_package(archive, root / "consumer")
            # Delete only the resolved, isolated fixture directory, never user files.
            self.assertTrue(author.resolve().is_relative_to(root.resolve()))
            shutil.rmtree(author)
            for duration in (1.4, 34.2):
                source, output = root / f"source-{duration}.mp4", root / f"output-{duration}.mp4"
                subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c=red:s=360x640:r=30:d={duration}", "-f", "lavfi", "-i", f"sine=frequency=600:duration={duration}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)], check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                result = render_template(directory, source, output, title="Judul & cerita <utuh>")
                self.assertFalse(result["editor_required"])
                self.assertTrue(result["source_audio_preserved"])
                info = probe_media(output)
                self.assertEqual((info["width"], info["height"]), (360, 640))
                self.assertAlmostEqual(info["duration"], duration, delta=.1)
                self.assertTrue(info["has_audio"])
                # The authored brightness effect must be visible away from the title.
                def red_pixel(path):
                    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "0.5", "-i", str(path),
                        "-vf", "crop=2:2:20:500,format=rgb24", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True, check=True)
                    return r.stdout[0]
                self.assertLess(red_pixel(output), red_pixel(source) - 15)

    def test_clipping_pipeline_keeps_captions_music_and_template_provenance(self):
        from services.core_workflow import CoreWorkflowMixin
        class LocalCore(CoreWorkflowMixin):
            def _render_clip_base(self, video, highlight, index, *args, **kwargs):
                directory = self.output_dir / f"clip-{index:03d}"
                directory.mkdir(parents=True, exist_ok=True)
                shutil.copy2(video, directory / "master.mp4")
            def is_cancelled(self):
                return False
            def _update_clip_state(self, index, **fields):
                self.steps.append(fields.get("step"))
            def add_captions_api_with_progress(self, source, output, **kwargs):
                # Substitute the paid transcription boundary only; burn a real subtitle.
                self.caption_style = kwargs["subtitle_style"]
                subtitle = Path(output).with_suffix(".srt")
                subtitle.write_text("1\n00:00:00,000 --> 00:00:02,200\nSubtitle test\n", encoding="utf-8")
                escaped = str(subtitle).replace("\\", "/").replace(":", "\\:")
                subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", source,
                    "-vf", f"subtitles='{escaped}'", "-c:v", "libx264",
                    "-c:a", "copy", output], check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            def log(self, message):
                pass
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, music = root / "placeholder.mp4", root / "music.wav"
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                "testsrc2=s=360x640:r=30:d=2.2", "-f", "lavfi", "-i", "sine=frequency=650:duration=2.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)], check=True)
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                "sine=frequency=220:duration=3", str(music)], check=True)
            timeline = root / "render.mlt"
            timeline.write_bytes(EXAMPLE.read_bytes())
            package = root / "example.ssrtemplate"
            export_template(timeline, package, source=source, template_id="pipeline", name="Pipeline Demo")
            library = root / "library"
            install_package(package, library)
            with patch("services.external_templates.library_root", return_value=library):
                core = LocalCore()
                core.campaign_config = normalize_campaign({"brief": {"durasi_min": 1, "durasi_max": 40}, "editing": {
                    "selection_mode": "weighted_random", "template_pool": [{"preset_id": "mlt:pipeline:v1", "enabled": True, "weight": 50}],
                    "music": {"policy": "local", "path": str(music), "volume": .15}}})
                core.output_dir = root / "output"
                core.source_analysis = {"source_id": "test:local", "path": str(source)}
                core.ffmpeg_path = "ffmpeg"
                core.watermark_settings = core.credit_watermark_settings = core.hook_style_settings = {}
                core.subtitle_language = "id"
                core.finalize_callback = None
                core._caption_lock = threading.Lock()
                core.steps = []
                highlight = {"start_time": "00:00:00", "end_time": "00:00:02.2", "duration_seconds": 2.2, "title": "Cerita lengkap",
                             "editing_template": choose_template(core.campaign_config, "clip1")}
                output = core.process_clip(str(source), highlight, 1)
                metadata = json.loads((output / "data.json").read_text(encoding="utf-8"))
                self.assertEqual(metadata["template"]["id"], "mlt:pipeline:v1")
                self.assertEqual(core.caption_style, "minimal")
                self.assertTrue(metadata["has_captions"])
                self.assertTrue(metadata["music"]["mixed"])
                self.assertTrue(metadata["template_render"]["source_audio_preserved"])
                self.assertFalse(metadata["template_render"]["editor_required"])
                self.assertTrue(metadata["final_sha256"])
                self.assertEqual(metadata["blockers"], [])

    def test_bundled_overlay_composites_after_original_asset_is_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, logo = root / "placeholder.mp4", root / "overlay.png"
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                "color=c=red:s=360x640:r=30:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                "color=c=blue:s=360x640,format=rgba", "-frames:v", "1", str(logo)], check=True)
            timeline = root / "render.mlt"
            xml = ET.fromstring(EXAMPLE.read_bytes())
            producer = ET.Element("producer", {"id": "overlay", "in": "0", "out": "89"})
            ET.SubElement(producer, "property", {"name": "mlt_service"}).text = "qimage"
            ET.SubElement(producer, "property", {"name": "resource"}).text = str(logo)
            xml.insert(2, producer)
            playlist = ET.Element("playlist", {"id": "overlay_track", "in": "0", "out": "89"})
            ET.SubElement(playlist, "entry", {"producer": "overlay", "in": "0", "out": "89"})
            xml.insert(len(xml)-1, playlist)
            tractor = xml.find("tractor")
            ET.SubElement(tractor, "track", {"producer": "overlay_track"})
            transition = ET.SubElement(tractor, "transition", {"in": "0", "out": "89"})
            for key, value in {"mlt_service": "qtblend", "a_track": "0", "b_track": "1"}.items():
                ET.SubElement(transition, "property", {"name": key}).text = value
            timeline.write_bytes(ET.tostring(xml))
            package = root / "example.ssrtemplate"
            export_template(timeline, package, source=source, template_id="layers", name="Layer Demo")
            directory, _ = install_package(package, root / "library")
            logo.unlink()
            timeline.unlink()
            package.unlink()
            output = root / "output.mp4"
            result = render_template(directory, source, output)
            self.assertFalse(result["source_audio_preserved"])
            pixel = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(output), "-vf",
                "crop=2:2:20:500,format=rgb24", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
            self.assertGreater(pixel[2], 200)
            self.assertLess(pixel[0], 30)
