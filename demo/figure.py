"""Quality and compute for every plan, from out/results.json -> docs/figure.svg (fixed light theme, for print).

One row per plan, three aligned columns: owner-extraction F1 and screening F1 (dot + 95% interval), and compute minutes
per 100 documents (bar). A row layout keeps every label clear even when plans cost almost the same.
"""
import json

import score as s

OUT = s.HERE.parent / "docs" / "figure.svg"
INK, INK2, GRID, MARK, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#2a78d6", "#fcfcfb"
NAMES = {"P0": "P0 name match", "P1": "P1 small model", "P1r": "P1r small + retry", "P2": "P2 large model",
         "P3": "P3 cascade", "P4": "P4 small + verifier", "P5": "P5 cascade + adjudicator"}
ORDER = ["P0", "P1", "P1r", "P2", "P3", "P4", "P5"]
W, ROW, TOP, LABEL_W, COL_GAP = 860, 30, 58, 178, 30


def column(x0, width, title, lo, hi, ticks, rows, kind):
    sx = lambda v: x0 + (v - lo) / (hi - lo) * width
    bottom = TOP + ROW * len(rows)
    g = [f'<text x="{x0}" y="22" font-size="12.5" font-weight="600" fill="{INK}">{title}</text>']
    for t in ticks:
        g.append(f'<line x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="{TOP - 10}" y2="{bottom}" stroke="{GRID}" stroke-width="1"/>'
                 f'<text x="{sx(t):.1f}" y="{TOP - 16}" font-size="10.5" fill="{INK2}" text-anchor="middle">{t:g}</text>')
    for i, r in enumerate(rows):
        y = TOP + ROW * i + ROW / 2
        if isinstance(r, str):
            g.append(f'<text x="{x0 + 4}" y="{y + 4:.1f}" font-size="11" fill="{INK2}">{r}</text>')
        elif kind == "bar":
            g.append(f'<rect x="{x0}" y="{y - 6:.1f}" width="{max(sx(r) - x0, 0):.1f}" height="12" rx="3" fill="{MARK}"/>'
                     f'<text x="{max(sx(r), x0) + 6:.1f}" y="{y + 4:.1f}" font-size="11" fill="{INK}">{r:.0f}</text>')
        else:
            v, (a, b) = r
            g.append(f'<line x1="{sx(a):.1f}" x2="{sx(b):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{MARK}" stroke-width="2" stroke-linecap="round"/>'
                     f'<circle cx="{sx(v):.1f}" cy="{y:.1f}" r="5" fill="{MARK}" stroke="{SURFACE}" stroke-width="2"/>'
                     f'<text x="{sx(b) + 7:.1f}" y="{y + 4:.1f}" font-size="11" fill="{INK}">{v:.2f}</text>')
    return g


def main():
    plans = json.loads((s.HERE / "out" / "results.json").read_text())["plans"]
    names = [n for n in ORDER if n in plans]
    rows = len(names)
    H = TOP + ROW * rows + 34
    cw = (W - LABEL_W - 2 * COL_GAP - 40) / 3
    xmax = max(10, (int(max(p["seconds"] for p in plans.values()) / 60 / 10) + 1) * 10)
    owners = ["same as P3" if n == "P5" else "no extraction" if not plans[n]["owners"]
              else (plans[n]["owners"]["F1"], plans[n]["owners_ci"]) for n in names]
    screen = [(plans[n]["screen"]["F1"], plans[n]["screen_ci"]) for n in names]
    minutes = [plans[n]["seconds"] / 60 for n in names]
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif" role="img" '
           f'aria-label="Owner extraction F1, screening F1 and compute minutes for each plan">',
           f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>']
    for i, n in enumerate(names):
        y = TOP + ROW * i + ROW / 2
        svg.append(f'<text x="8" y="{y + 4:.1f}" font-size="12" fill="{INK}">{NAMES[n]}</text>')
        if i:
            svg.append(f'<line x1="8" x2="{W - 8}" y1="{TOP + ROW * i:.1f}" y2="{TOP + ROW * i:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
    x = LABEL_W
    svg += column(x, cw, "Owner extraction F1", 0.70, 0.85, [0.70, 0.75, 0.80, 0.85], owners, "dot")
    x += cw + COL_GAP
    svg += column(x, cw, "Screening F1", 0.45, 1.00, [0.5, 0.6, 0.7, 0.8, 0.9, 1.0], screen, "dot")
    x += cw + COL_GAP
    svg += column(x, cw, "Compute, minutes per 100 docs", 0, xmax, list(range(0, xmax + 1, 20)), minutes, "bar")
    svg.append(f'<text x="8" y="{H - 10}" font-size="10.5" fill="{INK2}">NGA test set: owners n = 100, screening 91 documents with '
               f'reference labels. Dots: estimate; lines: 95% bootstrap interval. One laptop (Apple M4 Pro), local models.</text>')
    svg.append("</svg>")
    OUT.write_text("\n".join(svg))
    print(f"-> {OUT} ({rows} plans)")


if __name__ == "__main__":
    main()
