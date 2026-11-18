import base64
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services.music_audio import MusicAudioAnalyzer, audio_provider, provider_error_details, validate_observations
from services.music_review import MusicReviewMixin


def observations():
    return {"audio_access": True, "segments": [{"start": 0, "end": 10, "confidence": .9,
        "mood": "reflektif", "texture": "petikan", "instruments": "gitar", "vocals": "lirih",
        "energy": "low", "dialogue_risk": "rendah"}], "phrase_starts": [0, 3], "limitations": ""}


class MusicAudioTests(unittest.TestCase):
    def test_refuses_claims_without_audio_and_bad_timestamps(self):
        for changes in ({"audio_access": False}, {"audio_access": "true"}, {"segments": []},
                        {"phrase_starts": [-1]}, {"phrase_starts": [float("nan")]},
                        {"segments": [{**observations()["segments"][0], "end": 20}]},
                        {"segments": [{**observations()["segments"][0], "confidence": float("nan")}]},
                        {"segments": observations()["segments"] * 2}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, KeyError)):
                validate_observations({**observations(), **changes}, 10)

    def test_custom2_visual_default_and_explicit_provider_override(self):
        cfg = {"ai_providers": {"custom_provider": {"api_key": "fixture", "base_url": "https://test/v1"}}}
        self.assertEqual(audio_provider(cfg)["model"], "Visual-AI")
        cfg["ai_providers"]["music_analyzer"] = {"model": "other", "api_key": "separate"}
        self.assertEqual(audio_provider(cfg)["model"], "other")

    def test_real_audio_payload_and_cache_identity_include_content_range_model_and_version(self):
        with tempfile.TemporaryDirectory() as folder, patch("openai.OpenAI") as client, \
                patch("services.music_audio.probe_media", return_value={"duration": 10}), \
                patch("services.music_audio.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"ID3" + b"mp3" * 200)):
            path = Path(folder) / "song.wav"
            path.write_bytes(b"song-first")
            create = client.return_value.chat.completions.create
            create.return_value = SimpleNamespace(model="actual-gemini", id="response", choices=[
                SimpleNamespace(message=SimpleNamespace(content=json.dumps(observations())))])
            cfg = {"ai_providers": {"custom_provider": {"api_key": "fixture", "base_url": "https://test/v1"}}}
            analyzer = MusicAudioAnalyzer(cfg, folder)
            first = analyzer.analyze(path)
            second = analyzer.analyze(path)
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            create.assert_called_once()
            request = create.call_args.kwargs
            self.assertEqual(request["model"], "Visual-AI")
            self.assertNotIn("song.wav", json.dumps(request["messages"]))
            audio = request["messages"][1]["content"][0]
            self.assertEqual(audio["type"], "input_audio")
            self.assertEqual(audio["input_audio"]["format"], "mp3")
            self.assertTrue(base64.b64decode(audio["input_audio"]["data"]).startswith(b"ID3"))
            self.assertEqual(first["provenance"]["returned_model"], "actual-gemini")
            self.assertNotIn("fixture", json.dumps(first))
            path.write_bytes(b"song-replaced")
            analyzer.analyze(path)
            self.assertEqual(create.call_count, 2)
            create.return_value.choices[0].message.content = json.dumps({**observations(), "segments": [
                {**observations()["segments"][0], "end": 8}]})
            analyzer.analyze(path, start=2, seconds=8)
            self.assertEqual(create.call_count, 3)
            cfg["ai_providers"]["custom_provider"]["base_url"] = "https://changed/v1"
            analyzer = MusicAudioAnalyzer(cfg, folder)
            create.return_value.choices[0].message.content = json.dumps(observations())
            analyzer.analyze(path)
            self.assertEqual(create.call_count, 4)

    def test_missing_audio_capability_does_not_cache_a_fake_profile(self):
        with tempfile.TemporaryDirectory() as folder, patch("openai.OpenAI") as client, \
                patch("services.music_audio.probe_media", return_value={"duration": 10}), \
                patch("services.music_audio.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"x" * 1000)):
            path = Path(folder) / "song.wav"; path.write_bytes(b"source")
            client.return_value.chat.completions.create.return_value = SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(content='{"audio_access":false}'))])
            analyzer = MusicAudioAnalyzer({"ai_providers": {"custom_provider": {"api_key": "fixture"}}}, folder)
            with self.assertRaisesRegex(ValueError, "audio sungguhan"):
                analyzer.analyze(path)
            self.assertEqual(list((Path(folder) / "semantic").glob("*.json")), [])

    def test_forced_provider_test_bypasses_an_existing_valid_profile(self):
        with tempfile.TemporaryDirectory() as folder, patch("openai.OpenAI") as client, \
                patch("services.music_audio.probe_media", return_value={"duration": 10}), \
                patch("services.music_audio.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"x" * 1000)):
            path = Path(folder) / "song.mp3"
            path.write_bytes(b"source")
            create = client.return_value.chat.completions.create
            create.return_value = SimpleNamespace(model="visual", id="first", choices=[
                SimpleNamespace(message=SimpleNamespace(content=json.dumps(observations())))])
            analyzer = MusicAudioAnalyzer({"ai_providers": {"custom_provider": {"api_key": "fixture"}}}, folder)
            analyzer.analyze(path)
            self.assertTrue(analyzer.analyze(path)["cache_hit"])
            create.side_effect = ValueError("provider now offline")
            with self.assertRaisesRegex(ValueError, "audio sungguhan"):
                analyzer.analyze(path, use_cache=False)
            self.assertEqual(create.call_count, 2)
            self.assertTrue(analyzer.analyze(path)["cache_hit"])

    def test_settings_audio_test_always_requests_fresh_media_analysis(self):
        with tempfile.TemporaryDirectory() as folder, patch("services.music_audio.MusicAudioAnalyzer") as analyzer:
            path = Path(folder) / "_cache/music-selection/audio/song.mp3"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"fixture")
            analyzer.return_value.analyze.return_value = {"provenance": {"returned_model": "visual"}}
            api = SimpleNamespace(output_dir=folder)
            result = MusicReviewMixin.test_music_audio_model(api, {"model": "Visual-AI"})
            self.assertEqual(result["status"], "ok")
            analyzer.return_value.analyze.assert_called_once_with(path, seconds=12, use_cache=False)

    def test_provider_diagnostics_only_include_safe_status_and_model_fields(self):
        cause = ValueError("private token must not be copied")
        cause.status_code = 400
        cause.body = {"error": "Unsupported model mimo-auto", "api_key": "private token"}
        wrapped = ValueError("public")
        wrapped.__cause__ = cause
        details = provider_error_details(wrapped)
        self.assertEqual(details, {"type": "ValueError", "http_status": 400,
                                   "unsupported_model": "Unsupported model mimo-auto"})
        self.assertNotIn("private", json.dumps(details))


if __name__ == "__main__":
    unittest.main()
