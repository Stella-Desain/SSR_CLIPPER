"""Audience selection is campaign-owned and grounded in source transcript cues."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services.highlight_profiles import (GATES, SCORE_WEIGHTS, HIGHLIGHT_PROFILE_VERSION,
    normalize_highlight_profile, profile_fingerprint, build_highlight_prompt, build_verification_prompt,
    evaluate_selection, selection_range_matches)
from services.editing import EditingValidationError
from services.speech_boundaries import timestamp

TRANSCRIPT = ("[00:00:00,000 - 00:00:10,000] Kenapa tabungan penting?\n"
              "[00:00:10,000 - 00:00:20,000] Karena dana darurat membantu saat pekerjaan hilang.\n"
              "[00:00:20,000 - 00:00:30,000] Jadi sisihkan penghasilan secara rutin.\n"
              "[00:00:30,000 - 00:00:40,000] Tapi jangan abaikan kebutuhan pokok keluarga.\n"
              "[00:00:45,000 - 00:00:55,000] Bagaimana menjaga keluarga?\n"
              "[00:00:55,000 - 00:01:05,000] Dengarkan anak dan sediakan waktu bersama.\n"
              "[00:01:05,000 - 00:01:15,000] Jadi jadwalkan percakapan setiap hari.")
PROFILE = normalize_highlight_profile({"audience": "Pekerja yang ingin menabung", "topics": ["dana darurat"],
    "preferred_angles": ["langkah praktis"], "avoid": ["tips yang mengabaikan kebutuhan pokok"],
    "required_context": ["alasan dan langkah nyata"]})


def candidate(start=0, end=30, score=80, viral=8, title="Tabungan penting", profile=None):
    profile = profile or PROFILE
    if start == 0:
        quotes = [(0, 10, "Kenapa tabungan penting?"), (10, 20, "Karena dana darurat membantu saat pekerjaan hilang."),
                  (20, 30, "Jadi sisihkan penghasilan secara rutin.")]
    else:
        quotes = [(45, 55, "Bagaimana menjaga keluarga?"), (55, 65, "Dengarkan anak dan sediakan waktu bersama."),
                  (65, 75, "Jadi jadwalkan percakapan setiap hari.")]
    return {"start_time": timestamp(start), "end_time": timestamp(end), "title": title,
        "virality_score": viral, "description": "Caption setia pada isi", "hook_text": quotes[0][2],
        "selection": {"version": HIGHLIGHT_PROFILE_VERSION, "profile_hash": profile_fingerprint(profile),
            "scores": {name: score for name in SCORE_WEIGHTS}, "gates": {name: True for name in GATES},
            "reason": "Menjelaskan alasan dan tindakan sesuai kebutuhan audiens", "matched_patterns": ["langkah praktis"],
            "evidence": [{"part": part, "start_time": timestamp(a), "end_time": timestamp(b), "quote": quote}
                         for part, (a, b, quote) in zip(("opening", "message", "ending"), quotes)]}}


def provider(values):
    responses = [SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(value)))]) for value in values]
    create = Mock(side_effect=responses)
    return SimpleNamespace(base_url="https://example.invalid", chat=SimpleNamespace(completions=SimpleNamespace(create=create))), create


class HighlightProfileTests(unittest.TestCase):
    def test_legacy_defaults_use_campaign_requirements_without_creator_stereotypes(self):
        p = normalize_highlight_profile(campaign={"audience_scope": "Orang tua", "brief": {"tujuan": "Komunikasi keluarga", "angles": ["contoh nyata"]},
            "dont_rules": ["menyalahkan anak"], "do_rules": ["sertakan solusi"]})
        self.assertEqual(p["audience"], "Orang tua")
        self.assertEqual(p["topics"], [])
        self.assertEqual(p["preferred_angles"], ["contoh nyata"])
        self.assertEqual(p["avoid"], ["menyalahkan anak"])
        self.assertEqual(p["required_context"], ["sertakan solusi"])
        self.assertEqual(profile_fingerprint(p), profile_fingerprint(copy.deepcopy(p)))
        self.assertNotEqual(profile_fingerprint(p), profile_fingerprint({**p, "audience": "Pekerja"}))
        inherited = normalize_highlight_profile({"audience": "", "objective": ""},
            {"audience_scope": "Orang tua", "brief": {"tujuan": "Komunikasi keluarga"}})
        self.assertEqual(inherited["audience"], "Orang tua")
        self.assertEqual(inherited["objective"], "Komunikasi keluarga")

    def test_weights_and_threshold_must_be_finite_numbers(self):
        for value in (True, "60", float("nan"), float("inf"), -1, 101):
            with self.subTest(value=value), self.assertRaises(EditingValidationError):
                normalize_highlight_profile({"min_score": value})
        with self.assertRaises(EditingValidationError):
            normalize_highlight_profile({"weights": {name: 0 for name in SCORE_WEIGHTS}})

    def test_valid_selection_returns_snapshot_scores_and_cue_evidence(self):
        result = evaluate_selection(candidate(), PROFILE, TRANSCRIPT, 75)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["selection"]["weighted_score"], 80)
        self.assertEqual(result["selection"]["profile"], PROFILE)
        self.assertEqual(result["selection"]["evidence_scope"], "transcript_cues")
        self.assertTrue(selection_range_matches({**candidate(), "selection": result["selection"]}))

    def test_hard_gates_override_high_score_and_boolean_strings_reject(self):
        for name in GATES:
            for value in (False, "true", 1):
                item = candidate(score=100)
                item["selection"]["gates"][name] = value
                with self.subTest(gate=name, value=value):
                    self.assertFalse(evaluate_selection(item, PROFILE, TRANSCRIPT)["accepted"])
        item = candidate(score=100)
        item["selection"]["scores"]["audience_fit"] = True
        self.assertFalse(evaluate_selection(item, PROFILE, TRANSCRIPT)["accepted"])
        item["selection"]["scores"]["audience_fit"] = float("nan")
        self.assertFalse(evaluate_selection(item, PROFILE, TRANSCRIPT)["accepted"])

    def test_unrelated_profile_missing_assessment_low_score_and_forged_quotes_reject(self):
        altered = candidate()
        altered["selection"]["profile_hash"] = profile_fingerprint({"audience": "Orang tua"})
        self.assertFalse(evaluate_selection(altered, PROFILE, TRANSCRIPT)["accepted"])
        self.assertFalse(evaluate_selection({"start_time": timestamp(0), "end_time": timestamp(30)}, PROFILE, TRANSCRIPT)["accepted"])
        self.assertFalse(evaluate_selection(candidate(score=59), PROFILE, TRANSCRIPT)["accepted"])
        altered = candidate()
        altered["selection"]["evidence"][1]["quote"] = "Jual rumah untuk judi."
        self.assertFalse(evaluate_selection(altered, PROFILE, TRANSCRIPT)["accepted"])
        altered = candidate()
        altered["selection"]["evidence"][1]["start_time"] = timestamp(45)
        altered["selection"]["evidence"][1]["end_time"] = timestamp(55)
        self.assertFalse(evaluate_selection(altered, PROFILE, TRANSCRIPT)["accepted"])

    def test_early_quote_cannot_prove_later_ending_and_changed_range_is_stale(self):
        altered = candidate()
        altered["selection"]["evidence"][2] = {**altered["selection"]["evidence"][0], "part": "ending"}
        result = evaluate_selection(altered, PROFILE, TRANSCRIPT)
        self.assertFalse(result["accepted"])
        self.assertTrue(any("akhir" in reason for reason in result["reasons"]))
        assessed = evaluate_selection(candidate(), PROFILE, TRANSCRIPT)["selection"]
        self.assertFalse(selection_range_matches({**candidate(), "end_time": timestamp(40), "selection": assessed}))
        self.assertFalse(evaluate_selection({**candidate(), "end_time": timestamp(40), "selection": assessed}, PROFILE, TRANSCRIPT)["accepted"])

    def test_visual_description_is_not_treated_as_spoken_transcript(self):
        result = evaluate_selection(candidate(), PROFILE, "[00:00:00] Seseorang berbicara.")
        self.assertFalse(result["accepted"])
        self.assertTrue(any("deskripsi visual" in reason for reason in result["reasons"]))

    def test_prompt_and_verifier_are_campaign_specific_and_hide_platform_mentions(self):
        campaign = {"name": "Keluarga", "brief": {"tagged_accounts_by_platform": {"tiktok": ["@privatebrand"]}}}
        prompt = build_highlight_prompt(PROFILE, campaign)
        self.assertIn("Pekerja yang ingin menabung", prompt)
        self.assertNotIn("@privatebrand", prompt)
        self.assertNotIn("ARRAY KOSONG DILARANG", prompt)
        self.assertNotIn("TIER A", prompt)
        self.assertIn("matched_patterns", prompt)
        verification = build_verification_prompt(candidate(), PROFILE, TRANSCRIPT, campaign)
        self.assertNotIn("{num_clips}", verification)
        self.assertNotIn("ARRAY JSON", verification)
        self.assertNotIn("@privatebrand", verification)
        self.assertIn("OBJECT JSON", verification)

    def test_provider_generation_ranks_audience_score_instead_of_viral_and_filters_gates(self):
        from clipper_core import AutoClipperCore
        off_topic = candidate(end=40, score=100, title="Di luar audiens")
        off_topic["selection"]["gates"]["audience_match"] = False
        lower = candidate(score=70, viral=10, title="Viral kurang cocok")
        better = candidate(45, 75, score=95, viral=2, title="Lebih cocok")
        client, create = provider([[lower, off_topic, better]])
        with tempfile.TemporaryDirectory() as folder:
            core = AutoClipperCore(client=None, output_dir=folder, log_callback=lambda *_: None)
            core.campaign_config = {"name": "Tabungan", "highlight_profile": PROFILE}
            core.highlight_client = client
            original = core.system_prompt
            result = core._find_campaign_highlights(TRANSCRIPT, {"duration": 75}, 30, 1, 9, 25, 40)
            self.assertEqual([item["title"] for item in result], ["Lebih cocok", "Viral kurang cocok"])
            self.assertTrue(core._profile_candidates_required)
            self.assertEqual(core.system_prompt, original)
            rejections = json.loads((Path(folder)/"highlight_rejections.json").read_text(encoding="utf-8"))
            self.assertEqual(rejections["candidates"][0]["stage"], "profile")
            self.assertEqual(rejections["candidates"][0]["title"], "Di luar audiens")
        request = create.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("TIER A", request)
        self.assertIn(profile_fingerprint(PROFILE), request)

    def test_real_provider_missing_selection_cannot_use_legacy_compatibility(self):
        from clipper_core import AutoClipperCore
        item = candidate()
        item.pop("selection")
        client, _ = provider([[item]])
        with tempfile.TemporaryDirectory() as folder:
            core = AutoClipperCore(client=None, output_dir=folder, log_callback=lambda *_: None)
            core.campaign_config = {}  # Old campaign snapshots are strict too.
            core.highlight_client = client
            self.assertEqual(core._find_campaign_highlights(TRANSCRIPT, {"duration": 75}, 30, 1, 6, 25, 40), [])
            self.assertTrue(core._highlight_profile_rejections)

    def test_range_repair_reverifies_extended_content_and_rejected_candidate_does_not_consume_count(self):
        from clipper_core import AutoClipperCore
        client, create = provider([[candidate(), candidate(45, 75, title="Pilihan valid", score=75)]])
        revised = candidate(end=40)["selection"]
        revised["gates"]["brief_compliant"] = False
        client.chat.completions.create.side_effect = [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps([candidate(), candidate(45, 75, title="Pilihan valid", score=75)])))]),
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(revised)))])]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/"source.mp4"; source.write_bytes(b"offline fixture")
            source.with_suffix(".srt").write_text("1\n00:00:00,000 --> 00:00:30,000\nKenapa tabungan penting?\n", encoding="utf-8")
            core = AutoClipperCore(client=None, output_dir=root/"output", log_callback=lambda *_: None)
            core.campaign_config = {"highlight_profile": PROFILE}
            core.highlight_client = client
            core.parse_srt = Mock(return_value=TRANSCRIPT)
            observed = []
            core.process_clip = lambda _path, item, *_: observed.append(copy.deepcopy(item))
            def align(item, *_):
                item = copy.deepcopy(item)
                if item["title"] == "Tabungan penting":
                    item["end_time"] = timestamp(40)
                return item
            media = {"has_video": True, "has_audio": True, "duration": 75}
            with patch("services.core_workflow.probe_media", return_value=media), patch("services.core_workflow.SpeechBoundaryAligner") as aligner:
                aligner.return_value.align.side_effect = align
                core.process(str(source), fixed_count=1, dur_min=25, dur_max=40)
            self.assertEqual([item["title"] for item in observed], ["Pilihan valid"])
            self.assertEqual(create.call_count, 2)
            job = next((root/"output").glob("job-*"))
            metadata = json.loads((job/"data.json").read_text(encoding="utf-8"))
            plan = json.loads((job/"highlights.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["profile_hash"], profile_fingerprint(PROFILE))
            self.assertEqual(plan["highlights"][0]["selection"]["weighted_score"], 75)
            self.assertEqual(metadata["profile_rejections"][0]["title"], "Tabungan penting")
            self.assertTrue(any("brief" in reason for reason in metadata["profile_rejections"][0]["reasons"]))

    def test_final_reassessment_score_determines_quota_after_all_candidates_checked(self):
        from clipper_core import AutoClipperCore
        repaired = candidate(end=40, score=65)["selection"]
        repaired["evidence"][-1] = {"part": "ending", "start_time": timestamp(30), "end_time": timestamp(40),
            "quote": "Tapi jangan abaikan kebutuhan pokok keluarga."}
        client, create = provider([[candidate(score=95), candidate(45, 75, score=85, title="Lebih cocok setelah verifikasi")], repaired])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mp4"
            source.write_bytes(b"offline fixture")
            source.with_suffix(".srt").write_text("fixture", encoding="utf-8")
            core = AutoClipperCore(client=None, output_dir=root/"output", log_callback=lambda *_: None)
            core.campaign_config = {"highlight_profile": PROFILE}
            core.highlight_client = client
            core.parse_srt = Mock(return_value=TRANSCRIPT)
            observed = []
            core.process_clip = lambda _path, item, *_: observed.append(copy.deepcopy(item))
            def align(item, *_):
                item = copy.deepcopy(item)
                if item["title"] == "Tabungan penting":
                    item["end_time"] = timestamp(40)
                return item
            with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": True, "duration": 75}), \
                    patch("services.core_workflow.SpeechBoundaryAligner") as aligner:
                aligner.return_value.align.side_effect = align
                core.process(str(source), fixed_count=1, dur_min=25, dur_max=40)
            self.assertEqual([item["title"] for item in observed], ["Lebih cocok setelah verifikasi"])
            self.assertEqual(create.call_count, 2)

    def test_resumed_provider_plan_cannot_render_after_its_assessment_is_lost(self):
        from clipper_core import AutoClipperCore
        client, create = provider([[candidate()]])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mp4"
            source.write_bytes(b"offline fixture")
            source.with_suffix(".srt").write_text("fixture", encoding="utf-8")
            core = AutoClipperCore(client=None, output_dir=root/"output", log_callback=lambda *_: None)
            core.campaign_config = {"highlight_profile": PROFILE}
            core.resume_dir = root / "job"
            core.highlight_client = client
            core.parse_srt = Mock(return_value=TRANSCRIPT)
            core.process_clip = Mock()
            with patch("services.core_workflow.probe_media", return_value={"has_video": True, "has_audio": True, "duration": 75}), \
                    patch("services.core_workflow.SpeechBoundaryAligner") as aligner:
                aligner.return_value.align.side_effect = lambda item, *_: copy.deepcopy(item)
                core.process(str(source), fixed_count=1, dur_min=25, dur_max=40)
                plan_file = root / "job" / "highlights.json"
                plan = json.loads(plan_file.read_text(encoding="utf-8"))
                self.assertTrue(plan["profile_assessment_required"])
                plan["highlights"][0].pop("selection")
                plan_file.write_text(json.dumps(plan), encoding="utf-8")
                core.process_clip.reset_mock()
                with self.assertRaisesRegex(EditingValidationError, "profil audiens"):
                    core.process(str(source), fixed_count=1, dur_min=25, dur_max=40)
            core.process_clip.assert_not_called()
            self.assertEqual(create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
