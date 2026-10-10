"""Ask a provenance question in plain language; get a plan, then a checkable answer (FR-1, FR-3, FR-5, FR-11..14).

Usage: python3 ask.py "Which works passed through a Red Flag dealer between 1933 and 1945? Be quick."
       python3 ask.py --plan-only "..."      # show the plan, do not run it

The plan is picked from the measured results in out/results.json (same numbers as the write-up), not from guesses.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import cascade
import extract
import score

HERE = Path(__file__).parent
RESULTS = HERE / "out" / "results.json"  # final measured numbers (reference labels), same file as the write-up
RUNNABLE = ("P0", "P1", "P1r", "P2", "P3")  # plans this front end can execute
PLANNER_MODEL = SMALL = "qwen3:8b"
LARGE = "qwen2.5:14b"
SOURCES = {"NGA": HERE / "data" / "testset_nga.json"}  # ponytail: AIC joins here once its 20 checked texts exist

PLANNER_PROMPT = """Turn a provenance research question into a JSON plan spec. Fields:
"period": [first_year, last_year] the question asks about (default [1933, 1945]),
"watchlist": "red_flag" if the question is about looted art, Nazi-era dealers or the ALIU list, else null,
"sources": list from ["NGA"] the question allows (default all),
"preference": "fast", "accurate" or null,
"budget_seconds": total seconds the user allows, or null,
"object": the title of one specific artwork the question names, or null.
Answer with JSON only.

Question: {q}"""


BUDGET = re.compile(r"\b\d{1,5}\s*(?:secs?|seconds?|mins?|minutes?|hrs?|hours?)\b|\b\d{1,3}\s*[sh]\b", re.I)


def parse_question(q):
    """Local model reads the question; a regex fallback keeps the system usable if it fails. Every field the model
    returns is checked: a period must be two ordered years, a budget must be stated in the question."""
    years = [int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d)\b", q)]
    period = [min(years), max(years)] if len(years) >= 2 else [1933, 1945]
    body = {"model": PLANNER_MODEL, "messages": [{"role": "user", "content": PLANNER_PROMPT.format(q=q)}],
            "stream": False, "think": False, "options": {"temperature": 0, "seed": 0, "num_predict": 200}}
    try:
        req = urllib.request.Request(extract.OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            content = json.loads(r.read())["message"]["content"]
        spec = json.loads(content[content.find("{"): content.rfind("}") + 1])
        if not isinstance(spec, dict):
            raise ValueError("the model's answer is not a JSON object")
        spec["parsed_by"] = PLANNER_MODEL
    except (OSError, ValueError, KeyError) as e:
        spec = {"watchlist": "red_flag", "sources": list(SOURCES),
                "preference": "fast" if re.search(r"\b(quick|fast)\b", q, re.I) else None,
                "parsed_by": f"regex fallback ({type(e).__name__})"}
    b = spec.get("budget_seconds")
    # a budget only counts if the question states one ("60 seconds", not "1930s"); the model must not invent it
    spec["budget_seconds"] = b if BUDGET.search(q) and isinstance(b, (int, float)) and b > 0 else None
    spec["sources"] = [s for s in spec.get("sources") or SOURCES if s in SOURCES] or list(SOURCES)
    p = spec.get("period")
    ok = isinstance(p, list) and len(p) == 2 and all(isinstance(y, int) for y in p) and p[0] <= p[1]
    spec["period"] = p if ok else period  # a half, inverted or text period from the model falls back to the question's years
    o = spec.get("object")
    spec["object"] = o.strip() if isinstance(o, str) and o.strip() else None
    return spec


def title_key(t):
    """Case, accents, punctuation and spacing do not matter when matching a title ("Pietà" = "pieta.")."""
    return " ".join(re.sub(r"[^\w\s]", " ", score.fold(t or "").lower()).split())


def select_docs(spec, docs):
    """A named artwork: only its records. An exact title wins; otherwise titles that contain the name. Empty if the
    sources lack it (a longer name never matches a shorter title: "Saint Peter Martyr" is not "Saint Peter")."""
    obj = title_key(spec.get("object"))
    if not obj:
        return docs
    return [d for d in docs if title_key(d["title"]) == obj] or [d for d in docs if obj in title_key(d["title"])]


def guess_object(q, docs):
    """Without the model: a title that appears word for word in the question, longest first."""
    words = f" {title_key(q)} "
    titles = sorted({d["title"] for d in docs}, key=lambda t: len(title_key(t)), reverse=True)
    return next((t for t in titles if title_key(t) and f" {title_key(t)} " in words), None)


def choose_plan(spec, n_docs):
    """Pick from measured plans: within budget, best screening F1; 'fast' takes the quickest plan within 0.05 F1."""
    res = json.loads(RESULTS.read_text())
    plans = [{"name": k, "screen_f1": v["screen"]["F1"], "est_seconds": round(v["seconds"] / res["n_docs"] * n_docs)}
             for k, v in res["plans"].items() if k in RUNNABLE]
    budget = spec.get("budget_seconds")
    ok = [p for p in plans if not budget or p["est_seconds"] <= budget] or [min(plans, key=lambda p: p["est_seconds"])]
    best = max(ok, key=lambda p: p["screen_f1"])
    if spec.get("preference") == "fast":
        near = [p for p in ok if p["screen_f1"] >= best["screen_f1"] - 0.05]
        best = min(near, key=lambda p: p["est_seconds"])
    for p in plans:
        p["over_budget"] = p not in ok
    return best, plans


def show_plan(q, spec, plan, plans, n_docs):
    lines = [f"QUESTION  {q}",
             f"UNDERSTOOD  period {spec['period'][0]}-{spec['period'][1]} · watch list: {spec.get('watchlist') or 'none'} · "
             f"sources: {', '.join(spec['sources'])} ({n_docs} records) · preference: {spec.get('preference') or 'none'} · "
             f"budget: {str(spec['budget_seconds']) + ' s' if spec.get('budget_seconds') else 'none'} · read by {spec['parsed_by']}",
             "", "PLAN (chosen from measured results)"]
    steps = {"P0": ["string-match Red Flag full names in each text"],
             "P1": [f"extract ownership events with {SMALL}", "keep only events whose quote is in the text"],
             "P1r": [f"extract ownership events with {SMALL}; retry with more room if the answer breaks",
                     "keep only events whose quote is in the text"],
             "P2": [f"extract ownership events with {LARGE}", "keep only events whose quote is in the text"],
             "P3": [f"extract with {SMALL}", f"re-run with {LARGE} where a free check fails",
                    "keep only events whose quote is in the text"]}[plan["name"]]
    if plan["name"] != "P0":  # P0 matches names only; it cannot see dates
        steps.append(f"match owners to the Red Flag list, holding period within {spec['period'][0]}-{spec['period'][1]}")
    steps.append("verdict per object: flagged / not decided / not flagged, with evidence")
    lines += [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
    lines += ["", f"  chosen {plan['name']}: screening F1 {plan['screen_f1']:.2f}, about {plan['est_seconds']} s",
              "  alternatives: " + "; ".join(f"{p['name']} F1 {p['screen_f1']:.2f} ~{p['est_seconds']} s" + (" (over budget)" if p["over_budget"] else "")
                                for p in plans if p["name"] != plan["name"])]
    print("\n".join(lines), flush=True)


def run(plan, spec, docs):
    keys, rx = score.load_keys(score.REDFLAG)
    years = range(spec["period"][0], spec["period"][1] + 1)
    out = []
    for d in docs:
        if plan == "P0":
            hit = score.match(d["provenance_text"], rx, keys, tier="fullname")
            out.append({"doc": d, "verdict": "flagged" if hit else "not flagged", "events": [], "keys": sorted(hit)})
            continue
        r = {"P1": lambda: extract.extract(SMALL, d), "P2": lambda: extract.extract(LARGE, d),
             "P1r": lambda: (lambda a: a if not a["error"] else extract.extract(SMALL, d, max_out=4096))(extract.extract(SMALL, d)),
             "P3": lambda: cascade.cascade(SMALL, LARGE, d)}[plan]()
        events = score.prepare([d], {str(d["id"]): r})[str(d["id"])]["events"]  # same quote check as the scores
        out.append({"doc": d, "verdict": score.plan_verdict(events, keys, rx, years),
                    "events": score.flag_events(events, keys, rx, years), "all": events, "error": r["error"]})
    return out


def report(results):
    flagged = [r for r in results if r["verdict"] == "flagged"]
    undecided = [r for r in results if r["verdict"] == "not decided"]
    lines = ["", f"ANSWER  {len(flagged)} flagged · {len(undecided)} not decided · "
             f"{len(results) - len(flagged) - len(undecided)} not flagged, of {len(results)} records", ""]
    for r in flagged:
        d = r["doc"]
        lines.append(f"FLAGGED  NGA {d['id']} · {d['title']}")
        for e in r["events"]:
            lines.append(f"   {e['owner']} ({e['role']}, {e.get('date') or 'no date'}): \"{e['source_span'][:160]}\"")
            rest = r["all"][r["all"].index(e) + 1:]
            nxt = next((x for x in rest if isinstance(x.get("year"), int) and x.get("span_ok")), None)  # unverified steps never date a holding
            if not isinstance(e.get("year"), int) or not re.search(r"\b19[34]\d\b", e["source_span"]):
                if nxt:  # the date that puts this holder in the period comes from the next owner's event (FR-12)
                    lines.append(f"     until {nxt['owner']} ({nxt.get('date') or nxt['year']}): \"{nxt['source_span'][:160]}\"")
        for k in r.get("keys", []):
            lines.append(f"   list match: {k}")
    for r in undecided:
        d = r["doc"]
        names = ", ".join(sorted({e["owner"] for e in r["events"]}))
        lines.append(f"NOT DECIDED  NGA {d['id']} · {d['title']}: {names} is on the list, but the text gives no date for that step")
    if len(results) <= 5:  # a question about named works: say which records were checked and not flagged
        lines += [f"NOT FLAGGED  NGA {r['doc']['id']} · {r['doc']['title']}" for r in results if r["verdict"] == "not flagged"]
    lines += ["", "These are candidates and evidence for an expert to review, not a finding about any person or a restitution claim."]
    print("\n".join(lines))


def main():
    args = [a for a in sys.argv[1:] if a != "--plan-only"]
    if not args:
        raise SystemExit(__doc__)
    q = " ".join(args)
    spec = parse_question(q)
    pool = [d for s in spec["sources"] for d in json.loads(SOURCES[s].read_text())]
    if spec["parsed_by"].startswith("regex"):
        spec["object"] = guess_object(q, pool)  # without the model, a named work is still found by its exact title
    docs = select_docs(spec, pool)
    if not docs:
        raise SystemExit(f"QUESTION  {q}\nNOT IN SOURCES  \"{spec['object']}\" is not among the records of "
                         f"{', '.join(spec['sources'])}. This demo cannot answer for objects outside them.")
    plan, plans = choose_plan(spec, len(docs))
    show_plan(q, spec, plan, plans, len(docs))
    if "--plan-only" in sys.argv:
        return
    t0 = time.time()
    results = run(plan["name"], spec, docs)
    report(results)
    print(f"\nran in {time.time() - t0:.0f} s wall (cached answers are reused)")


if __name__ == "__main__":
    main()
