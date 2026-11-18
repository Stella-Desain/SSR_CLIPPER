"""Speech endings must follow evidence, not AI timestamps or duration caps."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from services.speech_boundaries import SpeechBoundaryAligner, SpeechBoundaryError, detect_pauses, seconds


def highlight(end=6, start=0):
    return {"start_time": start, "end_time": end, "title": "Cerita"}


class SpeechBoundaryTests(unittest.TestCase):
    def test_finishes_sentence_using_observed_cue_end_not_padding(self):
        aligner = SpeechBoundaryAligner("[00:00:00 - 00:00:04] Saat kita jatuh\n[00:00:04 - 00:00:08] kita bisa bangkit lagi.", 12)
        source = highlight()
        before = copy.deepcopy(source)
        result = aligner.align(source, 2, 10)
        self.assertEqual(seconds(result["end_time"]), 8)
        self.assertEqual(result["speech_boundary"]["requested_end_seconds"], 6)
        self.assertEqual(result["speech_boundary"]["method"], "sentence_timestamp")
        self.assertEqual(source, before)
        self.assertEqual(aligner.align(result, 2, 10), result)

    def test_strict_duration_chooses_previous_complete_ending(self):
        aligner = SpeechBoundaryAligner("[00:00:00 - 00:00:04] Satu cerita selesai.\n[00:00:04 - 00:00:08] Cerita lain selesai.", 12)
        result = aligner.align(highlight(), 2, 7)
        self.assertEqual(seconds(result["end_time"]), 4)
        self.assertNotEqual(seconds(result["end_time"]), 7)

    def test_rejects_if_no_complete_ending_fits_minimum_and_maximum(self):
        aligner = SpeechBoundaryAligner("[00:00:00 - 00:00:04] Selesai.\n[00:00:04 - 00:00:08] Selesai lagi.", 12)
        with self.assertRaises(SpeechBoundaryError):
            aligner.align(highlight(), 5, 7)

    def test_does_not_assume_internal_punctuation_has_word_timing(self):
        aligner = SpeechBoundaryAligner("[00:00:00 - 00:00:08] Selesai. Tetapi sesudah itu", 12)
        with self.assertRaises(SpeechBoundaryError):
            aligner.align(highlight(), 2, 10)

    def test_rolling_captions_need_real_pause_and_keep_uncertainty(self):
        text = "[00:00:00 - 00:00:10] Semuanya sudah selesai.\n[00:00:08 - 00:00:12] Pembicaraan berikutnya"
        aligner = SpeechBoundaryAligner(text, 15, path="source.mp4")
        with patch("services.speech_boundaries.detect_pauses", return_value=[(7.8, 8.2)]) as detector:
            result = aligner.align(highlight(), 2, 11)
            aligner.align(highlight(), 2, 11)
        self.assertEqual(detector.call_count, 1)
        self.assertEqual(seconds(result["end_time"]), 8)
        self.assertNotEqual(seconds(result["end_time"]), 10)
        self.assertEqual(result["speech_boundary"]["method"], "rolling_sentence_pause")
        self.assertEqual(result["speech_boundary"]["confidence"], "medium")
        self.assertTrue(result["speech_boundary"]["warnings"])

    def test_rolling_display_end_is_not_fallback_when_audio_fails(self):
        text = "[00:00:00 - 00:00:10] Selesai.\n[00:00:08 - 00:00:12] Tetapi masih berbicara"
        for pauses in (None, []):
            with patch("services.speech_boundaries.detect_pauses", return_value=pauses):
                with self.assertRaises(SpeechBoundaryError):
                    SpeechBoundaryAligner(text, 15, path="source.mp4").align(highlight(), 2, 11)

    def test_user_bangkit_case_ends_after_sentence_and_before_next_speech(self):
        # The real source uses overlapping YouTube captions; these are its
        # relevant cue times. Audio measurement gives a gap at 224.534–224.889.
        text = "\n".join([
            "[00:03:37,920 - 00:03:42,000] punya dihancurin. Uang yang lu punya",
            "[00:03:39,400 - 00:03:44,360] diambil. Ya, jabatan yang lu punya",
            "[00:03:42,000 - 00:03:46,400] dicopot. Semua mungkin pernah diambil.",
            "[00:03:44,360 - 00:03:48,560] Tapi lu harus punya ya keberanian di",
        ])
        with patch("services.speech_boundaries.detect_pauses", return_value=[(222.495, 222.923), (224.534, 224.889)]):
            result = SpeechBoundaryAligner(text, 1366.457, path="source.mp4").align(highlight(222, 193.799), 28, 55)
        self.assertEqual(result["end_time"], "00:03:44,712")
        self.assertAlmostEqual(result["duration_seconds"], 30.913)

    def test_unpunctuated_transcript_pause_is_exposed_for_review(self):
        text = "[00:00:00 - 00:00:05] pesan pertama\n[00:00:06 - 00:00:09] pesan berikutnya"
        result = SpeechBoundaryAligner(text, 10).align(highlight(4), 1, 8)
        self.assertEqual(seconds(result["end_time"]), 5)
        self.assertEqual(result["speech_boundary"]["method"], "transcript_pause")
        self.assertTrue(result["speech_boundary"]["warnings"])

    def test_visual_fallback_is_not_mistaken_for_speech_timestamps(self):
        result = SpeechBoundaryAligner("[00:00:00] A scenic view", 10).align(highlight(), 1, 8)
        self.assertEqual(result["speech_boundary"]["method"], "unverified")
        self.assertTrue(result["speech_boundary"]["warnings"])
        silent = SpeechBoundaryAligner("", 10, has_audio=False).align(highlight(), 1, 8)
        self.assertEqual(silent["speech_boundary"]["method"], "no_speech")
        self.assertFalse(silent["speech_boundary"]["warnings"])

    def test_eof_incomplete_speech_and_out_of_bounds_are_not_padded(self):
        aligner = SpeechBoundaryAligner("[00:00:00 - 00:00:07] tetapi belum selesai", 7)
        for ending in (6, 7, 7.3, float("nan")):
            with self.assertRaises(SpeechBoundaryError):
                aligner.align(highlight(ending), 1, 10)

    def test_long_sentence_uses_available_budget_beyond_twelve_seconds(self):
        aligner = SpeechBoundaryAligner("[00:00:00 - 00:00:30] Cerita panjang sekali.", 40)
        result = aligner.align(highlight(), 1, 35)
        self.assertEqual(seconds(result["end_time"]), 30)

    def test_unrelated_story_after_large_gap_is_not_pulled_into_highlight(self):
        text = "[00:00:00 - 00:00:08] kalimat tidak selesai\n[00:00:20 - 00:00:30] Cerita lain selesai."
        with self.assertRaises(SpeechBoundaryError):
            SpeechBoundaryAligner(text, 40).align(highlight(), 10, 35)

    def test_requested_end_in_silence_keeps_previous_story_instead_of_next_one(self):
        text = "[00:00:00 - 00:00:04] Cerita selesai.\n[00:00:20 - 00:00:30] Cerita lain selesai."
        result = SpeechBoundaryAligner(text, 40).align(highlight(), 1, 35)
        self.assertEqual(seconds(result["end_time"]), 4)

    def test_real_thirty_second_question_waits_for_answer_within_seventy_seconds(self):
        text = "\n".join([
            "[00:04:23,960 - 00:04:27,680] penghasilannya Rp10 juta. Tapi gua akan",
            "[00:04:26,360 - 00:04:30,080] lebih pilih, gua lebih tertarik sama",
            "[00:04:27,680 - 00:04:31,479] anak yang kedua yang Rp10 juta. Kenapa?",
            "[00:04:30,080 - 00:04:33,080] Karena kita di dalam hidup kita harus",
            "[00:04:31,479 - 00:04:34,880] ngelihat namanya slope-nya hidup,",
            "[00:04:58,520 - 00:05:03,919] grafiknya dia akan naik ke atas seperti",
            "[00:04:59,840 - 00:05:05,479] ini. Ya, jadi itu rahasianya dari hidup.",
            "[00:05:03,919 - 00:05:07,000] Jangan cuman lihat apa yang kelihatan di",
        ])
        # Fill the middle with continuous non-terminal cues: the answer keeps
        # going, so neither a punctuation mark nor a short pause closes it.
        text = text.replace("[00:04:58,520", "\n".join(
            f"[00:04:{s:02d},000 - 00:04:{s+4:02d},000] penjelasan jawaban berlanjut"
            for s in range(33, 56, 2)) + "\n[00:04:58,520")
        with patch("services.speech_boundaries.detect_pauses", return_value=[(269.6, 269.938), (303.43, 303.798)]):
            result = SpeechBoundaryAligner(text, 1900, path="source.mp4").align(highlight(270.08, 240.4), 28, 70)
        self.assertEqual(result["end_time"], "00:05:03,614")
        self.assertAlmostEqual(result["duration_seconds"], 63.214)

    def test_question_followed_by_answer_is_not_accepted_at_campaign_limit(self):
        text = "[00:00:00 - 00:00:30] Kenapa?\n[00:00:30 - 00:00:50] Karena jawabannya perlu dijelaskan sampai selesai."
        with self.assertRaises(SpeechBoundaryError):
            SpeechBoundaryAligner(text, 55).align(highlight(30), 28, 40)

    def test_unresolved_why_question_at_source_end_is_not_a_payoff(self):
        with self.assertRaises(SpeechBoundaryError):
            SpeechBoundaryAligner("[00:00:00 - 00:00:30] Lalu saya memilih dia. Kenapa?", 30).align(highlight(30), 28, 70)

    def test_pause_after_dangling_connector_is_not_a_complete_ending(self):
        text = "[00:00:00 - 00:00:30] Kita harus bangkit karena\n[00:00:31 - 00:00:45] hidup masih berjalan."
        result = SpeechBoundaryAligner(text, 50).align(highlight(30), 28, 50)
        self.assertEqual(seconds(result["end_time"]), 45)

    def test_complete_thirty_second_story_is_not_artificially_lengthened(self):
        text = "[00:00:00 - 00:00:30] Cerita ini sudah lengkap.\n[00:00:30 - 00:01:05] Cerita berikutnya juga sudah lengkap."
        result = SpeechBoundaryAligner(text, 70).align(highlight(30), 28, 70)
        self.assertEqual(seconds(result["end_time"]), 30)

    def test_process_replaces_stale_plan_and_does_not_realign_valid_resume(self):
        from clipper_core import AutoClipperCore
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mp4"
            source.write_bytes(b"isolated fixture")
            source.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:04,000\nKalimat lengkap.\n", encoding="utf8")
            job = root / "job"
            job.mkdir()
            (job / "highlights.json").write_text(json.dumps({"key": "old-pre-boundary-key", "highlights": [highlight(3)]}))
            observed = []
            def core():
                value = AutoClipperCore(client=None, output_dir=root, log_callback=lambda *_: None)
                value.resume_dir = job
                value.highlight_overrides = [{"start_time": "00:00:00", "end_time": "00:00:03", "title": "Cerita"}]
                value.process_clip = lambda video, h, *args: observed.append(h)
                return value
            media = {"has_video": True, "has_audio": True, "duration": 5}
            with patch("services.core_workflow.probe_media", return_value=media):
                core().process(str(source), dur_min=1, dur_max=5)
                with patch.object(SpeechBoundaryAligner, "align", side_effect=AssertionError("valid plan must resume exactly")):
                    core().process(str(source), dur_min=1, dur_max=5)
            self.assertEqual(len(observed), 2)
            self.assertEqual(observed[0], observed[1])
            self.assertEqual(observed[0]["end_time"], "00:00:04,000")
            self.assertEqual(observed[0]["speech_boundary"]["requested_end_seconds"], 3)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_audio_detection_measures_gap_without_using_window_edges(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / "source.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                "sine=frequency=440:duration=3,volume=enable='between(t,1,1.5)':volume=0", str(audio)],
                capture_output=True, check=True, timeout=30)
            pauses = detect_pauses(audio, 0, 3)
            self.assertEqual(len(pauses), 1)
            self.assertAlmostEqual(pauses[0][0], 1, delta=.04)
            self.assertAlmostEqual(pauses[0][1], 1.5, delta=.04)


if __name__ == "__main__":
    unittest.main()
