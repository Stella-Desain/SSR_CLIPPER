"""Per-clip ranking uses actual candidate audio and never invents a track ID."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app import WebAPI
from services.campaigns import normalize_campaign
from services.music_selection import MusicSelector, choose_window, download_track, measure_track, trend_catalog
from services.workflow import WorkflowMixin


def profile(rms):
    return {"version": 1, "sha256": "fixture", "duration_seconds": len(rms),
        "analyzed_seconds": len(rms), "rms": rms, "bass_ratio": [.5] * len(rms),
        "brightness_hz": [500] * len(rms), "method": "fixture"}


class MusicSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.track = self.root / "track.mp3"
        self.track.write_bytes(b"fixture")
        self.api = SimpleNamespace(
            get_jamendo_tracks=Mock(return_value={"status": "ok", "tracks": [
                {"id": "first", "name": "First result", "audiodownload": "https://test/1"},
                {"id": "better", "name": "Better fit", "audiodownload": "https://test/2"}]}),
            get_repliz_tiktok_music=Mock(return_value={"status": "ok", "tracks": [
                {"id": "7550444803676866577", "name": "NOW OR NEVER", "url": "https://test/reference"}]}))
        self.selector = MusicSelector.__new__(MusicSelector)
        self.selector.api, self.selector.cfg, self.selector.cache = self.api, {}, self.root
        self.selector.audio_analyzer = Mock()
        self.selector.audio_analyzer.analyze.return_value = {"identity": {"start": 0, "seconds": 12},
            "observations": {"segments": [{"start": 0, "end": 12, "mood": "reflektif", "confidence": .9}],
                             "phrase_starts": [0, 3, 6], "limitations": "fixture"},
            "provenance": {"requested_model": "Visual-AI", "returned_model": "fixture"}, "cache_hit": False}
        self.metadata = {"title": "Belajar dari kesalahan", "transcript": "Turunkan ego, ambil pelajarannya.", "duration_seconds": 4}
        self.criteria = {"tags": "hiphop atmospheric", "speed": "medium", "genre": "HIP_HOP/RAP",
                         "mood": "tegas", "energy": "medium", "arc": "steady", "reason": "Pesan self-growth"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_selection(self, rankings=None, ids=None, settings=None, measurement=None):
        ranking = rankings if rankings is not None else {"rankings": [
            {"candidate_id": "first:0", "score": 10, "reason": "Kurang cocok"},
            {"candidate_id": "better:0", "score": 95, "reason": "Mendukung pesan belajar tanpa menutupi dialog"}], "review_required": False}
        self.selector.ask = Mock(side_effect=[self.criteria, {"ids": ids or ["first", "better"]}, ranking])
        with patch("services.music_selection.download_track", return_value=self.track), \
                patch("services.music_selection.measure_track", side_effect=measurement or (lambda *_: profile([.1] * 12))):
            return self.selector.select(self.metadata, {"name": "Self-growth", "editing": {"music": settings or {}}})

    def test_best_fit_can_beat_first_search_result_and_metadata_explains_it(self):
        result = self.run_selection()
        self.assertEqual(result["id"], "better")
        self.assertIn("pesan", result["selection"]["reason"])
        self.assertEqual(result["selection"]["candidate_count"], 2)
        self.assertEqual(result["selection"]["reference"]["name"], "Reflektif / Action")
        self.assertEqual(len(result["selection"]["reference"]["profiles"]), 2)
        self.assertFalse(result["selection"]["fallback"])
        self.assertIsNone(result["metrics"]["bpm"])
        self.assertEqual(self.selector.ask.call_args_list[0].args[1]["transcript"], self.metadata["transcript"])
        self.assertEqual(result["metrics"]["measurement_scope"], "selected_passage")
        self.assertEqual(result["metrics"]["window_seconds"], 4)
        self.assertEqual(result["metrics"]["analyzed_seconds"], 12)

    def test_repliz_audio_urls_are_used_without_sending_jamendo_request(self):
        result = self.run_selection(ids=["7550444803676866577"], settings={"catalog": "repliz", "reference_style": "adaptive"},
            rankings={"rankings": [{"candidate_id": "7550444803676866577:0", "score": 80, "reason": "Cocok"}], "review_required": False})
        self.api.get_repliz_tiktok_music.assert_called_once_with("ALL", "ID", "7DAY")
        self.api.get_jamendo_tracks.assert_not_called()
        self.assertEqual(result["audiodownload"], "https://test/reference")
        self.assertIsNone(result["selection"]["reference"])
        self.assertEqual(result["selection"]["catalog_query"], {"genre": "ALL", "country_code": "ID", "date_range": "7DAY"})
        self.assertEqual(self.selector.ask.call_args_list[-1].args[1]["catalog_query"], result["selection"]["catalog_query"])

    def test_all_ai_stages_allow_vocal_songs_and_ranking_does_not_reward_low_gain(self):
        self.run_selection()
        for call in self.selector.ask.call_args_list:
            self.assertIn("bervokal", call.args[0])
        self.assertIn("RMS lebih rendah", self.selector.ask.call_args_list[-1].args[0])

    def test_hallucinated_or_duplicate_ids_do_not_trigger_downloads(self):
        result = self.run_selection(ids=["invented", "better", "better"])
        self.assertEqual(result["selection"]["candidate_count"], 1)
        self.assertEqual(result["id"], "better")
        with self.assertRaisesRegex(ValueError, "kandidat musik yang valid"):
            self.run_selection(ids=["invented"])

    def test_failed_candidate_is_skipped_and_all_failures_stop_selection(self):
        result = self.run_selection(measurement=Mock(side_effect=[ValueError("silent"), profile([.2] * 12)]))
        self.assertEqual(result["id"], "better")
        self.assertEqual(result["selection"]["failed_candidates"], [{"id": "first", "reason": "ValueError"}])
        with self.assertRaisesRegex(ValueError, "Semua kandidat"):
            self.run_selection(measurement=Mock(side_effect=ValueError("silent")))

    def test_invalid_rankings_use_an_explicit_measured_fallback(self):
        result = self.run_selection(rankings={"rankings": [{"candidate_id": "invented", "score": 100}, {"candidate_id": "first:0", "score": float("nan")}]})
        self.assertTrue(result["selection"]["fallback"])
        self.assertIn(result["id"], {"first", "better"})
        json.dumps(result, allow_nan=False)

    def test_ranking_only_failed_candidates_falls_back_to_playable_audio(self):
        result = self.run_selection(rankings={"rankings": [{"candidate_id": "first:0", "score": 100}]},
            measurement=Mock(side_effect=[ValueError("silent"), profile([.2] * 12)]))
        self.assertEqual(result["id"], "better")
        self.assertTrue(result["selection"]["fallback"])
        self.assertTrue(result["selection"]["review_required"])

    def test_semantic_observations_and_passages_reach_editor_and_bad_fit_requires_review(self):
        result = self.run_selection(rankings={"review_required": True, "rankings": [
            {"candidate_id": "better:1", "score": 40, "reason": "Vokal berisiko bersaing"}]})
        self.assertTrue(result["selection"]["review_required"])
        self.assertEqual(result["start"], 3)
        candidates = self.selector.ask.call_args_list[-1].args[1]["candidates"]
        self.assertEqual(len(candidates), 6)
        self.assertIn("observations", candidates[0]["semantic"])
        self.assertEqual(result["selection"]["semantic"]["provenance"]["requested_model"], "Visual-AI")

    def test_audio_analyzer_failure_is_not_replaced_with_title_only_selection(self):
        self.selector.audio_analyzer.analyze.side_effect = ValueError("no media support")
        with self.assertRaisesRegex(ValueError, "Semua kandidat"):
            self.run_selection()
        self.assertEqual(self.selector.ask.call_count, 2)

    def test_failed_audio_route_exposes_safe_actionable_model_diagnostic(self):
        cause = ValueError("private remote body")
        cause.status_code = 400
        cause.body = {"error": "Unsupported model mimo-auto"}
        error = ValueError("audio failed")
        error.__cause__ = cause
        self.selector.audio_analyzer.analyze.side_effect = error
        with self.assertRaisesRegex(ValueError, "Unsupported model mimo-auto"):
            self.run_selection()
        self.assertEqual(self.selector.ask.call_count, 2)

    def test_trend_cache_is_shared_and_offline_snapshot_is_explicit(self):
        first = trend_catalog(self.api, self.root)
        second = trend_catalog(self.api, self.root)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.api.get_repliz_tiktok_music.assert_called_once()
        self.api.get_repliz_tiktok_music.return_value = {"status": "error", "message": "offline"}
        import time
        with patch("services.music_selection.time.time", return_value=time.time() + 700):
            third = trend_catalog(self.api, self.root)
        self.assertTrue(third["offline_snapshot"])
        with patch("services.music_selection.time.time", return_value=time.time() + 90000):
            fourth = trend_catalog(self.api, self.root)
        self.assertEqual(fourth["status"], "error")

    def test_corrupt_cached_analysis_is_recomputed(self):
        for corruption in ({"brightness_hz": [500]}, {"rms": ["broken"] * 12},
                           {"bass_ratio": [float("nan")] * 12}, {"analyzed_seconds": None}, {"method": None}):
            with self.subTest(corruption=corruption):
                cached = {**profile([.1] * 12), **corruption}
                self.track.with_suffix(".analysis.json").write_text(json.dumps(cached), encoding="utf-8")
                measurement = Mock(return_value=profile([.1] * 12))
                with patch("services.music_selection.file_sha256", return_value="fixture"):
                    result = self.run_selection(ids=["better"], measurement=measurement)
                measurement.assert_called_once()
                self.assertEqual(result["id"], "better")
                json.dumps(result, allow_nan=False)

    def test_direction_and_campaign_context_reach_ai_without_mutating_campaign(self):
        settings = {"catalog": "jamendo", "style_brief": "Tenang dan reflektif", "volume": .21}
        before = copy.deepcopy(settings)
        result = self.run_selection(settings=settings)
        context = self.selector.ask.call_args_list[0].args[1]
        self.assertEqual(context["music_direction"], settings["style_brief"])
        self.assertEqual(context["campaign"]["name"], "Self-growth")
        self.assertEqual(settings, before)
        self.assertEqual(result["volume"], .21)

    def test_custom_model_reasoning_and_returned_model_are_recorded(self):
        cfg = {"ai_providers": {"highlight_finder": {"api_key": "fixture", "base_url": "https://test/v1",
            "model": "Codex-6.1sol", "reasoning_effort": "xhigh"},
            "custom_provider": {"api_key": "fixture", "base_url": "https://test/v1"}}}
        with patch("openai.OpenAI") as client:
            client.return_value.chat.completions.create.return_value = SimpleNamespace(
                model="gpt-6.1-sol", id="response-fixture",
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ids":["known"]}'))])
            selector = MusicSelector(self.api, cfg, self.root)
            self.assertEqual(selector.ask("Pilih kandidat", {}), {"ids": ["known"]})
            request = client.return_value.chat.completions.create.call_args.kwargs
            self.assertEqual(request["model"], "Codex-6.1sol")
            self.assertEqual(request["reasoning_effort"], "xhigh")
            self.assertNotIn("temperature", request)
            self.assertEqual(selector.ai_calls[0]["returned_model"], "gpt-6.1-sol")
            self.assertNotIn("api_key", selector.ai_calls[0])

    def test_criteria_cache_keeps_original_model_provenance_without_another_request(self):
        cfg = {"ai_providers": {"highlight_finder": {"api_key": "fixture", "model": "Codex-6.1sol"},
                                "custom_provider": {"api_key": "fixture"}}}
        with patch("openai.OpenAI") as client:
            create = client.return_value.chat.completions.create
            create.return_value = SimpleNamespace(model="gpt-6.1-sol", id="response", choices=[
                SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.criteria)))])
            selector = MusicSelector(self.api, cfg, self.root)
            selector.ask("Criteria", {"title": "Same clip"})
            selector.ask("Criteria", {"title": "Same clip"})
            self.assertEqual(create.call_count, 1)
            self.assertTrue(selector.ai_calls[-1]["cache_hit"])
            self.assertEqual(selector.ai_calls[-1]["returned_model"], "gpt-6.1-sol")
            selector.ask("Changed direction", {"title": "Same clip"})
            self.assertEqual(create.call_count, 2)

    def test_campaign_rejects_unknown_catalog_and_oversized_direction(self):
        for music in ({"catalog": "unknown"}, {"reference_style": "unknown"}, {"style_brief": "x" * 1001}, {"style_brief": []}):
            with self.subTest(music=music), self.assertRaises(ValueError):
                normalize_campaign({"editing": {"music": music}})

    def test_workflow_carries_evidence_and_retains_campaign_mix(self):
        selected = self.run_selection()
        api = SimpleNamespace(_select_background_sound=Mock(return_value={**selected, "volume": 0}))
        campaign = {"editing": {"music": {"volume": .22, "catalog": "jamendo"}}}
        with patch("requests.get") as get:
            result = WorkflowMixin._select_workflow_music(api, self.metadata, {"campaign": campaign}, self.root)
        get.assert_not_called()
        self.assertEqual(result["selection"], selected["selection"])
        self.assertEqual(result["volume"], .22)
        self.assertEqual(api._select_background_sound.call_args.args[-1], campaign)

    @patch("app.requests.get")
    def test_live_repliz_contract_uses_migrated_addon_endpoint(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"docs": [{"id": "7550444803676866577", "name": "NOW OR NEVER", "url": "https://test/audio"}]}
        api = SimpleNamespace(_get_cfg=lambda: {"repliz": {"access_key": "test", "secret_key": "test"}})
        result = WebAPI.get_repliz_tiktok_music(api)
        self.assertEqual(get.call_args.args[0], "https://api.repliz.com/public/addon/tiktok/music")
        self.assertEqual(result["tracks"][0]["id"], "7550444803676866577")

    def test_empty_or_interrupted_download_never_becomes_cached_audio(self):
        for chunks in ([], [b"partial", None]):
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=None)
            response.iter_content.return_value = iter(chunks)
            with patch("requests.get", return_value=response):
                with self.assertRaises((ValueError, TypeError)):
                    download_track("https://test/audio", self.root / "cache")
            self.assertEqual(list((self.root / "cache").iterdir()), [])

    def test_window_skips_silent_intro_and_fits_different_story_arcs(self):
        p = profile([0, 0, 0, .03, .07, .1, .15, .2, .22, .2, .1, .05])
        build = choose_window(p, 5, {"energy": "high", "arc": "build", "climax_seconds": 4})
        release = choose_window(p, 5, {"energy": "high", "arc": "release"})
        self.assertGreaterEqual(build["start"], 3)
        self.assertGreater(build["metrics"]["energy_change"], release["metrics"]["energy_change"])
        self.assertFalse(build["loop_needed"])
        self.assertTrue(choose_window(profile([.1] * 12), 30, {})["loop_needed"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RealMusicEvidenceTests(unittest.TestCase):
    def test_real_decoded_audio_has_signal_evidence_and_silence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, source in (("bass", "sine=frequency=100:duration=6"), ("bright", "sine=frequency=1800:duration=6"), ("silent", "anullsrc=r=8000:cl=mono")):
                path = Path(directory) / (name + ".wav")
                subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", source, "-t", "6", str(path)], check=True, capture_output=True, timeout=15)
            bass = measure_track(Path(directory) / "bass.wav")
            bright = measure_track(Path(directory) / "bright.wav")
            self.assertGreater(bass["bass_ratio"][0], .99)
            self.assertLess(bright["bass_ratio"][0], .01)
            self.assertAlmostEqual(bright["brightness_hz"][0], 1800, delta=5)
            self.assertEqual(bass["analyzed_seconds"], 6)
            with self.assertRaisesRegex(ValueError, "senyap"):
                measure_track(Path(directory) / "silent.wav")


if __name__ == "__main__":
    unittest.main()
