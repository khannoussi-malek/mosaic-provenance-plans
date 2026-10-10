"""Screening verdicts per document and plan vs SILVER labels, with the evidence behind each verdict (read-only).
Usage: python3 analysis/screening_diff.py P1 P2 P3  -> analysis/screening_<plans>.json + stdout table of disagreements."""
import json
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEMO))
import score  # noqa: E402


def silver_trigger(doc, keys, rx):
    """Gold owners that make the silver label 'flagged' (same test as score.silver_label)."""
    out = []
    for g in doc["gold_owners"]:
        years = [y for y in (g["beginyear"], g["endyear"]) if y]
        in_war = not years or (min(years) <= 1945 and max(years) >= 1933)
        if in_war and score.match(score.forward(g["name"]), rx, keys, tier="fullname"):
            out.append(f"{g['name']} ({g['beginyear']}-{g['endyear']})")
    return out


def flag_evidence(events, keys, rx):
    """Red Flag full-name hits among events, with the holding period plan_verdict would compute."""
    dated = [e.get("year") if isinstance(e.get("year"), int) else None for e in events]
    out = []
    for i, e in enumerate(events):
        hit = score.match(score.forward(e["owner"]), rx, keys, tier="fullname")
        if hit:
            nxt = next((y for y in dated[i + 1:] if y is not None), None)
            out.append({"owner": e["owner"], "keys": sorted(hit), "year": dated[i], "next_year": nxt,
                        "span_ok": e.get("span_ok"), "date": e.get("date")})
    return out


def main(plans):
    docs = json.loads(score.TESTSET.read_text())
    keys, rx = score.load_keys(score.REDFLAG)
    runs = {p: {str(r["id"]): r for r in json.loads((DEMO / "out" / f"run_{p}.json").read_text())} for p in plans}
    rows = []
    for d in docs:
        row = {"id": d["id"], "stratum": d["stratum"], "silver": score.silver_label(d, keys, rx),
               "trigger": silver_trigger(d, keys, rx), "P0": score.p0_verdict(d, keys, rx)}
        for p in plans:
            r = runs[p][d["id"]]
            row[p] = score.plan_verdict(r["events"], keys, rx)
            row[p + "_ev"] = flag_evidence(r["events"], keys, rx)
            row[p + "_err"] = r.get("error")
            row[p + "_esc"] = r.get("escalated")
        rows.append(row)
    (DEMO / "analysis" / f"screening_{'-'.join(plans)}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    for row in rows:
        vs = [row[p] for p in plans]
        if row["silver"] == "flagged" or "flagged" in vs:
            print(row["id"], row["stratum"], "silver=" + row["silver"], *(f"{p}={row[p][:4]}" for p in plans), row["trigger"])


if __name__ == "__main__":
    main(sys.argv[1:] or ["P1", "P2", "P3"])
