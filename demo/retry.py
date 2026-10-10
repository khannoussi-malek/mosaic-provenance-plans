"""P1r baseline: P1, and on a parse error or truncation retry the SAME model once with a larger output limit.
Separates 'recovering failures' from 'asking a bigger model' (the cascade P3 does both).

Usage: python3 retry.py MODEL DOCS.json OUT.json
"""
import json
import sys
from pathlib import Path

from extract import extract

RETRY_OUT = 4096


if __name__ == "__main__":
    model, docs_path, out_path = sys.argv[1:4]
    results = []
    for d in json.loads(Path(docs_path).read_text()):
        r = extract(model, d)
        if r["error"]:
            again = extract(model, d, max_out=RETRY_OUT)
            r = dict(again, retried=r["error"], in_tok=r["in_tok"] + again["in_tok"],
                     out_tok=r["out_tok"] + again["out_tok"], seconds=r["seconds"] + again["seconds"])
            print(f"{d['id']}: retried -> {len(r['events'])} events, err={r['error']}", flush=True)
        results.append(r)
    Path(out_path).write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"retried {sum('retried' in r for r in results)}/{len(results)}")
