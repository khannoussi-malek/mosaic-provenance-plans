"""P4: extractor + verifier agent. The extractor's events (P1, cached) go to a second pass that checks each
event against the text, fixes or drops it, and adds missed owners. Same JSON schema in and out.

Usage: python3 verify.py EXTRACTOR VERIFIER DOCS.json OUT.json
"""
import json
import sys
from pathlib import Path

from extract import MAX_OUT, call_raw, extract, validate

VERIFY_PROMPT = """You check an ownership history that another system extracted from a museum provenance text.
For each event: keep it if the text supports it, fix it if a field is wrong, drop it if the party never held the object
(places, authors or archives cited as sources, sales that did not happen). Add owners the list missed, including ones
only in footnotes. year = the year that party acquired the object, NOT birth or death years. Keep source_span an EXACT
copy from the text. Return the full corrected list, in the order of the history.
Answer with JSON only, exactly this shape:
{{"events": [{{"owner": "...", "role": "...", "date": "..." or null, "year": 1939 or null, "place": "..." or null, "source_span": "..."}}]}}

Provenance text:
{text}

Extracted events:
{events}"""
FIELDS = ("owner", "role", "date", "year", "place", "source_span")


def verify(extractor, verifier, doc):
    first = extract(extractor, doc)
    if first["error"]:
        return dict(first, verified=False)  # nothing to check; the error is counted as P1's
    events = json.dumps([{k: e.get(k) for k in FIELDS} for e in first["events"]], ensure_ascii=False)
    try:
        resp = call_raw(verifier, VERIFY_PROMPT.format(text=doc["provenance_text"], events=events))
        checked, error = validate(resp["message"]["content"]), None
        if resp.get("done_reason") == "length":
            error = f"verifier truncated at {MAX_OUT} tokens"
    except (OSError, KeyError, ValueError, TypeError) as e:
        resp, checked, error = {}, [], f"verifier failed: {type(e).__name__}: {e}"
    if error:  # keep the extractor's events rather than lose usable work
        checked = first["events"]
    for ev in checked:
        ev["span_ok"] = bool(ev.get("source_span")) and ev["source_span"] in doc["provenance_text"]
    return {"id": doc["id"], "model": f"{extractor}+{verifier}", "events": checked, "error": error, "verified": not error,
            "in_tok": first["in_tok"] + resp.get("prompt_eval_count", 0),
            "out_tok": first["out_tok"] + resp.get("eval_count", 0),
            "seconds": first["seconds"] + resp.get("total_duration", 0) / 1e9}


if __name__ == "__main__":
    extractor, verifier, docs_path, out_path = sys.argv[1:5]
    results = []
    for d in json.loads(Path(docs_path).read_text()):
        r = verify(extractor, verifier, d)
        results.append(r)
        n, ok = len(r["events"]), sum(e["span_ok"] for e in r["events"])
        print(f"{d['id']}: {n} events, {ok}/{n} spans ok, {r['seconds']:.1f}s, err={r['error']}", flush=True)
        Path(out_path).write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"verified {sum(r['verified'] for r in results)}/{len(results)}")
