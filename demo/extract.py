"""Ownership-event extraction with a local Ollama model, structured output, disk cache.

Usage: python3 extract.py MODEL DOCS.json OUT.json
DOCS.json: [{"id": ..., "provenance_text": ...}, ...]
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434/api/chat"
CACHE = Path(os.environ.get("MOSAIC_CACHE", Path(__file__).parent / "cache"))  # override for reproducibility checks
MAX_OUT = 2048  # ponytail: hard cap so a looping model cannot run forever
# No Ollama `format` schema: grammar-constrained decoding was ~5x slower wall-clock on this Mac.
# The schema is enforced by validate() instead; anything invalid is counted as an error.

EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "role": {"type": "string", "enum": [
                        "collector", "dealer", "auction", "museum", "heir",
                        "confiscating agency", "collecting point", "other"]},
                    "date": {"type": ["string", "null"]},
                    "year": {"type": ["integer", "null"]},
                    "place": {"type": ["string", "null"]},
                    "source_span": {"type": "string"},
                },
                "required": ["owner", "role", "date", "year", "place", "source_span"],
            },
        }
    },
    "required": ["events"],
}

PROMPT = """You extract the ownership history of an artwork from a museum provenance text.
List every owner or custodian in order, including those mentioned only in footnotes
(e.g. confiscations, Nazi agencies, collecting points, dealers, auctions).
For each: owner name as written, role, date as written, year (first year, integer) or null,
place or null, and source_span: an EXACT copy of the shortest passage that states it.
Do not invent anything that is not in the text.
Roles: collector, dealer, auction, museum, heir, confiscating agency, collecting point, other.
Answer with JSON only, exactly this shape:
{{"events": [{{"owner": "...", "role": "...", "date": "..." or null, "year": 1939 or null, "place": "..." or null, "source_span": "..."}}]}}

Provenance text:
{text}"""
PROMPT_V2 = """You extract the ownership history of an artwork from a museum provenance text.
List every owner or custodian in order, one entry per party, including those mentioned only in footnotes
(confiscations, Nazi agencies, collecting points, dealers, auctions).
Rules:
- An auction house or sale is its own entry (role auction), separate from the seller and the buyer.
- Do NOT list places, authors or archives cited as sources, estates without a person, or sales that did not happen.
- year = the year this party acquired the object (first year), NOT birth or death years in brackets; null if unknown.
- source_span = an EXACT copy of the shortest passage naming the party, including its date phrase if there is one.
Do not invent anything that is not in the text.
Roles: collector, dealer, auction, museum, heir, confiscating agency, collecting point, other.
Answer with JSON only, exactly this shape:
{{"events": [{{"owner": "...", "role": "...", "date": "..." or null, "year": 1939 or null, "place": "..." or null, "source_span": "..."}}]}}

Provenance text:
{text}"""
PROMPTS = {"v1": PROMPT, "v2": PROMPT_V2}  # v1 = frozen prompt of the reported P1-P3 runs


def call(model, text, prompt="v1", max_out=None):
    return call_raw(model, PROMPTS[prompt].format(text=text), max_out)


def call_raw(model, content, max_out=None):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "seed": 0, "num_ctx": 8192, "num_predict": max_out or MAX_OUT},
    }
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    hit = CACHE / f"{key}.json"
    if hit.exists():
        return json.loads(hit.read_text())
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in (1, 2):  # ponytail: one retry for a transient Ollama hiccup, then the doc is a counted error
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                resp = json.loads(r.read())
            break
        except OSError:  # URLError, timeouts, connection resets
            if attempt == 2:
                raise
            time.sleep(10)
    CACHE.mkdir(exist_ok=True)
    tmp = hit.with_suffix(".tmp")
    tmp.write_text(json.dumps(resp))
    os.replace(tmp, hit)  # atomic: a killed run never leaves a corrupt cache file
    return resp


def validate(content):
    """Parse the model's JSON (tolerating a code fence) and check it against EVENT_SCHEMA's fields and roles."""
    body = content[content.find("{"): content.rfind("}") + 1]
    events = json.loads(body, strict=False)["events"]  # raw newlines inside copied spans are allowed
    item = EVENT_SCHEMA["properties"]["events"]["items"]
    roles = set(item["properties"]["role"]["enum"])
    for ev in events:
        missing = set(item["required"]) - set(ev)
        if missing:
            raise ValueError(f"event missing {sorted(missing)}")
        if not isinstance(ev["owner"], str) or not isinstance(ev["source_span"], str):
            raise ValueError("owner and source_span must be strings")
        if ev["role"] not in roles:
            ev["role"] = "other"  # ponytail: unknown role label kept as 'other', not an error
        if ev["year"] is not None and not isinstance(ev["year"], int):
            ev["year"] = int(str(ev["year"])[:4]) if str(ev["year"])[:4].isdigit() else None
    return events


def extract(model, doc, prompt="v1", max_out=None):
    try:
        resp = call(model, doc["provenance_text"], prompt, max_out)
    except OSError as e:
        return {"id": doc["id"], "model": model, "events": [], "error": f"request failed: {e}",
                "in_tok": 0, "out_tok": 0, "seconds": 0.0}
    try:
        events, error = validate(resp["message"]["content"]), None
    except (KeyError, ValueError, TypeError) as e:
        events, error = [], f"{type(e).__name__}: {e}"  # counted, never silently dropped
    if resp.get("done_reason") == "length":
        error = (error or "") + f" truncated at {max_out or MAX_OUT} tokens"
    for ev in events:
        ev["span_ok"] = bool(ev.get("source_span")) and ev["source_span"] in doc["provenance_text"]
    return {
        "id": doc["id"], "model": model, "events": events, "error": error,
        "in_tok": resp.get("prompt_eval_count", 0), "out_tok": resp.get("eval_count", 0),
        "seconds": resp.get("total_duration", 0) / 1e9,
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--prompt=")]
    prompt = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--prompt=")), "v1")
    model, docs_path, out_path = args[:3]
    docs = json.loads(Path(docs_path).read_text())
    results = []
    t0 = time.time()
    for d in docs:
        r = extract(model, d, prompt)
        results.append(r)
        n, ok = len(r["events"]), sum(e["span_ok"] for e in r["events"])
        print(f"{model} {r['id']}: {n} events, {ok}/{n} spans ok, {r['seconds']:.1f}s, out_tok={r['out_tok']}, err={r['error']}", flush=True)
        Path(out_path).write_text(json.dumps(results, indent=1, ensure_ascii=False))  # after every doc: a crash keeps the work
    print(f"TOTAL {model}: {time.time() - t0:.1f}s wall for {len(docs)} docs")
