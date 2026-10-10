"""Candidate works present in both collections' 1933-45 subsets: same normalised title + artist surname token.
Usage: python -I cross_works.py <nga.csv> <aic.csv>
ponytail: crude key; catches duplicates/pendants/prints in editions, not true identity."""
import csv, re, sys, unicodedata
csv.field_size_limit(10**9)

def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9 ]", "", "".join(c for c in s if not unicodedata.combining(c))).strip()

nga = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
aic = list(csv.DictReader(open(sys.argv[2], encoding="utf-8")))
by_title = {}
for r in nga:
    by_title.setdefault(norm(r["title"]), []).append(r)
pairs = []
for a in aic:
    for n in by_title.get(norm(a["title"]), []):
        if set(norm(a["artist"]).split()) & set(norm(n["artist"]).split()) - {"the", "of", "and", "after", "attributed", "to", "french", "italian", "german", "dutch", "flemish", "american", "workshop", "follower", "circle", "school"}:
            pairs.append((n, a))
print(len(pairs), "title+artist candidate pairs")
for n, a in pairs[:25]:
    print(f"  NGA {n['id']} / AIC {a['id']}: {n['title'][:50]} | {n['artist'][:30]} | {a['artist'][:30]}")
