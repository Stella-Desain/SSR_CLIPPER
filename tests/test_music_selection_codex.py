"""The opt-in live probe never changes models, auth, or application settings."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.test_music_selection_codex import CodexTestAI, EFFORT, MODEL, response_schema


class CodexMusicProbeTests(unittest.TestCase):
    def make_ai(self):
        with patch("tools.test_music_selection_codex.shutil.which", return_value="codex.exe"), \
                patch("tools.test_music_selection_codex.subprocess.run", return_value=SimpleNamespace(
                    returncode=0, stdout="", stderr="Logged in using ChatGPT")):
            return CodexTestAI()

    def test_exact_model_effort_isolated_read_only_execution_and_structured_answer(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "not-for-this-test", "CODEX_API_KEY": "not-for-this-test"}):
            ai = self.make_ai()

        def respond(command, **kwargs):
            self.assertEqual(command[command.index("--model") + 1], MODEL)
            self.assertIn(f'model_reasoning_effort="{EFFORT}"', command)
            self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
            self.assertIn("--ephemeral", command)
            self.assertIn("--ignore-user-config", command)
            self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
            self.assertNotIn("CODEX_API_KEY", kwargs["env"])
            self.assertEqual(command[-1], "-")
            schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text(encoding="utf-8"))
            self.assertEqual(schema["required"], ["ids"])
            Path(command[command.index("--output-last-message") + 1]).write_text('{"ids":["known"]}', encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed","usage":{"input_tokens":10}}', stderr="")

        with patch("tools.test_music_selection_codex.subprocess.run", side_effect=respond):
            self.assertEqual(ai.ask("Pilih ID dari katalog", {"tracks": [{"id": "known"}]}), {"ids": ["known"]})
        self.assertEqual(ai.usage, [{"stage": "shortlist", "input_tokens": 10}])

    def test_unsupported_model_is_reported_without_switching_model(self):
        ai = self.make_ai()
        response = SimpleNamespace(returncode=1, stdout=f"The '{MODEL}' model is not supported when using Codex with a ChatGPT account.", stderr="")
        with patch("tools.test_music_selection_codex.subprocess.run", return_value=response) as run:
            with self.assertRaisesRegex(ValueError, "Model tidak diganti"):
                ai.ask("Analisis", {})
        self.assertEqual(run.call_count, 1)

    def test_saved_api_key_login_is_not_used_as_chatgpt_auth(self):
        with patch("tools.test_music_selection_codex.shutil.which", return_value="codex.exe"), \
                patch("tools.test_music_selection_codex.subprocess.run", return_value=SimpleNamespace(
                    returncode=0, stdout="", stderr="Logged in using an API key")):
            with self.assertRaisesRegex(ValueError, "login ChatGPT"):
                CodexTestAI()

    def test_schema_contains_fixed_criteria_and_known_ranking_shape(self):
        criteria = response_schema({})
        self.assertIn("climax_seconds", criteria["required"])
        self.assertEqual(criteria["properties"]["energy"]["enum"], ["low", "medium", "high"])
        ranking = response_schema({"candidates": []})
        self.assertEqual(ranking["properties"]["rankings"]["items"]["required"], ["candidate_id", "score", "reason"])


if __name__ == "__main__":
    unittest.main()
