"""Execute the user's approved 40 + 51 clip batch without opening the GUI.

Uses the existing review, account, storage, and Repliz scheduling adapters.
The user explicitly authorized moving clippo_five to Timothy Ronald and posting
all distinct approved edits, including edits sharing some source footage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import queue
import random
import re
import shutil
import sqlite3
import sys
import threading
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import WebAPI
from services.account_tags import publication_caption
from services.clip_variants import publication_media, verify_clip_files
from services.publishing import ReplizClient, eligible_accounts, matches_publication, overlapping, schedule_update
from services.scheduling import display_schedule_time
from services.storage import atomic_json, digest, utc_now

ZONE = ZoneInfo("Asia/Makassar")
CAMPAIGN = "camp_43ef11ba"
ACCOUNT_IDS = ["6ab7d8cb62caae1e044feb07", "6a6e52d862caae1e04ef51a3"]
JOB_FOLDERS = ["job-202cb116a5c24bf7", "job-129d2adda72b4e00"]
TIMES = ["08:20", "11:01", "19:00", "19:30"]
BATCH_ID = "approved-timothy-91-20261007"
REPORT_DIR = ROOT / "output" / "upload-approved-20261007"
PLAN = REPORT_DIR / "plan.json"


class HeadlessAPI(WebAPI):
    def _start_upload_worker(self):
        # This driver owns the worker lease and runs four bounded workers below.
        pass


def output(data):
    message = json.dumps(data, ensure_ascii=True)
    message = re.sub(r"/uploads/[^\s\"']+", "[storage URL redacted]", message)
    print(message, flush=True)


def provider(api):
    cfg = api._get_cfg()["repliz"]
    return ReplizClient(cfg["access_key"], cfg["secret_key"])


def remote_schedules(client):
    records = []
    for page in range(1, 101):
        result = client.get("schedule", {"page": page, "limit": 100, "accountIds[]": ACCOUNT_IDS})
        result = result.get("data", result)
        records.extend(result.get("docs", []))
        if not result.get("hasNextPage"):
            return records
    raise RuntimeError("Provider schedule pagination did not finish.")


def selected_clips(api):
    groups = [[c for c in api._get_store().list("clip") if folder in str(c.get("path", ""))]
              for folder in JOB_FOLDERS]
    if [len(g) for g in groups] != [40, 51]:
        raise RuntimeError("Expected the original 40 and 51 clip jobs.")
    for group in groups:
        group.sort(key=lambda c: c["path"])
    clips = []
    for index in range(max(map(len, groups))):
        clips.extend(group[index] for group in groups if index < len(group))
    for clip in clips:
        if clip.get("review_status") != "approved" or clip.get("approval_hash") != api._approval_digest(clip):
            raise RuntimeError(f"Approval changed: {clip['title']}")
        verify_clip_files(clip)
        publication_media(clip, "tiktok")
    return clips


def configure_accounts(api, accounts):
    # The user answered explicitly: move clippo_five away from the cosplay campaign.
    for campaign in api._get_cfg().get("campaigns", []):
        if campaign["id"] != CAMPAIGN and ACCOUNT_IDS[0] in campaign.get("account_ids", []):
            result = api.save_campaign_workspace(campaign["id"], {
                "account_ids": [aid for aid in campaign["account_ids"] if aid != ACCOUNT_IDS[0]]})
            if result.get("status") != "ok":
                raise RuntimeError(result)
    result = api.save_campaign_workspace(CAMPAIGN, {"account_ids": ACCOUNT_IDS})
    if result.get("status") != "ok":
        raise RuntimeError(result)
    for aid in ACCOUNT_IDS:
        result = api.save_account_profile(aid, {"campaign_id": CAMPAIGN, "daily_limit": 4,
            "upload_times": TIMES, "name": accounts[aid]["name"], "platform": "tiktok"})
        if result.get("status") != "ok":
            raise RuntimeError(result)


def balanced_assignment(clips):
    """Split 46/45, reducing same-account reuse of overlapping source ranges."""
    graph = {c["id"]: set() for c in clips}
    for index, clip in enumerate(clips):
        for other in clips[index + 1:]:
            if overlapping(clip, other):
                graph[clip["id"]].add(other["id"])
                graph[other["id"]].add(clip["id"])
    rng = random.Random(20261007)
    identifiers = list(graph)
    best = None
    for _ in range(50):
        rng.shuffle(identifiers)
        side = {cid: int(i >= 46) for i, cid in enumerate(identifiers)}
        for _ in range(100):
            gains = {cid: sum(1 if side[n] == side[cid] else -1 for n in graph[cid]) for cid in graph}
            moves = [(gains[a] + gains[b] + (2 if b in graph[a] else 0), a, b)
                     for a in graph if side[a] == 0 for b in graph if side[b] == 1]
            gain, a, b = max(moves)
            if gain <= 0:
                break
            side[a], side[b] = side[b], side[a]
        cost = sum(side[cid] == side[n] for cid in graph for n in graph[cid]) // 2
        if best is None or cost < best[0]:
            best = cost, side.copy()
    return [[c for c in clips if best[1][c["id"]] == i] for i in range(2)]


def make_plan(api, clips, accounts, remote):
    now = datetime.now(timezone.utc)
    all_clips = {c["id"]: c for c in clips}
    previous = api._get_store().publications()
    if any(p.get("clip_id") in all_clips and p["status"] != "cancelled" for p in previous):
        raise RuntimeError("Target clips already have publication records; resume the saved plan.")
    titles = {c.get("title") for c in clips}
    if any(r.get("title") in titles for r in remote):
        raise RuntimeError("A target title already exists at the provider; reconcile before submitting.")
    cfg = api._get_cfg()
    if cfg.get("timezone") != "Asia/Makassar":
        raise RuntimeError("Global timezone must remain WITA.")
    campaign = next(c for c in cfg["campaigns"] if c["id"] == CAMPAIGN)
    allowed = eligible_accounts(campaign, api._get_store().list("account_profile"), list(accounts.values()))
    if {str(a["_id"]) for a, _ in allowed} != set(ACCOUNT_IDS):
        raise RuntimeError("Both exact TikTok accounts must be eligible.")
    assignments = []
    for aid, group in zip(ACCOUNT_IDS, balanced_assignment(clips)):
        remaining = group.copy()
        history = []
        remote_times = [datetime.fromisoformat(r["scheduleAt"].replace("Z", "+00:00"))
                        for r in remote if r.get("accountId") == aid and r.get("scheduleAt")]
        for offset in range(366):
            day = now.astimezone(ZONE).date() + timedelta(days=offset)
            occupied = sum(t.astimezone(ZONE).date() == day for t in remote_times)
            for slot in TIMES:
                if not remaining:
                    break
                when = datetime.fromisoformat(day.isoformat() + "T" + slot).replace(tzinfo=ZONE).astimezone(timezone.utc)
                if when < now + timedelta(minutes=45) or occupied >= 4:
                    continue
                if any(abs((t - when).total_seconds()) < 60 for t in remote_times):
                    continue
                def priority(c):
                    # Spread related edits apart instead of placing them consecutively.
                    nearby = sum(overlapping(c, old) for old, t in history if when - t < timedelta(days=3))
                    same_source = bool(history and c.get("source_ranges", [{}])[0].get("source_id") ==
                        history[-1][0].get("source_ranges", [{}])[0].get("source_id"))
                    return nearby, same_source, clips.index(c)
                clip = min(remaining, key=priority)
                remaining.remove(clip)
                history.append((clip, when))
                occupied += 1
                media = publication_media(clip, "tiktok")
                assignments.append({
                    "id": "pub_" + digest({"batch": BATCH_ID, "clip": clip["id"]})[:32],
                    "dedupe_key": digest({"clip_id": clip["id"], "account_id": aid}),
                    "clip_id": clip["id"], "clip_title": clip["title"], "clip_path": media["path"],
                    "campaign_id": clip["campaign_id"], "campaign_version_id": clip.get("campaign_version_id"),
                    "revision_id": clip.get("revision_id"), "file_hash": media["file_hash"],
                    "approval_hash": clip["approval_hash"], "account_id": aid, "account_name": accounts[aid]["name"],
                    "platform": "tiktok", "audience_scope": campaign["audience_scope"],
                    "daily_limit": 4, "timezone": "Asia/Makassar", "upload_times": TIMES,
                    "scheduled_at": when.isoformat(), "local_day": day.isoformat(),
                    "caption": publication_caption(clip, "tiktok"), "status": "queued",
                    "source_ranges": clip.get("source_ranges", []), "created_at": utc_now(), "error": None,
                    "batch_id": BATCH_ID, "allow_source_overlap": True,
                    "overlap_authorization": "User requested every distinct approved clip from both original jobs.",
                })
            if not remaining:
                break
        if remaining:
            raise RuntimeError("Not enough scheduling slots.")
    assignments.sort(key=lambda a: (a["scheduled_at"], ACCOUNT_IDS.index(a["account_id"])))
    return {"batch_id": BATCH_ID, "created_at": utc_now(), "timezone": "Asia/Makassar", "assignments": assignments}


def prepare(api):
    if PLAN.exists():
        return json.loads(PLAN.read_text(encoding="utf-8"))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config.json", REPORT_DIR / "config-before-upload.json")
    with sqlite3.connect(ROOT / "workflow.sqlite3") as source, sqlite3.connect(REPORT_DIR / "workflow-before-upload.sqlite3") as backup:
        source.backup(backup)
    clips = selected_clips(api)
    response = api.get_repliz_accounts()
    if response.get("status") != "ok":
        raise RuntimeError(response)
    accounts = {a["_id"]: a for a in response["accounts"] if a["_id"] in ACCOUNT_IDS}
    if len(accounts) != 2 or any(a.get("isConnected") is False or a.get("type") != "tiktok" for a in accounts.values()):
        raise RuntimeError("The two requested TikTok accounts are not connected.")
    client = provider(api)
    remote = remote_schedules(client)
    usage = client.get("storage/statistic")
    size = sum(Path(publication_media(c, "tiktok")["path"]).stat().st_size for c in clips)
    if usage.get("usage", {}).get("free", 0) < size:
        raise RuntimeError("Provider storage is insufficient for the original approved files.")
    configure_accounts(api, accounts)
    plan = make_plan(api, clips, accounts, remote)
    atomic_json(PLAN, plan)
    return plan


def reserve(api, plan):
    store = api._get_store()
    token = "preview_" + BATCH_ID
    record = store.get("distribution_preview", token)
    if record and record.get("confirmed"):
        return
    store.put("distribution_preview", token, {"id": token, "assignments": plan["assignments"],
        "timezone": "Asia/Makassar", "created": time.time()})
    result = api.confirm_distribution(token)
    if result.get("status") != "ok":
        raise RuntimeError(result)
    output({"reserved": result.get("total_scheduled")})


def run_uploads(api, plan):
    store = api._get_store()
    tasks = queue.Queue()
    for item in plan["assignments"]:
        current = store.publication(item["id"])
        if current["status"] == "queued" or (current["status"] == "failed" and not current.get("uncertain_submission") and not current.get("schedule_id")):
            tasks.put(item["id"])
    stop = threading.Event()
    def worker():
        while not stop.is_set():
            try:
                pid = tasks.get_nowait()
            except queue.Empty:
                return
            try:
                pub = store.update_publication(pid, {"status": "uploading", "attempted_at": utc_now()}, expected_status={"queued", "failed"})
                api._send_publication(pub)
                current = store.publication(pid)
                output({"publication": pid, "status": current["status"], "error": current.get("error")})
                if any(code in str(current.get("error", "")) for code in ["HTTP 401", "HTTP 402", "HTTP 403"]):
                    stop.set()
            finally:
                tasks.task_done()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(worker) for _ in range(4)]
        for future in futures:
            future.result()


def verify_and_report(api, plan):
    store = api._get_store()
    problems = []
    def verify(item):
        current = store.publication(item["id"])
        if current.get("uncertain_submission") and current.get("media_url"):
            try:
                store.update_publication(current["id"], provider(api).reconcile(current))
                current = store.publication(current["id"])
            except Exception as exc:
                return {"id": item["id"], "error": str(exc)}
        if not current.get("schedule_id"):
            return {"id": item["id"], "error": current.get("error") or current["status"]}
        try:
            raw = provider(api).schedule(current["schedule_id"])
            remote = raw.get("data", raw)
            if not matches_publication(remote, current):
                raise RuntimeError("Provider account, caption, media, or scheduled time differs from the approved plan.")
            update = schedule_update(raw)
            if update.get("status") not in {"scheduled", "publishing", "published"}:
                raise RuntimeError(update.get("error") or "Provider did not confirm the schedule.")
            store.update_publication(current["id"], {**update, "verified_at": utc_now()})
        except Exception as exc:
            return {"id": item["id"], "error": str(exc)}
        return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        problems = [p for p in pool.map(verify, plan["assignments"]) if p]
    records = [store.publication(item["id"]) for item in plan["assignments"]]
    report = {"batch_id": BATCH_ID, "verified_at": utc_now(), "total": len(records),
        "statuses": dict(Counter(p["status"] for p in records)),
        "per_account": dict(Counter(p["account_name"] for p in records)), "problems": problems,
        "timezone": "Asia/Makassar", "daily_times": ["08:20 AM", "11:01 AM", "07:00 PM", "07:30 PM"],
        "first": min(p["scheduled_at"] for p in records), "last": max(p["scheduled_at"] for p in records),
        "publications": records}
    atomic_json(REPORT_DIR / "result.json", report)
    with (REPORT_DIR / "jadwal-upload.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["clip", "akun", "sosmed", "jadwal_wita", "status", "schedule_id"])
        writer.writeheader()
        for pub in records:
            writer.writerow({"clip": pub["clip_title"], "akun": pub["account_name"], "sosmed": "TikTok",
                "jadwal_wita": display_schedule_time(pub["scheduled_at"], "Asia/Makassar"),
                "status": pub["status"], "schedule_id": pub.get("schedule_id", "")})
    lines = ["# Hasil upload 91 clip Timothy Ronald", "",
        f"Diverifikasi: {display_schedule_time(report['verified_at'], 'Asia/Makassar')}", "",
        f"Status: {report['statuses']}", f"Pembagian: {report['per_account']}", "",
        "Jam harian per akun: 08:20 AM, 11:01 AM, 07:00 PM, 07:30 PM (WITA).", "",
        "| Clip | Akun | Jadwal WITA | Status | ID provider |", "|---|---|---|---|---|"]
    for pub in records:
        lines.append(f"| {pub['clip_title'].replace('|', '/')} | {pub['account_name']} | "
            f"{display_schedule_time(pub['scheduled_at'], 'Asia/Makassar')} | {pub['status']} | {pub.get('schedule_id', '')} |")
    (REPORT_DIR / "HASIL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    output({k: v for k, v in report.items() if k != "publications"})
    return not problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "run", "verify"])
    args = parser.parse_args()
    api = HeadlessAPI()
    if not api.worker_enabled:
        raise RuntimeError("Another SSR process owns the upload worker; no duplicate worker was started.")
    try:
        plan = prepare(api)
        if args.mode == "prepare":
            output({"prepared": len(plan["assignments"]), "per_account": dict(Counter(p["account_name"] for p in plan["assignments"])),
                "first": plan["assignments"][0]["scheduled_at"], "last": plan["assignments"][-1]["scheduled_at"]})
            return
        if args.mode == "run":
            reserve(api, plan)
            run_uploads(api, plan)
        if not verify_and_report(api, plan):
            raise SystemExit(2)
    finally:
        api._worker_lease.close()


if __name__ == "__main__":
    main()
