"""Spelling-variant, language, and date-range defect counts in the filtered CSVs.
Usage: python -I defects.py <csv>..."""
import csv, re, sys
from collections import Counter
csv.field_size_limit(10**9)
VARIANTS = {"Muehlmann": r"M(?:ü|ue|u)hlmann", "Goering": r"G(?:ö|oe|o)ring", "Boehler": r"B(?:ö|oe|o)hler",
            "Haberstock": r"Haberstoc?k", "Rosenberg (ERR)": r"Einsatzstab|\bE\.?R\.?R\.?\b", "Hoffmann": r"Hoff?mann"}
LANG = {"German words": r"\b(?:Sammlung|Kunsthandlung|Versteigerung|erworben|durch|verkauft)\b",
        "French words": r"\b(?:vente|acquis|collection de|chez|par descendance)\b",
        "Dutch words": r"\b(?:verzameling|kunsthandel|veiling)\b"}
for path in sys.argv[1:]:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    texts = [r["provenance_text"] for r in rows]
    print(f"\n== {path}: {len(rows)} texts")
    for k, p in VARIANTS.items():
        c = Counter(m.group(0) for t in texts for m in re.finditer(p, t))
        print(f"  {k}: {dict(c.most_common(6))}")
    for k, p in LANG.items():
        print(f"  {k}: {sum(bool(re.search(p, t)) for t in texts)} texts")
    print("  'by 19xx'/'c. 19xx'/'?' uncertainty markers:", sum(bool(re.search(r"\b(?:by|c\.|circa|about|until|before|after) 19[34]\d|\?", t)) for t in texts))
    print("  footnote markers [n]:", sum(bool(re.search(r"\[\d+\]", t)) for t in texts))
    print("  replacement/mojibake chars:", sum(("�" in t or "Ã" in t) for t in texts))
    print("  only decade/range not year (e.g. 1930s):", sum(bool(re.search(r"19[34]0s", t)) for t in texts))
