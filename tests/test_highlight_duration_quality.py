"""Campaign duration is a range; story quality decides its actual length."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from clipper_core import AutoClipperCore


def candidate(start, end, title="Cerita", score=8):
    return {"start_time": f"00:00:{start:02d},000", "end_time": f"00:01:{end-60:02d},000" if end >= 60 else f"00:00:{end:02d},000",
            "title": title, "virality_score": score, "description": title, "hook_text": title}


class HighlightDurationQualityTests(unittest.TestCase):
    def test_ai_receives_story_completion_contract_and_keeps_natural_durations(self):
        values = [candidate(0, 30), candidate(0, 49), candidate(0, 68)]
        create = Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(values)))]))
        client = SimpleNamespace(base_url="https://example.invalid", chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as folder:
            core = AutoClipperCore(client=None, output_dir=folder, log_callback=lambda *_: None)
            core.highlight_client = client
            core.system_prompt = "Temukan {num_clips} clip.\n{transcript}"
            result = core.find_highlights("[00:00:00 - 00:01:08] Cerita lengkap.", {}, max_highlights=12, dur_min=28, dur_max=70)
        self.assertEqual([h["duration_seconds"] for h in result], [30, 49, 68])
        prompt = create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Temukan 12 clip", prompt)
        self.assertIn("antara 28 sampai 70 detik", prompt)
        self.assertIn("BUKAN target durasi", prompt)
        self.assertIn("'Kenapa?' wajib diikuti jawabannya", prompt)
        self.assertNotIn("Target ideal:", prompt)

    def test_quality_filter_does_not_let_rejected_highlight_consume_requested_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mp4"
            source.write_bytes(b"isolated source fixture")
            source.with_suffix(".srt").write_text(
                "1\n00:00:00,000 --> 00:00:40,000\nKalimat belum selesai karena\n\n"
                "2\n00:00:45,000 --> 00:01:15,000\nCerita lengkap lainnya.\n", encoding="utf8")
            core = AutoClipperCore(client=None, output_dir=root, log_callback=lambda *_: None)
            core.find_highlights = Mock(return_value=[candidate(0, 30, "Belum selesai", 9), candidate(45, 75, "Utuh", 8)])
            observed = []
            core.process_clip = lambda _video, value, *_args: observed.append(value)
            media = {"has_video": True, "has_audio": True, "duration": 80}
            with patch("services.core_workflow.probe_media", return_value=media):
                core.process(str(source), fixed_count=1, dur_min=28, dur_max=40)
            self.assertEqual(len(observed), 1)
            self.assertEqual(observed[0]["title"], "Utuh")
            self.assertEqual(observed[0]["duration_seconds"], 30)


if __name__ == "__main__":
    unittest.main()
