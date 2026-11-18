"""Transactional workflow storage. Media stays on disk; SQLite owns mutable state."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def atomic_json(path, data):
    import os
    import tempfile
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(encode(data))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if Path(tmp).exists():
            Path(tmp).unlink()


class WorkflowStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS entities (
                    kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY(kind,id)
                );
                CREATE TABLE IF NOT EXISTS publications (
                    id TEXT PRIMARY KEY, dedupe_key TEXT NOT NULL UNIQUE,
                    clip_id TEXT NOT NULL, account_id TEXT NOT NULL,
                    local_day TEXT NOT NULL, scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS pub_capacity ON publications(account_id,local_day,status);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def put(self, kind, entity_id, data):
        with self.connect() as connection:
            self._put(connection, kind, entity_id, data)
        return data

    @staticmethod
    def _put(connection, kind, entity_id, data):
        connection.execute(
            "INSERT INTO entities VALUES (?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at",
            (kind, str(entity_id), encode(data), utc_now()),
        )

    def get(self, kind, entity_id):
        with self.connect() as connection:
            row = connection.execute("SELECT data FROM entities WHERE kind=? AND id=?", (kind, str(entity_id))).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind):
        with self.connect() as connection:
            rows = connection.execute("SELECT data FROM entities WHERE kind=? ORDER BY updated_at DESC,id", (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def update(self, kind, entity_id, fields):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM entities WHERE kind=? AND id=?", (kind, str(entity_id))).fetchone()
            if not row:
                raise KeyError(entity_id)
            data = json.loads(row[0])
            data.update(fields)
            self._put(connection, kind, entity_id, data)
            return data

    def delete(self, kind, entity_id):
        with self.connect() as connection:
            connection.execute("DELETE FROM entities WHERE kind=? AND id=?", (kind, str(entity_id)))

    def claim_job(self):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT id,data,updated_at FROM entities WHERE kind='job'").fetchall()
            ordered = [(row, json.loads(row["data"])) for row in rows]
            ordered.sort(key=lambda item: (item[1].get("queued_at") or item[1].get("created_at") or item[0]["updated_at"], item[0]["id"]))
            for row, job in ordered:
                if job.get("status") != "queued":
                    continue
                job.update(status="running", started_at=utc_now(), error=None)
                self._put(connection, "job", row["id"], job)
                return job
        return None

    def recover_interrupted(self):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT id,data FROM entities WHERE kind='job'").fetchall()
            for row in rows:
                job = json.loads(row["data"])
                if job.get("status") in ("running", "cancelling"):
                    job.update(status="interrupted", error="Aplikasi berhenti. Lanjutkan pekerjaan untuk memakai hasil yang sudah selesai.")
                    self._put(connection, "job", row["id"], job)
            rows = connection.execute("SELECT id,data FROM publications WHERE status IN ('uploading','publishing')").fetchall()
            for row in rows:
                pub = json.loads(row["data"])
                uncertain = pub["status"] == "publishing"
                pub.update(status="needs_attention" if uncertain else "failed", uncertain_submission=uncertain,
                           error="Pengiriman jadwal terputus; periksa provider sebelum mengulang." if uncertain else "Upload file terputus sebelum pengiriman jadwal. Bisa dicoba kembali.")
                self._save_publication(connection, pub)

    def publications(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT data FROM publications ORDER BY scheduled_at,id").fetchall()
        return [json.loads(row[0]) for row in rows]

    def publication(self, publication_id):
        with self.connect() as connection:
            row = connection.execute("SELECT data FROM publications WHERE id=?", (publication_id,)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _save_publication(connection, publication):
        p = publication
        connection.execute("""INSERT INTO publications VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET status=excluded.status,data=excluded.data,updated_at=excluded.updated_at,
            scheduled_at=excluded.scheduled_at,local_day=excluded.local_day""",
            (p["id"], p["dedupe_key"], p["clip_id"], p["account_id"], p["local_day"], p["scheduled_at"], p["status"], encode(p), utc_now()))

    def save_publication(self, publication):
        with self.connect() as connection:
            self._save_publication(connection, publication)

    def update_publication(self, publication_id, fields, expected_status=None):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM publications WHERE id=?", (publication_id,)).fetchone()
            if not row:
                raise KeyError(publication_id)
            publication = json.loads(row[0])
            if expected_status is not None and publication["status"] not in expected_status:
                raise ValueError("Status publikasi berubah. Perbarui halaman sebelum mencoba kembali.")
            publication.update(fields)
            self._save_publication(connection, publication)
            return publication

    def claim_publication(self):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM publications WHERE status='queued' ORDER BY scheduled_at,id LIMIT 1").fetchone()
            if not row:
                return None
            publication = json.loads(row[0])
            publication.update(status="uploading", attempted_at=utc_now())
            self._save_publication(connection, publication)
            return publication

    def reserve_publications(self, proposed, validate):
        """Recheck every slot inside a write transaction, then insert the whole batch."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self._reserve_publications(connection, proposed, validate)

    def _reserve_publications(self, connection, proposed, validate):
        existing = [json.loads(row[0]) for row in connection.execute("SELECT data FROM publications")]
        keys = {p["dedupe_key"] for p in existing}
        inserted = []
        for publication in proposed:
            if publication["dedupe_key"] in keys:
                previous = next(p for p in existing if p["dedupe_key"] == publication["dedupe_key"])
                if previous["status"] == "cancelled" and not previous.get("schedule_id") and not previous.get("uncertain_submission"):
                    # Keep cancelled history while allowing a fresh, explicitly approved batch.
                    previous["dedupe_key"] += ":cancelled:" + previous["id"]
                    connection.execute("UPDATE publications SET dedupe_key=?,data=? WHERE id=?", (previous["dedupe_key"], encode(previous), previous["id"]))
                    keys.discard(publication["dedupe_key"])
                else:
                    continue
            validate(publication, existing)
            self._save_publication(connection, publication)
            existing.append(publication)
            keys.add(publication["dedupe_key"])
            inserted.append(publication)
        return inserted

    def edit_distribution_preview(self, preview_id, edit_and_validate):
        """Serialize edits against confirmation and validate against live reservations."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM entities WHERE kind='distribution_preview' AND id=?", (str(preview_id),)).fetchone()
            if not row:
                raise ValueError("Preview tidak ditemukan. Buat preview distribusi ulang.")
            record = json.loads(row[0])
            if record.get("confirmed"):
                raise ValueError("Paket ini sudah masuk antrean. Jadwal preview tidak dapat diubah.")
            existing = [json.loads(p[0]) for p in connection.execute("SELECT data FROM publications")]
            edit_and_validate(record, existing)
            self._put(connection, "distribution_preview", str(preview_id), record)
            return record

    def reserve_distribution_preview(self, preview_id, validate_policy, validate):
        """Reserve and mark the exact persisted preview in one transaction."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM entities WHERE kind='distribution_preview' AND id=?", (str(preview_id),)).fetchone()
            if not row:
                raise ValueError("Preview tidak ditemukan. Buat preview distribusi ulang.")
            record = json.loads(row[0])
            if record.get("confirmed"):
                return []
            validate_policy(record)
            inserted = self._reserve_publications(connection, record["assignments"], validate)
            record["confirmed"] = True
            self._put(connection, "distribution_preview", str(preview_id), record)
            return inserted
