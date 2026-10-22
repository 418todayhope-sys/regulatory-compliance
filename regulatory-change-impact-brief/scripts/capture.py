"""Capture Stage 02 only; transport success never establishes legal suitability."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from http.client import HTTPException
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from scope import ROOT, validate
import registers

NAMES = {"LAW", "OJ", "AMEND", "CONSOLIDATED", "TIME", "FAQ", "POLICY", "SYSTEMS", "EVIDENCE", "CALENDAR"}
LIMIT = 8 * 1024 * 1024
OFFICIAL_HTML = {
    "OJ": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689",
    "AMEND": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202601744",
    "CONSOLIDATED": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727",
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.title_complete = False
        self.password = False
        self.text = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "title" and not self.title_complete:
            self.in_title = True
        attrs = dict(attrs)
        if tag == "input" and attrs.get("type", "").lower() == "password":
            self.password = True

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            if self.in_title:
                self.title_complete = True
            self.in_title = False

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)
        if self.in_title:
            self.title += data


def load_config(path, root, predecessor):
    raw = path.read_bytes()
    config = json.loads(raw)
    if config.get("official_html_fallbacks") != OFFICIAL_HTML:
        raise ValueError("Use the documented exact official HTML fallbacks")
    if set(config["sources"]) != NAMES:
        raise ValueError("Configuration must name exactly the ten interview sources")
    interview = root / config["interview"]
    body = interview.read_bytes()
    basis = next(r for r in predecessor["state"]["evidence_records"] if r["id"] == "e-interview")
    if digest(body) != basis["sha256"]:
        raise ValueError("Interview differs from the Stage 01 evidence binding")
    found = {}
    for name, url in re.findall(r"\[([A-Z]+)\]\((https://[^\s)]+)\)", body.decode("utf-8")):
        found.setdefault(name, set()).add(url)
    routes = []
    for name, role in config["sources"].items():
        urls = found.get(name, set())
        if len(urls) != 1:
            raise ValueError(f"Missing or ambiguous interview route: {name}")
        routes.append((name, next(iter(urls)), role))
    return routes, {"path": str(path), "sha256": digest(raw),
                    "interview_path": config["interview"], "interview_sha256": digest(body)}


def fetch(url, timeout):
    request = Request(url, headers={"User-Agent": "ProjectB-SourceCapture/0.1", "Cache-Control": "no-cache"})
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as error:
        response = error
    with response:
        return {"body": response.read(LIMIT + 1), "status": response.code,
                "url": response.geturl(), "headers": dict(response.headers.items())}


def legal_identity(name, page, final_url):
    """Match visible document identifiers/dates, not HTTP success or navigation titles."""
    text = re.sub(r"\s+", " ", " ".join(page.text)).strip()
    if urlsplit(final_url).hostname != "eur-lex.europa.eu" or urlsplit(final_url).scheme != "https":
        return None
    regulation = "2026/1744" if name == "AMEND" else "2024/1689"
    heading = re.search(r"REGULATION\s*\(EU\)\s*" + re.escape(regulation) +
                        r"\s+OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL", text, re.I)
    article = re.search(r"Article\s+1\b", text, re.I)
    if name == "CONSOLIDATED":
        version = re.search(r"02024R1689\s*[—–-]\s*EN\s*[—–-]\s*27\.07\.2026\s*[—–-]\s*(\d{3}\.\d{3})", text)
        if heading and article and version:
            return {"document_id": "02024R1689-20260727", "document_version": version.group(0),
                    "consolidation_date": "2026-07-27", "effective_date": None}
    else:
        adoption = "8 July 2026" if name == "AMEND" else "13 June 2024"
        publication = "24.7.2026" if name == "AMEND" else "12.7.2024"
        if heading and article and adoption in text and publication in text:
            return {"document_id": "32026R1744" if name == "AMEND" else "32024R1689",
                    "document_version": "original Official Journal publication",
                    "adoption_date": "2026-07-08" if name == "AMEND" else "2024-06-13",
                    "publication_date": "2026-07-24" if name == "AMEND" else "2024-07-12",
                    "effective_date": None}
    return None


def attempt(name, url, role, directory, timeout, transport, original_url=None, number=1, route_type=None):
    original_url = original_url or url
    record = {"id": f"source-{name.lower()}-{number:02}", "source_name": name,
              "summary": f"Live attempt for {name}; document suitability remains unverified.",
              "evidence_ids": ["e-interview"], "source_role": role, "authority": "unknown",
              "locator": original_url, "original_url": original_url, "requested_url": url,
              "attempt_number": number, "route_type": route_type or ("original" if number == 1 else "official-html-fallback"),
              "final_url": None, "http_status": None,
              "observed_identity": {"title": None, "expected_source": name},
              "retrieved_at": now(), "retrieval_status": "unavailable",
              "content_type": "unknown", "version_metadata": None,
              "content_hash": None, "local_reference": None,
              "identity_status": "unverified", "review_date_suitability": "unverified",
              "failure": None, "used_for_conclusions": False}
    try:
        result = transport(url, timeout)
    except (URLError, TimeoutError, OSError, HTTPException) as error:
        # Avoid storing exception text which may contain proxy credentials.
        record["failure"] = {"type": type(error).__name__, "reason": "Network/TLS/timeout failure; no complete response obtained",
                             "next_owner": "Runtime/source access operator", "recovery": "Restore access; capture in a fresh destination"}
        record["completed_at"] = now()
        return record
    headers = {k.lower(): v for k, v in result["headers"].items()}
    body = result["body"]
    record.update({"http_status": result["status"], "final_url": result["url"],
                   "content_type": headers.get("content-type", "application/octet-stream"),
                   "version_metadata": {"etag": headers.get("etag"), "last_modified": headers.get("last-modified"),
                                        "document_version": None, "effective_date": None,
                                        "note": "HTTP validators are not verified document versions"}})
    page = Page()
    if "html" in record["content_type"].lower():
        page.feed(body.decode("utf-8", errors="replace"))
    record["observed_identity"] = {"title": page.title.strip() or None,
                                   "returned_url": result["url"], "expected_source": name}
    login = (page.password or urlsplit(result["url"]).hostname in {"accounts.google.com", "login.microsoftonline.com"}
             or bool(re.search(r"sign[ -]?in|log[ -]?in|access denied|just a moment|notion\s*$", page.title, re.I)))
    if body:
        target = directory / (f"{name.lower()}-{number:02}.response")
        with target.open("xb") as output:
            output.write(body)
        record.update({"content_hash": digest(body), "local_reference": str(target),
                       "capture_locator": f"response bytes 0..{len(body)-1}", "byte_count": len(body)})
    if result["status"] != 200 or login or not body or len(body) > LIMIT:
        record["retrieval_status"] = "invalid"
        reason = ("Login/access/challenge or landing page" if login else
                  "HTTP response is not 200" if result["status"] != 200 else
                  "Response exceeds capture limit; retained prefix only" if len(body) > LIMIT else "Empty response")
        record["failure"] = {"type": "UnsuitableResponse", "reason": reason,
                             "next_owner": "Source access operator", "recovery": "Obtain intended document through disclosed route"}
    else:
        record["retrieval_status"] = "unverified"
        # Retained bytes are evidence of the response, not proof it is the requested document.
        if name in OFFICIAL_HTML:
            identity = legal_identity(name, page, result["url"])
            if identity:
                record["identity_status"] = "verified"
                record["retrieval_status"] = "retrieved"
                record["observed_identity"].update(identity)
                record["version_metadata"].update(identity)
                record["identity_verification"] = "Official hostname, visible regulation heading, Article 1 and expected publication/consolidation date"
                record["summary"] = f"{name} document identity/version matched; legal applicability remains unverified."
            else:
                record["identity_verification"] = "Required official document heading/date/version not established"
    record["completed_at"] = now()
    return record


def extract_register(record, tabs, directory):
    if record["retrieval_status"] in {"invalid", "unavailable"} or not record["local_reference"]:
        return []
    name = record["source_name"]
    raw = Path(record["local_reference"]).read_bytes()
    if digest(raw) != record["content_hash"]:
        raise ValueError("Captured register hash mismatch")
    try:
        tables, discovered = registers.extract(name, raw, record["content_type"], tabs)
    except (ValueError, UnicodeError, registers.csv.Error) as error:
        tables = [registers.table(name, [], tabs[0]["gid"], tabs[0]["name"])]
        tables[0]["errors"].append(type(error).__name__ + ": malformed table response")
        discovered = []
    if not tables:
        tables = [registers.table(name, [], tabs[0]["gid"], tabs[0]["name"])]
    for index, table in enumerate(tables):
        if {"gid": table["gid"], "name": table["tab_name"]} not in tabs:
            table["errors"].append("Exposed grid/tab identity is not a configured verified tab; review required")
            table["valid"] = False
        table.update({"id": f"table-{record['id']}-{index}", "summary": f"{name} source-reported register rows; no independent corroboration or approval.",
                      "evidence_ids": [record["id"]], "source_name": name,
                      "workbook_id": registers.workbook_id(record["original_url"]),
                      "original_url": record["original_url"], "requested_url": record["requested_url"],
                      "retrieval_url": record["final_url"], "retrieved_at": record["retrieved_at"],
                      "raw_reference": record["local_reference"], "raw_sha256": record["content_hash"],
                      "discovered_tabs": discovered, "tab_discovery_limitation": registers.LIMITATION,
                      "independently_corroborated": False, "approval_verified": False,
                      "format": "csv" if "csv" in record["content_type"].lower() else "html-grid"})
        target = directory / (table["id"] + ".json")
        data = (json.dumps(table, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        with target.open("xb") as output:
            output.write(data)
        table.update({"extracted_reference": str(target), "extracted_sha256": digest(data)})
    return tables


def manual_reference(config_path, root, policy_url):
    path = json.loads(config_path.read_bytes()).get("manual_policy_reference")
    if not path:
        return []
    raw = (root / path).read_bytes()
    text = raw.decode("utf-8")
    def claimed(pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else None
    return [{"id": "manual-policy-reference", "summary": "User-disclosed manual POLICY reference; not a live Notion capture or independently authenticated export.",
             "evidence_ids": ["e-interview"], "path": path, "sha256": digest(raw),
             "provenance_type": "user-supplied-manual-reference", "original_url": policy_url,
             "recorded_at": now(), "manual_retrieved_at": None, "manual_retriever": None,
             "provenance_verification": "unverified", "live_retrieval": False,
             "claimed_policy_version": claimed(r"Policy version: `([^`]+)`"),
             "claimed_context_revision": claimed(r"Context revision: `([^`]+)`"),
             "used_for_conclusions": False}]


def capture(stage01, config_path, destination, root=ROOT, transport=fetch, timeout=15, output_path=None):
    if output_path is not None and output_path.exists():
        raise FileExistsError(output_path)
    raw = stage01.read_bytes()
    previous = json.loads(raw)
    validate(previous, root)
    if previous["stage"] != "scope" or previous["sequence"] != 1:
        raise ValueError("Predecessor must be Stage 01")
    if "e-interview" not in previous["produced_record_ids"]:
        raise ValueError("Stage 01 must produce interview evidence")
    routes, config_binding = load_config(config_path, root, previous)
    tab_config = json.loads(config_path.read_bytes())["register_tabs"]
    if set(tab_config) != set(registers.HEADERS) or any(not tabs or len({t['gid'] for t in tabs}) != len(tabs) for tabs in tab_config.values()):
        raise ValueError("Explicit nonempty, unique register tab IDs required")
    manual = manual_reference(config_path, root, next(u for n,u,r in routes if n == "POLICY"))
    # An exclusive destination prevents overwriting either snapshots or evidence,
    # including concurrent invocations. Reruns never reuse an old source directory.
    destination.mkdir(parents=True, exist_ok=False)
    output = output_path or destination / "snapshots/02-source-capture.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir = destination / "sources"
    evidence_dir.mkdir()
    records = []
    tables = []
    selected = {}
    for name, url, role in routes:
        for number, actual_url in enumerate([url] + ([OFFICIAL_HTML[name]] if name in OFFICIAL_HTML else []), 1):
            record = attempt(name, actual_url, role, evidence_dir, timeout, transport, original_url=url, number=number)
            records.append(record)
            if name in registers.HEADERS:
                tables.extend(extract_register(record, tab_config[name], evidence_dir))
            # Preserve each attempt before trying its fallback or another source.
            with (evidence_dir / (f"{name.lower()}-{number:02}.attempt.json")).open("x", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2)
            print(f"{name} attempt {number}: {record['retrieval_status']} HTTP {record.get('http_status')}", flush=True)
            if record["identity_status"] == "verified":
                selected[name] = record["id"]
                break
        if name in registers.HEADERS:
            for number, tab in enumerate(tab_config[name], 2):
                export = registers.csv_url(url, tab["gid"])
                record = attempt(name, export, role, evidence_dir, timeout, transport, original_url=url, number=number, route_type="per-tab-csv-export")
                record.update({"workbook_id": registers.workbook_id(url), "gid": tab["gid"], "tab_name": tab["name"]})
                records.append(record)
                tables.extend(extract_register(record, [tab], evidence_dir))
                with (evidence_dir / f"{name.lower()}-{number:02}.attempt.json").open("x", encoding="utf-8") as handle:
                    json.dump(record, handle, indent=2)
                print(f"{name} CSV gid={tab['gid']}: {record['retrieval_status']} HTTP {record.get('http_status')}", flush=True)
    if stage01.read_bytes() != raw:
        raise ValueError("Stage 01 changed during capture; retained attempts, no snapshot published")
    blocker = {"id": "u-capture-authority", "summary": "Document identity checks do not establish applicable legal authority or review-date suitability; dependent conclusions remain blocked.",
               "evidence_ids": [r["id"] for r in records if r["source_name"] in {"LAW", "OJ", "AMEND", "CONSOLIDATED", "TIME", "FAQ"}],
               "owner": "Legal / source access operator", "resolution_need": "Verify captured documents and date-appropriate legal basis before dependent conclusions."}
    decision = {"id": "d-capture-status", "summary": "Separate captured HTTP responses from verified legal and business evidence.",
                "evidence_ids": [r["id"] for r in records], "concern": "Avoid treating a successful HTTP request as document verification.",
                "options": ["Retain bytes with unverified identity/version", "Assume HTTP success establishes suitability"],
                "chosen_behavior": "Verify legal document identity/version independently; keep applicability blocked and retain every attempt and manual provenance separately.",
                "rationale": "Capture alone cannot prove applicability or operational facts.",
                "tradeoffs": ["Conservative classification requires later document review even for useful responses."],
                "downstream_effect": "No system facts, legal conclusions or approvals are generated."}
    access_gaps = [{"id": "u-access-" + name.lower(), "summary": f"{name}: live document access/identity remains unresolved; manual references do not resolve access.",
                   "evidence_ids": [r["id"] for r in records if r["source_name"] == name],
                   "owner": "Operations / source access operator", "resolution_need": "Obtain and verify the live document through its legitimate route."}
                  for name in sorted(NAMES) if name not in selected and
                  (name in OFFICIAL_HTML or name == "POLICY" or
                   all(r["retrieval_status"] in {"invalid", "unavailable"} for r in records if r["source_name"] == name))]
    register_checks = registers.validate_relationships(tables)
    register_gap = {"id": "u-register-verification", "summary": "Downloaded register values are source-reported, not independently corroborated or proof of approval; tab completeness remains unverified.",
                    "evidence_ids": [t["id"] for t in tables], "owner": "System owners / Operations",
                    "resolution_need": "Review reported evidence gaps, tab inventory and any register validation errors; obtain underlying evidence separately.",
                    "validation_errors": register_checks["errors"]}
    snapshot = {"schema_version": previous["schema_version"], "snapshot_id": "snapshot-" + str(uuid4()),
                "run_id": previous["run_id"], "stage": "source-capture", "sequence": 2, "created_at": now(),
                "status": "blocked", "predecessor": {"snapshot_id": previous["snapshot_id"], "path": str(stage01), "sha256": digest(raw)},
                "consumed_record_ids": previous["produced_record_ids"],
                "produced_record_ids": [r["id"] for r in records + tables + manual + access_gaps] + [blocker["id"], decision["id"], register_gap["id"]],
                "state": {"sources": records, "as_of": previous["state"]["as_of"], "configuration": config_binding,
                          "selected_verified_documents": selected, "manual_references": manual,
                          "register_tables": tables, "register_validation": register_checks,
                          "legal_authority_status": "blocked", "system_ids": register_checks["system_ids"], "system_ids_status": "source-reported-unverified"},
                "unresolved": copy.deepcopy(previous["unresolved"]) + [blocker, register_gap] + access_gaps, "decisions": [decision]}
    validate(snapshot, root)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return output, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage01", type=Path, default=ROOT / "deliverables/snapshots/01-scope.json")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True, help="Fresh capture directory under deliverables/sources; must not exist")
    parser.add_argument("--output", type=Path, default=ROOT / "deliverables/snapshots/02-source-capture.json")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not destination.is_relative_to(ROOT / "deliverables/sources"):
        parser.error("CLI destination must be under deliverables/sources/")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    path, snapshot = capture(args.stage01.resolve(), args.config.resolve(), destination, timeout=args.timeout, output_path=args.output.resolve())
    print(f"Stage 02 schema-valid; review blocked: {path} (run {snapshot['run_id']})")


if __name__ == "__main__":
    main()
