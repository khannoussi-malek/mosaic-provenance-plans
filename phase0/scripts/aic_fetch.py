"""Fetch all AIC artworks that have provenance_text via the search API.
Polite: AIC-User-Agent header, ~1 req/s, fields= limited, limit=100.
AIC caps paging at 1000 results, so we bisect on id ranges until each bucket <= 1000.
Output: JSON lines to argv[1]."""
import json, sys, time, urllib.request

URL = "https://api.artic.edu/api/v1/artworks/search"
UA = "mosaic-demo (your-email@example.org)"  # the AIC API asks for a contact address
FIELDS = ["id", "title", "artist_display", "date_display", "provenance_text", "credit_line"]
CAP = 1000  # AIC search refuses from+limit > 1000 (403 "Invalid number of results")


def post(body):
    time.sleep(1.0)  # ponytail: fixed 1 req/s, fine for ~400 requests
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "AIC-User-Agent": UA, "User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print("retry", attempt, e, file=sys.stderr)
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("AIC request failed: %r" % body)


def query(lo, hi):
    return {"bool": {"must": [{"exists": {"field": "provenance_text"}},
                              {"range": {"id": {"gte": lo, "lt": hi}}}]}}


def buckets(lo, hi):
    total = post({"query": query(lo, hi), "limit": 0})["pagination"]["total"]
    if total <= CAP or hi - lo <= 1:
        return [(lo, hi, total)] if total else []
    mid = (lo + hi) // 2
    return buckets(lo, mid) + buckets(mid, hi)


def main(out):
    n = 0
    with open(out, "w") as f:
        for lo, hi, total in buckets(0, 2_000_000):
            print("bucket", lo, hi, total, file=sys.stderr)
            for page in range((total + 99) // 100):
                d = post({"query": query(lo, hi), "fields": FIELDS, "limit": 100,
                          "from": page * 100, "sort": [{"id": "asc"}]})
                for row in d["data"]:
                    row.pop("_score", None)
                    f.write(json.dumps(row) + "\n")
                    n += 1
    print("wrote", n, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
