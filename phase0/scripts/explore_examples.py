"""Count Nazi-era signal terms in the filtered CSVs and print short candidate demo texts.
Usage: python -I explore_examples.py <csv> [term_regex]"""
import csv, re, sys
from collections import Counter
csv.field_size_limit(10**9)
TERMS = r"Haberstock|Hofer|Boehler|B[oö]hler|Wendland|Buchholz|M[uü]e?hlmann|Lohse|Rochlitz|Theodor Fischer|G[oö]e?ring|Hitler|Linz|Einsatzstab|\bERR\b|confiscat|Central Collecting Point|restitut|forced sale|Jewish|aryani|looted|seized|Goudstikker|Gurlitt|Dietrich|Posse|Mannheimer|Rothschild"
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
rx = re.compile(sys.argv[2] if len(sys.argv) > 2 else TERMS, re.I)
c, hits = Counter(), []
for r in rows:
    found = {m.group(0).lower() for m in rx.finditer(r["provenance_text"])}
    c.update(found)
    if found:
        hits.append((len(found), r))
print(len(rows), "rows;", len(hits), "with signal terms"); print(c.most_common(40))
for n, r in sorted(hits, key=lambda x: -x[0])[:12]:
    print(f"\n### {r['id']} | {r['title'][:60]} | {r['artist'][:40]} | terms={n} len={len(r['provenance_text'])}\n{r['provenance_text'][:600]}")
