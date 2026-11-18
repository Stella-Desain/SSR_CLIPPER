"""Source-proof mistakes get one fresh assessment without bypassing hard gates."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services.highlight_profiles import GATES, SCORE_WEIGHTS, normalize_highlight_profile, profile_fingerprint
from services.speech_boundaries import timestamp


TRANSCRIPT = ("[00:00:00,000 - 00:00:10,000] Kenapa tabungan penting?\n"
              "[00:00:10,000 - 00:00:20,000] Karena dana darurat membantu saat pekerjaan hilang.\n"
              "[00:00:20,000 - 00:00:30,000] Jadi sisihkan penghasilan secara rutin.\n"
              "[00:00:30,000 - 00:00:40,000] Tapi jangan abaikan kebutuhan pokok keluarga.\n"
              "[00:00:45,000 - 00:00:55,000] Bagaimana menjaga keluarga?\n"
              "[00:00:55,000 - 00:01:05,000] Dengarkan anak dan sediakan waktu bersama.\n"
              "[00:01:05,000 - 00:01:15,000] Jadi jadwalkan percakapan setiap hari.")
PROFILE = normalize_highlight_profile({"audience": "Pekerja yang ingin menabung"})


def highlight(*, start=0, bad_quote=False, hard_gate=False, title="Tabungan penting"):
    rows = ([(0, 10, "Kenapa tabungan penting?"),
             (10, 20, "Dana darurat pasti membuatmu kaya." if bad_quote else "Karena dana darurat membantu saat pekerjaan hilang."),
             (20, 30, "Jadi sisihkan penghasilan secara rutin.")]
            if start == 0 else
            [(45, 55, "Bagaimana menjaga keluarga?"),
             (55, 65, "Dengarkan anak dan sediakan waktu bersama."),
             (65, 75, "Jadi jadwalkan percakapan setiap hari.")])
    gates = {name: True for name in GATES}
    if hard_gate:
        gates["audience_match"] = False
    return {"start_time": timestamp(rows[0][0]), "end_time": timestamp(rows[-1][1]),
        "title": title, "description": "Caption sesuai sumber", "hook_text": rows[0][2],
        "selection": {"version": 1, "profile_hash": profile_fingerprint(PROFILE),
            "scores": {name: 80 for name in SCORE_WEIGHTS}, "gates": gates,
            "reason": "Membahas kebutuhan audiens dengan langkah jelas", "matched_patterns": [],
            "evidence": [{"part": part, "start_time": timestamp(a), "end_time": timestamp(b), "quote": quote}
                for part, (a, b, quote) in zip(("opening", "message", "ending"), rows)]}}


def client_with_responses(*responses):
    create = Mock(side_effect=[value if isinstance(value, Exception) else
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(value) if not isinstance(value, str) else value))]) for value in responses])
    client = SimpleNamespace(base_url="https://example.invalid",
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, create


class HighlightEvidenceWorkflowTests(unittest.TestCase):
    def _run(self, root, client, *, align=None, plan_only=False):
        from clipper_core import AutoClipperCore
        source = root / "source.mp4"
        source.write_bytes(b"offline source fixture")
        source.with_suffix(".srt").write_text("fixture", encoding="utf-8")
        core = AutoClipperCore(client=None, output_dir=root / "output", log_callback=lambda *_: None)
        core.campaign_config = {"highlight_profile": PROFILE}
        core.highlight_client = client
        core.parse_srt = Mock(return_value=TRANSCRIPT)
        rendered = []
        core.process_clip = lambda _path, item, *_args: rendered.append(copy.deepcopy(item))
        media = {"has_video": True, "has_audio": True, "duration": 75}
        with patch("services.core_workflow.probe_media", return_value=media), \
                patch("services.core_workflow.SpeechBoundaryAligner") as aligner:
            aligner.return_value.align.side_effect = align or (lambda item, *_: copy.deepcopy(item))
            core.process(str(source), fixed_count=1, dur_min=25, dur_max=40, plan_only=plan_only)
        return rendered, core, root / "output"

    def test_plan_only_validates_and_saves_without_starting_renderer(self):
        invalid = highlight(bad_quote=True, hard_gate=True, title="Di luar audiens")
        valid = highlight(start=45, title="Untuk keluarga")
        client, create = client_with_responses([invalid, valid])
        with tempfile.TemporaryDirectory() as folder:
            rendered, core, output = self._run(Path(folder), client, plan_only=True)
            self.assertEqual(rendered, [])
            self.assertEqual(core.get_clips_state(), [])
            plan = json.loads(next(output.glob("job-*/highlights.json")).read_text(encoding="utf-8"))
            self.assertEqual([item["title"] for item in plan["highlights"]], ["Untuk keluarga"])
            self.assertTrue(plan["highlights"][0]["selection"]["verified_source"])
            self.assertEqual(create.call_count, 1)

    def test_bad_source_quote_is_reassessed_after_alignment_then_renders(self):
        original = highlight(bad_quote=True)
        revised = highlight()["selection"]
        client, create = client_with_responses([original], revised)
        with tempfile.TemporaryDirectory() as folder:
            rendered, _core, output = self._run(Path(folder), client)
            self.assertEqual(len(rendered), 1)
            self.assertEqual(rendered[0]["title"], original["title"])
            self.assertTrue(rendered[0]["selection"]["verified_source"])
            self.assertEqual(create.call_count, 2)
            self.assertFalse(list(output.glob("job-*/highlight_rejections.json")))

    def test_false_hard_gate_is_not_retried_and_other_candidate_survives(self):
        rejected = highlight(bad_quote=True, hard_gate=True, title="Di luar audiens")
        valid = highlight(start=45, title="Untuk keluarga")
        client, create = client_with_responses([rejected, valid])
        with tempfile.TemporaryDirectory() as folder:
            rendered, _core, output = self._run(Path(folder), client)
            self.assertEqual([item["title"] for item in rendered], ["Untuk keluarga"])
            self.assertEqual(create.call_count, 1)
            log = next(output.glob("job-*/highlight_rejections.json"))
            reasons = json.loads(log.read_text(encoding="utf-8"))["candidates"][0]["reasons"]
            self.assertTrue(any("audiens" in reason for reason in reasons))

    def test_still_unsupported_quote_is_rejected_without_losing_valid_candidate(self):
        invalid = highlight(bad_quote=True)
        valid = highlight(start=45, title="Untuk keluarga")
        client, create = client_with_responses([invalid, valid], invalid["selection"])
        with tempfile.TemporaryDirectory() as folder:
            rendered, _core, output = self._run(Path(folder), client)
            self.assertEqual([item["title"] for item in rendered], ["Untuk keluarga"])
            self.assertEqual(create.call_count, 2)
            log = next(output.glob("job-*/highlight_rejections.json"))
            self.assertEqual(json.loads(log.read_text(encoding="utf-8"))["candidates"][0]["title"], invalid["title"])

    def test_malformed_fresh_assessment_does_not_abort_valid_candidate(self):
        invalid = highlight(bad_quote=True)
        valid = highlight(start=45, title="Untuk keluarga")
        client, create = client_with_responses([invalid, valid], "not JSON")
        with tempfile.TemporaryDirectory() as folder:
            rendered, _core, output = self._run(Path(folder), client)
            self.assertEqual([item["title"] for item in rendered], ["Untuk keluarga"])
            self.assertEqual(create.call_count, 2)
            log = next(output.glob("job-*/highlight_rejections.json"))
            self.assertIn("JSON", json.loads(log.read_text(encoding="utf-8"))["candidates"][0]["reasons"][0])

    def test_untimed_visual_description_is_rejected_without_paid_recheck(self):
        from clipper_core import AutoClipperCore
        client, create = client_with_responses([highlight()])
        with tempfile.TemporaryDirectory() as folder:
            core = AutoClipperCore(client=None, output_dir=folder, log_callback=lambda *_: None)
            core.campaign_config = {"highlight_profile": PROFILE}
            core.highlight_client = client
            found = core._find_campaign_highlights("[00:00:00] Terlihat orang berbicara.",
                {"duration": 75}, 30, 1, 6, 25, 40)
            self.assertEqual(found, [])
            self.assertEqual(create.call_count, 1)
            self.assertTrue(core._highlight_profile_rejections)

    def test_verifier_provider_failure_skips_one_candidate_and_keeps_other(self):
        invalid = highlight(bad_quote=True)
        valid = highlight(start=45, title="Untuk keluarga")
        client, create = client_with_responses([invalid, valid], RuntimeError("offline provider error"))
        with tempfile.TemporaryDirectory() as folder:
            rendered, _core, output = self._run(Path(folder), client)
            self.assertEqual([item["title"] for item in rendered], ["Untuk keluarga"])
            self.assertEqual(create.call_count, 2)
            log = next(output.glob("job-*/highlight_rejections.json"))
            self.assertIn("RuntimeError", json.loads(log.read_text(encoding="utf-8"))["candidates"][0]["reasons"][0])

    def test_same_range_valid_proof_replaces_deferred_duplicate(self):
        from clipper_core import AutoClipperCore
        deferred = highlight(bad_quote=True)
        valid = highlight(title="Bukti valid")
        with tempfile.TemporaryDirectory() as folder:
            core = AutoClipperCore(client=None, output_dir=folder, log_callback=lambda *_: None)
            core.campaign_config = {"highlight_profile": PROFILE}
            def generated(*_args, **_kwargs):
                core._profile_candidates_required = True
                return [deferred, valid]
            core.find_highlights = generated
            result = core._find_campaign_highlights(TRANSCRIPT, {"duration": 75}, 30, 1, 6, 25, 40)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["title"], "Bukti valid")
            self.assertTrue(result[0]["selection"]["verified_source"])

    def test_rolling_candidate_reverified_after_audio_supported_end(self):
        from clipper_core import AutoClipperCore
        rolling = ("[00:00:00,000 - 00:00:08,000] Dengarkan pembuka ini.\n"
                   "[00:00:08,000 - 00:00:20,000] Intinya kamu bisa mencoba lagi.\n"
                   "[00:00:20,000 - 00:00:32,000] Hari ini bukan akhir segalanya.\n"
                   "[00:00:29,000 - 00:00:34,000] Sesudahnya mulai kisah lain")
        original = highlight()
        original["end_time"] = timestamp(30)
        original["selection"]["evidence"] = [
            {"part": "opening", "start_time": timestamp(0), "end_time": timestamp(8), "quote": "Dengarkan pembuka ini."},
            {"part": "message", "start_time": timestamp(8), "end_time": timestamp(20), "quote": "Intinya kamu bisa mencoba lagi."},
            {"part": "ending", "start_time": timestamp(20), "end_time": timestamp(30), "quote": "Hari ini bukan akhir segalanya."},
        ]
        revised = copy.deepcopy(original["selection"])
        revised["evidence"][2]["end_time"] = timestamp(29.3)
        client, create = client_with_responses([original], revised)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mp4"
            source.write_bytes(b"offline source fixture")
            source.with_suffix(".srt").write_text("fixture", encoding="utf-8")
            core = AutoClipperCore(client=None, output_dir=root / "output", log_callback=lambda *_: None)
            core.campaign_config = {"highlight_profile": PROFILE}
            core.highlight_client = client
            core.parse_srt = Mock(return_value=rolling)
            rendered = []
            core.process_clip = lambda _path, item, *_args: rendered.append(copy.deepcopy(item))
            with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": True, "duration": 75}), \
                    patch("services.speech_boundaries.detect_pauses", return_value=[(29.1, 29.5)]):
                core.process(str(source), fixed_count=1, dur_min=28, dur_max=40)
            self.assertEqual(len(rendered), 1)
            self.assertEqual(rendered[0]["end_time"], timestamp(29.3))
            self.assertEqual(rendered[0]["speech_boundary"]["method"], "rolling_sentence_pause")
            self.assertTrue(rendered[0]["selection"]["verified_source"])
            self.assertEqual(create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
