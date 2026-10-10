"""FR-10: report where the National Gallery's provenance TEXT and its structured OWNER LIST disagree, instead of
silently choosing one. The text side is read through a plan's extraction (default P3), so every item cites a quote.

Usage: python3 contradictions.py [out/run_P3.json]   -> demo/analysis/contradictions.md
Note: these are two descriptions by one institution, not two independent sources.
"""
import json
import re
import sys
from pathlib import Path

import score as s

OUT = s.HERE / "analysis" / "contradictions.md"
DATE_GAP = 3  # ponytail: years apart before a date difference is reported; below that, rounding and "by" dates dominate


def main():
    run = Path(sys.argv[1] if len(sys.argv) > 1 else s.HERE / "out" / "run_P3.json")
    docs = json.loads(s.TESTSET.read_text())
    results = s.prepare(docs, {str(r["id"]): r for r in json.loads(run.read_text())})
    only_text, only_list, dates, lifespan = [], [], [], []
    for d in docs:
        events = [e for e in results.get(d["id"], {}).get("events", []) if e.get("span_ok")]
        gold = d["gold_owners"]
        for e in events:
            match = next((g for g in gold if s.same_owner(e["owner"], g["name"])), None)
            if match is None:
                only_text.append((d, e))
            elif e.get("year") and match["beginyear"] and abs(e["year"] - match["beginyear"]) >= DATE_GAP:
                life = re.search(rf"\b{e['year']}\s*[-–]\s*\d{{4}}|\d{{4}}\s*[-–]\s*{e['year']}\b", e["source_span"])
                (lifespan if life else dates).append((d, e, match))
        for g in gold:
            if not any(s.same_owner(e["owner"], g["name"]) for e in events) and not s.tokens(g["name"]) <= s.RECEIVER:
                only_list.append((d, g))
    lines = [f"# Text vs structured owner list: National Gallery of Art test set ({len(docs)} objects)", "",
             f"Read with `{run.name}`. These are two descriptions by the same museum, not independent sources.",
             "Every row is a candidate for an expert to check, not a confirmed error in either description:",
             "the extraction itself can be wrong (e.g. an end date read as a start date).", "",
             "| Kind | Count | Objects affected |", "|---|---|---|",
             f"| Owner in the text, missing from the owner list | {len(only_text)} | {len({d['id'] for d, _ in only_text})} |",
             f"| Owner in the list, not found in the text extraction | {len(only_list)} | {len({d['id'] for d, _ in only_list})} |",
             f"| Same owner, acquisition years {DATE_GAP}+ years apart | {len(dates)} | {len({d['id'] for d, *_ in dates})} |",
             f"| (left out: the 'year' is a lifespan in the quote, an extraction error) | {len(lifespan)} | |", ""]
    lines += ["## Date conflicts", ""] + [
        f"- NGA {d['id']} · {e['owner']}: text {e['year']} (\"{e['source_span'][:120]}\") vs list {m['beginyear']}"
        for d, e, m in dates[:15]]
    lines += ["", "## Owners named in the text but missing from the owner list (first 20)", ""] + [
        f"- NGA {d['id']} · {e['owner']} ({e['role']}): \"{e['source_span'][:120]}\"" for d, e in only_text[:20]]
    lines += ["", "## In the owner list, not found in the text extraction (first 15)", "",
              "Either the extraction missed them or the list holds information the text does not show."] + [
        f"- NGA {d['id']} · {g['name']} ({g['beginyear'] or '?'}–{g['endyear'] or '?'})" for d, g in only_list[:15]]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[4:9]))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
