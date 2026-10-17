"""Evidence checklist for the requested activities, without a human-authenticity grade."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from .evaluation import read_inputs
from .models import Product
from .store import Store
from .workers import DocumentWorker, Verifier


def assess(directory):
    if not (directory / "state.sqlite").exists():
        raise FileNotFoundError("run database not found")
    store = Store(directory / "state.sqlite", readonly=True)
    try:
        settings = store.get("settings", {})
        mode = settings.get("backend", "unknown")
        action_counts, dispatches, activation = Counter(), Counter(), Counter()
        verified_ids, link_methods = set(), {}
        viewport_changes = set()
        pauses = {}
        intervals = []
        typos = 0
        for row in store.db.execute("SELECT kind,body FROM events ORDER BY seq"):
            kind, body = row["kind"], json.loads(row["body"])
            if kind == "action.verified":
                action_counts[body["kind"]] += 1
                verified_ids.add(body["action_id"])
            elif kind == "input.dispatched":
                dispatches[body["kind"]] += 1
                if body.get("requested_onset_interval_seconds") is not None:
                    intervals.append(body["requested_onset_interval_seconds"])
            elif kind == "browser.link_activation":
                link_methods[body["action_id"]] = body["method"]
            elif kind == "browser.viewport_changed":
                viewport_changes.add(body["action_id"])
            elif kind == "timing":
                category = body["category"]
                if category in ("behaviour.read", "behaviour.switch", "behaviour.plan", "behaviour.scroll"):
                    bucket = pauses.setdefault(
                        category, {"count": 0, "requested_seconds": 0, "elapsed_seconds": 0}
                    )
                    bucket["count"] += 1
                    bucket["requested_seconds"] += body.get("requested_seconds", 0)
                    bucket["elapsed_seconds"] += body.get("elapsed_seconds", 0)
                typos += category == "behaviour.typo_notice"
        try:
            products = [Product.model_validate(p) for p in store.get("products", [])]
            verification = (
                Verifier().check(directory, products, DocumentWorker().plan(products))
                if products
                else {"passed": False, "errors": ["no source products"]}
            )
        except (OSError, ValueError, KeyError, BadZipFile, ParseError) as exc:
            verification = {"passed": False, "errors": [str(exc)]}
        activation.update(method for identity, method in link_methods.items() if identity in verified_ids)
    finally:
        store.close()

    observed = read_inputs(directory / "inputs.jsonl") if (directory / "inputs.jsonl").exists() else None
    coverage = observed["coverage"] if observed else None
    input_complete = bool(
        coverage
        and observed["recording_roles"] == ["agent"]
        and coverage["enabled"]
        and not any(coverage[key] for key in ("gaps", "errors", "dropped_events", "invalid_timestamps"))
    )
    live_completed = mode == "macos" and verification["passed"] and bool(action_counts["write_document"])
    cv = (
        statistics.pstdev(intervals) / statistics.fmean(intervals)
        if intervals and statistics.fmean(intervals)
        else 0
    )
    unique_ms = len({round(value, 3) for value in intervals})
    counts = observed["event_counts"] if observed else {}

    def row(name, demonstrated, evidence, desktop_confirmed=False, limitation=None):
        return {
            "criterion": name,
            "policy_check": "pass" if demonstrated else "not_demonstrated",
            "desktop_check": "pass" if desktop_confirmed else "not_verified",
            "evidence": evidence,
            "limitation": limitation,
        }

    criteria = [
        row(
            "browsing_websites",
            action_counts["navigate"] > 0 and action_counts["read_page"] > 0,
            {"navigation_actions": action_counts["navigate"], "page_reads": action_counts["read_page"]},
            live_completed and action_counts["navigate"] > 0,
            "Demo is a local catalog; arbitrary websites/search are not evaluated.",
        ),
        row(
            "scrolling",
            action_counts["scroll"] > 0 and dispatches["scroll"] > 0,
            {
                "scroll_actions": action_counts["scroll"],
                "wheel_bursts_dispatched": dispatches["scroll"],
                "session_scroll_events_observed": counts.get("scroll", 0),
                "verified_viewport_changes": len(viewport_changes & verified_ids),
            },
            live_completed and bool(viewport_changes & verified_ids),
            "Native scrolling needs matching AX content anchors moving relative to the web viewport.",
        ),
        row(
            "clicking_links",
            activation["mouse"] > 0,
            {
                "mouse_link_activations": activation["mouse"],
                "keyboard_link_activations": activation["keyboard"],
            },
            live_completed and activation["mouse"] > 0,
            "Keyboard fallback is reported separately and does not satisfy the mouse-click criterion.",
        ),
        row(
            "interacting_with_applications",
            action_counts["open_file"] >= 2 and verification["passed"],
            {
                "opened_files": action_counts["open_file"],
                "row_edits": action_counts["set_cells"],
                "document_edits": action_counts["write_document"],
                "file_verification": verification,
            },
            live_completed,
        ),
        row(
            "contextual_pauses",
            all(
                key in pauses and pauses[key]["requested_seconds"] > 0
                for key in ("behaviour.read", "behaviour.switch", "behaviour.plan")
            ),
            pauses,
            live_completed
            and all(
                pauses.get(key, {}).get("elapsed_seconds", 0) > 0
                for key in ("behaviour.read", "behaviour.switch", "behaviour.plan")
            ),
            "Context-specific pauses can be checked without a baseline; human similarity remains unmeasured.",
        ),
        row(
            "occasional_corrected_typos",
            typos > 0 and verification["passed"],
            {
                "typo_notice_count": typos,
                "final_content_correct": verification["passed"],
                "session_corrections_observed": counts.get("corrections", 0),
            },
            live_completed and typos > 0 and input_complete and counts.get("corrections", 0) > 0,
            "Do not force a typo in every session. Session input may include unrelated user activity.",
        ),
        row(
            "varied_delays",
            len(intervals) >= 30 and unique_ms > 1,
            {
                "requested_interval_samples": len(intervals),
                "unique_millisecond_intervals": unique_ms,
                "requested_interval_cv": cv,
                "observed_inter_key_statistics": observed["statistics"]["inter_key_seconds"]
                if observed
                else None,
            },
            live_completed
            and input_complete
            and observed["statistics"]["inter_key_seconds"]["count"] >= 30
            and (observed["statistics"]["inter_key_seconds"]["cv"] or 0) > 0,
            "Nonconstant timing is a capability check, not a measure of human similarity.",
        ),
    ]
    return {
        "assessment": "requested_activity_checklist",
        "backend": mode,
        "policy_checks_passed": sum(item["policy_check"] == "pass" for item in criteria),
        "desktop_checks_passed": sum(item["desktop_check"] == "pass" for item in criteria),
        "criteria_count": len(criteria),
        "criteria": criteria,
        "input_coverage": coverage,
        "authenticity_score": None,
        "note": "Checklist evidence only. Simulation passes are not GUI passes or a competition grade. Human-likeness requires empirical baseline evaluation.",
    }
