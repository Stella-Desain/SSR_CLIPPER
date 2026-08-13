# TASK: Fix Repliz Integration Bugs — clip-v2 (branch: feature/pywebview-desktop-integration)

You are fixing 5 confirmed bugs in a pywebview desktop app. Do NOT redesign, refactor, or "improve" anything beyond what is specified below. Do NOT touch any file not listed here. Each fix has an exact FIND block (must match verbatim) and an exact REPLACE block. If a FIND block does not match exactly, STOP and report the mismatch instead of guessing.

## Scope lock

Only these 4 files may be edited:
- `app.py`
- `web/components/ai-settings.js`
- `web/app.js`
- `web/components/dashboard.js`

Do not modify `dialogs/repliz_upload.py`, `web/components/stock-clip.js`, or any other file. They are already correct and are the reference implementation for the API contract used below.

---

## FIX 1 — CRITICAL (blocks the entire Repliz upload feature)

**File:** `app.py`
**Problem:** `get_repliz_accounts()` is a stub. It always returns an error, so the account dropdown in the upload flow (`web/components/stock-clip.js`) never populates, and every Repliz upload gets blocked by a "Please select a Repliz account first" alert before it ever reaches the upload logic.

**FIND** (exact block, currently around line 289–328):

```python
    def get_account_stats(self):
        """Returns statistics of connected social accounts."""
        try:
            cfg = self._get_cfg()
            repliz_cfg = cfg.get("repliz", {})
            access_key = repliz_cfg.get("access_key")
            secret_key = repliz_cfg.get("secret_key")
            
            if not access_key or not secret_key:
                return {"error": True, "message": "Keys not configured"}
                
            import requests
            from requests.auth import HTTPBasicAuth
            url = "https://api.repliz.com/public/account"
            params = {"page": 1, "limit": 10}
            
            response = requests.get(
                url, 
                params=params,
                auth=HTTPBasicAuth(access_key, secret_key),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("totalDocs", 0)
                return {"campaigns": total, "error": False}
            else:
                return {"error": True, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def get_repliz_accounts(self):
        """Returns list of connected Repliz accounts for UI selection."""
        # TODO: Repliz API haven't provided official endpoints yet
        return {"status": "error", "message": "TODO: API Endpoint Repliz belum ada"}

    def get_campaigns(self):
        # TODO: Repliz API hasn't provided official endpoints yet
        return {"error": True, "message": "TODO: API Endpoint Repliz belum ada"}
```

**REPLACE with:**

```python
    def get_account_stats(self):
        """Returns statistics of connected social accounts, broken down by platform."""
        try:
            cfg = self._get_cfg()
            repliz_cfg = cfg.get("repliz", {})
            access_key = repliz_cfg.get("access_key")
            secret_key = repliz_cfg.get("secret_key")

            if not access_key or not secret_key:
                return {"error": True, "message": "Keys not configured"}

            import requests
            from requests.auth import HTTPBasicAuth
            url = "https://api.repliz.com/public/account"
            params = {"page": 1, "limit": 50}

            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(access_key, secret_key),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                docs = data.get("docs", [])
                total = data.get("totalDocs", len(docs))
                tiktok_count = sum(1 for a in docs if a.get("type") == "tiktok")
                youtube_count = sum(1 for a in docs if a.get("type") == "youtube")
                instagram_count = sum(1 for a in docs if a.get("type") == "instagram")
                return {
                    "campaigns": total,
                    "tiktok_count": tiktok_count,
                    "youtube_count": youtube_count,
                    "instagram_count": instagram_count,
                    "error": False
                }
            else:
                return {"error": True, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def get_repliz_accounts(self):
        """Returns list of connected Repliz accounts for UI selection (upload account picker)."""
        try:
            cfg = self._get_cfg()
            repliz_cfg = cfg.get("repliz", {})
            access_key = repliz_cfg.get("access_key")
            secret_key = repliz_cfg.get("secret_key")

            if not access_key or not secret_key:
                return {"status": "error", "message": "Repliz keys not configured"}

            import requests
            from requests.auth import HTTPBasicAuth
            url = "https://api.repliz.com/public/account"
            params = {"page": 1, "limit": 50}

            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(access_key, secret_key),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                docs = data.get("docs", [])
                accounts = [
                    {
                        "_id": a.get("_id"),
                        "name": a.get("name"),
                        "type": a.get("type"),
                        "isConnected": a.get("isConnected", True)
                    }
                    for a in docs
                ]
                return {"status": "ok", "accounts": accounts}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_campaigns(self):
        """Repliz public API has no campaigns endpoint yet. Return an empty list
        (not an error object) so the frontend's `campaigns.length` check works
        correctly and the Campaigns Tree just renders empty instead of breaking."""
        return []
```

**Why this is correct (context, do not second-guess it):** `test_repliz_connection()` (already in the file, untouched) and `dialogs/repliz_upload.py::load_accounts()` (reference implementation, untouched) both already call this exact same endpoint (`GET https://api.repliz.com/public/account`) with `HTTPBasicAuth(access_key, secret_key)` and successfully get back `{"docs": [...], "totalDocs": N}` where each doc has `_id`, `name`, `type`, `isConnected`. This fix just reuses that proven pattern. `get_campaigns()` returns `[]` because `web/components/dashboard.js` line ~298 does `campaigns = await window.pywebview.api.get_campaigns()` then checks `campaigns.length > 0` — it expects a plain array, not an object.

---

## FIX 2 — HIGH (dead button in Settings panel)

**File:** `web/components/ai-settings.js`
**Problem:** The "Connect More" button calls `window.pywebview.api.open_url(...)`, but no `open_url` method exists in `app.py`. Clicking it does nothing (silent JS error).

**FIND** (exact line, around line 251):

```javascript
  connectMoreDiv.innerHTML = '<button class="btn btn-lime-full" style="font-weight:600;font-size:13px;" onclick="window.pywebview.api.open_url(\'https://dashboard.repliz.com\')">Connect More</button>';
```

**REPLACE with:**

```javascript
  connectMoreDiv.innerHTML = '<button class="btn btn-lime-full" style="font-weight:600;font-size:13px;" onclick="window.open(\'https://dashboard.repliz.com\', \'_blank\')">Connect More</button>';
```

**Why:** `web/components/dashboard.js` already has a working pattern for opening an external URL from pywebview — it uses `window.open(url, '_blank')` directly in JS (see the `#btn-repliz-dashboard` handler), it does NOT call a Python method for this. Reuse that pattern instead of adding a new Python method.

---

## FIX 3 — HIGH (account list never renders in Settings panel)

**File:** `web/components/ai-settings.js`
**Problem:** The `accountsList` container div is created but never added to the `fields` object that gets returned, so `web/app.js` has no reference to it and can never render account cards into it.

**FIND** (exact block, near the end of the file, inside the `fields: { ... }` return object — look for this exact line):

```javascript
      accountsTitle: accountsTitle,
```

**REPLACE with:**

```javascript
      accountsTitle: accountsTitle,
      accountsList: accountsList,
```

---

## FIX 4 — HIGH (companion fix to FIX 3 — actually render the accounts)

**File:** `web/app.js`
**Problem:** `loadReplizData()` only sets a text label. It never renders individual account rows into `accountsList`.

**FIND** (exact block, the full `loadReplizData` function):

```javascript
async function loadReplizData() {
    try {
        if (!aiView.fields.accountsTitle) return;
        aiView.fields.accountsTitle.textContent = 'Loading Accounts...';
        const stats = await window.pywebview.api.get_account_stats();
        if (stats.error) {
             aiView.fields.accountsTitle.textContent = 'Failed to load accounts';
             return;
        }
        aiView.fields.accountsTitle.textContent = `${stats.campaigns} Account Connected`;
    } catch (e) {
        if (aiView.fields.accountsTitle) aiView.fields.accountsTitle.textContent = 'Error loading accounts';
    }
}
```

**REPLACE with:**

```javascript
async function loadReplizData() {
    try {
        if (!aiView.fields.accountsTitle) return;
        aiView.fields.accountsTitle.textContent = 'Loading Accounts...';
        const stats = await window.pywebview.api.get_account_stats();
        if (stats.error) {
             aiView.fields.accountsTitle.textContent = 'Failed to load accounts';
             if (aiView.fields.accountsList) aiView.fields.accountsList.innerHTML = '';
             return;
        }
        aiView.fields.accountsTitle.textContent = `${stats.campaigns} Account Connected`;

        if (aiView.fields.accountsList) {
            aiView.fields.accountsList.innerHTML = '';
            const res = await window.pywebview.api.get_repliz_accounts();
            if (res && res.status === 'ok' && res.accounts.length > 0) {
                res.accounts.forEach(acc => {
                    const row = document.createElement('div');
                    row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:#1A231A;border-radius:6px;';
                    row.innerHTML = `
                        <span style="font-size:13px;color:#E4E4E7;">${acc.name}</span>
                        <span style="font-size:11px;color:#A1A1AA;text-transform:capitalize;">${acc.type}</span>
                    `;
                    aiView.fields.accountsList.appendChild(row);
                });
            } else {
                aiView.fields.accountsList.innerHTML = '<div style="font-size:12px;color:#71717A;padding:8px 0;">No accounts connected yet.</div>';
            }
        }
    } catch (e) {
        if (aiView.fields.accountsTitle) aiView.fields.accountsTitle.textContent = 'Error loading accounts';
    }
}
```

---

## FIX 5 — MEDIUM (dashboard shows "undefined" counters)

**File:** `web/components/dashboard.js`
**Problem:** `accStats.tiktok_count`, `accStats.youtube_count`, `accStats.instagram_count` were referenced but never returned by the backend before. FIX 1 above already adds these fields to `get_account_stats()`. No code change is needed in `dashboard.js` itself — do NOT edit this file for this fix. This item exists only so you understand FIX 1 also resolves it. Confirm during testing (see checklist) that these three counters show real numbers instead of "undefined" after FIX 1 is applied.

---

## Do NOT do these things

- Do not invent a fake Repliz "campaigns" API. It does not exist publicly. `get_campaigns()` returning `[]` is the correct, honest fix.
- Do not change the `limit` value logic beyond what's shown (50 is intentional, matches the reference implementation in `dialogs/repliz_upload.py`).
- Do not add pagination handling, retries, caching, or any feature not explicitly listed above.
- Do not change `upload_clip()`, `ReplizUploaderAdapter`, or anything in `dialogs/repliz_upload.py` — they already work correctly.
- Do not change `stock-clip.js` — it already expects the correct `{"status": "ok", "accounts": [...]}` contract; FIX 1 makes the backend match what it already expects.

## Verification checklist (run through this after applying all fixes, report pass/fail for each)

1. Open Settings → Repliz panel. Enter valid `access_key`/`secret_key`, click Test Connection → should succeed, and the account list panel should now show real connected accounts (name + platform type), not stay empty.
2. Click "Connect More" → should open `https://dashboard.repliz.com` in the default browser, no console error.
3. Go to Dashboard → the account/campaign counter and the TikTok/YouTube/Instagram counters should show real numbers, not "undefined".
4. Go to the clips/upload screen, select platform "Repliz" → the account dropdown should populate with real account names instead of "Failed to load".
5. Select an account, click Upload on a clip → upload should proceed (success or a real API error), NOT the "Please select a Repliz account first" alert.
6. Confirm no other file besides the 4 listed in Scope lock was modified (`git diff --stat`).

## Output format

Output the full modified content of each of the 4 files you touched, one per code block, clearly labeled with the filename. Then output the result of the 6-item verification checklist above (mark each PASS/FAIL/UNTESTED and explain why if FAIL or UNTESTED — e.g. "UNTESTED: no live Repliz API key available in this environment").
