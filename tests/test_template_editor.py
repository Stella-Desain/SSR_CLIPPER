"""Draft lifecycle, portable publication and asynchronous preview bridge tests."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

from services.template_editor import TemplateEditorMixin, _preview_words
from template_sdk.ssr_template_engine.design import load_design


class PreviewStub:
    def __init__(self):
        self.registered = []

    def register(self, path):
        self.registered.append(str(path))
        return "http://127.0.0.1:12345/" + str(len(self.registered))


class EditorAPI(TemplateEditorMixin):
    pass


class TemplateEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.library = self.root / "library"
        self.patches = [patch("services.template_editor.editor_root", return_value=self.projects),
                        patch("services.external_templates.library_root", return_value=self.library),
                        patch("services.media_preview.MediaPreview", PreviewStub)]
        for item in self.patches:
            item.start()
        self.api = EditorAPI()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def create(self, **options):
        result = self.api.editor_create_project({"name": "Demo", **options})
        self.assertEqual(result["status"], "ok", result)
        return result["project"]

    def image(self, name="logo.png"):
        path = self.root / name
        Image.new("RGBA", (40, 20), "red").save(path)
        return path

    def save(self, model):
        result = self.api.editor_save_project(model)
        self.assertEqual(result["status"], "ok", result)
        return result["project"]

    def test_atomic_draft_reopen_stale_save_preserves_latest_edit(self):
        project = self.create()
        stale = copy.deepcopy(project)
        project["name"] = "Perubahan terbaru"
        saved = self.save(project)
        self.assertEqual(saved["revision"], project["revision"] + 1)
        stale["name"] = "Edit terlambat"
        failure = self.api.editor_save_project(stale)
        self.assertEqual(failure["status"], "error")
        self.assertTrue(failure["conflict"])
        reopened = EditorAPI().editor_get_project(project["id"])["project"]
        self.assertEqual(reopened["name"], "Perubahan terbaru")
        self.assertFalse(any(path.name.startswith("project-") for path in self.projects.rglob("*")))

    def test_save_cannot_create_unknown_draft_or_escape_storage(self):
        project = self.create()
        project["id"] = "design-" + "0" * 32
        self.assertEqual(self.api.editor_save_project(project)["status"], "error")
        self.assertEqual(self.api.editor_get_project("../outside")["status"], "error")
        self.assertEqual(len(list(self.projects.glob("*/project.json"))), 1)

    def test_invalid_new_project_is_not_saved_and_partial_import_folder_is_ignored(self):
        self.assertEqual(self.api.editor_create_project({"name": "x" * 121})["status"], "error")
        self.assertEqual(self.api.editor_create_project({"ratio": "invalid"})["status"], "error")
        project = self.create()
        (self.projects / ("design-" + "0" * 32)).mkdir()
        listed = self.api.editor_list_projects()
        self.assertEqual(listed["status"], "ok", listed)
        self.assertEqual([item["id"] for item in listed["projects"]], [project["id"]])

    def test_asset_copied_urls_cached_and_forged_asset_rejected(self):
        project = self.create()
        source = self.image()
        added = self.api.editor_add_asset(project["id"], str(source), "image")
        self.assertEqual(added["status"], "ok", added)
        asset, model = added["asset"], added["project"]
        self.assertEqual((asset["width"], asset["height"]), (40, 20))
        source.unlink()
        self.assertTrue((self.projects / model["id"] / asset["path"]).is_file())
        reopened = self.api.editor_get_project(model["id"])["project"]
        self.assertEqual(asset["url"], reopened["assets"][0]["url"])
        self.assertEqual(len(self.api._media_preview.registered), 1)
        on_disk = json.loads((self.projects / model["id"] / "project.json").read_text())
        self.assertNotIn("url", on_disk["assets"][0])
        model["assets"][0]["path"] = "../outside.png"
        self.assertEqual(self.api.editor_save_project(model)["status"], "error")

    def test_duplicate_owns_assets_and_archive_preserves_published_version(self):
        project = self.create()
        added = self.api.editor_add_asset(project["id"], str(self.image()), "image")
        project = added["project"]
        published = self.api.editor_publish_project(project["id"])
        self.assertEqual(published["status"], "ok", published)
        copied = self.api.editor_duplicate_project(project["id"])["project"]
        self.assertNotEqual(copied["id"], project["id"])
        self.assertEqual(copied["published_versions"], [])
        self.assertTrue((self.projects / copied["id"] / copied["assets"][0]["path"]).is_file())
        archived = self.api.editor_archive_project(project["id"], True)
        self.assertEqual(archived["status"], "ok")
        listing = self.api.editor_list_projects()
        self.assertEqual(len(listing["presets"]), 0)
        self.assertEqual(load_design(self.library / (project["id"] + "-v1"))["id"], project["id"])
        self.assertTrue(next(item for item in listing["projects"] if item["id"] == project["id"])["archived"])
        self.assertEqual(self.api.editor_publish_project(project["id"])["status"], "error")
        self.api.editor_archive_project(project["id"], False)
        self.assertEqual(len(self.api.editor_list_projects()["presets"]), 1)

    def test_publish_versions_immutable_and_sample_sources_never_bundled(self):
        model = self.create()
        sample = self.root / "private-sample.mp4"
        sample.write_bytes(b"sample")
        with patch("services.editing.probe_media", return_value={"duration": 42.5, "has_audio": True, "has_video": True}):
            added = self.api.editor_add_asset(model["id"], str(sample), "video")
        self.assertEqual(added["project"]["preview"]["duration"], 42.5)
        first = self.api.editor_publish_project(model["id"])
        self.assertEqual(first["status"], "ok", first)
        original = Path(first["path"]).read_bytes()
        with zipfile.ZipFile(first["path"]) as package:
            self.assertEqual(set(package.namelist()), {"manifest.json", "design.json"})
            self.assertNotIn(str(sample), package.read("design.json").decode())
            self.assertNotIn("preview", json.loads(package.read("design.json")))
        current = first["project"]
        current["canvas"]["background"] = "#ff0000"
        self.save(current)
        second = self.api.editor_publish_project(model["id"])
        self.assertEqual(second["status"], "ok", second)
        self.assertEqual(second["preset"]["version"], 2)
        self.assertEqual(Path(first["path"]).read_bytes(), original)
        old = load_design(self.library / (model["id"] + "-v1"))
        self.assertEqual(old["canvas"]["background"], "#101820")
        sample.unlink()
        self.assertEqual(load_design(self.library / (model["id"] + "-v2"))["canvas"]["background"], "#ff0000")

    def test_export_import_restores_editable_design_and_portable_assets(self):
        model = self.create(ratio="16:9")
        result = self.api.editor_add_asset(model["id"], str(self.image()), "image")
        package = self.root / "exported.ssrtemplate"
        exported = self.api.editor_export_project(model["id"], str(package))
        self.assertEqual(exported["status"], "ok", exported)
        self.assertEqual(self.api.editor_list_projects()["presets"], [])
        imported = self.api.editor_import_project(str(package))
        self.assertEqual(imported["status"], "ok", imported)
        self.assertTrue(imported["editable"])
        draft = imported["project"]
        self.assertNotEqual(draft["id"], model["id"])
        self.assertEqual(draft["canvas"], model["canvas"])
        self.assertEqual(draft["preview"]["video_path"], "")
        asset = draft["assets"][0]
        self.assertEqual((self.projects / draft["id"] / asset["path"]).read_bytes(),
                         (self.projects / model["id"] / result["asset"]["path"]).read_bytes())

    def test_preview_files_must_be_explicitly_imported_and_sample_subtitles_parsed(self):
        model = self.create()
        private = self.root / "config.json"
        private.write_text('{"key":"private"}')
        self.assertEqual(self.api.editor_media_preview(str(private))["status"], "error")
        source = self.root / "sample.srt"
        source.write_text("1\n00:00:01,000 --> 00:00:02,500\nKalimat lengkap.\n", encoding="utf-8")
        result = self.api.editor_add_asset(model["id"], str(source), "subtitle")
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["project"]["preview"]["subtitle_cues"],
                         [{"start": 1, "end": 2.5, "text": "Kalimat lengkap."}])
        self.assertEqual(result["project"]["assets"], [])
        self.assertEqual(self.api.editor_media_preview(str(source))["status"], "ok")
        altered = result["project"]
        altered["preview"]["video_path"] = str(private)
        self.assertEqual(self.api.editor_save_project(altered)["status"], "error")

    def prepare_sample(self):
        model = self.create()
        sample = self.root / "sample.mp4"
        sample.write_bytes(b"sample")
        with patch("services.editing.probe_media", return_value={"duration": 2, "has_audio": True, "has_video": True}):
            result = self.api.editor_add_asset(model["id"], str(sample), "video")
        self.assertEqual(result["status"], "ok", result)
        return result["project"]

    def test_async_preview_progress_cancellation_and_frozen_revision(self):
        model = self.prepare_sample()
        started, stopped = threading.Event(), threading.Event()
        seen = {}
        def render(model, root, source, output, **options):
            seen.update(options)
            options["progress"](45)
            started.set()
            options["cancel_event"].wait(2)
            stopped.set()
            raise ValueError("cancelled")
        with patch("template_sdk.ssr_template_engine.design.render_design", side_effect=render):
            result = self.api.editor_start_render(model["id"], {"timeout": 90})
            self.assertEqual(result["status"], "ok", result)
            render_id = result["render"]["id"]
            self.assertTrue(started.wait(2))
            record = self.api.editor_get_render(render_id)["render"]
            self.assertEqual(record["progress"], 45)
            self.assertEqual(record["revision"], model["revision"])
            self.assertNotIn("_cancel", record)
            self.assertEqual(self.api.editor_start_render(model["id"])["status"], "error")
            self.api.editor_cancel_render(render_id)
            self.assertTrue(stopped.wait(2))
            self.api._editor_renders[render_id]["_thread"].join(2)
            self.assertEqual(self.api.editor_get_render(render_id)["render"]["status"], "cancelled")
            self.assertEqual(seen["timeout"], 90)

    def test_async_preview_failure_and_success_preserve_draft(self):
        model = self.prepare_sample()
        with patch("template_sdk.ssr_template_engine.design.render_design", side_effect=ValueError("Font belum tersedia")):
            first = self.api.editor_start_render(model["id"])
            render_id = first["render"]["id"]
            self.api._editor_renders[render_id]["_thread"].join(2)
            record = self.api.editor_get_render(render_id)["render"]
            self.assertEqual(record["status"], "failed")
            self.assertIn("Font", record["message"])
        def render(model, root, source, output, **options):
            Path(output).write_bytes(b"preview")
        with patch("template_sdk.ssr_template_engine.design.render_design", side_effect=render):
            second = self.api.editor_start_render(model["id"])
            render_id = second["render"]["id"]
            self.api._editor_renders[render_id]["_thread"].join(2)
            record = self.api.editor_get_render(render_id)["render"]
            self.assertEqual((record["status"], record["progress"]), ("completed", 100))
            self.assertTrue(record["url"].startswith("http://127.0.0.1:"))
        self.assertEqual(self.api.editor_get_project(model["id"])["project"]["revision"], model["revision"])

    def test_missing_sample_and_unavailable_font_report_actionable_error(self):
        model = self.create()
        self.assertIn("video contoh", self.api.editor_start_render(model["id"])["message"])
        model["layers"].append({"id": "text", "type": "text", "name": "Judul", "x": 0, "y": 0,
                                "width": 800, "height": 100, "font_family": "FontTidakAda"})
        model = self.save(model)
        with patch("utils.font_scanner.get_path_for_name", return_value=None):
            result = self.api.editor_publish_project(model["id"])
        self.assertEqual(result["status"], "error")
        self.assertIn("impor font", result["message"])
        self.assertEqual(self.api.editor_get_project(model["id"])["project"]["published_versions"], [])

    def test_font_selection_is_bundled_and_survives_original_font_removal(self):
        model = self.create()
        model["layers"].append({"id": "text", "type": "text", "name": "Judul", "x": 0, "y": 0,
                                "width": 800, "height": 100, "font_family": "Roboto"})
        model = self.save(model)
        font = self.root / "original.ttf"
        font.write_bytes((Path(__file__).resolve().parents[1] / "assets" / "fonts" / "RobotoVariable.ttf").read_bytes())
        with patch("utils.font_scanner.get_path_for_name", return_value=str(font)):
            result = self.api.editor_publish_project(model["id"])
        self.assertEqual(result["status"], "ok", result)
        font.unlink()
        published = load_design(self.library / (model["id"] + "-v1"))
        layer = next(item for item in published["layers"] if item["id"] == "text")
        asset = next(item for item in published["assets"] if item["id"] == layer["font_asset_id"])
        self.assertEqual(asset["kind"], "font")
        self.assertTrue((self.library / (model["id"] + "-v1") / asset["path"]).is_file())

    def test_audio_only_and_invalid_duration_cannot_replace_sample_video(self):
        model = self.prepare_sample()
        original = model["preview"]["video_path"]
        invalid = self.root / "audio-only.mp4"
        invalid.write_bytes(b"audio")
        for info in ({"duration": 2, "has_video": False}, {"duration": float("nan"), "has_video": True},
                     {"duration": 3601, "has_video": True}):
            with patch("services.editing.probe_media", return_value=info):
                result = self.api.editor_add_asset(model["id"], str(invalid), "video")
            self.assertEqual(result["status"], "error")
            self.assertEqual(self.api.editor_get_project(model["id"])["project"]["preview"]["video_path"], original)

    def test_minute_only_vtt_is_normalized_to_render_words(self):
        model = self.prepare_sample()
        vtt = self.root / "sample.vtt"
        vtt.write_text("WEBVTT\n\n00:00.100 --> 00:01.900 align:start\nKalimat lengkap.\n", encoding="utf-8")
        added = self.api.editor_add_asset(model["id"], str(vtt), "subtitle")
        self.assertEqual(added["status"], "ok", added)
        seen = {}
        def render(model, root, source, output, **options):
            seen.update(options)
            Path(output).write_bytes(b"preview")
        with patch("template_sdk.ssr_template_engine.design.render_design", side_effect=render):
            result = self.api.editor_start_render(model["id"])
            render_id = result["render"]["id"]
            self.api._editor_renders[render_id]["_thread"].join(2)
        self.assertEqual([item["word"] for item in seen["subtitle_words"]], ["Kalimat", "lengkap."])
        self.assertAlmostEqual(seen["subtitle_words"][-1]["end"], 1.9)

    def test_segment_json_without_word_array_uses_same_preview_words_as_srt(self):
        model = self.create()
        subtitle = self.root / "sample.json"
        subtitle.write_text(json.dumps({"segments": [{"start": 0, "end": 2, "text": "Kalimat lengkap"}]}))
        added = self.api.editor_add_asset(model["id"], str(subtitle), "subtitle")
        self.assertEqual(added["status"], "ok", added)
        self.assertEqual(_preview_words(subtitle), [
            {"word": "Kalimat", "start": 0, "end": 1}, {"word": "lengkap", "start": 1, "end": 2}])


if __name__ == "__main__":
    unittest.main()
