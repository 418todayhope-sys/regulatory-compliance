"""Stage 02 table extraction only: source-reported values are not corroboration."""
import csv
from html.parser import HTMLParser
import io
import re
from urllib.parse import urlsplit

HEADERS = {
    "SYSTEMS": "system_id system_name use_case owner provider_role deployer_role exposed_group output_type current_notice human_review evidence_status evidence_updated_at record_version".split(),
    "EVIDENCE": "record_id system_id record_type reported_at owner status evidence_ref evidence_state notes".split(),
    "CALENDAR": "action_id system_id action owner due_date status approval_required source_version".split(),
}
TABS = {"SYSTEMS": "AI System Register", "EVIDENCE": "Incident Evidence Register", "CALENDAR": "Compliance Calendar"}
COUNTS = {"SYSTEMS": 8, "CALENDAR": 8}
LIMITATION = "Only exposed HTML grids/tab captions and explicitly configured gids are inspected; hidden/unexposed tabs and workbook completeness are not established."


class Grids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.divs = []
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.table_depth = 0
        self.captions = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.divs.append(attrs)
            if "docs-sheet-tab-caption" in attrs.get("class", "").split():
                self.captions.append("")
        if tag == "table":
            self.table_depth += 1
            if "waffle" in attrs.get("class", "").split():
                gids = [re.fullmatch(r"(\d+)-grid-container", d.get("id", "")) for d in self.divs]
                gid = next((m.group(1) for m in reversed(gids) if m), None)
                self.table = {"gid": gid, "rows": [], "depth": self.table_depth}
                self.tables.append(self.table)
        if self.table and self.table_depth == self.table["depth"]:
            if tag == "tr":
                self.row = []
            if tag == "td" and self.row is not None:
                self.cell = ""

    def handle_data(self, value):
        if self.cell is not None:
            self.cell += value
        if self.divs and "docs-sheet-tab-caption" in self.divs[-1].get("class", "").split():
            self.captions[-1] += value

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        if tag == "tr" and self.table and self.row is not None:
            if self.row:
                self.table["rows"].append(self.row)
            self.row = None
        if tag == "table":
            if self.table and self.table_depth == self.table["depth"]:
                self.table = None
            self.table_depth -= 1
        if tag == "div" and self.divs:
            self.divs.pop()


def workbook_id(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/spreadsheets/d/([^/]+)(?:/.*)?", parsed.path)
    if parsed.scheme != "https" or parsed.hostname != "docs.google.com" or not match:
        raise ValueError("Expected disclosed HTTPS Google spreadsheet URL")
    return match.group(1)


def csv_url(original, gid):
    if not str(gid).isdigit():
        raise ValueError("gid must be a numeric tab ID")
    return f"https://docs.google.com/spreadsheets/d/{workbook_id(original)}/export?format=csv&gid={gid}"


def table(name, rows, gid, tab_name):
    errors = []
    if not rows:
        return {"headers": [], "records": [], "record_ids": [], "record_count": 0,
                "gid": gid, "tab_name": tab_name, "errors": ["No grid rows/header found"], "valid": False}
    headers = list(rows[0])
    while headers and headers[-1] == "":
        headers.pop()
    if len(headers) != len(set(headers)) or "" in headers:
        errors.append("Duplicate or blank header")
    missing = sorted(set(HEADERS[name]) - set(headers))
    if missing:
        errors.append("Missing required headers: " + ", ".join(missing))
    records = []
    for number, row in enumerate(rows[1:], 2):
        if not any(row):
            continue
        if any(row[len(headers):]):
            errors.append(f"Nonempty cells beyond header at row {number}")
        records.append({"row_number": number, "values": dict(zip(headers, row[:len(headers)] + [""] * max(0, len(headers)-len(row))))})
    key = HEADERS[name][0]
    ids = [r["values"].get(key, "") for r in records]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        errors.append("Missing or duplicate record ID")
    if name in COUNTS and len(records) != COUNTS[name]:
        errors.append(f"Expected {COUNTS[name]} records from diagnosed case; observed {len(records)}; inventory change requires review")
    return {"headers": headers, "records": records, "record_ids": ids, "record_count": len(records),
            "gid": str(gid), "tab_name": tab_name, "valid": not errors, "errors": errors}


def extract(name, raw, content_type, configured_tabs):
    text = raw.decode("utf-8-sig")
    if "csv" in content_type.lower():
        if len(configured_tabs) != 1:
            raise ValueError("CSV response must be bound to exactly one requested tab")
        tab = configured_tabs[0]
        return [table(name, list(csv.reader(io.StringIO(text), strict=True)), tab["gid"], tab["name"])], []
    parser = Grids()
    parser.feed(text)
    discovered = [{"gid": t["gid"], "name": parser.captions[i] if len(parser.captions) == len(parser.tables) else None}
                  for i,t in enumerate(parser.tables)]
    return [table(name, t["rows"], t["gid"], discovered[i]["name"]) for i,t in enumerate(parser.tables)], discovered


def validate_relationships(tables):
    """Check joins and HTML/CSV agreement; never resolve business evidence states."""
    errors = []
    chosen = {}
    for name in HEADERS:
        candidates = [t for t in tables if t["source_name"] == name]
        valid = [t for t in candidates if t["valid"]]
        errors.extend(f"{name}: {e}" for t in candidates for e in t["errors"])
        if not valid:
            errors.append(f"{name}: no valid table available")
            continue
        chosen[name] = valid[-1]
        reference = {r["values"][HEADERS[name][0]]: r["values"] for r in valid[0]["records"]}
        for other in valid[1:]:
            comparison = {r["values"][HEADERS[name][0]]: r["values"] for r in other["records"]}
            if reference != comparison:
                errors.append(f"{name}: HTML/CSV or tab records disagree; retain both versions")
    system_ids = set(chosen.get("SYSTEMS", {}).get("record_ids", []))
    for name in ("EVIDENCE", "CALENDAR"):
        for row in chosen.get(name, {}).get("records", []):
            value = row["values"].get("system_id")
            if name == "CALENDAR" and value == "ALL":
                continue  # Explicit source-reported workbook-wide action, not a system ID.
            if value not in system_ids:
                errors.append(f"{name} row {row['row_number']}: unknown system_id {value!r}")
    return {"valid": not errors, "errors": errors, "record_counts": {n:t["record_count"] for n,t in chosen.items()},
            "system_ids": sorted(system_ids), "independently_corroborated": False,
            "approval_verified": False, "tab_discovery_limitation": LIMITATION}
