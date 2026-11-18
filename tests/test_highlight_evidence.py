"""Regression tests for source-backed campaign evidence on rolling subtitles."""
import copy
import unittest

from services.highlight_profiles import (
    GATES, HIGHLIGHT_PROFILE_VERSION, SCORE_WEIGHTS, build_highlight_prompt,
    build_verification_prompt, evaluate_selection,
    normalize_highlight_profile, profile_fingerprint,
)
from services.speech_boundaries import BOUNDARY_VERSION, timestamp


PROFILE = normalize_highlight_profile({"audience": "Penonton yang membutuhkan motivasi"})


def selection(start, end, evidence, *, score=80, boundary=None):
    item = {"start_time": timestamp(start), "end_time": timestamp(end), "title": "Gagasan utuh",
            "selection": {"version": HIGHLIGHT_PROFILE_VERSION, "profile_hash": profile_fingerprint(PROFILE),
                          "scores": {name: score for name in SCORE_WEIGHTS},
                          "gates": {name: True for name in GATES},
                          "reason": "Pembuka dan kesimpulan mendukung pesan yang sesuai audiens",
                          "matched_patterns": [], "evidence": evidence}}
    if boundary:
        item["speech_boundary"] = boundary
    return item


def proof(part, start, end, quote):
    return {"part": part, "start_time": timestamp(start), "end_time": timestamp(end), "quote": quote}


ROLLING_TRANSCRIPT = "\n".join((
    "[00:01:09,240 - 00:01:12,840] gua lakuin sampai hidup gua sampai sini?",
    "[00:01:11,000 - 00:01:15,119] Tapi gua pengen lu dengerin gua di sini",
    "[00:01:12,840 - 00:01:17,080] ya. Kadang hidup itu memang ngancurin lu",
    "[00:01:15,119 - 00:01:18,960] untuk ngajarin lu gimana caranya lu bisa",
    "[00:01:17,080 - 00:01:20,640] jadi manusia atau orang yang lebih baik.",
    "[00:01:20,640 - 00:01:23,480] Lu jangan ketika posisi ini lagi susah.",
))


class HighlightEvidenceTests(unittest.TestCase):
    def rolling_candidate(self):
        return selection(71, 80.64, [
            proof("opening", 71, 77.08,
                  "Tapi gua pengen lu dengerin gua di sini ya. Kadang hidup itu memang ngancurin lu"),
            proof("message", 75.119, 78.96, "untuk ngajarin lu gimana caranya lu bisa"),
            proof("ending", 77.08, 80.64, "jadi manusia atau orang yang lebih baik."),
        ])

    def test_generation_and_verification_show_three_distinct_source_proofs(self):
        for prompt in (build_highlight_prompt(PROFILE),
                       build_verification_prompt(self.rolling_candidate(), PROFILE, ROLLING_TRANSCRIPT)):
            for part in ("opening", "message", "ending"):
                self.assertIn(f'"part": "{part}"', prompt)
            self.assertNotIn('"part": "opening|message|reasoning|ending"', prompt)
            self.assertIn("baris subtitle berurutan", prompt)

    def test_rolling_prior_display_cue_does_not_replace_real_opening(self):
        result = evaluate_selection(self.rolling_candidate(), PROFILE, ROLLING_TRANSCRIPT)
        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["source_evidence_valid"])
        self.assertEqual(result["source_evidence_reasons"], [])
        self.assertTrue(result["selection"]["verified_source"])
        self.assertEqual(result["selection"]["evidence"][0]["cue_ids"], [1, 2])
        self.assertEqual(result["selection"]["evidence"][2]["cue_ids"], [4])

    def test_milliseconde_endpoint_excludes_next_rolling_caption(self):
        transcript = "\n".join((
            "[00:01:40,000 - 00:01:46,000] Pembuka yang sungguh penting.",
            "[00:01:45,000 - 00:01:51,000] Pesan yang perlu diingat.",
            "[00:01:49,439 - 00:01:53,520] Penjelasannya sudah jelas.",
            "[00:01:52,159 - 00:01:55,399] Ini topik berikutnya.",
        ))
        item = selection(100, 112.159, [
            proof("opening", 100, 106, "Pembuka yang sungguh penting."),
            proof("message", 105, 111, "Pesan yang perlu diingat."),
            proof("ending", 109.439, 112.159, "Penjelasannya sudah jelas."),
        ])
        result = evaluate_selection(item, PROFILE, transcript)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["selection"]["evidence"][2]["cue_ids"], [2])

    def test_multicue_ending_uses_its_last_source_cue(self):
        transcript = "\n".join((
            "[00:00:00,000 - 00:00:05,000] Kenapa ini penting?",
            "[00:00:05,000 - 00:00:12,000] Karena pilihan kecil menentukan arah.",
            "[00:00:12,000 - 00:00:17,000] Jadi mulai hari ini",
            "[00:00:17,000 - 00:00:20,000] ambil satu langkah yang nyata.",
        ))
        item = selection(0, 20, [
            proof("opening", 0, 5, "Kenapa ini penting?"),
            proof("message", 5, 12, "Karena pilihan kecil menentukan arah."),
            proof("ending", 12, 20, "Jadi mulai hari ini ambil satu langkah yang nyata."),
        ])
        result = evaluate_selection(item, PROFILE, transcript)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["selection"]["evidence"][2]["cue_ids"], [2, 3])

    def test_forged_mistimed_and_relabelled_quotes_still_reject(self):
        for alteration in ("forged", "mistimed", "relabelled"):
            item = self.rolling_candidate()
            if alteration == "forged":
                item["selection"]["evidence"][1]["quote"] = "Dapat uang ajaib setiap pagi."
            elif alteration == "mistimed":
                item["selection"]["evidence"][2]["start_time"] = timestamp(71)
                item["selection"]["evidence"][2]["end_time"] = timestamp(72)
            else:
                item["selection"]["evidence"][2] = copy.deepcopy(item["selection"]["evidence"][0])
                item["selection"]["evidence"][2]["part"] = "ending"
                item["selection"]["evidence"][2]["end_time"] = timestamp(80.64)
            with self.subTest(alteration=alteration):
                result = evaluate_selection(item, PROFILE, ROLLING_TRANSCRIPT)
                self.assertFalse(result["accepted"], result)
                self.assertFalse(result["source_evidence_valid"])
                self.assertFalse(result["selection"]["verified_source"])
                self.assertTrue(result["source_evidence_reasons"])
                self.assertTrue(set(result["source_evidence_reasons"]).issubset(result["reasons"]))

    def test_cue_level_time_overlap_accepts_exact_multicue_quote_only(self):
        item = self.rolling_candidate()
        # The model timed the quote at the second subtitle's onset, although
        # its first words belong to the immediately preceding rolling cue.
        item["selection"]["evidence"][0]["start_time"] = timestamp(72.84)
        item["selection"]["evidence"][0]["end_time"] = timestamp(73.5)
        result = evaluate_selection(item, PROFILE, ROLLING_TRANSCRIPT)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["selection"]["evidence"][0]["cue_ids"], [1, 2])
        # A time window elsewhere in the candidate cannot rescue that quote.
        item["selection"]["evidence"][0]["start_time"] = timestamp(78.96)
        item["selection"]["evidence"][0]["end_time"] = timestamp(79.5)
        self.assertFalse(evaluate_selection(item, PROFILE, ROLLING_TRANSCRIPT)["accepted"])

    def test_source_reasons_are_separate_from_semantic_rejections(self):
        item = self.rolling_candidate()
        item["selection"]["gates"]["audience_match"] = False
        item["selection"]["scores"] = {name: 0 for name in SCORE_WEIGHTS}
        result = evaluate_selection(item, PROFILE, ROLLING_TRANSCRIPT)
        self.assertFalse(result["accepted"])
        self.assertTrue(result["source_evidence_valid"])
        self.assertEqual(result["source_evidence_reasons"], [])
        self.assertTrue(result["selection"]["verified_source"])

    def test_audio_aligned_rolling_end_may_use_previous_closing_cue(self):
        transcript = "\n".join((
            "[00:00:00,000 - 00:00:04,000] Dengarkan pembuka ini.",
            "[00:00:04,000 - 00:00:08,000] Intinya kamu bisa mencoba lagi.",
            "[00:00:08,000 - 00:00:12,000] Hari ini bukan akhir segalanya.",
            "[00:00:10,000 - 00:00:14,000] Setelah itu kisah berlanjut.",
        ))
        evidence = [
            proof("opening", 0, 4, "Dengarkan pembuka ini."),
            proof("message", 4, 8, "Intinya kamu bisa mencoba lagi."),
            proof("ending", 8, 10.35, "Hari ini bukan akhir segalanya."),
        ]
        item = selection(0, 10.35, evidence)
        self.assertFalse(evaluate_selection(item, PROFILE, transcript)["accepted"])
        item["speech_boundary"] = {"version": BOUNDARY_VERSION, "method": "rolling_sentence_pause",
                                   "requested_start_seconds": 0, "aligned_end_seconds": 10.35,
                                   "confidence": "medium"}
        self.assertTrue(evaluate_selection(item, PROFILE, transcript)["accepted"])
        original_ending = copy.deepcopy(item["selection"]["evidence"][2])
        item["selection"]["evidence"][2] = proof("ending", 10, 10.35, "Setelah itu kisah berlanjut.")
        self.assertFalse(evaluate_selection(item, PROFILE, transcript)["accepted"])
        item["selection"]["evidence"][2] = original_ending
        item["speech_boundary"]["method"] = "sentence_timestamp"
        self.assertFalse(evaluate_selection(item, PROFILE, transcript)["accepted"])

    def test_repeated_message_quote_attributes_the_ordered_source_match(self):
        transcript = "\n".join((
            "[00:00:00,000 - 00:00:04,000] Pesan awal dimulai sekarang.",
            "[00:00:04,000 - 00:00:08,000] Pesan ini memberi tindakan.",
            "[00:00:08,000 - 00:00:12,000] Sekarang waktunya mencoba.",
        ))
        item = selection(0, 12, [
            proof("opening", 0, 4, "awal dimulai sekarang"),
            proof("message", 0, 8, "Pesan"),
            proof("ending", 8, 12, "Sekarang waktunya mencoba."),
        ])
        result = evaluate_selection(item, PROFILE, transcript)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["selection"]["evidence"][1]["cue_ids"], [1])


if __name__ == "__main__":
    unittest.main()
