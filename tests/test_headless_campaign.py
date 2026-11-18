import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from services.editing import file_sha256
from tools.run_headless_campaign import AuditedModel, EXPECTED_MODEL, load_library, validate_music_choices


class HeadlessCampaignTests(unittest.TestCase):
    def test_stream_is_assembled_audited_and_reused_after_restart(self):
        requests = []
        def create(**request):
            requests.append(request)
            return iter([SimpleNamespace(model=EXPECTED_MODEL, id="stream-1", usage=None,
                choices=[SimpleNamespace(index=0, delta=SimpleNamespace(content=part), finish_reason=finish)])
                for part, finish in [(' {"ok":', None), ('true}', "stop")]])
        client = SimpleNamespace(base_url="https://example.invalid/v1",
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as folder:
            model = AuditedModel({"model": EXPECTED_MODEL}, folder, client, streaming=True)
            self.assertEqual(model.ask("test", {}, "test"), {"ok": True})
            model = AuditedModel({"model": EXPECTED_MODEL}, folder, client, streaming=True)
            self.assertEqual(model.ask("test", {}, "test"), {"ok": True})
            self.assertEqual(len(requests), 1)
            self.assertTrue(requests[0]["stream"])
            self.assertEqual(model.calls[-1]["cache_source_call"], model.calls[-2]["id"])

    def test_incomplete_stream_is_not_accepted(self):
        client = SimpleNamespace(base_url="https://example.invalid/v1",
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **request: iter([
                SimpleNamespace(model=EXPECTED_MODEL, id="stream-1", usage=None,
                    choices=[SimpleNamespace(index=0, delta=SimpleNamespace(content='{"ok":true}'), finish_reason=None)])]))))
        with tempfile.TemporaryDirectory() as folder:
            model = AuditedModel({"model": EXPECTED_MODEL}, folder, client, streaming=True)
            with self.assertRaisesRegex(ValueError, "penanda selesai"):
                model.create(messages=[])
            self.assertEqual(model.calls[-1]["status"], "failed")

    def test_shorter_transcript_chunks_keep_timed_context_and_cover_source(self):
        from services.core_workflow import CoreWorkflowMixin
        from services.speech_boundaries import parse_cues, timestamp
        core = CoreWorkflowMixin()
        core.system_prompt, core.campaign_config = "", {}
        core.highlight_chunk_chars, core.highlight_context_seconds = 1200, 30
        core.is_cancelled, core.log = lambda: False, lambda *_: None
        captured = []
        core.find_highlights = lambda chunk, *args, **kwargs: captured.append(chunk) or []
        source = "\n".join(f"[{timestamp(i)} - {timestamp(i+5)}] Satu kalimat lengkap dengan konteks." for i in range(0, 600, 5))
        core._find_campaign_highlights(source, {"duration": 600}, 500, None, 6, 28, 70)
        chunks = [parse_cues(chunk) for chunk in captured]
        self.assertGreater(len(chunks), 1)
        self.assertEqual({cue["start"] for chunk in chunks for cue in chunk}, {cue["start"] for cue in parse_cues(source)})
        for previous, current in zip(chunks, chunks[1:]):
            self.assertLessEqual(current[0]["start"], previous[-1]["end"]-30)

    def test_parallel_analysis_keeps_campaign_prompt_until_workers_finish(self):
        import threading
        from services.core_workflow import CoreWorkflowMixin
        from services.speech_boundaries import timestamp
        core = CoreWorkflowMixin()
        core.system_prompt, core.campaign_config = "original", {}
        core.highlight_chunk_chars, core.highlight_context_seconds = 1200, 30
        core.highlight_request_workers = 2
        core.is_cancelled, core.log = lambda: False, lambda *_: None
        barrier, lock, captured = threading.Barrier(2), threading.Lock(), []
        def find(chunk, *args, **kwargs):
            with lock:
                first_pair = len(captured) < 2
                captured.append(core.system_prompt)
            if first_pair:
                barrier.wait(timeout=3)
            self.assertNotEqual(core.system_prompt, "original")
            return []
        core.find_highlights = find
        source = "\n".join(f"[{timestamp(i)} - {timestamp(i+5)}] Satu kalimat lengkap dengan konteks." for i in range(0, 600, 5))
        core._find_campaign_highlights(source, {"duration": 600}, 500, None, 6, 28, 70)
        self.assertGreater(len(captured), 1)
        self.assertEqual(core.system_prompt, "original")
        self.assertTrue(all(prompt == captured[0] for prompt in captured))

    def test_model_and_effort_are_forced_and_temperature_removed(self):
        requests = []

        def create(**request):
            requests.append(request)
            return SimpleNamespace(model=EXPECTED_MODEL, id="response-1", usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])

        client = SimpleNamespace(base_url="https://example.invalid/v1",
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as folder:
            model = AuditedModel({"model": "Codex-6.1sol"}, folder, client)
            model.create(model="other", reasoning_effort="low", temperature=.2, messages=[])
            self.assertEqual(requests[0]["model"], "Codex-6.1sol")
            self.assertEqual(requests[0]["reasoning_effort"], "xhigh")
            self.assertNotIn("temperature", requests[0])
            self.assertEqual(model.calls[0]["returned_model"], EXPECTED_MODEL)
            self.assertEqual(model.calls[0]["status"], "completed")
            self.assertTrue((Path(folder) / "ai-calls.json").is_file())

    def test_different_returned_model_is_rejected_without_fallback(self):
        response = SimpleNamespace(model="other-model", id="response-1", usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])
        client = SimpleNamespace(base_url="https://example.invalid/v1",
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
        with tempfile.TemporaryDirectory() as folder:
            model = AuditedModel({"model": "Codex-6.1sol"}, folder, client)
            with self.assertRaisesRegex(ValueError, "model tidak diganti"):
                model.create(messages=[])
            self.assertEqual(len(model.calls), 1)
            self.assertEqual(model.calls[0]["status"], "failed")

    def test_music_requires_one_available_choice_for_every_clip(self):
        available = {"clip1": {"music1": {"id": "music1"}}, "clip2": {"music2": {"id": "music2"}}}
        valid = {"choices": [{"clip_id": "clip1", "candidate_id": "music1", "reason": "Data tersedia"},
                             {"clip_id": "clip2", "candidate_id": "music2", "reason": "Durasi cukup"}]}
        self.assertEqual(set(validate_music_choices(valid, available)), set(available))
        with self.assertRaisesRegex(ValueError, "Tidak semua clip"):
            validate_music_choices({"choices": valid["choices"][:1]}, available)
        with self.assertRaisesRegex(ValueError, "tidak tersedia"):
            validate_music_choices({"choices": [{"clip_id": "clip1", "candidate_id": "foreign", "reason": "x"}]}, available)
        with self.assertRaisesRegex(ValueError, "duplikat"):
            validate_music_choices({"choices": [valid["choices"][0], valid["choices"][0]]}, available)

    def test_library_verifies_hashes_and_rejects_outside_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            library = root / "library"
            library.mkdir()
            audio = library / "track.mp3"
            audio.write_bytes(b"fixture")
            track = {"file": audio.name, "tiktok_music_id": "123", "sha256": file_sha256(audio)}
            manifest = library / "library.json"
            manifest.write_text(json.dumps({"tracks": [track]}), encoding="utf-8")
            self.assertEqual(load_library(library)[0]["path"], str(audio.resolve()))
            audio.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash"):
                load_library(library)
            outside = root / "outside.mp3"
            outside.write_bytes(b"fixture")
            track.update(file="../outside.mp3", sha256=file_sha256(outside))
            manifest.write_text(json.dumps({"tracks": [track]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "di luar"):
                load_library(library)


if __name__ == "__main__":
    unittest.main()
