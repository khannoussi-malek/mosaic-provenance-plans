"""Build the provenance graph from Claude's reading of the 100 test texts, and score that reading like any plan.

Read once (Claude, graph/claude_events_*.json), check every quote against the source text, merge name variants
(graph/owner_aliases.json), link owners to the Red Flag list, and write graph/graph.json:
  artworks  id -> title, artist
  owners    canonical name -> names as written, roles, Red Flag list keys
  holdings  one edge per ownership step: artwork, owner, order, year, until (next dated step), quote
Usage: python3 graph.py
"""
import json

import score as s

G = s.HERE / "graph"


def load_events(docs):
    """Claude's events per artwork, keeping only those whose quote is in the text (same check as every plan)."""
    rows = {}
    for f in sorted(G.glob("claude_events_*.json")):
        rows.update({str(r["id"]): dict(r, error=None, seconds=0) for r in json.loads(f.read_text())})
    missing = {d["id"] for d in docs} - set(rows)
    if missing:
        raise SystemExit(f"no Claude events for {len(missing)} artworks, e.g. {sorted(missing)[:3]}")
    return s.prepare(docs, rows)  # whitespace-tolerant quote check; drops the receiving museum as a *previous* owner


def load_aliases():
    """name -> canonical name; the file also keeps the reason for every merge ({"to": ..., "why": ...})."""
    f = G / "owner_aliases.json"
    raw = json.loads(f.read_text()) if f.exists() else {}
    return {k: v["to"] if isinstance(v, dict) else v for k, v in raw.items()}


def build(docs, results, aliases, keys, rx):
    owners, holdings = {}, []
    for d in docs:
        events = [e for e in results[d["id"]]["events"] if e["span_ok"]]
        years = [e["year"] if isinstance(e.get("year"), int) else None for e in events]
        for i, e in enumerate(events):
            canon = aliases.get(e["owner"], e["owner"])
            o = owners.setdefault(canon, {"names": [], "roles": [], "red_flag": []})
            o["names"] = sorted(set(o["names"]) | {e["owner"]})
            o["roles"] = sorted(set(o["roles"]) | {e["role"]})
            o["red_flag"] = sorted(set(o["red_flag"]) | s.match(s.forward(e["owner"]), rx, keys, tier="fullname"))
            holdings.append({"artwork": d["id"], "owner": canon, "as_written": e["owner"], "order": i,
                             "role": e["role"], "date": e.get("date"), "year": years[i],
                             "since": next((y for y in reversed(years[:i]) if y is not None), None),  # last date before
                             "until": next((y for y in years[i + 1:] if y is not None), None),
                             "quote": e["source_span"], "joint": bool(e.get("joint")), "hedge": e.get("hedge")})
    artworks = {d["id"]: {"title": d["title"], "artist": d.get("artist")} for d in docs}
    return {"artworks": artworks, "owners": owners, "holdings": holdings, "museum": museum_steps(docs)}


def museum_steps(docs):
    """How the National Gallery itself acquired each work: shown at the end of a history, never scored as an owner."""
    out = {}
    for f in sorted(G.glob("claude_events_*.json")):
        for r in json.loads(f.read_text()):
            last = r["events"][-1] if r["events"] else None
            if last and s.tokens(last["owner"]) <= s.RECEIVER:
                out[str(r["id"])] = {"year": last.get("year"), "quote": last["source_span"]}
    return {d["id"]: out[d["id"]] for d in docs if d["id"] in out}


def main():
    docs = json.loads(s.TESTSET.read_text())
    keys, rx = s.load_keys(s.REDFLAG)
    raw = sum(len(r["events"]) for f in G.glob("claude_events_*.json") for r in json.loads(f.read_text()))
    results = load_events(docs)
    aliases = load_aliases()
    graph = build(docs, results, aliases, keys, rx)
    (G / "graph.json").write_text(json.dumps(graph, indent=1, ensure_ascii=False))

    kept = len(graph["holdings"])
    names = {h["as_written"] for h in graph["holdings"]}
    print(f"graph: {len(graph['artworks'])} artworks, {len(graph['owners'])} owners "
          f"({len(names)} names as written, {len(aliases)} merged), {kept} holdings; "
          f"quotes checked: {kept} kept of {raw} extracted (receiving museum not counted as previous owner)")
    print(f"Red Flag owners in the graph: {sum(bool(o['red_flag']) for o in graph['owners'].values())}")

    ref = json.loads((s.HERE / "data" / "labels_reference.json").read_text())["labels"]
    labels = {d["id"]: ref.get(d["id"], "not flagged") for d in docs}
    verdicts = {d["id"]: s.plan_verdict(results[d["id"]]["events"], keys, rx) for d in docs}
    print(f"Claude reading, scored like the plans: owners {s.owner_scores(docs, results)}, "
          f"screening {s.screening(docs, verdicts, labels)}")


if __name__ == "__main__":
    main()
