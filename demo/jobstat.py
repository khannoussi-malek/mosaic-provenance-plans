"""One-line progress summary of the plan runs, read from their logs (for the tracker page)."""
import json
import re
from pathlib import Path

OUT = Path(__file__).parent / "out"
LINE = re.compile(r"(\d+)/(\d+) spans ok, ([\d.]+)s, out_tok=\d+, err=(.*)$")


def stat(log):
    rows = [LINE.search(l) for l in log.read_text().splitlines()] if log.exists() else []
    rows = [m for m in rows if m]
    if not rows:
        return {"done": 0}
    secs = [float(m.group(3)) for m in rows]
    return {"done": len(rows), "avgSec": round(sum(secs) / len(secs), 1),
            "spansOk": sum(int(m.group(1)) for m in rows), "spansTotal": sum(int(m.group(2)) for m in rows),
            "errors": sum(m.group(4) != "None" for m in rows)}


if __name__ == "__main__":
    s = {p: stat(OUT / f"run_{p}.log") for p in ("P1", "P2")}
    p3 = OUT / "run_P3.log"
    s["P3"] = {"done": sum("escalated=" in l for l in p3.read_text().splitlines())} if p3.exists() else {"done": 0}
    s["scored"] = (OUT / "scores.txt").exists()
    print(json.dumps(s))
