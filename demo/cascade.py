"""P3 cascade: small model first, escalate a doc to the large model only when a free check fails.

Usage: python3 cascade.py SMALL LARGE DOCS.json OUT.json
Output has the same shape as extract.py, plus 'escalated' and the summed cost of both calls.
"""
import json
import re
import sys
from pathlib import Path

from extract import extract

WAR_YEAR = re.compile(r"\b19(?:3[3-9]|4[0-5])\b")


def needs_escalation(doc, r):
    """Checks that cost nothing: errors, unsupported spans, a 1933-45 text with no dated 1933-45 event."""
    if r["error"] or not r["events"]:
        return "error or empty"
    if not all(e["span_ok"] for e in r["events"]):
        return "span not in text"
    if WAR_YEAR.search(doc["provenance_text"]) and not any(1933 <= (e.get("year") or 0) <= 1945 for e in r["events"]):
        return "no dated 1933-45 event"
    return None


def cascade(small, large, doc):
    r = extract(small, doc)
    reason = needs_escalation(doc, r)
    if not reason:
        return dict(r, escalated=None)
    big = extract(large, doc)
    kept = big if not big["error"] else r  # never swap usable small-model events for a failed large call
    return dict(kept, escalated=reason if not big["error"] else reason + "; large model failed, kept small", in_tok=r["in_tok"] + big["in_tok"],
                out_tok=r["out_tok"] + big["out_tok"], seconds=r["seconds"] + big["seconds"])


if __name__ == "__main__":
    small, large, docs_path, out_path = sys.argv[1:5]
    results = []
    for d in json.loads(Path(docs_path).read_text()):
        r = cascade(small, large, d)
        results.append(r)
        print(f"{d['id']}: {len(r['events'])} events, escalated={r['escalated']}, {r['seconds']:.1f}s", flush=True)
    Path(out_path).write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"escalated {sum(bool(r['escalated']) for r in results)}/{len(results)}")
