# PATCH 2 — CRITICAL: `upload_clip()` argument mismatch

This is a follow-up to `FIX_REPLIZ_BUGS.md`. Patch 1 is already applied and correct.
This patch fixes ONE bug discovered during live testing: `TypeError: WebAPI.upload_clip() takes 3 positional arguments but 4 were given`.

This bug is pre-existing and independent of Patch 1. It happens because pywebview forwards JS arguments as **positional** Python arguments — it does not unpack a trailing JS object into `**kwargs`. `stock-clip.js` calls `upload_clip(path, platform, {title, account_id})`, which arrives in Python as 3 positional args, but `**kwargs` cannot absorb an extra positional argument, only keyword ones.

## Scope lock

Only `app.py` may be edited. Do not touch `web/components/stock-clip.js` — its calling convention is fine and must not change.

## FIX 6 — CRITICAL (upload always crashes)

**File:** `app.py`

**FIND** (exact block — the signature line, docstring, and first body line of `upload_clip`):

```python
    def upload_clip(self, clip_path, platform, **kwargs):
        """Upload clip to the specified platform."""
        cfg_mgr = self._get_cfg_manager()
```

**REPLACE with:**

```python
    def upload_clip(self, clip_path, platform, options=None):
        """Upload clip to the specified platform."""
        kwargs = options or {}
        cfg_mgr = self._get_cfg_manager()
```

**Do not change anything else in this function.** Every line below this point (`kwargs.get("title", ...)`, `kwargs.get("description", "")`, `kwargs.get("account_id")`) stays exactly as-is — they still work because the local variable `kwargs` still exists, it is just now assigned from the `options` parameter instead of being the raw `**kwargs` collector.

## Verification checklist

1. Restart the app (`python app.py`).
2. Settings → Repliz panel → confirm account list still loads (regression check on Patch 1).
3. Go to clips screen, select platform "Repliz", pick an account, click Upload on a single clip.
   - Expected: no `TypeError`. Result is either `{"status": "success", ...}` or a real API-level error (e.g. missing credentials, network error) — NOT a Python argument error.
4. Repeat with "Upload Semua" (bulk upload button) — same expectation.
5. Also test platform "tiktok" and "youtube" from the same button to confirm this signature change didn't break those paths (they also read from the same `kwargs` variable).
6. Confirm only `app.py` was modified (`git diff --stat`).

## Output format

Output the full modified `upload_clip` function (just that function, not the whole file). Then report PASS/FAIL/UNTESTED for each of the 6 checklist items above, same as before.
