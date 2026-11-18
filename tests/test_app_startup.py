"""Desktop startup wiring can be checked without opening a native window."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app


class FakeEvent:
    def __init__(self):
        self.callbacks = []

    def __iadd__(self, callback):
        self.callbacks.append(callback)
        return self


class AppStartupTests(unittest.TestCase):
    def test_webview_uses_existing_unique_private_data_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = SimpleNamespace(**{name: FakeEvent() for name in
                ("initialized", "before_show", "shown", "loaded", "closed")})
            window = SimpleNamespace(events=events)
            shutdown_calls = []
            api = SimpleNamespace(output_dir=str(root / "output"),editor_shutdown=lambda:shutdown_calls.append(True))
            observed = []

            def start_webview(**kwargs):
                profile = Path(kwargs["storage_path"])
                self.assertTrue(profile.is_dir())
                self.assertEqual(profile.parent, root / "local" / "SSR_CLIPPER" / "webview2")
                self.assertTrue(kwargs["private_mode"])
                observed.append(profile)
                for name in ("initialized", "before_show", "shown", "loaded"):
                    for callback in getattr(events, name).callbacks:
                        if name != "loaded" or callback is not events.loaded.callbacks[-1]:
                            callback()
                for callback in events.closed.callbacks:
                    callback()

            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}), \
                    patch.object(app, "WebAPI", return_value=api), \
                    patch.object(app, "get_bundle_dir", return_value=Path(app.__file__).parent), \
                    patch.object(app.threading, "Thread"), \
                    patch.object(app.webview, "create_window", return_value=window) as create_window, \
                    patch.object(app.webview, "start", side_effect=start_webview) as start:
                app.main()

            self.assertEqual(len(observed), 1)
            self.assertFalse(observed[0].exists())
            self.assertEqual(create_window.call_count, 1)
            self.assertEqual(start.call_count, 1)
            self.assertEqual(len(shutdown_calls),2, 'Window close and event-loop exit both cancel pending Editor renders')


if __name__ == "__main__":
    unittest.main()
