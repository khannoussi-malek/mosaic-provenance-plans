"""Score plans on the NGA test set.

Usage:
  python3 score.py                      # P0 baseline only
  python3 score.py out/run_P1.json ...  # plus extraction plans (output of extract.py)

Two tasks:
  owners    - extracted owners vs NGA's structured previous owners (gold)
  screening - flagged / not decided / not flagged vs silver labels derived from gold owners
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "phase0" / "scripts"))
from analyze import fold, load_keys, match  # noqa: E402  (reuse phase-0 Red Flag matching)

HERE = Path(__file__).parent
TESTSET = HERE / "data" / "testset_nga.json"
DEVSET = HERE / "data" / "devset_nga.json"
REDFLAG = HERE.parent / "phase0" / "data" / "red_flag_names.csv"
WAR = range(1933, 1946)
STOP = {"the", "and", "de", "von", "van", "der", "la", "le", "du", "of", "et", "cie", "co", "inc", "ltd", "gallery",
        "galerie", "collection", "sale", "baron", "count", "dr", "prof", "mr", "mrs", "mme", "m"}


RECEIVER = {"national", "gallery", "art", "nga", "washington", "dc", "of"}  # the museum that now holds the object


def prepare(docs, results):
    """Definition fixes (7 Oct, from error analysis), applied to every plan alike:
    the receiving museum is not a *previous* owner, and quote checks ignore whitespace differences."""
    norm = lambda t: " ".join(t.split())
    texts = {d["id"]: norm(d["provenance_text"]) for d in docs}
    for r in results.values():
        text = texts.get(str(r["id"]), "")
        r["events"] = [dict(e, span_ok=bool(e.get("source_span")) and norm(e["source_span"]) in text)
                       for e in r["events"] if not (tokens(e["owner"]) and tokens(e["owner"]) <= RECEIVER)]
    return results


def tokens(name):
    return {t for t in re.findall(r"[a-z]+", fold(name).lower()) if len(t) > 1 and t not in STOP}


def same_owner(a, b):
    """ponytail: token-subset match ('Goering, Hermann, Reichsmarschall' ~ 'Hermann Goering'); fuzzy upgrade later."""
    ta, tb = tokens(a), tokens(b)
    return bool(ta and tb) and (ta <= tb or tb <= ta)


def forward(name):
    """'Goering, Hermann, Reichsmarschall' -> 'Hermann Goering' so full-name matching can see the forename."""
    parts = [p.strip() for p in name.split(",")]
    return f"{parts[1]} {parts[0]}" if len(parts) > 1 else name


def silver_label(doc, keys, rx):
    """flagged if a gold owner is on the Red Flag list (full name) and held it in 1933-45 or undated."""
    for g in doc["gold_owners"]:
        years = [y for y in (g["beginyear"], g["endyear"]) if y]
        in_war = not years or (min(years) <= 1945 and max(years) >= 1933)
        if in_war and match(forward(g["name"]), rx, keys, tier="fullname"):
            return "flagged"
    return "not flagged"


def p0_verdict(doc, keys, rx):
    return "flagged" if match(doc["provenance_text"], rx, keys, tier="fullname") else "not flagged"


def holding_status(events, i, keys, rx, years=WAR):
    """For a supported Red Flag event: 'flagged' if the owner's holding period (this event's year to the next dated
    event) meets the period, 'not decided' if the dates cannot tell, None otherwise or if the event does not count."""
    ev = events[i]
    if not ev.get("span_ok") or not match(forward(ev["owner"]), rx, keys, tier="fullname"):
        return None
    dated = [e.get("year") if isinstance(e.get("year"), int) and e.get("span_ok") else None for e in events]  # an unverified step never ends a holding
    start = dated[i]
    end = next((y for y in dated[i + 1:] if y is not None), None)
    if (start is None or start <= years[-1]) and (end is None or end >= years[0]) and (start or end):
        lo, hi = start or end, end or start
        if lo <= years[-1] and hi >= years[0]:
            return "flagged"
    if start is None and end is None or (start is not None and start < years[0] and end is None):
        return "not decided"
    return None


def plan_verdict(events, keys, rx, years=WAR):
    """An owner held the object from their event's year until the next dated event; flag if that span meets the period.
    Same definition as silver_label (holding interval overlaps the period). Unsupported events never count (QR-1)."""
    status = [holding_status(events, i, keys, rx, years) for i in range(len(events))]
    return "flagged" if "flagged" in status else "not decided" if "not decided" in status else "not flagged"


def flag_events(events, keys, rx, years=WAR):
    """The events that make a document flagged: the evidence an answer should cite."""
    return [e for i, e in enumerate(events) if holding_status(events, i, keys, rx, years) == "flagged"]


def owner_scores(docs, results):
    """Only supported events count (same rule as the verdict); most specific names match first."""
    tp = fp = fn = 0
    for d in docs:
        gold = [g["name"] for g in d["gold_owners"]]
        pred = [e["owner"] for e in results.get(d["id"], {}).get("events", []) if e.get("span_ok")]
        pred.sort(key=lambda p: len(tokens(p)), reverse=True)
        used = set()
        for p in pred:
            hit = next((i for i, g in enumerate(gold) if i not in used and same_owner(p, g)), None)
            if hit is None:
                fp += 1
            else:
                used.add(hit)
                tp += 1
        fn += len(gold) - len(used)
    return prf(tp, fp, fn)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"P": round(p, 3), "R": round(r, 3), "F1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def screening(docs, verdicts, labels):
    docs = [d for d in docs if labels[d["id"]] != "uncertain"]
    tp = sum(verdicts[d["id"]] == "flagged" and labels[d["id"]] == "flagged" for d in docs)
    fp = sum(verdicts[d["id"]] == "flagged" and labels[d["id"]] != "flagged" for d in docs)
    fn = sum(verdicts[d["id"]] != "flagged" and labels[d["id"]] == "flagged" for d in docs)
    out = prf(tp, fp, fn)
    out["not_decided"] = sum(v == "not decided" for v in verdicts.values())
    # lenient recall: 'not decided' on a flagged doc counts as found (the expert would see it)
    found = sum(verdicts[d["id"]] != "not flagged" and labels[d["id"]] == "flagged" for d in docs)
    out["R_lenient"] = round(found / max(tp + fn, 1), 3)
    return out


def bootstrap(docs, plans, labels, b=1000, seed=0):
    """95% intervals over documents (resampled with replacement) for owners F1, screening F1, and differences to P1."""
    import random
    rng = random.Random(seed)
    stats = {}
    for _ in range(b):
        sample = [rng.choice(docs) for _ in docs]
        for name, (results, verdicts) in plans.items():
            st = stats.setdefault(name, {"owners": [], "screen": []})
            st["screen"].append(screening(sample, verdicts, labels)["F1"])
            if results is not None:
                st["owners"].append(owner_scores(sample, results)["F1"])
        for name in plans:
            if name != "P0":
                d = stats.setdefault(name + " - P0", {"owners": [], "screen": []})
                d["screen"].append(stats[name]["screen"][-1] - stats["P0"]["screen"][-1])
        if "run_P1" in plans:
            for name in plans:
                if name in ("run_P1", "P0") or plans[name][0] is None or name.endswith(" - P0"):
                    continue
                d = stats.setdefault(name + " - P1", {"owners": [], "screen": []})
                d["owners"].append(stats[name]["owners"][-1] - stats["run_P1"]["owners"][-1])
                d["screen"].append(stats[name]["screen"][-1] - stats["run_P1"]["screen"][-1])
    ci = lambda xs: (round(sorted(xs)[int(0.025 * len(xs))], 3), round(sorted(xs)[int(0.975 * len(xs)) - 1], 3)) if xs else None
    return {k: {m: ci(v) for m, v in st.items()} for k, st in stats.items()}


def main():
    docs = json.loads((DEVSET if "--dev" in sys.argv else TESTSET).read_text())
    keys, rx = load_keys(REDFLAG)
    labels = {d["id"]: silver_label(d, keys, rx) for d in docs}
    ref_path = HERE / "data" / "labels_reference.json"
    if "--silver" not in sys.argv and "--dev" not in sys.argv and ref_path.exists():
        ref = json.loads(ref_path.read_text())["labels"]  # two independent LLM labelers; see reference_labels.py
        labels = {i: ref.get(i, "not flagged") for i in labels}
        print("labels: reference (two independent LLM labelers); 'uncertain' docs left out of screening")
    print(f"test set: {len(docs)} docs, {sum(len(d['gold_owners']) for d in docs)} gold owners, "
          f"{sum(v == 'flagged' for v in labels.values())} silver-flagged")
    p0 = {d["id"]: p0_verdict(d, keys, rx) for d in docs}
    rows = [("P0 string match", None, screening(docs, p0, labels), {})]
    plans = {"P0": (None, p0)}
    for path in [a for a in sys.argv[1:] if not a.startswith("--")]:
        results = prepare(docs, {str(r["id"]): r for r in json.loads(Path(path).read_text())})
        events = [e for r in results.values() for e in r["events"]]
        cost = {"docs": len(results), "errors": sum(bool(r["error"]) for r in results.values()),
                "out_tok": sum(r["out_tok"] for r in results.values()),
                "seconds": round(sum(r["seconds"] for r in results.values()), 1),
                "unsupported": round(sum(not e["span_ok"] for e in events) / max(len(events), 1), 3)}
        verdicts = {d["id"]: plan_verdict(results.get(d["id"], {}).get("events", []), keys, rx) for d in docs}
        rows.append((Path(path).stem, owner_scores(docs, results), screening(docs, verdicts, labels), cost))
        plans[Path(path).stem] = (results, verdicts)
    for name, own, scr, cost in rows:
        print(f"\n{name}\n  owners:    {own or 'n/a (no extraction)'}\n  screening: {scr}\n  cost:      {cost or '0 model calls'}")
    if "--ci" in sys.argv:
        print("\n95% bootstrap intervals (1,000 resamples of the 100 documents):")
        for name, ci in bootstrap(docs, plans, labels).items():
            print(f"  {name:16s} owners F1 {ci['owners']}  screening F1 {ci['screen']}")


if __name__ == "__main__":
    main()
