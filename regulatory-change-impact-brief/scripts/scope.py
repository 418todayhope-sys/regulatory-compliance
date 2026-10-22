"""Generate only the evidence-backed Stage 01 scope snapshot."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
INTERVIEW = "interviews/project-b-regulatory-compliance-20261018-1952.md"


def evidence(root, record_id, path, summary, locator):
    raw = (root / path).read_bytes()
    return {"id": record_id, "summary": summary, "evidence_ids": [],
            "path": path, "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "locator": locator, "evidence_type": "local-project-document"}


def build_scope(root=ROOT, interview=INTERVIEW):
    inputs = [
        evidence(root, "e-assignment", "Project_B_Learner_Assignment_Codex.md",
                 "Assigned review date, audiences and draft-only mandate.", "Scenario; Your task"),
        evidence(root, "e-interview", interview,
                 "Stakeholder-disclosed scope and responsibilities; not source-verified.",
                 "03:21–03:23 PM scope/date; 03:30 PM roles; 03:40 PM join key"),
        evidence(root, "e-readme", "README.md",
                 "Preserve schema, original interview and read-only source access.", "Before you work; Supplied files"),
    ]
    basis = ["e-assignment", "e-interview"]
    gaps = [
        {"id": "u-system-inventory", "summary": "Eight systems expected; actual IDs and facts await SYSTEMS verification.",
         "evidence_ids": ["e-interview"], "owner": "System owners",
         "resolution_need": "Read SYSTEMS through its disclosed route and verify identities and date-appropriate facts."},
        {"id": "u-authority", "summary": "Applicable legal versions and source suitability have not been verified.",
         "evidence_ids": basis, "owner": "Legal",
         "resolution_need": "Retrieve and reconcile required official sources in later authorized stages."},
        {"id": "u-approval", "summary": "No version-bound human approval has been supplied or applied.",
         "evidence_ids": basis, "owner": "Legal and Operations",
         "resolution_need": "Retain pending review until actual authorized, version-matched feedback exists."},
        {"id": "u-export", "summary": "Local interview export completeness has not been independently certified.",
         "evidence_ids": ["e-interview", "e-readme"], "owner": "Learner / facilitator",
         "resolution_need": "Verify original export and assessed-work prerequisites with facilitator."},
    ]
    decisions = [
        {"id": "d-date", "summary": "Keep the assigned review date fixed using a documented UTC date anchor.",
         "evidence_ids": basis, "concern": "Separate review date from execution time.",
         "options": ["Document a UTC calendar-date anchor", "Infer an unprovided local observation time"],
         "chosen_behavior": "Use 2026-08-26T00:00:00Z; timestamp generation separately.",
         "rationale": "The assignment fixes the date while the schema requires date-time.",
         "tradeoffs": ["UTC midnight satisfies date-time syntax but does not establish an observation instant."],
         "downstream_effect": "Later evidence must be assessed against 26 August 2026."},
        {"id": "d-unknown-ids", "summary": "Record descriptive scope while leaving all system IDs unknown.",
         "evidence_ids": basis, "concern": "Schema requires nonempty scope before SYSTEMS has been read.",
         "options": ["Describe expected inventory and retain empty IDs", "Invent eight system IDs"],
         "chosen_behavior": "Keep system_ids empty and inventory verification pending.",
         "rationale": "Interview establishes an expected count, not a verified inventory.",
         "tradeoffs": ["Scope is schema-valid but cannot yet support system-level joins or conclusions."],
         "downstream_effect": "SYSTEMS verification must establish actual IDs before analysis."},
    ]
    return {
        "schema_version": "regulatory-compliance-stage-snapshot/2",
        "snapshot_id": "snapshot-" + str(uuid4()), "run_id": "run-" + str(uuid4()),
        "stage": "scope", "sequence": 1,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "partial", "predecessor": None, "consumed_record_ids": [],
        "produced_record_ids": [r["id"] for r in inputs + gaps + decisions],
        "state": {
            "as_of": "2026-08-26T00:00:00Z",
            "as_of_convention": "UTC calendar-date anchor; not an observed operational timestamp",
            "review_type": "Draft EU AI Act Article 50 impact review",
            "team": "EU programme team", "location": "Dublin, Ireland",
            "systems_in_scope": ["Eight expected EU programme AI systems; identities unverified pending SYSTEMS"],
            "expected_system_count": 8, "system_ids": [], "system_ids_status": "unverified",
            "audiences": ["Legal", "Operations"],
            "approval_gates": ["Legal: final legal interpretation and exception review",
                               "Operations: policy activation, approved dates and incident closure"],
            "approval_status": "pending", "scope_basis": "Assignment and interview; live sources not read",
            "evidence_records": inputs, "supersedes_run_id": None,
        },
        "unresolved": gaps, "decisions": decisions,
    }


def validate(snapshot, root=ROOT):
    schema = json.loads((root / "snapshot.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()

    @checker.checks("date-time", raises=ValueError)
    def date_time(value):
        if not isinstance(value, str):
            return True  # The schema's type constraint handles non-strings.
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
            return False
        datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
        return True

    Draft202012Validator(schema, format_checker=checker).validate(snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "deliverables/snapshots/01-scope.json")
    args = parser.parse_args()
    snapshot = build_scope()
    validate(snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    print(f"Stage 01 partial draft validated: {args.output} (run {snapshot['run_id']})")


if __name__ == "__main__":
    main()
