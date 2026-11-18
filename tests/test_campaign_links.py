"""Offline contracts for link identity, Flight parsing, cache and mandatory assets."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from services.campaign_links import campaign_url, fetch_clippo, map_clippo, parse_clippo, _CACHE
from services.campaigns import CampaignMixin, normalize_campaign
from services.storage import WorkflowStore

ID = "cmtjkbbat06s17t26cxn7lk1k"
URL = "https://app.clippo.id/campaigns/" + ID


def fixture(**overrides):
    campaign = {"id": ID, "title": "Campaign contoh", "minDuration": 15, "maxDuration": 180,
                "hashtags": ["#contoh"], "platformSupported": [0, 1],
                "campaignTags": [{"platform": 0, "tags": ["akun_tt"]}, {"platform": 1, "tags": ["akun_ig"]}],
                "campaignPurpose": {"ops": [{"insert": "Kunjungi link di bio\n"}]},
                "campaignHook": {"ops": [{"insert": "Cerita pertama\nCerita kedua\n"}]},
                "requirementsV2": "$d", "campaignDos": ["Pakai footage asli"], "campaignDonts": ["Jangan bots"],
                "assetVideoUrlsV2": [{"url": "https://drive.google.com/drive/folders/example", "isRequired": True, "displayText": "FOOTAGE WAJIB"}],
                "creatorId": "never-retain", "adminNotes": "never-retain", "account_ids": ["never-retain"]}
    campaign.update(overrides)
    text = "<p>Campaign \U0001f680</p><p>Languages: Indonesia</p><p>contoh ]) di teks</p>"
    flight = "d:T" + format(len(text.encode()), "x") + "," + text
    flight += "8:" + json.dumps(["$", "$L1c", None, {"initialCampaign": campaign}], ensure_ascii=False) + "\n"
    pieces = [flight[:21], flight[21:70], flight[70:]]
    scripts = "".join("<script>self.__next_f.push(" + json.dumps([1, piece]).replace("<", "\\u003c") + ")</script>" for piece in pieces)
    return '<h1>Campaign contoh</h1><div data-section-id="brief-campaign">Durasi 15-180</div><div data-section-id="do-and-dont"><div><p>Aturan satu</p><p>Deskripsi satu</p></div></div>' + scripts


def response(status=200, body=None, headers=None):
    obj = MagicMock()
    obj.__enter__.return_value = obj
    obj.status_code = status
    obj.headers = headers or {"Content-Type": "text/html", "ETag": '"v1"'}
    obj.iter_content.return_value = [(body or fixture()).encode()]
    return obj


class Harness(CampaignMixin):
    def __init__(self, root):
        self.config_file = str(root / "config.json")
        self.cfg = {"campaigns": []}
        self.store = WorkflowStore(root / "workflow.sqlite3")

    def _get_cfg(self):
        return copy.deepcopy(self.cfg)

    def _get_cfg_manager(self):
        return self

    def save_config(self, cfg):
        self.cfg = copy.deepcopy(cfg)

    def _get_store(self):
        return self.store


class LinkParsingTests(unittest.TestCase):
    def test_identity_and_tracking_parameter_normalization(self):
        self.assertEqual(campaign_url(URL + "/?utm=test#brief"), (URL, ID))
        for bad in ["http://app.clippo.id/campaigns/" + ID, "https://127.0.0.1/" + ID,
                    "https://app.clippo.id.evil.test/campaigns/" + ID, "https://user:pass@app.clippo.id/campaigns/" + ID,
                    "https://app.clippo.id:8443/campaigns/" + ID, "https://app.clippo.id/campaigns/../" + ID]:
            with self.subTest(url=bad), self.assertRaises(ValueError):
                campaign_url(bad)

    def test_split_flight_unicode_text_and_literal_brackets(self):
        page = parse_clippo(fixture(), ID)
        extracted, links, meta = map_clippo(page)
        self.assertEqual(extracted["name"], "Campaign contoh")
        self.assertIn("Campaign \U0001f680", extracted["brief"]["catatan"])
        self.assertIn("]) di teks", extracted["brief"]["catatan"])
        self.assertEqual(extracted["language"], "id")
        self.assertEqual(extracted["brief"]["tagged_accounts_by_platform"], {"tiktok": ["akun_tt"], "instagram": ["akun_ig"]})
        self.assertEqual(extracted["brief"]["hooks"], ["Cerita pertama", "Cerita kedua"])
        self.assertEqual(len(extracted["aturan_umum"]), 1)
        self.assertTrue(links[0]["required"])
        self.assertNotIn("never-retain", meta["brief_text"])

    def test_other_campaign_must_not_fall_back_to_ai(self):
        with self.assertRaisesRegex(ValueError, "ID campaign"):
            parse_clippo(fixture(id="another_campaign_id"), ID)

    def test_login_wall_and_incompatible_schema_are_detected(self):
        with self.assertRaisesRegex(ValueError, "brief publik"):
            parse_clippo('<html><h1>Login</h1></html>', ID)
        for value in [None, "15", True]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Schema"):
                parse_clippo(fixture(minDuration=value), ID)

    def test_scoped_html_fallback_is_marked_and_excludes_scripts(self):
        body = fixture().split("<script>")[0] + '<script>secretPrompt="publish"</script>'
        page = parse_clippo(body, ID)
        self.assertEqual(page["method"], "html_ai")
        self.assertIsNone(page["data"])
        self.assertNotIn("publish", page["brief_text"])

    def test_missing_flight_reference_is_not_silently_imported(self):
        with self.assertRaisesRegex(ValueError, "Referensi"):
            parse_clippo(fixture(campaignPurpose="$eee"), ID)

    def test_layout_change_preserves_json_and_reports_missing_general_rules(self):
        page = parse_clippo(fixture().replace('data-section-id="do-and-dont"', 'data-section-id="renamed"'), ID)
        self.assertEqual(page["data"]["title"], "Campaign contoh")
        self.assertEqual(page["general_rules"], [])
        self.assertTrue(page["warnings"])

    def test_unknown_platform_is_preserved_without_guessing(self):
        extracted, _, metadata = map_clippo(parse_clippo(fixture(platformSupported=[0, 55]), ID))
        self.assertEqual(extracted["brief"]["platforms"], ["tiktok"])
        self.assertEqual(metadata["unmapped_platforms"], [55])

    def test_next_data_variant_and_initial_campaign_reference(self):
        campaign = {"id": ID, "title": "Pages Router", "minDuration": 15, "maxDuration": 60}
        visible = fixture().split("<script>")[0]
        body = visible + '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({"props": {"pageProps": {"initialCampaign": campaign}}}) + '</script>'
        self.assertEqual(parse_clippo(body, ID)["data"]["title"], "Pages Router")
        flight = '1:' + json.dumps({"initialCampaign": "$2"}) + '\n2:' + json.dumps(campaign) + '\n'
        body = visible + '<script>self.__next_f.push(' + json.dumps([1, flight]) + ')</script>'
        self.assertEqual(parse_clippo(body, ID)["data"]["title"], "Pages Router")


class LinkFetchTests(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()

    def test_cache_avoids_network_and_returns_independent_copy(self):
        with patch("requests.get", return_value=response()) as get:
            first = fetch_clippo(URL)
            first["data"]["title"] = "Changed by caller"
            second = fetch_clippo(URL)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(second["data"]["title"], "Campaign contoh")
        get.assert_called_once()
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_refresh_uses_conditional_request_and_304(self):
        with patch("requests.get", side_effect=[response(), response(304)]) as get:
            first = fetch_clippo(URL)
            second = fetch_clippo(URL, refresh=True)
        self.assertEqual(second["data"], first["data"])
        self.assertEqual(get.call_args.kwargs["headers"]["If-None-Match"], '"v1"')

    def test_redirect_or_auth_wall_never_followed(self):
        for code in [302, 401, 403, 404]:
            with self.subTest(code=code), patch("requests.get", return_value=response(code)) as get, self.assertRaises(ValueError):
                fetch_clippo(URL)
            get.assert_called_once()

    def test_url_validation_happens_before_network(self):
        with patch("requests.get") as get, self.assertRaises(ValueError):
            fetch_clippo("https://localhost/private")
        get.assert_not_called()

    def test_body_size_limit(self):
        with patch("requests.get", return_value=response(body="x" * (2 * 1024 * 1024 + 1))), self.assertRaisesRegex(ValueError, "2 MB"):
            fetch_clippo(URL)


class LinkBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        self.page = parse_clippo(fixture(), ID)
        self.page.update(url=URL, campaign_id=ID, adapter_version=1, fetched_at="2026-10-07T00:00:00Z", cache_hit=False)

    def tearDown(self):
        self.tmp.cleanup()

    def import_link(self, existing=None):
        with patch("services.campaign_links.fetch_clippo", return_value=self.page), patch.object(self.api, "_campaign_ai_source") as ai:
            result = self.api.extract_campaign_link(URL, existing)
            ai.assert_not_called()
        return result

    def test_json_import_needs_no_ai_and_does_not_save(self):
        result = self.import_link()
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(self.api.cfg["campaigns"], [])
        self.assertEqual(result["provenance"]["name"][0]["source_url"], URL)
        self.assertIn("audience_scope", result["missing"])
        self.assertNotIn("account_ids", result["extracted"])

    def test_user_values_preserved_and_conflicts_retained(self):
        result = self.import_link({"name": "Manual", "brief": {"durasi_max": 60}})
        self.assertEqual(result["extracted"]["name"], "Manual")
        self.assertEqual(result["extracted"]["brief"]["durasi_max"], 60)
        self.assertEqual(len(result["conflicts"]), 2)

    def test_required_remote_material_blocks_until_local_file_is_required(self):
        result = self.import_link()
        payload = {**result["extracted"], "source_url": URL, "source_links": result["source_links"], "external_campaign": result["external_campaign"]}
        saved = self.api.save_campaign_workspace(None, payload)
        self.assertEqual(saved["status"], "ok", saved)
        self.assertTrue(any("Materi tautan wajib" in msg for msg in saved["readiness"]["production_blockers"]))
        video = self.root / "local.mp4"
        video.write_bytes(b"fixture video")
        asset = self.api._inspect_campaign_file({"path": str(video), "role": "video", "required": True})
        payload["assets"] = [asset]
        payload["source_links"][0]["asset_id"] = asset["id"]
        ready = self.api.save_campaign_workspace(saved["campaign"]["id"], payload)
        self.assertEqual(ready["status"], "ok", ready)
        self.assertFalse(any("Materi tautan wajib" in msg for msg in ready["readiness"]["production_blockers"]))
        self.assertEqual(ready["campaign"]["source_url"], URL)

    def test_unsafe_source_link_cannot_be_saved(self):
        with self.assertRaisesRegex(ValueError, "HTTP/HTTPS"):
            normalize_campaign({"source_links": [{"url": "javascript:alert(1)"}]})


if __name__ == "__main__":
    unittest.main()
