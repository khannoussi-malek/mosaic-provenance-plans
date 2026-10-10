"""P5: Red Flag adjudicator agent, run on the documents a plan flags.
For each flagged document it reads the evidence quotes and the list entry's note and decides: same person? which role?
A 'no' removes the flag (false name match); the role is scored against the labelers' agreed roles.

Usage: python3 adjudicate.py MODEL RUN.json OUT.json      (e.g. qwen3:8b out/run_P3.json out/run_P5.json)
"""
import csv
import json
import sys
from pathlib import Path

import score as s
from extract import call_raw

PROMPT = """You check one match between a museum provenance record and the 1946 ALIU Red Flag Names List
(people and firms that US investigators linked to Nazi-era art looting; it also lists victims and mainstream firms).

Evidence from the provenance text:
{quotes}

Red Flag list entry and note:
{entries}

Answer two questions from this evidence only.
same: is the list entry the same person or firm as the owner in the evidence? "yes", "no" or "unclear"
role: their role according to the note: "perpetrator" (looter, agent, Nazi- or Fascist-linked dealer, collaborator),
"victim" (collection seized, persecuted), "firm" (auction house or mainstream dealer with a neutral note), "other", "unclear".
Answer with JSON only: {{"same": "...", "role": "...", "why": "max 15 words"}}"""


def main():
    model, run_path, out_path = sys.argv[1:4]
    docs = {d["id"]: d for d in json.loads(s.TESTSET.read_text())}
    keys, rx = s.load_keys(s.REDFLAG)
    notes = {r["name"]: r["notes"] for r in csv.DictReader(open(s.REDFLAG))}
    results = s.prepare(list(docs.values()), {str(r["id"]): r for r in json.loads(Path(run_path).read_text())})
    out = []
    for i, r in results.items():
        verdict = s.plan_verdict(r["events"], keys, rx)
        row = {"id": i, "base_verdict": verdict, "verdict": verdict, "same": None, "role": None, "seconds": 0.0}
        if verdict == "flagged":
            hits = [e for e in r["events"] if e.get("span_ok") and s.match(s.forward(e["owner"]), rx, keys, tier="fullname")]
            found = set().union(*(s.match(s.forward(e["owner"]), rx, keys, tier="fullname") for e in hits))
            quotes = "\n".join(f'- {e["owner"]} ({e.get("date") or "no date"}): "{e["source_span"]}"' for e in hits)
            entries = "\n".join(f"- {n}: {notes.get(n, '')}" for k in sorted(found) for n in keys[k])
            try:
                resp = call_raw(model, PROMPT.format(quotes=quotes, entries=entries))
                c = resp["message"]["content"]
                ans = json.loads(c[c.find("{"): c.rfind("}") + 1], strict=False)
                row.update(same=ans.get("same"), role=ans.get("role"), why=ans.get("why"),
                           seconds=resp.get("total_duration", 0) / 1e9)
                row["verdict"] = {"yes": "flagged", "no": "not flagged"}.get(row["same"], "not decided")
            except (OSError, KeyError, ValueError) as e:
                row["error"] = f"{type(e).__name__}: {e}"  # adjudicator failed: keep the base verdict
        out.append(row)
        if row["same"]:
            print(f"{i}: same={row['same']} role={row['role']} -> {row['verdict']}", flush=True)
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"adjudicated {sum(r['same'] is not None for r in out)} flagged docs, "
          f"{sum(r['base_verdict'] != r['verdict'] for r in out)} verdicts changed")


if __name__ == "__main__":
    main()
