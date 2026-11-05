#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / pinned E404 RT fair.c reject / six E2 context deltas / NO FLASH
"""Explain E2 six-hunk divergence without inventing a semantically valid port."""
import argparse
import difflib
import hashlib
import json
import re
import runpy
from pathlib import Path

ORDINALS = (1, 2, 3, 7, 15, 20)
REJ_SHA = "b8c15cc49c3ce680e176b54065795e0bc058b481ca297cb0dff47733d8ff4c2f"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def nearest_window(lines, target, symbol):
    # Limit candidates to textual windows near the named RT function.
    # This is a diagnostic candidate, never proof of semantic equivalence.
    starts = [i for i, row in enumerate(lines) if re.search(
        r"\b" + re.escape(symbol) + r"\s*\(", row)]
    if not starts:
        return None
    n = len(target)
    if not n:
        return None
    candidates = set()
    for loc in starts:
        for i in range(max(0, loc - 80), min(len(lines) - n + 1, loc + 180)):
            candidates.add(i)
    ranked = []
    for i in sorted(candidates):
        window = lines[i:i + n]
        score = difflib.SequenceMatcher(
            None, target, window, autojunk=False).ratio()
        ranked.append((score, i, window))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    if not ranked:
        return None
    best = ranked[0]
    ties = sum(1 for x in ranked if abs(x[0] - best[0]) < 1e-12)
    return {
        "start_line": best[1] + 1,
        "end_line": best[1] + n,
        "sha256": sha("".join(best[2])),
        "similarity_ratio": round(best[0], 6),
        "equal_best_candidates": ties,
        "selection": "NEAREST_TEXTUAL_WINDOW_NOT_SEMANTIC_MATCH",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--e2-result", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    args = p.parse_args()
    tree = args.tree
    result = json.loads(args.e2_result.read_text())
    module = runpy.run_path(str(Path(__file__).with_name("exp76-e2-lazy-port.py")))
    hunk_parser = module["hunks"]
    rej_file = tree / "kernel/sched/fair.c.rej"
    rej_raw = rej_file.read_bytes()
    if hashlib.sha256(rej_raw).hexdigest() != REJ_SHA:
        raise RuntimeError("E2 reject SHA diverged")
    hunks = hunk_parser(rej_raw.decode("utf-8"))
    fair_raw = (tree / "kernel/sched/fair.c").read_bytes()
    fair_text = fair_raw.decode("utf-8")
    actual_lines = fair_text.splitlines(keepends=True)
    if len(hunks) != 20 or len(result["entries"]) != 6:
        raise RuntimeError("unexpected E2 inventory")
    same_tree = result["source_sha256_before"] == result["source_sha256_after"]
    if hashlib.sha256(fair_raw).hexdigest() != result["source_sha256_after"]:
        raise RuntimeError("E2 report does not match the actual fair.c")
    data = {
        "schema_version": 1,
        "gate": "EXP76_SCHEDULER_E2_CONTEXT_DELTA",
        "e404_base": "fed88a6024cd4d46c52eda607a95d97d7371ba81",
        "source": "kernel/sched/fair.c",
        "reject_sha256": REJ_SHA,
        "before_sha256": result["source_sha256_before"],
        "after_sha256": result["source_sha256_after"],
        "e2_modified_fair_c": not same_tree,
        "port_verified_count": result["applied_count"],
        "blocked_count": result["blocked_count"],
        "hunks": [],
        "qemu_runtime_verified": False,
        "rt_handoff_ready": False,
    }
    for entry in result["entries"]:
        ordinal = entry["ordinal"]
        if ordinal not in ORDINALS:
            raise RuntimeError("unapproved E2 ordinal")
        header, expected, replacement = hunks[ordinal - 1]
        info = re.search(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", header)
        if not info:
            raise RuntimeError("invalid hunk line range: " + header)
        upstream_start = int(info.group(1))
        upstream_len = int(info.group(2) or 1)
        description = header.split("@@", 2)[-1].strip()
        match = re.search(r"\b([a-zA-Z_]\w*)\s*\(", description)
        if not match:
            raise RuntimeError("cannot derive target function: " + header)
        symbol = match.group(1)
        candidate = nearest_window(
            actual_lines, expected.splitlines(keepends=True), symbol)
        exists = candidate is not None
        exact_match = fair_text.count(expected)
        # The tool ran once; absence of any E2 source modification proves the
        # fix did not break any previously matching hunk in this run.
        data["hunks"].append({
            "ordinal": ordinal, "file": "kernel/sched/fair.c",
            "line_range": {
                "upstream_original_start": upstream_start,
                "upstream_original_end": upstream_start + upstream_len - 1,
                "actual_candidate_start": (
                    candidate["start_line"] if candidate else None),
                "actual_candidate_end": (
                    candidate["end_line"] if candidate else None),
            },
            "function_anchor": symbol,
            "expected_context_sha": sha(expected),
            "actual_context_sha": candidate["sha256"] if candidate else None,
            "actual_context_hash_scope": (
                "NEAREST_TEXTUAL_WINDOW_NOT_SEMANTIC_MATCH"
                if candidate else "NO_DEFENSIBLE_WINDOW"),
            "candidate_similarity": (
                candidate["similarity_ratio"] if candidate else None),
            "equal_best_candidates": (
                candidate["equal_best_candidates"] if candidate else None),
            "old_context_occurrences_before_and_after": exact_match if same_tree else None,
            "new_context_occurrences_after": fair_text.count(replacement),
            "fix_e2_touched_this_hunk": False if same_tree else None,
            "reason_divergence": "context_changed" if exists else "context_missing",
            "semantic_conflict": "NOT_ASSESSED",
            "state": entry["state"],
        })
    if len(data["hunks"]) != 6:
        raise RuntimeError("E2 detailed report must contain six hunks")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(data, indent=2) + "\n")
    print("E2_DETAIL_HUNKS=", len(data["hunks"]))
    print("E2_MODIFIED_FAIR_C=", data["e2_modified_fair_c"])
    print("E2_PORT_VERIFIED=", data["port_verified_count"])
    print("E2_ACTUAL_CONTEXT_HASHES=", sum(bool(x["actual_context_sha"]) for x in data["hunks"]))


if __name__ == "__main__":
    main()
