import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import capture


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stage01 = capture.ROOT / "deliverables/snapshots/01-scope.json"
        self.config = capture.ROOT / "regulatory-change-impact-brief/references/source-config.json"

    def response(self, url, timeout):
        return {"body": b"<html><title>Article 50</title><p>Controlled test only</p></html>",
                "status": 200, "url": url, "headers": {"Content-Type": "text/html", "ETag": "test-version"}}

    def test_provenance_hashes_and_predecessor(self):
        calls = []
        def transport(url, timeout):
            calls.append(url)
            return self.response(url, timeout)
        path, result = capture.capture(self.stage01, self.config, self.base / "first", transport=transport)
        previous = json.loads(self.stage01.read_bytes())
        self.assertEqual(result["run_id"], previous["run_id"])
        self.assertEqual(result["predecessor"]["sha256"], capture.digest(self.stage01.read_bytes()))
        self.assertEqual(result["predecessor"]["snapshot_id"], previous["snapshot_id"])
        self.assertEqual(set(result["consumed_record_ids"]), set(previous["produced_record_ids"]))
        self.assertEqual(len(calls), 16)
        self.assertEqual(len(set(calls)), 16)
        self.assertEqual(result["status"], "blocked")
        capture.validate(json.loads(path.read_text()))
        for source in result["state"]["sources"]:
            self.assertEqual(source["content_hash"], capture.digest(Path(source["local_reference"]).read_bytes()))
            self.assertEqual(source["retrieval_status"], "unverified")
            self.assertIsNone(source["version_metadata"]["document_version"])
            self.assertIsNone(source["version_metadata"]["effective_date"])
        self.assertEqual(result["state"]["system_ids"], [])
        with self.assertRaises(FileExistsError):
            capture.capture(self.stage01, self.config, self.base / "first", transport=transport)
        self.assertEqual(len(calls), 16)

    def test_failures_do_not_skip_any_source_or_invent_content(self):
        calls = []
        def failure(url, timeout):
            calls.append(url)
            raise URLError("controlled failure")
        _, result = capture.capture(self.stage01, self.config, self.base / "failed", transport=failure)
        self.assertEqual(len(calls), 16)
        for source in result["state"]["sources"]:
            self.assertEqual(source["retrieval_status"], "unavailable")
            self.assertIsNone(source["local_reference"])
            self.assertIsNone(source["content_hash"])
            self.assertIsNotNone(source["failure"])

    def test_login_error_and_empty_pages_are_not_documents(self):
        for index, (status, title, body, url) in enumerate([
            (200, "Sign in", b"<input type='password'>", "https://accounts.google.com/"),
            (403, "Denied", b"Access denied", "https://example.com"),
            (200, "", b"", "https://example.com"),
            (200, "Just a moment", b"Challenge", "https://example.com"),
            (200, "Notion", b"Landing page", "https://example.com"),
        ]):
            directory = self.base / str(index)
            directory.mkdir()
            data = (f"<title>{title}</title>".encode() + body) if title else body
            def response(original, timeout):
                return {"status": status, "url": url, "body": data, "headers": {"Content-Type": "text/html"}}
            result = capture.attempt("LAW", "https://example.com", "official-guidance", directory, 1, response)
            self.assertEqual(result["retrieval_status"], "invalid")
            if data:
                self.assertEqual(Path(result["local_reference"]).read_bytes(), data)

    def test_exact_routes_and_interview_binding(self):
        previous = json.loads(self.stage01.read_bytes())
        routes, _ = capture.load_config(self.config, capture.ROOT, previous)
        self.assertEqual(dict((n, u) for n, u, r in routes)["AMEND"],
                         "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL_202601744")
        previous["state"]["evidence_records"][1]["sha256"] = "sha256:" + "0" * 64
        with self.assertRaises(ValueError):
            capture.load_config(self.config, capture.ROOT, previous)

    def test_new_destination_makes_fresh_attempts_and_snapshot_id(self):
        first = capture.capture(self.stage01, self.config, self.base / "one", transport=self.response)[1]
        second = capture.capture(self.stage01, self.config, self.base / "two", transport=self.response)[1]
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertNotEqual(first["state"]["sources"][0]["local_reference"], second["state"]["sources"][0]["local_reference"])

    def test_existing_snapshot_refused_before_network(self):
        output = self.base / "existing.json"
        output.write_text("preserve me")
        with self.assertRaises(FileExistsError):
            capture.capture(self.stage01, self.config, self.base / "unused", transport=self.response, output_path=output)
        self.assertFalse((self.base / "unused").exists())
        self.assertEqual(output.read_text(), "preserve me")

    def test_navigation_login_icon_does_not_turn_document_into_login_page(self):
        page = capture.Page()
        page.feed("<title>Regulation 2024/1689</title><svg><title>Log in</title></svg>")
        self.assertEqual(page.title, "Regulation 2024/1689")
        directory = self.base / "document"
        directory.mkdir()
        response = self.response("https://example.com", 1)
        response["body"] = b"<title>Regulation</title><svg><title>Log in</title></svg>"
        record = capture.attempt("OJ", "https://example.com", "binding-regulation", directory, 1, lambda u,t: response)
        self.assertEqual(record["retrieval_status"], "unverified")

    def legal_response(self, name, url):
        regulation = "2026/1744" if name == "AMEND" else "2024/1689"
        dates = {"OJ": "13 June 2024 12.7.2024", "AMEND": "8 July 2026 24.7.2026",
                 "CONSOLIDATED": "02024R1689 — EN — 27.07.2026 — 001.001"}
        body = (f"<html><title>Official document</title><h1>REGULATION (EU) {regulation} "
                f"OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL</h1><p>{dates[name]}</p>"
                "<h2>Article 1</h2><p>Controlled identity fixture, not legal evidence.</p></html>").encode()
        return {"status": 200, "url": url, "body": body, "headers": {"Content-Type": "text/html"}}

    def test_fallback_original_first_and_preserved_attempts(self):
        calls = []
        def transport(url, timeout):
            calls.append(url)
            for name, fallback in capture.OFFICIAL_HTML.items():
                if url == fallback:
                    return self.legal_response(name, url)
            response = self.response(url, timeout)
            response.update(status=202, body=b"blocked original")
            return response
        _, snapshot = capture.capture(self.stage01, self.config, self.base / "fallback", transport=transport)
        self.assertEqual(len(calls), 16)
        self.assertEqual(len(snapshot["state"]["selected_verified_documents"]), 3)
        for name, fallback in capture.OFFICIAL_HTML.items():
            attempts = [r for r in snapshot["state"]["sources"] if r["source_name"] == name]
            original, alternative = attempts
            self.assertEqual(calls.index(fallback), calls.index(original["requested_url"]) + 1)
            self.assertEqual(original["retrieval_status"], "invalid")
            self.assertEqual(alternative["retrieval_status"], "retrieved")
            self.assertEqual(alternative["identity_status"], "verified")
            self.assertEqual(alternative["review_date_suitability"], "unverified")
            self.assertEqual(alternative["original_url"], original["requested_url"])
            self.assertEqual(alternative["final_url"], fallback)
            self.assertNotEqual(original["id"], alternative["id"])
            self.assertNotEqual(original["local_reference"], alternative["local_reference"])
            for attempt in attempts:
                self.assertEqual(capture.digest(Path(attempt["local_reference"]).read_bytes()), attempt["content_hash"])
                self.assertIn("completed_at", attempt)
        self.assertEqual(snapshot["state"]["legal_authority_status"], "blocked")

    def test_verified_original_does_not_request_fallback(self):
        previous = json.loads(self.stage01.read_bytes())
        routes, _ = capture.load_config(self.config, capture.ROOT, previous)
        lookup = {url: name for name, url, role in routes}
        calls = []
        def transport(url, timeout):
            calls.append(url)
            name = lookup[url.split("/export?")[0]]
            return self.legal_response(name, url) if name in capture.OFFICIAL_HTML else self.response(url, timeout)
        _, result = capture.capture(self.stage01, self.config, self.base / "originals", transport=transport)
        self.assertEqual(len(calls), 13)
        self.assertEqual(len(result["state"]["selected_verified_documents"]), 3)

    def test_wrong_identity_version_origin_and_script_only_are_not_verified(self):
        url = capture.OFFICIAL_HTML["CONSOLIDATED"]
        good = self.legal_response("CONSOLIDATED", url)
        cases = [
            (good["body"].replace(b"27.07.2026", b"12.07.2024"), url),
            (good["body"].replace(b"2024/1689", b"2024/9999"), url),
            (good["body"], "https://example.com/document"),
            (b"<script>" + good["body"] + b"</script>", url),
        ]
        for index, (body, returned_url) in enumerate(cases):
            directory = self.base / f"bad-{index}"
            directory.mkdir()
            response = dict(good, body=body, url=returned_url)
            result = capture.attempt("CONSOLIDATED", url, "binding-regulation", directory, 1, lambda u,t: response)
            self.assertNotEqual(result["identity_status"], "verified")
            self.assertNotEqual(result["retrieval_status"], "retrieved")
            self.assertIsNone(result["version_metadata"]["document_version"])

    def test_manual_policy_remains_separate_and_does_not_resolve_live_failure(self):
        def failure(url, timeout):
            raise URLError("controlled failure")
        _, result = capture.capture(self.stage01, self.config, self.base / "manual", transport=failure)
        manual = result["state"]["manual_references"][0]
        self.assertFalse(manual["live_retrieval"])
        self.assertIsNone(manual["manual_retrieved_at"])
        self.assertIsNone(manual["manual_retriever"])
        self.assertEqual(manual["claimed_policy_version"], "AI-POL-2026-08-15")
        self.assertEqual(manual["sha256"], capture.digest((capture.ROOT / manual["path"]).read_bytes()))
        policy = [r for r in result["state"]["sources"] if r["source_name"] == "POLICY"]
        self.assertEqual(len(policy), 1)
        self.assertEqual(policy[0]["retrieval_status"], "unavailable")
        self.assertIsNone(policy[0]["content_hash"])
        self.assertIn("u-access-policy", [r["id"] for r in result["unresolved"]])
