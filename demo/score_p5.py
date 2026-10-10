"""Score P5 against its base plan: screening on reference labels, plus role accuracy where both labelers agree on the role."""
import json
import sys
from pathlib import Path

import score as s

DATA = s.HERE / "data"


def main():
    rows = {r["id"]: r for r in json.loads(Path(sys.argv[1]).read_text())}
    docs = json.loads(s.TESTSET.read_text())
    ref = json.loads((DATA / "labels_reference.json").read_text())["labels"]
    labels = {d["id"]: ref.get(d["id"], "not flagged") for d in docs}
    base = s.screening(docs, {i: r["base_verdict"] for i, r in rows.items()}, labels)
    p5 = s.screening(docs, {i: r["verdict"] for i, r in rows.items()}, labels)
    first = {x["id"]: x["role"] for x in json.loads((DATA / "label_proposals.json").read_text())}
    second = {x["id"]: x["role"] for x in json.loads((DATA / "labels_second.json").read_text())}
    agreed = {i: first[i] for i in first if first[i] == second.get(i) and first[i] != "unclear"}
    judged = [r for r in rows.values() if r["role"] and r["id"] in agreed]
    right = sum(r["role"] == agreed[r["id"]] for r in judged)
    print(f"base plan screening: {base}\nwith P5:             {p5}")
    print(f"role accuracy on {len(judged)} docs with an agreed role: {right}/{len(judged)}"
          f" = {right / max(len(judged), 1):.2f} · adjudicator time {sum(r['seconds'] for r in rows.values()):.0f} s")


if __name__ == "__main__":
    main()
