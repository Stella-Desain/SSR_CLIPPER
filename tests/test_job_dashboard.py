"""Local queue/title/progress regressions. Network and render calls are mocked."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_workflow import Harness
from services.workflow import WorkflowMixin


class JobDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        result = self.api.save_campaign_workspace(None, {"name": "Campaign"})
        self.campaign = result["campaign"]

    def tearDown(self):
        self.tmp.cleanup()

    def add_local(self, name="video.mp4"):
        path = self.root / name
        path.write_bytes(name.encode())
        response = self.api.enqueue_sources([str(path)], self.campaign["id"], {"num_clips": 3})
        self.assertEqual(response["status"], "started", response)
        return self.api._get_store().get("job", response["jobs"][0])

    def test_titles_resolve_without_blocking_enqueue_or_mixing_jobs(self):
        waiting = threading.Event()
        release = threading.Event()
        def fetch(source):
            waiting.set()
            release.wait(5)
            return "Judul A" if "abcdefghijk" in source else "Judul B"
        self.api._fetch_source_title = fetch
        urls = ["https://youtu.be/abcdefghijk", "https://youtu.be/12345678901"]
        response = self.api.enqueue_sources(urls, self.campaign["id"], {"num_clips": 2})
        self.assertEqual(response["status"], "started")
        self.assertTrue(waiting.wait(2))
        thread = self.api._title_thread
        try:
            first = self.api._get_store().get("job", response["jobs"][0])
            self.assertEqual(first["title_status"], "pending")
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        jobs = [self.api._get_store().get("job", job_id) for job_id in response["jobs"]]
        self.assertEqual([j["title"] for j in jobs], ["Judul A", "Judul B"])
        self.assertTrue(all(j["status"] == "queued" for j in jobs))

    def test_metadata_failure_keeps_job_runnable_and_does_not_replace_worker_title(self):
        job = self.add_local()
        store = self.api._get_store()
        job.update(title="Memuat judul…", title_status="pending", source="https://youtu.be/abcdefghijk")
        store.put("job", job["id"], job)
        def fail_after_worker_title(source):
            store.update("job", job["id"], {"title": "Judul dari unduhan", "title_status": "ready"})
            raise TimeoutError("private transport details")
        self.api._fetch_source_title = fail_after_worker_title
        self.api._queue_job_titles([job])
        thread = self.api._title_thread
        if thread:
            thread.join(5)
        saved = store.get("job", job["id"])
        self.assertEqual(saved["title"], "Judul dari unduhan")
        self.assertEqual(saved["status"], "queued")
        self.assertIsNone(saved["error"])

    def test_metadata_command_uses_module_sentinel_timeout_and_cookie_copy(self):
        cookies = self.root / "cookies.txt"
        cookies.write_text("local test cookie", encoding="utf-8")
        observed = {}
        def run(command, **kwargs):
            observed.update(command=command, kwargs=kwargs)
            copied = Path(command[command.index("--cookies")+1])
            self.assertNotEqual(copied, cookies)
            self.assertEqual(copied.read_text(), "local test cookie")
            copied.write_text("changed by metadata process")
            return SimpleNamespace(returncode=0, stdout=json.dumps({"title": "Nama video"}))
        with patch("utils.helpers.get_ytdlp_path", return_value="yt_dlp_module"), patch("services.workflow.subprocess.run", side_effect=run):
            title = self.api._fetch_source_title("https://youtu.be/abcdefghijk")
        self.assertEqual(title, "Nama video")
        self.assertEqual(observed["command"][:3], [sys.executable, "-m", "yt_dlp"])
        self.assertIn("--skip-download", observed["command"])
        self.assertEqual(observed["kwargs"]["timeout"], 25)
        self.assertEqual(cookies.read_text(), "local test cookie")

    def test_title_updates_do_not_reorder_queue(self):
        first = self.add_local("first.mp4")
        second = self.add_local("second.mp4")
        store = self.api._get_store()
        store.update("job", first["id"], {"title": "Read later"})
        listed = {j["id"]: j for j in self.api.get_workflow_jobs()["jobs"]}
        self.assertEqual(listed[first["id"]]["queue_position"], 1)
        self.assertEqual(listed[second["id"]]["queue_position"], 2)
        self.assertEqual(store.claim_job()["id"], first["id"])

    def test_log_progress_and_clips_are_isolated_and_bounded(self):
        first = self.add_local("first.mp4")
        second = self.add_local("second.mp4")
        for index in range(105):
            self.api._record_job_event(first["id"], message=f"First event {index}")
        self.api._record_job_event(first["id"], force=True, progress=.6, step="Caption",
            clips=[{"index": 1, "title": "First clip", "status": "done"}, {"index": 2, "title": "Second clip", "status": "error", "error": "Oops"}])
        self.api._record_job_event(second["id"], force=True, message="Second job only", progress=.1)
        self.api._active_job = second
        self.api.core = SimpleNamespace(job_id="unrelated", get_clips_state=lambda: [{"title": "Foreign clip"}])
        self.api.progress = .99
        jobs = {j["id"]: j for j in self.api.get_workflow_jobs()["jobs"]}
        self.assertEqual(jobs[first["id"]]["progress"], .6)
        self.assertEqual(jobs[first["id"]]["counts"], {"requested": 3, "planned": 2, "completed": 1, "failed": 1, "cancelled": 0})
        self.assertEqual(len(jobs[first["id"]]["logs"]), 100)
        self.assertEqual(jobs[first["id"]]["logs"][0]["message"], "First event 5")
        self.assertEqual(jobs[second["id"]]["clips"], [])
        self.assertEqual([l["message"] for l in jobs[second["id"]]["logs"]], ["Second job only"])
        self.assertEqual(self.api._get_store().get("job", first["id"])["step"], "Caption")

    def test_next_job_failure_does_not_reuse_previous_core(self):
        job = self.add_local()
        self.api.core = SimpleNamespace(job_id="previous", get_clips_state=lambda: [{"title": "Previous", "status": "done"}])
        self.api.progress = 1
        self.api._run = Mock(side_effect=ValueError("Failed before core setup"))
        self.api._execute_job(job)
        saved = self.api._get_store().get("job", job["id"])
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["clips"], [])
        self.assertEqual(saved["progress"], 0)
        self.assertEqual(saved["error"], "Failed before core setup")

    def test_running_queue_accepts_another_source_and_drains_without_polling(self):
        first = self.add_local("first.mp4")
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        seen = []
        def run(source, *args):
            seen.append(Path(source).name)
            if len(seen) == 1:
                started.set()
                release.wait(5)
            self.api.progress = 1
            self.api.status = "complete"
            if len(seen) == 2:
                finished.set()
        self.api._run = run
        self.api._start_next_job = lambda: WorkflowMixin._start_next_job(self.api)
        self.api._start_next_job()
        self.assertTrue(started.wait(2))
        thread = self.api.thread
        try:
            second = self.add_local("second.mp4")
            self.assertEqual(self.api._get_store().get("job", second["id"])["status"], "queued")
        finally:
            release.set()
            thread.join(5)
        self.assertTrue(finished.is_set())
        self.assertFalse(thread.is_alive())
        self.assertEqual(seen, ["first.mp4", "second.mp4"])
        for job in (first, second):
            self.assertEqual(self.api._get_store().get("job", job["id"])["status"], "completed")

    def test_queued_cancel_is_serialized_with_worker_claim(self):
        job = self.add_local()
        store = self.api._get_store()
        read = threading.Event()
        release = threading.Event()
        original_get = store.get
        def delayed_get(kind, entity_id):
            value = original_get(kind, entity_id)
            if kind == "job" and entity_id == job["id"] and threading.current_thread().name == "cancel-test":
                read.set()
                release.wait(5)
            return value
        self.api._run = Mock()
        result = []
        with patch.object(store, "get", side_effect=delayed_get):
            cancel = threading.Thread(target=lambda: result.append(self.api.control_job(job["id"], "cancel")), name="cancel-test")
            cancel.start()
            self.assertTrue(read.wait(2))
            start = threading.Thread(target=lambda: WorkflowMixin._start_next_job(self.api))
            start.start()
            try:
                self.assertFalse(self.api._run.called)
            finally:
                release.set()
                cancel.join(5)
                start.join(5)
        self.assertEqual(result, [{"status": "ok"}])
        self.assertEqual(store.get("job", job["id"])["status"], "cancelled")
        self.api._run.assert_not_called()

    def test_cancelling_running_job_does_not_cancel_next_source(self):
        first = self.add_local("first.mp4")
        second = self.add_local("second.mp4")
        first_started = threading.Event()
        second_started = threading.Event()
        release_first = threading.Event()
        release_second = threading.Event()
        cancellation_on_second = []
        def run(source, *args):
            if Path(source).name == "first.mp4":
                first_started.set()
                release_first.wait(5)
            else:
                cancellation_on_second.append(self.api._cancel_event.is_set())
                second_started.set()
                release_second.wait(5)
            self.api.status = "complete"
        self.api._run = run
        WorkflowMixin._start_next_job(self.api)
        thread = self.api.thread
        try:
            self.assertTrue(first_started.wait(2))
            self.assertEqual(self.api.control_job(first["id"], "cancel")["status"], "ok")
            release_first.set()
            self.assertTrue(second_started.wait(2))
            self.assertEqual(self.api.control_job(first["id"], "cancel")["status"], "error")
            self.assertFalse(self.api._cancel_event.is_set())
        finally:
            release_first.set()
            release_second.set()
            thread.join(5)
        self.assertEqual(cancellation_on_second, [False])
        self.assertEqual(self.api._get_store().get("job", first["id"])["status"], "cancelled")
        self.assertEqual(self.api._get_store().get("job", second["id"])["status"], "completed")


if __name__ == "__main__":
    unittest.main()
