# MASTER — Repliz Integration: Audit, Test, Self-Fix (single session, no more back-and-forth)

## Status so far (do not redo these)

Already applied and confirmed correct by manual code review:
- `get_account_stats()`, `get_repliz_accounts()`, `get_campaigns()` in `app.py` — fixed (Patch 1)
- Account list rendering in `web/app.js` + `web/components/ai-settings.js` — fixed (Patch 1)
- `upload_clip()` signature in `app.py` — fixed (Patch 2), changed from `**kwargs` to `options=None`

This session is about testing everything end-to-end, auditing for the same bug class elsewhere, and fixing anything found — all in one pass, without waiting for another instruction file.

---

## PART A — Self-audit protocol (run this first, before testing)

### Root cause you're checking for

`pywebview` forwards JS arguments to Python **positionally**. If JS calls `window.pywebview.api.someMethod(a, b, {c, d})`, that arrives in Python as 3 positional arguments. A Python method defined as `def someMethod(self, a, b, **kwargs)` CANNOT accept that third positional argument — `**kwargs` only absorbs *keyword* arguments, not extra positional ones. This throws `TypeError: takes N positional arguments but M were given`. This is exactly what broke `upload_clip()` before Patch 2.

### What to do

1. Search `app.py` for every method definition matching `def <name>(self, ...` that is reachable from JS (i.e. not prefixed with `_`).
2. For each one, count the required parameters (excluding `self`, excluding ones with a default value).
3. Search all files under `web/` for every call site: `window.pywebview.api.<name>(...)`.
4. Count the arguments passed at each call site.
5. If any method has a call site passing **more positional arguments than the method's required-parameter count**, and the method uses `**kwargs` (or has too few named parameters), that is the same bug class. List it.
6. If you find any, fix them using the exact same pattern as `upload_clip()`:
   - Change `**kwargs` (or missing parameter) to an explicit named parameter, e.g. `options=None`.
   - Inside the function, do `kwargs = options or {}` if the body already reads from a `kwargs` dict, OR just rename references directly if simpler.
   - Do not change the JS call site unless the JS itself is clearly wrong (e.g. passing the wrong number of arguments for a legitimate reason). Prefer fixing the Python side.
7. You are pre-authorized to make this exact class of fix anywhere you find it, without asking first. Do not use this authorization for anything else (no refactors, no unrelated "improvements", no new features).

Report every mismatch found in this step, even if you already fixed it, in your final report (see Part C).

---

## PART B — Full end-to-end test pass (combined Patch 1 + Patch 2 checklist)

Run the app (`python app.py`) and actually click through this. "UNTESTED" is only acceptable for items that strictly require a live Repliz API key (marked below). Everything else must be actually clicked and observed.

1. App starts with no console errors on launch.
2. Settings → Repliz panel loads without crashing (even with no keys configured — should show a clean "not configured" state, not an exception).
3. **[needs live Repliz key]** Enter a valid access_key/secret_key, Test Connection → succeeds, account list populates with real names + platform type.
4. **[needs live Repliz key]** Dashboard → account/campaign counter and TikTok/YouTube/Instagram counters show real numbers, not "undefined".
5. **[needs live Repliz key]** Dashboard → "Connect More" button opens `https://dashboard.repliz.com` in the default browser, no console error.
6. Clips/upload screen → select platform "Repliz" with no account connected → should show a clean error/empty state, not crash.
7. **[needs live Repliz key]** Same screen, with an account connected → select it, click Upload on one clip → should return `{"status": "success"}` or a real API-level error message — must NOT be a Python `TypeError`.
8. **[needs live Repliz key]** Repeat step 7 using "Upload Semua" (bulk).
9. Same upload button flow, but with platform "tiktok" selected and no TikTok credentials configured → should return the clean `"Kredensial TikTok belum diisi di Settings"` message, not crash. (This alone proves the `options=None` signature change didn't break the tiktok/youtube code paths — no live key needed for this check.)
10. Same as #9 for platform "youtube".
11. Confirm `git diff --stat` — list every file touched in this session (Part A fixes, if any) plus the 4 files already touched in Patch 1/2. Nothing else should appear.

---

## PART C — Final report format (one report, at the end, not per-step)

Do not send partial reports mid-session. Finish Part A and Part B first, then report once:

1. **Part A findings**: list of any additional arg-count mismatches found, each with file:line, what was wrong, and what you changed. If none found, say so explicitly.
2. **Part B checklist**: all 11 items, each marked PASS / FAIL / UNTESTED (with reason — "needs live Repliz key" is a valid reason, anything else is not).
3. **Full diff**: output of `git diff` for any file touched in this session (Part A only — Patch 1/2 files don't need to be reprinted since they're already confirmed).
4. If anything is FAIL: describe the exact error/behavior observed, do not guess at a fix without showing it to me first, unless it is clearly the same arg-count bug class covered by your Part A authorization.
